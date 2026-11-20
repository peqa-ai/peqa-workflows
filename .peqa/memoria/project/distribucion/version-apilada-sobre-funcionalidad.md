---
{
  "schema_version": 1,
  "id": "version-apilada-sobre-funcionalidad",
  "title": "PR de versión apilado: no borres su rama base al mezclar la funcionalidad",
  "category": "distribucion",
  "tags": [
    "manifiestos",
    "pr-apilado",
    "version"
  ],
  "source": "Sesión del 2026-11-20; PRs #30 y #31 de peqa-ai/peqa-workflows; merge de prueba y publicación de v0.24.0",
  "scope": "project",
  "machine": null,
  "verification": "observed",
  "environment": "GitHub y gh, 2026-11-20",
  "recheck": "Si GitHub empieza a cambiar la base de los PRs apilados al borrar la rama",
  "created_at": "2026-11-20T16:24:02.611617Z",
  "updated_at": "2026-11-20T20:44:52.938977Z"
}
---
El 20 de noviembre de 2026, una rama `chore/version-0.24.0` creada desde `main` chocó con el PR #30 en los tres manifiestos (merge de prueba): la línea `version` está junto a `description`, y #30 cambió la descripción al añadir un skill.

Cuando la funcionalidad toca una línea vecina de `version`:

- Lo más simple, si se publica en la misma sesión: mezclar primero la funcionalidad y crear después la rama de versión desde `main` actualizado.
- Si se apila el PR de versión sobre la funcionalidad para revisarlos juntos, no mezcles la funcionalidad con `--delete-branch`. Borrar la rama base cerró el PR apilado (#31) en lugar de cambiarle la base, y un PR cerrado no admite cambio de base. Primero `gh pr edit <n> --base main`, después `git rebase --onto origin/main <head-de-la-funcionalidad> <rama-de-versión>` y `push --force-with-lease`. Borra la rama de la funcionalidad al final.

Recuperación usada en #31: volver a subir la rama base en su commit, `gh pr reopen`, `gh pr edit --base main`, rebase, push forzado y borrar otra vez la rama base.
