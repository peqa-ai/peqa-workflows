#!/usr/bin/env python3
"""Triggering evals: does a natural-language request load the right skill?

`run` launches real headless Claude Code sessions and costs money; every other
subcommand works offline. Results go to a folder outside any repository.

    trigger_eval.py validate
    trigger_eval.py split
    trigger_eval.py run --model claude-opus-5-5 --split train --dry-run
    trigger_eval.py run --model claude-opus-5-5 --split train --confirm-sessions 144
    trigger_eval.py score
    trigger_eval.py select
"""
import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
from statistics import mean, stdev
import threading
import time

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
QUERIES = HERE / "queries"
TEMPLATE = REPO / "tests/bench/scenarios/feature/template"
PLUGIN = "peqa-workflows"
SEED = "peqa-triggering-1"
TRAIN_SHARE = 0.6
ACTUAL = "actual"  # the checked-in descriptions
SPLITS = ("train", "holdout", "all")
KEEP_ENV = ("HOME", "USER", "LOGNAME", "LANG", "LC_ALL", "TERM", "SHELL", "TMPDIR", "SSH_AUTH_SOCK")
FIELDS = {"id", "query", "should_trigger", "lang", "expected", "why"}
SLUG = re.compile(r"[a-z0-9]+(-[a-z0-9]+)*")
ORDINARY_WORDS = {"idea", "revisa"}  # skill names that are everyday Spanish words: a bare mention is not an invocation
MIN_QUERIES, MIN_CHARS, MIN_REPS = 16, 120, 3
_bench = None


def bench():
    """The measurement bench, for its plugin export and output folder rules."""
    global _bench
    if _bench is None:
        spec = importlib.util.spec_from_file_location("bench_run", REPO / "tests/bench/run.py")
        _bench = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(_bench)
    return _bench


def default_out():
    return bench().default_out() / "triggering"


def all_skills(root=REPO):
    return sorted(path.parent.name for path in (root / "skills").glob("*/SKILL.md"))


def load_sets(only=None, folder=QUERIES):
    """Query sets by skill; each query also carries the name of its set."""
    sets = {}
    for path in sorted(folder.glob("*.json")):
        if only and path.stem not in only:
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        if data.get("skill") != path.stem or not isinstance(data.get("queries"), list):
            raise SystemExit(f"{path.name}: needs a 'skill' equal to the file name and a list of 'queries'")
        sets[path.stem] = [dict(query, skill=path.stem) for query in data["queries"]]
    missing = sorted(set(only or ()) - set(sets))
    if missing:
        raise SystemExit(f"no query set for: {', '.join(missing)}")
    return sets


def validate(sets, skills=None):
    """Problems in the query sets, as a list of messages; empty when they are sound."""
    skills = skills or all_skills()
    problems, seen = [], Counter(query.get("id") for queries in sets.values() for query in queries)
    for skill, queries in sets.items():
        def bad(message, query=None):
            problems.append(f"{skill}{': ' + str(query.get('id')) if query else ''}: {message}")
        if skill not in skills:
            bad("is not a skill of this plugin")
        invoked = re.compile(rf"(?:[/$]|{PLUGIN}:)(?:{'|'.join(map(re.escape, skills))})(?![\w-])")
        named = re.compile(rf"(?<![\w-]){re.escape(skill)}(?![\w-])", re.I)
        for query in queries:
            extra = set(query) - FIELDS - {"skill"}
            if extra:
                bad(f"unknown fields {sorted(extra)}", query)
            if not isinstance(query.get("id"), str) or not SLUG.fullmatch(query["id"]):
                bad("id must be a lowercase slug", query)
            elif seen[query["id"]] > 1:
                bad("id is repeated", query)
            if query.get("lang") not in ("es", "en"):
                bad("lang must be es or en", query)
            if not isinstance(query.get("should_trigger"), bool):
                bad("should_trigger must be true or false", query)
            text = query.get("query")
            if not isinstance(text, str) or len(text) < MIN_CHARS:
                bad(f"query must be a realistic request of at least {MIN_CHARS} characters", query)
            elif invoked.search(text):
                bad("query invokes a skill explicitly", query)
            if query.get("should_trigger") is True and ("expected" in query or "why" in query):
                bad("only negatives carry expected and why", query)
            if query.get("should_trigger") is False:
                if "expected" not in query or not (query["expected"] is None or query["expected"] in skills):
                    bad("expected must be another real skill or null", query)
                elif query["expected"] == skill:
                    bad("expected cannot be the skill under test", query)
                if not isinstance(query.get("why"), str) or not query["why"].strip():
                    bad("a negative needs a short why", query)
        sound = [query for query in queries if isinstance(query.get("should_trigger"), bool) and query.get("lang") in ("es", "en")]
        hits = sum(query["should_trigger"] for query in sound)
        if len(queries) < MIN_QUERIES:
            bad(f"has {len(queries)} queries; at least {MIN_QUERIES} are needed")
        if sound and not 0.4 <= hits / len(sound) <= 0.6:
            bad(f"is unbalanced: {hits} of {len(sound)} should trigger")
        strata = Counter((query["should_trigger"], query["lang"]) for query in sound)
        if any(strata[(hit, lang)] < 2 for hit in (True, False) for lang in ("es", "en")):
            bad("needs at least two queries per language among hits and among near misses")
        if sum(query["lang"] == "es" for query in sound) <= len(sound) / 2:
            bad("Spanish must be the majority language")
        if skill not in ORDINARY_WORDS and sum(bool(named.search(str(query.get("query")))) for query in queries) > 1:
            bad("names the skill in more than one query")
    return problems


