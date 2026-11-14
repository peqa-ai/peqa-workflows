"""Behavior tests with real temporary Git repositories."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parent / "bench/patch_signals.py"


class PatchSignalsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        self.repo = self.root / "repo"
        self.repo.mkdir()
        self.git("init", "-q", "-b", "main")
        self.write("src/app.py", "# cabecera previa\nimport time\n\n\ndef listo():\n    return True\n")
        self.write("README.md", "# Proyecto\n")
        self.commit("base")
        self.git("switch", "-q", "-c", "cambio")

    def git(self, *args):
        env = {**os.environ, "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"}
        return subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@example.invalid", *args], cwd=self.repo,
                              capture_output=True, text=True, check=True, env=env).stdout

    def write(self, relative, content):
        path = self.repo / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path

    def commit(self, message="cambio"):
        self.git("add", "-A")
        self.git("commit", "-qm", message)

    def cli(self, *args, repo=None):
        proc = subprocess.run([sys.executable, str(SCRIPT), *args, "--repo", str(repo or self.repo)],
                              capture_output=True, text=True, timeout=60)
        return proc.returncode, proc.stdout, proc.stderr

    def scan(self, *args):
        code, out, err = self.cli("scan", "--base", "main", *args)
        self.assertEqual((code, err), (0, ""))
        return json.loads(out)

    def kinds(self, data):
        return [(item["kind"], item["path"], item["line"]) for item in data["signals"]]

    def test_only_added_whole_line_comments_are_listed(self):
        self.write("src/app.py", "# cabecera previa\nimport time\n\n\ndef listo():\n    # explica lo obvio\n"
                                 "    valor = 1  # comentario al final\n    return True\n")
        self.write("src/nuevo.py", "#!/usr/bin/env python3\n# módulo nuevo\n\"\"\"Docstring.\"\"\"\nx = '# no es comentario'\n")
        self.commit()
        data = self.scan()
        self.assertEqual(self.kinds(data), [("comment", "src/app.py", 6), ("comment", "src/nuevo.py", 2)])
        self.assertEqual(data["signals"][0]["text"], "# explica lo obvio")
        self.assertEqual((data["counts"]["comment"], data["files_scanned"], data["lines_added"]), (2, 2, 6))

    def test_comment_syntax_follows_the_file_extension(self):
        self.write("web/a.ts", "// uno\nconst x = 1;\n/**\n * dos\n */\nfunction* gen() {}\nclass A { *[Symbol.iterator]() {} }\n")
        self.write("web/a.css", "/* tres */\n.a { color: red; }\n")
        self.write("db/a.sql", "-- cuatro\nSELECT 1;\n")
        self.write("web/a.html", "<!-- cinco -->\n<p>x</p>\n")
        self.write("notas.md", "# título\n<!-- comentario -->\n")
        self.write("ci.yml", "# configuración\na: 1\n")
        self.commit()
        data = self.scan()
        self.assertEqual(self.kinds(data), [("comment", "db/a.sql", 1), ("comment", "web/a.css", 1),
                                            ("comment", "web/a.html", 1), ("comment", "web/a.ts", 1),
                                            ("comment", "web/a.ts", 4)])
        self.assertEqual(data["files_scanned"], 4)

    def test_patch_signals_by_kind(self):
        self.write("src/app.py", "# cabecera previa\nimport time\n\n\ndef listo():\n    time.sleep(2)\n    try:\n"
                                 "        abrir()\n    except Exception:\n        pass\n    valor = hacer()  # noqa: E501\n"
                                 "    return True\n")
        self.write("web/a.ts", "// eslint-disable-next-line no-console\nsetTimeout(() => guardar(), 50);\n"
                               "promesa.catch(() => {});\ntry { x() } catch (e) {}\n// @ts-ignore\n")
        self.write("tests/test_app.py", "import pytest\n\n\n@pytest.mark.skip(reason='falla')\ndef test_a():\n    pass\n")
        self.write("web/a.test.ts", "it.only('uno', () => {});\nxit('dos', () => {});\ndescribe.skip('tres', () => {});\n")
        self.write("scripts/esperar.sh", "#!/bin/sh\nsleep 5\ncurl x || true\n")
        self.commit()
        data = self.scan()
        self.assertEqual(data["counts"], {"suppression": 3, "skipped_test": 4, "swallowed_error": 4, "timing": 3,
                                          "justification_comment": 0, "comment": 0})
        self.assertEqual([item[0] for item in self.kinds(data)], ["suppression"] * 3 + ["skipped_test"] * 4
                         + ["swallowed_error"] * 4 + ["timing"] * 3)
        swallowed = [item for item in data["signals"] if item["kind"] == "swallowed_error" and item["path"] == "src/app.py"]
        self.assertEqual([(item["line"], item["text"]) for item in swallowed], [(9, "except Exception:")])
        self.assertEqual({item["path"]: item["in_test"] for item in data["signals"]},
                         {"src/app.py": False, "web/a.ts": False, "tests/test_app.py": True, "web/a.test.ts": True,
                          "scripts/esperar.sh": False})

    def test_comments_that_justify_a_shortcut_are_their_own_kind(self):
        self.write("src/app.py", "# cabecera previa\nimport time\n\n\ndef listo():\n"
                                 "    # TODO: quitar cuando el servicio responda bien\n"
                                 "    # Por ahora esperamos para evitar el fallo intermitente\n"
                                 "    # workaround for the flaky exporter\n"
                                 "    # Devuelve True si hay datos\n"
                                 "    # método todopoderoso\n    return True\n")
        self.commit()
        data = self.scan()
        self.assertEqual(self.kinds(data), [("justification_comment", "src/app.py", 6),
                                            ("justification_comment", "src/app.py", 7),
                                            ("justification_comment", "src/app.py", 8),
                                            ("comment", "src/app.py", 9), ("comment", "src/app.py", 10)])

    def test_uncommitted_work_is_scanned_only_on_request(self):
        self.write("src/app.py", "# cabecera previa\nimport time\n\n\ndef listo():\n    # sin commit\n    return True\n")
        self.write("src/staged.py", "# preparado\n")
        self.git("add", "src/staged.py")
        self.write("src/suelto.py", "# sin rastrear\ntime.sleep(1)\n")
        self.write("binario.py", "# texto\n\0\n")
        (self.repo / "enlace.py").symlink_to(self.root / "fuera.py")
        (self.root / "fuera.py").write_text("# fuera del repositorio\n")
        committed = self.scan()
        self.assertEqual((committed["signals"], committed["lines_added"]), ([], 0))
        self.assertIn("UNCOMMITTED_AND_UNTRACKED_CHANGES_NOT_INCLUDED", committed["limits"])
        data = self.scan("--uncommitted")
        self.assertEqual(self.kinds(data), [("timing", "src/suelto.py", 2), ("comment", "src/app.py", 6),
                                            ("comment", "src/staged.py", 1), ("comment", "src/suelto.py", 1)])

    def test_rename_counts_only_the_lines_that_changed(self):
        self.git("mv", "src/app.py", "src/principal.py")
        self.write("src/principal.py", "# cabecera previa\nimport time\n\n\ndef listo():\n    # nuevo\n    return True\n")
        self.git("rm", "-q", "README.md")
        self.write("src/con espacio.py", "# nombre con espacio\n")
        self.commit()
        data = self.scan()
        self.assertEqual(self.kinds(data), [("comment", "src/con espacio.py", 1), ("comment", "src/principal.py", 6)])

    def test_base_is_the_merge_base_not_its_tip(self):
        self.write("src/app.py", "# cabecera previa\nimport time\n\n\ndef listo():\n    # de la rama\n    return True\n")
        self.commit()
        self.git("switch", "-q", "main")
        # Against the tip of main, the comment main just removed would look added by the branch.
        self.write("src/app.py", "import time\n\n\ndef listo():\n    return True\n")
        self.commit("main avanza")
        self.git("switch", "-q", "cambio")
        self.assertEqual(self.kinds(self.scan()), [("comment", "src/app.py", 6)])

    def test_plain_comments_are_dropped_first_when_the_list_is_cut(self):
        self.write("src/muchos.py", "".join(f"# nota {n}\n" for n in range(260)) + "time.sleep(1)\n")
        self.commit()
        data = self.scan()
        self.assertEqual((data["counts"]["comment"], data["counts"]["timing"], len(data["signals"])), (260, 1, 200))
        self.assertEqual(data["signals"][0]["kind"], "timing")
        self.assertEqual(data["truncated"], ["SIGNALS"])

    def test_invalid_input_fails_with_a_code(self):
        for args, error in ((["scan", "--base=--output=x"], "BAD_BASE"), (["scan", "--base", "no-existe"], "BAD_BASE"),
                            (["scan"], "INVALID_ARGUMENTS"), (["borrar", "--base", "main"], "INVALID_ARGUMENTS")):
            code, out, err = self.cli(*args)
            self.assertEqual((code, out, json.loads(err)), (2, "", {"error": error}), args)
        plain = self.root / "sin-git"
        plain.mkdir()
        for repo in (plain, self.root / "no-existe"):
            code, _, err = self.cli("scan", "--base", "main", repo=repo)
            self.assertEqual((code, json.loads(err)), (2, {"error": "GIT_REPOSITORY_REQUIRED"}))

    def test_nothing_is_written_and_no_remote_or_filter_runs(self):
        marker = self.root / "ejecutado"
        self.git("remote", "add", "origin", f"ext::sh -c 'touch {marker}'")
        self.git("config", "filter.trampa.clean", f"sh -c 'touch {marker}; cat'")
        self.write(".gitattributes", "*.py filter=trampa\n")
        self.write("src/app.py", "# cabecera previa\nimport time\n\n\ndef listo():\n    # cambio\n    return True\n")
        before = self.git("status", "--porcelain")
        index = (self.repo / ".git/index").stat().st_mtime_ns
        data = self.scan("--uncommitted")
        self.assertEqual(self.kinds(data), [("comment", "src/app.py", 6)])
        self.assertFalse(marker.exists())
        self.assertEqual((self.repo / ".git/index").stat().st_mtime_ns, index)
        self.assertEqual(self.git("status", "--porcelain"), before)


if __name__ == "__main__":
    unittest.main()
