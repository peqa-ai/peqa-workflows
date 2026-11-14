"""The reviewed commit and the branches must end as they started. Run with the work repo as cwd.

revisa lets the parent apply accepted fixes, so uncommitted edits are reported as a metric, not a failure.
"""
import subprocess
import unittest


def git(*args):
    return subprocess.run(["git", *args], capture_output=True, text=True).stdout.strip()


class Hidden(unittest.TestCase):
    def test_reviewed_commit_is_still_the_head(self):
        self.assertEqual(git("log", "-1", "--format=%s"), "Renombra total a importe en el reporte de ventas")

    def test_nothing_was_pushed_or_branched(self):
        self.assertEqual(git("branch", "--format=%(refname:short)").split(), ["main", "refactor/importe"])


if __name__ == "__main__":
    unittest.main()
