#!/usr/bin/env python3

import asyncio
from datetime import datetime
import hashlib
import json
import socket
import time
from threading import Thread
import websockets


connected2hoarder = False
company = 'hm'
department = 'cf'
group = 'jmw'
token = '441234567890=='
agents = {
}
ws = None


def handle_agent_action(sock, agent, action, data):
    if action == 'register':
        agent = data['agent']
        inputs = data['inputs']
        outputs = data['outputs']
        agents[agent] = dict(time=time.time(), socket=sock, inputs=(inputs), outputs=set(outputs))
        add_agent(agent)
        return dict(status='ok', agent=agent)
    elif action == 'ping':
        agents[agent]['time'] = time.time()
        return dict(status='ok', result='pong')
    elif action == 'reply':
        agents[agent]['time'] = time.time()
        id = data['id']
        outputs = data['outputs']
        forward(agent, id, outputs)
        return dict(status='ok')


def handle_agent(sock):
    agent = None
    iterations = 1
    try:
        while True:
            raw = sock.recv(32000).decode()
            data = json.loads(raw)
            action = data['action']
            if iterations == 1:
                assert action == 'register'
            r = handle_agent_action(sock, agent, action, data)
            if 'agent' in r:
                agent = r['agent']
            r['action'] = 'reply'
            sock.send(json.dumps(r).encode())
            if iterations == 1:
                output_status()
            iterations += 1
    except (ConnectionResetError, ConnectionAbortedError, json.decoder.JSONDecodeError) as e:
        print('error:', e)
        if agent:
            remove_agent(agent)
            del agents[agent]
            output_status()


def service_agents():
    sock = socket.socket()
    sock.bind(('', 3344))
    sock.listen(10)
    while True:
        conn, addr = sock.accept()
        Thread(target=handle_agent, args=(conn,)).start()


def find(find_data):
    print('find data:', find_data)
    sent = 0
    for agent,agent_data in agents.items():
        inputs = agent_data['inputs']
        print('agent data: ', agent_data)
        query_data = {key:value for key,value in find_data.items() if key in inputs}
        print(query_data)
        if not query_data:
            continue
        query_data['action'] = 'find'
        query_data['id'] = find_data['id']
        sock = agent_data['socket']
        sock.send(json.dumps(query_data).encode())
        sent += 1
    return 'ok' if sent else 'unavailable'


def add_agent(agent):
    global ws
    if ws:
        websocket = ws
        a = agents[agent]
        message = json.dumps(dict(action='add-agent', msgid='2', agent=agent, inputs=list(a['inputs']), outputs=list(a['outputs'])))
        ws_loop.call_soon_threadsafe(lambda: asyncio.ensure_future(websocket.send(message)))


def remove_agent(agent):
    global ws
    if ws:
        websocket = ws
        message = json.dumps(dict(action='remove-agent', msgid='3', agent=agent))
        ws_loop.call_soon_threadsafe(lambda: asyncio.ensure_future(websocket.send(message)))


async def slave(uri):
    while True:
        global connected2hoarder
        connected2hoarder = False
        try:
            async with websockets.connect(uri) as websocket:
                global ws
                ws = websocket
                for agent in agents:
                    add_agent(agent)
                #Thread(target=user_input, args=(websocket,)).start()
                timestamp = datetime.now().isoformat()
                digest = hashlib.md5((timestamp+'|'+token).encode()).hexdigest()
                digest = timestamp + '|' + digest
                data = json.dumps(dict(action='register', msgid='1', feeder='', company=company, department=department, group=group, digest=digest))
                await websocket.send(data)
                connected2hoarder = True
                while True:
                    print(await websocket.recv())
        except:
            pass


def service_master():
    global ws_loop
    ws_loop = asyncio.new_event_loop()
    ws_loop.run_until_complete(slave('ws://localhost:5001/apa/bepa'))


def cleanup_agents():
    for agent,agent_data in list(agents.items()):
        t = agent_data['time']
        if time.time()-t > 30:
            remove_agent(agent)
            del agents[agent]


def output_status():
    print('status: %s' % ('ok' if connected2hoarder else 'not connected'))
    print('agents: %i' % len(agents))


def maint():
    time.sleep(2)
    output_status()
    while True:
        time.sleep(10)
        cleanup_agents()
        output_status()


def run():
    Thread(target=service_agents, daemon=True).start()
    Thread(target=service_master, daemon=True).start()
    maint()


if __name__ == '__main__':
    run()
