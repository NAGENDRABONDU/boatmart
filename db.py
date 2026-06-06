import pyodbc
from config import CONNECTION_STRING

def get_connection():
    return pyodbc.connect(CONNECTION_STRING)