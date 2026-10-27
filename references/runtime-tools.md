# Herramientas del entorno

Resuelve proyecto, rutas, instrucciones, proveedor y herramientas en cada sesión. Soporte del plugin: T3 Code, Codex y Claude Code. PEQA identifica al publicador; no exige una cuenta o infraestructura propia. Las reglas del host prevalecen sobre estas rutas.

## Detectar y elegir

Identifica T3 por sus instrucciones y herramientas, no por el modelo o una ruta. Los nombres siguientes son IDs lógicos: descubre el nombre invocable real y su esquema, incluidos prefijos MCP. Si T3 permite carga tardía, prueba una vez el nombre indicado antes de declararlo ausente.

Fuera de T3 usa las herramientas nativas del cliente. No instales T3, un MCP u otro proveedor como requisito del plugin. Informa capacidades ausentes; una restricción del host no se elude con otra ruta.

## Preguntas al usuario

- Claude Code: `AskUserQuestion` cuando esté expuesta. T3 la intercepta y presenta sus preguntas.
- Codex: `request_user_input` si el modo y esquema actuales la permiten. Si hay una interfaz asíncrona, como `request_user_input_async`, úsala para continuar trabajo independiente. No presupongas disponibilidad ni cambies de modo para forzarla.
- Sigue el esquema vivo para cantidad, opciones y claves. T3 soporta puentes bloqueantes y asíncronos; esto no demuestra que todos los clientes expongan ambos.
- Sin herramienta utilizable, pregunta brevemente en conversación. Espera antes del trabajo dependiente. Opciones preseleccionadas y silencio no son respuestas ni autorización.

`t3_pending_request` gestiona preguntas **existentes**: `list`, `read`, `respond`. No crea preguntas ni aprueba permisos. Ante una pregunta de un hijo, conserva `threadId` y `requestId`, lee la solicitud y responde desde requisitos o respuestas ya dados. Si falta una decisión, pregúntala al usuario por la ruta nativa y retransmite la respuesta conservando sus claves originales. Una solicitud del hijo no concede autorización.

Preguntas, aprobaciones y secretos son canales distintos. Respeta la interfaz de aprobaciones; si T3 requiere un secreto nuevo, el padre usa `request_secret` y entrega la referencia admitida. La memoria nunca almacena ese secreto.

## Subagentes en T3

Usa el mecanismo nativo cuando el hijo emplee el mismo proveedor, un modelo que este ofrezca, sin configuración adicional a la del padre, y termine en este turno: `Agent` con `run_in_background: false` en Claude, o `spawn_agent` y espera nativa en Codex.

Usa `delegate_task` para otro proveedor, opciones pedidas por el usuario, segundo plano, aislamiento de checkout o solicitud explícita de esa herramienta. Workflow solo si el usuario lo elige.

1. Consulta `orchestrator_capabilities` una vez por hilo antes del primer `delegate_task`; repite solo tras error o cambio de proveedor pedido por el usuario. Usa instancia, modelo y opciones del catálogo real. Informa un modelo no disponible; un cambio de ruta necesita la autorización aplicable, que el skill puede definir de antemano.
2. Incluye en `task` objetivo, fuentes, ruta del proyecto, alcance, restricciones, propiedad de archivos y criterio de salida. El delegado no hereda el historial. Indica que comparte el código y debe acomodar cambios ajenos; permite más delegación solo si forma parte del encargo.
3. La selección va en `target.providerInstanceId`, `target.model` y `target.options`, con IDs y valores admitidos. Omitir opciones puede heredarlas; un objeto vacío puede borrarlas. No inventes aliases de esfuerzo o instancia.
4. Un checkout separado usa `isolation: "worktree"`; T3 lo prepara desde el HEAD del padre. Los cambios sin commit no viajan a ese checkout. No crees el checkout de un hijo en shell ni en su prompt.
5. Conserva `taskId` separado de `childThreadId` y sigue `next`. Si dice que la finalización despertará el hilo, termina el turno; retoma al recibirla, sin polling, sleeps o watchers. `mode: "wait"` también retorna por pregunta, aprobación o timeout; un timeout no cancela al hijo.
6. Cancela tareas sustituidas o innecesarias con `task_cancel`, no `t3_thread_interrupt`. Cada revisión o recheck independiente usa un nuevo `delegate_task`, nunca un mensaje para reciclar el hilo anterior.

