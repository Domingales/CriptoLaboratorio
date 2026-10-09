# Cripto · Laboratorio predictivo

App web instalable independiente para comprobar pronósticos sobre velas oficiales desde 2023. Tema negro y dorado. No modifica CriptoAnálisis Multi ni ejecuta operaciones.

## Abrir la app

1. Descomprime el proyecto.
2. Abre `dist/index.html`. Incluye un informe autónomo para revisar resultados sin servidor.
3. Para instalarla en el móvil, publica `dist/` en GitHub Pages mediante el workflow **Publicar app web**. Abre su URL HTTPS y utiliza **Instalar app** o la opción del navegador **Añadir a pantalla de inicio**. La instalación y el uso sin conexión en el dispositivo están pendientes de prueba física.

La app muestra resultados existentes, velas, señales y el último pronóstico **histórico**, con fecha visible. No obtiene cotizaciones actuales. El motor Python permite reproducir las predicciones; abrir la web no reentrena los modelos.

## Reproducir el experimento

Requiere Python 3.12 y Java 17 para el contraste Kotlin. En Windows, abre una terminal en esta carpeta:

```powershell
py -3.12 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
python -m research.download --data data
python -m research.experiment
python -m research.native_reference
python -m research.package_results
```

Alternativamente, usa **Experimento reproducible** en GitHub Actions. No requiere claves de exchanges. Guarda informes y la app como artefactos; no integra código en otro repositorio.

## Ejecución automática preparada

El workflow se ejecuta cada domingo a las 03:17 UTC y también al modificar el motor o sus pruebas en `main`. GitHub puede retrasar la hora programada. La programación sólo estará activa una vez publicado este repositorio con Actions habilitado; el archivo local no ejecuta tareas por sí mismo.

Cada tanda descarga hasta el último mes completo disponible, verifica las fuentes, reproduce las 15 combinaciones, contrasta Kotlin, ejecuta los 210 filtros exploratorios y exige los controles de integridad. Los archivos de cada ejecución se conservan 30 días en Actions. Los datos nuevos se incorporan al ampliar el corte mensual; una repetición dentro del mismo mes no genera evidencia nueva. No cambia automáticamente los parámetros, no diseña otros experimentos ni actualiza producción o la web publicada. Si falta un archivo oficial o falla una combinación, la ejecución debe quedar fallida y conservar sus resultados parciales.

## Protocolo

`docs/protocol.json` fija fechas, modelos, umbral, costes y horizonte antes del examen. BTC, ETH, ADA, SOL y XRP × 1h, 4h y diario. Aprendizaje 2023; calibración enero–junio 2024; validación julio–diciembre 2024; examen enero 2025–septiembre 2026.

Modelos: referencia EMA20/50, XGBoost direccional, referencia EMA con filtro XGBoost y un filtro exploratorio sobre las señales aceptadas del motor Kotlin. Los modelos quedan congelados tras calibrar; no se reajustan sus parámetros al ver el examen. El filtro de situaciones poco representadas usa solamente el rango de variables del aprendizaje.

Las velas de 2022 se descargan sólo para inicializar indicadores y contexto. Los modelos nuevos aprenden únicamente con etiquetas de 2023. Ver `docs/data-preparation-corrections.md`: se repitió la reconstrucción tras corregir la preparación, sin cambiar parámetros ni umbrales. El resultado no se presenta como registro prospectivo independiente.

Señal al cierre; entrada en la apertura siguiente. Triple barrera: objetivo e invalidación simétricos a 1 ATR (mínimo 0,4 %), más un plazo fijo. Primer toque con velas 5m completas. Ambas barreras en una misma vela sin orden conocido = AMBIGUA. Huecos = NO EVALUABLE. Los stops con salto de precio pueden ejecutarse peor que el nivel. Coste total fijo de 20 puntos básicos, con sensibilidad a 10 y 40.

Los episodios no se solapan: el cooldown dura siempre todo el horizonte, aunque el resultado se conozca antes. Por tanto, el recorrido futuro no cambia la selección de señales anteriores.

## Alcance del contraste Kotlin

`native/` conserva los componentes matemáticos de la rama de investigación del repositorio original y su adaptador previamente auditado. `docs/native-source-hashes.json` identifica commit y SHA256. El adaptador conserva una excepción documentada frente a `BacktestEngine`: corrige la influencia de la disponibilidad futura de velas sobre el cooldown. `NativeAudit.kt` comprueba paridad en datos completos y esa independencia temporal.

La evaluación Kotlin adicional aplica una regla común de resultados al motor original de investigación. ATR y algunos indicadores difieren entre Kotlin y Python: los resultados son exploratorios y no demuestran paridad completa. No se ha compilado ni probado físicamente una nueva APK.

## Antes de integrar cualquier cambio

No se ha demostrado un 100 % de aciertos, un 100 % de mejora ni una ventaja universal. No se integra automáticamente. Exigir comparación emparejada con el motor y configuración reales, equivalencia de indicadores y objetivos, suficiente muestra, mejora de aciertos y utilidad neta, sensibilidad a costes, estabilidad por régimen, ajuste por selección múltiple y registro prospectivo nuevo. El estudio histórico ya observado no puede volver a etiquetarse como examen independiente tras cambiar parámetros.

Ver `docs/RESULTADOS.md` y `dist/data/comparison.csv`. La precisión excluye neutras; también se muestran sus cantidades, no evaluables, tasa neta positiva, intervalos de confianza y cobertura. Los escenarios simétricos BUY/SELL no son una simulación de cartera spot.

## Archivos

- `dist/`: app web autónoma, PWA, gráficos, exportación y resultados.
- `research/`: descarga, auditoría, modelos, calibración, evaluación y publicación de informes.
- `tests/`: controles de integridad y ausencia de información futura.
- `native/`: copia de investigación Kotlin y pruebas del adaptador.
- `docs/`: protocolo, hashes, resultados y límites.
- `.github/workflows/`: experimentos y publicación manual en GitHub Pages.

Los datos descargados, dependencias JVM y modelos locales no se suben a GitHub. No hay cuentas, claves, secretos ni cambios de Firebase/Cloudflare.

Fuentes: [Binance Public Data](https://github.com/binance/binance-public-data), [XGBoost](https://xgboost.readthedocs.io/), [Mlfin.py](https://mlfinpy.readthedocs.io/en/stable/Labelling.html), [FreqAI](https://www.freqtrade.io/en/stable/freqai/). Mlfin.py y FreqAI son referencias metodológicas; no se presentan como algoritmos de rentabilidad comprobada para este proyecto.
