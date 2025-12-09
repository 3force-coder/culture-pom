import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from database import get_connection
from components import show_footer
from auth import is_authenticated, require_access
import io

st.set_page_config(page_title="CRM Statistiques - Culture Pom", page_icon="📈", layout="wide")

if not is_authenticated():
    st.warning("⚠️ Veuillez vous connecter")
    st.stop()

require_access("CRM")

st.markdown("""
<style>
    .block-container { padding-top: 1.5rem !important; padding-bottom: 0.5rem !important; }
    h1, h2, h3, h4 { margin-top: 0.3rem !important; margin-bottom: 0.3rem !important; }
    .kpi-card { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 1.2rem; border-radius: 10px; text-align: center; margin: 0.3rem; }
    .kpi-card h2 { color: white !important; margin: 0 !important; font-size: 2rem; }
    .kpi-card p { color: rgba(255,255,255,0.9) !important; margin: 0.3rem 0 0 0 !important; }
</style>
""", unsafe_allow_html=True)

st.title("📈 CRM - Statistiques")
st.markdown("---")

# ==========================================
# FONCTIONS
# ==========================================

def get_stats_globales():
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        stats = {}
        
        cursor.execute("SELECT COUNT(*) FROM crm_magasins WHERE is_active = TRUE")
        stats['total_magasins'] = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM crm_magasins WHERE is_active = TRUE AND statut = 'ACTIF'")
        stats['magasins_actifs'] = cursor.fetchone()[0]
        
        cursor.execute("""
            SELECT COUNT(*) FROM crm_visites 
            WHERE is_active = TRUE AND statut = 'EFFECTUEE'
            AND date_visite >= DATE_TRUNC('month', CURRENT_DATE)
        """)
        stats['visites_mois'] = cursor.fetchone()[0]
        
        cursor.execute("""
            SELECT COUNT(*) FROM crm_magasins 
            WHERE is_active = TRUE AND statut = 'ACTIF'
            AND date_derniere_visite >= CURRENT_DATE - INTERVAL '30 days'
        """)
        couverts = cursor.fetchone()[0]
        stats['taux_couverture'] = round((couverts / stats['magasins_actifs'] * 100), 1) if stats['magasins_actifs'] > 0 else 0
        
        cursor.execute("SELECT COUNT(*) FROM crm_animations WHERE is_active = TRUE AND statut = 'TERMINEE'")
        stats['animations_terminees'] = cursor.fetchone()[0]
        
        cursor.close()
        conn.close()
        
        return stats
    except:
        return None

def get_stats_par_commercial():
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
                COUNT(DISTINCT v.id) FILTER (WHERE v.statut = 'EFFECTUEE' AND v.date_visite >= CURRENT_DATE - INTERVAL '30 days') as visites_30j,
                COUNT(DISTINCT a.id) FILTER (WHERE a.statut = 'TERMINEE') as animations
            FROM crm_commerciaux c
            LEFT JOIN crm_magasins m ON c.id = m.commercial_id AND m.is_active = TRUE
            LEFT JOIN crm_visites v ON c.id = v.commercial_id AND v.is_active = TRUE
            LEFT JOIN crm_animations a ON c.id = a.commercial_id AND a.is_active = TRUE
            WHERE c.is_active = TRUE
            GROUP BY c.id, c.prenom, c.nom
            ORDER BY visites_mois DESC
        """)
        
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        
        if rows:
            return pd.DataFrame(rows, columns=['id', 'Commercial', 'Magasins', 'Actifs', 'Visites Mois', 'Visites 30j', 'Animations'])
        return pd.DataFrame()
    except:
        return pd.DataFrame()

def get_stats_par_enseigne():
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                m.enseigne,
                COUNT(DISTINCT m.id) as nb_magasins,
                COUNT(DISTINCT CASE WHEN m.statut = 'ACTIF' THEN m.id END) as nb_actifs,
                COUNT(DISTINCT v.id) FILTER (WHERE v.statut = 'EFFECTUEE') as nb_visites,
                ROUND(AVG(m.note_magasin)::numeric, 1) as note_moyenne
            FROM crm_magasins m
            LEFT JOIN crm_visites v ON m.id = v.magasin_id AND v.is_active = TRUE
            WHERE m.is_active = TRUE
            GROUP BY m.enseigne
            ORDER BY nb_magasins DESC
            LIMIT 15
        """)
        
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        
        if rows:
            return pd.DataFrame(rows, columns=['Enseigne', 'Magasins', 'Actifs', 'Visites', 'Note Moy'])
        return pd.DataFrame()
    except:
        return pd.DataFrame()

