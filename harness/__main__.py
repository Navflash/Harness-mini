"""
CLI entrypoint — run `python -m harness` to start the server.
"""
import uvicorn
from . import config

if __name__ == "__main__":
    uvicorn.run(
        "harness.server:app",
        host=config.HOST,
        port=config.PORT,
        reload=False,
    )
