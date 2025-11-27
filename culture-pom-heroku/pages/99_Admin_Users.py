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
                
                elif not can_manage:
                    st.warning("⚠️ Niveau insuffisant pour gérer cet utilisateur")
        
        # ==========================================
        # FORMULAIRE MODIFICATION (modal)
        # ==========================================
        
        if st.session_state.get('show_edit_form', False):
            edit_user_id = st.session_state.get('edit_user_id')
            user_to_edit = get_user_by_id(edit_user_id)
            
            if user_to_edit:
                st.markdown("---")
                st.subheader(f"✏️ Modifier : {user_to_edit['username']}")
                
                with st.form("edit_user_form"):
                    new_email = st.text_input("Email", value=user_to_edit['email'] or "")
                    new_nom = st.text_input("Nom", value=user_to_edit['nom'] or "")
                    new_prenom = st.text_input("Prénom", value=user_to_edit['prenom'] or "")
                    
                    # Rôle (seulement si on peut)
                    roles_options = get_roles_for_select()
                    current_role_label = f"{user_to_edit['role_libelle']} (Niveau {user_to_edit['role_niveau']})"
                    
                    if roles_options:
                        new_role_label = st.selectbox(
                            "Rôle",
                            options=list(roles_options.keys()),
                            index=list(roles_options.keys()).index(current_role_label) if current_role_label in roles_options else 0
                        )
                        new_role_id = roles_options[new_role_label]
                    else:
                        st.warning("Aucun rôle disponible")
                        new_role_id = user_to_edit['role_id']
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        submitted = st.form_submit_button("💾 Enregistrer", type="primary")
                    with col2:
                        cancelled = st.form_submit_button("❌ Annuler")
                    
                    if submitted:
                        success, msg = update_user(
                            edit_user_id,
                            email=new_email,
                            nom=new_nom,
                            prenom=new_prenom,
                            role_id=new_role_id
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
        
        # Afficher les rôles
        st.markdown("### 📋 Rôles disponibles")
        
        for role in roles:
            icon = "👑" if role['is_super_admin'] else ("🔧" if role['is_admin'] else "👤")
            
            with st.expander(f"{icon} {role['libelle']} (Niveau {role['niveau']})"):
                st.write(f"**Code** : `{role['code']}`")
                st.write(f"**Description** : {role['description'] or '-'}")
                st.write(f"**Super Admin** : {'✅' if role['is_super_admin'] else '❌'}")
                st.write(f"**Admin** : {'✅' if role['is_admin'] else '❌'}")
                
                # Permissions de ce rôle
                cursor.execute("""
                    SELECT page_group_code, can_view, can_edit, can_delete, can_admin
                    FROM permissions
                    WHERE role_id = %s
                    ORDER BY page_group_code
                """, (role['id'],))
                perms = cursor.fetchall()
                
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
        
        # Groupes de pages
        st.markdown("---")
        st.markdown("### 📄 Groupes de pages")
        
        cursor.execute("""
            SELECT code, libelle, description, pages
            FROM page_groups
            WHERE is_active = TRUE
            ORDER BY ordre
        """)
        page_groups = cursor.fetchall()
        
        for pg in page_groups:
            with st.expander(f"📁 {pg['libelle']} (`{pg['code']}`)"):
                st.write(f"**Description** : {pg['description'] or '-'}")
                st.write(f"**Pages** : {', '.join(pg['pages']) if pg['pages'] else '-'}")
        
        cursor.close()
        conn.close()
        
    except Exception as e:
        st.error(f"Erreur : {e}")
    
    # Note pour Super Admin
    if is_super_admin():
        st.markdown("---")
        st.info("💡 **Super Admin** : Pour modifier les rôles et permissions, utilisez directement la base de données ou un futur module d'administration avancée.")

show_footer()
