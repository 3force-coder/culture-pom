import streamlit as st
import pandas as pd
from datetime import datetime, date
from database import get_connection
from components import show_footer
from auth import require_access

st.set_page_config(page_title="Tâches - Culture Pom", page_icon="📋", layout="wide")

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
    
    /* En-têtes tableau : gras et centré */
    [data-testid="stDataFrame"] th {
        font-weight: bold !important;
        text-align: center !important;
    }
    [data-testid="stDataFrame"] th div {
        font-weight: bold !important;
        text-align: center !important;
    }
    
    /* Badges priorité */
    .priorite-urgente { color: #d62728; font-weight: bold; }
    .priorite-haute { color: #ff7f0e; font-weight: bold; }
    .priorite-normale { color: #1f77b4; }
    .priorite-basse { color: #7f7f7f; }
    
    /* Card commentaire */
    .comment-card {
        background-color: #f8f9fa;
        border-left: 3px solid #1f77b4;
        padding: 0.5rem 1rem;
        margin: 0.5rem 0;
        border-radius: 0 0.3rem 0.3rem 0;
    }
    .comment-meta {
        font-size: 0.8rem;
        color: #666;
    }
</style>
""", unsafe_allow_html=True)

# ============================================================
# 🔒 CONTRÔLE D'ACCÈS RBAC
# ============================================================
require_access("TACHES")
# ============================================================

st.title("📋 Gestion des Tâches")
st.markdown("---")

# ==========================================
# CONSTANTES
# ==========================================

PRIORITES = ['Basse', 'Normale', 'Haute', 'Urgente']
STATUTS = ['À faire', 'En cours', 'Terminée']
PRIORITE_ICONS = {
    'Urgente': '🔴',
    'Haute': '🟠',
    'Normale': '🔵',
    'Basse': '⚪'
}
STATUT_ICONS = {
    'À faire': '📝',
    'En cours': '🔄',
    'Terminée': '✅'
}

# ==========================================
# FONCTIONS UTILITAIRES
# ==========================================

def get_users_list():
    """Récupère la liste des utilisateurs pour assignation"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT username, name FROM users WHERE is_active = TRUE ORDER BY name")
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        return [(row['username'], row['name']) for row in rows]
    except:
        # Fallback si table users n'existe pas ou erreur
        return [('admin_3force', 'Admin 3Force'), ('user_judumas', 'Julien Dumas')]

def get_taches(statut_filter=None, priorite_filter=None, assigne_filter=None):
    """Récupère les tâches avec filtres optionnels"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        query = """
        SELECT 
            id, titre, description, priorite, statut,
            assigne_a, date_echeance,
            source_type, source_id, source_label,
            created_by, created_at, updated_at, closed_at
        FROM taches
        WHERE is_active = TRUE
        """
        
        params = []
        
        if statut_filter and statut_filter != "Tous":
            query += " AND statut = %s"
            params.append(statut_filter)
        
        if priorite_filter and priorite_filter != "Toutes":
            query += " AND priorite = %s"
            params.append(priorite_filter)
        
        if assigne_filter and assigne_filter != "Tous":
            query += " AND assigne_a = %s"
            params.append(assigne_filter)
        
        query += " ORDER BY CASE priorite WHEN 'Urgente' THEN 1 WHEN 'Haute' THEN 2 WHEN 'Normale' THEN 3 ELSE 4 END, date_echeance ASC NULLS LAST, created_at DESC"
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        
        if rows:
            return pd.DataFrame(rows)
        return pd.DataFrame()
        
    except Exception as e:
        st.error(f"❌ Erreur chargement tâches : {str(e)}")
        return pd.DataFrame()

def get_taches_counts():
    """Récupère les compteurs de tâches"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                COUNT(*) FILTER (WHERE statut = 'À faire' AND priorite = 'Urgente') as urgentes,
                COUNT(*) FILTER (WHERE statut = 'À faire') as a_faire,
                COUNT(*) FILTER (WHERE statut = 'En cours') as en_cours,
                COUNT(*) FILTER (WHERE statut = 'Terminée') as terminees
            FROM taches
            WHERE is_active = TRUE
        """)
        
        row = cursor.fetchone()
        cursor.close()
        conn.close()
        
        return {
            'urgentes': row['urgentes'] or 0,
            'a_faire': row['a_faire'] or 0,
            'en_cours': row['en_cours'] or 0,
            'terminees': row['terminees'] or 0
        }
        
    except Exception as e:
        return {'urgentes': 0, 'a_faire': 0, 'en_cours': 0, 'terminees': 0}

def get_commentaires(tache_id):
    """Récupère les commentaires d'une tâche"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, commentaire, created_by, created_at
            FROM taches_commentaires
            WHERE tache_id = %s
            ORDER BY created_at DESC
        """, (tache_id,))
        
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        
        return rows if rows else []
        
    except Exception as e:
        return []

def create_tache(titre, description, priorite, assigne_a, date_echeance, 
                 source_type=None, source_id=None, source_label=None):
    """Crée une nouvelle tâche"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        created_by = st.session_state.get('username', 'system')
        
        cursor.execute("""
            INSERT INTO taches (titre, description, priorite, assigne_a, date_echeance,
                               source_type, source_id, source_label, created_by)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (titre, description, priorite, assigne_a, date_echeance,
              source_type, source_id, source_label, created_by))
        
        tache_id = cursor.fetchone()['id']
        conn.commit()
        cursor.close()
        conn.close()
        
        return True, f"✅ Tâche #{tache_id} créée avec succès"
        
    except Exception as e:
        if 'conn' in locals():
            conn.rollback()
        return False, f"❌ Erreur : {str(e)}"

def update_tache_statut(tache_id, nouveau_statut):
    """Met à jour le statut d'une tâche"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        username = st.session_state.get('username', 'system')
        
        if nouveau_statut == 'Terminée':
            cursor.execute("""
                UPDATE taches
                SET statut = %s, updated_at = CURRENT_TIMESTAMP, 
                    closed_at = CURRENT_TIMESTAMP, closed_by = %s
                WHERE id = %s
            """, (nouveau_statut, username, tache_id))
        else:
            cursor.execute("""
                UPDATE taches
                SET statut = %s, updated_at = CURRENT_TIMESTAMP,
                    closed_at = NULL, closed_by = NULL
                WHERE id = %s
            """, (nouveau_statut, tache_id))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return True, f"✅ Statut mis à jour"
        
    except Exception as e:
        if 'conn' in locals():
            conn.rollback()
        return False, f"❌ Erreur : {str(e)}"

def update_tache(tache_id, titre, description, priorite, assigne_a, date_echeance):
    """Met à jour une tâche"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE taches
            SET titre = %s, description = %s, priorite = %s, 
                assigne_a = %s, date_echeance = %s, updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
        """, (titre, description, priorite, assigne_a, date_echeance, tache_id))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return True, "✅ Tâche mise à jour"
        
    except Exception as e:
        if 'conn' in locals():
            conn.rollback()
        return False, f"❌ Erreur : {str(e)}"

def add_commentaire(tache_id, commentaire):
    """Ajoute un commentaire à une tâche"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        created_by = st.session_state.get('username', 'system')
        
        cursor.execute("""
            INSERT INTO taches_commentaires (tache_id, commentaire, created_by)
            VALUES (%s, %s, %s)
        """, (tache_id, commentaire, created_by))
        
        # Mettre à jour updated_at de la tâche
        cursor.execute("""
            UPDATE taches SET updated_at = CURRENT_TIMESTAMP WHERE id = %s
        """, (tache_id,))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return True, "✅ Commentaire ajouté"
        
    except Exception as e:
        if 'conn' in locals():
            conn.rollback()
        return False, f"❌ Erreur : {str(e)}"

def delete_tache(tache_id):
    """Supprime une tâche (soft delete)"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE taches SET is_active = FALSE, updated_at = CURRENT_TIMESTAMP WHERE id = %s
        """, (tache_id,))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return True, "✅ Tâche supprimée"
        
    except Exception as e:
        if 'conn' in locals():
            conn.rollback()
        return False, f"❌ Erreur : {str(e)}"

# ==========================================
# KPIs
# ==========================================

counts = get_taches_counts()

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric("🔴 Urgentes", counts['urgentes'])

with col2:
    st.metric("📝 À faire", counts['a_faire'])

with col3:
    st.metric("🔄 En cours", counts['en_cours'])

with col4:
    st.metric("✅ Terminées", counts['terminees'])

st.markdown("---")

# ==========================================
# ONGLETS
# ==========================================

tab1, tab2, tab3, tab4 = st.tabs(["📝 À faire", "🔄 En cours", "✅ Terminées", "➕ Créer"])

# ==========================================
# ONGLET 1, 2, 3 : LISTES DE TÂCHES
# ==========================================

def display_taches_list(statut_filter):
    """Affiche la liste des tâches filtrées par statut"""
    
    # Filtres supplémentaires
    col_f1, col_f2 = st.columns(2)
    
    with col_f1:
        filtre_priorite = st.selectbox(
            "Filtrer par priorité",
            ["Toutes"] + PRIORITES,
            key=f"filtre_prio_{statut_filter}"
        )
    
    with col_f2:
        users = get_users_list()
        users_options = ["Tous"] + [f"{u[1]} ({u[0]})" for u in users]
        filtre_assigne = st.selectbox(
            "Filtrer par assigné",
            users_options,
            key=f"filtre_assigne_{statut_filter}"
        )
    
    # Extraire username si filtre assigné
    assigne_username = None
    if filtre_assigne != "Tous":
        # Extraire username entre parenthèses
        assigne_username = filtre_assigne.split('(')[1].replace(')', '')
    
    st.markdown("---")
    
    # Charger tâches
    df = get_taches(
        statut_filter=statut_filter,
        priorite_filter=filtre_priorite if filtre_priorite != "Toutes" else None,
        assigne_filter=assigne_username
    )
    
    if df.empty:
        st.info(f"📭 Aucune tâche '{statut_filter}'")
        return
    
    # Formater pour affichage
    df_display = df.copy()
    df_display['Priorité'] = df_display['priorite'].apply(lambda x: f"{PRIORITE_ICONS.get(x, '')} {x}")
    df_display['Échéance'] = df_display['date_echeance'].apply(
        lambda x: x.strftime('%d/%m/%Y') if pd.notna(x) else '-'
    )
    df_display['Source'] = df_display['source_label'].apply(lambda x: x if pd.notna(x) else '-')
    
    # Tableau avec sélection
    event = st.dataframe(
        df_display[['id', 'titre', 'Priorité', 'assigne_a', 'Échéance', 'Source']],
        column_config={
            "id": st.column_config.NumberColumn("ID", width="small"),
            "titre": st.column_config.TextColumn("Titre", width="large"),
            "Priorité": st.column_config.TextColumn("Priorité", width="small"),
            "assigne_a": st.column_config.TextColumn("Assigné", width="small"),
            "Échéance": st.column_config.TextColumn("Échéance", width="small"),
            "Source": st.column_config.TextColumn("Source", width="small"),
        },
        use_container_width=True,
        hide_index=True,
        on_select="rerun",
        selection_mode="single-row",
        key=f"table_{statut_filter}"
    )
    
    # Récupérer sélection
    selected_rows = event.selection.rows if hasattr(event, 'selection') else []
    
    if len(selected_rows) > 0:
        selected_idx = selected_rows[0]
        selected_tache = df.iloc[selected_idx]
        tache_id = int(selected_tache['id'])
        
        st.markdown("---")
        st.markdown(f"### 📋 Tâche #{tache_id} - {selected_tache['titre']}")
        
        # Détails
        col1, col2 = st.columns(2)
        
        with col1:
            st.write(f"**Priorité** : {PRIORITE_ICONS.get(selected_tache['priorite'], '')} {selected_tache['priorite']}")
            st.write(f"**Assigné à** : {selected_tache['assigne_a'] or '-'}")
            st.write(f"**Échéance** : {selected_tache['date_echeance'].strftime('%d/%m/%Y') if pd.notna(selected_tache['date_echeance']) else '-'}")
        
        with col2:
            st.write(f"**Source** : {selected_tache['source_type'] or '-'}")
            if selected_tache['source_label']:
                st.write(f"**Détail** : {selected_tache['source_label']}")
            st.write(f"**Créé par** : {selected_tache['created_by']} le {selected_tache['created_at'].strftime('%d/%m/%Y %H:%M')}")
        
        if selected_tache['description']:
            st.markdown("**Description** :")
            st.write(selected_tache['description'])
        
        st.markdown("---")
        
        # Actions
        col_a1, col_a2, col_a3, col_a4 = st.columns(4)
        
        with col_a1:
            if statut_filter != 'En cours':
                if st.button("🔄 Passer En cours", key=f"encours_{tache_id}", use_container_width=True):
                    success, msg = update_tache_statut(tache_id, 'En cours')
                    if success:
                        st.success(msg)
                        st.rerun()
                    else:
                        st.error(msg)
        
        with col_a2:
            if statut_filter != 'Terminée':
                if st.button("✅ Terminer", key=f"terminer_{tache_id}", use_container_width=True):
                    success, msg = update_tache_statut(tache_id, 'Terminée')
                    if success:
                        st.success(msg)
                        st.rerun()
                    else:
                        st.error(msg)
        
        with col_a3:
            if statut_filter == 'Terminée':
                if st.button("📝 Rouvrir", key=f"rouvrir_{tache_id}", use_container_width=True):
                    success, msg = update_tache_statut(tache_id, 'À faire')
                    if success:
                        st.success(msg)
                        st.rerun()
                    else:
                        st.error(msg)
        
        with col_a4:
            if st.button("🗑️ Supprimer", key=f"suppr_{tache_id}", use_container_width=True):
                success, msg = delete_tache(tache_id)
                if success:
                    st.success(msg)
                    st.rerun()
                else:
                    st.error(msg)
        
        # Commentaires
        st.markdown("---")
        st.markdown("#### 💬 Commentaires")
        
        commentaires = get_commentaires(tache_id)
        
        if commentaires:
            for comm in commentaires:
                st.markdown(f"""
                <div class="comment-card">
                    {comm['commentaire']}
                    <div class="comment-meta">— {comm['created_by']} le {comm['created_at'].strftime('%d/%m/%Y %H:%M')}</div>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.info("Aucun commentaire")
        
        # Ajouter commentaire
        with st.expander("➕ Ajouter un commentaire"):
            new_comment = st.text_area("Commentaire", key=f"comment_{tache_id}")
            if st.button("💾 Enregistrer", key=f"save_comment_{tache_id}"):
                if new_comment.strip():
                    success, msg = add_commentaire(tache_id, new_comment.strip())
                    if success:
                        st.success(msg)
                        st.rerun()
                    else:
                        st.error(msg)
                else:
                    st.warning("⚠️ Commentaire vide")
        
        # Modifier tâche
        with st.expander("✏️ Modifier la tâche"):
            users = get_users_list()
            users_dict = {u[0]: u[1] for u in users}
            
            mod_titre = st.text_input("Titre *", value=selected_tache['titre'], key=f"mod_titre_{tache_id}")
            mod_desc = st.text_area("Description", value=selected_tache['description'] or '', key=f"mod_desc_{tache_id}")
            
            col_m1, col_m2 = st.columns(2)
            with col_m1:
                mod_prio = st.selectbox(
                    "Priorité",
                    PRIORITES,
                    index=PRIORITES.index(selected_tache['priorite']),
                    key=f"mod_prio_{tache_id}"
                )
            with col_m2:
                current_assigne_idx = 0
                if selected_tache['assigne_a'] in [u[0] for u in users]:
                    current_assigne_idx = [u[0] for u in users].index(selected_tache['assigne_a'])
                
                mod_assigne = st.selectbox(
                    "Assigné à",
                    options=[u[0] for u in users],
                    format_func=lambda x: users_dict.get(x, x),
                    index=current_assigne_idx,
                    key=f"mod_assigne_{tache_id}"
                )
            
            mod_echeance = st.date_input(
                "Échéance",
                value=selected_tache['date_echeance'] if pd.notna(selected_tache['date_echeance']) else None,
                key=f"mod_echeance_{tache_id}"
            )
            
            if st.button("💾 Enregistrer modifications", key=f"save_mod_{tache_id}"):
                if mod_titre.strip():
                    success, msg = update_tache(tache_id, mod_titre.strip(), mod_desc, mod_prio, mod_assigne, mod_echeance)
                    if success:
                        st.success(msg)
                        st.rerun()
                    else:
                        st.error(msg)
                else:
                    st.warning("⚠️ Titre obligatoire")

# Afficher les onglets
with tab1:
    display_taches_list('À faire')

with tab2:
    display_taches_list('En cours')

with tab3:
    display_taches_list('Terminée')

# ==========================================
# ONGLET 4 : CRÉER TÂCHE
# ==========================================

with tab4:
    st.subheader("➕ Créer une nouvelle tâche")
    
    # Récupérer paramètres pré-remplis (si vient d'une autre page)
    prefill_titre = st.session_state.get('tache_prefill_titre', '')
    prefill_source_type = st.session_state.get('tache_prefill_source_type', None)
    prefill_source_id = st.session_state.get('tache_prefill_source_id', None)
    prefill_source_label = st.session_state.get('tache_prefill_source_label', None)
    
    # Nettoyer session après récupération
    for key in ['tache_prefill_titre', 'tache_prefill_source_type', 'tache_prefill_source_id', 'tache_prefill_source_label']:
        st.session_state.pop(key, None)
    
    # Afficher source si pré-remplie
    if prefill_source_label:
        st.info(f"📎 Source : {prefill_source_label}")
    
    # Formulaire
    new_titre = st.text_input("Titre *", value=prefill_titre, key="new_titre")
    new_desc = st.text_area("Description", key="new_desc")
    
    col1, col2 = st.columns(2)
    
    with col1:
        new_prio = st.selectbox("Priorité", PRIORITES, index=1, key="new_prio")  # Normale par défaut
    
    with col2:
        users = get_users_list()
        users_dict = {u[0]: u[1] for u in users}
        new_assigne = st.selectbox(
            "Assigné à",
            options=[''] + [u[0] for u in users],
            format_func=lambda x: users_dict.get(x, '— Non assigné —') if x else '— Non assigné —',
            key="new_assigne"
        )
    
    new_echeance = st.date_input("Échéance", value=None, key="new_echeance")
    
    st.markdown("---")
    
    if st.button("✅ Créer la tâche", type="primary", use_container_width=True):
        if new_titre.strip():
            success, msg = create_tache(
                titre=new_titre.strip(),
                description=new_desc if new_desc else None,
                priorite=new_prio,
                assigne_a=new_assigne if new_assigne else None,
                date_echeance=new_echeance,
                source_type=prefill_source_type,
                source_id=prefill_source_id,
                source_label=prefill_source_label
            )
            if success:
                st.success(msg)
                st.balloons()
            else:
                st.error(msg)
        else:
            st.warning("⚠️ Le titre est obligatoire")

st.markdown("---")
show_footer()
