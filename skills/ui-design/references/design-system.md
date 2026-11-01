# Sistema de diseño

Una fuente para cada valor y un componente por función. Una página que define su propio botón bifurca el sistema, y desde entonces cada cambio tiene dos sitios donde aplicarse.

## Encontrar lo que existe

Resuelve las ubicaciones desde el repositorio. Lugares habituales:

- Tokens: bloques `:root` con custom properties de CSS, el tema de Tailwind (`tailwind.config.*`, o `@theme` en CSS con Tailwind v4), objetos de tema (`createTheme`, `extendTheme`), JSON de tokens o fuentes de Style Dictionary y archivos de variables SCSS.
- Componentes: `components/ui/`, `src/components/`, un paquete del workspace como `packages/ui`, el `components.json` de shadcn y las bibliotecas de UI de `package.json` (MUI, Chakra, Mantine, Radix, React Aria, Headless UI, Vuetify, PrimeVue, Angular Material).
- Documentación: Storybook (`.storybook/`, `*.stories.*`), un `DESIGN.md` o notas de diseño y tokens exportados de Figma.

Búsquedas iniciales, ajustadas al repositorio:

```sh
rg -l --hidden -g '!node_modules' ':root\s*\{|@theme|createTheme|extendTheme' .
rg -l -g '!node_modules' 'export (default )?(function|const) (Button|Card|Input|Stack)\b' .
```

Después lee cómo usan lo encontrado dos o tres páginas existentes. El uso muestra las convenciones reales mejor que las definiciones.

## Elegir el modo

- **Extender.** Hay tokens y componentes, y las páginas los usan. Trabaja dentro de ellos. La dirección nueva entra como tokens nuevos, una variante o un componente nuevo. Cambiar el valor de un rol existente afecta a otras páginas, así que va al informe como propuesta, salvo que corrija el mínimo de calidad.
- **Consolidar.** Los estilos existen como literales dispersos, por ejemplo el mismo hex en muchos archivos o varias implementaciones de botón. En las reglas y componentes que usa la página de la tarea, la construcción empieza extrayendo tokens y un componente por función sin cambiar su aspecto. Las demás apariciones, incluidas las implementaciones heredadas de un componente consolidado, van al informe como seguimiento. Si una corrección del mínimo de calidad cambia un valor consolidado, aplícala a todos los usos que fallan ese mínimo, también fuera de la tarea, para que el sitio no quede con dos versiones; los usos que ya lo cumplen conservan el valor. Lista esos cambios en el informe.
- **Establecer.** No hay nada, o solo los estilos de demostración de una plantilla, como los de Vite, que se retiran. Crea el sistema mínimo descrito abajo antes de la primera página.

Si la interfaz vive dentro de una plataforma con sistema propio, como el panel de administración de un tercero, la extensión de un host o un servicio público con sistema oficial, el modo es extender ese sistema con su paquete oficial, aunque el repositorio no tenga tokens. Su aspecto forma parte del brief, así que la prueba de intercambio lo justifica. Sus componentes y patrones, incluidos los textos de ayuda, mandan sobre las preferencias de este skill. Si uno no alcanza el mínimo de calidad y su API no permite ajustarlo, el informe lo nombra.

Cuando el brief pide algo que el sistema no puede expresar, añade el token o la variante y nómbralo en el informe. Si el brief y el sistema discrepan, el brief manda en lo que nombra explícitamente y el sistema en todo lo demás.

## Capas de tokens

- **Valores base.** La paleta y las escalas en bruto, con nombres de lo que son: `--clay-600`, `--space-4`.
- **Roles semánticos.** Lo que usan componentes y páginas, con nombres de su función: `--color-surface`, `--color-text`, `--color-text-muted`, `--color-accent`, `--color-border`, `--color-danger`, `--color-focus`.
- **Tokens de componente.** Solo cuando un componente necesita un valor que ningún rol cubre.

Componentes y páginas usan roles semánticos. Así, un cambio de tema, el modo oscuro o una segunda marca editan una sola capa.

Conjunto mínimo al establecer:

