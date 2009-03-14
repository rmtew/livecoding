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

# ----------------------------------------------------------------------------

import namespace

MODE_OVERWRITE = 1
MODE_UPDATE = 2

class CodeReloader:
    def __init__(self, mode=MODE_OVERWRITE):
        self.mode = mode
        self.directoriesByPath = {}

        self.leakedAttributes = {}

    def AddDirectory(self, baseNamespace, baseDirPath):
        handler = self.directoriesByPath[baseDirPath] = ReloadableScriptDirectory(baseDirPath, baseNamespace)
        handler.Load()
        return handler

    def RemoveDirectory(self, baseDirPath):
        handler = self.directoriesByPath[baseDirPath]
        handler.Unload()

    def FindDirectory(self, filePath):
        filePathLower = filePath.lower()
        for dirPath, scriptDirectory in self.directoriesByPath.iteritems():
            if filePathLower.startswith(dirPath.lower()):
                return scriptDirectory

    def ProcessChangedFile(self, filePath, added=False, changed=False, deleted=False):
        scriptDirectory = self.FindDirectory(filePath)
        if scriptDirectory is None:
            logging.error("File change event for invalid path '%s'", filePath)
            return

        oldScriptFile = scriptDirectory.FindScript(filePath)
        if oldScriptFile:
            # Modified or deleted.
            if changed:
                self.ReloadScript(oldScriptFile)
            elif deleted:
                pass
        else:
            # Added.
            pass

    def ReloadScript(self, oldScriptFile):
        logging.info("ReloadScript")
        
        newScriptFile = self.CreateNewScript(oldScriptFile)
        if newScriptFile is None:
            return False

        self.UseNewScript(oldScriptFile, newScriptFile)

        return True

    def CreateNewScript(self, oldScriptFile):
        filePath = oldScriptFile.filePath
        namespacePath = oldScriptFile.namespacePath

        logging.info("CreateNewScript namespace='%s', file='%s'", namespacePath, filePath)

        # Read in and compile the modified script file.
        scriptDirectory = self.FindDirectory(filePath)
        newScriptFile = scriptDirectory.LoadScript(filePath, namespacePath)

        # Try and execute the new script file.
        if not newScriptFile.Run():
            # The execution failed, log context for the programmer to examine.
            newScriptFile.LogLastError()
            return None

        # Before we can go ahead and use the new version of the script file,
        # we need to verify that it is suitable for use.  That it ran without
        # error is a good start.  But we also need to verify that the
        # attributes provided by each are compatible.
        if not self.ScriptCompatibilityCheck(oldScriptFile, newScriptFile):
            return None

        newScriptFile.version = oldScriptFile.version + 1

        return newScriptFile

    def UseNewScript(self, oldScriptFile, newScriptFile):
        logging.info("UseNewScript")

        filePath = newScriptFile.filePath
        namespacePath = newScriptFile.namespacePath

        # The new version of the script being returned, means that it is
        # has been checked and approved for use.
        scriptDirectory = self.FindDirectory(filePath)
        scriptDirectory.UnregisterScript(oldScriptFile)
        scriptDirectory.RegisterScript(newScriptFile)

        # Leak the attributes the old version contributed.
        self.AddLeakedAttributes(oldScriptFile)

        # Insert the attributes from the new script file, allowing overwriting
        # of entries contributed by the old script file.
        namespace = scriptDirectory.GetNamespace(namespacePath)
        scriptDirectory.InsertModuleAttributes(newScriptFile, namespace, overwritableAttributes=self.leakedAttributes)

        # Remove as leaks the attributes the new version contributed.
        self.RemoveLeakedAttributes(newScriptFile)

    def IsAttributeLeaked(self, attributeName):
        return attributeName in self.leakedAttributes

    def GetLeakedAttributeVersion(self, attributeName):
        return self.leakedAttributes[attributeName][1]

    def AddLeakedAttributes(self, oldScriptFile):
        filePath = oldScriptFile.filePath
    
        for attributeName in oldScriptFile.contributedAttributes:
            self.leakedAttributes[attributeName] = (filePath, oldScriptFile.version)

    def RemoveLeakedAttributes(self, newScriptFile):
        for attributeName in newScriptFile.contributedAttributes:
            if attributeName in self.leakedAttributes:
                del self.leakedAttributes[attributeName]

    def ScriptCompatibilityCheck(self, oldScriptFile, newScriptFile):
        logging.info("ScriptCompatibilityCheck '%s'", oldScriptFile.filePath)

        # Do not allow replacement of old contributions, whether from the old
        # script file given, or contributions it has inherited itself, if the
        # new contributions are not compatible.
        pass
        # Overwrite:
        # - Different types.
        # Update:
        # - Change from old style class to new style class.
        return True


class ReloadableScriptFile(namespace.ScriptFile):
    version = 1


class ReloadableScriptDirectory(namespace.ScriptDirectory):
    scriptFileClass = ReloadableScriptFile
