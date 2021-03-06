# API Reference

## ModuleProxy

This class is used to create proxy when accessing a module, it has the following
properties and methods:

- `__name__: str` The name (with namespace) of the module.
- `__module__: ModuleType` The original exports object of the module.
- `__ctor__: typing.Callable` If there is a class via the same name as the
    filename, this property returns the class, otherwise it returns `None`.

This class is considered abstract, and shall not be used in user code.

## ModuleProxyApp

This class extends from `ModuleProxy`, and has the following extra properties
and methods:

- `__init__(self, name: str, canServe = True)` Creates a root module proxy,
    `name` will be used as a namespace for importing modules, if `canServe` is
    `false`, the proxy cannot be used to serve modules, and a client-only
    application will be created.
- `serve(self, options) -> asyncio.Future[RpcServer]`
    Serves an RPC server according to the given URL or Unix socket filename, or
    provide a dict for detailed options.
    - `serve(url: str)`
    - `serve(url: dict)`
- `connect(self, options) -> asyncio.Future[RpcClient]`
    Connects to an RPC server according to the given URL or Unix socket
    filename, or provide a dict for detailed options.
    - `connect(url: str)`
    - `connect(url: dict)`

An microse application must use this class to create a root proxy in order to
use its features.

#### Serve and Connect to IPC

If the first argument passed to `serve()` or `connect()` is a string of
filename, the RPC connection will be bound to a Unix socket, AKA IPC, for
example:

```py
server = await app.serve("/tmp/test.sock")
client = await app.connect("/tmp/test.sock")
```

**NOTE: `serve()` method is not available for client-only applications.**

## RpcChannel

This abstract class just indicates the RPC channel that allows modules to
communicate remotely. methods `ModuleProxyApp.serve()` and
`ModuleProxyApp.connect()` return its server and client implementations
accordingly.

The following properties and methods work in both implementations:

- `id: str` The unique ID of the server or the client.
- `dsn: str` Gets the data source name according to the configuration.
- `open() -> asyncio.Future[None]` Opens the channel. This method is
    called internally by `ModuleProxyApp.serve()` and
    `ModuleProxyApp.connect()`.
- `close() -> asyncio.Future[None]` Closes the channel.
- `register(mod: ModuleProxy) -> asyncio.Future[None]` Registers a module
    to the channel.
- `onError(handler: Callable): void` Binds an error handler invoked whenever an
    error occurred in asynchronous operations which can't be caught during
    run-time, the first arguments passed to the `handler` function is the
    exception raised.

Other than the above properties, the following keys listed in `ChannelOptions`
will be patched to the channel instance as properties as well.

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
- `codec: str` The codec used to encode and decode messages, currently the only
    supported codec is `JSON`.
- `ssl: ssl.SSLContext` If `protocol` is `wss:`, the server must set this option
    in order to ship a secure server; if the server uses a self-signed
    certificate, the client should set this option as well.

## RpcServer

The server implementation of the RpcChannel, which has the following extra
methods:

- `publish(self, topic: str, data: typing.Any, clients: typing.List[str]=[]): bool`
    Publishes data to the corresponding topic, if `clients` (an array with
    client ids) are provided, the topic will only be published to them.
- `getClients(self): typing.List[str]` Returns all IDs of clients that connected
    to the server.

## RpcClient

The client implementation of the RpcChannel, which has the following extra
methods:

- `connecting: bool` Whether the channel is in connecting state.
- `connected: bool` Whether the channel is connected.
- `closed: bool` Whether the channel is closed.
- `pause(self)`  Pauses the channel and redirect traffic to other channels.
- `resume(self)` Resumes the channel and continue handling traffic.
- `subscribe(self, topic: str, handle: Callable): RpcClient` Subscribes a handle
    function to the corresponding topic. The only argument passed to the `handle`
    is the data sent to the topic.
- `unsubscribe(self, topic: str[, handle: Callable]): bool` Unsubscribes the
    handle function or all handlers from the corresponding topic.

### ClientOptions

This dictionary indicates the options used by the RpcClient's initiation, it
inherits all `ChannelOptions`, and with the following keys:

- `serverId: str` By default, the `serverId` is automatically set according to
    the `dsn` of the server, and updated after established the connect. However,
    if an ID is set when serving the RPC server, it would be better to set
    `serverId` to that ID as well.
- `timeout: int` Used to force a timeout error when an RPC request fires and
    doesn't get a response after a long time, default value is `5000`ms.
- `pingTimeout: int` Used to set the maximum delay of the connection, the client
    will constantly check the availability of the connection, default value is
    `5000`ms. If there are too much delay between the peers, the connection will
    be automatically released and a new connection will be created.
- `pintInterval: int` Used to set a internal timer for ping function to ensure
    the connection is alive, default value is `5000`ms. If the server doesn't
    response after sending a ping in time, the client will consider the server
    is down and will destroy and retry the connection.
