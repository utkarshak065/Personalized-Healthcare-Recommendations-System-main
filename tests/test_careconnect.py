import os, sys, tempfile
os.environ["CC_DB_PATH"] = os.path.join(tempfile.mkdtemp(), "t.db")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "fastapi"))
from fastapi.testclient import TestClient
from main import app
c = TestClient(app); P = "/cc"

def login(email, pw):
    return {"x-token": c.post(P + "/login", json={"email": email, "password": pw}).json()["token"]}

def test_full_flow():
    assert c.post(P + "/register", json={"email": "p@x.y", "name": "Pat", "password": "secret1"}).status_code == 200
    assert c.post(P + "/register", json={"email": "p@x.y", "name": "Pat", "password": "secret1"}).status_code == 409
    H = login("p@x.y", "secret1")
    r = c.post(P + "/reports", json={"text": "headache nausea light sensitivity"}, headers=H).json()
    assert r["matches"][0]["name"] == "Migraine" and not r["urgent"]
    assert c.post(P + "/reports", json={"text": "chest pain"}, headers=H).json()["urgent"]
    docs = c.get(P + "/nearby", params={"pin": "110001", "disease": "Migraine"}).json()["doctors"]
    did = docs[0]["doctor_id"]; slot = c.get(P + "/slots", params={"doctor_id": did, "date": "2099-01-01"}).json()[0]
    assert c.post(P + "/appointments", json={"doctor_id": did, "slot": slot, "report_id": r["id"]}, headers=H).status_code == 200
    assert c.post(P + "/appointments", json={"doctor_id": did, "slot": slot}, headers=H).status_code == 409
    n = [d for d in range(1, 49) if c.post(P + "/login", json={"email": f"doctor{d}@demo.test", "password": "doctor123"}).json().get("name")]
    assert len(n) == 48

def test_auth_required():
    assert c.get(P + "/reports").status_code == 401
    assert c.get(P + "/search", params={"pin": "000000"}).json()["doctors"] == []
