#!/usr/bin/env python3

import json
import socket
from threading import Thread


def cmd(sock, action, data):
    data['action'] = action
    sock.send(json.dumps(data).encode())
    r = json.loads(sock.recv(8000).decode())
    print(r)
    assert r['status'] == 'ok'


while 1:
    try:
        sock = socket.socket()
        sock.connect(('localhost', 3344))
        reg_data = dict(agent='splunk-jmw', inputs=['email','orid','customerNumer'], outputs=['street1','city'])
        cmd(sock, 'register', reg_data)
        print('connected')
        while 1:
            r = json.loads(sock.recv(8000).decode())
            
    except (ConnectionRefusedError,ConnectionResetError):
        print('connection failed, retrying...')
