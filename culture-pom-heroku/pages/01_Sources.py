import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime
import time
from database import get_connection
from components import show_footer
from auth import is_authenticated
import io
import json
import os
from streamlit_lottie import st_lottie

st.set_page_config(page_title="Sources - Culture Pom", page_icon="Ã°Å¸â€œâ€¹", layout="wide")

# CSS custom pour rÃƒÂ©duire FORTEMENT les espacements
st.markdown("""
<style>
    /* RÃƒÂ©duire espacement gÃƒÂ©nÃƒÂ©ral du container */
    .block-container {
        padding-top: 2rem !important;
        padding-bottom: 0.5rem !important;
        padding-left: 2rem !important;
        padding-right: 2rem !important;
    }
    
    /* RÃƒÂ©duire espacement autour de TOUS les titres */
    h1, h2, h3, h4 {
        margin-top: 0.3rem !important;
        margin-bottom: 0.3rem !important;
        padding-top: 0 !important;
        padding-bottom: 0 !important;
    }
    
    /* RÃƒÂ©duire espacement entre widgets */
    .stSelectbox, .stButton, .stCheckbox {
        margin-bottom: 0.3rem !important;
        margin-top: 0.3rem !important;
    }
    
    /* RÃƒÂ©duire espacement des data_editor */
    .stDataFrame {
        margin-top: 0.5rem !important;
        margin-bottom: 0.5rem !important;
    }
    
    /* RÃƒÂ©duire espacement des mÃƒÂ©triques */
    [data-testid="stMetricValue"] {
        font-size: 1.4rem !important;
    }
    
    [data-testid="metric-container"] {
        padding: 0.3rem !important;
    }
    
    /* RÃƒÂ©duire espacement markdown (lignes hr) */
    hr {
        margin-top: 0.5rem !important;
        margin-bottom: 0.5rem !important;
    }
    
    /* RÃƒÂ©duire espacement colonnes */
    [data-testid="column"] {
        padding: 0.2rem !important;
    }
    
    /* RÃƒÂ©duire espacement formulaires */
    .stForm {
        padding: 0.5rem !important;
        margin: 0.3rem !important;
    }
    
    /* RÃƒÂ©duire espacement subheaders */
    .stSubheader {
        margin-top: 0.3rem !important;
        margin-bottom: 0.3rem !important;
    }
</style>
""", unsafe_allow_html=True)

if not is_authenticated():
    st.warning("Ã¢Å¡Â Ã¯Â¸Â Veuillez vous connecter pour accÃƒÂ©der ÃƒÂ  cette page")
    st.stop()

# Ã¢Â­Â FONCTION CHARGEMENT ANIMATION LOTTIE
def load_lottie_file(filepath: str):
    """Charge une animation Lottie depuis un fichier local"""
    try:
        with open(filepath, "r") as f:
            return json.load(f)
    except:
        return None

# Charger l'animation confetti (fichier dans le mÃƒÂªme dossier que le script)
LOTTIE_PATH = os.path.join(os.path.dirname(__file__), "confetti_animation.json")
LOTTIE_CONFETTI = load_lottie_file(LOTTIE_PATH)

st.title("Ã°Å¸â€œâ€¹ Gestion des Tables de RÃƒÂ©fÃƒÂ©rence")
st.markdown("---")

# Ã¢Â­Â LISTES DE VALEURS POUR DROPDOWNS

# VariÃƒÂ©tÃƒÂ©s
VARIETES_TYPES = [
    "Chair ferme jaune",
    "Chair ferme rouge",
    "Fritable entrÃƒÂ©e de gamme",
    "Fritable haut de gamme",
    "Fritable milieu de gamme",
    "Poly",
    "Poly jaune",
    "Poly rouge"
]

VARIETES_UTILISATIONS = [
    "Four",
    "Four/Frites",
    "Four/Potage",
    "Four/Potage/Frites",
    "Four/PurÃƒÂ©e/Potage",
    "Four/PurÃƒÂ©e/Potage/Frites",
    "Frites",
    "Vapeur",
    "Vapeur/RissolÃƒÂ©es"
]

