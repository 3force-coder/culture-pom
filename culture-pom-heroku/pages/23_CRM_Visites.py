import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from database import get_connection
from components import show_footer
from auth import is_authenticated, require_access, can_edit, can_delete

st.set_page_config(page_title="CRM Visites - Culture Pom", page_icon="📅", layout="wide")

if not is_authenticated():
    st.warning("⚠️ Veuillez vous connecter")
    st.stop()

require_access("CRM")

st.markdown("""
<style>
    .block-container { padding-top: 1.5rem !important; padding-bottom: 0.5rem !important; }
    h1, h2, h3, h4 { margin-top: 0.3rem !important; margin-bottom: 0.3rem !important; }
    .visite-planifiee { background-color: #e3f2fd; border-left: 4px solid #2196f3; padding: 0.5rem; margin: 0.3rem 0; border-radius: 4px; }
    .visite-effectuee { background-color: #e8f5e9; border-left: 4px solid #4caf50; padding: 0.5rem; margin: 0.3rem 0; border-radius: 4px; }
    .visite-annulee { background-color: #ffebee; border-left: 4px solid #f44336; padding: 0.5rem; margin: 0.3rem 0; border-radius: 4px; }
</style>
""", unsafe_allow_html=True)

st.title("📅 CRM - Gestion des Visites")
st.markdown("---")

# ==========================================
# FONCTIONS
# ==========================================

def get_magasins_dropdown():
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, enseigne || ' - ' || ville as nom FROM crm_magasins WHERE is_active = TRUE ORDER BY enseigne, ville")
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        return [(r['id'], r['nom']) for r in rows]
    except:
        return []

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

def get_types_visite():
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, libelle FROM crm_types_visite WHERE is_active = TRUE ORDER BY libelle")
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        return [(r['id'], r['libelle']) for r in rows]
    except:
        return []

def get_kpis_visites():
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        kpis = {}
        
        cursor.execute("SELECT COUNT(*) FROM crm_visites WHERE is_active = TRUE AND statut = 'PLANIFIEE'")
        kpis['planifiees'] = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM crm_visites WHERE is_active = TRUE AND statut = 'EFFECTUEE' AND date_visite >= DATE_TRUNC('month', CURRENT_DATE)")
        kpis['effectuees_mois'] = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM crm_visites WHERE is_active = TRUE AND statut = 'PLANIFIEE' AND date_visite BETWEEN CURRENT_DATE AND CURRENT_DATE + INTERVAL '7 days'")
        kpis['semaine'] = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM crm_visites WHERE is_active = TRUE AND statut = 'PLANIFIEE' AND date_visite < CURRENT_DATE")
        kpis['retard'] = cursor.fetchone()[0]
        
        cursor.close()
        conn.close()
        
        return kpis
    except:
        return None

def get_visites(filtres=None):
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # CORRECTION: note_visite → note_satisfaction, prochaine_visite → prochaine_visite_date
        query = """
            SELECT 
                v.id, v.date_visite, v.statut,
                m.id as magasin_id, m.enseigne, m.ville,
                c.id as commercial_id, c.prenom || ' ' || c.nom as commercial,
                tv.id as type_visite_id, tv.libelle as type_visite,
                v.compte_rendu, v.note_satisfaction, v.prochaine_visite_date, v.actions_suivre
            FROM crm_visites v
            JOIN crm_magasins m ON v.magasin_id = m.id
            LEFT JOIN crm_commerciaux c ON v.commercial_id = c.id
            LEFT JOIN crm_types_visite tv ON v.type_visite_id = tv.id
            WHERE v.is_active = TRUE
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
        
        query += " ORDER BY v.date_visite DESC"
        
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

def get_planning_semaine():
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                v.id, v.date_visite,
                m.enseigne, m.ville,
                c.prenom || ' ' || c.nom as commercial,
                tv.libelle as type_visite,
                v.statut
            FROM crm_visites v
            JOIN crm_magasins m ON v.magasin_id = m.id
            LEFT JOIN crm_commerciaux c ON v.commercial_id = c.id
            LEFT JOIN crm_types_visite tv ON v.type_visite_id = tv.id
            WHERE v.is_active = TRUE
            AND v.date_visite BETWEEN CURRENT_DATE AND CURRENT_DATE + INTERVAL '7 days'
            ORDER BY v.date_visite, c.nom
        """)
        
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        
        return rows if rows else []
    except:
        return []

