from microse.utils import local, evalRouteId, throwUnavailableError, getInstance
from importlib import import_module
from inspect import isclass
from typing import Callable, Any
import os


class ModuleProxy:
    """
    The base class used to create proxy when accessing a module.
    """

    def __init__(self, name: str, path: str, root):
        self.name = name
        self.path = os.path.normpath(path)
        self._root = root
        self._children = {}
        root._cache[name] = self

    @property
    def exports(self):
        """
        The original export of the module.
        """
        return import_module(self.name)

    @property
    def proto(self) -> Any:
        """
        If there is a class via the same name as the filename, this property
        returns the class, otherwise it returns the module itself.
        """
        exports = self.exports
        _name = self.name.split(".")[-1]
        _proto = getattr(exports, _name, None)

        # If the module has a class with the same name as the filename,
        # use it as the prototype, otherwise, use the module itself as
        # the prototype.
        if isclass(_proto):
            return _proto
        else:
            return exports

    @property
    def ctor(self) -> Callable:
        """
        If there is a class via the same name as the filename, this property
        returns the class, otherwise it returns `None`.
        """
        proto = self.proto

        if isclass(proto):
            return proto
        else:
            return None

    def new(self, *args, **kargs):
        """
        Creates a new instance of the module.
        """
        if self.ctor:
            return self.ctor(*args, **kargs)
        else:
            raise TypeError(self.name + " is not a valid module")

    # If the proxy is called as a function, reference it to the remote instance.
    def __call__(self, *args):
        index = self.name.rindex(".")
        modName = self.name[0:index]
        method = self.name[index+1:]
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
            else:
                throwUnavailableError(modName)
        else:
            ins = getInstance(self._root, modName)

            if callable(getattr(ins, method)):
                return getattr(ins, method)(*args)
            else:
                raise TypeError(f"{self.name} is not a function")

    def __getattr__(self, name: str):
        value = self._children.get(name)

        if value:
            return value
        elif name[0] != "_":
            value = ModuleProxy(self.name + "." + name,
                                self.path + os.sep + name,
                                self._root or self)
            self._children[name] = value
            return value
        else:
            return None

    def __instancecheck__(self, ins):
        return isinstance(ins, self.ctor)

    def __str__(self):
        return self.name

    def __json__(self):
        return self.name
