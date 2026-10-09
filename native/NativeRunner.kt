package com.domingales.criptoanalisis.multi.evaluation
import com.domingales.criptoanalisis.multi.domain.*
import java.io.File
import kotlin.math.*
class NativeRunner {
    private val steps = linkedMapOf("15m" to 900000L, "30m" to 1800000L, "1h" to 3600000L,
        "4h" to 14400000L, "1d" to 86400000L)
    private fun series(dir: File, name: String): List<Candle> = File(dir,"$name.csv").useLines { lines ->
        lines.drop(1).map { line -> val v=line.split(',')
            Candle(v[0].toLong(),v[1].toDouble(),v[2].toDouble(),v[3].toDouble(),v[4].toDouble(),v[5].toDouble(),v[6].toLong())
        }.toList()
    }
    private fun upper(c: List<Candle>, t: Long): Int {
        var lo=0; var hi=c.size
        while(lo<hi) { val m=(lo+hi)/2; if(c[m].closeTime<=t) lo=m+1 else hi=m }
        return lo
    }
    private fun valid(c: List<Candle>, step: Long): Set<Long> {
        var streak=0
        return c.indices.filter { i ->
            streak = if(c[i].closeTime!=c[i].openTime+step-1) 0 else
                if(i>0 && c[i].openTime==c[i-1].openTime+step) streak+1 else 1
            // Same 210 minimum / up to 300 closed lookback as the previous adapter.
            i>=209 && streak>=min(300,i+1)
        }.map { c[it].closeTime }.toSet()
    }
    fun run() {
        val dir=System.getenv("EXPANDED_DATA_DIR")?.let(::File) ?: return
        val symbol=System.getenv("EXPANDED_SYMBOL") ?: error("EXPANDED_SYMBOL")
        val tf=System.getenv("EXPANDED_TF") ?: error("EXPANDED_TF")
        require(tf in steps)
        val out=File(System.getenv("EXPANDED_KOTLIN_DIR") ?: error("EXPANDED_KOTLIN_DIR")); out.mkdirs()
        val wanted=linkedSetOf("15m",tf,"4h","1d")
        val all=wanted.associateWith { series(dir,symbol+"USDT_"+it) }
        val btc=series(dir,"BTCUSDT_4h"); val fine=series(dir,symbol+"USDT_5m")
        val validTimes=all.mapValues { (k,c) -> valid(c,steps.getValue(k)) }
        val btcValid=valid(btc,steps.getValue("4h"))
        var excluded=0
        File(out,"kotlin_decisions.csv").printWriter().use { decisions ->
            File(out,"kotlin_accepted.csv").printWriter().use { accepted ->
                decisions.println("signalCloseTime,direction,entry,targetPct,confidence,probability,isSignal,regime,atrPct,volumeRatio,adx,rsi,mtfScore,comparableCases,rejectionReason")
                accepted.println("signalCloseTime")
                val result=ExpandedResearchEngine.run(symbol,tf,all,81,btcCandles4h=btc,outcomeCandles5m=fine,auditThroughLatest=true,
                    evaluationEligible={ t ->
                        val ok=all.all { (k,c) ->
                            val time=c.getOrNull(upper(c,t)-1)?.closeTime
                            time==((t+1)/steps.getValue(k))*steps.getValue(k)-1 && time in validTimes.getValue(k)
                        } && (symbol=="BTC" || btc.getOrNull(upper(btc,t)-1)?.closeTime.let { time ->
                            time==((t+1)/14400000L)*14400000L-1 && time in btcValid
                        })
                        if(!ok) excluded++
                        ok
                    },onEvaluation={ a ->
                        decisions.println(listOf(a.candleCloseTime,a.direction,a.indicators.price,max(.45,a.indicators.atrPct*.55),
                            a.confidence,a.probability ?: "",a.isSignal,a.indicators.regime,a.indicators.atrPct,a.indicators.volumeRatio,
                            a.indicators.adx14,a.indicators.rsi14,a.mtf.alignmentScore,a.calibration.comparableCases).joinToString(",")+
                            ",\""+a.rejectionReason.replace("\"","\"\"")+"\"")
                        decisions.flush()
                    },onAccepted={ accepted.println(it.candleCloseTime); accepted.flush() })
                File(out,"kotlin_summary.txt").writeText("evaluated=${result.evaluatedWindows}\nexcluded_context=$excluded\nmissing_5m=${result.missingFiveMinuteData}\n")
                println("EXPANDED $symbol $tf evaluated=${result.evaluatedWindows} excluded=$excluded")
            }
        }
    }
}

fun main() { NativeRunner().run() }
