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
        self.assertEqual(app.name, "tests.app")
        self.assertEqual(app.path, normpath(os.getcwd() + "/test/app"))

    def test_accessing_module(self):
        self.assertEqual(app.simple.name, "tests.app.simple")
        self.assertEqual(app.simple.path,
                         normpath(os.getcwd() + "/test/app/simple"))
        self.assertEqual(app.simple.ctor, simple)

    def test_accessing_deep_module(self):
        self.assertEqual(app.services.detail.name, "tests.app.services.detail")
        self.assertEqual(app.services.detail.path,
                         normpath(os.getcwd() + "/test/app/services/detail"))
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
                         normpath(os.getcwd() + "/test/app/config"))

        self.assertEqual(app.config().hostname, _config.hostname)
        self.assertEqual(app.config().port, _config.port)

    def test_prototype_module_as_singleton(self):
        ins = app.config()
        self.assertEqual(ins, _config)

    async def test_getting_result_from_local_generator(self):
        gen = app.services.detail().getOrgs()
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
        gen = app.services.detail().repeatAfterMe()
        result = await gen.asend(None)
        result1 = await gen.asend("Google")

        self.assertEqual(result, None)
        self.assertEqual(result1, "Google")

    async def test_invoking_aclose_method_on_local_generator(self):
        gen = app.services.detail().repeatAfterMe()
        result = await gen.aclose()

        self.assertEqual(result, None)

    async def test_invoking_athrow_method_on_local_generator(self):
        gen = app.services.detail().repeatAfterMe()
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

        server.register(app.services.detail)
        client.register(app.services.detail)

        data = {}
        res = await app.services.detail("").setAndGet(data)

        self.assertIs(res, data)

        await client.close()
        await server.close()


if __name__ == "__main__":
    unittest.main()
