---
{
  "schema_version": 1,
  "id": "orca-worker-checkout-path",
  "title": "En Orca, `--worktree current` es el workspace de la sesión, no el checkout del cambio",
  "category": "orca",
  "tags": [
    "revisa",
    "workers",
    "worktree"
  ],
  "source": "Sesión del 2026-11-08, preparación de CR 1/3 del PR #11 de peqa-ai/peqa-workflows; `orca worktree current` y `orca worktree show --worktree path:<checkout>` en Orca 1.4.253",
  "scope": "project",
  "machine": null,
  "verification": "observed",
  "environment": "Orca 1.4.253, padre Claude Code en una terminal de Orca con el cambio en un worktree manual",
  "recheck": "Al actualizar Orca o si `worker-start` cambia sus selectores de `--worktree`",
  "created_at": "2026-11-08T13:55:00.853924Z",
  "updated_at": "2026-11-08T13:55:00.853924Z"
}
---
`orchestration worker-start --worktree current` lanza el worker en el workspace de Orca de la sesión. Si el padre trabaja en otro checkout, por ejemplo un worktree manual de otro repositorio, `current` apunta al proyecto equivocado. En la primera revisión real, `orca worktree current` devolvió el workspace de otro repositorio mientras el PR vivía en un worktree manual.

`--worktree path:<checkout>` resolvió el worktree manual porque Orca ya conocía su repositorio. `orca worktree show --worktree path:<checkout> --json` lo confirma sin efectos antes de lanzar. Desde 0.18.0, `revisa` y la puntuación de `ui-design` usan `path:` con el checkout revisado, y `dirige` lo usa cuando el padre trabaja fuera del workspace de la sesión (references/runtime-tools.md, skills/revisa/references/reviewers.md, skills/ui-design/references/scoring.md).

Sin comprobar: qué hace `path:` con un checkout de un repositorio que Orca no tiene registrado.
