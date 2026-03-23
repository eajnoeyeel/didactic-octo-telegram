"""Direct MCP connector — interface only for Phase 1. Full implementation in Phase 4+."""

from models import MCPTool, TOOL_ID_SEPARATOR


class MCPDirectConnector:
    """Connects directly to MCP servers via JSON-RPC tools/list.

    Phase 1: only parse_tools is implemented.
    Phase 4+: fetch_tools will make actual JSON-RPC calls.
    """

    async def fetch_tools(self, server_id: str, endpoint_url: str) -> list[MCPTool]:
        raise NotImplementedError("Direct MCP connection is planned for Phase 4+")

    @staticmethod
    def parse_tools(server_id: str, response: dict) -> list[MCPTool]:
        raw_tools = response.get("tools", [])
        return [
            MCPTool(
                server_id=server_id,
                tool_name=t["name"],
                tool_id=f"{server_id}{TOOL_ID_SEPARATOR}{t['name']}",
                description=t.get("description"),
                input_schema=t.get("inputSchema"),
            )
            for t in raw_tools
        ]
