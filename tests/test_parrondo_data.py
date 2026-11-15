import unittest
import numpy as np
from research.parrondo_data import aggregate_hourly

class HourlyAggregationTests(unittest.TestCase):
    def candles(self,n):
        step=3600000
        return np.array([[i*step,100+i,101+i,99+i,100+i,1,(i+1)*step-1] for i in range(n)],float)

    def test_4h_from_1h(self):
        out=aggregate_hourly(self.candles(8),4*3600000)
        self.assertEqual(len(out),2)
        self.assertEqual(out[0,4],103)
        self.assertEqual(out[0,5],4)

    def test_1d_from_1h(self):
        out=aggregate_hourly(self.candles(48),24*3600000)
        self.assertEqual(len(out),2)

    def test_missing_hour_drops_bucket(self):
        a=np.delete(self.candles(8),2,axis=0)
        out=aggregate_hourly(a,4*3600000)
        self.assertEqual(len(out),1)
        self.assertEqual(out[0,0],4*3600000)

if __name__=='__main__': unittest.main()
