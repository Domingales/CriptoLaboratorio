import datetime, json, tempfile, unittest
from pathlib import Path
from research.scheduled_run import prepare, verify

class ScheduledTests(unittest.TestCase):
    def test_year_boundary_extends_data_only(self):
        original=json.loads((Path(__file__).resolve().parents[1]/'docs/protocol.json').read_text())
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);(root/'docs').mkdir()
            (root/'docs/protocol.json').write_text(json.dumps(original))
            registered=prepare(root,datetime.date(2027,1,3))
            actual=json.loads((root/'docs/protocol.json').read_text())
            self.assertEqual(registered['download_end'],'2026-12')
            self.assertEqual(actual,dict(original,source_end_exclusive='2027-01-01T00:00:00Z'))

    def test_partial_execution_cannot_be_green(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);(root/'results').mkdir()
            (root/'results/summary.json').write_text(json.dumps({'results':[{'status':'ERROR'}]*15}))
            with self.assertRaisesRegex(RuntimeError,'Not all 15'):verify(root)

if __name__=='__main__':unittest.main()
