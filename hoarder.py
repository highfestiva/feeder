#!/usr/bin/env python3

import asyncio
from flask import Flask, render_template, request, send_from_directory
import hashlib
import json
from threading import Thread
import websockets


app = Flask(__name__)
tokens = {'hm': '441234567890=='}
websocket2feeder = {}


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/<company>/<department>/<group>')
def get_search_page(company, department='', group=''):
    feeders = [values for values in websocket2feeder.values() if values['company'] == company]
    feeder_names = [feeder['group'].partition('-')[2] for feeder in feeders]
    agents = [agent for feeder in feeders for agent in feeder['agent2data'].keys()]
    inputs = [inp for feeder in feeders for agent_data in feeder['agent2data'].values() for inp in agent_data['inputs']]
    inputs = set(inputs)
    return render_template('search.html', company=company, department=department, group=group, feeders=feeder_names, agents=agents, inputs=inputs)


@app.route('/favicon.ico')
def favicon():
    return send_from_directory('static', 'favicon.ico', mimetype='image/x-icon')


def handle_action(websocket, action, data):
    if action == 'register':
        company    = data['company']
        department = '%s-%s' % (company, data['department'])
        group      = '%s-%s' % (department, data['group'])
        timestamp,_,digest = data['digest'].partition('|')
        if group in tokens:
            token = tokens[group]
        elif department in tokens:
            token = tokens[department]
        else:
            token = tokens[company]
        assert hashlib.md5((timestamp+'|'+token).encode()).hexdigest() == digest
        websocket2feeder[websocket] = dict(company=company, department=department, group=group, agent2data={})
        return dict(status='ok')
    elif action == 'add-agent':
        agent = data['agent']
        agent_data = dict(inputs=data['inputs'], outputs=data['outputs'])
        websocket2feeder[websocket]['agent2data'][agent] = agent_data
        return dict(status='ok')
    elif action == 'remove-agent':
        agent = data['agent']
        agent2data = websocket2feeder[websocket]['agent2data']
        if agent in agent2data:
            del agent2data[agent]
        return dict(status='ok')
    elif action == 'reply':
        present('something')
        agent = data['agent']
        return dict(status='ok')


async def handle(websocket, path):
    try:
        async for message in websocket:
            data = json.loads(message)
            msgid = data['msgid']
            action = data['action']
            r = handle_action(websocket, action, data)
            if action != 'reply':
                r['action'] = 'reply'
                r['reference-action'] = action
                r['msgid'] = msgid+'-reply'
                await websocket.send(json.dumps(r))
    except Exception as e:
        print(e)
    finally:
        if websocket in websocket2feeder:
            del websocket2feeder[websocket]


def run_websocket():
    asyncio.get_event_loop().run_until_complete(
        websockets.serve(handle, '0.0.0.0', 5001))
    asyncio.get_event_loop().run_forever()


def run():
    Thread(target=app.run, kwargs=dict(host='0.0.0.0', port=5000, threaded=True)).start()
    run_websocket()


if __name__ == '__main__':
    run()
