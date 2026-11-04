# Escenarios de ui-design

Pruebas de comportamiento de `ui-design` y de su integración con `dirige`, no tests de un recolector ejecutable. Cada muestra se ejecuta con contexto fresco, leyendo el `SKILL.md` del checkout y las referencias que alcance. Usar datos sintéticos. Los prompts describen el pedido y el entorno sin nombrar la conducta que se prueba. Contrastar decisiones y diffs, no coincidencias de palabras.

Repositorio sintético de las muestras con código: Ledgerline, una web React + Vite + TypeScript de contabilidad para talleres de bicicletas. Tiene `tokens.css` con valores base y roles, `Button` con variantes, `Card`, `Stack` y una home que navega con un botón. No tiene dependencias instaladas ni se renderiza.

## Casos

| Caso | Condiciones | Resultado esperado |
| --- | --- | --- |
| Sistema existente | Ejecución en el repositorio sintético: añadir `/pricing` con tres planes y preguntas frecuentes, enlazada desde la home. Pedido en español, producto en inglés | Modo extender; botones y estilos del sistema; la navegación como enlace con los estilos del botón, añadida al componente; literales solo en tokens; la home conserva su aspecto salvo correcciones del mínimo de calidad; textos en inglés; informe con fuentes y cambios visibles |
| `dirige` con interfaz | Simulación: el padre recibe una página de precios y una pantalla de facturación | Pasos 1 a 4 de `ui-design` antes de dividir; un único propietario de tokens y componentes; briefs con plan, inventario, propietario y la indicación del paso 5 |
| `dirige` sin rediseño | Simulación: arreglar un botón Guardar que queda deshabilitado tras un error de red | No carga `ui-design`; un solo editor |
| Brief con una señal | Simulación: landing de cerámica que pide crema `#F4F1EA` y terracota `#D97757` | Sigue el brief; conserva el acento donde alcanza el contraste y añade una variante para texto; la auditoría lo justifica |
| Estilos dispersos | Simulación: sitio estático con `#0a6` en 14 reglas y tres clases de botón; rediseñar contacto | Modo consolidar limitado a contacto; CSS heredado en `@layer legacy`; comprobaciones sobre líneas añadidas; el resto como seguimiento |
| Hijo en checkout compartido | Simulación: un hijo con plan visual, cuyo sistema pertenece al padre, necesita un `Table` que no existe | No crea el componente; lo pide al padre y sigue con lo independiente; comprobaciones solo sobre sus archivos |
| Texto secundario | Simulación: pantalla de ventas con siete textos atenuados de acompañamiento, datos repetidos, instrucciones de lectura y títulos 18/600 contra 16/600 | Inventario de textos secundarios; solo queda el que nombra una marca de la gráfica; cada dato una vez; jerarquía corregida; secciones con una sola anatomía |
| Corrección puntual | Simulación: el revisor señala solo el texto gris bajo el título | Corrige todos los elementos con la misma estructura y registra la lección como patrón |
| Cabecera compacta | Simulación: cabecera con título y dos selectores de 44 px, `min-width` igual al alto y radio completo; revisar para teléfono y escritorio | Variante compacta de unos 28 px con área táctil de 44 px que no se solapa; mismo alto y radio en todas las opciones; controles en la línea del título, con el ancho desde el que caben |
| Landing sin recursos | Simulación: landing de un taller de cerámica sin fotos ni testimonios, leída sobre todo en el móvil, con seis enlaces y un botón Reservar | Primera pantalla con la acción visible a 1440×900 y 390×844; cifras marcadas como ejemplo; ninguna vista falsa del producto; movimiento solo como respuesta; navegación en una línea antes del colapso |
| Rediseño de formulario | Simulación: registro con campos rotulados solo por placeholder, `data-testid` y errores en un toast | Conserva `id`, `name`, `autoComplete` y `data-testid`; etiquetas visibles; error bajo el campo con `aria-describedby`; toast solo para el éxito; capturas de entrada, error y éxito |
| Sistema de plataforma | Simulación: pantalla de ajustes de una extensión dentro del panel de una plataforma con sistema oficial; el repositorio no tiene tokens | Modo extender con el paquete oficial; la identidad sale de agrupación, textos y vista previa, no de un sistema propio |
| Web con navegador | Ejecución en un sitio estático sintético con tokens, `.button`, `.card` y un menú que colapsa a 900 px: página de precios con tres tarifas y preguntas frecuentes, enlazada desde la navegación | Capturas a 375, 1440 px y en el ancho previo al colapso; helper `literals`, `contracts` y `contrast` con hallazgos corregidos o justificados; las demás páginas conservan su aspecto |
| SwiftUI | Ejecución sin compilar en un fixture SwiftUI con color sets claro/oscuro, `Theme.swift`, un `ButtonStyle` y UI tests con `accessibilityIdentifier`: Ajustes por secciones con tarjeta de plan | Lee `native.md`; modo extender sobre componentes de la plataforma; tokens con variante oscura; identificadores conservados; capturas declaradas pendientes |
| Compose | Ejecución sin compilar en el tema de la plantilla de Android Studio con color dinámico activo y un color institucional en el brief: préstamos con Renovar | Decide sobre el color dinámico; tema con espaciado en un `CompositionLocal`; `testTag` conservado; 48 dp; capturas pendientes |
| Casos aplazados | Simulación: plantilla de Vite, acento compartido más oscuro, plataforma con patrones propios, testimonios con menú que colapsa, registro con `<Input>` propio y entorno sin Python | Establece y retira la demo; token nuevo o corrección global según el contraste; la plataforma manda; contratos con el helper y reenvío al DOM revisado a mano; comprobaciones pendientes sin Python |
| Activación por descripción | Sesión real `claude -p --plugin-dir <checkout>` en copias de los fixtures web y SwiftUI, con una petición de interfaz que no nombra el skill y otros skills de diseño instalados | Carga `peqa-workflows:ui-design` desde el checkout |

