#!/usr/bin/env python3

from argparse import ArgumentParser
from collections import OrderedDict, defaultdict
from glob import glob
import json
import re
import socket


tokensplit = re.compile(r'(=|:| |,|;|\[|\]|\(|\)|/|<|>|")')


def traverse_logs(options):
    for wildcard in options.log_wildcard:
        for filename in glob(wildcard):
            for line in open(filename, encoding=options.encoding):
                yield line


def line2kvs(options, line):
    token__1 = ''
    token_0 = ''
    for token in tokensplit.split(line):
        if token_0 == options.separator:
            yield token__1,token
        token__1 = token_0
        token_0 = token


def find_output_fields(options):
    outputs = set()
    for line in traverse_logs(options):
        for k,v in line2kvs(options, line):
            if v:
                outputs.add(k)
    return sorted(outputs)


def list_users(options, list_dict):
    fields = options.input
    user_dict = defaultdict(dict)
    for line_dict in list_dict:
        user_key = '~'.join(line_dict[search_key] for search_key in fields)
        user_dict[user_key].update(line_dict)
        #print('user key stuff:', user_key, user_dict)
    return list(user_dict.values())

def send_cmd(options, sock, action, data):
    data['action'] = action
    j = json.dumps(data)
    if options.verbose:
        print(' >', j)
    sock.send(j.encode())


def handle(options, sock, action, data):
    if options.verbose:
        print(' <', data)
    if action == 'find':
        hit2linekvs = defaultdict(set)
        query = data['query']
        #searches = [(k,v,'%s%s%s'%(k,options.separator,v)) for k,v in query.items()]
        for line in traverse_logs(options):
            linekvs = {k:v for k,v in line2kvs(options, line) if v}
            s_linekvs = str(linekvs) # from dict to hashable str
            #for sk,sv,skv in searches:
            for qk,qv in query.items():
                #if skv in line:
                if qk in linekvs:
                    if linekvs[qk].startswith(qv):
                        hit2linekvs[qk].add(s_linekvs)
        # pick common hits
        common = None
        for _,linekvs in hit2linekvs.items():
            if common == None:
                common = set(linekvs)
            else:
                common &= linekvs
        uds = [eval(s) for s in common] if common else [] # back from strs to dicts
        #print('uds:', uds)
        # print('query:', query)
        # Split up in [user1_dict, user2_dict, ...]
        users = list_users(options, uds)
        outputs = users[:10] # this is our result
        # print('outputs:', outputs)
        if len(outputs) > 1:
            outputs = [{k:o[k] for k in options.input} for o in outputs]
        # print('outputs:', outputs)
        data = dict(status='ok', id=data['id'], data=outputs)
        send_cmd(options, sock, 'reply', data)
    elif action == 'cleanse':
        query = data['query']
        for line in traverse_logs(options, mode='r+b'):
            only cleanse input fields?!?
            linekvs = {k:v for k,v in line2kvs(options, line) if v}
            searches = ['%s%s%s'%(k,options.separator,v) for k,v in query.items()]


parser = ArgumentParser()
parser.add_argument('name', help='name of agent')
parser.add_argument('--feeder', default='localhost:3344', help='tcp address of feeder')
parser.add_argument('--input', nargs='+', help='what search fields to expose to call center')
parser.add_argument('--encoding', default='utf-8', help='log file encoding')
parser.add_argument('--log-wildcard', nargs='+', help='wildcard of log files, for instance /var/log/myapp/*.log')
parser.add_argument('--separator', default='=', help='key value separator used in log files')
parser.add_argument('-v','--verbose', action='store_true', default=False, help='print more stuff')
options = parser.parse_args()
if not options.input:
    print('no input fields supplied')
if not options.log_wildcard:
    print('no input files supplied')
options.outputs = find_output_fields(options)
if not options.outputs:
    print('no output fields found in log files')
if options.verbose:
    print('inputs:')
    for i in options.input:
        print(' -', i)
    print('outputs:')
    for o in options.outputs:
        print(' -', o)
for i in options.input:
    if i not in options.outputs:
        print('ERROR: input field %s not available in logs' % i)
        import sys
        sys.exit(1)

while options.input and options.log_wildcard and options.outputs:
    try:
        sock = socket.socket()
        if options.verbose:
            print('connecting to %s...' % options.feeder)
        host,port = options.feeder.split(':')
        sock.connect((host, int(port)))
        print(options.name, 'connected')
        reg_data = dict(agent=options.name, inputs=options.input, outputs=options.outputs)
        send_cmd(options, sock, 'register', reg_data)
        while 1:
            data = json.loads(sock.recv(32000).decode())
            action = data['action']
            handle(options, sock, action, data)
    except (ConnectionRefusedError,ConnectionResetError):
        print('connection failed, retrying...')