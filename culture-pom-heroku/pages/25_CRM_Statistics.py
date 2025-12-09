import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from database import get_connection
from components import show_footer
from auth import is_authenticated

st.set_page_config(page_title="CRM Statistiques - Culture Pom", page_icon="📊", layout="wide")

st.markdown("""
<style>
    .block-container { padding-top: 1.5rem !important; padding-bottom: 0.5rem !important; }
    h1, h2, h3, h4 { margin-top: 0.3rem !important; margin-bottom: 0.3rem !important; }
    .stat-card { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 1.5rem; border-radius: 10px; text-align: center; margin: 0.5rem 0; }
    .stat-card h2 { color: white !important; margin: 0 !important; font-size: 2.5rem !important; }
    .stat-card p { margin: 0.5rem 0 0 0; opacity: 0.9; }
</style>
""", unsafe_allow_html=True)

if not is_authenticated():
    st.warning("⚠️ Veuillez vous connecter")
    st.stop()

st.title("📊 CRM - Statistiques & Analyses")
st.markdown("---")

# ==========================================
# FONCTIONS
# ==========================================

def get_stats_globales():
    """Statistiques globales"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        stats = {}
        
        # Magasins
        cursor.execute("SELECT COUNT(*) FROM crm_magasins WHERE is_active = TRUE")
        stats['total_magasins'] = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM crm_magasins WHERE is_active = TRUE AND statut = 'ACTIF'")
        stats['magasins_actifs'] = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM crm_magasins WHERE is_active = TRUE AND statut = 'PROSPECT'")
        stats['prospects'] = cursor.fetchone()[0]
        
        # Contacts
        cursor.execute("SELECT COUNT(*) FROM crm_contacts WHERE is_active = TRUE")
        stats['total_contacts'] = cursor.fetchone()[0]
        
        # Visites
        cursor.execute("SELECT COUNT(*) FROM crm_visites WHERE is_active = TRUE AND statut = 'EFFECTUEE'")
        stats['visites_effectuees'] = cursor.fetchone()[0]
        
        cursor.execute("""
            SELECT COUNT(*) FROM crm_visites 
            WHERE is_active = TRUE AND statut = 'EFFECTUEE'
            AND date_visite >= DATE_TRUNC('month', CURRENT_DATE)
        """)
        stats['visites_mois'] = cursor.fetchone()[0]
        
        # Animations
        cursor.execute("SELECT COUNT(*) FROM crm_animations WHERE is_active = TRUE AND statut = 'TERMINEE'")
        stats['animations_terminees'] = cursor.fetchone()[0]
        
        # Couverture 30j
        cursor.execute("""
            SELECT COUNT(*) FROM crm_magasins 
            WHERE is_active = TRUE AND statut = 'ACTIF'
            AND date_derniere_visite >= CURRENT_DATE - INTERVAL '30 days'
        """)
        stats['couverts_30j'] = cursor.fetchone()[0]
        
        if stats['magasins_actifs'] > 0:
            stats['taux_couverture'] = round((stats['couverts_30j'] / stats['magasins_actifs']) * 100, 1)
        else:
            stats['taux_couverture'] = 0
        
        cursor.close()
        conn.close()
        
        return stats
    except Exception as e:
        st.error(f"❌ Erreur : {str(e)}")
        return None

def get_stats_par_commercial():
    """Stats par commercial"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        query = """
            SELECT 
                c.id,
                c.prenom || ' ' || c.nom as commercial,
                COUNT(DISTINCT m.id) as nb_magasins,
                COUNT(DISTINCT CASE WHEN m.statut = 'ACTIF' THEN m.id END) as nb_actifs,
                COUNT(DISTINCT v.id) FILTER (WHERE v.statut = 'EFFECTUEE' AND v.date_visite >= DATE_TRUNC('month', CURRENT_DATE)) as visites_mois,
                COUNT(DISTINCT v.id) FILTER (WHERE v.statut = 'EFFECTUEE' AND v.date_visite >= CURRENT_DATE - INTERVAL '30 days') as visites_30j,
                COUNT(DISTINCT a.id) FILTER (WHERE a.statut = 'TERMINEE') as animations_terminees
            FROM crm_commerciaux c
            LEFT JOIN crm_magasins m ON c.id = m.commercial_id AND m.is_active = TRUE
            LEFT JOIN crm_visites v ON c.id = v.commercial_id AND v.is_active = TRUE
            LEFT JOIN crm_animations a ON c.id = a.commercial_id AND a.is_active = TRUE
            WHERE c.is_active = TRUE
            GROUP BY c.id, c.prenom, c.nom
            ORDER BY visites_mois DESC
        """
        
        cursor.execute(query)
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        
        if rows:
            return pd.DataFrame(rows, columns=[
                'id', 'Commercial', 'Magasins', 'Actifs', 'Visites Mois', 'Visites 30j', 'Animations'
            ])
        return pd.DataFrame()
    except Exception as e:
        st.error(f"❌ Erreur : {str(e)}")
        return pd.DataFrame()

def get_stats_par_enseigne():
    """Stats par enseigne"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        query = """
            SELECT 
                m.enseigne,
                COUNT(DISTINCT m.id) as nb_magasins,
                COUNT(DISTINCT CASE WHEN m.statut = 'ACTIF' THEN m.id END) as nb_actifs,
                COUNT(DISTINCT v.id) FILTER (WHERE v.statut = 'EFFECTUEE') as total_visites,
                ROUND(AVG(m.note_magasin), 1) as note_moyenne
            FROM crm_magasins m
            LEFT JOIN crm_visites v ON m.id = v.magasin_id AND v.is_active = TRUE
            WHERE m.is_active = TRUE
            GROUP BY m.enseigne
            ORDER BY nb_magasins DESC
            LIMIT 15
        """
        
        cursor.execute(query)
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        
        if rows:
            return pd.DataFrame(rows, columns=['Enseigne', 'Magasins', 'Actifs', 'Visites', 'Note Moy.'])
        return pd.DataFrame()
    except Exception as e:
        st.error(f"❌ Erreur : {str(e)}")
        return pd.DataFrame()

def get_stats_par_departement():
    """Stats par département"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        query = """
            SELECT 
                COALESCE(m.departement, 'N/A') as departement,
                COUNT(DISTINCT m.id) as nb_magasins,
                COUNT(DISTINCT CASE WHEN m.statut = 'ACTIF' THEN m.id END) as nb_actifs,
                COUNT(DISTINCT v.id) FILTER (WHERE v.statut = 'EFFECTUEE' AND v.date_visite >= CURRENT_DATE - INTERVAL '30 days') as visites_30j
            FROM crm_magasins m
            LEFT JOIN crm_visites v ON m.id = v.magasin_id AND v.is_active = TRUE
            WHERE m.is_active = TRUE
            GROUP BY m.departement
            ORDER BY nb_magasins DESC
        """
        
        cursor.execute(query)
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        
        if rows:
            return pd.DataFrame(rows, columns=['Département', 'Magasins', 'Actifs', 'Visites 30j'])
        return pd.DataFrame()
    except Exception as e:
        st.error(f"❌ Erreur : {str(e)}")
        return pd.DataFrame()

def get_evolution_visites():
    """Évolution des visites sur 6 mois"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        query = """
            SELECT 
                TO_CHAR(date_visite, 'YYYY-MM') as mois,
                COUNT(*) as nb_visites
            FROM crm_visites
            WHERE is_active = TRUE AND statut = 'EFFECTUEE'
            AND date_visite >= CURRENT_DATE - INTERVAL '6 months'
            GROUP BY TO_CHAR(date_visite, 'YYYY-MM')
            ORDER BY mois
        """
        
        cursor.execute(query)
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        
        if rows:
            return pd.DataFrame(rows, columns=['Mois', 'Visites'])
        return pd.DataFrame()
    except Exception as e:
        return pd.DataFrame()

def get_repartition_statuts():
    """Répartition des statuts magasins"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        query = """
            SELECT statut, COUNT(*) as nb
            FROM crm_magasins
            WHERE is_active = TRUE
            GROUP BY statut
            ORDER BY nb DESC
        """
        
        cursor.execute(query)
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        
        if rows:
            return pd.DataFrame(rows, columns=['Statut', 'Nombre'])
        return pd.DataFrame()
    except Exception as e:
        return pd.DataFrame()

def get_top_magasins():
    """Top magasins par visites"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        query = """
            SELECT 
                m.enseigne,
                m.ville,
                COUNT(v.id) as nb_visites,
                MAX(v.date_visite) as derniere_visite
            FROM crm_magasins m
            JOIN crm_visites v ON m.id = v.magasin_id
            WHERE m.is_active = TRUE AND v.is_active = TRUE AND v.statut = 'EFFECTUEE'
            GROUP BY m.id, m.enseigne, m.ville
            ORDER BY nb_visites DESC
            LIMIT 10
        """
        
        cursor.execute(query)
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        
        if rows:
            df = pd.DataFrame(rows, columns=['Enseigne', 'Ville', 'Nb Visites', 'Dernière Visite'])
            df['Dernière Visite'] = pd.to_datetime(df['Dernière Visite']).dt.strftime('%d/%m/%Y')
            return df
        return pd.DataFrame()
    except Exception as e:
        return pd.DataFrame()

# ==========================================
# AFFICHAGE
# ==========================================

stats = get_stats_globales()

if stats:
    # KPIs principaux
    col1, col2, col3, col4, col5 = st.columns(5)
    
    with col1:
        st.markdown(f"""
        <div class="stat-card">
            <h2>{stats['total_magasins']}</h2>
            <p>🏪 Total Magasins</p>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        st.markdown(f"""
        <div class="stat-card">
            <h2>{stats['magasins_actifs']}</h2>
            <p>✅ Magasins Actifs</p>
        </div>
        """, unsafe_allow_html=True)
    
    with col3:
        st.markdown(f"""
        <div class="stat-card">
            <h2>{stats['visites_mois']}</h2>
            <p>📅 Visites ce mois</p>
        </div>
        """, unsafe_allow_html=True)
    
    with col4:
        st.markdown(f"""
        <div class="stat-card">
            <h2>{stats['taux_couverture']}%</h2>
            <p>📊 Taux Couverture</p>
        </div>
        """, unsafe_allow_html=True)
    
    with col5:
        st.markdown(f"""
        <div class="stat-card">
            <h2>{stats['animations_terminees']}</h2>
            <p>🎉 Animations</p>
        </div>
        """, unsafe_allow_html=True)

