from __future__ import annotations

import importlib.metadata

from fastapi import FastAPI

app = FastAPI(
    title="DevOps Control Tower",
    description="Centralized command center for AI-powered development operations",
)


@app.get("/healthz")
def healthz() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "ok"}


@app.get("/version")
def version() -> dict[str, str]:
    """Return the version of the application."""
    return {"version": importlib.metadata.version("devops-control-tower")}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
