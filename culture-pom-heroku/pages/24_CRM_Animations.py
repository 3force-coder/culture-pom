import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from database import get_connection
from components import show_footer
from auth import is_authenticated
from roles import is_admin

st.set_page_config(page_title="CRM Animations - Culture Pom", page_icon="🎉", layout="wide")

st.markdown("""
<style>
    .block-container { padding-top: 1.5rem !important; padding-bottom: 0.5rem !important; }
    h1, h2, h3, h4 { margin-top: 0.3rem !important; margin-bottom: 0.3rem !important; }
    .anim-planifiee { background-color: #e3f2fd; border-left: 4px solid #2196f3; padding: 0.8rem; border-radius: 4px; margin: 0.3rem 0; }
    .anim-en-cours { background-color: #fff3e0; border-left: 4px solid #ff9800; padding: 0.8rem; border-radius: 4px; margin: 0.3rem 0; }
    .anim-terminee { background-color: #e8f5e9; border-left: 4px solid #4caf50; padding: 0.8rem; border-radius: 4px; margin: 0.3rem 0; }
    .anim-annulee { background-color: #ffebee; border-left: 4px solid #f44336; padding: 0.8rem; border-radius: 4px; margin: 0.3rem 0; }
</style>
""", unsafe_allow_html=True)

if not is_authenticated():
    st.warning("⚠️ Veuillez vous connecter")
    st.stop()

st.title("🎉 CRM - Animations Commerciales")
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

def get_types_animation():
    """Liste des types d'animation"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, code, libelle FROM crm_types_animation WHERE is_active = TRUE ORDER BY libelle")
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        return [(r[0], r[1], r[2]) for r in rows]
    except:
        return []

def get_animations(filtres=None):
    """Récupère les animations avec filtres"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        query = """
            SELECT 
                a.id, a.magasin_id, m.code_magasin, m.enseigne, m.ville,
                a.commercial_id, c.prenom || ' ' || c.nom as commercial,
                a.type_animation_id, ta.libelle as type_animation,
                a.date_animation, a.date_fin, a.description, a.resultats,
                a.prochaine_date, a.statut, a.created_by, a.created_at
            FROM crm_animations a
            JOIN crm_magasins m ON a.magasin_id = m.id
            LEFT JOIN crm_commerciaux c ON a.commercial_id = c.id
            LEFT JOIN crm_types_animation ta ON a.type_animation_id = ta.id
            WHERE a.is_active = TRUE AND m.is_active = TRUE
        """
        params = []
        
        if filtres:
            if filtres.get('magasin_id') and filtres['magasin_id'] != 0:
                query += " AND a.magasin_id = %s"
                params.append(filtres['magasin_id'])
            if filtres.get('commercial_id') and filtres['commercial_id'] != 0:
                query += " AND a.commercial_id = %s"
                params.append(filtres['commercial_id'])
            if filtres.get('type_id') and filtres['type_id'] != 0:
                query += " AND a.type_animation_id = %s"
                params.append(filtres['type_id'])
            if filtres.get('statut') and filtres['statut'] != 'Tous':
                query += " AND a.statut = %s"
                params.append(filtres['statut'])
        
        query += " ORDER BY a.date_animation DESC, a.created_at DESC"
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        
        if rows:
            return pd.DataFrame(rows, columns=[
                'id', 'magasin_id', 'code_magasin', 'enseigne', 'ville',
                'commercial_id', 'commercial', 'type_animation_id', 'type_animation',
                'date_animation', 'date_fin', 'description', 'resultats',
                'prochaine_date', 'statut', 'created_by', 'created_at'
            ])
        return pd.DataFrame()
    except Exception as e:
        st.error(f"❌ Erreur : {str(e)}")
        return pd.DataFrame()

def get_kpis_animations():
    """KPIs des animations"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        kpis = {}
        
        cursor.execute("SELECT COUNT(*) FROM crm_animations WHERE is_active = TRUE AND statut = 'PLANIFIEE'")
        kpis['planifiees'] = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM crm_animations WHERE is_active = TRUE AND statut = 'EN_COURS'")
        kpis['en_cours'] = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM crm_animations WHERE is_active = TRUE AND statut = 'TERMINEE'")
        kpis['terminees'] = cursor.fetchone()[0]
        
        cursor.execute("""
            SELECT COUNT(*) FROM crm_animations 
            WHERE is_active = TRUE AND statut = 'PLANIFIEE'
            AND date_animation BETWEEN CURRENT_DATE AND CURRENT_DATE + INTERVAL '14 days'
        """)
        kpis['prochaines_14j'] = cursor.fetchone()[0]
        
        cursor.close()
        conn.close()
        
        return kpis
    except:
        return None

