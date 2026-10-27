---
name: peqa-idea
description: Use when an idea, feature, plan or technical approach needs challenging, product or implementation decisions are materially unresolved, or peqa-dirige needs clarification before dependent work.
---

# PEQA idea

Cuestiona la idea desde producto e implementación para producir una decisión ejecutable. Usa **como máximo tres rondas de preguntas por iniciativa**, incluida cualquier aclaración o confirmación que abra nuevas decisiones. Puede terminar antes. Conserva el contador al reanudar o cuando otro padre llame el skill para la misma iniciativa.

Identifica la iniciativa por su objetivo y brief. Cambiar de agente, rama, archivo o nombre no crea una iniciativa nueva; un objetivo distinto debe venir del usuario.

## Preparar

Consulta el estado del [registro opcional de uso](../../references/usage.md) sin activarlo. Si el usuario ya lo habilitó y el entorno permite escribir, registra esta invocación con su ID y resultado.

Lee lo que el usuario ya decidió y el contexto accesible: producto, usuarios, comportamiento actual, restricciones y código relevante. Busca los hechos que puedas comprobar; reserva las preguntas para decisiones del usuario. Una exploración pendiente no convierte una conjetura en un hecho. Si ayuda, el padre puede delegar investigación acotada sin trasladar al usuario preguntas que el proyecto permite responder.

Identifica las decisiones que cambian el resultado y sus dependencias. Revisa ambos lados:

- Producto: problema, usuario, resultado esperado, límites y criterios de aceptación.
- Implementación: contratos, datos, permisos, arquitectura existente, integración, errores, despliegue y forma de comprobar el resultado, solo donde afecten este caso.

## Preguntar por rondas

Presenta juntas pocas decisiones relacionadas que ya puedan responderse. Deja las que dependan de una respuesta abierta para una ronda posterior. Encabeza `Ronda n/3`. Cada pregunta contiene el contexto mínimo, opciones cuando ayuden y una recomendación razonada basada en el contexto actual. Señala el costo o consecuencia que hace relevante la elección.

Antes de preguntar o encargar investigación, lee las ramas de preguntas y subagentes de [herramientas del entorno](../../references/runtime-tools.md). En T3 las preguntas nuevas usan la interfaz nativa del proveedor; `t3_pending_request` solo gestiona solicitudes existentes. Espera respuestas antes del trabajo dependiente. Una opción preseleccionada o el silencio no son respuesta ni autorización. Responder una duda sin abrir nuevas decisiones no añade una ronda; volver a preguntar sí.

Después de cada respuesta actualiza decisiones y recomendaciones. No prolongues la entrevista para agotar el presupuesto ni para recorrer temas que no cambian la solución. Si la petición ya está clara y autorizada, devuelve el brief directamente sin pedir aprobación redundante.

## Cerrar

Al resolver las decisiones materiales o alcanzar la tercera ronda, entrega un brief corto: objetivo, alcance, decisiones de producto, enfoque técnico, alternativas descartadas con su razón, criterios de aceptación, supuestos y pendientes materiales.

Después de tres rondas no abras una cuarta mediante otra etiqueta, otro agente o una nueva invocación. Recomienda supuestos reversibles para detalles ordinarios. Si falta una decisión que cambie materialmente el resultado o una autorización necesaria, marca esa parte como pendiente y limita el siguiente paso a trabajo independiente; no inventes consentimiento ni ejecutes la operación pendiente.

Devuelve el brief al padre para que continúe dentro de lo ya autorizado. Este skill define decisiones; no inicia implementación, workflows ni swarms por sí mismo.
