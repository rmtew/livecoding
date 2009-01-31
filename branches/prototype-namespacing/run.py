import unittest
import sys
import logging

logging.basicConfig(level=logging.INFO)

class XTest(unittest.TestCase):
    def setUp(self):
        pass

    def tearDown(self):
        pass

    def testXXX(self):
        pass

if __name__ == "__main__":
    path = sys.path[0]
    print path
    import namespace
    namespace.DirectoryManager(path)
    # unittest.main()
