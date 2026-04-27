# pages/50_CRM_Prod_Producteurs.py
# CRM Producteurs - V1 #1bis (édition adresse + géocodage)
# Liée à ref_producteurs (CRUD coordonnées + services + certifs) + crm_prod_depots
# Pattern conforme POMI_REFERENCE_TECHNIQUE.md

import streamlit as st
import pandas as pd
from datetime import date

import folium
from streamlit_folium import st_folium
from streamlit_geolocation import streamlit_geolocation

from database import get_connection
from components import show_footer
from auth import require_access, can_edit, can_delete
from utils.geocoding import search_adresse, geocode_adresse, reverse_geocode

# ============================================================
# CONFIGURATION PAGE
# ============================================================
st.set_page_config(
    page_title="CRM Producteurs - Culture Pom",
    page_icon="🌾",
    layout="wide"
)

st.markdown("""
<style>
.block-container {padding-top:2rem!important;padding-bottom:0.5rem!important;
    padding-left:2rem!important;padding-right:2rem!important;}
h1,h2,h3,h4{margin-top:0.3rem!important;margin-bottom:0.3rem!important;}
[data-testid="stMetricValue"]{font-size:1.4rem!important;}
hr{margin-top:0.5rem!important;margin-bottom:0.5rem!important;}
.fiche-box {background:#f7faf0;border-left:4px solid #AFCA0A;
    border-radius:6px;padding:12px 16px;margin:8px 0;}
.depot-box {background:#fffbe6;border-left:4px solid #FFEC00;
    border-radius:6px;padding:10px 14px;margin:6px 0;}
.certif-ok {background:#d4edda;color:#155724;padding:2px 8px;
    border-radius:12px;font-size:0.85em;font-weight:600;}
.certif-ko {background:#f8d7da;color:#721c24;padding:2px 8px;
    border-radius:12px;font-size:0.85em;font-weight:600;}
.geo-info {background:#e8f4f8;border:1px solid #bee5eb;border-radius:6px;
    padding:8px 12px;margin:6px 0;font-size:0.88em;}
</style>
""", unsafe_allow_html=True)

# ============================================================
# CONTRÔLE ACCÈS
# ============================================================
require_access("CRM_PRODUCTEURS")

CAN_EDIT = can_edit("CRM_PRODUCTEURS")
CAN_DELETE = can_delete("CRM_PRODUCTEURS")

st.title("🌾 CRM Producteurs — Fiches enrichies")
st.markdown("*Source de vérité : ref_producteurs — édition coordonnées + services + certifs + dépôts*")
st.markdown("---")


# ============================================================
# FONCTIONS DB — PRODUCTEURS
# ============================================================

def get_producteurs(filtres=None):
    """Liste producteurs + nb dépôts."""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        query = """
            SELECT
                p.id, p.code_producteur, p.nom,
                p.adresse, p.code_postal, p.ville, p.departement,
                p.latitude, p.longitude,
                p.telephone, p.email, p.statut, p.acheteur_referent,
                p.global_gap, p.certif_global_gap_numero, p.certif_global_gap_validite,
                p.has_big_bag, p.has_lavage, p.has_stockage, p.notes,
                COALESCE(d.nb_depots, 0) AS nb_depots
            FROM ref_producteurs p
            LEFT JOIN (
                SELECT producteur_id, COUNT(*) AS nb_depots
                FROM crm_prod_depots WHERE is_active = TRUE
                GROUP BY producteur_id
            ) d ON p.id = d.producteur_id
            WHERE p.is_active = TRUE
        """
        params = []
        if filtres:
            if filtres.get('search'):
                query += " AND (LOWER(p.nom) LIKE %s OR LOWER(p.code_producteur) LIKE %s OR LOWER(COALESCE(p.ville,'')) LIKE %s)"
                s = f"%{filtres['search'].lower()}%"
                params.extend([s, s, s])
            if filtres.get('departement') and filtres['departement'] != 'Tous':
                query += " AND p.departement = %s"
                params.append(filtres['departement'])
            if filtres.get('global_gap_only'):
                query += " AND p.global_gap = TRUE"
            if filtres.get('service_filter') and filtres['service_filter'] != 'Tous':
                if filtres['service_filter'] == 'Big bag':
                    query += " AND p.has_big_bag = TRUE"
                elif filtres['service_filter'] == 'Lavage':
                    query += " AND p.has_lavage = TRUE"
                elif filtres['service_filter'] == 'Stockage':
                    query += " AND p.has_stockage = TRUE"
        query += " ORDER BY p.nom"
        cursor.execute(query, params)
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        return pd.DataFrame(rows) if rows else pd.DataFrame()
    except Exception as e:
        st.error(f"❌ Erreur chargement producteurs : {e}")
        return pd.DataFrame()