st.markdown("---")

# Onglets
tab1, tab2, tab3, tab4 = st.tabs(["👥 Par Commercial", "🏪 Par Enseigne", "🗺️ Par Département", "📈 Évolutions"])

# ==========================================
# TAB 1 : PAR COMMERCIAL
# ==========================================

with tab1:
    st.subheader("📊 Performance par Commercial")
    
    df_comm = get_stats_par_commercial()
    
    if not df_comm.empty:
        # Masquer colonne ID
        display_df = df_comm.drop(columns=['id'])
        
        st.dataframe(display_df, use_container_width=True, hide_index=True)
        
        # Graphique visites
        st.markdown("---")
        st.markdown("**📊 Visites du mois par commercial**")
        
        chart_data = df_comm[['Commercial', 'Visites Mois']].set_index('Commercial')
        st.bar_chart(chart_data)
        
        # Meilleur commercial
        if len(df_comm) > 0:
            best = df_comm.loc[df_comm['Visites Mois'].idxmax()]
            st.success(f"🏆 **Commercial du mois** : {best['Commercial']} avec {best['Visites Mois']} visites")
    else:
        st.info("Aucune donnée disponible")

# ==========================================
# TAB 2 : PAR ENSEIGNE
# ==========================================

with tab2:
    st.subheader("🏪 Statistiques par Enseigne")
    
    df_ens = get_stats_par_enseigne()
    
    if not df_ens.empty:
        st.dataframe(df_ens, use_container_width=True, hide_index=True)
        
        # Top 10 enseignes
        st.markdown("---")
        st.markdown("**📊 Top enseignes par nombre de magasins**")
        
        chart_data = df_ens.head(10)[['Enseigne', 'Magasins']].set_index('Enseigne')
        st.bar_chart(chart_data)
    else:
        st.info("Aucune donnée disponible")

