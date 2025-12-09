import streamlit as st
import pandas as pd
from datetime import datetime
from database import get_connection
from components import show_footer
from auth import is_authenticated, require_access, can_edit, can_delete

st.set_page_config(page_title="CRM Magasins - Culture Pom", page_icon="🏪", layout="wide")

if not is_authenticated():
    st.warning("⚠️ Veuillez vous connecter")
    st.stop()

require_access("CRM")

st.markdown("""
<style>
    .block-container { padding-top: 1.5rem !important; padding-bottom: 0.5rem !important; }
    h1, h2, h3, h4 { margin-top: 0.3rem !important; margin-bottom: 0.3rem !important; }
</style>
""", unsafe_allow_html=True)

st.title("🏪 CRM - Gestion des Magasins")
st.markdown("---")

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
                params.append(filtres['commercial_id'])
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

def get_contacts_magasin(magasin_id):
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, nom, prenom, fonction, telephone, email, is_principal
            FROM crm_contacts
            WHERE magasin_id = %s AND is_active = TRUE
            ORDER BY is_principal DESC, nom
        """, (int(magasin_id),))
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        return rows if rows else []
    except:
        return []

def get_visites_magasin(magasin_id):
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
        """, (int(magasin_id),))
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        return rows if rows else []
    except:
        return []

def create_magasin(data):
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
            data.get('commentaires'), data.get('notes'), int(magasin_id)
        ))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return True, "✅ Magasin mis à jour"
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
        return True, "✅ Magasin supprimé"
    except Exception as e:
        return False, f"❌ Erreur : {str(e)}"

# ==========================================
# INTERFACE
# ==========================================

tab1, tab2 = st.tabs(["📋 Liste des magasins", "➕ Nouveau magasin"])

# ==========================================
# TAB 1 : LISTE + DÉTAILS
# ==========================================

