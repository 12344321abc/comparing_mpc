import requests
from typing import Literal
import uuid

class BeaverClient:
    def __init__(self, ttp_url: str = "http://84.252.132.132:8090", session_id: str = None):
        self.ttp_url = ttp_url
        self.session_id = session_id if session_id else str(uuid.uuid4())
    
    def get_session_id(self) -> str:
        return self.session_id
    
    def set_session_id(self, session_id: str):
        self.session_id = session_id

    def get_share(self, party_id: int, 
                  triple_id: int, field: Literal["Z64", "Z2"]) -> dict:
        response = requests.post(
            f"{self.ttp_url}/api/beaver/share",
            json={
                "session_id": self.session_id,
                "party_id": party_id,
                "triple_id": triple_id,
                "field": field
            },
            timeout=5
        )
        
        if response.status_code == 200:
            data = response.json()
            return {
                "a": int(data["share"]["a"]),
                "b": int(data["share"]["b"]),
                "c": int(data["share"]["c"])
            }
        elif response.status_code == 403:
            error = response.json()
            raise RuntimeError(f"Protocol violation: {error['message']}")
        else:
            raise RuntimeError(f"Request failed: {response.status_code}")
    
    def get_batch(self, party_id: int, 
                  start_id: int, count: int, field: Literal["Z64", "Z2"]) -> list[dict]:
        shares = []
        for i in range(count):
            triple_id = start_id + i
            share = self.get_share(self.session_id, party_id, triple_id, field)
            shares.append(share)
        return shares

if __name__ == '__main__':

    # --- Test Z64 field ---
    print("--- Testing Z64 field ---")
    session_id_z64 = f"test-z64-{uuid.uuid4()}"
    print(f"Session: {session_id_z64}\n")
    client = BeaverClient("http://84.252.132.132:8090", session_id_z64)
    # Party 0
    print("Party 0 requesting...")
    share0_z64 = client.get_share(0, 0, "Z64")
    print(f"Got: a={share0_z64['a']}, b={share0_z64['b']}, c={share0_z64['c']}")
    
    # Party 1
    print("\nParty 1 requesting...")
    share1_z64 = client.get_share(1, 0, "Z64")
    print(f"Got: a={share1_z64['a']}, b={share1_z64['b']}, c={share1_z64['c']}")
    
    # Verify Z64
    modulus_z64 = 2**64
    a_z64 = (share0_z64['a'] + share1_z64['a']) % modulus_z64
    b_z64 = (share0_z64['b'] + share1_z64['b']) % modulus_z64
    c_z64 = (share0_z64['c'] + share1_z64['c']) % modulus_z64
    print(f"\nValid: {c_z64 == (a_z64*b_z64) % modulus_z64}")


    # --- Test Z2 field ---
    print("\n\n--- Testing Z2 field ---")
    session_id_z2 = f"test-z2-{uuid.uuid4()}"
    print(f"Session: {session_id_z2}\n")
    client.set_session_id(session_id_z2)
    # Party 0
    print("Party 0 requesting...")
    share0_z2 = client.get_share(0, 0, "Z2")
    print(f"Got: a={share0_z2['a']}, b={share0_z2['b']}, c={share0_z2['c']}")

    # Party 1
    print("\nParty 1 requesting...")
    share1_z2 = client.get_share(1, 0, "Z2")
    print(f"Got: a={share1_z2['a']}, b={share1_z2['b']}, c={share1_z2['c']}")

    # Verify Z2
    modulus_z2 = 2
    a_z2 = (share0_z2['a'] + share1_z2['a']) % modulus_z2
    b_z2 = (share0_z2['b'] + share1_z2['b']) % modulus_z2
    c_z2 = (share0_z2['c'] + share1_z2['c']) % modulus_z2
    print(f"\nValid: {c_z2 == (a_z2 * b_z2) % modulus_z2}")