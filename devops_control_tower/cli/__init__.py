"""
Command Line Interface for DevOps Control Tower.
"""

import asyncio
import typer
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import print as rprint
from typing import Optional
import uvicorn

from ..core.orchestrator import Orchestrator
from ..integrations.jules_dev_kit import JulesDevKitAgent
from ..data.models.events import Event, EventTypes, EventPriority
from ..data.models.workflows import WorkflowTemplates


app = typer.Typer(help="DevOps Control Tower - AI-powered development operations")
console = Console()

# Global orchestrator instance
orchestrator: Optional[Orchestrator] = None


@app.command()
def start(
    port: int = typer.Option(8000, help="Port to run the API server on"),
    host: str = typer.Option("0.0.0.0", help="Host to bind the server to"),
    jules_url: Optional[str] = typer.Option(None, help="Jules Dev Kit URL"),
    jules_api_key: Optional[str] = typer.Option(None, help="Jules Dev Kit API key"),
    dev: bool = typer.Option(False, help="Run in development mode")
):
    """Start the DevOps Control Tower."""
    rprint(Panel.fit("🏗️ Starting DevOps Control Tower", style="bold blue"))
    
    async def startup():
        global orchestrator
        orchestrator = Orchestrator()
        
        # Register Jules Dev Kit agent if configured
        if jules_url:
            jules_agent = JulesDevKitAgent(jules_url, jules_api_key)
            orchestrator.register_agent("jules_dev_kit", jules_agent)
            console.print("✅ Registered Jules Dev Kit agent")
        
        # Register default workflows
        orchestrator.register_workflow("incident_response", WorkflowTemplates.incident_response())
        orchestrator.register_workflow("deployment_pipeline", WorkflowTemplates.deployment_pipeline())
        orchestrator.register_workflow("security_scan", WorkflowTemplates.security_scan())
        console.print("✅ Registered default workflows")
        
        # Start the orchestrator
        await orchestrator.start()
        console.print("✅ Orchestrator started")
        
        console.print(f"🚀 DevOps Control Tower is running on http://{host}:{port}")
    
    # Start the orchestrator
    asyncio.run(startup())
    
    # Note: In a real implementation, you'd start the FastAPI server here
    # For now, just keep the orchestrator running
    try:
        asyncio.get_event_loop().run_forever()
    except KeyboardInterrupt:
        console.print("\n🛑 Shutting down...")
        if orchestrator:
            asyncio.run(orchestrator.stop())


@app.command()
def status():
    """Show the status of the DevOps Control Tower."""
    if not orchestrator:
        console.print("❌ DevOps Control Tower is not running")
        return
    
    status_data = orchestrator.get_status()
    
    # Create status table
    table = Table(title="DevOps Control Tower Status", show_header=True, header_style="bold magenta")
    table.add_column("Component", style="cyan")
    table.add_column("Status", style="green")
    table.add_column("Details")
    
    # Orchestrator status
    table.add_row(
        "Orchestrator",
        "🟢 Running" if status_data["is_running"] else "🔴 Stopped",
        f"Tasks: {status_data['running_tasks']}, Queue: {status_data['queue_size']}"
    )
    
    # Agents status
    for agent_name, agent_status in status_data["agents"].items():
        status_emoji = {
            "running": "🟢",
            "stopped": "🔴",
            "error": "🟠",
            "starting": "🟡",
            "stopping": "🟡"
        }.get(agent_status["status"], "❓")
        
        uptime = ""
        if agent_status.get("uptime_seconds"):
            uptime = f"Uptime: {agent_status['uptime_seconds']:.0f}s"
        
        table.add_row(
            f"Agent: {agent_name}",
            f"{status_emoji} {agent_status['status'].title()}",
            uptime
        )
    
    # Workflows status
    for workflow_name, workflow_status in status_data["workflows"].items():
        status_emoji = {
            "idle": "🟢",
            "running": "🟡",
            "completed": "✅",
            "failed": "❌",
            "cancelled": "⏹️"
        }.get(workflow_status["status"], "❓")
        
        executions = f"Executions: {workflow_status['execution_count']}"
        
        table.add_row(
            f"Workflow: {workflow_name}",
            f"{status_emoji} {workflow_status['status'].title()}",
            executions
        )
    
    console.print(table)


@app.command()
def emit_event(
    event_type: str = typer.Argument(..., help="Type of event to emit"),
    source: str = typer.Argument(..., help="Source of the event"),
    priority: str = typer.Option("medium", help="Event priority (low/medium/high/critical)"),
    data: str = typer.Option("{}", help="JSON data for the event")
):
    """Emit a test event to the orchestrator."""
    if not orchestrator:
        console.print("❌ DevOps Control Tower is not running")
        return
    
    import json
    
    try:
        event_data = json.loads(data)
    except json.JSONDecodeError:
        console.print("❌ Invalid JSON data")
        return
    
    try:
        priority_enum = EventPriority(priority.lower())
    except ValueError:
        console.print("❌ Invalid priority. Use: low, medium, high, or critical")
        return
    
    # Create and emit the event
    event = Event(
        event_type=event_type,
        source=source,
        data=event_data,
        priority=priority_enum
    )
    
    async def emit():
        await orchestrator.emit_event(event)
    
    asyncio.run(emit())
    console.print(f"✅ Emitted event: {event}")


