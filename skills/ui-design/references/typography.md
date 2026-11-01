# Tipografía

## Elegir tipos

Una familia suele bastar. Una segunda entra cuando cumple un papel que la primera no puede, como los titulares o las cifras, y se distingue de ella a simple vista. Busca tipos con vínculo con el tema: su historia, su señalética, sus impresos, sus herramientas. Una app de transporte puede tomar de las grotescas de señalización; un archivo, de las fichas de catálogo.

Aplica la prueba de intercambio sobre todo a la tipografía. El primer tipo que viene a la mente para cualquier brief «distintivo» también es un default: cuando se señaló Inter, las páginas generadas convergieron en Space Grotesk. Si elegirías el mismo tipo para un competidor, elige otro.

Busca primero en las fuentes que el cliente ya tiene licenciadas y después en bibliotecas que el proyecto pueda servir, como Google Fonts, Fontshare o fundiciones de código abierto. Confirma que la licencia cubre el uso web.

## Carga

- Aloja las fuentes en el proyecto o usa el CSS del proveedor, con `font-display: swap`.
- Precarga solo el tipo que aparece en la primera pantalla.
- Prefiere una fuente variable cuando necesites varios pesos.
- Declara una pila de fallback y ajústala con `size-adjust` para limitar el salto de layout.

## Escala y medida

Los valores numéricos usan punto decimal, como en CSS.

- Construye una escala con una sola razón, cerca de 1.2 para interfaces de producto densas y de 1.25 a 1.333 para páginas editoriales, con 5 a 7 pasos guardados como tokens. Usa `clamp()` para los tamaños fluidos de display.
- La medida del cuerpo va de 45 a 75 caracteres, con 66 como objetivo. `max-width: 65ch` es un buen valor por defecto.
- El interlineado sigue a la medida y a la altura de x. El cuerpo ronda 1.4 a 1.6; las líneas largas y los tipos con altura de x grande necesitan más, y los tamaños de display se acercan a 1.0 a 1.2.

## Jerarquía

Cada nivel se distingue del siguiente por tamaño y por peso. El peso más alto queda para los títulos de sección, los de subsección y la cifra clave de la pantalla; los datos usan peso regular. Dos niveles contiguos que comparten peso necesitan un salto de tamaño claro.

Para comprobarlo, anota tamaño y peso del título de sección, el de subsección, la etiqueta de fila y el valor. Si dos niveles vecinos comparten peso y su tamaño difiere en unos 2 px o menos, la jerarquía falla.

## Titulares y etiquetas

Un titular grande es un elemento gráfico. Decide su tamaño, peso, ancho e interlineado según cómo ocupa el espacio, y pruébalo con el texto real, que cambia dónde se corta la línea. Las etiquetas van con mayúscula solo al inicio, salvo que el lenguaje propio del tema use mayúsculas, como boletos, señalética o aviación. Aplica tracking a las mayúsculas que conserves.
