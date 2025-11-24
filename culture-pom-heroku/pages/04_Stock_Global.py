import streamlit as st
import pandas as pd
from datetime import datetime
from database import get_connection
from components import show_footer
from auth import is_authenticated
import io

# CSS compact
st.markdown("""
<style>
    .block-container {
        padding-top: 2rem !important;
        padding-bottom: 0.5rem !important;
    }
    h1, h2, h3, h4 {
        margin-top: 0.3rem !important;
        margin-bottom: 0.3rem !important;
    }
    .stMetric {
        background-color: #f0f2f6;
        padding: 1rem;
        border-radius: 0.5rem;
    }
</style>
""", unsafe_allow_html=True)

if not is_authenticated():
    st.warning("⚠️ Veuillez vous connecter pour accéder à cette page")
    st.stop()

st.title("📊 Stock Global")
st.markdown("*Vue d'ensemble du stock tous lots confondus*")
st.markdown("---")

# ==========================================
# FONCTIONS DE RÉCUPÉRATION DE DONNÉES
# ==========================================

def get_stock_global_kpis():
    """Récupère les KPIs globaux du stock"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Tonnage total
        cursor.execute("""
            SELECT COALESCE(SUM(poids_total_kg), 0) as tonnage_total
            FROM stock_emplacements
            WHERE is_active = TRUE
        """)
        tonnage_total = cursor.fetchone()['tonnage_total'] / 1000  # Conversion en tonnes
        
        # Nombre de lots avec stock
        cursor.execute("""
            SELECT COUNT(DISTINCT lot_id) as nb_lots
            FROM stock_emplacements
            WHERE is_active = TRUE AND nombre_unites > 0
        """)
        nb_lots = cursor.fetchone()['nb_lots']
        
        # Nombre d'emplacements actifs
        cursor.execute("""
            SELECT COUNT(*) as nb_emplacements
            FROM stock_emplacements
            WHERE is_active = TRUE AND nombre_unites > 0
        """)
        nb_emplacements = cursor.fetchone()['nb_emplacements']
        
        # Nombre de sites utilisés
        cursor.execute("""
            SELECT COUNT(DISTINCT site_stockage) as nb_sites
            FROM stock_emplacements
            WHERE is_active = TRUE AND nombre_unites > 0
        """)
        nb_sites = cursor.fetchone()['nb_sites']
        
        # Nombre total de pallox
        cursor.execute("""
            SELECT COALESCE(SUM(nombre_unites), 0) as total_pallox
            FROM stock_emplacements
            WHERE is_active = TRUE
        """)
        total_pallox = cursor.fetchone()['total_pallox']
        
        cursor.close()
        conn.close()
        
        return {
            'tonnage_total': tonnage_total,
            'nb_lots': nb_lots,
            'nb_emplacements': nb_emplacements,
            'nb_sites': nb_sites,
            'total_pallox': total_pallox
        }
        
    except Exception as e:
        st.error(f"❌ Erreur chargement KPIs : {str(e)}")
        return None

def get_stock_par_site():
    """Récupère le stock agrégé par site"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        query = """
        SELECT 
            site_stockage,
            COUNT(DISTINCT emplacement_stockage) as nb_emplacements,
            COUNT(DISTINCT lot_id) as nb_lots,
            SUM(nombre_unites) as total_pallox,
            SUM(poids_total_kg) as total_poids_kg
        FROM stock_emplacements
        WHERE is_active = TRUE AND nombre_unites > 0
        GROUP BY site_stockage
        ORDER BY site_stockage
        """
        
        cursor.execute(query)
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        
        if rows:
            # Créer DataFrame directement depuis les dictionnaires
            df = pd.DataFrame(rows)
            # Renommer les colonnes
            df = df.rename(columns={
                'site_stockage': 'Site',
                'nb_emplacements': 'Nb Emplacements',
                'nb_lots': 'Nb Lots',
                'total_pallox': 'Total Pallox',
                'total_poids_kg': 'Poids (kg)'
            })
            
            # Forcer la conversion en types numériques
            df['Nb Emplacements'] = pd.to_numeric(df['Nb Emplacements'], errors='coerce').fillna(0).astype(int)
            df['Nb Lots'] = pd.to_numeric(df['Nb Lots'], errors='coerce').fillna(0).astype(int)
            df['Total Pallox'] = pd.to_numeric(df['Total Pallox'], errors='coerce').fillna(0).astype(int)
            df['Poids (kg)'] = pd.to_numeric(df['Poids (kg)'], errors='coerce').fillna(0)
            
            # Conversion poids en tonnes
            df['Poids (T)'] = df['Poids (kg)'] / 1000
            df = df.drop(columns=['Poids (kg)'])
            # Arrondir
            df['Poids (T)'] = df['Poids (T)'].round(1)
            return df
        
        return pd.DataFrame()
        
    except Exception as e:
        st.error(f"❌ Erreur chargement stock par site : {str(e)}")
        return pd.DataFrame()

def get_stock_par_variete():
    """Récupère le stock agrégé par variété"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        query = """
        SELECT 
            COALESCE(v.nom_variete, l.code_variete, 'Non défini') as variete,
            COUNT(DISTINCT se.lot_id) as nb_lots,
            COUNT(DISTINCT se.id) as nb_emplacements,
            SUM(se.nombre_unites) as total_pallox,
            SUM(se.poids_total_kg) as total_poids_kg
        FROM stock_emplacements se
        LEFT JOIN lots_bruts l ON se.lot_id = l.id
        LEFT JOIN ref_varietes v ON l.code_variete = v.code_variete
        WHERE se.is_active = TRUE AND se.nombre_unites > 0
        GROUP BY variete
        ORDER BY variete
        """
        
        cursor.execute(query)
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        
        if rows:
            # Créer DataFrame directement depuis les dictionnaires
            df = pd.DataFrame(rows)
            # Renommer les colonnes
            df = df.rename(columns={
                'variete': 'Variété',
                'nb_lots': 'Nb Lots',
                'nb_emplacements': 'Nb Emplacements',
                'total_pallox': 'Total Pallox',
                'total_poids_kg': 'Poids (kg)'
            })
            
            # Forcer la conversion en types numériques
            df['Nb Lots'] = pd.to_numeric(df['Nb Lots'], errors='coerce').fillna(0).astype(int)
            df['Nb Emplacements'] = pd.to_numeric(df['Nb Emplacements'], errors='coerce').fillna(0).astype(int)
            df['Total Pallox'] = pd.to_numeric(df['Total Pallox'], errors='coerce').fillna(0).astype(int)
            df['Poids (kg)'] = pd.to_numeric(df['Poids (kg)'], errors='coerce').fillna(0)
            
            # Conversion poids en tonnes
            df['Poids (T)'] = df['Poids (kg)'] / 1000
            df = df.drop(columns=['Poids (kg)'])
            # Arrondir
            df['Poids (T)'] = df['Poids (T)'].round(1)
            return df
        
        return pd.DataFrame()
        
    except Exception as e:
        st.error(f"❌ Erreur chargement stock par variété : {str(e)}")
        return pd.DataFrame()

def get_stock_par_producteur():
    """Récupère le stock agrégé par producteur"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        query = """
        SELECT 
            COALESCE(p.nom, 'Non défini') as producteur,
            COUNT(DISTINCT se.lot_id) as nb_lots,
            COUNT(DISTINCT se.id) as nb_emplacements,
            SUM(se.nombre_unites) as total_pallox,
            SUM(se.poids_total_kg) as total_poids_kg
        FROM stock_emplacements se
        LEFT JOIN lots_bruts l ON se.lot_id = l.id
        LEFT JOIN ref_producteurs p ON l.code_producteur = p.code_producteur
        WHERE se.is_active = TRUE AND se.nombre_unites > 0
        GROUP BY producteur
        ORDER BY producteur
        """
        
        cursor.execute(query)
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        
        if rows:
            # Créer DataFrame directement depuis les dictionnaires
            df = pd.DataFrame(rows)
            # Renommer les colonnes
            df = df.rename(columns={
                'producteur': 'Producteur',
                'nb_lots': 'Nb Lots',
                'nb_emplacements': 'Nb Emplacements',
                'total_pallox': 'Total Pallox',
                'total_poids_kg': 'Poids (kg)'
            })
            
            # Forcer la conversion en types numériques
            df['Nb Lots'] = pd.to_numeric(df['Nb Lots'], errors='coerce').fillna(0).astype(int)
            df['Nb Emplacements'] = pd.to_numeric(df['Nb Emplacements'], errors='coerce').fillna(0).astype(int)
            df['Total Pallox'] = pd.to_numeric(df['Total Pallox'], errors='coerce').fillna(0).astype(int)
            df['Poids (kg)'] = pd.to_numeric(df['Poids (kg)'], errors='coerce').fillna(0)
            
            # Conversion poids en tonnes
            df['Poids (T)'] = df['Poids (kg)'] / 1000
            df = df.drop(columns=['Poids (kg)'])
            # Arrondir
            df['Poids (T)'] = df['Poids (T)'].round(1)
            return df
        
        return pd.DataFrame()
        
    except Exception as e:
        st.error(f"❌ Erreur chargement stock par producteur : {str(e)}")
        return pd.DataFrame()

# ==========================================
# AFFICHAGE - KPIs GLOBAUX
# ==========================================

kpis = get_stock_global_kpis()

if kpis:
    col1, col2, col3, col4, col5 = st.columns(5)
    
    with col1:
        st.metric("📦 Total Pallox", f"{int(kpis['total_pallox']):,}")
    
    with col2:
        st.metric("⚖️ Tonnage Total", f"{kpis['tonnage_total']:,.1f} T")
    
    with col3:
        st.metric("🎯 Lots en Stock", f"{kpis['nb_lots']}")
    
    with col4:
        st.metric("📍 Emplacements", f"{kpis['nb_emplacements']}")
    
    with col5:
        st.metric("🏭 Sites Utilisés", f"{kpis['nb_sites']}")

st.markdown("---")

# ==========================================
# AFFICHAGE - ONGLETS
# ==========================================

tab1, tab2, tab3 = st.tabs(["📍 Par Site", "🌱 Par Variété", "👤 Par Producteur"])

# ==========================================
# ONGLET 1 - PAR SITE
# ==========================================

with tab1:
    st.subheader("📍 Stock par Site")
    
    df_site = get_stock_par_site()
    
    if not df_site.empty:
        # Affichage tableau
        st.dataframe(
            df_site,
            use_container_width=True,
            hide_index=True
        )
        
        # Résumé
        col1, col2 = st.columns(2)
        with col1:
            st.info(f"**{len(df_site)} sites** utilisés")
        with col2:
            total_emplacements = df_site['Nb Emplacements'].sum()
            st.info(f"**{int(total_emplacements)} emplacements** au total")
        
        # Export Excel
        st.markdown("---")
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            df_site.to_excel(writer, index=False, sheet_name='Stock par Site')
        
        st.download_button(
            "📥 Exporter en Excel",
            buffer.getvalue(),
            f"stock_par_site_{datetime.now().strftime('%Y%m%d')}.xlsx",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True
        )
    else:
        st.warning("⚠️ Aucun stock trouvé")

# ==========================================
# ONGLET 2 - PAR VARIÉTÉ
# ==========================================

with tab2:
    st.subheader("🌱 Stock par Variété")
    
    df_variete = get_stock_par_variete()
    
    if not df_variete.empty:
        # Affichage tableau
        st.dataframe(
            df_variete,
            use_container_width=True,
            hide_index=True
        )
        
        # Résumé
        col1, col2 = st.columns(2)
        with col1:
            st.info(f"**{len(df_variete)} variétés** en stock")
        with col2:
            total_lots = df_variete['Nb Lots'].sum()
            st.info(f"**{int(total_lots)} lots** au total")
        
        # Export Excel
        st.markdown("---")
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            df_variete.to_excel(writer, index=False, sheet_name='Stock par Variété')
        
        st.download_button(
            "📥 Exporter en Excel",
            buffer.getvalue(),
            f"stock_par_variete_{datetime.now().strftime('%Y%m%d')}.xlsx",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True
        )
    else:
        st.warning("⚠️ Aucun stock trouvé")

# ==========================================
# ONGLET 3 - PAR PRODUCTEUR
# ==========================================

with tab3:
    st.subheader("👤 Stock par Producteur")
    
    df_producteur = get_stock_par_producteur()
    
    if not df_producteur.empty:
        # Affichage tableau
        st.dataframe(
            df_producteur,
            use_container_width=True,
            hide_index=True
        )
        
        # Résumé
        col1, col2 = st.columns(2)
        with col1:
            st.info(f"**{len(df_producteur)} producteurs** actifs")
        with col2:
            total_lots = df_producteur['Nb Lots'].sum()
            st.info(f"**{int(total_lots)} lots** au total")
        
        # Export Excel
        st.markdown("---")
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            df_producteur.to_excel(writer, index=False, sheet_name='Stock par Producteur')
        
        st.download_button(
            "📥 Exporter en Excel",
            buffer.getvalue(),
            f"stock_par_producteur_{datetime.now().strftime('%Y%m%d')}.xlsx",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True
        )
    else:
        st.warning("⚠️ Aucun stock trouvé")

show_footer()
