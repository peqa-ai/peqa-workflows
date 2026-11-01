# Páginas de marketing y editoriales

## Primera pantalla

A 1440×900 y a 390×844, la primera pantalla dice qué es el producto y para quién, y muestra la acción principal sin scroll. Su forma sale del material del tema: si el producto se entiende mejor viéndolo funcionar, muéstralo con sus componentes reales y datos realistas; si se entiende con una frase, la frase lleva el peso. Un titular de más de dos líneas en escritorio baja de tamaño, y los logos, los precios y las listas pasan a la sección siguiente.

Para secciones de alto completo usa `min-height: 100svh`, con `100vh` declarado antes como respaldo. Un alto fijo o `100vh` solo dejan la acción bajo la barra del navegador en el teléfono.

## Layout

Cada sección toma la forma de su contenido: una comparación pide columnas alineadas, un proceso pide orden y una cita pide aire. Todas usan las primitivas de layout y la escala de espaciado del sistema, y comparten la anatomía de sección de los [componentes](design-system.md#componentes).

## Movimiento

Si la página se mueve sin que nadie actúe, que sea una sola secuencia, con un propósito que puedas nombrar en el informe y respetando `prefers-reduced-motion`. Fuera de esa secuencia, solo se mueve lo que responde a una acción.

## Textos

Una página de marketing convence con hechos: qué hace el producto, para quién y con qué resultado, en las palabras de sus clientes cuando existen. Cada cifra sale del brief o de datos reales. Si no hay dato, marca el número como ejemplo en el marcado y nómbralo en el informe como pendiente. El resto de [textos de interfaz](copy.md) sigue aplicando.

## Recursos visuales

Sin imágenes reales, la página se apoya en la tipografía y el contenido, en SVG sencillos sacados de los objetos del tema o en placeholders etiquetados con su proporción final, y el informe lista lo que el cliente debe aportar. Una vista del producto se construye con capturas reales o con los componentes del sistema y datos realistas.