def create_animation(data):
    """Crée une nouvelle animation"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO crm_animations (
                magasin_id, commercial_id, type_animation_id,
                date_animation, date_fin, description, resultats,
                prochaine_date, statut, created_by
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (
            data['magasin_id'], data.get('commercial_id'), data.get('type_animation_id'),
            data.get('date_animation'), data.get('date_fin'), data.get('description'),
            data.get('resultats'), data.get('prochaine_date'),
            data.get('statut', 'PLANIFIEE'), data.get('created_by')
        ))
        
        anim_id = cursor.fetchone()[0]
        conn.commit()
        cursor.close()
        conn.close()
        
        return True, f"✅ Animation #{anim_id} créée"
    except Exception as e:
        return False, f"❌ Erreur : {str(e)}"

def update_animation(anim_id, data):
    """Met à jour une animation"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE crm_animations SET
                magasin_id = %s, commercial_id = %s, type_animation_id = %s,
                date_animation = %s, date_fin = %s, description = %s,
                resultats = %s, prochaine_date = %s, statut = %s,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
        """, (
            data['magasin_id'], data.get('commercial_id'), data.get('type_animation_id'),
            data.get('date_animation'), data.get('date_fin'), data.get('description'),
            data.get('resultats'), data.get('prochaine_date'), data.get('statut'),
            anim_id
        ))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return True, "✅ Animation mise à jour"
    except Exception as e:
        return False, f"❌ Erreur : {str(e)}"

def delete_animation(anim_id):
    """Supprime (désactive) une animation"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE crm_animations SET is_active = FALSE, updated_at = CURRENT_TIMESTAMP WHERE id = %s", (anim_id,))
        conn.commit()
        cursor.close()
        conn.close()
        return True, "✅ Animation supprimée"
    except Exception as e:
        return False, f"❌ Erreur : {str(e)}"

# ==========================================
# KPIs
# ==========================================

kpis = get_kpis_animations()

if kpis:
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("📅 Planifiées", kpis['planifiees'])
    with col2:
        st.metric("▶️ En cours", kpis['en_cours'])
    with col3:
        st.metric("✅ Terminées", kpis['terminees'])
    with col4:
        st.metric("⚠️ Dans 14 jours", kpis['prochaines_14j'])

st.markdown("---")

# ==========================================
# ONGLETS
# ==========================================

tab1, tab2 = st.tabs(["📋 Liste Animations", "➕ Nouvelle Animation"])

# ==========================================
# TAB 1 : LISTE
# ==========================================

