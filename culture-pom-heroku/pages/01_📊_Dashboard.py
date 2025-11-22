import streamlit as st
from auth import is_authenticated
from components import show_header, show_footer
from database import get_connection

st.set_page_config(page_title='Dashboard', page_icon='📊', layout='wide')

if not is_authenticated():
    st.error('🔒 Veuillez vous connecter')
    st.stop()

show_header('📊 Dashboard Stocks')

with st.sidebar:
    st.write(f"👤 {st.session_state['name']}")
    if st.button('🚪 Déconnexion'):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()

st.info('Vue d ensemble des stocks')

conn = get_connection()
if conn:
    try:
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) as nb FROM lots_bruts WHERE is_active = TRUE')
        result = cursor.fetchone()
        nb_lots = result['nb'] if result else 0
        st.metric('📦 Lots actifs', f'{nb_lots:,}')
        cursor.close()
        conn.close()
    except Exception as e:
        st.error(f'Erreur : {e}')
else:
    st.error('Connexion impossible')

show_footer()