def get_stats_par_departement():
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                m.departement,
                COUNT(DISTINCT m.id) as nb_magasins,
                COUNT(DISTINCT CASE WHEN m.statut = 'ACTIF' THEN m.id END) as nb_actifs,
                COUNT(DISTINCT v.id) FILTER (WHERE v.statut = 'EFFECTUEE' AND v.date_visite >= CURRENT_DATE - INTERVAL '30 days') as visites_30j
            FROM crm_magasins m
            LEFT JOIN crm_visites v ON m.id = v.magasin_id AND v.is_active = TRUE
            WHERE m.is_active = TRUE AND m.departement IS NOT NULL
            GROUP BY m.departement
            ORDER BY nb_magasins DESC
        """)
        
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        
        if rows:
            return pd.DataFrame(rows, columns=['Département', 'Magasins', 'Actifs', 'Visites 30j'])
        return pd.DataFrame()
    except:
        return pd.DataFrame()

def get_evolution_visites():
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                TO_CHAR(date_visite, 'YYYY-MM') as mois,
                COUNT(*) as nb_visites
            FROM crm_visites
            WHERE is_active = TRUE AND statut = 'EFFECTUEE'
            AND date_visite >= CURRENT_DATE - INTERVAL '6 months'
            GROUP BY TO_CHAR(date_visite, 'YYYY-MM')
            ORDER BY mois
        """)
        
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        
        if rows:
            return pd.DataFrame(rows, columns=['Mois', 'Visites'])
        return pd.DataFrame()
    except:
        return pd.DataFrame()

def get_repartition_statuts():
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT statut, COUNT(*) as nb
            FROM crm_magasins
            WHERE is_active = TRUE
            GROUP BY statut
            ORDER BY nb DESC
        """)
        
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        
        if rows:
            return pd.DataFrame(rows, columns=['Statut', 'Nombre'])
        return pd.DataFrame()
    except:
        return pd.DataFrame()

def get_top_magasins():
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                m.enseigne || ' - ' || m.ville as magasin,
                COUNT(v.id) as nb_visites
            FROM crm_magasins m
            LEFT JOIN crm_visites v ON m.id = v.magasin_id AND v.is_active = TRUE AND v.statut = 'EFFECTUEE'
            WHERE m.is_active = TRUE
            GROUP BY m.id, m.enseigne, m.ville
            HAVING COUNT(v.id) > 0
            ORDER BY nb_visites DESC
            LIMIT 10
        """)
        
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        
        if rows:
            return pd.DataFrame(rows, columns=['Magasin', 'Visites'])
        return pd.DataFrame()
    except:
        return pd.DataFrame()

# ==========================================
# KPIs GLOBAUX
# ==========================================

stats = get_stats_globales()

