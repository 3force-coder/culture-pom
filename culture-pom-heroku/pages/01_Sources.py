import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime
import time
from database import get_connection
from components import show_footer
from auth import is_authenticated
import io
import streamlit.components.v1 as components

# ⭐ FONCTION SIDEBAR USER INFO
def show_user_info():
    """Affiche les infos utilisateur dans la sidebar"""
    if st.session_state.get('authenticated', False):
        with st.sidebar:
            st.markdown("---")
            st.write(f"👤 {st.session_state.get('name', 'Utilisateur')}")
            st.caption(f"📧 {st.session_state.get('email', '')}")
            st.caption(f"🔑 {st.session_state.get('role', 'USER')}")
            st.markdown("---")
            
            if st.button("🚪 Déconnexion", use_container_width=True, key="btn_logout_sidebar"):
                for key in list(st.session_state.keys()):
                    del st.session_state[key]
                st.rerun()

st.set_page_config(page_title="Sources - Culture Pom", page_icon="📋", layout="wide")

# CSS custom pour réduire FORTEMENT les espacements
st.markdown("""
<style>
    /* Réduire espacement général du container */
    .block-container {
        padding-top: 2rem !important;
        padding-bottom: 0.5rem !important;
        padding-left: 2rem !important;
        padding-right: 2rem !important;
    }
    
    /* Réduire espacement autour de TOUS les titres */
    h1, h2, h3, h4 {
        margin-top: 0.3rem !important;
        margin-bottom: 0.3rem !important;
        padding-top: 0 !important;
        padding-bottom: 0 !important;
    }
    
    /* Réduire espacement entre widgets */
    .stSelectbox, .stButton, .stCheckbox {
        margin-bottom: 0.3rem !important;
        margin-top: 0.3rem !important;
    }
    
    /* Réduire espacement des data_editor */
    .stDataFrame {
        margin-top: 0.5rem !important;
        margin-bottom: 0.5rem !important;
    }
    
    /* Réduire espacement des métriques */
    [data-testid="stMetricValue"] {
        font-size: 1.4rem !important;
    }
    
    [data-testid="metric-container"] {
        padding: 0.3rem !important;
    }
    
    /* Réduire espacement markdown (lignes hr) */
    hr {
        margin-top: 0.5rem !important;
        margin-bottom: 0.5rem !important;
    }
    
    /* Réduire espacement colonnes */
    [data-testid="column"] {
        padding: 0.2rem !important;
    }
    
    /* Réduire espacement formulaires */
    .stForm {
        padding: 0.5rem !important;
        margin: 0.3rem !important;
    }
    
    /* Réduire espacement subheaders */
    .stSubheader {
        margin-top: 0.3rem !important;
        margin-bottom: 0.3rem !important;
    }
</style>
""", unsafe_allow_html=True)

if not is_authenticated():
    st.warning("⚠️ Veuillez vous connecter pour accéder à cette page")
    st.stop()

# ⭐ Afficher bloc utilisateur dans sidebar
show_user_info()

# ⭐ FONCTION ANIMATION LOTTIE
def show_confetti_animation():
    """Affiche l'animation confetti Lottie via web component"""
    confetti_html = """
    <script src="https://unpkg.com/@lottiefiles/dotlottie-wc@0.8.5/dist/dotlottie-wc.js" type="module"></script>
    <div style="display: flex; justify-content: center; align-items: center;">
        <dotlottie-wc 
            src="https://lottie.host/21b8e802-34df-4b54-89ca-4c7843e1da14/AoYf85WPKi.lottie" 
            style="width: 300px; height: 300px" 
            autoplay>
        </dotlottie-wc>
    </div>
    """
    components.html(confetti_html, height=320)

st.title("📋 Gestion des Tables de Référence")
st.markdown("---")

# ⭐ LISTES DE VALEURS POUR DROPDOWNS

