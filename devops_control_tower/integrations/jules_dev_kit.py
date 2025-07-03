"""
Integration with Jules Dev Kit.

This module provides seamless integration between the DevOps Control Tower
and the Jules Dev Kit, enabling advanced AI-powered development workflows.
"""

import httpx
import asyncio
from typing import Dict, Any, List, Optional
import logging

from ..data.models.events import Event, EventTypes, EventPriority
from ..agents.base import AIAgent


logger = logging.getLogger(__name__)


class JulesDevKitIntegration:
    """
    Integration client for communicating with Jules Dev Kit.
    """
    
    def __init__(self, base_url: str, api_key: Optional[str] = None):
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self.client = httpx.AsyncClient(
            timeout=30.0,
            headers={"Authorization": f"Bearer {api_key}"} if api_key else {}
        )
    
    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()
    
    async def get_issues(self, repo: Optional[str] = None, status: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get issues from Jules Dev Kit."""
        params = {}
        if repo:
            params["repo"] = repo
        if status:
            params["status"] = status
        
        try:
            response = await self.client.get(f"{self.base_url}/api/issues/", params=params)
            response.raise_for_status()
            return response.json()
        except httpx.RequestError as e:
            logger.error(f"Failed to get issues from Jules Dev Kit: {e}")
            raise
    
    async def create_issue(
        self,
        title: str,
        description: str,
        repo: str,
        priority: str = "medium",
        labels: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Create a new issue in Jules Dev Kit."""
        data = {
            "title": title,
            "description": description,
            "repo": repo,
            "priority": priority,
            "labels": labels or [],
            "auto_classify": True
        }
        
        try:
            response = await self.client.post(f"{self.base_url}/api/issues/", json=data)
            response.raise_for_status()
            return response.json()
        except httpx.RequestError as e:
            logger.error(f"Failed to create issue in Jules Dev Kit: {e}")
            raise
    
    async def generate_code(
        self,
        issue_id: int,
        language: str = "python",
        framework: Optional[str] = None
    ) -> Dict[str, Any]:
        """Generate code solution for an issue."""
        data = {
            "issue_id": issue_id,
            "language": language,
            "framework": framework
        }
        
        try:
            response = await self.client.post(f"{self.base_url}/api/code/generate/", json=data)
            response.raise_for_status()
            return response.json()
        except httpx.RequestError as e:
            logger.error(f"Failed to generate code: {e}")
            raise
    
    async def get_analytics(self, repo: Optional[str] = None) -> Dict[str, Any]:
        """Get development analytics from Jules Dev Kit."""
        params = {"repo": repo} if repo else {}
        
        try:
            response = await self.client.get(f"{self.base_url}/api/analytics/", params=params)
            response.raise_for_status()
            return response.json()
        except httpx.RequestError as e:
            logger.error(f"Failed to get analytics: {e}")
            raise
    
    async def trigger_workflow(self, workflow_name: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Trigger a workflow in Jules Dev Kit."""
        data = {
            "workflow": workflow_name,
            "context": context
        }
        
        try:
            response = await self.client.post(f"{self.base_url}/api/workflows/trigger/", json=data)
            response.raise_for_status()
            return response.json()
        except httpx.RequestError as e:
            logger.error(f"Failed to trigger workflow: {e}")
            raise


class JulesDevKitAgent(AIAgent):
    """
    AI agent that integrates with Jules Dev Kit for development operations.
    """
    
    def __init__(self, jules_base_url: str, jules_api_key: Optional[str] = None):
        super().__init__(
            name="jules_dev_kit_agent",
            description="AI agent for Jules Dev Kit integration and development automation"
        )
        self.jules = JulesDevKitIntegration(jules_base_url, jules_api_key)
        
        # Register event types this agent handles
        self.register_event_type(EventTypes.CODE_COMMIT)
        self.register_event_type(EventTypes.BUILD_FAILED)
        self.register_event_type(EventTypes.DEPLOYMENT_FAILED)
        self.register_event_type(EventTypes.SECURITY_VULNERABILITY)
        self.register_event_type(EventTypes.INFRASTRUCTURE_ALERT)
    
    async def _setup_llm_client(self) -> None:
        """Setup LLM client for the agent."""
        # Use the same LLM as Jules Dev Kit or configure separately
        pass
    
    async def _cleanup(self) -> None:
        """Cleanup resources."""
        await self.jules.close()
    
    async def handle_event(self, event: Event) -> None:
        """Handle events by creating appropriate issues or triggering workflows."""
        try:
            if event.type == EventTypes.CODE_COMMIT:
                await self._handle_code_commit(event)
            elif event.type == EventTypes.BUILD_FAILED:
                await self._handle_build_failure(event)
            elif event.type == EventTypes.DEPLOYMENT_FAILED:
                await self._handle_deployment_failure(event)
            elif event.type == EventTypes.SECURITY_VULNERABILITY:
                await self._handle_security_vulnerability(event)
            elif event.type == EventTypes.INFRASTRUCTURE_ALERT:
                await self._handle_infrastructure_alert(event)
        except Exception as e:
            logger.error(f"Failed to handle event {event.id}: {e}")
    
    async def _handle_code_commit(self, event: Event) -> None:
        """Handle code commit events."""
        commit_data = event.data
        repo = commit_data.get("repository")
        
        if not repo:
            return
        
        # Trigger code analysis workflow in Jules Dev Kit
        await self.jules.trigger_workflow("code_analysis", {
            "repository": repo,
            "commit_sha": commit_data.get("sha"),
            "files_changed": commit_data.get("files", [])
        })
        
        logger.info(f"Triggered code analysis for commit in {repo}")
    
    async def _handle_build_failure(self, event: Event) -> None:
        """Handle build failure events by creating issues."""
        build_data = event.data
        repo = build_data.get("repository")
        
        if not repo:
            return
        
        # Create an issue for the build failure
        issue = await self.jules.create_issue(
            title=f"Build Failed: {build_data.get('job_name', 'Unknown Job')}",
            description=f"""
Build failure detected:

**Repository:** {repo}
**Branch:** {build_data.get('branch', 'unknown')}
**Job:** {build_data.get('job_name', 'unknown')}
**Error:** {build_data.get('error', 'No error details available')}

**Logs:** {build_data.get('logs', 'No logs available')}

This issue was automatically created by the DevOps Control Tower.
            """.strip(),
            repo=repo,
            priority="high",
            labels=["bug", "build-failure", "automated"]
        )
        
        logger.info(f"Created issue #{issue.get('id')} for build failure in {repo}")
    
    async def _handle_deployment_failure(self, event: Event) -> None:
        """Handle deployment failure events."""
        deploy_data = event.data
        repo = deploy_data.get("repository")
        environment = deploy_data.get("environment", "unknown")
        
        if not repo:
            return
        
        # Create a critical issue for deployment failure
        issue = await self.jules.create_issue(
            title=f"Deployment Failed: {environment}",
            description=f"""
Deployment failure detected:

**Repository:** {repo}
**Environment:** {environment}
**Version:** {deploy_data.get('version', 'unknown')}
**Error:** {deploy_data.get('error', 'No error details available')}

**Previous Version:** {deploy_data.get('previous_version', 'unknown')}
**Rollback Required:** {deploy_data.get('rollback_required', False)}

This is a critical issue that requires immediate attention.
            """.strip(),
            repo=repo,
            priority="critical",
            labels=["critical", "deployment-failure", "automated"]
        )
        
        logger.info(f"Created critical issue #{issue.get('id')} for deployment failure in {repo}")
    
    async def _handle_security_vulnerability(self, event: Event) -> None:
        """Handle security vulnerability events."""
        vuln_data = event.data
        repo = vuln_data.get("repository")
        
        if not repo:
            return
        
        severity = vuln_data.get("severity", "medium")
        priority = "critical" if severity in ["critical", "high"] else "high"
        
        # Create a security issue
        issue = await self.jules.create_issue(
            title=f"Security Vulnerability: {vuln_data.get('title', 'Unknown Vulnerability')}",
            description=f"""
Security vulnerability detected:

**Repository:** {repo}
**Severity:** {severity.upper()}
**CVE:** {vuln_data.get('cve', 'N/A')}
**Package:** {vuln_data.get('package', 'unknown')}
**Version:** {vuln_data.get('version', 'unknown')}

**Description:** {vuln_data.get('description', 'No description available')}

**Fix Available:** {vuln_data.get('fix_available', False)}
**Fixed Version:** {vuln_data.get('fixed_version', 'N/A')}

This security issue requires immediate attention.
            """.strip(),
            repo=repo,
            priority=priority,
            labels=["security", "vulnerability", severity, "automated"]
        )
        
        logger.info(f"Created security issue #{issue.get('id')} for {repo}")
    
    async def _handle_infrastructure_alert(self, event: Event) -> None:
        """Handle infrastructure alerts by potentially creating issues."""
        alert_data = event.data
        severity = alert_data.get("severity", "medium")
        
        # Only create issues for high/critical infrastructure alerts
        if severity not in ["high", "critical"]:
            return
        
        # Try to map the alert to a specific repository
        service = alert_data.get("service")
        repo = alert_data.get("repository") or self._map_service_to_repo(service)
        
        if not repo:
            return
        
        # Create an infrastructure issue
        issue = await self.jules.create_issue(
            title=f"Infrastructure Alert: {alert_data.get('alert_name', 'Unknown Alert')}",
            description=f"""
Infrastructure alert triggered:

**Service:** {service}
**Severity:** {severity.upper()}
**Alert:** {alert_data.get('alert_name', 'unknown')}
**Message:** {alert_data.get('message', 'No message available')}

**Metrics:**
{self._format_metrics(alert_data.get('metrics', {}))}

**Runbook:** {alert_data.get('runbook', 'No runbook available')}

This infrastructure issue may require code or configuration changes.
            """.strip(),
            repo=repo,
            priority=severity,
            labels=["infrastructure", "alert", severity, "automated"]
        )
        
        logger.info(f"Created infrastructure issue #{issue.get('id')} for {service}")
    
    def _map_service_to_repo(self, service: Optional[str]) -> Optional[str]:
        """Map a service name to a repository name."""
        if not service:
            return None
        
        # This would typically involve a configuration mapping
        # For now, just return the service name as repo name
        return service
    
    def _format_metrics(self, metrics: Dict[str, Any]) -> str:
        """Format metrics for display in issue description."""
        if not metrics:
            return "No metrics available"
        
        formatted = []
        for key, value in metrics.items():
            formatted.append(f"- {key}: {value}")
        
        return "\n".join(formatted)
    
    async def _call_llm(self, prompt: str) -> str:
        """Make a call to the LLM for intelligent responses."""
        # This would integrate with your chosen LLM provider
        # For now, return a placeholder response
        return f"AI response to: {prompt[:50]}..."
    
    async def get_development_insights(self, repo: str) -> Dict[str, Any]:
        """Get development insights for a repository."""
        try:
            analytics = await self.jules.get_analytics(repo)
            issues = await self.jules.get_issues(repo)
            
            # Use AI to analyze the data and provide insights
            insight_prompt = f"""
Analyze the following development data for repository {repo}:

Analytics: {analytics}
Recent Issues: {issues[:5]}  # Last 5 issues

Provide insights on:
1. Development velocity trends
2. Common issue patterns
3. Areas for improvement
4. Recommended actions

Format as JSON with clear sections.
            """
            
            ai_insights = await self.think(insight_prompt)
            
            return {
                "repository": repo,
                "analytics": analytics,
                "ai_insights": ai_insights,
                "timestamp": datetime.utcnow().isoformat()
            }
        except Exception as e:
            logger.error(f"Failed to get development insights for {repo}: {e}")
            raise
