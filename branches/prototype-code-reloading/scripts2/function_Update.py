# ...

def TestFunction(self, newargument):
    return (newargument,)

def TestFunction_PositionalArguments(self, newarg1, *newargs):
    return (newarg1, newargs)

def TestFunction_KeywordArguments(self, newarg1="arg1", **newkwargs):
    return (newarg1, newkwargs)