def split_of(queries, seed=SEED):
    """Train or holdout for each query id, 60/40 within each (should_trigger, lang) stratum.

    The order inside a stratum comes from a hash of seed and id, so a new query
    can move at most the one query at the cut of its own stratum.
    """
    strata, assignment = {}, {}
    for query in queries:
        strata.setdefault((query["should_trigger"], query["lang"]), []).append(query["id"])
    for ids in strata.values():
        ranked = sorted(ids, key=lambda name: hashlib.sha256(f"{seed}:{name}".encode()).hexdigest())
        cut = int(len(ranked) * TRAIN_SHARE + 0.5)
        assignment.update((name, "train" if place < cut else "holdout") for place, name in enumerate(ranked))
    return assignment


def blocks(event):
    content = (event.get("message") or {}).get("content")
    return [block for block in content if isinstance(block, dict)] if isinstance(content, list) else []


class Watch:
    """Read a session's events one at a time until the outcome is known.

    A skill counts as loaded when the main thread calls the Skill tool with its
    name, or opens its SKILL.md with Read or a shell command. `stop` becomes
    'skill', 'tools' or 'ended' once there is nothing left to learn.
    """

    def __init__(self, skills, plugin_dir=None, max_tools=3, max_skills=1):
        self.skills, self.max_tools, self.max_skills = set(skills), max_tools, max_skills
        self.loaded, self.other_tools, self.cost_usd, self.terminal, self.error, self.stop = [], 0, None, None, False, None
        names = "|".join(re.escape(name) for name in sorted(self.skills, key=len, reverse=True))
        self.opened = re.compile(rf"([^\s\"'=;|&()<>]*)skills/({names})/SKILL\.md")
        roots = {str(plugin_dir), os.path.realpath(plugin_dir)} if plugin_dir else set()
        self.roots = tuple(root.rstrip("/") + "/" for root in roots)

    def files(self, text):
        for prefix, name in self.opened.findall(text):
            if prefix and not prefix.endswith("/"):
                continue
            if prefix.startswith(("/", "~")) and self.roots and not prefix.startswith(self.roots):
                continue  # A copy of the skill somewhere else on the machine, not the plugin under test.
            yield name

    def skills_in(self, name, data):
        if name == "Skill":
            skill = str(data.get("skill", "")).lstrip("/").removeprefix(PLUGIN + ":")
            return [skill] if skill in self.skills else []
        if name == "Read":
            return list(self.files(str(data.get("file_path", ""))))
        if name == "Bash":
            return list(self.files(str(data.get("command", ""))))
        return []

    def feed(self, line):
        if self.stop:
            return self.stop
        try:
            event = json.loads(line) if isinstance(line, str) else line
        except ValueError:
            return None
        if not isinstance(event, dict):
            return None
        if event.get("type") == "result":
            self.cost_usd, self.terminal = event.get("total_cost_usd"), event.get("subtype")
            self.error, self.stop = bool(event.get("is_error")), "ended"
            return self.stop
        if event.get("type") != "assistant" or event.get("parent_tool_use_id"):
            return None  # Subagents load skills for their own work; only the main thread routes the request.
        for block in blocks(event):
            if block.get("type") != "tool_use":
                continue
            found = self.skills_in(block.get("name"), block.get("input") or {})
            self.loaded += [skill for skill in dict.fromkeys(found) if skill not in self.loaded]
            self.other_tools += not found
        if self.max_skills and len(self.loaded) >= self.max_skills:
            self.stop = "skill"
        elif self.max_tools and self.other_tools >= self.max_tools:
            self.stop = "tools"
        return self.stop


