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
                m.surface_m2, m.potentiel, m.presence_produit, m.ca_annuel, m.note_magasin,
                m.statut, m.points_amelioration, m.commentaires,
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
                points_amelioration, commentaires, created_by
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id, code_magasin
        """, (
            data['enseigne'], data['ville'], data.get('departement'),
            data.get('adresse'), data.get('code_postal'),
            data.get('commercial_id'), data.get('centrale_achat'),
            data.get('type_magasin'), data.get('type_reseau'),
            data.get('surface_m2'), data.get('potentiel'),
            data.get('statut', 'PROSPECT'), data.get('presence_produit'),
            data.get('points_amelioration'), data.get('commentaires'),
            data.get('created_by')
        ))
        
        result = cursor.fetchone()
        conn.commit()
        cursor.close()
        conn.close()
        
        return True, f"✅ Magasin créé : {result['code_magasin']}"
    except Exception as e:
        return False, f"❌ Erreur : {str(e)}"

def update_magasin(magasin_id, data):
    """Met à jour un magasin"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE crm_magasins SET
                enseigne = %s, ville = %s, departement = %s,
                adresse = %s, code_postal = %s, commercial_id = %s,
                centrale_achat = %s, type_magasin = %s, type_reseau = %s,
                surface_m2 = %s, potentiel = %s, statut = %s,
                presence_produit = %s, points_amelioration = %s,
                commentaires = %s, updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
        """, (
            data['enseigne'], data['ville'], data.get('departement'),
            data.get('adresse'), data.get('code_postal'), data.get('commercial_id'),
            data.get('centrale_achat'), data.get('type_magasin'), data.get('type_reseau'),
            data.get('surface_m2'), data.get('potentiel'), data.get('statut'),
            data.get('presence_produit'), data.get('points_amelioration'),
            data.get('commentaires'), magasin_id
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
        cursor.execute("UPDATE crm_magasins SET is_active = FALSE, updated_at = CURRENT_TIMESTAMP WHERE id = %s", (magasin_id,))
        conn.commit()
        cursor.close()
        conn.close()
        return True, "✅ Magasin supprimé"
    except Exception as e:
        return False, f"❌ Erreur : {str(e)}"

# ==========================================
# ONGLETS
# ==========================================

tab1, tab2 = st.tabs(["📋 Liste Magasins", "➕ Nouveau Magasin"])

# ==========================================
# TAB 1 : LISTE
# ==========================================

with tab1:
    # Filtres
    options = get_filtres_options()
    commerciaux = get_commerciaux()
    
    col1, col2, col3, col4, col5 = st.columns(5)
    
    with col1:
        filtre_enseigne = st.selectbox("Enseigne", ['Tous'] + options['enseignes'], key="f_ens")
    with col2:
        filtre_dept = st.selectbox("Département", ['Tous'] + options['departements'], key="f_dept")
    with col3:
        comm_options = [(0, 'Tous')] + commerciaux
        filtre_comm = st.selectbox("Commercial", comm_options, format_func=lambda x: x[1], key="f_comm")
    with col4:
        filtre_statut = st.selectbox("Statut", ['Tous', 'ACTIF', 'PROSPECT', 'INACTIF', 'EN_PAUSE', 'PERDU'], key="f_stat")
    with col5:
        filtre_ville = st.selectbox("Ville", ['Tous'] + options['villes'], key="f_ville")
    
    filtres = {
        'enseigne': filtre_enseigne,
        'departement': filtre_dept,
        'commercial_id': filtre_comm[0] if filtre_comm else 0,
        'statut': filtre_statut,
        'ville': filtre_ville
    }
    
    st.markdown("---")
    
    df = get_magasins(filtres)
    
    if not df.empty:
        st.markdown(f"**{len(df)} magasin(s) trouvé(s)**")
        
        # Tableau simplifié
        display_df = df[['code_magasin', 'enseigne', 'ville', 'departement', 'commercial', 'statut', 'date_derniere_visite']].copy()
        display_df['date_derniere_visite'] = pd.to_datetime(display_df['date_derniere_visite']).dt.strftime('%d/%m/%Y')
        display_df.columns = ['Code', 'Enseigne', 'Ville', 'Dépt', 'Commercial', 'Statut', 'Dernière visite']
        display_df = display_df.fillna('')
        
        event = st.dataframe(
            display_df,
            use_container_width=True,
            hide_index=True,
            on_select="rerun",
            selection_mode="single-row",
            key="magasins_table"
        )
        
        selected_rows = event.selection.rows if hasattr(event, 'selection') else []
        
        if len(selected_rows) > 0:
            idx = selected_rows[0]
            mag = df.iloc[idx]
            
            st.markdown("---")
            st.subheader(f"🏪 {mag['enseigne']} - {mag['ville']}")
            
            # 3 sous-onglets
            sub1, sub2, sub3 = st.tabs(["📋 Informations", "👥 Contacts", "📅 Visites"])
            
            with sub1:
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    st.markdown("**Identification**")
                    st.write(f"Code : {mag['code_magasin']}")
                    st.write(f"Enseigne : {mag['enseigne']}")
                    st.write(f"Adresse : {mag['adresse'] or 'N/A'}")
                    st.write(f"CP/Ville : {mag['code_postal'] or ''} {mag['ville']}")
                    st.write(f"Département : {mag['departement'] or 'N/A'}")
                
                with col2:
                    st.markdown("**Commercial**")
                    st.write(f"Commercial : {mag['commercial'] or 'Non assigné'}")
                    st.write(f"Centrale : {mag['centrale_achat'] or 'N/A'}")
                    st.write(f"Type magasin : {mag['type_magasin'] or 'N/A'}")
                    st.write(f"Type réseau : {mag['type_reseau'] or 'N/A'}")
                    st.write(f"Statut : {mag['statut']}")
                
                with col3:
                    st.markdown("**Performance**")
                    st.write(f"Surface : {mag['surface_m2'] or 'N/A'} m²")
                    st.write(f"Potentiel : {mag['potentiel'] or 'N/A'}")
                    st.write(f"Présence produit : {mag['presence_produit'] or 'N/A'}")
                    st.write(f"CA annuel : {mag['ca_annuel'] or 'N/A'} €")
                    st.write(f"Note : {mag['note_magasin'] or 'N/A'}/10")
                
                if mag['points_amelioration']:
                    st.warning(f"📝 Points amélioration : {mag['points_amelioration']}")
                if mag['commentaires']:
                    st.info(f"💬 Commentaires : {mag['commentaires']}")
                
                # Boutons actions
                col_a, col_b, col_c = st.columns([1, 1, 2])
                
                with col_a:
                    if can_edit("CRM"):
                        if st.button("✏️ Modifier", key="btn_edit_m"):
                            st.session_state['edit_magasin_id'] = mag['id']
                            st.session_state['edit_magasin_data'] = mag.to_dict()
                            st.rerun()
                
                with col_b:
                    if can_delete("CRM"):
                        if st.button("🗑️ Supprimer", key="btn_del_m", type="secondary"):
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
                edit_enseigne = st.text_input("Enseigne *", value=data.get('enseigne', ''), key="edit_ens")
                edit_ville = st.text_input("Ville *", value=data.get('ville', ''), key="edit_ville")
                edit_adresse = st.text_input("Adresse", value=data.get('adresse', '') or '', key="edit_adr")
                edit_cp = st.text_input("Code postal", value=data.get('code_postal', '') or '', key="edit_cp")
                edit_dept = st.text_input("Département", value=data.get('departement', '') or '', key="edit_dept")
                
                comm_list = [(None, 'Non assigné')] + commerciaux
                current_comm = next((i for i, c in enumerate(comm_list) if c[0] == data.get('commercial_id')), 0)
                edit_commercial = st.selectbox("Commercial", comm_list, index=current_comm, format_func=lambda x: x[1], key="edit_comm")
            
            with col2:
                edit_centrale = st.text_input("Centrale achat", value=data.get('centrale_achat', '') or '', key="edit_centr")
                edit_type_mag = st.text_input("Type magasin", value=data.get('type_magasin', '') or '', key="edit_tmag")
                edit_type_res = st.text_input("Type réseau", value=data.get('type_reseau', '') or '', key="edit_tres")
                edit_surface = st.number_input("Surface m²", value=int(data.get('surface_m2') or 0), key="edit_surf")
                edit_potentiel = st.text_input("Potentiel", value=data.get('potentiel', '') or '', key="edit_pot")
                edit_statut = st.selectbox("Statut", ['ACTIF', 'PROSPECT', 'INACTIF', 'EN_PAUSE', 'PERDU'], 
                                          index=['ACTIF', 'PROSPECT', 'INACTIF', 'EN_PAUSE', 'PERDU'].index(data.get('statut', 'PROSPECT')), key="edit_stat")
            
            edit_presence = st.text_input("Présence produit", value=data.get('presence_produit', '') or '', key="edit_pres")
            edit_points = st.text_area("Points amélioration", value=data.get('points_amelioration', '') or '', key="edit_pts")
            edit_comments = st.text_area("Commentaires", value=data.get('commentaires', '') or '', key="edit_com")
            
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
                            'commentaires': edit_comments or None
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
                    'commentaires': new_comments or None,
                    'created_by': st.session_state.get('username', 'system')
                }
                success, msg = create_magasin(data)
                if success:
                    st.success(msg)
                    st.balloons()
                else:
                    st.error(msg)

show_footer()