## Control previo

Base inspeccionada: `00c6911`. El plugin no tenía un skill de interfaz y `dirige` no trataba el sistema de diseño como contrato compartido.

Control con el skill original `frontend-design` 1.1.1, en inglés y con una sola muestra del caso del sistema existente: reutilizó `Button` y los tokens, pero navegó con `<Button onClick={navigate}>`, y el CSS de la página ocupó 297 líneas. La primera versión del skill nuevo, también en inglés, extendió bien el sistema, pero añadió una cabecera de sitio, reseteos globales de márgenes y tamaños de encabezado que cambiaron la home. De ahí sale la regla de que las demás páginas conservan su aspecto.

## Resultado observado el 1 de noviembre de 2026

Primera tanda, con la versión en español: una ejecución y dos simulaciones.

- Sistema existente: modo extender, `ButtonLink` en `Button.tsx`, sin literales fuera de tokens ni estilos inline, y `global.css` intacto. La cabecera y la carga de fuentes quedaron como propuesta. En la home solo cambiaron el enlace nuevo y el anillo de foco, que pasó de 2.42:1 a 4.65:1. Los textos quedaron en inglés. El diff se comprobó con las búsquedas del skill.
- `dirige` con interfaz: el padre fijó la dirección con los pasos 1 a 4, asignó tokens y componentes a un hijo de sistema que trabaja antes que los de página, e incluyó en los briefs el plan, el inventario, el propietario y el paso 5.
- `dirige` sin rediseño: no cargó `ui-design` y citó la condición «construye o rediseña».
- Brief con una señal: siguió el brief, detectó que `#D97757` sobre la crema da 2.77:1 y añadió una variante oscura para texto, con el contraste como fuente.
- Estilos dispersos: eligió consolidar, limitado a contacto.

Fallos de redacción detectados en esa tanda:

- Las comprobaciones recorrían archivos completos; con una sola hoja compartida salían todos los literales heredados.
- En un checkout compartido, la lista de archivos cambiados incluía los de otros hijos.
- No se avisaba de que el CSS heredado sin capa gana a las capas nuevas.
- Una corrección de contraste a medias dejaba dos versiones del mismo color.
- La pauta de planificar con tokens solo nombraba el modo extender.

Se corrigieron con comprobaciones sobre líneas añadidas y archivos propios, la capa `legacy`, la corrección aplicada a los usos que fallan el mínimo y la mención del modo consolidar. En la misma revisión se incorporaron reglas sobre texto secundario, datos repetidos, gráficas, jerarquía, anatomía de secciones y correcciones aplicadas al patrón. Proceden de lecciones de una revisión de diseño en otra sesión, transmitidas en forma genérica.

Segunda tanda, con dos agentes nuevos sobre los casos corregidos y los nuevos:

