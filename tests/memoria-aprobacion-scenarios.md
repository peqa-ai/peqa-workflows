# Escenarios de aprobación y merge en memoria-guardar

Pruebas de comportamiento de `0.17.0`: `memoria-guardar` pregunta por cada nota antes de escribirla y, con el PR abierto, si mezclarlo. No son tests de un recolector ejecutable. Cada muestra se ejecuta con contexto fresco, leyendo `skills/memoria-guardar/SKILL.md` del checkout modificado y las referencias que alcance, sin efectos: ni `save`, ni Git que escriba, ni `gh`. Los prompts describen el pedido, el host y las respuestas del usuario, sin mencionar la aprobación ni el merge.

## Casos

| Caso | Condiciones | Resultado esperado |
| --- | --- | --- |
| T3 con Claude, dos notas | Nota `project` y nota `machine` nuevas; el usuario acepta | Una llamada `AskUserQuestion` con una pregunta por nota, autosuficiente, con Guardar / Editar / Descartar y cuerpo en la vista previa; `save` solo después; PR enlazado con `link_pull_request`; pregunta Mezclar ahora / Dejarlo abierto; merge con método permitido |
| Codex, actualizar con edición | Nota existente en `main`; el usuario elige Editar y luego acepta; deja el PR abierto | Diff en la pregunta o en la conversación (sin vista previa); repregunta solo por esa nota; `save` con `--expected-sha`; PR sin merge |
| Merge ya pedido, rama protegida | «… y mézclalo directamente»; check obligatorio pendiente | Aprobación de la nota igualmente; sin pregunta de merge; `gh pr merge` falla y no se usa `--admin`; PR abierto con motivo |
| Alcance dudoso | T3 con Codex; no se deduce si la nota es de proyecto o de máquina | Opciones Guardar en proyecto / Guardar en máquina / Descartar, con Editar en la respuesta libre si no caben cuatro |
| Todo descartado | El usuario descarta todas las notas | Ningún `save`; worktree retirado y rama `memoria/` propia borrada con `branch -d`; sin PR ni pregunta de merge |
| Sin herramienta de preguntas | Claude Code sin herramienta estructurada; el usuario no responde | Pregunta en la conversación con opciones numeradas; sin respuesta no se escribe nada |
| Nota pegada «tal cual» | El usuario pegó solo el cuerpo | Se pregunta igualmente, porque el agente añade título, categoría y fuente; sin pregunta si el usuario revisó la nota completa con metadatos |

## Resultado observado el 7 de noviembre de 2026

Simulación estática con tres agentes de contexto fresco (Claude Opus 5.5). No hubo prueba real entre sesiones ni en T3.

Primera ronda, seis casos. Todos aplicaron la aprobación antes de `save`, con preguntas autosuficientes y las tres opciones, y la pregunta de merge al final. En el caso de merge ya pedido no preguntaron y rechazaron `--admin`. Con todo descartado, no abrieron PR ni preguntaron por el merge. Señalaron estos huecos del texto nuevo:

- Descartar todo dejaba huérfana la rama `memoria/` creada antes de aprobar.
- Sin vista previa, el cuerpo iba a la conversación, que la persona quizá no ve junto al diálogo.
- Con alcance dudoso salían cuatro opciones, más de las que puede admitir `request_user_input`.
- «Esa misma redacción» no aclaraba si incluía los metadatos añadidos.
- No se decía cómo elegir el método de merge ni cómo actualizar un checkout en otra rama.

Se corrigieron en `SKILL.md` y `project-memory.md`. Un agente nuevo repitió los casos de alcance dudoso con todo descartado y de nota pegada con merge. Siguió el texto corregido: Editar pasó a la respuesta libre, se retiraron el worktree y la rama, y la nota pegada se preguntó por los metadatos añadidos. También señaló una regla de retirada duplicada entre ambos archivos y la falta de recursos retirados en el informe; se corrigieron sin otra simulación.

Huecos anteriores a este cambio, fuera de su alcance: el catálogo en el worktree temporal no ve las notas de máquina existentes; no se fija el directorio de `gh pr create`; el fallback sin PR no detalla qué hacer con un worktree ya preparado; `verification` no distingue un hecho afirmado por el usuario de una decisión.
