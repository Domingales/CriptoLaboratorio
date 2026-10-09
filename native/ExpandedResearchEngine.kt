// Generated research adapter. Production SHA256: 4b5085d77e53673cddd540415a8977a10e976ba107d4a260c0a2330c41be8d49
package com.domingales.criptoanalisis.multi.domain

import kotlin.math.abs
import kotlin.math.max

object ExpandedResearchEngine {
    private const val MIN_CASES = 10

    private data class ResolvedPattern(
        val availableAt: Long,
        val indicators: IndicatorSet,
        val mtfScore: Int,
        val btcRegime: Regime?,
        val direction: Direction,
        val outcome: OutcomeStatus
    )

    /** Compatibilidad con llamadas antiguas; la sobrecarga con mapa es la MTF completa. */
    fun run(symbol: String, timeframe: String, candles: List<Candle>, threshold: Int): BacktestResult =
        run(symbol, timeframe, mapOf(timeframe to candles), threshold, 60)

    /**
     * Backtest walk-forward: en cada ventana sólo usa velas cerradas, contexto
     * BTC ya conocido y patrones cuyo horizonte adaptado ya había finalizado.
     * Las noticias sólo se aplican cuando se aporta una cronología histórica;
     * nunca se sustituye por titulares actuales, porque introduciría futuro.
     */
    fun run(
        symbol: String,
        timeframe: String,
        candlesByTimeframe: Map<String, List<Candle>>,
        threshold: Int,
        cooldownMinutes: Int = 60,
        btcCandles4h: List<Candle> = emptyList(),
        fundamentalTimeline: List<HistoricalFundamentalPoint> = emptyList(),
        allowBuy: Boolean = true,
        allowSell: Boolean = true,
        outcomeCandles5m: List<Candle>? = null,
        auditThroughLatest: Boolean = false,
        onEvaluation: ((AnalysisResult) -> Unit)? = null,
        onAccepted: ((AnalysisResult) -> Unit)? = null,
        // Research-only gate; production callers keep the unchanged null default.
        evaluationEligible: ((Long) -> Boolean)? = null
    ): BacktestResult {
        val primary = candlesByTimeframe[timeframe].orEmpty().sortedBy { it.openTime }
        if (primary.size < 240) return BacktestResult(symbol, timeframe, 0, 0, 0, 0, 0.0, contextNote = "Histórico insuficiente")
        val outcomeWindowMinutes = OutcomeTracker.outcomeWindowMinutes(timeframe)
        val horizonBars = max(1, (outcomeWindowMinutes * 60_000L / timeframeMillis(timeframe)).toInt())
        val fundamentals = fundamentalTimeline.sortedBy { it.timestamp }
        val patterns = mutableListOf<ResolvedPattern>()
        val cases = mutableListOf<BacktestCase>()
        val fiveMinute = outcomeCandles5m?.sortedBy { it.openTime }
        var missingFiveMinuteData = 0

        val indicatorCache = mutableMapOf<String, Pair<Long, IndicatorSet>>()
        var signals = 0; var hits = 0; var fails = 0; var neutral = 0
        var buySignals = 0; var buyHits = 0; var buyFails = 0; var buyNeutral = 0
        var sellSignals = 0; var sellHits = 0; var sellFails = 0; var sellNeutral = 0
        var evaluated = 0; var skippedMtf = 0; var walkForwardCasesUsed = 0
        var btcContextWindows = 0; var fundamentalContextWindows = 0
        var idx = 220
        val lastAccepted = mutableMapOf<String, Pair<Long, Int>>()

        while (idx < primary.size - if (auditThroughLatest) 0 else horizonBars) {
            val window = primary.subList(0, idx + 1)
            val indicators = TechnicalEngine.calculate(window.takeLast(300))
            val asOf = window.last().closeTime
            if (evaluationEligible?.invoke(asOf) == false) {
                idx++
                continue
            }
            val mtf = buildHistoricalMtf(timeframe, indicators, asOf, candlesByTimeframe, indicatorCache)
            if (mtf.byTimeframe.size < 2) {
                skippedMtf++
                idx += 3
                continue
            }
            evaluated++

            val btcRegime = historicalBtcRegime(symbol, asOf, btcCandles4h, indicatorCache)
            if (btcRegime != null) btcContextWindows++
            val fundamental = fundamentals.lastOrNull { it.timestamp <= asOf }?.context
                ?.also { fundamentalContextWindows++ }
                ?: neutralFundamental(asOf)

            val eligiblePatterns = patterns.filter { it.availableAt <= asOf }
            val analysis = evaluateWalkForward(
                symbol, timeframe, asOf, indicators, mtf, btcRegime, fundamental,
                threshold, allowBuy, allowSell, eligiblePatterns
            )
            onEvaluation?.invoke(analysis)
            walkForwardCasesUsed += analysis.calibration.comparableCases

            if (analysis.isSignal) {
                val isSell = isSell(analysis.direction)
                val side = if (isSell) "SELL" else "BUY"
                val previous = lastAccepted[side]
                val withinCooldown = previous != null && asOf - previous.first < cooldownMinutes * 60_000L
                if (withinCooldown && analysis.confidence <= previous!!.second + 5) {
                    idx++
                    continue
                }
                onAccepted?.invoke(analysis)
                // Acceptance is known now; future data gaps cannot alter cooldown.
                lastAccepted[side] = asOf to analysis.confidence
                val entry = indicators.price
                val next = primary.subList(idx + 1, minOf(idx + 1 + horizonBars, primary.size))
                    .filter { it.openTime > asOf }
                val target = max(0.45, indicators.atrPct * 0.55)
                val outcomeEnd = asOf + outcomeWindowMinutes * 60_000L
                if (auditThroughLatest && outcomeEnd > primary.last().closeTime) {
                    lastAccepted[side] = asOf to analysis.confidence
                    cases += BacktestCase(symbol, timeframe, asOf, analysis.direction, entry,
                        analysis.confidence, analysis.probability, target, OutcomeStatus.PENDING,
                        null, "WINDOW_NOT_EXPIRED")
                    idx++
                    continue
                }
                val resolved = if (fiveMinute == null) {
                    OutcomeTracker.firstTouchResolution(entry, analysis.direction, next, target)
                } else {
                    val exact = fiveMinute.subList(upperClose(fiveMinute, asOf), upperClose(fiveMinute, outcomeEnd))
                    if (!completeFiveMinuteWindow(asOf, outcomeEnd, exact)) {
                        missingFiveMinuteData++
                        cases += BacktestCase(symbol, timeframe, asOf, analysis.direction, entry,
                            analysis.confidence, analysis.probability, target,
                            OutcomeStatus.PENDING, null, "MISSING_5M_DATA")
                        idx++
                        continue
                    }
                    OutcomeTracker.firstTouchResolution(entry, analysis.direction, exact, target)
                }
                val outcome = resolved?.status ?: OutcomeStatus.NEUTRAL
                cases += BacktestCase(symbol, timeframe, asOf, analysis.direction, entry,
                    analysis.confidence, analysis.probability, target,
                    outcome, resolved?.marketTimestamp, resolved?.reason ?: "WINDOW_EXPIRED")
                lastAccepted[side] = asOf to analysis.confidence
                signals++
                if (isSell) sellSignals++ else buySignals++
                when (outcome) {
                    OutcomeStatus.HIT -> { hits++; if (isSell) sellHits++ else buyHits++ }
                    OutcomeStatus.FAIL -> { fails++; if (isSell) sellFails++ else buyFails++ }
                    else -> { neutral++; if (isSell) sellNeutral++ else buyNeutral++ }
                }
                // Aunque el resultado ya pueda calcularse al ejecutar hoy el
                // backtest, la muestra no se revela hasta concluir la ventana
                // adaptada al timeframe que también usa el seguimiento real.
                patterns += ResolvedPattern(next.lastOrNull()?.closeTime ?: (asOf + outcomeWindowMinutes * 60_000L), indicators, mtf.alignmentScore, btcRegime, analysis.direction, outcome)
            }
            idx++
        }
        val resolved = hits + fails
        val note = buildString {
            append("Walk-forward MTF, primer toque y ventana adaptada ${outcomeWindowMinutes}m sin futuro")
            if (symbol != "BTC" && btcContextWindows == 0) append("; contexto BTC no disponible")
            if (fundamentalContextWindows == 0) append("; noticias históricas no aportadas y excluidas de forma neutral")
        }
        return BacktestResult(
            symbol, timeframe, signals, hits, fails, neutral,
            if (resolved == 0) 0.0 else 100.0 * hits / resolved,
            evaluated, skippedMtf,
            DirectionBacktestResult(buySignals, buyHits, buyFails, buyNeutral),
            DirectionBacktestResult(sellSignals, sellHits, sellFails, sellNeutral),
            walkForwardCasesUsed, btcContextWindows, fundamentalContextWindows, note,
            cases, missingFiveMinuteData
        )
    }

