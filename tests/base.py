from microse.app import ModuleProxyApp
import tests.app.config as _config

app = ModuleProxyApp("tests.app")
config = {
    "hostname": _config.hostname,
    "port": _config.port,
    "timeout": _config.timeout
}
