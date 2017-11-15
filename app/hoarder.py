#!/usr/bin/env python3

import asyncio
from flask import Flask, jsonify, redirect, render_template, request, send_from_directory
from wtforms import Form, PasswordField, StringField, validators
from flask_login import current_user, login_required, login_user, LoginManager, AnonymousUserMixin, UserMixin
import hashlib
import json
import ldap_login
from threading import Thread
import websockets


app = Flask(__name__)
app.secret_key = 'non-secret'
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = '/'
tokens = {'hm': '441234567890=='}
websocket2feeder = {}
jobindex = 1
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
    form = LoginForm(request.form)
    if request.method == 'POST' and form.validate():
        username = form.username.data
        password = form.password.data
        domain = username.partition('@')[2].split('.')[-2]
        fullname, groups = ldap_login.login(domain, username, password)
        user = load_user(username)
        user.domain = domain
        user.username = username
        login_user(user)
        print('Logged in successfully.')
        return redirect('/search')
    return render_template('index.html', form=form)


@app.route('/search', methods=['GET','POST'])
@app.route('/search/<department>', methods=['GET','POST'])
@app.route('/search/<department>/<group>', methods=['GET','POST'])
@login_required
def search_page(department='', group=''):
    company = current_user.domain
    feeders = [values for values in websocket2feeder.values() if values['company'] == company]
    feeder_names = [feeder['group'].partition('-')[2] for feeder in feeders]
    agents = [agent for feeder in feeders for agent in feeder['agent2data'].keys()]
    inputs = [inp for feeder in feeders for agent_data in feeder['agent2data'].values() for inp in agent_data['inputs']]
    inputs = set(inputs)
    values = {k:v for k,v in request.values.items()}
    job = None
    if values:
        global jobindex
        job = jobid(jobindex)
        jobindex += 1
        job2reply[job] = {}
        for websocket, feeder_data in websocket2feeder.items():
            if feeder_data['company'] == company:
                send2feeder(websocket, dict(action='find', job=job, data=dict(values)))
    return render_template('search.html', company=company, department=department, group=group, feeders=feeder_names, agents=agents, inputs=inputs, job=job)


@app.route('/api/job/<job>')
def get_job(job):
    if job in job2reply:
        reply = job2reply[job]
        print('getting job reply:', reply)
        result = dict(reply)
        del result['action']
        del result['job']
        if request.values.get('dom') != None:
            del result['data']
            result['dom'] = render_template('result.html', agents_data=reply['data'])
        return jsonify(result)


@app.route('/favicon.ico')
def favicon():
    return send_from_directory('static', 'favicon.ico', mimetype='image/x-icon')


def jobid(idx):
    return hashlib.md5(('whoot'+str(idx)+'?! 98732').encode()).hexdigest()[5:16]


def send2feeder(websocket, obj):
    data = json.dumps(obj)
    print('sending to feeder:', data)
    main_event_loop.call_soon_threadsafe(lambda: asyncio.ensure_future(websocket.send(data)))


def present_result(job, reply):
    job2reply[job] = reply


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
        print('GOT REPLY:', action, data)
        job = data['job']
        present_result(job, data)
        return dict(status='ok')


async def handle(websocket, path):
    try:
        async for message in websocket:
            data = json.loads(message)
            print('data from feeder:', data)
            action = data['action']
            r = handle_action(websocket, action, data)
            if action != 'reply':
                r['action'] = 'reply'
                r['reference-action'] = action
                await websocket.send(json.dumps(r))
    except Exception as e:
        print(e)
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
