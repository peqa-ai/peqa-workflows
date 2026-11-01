# Señales de UI generada

Revisado el 2026-11-01. Las interfaces generadas repiten soluciones que aparecen sea cual sea el tema. Esta lista recoge las que hemos observado; actualízala cuando deje de coincidir con lo que ves.

Úsala después de construir, como auditoría. Cada coincidencia es una pregunta: ¿lo pedía el brief o el tema? Si es así, consérvalo y explica por qué en el informe. Si no, sustitúyelo por una elección con fuente.

## Color y superficies

- Papel crema cálido con titulares serif de mucho contraste y un acento arcilla o terracota. El acento suele rondar `#D97757`, el color de Claude, y sobre crema no llega al contraste de texto: en nuestras pruebas dio 2.77:1.
- Fondo casi negro con un solo acento eléctrico, verde ácido o bermellón.
- Degradados que decoran sin señalar nada.

## Layout

- Estética de periódico sin motivo: filetes finos, esquinas rectas y columnas apretadas.
- Todo dentro de tarjetas iguales, con el mismo radio y la misma sombra gris suave (`rgba(0,0,0,.1)`), sea cual sea su jerarquía.
- Una cifra enorme con una etiqueta pequeña, unas estadísticas debajo y un degradado detrás, como primera pantalla.
- Numeración 01 / 02 / 03 sobre contenido que no tiene orden.
- Una vista del producto imitada con cajas y barras grises.
- Un mismo control con formas distintas, como círculos para las etiquetas cortas y pastillas para las largas.
- Controles de cabecera inflados hasta el área táctil, que bajan a su propia línea bajo el título en el teléfono.

## Tipografía y adornos

- Una palabra del titular destacada en cursiva, negrita o color.
- Antetítulos en mayúsculas espaciadas encima de cada encabezado, y etiquetas sobre contenido que se entiende sin ellas.
- Metadatos encadenados con puntos medios («A · B · C»).
- Etiquetas del tipo «PALABRA — fragmento», con una raya entre espacios.
- Monoespaciada en etiquetas pequeñas de datos, cuando lo que hace falta suele ser `tabular-nums`.
- Una flecha pegada al texto de enlaces y botones.

## Texto secundario

- Texto atenuado de acompañamiento: un elemento fuerte (etiqueta de fila, encabezado, cifra principal, opción de menú, botón) con un texto más pequeño y atenuado debajo o al lado, sea pie, conteo, base de cálculo, pista, calificador o aviso. Incluye la etiqueta y su valor apilados en dos líneas, y las frases hechas de una cifra en negrita seguida de una explicación atenuada.
- Datos repetidos: un calificador que repite lo que ya muestran el control seleccionado, un eje, la propia gráfica o un botón cercano.
- Instrucciones de lectura bajo el título de una gráfica, como «de arriba abajo: …» o «lo rayado significa …».

## Estructura

- Un botón que navega, en lugar de un enlace con los estilos del botón.
- Campos de formulario cuyo único rótulo es el placeholder.

## Movimiento

- Cada sección entra con un fundido y un desplazamiento hacia arriba.
- Cada tarjeta reacciona al pasar el cursor.
