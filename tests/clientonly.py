import unittest
from microse.app import ModuleProxyApp
from tests.aio import AioTestCase
from tests.RpcCommon import RpcCommonTest


app = ModuleProxyApp("tests.app", False)


class ClientOnlyTest(AioTestCase, RpcCommonTest):
    _app = app

    def test_creating_root_module_proxy_instance(self):
        self.assertEqual(app.__name__, "tests.app")

    def test_accessing_module(self):
        self.assertEqual(app.simple.__name__, "tests.app.simple")
        self.assertEqual(app.simple.__module__, None)
        self.assertEqual(app.simple.__ctor__, None)

    def test_accessing_deep_module(self):
        self.assertEqual(app.services.detail.__name__,
                         "tests.app.services.detail")
        self.assertEqual(app.services.detail.__module__, None)
        self.assertEqual(app.services.detail.__ctor__, None)

    async def test_throwing_error_if_trying_serve(self):
        err: Exception = None

        try:
            await app.serve("ws://localhost:18888")
        except Exception as e:
            err = e

        self.assertTrue(isinstance(err, Exception))
        self.assertEqual(
            err.args[0],
            "serve() is not available for client-only module proxy app")


if __name__ == "__main__":
    unittest.main()
