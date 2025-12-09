import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from database import get_connection
from components import show_footer
from auth import is_authenticated, require_access
import plotly.express as px
import plotly.graph_objects as go
import requests
import io

st.set_page_config(page_title="CRM Statistiques - Culture Pom", page_icon="📈", layout="wide")

if not is_authenticated():
    st.warning("⚠️ Veuillez vous connecter")
    st.stop()

require_access("CRM")

# ✅ CSS CORRIGÉ - Cartes KPI uniformes avec hauteur fixe
st.markdown("""
<style>
    .block-container { padding-top: 1.5rem !important; padding-bottom: 0.5rem !important; }
    h1, h2, h3, h4 { margin-top: 0.3rem !important; margin-bottom: 0.3rem !important; }
    
    /* Cartes KPI uniformes */
    .kpi-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        padding: 1rem 0.8rem;
        border-radius: 10px;
        text-align: center;
        margin: 0.3rem;
        min-height: 100px;
        display: flex;
        flex-direction: column;
        justify-content: center;
        align-items: center;
    }
    .kpi-card h2 {
        color: white !important;
        margin: 0 !important;
        font-size: 1.8rem;
        line-height: 1.2;
    }
    .kpi-card p {
        color: rgba(255,255,255,0.9) !important;
        margin: 0.3rem 0 0 0 !important;
        font-size: 0.85rem;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
        max-width: 100%;
    }
</style>
""", unsafe_allow_html=True)

st.title("📈 CRM - Statistiques")
st.markdown("---")

# ==========================================
# FONCTIONS
# ==========================================

@st.cache_data(ttl=3600)
def get_france_geojson():
    """Charge le GeoJSON des départements français (avec cache)"""
    try:
        # GeoJSON officiel des départements français
        url = "https://raw.githubusercontent.com/gregoiredavid/france-geojson/master/departements.geojson"
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            return response.json()
        return None
    except Exception as e:
        st.warning(f"⚠️ Impossible de charger la carte : {e}")
        return None

def get_stats_globales():
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        stats = {}
        
        cursor.execute("SELECT COUNT(*) as nb FROM crm_magasins WHERE is_active = TRUE")
        stats['total_magasins'] = cursor.fetchone()['nb']
        
        cursor.execute("SELECT COUNT(*) as nb FROM crm_magasins WHERE is_active = TRUE AND statut = 'ACTIF'")
        stats['magasins_actifs'] = cursor.fetchone()['nb']
        
        cursor.execute("""
            SELECT COUNT(*) as nb FROM crm_visites 
            WHERE statut = 'EFFECTUEE'
            AND date_visite >= DATE_TRUNC('month', CURRENT_DATE)
        """)
        stats['visites_mois'] = cursor.fetchone()['nb']
        
        cursor.execute("""
            SELECT COUNT(*) as nb FROM crm_magasins 
            WHERE is_active = TRUE AND statut = 'ACTIF'
            AND date_derniere_visite >= CURRENT_DATE - INTERVAL '30 days'
        """)
        couverts = cursor.fetchone()['nb']
        stats['taux_couverture'] = round((couverts / stats['magasins_actifs'] * 100), 1) if stats['magasins_actifs'] > 0 else 0
        
        cursor.execute("SELECT COUNT(*) as nb FROM crm_animations WHERE statut = 'TERMINEE'")
        stats['animations_terminees'] = cursor.fetchone()['nb']
        
        cursor.close()
        conn.close()
        
        return stats
    except Exception as e:
        st.error(f"Erreur stats globales: {e}")
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
            LEFT JOIN crm_visites v ON c.id = v.commercial_id
            LEFT JOIN crm_animations a ON c.id = a.commercial_id
            WHERE c.is_active = TRUE
            GROUP BY c.id, c.prenom, c.nom
            ORDER BY visites_mois DESC
        """)
        
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        
        if rows:
            df = pd.DataFrame(rows)
            df.columns = ['id', 'Commercial', 'Clients', 'Actifs', 'Visites Mois', 'Visites 30j', 'Animations']
            return df
        return pd.DataFrame()
    except Exception as e:
        st.error(f"Erreur stats commerciaux: {e}")
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
                COUNT(DISTINCT v.id) FILTER (WHERE v.statut = 'EFFECTUEE') as nb_visites
            FROM crm_magasins m
            LEFT JOIN crm_visites v ON m.id = v.magasin_id
            WHERE m.is_active = TRUE
            GROUP BY m.enseigne
            ORDER BY nb_magasins DESC
            LIMIT 15
        """)
        
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        
        if rows:
            df = pd.DataFrame(rows)
            df.columns = ['Enseigne', 'Clients', 'Actifs', 'Visites']
            return df
        return pd.DataFrame()
    except Exception as e:
        st.error(f"Erreur stats enseignes: {e}")
        return pd.DataFrame()

