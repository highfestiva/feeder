#!/usr/bin/env python3

import asyncio
from collections import OrderedDict
from datetime import datetime
import hashlib
import json
import ldap_login
import queue
import socket
import time
from threading import Thread
from util import prt
import websocket


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
        data = dict(status=data['status'], data=data['data'])
        forward(agent, job, data)
        return dict(status='ok')


def handle_agent(sock):
    agent = None
    ok = False
    while True:
        try:
            raw = sock.recv(int(1e8)).decode()
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
            ok = True
        except (ConnectionResetError, ConnectionAbortedError) as e:
            import traceback
            traceback.print_exc()
            if agent:
                remove_agent(agent)
                del agents[agent]
                output_status()
            break
        except json.decoder.JSONDecodeError as e:
            prt('data error from agent', agent, type(e), e)
            prt('raw data:', raw)
            if not ok:
                break
            ok = False
    sock.close()


def service_agents():
    sock = socket.socket()
    sock.bind(('', 3344))
    sock.listen(10)
    while True:
        conn, addr = sock.accept()
        Thread(target=handle_agent, args=(conn,)).start()


def send_find(find_data):
    prt('find data:', find_data)
    sent_to = []
    for agent,agent_data in agents.items():
        inputs = agent_data['inputs']
        prt('agent data: ', agent_data)
        query_data = {key:value for key,value in find_data.items() if value and key in inputs}
        prt(query_data)
        if not query_data:
            continue
        send_data = dict(action='find', id=find_data['id'], query=query_data)
        sock = agent_data['socket']
        sock.send(json.dumps(send_data).encode())
        sent_to += [agent]
    return sent_to


def add_agent(agent):
    global ws
    if ws:
        websock = ws
        a = agents[agent]
        message = json.dumps(dict(action='add-agent', agent=agent, inputs=list(a['inputs']), outputs=list(a['outputs'])))
        #ws_loop.call_soon_threadsafe(lambda: asyncio.ensure_future(websock.send(message)))
        websock.send(message)


def remove_agent(agent):
    global ws
    if ws:
        websock = ws
        message = json.dumps(dict(action='remove-agent', agent=agent))
        #ws_loop.call_soon_threadsafe(lambda: asyncio.ensure_future(websock.send(message)))
        websock.send(message)


def forward(agent, job, data):
    data['agent'] = agent
    prt('forwarding', data)
    #ws_loop.call_soon_threadsafe(lambda: asyncio.ensure_future(agent_job2queue[job].put(data)))
    agent_job2queue[job].put(data)


def handle_hoarder_action(websock, action, data):
    if action == 'find':
        global agent_job, agent_job2queue
        find_data = dict(data['data'])
        find_data['id'] = agent_job
        job = agent_job
        agent_job += 1
        #agent_job2queue[job] = asyncio.Queue()
        agent_job2queue[job] = queue.Queue()
        agents = send_find(find_data)
        agents_data = {agent:{} for agent in agents}
        recv_cnt = len(agents)
        prt('find waiting for %i answers...' % recv_cnt)
        for cnt in range(recv_cnt): # explicit about count
            r = agent_job2queue[job].get()
            prt('find got a reply:', r)
            agent = r['agent']
            agents_data[agent].update(r)
            del agents_data[agent]['agent']
            reply = dict(status=('ok' if cnt==recv_cnt-1 else 'ok-partial'), action='reply', job=data['job'], data=agents_data)
            prt('find partial reply:', reply)
            websock.send(json.dumps(reply))
        prt('find done')
    elif action == 'login':
        username = data['username']
        password = data['password']
        domain = data['domain']
        fullname, groups = ldap_login.login(domain, username, password)
        prt('login:', fullname)
        reply = dict(status='ok', action='reply', job=data['job'], fullname=fullname, groups=groups)
        websock.send(json.dumps(reply))
    elif action == 'reply':
        pass
    else:
        prt(data)
        assert False


def service_master(uri):
    while True:
        raw = ''
        try:
            global connected2hoarder, ws
            connected2hoarder = False
            prt('connecting to', uri)
            ws = websock = websocket.create_connection(uri)
            timestamp = datetime.now().isoformat()
            digest = hashlib.md5((timestamp+'|'+token).encode()).hexdigest()
            digest = timestamp + '|' + digest
            data = json.dumps(dict(action='register', company=company, department=department, group=group, digest=digest))
            websock.send(data)
            for agent in agents:
                add_agent(agent)
            while True:
                raw = websock.recv()
                data = json.loads(raw)
                connected2hoarder = True
                prt('got hoarder data:', data)
                action = data['action']
                handle_hoarder_action(websock, action, data)
        except Exception as e:
            prt(type(e), e)
            prt(raw)


def cleanup_agents():
    # for agent,agent_data in list(agents.items()):
        # t = agent_data['time']
        # if time.time()-t > 60:
            # remove_agent(agent)
            # del agents[agent]
    pass


def output_status():
    prt('status: %s' % ('ok' if connected2hoarder else 'not connected'))
    prt('agents: %i' % len(agents))


def maint():
    time.sleep(2)
    output_status()
    while True:
        time.sleep(10)
        cleanup_agents()
        output_status()


def run():
    import sys
    host = '18.195.83.64' if not sys.argv[1:] else sys.argv[1]
    hoarder_url = 'ws://%s/api/' % host
    Thread(target=service_agents, daemon=True).start()
    Thread(target=service_master, daemon=True, args=(hoarder_url,)).start()
    maint()


if __name__ == '__main__':
    run()
