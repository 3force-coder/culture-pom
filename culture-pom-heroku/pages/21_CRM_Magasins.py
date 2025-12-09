import streamlit as st
import pandas as pd
import requests
from datetime import datetime
from database import get_connection
from components import show_footer
from auth import is_authenticated, require_access, can_edit, can_delete

st.set_page_config(page_title="Proto API Adresse - Culture Pom", page_icon="🧪", layout="wide")

if not is_authenticated():
    st.warning("⚠️ Veuillez vous connecter")
    st.stop()

require_access("CRM")

st.markdown("""
<style>
    .block-container { padding-top: 1.5rem !important; padding-bottom: 0.5rem !important; }
    h1, h2, h3, h4 { margin-top: 0.3rem !important; margin-bottom: 0.3rem !important; }
    
    /* Style pour les suggestions d'adresse */
    .address-result {
        padding: 0.5rem;
        border-radius: 5px;
        background: #f0f2f6;
        margin: 0.2rem 0;
        cursor: pointer;
    }
    .address-result:hover {
        background: #e0e2e6;
    }
    
    /* Carte miniature */
    .mini-map {
        border-radius: 10px;
        overflow: hidden;
        border: 2px solid #ddd;
    }
</style>
""", unsafe_allow_html=True)

st.title("🧪 Proto - CRM Clients avec API Adresse")
st.caption("🗺️ Test autocomplétion adresse (data.gouv.fr) - Page de test")
st.markdown("---")

# ==========================================
# ⭐ FONCTIONS API ADRESSE (data.gouv.fr)
# ==========================================

def search_adresse(query, limit=5):
    """
    Recherche d'adresse via l'API Adresse du gouvernement français
    Retourne une liste de suggestions avec coordonnées GPS
    """
    if not query or len(query) < 3:
        return []
    
    try:
        response = requests.get(
            "https://api-adresse.data.gouv.fr/search/",
            params={
                "q": query,
                "limit": limit,
                "autocomplete": 1
            },
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
                    'housenumber': props.get('housenumber', ''),
                    'street': props.get('street', ''),
                    'postcode': props.get('postcode', ''),
                    'city': props.get('city', ''),
                    'context': props.get('context', ''),  # Ex: "75, Paris, Île-de-France"
                    'departement': props.get('postcode', '')[:2] if props.get('postcode') else '',
                    'longitude': coords[0] if coords else None,
                    'latitude': coords[1] if coords else None,
                    'score': props.get('score', 0)
                })
            
            return results
        return []
    except Exception as e:
        st.warning(f"⚠️ Erreur API Adresse : {e}")
        return []

