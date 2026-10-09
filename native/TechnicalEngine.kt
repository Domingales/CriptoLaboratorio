package com.domingales.criptoanalisis.multi.domain

import kotlin.math.abs
import kotlin.math.max
import kotlin.math.min

object TechnicalEngine {
    data class IncrementalState(
        val candleClose: Long,
        val ema20: Double,
        val ema50: Double,
        val ema200: Double,
        val ema20History: List<Double>,
        val ema50History: List<Double>,
        val rsiAverageGain: Double,
        val rsiAverageLoss: Double,
        val rsiHistory: List<Double>
    )

    data class Computation(val indicators: IndicatorSet, val state: IncrementalState)

    private fun emaSeries(values: List<Double>, period: Int): List<Double> {
        if (values.size < period) return List(values.size) { values.getOrElse(it) { 0.0 } }
        val out = MutableList(values.size) { 0.0 }
        var e = values.take(period).average()
        for (i in 0 until period) out[i] = e
        val k = 2.0 / (period + 1.0)
        for (i in period until values.size) {
            e = values[i] * k + e * (1.0 - k)
            out[i] = e
        }
        return out
    }

    private data class RsiComputation(val series: List<Double>, val averageGain: Double, val averageLoss: Double)

    private fun rsiSeries(values: List<Double>, period: Int = 14): RsiComputation {
        val out = MutableList(values.size) { 50.0 }
        if (values.size <= period) return RsiComputation(out, 0.0, 0.0)
        var gain = 0.0
        var loss = 0.0
        for (i in 1..period) {
            val d = values[i] - values[i - 1]
            if (d >= 0) gain += d else loss -= d
        }
        var avgGain = gain / period
        var avgLoss = loss / period
        out[period] = if (avgLoss == 0.0) 100.0 else 100.0 - 100.0 / (1.0 + avgGain / avgLoss)
        for (i in period + 1 until values.size) {
            val d = values[i] - values[i - 1]
            val g = if (d > 0) d else 0.0
            val l = if (d < 0) -d else 0.0
            avgGain = (avgGain * (period - 1) + g) / period
            avgLoss = (avgLoss * (period - 1) + l) / period
            out[i] = if (avgLoss == 0.0) 100.0 else 100.0 - 100.0 / (1.0 + avgGain / avgLoss)
        }
        return RsiComputation(out, avgGain, avgLoss)
    }

    private fun atr(c: List<Candle>, period: Int = 14): Double {
        if (c.size < 2) return 0.0
        val tr = mutableListOf<Double>()
        for (i in max(1, c.size - period) until c.size) {
            tr += max(c[i].high - c[i].low, max(abs(c[i].high - c[i - 1].close), abs(c[i].low - c[i - 1].close)))
        }
        return if (tr.isEmpty()) 0.0 else tr.average()
    }

    private data class Dmi(val adx: Double, val plus: Double, val minus: Double)

    private fun dmi(c: List<Candle>, period: Int = 14): Dmi {
        if (c.size < period * 2 + 2) return Dmi(0.0, 0.0, 0.0)
        val dxs = mutableListOf<Double>()
        var lastPlus = 0.0
        var lastMinus = 0.0
        for (end in c.size - period until c.size) {
            if (end < period) continue
            var trSum = 0.0
            var plusSum = 0.0
            var minusSum = 0.0
            for (i in end - period + 1..end) {
                val up = c[i].high - c[i - 1].high
                val down = c[i - 1].low - c[i].low
                plusSum += if (up > down && up > 0) up else 0.0
                minusSum += if (down > up && down > 0) down else 0.0
                trSum += max(c[i].high - c[i].low, max(abs(c[i].high - c[i - 1].close), abs(c[i].low - c[i - 1].close)))
            }
            if (trSum > 0) {
                lastPlus = 100.0 * plusSum / trSum
                lastMinus = 100.0 * minusSum / trSum
                val den = lastPlus + lastMinus
                dxs += if (den == 0.0) 0.0 else 100.0 * abs(lastPlus - lastMinus) / den
            }
        }
        return Dmi(if (dxs.isEmpty()) 0.0 else dxs.average(), lastPlus, lastMinus)
    }

    private fun slopePct(series: List<Double>, lookback: Int): Double {
        if (series.size <= lookback) return 0.0
        val now = series.last()
        val old = series[series.lastIndex - lookback]
        return if (old == 0.0) 0.0 else (now - old) / abs(old) * 100.0
    }

