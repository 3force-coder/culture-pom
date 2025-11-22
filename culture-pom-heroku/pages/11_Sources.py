import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime
from database import get_connection
from components import show_footer
from auth import is_authenticated
import io

st.set_page_config(page_title="Sources - Culture Pom", page_icon="📋", layout="wide")

# CSS custom pour réduire FORTEMENT les espacements
st.markdown("""
<style>
    .block-container {
        padding-top: 2rem !important;
        padding-bottom: 0.5rem !important;
        padding-left: 2rem !important;
        padding-right: 2rem !important;
    }
    h1, h2, h3, h4 {
        margin-top: 0.3rem !important;
        margin-bottom: 0.3rem !important;
        padding-top: 0 !important;
        padding-bottom: 0 !important;
    }
    .stSelectbox, .stButton, .stCheckbox {
        margin-bottom: 0.3rem !important;
        margin-top: 0.3rem !important;
    }
    .stDataFrame {
        margin-top: 0.5rem !important;
        margin-bottom: 0.5rem !important;
    }
    [data-testid="stMetricValue"] {
        font-size: 1.4rem !important;
    }
    [data-testid="metric-container"] {
        padding: 0.3rem !important;
    }
    hr {
        margin-top: 0.5rem !important;
        margin-bottom: 0.5rem !important;
    }
    [data-testid="column"] {
        padding: 0.2rem !important;
    }
    .stForm {
        padding: 0.5rem !important;
        margin: 0.3rem !important;
    }
    .stSubheader {
        margin-top: 0.3rem !important;
        margin-bottom: 0.3rem !important;
    }
</style>
""", unsafe_allow_html=True)

if not is_authenticated():
    st.warning("⚠️ Veuillez vous connecter pour accéder à cette page")
    st.stop()

st.title("📋 Gestion des Tables de Référence")
st.markdown("---")

# Listes dropdowns
VARIETES_TYPES = [
    "Chair ferme jaune", "Chair ferme rouge", "Fritable entrée de gamme",
    "Fritable haut de gamme", "Fritable milieu de gamme", "Poly", "Poly jaune", "Poly rouge"
]

VARIETES_UTILISATIONS = [
    "Four", "Four/Frites", "Four/Potage", "Four/Potage/Frites",
    "Four/Purée/Potage", "Four/Purée/Potage/Frites", "Frites", "Vapeur", "Vapeur/Rissolées"
]

PLANTS_CALIBRES = [
    "25/30", "25/32", "28/30", "28/32", "28/35", "28/40",
    "30/40", "30/45", "30/50", "32/35", "32/40",
    "35/45", "35/50", "35/55",
    "40/45", "40/50",
    "45/50", "45/55",
    "50/55", "50/60",
    "55/60", "55/65",
    "60/65", "60/80"
]

