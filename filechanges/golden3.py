"""
This script is publically available from the web page given below.  It is not
part of the live coding package but is included for the sake of completeness.

Author: Tim Golden
Source: http://tgolden.sc.sabren.com/python/win32_how_do_i/watch_directory_for_changes.html

The third technique uses the MS ReadDirectoryChanges API, exposed via the
pywin32 win32file module. The way we employ it here is to use call
ReadDirectoryChangesW in blocking mode. Similarly to the FindFirstChange
approach (but slightly differently � thank you, Microsoft!) we specify what
changes are to be notified and whether or not to watch subtrees. Then you
just wait... The function returns a list of 2-tuples, each one representing
an action and a filename. A rename always gives a pair of 2-tuples; other
compound actions may also give a list.

Obviously, you could get fancy with a micro state machine to give better
output on renames and other multiple actions.


"""

import os

import win32file
import win32con

ACTIONS = {
  1 : "Created",
  2 : "Deleted",
  3 : "Updated",
  4 : "Renamed from something",
  5 : "Renamed to something"
}
# Thanks to Claudio Grondi for the correct set of numbers
FILE_LIST_DIRECTORY = 0x0001

path_to_watch = "."
hDir = win32file.CreateFile (
  path_to_watch,
  FILE_LIST_DIRECTORY,
  win32con.FILE_SHARE_READ | win32con.FILE_SHARE_WRITE,
  None,
  win32con.OPEN_EXISTING,
  win32con.FILE_FLAG_BACKUP_SEMANTICS,
  None
)
while 1:
  #
  # ReadDirectoryChangesW takes a previously-created
  #  handle to a directory, a buffer size for results,
  #  a flag to indicate whether to watch subtrees and
  #  a filter of what changes to notify.
  #
  # NB Tim Juchcinski reports that he needed to up
  #  the buffer size to be sure of picking up all
  #  events when a large number of files were
  #  deleted at once.
  #
  results = win32file.ReadDirectoryChangesW (
    hDir,
    1024,
    True,
    win32con.FILE_NOTIFY_CHANGE_FILE_NAME | 
     win32con.FILE_NOTIFY_CHANGE_DIR_NAME |
     win32con.FILE_NOTIFY_CHANGE_ATTRIBUTES |
     win32con.FILE_NOTIFY_CHANGE_SIZE |
     win32con.FILE_NOTIFY_CHANGE_LAST_WRITE |
     win32con.FILE_NOTIFY_CHANGE_SECURITY,
    None,
    None
  )
  for action, file in results:
    full_filename = os.path.join (path_to_watch, file)
    print full_filename, ACTIONS.get (action, "Unknown")