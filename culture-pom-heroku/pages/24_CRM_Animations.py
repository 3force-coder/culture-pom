import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from database import get_connection
from components import show_footer
from auth import is_authenticated, require_access, can_edit, can_delete

st.set_page_config(page_title="CRM Animations - Culture Pom", page_icon="🎉", layout="wide")

if not is_authenticated():
    st.warning("⚠️ Veuillez vous connecter")
    st.stop()

require_access("CRM")

st.markdown("""
<style>
    .block-container { padding-top: 1.5rem !important; padding-bottom: 0.5rem !important; }
    h1, h2, h3, h4 { margin-top: 0.3rem !important; margin-bottom: 0.3rem !important; }
    .anim-planifiee { background-color: #e3f2fd; border-left: 4px solid #2196f3; padding: 0.8rem; border-radius: 4px; }
    .anim-encours { background-color: #fff3e0; border-left: 4px solid #ff9800; padding: 0.8rem; border-radius: 4px; }
    .anim-terminee { background-color: #e8f5e9; border-left: 4px solid #4caf50; padding: 0.8rem; border-radius: 4px; }
    .anim-annulee { background-color: #ffebee; border-left: 4px solid #f44336; padding: 0.8rem; border-radius: 4px; }
</style>
""", unsafe_allow_html=True)

st.title("🎉 CRM - Gestion des Animations")
st.markdown("---")

# ==========================================
# FONCTIONS HELPER - Conversion types
# ==========================================

def convert_to_native(value):
    """Convertit numpy/pandas types en types Python natifs pour psycopg2"""
    if value is None:
        return None
    if pd.isna(value):
        return None
    if isinstance(value, (np.integer, np.int64, np.int32)):
        return int(value)
    if isinstance(value, (np.floating, np.float64, np.float32)):
        return float(value)
    if isinstance(value, np.bool_):
        return bool(value)
    return value

def safe_int(value, default=0):
    """Convertit une valeur en int, gère None et NaN"""
    if value is None or pd.isna(value):
        return default
    try:
        return int(value)
    except (ValueError, TypeError):
        return default

def safe_str(value, default=''):
    """Convertit une valeur en str, gère None et NaN"""
    if value is None or pd.isna(value):
        return default
    return str(value)

# ==========================================
# FONCTIONS
# ==========================================

def get_magasins_dropdown():
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT m.id, COALESCE(e.libelle, m.nom_client) || ' - ' || m.ville as nom 
            FROM crm_magasins m
            LEFT JOIN ref_enseignes e ON m.enseigne_id = e.id
            WHERE m.is_active = TRUE 
            ORDER BY e.libelle, m.ville
        """)
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        return [(r['id'], r['nom']) for r in rows]
    except Exception as e:
        st.error(f"❌ Erreur get_magasins_dropdown: {str(e)}")
        return []

def get_commerciaux():
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, prenom || ' ' || nom as nom 
            FROM users_app 
            WHERE is_active = TRUE AND role IN ('COMMERCIAL', 'ADMIN', 'SUPER_ADMIN')
            ORDER BY nom
        """)
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        return [(r['id'], r['nom']) for r in rows]
    except Exception as e:
        st.error(f"❌ Erreur get_commerciaux: {str(e)}")
        return []

def get_types_animation():
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, libelle FROM crm_types_animation WHERE is_active = TRUE ORDER BY libelle")
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        return [(r['id'], r['libelle']) for r in rows]
    except:
        return []

def get_kpis_animations():
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        kpis = {}
        
        # ✅ CORRECTION: Utiliser alias 'as nb' et accès dict
        cursor.execute("SELECT COUNT(*) as nb FROM crm_animations WHERE is_active = TRUE AND statut = 'PLANIFIEE'")
        kpis['planifiees'] = cursor.fetchone()['nb']
        
        cursor.execute("SELECT COUNT(*) as nb FROM crm_animations WHERE is_active = TRUE AND statut = 'EN_COURS'")
        kpis['en_cours'] = cursor.fetchone()['nb']
        
        cursor.execute("SELECT COUNT(*) as nb FROM crm_animations WHERE is_active = TRUE AND statut = 'TERMINEE'")
        kpis['terminees'] = cursor.fetchone()['nb']
        
        cursor.execute("""
            SELECT COUNT(*) as nb FROM crm_animations 
            WHERE is_active = TRUE AND statut = 'PLANIFIEE'
            AND date_animation BETWEEN CURRENT_DATE AND CURRENT_DATE + INTERVAL '14 days'
        """)
        kpis['prochaines'] = cursor.fetchone()['nb']
        
        cursor.close()
        conn.close()
        
        return kpis
    except Exception as e:
        st.error(f"Erreur KPIs: {e}")
        return None

