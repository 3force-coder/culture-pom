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
    /* Badges statut */
    .badge-valid {
        background-color: #d4edda;
        color: #155724;
        padding: 0.2rem 0.5rem;
        border-radius: 0.3rem;
        font-weight: 600;
    }
    .badge-warning {
        background-color: #fff3cd;
        color: #856404;
        padding: 0.2rem 0.5rem;
        border-radius: 0.3rem;
        font-weight: 600;
    }
    .badge-error {
        background-color: #f8d7da;
        color: #721c24;
        padding: 0.2rem 0.5rem;
        border-radius: 0.3rem;
        font-weight: 600;
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
# FONCTIONS IMPORT EXCEL - MATCHING INTELLIGENT
# ============================================================================

def fuzzy_match_value(value, valid_values, threshold=0.8):
    """
    Match fuzzy avec difflib (intégré Python, pas de dépendance externe)
    
    Returns:
        - (True, value, "exact") si match exact
        - (True, best_match, "fuzzy") si similarité >= threshold
        - (False, None, "error") si aucun match
    """
    if pd.isna(value) or str(value).strip() == '':
        return (True, None, "empty")
    
    value_clean = str(value).strip().upper()
    
    # 1. Match exact (case insensitive)
    for valid in valid_values:
        if valid.upper() == value_clean:
            return (True, valid, "exact")
    
    # 2. Match fuzzy avec difflib
    matches = get_close_matches(value_clean, [v.upper() for v in valid_values], n=1, cutoff=threshold)
    
    if matches:
        # Retrouver la valeur originale (avec casse correcte)
        matched_upper = matches[0]
        for valid in valid_values:
            if valid.upper() == matched_upper:
                return (True, valid, "fuzzy")
    
    return (False, None, "error")


def get_valid_references():
    """Récupère toutes les valeurs valides depuis DB"""
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
        
        # Types conditionnement
        cursor.execute("SELECT DISTINCT type_conditionnement FROM stock_emplacements WHERE type_conditionnement IS NOT NULL")
        rows_type = cursor.fetchall()
        types_cond = [row['type_conditionnement'] for row in rows_type]
        if not types_cond:
            types_cond = ['Pallox', 'Petit Pallox', 'Big Bag']
        
        cursor.close()
        conn.close()
        
        return {
            'varietes': varietes,
            'producteurs': producteurs,
            'types_conditionnement': types_cond
        }
        
    except Exception as e:
        st.error(f"❌ Erreur chargement références : {str(e)}")
        return None


def create_import_template():
    """Crée un template Excel avec 3 onglets"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # ===== ONGLET 1 : Lots (template vide) =====
        lots_columns = [
            'code_lot_interne',
            'nom_usage',
            'code_producteur',
            'code_variete',
            'nombre_unites',
            'type_conditionnement',
            'poids_unitaire_kg',
            'date_entree_stock',
            'calibre_min',
            'calibre_max',
            'notes'
        ]
        
        df_lots_template = pd.DataFrame(columns=lots_columns)
        
        # Ajouter 2 lignes d'exemple
        df_lots_template.loc[0] = [
            'LOT_2025_AGATA_001',
            'AGATA BOSSELER',
            'ACQU001',
            'AGATA',
            10,
            'Pallox',
            1900,
            '2025-01-15',
            35,
            50,
            'Exemple lot 1'
        ]
        
        df_lots_template.loc[1] = [
            'LOT_2025_BINTJE_001',
            'BINTJE DUPONT',
            'BINT002',
            'BINTJE',
            5,
            'Pallox',
            1900,
            '2025-01-16',
            40,
            55,
            ''
        ]
        
        # ===== ONGLET 2 : Variétés (référence) =====
        cursor.execute("""
            SELECT code_variete, nom_variete, type, utilisation
            FROM ref_varietes
            WHERE is_active = TRUE
            ORDER BY code_variete
        """)
        rows = cursor.fetchall()
        df_varietes = pd.DataFrame(rows)
        
        # ===== ONGLET 3 : Producteurs (référence) =====
        cursor.execute("""
            SELECT code_producteur, nom, departement, ville
            FROM ref_producteurs
            WHERE is_active = TRUE
            ORDER BY code_producteur
        """)
        rows = cursor.fetchall()
        df_producteurs = pd.DataFrame(rows)
        
        cursor.close()
        conn.close()
        
        # ===== CRÉER FICHIER EXCEL =====
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            df_lots_template.to_excel(writer, sheet_name='Lots', index=False)
            df_varietes.to_excel(writer, sheet_name='Variétés', index=False)
            df_producteurs.to_excel(writer, sheet_name='Producteurs', index=False)
        
        return buffer.getvalue()
        
    except Exception as e:
        st.error(f"❌ Erreur création template : {str(e)}")
        return None


def validate_import_data(df, valid_refs):
    """
    Valide les données importées
    
    Returns:
        df_validated : DataFrame avec colonnes validation
        report : Dict avec statistiques
    """
    df_validated = df.copy()
    
    # Colonnes de validation
    df_validated['_status'] = 'valid'
    df_validated['_errors'] = ''
    df_validated['_warnings'] = ''
    df_validated['_variete_corrected'] = df_validated['code_variete']
    df_validated['_producteur_corrected'] = df_validated['code_producteur']
    df_validated['_type_cond_corrected'] = df_validated['type_conditionnement']
    
    errors_count = 0
    warnings_count = 0
    
    for idx, row in df_validated.iterrows():
        errors = []
        warnings = []
        
        # ===== 1. CHAMPS OBLIGATOIRES =====
        if pd.isna(row['code_lot_interne']) or str(row['code_lot_interne']).strip() == '':
            errors.append("Code lot manquant")
        
        if pd.isna(row['nom_usage']) or str(row['nom_usage']).strip() == '':
            errors.append("Nom usage manquant")
        
        if pd.isna(row['nombre_unites']) or row['nombre_unites'] <= 0:
            errors.append("Nombre unités invalide")
        
        if pd.isna(row['type_conditionnement']) or str(row['type_conditionnement']).strip() == '':
            errors.append("Type conditionnement manquant")
        
        # ===== 2. VALIDATION VARIÉTÉ =====
        if not pd.isna(row['code_variete']) and str(row['code_variete']).strip() != '':
            is_valid, matched, match_type = fuzzy_match_value(
                row['code_variete'], 
                valid_refs['varietes']
            )
            
            if is_valid:
                if match_type == "fuzzy":
                    warnings.append(f"Variété '{row['code_variete']}' → '{matched}'")
                    df_validated.at[idx, '_variete_corrected'] = matched
                elif match_type == "exact":
                    df_validated.at[idx, '_variete_corrected'] = matched
            else:
                errors.append(f"Variété '{row['code_variete']}' introuvable")
                df_validated.at[idx, '_variete_corrected'] = None
        
        # ===== 3. VALIDATION PRODUCTEUR =====
        if not pd.isna(row['code_producteur']) and str(row['code_producteur']).strip() != '':
            is_valid, matched, match_type = fuzzy_match_value(
                row['code_producteur'], 
                valid_refs['producteurs']
            )
            
            if is_valid:
                if match_type == "fuzzy":
                    warnings.append(f"Producteur '{row['code_producteur']}' → '{matched}'")
                    df_validated.at[idx, '_producteur_corrected'] = matched
                elif match_type == "exact":
                    df_validated.at[idx, '_producteur_corrected'] = matched
            else:
                errors.append(f"Producteur '{row['code_producteur']}' introuvable")
                df_validated.at[idx, '_producteur_corrected'] = None
        
        # ===== 4. VALIDATION TYPE CONDITIONNEMENT =====
        is_valid, matched, match_type = fuzzy_match_value(
            row['type_conditionnement'], 
            valid_refs['types_conditionnement']
        )
        
        if is_valid:
            if match_type == "fuzzy":
                warnings.append(f"Type '{row['type_conditionnement']}' → '{matched}'")
                df_validated.at[idx, '_type_cond_corrected'] = matched
            elif match_type == "exact":
                df_validated.at[idx, '_type_cond_corrected'] = matched
        else:
            errors.append(f"Type '{row['type_conditionnement']}' invalide")
            df_validated.at[idx, '_type_cond_corrected'] = None
        
        # ===== 5. DÉFINIR STATUT =====
        if errors:
            df_validated.at[idx, '_status'] = 'error'
            df_validated.at[idx, '_errors'] = ' | '.join(errors)
            errors_count += 1
        elif warnings:
            df_validated.at[idx, '_status'] = 'warning'
            df_validated.at[idx, '_warnings'] = ' | '.join(warnings)
            warnings_count += 1
    
    # Rapport
    report = {
        'total': len(df_validated),
        'valid': len(df_validated[df_validated['_status'] == 'valid']),
        'warnings': warnings_count,
        'errors': errors_count
    }
    
    return df_validated, report


def import_validated_lots(df_validated):
    """Importe uniquement les lots valides en base"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Filtrer lots valides ou warnings (erreurs exclues)
        df_to_import = df_validated[df_validated['_status'].isin(['valid', 'warning'])].copy()
        
        imported_count = 0
        failed_lots = []
        
        for idx, row in df_to_import.iterrows():
            try:
                # Utiliser valeurs corrigées
                code_variete = row['_variete_corrected'] if pd.notna(row['_variete_corrected']) else None
                code_producteur = row['_producteur_corrected'] if pd.notna(row['_producteur_corrected']) else None
                type_cond = row['_type_cond_corrected']
                
                # Calculer poids total
                poids_unitaire = float(row['poids_unitaire_kg']) if pd.notna(row['poids_unitaire_kg']) else None
                nombre_unites = int(row['nombre_unites'])
                poids_total = poids_unitaire * nombre_unites if poids_unitaire else None
                
                # INSERT lot
                query_lot = """
                INSERT INTO lots_bruts (
                    code_lot_interne, nom_usage, code_producteur, code_variete,
                    nombre_unites, type_conditionnement, poids_unitaire_kg, poids_total_brut_kg,
                    date_entree_stock, calibre_min, calibre_max, notes,
                    statut, is_active, created_at, updated_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'EN_STOCK', TRUE, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                """
                
                cursor.execute(query_lot, (
                    row['code_lot_interne'],
                    row['nom_usage'],
                    code_producteur,
                    code_variete,
                    nombre_unites,
                    type_cond,
                    poids_unitaire,
                    poids_total,
                    row['date_entree_stock'] if pd.notna(row['date_entree_stock']) else None,
                    int(row['calibre_min']) if pd.notna(row['calibre_min']) else None,
                    int(row['calibre_max']) if pd.notna(row['calibre_max']) else None,
                    row['notes'] if pd.notna(row['notes']) else None
                ))
                
                imported_count += 1
                
            except Exception as e:
                failed_lots.append(f"{row['code_lot_interne']}: {str(e)}")
        
        conn.commit()
        cursor.close()
        conn.close()
        
        if failed_lots:
            return True, f"✅ {imported_count} lots importés | ⚠️ {len(failed_lots)} échecs : {', '.join(failed_lots[:3])}"
        else:
            return True, f"✅ {imported_count} lots importés avec succès"
        
    except Exception as e:
        if 'conn' in locals():
            conn.rollback()
        return False, f"❌ Erreur import : {str(e)}"


# ============================================================================
# FONCTIONS UTILITAIRES LOTS (code existant)
# ============================================================================

def get_lots():
    """Récupère tous les lots"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        query = """
        SELECT 
            l.id,
            l.code_lot_interne,
            l.nom_usage,
            l.code_producteur,
            COALESCE(p.nom, l.code_producteur) as nom_producteur,
            l.code_variete,
            COALESCE(v.nom_variete, l.code_variete) as nom_variete,
            l.date_entree_stock,
            l.nombre_unites,
            l.type_conditionnement,
            l.poids_total_brut_kg,
            l.statut,
            l.notes,
            l.is_active
        FROM lots_bruts l
        LEFT JOIN ref_producteurs p ON l.code_producteur = p.code_producteur
        LEFT JOIN ref_varietes v ON l.code_variete = v.code_variete
        WHERE l.is_active = TRUE
        ORDER BY l.date_entree_stock DESC, l.code_lot_interne
        """
        
        cursor.execute(query)
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        
        if rows:
            df = pd.DataFrame(rows)
            # Convertir colonnes numériques
            numeric_cols = ['nombre_unites', 'poids_total_brut_kg']
            for col in numeric_cols:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
            return df
        return pd.DataFrame()
        
    except Exception as e:
        st.error(f"❌ Erreur chargement lots : {str(e)}")
        return pd.DataFrame()


def get_active_varietes():
    """Récupère les variétés actives"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT code_variete FROM ref_varietes WHERE is_active = TRUE ORDER BY code_variete")
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        return [row['code_variete'] for row in rows] if rows else []
    except Exception as e:
        st.error(f"❌ Erreur : {str(e)}")
        return []


