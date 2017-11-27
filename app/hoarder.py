#!/usr/bin/env python3

import asyncio
from flask import Flask, jsonify, redirect, render_template, request, send_from_directory
from wtforms import Form, PasswordField, StringField, validators
from flask_login import current_user, login_required, login_user, LoginManager, AnonymousUserMixin, UserMixin
import hashlib
import json
import time
from threading import Thread
from util import prt, uniq
import uuid
import websockets


app = Flask(__name__)
app.secret_key = 'non-secret'
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = '/'
tokens = {'hm': '441234567890=='}
websocket2feeder = {}
job2reply = {}
userdb = {}


class LoginForm(Form):
    username = StringField('Email Address', [validators.Length(min=6, max=35)])
    password = PasswordField('Password', [validators.Length(min=4, max=35)])


class User(UserMixin):
    def __init__(self, username):
        self.username = username
        self.domain = None
    @property
    def is_authenticated(self):
        return not not self.domain
    def get_id(self):
        return self.username


@login_manager.user_loader
def load_user(user_id):
    user = userdb.get(user_id)
    if not user:
        user = User(user_id)
        userdb[user_id] = user
    return user


@app.route('/', methods=['GET', 'POST'])
def index():
    nxt = request.values.get('next', '/search')
    form = LoginForm(request.form)
    if request.method == 'POST' and form.validate():
        username = form.username.data
        password = form.password.data
        domain = username.partition('@')[2].split('.')[-2]
        fullname, groups = login(domain, username, password)
        user = load_user(username)
        user.domain = domain
        user.fullname = fullname
        user.groups = groups
        login_user(user)
        assert current_user.fullname == fullname
        prt('Logged in successfully.')
        return redirect(nxt)
    return render_template('index.html', form=form, next=nxt)


@app.route('/search', methods=['GET','POST'])
@login_required
def auth_search_page():
    company = current_user.domain
    return search_page(company)


@app.route('/test-search/<company>', methods=['GET','POST'])
def search_page(company):
    feeders = get_company_feeders(company).values()
    feeder_names = [feeder['group'].partition('-')[2] for feeder in feeders]
    agents = [agent for feeder in feeders for agent in feeder['agent2data'].keys()]
    inputs = [inp for feeder in feeders for agent_data in feeder['agent2data'].values() for inp in agent_data['inputs']]
    inputs = uniq(inputs)
    job = None
    reqvalues = {k:v for k,v in request.values.items()} # how to translate to dict
    msg = reqvalues.get('msg')
    job = reqvalues.get('job')
    if msg:
        pass
    elif job:
        pass
    elif reqvalues:
        job = create_job()
        print(reqvalues)
        data = dict(action='find', job=job, data=dict(reqvalues))
        print('sending search:', data)
        send2company(company, data)
    return render_template('search.html', current_user=current_user, company=company, feeders=feeder_names, agents=agents, inputs=inputs, job=job, reqvalues=reqvalues, usrmsg=msg)


@app.route('/cleanse', methods=['POST'])
@login_required
def cleanse_page():
    company = current_user.domain
    return test_cleanse_page(company)


@app.route('/test-cleanse/<company>', methods=['POST'])
def test_cleanse_page(company):
    feeders = get_company_feeders(company).values()
    cleanses = [cleanse for feeder in feeders for agent_data in feeder['agent2data'].values() for cleanse in agent_data['cleanses']]
    reqvalues = {k:request.values[k] for k in cleanses}
    jobq = ''
    if 'job' in reqvalues:
        jobq = '?job=' + reqvalues['job']
    elif reqvalues:
        job = create_job()
        data = dict(action='cleanse', job=job, data=dict(reqvalues))
        send2company(company, data)
        jobq = '?job='+job
    return redirect('/search'+jobq)


