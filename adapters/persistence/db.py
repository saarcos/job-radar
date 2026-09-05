from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

CONNECTION_STRING = "postgresql+psycopg://jobradar:local@localhost:5433/jobradar"

engine = create_engine(CONNECTION_STRING)
SessionLocal = sessionmaker(bind=engine)
