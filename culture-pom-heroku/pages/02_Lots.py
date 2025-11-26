import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, date
import time
from database import get_connection
from components import show_footer
from auth import is_authenticated, is_admin
import io
import streamlit.components.v1 as components
from difflib import get_close_matches

st.set_page_config(page_title="Lots - Culture Pom", page_icon="📦", layout="wide")

# CSS compact
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

# Bloc utilisateur sidebar
def show_user_info():
    if st.session_state.get('authenticated', False):
        with st.sidebar:
            st.markdown("---")
            st.write(f"👤 {st.session_state.get('name', 'Utilisateur')}")
            st.caption(f"📧 {st.session_state.get('email', '')}")
            st.caption(f"🔑 {st.session_state.get('role', 'USER')}")
            st.markdown("---")
            st.caption(f"⚙️ Streamlit v{st.__version__}")
            if st.button("🚪 Déconnexion", use_container_width=True, key="btn_logout_sidebar"):
                for key in list(st.session_state.keys()):
                    del st.session_state[key]
                st.rerun()

show_user_info()

st.title("📦 Gestion des Lots")
st.caption("*Fiche achat des lots - Les emplacements se gèrent dans Détails Stock*")
st.markdown("---")

# ============================================================================
# ANIMATION CONFETTI
# ============================================================================

def show_confetti_animation():
    """Affiche l'animation confetti Lottie"""
    confetti_html = """
    <script src="https://unpkg.com/@lottiefiles/dotlottie-wc@0.8.5/dist/dotlottie-wc.js" type="module"></script>
    <div style="display: flex; justify-content: center; align-items: center;">
        <dotlottie-wc 
            src="https://lottie.host/21b8e802-34df-4b54-89ca-4c7843e1da14/AoYf85WPKi.lottie" 
            style="width: 300px; height: 300px" 
            autoplay>
        </dotlottie-wc>
    </div>
    """
    components.html(confetti_html, height=320)

# ============================================================================
# FONCTIONS HELPER - DROPDOWNS
# ============================================================================

def get_all_varietes_for_dropdown():
    """Récupère TOUTES les variétés actives (nom + code) pour dropdown"""
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
    """Récupère TOUS les producteurs actifs (nom + code) pour dropdown"""
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

# ============================================================================
# FONCTIONS CHARGEMENT / SAUVEGARDE
# ============================================================================

