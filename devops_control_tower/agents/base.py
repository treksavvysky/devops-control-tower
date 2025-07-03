"""
Base agent class for all AI agents in the DevOps Control Tower.
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any, Set
import asyncio
import logging
from datetime import datetime
from enum import Enum

from ..data.models.events import Event


logger = logging.getLogger(__name__)


class AgentStatus(Enum):
    """Agent status enumeration."""
    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    ERROR = "error"


class BaseAgent(ABC):
    """
    Abstract base class for all AI agents in the platform.
    
    Each agent is responsible for a specific domain of operations
    (e.g., infrastructure, security, monitoring, deployment).
    """
    
    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description
        self.status = AgentStatus.STOPPED
        self.started_at: Optional[datetime] = None
        self.error_count = 0
        self.last_error: Optional[str] = None
        self.handled_event_types: Set[str] = set()
        
    async def start(self) -> None:
        """Start the agent."""
        logger.info(f"Starting agent: {self.name}")
        self.status = AgentStatus.STARTING
        
        try:
            await self._initialize()
            self.status = AgentStatus.RUNNING
            self.started_at = datetime.utcnow()
            logger.info(f"Agent started successfully: {self.name}")
        except Exception as e:
            self.status = AgentStatus.ERROR
            self.last_error = str(e)
            self.error_count += 1
            logger.error(f"Failed to start agent {self.name}: {e}")
            raise
    
    async def stop(self) -> None:
        """Stop the agent."""
        logger.info(f"Stopping agent: {self.name}")
        self.status = AgentStatus.STOPPING
        
        try:
            await self._cleanup()
            self.status = AgentStatus.STOPPED
            self.started_at = None
            logger.info(f"Agent stopped successfully: {self.name}")
        except Exception as e:
            self.status = AgentStatus.ERROR
            self.last_error = str(e)
            self.error_count += 1
            logger.error(f"Failed to stop agent {self.name}: {e}")
            raise
    
    @abstractmethod
    async def _initialize(self) -> None:
        """Initialize the agent. Override in subclasses."""
        pass
    
    @abstractmethod
    async def _cleanup(self) -> None:
        """Cleanup agent resources. Override in subclasses."""
        pass
    
    @abstractmethod
    async def handle_event(self, event: Event) -> None:
        """Handle an event. Override in subclasses."""
        pass
    
    def handles_event_type(self, event_type: str) -> bool:
        """Check if this agent handles a specific event type."""
        return event_type in self.handled_event_types
    
    def register_event_type(self, event_type: str) -> None:
        """Register an event type that this agent can handle."""
        self.handled_event_types.add(event_type)
        logger.debug(f"Agent {self.name} registered for event type: {event_type}")
    
    def get_status(self) -> Dict[str, Any]:
        """Get the current status of the agent."""
        uptime = None
        if self.started_at:
            uptime = (datetime.utcnow() - self.started_at).total_seconds()
        
        return {
            "name": self.name,
            "description": self.description,
            "status": self.status.value,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "uptime_seconds": uptime,
            "error_count": self.error_count,
            "last_error": self.last_error,
            "handled_event_types": list(self.handled_event_types)
        }


class AIAgent(BaseAgent):
    """
    Enhanced base class for AI-powered agents with LLM integration.
    """
    
    def __init__(self, name: str, description: str, llm_provider: str = "openai"):
        super().__init__(name, description)
        self.llm_provider = llm_provider
        self.llm_client = None
        self.context_window = []
        self.max_context_length = 10
        
    async def _initialize(self) -> None:
        """Initialize the AI agent with LLM client."""
        await self._setup_llm_client()
        await self._load_agent_context()
    
    async def _cleanup(self) -> None:
        """Cleanup AI agent resources."""
        if self.llm_client:
            await self._close_llm_client()
    
    @abstractmethod
    async def _setup_llm_client(self) -> None:
        """Setup the LLM client. Override in subclasses."""
        pass
    
    async def _close_llm_client(self) -> None:
        """Close the LLM client connection."""
        # Override if needed
        pass
    
    async def _load_agent_context(self) -> None:
        """Load agent-specific context and knowledge."""
        # Override in subclasses to load specific context
        pass
    
    async def think(self, prompt: str, context: Optional[Dict[str, Any]] = None) -> str:
        """
        Use the LLM to think through a problem and generate a response.
        """
        if not self.llm_client:
            raise RuntimeError(f"LLM client not initialized for agent {self.name}")
        
        # Add context to the prompt
        enhanced_prompt = self._build_enhanced_prompt(prompt, context)
        
        try:
            response = await self._call_llm(enhanced_prompt)
            
            # Update context window
            self._update_context_window(prompt, response)
            
            return response
        except Exception as e:
            logger.error(f"LLM call failed for agent {self.name}: {e}")
            raise
    
    def _build_enhanced_prompt(self, prompt: str, context: Optional[Dict[str, Any]] = None) -> str:
        """Build an enhanced prompt with agent context and additional context."""
        enhanced_prompt = f"""
You are {self.name}, an AI agent specialized in {self.description}.

Recent context:
{self._format_context_window()}

Current situation:
{self._format_additional_context(context)}

Task: {prompt}

Please provide a thoughtful response based on your expertise and the context provided.
"""
        return enhanced_prompt
    
    def _format_context_window(self) -> str:
        """Format the recent context window for the prompt."""
        if not self.context_window:
            return "No recent context available."
        
        formatted = []
        for i, (prompt, response) in enumerate(self.context_window[-3:]):  # Last 3 interactions
            formatted.append(f"Context {i+1}:")
            formatted.append(f"  Query: {prompt[:100]}{'...' if len(prompt) > 100 else ''}")
            formatted.append(f"  Response: {response[:100]}{'...' if len(response) > 100 else ''}")
        
        return "\n".join(formatted)
    
    def _format_additional_context(self, context: Optional[Dict[str, Any]]) -> str:
        """Format additional context for the prompt."""
        if not context:
            return "No additional context provided."
        
        formatted = []
        for key, value in context.items():
            formatted.append(f"- {key}: {value}")
        
        return "\n".join(formatted)
    
    def _update_context_window(self, prompt: str, response: str) -> None:
        """Update the context window with the latest interaction."""
        self.context_window.append((prompt, response))
        
        # Keep only the most recent interactions
        if len(self.context_window) > self.max_context_length:
            self.context_window = self.context_window[-self.max_context_length:]
    
    @abstractmethod
    async def _call_llm(self, prompt: str) -> str:
        """Make a call to the LLM. Override in subclasses."""
        pass
