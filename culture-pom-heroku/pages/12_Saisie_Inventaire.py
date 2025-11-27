"""
Page 12 - Saisie Inventaire (Compteur)
Accès : COMPTEUR uniquement
Interface : Table scrollable + sauvegarde globale (compatible offline)

CONCEPT :
1. Charger toutes les lignes en session_state (1 appel réseau)
2. Saisie dans table scrollable (PAS de reload)
3. Données restent en mémoire navigateur
4. UN bouton "Sauvegarder tout" quand réseau OK
"""

import streamlit as st
import pandas as pd
from datetime import datetime
from database import get_connection
from components import show_footer
from auth import is_authenticated, is_compteur
import time

st.set_page_config(page_title="Saisie Inventaire - Culture Pom", page_icon="📱", layout="wide")

# CSS mobile-friendly
st.markdown("""
<style>
    .block-container { 
        padding-top: 1rem !important; 
        padding-bottom: 0.5rem !important;
        padding-left: 1rem !important;
        padding-right: 1rem !important;
    }
    h1, h2, h3, h4 { margin-top: 0.2rem !important; margin-bottom: 0.2rem !important; }
    
    /* Table plus grande sur mobile */
    .stDataFrame { font-size: 14px !important; }
    
    /* Bouton sticky en bas */
    .save-button-container {
        position: sticky;
        bottom: 0;
        background: white;
        padding: 1rem;
        border-top: 2px solid #ddd;
        z-index: 100;
    }
    
    /* Highlight lignes modifiées */
    .modified-row { background-color: #fff3cd !important; }
</style>
""", unsafe_allow_html=True)

# ============================================================
# SÉCURITÉ
# ============================================================

if not is_authenticated():
    st.warning("⚠️ Veuillez vous connecter")
    st.stop()

# Page réservée aux COMPTEUR (ou tous si pas de fonction is_compteur)
try:
    if not is_compteur():
        st.error("❌ Cette page est réservée aux compteurs")
        st.info("👉 Managers : utilisez la page **11 - Inventaire**")
        st.stop()
except:
    pass  # Si is_compteur n'existe pas, continuer

st.title("📱 Saisie Inventaire")
st.markdown("---")

# ============================================================
# FONCTIONS
# ============================================================

def get_inventaires_en_cours():
    """Récupère inventaires EN_COURS pour sélection"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, date_inventaire, site, compteur_1, compteur_2, nb_lignes
            FROM inventaires 
            WHERE type_inventaire = 'CONSOMMABLES' AND statut = 'EN_COURS'
            ORDER BY date_inventaire DESC
        """)
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        return rows if rows else []
    except:
        return []

def charger_lignes_inventaire(inventaire_id):
    """Charge TOUTES les lignes d'un inventaire en mémoire"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT 
                il.id as ligne_id,
                rc.code_consommable,
                rc.libelle,
                rc.unite_inventaire,
                il.site,
                il.atelier,
                il.stock_theorique,
                il.stock_compte,
                il.coefficient_conversion
            FROM inventaires_consommables_lignes il
            JOIN ref_consommables rc ON il.consommable_id = rc.id
            WHERE il.inventaire_id = %s
            ORDER BY rc.libelle
        """, (inventaire_id,))
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        
        if rows:
            df = pd.DataFrame(rows)
            # Convertir numériques
            for col in ['stock_theorique', 'stock_compte', 'coefficient_conversion']:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
            return df
        return pd.DataFrame()
    except Exception as e:
        st.error(f"❌ Erreur chargement : {e}")
        return pd.DataFrame()