def get_departements():
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT DISTINCT departement FROM ref_producteurs
            WHERE is_active = TRUE AND departement IS NOT NULL AND departement != ''
            ORDER BY departement
        """)
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        return [r['departement'] for r in rows]
    except Exception:
        return []


def get_producteur_by_id(producteur_id):
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM ref_producteurs WHERE id = %s", (int(producteur_id),))
        row = cursor.fetchone()
        cursor.close()
        conn.close()
        return dict(row) if row else None
    except Exception as e:
        st.error(f"❌ Erreur : {e}")
        return None


def update_producteur_enrichi(producteur_id, data):
    """Update champs services + certifs + acheteur + notes (PAS l'adresse)."""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE ref_producteurs SET
                has_big_bag = %s, has_lavage = %s, has_stockage = %s,
                global_gap = %s, certif_global_gap_numero = %s,
                certif_global_gap_validite = %s,
                acheteur_referent = %s, notes = %s,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
        """, (
            bool(data.get('has_big_bag', False)),
            bool(data.get('has_lavage', False)),
            bool(data.get('has_stockage', False)),
            bool(data.get('global_gap', False)),
            data.get('certif_global_gap_numero') or None,
            data.get('certif_global_gap_validite'),
            data.get('acheteur_referent') or None,
            data.get('notes') or None,
            int(producteur_id)
        ))
        conn.commit()
        cursor.close()
        conn.close()
        return True, "✅ Producteur mis à jour"
    except Exception as e:
        if 'conn' in locals():
            conn.rollback()
        return False, f"❌ Erreur : {e}"


def update_producteur_adresse(producteur_id, data):
    """Update SEULEMENT les champs d'adresse (siège) du producteur.
    Modifie ref_producteurs → visible aussi dans 01_Sources."""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE ref_producteurs SET
                adresse = %s, code_postal = %s, ville = %s,
                departement = %s, latitude = %s, longitude = %s,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
        """, (
            data.get('adresse') or None,
            data.get('code_postal') or None,
            data.get('ville') or None,
            data.get('departement') or None,
            float(data['latitude']) if data.get('latitude') is not None else None,
            float(data['longitude']) if data.get('longitude') is not None else None,
            int(producteur_id)
        ))
        conn.commit()
        cursor.close()
        conn.close()
        return True, "✅ Adresse siège mise à jour"
    except Exception as e:
        if 'conn' in locals():
            conn.rollback()
        return False, f"❌ Erreur : {e}"


def update_producteur_identite(producteur_id, data):
    """Update champs identité (nom, SIRET, contacts, statut, type_contrat).
    Modifie ref_producteurs → visible aussi dans 01_Sources pour les champs
    déjà éditables là-bas (nom, telephone, email, statut, nom_contact)."""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE ref_producteurs SET
                nom = %s,
                siret = %s,
                forme_juridique = %s,
                telephone = %s,
                email = %s,
                prenom_contact = %s,
                nom_contact = %s,
                statut = %s,
                type_contrat = %s,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
        """, (
            data['nom'].strip() if data.get('nom') else None,
            (data.get('siret') or '').strip() or None,
            (data.get('forme_juridique') or '').strip() or None,
            (data.get('telephone') or '').strip() or None,
            (data.get('email') or '').strip() or None,
            (data.get('prenom_contact') or '').strip() or None,
            (data.get('nom_contact') or '').strip() or None,
            (data.get('statut') or '').strip() or None,
            (data.get('type_contrat') or '').strip() or None,
            int(producteur_id)
        ))
        conn.commit()
        cursor.close()
        conn.close()
        return True, "✅ Identité mise à jour"
    except Exception as e:
        if 'conn' in locals():
            conn.rollback()
        return False, f"❌ Erreur : {e}"


def get_statuts_producteur_distincts():
    """Liste des valeurs distinctes de statut déjà présentes en base."""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT DISTINCT statut FROM ref_producteurs
            WHERE statut IS NOT NULL AND TRIM(statut) <> ''
            ORDER BY statut
        """)
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        return [r['statut'] for r in rows]
    except Exception:
        return []


def get_types_contrat_distincts():
    """Liste des valeurs distinctes de type_contrat déjà présentes en base."""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT DISTINCT type_contrat FROM ref_producteurs
            WHERE type_contrat IS NOT NULL AND TRIM(type_contrat) <> ''
            ORDER BY type_contrat
        """)
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        return [r['type_contrat'] for r in rows]
    except Exception:
        return []


# ============================================================
# FONCTIONS DB — DÉPÔTS
# ============================================================

def get_depots(producteur_id):
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, libelle, adresse, code_postal, ville, departement,
                   capacite_tonnes, latitude, longitude, notes
            FROM crm_prod_depots
            WHERE producteur_id = %s AND is_active = TRUE
            ORDER BY libelle
        """, (int(producteur_id),))
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        return rows if rows else []
    except Exception as e:
        st.error(f"❌ Erreur dépôts : {e}")
        return []


def create_depot(producteur_id, data):
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO crm_prod_depots (
                producteur_id, libelle, adresse, code_postal, ville, departement,
                capacite_tonnes, latitude, longitude, notes, created_by
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (
            int(producteur_id),
            data['libelle'],
            data.get('adresse') or None,
            data.get('code_postal') or None,
            data.get('ville') or None,
            data.get('departement') or None,
            float(data['capacite_tonnes']) if data.get('capacite_tonnes') else None,
            float(data['latitude']) if data.get('latitude') is not None else None,
            float(data['longitude']) if data.get('longitude') is not None else None,
            data.get('notes') or None,
            st.session_state.get('username', 'system')
        ))
        new_id = cursor.fetchone()['id']
        conn.commit()
        cursor.close()
        conn.close()
        return True, f"✅ Dépôt créé (id={new_id})"
    except Exception as e:
        if 'conn' in locals():
            conn.rollback()
        return False, f"❌ Erreur : {e}"


