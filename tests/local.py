import unittest
from tests.base import app, config
from tests.aio import AioTestCase
from tests.app.simple import simple
from tests.app.services.detail import detail
import tests.app.config as _config
from os.path import normpath
import os


class LocalInstanceTest(AioTestCase):
    def test_creating_root_module_proxy_instance(self):
        self.assertEqual(app.__name__, "tests.app")

    def test_accessing_module(self):
        self.assertEqual(app.simple.__name__, "tests.app.simple")
        self.assertEqual(app.simple.__ctor__, simple)

    def test_accessing_deep_module(self):
        self.assertEqual(app.services.detail.__name__,
                         "tests.app.services.detail")
        self.assertEqual(app.services.detail.__ctor__, detail)

    async def test_getting_singleton_instance(self):
        await app.services.detail.setName("Mr. Handsome")
        self.assertEqual(await app.services.detail.getName(), "Mr. Handsome")
        await app.services.detail.setName("Mr. World")
        self.assertEqual(await app.services.detail.getName(), "Mr. World")

    async def test_accessing_non_class_module(self):
        self.assertEqual(app.config.__name__, "tests.app.config")

        self.assertEqual(app.config.__module__.hostname, _config.hostname)
        self.assertEqual(app.config.__module__.port, _config.port)

        value = await app.config.get("hostname")
        self.assertEqual(value, "127.0.0.1")

    async def test_getting_result_from_local_generator(self):
        gen = app.services.detail.getOrgs()
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

    async def test_invoking_asend_method_on_local_generator(self):
        gen = app.services.detail.repeatAfterMe()
        result = await gen.asend(None)
        result1 = await gen.asend("Google")

        self.assertEqual(result, None)
        self.assertEqual(result1, "Google")

    async def test_invoking_aclose_method_on_local_generator(self):
        gen = app.services.detail.repeatAfterMe()
        result = await gen.aclose()

        self.assertEqual(result, None)

    async def test_invoking_athrow_method_on_local_generator(self):
        gen = app.services.detail.repeatAfterMe()
        msg = "test athrow method"
        err: Exception

        try:
            await gen.athrow(Exception, msg)
        except Exception as e:
            err = e

        self.assertTrue(isinstance(err, Exception))
        self.assertEqual(err.args[0], msg)

    async def test_use_local_instance_when_server_runs_in_same_process(self):
        server = await app.serve(config)
        client = await app.connect(config)

        await server.register(app.services.detail)
        await client.register(app.services.detail)

        data = {}
        res = await app.services.detail.setAndGet(data)

        self.assertIs(res, data)

        await client.close()
        await server.close()


if __name__ == "__main__":
    unittest.main()
