# TODO:
# - DestroyNamespace may be a little enthusiastic.  Should check the contents
#   of a namespace which is presumed to be clean, before deleting it.  If there
#   is something left, then do the appropriate thing.
# - The namespace contributions can only come from one ScriptDirectory.
#   - __file__ might be made shorter and clearer by using paths relative to
#     the base directory.

import os
import sys
import imp
import traceback
import types
import logging


class ScriptFile(object):
    lastError = None
    contributedAttributes = None

    def __init__(self, filePath, namespacePath):
        self.filePath = filePath
        self.namespacePath = namespacePath

        self.scriptGlobals = {}

        self.Load(filePath)

    def __repr__(self):
        return "<ScriptFile filePath='%s' namespacePath='%s'>" % (self.filePath, self.namespacePath)

    def Load(self, filePath):
        self.filePath = filePath

        script = open(self.filePath, 'r').read()
        self.codeObject = compile(script, self.filePath, "exec")

    def GetAttributeValue(self, attributeName):
        return self.scriptGlobals[attributeName]

    def SetContributedAttributes(self, contributedAttributes):
        self.contributedAttributes = contributedAttributes
        
    def Run(self):
        self.scriptGlobals = {}
        try:
            eval(self.codeObject, self.scriptGlobals, self.scriptGlobals)
        except ImportError:
            self.lastError = traceback.format_exception(*sys.exc_info())
            return False

        return True

    def LogLastError(self, flush=True, context="Unknown logic"):
        if self.lastError is None:
            logging.error("Script file '%s' unexpectedly missing a last error", self.filePath)
            return

        logging.error("Error executing script file '%s'", self.filePath)
        for line in self.lastError:
            logging.error("%s", line.rstrip("\r\n"))

        if flush:
            self.lastError = None