def get_animations(filtres=None):
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        query = """
            SELECT 
                a.id, a.date_animation, a.date_fin, a.statut,
                m.id as magasin_id, COALESCE(e.libelle, m.nom_client) as enseigne, m.ville,
                u.id as commercial_id, COALESCE(u.prenom || ' ' || u.nom, 'Non assigné') as commercial,
                ta.id as type_animation_id, ta.libelle as type_animation,
                a.description, a.resultats, a.prochaine_animation_date
            FROM crm_animations a
            JOIN crm_magasins m ON a.magasin_id = m.id
            LEFT JOIN ref_enseignes e ON m.enseigne_id = e.id
            LEFT JOIN users_app u ON a.commercial_id = u.id
            LEFT JOIN crm_types_animation ta ON a.type_animation_id = ta.id
            WHERE a.is_active = TRUE
        """
        params = []
        
        if filtres:
            if filtres.get('magasin_id') and filtres['magasin_id'] != 0:
                query += " AND a.magasin_id = %s"
                params.append(filtres['magasin_id'])
            if filtres.get('commercial_id') and filtres['commercial_id'] != 0:
                query += " AND a.commercial_id = %s"
                params.append(filtres['commercial_id'])
            if filtres.get('type_animation_id') and filtres['type_animation_id'] != 0:
                query += " AND a.type_animation_id = %s"
                params.append(filtres['type_animation_id'])
            if filtres.get('statut') and filtres['statut'] != 'Tous':
                query += " AND a.statut = %s"
                params.append(filtres['statut'])
        
        query += " ORDER BY a.date_animation DESC"
        
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