# ==========================================
# TAB 3 : PAR DÉPARTEMENT
# ==========================================

with tab3:
    st.subheader("🗺️ Répartition Géographique")
    
    df_dept = get_stats_par_departement()
    
    if not df_dept.empty:
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("**Magasins par département**")
            st.dataframe(df_dept, use_container_width=True, hide_index=True)
        
        with col2:
            st.markdown("**📊 Top 10 départements**")
            chart_data = df_dept.head(10)[['Département', 'Magasins']].set_index('Département')
            st.bar_chart(chart_data)
    else:
        st.info("Aucune donnée disponible")

# ==========================================
# TAB 4 : ÉVOLUTIONS
# ==========================================

with tab4:
    st.subheader("📈 Évolutions & Tendances")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("**📅 Évolution des visites (6 mois)**")
        df_evol = get_evolution_visites()
        if not df_evol.empty:
            chart_data = df_evol.set_index('Mois')
            st.line_chart(chart_data)
        else:
            st.info("Pas assez de données")
    
    with col2:
        st.markdown("**📊 Répartition des statuts**")
        df_statuts = get_repartition_statuts()
        if not df_statuts.empty:
            for _, row in df_statuts.iterrows():
                statut = row['Statut']
                nb = row['Nombre']
                color = {
                    'ACTIF': '🟢',
                    'PROSPECT': '🔵',
                    'EN_PAUSE': '🟡',
                    'INACTIF': '⚪',
                    'PERDU': '🔴'
                }.get(statut, '⚪')
                st.markdown(f"{color} **{statut}** : {nb} magasins")
        else:
            st.info("Aucune donnée")
    
    st.markdown("---")
    
    st.markdown("**🏆 Top 10 Magasins les plus visités**")
    df_top = get_top_magasins()
    if not df_top.empty:
        st.dataframe(df_top, use_container_width=True, hide_index=True)
    else:
        st.info("Aucune donnée")

# ==========================================
# EXPORT
# ==========================================

st.markdown("---")
st.subheader("📥 Exports")

col1, col2, col3 = st.columns(3)

with col1:
    df_comm = get_stats_par_commercial()
    if not df_comm.empty:
        csv = df_comm.to_csv(index=False).encode('utf-8')
        st.download_button("📥 Stats Commerciaux (CSV)", csv, "stats_commerciaux.csv", "text/csv")

with col2:
    df_ens = get_stats_par_enseigne()
    if not df_ens.empty:
        csv = df_ens.to_csv(index=False).encode('utf-8')
        st.download_button("📥 Stats Enseignes (CSV)", csv, "stats_enseignes.csv", "text/csv")

with col3:
    df_dept = get_stats_par_departement()
    if not df_dept.empty:
        csv = df_dept.to_csv(index=False).encode('utf-8')
        st.download_button("📥 Stats Départements (CSV)", csv, "stats_departements.csv", "text/csv")

show_footer()
