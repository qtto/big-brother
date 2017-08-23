import discord
import asyncio
from os import path
from configparser import ConfigParser
from time import time
from datetime import datetime, timedelta
from calendar import monthrange
from sqlalchemy import create_engine, func
from sqlalchemy.orm import sessionmaker
from sql_declaration import Log, Base
from plot import create_graph, date_to_unix
from collections import deque

# Read config file
def read_config():
    config = ConfigParser()
    config_file = path.join(path.dirname(__file__), 'config.ini')
    config.read(config_file)
    return config['main']

config_main = read_config()
TOKEN = config_main['token']
ONLINE = config_main['onlinetext']
GAME = config_main['gamename']
OWNERID = config_main['owner']
CMD_PREFIX = config_main['cmd_prefix']
MAX_OFFSET = 50  # Maximum offset an insert in db can have compared to INTERVAL
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


# Calculates a date relative to the current, with a given offset of x hours / days / weeks / months / years
def relative_date(type, amount):
    now = datetime.now()

    if type == 'hour':
        date = now - timedelta(hours=amount)
        return date_to_unix(date.hour, date.day, date.month, date.year)

    if type == 'day':
        date = now - timedelta(days=amount)
        return date_to_unix(0, date.day, date.month, date.year)

    if type == 'week':
        date = now - timedelta(days=now.isoweekday() % 7 + (7*amount))
        return date_to_unix(0, date.day, date.month, date.year)

    if type == 'month':
        month = (now.month - amount) % 12 or 12 # if it's 0 make it 12
        year = now.year - ((month > now.month) + (amount // 12)) # boolean for overflow into last year
        return date_to_unix(0, 1, month, year)

    if type == 'year':
        return date_to_unix(0, 1, 1, (now.year - amount))


def handle_message(message):
    """Handle incoming messages"""
    if message.content.startswith(CMD_PREFIX):
        command, *params = message.content.split(' ', 1)
        factory = CommandFactory()
        command = factory.create_command(command, *params)
        print(command.execute())
    else:
        pass


def getopts(message, author, cmd_prefix='$'):
    if message.startswith(cmd_prefix):
        command, *params = message.split(' ', 1)
        params = deque(params.split(' '))
        parsed = dict()
        parsed["__command_prefix"] = command[0]
        parsed["__command"] = command[1:]
        parsed["__author"] = author
        print(params)
        is_kwarg = False
        while params:
            param = params.popleft()
            if param.startswith('--') and is_kwarg:
                # error: expecting value.
                return f'error while parsing {message}, impossible syntax while parsing {param} - nesting detected on {pname}.'
            elif param.startswith('--') and not is_kwarg:
                if param[2:].startswith('__'):
                    return f'error while parsing keyword argument {param[2:]}: cannot start with __ (internal usage)'
                is_kwarg = True
                pname = param[2:]
                continue
            elif param.startswith('-'):
                parsed[param[1:]] = True  # flag value
                continue
            elif is_kwarg:
                parsed[pname] = param
                is_kwarg = False
            else:
                try:
                    parsed["positional"].append(param)
                except KeyError:
                    parsed["positional"] = []
                    parsed["positional"].append(param)
        return parsed
    else:
        x = dict()
        x['_command'] = None
        x['message'] = f'{author}: {message}'
        return x


def parse_msg(message):
    """Parse the requested time from a message."""
    values = {'hour': 1, 'day': 24, 'week': 24*7,  
              'month': 24 * 31, 'year': 24*365} # hours in an X

    if message[0] == 'today':
        return [int(relative_date('day', 0)), 24]

    if message[0] == 'yesterday':
        return [int(relative_date('day', 1)), 24]

    # This hour/day/week/month/year...
    if message[0] == 'this' and message[1] in values: 
        return [int(relative_date(message[1], 0)), values[message[1]]]

    # Last hour/day/week/month/year...
    if message[0] == 'last': # last week, last month
        if message[1] in values:
            if message[1] == 'month': # looks bad, but is necessary
                now = datetime.now()
                month = (now.month - 1) % 12 or 12 
                year = now.year - (now.month == 12) # substract year if it's january right now
                hours_in_month = 24 * monthrange(year, month)[1]
                return [int(relative_date('month', 1)), hours_in_month]
            return [int(relative_date(message[1], 1)), values[message[1]]]

        elif message[2][:-1] in values: # last 91 days, last 2 months
            try:
                value = values[message[2][:-1]] # hour(-s), day(-s)...
                number = int(message[1]) 
                ''' the 900 at the end of return is because weeks / months introduce an offset
                 since they start from sunday / 1st of the month. This can cause it to not check
                 up until the current date, which we do want. Use hours in a month, it
                 can't overflow anyways '''
                return [int(relative_date(message[2][:-1], number)), int(number * value + values['month'])]
            except:
                return False

    # No keywords: check if a specific date / length was given
    try:
        args = message[0].split('/')
        day = int(args[0])
        month = int(args[1])
        year = int(args[2])
        return [int(date_to_unix(0, day, month, year)), int(24 * message[1])]
    except:
        return False


def get_admins():
    """Fetch admin list and check current states"""
    members = client.get_all_members()
    timestamp = time()
    admins = [user for user in members if 'Staff' in [role.name for role in user.roles]]
    admins = [Admin_state(user, timestamp) for user in admins]
    return admins


def insert_state(admins):
    """Add admin states to db"""
    for admin in admins:
        entry = Log(timestamp = admin.timestamp,
                       userid = admin.id,
                       online = admin.online,
                       ingame = admin.ingame)
        session.add(entry)

    session.commit()
    print('> Inserted into DB.')


async def add_states():
    """Add states to db as bg task"""
    await client.wait_until_ready()
    while not client.is_closed:
        last_insert = session.query(func.max(Log.timestamp)).first()[0]
        last_insert = int(last_insert) if last_insert is not None else 0

        # Don't insert next entry too early (e.g. when script restarts)
        if time() - INTERVAL >= last_insert - MAX_OFFSET:
            admins = get_admins()
            insert_state(admins)
            await asyncio.sleep(INTERVAL)
        else:
            print(f'> Too early to insert. Waiting {int(last_insert - time() + INTERVAL)} seconds.')
            await asyncio.sleep(last_insert - time() + INTERVAL)


def get_entries():
    ids = session.query(Log).distinct(Log.userid).group_by(Log.userid).count()
    timestamps = session.query(Log).distinct(Log.timestamp).group_by(Log.timestamp).count()
    count = session.query(Log).count()

    return f'There are a total of {count} entries about {ids} unique ID\'s over {timestamps} timestamps. Currently ' \
           f'checking every {INTERVAL} seconds. '


@client.event
async def on_message(message):
    """Message actions"""
    print(message)
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

    if message.content.startswith('$plotperson '):
        person, *no_prefix = message.content.split(' ')[1:]
        plot = parse_msg(no_prefix)
        if not plot:
            msg = 'Sorry: please enter your arguments as `dd/mm/yyyy length`, `last / this hour/day/month/year` or `last x hours/././.`.'
            await client.send_message(message.channel, msg)
        else:
            if create_graph(plot[0], plot[1], '', person):
                await client.send_file(message.channel, 'plot.png')
            else:
                await client.send_message(message.channel, 'No data to plot for that period.')

    if message.content.startswith('$myid'):
        await client.send_message(message.channel, "Your ID is " + message.author.id)

    if message.content.startswith('$plot '):
        no_prefix = message.content.split(' ')[1:]
        plot = parse_msg(no_prefix)
        if not plot:
            msg = 'Sorry: please enter your arguments as `dd/mm/yyyy length`, `last / this hour/day/month/year` or `last x hours/././.`.'
            await client.send_message(message.channel, msg)
        else: 
            if create_graph(plot[0], plot[1], ''):
                await client.send_file(message.channel, 'plot.png')
            else:
                await client.send_message(message.channel, 'No data to plot for that period.')


@client.event
async def on_ready():
    """Login when ready."""
    length = len('# logged in as  #') + len(client.user.name)
    print(length * '#')
    print(f'# Logged in as {client.user.name} #')
    print(length * '#')


if __name__ == '__main__':
    client.loop.create_task(add_states())
    client.run(TOKEN)