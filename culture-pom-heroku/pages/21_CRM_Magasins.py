import streamlit as st
import pandas as pd
import requests
from datetime import datetime
from database import get_connection
from components import show_footer
from auth import require_access, can_edit, can_admin, is_super_admin
import folium
from streamlit_folium import st_folium

st.set_page_config(page_title="CRM Clients - Culture Pom", page_icon="🏪", layout="wide")

# Vérification accès
require_access("CRM")

# CSS personnalisé
st.markdown("""
<style>
    .block-container { padding-top: 2rem !important; }
    .client-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 1rem; border-radius: 10px; color: white; margin-bottom: 1rem;
    }
    .stat-box {
        background: #f8f9fa; padding: 1rem; border-radius: 8px;
        border-left: 4px solid #667eea; margin-bottom: 0.5rem;
    }
    .star-rating { font-size: 1.5rem; color: #ffc107; }
    .star-empty { color: #e0e0e0; }
</style>
""", unsafe_allow_html=True)

st.title("🏪 CRM - Gestion Clients")
st.markdown("---")

# ==========================================
# FONCTIONS API ADRESSE
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

def render_stars(rating, max_stars=5):
    """Génère l'affichage des étoiles"""
    if rating is None:
        return "Non défini"
    rating = int(rating)
    filled = "⭐" * rating
    empty = "☆" * (max_stars - rating)
    return filled + empty

def star_selector(key, current_value=None, label="Potentiel"):
    """Sélecteur d'étoiles avec tooltip"""
    tooltip_text = "1⭐ = Faible potentiel | 5⭐ = Potentiel maximum"
    
    options = [None, 1, 2, 3, 4, 5]
    labels = ["Non défini", "⭐ (Très faible)", "⭐⭐ (Faible)", "⭐⭐⭐ (Moyen)", "⭐⭐⭐⭐ (Fort)", "⭐⭐⭐⭐⭐ (Maximum)"]
    
    current_idx = 0
    if current_value is not None:
        try:
            current_idx = options.index(int(current_value))
        except:
            pass
    
    selected = st.selectbox(
        f"{label} ℹ️",
        options=range(len(options)),
        index=current_idx,
        format_func=lambda x: labels[x],
        help=tooltip_text,
        key=key
    )
    
    return options[selected]

# ==========================================
# FONCTIONS DB - RÉFÉRENTIELS
# ==========================================

def get_commerciaux():
    """Récupère les commerciaux depuis users_app (rôles commerciaux)"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT u.id, u.prenom, u.nom, r.libelle as role
            FROM users_app u
            JOIN roles r ON u.role_id = r.id
            WHERE u.is_active = TRUE 
            AND r.code IN ('SUPER_ADMIN', 'ADMIN_GENERAL', 'ADMIN_COMMERCIAL', 'USER_COMMERCIAL')
            ORDER BY u.nom, u.prenom
        """)
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        return [(r['id'], f"{r['prenom'] or ''} {r['nom'] or ''}".strip() or f"User #{r['id']}") for r in rows]
    except Exception as e:
        st.error(f"Erreur commerciaux: {e}")
        return []

def get_enseignes():
    """Récupère les enseignes"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, code, libelle FROM ref_enseignes WHERE is_active = TRUE ORDER BY ordre, libelle")
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        return [(r['id'], r['libelle']) for r in rows]
    except:
        return []

def get_types_client():
    """Récupère les types de client (liste fixe)"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, code, libelle FROM ref_types_client WHERE is_active = TRUE ORDER BY ordre")
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        return [(r['id'], r['libelle']) for r in rows]
    except:
        return []

def get_types_magasin():
    """Récupère les types de magasin"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT type_magasin FROM crm_magasins WHERE type_magasin IS NOT NULL AND type_magasin != '' ORDER BY type_magasin")
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        return [r['type_magasin'] for r in rows]
    except:
        return ['HYPER', 'SUPER', 'PROXIMITY', 'EXPRESS', 'CONTACT', 'Grossiste']

def get_centrales_achat():
    """Récupère les centrales d'achat existantes"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT centrale_achat FROM crm_magasins WHERE centrale_achat IS NOT NULL AND centrale_achat != '' ORDER BY centrale_achat")
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        return [r['centrale_achat'] for r in rows]
    except:
        return []

def get_types_reseau():
    """Récupère les types de réseau existants"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT type_reseau FROM crm_magasins WHERE type_reseau IS NOT NULL AND type_reseau != '' ORDER BY type_reseau")
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        return [r['type_reseau'] for r in rows]
    except:
        return []

def get_statuts():
    """Retourne la liste des statuts possibles"""
    return ['PROSPECT', 'ACTIF', 'INACTIF', 'EN_PAUSE', 'PERDU']

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
        return [(r['id'], r['code'], r['libelle']) for r in rows]
    except:
        return []

def save_magasin_marques(magasin_id, marque_ids):
    """Sauvegarde les marques d'un magasin"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        magasin_id = int(magasin_id)
        
        cursor.execute("UPDATE crm_magasins_marques SET is_active = FALSE WHERE magasin_id = %s", (magasin_id,))
        
        created_by = st.session_state.get('username', 'system')
        for marque_id in marque_ids:
            cursor.execute("""
                INSERT INTO crm_magasins_marques (magasin_id, marque_id, created_by, is_active)
                VALUES (%s, %s, %s, TRUE)
                ON CONFLICT (magasin_id, marque_id) DO UPDATE SET is_active = TRUE
            """, (magasin_id, int(marque_id), created_by))
        
        conn.commit()
        cursor.close()
        conn.close()
        return True
    except:
        return False

def save_magasin_produits(magasin_id, produit_ids):
    """Sauvegarde les types de produits d'un magasin"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        magasin_id = int(magasin_id)
        
        cursor.execute("UPDATE crm_magasins_produits SET is_active = FALSE WHERE magasin_id = %s", (magasin_id,))
        
        created_by = st.session_state.get('username', 'system')
        for produit_id in produit_ids:
            cursor.execute("""
                INSERT INTO crm_magasins_produits (magasin_id, type_produit_id, created_by, is_active)
                VALUES (%s, %s, %s, TRUE)
                ON CONFLICT (magasin_id, type_produit_id) DO UPDATE SET is_active = TRUE
            """, (magasin_id, int(produit_id), created_by))
        
        conn.commit()
        cursor.close()
        conn.close()
        return True
    except:
        return False

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

def get_magasins_produits_map():
    """Récupère la relation magasins-produits pour la carte"""
    try:
        conn = get_connection()
        if not conn:
            st.error("❌ Erreur connexion DB dans get_magasins_produits_map")
            return {}
        cursor = conn.cursor()
        cursor.execute("""
            SELECT magasin_id, type_produit_id 
            FROM crm_magasin_produits 
            WHERE is_active = TRUE
        """)
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        
        # Créer un dict magasin_id -> liste de produit_ids
        result = {}
        for row in rows:
            mid = row['magasin_id']
            pid = row['type_produit_id']
            if mid not in result:
                result[mid] = []
            result[mid].append(pid)
        return result
    except Exception as e:
        st.error(f"❌ Erreur get_magasins_produits_map: {str(e)}")
        return {}

def create_type_produit_crm(code, libelle, categorie='AUTRE'):
    """Crée un nouveau type de produit"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
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

