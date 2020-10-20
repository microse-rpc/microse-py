# API Reference

## ModuleProxy

This class used to create proxy when accessing a module, it has the following
properties and methods:

- `exports: ModuleType` The original export of the module.
- `proto: typing.Any` If there is a class via the same name as the filename,
    this property returns the class, otherwise it returns the module itself.
- `ctor: typing.Callable` If there is a class via the same name as the filename,
    this property returns the class, otherwise it returns `None`.
- `new(self, *args, **kargs)` Creates a new instance of the module.
- `instance(self, route=local)` Gets the local singleton or a remote instance of
    the module, if connected to one or more remote instances, the module proxy
    will automatically calculate the `route` and direct the traffic to the
    corresponding remote instance.
- `__call__ = instance` If the proxy is called as a function, reference it to
    the remote instance.

This class is considered abstract, and shall not be used in user code.

## ModuleProxyApp

This class extends from `ModuleProxy`, and has the following extra properties
and methods:

- `__init__(self, name: str, path: str)` Creates a root module proxy.
- `serve(self, options, immediate=True) -> asyncio.Future[RpcServer]`
    Serves an RPC server according to the given URL or Unix socket filename, or
    provide a dict for detailed options.
    - `serve(url: str, immediate = True)`
    - `serve(url: dict, immediate = True)`
- `connect(self, options, immediate=True) -> asyncio.Future[RpcClient]`
    Connects to an RPC server according to the given URL or Unix socket
    filename, or provide a dict for detailed options.
    - `connect(url: str, immediate = True)`
    - `connect(url: dict, immediate = True)`

An alar application must use this class to create a root proxy in order to use
its features.

#### Serve and Connect to IPC

If the first argument passed to `serve()` or `connect()` is a string of
filename, the RPC connection will be bound to a Unix socket, AKA IPC, for
example:

```ts
server = await app.serve("/tmp/test.sock");
client = await app.connect("/tmp/test.sock");
```

## RpcChannel

This abstract class just indicates the RPC channel that allows modules to
communicate remotely. methods `ModuleProxyApp.serve()` and
`ModuleProxyApp.connect()` return its server and client implementations
accordingly.

The following properties and methods work in both implementations:

- `id: str` The unique ID of the server or the client.
- `dsn: str` Gets the data source name according to the configuration.
- `open() -> asyncio.Future[RpcChannel]` Opens the channel. This method will be
    called automatically by `ModuleProxyApp.serve()` and
    `ModuleProxyApp.connect()` if their `immediate` argument is set `True`.
- `close() -> asyncio.Future[None]` Closes the channel.
- `register(mod: ModuleProxy) -> RpcChannel` Registers a module to the channel.
- `onError(handler: Callable` Binds an error handler invoked whenever an error
    occurred in asynchronous operations which can't be caught during run-time,
    the first arguments passed to the `handler` function is the exception raised.

### ChannelOptions

This dictionary indicates the options used by the RpcChannel's initiation, all
the following keys are optional:

- `protocol: str` The valid values are `ws:`, `wss:` and `ws+unix:`.
- `hostname: str` Binds the connection to a hostname.
- `port: int` Binds the connection to a port.
- `pathname: str` If `protocol` is `ws:` or `wss:`, the pathname is used as the
    URL pathname for checking connection; if `protocol` is `ws+unix:`, the
    pathname sets the filename of the unix socket.
- `secret: str` Used as a password for authentication, if used, the client must
    provide it as well in order to grant permission to connect.
- `id: str` In the server implementation, sets the server id, in the client
    implementation, sets the client id.
- `codec` The codec used to encode and decode messages, currently the only
    supported codec is `JSON`.
- `ssl: ssl.SSLContext` If `protocol` is `wss:`, the server must set this option
    in order to ship a secure server; if the server uses a self-signed
    certificate, the client should set this option as well.

## RpcServer

The server implementation of the RPC channel, which has the following extra
methods:

- `publish(self, topic: str, data: typing.Any, clients: typing.List[str]=[]): bool`
    Publishes data to the corresponding topic, if `clients` are provided, the
    topic will only be published to them.
- `getClients(self): typing.List[str]` Returns all IDs of clients that connected
    to the server.

## RpcClient

The client implementation of the RPC channel, which has the following extra
methods:

- `connecting: bool` Whether the channel is in connecting state.
- `connected: bool` Whether the channel is connected.
- `closed: bool` Whether the channel is closed.
- `pause(self)`  Pauses the channel and redirect traffic to other channels.
- `resume(self)` Resumes the channel and continue handling traffic.
- `subscribe(self, topic: str, handle: Callable)` Subscribes a handle
    function to the corresponding topic. The only argument passed to the `handle`
    is the data send to the topic.
- `unsubscribe(self, topic: str[, handle: Callable]): bool` Unsubscribes the
    handle function or all handlers from the corresponding topic.

### ClientOptions

This dictionary indicates the options used by the RpcClient's initiation, it
inherits all `ChannelOptions`, and with the following keys:

- `serverId: str` By default, the `serverId` is automatically set according to
    the `dsn` of the server, and updated after finishing the connect. However,
    if an ID is set when serving the RPC server, it would be better to set
    `serverId` to that ID as well.
- `timeout: int` Used to force a timeout error when an RPC request fires and
    doesn't get a response after a long time, default value is `5000`ms.
- `pingTimeout: int` Used to set the maximum delay of the connection, the client
    will constantly check the availability of the connection. If there are too
    much delay between the peers, the connection will be automatically released
    and a new connection will be created, default value is `5000`ms.
- `pintInterval: int` Used to set a internal timer for ping function to ensure
    the connection is alive. If the server doesn't response after sending a ping
    in time, the client will consider the server is down and will destroy and
    retry the connection.

## Pub-Sub Model between the server and clients

When the server publishes a message, all clients subscribe to the topic
will receive the data and invoke their handlers, this mechanism is often used
for the server to broadcast data to its clients.