def get_active_producteurs():
    """Récupère les producteurs actifs"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT code_producteur, nom FROM ref_producteurs WHERE is_active = TRUE ORDER BY nom")
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        return [(row['code_producteur'], row['nom']) for row in rows] if rows else []
    except Exception as e:
        st.error(f"❌ Erreur : {str(e)}")
        return []


def create_lot(data):
    """Crée un nouveau lot"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Calculer poids total
        if data.get('poids_unitaire_kg') and data.get('nombre_unites'):
            data['poids_total_brut_kg'] = data['poids_unitaire_kg'] * data['nombre_unites']
        
        # Colonnes
        columns = [
            'code_lot_interne', 'nom_usage', 'code_producteur', 'code_variete',
            'nombre_unites', 'type_conditionnement', 'poids_unitaire_kg', 'poids_total_brut_kg',
            'date_entree_stock', 'calibre_min', 'calibre_max', 'notes'
        ]
        
        values = [data.get(col) for col in columns]
        placeholders = ', '.join(['%s'] * len(columns))
        columns_str = ', '.join(columns)
        
        query = f"""
        INSERT INTO lots_bruts ({columns_str}, statut, is_active, created_at, updated_at)
        VALUES ({placeholders}, 'EN_STOCK', TRUE, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        RETURNING id
        """
        
        cursor.execute(query, values)
        lot_id = cursor.fetchone()['id']
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return True, f"✅ Lot #{lot_id} créé avec succès"
        
    except Exception as e:
        if 'conn' in locals():
            conn.rollback()
        return False, f"❌ Erreur : {str(e)}"


