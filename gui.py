#!/usr/bin/env python3

import asyncio
from flask import Flask, render_template, request, send_from_directory
from threading import Thread
import websockets


app = Flask(__name__)
ws = set()


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/favicon.ico')
def favicon():
    return send_from_directory('static', 'favicon.ico', mimetype='image/x-icon')


async def feed(websocket, path):
    ws.add(websocket)
    try:
        async for message in websocket:
            print(message)
            await asyncio.wait([w.send(message) for w in ws])
    except Exception as e:
        print(e)
    finally:
        ws.remove(websocket)


def run_websocket():
    asyncio.get_event_loop().run_until_complete(
        websockets.serve(feed, '0.0.0.0', 5001))
    asyncio.get_event_loop().run_forever()


def run():
    Thread(target=app.run, kwargs=dict(host='0.0.0.0', port=5000, threaded=True)).start()
    run_websocket()


if __name__ == '__main__':
    run()