def update_depot(depot_id, data):
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE crm_prod_depots SET
                libelle = %s, adresse = %s, code_postal = %s,
                ville = %s, departement = %s,
                capacite_tonnes = %s, latitude = %s, longitude = %s,
                notes = %s, updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
        """, (
            data['libelle'],
            data.get('adresse') or None,
            data.get('code_postal') or None,
            data.get('ville') or None,
            data.get('departement') or None,
            float(data['capacite_tonnes']) if data.get('capacite_tonnes') else None,
            float(data['latitude']) if data.get('latitude') is not None else None,
            float(data['longitude']) if data.get('longitude') is not None else None,
            data.get('notes') or None,
            int(depot_id)
        ))
        conn.commit()
        cursor.close()
        conn.close()
        return True, "✅ Dépôt mis à jour"
    except Exception as e:
        if 'conn' in locals():
            conn.rollback()
        return False, f"❌ Erreur : {e}"


def delete_depot(depot_id):
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE crm_prod_depots SET is_active = FALSE,
                                       updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
        """, (int(depot_id),))
        conn.commit()
        cursor.close()
        conn.close()
        return True, "✅ Dépôt supprimé"
    except Exception as e:
        if 'conn' in locals():
            conn.rollback()
        return False, f"❌ Erreur : {e}"


# ============================================================
# KPIs
# ============================================================

def get_kpis():
    try:
        conn = get_connection()
        cursor = conn.cursor()
        kpis = {}
        cursor.execute("SELECT COUNT(*) AS n FROM ref_producteurs WHERE is_active = TRUE")
        kpis['total'] = cursor.fetchone()['n']
        cursor.execute("SELECT COUNT(*) AS n FROM ref_producteurs WHERE is_active = TRUE AND global_gap = TRUE")
        kpis['global_gap'] = cursor.fetchone()['n']
        cursor.execute("""
            SELECT COUNT(*) AS n FROM ref_producteurs WHERE is_active = TRUE
              AND (has_big_bag = TRUE OR has_lavage = TRUE OR has_stockage = TRUE)
        """)
        kpis['avec_services'] = cursor.fetchone()['n']
        cursor.execute("SELECT COUNT(*) AS n FROM crm_prod_depots WHERE is_active = TRUE")
        kpis['nb_depots'] = cursor.fetchone()['n']
        cursor.execute("""
            SELECT COUNT(*) AS n FROM ref_producteurs WHERE is_active = TRUE AND global_gap = TRUE
              AND certif_global_gap_validite IS NOT NULL
              AND certif_global_gap_validite <= CURRENT_DATE + INTERVAL '60 days'
        """)
        kpis['certifs_expirent'] = cursor.fetchone()['n']
        cursor.close()
        conn.close()
        return kpis
    except Exception as e:
        st.error(f"❌ Erreur KPIs : {e}")
        return {}


# ============================================================
# COMPOSANT ÉDITION ADRESSE — réutilisable siège + dépôts
# ============================================================

