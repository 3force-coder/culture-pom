import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime
from database import get_connection
from components import show_header, show_footer
from auth import is_authenticated
import io

st.set_page_config(page_title="Stock - Culture Pom", page_icon="📦", layout="wide")

if not is_authenticated():
    st.warning("⚠️ Veuillez vous connecter pour accéder à cette page")
    st.stop()

show_header()
st.title("📦 Gestion du Stock de Lots")
st.markdown("---")

def load_stock_data():
    """Charge les données du stock AVEC jointures pour afficher les noms"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # ⭐ Requête avec jointures pour avoir nom_variete et nom_producteur
        query = """
            SELECT 
                l.id,
                l.code_lot_interne,
                l.nom_usage,
                l.code_variete,
                v.nom_variete,              
                l.code_producteur,
                p.nom as nom_producteur,     
                l.site_stockage,
                l.emplacement_stockage,
                l.nombre_unites,
                l.poids_unitaire_kg,         
                l.poids_total_brut_kg,       
                l.calibre_min,               
                l.calibre_max,               
                l.type_conditionnement,      
                l.date_entree_stock,
                l.age_jours,
                l.est_lave,
                l.est_bio,
                l.statut,
                l.poids_lave_net_kg,
                l.prix_achat_euro_tonne,
                l.valeur_lot_euro,
                l.is_active
            FROM lots_bruts l
            LEFT JOIN ref_varietes v ON l.code_variete = v.code_variete AND v.is_active = TRUE
            LEFT JOIN ref_producteurs p ON l.code_producteur = p.code_producteur AND p.is_active = TRUE
            WHERE l.is_active = TRUE
            ORDER BY l.date_entree_stock DESC
        """
        
        cursor.execute(query)
        rows = cursor.fetchall()
        column_names = [desc[0] for desc in cursor.description]
        cursor.close()
        conn.close()
        
        df = pd.DataFrame(rows, columns=column_names)
        return df
        
    except Exception as e:
        st.error(f"❌ Erreur chargement : {str(e)}")
        return pd.DataFrame()

def calculate_metrics(df):
    """Calcule les métriques"""
    if df.empty:
        return {'total_lots': 0, 'tonnage_total': 0.0, 'nb_varietes': 0, 'nb_producteurs': 0, 'age_moyen': 0, 'valeur_totale': 0.0}
    
    return {
        'total_lots': len(df),
        'tonnage_total': df['poids_total_brut_kg'].sum() / 1000 if 'poids_total_brut_kg' in df.columns else 0.0,
        'nb_varietes': df['code_variete'].nunique(),
        'nb_producteurs': df['code_producteur'].nunique(),
        'age_moyen': df['age_jours'].mean() if 'age_jours' in df.columns else 0,
        'valeur_totale': df['valeur_lot_euro'].sum() if 'valeur_lot_euro' in df.columns else 0.0
    }

def convert_to_native_types(value):
    """Convertit numpy types vers types Python natifs"""
    if pd.isna(value) or value is None:
        return None
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if isinstance(value, (np.integer, np.int64, np.int32, np.int16, np.int8)):
        return int(value)
    if isinstance(value, (np.floating, np.float64, np.float32)):
        return float(value)
    return value

def save_stock_changes(original_df, edited_df):
    """Sauvegarde les modifications"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        updates = 0
        
        # Colonnes éditables
        editable_columns = ['nom_usage', 'site_stockage', 'emplacement_stockage', 'nombre_unites', 
                           'poids_unitaire_kg', 'calibre_min', 'calibre_max', 'type_conditionnement',
                           'prix_achat_euro_tonne', 'valeur_lot_euro', 'statut']
        
        for idx in edited_df.index:
            if idx not in original_df.index:
                continue
                
            lot_id = convert_to_native_types(edited_df.loc[idx, 'id']) if 'id' in edited_df.columns else None
            if lot_id is None:
                continue
                
            changes = {}
            
            for col in editable_columns:
                if col not in edited_df.columns or col not in original_df.columns:
                    continue
                    
                old_val = original_df.loc[idx, col]
                new_val = edited_df.loc[idx, col]
                
                if pd.isna(old_val) and pd.isna(new_val):
                    continue
                elif pd.isna(old_val) or pd.isna(new_val) or old_val != new_val:
                    changes[col] = convert_to_native_types(new_val)
            
            if changes:
                set_clause = ", ".join([f"{col} = %s" for col in changes.keys()])
                values = list(changes.values()) + [lot_id]
                
                update_query = f"UPDATE lots_bruts SET {set_clause}, updated_at = CURRENT_TIMESTAMP WHERE id = %s"
                cursor.execute(update_query, values)
                updates += 1
        
        conn.commit()
        cursor.close()
        conn.close()
        return True, f"✅ {updates} lot(s) mis à jour"
        
    except Exception as e:
        if 'conn' in locals():
            conn.rollback()
        return False, f"❌ Erreur : {str(e)}"

