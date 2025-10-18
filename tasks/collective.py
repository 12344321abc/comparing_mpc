import torch
import torch.distributed as dist
import random
import uuid
from beaver import BeaverClient
import time
from . import task

@task("broadcast")
def broadcast(rank, world_size):
    dist.init_process_group("gloo", rank=rank, world_size=world_size)
    group = dist.new_group(list(range(world_size)))

    tensor_size = 4
    if rank == 0:
        tensor = torch.arange(tensor_size, dtype=torch.long)
    else:
        tensor = torch.zeros(tensor_size, dtype=torch.long)
    print(f"Rank {rank}: tensor before broadcast = {tensor}")

    dist.broadcast(tensor, src=0, group=group)
    print(f"Rank {rank}: tensor after broadcast = {tensor}")

    dist.destroy_process_group()

@task("reduce")
def reduce(rank, world_size):
    dist.init_process_group("gloo", rank=rank, world_size=world_size)
    group = dist.new_group(list(range(world_size)))

    tensor = torch.tensor([rank**3], dtype=torch.long)
    print(f"Rank {rank}: tensor before reduce = {tensor}")

    dist.reduce(tensor, dst=2, op=dist.ReduceOp.SUM, group=group)
    print(f"Rank {rank}: tensor after reduce = {tensor}")

    dist.destroy_process_group()

@task("all_reduce")
def all_reduce(rank, world_size):
    dist.init_process_group("gloo", rank=rank, world_size=world_size)
    group = dist.new_group(list(range(world_size)))

    tensor = torch.tensor([rank], dtype=torch.long)
    print(f"Rank {rank}: tensor before all_reduce = {tensor}")

    dist.all_reduce(tensor, op=dist.ReduceOp.SUM, group=group)
    print(f"Rank {rank}: tensor after all_reduce = {tensor}")

    dist.destroy_process_group()
 
@task("all_gather")
def all_gather(rank, world_size):
    dist.init_process_group("gloo", rank=rank, world_size=world_size)
    group = dist.new_group(list(range(world_size)))

    send_tensor = torch.tensor([rank**2], dtype=torch.long)
    recv_list = [torch.zeros(1, dtype=torch.long) for _ in range(world_size)]
    print(f"Rank {rank}: tensor before all_gather = {send_tensor}")

    dist.all_gather(recv_list, send_tensor, group=group)
    print(f"Rank {rank}: all_gather result = {recv_list}")

    dist.destroy_process_group()

triple_id = -1

def MCP_AND(group, rank, share_x, share_y, ttp:BeaverClient):
    global triple_id
    triple_id += 1
    beaver = ttp.get_share(rank, triple_id, "Z2")
    share_a = bool(beaver['a'])
    share_b = bool(beaver['b'])
    share_c = bool(beaver['c'])
    share_d = share_a^share_x
    share_e = share_b^share_y
    # print(f"triple_id: {triple_id} \t Rank {rank}: share_a = {share_a}, share_b = {share_b}, share_c = {share_c}, share_d = {share_d}, share_e = {share_e}, share_x = {share_x}, share_y = {share_y}")
    tensor_e = torch.tensor([share_e], dtype=torch.bool)
    tensor_d = torch.tensor([share_d], dtype=torch.bool)
    dist.all_reduce(tensor_e, op=dist.ReduceOp.BXOR, group=group)
    dist.all_reduce(tensor_d, op=dist.ReduceOp.BXOR, group=group)
    e = tensor_e.item()
    d = tensor_d.item()
    # print(f"Rank {rank}: e = {e}, d = {d}")
    if rank==0:
        return d&e^share_c^d&share_b^e&share_a
    else:
        return share_c^d&share_b^e&share_a

@task("compare")
def compare(rank, world_size, ttp_server = "http://84.252.132.132:8090"):
    dist.init_process_group("gloo", rank=rank, world_size=world_size)
    group = dist.new_group(list(range(world_size)))
    POWER = 3
    int_to_compare = random.randint(0, 2**POWER-1)
    if rank == 1:
        real_int_to_compare = (2**(POWER+1)-int_to_compare)%(2**(POWER+1))
        int_to_compare = -int_to_compare
    else:
        real_int_to_compare = int_to_compare
    POWER += 1
    binary_tensor_to_compare = torch.tensor([(real_int_to_compare >> i) & 1 for i in range(POWER)], dtype=torch.bool)
    print(f"Rank {rank}: {['x','-y'][rank]}= {int_to_compare}, in tensor = {binary_tensor_to_compare}")
    # dist.all_reduce(binary_tensor_to_compare, op = dist.ReduceOp.BXOR, group=group)
    # print(f"Rank {rank}: all_reduce result = {binary_tensor_to_compare}")
    binary_share_other = torch.tensor([random.randint(0, 1) for i in range(POWER)], dtype=torch.bool)
    binary_share_my = torch.tensor([binary_share_other[i] ^ binary_tensor_to_compare[i] for i in range(POWER)], dtype=torch.bool) # my part share
    if rank == 0: #to avoid deadlock
        torch.distributed.send(binary_share_other, dst=rank^1, group=group)
        torch.distributed.recv(binary_share_other, src=rank^1, group=group) 
        binary_share_x, binary_share_y = binary_share_my, binary_share_other
    else:
        binary_share_other_1 = binary_share_other.clone()
        torch.distributed.recv(binary_share_other, src=rank^1, group=group)
        torch.distributed.send(binary_share_other_1, dst=rank^1, group=group)
        binary_share_x, binary_share_y = binary_share_other, binary_share_my #x is for rank 0 y is for rank 1
    # print(f"Rank {rank}: binary_share_x = {binary_share_x}, binary_share_y = {binary_share_y}")
    ###Initialization of BeaverClient###
    # Convert UUID string to bytes tensor
    uuid_str = str(uuid.uuid4())
    uuid_bytes = uuid_str.encode('utf-8')
    session_id = torch.ByteTensor(list(uuid_bytes))

    if rank == 0:
        dist.send(session_id, dst=rank^1, group=group)
    else:
        dist.recv(session_id, src=rank^1, group=group)

    # Convert back to string
    uuid_str = bytes(session_id.tolist()).decode('utf-8')
    client = BeaverClient(ttp_server, uuid_str)
    # z_share =  torch.tensor([MCP_AND(group, rank, binary_share_x[i].item(), binary_share_y[i].item(), client) for i in range(POWER)], dtype=torch.bool)
    # print(f"Rank {rank}: z_share = {z_share}")
    summ_share = []
    for i in range(POWER):
        if i == 0:
            prev_p = False
        x_xor_y_share = binary_share_x[i].item() ^ binary_share_y[i].item()
        x_and_y_share = MCP_AND(group, rank, binary_share_x[i].item(), binary_share_y[i].item(), client)
        summ_share.append(prev_p^x_xor_y_share)
        prev_p = MCP_AND(group, rank, prev_p, x_xor_y_share, client)^x_and_y_share
    summ_share = torch.tensor(summ_share, dtype=torch.bool)
    # print(f"Rank {rank}: summ_share = {summ_share}")
    result_tensor = summ_share[-1]
    dist.all_reduce(result_tensor, op=dist.ReduceOp.BXOR, group=group)
    # print(f"Rank {rank}: result_tensor = {result_tensor}")
    if rank == 0:
        if result_tensor.item():
            print("OUR RESULT:x<y")
        else:
            print("OUR RESULT:x>=y")
    dist.destroy_process_group()
