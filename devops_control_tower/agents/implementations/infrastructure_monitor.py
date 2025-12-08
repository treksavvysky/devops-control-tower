"""
Infrastructure Monitoring Agent - First concrete AI agent implementation.
"""

import asyncio
import logging
import random
from datetime import datetime, timedelta
from typing import Any, Dict, List

from ...config import get_settings
from ...data.models.events import Event, EventPriority, EventTypes
from ..base import AgentStatus, AIAgent

logger = logging.getLogger(__name__)


class InfrastructureMonitoringAgent(AIAgent):
    """
    AI agent for infrastructure monitoring and alerting.

    This agent:
    - Monitors system resources (CPU, memory, disk, network)
    - Detects anomalies and performance issues
    - Generates intelligent alerts with context
    - Provides optimization recommendations
    """

    _monitoring_task: asyncio.Task[None]
    _health_status: str

    def __init__(self, name: str = "infrastructure-monitor") -> None:
        super().__init__(
            name=name,
            description="AI-powered infrastructure monitoring and alerting agent",
            capabilities=[
                "system_monitoring",
                "anomaly_detection",
                "performance_analysis",
                "alert_generation",
                "optimization_recommendations",
            ],
        )

        self.settings = get_settings()
        self.monitoring_interval = 60  # seconds
        self.thresholds: Dict[str, float] = {
            "cpu_percent": 80.0,
            "memory_percent": 85.0,
            "disk_percent": 90.0,
        }
        self.baseline_metrics: Dict[str, Any] = {}
        self.alert_cooldown: Dict[str, datetime] = {}
        self._health_status = "unknown"

    async def _setup_llm_client(self) -> None:
        """Setup the LLM client - not used for this agent."""
        # This agent doesn't require an LLM client for v0
        pass

    async def _call_llm(self, prompt: str) -> str:
        """Make a call to the LLM - not used for this agent."""
        # This agent doesn't require LLM calls for v0
        return ""

    async def start(self) -> None:
        """Start the infrastructure monitoring agent."""
        await super().start()

        # Initialize baseline metrics
        await self._collect_baseline_metrics()

        # Start monitoring loop
        self._monitoring_task = asyncio.create_task(self._monitoring_loop())

        logger.info(f"Infrastructure Monitoring Agent '{self.name}' started")

    async def stop(self) -> None:
        """Stop the infrastructure monitoring agent."""
        if hasattr(self, "_monitoring_task"):
            self._monitoring_task.cancel()

        await super().stop()
        logger.info(f"Infrastructure Monitoring Agent '{self.name}' stopped")

    async def _monitoring_loop(self) -> None:
        """Main monitoring loop."""
        while self.status == AgentStatus.RUNNING:
            try:
                # Collect current metrics
                metrics = await self._collect_system_metrics()

                # Analyze metrics for issues
                alerts = await self._analyze_metrics(metrics)

                # Generate events for any alerts
                for alert in alerts:
                    await self._generate_alert_event(alert, metrics)

                # Update health status
                await self._update_health_status(alerts)

                # Wait for next cycle
                await asyncio.sleep(self.monitoring_interval)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                await asyncio.sleep(10)

    async def _collect_baseline_metrics(self) -> None:
        """Collect baseline system metrics for comparison."""
        try:
            # Collect multiple samples for baseline
            samples: List[Dict[str, Any]] = []
            for _ in range(5):
                metrics = await self._collect_system_metrics()
                samples.append(metrics)
                await asyncio.sleep(1)

            # Calculate baseline averages
            self.baseline_metrics = {
                "cpu_percent": sum(s["cpu_percent"] for s in samples) / len(samples),
                "memory_percent": sum(s["memory_percent"] for s in samples)
                / len(samples),
                "disk_percent": sum(s["disk_percent"] for s in samples) / len(samples),
            }

            logger.info(f"Baseline metrics established: {self.baseline_metrics}")

        except Exception as e:
            logger.error(f"Failed to collect baseline metrics: {e}")
            # Set reasonable defaults
            self.baseline_metrics = {
                "cpu_percent": 10.0,
                "memory_percent": 30.0,
                "disk_percent": 50.0,
            }

    async def _collect_system_metrics(self) -> Dict[str, Any]:
        """Collect current system metrics."""
        # For now, simulate metrics since psutil might not be available
        # In production, this would use psutil or cloud APIs

        # Simulate realistic system metrics with some variance
        base_cpu = float(self.baseline_metrics.get("cpu_percent", 15.0))
        base_memory = float(self.baseline_metrics.get("memory_percent", 40.0))
        base_disk = float(self.baseline_metrics.get("disk_percent", 60.0))

        # Add variance to simulate real system behavior
        variance = random.uniform(-5, 15)

        metrics: Dict[str, Any] = {
            "timestamp": datetime.utcnow().isoformat(),
            "cpu_percent": max(0, min(100, base_cpu + variance)),
            "memory_percent": max(0, min(100, base_memory + variance * 0.5)),
            "disk_percent": max(0, min(100, base_disk + variance * 0.2)),
            "load_average": random.uniform(0.5, 3.0),
            "network_io": {
                "bytes_sent": random.randint(1000000, 5000000),
                "bytes_recv": random.randint(2000000, 8000000),
            },
            "process_count": random.randint(150, 300),
        }

        return metrics

    async def _analyze_metrics(self, metrics: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Analyze metrics and identify issues."""
        alerts: List[Dict[str, Any]] = []

        # CPU threshold check
        if metrics["cpu_percent"] > self.thresholds["cpu_percent"]:
            if self._should_alert("high_cpu"):
                alerts.append(
                    {
                        "type": "high_cpu",
                        "severity": "warning"
                        if metrics["cpu_percent"] < 95
                        else "critical",
                        "value": metrics["cpu_percent"],
                        "threshold": self.thresholds["cpu_percent"],
                        "message": f"CPU usage at {metrics['cpu_percent']:.1f}%",
                    }
                )

        # Memory threshold check
        if metrics["memory_percent"] > self.thresholds["memory_percent"]:
            if self._should_alert("high_memory"):
                alerts.append(
                    {
                        "type": "high_memory",
                        "severity": "warning"
                        if metrics["memory_percent"] < 95
                        else "critical",
                        "value": metrics["memory_percent"],
                        "threshold": self.thresholds["memory_percent"],
                        "message": f"Memory usage at {metrics['memory_percent']:.1f}%",
                    }
                )

        # Disk threshold check
        if metrics["disk_percent"] > self.thresholds["disk_percent"]:
            if self._should_alert("high_disk"):
                alerts.append(
                    {
                        "type": "high_disk",
                        "severity": "critical",  # Disk space is always critical
                        "value": metrics["disk_percent"],
                        "threshold": self.thresholds["disk_percent"],
                        "message": f"Disk usage at {metrics['disk_percent']:.1f}%",
                    }
                )

        return alerts

    def _should_alert(self, alert_type: str) -> bool:
        """Check if we should generate an alert (cooldown logic)."""
        cooldown_minutes = 15  # Don't repeat alerts within 15 minutes

        if alert_type not in self.alert_cooldown:
            self.alert_cooldown[alert_type] = datetime.utcnow()
            return True

        time_since_last = datetime.utcnow() - self.alert_cooldown[alert_type]
        if time_since_last > timedelta(minutes=cooldown_minutes):
            self.alert_cooldown[alert_type] = datetime.utcnow()
            return True

        return False

    async def _generate_alert_event(
        self, alert: Dict[str, Any], metrics: Dict[str, Any]
    ) -> None:
        """Generate an infrastructure alert event."""
        try:
            # Determine event priority based on severity
            priority_map: Dict[str, EventPriority] = {
                "info": EventPriority.LOW,
                "warning": EventPriority.MEDIUM,
                "critical": EventPriority.HIGH,
            }

            event = Event(
                event_type=EventTypes.INFRASTRUCTURE_ALERT,
                source=self.name,
                data={
                    "alert": alert,
                    "current_metrics": metrics,
                    "baseline_metrics": self.baseline_metrics,
                    "agent_recommendations": await self._generate_recommendations(
                        alert, metrics
                    ),
                },
                priority=priority_map.get(alert["severity"], EventPriority.MEDIUM),
                tags={
                    "agent": self.name,
                    "alert_type": alert["type"],
                    "severity": alert["severity"],
                },
            )

            # Submit event (would be connected to orchestrator in real implementation)
            logger.info(f"Generated infrastructure alert: {alert['message']}")
            # Suppress unused variable warning - event would be submitted in production
            _ = event

        except Exception as e:
            logger.error(f"Failed to generate alert event: {e}")

    async def _generate_recommendations(
        self, alert: Dict[str, Any], metrics: Dict[str, Any]
    ) -> List[str]:
        """Generate AI-powered recommendations for the alert."""
        # Suppress unused parameter warning
        _ = metrics

        recommendations: List[str] = []

        if alert["type"] == "high_cpu":
            recommendations.extend(
                [
                    "Consider scaling horizontally by adding more instances",
                    "Review CPU-intensive processes and optimize code",
                    "Check for background tasks that can be scheduled off-peak",
                ]
            )
        elif alert["type"] == "high_memory":
            recommendations.extend(
                [
                    "Review memory usage patterns and optimize allocation",
                    "Consider increasing instance memory or adding swap space",
                    "Check for memory leaks in applications",
                ]
            )
        elif alert["type"] == "high_disk":
            recommendations.extend(
                [
                    "Clean up old log files and temporary data",
                    "Archive or compress infrequently accessed files",
                    "Consider adding additional storage volumes",
                ]
            )

        return recommendations

    async def _update_health_status(self, alerts: List[Dict[str, Any]]) -> None:
        """Update agent health status based on current alerts."""
        if not alerts:
            self._health_status = "healthy"
        elif any(alert["severity"] == "critical" for alert in alerts):
            self._health_status = "critical"
        else:
            self._health_status = "warning"

    async def handle_event(self, event: Event) -> Dict[str, Any]:
        """Handle incoming events."""
        try:
            if event.type == EventTypes.USER_REQUEST:
                request_type = event.data.get("request_type", "")

                if request_type == "current_metrics":
                    metrics = await self._collect_system_metrics()
                    return {
                        "success": True,
                        "data": {
                            "current_metrics": metrics,
                            "baseline_metrics": self.baseline_metrics,
                            "thresholds": self.thresholds,
                        },
                    }

            return {"success": False, "error": "Unsupported event type"}

        except Exception as e:
            logger.error(f"Error handling event: {e}")
            return {"success": False, "error": str(e)}
