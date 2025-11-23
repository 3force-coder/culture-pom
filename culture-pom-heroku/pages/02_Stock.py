import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime
from database import get_connection
from components import show_footer
from auth import is_authenticated
import io

st.set_page_config(page_title="Stock - Culture Pom", page_icon="📦", layout="wide")

# CSS custom pour réduire FORTEMENT les espacements
st.markdown("""
<style>
    .block-container {
        padding-top: 2rem !important;
        padding-bottom: 0.5rem !important;
        padding-left: 2rem !important;
        padding-right: 2rem !important;
    }
    
    h1, h2, h3, h4 {
        margin-top: 0.3rem !important;
        margin-bottom: 0.3rem !important;
        padding-top: 0 !important;
        padding-bottom: 0 !important;
    }
    
    .stSelectbox, .stButton, .stCheckbox, .stTextInput {
        margin-bottom: 0.3rem !important;
        margin-top: 0.3rem !important;
    }
    
    .stDataFrame {
        margin-top: 0.5rem !important;
        margin-bottom: 0.5rem !important;
    }
    
    [data-testid="stMetricValue"] {
        font-size: 1.4rem !important;
    }
    
    [data-testid="metric-container"] {
        padding: 0.3rem !important;
    }
    
    hr {
        margin-top: 0.5rem !important;
        margin-bottom: 0.5rem !important;
    }
    
    [data-testid="column"] {
        padding: 0.2rem !important;
    }
    
    .stSubheader {
        margin-top: 0.3rem !important;
        margin-bottom: 0.3rem !important;
    }
</style>
""", unsafe_allow_html=True)

if not is_authenticated():
    st.warning("⚠️ Veuillez vous connecter pour accéder à cette page")
    st.stop()

st.title("📦 Gestion du Stock de Lots")
st.markdown("---")

def get_all_varietes_for_dropdown():
    """Récupère TOUTES les variétés actives (nom + code) pour dropdown édition"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT code_variete, nom_variete 
            FROM ref_varietes 
            WHERE is_active = TRUE 
            ORDER BY nom_variete
        """)
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        return {row['nom_variete']: row['code_variete'] for row in rows}
    except Exception as e:
        st.error(f"❌ Erreur variétés : {str(e)}")
        return {}

def get_all_producteurs_for_dropdown():
    """Récupère TOUS les producteurs actifs (nom + code) pour dropdown édition"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT code_producteur, nom 
            FROM ref_producteurs 
            WHERE is_active = TRUE 
            ORDER BY nom
        """)
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        return {row['nom']: row['code_producteur'] for row in rows}
    except Exception as e:
        st.error(f"❌ Erreur producteurs : {str(e)}")
        return {}

def get_all_sites_for_dropdown():
    """Récupère TOUS les sites de stockage actifs pour dropdown édition"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT DISTINCT code_site 
            FROM ref_sites_stockage 
            WHERE is_active = TRUE 
            ORDER BY code_site
        """)
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        return [row['code_site'] for row in rows]
    except Exception as e:
        st.error(f"❌ Erreur sites : {str(e)}")
        return []

def get_all_emplacements_for_dropdown():
    """Récupère TOUS les emplacements de stockage actifs pour dropdown édition"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT DISTINCT code_emplacement 
            FROM ref_sites_stockage 
            WHERE is_active = TRUE 
            ORDER BY code_emplacement
        """)
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        return [row['code_emplacement'] for row in rows]
    except Exception as e:
        st.error(f"❌ Erreur emplacements : {str(e)}")
        return []

def load_stock_data():
    """Charge les données du stock AVEC jointures BIDIRECTIONNELLES"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
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
            LEFT JOIN ref_varietes v ON 
                (l.code_variete = v.code_variete OR l.code_variete = v.nom_variete)
                AND v.is_active = TRUE
            LEFT JOIN ref_producteurs p ON 
                (l.code_producteur = p.code_producteur OR l.code_producteur = p.nom)
                AND p.is_active = TRUE
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
    """Calcule les métriques KPI"""
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

def save_stock_changes(original_df, edited_df, varietes_dict, producteurs_dict):
    """Sauvegarde les modifications avec conversion NOM → CODE pour variétés/producteurs"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        updates = 0
        
        varietes_reverse = {v: k for k, v in varietes_dict.items()}
        producteurs_reverse = {v: k for k, v in producteurs_dict.items()}
        
        editable_display_columns = ['nom_usage', 'nom_variete', 'nom_producteur', 'site_stockage', 
                                    'emplacement_stockage', 'nombre_unites', 'poids_unitaire_kg', 
                                    'calibre_min', 'calibre_max', 'type_conditionnement',
                                    'prix_achat_euro_tonne', 'valeur_lot_euro', 'statut']
        
        for idx in edited_df.index:
            if idx not in original_df.index:
                continue
                
            lot_id = convert_to_native_types(original_df.loc[idx, 'id'])
            changes = {}
            
            for col in editable_display_columns:
                if col not in edited_df.columns or col not in original_df.columns:
                    continue
                    
                old_val = original_df.loc[idx, col]
                new_val = edited_df.loc[idx, col]
                
                has_changed = False
                if pd.isna(old_val) and pd.isna(new_val):
                    has_changed = False
                elif pd.isna(old_val) or pd.isna(new_val):
                    has_changed = True
                elif old_val != new_val:
                    has_changed = True
                
                if has_changed:
                    if col == 'nom_variete':
                        if pd.notna(new_val) and new_val != '':
                            changes['code_variete'] = varietes_reverse.get(new_val, new_val)
                        else:
                            changes['code_variete'] = None
                    elif col == 'nom_producteur':
                        if pd.notna(new_val) and new_val != '':
                            changes['code_producteur'] = producteurs_reverse.get(new_val, new_val)
                        else:
                            changes['code_producteur'] = None
                    else:
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
        
        if updates == 0:
            return False, "ℹ️ Aucune modification détectée"
        return True, f"✅ {updates} lot(s) mis à jour"
        
    except Exception as e:
        if 'conn' in locals():
            conn.rollback()
        return False, f"❌ Erreur : {str(e)}"

