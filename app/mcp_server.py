from .store import STATE
from .retrieval import retrieve

def get_metrics(): return STATE["metrics"]
def search_logs(query=""):
    q=query.lower().strip();return [x for x in STATE["logs"] if not q or q in x["message"].lower() or q in x["service"].lower()]
def get_deployments(): return STATE["deployments"][-10:]
def search_runbooks(query): return retrieve(query,3)
def catalog(): return {"protocol":"MCP server available over stdio via python -m app.mcp_server","tools":["get_metrics","search_logs","get_deployments","search_runbooks"]}
def serve():
    from mcp.server.fastmcp import FastMCP
    mcp=FastMCP("OpsPilot")
    mcp.tool()(get_metrics);mcp.tool()(search_logs);mcp.tool()(get_deployments);mcp.tool()(search_runbooks)
    mcp.run(transport="stdio")
if __name__=="__main__": serve()
