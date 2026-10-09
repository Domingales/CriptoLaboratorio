package com.domingales.criptoanalisis.multi.domain

import kotlin.math.abs
import kotlin.math.max

object SignalEngine {
    data class Input(
        val symbol: String,
        val timeframe: String,
        val candleCloseTime: Long,
        val indicators: IndicatorSet,
        val mtf: MultiTimeframeContext,
        val calibration: HistoricalCalibration,
        val fundamental: FundamentalContext,
        val btcRegime: Regime?,
        val threshold: Int,
        val closedCandleMode: Boolean,
        val allowBuy: Boolean = true,
        val allowSell: Boolean = true,
        val calibrationDirection: Direction? = null
    )

    fun evaluate(input: Input): AnalysisResult {
        val i = input.indicators
        val why = mutableListOf<String>()

        val trendBull = scoreTrendBull(i)
        val trendBear = scoreTrendBear(i)
        val momentumBull = scoreMomentumBull(i)
        val momentumBear = scoreMomentumBear(i)
        val volumeBull = if (i.volumeExpansion) 10 else if (i.volumeRatio >= 0.9) 4 else -4
        val volumeBear = volumeBull
        val structureBull = when (i.structure) {
            MarketStructure.BULLISH -> 12
            MarketStructure.BEARISH -> -10
            MarketStructure.SIDEWAYS -> -5
            MarketStructure.MIXED -> 0
        }
        val structureBear = when (i.structure) {
            MarketStructure.BEARISH -> 12
            MarketStructure.BULLISH -> -10
            MarketStructure.SIDEWAYS -> -5
            MarketStructure.MIXED -> 0
        }
        val srBull = supportResistanceBull(i)
        val srBear = supportResistanceBear(i)
        val mtfBull = input.mtf.alignmentScore.coerceIn(-16, 16)
        val mtfBear = (-input.mtf.alignmentScore).coerceIn(-16, 16)
        val volRisk = when {
            i.atrPct > 6.0 -> -8
            i.atrPct > 4.0 -> -4
            i.atrPct < 0.25 -> -5
            else -> 3
        }
        val hist = historicalComponent(input.calibration)
        // Los comparables BUY sólo ponderan el escenario alcista y los SELL el
        // bajista. Aplicar la misma muestra a ambos lados falsearía el contraste.
        val histBull = if (input.calibrationDirection == Direction.BUY || input.calibrationDirection == Direction.REVERSAL_BUY) hist else 0
        val histBear = if (input.calibrationDirection == Direction.SELL || input.calibrationDirection == Direction.REVERSAL_SELL) hist else 0
        val btcBull = btcContext(input.symbol, input.btcRegime, true)
        val btcBear = btcContext(input.symbol, input.btcRegime, false)
        val fundamentalBull = input.fundamental.score.coerceIn(-10, 10)
        val fundamentalBear = (-input.fundamental.score).coerceIn(-10, 10)

        val bullBreakdown = ScoreBreakdown(trendBull, momentumBull, volumeBull, structureBull, srBull, mtfBull, volRisk, histBull, btcBull, fundamentalBull)
        val bearBreakdown = ScoreBreakdown(trendBear, momentumBear, volumeBear, structureBear, srBear, mtfBear, volRisk, histBear, btcBear, fundamentalBear)
        val bullRaw = normalize(bullBreakdown.total)
        val bearRaw = normalize(bearBreakdown.total)

        var direction = when {
            abs(bullRaw - bearRaw) < 8 -> Direction.WAIT
            bullRaw > bearRaw -> Direction.BUY
            else -> Direction.SELL
        }
        if (i.regime == Regime.POSSIBLE_REVERSAL) {
            if (i.rsiBullishDivergence && bullRaw >= bearRaw) direction = Direction.REVERSAL_BUY
            if (i.rsiBearishDivergence && bearRaw > bullRaw) direction = Direction.REVERSAL_SELL
        }

        val selected = if (direction == Direction.SELL || direction == Direction.REVERSAL_SELL) bearBreakdown else bullBreakdown
        val score = max(bullRaw, bearRaw)
        val directionalAdvantage = abs(bullRaw - bearRaw)
        val preliminaryConfidence = score - (if (direction == Direction.WAIT) 18 else 0) + minOf(7, directionalAdvantage / 4)
        val missingData = mutableListOf<String>()
        if (!i.price.isFinite() || i.price <= 0.0) missingData += "precio válido"
        if (!i.atr14.isFinite() || i.atr14 <= 0.0 || !i.atrPct.isFinite() || i.atrPct <= 0.0) missingData += "ATR"
        if (!i.volumeRatio.isFinite() || i.volumeRatio <= 0.0) missingData += "volumen"
        if (i.ema20 <= 0.0 || i.ema50 <= 0.0 || i.ema200 <= 0.0) missingData += "medias móviles"
        val mtfComplete = input.mtf.byTimeframe.containsKey(input.timeframe) && input.mtf.byTimeframe.size >= 2
        if (!mtfComplete) missingData += "confirmación multitemporal"
        val dataComplete = missingData.isEmpty()

        addExplanation(why, input, direction)

        val isDirectionalBuy = direction == Direction.BUY || direction == Direction.REVERSAL_BUY
        val isDirectionalSell = direction == Direction.SELL || direction == Direction.REVERSAL_SELL
        val isReversal = direction == Direction.REVERSAL_BUY || direction == Direction.REVERSAL_SELL
        val exhaustionRisk = (isDirectionalBuy && i.rsi14 >= 74.0 && !i.breakoutUp) ||
            (isDirectionalSell && i.rsi14 <= 26.0 && !i.breakoutDown)
        val opposingLevelTooClose = opposingLevelTooClose(i, isDirectionalBuy, isDirectionalSell)
        val trendRollover = (isDirectionalBuy && i.ema20SlopePct <= 0.0 && i.plusDi < i.minusDi) ||
            (isDirectionalSell && i.ema20SlopePct >= 0.0 && i.minusDi < i.plusDi)
        val higherTimeframeContradiction = !isReversal && contradictsHigherTimeframe(input.timeframe, input.mtf, isDirectionalBuy, isDirectionalSell)
        val timingPenalty = (if (exhaustionRisk) 8 else 0) + (if (opposingLevelTooClose) 8 else 0) +
            (if (trendRollover) 10 else 0) + (if (higherTimeframeContradiction) 10 else 0)
        val confidence = (preliminaryConfidence - timingPenalty).coerceIn(0, 100)
        val probability = calibratedProbability(input.calibration, confidence)
        val trendValid = i.adx14 >= 18 || i.regime == Regime.BREAKOUT || direction == Direction.REVERSAL_BUY || direction == Direction.REVERSAL_SELL
        val volumeValid = i.volumeRatio >= 0.72 || i.volumeExpansion || i.regime == Regime.POSSIBLE_REVERSAL
        val mtfValid = when {
            isDirectionalBuy -> input.mtf.alignmentScore >= -5
            isDirectionalSell -> input.mtf.alignmentScore <= 5
            else -> false
        }
        val directionAllowed = (!isDirectionalBuy || input.allowBuy) && (!isDirectionalSell || input.allowSell)
        val freshEnough = input.candleCloseTime > 0L
        val preCandidate = direction != Direction.WAIT && confidence >= (input.threshold - 8).coerceAtLeast(50)
        val timingValid = !exhaustionRisk && !opposingLevelTooClose && !trendRollover && !higherTimeframeContradiction
        val passesFinalFilters = dataComplete && direction != Direction.WAIT && confidence >= input.threshold && trendValid && volumeValid && mtfValid && timingValid && directionAllowed && freshEnough
        // Una vela todavía abierta nunca puede producir una señal definitiva.
        // En modo intravela, incluso si supera todos los filtros, se conserva como
        // PRESEÑAL hasta repetir la evaluación con la vela cerrada.
        val signal = input.closedCandleMode && passesFinalFilters
        val pre = dataComplete && direction != Direction.WAIT && timingValid && (preCandidate || passesFinalFilters) && !signal
        val rejection = when {
            signal -> ""
            !dataComplete -> "Datos esenciales incompletos: ${missingData.joinToString(", ")}"
            direction == Direction.WAIT -> "Sin ventaja direccional suficiente"
            !input.closedCandleMode && passesFinalFilters -> "Preseñal intravela: pendiente de confirmación al cierre"
            exhaustionRisk -> "Entrada tardía: momentum próximo al agotamiento sin ruptura confirmada"
            opposingLevelTooClose -> if (isDirectionalBuy) "Compra demasiado cerca de resistencia sin ruptura" else "Venta demasiado cerca de soporte sin ruptura"
            trendRollover -> "El impulso inmediato ya gira contra la dirección propuesta"
            higherTimeframeContradiction -> "Intervalo superior contradice la dirección propuesta"
            confidence < input.threshold -> "Confianza $confidence% por debajo del umbral ${input.threshold}%"
            !trendValid -> "ADX/tendencia insuficiente"
            !volumeValid -> "Volumen insuficiente"
            !mtfValid -> "Confluencia multitemporal no válida"
            !directionAllowed -> "Dirección desactivada para este activo"
            !freshEnough -> "Datos temporales no válidos"
            else -> "Filtros de calidad no superados"
        }
        val state = when {
            signal -> EvaluationState.SIGNAL
            pre -> EvaluationState.PRESIGNAL
            else -> EvaluationState.EVALUATION
        }
        val risk = when {
            i.atrPct >= 5.0 || i.falseBreakout -> "ALTO"
            i.atrPct >= 2.0 || input.mtf.alignmentScore.absoluteValue < 6 -> "MEDIO"
            else -> "BAJO"
        }
        val expected = if (dataComplete) i.expectedMoveAtr else 0.0
        val low = if (dataComplete) expected * 0.75 else 0.0
        val high = if (dataComplete) expected * 1.8 else 0.0
        val invalidation = if (!dataComplete || direction == Direction.WAIT) 0.0
        else boundedInvalidation(i, isDirectionalBuy)
        return AnalysisResult(
            symbol = input.symbol,
            timeframe = input.timeframe,
            timestamp = System.currentTimeMillis(),
            candleCloseTime = input.candleCloseTime,
            indicators = i,
            mtf = input.mtf,
            btcRegime = input.btcRegime,
            calibration = input.calibration,
            fundamental = input.fundamental,
            breakdown = selected,
            direction = direction,
            score = score,
            confidence = confidence,
            probability = probability,
            risk = risk,
            forecastLowPct = low,
            forecastHighPct = high,
            invalidationPrice = invalidation,
            state = state,
            isPreSignal = pre,
            isSignal = signal,
            rejectionReason = rejection,
            explanation = why,
            dataComplete = dataComplete,
            missingData = missingData,
            decisionThreshold = input.threshold,
            closedCandleEvaluation = input.closedCandleMode,
            allowBuy = input.allowBuy,
            allowSell = input.allowSell
        )
    }