- Estilos dispersos: envolvió el CSS heredado en `legacy` y revisó solo las líneas añadidas de `styles.css` y `contacto.html`.
- Hijo en checkout compartido: no creó `Table`, se lo pidió al padre con una especificación y siguió con lo independiente; limitó las búsquedas a `src/pages/settings`.
- Texto secundario: de siete textos atenuados dejó uno, la etiqueta de la meta en un medidor. Pasó el periodo al título, quitó los datos repetidos y las instrucciones de lectura, y unificó las dos secciones.
- Corrección puntual: corrigió los siete casos del patrón y escribió la lección como patrón.

Ambigüedades señaladas en la segunda tanda y aclaradas sin otra simulación:

- La regla de jerarquía pedía peso distinto entre niveles contiguos y a la vez el peso más alto para dos niveles vecinos; ahora admite el mismo peso con un salto de tamaño claro.
- «Las páginas existentes» no excluía la de la tarea.
- En modo extender no quedaba claro qué se toma del objeto del tema.
- El hijo que empieza en el paso 5 no leía las referencias de producto ni de tipografía.
- `xargs` sin `-r` busca en todo el directorio cuando la lista queda vacía en GNU.
- La corrección de contraste al consolidar podía oscurecer usos que ya cumplen.
- El elemento distintivo era obligatorio en un paso y «como mucho uno» en otro.
- Las búsquedas solo cubrían colores, aunque la regla abarca tamaños, espacios y radios.

Los patrones nuevos se probaron con `rg` sobre muestras positivas y negativas, y `xargs -0 -r` con una lista vacía en macOS. Los tests del repositorio pasan; no ejecutan estas instrucciones.

Tercera tanda, tras otra lección de la misma sesión sobre controles de cabecera. Un agente nuevo revisó la cabecera compacta sin que el prompt nombrara la conducta. Añadió una variante `compact` en el archivo del componente, de 28 px visibles con un `::before` que lleva el área táctil a 44 px solo en vertical. Usó un solo radio con `min-width: 0` para que ninguna opción quede como círculo, y mantuvo los controles en la línea del título desde unos 352 px, según su cálculo de anchos sin renderizar. La variante por defecto, usada en otras páginas, quedó como propuesta.

Cuarta tanda, tras reescribir el skill con instrucciones propias. Se rehicieron con otra redacción y ejemplos de estas pruebas las partes que seguían de cerca a `frontend-design`: primera pantalla, movimiento, textos de interfaz, señales, principios y formato del plan. Se añadieron ideas, redactadas de nuevo, de la revisión de `design-taste-frontend` e `intentional-ui`, dos skills sin licencia declarada:

- contratos invisibles en un rediseño
- cifras persuasivas con fuente
- ancho anterior al colapso de la navegación
- primera pantalla con `100svh`
- etiquetas visibles y errores junto al campo
- contraste sobre imágenes
- vistas del producto con componentes reales
- un solo conjunto de iconos
- sistemas impuestos por una plataforma
- capturas del flujo completo

Dos agentes nuevos cubrieron los tres casos añadidos y siguieron las instrucciones, citando archivo y línea:

- Landing sin recursos: descartó la terracota con la prueba de intercambio, marcó las cifras de la clase con `data-example`, sustituyó las fotos por una ilustración SVG de las fases de una pieza y una lista de recursos pendientes, dejó la página sin movimiento propio y fijó el colapso de la navegación en 1024 px, con capturas a 1023 y 1024.
- Rediseño de formulario: conservó los contratos, creó `Field`, añadió `loading` a `Button` y movió los errores junto a los campos.
- Sistema de plataforma: eligió extender el paquete oficial.

Ambigüedades corregidas después, sin otra simulación:

- La búsqueda de contratos no veía `autoComplete` ni `htmlFor`, ni comprobaba que un componente reenvía los atributos al DOM.
- Los estilos de demostración de una plantilla de Vite podían leerse como un sistema existente.
- No se decía que cambiar el valor de un rol existente afecta a otras páginas.
- Faltaba qué hacer cuando los patrones de una plataforma chocan con las preferencias del skill.
- CSS no acepta custom properties en `@media`, y los breakpoints figuraban como tokens.

## Resultado observado el 3 de noviembre de 2026

Versión 0.14.0: entrada reducida a unas 970 palabras con `critique.md`, referencia `native.md` y helper `scripts/ui_checks.py`, cubierto por `tests/test_ui_checks.py`. Fixtures sintéticos fuera del checkout: un sitio estático de un taller de cerámica, una app SwiftUI de recordatorios de medicación y una app Compose de una biblioteca municipal.

Primera tanda: una ejecución con navegador, dos ejecuciones nativas sin compilar, una simulación de seis casos y dos sesiones reales de Claude Code.

