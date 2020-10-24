from urllib.parse import urlparse, parse_qs
from asyncio.futures import Future
from typing import Callable
import asyncio
import sys
import os


def print_err(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)


class RpcChannel:
    """
    An RPC channel that allows modules to communicate remotely.
    """

    def __init__(self, options, hostname=""):
        self.protocol = "ws:"
        self.hostname = "127.0.0.1"
        self.port = 80
        self.pathname = "/"
        self.id = ""
        self.secret = ""
        self.codec = "JSON"
        self.ssl = None
        self.onError(print_err)

        if type(options) == int:
            self.hostname = str(hostname or self.hostname)
            self.port = int(options)
        elif type(options) == dict:
            self.protocol = options.get("protocol") or self.protocol
            self.hostname = options.get("hostname") or self.hostname
            self.port = options.get("port") or self.port
            self.pathname = options.get("pathname") or self.pathname
            self.id = options.get("id") or self.id
            self.secret = options.get("secret") or self.secret
            self.codec = options.get("codec") or self.codec
            self.ssl = options.get("ssl") or self.ssl
        elif type(options) == str:
            url = str(options)
            isAbsPath = url[0] == "/"

            if not url.startswith("ws:") and not url.startswith("wss:"):
                baseUrl = "ws+unix://localhost:80"

                if not isAbsPath:
                    baseUrl += "/"

                url = baseUrl + url

            urlObj = urlparse(url)
            query = parse_qs(urlObj.query)

            isUnixSocket = urlObj.scheme == "ws+unix"
            self.protocol = urlObj.scheme + ":"
            self.id = str(query.get("id") and query.get("id")[0] or self.id)
            self.secret = str(query.get("secret")
                              and query.get("secret")[0] or self.secret)
            self.codec = str(query.get("codec")
                             and query.get("secret")[0] or self.codec)

            if isUnixSocket:
                self.hostname = ""
                self.port = 0

                if isAbsPath:
                    self.pathname = urlObj.path
                elif urlObj.path != "/":
                    self.pathname = os.path.normpath(
                        os.getcwd() + "/" + urlObj.path)
                else:
                    raise Exception("IPC requires a pathname")
            else:
                self.hostname = str(urlObj.hostname or self.hostname)
                self.port = int(urlObj.port or self.port)
                self.pathname = urlObj.path or "/"
        else:
            raise TypeError("Argument 'options' must be a str, int or dict")

        isUnixSocket = self.protocol == "ws+unix:"

        if isUnixSocket and sys.platform == "win32":
            raise Exception("IPC on Windows is currently not supported")
        elif self.codec != "JSON":
            raise Exception("Only 'JSON' is supported by this implementation")
        elif self.protocol == "wss:" and not self.ssl:
            raise Exception("'ssl' must be provided for 'wss:' protocol")

    @property
    def dsn(self):
        protocol = self.protocol
        pathname = self.pathname

        if protocol == "ws+unix:":
            return protocol + pathname
        else:
            return f"{protocol}//{self.hostname}:{str(self.port)}{pathname}"

    def onError(self, handler: Callable):
        def handle(err: Exception):
            res = handler(err)

            # If the returning value of handleError is a coroutine or future
            # object, run it asynchronously.
            if asyncio.iscoroutine(res) or asyncio.isfuture(res):
                asyncio.create_task(res)

        self.handleError = handle

    def open(self) -> Future:
        """
        Opens the channel.
        """
        pass

    def close(self) -> Future:
        """
        Closes the channel.
        """
        pass

    def register(self) -> Future:
        """
        Registers a module proxy to the channel.
        """
        pass
