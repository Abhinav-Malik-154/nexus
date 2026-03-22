import requests

AAVE_SUBGRAPH = "https://api.thegraph.com/subgraphs/name/aave/protocol-v3-polygon"

query = """
{
  markets(first: 3) {
    id
    name
  }
}
"""

response = requests.post(AAVE_SUBGRAPH, json={"query": query})
print(response.status_code)
print(response.json())
