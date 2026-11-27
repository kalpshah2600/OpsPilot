"""Minimal MCP-style tool catalog.
This project keeps the transport dependency optional; these JSON-schema contracts are the
same boundary used by the agent and can be exposed through an MCP SDK when configured.
"""
TOOLS=[
 {"name":"get_metrics","description":"Read current service metrics","inputSchema":{"type":"object","properties":{}}},
 {"name":"search_logs","description":"Search recent service logs","inputSchema":{"type":"object","properties":{"query":{"type":"string"}}}},
 {"name":"get_deployments","description":"Read recent deployment history","inputSchema":{"type":"object","properties":{}}},
 {"name":"search_runbooks","description":"Retrieve operational knowledge","inputSchema":{"type":"object","properties":{"query":{"type":"string"}},"required":["query"]}},
]

def catalog(): return {"protocol":"MCP-compatible contracts","tools":TOOLS}