    private val Int.absoluteValue get() = kotlin.math.abs(this)

    /**
     * Uses the structural zone when it is useful, but prevents an old/distant
     * zone from producing a stop that is incoherent with current volatility.
     */
    private fun boundedInvalidation(i: IndicatorSet, buy: Boolean): Double {
        val minimumDistance = i.atr14 * 1.15
        val maximumDistance = i.atr14 * 3.0
        val structuralDistance = if (buy) i.price - i.supportZone.low else i.resistanceZone.high - i.price
        val distance = structuralDistance
            .takeIf { it.isFinite() && it > 0.0 }
            ?.coerceIn(minimumDistance, maximumDistance)
            ?: minimumDistance
        return if (buy) (i.price - distance).coerceAtLeast(0.0) else i.price + distance
    }

    private fun normalize(total: Int): Int = (50 + total / 2).coerceIn(0, 100)

    private fun scoreTrendBull(i: IndicatorSet): Int {
        var s = 0
        if (i.price > i.ema20) s += 7 else s -= 7
        if (i.ema20 > i.ema50) s += 8 else s -= 8
        if (i.ema50 > i.ema200) s += 10 else s -= 10
        if (i.ema20SlopePct > 0) s += 4
        if (i.ema50SlopePct > 0) s += 3
        if (i.plusDi > i.minusDi) s += 5
        if (i.adx14 >= 25) s += 5
        return s.coerceIn(-20, 20)
    }

