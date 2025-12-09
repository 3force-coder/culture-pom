import streamlit as st
import pandas as pd
from datetime import datetime
from database import get_connection
from components import show_footer
from auth import is_authenticated
from roles import is_admin

st.set_page_config(page_title="CRM Magasins - Culture Pom", page_icon="🏪", layout="wide")

st.markdown("""
<style>
    .block-container { padding-top: 1.5rem !important; padding-bottom: 0.5rem !important; }
    h1, h2, h3, h4 { margin-top: 0.3rem !important; margin-bottom: 0.3rem !important; }
    .magasin-card {
        background-color: #f8f9fa;
        padding: 1rem;
        border-radius: 8px;
        border-left: 4px solid #1976d2;
        margin: 0.5rem 0;
    }
    .statut-actif { color: #2e7d32; font-weight: bold; }
    .statut-prospect { color: #1976d2; font-weight: bold; }
    .statut-inactif { color: #757575; font-weight: bold; }
</style>
""", unsafe_allow_html=True)

if not is_authenticated():
    st.warning("⚠️ Veuillez vous connecter")
    st.stop()

st.title("🏪 CRM - Gestion Magasins")
st.markdown("---")

# ==========================================
# FONCTIONS
# ==========================================

def get_commerciaux():
    """Liste des commerciaux pour dropdown"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, prenom || ' ' || nom as nom FROM crm_commerciaux WHERE is_active = TRUE ORDER BY nom")
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        return [(r[0], r[1]) for r in rows]
    except:
        return []

def get_magasins(filtres=None):
    """Récupère les magasins avec filtres optionnels"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        query = """
            SELECT 
                m.id, m.code_magasin, m.enseigne, m.ville, m.departement,
                c.prenom || ' ' || c.nom as commercial,
                m.centrale_achat, m.type_magasin, m.type_reseau,
                m.statut, m.date_derniere_visite, m.date_prochaine_visite,
                m.potentiel, m.presence_produit, m.surface_m2,
                m.adresse, m.code_postal, m.ca_annuel, m.note_performance,
                m.points_amelioration, m.commentaires, m.commercial_id
            FROM crm_magasins m
            LEFT JOIN crm_commerciaux c ON m.commercial_id = c.id
            WHERE m.is_active = TRUE
        """
        params = []
        
        if filtres:
            if filtres.get('enseigne') and filtres['enseigne'] != 'Tous':
                query += " AND m.enseigne = %s"
                params.append(filtres['enseigne'])
            if filtres.get('ville') and filtres['ville'] != 'Tous':
                query += " AND m.ville = %s"
                params.append(filtres['ville'])
            if filtres.get('commercial_id') and filtres['commercial_id'] != 0:
                query += " AND m.commercial_id = %s"
                params.append(filtres['commercial_id'])
            if filtres.get('statut') and filtres['statut'] != 'Tous':
                query += " AND m.statut = %s"
                params.append(filtres['statut'])
            if filtres.get('departement') and filtres['departement'] != 'Tous':
                query += " AND m.departement = %s"
                params.append(filtres['departement'])
        
        query += " ORDER BY m.enseigne, m.ville"
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        
        if rows:
            return pd.DataFrame(rows, columns=[
                'id', 'code_magasin', 'enseigne', 'ville', 'departement',
                'commercial', 'centrale_achat', 'type_magasin', 'type_reseau',
                'statut', 'date_derniere_visite', 'date_prochaine_visite',
                'potentiel', 'presence_produit', 'surface_m2',
                'adresse', 'code_postal', 'ca_annuel', 'note_performance',
                'points_amelioration', 'commentaires', 'commercial_id'
            ])
        return pd.DataFrame()
    except Exception as e:
        st.error(f"❌ Erreur : {str(e)}")
        return pd.DataFrame()

def get_filtres_options():
    """Récupère les options pour les filtres"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT DISTINCT enseigne FROM crm_magasins WHERE is_active = TRUE ORDER BY enseigne")
        enseignes = ['Tous'] + [r[0] for r in cursor.fetchall() if r[0]]
        
        cursor.execute("SELECT DISTINCT ville FROM crm_magasins WHERE is_active = TRUE ORDER BY ville")
        villes = ['Tous'] + [r[0] for r in cursor.fetchall() if r[0]]
        
        cursor.execute("SELECT DISTINCT departement FROM crm_magasins WHERE is_active = TRUE ORDER BY departement")
        departements = ['Tous'] + [r[0] for r in cursor.fetchall() if r[0]]
        
        cursor.execute("SELECT DISTINCT statut FROM crm_magasins WHERE is_active = TRUE ORDER BY statut")
        statuts = ['Tous'] + [r[0] for r in cursor.fetchall() if r[0]]
        
        cursor.close()
        conn.close()
        
        return {'enseignes': enseignes, 'villes': villes, 'departements': departements, 'statuts': statuts}
    except:
        return {'enseignes': ['Tous'], 'villes': ['Tous'], 'departements': ['Tous'], 'statuts': ['Tous']}

