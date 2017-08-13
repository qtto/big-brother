import pandas as pd
import matplotlib as mpl
mpl.use('Agg') # drop tkinter dependecy
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import matplotlib.dates as dates
from time import time, mktime
from datetime import datetime
from sqlalchemy import create_engine, select as sqlselect, between
from sqlalchemy.orm import sessionmaker
from sql_declaration import Log, Base

# Create db session
engine = create_engine('sqlite:///admin_log.db')
Base.metadata.bind = engine
DBSession = sessionmaker(bind=engine)
session = DBSession()


def date_to_unix(hour, day, month, year): 
	d = datetime(year, month, day, hour)
	unix_time = mktime(d.timetuple())
	return unix_time


def calculate_end(begin, length): # length in hours
	end = begin + (length * 60 * 60)
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

	try:
		plt.figure()
		data.plot(x='timestamp', y='ingame', drawstyle="steps", color = 'r', legend=False)
	except TypeError:
		return False # probably no data to plot

	ax = plt.gca()
	ax.yaxis.grid(which="major", color='#dddddd', linestyle='--', linewidth=1) # horizontal gridlines
	ax.yaxis.set_major_locator(ticker.MaxNLocator(integer=True)) # show y axis as ints
	ax.spines['top'].set_visible(False) # remove top frame
	ax.spines['right'].set_visible(False) #remove right frame

	# time formatting
	xtick_locator = dates.AutoDateLocator()
	xtick_formatter = dates.AutoDateFormatter(xtick_locator)

	ax.xaxis.set_major_locator(xtick_locator)
	ax.xaxis.set_major_formatter(xtick_formatter)

	xax = ax.get_xaxis() # get the x-axis
	adf = xax.get_major_formatter() # the the auto-formatter

	adf.scaled[1/(24.*60.)] = '%H:%M'  # set the < 1d scale 
	adf.scaled[1./24] = '%d/%m %H:%M'  # set the > 1d  < 1m scale 
	adf.scaled[1.0] = '%Y-%m-%d' # set the > 1dm < 1y scale
	adf.scaled[30.] = '%Y-%m' # set the > 1Y scale
	adf.scaled[365.] = '%Y'


	begin = data['timestamp'].iloc[0].strftime("%H:%M, %B %d %Y") # formatted starting date
	end = data['timestamp'].iloc[-1].strftime("%H:%M, %B %d %Y") # formatted ending date
	plt.title(f'{begin} - {end}', loc='right') # set dates as title
	plt.xlabel('') # remove label x axis
	plt.ylim(ymin=0) # always start at 0
	plt.savefig('plot.png', bbox_inches='tight')

	return True


def main():
	print("Start date:")
	day = int(input("DD > "))
	month = int(input("MM > "))
	year = int(input("YY > "))
	begin = date_to_unix(0, day, month, year)
	length = int(input("Length (days) > "))
	graphtype = input("Type of graph > ")
	create_graph(begin, length * 24, graphtype)


if __name__ == '__main__':
	main()