    private fun structure(candles: List<Candle>): MarketStructure {
        val w = candles.takeLast(12)
        if (w.size < 8) return MarketStructure.MIXED
        val highs = listOf(w.take(4).maxOf { it.high }, w.drop(4).take(4).maxOf { it.high }, w.takeLast(4).maxOf { it.high })
        val lows = listOf(w.take(4).minOf { it.low }, w.drop(4).take(4).minOf { it.low }, w.takeLast(4).minOf { it.low })
        val hh = highs[2] > highs[1] && highs[1] >= highs[0]
        val hl = lows[2] > lows[1] && lows[1] >= lows[0]
        val lh = highs[2] < highs[1] && highs[1] <= highs[0]
        val ll = lows[2] < lows[1] && lows[1] <= lows[0]
        return when {
            hh && hl -> MarketStructure.BULLISH
            lh && ll -> MarketStructure.BEARISH
            abs(highs[2] - highs[0]) / max(highs[0], 1e-9) < 0.01 && abs(lows[2] - lows[0]) / max(lows[0], 1e-9) < 0.01 -> MarketStructure.SIDEWAYS
            else -> MarketStructure.MIXED
        }
    }

    private fun zone(values: List<Double>, reference: Double): SupportResistanceZone {
        if (values.isEmpty()) return SupportResistanceZone(reference, reference, 0, 0)
        val sorted = values.sorted()
        val center = sorted[sorted.size / 2]
        val tolerance = max(reference * 0.0035, 1e-9)
        val near = values.filter { abs(it - center) <= tolerance }
        val low = (near.minOrNull() ?: center) - tolerance * 0.25
        val high = (near.maxOrNull() ?: center) + tolerance * 0.25
        val touches = near.size
        return SupportResistanceZone(low, high, touches, (touches * 20).coerceAtMost(100))
    }

    private fun divergence(closes: List<Double>, rsi: List<Double>): Pair<Boolean, Boolean> {
        if (closes.size < 20 || rsi.size != closes.size) return false to false
        val aStart = closes.size - 20
        val mid = closes.size - 10
        val firstLowIdx = (aStart until mid).minByOrNull { closes[it] } ?: return false to false
        val secondLowIdx = (mid until closes.size).minByOrNull { closes[it] } ?: return false to false
        val firstHighIdx = (aStart until mid).maxByOrNull { closes[it] } ?: return false to false
        val secondHighIdx = (mid until closes.size).maxByOrNull { closes[it] } ?: return false to false
        val bull = closes[secondLowIdx] < closes[firstLowIdx] && rsi[secondLowIdx] > rsi[firstLowIdx] + 2.0
        val bear = closes[secondHighIdx] > closes[firstHighIdx] && rsi[secondHighIdx] < rsi[firstHighIdx] - 2.0
        return bull to bear
    }

    fun calculate(candles: List<Candle>): IndicatorSet = calculateWithState(candles).indicators

    fun calculateWithState(candles: List<Candle>): Computation {
        require(candles.size >= 210) { "Se requieren al menos 210 velas" }
        val closes = candles.map { it.close }
        val e20s = emaSeries(closes, 20)
        val e50s = emaSeries(closes, 50)
        val e200s = emaSeries(closes, 200)
        val rsiComputation = rsiSeries(closes)
        val rsis = rsiComputation.series
        val indicators = assemble(
            candles = candles,
            ema20 = e20s.last(),
            ema50 = e50s.last(),
            ema200 = e200s.last(),
            ema20Slope = slopePct(e20s, 5),
            ema50Slope = slopePct(e50s, 5),
            rsi = rsis.last(),
            rsiSlope = if (rsis.size > 4) rsis.last() - rsis[rsis.lastIndex - 3] else 0.0,
            divergence = divergence(closes, rsis)
        )
        return Computation(
            indicators,
            IncrementalState(
                candleClose = candles.last().closeTime,
                ema20 = e20s.last(), ema50 = e50s.last(), ema200 = e200s.last(),
                ema20History = e20s.takeLast(6), ema50History = e50s.takeLast(6),
                rsiAverageGain = rsiComputation.averageGain, rsiAverageLoss = rsiComputation.averageLoss,
                rsiHistory = rsis.takeLast(20)
            )
        )
    }

    /** Actualiza EMA/RSI en O(1); el resto usa únicamente ventanas locales acotadas. */
    fun calculateIncremental(candles: List<Candle>, previous: IncrementalState): Computation? {
        if (candles.size < 210 || candles[candles.lastIndex - 1].closeTime != previous.candleClose) return null
        val last = candles.last()
        val previousClose = candles[candles.lastIndex - 1].close
        fun nextEma(old: Double, period: Int) = last.close * (2.0 / (period + 1.0)) + old * (1.0 - 2.0 / (period + 1.0))
        val ema20 = nextEma(previous.ema20, 20)
        val ema50 = nextEma(previous.ema50, 50)
        val ema200 = nextEma(previous.ema200, 200)
        val ema20History = (previous.ema20History + ema20).takeLast(6)
        val ema50History = (previous.ema50History + ema50).takeLast(6)
        fun historySlope(history: List<Double>): Double {
            if (history.size < 6 || history.first() == 0.0) return 0.0
            return (history.last() - history.first()) / abs(history.first()) * 100.0
        }
        val delta = last.close - previousClose
        val gain = if (delta > 0.0) delta else 0.0
        val loss = if (delta < 0.0) -delta else 0.0
        val averageGain = (previous.rsiAverageGain * 13.0 + gain) / 14.0
        val averageLoss = (previous.rsiAverageLoss * 13.0 + loss) / 14.0
        val rsi = if (averageLoss == 0.0) 100.0 else 100.0 - 100.0 / (1.0 + averageGain / averageLoss)
        val rsiHistory = (previous.rsiHistory + rsi).takeLast(20)
        val rsiSlope = if (rsiHistory.size > 3) rsi - rsiHistory[rsiHistory.lastIndex - 3] else 0.0
        val closes = candles.takeLast(rsiHistory.size).map { it.close }
        val indicators = assemble(candles, ema20, ema50, ema200, historySlope(ema20History), historySlope(ema50History), rsi, rsiSlope, divergence(closes, rsiHistory))
        return Computation(
            indicators,
            IncrementalState(last.closeTime, ema20, ema50, ema200, ema20History, ema50History, averageGain, averageLoss, rsiHistory)
        )
    }

