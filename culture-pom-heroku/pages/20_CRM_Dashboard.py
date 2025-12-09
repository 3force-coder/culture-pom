import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from database import get_connection
from components import show_footer
from auth import is_authenticated, require_access, can_edit

st.set_page_config(page_title="CRM Dashboard - Culture Pom", page_icon="📊", layout="wide")

# Vérification authentification + permissions
if not is_authenticated():
    st.warning("⚠️ Veuillez vous connecter")
    st.stop()

require_access("CRM")

st.markdown("""
<style>
    .block-container { padding-top: 1.5rem !important; padding-bottom: 0.5rem !important; }
    h1, h2, h3, h4 { margin-top: 0.3rem !important; margin-bottom: 0.3rem !important; }
    .kpi-card { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 1rem; border-radius: 10px; text-align: center; }
    .kpi-card h2 { color: white !important; margin: 0 !important; }
    .alert-rouge { background-color: #ffebee; border-left: 4px solid #f44336; padding: 0.5rem; margin: 0.3rem 0; border-radius: 4px; }
    .alert-orange { background-color: #fff3e0; border-left: 4px solid #ff9800; padding: 0.5rem; margin: 0.3rem 0; border-radius: 4px; }
    .alert-jaune { background-color: #fffde7; border-left: 4px solid #ffeb3b; padding: 0.5rem; margin: 0.3rem 0; border-radius: 4px; }
</style>
""", unsafe_allow_html=True)

st.title("📊 CRM - Tableau de Bord")
st.markdown("---")

# ==========================================
# FONCTIONS
# ==========================================

def get_kpis_globaux():
    """KPIs globaux CRM"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        kpis = {}
        
        # Total magasins actifs
        cursor.execute("SELECT COUNT(*) FROM crm_magasins WHERE is_active = TRUE")
        kpis['total_magasins'] = cursor.fetchone()[0]
        
        # Magasins statut ACTIF
        cursor.execute("SELECT COUNT(*) FROM crm_magasins WHERE is_active = TRUE AND statut = 'ACTIF'")
        kpis['magasins_actifs'] = cursor.fetchone()[0]
        
        # Visites ce mois
        cursor.execute("""
            SELECT COUNT(*) FROM crm_visites 
            WHERE is_active = TRUE AND statut = 'EFFECTUEE'
            AND date_visite >= DATE_TRUNC('month', CURRENT_DATE)
        """)
        kpis['visites_mois'] = cursor.fetchone()[0]
        
        # Taux couverture 30 jours
        cursor.execute("""
            SELECT COUNT(*) FROM crm_magasins 
            WHERE is_active = TRUE AND statut = 'ACTIF'
            AND date_derniere_visite >= CURRENT_DATE - INTERVAL '30 days'
        """)
        couverts = cursor.fetchone()[0]
        kpis['taux_couverture'] = round((couverts / kpis['magasins_actifs'] * 100), 1) if kpis['magasins_actifs'] > 0 else 0
        
        # Animations planifiées
        cursor.execute("SELECT COUNT(*) FROM crm_animations WHERE is_active = TRUE AND statut = 'PLANIFIEE'")
        kpis['animations_planifiees'] = cursor.fetchone()[0]
        
        cursor.close()
        conn.close()
        
        return kpis
    except Exception as e:
        st.error(f"❌ Erreur KPIs : {str(e)}")
        return None

def get_alertes():
    """Récupère les alertes actives"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        alertes = {'rouge': [], 'orange': [], 'jaune': []}
        
        # ROUGE : Magasins sans visite > 30 jours
        cursor.execute("""
            SELECT m.id, m.enseigne, m.ville, m.date_derniere_visite,
                   CURRENT_DATE - m.date_derniere_visite as jours_sans_visite
            FROM crm_magasins m
            WHERE m.is_active = TRUE AND m.statut = 'ACTIF'
            AND (m.date_derniere_visite IS NULL OR m.date_derniere_visite < CURRENT_DATE - INTERVAL '30 days')
            ORDER BY m.date_derniere_visite ASC NULLS FIRST
            LIMIT 5
        """)
        alertes['rouge'] = cursor.fetchall()
        
        # ORANGE : Visites prévues en retard
        cursor.execute("""
            SELECT m.id, m.enseigne, m.ville, m.date_prochaine_visite
            FROM crm_magasins m
            WHERE m.is_active = TRUE 
            AND m.date_prochaine_visite < CURRENT_DATE
            ORDER BY m.date_prochaine_visite ASC
            LIMIT 5
        """)
        alertes['orange'] = cursor.fetchall()
        
        # JAUNE : Animations dans 14 jours
        cursor.execute("""
            SELECT a.id, m.enseigne, m.ville, a.date_animation, ta.libelle as type
            FROM crm_animations a
            JOIN crm_magasins m ON a.magasin_id = m.id
            LEFT JOIN crm_types_animation ta ON a.type_animation_id = ta.id
            WHERE a.is_active = TRUE AND a.statut = 'PLANIFIEE'
            AND a.date_animation BETWEEN CURRENT_DATE AND CURRENT_DATE + INTERVAL '14 days'
            ORDER BY a.date_animation ASC
            LIMIT 5
        """)
        alertes['jaune'] = cursor.fetchall()
        
        cursor.close()
        conn.close()
        
        return alertes
    except Exception as e:
        st.error(f"❌ Erreur alertes : {str(e)}")
        return None

