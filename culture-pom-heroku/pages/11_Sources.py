import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime
from database import get_connection
from components import show_header, show_footer
from auth import is_authenticated
import io

st.set_page_config(page_title="Sources - Culture Pom", page_icon="📋", layout="wide")

if not is_authenticated():
    st.warning("⚠️ Veuillez vous connecter pour accéder à cette page")
    st.stop()

show_header()
st.title("📋 Gestion des Tables de Référence")
st.markdown("---")

TABLES_CONFIG = {
    "Variétés": {
        "table": "ref_varietes",
        "columns": ["code_variete", "nom_variete", "type", "utilisation", "couleur_peau", "couleur_chair", "precocite", "is_active", "notes"],
        "primary_key": "id",
        "editable": ["nom_variete", "type", "utilisation", "couleur_peau", "couleur_chair", "precocite", "is_active", "notes"],
        "has_updated_at": True
    },
    "Plants": {
        "table": "ref_plants",
        "columns": ["code_plant", "variete", "description", "is_active", "notes"],
        "primary_key": "id",
        "editable": ["variete", "description", "is_active", "notes"],
        "has_updated_at": True
    },
    "Producteurs": {
        "table": "ref_producteurs",
        "columns": ["code_producteur", "raison_sociale", "adresse", "commune", "code_postal", "telephone", "email", "contact_principal", "est_bio", "is_active", "notes"],
        "primary_key": "id",
        "editable": ["raison_sociale", "adresse", "commune", "code_postal", "telephone", "email", "contact_principal", "est_bio", "is_active", "notes"],
        "has_updated_at": True
    },
    "Sites Stockage": {
        "table": "ref_sites_stockage",
        "columns": ["code_site", "code_emplacement", "nom_complet", "adresse", "capacite_max_pallox", "capacite_max_tonnes", "is_active", "notes"],
        "primary_key": "id",
        "editable": ["nom_complet", "adresse", "capacite_max_pallox", "capacite_max_tonnes", "is_active", "notes"],
        "has_updated_at": True,
        "auto_cle_unique": True
    },
    "Types Déchets": {
        "table": "ref_types_dechets",
        "columns": ["code", "libelle", "description", "is_active"],
        "primary_key": "id",
        "editable": ["libelle", "description", "is_active"],
        "has_updated_at": False
    },
    "Emballages": {
        "table": "ref_emballages",
        "columns": ["code_emballage", "type_emballage", "capacite_kg", "is_active", "notes"],
        "primary_key": "id",
        "editable": ["type_emballage", "capacite_kg", "is_active", "notes"],
        "has_updated_at": True
    },
    "Produits Commerciaux": {
        "table": "ref_produits_commerciaux",
        "columns": ["code_produit", "description", "categorie", "prix_vente_kg", "is_active", "notes"],
        "primary_key": "id",
        "editable": ["description", "categorie", "prix_vente_kg", "is_active", "notes"],
        "has_updated_at": True
    }
}

