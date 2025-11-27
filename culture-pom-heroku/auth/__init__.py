"""
Module d'authentification Culture Pom
Système RBAC avec permissions par groupe de pages
"""

from .authenticator import (
    show_login,
    is_authenticated,
    authenticate_user,
    create_user,
    update_user,
    reset_password,
    get_all_users,
    get_user_by_id
)

from .permissions import (
    get_user_permissions,
    load_user_session_permissions,
    require_access,
    has_access,
    can_view,
    can_edit,
    can_delete,
    can_admin,
    is_super_admin,
    is_admin,
    get_role_niveau,
    can_manage_users,
    get_manageable_roles,
    get_accessible_page_groups
)

# ============================================================
# FONCTIONS DE COMPATIBILITÉ (ancien système)
# ============================================================

def is_compteur():
    """
    Compatibilité : Vérifie si l'utilisateur a accès à la saisie inventaire
    Retourne True pour COMPTEUR et tous les admins
    """
    import streamlit as st
    if not st.session_state.get('authenticated', False):
        return False
    
    # Super admin et admins ont accès partout
    if st.session_state.get('is_super_admin', False):
        return True
    if st.session_state.get('is_admin', False):
        return True
    
    # Rôle COMPTEUR
    role_code = st.session_state.get('role_code', '')
    return role_code == 'COMPTEUR'


def is_compteur_only():
    """
    Vérifie si l'utilisateur est UNIQUEMENT compteur (pas admin)
    Utilisé pour rediriger les compteurs purs vers page 12
    """
    import streamlit as st
    if not st.session_state.get('authenticated', False):
        return False
    
    # Si admin, retourne False (pas "compteur only")
    if st.session_state.get('is_super_admin', False):
        return False
    if st.session_state.get('is_admin', False):
        return False
    
    # Vrai seulement si rôle = COMPTEUR
    role_code = st.session_state.get('role_code', '')
    return role_code == 'COMPTEUR'


def get_role():
    """
    Compatibilité : Retourne le rôle pour l'ancien code
    Retourne "ADMIN" ou "USER" (ancien système)
    """
    import streamlit as st
    if st.session_state.get('is_super_admin', False):
        return "ADMIN"
    if st.session_state.get('is_admin', False):
        return "ADMIN"
    return "USER"


def has_permission(permission):
    """
    DEPRECATED - Utiliser has_access() à la place
    Maintenu pour compatibilité avec ancien code
    """
    # Mapper les anciennes permissions vers les nouveaux groupes
    mapping = {
        'dashboard': 'ACCUEIL',
        'lots_read': 'STOCK',
        'lots_write': 'STOCK',
        'import': 'STOCK',
        'admin': 'ADMIN',
        'inventaire': 'INVENTAIRE',
        'stock': 'STOCK',
        'production': 'PRODUCTION',
        'commercial': 'COMMERCIAL'
    }
    
    group_code = mapping.get(permission, permission.upper())
    return has_access(group_code)


# Export all
__all__ = [
    # Authenticator
    'show_login',
    'is_authenticated',
    'authenticate_user',
    'create_user',
    'update_user', 
    'reset_password',
    'get_all_users',
    'get_user_by_id',
    
    # Permissions
    'get_user_permissions',
    'load_user_session_permissions',
    'require_access',
    'has_access',
    'can_view',
    'can_edit',
    'can_delete',
    'can_admin',
    'is_super_admin',
    'is_admin',
    'get_role_niveau',
    'can_manage_users',
    'get_manageable_roles',
    'get_accessible_page_groups',
    
    # Compatibilité
    'is_compteur',
    'is_compteur_only',
    'get_role',
    'has_permission'
]
