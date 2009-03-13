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
    def __init__(self, mode=MODE_OVERWRITE, leakRemovedAttributes=True):
        self.mode = mode
        self.leakRemovedAttributes = leakRemovedAttributes
        self.directoriesByPath = {}

    def AddDirectory(self, baseNamespace, baseDirPath):
        handler = self.directoriesByPath[baseDirPath] = ReloadableScriptDirectory(baseDirPath, baseNamespace)
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

        oldScriptFile = dirHandler.FindScript(filePath)
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
        filePath = oldScriptFile.filePath
        namespacePath = oldScriptFile.namespacePath

        logging.info("ReloadScript namespace='%s', file='%s'", namespacePath, filePath)

        # Read in and compile the modified script file.
        dirHandler = self.FindDirectory(filePath)
        newScriptFile = dirHandler.LoadScript(filePath, namespacePath)
        newScriptFile.ProcessPreviousVersion(oldScriptFile)

        # Try and execute the new script file.
        if not newScriptFile.Run():
            # The execution failed, log context for the programmer to examine.
            newScriptFile.LogLastError()
            return False

        # Before we can go ahead and use the new version of the script file,
        # we need to verify that it is suitable for use.  That it ran without
        # error is a good start.  But we also need to verify that the
        # attributes provided by each are compatible.
        if not self.ScriptCompatibilityCheck(oldScriptFile, newScriptFile):
            return False

        if self.leakRemovedAttributes:
            # Note what attributes the old script file contributes.
            overwritableAttributes = oldScriptFile.contributedAttributes.copy()
            namespace = dirHandler.GetNamespace(namespacePath)
        else:
            dirHandler.UnloadScript(oldScriptFile)

            overwritableAttributes = set()
            namespace = dirHandler.CreateNamespace(newScriptFile.namespacePath, filePath)

        # Insert the attributes from the new script file, allowing overwriting
        # of entries contributed by the old script file.
        dirHandler.InsertModuleAttributes(newScriptFile, namespace, overwritableAttributes)

        # Keep track of the contributions of the old script file, which were
        # not overwritten.  These are now leaked in the name of reliability.
        for attributeName in overwritableAttributes:
            logging.warn("ReloadScript leaked attribute '%s'", attributeName)
            newScriptFile.AddLeakedAttribute(oldScriptFile.version, attributeName)

        dirHandler.UnregisterScript(oldScriptFile)
        dirHandler.RegisterScript(newScriptFile)
        
        return True

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

    def __init__(self, filePath, namespacePath):
        super(ReloadableScriptFile, self).__init__(filePath, namespacePath)

        self.leakedAttributes = {}

    def ProcessPreviousVersion(self, oldScriptFile):
        # Keep track of how many revisions were made.
        self.version = oldScriptFile.version + 1

        # Inherit the registry of leaked attributes.
        self.leakedAttributes = oldScriptFile.leakedAttributes

    def SetContributedAttributes(self, contributedAttributes):
        super(ReloadableScriptFile, self).SetContributedAttributes(contributedAttributes)

        # Anything we contribute which overwrites an attribute leaked by a
        # previous version of this file, means that attribute is no longer
        # leaked.
        for attributeName in contributedAttributes:
            if attributeName in self.leakedAttributes:
                del self.leakedAttributes[attributeName]

    def SetLeakedAttributes(self, leakedAttributes):
        self.leakedAttributes = leakedAttributes

    def AddLeakedAttribute(self, fileVersion, attributeName):
        # We do not need to store the value, as it is in the namespace still..
        self.leakedAttributes[attributeName] = fileVersion


class ReloadableScriptDirectory(namespace.ScriptDirectory):
    scriptFileClass = ReloadableScriptFile