# Plants
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
    """RÃƒÂ©cupÃƒÂ¨re les codes variÃƒÂ©tÃƒÂ©s actifs depuis ref_varietes"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT code_variete FROM ref_varietes WHERE is_active = TRUE ORDER BY code_variete")
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        df = pd.DataFrame(rows, columns=['code_variete'])
        return df['code_variete'].tolist()
    except Exception as e:
        st.error(f"Ã¢ÂÅ’ Erreur chargement variÃƒÂ©tÃƒÂ©s : {str(e)}")
        return []

def get_varietes_with_existing(df, column_name):
    """RÃƒÂ©cupÃƒÂ¨re variÃƒÂ©tÃƒÂ©s actifs + valeurs dÃƒÂ©jÃƒÂ  prÃƒÂ©sentes dans le dataframe"""
    active = get_active_varietes()
    existing = df[column_name].dropna().unique().tolist() if column_name in df.columns else []
    return sorted(list(set(existing + active)))

# Ã¢Å“â€¦ TABLES_CONFIG CORRIGÃƒâ€° - TOUTES LES COLONNES EXACTES
TABLES_CONFIG = {
    "VariÃƒÂ©tÃƒÂ©s": {
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
        "filter_columns": ["nom_variete", "type", "utilisation"],
        "required_fields": ["code_variete", "nom_variete"]
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
        "filter_columns": ["libelle_long", "code_variete_base", "is_bio"],
        "required_fields": ["code_plant", "libelle_long"]
    },
    
    "Producteurs": {
        "table": "ref_producteurs",
        "columns": ["code_producteur", "nom", "code_postal", "ville", "departement", "telephone", "email", "nom_contact", "statut", "acheteur_referent", "global_gap", "is_active", "notes"],
        "hidden_columns": ["cle_producteur", "siret", "forme_juridique", "adresse", "adresse_complement", "pays", "latitude", "longitude", "prenom_contact", "type_contrat"],
        "primary_key": "id",
        "editable": ["nom", "code_postal", "ville", "telephone", "email", "nom_contact", "statut", "acheteur_referent", "global_gap", "is_active", "notes"],
        "has_updated_at": True,
        "filter_columns": ["nom", "departement", "acheteur_referent", "global_gap"],
        "required_fields": ["code_producteur", "nom"]
    },
    
    "Sites Stockage": {
        "table": "ref_sites_stockage",
        "columns": ["code_site", "code_emplacement", "nom_complet", "adresse", "capacite_max_pallox", "capacite_max_tonnes", "is_active", "notes"],
        "hidden_columns": ["cle_unique", "type_site"],
        "primary_key": "id",
        "editable": ["nom_complet", "adresse", "capacite_max_pallox", "capacite_max_tonnes", "is_active", "notes"],
        "has_updated_at": True,
        "auto_cle_unique": True,
        "required_fields": ["code_site", "code_emplacement", "nom_complet"]
    },
    
    "Types DÃƒÂ©chets": {
        "table": "ref_types_dechets",
        "columns": ["code", "libelle", "description", "is_active"],
        "primary_key": "id",
        "editable": ["libelle", "description", "is_active"],
        "has_updated_at": False,
        "required_fields": ["code", "libelle"]
    },
    
    "Emballages": {
        "table": "ref_emballages",
        "columns": ["code_emballage", "atelier", "poids_unitaire", "unite_poids", "nbr_uvc", "type_produit", "is_active", "notes"],
        "hidden_columns": ["sur_emballage"],
        "primary_key": "id",
        "editable": ["atelier", "poids_unitaire", "unite_poids", "nbr_uvc", "type_produit", "is_active", "notes"],
        "has_updated_at": True,
        "filter_columns": ["atelier", "code_emballage", "type_produit"],
        "required_fields": ["code_emballage"]
    },
    
    "Produits Commerciaux": {
        "table": "ref_produits_commerciaux",
        "columns": ["code_produit", "marque", "libelle", "poids_unitaire", "unite_poids", "type_produit", "code_variete", "is_bio", "is_active", "notes"],
        "primary_key": "id",
        "editable": ["marque", "libelle", "poids_unitaire", "unite_poids", "type_produit", "code_variete", "is_bio", "is_active", "notes"],
        "has_updated_at": True,
        "required_fields": ["code_produit", "marque", "libelle"]
    }
}

def load_table_data(table_name, show_inactive=False):
    """Charge les donnÃƒÂ©es d'une table"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        config = TABLES_CONFIG[table_name]
        
        # Ã¢Â­Â Charger toutes les colonnes (visibles + cachÃƒÂ©es) pour modifications
        all_columns = config["columns"].copy()
        if "hidden_columns" in config:
            all_columns.extend(config["hidden_columns"])
        
        columns_str = ", ".join(all_columns)
        
        # Ã¢Â­Â Filtrer par is_active si show_inactive = False
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
        
        # Ã¢Â­Â CALCULER dÃƒÂ©partement automatiquement depuis code_postal (2 premiers caractÃƒÂ¨res)
        if 'code_postal' in df.columns and 'departement' in df.columns:
            df['departement'] = df['code_postal'].apply(
                lambda x: str(x)[:2] if pd.notna(x) and str(x).strip() != '' else None
            )
        
        # Ã¢Â­Â Ne garder que les colonnes visibles pour l'affichage
        display_columns = [config['primary_key']] + config['columns']
        df_display = df[display_columns].copy()
        
        # Stocker le df complet en session pour les updates
        st.session_state[f'full_df_{table_name}'] = df
        
        return df_display
        
    except Exception as e:
        st.error(f"Ã¢ÂÅ’ Erreur : {str(e)}")
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
        
        # Ã¢Â­Â RÃƒÂ©cupÃƒÂ©rer le df complet avec colonnes cachÃƒÂ©es
        full_df = st.session_state.get(f'full_df_{table_name}')
        
        for idx in edited_df.index:
            if idx not in original_df.index:
                continue
            
            row_id = convert_to_native_types(edited_df.loc[idx, config['primary_key']])
            changes = {}
            
            # Colonnes visibles ÃƒÂ©ditÃƒÂ©es
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
        return True, f"Ã¢Å“â€¦ {updates} enregistrement(s) mis ÃƒÂ  jour"
        
    except Exception as e:
        if 'conn' in locals():
            conn.rollback()
        
        # Ã¢Â­Â RENDRE LES ERREURS COMPRÃƒâ€°HENSIBLES
        error_msg = str(e).lower()
        
        # Erreur : Code/clÃƒÂ© dÃƒÂ©jÃƒÂ  existant
        if "duplicate key" in error_msg or "unique constraint" in error_msg:
            if "code_producteur" in error_msg:
                return False, "Ã¢ÂÅ’ Ce code producteur est dÃƒÂ©jÃƒÂ  utilisÃƒÂ© par un autre enregistrement."
            elif "code_plant" in error_msg:
                return False, "Ã¢ÂÅ’ Ce code plant est dÃƒÂ©jÃƒÂ  utilisÃƒÂ© par un autre enregistrement."
            elif "code_variete" in error_msg:
                return False, "Ã¢ÂÅ’ Ce code variÃƒÂ©tÃƒÂ© est dÃƒÂ©jÃƒÂ  utilisÃƒÂ© par un autre enregistrement."
            elif "code_site" in error_msg:
                return False, "Ã¢ÂÅ’ Ce code site est dÃƒÂ©jÃƒÂ  utilisÃƒÂ© par un autre enregistrement."
            elif "code_emballage" in error_msg:
                return False, "Ã¢ÂÅ’ Ce code emballage est dÃƒÂ©jÃƒÂ  utilisÃƒÂ© par un autre enregistrement."
            elif "code_produit" in error_msg:
                return False, "Ã¢ÂÅ’ Ce code produit est dÃƒÂ©jÃƒÂ  utilisÃƒÂ© par un autre enregistrement."
            else:
                return False, "Ã¢ÂÅ’ Cette valeur est dÃƒÂ©jÃƒÂ  utilisÃƒÂ©e. Impossible de modifier."
        
        # Erreur : Champ obligatoire manquant
        elif "not null" in error_msg or "null value" in error_msg:
            return False, "Ã¢ÂÅ’ Un champ obligatoire ne peut pas ÃƒÂªtre vide."
        
        # Autres erreurs
        else:
            return False, f"Ã¢ÂÅ’ Erreur : {str(e)}"

