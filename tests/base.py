from microse.app import ModuleProxyApp
import tests.app.config as _config
import os

app = ModuleProxyApp("tests.app", os.getcwd() + "/test/app/")
config = {
    "hostname": _config.hostname,
    "port": _config.port,
    "timeout": _config.timeout
}