    private fun scoreTrendBear(i: IndicatorSet): Int {
        var s = 0
        if (i.price < i.ema20) s += 7 else s -= 7
        if (i.ema20 < i.ema50) s += 8 else s -= 8
        if (i.ema50 < i.ema200) s += 10 else s -= 10
        if (i.ema20SlopePct < 0) s += 4
        if (i.ema50SlopePct < 0) s += 3
        if (i.minusDi > i.plusDi) s += 5
        if (i.adx14 >= 25) s += 5
        return s.coerceIn(-20, 20)
    }

    private fun scoreMomentumBull(i: IndicatorSet): Int {
        var s = 0
        if (i.rsi14 in 52.0..72.0) s += 10
        if (i.rsiSlope > 0.5) s += 4
        if (i.rsiBullishDivergence) s += 8
        if (i.rsi14 > 78) s -= 6
        return s.coerceIn(-15, 15)
    }

    private fun scoreMomentumBear(i: IndicatorSet): Int {
        var s = 0
        if (i.rsi14 in 28.0..48.0) s += 10
        if (i.rsiSlope < -0.5) s += 4
        if (i.rsiBearishDivergence) s += 8
        if (i.rsi14 < 22) s -= 6
        return s.coerceIn(-15, 15)
    }

    private fun supportResistanceBull(i: IndicatorSet): Int {
        var s = 0
        val distSupportPct = if (i.price == 0.0) 99.0 else (i.price - i.supportZone.high) / i.price * 100.0
        if (distSupportPct in -0.5..2.0) s += 6
        if (i.breakoutUp) s += 10
        if (i.falseBreakout && i.price < i.resistance) s -= 7
        return s.coerceIn(-10, 12)
    }

