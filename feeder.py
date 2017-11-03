#!/usr/bin/env python3

import json
import socket
import time
from threading import Thread


company = 'hm'
group = 'jmw'
token = '441234567890=='
agents = {
}


def handle_action(sock, agent, action, data):
    if action == 'register':
        agent = data['agent']
        inputs = data['inputs']
        outputs = data['outputs']
        agents[agent] = dict(time=time.time(), socket=sock, inputs=set(inputs), outputs=set(outputs))
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


def handle(sock):
    agent = None
    iterations = 1
    try:
        while True:
            raw = sock.recv(8000).decode()
            data = json.loads(raw)
            action = data['action']
            if iterations == 1:
                assert action == 'register'
            r = handle_action(sock, agent, action, data)
            if 'agent' in r:
                agent = r['agent']
            r['action'] = 'reply'
            sock.send(json.dumps(r).encode())
            if iterations == 1:
                output_status()
    except (ConnectionResetError, ConnectionAbortedError, json.decoder.JSONDecodeError) as e:
        print('error:', e)
        if agent:
            del agents[agent]
            output_status()


def service_agents():
    sock = socket.socket()
    sock.bind(('', 3344))
    sock.listen(10)
    while True:
        conn, addr = sock.accept()
        Thread(target=handle, args=(conn,)).start()


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


def service_master():
    while True:
        time.sleep(5)
        r = find({'id': 'abc', 'email': 'hej@gmail.com'})
        print('find: %s' % r)


def cleanup_agents():
    for agent,agent_data in list(agents.items()):
        t = agent_data['time']
        if time.time()-t > 30:
            del agents[agent]


def output_status():
    print('status: ok')
    print('agents: %i' % len(agents))


def maint():
    time.sleep(2)
    output_status()
    while True:
        time.sleep(60)
        cleanup_agents()
        output_status()


def run():
    Thread(target=service_agents, daemon=True).start()
    Thread(target=service_master, daemon=True).start()
    maint()


if __name__ == '__main__':
    run()
