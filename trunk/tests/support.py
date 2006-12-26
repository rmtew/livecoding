# Want a base object which will only provide calls I want it to provide and
# only accept the arguments I want and then return the result I want.

from __future__ import with_statement
import os, weakref, types
import __builtin__

class Object(object):
    pass

class MonkeyPatcher(object):
    def __init__(self):
        self.dirTree = {}

    def __enter__(self):
        self._open = __builtin__.open
        __builtin__.open = self.open

        self._os_path_isfile = os.path.isfile
        os.path.isfile = self.os_path_isfile

        self._os_listdir = os.listdir
        os.listdir = self.os_listdir

        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        os.listdir = self._os_listdir
        os.path.isfile = self._os_path_isfile
        __builtin__.open = self._open

        return False

    # ...

    def SetDirectoryStructure(self, dirTree):
        self.dirTree = dirTree

    def GetDirectoryEntry(self, path):
        v = self.dirTree
        bits = path.split(os.path.sep)
        for bit in bits:
            v = v[bit]
        return v

    def SetFileContents(self, path, contents):
        dirPath, fileName = os.path.split(path)
        v = self.GetDirectoryEntry(dirPath)
        v[fileName] = contents

    # Monkeypatched functions.

    def os_listdir(self, path):
        v = self.GetDirectoryEntry(path)
        if type(v) is dict:
            return v.keys()
        elif type(v) is list:
            return v

    def os_path_isfile(self, path):
        v = self.GetDirectoryEntry(path)
        return type(v) in types.StringTypes

    def open(self, path):
        v = self.GetDirectoryEntry(path)

        instance = Object()
        instance.read = lambda: v
        instance.close = lambda: None
        return instance

if __name__ == "__main__":
    d = {
        "A": {
            "a.py": "#...",
        },
        "B": {
            "b.py": "#...",
        },
    }

    aFileName = os.path.join("A", "a.py")

    with MonkeyPatcher() as mp:
        mp.SetDirectoryStructure(d)

        print os.listdir("A")

        mp.SetFileContents(aFileName, "#....")