def delete_record(table_name, record_id):
    """DÃƒÂ©sactive un enregistrement (soft delete)"""
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
        return True, "Ã¢Å“â€¦ DÃƒÂ©sactivÃƒÂ©"
        
    except Exception as e:
        if 'conn' in locals():
            conn.rollback()
        return False, f"Ã¢ÂÅ’ Erreur : {str(e)}"

def reactivate_record(table_name, record_id):
    """RÃƒÂ©active un enregistrement"""
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
        return True, "Ã¢Å“â€¦ RÃƒÂ©activÃƒÂ©"
        
    except Exception as e:
        if 'conn' in locals():
            conn.rollback()
        return False, f"Ã¢ÂÅ’ Erreur : {str(e)}"

def add_record(table_name, data):
    """Ajoute un enregistrement"""
    try:
        config = TABLES_CONFIG[table_name]
        conn = get_connection()
        cursor = conn.cursor()
        
        # Ã¢Â­Â GÃƒÂ©nÃƒÂ©rer cle_unique pour Sites Stockage
        if config.get('auto_cle_unique'):
            if 'code_site' in data and 'code_emplacement' in data:
                data['cle_unique'] = f"{data['code_site']}_{data['code_emplacement']}"
        
        # Ã¢Â­Â Ajouter colonnes cachÃƒÂ©es avec valeurs NULL si besoin
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
        return True, "Ã¢Å“â€¦ AjoutÃƒÂ© avec succÃƒÂ¨s"
        
    except Exception as e:
        if 'conn' in locals():
            conn.rollback()
        
        # Ã¢Â­Â RENDRE LES ERREURS COMPRÃƒâ€°HENSIBLES
        error_msg = str(e).lower()
        
        # Erreur : Code/clÃƒÂ© dÃƒÂ©jÃƒÂ  existant
        if "duplicate key" in error_msg or "unique constraint" in error_msg:
            # Extraire le nom du champ
            if "code_producteur" in error_msg:
                return False, "Ã¢ÂÅ’ Ce code producteur est dÃƒÂ©jÃƒÂ  utilisÃƒÂ©. Merci de choisir un autre code."
            elif "code_plant" in error_msg:
                return False, "Ã¢ÂÅ’ Ce code plant est dÃƒÂ©jÃƒÂ  utilisÃƒÂ©. Merci de choisir un autre code."
            elif "code_variete" in error_msg:
                return False, "Ã¢ÂÅ’ Ce code variÃƒÂ©tÃƒÂ© est dÃƒÂ©jÃƒÂ  utilisÃƒÂ©. Merci de choisir un autre code."
            elif "code_site" in error_msg:
                return False, "Ã¢ÂÅ’ Ce code site est dÃƒÂ©jÃƒÂ  utilisÃƒÂ©. Merci de choisir un autre code."
            elif "code_emballage" in error_msg:
                return False, "Ã¢ÂÅ’ Ce code emballage est dÃƒÂ©jÃƒÂ  utilisÃƒÂ©. Merci de choisir un autre code."
            elif "code_produit" in error_msg:
                return False, "Ã¢ÂÅ’ Ce code produit est dÃƒÂ©jÃƒÂ  utilisÃƒÂ©. Merci de choisir un autre code."
            else:
                return False, "Ã¢ÂÅ’ Cette valeur est dÃƒÂ©jÃƒÂ  utilisÃƒÂ©e. Merci de choisir une autre valeur."
        
        # Erreur : Champ obligatoire manquant
        elif "not null" in error_msg or "null value" in error_msg:
            return False, "Ã¢ÂÅ’ Un champ obligatoire est manquant. Veuillez vÃƒÂ©rifier votre saisie."
        
        # Autres erreurs (afficher message technique)
        else:
            return False, f"Ã¢ÂÅ’ Erreur : {str(e)}"

