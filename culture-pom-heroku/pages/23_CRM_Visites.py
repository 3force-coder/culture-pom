import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from database import get_connection
from components import show_footer
from auth import is_authenticated
from roles import is_admin

st.set_page_config(page_title="CRM Visites - Culture Pom", page_icon="📋", layout="wide")

st.markdown("""
<style>
    .block-container { padding-top: 1.5rem !important; padding-bottom: 0.5rem !important; }
    h1, h2, h3, h4 { margin-top: 0.3rem !important; margin-bottom: 0.3rem !important; }
    .visite-effectuee { background-color: #e8f5e9; border-left: 4px solid #4caf50; padding: 0.8rem; border-radius: 4px; margin: 0.3rem 0; }
    .visite-planifiee { background-color: #e3f2fd; border-left: 4px solid #2196f3; padding: 0.8rem; border-radius: 4px; margin: 0.3rem 0; }
    .visite-annulee { background-color: #ffebee; border-left: 4px solid #f44336; padding: 0.8rem; border-radius: 4px; margin: 0.3rem 0; }
</style>
""", unsafe_allow_html=True)

if not is_authenticated():
    st.warning("⚠️ Veuillez vous connecter")
    st.stop()

st.title("📋 CRM - Gestion Visites")
st.markdown("---")

# ==========================================
# FONCTIONS
# ==========================================

def get_magasins_dropdown():
    """Liste des magasins pour dropdown"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, code_magasin, enseigne || ' - ' || ville as nom 
            FROM crm_magasins WHERE is_active = TRUE ORDER BY enseigne, ville
        """)
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        return [(r[0], r[1], r[2]) for r in rows]
    except:
        return []

def get_commerciaux():
    """Liste des commerciaux"""
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

def get_types_visite():
    """Liste des types de visite"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, code, libelle FROM crm_types_visite WHERE is_active = TRUE ORDER BY libelle")
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        return [(r[0], r[1], r[2]) for r in rows]
    except:
        return []

def get_visites(filtres=None):
    """Récupère les visites avec filtres"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        query = """
            SELECT 
                v.id, v.magasin_id, m.code_magasin, m.enseigne, m.ville,
                v.commercial_id, c.prenom || ' ' || c.nom as commercial,
                v.date_visite, v.type_visite_id, tv.libelle as type_visite,
                v.presence_produit, v.compte_rendu, v.points_amelioration,
                v.date_prochaine_visite, v.statut, v.created_by, v.created_at
            FROM crm_visites v
            JOIN crm_magasins m ON v.magasin_id = m.id
            LEFT JOIN crm_commerciaux c ON v.commercial_id = c.id
            LEFT JOIN crm_types_visite tv ON v.type_visite_id = tv.id
            WHERE m.is_active = TRUE
        """
        params = []
        
        if filtres:
            if filtres.get('magasin_id') and filtres['magasin_id'] != 0:
                query += " AND v.magasin_id = %s"
                params.append(filtres['magasin_id'])
            if filtres.get('commercial_id') and filtres['commercial_id'] != 0:
                query += " AND v.commercial_id = %s"
                params.append(filtres['commercial_id'])
            if filtres.get('statut') and filtres['statut'] != 'Tous':
                query += " AND v.statut = %s"
                params.append(filtres['statut'])
            if filtres.get('date_debut'):
                query += " AND v.date_visite >= %s"
                params.append(filtres['date_debut'])
            if filtres.get('date_fin'):
                query += " AND v.date_visite <= %s"
                params.append(filtres['date_fin'])
        
        query += " ORDER BY v.date_visite DESC, v.created_at DESC"
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        
        if rows:
            return pd.DataFrame(rows, columns=[
                'id', 'magasin_id', 'code_magasin', 'enseigne', 'ville',
                'commercial_id', 'commercial', 'date_visite', 'type_visite_id', 'type_visite',
                'presence_produit', 'compte_rendu', 'points_amelioration',
                'date_prochaine_visite', 'statut', 'created_by', 'created_at'
            ])
        return pd.DataFrame()
    except Exception as e:
        st.error(f"❌ Erreur : {str(e)}")
        return pd.DataFrame()

def get_visites_semaine(date_debut):
    """Récupère les visites pour une semaine (planning)"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        date_fin = date_debut + timedelta(days=6)
        
        cursor.execute("""
            SELECT 
                v.id, v.date_visite, m.enseigne, m.ville,
                c.prenom || ' ' || c.nom as commercial,
                tv.libelle as type_visite, v.statut
            FROM crm_visites v
            JOIN crm_magasins m ON v.magasin_id = m.id
            LEFT JOIN crm_commerciaux c ON v.commercial_id = c.id
            LEFT JOIN crm_types_visite tv ON v.type_visite_id = tv.id
            WHERE v.date_visite BETWEEN %s AND %s
            ORDER BY v.date_visite, c.nom
        """, (date_debut, date_fin))
        
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        
        if rows:
            return pd.DataFrame(rows, columns=['id', 'date_visite', 'enseigne', 'ville', 'commercial', 'type_visite', 'statut'])
        return pd.DataFrame()
    except Exception as e:
        st.error(f"❌ Erreur : {str(e)}")
        return pd.DataFrame()

