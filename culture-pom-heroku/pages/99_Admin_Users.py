import streamlit as st
import pandas as pd
from datetime import datetime
from database import get_connection
from components import show_footer
from auth import (
    is_authenticated, 
    require_access,
    is_super_admin,
    can_manage_users,
    can_manage_user_of_level,
    get_manageable_roles,
    get_role_niveau,
    get_current_user_id,
    get_current_username,
    create_user,
    update_user,
    reset_password,
    get_all_users,
    get_user_by_id
)

st.set_page_config(page_title="Admin Users - Culture Pom", page_icon="⚙️", layout="wide")

# CSS compact
st.markdown("""
<style>
    .block-container {
        padding-top: 2rem !important;
        padding-bottom: 0.5rem !important;
    }
    h1, h2, h3, h4 {
        margin-top: 0.3rem !important;
        margin-bottom: 0.3rem !important;
    }
    .user-card {
        background-color: #f0f2f6;
        padding: 1rem;
        border-radius: 0.5rem;
        margin: 0.5rem 0;
        border-left: 4px solid #1f77b4;
    }
    .user-card.inactive {
        border-left-color: #ff6b6b;
        background-color: #ffe8e8;
    }
    .user-card.super-admin {
        border-left-color: #ffd700;
        background-color: #fffef0;
    }
    .perm-granted { color: #28a745; font-weight: bold; }
    .perm-denied { color: #dc3545; }
    .group-card {
        background-color: #e8f4ea;
        padding: 1rem;
        border-radius: 0.5rem;
        margin: 0.5rem 0;
        border-left: 4px solid #28a745;
    }
</style>
""", unsafe_allow_html=True)

# ==========================================
# CONTRÔLE D'ACCÈS
# ==========================================

if not is_authenticated():
    st.warning("⚠️ Veuillez vous connecter")
    st.stop()

# Vérifier accès admin
if not can_manage_users():
    st.error("🚫 Accès non autorisé")
    st.info("Cette page est réservée aux administrateurs.")
    st.stop()

# ==========================================
# EN-TÊTE
# ==========================================

st.title("⚙️ Administration Utilisateurs")
st.markdown("*Gestion des comptes et des rôles*")
st.markdown("---")

# Info utilisateur courant
col_info1, col_info2 = st.columns([3, 1])
with col_info1:
    st.caption(f"👤 Connecté : **{get_current_username()}** | Niveau : **{get_role_niveau()}**")
with col_info2:
    if is_super_admin():
        st.success("🔑 Super Admin")

# ==========================================
# FONCTIONS UTILITAIRES
# ==========================================

def validate_password(password):
    """Valide un mot de passe (min 8 caractères)"""
    if len(password) < 8:
        return False, "Le mot de passe doit contenir au moins 8 caractères"
    return True, ""

def get_roles_for_select():
    """Récupère les rôles disponibles pour le select"""
    roles = get_manageable_roles()
    return {f"{r['libelle']} (Niveau {r['niveau']})": r['id'] for r in roles}

def get_all_page_groups():
    """Récupère tous les groupes de pages actifs"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT code, libelle, ordre
            FROM page_groups
            WHERE is_active = TRUE
            ORDER BY ordre
        """)
        groups = cursor.fetchall()
        cursor.close()
        conn.close()
        return groups if groups else []
    except Exception as e:
        st.error(f"Erreur : {e}")
        return []

def get_permissions_for_role(role_id):
    """Récupère les permissions d'un rôle"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, page_group_code, can_view, can_edit, can_delete, can_admin
            FROM permissions
            WHERE role_id = %s
            ORDER BY page_group_code
        """, (role_id,))
        perms = cursor.fetchall()
        cursor.close()
        conn.close()
        return {p['page_group_code']: p for p in perms} if perms else {}
    except Exception as e:
        st.error(f"Erreur : {e}")
        return {}

def update_permission(role_id, page_group_code, can_view, can_edit, can_delete, can_admin):
    """Met à jour ou crée une permission"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Vérifier si la permission existe
        cursor.execute("""
            SELECT id FROM permissions
            WHERE role_id = %s AND page_group_code = %s
        """, (role_id, page_group_code))
        existing = cursor.fetchone()
        
        if existing:
            # Update
            cursor.execute("""
                UPDATE permissions
                SET can_view = %s, can_edit = %s, can_delete = %s, can_admin = %s
                WHERE role_id = %s AND page_group_code = %s
            """, (can_view, can_edit, can_delete, can_admin, role_id, page_group_code))
        else:
            # Insert
            cursor.execute("""
                INSERT INTO permissions (role_id, page_group_code, can_view, can_edit, can_delete, can_admin)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (role_id, page_group_code, can_view, can_edit, can_delete, can_admin))
        
        conn.commit()
        cursor.close()
        conn.close()
        return True, "✅ Permission mise à jour"
    except Exception as e:
        return False, f"❌ Erreur : {e}"

