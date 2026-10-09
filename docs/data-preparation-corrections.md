# Correcciones de preparación del experimento

Se observaron resultados iniciales antes de estas correcciones. No se cambiaron parámetros, umbrales ni particiones por rendimiento. El examen final es una reconstrucción histórica repetida, no evidencia prospectiva independiente.

1. El archivo 5m de marzo de 2023 contiene una vela con cierre no estándar y un hueco de mercado. Se preserva el ZIP original y su CHECKSUM. Se excluye esa vela, en lugar de perder todo el mes. Las ventanas incompletas y los calentamientos después del hueco siguen excluidos.
2. Un histórico que comienza en enero de 2023 no inicializa EMA200/contextos de 300 velas diarias para el comienzo del aprendizaje. Se añade 2022 sólo como calentamiento de indicadores. Las etiquetas de aprendizaje de los modelos nuevos comienzan en enero de 2023; las de 2022 no se usan para entrenarlos. El motor Kotlin sí reconstruye cronológicamente su propia memoria histórica conforme a su código.
3. El calendario de selección de episodios utiliza timestamps y no posiciones de filas, de manera que un hueco futuro no prolongue retrospectivamente el cooldown.

La referencia matemática a 2022 no cambia el requisito de examinar las predicciones desde 2023. No se evalúan ni presentan como examen los pronósticos de 2022.
