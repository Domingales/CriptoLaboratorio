package com.domingales.criptoanalisis.multi.evaluation
import com.domingales.criptoanalisis.multi.domain.*
import kotlin.math.*
fun assertTrue(v:Boolean) { check(v) }
fun assertFalse(message:String,v:Boolean) { check(!v) { message } }
fun assertEquals(a:Any?,b:Any?) { check(a==b) { "Parity mismatch" } }
fun main() {
        fun sample(step: Long, size: Int) = (0 until size).map { i ->
            val p=100+sin(i*.17)*4+i*.01
            Candle(i*step,p,p+2,p-2,p+sin(i*.31),1000.0+i%11*90,i*step+step-1)
        }
        // Two contexts deliberately share timestamps but different prices: test cache isolation.
        val all=linkedMapOf("15m" to sample(900000L,580),"1h" to sample(900000L,580).map { it.copy(close=it.close*1.001,high=it.high*1.001) })
        val fine=sample(300000L,1740)
        val a=mutableListOf<AnalysisResult>(); val b=mutableListOf<AnalysisResult>()
        val aa=mutableListOf<Long>(); val bb=mutableListOf<Long>()
        val ra=BacktestEngine.run("ADA","15m",all,0,btcCandles4h=all.getValue("1h"),outcomeCandles5m=fine,auditThroughLatest=true,onEvaluation={a.add(it)},onAccepted={aa.add(it.candleCloseTime)})
        val rb=ExpandedResearchEngine.run("ADA","15m",all,0,btcCandles4h=all.getValue("1h"),outcomeCandles5m=fine,auditThroughLatest=true,onEvaluation={b.add(it)},onAccepted={bb.add(it.candleCloseTime)})
        // Wall-clock creation time is incidental; simulated candle time and every
        // indicator, decision, calibration and outcome must remain identical.
        fun normalized(rows: List<AnalysisResult>) = rows.map { it.copy(timestamp = 0L) }
        assertTrue(a.isNotEmpty()); assertEquals(normalized(a),normalized(b)); assertEquals(aa,bb); assertEquals(ra,rb)
        // Changing future candles must not alter earlier analyses or acceptance.
        val boundary=all.getValue("15m")[400].closeTime
        val changed=all.mapValues { (_,c) -> c.map { if(it.closeTime>boundary) it.copy(open=it.open*2,high=it.high*2,low=it.low*2,close=it.close*2) else it } }
        val future=mutableListOf<AnalysisResult>()
        ExpandedResearchEngine.run("ADA","15m",changed,0,btcCandles4h=all.getValue("1h"),outcomeCandles5m=fine,auditThroughLatest=true,onEvaluation={future.add(it)})
        assertEquals(normalized(b.filter { it.candleCloseTime<=boundary }),normalized(future.filter { it.candleCloseTime<=boundary }))
        // Availability is information too. Removing a future 5m candle must
        // never change acceptance before that candle, including cooldown.
        val missingAt=boundary+1+300000L
        val missingFine=fine.filter { it.openTime!=missingAt }
        assertEquals(fine.size-1,missingFine.size)
        val gapAccepted=mutableListOf<Long>()
        val gapAnalyses=mutableListOf<AnalysisResult>()
        ExpandedResearchEngine.run("ADA","15m",all,0,btcCandles4h=all.getValue("1h"),outcomeCandles5m=missingFine,auditThroughLatest=true,
            onEvaluation={gapAnalyses.add(it)},onAccepted={gapAccepted.add(it.candleCloseTime)})
        assertEquals(normalized(b.filter { it.candleCloseTime<=boundary }),normalized(gapAnalyses.filter { it.candleCloseTime<=boundary }))
        assertEquals(bb.filter { it<=boundary },gapAccepted.filter { it<=boundary })
        // Document the exception to untouched-engine parity rather than hide it.
        val untouchedGapAccepted=mutableListOf<Long>()
        BacktestEngine.run("ADA","15m",all,0,btcCandles4h=all.getValue("1h"),outcomeCandles5m=missingFine,auditThroughLatest=true,
            onAccepted={untouchedGapAccepted.add(it.candleCloseTime)})
        assertFalse("The regression fixture must expose the original future-availability leak",
            aa.filter { it<=boundary }==untouchedGapAccepted.filter { it<=boundary })
    }

