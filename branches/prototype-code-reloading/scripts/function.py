# ...

def TestFunction(self, argument):
    return (argument,)

def TestFunction_PositionalArguments(self, arg1, *args):
    return (arg1, args)

def TestFunction_KeywordArguments(self, arg1="arg1", **kwargs):
    return (arg1, kwargs)
