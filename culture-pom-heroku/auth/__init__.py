"""
Module Auth - Culture Pom
Authentification et gestion des permissions RBAC

Usage simple dans les pages:
    from auth import require_access, is_authenticated, show_login
    
    # En début de page
    if not is_authenticated():
        show_login()
        st.stop()
    
    require_access("STOCK")  # Vérifie les droits, stoppe si non autorisé
    
    # Pour vérifier les droits d'édition
    from auth import can_edit
    if can_edit("STOCK"):
        st.button("Modifier")
"""

import streamlit as st

# Authentification
from auth.authenticator import (
    show_login,
    is_authenticated,
    logout,
    authenticate_user,
    get_current_user_id,
    get_current_username,
    hash_password,
    verify_password,
)

# Gestion utilisateurs (admin)
from auth.authenticator import (
    create_user,
    update_user,
    reset_password,
    change_own_password,
    get_all_users,
    get_user_by_id,
)

# Permissions RBAC
from auth.permissions import (
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
    can_manage_user_of_level,
    get_manageable_roles,
    get_accessible_page_groups,
    get_page_group_icon,
    load_user_session_permissions,
)


# =====================================================
# FONCTIONS DE COMPATIBILITÉ (ancien système)
# À retirer progressivement quand les pages seront migrées
# =====================================================

def has_permission(permission):
    """
    DEPRECATED - Utiliser has_access() à la place
    Maintenu pour compatibilité avec ancien code
    """
    # Mapping ancien système vers nouveau
    old_to_new = {
        'dashboard': 'ACCUEIL',
        'lots_read': 'STOCK',
        'lots_write': 'STOCK',
        'import': 'STOCK',
        'admin': 'ADMIN'
    }
    page_group = old_to_new.get(permission, permission.upper())
    return has_access(page_group)


def is_compteur():
    """
    Vérifie si l'utilisateur a le rôle COMPTEUR
    Compatibilité avec pages existantes (11, 12)
    """
    role_code = st.session_state.get('role_code', '')
    # COMPTEUR ou tout admin/super_admin peut aussi faire le travail de compteur
    return role_code == 'COMPTEUR' or is_admin() or is_super_admin()


def get_role():
    """
    Retourne le code du rôle pour affichage (compatibilité ancien système)
    Mappe les nouveaux codes vers ADMIN/USER pour l'ancien affichage
    """
    role_code = st.session_state.get('role_code', '')
    if 'ADMIN' in role_code or is_super_admin():
        return 'ADMIN'
    return 'USER'


def ensure_role_compatibility():
    """
    Assure que session_state['role'] existe pour compatibilité
    À appeler après login si besoin
    """
    if 'role_code' in st.session_state:
        st.session_state['role'] = get_role()


# Export principal
__all__ = [
    # Authentification
    'show_login',
    'is_authenticated',
    'logout',
    'authenticate_user',
    'get_current_user_id',
    'get_current_username',
    'hash_password',
    'verify_password',
    
    # Admin users
    'create_user',
    'update_user',
    'reset_password',
    'change_own_password',
    'get_all_users',
    'get_user_by_id',
    
    # Permissions
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
    'can_manage_user_of_level',
    'get_manageable_roles',
    'get_accessible_page_groups',
    'get_page_group_icon',
    'load_user_session_permissions',
    
    # Compatibilité ancien système
    'has_permission',
    'is_compteur',
    'get_role',
    'ensure_role_compatibility',
]