def delete_permission(role_id, page_group_code):
    """Supprime une permission"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            DELETE FROM permissions
            WHERE role_id = %s AND page_group_code = %s
        """, (role_id, page_group_code))
        conn.commit()
        cursor.close()
        conn.close()
        return True, "✅ Permission supprimée"
    except Exception as e:
        return False, f"❌ Erreur : {e}"

# ==========================================
# ⭐ FONCTIONS GROUPES DE PAGES
# ==========================================

def get_all_page_groups_full():
    """Récupère tous les groupes de pages avec tous les détails"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, code, libelle, description, pages, ordre, is_active
            FROM page_groups
            ORDER BY ordre, code
        """)
        groups = cursor.fetchall()
        cursor.close()
        conn.close()
        return groups if groups else []
    except Exception as e:
        st.error(f"Erreur : {e}")
        return []

def get_page_group_by_id(group_id):
    """Récupère un groupe par son ID"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, code, libelle, description, pages, ordre, is_active
            FROM page_groups
            WHERE id = %s
        """, (int(group_id),))
        group = cursor.fetchone()
        cursor.close()
        conn.close()
        return dict(group) if group else None
    except Exception as e:
        st.error(f"Erreur : {e}")
        return None

def create_page_group(code, libelle, description, pages, ordre):
    """Crée un nouveau groupe de pages"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Vérifier si le code existe déjà
        cursor.execute("SELECT id FROM page_groups WHERE code = %s", (code,))
        if cursor.fetchone():
            cursor.close()
            conn.close()
            return False, f"❌ Le code '{code}' existe déjà"
        
        # Convertir pages en array PostgreSQL
        pages_array = pages if pages else []
        
        cursor.execute("""
            INSERT INTO page_groups (code, libelle, description, pages, ordre, is_active)
            VALUES (%s, %s, %s, %s, %s, TRUE)
            RETURNING id
        """, (code, libelle, description, pages_array, ordre))
        
        new_id = cursor.fetchone()['id']
        conn.commit()
        cursor.close()
        conn.close()
        
        return True, f"✅ Groupe '{libelle}' créé (ID: {new_id})"
    except Exception as e:
        return False, f"❌ Erreur : {e}"

def update_page_group(group_id, code, libelle, description, pages, ordre, is_active):
    """Met à jour un groupe de pages"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Vérifier si le nouveau code existe déjà (sauf pour ce groupe)
        cursor.execute("SELECT id FROM page_groups WHERE code = %s AND id != %s", (code, int(group_id)))
        if cursor.fetchone():
            cursor.close()
            conn.close()
            return False, f"❌ Le code '{code}' est déjà utilisé par un autre groupe"
        
        pages_array = pages if pages else []
        
        cursor.execute("""
            UPDATE page_groups
            SET code = %s, libelle = %s, description = %s, pages = %s, ordre = %s, is_active = %s
            WHERE id = %s
        """, (code, libelle, description, pages_array, ordre, is_active, int(group_id)))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return True, f"✅ Groupe '{libelle}' mis à jour"
    except Exception as e:
        return False, f"❌ Erreur : {e}"

