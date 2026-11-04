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
| Puntuación en sesión real | Sesión real `claude -p --plugin-dir <checkout>` en un sitio estático sintético con tokens, `.button` y `.card`: página de talleres enlazada desde la navegación, sin nombrar la puntuación | Guarda las capturas fuera del checkout; lanza un `Agent` con Opus y el Codex CLI a la vez, con el encargo sin autocrítica; calcula la media y sigue las rondas según el umbral |
| Revisores por CLI | Ejecución directa de las dos formas de `scoring.md` sobre las mismas capturas y el mismo encargo | Cada revisor responde con los nueve criterios, evidencia y hallazgos en JSON; el host expone el modelo efectivo |
| Escala exigente y mínimo por criterio | Ejecución directa de los dos revisores con la escala nueva sobre las mismas capturas y el mismo diff que puntuaron con la anterior | Bajan las notas altas, ningún criterio con hallazgo pasa de 8 y una nota por debajo de 8 obliga a corregir aunque la media supere 8 |
| Mínimo por criterio, simulación | Simulación: media de 8,50 con un 5 por un botón sin destino, 9,33 con un 7 que contradice el brief, todo en 8, un 10 con hallazgo, tercera ronda con un 7 y 9,40 con contraste fallido | Corrige o pregunta cuando hay una nota bajo 8; descarta con el brief; el 10 con hallazgo se relanza como incompleto; solo la persona amplía las rondas |
| Casos límite de la puntuación | Simulación: Codex ausente, media exacta de 8, 9,30 con contraste fallido, hijo de `dirige`, tercera ronda en 7,85, revisores con 4 puntos de diferencia, T3 con padre Codex, cambio solo de un token, Codex sin Claude CLI y 8,60 con correcciones menores | Sin sustituto del ausente; 8,00 corrige; el mínimo de calidad se corrige con cualquier nota; el hijo termina en el paso 6; la persona decide tras la tercera ronda; correcciones tras cerrar marcadas como no puntuadas |

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

## Puntuación observada el 3 de noviembre de 2026

Versión 0.15.0. Fixture sintético fuera del checkout: el sitio estático de un huerto comunitario, con tokens, `.button` y `.card`. La petición fue una página de talleres enlazada desde la navegación, sin mencionar la puntuación.

- **Primera sesión real.** Cargó `ui-design`, construyó la página, ejecutó el helper y capturó a 375, 320 y 1440 px. No leyó `scoring.md`, borró las capturas y cerró con «No he pedido la puntuación a revisores independientes». El paso 7 decía «Pide» y «los que estén disponibles», y el paso 6 no pedía guardar las capturas. Se corrigió así:
  - El paso 7 dice que cada cambio visual se puntúa y que el skill autoriza los revisores.
  - Un revisor solo queda fuera si su ruta no existe o falla.
  - El paso 6 guarda las capturas fuera del checkout.
- **Segunda sesión real.** Se ejecutó con el texto corregido, sobre una copia limpia del fixture.
  - Copió las capturas a una carpeta temporal y comprobó `codex --version` y `codex login status`.
  - Lanzó a la vez un `Agent` con `model: "opus"` y `codex exec` con `gpt-6.1-sol` en `xhigh` y las dos capturas adjuntas.
  - El encargo llevaba el brief, el encuadre, las capturas, la base y las secciones copiadas, sin autocrítica.
  - Opus dio 7,78 y Codex 9,00, con un resultado de 8,39 («bueno»).
  - Corrigió los hallazgos que aceptó y repitió el helper y las capturas. Marcó esas correcciones como no puntuadas y explicó los tres hallazgos que descartó.
  - El encargo copiaba también una frase dirigida al padre, la de relanzar una respuesta incompleta. Se movió a «Resultado».
- **Revisores por CLI.** Se ejecutaron directamente sobre la página de la primera sesión, con el resultado de 8,89 («bueno»).
  - `claude -p --model opus`, solo con herramientas de lectura, respondió con JSON válido y los nueve criterios. Dio 8,56, y el host expuso `claude-opus-5-5`.
  - `codex exec`, con `-i` antes de `--model`, respondió igual y dio 9,22. Sus eventos no exponen el modelo efectivo.
  - Los dos pusieron un 5 o un 6 en Encargo, porque «Inscribirme» lleva a una página sin formulario.
- **Simulación de casos límite.** Un agente nuevo recorrió los diez casos de la tabla y señaló ambigüedades. Se corrigieron las que cambian la conducta:
  - la ruta de Codex en T3 y el esfuerzo de Opus
  - cómo comprobar Claude Code CLI y la ausencia de sustitutos
  - qué hacer con una respuesta incompleta y cuándo redondear
  - repetir las comprobaciones tras correcciones fuera de una ronda
  - qué decide la persona tras la tercera ronda
  - el informe del hijo y el criterio Sistema frente a los cambios permitidos
  - el `--add-dir` del skill y las capturas web sin apariencia

  Las ambigüedades anteriores a este cambio siguen abiertas, y la simulación no se repitió.

- **Escala exigente y mínimo por criterio.** Se pidió corregir con cualquier nota por debajo de 8, y que el 9 y el 10 cueste conseguirlos. Cambios en la escala:
  - ante la duda, la nota más baja
  - un criterio con hallazgo tiene como mucho 8
  - un 9 o un 10 explica por qué no merece menos

  Los dos revisores puntuaron de nuevo, por CLI, las mismas capturas y el mismo diff de la primera sesión.

  | Revisor | Escala anterior | Escala nueva |
  | --- | --- | --- |
  | Opus | 8,56 | 7,89 |
  | Codex | 9,22 | 8,22 |
  | Resultado | 8,89, bueno | 8,06, corregir por Encargo 5 y 6, Tipografía 7 y Textos 7 |

  Las notas de 10 pasaron de 9 a ninguna, y las de 9 o más, de 13 a 8 de 18. Ningún criterio con hallazgo superó 8.

  Una simulación de seis casos encontró una banda sin nombre para más de 8 con una nota baja y un descarte que no admitía el brief. También faltaba qué hacer mientras se espera a la persona, y quién amplía las rondas. Se corrigieron sin repetirla.

## Pendiente

- La puntuación no se probó en T3 ni con un padre Codex: solo en Claude Code sin T3 y con los dos CLIs ejecutados directamente. Tampoco se probó con el padre de `dirige` puntuando un cambio integrado.
- La escala nueva se probó con una sola muestra por revisor y sin una sesión completa que haga las rondas.

- Ninguna muestra nativa compiló ni capturó en un simulador o emulador.
- Cada caso tuvo una sola muestra, y la activación por descripción dos.
- Las ambigüedades menores de la última tanda siguen abiertas: el modo de una app nativa sin tema, el contraste con color dinámico conservado y los anchos de teléfono distintos entre referencias.
- `dirige` sigue sin un criterio explícito para tareas demasiado pequeñas para delegar, para cuándo corresponde `revisa` o para quién posee el sistema cuando termina el hijo que lo tenía.
