"""
Module d'authentification - Version DB
Culture Pom - Authentification depuis table users_app

Remplace l'ancienne version qui utilisait le fichier users.py
"""

import streamlit as st
import bcrypt
from database import get_connection
from auth.permissions import load_user_session_permissions


def verify_password(plain_password, hashed_password):
    """Vérifie le mot de passe avec bcrypt"""
    try:
        return bcrypt.checkpw(
            plain_password.encode('utf-8'),
            hashed_password.encode('utf-8')
        )
    except Exception:
        return False


def hash_password(plain_password):
    """Hash un mot de passe avec bcrypt"""
    return bcrypt.hashpw(
        plain_password.encode('utf-8'), 
        bcrypt.gensalt()
    ).decode('utf-8')


def get_user_by_username(username):
    """Récupère un utilisateur depuis la base de données"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                u.id,
                u.username,
                u.password_hash,
                u.email,
                u.nom,
                u.prenom,
                u.is_active,
                r.code as role_code,
                r.libelle as role_libelle
            FROM users_app u
            JOIN roles r ON u.role_id = r.id
            WHERE u.username = %s
        """, (username,))
        
        user = cursor.fetchone()
        cursor.close()
        conn.close()
        
        return user
        
    except Exception as e:
        st.error(f"Erreur connexion: {e}")
        return None


def update_last_login(user_id):
    """Met à jour la date de dernière connexion"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE users_app 
            SET last_login = CURRENT_TIMESTAMP 
            WHERE id = %s
        """, (user_id,))
        
        conn.commit()
        cursor.close()
        conn.close()
        
    except Exception:
        pass  # Non bloquant


def authenticate_user(username, password):
    """
    Authentifie un utilisateur
    
    Returns:
        tuple: (success: bool, message: str, user_data: dict or None)
    """
    if not username or not password:
        return False, "Veuillez remplir tous les champs", None
    
    user = get_user_by_username(username)
    
    if not user:
        return False, "Nom d'utilisateur incorrect", None
    
    if not user['is_active']:
        return False, "Ce compte est désactivé. Contactez l'administrateur.", None
    
    if not verify_password(password, user['password_hash']):
        return False, "Mot de passe incorrect", None
    
    # Authentification réussie
    return True, "Connexion réussie", user


def show_login():
    """Affiche le formulaire de connexion"""
    
    # CSS personnalisé pour le login
    st.markdown("""
    <style>
        .login-container {
            max-width: 400px;
            margin: 0 auto;
            padding: 2rem;
        }
        .login-title {
            text-align: center;
            margin-bottom: 2rem;
        }
    </style>
    """, unsafe_allow_html=True)
    
    st.title('🔐 Connexion Culture Pom')
    st.markdown('---')
    
    # Formulaire de connexion
    with st.form('login_form'):
        username = st.text_input('👤 Nom d\'utilisateur', placeholder='Entrez votre identifiant')
        password = st.text_input('🔑 Mot de passe', type='password', placeholder='Entrez votre mot de passe')
        
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            submitted = st.form_submit_button('Se connecter', type='primary', use_container_width=True)
        
        if submitted:
            success, message, user = authenticate_user(username, password)
            
            if success:
                # Stocker les infos en session
                st.session_state['authenticated'] = True
                st.session_state['user_id'] = user['id']
                st.session_state['username'] = user['username']
                st.session_state['email'] = user['email']
                st.session_state['nom'] = user['nom']
                st.session_state['prenom'] = user['prenom']
                st.session_state['name'] = f"{user['prenom'] or ''} {user['nom'] or ''}".strip() or user['username']
                
                # Charger les permissions (nouveau!)
                load_user_session_permissions()
                
                # Compatibilité : mettre aussi 'role' pour ancien code
                role_code = st.session_state.get('role_code', '')
                if 'ADMIN' in role_code or st.session_state.get('is_super_admin', False):
                    st.session_state['role'] = 'ADMIN'
                else:
                    st.session_state['role'] = 'USER'
                
                # Mettre à jour last_login
                update_last_login(user['id'])
                
                st.success(f'✅ Bienvenue {st.session_state["name"]}')
                st.rerun()
            else:
                st.error(f'❌ {message}')
    
    # Footer
    st.markdown("---")
    st.caption("🔒 Connexion sécurisée")


def is_authenticated():
    """Vérifie si l'utilisateur est authentifié"""
    return st.session_state.get('authenticated', False)


def logout():
    """Déconnecte l'utilisateur"""
    keys_to_clear = [
        'authenticated', 'user_id', 'username', 'email', 'nom', 'prenom', 'name',
        'permissions', 'role_code', 'role_libelle', 'role_niveau', 
        'is_super_admin', 'is_admin'
    ]
    for key in keys_to_clear:
        st.session_state.pop(key, None)