def detect(lines, skills, plugin_dir=None, max_tools=None, max_skills=None):
    """Skills a stream loaded, in order. Without limits it reads the whole stream."""
    watch = Watch(skills, plugin_dir, max_tools, max_skills)
    for line in lines:
        if watch.feed(line):
            break
    return {"loaded": watch.loaded, "other_tools": watch.other_tools, "stop": watch.stop, "cost_usd": watch.cost_usd,
            "terminal": watch.terminal, "error": watch.error}


def description_of(skill_file):
    lines = skill_file.read_text(encoding="utf-8").split("\n")
    place = _description_line(lines, skill_file)
    text = lines[place].partition(":")[2].strip()
    return json.loads(text) if text.startswith('"') else text


def _description_line(lines, skill_file):
    if lines[0] != "---" or "---" not in lines[1:]:
        raise SystemExit(f"{skill_file}: no frontmatter")
    end = lines.index("---", 1)
    places = [place for place in range(1, end) if lines[place].startswith("description:")]
    if len(places) != 1 or lines[places[0] + 1][:1] in (" ", "\t"):
        raise SystemExit(f"{skill_file}: expected one single-line description in the frontmatter")
    return places[0]


def set_description(skill_file, text):
    """Rewrite only the frontmatter description of one SKILL.md."""
    if not isinstance(text, str) or not text.strip() or "\n" in text:
        raise SystemExit(f"{skill_file}: a description is one non-empty line")
    lines = skill_file.read_text(encoding="utf-8").split("\n")
    plain = not re.search(r": | #|:$", text) and not re.match(r"[\s!&*\[\]{}>|'\"%@`#,?:-]", text) and text == text.strip()
    lines[_description_line(lines, skill_file)] = "description: " + (text if plain else json.dumps(text, ensure_ascii=False))
    skill_file.write_text("\n".join(lines), encoding="utf-8")


def load_variants(path, skills=None):
    """{variant: {skill: description}}, always starting with the checked-in one."""
    skills = skills or all_skills()
    variants = {ACTUAL: {}}
    if not path:
        return variants
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    for name, changes in data.items():
        if name == ACTUAL or not SLUG.fullmatch(name) or not isinstance(changes, dict) or not changes:
            raise SystemExit(f"variant {name!r}: use a lowercase slug other than '{ACTUAL}' with at least one skill")
        for skill, text in changes.items():
            if skill not in skills or not isinstance(text, str) or not text.strip() or "\n" in text:
                raise SystemExit(f"variant {name!r}: {skill!r} needs a real skill and a one-line description")
        variants[name] = changes
    return variants


def export_variant(ref, dest, changes):
    """Copy the plugin and apply a variant's descriptions to the copy; the repository is never edited."""
    revision = bench().export_plugin(ref, dest)
    for skill, text in changes.items():
        set_description(dest / "skills" / skill / "SKILL.md", text)
    return revision


def session_command(query, model, plugin_dir, budget, permission_mode=None):
    # Same isolation as the bench; SendMessage is denied so concurrent sessions cannot write to each other.
    command = ["claude", "-p", query, "--model", model, "--plugin-dir", str(plugin_dir),
               "--output-format", "stream-json", "--verbose", "--setting-sources", "project,local",
               "--strict-mcp-config", "--no-session-persistence", "--disallowedTools", "SendMessage",
               "--max-budget-usd", str(budget)]
    return command + (["--permission-mode", permission_mode] if permission_mode else [])


def session_env():
    # Keep credentials (ANTHROPIC_*); drop host markers so the session behaves like a plain terminal one.
    env = {key: value for key, value in os.environ.items() if key in KEEP_ENV or key.startswith("ANTHROPIC_")}
    # The bench's stand-ins go first, so a session that calls gh or codex before it is stopped never reaches the real ones.
    env.update(PATH=f"{bench().SHIMS}:{os.environ['PATH']}", BENCH_REAL_GIT=bench().real_binary("git") or "git")
    return env