# Charger données
df = load_stock_data()

if not df.empty:
    metrics = calculate_metrics(df)
    
    # KPIs
    st.subheader("📊 Indicateurs Clés")
    col1, col2, col3, col4, col5, col6 = st.columns(6)
    
    with col1:
        st.metric("📦 Lots actifs", f"{metrics['total_lots']:,}".replace(',', ' '))
    with col2:
        st.metric("⚖️ Tonnage total", f"{metrics['tonnage_total']:.1f} t")
    with col3:
        st.metric("🌱 Variétés", metrics['nb_varietes'])
    with col4:
        st.metric("👨‍🌾 Producteurs", metrics['nb_producteurs'])
    with col5:
        st.metric("📅 Âge moyen", f"{metrics['age_moyen']:.0f} j")
    with col6:
        st.metric("💰 Valeur totale", f"{metrics['valeur_totale']:,.0f} €".replace(',', ' '))
    
    st.markdown("---")
    
    # Filtres - 6 filtres avec NOMS
    st.subheader("🔍 Filtres")
    col1, col2, col3, col4, col5, col6 = st.columns(6)
    
    with col1:
        # Filtre nom_usage (recherche texte)
        search_nom = st.text_input("Nom usage", key="filter_nom_usage", placeholder="Rechercher...")
    
    with col2:
        # Filtre variété - afficher NOM
        varietes = ['Toutes'] + sorted(df['nom_variete'].dropna().unique().tolist())
        selected_variete = st.selectbox("Variété", varietes, key="filter_variete")
    
    with col3:
        # Filtre producteur - afficher NOM
        producteurs = ['Tous'] + sorted(df['nom_producteur'].dropna().unique().tolist())
        selected_producteur = st.selectbox("Producteur", producteurs, key="filter_producteur")
    
    with col4:
        sites = ['Tous'] + sorted(df['site_stockage'].dropna().unique().tolist())
        selected_site = st.selectbox("Site", sites, key="filter_site")
    
    with col5:
        emplacements = ['Tous'] + sorted(df['emplacement_stockage'].dropna().unique().tolist())
        selected_emplacement = st.selectbox("Emplacement", emplacements, key="filter_emplacement")
    
    with col6:
        statuts = ['Tous', 'EN_STOCK', 'SORTI', 'RESERVE', 'BLOQUE']
        selected_statut = st.selectbox("Statut", statuts, key="filter_statut")
    
    # Appliquer filtres
    filtered_df = df.copy()
    
    if search_nom:
        filtered_df = filtered_df[filtered_df['nom_usage'].str.contains(search_nom, case=False, na=False)]
    
    if selected_variete != 'Toutes':
        filtered_df = filtered_df[filtered_df['nom_variete'] == selected_variete]
    
    if selected_producteur != 'Tous':
        filtered_df = filtered_df[filtered_df['nom_producteur'] == selected_producteur]
    
    if selected_site != 'Tous':
        filtered_df = filtered_df[filtered_df['site_stockage'] == selected_site]
    
    if selected_emplacement != 'Tous':
        filtered_df = filtered_df[filtered_df['emplacement_stockage'] == selected_emplacement]
    
    if selected_statut != 'Tous':
        filtered_df = filtered_df[filtered_df['statut'] == selected_statut]
    
    st.markdown("---")
    st.info(f"📊 {len(filtered_df)} lot(s) affiché(s) sur {len(df)} total")
    
    if 'original_stock_df' not in st.session_state:
        st.session_state.original_stock_df = filtered_df.copy()
    
    # Tableau avec NOMS et nouvelles colonnes
    st.subheader("📋 Liste des Lots")
    
    # Colonnes à afficher (avec NOMS et nouvelles colonnes)
    display_columns = [
        'code_lot_interne', 
        'nom_usage', 
        'nom_variete',              # NOM au lieu de code_variete
        'nom_producteur',           # NOM au lieu de code_producteur
        'site_stockage', 
        'emplacement_stockage',
        'nombre_unites',
        'poids_unitaire_kg',        
        'poids_total_brut_kg',      
        'calibre_min',              
        'calibre_max',              
        'type_conditionnement',     
        'age_jours',
        'statut'
    ]
    
    available_columns = [col for col in display_columns if col in filtered_df.columns]
    display_df = filtered_df[available_columns].copy()
    
    edited_df = st.data_editor(
        display_df,
        use_container_width=True,
        num_rows="fixed",
        disabled=['code_lot_interne', 'nom_variete', 'nom_producteur', 'age_jours', 'poids_total_brut_kg'],  # Noms + calculées en lecture seule
        key="stock_editor"
    )
    
    # Boutons
    col1, col2 = st.columns([1, 5])
    with col1:
        if st.button("💾 Enregistrer", use_container_width=True, type="primary"):
            success, message = save_stock_changes(st.session_state.original_stock_df, edited_df)
            if success:
                st.success(message)
                st.session_state.pop('original_stock_df', None)
                st.rerun()
            else:
                st.error(message)
    with col2:
        if st.button("🔄 Actualiser", use_container_width=True):
            st.session_state.pop('original_stock_df', None)
            st.rerun()
    
    # Alertes
    st.markdown("---")
    st.subheader("⚠️ Alertes")
    col1, col2 = st.columns(2)
    
    with col1:
        old_lots = df[df['age_jours'] > 90] if 'age_jours' in df.columns else pd.DataFrame()
        if not old_lots.empty:
            st.warning(f"⚠️ {len(old_lots)} lot(s) >90 jours")
            alert_df = old_lots[['code_lot_interne', 'nom_variete', 'age_jours']].head(5)
            st.dataframe(alert_df, use_container_width=True, hide_index=True)
        else:
            st.success("✅ Aucun lot ancien")
    
    with col2:
        no_variety = df[df['code_variete'].isna()]
        if not no_variety.empty:
            st.warning(f"⚠️ {len(no_variety)} lot(s) sans variété")
        else:
            st.success("✅ Tous avec variété")
    
    # Exports
    st.markdown("---")
    st.subheader("📤 Exports")
    col1, col2 = st.columns(2)
    
    with col1:
        csv = filtered_df.to_csv(index=False).encode('utf-8')
        st.download_button("📥 CSV", csv, f"stock_{datetime.now().strftime('%Y%m%d')}.csv", "text/csv", use_container_width=True)
    
    with col2:
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            filtered_df.to_excel(writer, index=False, sheet_name='Stock')
        st.download_button("📥 Excel", buffer.getvalue(), f"stock_{datetime.now().strftime('%Y%m%d')}.xlsx", 
                          "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)
else:
    st.warning("⚠️ Aucun lot trouvé")

show_footer()
