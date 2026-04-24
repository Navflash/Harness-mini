"""
FastAPI server — the API layer of the harness.

Endpoints:
  POST /chat              → send a message, get SSE-streamed response
  GET  /channels          → list channels
  GET  /channels/{id}     → get channel history
  POST /channels/{id}/branch → branch conversation at a turn
  GET  /health            → liveness check
  GET  /cost              → today's spend
  GET  /                  → serves a minimal chat UI
"""
import asyncio
import json

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from pydantic import BaseModel

from . import config
from .runner import run_agent
from .workspace import Workspace

app = FastAPI(title="Mini Agent Harness", version="0.1.0")

# Initialise workspace once at startup.
ws = Workspace(config.WORKSPACE_DIR)

# Simple lock per channel to prevent concurrent runs.
_channel_locks: dict[str, asyncio.Lock] = {}


def _lock_for(channel_id: str) -> asyncio.Lock:
    if channel_id not in _channel_locks:
        _channel_locks[channel_id] = asyncio.Lock()
    return _channel_locks[channel_id]


# ------------------------------------------------------------------
# Request / response models
# ------------------------------------------------------------------

class ChatRequest(BaseModel):
    channel: str = "default"
    message: str


class BranchRequest(BaseModel):
    turn_index: int


# ------------------------------------------------------------------
# Endpoints
# ------------------------------------------------------------------

@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/cost")
async def cost():
    return {"today_usd": round(ws.today_spend(), 6), "budget_usd": config.DAILY_BUDGET}


@app.get("/channels")
async def list_channels():
    channels_dir = ws.root / "channels"
    if not channels_dir.exists():
        return []
    return sorted([d.name for d in channels_dir.iterdir() if d.is_dir()])


@app.get("/channels/{channel_id}")
async def get_channel(channel_id: str):
    return ws.load_history(channel_id)


@app.post("/channels/{channel_id}/branch")
async def branch(channel_id: str, req: BranchRequest):
    ws.branch_at(channel_id, req.turn_index)
    return {"status": "branched", "remaining_turns": len(ws.load_history(channel_id))}


@app.post("/chat")
async def chat(req: ChatRequest):
    """Stream the agent's reply back as Server-Sent Events."""

    async def event_stream():
        lock = _lock_for(req.channel)
        async with lock:
            budget_remaining = config.DAILY_BUDGET - ws.today_spend()
            async for event in run_agent(ws, req.channel, req.message, budget_remaining):
                yield f"data: {json.dumps(event)}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


# ------------------------------------------------------------------
# Minimal chat UI  (served at /)
# ------------------------------------------------------------------