@app.route('/api/job/<job>')
def get_job(job):
    result = dict(status='pending')
    if job in job2reply:
        websocket,reply = job2reply[job]
        prt('getting job reply:', reply)
        result = dict(reply)
        del result['action']
        del result['job']
        if request.values.get('dom') != None:
            del result['data']
            if reply['reference-action'] == 'find':
                agent_hits = reply['data']
                cleanses = {}
                allow_cleanse = True
                if websocket in websocket2feeder:
                    feeder_data = websocket2feeder[websocket]
                    feeder_datas = get_company_feeders(feeder_data['company']).values()
                    for feeder_data in feeder_datas:
                        for agent,init_data in feeder_data['agent2data'].items():
                            agent_hit_user = agent_hits[agent]['data']
                            allow_cleanse &= (len(agent_hit_user) == 1)
                            for user in agent_hit_user:
                                cleanses.update({k:user[k] for k in init_data['cleanses'] if k in user})
                if not cleanses:
                    allow_cleanse = False
                result['dom'] = render_template('search-result.html', agents_hits=agent_hits, cleanses=cleanses, allow_cleanse=allow_cleanse)
            else:
                line_cnt = 0
                for agent, agent_data in reply['data'].items():
                    if agent_data['status'] == 'ok':
                        line_cnt += agent_data['data']['lines']
                result['dom'] = render_template('cleanse-result.html', line_cnt=line_cnt)
    return jsonify(result)


@app.route('/favicon.ico')
def favicon():
    return send_from_directory('static', 'favicon.ico', mimetype='image/x-icon')


def login(company, username, password):
    job = create_job()
    data = dict(action='login', job=job, domain=company, username=username, password=password)
    if send2company(company, data):
        for _ in range(100):
            time.sleep(0.1)
            if job in job2reply:
                _,reply = job2reply[job]
                fullname,groups = reply['fullname'], reply['groups']
                del job2reply[job]
                return fullname, groups
    return None, None


def create_job():
    return str(uuid.uuid4())


def send2company(company, data):
    websockets = get_company_feeders(company).keys()
    for websocket in websockets:
        send2feeder(websocket, data)
    return len(websockets)


def get_company_feeders(company):
    return {w:fd for w,fd in websocket2feeder.items() if fd['company']==company}


def send2feeder(websocket, obj):
    prt('sending to feeder:', obj)
    data = json.dumps(obj)
    main_event_loop.call_soon_threadsafe(lambda: asyncio.ensure_future(websocket.send(data)))


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
        agent_data = dict(inputs=data['inputs'], cleanses=data['cleanses'], outputs=data['outputs'])
        websocket2feeder[websocket]['agent2data'][agent] = agent_data
        return dict(status='ok')
    elif action == 'remove-agent':
        agent = data['agent']
        agent2data = websocket2feeder[websocket]['agent2data']
        if agent in agent2data:
            del agent2data[agent]
        return dict(status='ok')
    elif action == 'reply':
        prt('GOT REPLY:', action, data)
        job = data['job']
        job2reply[job] = (websocket,data)
        return dict(status='ok')
    else:
        prt('BAD DATA FROM FEEDER:', action, data)
        return dict(status='error')


async def handle(websocket, path):
    try:
        async for message in websocket:
            data = json.loads(message)
            prt('data from feeder:', data)
            action = data['action']
            r = handle_action(websocket, action, data)
            if action != 'reply':
                r['action'] = 'reply'
                r['reference-action'] = action
                await websocket.send(json.dumps(r))
    except Exception as e:
        prt(type(e), e)
    finally:
        if websocket in websocket2feeder:
            del websocket2feeder[websocket]


def run_websocket():
    global main_event_loop
    main_event_loop = asyncio.get_event_loop()
    main_event_loop.run_until_complete(
        websockets.serve(handle, '0.0.0.0', 5001))
    main_event_loop.run_forever()


def run():
    Thread(target=app.run, kwargs=dict(host='0.0.0.0', port=5000, threaded=True)).start()
    run_websocket()


if __name__ == '__main__':
    run()