    private fun assemble(
        candles: List<Candle>,
        ema20: Double,
        ema50: Double,
        ema200: Double,
        ema20Slope: Double,
        ema50Slope: Double,
        rsi: Double,
        rsiSlope: Double,
        divergence: Pair<Boolean, Boolean>
    ): IndicatorSet {
        val closes = candles.map { it.close }
        val price = closes.last()
        val a = atr(candles)
        val d = dmi(candles)
        val recent20 = candles.dropLast(1).takeLast(20)
        val previousResistance = recent20.maxOf { it.high }
        val previousSupport = recent20.minOf { it.low }
        val supportCandidates = candles.takeLast(80).map { it.low }.sorted().take(18)
        val resistanceCandidates = candles.takeLast(80).map { it.high }.sortedDescending().take(18)
        val supportZone = zone(supportCandidates, price)
        val resistanceZone = zone(resistanceCandidates, price)
        val avgVol20 = candles.dropLast(1).takeLast(20).map { it.volume }.average().takeIf { it > 0 } ?: 1.0
        val avgVol5 = candles.dropLast(1).takeLast(5).map { it.volume }.average().takeIf { it > 0 } ?: avgVol20
        val volRatio = candles.last().volume / avgVol20
        val volExpansion = avgVol5 > avgVol20 * 1.15 || volRatio >= 1.25
        val atrPct = if (price == 0.0) 0.0 else a / price * 100.0
        val breakoutUp = price > previousResistance && volRatio >= 1.15
        val breakoutDown = price < previousSupport && volRatio >= 1.15
        val last = candles.last()
        val falseBreakout = (last.high > previousResistance && last.close < previousResistance) || (last.low < previousSupport && last.close > previousSupport)
        val s = structure(candles)
        val regime = classifyRegime(price, ema20, ema50, ema200, d.adx, atrPct, breakoutUp, breakoutDown, divergence.first, divergence.second, falseBreakout)
        return IndicatorSet(
            price = price,
            ema20 = ema20,
            ema50 = ema50,
            ema200 = ema200,
            ema20SlopePct = ema20Slope,
            ema50SlopePct = ema50Slope,
            rsi14 = rsi,
            rsiSlope = rsiSlope,
            rsiBullishDivergence = divergence.first,
            rsiBearishDivergence = divergence.second,
            atr14 = a,
            atrPct = atrPct,
            adx14 = d.adx,
            plusDi = d.plus,
            minusDi = d.minus,
            volumeRatio = volRatio,
            volumeExpansion = volExpansion,
            support = previousSupport,
            resistance = previousResistance,
            supportZone = supportZone,
            resistanceZone = resistanceZone,
            structure = s,
            regime = regime,
            breakoutUp = breakoutUp,
            breakoutDown = breakoutDown,
            falseBreakout = falseBreakout,
            expectedMoveAtr = if (price == 0.0) 0.0 else a / price * 100.0
        )
    }

    internal fun classifyRegime(
        price: Double,
        ema20: Double,
        ema50: Double,
        ema200: Double,
        adx: Double,
        atrPct: Double,
        breakoutUp: Boolean,
        breakoutDown: Boolean,
        bullishDivergence: Boolean,
        bearishDivergence: Boolean,
        falseBreakout: Boolean
    ): Regime = when {
        breakoutUp || breakoutDown -> Regime.BREAKOUT
        atrPct > 4.0 -> Regime.HIGH_VOLATILITY
        price > ema20 && ema20 > ema50 && ema50 > ema200 && adx >= 20 -> Regime.TREND_UP
        price < ema20 && ema20 < ema50 && ema50 < ema200 && adx >= 20 -> Regime.TREND_DOWN
        adx < 16 -> Regime.RANGE
        atrPct < 0.7 -> Regime.LOW_VOLATILITY
        bullishDivergence || bearishDivergence || falseBreakout -> Regime.POSSIBLE_REVERSAL
        else -> Regime.MIXED
    }
}
