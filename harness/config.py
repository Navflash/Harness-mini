"""
Configuration for the harness.
Reads from environment variables with sensible defaults.
"""
import os

# --- LLM Provider ---
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
MODEL = os.getenv("MODEL", "gpt-4o-mini")

# --- Workspace ---
WORKSPACE_DIR = os.getenv("WORKSPACE_DIR", "./workspace")

# --- Cost budget (USD per day) ---
DAILY_BUDGET = float(os.getenv("DAILY_BUDGET", "1.00"))

# --- Server ---
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8000"))
