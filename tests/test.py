import unittest
from alar.app import ModuleProxyApp
from tests.aio import AioTestCase
from tests.app.simple import simple
from tests.app.services.detail import detail
import tests.app.config as config
import websockets
import asyncio
import sys
import os
import ssl
import pathlib


app = ModuleProxyApp("tests.app", os.getcwd() + "/test/app/")
_config = {
    "hostname": config.hostname,
    "port": config.port,
    "timeout": config.timeout
}


class AlarTest(AioTestCase):
    def test_creating_root_module_proxy_instance(self):
        self.assertEqual(app.name, "tests.app")
        self.assertEqual(app.path, os.getcwd() + "/test/app")

    def test_accessing_module(self):
        self.assertEqual(app.simple.name, "tests.app.simple")
        self.assertEqual(app.simple.path,
                         os.getcwd() + "/test/app/simple")
        self.assertEqual(app.simple.ctor, simple)

    def test_accessing_deep_module(self):
        self.assertEqual(app.services.detail.name, "tests.app.services.detail")
        self.assertEqual(app.services.detail.path,
                         os.getcwd() + "/test/app/services/detail")
        self.assertEqual(app.services.detail.ctor, detail)

    def test_resolving_module_name_accroding_to_path(self):
        self.assertEqual(app.resolve(app.services.detail.path),
                         "tests.app.services.detail")
        self.assertEqual(app.resolve(app.services.detail.path + ".py"),
                         "tests.app.services.detail")

    async def test_creating_instance(self):
        test: detail = app.services.detail.new("Mr. Handsome")

        self.assertTrue(isinstance(test, detail))
        self.assertEqual(test.name, "Mr. Handsome")
        self.assertEqual(await test.getName(), test.name)

    async def test_getting_singleton_instance(self):
        await app.services.detail().setName("Mr. Handsome")
        self.assertTrue(isinstance(app.services.detail(), detail))
        self.assertEqual(app.services.detail().name, "Mr. Handsome")
        await app.services.detail().setName("Mr. World")
        self.assertEqual(await app.services.detail().getName(), "Mr. World")

    def test_isinstance_check(self):
        test: detail = app.services.detail.new("A-yon Lee")
        self.assertTrue(isinstance(test, app.services.detail))
        self.assertTrue(isinstance(app.services.detail(), app.services.detail))

    def test_accessing_non_class_module(self):
        self.assertEqual(app.config.name, "tests.app.config")
        self.assertEqual(app.config.path,
                         os.getcwd() + "/test/app/config")

        self.assertEqual(app.config().hostname, config.hostname)
        self.assertEqual(app.config().port, config.port)

    def test_prototype_module_as_singleton(self):
        ins = app.config()
        self.assertEqual(ins, config)

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

    async def test_serving_and_connecting_rpc_service(self):
        server = await app.serve(_config)
        client = await app.connect(_config)

        server.register(app.services.detail)
        client.register(app.services.detail)

        await app.services.detail("").setName("Mr. Handsome")
        res = await app.services.detail("").getName()
        self.assertEqual(res, "Mr. Handsome")

        await client.close()
        await server.close()

    async def test_serving_and_connecting_rpc_with_secret(self):
        __config = _config.copy()
        __config["secret"] = "tesla"
        server = await app.serve(__config)
        client = await app.connect(__config)

        server.register(app.services.detail)
        client.register(app.services.detail)

        await app.services.detail("").setName("Mr. Handsome")
        res = await app.services.detail("").getName()
        self.assertEqual(res, "Mr. Handsome")

        await client.close()
        await server.close()

    async def test_serving_and_connecting_rpc_with_url(self):
        url = "ws://localhost:18888/alar"
        server = await app.serve(url)
        client = await app.connect(url)

        server.register(app.services.detail)
        client.register(app.services.detail)

        await app.services.detail("").setName("Mr. Handsome")
        res = await app.services.detail("").getName()
        self.assertEqual(res, "Mr. Handsome")

        await client.close()
        await server.close()

    async def test_serving_and_connecting_rpc_with_ssl(self):
        __config = _config.copy()
        __config["protocol"] = "wss:"
        __config["hostname"] = "localhost"
        serverConfig = __config.copy()
        clientConfig = __config.copy()
        certFile = pathlib.Path(__file__).with_name("cert.pem")
        keyFile = pathlib.Path(__file__).with_name("key.pem")
        serverSLL = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        clientSSL = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        serverSLL.load_cert_chain(certFile, keyFile, "alartest")
        clientSSL.load_verify_locations(certFile)
        serverConfig["ssl"] = serverSLL
        clientConfig["ssl"] = clientSSL
        server = await app.serve(serverConfig)
        client = await app.connect(clientConfig)

        server.register(app.services.detail)
        client.register(app.services.detail)

        await app.services.detail("").setName("Mr. Handsome")
        res = await app.services.detail("").getName()
        self.assertEqual(res, "Mr. Handsome")

        await client.close()
        await server.close()

    async def test_using_custom_serverId(self):
        __config = _config.copy()
        __config["id"] = "test-server"
        server = await app.serve(__config)
        client = await app.connect(_config)

        server.register(app.services.detail)
        client.register(app.services.detail)

        self.assertEqual(
            app.services.detail("test-server"),
            app.services.detail.remoteSingletons["test-server"]
        )

        await client.close()
        await server.close()

    async def test_reconnecting_rpc_in_background(self):
        server = await app.serve(_config)
        client = await app.connect(_config)

        server.register(app.services.detail)
        client.register(app.services.detail)

        await server.close()
        await asyncio.sleep(0.1)

        async def reserve():
            nonlocal server
            server = await app.serve(_config)
            server.register(app.services.detail)

        asyncio.create_task(reserve())

        while not client.connected:
            await asyncio.sleep(0.1)

        await app.services.detail("").setName("Mr. World")
        res = await app.services.detail("").getName()
        self.assertEqual(res, "Mr. World")

        await client.close()
        await server.close()

    async def test_rejecting_error_if_service_unavailable(self):
        err: Exception

        try:
            await app.services.detail("").getName()
        except Exception as e:
            err = e

        self.assertTrue(isinstance(err, ReferenceError))

    async def test_getting_result_from_remote_generator(self):
        server = await app.serve(_config)
        client = await app.connect(_config)

        server.register(app.services.detail)
        client.register(app.services.detail)

        gen = app.services.detail("").getOrgs()
        expected = ["Mozilla", "GitHub", "Linux"]
        result = []
        err: Exception

        while True:
            try:
                res = await gen.__anext__()
                result.append(res)
            except StopAsyncIteration as e:
                err = e
                break

        self.assertTrue(isinstance(err, StopAsyncIteration))
        self.assertListEqual(result, expected)

        await client.close()
        await server.close()

    async def test_invoking_asend_method_on_remote_generator(self):
        server = await app.serve(_config)
        client = await app.connect(_config)

        server.register(app.services.detail)
        client.register(app.services.detail)

        gen = app.services.detail("").repeatAfterMe()
        result = await gen.asend(None)
        result1 = await gen.asend("Google")

        self.assertEqual(result, None)
        self.assertEqual(result1, "Google")

        await client.close()
        await server.close()

    async def test_invoking_aclose_method_on_remote_generator(self):
        server = await app.serve(_config)
        client = await app.connect(_config)

        server.register(app.services.detail)
        client.register(app.services.detail)

        gen = app.services.detail("").repeatAfterMe()
        result = await gen.aclose()

        self.assertEqual(result, None)

        await client.close()
        await server.close()

    async def test_invoking_athrow_method_on_remote_generator(self):
        server = await app.serve(_config)
        client = await app.connect(_config)

        server.register(app.services.detail)
        client.register(app.services.detail)

        gen = app.services.detail("").repeatAfterMe()
        msg = "test athrow method"
        err: Exception

        try:
            await gen.athrow(Exception, msg)
        except Exception as e:
            err = e

        self.assertTrue(isinstance(err, Exception))
        self.assertEqual(err.args[0], msg)

        await client.close()
        await server.close()

    async def test_triggering_timeout_error(self):
        server = await app.serve(_config)
        client = await app.connect(_config)

        server.register(app.services.detail)
        client.register(app.services.detail)

        err: Exception

        try:
            await app.services.detail("").triggerTimeout()
        except Exception as e:
            err = e

        self.assertTrue(isinstance(err, Exception))
        self.assertEqual(err.args[0],
                         "tests.app.services.detail(route).triggerTimeout() timeout after 1.0s")

        await client.close()
        await server.close()

    async def test_refusing_connect_when_secret_not_match(self):
        severConfig = _config.copy()
        severConfig["secret"] = "tesla"
        server = await app.serve(severConfig)
        err: Exception = None

        try:
            await app.connect(_config)
        except Exception as e:
            err = e

        self.assertEqual(err.args[0],
                         "server rejected WebSocket connection: HTTP 401")

        await server.close()

    async def test_refusing_connect_when_missing_client_id(self):
        server = await app.serve(_config)
        err: Exception = None

        try:
            url = f"ws://{config.hostname}:{config.port}"
            await websockets.connect(url)
        except Exception as e:
            err = e

        self.assertEqual(err.args[0],
                         "server rejected WebSocket connection: HTTP 401")

        await server.close()

    async def test_refusing_connect_when_using_unrecognized_pathname(self):
        server = await app.serve(_config)
        err: Exception = None

        try:
            url = f"ws://{config.hostname}:{config.port}/somewhere?id=123"
            await websockets.connect(url)
        except Exception as e:
            err = e

        self.assertEqual(err.args[0],
                         "server rejected WebSocket connection: HTTP 404")

        await server.close()

    async def test_getting_all_clients(self):
        server = await app.serve(_config)
        client = await app.connect(_config)
        clients = server.getClients()
        
        self.assertListEqual(clients, [client.id])

        await client.close()
        await server.close()

    async def test_subscribing_and_publishing_topic(self):
        server = await app.serve(_config)
        client = await app.connect(_config)
        data: str = ""

        def handle(msg):
            nonlocal data
            data = msg

        client.subscribe("set-data", handle)
        server.publish("set-data", "Mr. World")

        while not data:
            await asyncio.sleep(0.1)

        self.assertEqual(data, "Mr. World")

        await client.close()
        await server.close()


if __name__ == "__main__":
    unittest.main()
