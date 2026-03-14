"""Tilde MCP server — expose SDK operations as MCP tools."""

from tilde.mcp.server import mcp


def main() -> None:
    """Run the Tilde MCP server (stdio transport)."""
    mcp.run()


__all__ = ["main", "mcp"]
