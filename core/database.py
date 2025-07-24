# core/database.py

from sqlalchemy.orm import sessionmaker
from core.orm_models import init_db

_engine = None
Session = None

def setup_database(db_url: str):
    global _engine, Session
    _engine = init_db(db_url)
    Session = sessionmaker(bind=_engine)

def get_session():
    return Session()

