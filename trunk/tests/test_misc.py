from __future__ import with_statement
import livecoding
import support
import sys, os, unittest, __builtin__

aFileName = os.path.join("A", "a.py")

aContentsBase = """
class ClassA:
    def FunctionA(self):
        return "a1"
"""

aContentsFunctionChange = """
class ClassA:
    def FunctionA(self):
        return "a2"
"""

bContents = """
class ClassB:
    def FunctionB(self):
        return "b1"
"""

d1 = {
    "A": {
        "a.py": aContentsBase,
    },
    "B": {
        "b.py": bContents,
    },
}

class MiscTestCase(unittest.TestCase):
    def test_importing(self):
        with support.MonkeyPatcher() as mp:
            mp.SetDirectoryStructure(d1)
            mp.SetFileContents(aFileName, aContentsBase)

            cm = livecoding.CodeManager()
            cm.AddDirectory("A", "base")

            from base import ClassA
            a = ClassA()
            self.assertEqual(a.FunctionA(), "a1")


    def test_file_update(self):
        with support.MonkeyPatcher() as mp:
            mp.SetDirectoryStructure(d1)
            mp.SetFileContents(aFileName, aContentsBase)

            cm = livecoding.CodeManager()
            cm.AddDirectory("A", "base")

            mp.SetFileContents(aFileName, aContentsFunctionChange)

            cm.ProcessChangedFile(aFileName, changed=True)

            from base import ClassA
            a = ClassA()
            self.assertEqual(a.FunctionA(), "a2")