def prepare_work(work):
    """A fresh sample project with one commit, so the session starts from a clean checkout."""
    if work.exists():
        shutil.rmtree(work)
    shutil.copytree(TEMPLATE, work)
    git = ("git", "-c", "user.name=dev", "-c", "user.email=dev@example.invalid", "-c", "init.defaultBranch=main")
    for arguments in (("init", "-q"), ("add", "-A"), ("commit", "-qm", "Reporte de ventas inicial")):
        subprocess.run([*git, *arguments], cwd=work, capture_output=True, text=True, check=True)


def plan(sets, variants, split, reps, seed=SEED):
    """One job per query, variant and repetition. A variant runs only the sets of the skills it rewrites."""
    jobs = []
    for rep in range(1, reps + 1):  # Repetitions outermost: variants alternate instead of running in blocks.
        for skill, queries in sets.items():
            assignment = split_of(queries, seed)
            for query in queries:
                for variant, changes in variants.items():
                    if split in ("all", assignment[query["id"]]) and (variant == ACTUAL or skill in changes):
                        jobs.append({"id": query["id"], "skill": skill, "rep": rep, "variant": variant,
                                     "should_trigger": query["should_trigger"], "expected": query.get("expected"),
                                     "lang": query["lang"], "query": query["query"]})
    return jobs


def result_path(out, model, job):
    return out / "results" / model / job["variant"] / job["skill"] / f"{job['id']}-r{job['rep']}.json"


def saved(path):
    try:
        return bool(json.loads(path.read_text(encoding="utf-8")).get("valid"))
    except (OSError, ValueError):
        return False


def launch(command, **options):
    """The only place that starts a paid session; tests replace it."""
    return subprocess.Popen(command, **options)


def run_session(job, args, out, skills):
    path = result_path(out, args.model, job)
    plugin_dir = out / "plugins" / job["variant"]
    work = out / "work" / args.model / job["variant"] / job["skill"] / path.stem
    stream = path.with_suffix(".jsonl")
    path.parent.mkdir(parents=True, exist_ok=True)
    prepare_work(work)
    watch = Watch(skills, plugin_dir, args.max_tools, args.max_skills)
    started = time.time()
    with open(stream, "w", encoding="utf-8") as events, open(path.with_suffix(".stderr.txt"), "w") as errors:
        process = launch(session_command(job["query"], args.model, plugin_dir, args.budget, args.permission_mode),
                         cwd=work, env=session_env(), stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                         stderr=errors, text=True, encoding="utf-8", errors="replace")
        timer = threading.Timer(args.timeout, process.kill)
        timer.start()
        try:
            for line in process.stdout:
                events.write(line)
                if watch.feed(line):
                    break  # The outcome is known: every further turn would only cost money.
        finally:
            timer.cancel()
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
    wall = time.time() - started
    stop = watch.stop or ("timeout" if wall >= args.timeout else "exit")
    result = {key: job[key] for key in ("id", "skill", "rep", "variant", "should_trigger", "expected", "lang")}
    result.update(model=args.model, description=description_of(plugin_dir / "skills" / job["skill"] / "SKILL.md"),
                  loaded=watch.loaded, triggered=job["skill"] in watch.loaded, other_tools=watch.other_tools, stop=stop,
                  valid=stop in ("skill", "tools") or (stop == "ended" and not watch.error), terminal=watch.terminal,
                  cost_usd=watch.cost_usd, wall_s=round(wall, 1), stream=str(stream))
    path.write_text(json.dumps(result, indent=1, ensure_ascii=False), encoding="utf-8")
    shutil.rmtree(work, ignore_errors=True)
    return result


