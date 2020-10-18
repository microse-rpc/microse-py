from websockets import WebSocketServer, WebSocketServerProtocol, serve, unix_serve
from websockets.exceptions import ConnectionClosedOK
from typing import Callable, Any, AsyncGenerator
from urllib.parse import urlparse, parse_qs
from alar.rpc.channel import RpcChannel
from alar.utils import sequid, randStr, JSON, Map, ChannelEvents, now, parseException, throwUnavailableError, tryLifeCycleFunction
from alar.client.proxy import ModuleProxy
import asyncio
import http
import ssl
import sys
import os
import pathlib


class RpcServer(RpcChannel):
    def __init__(self, options, host=""):
        RpcChannel.__init__(self, options, host)
        self.id = self.id or self.dsn
        self.enableLifeCycle = False
        self.wsServer = None
        self.pingTimer = None
        self.registry = dict()
        self.clients = Map()
        self.tasks = Map()
        self.proxyRoot = None
        self.state = "initiating"

    async def open(self, enableLifeCycle=True):
        protocol = self.protocol
        pathname = self.pathname
        isUnixSocket = protocol == "ws+unix:"
        wsServer: WebSocketServer

        if enableLifeCycle:
            self.enableLifeCycle = True

            # Perform initiation for every module in sequence.
            for mod in self.registry.values():
                await tryLifeCycleFunction(mod, "init", self.handleError)

        if isUnixSocket and pathname:
            dir = os.path.dirname(pathname)
            os.path.exists(dir) or os.makedirs(dir)

            # If the path exists, it's more likely caused by a previous
            # server process closing unexpected, just remove it before ship
            # the new server.
            if os.path.exists(pathname):
                os.unlink(pathname)

        # Verify authentication on the 'upgrade' stage.
        async def process_request(path: str, headers):
            parts = path.split("?")
            _pathname = parts[0]
            _query = ""

            if len(parts) >= 2:
                _query = "?".join(parts[1:])

            if not isUnixSocket and _pathname != pathname:
                return (http.HTTPStatus.NOT_FOUND, [], bytes([]))

            query = parse_qs(_query or "")
            clientId = str(query.get("id") and query.get("id")[0] or "")
            secret = str(query.get("secret")
                         and query.get("secret")[0] or "")

            if not clientId or (self.secret and secret != self.secret):
                return (http.HTTPStatus.UNAUTHORIZED, [], bytes([]))

        async def handleConnection(client: WebSocketServerProtocol, path: str):
            _, _query = path.split("?")
            query = parse_qs(_query)
            clientId = str(query.get("id") and query.get("id")[0] or "")
            self.clients.set(client, {"id": clientId, "isAlive": True})
            self.tasks.set(client, Map())

            # Notify the client that the connection is ready.
            self.__dispatch(client, ChannelEvents.CONNECT, self.id)

            asyncio.create_task(self.__listenClose(client))
            await self.__listenMessage(client)  # MUST use 'await'

        if isUnixSocket:
            wsServer = await unix_serve(handleConnection, pathname,
                                        process_request=process_request, ssl=self.ssl)
        else:
            wsServer = await serve(handleConnection, self.hostname, self.port,
                                   process_request=process_request, ssl=self.ssl)

        self.state = "listening"
        self.wsServer = wsServer
        self.__pingTask = asyncio.create_task(self.__listenPing())

    async def close(self):
        self.state = "closed"

        if self.wsServer:
            self.wsServer.close()
            self.__pingTask and self.__pingTask.cancel()

            # Close all suspended tasks of all socket.
            for tasks in self.tasks.values():
                for task in tasks.values():
                    await task.aclose()

            self.tasks = Map()
            self.clients = Map()
            await self.wsServer.wait_closed()

        if self.enableLifeCycle:
            for mod in self.registry.values():
                try:
                    await tryLifeCycleFunction(mod, "destroy")
                except:
                    pass

        if self.proxyRoot:
            self.proxyRoot.server = None
            self.proxyRoot = None

    def register(self, mod: ModuleProxy):
        self.registry[mod.name] = mod

    def publish(self, topic: str, data: Any, clients=[]):
        sent = False

        for (socket, info) in self.clients:
            if len(clients) == 0 or info["id"] in clients:
                self.__dispatch(socket, ChannelEvents.PUBLISH, topic, data)

        return sent

    def getClients(self) -> list:
        clients = []

        for info in self.clients.values():
            clients.append(info["id"])

        return clients

    def __dispatch(self, socket: WebSocketServerProtocol, event: int, taskId, data=None):
        if socket.open:

            if event == ChannelEvents.THROW and isinstance(data, Exception):
                data = {
                    "name": type(data).__name__,
                    "message": str(data.args[0])
                }

            if self.codec == "JSON":
                asyncio.create_task(socket.send(
                    JSON.stringify([event, taskId, data])))

    async def __listenMessage(self, socket: WebSocketServerProtocol):
        while True:
            if self.state == "closed" or socket.closed:
                break

            try:
                res: str = await socket.recv()
            except ConnectionClosedOK:
                continue
            except Exception as err:
                self.handleError(err)
                continue

            if type(res) != str:
                continue

            msg: list = JSON.parse(res)

            if type(msg) != list or type(msg[0]) != int:
                continue

            event: int = msg[0]
            taskId: int = msg[1]

            if len(msg) == 5:
                module: str = msg[2]
                method: str = msg[3]
                args: list = msg[4] or []

            # parse exceptions and errors
            if event == ChannelEvents.THROW and len(args) == 1 and type(args[0]) == dict:
                args[0] = parseException(args[0])

            if event == ChannelEvents.INVOKE:
                data: Any = None
                tasks: Map = self.tasks.get(socket)

                try:
                    mod = self.registry.get(module)

                    if not mod:
                        throwUnavailableError(module)

                    ins = mod()

                    if hasattr(ins, "__readyState") and getattr(ins, "__readyState", 0) != 1:
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
                    print(self.registry)
                    event = ChannelEvents.THROW
                    data = err

                self.__dispatch(socket, event, taskId, data)

            elif event in [ChannelEvents.YIELD, ChannelEvents.RETURN, ChannelEvents.THROW]:
                data: Any = None
                input: Any = None
                tasks: Map = self.tasks.get(socket)
                task: AsyncGenerator = tasks.get(taskId)

                try:
                    if not task:
                        callee = module + "(route)." + method + "()"
                        raise ReferenceError("Failed to call " + callee)
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
                        # Calling the throw method will cause an error
                        # being thrown and go to the except block.
                        await task.athrow(type(input), input.args[0])
                except StopAsyncIteration:
                    event = ChannelEvents.YIELD
                    tasks.delete(taskId)
                    data = {"done": True}
                except Exception as err:
                    event = ChannelEvents.THROW
                    tasks.delete(taskId)
                    data = err

                self.__dispatch(socket, event, taskId, data)

            elif event == ChannelEvents.PONG:
                info: dict = self.clients.get(socket)
                info["isAlive"] = True
                _now = now()
                ts = int(taskId or _now)

                if len(str(ts)) == 10:
                    ts *= 1000

                if now - ts > self.maxDelay:
                    socket.close(1001, "Slow Connection")
                    break

    async def __listenClose(self, socket: WebSocketServerProtocol):
        while True:
            try:
                if self.state == "closed" or socket.closed:
                    tasks: Map = self.tasks.get(socket)
                    self.tasks.delete(socket)
                    self.clients.delete(socket)

                    if tasks:
                        # Close all suspended tasks of the socket.
                        task: AsyncGenerator
                        for task in tasks.values():
                            asyncio.create_task(task.aclose())

                await asyncio.sleep(0.01)
                break
            except Exception as err:
                self.handleError(err)
                break

    async def __listenPing(self):
        while True:
            try:
                await asyncio.sleep(30)

                client: WebSocketServerProtocol
                info: dict
                for (client, info) in self.clients():
                    if info["isAlive"] == False:
                        asyncio.create_task(
                            client.close(1001, "Slow Connection"))
                    else:
                        client["isAlive"] = False
                        self.__dispatch(client, ChannelEvents.PING, now())
            except Exception as err:
                self.handleError(err)
