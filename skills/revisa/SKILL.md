---
name: revisa
description: Use when independent code review is requested, dirige reaches a review gate, or fixes on an existing PR need adversarial rechecking within its remaining review budget.
---

# PEQA revisa

Revisión adversarial por defecto: un revisor independiente intenta refutar que el cambio cumple su objetivo. El padre contrasta sus afirmaciones, decide qué corregir y publica o conserva el resultado.

Antes de reservar una pasada, elige **modelo revisor** y **profundidad (`lite` o `deep`)** en una sola ronda de preguntas, salvo que el usuario ya los haya indicado en su pedido. Consulta las reglas, la recomendación inteligente con diversidad respecto al modelo de la sesión y el helper `scripts/review_plan.py` en [modelos y profundidad](references/reviewers.md). Si el entorno no es interactivo, aplica la recomendación y declárala en el informe. La alternativa autorizada ante una ruta no disponible es un subagente independiente del motor actual, declarando modelo y esfuerzo solicitados y efectivos.

**Máximo tres CR por PR en total**, contando la primera revisión y las comprobaciones posteriores, entre todos los agentes, pushes, fallbacks y reanudaciones. Una ejecución iniciada consume una pasada aunque falle o se cancele. Una capacidad descartada antes de iniciar no la consume. Los revisores no crean otros revisores.

Completa la comprobación de capacidades antes de reservar. La reserva marca el inicio del intento; desde ese momento se conserva su consumo aunque falle la admisión o se cancele el envío. No hay reembolsos de pasadas.

Consulta el estado del [registro opcional de uso](../../references/usage.md) sin activarlo. Si el usuario ya lo habilitó y el entorno permite escribir, registra esta invocación con su ID y resultado.

## Contrato, profundidad y presupuesto

