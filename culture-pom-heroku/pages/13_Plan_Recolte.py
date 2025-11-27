import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime
import time
from database import get_connection
from components import show_footer
from auth import is_authenticated, has_access, can_edit, can_delete, get_current_username
import io

st.set_page_config(page_title="Plan Récolte - Culture Pom", page_icon="🌾", layout="wide")

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
    .stSelectbox, .stButton, .stCheckbox {
        margin-bottom: 0.3rem !important;
        margin-top: 0.3rem !important;
    }
    [data-testid="stMetricValue"] {
        font-size: 1.3rem !important;
    }
</style>
""", unsafe_allow_html=True)

# Vérification authentification
if not is_authenticated():
    st.warning("⚠️ Veuillez vous connecter pour accéder à cette page")
    st.stop()

# Vérification permissions
if not has_access("PLANS_RECOLTE"):
    st.error("🚫 Vous n'avez pas accès à cette page")
    st.stop()

# Permissions utilisateur
CAN_EDIT = can_edit("PLANS_RECOLTE")
CAN_DELETE = can_delete("PLANS_RECOLTE")

st.title("🌾 Plan de Récolte")
st.markdown("*Gestion du plan prévisionnel par variété, marque et type*")
st.markdown("---")

# ==========================================
# CONFIGURATION
# ==========================================

CAMPAGNE_ACTUELLE = 2026

# Liste des mois possibles
MOIS_OPTIONS = [
    "2026-07", "2026-08", "2026-09", "2026-10", "2026-11", "2026-12",
    "2027-01", "2027-02", "2027-03", "2027-04", "2027-05", "2027-06"
]

MOIS_LABELS = {
    "2026-07": "Juillet 2026", "2026-08": "Août 2026", "2026-09": "Septembre 2026",
    "2026-10": "Octobre 2026", "2026-11": "Novembre 2026", "2026-12": "Décembre 2026",
    "2027-01": "Janvier 2027", "2027-02": "Février 2027", "2027-03": "Mars 2027",
    "2027-04": "Avril 2027", "2027-05": "Mai 2027", "2027-06": "Juin 2027"
}

# ==========================================
# FONCTIONS UTILITAIRES
# ==========================================

def get_mois_numero(mois_str):
    """Extrait le numéro de mois"""
    try:
        return int(mois_str.split('-')[1])
    except:
        return 0

def calculer_volume_brut(volume_net, dechets_pct):
    """Calcule le volume brut"""
    if pd.isna(volume_net) or volume_net == 0:
        return 0
    if pd.isna(dechets_pct):
        dechets_pct = 15
    return volume_net / (1 - dechets_pct / 100)

def calculer_hectares(volume_brut, rendement):
    """Calcule les hectares nécessaires"""
    if pd.isna(volume_brut) or volume_brut == 0:
        return 0
    if pd.isna(rendement) or rendement == 0:
        rendement = 40
    return volume_brut / rendement

def load_plan_data(campagne, show_inactive=False):
    """Charge les données du plan"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        where_clause = f"WHERE campagne = {campagne}"
        if not show_inactive:
            where_clause += " AND is_active = TRUE"
        
        query = f"""
            SELECT id, campagne, mois, mois_numero, marque, type_produit, variete,
                   arrachage_quinzaine, volume_net_t, dechets_pct, volume_brut_t,
                   rendement_t_ha, hectares_necessaires, notes, is_active,
                   created_by, updated_by, created_at, updated_at
            FROM plans_recolte
            {where_clause}
            ORDER BY mois, marque, type_produit, variete
        """
        
        cursor.execute(query)
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        
        if rows:
            columns = ['id', 'campagne', 'mois', 'mois_numero', 'marque', 'type_produit', 
                      'variete', 'arrachage_quinzaine', 'volume_net_t', 'dechets_pct', 
                      'volume_brut_t', 'rendement_t_ha', 'hectares_necessaires', 'notes',
                      'is_active', 'created_by', 'updated_by', 'created_at', 'updated_at']
            df = pd.DataFrame(rows, columns=columns)
            
            # Convertir colonnes numériques
            numeric_cols = ['volume_net_t', 'dechets_pct', 'volume_brut_t', 
                           'rendement_t_ha', 'hectares_necessaires']
            for col in numeric_cols:
                df[col] = pd.to_numeric(df[col], errors='coerce')
            
            return df
        return pd.DataFrame()
        
    except Exception as e:
        st.error(f"❌ Erreur chargement : {str(e)}")
        return pd.DataFrame()

