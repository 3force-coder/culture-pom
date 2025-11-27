"""
Page 12 - Saisie Inventaire Consommables
VERSION MOBILE-FIRST - Optimisée pour compteurs terrain

CORRECTION: Utilise la table 'inventaires' (pas 'inventaires_consommables')
"""

import streamlit as st
import pandas as pd
from datetime import datetime
from database import get_connection
from auth import is_authenticated, is_admin

# Configuration page - DOIT être en premier
st.set_page_config(
    page_title="Saisie Inventaire",
    page_icon="📱",
    layout="centered",  # Centré = meilleur pour mobile
    initial_sidebar_state="collapsed"  # Sidebar fermée par défaut sur mobile
)

# CSS Mobile-First optimisé
st.markdown("""
<style>
    /* Réduire padding général */
    .block-container {
        padding-top: 1rem !important;
        padding-bottom: 1rem !important;
        padding-left: 0.5rem !important;
        padding-right: 0.5rem !important;
        max-width: 100% !important;
    }
    
    /* Carte consommable */
    .conso-card {
        background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%);
        border-radius: 12px;
        padding: 12px 16px;
        margin-bottom: 8px;
        border-left: 4px solid #4CAF50;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }
    
    .conso-card.modified {
        border-left-color: #ff9800;
        background: linear-gradient(135deg, #fff8e1 0%, #ffecb3 100%);
    }
    
    .conso-name {
        font-size: 1rem;
        font-weight: 600;
        color: #1a1a2e;
        margin-bottom: 4px;
        word-wrap: break-word;
        line-height: 1.3;
    }
    
    .conso-unit {
        font-size: 0.8rem;
        color: #666;
        margin-bottom: 8px;
    }
    
    /* Groupes atelier */
    .atelier-header {
        background: #2196F3;
        color: white;
        padding: 10px 16px;
        border-radius: 8px;
        margin: 16px 0 8px 0;
        font-weight: 600;
        font-size: 1rem;
    }
    
    /* Input number plus grand */
    .stNumberInput input {
        font-size: 1.2rem !important;
        font-weight: 600 !important;
        text-align: center !important;
        padding: 12px !important;
    }
    
    /* Masquer les flèches du number input sur mobile pour plus de place */
    @media (max-width: 768px) {
        .stNumberInput button {
            display: none !important;
        }
        .stNumberInput input {
            border-radius: 8px !important;
        }
    }
    
    /* Header compact */
    h1 {
        font-size: 1.5rem !important;
        margin-bottom: 0.5rem !important;
    }
    
    /* Compteur modifications */
    .modif-counter {
        background: #ff9800;
        color: white;
        padding: 8px 16px;
        border-radius: 20px;
        font-weight: 600;
        text-align: center;
        margin-bottom: 12px;
    }
    
    /* Success message */
    .success-banner {
        background: #4CAF50;
        color: white;
        padding: 12px;
        border-radius: 8px;
        text-align: center;
        margin-bottom: 12px;
    }
</style>
""", unsafe_allow_html=True)

# Vérification authentification
if not is_authenticated():
    st.warning("⚠️ Veuillez vous connecter")
    st.stop()

# Vérification accès : Compteurs OU Admins
def is_compteur():
    """Vérifie si l'utilisateur est un compteur"""
    return st.session_state.get('role') == 'COMPTEUR'

if not is_compteur() and not is_admin():
    st.error("🚫 Cette page est réservée aux compteurs")
    st.info("👉 Managers : utilisez la page 11 - Inventaire")
    st.stop()

# ============================================
# FONCTIONS - CORRIGÉES pour table 'inventaires'
# ============================================

def get_inventaires_en_cours():
    """Récupère les inventaires EN_COURS depuis la table 'inventaires'"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # ✅ CORRIGÉ: Utilise la table 'inventaires' (pas 'inventaires_consommables')
        cursor.execute("""
            SELECT 
                i.id, 
                i.site, 
                i.date_inventaire, 
                i.mois, 
                i.annee,
                i.nb_lignes,
                (SELECT COUNT(*) FROM inventaires_consommables_lignes WHERE inventaire_id = i.id) as nb_refs
            FROM inventaires i
            WHERE i.statut = 'EN_COURS'
            ORDER BY i.created_at DESC
        """)
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        return rows if rows else []
    except Exception as e:
        st.error(f"Erreur : {e}")
        return []

def get_lignes_inventaire(inventaire_id):
    """Récupère les lignes d'un inventaire avec infos consommable"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT 
                icl.id,
                icl.consommable_id,
                icl.site,
                icl.atelier,
                icl.stock_theorique,
                icl.stock_compte,
                rc.libelle as nom,
                rc.unite_inventaire as unite
            FROM inventaires_consommables_lignes icl
            JOIN ref_consommables rc ON icl.consommable_id = rc.id
            WHERE icl.inventaire_id = %s
            ORDER BY icl.atelier, rc.libelle
        """, (inventaire_id,))
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        
        if rows:
            df = pd.DataFrame(rows)
            return df
        return pd.DataFrame()
    except Exception as e:
        st.error(f"Erreur : {e}")
        return pd.DataFrame()

def sauvegarder_comptages(inventaire_id, comptages):
    """Sauvegarde tous les comptages en une transaction"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        updated = 0
        for ligne_id, stock_compte in comptages.items():
            if stock_compte is not None:
                cursor.execute("""
                    UPDATE inventaires_consommables_lignes
                    SET stock_compte = %s,
                        ecart = %s - stock_theorique,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                """, (int(stock_compte), int(stock_compte), int(ligne_id)))
                updated += 1
        
        # Mettre à jour le compteur nb_lignes dans inventaires
        cursor.execute("""
            UPDATE inventaires
            SET nb_lignes = (
                SELECT COUNT(*) FROM inventaires_consommables_lignes 
                WHERE inventaire_id = %s AND stock_compte IS NOT NULL
            )
            WHERE id = %s
        """, (inventaire_id, inventaire_id))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return True, f"✅ {updated} ligne(s) enregistrée(s)"
    except Exception as e:
        return False, f"❌ Erreur : {e}"