def adresse_editor_component(prefix, current_data, on_save_label="💾 Enregistrer adresse"):
    """Composant d'édition d'adresse avec :
       - autocomplete (search BAN)
       - bouton géoloc utilisateur (avec reverse geocoding)
       - saisie manuelle
       - mini-carte interactive avec pin déplaçable

    Args:
        prefix: identifiant unique pour les session_state keys (ex: "siege_42", "depot_12")
        current_data: dict avec les valeurs initiales (adresse, code_postal, ville,
                      departement, latitude, longitude)
        on_save_label: libellé du bouton de sauvegarde

    Returns:
        dict avec les valeurs courantes des champs (toujours retourné, même sans clic)
        + clé '_save_clicked' = True si l'utilisateur a cliqué sur Enregistrer ce tour-ci.
    """
    # ----- Initialisation session_state (seulement la 1re fois) -----
    keys = {
        'adresse': f"adr_{prefix}",
        'cp': f"cp_{prefix}",
        'ville': f"vi_{prefix}",
        'dept': f"dp_{prefix}",
        'lat': f"la_{prefix}",
        'lng': f"lo_{prefix}",
        'init_done': f"init_{prefix}",
    }
    if not st.session_state.get(keys['init_done']):
        st.session_state[keys['adresse']] = current_data.get('adresse') or ''
        st.session_state[keys['cp']] = current_data.get('code_postal') or ''
        st.session_state[keys['ville']] = current_data.get('ville') or ''
        st.session_state[keys['dept']] = current_data.get('departement') or ''
        st.session_state[keys['lat']] = float(current_data.get('latitude')) if current_data.get('latitude') is not None else 0.0
        st.session_state[keys['lng']] = float(current_data.get('longitude')) if current_data.get('longitude') is not None else 0.0
        st.session_state[keys['init_done']] = True

    # ----- Recherche adresse + géoloc -----
    col_search, col_geoloc = st.columns([3, 1])

    with col_search:
        query = st.text_input(
            "🔍 Rechercher une adresse",
            key=f"q_{prefix}",
            placeholder="Ex: 10 rue de la Paix Épernay",
            disabled=not CAN_EDIT,
        )
        if query and len(query) >= 3:
            results = search_adresse(query, limit=5)
            if results:
                options = ["-- Sélectionner --"] + [r['label'] for r in results]

                def _on_select():
                    chosen = st.session_state.get(f"sel_{prefix}")
                    if chosen and chosen != "-- Sélectionner --":
                        for r in results:
                            if r['label'] == chosen:
                                st.session_state[keys['adresse']] = r.get('name', '')
                                st.session_state[keys['cp']] = r.get('postcode', '')
                                st.session_state[keys['ville']] = r.get('city', '')
                                st.session_state[keys['dept']] = r.get('departement', '')
                                if r.get('latitude') is not None:
                                    st.session_state[keys['lat']] = float(r['latitude'])
                                if r.get('longitude') is not None:
                                    st.session_state[keys['lng']] = float(r['longitude'])
                                break

                st.selectbox("Résultats", options, key=f"sel_{prefix}",
                             on_change=_on_select, disabled=not CAN_EDIT)
            elif len(query) >= 3:
                st.caption("Aucun résultat — affine ta recherche")

    with col_geoloc:
        st.markdown("**📍 Ma position**")
        st.caption("Clic = utilise ma position GPS")
        if CAN_EDIT:
            loc = streamlit_geolocation()
            # streamlit_geolocation renvoie un dict avec latitude/longitude au top-level
            if loc and isinstance(loc, dict):
                lat_user = loc.get('latitude')
                lng_user = loc.get('longitude')
                if lat_user is not None and lng_user is not None:
                    # Bouton pour appliquer
                    if st.button("✅ Utiliser cette position",
                                 key=f"use_geo_{prefix}", type="secondary"):
                        # Reverse geocoding
                        rev = reverse_geocode(lat_user, lng_user)
                        st.session_state[keys['lat']] = float(lat_user)
                        st.session_state[keys['lng']] = float(lng_user)
                        if rev:
                            st.session_state[keys['adresse']] = rev.get('name', '') or st.session_state[keys['adresse']]
                            st.session_state[keys['cp']] = rev.get('postcode', '') or st.session_state[keys['cp']]
                            st.session_state[keys['ville']] = rev.get('city', '') or st.session_state[keys['ville']]
                            st.session_state[keys['dept']] = rev.get('departement', '') or st.session_state[keys['dept']]
                            st.success(f"📍 Position trouvée : {rev.get('label', '')}")
                        else:
                            st.warning("Position prise mais adresse non trouvée")
                        st.rerun()
                    else:
                        st.caption(f"GPS détecté : {float(lat_user):.5f}, {float(lng_user):.5f}")

    # ----- Champs adresse (édition manuelle toujours possible) -----
    f1, f2 = st.columns(2)
    with f1:
        st.text_input("Adresse", key=keys['adresse'], disabled=not CAN_EDIT)
        st.text_input("Code postal", key=keys['cp'], disabled=not CAN_EDIT)
        st.text_input("Ville", key=keys['ville'], disabled=not CAN_EDIT)
    with f2:
        st.text_input("Département", key=keys['dept'], disabled=not CAN_EDIT)
        st.number_input("Latitude", key=keys['lat'], format="%.6f", disabled=not CAN_EDIT)
        st.number_input("Longitude", key=keys['lng'], format="%.6f", disabled=not CAN_EDIT)

    # ----- Carte interactive avec pin déplaçable -----
    lat_val = float(st.session_state.get(keys['lat']) or 0.0)
    lng_val = float(st.session_state.get(keys['lng']) or 0.0)

    if lat_val != 0.0 and lng_val != 0.0:
        st.markdown("**🗺️ Carte (déplace le pin pour ajuster)**")
        m = folium.Map(location=[lat_val, lng_val], zoom_start=15, tiles='OpenStreetMap')
        folium.Marker(
            location=[lat_val, lng_val],
            popup=st.session_state.get(keys['adresse']) or 'Position',
            draggable=CAN_EDIT,
        ).add_to(m)

        map_data = st_folium(m, width=None, height=300, key=f"map_{prefix}",
                             returned_objects=["last_object_clicked", "all_drawings"])

        # Détection du déplacement du pin via last_object_clicked
        # NB : st_folium remonte les clicks, mais le drag end remonte aussi via center
        # On propose un bouton manuel pour ne pas trigger d'API à chaque rerun.
        st.caption("Si tu déplaces le pin, clique le bouton ci-dessous pour récupérer la nouvelle adresse.")
        if CAN_EDIT and st.button("🔄 Récupérer adresse depuis la carte",
                                  key=f"reverse_{prefix}", type="secondary"):
            # On utilise les coords courantes (l'utilisateur a peut-être édité lat/lng à la main)
            rev = reverse_geocode(lat_val, lng_val)
            if rev:
                st.session_state[keys['adresse']] = rev.get('name', '') or st.session_state[keys['adresse']]
                st.session_state[keys['cp']] = rev.get('postcode', '') or st.session_state[keys['cp']]
                st.session_state[keys['ville']] = rev.get('city', '') or st.session_state[keys['ville']]
                st.session_state[keys['dept']] = rev.get('departement', '') or st.session_state[keys['dept']]
                st.success(f"📍 {rev.get('label', '')}")
                st.rerun()
            else:
                st.warning("Aucune adresse trouvée à ces coordonnées")
    else:
        st.info("ℹ️ Pas de coordonnées GPS — fais une recherche, utilise ta position, ou saisis-les manuellement pour voir la carte.")

    # ----- Bouton Enregistrer -----
    save_clicked = False
    if CAN_EDIT:
        if st.button(on_save_label, key=f"save_{prefix}", type="primary"):
            save_clicked = True

    # ----- Retour valeurs courantes -----
    return {
        'adresse': st.session_state.get(keys['adresse']) or '',
        'code_postal': st.session_state.get(keys['cp']) or '',
        'ville': st.session_state.get(keys['ville']) or '',
        'departement': st.session_state.get(keys['dept']) or '',
        'latitude': float(st.session_state[keys['lat']]) if st.session_state.get(keys['lat']) else None,
        'longitude': float(st.session_state[keys['lng']]) if st.session_state.get(keys['lng']) else None,
        '_save_clicked': save_clicked,
    }


