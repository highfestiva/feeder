#!/usr/bin/env python3

import json
import socket
import time
from threading import Thread


def send_cmd(sock, action, data):
    data['action'] = action
    sock.send(json.dumps(data).encode())


def handle(sock, action, data):
    if action == 'find':
        time.sleep(2)
        data = dict(status='ok', id=data['id'], data=dict(last_purchase='2017-11-08', credit='Yes'))
        send_cmd(sock, 'reply', data)


while 1:
    try:
        sock = socket.socket()
        sock.connect(('localhost', 3344))
        reg_data = dict(agent='jmw-credit-check', inputs=['customerNumer'], outputs=['last_purchase','credit'])
        send_cmd(sock, 'register', reg_data)
        print('connected')
        while 1:
            data = json.loads(sock.recv(32000).decode())
            action = data['action']
            handle(sock, action, data)
    except (ConnectionRefusedError,ConnectionResetError):
        print('connection failed, retrying...')
