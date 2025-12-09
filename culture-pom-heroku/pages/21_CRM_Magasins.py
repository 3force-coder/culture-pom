import streamlit as st
import pandas as pd
from datetime import datetime
from database import get_connection
from components import show_footer
from auth import is_authenticated, require_access, can_edit, can_delete

st.set_page_config(page_title="CRM Magasins - Culture Pom", page_icon="🏪", layout="wide")

# Vérification authentification + permissions
if not is_authenticated():
    st.warning("⚠️ Veuillez vous connecter")
    st.stop()

require_access("CRM")

st.markdown("""
<style>
    .block-container { padding-top: 1.5rem !important; padding-bottom: 0.5rem !important; }
    h1, h2, h3, h4 { margin-top: 0.3rem !important; margin-bottom: 0.3rem !important; }
    .magasin-card { background-color: #f8f9fa; padding: 1rem; border-radius: 8px; border-left: 4px solid #4CAF50; }
</style>
""", unsafe_allow_html=True)

st.title("🏪 CRM - Gestion des Magasins")
st.markdown("---")

# ==========================================
# FONCTIONS HELPER
# ==========================================

def safe_int(value, default=0):
    """Convertit une valeur en int, gère None et NaN"""
    if value is None:
        return default
    if pd.isna(value):
        return default
    try:
        return int(value)
    except (ValueError, TypeError):
        return default

def safe_str(value, default=''):
    """Convertit une valeur en str, gère None et NaN"""
    if value is None:
        return default
    if pd.isna(value):
        return default
    return str(value)

def safe_float(value, default=0.0):
    """Convertit une valeur en float, gère None et NaN"""
    if value is None:
        return default
    if pd.isna(value):
        return default
    try:
        return float(value)
    except (ValueError, TypeError):
        return default

# ==========================================
# FONCTIONS
# ==========================================

def get_commerciaux():
    """Liste des commerciaux"""
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
    """Options pour les filtres"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        options = {}
        
        cursor.execute("SELECT DISTINCT enseigne FROM crm_magasins WHERE is_active = TRUE AND enseigne IS NOT NULL ORDER BY enseigne")
        options['enseignes'] = [r['enseigne'] for r in cursor.fetchall()]
        
        cursor.execute("SELECT DISTINCT departement FROM crm_magasins WHERE is_active = TRUE AND departement IS NOT NULL ORDER BY departement")
        options['departements'] = [r['departement'] for r in cursor.fetchall()]
        
        cursor.execute("SELECT DISTINCT ville FROM crm_magasins WHERE is_active = TRUE AND ville IS NOT NULL ORDER BY ville")
        options['villes'] = [r['ville'] for r in cursor.fetchall()]
        
        cursor.close()
        conn.close()
        
        return options
    except:
        return {'enseignes': [], 'departements': [], 'villes': []}

def get_magasins(filtres=None):
    """Récupère les magasins avec filtres"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        query = """
            SELECT 
                m.id, m.code_magasin, m.enseigne, m.ville, m.departement,
                m.adresse, m.code_postal, m.centrale_achat, m.type_magasin, m.type_reseau,
                m.surface_m2, m.potentiel, m.presence_produit, m.ca_annuel,
                m.statut, m.points_amelioration, m.commentaires, m.notes,
                m.date_derniere_visite, m.date_prochaine_visite,
                m.commercial_id, c.prenom || ' ' || c.nom as commercial
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
                params.append(filtres['commercial_id'])
            if filtres.get('statut') and filtres['statut'] != 'Tous':
                query += " AND m.statut = %s"
                params.append(filtres['statut'])
            if filtres.get('ville') and filtres['ville'] != 'Tous':
                query += " AND m.ville = %s"
                params.append(filtres['ville'])
        
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

def get_contacts_magasin(magasin_id):
    """Contacts d'un magasin"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, nom, prenom, fonction, telephone, email, is_principal
            FROM crm_contacts
            WHERE magasin_id = %s AND is_active = TRUE
            ORDER BY is_principal DESC, nom
        """, (magasin_id,))
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        return rows if rows else []
    except:
        return []

