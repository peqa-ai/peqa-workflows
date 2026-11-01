---
name: ui-design
description: Use when building or restyling web UI, whether a landing page, an app screen or a single component, and whenever the work touches a project's design tokens, theme or component library.
---

# PEQA ui-design

Este skill diseña desde el sistema del proyecto. Cada color, medida y componente tiene una sola definición, y las páginas la reutilizan en lugar de recrear botones o estilos. Lo propio del proyecto se expresa en los valores de los tokens y, si la pantalla lo admite, en un elemento que se recuerde. La estructura del sistema sigue convenciones para que otros puedan extenderla.

Consulta el estado del [registro opcional de uso](../../references/usage.md) sin activarlo. Si el usuario ya lo habilitó y el entorno permite escribir, registra esta invocación con su ID y resultado.

Si recibiste un encargo delegado que ya trae plan visual e inventario, lee el archivo del tipo de trabajo del paso 1 y [tipografía](references/typography.md), empieza en el paso 5 y trata ese plan como decidido. Los tokens, el tema y los componentes compartidos tienen el propietario que indique el encargo; si necesitas cambiarlos o añadir uno y no eres ese propietario, pídeselo al padre y sigue con lo que no depende de ello.

## Pasos

### 1. Encuadrar el brief

Resume en una frase de qué trata el producto, quién usará esta interfaz y qué tiene que poder hacer en ella. Si el brief no lo dice, dedúcelo del brief, del repositorio y de la memoria del proyecto. Pregunta solo cuando el host admita preguntas y la respuesta cambie el diseño; si no, declara el supuesto y continúa.

Después lee el archivo del tipo de trabajo. Una tarea mixta lee ambos.

- Página de marketing o editorial: [marketing-page.md](references/marketing-page.md)
- Interfaz de producto, como pantallas de una app, dashboards, formularios y ajustes: [product-ui.md](references/product-ui.md)

Termina cuando la frase está escrita y el archivo leído.

### 2. Inventariar el sistema

Antes de diseñar, localiza los tokens, el tema y los componentes del proyecto según [sistema de diseño](references/design-system.md). Elige el modo que describe: **extender** un sistema existente, **consolidar** los valores dispersos que toque la tarea o **establecer** un sistema mínimo cuando no hay ninguno.

Termina cuando puedes listar los tokens y cada componente que necesita la tarea está marcado como existente, con variante pendiente o nuevo.

### 3. Planificar la dirección

El plan cabe en una pantalla y responde cuatro preguntas:

- Qué roles de color usa la interfaz (superficie, texto, acento, borde, estados) y qué valor tiene cada uno.
- Qué familias tipográficas y qué escala. Lee [tipografía](references/typography.md) cuando elijas o cambies tipos, tamaños o pesos.
- Cómo se reparte la pantalla en teléfono y en escritorio, en un esquema de texto con la alineación de cada bloque.
- Qué elemento se recuerda, si la pantalla admite uno. Como mucho uno; el resto lo acompaña.

Cada valor indica su fuente: el brief, el sistema existente, una restricción como el contraste o un objeto del mundo del tema. Para encontrar esos objetos, enumera tres objetos físicos o culturales de ese mundo (un mapa de senderos, una etiqueta de farmacia, un boleto), elige uno y toma de él la paleta y un recurso de layout. En los modos extender y consolidar, el plan usa los tokens del sistema y del objeto toma solo el recurso de layout; la dirección nueva entra como valores nuevos de tokens, una variante o un componente nuevo.

Termina cuando cada valor tiene una fuente nombrada.

### 4. Hacer la prueba de intercambio

En pocas líneas, escribe el plan que harías para un competidor de la misma categoría. Cada valor que aparece en los dos planes es un default: sustitúyelo o justifícalo en una línea ligada a este brief.

Termina cuando cada valor compartido está sustituido o justificado y puedes decir qué cambió.

### 5. Construir desde el sistema

