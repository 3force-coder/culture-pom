import streamlit as st
import pandas as pd
from datetime import datetime
from database import get_connection
from components import show_header, show_footer
from auth import require_auth, is_admin
import io

# Configuration de la page
st.set_page_config(
    page_title="Sources - Culture Pom",
    page_icon="📋",
    layout="wide"
)

# Vérification authentification
require_auth()

# Affichage header et footer
show_header()

# Titre de la page
st.title("📋 Gestion des Tables de Référence")
st.markdown("---")

# Définition des tables de référence disponibles
TABLES_CONFIG = {
    "Variétés": {
        "table": "ref_varietes",
        "columns": ["code_variete", "nom_variete", "type", "utilisation", "couleur_peau", "couleur_chair", "precocite", "is_active", "notes"],
        "display_names": ["Code", "Nom Variété", "Type", "Utilisation", "Couleur Peau", "Couleur Chair", "Précocité", "Actif", "Notes"],
        "primary_key": "id",
        "editable": ["nom_variete", "type", "utilisation", "couleur_peau", "couleur_chair", "precocite", "is_active", "notes"]
    },
    "Producteurs": {
        "table": "ref_producteurs",
        "columns": ["code_producteur", "raison_sociale", "adresse", "commune", "code_postal", "telephone", "email", "contact_principal", "est_bio", "is_active", "notes"],
        "display_names": ["Code", "Raison Sociale", "Adresse", "Commune", "Code Postal", "Téléphone", "Email", "Contact", "Bio", "Actif", "Notes"],
        "primary_key": "id",
        "editable": ["raison_sociale", "adresse", "commune", "code_postal", "telephone", "email", "contact_principal", "est_bio", "is_active", "notes"]
    },
    "Sites de Stockage": {
        "table": "ref_sites_stockage",
        "columns": ["code_site", "code_emplacement", "nom_complet", "adresse", "capacite_max_pallox", "capacite_max_tonnes", "is_active", "notes"],
        "display_names": ["Code Site", "Code Emplacement", "Nom Complet", "Adresse", "Capacité Pallox", "Capacité Tonnes", "Actif", "Notes"],
        "primary_key": "id",
        "editable": ["code_emplacement", "nom_complet", "adresse", "capacite_max_pallox", "capacite_max_tonnes", "is_active", "notes"]
    },
    "Types de Déchets": {
        "table": "ref_types_dechets",
        "columns": ["code", "libelle", "description", "is_active"],
        "display_names": ["Code", "Libellé", "Description", "Actif"],
        "primary_key": "id",
        "editable": ["libelle", "description", "is_active"]
    }
}

