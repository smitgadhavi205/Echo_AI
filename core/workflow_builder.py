"""
core/workflow_builder.py — Reusable Workflow Builder and Execution Engine for Echo AI.
Allows users to:
1. Define, store, and parameterize reusable multi-step task workflows
2. Convert successful autonomous task plans (checkpoints) into reusable templates
3. Execute workflows on-demand or with triggers through the TaskEngine
"""
from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Callable

from core.task_engine import TaskEngine, TaskPlan, TaskStep

_WORKFLOWS_DIR = Path("data/workflows")


@dataclass
class Workflow:
    id: str
    name: str
    description: str
    parameters: Dict[str, Any] = field(default_factory=dict)
    trigger: Dict[str, Any] = field(default_factory=lambda: {"type": "manual"})
    steps: List[Dict[str, Any]] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> Workflow:
        return cls(**data)


class WorkflowStore:
    """Manages creation, storage, and execution of parameterized workflows."""

    def __init__(self, workflows_dir: Path = _WORKFLOWS_DIR, task_engine: Optional[TaskEngine] = None):
        self.workflows_dir = workflows_dir
        self.workflows_dir.mkdir(parents=True, exist_ok=True)
        self.engine = task_engine or TaskEngine()

    def _file_path(self, workflow_id: str) -> Path:
        clean_id = re.sub(r"[^a-zA-Z0-9_\-]", "_", workflow_id).strip("_").lower()
        return self.workflows_dir / f"{clean_id}.json"

    def save(self, workflow: Workflow) -> None:
        workflow.updated_at = time.time()
        path = self._file_path(workflow.id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(workflow.to_dict(), indent=2), encoding="utf-8")

    def get(self, workflow_id: str) -> Optional[Workflow]:
        # Try direct id
        path = self._file_path(workflow_id)
        if path.is_file():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                return Workflow.from_dict(data)
            except Exception:
                pass

        # Try match by name
        clean_q = workflow_id.strip().lower()
        for f in self.workflows_dir.glob("*.json"):
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                if data.get("id", "").lower() == clean_q or data.get("name", "").lower() == clean_q:
                    return Workflow.from_dict(data)
            except Exception:
                continue
        return None

    def list_all(self) -> List[Dict[str, Any]]:
        results = []
        if not self.workflows_dir.exists():
            return results
        for f in sorted(self.workflows_dir.glob("*.json"), key=os.path.getmtime, reverse=True):
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                results.append({
                    "id": data.get("id", f.stem),
                    "name": data.get("name", ""),
                    "description": data.get("description", ""),
                    "steps_count": len(data.get("steps", [])),
                    "trigger": data.get("trigger", {}).get("type", "manual"),
                    "updated_at": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(data.get("updated_at", 0))),
                })
            except Exception:
                continue
        return results

    def delete(self, workflow_id: str) -> bool:
        path = self._file_path(workflow_id)
        if path.is_file():
            path.unlink()
            return True
        target = self.get(workflow_id)
        if target:
            p = self._file_path(target.id)
            if p.is_file():
                p.unlink()
                return True
        return False

    def export_from_task(
        self,
        task_id: str,
        workflow_id: str,
        name: str = "",
        description: str = "",
        parameters: Optional[Dict[str, Any]] = None,
    ) -> Optional[Workflow]:
        """Convert a completed TaskPlan into a reusable workflow."""
        plan = self.engine.load_checkpoint(task_id)
        if not plan:
            return None

        clean_id = re.sub(r"[^a-zA-Z0-9_\-]", "_", workflow_id).strip("_").lower()
        steps = []
        for s in plan.steps:
            steps.append({
                "id": s.id,
                "description": s.description,
                "tool": s.tool,
                "parameters": s.parameters,
                "depends_on": s.depends_on,
                "verification": s.verification,
            })

        wf = Workflow(
            id=clean_id,
            name=name or plan.goal or clean_id.replace("_", " ").title(),
            description=description or f"Workflow created from task {task_id}",
            parameters=parameters or {},
            steps=steps,
        )
        self.save(wf)
        return wf

    def execute_workflow(
        self,
        workflow_id: str,
        param_overrides: Optional[Dict[str, Any]] = None,
        executor_fn: Optional[Callable[[str, dict], Any]] = None,
        logger: Optional[Callable[[str], None]] = None,
    ) -> Optional[TaskPlan]:
        """Run workflow through TaskEngine with parameter substitution."""
        wf = self.get(workflow_id)
        if not wf:
            return None

        # Build parameters mapping
        merged_params = {}
        for k, v in wf.parameters.items():
            default_val = v.get("default") if isinstance(v, dict) else v
            merged_params[k] = default_val
        if param_overrides:
            merged_params.update(param_overrides)

        # Substitute {{params.<key>}} in steps
        def _substitute(obj: Any) -> Any:
            if isinstance(obj, str):
                for k, v in merged_params.items():
                    tag = f"{{{{params.{k}}}}}"
                    if tag in obj:
                        if obj.strip() == tag:
                            return v
                        obj = obj.replace(tag, str(v))
                return obj
            elif isinstance(obj, dict):
                return {k: _substitute(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [_substitute(x) for x in obj]
            return obj

        hydrated_steps = _substitute(wf.steps)
        plan = self.engine.create_plan(
            goal=f"Workflow '{wf.name}': {wf.description}",
            steps=hydrated_steps,
        )
        plan.context["workflow_id"] = wf.id
        plan.context["parameters"] = merged_params

        return self.engine.execute_plan(plan, executor_fn=executor_fn, logger=logger)