def get_contacts_magasin(magasin_id):
    """Récupère les contacts d'un magasin"""
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
        return rows
    except:
        return []

def get_visites_magasin(magasin_id, limit=5):
    """Récupère les dernières visites d'un magasin"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT v.date_visite, c.prenom || ' ' || c.nom as commercial, tv.libelle, v.compte_rendu
            FROM crm_visites v
            LEFT JOIN crm_commerciaux c ON v.commercial_id = c.id
            LEFT JOIN crm_types_visite tv ON v.type_visite_id = tv.id
            WHERE v.magasin_id = %s
            ORDER BY v.date_visite DESC
            LIMIT %s
        """, (magasin_id, limit))
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        return rows
    except:
        return []

def create_magasin(data):
    """Crée un nouveau magasin"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO crm_magasins (
                enseigne, ville, commercial_id, centrale_achat, type_magasin,
                type_reseau, adresse, code_postal, departement, surface_m2,
                potentiel, statut, presence_produit, points_amelioration, commentaires
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id, code_magasin
        """, (
            data['enseigne'], data['ville'], data.get('commercial_id'),
            data.get('centrale_achat'), data.get('type_magasin'),
            data.get('type_reseau'), data.get('adresse'), data.get('code_postal'),
            data.get('departement'), data.get('surface_m2'),
            data.get('potentiel'), data.get('statut', 'PROSPECT'),
            data.get('presence_produit'), data.get('points_amelioration'),
            data.get('commentaires')
        ))
        
        result = cursor.fetchone()
        conn.commit()
        cursor.close()
        conn.close()
        
        return True, f"✅ Magasin {result[1]} créé"
    except Exception as e:
        return False, f"❌ Erreur : {str(e)}"