    /** A missing minute must not turn an unobserved stop into an apparent hit. */
    internal fun completeFiveMinuteWindow(start: Long, end: Long, candles: List<Candle>): Boolean {
        val step = 5 * 60_000L
        if (candles.isEmpty() || end <= start) return false
        var expectedOpen = start + 1L
        for (c in candles) {
            if (c.openTime != expectedOpen || c.closeTime != c.openTime + step - 1L) return false
            expectedOpen += step
        }
        return candles.last().closeTime >= end
    }

    private fun evaluateWalkForward(
        symbol: String,
        timeframe: String,
        asOf: Long,
        indicators: IndicatorSet,
        mtf: MultiTimeframeContext,
        btcRegime: Regime?,
        fundamental: FundamentalContext,
        threshold: Int,
        allowBuy: Boolean,
        allowSell: Boolean,
        patterns: List<ResolvedPattern>
    ): AnalysisResult {
        val empty = HistoricalCalibration(0, 0, 0, 0, null, StatisticalConfidence.INSUFFICIENT)
        fun evaluate(calibration: HistoricalCalibration, side: Direction? = null) = SignalEngine.evaluate(
            SignalEngine.Input(symbol, timeframe, asOf, indicators, mtf, calibration, fundamental, btcRegime,
                threshold, true, allowBuy, allowSell, side)
        )
        val preliminary = evaluate(empty)
        if (preliminary.direction == Direction.WAIT) return preliminary
        var side = preliminary.direction
        repeat(3) {
            val calibration = historicalCalibration(indicators, side, mtf.alignmentScore, btcRegime, patterns)
            val result = evaluate(calibration, side)
            if (result.direction == Direction.WAIT || sameSide(side, result.direction)) return result
            side = result.direction
        }
        return preliminary
    }

