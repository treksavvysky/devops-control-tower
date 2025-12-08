"""
DevOps Control Tower

A centralized command center for AI-powered development operations.
"""

import importlib.metadata

__author__ = "George Loudon"
__email__ = "george@example.com"
__version__ = importlib.metadata.version("devops-control-tower")

from .agents.base import BaseAgent
from .core.orchestrator import Orchestrator
from .data.models import (
    Event,
    EventPriority,
    EventStatus,
    EventTypes,
    Workflow,
    WorkflowBuilder,
    WorkflowStep,
    WorkflowTemplates,
)

__all__ = [
    "BaseAgent",
    "Event",
    "EventPriority",
    "EventStatus",
    "EventTypes",
    "Orchestrator",
    "Workflow",
    "WorkflowBuilder",
    "WorkflowStep",
    "WorkflowTemplates",
]