def get_active_varietes():
    """Récupère les codes variétés actifs"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT code_variete FROM ref_varietes WHERE is_active = TRUE ORDER BY code_variete")
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        df = pd.DataFrame(rows, columns=['code_variete'])
        return df['code_variete'].tolist()
    except:
        return []

def get_varietes_with_existing(df, column_name):
    """Récupère variétés + valeurs existantes"""
    active = get_active_varietes()
    existing = df[column_name].dropna().unique().tolist() if column_name in df.columns else []
    return sorted(list(set(existing + active)))

TABLES_CONFIG = {
    "Variétés": {
        "table": "ref_varietes",
        "columns": ["code_variete", "nom_variete", "type", "utilisation", "is_active", "notes"],
        "hidden_columns": ["couleur_peau", "couleur_chair", "precocite"],
        "primary_key": "id",
        "editable": ["nom_variete", "type", "utilisation", "is_active", "notes"],
        "has_updated_at": True,
        "dropdown_fields": {
            "type": VARIETES_TYPES,
            "utilisation": VARIETES_UTILISATIONS
        },
        "filter_columns": ["nom_variete", "type", "utilisation"]
    },
    
    "Plants": {
        "table": "ref_plants",
        "columns": ["code_plant", "libelle_long", "code_variete_base", "calibre", "is_bio", "is_active", "notes"],
        "hidden_columns": ["poids_unite"],
        "primary_key": "id",
        "editable": ["libelle_long", "code_variete_base", "calibre", "is_bio", "is_active", "notes"],
        "has_updated_at": True,
        "dropdown_fields": {
            "calibre": PLANTS_CALIBRES,
            "code_variete_base": "dynamic_varietes"
        },
        "filter_columns": ["libelle_long", "code_variete_base", "is_bio"]
    },
    
    "Producteurs": {
        "table": "ref_producteurs",
        "columns": ["code_producteur", "cle_producteur", "nom", "siret", "adresse", "code_postal", "ville", "telephone", "email", "nom_contact", "is_active", "notes"],
        "primary_key": "id",
        "editable": ["nom", "siret", "adresse", "code_postal", "ville", "telephone", "email", "nom_contact", "is_active", "notes"],
        "has_updated_at": True
    },
    
    "Sites Stockage": {
        "table": "ref_sites_stockage",
        "columns": ["code_site", "code_emplacement", "nom_complet", "adresse", "capacite_max_pallox", "capacite_max_tonnes", "is_active", "notes"],
        "primary_key": "id",
        "editable": ["nom_complet", "adresse", "capacite_max_pallox", "capacite_max_tonnes", "is_active", "notes"],
        "has_updated_at": True,
        "auto_cle_unique": True
    },
    
    "Types Déchets": {
        "table": "ref_types_dechets",
        "columns": ["code", "libelle", "description", "is_active"],
        "primary_key": "id",
        "editable": ["libelle", "description", "is_active"],
        "has_updated_at": False
    },
    
    "Emballages": {
        "table": "ref_emballages",
        "columns": ["code_emballage", "atelier", "poids_unitaire", "unite_poids", "nbr_uvc", "type_produit", "is_active", "notes"],
        "primary_key": "id",
        "editable": ["atelier", "poids_unitaire", "unite_poids", "nbr_uvc", "type_produit", "is_active", "notes"],
        "has_updated_at": True
    },
    
    "Produits Commerciaux": {
        "table": "ref_produits_commerciaux",
        "columns": ["code_produit", "marque", "libelle", "poids_unitaire", "unite_poids", "type_produit", "code_variete", "is_bio", "is_active", "notes"],
        "primary_key": "id",
        "editable": ["marque", "libelle", "poids_unitaire", "unite_poids", "type_produit", "code_variete", "is_bio", "is_active", "notes"],
        "has_updated_at": True
    }
}

def load_table_data(table_name, show_inactive=False):
    """Charge les données d'une table"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        config = TABLES_CONFIG[table_name]
        
        all_columns = config["columns"].copy()
        if "hidden_columns" in config:
            all_columns.extend(config["hidden_columns"])
        
        columns_str = ", ".join(all_columns)
        where_clause = ""
        if not show_inactive and 'is_active' in all_columns:
            where_clause = " WHERE is_active = TRUE"
        
        query = f"SELECT {config['primary_key']}, {columns_str} FROM {config['table']}{where_clause} ORDER BY {config['primary_key']}"
        cursor.execute(query)
        
        rows = cursor.fetchall()
        columns = [config['primary_key']] + all_columns
        cursor.close()
        conn.close()
        
        df = pd.DataFrame(rows, columns=columns)
        display_columns = [config['primary_key']] + config['columns']
        df_display = df[display_columns].copy()
        st.session_state[f'full_df_{table_name}'] = df
        
        return df_display
    except Exception as e:
        st.error(f"❌ Erreur : {str(e)}")
        return pd.DataFrame()

def convert_to_native_types(value):
    """Convertit numpy types vers types Python natifs"""
    if pd.isna(value) or value is None:
        return None
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if isinstance(value, (np.integer, np.int64, np.int32, np.int16, np.int8)):
        return int(value)
    if isinstance(value, (np.floating, np.float64, np.float32)):
        return float(value)
    return value

