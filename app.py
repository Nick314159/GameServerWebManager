from time import sleep
from flask import request
from flask import Flask, render_template, redirect, url_for
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask_bootstrap import Bootstrap
import subprocess
import bcrypt
import os
import json

app = Flask("BlackSquadronGamingServerManager")
app.secret_key = os.environ.get('FLASK_SECRET_KEY')
Bootstrap(app)


# servers = [
#     {'name': 'Arma3', 'start': '/home/game/Arma3Server/startServer.sh', 'screen': 'arma3', 'status': 'unknown'},
#     {'name': 'Squad', 'start': 'home/game/SquadServer/startServer.sh', 'screen': 'squad', 'status': 'unknown'},
#     {'name': 'test', 'start': './test.sh', 'screen': 'test', 'status': 'unknown'},
#     {'name': 'Wreckfest', 'start': 'home/game/WreckfestServer/startServer.sh', 'screen': 'wreckfest','status': 'unknown'}
# ]
class ServerController:
    def __init__(self, server):
        self.server = server

    def start(self):
        if self.check_status() == "online":
            return f"Server {self.server['name']} is already online"
        subprocess.run(['/usr/bin/screen', '-dmS', self.server['screen']])
        sleep(1)
        subprocess.run(['/usr/bin/screen', '-S', self.server['screen'], '-X', 'stuff', self.server['start'] + '\n'])

    def stop(self):
        if self.check_status() == "offline":
            return f"Server {self.server['name']} is already offline"
        if self.server['stop'] == "":
            subprocess.run(['/usr/bin/screen', '-S', self.server['screen'], '-X', 'stuff', '^C'])
        else:
            subprocess.run(['/usr/bin/screen', '-S', self.server['screen'], '-X', 'stuff', self.server['stop'] + '\n'])
        sleep(15) #Some games take a while to shut down properly.
        subprocess.run(['/usr/bin/screen', '-S', self.server['screen'], '-X', 'quit'])

    def restart(self):
        if self.check_status() == "online":
            self.stop()
        sleep(3)
        if self.check_status() == "offline":
            self.start()

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
login_manager.login_view = 'login'  # Name of the login view

# Mock user
class User(UserMixin):
    def __init__(self, id):
        self.id = id

users = {user['username']: user['password'] for user in config['users']}


# Tell flask-login how to load a user
@login_manager.user_loader
def load_user(user_id):
    return User(user_id)


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
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
@login_required
def index():
    return render_template('index.html', servers=servers)


@app.route('/start/<name>')
@login_required
def start(name):
    controller = server_controllers.get(name)
    if controller:
        controller.start()


@app.route('/stop/<name>')
@login_required
def stop(name):
    controller = server_controllers.get(name)
    if controller:
        controller.stop()


@app.route('/restart/<name>')
@login_required
def restart(name):
    controller = server_controllers.get(name)
    if controller:
        controller.restart()

@app.route('/check/<name>')
@login_required
def checkStatus(name):
    controller = server_controllers.get(name)
    return controller.check_status() if controller else f"No server found with the name {name}"
