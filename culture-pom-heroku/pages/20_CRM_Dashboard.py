import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from database import get_connection
from components import show_footer
from auth import is_authenticated

st.set_page_config(page_title="CRM Dashboard - Culture Pom", page_icon="📊", layout="wide")

# CSS compact
st.markdown("""
<style>
    .block-container {
        padding-top: 1.5rem !important;
        padding-bottom: 0.5rem !important;
    }
    h1, h2, h3, h4 {
        margin-top: 0.3rem !important;
        margin-bottom: 0.3rem !important;
    }
    .alerte-rouge {
        background-color: #ffebee;
        border-left: 4px solid #f44336;
        padding: 0.8rem;
        margin: 0.3rem 0;
        border-radius: 4px;
    }
    .alerte-orange {
        background-color: #fff3e0;
        border-left: 4px solid #ff9800;
        padding: 0.8rem;
        margin: 0.3rem 0;
        border-radius: 4px;
    }
    .alerte-jaune {
        background-color: #fffde7;
        border-left: 4px solid #ffeb3b;
        padding: 0.8rem;
        margin: 0.3rem 0;
        border-radius: 4px;
    }
</style>
""", unsafe_allow_html=True)

if not is_authenticated():
    st.warning("⚠️ Veuillez vous connecter pour accéder à cette page")
    st.stop()

st.title("📊 CRM - Tableau de Bord")
st.markdown("*Vue d'ensemble de l'activité commerciale*")
st.markdown("---")

# ==========================================
# FONCTIONS DE CHARGEMENT
# ==========================================

