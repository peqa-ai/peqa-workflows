---
name: ui-design
description: Use when building or restyling UI, whether a landing page, a web or native app screen (SwiftUI, Jetpack Compose) or a single component, and whenever the work touches a project's design tokens, theme or component library.
---

# PEQA ui-design

Este skill diseña desde el sistema del proyecto: cada color, medida y componente tiene una sola definición, que las pantallas reutilizan, y lo propio del proyecto vive en los valores de los tokens.

Consulta el estado del [registro opcional de uso](../../references/usage.md) sin activarlo. Si el usuario ya lo habilitó y el entorno permite escribir, registra esta invocación con su ID y resultado.

Si recibiste un encargo delegado que ya trae plan visual e inventario, lee los archivos del paso 1 que correspondan y [tipografía](references/typography.md), empieza en el paso 5 y trata ese plan como decidido. Los tokens, el tema y los componentes compartidos tienen el propietario que indique el encargo; si no eres tú y necesitas cambiarlos o añadir uno, pídeselo al padre y sigue con lo que no depende de ello.

## Pasos

### 1. Encuadrar el brief

Resume en una frase de qué trata el producto, quién usará esta interfaz y qué tiene que poder hacer en ella. Si el brief no lo dice, dedúcelo del repositorio y de la memoria del proyecto. Pregunta solo cuando el host admita preguntas y la respuesta cambie el diseño; si no, declara el supuesto y continúa.

Después lee el archivo del tipo de trabajo. Una tarea mixta lee ambos.

- Página de marketing o editorial: [marketing-page.md](references/marketing-page.md)
- Interfaz de producto, como pantallas de una app, dashboards, formularios y ajustes: [product-ui.md](references/product-ui.md)

Si es una pantalla nativa en SwiftUI o Jetpack Compose, lee también [pantallas nativas](references/native.md).

Termina cuando la frase está escrita y esos archivos están leídos.

### 2. Inventariar el sistema

Localiza los tokens, el tema y los componentes del proyecto según [sistema de diseño](references/design-system.md). Elige el modo que describe: **extender** un sistema existente, **consolidar** los valores dispersos que toque la tarea o **establecer** un sistema mínimo cuando no hay ninguno.

Termina cuando puedes listar los tokens y cada componente que necesita la tarea está marcado como existente, con variante pendiente o nuevo.

### 3. Planificar la dirección

El plan cabe en una pantalla y responde cuatro preguntas:

- Qué roles de color usa la interfaz (superficie, texto, acento, borde, estados) y qué valor tiene cada uno.
- Qué familias tipográficas y qué escala. Lee [tipografía](references/typography.md) cuando elijas o cambies tipos, tamaños o pesos.
- Cómo se reparte la pantalla en teléfono y en escritorio, en un esquema de texto con la alineación de cada bloque.
- Qué elemento se recuerda, si la pantalla admite uno. Como mucho uno; el resto lo acompaña.

Cada valor indica su fuente: el brief, el sistema existente, una restricción como el contraste o un objeto del mundo del tema. Para encontrarlo, enumera tres objetos físicos o culturales de ese mundo (un mapa de senderos, una etiqueta de farmacia, un boleto), elige uno y toma de él la paleta y un recurso de layout. Al extender o consolidar, el plan usa los tokens del sistema, toma del objeto solo el recurso de layout y añade la dirección nueva como tokens, variantes o componentes nuevos.

Termina cuando cada valor tiene una fuente nombrada.

### 4. Hacer la prueba de intercambio

En pocas líneas, escribe el plan que harías para un competidor de la misma categoría. Cada valor que aparece en los dos planes es un default: sustitúyelo o justifícalo en una línea ligada a este brief. Lo que el brief fija explícitamente se conserva, aunque figure entre las [señales de UI generada](references/tells.md).

Termina cuando cada valor compartido está sustituido o justificado y puedes decir qué cambió.

### 5. Construir desde el sistema

Construye en orden: tokens, [componentes](references/design-system.md#componentes) y pantalla. Las pantallas componen componentes y usan tokens semánticos, de modo que colores, tamaños de texto, espacios y radios solo aparecen como literales en la definición de tokens. Construye ya con el [mínimo de calidad](references/critique.md#mínimo-de-calidad). Al rediseñar, conserva los [contratos invisibles](references/design-system.md#contratos-invisibles). Escribe los textos con [textos de interfaz](references/copy.md).

Anota en un comentario la fuente de cada token nuevo. Las demás pantallas existentes conservan su aspecto salvo que el cambio corrija un fallo del mínimo de calidad; cualquier otro cambio del sistema que se notaría en ellas va al informe como propuesta.

Termina cuando cada hallazgo de las [comprobaciones](references/design-system.md#comprobaciones) en los archivos modificados está corregido o justificado, o el informe declara pendiente la comprobación que no pudo ejecutarse.

### 6. Criticar

Si el entorno puede renderizar, captura con las herramientas de [evidencia visual](../../references/visual-evidence.md#screenshots) a 375 px, a 1440 px y, si la navegación colapsa, en el ancho más estrecho que aún la muestra completa, y mira cada captura. En una app en webview, como Tauri, Electron o Capacitor, esos anchos y los del mínimo de calidad son el tamaño mínimo y el típico de su ventana; una pantalla nativa sigue [sus capturas](references/native.md#capturas). Si la tarea cambia un flujo, captura también la pantalla de entrada y los resultados de éxito y de error.

Revisa el resultado con las [señales de UI generada](references/tells.md) y después con la [crítica](references/critique.md). Antes de cerrar, retira el elemento que menos aporta al encargo y anótalo en el informe.

Termina cuando cada comprobación pasa o el informe nombra lo que falta.

## Al recibir correcciones

Cuando alguien señala un caso, busca en la pantalla cada elemento con la misma estructura y corrígelos todos antes de responder. Si guardas la lección, escríbela como patrón y no como el ejemplo.

## Informe

Termina con la frase de encuadre, el modo del sistema, el plan con sus fuentes, lo que cambió la prueba de intercambio, los componentes añadidos o con variantes nuevas, cada cambio visible en pantallas existentes, el resultado de las comprobaciones y lo que retiraste.
