import streamlit as st

def has_permission(permission):
    """Vérifie si l'utilisateur a une permission donnée"""
    if not st.session_state.get('authenticated', False):
        return False
    
    role = st.session_state.get('role', 'NONE')
    
    permissions = {
        'ADMIN': ['dashboard', 'lots_read', 'lots_write', 'import', 'admin', 'inventaire'],
        'USER': ['dashboard', 'lots_read', 'lots_write', 'inventaire'],
        'COMPTEUR': ['inventaire']  # ✅ NOUVEAU : Accès uniquement à l'inventaire
    }
    
    return permission in permissions.get(role, [])

def is_admin():
    """Vérifie si l'utilisateur est admin"""
    return st.session_state.get('role') == 'ADMIN'

def is_compteur():
    """Vérifie si l'utilisateur est compteur (accès limité inventaire)"""
    return st.session_state.get('role') == 'COMPTEUR'

def get_authorized_pages():
    """Retourne la liste des pages autorisées selon le rôle"""
    role = st.session_state.get('role', 'NONE')
    
    pages_by_role = {
        'ADMIN': [
            '00_Accueil',
            '01_Sources',
            '02_Lots',
            '03_Détails_stock',
            '04_Stock_Global',
            '05_Planning_Lavage',
            '06_Previsions_Ventes',
            '07_Affectation_Stock',
            '08_Planning_Production',
            '09_Valorisation_Lots',
            '10_Stock_Consommables',
            '11_Inventaire'
        ],
        'USER': [
            '00_Accueil',
            '01_Sources',
            '02_Lots',
            '03_Détails_stock',
            '04_Stock_Global',
            '05_Planning_Lavage',
            '06_Previsions_Ventes',
            '07_Affectation_Stock',
            '08_Planning_Production',
            '09_Valorisation_Lots',
            '10_Stock_Consommables',
            '11_Inventaire'
        ],
        'COMPTEUR': [
            '11_Inventaire'  # ✅ UNIQUEMENT Inventaire
        ]
    }
    
    return pages_by_role.get(role, [])

def check_page_access(page_name):
    """Vérifie si l'utilisateur a accès à une page donnée"""
    authorized_pages = get_authorized_pages()
    
    # Extraire le nom de la page sans extension
    page_base = page_name.replace('.py', '').replace('pages/', '')
    
    return page_base in authorized_pages