def reset_adresse_state(prefix):
    """Permet de forcer la ré-init du composant adresse pour ce prefix."""
    for suffix in ['adr_', 'cp_', 'vi_', 'dp_', 'la_', 'lo_', 'init_']:
        st.session_state.pop(f"{suffix}{prefix}", None)


# ============================================================
# FICHE PRODUCTEUR — affichage + édition
# ============================================================

def afficher_fiche_producteur(prod):
    """Fiche détail producteur : édition adresse siège + données CRM + dépôts."""
    st.markdown(f"### 👨‍🌾 {prod['nom']}")
    st.caption(f"Code : `{prod.get('code_producteur', '')}`  |  ID : {prod['id']}")

    # ============ Onglets fiche ============
    tab_id, tab_adr, tab_crm, tab_dep = st.tabs([
        "ℹ️ Identité", "📍 Adresse siège", "✏️ Données CRM", "📦 Dépôts"
    ])

    # ----- Identité (édition complète) -----
    with tab_id:
        if not CAN_EDIT:
            st.info("Lecture seule — droits insuffisants pour modifier.")
            st.markdown(f"""
            - **Nom** : {prod.get('nom') or '—'}
            - **SIRET** : {prod.get('siret') or '—'}
            - **Forme juridique** : {prod.get('forme_juridique') or '—'}
            - **Téléphone** : {prod.get('telephone') or '—'}
            - **Email** : {prod.get('email') or '—'}
            - **Contact** : {prod.get('prenom_contact') or ''} {prod.get('nom_contact') or '—'}
            - **Statut** : {prod.get('statut') or '—'}
            - **Type contrat** : {prod.get('type_contrat') or '—'}
            """)
        else:
            # Récupérer dropdowns dynamiques (valeurs existantes en base)
            statuts_existants = get_statuts_producteur_distincts()
            types_contrat_existants = get_types_contrat_distincts()

            i_col1, i_col2 = st.columns(2)

            with i_col1:
                st.markdown("**🏢 Entreprise**")
                e_nom = st.text_input(
                    "Nom / Raison sociale *",
                    value=prod.get('nom') or '',
                    key=f"id_nom_{prod['id']}"
                )
                e_siret = st.text_input(
                    "SIRET",
                    value=prod.get('siret') or '',
                    key=f"id_siret_{prod['id']}",
                    help="Format : 14 chiffres (non validé strictement)"
                )
                e_forme = st.text_input(
                    "Forme juridique",
                    value=prod.get('forme_juridique') or '',
                    key=f"id_forme_{prod['id']}",
                    placeholder="Ex: SARL, SAS, EARL, GAEC..."
                )

            with i_col2:
                st.markdown("**📞 Coordonnées**")
                e_tel = st.text_input(
                    "Téléphone",
                    value=prod.get('telephone') or '',
                    key=f"id_tel_{prod['id']}"
                )
                e_email = st.text_input(
                    "Email",
                    value=prod.get('email') or '',
                    key=f"id_email_{prod['id']}"
                )

            st.markdown("**👤 Contact référent**")
            c_col1, c_col2 = st.columns(2)
            with c_col1:
                e_prenom_c = st.text_input(
                    "Prénom contact",
                    value=prod.get('prenom_contact') or '',
                    key=f"id_prenom_c_{prod['id']}"
                )
            with c_col2:
                e_nom_c = st.text_input(
                    "Nom contact",
                    value=prod.get('nom_contact') or '',
                    key=f"id_nom_c_{prod['id']}"
                )

            st.markdown("**📋 Relation commerciale**")
            r_col1, r_col2 = st.columns(2)

            # Dropdown statut dynamique avec option "+ Saisir nouvelle valeur"
            with r_col1:
                statut_courant = prod.get('statut') or ''
                options_statut = ['(non défini)'] + statuts_existants
                if statut_courant and statut_courant not in options_statut:
                    options_statut.append(statut_courant)
                options_statut.append('+ Saisir nouvelle valeur')

                idx_statut = 0
                if statut_courant in options_statut:
                    idx_statut = options_statut.index(statut_courant)

                e_statut_choix = st.selectbox(
                    "Statut",
                    options_statut,
                    index=idx_statut,
                    key=f"id_statut_choix_{prod['id']}"
                )
                if e_statut_choix == '+ Saisir nouvelle valeur':
                    e_statut = st.text_input(
                        "Nouveau statut",
                        key=f"id_statut_new_{prod['id']}"
                    )
                elif e_statut_choix == '(non défini)':
                    e_statut = ''
                else:
                    e_statut = e_statut_choix

            # Dropdown type_contrat dynamique
            with r_col2:
                tc_courant = prod.get('type_contrat') or ''
                options_tc = ['(non défini)'] + types_contrat_existants
                if tc_courant and tc_courant not in options_tc:
                    options_tc.append(tc_courant)
                options_tc.append('+ Saisir nouvelle valeur')

                idx_tc = 0
                if tc_courant in options_tc:
                    idx_tc = options_tc.index(tc_courant)

                e_tc_choix = st.selectbox(
                    "Type contrat",
                    options_tc,
                    index=idx_tc,
                    key=f"id_tc_choix_{prod['id']}"
                )
                if e_tc_choix == '+ Saisir nouvelle valeur':
                    e_tc = st.text_input(
                        "Nouveau type contrat",
                        key=f"id_tc_new_{prod['id']}"
                    )
                elif e_tc_choix == '(non défini)':
                    e_tc = ''
                else:
                    e_tc = e_tc_choix

            st.markdown("---")

            if st.button("💾 Enregistrer identité", type="primary",
                         key=f"save_id_{prod['id']}"):
                if not e_nom or not e_nom.strip():
                    st.error("❌ Le nom est obligatoire")
                else:
                    ok, msg = update_producteur_identite(prod['id'], {
                        'nom': e_nom,
                        'siret': e_siret,
                        'forme_juridique': e_forme,
                        'telephone': e_tel,
                        'email': e_email,
                        'prenom_contact': e_prenom_c,
                        'nom_contact': e_nom_c,
                        'statut': e_statut,
                        'type_contrat': e_tc,
                    })
                    if ok:
                        st.success(msg)
                        st.rerun()
                    else:
                        st.error(msg)

    # ----- Adresse siège (édition complète) -----
    with tab_adr:
        st.markdown("Mets à jour l'**adresse du siège**. La modification sera répercutée dans `01_Sources` (même base).")
        st.markdown('<div class="geo-info">💡 Astuce : tape une adresse dans la recherche pour autocomplétion, '
                    'ou clique sur 📍 Ma position si tu es sur place. La carte permet d\'ajuster le pin.</div>',
                    unsafe_allow_html=True)

        prefix = f"siege_{prod['id']}"
        adr_data = adresse_editor_component(
            prefix=prefix,
            current_data={
                'adresse': prod.get('adresse'),
                'code_postal': prod.get('code_postal'),
                'ville': prod.get('ville'),
                'departement': prod.get('departement'),
                'latitude': prod.get('latitude'),
                'longitude': prod.get('longitude'),
            },
            on_save_label="💾 Enregistrer adresse siège"
        )

        if adr_data['_save_clicked']:
            ok, msg = update_producteur_adresse(prod['id'], adr_data)
            if ok:
                st.success(msg)
                reset_adresse_state(prefix)
                st.rerun()
            else:
                st.error(msg)

    # ----- Données CRM (services + certifs) -----
    with tab_crm:
        if not CAN_EDIT:
            st.info("Lecture seule — droits insuffisants pour modifier.")

        e1, e2 = st.columns(2)
        with e1:
            st.markdown("**🏭 Services proposés**")
            e_bb = st.checkbox("Mise en big bag", value=bool(prod.get('has_big_bag')),
                               disabled=not CAN_EDIT, key=f"bb_{prod['id']}")
            e_lv = st.checkbox("Lavage", value=bool(prod.get('has_lavage')),
                               disabled=not CAN_EDIT, key=f"lv_{prod['id']}")
            e_st = st.checkbox("Stockage", value=bool(prod.get('has_stockage')),
                               disabled=not CAN_EDIT, key=f"st_{prod['id']}")
            e_ach = st.text_input("Acheteur référent", value=prod.get('acheteur_referent') or '',
                                  disabled=not CAN_EDIT, key=f"ach_{prod['id']}")
        with e2:
            st.markdown("**📜 Certifications Global GAP**")
            e_gap = st.checkbox("Certifié Global GAP", value=bool(prod.get('global_gap')),
                                disabled=not CAN_EDIT, key=f"gap_{prod['id']}")
            e_gnum = st.text_input("N° certificat", value=prod.get('certif_global_gap_numero') or '',
                                   disabled=not CAN_EDIT or not e_gap, key=f"gnum_{prod['id']}")
            e_gval = st.date_input("Date validité", value=prod.get('certif_global_gap_validite'),
                                   disabled=not CAN_EDIT or not e_gap, key=f"gval_{prod['id']}")

            if e_gap and prod.get('certif_global_gap_validite'):
                jours = (prod['certif_global_gap_validite'] - date.today()).days
                if jours < 0:
                    st.markdown(f'<span class="certif-ko">⛔ Expirée ({-jours}j)</span>', unsafe_allow_html=True)
                elif jours < 60:
                    st.markdown(f'<span class="certif-ko">⚠️ Expire dans {jours}j</span>', unsafe_allow_html=True)
                else:
                    st.markdown(f'<span class="certif-ok">✅ Valide ({jours}j)</span>', unsafe_allow_html=True)

        e_notes = st.text_area("Notes", value=prod.get('notes') or '',
                               disabled=not CAN_EDIT, key=f"nt_{prod['id']}")

        if CAN_EDIT and st.button("💾 Enregistrer données CRM", type="primary",
                                  key=f"save_crm_{prod['id']}"):
            ok, msg = update_producteur_enrichi(prod['id'], {
                'has_big_bag': e_bb, 'has_lavage': e_lv, 'has_stockage': e_st,
                'global_gap': e_gap,
                'certif_global_gap_numero': e_gnum if e_gap else None,
                'certif_global_gap_validite': e_gval if e_gap else None,
                'acheteur_referent': e_ach, 'notes': e_notes,
            })
            if ok:
                st.success(msg)
                st.rerun()
            else:
                st.error(msg)

    # ----- Dépôts -----
    with tab_dep:
        depots = get_depots(prod['id'])

        if not depots:
            st.info("Aucun dépôt enregistré.")
        else:
            for dep in depots:
                with st.expander(f"📦 {dep['libelle']} — {dep.get('ville') or ''}"):
                    afficher_depot(prod['id'], dep)

        st.markdown("---")

        # Formulaire ajout dépôt
        if CAN_EDIT:
            if st.button("➕ Ajouter un dépôt", key=f"add_dep_btn_{prod['id']}"):
                st.session_state[f'show_new_dep_{prod["id"]}'] = True
                st.rerun()

            if st.session_state.get(f'show_new_dep_{prod["id"]}'):
                st.markdown("##### ➕ Nouveau dépôt")
                n_lib = st.text_input("Libellé *", key=f"new_lib_{prod['id']}")
                n_cap = st.number_input("Capacité (T)", value=0.0, min_value=0.0, step=10.0,
                                        key=f"new_cap_{prod['id']}")

                st.markdown("**Adresse du dépôt**")
                prefix_new = f"new_depot_{prod['id']}"
                new_adr = adresse_editor_component(
                    prefix=prefix_new,
                    current_data={},
                    on_save_label="(le bouton enregistre ci-dessous)"
                )

                n_notes = st.text_area("Notes", key=f"new_notes_dep_{prod['id']}")

                bcol1, bcol2 = st.columns(2)
                with bcol1:
                    if st.button("✅ Créer le dépôt", type="primary",
                                 key=f"new_save_dep_{prod['id']}"):
                        if not n_lib:
                            st.error("Libellé obligatoire")
                        else:
                            ok, msg = create_depot(prod['id'], {
                                'libelle': n_lib,
                                'adresse': new_adr['adresse'],
                                'code_postal': new_adr['code_postal'],
                                'ville': new_adr['ville'],
                                'departement': new_adr['departement'],
                                'latitude': new_adr['latitude'],
                                'longitude': new_adr['longitude'],
                                'capacite_tonnes': n_cap if n_cap > 0 else None,
                                'notes': n_notes,
                            })
                            if ok:
                                st.success(msg)
                                reset_adresse_state(prefix_new)
                                st.session_state.pop(f'show_new_dep_{prod["id"]}', None)
                                st.rerun()
                            else:
                                st.error(msg)
                with bcol2:
                    if st.button("❌ Annuler", key=f"new_cancel_dep_{prod['id']}"):
                        reset_adresse_state(prefix_new)
                        st.session_state.pop(f'show_new_dep_{prod["id"]}', None)
                        st.rerun()