def create_visite(data):
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # CORRECTION: note_visite → note_satisfaction, prochaine_visite → prochaine_visite_date
        cursor.execute("""
            INSERT INTO crm_visites (
                magasin_id, commercial_id, type_visite_id, date_visite,
                statut, compte_rendu, note_satisfaction, prochaine_visite_date, actions_suivre, created_by
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (
            data['magasin_id'], data.get('commercial_id'), data.get('type_visite_id'),
            data['date_visite'], data.get('statut', 'PLANIFIEE'),
            data.get('compte_rendu'), data.get('note_satisfaction'), data.get('prochaine_visite_date'),
            data.get('actions_suivre'), data.get('created_by')
        ))
        
        visite_id = cursor.fetchone()['id']
        conn.commit()
        cursor.close()
        conn.close()
        
        return True, f"✅ Visite #{visite_id} créée"
    except Exception as e:
        return False, f"❌ Erreur : {str(e)}"

def update_visite(visite_id, data):
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # CORRECTION: note_visite → note_satisfaction, prochaine_visite → prochaine_visite_date
        cursor.execute("""
            UPDATE crm_visites SET
                magasin_id = %s, commercial_id = %s, type_visite_id = %s,
                date_visite = %s, statut = %s, compte_rendu = %s,
                note_satisfaction = %s, prochaine_visite_date = %s, actions_suivre = %s,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
        """, (
            data['magasin_id'], data.get('commercial_id'), data.get('type_visite_id'),
            data['date_visite'], data['statut'], data.get('compte_rendu'),
            data.get('note_satisfaction'), data.get('prochaine_visite_date'), data.get('actions_suivre'),
            visite_id
        ))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return True, "✅ Visite mise à jour"
    except Exception as e:
        return False, f"❌ Erreur : {str(e)}"

def delete_visite(visite_id):
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE crm_visites SET is_active = FALSE, updated_at = CURRENT_TIMESTAMP WHERE id = %s", (visite_id,))
        conn.commit()
        cursor.close()
        conn.close()
        return True, "✅ Visite supprimée"
    except Exception as e:
        return False, f"❌ Erreur : {str(e)}"

# ==========================================
# INTERFACE
# ==========================================

# KPIs
kpis = get_kpis_visites()
if kpis:
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("📋 Planifiées", kpis['planifiees'])
    with col2:
        st.metric("✅ Ce mois", kpis['effectuees_mois'])
    with col3:
        st.metric("📅 Cette semaine", kpis['semaine'])
    with col4:
        delta_color = "inverse" if kpis['retard'] > 0 else "off"
        st.metric("⚠️ En retard", kpis['retard'], delta_color=delta_color)

st.markdown("---")

tab1, tab2, tab3 = st.tabs(["📋 Liste Visites", "📅 Planning Semaine", "➕ Nouvelle Visite"])

with tab1:
    # Filtres
    magasins = get_magasins_dropdown()
    commerciaux = get_commerciaux()
    
    col1, col2, col3, col4, col5 = st.columns(5)
    
    with col1:
        mag_opts = [(0, 'Tous')] + magasins
        filtre_mag = st.selectbox("Magasin", mag_opts, format_func=lambda x: x[1], key="f_mag")
    with col2:
        comm_opts = [(0, 'Tous')] + commerciaux
        filtre_comm = st.selectbox("Commercial", comm_opts, format_func=lambda x: x[1], key="f_comm")
    with col3:
        filtre_statut = st.selectbox("Statut", ['Tous', 'PLANIFIEE', 'EFFECTUEE', 'ANNULEE'], key="f_stat")
    with col4:
        filtre_date_debut = st.date_input("Du", value=datetime.now().date() - timedelta(days=30), key="f_dd")
    with col5:
        filtre_date_fin = st.date_input("Au", value=datetime.now().date() + timedelta(days=30), key="f_df")
    
    st.markdown("---")
    
    # Charger visites
    filtres = {
        'magasin_id': filtre_mag[0],
        'commercial_id': filtre_comm[0],
        'statut': filtre_statut,
        'date_debut': filtre_date_debut,
        'date_fin': filtre_date_fin
    }
    
    df = get_visites(filtres)
    
    if not df.empty:
        st.info(f"📊 {len(df)} visite(s) trouvée(s)")
        
        # Tableau sélection
        df_display = df[['id', 'date_visite', 'enseigne', 'ville', 'commercial', 'type_visite', 'statut']].copy()
        df_display['date_visite'] = pd.to_datetime(df_display['date_visite']).dt.strftime('%d/%m/%Y')
        df_display.columns = ['ID', 'Date', 'Enseigne', 'Ville', 'Commercial', 'Type', 'Statut']
        
        event = st.dataframe(
            df_display,
            use_container_width=True,
            hide_index=True,
            on_select="rerun",
            selection_mode="single-row",
            key="table_visites"
        )
        
        # Détail visite sélectionnée
        selected_rows = event.selection.rows if hasattr(event, 'selection') else []
        
        if selected_rows:
            idx = selected_rows[0]
            visite = df.iloc[idx]
            
            st.markdown("---")
            
            statut_class = "visite-planifiee" if visite['statut'] == 'PLANIFIEE' else ("visite-effectuee" if visite['statut'] == 'EFFECTUEE' else "visite-annulee")
            statut = "📋 Planifiée" if visite['statut'] == 'PLANIFIEE' else ("✅ Effectuée" if visite['statut'] == 'EFFECTUEE' else "❌ Annulée")
            date_str = visite['date_visite'].strftime('%d/%m/%Y') if visite['date_visite'] else ''
            
            st.markdown(f"""
            <div class="{statut_class}">
                <h4>📅 {date_str} - {visite['enseigne']} ({visite['ville']})</h4>
                <p><strong>Commercial :</strong> {visite['commercial'] or 'N/A'} | <strong>Type :</strong> {visite['type_visite'] or 'N/A'} | <strong>Statut :</strong> {statut}</p>
            </div>
            """, unsafe_allow_html=True)
            
            if visite['compte_rendu']:
                st.markdown(f"**📝 Compte-rendu :** {visite['compte_rendu']}")
            if visite['note_satisfaction']:
                st.markdown(f"**⭐ Note :** {visite['note_satisfaction']}/10")
            if visite['actions_suivre']:
                st.warning(f"🎯 Actions à suivre : {visite['actions_suivre']}")
            if visite['prochaine_visite_date']:
                proch_str = visite['prochaine_visite_date'].strftime('%d/%m/%Y') if visite['prochaine_visite_date'] else ''
                st.info(f"📅 Prochaine visite prévue : {proch_str}")
            
            col_a, col_b, col_c = st.columns([1, 1, 2])
            
            with col_a:
                if can_edit("CRM"):
                    if st.button("✏️ Modifier", key="btn_edit_v"):
                        st.session_state['edit_visite_id'] = visite['id']
                        st.session_state['edit_visite_data'] = visite.to_dict()
                        st.rerun()
            
            with col_b:
                if can_delete("CRM"):
                    if st.button("🗑️ Supprimer", key="btn_del_v", type="secondary"):
                        st.session_state['confirm_delete_visite'] = visite['id']
                        st.rerun()
            
            if st.session_state.get('confirm_delete_visite') == visite['id']:
                st.warning("⚠️ Confirmer la suppression ?")
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
        if 'edit_visite_id' in st.session_state and can_edit("CRM"):
            st.markdown("---")
            st.subheader("✏️ Modifier la visite")
            
            data = st.session_state['edit_visite_data']
            types_visite = get_types_visite()
            
            col1, col2 = st.columns(2)
            
            with col1:
                current_mag = next((i for i, m in enumerate(magasins) if m[0] == data.get('magasin_id')), 0)
                edit_magasin = st.selectbox("Magasin *", magasins, index=current_mag, format_func=lambda x: x[1], key="edit_mag_v")
                
                comm_list = [(None, 'Non assigné')] + commerciaux
                current_comm = next((i for i, c in enumerate(comm_list) if c[0] == data.get('commercial_id')), 0)
                edit_commercial = st.selectbox("Commercial", comm_list, index=current_comm, format_func=lambda x: x[1], key="edit_comm_v")
                
                type_list = [(None, 'Non défini')] + types_visite
                current_type = next((i for i, t in enumerate(type_list) if t[0] == data.get('type_visite_id')), 0)
                edit_type = st.selectbox("Type visite", type_list, index=current_type, format_func=lambda x: x[1], key="edit_type_v")
            
            with col2:
                edit_date = st.date_input("Date visite *", value=data.get('date_visite') or datetime.now().date(), key="edit_date_v")
                edit_statut = st.selectbox("Statut", ['PLANIFIEE', 'EFFECTUEE', 'ANNULEE'], 
                                          index=['PLANIFIEE', 'EFFECTUEE', 'ANNULEE'].index(data.get('statut', 'PLANIFIEE')), key="edit_stat_v")
                edit_note = st.slider("Note", 0, 10, int(data.get('note_satisfaction') or 0), key="edit_note_v")
                edit_prochaine = st.date_input("Prochaine visite", value=data.get('prochaine_visite_date'), key="edit_proch_v")
            
            edit_cr = st.text_area("Compte-rendu", value=data.get('compte_rendu', '') or '', key="edit_cr_v")
            edit_actions = st.text_area("Actions à suivre", value=data.get('actions_suivre', '') or '', key="edit_act_v")
            
            col_save, col_cancel = st.columns(2)
            
            with col_save:
                if st.button("💾 Enregistrer", type="primary", key="btn_save_v"):
                    update_data = {
                        'magasin_id': edit_magasin[0],
                        'commercial_id': edit_commercial[0] if edit_commercial else None,
                        'type_visite_id': edit_type[0] if edit_type else None,
                        'date_visite': edit_date, 'statut': edit_statut,
                        'compte_rendu': edit_cr or None, 'note_satisfaction': edit_note if edit_note > 0 else None,
                        'prochaine_visite_date': edit_prochaine if edit_prochaine else None,
                        'actions_suivre': edit_actions or None
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

with tab2:
    st.subheader("📅 Planning des 7 prochains jours")
    
    planning = get_planning_semaine()
    
    if planning:
        # Grouper par jour
        jours = {}
        for v in planning:
            jour = v['date_visite'].strftime('%A %d/%m/%Y')
            if jour not in jours:
                jours[jour] = []
            jours[jour].append(v)
        
        for jour, visites in jours.items():
            with st.expander(f"📅 {jour} ({len(visites)} visite(s))", expanded=True):
                for v in visites:
                    statut_icon = "✅" if v['statut'] == 'EFFECTUEE' else ("❌" if v['statut'] == 'ANNULEE' else "📋")
                    st.markdown(f"{statut_icon} **{v['enseigne']}** - {v['ville']} | {v['commercial'] or 'N/A'} ({v['type_visite'] or 'N/A'})")
    else:
        st.info("Aucune visite planifiée cette semaine")

with tab3:
    if not can_edit("CRM"):
        st.warning("⚠️ Vous n'avez pas les droits pour créer une visite")
    else:
        st.subheader("➕ Créer une visite")
        
        magasins = get_magasins_dropdown()
        commerciaux = get_commerciaux()
        types_visite = get_types_visite()
        
        if not magasins:
            st.warning("⚠️ Aucun magasin disponible")
        else:
            col1, col2 = st.columns(2)
            
            with col1:
                new_magasin = st.selectbox("Magasin *", magasins, format_func=lambda x: x[1], key="new_mag_v")
                comm_list = [(None, 'Non assigné')] + commerciaux
                new_commercial = st.selectbox("Commercial", comm_list, format_func=lambda x: x[1], key="new_comm_v")
                type_list = [(None, 'Non défini')] + types_visite
                new_type = st.selectbox("Type visite", type_list, format_func=lambda x: x[1], key="new_type_v")
            
            with col2:
                new_date = st.date_input("Date visite *", value=datetime.now().date(), key="new_date_v")
                new_statut = st.selectbox("Statut", ['PLANIFIEE', 'EFFECTUEE'], key="new_stat_v")
                new_note = st.slider("Note", 0, 10, 0, key="new_note_v")
                new_prochaine = st.date_input("Prochaine visite prévue", value=None, key="new_proch_v")
            
            new_cr = st.text_area("Compte-rendu", key="new_cr_v")
            new_actions = st.text_area("Actions à suivre", key="new_act_v")
            
            if st.button("✅ Créer la visite", type="primary", key="btn_create_v"):
                data = {
                    'magasin_id': new_magasin[0],
                    'commercial_id': new_commercial[0] if new_commercial else None,
                    'type_visite_id': new_type[0] if new_type else None,
                    'date_visite': new_date, 'statut': new_statut,
                    'compte_rendu': new_cr or None, 'note_satisfaction': new_note if new_note > 0 else None,
                    'prochaine_visite_date': new_prochaine if new_prochaine else None,
                    'actions_suivre': new_actions or None,
                    'created_by': st.session_state.get('username', 'system')
                }
                success, msg = create_visite(data)
                if success:
                    st.success(msg)
                    st.balloons()
                else:
                    st.error(msg)

show_footer()
