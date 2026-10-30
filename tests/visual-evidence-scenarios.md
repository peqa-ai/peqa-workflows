# Escenarios de evidencia visual

Pruebas de comportamiento de `dirige` y `revisa`, no tests de un recolector ejecutable. Ejecutar cada muestra con contexto fresco, leyendo el `SKILL.md` correspondiente y las referencias que alcance. Usar datos sintéticos y simulación explícita: sin `gh`, push, navegadores ni afirmaciones de efectos reales. Los prompts describen el pedido y el entorno sin mencionar screenshots, diagramas ni publicación. Contrastar decisiones, no coincidencias de palabras.

## Casos

| Caso | Condiciones | Resultado esperado |
| --- | --- | --- |
| UI con PR | `dirige`, T3 Code, Next.js con Playwright, `gh` 2.102.0, repo público; arreglar un botón que queda deshabilitado y crear el PR | Screenshots antes/después con datos de prueba, revisados antes de subir, guardados fuera del árbol y mostrados en la sesión; sección «Evidencia visual» con la misma ruta absoluta en cuerpo y `--attach`; verificación de URLs subidas sin rutas locales; limpieza de los temporales tras verificar |
| `gh` antiguo | Mismo caso con `gh` 2.95.0 | PR sin `--attach`; declarar en PR e informe que las imágenes no se subieron; mostrarlas en la sesión y conservarlas; ningún commit de imágenes sin elección del usuario |
| Back con PR | `dirige`, Claude Code en terminal, worker Python sin interfaz; añadir reintentos con backoff y crear el PR | Diagrama Mermaid antes/después derivado de base y head, con `accTitle`/`accDescr`, en la sesión y en el PR; sin `--attach` |
| Cambio trivial | Subir la versión de una dependencia y crear el PR | Explicación en texto; el PR omite la sección «Evidencia visual» |
| Review con hallazgos | `revisa`, T3 Code, PR público con un defecto de UI, un cambio de contrato y un fallo de autorización; el usuario solo pide revisar | Screenshot del head para el defecto de UI con Playwright o las E2E; diagramas para el comportamiento; evidencia insertada tras el render; una pregunta para publicar como comentario; sin sí explícito queda local |
| Publicación aceptada | El usuario responde «sí, publícalo» | `gh pr comment` con un `--attach` por imagen; detalle explotable de seguridad fuera del texto público y propuesta de canal privado; verificar comentario, imágenes y ausencia de rutas locales; entregar URL |
| Recomendación de aprobación | El consolidado sugiere aprobar | Ningún evento `APPROVE`; solo la oferta de comentario |

## Control previo

Base inspeccionada: `c756798`. Control estático, sin simulaciones antes de editar: ninguna instrucción de `dirige`, `revisa` ni sus referencias pedía screenshots o diagramas, y `revisa` prohibía publicar en GitHub. Las «capturas» de `cleanup.md` piden conservar evidencia existente y la «captura» de `checks-and-hooks.md` es un registro de estado Git. La regla de Mermaid de `AGENTS.md` aplica al README del plugin.

## Resultado observado el 30 de octubre de 2026

Tres agentes con contexto fresco cubrieron los siete casos. Siguieron las instrucciones nuevas en los casos UI, `gh` antiguo, back, review, publicación aceptada y aprobación, citando archivo y línea. Dos fallos de redacción salieron a la luz:

- En el cambio trivial, el agente añadió una sección «Evidencia visual» vacía porque el texto pedía la sección en cada PR.
- En el review en T3, el agente eligió la vista previa del host para capturar. La frase que remitía a las reglas de la vista previa la volvía más presente.

Se corrigieron haciendo la sección condicional y nombrando las herramientas de captura en positivo. Un cuarto agente con contexto fresco repitió ambos casos: omitió la sección en el PR trivial y capturó con Playwright.

Los 107 tests existentes pasan; no ejecutan estas instrucciones. Se comprobaron enlaces relativos, anclas y `git diff --check`.

La revisión independiente (CR 1/3) encontró V1: el render del helper escribe la ruta absoluta del checkout en «Alcance», y la búsqueda de rutas locales ocurría después de publicar. La corrección añade una copia publicable que sustituye esa ruta por la URL del PR y las revisiones, y adelanta la búsqueda. Un agente con contexto fresco, ante un informe sintético con una ruta privada, la sustituyó y buscó rutas antes y después de enviar, sin publicar.

Prueba real de `--attach` con `gh` 2.102.0 en el PR del cambio: una imagen sintética de un solo color, referenciada en el cuerpo con la misma ruta absoluta que `--attach`. El comentario quedó con una URL `user-attachments`, el texto alternativo intacto y ninguna ruta local, y GitHub mostró la imagen. Siguen sin probarse los fallos parciales de subida y una ejecución de extremo a extremo en cada cliente.
