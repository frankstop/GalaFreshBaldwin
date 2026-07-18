from __future__ import annotations

from pathlib import Path
import subprocess
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]


class ScriptTests(unittest.TestCase):
    def test_workflow_summary_is_useful_with_or_without_baseline(self) -> None:
        result = subprocess.run(
            [sys.executable, "scripts/workflow_summary.py"], cwd=ROOT, text=True, capture_output=True, check=True
        )
        self.assertIn("Gala Fresh Baldwin pipeline", result.stdout)
        self.assertTrue(
            "No healthy production snapshot" in result.stdout or "Status: **healthy**" in result.stdout
        )


if __name__ == "__main__":
    unittest.main()
