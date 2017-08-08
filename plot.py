import pandas as pd
from time import time, mktime
from datetime import date
from sqlalchemy import create_engine, func, select as sqlselect, between
from sqlalchemy.orm import sessionmaker
from sql_declaration import Log, Base

import matplotlib.pyplot as plt



# Create db session
engine = create_engine('sqlite:///admin_log.db')
Base.metadata.bind = engine
DBSession = sessionmaker(bind=engine)
session = DBSession()


def date_to_unix(day, month, year): 
	d = date(year, month, day)
	unix_time = mktime(d.timetuple())
	return unix_time


def calculate_end(begin, length): # length in days
	end = begin + (length * 24 * 60 * 60)
	return end


def select_data(begin, end):
	expression = sqlselect([Log]).where(between(Log.timestamp, begin, end))
	data = pd.read_sql(expression, engine)
	return data


def create_graph(begin, length, graphtype):
	end = calculate_end(begin, length)
	data = select_data(begin, end)

	data = data[['timestamp', 'ingame']]
	data['timestamp'] = pd.to_datetime(data.timestamp, unit='s')

	data = data.groupby('timestamp').sum().reset_index()
	data['ingame'] = data['ingame'].astype(int)
	
	data.plot(x='timestamp', y='ingame')
	plt.ylim(ymin=0)
	plt.savefig('plot.png', bbox_inches='tight')


def main():
	print("Start date:")
	day = int(input("DD > "))
	month = int(input("MM > "))
	year = int(input("YY > "))
	begin = date_to_unix(day, month, year)
	length = int(input("Length (days) > "))
	graphtype = input("Type of graph > ")
	create_graph(begin, length, graphtype)


if __name__ == '__main__':
	main()