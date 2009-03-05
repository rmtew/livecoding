import unittest
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

# logging.basicConfig(level=logging.INFO)

import namespace
import reloader

class CodeReloadingTests(unittest.TestCase):
    mockedNamespaces = None
    codeReloader = None

    def setUp(self):
        pass

    def tearDown(self):
        # Restore all the mocked namespace entries.
        if self.mockedNamespaces is not None:
            for namespacePath, replacedValue in self.mockedNamespaces.iteritems():
                moduleNamespace, attributeName = namespacePath.rsplit(".", 1)
                module = __import__(moduleNamespace)
                setattr(module, attributeName, replacedValue)

        if self.codeReloader is not None:
            for dirPath in self.codeReloader.directoriesByPath.keys():
                self.codeReloader.RemoveDirectory(dirPath)

    def InsertMockNamespaceEntry(self, namespacePath, replacementValue):
        if self.mockedNamespaces is None:
            self.mockedNamespaces = {}

        # Avoid the case where we leak and reuse our mock class by keeping
        # the first value we stored around as the original.
        if namespacePath not in self.mockedNamespaces:
            moduleNamespace, attributeName = namespacePath.rsplit(".", 1)
            module = __import__(moduleNamespace)
            self.mockedNamespaces[namespacePath] = getattr(module, attributeName)

        namespace.ScriptDirectory = replacementValue

    def ReloadScriptFile(self, dirHandler, scriptDirPath, scriptFileName):
        # Get a reference to the original script file object.
        scriptPath = os.path.join(scriptDirPath, scriptFileName)
        oldScriptFile = dirHandler.FindScript(scriptPath)
        self.failUnless(isinstance(oldScriptFile, namespace.ScriptFile), "Unable to locate the example script")

        # Now we need to create a fresh object for the same script file.
        newScriptFile = dirHandler.LoadScript(scriptPath, oldScriptFile.namespacePath)

        # Run the new script object and inject its contents into the namespace,
        # overwriting the original injection from the original object.
        dirHandler.UnloadScript(oldScriptFile)
        success = dirHandler.RunScript(newScriptFile)
        self.failUnless(success, "Failed to run the new script file object")
        
        return newScriptFile

    def UpdateBaseClass(self, oldBaseClass, newBaseClass):
        import gc, types
        for ob1 in gc.get_referrers(oldBaseClass):
            # Class '__bases__' references are stored in a tuple.
            if type(ob1) is tuple:
                for ob2 in gc.get_referrers(ob1):
                    if type(ob2) in (types.ClassType, types.TypeType):
                        if ob2.__bases__ is ob1:
                            __bases__ = list(ob2.__bases__)
                            idx = __bases__.index(oldBaseClass)
                            __bases__[idx] = newBaseClass
                            ob2.__bases__ = tuple(__bases__)

    def UpdateGlobalReferences(self, oldBaseClass, newBaseClass):
        """
        References to the old version of the class might be held in global dictionaries.
        - Do not replace the reference to the old class, if it is held in the
          its own file.
        - Do not worry about replacing references held in local dictionaries, as this
          is not possible.

        So, just replace all references held in dictionaries.  We're avoiding replacing
        the case which shouldn't be replaced, so this should be safe.
        """
        import gc, types
        for ob1 in gc.get_referrers(oldBaseClass):
            # Class '__bases__' references are stored in a tuple.
            if type(ob1) is dict:
                for ob2 in gc.get_referrers(ob1):
                    if type(ob2) is dict:
                        for ob3 in gc.get_referrers(ob2):
                            if type(ob3) is types.InstanceType:
                                # Ignore originating globals dictionary.
                                if oldBaseClass.__file__ == ob3.filePath:
                                    continue

                                keyList = []
                                for k, v in ob1.iteritems():
                                    if v is oldBaseClass:
                                        keyList.append(k)
                                for k in keyList:
                                    ob1[k] = newBaseClass

    def testOverwriteDifferentFileBaseClassReload(self):
        """
        Reloading approach: Overwrite old objects on reload.
        Reloading scope: Different file.

        This test is intended to demonstrate the problems involved in reloading
        base classes with regard to existing subclasses.

        Problems:
        1) Class references used by subclasses, stored outside of the namespace.

           i.e. import module
                BaseClass = module.BaseClass

                class SubClass(BaseClass):
                    def __init__(self):
                        BaseClass.__init__(self)

           When 'module.BaseClass' is updated to a new version, 'BaseClass'
           will still refer to the old version.
           
           'SubClass' will also have the next problem.

        2) The class reference held by a subclass.

           i.e. SubClass.__bases__

           When 'module.BaseClass' is updated to a new version, 'SubClass.__bases__'
           will still hold a reference to the old version.

        """
        scriptDirPath = GetScriptDirectory()
        cr = self.codeReloader = reloader.CodeReloader()
        dirHandler = cr.AddDirectory("game", scriptDirPath)

        import game

        oldStyleClass = game.OldStyleBase
        newStyleClass = game.NewStyleBase

        ## Obtain references and instances for the two classes defined in the script.
        oldStyleNamespaceClass = game.OldStyleSubclassViaNamespace
        oldStyleNamespaceClassInstance1 = oldStyleNamespaceClass()
        oldStyleGlobalReferenceClass = game.OldStyleSubclassViaGlobalReference
        oldStyleGlobalReferenceClassInstance1 = oldStyleGlobalReferenceClass()
        newStyleNamespaceClass = game.NewStyleSubclassViaNamespace
        newStyleNamespaceClassInstance1 = newStyleNamespaceClass()
        newStyleGlobalReferenceClass = game.NewStyleSubclassViaGlobalReference
        newStyleGlobalReferenceClassInstance1 = newStyleGlobalReferenceClass()
        newStyleClassReferenceClass = game.NewStyleSubclassViaClassReference
        newStyleClassReferenceClassInstance1 = newStyleClassReferenceClass()

        ## Verify that all the functions are callable before the reload.
        oldStyleNamespaceClassInstance1.Func()
        oldStyleGlobalReferenceClassInstance1.Func()
        newStyleNamespaceClassInstance1.Func()
        newStyleNamespaceClassInstance1.FuncSuper()
        newStyleGlobalReferenceClassInstance1.Func()
        newStyleGlobalReferenceClassInstance1.FuncSuper()
        newStyleClassReferenceClassInstance1.Func()

        self.ReloadScriptFile(dirHandler, scriptDirPath, "example.py")

        ## Call functions on the instances created pre-reload.
        self.failUnlessRaises(TypeError, oldStyleNamespaceClassInstance1.Func)  # A
        oldStyleGlobalReferenceClassInstance1.Func()
        self.failUnlessRaises(TypeError, newStyleNamespaceClassInstance1.Func)  # B
        newStyleNamespaceClassInstance1.FuncSuper()
        newStyleGlobalReferenceClassInstance1.Func()
        newStyleGlobalReferenceClassInstance1.FuncSuper()
        newStyleClassReferenceClassInstance1.Func()

        # A) Accessed the base class via namespace, got incompatible post-reload version.
        # B) Same as A.

        ## Create new post-reload instances of the subclasses.
        self.failUnlessRaises(TypeError, game.OldStyleSubclassViaNamespace)
        oldStyleGlobalReferenceClassInstance2 = game.OldStyleSubclassViaGlobalReference()
        self.failUnlessRaises(TypeError, game.NewStyleSubclassViaNamespace)
        newStyleGlobalReferenceClassInstance2 = game.NewStyleSubclassViaGlobalReference()
        newStyleClassReferenceClassInstance2 = game.NewStyleSubclassViaClassReference()

        # *) Fail for same reason as the calls to the pre-reload instances.

        ## Call functions on the instances created post-reload.
        # oldStyleNamespaceClassInstance2.Func()
        oldStyleGlobalReferenceClassInstance2.Func()
        # newStyleNamespaceClassInstance2.Func()
        # newStyleNamespaceClassInstance2.FuncSuper()
        newStyleGlobalReferenceClassInstance2.Func()
        newStyleGlobalReferenceClassInstance2.FuncSuper()
        newStyleClassReferenceClassInstance2.Func()

        ## Pre-reload instances get their base class replaced with the new version.
        self.UpdateBaseClass(oldStyleClass, game.OldStyleBase)
        self.UpdateBaseClass(newStyleClass, game.NewStyleBase)

        ## Call functions on the instances created pre-reload.
        oldStyleNamespaceClassInstance1.Func()                                          # A
        self.failUnlessRaises(TypeError, oldStyleGlobalReferenceClassInstance1.Func)    # B
        newStyleNamespaceClassInstance1.Func()                                          # C
        newStyleNamespaceClassInstance1.FuncSuper()
        self.failUnlessRaises(TypeError, newStyleGlobalReferenceClassInstance1.Func)    # D
        newStyleGlobalReferenceClassInstance1.FuncSuper()
        newStyleClassReferenceClassInstance1.Func()

        # A) Fixed, due to base class update.
        # B) The base class is now post-reload, the global reference still pre-reload.
        # C) Fixed, due to base class update.
        # D) The base class is now post-reload, the global reference still pre-reload.

        ## Call functions on the instances created post-reload.
        # oldStyleNamespaceClassInstance2.Func()
        self.failUnless(TypeError, oldStyleGlobalReferenceClassInstance2.Func)
        # newStyleNamespaceClassInstance2.Func()
        # newStyleNamespaceClassInstance2.FuncSuper()
        self.failUnlessRaises(TypeError, newStyleGlobalReferenceClassInstance2.Func)
        newStyleGlobalReferenceClassInstance2.FuncSuper()
        newStyleClassReferenceClassInstance2.Func()

        ## Create new post-reload post-update instances of the subclasses.
        oldStyleNamespaceClassInstance3 = game.OldStyleSubclassViaNamespace()
        self.failUnlessRaises(TypeError, game.OldStyleSubclassViaGlobalReference)
        newStyleNamespaceClassInstance3 = game.NewStyleSubclassViaNamespace()
        self.failUnlessRaises(TypeError, game.NewStyleSubclassViaGlobalReference)
        newStyleClassReferenceClassInstance3 = game.NewStyleSubclassViaClassReference()

        ## Call functions on the instances created post-reload post-update.
        oldStyleNamespaceClassInstance3.Func()
        #oldStyleGlobalReferenceClassInstance3.Func()
        newStyleNamespaceClassInstance3.Func()
        newStyleNamespaceClassInstance3.FuncSuper()
        #newStyleGlobalReferenceClassInstance3.Func()
        #newStyleGlobalReferenceClassInstance3.FuncSuper()
        newStyleClassReferenceClassInstance3.Func()

        self.UpdateGlobalReferences(oldStyleClass, game.OldStyleBase)
        self.UpdateGlobalReferences(newStyleClass, game.NewStyleBase)

        ### All calls on instances created at any point, should now work.
        ## Call functions on the instances created pre-reload.
        oldStyleNamespaceClassInstance1.Func()
        oldStyleGlobalReferenceClassInstance1.Func()
        newStyleNamespaceClassInstance1.Func()
        newStyleNamespaceClassInstance1.FuncSuper()
        newStyleGlobalReferenceClassInstance1.Func()
        newStyleGlobalReferenceClassInstance1.FuncSuper()
        newStyleClassReferenceClassInstance1.Func()

        ## Call functions on the instances created post-reload.
        # oldStyleNamespaceClassInstance2.Func()
        oldStyleGlobalReferenceClassInstance2.Func()
        # newStyleNamespaceClassInstance2.Func()
        # newStyleNamespaceClassInstance2.FuncSuper()
        newStyleGlobalReferenceClassInstance2.Func()
        newStyleGlobalReferenceClassInstance2.FuncSuper()
        newStyleClassReferenceClassInstance2.Func()

        ## Call functions on the instances created post-reload post-update.
        oldStyleNamespaceClassInstance3.Func()
        #oldStyleGlobalReferenceClassInstance3.Func()
        newStyleNamespaceClassInstance3.Func()
        newStyleNamespaceClassInstance3.FuncSuper()
        #newStyleGlobalReferenceClassInstance3.Func()
        #newStyleGlobalReferenceClassInstance3.FuncSuper()
        newStyleClassReferenceClassInstance3.Func()

        ### New instances from the classes should be creatable.
        ## Instantiate the classes.
        oldStyleNamespaceClassInstance4 = game.OldStyleSubclassViaNamespace()
        oldStyleGlobalReferenceClassInstance4 = game.OldStyleSubclassViaGlobalReference()
        newStyleNamespaceClassInstance4 = game.NewStyleSubclassViaNamespace()
        newStyleGlobalReferenceClassInstance4 = game.NewStyleSubclassViaGlobalReference()
        newStyleClassReferenceClassInstance4 = game.NewStyleSubclassViaClassReference()

        ## Call functions on the instances.
        oldStyleNamespaceClassInstance4.Func()
        oldStyleGlobalReferenceClassInstance4.Func()
        newStyleNamespaceClassInstance4.Func()
        newStyleNamespaceClassInstance4.FuncSuper()
        newStyleGlobalReferenceClassInstance4.Func()
        newStyleGlobalReferenceClassInstance4.FuncSuper()
        newStyleClassReferenceClassInstance4.Func()

    def testOverwriteSameFileClassReload(self):
        """
        Reloading approach: Overwrite old objects on reload.
        Reloading scope: Same file.
        
        1. Get references to the exported classes.
        2. Instantiate an instance from each class.
        3. Call the functions exposed by each instance.

        4. Reload the script the classes were exported from.

        5. Verify that the old classes were replaced with new ones.
        6. Call the functions exposed by each old class instance.
        7. Instantiate an instance of each new class.
        8. Call the functions exposed by each new class instance.

        This verifies that instances linked to old superceded
        versions of a class, still work.
        """
        scriptDirPath = GetScriptDirectory()
        cr = self.codeReloader = reloader.CodeReloader()
        dirHandler = cr.AddDirectory("game", scriptDirPath)
        
        import game

        # Obtain references and instances for the classes defined in the script.
        oldStyleBaseClass = game.OldStyleBase
        oldStyleBaseClassInstance = oldStyleBaseClass()
        oldStyleClass = game.OldStyle
        oldStyleClassInstance = oldStyleClass()

        newStyleBaseClass = game.NewStyleBase
        newStyleBaseClassInstance = newStyleBaseClass()
        newStyleClass = game.NewStyle
        newStyleClassInstance = newStyleClass()

        # Verify that the exposed method can be called on each.
        oldStyleBaseClassInstance.Func()
        oldStyleClassInstance.Func()
        newStyleBaseClassInstance.Func()
        newStyleClassInstance.Func()
        newStyleClassInstance.FuncSuper()

        self.ReloadScriptFile(dirHandler, scriptDirPath, "example.py")

        # Verify that the original classes were replaced with new versions.
        self.failUnless(oldStyleBaseClass is not game.OldStyleBase, "Failed to replace the original 'game.OldStyleBase' class")
        self.failUnless(oldStyleClass is not game.OldStyle, "Failed to replace the original 'game.OldStyle' class")
        self.failUnless(newStyleBaseClass is not game.NewStyleBase, "Failed to replace the original 'game.NewStyleBase' class")
        self.failUnless(newStyleClass is not game.NewStyle, "Failed to replace the original 'game.NewStyle' class")

        # Verify that the exposed method can be called on the pre-existing instances.
        oldStyleBaseClassInstance.Func()
        oldStyleClassInstance.Func()
        newStyleBaseClassInstance.Func()
        newStyleClassInstance.Func()
        newStyleClassInstance.FuncSuper()

        # Make some new instances from the old class references.
        oldStyleBaseClassInstance = oldStyleBaseClass()
        oldStyleClassInstance = oldStyleClass()
        newStyleBaseClassInstance = newStyleBaseClass()
        newStyleClassInstance = newStyleClass()
        
        # Verify that the exposed method can be called on the new instances.
        oldStyleBaseClassInstance.Func()
        oldStyleClassInstance.Func()
        newStyleBaseClassInstance.Func()
        newStyleClassInstance.Func()
        newStyleClassInstance.FuncSuper()
        
        # Make some new instances from the new class references.
        oldStyleBaseClassInstance = game.OldStyleBase()
        oldStyleClassInstance = game.OldStyle()
        newStyleBaseClassInstance = game.NewStyleBase()
        newStyleClassInstance = game.NewStyle()
        
        # Verify that the exposed method can be called on the new instances.
        oldStyleBaseClassInstance.Func()
        oldStyleClassInstance.Func()
        newStyleBaseClassInstance.Func()
        newStyleClassInstance.Func()
        newStyleClassInstance.FuncSuper()

    def testDirectoryRegistration(self):
        """
        Verify that this function returns a registered handler for a parent
        directory, if there are any above the given file path.
        """
        self.InsertMockNamespaceEntry("namespace.ScriptDirectory", DummyClass)

        currentDirPath = GetCurrentDirectory()
        # Add several directories to ensure correct results are returned.
        scriptDirPath1 = os.path.join(currentDirPath, "scripts1")
        scriptDirPath2 = os.path.join(currentDirPath, "scripts2")
        scriptDirPath3 = os.path.join(currentDirPath, "scripts3")
        scriptDirPaths = [ scriptDirPath1, scriptDirPath2, scriptDirPath3 ]
        handlersByPath = {}

        baseNamespaceName = "testns"
        
        cr = reloader.CodeReloader()        

        # Test that a bad path will not find a handler when there are no handlers.
        self.failUnless(cr.FindDirectory("unregistered path") is None, "Got a script directory handler for an unregistered path")

        for scriptDirPath in scriptDirPaths:
            handlersByPath[scriptDirPath] = cr.AddDirectory(baseNamespaceName, scriptDirPath)
        
        # Test that a given valid registered script path gives the known handler for that path.
        while len(scriptDirPaths):
            scriptDirPath = scriptDirPaths.pop()
            fictionalScriptPath = os.path.join(scriptDirPath, "nonExistentScript.py")
            dirHandler = cr.FindDirectory(fictionalScriptPath)
            self.failUnless(dirHandler, "Got no script directory handler instance")
            self.failUnless(dirHandler is handlersByPath[scriptDirPath], "Got a different script directory handler instance")

        # Test that a bad path will not find a handler when there are valid ones for other paths.
        self.failUnless(cr.FindDirectory("unregistered path") is None, "Got a script directory handler for an unregistered path")

    def testLocalVariableDirectModificationLimitation(self):
        """
        Demonstrate that local variables cannot be indirectly modified via locals().
        """
        def ModifyLocal():
            localValue = 1
            locals()["localValue"] = 2
            return localValue

        value = ModifyLocal()
        self.failUnless(value == 1, "Local variable unexpectedly indirectly modified")

        # Conclusion: Local variables are an unavoidable problem when code reloading.

    def testLocalVariableFrameModificationLimitation(self):
        """
        Demonstrate that local variables cannot be indirectly modified via frame references.
        """
        expectedValue = 1

        def ModifyLocal():
            localValue = expectedValue
            yield localValue
            yield localValue

        g = ModifyLocal()

        # Verify that the first generated value is the expected value.
        v = g.next()
        self.failUnless(v == expectedValue, "Initial local variable value %s, expected %d" % (v, expectedValue))

        f_locals = g.gi_frame.f_locals

        # Verify that the frame local value is the expected value.
        v = f_locals["localValue"]
        self.failUnless(v == expectedValue, "Indirectly referenced local variable value %s, expected %d" % (v, expectedValue))
        f_locals["localValue"] = 2

        # Verify that the frame local value pretended to change.
        v = f_locals["localValue"]
        self.failUnless(v == 2, "Indirectly referenced local variable value %s, expected %d" % (v, 2))

        # Verify that the second generated value is unchanged and still the expected value.
        v = g.next()
        self.failUnless(v == expectedValue, "Initial local variable value %s, expected %d" % (v, expectedValue))
        
        # Conclusion: Local variables are an unavoidable problem when code reloading.


class DummyClass:
    def __init__(self, *args, **kwargs):
        pass

    def __call__(self, *args, **kwargs):
        pass

    def __getattr__(self, attrName, defaultValue=None):
        if attrName.startswith("__"):
            return getattr(DummyClass, attrName)

        instance = self.__class__()
        instance.attrName = attrName
        instance.defaultValue = defaultValue
        return instance

def GetCurrentDirectory():
    # There's probably a better way of doing this.
    dirPath = os.path.dirname(__file__)
    if not len(dirPath):
        dirPath = sys.path[0]
    return dirPath

def GetScriptDirectory():
    currentDirPath = GetCurrentDirectory()
    return os.path.join(currentDirPath, "scripts")

if __name__ == "__main__":
    # If this is being run on earlier versions of Python than 2.6, monkeypatch 
    # in something resembling missing standard library functionality.
    if sys.version_info[0] == 2 and sys.version_info[1] < 6:
        def relpath(longPath, basePath):
            if not longPath.startswith(basePath):
                raise RuntimeError("Unexpected arguments")
            if longPath == basePath:
                return "."
            i = len(basePath)
            if not basePath.endswith(os.path.sep):
                i += len(os.path.sep)
            return longPath[i:]

        os.path.relpath = relpath

    unittest.main()