def create_visite(data):
    """Crée une nouvelle visite"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO crm_visites (
                magasin_id, commercial_id, date_visite, type_visite_id,
                presence_produit, compte_rendu, points_amelioration,
                date_prochaine_visite, statut, created_by
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (
            data['magasin_id'], data.get('commercial_id'), data['date_visite'],
            data.get('type_visite_id'), data.get('presence_produit'),
            data.get('compte_rendu'), data.get('points_amelioration'),
            data.get('date_prochaine_visite'), data.get('statut', 'EFFECTUEE'),
            data.get('created_by')
        ))
        
        visite_id = cursor.fetchone()[0]
        
        # Mettre à jour date_derniere_visite du magasin si effectuée
        if data.get('statut') == 'EFFECTUEE':
            cursor.execute("""
                UPDATE crm_magasins 
                SET date_derniere_visite = %s, updated_at = CURRENT_TIMESTAMP
                WHERE id = %s AND (date_derniere_visite IS NULL OR date_derniere_visite < %s)
            """, (data['date_visite'], data['magasin_id'], data['date_visite']))
        
        # Mettre à jour date_prochaine_visite si renseignée
        if data.get('date_prochaine_visite'):
            cursor.execute("""
                UPDATE crm_magasins 
                SET date_prochaine_visite = %s, updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
            """, (data['date_prochaine_visite'], data['magasin_id']))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return True, f"✅ Visite #{visite_id} créée"
    except Exception as e:
        return False, f"❌ Erreur : {str(e)}"

def update_visite(visite_id, data):
    """Met à jour une visite"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE crm_visites SET
                magasin_id = %s, commercial_id = %s, date_visite = %s,
                type_visite_id = %s, presence_produit = %s, compte_rendu = %s,
                points_amelioration = %s, date_prochaine_visite = %s, statut = %s,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
        """, (
            data['magasin_id'], data.get('commercial_id'), data['date_visite'],
            data.get('type_visite_id'), data.get('presence_produit'),
            data.get('compte_rendu'), data.get('points_amelioration'),
            data.get('date_prochaine_visite'), data.get('statut'),
            visite_id
        ))
        
        # Mettre à jour dates magasin
        if data.get('statut') == 'EFFECTUEE':
            cursor.execute("""
                UPDATE crm_magasins 
                SET date_derniere_visite = %s, updated_at = CURRENT_TIMESTAMP
                WHERE id = %s AND (date_derniere_visite IS NULL OR date_derniere_visite < %s)
            """, (data['date_visite'], data['magasin_id'], data['date_visite']))
        
        if data.get('date_prochaine_visite'):
            cursor.execute("""
                UPDATE crm_magasins 
                SET date_prochaine_visite = %s, updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
            """, (data['date_prochaine_visite'], data['magasin_id']))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return True, "✅ Visite mise à jour"
    except Exception as e:
        return False, f"❌ Erreur : {str(e)}"

def delete_visite(visite_id):
    """Supprime une visite"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM crm_visites WHERE id = %s", (visite_id,))
        conn.commit()
        cursor.close()
        conn.close()
        return True, "✅ Visite supprimée"
    except Exception as e:
        return False, f"❌ Erreur : {str(e)}"

# ==========================================
# ONGLETS
# ==========================================

tab1, tab2, tab3 = st.tabs(["📅 Planning Semaine", "📋 Liste Visites", "➕ Nouvelle Visite"])

# ==========================================
# TAB 1 : PLANNING SEMAINE
# ==========================================