CHAT_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>Mini Agent Harness</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: system-ui, sans-serif; background: #f0f4f8; color: #1b2a4a; display: flex; flex-direction: column; height: 100vh; }
  header { padding: 14px 20px; background: #1b2a4a; border-bottom: 2px solid #2c3e6b; font-size: 1.1rem; font-weight: 600; display: flex; align-items: center; gap: 16px; color: #fff; }
  header span { flex: 1; }
  #channelBar { display: flex; align-items: center; gap: 8px; font-size: 0.85rem; font-weight: 400; }
  #channelBar select { padding: 4px 8px; border-radius: 6px; border: 1px solid #4a5f8a; background: #2c3e6b; color: #fff; font-size: 0.85rem; }
  #channelBar button { padding: 4px 10px; border-radius: 6px; border: 1px solid #4a5f8a; background: #3b5298; color: #fff; font-size: 0.85rem; cursor: pointer; }
  #channelBar button:hover { background: #4a65b0; }
  #messages { flex: 1; overflow-y: auto; padding: 20px; display: flex; flex-direction: column; gap: 12px; }
  .msg { max-width: 75%; padding: 10px 14px; border-radius: 12px; line-height: 1.5; white-space: pre-wrap; box-shadow: 0 1px 3px rgba(27,42,74,0.1); }
  .msg.user { align-self: flex-end; background: #1b2a4a; color: #fff; }
  .msg.assistant { align-self: flex-start; background: #ffffff; color: #1b2a4a; border: 1px solid #d8dee8; }
  .msg.error { align-self: center; background: #d63031; color: #fff; font-size: 0.9rem; }
  .meta { font-size: 0.75rem; color: #6b7c93; text-align: center; padding: 2px; }
  form { display: flex; gap: 8px; padding: 12px 20px; background: #ffffff; border-top: 2px solid #d8dee8; }
  input { flex: 1; padding: 10px 14px; border-radius: 8px; border: 1px solid #c5cdd8; background: #f0f4f8; color: #1b2a4a; font-size: 1rem; }
  input:focus { outline: none; border-color: #1b2a4a; background: #fff; }
  button { padding: 10px 20px; border-radius: 8px; border: none; background: #1b2a4a; color: #fff; font-size: 1rem; cursor: pointer; }
  button:hover { background: #2c3e6b; }
  button:disabled { opacity: 0.5; cursor: not-allowed; }
</style>
</head>
<body>
<header>
  <span>🤖 Mini Agent Harness</span>
  <div id="channelBar">
    <label>Channel:</label>
    <select id="channelSelect"><option value="default">default</option></select>
    <button id="newChannelBtn">+ New</button>
  </div>
</header>
<div id="messages"></div>
<form id="chatForm">
  <input id="input" placeholder="Type a message…" autocomplete="off" required />
  <button id="sendBtn" type="submit">Send</button>
</form>
<script>
const msgs = document.getElementById('messages');
const form = document.getElementById('chatForm');
const input = document.getElementById('input');
const btn = document.getElementById('sendBtn');
const channelSelect = document.getElementById('channelSelect');
const newChannelBtn = document.getElementById('newChannelBtn');

let currentChannel = 'default';

// --- Channel management ---
async function loadChannels() {
  const res = await fetch('/channels');
  const channels = await res.json();
  channelSelect.innerHTML = '';
  const seen = new Set(channels);
  if (!seen.has('default')) seen.add('default');
  for (const ch of [...seen].sort()) {
    const opt = document.createElement('option');
    opt.value = ch;
    opt.textContent = ch;
    if (ch === currentChannel) opt.selected = true;
    channelSelect.appendChild(opt);
  }
}

async function loadHistory(channel) {
  msgs.innerHTML = '';
  const res = await fetch('/channels/' + encodeURIComponent(channel));
  const history = await res.json();
  for (const m of history) {
    addBubble(m.role, m.content);
  }
}

channelSelect.addEventListener('change', () => {
  currentChannel = channelSelect.value;
  loadHistory(currentChannel);
});

newChannelBtn.addEventListener('click', () => {
  const name = prompt('Channel name (lowercase, no spaces):');
  if (!name || !/^[a-z0-9_-]+$/.test(name)) return;
  currentChannel = name;
  const opt = document.createElement('option');
  opt.value = name;
  opt.textContent = name;
  channelSelect.appendChild(opt);
  channelSelect.value = name;
  msgs.innerHTML = '';
});

// Load on startup
loadChannels().then(() => loadHistory(currentChannel));

function addBubble(role, text) {
  const d = document.createElement('div');
  d.className = 'msg ' + role;
  d.textContent = text;
  msgs.appendChild(d);
  msgs.scrollTop = msgs.scrollHeight;
  return d;
}

form.addEventListener('submit', async (e) => {
  e.preventDefault();
  const text = input.value.trim();
  if (!text) return;
  input.value = '';
  btn.disabled = true;

  addBubble('user', text);
  const bubble = addBubble('assistant', '');

  try {
    const res = await fetch('/chat', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({ message: text, channel: currentChannel }),
    });

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\\n');
      buffer = lines.pop();
      for (const line of lines) {
        if (line.startsWith('data: ')) {
          const evt = JSON.parse(line.slice(6));
          if (evt.type === 'token') {
            bubble.textContent += evt.data;
            msgs.scrollTop = msgs.scrollHeight;
          } else if (evt.type === 'done') {
            const meta = document.createElement('div');
            meta.className = 'meta';
            meta.textContent = `Cost: $${evt.cost} · ${evt.duration}s`;
            msgs.appendChild(meta);
          } else if (evt.type === 'error') {
            bubble.className = 'msg error';
            bubble.textContent = evt.data;
          }
        }
      }
    }
  } catch (err) {
    addBubble('error', 'Network error: ' + err.message);
  }
  btn.disabled = false;
  input.focus();
});
</script>
</body>
</html>"""


@app.get("/", response_class=HTMLResponse)
async def index():
    return CHAT_HTML