- roles de color, con cada par de texto y superficie cumpliendo el contraste
- familias tipográficas, una escala de 5 a 7 pasos con una sola razón, pesos e interlineados
- una escala de espaciado, como 4, 8, 12, 16, 24, 32, 48, 64 y 96 px
- radios por jerarquía, por ejemplo ninguno, pequeño y grande
- dos o tres niveles de elevación, o ninguno
- duraciones y curvas de movimiento
- tamaños de icono y grosor de trazo
- un anillo de foco y los breakpoints; CSS no acepta custom properties dentro de `@media`, así que los breakpoints se documentan como tokens y su valor se repite en las consultas

Usa el mecanismo que ya tiene el stack: custom properties mapeadas al tema de Tailwind si hay Tailwind, el objeto de tema de la biblioteca si hay una biblioteca, y propiedades en `:root` en los demás casos. Una herramienta de build de tokens es una dependencia nueva y necesita un motivo que aporte la tarea. Los componentes usan el mecanismo de estilos que ya tiene el proyecto, como CSS Modules, Tailwind o CSS-in-JS; en un proyecto nuevo, el que trae el stack, como CSS Modules en Vite.

## Componentes

- Busca por función antes de crear nada: botón, enlace, input, select, checkbox, diálogo, tarjeta, badge, pestañas, tabla. Cada función tiene un componente.
- Una diferencia necesaria se convierte en una variante o prop de tamaño, añadida en el archivo del propio componente. Quien usa el componente elige la variante y deja el estilo al componente.
- Un elemento que parece botón pero navega es un enlace. Da al componente de enlace las variantes del botón, o deja que el botón se renderice como enlace, para que ambos compartan un solo conjunto de estilos.
- Estiliza los componentes de una biblioteca con su API de tema, como `styleOverrides` de MUI o los objetos de tema de Chakra y Mantine. Los archivos de shadcn/ui se copian al repositorio y le pertenecen, así que se editan en su sitio.
- Al establecer, construye solo las primitivas que usa la tarea. Normalmente son un Button con variantes por intención (primary, secondary, quiet, danger), un Link, un Field que une el input con su label y su error, una Surface o Card y primitivas de layout como Stack, Cluster y Grid.
- Cada campo muestra una etiqueta visible; el placeholder solo da un ejemplo de formato. El error aparece bajo el campo y se enlaza con `aria-describedby`.
- Los iconos salen de un solo conjunto, el del proyecto si ya tiene uno, con tamaños y grosor de trazo tomados de tokens. Un emoji no sustituye a un icono. Si el proyecto no tiene conjunto, añadir uno es una dependencia nueva y necesita motivo.
- La navegación de escritorio cabe en una línea en el ancho más estrecho en que se muestra. Si no cabe, acorta etiquetas, retira las secundarias o adelanta el colapso.
- Cada componente interactivo define hover, focus-visible, active y disabled, y loading cuando una acción espera.
- El tamaño visible no es el área táctil. Un control puede verse compacto, de unos 28 px de alto, y extender su área táctil hasta 44 px de alto en teléfono con un pseudo-elemento posicionado (`::before` con `inset` negativo), sin solaparse con la del vecino.
- Todas las instancias de un control comparten alto y radio, sea cual sea el largo de su etiqueta. Un ancho mínimo igual al alto convierte las etiquetas cortas en círculos y deja las largas como pastillas.
- El layout es dueño del espaciado. Los componentes no llevan margen exterior y los contenedores fijan `gap`. Así terminan las peleas de márgenes entre secciones.
- Las secciones comparten una anatomía (título, acciones y contenido) y reutilizan un solo juego de piezas internas. Las variantes hechas a mano en cada sección se leen como generadas.
- Las acciones de una cabecera van en la línea de su título. Antes de bajarlas a otra línea, compáctalas con menos relleno y menos espacio entre botones. Solo bajan en el ancho más angosto, y el informe dice desde qué ancho caben en la misma línea.
- El inicio de cada sección se nota sin ambigüedad, con un filete y un título o con un salto claro de tamaño. El filete no se apila contra un separador que ya existe, como el borde de la barra superior o el inicio de la página.
- Sin framework, deja los tokens en `:root` y los componentes como bloques de clases (`.button`, `.button--quiet`) en una hoja de estilos, y declara `@layer tokens, base, components, layouts, utilities;` para que el orden de la cascada sea explícito. Usa `:where()` cuando una regla base deba ser fácil de sobrescribir.
- Si hay CSS heredado sin capa, envuélvelo sin reindentar en una capa `legacy` declarada primero, y pasa sus `@import` a `@import url(...) layer(legacy)`. Las reglas sin capa ganan a todas las capas, y un `!important` heredado invierte el orden entre capas. Una vez en `legacy`, cualquier regla de una capa posterior le gana sea cual sea su especificidad, así que las reglas nuevas de `base` se limitan a lo que usa la tarea o reproducen el valor actual.

