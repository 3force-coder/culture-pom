import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, date
import time
from database import get_connection
from components import show_footer
from auth import is_authenticated
import io
import streamlit.components.v1 as components

st.set_page_config(page_title="Stock - Culture Pom", page_icon="📦", layout="wide")

# CSS custom pour réduire espacements
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
</style>
""", unsafe_allow_html=True)

if not is_authenticated():
    st.warning("⚠️ Veuillez vous connecter pour accéder à cette page")
    st.stop()

# ⭐ FONCTION ANIMATION LOTTIE
def show_confetti_animation():
    """Affiche l'animation confetti Lottie"""
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

st.title("📦 Gestion du Stock")
st.markdown("---")

# ⭐ FONCTIONS DROPDOWNS DYNAMIQUES

def get_varietes_for_dropdown():
    """Récupère NOMS de variétés depuis ref_varietes"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT code_variete, nom_variete 
            FROM ref_varietes 
            WHERE is_active = TRUE 
            ORDER BY nom_variete
        """)
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        
        # Retourner dictionnaire {nom: code}
        return {row[1]: row[0] for row in rows}
    except Exception as e:
        st.error(f"❌ Erreur chargement variétés : {str(e)}")
        return {}

def get_producteurs_for_dropdown():
    """Récupère NOMS de producteurs depuis ref_producteurs"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT code_producteur, nom 
            FROM ref_producteurs 
            WHERE is_active = TRUE 
            ORDER BY nom
        """)
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        
        # Retourner dictionnaire {nom: code}
        return {row[1]: row[0] for row in rows}
    except Exception as e:
        st.error(f"❌ Erreur chargement producteurs : {str(e)}")
        return {}

def get_sites_for_dropdown():
    """Récupère codes sites depuis ref_sites_stockage"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT DISTINCT code_site 
            FROM ref_sites_stockage 
            WHERE is_active = TRUE 
            ORDER BY code_site
        """)
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        return [row[0] for row in rows]
    except Exception as e:
        st.error(f"❌ Erreur chargement sites : {str(e)}")
        return []

def get_emplacements_for_dropdown():
    """Récupère codes emplacements depuis ref_sites_stockage"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT DISTINCT code_emplacement 
            FROM ref_sites_stockage 
            WHERE is_active = TRUE 
            ORDER BY code_emplacement
        """)
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        return [row[0] for row in rows]
    except Exception as e:
        st.error(f"❌ Erreur chargement emplacements : {str(e)}")
        return []

def get_unique_values_from_db(table, column, where_active=True):
    """Récupère valeurs uniques d'une colonne"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        where_clause = " WHERE is_active = TRUE" if where_active else ""
        query = f"SELECT DISTINCT {column} FROM {table}{where_clause} WHERE {column} IS NOT NULL ORDER BY {column}"
        
        cursor.execute(query)
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        
        return [row[0] for row in rows if row[0]]
    except Exception as e:
        return []

# ⭐ FONCTION AJOUT LOT

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
    if isinstance(value, date):
        return value
    return value

def add_lot(data, varietes_dict, producteurs_dict):
    """Ajoute un nouveau lot dans lots_bruts"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # ⭐ CONVERTIR NOM → CODE pour variété
        if 'nom_variete' in data and data['nom_variete']:
            if data['nom_variete'] in varietes_dict:
                data['code_variete'] = varietes_dict[data['nom_variete']]
            del data['nom_variete']
        
        # ⭐ CONVERTIR NOM → CODE pour producteur
        if 'nom_producteur' in data and data['nom_producteur']:
            if data['nom_producteur'] in producteurs_dict:
                data['code_producteur'] = producteurs_dict[data['nom_producteur']]
            del data['nom_producteur']
        
        # ⭐ Ajouter is_active = TRUE
        data['is_active'] = True
        
        # ⭐ Préparer l'insertion
        columns = list(data.keys())
        values = [convert_to_native_types(v) for v in data.values()]
        placeholders = ", ".join(["%s"] * len(columns))
        columns_str = ", ".join(columns)
        
        query = f"""
            INSERT INTO lots_bruts ({columns_str}, created_at, updated_at) 
            VALUES ({placeholders}, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """
        
        cursor.execute(query, values)
        conn.commit()
        cursor.close()
        conn.close()
        
        return True, "✅ Lot ajouté avec succès"
        
    except Exception as e:
        if 'conn' in locals():
            conn.rollback()
        
        # ⭐ MESSAGES D'ERREUR CLAIRS
        error_msg = str(e).lower()
        
        if "duplicate key" in error_msg or "unique constraint" in error_msg:
            if "code_lot_interne" in error_msg:
                return False, "❌ Ce code lot est déjà utilisé. Merci de choisir un autre code."
            else:
                return False, "❌ Cette valeur est déjà utilisée."
        elif "not null" in error_msg or "null value" in error_msg:
            return False, "❌ Un champ obligatoire est manquant."
        elif "foreign key" in error_msg:
            return False, "❌ Valeur invalide (variété ou producteur inexistant)."
        else:
            return False, f"❌ Erreur : {str(e)}"