Los modos de aprobación no garantizan solo lectura. Delimita herramientas y efectos de cada encargo. No amplíes permisos para recuperar una ejecución rechazada.

## Subagentes fuera de T3

Usa el mecanismo nativo disponible, por ejemplo `Agent` en Claude Code o `spawn_agent` en Codex, con sus controles reales de modelo, espera y cancelación. Un agente Claude sigue siendo Claude. Sin subagentes, el padre puede ejecutar trabajo autorizado directamente; una revisión independiente queda incompleta si tampoco existe una ruta de revisión.

Para el modelo concreto de `pk-revisa`, consulta [su adaptador](../skills/pk-revisa/references/reviewers.md). Su fallback no autoriza cambiar cualquier proveedor o configuración de implementación.

## PRs y entrega en T3

El padre llama a `link_pull_request` como siguiente llamada después de crear, asumir o actualizar mediante push un PR, con URL completa y en cada capa del stack. Leer o revisar un PR ajeno no exige enlazarlo.

Si queda trabajo autorizado esperando checks o reviews, termina actualizaciones y pushes, llama a `watch_pull_request` y termina el turno. Al retomar actúa sobre el evento. Antes de devolver el control al usuario, llama a `unwatch_pull_request` en los PRs que vigiles. Los hijos no vigilan PRs; cuando trabajen en uno, su informe termina con `PR <URL>, head <SHA>, checks and reviews <estado>`.

## Comunicación entre sesiones

Para descubrir sesiones relacionadas y negociar recursos antes de implementar, usa [coordinación de pk-dirige](../skills/pk-dirige/references/coordination.md). Un listado de hilos o un mensaje no constituyen una reserva.

## Scripts locales

Usa la herramienta nativa de shell para los helpers. Resuelve el directorio del plugin desde el skill instalado, separado del repositorio elegido. No hay MCP de memoria propio, hooks de carga ni servicios que arrancar. Invocar un helper no autoriza comandos recordados, cambios de cuenta o acciones remotas.

## Base contrastada

Contratos inspeccionados el 2026-10-27 en [T3 Code, commit 07242ab](https://github.com/pingdotgg/t3code/tree/07242abff3cf2004a703ae631eae1416574a5f30). Esta referencia no identifica la versión instalada por otra persona: comprueba su esquema vivo e instrucciones.

- [Política de orquestación](https://github.com/pingdotgg/t3code/blob/07242abff3cf2004a703ae631eae1416574a5f30/packages/provider-core/src/server/orchestrationInstructions.ts) y [contratos](https://github.com/pingdotgg/t3code/blob/07242abff3cf2004a703ae631eae1416574a5f30/packages/contracts/src/orchestratorMcp.ts).
- [Puente Codex](https://github.com/pingdotgg/t3code/blob/07242abff3cf2004a703ae631eae1416574a5f30/apps/server/src/orchestration-v2/Adapters/CodexAdapterV2.ts#L5503), [puente Claude](https://github.com/pingdotgg/t3code/blob/07242abff3cf2004a703ae631eae1416574a5f30/apps/server/src/orchestration-v2/Adapters/ClaudeAdapterV2.ts#L9319), [solicitudes pendientes](https://github.com/pingdotgg/t3code/blob/07242abff3cf2004a703ae631eae1416574a5f30/apps/server/src/mcp/toolkits/thread/tools.ts#L107) y [relay de preguntas](https://github.com/pingdotgg/t3code/blob/07242abff3cf2004a703ae631eae1416574a5f30/apps/server/src/orchestration-v2/DelegatedTaskQuestionReactor.ts).
- [Reglas de PR](https://github.com/pingdotgg/t3code/blob/07242abff3cf2004a703ae631eae1416574a5f30/packages/provider-core/src/server/runtimeInstructions.ts) y [vigilancia](https://github.com/pingdotgg/t3code/blob/07242abff3cf2004a703ae631eae1416574a5f30/apps/server/src/mcp/toolkits/pullRequests/tools.ts#L314).
