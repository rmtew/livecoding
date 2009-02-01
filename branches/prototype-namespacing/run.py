import unittest
import sys
import logging

import namespace

logging.basicConfig(level=logging.INFO)

class CustomNamespaceTests(unittest.TestCase):
    def setUp(self):
        pass

    def tearDown(self):
        pass

    def testXXX(self):
        sd = namespace.ScriptDirectory()


if __name__ == "__main__":
    unittest.main()
