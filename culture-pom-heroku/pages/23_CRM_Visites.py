import streamlit as st
import pandas as pd
import numpy as np
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
# FONCTIONS HELPER - Conversion types
# ==========================================

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
    if value is None:
        return default
    if isinstance(value, float) and pd.isna(value):
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

def get_types_visite():
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, libelle FROM crm_types_visite ORDER BY libelle")
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
        
        cursor.execute("SELECT COUNT(*) FROM crm_visites WHERE statut = 'PLANIFIEE'")
        kpis['planifiees'] = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM crm_visites WHERE statut = 'EFFECTUEE' AND date_visite >= DATE_TRUNC('month', CURRENT_DATE)")
        kpis['effectuees_mois'] = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM crm_visites WHERE statut = 'PLANIFIEE' AND date_visite BETWEEN CURRENT_DATE AND CURRENT_DATE + INTERVAL '7 days'")
        kpis['semaine'] = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM crm_visites WHERE statut = 'PLANIFIEE' AND date_visite < CURRENT_DATE")
        kpis['retard'] = cursor.fetchone()[0]
        
        cursor.close()
        conn.close()
        
        return kpis
    except:
        return None

def get_mois_disponibles():
    """⭐ V7: Récupère la liste des mois avec des visites"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT DISTINCT 
                DATE_TRUNC('month', date_visite) as mois,
                TO_CHAR(date_visite, 'YYYY-MM') as mois_code,
                TO_CHAR(date_visite, 'Month YYYY') as mois_libelle
            FROM crm_visites
            ORDER BY mois DESC
        """)
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        return [(r['mois_code'], r['mois_libelle'].strip()) for r in rows]
    except:
        return []

def get_visites(filtres=None):
    """Récupère les visites avec filtres"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        query = """
            SELECT 
                v.id, v.date_visite, v.statut,
                m.id as magasin_id, m.nom_client, COALESCE(e.libelle, '') as enseigne, m.ville,
                u.id as commercial_id, COALESCE(u.prenom || ' ' || u.nom, 'Non assigné') as commercial,
                tv.id as type_visite_id, tv.libelle as type_visite,
                v.compte_rendu, v.note_satisfaction, v.prochaine_visite_date, v.actions_suivre
            FROM crm_visites v
            JOIN crm_magasins m ON v.magasin_id = m.id
            LEFT JOIN ref_enseignes e ON m.enseigne_id = e.id
            LEFT JOIN users_app u ON v.commercial_id = u.id
            LEFT JOIN crm_types_visite tv ON v.type_visite_id = tv.id
            WHERE 1=1
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
            # ⭐ V7: Filtre par mois
            if filtres.get('mois') and filtres['mois'] != 'Tous':
                query += " AND TO_CHAR(v.date_visite, 'YYYY-MM') = %s"
                params.append(filtres['mois'])
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
    """Planning avec nom_client"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                v.id, v.date_visite,
                m.nom_client, COALESCE(e.libelle, '') as enseigne, m.ville,
                COALESCE(u.prenom || ' ' || u.nom, 'Non assigné') as commercial,
                tv.libelle as type_visite,
                v.statut
            FROM crm_visites v
            JOIN crm_magasins m ON v.magasin_id = m.id
            LEFT JOIN ref_enseignes e ON m.enseigne_id = e.id
            LEFT JOIN users_app u ON v.commercial_id = u.id
            LEFT JOIN crm_types_visite tv ON v.type_visite_id = tv.id
            WHERE v.date_visite BETWEEN CURRENT_DATE AND CURRENT_DATE + INTERVAL '7 days'
            ORDER BY v.date_visite, m.nom_client
        """)
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        return rows if rows else []
    except Exception as e:
        st.error(f"❌ Erreur : {str(e)}")
        return []

