from __future__ import with_statement
import livecoding, support
import types, sys, os, unittest, weakref, __builtin__

aFileName = os.path.join("A", "a.py")
bFileName = os.path.join("B", os.path.join("C", "b.py"))

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

bContentsBase = """
from base import ClassA
class ClassB(ClassA):
    def FunctionB(self):
        return "b1"
"""

d1 = {
    "A": {
        "a.py": aContentsBase,
    },
    "B": {
        "C": {
            "b.py": bContentsBase,
        },
    },
}

class SupportTestCase(unittest.TestCase):
    def test_monkeypatching(self):
        # Verify that the monkeypatcher leaves things as they were before
        # it replaced them.  Given that it automatically detects what to
        # replace where, it should be sufficient to check this one.
        self.failUnless(isinstance(os.listdir, types.BuiltinFunctionType))
        with support.MonkeyPatcher() as mp:
            self.failUnless(not isinstance(os.listdir, types.BuiltinFunctionType))
        self.failUnless(isinstance(os.listdir, types.BuiltinFunctionType))

class ImportTestCase(unittest.TestCase):
    def test_importing(self):
        with support.MonkeyPatcher() as mp:
            mp.SetDirectoryStructure(d1)
            mp.SetFileContents(aFileName, aContentsBase)

            cm = livecoding.CodeManager()
            cm.AddDirectory("A", "base")

            from base import ClassA
            a = ClassA()
            self.failUnlessEqual(a.FunctionA(), "a1")

    def test_subclassing_dependencies(self):
        with support.MonkeyPatcher() as mp:
            mp.SetDirectoryStructure(d1)
            mp.SetFileContents(aFileName, aContentsBase)
            mp.SetFileContents(bFileName, bContentsBase)

            cm = livecoding.CodeManager()
            cm.AddDirectory("A", "base")
            cm.AddDirectory("B", "base")

            from base import ClassA
            from base.C import ClassB
            a, b = ClassA(), ClassB()
            self.failUnlessEqual(a.FunctionA(), b.FunctionA())

    def test_directory_removal(self):
        with support.MonkeyPatcher() as mp:
            mp.SetDirectoryStructure(d1)
            mp.SetFileContents(aFileName, aContentsBase)
            mp.SetFileContents(bFileName, bContentsBase)

            cm = livecoding.CodeManager()
            cm.AddDirectory("A", "base")
            cm.AddDirectory("B", "base")
            cm.RemoveDirectory("B")

            try:
                from base import C
                self.fail("namespace entry 'C' still available")
            except ImportError:
                pass

            cm.RemoveDirectory("A")

            try:
                import base
                self.fail("namespace entry 'base' still available")
            except ImportError:
                pass

    def test_garbage_collection(self):
        """ It is an expectation that when all known references to the code
            manager are released, then the code manager will be released itself. """
        with support.MonkeyPatcher() as mp:
            mp.SetDirectoryStructure(d1)
            mp.SetFileContents(aFileName, aContentsBase)

            cm = livecoding.CodeManager()
            cm.AddDirectory("A", "base")

        cmProxy = weakref.ref(cm)
        del cm
        # At this point the code manager will have been cleaned up.
        self.failUnless(cmProxy() is None)

class UpdateTestCase(unittest.TestCase):
    def test_file_update(self):
        with support.MonkeyPatcher() as mp:
            mp.SetDirectoryStructure(d1)
            mp.SetFileContents(aFileName, aContentsBase)
            mp.SetFileContents(bFileName, bContentsBase)

            cm = livecoding.CodeManager()
            cm.AddDirectory("A", "base")
            cm.AddDirectory("B", "base")

            mp.SetFileContents(aFileName, aContentsFunctionChange)

            cm.ProcessChangedFile(aFileName, changed=True)

            from base.C import ClassB
            b = ClassB()
            self.failUnlessEqual(b.FunctionA(), "a2")