with tab1:
    # ========== FORMULAIRE MODIFICATION (EN HAUT) ==========
    if 'edit_magasin_id' in st.session_state and can_edit("CRM"):
        st.subheader("✏️ Modifier le magasin")
        
        data = st.session_state.get('edit_magasin_data', {})
        commerciaux = get_commerciaux()
        
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
            edit_surface = st.number_input("Surface m²", value=safe_int(data.get('surface_m2'), 0), key="edit_surf")
            edit_potentiel = st.text_input("Potentiel", value=safe_str(data.get('potentiel')), key="edit_pot")
            
            statut_options = ['ACTIF', 'PROSPECT', 'INACTIF', 'EN_PAUSE', 'PERDU']
            current_statut = safe_str(data.get('statut'), 'PROSPECT')
            if current_statut not in statut_options:
                current_statut = 'PROSPECT'
            edit_statut = st.selectbox("Statut", statut_options, index=statut_options.index(current_statut), key="edit_stat")
        
        edit_presence = st.text_input("Présence produit", value=safe_str(data.get('presence_produit')), key="edit_pres")
        edit_points = st.text_area("Points amélioration", value=safe_str(data.get('points_amelioration')), key="edit_pts", height=80)
        edit_notes = st.text_area("Notes", value=safe_str(data.get('notes')), key="edit_notes", height=80)
        
        col_save, col_cancel = st.columns(2)
        
        with col_save:
            if st.button("💾 Enregistrer", type="primary", key="btn_save_m", use_container_width=True):
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
                        'notes': edit_notes or None
                    }
                    success, msg = update_magasin(st.session_state['edit_magasin_id'], update_data)
                    if success:
                        st.success(msg)
                        st.session_state.pop('edit_magasin_id', None)
                        st.session_state.pop('edit_magasin_data', None)
                        st.session_state.pop('selected_magasin_id', None)
                        st.rerun()
                    else:
                        st.error(msg)
        
        with col_cancel:
            if st.button("❌ Annuler", key="btn_cancel_m", use_container_width=True):
                st.session_state.pop('edit_magasin_id', None)
                st.session_state.pop('edit_magasin_data', None)
                st.rerun()
        
        st.markdown("---")
    
    # ========== FILTRES ==========
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
    
    # ========== TABLEAU ==========
    df = get_magasins(filtres)
    
    if not df.empty:
        st.info(f"📊 **{len(df)} magasin(s)** - Cliquez sur une ligne pour voir les détails")
        
        # Préparer DataFrame pour affichage
        df_display = df[['id', 'enseigne', 'ville', 'departement', 'statut', 'commercial']].copy()
        df_display.columns = ['ID', 'Enseigne', 'Ville', 'Dept', 'Statut', 'Commercial']
        df_display['Commercial'] = df_display['Commercial'].fillna('Non assigné')
        
        # Configuration colonnes
        column_config = {
            "ID": st.column_config.NumberColumn("ID", width="small"),
            "Enseigne": st.column_config.TextColumn("Enseigne", width="medium"),
            "Ville": st.column_config.TextColumn("Ville", width="medium"),
            "Dept": st.column_config.TextColumn("Dept", width="small"),
            "Statut": st.column_config.TextColumn("Statut", width="small"),
            "Commercial": st.column_config.TextColumn("Commercial", width="medium")
        }
        
        # Tableau avec sélection
        event = st.dataframe(
            df_display,
            column_config=column_config,
            use_container_width=True,
            hide_index=True,
            on_select="rerun",
            selection_mode="single-row",
            key="magasins_table"
        )
        
        # Récupérer sélection
        selected_rows = event.selection.rows if hasattr(event, 'selection') else []
        
        # ========== ACTIONS + DÉTAILS ==========
        if len(selected_rows) > 0:
            selected_idx = selected_rows[0]
            selected_id = int(df_display.iloc[selected_idx]['ID'])
            
            # Charger données complètes du magasin
            mag = get_magasin_by_id(selected_id)
            
            if mag:
                st.session_state['selected_magasin_id'] = selected_id
                
                st.markdown("---")
                
                # ========== BOUTONS D'ACTION ==========
                col_actions = st.columns(4)
                
                with col_actions[0]:
                    st.success(f"✅ **{mag['enseigne']}** - {mag['ville']}")
                
                with col_actions[1]:
                    if can_edit("CRM"):
                        if st.button("✏️ Modifier", type="primary", use_container_width=True, key="btn_edit"):
                            st.session_state['edit_magasin_id'] = selected_id
                            st.session_state['edit_magasin_data'] = mag
                            st.rerun()
                
                with col_actions[2]:
                    if can_delete("CRM"):
                        if st.button("🗑️ Supprimer", type="secondary", use_container_width=True, key="btn_del"):
                            st.session_state['confirm_delete'] = selected_id
                
                with col_actions[3]:
                    if st.button("🔄 Désélectionner", use_container_width=True, key="btn_deselect"):
                        st.session_state.pop('selected_magasin_id', None)
                        st.rerun()
                
                # Confirmation suppression
                if st.session_state.get('confirm_delete') == selected_id:
                    st.warning("⚠️ Confirmer la suppression ?")
                    col_yes, col_no = st.columns(2)
                    with col_yes:
                        if st.button("✅ Oui, supprimer", key="confirm_yes"):
                            success, msg = delete_magasin(selected_id)
                            if success:
                                st.success(msg)
                                st.session_state.pop('confirm_delete', None)
                                st.session_state.pop('selected_magasin_id', None)
                                st.rerun()
                            else:
                                st.error(msg)
                    with col_no:
                        if st.button("❌ Annuler", key="confirm_no"):
                            st.session_state.pop('confirm_delete', None)
                            st.rerun()
                
                # ========== DÉTAILS EN ONGLETS ==========
                tab_info, tab_contacts, tab_visites = st.tabs(["📝 Informations", "👥 Contacts", "📅 Visites"])
                
                with tab_info:
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.markdown(f"**Enseigne** : {mag['enseigne']}")
                        st.markdown(f"**Ville** : {mag['ville']}")
                        st.markdown(f"**Adresse** : {safe_str(mag.get('adresse'), 'N/A')}")
                        st.markdown(f"**Code postal** : {safe_str(mag.get('code_postal'), 'N/A')}")
                        st.markdown(f"**Département** : {safe_str(mag.get('departement'), 'N/A')}")
                        st.markdown(f"**Commercial** : {safe_str(mag.get('commercial'), 'Non assigné')}")
                    
                    with col2:
                        statut = mag.get('statut', 'N/A')
                        statut_icon = "🟢" if statut == 'ACTIF' else ("🔵" if statut == 'PROSPECT' else ("🟡" if statut == 'EN_PAUSE' else "🔴"))
                        st.markdown(f"**Statut** : {statut_icon} {statut}")
                        st.markdown(f"**Centrale** : {safe_str(mag.get('centrale_achat'), 'N/A')}")
                        st.markdown(f"**Type magasin** : {safe_str(mag.get('type_magasin'), 'N/A')}")
                        st.markdown(f"**Type réseau** : {safe_str(mag.get('type_reseau'), 'N/A')}")
                        surface = safe_int(mag.get('surface_m2'), 0)
                        st.markdown(f"**Surface** : {surface} m²" if surface > 0 else "**Surface** : N/A")
                        st.markdown(f"**Potentiel** : {safe_str(mag.get('potentiel'), 'N/A')}")
                    
                    if mag.get('presence_produit'):
                        st.markdown(f"**Présence produit** : {mag['presence_produit']}")
                    if mag.get('points_amelioration'):
                        st.markdown(f"**Points amélioration** : {mag['points_amelioration']}")
                    if mag.get('notes'):
                        st.markdown(f"**Notes** : {mag['notes']}")
                
                with tab_contacts:
                    contacts = get_contacts_magasin(selected_id)
                    if contacts:
                        for c in contacts:
                            principal = "⭐ " if c['is_principal'] else ""
                            st.markdown(f"**{principal}{safe_str(c.get('prenom'))} {safe_str(c.get('nom'))}** - {safe_str(c.get('fonction'), 'N/A')}")
                            st.caption(f"📞 {safe_str(c.get('telephone'), 'N/A')} | ✉️ {safe_str(c.get('email'), 'N/A')}")
                            st.markdown("---")
                    else:
                        st.info("Aucun contact enregistré")
                    
                    st.page_link("pages/22_CRM_Contacts.py", label="➕ Gérer les contacts", icon="👥")
                
                with tab_visites:
                    visites = get_visites_magasin(selected_id)
                    if visites:
                        for v in visites:
                            date_str = v['date_visite'].strftime('%d/%m/%Y') if v.get('date_visite') else 'N/A'
                            st.markdown(f"**{date_str}** - {safe_str(v.get('commercial'), 'N/A')} ({safe_str(v.get('type_visite'), 'N/A')})")
                            if v.get('compte_rendu'):
                                cr = v['compte_rendu']
                                st.caption(cr[:200] + "..." if len(cr) > 200 else cr)
                            st.markdown("---")
                    else:
                        st.info("Aucune visite enregistrée")
                    
                    st.page_link("pages/23_CRM_Visites.py", label="➕ Gérer les visites", icon="📅")
        else:
            st.info("👆 Sélectionnez un magasin dans le tableau pour voir ses détails")
    else:
        st.warning("Aucun magasin trouvé avec ces filtres")

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
        new_points = st.text_area("Points amélioration", key="new_pts", height=80)
        new_notes = st.text_area("Notes", key="new_notes", height=80)
        
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
                    'notes': new_notes or None,
                    'created_by': st.session_state.get('username', 'system')
                }
                success, msg = create_magasin(data)
                if success:
                    st.success(msg)
                    st.balloons()
                else:
                    st.error(msg)

show_footer()