def afficher_depot(producteur_id, dep):
    """Affiche un dépôt avec édition adresse intégrée."""
    edit_mode = st.session_state.get(f"edit_dep_{dep['id']}", False)

    if not edit_mode:
        # Lecture seule
        d1, d2 = st.columns(2)
        with d1:
            st.markdown(f"**Adresse** : {dep.get('adresse') or '—'}")
            st.markdown(f"**CP / Ville** : {dep.get('code_postal') or '—'} {dep.get('ville') or '—'}")
            st.markdown(f"**Département** : {dep.get('departement') or '—'}")
        with d2:
            cap = dep.get('capacite_tonnes')
            st.markdown(f"**Capacité** : {f'{cap} T' if cap else '—'}")
            lat = dep.get('latitude')
            lng = dep.get('longitude')
            if lat is not None and lng is not None:
                st.markdown(f"**GPS** : {float(lat):.5f}, {float(lng):.5f}")
            if dep.get('notes'):
                st.markdown(f"**Notes** : {dep['notes']}")

        # Mini-carte si GPS
        if dep.get('latitude') is not None and dep.get('longitude') is not None:
            m = folium.Map(location=[float(dep['latitude']), float(dep['longitude'])],
                           zoom_start=14, tiles='OpenStreetMap')
            folium.Marker(location=[float(dep['latitude']), float(dep['longitude'])],
                          popup=dep.get('libelle')).add_to(m)
            st_folium(m, width=None, height=250, key=f"map_dep_view_{dep['id']}",
                      returned_objects=[])

        # Boutons action
        if CAN_EDIT or CAN_DELETE:
            bcol1, bcol2 = st.columns(2)
            with bcol1:
                if CAN_EDIT and st.button("✏️ Modifier", key=f"btn_edit_dep_{dep['id']}"):
                    st.session_state[f"edit_dep_{dep['id']}"] = True
                    st.rerun()
            with bcol2:
                if CAN_DELETE and st.button("🗑️ Supprimer", key=f"btn_del_dep_{dep['id']}"):
                    ok, msg = delete_depot(dep['id'])
                    if ok:
                        st.success(msg)
                        st.rerun()
                    else:
                        st.error(msg)
    else:
        # Édition
        st.markdown("##### ✏️ Modifier le dépôt")

        ed_lib = st.text_input("Libellé *", value=dep.get('libelle', '') or '',
                               key=f"ed_lib_{dep['id']}")
        ed_cap = st.number_input("Capacité (T)",
                                 value=float(dep.get('capacite_tonnes') or 0.0),
                                 min_value=0.0, step=10.0, key=f"ed_cap_{dep['id']}")

        st.markdown("**Adresse du dépôt**")
        prefix = f"depot_{dep['id']}"
        adr_data = adresse_editor_component(
            prefix=prefix,
            current_data={
                'adresse': dep.get('adresse'),
                'code_postal': dep.get('code_postal'),
                'ville': dep.get('ville'),
                'departement': dep.get('departement'),
                'latitude': dep.get('latitude'),
                'longitude': dep.get('longitude'),
            },
            on_save_label="(bouton enregistre ci-dessous)"
        )

        ed_notes = st.text_area("Notes", value=dep.get('notes', '') or '',
                                key=f"ed_notes_dep_{dep['id']}")

        bs1, bs2 = st.columns(2)
        with bs1:
            if st.button("💾 Enregistrer", type="primary", key=f"save_dep_{dep['id']}"):
                if not ed_lib:
                    st.error("Libellé obligatoire")
                else:
                    ok, msg = update_depot(dep['id'], {
                        'libelle': ed_lib,
                        'adresse': adr_data['adresse'],
                        'code_postal': adr_data['code_postal'],
                        'ville': adr_data['ville'],
                        'departement': adr_data['departement'],
                        'latitude': adr_data['latitude'],
                        'longitude': adr_data['longitude'],
                        'capacite_tonnes': ed_cap if ed_cap > 0 else None,
                        'notes': ed_notes,
                    })
                    if ok:
                        st.success(msg)
                        reset_adresse_state(prefix)
                        st.session_state.pop(f"edit_dep_{dep['id']}", None)
                        st.rerun()
                    else:
                        st.error(msg)
        with bs2:
            if st.button("❌ Annuler", key=f"cancel_dep_{dep['id']}"):
                reset_adresse_state(prefix)
                st.session_state.pop(f"edit_dep_{dep['id']}", None)
                st.rerun()