def load_stock_data():
    """Charge les données du stock AVEC jointures"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        query = """
            SELECT 
                l.id,
                l.code_lot_interne,
                l.nom_usage,
                l.code_variete,
                COALESCE(v.nom_variete, l.code_variete) as nom_variete,
                l.code_producteur,
                COALESCE(p.nom, l.code_producteur) as nom_producteur,
                l.date_entree_stock,
                l.calibre_min,
                l.calibre_max,
                l.poids_total_brut_kg,
                l.prix_achat_euro_tonne,
                l.tare_achat_pct,
                l.valeur_lot_euro,
                l.statut,
                COALESCE((CURRENT_DATE - l.date_entree_stock::DATE), 0) as age_jours,
                l.is_active
            FROM lots_bruts l
            LEFT JOIN ref_varietes v ON l.code_variete = v.code_variete
            LEFT JOIN ref_producteurs p ON l.code_producteur = p.code_producteur
            WHERE l.is_active = TRUE
            ORDER BY l.date_entree_stock DESC
        """
        
        cursor.execute(query)
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        
        if rows:
            df = pd.DataFrame(rows)
            # Convertir colonnes numériques
            numeric_cols = ['poids_total_brut_kg', 'prix_achat_euro_tonne', 'tare_achat_pct', 'valeur_lot_euro', 'age_jours', 'calibre_min', 'calibre_max']
            for col in numeric_cols:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
            return df
        return pd.DataFrame()
        
    except Exception as e:
        st.error(f"❌ Erreur chargement : {str(e)}")
        return pd.DataFrame()

def calculate_metrics(df):
    """Calcule les métriques KPI"""
    if df.empty:
        return {'total_lots': 0, 'tonnage_total': 0.0, 'nb_varietes': 0, 'nb_producteurs': 0}
    
    return {
        'total_lots': len(df),
        'tonnage_total': df['poids_total_brut_kg'].sum() / 1000 if 'poids_total_brut_kg' in df.columns else 0.0,
        'nb_varietes': df['code_variete'].nunique(),
        'nb_producteurs': df['code_producteur'].nunique()
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
    if isinstance(value, date):
        return value
    return value

def save_stock_changes(original_df, edited_df, varietes_dict, producteurs_dict):
    """Sauvegarde les modifications avec conversion NOM → CODE pour variétés/producteurs"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        updates = 0
        
        varietes_reverse = {v: k for k, v in varietes_dict.items()}
        producteurs_reverse = {v: k for k, v in producteurs_dict.items()}
        
        for idx in edited_df.index:
            if idx not in original_df.index:
                continue
            
            if 'id' not in edited_df.columns:
                continue
            
            row_id = edited_df.loc[idx, 'id']
            
            if pd.isna(row_id) or row_id == 0:
                continue
            
            row_id = convert_to_native_types(row_id)
            
            changes = {}
            
            editable_columns = ['nom_usage', 'nom_variete', 'nom_producteur', 'calibre_min', 'calibre_max', 
                               'prix_achat_euro_tonne', 'tare_achat_pct', 'statut']
            
            for col in editable_columns:
                if col not in edited_df.columns or col not in original_df.columns:
                    continue
                
                old_val = original_df.loc[idx, col]
                new_val = edited_df.loc[idx, col]
                
                if pd.isna(old_val) and pd.isna(new_val):
                    continue
                elif pd.isna(old_val) or pd.isna(new_val) or old_val != new_val:
                    if col == 'nom_variete' and new_val in varietes_dict:
                        changes['code_variete'] = varietes_dict[new_val]
                    elif col == 'nom_producteur' and new_val in producteurs_dict:
                        changes['code_producteur'] = producteurs_dict[new_val]
                    elif col not in ['nom_variete', 'nom_producteur']:
                        changes[col] = convert_to_native_types(new_val)
            
            # ⭐ Recalcul valeur_lot si tare ou prix change
            if 'tare_achat_pct' in changes or 'prix_achat_euro_tonne' in changes:
                poids_brut = float(edited_df.loc[idx, 'poids_total_brut_kg']) if pd.notna(edited_df.loc[idx, 'poids_total_brut_kg']) else 0.0
                tare = float(changes.get('tare_achat_pct', edited_df.loc[idx, 'tare_achat_pct'])) if 'tare_achat_pct' in changes or pd.notna(edited_df.loc[idx, 'tare_achat_pct']) else 0.0
                prix = float(changes.get('prix_achat_euro_tonne', edited_df.loc[idx, 'prix_achat_euro_tonne'])) if 'prix_achat_euro_tonne' in changes or pd.notna(edited_df.loc[idx, 'prix_achat_euro_tonne']) else 0.0
                
                poids_tonnes = poids_brut / 1000.0
                valeur_lot = poids_tonnes * (1.0 - tare / 100.0) * prix
                changes['valeur_lot_euro'] = valeur_lot
            
            if changes:
                set_clause = ", ".join([f"{col} = %s" for col in changes.keys()])
                values = list(changes.values()) + [row_id]
                
                update_query = f"UPDATE lots_bruts SET {set_clause}, updated_at = CURRENT_TIMESTAMP WHERE id = %s"
                cursor.execute(update_query, values)
                updates += 1
        
        conn.commit()
        cursor.close()
        conn.close()
        
        if updates == 0:
            return True, "ℹ️ Aucune modification détectée"
        return True, f"✅ {updates} lot(s) mis à jour"
        
    except Exception as e:
        if 'conn' in locals():
            conn.rollback()
        return False, f"❌ Erreur : {str(e)}"

