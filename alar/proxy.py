from alar.utils import local, evalRouteId, throwUnavailableError
from importlib import import_module
from inspect import isclass
from typing import Callable, Any
import os


class ModuleProxy:
    """
    The base class used to create proxy when accessing a module.
    """

    def __init__(self, name: str, path: str, singletons: dict, root):
        self.name = name
        self.path = path
        self.root = root
        self.children = {}
        self.singletons = singletons
        self.remoteSingletons = {}
        self.__fallbackToLocal = False

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

    def instance(self, route=local):
        """
        Gets the local singleton or a remote instance of the module, if
        connected to one or more remote instances, the module proxy will
        automatically calculate the `route` and direct the traffic to the
        corresponding remote instance.
        """

        # If the route refers to the 'local', always return the local instance.
        if route == local:
            if not self.singletons.get(self.name):
                if self.ctor:
                    self.singletons[self.name] = self.new()
                else:
                    self.singletons[self.name] = self.exports

            return self.singletons.get(self.name)

        # If the route matches any key of the remoteSingletons, return the
        # corresponding singleton as wanted.
        if type(route) == str and self.remoteSingletons.get(route):
            return self.remoteSingletons.get(route)

        singletons = []

        for singleton in list(self.remoteSingletons.values()):
            if getattr(singleton, "__readyState", 0) == 1:
                singletons.append(singleton)

        count = len(singletons)

        if count == 0:
            throwUnavailableError(self.name)
        elif count == 1:
            return singletons[0]
        else:
            # Evaluate the route to produce id and
            id = evalRouteId(route)
            return singletons[id % count]  # return one of the singletons.

    def fallbackToLocal(self, enable: bool = None):
        """
        Allows the services falling to local instance if the remote instance
        isn't available.
        """
        if enable is None:
            return self.__fallbackToLocal
        else:
            self.__fallbackToLocal = enable

    # If the proxy is called as a function, reference it to the remote instance.
    __call__ = instance

    def __getattr__(self, name: str):
        value = self.children.get(name)

        if value:
            return value
        elif name[0] != "_":
            value = ModuleProxy(self.name + "." + name,
                                self.path + os.sep + name,
                                self.singletons,
                                self.root or self)
            self.children[name] = value
            return value
        else:
            return None

    def __instancecheck__(self, ins):
        return isinstance(ins, self.ctor)

    def __str__(self):
        return self.name

    def __json__(self):
        return self.name
