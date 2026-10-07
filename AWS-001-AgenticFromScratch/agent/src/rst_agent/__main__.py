"""Interactive chat with the restaurant agent.

    uv run python -m rst_agent                         local server, HQ user
    uv run python -m rst_agent --role manager --branch 12
    MCP_URL=https://.../mcp MCP_TOKEN=... uv run python -m rst_agent

Each tool call is printed as a numbered step. Write actions stop and ask you to approve.
"""
import argparse

from rst_agent.agent import build_agent
from rst_agent.connections import all_tools, server_from_env
from rst_agent.hooks import ToolCallRecorder, console_approver


def main() -> None:
    parser = argparse.ArgumentParser(description="Chat with the restaurant agent")
    parser.add_argument("--role", choices=["hq", "manager", "staff"], help="simulated user (local server only)")
    parser.add_argument("--branch", type=int, help="simulated user's branch (local server only)")
    parser.add_argument("--model-id", help="Bedrock model ID (default: BEDROCK_MODEL_ID or built-in default)")
    args = parser.parse_args()

    recorder = ToolCallRecorder()
    with server_from_env(role=args.role, branch_id=args.branch) as server:
        tools = all_tools(server)
        print(f"Connected. {len(tools)} tools available. Type 'exit' to quit.\n")
        agent = build_agent(tools, approver=console_approver, recorder=recorder, model_id=args.model_id)
        while True:
            try:
                question = input("you> ").strip()
            except (EOFError, KeyboardInterrupt):
                break
            if question.lower() in ("exit", "quit"):
                break
            if not question:
                continue
            recorder.reset()
            result = agent(question)
            print(f"\nagent> {result}\n({len(recorder.calls)} tool calls)\n")


if __name__ == "__main__":
    main()
