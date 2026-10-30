# Informe consolidado

El padre prepara el informe final después de adjudicar los hallazgos. Abre con la recomendación y la evaluación de mínimos; después presenta la evidencia. Un resultado de un subagente solo cubre su encargo y no sustituye el consolidado.

Prepara el registro estructurado, conserva la captura del estado probado y ejecuta [los validadores portables](../../../references/checks-and-hooks.md#validar-el-consolidado-y-su-evidencia) antes de entregar. El render del registro facilita conservar el encabezado y evita contradicciones entre mínimos y recomendación. Un registro válido puede recomendar cambios o declarar revisión incompleta; el helper no demuestra que los tests declarados se ejecutaron.

## Recomendación y mínimos

Evalúa cuatro criterios para el alcance revisado: requisitos acordados, validación funcional pertinente, controles de seguridad aplicables y compatibilidad de los componentes afectados. Cada criterio indica `cumple`, `no cumple`, `no verificado` o `no aplica`, con evidencia o justificación. Define los mínimos desde el encargo, las reglas del proyecto y [la revisión de seguridad](security.md); no añadas mejoras opcionales como condiciones de aprobación.

La evaluación global es `no cumple` si hay un incumplimiento material demostrado; si no lo hay pero queda evidencia material pendiente, es `no verificado`. Solo es `cumple` cuando todos los mínimos aplicables tienen evidencia suficiente. `No aplica` exige una razón y no cuenta como una comprobación aprobada. No uses puntuaciones o porcentajes inventados ni promedies un fallo de seguridad con otros resultados favorables.

| Recomendación en español | En inglés | Condición |
| --- | --- | --- |
| Aprobación sugerida | Approval recommended | Mínimos cumplidos, sin hallazgos materiales abiertos ni cobertura material pendiente. Equivale a listo dentro del alcance comprobado. |
| Cambios requeridos | Changes required | Incumplimiento material demostrado. Incluye también las comprobaciones pendientes, si las hay. |
| Revisión incompleta | Review incomplete | Falta evidencia, acceso o una revisión independiente necesaria para decidir; no se ha demostrado un incumplimiento que ya exija cambios. |

Aplica los criterios de [pruebas e impacto](validation.md). Los tests fallidos o las carencias materiales impiden sugerir aprobación. El encabezado expresa una recomendación de IA; no afirma una aprobación humana ni registra un evento `APPROVE` en GitHub.

Si hay varios PRs, muestra el estado y revisión exacta de cada uno. El consolidado exige cambios si alguno tiene un incumplimiento material; en ausencia de estos, queda incompleto si falta cobertura material en cualquier componente requerido. Un hijo aprobado no vuelve aprobado al conjunto.

## Plantilla adaptable

Usa el idioma de la conversación o del informe solicitado. Adapta Markdown a texto plano o a los campos del cliente conservando el orden: título, atribución, mínimos, alcance y motivo. Esta plantilla sirve en T3 Code, Codex y Claude Code sin herramientas de publicación.

```markdown
# Review consolidado: {recomendación}
*Generado por IA en nombre de {persona solicitante identificada}.*

**Mínimos del cambio:** {cumple / no cumple / no verificado}
**Alcance:** {repositorio o PR, base y revisión exacta; componentes incluidos}
**Motivo:** {razón principal y bloqueo o límite relevante}

| Criterio | Evaluación | Evidencia o pendiente |
| --- | --- | --- |
| Requisitos acordados | {estado} | {requisito y comprobación} |
| Validación funcional | {estado} | {pruebas pertinentes y resultado} |
| Seguridad aplicable | {estado} | {versiones, controles y cobertura} |
| Compatibilidad e impacto | {estado} | {consumidores, contratos e incertidumbre} |

## Hallazgos y decisiones
{Diagrama antes/después del cambio, si modifica comportamiento.}
{Defectos materiales, evidencia, decisión del padre y corrección mínima, cada uno con su screenshot o diagrama; o ninguno encontrado dentro del alcance.}

## Pruebas, seguridad e impacto
{Resultados por repositorio, matriz de seguridad, blast radius y limitaciones según las referencias del skill.}

## Trazabilidad
{Modelo/esfuerzo solicitados y efectivos, ruta, fallback, fuentes de evidencia y CR n/3 por PR.}
```

Resuelve la persona solicitante desde su indicación explícita o una identidad de sesión verificada. No la deduzcas del autor del PR, del último commit, de `git user.name` o de la cuenta CLI autenticada. Si no está identificada, usa `Generado por IA. Persona solicitante no identificada.` y continúa. La atribución identifica quién pidió el informe, no quién lo aprobó. En inglés usa `Consolidated review` y `AI-generated on behalf of …`, con el mismo criterio de identidad.

Sustituye todos los campos antes de entregar. Mantén el resumen breve y enlaza evidencia extensa; conserva los fallos y límites aunque el cliente solo admita texto plano.

El render del helper escapa el Markdown de los campos del registro. Inserta la [evidencia visual](../../../references/visual-evidence.md#en-el-review) en el Markdown renderizado: el diagrama del cambio al inicio de «Hallazgos y decisiones» y cada imagen o diagrama debajo de su hallazgo, identificado por su ID. El resto del texto queda igual; la copia publicable solo cambia lo que indica [Publicar en el PR](#publicar-en-el-pr).

## Publicar en el PR

El consolidado se entrega primero en la sesión. Si corresponde a un PR identificado por URL, pregunta al entregarlo si el usuario quiere publicarlo como comentario de ese PR, salvo que ya lo haya indicado. Usa [la interfaz de preguntas](../../../references/runtime-tools.md#preguntas-al-usuario). Es una autorización: no consume rondas de `idea` ni pasadas de revisión. Sin un sí explícito, el informe queda en local.

1. Prepara una copia publicable del consolidado ya adjudicado. Conserva encabezado, atribución, recomendación, mínimos, hallazgos, decisiones y evidencia técnica y visual. En «Alcance», sustituye la raíz local que escribe el render por la URL del PR y las revisiones base y head. En un repositorio público, describe un hallazgo de seguridad explotable sin detalles de explotación y propón al usuario un canal privado, como un aviso de seguridad del repositorio.
2. Publícalo con `gh pr comment "$PR_URL" --body-file "$INFORME"` y un `--attach` por imagen, según [evidencia visual en el PR](../../../references/visual-evidence.md#en-el-pr). El comentario expresa una recomendación de IA; la aprobación o la petición formal de cambios en GitHub corresponden a una persona.
3. Comprueba que el comentario existe, muestra las imágenes y no contiene rutas locales. Entrega su URL.

Ofrece de nuevo la publicación con cada consolidado posterior del mismo PR, salvo que el usuario haya pedido publicarlos todos. Responder otros comentarios o bots es un encargo aparte.
