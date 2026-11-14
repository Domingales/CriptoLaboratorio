# Protocolo de investigación — paradoja de Parrondo (v0.1)

Estado: **propuesto, no ejecutado**. Rama aislada: `research/parrondo-experiment`. No integrar en `main` ni modificar Android, Firebase, Cloudflare o los modelos actuales.

## Hipótesis falsable
Dos políticas A y B con rendimiento esperado neto negativo, evaluadas **sobre la misma secuencia temporal y con idéntica exposición y costes**, pueden producir una política alternada C con rendimiento esperado neto positivo debido a cambios en la distribución de estados. Si A o B son rentables por sí solas, una mejora de C no se clasificará como paradoja de Parrondo.

## Diseño predefinido
- Activos: BTC, ETH, ADA, SOL, XRP. Velas: 1h, 4h, 1d. Datos oficiales con auditoría de huecos.
- A: reversión a la media; B: seguimiento de tendencia. Las reglas exactas y sus umbrales deben registrarse y congelarse **antes** de consultar el examen.
- C1: alternancia determinista AABB; C2: alternancia por estado observable al cierre de vela. No se permite usar el resultado futuro para seleccionar juego.
- Control: A, B, alternancia aleatoria con semilla fija, mejor estrategia simple elegida sólo en validación y referencia EMA existente.
- Entrada como mínimo en apertura siguiente; misma regla de salida, horizonte, capital, coste, deslizamiento y restricción de posiciones para todas las políticas. Distinguir simulación de venta corta de operativa spot.
- Divisiones cronológicas sin solapamiento ni fuga: entrenamiento, calibración/selección, examen intocable y posterior seguimiento prospectivo.
- Comparación emparejada por activo, intervalo y fecha; intervalos de confianza mediante bloques temporales, sensibilidad a costes y corrección por múltiples pruebas.
- Métricas: beneficio neto, factor de beneficio, máximo drawdown, cobertura, operaciones, acierto direccional y acierto de objetivo/plazo por separado.
- Declarar **NO EVALUABLE** ante datos insuficientes, barreras ambiguas, datos faltantes o muestra inadecuada.
- Criterio de evidencia: A<0, B<0 y C>0 netos en examen, con robustez temporal y suficiente evidencia estadística; no inferir rentabilidad futura garantizada.

## Condiciones de ejecución
1. Resolver primero las incidencias de infraestructura del workflow principal sin cambiar parámetros para favorecer resultados.
2. Implementar código y pruebas independientes en esta rama. No activar el workflow dominical principal desde la rama.
3. Registrar reglas y hashes de datos antes de correr el examen.
4. Publicar resultados completos, incluidos negativos y no evaluables.

## Incidencia previa verificada
El workflow `experiment.yml` del 8 de noviembre de 2026 (run 42471242640) terminó en fallo durante `python -m research.native_reference`, con `urllib.error.HTTPError: HTTP Error 504: Gateway Time-out`. El resumen de ese run enumera 15 combinaciones COMPLETE, pero esto **no** equivale a una ejecución completa y verificada: las etapas posteriores al fallo no se ejecutaron. No repetir automáticamente ni afirmar que pasó las pruebas.