def get_stats_par_departement():
    """Récupère les stats par département avec le code pour la carte"""
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
            LEFT JOIN crm_visites v ON m.id = v.magasin_id
            WHERE m.is_active = TRUE AND m.departement IS NOT NULL AND m.departement != ''
            GROUP BY m.departement
            ORDER BY nb_magasins DESC
        """)
        
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        
        if rows:
            df = pd.DataFrame(rows)
            df.columns = ['Département', 'Clients', 'Actifs', 'Visites 30j']
            # Normaliser les codes département (ajouter 0 devant si nécessaire)
            df['code'] = df['Département'].apply(lambda x: str(x).zfill(2) if x else '')
            return df
        return pd.DataFrame()
    except Exception as e:
        st.error(f"Erreur stats départements: {e}")
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
            WHERE statut = 'EFFECTUEE'
            AND date_visite >= CURRENT_DATE - INTERVAL '6 months'
            GROUP BY TO_CHAR(date_visite, 'YYYY-MM')
            ORDER BY mois
        """)
        
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        
        if rows:
            df = pd.DataFrame(rows)
            df.columns = ['Mois', 'Visites']
            return df
        return pd.DataFrame()
    except Exception as e:
        st.error(f"Erreur évolution visites: {e}")
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
            df = pd.DataFrame(rows)
            df.columns = ['Statut', 'Nombre']
            return df
        return pd.DataFrame()
    except Exception as e:
        st.error(f"Erreur répartition statuts: {e}")
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
            LEFT JOIN crm_visites v ON m.id = v.magasin_id AND v.statut = 'EFFECTUEE'
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
            df = pd.DataFrame(rows)
            df.columns = ['Client', 'Visites']
            return df
        return pd.DataFrame()
    except Exception as e:
        st.error(f"Erreur top magasins: {e}")
        return pd.DataFrame()

def create_france_map(df_dept, geojson, metric='Clients'):
    """Crée une carte choroplèthe de France par département"""
    
    if geojson is None or df_dept.empty:
        return None
    
    # Créer la carte
    fig = px.choropleth(
        df_dept,
        geojson=geojson,
        locations='code',
        featureidkey="properties.code",
        color=metric,
        color_continuous_scale="YlOrRd",  # Jaune -> Orange -> Rouge
        hover_name='Département',
        hover_data={
            'code': False,
            'Clients': True,
            'Actifs': True,
            'Visites 30j': True
        },
        labels={
            'Clients': 'Clients',
            'Actifs': 'Actifs',
            'Visites 30j': 'Visites 30j'
        }
    )
    
    # Centrer sur la France
    fig.update_geos(
        fitbounds="locations",
        visible=False,
        bgcolor='rgba(0,0,0,0)'
    )
    
    # Style
    fig.update_layout(
        title=dict(
            text=f"🗺️ Répartition des clients par département ({metric})",
            font=dict(size=16)
        ),
        margin={"r": 0, "t": 40, "l": 0, "b": 0},
        height=500,
        coloraxis_colorbar=dict(
            title=metric,
            tickfont=dict(size=10)
        ),
        paper_bgcolor='rgba(0,0,0,0)',
        geo=dict(
            showframe=False,
            showcoastlines=False,
            projection_type='mercator'
        )
    )
    
    return fig

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
            <p>🏪 Total Clients</p>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        st.markdown(f"""
        <div class="kpi-card">
            <h2>{stats['magasins_actifs']}</h2>
            <p>✅ Clients Actifs</p>
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
            <p>📊 Couverture 30j</p>
        </div>
        """, unsafe_allow_html=True)
    
    with col5:
        st.markdown(f"""
        <div class="kpi-card">
            <h2>{stats['animations_terminees']}</h2>
            <p>🎉 Animations</p>
        </div>
        """, unsafe_allow_html=True)
else:
    st.warning("⚠️ Impossible de charger les statistiques globales")

st.markdown("---")

# ==========================================
# ONGLETS
# ==========================================

tab1, tab2, tab3, tab4 = st.tabs(["👥 Par Commercial", "🏪 Par Enseigne", "🗺️ Par Département", "📈 Évolutions"])

with tab1:
    st.subheader("👥 Performance par Commercial")
    
    df_comm = get_stats_par_commercial()
    
    if not df_comm.empty:
        st.dataframe(df_comm.drop(columns=['id']), use_container_width=True, hide_index=True)
        
        st.markdown("---")
        st.markdown("**📊 Visites du mois par commercial**")
        
        # Graphique Plotly plus joli
        fig = px.bar(
            df_comm, 
            x='Commercial', 
            y='Visites Mois',
            color='Visites Mois',
            color_continuous_scale='Blues',
            text='Visites Mois'
        )
        fig.update_traces(textposition='outside')
        fig.update_layout(
            showlegend=False,
            coloraxis_showscale=False,
            height=400
        )
        st.plotly_chart(fig, use_container_width=True)
        
        # Commercial du mois
        if len(df_comm) > 0 and df_comm['Visites Mois'].notna().any():
            max_visites = df_comm['Visites Mois'].max()
            if pd.notna(max_visites) and max_visites > 0:
                best = df_comm.loc[df_comm['Visites Mois'].idxmax()]
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
        st.markdown("**📊 Top 10 enseignes par nombre de clients**")
        
        # Graphique Plotly
        fig = px.bar(
            df_enseigne.head(10), 
            x='Enseigne', 
            y='Clients',
            color='Clients',
            color_continuous_scale='Greens',
            text='Clients'
        )
        fig.update_traces(textposition='outside')
        fig.update_layout(
            showlegend=False,
            coloraxis_showscale=False,
            height=400,
            xaxis_tickangle=-45
        )
        st.plotly_chart(fig, use_container_width=True)
        
        # Export
        csv = df_enseigne.to_csv(index=False).encode('utf-8')
        st.download_button("📥 Exporter CSV", csv, "stats_enseignes.csv", "text/csv")
    else:
        st.info("Aucune donnée")