# ============================================================================
# INTERFACE PRINCIPALE - ONGLETS
# ============================================================================

# Créer 3 onglets
tab1, tab2, tab3 = st.tabs(["📋 Liste Lots", "➕ Créer Lot", "📥 Import Excel"])

# ============================================================================
# ONGLET 1 : LISTE LOTS
# ============================================================================

with tab1:
    st.subheader("📋 Liste des Lots")
    
    df_lots = get_lots()
    
    if not df_lots.empty:
        # Métriques
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("📦 Total Lots", len(df_lots))
        
        with col2:
            total_unites = df_lots['nombre_unites'].sum()
            st.metric("📊 Total Unités", f"{int(total_unites):,}")
        
        with col3:
            total_tonnes = df_lots['poids_total_brut_kg'].sum() / 1000
            st.metric("⚖️ Total Tonnage", f"{total_tonnes:,.1f} T")
        
        st.markdown("---")
        
        # Filtres
        col1, col2, col3 = st.columns(3)
        
        with col1:
            varietes_list = ["Toutes"] + sorted(df_lots['nom_variete'].dropna().unique().tolist())
            filtre_variete = st.selectbox("Filtrer par variété", varietes_list, key="filtre_var_liste")
        
        with col2:
            producteurs_list = ["Tous"] + sorted(df_lots['nom_producteur'].dropna().unique().tolist())
            filtre_producteur = st.selectbox("Filtrer par producteur", producteurs_list, key="filtre_prod_liste")
        
        with col3:
            statuts_list = ["Tous"] + sorted(df_lots['statut'].dropna().unique().tolist())
            filtre_statut = st.selectbox("Filtrer par statut", statuts_list, key="filtre_statut")
        
        # Appliquer filtres
        df_filtered = df_lots.copy()
        if filtre_variete != "Toutes":
            df_filtered = df_filtered[df_filtered['nom_variete'] == filtre_variete]
        if filtre_producteur != "Tous":
            df_filtered = df_filtered[df_filtered['nom_producteur'] == filtre_producteur]
        if filtre_statut != "Tous":
            df_filtered = df_filtered[df_filtered['statut'] == filtre_statut]
        
        st.info(f"📊 {len(df_filtered)} lot(s) affiché(s)")
        
        # Tableau
        df_display = df_filtered[[
            'code_lot_interne', 'nom_usage', 'nom_variete', 'nom_producteur',
            'date_entree_stock', 'nombre_unites', 'type_conditionnement',
            'poids_total_brut_kg', 'statut'
        ]].copy()
        
        column_config = {
            'code_lot_interne': st.column_config.TextColumn("Code Lot", width="medium"),
            'nom_usage': st.column_config.TextColumn("Nom Usage", width="medium"),
            'nom_variete': st.column_config.TextColumn("Variété", width="small"),
            'nom_producteur': st.column_config.TextColumn("Producteur", width="medium"),
            'date_entree_stock': st.column_config.DateColumn("Date Entrée", format="DD/MM/YYYY"),
            'nombre_unites': st.column_config.NumberColumn("Unités", format="%d"),
            'type_conditionnement': st.column_config.TextColumn("Type", width="small"),
            'poids_total_brut_kg': st.column_config.NumberColumn("Poids (kg)", format="%.0f"),
            'statut': st.column_config.TextColumn("Statut", width="small")
        }
        
        st.dataframe(
            df_display,
            column_config=column_config,
            use_container_width=True,
            hide_index=True
        )
        
        # Bouton Détails
        st.markdown("---")
        if st.button("👁️ Voir Détails Stock", type="primary", use_container_width=True):
            st.switch_page("pages/03_Détails stock.py")
    
    else:
        st.warning("⚠️ Aucun lot enregistré. Créez-en un ou importez depuis Excel !")

