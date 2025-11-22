import streamlit as st
import bcrypt
from auth.users import USERS

def verify_password(plain_password, hashed_password):
    """Vérifie le mot de passe avec bcrypt"""
    return bcrypt.checkpw(
        plain_password.encode('utf-8'),
        hashed_password.encode('utf-8')
    )

def show_login():
    st.title('🔐 Connexion Culture Pom')
    st.markdown('---')
    
    with st.form('login_form'):
        username = st.text_input('Username')
        password = st.text_input('Password', type='password')
        submitted = st.form_submit_button('Se connecter', type='primary', use_container_width=True)
        
        if submitted:
            if username in USERS:
                user = USERS[username]
                if verify_password(password, user['password_hash']):
                    st.session_state['authenticated'] = True
                    st.session_state['name'] = user['name']
                    st.session_state['username'] = username
                    st.session_state['email'] = user['email']
                    st.session_state['role'] = user['role']
                    st.success(f'✅ Bienvenue {user["name"]}')
                    st.rerun()
                else:
                    st.error('❌ Mot de passe incorrect')
            else:
                st.error('❌ Username incorrect')

def is_authenticated():
    return st.session_state.get('authenticated', False)