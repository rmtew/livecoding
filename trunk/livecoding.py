"""
= livecoding.py =

This library is licensed under the BSD license, which is distributed with
it and can be found in the same directory as the file 'LICENSE'.

== Authors ==

 * Michael Brannan
 * Richard Tew <richard.m.tew@gmail.com>
 
== Overview ==

Directories containing Python scripts can be registered to be monitored
so that any time a change is made to a script the code within it will be
reloaded and put in place transparently.

Note that these directories should not be those of standard Python
modules available for normal import.  The reason for this is that this
library manually processes the contents of registered directories and
places them so that they can be imported.  By handling this itself,
this allows the library to know enough to apply changes to modules
as they happen.

Yes, this means that the directories registered must follow a custom
structure.  An arbitrary one determined by my fellow author and I
after several years of using another arbitrary one in our day to day work.

== Further information ==

  http://code.google.com/p/livecoding/wiki/Importing

== Potential problems ==

 * If someone were to add a directory under a standard library namespace
   then it might merge the contents of the directory into that existing
   namespace.  But is it really practical to prevent it given that it can
   work the other way round - where the standard library module might be
   inaccessible because the one provided through this library was imported
   first.

== Todo ==

 * Some code to detect changed files.

"""

import os
import marshal
import __builtin__
import traceback
import sys
import types
import imp
import new
import random

CCSTATE_FAILED      = 0
CCSTATE_INITIALIZED = 1
CCSTATE_BUILDING    = 2
CCSTATE_BUILT       = 3
#CCSTATE_READY       = 4
#CCSTATE_INTERACTIVE = 5

CCMODE_NORMAL       = 0
CCMODE_VERBOSE      = 1

class CompiledFile:
    def __init__(self, filePath = None, realFilePath = None, namespace=None):
        self.namespace = namespace
        self.filePath = filePath
        if realFilePath is None:
            self.realFilePath = filePath
        else:
            self.realFilePath = realFilePath
        self.codeObject = None
        self.timeStamp = None
        self.locals = {
            "__file__": filePath,
        }
        if file is not None:
            return self.Compile()

    def Compile(self):
        if self.realFilePath != self.filePath:
            sys.stdout.write("Compiling file: %s (actually %s)\n"%(self.filePath, self.realFilePath))
        else:
            sys.stdout.write("Compiling file: %s\n"%(self.filePath))

        f = open(self.realFilePath)
        try:
            self.timeStamp = os.fstat(f.fileno())
        except AttributeError:
            sys.exc_clear()
            self.timeStamp = os.stat(self.realFilePath)

        codestring = f.read()
        f.close()
        codestring = codestring.replace("\r\n", "\n")
        codestring = codestring.replace("\r", "\n")
        if codestring and codestring[-1] != "\n":
            codestring += "\n"

        try:
            self.codeObject = __builtin__.compile(codestring, self.filePath, "exec")
        except SyntaxError, e:
            if self.realFilePath != self.filePath:
                sys.stderr.write("Compilation failed: %s (actually %s)\n"%(self.filePath, self.realFilePath))
            else:
                sys.stderr.write("Compilation failed: %s\n"%(self.filePath))
            lines = traceback.format_exception_only(SyntaxError, e)
            for line in lines:
                sys.stderr.write(line.replace('File "<string>"', 'File %s'%(self.filePath)))
            sys.exc_clear()
            self.codeObject = None
            self.timeStamp = None

    def Actualize(self, path):
        stripIdx = path.rfind("\\")
        # Should we clear self.locals?  Need to think about this.
        eval(self.codeObject, self.locals)

    def GetExports(self):
        exports = {}
        for k, v in self.locals.iteritems():
            if k in ("__builtins__", "__file__"):
                continue

            if hasattr(v, "__module__"):
                # New classes and new functions respectively.  These will get
                # a module set when these exports are put in place.
                if v.__module__ is None or v.__module__ == "__builtin__":
                    exports[k] = v
            #else:
            #    print "-- UNKNOWN", type(v), k, v, v.__module__, v.__dict__.keys()
        return exports