# ============================================================================
# ONGLET 2 : CRÉER LOT
# ============================================================================

with tab2:
    st.subheader("➕ Créer un Nouveau Lot")
    
    # Formulaire
    with st.form("form_create_lot", clear_on_submit=True):
        col1, col2 = st.columns(2)
        
        with col1:
            code_lot = st.text_input("Code Lot *", placeholder="LOT_2025_AGATA_001")
            nom_usage = st.text_input("Nom Usage *", placeholder="AGATA BOSSELER")
            
            # Producteurs
            producteurs = get_active_producteurs()
            prod_options = [""] + [f"{p[0]} - {p[1]}" for p in producteurs]
            selected_prod = st.selectbox("Producteur", prod_options)
            code_producteur = selected_prod.split(" - ")[0] if selected_prod else None
            
            # Variétés
            varietes = get_active_varietes()
            code_variete = st.selectbox("Variété", [""] + varietes)
            
            nombre_unites = st.number_input("Nombre Unités *", min_value=1, value=1, step=1)
        
        with col2:
            type_conditionnement = st.selectbox("Type Conditionnement *", 
                                                ["Pallox", "Petit Pallox", "Big Bag", "Vrac"])
            
            poids_unitaire = st.number_input("Poids Unitaire (kg)", min_value=0.0, value=1900.0, step=100.0)
            
            date_entree = st.date_input("Date Entrée", value=datetime.now().date())
            
            calibre_min = st.number_input("Calibre Min", min_value=0, value=35, step=5)
            calibre_max = st.number_input("Calibre Max", min_value=0, value=50, step=5)
        
        notes = st.text_area("Notes (optionnel)")
        
        submitted = st.form_submit_button("✅ Créer le Lot", type="primary", use_container_width=True)
        
        if submitted:
            # Validation
            if not code_lot or not nom_usage or not nombre_unites or not type_conditionnement:
                st.error("❌ Champs obligatoires manquants : Code Lot, Nom Usage, Nombre Unités, Type")
            else:
                data = {
                    'code_lot_interne': code_lot,
                    'nom_usage': nom_usage,
                    'code_producteur': code_producteur if code_producteur else None,
                    'code_variete': code_variete if code_variete else None,
                    'nombre_unites': nombre_unites,
                    'type_conditionnement': type_conditionnement,
                    'poids_unitaire_kg': poids_unitaire,
                    'date_entree_stock': date_entree,
                    'calibre_min': calibre_min,
                    'calibre_max': calibre_max,
                    'notes': notes if notes else None
                }
                
                success, message = create_lot(data)
                
                if success:
                    st.success(message)
                    show_confetti_animation()
                    time.sleep(2)
                    st.rerun()
                else:
                    st.error(message)

