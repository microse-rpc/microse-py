import unittest
from microse.client.app import ModuleProxyApp
from tests.aio import AioTestCase
from tests.RpcCommon import RpcCommonTest


app = ModuleProxyApp("tests.app")


class StandaloneClientTest(AioTestCase, RpcCommonTest):
    _app = app

    def test_creating_root_module_proxy_instance(self):
        self.assertEqual(app.name, "tests.app")
        self.assertEqual(app.path, None)

    def test_accessing_module(self):
        self.assertEqual(app.simple.name, "tests.app.simple")
        self.assertEqual(app.simple.path, None)
        self.assertEqual(app.simple.ctor, None)
        self.assertEqual(app.simple.proto, None)
        self.assertEqual(app.simple.exports, None)

    def test_accessing_deep_module(self):
        self.assertEqual(app.services.detail.name, "tests.app.services.detail")
        self.assertEqual(app.services.detail.path, None)
        self.assertEqual(app.services.detail.ctor, None)
        self.assertEqual(app.services.detail.proto, None)
        self.assertEqual(app.services.detail.exports, None)

    def test_throwing_error_if_trying_to_create_instance(self):
        err: Exception

        try:
            app.services.detail.new("Mr. Handsome")
        except Exception as e:
            err = e

        self.assertTrue(isinstance(err, TypeError))
        self.assertEqual(err.args[0],
                         "tests.app.services.detail is not a class")


if __name__ == "__main__":
    unittest.main()
