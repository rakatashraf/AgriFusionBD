import requests, json

base = "http://localhost:8000/api/v1"
s = requests.Session()
r = s.post(base + "/auth/login/", json={
    "phone": "1700000000",
    "password": "password123",
    "role": "researcher",
})
print("login:", r.status_code)
if r.status_code != 200:
    print(r.text[:200])

for path in ["/research/locations", "/research/exports"]:
    resp = s.get(base + path)
    print("\n=== " + path + " ===")
    print("status:", resp.status_code)
    d = resp.json()
    if isinstance(d, list):
        print("LIST len=" + str(len(d)))
        if d:
            print(json.dumps(d[0], indent=2)[:400])
    elif isinstance(d, dict):
        print("DICT keys:", list(d.keys()))
        if "results" in d:
            print("results len:", len(d["results"]))
            if d["results"]:
                print(json.dumps(d["results"][0], indent=2)[:400])
