# Pantallas nativas

Revisado el 2026-11-03. Cubre pantallas de apps para iOS y iPadOS en SwiftUI y para Android en Jetpack Compose. El resto del skill sigue aplicando; aquí está lo que cambia de herramienta o de medida.

## Tokens y tema

Resuelve las ubicaciones desde el proyecto. Lugares habituales:

- SwiftUI: color sets del asset catalog (`Assets.xcassets`), cada uno con su variante para la apariencia oscura, y un tipo de tema en Swift con miembros estáticos para roles, espaciado, radios y tipografía, como `extension Color { static let surface = Color("Surface") }` o `enum Spacing { static let medium: CGFloat = 16 }`.
- Compose: `MaterialTheme` con su `ColorScheme`, su `Typography` y sus `Shapes`. Material no define espaciado: va en una clase propia que el tema provee con un `CompositionLocal` (`staticCompositionLocalOf`). La plantilla de Android Studio deja el tema en `ui/theme/Color.kt`, `Type.kt` y `Theme.kt`.

Esos archivos y el asset catalog son la definición de tokens; pásalos a `literals` con `--tokens`. La tipografía sigue el tamaño de texto del sistema: en SwiftUI, con estilos de texto (`.body`, `.headline`) o `Font.custom(_:size:relativeTo:)`; en Compose, con tamaños e interlineados en `sp` y el espaciado en `dp`.

Si `Theme.kt` elige `dynamicLightColorScheme` o `dynamicDarkColorScheme`, como hace la plantilla en Android 12 y posteriores, la paleta sale del fondo de pantalla de la persona y no del tema. El plan decide si la app conserva ese color dinámico, y el informe lo dice.

## Componentes de la plataforma

Los componentes de SwiftUI y de Material 3 forman la capa de componentes del sistema, y las Human Interface Guidelines y Material Design son su documentación. Extender trabaja sobre ellos y sobre el tema del proyecto. Establecer crea el tema que esos componentes leen, sin reimplementarlos. Una variante vive en el archivo del componente, como un `ButtonStyle` en SwiftUI o un botón propio que fija `ButtonDefaults.buttonColors` en Compose. Un componente propio aparece cuando ninguno de la plataforma cumple la función, y se construye componiendo los suyos.

