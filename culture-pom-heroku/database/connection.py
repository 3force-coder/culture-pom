import os
import streamlit as st
import psycopg2
from psycopg2.extras import RealDictCursor

def get_connection():
    try:
        if os.getenv('DYNO'):
            conn_string = os.getenv('DATABASE_URL')
            if conn_string and conn_string.startswith('postgres://'):
                conn_string = conn_string.replace('postgres://', 'postgresql://', 1)
        else:
            db = st.secrets["postgres"]
            conn_string = f"postgresql://{db['user']}:{db['password']}@{db['host']}:{db['port']}/{db['database']}"
        
        conn = psycopg2.connect(conn_string, cursor_factory=RealDictCursor, sslmode='require')
        return conn
    except Exception as e:
        st.error(f"Erreur connexion : {e}")
        return None