with tab1:
    st.subheader("📅 Planning Hebdomadaire")
    
    # Navigation semaine
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col1:
        if st.button("◀ Semaine précédente", key="prev_week"):
            if 'planning_date' not in st.session_state:
                st.session_state.planning_date = datetime.now().date()
            st.session_state.planning_date -= timedelta(days=7)
            st.rerun()
    
    with col2:
        if 'planning_date' not in st.session_state:
            st.session_state.planning_date = datetime.now().date()
        
        # Trouver le lundi de la semaine
        lundi = st.session_state.planning_date - timedelta(days=st.session_state.planning_date.weekday())
        dimanche = lundi + timedelta(days=6)
        
        st.markdown(f"### Semaine du {lundi.strftime('%d/%m')} au {dimanche.strftime('%d/%m/%Y')}")
    
    with col3:
        if st.button("Semaine suivante ▶", key="next_week"):
            st.session_state.planning_date += timedelta(days=7)
            st.rerun()
    
    st.markdown("---")
    
    # Charger visites de la semaine
    visites_sem = get_visites_semaine(lundi)
    
    # Afficher par jour
    jours = ['Lundi', 'Mardi', 'Mercredi', 'Jeudi', 'Vendredi', 'Samedi', 'Dimanche']
    
    cols = st.columns(5)  # Lundi à Vendredi
    
    for i, jour in enumerate(jours[:5]):
        date_jour = lundi + timedelta(days=i)
        
        with cols[i]:
            st.markdown(f"**{jour} {date_jour.strftime('%d/%m')}**")
            
            if not visites_sem.empty:
                visites_jour = visites_sem[visites_sem['date_visite'] == date_jour]
                
                if not visites_jour.empty:
                    for _, v in visites_jour.iterrows():
                        statut_class = 'visite-effectuee' if v['statut'] == 'EFFECTUEE' else 'visite-planifiee' if v['statut'] == 'PLANIFIEE' else 'visite-annulee'
                        st.markdown(f"""
                        <div class="{statut_class}">
                            <small><strong>{v['enseigne']}</strong><br>
                            {v['ville']}<br>
                            👤 {v['commercial'] or 'N/A'}<br>
                            📋 {v['type_visite'] or ''}</small>
                        </div>
                        """, unsafe_allow_html=True)
                else:
                    st.caption("Aucune visite")
            else:
                st.caption("Aucune visite")
    
    # Stats semaine
    st.markdown("---")
    if not visites_sem.empty:
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total visites", len(visites_sem))
        with col2:
            effectuees = len(visites_sem[visites_sem['statut'] == 'EFFECTUEE'])
            st.metric("Effectuées", effectuees)
        with col3:
            planifiees = len(visites_sem[visites_sem['statut'] == 'PLANIFIEE'])
            st.metric("Planifiées", planifiees)

# ==========================================
# TAB 2 : LISTE VISITES
# ==========================================