@app.command()
def list_workflows():
    """List all registered workflows."""
    if not orchestrator:
        console.print("❌ DevOps Control Tower is not running")
        return
    
    status_data = orchestrator.get_status()
    workflows = status_data["workflows"]
    
    if not workflows:
        console.print("No workflows registered")
        return
    
    table = Table(title="Registered Workflows", show_header=True, header_style="bold cyan")
    table.add_column("Name", style="yellow")
    table.add_column("Status", style="green")
    table.add_column("Executions", style="blue")
    table.add_column("Steps", style="magenta")
    table.add_column("Description")
    
    for name, workflow in workflows.items():
        status_emoji = {
            "idle": "🟢",
            "running": "🟡",
            "completed": "✅",
            "failed": "❌",
            "cancelled": "⏹️"
        }.get(workflow["status"], "❓")
        
        table.add_row(
            name,
            f"{status_emoji} {workflow['status'].title()}",
            str(workflow["execution_count"]),
            f"{workflow['current_step_index'] + 1}/{workflow['total_steps']}",
            workflow["description"][:50] + "..." if len(workflow["description"]) > 50 else workflow["description"]
        )
    
    console.print(table)


@app.command()
def execute_workflow(
    workflow_name: str = typer.Argument(..., help="Name of the workflow to execute"),
    context: str = typer.Option("{}", help="JSON context for the workflow")
):
    """Execute a workflow manually."""
    if not orchestrator:
        console.print("❌ DevOps Control Tower is not running")
        return
    
    import json
    
    try:
        workflow_context = json.loads(context)
    except json.JSONDecodeError:
        console.print("❌ Invalid JSON context")
        return
    
    async def execute():
        try:
            console.print(f"🚀 Executing workflow: {workflow_name}")
            result = await orchestrator.execute_workflow(workflow_name, workflow_context)
            console.print(f"✅ Workflow completed successfully")
            console.print(f"Result: {result}")
        except Exception as e:
            console.print(f"❌ Workflow failed: {e}")
    
    asyncio.run(execute())


@app.command()
def init_project(
    name: str = typer.Argument(..., help="Project name"),
    description: str = typer.Option("", help="Project description")
):
    """Initialize a new DevOps Control Tower project."""
    import os
    from pathlib import Path
    
    project_dir = Path(name)
    
    if project_dir.exists():
        console.print(f"❌ Directory {name} already exists")
        return
    
    # Create project structure
    directories = [
        "agents",
        "workflows", 
        "integrations",
        "config",
        "logs",
        "scripts"
    ]
    
    project_dir.mkdir()
    
    for directory in directories:
        (project_dir / directory).mkdir()
        (project_dir / directory / "__init__.py").touch()
    
    # Create basic configuration file
    config_content = f"""# DevOps Control Tower Configuration
# Project: {name}

[project]
name = "{name}"
description = "{description}"
version = "0.1.0"

[orchestrator]
log_level = "INFO"
max_concurrent_workflows = 10
event_queue_size = 1000

[integrations]
# jules_dev_kit_url = "http://localhost:8001"
# jules_dev_kit_api_key = "your-api-key"

[agents]
# Configure your AI agents here

[workflows]
# Configure your workflows here
"""
    
    (project_dir / "config" / "tower.toml").write_text(config_content)
    
    # Create basic docker-compose for development
    docker_compose = f"""version: '3.8'

services:
  control-tower:
    build: .
    ports:
      - "8000:8000"
    environment:
      - ENVIRONMENT=development
      - LOG_LEVEL=INFO
    volumes:
      - ./config:/app/config
      - ./logs:/app/logs
    depends_on:
      - redis
      - postgres

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"

  postgres:
    image: postgres:15-alpine
    environment:
      POSTGRES_DB: devops_control_tower
      POSTGRES_USER: devops
      POSTGRES_PASSWORD: devops
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data

volumes:
  postgres_data:
"""
    
    (project_dir / "docker-compose.yml").write_text(docker_compose)
    
    # Create README
    readme_content = f"""# {name}

{description}

## Getting Started

1. Install dependencies:
   ```bash
   pip install devops-control-tower
   ```

2. Start the services:
   ```bash
   docker-compose up -d
   ```

3. Run the control tower:
   ```bash
   devops-tower start
   ```

## Configuration

Edit `config/tower.toml` to configure your agents, workflows, and integrations.

## Custom Agents

Add your custom agents in the `agents/` directory.

## Custom Workflows

Define your workflows in the `workflows/` directory.
"""
    
    (project_dir / "README.md").write_text(readme_content)
    
    console.print(f"✅ Created DevOps Control Tower project: {name}")
    console.print(f"📁 Project directory: {project_dir.absolute()}")
    console.print("\nNext steps:")
    console.print(f"1. cd {name}")
    console.print("2. Edit config/tower.toml")
    console.print("3. docker-compose up -d")
    console.print("4. devops-tower start")


@app.command()
def version():
    """Show version information."""
    from .. import __version__
    rprint(Panel.fit(f"DevOps Control Tower v{__version__}", style="bold green"))


def main():
    """Main CLI entry point."""
    app()


if __name__ == "__main__":
    main()
