"""
Action: workflow_manager
Reusable Workflow Builder and Runner for Echo AI.
Allows users to create, list, execute, and export multi-step workflows.
Auto-discovered by core/action_loader.py.
"""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional
from core.workflow_builder import WorkflowStore, Workflow
from actions.task_planner import _dispatch_action

_store = WorkflowStore()


def workflow_manager(
    parameters: dict = None,
    response=None,
    player=None,
    session_memory=None,
) -> str:
    params = parameters or {}
    action = params.get("action", "list").lower().strip()
    workflow_id = params.get("workflow_id", "").strip()
    name = params.get("name", "").strip()
    description = params.get("description", "").strip()
    steps_raw = params.get("steps")
    wf_params = params.get("parameters", {})
    task_id = params.get("task_id", "").strip()

    logger = (lambda msg: player.write_log(f"[Workflow] {msg}")) if player else None

    # 1. List workflows
    if action in ("list", "list_workflows"):
        items = _store.list_all()
        if not items:
            return "No reusable workflows found yet. You can create one or export from a task!"
        lines = [f"• '{w['name']}' (ID: {w['id']}) - {w['description']} [{w['steps_count']} steps, trigger: {w['trigger']}]" for w in items]
        return "Reusable Workflows:\n" + "\n".join(lines)

    # 2. Run workflow
    elif action in ("run", "execute", "start"):
        if not workflow_id:
            return "Please provide workflow_id or name to run."

        def run_tool(t_name: str, t_params: dict) -> Any:
            return _dispatch_action(t_name, t_params, player=player)

        plan = _store.execute_workflow(
            workflow_id=workflow_id,
            param_overrides=wf_params if isinstance(wf_params, dict) else {},
            executor_fn=run_tool,
            logger=logger,
        )
        if not plan:
            return f"Workflow '{workflow_id}' not found."

        completed_c = sum(1 for s in plan.steps if s.status == "COMPLETED")
        return f"Workflow '{workflow_id}' executed with status {plan.status} ({completed_c}/{len(plan.steps)} steps)."

    # 3. Create workflow
    elif action in ("create", "save", "add"):
        if not workflow_id and not name:
            return "Please specify a workflow_id or name."
        clean_id = workflow_id or name.lower().replace(" ", "_")

        steps = []
        if isinstance(steps_raw, list):
            steps = steps_raw
        elif isinstance(steps_raw, str) and steps_raw.strip():
            try:
                steps = json.loads(steps_raw)
            except Exception:
                steps = []

        if not steps:
            return "Please specify steps for the workflow."

        wf = Workflow(
            id=clean_id,
            name=name or clean_id.title(),
            description=description or f"Workflow {clean_id}",
            parameters=wf_params if isinstance(wf_params, dict) else {},
            steps=steps,
        )
        _store.save(wf)
        return f"Workflow '{wf.name}' (ID: {wf.id}) saved with {len(wf.steps)} steps."

    # 4. Export from completed task checkpoint
    elif action in ("export_task", "convert_task"):
        if not task_id:
            return "Please specify the task_id to export."
        clean_id = workflow_id or f"wf_{task_id}"
        wf = _store.export_from_task(
            task_id=task_id,
            workflow_id=clean_id,
            name=name,
            description=description,
            parameters=wf_params if isinstance(wf_params, dict) else {},
        )
        if not wf:
            return f"Task '{task_id}' not found in checkpoints."
        return f"Exported task '{task_id}' into reusable workflow '{wf.name}' (ID: {wf.id})."

    # 5. Delete workflow
    elif action in ("delete", "remove"):
        if not workflow_id:
            return "Please specify workflow_id to delete."
        ok = _store.delete(workflow_id)
        return f"Workflow '{workflow_id}' {'deleted' if ok else 'not found'}."

    return f"Unknown workflow action '{action}'. Available: list, run, create, export_task, delete."


# ── Tool declaration (auto-discovered by core/action_loader.py) ──────────────
TOOL = {
    "name": "workflow_manager",
    "description": (
        "Build, save, list, and run reusable multi-step task workflows. "
        "Allows converting successful autonomous tasks into reusable routines, "
        "substituting parameters, and running saved workflows."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "description": "Action: 'run' | 'list' | 'create' | 'export_task' | 'delete'",
            },
            "workflow_id": {
                "type": "STRING",
                "description": "Unique identifier or name of the workflow.",
            },
            "name": {
                "type": "STRING",
                "description": "Human-readable workflow name.",
            },
            "description": {
                "type": "STRING",
                "description": "Description of the workflow.",
            },
            "parameters": {
                "type": "OBJECT",
                "description": "Parameter values or declarations for the workflow.",
            },
            "steps": {
                "type": "ARRAY",
                "description": "List of step objects to execute.",
                "items": {"type": "OBJECT"},
            },
            "task_id": {
                "type": "STRING",
                "description": "Task ID when exporting an existing task to a workflow.",
            },
        },
        "required": ["action"],
    },
    "handler": workflow_manager,
}
