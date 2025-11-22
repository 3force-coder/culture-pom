import streamlit as st

def has_permission(permission):
    if not st.session_state.get('authenticated', False):
        return False
    role = st.session_state.get('role', 'NONE')
    permissions = {
        'ADMIN': ['dashboard', 'lots_read', 'lots_write', 'import', 'admin'],
        'USER': ['dashboard', 'lots_read', 'lots_write']
    }
    return permission in permissions.get(role, [])

def is_admin():
    return st.session_state.get('role') == 'ADMIN'
