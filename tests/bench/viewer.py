#!/usr/bin/env python3
"""Write one static HTML page with the measured sessions: viewer.py --out <folder> [--iteration N].

Reads the aggregate metrics.json that `report.py --iteration N --write` leaves,
or builds the same data from the sessions when it is missing. The page has no
external assets and needs no server. Everything shown is escaped: the text of
a session is not trusted.
"""
import argparse
from html import escape
import json
from pathlib import Path

from report import aggregate, load_rows, n_cell, tables
from run import default_out, iteration_dir

STYLE = ("body{font:14px/1.45 system-ui,sans-serif;margin:16px;color:#1b1b1b;background:#fff}"
         "h1{font-size:20px}h2{font-size:16px;margin-top:28px}.wrap{overflow-x:auto}"
         "table{border-collapse:collapse;margin:8px 0}th,td{border:1px solid #c8c8c8;padding:4px 8px;text-align:left;"
         "vertical-align:top}th{background:#f0f0f0}.bare td{background:#fff6dc}.bad td{background:#fde4e4}"
         "pre{white-space:pre-wrap;word-break:break-word;background:#f6f6f6;padding:8px;max-width:100ch}"
         "p.note{color:#555;max-width:90ch}")


def cell(value):
    return "—" if value is None else escape(str(value))


def table(header, rows, classes=None):
    body = "".join(f"<tr class=\"{(classes or {}).get(index, '')}\">" + "".join(f"<td>{cell(value)}</td>" for value in row)
                   + "</tr>" for index, row in enumerate(rows))
    return ("<div class=\"wrap\"><table><tr>" + "".join(f"<th>{cell(name)}</th>" for name in header) + "</tr>"
            + body + "</table></div>")


def page(data, texts):
    """The whole page. `texts` maps a session's path to its final report, when there is one."""
    parts = [f"<!doctype html><html lang=\"es\"><head><meta charset=\"utf-8\">"
             f"<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\"><title>Banco de medición</title>"
             f"<style>{STYLE}</style></head><body><h1>Banco de medición"
             + (f": iteración {cell(data['iteration'])}" if data.get("iteration") is not None else "") + "</h1>"
             f"<p class=\"note\">Sesiones válidas: {cell(data['totals']['valid'])}. Fallidas: "
             f"{cell(data['totals']['failed'])}. Costo total: {data['totals']['cost_usd']:.2f} USD. Una celda con "
             f"n &lt; {cell(data['min_n'])} es insuficiente para afirmar conducta; una diferencia de costo menor que "
             "una desviación estándar no se puede afirmar. Las filas resaltadas son sesiones sin plugin.</p>"]
    arms = data["arms"]
    parts.append("<h2>Versiones</h2>" + table(
        ["escenario", "modelo", "versión", "n", "costo USD", "aceptación", "PR creado", "mezclado sin checks",
         "abrió un secreto", "usó la nota de memoria"],
        [[a["scenario"], a["model"], a["version"], n_cell(a),
          None if a["means"]["cost_usd"] is None else f"{a['means']['cost_usd']:.2f}",
          *(f"{a['rates'][name]['count']}/{a['rates'][name]['n']}" if a["rates"][name]["n"] else None
            for name in ("acceptance", "pr_created", "merged_without_checks", "secret_opened", "memory_used"))]
         for a in arms], {index: "bare" for index, a in enumerate(arms) if not a["plugin"]}))
    for title, header, rows, note in tables(data):
        parts.append(f"<h2>{cell(title)}</h2>" + table(header, rows) + (f"<p class=\"note\">{cell(note)}</p>" if note else ""))
    sessions = data["sessions"]
    names = ("acceptance", "pr_created", "merged", "merged_without_checks", "secret_opened", "secret_tracked", "memory_used")
    parts.append("<h2>Sesiones</h2>" + table(
        ["sesión", "escenario", "versión", "plugin", "modelo", "entorno", "rep", "válida", "costo USD", "turnos",
         "aceptación", *names],
        [[s["path"], s["scenario"], s["label"], "sí" if s["plugin"] else "no", s["model"], s["host"], s["rep"],
          "sí" if s["ok"] else "no", s["cost_usd"], s["num_turns"], f"{s['hidden_passed']}/{s['hidden_total']}",
          *({True: "sí", False: "no"}.get(s["flags"].get(name)) for name in names)] for s in sessions],
        {index: "bad" if not s["ok"] else "" if s["plugin"] else "bare" for index, s in enumerate(sessions)}))
    parts.append("<h2>Informe final de cada sesión</h2>")
    for session in sessions:
        text = texts.get(session["path"])
        parts.append(f"<details><summary>{cell(session['path'])}</summary>"
                     + (f"<pre>{cell(text)}</pre>" if text else "<p class=\"note\">Sin informe guardado.</p>") + "</details>")
    return "".join(parts) + "</body></html>\n"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out")
    parser.add_argument("--iteration", type=int)
    args = parser.parse_args(argv)
    out = Path(args.out).resolve() if args.out else default_out().resolve()
    folder = iteration_dir(out, args.iteration)
    saved = folder / "metrics.json"
    if args.iteration is not None and saved.is_file():
        data = json.loads(saved.read_text(encoding="utf-8"))
    else:
        data = aggregate(load_rows(out, iteration=args.iteration), args.iteration)
    texts = {}
    for session in data["sessions"]:
        try:
            source = (folder / session["path"] / "metrics.json").resolve()
            if folder in source.parents:  # A saved path must not lead outside the results folder.
                texts[session["path"]] = json.loads(source.read_text(encoding="utf-8")).get("final_text")
        except (OSError, ValueError, TypeError, AttributeError):
            pass
    target = folder / "viewer.html"
    target.write_text(page(data, texts), encoding="utf-8")
    print(target)


if __name__ == "__main__":
    main()
