import time
import json
import random
import string
from enum import IntEnum
from typing import Callable, Any
from inspect import isclass


__global: dict = globals()["__builtins__"]

if type(__global) != dict:
    __global = __global.__dict__


class ChannelEvents(IntEnum):
    CONNECT, INVOKE, RETURN, THROW, YIELD, PUBLISH, PING, PONG = range(1, 9)


class JSONSerializable(json.JSONEncoder):
    def default(self, obj):
        if hasattr(obj, "toJSON"):
            return obj.toJSON()
        elif hasattr(obj, "__json__"):
            return obj.__json__
        elif hasattr(obj, "__dict__"):
            _dict = {}

            for key in obj.__dict__:
                if key[0:2] != "__":
                    _dict[key] = obj.__dict__[key]

            return _dict
        else:
            return obj


class JSON():
    @staticmethod
    def stringify(obj: Any) -> str:
        return json.dumps(obj, cls=JSONSerializable, ensure_ascii=False)

    @staticmethod
    def parse(jsonStr: str) -> Any:
        return json.loads(jsonStr)


class Map:
    @property
    def size(self):
        return len(self.__keys)

    def __init__(self, entry=[]):
        self.__keys = []
        self.__values = []

        for (key, value) in entry:
            self.set(key, value)

    def set(self, key, value):
        self.__keys.append(key)
        self.__values.append(value)

    def get(self, key):
        try:
            index = self.__keys.index(key)
            return self.__values[index]
        except:
            return None

    def delete(self, key):
        try:
            index = self.__keys.index(key)
            self.__keys.pop(index)
            self.__values.pop(index)
            return True
        except:
            return False

    def has(self, key):
        return key in self.__keys

    def clear(self):
        self.__keys = []
        self.__values = []

    def keys(self):
        for key in self.__keys:
            yield key

    def values(self):
        for value in self.__values:
            yield value

    def __iter__(self):
        for i in range(len(self.__keys)):
            yield (self.__keys[i], self.__values[i])


def sequid(id=0):
    while True:
        id += 1
        yield id


def randStr(length: int):
    letters = string.ascii_lowercase + string.ascii_uppercase
    return ''.join(random.choice(letters) for i in range(length))


def now():
    return round(time.time_ns() / 1000000)


def evalRouteId(value) -> int:
    _type = type(value)

    if value is None:
        return 0
    if _type in [bool, int, float]:
        return int(value)
    elif _type == str or _type == complex:
        return abs(hash(value))
    elif callable(value):
        return abs(hash(value.__name__))
    else:
        try:
            return abs(hash(JSON.stringify(value)))
        except:
            return id(value)


def parseError(data):
    err: Exception = None

    if type(data) == dict and type(data.get("message")) == str:
        errObj: dict = data
        name = errObj.get("name")
        message = errObj.get("message")
        code = errObj.get("code")

        if name in __global and isclass(__global[name]):
            err = __global[name](message)
        elif name == "EvalError":
            err = SyntaxError(message)
        elif name == "RangeError":
            err = OverflowError(message)
        elif code == "ERR_SYSTEM_ERROR":
            err = SystemError(message)
        elif code in ["MODULE_NOT_FOUND", "ERR_MODULE_NOT_FOUND"]:
            err = ModuleNotFoundError(message)
        elif code in ["ERR_BUFFER_TOO_LARGE", "ERR_OUTOFMEMORY", "ERR_OUT_OF_RANGE"]:
            err = OverflowError(message)
        elif code in ["ERR_INVALID_URI", "ERR_INVALID_URL", "ERR_INVALID_IP_ADDRESS"]:
            err = TypeError(message)
        elif code in ["ERR_MISSING_ARGS", "ERR_INVALID_TUPLE", "ERR_INVALID_THIS"]:
            err = TypeError(message)
        else:
            err = Exception(message)
    elif type(data) == str:
        err = Exception(data)
    else:
        err = Exception("Unexpected exception: " + str(data))

    return err


def getInstance(app, module: str):
    if not app._singletons.get(module):
        mod = app._cache.get(module)
        if mod:
            if mod.__ctor__:
                app._singletons[module] = mod.__ctor__()
            else:
                return mod.__module__
        else:
            throwUnavailableError(module)

    return app._singletons[module]


async def tryLifeCycleFunction(mod, fn: str, errorHandle: Callable):
    ins = getInstance(mod._root, mod.__name__)

    if fn == "init":
        if hasattr(ins, "init") and callable(ins.init):
            if errorHandle:
                try:
                    await ins.init()
                except Exception as err:
                    errorHandle(err)
            else:
                await ins.init()

        setattr(ins, "__readyState", 1)  # ready

    elif fn == "destroy":
        setattr(ins, "__readyState", 0)  # not ready

        if hasattr(ins, "destroy") and callable(ins.destroy):
            if errorHandle:
                try:
                    await ins.destroy()
                except Exception as err:
                    errorHandle(err)
            else:
                await ins.destroy()


def throwUnavailableError(module: str):
    raise ReferenceError(module + " is not available")
