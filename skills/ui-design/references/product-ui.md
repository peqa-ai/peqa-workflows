# Interfaz de producto

La gente llega a las pantallas de una app para hacer algo, y lo familiar le ayuda. Los controles se comportan como se espera: controles de formulario estándar, acciones principales donde las pone la plataforma y una navegación estable. La identidad vive en la tipografía, el color, la densidad y los textos.

## Estados

Diseña cada estado posible de la pantalla con los componentes del sistema: vacío, cargando, error, datos parciales y desbordamiento, como nombres largos, cero elementos o diez mil. Una pantalla vacía invita a la primera acción. Un error dice qué pasó y cómo arreglarlo, y se queda junto a lo que lo causó; un aviso pasajero (toast) sirve para confirmar lo que salió bien.

Un error parcial nombra la información que falló y permite reintentar ese bloque; no afirma que toda la página falló cuando el resto funciona. Distingue ausencia de datos de un cero válido: el historial, las previsiones o las referencias pueden seguir aportando información aunque el valor actual sea cero.

## Densidad y datos

Ajusta la densidad a quien usa la herramienta. Quien vive en ella quiere tablas densas y atajos de teclado; quien la usa de vez en cuando quiere menos opciones por pantalla.

- Los números usan `font-variant-numeric: tabular-nums`, las columnas numéricas se alinean a la derecha y las unidades van en el encabezado de la columna.
- Las tablas largas mantienen visible el encabezado al desplazarse, y las columnas de texto se alinean a la izquierda.

### Acciones y primera pantalla

Distribuye las acciones según sus etiquetas y su prioridad. Cuando las columnas iguales no expresan una relación útil, prueba anchos según el contenido o filas flexibles antes de partir un nombre ordinario en dos líneas. Conserva la altura base y el radio del sistema; un nombre largo puede crecer al disponer de todo el ancho, sin elevar por ello cada acción vecina. No resuelvas un reparto de ancho deficiente con elipsis, texto diminuto ni un badge: una etiqueta de estado se justifica cuando aporta un significado propio.

En móvil, revisa qué tarea y qué información quedan en la primera pantalla. Una pila sin desbordamiento puede ocuparla entera y desplazar el resumen que la persona necesita. Si las acciones secundarias dominan esa vista, muestra un subconjunto prioritario con una expansión como «Mostrar más» y su cierre. Elige la cantidad por el contenido, el espacio y la tarea; conserva las acciones críticas y el orden del dominio. Si el conjunto ya cabe con el contenido principal, déjalo visible. Comprueba ambos estados y sus [contratos de interacción](design-system.md#contratos-invisibles).

En escritorio, cuando bloques vecinos tienen alturas diferentes y no necesitan alinearse por filas, permite que cada columna apile sus bloques sin dejar huecos por la altura de la otra. Conserva el orden de lectura y teclado, también al pasar a móvil, y el estado de los controles montados.

## Gráficas

Una gráfica lleva su nombre como título, y sus marcas, ejes y leyenda cargan el significado. El periodo seleccionado puede ser ese título. Si una gráfica necesita instrucciones para leerse, cambia su codificación.

Si no hay datos, historial ni referencias significativas que representar, sustituye la gráfica por un vacío que oriente a la primera acción y retira sus títulos y leyendas sin marcas. Conserva el título del bloque. Un cero con contexto útil sigue siendo una gráfica válida.

## Temas

Si el producto tiene modo oscuro, da a cada rol semántico un valor oscuro elegido para ese tema y vuelve a comprobar el contraste. Las paletas claras invertidas suelen fallar en acentos y sombras.

## Movimiento

Aquí el movimiento responde a acciones: abrir, expandir, confirmar, reordenar. Las duraciones salen de los tokens de movimiento y son cortas, normalmente de 100 a 250 ms.
