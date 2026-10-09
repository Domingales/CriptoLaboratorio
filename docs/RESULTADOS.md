# Resultados del laboratorio independiente

Estado: prueba histórica. Integración en CriptoAnálisis Multi desactivada.
No se ha demostrado un 100 % de aciertos ni una mejora universal.

## Conclusiones

- ADA 1h: XGBoost acertó las 2 señales seleccionadas (100 % observado). Con sólo dos casos, no demuestra fiabilidad futura.
- SOL 1h: el filtro sobre Kotlin obtuvo 58,33 % con 36 señales frente a 51,89 % del motor sin filtro. La media neta del filtro fue -0,064 % por escenario: más aciertos no bastan para cubrir costes.
- ETH 4h: el filtro sobre EMA obtuvo 65 % en 20 casos resueltos (21 señales totales), con media neta +0,184 %. Muestra pequeña; indicio exploratorio, no mejora general demostrada.
- Muchos candidatos no emitieron señales con el umbral fijado. Se conserva el rechazo.
- Se evalúan las 15 combinaciones principales. El filtro adicional sobre Kotlin diario tiene menos de los 100 ejemplos de aprendizaje exigidos en 5 combinaciones y no se entrena.
- No se integra ningún cambio en la app actual.

Velas de 2022 sólo inicializan indicadores. El modelo aprende únicamente en 2023; enero–junio 2024 calibra, julio–diciembre 2024 valida; 2025–septiembre 2026 es el examen reservado.
Modelos congelados, umbral 60 %, escenarios simétricos con coste total 0,20 %. No son operaciones spot ejecutadas.
La precisión de barrera excluye neutras y ambiguas; la tasa de escenarios netos positivos incluye neutras. No debe confundirse ninguna con certeza futura.

| Moneda | Intervalo | Motor | Señales | Aciertos | Fallos | Neutras | No evaluables | Precisión | Media neta |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|
| BTC | 1h | ema | 1177 | 522 | 574 | 81 | 0 | 47.63 % | -0.23 % |
| BTC | 1h | xgboost | 7 | 4 | 3 | 0 | 0 | 57.14 % | -0.22 % |
| BTC | 1h | meta | 12 | 5 | 5 | 2 | 0 | 50.00 % | 0.12 % |
| BTC | 1h | original | 550 | 259 | 273 | 18 | 0 | 48.68 % | -0.22 % |
| BTC | 1h | original_meta | 0 | 0 | 0 | 0 | 0 | — | — |
| BTC | 4h | ema | 546 | 246 | 225 | 75 | 0 | 52.23 % | -0.18 % |
| BTC | 4h | xgboost | 0 | 0 | 0 | 0 | 0 | — | — |
| BTC | 4h | meta | 0 | 0 | 0 | 0 | 0 | — | — |
| BTC | 4h | original | 261 | 116 | 112 | 33 | 0 | 50.88 % | -0.19 % |
| BTC | 4h | original_meta | 0 | 0 | 0 | 0 | 0 | — | — |
| BTC | 1d | ema | 106 | 39 | 45 | 22 | 0 | 46.43 % | -0.36 % |
| BTC | 1d | xgboost | 0 | 0 | 0 | 0 | 0 | — | — |
| BTC | 1d | meta | 22 | 8 | 10 | 4 | 0 | 44.44 % | -0.71 % |
| BTC | 1d | original | 55 | 26 | 19 | 10 | 0 | 57.78 % | -0.01 % |
| ETH | 1h | ema | 1177 | 556 | 557 | 63 | 1 | 49.96 % | -0.22 % |
| ETH | 1h | xgboost | 0 | 0 | 0 | 0 | 0 | — | — |
| ETH | 1h | meta | 95 | 46 | 43 | 6 | 0 | 51.69 % | -0.17 % |
| ETH | 1h | original | 529 | 266 | 248 | 15 | 0 | 51.75 % | -0.21 % |
| ETH | 1h | original_meta | 0 | 0 | 0 | 0 | 0 | — | — |
| ETH | 4h | ema | 546 | 242 | 233 | 71 | 0 | 50.95 % | -0.17 % |
| ETH | 4h | xgboost | 0 | 0 | 0 | 0 | 0 | — | — |
| ETH | 4h | meta | 21 | 13 | 7 | 1 | 0 | 65.00 % | 0.18 % |
| ETH | 4h | original | 246 | 124 | 98 | 24 | 0 | 55.86 % | -0.05 % |
| ETH | 4h | original_meta | 0 | 0 | 0 | 0 | 0 | — | — |
| ETH | 1d | ema | 106 | 49 | 29 | 28 | 0 | 62.82 % | 0.87 % |
| ETH | 1d | xgboost | 8 | 4 | 2 | 2 | 0 | 66.67 % | 0.66 % |
| ETH | 1d | meta | 16 | 5 | 8 | 3 | 0 | 38.46 % | -1.21 % |
| ETH | 1d | original | 35 | 15 | 12 | 8 | 0 | 55.56 % | -0.64 % |
| ADA | 1h | ema | 1177 | 582 | 560 | 35 | 0 | 50.96 % | -0.17 % |
| ADA | 1h | xgboost | 2 | 2 | 0 | 0 | 0 | 100.00 % | 1.79 % |
| ADA | 1h | meta | 1 | 0 | 1 | 0 | 0 | 0.00 % | -2.41 % |
| ADA | 1h | original | 551 | 275 | 272 | 4 | 0 | 50.27 % | -0.19 % |
| ADA | 1h | original_meta | 0 | 0 | 0 | 0 | 0 | — | — |
| ADA | 4h | ema | 546 | 232 | 243 | 71 | 0 | 48.84 % | -0.36 % |
| ADA | 4h | xgboost | 0 | 0 | 0 | 0 | 0 | — | — |
| ADA | 4h | meta | 0 | 0 | 0 | 0 | 0 | — | — |
| ADA | 4h | original | 255 | 113 | 114 | 28 | 0 | 49.78 % | -0.19 % |
| ADA | 4h | original_meta | 0 | 0 | 0 | 0 | 0 | — | — |
| ADA | 1d | ema | 106 | 48 | 41 | 17 | 0 | 53.93 % | 0.14 % |
| ADA | 1d | xgboost | 4 | 2 | 1 | 1 | 0 | 66.67 % | 1.16 % |
| ADA | 1d | meta | 29 | 9 | 13 | 7 | 0 | 40.91 % | -0.64 % |
| ADA | 1d | original | 32 | 17 | 13 | 2 | 0 | 56.67 % | 0.58 % |
| SOL | 1h | ema | 1177 | 553 | 589 | 35 | 0 | 48.42 % | -0.27 % |
| SOL | 1h | xgboost | 7 | 2 | 5 | 0 | 0 | 28.57 % | -1.22 % |
| SOL | 1h | meta | 1 | 0 | 1 | 0 | 0 | 0.00 % | -2.90 % |
| SOL | 1h | original | 566 | 288 | 267 | 11 | 0 | 51.89 % | -0.14 % |
| SOL | 1h | original_meta | 36 | 21 | 15 | 0 | 0 | 58.33 % | -0.06 % |
| SOL | 4h | ema | 546 | 278 | 223 | 45 | 0 | 55.49 % | 0.06 % |
| SOL | 4h | xgboost | 0 | 0 | 0 | 0 | 0 | — | — |
| SOL | 4h | meta | 1 | 0 | 0 | 1 | 0 | — | -1.26 % |
| SOL | 4h | original | 258 | 125 | 116 | 17 | 0 | 51.87 % | -0.15 % |
| SOL | 4h | original_meta | 0 | 0 | 0 | 0 | 0 | — | — |
| SOL | 1d | ema | 106 | 41 | 44 | 21 | 0 | 48.24 % | -0.23 % |
| SOL | 1d | xgboost | 32 | 15 | 14 | 3 | 0 | 51.72 % | -0.16 % |
| SOL | 1d | meta | 2 | 0 | 2 | 0 | 0 | 0.00 % | -4.77 % |
| SOL | 1d | original | 37 | 21 | 14 | 2 | 0 | 60.00 % | 1.32 % |
| XRP | 1h | ema | 1177 | 561 | 570 | 46 | 0 | 49.60 % | -0.22 % |
| XRP | 1h | xgboost | 233 | 108 | 107 | 18 | 0 | 50.23 % | -0.19 % |
| XRP | 1h | meta | 0 | 0 | 0 | 0 | 0 | — | — |
| XRP | 1h | original | 558 | 276 | 268 | 14 | 0 | 50.74 % | -0.19 % |
| XRP | 1h | original_meta | 0 | 0 | 0 | 0 | 0 | — | — |
| XRP | 4h | ema | 546 | 246 | 228 | 72 | 0 | 51.90 % | -0.21 % |
| XRP | 4h | xgboost | 4 | 2 | 2 | 0 | 0 | 50.00 % | -0.20 % |
| XRP | 4h | meta | 0 | 0 | 0 | 0 | 0 | — | — |
| XRP | 4h | original | 251 | 120 | 108 | 23 | 0 | 52.63 % | -0.19 % |
| XRP | 4h | original_meta | 0 | 0 | 0 | 0 | 0 | — | — |
| XRP | 1d | ema | 106 | 40 | 42 | 24 | 0 | 48.78 % | -0.10 % |
| XRP | 1d | xgboost | 24 | 9 | 9 | 6 | 0 | 50.00 % | 0.74 % |
| XRP | 1d | meta | 0 | 0 | 0 | 0 | 0 | — | — |
| XRP | 1d | original | 26 | 16 | 8 | 2 | 0 | 66.67 % | 1.32 % |

