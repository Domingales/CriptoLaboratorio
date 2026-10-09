package com.domingales.criptoanalisis.multi.domain

import kotlin.math.max

/** Cálculo temporal compartido por seguimiento real y backtest. */
object OutcomeTracker {
    data class Excursions(val mfe: Double, val mae: Double)
    data class TouchResolution(
        val status: OutcomeStatus,
        val marketTimestamp: Long,
        val reason: String
    )
    data class Observation(
        val marketTimestamp: Long,
        val price: Double,
        val movePct: Double,
        val status: OutcomeStatus
    )

    /** Excluye toda vela que hubiera empezado antes o durante la señal. */
    fun candlesStrictlyAfter(signalCloseTime: Long, endTime: Long, candles: List<Candle>): List<Candle> =
        candles.filter { it.openTime > signalCloseTime && it.closeTime <= endTime }

    fun excursions(entry: Double, direction: String, candles: List<Candle>): Excursions {
        if (entry <= 0.0 || candles.isEmpty()) return Excursions(0.0, 0.0)
        val sell = direction.contains("SELL")
        var mfe = 0.0
        var mae = 0.0
        candles.forEach { candle ->
            val favorable = if (sell) percent(entry - candle.low, entry) else percent(candle.high - entry, entry)
            val adverse = if (sell) percent(entry - candle.high, entry) else percent(candle.low - entry, entry)
            mfe = max(mfe, favorable)
            mae = minOf(mae, adverse)
        }
        return Excursions(mfe, mae)
    }

    fun observationAt(
        entry: Double,
        direction: String,
        dueTimestamp: Long,
        candles: List<Candle>,
        thresholdPct: Double,
        maxLagMillis: Long = 10 * 60_000L
    ): Observation? {
        if (entry <= 0.0) return null
        val candle = candles.asSequence().filter { it.closeTime <= dueTimestamp }.maxByOrNull { it.closeTime } ?: return null
        if (dueTimestamp - candle.closeTime !in 0..maxLagMillis) return null
        val rawMove = percent(candle.close - entry, entry)
        val move = if (direction.contains("SELL")) -rawMove else rawMove
        val status = when {
            move >= thresholdPct -> OutcomeStatus.HIT
            move <= -thresholdPct -> OutcomeStatus.FAIL
            else -> OutcomeStatus.NEUTRAL
        }
        return Observation(candle.closeTime, candle.close, move, status)
    }

    /**
     * Resuelve por el primer toque cronológico. Si objetivo y stop aparecen en
     * la misma vela, el orden intravela es desconocido y se clasifica NEUTRAL.
     */
    fun firstTouch(entry: Double, direction: Direction, candles: List<Candle>, thresholdPct: Double): OutcomeStatus {
        return firstTouchResolution(entry, direction, candles, thresholdPct)?.status ?: OutcomeStatus.NEUTRAL
    }

    /**
     * Devuelve el primer desenlace cronológico verificable. Un valor null no
     * significa NEUTRAL: significa que objetivo y stop todavía no se tocaron.
     */
    fun firstTouchResolution(entry: Double, direction: Direction, candles: List<Candle>, thresholdPct: Double): TouchResolution? {
        if (entry <= 0.0 || candles.isEmpty() || thresholdPct <= 0.0) return null
        val sell = direction == Direction.SELL || direction == Direction.REVERSAL_SELL
        candles.forEach { candle ->
            val favorable = if (sell) percent(entry - candle.low, entry) else percent(candle.high - entry, entry)
            val adverse = if (sell) percent(entry - candle.high, entry) else percent(candle.low - entry, entry)
            val hit = favorable >= thresholdPct
            val fail = adverse <= -thresholdPct
            if (hit && fail) return TouchResolution(OutcomeStatus.NEUTRAL, candle.closeTime, "BOTH_TOUCHED_SAME_5M_CANDLE")
            if (hit) return TouchResolution(OutcomeStatus.HIT, candle.closeTime, "TARGET_FIRST")
            if (fail) return TouchResolution(OutcomeStatus.FAIL, candle.closeTime, "STOP_FIRST")
        }
        return null
    }

    /** Ventanas de persistencia adaptadas al intervalo que originó la señal. */
    fun persistenceHorizonsMinutes(timeframe: String): List<Int> = when (timeframe) {
        "15m" -> listOf(15, 60, 240, 1440)
        "30m" -> listOf(30, 120, 480, 1440)
        "1h" -> listOf(60, 240, 720, 1440)
        "4h" -> listOf(240, 720, 1440, 4320)
        "1d" -> listOf(1440, 4320, 10080, 20160)
        else -> listOf(60, 240, 720, 1440)
    }

    fun outcomeWindowMinutes(timeframe: String): Int = persistenceHorizonsMinutes(timeframe).last()

    fun movementThresholdPct(entry: Double, atr: Double): Double {
        val atrPct = if (entry > 0.0) atr / entry * 100.0 else 0.0
        return max(0.45, atrPct * 0.55)
    }

    fun targetPrice(entry: Double, direction: String, thresholdPct: Double): Double =
        if (direction.contains("SELL")) entry * (1.0 - thresholdPct / 100.0) else entry * (1.0 + thresholdPct / 100.0)

    fun stopPrice(entry: Double, direction: String, thresholdPct: Double): Double =
        if (direction.contains("SELL")) entry * (1.0 + thresholdPct / 100.0) else entry * (1.0 - thresholdPct / 100.0)

    private fun percent(delta: Double, entry: Double): Double = delta / entry * 100.0
}
