---
{
  "schema_version": 1,
  "id": "main-protegida-checks-por-nombre",
  "title": "main exige PR y tres checks por nombre: cambiar la matriz del CI exige actualizar la protección",
  "category": "distribucion",
  "tags": [
    "ci",
    "proteccion",
    "version"
  ],
  "source": "Sesión del 2026-11-13 y consulta en vivo de la protección el 2026-11-25; .github/workflows/ci.yml",
  "scope": "project",
  "machine": null,
  "verification": "observed",
  "environment": "GitHub, repositorio público con protección clásica de rama",
  "recheck": "Al cambiar la matriz del CI o la protección de main",
  "created_at": "2026-11-25T16:31:56.429110Z",
  "updated_at": "2026-11-25T16:31:56.429110Z"
}
---
Desde el 13 de noviembre de 2026, `main` exige PR y tres checks, también a quien administra el repositorio (`enforce_admins`):

- `tests (ubuntu-latest, Python 3.10)`
- `tests (ubuntu-latest, Python 3.x)`
- `tests (macos-latest, Python 3.x)`

Consecuencias:

- No hay push directo a `main`. Subir la versión necesita su propio PR, con su CI.
- Los checks se exigen por nombre, y el nombre sale de la matriz de `.github/workflows/ci.yml`. Si cambias el sistema, la versión de Python o el nombre del job, actualiza la protección en el mismo cambio. Sin probar aquí: según el funcionamiento de GitHub, el PR quedaría esperando un check que ya nadie informa.
- Para leer la protección sin ser administrador: `gh api repos/{owner}/{repo}/branches/main`, campo `protection`. La ruta `branches/main/protection` responde 404 a quien no administra, aunque la rama esté protegida.
