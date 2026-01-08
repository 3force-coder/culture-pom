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
    """⭐ V7: Convertit une valeur en int, gère None et NaN"""
    if value is None:
        return default
    if isinstance(value, float) and (pd.isna(value) or np.isnan(value)):
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
    """Récupère TOUS les clients - Affiche nom_client - ville (enseigne si existante)"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT m.id, m.nom_client || ' - ' || m.ville || COALESCE(' (' || e.libelle || ')', '') as nom 
            FROM crm_magasins m
            LEFT JOIN ref_enseignes e ON m.enseigne_id = e.id
            WHERE m.is_active = TRUE 
            ORDER BY m.nom_client, m.ville
        """)
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        return [(r['id'], r['nom']) for r in rows]
    except Exception as e:
        st.error(f"❌ Erreur get_magasins_dropdown: {str(e)}")
        return []

def get_commerciaux():
    """⭐ V7: Récupère TOUS les users actifs (comme affectation clients)"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        # ⭐ V7.1: COALESCE pour gérer prenom/nom NULL
        cursor.execute("""
            SELECT u.id, 
                   COALESCE(NULLIF(TRIM(COALESCE(u.prenom, '') || ' ' || COALESCE(u.nom, '')), ''), 
                            u.username, 
                            'User #' || u.id::text) as nom 
            FROM users_app u
            WHERE u.is_active = TRUE 
            ORDER BY COALESCE(u.nom, ''), COALESCE(u.prenom, '')
        """)
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        if rows:
            # ⭐ V7.1: Filtrer les None et s'assurer que nom est une string
            return [(r['id'], str(r['nom']) if r['nom'] else f"User #{r['id']}") for r in rows]
        return []
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

def get_mois_disponibles():
    """⭐ V7: Récupère la liste des mois avec des animations"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT DISTINCT 
                DATE_TRUNC('month', date_animation) as mois,
                TO_CHAR(date_animation, 'YYYY-MM') as mois_code,
                TO_CHAR(date_animation, 'Month YYYY') as mois_libelle
            FROM crm_animations
            WHERE is_active = TRUE
            ORDER BY mois DESC
        """)
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        return [(r['mois_code'], r['mois_libelle'].strip()) for r in rows]
    except:
        return []

def get_animations(filtres=None):
    """Récupère les animations avec nom_client comme base"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        query = """
            SELECT 
                a.id, a.date_animation, a.date_fin, a.statut,
                m.id as magasin_id, m.nom_client, COALESCE(e.libelle, '') as enseigne, m.ville,
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
            if filtres.get('statut') and filtres['statut'] != 'Tous':
                query += " AND a.statut = %s"
                params.append(filtres['statut'])
            # ⭐ V7: Filtre par mois
            if filtres.get('mois') and filtres['mois'] != 'Tous':
                query += " AND TO_CHAR(a.date_animation, 'YYYY-MM') = %s"
                params.append(filtres['mois'])
        
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
        
        cursor.execute("""
            INSERT INTO crm_animations 
            (magasin_id, commercial_id, type_animation_id, date_animation, date_fin,
             statut, description, created_by)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (
            data['magasin_id'], data.get('commercial_id'), data.get('type_animation_id'),
            data['date_animation'], data.get('date_fin'),
            data['statut'], data.get('description'),
            data.get('created_by', 'system')
        ))
        
        new_id = cursor.fetchone()[0]
        conn.commit()
        cursor.close()
        conn.close()
        
        return True, f"✅ Animation #{new_id} créée"
    except Exception as e:
        if 'conn' in locals():
            conn.rollback()
        return False, f"❌ Erreur : {str(e)}"

def update_animation(anim_id, data):
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE crm_animations SET
                magasin_id = %s, commercial_id = %s, type_animation_id = %s,
                date_animation = %s, date_fin = %s, statut = %s,
                description = %s, resultats = %s, prochaine_animation_date = %s,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
        """, (
            data['magasin_id'], data.get('commercial_id'), data.get('type_animation_id'),
            data['date_animation'], data.get('date_fin'), data['statut'],
            data.get('description'), data.get('resultats'), data.get('prochaine_animation_date'),
            anim_id
        ))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return True, "✅ Animation mise à jour"
    except Exception as e:
        if 'conn' in locals():
            conn.rollback()
        return False, f"❌ Erreur : {str(e)}"

