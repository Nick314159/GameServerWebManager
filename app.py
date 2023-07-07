from time import sleep
from flask import request
from flask import Flask, render_template, redirect, url_for
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask_bootstrap import Bootstrap
import subprocess
import os

app = Flask("BlackSquadronGamingServerManager")
app.secret_key = os.environ.get('FLASK_SECRET_KEY')
Bootstrap(app)

servers = [
    {'name': 'Arma3', 'start': '/home/game/Arma3Server/startServer.sh', 'screen': 'arma3', 'status': 'unknown'},
    {'name': 'Squad', 'start': 'home/game/SquadServer/startServer.sh', 'screen': 'squad', 'status': 'unknown'},
    {'name': 'test', 'start': './test.sh', 'screen': 'test', 'status': 'unknown'},
    {'name': 'Wreckfest', 'start': 'home/game/WreckfestServer/startServer.sh', 'screen': 'wreckfest','status': 'unknown'}
]


# Setup Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'  # Name of the login view

# Mock user
class User(UserMixin):
    def __init__(self, id):
        self.id = id

# This is where you'd usually use a database,
# but we'll use a dict to keep it simple
users = {'admin': {'password': 'securepassword'}}

# Tell flask-login how to load a user
@login_manager.user_loader
def load_user(user_id):
    return User(user_id)

@app.route('/')
@login_required
def index():
    return render_template('index.html', servers=servers)

@app.route('/start/<name>')
@login_required
def start(name):
    server = next((s for s in servers if s['name'] == name), None)
    checkStatus(name)
    if server['status'] == "online":
        return f"Server {name} is already online"
    if server:
        subprocess.run(['screen', '-dmS', server['screen']])
        sleep(1)
        subprocess.run(['screen', '-S', server['screen'], '-X', 'stuff', server['start']+'\n'])
        # subprocess.run(['bash', server['start']])

@app.route('/stop/<name>')
@login_required
def stop(name):
    #@TODO @BUG when the button is pushed on webpage, this call is excuted twice, reason unknown.
    server = next((s for s in servers if s['name'] == name), None)
    checkStatus(name)
    if server['status'] == "offline":
        return f"Server {name} is already offline"
    if server:
        subprocess.run(['screen', '-S', server['screen'], '-X', 'stuff', '^C'])
        # sleep(5)  # Give the server some time to properly shut down
        subprocess.run(['screen', '-S', server['screen'], '-X', 'quit'])
        return redirect(url_for('index'))


@app.route('/restart/<name>')
@login_required
def restart(name):
    server = next((s for s in servers if s['name'] == name), None)
    checkStatus(server)
    if server['status'] == "online":
        stop(name)
    sleep(3)
    if server['status'] == "offline":
        start(name)


@app.route('/check/<name>')
@login_required
def checkStatus(name):
    server = next((s for s in servers if s['name'] == name), None)
    if server:
        result = subprocess.run(['screen', '-ls'], stdout=subprocess.PIPE)
        output = result.stdout.decode()
        if output.startswith('No Sockets'):
            server['status'] = "offline"
            return "offline"
        if server['screen'] in output:
            server['status'] = "online"
            return "online"
        else:
            server['status'] = "offline"
            return "offline"
    else:
        return f"No server found with the name {name}"

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        if (username in users) and (password == users[username]['password']):
            user = User(username)
            login_user(user)
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


