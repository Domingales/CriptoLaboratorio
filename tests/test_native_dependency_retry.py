import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import patch
from research import native_reference

class NativeDependencyTests(unittest.TestCase):
    def test_transient_504_retries_and_writes_complete_jar(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            (root/'native').mkdir()
            (root/'docs').mkdir()
            calls=[]
            class Response:
                def __enter__(self): return self
                def __exit__(self,*args): return False
                def read(self,n=-1):
                    if not hasattr(self,'read_once'):
                        self.read_once=True
                        return b'valid-jar-bytes'
                    return b''
            def fetch(url,timeout):
                calls.append(url)
                if len(calls)==1: raise urllib.error.HTTPError(url,504,'Gateway Timeout',None,None)
                return Response()
            # All artifact requests are parallel; this test uses a single dependency.
            with patch.object(native_reference,'ARTIFACTS',[('test','dependency','1')]), \
                 patch.object(native_reference.urllib.request,'urlopen',side_effect=fetch), \
                 patch.object(native_reference.time,'sleep'), \
                 patch.object(native_reference.subprocess,'run'):
                native_reference.setup(root)
            self.assertEqual(len(calls),2)
            self.assertEqual((root/'private/jvm/dependency-1.jar').read_bytes(),b'valid-jar-bytes')
            self.assertFalse((root/'private/jvm/dependency-1.jar.part').exists())

    def test_permanent_404_does_not_retry(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);(root/'native').mkdir();(root/'docs').mkdir()
            calls=[]
            def fetch(url,timeout):
                calls.append(url)
                raise urllib.error.HTTPError(url,404,'Not Found',None,None)
            with patch.object(native_reference,'ARTIFACTS',[('test','dependency','1')]), \
                 patch.object(native_reference.urllib.request,'urlopen',side_effect=fetch), \
                 patch.object(native_reference.time,'sleep'):
                with self.assertRaises(urllib.error.HTTPError): native_reference.setup(root)
            self.assertEqual(len(calls),1)

if __name__=='__main__': unittest.main()
