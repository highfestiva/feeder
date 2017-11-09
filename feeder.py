#!/usr/bin/env python3

import asyncio
from collections import OrderedDict
from datetime import datetime
import hashlib
import json
import socket
import time
from threading import Thread
import websockets


json_decoder = json.JSONDecoder(object_pairs_hook=OrderedDict)
connected2hoarder = False
company = 'hm'
department = 'cf'
group = 'jmw'
token = '441234567890=='
agents = {
}
ws = None
agent_job = 1
agent_job2queue = {
}


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
        job = data['id']
        data = data['data']
        forward(agent, job, data)
        return dict(status='ok')


def handle_agent(sock):
    agent = None
    while True:
        try:
            raw = sock.recv(32000).decode()
            #data = json.loads(raw)
            data = json_decoder.decode(raw)
            action = data['action']
            r = handle_agent_action(sock, agent, action, data)
            if 'agent' in r:
                agent = r['agent']
            if action != 'reply':
                r['action'] = 'reply'
                sock.send(json.dumps(r).encode())
            if action == 'register':
                output_status()
        except (ConnectionResetError, ConnectionAbortedError) as e:
            import traceback
            traceback.print_exc()
            if agent:
                remove_agent(agent)
                del agents[agent]
                output_status()
            break
        except json.decoder.JSONDecodeError as e:
            print('data error from agent', agent, type(e), e)
            print('raw data:', raw)
    sock.close()


def service_agents():
    sock = socket.socket()
    sock.bind(('', 3344))
    sock.listen(10)
    while True:
        conn, addr = sock.accept()
        Thread(target=handle_agent, args=(conn,)).start()


def send_find(find_data):
    print('find data:', find_data)
    sent_to = []
    for agent,agent_data in agents.items():
        inputs = agent_data['inputs']
        print('agent data: ', agent_data)
        query_data = {key:value for key,value in find_data.items() if value and key in inputs}
        print(query_data)
        if not query_data:
            continue
        query_data['action'] = 'find'
        query_data['id'] = find_data['id']
        sock = agent_data['socket']
        sock.send(json.dumps(query_data).encode())
        sent_to += [agent]
    return sent_to


def add_agent(agent):
    global ws
    if ws:
        websocket = ws
        a = agents[agent]
        message = json.dumps(dict(action='add-agent', agent=agent, inputs=list(a['inputs']), outputs=list(a['outputs'])))
        ws_loop.call_soon_threadsafe(lambda: asyncio.ensure_future(websocket.send(message)))


def remove_agent(agent):
    global ws
    if ws:
        websocket = ws
        message = json.dumps(dict(action='remove-agent', agent=agent))
        ws_loop.call_soon_threadsafe(lambda: asyncio.ensure_future(websocket.send(message)))


def forward(agent, job, data):
    data['agent'] = agent
    print('forwarding', data)
    ws_loop.call_soon_threadsafe(lambda: asyncio.ensure_future(agent_job2queue[job].put(data)))


async def handle_hoarder_action(websocket, action, data):
    if action == 'find':
        global agent_job, agent_job2queue
        find_data = dict(data['data'])
        find_data['id'] = agent_job
        job = agent_job
        agent_job += 1
        agent_job2queue[job] = asyncio.Queue()
        agents = send_find(find_data)
        agents_data = {agent:{} for agent in agents}
        recv_cnt = len(agents)
        print('find waiting for %i answers...' % recv_cnt)
        for cnt in range(recv_cnt): # explicit about count
            r = await agent_job2queue[job].get()
            print('find got a reply:', r)
            agent = r['agent']
            agents_data[agent].update(r)
            del agents_data[agent]['agent']
            reply = dict(status=('ok' if cnt==recv_cnt-1 else 'ok-partial'), action='reply', job=data['job'], data=agents_data)
            print('find partial reply:', reply)
            await websocket.send(json.dumps(reply))
        print('find done')
    elif action == 'reply':
        pass
    else:
        print(data)
        assert False


async def slave(uri):
    while True:
        global connected2hoarder
        connected2hoarder = False
        try:
            print('connecting')
            async with websockets.connect(uri) as websocket:
                global ws
                ws = websocket
                for agent in agents:
                    add_agent(agent)
                #Thread(target=user_input, args=(websocket,)).start()
                timestamp = datetime.now().isoformat()
                digest = hashlib.md5((timestamp+'|'+token).encode()).hexdigest()
                digest = timestamp + '|' + digest
                data = json.dumps(dict(action='register', company=company, department=department, group=group, digest=digest))
                await websocket.send(data)
                connected2hoarder = True
                while True:
                    raw = await websocket.recv()
                    data = json.loads(raw)
                    print('got hoarder data:', data)
                    action = data['action']
                    await handle_hoarder_action(websocket, action, data)
        except Exception as e:
            print(type(e), e)


def service_master():
    global ws_loop
    ws_loop = asyncio.new_event_loop()
    try:
        ws_loop.run_until_complete(slave('ws://localhost:5000/feed'))
    except Exception as e:
        print(type(e), e, 'crash and burn!')


def cleanup_agents():
    # for agent,agent_data in list(agents.items()):
        # t = agent_data['time']
        # if time.time()-t > 60:
            # remove_agent(agent)
            # del agents[agent]
    pass


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