class CodeCompiler:
    def __init__(self):
        CodeCompiler.state = CCSTATE_INITIALIZED
        CodeCompiler.mode = CCMODE_VERBOSE

        self.compiledFiles = {}
        self.bootStrapOrder = []

        self.directories = {}
        self.namespaces = {}
        self.overrides = {}

        self.invalidDirectories = [ ".svn" ]

        # Import hook state.
        self.__import__ = None
        self.lastImport = None

    # ------------------------------------------------------------------------
    def AddDirectory(self, path, ns, monitor=False):
        CodeCompiler.state = CCSTATE_BUILDING
        try:
            fileList = self.ProcessDirectory(path, ns)
            self.CompileFiles(path, fileList)
        except:
            CodeCompiler.state = CCSTATE_FAILED
            raise

    def ProcessDirectory(self, path, ns, files=None):
        if path in self.directories:
            raise RuntimeError("Path already added", path)

        self.directories[path] = None

        if files is None:
            files = {}

        for fileName in os.listdir(path):
            filePath = os.path.join(path, fileName)
            if os.path.isdir(filePath):
                if fileName not in self.invalidDirectories:
                    self.ProcessDirectory(filePath, "%s.%s" % (ns, fileName), files)
            elif os.path.isfile(filePath):
                if fileName.endswith(".py"):
                    if not files.has_key(ns):
                        files[ns] = []
                    files[ns].append(filePath)

        return files

    # ------------------------------------------------------------------------
    # It is unnecessary to override the built-in import function in order to
    # put our namespace in place.  However, we can use it to find out what
    # action exactly failed.  Something which ImportError is unable to tell
    # us to a useful extent.

    def AddImportHook(self):
        if self.__import__:
            raise RuntimeError("Import hook already installed", self.__import__, __builtin__.__import__)

        self.__import__ = __builtin__.__import__
        __builtin__.__import__ = self.ImportHook

    def RemoveImportHook(self):
        if not self.__import__:
            raise RuntimeError("Import hook not currently installed")

        __builtin__.__import__ = self.__import__
        self.__import__ = None
        self.lastImport = None

    # The keywords are named the same as the Python documentation gives for __import__.
    def ImportHook(self, name=None, globals=None, locals=None, fromlist=None, level=-1):
        try:
            # print "IMPORT", name, fromlist, globals["__file__"]
            ret = self.__import__(name, globals, locals, fromlist, level)
            # print "IMPORT.POST", name, globals.keys(), ret
            return ret
        except:
            if CodeCompiler.mode == CCMODE_VERBOSE:
                print "** Import failed", name, fromlist
            self.lastImport = (name, fromlist)
            raise

    # ------------------------------------------------------------------------
    def CompileFiles(self, path, files):
        errors = 0
        candidates = []
        for ns in files:
            fileList = files[ns][:]
            random.shuffle(fileList)
            for filePath in fileList:
                compiledFile = CompiledFile(filePath, namespace=ns)
                if compiledFile.timeStamp is not None and compiledFile.codeObject is not None:
                    self.compiledFiles[filePath] = compiledFile
                    candidates.append(filePath)
                else:
                    errors += 1

        if errors > 0:
            CodeCompiler.state = CCSTATE_FAILED
            sys.stderr.write("Compilation failed: %d errors\n"%(errors))
            return

        sys.stdout.write("Compilation completed: %d errors\n"%(errors))

        self.AddImportHook()
        try:
            if self.ActualizeCompiledFiles(path, candidates):
                CodeCompiler.state = CCSTATE_BUILT
            else:
                CodeCompiler.state = CCSTATE_FAILED
        finally:
            self.RemoveImportHook()

    def ActualizeCompiledFiles(self, path, candidates):
        stripIdx = path.rfind("\\")

        # This is kind of meaningless now, and needs to be per-added-directory.
        self.bootStrapOrder = []

        errors = 0
        while len(candidates):
            if errors > 100:
                return False

            for candidate in candidates:
                compiledFile = self.compiledFiles[candidate]
                try:
                    compiledFile.Actualize(path)
                except Exception, e:
                    errors += 1

                    sys.stderr.write("%s in %s\n"%(e.__class__.__name__, candidate))
                    lines = traceback.format_exception_only(e.__class__, e)
                    for line in lines:
                        sys.stderr.write(line.replace('File "<string>"', 'File %s'%(compiledFile.filePath)))

                    sys.exc_clear()
                    continue

                self.bootStrapOrder.append(candidate)
                if CodeCompiler.mode == CCMODE_VERBOSE:
                    print "Exporting:", compiledFile.filePath[stripIdx:]

                self.ProcessCompiledFile(compiledFile)
                candidates.remove(candidate)

        return True

    # ------------------------------------------------------------------------
    def ProcessCompiledFile(self, compiledFile):
        filePath = compiledFile.filePath
        namespace = compiledFile.namespace
        exports = compiledFile.GetExports()
        for name, objectRef in exports.iteritems():
            self.InsertNamespaceEntry(filePath, namespace, name, objectRef)

    def InsertNamespaceEntry(self, filePath, name_space, object_name, objectRef):
        lastModule = None
        currentNamespace = ""
        for namePart in name_space.split("."):
            if len(currentNamespace):
                currentNamespace += "."
            currentNamespace += namePart

            if lastModule is None:
                if namePart in sys.modules:
                    module = sys.modules[namePart]
                else:
                    module = sys.modules[namePart] = imp.new_module(namePart)
                    module.__name__ = namePart
                    if CodeCompiler.mode == CCMODE_VERBOSE:
                        print "Created module: %s (%s)" % (namePart, currentNamespace)
            else:
                if hasattr(lastModule, namePart):
                    module = getattr(lastModule, namePart)
                    if type(module) is not types.ModuleType:
                        raise RuntimeError("Submodule name already used for non-module", currentNamespace, namePart, module)
                else:
                    module = imp.new_module(namePart)
                    module.__name__ = currentNamespace
                    if CodeCompiler.mode == CCMODE_VERBOSE:
                        print "Created submodule: %s (%s)" % (namePart, currentNamespace)
                setattr(lastModule, namePart, module)
                sys.modules[currentNamespace] = module

            lastModule = module

        moduleFile = getattr(module, "__file__", "")
        # There is probably something better than this relative path to put
        # in this attribute.
        relFilePath = self.GetRelativePath(filePath)
        if relFilePath not in moduleFile:
            if len(moduleFile):
                moduleFile += "|"
            moduleFile += relFilePath

        module.__dict__.update({ object_name: objectRef, "__file__": moduleFile })
        all = module.__dict__.get("__all__", [])
        if object_name not in all:
            all.append(object_name)
        if hasattr(objectRef, "__module__"):
            objectRef.__module__ = name_space or module.__name__

    # ------------------------------------------------------------------------
    def OverrideClassFunction(self, moduleNamespace, className, attributeName, value):
        # Check everything involved to make sure that there is such a function.
        if moduleNamespace not in sys.modules:
            raise RuntimeError("Namespace does not exist")

        module = sys.modules[moduleNamespace]
        if not hasattr(module, className):
            raise RuntimeError("no entry for given class name in the module", className, moduleNamespace)

        klass = getattr(module, className)
        if type(klass) not in (types.ClassType, types.TypeType):
            raise RuntimeError("entry for given module is not a class", className, moduleNamespace, entry)

        # If this class was imported from somewhere else, then it needs to be
        # addressed in the namespace it belongs in.
        if klass.__module__ != module.__name__:
            raise RuntimeError("entry originated from another module", className, klass.__module__)

        # This will work if the given class, or one of its superclasses has the attribute.
        originalValue = getattr(klass, attributeName)

        if not self.overrides.has_key(moduleNamespace):
            self.overrides[moduleNamespace] = {}
        if not self.overrides[moduleNamespace].has_key(className):
            self.overrides[moduleNamespace][className] = {}
        if not self.overrides[moduleNamespace][className].has_key(attributeName):
            # We leave this unbound so we can see what class it actually came from.
            overrides = self.overrides[moduleNamespace][className][attributeName] = [ originalValue ]
        else:
            overrides = self.overrides[moduleNamespace][className][attributeName]
            # Check that the first entry is still valid, otherwise we have a consistency problem.
            oldKlass, oldOriginalValue = overrides[0]
            if oldKlass != klass:
                raise RuntimeError("inconsistency detected")
            self.RevertOverrides(moduleNamespace, className, attributeName)

        overrides.append(value)

        self.InjectOverrides(moduleNamespace, className, attributeName)

        # This will do for now.  Could reference it internally with some unique ID, but same effect.
        return (moduleNamespace, className, attributeName, value)

    def OverrideFunction(self, namespace, functionName, f):
        raise NotImplementedError("not considered worth supporting")

    def InjectOverrides(self, moduleNamespace, className, attributeName):
        # Ensure there are overrides to inject.
        if self.overrides.has_key(moduleNamespace) and self.overrides[moduleNamespace].has_key(className) and self.overrides[moduleNamespace][className].has_key(attributeName):
            # Ensure that the desired element to override exists.
            if moduleNamespace in sys.modules:
                module = sys.modules[moduleNamespace]
                if hasattr(module, className):
                    klass = getattr(module, className)
                    if hasattr(klass, attributeName):
                        overrides = self.overrides[moduleNamespace][className][attributeName]
                        # The first entry is the original value.  The subsequent entries are the overrides to install.
                        oldKlass, oldOriginalValue = overrides[0]
                        
                        # Chain the overrides from the first override down to the original value.

    def RevertOverrides(self, moduleNamespace, className, attributeName):
        pass

    def RemoveOverride(self, k):
        moduleNamespace, className, attributeName, value = k
        if self.overrides.has_key(moduleNamespace) and self.overrides[moduleNamespace].has_key(className) and self.overrides[moduleNamespace][className].has_key(attributeName):
            overrides = self.overrides[moduleNamespace][className][attributeName]
            overrides.remove(value)

            self.RevertOverrides(moduleNamespace, className, attributeName)
            if len(overrides) == 1:
                del self.overrides[moduleNamespace][className][attributeName]
                if not len(self.overrides[moduleNamespace][className]):
                    del self.overrides[moduleNamespace][className]
                if not len(self.overrides[moduleNamespace]):
                    del self.overrides[moduleNamespace]
            else:
                self.InjectOverrides(moduleNamespace, className, attributeName)

    # ------------------------------------------------------------------------
    def ProcessChangedFile(self, filePath, realFilePath=None):
        """
        This can be called manually if the automatic file change detection is
        not installed.  Your code base might be handling this already at a
        higher level, or something similar.
        """
    
        sys.stdout.write("Processing changed file: %s\n"%(filePath))

        oldCompiledFile = None
        oldLocals = {}
        oldExports = {}
        newCompiledFile = None
        newLocals = {}
        newExports = {}

        if self.compiledFiles.has_key(filePath):
            if CodeCompiler.mode == CCMODE_VERBOSE:
                print "Gathering old code for %s"%(filePath)
            oldCompiledFile = self.compiledFiles[filePath]
            oldLocals = oldCompiledFile.locals
            oldExports = oldCompiledFile.GetExports()

        newCompiledFile = CompiledFile(filePath, realFilePath)
        if newCompiledFile.timeStamp is None and newCompiledFile.codeObject is None:
            return
        try:
            newCompiledFile.Actualize()
        except ImportError, e:
            sys.stderr.write("ImportError in %s\n"%(filePath))
            lines = traceback.format_exception_only(ImportError, e)
            for line in lines:
                sys.stderr.write(line.replace('File "<string>"', 'File %s'%(newCompiledFile.filePath)))
            return

        # Short cut for pure additions
        if oldCompiledFile is None:
            self.compiledFiles[filePath] = newCompiledFile
            self.ProcessCompiledFile(newCompiledFile)
            return

        newLocals = newCompiledFile.locals
        newExports = newCompiledFile.GetExports()

        changeExports = {}
        for key, val in newExports.iteritems():
            changeExports[key] = [None, val]
        for key, val in oldExports.iteritems():
            if changeExports.has_key(key):
                changeExports[key][0] = val
            else:
                changeExports[key] = [val, None]

        changeLocals = {}
        for key, val in newLocals.iteritems():
            changeLocals[key] = [None, val]
        for key, val in oldLocals.iteritems():
            if changeLocals.has_key(key):
                changeLocals[key][0] = val
            else:
                changeLocals[key] = [val, None]

        # Update the locals
        for objectName, change in changeLocals.iteritems():
            oldObject, newObject = change
            if newObject is None:
                # Existing objects which reference this dictionary
                # may depend on the presence of this entry.
                ## del oldLocals[objectName]
                continue
            if type(newObject) not in (types.ClassType, types.TypeType):
                # Cack imported from somewhere else?
                if oldObject and type(oldObject) is type(newObject):
                    try:
                        if oldObject == newObject:
                            continue
                    except:
                        sys.exc_clear()

                if isinstance(newObject, (types.UnboundMethodType, types.FunctionType, types.MethodType)):
                    if isinstance(newObject, types.FunctionType):
                        print "==> Function", objectName # , id(newObject.func_globals), id(oldLocals)
                        newObject = RebindFunction(newObject, oldLocals)
                    elif hasattr(newObject, "im_func"):
                        print "==> (im_func)", objectName
                        newObject = RebindFunction(newObject.im_func, oldLocals)

                oldLocals[objectName] = newObject
                continue
            if oldObject:
                toDelAttr = []
                for k, oldV in oldObject.__dict__.iteritems():
                    if not newObject.__dict__.has_key(k):
                        toDelAttr.append(k)
                if CodeCompiler.mode == CCMODE_VERBOSE:
                    print "removing:",toDelAttr
                for k in toDelAttr:
                    del oldObject[k]
            # Go over the entries in the newly (re)loaded file locals.
            for k, v in newObject.__dict__.iteritems():
                if CodeCompiler.mode == CCMODE_VERBOSE:
                    print "(NEW)TYPE k:", k,"is:", type(v)
                    if oldObject and k in oldObject.__dict__:
                        print "(OLD)TYPE k:", k,"is:", type(oldObject.__dict__[k])
                if k in ["__dict__","__doc__","__module__","__weakref__"]:
                    continue

                targetObject = oldObject and oldObject or newObject
                if isinstance(v, (types.UnboundMethodType, types.FunctionType, types.MethodType)):
                    if isinstance(v, types.FunctionType):
                        print "--> Function", k
                        nv = RebindFunction(v, oldLocals)
                        setattr(targetObject, k, nv)
                    elif hasattr(v, "im_func"):
                        print "--> (im_func)", k
                        nv = RebindFunction(v.im_func, oldLocals)
                        setattr(targetObject, k, nv)
                    elif oldObject:
                        # Copy the method from the new object to the old.
                        print "--> ", k, dir(v)
                        #oldObject.__dict__[k] = new.instancemethod(v, None, type(oldObject))
                        setattr(oldObject, k, v)
                elif oldObject:
                    # Copy the value from the new object to the old.
                    setattr(oldObject, k, v)

        if CodeCompiler.mode == CCMODE_VERBOSE:
            print "change (newObject):"
            for k, v in newObject.__dict__.iteritems():
                if k == "__builtins__":
                    continue
                print k, ":", v
            print "change (oldObject):"
            for k, v in oldObject.__dict__.iteritems():
                if k == "__builtins__":
                    continue
                print k, ":", v

        if CodeCompiler.mode == CCMODE_VERBOSE:
            print "Change Exports:"

        for guid, change in changeExports.iteritems():
            if CodeCompiler.mode == CCMODE_VERBOSE:
                print "GUID:",guid, "change:",change
                print type(change[0]), type(change[1])
            oldObjectRef, newObjectRef = change

            if type(change[0]) is type(change[1]):
                # This fixes that bug where you derive a class from another
                # and then update the base class.
                # It might be an idea to check that __name__ is the same as well.
                if CodeCompiler.mode == CCMODE_VERBOSE:
                    print "Not updating %s as its type has not changed"
                continue

            name_space, object_name = guid.split(".")
            module = None
            if name_space in sys.modules:
                module = sys.modules[name_space]
            else:
                if newObjectRef is not None:
                    module = imp.new_module(name_space)
                    if CodeCompiler.mode == CCMODE_VERBOSE:
                        print "Created module:", name_space
            if module is None:
                continue
            if newObjectRef is not None:
                module.__dict__.update({object_name:newObjectRef})
            else:
                del module.__dict__[object_name]

            all = module.__dict__.get("__all__", None)
            if all is not None:
                if newObjectRef is not None:
                    if object_name not in all:
                        all.append(object_name)
                else:
                    if object_name in all:
                        all.remove(object_name)
                        if 0 == len(all):
                            del sys.modules[name_space]
                            return

            module.__name__ = name_space
            sys.modules[name_space] = module

    def GetRelativePath(self, filePath):
        for dirPath in self.directories.iterkeys():
            if filePath.startswith(dirPath):
                return filePath[len(dirPath)+1:]
        return filePath