with tab1:
    # Filtres
    magasins = get_magasins_dropdown()
    commerciaux = get_commerciaux()
    types_anim = get_types_animation()
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        mag_options = [(0, '', 'Tous les magasins')] + magasins
        filtre_magasin = st.selectbox("Magasin", mag_options, format_func=lambda x: x[2], key="f_mag_a")
    
    with col2:
        comm_options = [(0, 'Tous')] + commerciaux
        filtre_commercial = st.selectbox("Commercial", comm_options, format_func=lambda x: x[1], key="f_comm_a")
    
    with col3:
        type_options = [(0, '', 'Tous les types')] + [(t[0], t[1], t[2]) for t in types_anim]
        filtre_type = st.selectbox("Type", type_options, format_func=lambda x: x[2], key="f_type_a")
    
    with col4:
        filtre_statut = st.selectbox("Statut", ['Tous', 'PLANIFIEE', 'EN_COURS', 'TERMINEE', 'ANNULEE'], key="f_stat_a")
    
    filtres = {
        'magasin_id': filtre_magasin[0] if filtre_magasin else 0,
        'commercial_id': filtre_commercial[0] if filtre_commercial else 0,
        'type_id': filtre_type[0] if filtre_type else 0,
        'statut': filtre_statut
    }
    
    st.markdown("---")
    
    df = get_animations(filtres)
    
    if not df.empty:
        st.markdown(f"**{len(df)} animation(s) trouvée(s)**")
        
        display_df = df[['date_animation', 'enseigne', 'ville', 'commercial', 'type_animation', 'statut']].copy()
        display_df['date_animation'] = pd.to_datetime(display_df['date_animation']).dt.strftime('%d/%m/%Y')
        display_df.columns = ['Date', 'Enseigne', 'Ville', 'Commercial', 'Type', 'Statut']
        display_df = display_df.fillna('')
        
        event = st.dataframe(
            display_df,
            use_container_width=True,
            hide_index=True,
            on_select="rerun",
            selection_mode="single-row",
            key="animations_table"
        )
        
        selected_rows = event.selection.rows if hasattr(event, 'selection') else []
        
        if len(selected_rows) > 0:
            idx = selected_rows[0]
            anim = df.iloc[idx]
            
            st.markdown("---")
            
            statut_class = {
                'PLANIFIEE': 'anim-planifiee',
                'EN_COURS': 'anim-en-cours',
                'TERMINEE': 'anim-terminee',
                'ANNULEE': 'anim-annulee'
            }.get(anim['statut'], 'anim-planifiee')
            
            date_str = anim['date_animation'].strftime('%d/%m/%Y') if anim['date_animation'] else ''
            date_fin_str = anim['date_fin'].strftime('%d/%m/%Y') if anim['date_fin'] else ''
            
            st.markdown(f"""
            <div class="{statut_class}">
                <h4>🎉 {anim['type_animation'] or 'Animation'} - {date_str}</h4>
                <p><strong>Magasin :</strong> {anim['enseigne']} - {anim['ville']}</p>
                <p><strong>Commercial :</strong> {anim['commercial'] or 'N/A'}</p>
                <p><strong>Statut :</strong> {anim['statut']}</p>
                {f"<p><strong>Date fin :</strong> {date_fin_str}</p>" if date_fin_str else ""}
            </div>
            """, unsafe_allow_html=True)
            
            if anim['description']:
                st.markdown("**Description :**")
                st.info(anim['description'])
            
            if anim['resultats']:
                st.markdown("**Résultats :**")
                st.success(anim['resultats'])
            
            if anim['prochaine_date']:
                proch = anim['prochaine_date'].strftime('%d/%m/%Y') if anim['prochaine_date'] else ''
                st.markdown(f"📅 **Prochaine animation prévue :** {proch}")
            
            # Boutons
            col_a, col_b, col_c, col_d = st.columns([1, 1, 1, 1])
            
            with col_a:
                if st.button("✏️ Modifier", key="btn_edit_a"):
                    st.session_state['edit_anim_id'] = anim['id']
                    st.session_state['edit_anim_data'] = anim.to_dict()
                    st.rerun()
            
            with col_b:
                if anim['statut'] == 'PLANIFIEE':
                    if st.button("▶️ Démarrer", key="btn_start_a"):
                        success, msg = update_animation(anim['id'], {**anim.to_dict(), 'statut': 'EN_COURS'})
                        if success:
                            st.success("Animation démarrée")
                            st.rerun()
            
            with col_c:
                if anim['statut'] == 'EN_COURS':
                    if st.button("✅ Terminer", key="btn_finish_a"):
                        st.session_state['finish_anim_id'] = anim['id']
                        st.session_state['finish_anim_data'] = anim.to_dict()
                        st.rerun()
            
            with col_d:
                if is_admin():
                    if st.button("🗑️ Supprimer", key="btn_del_a", type="secondary"):
                        st.session_state['confirm_delete_anim'] = anim['id']
                        st.rerun()
            
            # Formulaire terminer animation
            if st.session_state.get('finish_anim_id') == anim['id']:
                st.markdown("---")
                st.subheader("✅ Terminer l'animation")
                
                finish_resultats = st.text_area("Résultats de l'animation *", key="finish_res")
                finish_prochaine = st.date_input("Prochaine animation prévue", value=None, key="finish_proch")
                
                col_save, col_cancel = st.columns(2)
                with col_save:
                    if st.button("💾 Valider", type="primary", key="btn_finish_save"):
                        update_data = {**anim.to_dict(), 'statut': 'TERMINEE', 'resultats': finish_resultats, 'prochaine_date': finish_prochaine}
                        success, msg = update_animation(anim['id'], update_data)
                        if success:
                            st.success("Animation terminée")
                            st.session_state.pop('finish_anim_id', None)
                            st.session_state.pop('finish_anim_data', None)
                            st.rerun()
                with col_cancel:
                    if st.button("❌ Annuler", key="btn_finish_cancel"):
                        st.session_state.pop('finish_anim_id', None)
                        st.session_state.pop('finish_anim_data', None)
                        st.rerun()
            
            # Confirmation suppression
            if st.session_state.get('confirm_delete_anim') == anim['id']:
                st.warning("⚠️ Confirmer la suppression de cette animation ?")
                col_yes, col_no = st.columns(2)
                with col_yes:
                    if st.button("✅ Confirmer", key="confirm_yes_a"):
                        success, msg = delete_animation(anim['id'])
                        if success:
                            st.success(msg)
                            st.session_state.pop('confirm_delete_anim', None)
                            st.rerun()
                        else:
                            st.error(msg)
                with col_no:
                    if st.button("❌ Annuler", key="confirm_no_a"):
                        st.session_state.pop('confirm_delete_anim', None)
                        st.rerun()
        
        # Formulaire modification
        if 'edit_anim_id' in st.session_state:
            st.markdown("---")
            st.subheader("✏️ Modifier l'animation")
            
            data = st.session_state['edit_anim_data']
            
            col1, col2 = st.columns(2)
            
            with col1:
                mag_list = magasins
                current_mag = next((i for i, m in enumerate(mag_list) if m[0] == data.get('magasin_id')), 0)
                edit_magasin = st.selectbox("Magasin *", mag_list, index=current_mag, format_func=lambda x: x[2], key="edit_mag_a")
                
                comm_list = [(None, 'Non assigné')] + commerciaux
                current_comm = next((i for i, c in enumerate(comm_list) if c[0] == data.get('commercial_id')), 0)
                edit_commercial = st.selectbox("Commercial", comm_list, index=current_comm, format_func=lambda x: x[1], key="edit_comm_a")
                
                type_list = [(None, '', 'Non défini')] + [(t[0], t[1], t[2]) for t in types_anim]
                current_type = next((i for i, t in enumerate(type_list) if t[0] == data.get('type_animation_id')), 0)
                edit_type = st.selectbox("Type animation", type_list, index=current_type, format_func=lambda x: x[2], key="edit_type_a")
            
            with col2:
                edit_date = st.date_input("Date début", value=data.get('date_animation') or datetime.now().date(), key="edit_date_a")
                edit_date_fin = st.date_input("Date fin", value=data.get('date_fin'), key="edit_fin_a")
                edit_statut = st.selectbox("Statut", ['PLANIFIEE', 'EN_COURS', 'TERMINEE', 'ANNULEE'], index=['PLANIFIEE', 'EN_COURS', 'TERMINEE', 'ANNULEE'].index(data.get('statut', 'PLANIFIEE')), key="edit_stat_a")
            
            edit_desc = st.text_area("Description", value=data.get('description', '') or '', key="edit_desc_a")
            edit_res = st.text_area("Résultats", value=data.get('resultats', '') or '', key="edit_res_a")
            edit_proch = st.date_input("Prochaine animation", value=data.get('prochaine_date'), key="edit_proch_a")
            
            col_save, col_cancel = st.columns(2)
            
            with col_save:
                if st.button("💾 Enregistrer", type="primary", key="btn_save_a"):
                    update_data = {
                        'magasin_id': edit_magasin[0],
                        'commercial_id': edit_commercial[0],
                        'type_animation_id': edit_type[0],
                        'date_animation': edit_date,
                        'date_fin': edit_date_fin if edit_date_fin else None,
                        'description': edit_desc or None,
                        'resultats': edit_res or None,
                        'prochaine_date': edit_proch if edit_proch else None,
                        'statut': edit_statut
                    }
                    success, msg = update_animation(st.session_state['edit_anim_id'], update_data)
                    if success:
                        st.success(msg)
                        st.session_state.pop('edit_anim_id', None)
                        st.session_state.pop('edit_anim_data', None)
                        st.rerun()
                    else:
                        st.error(msg)
            
            with col_cancel:
                if st.button("❌ Annuler", key="btn_cancel_a"):
                    st.session_state.pop('edit_anim_id', None)
                    st.session_state.pop('edit_anim_data', None)
                    st.rerun()
    else:
        st.info("Aucune animation trouvée")

