# Herramientas del entorno

Resuelve proyecto, rutas, instrucciones, proveedor y herramientas en cada sesión. Soporte del plugin: T3 Code, Orca, Codex y Claude Code. PEQA identifica al publicador; no exige una cuenta o infraestructura propia. Las reglas del host prevalecen sobre estas rutas.

## Detectar y elegir

Identifica T3 por sus instrucciones y herramientas, no por el modelo o una ruta. Los nombres siguientes son IDs lógicos: descubre el nombre invocable real y su esquema, incluidos prefijos MCP. Si T3 permite carga tardía, prueba una vez el nombre indicado antes de declararlo ausente.

Identifica Orca por su entorno: la sesión corre en una terminal que Orca gestiona (`ORCA_AGENT_SESSION_ID` presente) y el ejecutable de `ORCA_CLI_COMMAND` responde a `status`. Dentro de Orca, Claude Code y Codex conservan sus herramientas nativas; Orca añade workers supervisados. Si también están las herramientas de T3, manda T3: el orden es T3, Orca y después las herramientas nativas.

Fuera de T3 y de Orca usa las herramientas nativas del cliente. No instales T3, Orca, un MCP u otro proveedor como requisito del plugin. Informa capacidades ausentes; una restricción del host no se elude con otra ruta.

## Preguntas al usuario

- Claude Code: `AskUserQuestion` cuando esté expuesta. T3 la intercepta y presenta sus preguntas.
- Codex: `request_user_input` si el modo y esquema actuales la permiten. Si hay una interfaz asíncrona, como `request_user_input_async`, úsala para continuar trabajo independiente. No presupongas disponibilidad ni cambies de modo para forzarla.
- Sigue el esquema vivo para cantidad, opciones y claves. T3 soporta puentes bloqueantes y asíncronos; esto no demuestra que todos los clientes expongan ambos.
- Sin herramienta utilizable, pregunta brevemente en conversación. Espera antes del trabajo dependiente. Opciones preseleccionadas y silencio no son respuestas ni autorización.

`t3_pending_request` gestiona preguntas **existentes**: `list`, `read`, `respond`. No crea preguntas ni aprueba permisos. Ante una pregunta de un hijo, conserva `threadId` y `requestId`, lee la solicitud y responde desde requisitos o respuestas ya dados. Si falta una decisión, pregúntala al usuario por la ruta nativa y retransmite la respuesta conservando sus claves originales. Una solicitud del hijo no concede autorización.

En Orca, un worker pregunta con `orchestration ask` y Orca despierta al padre con la pregunta. El padre responde con `orchestration reply --id <message_id>` desde requisitos o respuestas ya dados. Si falta una decisión, la pregunta al usuario por la ruta nativa y retransmite la respuesta. La pregunta del worker tampoco concede autorización.

Preguntas, aprobaciones y secretos son canales distintos. Respeta la interfaz de aprobaciones; si T3 requiere un secreto nuevo, el padre usa `request_secret` y entrega la referencia admitida. La memoria nunca almacena ese secreto.

## Subagentes en T3

Usa el mecanismo nativo cuando el hijo emplee el mismo proveedor, un modelo que este ofrezca, sin configuración adicional a la del padre, y termine en este turno: `Agent` con `run_in_background: false` en Claude, o `spawn_agent` y espera nativa en Codex.

Usa `delegate_task` para otro proveedor, opciones pedidas por el usuario, segundo plano, aislamiento de checkout o solicitud explícita de esa herramienta. Workflow solo si el usuario lo elige.

1. Consulta `orchestrator_capabilities` una vez por hilo antes del primer `delegate_task`; repite solo tras error o cambio de proveedor pedido por el usuario. Usa instancia, modelo y opciones del catálogo real. Informa un modelo no disponible; un cambio de ruta necesita la autorización aplicable, que el skill puede definir de antemano.
2. Incluye en `task` objetivo, fuentes, ruta del proyecto, alcance, restricciones, propiedad de archivos y criterio de salida. El delegado no hereda el historial. Indica que comparte el código y debe acomodar cambios ajenos; permite más delegación solo si forma parte del encargo.
3. La selección va en `target.providerInstanceId`, `target.model` y `target.options`, con IDs y valores admitidos. Omitir opciones puede heredarlas; un objeto vacío puede borrarlas. No inventes aliases de esfuerzo o instancia.
4. Un checkout separado usa `isolation: "worktree"`; T3 lo prepara desde el HEAD del padre. Los cambios sin commit no viajan a ese checkout: si el hijo los necesita, publícalos antes en un PR según [la regla de commits de dirige](../skills/dirige/SKILL.md) o delega en el mismo checkout. No crees el checkout de un hijo en shell ni en su prompt.
5. Conserva `taskId` separado de `childThreadId` y sigue `next`. Si dice que la finalización despertará el hilo, termina el turno; retoma al recibirla, sin polling, sleeps o watchers. `mode: "wait"` también retorna por pregunta, aprobación o timeout; un timeout no cancela al hijo.
6. Cancela tareas sustituidas o innecesarias con `task_cancel`, no `t3_thread_interrupt`. Cada revisión o recheck independiente usa un nuevo `delegate_task`, nunca un mensaje para reciclar el hilo anterior.