# Interface - SÃƒÂ©lection table
selected_table = st.selectbox("Ã°Å¸â€œâ€¹ Table", list(TABLES_CONFIG.keys()), key="table_selector")

st.markdown("---")

# Ã¢Â­Â Formulaire ajout - SANS st.form()
if st.session_state.get('show_add_form', False):
    st.subheader(f"Ã¢Å¾â€¢ Ajouter - {selected_table}")
    config = TABLES_CONFIG[selected_table]
    
    # Ã¢Â­Â Afficher liste champs obligatoires
    if "required_fields" in config:
        required_fields_str = ", ".join([f.replace('_', ' ').title() for f in config["required_fields"]])
        st.info(f"Ã°Å¸â€œÅ’ Champs obligatoires : **{required_fields_str}**")
    
    # Initialiser session_state
    if 'new_data' not in st.session_state:
        st.session_state.new_data = {}
    
    col1, col2 = st.columns(2)
    
    for i, col in enumerate(config['columns']):
        # Ã¢Â­Â Marquer champs obligatoires avec astÃƒÂ©risque
        label = col.replace('_', ' ').title()
        if "required_fields" in config and col in config["required_fields"]:
            label = f"{label} *"
        
        with col1 if i % 2 == 0 else col2:
            # Ã¢Â­Â Dropdowns pour champs spÃƒÂ©cifiques
            if "dropdown_fields" in config and col in config["dropdown_fields"]:
                field_config = config["dropdown_fields"][col]
                
                # Ã¢Â­Â Dropdown dynamique pour code_variete_base
                if field_config == "dynamic_varietes":
                    varietes = get_active_varietes()
                    options = [""] + varietes
                    st.session_state.new_data[col] = st.selectbox(
                        label,
                        options=options,
                        key=f"add_{col}"
                    )
                # Dropdown statique
                else:
                    options = [""] + field_config
                    st.session_state.new_data[col] = st.selectbox(
                        label,
                        options=options,
                        key=f"add_{col}"
                    )
            elif col in ['is_active', 'is_bio', 'global_gap']:
                st.session_state.new_data[col] = st.checkbox(label, value=True, key=f"add_{col}")
            elif 'capacite' in col or 'prix' in col or 'poids' in col:
                st.session_state.new_data[col] = st.number_input(label, min_value=0.0, value=0.0, step=0.1, key=f"add_{col}")
            elif 'nbr' in col:
                st.session_state.new_data[col] = st.number_input(label, min_value=0, value=0, step=1, key=f"add_{col}")
            else:
                st.session_state.new_data[col] = st.text_input(label, key=f"add_{col}")
    
    # Boutons
    col1, col2 = st.columns([1, 1])
    with col1:
        if st.button("Ã°Å¸â€™Â¾ Enregistrer", use_container_width=True, type="primary", key="btn_save_add"):
            # Ã¢Â­Â VALIDATION EXPLICITE des champs obligatoires
            missing_fields = []
            if "required_fields" in config:
                for field in config["required_fields"]:
                    if field not in st.session_state.new_data or not st.session_state.new_data[field] or st.session_state.new_data[field] == '':
                        missing_fields.append(field.replace('_', ' ').title())
            
            if missing_fields:
                st.error(f"Ã¢ÂÅ’ Champs obligatoires manquants : {', '.join(missing_fields)}")
            else:
                # Ã¢Â­Â Filtrer les donnÃƒÂ©es
                filtered_data = {}
                for k, v in st.session_state.new_data.items():
                    # Garder False (checkboxes dÃƒÂ©cochÃƒÂ©es)
                    if isinstance(v, bool):
                        filtered_data[k] = v
                    # Garder 0 (nombres)
                    elif isinstance(v, (int, float)) and v == 0:
                        filtered_data[k] = v
                    # Exclure chaÃƒÂ®nes vides et None
                    elif v != '' and v is not None:
                        filtered_data[k] = v
                
                success, message = add_record(selected_table, filtered_data)
                if success:
                    st.success(message)
                    # Ã¢Â­Â Animation confettis Lottie
                    if LOTTIE_CONFETTI:
                        # CrÃ©er colonnes pour centrer l'animation
                        col1, col2, col3 = st.columns([1, 2, 1])
                        with col2:
                            st_lottie(LOTTIE_CONFETTI, height=400, key="confetti_success")
                        time.sleep(2)
                    else:
                        # Fallback si fichier non trouvÃƒÂ©
                        st.balloons()
                        time.sleep(1.5)
                    st.session_state.show_add_form = False
                    st.session_state.pop('new_data', None)
                    st.rerun()
                else:
                    st.error(message)
    
    with col2:
        if st.button("Ã¢ÂÅ’ Annuler", use_container_width=True, key="btn_cancel_add"):
            st.session_state.show_add_form = False
            st.session_state.pop('new_data', None)
            st.rerun()
    
    st.markdown("---")