    private fun historicalCalibration(
        current: IndicatorSet,
        direction: Direction,
        mtfScore: Int,
        btcRegime: Regime?,
        patterns: List<ResolvedPattern>
    ): HistoricalCalibration {
        val currentSupportDistance = distanceFromSupport(current)
        val currentResistanceDistance = distanceToResistance(current)
        val comparable = patterns.asSequence().filter { pattern ->
            val old = pattern.indicators
            sameSide(direction, pattern.direction) && old.regime == current.regime && old.structure == current.structure &&
                abs(old.rsi14 - current.rsi14) <= 10 && abs(old.adx14 - current.adx14) <= 12 &&
                old.atrPct in (current.atrPct * 0.55)..(current.atrPct * 1.8) &&
                old.volumeRatio in (current.volumeRatio - 0.6).coerceAtLeast(0.0)..(current.volumeRatio + 0.6) &&
                (old.ema20 - old.ema50) * (current.ema20 - current.ema50) >= 0 &&
                abs(pattern.mtfScore - mtfScore) <= 8 && pattern.mtfScore * mtfScore >= 0 &&
                abs(distanceFromSupport(old) - currentSupportDistance) <= 3 &&
                abs(distanceToResistance(old) - currentResistanceDistance) <= 3 &&
                (btcRegime == null || pattern.btcRegime == btcRegime)
        }.take(500).toList()
        val wins = comparable.count { it.outcome == OutcomeStatus.HIT }
        val losses = comparable.count { it.outcome == OutcomeStatus.FAIL }
        val neutral = comparable.count { it.outcome == OutcomeStatus.NEUTRAL }
        val resolved = wins + losses
        val probability = if (resolved >= MIN_CASES) (100.0 * wins / resolved).toInt() else null
        val confidence = when {
            resolved >= 100 -> StatisticalConfidence.HIGH
            resolved >= 30 -> StatisticalConfidence.MEDIUM
            resolved >= MIN_CASES -> StatisticalConfidence.LOW
            else -> StatisticalConfidence.INSUFFICIENT
        }
        return HistoricalCalibration(comparable.size, wins, losses, neutral, probability, confidence)
    }