# ============================================================================
# ONGLET 3 : IMPORT EXCEL
# ============================================================================

with tab3:
    st.subheader("📥 Import en Masse via Excel")
    st.markdown("*Import intelligent avec détection automatique des fautes de frappe*")
    
    st.markdown("---")
    
    # ===== ÉTAPE 1 : Télécharger template =====
    st.markdown("#### 1️⃣ Télécharger le Template Excel")
    
    col1, col2 = st.columns([3, 1])
    
    with col1:
        st.info("""
        📋 **Template avec 3 onglets** :
        - **Lots** : Vos données à importer (2 exemples fournis)
        - **Variétés** : Liste complète des variétés valides
        - **Producteurs** : Liste complète des producteurs valides
        """)
    
    with col2:
        if st.button("📥 Télécharger", use_container_width=True, type="primary", key="btn_download_template"):
            template_data = create_import_template()
            if template_data:
                st.download_button(
                    label="💾 Template Excel",
                    data=template_data,
                    file_name=f"template_import_lots_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True
                )
    
    st.markdown("---")
    
    # ===== ÉTAPE 2 : Upload fichier =====
    st.markdown("#### 2️⃣ Uploader votre Fichier Excel")
    
    uploaded_file = st.file_uploader(
        "Choisir un fichier Excel (.xlsx)",
        type=['xlsx'],
        key="import_excel_file",
        help="Le fichier doit contenir un onglet 'Lots' avec les colonnes du template"
    )
    
    if uploaded_file:
        try:
            # Lire onglet Lots
            df_import = pd.read_excel(uploaded_file, sheet_name='Lots')
            
            st.success(f"✅ Fichier chargé : **{len(df_import)}** ligne(s)")
            
            # Aperçu
            with st.expander("👁️ Aperçu Données Brutes", expanded=False):
                st.dataframe(df_import.head(10), use_container_width=True)
            
            st.markdown("---")
            
            # ===== ÉTAPE 3 : Validation =====
            st.markdown("#### 3️⃣ Validation des Données")
            
            if st.button("🔍 Valider les Données", type="primary", use_container_width=True, key="btn_validate"):
                with st.spinner("⏳ Validation en cours..."):
                    # Récupérer références
                    valid_refs = get_valid_references()
                    
                    if valid_refs:
                        # Valider
                        df_validated, report = validate_import_data(df_import, valid_refs)
                        
                        # Stocker en session
                        st.session_state['df_validated'] = df_validated
                        st.session_state['import_report'] = report
                        
                        st.rerun()
            
            # ===== AFFICHER RÉSULTATS VALIDATION =====
            if 'df_validated' in st.session_state:
                df_val = st.session_state['df_validated']
                report = st.session_state['import_report']
                
                st.markdown("---")
                st.markdown("#### 📊 Résultats Validation")
                
                # Statistiques
                col1, col2, col3, col4 = st.columns(4)
                
                with col1:
                    st.metric("📊 Total", report['total'])
                
                with col2:
                    pct_valid = f"{report['valid']/report['total']*100:.0f}%" if report['total'] > 0 else "0%"
                    st.metric("✅ Valides", report['valid'], delta=pct_valid)
                
                with col3:
                    st.metric("⚠️ Warnings", report['warnings'], 
                             help="Corrections automatiques appliquées")
                
                with col4:
                    st.metric("❌ Erreurs", report['errors'],
                             help="Lots rejetés (à corriger)")
                
                st.markdown("---")
                
                # Tableau prévisualisation
                st.markdown("#### 📋 Prévisualisation (Code Couleur)")
                
                # Créer DataFrame affichage
                df_display = df_val[[
                    'code_lot_interne', 'nom_usage',
                    'code_variete', '_variete_corrected',
                    'code_producteur', '_producteur_corrected',
                    'nombre_unites', 'type_conditionnement',
                    '_status', '_errors', '_warnings'
                ]].copy()
                
                # Renommer colonnes
                df_display = df_display.rename(columns={
                    'code_lot_interne': 'Code Lot',
                    'nom_usage': 'Nom Usage',
                    'code_variete': 'Variété (Excel)',
                    '_variete_corrected': '✓ Corrigé',
                    'code_producteur': 'Producteur (Excel)',
                    '_producteur_corrected': '✓ Corrigé',
                    'nombre_unites': 'Unités',
                    'type_conditionnement': 'Type',
                    '_status': 'Statut',
                    '_errors': 'Erreurs',
                    '_warnings': 'Corrections Auto'
                })
                
                # Configuration colonnes avec couleurs
                column_config = {
                    'Code Lot': st.column_config.TextColumn("Code Lot", width="medium"),
                    'Nom Usage': st.column_config.TextColumn("Nom Usage", width="medium"),
                    'Variété (Excel)': st.column_config.TextColumn("Variété (Excel)", width="small"),
                    '✓ Corrigé': st.column_config.TextColumn("✓ Corrigé", width="small"),
                    'Producteur (Excel)': st.column_config.TextColumn("Producteur (Excel)", width="small"),
                    '✓ Corrigé.1': st.column_config.TextColumn("✓ Corrigé", width="small"),
                    'Unités': st.column_config.NumberColumn("Unités", format="%d"),
                    'Type': st.column_config.TextColumn("Type", width="small"),
                    'Statut': st.column_config.TextColumn("Statut", width="small"),
                    'Erreurs': st.column_config.TextColumn("Erreurs", width="large"),
                    'Corrections Auto': st.column_config.TextColumn("Corrections Auto", width="large")
                }
                
                st.dataframe(
                    df_display,
                    column_config=column_config,
                    use_container_width=True,
                    hide_index=True
                )
                
                # Légende couleurs
                st.caption("""
                **Légende** :
                - 🟢 **valid** : Lot OK, aucune modification
                - 🟠 **warning** : Corrections automatiques appliquées (lot importable)
                - 🔴 **error** : Erreurs bloquantes (lot rejeté)
                """)
                
                st.markdown("---")
                
                # ===== ÉTAPE 4 : Import =====
                if report['errors'] == 0:
                    st.success(f"✅ **Tous les lots sont valides !** ({report['valid'] + report['warnings']} lots importables)")
                    
                    if report['warnings'] > 0:
                        st.warning(f"⚠️ {report['warnings']} lot(s) avec corrections automatiques. Vérifiez avant import.")
                    
                    if st.button("✅ CONFIRMER IMPORT", type="primary", use_container_width=True, key="btn_import"):
                        with st.spinner("⏳ Import en cours..."):
                            success, message = import_validated_lots(df_val)
                            
                            if success:
                                st.success(message)
                                st.balloons()
                                time.sleep(2)
                                
                                # Nettoyer session
                                st.session_state.pop('df_validated', None)
                                st.session_state.pop('import_report', None)
                                
                                st.rerun()
                            else:
                                st.error(message)
                else:
                    st.error(f"❌ **{report['errors']} lot(s) avec erreurs bloquantes**")
                    st.info("💡 **Action requise** : Corrigez les erreurs dans votre fichier Excel, puis réuploadez.")
                    
                    # Afficher détails erreurs
                    with st.expander("📝 Détails des Erreurs", expanded=True):
                        df_errors = df_val[df_val['_status'] == 'error'][['code_lot_interne', '_errors']]
                        df_errors = df_errors.rename(columns={
                            'code_lot_interne': 'Code Lot',
                            '_errors': 'Erreurs'
                        })
                        st.dataframe(df_errors, use_container_width=True, hide_index=True)
        
        except Exception as e:
            st.error(f"❌ Erreur lecture fichier : {str(e)}")
            st.info("💡 Vérifiez que votre fichier contient bien un onglet 'Lots' avec les colonnes du template")
    
    else:
        st.info("👆 Uploadez votre fichier Excel pour commencer la validation")

# ============================================================================
# FOOTER
# ============================================================================

show_footer()