def save_changes(table_name, original_df, edited_df):
    """Sauvegarde les modifications"""
    try:
        config = TABLES_CONFIG[table_name]
        conn = get_connection()
        cursor = conn.cursor()
        updates = 0
        
        for idx in edited_df.index:
            if idx not in original_df.index:
                continue
            
            row_id = convert_to_native_types(edited_df.loc[idx, config['primary_key']])
            changes = {}
            
            for col in config['editable']:
                if col not in edited_df.columns or col not in original_df.columns:
                    continue
                
                old_val = original_df.loc[idx, col]
                new_val = edited_df.loc[idx, col]
                
                if pd.isna(old_val) and pd.isna(new_val):
                    continue
                elif pd.isna(old_val) or pd.isna(new_val) or old_val != new_val:
                    changes[col] = convert_to_native_types(new_val)
            
            if changes:
                set_clause = ", ".join([f"{col} = %s" for col in changes.keys()])
                values = list(changes.values()) + [row_id]
                
                if config.get('has_updated_at', True):
                    update_query = f"UPDATE {config['table']} SET {set_clause}, updated_at = CURRENT_TIMESTAMP WHERE {config['primary_key']} = %s"
                else:
                    update_query = f"UPDATE {config['table']} SET {set_clause} WHERE {config['primary_key']} = %s"
                
                cursor.execute(update_query, values)
                updates += 1
        
        conn.commit()
        cursor.close()
        conn.close()
        return True, f"✅ {updates} enregistrement(s) mis à jour"
    except Exception as e:
        if 'conn' in locals():
            conn.rollback()
        return False, f"❌ Erreur : {str(e)}"

def delete_record(table_name, record_id):
    """Désactive un enregistrement"""
    try:
        config = TABLES_CONFIG[table_name]
        conn = get_connection()
        cursor = conn.cursor()
        
        if config.get('has_updated_at', True):
            query = f"UPDATE {config['table']} SET is_active = FALSE, updated_at = CURRENT_TIMESTAMP WHERE {config['primary_key']} = %s"
        else:
            query = f"UPDATE {config['table']} SET is_active = FALSE WHERE {config['primary_key']} = %s"
        
        cursor.execute(query, (record_id,))
        conn.commit()
        cursor.close()
        conn.close()
        return True, "✅ Désactivé"
    except Exception as e:
        if 'conn' in locals():
            conn.rollback()
        return False, f"❌ Erreur : {str(e)}"

def reactivate_record(table_name, record_id):
    """Réactive un enregistrement"""
    try:
        config = TABLES_CONFIG[table_name]
        conn = get_connection()
        cursor = conn.cursor()
        
        if config.get('has_updated_at', True):
            query = f"UPDATE {config['table']} SET is_active = TRUE, updated_at = CURRENT_TIMESTAMP WHERE {config['primary_key']} = %s"
        else:
            query = f"UPDATE {config['table']} SET is_active = TRUE WHERE {config['primary_key']} = %s"
        
        cursor.execute(query, (record_id,))
        conn.commit()
        cursor.close()
        conn.close()
        return True, "✅ Réactivé"
    except Exception as e:
        if 'conn' in locals():
            conn.rollback()
        return False, f"❌ Erreur : {str(e)}"

def add_record(table_name, data):
    """Ajoute un enregistrement - CODE SIMPLE QUI MARCHAIT"""
    try:
        config = TABLES_CONFIG[table_name]
        conn = get_connection()
        cursor = conn.cursor()
        
        if config.get('auto_cle_unique'):
            if 'code_site' in data and 'code_emplacement' in data:
                data['cle_unique'] = f"{data['code_site']}_{data['code_emplacement']}"
        
        if "hidden_columns" in config:
            for col in config["hidden_columns"]:
                if col not in data:
                    data[col] = None
        
        columns = list(data.keys())
        values = [convert_to_native_types(v) for v in data.values()]
        placeholders = ", ".join(["%s"] * len(columns))
        columns_str = ", ".join(columns)
        
        if config.get('has_updated_at', True):
            query = f"INSERT INTO {config['table']} ({columns_str}, created_at, updated_at) VALUES ({placeholders}, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
        else:
            query = f"INSERT INTO {config['table']} ({columns_str}, created_at) VALUES ({placeholders}, CURRENT_TIMESTAMP)"
        
        cursor.execute(query, values)
        conn.commit()
        cursor.close()
        conn.close()
        return True, "✅ Ajouté"
    except Exception as e:
        if 'conn' in locals():
            conn.rollback()
        return False, f"❌ Erreur : {str(e)}"

