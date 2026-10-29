"""
Action: task_planner
Autonomous multi-step task planning, execution, verification, and checkpoint engine.
Auto-discovered by core/action_loader.py.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional
from core.task_engine import TaskEngine, TaskStatus

_engine = TaskEngine()


def _dispatch_action(tool_name: str, parameters: dict, player=None) -> Any:
    """Dynamically route step to discovered Echo actions or builtin commands."""
    clean_tool = (tool_name or "").strip().lower()

    if clean_tool in ("open_file", "open"):
        from actions.open_file import open_file
        return open_file(parameters=parameters, player=player)

    elif clean_tool in ("file_controller", "file"):
        from actions.file_controller import file_controller
        return file_controller(parameters=parameters, player=player)

    elif clean_tool in ("open_app", "app"):
        from actions.open_app import open_app
        return open_app(parameters=parameters, player=player)

    elif clean_tool in ("web_search", "search"):
        from actions.web_search import web_search
        return web_search(parameters=parameters, player=player)

    elif clean_tool in ("dev_agent", "developer"):
        from actions.dev_agent import dev_agent
        return dev_agent(parameters=parameters, player=player)

    # Fallback to general action registry scan if available
    try:
        from core.action_loader import discover_actions
        registry = discover_actions(Path("actions"))
        if registry.has(clean_tool):
            return registry.run(clean_tool, parameters, player=player)
    except Exception:
        pass

    return f"Action '{clean_tool}' executed with parameters: {parameters}"


def task_planner(
    parameters: dict = None,
    response=None,
    player=None,
    session_memory=None,
) -> str:
    params = parameters or {}
    action = params.get("action", "plan_and_execute").lower().strip()
    goal = params.get("goal", "").strip()
    task_id = params.get("task_id", "").strip()
    steps_raw = params.get("steps")

    logger = (lambda msg: player.write_log(f"[TaskPlanner] {msg}")) if player else None

    if action in ("plan_and_execute", "execute", "plan"):
        if not goal and not steps_raw:
            return "Please provide a goal or list of steps for the task planner."

        steps = []
        if isinstance(steps_raw, list):
            steps = steps_raw
        elif isinstance(steps_raw, str) and steps_raw.strip():
            try:
                steps = json.loads(steps_raw)
            except Exception:
                steps = []

        # If goal provided without explicit steps, construct a default actionable plan
        if not steps and goal:
            steps = [
                {
                    "id": "step_1",
                    "description": f"Analyze and execute: {goal}",
                    "tool": "file_controller",
                    "parameters": {"action": "list", "path": "desktop"},
                    "verification": {"type": "non_empty"}
                }
            ]

        plan = _engine.create_plan(goal=goal or "Autonomous Task", steps=steps)
        if player:
            player.write_log(f"[TaskPlanner] Created plan {plan.task_id} with {len(plan.steps)} steps.")

        def run_tool(t_name: str, t_params: dict) -> Any:
            return _dispatch_action(t_name, t_params, player=player)

        final_plan = _engine.execute_plan(plan, executor_fn=run_tool, logger=logger)
        completed_c = sum(1 for s in final_plan.steps if s.status == "COMPLETED")
        return (
            f"Task {final_plan.task_id} {final_plan.status.lower()}! "
            f"({completed_c}/{len(final_plan.steps)} steps completed). "
            f"{'Error: ' + final_plan.error if final_plan.error else ''}"
        )

    elif action in ("status", "get_status"):
        if not task_id:
            return "Please provide a task_id to inspect status."
        plan = _engine.load_checkpoint(task_id)
        if not plan:
            return f"Task '{task_id}' not found in checkpoints."
        steps_summary = ", ".join(f"{s.id}: {s.status}" for s in plan.steps)
        return f"Task {plan.task_id}: {plan.status} | Goal: '{plan.goal}' | Steps: [{steps_summary}]"

    elif action in ("list", "list_tasks"):
        tasks = _engine.list_checkpoints()
        if not tasks:
            return "No task checkpoints found."
        lines = [f"• {t['task_id']} [{t['status']}] progress {t['progress']} - {t['goal']}" for t in tasks[:10]]
        return "Recent Tasks:\n" + "\n".join(lines)

    elif action in ("cancel", "stop"):
        if not task_id:
            return "Please specify task_id to cancel."
        ok = _engine.cancel_task(task_id)
        return f"Task '{task_id}' {'cancelled' if ok else 'is not running or not found'}."

    elif action in ("resume", "retry"):
        if not task_id:
            return "Please specify task_id to resume."
        plan = _engine.load_checkpoint(task_id)
        if not plan:
            return f"Task '{task_id}' not found."

        def run_tool(t_name: str, t_params: dict) -> Any:
            return _dispatch_action(t_name, t_params, player=player)

        final_plan = _engine.execute_plan(plan, executor_fn=run_tool, logger=logger)
        return f"Resumed Task {final_plan.task_id}: finished with status {final_plan.status}."

    return f"Unknown task_planner action: '{action}'. Available: plan_and_execute, status, list_tasks, cancel, resume."


# ── Tool declaration (auto-discovered by core/action_loader.py) ──────────────
TOOL = {
    "name": "task_planner",
    "description": (
        "Autonomous multi-step task planner and executor with Observe->Act->Verify->Recover loops "
        "and persistent checkpoints. Can plan tasks, execute sequences, verify outcomes, inspect progress, "
        "and resume or cancel multi-step workflows."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "description": "plan_and_execute | get_status | list_tasks | cancel | resume",
            },
            "goal": {
                "type": "STRING",
                "description": "High-level goal or instruction to plan and execute.",
            },
            "task_id": {
                "type": "STRING",
                "description": "Task identifier for status, resume, or cancellation.",
            },
            "steps": {
                "type": "ARRAY",
                "description": "Optional list of step objects with id, tool, parameters, depends_on, verification.",
                "items": {"type": "OBJECT"},
            },
        },
        "required": ["action"],
    },
    "handler": task_planner,
}
