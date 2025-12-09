"""
Module de gestion des permissions RBAC
Culture Pom - Système de contrôle d'accès basé sur les rôles

Usage dans chaque page:
    from auth import require_access
    require_access("STOCK")  # Bloque si pas accès
    
    # Ou pour vérifier sans bloquer:
    from auth import has_access, can_edit
    if has_access("STOCK"):
        ...
    if can_edit("STOCK"):
        # Afficher boutons édition
"""

import streamlit as st
from database import get_connection


def get_user_permissions(user_id):
    """
    Récupère toutes les permissions d'un utilisateur
    Retourne un dict: {page_group_code: {can_view, can_edit, can_delete, can_admin}}
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                p.page_group_code,
                p.can_view,
                p.can_edit,
                p.can_delete,
                p.can_admin
            FROM permissions p
            JOIN users_app u ON u.role_id = p.role_id
            WHERE u.id = %s
        """, (user_id,))
        
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        
        permissions = {}
        for row in rows:
            permissions[row['page_group_code']] = {
                'can_view': row['can_view'],
                'can_edit': row['can_edit'],
                'can_delete': row['can_delete'],
                'can_admin': row['can_admin']
            }
        
        return permissions
        
    except Exception as e:
        st.error(f"Erreur chargement permissions: {e}")
        return {}


def get_user_role_info(user_id):
    """
    Récupère les informations du rôle d'un utilisateur
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                r.id as role_id,
                r.code as role_code,
                r.libelle as role_libelle,
                r.niveau,
                r.is_super_admin,
                r.is_admin
            FROM users_app u
            JOIN roles r ON u.role_id = r.id
            WHERE u.id = %s
        """, (user_id,))
        
        row = cursor.fetchone()
        cursor.close()
        conn.close()
        
        return row if row else None
        
    except Exception as e:
        st.error(f"Erreur chargement rôle: {e}")
        return None


def load_user_session_permissions():
    """
    Charge les permissions dans session_state après login
    À appeler après authentification réussie
    """
    user_id = st.session_state.get('user_id')
    if not user_id:
        return False
    
    # Charger permissions
    permissions = get_user_permissions(user_id)
    st.session_state['permissions'] = permissions
    
    # Charger info rôle
    role_info = get_user_role_info(user_id)
    if role_info:
        st.session_state['role_code'] = role_info['role_code']
        st.session_state['role_libelle'] = role_info['role_libelle']
        st.session_state['role_niveau'] = role_info['niveau']
        st.session_state['is_super_admin'] = role_info['is_super_admin']
        st.session_state['is_admin'] = role_info['is_admin']
    
    return True


def is_super_admin():
    """Vérifie si l'utilisateur est SUPER_ADMIN"""
    return st.session_state.get('is_super_admin', False)


def is_admin():
    """Vérifie si l'utilisateur a un rôle admin (peut gérer des users)"""
    return st.session_state.get('is_admin', False)


def get_role_niveau():
    """Retourne le niveau du rôle (0-100)"""
    return st.session_state.get('role_niveau', 0)


def has_access(page_group_code):
    """
    Vérifie si l'utilisateur a accès (view) à un groupe de pages
    
    Args:
        page_group_code: Code du groupe (ex: "STOCK", "ADMIN")
    
    Returns:
        bool: True si accès autorisé
    """
    # Super admin a accès à tout
    if is_super_admin():
        return True
    
    permissions = st.session_state.get('permissions', {})
    group_perms = permissions.get(page_group_code, {})
    
    return group_perms.get('can_view', False)


def can_view(page_group_code):
    """Alias de has_access pour clarté"""
    return has_access(page_group_code)


def can_edit(page_group_code):
    """Vérifie si l'utilisateur peut éditer dans ce groupe"""
    if is_super_admin():
        return True
    
    permissions = st.session_state.get('permissions', {})
    group_perms = permissions.get(page_group_code, {})
    
    return group_perms.get('can_edit', False)


def can_delete(page_group_code):
    """Vérifie si l'utilisateur peut supprimer dans ce groupe"""
    if is_super_admin():
        return True
    
    permissions = st.session_state.get('permissions', {})
    group_perms = permissions.get(page_group_code, {})
    
    return group_perms.get('can_delete', False)


