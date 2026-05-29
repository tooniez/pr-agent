# PR-Agent MOSAICO Solution Agent — registration

This directory holds the MOSAICO registration template for running pr-agent as a
MOSAICO A2A *solution agent* (in-process A2A server, image target `mosaico_agent`).

## Build & run the image

```bash
# from the pr-agent repo root
docker build --target mosaico_agent -t pr-agent-mosaico -f docker/Dockerfile .
docker run -d -p 9000:9000 --name pr-agent-mosaico pr-agent-mosaico
```

The server exposes (port 9000):
- `GET /.well-known/agent-card.json` — the A2A agent card (streaming=false, observability extension, skills: review/improve/describe/ask)
- `POST /` — A2A JSON-RPC `message/send`
- `GET /health` — LLM-connectivity probe (200 `{"is_healthy": true, ...}` / 503)

MOSAICO LLM env vars (consumed by the Stage-1 env bridge at startup): `API_BASE`,
`API_KEY`, `MODEL_NAME`, and optionally `LANGFUSE_HOST`/`LANGFUSE_PUBLIC_KEY`/`LANGFUSE_SECRET_KEY`.
`HOST` (default `0.0.0.0`) / `PORT` (default `9000`) control the bind address.

## Register with MOSAICO (ENDPOINT mode)

Registration is done by the demonstrator's `register-agent.py`. ENDPOINT mode is
selected when `AGENT_CARD_URL` is set. Example:

```bash
REPOSITORY_API=http://mosaico-app:8080 \
AGENT_NAME="PR-Agent Solution Agent" \
AGENT_JSON=/app/pr-agent-solution-agent.json \
AGENT_CARD_URL=http://pr-agent-mosaico:9000/.well-known/agent-card.json \
python register-agent.py
```

- `pr-agent-solution-agent.json` is the template in this directory (kept in MOSAICO's
  `docker/agent-registrations/` at deploy time).
- `AGENT_NAME` is injected as the agent name; the card URL is set as the top-level
  `a2aAgentCardUrl` and `deployment.mode` is forced to `ENDPOINT`.