    private fun buildHistoricalMtf(
        primaryTimeframe: String,
        primaryIndicators: IndicatorSet,
        asOf: Long,
        candlesByTimeframe: Map<String, List<Candle>>,
        cache: MutableMap<String, Pair<Long, IndicatorSet>>
    ): MultiTimeframeContext {
        val regimes = linkedMapOf<String, Regime>()
        val directions = linkedMapOf<String, Direction>()
        var score = 0
        fun add(tf: String, indicators: IndicatorSet) {
            val direction = directionOf(indicators)
            regimes[tf] = indicators.regime
            directions[tf] = direction
            val weight = when (tf) { "1d", "4h" -> 5; primaryTimeframe -> 4; else -> 2 }
            score += when (direction) {
                Direction.BUY, Direction.REVERSAL_BUY -> weight
                Direction.SELL, Direction.REVERSAL_SELL -> -weight
                else -> 0
            }
        }
        add(primaryTimeframe, primaryIndicators)
        for ((tf, allCandles) in candlesByTimeframe) {
            if (tf == primaryTimeframe) continue
            val historical = closedSlice(allCandles, asOf)
            if (historical.size >= 210) add(tf, cachedIndicators(tf, historical, cache))
        }
        val summary = regimes.keys.joinToString(" • ") { tf -> "$tf:${directions[tf]?.name ?: "N/D"}" }
        return MultiTimeframeContext(regimes, directions, score.coerceIn(-16, 16), summary)
    }

    private fun historicalBtcRegime(symbol: String, asOf: Long, candles: List<Candle>, cache: MutableMap<String, Pair<Long, IndicatorSet>>): Regime? {
        if (symbol == "BTC") return null
        val historical = closedSlice(candles, asOf)
        return if (historical.size < 210) null else cachedIndicators("BTC_CONTEXT", historical, cache).regime
    }

    private fun neutralFundamental(asOf: Long) = FundamentalContext(0, 0, 0, 0, "sin cronología histórica; componente excluido", asOf)
    private fun distanceFromSupport(i: IndicatorSet) = if (i.price > 0) (i.price - i.support) / i.price * 100.0 else 0.0
    private fun distanceToResistance(i: IndicatorSet) = if (i.price > 0) (i.resistance - i.price) / i.price * 100.0 else 0.0
    private fun isSell(direction: Direction) = direction == Direction.SELL || direction == Direction.REVERSAL_SELL
    private fun sameSide(first: Direction, second: Direction) = isSell(first) == isSell(second) && first != Direction.WAIT && second != Direction.WAIT
    private fun directionOf(i: IndicatorSet): Direction = when {
        i.price > i.ema20 && i.plusDi >= i.minusDi -> Direction.BUY
        i.price < i.ema20 && i.minusDi > i.plusDi -> Direction.SELL
        else -> Direction.WAIT
    }
    private fun timeframeMillis(timeframe: String): Long = when (timeframe) {
        "15m" -> 15 * 60_000L
        "30m" -> 30 * 60_000L
        "1h" -> 60 * 60_000L
        "4h" -> 4 * 60 * 60_000L
        "1d" -> 24 * 60 * 60_000L
        else -> 60 * 60_000L
    }

    private fun upperClose(c: List<Candle>, t: Long): Int {
        var lo = 0; var hi = c.size
        while (lo < hi) { val m = (lo+hi)/2; if (c[m].closeTime <= t) lo=m+1 else hi=m }
        return lo
    }
    private fun closedSlice(c: List<Candle>, t: Long): List<Candle> {
        val end = upperClose(c,t)
        return c.subList(max(0,end-300),end)
    }
    private fun cachedIndicators(key: String, c: List<Candle>, cache: MutableMap<String, Pair<Long, IndicatorSet>>): IndicatorSet {
        val time = c.last().closeTime
        val old = cache[key]
        if (old != null && old.first == time) return old.second
        val value = TechnicalEngine.calculate(c)
        cache[key] = time to value
        return value
    }
}
