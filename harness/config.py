"""
Configuration for the harness.
Reads from environment variables with sensible defaults.
"""
import os

# --- LLM Provider ---
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "ollama")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "http://localhost:11434/v1")
MODEL = os.getenv("MODEL", "qwen3.5:latest")

# Number of user+assistant turn pairs to keep in context (older turns are dropped)
MAX_HISTORY_TURNS = int(os.getenv("MAX_HISTORY_TURNS", "20"))

# True when pointing at a local server (Ollama, llama.cpp, LM Studio, etc.)
IS_LOCAL = "localhost" in OPENAI_BASE_URL or "127.0.0.1" in OPENAI_BASE_URL

# --- Workspace ---
WORKSPACE_DIR = os.getenv("WORKSPACE_DIR", "./workspace")

# --- Cost budget (USD per day) ---
DAILY_BUDGET = float(os.getenv("DAILY_BUDGET", "1.00"))

# --- Server ---
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8000"))
