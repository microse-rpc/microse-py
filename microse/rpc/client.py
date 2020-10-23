from websockets import connect, unix_connect
from websockets.exceptions import ConnectionClosedOK
from typing import Callable, Any, List
from microse.rpc.channel import RpcChannel
from microse.utils import sequid, randStr, JSON, Map, ChannelEvents, now, parseError, throwUnavailableError, getInstance
from microse.proxy import ModuleProxy
import asyncio


loop = asyncio.get_event_loop()
ResolvableEvents = [ChannelEvents.RETURN,
                    ChannelEvents.INVOKE,
                    ChannelEvents.YIELD]


class RpcClient(RpcChannel):
    def __init__(self, options, host=""):
        RpcChannel.__init__(self, options, host)
        self.timeout = 5000
        self.pingTimeout = 5000
        self.pingInterval = 5000
        self.serverId = ""
        self.state = "initiated"
        self.socket = None
        self.registry = {}
        self.topics = Map()
        self.tasks = Map()  # Stores the all suspended generator calls.
        self.taskId = sequid(0)

        if type(options) == dict:
            self.timeout = options.get("timeout") or self.timeout
            self.serverId = options.get("serverId") or self.serverId
            self.pingTimeout = options.get("pingTimeout") or self.pingTimeout
            self.pingInterval = options.get(
                "pingInterval") or self.pingInterval

        self.id = self.id or randStr(10)
        self.serverId = self.serverId or self.dsn

    @property
    def connecting(self):
        """
        Whether the channel is in connecting state.
        """
        return self.state == "connecting"

    @property
    def connected(self):
        """
        Whether the channel is connected.
        """
        return self.state == "connected"

    @property
    def closed(self):
        """
        Whether the channel is closed.
        """
        return self.state == "closed"

    async def open(self):
        if self.socket and self.socket.open:
            raise Exception("Channel to " + self.serverId + " is already open")
        elif self.closed:
            raise Exception("Cannot reconnect to " +
                            self.serverId + " after closing the channel")

        self.state = "connecting"
        ping_timeout = self.pingTimeout / 1000
        ping_interval = self.pingInterval / 1000
        url: str

        if self.protocol == "ws+unix:":
            url = "ws://localhost?id=" + self.id

            if self.secret:
                url += "&secret=" + self.secret

            self.socket = await unix_connect(self.pathname, url, ssl=self.ssl,
                                             ping_interval=ping_interval,
                                             ping_timeout=ping_timeout)
        else:
            url = self.protocol + "//" + self.hostname + \
                ":" + str(self.port) + self.pathname + "?id=" + self.id

            if self.secret:
                url += "&secret=" + self.secret

            self.socket = await connect(url, ssl=self.ssl,
                                        ping_interval=ping_interval,
                                        ping_timeout=ping_timeout)

        # Accept the first message for handshake.
        msg = await self.socket.recv()
        res = self.__parseResponse(msg)

        if type(res) != list or len(res) < 2 or res[0] != ChannelEvents.CONNECT:
            # Protocol error, shall close the channel.
            self.close()
            raise Exception("Cannot connect to " + self.serverId)
        else:
            self.state = "connected"
            self.__updateServerId(str(res[1]))
            asyncio.create_task(self.__listenMessage())
            self.resume()

    def __updateServerId(self, serverId: str):
        if serverId != self.serverId:
            for name in self.registry:
                mod: ModuleProxy = self.registry[name]
                singletons = mod._root._remoteSingletons

                if singletons.get(self.serverId):
                    singletons[serverId] = singletons[self.serverId]
                    singletons.pop(self.serverId)

            self.serverId = serverId

    async def __listenMessage(self):
        while True:
            msg: Any = None

            try:
                msg = await self.socket.recv()
            except ConnectionClosedOK:
                pass
            except ConnectionError:
                pass
            except Exception as err:
                self.handleError(err)

            if self.socket.closed or self.closed:
                # Handle disconnection asynchronously.
                asyncio.create_task(self.__handleDisconnection())
                break

            # Process the message asynchronously.
            asyncio.create_task(self.__handleMessage(msg))

    def __parseResponse(self, msg: Any) -> list:
        if type(msg) != str:
            return

        try:
            return JSON.parse(msg)
        except Exception as err:
            self.handleError(err)

    async def __handleMessage(self, msg: Any):
        res = self.__parseResponse(msg)

        if type(res) != list or type(res[0]) != int:
            return

        event: int = res[0]
        taskId = res[1]
        data: Any = None

        if len(res) == 3:
            data = res[2]

        # When receiving response from the server, resolve immediately.
        if event in ResolvableEvents:
            task: Task = self.tasks.get(taskId)

            if task:
                task.resolve(data)

        # If any error occurs on the server, it will be delivered to the
        # client.
        elif event == ChannelEvents.THROW:
            task: Task = self.tasks.get(taskId)

            if task:
                task.reject(parseError(data))

        elif event == ChannelEvents.PUBLISH:
            # If receives the PUBLISH event, call all the handlers
            # bound to the corresponding topic.
            handlers: List[Callable] = self.topics.get(str(taskId))

            if handlers:
                for handle in handlers:
                    try:
                        res = handle(data)

                        if asyncio.iscoroutine(res) or asyncio.isfuture(res):
                            asyncio.create_task(res)

                    except Exception as err:
                        self.handleError(err)

    async def __handleDisconnection(self):
        # If the socket is closed or reset. but the channel remains open, pause
        # the service immediately and try to reconnect.
        if not self.connecting and not self.closed:
            self.pause()
            await self.__reconnect()

    async def __reconnect(self):
        while True:
            try:
                await self.open()
                break
            except:
                pass

            if self.closed:
                break
            else:
                await asyncio.sleep(2)

    def send(self, *args):
        if self.socket and self.socket.open:
            data = list(args)

            if self.codec == "JSON":
                asyncio.create_task(self.socket.send(JSON.stringify(data)))

    def subscribe(self, topic: str, handle: Callable):
        """
        Subscribes a handle function to the corresponding topic.
        """
        handlers: List[Callable] = self.topics.get(topic)

        if handlers is None:
            handlers = [handle]
            self.topics.set(topic, handlers)
        else:
            handlers.append(handle)

        return self

    def unsubscribe(self, topic: str, handle: Callable = None) -> bool:
        """
        Unsubscribes the handle function or all handlers from the corresponding
        topic.
        """
        if handle is None:
            return self.topics.delete(topic)
        else:
            handlers: List[Callable] = self.topics.get(topic)

            if handlers:
                try:
                    i = handlers.index(handle)
                    handlers.pop(i)
                    return True
                except:
                    pass

        return False

    async def close(self):
        self.state = "closed"
        self.pause()

        if self.socket:
            await self.socket.close()

        for name in self.registry:
            mod = self.registry[name]
            singletons: dict = mod._root._remoteSingletons.get(name)

            if singletons and singletons.get(self.serverId):
                singletons.pop(self.serverId)

    def pause(self):
        """
        Pauses the channel and redirect traffic to other channels.
        """
        self.__flushReadyState(0)

    def resume(self):
        """
        Resumes the channel and continue handling traffic.
        """
        self.__flushReadyState(1)

    async def register(self, mod: ModuleProxy):
        if self.registry.get(mod.__name__) is None:
            self.registry[mod.__name__] = mod
            singletons = mod._root._remoteSingletons.get(mod.__name__)

            if not singletons:
                singletons = mod._root._remoteSingletons[mod.__name__] = {}

            singletons[self.serverId] = self.__createRemoteInstance(mod)

            if self.connected:
                setattr(singletons[self.serverId], "__readyState", 1)
            else:
                setattr(singletons[self.serverId], "__readyState", 0)

    def __flushReadyState(self, state: int):
        for name in self.registry:
            mod: ModuleProxy = self.registry.get(name)
            singletons = mod._root._remoteSingletons.get(mod.__name__)

            if singletons and singletons.get(self.serverId):
                setattr(singletons.get(self.serverId), "__readyState", state)

    def __createRemoteInstance(self, mod: ModuleProxy):
        return RpcInstance(mod, self)


