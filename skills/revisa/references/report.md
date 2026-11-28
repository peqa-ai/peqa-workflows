# Informe consolidado

El padre prepara el informe final después de adjudicar los hallazgos. Toda revisión (`lite` o `deep`, local o de PR) usa la misma estructura escaneable: abre con encabezado, recomendación y evaluación de mínimos; después presenta hallazgos materiales, adjudicaciones del padre, evidencia de pruebas, blast radius, seguridad y trazabilidad. Un resultado de un subagente solo cubre su encargo y no sustituye el consolidado.

Prepara el registro estructurado con `depth` (`lite` o `deep`), conserva la captura del estado probado y ejecuta [los validadores portables](../../../references/checks-and-hooks.md#validar-el-consolidado-y-su-evidencia) antes de entregar o publicar. El render del helper garantiza conservar el encabezado y evita contradicciones entre mínimos y recomendación. Un registro válido puede recomendar cambios o declarar revisión incompleta; el helper no demuestra que los tests declarados se ejecutaron.

## Recomendación y mínimos

Evalúa cuatro criterios para el alcance revisado: requisitos acordados, validación funcional pertinente, controles de seguridad aplicables y compatibilidad de los componentes afectados. Cada criterio indica `cumple`, `no cumple`, `no verificado` o `no aplica`, con evidencia o justificación. Define los mínimos desde el encargo, las reglas del proyecto y, en `deep`, [la revisión de seguridad](security.md); no añadas mejoras opcionales como condiciones de aprobación. En `lite`, `seguridad aplicable` puede ser `no aplica` con justificación de profundidad `lite` si no se observan defectos obvios, o `no cumple` si aparece un defecto de seguridad material.

La evaluación global es `no cumple` si hay un incumplimiento material demostrado; si no lo hay pero queda evidencia material pendiente, es `no verificado`. Solo es `cumple` cuando todos los mínimos aplicables tienen evidencia suficiente. `No aplica` exige una razón y no cuenta como una comprobación aprobada. No uses puntuaciones o porcentajes inventados ni promedies un fallo de seguridad con otros resultados favorables.

| Recomendación en español | En inglés | Condición |
| --- | --- | --- |
| Aprobación sugerida | Approval recommended | Mínimos cumplidos, sin hallazgos materiales abiertos ni cobertura material pendiente. Equivale a listo dentro del alcance comprobado. |
| Cambios requeridos | Changes required | Incumplimiento material demostrado. Incluye también las comprobaciones pendientes, si las hay. |
| Revisión incompleta | Review incomplete | Falta evidencia, acceso o una revisión independiente necesaria para decidir; no se ha demostrado un incumplimiento que ya exija cambios. |

Aplica los criterios de [pruebas e impacto](validation.md). Los tests fallidos o las carencias materiales impiden sugerir aprobación. El encabezado expresa una recomendación de IA; no afirma una aprobación humana ni registra un evento `APPROVE` en GitHub.

Si hay varios PRs, muestra el estado y revisión exacta de cada uno. El consolidado exige cambios si alguno tiene un incumplimiento material; en ausencia de estos, queda incompleto si falta cobertura material en cualquier componente requerido. Un hijo aprobado no vuelve aprobado al conjunto.

## Plantilla adaptable

Usa el idioma de la conversación o del informe solicitado. Adapta Markdown a texto plano o a los campos del cliente conservando el orden del encabezado y las secciones. Esta plantilla sirve en T3 Code, Orca, Codex y Claude Code sin herramientas de publicación.

```markdown
# Review consolidado: {recomendación}
*Generado por IA en nombre de {persona solicitante identificada}.*

**Mínimos del cambio:** {cumple / no cumple / no verificado}
**Profundidad:** `{lite | deep}`
**Alcance:** {URL del PR o repositorio} (`{base}..{head}`)
**Modelo y esfuerzo:** solicitado {modelo/esfuerzo}; efectivo {modelo/esfuerzo o desconocido}
**Presupuesto:** `CR n/3`
**Motivo:** {razón principal y bloqueo o límite relevante}

| Criterio | Evaluación | Evidencia o pendiente |
| --- | --- | --- |
| Requisitos acordados | {estado} | {requisito y comprobación} |
| Validación funcional | {estado} | {pruebas pertinentes y resultado} |
| Seguridad aplicable | {estado} | {versiones, controles y cobertura; o alcance `lite` justificado} |
| Compatibilidad e impacto | {estado} | {consumidores, contratos e incertidumbre} |

## Alcance capturado
{Cobertura de la captura y, por repositorio, HEAD, índice, worktree y cambios locales.}

## Hallazgos materiales y adjudicaciones
{Diagrama antes/después del cambio, si modifica comportamiento.}
- {ID}: {estado} [material, {severidad}] `{archivo:línea}`. {evidencia}
  - Condiciones: {cuándo ocurre}
  - Impacto: {efecto material}
  - Corrección mínima: {cambio necesario}
  - Flujo / pantalla visible: {cómo se observa; screenshot o diagrama debajo}
  - Adjudicación del padre: {aceptado / descartado / no resuelto y razón con evidencia}
{O: Sin hallazgos materiales dentro del alcance.}

## Evidencia de pruebas
{Tabla o lista por repositorio: revisión, comando, cwd, estado, salida observada y cobertura pendiente.}

## Alcance del impacto (blast radius)
{Impacto acotado, compartido, amplio o indeterminado; consumidores, datos, reversibilidad e incertidumbre.}

## Evidencia de seguridad
{En `deep`: matriz OWASP Top 10 y NIST SSDF con ediciones verificadas, controles y límites. En `lite`: nota de omisión de auditoría completa o detalle del defecto obvio encontrado.}

## Trazabilidad
{Profundidad, modelo de sesión si fue expuesto, modelo y esfuerzo solicitados y efectivos, ruta, fallback si lo hubo, fuentes de evidencia y `CR n/3` por PR.}
```

Resuelve la persona solicitante desde su indicación explícita o una identidad de sesión verificada. No la deduzcas del autor del PR, del último commit, de `git user.name` o de la cuenta CLI autenticada. Si no está identificada, usa `Generado por IA. Persona solicitante no identificada.` y continúa. La atribución identifica quién pidió el informe, no quién lo aprobó. En inglés usa `Consolidated review` y `AI-generated on behalf of …`, con el mismo criterio de identidad.

La plantilla sigue la salida de `render`; si difieren, manda el helper. Sustituye todos los campos antes de entregar. Mantén el resumen breve y enlaza evidencia extensa; conserva los fallos y límites aunque el cliente solo admita texto plano.

El render del helper escapa el Markdown de los campos del registro. Inserta la [evidencia visual](../../../references/visual-evidence.md#en-el-review) en el Markdown renderizado: el diagrama del cambio al inicio de «Hallazgos materiales y adjudicaciones» y cada imagen o diagrama debajo de su hallazgo, identificado por su ID. El resto del texto queda igual; la copia publicable solo aplica las reglas de [Publicar en el PR](#publicar-en-el-pr).

## Publicar en el PR

Invocar `revisa` autoriza publicar el consolidado en el PR del cambio, sin otra pregunta. El PR es el de la URL que dio el usuario o el que devuelva `gh pr view --json url` en la rama revisada.

- **Si no existe un PR aún:** conserva el informe consolidado y el registro en local.
- **Si ya existe un PR:** publica el informe consolidado estandarizado en el PR y conserva también el registro en local.
- **Si el usuario pidió no publicar:** conserva ambos en local y dilo en la entrega.

`python3 "$REVIEW_PLAN_SCRIPT" publish-plan --pr-url "$PR_URL"` devuelve el destino, el evento y el endpoint de esa URL. Añade `--direct-pr` en la revisión directa y `--public-repo` si el repositorio es público. `REVIEW_PLAN_SCRIPT` apunta a `scripts/review_plan.py` de este skill.

Reglas obligatorias antes de publicar:

1. Prepara una copia publicable del consolidado ya adjudicado. Conserva encabezado, profundidad, atribución, recomendación, mínimos, hallazgos, adjudicaciones y evidencia técnica y visual. En «Alcance», sustituye cualquier ruta local por la URL del PR y las revisiones `base..head`. GitHub admite hasta 65 536 caracteres por cuerpo: enlaza la evidencia extensa.
2. **Seguridad en repositorios públicos:** comprueba la visibilidad con `gh repo view "$OWNER/$REPO" --json visibility`; si no puedes comprobarla, trátalo como público. Nunca publiques detalles de explotación, payloads ni pasos reproducibles de una vulnerabilidad de seguridad en un repositorio público. Redacta únicamente el impacto de alto nivel sin vector de ataque y propón al usuario abrir un aviso privado de seguridad (GitHub Security Advisory).
3. **Solo comentarios (`COMMENT`):** publica siempre con evento `COMMENT`. Nunca envíes `APPROVE` ni `REQUEST_CHANGES` de forma automática; esas acciones requieren una petición explícita de la persona.
4. **Sin doble publicación:** realiza una sola publicación por consolidado. Si una llamada termina sin respuesta clara, consulta las revisiones y comentarios del PR antes de reintentar.
   - En revisión estándar de un PR sin comentarios en línea, usa `gh api "repos/$OWNER/$REPO/pulls/$PR_NUMBER/reviews" --method POST -f event=COMMENT -F body=@"$INFORME"` (o `gh pr comment "$PR_URL" --body-file "$INFORME" --attach ...` cuando el informe incluya capturas locales para subir según [evidencia visual en el PR](../../../references/visual-evidence.md#en-el-pr)). No ejecutes ambos para el mismo consolidado. Si el PR no está en github.com, añade `--hostname "$PR_HOST"` a `gh api`.
   - En revisión directa por URL de PR, usa la sección siguiente para enviar en una sola revisión el resumen general y los comentarios en línea.
5. Comprueba después de publicar que la revisión o comentario existe, que las imágenes subidas cargan si las hubo y que el texto no contiene rutas locales. Entrega la URL publicada junto con el resumen de sesión.

## Revisión directa por URL de PR

Aplica cuando el usuario invoca directamente `/revisa <URL-del-PR>` o `$revisa <URL-del-PR>` (por ejemplo `revisa https://github.com/owner/repo/pull/123`). Es una revisión de solo lectura sobre ese PR: no edites ni empujes a su rama salvo que el usuario lo pida.

1. Valida la URL completa HTTPS y resuelve `owner`, `repo`, número, base y head con `gh pr view "$PR_URL" --json baseRefName,headRefOid`. `$PR_HEAD_SHA` es el `headRefOid` completo; el helper rechaza un SHA abreviado. Guarda el diff con `gh pr diff "$PR_URL" > "$PR_DIFF"`. Revisa sobre un checkout en ese head; si el actual no lo es, usa un worktree aparte sin tocar el trabajo en curso, o declara en el informe que la revisión cubrió solo el diff. Ejecuta la selección de modelo y profundidad y respeta el presupuesto `CR n/3` de ese PR.
2. Ejecuta la revisión adversarial y adjudica los hallazgos. Los comentarios en línea llevan los hallazgos materiales abiertos; los resueltos, descartados y no materiales quedan solo en el consolidado.
3. Construye el payload determinista con el helper incluido para separar hallazgos en líneas exactas del diff (lado `RIGHT`) de los hallazgos fuera del diff:

```sh
python3 "$REVIEW_PLAN_SCRIPT" pr-review-payload \
  --pr-url "$PR_URL" \
  --head "$PR_HEAD_SHA" \
  --summary-file "$INFORME_GENERAL" \
  --findings-file "$HALLAZGOS_JSON" \
  --diff-file "$PR_DIFF" \
  --local-root "$REVIEW_REPO" > "$REVIEW_PAYLOAD_WRAPPER"
```

`$INFORME_GENERAL` es la copia publicable del consolidado. `$HALLAZGOS_JSON` es el registro estructurado del consolidado o solo su lista `findings`. Añade `--public-repo` si el repositorio es público y `--language en` para un informe en inglés. Marca con `"security_exploitable": true` cada hallazgo de seguridad explotable.

El helper valida cada `(path, line)` contra los hunks del diff, evita duplicados, sustituye la raíz local, fija `"event": "COMMENT"` y mueve automáticamente al resumen general (`body`) cualquier hallazgo fuera del diff, en una línea eliminada o sin línea, explicando que GitHub no admite ahí comentarios en línea. Antes de publicar, deja vacías dos listas de su salida y vuelve a generar el payload:

- `redaction_required_ids`: hallazgos explotables en un repositorio público. Reescribe su texto según la regla 2.
- `local_path_hits`: rutas que aún parecen locales. Sustitúyelas, salvo que sean rutas del propio código revisado.

Si el head del PR cambió desde el paso 1, repite el diff y el payload sobre el head nuevo.

4. **Publica una sola revisión** según el entorno (elige una única ruta, nunca las dos, para evitar doble publicación):

   - **Ruta portable con GitHub CLI (`gh`):** envía el objeto `payload` en una sola llamada que incluye el resumen general (`body`) y los comentarios en línea (`comments: [{path, line, side: "RIGHT", body}]`). Si el PR no está en github.com, añade `--hostname "$PR_HOST"`:

     ```sh
     python3 -c 'import json, sys; print(json.dumps(json.load(sys.stdin)["payload"]))' \
       < "$REVIEW_PAYLOAD_WRAPPER" \
       | gh api "repos/$OWNER/$REPO/pulls/$PR_NUMBER/reviews" --method POST --input -
     ```

   - **Ruta Orca cuando el agente fue despertado por un evento en ese PR:** usa `orca bot reply` con el resumen general en un archivo y un `--note` por cada entrada de `orca_notes`, copiada tal cual:

     ```sh
     python3 -c 'import json, sys; sys.stdout.write(json.load(sys.stdin)["payload"]["body"])' \
       < "$REVIEW_PAYLOAD_WRAPPER" > "$REVIEW_BODY"
     "$ORCA" bot reply --text-file "$REVIEW_BODY" \
       --note "src/auth.py:42:[F1/high] Falta validar el tenant en la consulta. Fix: filtrar por tenant_id del token."
     ```

     `"$ORCA" bot reply --help` indica cuántas notas admite una respuesta; si `orca_notes` trae más, usa la ruta `gh`.

5. Confirma que la revisión quedó publicada con su resumen general y sus comentarios en línea, sin rutas locales y sin haber enviado `APPROVE` ni `REQUEST_CHANGES`. Conserva el registro local y entrega la URL de la revisión al usuario.
