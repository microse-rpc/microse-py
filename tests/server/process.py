from multiprocessing import Process, Manager
from alar.app import ModuleProxyApp
from alar.rpc.server import RpcServer
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


async def __serve(state: dict, env: dict):
    server: RpcServer = None

    if env.get("USE_IPC"):
        server = await app.serve(env.get("USE_IPC"))
    elif env.get("USE_URL"):
        server = await app.serve(env.get("USE_URL"))
    elif env.get("USE_ID"):
        __config = _config.copy()
        __config["id"] = env.get("USE_ID")
        server = await app.serve(__config)
    elif env.get("USE_SECRET"):
        __config = _config.copy()
        __config["secret"] = env.get("USE_SECRET")
        server = await app.serve(__config)
    elif env.get("USE_WSS"):
        __config = _config.copy()
        __config["protocol"] = "wss:"
        __config["hostname"] = "localhost"
        certFile = pathlib.Path(os.getcwd() + "/tests/cert.pem")
        keyFile = pathlib.Path(os.getcwd() + "/tests/key.pem")
        serverSLL = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        serverSLL.load_cert_chain(certFile, keyFile, "alartest")
        __config["ssl"] = serverSLL
        server = await app.serve(__config)
    else:
        server = await app.serve(_config)

    server.register(app.services.detail)

    state["ready"] = True

    while not state["exit"]:
        await asyncio.sleep(0.1)

    await server.close()
    state["ready"] = False


def __fork(state: dict, env: dict):
    loop = asyncio.get_event_loop()
    loop.run_until_complete(__serve(state, env))


async def serve(env: dict = {}):
    manager = Manager()
    state = manager.dict({"ready": False, "exit": False})

    prox = Process(target=__fork, args=(state, env))
    prox.start()

    while not state["ready"]:
        await asyncio.sleep(0.1)

    return ServerProcess(prox, state)


class ServerProcess:
    def __init__(self, prox: Process, state: dict):
        self.prox = prox
        self.state = state

    async def terminate(self):
        self.state["exit"] = True

        while self.state["ready"]:
            await asyncio.sleep(0.1)

        self.prox.terminate()