Las convenciones de la plataforma, como el estilo de las cabeceras de lista o sus colores de sistema, mandan sobre las preferencias de este skill, igual que en una [plataforma con sistema propio](design-system.md#elegir-el-modo). Esa regla también fija qué hacer si una no alcanza el mínimo de calidad. Al establecer, el conjunto mínimo de tokens se limita a lo que la plataforma no trae: sus componentes ya definen foco, movimiento y estados, y los iconos salen de SF Symbols o de Material Symbols si el proyecto no tiene otro conjunto.

## Plan y construcción

- El reparto de la pantalla se planifica para el dispositivo más pequeño y el más grande que admite la app, en lugar de teléfono y escritorio, y para el tamaño de texto más grande.
- El contenedor fija el espacio entre sus hijos con valores del tema: `VStack(spacing:)` y `HStack(spacing:)` en SwiftUI, `Arrangement.spacedBy()` en Compose. Los componentes no añaden padding alrededor de sí mismos.
- Un composable propio recibe `modifier` y lo aplica a su raíz, para que el `testTag`, la semántica y el layout que le pasan lleguen al control.
- La regla web de enlace frente a botón se traduce al patrón de navegación de cada plataforma. En SwiftUI, lo que abre otra pantalla es un `NavigationLink`, que puede llevar el `ButtonStyle` del sistema. En Compose, un botón cuyo `onClick` navega es el patrón habitual.
- Las fuentes propias van en el bundle de la app, declaradas en `UIAppFonts` del `Info.plist`, o en `res/font` en Android. Las cifras tabulares se piden con `.monospacedDigit()` en SwiftUI y con `fontFeatureSettings = "tnum"` en el `TextStyle` de Compose.
- El sistema cambia de apariencia aunque la app no lo pida, así que la pantalla tiene modo oscuro y aplica [temas](product-ui.md#temas), salvo que la app fije una sola apariencia (`UIUserInterfaceStyle` en `Info.plist`, o un tema de Compose sin esquema oscuro).

## Contratos invisibles

Además de los [contratos de la web](design-system.md#contratos-invisibles) que tengan equivalente, un rediseño nativo conserva:

- `accessibilityIdentifier` en SwiftUI y `testTag` en Compose, que usan las pruebas de UI
- las rutas de navegación y los deep links, incluidos los universal links y los App Links
- las etiquetas de accesibilidad, como `accessibilityLabel` y `contentDescription`

`contracts` lista los identificadores y tags retirados; las rutas, los deep links y las etiquetas se revisan a mano.

## Mínimo de calidad

Cada punto del [mínimo de calidad](critique.md#mínimo-de-calidad) se mide así en nativo:

| Web | Nativo |
| --- | --- |
| Contraste | Los mismos umbrales, en apariencia clara y oscura |
| Foco de teclado visible | Con teclado externo, cada control muestra el foco; los de la plataforma ya lo hacen |
| `prefers-reduced-motion` | Con Reducir movimiento en iOS (`accessibilityReduceMotion` en SwiftUI) o Quitar animaciones en Android, la pantalla funciona sin movimiento automático |
| Sin scroll horizontal a 320 px | Con el tamaño de texto más grande (Dynamic Type en iOS, escala de fuente en Android), ningún texto queda cortado ni solapado, y lo que no cabe en horizontal pasa a vertical, por ejemplo con `ViewThatFits` en SwiftUI o `FlowRow` en Compose |
| Título y controles en una línea a 360 y 390 px | En el dispositivo más pequeño, con el tamaño de texto por defecto |
| Áreas táctiles de 44 px de alto en teléfono | 44×44 pt en iOS y iPadOS, el tamaño por defecto de la HIG, y 48×48 dp en Android, sin solaparse. Componentes de Material como `Checkbox` o `Switch` reservan los 48 dp cuando reciben acciones; un control propio usa `minimumInteractiveComponentSize()` en Compose o `.frame(minWidth:minHeight:)` con `.contentShape(_:)` en SwiftUI, con la medida tomada del tema |
| Estados hover, focus, active, disabled y loading | Pressed, disabled y loading; focus y hover cuando hay teclado o puntero |

## Capturas

Captura con el simulador o el emulador que exponga el host, según [evidencia visual](../../../references/visual-evidence.md#screenshots), en el dispositivo más pequeño y el más grande que admite la app, en apariencia clara y oscura y con el tamaño de texto más grande. Con `xcrun simctl` y `adb`, estos comandos fijan apariencia y tamaño antes de capturar:

```sh
xcrun simctl ui booted appearance dark
xcrun simctl ui booted content_size accessibility-extra-extra-extra-large
xcrun simctl io booted screenshot "$EVIDENCIA/ios-ajustes-oscuro-texto-max.png"

adb shell cmd uimode night yes
adb shell settings put system font_scale 2.0
adb exec-out screencap -p > "$EVIDENCIA/android-ajustes-oscuro-texto-max.png"
```

La escala 2.0 es el máximo desde Android 14; en versiones anteriores, usa el máximo de sus ajustes. Restablece apariencia y tamaño al terminar.

## Fuentes

Consultadas el 2026-11-03:

- [HIG: Accessibility](https://developer.apple.com/design/human-interface-guidelines/accessibility): 44×44 pt por defecto y 28×28 pt de mínimo para controles en iOS y iPadOS, texto ampliable al menos al 200 % y Reducir movimiento.
- [Supporting Dark Mode in your interface](https://developer.apple.com/documentation/uikit/supporting-dark-mode-in-your-interface), [Choosing a specific interface style for your iOS app](https://developer.apple.com/documentation/uikit/choosing-a-specific-interface-style-for-your-ios-app), [`Font.custom(_:size:relativeTo:)`](https://developer.apple.com/documentation/swiftui/font/custom(_:size:relativeto:)) y [`accessibilityReduceMotion`](https://developer.apple.com/documentation/swiftui/environmentvalues/accessibilityreducemotion).
- [Material Design 3 in Compose](https://developer.android.com/develop/ui/compose/designsystems/material3), [Custom design systems in Compose](https://developer.android.com/develop/ui/compose/designsystems/custom) y [el codelab de theming](https://developer.android.com/codelabs/jetpack-compose-theming), con `Color.kt`, `Type.kt` y `Theme.kt` en `ui/theme`.
- [Accessibility API defaults in Compose](https://developer.android.com/develop/ui/compose/accessibility/api-defaults): 48 dp, según las guías de accesibilidad de Material.
- [Android 14 features](https://developer.android.com/about/versions/14/features): escala de fuente no lineal hasta el 200 % y texto en `sp`.

Las cifras se contrastaron con esas páginas. Los comandos de `simctl` se comprobaron con su ayuda; los de `adb` no se probaron en un dispositivo. Que la plantilla de Android Studio active el color dinámico consta en fuentes secundarias; la documentación oficial muestra el código, pero no el valor de la plantilla.