# Ã¢Â­Â Toggle pour afficher/masquer les inactifs
show_inactive = st.checkbox("Ã°Å¸â€˜ÂÃ¯Â¸Â Afficher les ÃƒÂ©lÃƒÂ©ments inactifs", value=False, key=f"show_inactive_{selected_table}")

# Charger donnÃƒÂ©es avec filtre
df_full = load_table_data(selected_table, show_inactive=show_inactive)

if not df_full.empty:
    config = TABLES_CONFIG[selected_table]
    
    # MÃƒÂ©triques (sur donnÃƒÂ©es complÃƒÂ¨tes avant filtrage)
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Ã°Å¸â€œÅ  Total", len(df_full))
    with col2:
        actifs = df_full['is_active'].sum() if 'is_active' in df_full.columns else len(df_full)
        st.metric("Ã¢Å“â€¦ Actifs", actifs)
    with col3:
        inactifs = len(df_full) - actifs if 'is_active' in df_full.columns else 0
        st.metric("Ã¢ÂÅ’ Inactifs", inactifs)
    
    st.markdown("---")
    
    # Ã¢Â­Â FILTRES (colonnes les plus importantes)
    df = df_full.copy()  # Copie pour filtrage
    
    if "filter_columns" in config:
        st.markdown("#### Ã°Å¸â€Â Filtres")
        filter_cols = st.columns(len(config["filter_columns"]))
        filters = {}
        
        for i, col_name in enumerate(config["filter_columns"]):
            with filter_cols[i]:
                if col_name in df.columns:
                    # Ã¢Â­Â Traitement spÃƒÂ©cial pour boolean (is_bio, global_gap)
                    if col_name in ["is_bio", "global_gap"]:
                        bool_options = ["Tous", "OUI", "NON"]
                        label = "Bio" if col_name == "is_bio" else "Global Gap"
                        filters[col_name] = st.selectbox(
                            label,
                            bool_options,
                            key=f"filter_{col_name}"
                        )
                    else:
                        unique_values = ["Tous"] + sorted([str(v) for v in df[col_name].dropna().unique()])
                        filters[col_name] = st.selectbox(
                            col_name.replace('_', ' ').title(),
                            unique_values,
                            key=f"filter_{col_name}"
                        )
        
        # Appliquer les filtres
        for col_name, selected_value in filters.items():
            if selected_value != "Tous":
                if col_name in ["is_bio", "global_gap"]:
                    # Filtrer par boolean
                    if selected_value == "OUI":
                        df = df[df[col_name] == True]
                    elif selected_value == "NON":
                        df = df[df[col_name] == False]
                else:
                    df = df[df[col_name].astype(str) == selected_value]
        
        # Afficher nombre de rÃƒÂ©sultats filtrÃƒÂ©s
        if len(df) != len(df_full):
            st.info(f"Ã°Å¸â€Â {len(df)} rÃƒÂ©sultat(s) aprÃƒÂ¨s filtrage (sur {len(df_full)} total)")
        
        st.markdown("---")
    
    # Ã¢Â­Â En-tÃƒÂªte table avec bouton Ajouter alignÃƒÂ© ÃƒÂ  droite
    col_title, col_button = st.columns([4, 1])
    with col_title:
        st.subheader(f"Ã°Å¸â€œâ€¹ {selected_table}")
    with col_button:
        if st.button("Ã¢Å¾â€¢ Ajouter", use_container_width=True, type="primary"):
            st.session_state.show_add_form = not st.session_state.get('show_add_form', False)
            st.rerun()
    
    # Ã¢Â­Â Configuration colonnes pour data_editor avec dropdowns
    column_config = {}
    if "dropdown_fields" in config:
        for field, field_config in config["dropdown_fields"].items():
            # Ã¢Â­Â Dropdown dynamique
            if field_config == "dynamic_varietes":
                varietes = get_varietes_with_existing(df_full, field)
                column_config[field] = st.column_config.SelectboxColumn(
                    field.replace('_', ' ').title(),
                    options=varietes,
                    required=False
                )
            # Dropdown statique
            else:
                # Ã¢Â­Â Inclure valeurs existantes aussi pour listes statiques
                existing = df_full[field].dropna().unique().tolist() if field in df_full.columns else []
                all_options = sorted(list(set(existing + field_config)))
                column_config[field] = st.column_config.SelectboxColumn(
                    field.replace('_', ' ').title(),
                    options=all_options,
                    required=False
                )
    
    # Initialiser original_df
    if 'original_df' not in st.session_state:
        st.session_state.original_df = df.copy()
    
    # Tableau
    edited_df = st.data_editor(
        df,
        use_container_width=True,
        num_rows="fixed",
        disabled=[config['primary_key']],
        column_config=column_config if column_config else None,
        key=f"editor_{selected_table}"
    )
    
    # Boutons
    col1, col2 = st.columns([1, 5])
    with col1:
        if st.button("Ã°Å¸â€™Â¾ Enregistrer", use_container_width=True, type="primary"):
            success, message = save_changes(selected_table, st.session_state.original_df, edited_df)
            if success:
                st.success(message)
                st.session_state.original_df = edited_df.copy()
                st.rerun()
            else:
                st.error(message)
    with col2:
        if st.button("Ã°Å¸â€â€ž Actualiser", use_container_width=True):
            st.session_state.pop('original_df', None)
            st.rerun()
    
    # DÃƒÂ©sactivation / RÃƒÂ©activation
    st.markdown("---")
    st.subheader("Ã°Å¸â€â€™ Gestion activation")
    
    # Dropdown pleine largeur
    first_col = config['columns'][0]
    options = [f"{row[config['primary_key']]} - {row[first_col]}" for _, row in df_full.iterrows()]
    selected_record = st.selectbox(
        f"SÃƒÂ©lectionner un ÃƒÂ©lÃƒÂ©ment ÃƒÂ  activer/dÃƒÂ©sactiver",
        options,
        key="activation_selector"
    )
    
    # Boutons centrÃƒÂ©s en dessous
    col_space1, col_btn1, col_btn2, col_space2 = st.columns([1, 1, 1, 1])
    
    with col_btn1:
        if st.button("Ã°Å¸â€â€™ DÃƒÂ©sactiver", use_container_width=True, type="secondary", key="btn_deactivate"):
            record_id = int(selected_record.split(" - ")[0])
            success, message = delete_record(selected_table, record_id)
            if success:
                st.success(message)
                st.session_state.pop('original_df', None)
                st.rerun()
            else:
                st.error(message)
    
    with col_btn2:
        if st.button("Ã°Å¸â€â€œ RÃƒÂ©activer", use_container_width=True, type="secondary", key="btn_reactivate"):
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
    st.subheader("Ã°Å¸â€œÂ¤ Exports")
    col1, col2 = st.columns(2)
    
    with col1:
        csv = df.to_csv(index=False).encode('utf-8')
        st.download_button("Ã°Å¸â€œÂ¥ CSV", csv, f"{config['table']}_{datetime.now().strftime('%Y%m%d')}.csv", 
                          "text/csv", use_container_width=True)
    
    with col2:
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name=selected_table)
        st.download_button("Ã°Å¸â€œÂ¥ Excel", buffer.getvalue(), f"{config['table']}_{datetime.now().strftime('%Y%m%d')}.xlsx",
                          "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)
else:
    st.warning(f"Ã¢Å¡Â Ã¯Â¸Â Aucune donnÃƒÂ©e pour {selected_table}")

show_footer()
