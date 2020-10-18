from alar.client.proxy import ModuleProxy
from alar.rpc.client import RpcClient


class ModuleProxyApp(ModuleProxy):
    def __init__(self, name: str):
        ModuleProxy.__init__(self, name, None)

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
