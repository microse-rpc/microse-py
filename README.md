# 🌹Microse

Microse (stands for *Micro Remote Object Serving Engine*) is a light-weight
engine that provides applications the ability to serve modules as RPC services,
whether in another process or in another machine.

This is the python version of the microse implementation. For API reference,
please check the [API documentation](./api.md), or the
[Protocol Reference](https://github.com/microse-rpc/microse-node/blob/master/docs/protocol.md).

Other implementations:

- [microse-node](https://github.com/microse-rpc/microse-node) Node.js implementation
- [microse-swoole](https://github.com/microse-rpc/microse-swoole) PHP implementation
    based on swoole

## Install

```sh
pip install microse
```

## Peel The Onion

In order to use microse, one must create a root `ModuleProxyApp` instance, so
other files can use it as a root namespace and access its sub-modules.

### Example

```py
# app/app.py
from microse.app import ModuleProxyApp
import os

# Create an abstract class to be used for IDE intellisense:
class AppInstance(ModuleProxyApp):
    pass

# Create the instance amd add type annotation,
# 'app' will be the root namespace for modules
app: AppInstance = ModuleProxyApp("app")
```

In other files, just define a class with the same name as the filename, so that
another file can access it directly via the `app` namespace.

```py
# Be aware that the class name must correspond to the filename.

# app/Bootstrap.py
class Bootstrap:
    def init(self):
        # ...
```

Don't forget to augment types in the `AppInstance` class if you need IDE typing
support:

```python
from app.Bootstrap import Bootstrap as iBootstrap

class AppInstance(ModuleProxyApp):
    @property
    def Bootstrap(self) -> iBootstrap:
        pass
```

And other files can access to the modules via the namespace:

```py
# index.py
from app import app

#  Accessing the module as a singleton and calling its function directly.
app.Bootstrap.init()
```

### Non-class Module

If a module doesn't have a class with the same name as the filename, the module
it it self will be used instead.

```py
# app/config.py
async def get(name: str):
    # some async operations...
    return value
```

```py
# call the function directly
value = await app.config.get("someKey")
```

## Remote Service

The above example accesses the module and calls the function in the current
process, but we can do more, we can serve the module as a remote service, and
calls its functions as remote procedures.

### Example

For example, if I want to serve a user service in a different process, I just
have to do this:

```py
# app/services/User.py
# It is recommended not to define the '__init__' method or use a non-parameter
# '__init__' method.

class User:
    __users = [
        { "firstName": "David", "lastName": "Wood" },
        # ...
    ]

    # Any method that will potentially be called remotely shall be async.
    async def getFullName(self, firstName: str):
        for user in self.__users:
            if user["firstName"] == firstName:
                return f"{user['firstName']} {user['lastName']}"


# app/app.py
from app.services.User import User as iUser

class iServices:
    @property
    def User(self) -> iUser:
        pass

class AppInstance(ModuleProxyApp):
    @property
    def services(self) -> iService:
        pass
```

```py
# server.py
from app import app
import asyncio

async def serve():
    server = await app.serve("ws://localhost:4000")
    await server.register(app.services.User)

    print("Server started!")

loop = asyncio.get_event_loop()
loop.run_until_complete(serve())
loop.run_forever()
```

Just try `python server.py` and the service will be started immediately.

And in the client-side code, connect to the service before using remote
functions.

```py
# client.py
from app import app
import asyncio

async def connect():
    client = await app.connect("ws://localhost:4000")

    # Once registered, all functions of the service module will be remotized.
    await client.register(app.services.User)

    # Accessing the instance in local style but actually calling remote.
    fullName = await app.services.User.getFullName("David")

    print(fullName) # David Wood

asyncio.get_event_loop().run_until_complete(connect())
```

NOTE: to ship a service in multiple server nodes, just create and connect to
multiple channels, and register the service to each of them, when calling remote
functions, microse will automatically calculate routes and redirect traffics to
them.

NOTE: RPC calling will serialize (via JSON) all input and output data, those
data that cannot be serialized will be lost during transmission.

## Generator Support

When in the need of transferring large data, generator functions could be a
great help, unlike general functions, which may block network traffic when
transmitting large data since they send the data as a whole, generator functions,
on the other hand, will transfer the data piece by piece.

```py
# app/services/User.py
class User:
    __friends = {
        "David": [
            { "firstName": "Albert", "lastName": "Einstein" },
            { "firstName": "Nicola", "lastName": "Tesla" },
            # ...
        ],
        # ...
    }

    async def getFriendsOf(self, name: str):
        friends = self.__friends.get(name)

        if friends:
            for friend in friends:
                yield f"{friend['firstName'} {friend['lastName']}"
```

```py
# index.py

async def handle():
    generator = app.services.User.getFriendsOf("David")

    async for name in generator:
        print(name)
        # Albert Einstein
        # Nicola tesla
        # ...

    # The following usage gets the same result.
    generator2 = app.services.User.getFriendsOf("David")

    while True:
        try:
            name = await generator2.__anext__()
            print(name)
            # Albert Einstein
            # Nicola tesla
            # ...

        # When all data has been transferred, a StopAsyncIteration exception
        # will be raised.
        except StopAsyncIteration:
            break

asyncio.get_event_loop().run_until_complete(handle())
```

## Life Cycle Support

Microse provides a way to support life cycle functions, if a service class has
an `init()` method, it will be used for asynchronous initiation, and if the
class has a `destroy()` method, it will be used for asynchronous destruction.
With these feature, the service class can, for example, connect to a database
when starting the server and release the connection when the server shuts down.

```py
# app/services/User.py
class user:
    # Instead of using '__init__()', which is synchronous, we define an
    # asynchronous 'init()' method.
    async def init(self):
        # ...

    # Instead of using '__del__()', which is synchronous, we define an
    # asynchronous 'destroy()' method.
    async def destroy(self):
        # ...
```

## Standalone Client

Microse also provides a way to be running as a client-only application, in this
case the client will not actually load any modules since there are no such files,
instead, it just map the module names so you can use them as usual.

In the following example, we assume that `app.services.user` service is served
by a Node.js program, and we can use it in our python program as usual.

```py
from microse.app import ModuleProxyApp

app = ModuleProxyApp("app", False) # pass the second argument False

async def handle():
    client = await app.connect("ws://localhost:4000")
    await client.register(app.services.user)

    fullName = await app.services.user.getFullName("David")

    print(fullName) # David Wood

asyncio.get_event_loop().run_until_complete(handle())
```

For client-only application, you may need to declare all abstract classes:

```py
class iUser:
    def getFullName(self, name: str) -> str:
        pass

class iServices:
    @property
    def user(self) -> iUser:
        pass

class AppInstance(ModuleProxyApp):
    @property
    def services(self) -> iServices:
        pass
```

## Process Interop

This implementation supports interop in the same process, that means, if it
detects that the target remote instance is served in the current process,
the function will always be called locally and prevent unnecessary network
traffic.
