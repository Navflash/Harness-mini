"""
Workspace manager — file-based conversation persistence.

Each channel gets its own directory under the workspace root:

    workspace/
      channels/
        <channel_id>/
          history.jsonl      ← full message log
          threads.json       ← thread metadata list
          memory.md          ← channel-specific memory (user-editable)
          scratch/            ← temp files for the current run
      global_memory.md       ← facts available to every channel
      cost_ledger.json       ← daily spend tracking
"""
import json
import os
import time
import uuid
from datetime import date
from pathlib import Path
from typing import Optional


class Workspace:
    """Manages the file-backed workspace for all channels."""

    def __init__(self, root: str):
        self.root = Path(root)
        self._ensure_dirs()

    # ------------------------------------------------------------------
    # Initialisation helpers
    # ------------------------------------------------------------------

    def _ensure_dirs(self):
        (self.root / "channels").mkdir(parents=True, exist_ok=True)
        # Create default global memory if missing.
        gm = self.root / "global_memory.md"
        if not gm.exists():
            gm.write_text(
                "# Global Memory\n\n"
                "Write facts here that the agent should always know.\n"
            )
        # Ensure cost ledger exists.
        cl = self.root / "cost_ledger.json"
        if not cl.exists():
            cl.write_text("{}")

    def channel_dir(self, channel_id: str) -> Path:
        d = self.root / "channels" / channel_id
        d.mkdir(parents=True, exist_ok=True)
        (d / "scratch").mkdir(exist_ok=True)
        return d

    # ------------------------------------------------------------------
    # Message history  (JSONL – one JSON object per line)
    # ------------------------------------------------------------------

    def append_message(self, channel_id: str, role: str, content: str):
        """Append a message to the channel's history file."""
        path = self.channel_dir(channel_id) / "history.jsonl"
        entry = {"role": role, "content": content, "ts": time.time()}
        with open(path, "a") as f:
            f.write(json.dumps(entry) + "\n")

    def load_history(self, channel_id: str) -> list[dict]:
        """Return all messages as a list of {role, content} dicts."""
        path = self.channel_dir(channel_id) / "history.jsonl"
        if not path.exists():
            return []
        messages = []
        for line in path.read_text().splitlines():
            if line.strip():
                obj = json.loads(line)
                messages.append({"role": obj["role"], "content": obj["content"]})
        return messages

    def branch_at(self, channel_id: str, turn_index: int):
        """Truncate history to `turn_index` messages (branching)."""
        history = self.load_history(channel_id)
        history = history[:turn_index]
        path = self.channel_dir(channel_id) / "history.jsonl"
        with open(path, "w") as f:
            for msg in history:
                entry = {"role": msg["role"], "content": msg["content"], "ts": time.time()}
                f.write(json.dumps(entry) + "\n")

    # ------------------------------------------------------------------
    # Threads
    # ------------------------------------------------------------------

    def create_thread(self, channel_id: str, user_summary: str) -> str:
        """Create a thread record, return the thread ID."""
        tid = uuid.uuid4().hex[:8]
        path = self.channel_dir(channel_id) / "threads.json"
        threads = json.loads(path.read_text()) if path.exists() else []
        threads.append({
            "id": tid,
            "summary": user_summary[:120],
            "status": "running",
            "started": time.time(),
            "cost_usd": 0.0,
            "duration_s": 0.0,
        })
        path.write_text(json.dumps(threads, indent=2))
        return tid

    def finish_thread(self, channel_id: str, tid: str, cost: float, duration: float):
        path = self.channel_dir(channel_id) / "threads.json"
        threads = json.loads(path.read_text()) if path.exists() else []
        for t in threads:
            if t["id"] == tid:
                t["status"] = "done"
                t["cost_usd"] = cost
                t["duration_s"] = round(duration, 2)
        path.write_text(json.dumps(threads, indent=2))

    # ------------------------------------------------------------------
    # Memory / context injection
    # ------------------------------------------------------------------

    def global_memory(self) -> str:
        return (self.root / "global_memory.md").read_text()

    def channel_memory(self, channel_id: str) -> str:
        path = self.channel_dir(channel_id) / "memory.md"
        if not path.exists():
            path.write_text(f"# Channel Memory — {channel_id}\n")
        return path.read_text()

    # ------------------------------------------------------------------
    # Cost ledger  (daily JSON: {"2026-04-22": 0.0042, ...})
    # ------------------------------------------------------------------

    def record_cost(self, amount: float):
        path = self.root / "cost_ledger.json"
        ledger = json.loads(path.read_text())
        today = str(date.today())
        ledger[today] = ledger.get(today, 0.0) + amount
        path.write_text(json.dumps(ledger, indent=2))

    def today_spend(self) -> float:
        path = self.root / "cost_ledger.json"
        ledger = json.loads(path.read_text())
        return ledger.get(str(date.today()), 0.0)