# Interface
selected_table = st.selectbox("📋 Table", list(TABLES_CONFIG.keys()), key="table_selector")
st.markdown("---")

# Formulaire ajout - SIMPLE comme v3
if st.session_state.get('show_add_form', False):
    with st.form("add_form"):
        st.subheader(f"➕ Ajouter - {selected_table}")
        config = TABLES_CONFIG[selected_table]
        new_data = {}
        
        col1, col2 = st.columns(2)
        for i, col in enumerate(config['columns']):
            with col1 if i % 2 == 0 else col2:
                if "dropdown_fields" in config and col in config["dropdown_fields"]:
                    field_config = config["dropdown_fields"][col]
                    
                    if field_config == "dynamic_varietes":
                        varietes = get_active_varietes()
                        options = [""] + varietes
                        new_data[col] = st.selectbox(col.replace('_', ' ').title(), options, key=f"add_{col}")
                    else:
                        options = [""] + field_config
                        new_data[col] = st.selectbox(col.replace('_', ' ').title(), options, key=f"add_{col}")
                elif col in ['is_active', 'is_bio', 'global_gap']:
                    new_data[col] = st.checkbox(col.replace('_', ' ').title(), value=True)
                elif 'capacite' in col or 'prix' in col or 'poids' in col:
                    new_data[col] = st.number_input(col.replace('_', ' ').title(), min_value=0.0, value=0.0, step=0.1)
                elif 'nbr' in col:
                    new_data[col] = st.number_input(col.replace('_', ' ').title(), min_value=0, value=0, step=1)
                else:
                    new_data[col] = st.text_input(col.replace('_', ' ').title())
        
        col1, col2 = st.columns([1, 1])
        with col1:
            if st.form_submit_button("💾 Enregistrer", use_container_width=True):
                filtered_data = {k: v for k, v in new_data.items() if v != '' and v is not None}
                success, message = add_record(selected_table, filtered_data)
                if success:
                    st.success(message)
                    st.session_state.show_add_form = False
                    st.rerun()
                else:
                    st.error(message)
        with col2:
            if st.form_submit_button("❌ Annuler", use_container_width=True):
                st.session_state.show_add_form = False
                st.rerun()
    
    st.markdown("---")

# Toggle inactifs
show_inactive = st.checkbox("👁️ Afficher les éléments inactifs", value=False, key=f"show_inactive_{selected_table}")
df_full = load_table_data(selected_table, show_inactive=show_inactive)