- **Web con navegador.** Eligió extender, creó `precios.html` y la enlazó desde las tres páginas. Capturó a 375, 901 y 1440 px, la primera pantalla a 390×844 y 1440×900, y la cabecera a 320 px. Midió también 360 y 390 px. Ejecutó `literals`, `contracts` y `contrast`; justificó los `raw_control` del `<button class="button">` heredado y los filetes decorativos de 1.26:1. Marcó los precios con `data-ejemplo`. El menú sin script, el alto de 62 px de `.button` y el color de la marca quedaron como propuestas. Comparó la home antes y después: idéntica a 375 px y solo cambia la zona del menú a 1440 px.
- **SwiftUI.** Leyó `native.md`. Extendió el tema con tres color sets con variante oscura, creó `PlanCard` sobre componentes de la plataforma con `ViewThatFits`, añadió el estado disabled al `ButtonStyle` y conservó los cuatro `accessibilityIdentifier`. Midió el contraste en claro y oscuro con el helper. Hizo `swiftc -typecheck` contra el SDK de iOS por iniciativa propia y declaró pendientes las capturas. Usó `Button` para navegar porque `native.md` no traducía la regla web de enlace frente a botón.
- **Compose.** Eligió establecer sobre la plantilla, desactivó el color dinámico para conservar el verde del brief y añadió una variante oscura del verde por contraste. Creó `Dimens.kt` con un `CompositionLocal`, `LoanItem` con `FlowRow` y aplicó `modifier` a la raíz. `literals` sin `--tokens` dio 49 hallazgos solo en el tema, y con `--tokens` ninguno. Conservó `home.search`. Preguntó si el contenedor de un botón tonal necesita 3:1.
- **Casos aplazados.** Siguió las aclaraciones del PR #4: retiró la demo de Vite, llevó el acento compartido a un token nuevo o a una corrección global según el contraste medido, dio prioridad a la plataforma, revisó a mano el reenvío de `<Input>` y, sin Python, declaró pendientes las comprobaciones.
- **Activación por descripción.** Las dos sesiones cargaron `peqa-workflows:ui-design` desde el checkout sin que la petición lo nombrara, con `design` y `design-sync` también instalados. La web capturó a 375, 901 y 1440 px y ejecutó el helper; la nativa comprobó tipos, ejecutó el helper y dejó pendientes las capturas.

Fallos de redacción detectados en esa tanda:

- `native.md` no traducía la regla web de enlace frente a botón, ni decía que las convenciones de la plataforma mandan.
- Faltaban la carga de fuentes y las cifras tabulares en nativo, y qué parte del conjunto mínimo ya trae la plataforma.
- El paso 5 terminaba cuando las comprobaciones «pasan», aunque la referencia admite hallazgos justificados o pendientes.
- `git merge-base origin/main HEAD` falla sin remoto, y la ruta sin Git no decía cuándo copiar los originales ni excluía dependencias.
- El ancho previo al colapso no preveía pantallas sin navegación, y los anchos del mínimo de calidad parecían exigir capturas.
- `contrast --kind ui` no decía si el fondo de un botón con etiqueta necesita 3:1.

Segunda tanda: un agente nuevo repitió solo los casos corregidos (botón de SwiftUI que navega, botón tonal de Compose, sitio sin Git, repositorio sin remoto con `raw_control` y landing sin menú). Usó `NavigationLink` con `ButtonStyle`, no exigió 3:1 al contenedor tonal, copió la carpeta antes de editar, tomó `HEAD` como base y omitió el ancho de colapso. Señaló que copiar solo los archivos tocados hace que `diff -ruN` marque el resto como nuevo y que faltaba el equivalente de `ViewThatFits` en Compose. Ambos se corrigieron sin otra simulación.

Validación estática: `python3 -m unittest discover -s tests -v`, enlaces relativos y anclas comprobados con un script, y `git diff --check` limpio. Los comandos de `adb` de `native.md` no se ejecutaron en un dispositivo.

## Pendiente

- Ninguna muestra nativa compiló ni capturó en un simulador o emulador.
- Cada caso tuvo una sola muestra, y la activación por descripción dos.
- Las ambigüedades menores de la última tanda siguen abiertas: el modo de una app nativa sin tema, el contraste con color dinámico conservado y los anchos de teléfono distintos entre referencias.
- `dirige` sigue sin un criterio explícito para tareas demasiado pequeñas para delegar, para cuándo corresponde `revisa` o para quién posee el sistema cuando termina el hijo que lo tenía.