def can_admin(page_group_code):
    """Vérifie si l'utilisateur a les droits admin sur ce groupe"""
    if is_super_admin():
        return True
    
    permissions = st.session_state.get('permissions', {})
    group_perms = permissions.get(page_group_code, {})
    
    return group_perms.get('can_admin', False)


def require_access(page_group_code, require_edit=False, require_delete=False):
    """
    Vérifie l'accès et STOPPE la page si non autorisé
    À utiliser en début de chaque page
    
    Args:
        page_group_code: Code du groupe de pages
        require_edit: Si True, exige aussi le droit d'édition
        require_delete: Si True, exige aussi le droit de suppression
    
    Usage:
        require_access("STOCK")  # Lecture suffit
        require_access("STOCK", require_edit=True)  # Exige édition
    """
    # Vérifier authentification d'abord
    if not st.session_state.get('authenticated', False):
        st.warning("⚠️ Veuillez vous connecter pour accéder à cette page")
        st.stop()
    
    # Vérifier accès view
    if not has_access(page_group_code):
        st.error("🚫 Accès non autorisé")
        st.info(f"Votre rôle ({st.session_state.get('role_libelle', 'Non défini')}) n'a pas accès à cette section.")
        st.stop()
    
    # Vérifier édition si requis
    if require_edit and not can_edit(page_group_code):
        st.error("🚫 Droits d'édition insuffisants")
        st.info("Vous avez accès en lecture seule à cette section.")
        st.stop()
    
    # Vérifier suppression si requis
    if require_delete and not can_delete(page_group_code):
        st.error("🚫 Droits de suppression insuffisants")
        st.stop()


def get_accessible_page_groups():
    """
    Retourne la liste des groupes de pages accessibles par l'utilisateur
    Utile pour construire le menu dynamique
    """
    if is_super_admin():
        # Super admin voit tout
        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT code, libelle, ordre FROM page_groups WHERE is_active = TRUE ORDER BY ordre")
            rows = cursor.fetchall()
            cursor.close()
            conn.close()
            return [{'code': r['code'], 'libelle': r['libelle']} for r in rows]
        except:
            return []
    
    permissions = st.session_state.get('permissions', {})
    accessible = []
    
    for code, perms in permissions.items():
        if perms.get('can_view', False):
            accessible.append(code)
    
    return accessible


def can_manage_users():
    """Vérifie si l'utilisateur peut gérer d'autres utilisateurs"""
    return is_super_admin() or (is_admin() and has_access("ADMIN"))


def can_manage_user_of_level(target_niveau):
    """
    Vérifie si l'utilisateur peut gérer un user d'un certain niveau
    Un admin ne peut gérer que des users de niveau inférieur
    """
    if is_super_admin():
        return True
    
    my_niveau = get_role_niveau()
    return my_niveau > target_niveau


def get_manageable_roles():
    """
    Retourne les rôles que l'utilisateur courant peut attribuer
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        my_niveau = get_role_niveau()
        
        if is_super_admin():
            # Super admin peut attribuer tous les rôles
            cursor.execute("""
                SELECT id, code, libelle, niveau 
                FROM roles 
                WHERE is_active = TRUE 
                ORDER BY niveau DESC
            """)
        else:
            # Admin ne peut attribuer que des rôles de niveau inférieur
            cursor.execute("""
                SELECT id, code, libelle, niveau 
                FROM roles 
                WHERE is_active = TRUE 
                  AND niveau < %s 
                  AND is_super_admin = FALSE
                ORDER BY niveau DESC
            """, (my_niveau,))
        
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        
        return rows
        
    except Exception as e:
        st.error(f"Erreur: {e}")
        return []


# Mapping page_group → icône pour le menu
PAGE_GROUP_ICONS = {
    'ACCUEIL': '🏠',
    'REFERENTIELS': '📋',
    'STOCK': '📦',
    'CONSOMMABLES': '🧴',
    'PRODUCTION': '🏭',
    'COMMERCIAL': '📈',
    'CRM': '🛒',
    'FINANCE': '💰',
    'INVENTAIRE': '📊',
    'INVENTAIRE_SAISIE': '✏️',
    'PLANS_RECOLTE': '🌱',
    'TACHES': '✅',  # ⭐ AJOUTÉ pour module Tâches
    'ADMIN': '⚙️'
}


def get_page_group_icon(code):
    """Retourne l'icône d'un groupe de pages"""
    return PAGE_GROUP_ICONS.get(code, '📄')
