import streamlit as st
import pandas as pd
import requests
from datetime import datetime
from database import get_connection
from components import show_footer
from auth import is_authenticated, require_access, can_edit, can_delete

st.set_page_config(page_title="CRM Clients - Culture Pom", page_icon="🏪", layout="wide")

if not is_authenticated():
    st.warning("⚠️ Veuillez vous connecter")
    st.stop()

require_access("CRM")

st.markdown("""
<style>
    .block-container { padding-top: 1.5rem !important; padding-bottom: 0.5rem !important; }
    h1, h2, h3, h4 { margin-top: 0.3rem !important; margin-bottom: 0.3rem !important; }
    
    /* Style pour les tags de marques */
    .tag-marque {
        display: inline-block;
        background: #e3f2fd;
        color: #1565c0;
        padding: 0.2rem 0.5rem;
        border-radius: 15px;
        margin: 0.1rem;
        font-size: 0.85rem;
    }
    .tag-produit {
        display: inline-block;
        background: #e8f5e9;
        color: #2e7d32;
        padding: 0.2rem 0.5rem;
        border-radius: 15px;
        margin: 0.1rem;
        font-size: 0.85rem;
    }
</style>
""", unsafe_allow_html=True)

st.title("🏪 CRM - Gestion des Clients")
st.caption("🗺️ Recherche d'adresse avec API Adresse (data.gouv.fr)")
st.markdown("---")

# ==========================================
# ⭐ FONCTIONS API ADRESSE (data.gouv.fr)
# ==========================================

def search_adresse(query, limit=5):
    """Recherche d'adresse via l'API Adresse du gouvernement français"""
    if not query or len(query) < 3:
        return []
    
    try:
        response = requests.get(
            "https://api-adresse.data.gouv.fr/search/",
            params={"q": query, "limit": limit, "autocomplete": 1},
            timeout=5
        )
        
        if response.status_code == 200:
            data = response.json()
            results = []
            
            for feature in data.get('features', []):
                props = feature.get('properties', {})
                coords = feature.get('geometry', {}).get('coordinates', [None, None])
                
                results.append({
                    'label': props.get('label', ''),
                    'name': props.get('name', ''),
                    'postcode': props.get('postcode', ''),
                    'city': props.get('city', ''),
                    'departement': props.get('postcode', '')[:2] if props.get('postcode') else '',
                    'longitude': coords[0] if coords else None,
                    'latitude': coords[1] if coords else None,
                })
            return results
        return []
    except:
        return []

def geocode_adresse(adresse_complete):
    """Géocode une adresse complète pour obtenir lat/lng"""
    try:
        response = requests.get(
            "https://api-adresse.data.gouv.fr/search/",
            params={"q": adresse_complete, "limit": 1},
            timeout=5
        )
        if response.status_code == 200:
            data = response.json()
            if data.get('features'):
                coords = data['features'][0].get('geometry', {}).get('coordinates', [None, None])
                return {'latitude': coords[1], 'longitude': coords[0]}
        return None
    except:
        return None

# ==========================================
# FONCTIONS HELPER
# ==========================================

def safe_int(value, default=0):
    if value is None or pd.isna(value):
        return default
    try:
        return int(value)
    except:
        return default

def safe_str(value, default=''):
    if value is None or pd.isna(value):
        return default
    return str(value)

def safe_float(value, default=None):
    if value is None or pd.isna(value):
        return default
    try:
        return float(value)
    except:
        return default

# ==========================================
# FONCTIONS DB - DONNÉES DE BASE
# ==========================================

def get_commerciaux():
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, prenom || ' ' || nom as nom FROM crm_commerciaux WHERE is_active = TRUE ORDER BY nom")
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        return [(r['id'], r['nom']) for r in rows]
    except:
        return []

def get_filtres_options():
    try:
        conn = get_connection()
        cursor = conn.cursor()
        options = {}
        cursor.execute("SELECT DISTINCT enseigne FROM crm_magasins WHERE is_active = TRUE AND enseigne IS NOT NULL ORDER BY enseigne")
        options['enseignes'] = [r['enseigne'] for r in cursor.fetchall()]
        cursor.execute("SELECT DISTINCT departement FROM crm_magasins WHERE is_active = TRUE AND departement IS NOT NULL ORDER BY departement")
        options['departements'] = [r['departement'] for r in cursor.fetchall()]
        cursor.close()
        conn.close()
        return options
    except:
        return {'enseignes': [], 'departements': []}

def get_centrales_achat():
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT centrale_achat FROM crm_magasins WHERE is_active = TRUE AND centrale_achat IS NOT NULL AND centrale_achat != '' ORDER BY centrale_achat")
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        return [r['centrale_achat'] for r in rows]
    except:
        return []

def get_types_client():
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT type_magasin FROM crm_magasins WHERE is_active = TRUE AND type_magasin IS NOT NULL AND type_magasin != '' ORDER BY type_magasin")
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        return [r['type_magasin'] for r in rows]
    except:
        return []

