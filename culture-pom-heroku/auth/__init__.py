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
    get_accessible_page_groups,
    get_page_group_icon,  # ⭐ AJOUTÉ pour module Tâches
    PAGE_GROUP_ICONS      # ⭐ AJOUTÉ - dictionnaire des icônes
)

# ============================================================
# FONCTIONS UTILITAIRES SESSION
# ============================================================

def get_current_user_id():
    """
    Retourne l'ID de l'utilisateur connecté
    """
    import streamlit as st
    return st.session_state.get('user_id', None)


def get_current_username():
    """
    Retourne le username de l'utilisateur connecté
    """
    import streamlit as st
    return st.session_state.get('username', None)


def get_current_user_info():
    """
    Retourne les infos complètes de l'utilisateur connecté
    """
    import streamlit as st
    return {
        'user_id': st.session_state.get('user_id'),
        'username': st.session_state.get('username'),
        'name': st.session_state.get('name'),
        'email': st.session_state.get('email'),
        'role_code': st.session_state.get('role_code'),
        'role_libelle': st.session_state.get('role_libelle'),
        'role_niveau': st.session_state.get('role_niveau'),
        'is_super_admin': st.session_state.get('is_super_admin', False),
        'is_admin': st.session_state.get('is_admin', False)
    }


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
        'commercial': 'COMMERCIAL',
        'taches': 'TACHES'  # ⭐ AJOUTÉ
    }
    
    group_code = mapping.get(permission, permission.upper())
    return has_access(group_code)


# ============================================================
# FONCTIONS GESTION UTILISATEURS
# ============================================================

def can_manage_user_of_level(target_level):
    """
    Vérifie si l'utilisateur courant peut gérer un user de niveau donné
    Un admin ne peut gérer que des users de niveau STRICTEMENT inférieur
    """
    import streamlit as st
    
    if not st.session_state.get('authenticated', False):
        return False
    
    # Super admin peut tout gérer
    if st.session_state.get('is_super_admin', False):
        return True
    
    # Récupérer le niveau de l'utilisateur courant
    current_level = st.session_state.get('role_niveau', 0)
    
    # Peut gérer seulement si niveau cible < niveau courant
    return target_level < current_level


def get_all_roles():
    """
    Récupère tous les rôles actifs depuis la base
    """
    from database import get_connection
    
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, code, libelle, niveau, is_super_admin, is_admin, description
            FROM roles
            WHERE is_active = TRUE
            ORDER BY niveau DESC
        """)
        
        roles = cursor.fetchall()
        cursor.close()
        conn.close()
        
        return roles if roles else []
        
    except Exception as e:
        print(f"Erreur get_all_roles: {e}")
        return []


def get_role_by_id(role_id):
    """
    Récupère un rôle par son ID
    """
    from database import get_connection
    
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, code, libelle, niveau, is_super_admin, is_admin, description
            FROM roles
            WHERE id = %s
        """, (role_id,))
        
        role = cursor.fetchone()
        cursor.close()
        conn.close()
        
        return role
        
    except Exception as e:
        print(f"Erreur get_role_by_id: {e}")
        return None


def get_permissions_for_role(role_id):
    """
    Récupère toutes les permissions d'un rôle
    """
    from database import get_connection
    
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT p.*, pg.libelle as group_libelle
            FROM permissions p
            JOIN page_groups pg ON p.page_group_code = pg.code
            WHERE p.role_id = %s
            ORDER BY pg.ordre
        """, (role_id,))
        
        perms = cursor.fetchall()
        cursor.close()
        conn.close()
        
        return perms if perms else []
        
    except Exception as e:
        print(f"Erreur get_permissions_for_role: {e}")
        return []


def get_all_page_groups():
    """
    Récupère tous les groupes de pages
    """
    from database import get_connection
    
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, code, libelle, description, pages, ordre
            FROM page_groups
            WHERE is_active = TRUE
            ORDER BY ordre
        """)
        
        groups = cursor.fetchall()
        cursor.close()
        conn.close()
        
        return groups if groups else []
        
    except Exception as e:
        print(f"Erreur get_all_page_groups: {e}")
        return []


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
    'get_page_group_icon',   # ⭐ AJOUTÉ
    'PAGE_GROUP_ICONS',      # ⭐ AJOUTÉ
    
    # Session utilisateur
    'get_current_user_id',
    'get_current_username',
    'get_current_user_info',
    
    # Compatibilité
    'is_compteur',
    'is_compteur_only',
    'get_role',
    'has_permission',
    
    # Gestion users/rôles
    'can_manage_user_of_level',
    'get_all_roles',
    'get_role_by_id',
    'get_permissions_for_role',
    'get_all_page_groups'
]
