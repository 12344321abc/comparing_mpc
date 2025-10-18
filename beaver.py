import os
import requests
from typing import Literal
import uuid

class BeaverClient:
    def __init__(self, ttp_url: str = None, session_id: str = None):
        if ttp_url is None:
            ttp_url = os.getenv("TTP_URL", "http://84.252.132.132:8090")
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
            share = self.get_share(party_id, triple_id, field)
            shares.append(share)
        return shares