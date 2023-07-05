from flask import Flask, render_template, redirect, url_for
from flask_bootstrap import Bootstrap
import subprocess

app = Flask("BlackSquadronGamingServerManager")
Bootstrap(app)

servers = [
    {'name': 'Arma3', 'start': '/home/game/Arma3Server/startServer.sh', 'screen': 'arma3', 'status': 'unknown'},
    {'name': 'Squad', 'start': 'home/game/SquadServer/startServer.sh', 'screen': 'squad', 'status': 'unknown'},
    {'name': 'Wreckfest', 'start': 'home/game/WreckfestServer/startServer.sh', 'screen': 'wreckfest','status': 'unknown'}
]

@app.route('/')
def index():
    return render_template('index.html', servers=servers)

@app.route('/start/<name>')
def start(name):
    server = next((s for s in servers if s['name'] == name), None)
    if server:
        subprocess.run(['bash', server['start']])
    return redirect(url_for('index'))

@app.route('/check/<name>')
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

