import json
import shutil
import tempfile
import unittest
from pathlib import Path

# ── 1. Test Full Developer Agent (Item 4) ──────────────────────────────────
from actions.dev_agent import (
    dev_agent, git_status, git_diff, git_create_branch,
    git_rollback, run_tests, verify_build, run_terminal_command
)

# ── 2. Test Reusable Workflow Builder (Item 7) ─────────────────────────────
from core.workflow_builder import WorkflowStore, Workflow
from actions.workflow_manager import workflow_manager

# ── 3. Test Secure Remote Task Management (Item 8) ─────────────────────────
from dashboard.server import DashboardServer
from fastapi.testclient import TestClient

class TestAdditions478(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp_dir = Path(tempfile.mkdtemp())
        cls.wf_store = WorkflowStore(workflows_dir=cls.tmp_dir / "workflows")

        # Set up a test DashboardServer instance
        cls.server = DashboardServer()
        # Add a mock authenticated token
        cls.valid_token = "test_valid_auth_token_xyz"
        cls.server._tokens.add(cls.valid_token)
        cls.client = TestClient(cls.server.app)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp_dir, ignore_errors=True)

    # ── Item 4 Tests ───────────────────────────────────────────────────────
    def test_dev_agent_git_status(self):
        res = dev_agent({"action": "git_status"})
        self.assertIn("Git Status", res)

    def test_dev_agent_git_diff(self):
        res = dev_agent({"action": "git_diff"})
        self.assertIsInstance(res, str)
        self.assertTrue(len(res) > 0)

    def test_dev_agent_verify_build(self):
        res = dev_agent({"action": "verify_build"})
        self.assertIn("Build", res)

    def test_dev_agent_terminal(self):
        res = dev_agent({"action": "terminal", "command": "python --version"})
        self.assertIn("Success", res)
        self.assertIn("Python", res)

    def test_dev_agent_run_tests(self):
        # Run test discovery in a small temp project
        test_proj = self.tmp_dir / "test_proj"
        test_proj.mkdir(parents=True, exist_ok=True)
        test_file = test_proj / "test_sample.py"
        test_file.write_text("import unittest\nclass T(unittest.TestCase):\n    def test_pass(self):\n        self.assertTrue(True)\nif __name__ == '__main__':\n    unittest.main()", encoding="utf-8")
        res = run_tests(test_proj)
        self.assertIn("PASSED", res)

    # ── Item 7 Tests ───────────────────────────────────────────────────────
    def test_workflow_builder_save_and_run(self):
        wf = Workflow(
            id="unit_test_wf",
            name="Unit Test Workflow",
            description="Testing automated execution",
            parameters={"test_target": {"default": "all"}},
            steps=[
                {
                    "id": "s1",
                    "description": "Echo test",
                    "tool": "file_controller",
                    "parameters": {"action": "list", "path": "desktop"},
                    "verification": {"type": "non_empty"}
                }
            ]
        )
        self.wf_store.save(wf)
        loaded = self.wf_store.get("unit_test_wf")
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded.name, "Unit Test Workflow")

        # Execute directly via test store
        def dummy_tool(tool_name, params):
            return "File listed successfully"
        exec_plan = self.wf_store.execute_workflow(
            "unit_test_wf",
            executor_fn=dummy_tool,
            param_overrides={"test_target": "custom"}
        )
        self.assertEqual(exec_plan.status.upper(), "COMPLETED")

        # Test via workflow_manager action
        save_res = workflow_manager({
            "action": "save",
            "workflow_id": "manager_test_wf",
            "name": "Manager Test Workflow",
            "description": "Test via manager",
            "steps": [
                {
                    "id": "s1",
                    "description": "List desktop",
                    "tool": "file_controller",
                    "parameters": {"action": "list", "path": "desktop"}
                }
            ]
        })
        self.assertIn("saved with", save_res.lower())

        list_res = workflow_manager({"action": "list"})
        self.assertIn("Manager Test Workflow", list_res)

        del_res = workflow_manager({"action": "delete", "workflow_id": "manager_test_wf"})
        self.assertIn("deleted", del_res.lower())

    # ── Item 8 Tests ───────────────────────────────────────────────────────
    def test_remote_tasks_unauthorized(self):
        # Request without bearer token should fail with 401
        res = self.client.get("/api/tasks")
        self.assertEqual(res.status_code, 401)

    def test_remote_tasks_authorized_list(self):
        # Request with valid bearer token
        headers = {"Authorization": f"Bearer {self.valid_token}"}
        res = self.client.get("/api/tasks", headers=headers)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data.get("ok"))
        self.assertIsInstance(data.get("tasks"), list)

    def test_remote_task_create_and_action(self):
        headers = {"Authorization": f"Bearer {self.valid_token}"}
        # Create a task remotely
        create_res = self.client.post(
            "/api/tasks/create",
            headers=headers,
            json={"goal": "Remote companion test goal"}
        )
        self.assertEqual(create_res.status_code, 200)
        cdata = create_res.json()
        self.assertTrue(cdata.get("ok"))
        task_id = cdata.get("task_id")
        self.assertIsNotNone(task_id)

        # Inspect task detail remotely
        get_res = self.client.get(f"/api/tasks/{task_id}", headers=headers)
        self.assertEqual(get_res.status_code, 200)
        gdata = get_res.json()
        self.assertTrue(gdata.get("ok"))
        self.assertEqual(gdata.get("task", {}).get("goal"), "Remote companion test goal")

        # Cancel task remotely
        action_res = self.client.post(
            f"/api/tasks/{task_id}/action",
            headers=headers,
            json={"action": "cancel"}
        )
        self.assertEqual(action_res.status_code, 200)
        adata = action_res.json()
        self.assertTrue(adata.get("ok"))

if __name__ == "__main__":
    unittest.main()
