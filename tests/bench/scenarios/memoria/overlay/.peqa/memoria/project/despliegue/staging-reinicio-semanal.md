---
{
  "schema_version": 1,
  "id": "staging-reinicio-semanal",
  "title": "Staging se reinicia los domingos",
  "category": "despliegue",
  "tags": [
    "staging"
  ],
  "source": "Incidente del 2026-08-17",
  "scope": "project",
  "machine": null,
  "verification": "observed",
  "environment": null,
  "recheck": null,
  "created_at": "2026-11-17T17:49:30.621555Z",
  "updated_at": "2026-11-17T17:49:30.621555Z"
}
---
El servidor de staging se reinicia cada domingo a las 03:00 UTC. Un despliegue en esa ventana puede quedar a medias; hay que repetirlo después.
