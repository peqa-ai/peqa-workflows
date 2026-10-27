# Presupuesto por PR

Un CR es una ejecución independiente de revisión que inicia este flujo. El máximo es tres por PR, no tres por head, agente o hilo. Las revisiones humanas y los bots ajenos no son ejecuciones que este skill inicie. Un revisor a la vez evita amplificar el presupuesto mediante conversaciones paralelas.

El padre es dueño del contador y de los informes. Los hijos no escriben el registro ni abren nuevas revisiones. El helper incluido reserva de forma atómica para evitar que dos padres locales admitan una cuarta pasada. Su estado vive bajo el `git-common-dir`, fuera de los archivos versionados del proyecto.

Usa la ruta absoluta del helper incluida en esta instalación:

```sh
python3 "$REVIEW_BUDGET_SCRIPT" inspect --repo "$REVIEW_REPO" --pr-url "$REVIEW_PR_URL"
python3 "$REVIEW_BUDGET_SCRIPT" init --repo "$REVIEW_REPO" --pr-url "$REVIEW_PR_URL" --prior-used 0
python3 "$REVIEW_BUDGET_SCRIPT" reserve --repo "$REVIEW_REPO" --pr-url "$REVIEW_PR_URL" --head "$REVIEW_HEAD"
python3 "$REVIEW_BUDGET_SCRIPT" finish --repo "$REVIEW_REPO" --pr-url "$REVIEW_PR_URL" --token "$REVIEW_TOKEN" --status completed
```

`REVIEW_BUDGET_SCRIPT` apunta a `scripts/review_budget.py` de este skill. `REVIEW_PR_URL` es la URL web HTTPS completa, por ejemplo `https://github.com/equipo/proyecto/pull/42`. El helper acepta ese formato también en hosts GitHub Enterprise; normaliza host, propietario/repositorio, puerto HTTPS por defecto y slash final, y descarta query/fragment. Guarda la URL canónica y deriva una identidad con SHA-256. Hosts o repositorios distintos mantienen contadores distintos. Otros formatos de proveedor requieren un adaptador antes de usar este controlador; no los reduzcas a un número.

La inicialización requiere un conteo anterior verificado. Usa cero únicamente si sabes que todavía no se inició ninguna revisión de ese cambio. Los estados `failed` y `cancelled` conservan el consumo de la reserva.

Antes de crear el PR usa una identidad estable como `change-feature`. Cuando exista el PR, inicializa su identidad con el historial de revisiones propias de ese PR y une los registros para conservar ambos consumos:

```sh
python3 "$REVIEW_BUDGET_SCRIPT" attach --repo "$REVIEW_REPO" --pr-url "$REVIEW_PR_URL" --from-id change-feature
```

Los aliases anteriores deben redirigir al mismo contador y no pueden reasignarse a otro PR. Si un alias heredado resuelve a `pr-N`, primero migra esa identidad a su URL probada; `attach` no sustituye la migración. Una nueva rama, push, checkout o agente no lo reinicia. Guarda el informe de cada pasada y las decisiones del padre junto al registro o en la ubicación privada de artefactos del entorno. Al entregar incluye contador, URL/identidad, revisión y ruta del registro.

## Registros de un borrador anterior

Una identidad antigua `pr-42` es ambigua. El helper bloquea iniciar un PR con ese número mientras exista un registro antiguo sin asociar. Verifica a qué URL corresponde usando recibos e historial; no lo infieras del remoto predeterminado. Cuando la asociación esté probada:

```sh
python3 "$REVIEW_BUDGET_SCRIPT" migrate --repo "$REVIEW_REPO" --pr-url "$REVIEW_PR_URL" --from-id pr-42
```

La migración conserva todas las reservas, une un destino existente sin duplicar tokens y redirige la identidad antigua de forma atómica. Repetir la misma asociación es idempotente; asociarla a otro PR falla. Si el registro mezcló varios PRs o no puede identificarse, el historial queda desconocido: reconstruye los consumos con evidencia antes de continuar. No borres ni reinicies el contador para sortear ese bloqueo.

Los worktrees del mismo repositorio comparten el contador. Un clon independiente u otra computadora no comparte automáticamente ese directorio. En un handoff transmite e importa el conteo y los recibos antes de revisar; si no puedes reconstruir el historial, informa presupuesto desconocido y no inicies otro CR. No uses comentarios en GitHub para transportar el registro.