def geocode_adresse(adresse_complete):
    """
    Géocode une adresse complète pour obtenir lat/lng
    """
    if not adresse_complete:
        return None, None
    
    try:
        response = requests.get(
            "https://api-adresse.data.gouv.fr/search/",
            params={"q": adresse_complete, "limit": 1},
            timeout=5
        )
        
        if response.status_code == 200:
            data = response.json()
            if data.get('features'):
                coords = data['features'][0]['geometry']['coordinates']
                return coords[1], coords[0]  # lat, lng
        return None, None
    except:
        return None, None

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
# FONCTIONS DB
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
        cursor.execute("""
            SELECT DISTINCT centrale_achat 
            FROM crm_magasins 
            WHERE is_active = TRUE AND centrale_achat IS NOT NULL AND centrale_achat != ''
            ORDER BY centrale_achat
        """)
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
        cursor.execute("""
            SELECT DISTINCT type_magasin 
            FROM crm_magasins 
            WHERE is_active = TRUE AND type_magasin IS NOT NULL AND type_magasin != ''
            ORDER BY type_magasin
        """)
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
        cursor.execute("""
            SELECT DISTINCT type_reseau 
            FROM crm_magasins 
            WHERE is_active = TRUE AND type_reseau IS NOT NULL AND type_reseau != ''
            ORDER BY type_reseau
        """)
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        return [r['type_reseau'] for r in rows]
    except:
        return []

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
        
        if rows:
            return pd.DataFrame(rows)
        return pd.DataFrame()
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
        
        # ⭐ Inclure latitude et longitude
        cursor.execute("""
            INSERT INTO crm_magasins (
                enseigne, ville, departement, adresse, code_postal,
                commercial_id, centrale_achat, type_magasin, type_reseau,
                surface_m2, potentiel, statut, presence_produit,
                points_amelioration, commentaires, notes, 
                latitude, longitude,
                created_by
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (
            data['enseigne'], data['ville'], data.get('departement'),
            data.get('adresse'), data.get('code_postal'), commercial_id,
            data.get('centrale_achat'), data.get('type_magasin'), data.get('type_reseau'),
            data.get('surface_m2'), data.get('potentiel'), data.get('statut', 'PROSPECT'),
            data.get('presence_produit'), data.get('points_amelioration'),
            data.get('commentaires'), data.get('notes'),
            data.get('latitude'), data.get('longitude'),
            data.get('created_by')
        ))
        
        new_id = cursor.fetchone()['id']
        conn.commit()
        cursor.close()
        conn.close()
        
        return True, f"✅ Client créé (ID: {new_id})"
    except Exception as e:
        return False, f"❌ Erreur : {str(e)}"

def update_magasin(magasin_id, data):
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        magasin_id = int(magasin_id)
        commercial_id = int(data['commercial_id']) if data.get('commercial_id') else None
        
        # ⭐ Inclure latitude et longitude
        cursor.execute("""
            UPDATE crm_magasins SET
                enseigne = %s, ville = %s, departement = %s, adresse = %s,
                code_postal = %s, commercial_id = %s, centrale_achat = %s,
                type_magasin = %s, type_reseau = %s, surface_m2 = %s,
                potentiel = %s, statut = %s, presence_produit = %s,
                points_amelioration = %s, commentaires = %s, notes = %s,
                latitude = %s, longitude = %s,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
        """, (
            data['enseigne'], data['ville'], data.get('departement'),
            data.get('adresse'), data.get('code_postal'), commercial_id,
            data.get('centrale_achat'), data.get('type_magasin'), data.get('type_reseau'),
            data.get('surface_m2'), data.get('potentiel'), data.get('statut'),
            data.get('presence_produit'), data.get('points_amelioration'),
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
# ⭐ COMPOSANT RECHERCHE ADRESSE
# ==========================================

def adresse_autocomplete(prefix_key, initial_values=None):
    """
    Composant de recherche d'adresse avec autocomplétion
    Retourne un dict avec adresse, code_postal, ville, departement, lat, lng
    """
    
    if initial_values is None:
        initial_values = {}
    
    st.markdown("#### 🗺️ Adresse (recherche automatique)")
    
    # Champ de recherche
    search_query = st.text_input(
        "🔍 Rechercher une adresse",
        placeholder="Tapez une adresse (ex: 12 rue de la Paix Paris)...",
        key=f"{prefix_key}_search"
    )
    
    # Stocker les résultats en session
    results_key = f"{prefix_key}_results"
    selected_key = f"{prefix_key}_selected"
    
    # Recherche si query >= 3 caractères
    if search_query and len(search_query) >= 3:
        results = search_adresse(search_query)
        st.session_state[results_key] = results
        
        if results:
            # Afficher les suggestions
            options = [""] + [r['label'] for r in results]
            selected_label = st.selectbox(
                "📍 Sélectionner une adresse",
                options,
                key=f"{prefix_key}_select"
            )
            
            # Si une adresse est sélectionnée
            if selected_label:
                selected = next((r for r in results if r['label'] == selected_label), None)
                if selected:
                    st.session_state[selected_key] = selected
                    st.success(f"✅ Adresse sélectionnée : **{selected['label']}**")
                    
                    # Afficher les détails
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.caption(f"📮 Code postal : **{selected['postcode']}**")
                    with col2:
                        st.caption(f"🏙️ Ville : **{selected['city']}**")
                    with col3:
                        st.caption(f"📍 Dept : **{selected['departement']}**")
                    
                    # Mini-carte si coordonnées disponibles
                    if selected['latitude'] and selected['longitude']:
                        st.caption(f"🌐 GPS : {selected['latitude']:.6f}, {selected['longitude']:.6f}")
                        
                        # Carte
                        map_data = pd.DataFrame({
                            'lat': [selected['latitude']],
                            'lon': [selected['longitude']]
                        })
                        st.map(map_data, zoom=14)
        else:
            st.info("Aucune adresse trouvée. Essayez une autre recherche.")
    
    # Récupérer l'adresse sélectionnée ou les valeurs initiales
    selected = st.session_state.get(selected_key, {})
    
    st.markdown("---")
    st.markdown("#### ✏️ Détails de l'adresse")
    
    col1, col2 = st.columns(2)
    
    with col1:
        adresse = st.text_input(
            "Adresse",
            value=selected.get('name', '') or safe_str(initial_values.get('adresse')),
            key=f"{prefix_key}_adresse"
        )
        
        code_postal = st.text_input(
            "Code postal",
            value=selected.get('postcode', '') or safe_str(initial_values.get('code_postal')),
            key=f"{prefix_key}_cp"
        )
        
        ville = st.text_input(
            "Ville *",
            value=selected.get('city', '') or safe_str(initial_values.get('ville')),
            key=f"{prefix_key}_ville"
        )
    
    with col2:
        departement = st.text_input(
            "Département",
            value=selected.get('departement', '') or safe_str(initial_values.get('departement')),
            key=f"{prefix_key}_dept"
        )
        
        latitude = st.number_input(
            "Latitude",
            value=selected.get('latitude') or safe_float(initial_values.get('latitude'), 0.0),
            format="%.6f",
            key=f"{prefix_key}_lat"
        )
        
        longitude = st.number_input(
            "Longitude",
            value=selected.get('longitude') or safe_float(initial_values.get('longitude'), 0.0),
            format="%.6f",
            key=f"{prefix_key}_lng"
        )
    
    return {
        'adresse': adresse,
        'code_postal': code_postal,
        'ville': ville,
        'departement': departement,
        'latitude': latitude if latitude != 0 else None,
        'longitude': longitude if longitude != 0 else None
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
        nouvelle_valeur = st.text_input(f"Nouvelle valeur pour {label}", key=f"{key_prefix}_new")
        return nouvelle_valeur if nouvelle_valeur else None
    elif selected == "":
        return None
    else:
        return selected

# ==========================================
# INTERFACE
# ==========================================

tab1, tab2, tab3 = st.tabs(["📋 Liste des clients", "➕ Nouveau client", "🗺️ Carte clients"])

# ==========================================
# TAB 1 : LISTE
# ==========================================

with tab1:
    # Filtres
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
        f_statut = st.selectbox("Statut", ['Tous', 'ACTIF', 'PROSPECT', 'INACTIF', 'EN_PAUSE', 'PERDU'], key="f_stat")
    
    filtres = {
        'enseigne': f_enseigne,
        'departement': f_dept,
        'commercial_id': f_commercial[0],
        'statut': f_statut
    }
    
    st.markdown("---")
    
    # Tableau
    df = get_magasins(filtres)
    
    if not df.empty:
        st.info(f"📊 **{len(df)} client(s)** - Cliquez sur une ligne pour voir les détails")
        
        df_display = df[['id', 'enseigne', 'ville', 'departement', 'statut', 'commercial']].copy()
        df_display.columns = ['ID', 'Enseigne', 'Ville', 'Dept', 'Statut', 'Commercial']
        df_display['Commercial'] = df_display['Commercial'].fillna('Non assigné')
        
        column_config = {
            "ID": st.column_config.NumberColumn("ID", width="small"),
            "Enseigne": st.column_config.TextColumn("Enseigne", width="medium"),
            "Ville": st.column_config.TextColumn("Ville", width="medium"),
            "Dept": st.column_config.TextColumn("Dept", width="small"),
            "Statut": st.column_config.TextColumn("Statut", width="small"),
            "Commercial": st.column_config.TextColumn("Commercial", width="medium")
        }
        
        event = st.dataframe(
            df_display,
            column_config=column_config,
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
                
                # Détails avec carte
                col_info, col_map = st.columns([1, 1])
                
                with col_info:
                    st.markdown("##### 📝 Informations")
                    st.markdown(f"**Adresse** : {safe_str(mag.get('adresse'), 'N/A')}")
                    st.markdown(f"**Code postal** : {safe_str(mag.get('code_postal'), 'N/A')}")
                    st.markdown(f"**Ville** : {mag['ville']}")
                    st.markdown(f"**Département** : {safe_str(mag.get('departement'), 'N/A')}")
                    
                    statut = mag.get('statut', 'N/A')
                    statut_icon = "🟢" if statut == 'ACTIF' else ("🔵" if statut == 'PROSPECT' else "🔴")
                    st.markdown(f"**Statut** : {statut_icon} {statut}")
                    st.markdown(f"**Commercial** : {safe_str(mag.get('commercial'), 'Non assigné')}")
                    
                    if mag.get('latitude') and mag.get('longitude'):
                        st.markdown(f"**GPS** : {mag['latitude']:.6f}, {mag['longitude']:.6f}")
                
                with col_map:
                    # Afficher carte si coordonnées disponibles
                    if mag.get('latitude') and mag.get('longitude'):
                        st.markdown("##### 🗺️ Localisation")
                        map_data = pd.DataFrame({
                            'lat': [float(mag['latitude'])],
                            'lon': [float(mag['longitude'])]
                        })
                        st.map(map_data, zoom=13)
                    else:
                        st.info("📍 Coordonnées GPS non disponibles")
                        
                        # Bouton pour géocoder
                        if st.button("🔍 Rechercher coordonnées GPS"):
                            adresse_complete = f"{safe_str(mag.get('adresse'))} {safe_str(mag.get('code_postal'))} {mag['ville']}"
                            lat, lng = geocode_adresse(adresse_complete)
                            
                            if lat and lng:
                                # Mettre à jour en base
                                update_data = {
                                    'enseigne': mag['enseigne'],
                                    'ville': mag['ville'],
                                    'departement': mag.get('departement'),
                                    'adresse': mag.get('adresse'),
                                    'code_postal': mag.get('code_postal'),
                                    'commercial_id': mag.get('commercial_id'),
                                    'centrale_achat': mag.get('centrale_achat'),
                                    'type_magasin': mag.get('type_magasin'),
                                    'type_reseau': mag.get('type_reseau'),
                                    'surface_m2': mag.get('surface_m2'),
                                    'potentiel': mag.get('potentiel'),
                                    'statut': mag.get('statut'),
                                    'presence_produit': mag.get('presence_produit'),
                                    'points_amelioration': mag.get('points_amelioration'),
                                    'notes': mag.get('notes'),
                                    'latitude': lat,
                                    'longitude': lng
                                }
                                success, msg = update_magasin(selected_id, update_data)
                                if success:
                                    st.success(f"✅ GPS trouvé : {lat:.6f}, {lng:.6f}")
                                    st.rerun()
                            else:
                                st.warning("⚠️ Impossible de trouver les coordonnées")
        else:
            st.info("👆 Sélectionnez un client dans le tableau pour voir les détails")
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
            # ⭐ Composant adresse avec autocomplétion
            adresse_data = adresse_autocomplete("new")
        
        new_presence = st.text_input("Présence produit", key="new_pres")
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
                    'presence_produit': new_presence or None,
                    'notes': new_notes or None,
                    'created_by': st.session_state.get('username', 'system')
                }
                success, msg = create_magasin(data)
                if success:
                    st.success(msg)
                    st.balloons()
                else:
                    st.error(msg)

# ==========================================
# TAB 3 : CARTE TOUS LES CLIENTS
# ==========================================

with tab3:
    st.subheader("🗺️ Carte de tous les clients")
    
    # Charger tous les clients avec coordonnées
    df_all = get_magasins()
    
    if not df_all.empty:
        # Filtrer ceux qui ont des coordonnées
        df_with_coords = df_all[
            df_all['latitude'].notna() & 
            df_all['longitude'].notna()
        ].copy()
        
        col1, col2 = st.columns([1, 3])
        
        with col1:
            st.metric("📍 Clients géolocalisés", len(df_with_coords))
            st.metric("❓ Sans coordonnées", len(df_all) - len(df_with_coords))
            
            if len(df_all) - len(df_with_coords) > 0:
                st.warning(f"⚠️ {len(df_all) - len(df_with_coords)} clients sans GPS")
                
                if st.button("🔄 Géocoder tous les clients"):
                    progress = st.progress(0)
                    updated = 0
                    
                    df_without = df_all[df_all['latitude'].isna() | df_all['longitude'].isna()]
                    
                    for i, (_, row) in enumerate(df_without.iterrows()):
                        adresse_complete = f"{safe_str(row.get('adresse'))} {safe_str(row.get('code_postal'))} {row['ville']}"
                        lat, lng = geocode_adresse(adresse_complete)
                        
                        if lat and lng:
                            # Mettre à jour
                            conn = get_connection()
                            cursor = conn.cursor()
                            cursor.execute(
                                "UPDATE crm_magasins SET latitude = %s, longitude = %s WHERE id = %s",
                                (lat, lng, int(row['id']))
                            )
                            conn.commit()
                            cursor.close()
                            conn.close()
                            updated += 1
                        
                        progress.progress((i + 1) / len(df_without))
                    
                    st.success(f"✅ {updated} clients géocodés")
                    st.rerun()
        
        with col2:
            if not df_with_coords.empty:
                # Préparer données pour la carte
                map_data = pd.DataFrame({
                    'lat': df_with_coords['latitude'].astype(float),
                    'lon': df_with_coords['longitude'].astype(float)
                })
                
                st.map(map_data, zoom=5)
            else:
                st.info("📍 Aucun client avec coordonnées GPS")
    else:
        st.warning("Aucun client trouvé")

show_footer()
