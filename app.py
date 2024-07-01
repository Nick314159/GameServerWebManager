from time import sleep
from flask import Flask, render_template, redirect, url_for, request,send_from_directory
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask_bootstrap import Bootstrap
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_wtf import FlaskForm
from wtforms import StringField
from wtforms.validators import DataRequired
import bleach
import subprocess
import bcrypt
import os
import json
import logging

app = Flask("BlackSquadronGamingServerManager")
app.secret_key = os.environ.get('FLASK_SECRET_KEY')

logging.basicConfig(filename='app.log', level=logging.INFO,
                        format='%(asctime)s %(levelname)s: %(message)s',
                        datefmt='%Y-%m-%d %H:%M:%S')

Bootstrap(app)



logging.info('Starting the application')
logging.warning('This is a warning message')
logging.error('This is an error message')

limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["200 per day", "50 per hour"],
    storage_uri="memory://",
)

class ServerController:
    def __init__(self, server):
        self.server = server

    def start(self):
        if self.check_status() == "online":
            return f"Server {self.server['name']} is already online"
        logging.info('Starting ' +self.server['screen'])
        logging.info('Starting screen session for ' +self.server['screen'])
        subprocess.run(['/usr/bin/screen', '-dmS', self.server['screen']])
        sleep(1)
        logging.info('Starting game server for ' +self.server['screen'])
        subprocess.run(['/usr/bin/screen', '-S', self.server['screen'], '-X', 'stuff', self.server['start'] + '\n'])

    def stop(self):
        if self.check_status() == "offline":
            return f"Server {self.server['name']} is already offline"

        logging.info('Stopping ' +self.server['screen'])

        # List all screen sessions
        result = subprocess.run(['/usr/bin/screen', '-ls'], stdout=subprocess.PIPE, text=True)
        output = result.stdout

        # Find sessions that match the server's screen name pattern
        pattern = self.server['screen']
        matching_sessions = [line.split()[0] for line in output.splitlines() if pattern in line]
        logging.info('Found '+str(len(matching_sessions))+" session(s) for " +self.server['screen'])


        for session in matching_sessions:
            logging.info('Stopping game server for ' + session)
            if self.server['stop'] == "":
                subprocess.run(['/usr/bin/screen', '-S', session, '-X', 'stuff', '^C^C^C'])
            else:
                subprocess.run(['/usr/bin/screen', '-S', session, '-X', 'stuff', self.server['stop'] + '\n'])
            sleep(15) #Some games take a while to shut down properly.
            logging.info('Stopping screen session for ' + session)
            subprocess.run(['/usr/bin/screen', '-S', session, '-X', 'quit'])

    def restart(self):
        logging.info('Restarting server for ' + self.server['screen'])
        if self.check_status() == "online":
            self.stop()
        sleep(3)
        if self.check_status() == "offline":
            self.start()

    def save(self):
        logging.info('Backing up ' +self.server['name'] + '...')
        subprocess.run([self.server['save']])
        logging.info(self.server['name'] + ' backup complete.')


    def check_status(self):
        result = subprocess.run(['/usr/bin/screen', '-ls'], stdout=subprocess.PIPE)
        output = result.stdout.decode()
        if output.startswith('No Sockets') or self.server['screen'] not in output:
            return "offline"
        else:
            return "online"

    def to_dict(self):
        return self.server


# Load server data from a JSON file
with open('config.json', 'r') as file:
    config = json.load(file)

server_controllers = {s['name']: ServerController(s) for s in config['servers']}
servers = [controller.to_dict() for controller in server_controllers.values()]

# Setup Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

class LoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    password = StringField('Password', validators=[DataRequired()])

# Mock user
class User(UserMixin):
    def __init__(self, id):
        self.id = id

users = {user['username']: user['password'] for user in config['users']}


@app.route('/favicon.ico')
def favicon():
    return send_from_directory(os.path.join(app.root_path, 'static/images'), 'favicon.ico', mimetype='image/vnd.microsoft.icon')


# Tell flask-login how to load a user
@login_manager.user_loader
def load_user(user_id):
    return User(user_id)


@app.route('/login', methods=['GET', 'POST'])
@limiter.limit("5/minute")
def login():
    if request.method == 'POST':
        form = LoginForm()
        username = form.username.data
        password = form.password.data
        user = next((user for user in config['users'] if user['username'] == username), None)
        if user and bcrypt.checkpw(password.encode('utf-8'), user['password'].encode('utf-8')):
            user_obj = User(username)
            login_user(user_obj)
            return redirect(url_for('index'))
        else:
            return "Invalid credentials", 401
    else:
        return render_template('login.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))


@app.route('/')
@app.route('/dashboard')
def index():
    user_agent = request.headers.get('User-Agent')
    is_mobile = 'Mobile' in user_agent
    return render_template('index.html', servers=servers, is_mobile=is_mobile)

@app.route('/start/<name>')
@limiter.limit("1/second")
def start(name):
    name = bleach.clean(name)
    if current_user.is_authenticated:
        name = name.replace('_', ' ')
        controller = server_controllers.get(name)
        if controller:
            controller.start()
            return f"Server {name} started succefully", 200
        else:
            return f"No server found with the name {name}", 404
    else:
        return "Unauthorized", 401

@app.route('/stop/<name>')
def stop(name):
    name = bleach.clean(name)
    if current_user.is_authenticated:
        name = name.replace('_', ' ')
        controller = server_controllers.get(name)
        if controller:
            controller.stop()
            return f"Server {name} stopped succefully", 200
        else:
            return f"No server found with the name {name}", 404
    else:
        return "Unauthorized", 401

@app.route('/restart/<name>')
def restart(name):
    name = bleach.clean(name)
    if current_user.is_authenticated:
        name = name.replace('_', ' ')
        controller = server_controllers.get(name)
        if controller:
            controller.restart()
            return f"Server {name} restarted succefully", 200
        else:
            return f"No server found with the name {name}", 404
    else:
        return "Unauthorized", 401

@app.route('/save/<name>')
@limiter.limit("1/second")
def save(name):
    name = bleach.clean(name)
    if current_user.is_authenticated:
        name = name.replace('_', ' ')
        controller = server_controllers.get(name)
        if controller:
            controller.save()
            return f"Server {name} saved succefully", 200
        else:
            return f"No server found with the name {name}", 404
    else:
        return "Unauthorized", 401

@app.route('/check/<name>')
@limiter.limit("1000/minute")
def checkStatus(name):
    name = bleach.clean(name)
    name = name.replace('_', ' ')
    controller = server_controllers.get(name)
    return controller.check_status() if controller else f"No server found with the name {name}"