# ==========================================
# TAB 2 : NOUVELLE ANIMATION
# ==========================================

with tab2:
    st.subheader("➕ Planifier une animation")
    
    magasins = get_magasins_dropdown()
    commerciaux = get_commerciaux()
    types_anim = get_types_animation()
    
    if not magasins:
        st.warning("⚠️ Aucun magasin disponible")
    else:
        col1, col2 = st.columns(2)
        
        with col1:
            new_magasin = st.selectbox("Magasin *", magasins, format_func=lambda x: x[2], key="new_mag_a")
            comm_list = [(None, 'Non assigné')] + commerciaux
            new_commercial = st.selectbox("Commercial", comm_list, format_func=lambda x: x[1], key="new_comm_a")
            type_list = [(None, '', 'Non défini')] + [(t[0], t[1], t[2]) for t in types_anim]
            new_type = st.selectbox("Type animation", type_list, format_func=lambda x: x[2], key="new_type_a")
        
        with col2:
            new_date = st.date_input("Date début *", value=datetime.now().date(), key="new_date_a")
            new_date_fin = st.date_input("Date fin", value=None, key="new_fin_a")
            new_statut = st.selectbox("Statut", ['PLANIFIEE', 'EN_COURS'], key="new_stat_a")
        
        new_desc = st.text_area("Description", key="new_desc_a")
        
        if st.button("✅ Créer l'animation", type="primary", key="btn_create_a"):
            if not new_date:
                st.error("❌ La date est obligatoire")
            else:
                data = {
                    'magasin_id': new_magasin[0],
                    'commercial_id': new_commercial[0],
                    'type_animation_id': new_type[0],
                    'date_animation': new_date,
                    'date_fin': new_date_fin if new_date_fin else None,
                    'description': new_desc or None,
                    'statut': new_statut,
                    'created_by': st.session_state.get('username', 'system')
                }
                success, msg = create_animation(data)
                if success:
                    st.success(msg)
                    st.balloons()
                else:
                    st.error(msg)

show_footer()