# Charger données
df = load_stock_data()

# ⭐ FIX DOUBLONS : Supprimer les doublons basés sur l'ID
if not df.empty:
    initial_count = len(df)
    df = df.drop_duplicates(subset=['id'], keep='first')
    df = df.reset_index(drop=True)
    duplicates_removed = initial_count - len(df)
    if duplicates_removed > 0:
        st.warning(f"⚠️ {duplicates_removed} doublon(s) supprimé(s) de l'affichage")

# Formulaire d'ajout (masqué par défaut)
if st.session_state.get('show_add_form', False):
    st.subheader("➕ Ajouter un lot")
    st.info("📌 Formulaire d'ajout en construction - Étape 2")
    
    col1, col2 = st.columns([1, 5])
    with col1:
        if st.button("❌ Annuler", use_container_width=True):
            st.session_state.show_add_form = False
            st.rerun()
    
    st.markdown("---")

if not df.empty:
    # Récupérer tous les dropdowns
    varietes_dict = get_all_varietes_for_dropdown()
    producteurs_dict = get_all_producteurs_for_dropdown()
    sites_list = get_all_sites_for_dropdown()
    emplacements_list = get_all_emplacements_for_dropdown()
    
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
    
    # Filtres
    st.subheader("🔍 Filtres")
    col1, col2, col3, col4, col5, col6 = st.columns(6)
    
    with col1:
        search_nom = st.text_input("Nom usage", key="filter_nom_usage", placeholder="Rechercher...")
    
    with col2:
        varietes = ['Toutes'] + sorted(df['nom_variete'].dropna().unique().tolist())
        selected_variete = st.selectbox("Variété", varietes, key="filter_variete")
    
    with col3:
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
    
    # En-tête tableau
    col_title, col_button = st.columns([4, 1])
    with col_title:
        st.subheader("📋 Liste des Lots")
    with col_button:
        if st.button("➕ Ajouter", use_container_width=True, type="primary"):
            st.session_state.show_add_form = not st.session_state.get('show_add_form', False)
            st.rerun()
    
    # Colonnes à afficher
    display_columns = [
        'code_lot_interne', 
        'nom_usage', 
        'code_variete',
        'nom_variete',
        'code_producteur',
        'nom_producteur',
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
    
    # Configuration dropdowns
    column_config = {
        "code_variete": None,
        "code_producteur": None,
        "nom_variete": st.column_config.SelectboxColumn(
            "Variété",
            options=sorted(varietes_dict.keys()),
            required=False
        ),
        "nom_producteur": st.column_config.SelectboxColumn(
            "Producteur",
            options=sorted(producteurs_dict.keys()),
            required=False
        ),
        "site_stockage": st.column_config.SelectboxColumn(
            "Site",
            options=sorted(sites_list),
            required=False
        ),
        "emplacement_stockage": st.column_config.SelectboxColumn(
            "Emplacement",
            options=sorted(emplacements_list),
            required=False
        )
    }
    
    edited_df = st.data_editor(
        display_df,
        use_container_width=True,
        num_rows="fixed",
        disabled=['code_lot_interne', 'code_variete', 'code_producteur', 'age_jours', 'poids_total_brut_kg'],
        column_config=column_config,
        key="stock_editor"
    )
    
    # Boutons
    col1, col2 = st.columns([1, 5])
    with col1:
        if st.button("💾 Enregistrer", use_container_width=True, type="primary"):
            success, message = save_stock_changes(st.session_state.original_stock_df, edited_df, varietes_dict, producteurs_dict)
            if success:
                st.success(message)
                st.session_state.pop('original_stock_df', None)
                st.rerun()
            else:
                if "Aucune modification" in message:
                    st.info(message)
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
        no_variety = df[df['nom_variete'].isna() | (df['nom_variete'] == '')]
        if not no_variety.empty:
            st.warning(f"⚠️ {len(no_variety)} lot(s) sans variété")
            alert_variety_df = no_variety[['code_lot_interne', 'nom_usage']].head(5)
            st.dataframe(alert_variety_df, use_container_width=True, hide_index=True)
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