def create_animation(data):
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # ✅ CORRECTION: Convertir tous les types numpy
        cursor.execute("""
            INSERT INTO crm_animations (
                magasin_id, commercial_id, type_animation_id, date_animation, date_fin,
                statut, description, resultats, prochaine_animation_date, created_by
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (
            convert_to_native(data['magasin_id']),
            convert_to_native(data.get('commercial_id')),
            convert_to_native(data.get('type_animation_id')),
            data['date_animation'],
            data.get('date_fin'),
            data.get('statut', 'PLANIFIEE'),
            data.get('description'),
            data.get('resultats'),
            data.get('prochaine_animation_date'),
            data.get('created_by')
        ))
        
        anim_id = cursor.fetchone()['id']
        conn.commit()
        cursor.close()
        conn.close()
        
        return True, f"✅ Animation #{anim_id} créée"
    except Exception as e:
        return False, f"❌ Erreur : {str(e)}"

def update_animation(anim_id, data):
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # ✅ CORRECTION: Convertir tous les types numpy avant UPDATE
        cursor.execute("""
            UPDATE crm_animations SET
                magasin_id = %s, commercial_id = %s, type_animation_id = %s,
                date_animation = %s, date_fin = %s, statut = %s,
                description = %s, resultats = %s, prochaine_animation_date = %s,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
        """, (
            convert_to_native(data['magasin_id']),
            convert_to_native(data.get('commercial_id')),
            convert_to_native(data.get('type_animation_id')),
            data.get('date_animation'),
            data.get('date_fin'),
            data.get('statut'),
            data.get('description'),
            data.get('resultats'),
            data.get('prochaine_animation_date'),
            convert_to_native(anim_id)
        ))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return True, "✅ Animation mise à jour"
    except Exception as e:
        return False, f"❌ Erreur : {str(e)}"

def delete_animation(anim_id):
    try:
        conn = get_connection()
        cursor = conn.cursor()
        # ✅ CORRECTION: Convertir anim_id
        cursor.execute("UPDATE crm_animations SET is_active = FALSE, updated_at = CURRENT_TIMESTAMP WHERE id = %s", (convert_to_native(anim_id),))
        conn.commit()
        cursor.close()
        conn.close()
        return True, "✅ Animation supprimée"
    except Exception as e:
        return False, f"❌ Erreur : {str(e)}"

# ==========================================
# INTERFACE
# ==========================================

# KPIs
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
        st.metric("⏰ Dans 14 jours", kpis['prochaines'])
else:
    st.warning("⚠️ Impossible de charger les KPIs")

st.markdown("---")

tab1, tab2 = st.tabs(["📋 Liste Animations", "➕ Nouvelle Animation"])

with tab1:
    # Filtres
    magasins = get_magasins_dropdown()
    commerciaux = get_commerciaux()
    types_animation = get_types_animation()
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        mag_opts = [(0, 'Tous')] + magasins
        filtre_mag = st.selectbox("Magasin", mag_opts, format_func=lambda x: x[1], key="f_mag")
    with col2:
        comm_opts = [(0, 'Tous')] + commerciaux
        filtre_comm = st.selectbox("Commercial", comm_opts, format_func=lambda x: x[1], key="f_comm")
    with col3:
        type_opts = [(0, 'Tous')] + types_animation
        filtre_type = st.selectbox("Type animation", type_opts, format_func=lambda x: x[1], key="f_type")
    with col4:
        filtre_statut = st.selectbox("Statut", ['Tous', 'PLANIFIEE', 'EN_COURS', 'TERMINEE', 'ANNULEE'], key="f_stat")
    
    st.markdown("---")
    
    # Charger animations
    filtres = {
        'magasin_id': filtre_mag[0],
        'commercial_id': filtre_comm[0],
        'type_animation_id': filtre_type[0],
        'statut': filtre_statut
    }
    
    df = get_animations(filtres)
    
    if not df.empty:
        st.info(f"📊 {len(df)} animation(s) trouvée(s)")
        
        for _, anim in df.iterrows():
            statut = safe_str(anim.get('statut'), 'PLANIFIEE')
            if statut == 'PLANIFIEE':
                statut_class = "anim-planifiee"
                statut_icon = "📅"
            elif statut == 'EN_COURS':
                statut_class = "anim-encours"
                statut_icon = "▶️"
            elif statut == 'TERMINEE':
                statut_class = "anim-terminee"
                statut_icon = "✅"
            else:
                statut_class = "anim-annulee"
                statut_icon = "❌"
            
            date_str = anim['date_animation'].strftime('%d/%m/%Y') if anim.get('date_animation') else 'N/A'
            
            with st.expander(f"{statut_icon} {date_str} - {safe_str(anim.get('enseigne'))} {safe_str(anim.get('ville'))} - {safe_str(anim.get('type_animation'), 'N/A')}"):
                st.markdown(f"""<div class="{statut_class}">
                    <strong>Magasin</strong> : {safe_str(anim.get('enseigne'))} - {safe_str(anim.get('ville'))}<br>
                    <strong>Commercial</strong> : {safe_str(anim.get('commercial'), 'Non assigné')}<br>
                    <strong>Type</strong> : {safe_str(anim.get('type_animation'), 'Non défini')}<br>
                    <strong>Date</strong> : {date_str}{' au ' + anim['date_fin'].strftime('%d/%m/%Y') if anim.get('date_fin') else ''}<br>
                    <strong>Statut</strong> : {statut}
                </div>""", unsafe_allow_html=True)
                
                if anim.get('description'):
                    st.markdown(f"**Description** : {anim['description']}")
                if anim.get('resultats'):
                    st.markdown(f"**Résultats** : {anim['resultats']}")
                if anim.get('prochaine_animation_date'):
                    proch_date = anim['prochaine_animation_date']
                    if hasattr(proch_date, 'strftime'):
                        st.markdown(f"**Prochaine animation** : {proch_date.strftime('%d/%m/%Y')}")
                
                # Actions
                col_actions = st.columns(4)
                
                with col_actions[0]:
                    if can_edit("CRM") and statut == 'PLANIFIEE':
                        if st.button("▶️ Démarrer", key=f"start_{anim['id']}"):
                            update_data = anim.to_dict()
                            update_data['statut'] = 'EN_COURS'
                            success, msg = update_animation(anim['id'], update_data)
                            if success:
                                st.success("✅ Animation démarrée")
                                st.rerun()
                            else:
                                st.error(msg)
                
                with col_actions[1]:
                    if can_edit("CRM") and statut == 'EN_COURS':
                        if st.button("✅ Terminer", key=f"finish_{anim['id']}"):
                            st.session_state['finish_animation_id'] = anim['id']
                            st.session_state['finish_animation_data'] = anim.to_dict()
                            st.rerun()
                
                with col_actions[2]:
                    if can_edit("CRM"):
                        if st.button("✏️ Modifier", key=f"edit_{anim['id']}"):
                            st.session_state['edit_animation_id'] = anim['id']
                            st.session_state['edit_animation_data'] = anim.to_dict()
                            st.rerun()
                
                with col_actions[3]:
                    if can_delete("CRM"):
                        if st.button("🗑️ Supprimer", key=f"del_{anim['id']}", type="secondary"):
                            st.session_state['confirm_delete_animation'] = anim['id']
                            st.rerun()
                
                # Confirmation suppression
                if st.session_state.get('confirm_delete_animation') == anim['id']:
                    st.warning("⚠️ Confirmer la suppression ?")
                    col_yes, col_no = st.columns(2)
                    with col_yes:
                        if st.button("✅ Confirmer", key="confirm_yes_a"):
                            success, msg = delete_animation(anim['id'])
                            if success:
                                st.success(msg)
                                st.session_state.pop('confirm_delete_animation', None)
                                st.rerun()
                            else:
                                st.error(msg)
                    with col_no:
                        if st.button("❌ Annuler", key="confirm_no_a"):
                            st.session_state.pop('confirm_delete_animation', None)
                            st.rerun()
                
                # Formulaire terminaison
                if st.session_state.get('finish_animation_id') == anim['id'] and can_edit("CRM"):
                    st.markdown("---")
                    st.subheader("✅ Terminer l'animation")
                    
                    finish_resultats = st.text_area("Résultats de l'animation *", key="finish_res_a")
                    finish_prochaine = st.date_input("Date prochaine animation", value=None, key="finish_proch_a")
                    
                    col_save, col_cancel = st.columns(2)
                    
                    with col_save:
                        if st.button("💾 Enregistrer", type="primary", key="btn_save_finish_a"):
                            if not finish_resultats:
                                st.error("❌ Résultats obligatoires")
                            else:
                                update_data = anim.to_dict()
                                update_data['statut'] = 'TERMINEE'
                                update_data['resultats'] = finish_resultats
                                if finish_prochaine:
                                    update_data['prochaine_animation_date'] = finish_prochaine
                                success, msg = update_animation(anim['id'], update_data)
                                if success:
                                    st.success("✅ Animation terminée")
                                    st.session_state.pop('finish_animation_id', None)
                                    st.session_state.pop('finish_animation_data', None)
                                    st.balloons()
                                    st.rerun()
                                else:
                                    st.error(msg)
                    
                    with col_cancel:
                        if st.button("❌ Annuler", key="btn_cancel_finish_a"):
                            st.session_state.pop('finish_animation_id', None)
                            st.session_state.pop('finish_animation_data', None)
                            st.rerun()
        
        # Formulaire modification
        if 'edit_animation_id' in st.session_state and can_edit("CRM"):
            st.markdown("---")
            st.subheader("✏️ Modifier l'animation")
            
            data = st.session_state['edit_animation_data']
            
            col1, col2 = st.columns(2)
            
            with col1:
                current_mag = next((i for i, m in enumerate(magasins) if m[0] == data.get('magasin_id')), 0)
                edit_magasin = st.selectbox("Magasin *", magasins, index=current_mag, format_func=lambda x: x[1], key="edit_mag_a")
                
                comm_list = [(None, 'Non assigné')] + commerciaux
                current_comm = next((i for i, c in enumerate(comm_list) if c[0] == data.get('commercial_id')), 0)
                edit_commercial = st.selectbox("Commercial", comm_list, index=current_comm, format_func=lambda x: x[1], key="edit_comm_a")
                
                type_list = [(None, 'Non défini')] + types_animation
                current_type = next((i for i, t in enumerate(type_list) if t[0] == data.get('type_animation_id')), 0)
                edit_type = st.selectbox("Type animation", type_list, index=current_type, format_func=lambda x: x[1], key="edit_type_a")
            
            with col2:
                edit_date = st.date_input("Date début *", value=data.get('date_animation') or datetime.now().date(), key="edit_date_a")
                edit_date_fin = st.date_input("Date fin", value=data.get('date_fin'), key="edit_datefin_a")
                
                statut_options = ['PLANIFIEE', 'EN_COURS', 'TERMINEE', 'ANNULEE']
                current_statut = safe_str(data.get('statut'), 'PLANIFIEE')
                if current_statut not in statut_options:
                    current_statut = 'PLANIFIEE'
                edit_statut = st.selectbox("Statut", statut_options, 
                                          index=statut_options.index(current_statut), key="edit_stat_a")
            
            edit_desc = st.text_area("Description", value=safe_str(data.get('description')), key="edit_desc_a")
            edit_resultats = st.text_area("Résultats", value=safe_str(data.get('resultats')), key="edit_res_a")
            edit_prochaine = st.date_input("Prochaine animation", value=data.get('prochaine_animation_date'), key="edit_proch_a")
            
            col_save, col_cancel = st.columns(2)
            
            with col_save:
                if st.button("💾 Enregistrer", type="primary", key="btn_save_a"):
                    update_data = {
                        'magasin_id': edit_magasin[0],
                        'commercial_id': edit_commercial[0] if edit_commercial else None,
                        'type_animation_id': edit_type[0] if edit_type else None,
                        'date_animation': edit_date,
                        'date_fin': edit_date_fin if edit_date_fin else None,
                        'statut': edit_statut,
                        'description': edit_desc or None,
                        'resultats': edit_resultats or None,
                        'prochaine_animation_date': edit_prochaine if edit_prochaine else None
                    }
                    success, msg = update_animation(st.session_state['edit_animation_id'], update_data)
                    if success:
                        st.success(msg)
                        st.session_state.pop('edit_animation_id', None)
                        st.session_state.pop('edit_animation_data', None)
                        st.rerun()
                    else:
                        st.error(msg)
            
            with col_cancel:
                if st.button("❌ Annuler", key="btn_cancel_a"):
                    st.session_state.pop('edit_animation_id', None)
                    st.session_state.pop('edit_animation_data', None)
                    st.rerun()
    else:
        st.info("Aucune animation trouvée")

with tab2:
    if not can_edit("CRM"):
        st.warning("⚠️ Vous n'avez pas les droits pour créer une animation")
    else:
        st.subheader("➕ Créer une animation")
        
        magasins = get_magasins_dropdown()
        commerciaux = get_commerciaux()
        types_animation = get_types_animation()
        
        if not magasins:
            st.warning("⚠️ Aucun magasin disponible")
        else:
            col1, col2 = st.columns(2)
            
            with col1:
                new_magasin = st.selectbox("Magasin *", magasins, format_func=lambda x: x[1], key="new_mag_a")
                comm_list = [(None, 'Non assigné')] + commerciaux
                new_commercial = st.selectbox("Commercial", comm_list, format_func=lambda x: x[1], key="new_comm_a")
                type_list = [(None, 'Non défini')] + types_animation
                new_type = st.selectbox("Type animation", type_list, format_func=lambda x: x[1], key="new_type_a")
            
            with col2:
                new_date = st.date_input("Date début *", value=datetime.now().date(), key="new_date_a")
                new_date_fin = st.date_input("Date fin", value=None, key="new_datefin_a")
                new_statut = st.selectbox("Statut", ['PLANIFIEE', 'EN_COURS'], key="new_stat_a")
            
            new_desc = st.text_area("Description", key="new_desc_a")
            
            if st.button("✅ Créer l'animation", type="primary", key="btn_create_a"):
                data = {
                    'magasin_id': new_magasin[0],
                    'commercial_id': new_commercial[0] if new_commercial else None,
                    'type_animation_id': new_type[0] if new_type else None,
                    'date_animation': new_date,
                    'date_fin': new_date_fin if new_date_fin else None,
                    'statut': new_statut,
                    'description': new_desc or None,
                    'created_by': st.session_state.get('username', 'system')
                }
                success, msg = create_animation(data)
                if success:
                    st.success(msg)
                    st.balloons()
                else:
                    st.error(msg)

show_footer()
