import discord
import asyncio
from configparser import ConfigParser
from time import time
from sqlalchemy import create_engine, func
from sqlalchemy.orm import sessionmaker
from sql_declaration import Log, Base

# Read config file
def read_config():
    config = ConfigParser()
    config.read('config.ini')
    return config['main']

config_main = read_config()
TOKEN = config_main['token']
ONLINE = config_main['onlinetext']
GAME = config_main['gamename']
OWNERID = config_main['owner']
MAX_OFFSET = 50 # Maximum offset an insert in db can have compared to INTERVAL
try:
    INTERVAL = int(config_main['interval'])
except TypeError:
    print('Enter an interval in seconds.')
    exit()

# Create db session
engine = create_engine('sqlite:///admin_log.db')
Base.metadata.bind = engine
DBSession = sessionmaker(bind=engine)
session = DBSession()

# Create discord client
client = discord.Client()

# Current state per admin
class Admin_state:
    def __init__(self, user, timestamp):
        self.name = user.name
        self.id = user.id
        self.online = str(user.status) == ONLINE
        self.ingame = GAME.lower() in str(user.game).lower()
        self.timestamp = timestamp

    def __repr__(self):
        return self.name

# Fetch admin list and check current states
def get_admins():
    members = client.get_all_members()
    timestamp = time()
    admins = [user for user in members if 'Staff' in [role.name for role in user.roles]]
    admins = [Admin_state(user, timestamp) for user in admins]
    return admins

# Aadd admin states to db
def insert_state(admins):
    for admin in admins:
        entry = Log(timestamp = admin.timestamp,
                       userid = admin.id,
                       online = admin.online,
                       ingame = admin.ingame)
        session.add(entry)

    session.commit()
    print('> Inserted into DB.')

# Add states to db as bg task
async def add_states():
    await client.wait_until_ready()
    while not client.is_closed:
        last_insert = int(session.query(func.max(Log.timestamp)).first()[0])
        if time() - INTERVAL >= last_insert - MAX_OFFSET: # Don't insert next entry too early (e.g. when script restarts)
            admins = get_admins()
            insert_state(admins)
            await asyncio.sleep(INTERVAL)
        else:
            print(f'> Too early to insert. Waiting {int(last_insert - time() + INTERVAL)} seconds.')
            await asyncio.sleep(last_insert - time() + INTERVAL)

# List db on message
@client.event
async def on_message(message):
    if message.author == client.user:
        return

    def check_owner(message):
        return str(message.author.id) == str(OWNERID)

    if message.content.startswith('$entries'):
        ids = session.query(Log).distinct(Log.userid).group_by(Log.userid).count()
        timestamps = session.query(Log).distinct(Log.timestamp).group_by(Log.timestamp).count()
        count = session.query(Log).count()

        msg = f'There are a total of {count} entries about {ids} unique ID\'s over {timestamps} timestamps. Currently ' \
              f'checking every {INTERVAL} seconds. '
        await client.send_message(message.channel, msg)

    if message.content.startswith('$insert') and check_owner(message):
        admins = get_admins()
        insert_state(admins)
        await client.send_message(message.channel, 'Inserted current state.')

    if message.content.startswith('$cleardb') and check_owner(message):
        await client.send_message(message.channel, 'This will delete all saved records. Are you sure?')

        confirmation = await client.wait_for_message(timeout=10.0, author=message.author)

        if confirmation.content == 'yes':
            session.query(Log).delete()
            print('> Clearing DB.')
            await client.send_message(message.channel, 'Deleted all records.')
        else:
            await client.send_message(message.channel, 'No records deleted.')

# Log in
@client.event
async def on_ready():
    length = len('# logged in as  #') + len(client.user.name)
    print(length * '#')
    print(f'# Logged in as {client.user.name} #')
    print(length * '#')


if __name__ == '__main__':
    client.loop.create_task(add_states())
    client.run(TOKEN)