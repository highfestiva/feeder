#!/usr/bin/env python3

import asyncio
import websockets


connections = set()


async def broadcast(websocket, path):
    connections.add(websocket)
    try:
        async for message in websocket:
            print(message)
            await asyncio.wait([w.send(message) for w in connections])
    finally:
        connections.remove(websocket)


asyncio.get_event_loop().run_until_complete(websockets.serve(broadcast, '0.0.0.0', 5001))
asyncio.get_event_loop().run_forever()