def get_stats_commerciaux():
    """Stats par commercial"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                c.id,
                c.prenom || ' ' || c.nom as commercial,
                COUNT(DISTINCT m.id) as nb_magasins,
                COUNT(DISTINCT CASE WHEN m.statut = 'ACTIF' THEN m.id END) as nb_actifs,
                COUNT(DISTINCT v.id) FILTER (WHERE v.statut = 'EFFECTUEE' AND v.date_visite >= DATE_TRUNC('month', CURRENT_DATE)) as visites_mois,
                COUNT(DISTINCT v.id) FILTER (WHERE v.statut = 'EFFECTUEE' AND v.date_visite >= CURRENT_DATE - INTERVAL '30 days') as visites_30j
            FROM crm_commerciaux c
            LEFT JOIN crm_magasins m ON c.id = m.commercial_id AND m.is_active = TRUE
            LEFT JOIN crm_visites v ON c.id = v.commercial_id AND v.is_active = TRUE
            WHERE c.is_active = TRUE
            GROUP BY c.id, c.prenom, c.nom
            ORDER BY visites_mois DESC
        """)
        
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        
        if rows:
            return pd.DataFrame(rows, columns=['id', 'Commercial', 'Magasins', 'Actifs', 'Visites Mois', 'Visites 30j'])
        return pd.DataFrame()
    except:
        return pd.DataFrame()

def get_agenda_semaine():
    """Visites prévues cette semaine"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                v.date_visite,
                m.enseigne,
                m.ville,
                c.prenom || ' ' || c.nom as commercial,
                tv.libelle as type_visite
            FROM crm_visites v
            JOIN crm_magasins m ON v.magasin_id = m.id
            LEFT JOIN crm_commerciaux c ON v.commercial_id = c.id
            LEFT JOIN crm_types_visite tv ON v.type_visite_id = tv.id
            WHERE v.is_active = TRUE 
            AND v.statut = 'PLANIFIEE'
            AND v.date_visite BETWEEN CURRENT_DATE AND CURRENT_DATE + INTERVAL '7 days'
            ORDER BY v.date_visite ASC
        """)
        
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        
        return rows if rows else []
    except:
        return []

def get_dernieres_visites():
    """10 dernières visites"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                v.date_visite,
                m.enseigne,
                m.ville,
                c.prenom || ' ' || c.nom as commercial,
                tv.libelle as type_visite
            FROM crm_visites v
            JOIN crm_magasins m ON v.magasin_id = m.id
            LEFT JOIN crm_commerciaux c ON v.commercial_id = c.id
            LEFT JOIN crm_types_visite tv ON v.type_visite_id = tv.id
            WHERE v.is_active = TRUE AND v.statut = 'EFFECTUEE'
            ORDER BY v.date_visite DESC
            LIMIT 10
        """)
        
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        
        if rows:
            df = pd.DataFrame(rows, columns=['Date', 'Enseigne', 'Ville', 'Commercial', 'Type'])
            df['Date'] = pd.to_datetime(df['Date']).dt.strftime('%d/%m/%Y')
            return df
        return pd.DataFrame()
    except:
        return pd.DataFrame()

# ==========================================
# AFFICHAGE KPIs
# ==========================================

kpis = get_kpis_globaux()

if kpis:
    col1, col2, col3, col4, col5 = st.columns(5)
    
    with col1:
        st.metric("🏪 Total Magasins", kpis['total_magasins'])
    with col2:
        st.metric("✅ Magasins Actifs", kpis['magasins_actifs'])
    with col3:
        st.metric("📅 Visites ce mois", kpis['visites_mois'])
    with col4:
        st.metric("📊 Couverture 30j", f"{kpis['taux_couverture']}%")
    with col5:
        st.metric("🎉 Animations", kpis['animations_planifiees'])

