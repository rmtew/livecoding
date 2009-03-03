import os
import sys
import logging

# Temporary hack to bring in the namespace prototype.
if __name__ == "__main__":
    currentPath = sys.path[0]
    parentPath = os.path.dirname(currentPath)
    namespacePath = os.path.join(parentPath, "prototype-namespacing")
    if namespacePath not in sys.path:
        sys.path.append(namespacePath)

import namespace


class CodeReloader:
    def __init__(self):
        self.directoriesByPath = {}

    def AddDirectory(self, baseNamespace, baseDirPath):
        handler = self.directoriesByPath[baseDirPath] = namespace.ScriptDirectory(baseDirPath, baseNamespace)
        handler.Load()
        return handler

    def RemoveDirectory(self, baseDirPath):
        handler = self.directoriesByPath[baseDirPath]
        handler.Unload()

    def FindDirectory(self, filePath):
        filePathLower = filePath.lower()
        for dirPath, dirHandler in self.directoriesByPath.iteritems():
            if filePathLower.startswith(dirPath.lower()):
                return dirHandler

    def ProcessChangedFile(self, filePath, added=False, changed=False, deleted=False):
        dirHandler = self.FindDirectory(filePath)
        if dirHandler is None:
            logging.error("File change event for invalid path '%s'", filePath)
            return

        # Proceed to handle the file change.

    def ReloadScript(self, filePath):
        dirHandler = self.FindDirectory(filePath)
        oldScriptFile = dirHandler.FindScript(filePath)
        
        newScriptFile = dirHandler.LoadScript(filePath, oldScriptFile.namespacePath)
        print "XXX", oldScriptFile, newScriptFile

if __name__ == "__main__":
    scriptDirPath = os.path.join(currentPath, "scripts")
    exampleScriptPath = os.path.join(scriptDirPath, "example.py")

    cr = CodeReloader()
    cr.AddDirectory("game", scriptDirPath)

    import game
    oldKlass = game.Test

    cr.ReloadScript(exampleScriptPath)