class ScriptDirectory(object):
    scriptFileClass = ScriptFile

    dependencyResolutionPasses = 10

    def __init__(self, baseDirPath=None, baseNamespace=None):
        # Script file objects indexed in different ways.
        self.filesByPath = {}
        self.filesByDirectory = {}

        # Personal references to created namespaces.
        self.namespaces = {}

        self.SetBaseDirectory(baseDirPath)
        self.SetBaseNamespaceName(baseNamespace)

    def __del__(self):
        self.Unload()

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
                    self.RegisterScript(scriptFile)
            else:
                logging.error("Unrecognised type of directory entry %s", entryPath)

    def Unload(self):
        logging.info("Cleaning up after removed directory '%s'", self.baseDirPath)

        for k, scriptFile in self.filesByPath.items():
            self.UnloadScript(scriptFile)
            del self.filesByPath[k]

        namespacePaths = self.namespaces.keys()
        namespacePaths.sort()
        namespacePaths.reverse()
        
        for namespacePath in namespacePaths:
            self.DestroyNamespace(namespacePath)

    def GetNamespace(self, namespaceName):
        return self.namespaces[namespaceName]

    def CreateNamespace(self, namespaceName, filePath):
        module = self.namespaces.get(namespaceName, None)
        if module is not None:
            if filePath in module.__file__:
                raise RuntimeError("Namespace already exists", namespaceName)
            return module

        if namespaceName in sys.modules:
            raise RuntimeError("Namespace already occupied", namespaceName)

        parts = namespaceName.rsplit(".", 1)
        if len(parts) == 2:
            baseNamespaceName, moduleName = parts
            baseNamespace = self.CreateNamespace(baseNamespaceName, filePath)
        else:
            baseNamespaceName, moduleName = None, parts[0]
            baseNamespace = None

        module = imp.new_module(moduleName)
        module.__name__ = moduleName
        # Our modules don't map to files.  Have a placeholder.
        module.__file__ = ""
        module.__package__ = baseNamespaceName

        self.namespaces[namespaceName] = module
        sys.modules[namespaceName] = module

        if baseNamespace is not None:
            setattr(baseNamespace, moduleName, module)

        return module

    def DestroyNamespace(self, namespaceName):
        module = self.namespaces.get(namespaceName, None)
        if module.__file__:
            logging.info("DestroyNamespace '%s' skipping, still used %s", namespaceName, module.__file__)
            return

        logging.info("DestroyNamespace '%s'", namespaceName)
        del sys.modules[namespaceName]
        del self.namespaces[namespaceName]

    def RegisterScript(self, scriptFile):
        # Index the file by its full path.
        self.filesByPath[scriptFile.filePath] = scriptFile

        dirPath = os.path.dirname(scriptFile.filePath)
        relativeDirPath = os.path.relpath(dirPath, self.baseDirPath)

        # Index the file with other files in the same directory.
        if relativeDirPath not in self.filesByDirectory:
            self.filesByDirectory[relativeDirPath] = []
        self.filesByDirectory[relativeDirPath].append(scriptFile)

    def UnregisterScript(self, scriptFile):
        dirPath = os.path.dirname(scriptFile.filePath)
        relativeDirPath = os.path.relpath(dirPath, self.baseDirPath)

        self.filesByDirectory[relativeDirPath].remove(scriptFile)
        if not len(self.filesByDirectory[relativeDirPath]):
            del self.filesByDirectory[relativeDirPath]

        del self.filesByPath[scriptFile.filePath]

    def FindScript(self, filePath):
        if filePath in self.filesByPath:
            return self.filesByPath[filePath]

    def LoadScript(self, filePath, namespacePath):
        logging.info("LoadScript %s", filePath)

        return self.scriptFileClass(filePath, namespacePath)

    def RunScript(self, scriptFile):
        logging.info("RunScript %s", scriptFile.filePath)

        if not scriptFile.Run():
            logging.info("RunScript:Failed to run '%s'", scriptFile.filePath)
            return False

        logging.info("RunScript:Ran '%s'", scriptFile.filePath)

        namespace = self.CreateNamespace(scriptFile.namespacePath, scriptFile.filePath)
        self.InsertModuleAttributes(scriptFile, namespace)

        return True

    def UnloadScript(self, scriptFile, force=False):
        namespace = self.GetNamespace(scriptFile.namespacePath)
        if self.RemoveModuleAttributes(scriptFile, namespace):
            return True
        return False            

    def InsertModuleAttributes(self, scriptFile, namespace, overwritableAttributes=set()):
        moduleName = namespace.__name__
        
        # Track what files have contributed to the namespace.
        if scriptFile.filePath not in namespace.__file__:
            if len(namespace.__file__):
                namespace.__file__ += ";"
            namespace.__file__ += scriptFile.filePath

        contributedAttributes = set()
        for k, v in scriptFile.scriptGlobals.iteritems():
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
                v.__file__ = scriptFile.filePath

            # By default we never overwrite.  This way we can identify duplicate contributions.
            if hasattr(namespace, k) and k not in overwritableAttributes:
                logging.error("Duplicate namespace contribution for '%s.%s' from '%s', our class = %s", moduleName, k, scriptFile.filePath, v.__file__ == scriptFile.filePath)
                continue

            logging.info("InsertModuleAttribute %s.%s", moduleName, k)
            setattr(namespace, k, v)
            contributedAttributes.add(k)

        scriptFile.SetContributedAttributes(contributedAttributes)

    def RemoveModuleAttributes(self, scriptFile, namespace):
        logging.info("RemoveModuleAttributes %s", scriptFile.filePath)

        paths = namespace.__file__.split(";")
        if scriptFile.filePath not in paths:
            raise RuntimeError("Namespace mismatch")
        paths.remove(scriptFile.filePath)
        namespace.__file__ = ";".join(paths)

        for k in scriptFile.contributedAttributes:
            # Is the attribute still in use?
            # self.PrintNamespaceEntryReferers(scriptFile, namespace, k)
            delattr(namespace, k)

        return True

    def PrintNamespaceEntryReferers(self, scriptFile, namespace, k):
        return
        v = getattr(namespace, k)
        import gc
        print "VALUE", v
        for ob1 in gc.get_referrers(v):
            # Ignore this function as a known referer.
            if ob1 is sys._getframe():
                continue

            # Ignore the namespace as a known referer.
            if ob1 is namespace.__dict__:
                continue

            # Ignore the contributing script file as a known referer.
            if ob1 is scriptFile.scriptGlobals:
                continue

            if type(ob1) is dict:
                print type(ob1), len(ob1)
                print ob1.keys()
            else:
                print type(ob1), ob1


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
    