def get_types_reseau():
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT type_reseau FROM crm_magasins WHERE is_active = TRUE AND type_reseau IS NOT NULL AND type_reseau != '' ORDER BY type_reseau")
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        return [r['type_reseau'] for r in rows]
    except:
        return []

# ==========================================
# FONCTIONS DB - PRÉSENCE PRODUIT
# ==========================================

def get_marques_concurrentes():
    """Récupère toutes les marques concurrentes actives"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, nom FROM ref_marques_concurrentes WHERE is_active = TRUE ORDER BY nom")
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        return [(r['id'], r['nom']) for r in rows]
    except:
        return []

def get_types_produits_crm():
    """Récupère tous les types de produits CRM actifs"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, code, libelle, categorie FROM ref_types_produits_crm WHERE is_active = TRUE ORDER BY ordre")
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        return [(r['id'], r['code'], r['libelle'], r['categorie']) for r in rows]
    except:
        return []

def get_magasin_marques(magasin_id):
    """Récupère les marques associées à un magasin"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT m.id, m.nom 
            FROM ref_marques_concurrentes m
            JOIN crm_magasins_marques mm ON m.id = mm.marque_id
            WHERE mm.magasin_id = %s AND mm.is_active = TRUE AND m.is_active = TRUE
            ORDER BY m.nom
        """, (int(magasin_id),))
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        return [(r['id'], r['nom']) for r in rows]
    except:
        return []

def get_magasin_produits(magasin_id):
    """Récupère les types de produits associés à un magasin"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT tp.id, tp.code, tp.libelle
            FROM ref_types_produits_crm tp
            JOIN crm_magasins_produits mp ON tp.id = mp.type_produit_id
            WHERE mp.magasin_id = %s AND mp.is_active = TRUE AND tp.is_active = TRUE
            ORDER BY tp.ordre
        """, (int(magasin_id),))
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        return [r['id'] for r in rows]
    except:
        return []

def create_marque_concurrente(nom):
    """Crée une nouvelle marque concurrente"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO ref_marques_concurrentes (nom) VALUES (%s)
            ON CONFLICT (nom) DO UPDATE SET is_active = TRUE
            RETURNING id
        """, (nom.strip(),))
        new_id = cursor.fetchone()['id']
        conn.commit()
        cursor.close()
        conn.close()
        return new_id
    except:
        return None

def create_type_produit_crm(code, libelle, categorie='AUTRE'):
    """Crée un nouveau type de produit"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        # Récupérer le max ordre
        cursor.execute("SELECT COALESCE(MAX(ordre), 0) + 1 as next_ordre FROM ref_types_produits_crm")
        next_ordre = cursor.fetchone()['next_ordre']
        
        cursor.execute("""
            INSERT INTO ref_types_produits_crm (code, libelle, categorie, ordre) 
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (code) DO UPDATE SET is_active = TRUE
            RETURNING id
        """, (code.upper().replace(' ', '_'), libelle.strip(), categorie, next_ordre))
        new_id = cursor.fetchone()['id']
        conn.commit()
        cursor.close()
        conn.close()
        return new_id
    except:
        return None

def save_magasin_marques(magasin_id, marque_ids):
    """Sauvegarde les marques d'un magasin (avec historique)"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        username = st.session_state.get('username', 'system')
        
        # Désactiver les anciennes liaisons
        cursor.execute("""
            UPDATE crm_magasins_marques 
            SET is_active = FALSE, updated_at = CURRENT_TIMESTAMP 
            WHERE magasin_id = %s AND is_active = TRUE
        """, (int(magasin_id),))
        
        # Insérer/réactiver les nouvelles
        for marque_id in marque_ids:
            cursor.execute("""
                INSERT INTO crm_magasins_marques (magasin_id, marque_id, created_by)
                VALUES (%s, %s, %s)
                ON CONFLICT (magasin_id, marque_id) 
                DO UPDATE SET is_active = TRUE, updated_at = CURRENT_TIMESTAMP
            """, (int(magasin_id), int(marque_id), username))
        
        conn.commit()
        cursor.close()
        conn.close()
        return True
    except Exception as e:
        st.error(f"Erreur sauvegarde marques: {e}")
        return False

