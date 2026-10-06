# D3 M00 — Agent Fundamentals (30m)

> **Preview** — this module has not yet been tested end to end.

> **Shared account?** Put your participant name in the agent's AgentCore names (for example the runtime `rst_agent_<name>` in Module 05), as on Day 2. Delete only your own resources at the end.

On Days 1–2 we built tools. Quick and Kiro decided when to call them. Today we build that deciding part ourselves: the agent.

## Objectives
- Explain the agent loop: plan → tool call → result → next step.
- Name the ways a loop ends: final answer, question back to the user, error, step limit, pause for approval.
- Read a Day 1 Quick/Kiro session as an agent loop.

## What an agent is
> An agent runs tools in a loop to achieve a goal.

Three parts:

- **Model**: decides what to do next. Bedrock, `BEDROCK_MODEL_ID`.
- **Tools**: the ones we already built. The Day 1 MCP server's 22 tools, unchanged.
- **Loop**: the code that sends the question to the model, runs the tool it asks for, sends back the result, and repeats. Strands Agents provides this loop. We don't write it.

## The agent loop
1. The question, system prompt, tool list (names, descriptions, parameters) and past messages go to the model.
2. The model decides one of three things:
    - call one or more tools, with parameters;
    - ask the user for more information (loop ends for now);
    - give the final answer (loop ends).
3. The agent runs the tools and sends the results back to the model.
4. Back to step 2.

Everything the model knows about a tool comes from its name, docstring and parameters. This is why the Day 1 tool-design work matters: a vague description gives a confused plan.

## Exercise: read Day 1 as a loop (15m)
Replay the Day 1 M07 demo question in Kiro as `manager_branch_12`:
> What are my best-selling items this month? Am I low on any of them right now? How much of them did I waste last month?

Expand each tool call in the Kiro chat. In pairs, write the loop down:

| Step | Model decided | Tool + parameters | What came back | Why the next step |
|---|---|---|---|---|
| 1 | | | | |
| 2 | | | | |

Discuss:

- Where did the model plan? (It picked dates for "this month" and "last month", and IDs from the first result.)
- Did it ever pick a wrong or extra tool? What in the description led it there?
- What made it stop?

## Where today goes
| Module | Adds |
|---|---|
| M01 | Our own agent, with every step printed |
| M02 | Questions that need several steps, and how plans go wrong |
| M03 | A person approves anything that changes data |
| M04 | Measure the agent with 15–20 test questions |
| M05 | Run it on AgentCore |

## Checkpoint
Each pair has a filled-in loop table for the demo question and can say what ended the loop.

## Learn more
- The agent-loop explanation is adapted from the *AWS Building with Amazon Bedrock* workshop ("Agents and agentic applications").
- Strands docs: strandsagents.com → User guide → Agent loop.