El padre fija objetivo original, alcance, base, revisión exacta, requisitos, profundidad (`lite` o `deep`) y resultados de checks. Identifica el PR por su URL completa: host, repositorio destino y número; un número solo no basta entre forks. Si el usuario invoca `revisa <URL-del-PR>`, inspecciona ese PR y sigue el flujo de [revisión directa por URL de PR](references/report.md#revisión-directa-por-url-de-pr).

Consulta el registro del PR o del cambio previo a su creación, reserva una pasada registrando `--depth lite|deep` y el modelo solicitado, y admite su despacho una única vez con `claim`, según el [controlador de presupuesto](references/budget.md), que comparte estado entre worktrees locales. Conserva el registro en los handoffs. Un historial desconocido no equivale a cero.

- **`lite`**: valida requisitos funcionales, defectos materiales, regresiones, casos borde y cobertura de pruebas. Omite la auditoría completa OWASP Top 10 / NIST SSDF salvo que aparezca un defecto de seguridad obvio, que sí bloquea aprobación. Recomendada para cambios pequeños, de bajo riesgo y directos.
- **`deep`**: revisión adversarial completa. Incluye todo lo de `lite` más [seguridad aplicable al cambio](references/security.md) (OWASP Top 10 y NIST SSDF contrastados en fuentes oficiales, autenticación, autorización y aislamiento de tenants, concurrencia y condiciones de carrera, integridad de datos, secretos y dependencias) y análisis completo de impacto. Recomendada para backend, autenticación, dinero o contabilidad, migraciones, cambios multirrepositorio o alto riesgo.

En toda revisión (`lite` y `deep`), aplica [pruebas y blast radius](references/validation.md): descubre los tests disponibles, haz que el padre ejecute los pertinentes y evalúa consumidores, datos e integración afectados. Si hay submódulos, carga [revisión del conjunto](../../references/submodules.md#revisar-el-conjunto); el diff del padre no sustituye los diffs y la evidencia de sus hijos.

Si ya se usaron tres pasadas, el padre verifica los cambios y ejecuta checks pertinentes sin iniciar una cuarta revisión. Informa qué evidencia cubre el estado final y qué quedó sin revisión independiente. El agotamiento del presupuesto no es aprobación.

## Una pasada

1. Resuelve modelo y profundidad con [modelos y runtime](references/reviewers.md). Presenta en una sola pregunta las cuatro opciones de modelo (**Astra 6.2**, **Opus 5.5**, **Neon 4**, **Sol 6.2**) y las dos profundidades (`lite`, `deep`), con la recomendación primero y diversificando respecto al modelo de la sesión cuando el host lo exponga. Si el usuario ya especificó ambos, no preguntes. No sustituyas silenciosamente el modelo elegido ni rebajes su esfuerzo; si la ruta falla antes de iniciar, usa el fallback autorizado y decláralo. Un intento iniciado que falla seguido de otro revisor son dos ejecuciones del presupuesto.
2. Da al revisor un contexto fresco con fuentes originales, requisitos, profundidad (`lite` o `deep`), diff/base/head, archivos nuevos, mapa de repositorios, mapa de `blast_radius.py` y pruebas observadas o pendientes ligadas a esa revisión. Mantén sus primeras conclusiones independientes de la defensa del autor. Su encargo es solo lectura: descubre pruebas, analiza el impacto y solicita al padre las ejecuciones que falten; no edita, publica comentarios, crea revisiones en GitHub, empuja cambios ni delega.
3. Pide únicamente defectos materiales del alcance: incumplimiento de requisitos, comportamiento incorrecto, regresiones o riesgos concretos de datos, seguridad y concurrencia. Cada hallazgo incluye ID estable, severidad (`critical`, `high`, `medium`, `low`), `archivo:línea`, evidencia, condiciones, impacto, corrección mínima y la pantalla o el flujo que lo hace visible. Omite nitpicks, preferencias de estilo y sugerencias sin impacto demostrado. Cero hallazgos es válido.
4. El padre clasifica cada hallazgo como aceptado, descartado o no resuelto con una razón basada en evidencia. Descarta duplicados, afirmaciones refutadas y ampliaciones que no atiendan el objetivo. Una condición poco frecuente no invalida un impacto material. Un único editor aplica los cambios aceptados y comprueba su comportamiento. El padre prepara la [evidencia visual](../../references/visual-evidence.md#en-el-review) del cambio y de los hallazgos materiales del consolidado.
5. Inicia otra pasada solo si queda presupuesto y cambios de comportamiento o hallazgos materiales justifican una comprobación independiente. Dirige esa pasada a cambios y hallazgos abiertos. Evita debates entre agentes: una réplica repetida sin evidencia nueva termina como desacuerdo explícito para el padre.

## Entrega y publicación

El padre valida el registro estructurado (incluyendo `depth`) y su captura mediante [comprobaciones portables](../../references/checks-and-hooks.md) y genera el [informe consolidado estandarizado](references/report.md) en el idioma del usuario. Los hooks son opcionales; en Codex prioriza la ejecución directa. Incluye encabezado estandarizado (PR o alcance, `base..head`, profundidad `lite|deep`, modelo y esfuerzo solicitados y efectivos, `CR n/3`, recomendación y evaluación de mínimos), atribución de IA, hallazgos materiales con adjudicación del padre, evidencia de pruebas, blast radius, evidencia de seguridad en `deep` (o cualquier defecto obvio en `lite`) y trazabilidad. Declara qué comportamiento se comprobó y qué sigue sin comprobar; tests ausentes, bloqueados o fallidos no se presentan como aprobados.

Destino de salida según [publicar en el PR](references/report.md#publicar-en-el-pr):

- **Si ya existe un PR para el cambio:** publica el informe estandarizado en el PR y conserva también el registro en local.
- **Si aún no existe PR:** conserva el informe estandarizado y el registro en local.
- **Si se invocó directamente con una URL de PR (`revisa <link-del-PR>`):** publica una única revisión de GitHub (`COMMENT`) con el informe general estandarizado y comentarios en línea (`path:line`) en cada línea exacta del diff que falle validaciones, listando en el resumen general los hallazgos que caigan fuera del diff.

Reglas de seguridad al publicar: usa siempre revisiones de solo comentario (`COMMENT`; nunca `APPROVE` ni `REQUEST_CHANGES` automáticos salvo que el usuario lo pida de forma expresa). En repositorios públicos, nunca publiques detalles de explotación de vulnerabilidades de seguridad; redacta el impacto sin vector de ataque y propón un aviso privado de seguridad del repositorio. Las correcciones cosméticas, de formato o documentación sin cambio de comportamiento no disparan otra pasada.
