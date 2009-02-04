# TODO:
# - When garbage collected the namespaces created should be removed cleanly.
# - Determine a better value for 'module.__file__' when a namespace is created.

import os
import sys
import imp
import traceback
import types
import logging

class ScriptDirectory:
    dependencyResolutionPasses = 10

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
        ## Pass 1: Load all the valid scripts under the given directory.
        self.LoadDirectory(self.baseDirPath)
        
        ## Pass 2: Execute the scripts, ordering for dependencies and then add the namespace entries.
        scriptFilesToLoad = set(self.filesByPath.itervalues())
        attemptsLeft = self.dependencyResolutionPasses
        while len(scriptFilesToLoad) and attemptsLeft > 0:
            scriptFilesLoaded = set()
            for scriptFile in scriptFilesToLoad:
                if self.RunScript(scriptFile):
                    scriptFilesLoaded.add(scriptFile)

            # Update the set of scripts which have yet to be loaded.
            scriptFilesToLoad -= scriptFilesLoaded

            attemptsLeft -= 1

        if len(scriptFilesToLoad):
            logging.error("ScriptDirectory.Load failed to resolve dependencies")

            # Log information about the problematic script files.
            for scriptFile in scriptFilesToLoad:
                scriptFile.LogLastError()

            return False

        return True

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
        module.__package__ = baseNamespaceName

        self.namespaces[namespaceName] = module
        sys.modules[namespaceName] = module

        if baseNamespace is not None:
            setattr(baseNamespace, moduleName, module)

        return module

    def LoadScript(self, filePath, namespacePath):
        logging.info("LoadScript %s", filePath)

        return ScriptFile(filePath, namespacePath)

    def RunScript(self, scriptFile):
        logging.info("RunScript %s", scriptFile.filePath)

        if not scriptFile.Run():
            logging.info("RunScript:Failed to run '%s'", scriptFile.filePath)
            return False

        logging.info("RunScript:Ran '%s'", scriptFile.filePath)

        namespace = self.CreateNamespace(scriptFile.namespacePath)
        self.InsertModuleAttributes(scriptFile.scriptGlobals, namespace)

        return True

    def InsertModuleAttributes(self, attributes, namespace):
        moduleName = namespace.__name__

        for k, v in attributes.iteritems():
            if k == "__builtins__":
                continue

            valueType = type(v)
            # Modules will have been imported from elsewhere.
            if valueType is types.ModuleType:
                continue

            if valueType in (types.ClassType, types.TypeType):
                # Classes with valid modules will have been imported from elsewhere.
                if v.__module__ != "__builtin__":
                    continue

                v.__module__ = moduleName

            logging.info("InsertModuleAttribute %s.%s", moduleName, k)
            setattr(namespace, k, v)


class ScriptFile:
    lastError = None

    def __init__(self, filePath, namespacePath):
        self.filePath = filePath
        self.namespacePath = namespacePath

        self.scriptGlobals = {}

        self.Load(filePath)

    def Load(self, filePath):
        self.filePath = filePath

        script = open(self.filePath, 'r').read()
        self.codeObject = compile(script, self.filePath, "exec")
        
    def Run(self):
        self.scriptGlobals = {}
        try:
            eval(self.codeObject, self.scriptGlobals, self.scriptGlobals)
        except ImportError:
            self.lastError = traceback.format_exception(*sys.exc_info())
            return False

        return True

    def LogLastError(self, flush=True):
        if self.lastError is None:
            logging.error("Script file '%s' unexpectedly missing a last error", self.filePath)
            return

        logging.error("Script file '%s'", self.filePath)
        for line in self.lastError:
            logging.error("%s", line.rstrip("\r\n"))

        if flush:
            self.lastError = None


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    path = sys.path[0]
    dirPath = os.path.join(path, "script-hierarchy")
    gameScripts = ScriptDirectory(dirPath, "game")
    if not gameScripts.Load():
        sys.exit(0)
    
    import game
    game.Alpha
    import game.beta
    game.beta.Beta
    