import streamlit as st
from auth import is_authenticated, is_admin
from components import show_header, show_footer
from database import get_connection

st.set_page_config(page_title='Admin', page_icon='⚙️', layout='wide')

if not is_authenticated():
    st.error('🔒 Veuillez vous connecter')
    st.stop()

if not is_admin():
    st.error('🚫 Accès réservé aux ADMIN')
    st.info(f"Votre rôle : {st.session_state.get('role')}")
    st.stop()

show_header('⚙️ Administration')

with st.sidebar:
    st.write(f"👤 {st.session_state['name']}")
    if st.button('🚪 Déconnexion'):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()

st.warning('⚠️ Zone réservée aux administrateurs')
st.markdown('### 📊 Statistiques')

conn = get_connection()
if conn:
    try:
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) as nb FROM lots_bruts')
        result = cursor.fetchone()
        count = result['nb'] if result else 0
        st.metric('📋 lots_bruts', f'{count:,} lignes')
        cursor.close()
        conn.close()
    except Exception as e:
        st.info(f'Base connectée : {e}')
else:
    st.error('Connexion impossible')

show_footer()