## Contratos invisibles

Un rediseño cambia lo que se ve y conserva lo que otros usan sin verlo: los `id` y las anclas, el `name` y el orden de los campos, `autocomplete`, los `data-*` de pruebas y analítica, las rutas, los metadatos (título, Open Graph, datos estructurados), los textos legales y de consentimiento, y las etiquetas de navegación. Cambiar uno de ellos necesita que lo pidan el brief o el usuario.

Para comprobarlo, compara los atributos de las líneas retiradas con los de las añadidas. Cada línea que empieza por `<` es un atributo que desapareció:

```sh
ATTR='\b(id|name|for|htmlFor|autocomplete|autoComplete|href|data-[a-z-]+)="[^"]*"'
diff <(git diff -U0 "$BASE" -- <archivos> | rg '^-[^-]' | rg -o "$ATTR" | sort -u) \
     <(git diff -U0 "$BASE" -- <archivos> | rg '^\+[^+]' | rg -o "$ATTR" | sort -u) | rg '^<'
```

En JSX, revisa además los atributos con valor entre llaves, que este patrón no captura. Si un componente envuelve el control, comprueba también que reenvía esos atributos al elemento del DOM.

## Comprobaciones

Ejecútalas sobre lo que cambió la tarea respecto a su base: los archivos nuevos completos y, en los que ya existían, solo las líneas añadidas, para que el código heredado no tape la señal. En un checkout compartido con otros agentes, limita la lista a tus archivos.

Los literales de color, tamaño de texto, espacio y radio solo van en la definición de tokens: su archivo, o el bloque `:root` o `@layer tokens` cuando todo vive en una hoja. Los elementos de formulario sin envolver solo van dentro del componente que los envuelve; en HTML sin componentes, cada control lleva la clase de su bloque. Cualquier otro resultado se corrige o lleva una justificación de una línea en el informe.

- Literales de color: `#[0-9a-fA-F]{3,8}\b|(rgba?|hsla?|hwb|lab|lch|oklab|oklch|color|color-mix)\(`
- Literales de tamaño, espacio y radio en CSS: `(margin|padding|gap|font-size|border-radius)[a-z-]*\s*:[^;]*\b[0-9.]+(px|rem|em)\b`
- Valores arbitrarios de Tailwind: `\[(#|-?[0-9.]+(px|rem|em))`
- Estilos inline y overrides: `style=\{\{|style="|!important`
- Elementos sin envolver que ya tienen componente: `<(button|input|select|textarea)\b`

Pasa cada archivo como argumento separado. Por ejemplo, para los literales de color:

```sh
COLOR='#[0-9a-fA-F]{3,8}\b|(rgba?|hsla?|hwb|lab|lch|oklab|oklch|color|color-mix)\('
# Líneas añadidas en archivos versionados
git diff -U0 "$BASE" -- <archivos> | rg '^\+[^+]' | rg "$COLOR"
# Archivos nuevos sin versionar, completos; -r evita buscar en todo el directorio si la lista queda vacía
git ls-files -z --others --exclude-standard -- <archivos> | xargs -0 -r rg -n "$COLOR"
```

Sin Git, compara con una copia de los originales mediante `diff -U0`.

Compara además cada componente nuevo con el inventario del paso 2: dos componentes para la misma función son un defecto, salvo las implementaciones heredadas que el modo consolidar dejó como seguimiento.