    private fun supportResistanceBear(i: IndicatorSet): Int {
        var s = 0
        val distResPct = if (i.price == 0.0) 99.0 else (i.resistanceZone.low - i.price) / i.price * 100.0
        if (distResPct in -0.5..2.0) s += 6
        if (i.breakoutDown) s += 10
        if (i.falseBreakout && i.price > i.support) s -= 7
        return s.coerceIn(-10, 12)
    }

    private fun opposingLevelTooClose(i: IndicatorSet, buy: Boolean, sell: Boolean): Boolean {
        val minimumRoom = max(i.atr14 * 0.65, i.price * 0.003)
        if (buy && !i.breakoutUp && i.resistanceZone.low > i.price) return i.resistanceZone.low - i.price < minimumRoom
        if (sell && !i.breakoutDown && i.supportZone.high < i.price) return i.price - i.supportZone.high < minimumRoom
        return false
    }

    private fun contradictsHigherTimeframe(timeframe: String, mtf: MultiTimeframeContext, buy: Boolean, sell: Boolean): Boolean {
        val rank = mapOf("15m" to 1, "30m" to 2, "1h" to 3, "4h" to 4, "1d" to 5)
        val current = rank[timeframe] ?: 3
        return mtf.directionByTimeframe.any { (tf, direction) ->
            (rank[tf] ?: 0) > current && ((buy && direction == Direction.SELL) || (sell && direction == Direction.BUY))
        }
    }

