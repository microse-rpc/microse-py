from microse.utils import evalRouteId, throwUnavailableError, getInstance
from importlib import import_module
from inspect import isclass
from typing import Callable, Any


class ModuleProxy:
    """
    The base class used to create proxy when accessing a module.
    """

    def __init__(self, name: str, root):
        self.__name__ = name
        self._root = root
        self._children = {}
        root._cache[name] = self

    @property
    def __module__(self):
        """
        The original export of the module.
        """
        if self._root._clientOnly:
            return None

        return import_module(self.__name__)

    @property
    def __ctor__(self) -> Callable:
        """
        If there is a class via the same name as the filename, this property
        returns the class, otherwise it returns `None`.
        """
        if self._root._clientOnly:
            return None

        _name = self.__name__.split(".")[-1]
        _class = getattr(self.__module__, _name, None)

        if isclass(_class):
            return _class
        else:
            return None

    def __getattr__(self, name: str):
        value = self._children.get(name)

        if value:
            return value
        elif name[0] != "_":
            value = ModuleProxy(self.__name__ + "." + name, self._root or self)
            self._children[name] = value
            return value
        else:
            return None

    # If the proxy is called as a function, reference it to the remote instance.
    def __call__(self, *args):
        index = self.__name__.rindex(".")
        modName = self.__name__[0:index]
        method = self.__name__[index+1:]
        singletons: dict = self._root._remoteSingletons.get(modName)

        if singletons and len(singletons.values()) > 0:
            route: Any
            ins: Any = None

            if len(args) > 0:
                route = args[0]
            else:
                route = ""

            # If the route matches any key of the _remoteSingletons, return the
            # corresponding singleton as wanted.
            if type(route) == str and singletons.get(route):
                ins = singletons.get(route)
            else:
                _singletons = []

                for singelton in singletons.values():
                    if getattr(singelton, "__readyState", 0):
                        _singletons.append(singelton)

                count = len(_singletons)

                if count == 1:
                    ins = _singletons[0]
                elif count >= 2:
                    # If the module is connected to more than one remote
                    # instances, redirect traffic to one of them automatically
                    # according to the route.
                    id = evalRouteId(route)
                    ins = _singletons[id % count]

            if ins:
                return getattr(ins, method)(*args)
            else:
                throwUnavailableError(modName)
        else:
            if self._root._clientOnly:
                throwUnavailableError(modName)

            # The module hasn't been registered to rpc channel, access the local
            # instance instead.
            ins = getInstance(self._root, modName)

            if callable(getattr(ins, method)):
                return getattr(ins, method)(*args)
            else:
                raise TypeError(f"{self.__name__} is not callable")

    def __str__(self):
        return self.__name__

    def __json__(self):
        return self.__name__
