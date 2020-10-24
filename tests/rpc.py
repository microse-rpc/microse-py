import unittest
from tests.aio import AioTestCase
from tests.RpcCommon import RpcCommonTest
from tests.base import app, config
from tests.server.process import serve
import sys
import os


class RemoteInstanceTest(AioTestCase, RpcCommonTest):
    _app = app

    async def test_serving_and_connecting_ipc_service(self):
        # IPC on Windows is not supported.
        if sys.platform == "win32":
            return

        sockPath = os.getcwd() + "/test.sock"
        server = await serve({ "USE_IPC": sockPath })
        client = await app.connect(sockPath)
        await client.register(app.services.detail)

        self.assertEqual(client.dsn, "ws+unix:" + sockPath)
        self.assertEqual(client.serverId, "ws+unix:" + sockPath)

        await app.services.detail.setName("Mr. Handsome")
        res = await app.services.detail.getName()
        self.assertEqual(res, "Mr. Handsome")

        await client.close()
        await server.terminate()

    async def test_closing_server_before_closing_client(self):
        server = await app.serve(config)
        client = await app.connect(config)

        await server.register(app.services.detail)
        await client.register(app.services.detail)

        app.services.detail.getOrgs()
        self.assertEqual(server.clients.size, 1)
        self.assertEqual(server.tasks.size, 1)

        await server.close()
        self.assertEqual(server.clients.size, 0)
        self.assertEqual(server.tasks.size, 0)

        await client.close()

    async def test_life_cycle(self):
        async def init(self):
            await self.setName("Mr. Handsome")

        async def destroy(self):
            await self.setName("Mr. World")

        setattr(app.services.detail.__ctor__, "init", init)
        setattr(app.services.detail.__ctor__, "destroy", destroy)

        server = await app.serve(config)
        await server.register(app.services.detail)

        res = await app.services.detail.getName()
        self.assertEqual(res, "Mr. Handsome")

        await server.close()

        res2 = await app.services.detail.getName()
        self.assertEqual(res2, "Mr. World")

        delattr(app.services.detail.__ctor__, "init")
        delattr(app.services.detail.__ctor__, "destroy")


if __name__ == "__main__":
    unittest.main()