# Fonction pour charger les données
def load_table_data(table_name):
    """Charge les données d'une table"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Récupérer les colonnes
        config = TABLES_CONFIG[table_name]
        columns_str = ", ".join(config["columns"])
        
        query = f"SELECT {config['primary_key']}, {columns_str} FROM {config['table']} ORDER BY {config['primary_key']}"
        cursor.execute(query)
        
        # Récupérer les résultats
        rows = cursor.fetchall()
        columns = [config['primary_key']] + config['columns']
        
        cursor.close()
        conn.close()
        
        # Créer DataFrame - MÉTHODE CORRECTE
        df = pd.DataFrame(rows, columns=columns)
        
        return df
        
    except Exception as e:
        st.error(f"Erreur lors du chargement des données : {str(e)}")
        return pd.DataFrame()

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
def save_changes(table_name, original_df, edited_df):
    """Sauvegarde les modifications dans la base de données"""
    try:
        config = TABLES_CONFIG[table_name]
        conn = get_connection()
        cursor = conn.cursor()
        
        # Convertir les types numpy en types Python natifs
        edited_df = convert_numpy_types(edited_df)
        
        updates = 0
        
        # Comparer ligne par ligne
        for idx in edited_df.index:
            row_id = edited_df.loc[idx, config['primary_key']]
            
            # Vérifier si la ligne a changé
            if idx in original_df.index:
                changes = {}
                for col in config['editable']:
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
                    values = list(changes.values()) + [row_id]
                    
                    update_query = f"""
                        UPDATE {config['table']}
                        SET {set_clause}, updated_at = CURRENT_TIMESTAMP
                        WHERE {config['primary_key']} = %s
                    """
                    
                    cursor.execute(update_query, values)
                    updates += 1
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return True, f"✅ {updates} enregistrement(s) mis à jour avec succès"
        
    except Exception as e:
        if conn:
            conn.rollback()
        return False, f"❌ Erreur lors de la sauvegarde : {str(e)}"

# Fonction pour supprimer un enregistrement
def delete_record(table_name, record_id):
    """Supprime un enregistrement (soft delete)"""
    try:
        config = TABLES_CONFIG[table_name]
        conn = get_connection()
        cursor = conn.cursor()
        
        # Soft delete : marquer comme inactif au lieu de supprimer
        query = f"""
            UPDATE {config['table']}
            SET is_active = FALSE, updated_at = CURRENT_TIMESTAMP
            WHERE {config['primary_key']} = %s
        """
        
        cursor.execute(query, (record_id,))
        conn.commit()
        cursor.close()
        conn.close()
        
        return True, "✅ Enregistrement supprimé (marqué inactif)"
        
    except Exception as e:
        if conn:
            conn.rollback()
        return False, f"❌ Erreur lors de la suppression : {str(e)}"

# Fonction pour ajouter un nouvel enregistrement
def add_record(table_name, data):
    """Ajoute un nouvel enregistrement"""
    try:
        config = TABLES_CONFIG[table_name]
        conn = get_connection()
        cursor = conn.cursor()
        
        # Préparer les colonnes et valeurs
        columns = list(data.keys())
        values = list(data.values())
        placeholders = ", ".join(["%s"] * len(columns))
        columns_str = ", ".join(columns)
        
        query = f"""
            INSERT INTO {config['table']} ({columns_str}, created_at, updated_at)
            VALUES ({placeholders}, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """
        
        cursor.execute(query, values)
        conn.commit()
        cursor.close()
        conn.close()
        
        return True, "✅ Nouvel enregistrement ajouté avec succès"
        
    except Exception as e:
        if conn:
            conn.rollback()
        return False, f"❌ Erreur lors de l'ajout : {str(e)}"

# Interface utilisateur
col1, col2 = st.columns([3, 1])

with col1:
    selected_table = st.selectbox(
        "📋 Sélectionnez une table",
        options=list(TABLES_CONFIG.keys()),
        key="table_selector"
    )

with col2:
    if st.button("➕ Ajouter un enregistrement", use_container_width=True):
        st.session_state.show_add_form = True

# Afficher le formulaire d'ajout si demandé
if st.session_state.get('show_add_form', False):
    with st.form("add_form"):
        st.subheader(f"➕ Ajouter un nouvel enregistrement - {selected_table}")
        
        config = TABLES_CONFIG[selected_table]
        new_data = {}
        
        # Créer les champs selon la table
        col1, col2 = st.columns(2)
        
        for i, col in enumerate(config['columns']):
            with col1 if i % 2 == 0 else col2:
                display_name = config['display_names'][i]
                
                # Champs booléens
                if col in ['is_active', 'est_bio']:
                    new_data[col] = st.checkbox(display_name, value=True)
                # Champs numériques
                elif 'capacite' in col:
                    new_data[col] = st.number_input(display_name, min_value=0, value=0)
                # Champs texte
                else:
                    new_data[col] = st.text_input(display_name)
        
        col1, col2, col3 = st.columns([1, 1, 2])
        with col1:
            if st.form_submit_button("💾 Enregistrer", use_container_width=True):
                # Filtrer les champs vides
                filtered_data = {k: v for k, v in new_data.items() if v != '' and v is not None}
                
                success, message = add_record(selected_table, filtered_data)
                if success:
                    st.success(message)
                    st.session_state.show_add_form = False
                    st.rerun()
                else:
                    st.error(message)
        
        with col2:
            if st.form_submit_button("❌ Annuler", use_container_width=True):
                st.session_state.show_add_form = False
                st.rerun()

st.markdown("---")

# Charger les données
df = load_table_data(selected_table)

if not df.empty:
    # Afficher les métriques
    config = TABLES_CONFIG[selected_table]
    
    col1, col2, col3 = st.columns(3)
    with col1:
        total = len(df)
        st.metric("📊 Total", total)
    with col2:
        actifs = df['is_active'].sum() if 'is_active' in df.columns else total
        st.metric("✅ Actifs", actifs)
    with col3:
        inactifs = total - actifs if 'is_active' in df.columns else 0
        st.metric("❌ Inactifs", inactifs)
    
    st.markdown("---")
    
    # Sauvegarder le DataFrame original pour comparaison
    if 'original_df' not in st.session_state:
        st.session_state.original_df = df.copy()
    
    # Afficher le tableau éditable
    st.subheader(f"📋 {selected_table}")
    
    edited_df = st.data_editor(
        df,
        use_container_width=True,
        num_rows="fixed",
        disabled=[config['primary_key']],  # Désactiver l'édition de l'ID
        key=f"editor_{selected_table}"
    )
    
    # Boutons d'action
    col1, col2, col3, col4 = st.columns([2, 2, 2, 4])
    
    with col1:
        if st.button("💾 Enregistrer les modifications", use_container_width=True, type="primary"):
            success, message = save_changes(selected_table, st.session_state.original_df, edited_df)
            if success:
                st.success(message)
                st.session_state.original_df = edited_df.copy()
                st.rerun()
            else:
                st.error(message)
    
    with col2:
        if st.button("🔄 Actualiser", use_container_width=True):
            st.session_state.pop('original_df', None)
            st.rerun()
    
    # Section suppression
    st.markdown("---")
    st.subheader("🗑️ Supprimer un enregistrement")
    
    col1, col2 = st.columns([3, 1])
    
    with col1:
        # Créer une liste de sélection avec ID + nom
        if 'code_variete' in df.columns:
            options = [f"{row[config['primary_key']]} - {row['code_variete']} - {row['nom_variete']}" 
                      for _, row in df.iterrows()]
        elif 'code_producteur' in df.columns:
            options = [f"{row[config['primary_key']]} - {row['code_producteur']} - {row['raison_sociale']}" 
                      for _, row in df.iterrows()]
        elif 'code_site' in df.columns:
            options = [f"{row[config['primary_key']]} - {row['code_site']} - {row['nom_complet']}" 
                      for _, row in df.iterrows()]
        else:
            options = [f"{row[config['primary_key']]} - {row[config['columns'][0]]}" 
                      for _, row in df.iterrows()]
        
        selected_record = st.selectbox(
            "Sélectionnez l'enregistrement à supprimer",
            options=options,
            key="delete_selector"
        )
    
    with col2:
        if st.button("🗑️ Supprimer", use_container_width=True, type="secondary"):
            # Extraire l'ID du texte sélectionné
            record_id = int(selected_record.split(" - ")[0])
            
            success, message = delete_record(selected_table, record_id)
            if success:
                st.success(message)
                st.session_state.pop('original_df', None)
                st.rerun()
            else:
                st.error(message)
    
    # Section export
    st.markdown("---")
    st.subheader("📤 Exports")
    
    col1, col2, col3 = st.columns([1, 1, 2])
    
    with col1:
        # Export CSV
        csv = df.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Télécharger CSV",
            data=csv,
            file_name=f"{config['table']}_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv",
            use_container_width=True
        )
    
    with col2:
        # Export Excel
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name=selected_table)
        
        st.download_button(
            label="📥 Télécharger Excel",
            data=buffer.getvalue(),
            file_name=f"{config['table']}_{datetime.now().strftime('%Y%m%d')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True
        )

else:
    st.warning(f"⚠️ Aucune donnée trouvée pour {selected_table}")

# Footer
show_footer()
