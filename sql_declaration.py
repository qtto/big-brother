from sqlalchemy import Column, Integer, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import create_engine

Base = declarative_base()

class Log(Base):
    __tablename__ = 'admin_records'
    # Here we define columns for the table person
    # Notice that each column is also a normal Python instance attribute.
    id = Column(Integer, primary_key=True)
    timestamp = Column(Integer, nullable=False)
    userid    = Column(Integer, nullable=False)
    online    = Column(Boolean, nullable=False)
    ingame    = Column(Boolean, nullable=False)


# Create an engine that stores data in the local directory's
# sqlalchemy_example.db file.
engine = create_engine('sqlite:///admin_log.db')

# Create all tables in the engine. This is equivalent to "Create Table"
# statements in raw SQL.
Base.metadata.create_all(engine)
