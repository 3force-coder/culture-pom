import streamlit as st
import pandas as pd
import json
from datetime import datetime
from database import get_connection
from components import show_header, show_footer
from auth import is_authenticated, is_admin
from io import BytesIO

st.set_page_config(
    page_title="Culture Pom - Stock",
    page_icon="📦",
    layout="wide"
)

# Logo
st.logo('https://i.imgur.com/kuLXrHZ.png')

# Contrôle ADMIN
if not is_authenticated():
    st.warning("⚠️ Veuillez vous connecter")
    st.stop()

if not is_admin():
    st.error("🔒 Accès réservé aux administrateurs")
    st.stop()


def get_stock_data():
    """Récupère les lots actifs - VERSION SIMPLE"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Sélectionner seulement les colonnes principales
        query = """
            SELECT 
                id,
                code_lot_interne,
                nom_usage,
                code_variete,
                code_producteur,
                date_entree_stock,
                age_jours,
                poids_lave_net_kg,
                site_stockage,
                statut,
                est_lave,
                est_bio,
                is_active
            FROM lots_bruts 
            WHERE is_active = TRUE 
            ORDER BY date_entree_stock DESC
        """
        
        cursor.execute(query)
        rows = cursor.fetchall()
        columns = [desc[0] for desc in cursor.description]
        
        cursor.close()
        conn.close()
        
        if rows:
            # Créer DataFrame
            data = []
            for row in rows:
                row_dict = dict(zip(columns, row))
                data.append(row_dict)
            
            df = pd.DataFrame(data)
            
            # Convertir les types
            if 'poids_lave_net_kg' in df.columns:
                df['poids_lave_net_kg'] = pd.to_numeric(df['poids_lave_net_kg'], errors='coerce')
            if 'age_jours' in df.columns:
                df['age_jours'] = pd.to_numeric(df['age_jours'], errors='coerce')
            
            return df
        else:
            return pd.DataFrame()
            
    except Exception as e:
        st.error(f"❌ Erreur chargement : {str(e)}")
        return pd.DataFrame()


def main():
    show_header("Stock", "Gestion des lots de pommes de terre")
    
    # Charger les données
    df = get_stock_data()
    
    if df.empty:
        st.warning("⚠️ Aucun lot actif")
        show_footer()
        return
    
    # Métriques
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("📦 Lots actifs", len(df))
    
    with col2:
        tonnage = df['poids_lave_net_kg'].sum() / 1000 if 'poids_lave_net_kg' in df.columns else 0
        st.metric("⚖️ Tonnage", f"{tonnage:,.1f} T")
    
    with col3:
        varietes = df['code_variete'].nunique() if 'code_variete' in df.columns else 0
        st.metric("🌾 Variétés", varietes)
    
    st.markdown("---")
    
    # Filtres simples
    col_f1, col_f2, col_f3 = st.columns(3)
    
    with col_f1:
        search = st.text_input("🔍 Rechercher", placeholder="Code, variété...")
    
    with col_f2:
        varietes_list = ['Toutes'] + sorted(df['code_variete'].dropna().unique().tolist())
        variete_filter = st.selectbox("Variété", varietes_list)
    
    with col_f3:
        sites_list = ['Tous'] + sorted(df['site_stockage'].dropna().unique().tolist())
        site_filter = st.selectbox("Site", sites_list)
    
    # Appliquer filtres
    df_filtered = df.copy()
    
    if search:
        mask = df_filtered.astype(str).apply(
            lambda row: row.str.contains(search, case=False, na=False).any(), 
            axis=1
        )
        df_filtered = df_filtered[mask]
    
    if variete_filter != 'Toutes':
        df_filtered = df_filtered[df_filtered['code_variete'] == variete_filter]
    
    if site_filter != 'Tous':
        df_filtered = df_filtered[df_filtered['site_stockage'] == site_filter]
    
    st.markdown(f"**{len(df_filtered)}** lots affichés")
    
    # AFFICHER LES DONNÉES - TEST
    st.markdown("### 📋 Données")
    
    # D'abord avec dataframe simple pour VOIR si les données arrivent
    st.dataframe(
        df_filtered,
        use_container_width=True,
        height=600
    )
    
    st.info("ℹ️ Tableau en lecture seule pour l'instant - Version de diagnostic")
    st.caption(f"Colonnes : {', '.join(df_filtered.columns)}")
    st.caption(f"Nombre de lignes chargées : {len(df_filtered)}")
    
    # Boutons exports
    st.markdown("### 📥 Exports")
    col_e1, col_e2 = st.columns(2)
    
    with col_e1:
        csv = df_filtered.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Télécharger CSV",
            data=csv,
            file_name=f"stock_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv",
            use_container_width=True
        )
    
    with col_e2:
        try:
            output = BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df_filtered.to_excel(writer, index=False, sheet_name='Stock')
            output.seek(0)
            
            st.download_button(
                label="📥 Télécharger Excel",
                data=output.getvalue(),
                file_name=f"stock_{datetime.now().strftime('%Y%m%d')}.xlsx",
                mime="application/vnd.ms-excel",
                use_container_width=True
            )
        except Exception as e:
            st.error(f"Export Excel : {str(e)}")
    
    show_footer()


if __name__ == "__main__":
    main()