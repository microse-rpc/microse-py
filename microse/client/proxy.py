from microse.utils import local, evalRouteId, throwUnavailableError
from typing import Any


class ModuleProxy:
    def __init__(self, name: str, root):
        self.__name__ = name
        self._root = root
        self._children = {}
        root._cache[name] = self

        # Standalone client doesn't support these properties, so just set  them
        # to None.
        self.__module__ = None
        self.__ctor__ = None

    def __getattr__(self, name: str):
        mod = self._children.get(name)

        if mod:
            return mod
        elif name[0] != "_":
            mod = ModuleProxy(self.__name__ + "." + name, self._root or self)
            self._children[name] = mod
            return mod
        else:
            return None

    def __call__(self, *args):
        index = self.__name__.rindex(".")
        modName = self.__name__[0:index]
        method = self.__name__[index+1:]
        singletons: dict = self._root._remoteSingletons.get(modName)

        if singletons and len(singletons.values()) > 0:
            route: Any

            if len(args) > 0:
                route = args[0]
            else:
                route = ""

            # If the route matches any key of the _remoteSingletons, return the
            # corresponding singleton as wanted.
            if type(route) == str and singletons.get(route):
                return singletons.get(route)

            _singletons = []

            for singelton in singletons.values():
                if getattr(singelton, "__readyState", 0):
                    _singletons.append(singelton)

            count = len(_singletons)
            ins: Any = None

            if count == 1:
                ins = _singletons[0]
            elif count >= 2:
                # If the module is connected to more than one remote instances,
                # redirect traffic to one of them automatically according to the
                # route.
                id = evalRouteId(route)
                ins = _singletons[id % count]

            if ins:
                return getattr(ins, method)(*args)

        throwUnavailableError(modName)

    def __str__(self):
        return self.__name__

    def __json__(self):
        return self.__name__