if not df_full.empty:
    config = TABLES_CONFIG[selected_table]
    
    # Métriques
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("📊 Total", len(df_full))
    with col2:
        actifs = df_full['is_active'].sum() if 'is_active' in df_full.columns else len(df_full)
        st.metric("✅ Actifs", actifs)
    with col3:
        inactifs = len(df_full) - actifs if 'is_active' in df_full.columns else 0
        st.metric("❌ Inactifs", inactifs)
    
    st.markdown("---")
    
    # Filtres
    df = df_full.copy()
    if "filter_columns" in config:
        st.markdown("#### 🔍 Filtres")
        filter_cols = st.columns(len(config["filter_columns"]))
        filters = {}
        
        for i, col_name in enumerate(config["filter_columns"]):
            with filter_cols[i]:
                if col_name in df.columns:
                    if col_name == "is_bio":
                        bio_options = ["Tous", "OUI", "NON"]
                        filters[col_name] = st.selectbox("Bio", bio_options, key=f"filter_{col_name}")
                    else:
                        unique_values = ["Tous"] + sorted([str(v) for v in df[col_name].dropna().unique()])
                        filters[col_name] = st.selectbox(col_name.replace('_', ' ').title(), unique_values, key=f"filter_{col_name}")
        
        for col_name, selected_value in filters.items():
            if selected_value != "Tous":
                if col_name == "is_bio":
                    if selected_value == "OUI":
                        df = df[df[col_name] == True]
                    elif selected_value == "NON":
                        df = df[df[col_name] == False]
                else:
                    df = df[df[col_name].astype(str) == selected_value]
        
        if len(df) != len(df_full):
            st.info(f"🔍 {len(df)} résultat(s) après filtrage (sur {len(df_full)} total)")
        
        st.markdown("---")
    
    # En-tête + bouton Ajouter
    col_title, col_button = st.columns([4, 1])
    with col_title:
        st.subheader(f"📋 {selected_table}")
    with col_button:
        if st.button("➕ Ajouter", use_container_width=True, type="primary"):
            st.session_state.show_add_form = not st.session_state.get('show_add_form', False)
    
    # Configuration dropdowns
    column_config = {}
    if "dropdown_fields" in config:
        for field, field_config in config["dropdown_fields"].items():
            if field_config == "dynamic_varietes":
                varietes = get_varietes_with_existing(df_full, field)
                column_config[field] = st.column_config.SelectboxColumn(
                    field.replace('_', ' ').title(), options=varietes, required=False)
            else:
                existing = df_full[field].dropna().unique().tolist() if field in df_full.columns else []
                all_options = sorted(list(set(existing + field_config)))
                column_config[field] = st.column_config.SelectboxColumn(
                    field.replace('_', ' ').title(), options=all_options, required=False)
    
    if 'original_df' not in st.session_state:
        st.session_state.original_df = df.copy()
    
    # Tableau
    edited_df = st.data_editor(
        df, use_container_width=True, num_rows="fixed",
        disabled=[config['primary_key']],
        column_config=column_config if column_config else None,
        key=f"editor_{selected_table}")
    
    # Boutons
    col1, col2 = st.columns([1, 5])
    with col1:
        if st.button("💾 Enregistrer", use_container_width=True, type="primary"):
            success, message = save_changes(selected_table, st.session_state.original_df, edited_df)
            if success:
                st.success(message)
                st.session_state.original_df = edited_df.copy()
                st.rerun()
            else:
                st.error(message)
    with col2:
        if st.button("🔄 Actualiser", use_container_width=True):
            st.session_state.pop('original_df', None)
            st.rerun()
    
    # Gestion activation
    st.markdown("---")
    st.subheader("🔒 Gestion activation")
    
    first_col = config['columns'][0]
    options = [f"{row[config['primary_key']]} - {row[first_col]}" for _, row in df_full.iterrows()]
    selected_record = st.selectbox(f"Sélectionner un élément à activer/désactiver", options, key="activation_selector")
    
    col_space1, col_btn1, col_btn2, col_space2 = st.columns([1, 1, 1, 1])
    
    with col_btn1:
        if st.button("🔒 Désactiver", use_container_width=True, type="secondary", key="btn_deactivate"):
            record_id = int(selected_record.split(" - ")[0])
            success, message = delete_record(selected_table, record_id)
            if success:
                st.success(message)
                st.session_state.pop('original_df', None)
                st.rerun()
            else:
                st.error(message)
    
    with col_btn2:
        if st.button("🔓 Réactiver", use_container_width=True, type="secondary", key="btn_reactivate"):
            record_id = int(selected_record.split(" - ")[0])
            success, message = reactivate_record(selected_table, record_id)
            if success:
                st.success(message)
                st.session_state.pop('original_df', None)
                st.rerun()
            else:
                st.error(message)
    
    # Exports
    st.markdown("---")
    st.subheader("📤 Exports")
    col1, col2 = st.columns(2)
    
    with col1:
        csv = df.to_csv(index=False).encode('utf-8')
        st.download_button("📥 CSV", csv, f"{config['table']}_{datetime.now().strftime('%Y%m%d')}.csv", "text/csv", use_container_width=True)
    
    with col2:
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name=selected_table)
        st.download_button("📥 Excel", buffer.getvalue(), f"{config['table']}_{datetime.now().strftime('%Y%m%d')}.xlsx",
                          "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)
else:
    st.warning(f"⚠️ Aucune donnée pour {selected_table}")

show_footer()
