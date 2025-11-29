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
# ONGLETS
# ==========================================

tab1, tab2, tab3 = st.tabs(["👥 Liste Utilisateurs", "➕ Créer Utilisateur", "🔑 Rôles & Permissions"])

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
        
        # Groupes de pages
        st.markdown("---")
        st.markdown("### 📄 Groupes de pages")
        
        conn3 = get_connection()
        cursor3 = conn3.cursor()
        cursor3.execute("""
            SELECT code, libelle, description, pages
            FROM page_groups
            WHERE is_active = TRUE
            ORDER BY ordre
        """)
        page_groups_list = cursor3.fetchall()
        cursor3.close()
        conn3.close()
        
        for pg in page_groups_list:
            pages_str = ', '.join(pg['pages']) if pg['pages'] else '-'
            with st.expander(f"📁 {pg['libelle']} (`{pg['code']}`)"):
                st.write(f"**Description** : {pg['description'] or '-'}")
                st.write(f"**Pages** : {pages_str}")
        
    except Exception as e:
        st.error(f"Erreur : {e}")
        import traceback
        st.code(traceback.format_exc())

show_footer()
