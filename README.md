# Mini Agent Harness

A beginner-friendly Python agent harness that shows the core ideas behind production agent infrastructure — in ~400 lines of code you can read in one sitting.

## What Is a Harness?

An AI agent is stateless: you send a prompt, it replies, it forgets. A **harness** is the infrastructure that wraps the agent to add:

| Capability | How this harness does it |
|---|---|
| **Conversation persistence** | JSONL message history per channel |
| **Context injection** | Global + per-channel memory files merged into the system prompt |
| **Streaming output** | Server-Sent Events (SSE) to a browser or any HTTP client |
| **Cost tracking** | Daily spend ledger with a configurable budget gate |
| **Concurrency control** | Async lock per channel — one run at a time |
| **Conversation branching** | Truncate history at any turn and continue from there |
| **Docker deployment** | Single `docker compose up` and you're running |

```
┌──────────────┐
│   Browser /  │
│   curl /     │──── POST /chat ────▶ ┌──────────────┐
│   any client │◀── SSE stream ────── │  FastAPI      │
└──────────────┘                      │  Server       │
                                      │  (server.py)  │
                                      └──────┬───────┘
                                             │
                                      ┌──────▼───────┐
                                      │  Runner       │
                                      │  (runner.py)  │
                                      │  • builds ctx │
                                      │  • calls LLM  │
                                      │  • streams    │
                                      └──────┬───────┘
                                             │
                                      ┌──────▼───────┐
                                      │  Workspace    │
                                      │  (workspace.py)│
                                      │  • history    │
                                      │  • memory     │
                                      │  • cost ledger│
                                      └──────────────┘
```

## Quick Start (Local with Ollama)

**Prerequisites:** [Install Ollama](https://ollama.ai) and download a model:
```bash
ollama pull qwen2.5:7b    # or your preferred model
ollama serve              # start Ollama server (runs on http://localhost:11434)
```

Then run the harness:

```bash
# 1. Clone & enter the project
cd harness

# 2. Create a virtualenv
python3 -m venv .venv && source .venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Run (no API key needed for local Ollama!)
python -m harness
```

Open **http://localhost:8000** — you'll see a chat UI. Type a message and watch the response stream in. Free, local, no API costs.

### Switching Models

```bash
# List available models
ollama list

# Use a different model (edit .env or set env var)
export MODEL=mistral:latest
python -m harness

# Or in .env:
MODEL=neural-chat:latest
```

## Quick Start (Docker)

With Ollama already running on your machine:

```bash
# Create .env if needed (optional—defaults to local Ollama)
cp .env.example .env

docker compose up --build
```

Open **http://localhost:8000**. The workspace directory is mounted as a volume so conversation history survives container restarts.

**Note:** The Docker container connects to Ollama on your host machine. On Linux, this usually works automatically. On macOS/Windows, you may need to set `OPENAI_BASE_URL` to point to your Docker host (e.g., `host.docker.internal:11434` on Windows/Mac).

## Project Structure

```
harness/
├── harness/
│   ├── __init__.py       # package marker
│   ├── __main__.py       # python -m harness entrypoint
│   ├── config.py         # env-based configuration
│   ├── workspace.py      # file-based persistence (history, memory, cost)
│   ├── runner.py         # LLM caller with streaming + cost tracking
│   └── server.py         # FastAPI app with SSE + minimal chat UI
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
├── .env.example
└── README.md
```

## API Reference

| Method | Path | Description |
|---|---|---|
| `GET` | `/` | Minimal chat web UI |
| `POST` | `/chat` | Send `{"channel":"default","message":"..."}`, get SSE stream |
| `GET` | `/channels` | List all channel IDs |
| `GET` | `/channels/{id}` | Get full message history for a channel |
| `POST` | `/channels/{id}/branch` | Branch at turn `{"turn_index": N}` |
| `GET` | `/cost` | Today's spend vs budget |
| `GET` | `/health` | Liveness probe |

### SSE Event Format

Each SSE `data:` line contains JSON:

```json
{"type": "token", "data": "Hello"}       // streamed text chunk
{"type": "done", "cost": 0.000123, "duration": 1.42}  // final event
{"type": "error", "data": "Budget exhausted"}          // error
```

## Workspace Layout

After a few conversations, the workspace directory looks like:

```
workspace/
├── global_memory.md          ← edit this to give the agent persistent knowledge
├── cost_ledger.json          ← daily spend tracking
└── channels/
    └── default/
        ├── history.jsonl     ← full conversation log
        ├── threads.json      ← thread metadata
        ├── memory.md         ← channel-specific memory
        └── scratch/          ← temp working area
```

All files are human-readable JSON/JSONL/Markdown — easy to inspect and debug.

## Configuration

All settings come from environment variables (or `.env`):

| Variable | Default | Description |
|---|---|---|
| `OPENAI_API_KEY` | `ollama` | API key; use "ollama" for local (no key needed) |
| `OPENAI_BASE_URL` | `http://localhost:11434/v1` | Endpoint URL (defaults to Ollama local) |
| `MODEL` | `qwen2.5:7b` | Model name to run |
| `MAX_HISTORY_TURNS` | `20` | Keep last N user+assistant turn pairs (prevents context overflow) |
| `DAILY_BUDGET` | `1.00` | Max USD spend per day (bypassed for local Ollama) |
| `WORKSPACE_DIR` | `./workspace` | Where conversation data lives |
| `HOST` | `0.0.0.0` | Server host |
| `PORT` | `8000` | Server port |

### Using OpenAI API (instead of local Ollama)

```bash
export OPENAI_API_KEY=sk-...your-key...
export OPENAI_BASE_URL=https://api.openai.com/v1
export MODEL=gpt-4o-mini
python -m harness
```

### Using Other Local LLM Servers

The harness works with any OpenAI-compatible endpoint:

```bash
# LM Studio (default port 1234)
export OPENAI_BASE_URL=http://localhost:1234/v1
export MODEL=your-model-name

# llama.cpp (if server enabled)
export OPENAI_BASE_URL=http://localhost:8000/v1

# Together.ai
export OPENAI_API_KEY=your-together-key
export OPENAI_BASE_URL=https://api.together.xyz/v1
export MODEL=meta-llama/Meta-Llama-3-70B-Instruct

python -m harness
```

## Key Concepts Demonstrated

1. **Stateless agent, stateful harness** — the LLM has no memory; the harness persists everything.
2. **File-based storage** — no database needed; JSON/JSONL files you can `cat` and `grep`.
3. **Context injection** — global and channel memory are assembled into the system prompt automatically.
4. **Bounded context** — `MAX_HISTORY_TURNS` keeps the KV cache from growing unbounded (important for local models).
5. **Streaming delivery** — SSE so the browser shows tokens as they arrive.
6. **Cost as first-class concern** — every run is metered and gated against a daily budget (skipped for local Ollama).
7. **Multi-backend support** — works with OpenAI, Ollama, LM Studio, Together.ai, or any OpenAI-compatible endpoint.
8. **Abstract delivery** — the runner yields events; the server decides how to deliver them.

## License

MIT
