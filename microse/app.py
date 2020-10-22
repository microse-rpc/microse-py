from microse.proxy import ModuleProxy
from microse.rpc.server import RpcServer
from microse.rpc.client import RpcClient
import os


class ModuleProxyApp(ModuleProxy):
    """
    Creates a root module proxy.
    """

    def __init__(self, name: str):
        self._server = None
        self._cache = {}
        self._singletons = {}
        self._remoteSingletons = {}
        ModuleProxy.__init__(self, name, self)

    async def serve(self, options):
        """
        Serves an RPC server according to the given URL or Unix socket
        filename, or provide a dict for detailed options.

        `serve(url: str)`

        `serve(url: dict)`
        """
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