def get_unique_values(df, column):
    """Récupère valeurs uniques triées"""
    if column not in df.columns:
        return []
    values = df[column].dropna().unique().tolist()
    return sorted([str(v) for v in values if str(v).strip()])

def save_changes(original_df, edited_df):
    """Sauvegarde les modifications"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        updates = 0
        username = get_current_username()
        
        for idx in edited_df.index:
            if idx not in original_df.index:
                continue
            
            row_id = int(edited_df.loc[idx, 'id'])
            changes = {}
            
            # Colonnes éditables
            editable_cols = ['mois', 'marque', 'type_produit', 'variete', 
                           'arrachage_quinzaine', 'volume_net_t', 'dechets_pct',
                           'rendement_t_ha', 'notes']
            
            for col in editable_cols:
                if col not in edited_df.columns:
                    continue
                
                old_val = original_df.loc[idx, col]
                new_val = edited_df.loc[idx, col]
                
                # Comparer en gérant les NaN
                if pd.isna(old_val) and pd.isna(new_val):
                    continue
                elif pd.isna(old_val) or pd.isna(new_val) or old_val != new_val:
                    # Conversion type Python natif
                    if pd.isna(new_val):
                        changes[col] = None
                    elif isinstance(new_val, (np.integer, np.int64)):
                        changes[col] = int(new_val)
                    elif isinstance(new_val, (np.floating, np.float64)):
                        changes[col] = float(new_val)
                    else:
                        changes[col] = new_val
            
            if changes:
                # Recalculer colonnes automatiques si nécessaire
                volume_net = changes.get('volume_net_t', edited_df.loc[idx, 'volume_net_t'])
                dechets = changes.get('dechets_pct', edited_df.loc[idx, 'dechets_pct'])
                rendement = changes.get('rendement_t_ha', edited_df.loc[idx, 'rendement_t_ha'])
                
                volume_brut = calculer_volume_brut(volume_net, dechets)
                hectares = calculer_hectares(volume_brut, rendement)
                
                changes['volume_brut_t'] = volume_brut
                changes['hectares_necessaires'] = hectares
                changes['mois_numero'] = get_mois_numero(changes.get('mois', edited_df.loc[idx, 'mois']))
                
                # Construire UPDATE
                set_clause = ", ".join([f"{col} = %s" for col in changes.keys()])
                values = list(changes.values()) + [username, row_id]
                
                query = f"""
                    UPDATE plans_recolte 
                    SET {set_clause}, updated_by = %s, updated_at = CURRENT_TIMESTAMP 
                    WHERE id = %s
                """
                cursor.execute(query, values)
                updates += 1
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return True, f"✅ {updates} ligne(s) modifiée(s)"
        
    except Exception as e:
        if 'conn' in locals():
            conn.rollback()
        return False, f"❌ Erreur : {str(e)}"

def add_record(data):
    """Ajoute une nouvelle ligne"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        username = get_current_username()
        
        # Calculs automatiques
        volume_brut = calculer_volume_brut(data.get('volume_net_t', 0), data.get('dechets_pct', 15))
        hectares = calculer_hectares(volume_brut, data.get('rendement_t_ha', 40))
        mois_numero = get_mois_numero(data.get('mois', ''))
        
        query = """
            INSERT INTO plans_recolte (
                campagne, mois, mois_numero, marque, type_produit, variete,
                arrachage_quinzaine, volume_net_t, dechets_pct, volume_brut_t,
                rendement_t_ha, hectares_necessaires, notes, created_by
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """
        
        cursor.execute(query, (
            CAMPAGNE_ACTUELLE,
            data.get('mois'),
            mois_numero,
            data.get('marque'),
            data.get('type_produit'),
            data.get('variete'),
            data.get('arrachage_quinzaine'),
            data.get('volume_net_t', 0),
            data.get('dechets_pct', 15),
            volume_brut,
            data.get('rendement_t_ha', 40),
            hectares,
            data.get('notes'),
            username
        ))
        
        new_id = cursor.fetchone()[0]
        conn.commit()
        cursor.close()
        conn.close()
        
        return True, f"✅ Ligne #{new_id} ajoutée"
        
    except Exception as e:
        if 'conn' in locals():
            conn.rollback()
        return False, f"❌ Erreur : {str(e)}"