def create_enseigne(libelle):
    """Crée une nouvelle enseigne"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        code = libelle.upper().replace(' ', '_').replace("'", "")
        cursor.execute("SELECT COALESCE(MAX(ordre), 0) + 1 as next_ordre FROM ref_enseignes")
        next_ordre = cursor.fetchone()['next_ordre']
        
        cursor.execute("""
            INSERT INTO ref_enseignes (code, libelle, ordre) 
            VALUES (%s, %s, %s)
            ON CONFLICT (code) DO UPDATE SET is_active = TRUE, libelle = EXCLUDED.libelle
            RETURNING id
        """, (code, libelle.strip(), next_ordre))
        new_id = cursor.fetchone()['id']
        conn.commit()
        cursor.close()
        conn.close()
        return new_id
    except:
        return None

# ==========================================
# FONCTIONS DB - MAGASINS (CRUD)
# ==========================================

def get_magasins(filtres=None):
    """Récupère tous les magasins avec filtres optionnels"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        query = """
            SELECT m.id, m.code_magasin, m.nom_client, m.ville, m.departement,
                m.statut, m.type_magasin, m.type_reseau, m.centrale_achat,
                m.enseigne_id, e.libelle as enseigne_libelle,
                m.type_client_id, tc.libelle as type_client_libelle,
                m.vente_directe, m.potentiel_etoiles,
                m.commercial_id,
                COALESCE(u.prenom || ' ' || u.nom, 'Non assigné') as commercial,
                m.adresse, m.code_postal,
                m.surface_m2, m.potentiel,
                m.points_amelioration, m.commentaires, m.notes,
                m.latitude, m.longitude,
                m.date_derniere_visite, m.date_prochaine_visite
            FROM crm_magasins m
            LEFT JOIN users_app u ON m.commercial_id = u.id
            LEFT JOIN ref_enseignes e ON m.enseigne_id = e.id
            LEFT JOIN ref_types_client tc ON m.type_client_id = tc.id
            WHERE m.is_active = TRUE
        """
        params = []
        
        if filtres:
            if filtres.get('nom_client') and filtres['nom_client'] != 'Tous':
                query += " AND m.nom_client = %s"
                params.append(filtres['nom_client'])
            if filtres.get('departement') and filtres['departement'] != 'Tous':
                query += " AND m.departement = %s"
                params.append(filtres['departement'])
            if filtres.get('commercial_id') and filtres['commercial_id'] != 0:
                query += " AND m.commercial_id = %s"
                params.append(int(filtres['commercial_id']))
            if filtres.get('statut') and filtres['statut'] != 'Tous':
                query += " AND m.statut = %s"
                params.append(filtres['statut'])
            if filtres.get('enseigne_id') and filtres['enseigne_id'] != 0:
                query += " AND m.enseigne_id = %s"
                params.append(int(filtres['enseigne_id']))
            if filtres.get('type_client_id') and filtres['type_client_id'] != 0:
                query += " AND m.type_client_id = %s"
                params.append(int(filtres['type_client_id']))
        
        query += " ORDER BY m.nom_client, m.ville"
        
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
            SELECT m.*, 
                   COALESCE(u.prenom || ' ' || u.nom, 'Non assigné') as commercial,
                   e.libelle as enseigne_libelle,
                   tc.libelle as type_client_libelle
            FROM crm_magasins m
            LEFT JOIN users_app u ON m.commercial_id = u.id
            LEFT JOIN ref_enseignes e ON m.enseigne_id = e.id
            LEFT JOIN ref_types_client tc ON m.type_client_id = tc.id
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
        
        # ⭐ V9.1: FK commercial_id corrigée - réactivé
        commercial_id = int(data['commercial_id']) if data.get('commercial_id') else None
        
        enseigne_id = int(data['enseigne_id']) if data.get('enseigne_id') else None
        type_client_id = int(data['type_client_id']) if data.get('type_client_id') else None
        
        cursor.execute("""
            INSERT INTO crm_magasins (
                nom_client, ville, departement, adresse, code_postal,
                commercial_id, centrale_achat, type_magasin, type_reseau,
                enseigne_id, type_client_id, vente_directe, potentiel_etoiles,
                surface_m2, statut,
                points_amelioration, commentaires, notes, 
                latitude, longitude, created_by
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (
            data['nom_client'], data['ville'], data.get('departement'),
            data.get('adresse'), data.get('code_postal'), commercial_id,
            data.get('centrale_achat'), data.get('type_magasin'), data.get('type_reseau'),
            enseigne_id, type_client_id, data.get('vente_directe', False),
            data.get('potentiel_etoiles'),
            data.get('surface_m2'), data.get('statut', 'PROSPECT'),
            data.get('points_amelioration'),
            data.get('commentaires'), data.get('notes'),
            data.get('latitude'), data.get('longitude'),
            st.session_state.get('username', 'system')
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
        # ⭐ V9.1: FK commercial_id corrigée - réactivé
        commercial_id = int(data['commercial_id']) if data.get('commercial_id') else None
        
        enseigne_id = int(data['enseigne_id']) if data.get('enseigne_id') else None
        type_client_id = int(data['type_client_id']) if data.get('type_client_id') else None
        
        cursor.execute("""
            UPDATE crm_magasins SET
                nom_client = %s, ville = %s, departement = %s, adresse = %s,
                code_postal = %s, commercial_id = %s, centrale_achat = %s,
                type_magasin = %s, type_reseau = %s,
                enseigne_id = %s, type_client_id = %s, vente_directe = %s,
                potentiel_etoiles = %s,
                surface_m2 = %s, statut = %s,
                points_amelioration = %s, commentaires = %s, notes = %s,
                latitude = %s, longitude = %s,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
        """, (
            data['nom_client'], data['ville'], data.get('departement'),
            data.get('adresse'), data.get('code_postal'), commercial_id,
            data.get('centrale_achat'), data.get('type_magasin'), data.get('type_reseau'),
            enseigne_id, type_client_id, data.get('vente_directe', False),
            data.get('potentiel_etoiles'),
            data.get('surface_m2'), data.get('statut'),
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

def update_magasin_gps(magasin_id, latitude, longitude):
    """Met à jour uniquement les coordonnées GPS"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE crm_magasins 
            SET latitude = %s, longitude = %s, updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
        """, (latitude, longitude, int(magasin_id)))
        conn.commit()
        cursor.close()
        conn.close()
        return True
    except:
        return False

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
# ⭐⭐⭐ COMPOSANT ADRESSE V9 - FIX DÉFINITIF ⭐⭐⭐
# ==========================================

def adresse_autocomplete_v9(prefix_key, initial_values=None, client_id=None):
    """
    Composant de recherche d'adresse avec autocomplétion - VERSION V9
    ⭐ FIX DÉFINITIF: Utilisation d'un SEUL dictionnaire dans session_state
    et mise à jour DIRECTE des clés des widgets
    """
    
    if initial_values is None:
        initial_values = {}
    
    # Clé unique basée sur prefix et client_id
    p = f"{prefix_key}_{client_id}" if client_id else prefix_key
    
    st.markdown("#### 🗺️ Adresse")
    
    # ⭐ Clé pour détecter changement de client
    client_key = f"{p}_current_client"
    
    # Réinitialiser si nouveau client
    if client_id and st.session_state.get(client_key) != client_id:
        st.session_state[client_key] = client_id
        # Nettoyer TOUTES les anciennes clés
        keys_to_clean = [k for k in st.session_state.keys() if k.startswith(p)]
        for k in keys_to_clean:
            if k != client_key:
                del st.session_state[k]
    
    # ⭐ Définir les clés des widgets (celles que Streamlit utilise)
    key_adresse = f"{p}_adresse_widget"
    key_cp = f"{p}_cp_widget"
    key_ville = f"{p}_ville_widget"
    key_dept = f"{p}_dept_widget"
    key_lat = f"{p}_lat_widget"
    key_lng = f"{p}_lng_widget"
    key_search = f"{p}_search_widget"
    key_select = f"{p}_select_widget"
    
    # ⭐ Initialiser les widgets avec valeurs initiales (seulement si pas déjà défini)
    if key_ville not in st.session_state:
        st.session_state[key_adresse] = safe_str(initial_values.get('adresse', ''))
        st.session_state[key_cp] = safe_str(initial_values.get('code_postal', ''))
        st.session_state[key_ville] = safe_str(initial_values.get('ville', ''))
        st.session_state[key_dept] = safe_str(initial_values.get('departement', ''))
        st.session_state[key_lat] = float(initial_values.get('latitude')) if initial_values.get('latitude') else 0.0
        st.session_state[key_lng] = float(initial_values.get('longitude')) if initial_values.get('longitude') else 0.0
    
    # Recherche d'adresse
    search_query = st.text_input(
        "🔍 Rechercher une adresse",
        placeholder="Tapez une adresse (ex: 12 rue de la Paix Paris)...",
        key=key_search
    )
    
    if search_query and len(search_query) >= 3:
        results = search_adresse(search_query)
        
        if results:
            options = ["-- Sélectionner une adresse --"] + [r['label'] for r in results]
            
            # ⭐ Utiliser on_change pour détecter la sélection
            def on_address_selected():
                selected = st.session_state.get(key_select)
                if selected and selected != "-- Sélectionner une adresse --":
                    # Trouver l'adresse sélectionnée
                    for r in results:
                        if r['label'] == selected:
                            # ⭐⭐⭐ MISE À JOUR DIRECTE DES CLÉS DES WIDGETS ⭐⭐⭐
                            st.session_state[key_adresse] = r.get('name', '')
                            st.session_state[key_cp] = r.get('postcode', '')
                            st.session_state[key_ville] = r.get('city', '')
                            st.session_state[key_dept] = r.get('departement', '')
                            st.session_state[key_lat] = float(r.get('latitude')) if r.get('latitude') else 0.0
                            st.session_state[key_lng] = float(r.get('longitude')) if r.get('longitude') else 0.0
                            break
            
            st.selectbox(
                "📍 Sélectionner une adresse",
                options,
                key=key_select,
                on_change=on_address_selected
            )
            
            # Confirmation visuelle si GPS disponible après sélection
            if st.session_state.get(key_lat, 0) != 0 and st.session_state.get(key_lng, 0) != 0:
                st.success(f"✅ Adresse sélectionnée - GPS: {st.session_state[key_lat]:.6f}, {st.session_state[key_lng]:.6f}")
    
    # ⭐ Champs - Streamlit va automatiquement utiliser les valeurs dans session_state[key]
    col1, col2 = st.columns(2)
    
    with col1:
        st.text_input("Adresse", key=key_adresse)
        st.text_input("Code postal", key=key_cp)
        st.text_input("Ville *", key=key_ville)
    
    with col2:
        st.text_input("Département", key=key_dept)
        st.number_input("Latitude", format="%.6f", key=key_lat)
        st.number_input("Longitude", format="%.6f", key=key_lng)
    
    # ⭐ Retourner les valeurs depuis session_state
    return {
        'adresse': st.session_state.get(key_adresse, ''),
        'code_postal': st.session_state.get(key_cp, ''),
        'ville': st.session_state.get(key_ville, ''),
        'departement': st.session_state.get(key_dept, ''),
        'latitude': st.session_state.get(key_lat) if st.session_state.get(key_lat, 0) != 0 else None,
        'longitude': st.session_state.get(key_lng) if st.session_state.get(key_lng, 0) != 0 else None
    }

# ==========================================
# ⭐ COMPOSANT PRÉSENCE PRODUIT V9
# ==========================================

def presence_produit_component_v9(prefix_key, magasin_id=None):
    """
    Composant pour gérer la présence produit - VERSION V9
    ⭐ Marques et produits séparés
    """
    
    st.markdown("#### 📦 Présence Produits")
    
    marques = get_marques_concurrentes()
    types_produits = get_types_produits_crm()
    
    current_marques = []
    current_produits = []
    
    if magasin_id:
        current_marques = [m[0] for m in get_magasin_marques(magasin_id)]
        current_produits = [p[0] for p in get_magasin_produits(magasin_id)]
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("##### 🏷️ Marques présentes")
        
        marques_options = {m[0]: m[1] for m in marques}
        selected_marques = st.multiselect(
            "Sélectionner les marques présentes",
            options=list(marques_options.keys()),
            default=current_marques,
            format_func=lambda x: marques_options.get(x, str(x)),
            key=f"{prefix_key}_marques"
        )
        
        with st.expander("➕ Ajouter une marque"):
            new_marque = st.text_input("Nom de la marque", key=f"{prefix_key}_new_marque")
            if st.button("Ajouter", key=f"{prefix_key}_btn_add_marque"):
                if new_marque:
                    new_id = create_marque_concurrente(new_marque)
                    if new_id:
                        st.success(f"✅ Marque '{new_marque}' ajoutée")
                        st.rerun()
    
    with col2:
        st.markdown("##### 📋 Types de produits")
        
        categories = {}
        for tp in types_produits:
            cat = tp[3] if tp[3] else 'AUTRE'
            if cat not in categories:
                categories[cat] = []
            categories[cat].append(tp)
        
        selected_produits = []
        for cat, prods in categories.items():
            st.markdown(f"**{cat}**")
            for prod in prods:
                checked = st.checkbox(
                    prod[2],
                    value=prod[0] in current_produits,
                    key=f"{prefix_key}_prod_{prod[0]}"
                )
                if checked:
                    selected_produits.append(prod[0])
        
        with st.expander("➕ Ajouter un type"):
            new_type_code = st.text_input("Code", key=f"{prefix_key}_new_type_code")
            new_type_lib = st.text_input("Libellé", key=f"{prefix_key}_new_type_lib")
            new_type_cat = st.selectbox("Catégorie", ['LA_CHAMPIONNE', 'MDD', 'AUTRE'], key=f"{prefix_key}_new_type_cat")
            if st.button("Ajouter", key=f"{prefix_key}_btn_add_type"):
                if new_type_code and new_type_lib:
                    new_id = create_type_produit_crm(new_type_code, new_type_lib, new_type_cat)
                    if new_id:
                        st.success(f"✅ Type '{new_type_lib}' ajouté")
                        st.rerun()
    
    return {
        'marques_ids': selected_marques,
        'produits_ids': selected_produits
    }

# ==========================================
# COMPOSANTS DROPDOWNS
# ==========================================

def dropdown_dynamique(label, options_list, current_value, key_prefix, allow_new=True):
    """Dropdown avec option d'ajout de nouvelle valeur"""
    
    options = [""] + options_list
    if allow_new:
        options = options + ["➕ Nouvelle valeur..."]
    
    current_idx = 0
    if current_value and current_value in options:
        current_idx = options.index(current_value)
    
    selected = st.selectbox(label, options, index=current_idx, key=f"{key_prefix}_select")
    
    if selected == "➕ Nouvelle valeur..." and allow_new:
        new_val = st.text_input(f"Nouveau {label}", key=f"{key_prefix}_new")
        return new_val if new_val else ""
    
    return selected if selected else ""

def enseigne_dropdown(current_value, key_prefix):
    """Dropdown enseigne avec possibilité d'ajout"""
    
    enseignes = get_enseignes()
    
    options = [(None, "-- Sélectionner --")] + enseignes + [(0, "➕ Nouvelle enseigne...")]
    
    current_idx = 0
    if current_value:
        for i, (eid, elib) in enumerate(options):
            if eid == current_value:
                current_idx = i
                break
    
    selected = st.selectbox(
        "Enseigne",
        options=range(len(options)),
        index=current_idx,
        format_func=lambda x: options[x][1],
        key=f"{key_prefix}_enseigne_select"
    )
    
    selected_id = options[selected][0]
    
    if selected_id == 0:
        new_enseigne = st.text_input("Nom de l'enseigne", key=f"{key_prefix}_new_enseigne")
        if new_enseigne:
            if st.button("Créer l'enseigne", key=f"{key_prefix}_btn_create_enseigne"):
                new_id = create_enseigne(new_enseigne)
                if new_id:
                    st.success(f"✅ Enseigne '{new_enseigne}' créée")
                    st.rerun()
        return None
    
    return selected_id

# ==========================================
# ONGLETS PRINCIPAUX
# ==========================================

tab1, tab2, tab3, tab4 = st.tabs(["📋 Liste clients", "➕ Nouveau client", "🗺️ Carte", "⚙️ Administration"])

# ==========================================
# TAB 1 : LISTE CLIENTS
# ==========================================

with tab1:
    st.subheader("📋 Liste des clients")
    
    commerciaux = get_commerciaux()
    enseignes = get_enseignes()
    types_client = get_types_client()
    
    col_f1, col_f2, col_f3, col_f4, col_f5 = st.columns(5)
    
    with col_f1:
        df_all = get_magasins()
        depts = ["Tous"] + sorted(df_all['departement'].dropna().unique().tolist()) if not df_all.empty else ["Tous"]
        filtre_dept = st.selectbox("Département", depts, key="f_dept")
    
    with col_f2:
        comm_options = [(0, "Tous")] + commerciaux
        filtre_comm = st.selectbox("Commercial", comm_options, format_func=lambda x: x[1], key="f_comm")
    
    with col_f3:
        statuts = ["Tous"] + get_statuts()
        filtre_statut = st.selectbox("Statut", statuts, key="f_statut")
    
    with col_f4:
        ens_options = [(0, "Toutes")] + enseignes
        filtre_enseigne = st.selectbox("Enseigne", ens_options, format_func=lambda x: x[1], key="f_enseigne")
    
    with col_f5:
        tc_options = [(0, "Tous")] + types_client
        filtre_type_client = st.selectbox("Type client", tc_options, format_func=lambda x: x[1], key="f_type_client")
    
    filtres = {}
    if filtre_dept != "Tous":
        filtres['departement'] = filtre_dept
    if filtre_comm[0] != 0:
        filtres['commercial_id'] = filtre_comm[0]
    if filtre_statut != "Tous":
        filtres['statut'] = filtre_statut
    if filtre_enseigne[0] != 0:
        filtres['enseigne_id'] = filtre_enseigne[0]
    if filtre_type_client[0] != 0:
        filtres['type_client_id'] = filtre_type_client[0]
    
    df = get_magasins(filtres) if filtres else df_all
    
    if not df.empty:
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("📊 Total", len(df))
        with col2:
            actifs = len(df[df['statut'] == 'ACTIF']) if 'statut' in df.columns else 0
            st.metric("✅ Actifs", actifs)
        with col3:
            prospects = len(df[df['statut'] == 'PROSPECT']) if 'statut' in df.columns else 0
            st.metric("🎯 Prospects", prospects)
        with col4:
            with_gps = len(df[df['latitude'].notna()]) if 'latitude' in df.columns else 0
            st.metric("📍 Avec GPS", with_gps)
        
        st.markdown("---")
        
        search_text = st.text_input("🔍 Recherche rapide", placeholder="Nom client, ville...", key="search_client")
        
        df_filtered = df.copy()
        if search_text:
            mask = df_filtered['nom_client'].str.contains(search_text, case=False, na=False) | \
                   df_filtered['ville'].str.contains(search_text, case=False, na=False)
            df_filtered = df_filtered[mask]
        
        df_display = df_filtered[['id', 'nom_client', 'ville', 'departement', 'commercial', 'enseigne_libelle', 'type_client_libelle', 'statut', 'potentiel_etoiles']].copy()
        df_display.columns = ['ID', 'Nom Client', 'Ville', 'Dép', 'Commercial', 'Enseigne', 'Type', 'Statut', 'Potentiel']
        df_display['Potentiel'] = df_display['Potentiel'].apply(lambda x: render_stars(x) if pd.notna(x) else '-')
        
        st.markdown(f"**{len(df_filtered)} client(s)** - 👆 Cliquez sur une ligne pour sélectionner")
        
        event = st.dataframe(
            df_display,
            use_container_width=True,
            hide_index=True,
            on_select="rerun",
            selection_mode="single-row",
            key="clients_table"
        )
        
        selected_rows = event.selection.rows if hasattr(event, 'selection') and event.selection else []
        
        if selected_rows:
            selected_idx = selected_rows[0]
            selected_id = df_filtered.iloc[selected_idx]['id']
            
            st.markdown("---")
            mag = get_magasin_by_id(selected_id)
            
            if mag:
                st.subheader(f"🏪 {mag['nom_client']} - {mag['ville']}")
                
                col_actions = st.columns(4)
                with col_actions[0]:
                    if st.button("✏️ Modifier", type="primary", use_container_width=True):
                        st.session_state['edit_mode'] = selected_id
                        # Reset les données d'adresse pour ce client
                        p = f"edit_{selected_id}"
                        keys_to_clean = [k for k in st.session_state.keys() if k.startswith(p)]
                        for k in keys_to_clean:
                            del st.session_state[k]
                        st.rerun()
                
                with col_actions[1]:
                    if can_edit("CRM"):
                        if st.button("🗑️ Supprimer", type="secondary", use_container_width=True):
                            if st.session_state.get('confirm_delete') == selected_id:
                                success, msg = delete_magasin(selected_id)
                                if success:
                                    st.success(msg)
                                    st.session_state.pop('confirm_delete', None)
                                    st.rerun()
                                else:
                                    st.error(msg)
                            else:
                                st.session_state['confirm_delete'] = selected_id
                                st.warning("⚠️ Cliquez à nouveau pour confirmer")
                
                if st.session_state.get('edit_mode') == selected_id:
                    st.markdown("---")
                    st.subheader("✏️ Modifier le client")
                    
                    commerciaux_edit = get_commerciaux()
                    centrales_edit = get_centrales_achat()
                    types_magasin_edit = get_types_magasin()
                    types_reseau_edit = get_types_reseau()
                    types_client_edit = get_types_client()
                    
                    col_edit1, col_edit2 = st.columns(2)
                    
                    with col_edit1:
                        st.markdown("#### 🏪 Informations client")
                        edit_nom_client = st.text_input("Nom Client / Raison sociale *", value=safe_str(mag.get('nom_client')), key="edit_nom")
                        
                        comm_edit_list = [(None, 'Non assigné')] + commerciaux_edit
                        current_comm_idx = 0
                        if mag.get('commercial_id'):
                            for i, (cid, cname) in enumerate(comm_edit_list):
                                if cid == mag.get('commercial_id'):
                                    current_comm_idx = i
                                    break
                        edit_commercial = st.selectbox("Commercial", comm_edit_list, index=current_comm_idx, format_func=lambda x: x[1], key="edit_comm")
                        
                        edit_enseigne_id = enseigne_dropdown(mag.get('enseigne_id'), "edit")
                        
                        tc_options = [(None, '-- Sélectionner --')] + types_client_edit
                        current_tc_idx = 0
                        if mag.get('type_client_id'):
                            for i, (tcid, tclib) in enumerate(tc_options):
                                if tcid == mag.get('type_client_id'):
                                    current_tc_idx = i
                                    break
                        edit_type_client = st.selectbox("Type de client", tc_options, index=current_tc_idx, format_func=lambda x: x[1], key="edit_type_client")
                        
                        edit_centrale = dropdown_dynamique("Centrale d'achat ou MIN de rattachement", centrales_edit, safe_str(mag.get('centrale_achat')), "edit_centrale")
                        edit_type_magasin = dropdown_dynamique("Type de magasin", types_magasin_edit, safe_str(mag.get('type_magasin')), "edit_type_magasin")
                        edit_type_reseau = dropdown_dynamique("Type réseau", types_reseau_edit, safe_str(mag.get('type_reseau')), "edit_type_reseau")
                        
                        edit_surface = st.number_input("Surface m²", min_value=0, value=safe_int(mag.get('surface_m2')), key="edit_surf")
                        edit_potentiel = star_selector("edit_pot_stars", mag.get('potentiel_etoiles'), "Potentiel")
                        edit_vente_directe = st.checkbox("Vente directe", value=mag.get('vente_directe', False), key="edit_vente_directe")
                        edit_statut = st.selectbox("Statut", get_statuts(), 
                                                   index=get_statuts().index(mag.get('statut', 'PROSPECT')) if mag.get('statut') in get_statuts() else 0,
                                                   key="edit_stat")
                    
                    with col_edit2:
                        # ⭐ V9: Composant adresse avec client_id
                        adresse_data_edit = adresse_autocomplete_v9("edit", {
                            'adresse': mag.get('adresse'),
                            'code_postal': mag.get('code_postal'),
                            'ville': mag.get('ville'),
                            'departement': mag.get('departement'),
                            'latitude': mag.get('latitude'),
                            'longitude': mag.get('longitude')
                        }, client_id=selected_id)
                    
                    st.markdown("---")
                    presence_data = presence_produit_component_v9("edit", selected_id)
                    
                    edit_notes = st.text_area("Notes", value=safe_str(mag.get('notes')), key="edit_notes", height=80)
                    
                    col_save, col_cancel = st.columns(2)
                    
                    with col_save:
                        if st.button("💾 Enregistrer", type="primary", use_container_width=True, key="btn_save_edit"):
                            if not edit_nom_client:
                                st.error("❌ Le nom client est obligatoire")
                            elif not adresse_data_edit['ville']:
                                st.error("❌ La ville est obligatoire")
                            else:
                                update_data = {
                                    'nom_client': edit_nom_client,
                                    'ville': adresse_data_edit['ville'],
                                    'departement': adresse_data_edit['departement'] or None,
                                    'adresse': adresse_data_edit['adresse'] or None,
                                    'code_postal': adresse_data_edit['code_postal'] or None,
                                    'latitude': adresse_data_edit['latitude'],
                                    'longitude': adresse_data_edit['longitude'],
                                    'commercial_id': edit_commercial[0],
                                    'enseigne_id': edit_enseigne_id,
                                    'type_client_id': edit_type_client[0] if edit_type_client[0] else None,
                                    'centrale_achat': edit_centrale or None,
                                    'type_magasin': edit_type_magasin or None,
                                    'type_reseau': edit_type_reseau or None,
                                    'surface_m2': edit_surface if edit_surface > 0 else None,
                                    'potentiel_etoiles': edit_potentiel,
                                    'vente_directe': edit_vente_directe,
                                    'statut': edit_statut,
                                    'notes': edit_notes or None
                                }
                                success, msg = update_magasin(selected_id, update_data)
                                
                                if success:
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
                
                else:
                    # ⭐ V9: Affichage récap avec marques ET produits
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.markdown("#### 📋 Informations")
                        st.write(f"**Adresse** : {mag.get('adresse') or '-'}")
                        st.write(f"**Ville** : {mag['ville']} ({mag.get('departement') or '-'})")
                        st.write(f"**Commercial** : {mag.get('commercial', 'Non assigné')}")
                        st.write(f"**Enseigne** : {mag.get('enseigne_libelle') or '-'}")
                        st.write(f"**Type client** : {mag.get('type_client_libelle') or '-'}")
                        st.write(f"**Centrale/MIN** : {mag.get('centrale_achat') or '-'}")
                        st.write(f"**Type magasin** : {mag.get('type_magasin') or '-'}")
                        st.write(f"**Potentiel** : {render_stars(mag.get('potentiel_etoiles'))}")
                        st.write(f"**Vente directe** : {'Oui' if mag.get('vente_directe') else 'Non'}")
                        
                        if mag.get('latitude') and mag.get('longitude'):
                            st.write(f"**GPS** : {mag['latitude']:.6f}, {mag['longitude']:.6f}")
                        else:
                            st.write("**GPS** : Non renseigné")
                    
                    with col2:
                        st.markdown("#### 📊 Statistiques")
                        st.write(f"**Surface** : {mag.get('surface_m2') or '-'} m²")
                        st.write(f"**Statut** : {mag.get('statut') or '-'}")
                        
                        if mag.get('notes'):
                            st.markdown("#### 📝 Notes")
                            st.write(mag['notes'])
                    
                    # ⭐ V9.1: Section Présence Produits avec checkboxes pour upsell
                    st.markdown("---")
                    st.markdown("#### 📦 Présence Produits")
                    
                    col_p1, col_p2 = st.columns(2)
                    
                    with col_p1:
                        st.markdown("##### 🏷️ Marques présentes")
                        marques_mag = get_magasin_marques(selected_id)
                        if marques_mag:
                            for m in marques_mag:
                                st.write(f"✅ {m[1]}")
                        else:
                            st.info("Aucune marque renseignée")
                    
                    with col_p2:
                        st.markdown("##### 📋 Types produits")
                        # Récupérer TOUS les types de produits
                        all_types_produits = get_types_produits_crm()
                        # Récupérer ceux du magasin
                        produits_mag = get_magasin_produits(selected_id)
                        produits_mag_ids = [p[0] for p in produits_mag]
                        
                        if all_types_produits:
                            # Grouper par catégorie
                            categories = {}
                            for tp in all_types_produits:
                                cat = tp[3] if tp[3] else 'AUTRE'
                                if cat not in categories:
                                    categories[cat] = []
                                categories[cat].append(tp)
                            
                            for cat, prods in categories.items():
                                st.markdown(f"**{cat}**")
                                for prod in prods:
                                    is_selected = prod[0] in produits_mag_ids
                                    # Checkbox désactivée (lecture seule)
                                    st.checkbox(
                                        prod[2],
                                        value=is_selected,
                                        disabled=True,
                                        key=f"recap_prod_{selected_id}_{prod[0]}"
                                    )
                        else:
                            st.info("Aucun type de produit défini")
        else:
            st.info("👆 Cliquez sur une ligne du tableau pour sélectionner un client")
    else:
        st.info("📭 Aucun client trouvé")

# ==========================================
# TAB 2 : NOUVEAU CLIENT
# ==========================================

with tab2:
    st.subheader("➕ Nouveau client")
    
    if can_edit("CRM"):
        commerciaux = get_commerciaux()
        centrales_list = get_centrales_achat()
        types_magasin_list = get_types_magasin()
        types_reseau_list = get_types_reseau()
        types_client_list = get_types_client()
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("#### 🏪 Informations client")
            new_nom_client = st.text_input("Nom Client / Raison sociale *", key="new_nom")
            
            comm_list = [(None, 'Non assigné')] + commerciaux
            new_commercial = st.selectbox("Commercial", comm_list, format_func=lambda x: x[1], key="new_comm")
            
            new_enseigne_id = enseigne_dropdown(None, "new")
            
            tc_options = [(None, '-- Sélectionner --')] + types_client_list
            new_type_client = st.selectbox("Type de client", tc_options, format_func=lambda x: x[1], key="new_type_client")
            
            new_centrale = dropdown_dynamique("Centrale d'achat ou MIN de rattachement", centrales_list, "", "new_centrale")
            new_type_magasin = dropdown_dynamique("Type de magasin", types_magasin_list, "", "new_type_magasin")
            new_type_reseau = dropdown_dynamique("Type réseau", types_reseau_list, "", "new_type_reseau")
            
            new_surface = st.number_input("Surface m²", min_value=0, value=0, key="new_surf")
            new_potentiel = star_selector("new_pot_stars", None, "Potentiel")
            new_vente_directe = st.checkbox("Vente directe", value=False, key="new_vente_directe")
            new_statut = st.selectbox("Statut", get_statuts(), key="new_stat")
        
        with col2:
            # ⭐ V9: Composant adresse pour nouveau client
            adresse_data = adresse_autocomplete_v9("new", {})
        
        st.markdown("---")
        presence_data = presence_produit_component_v9("new")
        
        new_notes = st.text_area("Notes", key="new_notes", height=80)
        
        if st.button("✅ Créer le client", type="primary", key="btn_create"):
            if not new_nom_client:
                st.error("❌ Le nom client est obligatoire")
            elif not adresse_data['ville']:
                st.error("❌ La ville est obligatoire")
            else:
                data = {
                    'nom_client': new_nom_client,
                    'ville': adresse_data['ville'],
                    'departement': adresse_data['departement'] or None,
                    'adresse': adresse_data['adresse'] or None,
                    'code_postal': adresse_data['code_postal'] or None,
                    'latitude': adresse_data['latitude'],
                    'longitude': adresse_data['longitude'],
                    'commercial_id': new_commercial[0],
                    'enseigne_id': new_enseigne_id,
                    'type_client_id': new_type_client[0] if new_type_client[0] else None,
                    'centrale_achat': new_centrale or None,
                    'type_magasin': new_type_magasin or None,
                    'type_reseau': new_type_reseau or None,
                    'surface_m2': new_surface if new_surface > 0 else None,
                    'potentiel_etoiles': new_potentiel,
                    'vente_directe': new_vente_directe,
                    'statut': new_statut,
                    'notes': new_notes or None
                }
                success, result = create_magasin(data)
                
                if success:
                    new_id = result
                    save_magasin_marques(new_id, presence_data['marques_ids'])
                    save_magasin_produits(new_id, presence_data['produits_ids'])
                    
                    st.success(f"✅ Client créé (ID: {new_id})")
                    st.balloons()
                    # Nettoyer le session_state
                    for k in list(st.session_state.keys()):
                        if k.startswith('new_'):
                            st.session_state.pop(k, None)
                else:
                    st.error(f"❌ Erreur : {result}")
    else:
        st.warning("⚠️ Vous n'avez pas les droits pour créer des clients")

# ==========================================
# TAB 3 : CARTE
# ==========================================

with tab3:
    st.subheader("🗺️ Carte des clients")
    
    df_all = get_magasins()
    
    if not df_all.empty:
        df_geo = df_all[df_all['latitude'].notna() & df_all['longitude'].notna()].copy()
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("📊 Total", len(df_all))
        with col2:
            st.metric("📍 Avec GPS", len(df_geo))
        with col3:
            st.metric("❌ Sans GPS", len(df_all) - len(df_geo))
        
        st.markdown("---")
        
        if can_edit("CRM"):
            df_sans_gps = df_all[df_all['latitude'].isna() | df_all['longitude'].isna()].copy()
            
            if len(df_sans_gps) > 0:
                st.warning(f"⚠️ {len(df_sans_gps)} clients sans coordonnées GPS")
                
                if st.button("🌍 Géocoder tous les clients sans GPS", type="primary"):
                    progress_bar = st.progress(0)
                    status_text = st.empty()
                    
                    success_count = 0
                    error_count = 0
                    total = len(df_sans_gps)
                    
                    for i, (idx, row) in enumerate(df_sans_gps.iterrows()):
                        adresse_parts = []
                        if row.get('adresse'):
                            adresse_parts.append(str(row['adresse']))
                        if row.get('code_postal'):
                            adresse_parts.append(str(row['code_postal']))
                        if row.get('ville'):
                            adresse_parts.append(str(row['ville']))
                        
                        if adresse_parts:
                            adresse_complete = ' '.join(adresse_parts)
                            status_text.text(f"🔍 Géocodage: {row['nom_client']} - {row['ville']}...")
                            
                            coords = geocode_adresse(adresse_complete)
                            
                            if coords and coords.get('latitude') and coords.get('longitude'):
                                if update_magasin_gps(row['id'], coords['latitude'], coords['longitude']):
                                    success_count += 1
                                else:
                                    error_count += 1
                            else:
                                error_count += 1
                        
                        progress_bar.progress((i + 1) / total)
                    
                    status_text.empty()
                    progress_bar.empty()
                    
                    st.success(f"✅ Géocodage terminé: {success_count} réussis, {error_count} échecs")
                    st.rerun()
        
        if not df_geo.empty:
            st.markdown("### 📍 Carte des clients géolocalisés")
            
            # ⭐ V9.2: FILTRES AVANCÉS
            st.markdown("#### 🔍 Filtres")
            
            col_f1, col_f2, col_f3, col_f4 = st.columns(4)
            
            with col_f1:
                # Filtre enseignes
                enseignes_list = get_enseignes()
                enseigne_options = ['Toutes'] + [e[1] for e in enseignes_list]
                filtre_enseignes = st.multiselect("Enseignes", enseigne_options, default=['Toutes'], key="map_enseigne")
            
            with col_f2:
                # Filtre commerciaux
                commerciaux_list = get_commerciaux()
                commercial_options = ['Tous'] + [c[1] for c in commerciaux_list]
                filtre_commerciaux = st.multiselect("Commerciaux", commercial_options, default=['Tous'], key="map_commercial")
            
            with col_f3:
                # Filtre statuts
                statut_options = ['Tous'] + get_statuts()
                filtre_statuts = st.multiselect("Statuts", statut_options, default=['Tous'], key="map_statut")
            
            with col_f4:
                # Filtre types client
                types_client = get_types_client()
                type_client_options = ['Tous'] + [t[1] for t in types_client]
                filtre_types_client = st.multiselect("Types client", type_client_options, default=['Tous'], key="map_type_client")
            
            # Filtre produits (ligne séparée pour plus de place)
            types_produits = get_types_produits_crm()
            produit_options = [(tp[0], tp[2]) for tp in types_produits]  # (id, libelle)
            filtre_produits = st.multiselect(
                "📦 Filtrer par produits présents", 
                options=[p[0] for p in produit_options],
                format_func=lambda x: next((p[1] for p in produit_options if p[0] == x), str(x)),
                key="map_produits"
            )
            
            st.markdown("---")
            
            # Appliquer les filtres
            df_filtered = df_geo.copy()
            
            # Filtre enseignes
            if 'Toutes' not in filtre_enseignes and filtre_enseignes:
                df_filtered = df_filtered[df_filtered['enseigne_libelle'].isin(filtre_enseignes)]
            
            # Filtre commerciaux
            if 'Tous' not in filtre_commerciaux and filtre_commerciaux:
                df_filtered = df_filtered[df_filtered['commercial'].isin(filtre_commerciaux)]
            
            # Filtre statuts
            if 'Tous' not in filtre_statuts and filtre_statuts:
                df_filtered = df_filtered[df_filtered['statut'].isin(filtre_statuts)]
            
            # Filtre types client
            if 'Tous' not in filtre_types_client and filtre_types_client:
                df_filtered = df_filtered[df_filtered['type_client_libelle'].isin(filtre_types_client)]
            
            # Filtre produits (magasins ayant AU MOINS UN des produits sélectionnés)
            if filtre_produits:
                magasins_produits = get_magasins_produits_map()
                # Debug: afficher le nombre d'associations trouvées
                if not magasins_produits:
                    st.warning("⚠️ Aucune association magasin-produit trouvée dans crm_magasin_produits")
                magasins_avec_produits = [
                    mid for mid, pids in magasins_produits.items() 
                    if any(p in pids for p in filtre_produits)
                ]
                df_filtered = df_filtered[df_filtered['id'].isin(magasins_avec_produits)]
            
            st.info(f"📊 **{len(df_filtered)}** clients affichés sur **{len(df_geo)}** géolocalisés")
            
            if not df_filtered.empty:
                # ⭐ V9.2: CARTE FOLIUM INTERACTIVE
                # Centre de la carte
                center_lat = df_filtered['latitude'].astype(float).mean()
                center_lon = df_filtered['longitude'].astype(float).mean()
                
                # Créer la carte
                m = folium.Map(
                    location=[center_lat, center_lon], 
                    zoom_start=6,
                    tiles='OpenStreetMap'
                )
                
                # Couleurs par statut
                statut_colors = {
                    'PROSPECT': 'blue',
                    'CLIENT_ACTIF': 'green',
                    'CLIENT_INACTIF': 'orange',
                    'PERDU': 'red',
                    'EN_NEGOCIATION': 'purple'
                }
                
                # Ajouter les marqueurs
                for _, row in df_filtered.iterrows():
                    lat = float(row['latitude'])
                    lon = float(row['longitude'])
                    
                    # Infos pour le tooltip (survol)
                    tooltip_text = f"""
                    <b>{row['nom_client']}</b><br>
                    🏷️ {row.get('enseigne_libelle') or 'Sans enseigne'}<br>
                    👤 {row.get('commercial') or 'Non assigné'}<br>
                    📍 {row.get('ville')}
                    """
                    
                    # Infos pour le popup (clic)
                    pot_val = row.get('potentiel_etoiles')
                    potentiel_stars = '⭐' * int(pot_val) if pd.notna(pot_val) and pot_val else ''
                    popup_html = f"""
                    <div style="width:200px">
                        <h4>{row['nom_client']}</h4>
                        <p><b>Enseigne:</b> {row.get('enseigne_libelle') or '-'}</p>
                        <p><b>Commercial:</b> {row.get('commercial') or 'Non assigné'}</p>
                        <p><b>Ville:</b> {row.get('ville')}</p>
                        <p><b>Statut:</b> {row.get('statut') or '-'}</p>
                        <p><b>Potentiel:</b> {potentiel_stars or '-'}</p>
                        <p><b>Type:</b> {row.get('type_client_libelle') or '-'}</p>
                    </div>
                    """
                    
                    # Couleur du marqueur
                    color = statut_colors.get(row.get('statut'), 'gray')
                    
                    folium.Marker(
                        location=[lat, lon],
                        popup=folium.Popup(popup_html, max_width=250),
                        tooltip=tooltip_text,
                        icon=folium.Icon(color=color, icon='info-sign')
                    ).add_to(m)
                
                # Légende
                legend_html = """
                <div style="position: fixed; bottom: 50px; left: 50px; z-index: 1000; 
                            background: white; padding: 10px; border-radius: 5px; border: 2px solid grey;">
                    <b>Légende</b><br>
                    🔵 Prospect<br>
                    🟢 Client Actif<br>
                    🟠 Client Inactif<br>
                    🔴 Perdu<br>
                    🟣 En négociation
                </div>
                """
                m.get_root().html.add_child(folium.Element(legend_html))
                
                # Afficher la carte
                st_folium(m, width=None, height=600, use_container_width=True)
            else:
                st.warning("⚠️ Aucun client ne correspond aux filtres sélectionnés")
        else:
            st.info("📭 Aucun client géolocalisé à afficher")
    else:
        st.info("📭 Aucun client enregistré")

# ==========================================
# TAB 4 : ADMINISTRATION - V9 COMPLET
# ==========================================

with tab4:
    st.subheader("⚙️ Administration des listes")
    
    if can_admin("CRM") or is_super_admin():
        
        # ⭐ V9: 8 onglets au lieu de 4
        admin_tabs = st.tabs([
            "🏷️ Enseignes", 
            "📦 Types produits", 
            "🏪 Types magasin",
            "🏢 Centrales/MIN",
            "🔗 Types réseau",
            "📊 Statuts",
            "🏷️ Marques",
            "👥 Types client"
        ])
        
        # === ENSEIGNES ===
        with admin_tabs[0]:
            st.markdown("### Gestion des enseignes")
            
            enseignes = get_enseignes()
            
            if enseignes:
                for eid, elib in enseignes:
                    col1, col2 = st.columns([4, 1])
                    with col1:
                        st.write(f"• {elib}")
                    with col2:
                        if st.button("🗑️", key=f"del_ens_{eid}", help="Supprimer"):
                            try:
                                conn = get_connection()
                                cursor = conn.cursor()
                                cursor.execute("UPDATE ref_enseignes SET is_active = FALSE WHERE id = %s", (eid,))
                                conn.commit()
                                cursor.close()
                                conn.close()
                                st.rerun()
                            except Exception as e:
                                st.error(f"Erreur: {e}")
            
            st.markdown("---")
            new_enseigne = st.text_input("Nouvelle enseigne", key="admin_new_enseigne")
            if st.button("➕ Ajouter", key="admin_btn_add_enseigne"):
                if new_enseigne:
                    if create_enseigne(new_enseigne):
                        st.success("✅ Enseigne ajoutée")
                        st.rerun()
        
        # === TYPES PRODUITS ===
        with admin_tabs[1]:
            st.markdown("### Gestion des types de produits CRM")
            
            types_produits = get_types_produits_crm()
            
            if types_produits:
                for tp in types_produits:
                    col1, col2, col3 = st.columns([3, 2, 1])
                    with col1:
                        st.write(f"• {tp[2]} ({tp[1]})")
                    with col2:
                        st.caption(f"Catégorie: {tp[3]}")
                    with col3:
                        if st.button("🗑️", key=f"del_tp_{tp[0]}", help="Supprimer"):
                            try:
                                conn = get_connection()
                                cursor = conn.cursor()
                                cursor.execute("UPDATE ref_types_produits_crm SET is_active = FALSE WHERE id = %s", (tp[0],))
                                conn.commit()
                                cursor.close()
                                conn.close()
                                st.rerun()
                            except Exception as e:
                                st.error(f"Erreur: {e}")
            
            st.markdown("---")
            col1, col2, col3 = st.columns(3)
            with col1:
                new_tp_code = st.text_input("Code", key="admin_new_tp_code")
            with col2:
                new_tp_lib = st.text_input("Libellé", key="admin_new_tp_lib")
            with col3:
                new_tp_cat = st.selectbox("Catégorie", ['LA_CHAMPIONNE', 'MDD', 'AUTRE'], key="admin_new_tp_cat")
            
            if st.button("➕ Ajouter", key="admin_btn_add_tp"):
                if new_tp_code and new_tp_lib:
                    if create_type_produit_crm(new_tp_code, new_tp_lib, new_tp_cat):
                        st.success("✅ Type produit ajouté")
                        st.rerun()
        
        # === TYPES MAGASIN (V9: MODIFIABLE) ===
        with admin_tabs[2]:
            st.markdown("### Gestion des types de magasin")
            
            types_magasin = get_types_magasin()
            
            if types_magasin:
                for tm in types_magasin:
                    col1, col2 = st.columns([4, 1])
                    with col1:
                        st.write(f"• {tm}")
                    with col2:
                        if st.button("🗑️", key=f"del_tm_{tm}", help="Supprimer (met à NULL)"):
                            try:
                                conn = get_connection()
                                cursor = conn.cursor()
                                cursor.execute("UPDATE crm_magasins SET type_magasin = NULL WHERE type_magasin = %s", (tm,))
                                conn.commit()
                                cursor.close()
                                conn.close()
                                st.success(f"✅ Type '{tm}' supprimé")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Erreur: {e}")
            else:
                st.info("Aucun type de magasin défini")
            
            st.markdown("---")
            st.info("💡 Les types de magasin sont ajoutés lors de la création/modification de clients. Vous pouvez supprimer un type (les clients concernés auront un type vide).")
            
            new_type_mag = st.text_input("Nouveau type de magasin", key="admin_new_type_mag")
            if st.button("➕ Ajouter", key="admin_btn_add_type_mag"):
                if new_type_mag:
                    st.info(f"💡 Le type '{new_type_mag}' sera disponible lors de la prochaine création/modification de client.")
        
        # === CENTRALES / MIN (V9: NOUVEAU) ===
        with admin_tabs[3]:
            st.markdown("### Gestion des Centrales d'achat / MIN")
            
            centrales = get_centrales_achat()
            
            if centrales:
                for ca in centrales:
                    col1, col2 = st.columns([4, 1])
                    with col1:
                        st.write(f"• {ca}")
                    with col2:
                        if st.button("🗑️", key=f"del_ca_{ca}", help="Supprimer (met à NULL)"):
                            try:
                                conn = get_connection()
                                cursor = conn.cursor()
                                cursor.execute("UPDATE crm_magasins SET centrale_achat = NULL WHERE centrale_achat = %s", (ca,))
                                conn.commit()
                                cursor.close()
                                conn.close()
                                st.success(f"✅ Centrale '{ca}' supprimée")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Erreur: {e}")
            else:
                st.info("Aucune centrale d'achat définie")
            
            st.markdown("---")
            st.info("💡 Les centrales sont ajoutées lors de la création/modification de clients via '➕ Nouvelle valeur...'")
        
        # === TYPES RÉSEAU (V9: NOUVEAU) ===
        with admin_tabs[4]:
            st.markdown("### Gestion des types de réseau")
            
            types_reseau = get_types_reseau()
            
            if types_reseau:
                for tr in types_reseau:
                    col1, col2 = st.columns([4, 1])
                    with col1:
                        st.write(f"• {tr}")
                    with col2:
                        if st.button("🗑️", key=f"del_tr_{tr}", help="Supprimer (met à NULL)"):
                            try:
                                conn = get_connection()
                                cursor = conn.cursor()
                                cursor.execute("UPDATE crm_magasins SET type_reseau = NULL WHERE type_reseau = %s", (tr,))
                                conn.commit()
                                cursor.close()
                                conn.close()
                                st.success(f"✅ Type réseau '{tr}' supprimé")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Erreur: {e}")
            else:
                st.info("Aucun type de réseau défini")
            
            st.markdown("---")
            st.info("💡 Les types de réseau sont ajoutés lors de la création/modification de clients via '➕ Nouvelle valeur...'")
        
        # === STATUTS (V9: NOUVEAU) ===
        with admin_tabs[5]:
            st.markdown("### Gestion des statuts")
            
            statuts = get_statuts()
            
            st.info("ℹ️ Les statuts sont prédéfinis dans le système et ne peuvent pas être modifiés.")
            
            for s in statuts:
                st.write(f"• {s}")
        
        # === MARQUES ===
        with admin_tabs[6]:
            st.markdown("### Gestion des marques concurrentes")
            
            marques = get_marques_concurrentes()
            
            if marques:
                for mid, mnom in marques:
                    col1, col2 = st.columns([4, 1])
                    with col1:
                        st.write(f"• {mnom}")
                    with col2:
                        if st.button("🗑️", key=f"del_marque_{mid}", help="Supprimer"):
                            try:
                                conn = get_connection()
                                cursor = conn.cursor()
                                cursor.execute("UPDATE ref_marques_concurrentes SET is_active = FALSE WHERE id = %s", (mid,))
                                conn.commit()
                                cursor.close()
                                conn.close()
                                st.rerun()
                            except Exception as e:
                                st.error(f"Erreur: {e}")
            
            st.markdown("---")
            new_marque = st.text_input("Nouvelle marque", key="admin_new_marque")
            if st.button("➕ Ajouter", key="admin_btn_add_marque"):
                if new_marque:
                    if create_marque_concurrente(new_marque):
                        st.success("✅ Marque ajoutée")
                        st.rerun()
        
        # === TYPES CLIENT (V9: NOUVEAU) ===
        with admin_tabs[7]:
            st.markdown("### Gestion des types de client")
            
            types_client = get_types_client()
            
            st.info("ℹ️ Les types de client sont gérés dans la table ref_types_client.")
            
            if types_client:
                for tcid, tclib in types_client:
                    col1, col2 = st.columns([4, 1])
                    with col1:
                        st.write(f"• {tclib}")
                    with col2:
                        if st.button("🗑️", key=f"del_tc_{tcid}", help="Désactiver"):
                            try:
                                conn = get_connection()
                                cursor = conn.cursor()
                                cursor.execute("UPDATE ref_types_client SET is_active = FALSE WHERE id = %s", (tcid,))
                                conn.commit()
                                cursor.close()
                                conn.close()
                                st.rerun()
                            except Exception as e:
                                st.error(f"Erreur: {e}")
            
            st.markdown("---")
            col1, col2 = st.columns(2)
            with col1:
                new_tc_code = st.text_input("Code", key="admin_new_tc_code")
            with col2:
                new_tc_lib = st.text_input("Libellé", key="admin_new_tc_lib")
            
            if st.button("➕ Ajouter", key="admin_btn_add_tc"):
                if new_tc_code and new_tc_lib:
                    try:
                        conn = get_connection()
                        cursor = conn.cursor()
                        cursor.execute("SELECT COALESCE(MAX(ordre), 0) + 1 as next_ordre FROM ref_types_client")
                        next_ordre = cursor.fetchone()['next_ordre']
                        cursor.execute("""
                            INSERT INTO ref_types_client (code, libelle, ordre) VALUES (%s, %s, %s)
                            ON CONFLICT (code) DO UPDATE SET is_active = TRUE, libelle = EXCLUDED.libelle
                        """, (new_tc_code.upper(), new_tc_lib, next_ordre))
                        conn.commit()
                        cursor.close()
                        conn.close()
                        st.success("✅ Type client ajouté")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Erreur: {e}")
    
    else:
        st.warning("⚠️ Accès réservé aux administrateurs")

show_footer()
