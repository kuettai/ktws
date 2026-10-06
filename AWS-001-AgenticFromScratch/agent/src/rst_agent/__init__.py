"""restaurant branch analyst agent built with Strands Agents.

    build_agent()        an Agent with the restaurant system prompt, recorder and approval hooks
    ask()                run one question, handling approval pauses
    ToolCallRecorder     prints and stores every tool call, step by step
    ApprovalHook         a person must approve WRITE_TOOLS before they run
    stdio_server(), http_server(), server_from_env()   connect to the restaurant MCP server
"""
from rst_agent.agent import DEFAULT_MODEL_ID, SYSTEM_PROMPT, ask, build_agent
from rst_agent.connections import http_server, server_from_env, stdio_server
from rst_agent.hooks import WRITE_TOOLS, ApprovalHook, ToolCallRecorder, auto_approver, console_approver

__all__ = [
    "DEFAULT_MODEL_ID",
    "SYSTEM_PROMPT",
    "WRITE_TOOLS",
    "ApprovalHook",
    "ToolCallRecorder",
    "ask",
    "auto_approver",
    "build_agent",
    "console_approver",
    "http_server",
    "server_from_env",
    "stdio_server",
]