def delete_record(record_id):
    """Désactive une ligne (soft delete)"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        username = get_current_username()
        
        cursor.execute("""
            UPDATE plans_recolte 
            SET is_active = FALSE, updated_by = %s, updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
        """, (username, record_id))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return True, "✅ Ligne désactivée"
        
    except Exception as e:
        if 'conn' in locals():
            conn.rollback()
        return False, f"❌ Erreur : {str(e)}"

def reactivate_record(record_id):
    """Réactive une ligne"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        username = get_current_username()
        
        cursor.execute("""
            UPDATE plans_recolte 
            SET is_active = TRUE, updated_by = %s, updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
        """, (username, record_id))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return True, "✅ Ligne réactivée"
        
    except Exception as e:
        if 'conn' in locals():
            conn.rollback()
        return False, f"❌ Erreur : {str(e)}"

def recalculer_besoins():
    """Recalcule les besoins agrégés"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT recalculer_besoins_recolte(%s)", (CAMPAGNE_ACTUELLE,))
        nb_besoins = cursor.fetchone()[0]
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return True, f"✅ {nb_besoins} besoins recalculés"
        
    except Exception as e:
        if 'conn' in locals():
            conn.rollback()
        return False, f"❌ Erreur : {str(e)}"

# ==========================================
# CHARGEMENT DONNÉES
# ==========================================

# Toggle afficher inactifs
show_inactive = st.checkbox("👁️ Afficher lignes désactivées", value=False)

# Charger données
df_full = load_plan_data(CAMPAGNE_ACTUELLE, show_inactive)

if df_full.empty:
    st.warning(f"⚠️ Aucune donnée pour la campagne {CAMPAGNE_ACTUELLE}")
    st.info("💡 Utilisez le script d'import pour charger les données Excel")
    show_footer()
    st.stop()

# ==========================================
# KPIs
# ==========================================

df_actif = df_full[df_full['is_active'] == True] if 'is_active' in df_full.columns else df_full

col1, col2, col3, col4, col5 = st.columns(5)

with col1:
    st.metric("📋 Lignes", len(df_actif))

with col2:
    total_net = df_actif['volume_net_t'].sum()
    st.metric("📦 Vol. Net", f"{total_net:,.0f} T")

with col3:
    total_brut = df_actif['volume_brut_t'].sum()
    st.metric("📦 Vol. Brut", f"{total_brut:,.0f} T")

with col4:
    total_ha = df_actif['hectares_necessaires'].sum()
    st.metric("🌾 Hectares", f"{total_ha:,.1f}")

with col5:
    nb_varietes = df_actif['variete'].nunique()
    st.metric("🌱 Variétés", nb_varietes)

st.markdown("---")

# ==========================================
# FILTRES
# ==========================================

st.markdown("#### 🔍 Filtres")

col1, col2, col3, col4 = st.columns(4)

with col1:
    mois_options = ["Tous"] + get_unique_values(df_full, 'mois')
    filtre_mois = st.selectbox("Mois", mois_options, key="filtre_mois")

with col2:
    marque_options = ["Tous"] + get_unique_values(df_full, 'marque')
    filtre_marque = st.selectbox("Marque", marque_options, key="filtre_marque")

with col3:
    type_options = ["Tous"] + get_unique_values(df_full, 'type_produit')
    filtre_type = st.selectbox("Type", type_options, key="filtre_type")

with col4:
    variete_options = ["Tous"] + get_unique_values(df_full, 'variete')
    filtre_variete = st.selectbox("Variété", variete_options, key="filtre_variete")

# Appliquer filtres
df = df_full.copy()
if filtre_mois != "Tous":
    df = df[df['mois'] == filtre_mois]
if filtre_marque != "Tous":
    df = df[df['marque'] == filtre_marque]
if filtre_type != "Tous":
    df = df[df['type_produit'] == filtre_type]
if filtre_variete != "Tous":
    df = df[df['variete'] == filtre_variete]

# Afficher nombre résultats
if len(df) != len(df_full):
    st.info(f"🔍 {len(df)} ligne(s) après filtrage (sur {len(df_full)} total)")

st.markdown("---")

# ==========================================
# FORMULAIRE AJOUT
# ==========================================

if CAN_EDIT and st.session_state.get('show_add_form', False):
    st.subheader("➕ Ajouter une ligne")
    
    # Initialiser new_data
    if 'new_data' not in st.session_state:
        st.session_state.new_data = {}
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.session_state.new_data['mois'] = st.selectbox(
            "Mois *", 
            options=MOIS_OPTIONS,
            format_func=lambda x: MOIS_LABELS.get(x, x),
            key="add_mois"
        )
        
        # Dropdown marque avec option nouvelle valeur
        marques_existantes = get_unique_values(df_full, 'marque')
        marque_options = marques_existantes + ["➕ Nouvelle marque"]
        selected_marque = st.selectbox("Marque *", marque_options, key="add_marque_select")
        
        if selected_marque == "➕ Nouvelle marque":
            st.session_state.new_data['marque'] = st.text_input("Nouvelle marque", key="add_marque_new")
        else:
            st.session_state.new_data['marque'] = selected_marque
        
        # Dropdown type avec option nouvelle valeur
        types_existants = get_unique_values(df_full, 'type_produit')
        type_options = types_existants + ["➕ Nouveau type"]
        selected_type = st.selectbox("Type *", type_options, key="add_type_select")
        
        if selected_type == "➕ Nouveau type":
            st.session_state.new_data['type_produit'] = st.text_input("Nouveau type", key="add_type_new")
        else:
            st.session_state.new_data['type_produit'] = selected_type
        
        # Dropdown variété avec option nouvelle valeur
        varietes_existantes = get_unique_values(df_full, 'variete')
        variete_options = varietes_existantes + ["➕ Nouvelle variété"]
        selected_variete = st.selectbox("Variété *", variete_options, key="add_variete_select")
        
        if selected_variete == "➕ Nouvelle variété":
            st.session_state.new_data['variete'] = st.text_input("Nouvelle variété", key="add_variete_new")
        else:
            st.session_state.new_data['variete'] = selected_variete
    
    with col2:
        st.session_state.new_data['volume_net_t'] = st.number_input(
            "Volume net (T) *", min_value=0.0, value=0.0, step=10.0, key="add_volume"
        )
        
        st.session_state.new_data['dechets_pct'] = st.number_input(
            "Déchets (%)", min_value=0.0, max_value=50.0, value=15.0, step=1.0, key="add_dechets"
        )
        
        st.session_state.new_data['rendement_t_ha'] = st.number_input(
            "Rendement (T/ha)", min_value=10.0, max_value=100.0, value=40.0, step=5.0, key="add_rendement"
        )
        
        st.session_state.new_data['arrachage_quinzaine'] = st.text_input(
            "Quinzaine arrachage", key="add_quinzaine"
        )
        
        st.session_state.new_data['notes'] = st.text_area("Notes", key="add_notes", height=68)
    
    # Aperçu calculs
    vol_net = st.session_state.new_data.get('volume_net_t', 0) or 0
    dechets = st.session_state.new_data.get('dechets_pct', 15) or 15
    rendement = st.session_state.new_data.get('rendement_t_ha', 40) or 40
    
    vol_brut = calculer_volume_brut(vol_net, dechets)
    hectares = calculer_hectares(vol_brut, rendement)
    
    st.markdown("**Calculs automatiques :**")
    col_calc1, col_calc2 = st.columns(2)
    with col_calc1:
        st.metric("Volume brut calculé", f"{vol_brut:.1f} T")
    with col_calc2:
        st.metric("Hectares calculés", f"{hectares:.2f} ha")
    
    # Boutons
    col_btn1, col_btn2 = st.columns(2)
    
    with col_btn1:
        if st.button("💾 Enregistrer", type="primary", use_container_width=True, key="btn_save_add"):
            # Validation
            if not st.session_state.new_data.get('mois'):
                st.error("❌ Mois obligatoire")
            elif not st.session_state.new_data.get('marque'):
                st.error("❌ Marque obligatoire")
            elif not st.session_state.new_data.get('type_produit'):
                st.error("❌ Type obligatoire")
            elif not st.session_state.new_data.get('variete'):
                st.error("❌ Variété obligatoire")
            elif not st.session_state.new_data.get('volume_net_t') or st.session_state.new_data['volume_net_t'] <= 0:
                st.error("❌ Volume net doit être > 0")
            else:
                success, message = add_record(st.session_state.new_data)
                if success:
                    st.success(message)
                    st.balloons()
                    st.session_state.show_add_form = False
                    st.session_state.pop('new_data', None)
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error(message)
    
    with col_btn2:
        if st.button("❌ Annuler", use_container_width=True, key="btn_cancel_add"):
            st.session_state.show_add_form = False
            st.session_state.pop('new_data', None)
            st.rerun()
    
    st.markdown("---")

# ==========================================
# TABLEAU PRINCIPAL
# ==========================================

# En-tête avec boutons
col_title, col_btn1, col_btn2 = st.columns([3, 1, 1])

with col_title:
    st.subheader(f"📋 Plan Récolte {CAMPAGNE_ACTUELLE}")

with col_btn1:
    if CAN_EDIT:
        if st.button("➕ Ajouter", type="primary", use_container_width=True):
            st.session_state.show_add_form = not st.session_state.get('show_add_form', False)
            st.rerun()

with col_btn2:
    if st.button("🔄 Actualiser", use_container_width=True):
        st.rerun()

# Préparer DataFrame pour affichage
df_display = df[[
    'id', 'mois', 'marque', 'type_produit', 'variete', 
    'arrachage_quinzaine', 'volume_net_t', 'dechets_pct', 
    'volume_brut_t', 'rendement_t_ha', 'hectares_necessaires', 'notes'
]].copy()

# Renommer colonnes pour affichage
df_display = df_display.rename(columns={
    'mois': 'Mois',
    'marque': 'Marque',
    'type_produit': 'Type',
    'variete': 'Variété',
    'arrachage_quinzaine': 'Quinzaine',
    'volume_net_t': 'Vol. Net (T)',
    'dechets_pct': 'Déchets %',
    'volume_brut_t': 'Vol. Brut (T)',
    'rendement_t_ha': 'Rdt T/ha',
    'hectares_necessaires': 'Hectares',
    'notes': 'Notes'
})

# Configuration colonnes
column_config = {
    "id": None,  # Masquer
    "Mois": st.column_config.SelectboxColumn(
        "Mois",
        options=MOIS_OPTIONS,
        required=True
    ),
    "Marque": st.column_config.SelectboxColumn(
        "Marque",
        options=get_unique_values(df_full, 'marque'),
        required=True
    ),
    "Type": st.column_config.SelectboxColumn(
        "Type",
        options=get_unique_values(df_full, 'type_produit'),
        required=True
    ),
    "Variété": st.column_config.SelectboxColumn(
        "Variété",
        options=get_unique_values(df_full, 'variete'),
        required=True
    ),
    "Vol. Net (T)": st.column_config.NumberColumn(
        "Vol. Net (T)",
        format="%.1f",
        min_value=0
    ),
    "Déchets %": st.column_config.NumberColumn(
        "Déchets %",
        format="%.0f",
        min_value=0,
        max_value=50
    ),
    "Vol. Brut (T)": st.column_config.NumberColumn(
        "Vol. Brut (T)",
        format="%.1f",
        disabled=True
    ),
    "Rdt T/ha": st.column_config.NumberColumn(
        "Rdt T/ha",
        format="%.0f",
        min_value=10,
        max_value=100
    ),
    "Hectares": st.column_config.NumberColumn(
        "Hectares",
        format="%.2f",
        disabled=True
    )
}

# Stocker original pour comparaison
if 'original_df_plan' not in st.session_state:
    st.session_state.original_df_plan = df_display.copy()

# Afficher tableau éditable
if CAN_EDIT:
    edited_df = st.data_editor(
        df_display,
        column_config=column_config,
        use_container_width=True,
        num_rows="fixed",
        disabled=['id', 'Vol. Brut (T)', 'Hectares'],
        hide_index=True,
        key="plan_editor"
    )
else:
    st.dataframe(
        df_display,
        column_config=column_config,
        use_container_width=True,
        hide_index=True
    )
    edited_df = df_display

# ==========================================
# BOUTONS ACTIONS
# ==========================================

if CAN_EDIT:
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        if st.button("💾 Enregistrer modifs", type="primary", use_container_width=True):
            # Reconvertir noms colonnes
            edited_df_save = edited_df.rename(columns={
                'Mois': 'mois', 'Marque': 'marque', 'Type': 'type_produit',
                'Variété': 'variete', 'Quinzaine': 'arrachage_quinzaine',
                'Vol. Net (T)': 'volume_net_t', 'Déchets %': 'dechets_pct',
                'Vol. Brut (T)': 'volume_brut_t', 'Rdt T/ha': 'rendement_t_ha',
                'Hectares': 'hectares_necessaires', 'Notes': 'notes'
            })
            
            original_df_save = st.session_state.original_df_plan.rename(columns={
                'Mois': 'mois', 'Marque': 'marque', 'Type': 'type_produit',
                'Variété': 'variete', 'Quinzaine': 'arrachage_quinzaine',
                'Vol. Net (T)': 'volume_net_t', 'Déchets %': 'dechets_pct',
                'Vol. Brut (T)': 'volume_brut_t', 'Rdt T/ha': 'rendement_t_ha',
                'Hectares': 'hectares_necessaires', 'Notes': 'notes'
            })
            
            success, message = save_changes(original_df_save, edited_df_save)
            if success:
                st.success(message)
                st.session_state.original_df_plan = edited_df.copy()
                time.sleep(1)
                st.rerun()
            else:
                st.error(message)
    
    with col2:
        if st.button("🔄 Recalculer besoins", use_container_width=True):
            success, message = recalculer_besoins()
            if success:
                st.success(message)
            else:
                st.error(message)

# ==========================================
# GESTION ACTIVATION / DÉSACTIVATION
# ==========================================

if CAN_DELETE:
    st.markdown("---")
    st.subheader("🔒 Gestion activation")
    
    # Sélecteur de ligne
    options = [f"{row['id']} - {row['Mois']} | {row['Marque']} | {row['Variété']} ({row['Vol. Net (T)']:.0f}T)" 
               for _, row in df_display.iterrows()]
    
    if options:
        selected = st.selectbox("Sélectionner une ligne", options, key="select_activation")
        
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("🔒 Désactiver", use_container_width=True):
                record_id = int(selected.split(" - ")[0])
                success, message = delete_record(record_id)
                if success:
                    st.success(message)
                    st.rerun()
                else:
                    st.error(message)
        
        with col2:
            if st.button("🔓 Réactiver", use_container_width=True):
                record_id = int(selected.split(" - ")[0])
                success, message = reactivate_record(record_id)
                if success:
                    st.success(message)
                    st.rerun()
                else:
                    st.error(message)

# ==========================================
# EXPORTS
# ==========================================

st.markdown("---")
st.subheader("📤 Exports")

col1, col2 = st.columns(2)

with col1:
    csv = df_display.to_csv(index=False).encode('utf-8')
    st.download_button(
        "📥 Export CSV",
        csv,
        f"plan_recolte_{CAMPAGNE_ACTUELLE}_{datetime.now().strftime('%Y%m%d')}.csv",
        "text/csv",
        use_container_width=True
    )

with col2:
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
        df_display.to_excel(writer, index=False, sheet_name='Plan')
    
    st.download_button(
        "📥 Export Excel",
        buffer.getvalue(),
        f"plan_recolte_{CAMPAGNE_ACTUELLE}_{datetime.now().strftime('%Y%m%d')}.xlsx",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True
    )

show_footer()