# ⭐ LISTES STATIQUES

STATUTS = ["EN_STOCK", "RESERVE", "VENDU", "DECHET"]
TYPES_CONDITIONNEMENT = ["PALLOX", "CAISSE", "FILET", "VRAC"]

# ===============================================
# FORMULAIRE D'AJOUT
# ===============================================

st.subheader("➕ Ajouter un nouveau lot")

# ⭐ Charger les dictionnaires pour dropdowns
varietes_dict = get_varietes_for_dropdown()
producteurs_dict = get_producteurs_for_dropdown()
sites_list = get_sites_for_dropdown()
emplacements_list = get_emplacements_for_dropdown()
types_cond_list = get_unique_values_from_db("lots_bruts", "type_conditionnement")

# ⭐ Afficher champs obligatoires
st.info("📌 Champs obligatoires : **Code Lot Interne, Nom Usage, Variété, Producteur, Site, Emplacement, Nombre Unités, Poids Unitaire**")

# ⭐ Initialiser session_state pour formulaire
if 'new_lot_data' not in st.session_state:
    st.session_state.new_lot_data = {}

# ⭐ FORMULAIRE EN 2 COLONNES

col1, col2 = st.columns(2)

with col1:
    # Champs obligatoires
    st.session_state.new_lot_data['code_lot_interne'] = st.text_input(
        "Code Lot Interne *",
        key="add_code_lot_interne",
        help="Code unique du lot (ex: LOT_2025_AGATA_001)"
    )
    
    st.session_state.new_lot_data['nom_usage'] = st.text_input(
        "Nom Usage *",
        key="add_nom_usage",
        help="Nom d'usage du lot"
    )
    
    # Variété (dropdown noms) - OBLIGATOIRE
    variete_options = [""] + list(varietes_dict.keys())
    st.session_state.new_lot_data['nom_variete'] = st.selectbox(
        "Variété *",
        options=variete_options,
        key="add_variete"
    )
    
    # Producteur (dropdown noms) - OBLIGATOIRE
    producteur_options = [""] + list(producteurs_dict.keys())
    st.session_state.new_lot_data['nom_producteur'] = st.selectbox(
        "Producteur *",
        options=producteur_options,
        key="add_producteur"
    )
    
    # Site (dropdown codes) - OBLIGATOIRE
    site_options = [""] + sites_list
    st.session_state.new_lot_data['site_stockage'] = st.selectbox(
        "Site Stockage *",
        options=site_options,
        key="add_site"
    )
    
    # Emplacement (dropdown codes) - OBLIGATOIRE
    emplacement_options = [""] + emplacements_list
    st.session_state.new_lot_data['emplacement_stockage'] = st.selectbox(
        "Emplacement *",
        options=emplacement_options,
        key="add_emplacement"
    )
    
    # Date entrée - AUTO (non modifiable pour l'instant, toujours aujourd'hui)
    st.session_state.new_lot_data['date_entree_stock'] = datetime.now().date()
    st.text_input(
        "Date Entrée Stock (auto)",
        value=datetime.now().strftime("%d/%m/%Y"),
        disabled=True,
        key="add_date_entree_display"
    )

