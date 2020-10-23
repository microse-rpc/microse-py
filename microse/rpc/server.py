from websockets import WebSocketServer, WebSocketServerProtocol as WebSocket, serve, unix_serve
from websockets.exceptions import ConnectionClosedOK, ConnectionClosedError
from typing import Any, AsyncGenerator, List
from urllib.parse import parse_qs
from microse.rpc.channel import RpcChannel
from microse.utils import JSON, Map, ChannelEvents, now, parseError, throwUnavailableError, tryLifeCycleFunction, getInstance
from microse.proxy import ModuleProxy
import asyncio
import http
import os


GeneratorEvents = [ChannelEvents.YIELD,
                   ChannelEvents.RETURN,
                   ChannelEvents.THROW]


class RpcServer(RpcChannel):
    def __init__(self, options, hostname=""):
        RpcChannel.__init__(self, options, hostname)
        self.id = self.id or self.dsn
        self.wsServer = None
        self.registry = dict()
        self.clients = Map()
        self.tasks = Map()
        self.proxyRoot = None

    async def open(self):
        pathname = self.pathname
        isUnixSocket = self.protocol == "ws+unix:"
        wsServer: WebSocketServer

        if isUnixSocket and pathname:
            dir = os.path.dirname(pathname)
            os.path.exists(dir) or os.makedirs(dir)

            # If the path exists, it's more likely caused by a previous
            # server process closing unexpected, just remove it before ship
            # the new server.
            if os.path.exists(pathname):
                os.unlink(pathname)

        if isUnixSocket:
            wsServer = await unix_serve(self.__handleConnection, pathname,
                                        process_request=self.__handleHandshake,
                                        ping_interval=None,
                                        ping_timeout=None,
                                        ssl=self.ssl)
        else:
            wsServer = await serve(self.__handleConnection,
                                   self.hostname, self.port,
                                   process_request=self.__handleHandshake,
                                   ping_interval=None,
                                   ping_timeout=None,
                                   ssl=self.ssl)

        self.wsServer = wsServer

    async def __handleHandshake(self, path: str, headers):
        """
        Verify authentication on the `upgrade` stage.
        """
        parts = path.split("?")
        _pathname = parts[0]
        _query = ""

        if len(parts) >= 2:
            _query = "?".join(parts[1:])

        if self.protocol != "ws+unix:" and _pathname != self.pathname:
            return (http.HTTPStatus.NOT_FOUND, [], bytes([]))

        query = parse_qs(_query or "")
        clientId = str(query.get("id") and query.get("id")[0] or "")
        secret = str(query.get("secret")
                     and query.get("secret")[0] or "")

        if not clientId or (self.secret and secret != self.secret):
            return (http.HTTPStatus.UNAUTHORIZED, [], bytes([]))

    async def __handleConnection(self, client: WebSocket, path: str):
        _, _query = path.split("?")
        query = parse_qs(_query)
        clientId = str(query.get("id") and query.get("id")[0] or "")
        self.clients.set(client, clientId)
        self.tasks.set(client, Map())

        # Notify the client that the connection is ready.
        self.__dispatch(client, ChannelEvents.CONNECT, self.id)

        await self.__listenMessage(client)  # MUST use 'await'

    async def close(self):
        if self.wsServer:
            # wsServer.close() will emit close event on the clients, which
            # already closed tasks and empty maps, so we don't need to do the
            # work here.
            self.wsServer.close()
            await self.wsServer.wait_closed()

        for mod in self.registry.values():
            await tryLifeCycleFunction(mod, "destroy", self.handleError)

        if self.proxyRoot:
            self.proxyRoot._server = None
            self.proxyRoot._remoteSingletons = {}
            self.proxyRoot = None

    async def register(self, mod: ModuleProxy):
        self.registry[mod.__name__] = mod
        await tryLifeCycleFunction(mod, "init", self.handleError)

    def publish(self, topic: str, data: Any, clients: List[str] = []) -> bool:
        """
        Publishes data to the corresponding topic, if `clients` are provided,
        the topic will only be published to them.
        """
        sent = False

        for (socket, id) in self.clients:
            if len(clients) == 0 or id in clients:
                self.__dispatch(socket, ChannelEvents.PUBLISH, topic, data)
                sent = True

        return sent

    def getClients(self):
        """
        Returns all IDs of clients that connected to the server.
        """

        clients: List[str] = []

        for id in self.clients.values():
            clients.append(id)

        return clients

    def __dispatch(self, socket: WebSocket, event: int, taskId, data=None):
        if socket.open:
            if event == ChannelEvents.THROW and isinstance(data, Exception):
                data = {
                    "name": type(data).__name__,
                    "message": str(data.args[0])
                }

            _data: Any = None

            if event == ChannelEvents.CONNECT:
                _data = [event, str(taskId)]
            elif event == ChannelEvents.PONG:
                _data = [event, int(taskId)]
            elif self.codec == "JSON":
                _data = [event, taskId, data]

            if _data:
                try:
                    msg = JSON.stringify(_data)
                    asyncio.create_task(socket.send(msg))
                except Exception as err:
                    self.__dispatch(socket, ChannelEvents.THROW, taskId, err)

    async def __listenMessage(self, socket: WebSocket):
        while True:
            msg: Any = None

            try:
                msg = await socket.recv()
            except ConnectionClosedOK:
                pass
            except ConnectionError:
                pass
            except Exception as err:
                self.handleError(err)

            if socket.closed:
                # Handle disconnection asynchronously.
                asyncio.create_task(self.__handleDisconnection(socket))
                break

            # Process the message asynchronously.
            asyncio.create_task(self.__handleMessage(socket, msg))

    async def __handleDisconnection(self, socket: WebSocket):
        tasks: Map = self.tasks.get(socket)
        self.tasks.delete(socket)
        self.clients.delete(socket)

        if tasks:
            # Close all suspended tasks of the socket.
            task: AsyncGenerator
            for task in tasks.values():
                asyncio.create_task(task.aclose())

    async def __handleMessage(self, socket: WebSocket, res: Any):
        if type(res) != str:
            return

        req: list = None

        try:
            req = JSON.parse(res)
        except Exception as err:
            self.handleError(err)

        if type(req) != list or len(req) == 0 or type(req[0]) != int:
            return

        event: int = req[0]
        taskId: int = req[1]

        if len(req) == 5:
            module: str = req[2]
            method: str = req[3]
            args: list = req[4] or []

        if event == ChannelEvents.THROW and len(args) == 1 and type(args[0]) == dict:
            # parse exceptions and errors
            args[0] = parseError(args[0])

        if event == ChannelEvents.INVOKE:
            await self.__handleInvokeEvent(socket, taskId,
                                           module, method, args)

        elif event in GeneratorEvents:
            await self.__handleGeneratorEvent(socket, event, taskId,
                                              module, method, args)

        elif event == ChannelEvents.PING:
            self.__dispatch(socket, ChannelEvents.PONG, taskId)

    async def __handleInvokeEvent(
        self,
        socket: WebSocket,
        taskId: int,
        module: str,
        method: str,
        args: list
    ):
        event: int = 0
        data: Any = None
        tasks: Map = self.tasks.get(socket)

        try:
            mod = self.registry.get(module)

            if not mod:
                throwUnavailableError(module)

            app = mod._root
            ins = getInstance(app, module)

            if getattr(ins, "__readyState", -1) == 0:
                throwUnavailableError(module)

            task = getattr(ins, method)(*args)

            if hasattr(task, "__aiter__") and hasattr(task, "__anext__"):
                tasks.set(taskId, task)
                event = ChannelEvents.INVOKE
            elif hasattr(task, "__await__"):
                data = await task
                event = ChannelEvents.RETURN
            else:
                data = task
                event = ChannelEvents.RETURN

        except Exception as err:
            event = ChannelEvents.THROW
            data = err

        self.__dispatch(socket, event, taskId, data)

    async def __handleGeneratorEvent(
        self,
        socket: WebSocket,
        event: int,
        taskId: int,
        module: str,
        method: str,
        args: list
    ):
        data: Any = None
        input: Any = None
        tasks: Map = self.tasks.get(socket)
        task: AsyncGenerator = tasks.get(taskId)

        try:
            if not task:
                raise ReferenceError(f"Failed to call {module}.{method}()")
            elif len(args) > 0:
                input = args[0]
            else:
                input = None

            if event == ChannelEvents.YIELD:
                data = await task.asend(input)
                data = {"done": False, "value": data}
            elif event == ChannelEvents.RETURN:
                tasks.delete(taskId)
                data = await task.aclose()
                data = {"done": True}
            else:
                # Calling the throw method will cause an error being thrown and
                # go to the except block.
                await task.athrow(type(input), input.args[0])
        except StopAsyncIteration:
            event = ChannelEvents.RETURN
            tasks.delete(taskId)
            data = {"done": True}
        except Exception as err:
            event = ChannelEvents.THROW
            tasks.delete(taskId)
            data = err

        self.__dispatch(socket, event, taskId, data)
