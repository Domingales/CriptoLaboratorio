"""Frozen, causal Parrondo-style policy comparison. Research only; never sends orders."""
from dataclasses import dataclass
import math

@dataclass(frozen=True)
class Bar:
    time: int
    open: float
    high: float
    low: float
    close: float

def _valid(bars):
    if len(bars) < 52:
        raise ValueError("At least 52 consecutive bars are required")
    if any(not all(math.isfinite(v) and v > 0 for v in (b.open,b.high,b.low,b.close)) or
           b.low > min(b.open,b.close) or b.high < max(b.open,b.close) for b in bars):
        raise ValueError("Invalid OHLC")
    diffs=[bars[i].time-bars[i-1].time for i in range(1,len(bars))]
    if diffs[0] <= 0 or any(d != diffs[0] for d in diffs):
        raise ValueError("Nonconsecutive bars: do not score missing data")

def policies(bars):
    """At close t decide direction for open t+1. No forward data in decisions.
    A: mean reversion relative to prior 20-bar mean; B: 20/50 SMA trend.
    C: AABB switching by decision index; state-C uses trailing volatility.
    All parameters are fixed here, not tuned on evaluation results.
    """
    _valid(bars)
    out=[]
    for t in range(49,len(bars)-1):
        closes=[b.close for b in bars[t-49:t+1]]
        ma20=sum(closes[-20:])/20
        ma50=sum(closes)/50
        a=-1 if bars[t].close > ma20 else 1
        b=1 if ma20 >= ma50 else -1
        ret=[math.log(closes[i]/closes[i-1]) for i in range(30,50)]
        vol=math.sqrt(sum(v*v for v in ret)/len(ret))
        # Pre-registered illustrative state rule: choose B when recent
        # absolute 1-bar return exceeds trailing 20-bar RMS return.
        state_b=abs(ret[-1]) > vol
        out.append(dict(t=t,time=bars[t].time,A=a,B=b,
                        C_aabb=(a if len(out)%4 < 2 else b),
                        C_state=(b if state_b else a)))
    return out

def evaluate(bars, cost_bps=20):
    """One-bar non-overlapping research episodes, gross close-to-next-open excluded.
    Entry next bar OPEN, exit next bar CLOSE; cost is round-trip in bps.
    Each policy has identical exposure and execution timing.
    """
    if cost_bps < 0 or not math.isfinite(cost_bps):
        raise ValueError("Invalid cost")
    decisions=policies(bars)
    keys=("A","B","C_aabb","C_state")
    results={k:[] for k in keys}
    for d in decisions:
        candle=bars[d["t"]+1]
        for k in keys:
            side=d[k]
            gross=side*(candle.close/candle.open-1)
            results[k].append(gross-cost_bps/10000)
    metrics={}
    for k,values in results.items():
        wealth=1.;peak=1.;max_dd=0.
        for r in values:
            wealth*=1+r
            peak=max(peak,wealth)
            max_dd=min(max_dd,wealth/peak-1)
        metrics[k]=dict(n=len(values),mean_net=sum(values)/len(values),
                        total_compound=wealth-1,max_drawdown=max_dd,
                        positive_net_rate=sum(v>0 for v in values)/len(values))
    # A true Parrondo claim requires BOTH components losing, mixture winning.
    claim={k:(metrics["A"]["mean_net"]<0 and metrics["B"]["mean_net"]<0
              and metrics[k]["mean_net"]>0) for k in ("C_aabb","C_state")}
    return dict(metrics=metrics,parrondo_candidate=claim,
                caveat="Exploratory one-bar long/short scenario; no statistical significance or spot feasibility established")
