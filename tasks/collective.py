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

def _secure_and(a_share: bool, b_share: bool, triple_id: int, rank: int, group, ttp_client: BeaverClient) -> bool:
    """
    Securely computes the AND of two bits using a Beaver triple.
    """
    beaver = ttp_client.get_share(rank, triple_id, "Z2")
    a_triple_share, b_triple_share, c_triple_share = \
        bool(beaver['a']), bool(beaver['b']), bool(beaver['c'])

    # Blind the shares and reveal them
    d_blinded = a_share ^ a_triple_share
    e_blinded = b_share ^ b_triple_share

    # All-reduce to reveal the blinded values to all parties
    d_tensor = torch.tensor([d_blinded], dtype=torch.bool)
    e_tensor = torch.tensor([e_blinded], dtype=torch.bool)
    dist.all_reduce(d_tensor, op=dist.ReduceOp.BXOR, group=group)
    dist.all_reduce(e_tensor, op=dist.ReduceOp.BXOR, group=group)
    d_revealed, e_revealed = d_tensor.item(), e_tensor.item()

    # Compute the share of the AND result
    # Formula for 2PC: res = c_share ^ (d*b_share) ^ (e*a_share) ^ (d*e)
    # The (d*e) term is only added by one party (rank 0) to avoid duplication.
    and_share = c_triple_share ^ (d_revealed & b_share) ^ (e_revealed & a_share)
    if rank == 0:
        and_share ^= (d_revealed & e_revealed)
    
    return and_share

def _secure_full_adder(x_share: bool, y_share: bool, carry_in_share: bool, triple_id_base: int, rank: int, group, ttp_client: BeaverClient):
    """
    Performs one bit of a secure full adder.
    Returns: (sum_share, carry_out_share)
    """
    # sum = x ^ y ^ carry_in
    propagated_share = x_share ^ y_share
    sum_share = propagated_share ^ carry_in_share

    # carry_out = (x & y) ^ (carry_in & (x ^ y))
    xy_and_share = _secure_and(x_share, y_share, triple_id_base, rank, group, ttp_client)
    carry_prop_and_share = _secure_and(carry_in_share, propagated_share, triple_id_base + 1, rank, group, ttp_client)
    carry_out_share = xy_and_share ^ carry_prop_and_share
    
    return sum_share, carry_out_share

def _synchronize_session_id(rank, group) -> str:
    """Ensures all parties use the same TTP session ID."""
    if rank == 0:
        session_id = str(uuid.uuid4())
        # Use a broadcast to send the session_id string
        obj_list = [session_id]
        dist.broadcast_object_list(obj_list, src=0, group=group)
    else:
        obj_list = [None]
        dist.broadcast_object_list(obj_list, src=0, group=group)
        session_id = obj_list[0]
    return session_id

@task("compare")
def compare(rank, world_size, ttp_server=None):
    """
    Securely compares two numbers, x (from Party 0) and y (from Party 1).
    This function implements the secure comparison protocol by computing the
    sign bit of (x - y) using a secure multi-party addition circuit.
    """
    dist.init_process_group("gloo", rank=rank, world_size=world_size)
    group = dist.new_group(list(range(world_size)))
    
    # --- 1. Setup and Initialization ---
    BIT_LENGTH = 3  # The range of numbers to compare, e.g., 0 to 2**3-1
    SECURE_ADD_BIT_LENGTH = BIT_LENGTH + 1  # Need an extra bit for two's complement sign
    
    session_id = _synchronize_session_id(rank, group)
    client = BeaverClient(ttp_url=ttp_server, session_id=session_id)
    print(f"Rank {rank}: Synchronized TTP session: {session_id}")

    # --- 2. Generate and Represent Local Values ---
    # Party 0 holds x. Party 1 computes -y in two's complement for the subtraction x + (-y).
    if rank == 0:
        value = random.randint(0, 2**BIT_LENGTH - 1)
        # For Party 0, the value is just x, represented in binary
        value_bits = torch.tensor([(value >> i) & 1 for i in range(SECURE_ADD_BIT_LENGTH)], dtype=torch.bool)
        print(f"Rank {rank}: My value x = {value}")
    else:
        value = random.randint(0, 2**BIT_LENGTH - 1)
        # For Party 1, compute -y in two's complement
        neg_value = (2**SECURE_ADD_BIT_LENGTH - value)
        value_bits = torch.tensor([(neg_value >> i) & 1 for i in range(SECURE_ADD_BIT_LENGTH)], dtype=torch.bool)
        print(f"Rank {rank}: My value y = {value} (computing as -y)")

    # --- 3. Secret Share and Distribute Values ---
    # Each party splits its value into two shares: `my_share` and `random_part`.
    # They keep `my_share` and exchange `random_part` to get shares of both x and y.
    random_part = torch.tensor([random.randint(0, 1) for _ in range(SECURE_ADD_BIT_LENGTH)], dtype=torch.bool)
    my_share = value_bits ^ random_part
    
    # This exchange logic results in:
    # Party 0 holding (share_of_x, share_of_y) = (my_share_p0, random_part_p1)
    # Party 1 holding (share_of_x, share_of_y) = (random_part_p0, my_share_p1)
    if rank == 0:
        dist.send(random_part, dst=1, group=group)
        other_random_part = torch.empty_like(random_part)
        dist.recv(other_random_part, src=1, group=group)
        x_bit_shares, y_bit_shares = my_share, other_random_part
    else:
        other_random_part = torch.empty_like(random_part)
        dist.recv(other_random_part, src=0, group=group)
        dist.send(random_part, dst=0, group=group)
        x_bit_shares, y_bit_shares = other_random_part, my_share

    # --- 4. Perform Secure Adder Circuit ---
    # Iteratively compute the sum bits and carry bits, from least to most significant.
    sum_bit_shares = []
    carry_in_share = False  # Initial carry is 0 for both parties
    
    for i in range(SECURE_ADD_BIT_LENGTH):
        # Each full adder requires 2 Beaver triples for the two secure AND operations.
        triple_id_base = i * 2
        
        sum_share, carry_out_share = _secure_full_adder(
            x_bit_shares[i].item(),
            y_bit_shares[i].item(),
            carry_in_share,
            triple_id_base,
            rank, group, client
        )
        sum_bit_shares.append(sum_share)
        carry_in_share = carry_out_share

    # --- 5. Reveal the Final Result ---
    # The most significant bit of the sum (x-y) determines the sign.
    sign_bit_share = torch.tensor([sum_bit_shares[-1]], dtype=torch.bool)

    # All-reduce to combine the shares and reveal the final sign bit.
    dist.all_reduce(sign_bit_share, op=dist.ReduceOp.BXOR, group=group)
    is_negative = sign_bit_share.item()

    # Rank 0 prints the final outcome.
    if rank == 0:
        print("\n" + "="*20)
        if is_negative:
            print("Result: x < y")
        else:
            print("Result: x >= y")
        print("="*20 + "\n")

    dist.destroy_process_group()
