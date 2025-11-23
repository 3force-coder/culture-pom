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

# ⭐ Récupérer les IDs des lots sélectionnés depuis session_state
selected_lot_ids = st.session_state.get('selected_lots_for_emplacements', [])

if not selected_lot_ids:
    st.error("❌ Aucun lot sélectionné")
    st.info("💡 Veuillez cocher un ou plusieurs lots dans la page Stock, puis cliquer sur 'Voir Emplacements'")
    if st.button("← Retour à la liste des lots", use_container_width=True):
        st.switch_page("pages/02_Stock.py")
    st.stop()

# Vérifier que ce sont bien des entiers
try:
    selected_lot_ids = [int(lot_id) for lot_id in selected_lot_ids]
except:
    st.error("❌ IDs de lots invalides")
    if st.button("← Retour à la liste des lots", use_container_width=True):
        st.switch_page("pages/02_Stock.py")
    st.stop()

# ============================================================================
# TITRE & NAVIGATION
# ============================================================================

col_title, col_back = st.columns([4, 1])

with col_title:
    nb_lots = len(selected_lot_ids)
    if nb_lots == 1:
        st.title(f"📦 Emplacements du Lot")
    else:
        st.title(f"📦 Emplacements de {nb_lots} Lots")

with col_back:
    if st.button("← Retour Stock", use_container_width=True):
        st.switch_page("pages/02_Stock.py")

st.markdown("---")

# ============================================================================
# VUE D'ENSEMBLE CONSOLIDÉE (tous les lots)
# ============================================================================

st.subheader("📊 Vue Consolidée")

# Calculer totaux pour tous les lots
total_lots = len(selected_lot_ids)
total_pallox_global = 0
total_tonnage_global = 0
total_emplacements_global = 0

# Charger données de tous les lots
lots_data = []

for lot_id in selected_lot_ids:
    lot_info = get_lot_info(lot_id)
    if lot_info:
        emplacements_df = get_lot_emplacements(lot_id)
        
        nb_emplacements = len(emplacements_df)
        total_pallox = emplacements_df['nombre_unites'].sum() if not emplacements_df.empty else 0
        total_tonnage = (emplacements_df['poids_total_kg'].sum() / 1000) if not emplacements_df.empty and 'poids_total_kg' in emplacements_df.columns else 0
        
        lots_data.append({
            'lot_id': lot_id,
            'lot_info': lot_info,
            'emplacements_df': emplacements_df,
            'nb_emplacements': nb_emplacements,
            'total_pallox': total_pallox,
            'total_tonnage': total_tonnage
        })
        
        total_pallox_global += total_pallox
        total_tonnage_global += total_tonnage
        total_emplacements_global += nb_emplacements

# KPIs Consolidés
col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric("📦 Total Lots", total_lots)

with col2:
    st.metric("📦 Total Pallox", f"{int(total_pallox_global)}")

with col3:
    st.metric("⚖️ Total Tonnage", f"{total_tonnage_global:.1f} T")

with col4:
    st.metric("📍 Total Emplacements", total_emplacements_global)

st.markdown("---")

# ============================================================================
# DÉTAIL PAR LOT (Vue Compacte avec Expanders)
# ============================================================================

st.subheader("📍 Détail par Lot")

for lot_data in lots_data:
    lot_info = lot_data['lot_info']
    emplacements_df = lot_data['emplacements_df']
    
    # ⭐ EXPANDER POUR CHAQUE LOT
    with st.expander(
        f"🔽 {lot_info['code_lot_interne']} - {lot_info['nom_usage']} "
        f"({int(lot_data['total_pallox'])} pallox, {lot_data['total_tonnage']:.1f}T)",
        expanded=True if len(lots_data) <= 3 else False
    ):
        
        # Infos lot (compact - 2 colonnes)
        col1, col2 = st.columns(2)
        
        with col1:
            st.write(f"**Variété** : {lot_info['nom_variete'] or 'N/A'}")
            st.write(f"**Producteur** : {lot_info['nom_producteur'] or 'N/A'}")
            st.write(f"**Âge** : {lot_info['age_jours']} jours")
        
        with col2:
            statut_display = f"{lot_info['statut_icone']} {lot_info['statut_libelle']}" if lot_info['statut_icone'] else lot_info['statut_libelle'] or "N/A"
            st.write(f"**Statut** : {statut_display}")
            valeur_display = f"{lot_info['valeur_lot_euro']:,.0f} €" if lot_info['valeur_lot_euro'] else "N/A"
            st.write(f"**Valeur** : {valeur_display}")
            st.write(f"**Emplacements** : {lot_data['nb_emplacements']}")
        
        st.markdown("---")
        
        # Tableau emplacements
        if not emplacements_df.empty:
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
            
            # Historique (5 derniers mouvements seulement)
            st.markdown("**📜 Historique récent**")
            mouvements_df = get_lot_mouvements(lot_data['lot_id'], limit=5)
            
            if not mouvements_df.empty:
                display_mouvements = mouvements_df.copy()
                
                display_mouvements['Date'] = pd.to_datetime(display_mouvements['created_at']).dt.strftime('%d/%m %H:%M')
                
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
                
                display_mouvements['Trajet'] = display_mouvements.apply(
                    lambda row: f"{row['site_avant'] or '-'} → {row['site_apres'] or '-'}",
                    axis=1
                )
                
                final_df = display_mouvements[['Date', 'Type', 'Trajet']]
                
                st.dataframe(
                    final_df,
                    use_container_width=True,
                    hide_index=True,
                    height=150
                )
            else:
                st.caption("Aucun mouvement enregistré")
        else:
            st.warning("⚠️ Aucun emplacement trouvé pour ce lot")

st.markdown("---")

# ============================================================================
# ACTIONS RAPIDES
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
    if st.button("← Retour à la Liste", use_container_width=True):
        st.switch_page("pages/02_Stock.py")

# Footer
show_footer()
