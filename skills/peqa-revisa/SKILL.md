---
name: peqa-revisa
description: Use when independent code review is requested, peqa-dirige reaches a review gate, or fixes on an existing PR need adversarial rechecking within its remaining review budget.
---

# PEQA revisa

Revisión adversarial por defecto: un revisor independiente intenta refutar que el cambio cumple su objetivo. El padre contrasta sus afirmaciones y decide. Modelo preferido exacto: **`gpt-6.1-sol`, esfuerzo `xhigh`**. La alternativa autorizada es un subagente del motor actual, con identidad y esfuerzo efectivos declarados.

**Máximo tres CR por PR en total**, contando la primera revisión y las comprobaciones posteriores, entre todos los agentes, pushes, fallbacks y reanudaciones. Una ejecución iniciada consume una pasada aunque falle o se cancele. Una capacidad descartada antes de iniciar no la consume. Los revisores no crean otros revisores.

Completa la comprobación de capacidades antes de reservar. La reserva marca el inicio del intento; desde ese momento se conserva su consumo aunque falle la admisión o se cancele el envío. No hay reembolsos de pasadas.

## Contrato y presupuesto

El padre fija objetivo original, alcance, base, revisión exacta, requisitos y resultados de checks. Identifica el PR por su URL completa: host, repositorio destino y número; un número solo no basta entre forks. Consulta el registro del PR o del cambio previo a su creación y reserva una pasada antes de iniciar al revisor. Usa el [controlador de presupuesto](references/budget.md), que comparte estado entre worktrees locales. Conserva el registro en los handoffs. Un historial desconocido no equivale a cero.

Si ya se usaron tres pasadas, el padre verifica los cambios y ejecuta checks pertinentes sin iniciar una cuarta revisión. Informa qué evidencia cubre el estado final y qué quedó sin revisión independiente. El agotamiento del presupuesto no es aprobación.

## Una pasada

1. Selecciona la ruta de [modelos y runtime](references/reviewers.md). Solicita Sol 6.1/xhigh; no lo cambies por otra versión ni rebajes su esfuerzo silenciosamente. Si la ruta no puede ejecutarlo, utiliza el fallback autorizado y decláralo. Un intento fallido seguido de otro revisor son dos ejecuciones del presupuesto.
2. Da al revisor un contexto fresco con fuentes originales, requisitos, diff/base/head, archivos nuevos y checks observados. Mantén sus primeras conclusiones independientes de la defensa del autor. Su encargo es solo lectura: devuelve hallazgos al padre; no edita, publica comentarios, crea revisiones en GitHub, empuja cambios ni delega.
3. Pide únicamente defectos materiales del alcance: incumplimiento de requisitos, comportamiento incorrecto, regresiones o riesgos concretos de datos, seguridad y concurrencia. Cada hallazgo incluye ID estable, severidad, archivo/línea, evidencia, condiciones, impacto y corrección mínima. Omite nitpicks, preferencias de estilo y sugerencias sin impacto demostrado. Cero hallazgos es válido.
4. El padre clasifica cada hallazgo como aceptado, descartado o no resuelto con una razón basada en evidencia. Descarta duplicados, afirmaciones refutadas y ampliaciones que no atiendan el objetivo. Una condición poco frecuente no invalida un impacto material. Un único editor aplica los cambios aceptados y comprueba su comportamiento.
5. Inicia otra pasada solo si queda presupuesto y cambios de comportamiento o hallazgos materiales justifican una comprobación independiente. Dirige esa pasada a cambios y hallazgos abiertos. Evita debates entre agentes: una réplica repetida sin evidencia nueva termina como desacuerdo explícito para el padre.

## Entrega

Devuelve al padre o al usuario el veredicto, hallazgos materiales, decisiones del padre, checks, revisión cubierta, modelo/esfuerzo solicitados y efectivos, ruta, fallback si lo hubo y contador `CR n/3`.

Los resultados permanecen en el informe y registro local. Este skill no publica comentarios ni reviews en GitHub, incluidos comentarios de seguimiento o respuestas a bots. Las correcciones cosméticas, de formato o documentación sin cambio de comportamiento no disparan otra pasada.
