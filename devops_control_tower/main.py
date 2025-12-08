"""
Main entry point for DevOps Control Tower.
"""

from .api import app  # noqa: F401

if __name__ == "__main__":
    import uvicorn

    from .config import get_settings

    settings = get_settings()
    uvicorn.run(
        "devops_control_tower.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.debug,
        workers=1 if settings.debug else settings.api_workers,
    )
