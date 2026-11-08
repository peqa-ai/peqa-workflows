# Escenarios de Orca como host

Pruebas de comportamiento de `0.18.0`, no tests ejecutables. Cada muestra corre con contexto nuevo, lee el `SKILL.md` de `dirige` o `revisa` en el checkout modificado y las referencias que alcance, y responde sin ejecutar Git, `gh`, `orca` ni `codex`. Los prompts describen el entorno y el pedido sin nombrar la conducta que se prueba. Se comparan decisiones, no palabras.

El usuario decidió el 8 de noviembre de 2026 que Orca quede al mismo nivel que T3. `dirige` delega con el criterio de T3. Dentro de Orca, `revisa` lanza al revisor Sol como worker si el CLI de Orca responde, y si no, usa la ruta de hoy.

## Casos

| Caso | Condiciones | Resultado esperado |
| --- | --- | --- |
| S1 · Hijo de otro proveedor | Claude Code en Orca, `orca status` ok, sin T3; el usuario pide que Codex implemente | Host Orca; carga `skills get orchestration`; `worker-start --agent codex --worktree current` con el encargo en `--spec-file`, sin `--keep-open`; termina el turno; PR adjunto con `reference add` |
| S2 · Mismo proveedor | Mismo entorno; dos partes independientes y pequeñas | `Agent` nativo para cada parte, en paralelo y con un editor por archivo; ningún worker de Orca para implementar |
| S3 · `revisa` en Orca | Claude Code en Orca, Codex autenticado, PR sin revisiones | Comprobaciones antes de reservar; `worker-start --agent codex --model gpt-6.1-sol --effort xhigh --worktree current`; captura de HEAD y `git status` antes y después; `CR 1/3` |
| S4 · Orca no responde | `ORCA_*` presentes, `orca status` falla | Ruta de Claude Code con `codex exec`; ninguna pasada gastada en Orca |
| S5 · T3 lanzado desde Orca | Codex con herramientas de T3 y variables de Orca | Manda T3: `delegate_task` para el hijo Claude, `link_pull_request` y watcher; nada de `reference add` |
| S6 · Entrega en Orca | Implementación integrada por un worker en el mismo checkout; CI de 10 minutos | Commit, push y PR borrador; `reference add`; `gh pr checks --watch` con límite; el worker del mismo checkout no se retira; pregunta por el merge |

## Resultado observado el 8 de noviembre de 2026

Primera ronda, seis agentes Opus con contexto fresco. Los seis eligieron la ruta esperada, con estas observaciones:

- **S3:** las pruebas que el padre corre a pedido del revisor podían cambiar `git status` e invalidar la captura de solo lectura. No quedaba claro si cargar la guía de Orca iba antes de reservar. `$REVIEW_TITLE` no estaba definido.
- **S5:** la frase de `dirige` "En Orca adjunta cada PR" no decía qué hacer cuando manda T3.
- **S1 y S6:** `runtime-tools.md` decía que un worker del mismo checkout se cierra solo y `cleanup.md` mandaba liberarlo con `worker-release`. No quedaba claro si hacían falta las dos cosas. S6 tampoco tenía un criterio para el límite de espera de los checks.
- **S2:** "aplica el criterio de T3" remitía a la sección de T3 para el mecanismo nativo concreto, y `coordination.md` omitía el prefijo del ejecutable de Orca.
- **S1:** sin `--model`, nada decía qué modelo usa el worker.

Correcciones aplicadas:

- La sección de Orca nombra el mecanismo nativo y su paralelismo.
- Sin `--model` se registra el modelo que exponga `worker-show`.
- `worker-release` es solo para workers que `worker-list` muestre abiertos.
- El límite de espera sigue lo que suele tardar el CI.
- La entrega en Orca aplica solo cuando Orca es el host.
- `revisa` carga la guía antes de reservar, usa `PR $PR_NUMBER` en el título y descuenta los archivos que generan las pruebas del padre.

Segunda ronda, con dos agentes nuevos sobre los casos corregidos:

- **S3 con `pytest` a pedido del revisor:** cargó la guía antes de reservar y lanzó el worker con `--task-title "revisa: PR 42"`. Anotó `.pytest_cache/` y `coverage.xml` como generados y dio la pasada por válida solo si ningún otro archivo cambiaba.
- **S6 con dos workers, uno en el mismo checkout y otro en un worktree nuevo:** dejó el primero cerrado. Liberó el segundo con `worker-release` y retiró su workspace con `worktree rm`, sin forzar, después de las comprobaciones de `cleanup.md`. Señaló que un CI de 25 minutos no cabe en un comando en primer plano. La regla ahora admite la ejecución en segundo plano del cliente que despierta al padre, como `run_in_background` en Claude Code; esa última redacción no se volvió a simular.

Ambigüedades anteriores a este cambio, que siguen abiertas: cuándo abrir el PR borrador si aún no hay nada que commitear, cómo verificar un historial de revisión en cero y si una revisión previa al PR se ofrece como comentario al abrirlo.

Estas simulaciones no prueban una sesión real en Orca. Esa prueba, con un padre Claude y un hijo Codex, queda pendiente antes de mezclar.
