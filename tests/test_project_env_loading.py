import ast
import contextlib
import io
import os
from pathlib import Path
import sys
import tempfile
from types import ModuleType
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "runAiBot2.py"


class ProjectEnvLoadingTests(unittest.TestCase):
    def _run_bootstrap(self, project_root: Path):
        source = RUNTIME.read_text(encoding="utf-8")
        tree = ast.parse(source)
        bootstrap = []
        load_index = None
        first_project_import = None
        for index, node in enumerate(tree.body):
            if isinstance(node, ast.ImportFrom) and node.module in {
                "pathlib", "dotenv"
            }:
                bootstrap.append(node)
            elif (
                isinstance(node, ast.Expr)
                and isinstance(node.value, ast.Call)
                and isinstance(node.value.func, ast.Name)
                and node.value.func.id == "load_dotenv"
            ):
                bootstrap.append(node)
                load_index = index
            elif (
                first_project_import is None
                and isinstance(node, ast.ImportFrom)
                and node.module
                and (
                    node.module.startswith("config.")
                    or node.module.startswith("modules.ai.")
                )
            ):
                first_project_import = index

        self.assertIsNotNone(load_index)
        self.assertIsNotNone(first_project_import)
        self.assertLess(load_index, first_project_import)

        calls = []
        dotenv_module = ModuleType("dotenv")

        def fake_load_dotenv(*, dotenv_path, override):
            path = Path(dotenv_path)
            calls.append((path, override))
            if not path.exists():
                return False
            for raw_line in path.read_text(encoding="utf-8").splitlines():
                line = raw_line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if override or key not in os.environ:
                    os.environ[key] = value
            return True

        dotenv_module.load_dotenv = fake_load_dotenv
        namespace = {"__file__": str(project_root / "runAiBot2.py")}
        module = ast.Module(body=bootstrap, type_ignores=[])
        with patch.dict(sys.modules, {"dotenv": dotenv_module}):
            exec(compile(module, str(RUNTIME), "exec"), namespace)
        return calls

    def test_project_env_key_loads_when_process_env_is_empty(self):
        with tempfile.TemporaryDirectory() as directory:
            project_root = Path(directory)
            (project_root / ".env").write_text(
                "GEMINI_API_KEY=env-file-key\nGEMINI_MODEL=env-file-model\n",
                encoding="utf-8",
            )
            with patch.dict(os.environ, {}, clear=True):
                calls = self._run_bootstrap(project_root)
                self.assertEqual(os.environ["GEMINI_API_KEY"], "env-file-key")
                self.assertEqual(os.environ["GEMINI_MODEL"], "env-file-model")
            self.assertEqual(
                calls, [((project_root / ".env").resolve(), False)]
            )

    def test_existing_process_env_overrides_project_env(self):
        with tempfile.TemporaryDirectory() as directory:
            project_root = Path(directory)
            (project_root / ".env").write_text(
                "GEMINI_API_KEY=env-file-key\nGEMINI_MODEL=env-file-model\n",
                encoding="utf-8",
            )
            existing = {
                "GEMINI_API_KEY": "exported-key",
                "GEMINI_MODEL": "exported-model",
            }
            with patch.dict(os.environ, existing, clear=True):
                self._run_bootstrap(project_root)
                self.assertEqual(os.environ["GEMINI_API_KEY"], "exported-key")
                self.assertEqual(os.environ["GEMINI_MODEL"], "exported-model")

    def test_missing_project_env_does_not_crash(self):
        with tempfile.TemporaryDirectory() as directory:
            project_root = Path(directory)
            with patch.dict(os.environ, {}, clear=True):
                calls = self._run_bootstrap(project_root)
                self.assertNotIn("GEMINI_API_KEY", os.environ)
                self.assertNotIn("GEMINI_MODEL", os.environ)
            self.assertEqual(
                calls, [((project_root / ".env").resolve(), False)]
            )

    def test_api_key_is_never_logged(self):
        secret = "never-log-this-gemini-key"
        output = io.StringIO()
        with tempfile.TemporaryDirectory() as directory:
            project_root = Path(directory)
            (project_root / ".env").write_text(
                f"GEMINI_API_KEY={secret}\n",
                encoding="utf-8",
            )
            with patch.dict(os.environ, {}, clear=True), contextlib.redirect_stdout(
                output
            ), contextlib.redirect_stderr(output):
                self._run_bootstrap(project_root)
        self.assertNotIn(secret, output.getvalue())


if __name__ == "__main__":
    unittest.main()