Construye en orden: tokens, componentes y página. Las páginas componen componentes y usan tokens semánticos, de modo que colores, tamaños de texto, espacios y radios solo aparecen como literales en la definición de tokens. Una diferencia necesaria se convierte en una variante en el archivo del propio componente. Cada contenedor fija el espacio entre sus hijos con `gap`, y los componentes no llevan margen exterior. Al rediseñar, conserva los [contratos invisibles](references/design-system.md#contratos-invisibles) de la página. Escribe los textos con [textos de interfaz](references/copy.md).

Anota en un comentario la fuente de cada token nuevo, para que el trabajo posterior extienda esta dirección en lugar de reinventarla. Las demás páginas existentes conservan su aspecto salvo que el cambio corrija un fallo del mínimo de calidad; cualquier otro cambio del sistema que se notaría en ellas va al informe como propuesta.

Termina cuando las [comprobaciones](references/design-system.md#comprobaciones) pasan en los archivos modificados.

### 6. Criticar

Si el entorno puede renderizar, captura con las herramientas de [evidencia visual](../../references/visual-evidence.md#screenshots) a 375 px, a 1440 px y en el ancho justo anterior al colapso de la navegación, y mira cada captura. Si la tarea cambia un flujo, captura también la pantalla de entrada y los resultados de éxito y de error. Revisa el resultado con las [señales de UI generada](references/tells.md). Después comprueba el mínimo de calidad, que se construye sin anunciarlo en los textos:

- contraste de al menos 4.5:1 para texto de cuerpo y 3:1 para texto grande y componentes de interfaz; sobre una imagen, medido en su zona más clara o más cargada
- foco de teclado visible en cada elemento interactivo
- `prefers-reduced-motion` respetado
- sin scroll horizontal a 320 px, ni anotaciones partidas que vuelvan a apilar etiqueta y valor
- a 360 y 390 px, cada título y los controles de su cabecera en la misma línea
- en teléfono, áreas táctiles de al menos 44 px de alto que no se solapan, aunque el control visible sea más pequeño
- estados hover, focus, active y disabled definidos en el componente, y loading cuando una acción espera

Haz inventario de cada texto secundario (atenuado, pequeño o calificador) y da un motivo para cada uno. «Es un dato» no es un motivo: el problema es la forma, no el contenido.

Antes de cerrar, retira el elemento que menos aporta al encargo y anótalo en el informe.

Termina cuando cada comprobación pasa o el informe nombra lo que falta.

## Principios

- Lo que el brief fija de forma explícita se respeta tal cual, aunque figure entre las señales de UI generada. Si un color del brief no alcanza el contraste en un uso, se conserva donde lo alcanza y se añade una variante para ese uso, con el contraste como fuente.
- Cada borde, número o divisor afirma algo del contenido: un orden, un grupo o un límite. Si el contenido no tiene ese orden o ese límite, el recurso sobra; la numeración, por ejemplo, queda para pasos y cronologías.
- Una etiqueta es su nombre y una cifra es su valor. El texto atenuado solo nombra marcas dentro de una gráfica: anotaciones, marcas de eje o leyenda. Lo demás pasa a un título o una etiqueta que ya existen, a la codificación de la gráfica o a un tooltip con descripción accesible, o se corta.
- Cada dato aparece una sola vez en la pantalla.
- El movimiento cuenta qué cambió después de una acción de la persona: qué se abrió, qué se movió, qué se guardó. El que nadie provocó compite con el contenido, así que necesita un propósito que puedas nombrar.

## Al recibir correcciones

Cuando alguien señala un caso, busca en la pantalla cada elemento con la misma estructura y corrígelos todos antes de responder. Si guardas la lección, escríbela como patrón y no como el ejemplo.

## Informe

Termina con la frase de encuadre, el modo del sistema, el plan con sus fuentes, lo que cambió la prueba de intercambio, los componentes añadidos o con variantes nuevas, cada cambio visible en páginas existentes, el resultado de las comprobaciones y lo que retiraste.