with col2:
    # Nombre unités - OBLIGATOIRE (défaut 1)
    st.session_state.new_lot_data['nombre_unites'] = st.number_input(
        "Nombre Unités *",
        min_value=1,
        value=1,
        step=1,
        key="add_nombre_unites"
    )
    
    # Poids unitaire - OBLIGATOIRE (défaut 1900 kg)
    st.session_state.new_lot_data['poids_unitaire_kg'] = st.number_input(
        "Poids Unitaire (kg) *",
        min_value=1.0,
        value=1900.0,
        step=50.0,
        key="add_poids_unitaire",
        help="Défaut: 1900 kg (pallox standard)"
    )
    
    # Type conditionnement
    type_cond_options = [""] + types_cond_list + ["➕ Saisir nouvelle valeur"]
    type_cond_selected = st.selectbox(
        "Type Conditionnement",
        options=type_cond_options,
        key="add_type_cond_select"
    )
    
    if type_cond_selected == "➕ Saisir nouvelle valeur":
        st.session_state.new_lot_data['type_conditionnement'] = st.text_input(
            "Nouveau type",
            key="add_type_cond_new"
        )
    else:
        st.session_state.new_lot_data['type_conditionnement'] = type_cond_selected
    
    # Calibres
    st.session_state.new_lot_data['calibre_min'] = st.number_input(
        "Calibre Min",
        min_value=0,
        value=0,
        step=5,
        key="add_calibre_min"
    )
    
    st.session_state.new_lot_data['calibre_max'] = st.number_input(
        "Calibre Max",
        min_value=0,
        value=0,
        step=5,
        key="add_calibre_max"
    )
    
    # Prix achat
    st.session_state.new_lot_data['prix_achat_euro_tonne'] = st.number_input(
        "Prix Achat (€/tonne)",
        min_value=0.0,
        value=0.0,
        step=10.0,
        key="add_prix_achat"
    )
    
    # Statut
    st.session_state.new_lot_data['statut'] = st.selectbox(
        "Statut",
        options=STATUTS,
        index=0,  # EN_STOCK par défaut
        key="add_statut"
    )

# ⭐ BOUTONS ENREGISTRER / ANNULER

st.markdown("---")

col1, col2, col3 = st.columns([1, 1, 4])

with col1:
    if st.button("💾 Enregistrer", use_container_width=True, type="primary", key="btn_save_lot"):
        # ⭐ VALIDATION CHAMPS OBLIGATOIRES
        missing_fields = []
        
        if not st.session_state.new_lot_data.get('code_lot_interne'):
            missing_fields.append("Code Lot Interne")
        if not st.session_state.new_lot_data.get('nom_usage'):
            missing_fields.append("Nom Usage")
        if not st.session_state.new_lot_data.get('nom_variete'):
            missing_fields.append("Variété")
        if not st.session_state.new_lot_data.get('nom_producteur'):
            missing_fields.append("Producteur")
        if not st.session_state.new_lot_data.get('site_stockage'):
            missing_fields.append("Site Stockage")
        if not st.session_state.new_lot_data.get('emplacement_stockage'):
            missing_fields.append("Emplacement")
        if not st.session_state.new_lot_data.get('nombre_unites') or st.session_state.new_lot_data.get('nombre_unites') == 0:
            missing_fields.append("Nombre Unités")
        if not st.session_state.new_lot_data.get('poids_unitaire_kg') or st.session_state.new_lot_data.get('poids_unitaire_kg') == 0:
            missing_fields.append("Poids Unitaire")
        
        if missing_fields:
            st.error(f"❌ Champs obligatoires manquants : {', '.join(missing_fields)}")
        else:
            # ⭐ FILTRER LES DONNÉES (enlever valeurs vides)
            filtered_data = {}
            for k, v in st.session_state.new_lot_data.items():
                # Garder False et 0
                if isinstance(v, bool) or (isinstance(v, (int, float)) and v == 0):
                    filtered_data[k] = v
                # Garder dates
                elif isinstance(v, date):
                    filtered_data[k] = v
                # Exclure chaînes vides et None
                elif v != '' and v is not None:
                    filtered_data[k] = v
            
            # ⭐ AJOUTER LE LOT
            success, message = add_lot(filtered_data, varietes_dict, producteurs_dict)
            
            if success:
                st.success(message)
                # ⭐ ANIMATION CONFETTIS
                show_confetti_animation()
                time.sleep(2)
                st.session_state.pop('new_lot_data', None)
                st.rerun()
            else:
                st.error(message)

with col2:
    if st.button("❌ Annuler", use_container_width=True, key="btn_cancel_lot"):
        st.session_state.pop('new_lot_data', None)
        st.rerun()

st.markdown("---")

# ⭐ MESSAGE EXPLICATIF
st.info("""
**📝 Instructions** :
- Les champs marqués * sont **obligatoires** (8 au total)
- La **Date Entrée Stock** est automatiquement remplie avec la date du jour
- Le **Nombre d'Unités** est pré-rempli à 1
- Le **Poids Unitaire** est pré-rempli à 1900 kg (pallox standard)
- Le **Statut** est pré-rempli à EN_STOCK
- Les **dropdowns** vous permettent de sélectionner des valeurs normalisées
- Le **Type Conditionnement** peut être personnalisé avec "➕ Saisir nouvelle valeur"
""")

show_footer()