def delete_animation(anim_id):
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE crm_animations SET is_active = FALSE WHERE id = %s", (anim_id,))
        conn.commit()
        cursor.close()
        conn.close()
        return True, "✅ Animation supprimée"
    except Exception as e:
        if 'conn' in locals():
            conn.rollback()
        return False, f"❌ Erreur : {str(e)}"

# ==========================================
# KPIs
# ==========================================

kpis = get_kpis_animations()

if kpis:
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("📋 Planifiées", kpis['planifiees'])
    with col2:
        st.metric("⚙️ En cours", kpis['en_cours'])
    with col3:
        st.metric("✅ Terminées", kpis['terminees'])
    with col4:
        st.metric("📅 14 prochains jours", kpis['prochaines'])

st.markdown("---")

# ==========================================
# ONGLETS
# ==========================================

tab1, tab2 = st.tabs(["📋 Liste", "➕ Nouvelle"])

with tab1:
    st.subheader("📋 Liste des animations")
    
    magasins = get_magasins_dropdown()
    commerciaux = get_commerciaux()
    types_animation = get_types_animation()
    mois_disponibles = get_mois_disponibles()
    
    # ⭐ V7: FORMULAIRE MODIFICATION AU-DESSUS
    if 'edit_animation_id' in st.session_state and can_edit("CRM"):
        st.markdown("### ✏️ Modifier l'animation")
        
        data = st.session_state['edit_animation_data']
        
        col1, col2 = st.columns(2)
        
        with col1:
            current_mag = next((i for i, m in enumerate(magasins) if m[0] == data.get('magasin_id')), 0)
            edit_magasin = st.selectbox("Client *", magasins, index=current_mag, format_func=lambda x: x[1], key="edit_mag_a")
            
            comm_list = [(None, 'Non assigné')] + commerciaux
            current_comm = next((i for i, c in enumerate(comm_list) if c[0] == data.get('commercial_id')), 0)
            edit_commercial = st.selectbox("Responsable", comm_list, index=current_comm, format_func=lambda x: x[1], key="edit_comm_a")
            
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
            is_saving = st.session_state.get('is_saving_animation', False)
            if st.button("💾 Enregistrer", type="primary", key="btn_save_a", disabled=is_saving):
                st.session_state['is_saving_animation'] = True
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
                    st.session_state.pop('is_saving_animation', None)
                    st.rerun()
                else:
                    st.session_state.pop('is_saving_animation', None)
                    st.error(msg)
        
        with col_cancel:
            if st.button("❌ Annuler", key="btn_cancel_a"):
                st.session_state.pop('edit_animation_id', None)
                st.session_state.pop('edit_animation_data', None)
                st.session_state.pop('is_saving_animation', None)
                st.rerun()
        
        st.markdown("---")
    
    # ⭐ V7: Formulaire "Terminer" AU-DESSUS aussi
    if 'finish_animation_id' in st.session_state and can_edit("CRM"):
        anim = st.session_state['finish_animation_data']
        
        st.markdown("### ✅ Terminer l'animation")
        st.info(f"Animation : {anim.get('nom_client', '')} - {anim.get('date_animation', '')}")
        
        finish_resultats = st.text_area("Résultats de l'animation *", value=safe_str(anim.get('resultats')), key="finish_res_a")
        finish_prochaine = st.date_input("Date prochaine animation", value=None, key="finish_proch_a")
        
        col_save, col_cancel = st.columns(2)
        
        with col_save:
            is_finishing = st.session_state.get('is_finishing_animation', False)
            if st.button("💾 Terminer", type="primary", key="btn_save_finish_a", disabled=is_finishing):
                if not finish_resultats:
                    st.error("❌ Résultats obligatoires")
                else:
                    st.session_state['is_finishing_animation'] = True
                    update_data = anim
                    update_data['statut'] = 'TERMINEE'
                    update_data['resultats'] = finish_resultats
                    if finish_prochaine:
                        update_data['prochaine_animation_date'] = finish_prochaine
                    success, msg = update_animation(st.session_state['finish_animation_id'], update_data)
                    if success:
                        st.success("✅ Animation terminée")
                        st.session_state.pop('finish_animation_id', None)
                        st.session_state.pop('finish_animation_data', None)
                        st.session_state.pop('is_finishing_animation', None)
                        st.balloons()
                        st.rerun()
                    else:
                        st.session_state.pop('is_finishing_animation', None)
                        st.error(msg)
        
        with col_cancel:
            if st.button("❌ Annuler", key="btn_cancel_finish_a"):
                st.session_state.pop('finish_animation_id', None)
                st.session_state.pop('finish_animation_data', None)
                st.session_state.pop('is_finishing_animation', None)
                st.rerun()
        
        st.markdown("---")
    
    # ⭐ V7: FILTRES avec pagination par mois
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        mag_list = [(0, 'Tous les clients')] + magasins
        filtre_magasin = st.selectbox("Client", mag_list, format_func=lambda x: x[1], key="filtre_mag_a")
    
    with col2:
        comm_list = [(0, 'Tous')] + commerciaux
        filtre_commercial = st.selectbox("Responsable", comm_list, format_func=lambda x: x[1], key="filtre_comm_a")
    
    with col3:
        filtre_statut = st.selectbox("Statut", ['Tous', 'PLANIFIEE', 'EN_COURS', 'TERMINEE', 'ANNULEE'], key="filtre_stat_a")
    
    with col4:
        # ⭐ V7: Filtre par mois
        mois_list = [('Tous', 'Tous les mois')] + mois_disponibles
        filtre_mois = st.selectbox("Mois", mois_list, format_func=lambda x: x[1], key="filtre_mois_a")
    
    filtres = {
        'magasin_id': filtre_magasin[0],
        'commercial_id': filtre_commercial[0],
        'statut': filtre_statut,
        'mois': filtre_mois[0]
    }
    
    animations = get_animations(filtres)
    
    if not animations.empty:
        st.markdown(f"**{len(animations)} animation(s) trouvée(s)**")
        
        for _, anim in animations.iterrows():
            date_str = anim['date_animation'].strftime('%d/%m/%Y') if anim['date_animation'] else ''
            date_fin_str = f" → {anim['date_fin'].strftime('%d/%m/%Y')}" if anim['date_fin'] else ''
            
            statut_icon = "✅" if anim['statut'] == 'TERMINEE' else (
                "⚙️" if anim['statut'] == 'EN_COURS' else (
                    "❌" if anim['statut'] == 'ANNULEE' else "📋"
                )
            )
            
            # Affichage client
            client_display = anim['nom_client']
            if anim['enseigne']:
                client_display += f" ({anim['enseigne']})"
            
            with st.expander(f"{statut_icon} {date_str}{date_fin_str} | {client_display} - {anim['ville']} | {anim['commercial']}"):
                col1, col2 = st.columns(2)
                
                with col1:
                    st.markdown(f"**📅 Période :** {date_str}{date_fin_str}")
                    st.markdown(f"**🏪 Client :** {client_display}")
                    st.markdown(f"**📍 Ville :** {anim['ville']}")
                
                with col2:
                    st.markdown(f"**👤 Responsable :** {anim['commercial']}")
                    st.markdown(f"**📌 Type :** {anim['type_animation'] or 'Non défini'}")
                    st.markdown(f"**🏷️ Statut :** {anim['statut']}")
                
                if anim['description']:
                    st.markdown(f"**📝 Description :** {anim['description']}")
                if anim['resultats']:
                    st.success(f"📊 Résultats : {anim['resultats']}")
                if anim['prochaine_animation_date']:
                    proch_str = anim['prochaine_animation_date'].strftime('%d/%m/%Y')
                    st.info(f"📅 Prochaine animation : {proch_str}")
                
                col_a, col_b, col_c, col_d = st.columns([1, 1, 1, 1])
                
                with col_a:
                    if can_edit("CRM"):
                        if st.button("✏️ Modifier", key=f"btn_edit_a_{anim['id']}"):
                            st.session_state['edit_animation_id'] = anim['id']
                            st.session_state['edit_animation_data'] = anim.to_dict()
                            st.rerun()
                
                with col_b:
                    if can_edit("CRM") and anim['statut'] == 'EN_COURS':
                        if st.button("✅ Terminer", key=f"btn_finish_a_{anim['id']}"):
                            st.session_state['finish_animation_id'] = anim['id']
                            st.session_state['finish_animation_data'] = anim.to_dict()
                            st.rerun()
                
                with col_c:
                    if can_edit("CRM") and anim['statut'] == 'PLANIFIEE':
                        if st.button("▶️ Démarrer", key=f"btn_start_a_{anim['id']}"):
                            update_data = anim.to_dict()
                            update_data['statut'] = 'EN_COURS'
                            success, msg = update_animation(anim['id'], update_data)
                            if success:
                                st.success("✅ Animation démarrée")
                                st.rerun()
                            else:
                                st.error(msg)
                
                with col_d:
                    if can_delete("CRM"):
                        if st.button("🗑️ Supprimer", key=f"btn_del_a_{anim['id']}", type="secondary"):
                            st.session_state['confirm_delete_anim'] = anim['id']
                            st.rerun()
                
                if st.session_state.get('confirm_delete_anim') == anim['id']:
                    st.warning("⚠️ Confirmer la suppression ?")
                    col_yes, col_no = st.columns(2)
                    with col_yes:
                        if st.button("✅ Confirmer", key=f"confirm_yes_a_{anim['id']}"):
                            success, msg = delete_animation(anim['id'])
                            if success:
                                st.success(msg)
                                st.session_state.pop('confirm_delete_anim', None)
                                st.rerun()
                            else:
                                st.error(msg)
                    with col_no:
                        if st.button("❌ Annuler", key=f"confirm_no_a_{anim['id']}"):
                            st.session_state.pop('confirm_delete_anim', None)
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
            st.warning("⚠️ Aucun client disponible")
        else:
            st.info(f"📋 {len(magasins)} client(s) disponible(s)")
            
            col1, col2 = st.columns(2)
            
            with col1:
                new_magasin = st.selectbox("Client *", magasins, format_func=lambda x: x[1], key="new_mag_a")
                # ⭐ V7: Label "Responsable" au lieu de "Commercial"
                comm_list = [(None, 'Non assigné')] + commerciaux
                new_commercial = st.selectbox("Responsable", comm_list, format_func=lambda x: x[1], key="new_comm_a")
                type_list = [(None, 'Non défini')] + types_animation
                new_type = st.selectbox("Type animation", type_list, format_func=lambda x: x[1], key="new_type_a")
            
            with col2:
                new_date = st.date_input("Date début *", value=datetime.now().date(), key="new_date_a")
                new_date_fin = st.date_input("Date fin", value=None, key="new_datefin_a")
                new_statut = st.selectbox("Statut", ['PLANIFIEE', 'EN_COURS'], key="new_stat_a")
            
            new_desc = st.text_area("Description", key="new_desc_a")
            
            is_creating = st.session_state.get('is_creating_animation', False)
            
            if st.button("✅ Créer l'animation", type="primary", key="btn_create_a", disabled=is_creating):
                st.session_state['is_creating_animation'] = True
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
                    for k in list(st.session_state.keys()):
                        if k.startswith('new_'):
                            st.session_state.pop(k, None)
                    st.session_state.pop('is_creating_animation', None)
                    st.rerun()
                else:
                    st.session_state.pop('is_creating_animation', None)
                    st.error(msg)

show_footer()