def update_magasin(magasin_id, data):
    """Met à jour un magasin"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE crm_magasins SET
                enseigne = %s, ville = %s, commercial_id = %s, centrale_achat = %s,
                type_magasin = %s, type_reseau = %s, adresse = %s, code_postal = %s,
                departement = %s, surface_m2 = %s, potentiel = %s, statut = %s,
                presence_produit = %s, points_amelioration = %s, commentaires = %s,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
        """, (
            data['enseigne'], data['ville'], data.get('commercial_id'),
            data.get('centrale_achat'), data.get('type_magasin'),
            data.get('type_reseau'), data.get('adresse'), data.get('code_postal'),
            data.get('departement'), data.get('surface_m2'),
            data.get('potentiel'), data.get('statut'),
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
    """Supprime (désactive) un magasin - ADMIN uniquement"""
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
        filtre_enseigne = st.selectbox("Enseigne", options['enseignes'], key="f_ens")
    with col2:
        filtre_dept = st.selectbox("Département", options['departements'], key="f_dept")
    with col3:
        comm_options = [(0, 'Tous')] + commerciaux
        filtre_commercial = st.selectbox("Commercial", comm_options, format_func=lambda x: x[1], key="f_comm")
    with col4:
        filtre_statut = st.selectbox("Statut", options['statuts'], key="f_stat")
    with col5:
        filtre_ville = st.selectbox("Ville", options['villes'], key="f_ville")
    
    filtres = {
        'enseigne': filtre_enseigne,
        'departement': filtre_dept,
        'commercial_id': filtre_commercial[0] if filtre_commercial else 0,
        'statut': filtre_statut,
        'ville': filtre_ville
    }
    
    st.markdown("---")
    
    # Chargement
    df = get_magasins(filtres)
    
    if not df.empty:
        st.markdown(f"**{len(df)} magasin(s) trouvé(s)**")
        
        # Tableau principal
        display_df = df[['code_magasin', 'enseigne', 'ville', 'departement', 'commercial', 'statut', 'date_derniere_visite']].copy()
        display_df.columns = ['Code', 'Enseigne', 'Ville', 'Dépt', 'Commercial', 'Statut', 'Dernière visite']
        display_df['Dernière visite'] = pd.to_datetime(display_df['Dernière visite']).dt.strftime('%d/%m/%Y')
        display_df = display_df.fillna('')
        
        # Sélection
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
            st.subheader(f"📋 {mag['enseigne']} - {mag['ville']}")
            
            # Onglets détail
            detail_tab1, detail_tab2, detail_tab3 = st.tabs(["ℹ️ Informations", "👥 Contacts", "📅 Visites"])
            
            with detail_tab1:
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    st.markdown("**Identification**")
                    st.write(f"📌 Code : {mag['code_magasin']}")
                    st.write(f"🏪 Enseigne : {mag['enseigne']}")
                    st.write(f"📍 {mag['adresse'] or ''}")
                    st.write(f"📮 {mag['code_postal'] or ''} {mag['ville']}")
                    st.write(f"🗺️ Département : {mag['departement'] or ''}")
                
                with col2:
                    st.markdown("**Commercial**")
                    st.write(f"👤 {mag['commercial'] or 'Non assigné'}")
                    st.write(f"🏢 Centrale : {mag['centrale_achat'] or ''}")
                    st.write(f"🏷️ Type : {mag['type_magasin'] or ''}")
                    st.write(f"🔗 Réseau : {mag['type_reseau'] or ''}")
                    statut_class = 'statut-actif' if mag['statut'] == 'ACTIF' else 'statut-prospect' if mag['statut'] == 'PROSPECT' else 'statut-inactif'
                    st.markdown(f"📊 Statut : <span class='{statut_class}'>{mag['statut']}</span>", unsafe_allow_html=True)
                
                with col3:
                    st.markdown("**Performance**")
                    st.write(f"📐 Surface : {mag['surface_m2'] or '-'} m²")
                    st.write(f"⭐ Potentiel : {mag['potentiel'] or '-'}")
                    st.write(f"📦 Présence produit : {mag['presence_produit'] or '-'}")
                    ca = f"{mag['ca_annuel']:,.0f} €" if mag['ca_annuel'] else '-'
                    st.write(f"💰 CA annuel : {ca}")
                    st.write(f"📝 Note : {mag['note_performance'] or '-'}/10")
                
                if mag['points_amelioration']:
                    st.markdown("**Points d'amélioration**")
                    st.info(mag['points_amelioration'])
                
                if mag['commentaires']:
                    st.markdown("**Commentaires**")
                    st.write(mag['commentaires'])
                
                # Boutons actions
                st.markdown("---")
                col_a, col_b, col_c = st.columns([1, 1, 2])
                
                with col_a:
                    if st.button("✏️ Modifier", key="btn_edit"):
                        st.session_state['edit_magasin_id'] = mag['id']
                        st.session_state['edit_magasin_data'] = mag.to_dict()
                        st.rerun()
                
                with col_b:
                    if is_admin():
                        if st.button("🗑️ Supprimer", key="btn_del", type="secondary"):
                            st.session_state['confirm_delete'] = mag['id']
                            st.rerun()
                
                # Confirmation suppression
                if st.session_state.get('confirm_delete') == mag['id']:
                    st.warning(f"⚠️ Confirmer la suppression de {mag['enseigne']} - {mag['ville']} ?")
                    col_yes, col_no = st.columns(2)
                    with col_yes:
                        if st.button("✅ Confirmer", key="confirm_yes"):
                            success, msg = delete_magasin(mag['id'])
                            if success:
                                st.success(msg)
                                st.session_state.pop('confirm_delete', None)
                                st.rerun()
                            else:
                                st.error(msg)
                    with col_no:
                        if st.button("❌ Annuler", key="confirm_no"):
                            st.session_state.pop('confirm_delete', None)
                            st.rerun()
            
            with detail_tab2:
                contacts = get_contacts_magasin(mag['id'])
                if contacts:
                    for c in contacts:
                        principal = "⭐ " if c[6] else ""
                        st.markdown(f"**{principal}{c[1] or ''} {c[2] or ''}** - {c[3] or ''}")
                        if c[4]:
                            st.write(f"📞 {c[4]}")
                        if c[5]:
                            st.write(f"📧 {c[5]}")
                        st.markdown("---")
                else:
                    st.info("Aucun contact enregistré")
                
                st.page_link("pages/22_CRM_Contacts.py", label="👥 Gérer les contacts", use_container_width=True)
            
            with detail_tab3:
                visites = get_visites_magasin(mag['id'])
                if visites:
                    for v in visites:
                        date_str = v[0].strftime('%d/%m/%Y') if v[0] else ''
                        st.markdown(f"**{date_str}** - {v[1] or 'N/A'} ({v[2] or ''})")
                        if v[3]:
                            st.caption(v[3][:200] + "..." if len(v[3] or '') > 200 else v[3])
                        st.markdown("---")
                else:
                    st.info("Aucune visite enregistrée")
                
                st.page_link("pages/23_CRM_Visites.py", label="📋 Gérer les visites", use_container_width=True)
        
        # Formulaire modification
        if 'edit_magasin_id' in st.session_state:
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
                edit_centrale = st.text_input("Centrale d'achat", value=data.get('centrale_achat', '') or '', key="edit_centr")
                type_mag_opts = ['', 'EXPRESS', 'CONTACT', 'HYPER', 'SUPER']
                current_type = type_mag_opts.index(data.get('type_magasin', '')) if data.get('type_magasin', '') in type_mag_opts else 0
                edit_type_mag = st.selectbox("Type magasin", type_mag_opts, index=current_type, key="edit_type")
                reseau_opts = ['', 'INDEPENDANT', 'INTEGRE']
                current_reseau = reseau_opts.index(data.get('type_reseau', '')) if data.get('type_reseau', '') in reseau_opts else 0
                edit_reseau = st.selectbox("Type réseau", reseau_opts, index=current_reseau, key="edit_reseau")
                statut_opts = ['PROSPECT', 'ACTIF', 'EN_PAUSE', 'INACTIF', 'PERDU']
                current_statut = statut_opts.index(data.get('statut', 'PROSPECT')) if data.get('statut', 'PROSPECT') in statut_opts else 0
                edit_statut = st.selectbox("Statut", statut_opts, index=current_statut, key="edit_statut")
                potentiel_opts = ['', 'TRES_FAIBLE', 'FAIBLE', 'MOYEN', 'FORT', 'ELEVE']
                current_pot = potentiel_opts.index(data.get('potentiel', '')) if data.get('potentiel', '') in potentiel_opts else 0
                edit_potentiel = st.selectbox("Potentiel", potentiel_opts, index=current_pot, key="edit_pot")
                presence_opts = ['', 'OUI', 'NON', 'PARTIELLE']
                current_pres = presence_opts.index(data.get('presence_produit', '')) if data.get('presence_produit', '') in presence_opts else 0
                edit_presence = st.selectbox("Présence produit", presence_opts, index=current_pres, key="edit_pres")
            
            edit_surface = st.number_input("Surface m²", value=int(data.get('surface_m2', 0) or 0), min_value=0, key="edit_surf")
            edit_points = st.text_area("Points d'amélioration", value=data.get('points_amelioration', '') or '', key="edit_pts")
            edit_comm_txt = st.text_area("Commentaires", value=data.get('commentaires', '') or '', key="edit_comm_txt")
            
            col_save, col_cancel = st.columns(2)
            
            with col_save:
                if st.button("💾 Enregistrer", type="primary", key="btn_save_edit"):
                    if not edit_enseigne or not edit_ville:
                        st.error("❌ Enseigne et Ville obligatoires")
                    else:
                        update_data = {
                            'enseigne': edit_enseigne,
                            'ville': edit_ville,
                            'commercial_id': edit_commercial[0],
                            'centrale_achat': edit_centrale or None,
                            'type_magasin': edit_type_mag or None,
                            'type_reseau': edit_reseau or None,
                            'adresse': edit_adresse or None,
                            'code_postal': edit_cp or None,
                            'departement': edit_dept or None,
                            'surface_m2': edit_surface or None,
                            'potentiel': edit_potentiel or None,
                            'statut': edit_statut,
                            'presence_produit': edit_presence or None,
                            'points_amelioration': edit_points or None,
                            'commentaires': edit_comm_txt or None
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
                if st.button("❌ Annuler", key="btn_cancel_edit"):
                    st.session_state.pop('edit_magasin_id', None)
                    st.session_state.pop('edit_magasin_data', None)
                    st.rerun()
    else:
        st.info("Aucun magasin trouvé avec ces filtres")

# ==========================================
# TAB 2 : NOUVEAU MAGASIN
# ==========================================

with tab2:
    st.subheader("➕ Créer un nouveau magasin")
    
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
        new_centrale = st.text_input("Centrale d'achat", key="new_centr")
        new_type_mag = st.selectbox("Type magasin", ['', 'EXPRESS', 'CONTACT', 'HYPER', 'SUPER'], key="new_type")
        new_reseau = st.selectbox("Type réseau", ['', 'INDEPENDANT', 'INTEGRE'], key="new_reseau")
        new_statut = st.selectbox("Statut", ['PROSPECT', 'ACTIF', 'EN_PAUSE', 'INACTIF', 'PERDU'], key="new_statut")
        new_potentiel = st.selectbox("Potentiel", ['', 'TRES_FAIBLE', 'FAIBLE', 'MOYEN', 'FORT', 'ELEVE'], key="new_pot")
        new_presence = st.selectbox("Présence produit", ['', 'OUI', 'NON', 'PARTIELLE'], key="new_pres")
    
    new_surface = st.number_input("Surface m²", value=0, min_value=0, key="new_surf")
    new_points = st.text_area("Points d'amélioration", key="new_pts")
    new_comm_txt = st.text_area("Commentaires", key="new_comm_txt")
    
    if st.button("✅ Créer le magasin", type="primary", key="btn_create"):
        if not new_enseigne or not new_ville:
            st.error("❌ Enseigne et Ville sont obligatoires")
        else:
            data = {
                'enseigne': new_enseigne,
                'ville': new_ville,
                'commercial_id': new_commercial[0],
                'centrale_achat': new_centrale or None,
                'type_magasin': new_type_mag or None,
                'type_reseau': new_reseau or None,
                'adresse': new_adresse or None,
                'code_postal': new_cp or None,
                'departement': new_dept or None,
                'surface_m2': new_surface or None,
                'potentiel': new_potentiel or None,
                'statut': new_statut,
                'presence_produit': new_presence or None,
                'points_amelioration': new_points or None,
                'commentaires': new_comm_txt or None
            }
            success, msg = create_magasin(data)
            if success:
                st.success(msg)
                st.balloons()
            else:
                st.error(msg)

show_footer()
