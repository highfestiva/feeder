def prt(*args):
    def _cleandict(a):
        if isinstance(a, dict):
            a = dict(a)
            for name in 'groups password'.split():
                if name in a:
                    del a[name]
        return a
    args = [_cleandict(a) for a in args]
    print(*args)
