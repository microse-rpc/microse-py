# Alar

Alar (stands for *Auto-Load And Remote*) is a light-weight engine that provides
applications the ability to auto-load modules and serve them remotely as RPC
services.

NOTE: Alar is originally designed for Node.js,  this python implementation is
primarily meant to allow python programs and Node.js programs work together in
the same fusion.

For API reference, please check the [API documentation](./api.md),
or the [Protocol Reference](https://github.com/hyurl/alar/blob/v7/docs/protocol.md).

## Install

```sh
pip install alar
```

## Peel The Onion

In order to use Alar, one must create a root `ModuleProxyApp` instance, so other
files can use it as a root namespace and access its sub-modules.

### Example

```py
# app/app.py
from alar.app import ModuleProxyApp
import os

app = ModuleProxyApp("app", os.getcwd() + "/app")
```

In other files, just define a class with the same name as the filename, so that
another file can access it directly via the `app` namespace.

(NOTE: Alar offers first priority of the same-name class, if a module doesn't 
have a same-name class, Alar will try to load all identifiers instead.)

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

# Calling the module as a function will link to the singleton of the module.
app.Bootstrap().init()

# Using `new()` method on the module to create a new instance.
user = app.models.User.new("Mr. Handsome")

print(user.getName()) # Mr. Handsome
```

*TIP: in regular python script, calling a class as a function will create an*
*instance, but since alar uses that signature for singletons, and*
*`app.Bootstrap` is technically not a class, so it has its own behavior and*
*calling style. This may seem a little weird at first, but it will get by.*

### Non-class Module

If a module doesn't have a class with the same name as the filename, then this
module will be used directly when accessing to it as a singleton.

```py
# app/config.py
hostname = "127.0.0.1"
port = 80
```

```py
config = app.config()

print(f"{config.hostname}:{config.port}") # 127.0.0.1:80
```

## Remote Service

RPC is the central part of alar engine, which allows user to serve a module
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
    service = await app.serve("ws://localhost:4000")
    service.register(app.services.User)

    print("Service started!")

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
    service = await app.connect("ws://localhost:4000")
    service.register(app.services.User)

    # Accessing the instance in local style but actually calling remote.
    # The **route** argument for the module must be explicit.
    fullName = await app.services.User("route").getFullName("David")

    print(fullName) # David Wood

asyncio.get_event_loop().run_until_complete(connect())
```

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
    generator = app.services.User("route").getFriendsOf("David")

    async for name in generator:
        print(name)
        # Albert Einstein
        # Nicola tesla
        # ...

    # The following usage gets the same result.
    generator2 = app.services.User("route").getFriendsOf("David")

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

Alar provides a new way to support life cycle functions, it will be used to
perform asynchronous initiation and destruction, for example, connecting to a
database when starting the services and release the connection when the server
shuts down.

To enable this feature, first calling `ModuleProxyApp.serve()` method to create
an RPC server that is not yet served immediately by passing the second argument
`false`, and after all preparations are finished, calling the `RpcServer.open()`
method to open the channel and initiate bound modules.

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

```py
async def serve():
    services = app.serve(config, False) # pass False to serve()
    services.register(app.services.User)

    # other preparations...

    await service.open()

asyncio.get_event_loop().run_until_complete(serve())
```

## Standalone Client

Alar also provides a way to be running as a standalone client outside the main
program codebase, Instead of importing from the main module, we import the 
`alar.client.app` sub-module, which is designed to be run in standalone python
programs. The client will not actually load any modules since there are no such
files, instead, it just map the module names so you can use them as usual. To
create a standalone client, use the following code:

```py
from alar.client.app import ModuleProxyApp

app = ModuleProxyApp("app") # no path needed

async def handle():
    client = await app.connect("ws://localhost:4000")
    client.register(app.services.User)

asyncio.get_event_loop().run_until_complete(handle())
```

For more details, please check the [API documentation](./api.md).
