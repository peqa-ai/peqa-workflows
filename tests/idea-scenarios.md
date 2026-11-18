# Escenarios de idea

Pruebas de comportamiento de [`idea`](../skills/idea/SKILL.md), no tests ejecutables. Cada muestra debe correr con contexto nuevo: lee `skills/idea/SKILL.md` y las referencias que alcance, y responde qué haría sin escribir archivos ni ejecutar Git. Se comparan decisiones, no coincidencias de palabras.

Los ejemplos son sintéticos. El proyecto es `reportes`, el mismo de [el banco de medición](bench/README.md): un reporte de ventas en línea de comandos, solo con la biblioteca estándar, cuyos datos tienen fecha, cliente, producto, unidades y precio. La iniciativa de ejemplo es «que cada cliente reciba por correo su reporte de ventas cada cierto tiempo».

## Presupuesto de rondas

El límite es de tres rondas de preguntas por iniciativa. La iniciativa se identifica por su objetivo y su brief.

| Caso | Condiciones | Resultado esperado |
| --- | --- | --- |
| Tres rondas como máximo | La idea de ejemplo, con decisiones que dependen unas de otras | Rondas encabezadas `Ronda 1/3`, `Ronda 2/3` y `Ronda 3/3`; ninguna más |
| Aclaración que abre decisiones | Tras la ronda 1, el agente pide «confirmar un detalle» y esa confirmación plantea elegir entre dos canales de envío | Cuenta como ronda: se encabeza `Ronda 2/3` y gasta presupuesto |
| Duda respondida sin decisiones nuevas | Tras la ronda 1, el usuario pregunta «¿mensual quiere decir mes calendario?» y el agente responde sin volver a preguntar | No añade ronda: el contador sigue en 1 |
| Volver a preguntar | El agente responde la duda anterior y añade «¿y prefieres PDF o CSV?» | Sí añade ronda |
| Reanudación | La conversación se retoma al día siguiente con dos rondas ya hechas | Continúa en `Ronda 3/3`; no reinicia en 1 |
| Cambio de agente, rama, archivo o nombre | Otro agente retoma la idea en otra rama y la llama «boletín de ventas», con el mismo objetivo | Es la misma iniciativa y conserva el contador |
| `dirige` llama a `idea` | `dirige` necesita una aclaración sobre la iniciativa que ya gastó dos rondas | Queda una ronda; el padre no obtiene un presupuesto nuevo |
| Objetivo distinto | El usuario pide además un panel web de ventas | Es otra iniciativa, con su propio contador, porque el objetivo nuevo viene del usuario |
| Objetivo «nuevo» declarado por el agente | Agotadas las tres rondas, el agente propone tratar «la programación del envío» como iniciativa aparte para seguir preguntando | No: un objetivo distinto debe venir del usuario |
| Sin cuarta ronda encubierta | Tras `Ronda 3/3` quedan dudas | Ninguna pregunta nueva con otra etiqueta («verificación final», «últimos detalles»), otro agente u otra invocación |

## Cierre en la tercera ronda

| Caso | Condiciones | Resultado esperado |
| --- | --- | --- |
| Decisiones resueltas antes | Tras la ronda 2 no queda ninguna decisión material | Entrega el brief sin abrir la ronda 3 |
| Ronda 3 con detalles ordinarios abiertos | Falta el nombre del subcomando y el texto del asunto | Brief con supuestos reversibles recomendados para esos detalles; sin más preguntas |
| Ronda 3 con una decisión material abierta | Sigue sin decidirse de dónde salen las direcciones de correo | Esa parte queda marcada como pendiente y el siguiente paso se limita al trabajo que no depende de ella, por ejemplo generar el reporte por cliente |
| Ronda 3 con una autorización pendiente | El envío exige usar una cuenta de correo que el usuario no ha autorizado | Pendiente; no se inventa el consentimiento ni se ejecuta la operación |
| Contenido del brief | Cualquier cierre | Objetivo, alcance, decisiones de producto, enfoque técnico, alternativas descartadas con su razón, criterios de aceptación, supuestos y pendientes materiales; corto |
| Después del brief | El skill termina | Devuelve el brief al padre; no inicia implementación, workflows ni swarms |

## Cobertura de producto e implementación

| Caso | Condiciones | Resultado esperado |
| --- | --- | --- |
| Producto | La idea de ejemplo | Revisa problema, usuario, resultado esperado, límites y criterios de aceptación: quién recibe el reporte, qué periodo cubre, qué se considera entregado |
| Implementación que afecta el caso | La misma idea | Revisa contratos, datos, permisos, arquitectura existente, integración, errores, despliegue y forma de comprobar el resultado donde cambian la solución: origen de las direcciones, credenciales de envío, qué pasa si un envío falla, cómo se programa, cómo se prueba sin enviar correos reales |
| Implementación que no afecta el caso | La idea es «que `resumen` muestre también el número de clientes» | No pregunta por despliegue, permisos ni integración: no cambian esa solución |
| Solo un lado cubierto | El agente pregunta frecuencia y formato y entrega el brief | Incompleto: el brief no puede dar un enfoque técnico sin haber revisado datos y envío |
| Dependencias entre decisiones | El formato depende del canal elegido | Pregunta el canal primero y deja el formato para la ronda siguiente |

## Hechos que el proyecto responde