def get_current_user_id():
    """Retourne l'ID de l'utilisateur courant"""
    return st.session_state.get('user_id')


def get_current_username():
    """Retourne le username de l'utilisateur courant"""
    return st.session_state.get('username')


# ===================================================
# FONCTIONS ADMIN - Gestion des utilisateurs
# ===================================================

def create_user(username, password, email, nom, prenom, role_id, created_by):
    """
    Crée un nouvel utilisateur
    
    Returns:
        tuple: (success: bool, message: str)
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Vérifier si username existe déjà
        cursor.execute("SELECT id FROM users_app WHERE username = %s", (username,))
        if cursor.fetchone():
            cursor.close()
            conn.close()
            return False, "Ce nom d'utilisateur existe déjà"
        
        # Hash du mot de passe
        password_hash = hash_password(password)
        
        # Insertion
        cursor.execute("""
            INSERT INTO users_app (username, password_hash, email, nom, prenom, role_id, created_by)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (username, password_hash, email, nom, prenom, role_id, created_by))
        
        new_id = cursor.fetchone()['id']
        conn.commit()
        cursor.close()
        conn.close()
        
        return True, f"Utilisateur créé avec succès (ID: {new_id})"
        
    except Exception as e:
        return False, f"Erreur: {str(e)}"


def update_user(user_id, email=None, nom=None, prenom=None, role_id=None, is_active=None):
    """
    Met à jour un utilisateur
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        updates = []
        values = []
        
        if email is not None:
            updates.append("email = %s")
            values.append(email)
        if nom is not None:
            updates.append("nom = %s")
            values.append(nom)
        if prenom is not None:
            updates.append("prenom = %s")
            values.append(prenom)
        if role_id is not None:
            updates.append("role_id = %s")
            values.append(role_id)
        if is_active is not None:
            updates.append("is_active = %s")
            values.append(is_active)
        
        if not updates:
            return False, "Aucune modification"
        
        updates.append("updated_at = CURRENT_TIMESTAMP")
        values.append(user_id)
        
        query = f"UPDATE users_app SET {', '.join(updates)} WHERE id = %s"
        cursor.execute(query, values)
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return True, "Utilisateur mis à jour"
        
    except Exception as e:
        return False, f"Erreur: {str(e)}"


def reset_password(user_id, new_password):
    """
    Réinitialise le mot de passe d'un utilisateur
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        password_hash = hash_password(new_password)
        
        cursor.execute("""
            UPDATE users_app 
            SET password_hash = %s, updated_at = CURRENT_TIMESTAMP 
            WHERE id = %s
        """, (password_hash, user_id))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return True, "Mot de passe réinitialisé"
        
    except Exception as e:
        return False, f"Erreur: {str(e)}"


def change_own_password(user_id, current_password, new_password):
    """
    Permet à un utilisateur de changer son propre mot de passe
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Vérifier l'ancien mot de passe
        cursor.execute("SELECT password_hash FROM users_app WHERE id = %s", (user_id,))
        user = cursor.fetchone()
        
        if not user:
            cursor.close()
            conn.close()
            return False, "Utilisateur introuvable"
        
        if not verify_password(current_password, user['password_hash']):
            cursor.close()
            conn.close()
            return False, "Mot de passe actuel incorrect"
        
        # Changer le mot de passe
        new_hash = hash_password(new_password)
        cursor.execute("""
            UPDATE users_app 
            SET password_hash = %s, updated_at = CURRENT_TIMESTAMP 
            WHERE id = %s
        """, (new_hash, user_id))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return True, "Mot de passe modifié avec succès"
        
    except Exception as e:
        return False, f"Erreur: {str(e)}"


def get_all_users():
    """Récupère la liste de tous les utilisateurs"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                u.id,
                u.username,
                u.email,
                u.nom,
                u.prenom,
                u.is_active,
                u.last_login,
                u.created_at,
                r.code as role_code,
                r.libelle as role_libelle,
                r.niveau as role_niveau
            FROM users_app u
            JOIN roles r ON u.role_id = r.id
            ORDER BY r.niveau DESC, u.username
        """)
        
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        
        return rows
        
    except Exception as e:
        st.error(f"Erreur: {e}")
        return []


def get_user_by_id(user_id):
    """Récupère un utilisateur par son ID"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                u.id,
                u.username,
                u.email,
                u.nom,
                u.prenom,
                u.is_active,
                u.role_id,
                u.last_login,
                u.created_at,
                r.code as role_code,
                r.libelle as role_libelle,
                r.niveau as role_niveau
            FROM users_app u
            JOIN roles r ON u.role_id = r.id
            WHERE u.id = %s
        """, (user_id,))
        
        user = cursor.fetchone()
        cursor.close()
        conn.close()
        
        return user
        
    except Exception as e:
        st.error(f"Erreur: {e}")
        return None
