import streamlit as st
import pandas as pd
from datetime import datetime
from database import get_connection
from components import show_header, show_footer
from auth import is_authenticated, is_admin
from io import BytesIO

st.set_page_config(
    page_title="Culture Pom - Sources",
    page_icon="📂",
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


# Configuration des tables
TABLES = {
    "Variétés": {
        "table": "ref_varietes",
        "emoji": "🌾",
        "key_field": "code_variete",
        "display_name": "nom_variete"
    },
    "Producteurs": {
        "table": "ref_producteurs",
        "emoji": "👨‍🌾",
        "key_field": "code_producteur",
        "display_name": "raison_sociale"
    },
    "Sites de Stockage": {
        "table": "ref_sites_stockage",
        "emoji": "🏢",
        "key_field": "code_site",
        "display_name": "nom_complet"
    },
    "Emballages": {
        "table": "ref_emballages",
        "emoji": "📦",
        "key_field": "code_emballage",
        "display_name": "code_emballage"
    },
    "Plants": {
        "table": "ref_plants",
        "emoji": "🌱",
        "key_field": "code_plant",
        "display_name": "code_plant"
    },
    "Produits Commerciaux": {
        "table": "ref_produits_commerciaux",
        "emoji": "📦",
        "key_field": "code_produit",
        "display_name": "code_produit"
    },
    "Types de Déchets": {
        "table": "ref_types_dechets",
        "emoji": "🗑️",
        "key_field": "code",
        "display_name": "libelle"
    }
}


def get_table_data(table_name):
    """Récupère les données d'une table"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute(f"SELECT * FROM {table_name} ORDER BY id")
        
        rows = cursor.fetchall()
        columns = [desc[0] for desc in cursor.description]
        
        cursor.close()
        conn.close()
        
        if rows:
            df = pd.DataFrame(rows, columns=columns)
            return df
        else:
            return pd.DataFrame()
            
    except Exception as e:
        st.error(f"❌ Erreur : {str(e)}")
        return pd.DataFrame()


def save_changes(table_name, original_df, edited_df):
    """Sauvegarde les modifications"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        changes_count = 0
        
        # Comparer ligne par ligne
        for idx in edited_df.index:
            if idx in original_df.index:
                original_row = original_df.loc[idx]
                edited_row = edited_df.loc[idx]
                
                # Vérifier si la ligne a changé
                if not original_row.equals(edited_row):
                    record_id = int(edited_row['id'])
                    
                    # Construire UPDATE
                    set_clauses = []
                    values = []
                    
                    for col in edited_df.columns:
                        if col not in ['id', 'created_at', 'updated_at']:
                            value = edited_row[col]
                            if pd.isna(value):
                                set_clauses.append(f"{col} = NULL")
                            else:
                                set_clauses.append(f"{col} = %s")
                                values.append(value)
                    
                    if set_clauses:
                        query = f"""
                            UPDATE {table_name} 
                            SET {', '.join(set_clauses)}, updated_at = NOW()
                            WHERE id = %s
                        """
                        values.append(record_id)
                        
                        cursor.execute(query, values)
                        changes_count += 1
        
        conn.commit()
        cursor.close()
        conn.close()
        
        if changes_count > 0:
            st.success(f"✅ {changes_count} modification(s) enregistrée(s)")
            st.rerun()
        else:
            st.info("ℹ️ Aucune modification à enregistrer")
        
        return True
        
    except Exception as e:
        st.error(f"❌ Erreur sauvegarde : {str(e)}")
        return False


def delete_record(table_name, record_id, key_value):
    """Supprime un enregistrement (soft delete)"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        query = f"""
            UPDATE {table_name} 
            SET is_active = FALSE, updated_at = NOW()
            WHERE id = %s
        """
        cursor.execute(query, (record_id,))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        st.success(f"✅ {key_value} désactivé")
        st.rerun()
        
    except Exception as e:
        st.error(f"❌ Erreur : {str(e)}")


def main():
    show_header("Sources", "Gestion des données de référence")
    
    # Sélection de la table
    st.markdown("### 📂 Choisir une table")
    
    table_choice = st.selectbox(
        "Table",
        options=list(TABLES.keys()),
        format_func=lambda x: f"{TABLES[x]['emoji']} {x}",
        label_visibility="collapsed"
    )
    
    config = TABLES[table_choice]
    table_name = config['table']
    emoji = config['emoji']
    key_field = config['key_field']
    
    st.markdown("---")
    
    # Charger les données
    df_original = get_table_data(table_name)
    
    if df_original.empty:
        st.warning(f"⚠️ Aucune donnée dans {table_choice}")
        show_footer()
        return
    
    # Compteur
    st.markdown(f"**{len(df_original)}** enregistrements dans {emoji} {table_choice}")
    
    # Recherche
    search = st.text_input("🔍 Rechercher", placeholder="Saisir un terme...")
    
    df_filtered = df_original.copy()
    
    if search:
        mask = df_filtered.astype(str).apply(
            lambda row: row.str.contains(search, case=False, na=False).any(), 
            axis=1
        )
        df_filtered = df_filtered[mask]
        st.caption(f"{len(df_filtered)} résultats")
    
    # TABLEAU ÉDITABLE
    st.markdown(f"### 📋 {table_choice}")
    
    # Colonnes à désactiver pour l'édition
    disabled_cols = ["id", "created_at", "updated_at"]
    
    edited_df = st.data_editor(
        df_filtered,
        use_container_width=True,
        hide_index=True,
        disabled=disabled_cols,
        num_rows="fixed",
        height=500,
        key=f"editor_{table_name}"
    )
    
    # Boutons d'action
    st.markdown("### 🎯 Actions")
    
    col1, col2, col3 = st.columns([2, 2, 6])
    
    with col1:
        if st.button("💾 Enregistrer", use_container_width=True, type="primary"):
            save_changes(table_name, df_filtered, edited_df)
    
    with col2:
        if st.button("🔄 Actualiser", use_container_width=True):
            st.rerun()
    
    st.markdown("---")
    
    # Suppression
    st.markdown("### 🗑️ Supprimer un enregistrement")
    st.caption("Sélectionnez un enregistrement à désactiver")
    
    if len(df_filtered) > 0:
        # Créer une liste déroulante pour sélectionner
        display_field = config.get('display_name', key_field)
        
        # Créer options
        options_list = []
        for idx, row in df_filtered.iterrows():
            key_val = row[key_field] if not pd.isna(row[key_field]) else "N/A"
            display_val = row[display_field] if not pd.isna(row[display_field]) else ""
            options_list.append(f"{key_val} - {display_val}")
        
        selected_display = st.selectbox("Enregistrement", ["Sélectionner..."] + options_list)
        
        if selected_display != "Sélectionner...":
            col_del1, col_del2 = st.columns([1, 5])
            with col_del1:
                if st.button("🗑️ Supprimer", type="secondary", use_container_width=True):
                    # Extraire le code
                    selected_code = selected_display.split(" - ")[0]
                    record = df_filtered[df_filtered[key_field] == selected_code].iloc[0]
                    record_id = int(record['id'])
                    
                    delete_record(table_name, record_id, selected_display)
    
    # Exports
    st.markdown("---")
    st.markdown("### 📥 Exports")
    col_e1, col_e2 = st.columns(2)
    
    with col_e1:
        csv = df_filtered.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Télécharger CSV",
            data=csv,
            file_name=f"{table_name}_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv",
            use_container_width=True
        )
    
    with col_e2:
        try:
            output = BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df_filtered.to_excel(writer, index=False, sheet_name='Data')
            output.seek(0)
            
            st.download_button(
                label="📥 Télécharger Excel",
                data=output.getvalue(),
                file_name=f"{table_name}_{datetime.now().strftime('%Y%m%d')}.xlsx",
                mime="application/vnd.ms-excel",
                use_container_width=True
            )
        except Exception as e:
            st.error(f"Export Excel : {str(e)}")
    
    show_footer()


if __name__ == "__main__":
    main()