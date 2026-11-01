# Interfaz de producto

La gente llega a las pantallas de una app para hacer algo, y lo familiar le ayuda. Los controles se comportan como se espera: controles de formulario estándar, acciones principales donde las pone la plataforma y una navegación estable. La identidad vive en la tipografía, el color, la densidad y los textos.

## Estados

Diseña cada estado posible de la pantalla con los componentes del sistema: vacío, cargando, error, datos parciales y desbordamiento, como nombres largos, cero elementos o diez mil. Una pantalla vacía invita a la primera acción. Un error dice qué pasó y cómo arreglarlo, y se queda junto a lo que lo causó; un aviso pasajero (toast) sirve para confirmar lo que salió bien.

## Densidad y datos

Ajusta la densidad a quien usa la herramienta. Quien vive en ella quiere tablas densas y atajos de teclado; quien la usa de vez en cuando quiere menos opciones por pantalla.

- Los números usan `font-variant-numeric: tabular-nums`, las columnas numéricas se alinean a la derecha y las unidades van en el encabezado de la columna.
- Las tablas largas mantienen visible el encabezado al desplazarse, y las columnas de texto se alinean a la izquierda.

## Gráficas

Una gráfica lleva su nombre como título, y sus marcas, ejes y leyenda cargan el significado. El periodo seleccionado puede ser ese título. Si una gráfica necesita instrucciones para leerse, cambia su codificación.

## Temas

Si el producto tiene modo oscuro, da a cada rol semántico un valor oscuro elegido para ese tema y vuelve a comprobar el contraste. Las paletas claras invertidas suelen fallar en acentos y sombras.

## Movimiento

Aquí el movimiento responde a acciones: abrir, expandir, confirmar, reordenar. Las duraciones salen de los tokens de movimiento y son cortas, normalmente de 100 a 250 ms.