Los modos de aprobación no garantizan solo lectura. Delimita herramientas y efectos de cada encargo. No amplíes permisos para recuperar una ejecución rechazada.

## Subagentes en Orca

Aplica el criterio de T3. Usa el mecanismo nativo cuando el hijo emplee el mismo proveedor, un modelo que este ofrezca, sin configuración adicional a la del padre, y termine en este turno: `Agent` con `run_in_background: false` en Claude, o `spawn_agent` y espera nativa en Codex. Varios hijos nativos independientes se lanzan en un mismo mensaje para que corran en paralelo. Usa un worker de Orca para otro proveedor, opciones pedidas por el usuario, segundo plano o aislamiento de checkout.

1. Antes del primer worker del hilo, y antes de reservar cualquier pasada de `revisa`, carga la guía de la versión instalada con `<orca> skills get orchestration`, donde `<orca>` es el ejecutable de `ORCA_CLI_COMMAND`. Esa guía manda sobre los comandos y opciones exactos; esta sección fija qué hace el plugin con ellos. Si el ejecutable falla, informa su error y usa el mecanismo nativo.
2. Inicia cada hijo con `orchestration worker-start --agent <claude|codex>` y el encargo en `--spec-file`: objetivo, fuentes, ruta del proyecto, alcance, restricciones, propiedad de archivos y criterio de salida. El worker no hereda el historial. Indica que comparte el código y debe acomodar cambios ajenos; permite más delegación solo si forma parte del encargo. Pasa `--model` y `--effort` solo con valores que la instalación acepte y que el usuario o el skill hayan elegido. No inventes aliases. Sin `--model`, el worker usa el modelo configurado para ese agente; registra el que exponga `worker-show` o decláralo desconocido.
3. `--worktree current` comparte el checkout del padre. Un checkout separado usa `--worktree new-top-level` con la rama base que el hijo necesita. Los cambios sin commit no viajan a ese checkout: si el hijo los necesita, publícalos antes en un PR según [la regla de commits de dirige](../skills/dirige/SKILL.md) o delega en el mismo checkout. No crees el checkout de un hijo en shell ni en su prompt.
4. No uses `--keep-open`: el padre responde por el resultado y el usuario no conversa con los hijos. Un worker en el checkout del padre se cierra solo al terminar y no necesita más. Uno en un worktree nuevo, o uno que `worker-list` muestre todavía abierto, queda así hasta que el [cierre de recursos](../skills/dirige/references/cleanup.md) lo libere.
5. Conserva el `dispatch_id` de cada worker. Después de iniciarlos, termina el turno: Orca despierta al padre con `worker_done`, una pregunta o una escalada. No hagas polling ni scripts de vigilancia, y ejecuta `check` solo cuando el aviso lo indique. El silencio o un timeout no prueban que el worker terminó.
6. Cancela tareas sustituidas o innecesarias con `orchestration worker-stop --dispatch <dispatch_id>` y confirma el estado con `worker-show`: el recibo de la parada no prueba que el agente se detuvo. No dirijas un worker escribiendo en su terminal. Cada revisión o recheck independiente es un worker nuevo; `send` no recicla un worker terminado para otra pasada.

Orca no ofrece un modo de solo lectura para workers. Delimita herramientas y efectos en el encargo y comprueba el resultado. Los servidores remotos (`--on`), los DAGs de tareas y los gates se usan solo si el usuario los pide.

## Subagentes nativos

Fuera de T3 y de Orca, o cuando el criterio anterior elige el mecanismo nativo, usa el mecanismo disponible, por ejemplo `Agent` en Claude Code o `spawn_agent` en Codex, con sus controles reales de modelo, espera y cancelación. Un agente Claude sigue siendo Claude. Sin subagentes, el padre puede ejecutar trabajo autorizado directamente; una revisión independiente queda incompleta si tampoco existe una ruta de revisión.

Para el modelo concreto de `revisa`, consulta [su adaptador](../skills/revisa/references/reviewers.md). Su fallback no autoriza cambiar cualquier proveedor o configuración de implementación.