# ============================================================
# AFFICHAGE KPIs
# ============================================================

kpis = get_kpis()
if kpis:
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("👨‍🌾 Producteurs", kpis.get('total', 0))
    c2.metric("✅ Global GAP", kpis.get('global_gap', 0))
    c3.metric("🏭 Avec services", kpis.get('avec_services', 0))
    c4.metric("📦 Dépôts", kpis.get('nb_depots', 0))
    if kpis.get('certifs_expirent', 0) > 0:
        c5.metric("⚠️ Certifs <60j", kpis['certifs_expirent'],
                  delta=f"-{kpis['certifs_expirent']}", delta_color="inverse")
    else:
        c5.metric("✅ Certifs OK", 0)

st.markdown("---")

# ============================================================
# ONGLETS PRINCIPAUX
# ============================================================

tab1, tab2 = st.tabs(["📋 Liste & Fiche", "📊 Vue tableau"])

# ----- TAB 1 -----
with tab1:
    st.subheader("📋 Producteurs")

    departements = get_departements()
    fcol1, fcol2, fcol3, fcol4 = st.columns([2, 1, 1, 1])
    with fcol1:
        f_search = st.text_input("🔍 Recherche (nom, code, ville)", key="prod_search")
    with fcol2:
        f_dept = st.selectbox("Département", ['Tous'] + departements, key="prod_dept")
    with fcol3:
        f_service = st.selectbox("Service", ['Tous', 'Big bag', 'Lavage', 'Stockage'], key="prod_service")
    with fcol4:
        f_gap = st.checkbox("Global GAP uniquement", key="prod_gap_only")

    df_prod = get_producteurs({
        'search': f_search,
        'departement': f_dept,
        'service_filter': f_service,
        'global_gap_only': f_gap,
    })

    st.markdown(f"**{len(df_prod)} producteur(s) trouvé(s)**")

    if df_prod.empty:
        st.info("Aucun producteur ne correspond aux filtres.")
    else:
        col_list, col_fiche = st.columns([1, 1])
        with col_list:
            display_df = df_prod[[
                'code_producteur', 'nom', 'ville', 'departement',
                'global_gap', 'has_big_bag', 'has_lavage', 'has_stockage', 'nb_depots'
            ]].copy()
            for c in ['global_gap', 'has_big_bag', 'has_lavage', 'has_stockage']:
                display_df[c] = display_df[c].apply(lambda x: '✅' if x else '')
            display_df.columns = ['Code', 'Nom', 'Ville', 'Dept',
                                  'GAP', 'BBag', 'Lav', 'Stock', 'Dépôts']
            event = st.dataframe(
                display_df.fillna(''),
                use_container_width=True, hide_index=True,
                on_select="rerun", selection_mode="single-row",
                key="prod_table"
            )
            if event.selection.rows:
                idx = event.selection.rows[0]
                st.session_state['prod_selected_id'] = int(df_prod.iloc[idx]['id'])

        with col_fiche:
            sel_id = st.session_state.get('prod_selected_id')
            if not sel_id:
                st.info("👈 Sélectionne un producteur dans le tableau pour voir sa fiche")
            else:
                prod = get_producteur_by_id(sel_id)
                if not prod:
                    st.error("Producteur introuvable")
                    st.session_state.pop('prod_selected_id', None)
                else:
                    afficher_fiche_producteur(prod)


# ----- TAB 2 -----
with tab2:
    st.subheader("📊 Vue tableau complète")
    df_all = get_producteurs(None)
    if df_all.empty:
        st.info("Aucun producteur en base.")
    else:
        export_df = df_all.copy()
        for col in ['global_gap', 'has_big_bag', 'has_lavage', 'has_stockage']:
            if col in export_df.columns:
                export_df[col] = export_df[col].apply(lambda x: 'OUI' if x else 'NON')
        st.dataframe(export_df, use_container_width=True, hide_index=True)
        csv = export_df.to_csv(index=False).encode('utf-8')
        st.download_button(
            "📥 Exporter CSV", data=csv,
            file_name=f"crm_producteurs_{date.today().isoformat()}.csv",
            mime="text/csv"
        )

show_footer()
