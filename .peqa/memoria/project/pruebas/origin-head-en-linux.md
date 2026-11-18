---
{
  "schema_version": 1,
  "id": "origin-head-en-linux",
  "title": "En Linux, Git registra origin/HEAD al traer el remoto: no es una rama publicada",
  "category": "pruebas",
  "tags": [
    "ci",
    "git",
    "linux"
  ],
  "source": "PR #27 de peqa-ai/peqa-workflows, run 44387764463 (2026-11-18)",
  "scope": "project",
  "machine": null,
  "verification": "observed",
  "environment": "Git de ubuntu-latest en GitHub Actions; el Git de macOS local no lo hizo",
  "recheck": "Si una prueba vuelve a listar refs remotas",
  "created_at": "2026-11-18T20:47:36.593467Z",
  "updated_at": "2026-11-18T20:47:36.593467Z"
}
---
En los runners de Linux, el checkout de ejemplo del banco tiene `refs/remotes/origin/HEAD` además de `origin/main` después de `git fetch`; en macOS local no aparece. Con `for-each-ref --format=%(refname:short)` esa ref se imprime como `origin`.

La aceptación del escenario `idea` comparaba las refs remotas con `["origin/main"]` para comprobar que nada se publicó, y falló en Linux sobre el proyecto sin tocar (5 pruebas de `tests/test_bench_idea.py`). En macOS pasaba.

Al comprobar refs remotas, usa `%(refname)` completo y descarta `refs/remotes/origin/HEAD`. La suite local en macOS no detecta este tipo de diferencia: solo el CI la ve.
