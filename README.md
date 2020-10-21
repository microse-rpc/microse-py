# Microse

Microse (stands for *Micro Remote Object Serving Engine*) is a light-weight
engine that provides applications the ability to auto-load modules and serve
them remotely as RPC services.

For API reference, please check the [API documentation](./api.md),
or the [Protocol Reference](https://github.com/hyurl/microse/blob/master/docs/protocol.md).

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

app = ModuleProxyApp("app", os.getcwd() + "/app")
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

```py
# app/models/User.py

class User:
    def __init__(self, name: str):
        self.name = name

    def getName(self):
        return self.name

    def setName(self, name: str):
        self.name = name
```

And other files can access to the modules via the namespace:

```py
# index.py
from app import app

#  Accessing the module as a singleton and call its function directly.
app.Bootstrap.init()

# Using `new()` method on the module to create a new instance.
user = app.models.User.new("Mr. Handsome")

print(user.getName()) # Mr. Handsome
```

*TIP: in regular python script, calling a class as a function will create an*
*instance, but since microse uses this signature for function calls, so to*
*create instance, we should use the `new` method instead. This may seem a little*
*odd at first, but it will get by.*

### Non-class Module

If a module doesn't have a class with the same name as the filename, then this
module will be used directly when accessing to it as a singleton.

```py
# app/config.py
hostname = "127.0.0.1"
port = 80

async def get(key: str):
    # some async operations...
    return value
```

```py
# Use `exports` property to access the module original exports:
config = app.config.exports
print(f"{config.hostname}:{config.port}") # 127.0.0.1:80

# Functions can be called directly:
print(await app.config.get("someKey"))
```

## Remote Service

RPC is the central part of microse engine, which allows user to serve a module
remotely, whether in another process or in another machine.

### Example

Say I want to serve a user service in a different process and communicate via
RPC channel, I just have to do this:

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
```

```py
# server.py
from app import app
import asyncio

async def serve():
    channel = await app.serve("ws://localhost:4000")
    await channel.register(app.services.User)

    print("Server started!")

loop = asyncio.get_event_loop()
loop.run_until_complete(serve())
loop.run_forever()
```

Just try `python server.py` and the service will be started
immediately.

And in the client-side code, connect to the service before using remote
functions.

```py
# client.py
from app import app
import asyncio

async def connect():
    channel = await app.connect("ws://localhost:4000")
    await channel.register(app.services.User)

    # Accessing the instance in local style but actually calling remote.
    fullName = await app.services.User.getFullName("David")

    print(fullName) # David Wood

asyncio.get_event_loop().run_until_complete(connect())
```

NOTE: to ship a service in multiple server nodes, just create and connect to
multiple channels, and register the service to each of them, when calling remote
functions, microse will automatically calculate routes and redirect traffics to
them.

NOTE: RPC calling will serialize all input and output data, those data that
cannot be serialized will be lost during transmission.

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

Microse also provides a way to be running as a standalone client outside the
main program codebase, Instead of importing from the main module, we import the 
`microse.client.app` sub-module, which is designed to be run in standalone
python programs. The client will not actually load any modules since there are
no such files, instead, it just map the module names so you can use them as
usual. To create a standalone client, use the following code:

```py
from microse.client.app import ModuleProxyApp

app = ModuleProxyApp("app") # no path needed

async def handle():
    channel = await app.connect("ws://localhost:4000")
    await channel.register(app.services.User)

asyncio.get_event_loop().run_until_complete(handle())
```

For more details, please check the [API documentation](./api.md).
