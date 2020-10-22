hostname = "127.0.0.1"
port = 18888
timeout = 1000

async def get(name: str):
    if name == "hostname":
        return hostname
    elif name == "port":
        return port
    elif name == "timeout":
        return timeout
    else:
        return None
