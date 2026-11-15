import tempfile
import unittest
from pathlib import Path
import numpy as np
from research.parrondo_backtest import evaluate_file, run, timestamp

class ParrondoBacktestTests(unittest.TestCase):
    def test_missing_data_is_explicitly_not_evaluable(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            rows=run(root/'missing',root/'results',20)
            self.assertEqual(len(rows),30)
            self.assertTrue(all(r['status']=='NOT_EVALUABLE' for r in rows))
            self.assertTrue((root/'results/comparison.csv').exists())

    def test_no_future_prices_change_earlier_period(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            start=timestamp('2024-01-01')
            step=3600000
            a=np.array([[start+i*step,100+i*.01,101+i*.01,99+i*.01,100+i*.01,1,start+(i+1)*step-1] for i in range(240)],float)
            path=root/'BTC_1h.npy'
            np.save(path,a)
            first=evaluate_file(path,start+100*step,start+150*step,20)
            a[200:,1:5]*=1.5
            np.save(path,a)
            second=evaluate_file(path,start+100*step,start+150*step,20)
            self.assertEqual(first,second)

if __name__=='__main__':unittest.main()