st.markdown("---")

# ==========================================
# ALERTES
# ==========================================

col_alertes, col_stats = st.columns([1, 1])

with col_alertes:
    st.subheader("⚠️ Alertes Actives")
    
    alertes = get_alertes()
    
    if alertes:
        # Alertes rouges
        if alertes['rouge']:
            st.markdown("**🔴 Magasins sans visite > 30 jours**")
            for a in alertes['rouge']:
                jours = a['jours_sans_visite'] if a['jours_sans_visite'] else "Jamais visité"
                st.markdown(f"""<div class="alert-rouge">
                    <strong>{a['enseigne']}</strong> - {a['ville']}<br>
                    <small>⏰ {jours} jours</small>
                </div>""", unsafe_allow_html=True)
        
        # Alertes oranges
        if alertes['orange']:
            st.markdown("**🟠 Visites en retard**")
            for a in alertes['orange']:
                date_str = a['date_prochaine_visite'].strftime('%d/%m/%Y') if a['date_prochaine_visite'] else ''
                st.markdown(f"""<div class="alert-orange">
                    <strong>{a['enseigne']}</strong> - {a['ville']}<br>
                    <small>📅 Prévue le {date_str}</small>
                </div>""", unsafe_allow_html=True)
        
        # Alertes jaunes
        if alertes['jaune']:
            st.markdown("**🟡 Animations à venir**")
            for a in alertes['jaune']:
                date_str = a['date_animation'].strftime('%d/%m/%Y') if a['date_animation'] else ''
                st.markdown(f"""<div class="alert-jaune">
                    <strong>{a['enseigne']}</strong> - {a['ville']}<br>
                    <small>🎉 {a['type'] or 'Animation'} le {date_str}</small>
                </div>""", unsafe_allow_html=True)
        
        if not alertes['rouge'] and not alertes['orange'] and not alertes['jaune']:
            st.success("✅ Aucune alerte active")
    else:
        st.info("Aucune donnée d'alerte")

with col_stats:
    st.subheader("👥 Performance Équipe")
    
    df_stats = get_stats_commerciaux()
    
    if not df_stats.empty:
        st.dataframe(df_stats.drop(columns=['id']), use_container_width=True, hide_index=True)
        
        # Commercial du mois
        if len(df_stats) > 0:
            best = df_stats.loc[df_stats['Visites Mois'].idxmax()]
            if best['Visites Mois'] > 0:
                st.success(f"🏆 **Commercial du mois** : {best['Commercial']} ({int(best['Visites Mois'])} visites)")
    else:
        st.info("Aucune donnée")

st.markdown("---")

# ==========================================
# AGENDA & DERNIÈRES VISITES
# ==========================================

col_agenda, col_visites = st.columns([1, 1])

with col_agenda:
    st.subheader("📅 Agenda Semaine")
    
    agenda = get_agenda_semaine()
    
    if agenda:
        # Grouper par date
        dates = {}
        for v in agenda:
            date_str = v['date_visite'].strftime('%d/%m/%Y')
            if date_str not in dates:
                dates[date_str] = []
            dates[date_str].append(v)
        
        for date_str, visites in dates.items():
            with st.expander(f"📅 {date_str} ({len(visites)} visite(s))"):
                for v in visites:
                    st.markdown(f"• **{v['enseigne']}** - {v['ville']} ({v['commercial'] or 'N/A'})")
    else:
        st.info("Aucune visite planifiée cette semaine")

with col_visites:
    st.subheader("📋 Dernières Visites")
    
    df_visites = get_dernieres_visites()
    
    if not df_visites.empty:
        st.dataframe(df_visites, use_container_width=True, hide_index=True)
    else:
        st.info("Aucune visite enregistrée")

st.markdown("---")

# ==========================================
# RACCOURCIS
# ==========================================

st.subheader("🔗 Accès Rapide")

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.page_link("pages/21_CRM_Magasins.py", label="🏪 Magasins", icon="🏪")
with col2:
    st.page_link("pages/22_CRM_Contacts.py", label="👥 Contacts", icon="👥")
with col3:
    st.page_link("pages/23_CRM_Visites.py", label="📅 Visites", icon="📅")
with col4:
    st.page_link("pages/24_CRM_Animations.py", label="🎉 Animations", icon="🎉")

show_footer()
