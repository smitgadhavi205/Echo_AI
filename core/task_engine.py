"""
Autonomous Task Planner, Executor, and Checkpoint Engine for Echo AI.
Implements:
1. Ordered dependency-aware multi-step task planning
2. Observe -> Act -> Verify -> Recover execution cycle
3. Persistent checkpointing (save/resume/retry/cancel across sessions)
4. Parameter binding between sequential steps ({{steps.<id>.output}})
"""
from __future__ import annotations

import json
import os
import time
import uuid
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

_TASKS_DIR = Path("data/tasks")


class TaskStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class StepStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"
    WAITING_APPROVAL = "WAITING_APPROVAL"


@dataclass
class TaskStep:
    id: str
    description: str
    tool: str
    parameters: Dict[str, Any] = field(default_factory=dict)
    depends_on: List[str] = field(default_factory=list)
    verification: Dict[str, Any] = field(default_factory=dict)
    max_retries: int = 2
    retries: int = 0
    status: str = StepStatus.PENDING.value
    output: Any = None
    error: str = ""
    started_at: Optional[float] = None
    completed_at: Optional[float] = None


@dataclass
class TaskPlan:
    task_id: str
    goal: str
    steps: List[TaskStep]
    status: str = TaskStatus.PENDING.value
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    error: str = ""
    context: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> TaskPlan:
        steps = [TaskStep(**s) for s in data.get("steps", [])]
        data_copy = dict(data)
        data_copy["steps"] = steps
        return cls(**data_copy)


