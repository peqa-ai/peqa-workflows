# Crítica

El mínimo de calidad se construye desde el paso 5. En la crítica se comprueba sobre las capturas y, en los anchos que nombra cada punto, midiendo en el navegador, junto con el texto secundario y los principios. En una pantalla nativa, [pantallas nativas](native.md#mínimo-de-calidad) da la medida equivalente de cada punto que depende de la web.

## Mínimo de calidad

Se construye sin anunciarlo en los textos.

- contraste de al menos 4.5:1 para texto de cuerpo y 3:1 para texto grande y componentes de interfaz; sobre una imagen, medido en su zona más clara o más cargada
- foco de teclado visible en cada elemento interactivo
- `prefers-reduced-motion` respetado
- sin scroll horizontal a 320 px, ni anotaciones partidas que vuelvan a apilar etiqueta y valor
- a 360 y 390 px, cada título y los controles de su cabecera en la misma línea
- en teléfono, áreas táctiles de al menos 44 px de alto que no se solapan, aunque el control visible sea más pequeño
- estados hover, focus, active y disabled definidos en el componente, y loading cuando una acción espera

Si un color que fija el brief no alcanza el contraste en un uso, se conserva donde lo alcanza y se añade una variante para ese uso, con el contraste como fuente.

### Medir el contraste

Mide cada par de primer plano y fondo con el subcomando `contrast` del [helper de comprobaciones](design-system.md#comprobaciones). `--kind` fija el umbral: `text` para el cuerpo, `large` para texto grande y `ui` para bordes, iconos y anillos de foco frente al color vecino, cuando son lo que identifica el control o su estado; el fondo de un botón cuya etiqueta ya lo identifica no lo necesita. WCAG llama texto grande al de 18 pt (24 px) o más, o de 14 pt (unos 18.5 px) en negrita. Un primer plano con transparencia se compone sobre el fondo, que va opaco; sobre una imagen, el fondo es el color de esa zona. Acepta hex, con alfa opcional, y `rgb()` o `rgba()`; convierte antes otros formatos, como `oklch()` o `hsl()`, al valor sRGB que resuelve el navegador.

```sh
python3 "$UI_CHECKS" contrast --kind text --pair '#5C6470' '#FFFFFF' --pair '#5C6470' '#F4F1EA'
python3 "$UI_CHECKS" contrast --kind ui --pair '#2F6FEB' '#FFFFFF'
```

Fuentes: [WCAG 2.2](https://www.w3.org/TR/WCAG22/), criterios 1.4.3 y 1.4.11, y [su guía de 1.4.3](https://www.w3.org/WAI/WCAG22/Understanding/contrast-minimum.html), consultadas el 2026-11-03.

## Texto secundario

Haz inventario de cada texto secundario (atenuado, pequeño o calificador) y da un motivo para cada uno. «Es un dato» no es un motivo: el problema es la forma, no el contenido.

- Una etiqueta es su nombre y una cifra es su valor. El texto atenuado solo nombra marcas dentro de una gráfica: anotaciones, marcas de eje o leyenda. Lo demás pasa a un título o una etiqueta que ya existen, a la codificación de la gráfica o a un tooltip con descripción accesible, o se corta.
- Cada dato aparece una sola vez en la pantalla.

## Principios

- Cada borde, número o divisor afirma algo del contenido: un orden, un grupo o un límite. Si el contenido no tiene ese orden o ese límite, el recurso sobra; la numeración, por ejemplo, queda para pasos y cronologías.
- El movimiento cuenta qué cambió después de una acción de la persona: qué se abrió, qué se movió, qué se guardó. El que nadie provocó compite con el contenido, así que necesita un propósito que puedas nombrar.
