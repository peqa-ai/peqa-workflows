---
{
  "schema_version": 1,
  "id": "anadir-un-skill-toca",
  "title": "Añadir un skill toca más que su carpeta: helper de uso, tests y conteos",
  "category": "skills",
  "tags": [
    "empaquetado",
    "tests",
    "uso"
  ],
  "source": "Sesión del 2026-11-20; PR #30 de peqa-ai/peqa-workflows",
  "scope": "project",
  "machine": null,
  "verification": "observed",
  "environment": "peqa-workflows 0.24.0",
  "recheck": "Si los tests dejan de fijar listas de skills o el helper de uso lee los skills del disco",
  "created_at": "2026-11-20T16:24:02.680594Z",
  "updated_at": "2026-11-20T16:24:02.680594Z"
}
---
Al añadir `lenguaje-claro-formal-es` (PR #30, 20 de noviembre de 2026) hubo que tocar, además de `skills/<nombre>/` y `agents/openai.yaml`:

- `scripts/peqa_usage.py`: la tupla `SKILLS`; sin el nombre, `record --skill` lo rechaza.
- `tests/test_peqa_usage.py`: la lista de skills y el total de eventos (seis runtimes por skill).
- `tests/test_trigger_eval.py`: la lista fija de conjuntos, si se añade `queries/<skill>.json`.
- `references/usage.md`, README, los tres manifiestos (en Codex también `interface.shortDescription`) y `.claude-plugin/marketplace.json`: el número de skills o lo que hace el plugin, escritos en texto.

`git grep -n -e seis -e <skill-reciente>` encuentra esos conteos y listas. `revisa` y `ui-design` no tienen conjunto de consultas de activación: no es obligatorio para cada skill.