with tab2:
    # Filtres
    magasins = get_magasins_dropdown()
    commerciaux = get_commerciaux()
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        mag_options = [(0, '', 'Tous les magasins')] + magasins
        filtre_magasin = st.selectbox("Magasin", mag_options, format_func=lambda x: x[2], key="f_mag_v")
    
    with col2:
        comm_options = [(0, 'Tous')] + commerciaux
        filtre_commercial = st.selectbox("Commercial", comm_options, format_func=lambda x: x[1], key="f_comm_v")
    
    with col3:
        filtre_statut = st.selectbox("Statut", ['Tous', 'EFFECTUEE', 'PLANIFIEE', 'ANNULEE'], key="f_stat_v")
    
    with col4:
        filtre_periode = st.selectbox("Période", ['30 derniers jours', '7 derniers jours', 'Ce mois', 'Tout'], key="f_periode")
    
    # Calculer dates selon période
    date_debut = None
    date_fin = None
    if filtre_periode == '30 derniers jours':
        date_debut = datetime.now().date() - timedelta(days=30)
    elif filtre_periode == '7 derniers jours':
        date_debut = datetime.now().date() - timedelta(days=7)
    elif filtre_periode == 'Ce mois':
        date_debut = datetime.now().date().replace(day=1)
    
    filtres = {
        'magasin_id': filtre_magasin[0] if filtre_magasin else 0,
        'commercial_id': filtre_commercial[0] if filtre_commercial else 0,
        'statut': filtre_statut,
        'date_debut': date_debut,
        'date_fin': date_fin
    }
    
    st.markdown("---")
    
    df = get_visites(filtres)
    
    if not df.empty:
        st.markdown(f"**{len(df)} visite(s) trouvée(s)**")
        
        display_df = df[['date_visite', 'enseigne', 'ville', 'commercial', 'type_visite', 'statut']].copy()
        display_df['date_visite'] = pd.to_datetime(display_df['date_visite']).dt.strftime('%d/%m/%Y')
        display_df.columns = ['Date', 'Enseigne', 'Ville', 'Commercial', 'Type', 'Statut']
        display_df = display_df.fillna('')
        
        event = st.dataframe(
            display_df,
            use_container_width=True,
            hide_index=True,
            on_select="rerun",
            selection_mode="single-row",
            key="visites_table"
        )
        
        selected_rows = event.selection.rows if hasattr(event, 'selection') else []
        
        if len(selected_rows) > 0:
            idx = selected_rows[0]
            visite = df.iloc[idx]
            
            st.markdown("---")
            
            statut_class = 'visite-effectuee' if visite['statut'] == 'EFFECTUEE' else 'visite-planifiee' if visite['statut'] == 'PLANIFIEE' else 'visite-annulee'
            date_str = visite['date_visite'].strftime('%d/%m/%Y') if visite['date_visite'] else ''
            
            st.markdown(f"""
            <div class="{statut_class}">
                <h4>📋 Visite du {date_str}</h4>
                <p><strong>Magasin :</strong> {visite['enseigne']} - {visite['ville']}</p>
                <p><strong>Commercial :</strong> {visite['commercial'] or 'N/A'}</p>
                <p><strong>Type :</strong> {visite['type_visite'] or '-'} | <strong>Statut :</strong> {visite['statut']}</p>
                <p><strong>Présence produit :</strong> {visite['presence_produit'] or '-'}</p>
            </div>
            """, unsafe_allow_html=True)
            
            if visite['compte_rendu']:
                st.markdown("**Compte-rendu :**")
                st.info(visite['compte_rendu'])
            
            if visite['points_amelioration']:
                st.markdown("**Points d'amélioration :**")
                st.warning(visite['points_amelioration'])
            
            if visite['date_prochaine_visite']:
                proch = visite['date_prochaine_visite'].strftime('%d/%m/%Y') if visite['date_prochaine_visite'] else ''
                st.markdown(f"📅 **Prochaine visite prévue :** {proch}")
            
            # Boutons
            col_a, col_b, col_c = st.columns([1, 1, 2])
            
            with col_a:
                if st.button("✏️ Modifier", key="btn_edit_v"):
                    st.session_state['edit_visite_id'] = visite['id']
                    st.session_state['edit_visite_data'] = visite.to_dict()
                    st.rerun()
            
            with col_b:
                if is_admin():
                    if st.button("🗑️ Supprimer", key="btn_del_v", type="secondary"):
                        st.session_state['confirm_delete_visite'] = visite['id']
                        st.rerun()
            
            # Confirmation suppression
            if st.session_state.get('confirm_delete_visite') == visite['id']:
                st.warning("⚠️ Confirmer la suppression de cette visite ?")
                col_yes, col_no = st.columns(2)
                with col_yes:
                    if st.button("✅ Confirmer", key="confirm_yes_v"):
                        success, msg = delete_visite(visite['id'])
                        if success:
                            st.success(msg)
                            st.session_state.pop('confirm_delete_visite', None)
                            st.rerun()
                        else:
                            st.error(msg)
                with col_no:
                    if st.button("❌ Annuler", key="confirm_no_v"):
                        st.session_state.pop('confirm_delete_visite', None)
                        st.rerun()
        
        # Formulaire modification
        if 'edit_visite_id' in st.session_state:
            st.markdown("---")
            st.subheader("✏️ Modifier la visite")
            
            data = st.session_state['edit_visite_data']
            types_visite = get_types_visite()
            
            col1, col2 = st.columns(2)
            
            with col1:
                mag_list = magasins
                current_mag = next((i for i, m in enumerate(mag_list) if m[0] == data.get('magasin_id')), 0)
                edit_magasin = st.selectbox("Magasin *", mag_list, index=current_mag, format_func=lambda x: x[2], key="edit_mag_v")
                
                comm_list = [(None, 'Non assigné')] + commerciaux
                current_comm = next((i for i, c in enumerate(comm_list) if c[0] == data.get('commercial_id')), 0)
                edit_commercial = st.selectbox("Commercial", comm_list, index=current_comm, format_func=lambda x: x[1], key="edit_comm_v")
                
                edit_date = st.date_input("Date visite *", value=data.get('date_visite') or datetime.now().date(), key="edit_date_v")
                
                type_list = [(None, '', 'Non défini')] + [(t[0], t[1], t[2]) for t in types_visite]
                current_type = next((i for i, t in enumerate(type_list) if t[0] == data.get('type_visite_id')), 0)
                edit_type = st.selectbox("Type visite", type_list, index=current_type, format_func=lambda x: x[2], key="edit_type_v")
            
            with col2:
                edit_statut = st.selectbox("Statut", ['EFFECTUEE', 'PLANIFIEE', 'ANNULEE'], index=['EFFECTUEE', 'PLANIFIEE', 'ANNULEE'].index(data.get('statut', 'EFFECTUEE')), key="edit_stat_v")
                edit_presence = st.selectbox("Présence produit", ['', 'OUI', 'NON', 'PARTIELLE'], index=['', 'OUI', 'NON', 'PARTIELLE'].index(data.get('presence_produit', '') or ''), key="edit_pres_v")
                edit_prochaine = st.date_input("Prochaine visite", value=data.get('date_prochaine_visite'), key="edit_proch_v")
            
            edit_cr = st.text_area("Compte-rendu", value=data.get('compte_rendu', '') or '', height=100, key="edit_cr_v")
            edit_pts = st.text_area("Points d'amélioration", value=data.get('points_amelioration', '') or '', key="edit_pts_v")
            
            col_save, col_cancel = st.columns(2)
            
            with col_save:
                if st.button("💾 Enregistrer", type="primary", key="btn_save_v"):
                    update_data = {
                        'magasin_id': edit_magasin[0],
                        'commercial_id': edit_commercial[0],
                        'date_visite': edit_date,
                        'type_visite_id': edit_type[0],
                        'statut': edit_statut,
                        'presence_produit': edit_presence or None,
                        'compte_rendu': edit_cr or None,
                        'points_amelioration': edit_pts or None,
                        'date_prochaine_visite': edit_prochaine if edit_prochaine else None
                    }
                    success, msg = update_visite(st.session_state['edit_visite_id'], update_data)
                    if success:
                        st.success(msg)
                        st.session_state.pop('edit_visite_id', None)
                        st.session_state.pop('edit_visite_data', None)
                        st.rerun()
                    else:
                        st.error(msg)
            
            with col_cancel:
                if st.button("❌ Annuler", key="btn_cancel_v"):
                    st.session_state.pop('edit_visite_id', None)
                    st.session_state.pop('edit_visite_data', None)
                    st.rerun()
    else:
        st.info("Aucune visite trouvée")