with tab3:
    st.subheader("🗺️ Répartition Géographique par Département")
    
    df_dept = get_stats_par_departement()
    
    if not df_dept.empty:
        # ⭐ CARTE DE FRANCE
        st.markdown("### 🗺️ Carte de France")
        
        # Sélecteur de métrique pour la carte
        col_metric, col_info = st.columns([1, 3])
        with col_metric:
            metric_carte = st.selectbox(
                "Colorier par",
                ['Clients', 'Actifs', 'Visites 30j'],
                key="metric_carte"
            )
        with col_info:
            st.info(f"💡 Survolez les départements pour voir les détails")
        
        # Charger GeoJSON
        geojson = get_france_geojson()
        
        if geojson:
            fig_map = create_france_map(df_dept, geojson, metric_carte)
            if fig_map:
                st.plotly_chart(fig_map, use_container_width=True)
            else:
                st.warning("⚠️ Impossible de générer la carte")
        else:
            st.warning("⚠️ Carte non disponible (vérifiez votre connexion internet)")
        
        st.markdown("---")
        
        # Tableau des départements
        st.markdown("### 📊 Détail par département")
        
        # Afficher sans la colonne 'code' technique
        df_display = df_dept[['Département', 'Clients', 'Actifs', 'Visites 30j']].copy()
        st.dataframe(df_display, use_container_width=True, hide_index=True)
        
        st.markdown("---")
        
        # Top 10 départements en graphique
        st.markdown("**📊 Top 10 départements**")
        
        fig = px.bar(
            df_dept.head(10), 
            x='Département', 
            y='Clients',
            color='Clients',
            color_continuous_scale='Oranges',
            text='Clients'
        )
        fig.update_traces(textposition='outside')
        fig.update_layout(
            showlegend=False,
            coloraxis_showscale=False,
            height=350
        )
        st.plotly_chart(fig, use_container_width=True)
        
        # Stats résumé
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("📍 Départements couverts", len(df_dept))
        with col2:
            st.metric("🏆 Dept. le plus dense", df_dept.iloc[0]['Département'] if len(df_dept) > 0 else "N/A")
        with col3:
            total_clients = df_dept['Clients'].sum()
            st.metric("📊 Total clients", int(total_clients))
        
        # Export
        csv = df_dept.to_csv(index=False).encode('utf-8')
        st.download_button("📥 Exporter CSV", csv, "stats_departements.csv", "text/csv")
    else:
        st.info("Aucune donnée de département disponible")

with tab4:
    st.subheader("📈 Évolutions et Répartitions")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("**📊 Évolution des visites (6 mois)**")
        df_evol = get_evolution_visites()
        
        if not df_evol.empty:
            fig = px.line(
                df_evol, 
                x='Mois', 
                y='Visites',
                markers=True,
                line_shape='spline'
            )
            fig.update_traces(
                line=dict(color='#667eea', width=3),
                marker=dict(size=10)
            )
            fig.update_layout(height=300)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Pas assez de données")
    
    with col2:
        st.markdown("**📊 Répartition par statut**")
        df_statuts = get_repartition_statuts()
        
        if not df_statuts.empty:
            # Camembert
            colors = {
                'ACTIF': '#2ca02c',
                'PROSPECT': '#1f77b4',
                'EN_PAUSE': '#ff7f0e',
                'INACTIF': '#7f7f7f',
                'PERDU': '#d62728'
            }
            df_statuts['color'] = df_statuts['Statut'].map(colors).fillna('#999999')
            
            fig = px.pie(
                df_statuts, 
                values='Nombre', 
                names='Statut',
                color='Statut',
                color_discrete_map=colors,
                hole=0.4
            )
            fig.update_layout(height=300)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Aucune donnée")
    
    st.markdown("---")
    st.markdown("**🏆 Top 10 clients les plus visités**")
    
    df_top = get_top_magasins()
    
    if not df_top.empty:
        fig = px.bar(
            df_top, 
            x='Visites', 
            y='Client',
            orientation='h',
            color='Visites',
            color_continuous_scale='Purples',
            text='Visites'
        )
        fig.update_traces(textposition='outside')
        fig.update_layout(
            showlegend=False,
            coloraxis_showscale=False,
            height=400,
            yaxis=dict(autorange="reversed")
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Aucune donnée")

show_footer()
