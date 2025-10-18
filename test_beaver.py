import uuid
from beaver import BeaverClient

def test_beaver_client():
    # --- Test Z64 field ---
    print("--- Testing Z64 field ---")
    session_id_z64 = f"test-z64-{uuid.uuid4()}"
    print(f"Session: {session_id_z64}\n")
    client = BeaverClient(session_id=session_id_z64)
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


if __name__ == '__main__':
    test_beaver_client()