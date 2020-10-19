import unittest
from alar.client.app import ModuleProxyApp
from tests.server.process import serve
import tests.app.config as config
import asyncio
import os
import ssl
import pathlib
import websockets


_config = {
    "hostname": config.hostname,
    "port": config.port,
    "timeout": config.timeout
}


class RpcCommonTest:
    @property
    def app(self) -> ModuleProxyApp:
        return self._app

    @property
    def utils(self) -> unittest.TestCase:
        return self

    async def test_serving_and_connecting_rpc_service(self):
        server = await serve()
        client = await self.app.connect(_config)

        client.register(self.app.services.detail)
        await self.app.services.detail("").setName("Mr. Handsome")
        res = await self.app.services.detail("").getName()

        self.utils.assertEqual(res, "Mr. Handsome")

        await client.close()
        await server.terminate()

    async def test_serving_and_connecting_rpc_with_secret(self):
        __config = _config.copy()
        __config["secret"] = "tesla"
        server = await serve({"USE_SECRET": "tesla"})
        client = await self.app.connect(__config)

        client.register(self.app.services.detail)

        await self.app.services.detail("").setName("Mr. Handsome")
        res = await self.app.services.detail("").getName()
        self.utils.assertEqual(res, "Mr. Handsome")

        await client.close()
        await server.terminate()

    async def test_serving_and_connecting_rpc_with_url(self):
        # There is a bug when using nest_asyncio, if set a domain name instead
        # an IP address, the server will hangup, the reason is unknown.
        url = "ws://127.0.0.1:18888/alar"
        server = await serve({"USE_URL": url})
        client = await self.app.connect(url)

        client.register(self.app.services.detail)

        await self.app.services.detail("").setName("Mr. Handsome")
        res = await self.app.services.detail("").getName()
        self.utils.assertEqual(res, "Mr. Handsome")

        await client.close()
        await server.terminate()

    async def test_serving_and_connecting_rpc_with_ssl(self):
        __config = _config.copy()
        __config["protocol"] = "wss:"
        __config["hostname"] = "localhost"
        clientConfig = __config.copy()
        certFile = pathlib.Path(os.getcwd() + "/tests/cert.pem")
        clientSSL = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        clientSSL.load_verify_locations(certFile)
        clientConfig["ssl"] = clientSSL
        server = await serve({"USE_WSS": "true"})
        client = await self.app.connect(clientConfig)

        client.register(self.app.services.detail)

        await self.app.services.detail("").setName("Mr. Handsome")
        res = await self.app.services.detail("").getName()
        self.assertEqual(res, "Mr. Handsome")

        await client.close()
        await server.terminate()

    async def test_using_custom_serverId(self):
        __config = _config.copy()
        __config["id"] = "test-server"
        server = await serve({"USE_ID": "test-server"})
        client = await self.app.connect(_config)

        client.register(self.app.services.detail)

        self.utils.assertEqual(
            self.app.services.detail("test-server"),
            self.app.services.detail.remoteSingletons["test-server"]
        )

        await client.close()
        await server.terminate()

    async def test_reconnecting_rpc_in_background(self):
        server = await serve()
        client = await self.app.connect(_config)

        client.register(self.app.services.detail)

        await server.terminate()
        await asyncio.sleep(0.1)

        async def reserve():
            nonlocal server
            server = await serve()

        asyncio.create_task(reserve())

        while not client.connected:
            await asyncio.sleep(0.1)

        await self.app.services.detail("").setName("Mr. World")
        res = await self.app.services.detail("").getName()
        self.utils.assertEqual(res, "Mr. World")

        await client.close()
        await server.terminate()

    async def test_rejecting_error_if_service_unavailable(self):
        err: Exception

        try:
            await self.app.services.detail("").getName()
        except Exception as e:
            err = e

        self.utils.assertTrue(isinstance(err, ReferenceError))
        self.utils.assertEqual(err.args[0],
                               "Service tests.app.services.detail is not available")

    async def test_getting_result_from_remote_generator(self):
        server = await serve()
        client = await self.app.connect(_config)

        client.register(self.app.services.detail)

        gen = self.app.services.detail("").getOrgs()
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

        self.utils.assertTrue(isinstance(err, StopAsyncIteration))
        self.utils.assertListEqual(result, expected)

        await client.close()
        await server.terminate()

    async def test_invoking_asend_method_on_remote_generator(self):
        server = await serve()
        client = await self.app.connect(_config)

        client.register(self.app.services.detail)

        gen = self.app.services.detail("").repeatAfterMe()
        result = await gen.asend(None)
        result1 = await gen.asend("Google")

        self.utils.assertEqual(result, None)
        self.utils.assertEqual(result1, "Google")

        await client.close()
        await server.terminate()

    async def test_invoking_aclose_method_on_remote_generator(self):
        server = await serve()
        client = await self.app.connect(_config)

        client.register(self.app.services.detail)

        gen = self.app.services.detail("").repeatAfterMe()
        result = await gen.aclose()

        self.utils.assertEqual(result, None)

        await client.close()
        await server.terminate()

    async def test_invoking_athrow_method_on_remote_generator(self):
        server = await serve()
        client = await self.app.connect(_config)

        client.register(self.app.services.detail)

        gen = self.app.services.detail("").repeatAfterMe()
        msg = "test athrow method"
        err: Exception

        try:
            await gen.athrow(Exception, msg)
        except Exception as e:
            err = e

        self.utils.assertTrue(isinstance(err, Exception))
        self.utils.assertEqual(err.args[0], msg)

        await client.close()
        await server.terminate()

    async def test_triggering_timeout_error(self):
        server = await serve()
        client = await self.app.connect(_config)

        client.register(self.app.services.detail)

        err: Exception

        try:
            await self.app.services.detail("").triggerTimeout()
        except Exception as e:
            err = e

        self.utils.assertTrue(isinstance(err, Exception))
        self.utils.assertEqual(err.args[0],
                               "tests.app.services.detail(route).triggerTimeout() timeout after 1.0s")

        await client.close()
        await server.terminate()

    async def test_refusing_connect_when_secret_not_match(self):
        server = await serve({"USE_SECRET": "tesla"})
        err: Exception = None

        try:
            await self.app.connect(_config)
        except Exception as e:
            err = e

        self.utils.assertEqual(err.args[0],
                               "server rejected WebSocket connection: HTTP 401")

        await server.terminate()

    async def test_refusing_connect_when_missing_client_id(self):
        server = await serve()
        err: Exception = None

        try:
            url = f"ws://{config.hostname}:{config.port}"
            await websockets.connect(url)
        except Exception as e:
            err = e

        self.utils.assertEqual(err.args[0],
                               "server rejected WebSocket connection: HTTP 401")

        await server.terminate()

    async def test_refusing_connect_when_using_unrecognized_pathname(self):
        server = await serve()
        err: Exception = None

        try:
            url = f"ws://{config.hostname}:{config.port}/somewhere?id=123"
            await websockets.connect(url)
        except Exception as e:
            err = e

        self.utils.assertEqual(err.args[0],
                               "server rejected WebSocket connection: HTTP 404")

        await server.terminate()


if __name__ == "__main__":
    unittest.main()