def delete_page_group(group_id):
    """Supprime un groupe de pages (soft delete)"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Vérifier s'il y a des permissions liées
        cursor.execute("SELECT COUNT(*) as cnt FROM permissions WHERE page_group_code = (SELECT code FROM page_groups WHERE id = %s)", (int(group_id),))
        count = cursor.fetchone()['cnt']
        
        if count > 0:
            # Soft delete seulement
            cursor.execute("UPDATE page_groups SET is_active = FALSE WHERE id = %s", (int(group_id),))
            msg = f"✅ Groupe désactivé ({count} permission(s) associée(s) conservées)"
        else:
            # Hard delete si pas de permissions
            cursor.execute("DELETE FROM page_groups WHERE id = %s", (int(group_id),))
            msg = "✅ Groupe supprimé"
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return True, msg
    except Exception as e:
        return False, f"❌ Erreur : {e}"

# ==========================================
# ONGLETS
# ==========================================

tab1, tab2, tab3, tab4 = st.tabs(["👥 Liste Utilisateurs", "➕ Créer Utilisateur", "🔑 Rôles & Permissions", "📁 Groupes de Pages"])

# ==========================================
# TAB 1 : LISTE UTILISATEURS
# ==========================================

with tab1:
    st.subheader("👥 Utilisateurs")
    
    # Bouton refresh
    if st.button("🔄 Actualiser", key="refresh_users"):
        st.rerun()
    
    # Charger users
    users = get_all_users()
    
    if users:
        # Filtres
        col1, col2 = st.columns(2)
        with col1:
            filter_role = st.selectbox(
                "Filtrer par rôle",
                ["Tous"] + list(set([u['role_libelle'] for u in users])),
                key="filter_role"
            )
        with col2:
            filter_status = st.selectbox(
                "Filtrer par statut",
                ["Tous", "Actifs", "Inactifs"],
                key="filter_status"
            )
        
        # Appliquer filtres
        filtered_users = users
        if filter_role != "Tous":
            filtered_users = [u for u in filtered_users if u['role_libelle'] == filter_role]
        if filter_status == "Actifs":
            filtered_users = [u for u in filtered_users if u['is_active']]
        elif filter_status == "Inactifs":
            filtered_users = [u for u in filtered_users if not u['is_active']]
        
        st.markdown(f"**{len(filtered_users)} utilisateur(s)**")
        st.markdown("---")
        
        # Affichage des users
        for user in filtered_users:
            # Déterminer la classe CSS
            card_class = "user-card"
            if not user['is_active']:
                card_class += " inactive"
            elif user['role_code'] == 'SUPER_ADMIN':
                card_class += " super-admin"
            
            with st.expander(f"{'🟢' if user['is_active'] else '🔴'} {user['username']} - {user['role_libelle']}"):
                col1, col2 = st.columns(2)
                
                with col1:
                    st.write(f"**ID** : {user['id']}")
                    st.write(f"**Username** : {user['username']}")
                    st.write(f"**Email** : {user['email'] or '-'}")
                    st.write(f"**Nom** : {user['prenom'] or ''} {user['nom'] or ''}")
                
                with col2:
                    st.write(f"**Rôle** : {user['role_libelle']}")
                    st.write(f"**Niveau** : {user['role_niveau']}")
                    st.write(f"**Statut** : {'✅ Actif' if user['is_active'] else '❌ Inactif'}")
                    st.write(f"**Dernière connexion** : {user['last_login'] or 'Jamais'}")
                
                # Actions (si on peut gérer cet utilisateur)
                can_manage = can_manage_user_of_level(user['role_niveau'])
                is_self = user['id'] == get_current_user_id()
                
                if can_manage and not is_self:
                    st.markdown("---")
                    col_a, col_b, col_c = st.columns(3)
                    
                    with col_a:
                        if st.button(f"✏️ Modifier", key=f"edit_{user['id']}"):
                            st.session_state['edit_user_id'] = user['id']
                            st.session_state['show_edit_form'] = True
                            st.rerun()
                    
                    with col_b:
                        if st.button(f"🔑 Reset MDP", key=f"reset_{user['id']}"):
                            st.session_state['reset_user_id'] = user['id']
                            st.session_state['show_reset_form'] = True
                            st.rerun()
                    
                    with col_c:
                        if user['is_active']:
                            if st.button(f"🚫 Désactiver", key=f"deact_{user['id']}"):
                                success, msg = update_user(user['id'], is_active=False)
                                if success:
                                    st.success("✅ Utilisateur désactivé")
                                    st.rerun()
                                else:
                                    st.error(msg)
                        else:
                            if st.button(f"✅ Réactiver", key=f"react_{user['id']}"):
                                success, msg = update_user(user['id'], is_active=True)
                                if success:
                                    st.success("✅ Utilisateur réactivé")
                                    st.rerun()
                                else:
                                    st.error(msg)
                
                elif is_self:
                    st.info("ℹ️ Vous ne pouvez pas modifier votre propre compte ici")
        
        # ==========================================
        # FORMULAIRE ÉDITION (modal)
        # ==========================================
        
        if st.session_state.get('show_edit_form', False):
            edit_user_id = st.session_state.get('edit_user_id')
            user_to_edit = get_user_by_id(edit_user_id)
            
            if user_to_edit:
                st.markdown("---")
                st.subheader(f"✏️ Modifier : {user_to_edit['username']}")
                
                with st.form("edit_user_form"):
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        edit_email = st.text_input("Email", value=user_to_edit['email'] or "")
                        edit_nom = st.text_input("Nom", value=user_to_edit['nom'] or "")
                    
                    with col2:
                        edit_prenom = st.text_input("Prénom", value=user_to_edit['prenom'] or "")
                        
                        # Sélection du rôle
                        roles_options = get_roles_for_select()
                        current_role_label = None
                        for label, rid in roles_options.items():
                            if rid == user_to_edit['role_id']:
                                current_role_label = label
                                break
                        
                        if roles_options:
                            edit_role_label = st.selectbox(
                                "Rôle",
                                options=list(roles_options.keys()),
                                index=list(roles_options.keys()).index(current_role_label) if current_role_label else 0
                            )
                            edit_role_id = roles_options[edit_role_label]
                        else:
                            edit_role_id = user_to_edit['role_id']
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        submitted = st.form_submit_button("💾 Enregistrer", type="primary")
                    with col2:
                        cancelled = st.form_submit_button("❌ Annuler")
                    
                    if submitted:
                        success, msg = update_user(
                            edit_user_id,
                            email=edit_email or None,
                            nom=edit_nom or None,
                            prenom=edit_prenom or None,
                            role_id=edit_role_id
                        )
                        if success:
                            st.success("✅ Utilisateur modifié")
                            st.session_state.pop('show_edit_form', None)
                            st.session_state.pop('edit_user_id', None)
                            st.rerun()
                        else:
                            st.error(msg)
                    
                    if cancelled:
                        st.session_state.pop('show_edit_form', None)
                        st.session_state.pop('edit_user_id', None)
                        st.rerun()
        
        # ==========================================
        # FORMULAIRE RESET MDP (modal)
        # ==========================================
        
        if st.session_state.get('show_reset_form', False):
            reset_user_id = st.session_state.get('reset_user_id')
            user_to_reset = get_user_by_id(reset_user_id)
            
            if user_to_reset:
                st.markdown("---")
                st.subheader(f"🔑 Reset MDP : {user_to_reset['username']}")
                
                with st.form("reset_pwd_form"):
                    new_password = st.text_input("Nouveau mot de passe", type="password")
                    confirm_password = st.text_input("Confirmer mot de passe", type="password")
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        submitted = st.form_submit_button("🔑 Réinitialiser", type="primary")
                    with col2:
                        cancelled = st.form_submit_button("❌ Annuler")
                    
                    if submitted:
                        if new_password != confirm_password:
                            st.error("❌ Les mots de passe ne correspondent pas")
                        else:
                            valid, msg = validate_password(new_password)
                            if not valid:
                                st.error(f"❌ {msg}")
                            else:
                                success, msg = reset_password(reset_user_id, new_password)
                                if success:
                                    st.success("✅ Mot de passe réinitialisé")
                                    st.session_state.pop('show_reset_form', None)
                                    st.session_state.pop('reset_user_id', None)
                                    st.rerun()
                                else:
                                    st.error(msg)
                    
                    if cancelled:
                        st.session_state.pop('show_reset_form', None)
                        st.session_state.pop('reset_user_id', None)
                        st.rerun()
    else:
        st.warning("Aucun utilisateur trouvé")

# ==========================================
# TAB 2 : CRÉER UTILISATEUR
# ==========================================

with tab2:
    st.subheader("➕ Créer un utilisateur")
    
    with st.form("create_user_form"):
        col1, col2 = st.columns(2)
        
        with col1:
            new_username = st.text_input("Username *", placeholder="ex: jean_dupont")
            new_email = st.text_input("Email", placeholder="ex: jean@example.com")
            new_password = st.text_input("Mot de passe *", type="password")
            new_password_confirm = st.text_input("Confirmer MDP *", type="password")
        
        with col2:
            new_nom = st.text_input("Nom", placeholder="ex: Dupont")
            new_prenom = st.text_input("Prénom", placeholder="ex: Jean")
            
            # Sélection du rôle
            roles_options = get_roles_for_select()
            if roles_options:
                selected_role_label = st.selectbox("Rôle *", options=list(roles_options.keys()))
                selected_role_id = roles_options[selected_role_label]
            else:
                st.error("❌ Aucun rôle disponible")
                selected_role_id = None
        
        st.markdown("---")
        st.caption("* Champs obligatoires")
        
        submitted = st.form_submit_button("✅ Créer l'utilisateur", type="primary", use_container_width=True)
        
        if submitted:
            # Validations
            errors = []
            
            if not new_username or len(new_username) < 3:
                errors.append("Username requis (min 3 caractères)")
            
            if not new_password:
                errors.append("Mot de passe requis")
            elif new_password != new_password_confirm:
                errors.append("Les mots de passe ne correspondent pas")
            else:
                valid, msg = validate_password(new_password)
                if not valid:
                    errors.append(msg)
            
            if not selected_role_id:
                errors.append("Rôle requis")
            
            if errors:
                for err in errors:
                    st.error(f"❌ {err}")
            else:
                # Créer l'utilisateur
                success, msg = create_user(
                    username=new_username,
                    password=new_password,
                    email=new_email or None,
                    nom=new_nom or None,
                    prenom=new_prenom or None,
                    role_id=selected_role_id,
                    created_by=get_current_username()
                )
                
                if success:
                    st.success(f"✅ {msg}")
                    st.balloons()
                else:
                    st.error(f"❌ {msg}")

# ==========================================
# TAB 3 : RÔLES & PERMISSIONS
# ==========================================

with tab3:
    st.subheader("🔑 Rôles & Permissions")
    
    # Charger les rôles
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
        
        # ==========================================
        # SECTION 1 : ÉDITION DES PERMISSIONS (Super Admin only)
        # ==========================================
        
        if is_super_admin():
            st.markdown("### ✏️ Modifier les permissions")
            st.caption("Sélectionnez un rôle pour modifier ses permissions d'accès aux différentes sections.")
            
            # Sélection du rôle à éditer
            role_options = {f"{r['libelle']} (Niveau {r['niveau']})": r for r in roles}
            selected_role_label = st.selectbox(
                "Rôle à modifier",
                options=list(role_options.keys()),
                key="edit_perm_role"
            )
            selected_role = role_options[selected_role_label]
            
            # Avertissement pour SUPER_ADMIN
            if selected_role['is_super_admin']:
                st.warning("⚠️ Le Super Admin a automatiquement accès à tout. Les permissions ci-dessous sont indicatives.")
            
            st.markdown("---")
            
            # Charger les groupes de pages et les permissions actuelles
            page_groups = get_all_page_groups()
            current_perms = get_permissions_for_role(selected_role['id'])
            
            # Afficher un tableau éditable
            st.markdown(f"**Permissions de : {selected_role['libelle']}**")
            
            # Créer les colonnes pour les checkboxes
            cols = st.columns([3, 1, 1, 1, 1])
            cols[0].markdown("**Groupe**")
            cols[1].markdown("**Voir**")
            cols[2].markdown("**Éditer**")
            cols[3].markdown("**Suppr.**")
            cols[4].markdown("**Admin**")
            
            st.markdown("---")
            
            # Pour chaque groupe de pages
            permissions_to_save = {}
            
            for pg in page_groups:
                pg_code = pg['code']
                pg_libelle = pg['libelle']
                
                # Permissions actuelles (ou défaut à False)
                perm = current_perms.get(pg_code, {})
                current_view = perm.get('can_view', False) if perm else False
                current_edit = perm.get('can_edit', False) if perm else False
                current_delete = perm.get('can_delete', False) if perm else False
                current_admin = perm.get('can_admin', False) if perm else False
                
                cols = st.columns([3, 1, 1, 1, 1])
                cols[0].write(f"📁 {pg_libelle}")
                
                new_view = cols[1].checkbox("", value=current_view, key=f"view_{selected_role['id']}_{pg_code}")
                new_edit = cols[2].checkbox("", value=current_edit, key=f"edit_{selected_role['id']}_{pg_code}")
                new_delete = cols[3].checkbox("", value=current_delete, key=f"delete_{selected_role['id']}_{pg_code}")
                new_admin = cols[4].checkbox("", value=current_admin, key=f"admin_{selected_role['id']}_{pg_code}")
                
                permissions_to_save[pg_code] = {
                    'can_view': new_view,
                    'can_edit': new_edit,
                    'can_delete': new_delete,
                    'can_admin': new_admin
                }
            
            st.markdown("---")
            
            # Bouton de sauvegarde
            col_save, col_cancel = st.columns([1, 3])
            with col_save:
                if st.button("💾 Enregistrer les permissions", type="primary", use_container_width=True):
                    errors = []
                    successes = 0
                    
                    for pg_code, perms in permissions_to_save.items():
                        # Si aucune permission, on pourrait supprimer l'entrée
                        # Mais on préfère garder avec can_view=False pour explicité
                        success, msg = update_permission(
                            role_id=selected_role['id'],
                            page_group_code=pg_code,
                            can_view=perms['can_view'],
                            can_edit=perms['can_edit'],
                            can_delete=perms['can_delete'],
                            can_admin=perms['can_admin']
                        )
                        if success:
                            successes += 1
                        else:
                            errors.append(f"{pg_code}: {msg}")
                    
                    if errors:
                        for err in errors:
                            st.error(err)
                    else:
                        st.success(f"✅ {successes} permission(s) enregistrée(s)")
                        st.info("⚠️ Les utilisateurs doivent se **reconnecter** pour voir les changements.")
                        st.balloons()
            
            st.markdown("---")
        
        # ==========================================
        # SECTION 2 : AFFICHAGE DES RÔLES (lecture seule)
        # ==========================================
        
        st.markdown("### 📋 Récapitulatif des rôles")
        
        for role in roles:
            icon = "👑" if role['is_super_admin'] else ("🔧" if role['is_admin'] else "👤")
            
            with st.expander(f"{icon} {role['libelle']} (Niveau {role['niveau']})"):
                st.write(f"**Code** : `{role['code']}`")
                st.write(f"**Description** : {role['description'] or '-'}")
                st.write(f"**Super Admin** : {'✅' if role['is_super_admin'] else '❌'}")
                st.write(f"**Admin** : {'✅' if role['is_admin'] else '❌'}")
                
                # Permissions de ce rôle
                conn2 = get_connection()
                cursor2 = conn2.cursor()
                cursor2.execute("""
                    SELECT page_group_code, can_view, can_edit, can_delete, can_admin
                    FROM permissions
                    WHERE role_id = %s
                    ORDER BY page_group_code
                """, (role['id'],))
                perms = cursor2.fetchall()
                cursor2.close()
                conn2.close()
                
                if perms:
                    st.markdown("**Permissions :**")
                    
                    # Tableau des permissions
                    df_perms = pd.DataFrame([
                        {
                            'Groupe': p['page_group_code'],
                            'Voir': '✅' if p['can_view'] else '❌',
                            'Éditer': '✅' if p['can_edit'] else '❌',
                            'Supprimer': '✅' if p['can_delete'] else '❌',
                            'Admin': '✅' if p['can_admin'] else '❌'
                        }
                        for p in perms
                    ])
                    
                    st.dataframe(df_perms, use_container_width=True, hide_index=True)
                else:
                    st.info("Aucune permission définie")
        
    except Exception as e:
        st.error(f"Erreur : {e}")
        import traceback
        st.code(traceback.format_exc())

# ==========================================
# ⭐ TAB 4 : GROUPES DE PAGES
# ==========================================

with tab4:
    st.subheader("📁 Gestion des Groupes de Pages")
    st.caption("Les groupes de pages servent à définir les permissions d'accès aux différentes sections de l'application.")
    
    if not is_super_admin():
        st.warning("⚠️ Seul le Super Admin peut gérer les groupes de pages")
        st.stop()
    
    # Bouton refresh
    if st.button("🔄 Actualiser", key="refresh_groups"):
        st.rerun()
    
    st.markdown("---")
    
    # ==========================================
    # FORMULAIRE CRÉATION
    # ==========================================
    
    with st.expander("➕ Créer un nouveau groupe", expanded=st.session_state.get('show_create_group', False)):
        st.markdown("##### Nouveau groupe de pages")
        
        col1, col2 = st.columns(2)
        
        with col1:
            new_code = st.text_input(
                "Code *", 
                placeholder="Ex: CRM, FINANCE, PRODUCTION",
                help="Code unique en MAJUSCULES, utilisé dans require_access()",
                key="new_group_code"
            ).upper().replace(" ", "_")
            
            new_libelle = st.text_input(
                "Libellé *",
                placeholder="Ex: CRM Commercial",
                key="new_group_libelle"
            )
        
        with col2:
            new_ordre = st.number_input(
                "Ordre d'affichage",
                min_value=1,
                max_value=100,
                value=10,
                key="new_group_ordre"
            )
            
            new_description = st.text_input(
                "Description",
                placeholder="Ex: Gestion des clients et contacts",
                key="new_group_desc"
            )
        
        new_pages_str = st.text_area(
            "Pages (noms des fichiers, séparés par des virgules)",
            placeholder="Ex: 21_CRM_Magasins, 22_CRM_Contacts, 23_CRM_Visites",
            help="Liste des noms de fichiers Python (sans .py) associés à ce groupe",
            key="new_group_pages"
        )
        
        col_create, col_cancel = st.columns([1, 3])
        
        with col_create:
            if st.button("✅ Créer le groupe", type="primary", use_container_width=True, key="btn_create_group"):
                if not new_code:
                    st.error("❌ Le code est obligatoire")
                elif not new_libelle:
                    st.error("❌ Le libellé est obligatoire")
                else:
                    # Parser les pages
                    pages_list = [p.strip() for p in new_pages_str.split(",") if p.strip()] if new_pages_str else []
                    
                    success, msg = create_page_group(
                        code=new_code,
                        libelle=new_libelle,
                        description=new_description or None,
                        pages=pages_list,
                        ordre=new_ordre
                    )
                    
                    if success:
                        st.success(msg)
                        st.balloons()
                        st.info("💡 N'oubliez pas d'attribuer des permissions à ce groupe dans l'onglet 'Rôles & Permissions'")
                        st.rerun()
                    else:
                        st.error(msg)
    
    st.markdown("---")
    
    # ==========================================
    # LISTE DES GROUPES
    # ==========================================
    
    st.markdown("### 📋 Groupes existants")
    
    groups = get_all_page_groups_full()
    
    if groups:
        # Stats
        active_count = len([g for g in groups if g['is_active']])
        inactive_count = len(groups) - active_count
        
        col1, col2 = st.columns(2)
        col1.metric("✅ Actifs", active_count)
        col2.metric("❌ Inactifs", inactive_count)
        
        st.markdown("---")
        
        for group in groups:
            status_icon = "🟢" if group['is_active'] else "🔴"
            pages_str = ", ".join(group['pages']) if group['pages'] else "Aucune page"
            
            with st.expander(f"{status_icon} {group['libelle']} (`{group['code']}`) - Ordre {group['ordre']}"):
                
                # Mode édition ?
                edit_mode = st.session_state.get(f'edit_group_{group["id"]}', False)
                
                if edit_mode:
                    # ==========================================
                    # FORMULAIRE ÉDITION
                    # ==========================================
                    st.markdown("##### ✏️ Modifier le groupe")
                    
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        edit_code = st.text_input(
                            "Code *",
                            value=group['code'],
                            key=f"edit_code_{group['id']}"
                        ).upper().replace(" ", "_")
                        
                        edit_libelle = st.text_input(
                            "Libellé *",
                            value=group['libelle'],
                            key=f"edit_libelle_{group['id']}"
                        )
                    
                    with col2:
                        edit_ordre = st.number_input(
                            "Ordre",
                            min_value=1,
                            max_value=100,
                            value=group['ordre'],
                            key=f"edit_ordre_{group['id']}"
                        )
                        
                        edit_description = st.text_input(
                            "Description",
                            value=group['description'] or "",
                            key=f"edit_desc_{group['id']}"
                        )
                    
                    edit_pages_str = st.text_area(
                        "Pages",
                        value=", ".join(group['pages']) if group['pages'] else "",
                        key=f"edit_pages_{group['id']}"
                    )
                    
                    edit_is_active = st.checkbox(
                        "Actif",
                        value=group['is_active'],
                        key=f"edit_active_{group['id']}"
                    )
                    
                    col_save, col_cancel = st.columns(2)
                    
                    with col_save:
                        if st.button("💾 Enregistrer", type="primary", key=f"save_group_{group['id']}"):
                            if not edit_code:
                                st.error("❌ Le code est obligatoire")
                            elif not edit_libelle:
                                st.error("❌ Le libellé est obligatoire")
                            else:
                                pages_list = [p.strip() for p in edit_pages_str.split(",") if p.strip()] if edit_pages_str else []
                                
                                success, msg = update_page_group(
                                    group_id=group['id'],
                                    code=edit_code,
                                    libelle=edit_libelle,
                                    description=edit_description or None,
                                    pages=pages_list,
                                    ordre=edit_ordre,
                                    is_active=edit_is_active
                                )
                                
                                if success:
                                    st.success(msg)
                                    st.session_state.pop(f'edit_group_{group["id"]}', None)
                                    st.rerun()
                                else:
                                    st.error(msg)
                    
                    with col_cancel:
                        if st.button("❌ Annuler", key=f"cancel_group_{group['id']}"):
                            st.session_state.pop(f'edit_group_{group["id"]}', None)
                            st.rerun()
                
                else:
                    # ==========================================
                    # AFFICHAGE LECTURE
                    # ==========================================
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.write(f"**Code** : `{group['code']}`")
                        st.write(f"**Libellé** : {group['libelle']}")
                        st.write(f"**Ordre** : {group['ordre']}")
                    
                    with col2:
                        st.write(f"**Description** : {group['description'] or '-'}")
                        st.write(f"**Statut** : {'✅ Actif' if group['is_active'] else '❌ Inactif'}")
                    
                    st.write(f"**Pages** : {pages_str}")
                    
                    # Compter les permissions liées
                    try:
                        conn_count = get_connection()
                        cursor_count = conn_count.cursor()
                        cursor_count.execute(
                            "SELECT COUNT(*) as cnt FROM permissions WHERE page_group_code = %s",
                            (group['code'],)
                        )
                        perm_count = cursor_count.fetchone()['cnt']
                        cursor_count.close()
                        conn_count.close()
                        st.caption(f"🔗 {perm_count} permission(s) liée(s)")
                    except:
                        pass
                    
                    st.markdown("---")
                    
                    # Boutons actions
                    col_edit, col_delete = st.columns(2)
                    
                    with col_edit:
                        if st.button("✏️ Modifier", key=f"btn_edit_group_{group['id']}", use_container_width=True):
                            st.session_state[f'edit_group_{group["id"]}'] = True
                            st.rerun()
                    
                    with col_delete:
                        if st.button("🗑️ Supprimer", key=f"btn_del_group_{group['id']}", use_container_width=True):
                            st.session_state[f'confirm_delete_{group["id"]}'] = True
                            st.rerun()
                    
                    # Confirmation suppression
                    if st.session_state.get(f'confirm_delete_{group["id"]}', False):
                        st.warning(f"⚠️ Voulez-vous vraiment supprimer le groupe **{group['libelle']}** ?")
                        
                        col_yes, col_no = st.columns(2)
                        
                        with col_yes:
                            if st.button("✅ Oui, supprimer", key=f"confirm_yes_{group['id']}", type="primary"):
                                success, msg = delete_page_group(group['id'])
                                if success:
                                    st.success(msg)
                                    st.session_state.pop(f'confirm_delete_{group["id"]}', None)
                                    st.rerun()
                                else:
                                    st.error(msg)
                        
                        with col_no:
                            if st.button("❌ Non, annuler", key=f"confirm_no_{group['id']}"):
                                st.session_state.pop(f'confirm_delete_{group["id"]}', None)
                                st.rerun()
    
    else:
        st.warning("Aucun groupe de pages trouvé")
    
    # ==========================================
    # AIDE
    # ==========================================
    
    st.markdown("---")
    st.markdown("### 💡 Aide")
    
    with st.expander("Comment utiliser les groupes de pages ?"):
        st.markdown("""
        **1. Créer un groupe**
        - Définissez un **code unique** en MAJUSCULES (ex: `CRM`, `FINANCE`)
        - Ce code sera utilisé dans le code Python avec `require_access("CRM")`
        
        **2. Associer des pages**
        - Listez les fichiers Python (sans .py) associés à ce groupe
        - Ex: `21_CRM_Magasins, 22_CRM_Contacts`
        
        **3. Attribuer des permissions**
        - Allez dans l'onglet "🔑 Rôles & Permissions"
        - Sélectionnez un rôle et cochez les permissions pour le nouveau groupe
        
        **4. Utiliser dans le code**
        ```python
        from auth import require_access, can_edit, can_delete
        
        require_access("CRM")  # Bloque si pas accès
        
        if can_edit("CRM"):
            # Afficher bouton éditer
        
        if can_delete("CRM"):
            # Afficher bouton supprimer
        ```
        
        **5. Reconnecter les utilisateurs**
        - Les permissions sont chargées à la connexion
        - Les utilisateurs doivent se **reconnecter** pour voir les changements
        """)

show_footer()