# ==========================================
# TAB 3 : NOUVELLE VISITE
# ==========================================

with tab3:
    st.subheader("➕ Enregistrer une visite")
    
    magasins = get_magasins_dropdown()
    commerciaux = get_commerciaux()
    types_visite = get_types_visite()
    
    if not magasins:
        st.warning("⚠️ Aucun magasin disponible")
    else:
        col1, col2 = st.columns(2)
        
        with col1:
            new_magasin = st.selectbox("Magasin *", magasins, format_func=lambda x: x[2], key="new_mag_v")
            comm_list = [(None, 'Non assigné')] + commerciaux
            new_commercial = st.selectbox("Commercial", comm_list, format_func=lambda x: x[1], key="new_comm_v")
            new_date = st.date_input("Date visite *", value=datetime.now().date(), key="new_date_v")
            type_list = [(None, '', 'Non défini')] + [(t[0], t[1], t[2]) for t in types_visite]
            new_type = st.selectbox("Type visite", type_list, format_func=lambda x: x[2], key="new_type_v")
        
        with col2:
            new_statut = st.selectbox("Statut", ['EFFECTUEE', 'PLANIFIEE'], key="new_stat_v")
            new_presence = st.selectbox("Présence produit", ['', 'OUI', 'NON', 'PARTIELLE'], key="new_pres_v")
            new_prochaine = st.date_input("Prochaine visite prévue", value=None, key="new_proch_v")
        
        new_cr = st.text_area("Compte-rendu", height=100, key="new_cr_v")
        new_pts = st.text_area("Points d'amélioration", key="new_pts_v")
        
        if st.button("✅ Enregistrer la visite", type="primary", key="btn_create_v"):
            data = {
                'magasin_id': new_magasin[0],
                'commercial_id': new_commercial[0],
                'date_visite': new_date,
                'type_visite_id': new_type[0],
                'statut': new_statut,
                'presence_produit': new_presence or None,
                'compte_rendu': new_cr or None,
                'points_amelioration': new_pts or None,
                'date_prochaine_visite': new_prochaine if new_prochaine else None,
                'created_by': st.session_state.get('username', 'system')
            }
            success, msg = create_visite(data)
            if success:
                st.success(msg)
                st.balloons()
            else:
                st.error(msg)

show_footer()
