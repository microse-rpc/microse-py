import unittest
from alar.app import ModuleProxyApp
from tests.aio import AioTestCase
from tests.RpcCommon import RpcCommonTest
import tests.app.config as config
import sys
import os


app = ModuleProxyApp("tests.app", os.getcwd() + "/test/app/")
_config = {
    "hostname": config.hostname,
    "port": config.port,
    "timeout": config.timeout
}


class RemoteInstanceTest(AioTestCase, RpcCommonTest):
    _app = app

    async def test_serving_and_connecting_ipc_service(self):
        # IPC on Windows is not supported.
        if sys.platform == "win32":
            return

        sockPath = os.getcwd() + "/alar.sock"
        server = await app.serve(sockPath)
        client = await app.connect(sockPath)
        server.register(app.services.detail)
        client.register(app.services.detail)

        await app.services.detail("").setName("Mr. Handsome")
        res = await app.services.detail("").getName()
        self.assertEqual(res, "Mr. Handsome")

        await client.close()
        await server.close()

    async def test_accessing_singleton_with_dsn(self):
        server = await app.serve(_config)
        client = await app.connect(_config)

        server.register(app.services.detail)
        client.register(app.services.detail)

        self.assertEqual(
            app.services.detail(server.dsn),
            app.services.detail.remoteSingletons[server.dsn]
        )

        await client.close()
        await server.close()

    async def test_closing_server_before_closing_client(self):
        server = await app.serve(_config)
        client = await app.connect(_config)

        server.register(app.services.detail)
        client.register(app.services.detail)

        app.services.detail("").getOrgs()
        self.assertEqual(server.clients.size, 1)
        self.assertEqual(server.tasks.size, 1)

        await server.close()
        self.assertEqual(server.clients.size, 0)
        self.assertEqual(server.tasks.size, 0)

        await client.close()

    async def test_life_cycle(self):
        server = await app.serve(_config, False)
        server.register(app.services.detail)
        await server.open()

        res = await app.services.detail().getName()
        self.assertEqual(res, "Mr. Handsome")

        await server.close()

        res2 = await app.services.detail().getName()
        self.assertEqual(res2, "Mr. World")

        # Recover readyState of the service since this test maybe started early.
        delattr(app.services.detail(), "__readyState")


if __name__ == "__main__":
    unittest.main()
