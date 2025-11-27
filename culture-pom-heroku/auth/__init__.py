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

# Ancien alias pour compatibilité (à retirer progressivement)
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
    
    # Compatibilité
    'has_permission',
]
