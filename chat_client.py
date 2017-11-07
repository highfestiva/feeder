#!/usr/bin/env python3

import asyncio
from threading import Thread
import websockets


loop = asyncio.get_event_loop()


def user_input(websocket):
    while True:
        message = input('>')
        loop.call_soon_threadsafe(lambda: asyncio.ensure_future(websocket.send(message)))


async def chat_client(uri):
    async with websockets.connect(uri) as websocket:
        Thread(target=user_input, args=(websocket,)).start()
        while True:
            print(await websocket.recv())


loop.run_until_complete(chat_client('ws://localhost:5001/apa/bepa'))