def run(args):
    out = Path(args.out).resolve() if args.out else default_out().resolve()
    if not bench().outside_repositories(out):
        raise SystemExit("--out must be outside any Git repository: the session would load that project's instructions")
    skills = all_skills()
    sets = load_sets(args.skill)
    problems = validate(sets, skills)
    if problems:
        raise SystemExit("invalid query sets:\n" + "\n".join(problems))
    variants = load_variants(args.descriptions, skills)
    if args.variant:
        unknown = sorted(set(args.variant) - set(variants))
        if unknown:
            raise SystemExit(f"unknown variants: {', '.join(unknown)}")
        variants = {name: changes for name, changes in variants.items() if name in args.variant}
    jobs = plan(sets, variants, args.split, args.reps, args.seed)
    pending = [job for job in jobs if not saved(result_path(out, args.model, job))]
    print(f"Planned sessions: {len(jobs)} ({len(jobs) - len(pending)} already saved, {len(pending)} to launch), "
          f"each capped at {args.budget} USD. Output: {out}")
    if args.dry_run:
        for job in pending:
            print(shlex.join(session_command(job["query"], args.model, out / "plugins" / job["variant"], args.budget,
                                             args.permission_mode)))
        return
    if not pending:
        return
    if args.confirm_sessions != len(pending):
        raise SystemExit(f"Every session calls the model and costs money. Nothing was launched: "
                         f"pass --confirm-sessions {len(pending)} to run exactly these sessions.")
    for variant in sorted({job["variant"] for job in pending}):
        export_variant(args.plugin_ref, out / "plugins" / variant, variants[variant])
    with ThreadPoolExecutor(max_workers=max(1, args.jobs)) as pool:
        for result in pool.map(lambda job: run_session(job, args, out, skills), pending):
            print(json.dumps({key: result[key] for key in ("skill", "variant", "id", "rep", "loaded", "stop", "valid", "cost_usd")}),
                  flush=True)


def load_results(out):
    rows = []
    for path in sorted((out / "results").glob("*/*/*/*.json")):
        try:
            rows.append(json.loads(path.read_text(encoding="utf-8")))
        except ValueError:
            continue
    return rows


def measure(queries, results):
    """Metrics of one skill, variant and split from its valid sessions.

    A query passes when it triggered in most repetitions (should trigger) or in
    fewer than half (should not); an exact half fails either way.
    """
    known = {query["id"]: query for query in queries}
    by_query, by_rep = {}, {}
    for row in results:
        if row["id"] in known:
            by_query.setdefault(row["id"], []).append(row)
            by_rep.setdefault(row["rep"], []).append((row["skill"] in row["loaded"]) == known[row["id"]]["should_trigger"])
    counts, failing, expected_hits, expected_total = Counter(), [], 0, 0
    for name, rows in sorted(by_query.items()):
        query, fired = known[name], sum(row["skill"] in row["loaded"] for row in rows)
        passed = fired * 2 > len(rows) if query["should_trigger"] else fired * 2 < len(rows)
        counts[("t" if passed else "f") + ("p" if query["should_trigger"] == passed else "n")] += 1
        if query.get("expected"):
            expected_total += len(rows)
            expected_hits += sum(query["expected"] in row["loaded"] for row in rows)
        if not passed:
            first = Counter(row["loaded"][0] if row["loaded"] else "ninguno" for row in rows)
            failing.append({"id": name, "should_trigger": query["should_trigger"], "triggered": fired, "sessions": len(rows),
                            "expected": query.get("expected"), "loaded": dict(first)})
    tp, fp, fn, tn = counts["tp"], counts["fp"], counts["fn"], counts["tn"]
    per_rep = [mean(hits) for _, hits in sorted(by_rep.items())]
    return {"queries": len(by_query), "reps": len(per_rep), "tp": tp, "fp": fp, "fn": fn, "tn": tn,
            "precision": tp / (tp + fp) if tp + fp else None, "recall": tp / (tp + fn) if tp + fn else None,
            "accuracy": (tp + tn) / len(by_query) if by_query else None,
            "rep_accuracy": per_rep, "rep_mean": mean(per_rep) if per_rep else None,
            "rep_stdev": stdev(per_rep) if len(per_rep) > 1 else 0.0,
            "expected_loaded": [expected_hits, expected_total], "failing": failing}


def summarise(results, sets, seed=SEED):
    """One row per model, skill, variant and split."""
    groups = {}
    for row in results:
        if row.get("valid") and row.get("skill") in sets:
            groups.setdefault((row["model"], row["skill"], row["variant"]), []).append(row)
    rows = []
    for (model, skill, variant), items in sorted(groups.items()):
        assignment = split_of(sets[skill], seed)
        for split in SPLITS:
            queries = [query for query in sets[skill] if split in ("all", assignment[query["id"]])]
            rows.append({"model": model, "skill": skill, "variant": variant, "split": split, **measure(queries, items)})
    return rows


