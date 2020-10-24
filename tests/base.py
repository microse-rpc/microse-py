from microse.app import ModuleProxyApp
import tests.app.config as _config
from tests.app.simple import simple as Simple
from tests.app.services.detail import detail as Detail


class Services:
    @property
    def detail(self) -> Detail:
        pass


class AppInstance(ModuleProxyApp):
    @property
    def config(self) -> _config:
        pass

    @property
    def simple(self) -> Simple:
        pass

    @property
    def services(self) -> Services:
        pass


app: AppInstance = ModuleProxyApp("tests.app")
config = {
    "hostname": _config.hostname,
    "port": _config.port,
    "timeout": _config.timeout
}