## Límites de la comparación
- La referencia EMA no es el motor Android. La comparación Kotlin adicional corresponde al snapshot de investigación identificado por hashes, con su excepción auditada para datos futuros ausentes.
- Las implementaciones de ATR/indicadores Python y Kotlin no son idénticas. La comparación de señales es exploratoria: exige paridad adicional antes de integrar.
- No hay noticias históricas, funding, profundidad de libro ni simulación de cartera spot. La tasa de acierto por sí sola no demuestra rentabilidad.
- El examen histórico no sustituye un registro prospectivo. Las fechas previas ya pudieron influir indirectamente en decisiones de investigación anteriores.
- Se repitió el examen tras corregir la falta de calentamiento de indicadores (2022). No se cambiaron umbrales ni parámetros según los resultados, pero el examen ya observado no es un registro prospectivo independiente.
- No se ha probado físicamente la APK ni el navegador/PWA del móvil.

## Combinaciones no evaluables
Ninguna combinación excluida por completo. Los casos ambiguos y ausentes figuran en la tabla.

## Modelos adicionales no evaluables
- BTC 1d · filtro sobre motor Kotlin: aprendizaje 67, calibración 146. Insufficient training/calibration samples or classes
- ETH 1d · filtro sobre motor Kotlin: aprendizaje 70, calibración 142. Insufficient training/calibration samples or classes
- ADA 1d · filtro sobre motor Kotlin: aprendizaje 72, calibración 147. Insufficient training/calibration samples or classes
- SOL 1d · filtro sobre motor Kotlin: aprendizaje 68, calibración 136. Insufficient training/calibration samples or classes
- XRP 1d · filtro sobre motor Kotlin: aprendizaje 72, calibración 136. Insufficient training/calibration samples or classes