def choose(holdout):
    """Pick a variant from {variant: holdout metrics}; returns (winner, {variant: verdict}).

    A variant beats `actual` only when its mean per-repetition accuracy exceeds
    it by more than one standard deviation (the larger of the two) with at least
    three repetitions on each side. Anything else is a tie and keeps `actual`.
    """
    base, verdicts, winner, best = holdout.get(ACTUAL), {}, ACTUAL, 0.0
    for variant, row in holdout.items():
        if variant == ACTUAL:
            continue
        if not base or not base["reps"] or not row["reps"]:
            verdicts[variant] = "sin datos de holdout"
        elif min(base["reps"], row["reps"]) < MIN_REPS:
            verdicts[variant] = f"faltan repeticiones (mínimo {MIN_REPS})"
        else:
            gain, sigma = row["rep_mean"] - base["rep_mean"], max(row["rep_stdev"], base["rep_stdev"])
            wins = gain > sigma + 1e-9  # An advantage of exactly one deviation is still a tie.
            verdicts[variant] = "gana" if wins else "peor" if -gain > sigma + 1e-9 else "empate"
            if wins and gain > best:
                winner, best = variant, gain
    return winner, verdicts


def share(value):
    return "–" if value is None else f"{value:.2f}"


def spread(row):
    return "–" if row["rep_mean"] is None else f"{row['rep_mean']:.2f} ± {row['rep_stdev']:.2f}"


def table(title, header, rows):
    print(f"\n## {title}\n")
    print("| " + " | ".join(header) + " |")
    print("|" + "---|" * len(header))
    for row in rows:
        print("| " + " | ".join(str(cell) for cell in row) + " |")


def saved_rows(args):
    out = Path(args.out).resolve() if args.out else default_out().resolve()
    results = load_results(out)
    return results, summarise(results, load_sets(args.skill), args.seed)


def score(args):
    results, rows = saved_rows(args)
    if args.json:
        print(json.dumps(rows, indent=1, ensure_ascii=False))
        return
    table("Activación por skill, variante y partición",
          ["modelo", "skill", "variante", "partición", "consultas", "reps", "precisión", "recall", "exactitud",
           "exactitud por rep (media ± σ)", "casi aciertos: cargó el skill esperado"],
          [(row["model"], row["skill"], row["variant"], row["split"], row["queries"], row["reps"], share(row["precision"]),
            share(row["recall"]), share(row["accuracy"]), spread(row), "{}/{}".format(*row["expected_loaded"]))
           for row in rows])
    table("Consultas que fallan",
          ["modelo", "skill", "variante", "partición", "consulta", "debía activar", "activó", "esperado", "primer skill cargado"],
          [(row["model"], row["skill"], row["variant"], row["split"], item["id"], "sí" if item["should_trigger"] else "no",
            f"{item['triggered']}/{item['sessions']}", item["expected"] or "ninguno",
            ", ".join(f"{name} ×{count}" for name, count in sorted(item["loaded"].items())))
           for row in rows if row["split"] != "all" for item in row["failing"]])
    invalid = [row for row in results if not row.get("valid")]
    print(f"\nUna consulta pasa si activó el skill en la mayoría de las repeticiones (cuando debía) o en menos de la "
          f"mitad (cuando no). Sesiones válidas: {len(results) - len(invalid)}. Inválidas: {len(invalid)}. "
          f"Costo conocido: {sum(row.get('cost_usd') or 0 for row in results):.2f} USD "
          f"(las sesiones detenidas al conocer el resultado no informan costo).")