def RebindFunction(newFunction, oldLocals):
    '''return *f* with some globals rebound.'''
    # Not sure what this does, it seems to do nothing but prevent
    # the globals from being fixed.
    #d = {}
    #if objectToBindTo and hasattr(objectToBindTo, "__dir__"):
    #    d.update(objectToBindTo.__dir__)
    #if not d:
    #    return newFunction
    if objectToBindTo and hasattr(objectToBindTo, "__dir__"):
        raise NotImplementedError("unexpected case")
    nf = types.FunctionType(newFunction.func_code, oldLocals, newFunction.func_name, newFunction.func_defaults or ())
    nf.__doc__= newFunction.__doc__
    if newFunction.__dict__ is not None:
        nf.__dict__= newFunction.__dict__.copy()
    return nf

def ResolvePath(originalPath):
    # If the path is an absolute one, then we are done.
    drive, path = os.path.splitdrive(originalPath)
    if len(drive):
        return originalPath

    # Determine whether the file name is an absolute path or not.
    drive, path = os.path.splitdrive(__file__)
    if len(drive):
        # Absolute path to the file.
        filePath = __file__
    else:
        # Relative path to the file, add to the current directory.
        filePath = os.path.join(os.getcwd(), __file__)

    # We now have the directory this file is in.
    path = os.path.join(os.path.dirname(filePath), originalPath)
    if not os.path.exists(path):
        raise RuntimeError("Bad path", path)
    return path

def Test():
    coreScriptPath = ResolvePath(r"server-core")
    gameScriptPath = ResolvePath(r"server-game")

    # Add the directories under these two, to the server namespace.
    cc = CodeCompiler()
    cc.AddDirectory(coreScriptPath, "server")
    cc.AddDirectory(gameScriptPath, "server")

    print
    print "TEST"
    print

    from server import services

    from server.services import Beta
    from server.services import Alpha1

    from server.services import BlahService
    print services

    print BlahService

if __name__ == "__main__":
    Test()