def add_lot(data, varietes_dict, producteurs_dict):
    """Ajoute un nouveau lot dans lots_bruts"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Convertir NOM → CODE pour variété
        if 'nom_variete' in data and data['nom_variete']:
            if data['nom_variete'] in varietes_dict:
                data['code_variete'] = varietes_dict[data['nom_variete']]
            del data['nom_variete']
        
        # Convertir NOM → CODE pour producteur
        if 'nom_producteur' in data and data['nom_producteur']:
            if data['nom_producteur'] in producteurs_dict:
                data['code_producteur'] = producteurs_dict[data['nom_producteur']]
            del data['nom_producteur']
        
        # ⚠️ poids_total_brut_kg = NULL (sera défini dans page 03 Détails Stock)
        data['poids_total_brut_kg'] = None
        
        # Calcul valeur_lot (si poids défini plus tard)
        data['valeur_lot_euro'] = 0.0
        
        # Ajouter is_active
        data['is_active'] = True
        
        # ⚠️ FILTRER champs qui n'existent pas dans lots_bruts
        data.pop('type_conditionnement', None)
        data.pop('nombre_unites', None)
        
        # Préparer l'insertion
        columns = list(data.keys())
        values = [convert_to_native_types(v) for v in data.values()]
        placeholders = ", ".join(["%s"] * len(columns))
        columns_str = ", ".join(columns)
        
        query = f"""
            INSERT INTO lots_bruts ({columns_str}, created_at, updated_at) 
            VALUES ({placeholders}, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """
        
        cursor.execute(query, values)
        conn.commit()
        cursor.close()
        conn.close()
        
        return True, "✅ Lot ajouté avec succès"
        
    except Exception as e:
        if 'conn' in locals():
            conn.rollback()
        
        error_msg = str(e).lower()
        
        if "duplicate key" in error_msg or "unique constraint" in error_msg:
            if "code_lot_interne" in error_msg:
                return False, "❌ Ce code lot est déjà utilisé. Merci de choisir un autre code."
            else:
                return False, "❌ Cette valeur est déjà utilisée."
        elif "not null" in error_msg or "null value" in error_msg:
            return False, "❌ Un champ obligatoire est manquant."
        elif "foreign key" in error_msg:
            return False, "❌ Valeur invalide (variété ou producteur inexistant)."
        else:
            return False, f"❌ Erreur : {str(e)}"

def delete_lot(lot_id):
    """Désactive un lot (soft delete)"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        query = "UPDATE lots_bruts SET is_active = FALSE, updated_at = CURRENT_TIMESTAMP WHERE id = %s"
        cursor.execute(query, (lot_id,))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return True, "✅ Lot désactivé avec succès"
        
    except Exception as e:
        if 'conn' in locals():
            conn.rollback()
        return False, f"❌ Erreur : {str(e)}"

# ============================================================================
# CHARGEMENT DES DONNÉES
# ============================================================================


# ============================================================================
# FONCTIONS IMPORT EXCEL - AJOUT ONGLET
# ============================================================================

def fuzzy_match_value(value, valid_values, threshold=0.8):
    """Match fuzzy avec difflib (intégré Python)"""
    if pd.isna(value) or str(value).strip() == '':
        return (True, None, "empty")
    
    value_clean = str(value).strip().upper()
    
    # 1. Match exact
    for valid in valid_values:
        if valid.upper() == value_clean:
            return (True, valid, "exact")
    
    # 2. Match fuzzy
    matches = get_close_matches(value_clean, [v.upper() for v in valid_values], n=1, cutoff=threshold)
    
    if matches:
        matched_upper = matches[0]
        for valid in valid_values:
            if valid.upper() == matched_upper:
                return (True, valid, "fuzzy")
    
    return (False, None, "error")

def get_valid_references_import():
    """Récupère toutes les valeurs valides depuis DB pour import"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Variétés
        cursor.execute("SELECT code_variete FROM ref_varietes WHERE is_active = TRUE ORDER BY code_variete")
        rows_var = cursor.fetchall()
        varietes = [row['code_variete'] for row in rows_var]
        
        # Producteurs
        cursor.execute("SELECT code_producteur FROM ref_producteurs WHERE is_active = TRUE ORDER BY code_producteur")
        rows_prod = cursor.fetchall()
        producteurs = [row['code_producteur'] for row in rows_prod]
        
        cursor.close()
        conn.close()
        
        return {
            'varietes': varietes,
            'producteurs': producteurs
        }
        
    except Exception as e:
        st.error(f"❌ Erreur : {str(e)}")
        return None

def create_import_template_excel():
    """Crée template Excel 3 onglets"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Onglet Lots (vide)
        lots_columns = [
            'code_lot_interne', 'nom_usage', 'code_producteur', 'code_variete',
            'poids_total_brut_kg', 'date_entree_stock', 'calibre_min', 'calibre_max', 
            'prix_achat_euro_tonne', 'tare_achat_pct', 'notes'
        ]
        df_lots_template = pd.DataFrame(columns=lots_columns)
        df_lots_template.loc[0] = [
            'LOT_2025_AGATA_001', 'AGATA BOSSELER', 'ACQU001', 'AGATA',
            19000, '2025-01-15', 35, 50, 150.0, 5.0, 'Exemple'
        ]
        
        # Onglet Variétés
        cursor.execute("SELECT code_variete, nom_variete, type FROM ref_varietes WHERE is_active = TRUE ORDER BY code_variete")
        df_varietes = pd.DataFrame(cursor.fetchall())
        
        # Onglet Producteurs
        cursor.execute("SELECT code_producteur, nom, ville FROM ref_producteurs WHERE is_active = TRUE ORDER BY code_producteur")
        df_producteurs = pd.DataFrame(cursor.fetchall())
        
        cursor.close()
        conn.close()
        
        # Créer Excel
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            df_lots_template.to_excel(writer, sheet_name='Lots', index=False)
            df_varietes.to_excel(writer, sheet_name='Variétés', index=False)
            df_producteurs.to_excel(writer, sheet_name='Producteurs', index=False)
        
        return buffer.getvalue()
        
    except Exception as e:
        st.error(f"❌ Erreur : {str(e)}")
        return None

def validate_import_data_excel(df, valid_refs):
    """Valide les données importées"""
    df_validated = df.copy()
    
    df_validated['_status'] = 'valid'
    df_validated['_errors'] = ''
    df_validated['_warnings'] = ''
    df_validated['_variete_corrected'] = df_validated['code_variete']
    df_validated['_producteur_corrected'] = df_validated['code_producteur']
    
    errors_count = 0
    warnings_count = 0
    
    for idx, row in df_validated.iterrows():
        errors = []
        warnings = []
        
        # Champs obligatoires
        if pd.isna(row['code_lot_interne']) or str(row['code_lot_interne']).strip() == '':
            errors.append("Code lot manquant")
        if pd.isna(row['nom_usage']) or str(row['nom_usage']).strip() == '':
            errors.append("Nom usage manquant")
        if pd.isna(row['poids_total_brut_kg']) or row['poids_total_brut_kg'] <= 0:
            errors.append("Poids total invalide")
        
        # Validation variété
        if not pd.isna(row['code_variete']) and str(row['code_variete']).strip() != '':
            is_valid, matched, match_type = fuzzy_match_value(row['code_variete'], valid_refs['varietes'])
            if is_valid and match_type == "fuzzy":
                warnings.append(f"Variété '{row['code_variete']}' → '{matched}'")
                df_validated.at[idx, '_variete_corrected'] = matched
            elif is_valid and match_type == "exact":
                df_validated.at[idx, '_variete_corrected'] = matched
            elif not is_valid:
                errors.append(f"Variété '{row['code_variete']}' introuvable")
                df_validated.at[idx, '_variete_corrected'] = None
        
        # Validation producteur
        if not pd.isna(row['code_producteur']) and str(row['code_producteur']).strip() != '':
            is_valid, matched, match_type = fuzzy_match_value(row['code_producteur'], valid_refs['producteurs'])
            if is_valid and match_type == "fuzzy":
                warnings.append(f"Producteur '{row['code_producteur']}' → '{matched}'")
                df_validated.at[idx, '_producteur_corrected'] = matched
            elif is_valid and match_type == "exact":
                df_validated.at[idx, '_producteur_corrected'] = matched
            elif not is_valid:
                errors.append(f"Producteur '{row['code_producteur']}' introuvable")
                df_validated.at[idx, '_producteur_corrected'] = None
        
        # Statut
        if errors:
            df_validated.at[idx, '_status'] = 'error'
            df_validated.at[idx, '_errors'] = ' | '.join(errors)
            errors_count += 1
        elif warnings:
            df_validated.at[idx, '_status'] = 'warning'
            df_validated.at[idx, '_warnings'] = ' | '.join(warnings)
            warnings_count += 1
    
    report = {
        'total': len(df_validated),
        'valid': len(df_validated[df_validated['_status'] == 'valid']),
        'warnings': warnings_count,
        'errors': errors_count
    }
    
    return df_validated, report

def import_validated_lots_excel(df_validated):
    """Importe lots validés en base"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        df_to_import = df_validated[df_validated['_status'].isin(['valid', 'warning'])].copy()
        
        imported_count = 0
        failed_lots = []
        
        for idx, row in df_to_import.iterrows():
            try:
                code_variete = row['_variete_corrected'] if pd.notna(row['_variete_corrected']) else None
                code_producteur = row['_producteur_corrected'] if pd.notna(row['_producteur_corrected']) else None
                
                # Poids direct depuis Excel
                poids_total = float(row['poids_total_brut_kg']) if pd.notna(row['poids_total_brut_kg']) else 0.0
                
                # Calcul valeur_lot
                tare = float(row['tare_achat_pct']) if pd.notna(row['tare_achat_pct']) else 0.0
                prix = float(row['prix_achat_euro_tonne']) if pd.notna(row['prix_achat_euro_tonne']) else 0.0
                poids_tonnes = poids_total / 1000.0
                valeur_lot = poids_tonnes * (1.0 - tare / 100.0) * prix
                
                query = """
                INSERT INTO lots_bruts (
                    code_lot_interne, nom_usage, code_producteur, code_variete,
                    poids_total_brut_kg, date_entree_stock, calibre_min, calibre_max,
                    prix_achat_euro_tonne, tare_achat_pct, valeur_lot_euro, notes,
                    statut, is_active, created_at, updated_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'EN_STOCK', TRUE, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                """
                
                cursor.execute(query, (
                    row['code_lot_interne'], row['nom_usage'], code_producteur, code_variete,
                    poids_total,
                    row['date_entree_stock'] if pd.notna(row['date_entree_stock']) else None,
                    int(row['calibre_min']) if pd.notna(row['calibre_min']) else None,
                    int(row['calibre_max']) if pd.notna(row['calibre_max']) else None,
                    prix, tare, valeur_lot,
                    row['notes'] if pd.notna(row['notes']) else None
                ))
                
                imported_count += 1
                
            except Exception as e:
                failed_lots.append(f"{row['code_lot_interne']}: {str(e)}")
        
        conn.commit()
        cursor.close()
        conn.close()
        
        if failed_lots:
            return True, f"✅ {imported_count} lots importés | ⚠️ {len(failed_lots)} échecs"
        else:
            return True, f"✅ {imported_count} lots importés avec succès"
        
    except Exception as e:
        if 'conn' in locals():
            conn.rollback()
        return False, f"❌ Erreur : {str(e)}"


# ============================================================================
# INTERFACE - ONGLETS
# ============================================================================

tab1, tab2 = st.tabs(["📋 Liste Lots", "📥 Import Excel"])

# ===== ONGLET 1 : CODE ORIGINAL (100% INCHANGÉ) =====
with tab1:
    df = load_stock_data()
    
    # ============================================================================
    # FORMULAIRE D'AJOUT (AU CLIC SUR BOUTON)
    # ============================================================================
    
    if st.session_state.get('show_add_form', False):
        st.subheader("➕ Ajouter un nouveau lot")
        
        varietes_dict = get_all_varietes_for_dropdown()
        producteurs_dict = get_all_producteurs_for_dropdown()
        
        st.info("📌 Champs obligatoires : **Code Lot, Nom Usage, Variété, Producteur**")
        
        if 'new_lot_data' not in st.session_state:
            st.session_state.new_lot_data = {}
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.session_state.new_lot_data['code_lot_interne'] = st.text_input(
                "Code Lot Interne *",
                key="add_code_lot_interne",
                help="Code unique du lot (ex: LOT_2025_AGATA_001)"
            )
            
            st.session_state.new_lot_data['nom_usage'] = st.text_input(
                "Nom Usage *",
                key="add_nom_usage",
                help="Nom d'usage du lot"
            )
            
            variete_options = [""] + list(varietes_dict.keys())
            st.session_state.new_lot_data['nom_variete'] = st.selectbox(
                "Variété *",
                options=variete_options,
                key="add_variete"
            )
            
            producteur_options = [""] + list(producteurs_dict.keys())
            st.session_state.new_lot_data['nom_producteur'] = st.selectbox(
                "Producteur *",
                options=producteur_options,
                key="add_producteur"
            )
            
            # Date création - AUTO
            st.session_state.new_lot_data['date_entree_stock'] = datetime.now().date()
            st.text_input(
                "Date Création (auto)",
                value=datetime.now().strftime("%d/%m/%Y"),
                disabled=True,
                key="add_date_entree_display"
            )
        
        with col2:
            # Calibres
            st.session_state.new_lot_data['calibre_min'] = st.number_input(
                "Calibre Min",
                min_value=0,
                value=0,
                step=5,
                key="add_calibre_min"
            )
            
            st.session_state.new_lot_data['calibre_max'] = st.number_input(
                "Calibre Max",
                min_value=0,
                value=75,
                step=5,
                key="add_calibre_max"
            )
            
            # Prix + Tare
            st.session_state.new_lot_data['prix_achat_euro_tonne'] = st.number_input(
                "Prix Achat (€/tonne)",
                min_value=0.0,
                value=0.0,
                step=10.0,
                key="add_prix_achat"
            )
            
            st.session_state.new_lot_data['tare_achat_pct'] = st.number_input(
                "Tare Achat (%)",
                min_value=0.0,
                max_value=100.0,
                value=5.0,
                step=0.5,
                key="add_tare_achat"
            )
            
            # Statut
            STATUTS = ["EN_STOCK", "RESERVE", "VENDU", "DECHET"]
            st.session_state.new_lot_data['statut'] = st.selectbox(
                "Statut",
                options=STATUTS,
                index=0,
                key="add_statut"
            )
            
            # Tarification Définitive
            st.session_state.new_lot_data['tarif_definitif'] = st.checkbox(
                "Tarification Définitive",
                value=False,
                key="add_tarif_definitif",
                help="Cocher si le prix d'achat est définitif"
            )
        
        st.markdown("---")
        
        col1, col2 = st.columns([1, 1])
        
        with col1:
            if st.button("💾 Enregistrer", use_container_width=True, type="primary", key="btn_save_lot"):
                missing_fields = []
                
                if not st.session_state.new_lot_data.get('code_lot_interne'):
                    missing_fields.append("Code Lot Interne")
                if not st.session_state.new_lot_data.get('nom_usage'):
                    missing_fields.append("Nom Usage")
                if not st.session_state.new_lot_data.get('nom_variete'):
                    missing_fields.append("Variété")
                if not st.session_state.new_lot_data.get('nom_producteur'):
                    missing_fields.append("Producteur")
                
                if missing_fields:
                    st.error(f"❌ Champs obligatoires manquants : {', '.join(missing_fields)}")
                else:
                    filtered_data = {}
                    for k, v in st.session_state.new_lot_data.items():
                        if isinstance(v, bool) or (isinstance(v, (int, float)) and v == 0):
                            filtered_data[k] = v
                        elif isinstance(v, date):
                            filtered_data[k] = v
                        elif v != '' and v is not None:
                            filtered_data[k] = v
                    
                    success, message = add_lot(filtered_data, varietes_dict, producteurs_dict)
                    
                    if success:
                        st.success(message)
                        show_confetti_animation()
                        st.info("💡 **Prochaine étape** : Allez dans **Détails Stock** pour ajouter les emplacements de ce lot")
                        time.sleep(3)
                        st.session_state.show_add_form = False
                        st.session_state.pop('new_lot_data', None)
                        st.rerun()
                    else:
                        st.error(message)
        
        with col2:
            if st.button("❌ Annuler", use_container_width=True, key="btn_cancel_lot"):
                st.session_state.show_add_form = False
                st.session_state.pop('new_lot_data', None)
                st.rerun()
        
        st.markdown("---")
    
    # ============================================================================
    # AFFICHAGE TABLEAU ET FILTRES
    # ============================================================================
    
    if not df.empty:
        varietes_dict = get_all_varietes_for_dropdown()
        producteurs_dict = get_all_producteurs_for_dropdown()
        
        metrics = calculate_metrics(df)
        
        # KPIs
        st.subheader("📊 Indicateurs Clés")
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("📦 Lots actifs", f"{metrics['total_lots']:,}".replace(',', ' '))
        with col2:
            st.metric("⚖️ Tonnage total", f"{metrics['tonnage_total']:.1f} t")
        with col3:
            st.metric("🌱 Variétés", metrics['nb_varietes'])
        with col4:
            st.metric("👨‍🌾 Producteurs", metrics['nb_producteurs'])
        
        st.markdown("---")
        
        # Filtres
        st.subheader("🔍 Filtres")
        col1, col2, col3 = st.columns(3)
        
        with col1:
            search_nom = st.text_input("Nom usage", key="filter_nom_usage", placeholder="Rechercher...")
        
        with col2:
            varietes = ['Toutes'] + sorted(df['nom_variete'].dropna().unique().tolist())
            selected_variete = st.selectbox("Variété", varietes, key="filter_variete")
        
        with col3:
            producteurs = ['Tous'] + sorted(df['nom_producteur'].dropna().unique().tolist())
            selected_producteur = st.selectbox("Producteur", producteurs, key="filter_producteur")
        
        # Appliquer filtres
        filtered_df = df.copy()
        
        if search_nom:
            filtered_df = filtered_df[filtered_df['nom_usage'].str.contains(search_nom, case=False, na=False)]
        
        if selected_variete != 'Toutes':
            filtered_df = filtered_df[filtered_df['nom_variete'] == selected_variete]
        
        if selected_producteur != 'Tous':
            filtered_df = filtered_df[filtered_df['nom_producteur'] == selected_producteur]
        
        st.markdown("---")
        st.info(f"📊 {len(filtered_df)} lot(s) affiché(s) sur {len(df)} total")
        
        if 'original_stock_df' not in st.session_state:
            st.session_state.original_stock_df = filtered_df.copy()
        
        # ⭐ EN-TÊTE avec BOUTONS
        col_title, col_save, col_refresh, col_add, col_details = st.columns([2, 1, 1, 1, 1.5])
        
        with col_title:
            st.subheader("📋 Liste des Lots")
        
        with col_save:
            if st.button("💾 Enregistrer", use_container_width=True, type="primary", key="btn_save_top"):
                if 'edited_stock_df' in st.session_state:
                    success, message = save_stock_changes(st.session_state.original_stock_df, st.session_state.edited_stock_df, varietes_dict, producteurs_dict)
                    if success:
                        st.success(message)
                        st.session_state.pop('original_stock_df', None)
                        st.session_state.pop('edited_stock_df', None)
                        st.rerun()
                    else:
                        if "Aucune modification" in message:
                            st.info(message)
                        else:
                            st.error(message)
                else:
                    st.warning("⚠️ Aucune modification à enregistrer")
        
        with col_refresh:
            if st.button("🔄 Actualiser", use_container_width=True, key="btn_refresh_top"):
                st.session_state.pop('original_stock_df', None)
                st.rerun()
        
        with col_add:
            if st.button("➕ Ajouter", use_container_width=True, type="primary", key="btn_add_top"):
                st.session_state.show_add_form = not st.session_state.get('show_add_form', False)
                st.rerun()
        
        # ⭐ BOUTON DÉTAILS STOCK (avec compteur sélectionnés)
        with col_details:
            nb_selected = len(st.session_state.get('selected_lots_for_details', []))
            
            if nb_selected > 0:
                btn_label = f"📦 Détails ({nb_selected})"
                btn_disabled = False
            else:
                btn_label = "📦 Détails Stock"
                btn_disabled = True
            
            if st.button(btn_label, use_container_width=True, type="secondary", key="btn_view_details", disabled=btn_disabled):
                st.switch_page("pages/03_Détails stock.py")
        
        # Colonnes à afficher
        display_columns = [
            'id',
            'code_lot_interne', 
            'nom_usage', 
            'nom_variete',
            'nom_producteur',
            'calibre_min',
            'calibre_max',
            'prix_achat_euro_tonne',
            'tare_achat_pct',
            'valeur_lot_euro',
            'age_jours',
            'statut'
        ]
        
        available_columns = [col for col in display_columns if col in filtered_df.columns]
        display_df = filtered_df[available_columns].copy()
        
        # Configuration dropdowns
        column_config = {
            "id": None,
            "poids_total_brut_kg": None,
            "nom_variete": st.column_config.SelectboxColumn(
                "Variété",
                options=sorted(varietes_dict.keys()),
                required=False
            ),
            "nom_producteur": st.column_config.SelectboxColumn(
                "Producteur",
                options=sorted(producteurs_dict.keys()),
                required=False
            )
        }
        
        # ⭐ AJOUTER COLONNE CHECKBOX POUR SÉLECTION
        df_with_select = display_df.copy()
        df_with_select.insert(0, "Select", False)
        
        column_config["Select"] = st.column_config.CheckboxColumn(
            "☑",
            help="Cochez les lots puis cliquez 'Actualiser' pour voir le bouton Détails Stock",
            default=False,
            width="small"
        )
        
        # DATA EDITOR avec colonne checkbox
        edited_df = st.data_editor(
            df_with_select,
            use_container_width=True,
            num_rows="fixed",
            disabled=['id', 'code_lot_interne', 'poids_total_brut_kg', 'valeur_lot_euro', 'age_jours'],
            column_config=column_config,
            key="stock_editor"
        )
        
        # Stocker edited_df
        edited_df_for_save = edited_df.drop('Select', axis=1) if 'Select' in edited_df.columns else edited_df
        st.session_state.edited_stock_df = edited_df_for_save
        
        # ⭐ RÉCUPÉRER LES LOTS SÉLECTIONNÉS
        selected_lot_ids = []
        
        if 'Select' in edited_df.columns:
            selected_rows = edited_df[edited_df['Select'] == True]
            
            if len(selected_rows) > 0:
                selected_lot_ids = selected_rows['id'].tolist()
                
                if len(selected_lot_ids) > 10:
                    st.warning("⚠️ Vous avez sélectionné plus de 10 lots. Seuls les 10 premiers seront affichés.")
                    selected_lot_ids = selected_lot_ids[:10]
        
        # Stocker dans session_state
        st.session_state.selected_lots_for_details = selected_lot_ids
        
        # ⭐ DÉTECTION INTELLIGENTE : Rerun si sélection change
        if 'Select' in edited_df.columns:
            current_select_state = tuple(sorted(selected_lot_ids))
            previous_select_state = st.session_state.get('previous_select_state', tuple())
            
            if current_select_state != previous_select_state and not st.session_state.get('is_rerunning_for_select', False):
                st.session_state.previous_select_state = current_select_state
                st.session_state.is_rerunning_for_select = True
                st.rerun()
            else:
                st.session_state.is_rerunning_for_select = False
        
        # Afficher info sélection
        if len(selected_lot_ids) > 0:
            col_msg, col_btn = st.columns([3, 1])
            
            with col_msg:
                st.success(f"✅ {len(selected_lot_ids)} lot(s) sélectionné(s) pour voir les détails stock")
            
            with col_btn:
                if st.button(f"📦 Aller aux Détails ({len(selected_lot_ids)})", use_container_width=True, type="primary", key="btn_goto_details_bottom"):
                    st.switch_page("pages/03_Détails stock.py")
        
        # Exports
        st.markdown("---")
        st.subheader("📤 Exports")
        col1, col2 = st.columns(2)
        
        with col1:
            csv = filtered_df.to_csv(index=False).encode('utf-8')
            st.download_button("📥 CSV", csv, f"lots_{datetime.now().strftime('%Y%m%d')}.csv", "text/csv", use_container_width=True)
        
        with col2:
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                filtered_df.to_excel(writer, index=False, sheet_name='Lots')
            st.download_button("📥 Excel", buffer.getvalue(), f"lots_{datetime.now().strftime('%Y%m%d')}.xlsx", 
                              "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)
        
        # ⭐ SUPPRESSION LOTS (ADMIN UNIQUEMENT)
        if is_admin():
            st.markdown("---")
            st.subheader("🗑️ Suppression de Lots (Admin)")
            
            lot_options = [f"{row['id']} - {row['code_lot_interne']} - {row['nom_usage']}" for _, row in df.iterrows()]
            
            if lot_options:
                selected_lot = st.selectbox(
                    "Sélectionner un lot à supprimer",
                    options=lot_options,
                    key="delete_lot_selector"
                )
                
                selected_lot_id = int(selected_lot.split(" - ")[0])
                
                col1, col2 = st.columns([1, 5])
                with col1:
                    if st.button("🗑️ Supprimer", use_container_width=True, type="secondary", key="btn_delete_lot"):
                        st.session_state.confirm_delete_lot_id = selected_lot_id
                        st.session_state.confirm_delete_lot_name = selected_lot
                
                if st.session_state.get('confirm_delete_lot_id'):
                    st.warning(f"⚠️ **ATTENTION** : Vous êtes sur le point de supprimer le lot :\n\n**{st.session_state.confirm_delete_lot_name}**")
                    
                    col_confirm1, col_confirm2, col_confirm3 = st.columns([1, 1, 4])
                    
                    with col_confirm1:
                        if st.button("✅ CONFIRMER", use_container_width=True, type="primary", key="btn_confirm_delete"):
                            lot_id = st.session_state.confirm_delete_lot_id
                            
                            success, message = delete_lot(lot_id)
                            
                            if success:
                                st.success(message)
                                st.session_state.pop('confirm_delete_lot_id', None)
                                st.session_state.pop('confirm_delete_lot_name', None)
                                st.session_state.pop('original_stock_df', None)
                                time.sleep(1)
                                st.rerun()
                            else:
                                st.error(message)
                                st.session_state.pop('confirm_delete_lot_id', None)
                                st.session_state.pop('confirm_delete_lot_name', None)
                    
                    with col_confirm2:
                        if st.button("❌ ANNULER", use_container_width=True, key="btn_cancel_delete"):
                            st.session_state.pop('confirm_delete_lot_id', None)
                            st.session_state.pop('confirm_delete_lot_name', None)
                            st.rerun()
            else:
                st.info("ℹ️ Aucun lot à supprimer")
    
    else:
        st.warning("⚠️ Aucun lot trouvé")
    
    show_footer()

# ===== ONGLET 2 : IMPORT EXCEL =====
with tab2:
    st.subheader("📥 Import en Masse via Excel")
    st.markdown("*Import intelligent avec détection automatique des fautes de frappe*")
    st.markdown("---")
    
    # Étape 1 : Télécharger template
    st.markdown("#### 1️⃣ Télécharger le Template Excel")
    
    col1, col2 = st.columns([3, 1])
    
    with col1:
        st.info("""
        📋 **Template avec 3 onglets** :
        - **Lots** : Vos données à importer (1 exemple fourni)
        - **Variétés** : Liste complète des variétés valides
        - **Producteurs** : Liste complète des producteurs valides
        """)
    
    with col2:
        if st.button("📥 Télécharger", use_container_width=True, type="primary", key="btn_download_template_import"):
            template_data = create_import_template_excel()
            if template_data:
                st.download_button(
                    label="💾 Template Excel",
                    data=template_data,
                    file_name=f"template_import_lots_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True
                )
    
    st.markdown("---")
    
    # Étape 2 : Upload fichier
    st.markdown("#### 2️⃣ Uploader votre Fichier Excel")
    
    uploaded_file = st.file_uploader(
        "Choisir un fichier Excel (.xlsx)",
        type=['xlsx'],
        key="import_excel_file_upload",
        help="Le fichier doit contenir un onglet 'Lots' avec les colonnes du template"
    )
    
    if uploaded_file:
        try:
            df_import = pd.read_excel(uploaded_file, sheet_name='Lots')
            st.success(f"✅ Fichier chargé : **{len(df_import)}** ligne(s)")
            
            with st.expander("👁️ Aperçu Données Brutes", expanded=False):
                st.dataframe(df_import.head(10), use_container_width=True)
            
            st.markdown("---")
            
            # Étape 3 : Validation
            st.markdown("#### 3️⃣ Validation des Données")
            
            if st.button("🔍 Valider les Données", type="primary", use_container_width=True, key="btn_validate_import"):
                with st.spinner("⏳ Validation en cours..."):
                    valid_refs = get_valid_references_import()
                    
                    if valid_refs:
                        df_validated, report = validate_import_data_excel(df_import, valid_refs)
                        st.session_state['df_validated_import'] = df_validated
                        st.session_state['import_report'] = report
                        st.rerun()
            
            # Afficher résultats validation
            if 'df_validated_import' in st.session_state:
                df_val = st.session_state['df_validated_import']
                report = st.session_state['import_report']
                
                st.markdown("---")
                st.markdown("#### 📊 Résultats Validation")
                
                col1, col2, col3, col4 = st.columns(4)
                
                with col1:
                    st.metric("📊 Total", report['total'])
                with col2:
                    pct_valid = f"{report['valid']/report['total']*100:.0f}%" if report['total'] > 0 else "0%"
                    st.metric("✅ Valides", report['valid'], delta=pct_valid)
                with col3:
                    st.metric("⚠️ Warnings", report['warnings'])
                with col4:
                    st.metric("❌ Erreurs", report['errors'])
                
                st.markdown("---")
                st.markdown("#### 📋 Prévisualisation")
                
                df_display = df_val[[
                    'code_lot_interne', 'nom_usage', 'code_variete', '_variete_corrected',
                    'code_producteur', '_producteur_corrected', 'nombre_unites',
                    '_status', '_errors', '_warnings'
                ]].copy()
                
                st.dataframe(df_display, use_container_width=True, hide_index=True)
                
                st.caption("""
                **Légende** :
                - 🟢 **valid** : Lot OK
                - 🟠 **warning** : Corrections auto appliquées
                - 🔴 **error** : Erreurs bloquantes
                """)
                
                st.markdown("---")
                
                # Étape 4 : Import
                if report['errors'] == 0:
                    st.success(f"✅ **Tous les lots sont valides !** ({report['valid'] + report['warnings']} lots)")
                    
                    if report['warnings'] > 0:
                        st.warning(f"⚠️ {report['warnings']} lot(s) avec corrections auto. Vérifiez avant import.")
                    
                    if st.button("✅ CONFIRMER IMPORT", type="primary", use_container_width=True, key="btn_confirm_import"):
                        with st.spinner("⏳ Import en cours..."):
                            success, message = import_validated_lots_excel(df_val)
                            
                            if success:
                                st.success(message)
                                st.balloons()
                                time.sleep(2)
                                st.session_state.pop('df_validated_import', None)
                                st.session_state.pop('import_report', None)
                                st.rerun()
                            else:
                                st.error(message)
                else:
                    st.error(f"❌ **{report['errors']} lot(s) avec erreurs bloquantes**")
                    st.info("💡 Corrigez les erreurs dans Excel, puis réuploadez.")
                    
                    with st.expander("📝 Détails des Erreurs", expanded=True):
                        df_errors = df_val[df_val['_status'] == 'error'][['code_lot_interne', '_errors']]
                        st.dataframe(df_errors, use_container_width=True, hide_index=True)
        
        except Exception as e:
            st.error(f"❌ Erreur lecture fichier : {str(e)}")
    
    else:
        st.info("👆 Uploadez votre fichier Excel pour commencer")
