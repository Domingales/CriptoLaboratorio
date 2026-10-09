# CriptoLaboratorio: experimento 2 — filtros de señales

Se evaluaron 210 candidatos: 7 filtros × 5 criptomonedas × 3 intervalos × 2 motores (EMA y Kotlin de investigación). No se modificó la app original ni el conjunto de episodios de referencia. Un filtro únicamente acepta o rechaza señales ya existentes; no cambia su dirección ni genera entradas nuevas.

Los indicadores usan velas cerradas. Las cotas de volatilidad se calculan únicamente con 2023. La selección se hace con julio–diciembre de 2024: al menos 50 aciertos/fallos resueltos, conservar al menos el 10% de las señales, subir la precisión al menos 5 puntos porcentuales y obtener una media neta positiva con un coste total supuesto de 0,40%. Si hay varios candidatos válidos se escoge el de mayor media neta en validación. No se escoge el mejor resultado de 2025–2026.

Los datos de 2025–septiembre de 2026 ya se habían observado en la investigación V1. Este es un estudio exploratorio retrospectivo; NO es una confirmación prospectiva independiente.

## Candidatos seleccionados con 2024

| Caso / motor Kotlin | Filtro | Aciertos base en 2024 | Aciertos filtrados en 2024 | Aciertos base en 2025–2026 | Aciertos filtrados en 2025–2026 | Resueltos filtrados | Media neta base / filtrada |
|---|---|---:|---:|---:|---:|---:|---:|
| ADA 4h | normal_volatility | 54.93% | 60.00% | 49.78% | 50.00% | 186 | -0.385% / -0.361% |
| XRP 1h | trend200_adx20_volume120 | 50.62% | 58.21% | 50.74% | 48.47% | 196 | -0.392% / -0.418% |

La precisión es HIT / (HIT + FAIL); excluye las señales neutras y los casos sin resolución fiable. La media neta sí incluye las neutras resolubles. Los porcentajes netos usan coste total fijo de 40 puntos básicos y escenarios direccionales simétricos, no una cartera real.

ADA 4h: el filtro conserva 201 de 255 señales, con 93 aciertos, 93 fallos y 15 neutras. La precisión pasa de 49,78% a 50,00%; su intervalo Wilson del 95% es 42,89–57,11%. No reproduce la mejora de validación.

XRP 1h: el filtro conserva 203 de 558 señales, con 95 aciertos, 101 fallos y 7 neutras. La precisión baja de 50,74% a 48,47%; su intervalo Wilson del 95% es 41,57–55,43%. Su media neta también empeora. La suma acumulada de pérdidas se reduce porque descarta operaciones, pero eso no mejora los pronósticos.

Los otros 28 grupos no tuvieron ningún filtro que cumpliera los criterios en 2024. Los marcos diarios tienen muestras pequeñas y no se relajan los mínimos para obtener un ganador.

## Conclusión

Ningún candidato seleccionado demuestra una mejora persistente de precisión y utilidad neta. No hay fundamento para integrar estos filtros en CriptoAnálisis Multi. Tampoco se demuestra un 100% de aciertos ni un 100% de mejora. Todos los candidatos y sus descartes están incluidos en comparison.csv y results.json. Los intervalos por bloques mensuales son descriptivos y no corrigen la selección múltiple.

## Reproducir y continuar

Con el proyecto V1 y sus datos/reports originales disponibles, coloca los archivos del complemento manteniendo sus rutas y ejecuta `python -m research.filter_experiment`. El complemento no cambia la interfaz web V1.

Siguiente línea razonable: comprobar un aprendizaje que se actualice cronológicamente y compararlo con el modelo congelado, con parámetros prefijados y etiquetas ya maduras. Un resultado favorable sobre este historial seguirá siendo exploratorio; necesita después un registro de señales sobre datos nuevos. Esa prueba aún no está ejecutada.

Verificación realizada: 11 controles de integridad del laboratorio aprobados; auditoría del segundo experimento aprobada para 210 candidatos/30 grupos, costes, recuentos, subconjuntos y selección exclusiva con validación.