def get_kpis_globaux():
    """Récupère les KPIs globaux du CRM"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        kpis = {}
        
        cursor.execute("SELECT COUNT(*) FROM crm_magasins WHERE is_active = TRUE")
        kpis['total_magasins'] = cursor.fetchone()[0]
        
        cursor.execute("""
            SELECT statut, COUNT(*) 
            FROM crm_magasins 
            WHERE is_active = TRUE 
            GROUP BY statut
        """)
        kpis['par_statut'] = {row[0]: row[1] for row in cursor.fetchall()}
        
        cursor.execute("""
            SELECT COUNT(*) FROM crm_visites 
            WHERE date_visite >= DATE_TRUNC('month', CURRENT_DATE)
        """)
        kpis['visites_mois'] = cursor.fetchone()[0]
        
        cursor.execute("""
            SELECT COUNT(*) FROM crm_magasins 
            WHERE date_prochaine_visite BETWEEN CURRENT_DATE AND CURRENT_DATE + INTERVAL '7 days'
            AND is_active = TRUE
        """)
        kpis['visites_semaine'] = cursor.fetchone()[0]
        
        cursor.execute("""
            SELECT 
                COUNT(DISTINCT m.id) FILTER (WHERE m.date_derniere_visite >= CURRENT_DATE - INTERVAL '30 days') as visites,
                COUNT(DISTINCT m.id) as total
            FROM crm_magasins m
            WHERE m.is_active = TRUE AND m.statut = 'ACTIF'
        """)
        row = cursor.fetchone()
        kpis['taux_couverture'] = round((row[0] / row[1]) * 100, 1) if row[1] > 0 else 0
        
        cursor.execute("""
            SELECT COUNT(*) FROM crm_animations 
            WHERE statut = 'PLANIFIEE' AND is_active = TRUE
        """)
        kpis['animations_planifiees'] = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM crm_contacts WHERE is_active = TRUE")
        kpis['total_contacts'] = cursor.fetchone()[0]
        
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
        
        cursor.execute("""
            SELECT 
                m.id, m.code_magasin, m.enseigne, m.ville,
                c.prenom || ' ' || c.nom as commercial,
                m.date_derniere_visite,
                CASE 
                    WHEN m.date_derniere_visite IS NULL THEN 999
                    ELSE CURRENT_DATE - m.date_derniere_visite 
                END as jours_sans_visite
            FROM crm_magasins m
            LEFT JOIN crm_commerciaux c ON m.commercial_id = c.id
            WHERE m.is_active = TRUE
              AND (m.date_derniere_visite IS NULL OR CURRENT_DATE - m.date_derniere_visite > 30)
            ORDER BY jours_sans_visite DESC
            LIMIT 10
        """)
        alertes_rouge = cursor.fetchall()
        
        cursor.execute("""
            SELECT 
                m.id, m.code_magasin, m.enseigne, m.ville,
                c.prenom || ' ' || c.nom as commercial,
                m.date_prochaine_visite,
                CURRENT_DATE - m.date_prochaine_visite as jours_retard
            FROM crm_magasins m
            LEFT JOIN crm_commerciaux c ON m.commercial_id = c.id
            WHERE m.is_active = TRUE
              AND m.date_prochaine_visite < CURRENT_DATE
            ORDER BY jours_retard DESC
            LIMIT 10
        """)
        alertes_orange = cursor.fetchall()
        
        cursor.execute("""
            SELECT 
                a.id, m.code_magasin, m.enseigne, m.ville,
                c.prenom || ' ' || c.nom as commercial,
                ta.libelle as type_animation,
                a.date_animation,
                a.date_animation - CURRENT_DATE as jours_avant
            FROM crm_animations a
            JOIN crm_magasins m ON a.magasin_id = m.id
            LEFT JOIN crm_commerciaux c ON a.commercial_id = c.id
            LEFT JOIN crm_types_animation ta ON a.type_animation_id = ta.id
            WHERE a.is_active = TRUE
              AND a.statut = 'PLANIFIEE'
              AND a.date_animation BETWEEN CURRENT_DATE AND CURRENT_DATE + INTERVAL '14 days'
            ORDER BY a.date_animation
            LIMIT 10
        """)
        alertes_jaune = cursor.fetchall()
        
        cursor.close()
        conn.close()
        
        return {'rouge': alertes_rouge, 'orange': alertes_orange, 'jaune': alertes_jaune}
        
    except Exception as e:
        st.error(f"❌ Erreur alertes : {str(e)}")
        return None

def get_stats_commerciaux():
    """Récupère les statistiques par commercial"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                c.id,
                c.prenom || ' ' || c.nom as commercial,
                COUNT(DISTINCT m.id) as nb_magasins,
                COUNT(DISTINCT CASE WHEN m.statut = 'ACTIF' THEN m.id END) as nb_actifs,
                COUNT(DISTINCT v.id) FILTER (WHERE v.date_visite >= DATE_TRUNC('month', CURRENT_DATE)) as visites_mois,
                COUNT(DISTINCT v.id) FILTER (WHERE v.date_visite >= CURRENT_DATE - INTERVAL '30 days') as visites_30j
            FROM crm_commerciaux c
            LEFT JOIN crm_magasins m ON m.commercial_id = c.id AND m.is_active = TRUE
            LEFT JOIN crm_visites v ON v.commercial_id = c.id
            WHERE c.is_active = TRUE
            GROUP BY c.id, c.prenom, c.nom
            ORDER BY visites_mois DESC
        """)
        
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        
        if rows:
            return pd.DataFrame(rows, columns=['id', 'commercial', 'nb_magasins', 'nb_actifs', 'visites_mois', 'visites_30j'])
        return pd.DataFrame()
        
    except Exception as e:
        st.error(f"❌ Erreur stats : {str(e)}")
        return pd.DataFrame()

def get_agenda_semaine():
    """Récupère l'agenda des visites prévues cette semaine"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                m.id, m.code_magasin, m.enseigne, m.ville,
                c.prenom || ' ' || c.nom as commercial,
                m.date_prochaine_visite
            FROM crm_magasins m
            LEFT JOIN crm_commerciaux c ON m.commercial_id = c.id
            WHERE m.is_active = TRUE
              AND m.date_prochaine_visite BETWEEN CURRENT_DATE AND CURRENT_DATE + INTERVAL '7 days'
            ORDER BY m.date_prochaine_visite, m.enseigne
        """)
        
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        
        if rows:
            return pd.DataFrame(rows, columns=['id', 'code_magasin', 'enseigne', 'ville', 'commercial', 'date_prochaine_visite'])
        return pd.DataFrame()
        
    except Exception as e:
        st.error(f"❌ Erreur agenda : {str(e)}")
        return pd.DataFrame()

def get_dernieres_visites():
    """Récupère les 10 dernières visites"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                v.id, v.date_visite,
                m.enseigne, m.ville,
                c.prenom || ' ' || c.nom as commercial,
                tv.libelle as type_visite
            FROM crm_visites v
            JOIN crm_magasins m ON v.magasin_id = m.id
            LEFT JOIN crm_commerciaux c ON v.commercial_id = c.id
            LEFT JOIN crm_types_visite tv ON v.type_visite_id = tv.id
            ORDER BY v.date_visite DESC, v.created_at DESC
            LIMIT 10
        """)
        
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        
        if rows:
            return pd.DataFrame(rows, columns=['id', 'date_visite', 'enseigne', 'ville', 'commercial', 'type_visite'])
        return pd.DataFrame()
        
    except Exception as e:
        st.error(f"❌ Erreur visites : {str(e)}")
        return pd.DataFrame()

# ==========================================
# AFFICHAGE KPIs
# ==========================================

kpis = get_kpis_globaux()

if kpis:
    col1, col2, col3, col4, col5 = st.columns(5)
    
    with col1:
        st.metric("🏪 Magasins", kpis['total_magasins'])
    with col2:
        st.metric("✅ Actifs", kpis['par_statut'].get('ACTIF', 0))
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

st.subheader("🚨 Alertes")

alertes = get_alertes()

if alertes:
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown(f"**🔴 Sans visite > 30j** ({len(alertes['rouge'])})")
        if alertes['rouge']:
            for a in alertes['rouge'][:5]:
                jours = a[6] if a[6] != 999 else "Jamais"
                st.markdown(f'<div class="alerte-rouge"><strong>{a[2]}</strong> - {a[3]}<br><small>👤 {a[4] or "N/A"} | ⏱️ {jours}j</small></div>', unsafe_allow_html=True)
        else:
            st.success("✅ RAS")
    
    with col2:
        st.markdown(f"**🟠 Visite en retard** ({len(alertes['orange'])})")
        if alertes['orange']:
            for a in alertes['orange'][:5]:
                st.markdown(f'<div class="alerte-orange"><strong>{a[2]}</strong> - {a[3]}<br><small>👤 {a[4] or "N/A"} | ⏱️ +{a[6]}j</small></div>', unsafe_allow_html=True)
        else:
            st.success("✅ RAS")
    
    with col3:
        st.markdown(f"**🟡 Animation proche** ({len(alertes['jaune'])})")
        if alertes['jaune']:
            for a in alertes['jaune'][:5]:
                date_str = a[6].strftime('%d/%m') if a[6] else ''
                st.markdown(f'<div class="alerte-jaune"><strong>{a[2]}</strong> - {a[3]}<br><small>🎉 {a[5]} | 📅 {date_str}</small></div>', unsafe_allow_html=True)
        else:
            st.info("ℹ️ Aucune")

st.markdown("---")

# ==========================================
# STATS + AGENDA
# ==========================================

col_left, col_right = st.columns([1, 1])

with col_left:
    st.subheader("👥 Performance Équipe")
    stats_df = get_stats_commerciaux()
    
    if not stats_df.empty:
        if stats_df['visites_mois'].max() > 0:
            best = stats_df.loc[stats_df['visites_mois'].idxmax()]
            st.markdown(f"🏆 **Commercial du mois** : {best['commercial']} ({int(best['visites_mois'])} visites)")
        
        display_df = stats_df[['commercial', 'nb_magasins', 'nb_actifs', 'visites_mois', 'visites_30j']].copy()
        display_df.columns = ['Commercial', 'Magasins', 'Actifs', 'Ce mois', '30j']
        st.dataframe(display_df, use_container_width=True, hide_index=True)
    else:
        st.info("Aucune donnée")

with col_right:
    st.subheader("📅 Visites Prévues (7j)")
    agenda_df = get_agenda_semaine()
    
    if not agenda_df.empty:
        st.markdown(f"**{len(agenda_df)} visite(s) cette semaine**")
        for date in sorted(agenda_df['date_prochaine_visite'].unique()):
            jour_df = agenda_df[agenda_df['date_prochaine_visite'] == date]
            date_str = pd.to_datetime(date).strftime('%a %d/%m')
            with st.expander(f"📆 {date_str} ({len(jour_df)})", expanded=True):
                for _, row in jour_df.iterrows():
                    st.markdown(f"- **{row['enseigne']}** {row['ville']} - {row['commercial'] or 'N/A'}")
    else:
        st.info("📅 Aucune visite prévue")

st.markdown("---")

# ==========================================
# DERNIÈRES VISITES
# ==========================================

st.subheader("🕐 Dernières Visites")
visites_df = get_dernieres_visites()

if not visites_df.empty:
    display_df = visites_df.copy()
    display_df['date_visite'] = pd.to_datetime(display_df['date_visite']).dt.strftime('%d/%m/%Y')
    display_df.columns = ['ID', 'Date', 'Enseigne', 'Ville', 'Commercial', 'Type']
    st.dataframe(display_df[['Date', 'Enseigne', 'Ville', 'Commercial', 'Type']], use_container_width=True, hide_index=True)
else:
    st.info("Aucune visite enregistrée")

st.markdown("---")

# ==========================================
# RACCOURCIS
# ==========================================

st.subheader("🔗 Accès Rapides")
col1, col2, col3, col4 = st.columns(4)

with col1:
    st.page_link("pages/21_CRM_Magasins.py", label="🏪 Magasins", use_container_width=True)
with col2:
    st.page_link("pages/23_CRM_Visites.py", label="📋 Visites", use_container_width=True)
with col3:
    st.page_link("pages/22_CRM_Contacts.py", label="👥 Contacts", use_container_width=True)
with col4:
    st.page_link("pages/24_CRM_Animations.py", label="🎉 Animations", use_container_width=True)

show_footer()