# ============================================
# INTERFACE MOBILE
# ============================================

st.title("📱 Saisie Inventaire")

# Sélection inventaire
inventaires = get_inventaires_en_cours()

if not inventaires:
    st.warning("📋 Aucun inventaire en cours")
    st.info("Demandez à un manager de créer un inventaire")
    st.stop()

# Dropdown sélection inventaire
inv_options = {}
for inv in inventaires:
    nb = inv['nb_refs'] if inv['nb_refs'] else inv['nb_lignes'] if inv['nb_lignes'] else 0
    label = f"{inv['site']} - {inv['mois']}/{inv['annee']} ({nb} réf.)"
    inv_options[label] = inv['id']

selected_inv_label = st.selectbox(
    "📍 Sélectionner l'inventaire",
    options=list(inv_options.keys()),
    key="select_inv"
)

inventaire_id = inv_options[selected_inv_label]

# Charger les lignes
df_lignes = get_lignes_inventaire(inventaire_id)

if df_lignes.empty:
    st.warning("Aucune ligne dans cet inventaire")
    st.info("L'inventaire a été créé mais aucune référence n'a été chargée.")
    st.stop()

# Initialiser session state pour les comptages
if 'comptages' not in st.session_state:
    st.session_state.comptages = {}
if 'inventaire_id_loaded' not in st.session_state or st.session_state.inventaire_id_loaded != inventaire_id:
    # Charger les comptages existants
    st.session_state.comptages = {}
    for _, row in df_lignes.iterrows():
        if pd.notna(row['stock_compte']):
            st.session_state.comptages[row['id']] = int(row['stock_compte'])
    st.session_state.inventaire_id_loaded = inventaire_id

# Info inventaire
site_name = selected_inv_label.split(" - ")[0]
st.markdown(f"**{len(df_lignes)} références** à compter sur **{site_name}**")

st.markdown("---")

# Grouper par atelier
ateliers = df_lignes['atelier'].fillna('SANS ATELIER').unique()

# Formulaire de saisie par cartes
for atelier in sorted(ateliers):
    df_atelier = df_lignes[df_lignes['atelier'].fillna('SANS ATELIER') == atelier]
    
    # Header atelier
    st.markdown(f"""
    <div class="atelier-header">
        📦 {atelier} ({len(df_atelier)} réf.)
    </div>
    """, unsafe_allow_html=True)
    
    # Cartes consommables
    for idx, row in df_atelier.iterrows():
        ligne_id = row['id']
        nom = row['nom']
        unite = row['unite'] if pd.notna(row['unite']) else "Unité"
        
        # Valeur actuelle (du session_state ou de la base)
        current_value = st.session_state.comptages.get(ligne_id)
        if current_value is None and pd.notna(row['stock_compte']):
            current_value = int(row['stock_compte'])
        
        # Carte avec input
        col1, col2 = st.columns([3, 2])
        
        with col1:
            st.markdown(f"""
            <div style="padding: 8px 0;">
                <div class="conso-name">{nom}</div>
                <div class="conso-unit">📦 {unite}</div>
            </div>
            """, unsafe_allow_html=True)
        
        with col2:
            # Number input avec clavier numérique
            new_value = st.number_input(
                "Compté",
                min_value=0,
                max_value=99999,
                value=current_value if current_value is not None else 0,
                step=1,
                key=f"input_{ligne_id}",
                label_visibility="collapsed"
            )
            
            # Enregistrer la modification
            if new_value != current_value:
                st.session_state.comptages[ligne_id] = new_value
        
        # Séparateur léger
        st.markdown("<hr style='margin: 4px 0; border: none; border-top: 1px solid #eee;'>", 
                    unsafe_allow_html=True)

# Espace pour le bouton sticky
st.markdown("<div style='height: 80px;'></div>", unsafe_allow_html=True)

# Bouton sauvegarde (sticky en bas)
st.markdown("---")

col1, col2 = st.columns([1, 2])

with col1:
    nb_saisis = len([v for v in st.session_state.comptages.values() if v is not None and v > 0])
    st.metric("Saisis", f"{nb_saisis}/{len(df_lignes)}")

with col2:
    if st.button("💾 ENREGISTRER TOUT", type="primary", use_container_width=True):
        if st.session_state.comptages:
            success, message = sauvegarder_comptages(inventaire_id, st.session_state.comptages)
            if success:
                st.success(message)
                st.balloons()
            else:
                st.error(message)
        else:
            st.warning("Aucun comptage à enregistrer")

# Note pour admin
if is_admin():
    st.markdown("---")
    st.info("👤 Mode Admin : vous voyez cette page pour test/debug")
