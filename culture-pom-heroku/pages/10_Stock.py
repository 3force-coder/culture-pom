import streamlit as st
import pandas as pd
from datetime import datetime
from database import get_connection
from components import show_header, show_footer
from auth import require_auth
import io

# Configuration de la page
st.set_page_config(
    page_title="Stock - Culture Pom",
    page_icon="📦",
    layout="wide"
)

# Vérification authentification
require_auth()

# Affichage header et footer
show_header()

# Titre de la page
st.title("📦 Gestion du Stock de Lots")
st.markdown("---")

# Fonction pour charger les données du stock
def load_stock_data():
    """Charge les données du stock avec jointures"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        query = """
            SELECT 
                l.id,
                l.code_lot_interne,
                l.nom_usage,
                l.code_producteur,
                p.raison_sociale as producteur,
                l.code_variete,
                v.nom_variete as variete,
                l.date_entree_stock,
                l.age_jours,
                l.calibre_min,
                l.calibre_max,
                l.est_lave,
                l.est_bio,
                l.avec_grenailles,
                l.site_stockage,
                s.nom_complet as site,
                l.emplacement_stockage,
                l.nombre_unites,
                l.poids_total_brut_kg,
                l.poids_lave_net_kg,
                l.prix_achat_euro_tonne,
                l.valeur_lot_euro,
                l.statut,
                l.is_active
            FROM lots_bruts l
            LEFT JOIN ref_producteurs p ON l.code_producteur = p.code_producteur
            LEFT JOIN ref_varietes v ON l.code_variete = v.code_variete
            LEFT JOIN ref_sites_stockage s ON l.site_stockage = s.code_site
            WHERE l.is_active = TRUE
            ORDER BY l.date_entree_stock DESC
        """
        
        cursor.execute(query)
        
        # Récupérer les résultats et les noms de colonnes
        rows = cursor.fetchall()
        column_names = [desc[0] for desc in cursor.description]
        
        cursor.close()
        conn.close()
        
        # Créer DataFrame - MÉTHODE CORRECTE
        df = pd.DataFrame(rows, columns=column_names)
        
        return df
        
    except Exception as e:
        st.error(f"Erreur lors du chargement des données : {str(e)}")
        return pd.DataFrame()

# Fonction pour calculer les métriques
def calculate_metrics(df):
    """Calcule les métriques du stock"""
    if df.empty:
        return {
            'total_lots': 0,
            'tonnage_total': 0.0,
            'nb_varietes': 0,
            'nb_producteurs': 0,
            'age_moyen': 0,
            'valeur_totale': 0.0
        }
    
    return {
        'total_lots': len(df),
        'tonnage_total': df['poids_lave_net_kg'].sum() / 1000 if 'poids_lave_net_kg' in df.columns else 0.0,
        'nb_varietes': df['code_variete'].nunique() if 'code_variete' in df.columns else 0,
        'nb_producteurs': df['code_producteur'].nunique() if 'code_producteur' in df.columns else 0,
        'age_moyen': df['age_jours'].mean() if 'age_jours' in df.columns and df['age_jours'].notna().any() else 0,
        'valeur_totale': df['valeur_lot_euro'].sum() if 'valeur_lot_euro' in df.columns else 0.0
    }

# Fonction pour convertir numpy types vers types Python natifs
def convert_numpy_types(df):
    """Convertit les types numpy en types Python natifs pour PostgreSQL"""
    df_copy = df.copy()
    
    for col in df_copy.columns:
        # Convertir numpy.bool_ en bool Python
        if df_copy[col].dtype == 'bool':
            df_copy[col] = df_copy[col].astype(object)
            df_copy[col] = df_copy[col].apply(
                lambda x: bool(x) if pd.notna(x) and x is not None else None
            )
        # Convertir numpy.int64 en int Python
        elif df_copy[col].dtype in ['int64', 'int32']:
            df_copy[col] = df_copy[col].astype(object)
            df_copy[col] = df_copy[col].apply(
                lambda x: int(x) if pd.notna(x) and x is not None else None
            )
        # Convertir numpy.float64 en float Python
        elif df_copy[col].dtype in ['float64', 'float32']:
            df_copy[col] = df_copy[col].astype(object)
            df_copy[col] = df_copy[col].apply(
                lambda x: float(x) if pd.notna(x) and x is not None else None
            )
    
    return df_copy

# Fonction pour sauvegarder les modifications
def save_stock_changes(original_df, edited_df):
    """Sauvegarde les modifications du stock"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Convertir les types numpy en types Python natifs
        edited_df = convert_numpy_types(edited_df)
        
        updates = 0
        
        # Colonnes modifiables
        editable_columns = [
            'nom_usage', 'site_stockage', 'emplacement_stockage', 
            'nombre_unites', 'poids_lave_net_kg', 'prix_achat_euro_tonne',
            'valeur_lot_euro', 'statut', 'is_active'
        ]
        
        # Comparer ligne par ligne
        for idx in edited_df.index:
            lot_id = edited_df.loc[idx, 'id']
            
            if idx in original_df.index:
                changes = {}
                for col in editable_columns:
                    if col in edited_df.columns and col in original_df.columns:
                        old_val = original_df.loc[idx, col]
                        new_val = edited_df.loc[idx, col]
                        
                        # Comparer en tenant compte des NaN
                        if pd.isna(old_val) and pd.isna(new_val):
                            continue
                        elif pd.isna(old_val) or pd.isna(new_val) or old_val != new_val:
                            changes[col] = new_val
                
                # S'il y a des changements, mettre à jour
                if changes:
                    set_clause = ", ".join([f"{col} = %s" for col in changes.keys()])
                    values = list(changes.values()) + [lot_id]
                    
                    update_query = f"""
                        UPDATE lots_bruts
                        SET {set_clause}, updated_at = CURRENT_TIMESTAMP
                        WHERE id = %s
                    """
                    
                    cursor.execute(update_query, values)
                    updates += 1
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return True, f"✅ {updates} lot(s) mis à jour avec succès"
        
    except Exception as e:
        if conn:
            conn.rollback()
        return False, f"❌ Erreur lors de la sauvegarde : {str(e)}"

