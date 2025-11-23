import streamlit as st
import pandas as pd
from datetime import datetime
from database import get_connection
from components import show_footer
from auth import is_authenticated, is_admin
import streamlit.components.v1 as components

st.set_page_config(page_title="Emplacements - Culture Pom", page_icon="📦", layout="wide")

# CSS espacements réduits
st.markdown("""
<style>
    .block-container {
        padding-top: 2rem !important;
        padding-bottom: 0.5rem !important;
    }
    h1, h2, h3, h4 {
        margin-top: 0.3rem !important;
        margin-bottom: 0.3rem !important;
    }
    .stSelectbox, .stButton, .stCheckbox {
        margin-bottom: 0.3rem !important;
        margin-top: 0.3rem !important;
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
            if st.button("🚪 Déconnexion", use_container_width=True, key="btn_logout_sidebar"):
                for key in list(st.session_state.keys()):
                    del st.session_state[key]
                st.rerun()

show_user_info()

# ============================================================================
# FONCTIONS
# ============================================================================

def get_lot_info(lot_id):
    """Récupère les informations complètes d'un lot"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        query = """
        SELECT 
            l.id,
            l.code_lot_interne,
            l.nom_usage,
            v.nom_variete,
            p.nom as nom_producteur,
            l.date_entree_stock,
            l.nombre_unites,
            l.poids_total_brut_kg,
            l.valeur_lot_euro,
            s.libelle as statut_libelle,
            s.couleur_hexa as statut_couleur,
            s.icone_emoji as statut_icone,
            EXTRACT(DAY FROM (CURRENT_DATE - l.date_entree_stock)) as age_jours
        FROM lots_bruts l
        LEFT JOIN ref_varietes v ON l.code_variete = v.code_variete
        LEFT JOIN ref_producteurs p ON l.code_producteur = p.code_producteur
        LEFT JOIN ref_statuts s ON l.statut_id = s.id
        WHERE l.id = %s
        """
        
        cursor.execute(query, (lot_id,))
        result = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if result:
            return {
                'id': result['id'],
                'code_lot_interne': result['code_lot_interne'],
                'nom_usage': result['nom_usage'],
                'nom_variete': result['nom_variete'],
                'nom_producteur': result['nom_producteur'],
                'date_entree_stock': result['date_entree_stock'],
                'nombre_unites': result['nombre_unites'],
                'poids_total_brut_kg': result['poids_total_brut_kg'],
                'valeur_lot_euro': result['valeur_lot_euro'],
                'statut_libelle': result['statut_libelle'],
                'statut_couleur': result['statut_couleur'],
                'statut_icone': result['statut_icone'],
                'age_jours': int(result['age_jours']) if result['age_jours'] else 0
            }
        return None
    except Exception as e:
        st.error(f"❌ Erreur chargement lot : {str(e)}")
        return None

def get_lot_emplacements(lot_id):
    """Récupère tous les emplacements d'un lot"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        query = """
        SELECT 
            id,
            site_stockage,
            emplacement_stockage,
            nombre_unites,
            poids_total_kg,
            type_stock,
            is_active,
            created_at,
            updated_at
        FROM stock_emplacements
        WHERE lot_id = %s AND is_active = TRUE
        ORDER BY created_at DESC
        """
        
        cursor.execute(query, (lot_id,))
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        
        if rows:
            df = pd.DataFrame(rows, columns=[
                'id', 'site_stockage', 'emplacement_stockage', 
                'nombre_unites', 'poids_total_kg', 'type_stock',
                'is_active', 'created_at', 'updated_at'
            ])
            return df
        return pd.DataFrame()
    except Exception as e:
        st.error(f"❌ Erreur chargement emplacements : {str(e)}")
        return pd.DataFrame()

def get_lot_mouvements(lot_id, limit=10):
    """Récupère les derniers mouvements d'un lot"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        query = """
        SELECT 
            type_mouvement,
            site_avant,
            site_apres,
            quantite_mouvement,
            description,
            created_at,
            created_by
        FROM stock_mouvements
        WHERE lot_id = %s
        ORDER BY created_at DESC
        LIMIT %s
        """
        
        cursor.execute(query, (lot_id, limit))
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        
        if rows:
            df = pd.DataFrame(rows, columns=[
                'type_mouvement', 'site_avant', 'site_apres',
                'quantite_mouvement', 'description', 'created_at', 'created_by'
            ])
            return df
        return pd.DataFrame()
    except Exception as e:
        st.error(f"❌ Erreur chargement mouvements : {str(e)}")
        return pd.DataFrame()

# ============================================================================
# INTERFACE
# ============================================================================

# Récupérer lot_id depuis query params
query_params = st.query_params
lot_id = query_params.get("lot_id")

if not lot_id:
    st.error("❌ Aucun lot sélectionné")
    if st.button("← Retour à la liste des lots"):
        st.switch_page("pages/02_Stock.py")
    st.stop()

# Convertir en entier
try:
    lot_id = int(lot_id)
except:
    st.error("❌ ID de lot invalide")
    st.stop()

# Charger infos lot
lot_info = get_lot_info(lot_id)

if not lot_info:
    st.error("❌ Lot introuvable")
    if st.button("← Retour à la liste des lots"):
        st.switch_page("pages/02_Stock.py")
    st.stop()

# ============================================================================
# TITRE & NAVIGATION
# ============================================================================

col_title, col_back = st.columns([4, 1])

with col_title:
    st.title(f"📦 Emplacements du Lot")
    st.caption(f"**{lot_info['code_lot_interne']}** - {lot_info['nom_usage']}")

with col_back:
    if st.button("← Retour Stock", use_container_width=True):
        st.switch_page("pages/02_Stock.py")

st.markdown("---")

# ============================================================================
# VUE D'ENSEMBLE
# ============================================================================

st.subheader("📊 Vue d'ensemble")

# KPIs
col1, col2, col3, col4 = st.columns(4)

# Calculer totaux depuis emplacements
emplacements_df = get_lot_emplacements(lot_id)
nb_emplacements = len(emplacements_df)
total_pallox = emplacements_df['nombre_unites'].sum() if not emplacements_df.empty else 0
total_tonnage = (emplacements_df['poids_total_kg'].sum() / 1000) if not emplacements_df.empty and 'poids_total_kg' in emplacements_df.columns else 0

with col1:
    st.metric("📦 Total Pallox", f"{int(total_pallox)}")

with col2:
    st.metric("⚖️ Total Tonnage", f"{total_tonnage:.1f} T")

with col3:
    st.metric("📍 Nb Emplacements", nb_emplacements)

with col4:
    statut_display = f"{lot_info['statut_icone']} {lot_info['statut_libelle']}" if lot_info['statut_icone'] else lot_info['statut_libelle']
    st.metric("🏷️ Statut", statut_display)

st.markdown("---")

# ============================================================================
# INFORMATIONS LOT
# ============================================================================

st.subheader("📋 Informations du Lot")

col1, col2, col3 = st.columns(3)

with col1:
    st.write(f"**Code Lot** : {lot_info['code_lot_interne']}")
    st.write(f"**Nom d'usage** : {lot_info['nom_usage']}")
    st.write(f"**Variété** : {lot_info['nom_variete'] or 'N/A'}")

with col2:
    st.write(f"**Producteur** : {lot_info['nom_producteur'] or 'N/A'}")
    st.write(f"**Date entrée** : {lot_info['date_entree_stock'].strftime('%d/%m/%Y') if lot_info['date_entree_stock'] else 'N/A'}")
    st.write(f"**Âge** : {lot_info['age_jours']} jours")

with col3:
    st.write(f"**Pallox total** : {lot_info['nombre_unites']}")
    poids_display = f"{lot_info['poids_total_brut_kg'] / 1000:.1f} T" if lot_info['poids_total_brut_kg'] else "N/A"
    st.write(f"**Poids brut** : {poids_display}")
    valeur_display = f"{lot_info['valeur_lot_euro']:,.0f} €" if lot_info['valeur_lot_euro'] else "N/A"
    st.write(f"**Valeur** : {valeur_display}")

st.markdown("---")

# ============================================================================
# DÉTAIL EMPLACEMENTS
# ============================================================================

st.subheader("📍 Détail des Emplacements")

if emplacements_df.empty:
    st.warning("⚠️ Aucun emplacement trouvé pour ce lot")
else:
    # Préparer affichage
    display_df = emplacements_df[['site_stockage', 'emplacement_stockage', 'nombre_unites', 'poids_total_kg', 'type_stock']].copy()
    
    # Formatter poids
    if 'poids_total_kg' in display_df.columns:
        display_df['poids_total_t'] = display_df['poids_total_kg'].apply(
            lambda x: f"{x/1000:.1f} T" if pd.notna(x) else "N/A"
        )
        display_df = display_df.drop('poids_total_kg', axis=1)
    
    # Renommer colonnes
    display_df.columns = ['Site', 'Emplacement', 'Pallox', 'Poids', 'Type']
    
    # Afficher tableau
    st.dataframe(
        display_df,
        use_container_width=True,
        hide_index=True
    )
    
    # Stats rapides
    col1, col2, col3 = st.columns(3)
    
    with col1:
        sites_uniques = display_df['Site'].nunique()
        st.info(f"📍 **{sites_uniques}** site(s) de stockage")
    
    with col2:
        bruts = len(display_df[display_df['Type'] == 'BRUT'])
        st.info(f"📦 **{bruts}** emplacement(s) brut")
    
    with col3:
        transit = len(display_df[display_df['Type'] == 'EN_TRANSIT'])
        if transit > 0:
            st.warning(f"🚚 **{transit}** emplacement(s) en transit")

st.markdown("---")

# ============================================================================
# HISTORIQUE MOUVEMENTS
# ============================================================================

st.subheader("📜 Historique des Mouvements (10 derniers)")

mouvements_df = get_lot_mouvements(lot_id, limit=10)

if mouvements_df.empty:
    st.info("ℹ️ Aucun mouvement enregistré pour ce lot")
else:
    # Préparer affichage
    display_mouvements = mouvements_df.copy()
    
    # Formatter date
    display_mouvements['Date'] = pd.to_datetime(display_mouvements['created_at']).dt.strftime('%d/%m %H:%M')
    
    # Formatter type mouvement
    type_labels = {
        'CREATION_LOT': '🆕 Création',
        'TRANSFERT_DEPART': '🚚 Départ',
        'TRANSFERT_ARRIVEE': '📥 Arrivée',
        'DIVISION_LOT': '✂️ Division',
        'LAVAGE': '🧼 Lavage',
        'AJUSTEMENT_MANUEL': '✏️ Ajustement',
        'VENTE': '💰 Vente',
        'PERTE': '⚠️ Perte'
    }
    display_mouvements['Type'] = display_mouvements['type_mouvement'].map(type_labels)
    
    # Formatter trajet
    display_mouvements['Trajet'] = display_mouvements.apply(
        lambda row: f"{row['site_avant'] or '-'} → {row['site_apres'] or '-'}",
        axis=1
    )
    
    # Formatter quantité
    display_mouvements['Quantité'] = display_mouvements['quantite_mouvement'].apply(
        lambda x: f"{'+' if x > 0 else ''}{x} P" if pd.notna(x) else "N/A"
    )
    
    # Formatter utilisateur
    display_mouvements['Par'] = display_mouvements['created_by'].fillna('Système')
    
    # Sélectionner colonnes finales
    final_df = display_mouvements[['Date', 'Type', 'Trajet', 'Quantité', 'Par']]
    
    # Afficher tableau
    st.dataframe(
        final_df,
        use_container_width=True,
        hide_index=True
    )

st.markdown("---")

# ============================================================================
# ACTIONS
# ============================================================================

st.subheader("⚡ Actions Rapides")

col1, col2, col3 = st.columns(3)

with col1:
    if st.button("🚚 Créer un Transfert", use_container_width=True, type="primary"):
        st.info("🚧 Fonctionnalité disponible en Phase B (Planning Transferts)")

with col2:
    if st.button("📊 Voir Historique Complet", use_container_width=True):
        st.info("🚧 Fonctionnalité disponible en Phase C (Historique Stock)")

with col3:
    if st.button("✏️ Modifier Lot", use_container_width=True):
        st.switch_page("pages/02_Stock.py")

# Footer
show_footer()
