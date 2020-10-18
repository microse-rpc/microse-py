from alar.utils import local, evalRouteId, throwUnavailableError
from typing import Any


class ModuleProxy:
    def __init__(self, name: str, root):
        self.name = name
        self.children = {}
        self.remoteSingletons = {}
        self.root = root

        # Standalone client doesn't support these properties, so just set  them
        # to None.
        self.path = None
        self.singletons = None
        self.exports = None
        self.proto = None
        self.ctor = None

    def new(self, *args, **kargs):
        return self.instance(local)

    def instance(self, route: Any = local):
        if route == local:
            raise TypeError(
                "Local instance is not supported by standalone client")

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

    def fallbackToLocal(self, enable=True):
        self.instance(local)

    __call__ = instance

    def __getattr__(self, name: str):
        value = self.children.get(name)

        if value:
            return value
        elif name[0] != "_":
            value = ModuleProxy(self.name + "." + name, self.root or self)
            self.children[name] = value
            return value
        else:
            return None

    def __str__(self):
        return self.name

    def __json__(self):
        return self.name
