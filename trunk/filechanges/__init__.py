#
# Do some generic stuff to wrap whatever method is chosen.
#
# To do list:
#
# - Detect if stackless is present and use that instead of a thread.  This
#   of course requires that the user is running the scheduler, but that is
#   their problem.
#

import os, time
import threading, Queue


class ChangeHandler:
    watchState = None

    def __init__(self, callback, delay=1.0):
        self.callback = callback
        self.delay = delay

        self.thread = None
        self.directories = []

        self.skipList = [
            os.path.join(os.path.sep, ".svn", os.path.sep),
        ]

    def AddDirectory(self, path):
        self.directories.append(path)
        if self.thread is None:
            self.thread = ChangeThread(self, self.delay)

    def ProcessFileAddition(self, path):
        self.callback(path, added=True)

    def ProcessFileChange(self, path):
        self.callback(path, changed=True)

    def ProcessFileDeletion(self, path):
        self.callback(path, deleted=True)

    def ShouldIgnorePathEntry(self, path):
        # By default this concentrates on files, not directories.
        if os.path.isdir(path):
            return True

        # Perhaps there are some standard things we should ignore.
        for skipPath in self.skipList:
            if skipPath in path:
                return True

        return False

class ChangeThread(threading.Thread):
    def __init__(self, handler, delay, **kwargs):
        threading.Thread.__init__ (self, **kwargs)
        self.setDaemon(1)

        self.handler = handler
        self.delay = delay
        self.start()
        
    def run(self):
        module = None
        # Not ready for use.  If it is going to handle multiple directories,
        # it needs to be non-blocking.
        #if os.name == "nt":
        #    if IsModuleAvailable("win32file"):
        #        import golden3
        #        module = golden3        
        if module is None:
            import recipe215418
            module = recipe215418
        module.Prepare(self.handler)

        while len(self.handler.directories):
            module.Check(self.handler)
            time.sleep(self.delay)

if __name__ == "__main__":
    path = r"C:\devkitPro\dl\livecoding\livecoding-google\trunk\filechanges"
    def f(path, added=False, changed=False, deleted=False):
        print "f", path, (added, changed, deleted) 
    ch = ChangeHandler(f)
    ch.AddDirectory(path)

    while 1:
        time.sleep(10)