def save_magasin_produits(magasin_id, produit_ids):
    """Sauvegarde les types de produits d'un magasin (avec historique)"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        username = st.session_state.get('username', 'system')
        
        # Désactiver les anciennes liaisons
        cursor.execute("""
            UPDATE crm_magasins_produits 
            SET is_active = FALSE, updated_at = CURRENT_TIMESTAMP 
            WHERE magasin_id = %s AND is_active = TRUE
        """, (int(magasin_id),))
        
        # Insérer/réactiver les nouvelles
        for produit_id in produit_ids:
            cursor.execute("""
                INSERT INTO crm_magasins_produits (magasin_id, type_produit_id, created_by)
                VALUES (%s, %s, %s)
                ON CONFLICT (magasin_id, type_produit_id) 
                DO UPDATE SET is_active = TRUE, updated_at = CURRENT_TIMESTAMP
            """, (int(magasin_id), int(produit_id), username))
        
        conn.commit()
        cursor.close()
        conn.close()
        return True
    except Exception as e:
        st.error(f"Erreur sauvegarde produits: {e}")
        return False

# ==========================================
# FONCTIONS DB - MAGASINS
# ==========================================

def get_magasins(filtres=None):
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        query = """
            SELECT 
                m.id, m.enseigne, m.ville, m.departement, m.code_postal,
                m.statut, m.commercial_id, c.prenom || ' ' || c.nom as commercial,
                m.adresse, m.centrale_achat, m.type_magasin, m.type_reseau,
                m.surface_m2, m.potentiel, m.presence_produit,
                m.presence_marque_hors_mdd,
                m.points_amelioration, m.commentaires, m.notes,
                m.latitude, m.longitude,
                m.date_derniere_visite, m.date_prochaine_visite
            FROM crm_magasins m
            LEFT JOIN crm_commerciaux c ON m.commercial_id = c.id
            WHERE m.is_active = TRUE
        """
        params = []
        
        if filtres:
            if filtres.get('enseigne') and filtres['enseigne'] != 'Tous':
                query += " AND m.enseigne = %s"
                params.append(filtres['enseigne'])
            if filtres.get('departement') and filtres['departement'] != 'Tous':
                query += " AND m.departement = %s"
                params.append(filtres['departement'])
            if filtres.get('commercial_id') and filtres['commercial_id'] != 0:
                query += " AND m.commercial_id = %s"
                params.append(int(filtres['commercial_id']))
            if filtres.get('statut') and filtres['statut'] != 'Tous':
                query += " AND m.statut = %s"
                params.append(filtres['statut'])
        
        query += " ORDER BY m.enseigne, m.ville"
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        
        return pd.DataFrame(rows) if rows else pd.DataFrame()
    except Exception as e:
        st.error(f"❌ Erreur : {str(e)}")
        return pd.DataFrame()

def get_magasin_by_id(magasin_id):
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT m.*, c.prenom || ' ' || c.nom as commercial
            FROM crm_magasins m
            LEFT JOIN crm_commerciaux c ON m.commercial_id = c.id
            WHERE m.id = %s
        """, (int(magasin_id),))
        row = cursor.fetchone()
        cursor.close()
        conn.close()
        return dict(row) if row else None
    except:
        return None