if stats:
    col1, col2, col3, col4, col5 = st.columns(5)
    
    with col1:
        st.markdown(f"""
        <div class="kpi-card">
            <h2>{stats['total_magasins']}</h2>
            <p>🏪 Total Magasins</p>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        st.markdown(f"""
        <div class="kpi-card">
            <h2>{stats['magasins_actifs']}</h2>
            <p>✅ Magasins Actifs</p>
        </div>
        """, unsafe_allow_html=True)
    
    with col3:
        st.markdown(f"""
        <div class="kpi-card">
            <h2>{stats['visites_mois']}</h2>
            <p>📅 Visites ce mois</p>
        </div>
        """, unsafe_allow_html=True)
    
    with col4:
        st.markdown(f"""
        <div class="kpi-card">
            <h2>{stats['taux_couverture']}%</h2>
            <p>📊 Taux Couverture</p>
        </div>
        """, unsafe_allow_html=True)
    
    with col5:
        st.markdown(f"""
        <div class="kpi-card">
            <h2>{stats['animations_terminees']}</h2>
            <p>🎉 Animations terminées</p>
        </div>
        """, unsafe_allow_html=True)

st.markdown("---")

# ==========================================
# ONGLETS
# ==========================================

tab1, tab2, tab3, tab4 = st.tabs(["👥 Par Commercial", "🏪 Par Enseigne", "📍 Par Département", "📈 Évolutions"])

with tab1:
    st.subheader("👥 Performance par Commercial")
    
    df_comm = get_stats_par_commercial()
    
    if not df_comm.empty:
        st.dataframe(df_comm.drop(columns=['id']), use_container_width=True, hide_index=True)
        
        st.markdown("---")
        st.markdown("**📊 Visites du mois par commercial**")
        
        chart_data = df_comm[['Commercial', 'Visites Mois']].copy()
        st.bar_chart(chart_data.set_index('Commercial'))
        
        # Commercial du mois
        if len(df_comm) > 0:
            best = df_comm.loc[df_comm['Visites Mois'].idxmax()]
            if best['Visites Mois'] > 0:
                st.success(f"🏆 **Commercial du mois** : {best['Commercial']} avec {int(best['Visites Mois'])} visites")
        
        # Export
        csv = df_comm.to_csv(index=False).encode('utf-8')
        st.download_button("📥 Exporter CSV", csv, "stats_commerciaux.csv", "text/csv")
    else:
        st.info("Aucune donnée")

with tab2:
    st.subheader("🏪 Statistiques par Enseigne")
    
    df_enseigne = get_stats_par_enseigne()
    
    if not df_enseigne.empty:
        st.dataframe(df_enseigne, use_container_width=True, hide_index=True)
        
        st.markdown("---")
        st.markdown("**📊 Top 10 enseignes par nombre de magasins**")
        
        chart_data = df_enseigne.head(10)[['Enseigne', 'Magasins']].copy()
        st.bar_chart(chart_data.set_index('Enseigne'))
        
        # Export
        csv = df_enseigne.to_csv(index=False).encode('utf-8')
        st.download_button("📥 Exporter CSV", csv, "stats_enseignes.csv", "text/csv")
    else:
        st.info("Aucune donnée")

with tab3:
    st.subheader("📍 Statistiques par Département")
    
    df_dept = get_stats_par_departement()
    
    if not df_dept.empty:
        st.dataframe(df_dept, use_container_width=True, hide_index=True)
        
        st.markdown("---")
        st.markdown("**📊 Top 10 départements**")
        
        chart_data = df_dept.head(10)[['Département', 'Magasins']].copy()
        st.bar_chart(chart_data.set_index('Département'))
        
        # Export
        csv = df_dept.to_csv(index=False).encode('utf-8')
        st.download_button("📥 Exporter CSV", csv, "stats_departements.csv", "text/csv")
    else:
        st.info("Aucune donnée")

with tab4:
    st.subheader("📈 Évolutions et Répartitions")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("**📊 Évolution des visites (6 mois)**")
        df_evol = get_evolution_visites()
        
        if not df_evol.empty:
            st.line_chart(df_evol.set_index('Mois'))
        else:
            st.info("Pas assez de données")
    
    with col2:
        st.markdown("**📊 Répartition par statut**")
        df_statuts = get_repartition_statuts()
        
        if not df_statuts.empty:
            for _, row in df_statuts.iterrows():
                statut = row['Statut']
                nb = row['Nombre']
                icon = "🟢" if statut == 'ACTIF' else ("🔵" if statut == 'PROSPECT' else ("🟡" if statut == 'EN_PAUSE' else ("⚪" if statut == 'INACTIF' else "🔴")))
                st.markdown(f"{icon} **{statut}** : {nb}")
        else:
            st.info("Aucune donnée")
    
    st.markdown("---")
    st.markdown("**🏆 Top 10 magasins les plus visités**")
    
    df_top = get_top_magasins()
    
    if not df_top.empty:
        st.dataframe(df_top, use_container_width=True, hide_index=True)
    else:
        st.info("Aucune donnée")

show_footer()