class RpcInstance:
    def __init__(self, module: ModuleProxy, client: RpcClient):
        self.props = {}
        self.module = module
        self.client = client
        self.__readyState = 0

    def __getattr__(self, prop: str):
        if self.props.get(prop) is None:
            mod = self.module
            ctor = mod.__ctor__
            method = getattr(ctor, prop, None)

            if ctor and not callable(method):
                return None

            def bound(*args):
                if ctor:
                    server: RpcChannel = mod._root and mod._root._server

                    # If the RPC server and the RPC client runs in the same
                    # process, then directly call the local instance to prevent
                    # unnecessary network traffics.
                    if server and server.id == self.client.serverId:
                        ins = getInstance(mod._root, mod.__name__)

                        if getattr(ins, "__readyState", -1) == 0:
                            throwUnavailableError(mod.__name__)
                        else:
                            return getattr(ins, prop)(*args)

                    # If the RPC channel is not available, call the local
                    # instance and wrap it asynchronous.
                    if not self.client.connected:
                        throwUnavailableError(mod.__name__)

                return AwaitableGenerator(self.client,
                                          mod.__name__, prop, *args)

            self.props[prop] = bound
            bound.__name__ = ctor and method.__name__ or prop

        return self.props.get(prop)


class Task:
    def __init__(self, resolve: Callable, reject: Callable, event=0, data=None):
        self.resolve = resolve
        self.reject = reject
        self.event = event
        self.data = data