# Variétés
VARIETES_TYPES = [
    "Chair ferme jaune",
    "Chair ferme rouge",
    "Fritable entrée de gamme",
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
    "Four/Purée/Potage",
    "Four/Purée/Potage/Frites",
    "Frites",
    "Vapeur",
    "Vapeur/Rissolées"
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
    """Récupère les codes variétés actifs depuis ref_varietes"""
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
        st.error(f"❌ Erreur chargement variétés : {str(e)}")
        return []

def get_varietes_with_existing(df, column_name):
    """Récupère variétés actifs + valeurs déjà présentes dans le dataframe"""
    active = get_active_varietes()
    existing = df[column_name].dropna().unique().tolist() if column_name in df.columns else []
    return sorted(list(set(existing + active)))

def get_unique_values_from_column(df, column_name):
    """Récupère toutes les valeurs uniques d'une colonne depuis le dataframe"""
    if column_name not in df.columns:
        return []
    values = df[column_name].dropna().unique().tolist()
    # Filtrer les chaînes vides
    values = [str(v) for v in values if str(v).strip() != '']
    return sorted(list(set(values)))

# ✅ TABLES_CONFIG CORRIGÉ - TOUTES LES COLONNES EXACTES
TABLES_CONFIG = {
    "Variétés": {
        "table": "ref_varietes",
        "columns": ["code_variete", "nom_variete", "type", "utilisation", "notes"],
        "hidden_columns": ["couleur_peau", "couleur_chair", "precocite", "is_active"],
        "primary_key": "id",
        "editable": ["nom_variete", "type", "utilisation", "notes"],
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
        "columns": ["code_plant", "libelle_long", "code_variete_base", "calibre", "is_bio", "notes"],
        "hidden_columns": ["poids_unite", "is_active"],
        "primary_key": "id",
        "editable": ["libelle_long", "code_variete_base", "calibre", "is_bio", "notes"],
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
        "columns": ["code_producteur", "nom", "code_postal", "ville", "departement", "telephone", "email", "nom_contact", "statut", "acheteur_referent", "global_gap", "notes"],
        "hidden_columns": ["cle_producteur", "siret", "forme_juridique", "adresse", "adresse_complement", "pays", "latitude", "longitude", "prenom_contact", "type_contrat", "is_active"],
        "primary_key": "id",
        "editable": ["nom", "code_postal", "ville", "telephone", "email", "nom_contact", "statut", "acheteur_referent", "global_gap", "notes"],
        "has_updated_at": True,
        "filter_columns": ["nom", "departement", "acheteur_referent", "global_gap"],
        "required_fields": ["code_producteur", "nom"]
    },
    
    "Sites Stockage": {
        "table": "ref_sites_stockage",
        "columns": ["code_site", "code_emplacement", "nom_complet", "adresse", "capacite_max_pallox", "capacite_max_tonnes", "notes"],
        "hidden_columns": ["cle_unique", "is_active"],
        "primary_key": "id",
        "editable": ["nom_complet", "adresse", "capacite_max_pallox", "capacite_max_tonnes", "notes"],
        "has_updated_at": True,
        "auto_cle_unique": True,
        "required_fields": ["code_site", "code_emplacement", "nom_complet"]
    },
    
    "Types Déchets": {
        "table": "ref_types_dechets",
        "columns": ["code", "libelle", "description"],
        "hidden_columns": ["is_active"],
        "primary_key": "id",
        "editable": ["libelle", "description"],
        "has_updated_at": False,
        "required_fields": ["code", "libelle"]
    },
    
    "Code Emballage": {
        "table": "ref_emballages",
        "columns": ["code_emballage", "atelier", "poids_unitaire", "unite_poids", "poids", "nbr_uvc", "type_produit", "sur_emballage"],
        "hidden_columns": ["notes", "is_active"],
        "primary_key": "id",
        "editable": ["atelier", "poids_unitaire", "unite_poids", "nbr_uvc", "type_produit", "sur_emballage"],
        "has_updated_at": True,
        "dropdown_fields": {
            "atelier": "dynamic_from_db",
            "unite_poids": "dynamic_from_db",
            "type_produit": "dynamic_from_db",
            "sur_emballage": "dynamic_from_db"
        },
        "filter_columns": ["poids", "atelier", "type_produit"],
        "required_fields": ["code_emballage"],
        "calculated_columns": {
            "poids": ["poids_unitaire", "unite_poids"]
        }
    },
    
    "Produits Commerciaux": {
        "table": "ref_produits_commerciaux",
        "columns": ["code_produit", "marque", "libelle", "poids_unitaire", "unite_poids", "poids", "type_produit", "code_variete"],
        "hidden_columns": ["is_bio", "notes", "is_active"],
        "primary_key": "id",
        "editable": ["marque", "libelle", "poids_unitaire", "unite_poids", "type_produit", "code_variete"],
        "has_updated_at": True,
        "dropdown_fields": {
            "marque": "dynamic_from_db",
            "unite_poids": "dynamic_from_db",
            "type_produit": "dynamic_from_db",
            "code_variete": "dynamic_varietes"
        },
        "filter_columns": ["poids", "marque", "type_produit"],
        "required_fields": ["code_produit", "marque", "libelle"],
        "calculated_columns": {
            "poids": ["poids_unitaire", "unite_poids"]
        }
    }
}

def load_table_data(table_name, show_inactive=False):
    """Charge les données d'une table"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        config = TABLES_CONFIG[table_name]
        
        # ⭐ Charger toutes les colonnes (visibles + cachées) pour modifications
        all_columns = config["columns"].copy()
        if "hidden_columns" in config:
            all_columns.extend(config["hidden_columns"])
        
        # ⭐ Retirer les colonnes calculées de la requête SQL
        sql_columns = [col for col in all_columns if col not in config.get("calculated_columns", {})]
        
        columns_str = ", ".join(sql_columns)
        
        # ⭐ Filtrer par is_active si show_inactive = False
        where_clause = ""
        if not show_inactive and 'is_active' in sql_columns:
            where_clause = " WHERE is_active = TRUE"
        
        query = f"SELECT {config['primary_key']}, {columns_str} FROM {config['table']}{where_clause} ORDER BY {config['primary_key']}"
        cursor.execute(query)
        
        rows = cursor.fetchall()
        columns = [config['primary_key']] + sql_columns
        cursor.close()
        conn.close()
        
        df = pd.DataFrame(rows, columns=columns)
        
        # ⭐ CALCULER département automatiquement depuis code_postal (2 premiers caractères)
        if 'code_postal' in df.columns and 'departement' in df.columns:
            df['departement'] = df['code_postal'].apply(
                lambda x: str(x)[:2] if pd.notna(x) and str(x).strip() != '' else None
            )
        
        # ⭐ CALCULER colonnes Poids (poids_unitaire + unite_poids)
        if "calculated_columns" in config and "poids" in config["calculated_columns"]:
            source_cols = config["calculated_columns"]["poids"]
            if all(col in df.columns for col in source_cols):
                df['poids'] = df.apply(
                    lambda row: f"{row[source_cols[0]]} {row[source_cols[1]]}" 
                    if pd.notna(row[source_cols[0]]) and pd.notna(row[source_cols[1]]) 
                    else "", 
                    axis=1
                )
        
        # ⭐ Ne garder que les colonnes visibles pour l'affichage
        display_columns = [config['primary_key']] + config['columns']
        df_display = df[display_columns].copy()
        
        # Stocker le df complet en session pour les updates
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
        
        # ⭐ Récupérer le df complet avec colonnes cachées
        full_df = st.session_state.get(f'full_df_{table_name}')
        
        for idx in edited_df.index:
            if idx not in original_df.index:
                continue
            
            row_id = convert_to_native_types(edited_df.loc[idx, config['primary_key']])
            changes = {}
            
            # Colonnes visibles éditées
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
        
        # ⭐ RENDRE LES ERREURS COMPRÉHENSIBLES
        error_msg = str(e).lower()
        
        # Erreur : Code/clé déjà existant
        if "duplicate key" in error_msg or "unique constraint" in error_msg:
            if "code_producteur" in error_msg:
                return False, "❌ Ce code producteur est déjà utilisé par un autre enregistrement."
            elif "code_plant" in error_msg:
                return False, "❌ Ce code plant est déjà utilisé par un autre enregistrement."
            elif "code_variete" in error_msg:
                return False, "❌ Ce code variété est déjà utilisé par un autre enregistrement."
            elif "code_site" in error_msg:
                return False, "❌ Ce code site est déjà utilisé par un autre enregistrement."
            elif "code_emballage" in error_msg:
                return False, "❌ Ce code emballage est déjà utilisé par un autre enregistrement."
            elif "code_produit" in error_msg:
                return False, "❌ Ce code produit est déjà utilisé par un autre enregistrement."
            else:
                return False, "❌ Cette valeur est déjà utilisée. Impossible de modifier."
        
        # Erreur : Champ obligatoire manquant
        elif "not null" in error_msg or "null value" in error_msg:
            return False, "❌ Un champ obligatoire ne peut pas être vide."
        
        # Autres erreurs
        else:
            return False, f"❌ Erreur : {str(e)}"

def delete_record(table_name, record_id):
    """Désactive un enregistrement (soft delete)"""
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
    """Ajoute un enregistrement"""
    try:
        config = TABLES_CONFIG[table_name]
        conn = get_connection()
        cursor = conn.cursor()
        
        # ⭐ Générer cle_unique pour Sites Stockage
        if config.get('auto_cle_unique'):
            if 'code_site' in data and 'code_emplacement' in data:
                data['cle_unique'] = f"{data['code_site']}_{data['code_emplacement']}"
        
        # ⭐ Retirer les colonnes calculées (n'existent pas en DB)
        if "calculated_columns" in config:
            for calc_col in config["calculated_columns"].keys():
                data.pop(calc_col, None)
        
        # ⭐ Ajouter colonnes cachées avec valeurs NULL si besoin
        if "hidden_columns" in config:
            for col in config["hidden_columns"]:
                if col not in data and col != "is_active":
                    data[col] = None
        
        # ⭐ Ajouter is_active = TRUE par défaut
        if "is_active" in config.get("hidden_columns", []):
            data["is_active"] = True
        
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
        return True, "✅ Ajouté avec succès"
        
    except Exception as e:
        if 'conn' in locals():
            conn.rollback()
        
        # ⭐ RENDRE LES ERREURS COMPRÉHENSIBLES
        error_msg = str(e).lower()
        
        # Erreur : Code/clé déjà existant
        if "duplicate key" in error_msg or "unique constraint" in error_msg:
            # Extraire le nom du champ
            if "code_producteur" in error_msg:
                return False, "❌ Ce code producteur est déjà utilisé. Merci de choisir un autre code."
            elif "code_plant" in error_msg:
                return False, "❌ Ce code plant est déjà utilisé. Merci de choisir un autre code."
            elif "code_variete" in error_msg:
                return False, "❌ Ce code variété est déjà utilisé. Merci de choisir un autre code."
            elif "code_site" in error_msg:
                return False, "❌ Ce code site est déjà utilisé. Merci de choisir un autre code."
            elif "code_emballage" in error_msg:
                return False, "❌ Ce code emballage est déjà utilisé. Merci de choisir un autre code."
            elif "code_produit" in error_msg:
                return False, "❌ Ce code produit est déjà utilisé. Merci de choisir un autre code."
            else:
                return False, "❌ Cette valeur est déjà utilisée. Merci de choisir une autre valeur."
        
        # Erreur : Champ obligatoire manquant
        elif "not null" in error_msg or "null value" in error_msg:
            return False, "❌ Un champ obligatoire est manquant. Veuillez vérifier votre saisie."
        
        # Autres erreurs (afficher message technique)
        else:
            return False, f"❌ Erreur : {str(e)}"

# Interface - Sélection table
selected_table = st.selectbox("📋 Table", list(TABLES_CONFIG.keys()), key="table_selector")

st.markdown("---")

# ⭐ Formulaire ajout - SANS st.form()
if st.session_state.get('show_add_form', False):
    st.subheader(f"➕ Ajouter - {selected_table}")
    config = TABLES_CONFIG[selected_table]
    
    # ⭐ Afficher liste champs obligatoires
    if "required_fields" in config:
        required_fields_str = ", ".join([f.replace('_', ' ').title() for f in config["required_fields"]])
        st.info(f"📌 Champs obligatoires : **{required_fields_str}**")
    
    # Initialiser session_state
    if 'new_data' not in st.session_state:
        st.session_state.new_data = {}
    
    col1, col2 = st.columns(2)
    
    for i, col in enumerate(config['columns']):
        # ⭐ Ignorer colonnes calculées dans le formulaire
        if col in config.get("calculated_columns", {}):
            continue
            
        # ⭐ Marquer champs obligatoires avec astérisque
        label = col.replace('_', ' ').title()
        if "required_fields" in config and col in config["required_fields"]:
            label = f"{label} *"
        
        with col1 if i % 2 == 0 else col2:
            # ⭐ Dropdowns pour champs spécifiques
            if "dropdown_fields" in config and col in config["dropdown_fields"]:
                field_config = config["dropdown_fields"][col]
                
                # ⭐ Dropdown dynamique pour code_variete
                if field_config == "dynamic_varietes":
                    varietes = get_active_varietes()
                    options = [""] + varietes
                    st.session_state.new_data[col] = st.selectbox(
                        label,
                        options=options,
                        key=f"add_{col}"
                    )
                # ⭐ Dropdown depuis DB avec option "Autre"
                elif field_config == "dynamic_from_db":
                    # Récupérer valeurs existantes
                    full_df_for_form = st.session_state.get(f'full_df_{selected_table}')
                    if full_df_for_form is not None and col in full_df_for_form.columns:
                        existing_values = get_unique_values_from_column(full_df_for_form, col)
                    else:
                        existing_values = []
                    
                    options = [""] + existing_values + ["➕ Saisir nouvelle valeur"]
                    selected = st.selectbox(
                        label,
                        options=options,
                        key=f"add_{col}_select"
                    )
                    
                    # Si "Autre", afficher champ texte
                    if selected == "➕ Saisir nouvelle valeur":
                        st.session_state.new_data[col] = st.text_input(
                            f"Nouvelle valeur pour {label}",
                            key=f"add_{col}_new"
                        )
                    else:
                        st.session_state.new_data[col] = selected
                # Dropdown statique
                else:
                    options = [""] + field_config
                    st.session_state.new_data[col] = st.selectbox(
                        label,
                        options=options,
                        key=f"add_{col}"
                    )
            elif col in ['is_bio', 'global_gap']:
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
        if st.button("💾 Enregistrer", use_container_width=True, type="primary", key="btn_save_add"):
            # ⭐ VALIDATION EXPLICITE des champs obligatoires
            missing_fields = []
            if "required_fields" in config:
                for field in config["required_fields"]:
                    if field not in st.session_state.new_data or not st.session_state.new_data[field] or st.session_state.new_data[field] == '':
                        missing_fields.append(field.replace('_', ' ').title())
            
            if missing_fields:
                st.error(f"❌ Champs obligatoires manquants : {', '.join(missing_fields)}")
            else:
                # ⭐ Filtrer les données
                filtered_data = {}
                for k, v in st.session_state.new_data.items():
                    # Garder False (checkboxes décochées)
                    if isinstance(v, bool):
                        filtered_data[k] = v
                    # Garder 0 (nombres)
                    elif isinstance(v, (int, float)) and v == 0:
                        filtered_data[k] = v
                    # Exclure chaînes vides et None
                    elif v != '' and v is not None:
                        filtered_data[k] = v
                
                success, message = add_record(selected_table, filtered_data)
                if success:
                    st.success(message)
                    # ⭐ Animation confettis Lottie
                    show_confetti_animation()
                    time.sleep(2)
                    st.session_state.show_add_form = False
                    st.session_state.pop('new_data', None)
                    st.rerun()
                else:
                    st.error(message)
    
    with col2:
        if st.button("❌ Annuler", use_container_width=True, key="btn_cancel_add"):
            st.session_state.show_add_form = False
            st.session_state.pop('new_data', None)
            st.rerun()
    
    st.markdown("---")

# ⭐ Toggle pour afficher/masquer les inactifs
show_inactive = st.checkbox("👁️ Afficher les éléments inactifs", value=False, key=f"show_inactive_{selected_table}")

# Charger données avec filtre
df_full = load_table_data(selected_table, show_inactive=show_inactive)

if not df_full.empty:
    config = TABLES_CONFIG[selected_table]
    
    # Récupérer le df complet avec is_active pour les métriques
    full_df_with_inactive = st.session_state.get(f'full_df_{selected_table}')
    
    # Métriques (sur données complètes avant filtrage)
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("📊 Total", len(df_full))
    with col2:
        if full_df_with_inactive is not None and 'is_active' in full_df_with_inactive.columns:
            actifs = full_df_with_inactive['is_active'].sum()
        else:
            actifs = len(df_full)
        st.metric("✅ Actifs", actifs)
    with col3:
        if full_df_with_inactive is not None and 'is_active' in full_df_with_inactive.columns:
            inactifs = len(full_df_with_inactive) - actifs
        else:
            inactifs = 0
        st.metric("❌ Inactifs", inactifs)
    
    st.markdown("---")
    
    # ⭐ FILTRES (colonnes les plus importantes)
    df = df_full.copy()  # Copie pour filtrage
    
    if "filter_columns" in config:
        st.markdown("#### 🔍 Filtres")
        filter_cols = st.columns(len(config["filter_columns"]))
        filters = {}
        
        for i, col_name in enumerate(config["filter_columns"]):
            with filter_cols[i]:
                if col_name in df.columns:
                    # ⭐ Traitement spécial pour boolean (is_bio, global_gap)
                    if col_name in ["is_bio", "global_gap"]:
                        bool_options = ["Tous", "OUI", "NON"]
                        label = "Bio" if col_name == "is_bio" else "Global Gap"
                        filters[col_name] = st.selectbox(
                            label,
                            bool_options,
                            key=f"filter_{col_name}"
                        )
                    else:
                        unique_values = ["Tous"] + sorted([str(v) for v in df[col_name].dropna().unique() if str(v).strip() != ''])
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
        
        # Afficher nombre de résultats filtrés
        if len(df) != len(df_full):
            st.info(f"🔍 {len(df)} résultat(s) après filtrage (sur {len(df_full)} total)")
        
        st.markdown("---")
    
    # ⭐ En-tête table avec bouton Ajouter aligné à droite
    col_title, col_button = st.columns([4, 1])
    with col_title:
        st.subheader(f"📋 {selected_table}")
    with col_button:
        if st.button("➕ Ajouter", use_container_width=True, type="primary"):
            st.session_state.show_add_form = not st.session_state.get('show_add_form', False)
            st.rerun()
    
    # ⭐ Configuration colonnes pour data_editor avec dropdowns
    column_config = {}
    if "dropdown_fields" in config:
        full_df_for_dropdown = st.session_state.get(f'full_df_{selected_table}', df_full)
        for field, field_config in config["dropdown_fields"].items():
            # ⭐ Dropdown dynamique depuis ref_varietes
            if field_config == "dynamic_varietes":
                varietes = get_varietes_with_existing(full_df_for_dropdown, field)
                column_config[field] = st.column_config.SelectboxColumn(
                    field.replace('_', ' ').title(),
                    options=varietes,
                    required=False
                )
            # ⭐ Dropdown depuis valeurs existantes de la colonne
            elif field_config == "dynamic_from_db":
                unique_values = get_unique_values_from_column(full_df_for_dropdown, field)
                if unique_values:
                    column_config[field] = st.column_config.SelectboxColumn(
                        field.replace('_', ' ').title(),
                        options=unique_values,
                        required=False
                    )
            # Dropdown statique
            else:
                # ⭐ Inclure valeurs existantes aussi pour listes statiques
                existing = full_df_for_dropdown[field].dropna().unique().tolist() if field in full_df_for_dropdown.columns else []
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
        disabled=[config['primary_key']] + list(config.get("calculated_columns", {}).keys()),
        column_config=column_config if column_config else None,
        key=f"editor_{selected_table}"
    )
    
    # ⭐ DÉTECTION CHANGEMENTS (Auto-save) - VERSION CORRIGÉE
    changes_detected = False
    try:
        if 'original_df' in st.session_state:
            config = TABLES_CONFIG[selected_table]
            
            # Comparer ligne par ligne sur colonnes éditables
            for idx in edited_df.index:
                if idx not in st.session_state.original_df.index:
                    continue
                
                for col in config.get('editable', []):
                    if col in st.session_state.original_df.columns and col in edited_df.columns:
                        old_val = st.session_state.original_df.loc[idx, col]
                        new_val = edited_df.loc[idx, col]
                        
                        # Comparer en ignorant NaN
                        if pd.isna(old_val) and pd.isna(new_val):
                            continue
                        elif old_val != new_val:
                            changes_detected = True
                            break
                
                if changes_detected:
                    break
    except Exception as e:
        # Debug
        st.caption(f"Debug détection: {str(e)}")
    
    # ⭐ ALERTE si modifications non sauvegardées
    if changes_detected:
        st.error("🚫 **MODIFICATIONS NON SAUVEGARDÉES !**")
        st.warning("⚠️ Vous avez modifié des données. **Cliquez sur 💾 Enregistrer** avant de changer de table ou vous perdrez vos modifications !")
    
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
    
    # Désactivation / Réactivation
    st.markdown("---")
    st.subheader("🔒 Gestion activation")
    
    # Utiliser le df complet avec is_active pour la gestion
    full_df_for_activation = st.session_state.get(f'full_df_{selected_table}', df_full)
    
    # Dropdown pleine largeur
    first_col = config['columns'][0]
    options = [f"{row[config['primary_key']]} - {row[first_col]}" for _, row in full_df_for_activation.iterrows()]
    selected_record = st.selectbox(
        f"Sélectionner un élément à activer/désactiver",
        options,
        key="activation_selector"
    )
    
    # Boutons centrés en dessous
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
        st.download_button("📥 CSV", csv, f"{config['table']}_{datetime.now().strftime('%Y%m%d')}.csv", 
                          "text/csv", use_container_width=True)
    
    with col2:
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name=selected_table)
        st.download_button("📥 Excel", buffer.getvalue(), f"{config['table']}_{datetime.now().strftime('%Y%m%d')}.xlsx",
                          "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)
else:
    st.warning(f"⚠️ Aucune donnée pour {selected_table}")

show_footer()
