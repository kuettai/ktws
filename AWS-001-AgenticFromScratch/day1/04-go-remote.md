# D1 M04 — Go Remote (30m)

## Objectives
- Switch transport from stdio to Streamable HTTP.
- Understand why stateless mode matters behind a load balancer.
- Run the server in a container locally.

## Steps
1. Read `main()` in `server.py` — already supports both transports:

    ```python
    mcp.run(
        "streamable-http",
        host="0.0.0.0",
        port=int(os.environ.get("PORT", "8000")),
        stateless_http=True,
        json_response=True,
    )
    ```
    and a `/health` route for the load balancer.

2. Run over HTTP: `MCP_TRANSPORT=http uv run python server.py` (PowerShell: `$env:MCP_TRANSPORT = "http"; uv run python server.py`, then `Remove-Item Env:MCP_TRANSPORT` to go back to stdio)
3. Test: Inspector → transport "Streamable HTTP" → `http://localhost:8000/mcp`.

    > **Screenshot** — `<SCREENSHOT_YET_TO_PREPARE>` MCP Inspector with transport Streamable HTTP and URL `http://localhost:8000/mcp` · save as `img/m04-inspector-http.png`

4. Container (needs Docker or Finch), from the workshop folder:

    ```bash
    docker compose --profile http up --build
    ```

    ```powershell
    docker compose --profile http up --build
    ```
    Starts mock-api, legacy-app and the MCP server on `:8000`.

5. Point Kiro at `http://localhost:8000/mcp` (no auth yet).

## stdio vs Streamable HTTP

```mermaid
flowchart LR
    subgraph local["stdio (M01-M03)"]
        k1["Kiro"] -- "starts the process,<br/>stdin / stdout" --> s1["server.py<br/>on your laptop"]
    end
    subgraph remote["Streamable HTTP (M04 onward)"]
        k2["Kiro / Quick"] -- "HTTPS POST /mcp" --> lb["Load balancer"]
        lb --> t1["Task 1"]
        lb --> t2["Task 2"]
    end
```

Open full size: [PNG](img/diagrams/04-go-remote-1.png) · [SVG](img/diagrams/04-go-remote-1.svg)

**Why stateless:** the load balancer may send each request to a different task. With `stateless_http=True` no task keeps session state, so any task can answer any request and no sticky sessions are needed.

## Key concepts
- **Stateless:** each request independent → any ECS task can serve it, no sticky sessions. AgentCore Runtime (Day 2) also expects this.
- **JSON responses:** no long-lived SSE streams, which keeps ALB and CloudFront simple.
- **No auth yet:** anyone who can reach port 8000 can query Redshift. Fixed in M06.

## Checkpoint
HTTP server answers tool calls from Inspector and Kiro.
