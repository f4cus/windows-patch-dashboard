# Revisión de exactitud: octubre de 2026

Se regeneró `data/reports/2026-10.json` mediante `collect --month 2026-10`,
conservando las correcciones locales de fechas, aplicabilidad, enlaces oficiales y
separación de ramas Windows 11. Durante el diagnóstico y la corrección no se realizó
commit, push ni despliegue.

## Causas y corrección

El [CVRF oficial de octubre](https://api.msrc.microsoft.com/cvrf/v3.0/cvrf/2026-Oct)
contiene KB5126835, KB5126836 y KB5126868. Los dos rollups ESU tienen subtipo
`Security Update`; el filtro anterior exigía `Monthly Rollup` y los descartaba antes
de verificar Support. Ahora se conservan esos candidatos y se exige que Support
confirme Monthly Rollup y producto. Una clasificación ESU genérica sin evidencia
suficiente hace fallar la recolección, sin emitir un falso `NO PUBLICADO`.

CVRF también etiqueta KB5126649 como `Security Update`. El desempate anterior
aceptaba un artículo parseable con fecha y producto correctos, sin comprobar el tipo
de paquete. Por eso una SSU podía ganar cuando no se recuperaba el artículo de la
LCU. Ahora Support clasifica el paquete por su propio título: acumulativa, Monthly
Rollup, SSU, security-only, auxiliar o desconocido. Las referencias a prerrequisitos
en el cuerpo no clasifican el paquete principal. SSU, security-only y auxiliares
verificados se excluyen; un tipo desconocido no puede resolver un empate.

D001 mantiene CVRF como descubrimiento principal. No se añadió un crawler de
Catalog ni descubrimiento mensual desde historiales. El índice oficial de Server
y Catalog se consultaron como contraste independiente; las rutas oficiales
`/help/` resolvieron los artículos esperados en esta ejecución. D004 documenta la
clasificación y el requisito de tipo principal, fecha y producto para desempatar.
No se modificó el contrato JSON ni se añadieron dependencias o exclusiones por KB.

## Registros y procedencia

Los diez registros tienen fecha `2026-10-13`, `updateType: security`,
`supersededBy: null` y fuentes CVRF + Microsoft Support con timestamps reales.
Se revisaron título, fecha, tipo y Applies To de los nueve artículos distintos.
El JSON contiene los enlaces canónicos recuperados.

| Sistema | Antes | JSON regenerado | Verificación |
| --- | --- | --- | --- |
| Server 2012 ESU | NO PUBLICADO | KB5126835 | Support: Monthly Rollup, producto ESU; Catalog: Security Monthly Quality Rollup |
| Server 2012 R2 ESU | NO PUBLICADO | KB5126836 | Support: Monthly Rollup, producto ESU; Catalog: Security Monthly Quality Rollup |
| Server 2016 | KB5126649 (SSU) | KB5126868 | Support e índice Server: OS Build 14393.9612; Catalog: Cumulative Update |
| Server 2019 | KB5126651 | KB5126651 | Support: OS Build 17763.9376 |
| Server 2022 | KB5126655 | KB5126655 | Support: OS Build 20348.5761 |
| Server 2025 | KB5126646 | KB5126646 | Support: OS Build 26100.33650 |
| Windows 11 23H2 | KB5126653 | KB5126653 | Support: OS Build 22621.7652 |
| Windows 11 24H2/25H2 | KB5127648 | KB5127648 | Support: OS Builds 26300.9711, 26200.9711, 26100.9711 |
| Windows 11 26H1 | KB5127646 | KB5127646 | Support: OS Build 28000.3231 |
| Windows 11 26H2 | KB5127648 | KB5127648 | Mismo artículo; metadata CVRF diferente |

CVRF declara `Supercedence: 5124008` para KB5127648 en 24H2/25H2 y ningún
antecedente para 26H2. Se mantienen las dos filas según el contrato existente.
Ese antecedente histórico no crea un enlace `supersededBy` a un OOB de octubre.

La recolección verificó 30 KB candidatas, descartó 18 candidatos históricos
mediante fecha/producto de Support y excluyó tres SSU: KB5126649, KB5127357 y
KB5127356. No hay registros OOB de octubre en el resultado.

## Validación y limitaciones

- Cierre de selección: 96 tests enfocados y 204 tests Python completos.
- Cierre de clasificación: 99 tests enfocados; suite Python completa: 255 tests
  exitosos (51 regresiones nuevas para problemas conocidos).
- Ruff, format y mypy: correctos.
- JSON Schema y semántica: cuatro archivos validados.
- Frontend: npm ci, format, lint, typecheck, 50 tests y build correctos.
- `git diff --check`: correcto.
- Los errores iniciales de temporales pytest se resolvieron usando una carpeta
  temporal dentro del workspace; npm.cmd evitó el bloqueo del shim PowerShell.

La ejecución final quedó en estado `generated`: todos los candidatos tuvieron artículo
verificado y no quedaron estados desconocidos bajo las reglas actuales. Esto no
certifica exhaustividad editorial. Cuatro filas conservan un resumen de
correcciones no disponible: Server 2012, 2012 R2, 2016 y 2025; el parser no
identificó correcciones explícitas compatibles en esas publicaciones.

## Cierre de clasificación de problemas conocidos

Se reprodujo el defecto con fragmentos literales de los nueve artículos oficiales,
capturados con URL y timestamp en
`collector/tests/fixtures/microsoft-support-known-issues.json`. La afirmación de
resolución parcial y la indicación de otros síntomas pendientes devolvían
`resolved` porque el patrón anterior encontraba una resolución dentro del texto.

Ahora la evidencia explícita de resolución parcial, síntomas pendientes o trabajo
en una solución tiene prioridad y produce `open`. Una resolución completa requiere
una afirmación positiva; posibilidades futuras, falta de confirmación o evidencia
contradictoria producen `unknown`. `none` requiere ausencia de problemas expresamente
confirmada. Las descripciones históricas seguidas de resolución completa conservan
`resolved`; una mitigación que ya no se necesita no indica por sí sola un problema
pendiente. Para múltiples problemas, cualquiera abierto mantiene `open`; un problema
sin clasificación impide declarar que todos están resueltos.

| Estado | Antes del cierre | Reporte final |
| --- | --- | --- |
| open | 2 | 9 |
| resolved | 7 | 0 |
| none | 1 | 1 |
| unknown | 0 | 0 |
| not-published | 0 | 0 |

Las siete filas reclasificadas de `resolved` a `open` son Server 2012, 2012 R2,
2016, 2019 y Windows 11 24H2/25H2, 26H1 y 26H2. Corresponden a KB5126835,
KB5126836, KB5126868, KB5126651, KB5127646 y KB5127648 (dos filas). La fuente
oficial conserva resolución parcial y trabajo en otros síntomas en las seis KB.
Server 2022 y 2025 siguen `open`; Windows 11 23H2 sigue `none` con declaración
expresa de Microsoft.

La comparación fila por fila confirmó las diez KB, fechas, sistemas, tipos de
actualización, supersedencia y URLs de procedencia anteriores. Los resúmenes tampoco
cambiaron: las únicas diferencias de contenido son las siete etiquetas. Los
timestamps se actualizaron mediante la recolección real, sin editar manualmente
el reporte. Se preservan contrato JSON, selección, frontend, OOB y decisiones.

Una recolección CLI fue exitosa; una ejecución posterior recibió HTTP 403 en
`/es-es/help/5126835` y `/en-us/help/5126835`, rechazó la clasificación ESU incierta
y preservó el reporte válido. La recolección final utilizó la API existente
`collect_month` y el parámetro existente `fallback_urls` de `fetch_support_article`,
con URLs canónicas literales de la procedencia del reporte anterior. Se volvieron
a solicitar los artículos a Microsoft y se verificaron 30 de 30 candidatos;
se normalizó, validó y escribió mediante `write_report_atomic`. No se reutilizó
contenido cacheado para poblar el reporte ni se modificó la política permanente
de fuentes/reintentos. La disponibilidad de las rutas `/help/` sigue siendo un
riesgo externo observable.

Las reglas son reutilizables: no contienen KB ni fechas específicas. Los tests
incluyen evidencia real y casos sintéticos identificados como tales para equivalentes
en inglés/español, negaciones, resolución completa, parcial, incertidumbre y problemas
múltiples. Los controles existentes de CVRF, Support, OOB y conflictos siguen pasando.

Persisten riesgos externos: Microsoft puede cambiar HTML, idioma, redacción o
contenido de sus publicaciones; una publicación puede estar incompleta o temporalmente
inaccesible. Los patrones deterministas no interpretan cualquier redacción posible.
Para detectarlo pronto, revisar warnings y estados `unknown`/`partial` en cada refresh,
comparar las diferencias de estado y comprobar las secciones oficiales antes de
aceptar cambios a `resolved` o `none`. Conservar snapshots reproducibles y ampliar las
regresiones cuando aparezca una nueva formulación verificable. No se implementaron
reintentos adicionales, alertas ni cambios de calendario.

## Riesgo operativo pendiente: WPD-INC-003

La CLI usa el descubrimiento de enlaces configurado en producción; la recolección
manual mediante `collect_month` recibió explícitamente URLs canónicas de respaldo
desde la procedencia del reporte anterior. Ante HTTP 403 en `/help/`, esas dos
formas de invocación pueden disponer de enlaces diferentes y producir éxito o
fallo distintos. La clasificación y validación son las mismas; la diferencia está
en los enlaces disponibles para verificar Support. Se registra como pendiente,
sin implementar WPD-INC-003, reintentos, alertas ni cambios de calendario.

Los dos defectos de selección y el defecto de clasificación solicitado están
corregidos y validados. La implementación y el reporte fueron aprobados para
publicación, condicionada a revisar el diff, sincronizar con `origin/main` y
verificar CI, GitHub Pages y la aplicación pública.
