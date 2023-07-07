import json
import bcrypt
import getpass

username = input("Enter username: ")
password = getpass.getpass("Enter password: ")

hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

with open('config.json', 'r') as file:
    config = json.load(file)

if 'users' not in config:
    config['users'] = []

config['users'].append({'username': username, 'password': hashed_password})

with open('config.json', 'w') as file:
    json.dump(config, file)
