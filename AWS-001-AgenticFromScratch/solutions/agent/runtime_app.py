"""AgentCore Runtime entrypoint for the restaurant agent (Day 3, Module 05).

    agentcore configure -e runtime_app.py ...
    agentcore deploy --env MCP_URL=<Day 2 Gateway MCP URL>

Each Runtime session keeps its own agent in memory, so a conversation carries on across
invocations with the same session ID, and a paused write action can be answered later.

Request payloads:
    {"prompt": "What were my best sellers last week?"}
    {"approve": true}   or   {"approve": false}        answer the pending write action

Responses:
    {"status": "done", "answer": "...", "tool_calls": [...]}
    {"status": "needs_approval", "pending": [{"tool", "input", "message"}], "tool_calls": [...]}
    {"status": "error", "error": "..."}

The caller's bearer token (Runtime inbound JWT) is forwarded to the Gateway, so the tools
see the real user and branch scoping still applies. This needs Runtime to pass the
Authorization header through: agentcore configure --request-header-allowlist Authorization.
"""
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from bedrock_agentcore.runtime import BedrockAgentCoreApp, RequestContext

from rst_agent import ToolCallRecorder, build_agent, http_server
from rst_agent.connections import all_tools
from rst_agent.hooks import APPROVED, DECLINED

app = BedrockAgentCoreApp()


@dataclass
class Session:
    agent: Any
    recorder: ToolCallRecorder
    client: Any = None
    pending: list = field(default_factory=list)


def new_session(token: str | None) -> Session:
    """Connect to the Gateway as the caller and build a fresh agent."""
    client = http_server(token=token)
    client.start()
    recorder = ToolCallRecorder(printer=None)
    agent = build_agent(all_tools(client), recorder=recorder)  # no approver: pauses for approval
    return Session(agent=agent, recorder=recorder, client=client)


SESSIONS: dict[str, Session] = {}


def _bearer(headers: dict[str, str] | None) -> str | None:
    auth = (headers or {}).get("Authorization", "")
    return auth.removeprefix("Bearer ").strip() or None


def _reply(session: Session, result: Any) -> dict:
    calls = list(session.recorder.calls)
    if result.stop_reason == "interrupt":
        session.pending = list(result.interrupts)
        return {"status": "needs_approval", "pending": [i.reason for i in session.pending], "tool_calls": calls}
    session.pending = []
    return {"status": "done", "answer": str(result), "tool_calls": calls}


def handle(
    payload: dict,
    session_id: str,
    token: str | None,
    factory: Callable[[str | None], Session] = new_session,
) -> dict:
    session = SESSIONS.get(session_id)
    if session is None:
        session = SESSIONS[session_id] = factory(token)

    if "approve" in payload:
        if not session.pending:
            return {"status": "error", "error": "Nothing is waiting for approval in this session"}
        answer = APPROVED if payload["approve"] is True else DECLINED
        responses = [{"interruptResponse": {"interruptId": i.id, "response": answer}} for i in session.pending]
        return _reply(session, session.agent(responses))

    prompt = (payload.get("prompt") or "").strip()
    if not prompt:
        return {"status": "error", "error": 'Send {"prompt": "..."} or {"approve": true|false}'}
    if session.pending:
        return {"status": "error", "error": "A write action is waiting for approval. Send {\"approve\": ...} first"}
    session.recorder.reset()
    return _reply(session, session.agent(prompt))


@app.entrypoint
def invoke(payload: dict, context: RequestContext) -> dict:
    return handle(payload, context.session_id or "default", _bearer(context.request_headers))


if __name__ == "__main__":
    app.run()