def create_visite(data):
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO crm_visites 
            (magasin_id, commercial_id, type_visite_id, date_visite, statut, 
             compte_rendu, note_satisfaction, prochaine_visite_date, actions_suivre, created_by)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (
            data['magasin_id'], data.get('commercial_id'), data.get('type_visite_id'),
            data['date_visite'], data['statut'],
            data.get('compte_rendu'), data.get('note_satisfaction'),
            data.get('prochaine_visite_date'), data.get('actions_suivre'),
            data.get('created_by', 'system')
        ))
        
        new_id = cursor.fetchone()[0]
        conn.commit()
        cursor.close()
        conn.close()
        
        return True, f"✅ Visite #{new_id} créée"
    except Exception as e:
        if 'conn' in locals():
            conn.rollback()
        return False, f"❌ Erreur : {str(e)}"

def update_visite(visite_id, data):
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE crm_visites SET
                magasin_id = %s, commercial_id = %s, type_visite_id = %s,
                date_visite = %s, statut = %s,
                compte_rendu = %s, note_satisfaction = %s,
                prochaine_visite_date = %s, actions_suivre = %s,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
        """, (
            data['magasin_id'], data.get('commercial_id'), data.get('type_visite_id'),
            data['date_visite'], data['statut'],
            data.get('compte_rendu'), data.get('note_satisfaction'),
            data.get('prochaine_visite_date'), data.get('actions_suivre'),
            visite_id
        ))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return True, "✅ Visite mise à jour"
    except Exception as e:
        if 'conn' in locals():
            conn.rollback()
        return False, f"❌ Erreur : {str(e)}"

def delete_visite(visite_id):
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM crm_visites WHERE id = %s", (visite_id,))
        conn.commit()
        cursor.close()
        conn.close()
        return True, "✅ Visite supprimée"
    except Exception as e:
        if 'conn' in locals():
            conn.rollback()
        return False, f"❌ Erreur : {str(e)}"

# ==========================================
# KPIs
# ==========================================

kpis = get_kpis_visites()

if kpis:
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("📋 Planifiées", kpis['planifiees'])
    with col2:
        st.metric("✅ Effectuées (mois)", kpis['effectuees_mois'])
    with col3:
        st.metric("📅 Cette semaine", kpis['semaine'])
    with col4:
        # ⭐ V7: KPI en retard avec alerte visuelle
        if kpis['retard'] > 0:
            st.metric("⚠️ En retard", kpis['retard'], delta=f"-{kpis['retard']}", delta_color="inverse")
        else:
            st.metric("✅ En retard", 0)

st.markdown("---")

# ==========================================
# ONGLETS
# ==========================================

tab1, tab2, tab3 = st.tabs(["📋 Liste", "📅 Planning", "➕ Nouvelle"])

with tab1:
    st.subheader("📋 Liste des visites")
    
    magasins = get_magasins_dropdown()
    commerciaux = get_commerciaux()
    mois_disponibles = get_mois_disponibles()
    
    # ⭐ V7: FORMULAIRE MODIFICATION AU-DESSUS
    if 'edit_visite_id' in st.session_state and can_edit("CRM"):
        st.markdown("### ✏️ Modifier la visite")
        
        data = st.session_state['edit_visite_data']
        types_visite = get_types_visite()
        
        col1, col2 = st.columns(2)
        
        with col1:
            current_mag = next((i for i, m in enumerate(magasins) if m[0] == data.get('magasin_id')), 0)
            edit_magasin = st.selectbox("Client *", magasins, index=current_mag, format_func=lambda x: x[1], key="edit_mag_v")
            
            comm_list = [(None, 'Non assigné')] + commerciaux
            current_comm = next((i for i, c in enumerate(comm_list) if c[0] == data.get('commercial_id')), 0)
            edit_commercial = st.selectbox("Responsable", comm_list, index=current_comm, format_func=lambda x: x[1], key="edit_comm_v")
            
            type_list = [(None, 'Non défini')] + types_visite
            current_type = next((i for i, t in enumerate(type_list) if t[0] == data.get('type_visite_id')), 0)
            edit_type = st.selectbox("Type visite", type_list, index=current_type, format_func=lambda x: x[1], key="edit_type_v")
        
        with col2:
            edit_date = st.date_input("Date visite *", value=data.get('date_visite') or datetime.now().date(), key="edit_date_v")
            edit_statut = st.selectbox("Statut", ['PLANIFIEE', 'EFFECTUEE', 'ANNULEE'], 
                                      index=['PLANIFIEE', 'EFFECTUEE', 'ANNULEE'].index(data.get('statut', 'PLANIFIEE')), key="edit_stat_v")
            # ⭐ V7: Fix NaN avec safe_int
            edit_note = st.slider("Note", 0, 10, safe_int(data.get('note_satisfaction'), 0), key="edit_note_v")
            edit_prochaine = st.date_input("Prochaine visite", value=data.get('prochaine_visite_date'), key="edit_proch_v")
        
        edit_cr = st.text_area("Compte-rendu", value=safe_str(data.get('compte_rendu'), ''), key="edit_cr_v")
        edit_actions = st.text_area("Actions à suivre", value=safe_str(data.get('actions_suivre'), ''), key="edit_act_v")
        
        col_save, col_cancel = st.columns(2)
        
        with col_save:
            is_saving = st.session_state.get('is_saving_visite', False)
            if st.button("💾 Enregistrer", type="primary", key="btn_save_v", disabled=is_saving):
                st.session_state['is_saving_visite'] = True
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
                    st.session_state.pop('is_saving_visite', None)
                    st.rerun()
                else:
                    st.session_state.pop('is_saving_visite', None)
                    st.error(msg)
        
        with col_cancel:
            if st.button("❌ Annuler", key="btn_cancel_v"):
                st.session_state.pop('edit_visite_id', None)
                st.session_state.pop('edit_visite_data', None)
                st.session_state.pop('is_saving_visite', None)
                st.rerun()
        
        st.markdown("---")
    
    # ⭐ V7: FILTRES avec pagination par mois
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        mag_list = [(0, 'Tous les clients')] + magasins
        filtre_magasin = st.selectbox("Client", mag_list, format_func=lambda x: x[1], key="filtre_mag_v")
    
    with col2:
        comm_list = [(0, 'Tous')] + commerciaux
        filtre_commercial = st.selectbox("Responsable", comm_list, format_func=lambda x: x[1], key="filtre_comm_v")
    
    with col3:
        filtre_statut = st.selectbox("Statut", ['Tous', 'PLANIFIEE', 'EFFECTUEE', 'ANNULEE'], key="filtre_stat_v")
    
    with col4:
        # ⭐ V7: Filtre par mois
        mois_list = [('Tous', 'Tous les mois')] + mois_disponibles
        filtre_mois = st.selectbox("Mois", mois_list, format_func=lambda x: x[1], key="filtre_mois_v")
    
    filtres = {
        'magasin_id': filtre_magasin[0],
        'commercial_id': filtre_commercial[0],
        'statut': filtre_statut,
        'mois': filtre_mois[0]
    }
    
    visites = get_visites(filtres)
    
    if not visites.empty:
        st.markdown(f"**{len(visites)} visite(s) trouvée(s)**")
        
        for _, visite in visites.iterrows():
            # Formatage affichage
            date_str = visite['date_visite'].strftime('%d/%m/%Y') if visite['date_visite'] else ''
            statut_icon = "✅" if visite['statut'] == 'EFFECTUEE' else ("❌" if visite['statut'] == 'ANNULEE' else "📋")
            
            # Affichage client
            client_display = visite['nom_client']
            if visite['enseigne']:
                client_display += f" ({visite['enseigne']})"
            
            with st.expander(f"{statut_icon} {date_str} | {client_display} - {visite['ville']} | {visite['commercial']}"):
                col1, col2, col3 = st.columns([2, 2, 1])
                
                with col1:
                    st.markdown(f"**📅 Date :** {date_str}")
                    st.markdown(f"**🏪 Client :** {client_display}")
                    st.markdown(f"**📍 Ville :** {visite['ville']}")
                
                with col2:
                    st.markdown(f"**👤 Responsable :** {visite['commercial']}")
                    st.markdown(f"**📌 Type :** {visite['type_visite'] or 'Non défini'}")
                    st.markdown(f"**🏷️ Statut :** {visite['statut']}")
                
                with col3:
                    if visite['note_satisfaction']:
                        note = safe_int(visite['note_satisfaction'], 0)
                        stars = "⭐" * min(note, 10)
                        st.markdown(f"**Note :** {note}/10")
                        st.caption(stars)
                
                if visite['compte_rendu']:
                    st.markdown(f"**📝 Compte-rendu :** {visite['compte_rendu']}")
                if visite['actions_suivre']:
                    st.warning(f"🎯 Actions à suivre : {visite['actions_suivre']}")
                if visite['prochaine_visite_date']:
                    proch_str = visite['prochaine_visite_date'].strftime('%d/%m/%Y') if visite['prochaine_visite_date'] else ''
                    st.info(f"📅 Prochaine visite prévue : {proch_str}")
                
                col_a, col_b, col_c = st.columns([1, 1, 2])
                
                with col_a:
                    if can_edit("CRM"):
                        if st.button("✏️ Modifier", key=f"btn_edit_v_{visite['id']}"):
                            st.session_state['edit_visite_id'] = visite['id']
                            st.session_state['edit_visite_data'] = visite.to_dict()
                            st.rerun()
                
                with col_b:
                    if can_delete("CRM"):
                        if st.button("🗑️ Supprimer", key=f"btn_del_v_{visite['id']}", type="secondary"):
                            st.session_state['confirm_delete_visite'] = visite['id']
                            st.rerun()
                
                if st.session_state.get('confirm_delete_visite') == visite['id']:
                    st.warning("⚠️ Confirmer la suppression ?")
                    col_yes, col_no = st.columns(2)
                    with col_yes:
                        if st.button("✅ Confirmer", key=f"confirm_yes_v_{visite['id']}"):
                            success, msg = delete_visite(visite['id'])
                            if success:
                                st.success(msg)
                                st.session_state.pop('confirm_delete_visite', None)
                                st.rerun()
                            else:
                                st.error(msg)
                    with col_no:
                        if st.button("❌ Annuler", key=f"confirm_no_v_{visite['id']}"):
                            st.session_state.pop('confirm_delete_visite', None)
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
                    client_display = v['nom_client']
                    if v['enseigne']:
                        client_display += f" ({v['enseigne']})"
                    st.markdown(f"{statut_icon} **{client_display}** - {v['ville']} | {v['commercial'] or 'N/A'} ({v['type_visite'] or 'N/A'})")
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
            st.warning("⚠️ Aucun client disponible")
        else:
            st.info(f"📋 {len(magasins)} client(s) disponible(s)")
            
            col1, col2 = st.columns(2)
            
            with col1:
                new_magasin = st.selectbox("Client *", magasins, format_func=lambda x: x[1], key="new_mag_v")
                # ⭐ V7: Label "Responsable" au lieu de "Commercial"
                comm_list = [(None, 'Non assigné')] + commerciaux
                new_commercial = st.selectbox("Responsable", comm_list, format_func=lambda x: x[1], key="new_comm_v")
                type_list = [(None, 'Non défini')] + types_visite
                new_type = st.selectbox("Type visite", type_list, format_func=lambda x: x[1], key="new_type_v")
            
            with col2:
                new_date = st.date_input("Date visite *", value=datetime.now().date(), key="new_date_v")
                new_statut = st.selectbox("Statut", ['PLANIFIEE', 'EFFECTUEE'], key="new_stat_v")
                new_note = st.slider("Note", 0, 10, 0, key="new_note_v")
                new_prochaine = st.date_input("Prochaine visite prévue", value=None, key="new_proch_v")
            
            new_cr = st.text_area("Compte-rendu", key="new_cr_v")
            new_actions = st.text_area("Actions à suivre", key="new_act_v")
            
            is_creating = st.session_state.get('is_creating_visite', False)
            
            if st.button("✅ Créer la visite", type="primary", key="btn_create_v", disabled=is_creating):
                st.session_state['is_creating_visite'] = True
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
                    for k in list(st.session_state.keys()):
                        if k.startswith('new_'):
                            st.session_state.pop(k, None)
                    st.session_state.pop('is_creating_visite', None)
                    st.rerun()
                else:
                    st.session_state.pop('is_creating_visite', None)
                    st.error(msg)

show_footer()