def select(args):
    _, rows = saved_rows(args)
    cells = {(row["model"], row["skill"], row["split"], row["variant"]): row for row in rows}
    decisions, lines = [], []
    for model, skill in sorted({(row["model"], row["skill"]) for row in rows}):
        holdout = {variant: row for (m, s, split, variant), row in cells.items() if (m, s, split) == (model, skill, "holdout")}
        winner, verdicts = choose(holdout)
        decisions.append({"model": model, "skill": skill, "selected": winner, "verdicts": verdicts,
                          "holdout": {variant: {key: row[key] for key in ("rep_mean", "rep_stdev", "reps", "queries")}
                                      for variant, row in holdout.items()}})
        for variant in sorted(holdout, key=lambda name: (name != ACTUAL, name)):
            train = cells.get((model, skill, "train", variant))
            gain = holdout[variant]["rep_mean"] - holdout[ACTUAL]["rep_mean"] \
                if variant != ACTUAL and ACTUAL in holdout and holdout[ACTUAL]["reps"] and holdout[variant]["reps"] else None
            lines.append((model, skill, variant, spread(holdout[variant]), holdout[variant]["reps"],
                          "–" if gain is None else f"{gain:+.2f}", spread(train) if train else "–",
                          verdicts.get(variant, "referencia"), "sí" if variant == winner else ""))
    if args.json:
        print(json.dumps(decisions, indent=1, ensure_ascii=False))
        return
    table("Selección de descripción por holdout",
          ["modelo", "skill", "variante", "holdout: exactitud por rep (media ± σ)", "reps", "ventaja sobre actual",
           "train (solo contexto)", "veredicto", "elegida"], lines)
    print(f"\nLa elección usa solo el holdout; train se muestra como contexto y no decide. Una variante gana a "
          f"`{ACTUAL}` si su ventaja en holdout supera una desviación estándar de la exactitud por repetición "
          f"(la mayor de las dos) con al menos {MIN_REPS} repeticiones en cada lado. Lo demás es empate y se conserva `{ACTUAL}`.")


def check(args):
    sets = load_sets(args.skill)
    problems = validate(sets)
    for skill, queries in sets.items():
        hits = sum(query["should_trigger"] is True for query in queries)
        print(f"{skill}: {len(queries)} queries, {hits} should trigger, "
              f"{sum(query.get('lang') == 'es' for query in queries)} in Spanish")
    if problems:
        raise SystemExit("\n".join(problems))
    print("ok")


def show_split(args):
    sets = load_sets(args.skill)
    assignment = {skill: split_of(queries, args.seed) for skill, queries in sets.items()}
    if args.json:
        print(json.dumps(assignment, indent=1))
        return
    for skill, queries in sets.items():
        for query in queries:
            print(f"{assignment[skill][query['id']]:8}{skill:17}{'hit ' if query['should_trigger'] else 'miss'} "
                  f"{query['lang']} {query['id']}")
        print(f"# {skill}: {Counter(assignment[skill].values())['train']} train, "
              f"{Counter(assignment[skill].values())['holdout']} holdout")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)

    def command(name, action, text):
        sub = commands.add_parser(name, help=text)
        sub.set_defaults(action=action)
        sub.add_argument("--skill", action="append", help="limit to this query set; repeat for several")
        sub.add_argument("--seed", default=SEED, help="seed of the train/holdout split")
        return sub

    command("validate", check, "check the query sets; no model")
    command("split", show_split, "print the train/holdout assignment; no model").add_argument("--json", action="store_true")
    paid = command("run", run, "PAID: launch the sessions")
    paid.add_argument("--model", required=True)
    paid.add_argument("--split", choices=SPLITS, default="train")
    paid.add_argument("--reps", type=int, default=3)
    paid.add_argument("--descriptions", help="JSON file {variant: {skill: description}} to compare against the checked-in ones")
    paid.add_argument("--variant", action="append", help=f"limit to this variant ('{ACTUAL}' is the checked-in one); repeat for several")
    paid.add_argument("--plugin-ref", default=".", help="Git ref of this repository to load as the plugin, or '.' for the working tree")
    paid.add_argument("--confirm-sessions", type=int, help="number of sessions you agree to pay for; must equal the plan")
    paid.add_argument("--dry-run", action="store_true", help="print the plan and the commands without launching anything")
    paid.add_argument("--jobs", type=int, default=2, help="sessions in parallel")
    paid.add_argument("--budget", default="0.5", help="spending cap for each session in USD")
    paid.add_argument("--timeout", type=int, default=300)
    paid.add_argument("--max-tools", type=int, default=3, help="stop a session after this many tool calls that load no skill")
    paid.add_argument("--max-skills", type=int, default=1, help="stop a session once this many skills loaded")
    paid.add_argument("--permission-mode", help="passed through to claude; omitted by default, so the session asks for nothing it is not already allowed")
    paid.add_argument("--out")
    for name, action, text in (("score", score, "metrics from the saved sessions; no model"),
                               ("select", select, "choose a description variant per skill by holdout; no model")):
        sub = command(name, action, text)
        sub.add_argument("--out")
        sub.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    args.action(args)


if __name__ == "__main__":
    main()
