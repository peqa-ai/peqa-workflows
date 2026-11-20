---
{
  "schema_version": 1,
  "id": "version-apilada-sobre-funcionalidad",
  "title": "Una rama de versión desde main choca con un PR que cambia la description de los manifiestos",
  "category": "distribucion",
  "tags": [
    "manifiestos",
    "pr-apilado",
    "version"
  ],
  "source": "Sesión del 2026-11-20; PRs #30 y #31 de peqa-ai/peqa-workflows; merge de prueba de chore/version-0.24.0 con la rama de #30",
  "scope": "project",
  "machine": null,
  "verification": "observed",
  "environment": "Git local y GitHub; el squash del PR apilado sin comprobar",
  "recheck": "Al mezclar #30 y #31, confirmar si el PR apilado necesitó rebase",
  "created_at": "2026-11-20T16:24:02.611617Z",
  "updated_at": "2026-11-20T16:24:02.611617Z"
}
---
El 20 de noviembre de 2026, una rama `chore/version-0.24.0` creada desde `main` dio conflicto con el PR #30 en `plugin.json`, `.claude-plugin/plugin.json` y `.codex-plugin/plugin.json` (merge de prueba). La línea `version` está junto a `description`, y #30 cambió la descripción al añadir un skill.

Si el PR de la funcionalidad toca la `description` u otra línea vecina de `version`, apila el PR de versión sobre la rama de la funcionalidad en lugar de crearlo desde `main`. Su diff queda en las cuatro líneas de versión. Si la funcionalidad no toca los manifiestos, una rama desde `main` basta, como en #26.

Sin comprobar: que GitHub cambie la base a `main` y mezcle el PR apilado con squash sin conflicto tras el squash de la funcionalidad. Si falla: `git rebase --onto origin/main <head-de-la-funcionalidad> <rama-de-versión>` y `push --force-with-lease`.
