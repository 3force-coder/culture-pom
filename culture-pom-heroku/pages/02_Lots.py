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
# FONCTIONS DATA - CHARGEMENT LOTS
# ============================================================================

def load_stock_data():
    """Charge les données des lots (SANS colonnes emplacement)"""
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
                l.poids_total_brut_kg,
                l.calibre_min,
                l.calibre_max,
                l.prix_achat_euro_tonne,
                l.tare_achat_pct,
                l.valeur_lot_euro,
                l.date_entree_stock,
                l.statut,
                COALESCE((CURRENT_DATE - l.date_entree_stock::DATE), 0) as age_jours,
                l.notes
            FROM lots_bruts l
            LEFT JOIN ref_varietes v ON l.code_variete = v.code_variete
            LEFT JOIN ref_producteurs p ON l.code_producteur = p.code_producteur
            WHERE l.is_active = TRUE
            ORDER BY l.date_entree_stock DESC, l.code_lot_interne
        """
        
        cursor.execute(query)
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        
        if rows:
            df = pd.DataFrame(rows)
            
            # Conversion types
            numeric_cols = ['poids_total_brut_kg', 'calibre_min', 'calibre_max',
                          'prix_achat_euro_tonne', 'tare_achat_pct', 'valeur_lot_euro', 'age_jours']
            for col in numeric_cols:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
            
            # Format dates
            if 'date_entree_stock' in df.columns:
                df['date_entree_stock'] = pd.to_datetime(df['date_entree_stock']).dt.date
            
            return df
        
        return pd.DataFrame()
    except Exception as e:
        st.error(f"❌ Erreur chargement données : {str(e)}")
        return pd.DataFrame()

# ============================================================================
# FONCTIONS DATA - AJOUT LOT
# ============================================================================

def add_lot(data, varietes_dict, producteurs_dict):
    """Ajoute un nouveau lot (SANS créer d'emplacement)"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Convertir nom_variete → code_variete
        code_variete = varietes_dict.get(data.get('nom_variete'))
        if not code_variete:
            return False, "❌ Variété invalide"
        
        # Convertir nom_producteur → code_producteur
        code_producteur = producteurs_dict.get(data.get('nom_producteur'))
        if not code_producteur:
            return False, "❌ Producteur invalide"
        
        # Vérifier unicité code_lot_interne
        cursor.execute("SELECT COUNT(*) as nb FROM lots_bruts WHERE code_lot_interne = %s", 
                      (data['code_lot_interne'],))
        if cursor.fetchone()['nb'] > 0:
            cursor.close()
            conn.close()
            return False, "❌ Ce code lot existe déjà"
        
        # Calculer poids_total_brut_kg
        poids_total_brut = float(data.get('poids_total_brut_kg', 0))
        
        # Calculer valeur_lot_euro
        prix_tonne = float(data.get('prix_achat_euro_tonne', 0))
        tare_pct = float(data.get('tare_achat_pct', 0))
        
        poids_net_kg = poids_total_brut * (1 - tare_pct / 100)
        valeur_lot = (poids_net_kg / 1000) * prix_tonne
        
        # INSERT
        query = """
            INSERT INTO lots_bruts (
                code_lot_interne, nom_usage, code_variete, code_producteur,
                poids_total_brut_kg, calibre_min, calibre_max,
                prix_achat_euro_tonne, tare_achat_pct, valeur_lot_euro,
                date_entree_stock, statut, notes, is_active, created_at, updated_at
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, TRUE, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            )
        """
        
        cursor.execute(query, (
            data['code_lot_interne'],
            data['nom_usage'],
            code_variete,
            code_producteur,
            poids_total_brut,
            data.get('calibre_min'),
            data.get('calibre_max'),
            prix_tonne,
            tare_pct,
            valeur_lot,
            data['date_entree_stock'],
            data.get('statut', 'EN_STOCK'),
            data.get('notes')
        ))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return True, "✅ Lot créé avec succès ! Allez dans Détails Stock pour ajouter les emplacements."
    
    except Exception as e:
        if conn:
            conn.rollback()
            conn.close()
        return False, f"❌ Erreur : {str(e)}"

# ============================================================================
# FONCTIONS DATA - SAUVEGARDE MODIFICATIONS
# ============================================================================

def save_lot_changes(edited_df, varietes_dict, producteurs_dict):
    """Sauvegarde les modifications du tableau"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        success_count = 0
        
        for _, row in edited_df.iterrows():
            lot_id = int(row['id'])
            
            # Convertir nom_variete → code_variete
            code_variete = varietes_dict.get(row.get('nom_variete'))
            code_producteur = producteurs_dict.get(row.get('nom_producteur'))
            
            if not code_variete or not code_producteur:
                continue
            
            # Recalculer valeur_lot_euro
            poids_total_brut = float(row.get('poids_total_brut_kg', 0))
            prix_tonne = float(row.get('prix_achat_euro_tonne', 0))
            tare_pct = float(row.get('tare_achat_pct', 0))
            
            poids_net_kg = poids_total_brut * (1 - tare_pct / 100)
            valeur_lot = (poids_net_kg / 1000) * prix_tonne
            
            # UPDATE
            query = """
                UPDATE lots_bruts SET
                    nom_usage = %s,
                    code_variete = %s,
                    code_producteur = %s,
                    poids_total_brut_kg = %s,
                    calibre_min = %s,
                    calibre_max = %s,
                    prix_achat_euro_tonne = %s,
                    tare_achat_pct = %s,
                    valeur_lot_euro = %s,
                    statut = %s,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
            """
            
            cursor.execute(query, (
                row['nom_usage'],
                code_variete,
                code_producteur,
                poids_total_brut,
                row.get('calibre_min'),
                row.get('calibre_max'),
                prix_tonne,
                tare_pct,
                valeur_lot,
                row.get('statut'),
                lot_id
            ))
            
            success_count += 1
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return True, f"✅ {success_count} lot(s) modifié(s)"
    
    except Exception as e:
        if conn:
            conn.rollback()
            conn.close()
        return False, f"❌ Erreur : {str(e)}"

# ============================================================================
# FONCTIONS DATA - SUPPRESSION
# ============================================================================

def delete_lot(lot_id):
    """Supprime un lot (soft delete)"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute("UPDATE lots_bruts SET is_active = FALSE WHERE id = %s", (lot_id,))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return True, "✅ Lot supprimé"
    
    except Exception as e:
        if conn:
            conn.rollback()
            conn.close()
        return False, f"❌ Erreur : {str(e)}"

# ============================================================================
# CHARGEMENT DONNÉES
# ============================================================================

df = load_stock_data()

# Charger dropdowns
varietes_dict = get_all_varietes_for_dropdown()
producteurs_dict = get_all_producteurs_for_dropdown()

# ============================================================================
# KPIS
# ============================================================================

if not df.empty:
    st.subheader("📊 Indicateurs Clés")
    
    col1, col2, col3, col4, col5 = st.columns(5)
    
    with col1:
        st.metric("📦 Lots actifs", len(df))
    
    with col2:
        tonnage = df['poids_total_brut_kg'].sum() / 1000
        st.metric("⚖️ Tonnage total", f"{tonnage:,.1f} t")
    
    with col3:
        nb_varietes = df['nom_variete'].nunique()
        st.metric("🌱 Variétés", nb_varietes)
    
    with col4:
        nb_producteurs = df['nom_producteur'].nunique()
        st.metric("👤 Producteurs", nb_producteurs)
    
    with col5:
        age_moyen = df['age_jours'].mean()
        st.metric("📅 Âge moyen", f"{int(age_moyen)} j")
    
    st.markdown("---")

# ============================================================================
# FILTRES
# ============================================================================

if not df.empty:
    st.subheader("🔎 Filtres")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        search_nom = st.text_input("Nom usage", key="filter_nom")
    
    with col2:
        varietes_list = ["Toutes"] + sorted(df['nom_variete'].dropna().unique().tolist())
        filter_variete = st.selectbox("Variété", varietes_list, key="filter_variete")
    
    with col3:
        producteurs_list = ["Tous"] + sorted(df['nom_producteur'].dropna().unique().tolist())
        filter_producteur = st.selectbox("Producteur", producteurs_list, key="filter_producteur")
    
    with col4:
        statuts_list = ["Tous"] + sorted(df['statut'].dropna().unique().tolist())
        filter_statut = st.selectbox("Statut", statuts_list, key="filter_statut")
    
    # Appliquer filtres
    filtered_df = df.copy()
    
    if search_nom:
        filtered_df = filtered_df[filtered_df['nom_usage'].str.contains(search_nom, case=False, na=False)]
    
    if filter_variete != "Toutes":
        filtered_df = filtered_df[filtered_df['nom_variete'] == filter_variete]
    
    if filter_producteur != "Tous":
        filtered_df = filtered_df[filtered_df['nom_producteur'] == filter_producteur]
    
    if filter_statut != "Tous":
        filtered_df = filtered_df[filtered_df['statut'] == filter_statut]
    
    st.info(f"📋 {len(filtered_df)} lot(s) affiché(s) sur {len(df)} total")
    
    st.markdown("---")

# ============================================================================
# BOUTONS ACTIONS
# ============================================================================

col1, col2, col3 = st.columns(3)

with col1:
    if st.button("➕ Ajouter un Lot", use_container_width=True, type="primary"):
        st.session_state.show_add_form = True

with col2:
    if st.button("🔄 Actualiser", use_container_width=True):
        st.session_state.pop('original_stock_df', None)
        st.rerun()

with col3:
    if st.button("📦 Voir Détails Stock", use_container_width=True):
        st.switch_page("pages/03_Détails stock.py")

st.markdown("---")

# ============================================================================
# FORMULAIRE AJOUT LOT
# ============================================================================

if st.session_state.get('show_add_form', False):
    st.subheader("➕ Ajouter un Nouveau Lot")
    
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
            key="add_nom_usage"
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
        
        # Date entrée - AUTO
        st.session_state.new_lot_data['date_entree_stock'] = datetime.now().date()
        st.text_input(
            "Date Entrée Stock (auto)",
            value=datetime.now().strftime("%d/%m/%Y"),
            disabled=True,
            key="add_date_entree_display"
        )
    
    with col2:
        # Type conditionnement avec poids auto
        type_cond_options = ["", "Pallox", "Petit Pallox", "Big Bag"]
        type_cond = st.selectbox(
            "Type Conditionnement *",
            options=type_cond_options,
            key="add_type_cond"
        )
        
        # Poids unitaire selon type (affichage info)
        poids_unitaire_map = {
            "Pallox": 1900,
            "Petit Pallox": 1200,
            "Big Bag": 1600
        }
        
        poids_unitaire = poids_unitaire_map.get(type_cond, 0)
        
        if type_cond:
            st.info(f"💡 Poids unitaire : {poids_unitaire} kg")
        
        # Nombre unités
        nombre_unites = st.number_input(
            "Nombre d'Unités *",
            min_value=1,
            value=1,
            step=1,
            key="add_nombre_unites"
        )
        
        # Calcul poids total AUTO
        poids_total_brut = nombre_unites * poids_unitaire
        st.session_state.new_lot_data['poids_total_brut_kg'] = poids_total_brut
        
        st.metric("📦 Poids Total Brut", f"{poids_total_brut:,} kg")
        
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
            value=0,
            step=5,
            key="add_calibre_max"
        )
        
        # Prix achat
        st.session_state.new_lot_data['prix_achat_euro_tonne'] = st.number_input(
            "Prix Achat (€/tonne)",
            min_value=0.0,
            value=0.0,
            step=10.0,
            key="add_prix_achat"
        )
        
        # Tare achat
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
    
    # Notes
    st.session_state.new_lot_data['notes'] = st.text_area(
        "Notes",
        key="add_notes"
    )
    
    # Boutons
    st.markdown("---")
    
    col1, col2 = st.columns([1, 1])
    
    with col1:
        if st.button("💾 Enregistrer", use_container_width=True, type="primary", key="btn_save_lot"):
            # Validation
            missing_fields = []
            
            if not st.session_state.new_lot_data.get('code_lot_interne'):
                missing_fields.append("Code Lot Interne")
            if not st.session_state.new_lot_data.get('nom_usage'):
                missing_fields.append("Nom Usage")
            if not st.session_state.new_lot_data.get('nom_variete'):
                missing_fields.append("Variété")
            if not st.session_state.new_lot_data.get('nom_producteur'):
                missing_fields.append("Producteur")
            if not type_cond:
                missing_fields.append("Type Conditionnement")
            if poids_total_brut == 0:
                missing_fields.append("Poids Total (vérifiez Type Conditionnement et Nombre Unités)")
            
            if missing_fields:
                st.error(f"❌ Champs obligatoires manquants : {', '.join(missing_fields)}")
            else:
                success, message = add_lot(st.session_state.new_lot_data, varietes_dict, producteurs_dict)
                
                if success:
                    st.success(message)
                    show_confetti_animation()
                    time.sleep(2)
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
# TABLEAU ÉDITABLE
# ============================================================================

