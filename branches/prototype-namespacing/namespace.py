# TODO:
# - When garbage collected the namespaces created should be removed cleanly.

import os
import sys
import imp
import types
import logging

class ScriptDirectory:
    def __init__(self, baseDirPath=None, baseNamespace=None):
        self.filesByPath = {}
        self.filesByDirectory = {}
        self.namespaces = {}

        self.SetBaseDirectory(baseDirPath)
        self.SetBaseNamespaceName(baseNamespace)

    def __del__(self):
        pass

    def SetBaseDirectory(self, baseDirPath):
        self.baseDirPath = baseDirPath

    def SetBaseNamespaceName(self, baseNamespaceName):
        self.baseNamespaceName = baseNamespaceName

    def Load(self):
        self.LoadDirectory(self.baseDirPath)

    def LoadDirectory(self, dirPath):
        logging.info("LoadDirectory %s", dirPath)

        namespace = self.baseNamespaceName
        relativeDirPath = os.path.relpath(dirPath, self.baseDirPath)
        if relativeDirPath != ".":
            namespace += "."+ relativeDirPath.replace(os.path.sep, ".")

        for entryName in os.listdir(dirPath):
            if entryName == ".svn":
                continue

            entryPath = os.path.join(dirPath, entryName)
            if os.path.isdir(entryPath):
                self.LoadDirectory(entryPath)
            elif os.path.isfile(entryPath):
                if entryName.endswith(".py"):
                    scriptFile = self.LoadScript(entryPath, namespace)

                    # Index the file by its full path.
                    self.filesByPath[entryPath] = scriptFile
                    
                    # Index the file with other files in the same directory.
                    if relativeDirPath not in self.filesByDirectory:
                        self.filesByDirectory[relativeDirPath] = []
                    self.filesByDirectory[relativeDirPath].append(scriptFile)
            else:
                logging.error("Unrecognised type of directory entry %s", entryPath)

    def CreateNamespace(self, namespaceName):
        module = self.namespaces.get(namespaceName, None)
        if module is not None:
            return module

        if namespaceName in sys.modules:
            raise RuntimeError("Namespace already exists", namespaceName)

        parts = namespaceName.rsplit(".", 1)
        if len(parts) == 2:
            baseNamespaceName, moduleName = parts
            baseNamespace = self.CreateNamespace(baseNamespaceName)
        else:
            baseNamespaceName, moduleName = None, parts[0]
            baseNamespace = None

        module = imp.new_module(moduleName)
        module.__name__ = moduleName
        # Our modules don't map to files.  Have a placeholder.
        module.__file__ = "DIRECTORY("+ namespaceName +")"

        self.namespaces[namespaceName] = module
        sys.modules[namespaceName] = module

        if baseNamespace is not None:
            setattr(baseNamespace, moduleName, module)

        return module

    def LoadScript(self, filePath, namespacePath):
        logging.info("LoadScript %s", filePath)

        scriptFile = ScriptFile(filePath)
        namespace = self.CreateNamespace(namespacePath)
        self.InsertModuleAttributes(scriptFile.scriptGlobals, namespace)

        return scriptFile

    def InsertModuleAttributes(self, attributes, namespace):
        moduleName = namespace.__name__

        for k, v in attributes.iteritems():
            if k == "__builtins__":
                continue

            if type(v) is types.ClassType or type(v) is types.TypeType:
                v.__module__ = moduleName

            logging.info("InsertModuleAttribute %s %s", k, namespace.__file__)
            setattr(namespace, k, v)


class ScriptFile:
    def __init__(self, filePath):
        self.Load(filePath)

    def Load(self, filePath):
        self.filePath = filePath

        script = open(self.filePath, 'r').read()
        self.codeObject = compile(script, self.filePath, "exec")
        
        self.scriptGlobals = {}
        eval(self.codeObject, self.scriptGlobals, self.scriptGlobals)



if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    path = sys.path[0]
    dirPath = os.path.join(path, "script-hierarchy")
    gameScripts = ScriptDirectory(dirPath, "game")
    gameScripts.Load()
    
    import game
    game.Alpha
    import game.beta
    game.beta.Beta
    