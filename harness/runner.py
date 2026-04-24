"""
Agent runner — spawns the LLM call with full context and streams the response.

This is the core "process management" piece of the harness:
  1. Assembles the context (system prompt + memory + history).
  2. Calls the LLM via the OpenAI-compatible API.
  3. Streams tokens back through an async generator.
  4. Parses cost from the API response.
"""
import time
from typing import AsyncGenerator

import openai

from . import config
from .workspace import Workspace


def _build_system_prompt(ws: Workspace, channel_id: str) -> str:
    """Assemble everything the agent should know before reading the user's message."""
    parts = [
        "You are a helpful AI assistant.",
        "",
        "## Global Memory",
        ws.global_memory(),
        "",
        "## Channel Memory",
        ws.channel_memory(channel_id),
    ]
    return "\n".join(parts)


async def run_agent(
    ws: Workspace,
    channel_id: str,
    user_message: str,
    budget_remaining: float,
) -> AsyncGenerator[dict, None]:
    """
    Run the agent and yield events:
        {"type": "token",  "data": "..."}   — a streamed text chunk
        {"type": "done",   "cost": 0.0012}  — final event with cost
        {"type": "error",  "data": "..."}   — if something went wrong
    """
    # --- 1. Budget gate ---
    if budget_remaining <= 0:
        yield {"type": "error", "data": "Daily budget exhausted. Try again tomorrow."}
        return

    # --- 2. Build messages ---
    system_prompt = _build_system_prompt(ws, channel_id)
    history = ws.load_history(channel_id)

    messages = [{"role": "system", "content": system_prompt}]
    messages.extend(history)
    messages.append({"role": "user", "content": user_message})

    # --- 3. Persist the user message ---
    ws.append_message(channel_id, "user", user_message)

    # --- 4. Create thread ---
    summary = user_message[:80]
    tid = ws.create_thread(channel_id, summary)
    start = time.time()

    # --- 5. Call the LLM (streaming) ---
    client = openai.AsyncOpenAI(
        api_key=config.OPENAI_API_KEY,
        base_url=config.OPENAI_BASE_URL,
    )

    full_reply = ""
    prompt_tokens = 0
    completion_tokens = 0

    try:
        stream = await client.chat.completions.create(
            model=config.MODEL,
            messages=messages,
            stream=True,
            stream_options={"include_usage": True},
        )

        async for chunk in stream:
            # Usage info arrives in the final chunk.
            if chunk.usage:
                prompt_tokens = chunk.usage.prompt_tokens
                completion_tokens = chunk.usage.completion_tokens

            if chunk.choices and chunk.choices[0].delta.content:
                token = chunk.choices[0].delta.content
                full_reply += token
                yield {"type": "token", "data": token}

    except openai.APIError as exc:
        yield {"type": "error", "data": str(exc)}
        return

    # --- 6. Persist the assistant reply ---
    ws.append_message(channel_id, "assistant", full_reply)

    # --- 7. Estimate cost (rough pricing for gpt-4o-mini) ---
    cost = _estimate_cost(prompt_tokens, completion_tokens)
    duration = time.time() - start

    ws.record_cost(cost)
    ws.finish_thread(channel_id, tid, cost, duration)

    yield {"type": "done", "cost": round(cost, 6), "duration": round(duration, 2)}


def _estimate_cost(prompt_tokens: int, completion_tokens: int) -> float:
    """
    Very rough cost estimate.  Override with real pricing for your model.
    Defaults assume gpt-4o-mini pricing (~$0.15 / 1M input, ~$0.60 / 1M output).
    """
    input_cost = (prompt_tokens / 1_000_000) * 0.15
    output_cost = (completion_tokens / 1_000_000) * 0.60
    return input_cost + output_cost