class TaskEngine:
    """Orchestrates persistent autonomous task execution for Echo AI."""

    def __init__(self, action_registry=None, tasks_dir: Path = _TASKS_DIR):
        self.action_registry = action_registry
        self.tasks_dir = tasks_dir
        self.tasks_dir.mkdir(parents=True, exist_ok=True)
        self._cancel_flags: Dict[str, bool] = {}

    def _checkpoint_path(self, task_id: str) -> Path:
        return self.tasks_dir / f"{task_id}.json"

    def save_checkpoint(self, plan: TaskPlan) -> None:
        """Persist task plan state to disk."""
        plan.updated_at = time.time()
        path = self._checkpoint_path(plan.task_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(plan.to_dict(), indent=2), encoding="utf-8")

    def load_checkpoint(self, task_id: str) -> Optional[TaskPlan]:
        """Load an existing task plan checkpoint from disk."""
        path = self._checkpoint_path(task_id)
        if not path.is_file():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return TaskPlan.from_dict(data)
        except Exception as e:
            print(f"[TaskEngine] Checkpoint load failed for {task_id}: {e}")
            return None

    def list_checkpoints(self) -> List[Dict[str, Any]]:
        """List summary of all saved task checkpoints."""
        res = []
        if not self.tasks_dir.exists():
            return res
        for f in sorted(self.tasks_dir.glob("*.json"), key=os.path.getmtime, reverse=True):
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                total_steps = len(data.get("steps", []))
                completed_steps = sum(
                    1 for s in data.get("steps", []) if s.get("status") == StepStatus.COMPLETED.value
                )
                res.append({
                    "task_id": data.get("task_id", f.stem),
                    "goal": data.get("goal", ""),
                    "status": data.get("status", ""),
                    "progress": f"{completed_steps}/{total_steps}",
                    "updated_at": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(data.get("updated_at", 0))),
                })
            except Exception:
                continue
        return res

    def cancel_task(self, task_id: str) -> bool:
        """Request immediate cancellation of a running task."""
        self._cancel_flags[task_id] = True
        plan = self.load_checkpoint(task_id)
        if plan and plan.status == TaskStatus.RUNNING.value:
            plan.status = TaskStatus.CANCELLED.value
            self.save_checkpoint(plan)
            return True
        return False

    def create_plan(self, goal: str, steps: List[Dict[str, Any]]) -> TaskPlan:
        """Instantiate a new task plan and store its initial checkpoint."""
        task_id = f"task_{int(time.time())}_{uuid.uuid4().hex[:6]}"
        task_steps = []
        for i, s in enumerate(steps):
            sid = s.get("id") or f"step_{i + 1}"
            task_steps.append(TaskStep(
                id=sid,
                description=s.get("description", f"Execute {s.get('tool', 'action')}"),
                tool=s.get("tool", ""),
                parameters=s.get("parameters", {}),
                depends_on=s.get("depends_on", []),
                verification=s.get("verification", {}),
                max_retries=s.get("max_retries", 2),
            ))
        plan = TaskPlan(task_id=task_id, goal=goal, steps=task_steps)
        self.save_checkpoint(plan)
        return plan

    def resolve_parameters(self, params: Any, completed_steps: Dict[str, TaskStep]) -> Any:
        """Recursively resolve {{steps.<step_id>.output}} template tags."""
        if isinstance(params, str):
            if "{{" in params and "}}" in params:
                for sid, step in completed_steps.items():
                    tag = f"{{{{steps.{sid}.output}}}}"
                    if tag in params:
                        if params.strip() == tag:
                            return step.output
                        params = params.replace(tag, str(step.output))
            return params
        elif isinstance(params, dict):
            return {k: self.resolve_parameters(v, completed_steps) for k, v in params.items()}
        elif isinstance(params, list):
            return [self.resolve_parameters(x, completed_steps) for x in params]
        return params

    def verify_step_result(self, step: TaskStep, result: Any) -> Tuple[bool, str]:
        """
        Observe -> Verify: Validate whether intended action outcome occurred.
        Supported verification strategies:
        - file_exists: check file is created and non-empty
        - non_empty: ensure tool returned meaningful output
        - contains_text: ensure expected text is in output
        """
        rule = step.verification or {}
        vtype = rule.get("type", "non_empty")

        if vtype == "file_exists":
            target = rule.get("target") or step.parameters.get("path") or step.parameters.get("name")
            if not target:
                return True, "No target path specified for file verification"
            p = Path(str(target)).expanduser()
            if not p.exists():
                return False, f"Verification failed: file '{p}' was not created."
            if rule.get("require_content", True) and p.stat().st_size == 0:
                return False, f"Verification failed: file '{p}' exists but is 0 bytes."
            return True, f"Verified: file '{p}' exists ({p.stat().st_size} bytes)."

        elif vtype == "contains_text":
            expected = rule.get("expected", "").lower()
            res_str = str(result or "").lower()
            if expected not in res_str:
                return False, f"Verification failed: expected '{expected}' not found in output."
            return True, f"Verified: found '{expected}' in output."

        elif vtype == "non_empty":
            if result is None or str(result).strip() == "":
                return False, "Verification failed: tool returned empty result."
            res_str = str(result)
            if "error" in res_str.lower() and "no error" not in res_str.lower():
                return False, f"Verification failed: tool indicated error: {res_str[:120]}"
            return True, "Verified: tool returned successful result."

        return True, "Verified (default pass)"

    def execute_plan(
        self,
        plan: TaskPlan,
        executor_fn: Optional[Callable[[str, dict], Any]] = None,
        logger: Optional[Callable[[str], None]] = None,
    ) -> TaskPlan:
        """
        Execute plan through the Observe -> Act -> Verify -> Recover loop.
        Can resume cleanly from an existing checkpoint.
        """
        log = logger or (lambda msg: print(f"[TaskEngine] {msg}"))
        self._cancel_flags[plan.task_id] = False
        plan.status = TaskStatus.RUNNING.value
        self.save_checkpoint(plan)

        log(f"Starting Task {plan.task_id}: '{plan.goal}' ({len(plan.steps)} steps)")

        completed_map: Dict[str, TaskStep] = {
            s.id: s for s in plan.steps if s.status == StepStatus.COMPLETED.value
        }

        for i, step in enumerate(plan.steps):
            if self._cancel_flags.get(plan.task_id, False):
                plan.status = TaskStatus.CANCELLED.value
                log(f"Task {plan.task_id} was cancelled by user.")
                self.save_checkpoint(plan)
                return plan

            if step.status == StepStatus.COMPLETED.value:
                log(f"Step {step.id} ('{step.description}') already completed. Skipping.")
                continue

            # Check dependencies
            unmet = [dep for dep in step.depends_on if dep not in completed_map]
            if unmet:
                step.status = StepStatus.FAILED.value
                step.error = f"Unmet dependencies: {', '.join(unmet)}"
                plan.status = TaskStatus.FAILED.value
                plan.error = f"Step {step.id} blocked by dependencies."
                self.save_checkpoint(plan)
                log(f"Step {step.id} failed: {step.error}")
                return plan

            # Observe & prepare
            step.status = StepStatus.RUNNING.value
            step.started_at = time.time()
            self.save_checkpoint(plan)

            resolved_params = self.resolve_parameters(step.parameters, completed_map)
            log(f"Executing [{step.id}/{len(plan.steps)}]: {step.description} via '{step.tool}'")

            # Act -> Verify -> Recover retry loop
            success = False
            while step.retries <= step.max_retries and not success:
                if self._cancel_flags.get(plan.task_id, False):
                    plan.status = TaskStatus.CANCELLED.value
                    self.save_checkpoint(plan)
                    return plan

                try:
                    # Act
                    if executor_fn:
                        output = executor_fn(step.tool, resolved_params)
                    else:
                        output = f"Executed {step.tool}({resolved_params})"

                    # Verify
                    verified, v_msg = self.verify_step_result(step, output)
                    if verified:
                        step.status = StepStatus.COMPLETED.value
                        step.output = output
                        step.completed_at = time.time()
                        completed_map[step.id] = step
                        success = True
                        log(f"Step {step.id} succeeded. ({v_msg})")
                    else:
                        step.retries += 1
                        log(f"Step {step.id} verify failed (try {step.retries}/{step.max_retries + 1}): {v_msg}")
                        if step.retries <= step.max_retries:
                            # Recover delay / backoff
                            time.sleep(0.5)

                except Exception as e:
                    step.retries += 1
                    step.error = str(e)
                    log(f"Step {step.id} execution exception (try {step.retries}/{step.max_retries + 1}): {e}")
                    if step.retries <= step.max_retries:
                        time.sleep(0.5)

            if not success:
                step.status = StepStatus.FAILED.value
                plan.status = TaskStatus.FAILED.value
                plan.error = f"Step {step.id} failed after {step.retries} attempts: {step.error or 'Verification failed'}"
                self.save_checkpoint(plan)
                log(f"Task {plan.task_id} halted on failed step {step.id}.")
                return plan

            self.save_checkpoint(plan)

        plan.status = TaskStatus.COMPLETED.value
        self.save_checkpoint(plan)
        log(f"Task {plan.task_id} completed successfully!")
        return plan
