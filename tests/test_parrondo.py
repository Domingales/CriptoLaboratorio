import unittest
from research.parrondo import Bar, policies, evaluate

class ParrondoTests(unittest.TestCase):
    def bars(self, n=120):
        return [Bar(i*3600000,100+i*.02,101+i*.02,99+i*.02,100+i*.02) for i in range(n)]

    def test_no_future_leakage(self):
        original=self.bars()
        changed=list(original)
        changed[100]=Bar(changed[100].time,200,201,199,200)
        a=policies(original)
        b=policies(changed)
        self.assertEqual([r for r in a if r['t']<100],[r for r in b if r['t']<100])

    def test_nonconsecutive_rejected(self):
        a=self.bars()
        a[60]=Bar(a[60].time+1,a[60].open,a[60].high,a[60].low,a[60].close)
        with self.assertRaises(ValueError): evaluate(a)

    def test_no_zero_cost_alpha_on_flat_candles(self):
        a=[Bar(i*3600000,100,100,100,100) for i in range(100)]
        r=evaluate(a,cost_bps=20)
        for metric in r['metrics'].values():
            self.assertAlmostEqual(metric['mean_net'],-.002)
        self.assertFalse(any(r['parrondo_candidate'].values()))

    def test_fixed_number_and_identical_exposure(self):
        r=evaluate(self.bars())
        self.assertEqual(set(v['n'] for v in r['metrics'].values()),{70})

    def test_invalid_cost(self):
        with self.assertRaises(ValueError): evaluate(self.bars(),-1)

if __name__=='__main__': unittest.main()
