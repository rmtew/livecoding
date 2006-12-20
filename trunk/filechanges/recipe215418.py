"""
This script is publically available from the web page given below.  It is not
part of the live coding package but is included for the sake of completeness.

Author: A.M. Kuchling
Source: http://aspn.activestate.com/ASPN/Cookbook/Python/Recipe/215418

The watch_directories() function takes a list of paths and a callable object, 
and then repeatedly traverses the directory trees rooted at those paths,
watching for files that get deleted or have their modification time changed.
The callable object is then passed two lists containing the files that have
changed and the files that have been removed.

This recipe is useful where you'd like some way to send jobs to a daemon, but
don't want to use some IPC mechanism such as sockets or pipes. Instead, the
daemon can sit and watch a submission directory, and jobs can be submitted
by dropping a file or directory into the submission directory.

Locking is not taken into account. The watch_directories() function itself
doesn't really need to do locking; if it misses a modification on one pass,
it'll notice it on the next pass. However, if jobs are written directly
into a watched directory, the callable object might start running while a
job file is only half-written. To solve this, you can use a lockfile; the
callable must acquire the lock when it runs, and submitters must acquire the
lock when they wish to add a new job. A simpler approach is to rely on the
rename() system call being atomic: write the job into a temporary directory
that isn't being watched, and once the file is complete use os.rename() to
move it into the submission directory.
"""

import os, time

def watch_directories (paths, func, delay=1.0):
    """(paths:[str], func:callable, delay:float)
    Continuously monitors the paths and their subdirectories
    for changes.  If any files or directories are modified,
    the callable 'func' is called with a list of the modified paths of both
    files and directories.  'func' can return a Boolean value
    for rescanning; if it returns True, the directory tree will be
    rescanned without calling func() for any found changes.
    (This is so func() can write changes into the tree and prevent itself
    from being immediately called again.)
    """

    # Basic principle: all_files is a dictionary mapping paths to
    # modification times.  We repeatedly crawl through the directory
    # tree rooted at 'path', doing a stat() on each file and comparing
    # the modification time.  

    all_files = {}
    def f (unused, dirname, files):
        # Traversal function for directories
        for filename in files:
            path = os.path.join(dirname, filename)

            try:
                t = os.stat(path)
            except os.error:
                # If a file has been deleted between os.path.walk()
                # scanning the directory and now, we'll get an
                # os.error here.  Just ignore it -- we'll report
                # the deletion on the next pass through the main loop.
                continue

            mtime = remaining_files.get(path)
            if mtime is not None:
                # Record this file as having been seen
                del remaining_files[path]
                # File's mtime has been changed since we last looked at it.
                if t.st_mtime > mtime:
                    changed_list.append(path)
            else:
                # No recorded modification time, so it must be
                # a brand new file.
                changed_list.append(path)

            # Record current mtime of file.
            all_files[path] = t.st_mtime

    # Main loop
    rescan = False
    while True:
        changed_list = []
        remaining_files = all_files.copy()
        all_files = {}
        for path in paths:
            os.path.walk(path, f, None)
        removed_list = remaining_files.keys()
        if rescan:
            rescan = False
        elif changed_list or removed_list:
            rescan = func(changed_list, removed_list)

        time.sleep(delay)
