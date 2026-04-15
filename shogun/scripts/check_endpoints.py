"""Quick endpoint health check."""
import urllib.request
import json

endpoints = [
    "/api/v1/system/health",
    "/api/v1/agents/shogun",
    "/api/v1/personas",
    "/api/v1/model-routing-profiles",
    "/api/v1/security/policies",
]

for ep in endpoints:
    try:
        r = urllib.request.urlopen(f"http://localhost:8000{ep}")
        print(f"  {r.status} OK  {ep}")
    except Exception as e:
        print(f"  FAIL   {ep}  ({e})")