## PRs y entrega en T3

El padre llama a `link_pull_request` como siguiente llamada después de crear, asumir o actualizar mediante push un PR, con URL completa y en cada capa del stack. Leer o revisar un PR ajeno no exige enlazarlo.

Si queda trabajo autorizado esperando checks o reviews, termina actualizaciones y pushes, llama a `watch_pull_request` y termina el turno. Al retomar actúa sobre el evento. Antes de devolver el control al usuario, llama a `unwatch_pull_request` en los PRs que vigiles. Los hijos no vigilan PRs; cuando trabajen en uno, su informe termina con `PR <URL>, head <SHA>, checks and reviews <estado>`.

## PRs y entrega en Orca

Aplica cuando el host elegido es Orca; si manda T3, sigue la sección de T3. Después de crear, asumir o actualizar mediante push un PR, el padre lo adjunta al workspace con `<orca> reference add <URL> --worktree current`, en cada capa del stack. Orca no vigila checks ni reviews. Si queda trabajo autorizado esperando checks, espera con `gh pr checks <URL> --watch` dentro de un límite acorde a lo que suele tardar ese CI y actúa sobre el resultado; si no terminan, entrega con su estado pendiente. Cuando la espera supera lo que admite un comando en primer plano, usa la ejecución en segundo plano del cliente que despierte al padre al terminar, como `run_in_background` en Claude Code. No escribas scripts propios de vigilancia ni dejes procesos al devolver el control. Los hijos no adjuntan ni vigilan PRs; su informe termina igual que en T3.

## Comunicación entre sesiones

Para descubrir sesiones relacionadas y negociar recursos antes de implementar, usa [coordinación de dirige](../skills/dirige/references/coordination.md). Un listado de hilos o un mensaje no constituyen una reserva.

## Scripts locales

Usa la herramienta nativa de shell para los helpers. Resuelve el directorio del plugin desde el skill instalado, separado del repositorio elegido. No hay MCP de memoria propio, hooks de carga ni servicios que arrancar. Invocar un helper no autoriza comandos recordados, cambios de cuenta o acciones remotas.

## Base contrastada

Contratos inspeccionados el 2026-10-27 en [T3 Code, commit 07242ab](https://github.com/pingdotgg/t3code/tree/07242abff3cf2004a703ae631eae1416574a5f30). Esta referencia no identifica la versión instalada por otra persona: comprueba su esquema vivo e instrucciones.

- [Política de orquestación](https://github.com/pingdotgg/t3code/blob/07242abff3cf2004a703ae631eae1416574a5f30/packages/provider-core/src/server/orchestrationInstructions.ts) y [contratos](https://github.com/pingdotgg/t3code/blob/07242abff3cf2004a703ae631eae1416574a5f30/packages/contracts/src/orchestratorMcp.ts).
- [Puente Codex](https://github.com/pingdotgg/t3code/blob/07242abff3cf2004a703ae631eae1416574a5f30/apps/server/src/orchestration-v2/Adapters/CodexAdapterV2.ts#L5503), [puente Claude](https://github.com/pingdotgg/t3code/blob/07242abff3cf2004a703ae631eae1416574a5f30/apps/server/src/orchestration-v2/Adapters/ClaudeAdapterV2.ts#L9319), [solicitudes pendientes](https://github.com/pingdotgg/t3code/blob/07242abff3cf2004a703ae631eae1416574a5f30/apps/server/src/mcp/toolkits/thread/tools.ts#L107) y [relay de preguntas](https://github.com/pingdotgg/t3code/blob/07242abff3cf2004a703ae631eae1416574a5f30/apps/server/src/orchestration-v2/DelegatedTaskQuestionReactor.ts).
- [Reglas de PR](https://github.com/pingdotgg/t3code/blob/07242abff3cf2004a703ae631eae1416574a5f30/packages/provider-core/src/server/runtimeInstructions.ts) y [vigilancia](https://github.com/pingdotgg/t3code/blob/07242abff3cf2004a703ae631eae1416574a5f30/apps/server/src/mcp/toolkits/pullRequests/tools.ts#L314).

Orca 1.4.253 contrastado el 2026-11-08 con el `--help` de `orchestration worker-start`, `ask`, `reply`, `worker-stop`, `worker-release`, `reference add` y `worktree rm`, y con la guía `skills get orchestration` de esa versión. `worker-start` acepta `--agent`, `--model`, `--effort`, `--worktree` y `--keep-open`, y no tiene opción de sandbox. La guía de la versión instalada prevalece sobre estos datos.