def create_magasin(data):
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        commercial_id = int(data['commercial_id']) if data.get('commercial_id') else None
        
        cursor.execute("""
            INSERT INTO crm_magasins (
                enseigne, ville, departement, adresse, code_postal,
                commercial_id, centrale_achat, type_magasin, type_reseau,
                surface_m2, potentiel, statut, presence_produit,
                presence_marque_hors_mdd,
                points_amelioration, commentaires, notes, 
                latitude, longitude
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (
            data['enseigne'], data['ville'], data.get('departement'),
            data.get('adresse'), data.get('code_postal'), commercial_id,
            data.get('centrale_achat'), data.get('type_magasin'), data.get('type_reseau'),
            data.get('surface_m2'), data.get('potentiel'), data.get('statut', 'PROSPECT'),
            data.get('presence_produit'),
            data.get('presence_marque_hors_mdd', False),
            data.get('points_amelioration'),
            data.get('commentaires'), data.get('notes'),
            data.get('latitude'), data.get('longitude')
        ))
        
        new_id = cursor.fetchone()['id']
        conn.commit()
        cursor.close()
        conn.close()
        
        return True, new_id
    except Exception as e:
        return False, str(e)

def update_magasin(magasin_id, data):
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        magasin_id = int(magasin_id)
        commercial_id = int(data['commercial_id']) if data.get('commercial_id') else None
        
        cursor.execute("""
            UPDATE crm_magasins SET
                enseigne = %s, ville = %s, departement = %s, adresse = %s,
                code_postal = %s, commercial_id = %s, centrale_achat = %s,
                type_magasin = %s, type_reseau = %s, surface_m2 = %s,
                potentiel = %s, statut = %s, presence_produit = %s,
                presence_marque_hors_mdd = %s,
                points_amelioration = %s, commentaires = %s, notes = %s,
                latitude = %s, longitude = %s,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
        """, (
            data['enseigne'], data['ville'], data.get('departement'),
            data.get('adresse'), data.get('code_postal'), commercial_id,
            data.get('centrale_achat'), data.get('type_magasin'), data.get('type_reseau'),
            data.get('surface_m2'), data.get('potentiel'), data.get('statut'),
            data.get('presence_produit'),
            data.get('presence_marque_hors_mdd', False),
            data.get('points_amelioration'),
            data.get('commentaires'), data.get('notes'),
            data.get('latitude'), data.get('longitude'),
            magasin_id
        ))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return True, "✅ Client mis à jour"
    except Exception as e:
        return False, f"❌ Erreur : {str(e)}"

def delete_magasin(magasin_id):
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE crm_magasins SET is_active = FALSE WHERE id = %s", (int(magasin_id),))
        conn.commit()
        cursor.close()
        conn.close()
        return True, "✅ Client supprimé"
    except Exception as e:
        return False, f"❌ Erreur : {str(e)}"

# ==========================================
# ⭐ COMPOSANT ADRESSE AUTOCOMPLETE
# ==========================================

def adresse_autocomplete(prefix_key, initial_values=None):
    """Composant de recherche d'adresse avec autocomplétion"""
    
    if initial_values is None:
        initial_values = {}
    
    st.markdown("#### 🗺️ Adresse")
    
    applied_key = f"{prefix_key}_applied"
    
    # Initialiser les valeurs dans session_state SI pas déjà présentes
    if f"{prefix_key}_adresse_val" not in st.session_state:
        st.session_state[f"{prefix_key}_adresse_val"] = safe_str(initial_values.get('adresse', ''))
    if f"{prefix_key}_cp_val" not in st.session_state:
        st.session_state[f"{prefix_key}_cp_val"] = safe_str(initial_values.get('code_postal', ''))
    if f"{prefix_key}_ville_val" not in st.session_state:
        st.session_state[f"{prefix_key}_ville_val"] = safe_str(initial_values.get('ville', ''))
    if f"{prefix_key}_dept_val" not in st.session_state:
        st.session_state[f"{prefix_key}_dept_val"] = safe_str(initial_values.get('departement', ''))
    if f"{prefix_key}_lat_val" not in st.session_state:
        st.session_state[f"{prefix_key}_lat_val"] = safe_float(initial_values.get('latitude'), 0.0)
    if f"{prefix_key}_lng_val" not in st.session_state:
        st.session_state[f"{prefix_key}_lng_val"] = safe_float(initial_values.get('longitude'), 0.0)
    
    search_query = st.text_input(
        "🔍 Rechercher une adresse",
        placeholder="Tapez une adresse (ex: 12 rue de la Paix Paris)...",
        key=f"{prefix_key}_search"
    )
    
    if search_query and len(search_query) >= 3:
        results = search_adresse(search_query)
        
        if results:
            options = ["-- Sélectionner --"] + [r['label'] for r in results]
            selected_label = st.selectbox("📍 Sélectionner", options, key=f"{prefix_key}_select")
            
            if selected_label and selected_label != "-- Sélectionner --":
                selected = next((r for r in results if r['label'] == selected_label), None)
                
                if selected and st.session_state.get(applied_key) != selected_label:
                    # Mettre à jour les valeurs dans session_state
                    st.session_state[f"{prefix_key}_adresse_val"] = selected.get('name', '')
                    st.session_state[f"{prefix_key}_cp_val"] = selected.get('postcode', '')
                    st.session_state[f"{prefix_key}_ville_val"] = selected.get('city', '')
                    st.session_state[f"{prefix_key}_dept_val"] = selected.get('departement', '')
                    st.session_state[f"{prefix_key}_lat_val"] = float(selected.get('latitude', 0) or 0)
                    st.session_state[f"{prefix_key}_lng_val"] = float(selected.get('longitude', 0) or 0)
                    st.session_state[applied_key] = selected_label
                    st.rerun()
                
                if selected:
                    st.success(f"✅ {selected_label}")
    
    col1, col2 = st.columns(2)
    
    # Fonctions de callback pour mettre à jour les valeurs
    def update_adresse(): st.session_state[f"{prefix_key}_adresse_val"] = st.session_state[f"{prefix_key}_adresse_input"]
    def update_cp(): st.session_state[f"{prefix_key}_cp_val"] = st.session_state[f"{prefix_key}_cp_input"]
    def update_ville(): st.session_state[f"{prefix_key}_ville_val"] = st.session_state[f"{prefix_key}_ville_input"]
    def update_dept(): st.session_state[f"{prefix_key}_dept_val"] = st.session_state[f"{prefix_key}_dept_input"]
    def update_lat(): st.session_state[f"{prefix_key}_lat_val"] = st.session_state[f"{prefix_key}_lat_input"]
    def update_lng(): st.session_state[f"{prefix_key}_lng_val"] = st.session_state[f"{prefix_key}_lng_input"]
    
    with col1:
        st.text_input(
            "Adresse", 
            value=st.session_state[f"{prefix_key}_adresse_val"],
            key=f"{prefix_key}_adresse_input",
            on_change=update_adresse
        )
        st.text_input(
            "Code postal", 
            value=st.session_state[f"{prefix_key}_cp_val"],
            key=f"{prefix_key}_cp_input",
            on_change=update_cp
        )
        st.text_input(
            "Ville *", 
            value=st.session_state[f"{prefix_key}_ville_val"],
            key=f"{prefix_key}_ville_input",
            on_change=update_ville
        )
    
    with col2:
        st.text_input(
            "Département", 
            value=st.session_state[f"{prefix_key}_dept_val"],
            key=f"{prefix_key}_dept_input",
            on_change=update_dept
        )
        st.number_input(
            "Latitude", 
            value=st.session_state[f"{prefix_key}_lat_val"],
            format="%.6f",
            key=f"{prefix_key}_lat_input",
            on_change=update_lat
        )
        st.number_input(
            "Longitude", 
            value=st.session_state[f"{prefix_key}_lng_val"],
            format="%.6f",
            key=f"{prefix_key}_lng_input",
            on_change=update_lng
        )
    
    return {
        'adresse': st.session_state.get(f"{prefix_key}_adresse_val", ''),
        'code_postal': st.session_state.get(f"{prefix_key}_cp_val", ''),
        'ville': st.session_state.get(f"{prefix_key}_ville_val", ''),
        'departement': st.session_state.get(f"{prefix_key}_dept_val", ''),
        'latitude': st.session_state.get(f"{prefix_key}_lat_val", 0) if st.session_state.get(f"{prefix_key}_lat_val", 0) != 0 else None,
        'longitude': st.session_state.get(f"{prefix_key}_lng_val", 0) if st.session_state.get(f"{prefix_key}_lng_val", 0) != 0 else None
    }

# ==========================================
# ⭐ COMPOSANT PRÉSENCE PRODUIT
# ==========================================

def presence_produit_component(prefix_key, magasin_id=None):
    """
    Composant pour gérer la présence produit :
    - Checkbox présence marque hors MDD
    - Multi-select marques concurrentes
    - Multi-checkbox types produits
    """
    
    st.markdown("#### 📦 Présence Produits")
    
    # Charger les données de référence
    marques_dispo = get_marques_concurrentes()
    types_produits = get_types_produits_crm()
    
    # Charger les données existantes si magasin_id
    marques_magasin = []
    produits_magasin = []
    presence_mdd = False
    
    if magasin_id:
        marques_magasin = get_magasin_marques(magasin_id)
        produits_magasin = get_magasin_produits(magasin_id)
        mag = get_magasin_by_id(magasin_id)
        if mag:
            presence_mdd = mag.get('presence_marque_hors_mdd', False) or False
    
    # 1. Checkbox présence marque hors MDD
    presence_marque_mdd = st.checkbox(
        "🏷️ Présence marque hors MDD",
        value=presence_mdd,
        key=f"{prefix_key}_presence_mdd"
    )
    
    # 2. Multi-select marques concurrentes (si présence = Oui)
    selected_marques = []
    
    if presence_marque_mdd:
        st.markdown("##### 🏷️ Marques concurrentes présentes")
        
        # Liste des marques déjà sélectionnées
        marques_ids_existants = [m[0] for m in marques_magasin]
        
        # Multi-select avec les marques disponibles
        marques_options = {m[1]: m[0] for m in marques_dispo}
        
        # Déterminer les valeurs par défaut
        default_marques = [m[1] for m in marques_magasin]
        
        selected_marques_noms = st.multiselect(
            "Sélectionner les marques",
            options=list(marques_options.keys()),
            default=default_marques,
            key=f"{prefix_key}_marques_select"
        )
        
        selected_marques = [marques_options[nom] for nom in selected_marques_noms]
        
        # Option pour ajouter une nouvelle marque
        col_new, col_btn = st.columns([3, 1])
        with col_new:
            new_marque = st.text_input("➕ Nouvelle marque", key=f"{prefix_key}_new_marque", placeholder="Nom de la marque...")
        with col_btn:
            st.write("")  # Espacement
            st.write("")
            if st.button("Ajouter", key=f"{prefix_key}_btn_add_marque"):
                if new_marque and new_marque.strip():
                    new_id = create_marque_concurrente(new_marque)
                    if new_id:
                        st.success(f"✅ Marque '{new_marque}' ajoutée")
                        st.rerun()
                    else:
                        st.error("❌ Erreur lors de l'ajout")
    
    st.markdown("---")
    
    # 3. Multi-checkbox types produits
    st.markdown("##### 📋 Types de produits présents")
    
    # Grouper par catégorie
    produits_par_cat = {}
    for tp in types_produits:
        cat = tp[3] or 'AUTRE'
        if cat not in produits_par_cat:
            produits_par_cat[cat] = []
        produits_par_cat[cat].append(tp)
    
    selected_produits = []
    
    # Afficher en colonnes par catégorie
    cols = st.columns(len(produits_par_cat))
    
    for i, (cat, produits) in enumerate(produits_par_cat.items()):
        with cols[i]:
            cat_label = {'CARTON': '📦 Cartons', 'SAC': '🛍️ Sacs', 'AUTRE': '🏷️ Autres'}.get(cat, cat)
            st.markdown(f"**{cat_label}**")
            
            for tp in produits:
                tp_id, tp_code, tp_libelle, _ = tp
                is_checked = tp_id in produits_magasin
                
                if st.checkbox(tp_libelle, value=is_checked, key=f"{prefix_key}_prod_{tp_id}"):
                    selected_produits.append(tp_id)
    
    # Option pour ajouter un nouveau type
    with st.expander("➕ Ajouter un nouveau type de produit"):
        col1, col2, col3 = st.columns([2, 2, 1])
        with col1:
            new_produit_libelle = st.text_input("Libellé", key=f"{prefix_key}_new_prod_lib")
        with col2:
            new_produit_cat = st.selectbox("Catégorie", ['CARTON', 'SAC', 'AUTRE'], key=f"{prefix_key}_new_prod_cat")
        with col3:
            st.write("")
            st.write("")
            if st.button("Ajouter", key=f"{prefix_key}_btn_add_prod"):
                if new_produit_libelle:
                    code = new_produit_libelle.upper().replace(' ', '_')[:20]
                    new_id = create_type_produit_crm(code, new_produit_libelle, new_produit_cat)
                    if new_id:
                        st.success(f"✅ Type '{new_produit_libelle}' ajouté")
                        st.rerun()
    
    return {
        'presence_marque_hors_mdd': presence_marque_mdd,
        'marques_ids': selected_marques,
        'produits_ids': selected_produits
    }

# ==========================================
# ⭐ DROPDOWN DYNAMIQUE
# ==========================================

def dropdown_dynamique(label, valeurs_existantes, valeur_actuelle, key_prefix):
    """Crée un dropdown avec option nouvelle valeur"""
    options = [""] + valeurs_existantes + ["➕ Saisir nouvelle valeur"]
    
    if valeur_actuelle and valeur_actuelle in valeurs_existantes:
        default_idx = valeurs_existantes.index(valeur_actuelle) + 1
    elif valeur_actuelle:
        options = [""] + [valeur_actuelle] + [v for v in valeurs_existantes if v != valeur_actuelle] + ["➕ Saisir nouvelle valeur"]
        default_idx = 1
    else:
        default_idx = 0
    
    selected = st.selectbox(label, options, index=default_idx, key=f"{key_prefix}_select")
    
    if selected == "➕ Saisir nouvelle valeur":
        return st.text_input(f"Nouvelle valeur pour {label}", key=f"{key_prefix}_new") or None
    elif selected == "":
        return None
    return selected

# ==========================================
# INTERFACE
# ==========================================

tab1, tab2, tab3 = st.tabs(["📋 Liste des clients", "➕ Nouveau client", "🗺️ Carte clients"])

# ==========================================
# TAB 1 : LISTE
# ==========================================

with tab1:
    st.subheader("🔍 Filtres")
    
    options = get_filtres_options()
    commerciaux = get_commerciaux()
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        f_enseigne = st.selectbox("Enseigne", ['Tous'] + options['enseignes'], key="f_ens")
    with col2:
        f_dept = st.selectbox("Département", ['Tous'] + options['departements'], key="f_dept")
    with col3:
        comm_options = [(0, 'Tous')] + commerciaux
        f_commercial = st.selectbox("Commercial", comm_options, format_func=lambda x: x[1], key="f_comm")
    with col4:
        f_statut = st.selectbox("Statut", ['Tous', 'PROSPECT', 'ACTIF', 'INACTIF', 'EN_PAUSE', 'PERDU'], key="f_stat")
    
    st.markdown("---")
    
    filtres = {
        'enseigne': f_enseigne,
        'departement': f_dept,
        'commercial_id': f_commercial[0],
        'statut': f_statut
    }
    
    df = get_magasins(filtres)
    
    if not df.empty:
        st.info(f"📊 **{len(df)} client(s)**")
        
        df_display = df[['id', 'enseigne', 'ville', 'departement', 'statut', 'commercial']].copy()
        df_display.columns = ['ID', 'Enseigne', 'Ville', 'Dept', 'Statut', 'Commercial']
        df_display['Commercial'] = df_display['Commercial'].fillna('Non assigné')
        
        event = st.dataframe(
            df_display,
            use_container_width=True,
            hide_index=True,
            on_select="rerun",
            selection_mode="single-row",
            key="magasins_table"
        )
        
        selected_rows = event.selection.rows if hasattr(event, 'selection') else []
        
        if len(selected_rows) > 0:
            selected_idx = selected_rows[0]
            selected_id = int(df_display.iloc[selected_idx]['ID'])
            mag = get_magasin_by_id(selected_id)
            
            if mag:
                st.markdown("---")
                
                col1, col2, col3 = st.columns([2, 1, 1])
                
                with col1:
                    st.success(f"✅ **{mag['enseigne']}** - {mag['ville']}")
                
                with col2:
                    if can_edit("CRM"):
                        if st.button("✏️ Modifier", type="primary", use_container_width=True):
                            st.session_state['edit_mode'] = selected_id
                            st.rerun()
                
                with col3:
                    if can_delete("CRM"):
                        if st.button("🗑️ Supprimer", type="secondary", use_container_width=True):
                            success, msg = delete_magasin(selected_id)
                            if success:
                                st.success(msg)
                                st.rerun()
                            else:
                                st.error(msg)
                
                # ==========================================
                # MODE ÉDITION
                # ==========================================
                if st.session_state.get('edit_mode') == selected_id:
                    st.markdown("---")
                    st.subheader("✏️ Modifier le client")
                    
                    commerciaux_edit = get_commerciaux()
                    centrales_edit = get_centrales_achat()
                    types_client_edit = get_types_client()
                    types_reseau_edit = get_types_reseau()
                    
                    col_edit1, col_edit2 = st.columns(2)
                    
                    with col_edit1:
                        st.markdown("#### 🏪 Informations client")
                        edit_enseigne = st.text_input("Enseigne *", value=safe_str(mag.get('enseigne')), key="edit_ens")
                        
                        comm_edit_list = [(None, 'Non assigné')] + commerciaux_edit
                        current_comm_idx = 0
                        if mag.get('commercial_id'):
                            for i, (cid, cname) in enumerate(comm_edit_list):
                                if cid == mag.get('commercial_id'):
                                    current_comm_idx = i
                                    break
                        edit_commercial = st.selectbox("Commercial", comm_edit_list, index=current_comm_idx, format_func=lambda x: x[1], key="edit_comm")
                        
                        edit_centrale = dropdown_dynamique("Centrale d'achat", centrales_edit, safe_str(mag.get('centrale_achat')), "edit_centrale")
                        edit_type_client = dropdown_dynamique("Type client", types_client_edit, safe_str(mag.get('type_magasin')), "edit_type_client")
                        edit_type_reseau = dropdown_dynamique("Type réseau", types_reseau_edit, safe_str(mag.get('type_reseau')), "edit_type_reseau")
                        
                        edit_surface = st.number_input("Surface m²", min_value=0, value=safe_int(mag.get('surface_m2')), key="edit_surf")
                        edit_potentiel = st.text_input("Potentiel", value=safe_str(mag.get('potentiel')), key="edit_pot")
                        edit_statut = st.selectbox("Statut", ['PROSPECT', 'ACTIF', 'INACTIF', 'EN_PAUSE', 'PERDU'], 
                                                   index=['PROSPECT', 'ACTIF', 'INACTIF', 'EN_PAUSE', 'PERDU'].index(mag.get('statut', 'PROSPECT')) if mag.get('statut') in ['PROSPECT', 'ACTIF', 'INACTIF', 'EN_PAUSE', 'PERDU'] else 0,
                                                   key="edit_stat")
                    
                    with col_edit2:
                        adresse_data_edit = adresse_autocomplete("edit", {
                            'adresse': mag.get('adresse'),
                            'code_postal': mag.get('code_postal'),
                            'ville': mag.get('ville'),
                            'departement': mag.get('departement'),
                            'latitude': mag.get('latitude'),
                            'longitude': mag.get('longitude')
                        })
                    
                    # ⭐ SECTION PRÉSENCE PRODUIT
                    st.markdown("---")
                    presence_data = presence_produit_component("edit", selected_id)
                    
                    edit_notes = st.text_area("Notes", value=safe_str(mag.get('notes')), key="edit_notes", height=80)
                    
                    col_save, col_cancel = st.columns(2)
                    
                    with col_save:
                        if st.button("💾 Enregistrer", type="primary", use_container_width=True, key="btn_save_edit"):
                            if not edit_enseigne:
                                st.error("❌ L'enseigne est obligatoire")
                            elif not adresse_data_edit['ville']:
                                st.error("❌ La ville est obligatoire")
                            else:
                                update_data = {
                                    'enseigne': edit_enseigne,
                                    'ville': adresse_data_edit['ville'],
                                    'departement': adresse_data_edit['departement'] or None,
                                    'adresse': adresse_data_edit['adresse'] or None,
                                    'code_postal': adresse_data_edit['code_postal'] or None,
                                    'latitude': adresse_data_edit['latitude'],
                                    'longitude': adresse_data_edit['longitude'],
                                    'commercial_id': edit_commercial[0],
                                    'centrale_achat': edit_centrale or None,
                                    'type_magasin': edit_type_client or None,
                                    'type_reseau': edit_type_reseau or None,
                                    'surface_m2': edit_surface if edit_surface > 0 else None,
                                    'potentiel': edit_potentiel or None,
                                    'statut': edit_statut,
                                    'presence_marque_hors_mdd': presence_data['presence_marque_hors_mdd'],
                                    'notes': edit_notes or None
                                }
                                success, msg = update_magasin(selected_id, update_data)
                                
                                if success:
                                    # Sauvegarder les marques et produits
                                    save_magasin_marques(selected_id, presence_data['marques_ids'])
                                    save_magasin_produits(selected_id, presence_data['produits_ids'])
                                    
                                    st.success(msg)
                                    st.session_state.pop('edit_mode', None)
                                    st.rerun()
                                else:
                                    st.error(msg)
                    
                    with col_cancel:
                        if st.button("❌ Annuler", use_container_width=True, key="btn_cancel_edit"):
                            st.session_state.pop('edit_mode', None)
                            st.rerun()
                
                # ==========================================
                # MODE AFFICHAGE
                # ==========================================
                else:
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.markdown("#### 📋 Informations")
                        st.write(f"**Adresse** : {mag.get('adresse', '-')}")
                        st.write(f"**Ville** : {mag['ville']} ({mag.get('departement', '-')})")
                        st.write(f"**Commercial** : {mag.get('commercial', 'Non assigné')}")
                        st.write(f"**Centrale** : {mag.get('centrale_achat', '-')}")
                        st.write(f"**Type** : {mag.get('type_magasin', '-')}")
                        
                        # Présence produit
                        st.markdown("---")
                        st.markdown("#### 📦 Présence Produits")
                        
                        if mag.get('presence_marque_hors_mdd'):
                            st.write("🏷️ **Présence marque hors MDD** : ✅ Oui")
                            marques = get_magasin_marques(selected_id)
                            if marques:
                                st.write("**Marques** : " + ", ".join([m[1] for m in marques]))
                        else:
                            st.write("🏷️ **Présence marque hors MDD** : ❌ Non")
                        
                        produits = get_magasin_produits(selected_id)
                        if produits:
                            types_produits = get_types_produits_crm()
                            produits_noms = [tp[2] for tp in types_produits if tp[0] in produits]
                            st.write("**Types produits** : " + ", ".join(produits_noms))
                    
                    with col2:
                        st.markdown("#### 🗺️ Localisation")
                        lat = safe_float(mag.get('latitude'))
                        lng = safe_float(mag.get('longitude'))
                        
                        if lat and lng:
                            st.success(f"📍 GPS : {lat:.6f}, {lng:.6f}")
                            st.map(pd.DataFrame({'lat': [lat], 'lon': [lng]}), zoom=13)
                        else:
                            st.warning("⚠️ Pas de coordonnées GPS")
        else:
            st.info("👆 Sélectionnez un client")
    else:
        st.warning("Aucun client trouvé")

# ==========================================
# TAB 2 : NOUVEAU CLIENT
# ==========================================

with tab2:
    if not can_edit("CRM"):
        st.warning("⚠️ Vous n'avez pas les droits pour créer un client")
    else:
        st.subheader("➕ Créer un nouveau client")
        
        commerciaux = get_commerciaux()
        centrales_list = get_centrales_achat()
        types_client_list = get_types_client()
        types_reseau_list = get_types_reseau()
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("#### 🏪 Informations client")
            new_enseigne = st.text_input("Enseigne *", key="new_ens")
            
            comm_list = [(None, 'Non assigné')] + commerciaux
            new_commercial = st.selectbox("Commercial", comm_list, format_func=lambda x: x[1], key="new_comm")
            
            new_centrale = dropdown_dynamique("Centrale d'achat", centrales_list, "", "new_centrale")
            new_type_client = dropdown_dynamique("Type client", types_client_list, "", "new_type_client")
            new_type_reseau = dropdown_dynamique("Type réseau", types_reseau_list, "", "new_type_reseau")
            
            new_surface = st.number_input("Surface m²", min_value=0, value=0, key="new_surf")
            new_potentiel = st.text_input("Potentiel", key="new_pot")
            new_statut = st.selectbox("Statut", ['PROSPECT', 'ACTIF', 'INACTIF', 'EN_PAUSE', 'PERDU'], key="new_stat")
        
        with col2:
            adresse_data = adresse_autocomplete("new")
        
        # ⭐ SECTION PRÉSENCE PRODUIT
        st.markdown("---")
        presence_data = presence_produit_component("new")
        
        new_notes = st.text_area("Notes", key="new_notes", height=80)
        
        if st.button("✅ Créer le client", type="primary", key="btn_create"):
            if not new_enseigne:
                st.error("❌ L'enseigne est obligatoire")
            elif not adresse_data['ville']:
                st.error("❌ La ville est obligatoire")
            else:
                data = {
                    'enseigne': new_enseigne,
                    'ville': adresse_data['ville'],
                    'departement': adresse_data['departement'] or None,
                    'adresse': adresse_data['adresse'] or None,
                    'code_postal': adresse_data['code_postal'] or None,
                    'latitude': adresse_data['latitude'],
                    'longitude': adresse_data['longitude'],
                    'commercial_id': new_commercial[0],
                    'centrale_achat': new_centrale or None,
                    'type_magasin': new_type_client or None,
                    'type_reseau': new_type_reseau or None,
                    'surface_m2': new_surface if new_surface > 0 else None,
                    'potentiel': new_potentiel or None,
                    'statut': new_statut,
                    'presence_marque_hors_mdd': presence_data['presence_marque_hors_mdd'],
                    'notes': new_notes or None
                }
                success, result = create_magasin(data)
                
                if success:
                    new_id = result
                    # Sauvegarder marques et produits
                    save_magasin_marques(new_id, presence_data['marques_ids'])
                    save_magasin_produits(new_id, presence_data['produits_ids'])
                    
                    st.success(f"✅ Client créé (ID: {new_id})")
                    st.balloons()
                else:
                    st.error(f"❌ Erreur : {result}")

# ==========================================
# TAB 3 : CARTE
# ==========================================

with tab3:
    st.subheader("🗺️ Carte des clients")
    
    df_all = get_magasins()
    
    if not df_all.empty:
        df_geo = df_all[df_all['latitude'].notna() & df_all['longitude'].notna()].copy()
        
        col1, col2 = st.columns(2)
        with col1:
            st.metric("📊 Total", len(df_all))
        with col2:
            st.metric("📍 Avec GPS", len(df_geo))
        
        if not df_geo.empty:
            map_df = pd.DataFrame({
                'lat': df_geo['latitude'].astype(float),
                'lon': df_geo['longitude'].astype(float)
            })
            st.map(map_df, zoom=5)

show_footer()
