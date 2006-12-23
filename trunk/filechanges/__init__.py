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


def IsModuleAvailable(moduleName):
    try:
        __import__(moduleName)
        return True
    except ImportError:
        return False


class ChangeHandler:
    watchState = None
    ready = False

    def __init__(self, callback, delay=1.0):
        self.callback = callback
        self.delay = delay

        self.thread = None
        self.directories = []

    def AddDirectory(self, path):
        self.directories.append(path)
        if self.thread is None:
            self.thread = ChangeThread(self, self.delay)

    def StartWatching(self):
        """ Call this after all the directories are added.  Otherwise if there is more
            than one directory added, this will give false alarms as it detects the
            contents of the freshly added directories mid-run. """
        self.ready = True

    def ProcessFileAddition(self, path):
        self.callback(path, added=True)

    def ProcessFileChange(self, path):
        self.callback(path, changed=True)

    def ProcessFileDeletion(self, path):
        self.callback(path, deleted=True)

class ChangeThread(threading.Thread):
    def __init__(self, handler, delay, **kwargs):
        threading.Thread.__init__ (self, **kwargs)
        self.setDaemon(1)

        self.handler = handler
        self.delay = delay
        self.start()
        
    def run(self):
        while not self.handler.ready:
            time.sleep(1.0)

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