    private fun historicalComponent(c: HistoricalCalibration): Int {
        val p = c.estimatedProbability ?: return 0
        val strength = when (c.confidence) {
            StatisticalConfidence.HIGH -> 8
            StatisticalConfidence.MEDIUM -> 5
            StatisticalConfidence.LOW -> 2
            StatisticalConfidence.INSUFFICIENT -> 0
        }
        return when {
            p >= 70 -> strength
            p <= 45 -> -strength
            else -> 0
        }
    }

    private fun calibratedProbability(c: HistoricalCalibration, technicalConfidence: Int): Int? {
        if (c.confidence == StatisticalConfidence.INSUFFICIENT || c.wins + c.losses < MIN_CALIBRATION_CASES) return null
        val hp = c.estimatedProbability ?: return null
        val histWeight = when (c.confidence) {
            StatisticalConfidence.HIGH -> 0.65
            StatisticalConfidence.MEDIUM -> 0.45
            StatisticalConfidence.LOW -> 0.25
            StatisticalConfidence.INSUFFICIENT -> 0.0
        }
        return (hp * histWeight + technicalConfidence * (1.0 - histWeight)).toInt().coerceIn(1, 99)
    }

    private const val MIN_CALIBRATION_CASES = 10

    private fun btcContext(symbol: String, regime: Regime?, bullish: Boolean): Int {
        if (symbol == "BTC" || regime == null) return 0
        return when (regime) {
            // BTC actúa como filtro de riesgo. Un contexto coincidente no crea
            // puntos positivos por sí solo; uno contrario sí resta confianza.
            Regime.TREND_UP -> if (bullish) 0 else -5
            Regime.TREND_DOWN -> if (bullish) -5 else 0
            Regime.HIGH_VOLATILITY -> -3
            else -> 0
        }
    }

    private fun addExplanation(out: MutableList<String>, input: Input, d: Direction) {
        val i = input.indicators
        out += "Régimen ${i.regime.name.replace('_', ' ')}; estructura ${i.structure.name}"
        out += "EMA20 ${fmt(i.ema20)} / EMA50 ${fmt(i.ema50)} / EMA200 ${fmt(i.ema200)}"
        out += "RSI ${i.rsi14.toInt()} (pendiente ${"%.1f".format(i.rsiSlope)}) • ADX ${i.adx14.toInt()} • +DI ${i.plusDi.toInt()} / -DI ${i.minusDi.toInt()}"
        out += "Volumen x${"%.2f".format(i.volumeRatio)} • ATR ${"%.2f".format(i.atrPct)}%"
        out += "MTF: ${input.mtf.summary}"
        if (i.rsiBullishDivergence) out += "Divergencia RSI alcista detectada"
        if (i.rsiBearishDivergence) out += "Divergencia RSI bajista detectada"
        if (i.breakoutUp) out += "Ruptura alcista con confirmación de volumen"
        if (i.breakoutDown) out += "Ruptura bajista con confirmación de volumen"
        if (i.falseBreakout) out += "Riesgo de falsa ruptura"
        if (input.calibration.estimatedProbability != null && input.calibration.confidence != StatisticalConfidence.INSUFFICIENT) {
            out += "${input.calibration.comparableCases} casos comparables; prob. histórica ${input.calibration.estimatedProbability}% (${input.calibration.confidence})"
        } else {
            out += "Probabilidad histórica sin calibrar: ${input.calibration.wins + input.calibration.losses}/$MIN_CALIBRATION_CASES resultados mínimos"
        }
        if (input.fundamental.headlineCount > 0) out += "Noticias: ${input.fundamental.summary}"
        out += "Dirección propuesta: ${d.name.replace('_', ' ')}"
    }

    private fun fmt(v: Double) = if (v >= 1000) "%.2f".format(v) else "%.6f".format(v)
}
