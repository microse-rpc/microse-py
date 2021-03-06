import asyncio


class detail:
    def __init__(self, name="Mr. World"):
        def fn():
            pass

        self.propFn = fn
        self.name = name

    async def setName(self, name: str):
        self.name = name

    async def getName(self):
        return self.name

    async def getOrgs(self):
        yield "Mozilla"
        yield "GitHub"
        yield "Linux"

    async def repeatAfterMe(self):
        value = None

        while True:
            value = yield value

            if value == "break":
                break

    async def raiseError(self):
        raise TypeError("something went wrong")

    async def triggerTimeout(self):
        await asyncio.sleep(1.5)

    async def setAndGet(self, data):
        return data
