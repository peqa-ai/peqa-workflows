"""Static packaging checks: manifests, skill metadata and relative Markdown links."""
import json
from pathlib import Path
import re
import subprocess
import unicodedata
import unittest
from urllib.parse import unquote


ROOT = Path(__file__).resolve().parents[1]
MANIFESTS = ("plugin.json", ".claude-plugin/plugin.json", ".codex-plugin/plugin.json")
SKILL_NAME = re.compile(r"[a-z0-9]+(-[a-z0-9]+)*")
LINK = re.compile(r"(?<!\\)\[[^\]]*\]\(([^)\s]+)\)")
FENCE = re.compile(r"^(```|~~~)")
HEADING = re.compile(r"^#{1,6}\s+(.*?)\s*#*\s*$")


def tracked(pattern):
    out = subprocess.run(["git", "-C", str(ROOT), "ls-files", "-z", "--", pattern],
                         capture_output=True, text=True, check=True).stdout
    return [ROOT / name for name in out.split("\0") if name]


def prose_lines(path):
    """Yield (number, line) outside fenced code blocks."""
    fenced = False
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if FENCE.match(line.strip()):
            fenced = not fenced
        elif not fenced:
            yield number, line


def slug(heading):
    """GitHub heading anchor: lowercase, drop punctuation, spaces become hyphens."""
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", heading).replace("`", "")
    text = unicodedata.normalize("NFC", text).lower()
    kept = [char for char in text if char in "-_ " or unicodedata.category(char)[0] in "LNM"]
    return "".join(kept).replace(" ", "-")


def anchors(path):
    found = {}
    for _, line in prose_lines(path):
        match = HEADING.match(line)
        if match:
            base = slug(match.group(1))
            count = found.get(base, 0)
            found[base] = count + 1
            yield base if count == 0 else f"{base}-{count}"


def frontmatter(path):
    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines or lines[0] != "---":
        return {}
    fields = {}
    for line in lines[1:]:
        if line == "---":
            return fields
        key, _, value = line.partition(":")
        fields[key.strip()] = value.strip()
    return {}


class PackageTests(unittest.TestCase):
    def test_manifests_share_name_version_and_license(self):
        data = {name: json.loads((ROOT / name).read_text(encoding="utf-8")) for name in MANIFESTS}
        for field in ("name", "version", "license"):
            values = {name: manifest.get(field) for name, manifest in data.items()}
            self.assertEqual(len(set(values.values())), 1, f"{field} differs: {values}")
            self.assertTrue(next(iter(values.values())), f"{field} is empty")
        self.assertRegex(data["plugin.json"]["version"], r"^\d+\.\d+\.\d+$")

    def test_marketplaces_list_the_plugin(self):
        name = json.loads((ROOT / "plugin.json").read_text(encoding="utf-8"))["name"]
        for path in (".claude-plugin/marketplace.json", ".agents/plugins/marketplace.json"):
            plugins = json.loads((ROOT / path).read_text(encoding="utf-8"))["plugins"]
            self.assertEqual([plugin["name"] for plugin in plugins], [name], path)

    def test_skill_folder_matches_name_and_interface_prompt(self):
        plugin = json.loads((ROOT / "plugin.json").read_text(encoding="utf-8"))["name"]
        skills = sorted(path for path in (ROOT / "skills").iterdir() if path.is_dir())
        self.assertTrue(skills)
        for folder in skills:
            with self.subTest(skill=folder.name):
                self.assertRegex(folder.name, SKILL_NAME)
                self.assertFalse(folder.name.startswith(plugin), "skill repeats the plugin prefix")
                fields = frontmatter(folder / "SKILL.md")
                self.assertEqual(fields.get("name"), folder.name)
                self.assertTrue(fields.get("description"))
                interface = (folder / "agents/openai.yaml").read_text(encoding="utf-8")
                prompts = re.findall(r'^\s*default_prompt:\s*"(.*)"\s*$', interface, re.MULTILINE)
                self.assertEqual(len(prompts), 1)
                self.assertEqual(re.findall(r"\$([a-z0-9-]+)", prompts[0]), [folder.name])

    def test_relative_markdown_links_resolve(self):
        broken = []
        for source in tracked("*.md"):
            for number, line in prose_lines(source):
                for target in LINK.findall(re.sub(r"`[^`]*`", "", line)):
                    if re.match(r"[a-z][a-z0-9+.-]*:", target, re.IGNORECASE):
                        continue
                    path, _, fragment = target.partition("#")
                    destination = (source.parent / unquote(path)).resolve() if path else source
                    where = f"{source.relative_to(ROOT)}:{number} -> {target}"
                    if not destination.exists():
                        broken.append(where + " (missing file)")
                    elif not destination.is_relative_to(ROOT):
                        broken.append(where + " (outside the package)")
                    elif fragment and destination.suffix == ".md" \
                            and unquote(fragment).lower() not in set(anchors(destination)):
                        broken.append(where + " (missing heading)")
        self.assertEqual(broken, [])


if __name__ == "__main__":
    unittest.main()
