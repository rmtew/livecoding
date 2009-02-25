
class OldStyleBase:
    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs

    def Func(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs

class NewStyleBase(object):
    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs

    def Func(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs

class OldStyle(OldStyleBase):
    def __init__(self, *args, **kwargs):
        OldStyleBase.__init__(self, *args, **kwargs)

    def Func(self, *args, **kwargs):
        OldStyleBase.Func(self, *args, **kwargs)

class NewStyle(NewStyleBase):
    def __init__(self, *args, **kwargs):
        NewStyleBase.__init__(self, *args, **kwargs)

    def Func(self, *args, **kwargs):
        NewStyleBase.Func(self, *args, **kwargs)

    def FuncSuper(self, *args, **kwargs):
        super(NewStyleBase, self).Func(self, *args, **kwargs)
