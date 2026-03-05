"""
Generate a ChatGPT-compatible OpenAPI spec for the JCT task endpoints.

Filters the full app schema down to only the 3 task operations, sets the
configurable server URL, adds bearer auth, and enforces ChatGPT description
length limits.

Served as GET /openapi-gpt.json (registered in api.py).
"""

from __future__ import annotations

import copy
from typing import Any, Dict, Set

from fastapi import FastAPI

from .config import get_settings

# operationIds exposed to ChatGPT
_GPT_OPERATION_IDS: Set[str] = {"enqueueTask", "listTasks", "getTask"}

# ChatGPT character limits
_MAX_DESCRIPTION_LEN = 300
_MAX_PARAM_DESCRIPTION_LEN = 700


def build_gpt_openapi_spec(
    app: FastAPI, server_url_override: str | None = None
) -> Dict[str, Any]:
    """Build a filtered OpenAPI spec for ChatGPT Actions.

    Takes the full auto-generated spec from the FastAPI app, keeps only the
    task endpoints, injects the public server URL and bearer auth scheme.

    Args:
        app: The FastAPI application instance.
        server_url_override: If provided, overrides JCT_API_BASE_URL as the
            server URL in the spec. Useful via ``?server=https://...`` query param.
    """
    settings = get_settings()
    server_url = server_url_override or settings.jct_api_base_url

    # Deep copy so we don't mutate the cached spec
    full_spec = copy.deepcopy(app.openapi())

    gpt_spec: Dict[str, Any] = {
        "openapi": full_spec.get("openapi", "3.1.0"),
        "info": {
            "title": "DevOps Control Tower - Task API",
            "description": (
                "Submit and track development tasks. "
                "Used by ChatGPT to orchestrate AI-assisted dev ops."
            ),
            "version": full_spec["info"]["version"],
        },
        "servers": [{"url": server_url}],
        "paths": {},
        "components": {},
    }

    # Filter paths to only GPT-relevant operations
    for path, path_item in full_spec.get("paths", {}).items():
        filtered_methods: Dict[str, Any] = {}
        for method, operation in path_item.items():
            if not isinstance(operation, dict):
                continue
            if operation.get("operationId") not in _GPT_OPERATION_IDS:
                continue

            op = dict(operation)

            # Truncate operation description
            if "description" in op and len(op["description"]) > _MAX_DESCRIPTION_LEN:
                op["description"] = (
                    op["description"][: _MAX_DESCRIPTION_LEN - 3] + "..."
                )

            # Truncate parameter descriptions
            if "parameters" in op:
                for param in op["parameters"]:
                    desc = param.get("description", "")
                    if len(desc) > _MAX_PARAM_DESCRIPTION_LEN:
                        param["description"] = (
                            desc[: _MAX_PARAM_DESCRIPTION_LEN - 3] + "..."
                        )

            # Remove per-operation security (handled at spec level)
            op.pop("security", None)

            filtered_methods[method] = op

        if filtered_methods:
            gpt_spec["paths"][path] = filtered_methods

    # Copy referenced schemas so $ref pointers resolve
    if "components" in full_spec and "schemas" in full_spec["components"]:
        gpt_spec["components"]["schemas"] = full_spec["components"]["schemas"]

    # Add bearer auth security scheme
    gpt_spec["components"]["securitySchemes"] = {
        "BearerAuth": {
            "type": "http",
            "scheme": "bearer",
            "description": "API key as Bearer token",
        }
    }
    gpt_spec["security"] = [{"BearerAuth": []}]

    return gpt_spec
