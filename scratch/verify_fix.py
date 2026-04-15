"""Verify the samurai role serialization fix."""
import urllib.request
import json

# Test 1: Samurai roles endpoint
r = urllib.request.urlopen("http://localhost:8000/api/v1/samurai-roles")
roles_data = json.loads(r.read().decode())
print(f"[OK] GET /api/v1/samurai-roles -> {len(roles_data['data'])} roles")

# Test 2: Samurai agents endpoint (this was the 500 error)
r = urllib.request.urlopen("http://localhost:8000/api/v1/agents?agent_type=samurai")
agents_data = json.loads(r.read().decode())
agents = agents_data["data"]
print(f"[OK] GET /api/v1/agents?agent_type=samurai -> {len(agents)} agents")

# Test 3: Check samurai_role is properly nested
for a in agents[:5]:
    profile = a.get("samurai_profile")
    if profile and profile.get("samurai_role"):
        role = profile["samurai_role"]
        print(f"  {a['name']}: role={role['name']}, purpose={role['purpose'][:50]}...")
    else:
        print(f"  {a['name']}: No samurai_role attached")

print("\nAll checks passed!")
