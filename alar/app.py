from alar.proxy import ModuleProxy
from alar.rpc.server import RpcServer
from alar.rpc.client import RpcClient
import os


class ModuleProxyApp(ModuleProxy):
    def __init__(self, name: str, path: str):
        ModuleProxy.__init__(self, name, path, {}, self)
        self.path = os.path.normpath(path)
        self._server = None

    async def serve(self, options, immediate=True):
        """
        Serves an RPC server according to the given URL or Unix socket
        filename, or provide a dict for detailed options.

        `serve(url: str, immediate = True)`

        `serve(url: dict, immediate = True)`
        """
        self._server = RpcServer(options)
        self._server.proxyRoot = self
        immediate and await self._server.open(False)
        return self._server

    async def connect(self, options, immediate=True):
        """
        Connects to an RPC server according to the given URL or Unix socket
        filename, or provide a dict for detailed options.

        `connect(url: str, immediate = True)`

        `connect(url: dict, immediate = True)`
        """
        client = RpcClient(options)
        immediate and await client.open()
        return client

    def resolve(self, path: str) -> str:
        """
        Resolves the given path to a module name.
        """
        path = os.path.normpath(path)
        dir = self.path + os.sep

        if path.startswith(dir):
            modPath, ext = os.path.splitext(path[len(dir):])
            return self.name + "." + modPath.replace(os.sep, ".")
