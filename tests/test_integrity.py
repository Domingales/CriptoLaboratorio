import unittest
import numpy as np
from research.download import aggregate
from research.experiment import features,resolve,valid_windows,episode_selection,wilson

class IntegrityTests(unittest.TestCase):
    def fine(self,n=12):
        return np.array([[i*300000,100,100.2,99.8,100,10,(i+1)*300000-1] for i in range(n)],dtype=float)
    def test_future_prices_do_not_change_past_features(self):
        a=self.fine(500);a[:,4]=100+np.arange(500)*.01+np.sin(np.arange(500)/3)*.1
        a[:,1]=a[:,4];a[:,2]=a[:,4]+.2;a[:,3]=a[:,4]-.2
        b=a.copy();b[350:,1:5]*=2;b[350:,5]*=10
        x,atr,side,regime=features(a);xx,aa,ss,rr=features(b)
        np.testing.assert_allclose(x.iloc[:350],xx.iloc[:350],equal_nan=True)
        np.testing.assert_allclose(atr[:350],aa[:350],equal_nan=True)
        np.testing.assert_equal(side[:350],ss[:350])
    def test_both_barriers_same_candle_is_ambiguous(self):
        a=self.fine();a[1,2:4]=[102,98]
        self.assertEqual(resolve(a,0,100,.01,3600000)['status'],'AMBIGUOUS')
    def test_gap_stop_uses_worse_open(self):
        a=self.fine();a[1,1:5]=[97,97.2,96.8,97]
        r=resolve(a,0,100,.01,3600000);self.assertEqual(r['status'],'FAIL');self.assertAlmostEqual(r['net'],-.032)
    def test_missing_fine_candle_never_scored_as_hit(self):
        a=self.fine();a[0,2]=103
        self.assertEqual(resolve(np.delete(a,8,axis=0),0,100,.01,3600000)['status'],'MISSING')
    def test_sell_hit_is_downward(self):
        a=self.fine();a[2,3]=98
        r=resolve(a,0,100,.01,3600000,-1);self.assertEqual(r['status'],'HIT');self.assertAlmostEqual(r['net'],.008)
    def test_no_signal_candle_used_in_outcome(self):
        a=self.fine(24);a[0,2]=110
        self.assertEqual(resolve(a,3600000,100,.01,3600000)['status'],'NEUTRAL')
    def test_aggregate_omits_incomplete_candles(self):
        a=self.fine(24);a=np.delete(a,4,axis=0);b=aggregate(a,3600000)
        self.assertEqual(len(b),1);self.assertEqual(b[0,0],3600000)
    def test_cooldown_is_outcome_independent(self):
        indices=np.arange(30);accept=np.ones(30,dtype=bool)
        self.assertEqual(episode_selection(indices,accept,5),[0,6,12,18,24])
    def test_cooldown_uses_clock_when_future_candles_are_missing(self):
        times=np.array([0,1,2,7,8,9,10])*3600000
        chosen=episode_selection(np.arange(7),np.ones(7,dtype=bool),5,times,3600000)
        self.assertEqual(chosen,[0,3])
    def test_warmup_resets_after_gap(self):
        a=self.fine(500);a[300:,0]+=300000;a[300:,6]+=300000
        valid=valid_windows(a,300000,220)
        self.assertTrue(valid[299]);self.assertFalse(valid[300]);self.assertFalse(valid[-1])
    def test_small_sample_not_100_percent_certainty(self):
        low,high=wilson(2,2);self.assertLess(low,.5);self.assertAlmostEqual(high,1)

if __name__=='__main__':unittest.main()
