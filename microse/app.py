from microse.proxy import ModuleProxy
from microse.rpc.server import RpcServer
from microse.rpc.client import RpcClient
import os


class ModuleProxyApp(ModuleProxy):
    """
    Creates a root module proxy.
    """

    def __init__(self, name: str, canServe=True):
        self._server = None
        self._cache = {}
        self._singletons = {}
        self._remoteSingletons = {}
        self._clientOnly = not canServe
        ModuleProxy.__init__(self, name, self)

    async def serve(self, options):
        """
        Serves an RPC server according to the given URL or Unix socket
        filename, or provide a dict for detailed options.

        `serve(url: str)`

        `serve(url: dict)`

        NOTE: this method is not available for client-only module proxy app.
        """

        if (self._clientOnly):
            raise Exception(
                "serve() is not available for client-only module proxy app")

        self._server = RpcServer(options)
        self._server.proxyRoot = self
        await self._server.open()
        return self._server

    async def connect(self, options):
        """
        Connects to an RPC server according to the given URL or Unix socket
        filename, or provide a dict for detailed options.

        `connect(url: str)`

        `connect(url: dict)`
        """
        client = RpcClient(options)
        await client.open()
        return client