if not df.empty and not st.session_state.get('show_add_form', False):
    st.subheader("📋 Liste des Lots")
    
    # Préparer affichage
    df_display = filtered_df.copy()
    
    # Colonnes éditables
    editable_cols = ['nom_usage', 'nom_variete', 'nom_producteur', 'poids_total_brut_kg',
                    'calibre_min', 'calibre_max', 'prix_achat_euro_tonne', 'tare_achat_pct', 'statut']
    
    # Colonnes display
    display_cols = ['id', 'code_lot_interne', 'nom_usage', 'nom_variete', 'nom_producteur',
                   'poids_total_brut_kg', 'calibre_min', 'calibre_max', 
                   'prix_achat_euro_tonne', 'tare_achat_pct', 'valeur_lot_euro', 
                   'date_entree_stock', 'statut', 'age_jours']
    
    df_display = df_display[display_cols]
    
    # Sauvegarder original
    if 'original_stock_df' not in st.session_state:
        st.session_state.original_stock_df = df_display.copy()
    
    # Data editor
    edited_df = st.data_editor(
        df_display,
        use_container_width=True,
        hide_index=True,
        disabled=['id', 'code_lot_interne', 'valeur_lot_euro', 'date_entree_stock', 'age_jours'],
        column_config={
            'id': st.column_config.NumberColumn('ID', width='small'),
            'code_lot_interne': st.column_config.TextColumn('Code Lot', width='medium'),
            'nom_usage': st.column_config.TextColumn('Nom', width='medium'),
            'nom_variete': st.column_config.SelectboxColumn('Variété', options=list(varietes_dict.keys())),
            'nom_producteur': st.column_config.SelectboxColumn('Producteur', options=list(producteurs_dict.keys())),
            'poids_total_brut_kg': st.column_config.NumberColumn('Poids (kg)', format='%d kg'),
            'calibre_min': st.column_config.NumberColumn('Cal Min', width='small'),
            'calibre_max': st.column_config.NumberColumn('Cal Max', width='small'),
            'prix_achat_euro_tonne': st.column_config.NumberColumn('Prix (€/t)', format='%.0f €'),
            'tare_achat_pct': st.column_config.NumberColumn('Tare (%)', format='%.1f%%'),
            'valeur_lot_euro': st.column_config.NumberColumn('Valeur (€)', format='%.2f €'),
            'date_entree_stock': st.column_config.DateColumn('Date Entrée', format='DD/MM/YYYY'),
            'statut': st.column_config.SelectboxColumn('Statut', options=['EN_STOCK', 'RESERVE', 'VENDU', 'DECHET']),
            'age_jours': st.column_config.NumberColumn('Âge (j)', width='small')
        },
        key="data_editor_lots"
    )
    
    # Détecter changements
    changes_detected = False
    try:
        if 'original_stock_df' in st.session_state:
            if len(st.session_state.original_stock_df) != len(edited_df):
                changes_detected = False
            else:
                for col in editable_cols:
                    if col in st.session_state.original_stock_df.columns and col in edited_df.columns:
                        orig_vals = st.session_state.original_stock_df[col].fillna('')
                        edit_vals = edited_df[col].fillna('')
                        
                        if not orig_vals.equals(edit_vals):
                            changes_detected = True
                            break
    except Exception as e:
        pass
    
    # Alerte modifications
    if changes_detected:
        st.markdown("""
        <div style="
            position: fixed;
            top: 60px;
            left: 0;
            right: 0;
            background: linear-gradient(90deg, #ff4b4b 0%, #ff6b6b 100%);
            color: white;
            padding: 15px 20px;
            text-align: center;
            font-weight: bold;
            font-size: 16px;
            z-index: 999999;
            box-shadow: 0 4px 15px rgba(0,0,0,0.4);
            border-bottom: 4px solid #cc0000;
        ">
            🚫 MODIFICATIONS NON SAUVEGARDÉES ! 
            Cliquez sur 💾 Enregistrer avant de quitter.
        </div>
        """, unsafe_allow_html=True)
    
    # Bouton enregistrer
    if st.button("💾 Enregistrer les Modifications", use_container_width=True, type="primary"):
        success, message = save_lot_changes(edited_df, varietes_dict, producteurs_dict)
        
        if success:
            st.success(message)
            st.session_state.pop('original_stock_df', None)
            time.sleep(1)
            st.rerun()
        else:
            st.error(message)
    
    st.markdown("---")
    
    # Alertes
    st.subheader("⚠️ Alertes")
    col1, col2 = st.columns(2)
    
    with col1:
        old_lots = df[df['age_jours'] > 90]
        if not old_lots.empty:
            st.warning(f"⚠️ {len(old_lots)} lot(s) >90 jours")
        else:
            st.success("✅ Aucun lot ancien")
    
    with col2:
        no_variety = df[df['nom_variete'].isna() | (df['nom_variete'] == '')]
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
        st.download_button("📥 CSV", csv, f"lots_{datetime.now().strftime('%Y%m%d')}.csv", "text/csv", use_container_width=True)
    
    with col2:
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            filtered_df.to_excel(writer, index=False, sheet_name='Lots')
        st.download_button("📥 Excel", buffer.getvalue(), f"lots_{datetime.now().strftime('%Y%m%d')}.xlsx", 
                          "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)
    
    # Suppression (Admin)
    if is_admin():
        st.markdown("---")
        st.subheader("🗑️ Suppression de Lots")
        
        lot_options = [f"{row['id']} - {row['code_lot_interne']} - {row['nom_usage']}" for _, row in df.iterrows()]
        
        if lot_options:
            selected_lot = st.selectbox("Sélectionner un lot à supprimer", options=lot_options, key="delete_lot_selector")
            
            selected_lot_id = int(selected_lot.split(" - ")[0])
            
            col1, col2 = st.columns([1, 5])
            with col1:
                if st.button("🗑️ Supprimer", use_container_width=True, type="secondary", key="btn_delete_lot"):
                    st.session_state.confirm_delete_lot_id = selected_lot_id
                    st.session_state.confirm_delete_lot_name = selected_lot
            
            if st.session_state.get('confirm_delete_lot_id'):
                st.warning(f"⚠️ **ATTENTION** : Supprimer le lot :\n\n**{st.session_state.confirm_delete_lot_name}**")
                
                col_confirm1, col_confirm2, col_confirm3 = st.columns([1, 1, 4])
                
                with col_confirm1:
                    if st.button("✅ CONFIRMER", use_container_width=True, type="primary", key="btn_confirm_delete"):
                        success, message = delete_lot(st.session_state.confirm_delete_lot_id)
                        
                        if success:
                            st.success(message)
                            st.session_state.pop('confirm_delete_lot_id', None)
                            st.session_state.pop('confirm_delete_lot_name', None)
                            time.sleep(1)
                            st.rerun()
                        else:
                            st.error(message)
                
                with col_confirm2:
                    if st.button("❌ ANNULER", use_container_width=True, key="btn_cancel_delete"):
                        st.session_state.pop('confirm_delete_lot_id', None)
                        st.session_state.pop('confirm_delete_lot_name', None)
                        st.rerun()
    else:
        st.markdown("---")
        st.info("🔒 Suppression réservée aux administrateurs")

else:
    st.warning("⚠️ Aucun lot trouvé")

show_footer()
