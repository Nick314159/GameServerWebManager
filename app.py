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
import datetime

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
        subprocess.run(['/usr/bin/screen', '-dmS', self.server['screen']]) #The -m forces the creation of a new session, but if its already online, how did it get to this point. Also, it must be calling this method twice from higher up, why??
        sleep(1)
        logging.info('Starting game server for ' +self.server['screen'])
        subprocess.run(['/usr/bin/screen', '-S', self.server['screen'], '-X', 'stuff', self.server['start'] + '\n'])

        #This is a workaround to the app starting multiple screen sessions, I cannot identify why it is doing that, so unfornuatly im stuck with this recursive call. 
        sleep(1)
        while self.check_for_duplicate_screens():
            self.stop()
            sleep(1)
            self.start()

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
        
    def check_for_duplicate_screens(self):
        result = subprocess.run(['/usr/bin/screen', '-ls'], stdout=subprocess.PIPE)
        output = result.stdout.decode()
        lines = output.splitlines()
    
        # Find lines that contain the session name
        matching_sessions = [line for line in lines if self.server['screen'] in line]
        
        return True if len(matching_sessions) > 1 else False

    def get_last_save_timestamp(self):
        #This expect the backup.tar.gz to be alongside the backup.sh from the save parameter in config, will need to make another config parameter if these are to be sepeerate.
        save_file = self.server['save'].replace('.sh', '.tar.gz')
        if os.path.exists(save_file):
            return os.path.getmtime(save_file)
        return None

    def to_dict(self):
        server_dict = self.server.copy()
        server_dict['last_saved'] = self.get_last_save_timestamp()
        return server_dict

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
    
@app.route('/last_saved/<name>')
@limiter.limit("1/second")
def last_saved(name):
    name = bleach.clean(name)
    name = name.replace('_', ' ')
    controller = server_controllers.get(name)
    if controller:
        timestamp = controller.get_last_save_timestamp()
        if timestamp:
            formatted_date = datetimeformat(timestamp)
            return {"formatted_date": formatted_date}, 200
        else:
            return {"error": "No backup found"}, 404
    else:
        return {"error": "No server found with the name " + name}, 404

@app.template_filter('format_datetime')
def datetimeformat(value, format='%Y-%m-%d %H:%M:%S'):
    """Format a date time to (Default): yyyy-mm-dd H:M:S"""
    # return datetime.datetime.fromtimestamp(value).strftime(format)
    date = datetime.datetime.fromtimestamp(value)
    suffix = 'th' if 11 <= date.day <= 13 else {1: 'st', 2: 'nd', 3: 'rd'}.get(date.day % 10, 'th')
    return date.strftime(f'%a %B {date.day}{suffix}, %I:%M %p')

@app.route('/check/<name>')
@limiter.limit("1000/minute")
def checkStatus(name):
    name = bleach.clean(name)
    name = name.replace('_', ' ')
    controller = server_controllers.get(name)
    return controller.check_status() if controller else f"No server found with the name {name}"