# Charger les données
df = load_stock_data()

if not df.empty:
    # Calculer les métriques
    metrics = calculate_metrics(df)
    
    # Afficher les KPIs
    st.subheader("📊 Indicateurs Clés")
    
    col1, col2, col3, col4, col5, col6 = st.columns(6)
    
    with col1:
        st.metric(
            "📦 Lots actifs",
            f"{metrics['total_lots']:,}".replace(',', ' ')
        )
    
    with col2:
        st.metric(
            "⚖️ Tonnage total",
            f"{metrics['tonnage_total']:.1f} t"
        )
    
    with col3:
        st.metric(
            "🌱 Variétés",
            metrics['nb_varietes']
        )
    
    with col4:
        st.metric(
            "👨‍🌾 Producteurs",
            metrics['nb_producteurs']
        )
    
    with col5:
        st.metric(
            "📅 Âge moyen",
            f"{metrics['age_moyen']:.0f} j"
        )
    
    with col6:
        st.metric(
            "💰 Valeur totale",
            f"{metrics['valeur_totale']:,.0f} €".replace(',', ' ')
        )
    
    st.markdown("---")
    
    # Filtres
    st.subheader("🔍 Filtres")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        varietes = ['Toutes'] + sorted(df['variete'].dropna().unique().tolist())
        selected_variete = st.selectbox("Variété", varietes)
    
    with col2:
        producteurs = ['Tous'] + sorted(df['producteur'].dropna().unique().tolist())
        selected_producteur = st.selectbox("Producteur", producteurs)
    
    with col3:
        sites = ['Tous'] + sorted(df['site'].dropna().unique().tolist())
        selected_site = st.selectbox("Site", sites)
    
    with col4:
        statuts = ['Tous', 'EN_STOCK', 'VENDU', 'TRANSFERE']
        selected_statut = st.selectbox("Statut", statuts)
    
    # Appliquer les filtres
    filtered_df = df.copy()
    
    if selected_variete != 'Toutes':
        filtered_df = filtered_df[filtered_df['variete'] == selected_variete]
    
    if selected_producteur != 'Tous':
        filtered_df = filtered_df[filtered_df['producteur'] == selected_producteur]
    
    if selected_site != 'Tous':
        filtered_df = filtered_df[filtered_df['site'] == selected_site]
    
    if selected_statut != 'Tous':
        filtered_df = filtered_df[filtered_df['statut'] == selected_statut]
    
    st.markdown("---")
    
    # Afficher le nombre de résultats filtrés
    st.info(f"📊 {len(filtered_df)} lot(s) affiché(s) sur {len(df)} total")
    
    # Sauvegarder le DataFrame original pour comparaison
    if 'original_stock_df' not in st.session_state:
        st.session_state.original_stock_df = filtered_df.copy()
    
    # Afficher le tableau éditable
    st.subheader("📋 Liste des Lots")
    
    # Sélectionner et réorganiser les colonnes pour l'affichage
    display_columns = [
        'id', 'code_lot_interne', 'nom_usage', 'variete', 'producteur',
        'date_entree_stock', 'age_jours', 'calibre_min', 'calibre_max',
        'est_lave', 'est_bio', 'site', 'emplacement_stockage',
        'nombre_unites', 'poids_lave_net_kg', 'prix_achat_euro_tonne',
        'valeur_lot_euro', 'statut', 'is_active'
    ]
    
    # Filtrer les colonnes qui existent réellement
    available_columns = [col for col in display_columns if col in filtered_df.columns]
    display_df = filtered_df[available_columns].copy()
    
    # Renommer les colonnes pour un affichage plus lisible
    column_config = {
        'id': 'ID',
        'code_lot_interne': 'Code Lot',
        'nom_usage': 'Nom',
        'variete': 'Variété',
        'producteur': 'Producteur',
        'date_entree_stock': st.column_config.DateColumn('Date Entrée', format="DD/MM/YYYY"),
        'age_jours': 'Âge (j)',
        'calibre_min': 'Cal. Min',
        'calibre_max': 'Cal. Max',
        'est_lave': 'Lavé',
        'est_bio': 'Bio',
        'site': 'Site',
        'emplacement_stockage': 'Emplacement',
        'nombre_unites': 'Nb Unités',
        'poids_lave_net_kg': st.column_config.NumberColumn('Poids Net (kg)', format="%.1f"),
        'prix_achat_euro_tonne': st.column_config.NumberColumn('Prix €/t', format="%.2f"),
        'valeur_lot_euro': st.column_config.NumberColumn('Valeur €', format="%.2f"),
        'statut': 'Statut',
        'is_active': 'Actif'
    }
    
    edited_df = st.data_editor(
        display_df,
        column_config=column_config,
        use_container_width=True,
        num_rows="fixed",
        disabled=['id', 'code_lot_interne', 'variete', 'producteur', 'date_entree_stock', 'age_jours', 'calibre_min', 'calibre_max', 'est_lave', 'est_bio'],
        key="stock_editor"
    )
    
    # Boutons d'action
    col1, col2, col3 = st.columns([2, 2, 6])
    
    with col1:
        if st.button("💾 Enregistrer les modifications", use_container_width=True, type="primary"):
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
    
    # Section alertes
    st.markdown("---")
    st.subheader("⚠️ Alertes")
    
    col1, col2 = st.columns(2)
    
    with col1:
        # Lots anciens (>90 jours)
        old_lots = df[df['age_jours'] > 90] if 'age_jours' in df.columns else pd.DataFrame()
        
        if not old_lots.empty:
            st.warning(f"⚠️ {len(old_lots)} lot(s) de plus de 90 jours")
            
            alert_df = old_lots[['code_lot_interne', 'variete', 'age_jours', 'poids_lave_net_kg']].head(5)
            alert_df.columns = ['Code Lot', 'Variété', 'Âge (j)', 'Poids (kg)']
            st.dataframe(alert_df, use_container_width=True, hide_index=True)
        else:
            st.success("✅ Aucun lot ancien (>90j)")
    
    with col2:
        # Lots sans variété
        no_variety = df[df['code_variete'].isna()] if 'code_variete' in df.columns else pd.DataFrame()
        
        if not no_variety.empty:
            st.warning(f"⚠️ {len(no_variety)} lot(s) sans variété")
        else:
            st.success("✅ Tous les lots ont une variété")
    
    # Section export
    st.markdown("---")
    st.subheader("📤 Exports")
    
    col1, col2, col3 = st.columns([1, 1, 2])
    
    with col1:
        # Export CSV
        csv = filtered_df.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Télécharger CSV",
            data=csv,
            file_name=f"stock_lots_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv",
            use_container_width=True
        )
    
    with col2:
        # Export Excel
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            filtered_df.to_excel(writer, index=False, sheet_name='Stock')
            
            # Ajouter une feuille avec les métriques
            metrics_df = pd.DataFrame([metrics])
            metrics_df.to_excel(writer, index=False, sheet_name='Métriques')
        
        st.download_button(
            label="📥 Télécharger Excel",
            data=buffer.getvalue(),
            file_name=f"stock_lots_{datetime.now().strftime('%Y%m%d')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True
        )

else:
    st.warning("⚠️ Aucun lot actif trouvé dans la base de données")
    
    st.info("""
    **Que faire ?**
    
    1. Vérifiez que la base de données est correctement connectée
    2. Assurez-vous qu'il y a des lots avec `is_active = TRUE`
    3. Utilisez la page **Reception Lots** pour ajouter de nouveaux lots
    4. Contactez l'administrateur si le problème persiste
    """)

# Footer
show_footer()
