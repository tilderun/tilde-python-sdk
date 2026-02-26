"""Cerebral MCP server — expose SDK operations as MCP tools."""

from cerebral.mcp.server import mcp


def main() -> None:
    """Run the Cerebral MCP server (stdio transport)."""
    mcp.run()


__all__ = ["main", "mcp"]