def load_table_data(table_name):
    """Charge les données d'une table"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        config = TABLES_CONFIG[table_name]
        
        columns_str = ", ".join(config["columns"])
        query = f"SELECT {config['primary_key']}, {columns_str} FROM {config['table']} ORDER BY {config['primary_key']}"
        cursor.execute(query)
        
        rows = cursor.fetchall()
        columns = [config['primary_key']] + config['columns']
        cursor.close()
        conn.close()
        
        df = pd.DataFrame(rows, columns=columns)
        return df
        
    except Exception as e:
        st.error(f"❌ Erreur : {str(e)}")
        return pd.DataFrame()

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

def save_changes(table_name, original_df, edited_df):
    """Sauvegarde les modifications"""
    try:
        config = TABLES_CONFIG[table_name]
        conn = get_connection()
        cursor = conn.cursor()
        updates = 0
        
        for idx in edited_df.index:
            if idx not in original_df.index:
                continue
            
            row_id = convert_to_native_types(edited_df.loc[idx, config['primary_key']])
            changes = {}
            
            for col in config['editable']:
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
                values = list(changes.values()) + [row_id]
                
                if config.get('has_updated_at', True):
                    update_query = f"UPDATE {config['table']} SET {set_clause}, updated_at = CURRENT_TIMESTAMP WHERE {config['primary_key']} = %s"
                else:
                    update_query = f"UPDATE {config['table']} SET {set_clause} WHERE {config['primary_key']} = %s"
                
                cursor.execute(update_query, values)
                updates += 1
        
        conn.commit()
        cursor.close()
        conn.close()
        return True, f"✅ {updates} enregistrement(s) mis à jour"
        
    except Exception as e:
        if 'conn' in locals():
            conn.rollback()
        return False, f"❌ Erreur : {str(e)}"

def delete_record(table_name, record_id):
    """Supprime (soft delete)"""
    try:
        config = TABLES_CONFIG[table_name]
        conn = get_connection()
        cursor = conn.cursor()
        
        if config.get('has_updated_at', True):
            query = f"UPDATE {config['table']} SET is_active = FALSE, updated_at = CURRENT_TIMESTAMP WHERE {config['primary_key']} = %s"
        else:
            query = f"UPDATE {config['table']} SET is_active = FALSE WHERE {config['primary_key']} = %s"
        
        cursor.execute(query, (record_id,))
        conn.commit()
        cursor.close()
        conn.close()
        return True, "✅ Supprimé"
        
    except Exception as e:
        if 'conn' in locals():
            conn.rollback()
        return False, f"❌ Erreur : {str(e)}"

def add_record(table_name, data):
    """Ajoute un enregistrement"""
    try:
        config = TABLES_CONFIG[table_name]
        conn = get_connection()
        cursor = conn.cursor()
        
        # Générer cle_unique pour Sites Stockage
        if config.get('auto_cle_unique'):
            if 'code_site' in data and 'code_emplacement' in data:
                data['cle_unique'] = f"{data['code_site']}_{data['code_emplacement']}"
        
        columns = list(data.keys())
        values = [convert_to_native_types(v) for v in data.values()]
        placeholders = ", ".join(["%s"] * len(columns))
        columns_str = ", ".join(columns)
        
        if config.get('has_updated_at', True):
            query = f"INSERT INTO {config['table']} ({columns_str}, created_at, updated_at) VALUES ({placeholders}, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
        else:
            query = f"INSERT INTO {config['table']} ({columns_str}, created_at) VALUES ({placeholders}, CURRENT_TIMESTAMP)"
        
        cursor.execute(query, values)
        conn.commit()
        cursor.close()
        conn.close()
        return True, "✅ Ajouté"
        
    except Exception as e:
        if 'conn' in locals():
            conn.rollback()
        return False, f"❌ Erreur : {str(e)}"

# Interface
col1, col2 = st.columns([3, 1])
with col1:
    selected_table = st.selectbox("📋 Table", list(TABLES_CONFIG.keys()), key="table_selector")
with col2:
    if st.button("➕ Ajouter", use_container_width=True):
        # Toggle l'affichage du formulaire
        st.session_state.show_add_form = not st.session_state.get('show_add_form', False)

st.markdown("---")

# Formulaire ajout - SE DÉPLIE/RÉTRACTE
if st.session_state.get('show_add_form', False):
    with st.form("add_form"):
        st.subheader(f"➕ Ajouter - {selected_table}")
        config = TABLES_CONFIG[selected_table]
        new_data = {}
        
        col1, col2 = st.columns(2)
        for i, col in enumerate(config['columns']):
            with col1 if i % 2 == 0 else col2:
                if col in ['is_active', 'est_bio']:
                    new_data[col] = st.checkbox(col.replace('_', ' ').title(), value=True)
                elif 'capacite' in col or 'prix' in col:
                    new_data[col] = st.number_input(col.replace('_', ' ').title(), min_value=0.0, value=0.0, step=0.1)
                else:
                    new_data[col] = st.text_input(col.replace('_', ' ').title())
        
        col1, col2 = st.columns([1, 1])
        with col1:
            if st.form_submit_button("💾 Enregistrer", use_container_width=True):
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

# Charger données
df = load_table_data(selected_table)

if not df.empty:
    config = TABLES_CONFIG[selected_table]
    
    # Métriques
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("📊 Total", len(df))
    with col2:
        actifs = df['is_active'].sum() if 'is_active' in df.columns else len(df)
        st.metric("✅ Actifs", actifs)
    with col3:
        inactifs = len(df) - actifs if 'is_active' in df.columns else 0
        st.metric("❌ Inactifs", inactifs)
    
    st.markdown("---")
    
    if 'original_df' not in st.session_state:
        st.session_state.original_df = df.copy()
    
    # Tableau
    st.subheader(f"📋 {selected_table}")
    
    edited_df = st.data_editor(
        df,
        use_container_width=True,
        num_rows="fixed",
        disabled=[config['primary_key']],
        key=f"editor_{selected_table}"
    )
    
    # Boutons
    col1, col2 = st.columns([1, 5])
    with col1:
        if st.button("💾 Enregistrer", use_container_width=True, type="primary"):
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
    
    # Suppression
    st.markdown("---")
    st.subheader("🗑️ Supprimer")
    col1, col2 = st.columns([3, 1])
    
    with col1:
        first_col = config['columns'][0]
        options = [f"{row[config['primary_key']]} - {row[first_col]}" for _, row in df.iterrows()]
        selected_record = st.selectbox("Sélectionner", options, key="delete_selector")
    
    with col2:
        if st.button("🗑️ Supprimer", use_container_width=True, type="secondary"):
            record_id = int(selected_record.split(" - ")[0])
            success, message = delete_record(selected_table, record_id)
            if success:
                st.success(message)
                st.session_state.pop('original_df', None)
                st.rerun()
            else:
                st.error(message)
    
    # Exports
    st.markdown("---")
    st.subheader("📤 Exports")
    col1, col2 = st.columns(2)
    
    with col1:
        csv = df.to_csv(index=False).encode('utf-8')
        st.download_button("📥 CSV", csv, f"{config['table']}_{datetime.now().strftime('%Y%m%d')}.csv", 
                          "text/csv", use_container_width=True)
    
    with col2:
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name=selected_table)
        st.download_button("📥 Excel", buffer.getvalue(), f"{config['table']}_{datetime.now().strftime('%Y%m%d')}.xlsx",
                          "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)
else:
    st.warning(f"⚠️ Aucune donnée pour {selected_table}")

show_footer()
