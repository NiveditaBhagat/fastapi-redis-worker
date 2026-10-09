import httpx

response = httpx.get( "https://api.github.com/users/octocat",timeout=5.0)

response.raise_for_status()

data = response.json()

print("Username:", data["login"])
print("Public repositories:", data["public_repos"])
print("Followers:", data["followers"])