def get_visites_magasin(magasin_id):
    """Dernières visites d'un magasin"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT v.date_visite, c.prenom || ' ' || c.nom as commercial, 
                   tv.libelle as type_visite, v.compte_rendu
            FROM crm_visites v
            LEFT JOIN crm_commerciaux c ON v.commercial_id = c.id
            LEFT JOIN crm_types_visite tv ON v.type_visite_id = tv.id
            WHERE v.magasin_id = %s AND v.is_active = TRUE AND v.statut = 'EFFECTUEE'
            ORDER BY v.date_visite DESC
            LIMIT 5
        """, (magasin_id,))
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        return rows if rows else []
    except:
        return []

def create_magasin(data):
    """Crée un nouveau magasin"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO crm_magasins (
                enseigne, ville, departement, adresse, code_postal,
                commercial_id, centrale_achat, type_magasin, type_reseau,
                surface_m2, potentiel, statut, presence_produit,
                points_amelioration, commentaires, notes, created_by
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (
            data['enseigne'], data['ville'], data.get('departement'),
            data.get('adresse'), data.get('code_postal'), data.get('commercial_id'),
            data.get('centrale_achat'), data.get('type_magasin'), data.get('type_reseau'),
            data.get('surface_m2'), data.get('potentiel'), data.get('statut', 'PROSPECT'),
            data.get('presence_produit'), data.get('points_amelioration'),
            data.get('commentaires'), data.get('notes'), data.get('created_by')
        ))
        
        new_id = cursor.fetchone()['id']
        conn.commit()
        cursor.close()
        conn.close()
        
        return True, f"✅ Magasin créé (ID: {new_id})"
    except Exception as e:
        return False, f"❌ Erreur : {str(e)}"

def update_magasin(magasin_id, data):
    """Met à jour un magasin"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE crm_magasins SET
                enseigne = %s, ville = %s, departement = %s, adresse = %s,
                code_postal = %s, commercial_id = %s, centrale_achat = %s,
                type_magasin = %s, type_reseau = %s, surface_m2 = %s,
                potentiel = %s, statut = %s, presence_produit = %s,
                points_amelioration = %s, commentaires = %s, notes = %s,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
        """, (
            data['enseigne'], data['ville'], data.get('departement'),
            data.get('adresse'), data.get('code_postal'), data.get('commercial_id'),
            data.get('centrale_achat'), data.get('type_magasin'), data.get('type_reseau'),
            data.get('surface_m2'), data.get('potentiel'), data.get('statut'),
            data.get('presence_produit'), data.get('points_amelioration'),
            data.get('commentaires'), data.get('notes'), magasin_id
        ))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return True, "✅ Magasin mis à jour"
    except Exception as e:
        return False, f"❌ Erreur : {str(e)}"

def delete_magasin(magasin_id):
    """Supprime (désactive) un magasin"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE crm_magasins SET is_active = FALSE, updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
        """, (magasin_id,))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return True, "✅ Magasin supprimé"
    except Exception as e:
        return False, f"❌ Erreur : {str(e)}"

# ==========================================
# INTERFACE
# ==========================================

tab1, tab2 = st.tabs(["📋 Liste des magasins", "➕ Nouveau magasin"])

# ==========================================
# TAB 1 : LISTE
# ==========================================

with tab1:
    # Filtres
    st.subheader("🔍 Filtres")
    
    options = get_filtres_options()
    commerciaux = get_commerciaux()
    
    col1, col2, col3, col4, col5 = st.columns(5)
    
    with col1:
        f_enseigne = st.selectbox("Enseigne", ['Tous'] + options['enseignes'], key="f_ens")
    with col2:
        f_dept = st.selectbox("Département", ['Tous'] + options['departements'], key="f_dept")
    with col3:
        f_ville = st.selectbox("Ville", ['Tous'] + options['villes'], key="f_ville")
    with col4:
        comm_options = [(0, 'Tous')] + commerciaux
        f_commercial = st.selectbox("Commercial", comm_options, format_func=lambda x: x[1], key="f_comm")
    with col5:
        f_statut = st.selectbox("Statut", ['Tous', 'ACTIF', 'PROSPECT', 'INACTIF', 'EN_PAUSE', 'PERDU'], key="f_stat")
    
    filtres = {
        'enseigne': f_enseigne,
        'departement': f_dept,
        'ville': f_ville,
        'commercial_id': f_commercial[0],
        'statut': f_statut
    }
    
    st.markdown("---")
    
    # Liste magasins
    df = get_magasins(filtres)
    
    if not df.empty:
        st.info(f"📊 {len(df)} magasin(s) trouvé(s)")
        
        for _, mag in df.iterrows():
            statut_icon = "🟢" if mag['statut'] == 'ACTIF' else ("🔵" if mag['statut'] == 'PROSPECT' else ("🟡" if mag['statut'] == 'EN_PAUSE' else "🔴"))
            
            with st.expander(f"{statut_icon} **{mag['enseigne']}** - {mag['ville']} ({mag['departement'] or 'N/A'})"):
                sub1, sub2, sub3 = st.tabs(["📝 Infos", "👥 Contacts", "📅 Visites"])
                
                with sub1:
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.markdown(f"**Code** : {safe_str(mag.get('code_magasin'), 'N/A')}")
                        st.markdown(f"**Adresse** : {safe_str(mag.get('adresse'), 'N/A')}")
                        st.markdown(f"**Code postal** : {safe_str(mag.get('code_postal'), 'N/A')}")
                        st.markdown(f"**Commercial** : {safe_str(mag.get('commercial'), 'Non assigné')}")
                        st.markdown(f"**Centrale** : {safe_str(mag.get('centrale_achat'), 'N/A')}")
                    
                    with col2:
                        st.markdown(f"**Type magasin** : {safe_str(mag.get('type_magasin'), 'N/A')}")
                        st.markdown(f"**Type réseau** : {safe_str(mag.get('type_reseau'), 'N/A')}")
                        surface_val = safe_int(mag.get('surface_m2'), 0)
                        st.markdown(f"**Surface** : {surface_val} m²" if surface_val > 0 else "**Surface** : N/A")
                        st.markdown(f"**Potentiel** : {safe_str(mag.get('potentiel'), 'N/A')}")
                        st.markdown(f"**Statut** : {mag['statut']}")
                    
                    if mag.get('presence_produit'):
                        st.markdown(f"**Présence produit** : {mag['presence_produit']}")
                    if mag.get('points_amelioration'):
                        st.markdown(f"**Points amélioration** : {mag['points_amelioration']}")
                    if mag.get('notes'):
                        st.markdown(f"**Notes** : {mag['notes']}")
                    
                    # Boutons actions
                    col_edit, col_delete = st.columns(2)
                    
                    with col_edit:
                        if can_edit("CRM"):
                            if st.button("✏️ Modifier", key=f"edit_{mag['id']}"):
                                st.session_state['edit_magasin_id'] = mag['id']
                                st.session_state['edit_magasin_data'] = mag.to_dict()
                                st.rerun()
                    
                    with col_delete:
                        if can_delete("CRM"):
                            if st.button("🗑️ Supprimer", key=f"del_{mag['id']}"):
                                st.session_state['confirm_delete_magasin'] = mag['id']
                                st.rerun()
                    
                    # Confirmation suppression
                    if st.session_state.get('confirm_delete_magasin') == mag['id']:
                        st.warning("⚠️ Confirmer la suppression ?")
                        col_yes, col_no = st.columns(2)
                        with col_yes:
                            if st.button("✅ Confirmer", key="confirm_yes_m"):
                                success, msg = delete_magasin(mag['id'])
                                if success:
                                    st.success(msg)
                                    st.session_state.pop('confirm_delete_magasin', None)
                                    st.rerun()
                                else:
                                    st.error(msg)
                        with col_no:
                            if st.button("❌ Annuler", key="confirm_no_m"):
                                st.session_state.pop('confirm_delete_magasin', None)
                                st.rerun()
                
                with sub2:
                    contacts = get_contacts_magasin(mag['id'])
                    if contacts:
                        for c in contacts:
                            principal = "⭐ " if c['is_principal'] else ""
                            st.markdown(f"**{principal}{c['prenom'] or ''} {c['nom'] or ''}** - {c['fonction'] or 'N/A'}")
                            st.caption(f"📞 {c['telephone'] or 'N/A'} | ✉️ {c['email'] or 'N/A'}")
                            st.markdown("---")
                    else:
                        st.info("Aucun contact")
                    
                    st.page_link("pages/22_CRM_Contacts.py", label="➕ Gérer les contacts", icon="👥")
                
                with sub3:
                    visites = get_visites_magasin(mag['id'])
                    if visites:
                        for v in visites:
                            date_str = v['date_visite'].strftime('%d/%m/%Y') if v['date_visite'] else ''
                            st.markdown(f"**{date_str}** - {v['commercial'] or 'N/A'} ({v['type_visite'] or 'N/A'})")
                            if v['compte_rendu']:
                                st.caption(v['compte_rendu'][:200] + "..." if len(v['compte_rendu'] or '') > 200 else v['compte_rendu'])
                            st.markdown("---")
                    else:
                        st.info("Aucune visite")
                    
                    st.page_link("pages/23_CRM_Visites.py", label="➕ Gérer les visites", icon="📅")
        
        # Formulaire modification
        if 'edit_magasin_id' in st.session_state and can_edit("CRM"):
            st.markdown("---")
            st.subheader("✏️ Modifier le magasin")
            
            data = st.session_state['edit_magasin_data']
            
            col1, col2 = st.columns(2)
            
            with col1:
                edit_enseigne = st.text_input("Enseigne *", value=safe_str(data.get('enseigne')), key="edit_ens")
                edit_ville = st.text_input("Ville *", value=safe_str(data.get('ville')), key="edit_ville")
                edit_adresse = st.text_input("Adresse", value=safe_str(data.get('adresse')), key="edit_adr")
                edit_cp = st.text_input("Code postal", value=safe_str(data.get('code_postal')), key="edit_cp")
                edit_dept = st.text_input("Département", value=safe_str(data.get('departement')), key="edit_dept")
                
                comm_list = [(None, 'Non assigné')] + commerciaux
                current_comm = next((i for i, c in enumerate(comm_list) if c[0] == data.get('commercial_id')), 0)
                edit_commercial = st.selectbox("Commercial", comm_list, index=current_comm, format_func=lambda x: x[1], key="edit_comm")
            
            with col2:
                edit_centrale = st.text_input("Centrale achat", value=safe_str(data.get('centrale_achat')), key="edit_centr")
                edit_type_mag = st.text_input("Type magasin", value=safe_str(data.get('type_magasin')), key="edit_tmag")
                edit_type_res = st.text_input("Type réseau", value=safe_str(data.get('type_reseau')), key="edit_tres")
                # ✅ CORRECTION: Utiliser safe_int pour gérer NaN
                edit_surface = st.number_input("Surface m²", value=safe_int(data.get('surface_m2'), 0), key="edit_surf")
                edit_potentiel = st.text_input("Potentiel", value=safe_str(data.get('potentiel')), key="edit_pot")
                
                # Gérer le statut avec valeur par défaut
                statut_options = ['ACTIF', 'PROSPECT', 'INACTIF', 'EN_PAUSE', 'PERDU']
                current_statut = safe_str(data.get('statut'), 'PROSPECT')
                if current_statut not in statut_options:
                    current_statut = 'PROSPECT'
                edit_statut = st.selectbox("Statut", statut_options, 
                                          index=statut_options.index(current_statut), key="edit_stat")
            
            edit_presence = st.text_input("Présence produit", value=safe_str(data.get('presence_produit')), key="edit_pres")
            edit_points = st.text_area("Points amélioration", value=safe_str(data.get('points_amelioration')), key="edit_pts")
            edit_comments = st.text_area("Commentaires", value=safe_str(data.get('commentaires')), key="edit_com")
            edit_notes = st.text_area("Notes", value=safe_str(data.get('notes')), key="edit_notes")
            
            col_save, col_cancel = st.columns(2)
            
            with col_save:
                if st.button("💾 Enregistrer", type="primary", key="btn_save_m"):
                    if not edit_enseigne or not edit_ville:
                        st.error("❌ Enseigne et ville obligatoires")
                    else:
                        update_data = {
                            'enseigne': edit_enseigne, 'ville': edit_ville,
                            'departement': edit_dept or None, 'adresse': edit_adresse or None,
                            'code_postal': edit_cp or None, 'commercial_id': edit_commercial[0],
                            'centrale_achat': edit_centrale or None, 'type_magasin': edit_type_mag or None,
                            'type_reseau': edit_type_res or None, 'surface_m2': edit_surface if edit_surface > 0 else None,
                            'potentiel': edit_potentiel or None, 'statut': edit_statut,
                            'presence_produit': edit_presence or None, 'points_amelioration': edit_points or None,
                            'commentaires': edit_comments or None, 'notes': edit_notes or None
                        }
                        success, msg = update_magasin(st.session_state['edit_magasin_id'], update_data)
                        if success:
                            st.success(msg)
                            st.session_state.pop('edit_magasin_id', None)
                            st.session_state.pop('edit_magasin_data', None)
                            st.rerun()
                        else:
                            st.error(msg)
            
            with col_cancel:
                if st.button("❌ Annuler", key="btn_cancel_m"):
                    st.session_state.pop('edit_magasin_id', None)
                    st.session_state.pop('edit_magasin_data', None)
                    st.rerun()
    else:
        st.info("Aucun magasin trouvé")

# ==========================================
# TAB 2 : NOUVEAU MAGASIN
# ==========================================

with tab2:
    if not can_edit("CRM"):
        st.warning("⚠️ Vous n'avez pas les droits pour créer un magasin")
    else:
        st.subheader("➕ Créer un magasin")
        
        commerciaux = get_commerciaux()
        
        col1, col2 = st.columns(2)
        
        with col1:
            new_enseigne = st.text_input("Enseigne *", key="new_ens")
            new_ville = st.text_input("Ville *", key="new_ville")
            new_adresse = st.text_input("Adresse", key="new_adr")
            new_cp = st.text_input("Code postal", key="new_cp")
            new_dept = st.text_input("Département", key="new_dept")
            
            comm_list = [(None, 'Non assigné')] + commerciaux
            new_commercial = st.selectbox("Commercial", comm_list, format_func=lambda x: x[1], key="new_comm")
        
        with col2:
            new_centrale = st.text_input("Centrale achat", key="new_centr")
            new_type_mag = st.text_input("Type magasin", key="new_tmag")
            new_type_res = st.text_input("Type réseau", key="new_tres")
            new_surface = st.number_input("Surface m²", min_value=0, value=0, key="new_surf")
            new_potentiel = st.text_input("Potentiel", key="new_pot")
            new_statut = st.selectbox("Statut", ['PROSPECT', 'ACTIF', 'INACTIF', 'EN_PAUSE', 'PERDU'], key="new_stat")
        
        new_presence = st.text_input("Présence produit", key="new_pres")
        new_points = st.text_area("Points amélioration", key="new_pts")
        new_comments = st.text_area("Commentaires", key="new_com")
        new_notes = st.text_area("Notes", key="new_notes")
        
        if st.button("✅ Créer le magasin", type="primary", key="btn_create_m"):
            if not new_enseigne or not new_ville:
                st.error("❌ Enseigne et ville obligatoires")
            else:
                data = {
                    'enseigne': new_enseigne, 'ville': new_ville,
                    'departement': new_dept or None, 'adresse': new_adresse or None,
                    'code_postal': new_cp or None, 'commercial_id': new_commercial[0],
                    'centrale_achat': new_centrale or None, 'type_magasin': new_type_mag or None,
                    'type_reseau': new_type_res or None, 'surface_m2': new_surface if new_surface > 0 else None,
                    'potentiel': new_potentiel or None, 'statut': new_statut,
                    'presence_produit': new_presence or None, 'points_amelioration': new_points or None,
                    'commentaires': new_comments or None, 'notes': new_notes or None,
                    'created_by': st.session_state.get('username', 'system')
                }
                success, msg = create_magasin(data)
                if success:
                    st.success(msg)
                    st.balloons()
                else:
                    st.error(msg)

show_footer()