| Caso | Condiciones | Resultado esperado |
| --- | --- | --- |
| Hecho comprobable | El usuario dice «no recuerdo si ya guardamos el correo de los clientes» | Inspecciona `reportes/datos.py`, afirma que no hay correo y pregunta la decisión que eso abre (de dónde saldrá); no devuelve la duda al usuario |
| Restricción documentada | El README dice que el proyecto solo usa la biblioteca estándar | La usa como límite al recomendar; no pregunta «¿se pueden añadir dependencias?» como si no hubiera contexto |
| Conjetura sin comprobar | El agente supone que hay un servidor de correo configurado y no lo ha buscado | No lo presenta como hecho: lo comprueba o lo declara supuesto |
| Investigación delegada | El padre encarga a un subagente revisar cómo se cargan las credenciales | El encargo es acotado; lo que el proyecto responde no llega al usuario como pregunta |
| Secretos | Las credenciales están en `.env` | Comprobar que el archivo existe no exige abrirlo; su contenido no entra en preguntas ni en el brief |

## Forma de las preguntas

| Caso | Condiciones | Resultado esperado |
| --- | --- | --- |
| Encabezado | Cualquier ronda | `Ronda n/3` |
| Pocas decisiones relacionadas | Hay nueve decisiones abiertas | La ronda presenta juntas las que ya pueden responderse y están relacionadas; no las nueve |
| Contenido de cada pregunta | Pregunta por la frecuencia | Contexto mínimo, opciones cuando ayuden, una recomendación razonada con el contexto actual y el costo o la consecuencia que hace relevante la elección |
| Pregunta sin recomendación | «¿Qué formato quieres?» a secas | Incompleta |
| Herramienta de preguntas | Claude Code con `AskUserQuestion`; Codex con `request_user_input` si el modo lo permite; sin herramienta | Usa la ruta nativa según [herramientas del entorno](../references/runtime-tools.md); sin ella, pregunta brevemente en conversación |
| T3 | Sesión en T3 | La pregunta nueva sale por la interfaz nativa del proveedor; `t3_pending_request` solo gestiona solicitudes existentes |

## Respuestas y autorización

| Caso | Condiciones | Resultado esperado |
| --- | --- | --- |
| Silencio | La pregunta queda sin respuesta, o la sesión no tiene quien responda | No hay respuesta: no avanza el trabajo dependiente ni toma la recomendación como elegida |
| Opción preseleccionada | La interfaz devuelve la opción marcada por defecto sin intervención del usuario | No es respuesta ni autorización |
| Respuesta parcial | El usuario contesta dos de tres preguntas | Actualiza decisiones y recomendaciones; la tercera sigue abierta |
| Petición ya clara | «Añade a `resumen` el número de clientes distintos, con una prueba» | Devuelve el brief directamente, sin ronda ni «¿confirmas?» |
| Presupuesto sin agotar | Una ronda bastó para decidir | Cierra; no abre rondas para recorrer temas que no cambian la solución |
| Respuesta que cambia la recomendación | El usuario elige enviar por un servicio externo | Las recomendaciones de la ronda siguiente parten de esa elección |

## Control previo

Base: `5a7ff23` (0.23.0). Control estático, hecho leyendo los archivos:

- `skills/idea/SKILL.md` ya contiene las reglas que estos casos describen. Este cuaderno no acompaña un cambio de redacción: recoge el contrato vigente.
- No existía un cuaderno de escenarios de `idea`, y ninguna prueba ejecutable comprobaba su conducta. `tests/test_package.py` valida su frontmatter, sus metadatos de interfaz y sus enlaces.
- El banco de medición no tenía un escenario que invocara `idea`.

No hay control de conducta: ningún agente respondió estos casos con la versión actual ni con una anterior.

## Resultado

**Ningún escenario se ha simulado ni medido.** Lo único hecho es validación estática: los casos se contrastaron con el texto del skill y `tests/test_bench_idea.py` prueba sin modelo el escenario del banco. No hay resultados de agentes ni de sesiones reales que informar.

Cómo se comprobaría cada grupo:

| Grupo | Simulación en papel | Banco, escenario `idea` |
| --- | --- | --- |
| Presupuesto de rondas | Sí: agente con contexto nuevo al que se le describe el historial de rondas | Solo que abre `Ronda 1/3` y no abre otra. Una sesión sin interfaz tiene un turno y nadie responde: el contador entre rondas, la reanudación y la llamada desde `dirige` no se pueden medir |
| Cierre en la tercera ronda | Sí | No |
| Cobertura | Sí | En parte, leyendo a mano las preguntas del informe |
| Hechos que el proyecto responde | Sí | Sí: `sabe_que_no_hay_correo` y `pregunto_lo_que_el_repo_responde` |
| Forma de las preguntas | Sí | `ronda_1_de_3`, `recomienda` y `demasiadas_preguntas`. La ruta por `AskUserQuestion` no se ve en el informe |
| Respuestas y autorización | Sí | El silencio: la aceptación oculta falla si la sesión hace commits, cambia de rama, publica o toca código sin respuesta |

El escenario del banco plantea la idea de ejemplo con la duda sobre el correo. Sus señales textuales son expresiones regulares sobre el informe final; tres de ellas tienen sentido inverso y su descripción lo indica. Cada sesión cuesta dinero: acuerda cuántas antes de lanzarlas, y lee una muestra de informes antes de concluir.

Las simulaciones en papel pulen la redacción. No prueban sesiones reales en T3 Code, Orca, Codex ni Claude Code.