class AwaitableGenerator:
    def __init__(self, client: RpcClient, module: str, method: str, *args):
        self.state = "pending"
        self.client = client
        self.module = module
        self.method = method
        self.taskId = next(client.taskId)

        # Generators calls will be queued in a sequence so that when the server
        # yield a value (which is sequential), the client can process them
        # properly. For regular calls, the queue's size is fixed to 1.
        self.queue = []

        # Initiate the task immediately when the remote method is called, this
        # operation will create an individual task, it will either be awaited as
        # a promise or iterated as a iterator.
        self.task = self.__invokeTask(ChannelEvents.INVOKE, *args)
        self.result = None

    def __await__(self):  # support 'await'
        if not self.task.done():
            yield from self.task

        if not self.task.done():
            raise RuntimeError("await wasn't used with future")  # required
        else:
            self.result = self.task.result()
            return self.result

    __iter__ = __await__  # make compatible with 'yield from'.

    def __aiter__(self):  # support `async for`
        return self

    async def __anext__(self):  # support `async for`
        return await self.asend(None)

    async def asend(self, value: Any):
        if self.state == "closed":
            raise StopAsyncIteration()

        try:
            # `res` will be a JSON in `{ value: Any, done: bool }`
            res: dict = await self.__invokeTask(ChannelEvents.YIELD, value)

            if res.get("done") is True:
                raise StopAsyncIteration()
            else:
                return res.get("value")
        except Exception as err:
            self.__close()
            raise err

    async def athrow(self, type: Callable, message: str = None, traceback=None):
        if self.state == "closed":
            return

        try:
            data = {
                "name": type.__name__,
                "message": message,
                "stack": traceback and str(traceback) or None
            }

            # notify the server
            await self.__invokeTask(ChannelEvents.THROW, data)
            self.__close()
        except:
            # raise local exception instead
            err = type(message)

            if traceback is not None:
                err = err.with_traceback(traceback)

            self.__close(err)
            raise err

    async def aclose(self):
        if self.state == "closed":
            return

        try:
            # `res` will be a JSON in `{ value: None, done: True }`
            res: dict = await self.__invokeTask(ChannelEvents.RETURN, None)

            if res.get("done") is True:
                self.__close()
                return
            else:
                raise RuntimeError(
                    "Generator must be closed after calling 'aclose()'")
        except Exception as err:
            self.__close()
            raise err

    def __close(self, result: Any = None):
        if self.state != "closed":
            self.result = result
            self.state = "closed"
            self.client.tasks.delete(self.taskId)

            # Stop all pending tasks
            task: Task
            for task in self.queue:
                if task.event == ChannelEvents.INVOKE:
                    task.resolve(None)
                elif task.event == ChannelEvents.YIELD:
                    task.resolve({"done": True, "value": None})
                elif task.event == ChannelEvents.RETURN:
                    task.resolve({"done": True, "value": task.data})
                elif task.event == ChannelEvents.THROW:
                    task.reject(task.data)

    def __createTask(self):
        def resolve(data):
            if self.state == "pending":
                if len(self.queue) > 0:
                    task: Task = self.queue[0]
                    self.queue = self.queue[1:]
                    task.resolve(data)

        def reject(err):
            if self.state == "pending":
                if len(self.queue) > 0:
                    task: Task = self.queue[0]
                    self.queue = self.queue[1:]
                    task.reject(err)

                self.__close()

        return Task(resolve, reject)

    def __prepareTask(self, event: int, args: List[Any]):
        if not self.client.tasks.get(self.taskId):
            self.client.tasks.set(self.taskId, self.__createTask())

        def handleTimeout():
            if len(self.queue) > 0:
                task: Task = self.queue[0]
                self.task = self.queue[1:]
                callee = self.module + "." + self.method + "()"
                duration = str(self.client.timeout / 1000) + "s"
                err = TimeoutError(callee + " timeout after " + duration)
                task.reject(err)

        timeout = loop.call_later(self.client.timeout / 1000, handleTimeout)
        future = loop.create_future()
        genData = None

        if len(args) > 0:
            genData = args[0]

        def resolve(data):
            timeout.cancelled() or timeout.cancel()
            future.set_result(data)

        def reject(err):
            timeout.cancelled() or timeout.cancel()
            future.set_exception(err)

        task = Task(resolve, reject, event, genData)
        self.queue.append(task)
        self.client.send(event, self.taskId,
                         self.module, self.method, args)

        return future

    def __invokeTask(self, event: int, *args):
        data = None

        if len(args) >= 1:
            data = args[0]

        if self.state == "closed":
            if event == ChannelEvents.INVOKE:
                return self.result
            elif event == ChannelEvents.YIELD:
                return None
            elif event == ChannelEvents.RETURN:
                return data
            elif event == ChannelEvents.THROW:
                raise data
        else:
            return self.__prepareTask(event, args)