def sauvegarder_comptages(inventaire_id, df_comptages):
    """
    Sauvegarde TOUS les comptages en UNE transaction
    df_comptages : DataFrame avec colonnes [ligne_id, stock_compte]
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        nb_maj = 0
        
        for _, row in df_comptages.iterrows():
            ligne_id = int(row['ligne_id'])
            stock_compte = row['stock_compte']
            stock_theorique = row['stock_theorique']
            
            # Ignorer si pas de valeur saisie
            if pd.isna(stock_compte):
                continue
            
            stock_compte = float(stock_compte)
            stock_theorique = float(stock_theorique) if pd.notna(stock_theorique) else 0
            
            # Calculer écart
            ecart = stock_compte - stock_theorique
            
            # Récupérer coefficient et prix pour écart_valeur
            cursor.execute("""
                SELECT il.coefficient_conversion, rc.prix_unitaire
                FROM inventaires_consommables_lignes il
                JOIN ref_consommables rc ON il.consommable_id = rc.id
                WHERE il.id = %s
            """, (ligne_id,))
            info = cursor.fetchone()
            
            coef = float(info['coefficient_conversion'] or 1) if info else 1
            prix = float(info['prix_unitaire'] or 0) if info else 0
            ecart_valeur = ecart * coef * prix
            
            # Mettre à jour ligne
            cursor.execute("""
                UPDATE inventaires_consommables_lignes
                SET stock_compte = %s, ecart = %s, ecart_valeur = %s, updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
            """, (stock_compte, ecart, ecart_valeur, ligne_id))
            
            nb_maj += 1
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return True, f"✅ {nb_maj} ligne(s) enregistrée(s)"
    except Exception as e:
        if 'conn' in locals():
            conn.rollback()
        return False, f"❌ Erreur : {str(e)}"

# ============================================================
# INTERFACE
# ============================================================

# Sélection inventaire
inventaires = get_inventaires_en_cours()

if not inventaires:
    st.warning("📭 Aucun inventaire en cours")
    st.info("👉 Demandez à un manager de créer un inventaire")
    show_footer()
    st.stop()

# Dropdown sélection
options = [f"#{inv['id']} - {inv['date_inventaire']} - {inv['site']} ({inv['nb_lignes']} réf.)" 
           for inv in inventaires]
selected = st.selectbox("📋 Sélectionner l'inventaire", options)
inv_id = int(selected.split('#')[1].split(' ')[0])

# Trouver info inventaire sélectionné
inv_info = next((inv for inv in inventaires if inv['id'] == inv_id), None)

if inv_info:
    st.info(f"👤 Compteur(s) : **{inv_info['compteur_1']}** {', ' + inv_info['compteur_2'] if inv_info['compteur_2'] else ''}")

st.markdown("---")

# ============================================================
# CHARGEMENT DONNÉES EN SESSION
# ============================================================

# Clé unique pour cet inventaire
session_key = f"inventaire_{inv_id}_data"
session_key_original = f"inventaire_{inv_id}_original"

# Bouton recharger
col1, col2 = st.columns([3, 1])
with col2:
    if st.button("🔄 Recharger", use_container_width=True):
        st.session_state.pop(session_key, None)
        st.session_state.pop(session_key_original, None)
        st.rerun()

# Charger données si pas en session
if session_key not in st.session_state:
    with st.spinner("⏳ Chargement des références..."):
        df = charger_lignes_inventaire(inv_id)
        if not df.empty:
            st.session_state[session_key] = df.copy()
            st.session_state[session_key_original] = df.copy()
            st.success(f"✅ {len(df)} références chargées")
        else:
            st.error("❌ Aucune donnée")
            st.stop()

# Récupérer données de session
df_data = st.session_state[session_key]

# ============================================================
# STATISTIQUES
# ============================================================

nb_total = len(df_data)
nb_comptees = df_data['stock_compte'].notna().sum()

col1, col2, col3 = st.columns(3)
with col1:
    st.metric("📦 Total références", nb_total)
with col2:
    st.metric("✅ Comptées", int(nb_comptees))
with col3:
    pct = (nb_comptees / nb_total * 100) if nb_total > 0 else 0
    st.metric("📊 Progression", f"{pct:.0f}%")

st.progress(nb_comptees / nb_total if nb_total > 0 else 0)

st.markdown("---")

# ============================================================
# TABLE ÉDITABLE (SCROLL INFINI)
# ============================================================

st.markdown("### 📝 Saisie des comptages")
st.caption("💡 Saisissez les quantités comptées puis cliquez sur **Enregistrer tout**")

# Préparer DataFrame pour édition
df_edit = df_data[['ligne_id', 'libelle', 'atelier', 'unite_inventaire', 'stock_theorique', 'stock_compte']].copy()
df_edit.columns = ['ID', 'Consommable', 'Atelier', 'Unité', 'Stock Théo', 'Stock Compté']

# Configuration colonnes
column_config = {
    "ID": None,  # Masqué
    "Consommable": st.column_config.TextColumn("Consommable", disabled=True, width="large"),
    "Atelier": st.column_config.TextColumn("Atelier", disabled=True, width="small"),
    "Unité": st.column_config.TextColumn("Unité", disabled=True, width="small"),
    "Stock Théo": st.column_config.NumberColumn("Théorique", disabled=True, format="%.0f"),
    "Stock Compté": st.column_config.NumberColumn("🎯 COMPTÉ", format="%.0f", required=False, min_value=0),
}

# ⭐ Table éditable avec scroll (PAS de reload entre lignes)
edited_df = st.data_editor(
    df_edit,
    column_config=column_config,
    use_container_width=True,
    hide_index=True,
    num_rows="fixed",
    height=500,  # Hauteur fixe avec scroll
    key=f"editor_{inv_id}"
)

# ============================================================
# MISE À JOUR SESSION STATE
# ============================================================

# Synchroniser éditions avec session_state
if edited_df is not None:
    # Mapper les modifications
    for idx, row in edited_df.iterrows():
        ligne_id = df_data.iloc[idx]['ligne_id']
        new_value = row['Stock Compté']
        
        # Mettre à jour session_state
        mask = st.session_state[session_key]['ligne_id'] == ligne_id
        st.session_state[session_key].loc[mask, 'stock_compte'] = new_value

# ============================================================
# BOUTON SAUVEGARDE GLOBAL
# ============================================================

st.markdown("---")

# Compter modifications non sauvegardées
df_current = st.session_state[session_key]
nb_modif = df_current['stock_compte'].notna().sum()

if nb_modif > 0:
    st.warning(f"💾 **{int(nb_modif)} ligne(s)** avec comptage à enregistrer")

col1, col2 = st.columns([2, 1])

with col1:
    if st.button("💾 ENREGISTRER TOUT", type="primary", use_container_width=True, 
                 disabled=(nb_modif == 0)):
        with st.spinner("⏳ Enregistrement en cours..."):
            # Préparer données pour sauvegarde
            df_save = st.session_state[session_key][['ligne_id', 'stock_theorique', 'stock_compte']].copy()
            
            success, msg = sauvegarder_comptages(inv_id, df_save)
            
            if success:
                st.success(msg)
                st.balloons()
                # Recharger pour avoir les données à jour
                time.sleep(1)
                st.session_state.pop(session_key, None)
                st.session_state.pop(session_key_original, None)
                st.rerun()
            else:
                st.error(msg)
                st.error("⚠️ Vérifiez votre connexion et réessayez")

with col2:
    if st.button("🔄 Annuler modif.", use_container_width=True):
        if session_key_original in st.session_state:
            st.session_state[session_key] = st.session_state[session_key_original].copy()
            st.rerun()

# ============================================================
# AIDE
# ============================================================

with st.expander("❓ Aide"):
    st.markdown("""
    ### Comment utiliser cette page
    
    1. **Sélectionnez l'inventaire** en haut de page
    2. **Scrollez** dans le tableau pour voir toutes les références
    3. **Saisissez** les quantités comptées dans la colonne "COMPTÉ"
    4. **Enregistrez** en cliquant sur le bouton vert quand vous avez terminé
    
    ### 💡 Astuces
    - Les données restent en mémoire même si vous perdez le réseau
    - Vous pouvez saisir plusieurs lignes avant d'enregistrer
    - Le bouton "Recharger" récupère les données du serveur
    - Le bouton "Annuler modif." restaure les valeurs initiales
    
    ### ⚠️ Important
    - N'actualisez PAS la page pendant la saisie (perte des données non enregistrées)
    - Enregistrez régulièrement si vous avez beaucoup de lignes
    """)

show_footer()
