package com.domingales.criptoanalisis.multi.domain

data class CryptoAsset(val symbol: String, val name: String)

data class Candle(
    val openTime: Long,
    val open: Double,
    val high: Double,
    val low: Double,
    val close: Double,
    val volume: Double,
    val closeTime: Long
)

enum class Direction { BUY, SELL, WAIT, REVERSAL_BUY, REVERSAL_SELL }
enum class Regime { TREND_UP, TREND_DOWN, RANGE, HIGH_VOLATILITY, LOW_VOLATILITY, BREAKOUT, POSSIBLE_REVERSAL, MIXED }
enum class MarketStructure { BULLISH, BEARISH, SIDEWAYS, MIXED }
enum class EvaluationState { EVALUATION, PRESIGNAL, SIGNAL, ALERT, RESULT }
enum class StatisticalConfidence { INSUFFICIENT, LOW, MEDIUM, HIGH }
enum class OutcomeStatus { PENDING, HIT, FAIL, NEUTRAL }

data class SupportResistanceZone(
    val low: Double,
    val high: Double,
    val touches: Int,
    val strength: Int
)

data class IndicatorSet(
    val price: Double,
    val ema20: Double,
    val ema50: Double,
    val ema200: Double,
    val ema20SlopePct: Double,
    val ema50SlopePct: Double,
    val rsi14: Double,
    val rsiSlope: Double,
    val rsiBullishDivergence: Boolean,
    val rsiBearishDivergence: Boolean,
    val atr14: Double,
    val atrPct: Double,
    val adx14: Double,
    val plusDi: Double,
    val minusDi: Double,
    val volumeRatio: Double,
    val volumeExpansion: Boolean,
    val support: Double,
    val resistance: Double,
    val supportZone: SupportResistanceZone,
    val resistanceZone: SupportResistanceZone,
    val structure: MarketStructure,
    val regime: Regime,
    val breakoutUp: Boolean,
    val breakoutDown: Boolean,
    val falseBreakout: Boolean,
    val expectedMoveAtr: Double
)

data class MultiTimeframeContext(
    val byTimeframe: Map<String, Regime>,
    val directionByTimeframe: Map<String, Direction>,
    val alignmentScore: Int,
    val summary: String
)

data class HistoricalCalibration(
    val comparableCases: Int,
    val wins: Int,
    val losses: Int,
    val neutral: Int,
    val estimatedProbability: Int?,
    val confidence: StatisticalConfidence
)

data class FundamentalContext(
    val score: Int,
    val headlineCount: Int,
    val positiveCount: Int,
    val negativeCount: Int,
    val summary: String,
    val updatedAt: Long
)

data class ScoreBreakdown(
    val trend: Int,
    val momentum: Int,
    val volume: Int,
    val structure: Int,
    val supportResistance: Int,
    val mtf: Int,
    val volatility: Int,
    val historical: Int,
    val btcContext: Int,
    val fundamental: Int
) {
    val total: Int get() = (trend + momentum + volume + structure + supportResistance + mtf + volatility + historical + btcContext + fundamental).coerceIn(-100, 100)
}

data class AnalysisResult(
    val symbol: String,
    val timeframe: String,
    val timestamp: Long,
    val candleCloseTime: Long,
    val indicators: IndicatorSet,
    val mtf: MultiTimeframeContext,
    val btcRegime: Regime?,
    val calibration: HistoricalCalibration,
    val fundamental: FundamentalContext,
    val breakdown: ScoreBreakdown,
    val direction: Direction,
    val score: Int,
    val confidence: Int,
    val probability: Int?,
    val risk: String,
    val forecastLowPct: Double,
    val forecastHighPct: Double,
    val invalidationPrice: Double,
    val state: EvaluationState,
    val isPreSignal: Boolean,
    val isSignal: Boolean,
    val rejectionReason: String,
    val explanation: List<String>,
    val dataComplete: Boolean,
    val missingData: List<String>,
    val decisionThreshold: Int,
    val closedCandleEvaluation: Boolean,
    val allowBuy: Boolean,
    val allowSell: Boolean
)

data class DashboardItem(
    val symbol: String,
    val timeframe: String,
    val price: Double,
    val direction: String,
    val score: Int,
    val confidence: Int,
    val probability: Int?,
    val risk: String,
    val regime: String,
    val state: String,
    val updatedAt: Long,
    val changePct: Double,
    val lastAlertAt: Long?,
    val activeFollowups: Int
)

data class PerformanceSummary(
    val totalSignals: Int,
    val pending: Int,
    val hits: Int,
    val fails: Int,
    val neutral: Int,
    val resolvedAccuracy: Double
)

data class BacktestCase(
    val symbol: String,
    val timeframe: String,
    val signalCloseTime: Long,
    val direction: Direction,
    val entry: Double,
    val confidence: Int,
    val historicalProbability: Int?,
    val targetPct: Double,
    val outcome: OutcomeStatus,
    val outcomeTime: Long?,
    val outcomeReason: String
)

data class BacktestResult(
    val symbol: String,
    val timeframe: String,
    val signals: Int,
    val hits: Int,
    val fails: Int,
    val neutral: Int,
    val accuracy: Double,
    val evaluatedWindows: Int = 0,
    val skippedWithoutMtf: Int = 0,
    val buy: DirectionBacktestResult = DirectionBacktestResult(),
    val sell: DirectionBacktestResult = DirectionBacktestResult(),
    val walkForwardCasesUsed: Int = 0,
    val btcContextWindows: Int = 0,
    val fundamentalContextWindows: Int = 0,
    val contextNote: String = "",
    val cases: List<BacktestCase> = emptyList(),
    val missingFiveMinuteData: Int = 0
)

data class HistoricalFundamentalPoint(
    val timestamp: Long,
    val context: FundamentalContext
)

data class DirectionBacktestResult(
    val signals: Int = 0,
    val hits: Int = 0,
    val fails: Int = 0,
    val neutral: Int = 0
) {
    val accuracy: Double
        get() = if (hits + fails == 0) 0.0 else 100.0 * hits / (hits + fails)
}
