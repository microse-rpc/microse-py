import unittest
from microse.utils import Map
from tests.aio import AioTestCase
from tests.base import app, config
import asyncio
import os

class PubSubTest(AioTestCase):
    async def test_getting_all_clients(self):
        server = await app.serve(config)
        client = await app.connect(config)
        clients = server.getClients()

        self.assertListEqual(clients, [client.id])

        await client.close()
        await server.close()

    async def test_subscribing_and_publishing_topic(self):
        server = await app.serve(config)
        client = await app.connect(config)
        data: str = ""

        def handle(msg):
            nonlocal data
            data = msg

        client.subscribe("set-data", handle)
        server.publish("set-data", "Mr. World")

        while not data:
            await asyncio.sleep(0.1)

        self.assertEqual(data, "Mr. World")

        await client.close()
        await server.close()

    async def test_subscribing_and_publishing_multi_topics(self):
        server = await app.serve(config)
        client = await app.connect(config)
        data1 = ""
        data2 = ""
        data3 = ""

        def handle(msg):
            nonlocal data1
            data1 = msg

        def handle1(msg):
            nonlocal data2
            data2 = msg

        def handle2(msg):
            nonlocal data3
            data3 = msg

        client.subscribe("set-data", handle)
        client.subscribe("set-data", handle1)
        client.subscribe("set-data-2", handle2)

        server.publish("set-data", "Mr. World")
        server.publish("set-data-2", "Mr. World")

        while not data1 or not data2 or not data3:
            await asyncio.sleep(0.1)

        self.assertEqual(data1, "Mr. World")
        self.assertEqual(data2, "Mr. World")
        self.assertEqual(data3, "Mr. World")

        await client.close()
        await server.close()

    async def test_unsubscribing_topic_handlers(self):
        server = await app.serve(config)
        client = await app.connect(config)

        def listener1():
            pass

        def listener2():
            pass

        client.subscribe("set-data", listener1)
        client.subscribe("set-data", listener2)
        client.subscribe("set-data-2", listener1)
        client.subscribe("set-data-2", listener2)

        client.unsubscribe("set-data", listener1)
        client.unsubscribe("set-data-2")

        self.assertTrue(isinstance(client.topics, Map))
        self.assertTrue(client.topics.size == 1)
        self.assertTrue(len(client.topics.get("set-data")) == 1)
        self.assertTrue(client.topics.get("set-data").index(listener2) == 0)

        await client.close()
        await server.close()

    async def test_publishing_topic_to_specified_clients(self):
        clientConfig = config.copy()
        clientConfig["id"] = "abc"
        server = await app.serve(config)
        client = await app.connect(clientConfig)
        data = ""

        self.assertEqual(client.id, "abc")

        def handle(msg):
            nonlocal data
            data = msg

        client.subscribe("set-data", handle)
        server.publish("set-data", "Mr. World", ["abc"])

        while not data:
            await asyncio.sleep(0.1)

        self.assertEqual(data, "Mr. World")

        await client.close()
        await server.close()


if __name__ == "__main__":
    unittest.main()
