"""
Page 14 - Récaps Plan Récolte ENHANCED
KPIs globaux + 5 vues agrégées + 2 nouveaux onglets d'ajustement
VERSION DÉCIMAUX - Support hectares par pas de 0.5

NOUVEAUTÉS :
- ⭐ Récap Marque+Type : Ajustement volume total avec répartition proportionnelle
- ⭐ Récap Variété : Modification masse taux déchets/rendement

ATTENTION COLONNES GENERATED :
- volume_brut_t = volume_net_t / (1 - dechets_pct/100)
- hectares_necessaires = volume_brut_t / rendement_t_ha
→ Ne JAMAIS les modifier dans les UPDATE, elles se recalculent auto
"""
import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime
import time
from database import get_connection
from components import show_footer
from auth import require_access, can_edit, can_delete, get_current_username
import io

st.set_page_config(page_title="Récaps Plan - Culture Pom", page_icon="📊", layout="wide")

# CSS compact
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
    .metric-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 1rem;
        border-radius: 0.5rem;
        color: white;
        text-align: center;
    }
    .recap-card {
        background: linear-gradient(135deg, #51cf66 0%, #40c057 100%);
        padding: 1.5rem;
        border-radius: 0.8rem;
        color: white;
        margin: 1rem 0;
    }
    .impact-card {
        background: #fff3e0;
        border-left: 4px solid #ff9800;
        padding: 1rem;
        border-radius: 0.5rem;
        margin: 1rem 0;
    }
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
    }
    .stTabs [data-baseweb="tab"] {
        padding: 8px 16px;
    }
</style>
""", unsafe_allow_html=True)

# Vérification authentification et permissions RBAC
require_access("PLANS_RECOLTE")

# Permissions utilisateur
CAN_EDIT = can_edit("PLANS_RECOLTE")
CAN_DELETE = can_delete("PLANS_RECOLTE")

st.title("📊 Récaps Plan Récolte")
st.markdown("*Synthèses et analyses du plan de récolte*")
st.markdown("---")

# ==========================================
# FONCTIONS UTILITAIRES
# ==========================================

def convert_to_native(value):
    """Convertit numpy/pandas types en types Python natifs"""
    if pd.isna(value) or value is None:
        return None
    if isinstance(value, (np.int64, np.int32, np.int16, np.int8)):
        return int(value)
    if isinstance(value, (np.float64, np.float32)):
        return float(value)
    if isinstance(value, np.bool_):
        return bool(value)
    return value

# ==========================================
# FONCTIONS DE CHARGEMENT (EXISTANTES)
# ==========================================

@st.cache_data(ttl=60)
def get_kpis_globaux(campagne):
    """KPIs globaux du plan"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                COUNT(*) as nb_lignes,
                COUNT(DISTINCT variete) as nb_varietes,
                COUNT(DISTINCT marque) as nb_marques,
                COUNT(DISTINCT type_produit) as nb_types,
                COALESCE(SUM(volume_net_t), 0) as total_volume_net,
                COALESCE(SUM(volume_brut_t), 0) as total_volume_brut,
                COALESCE(SUM(hectares_necessaires), 0) as total_hectares,
                COALESCE(ROUND(SUM(hectares_necessaires)::NUMERIC, 1), 0) as total_hectares_arrondi
            FROM plans_recolte
            WHERE campagne = %s AND is_active = TRUE
        """, (campagne,))
        
        row = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if row:
            return {
                'nb_lignes': row['nb_lignes'],
                'nb_varietes': row['nb_varietes'],
                'nb_marques': row['nb_marques'],
                'nb_types': row['nb_types'],
                'total_volume_net': float(row['total_volume_net']),
                'total_volume_brut': float(row['total_volume_brut']),
                'total_hectares': float(row['total_hectares']),
                'total_hectares_arrondi': float(row['total_hectares_arrondi'])
            }
        return None
    except Exception as e:
        st.error(f"Erreur KPIs : {e}")
        return None


@st.cache_data(ttl=60)
def get_recap_par_mois(campagne):
    """Récap par mois"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                mois,
                mois_numero,
                COUNT(*) as nb_lignes,
                COUNT(DISTINCT variete) as nb_varietes,
                SUM(volume_net_t) as volume_net,
                SUM(volume_brut_t) as volume_brut,
                SUM(hectares_necessaires) as hectares,
                ROUND(SUM(hectares_necessaires)::NUMERIC, 1) as hectares_arrondi
            FROM plans_recolte
            WHERE campagne = %s AND is_active = TRUE
            GROUP BY mois, mois_numero
            ORDER BY mois_numero
        """, (campagne,))
        
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        
        if rows:
            df = pd.DataFrame(rows)
            df = df.rename(columns={
                'mois': 'Mois',
                'nb_lignes': 'Lignes',
                'nb_varietes': 'Variétés',
                'volume_net': 'Volume Net (T)',
                'volume_brut': 'Volume Brut (T)',
                'hectares': 'Hectares',
                'hectares_arrondi': 'Ha Arrondi'
            })
            return df
        return pd.DataFrame()
    except Exception as e:
        st.error(f"Erreur : {e}")
        return pd.DataFrame()


@st.cache_data(ttl=60)
def get_recap_par_variete(campagne):
    """Récap par variété"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                variete,
                COUNT(*) as nb_lignes,
                COUNT(DISTINCT mois) as nb_mois,
                SUM(volume_net_t) as volume_net,
                SUM(volume_brut_t) as volume_brut,
                SUM(hectares_necessaires) as hectares,
                ROUND(SUM(hectares_necessaires)::NUMERIC, 1) as hectares_arrondi
            FROM plans_recolte
            WHERE campagne = %s AND is_active = TRUE
            GROUP BY variete
            ORDER BY SUM(volume_net_t) DESC
        """, (campagne,))
        
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        
        if rows:
            df = pd.DataFrame(rows)
            df = df.rename(columns={
                'variete': 'Variété',
                'nb_lignes': 'Lignes',
                'nb_mois': 'Mois',
                'volume_net': 'Volume Net (T)',
                'volume_brut': 'Volume Brut (T)',
                'hectares': 'Hectares',
                'hectares_arrondi': 'Ha Arrondi'
            })
            return df
        return pd.DataFrame()
    except Exception as e:
        st.error(f"Erreur : {e}")
        return pd.DataFrame()


@st.cache_data(ttl=60)
def get_recap_par_marque(campagne):
    """Récap par marque"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                marque,
                COUNT(*) as nb_lignes,
                COUNT(DISTINCT type_produit) as nb_types,
                SUM(volume_net_t) as volume_net,
                SUM(volume_brut_t) as volume_brut,
                SUM(hectares_necessaires) as hectares,
                ROUND(SUM(hectares_necessaires)::NUMERIC, 1) as hectares_arrondi
            FROM plans_recolte
            WHERE campagne = %s AND is_active = TRUE
            GROUP BY marque
            ORDER BY SUM(volume_net_t) DESC
        """, (campagne,))
        
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        
        if rows:
            df = pd.DataFrame(rows)
            df = df.rename(columns={
                'marque': 'Marque',
                'nb_lignes': 'Lignes',
                'nb_types': 'Types',
                'volume_net': 'Volume Net (T)',
                'volume_brut': 'Volume Brut (T)',
                'hectares': 'Hectares',
                'hectares_arrondi': 'Ha Arrondi'
            })
            return df
        return pd.DataFrame()
    except Exception as e:
        st.error(f"Erreur : {e}")
        return pd.DataFrame()


@st.cache_data(ttl=60)
def get_recap_par_type(campagne):
    """Récap par type produit"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                type_produit,
                COUNT(*) as nb_lignes,
                COUNT(DISTINCT marque) as nb_marques,
                SUM(volume_net_t) as volume_net,
                SUM(volume_brut_t) as volume_brut,
                SUM(hectares_necessaires) as hectares,
                ROUND(SUM(hectares_necessaires)::NUMERIC, 1) as hectares_arrondi
            FROM plans_recolte
            WHERE campagne = %s AND is_active = TRUE
            GROUP BY type_produit
            ORDER BY SUM(volume_net_t) DESC
        """, (campagne,))
        
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        
        if rows:
            df = pd.DataFrame(rows)
            df = df.rename(columns={
                'type_produit': 'Type Produit',
                'nb_lignes': 'Lignes',
                'nb_marques': 'Marques',
                'volume_net': 'Volume Net (T)',
                'volume_brut': 'Volume Brut (T)',
                'hectares': 'Hectares',
                'hectares_arrondi': 'Ha Arrondi'
            })
            return df
        return pd.DataFrame()
    except Exception as e:
        st.error(f"Erreur : {e}")
        return pd.DataFrame()


@st.cache_data(ttl=60)
def get_besoins_avec_couverture(campagne):
    """Besoins mensuels avec couverture"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                mois,
                variete,
                SUM(volume_net_t) as volume_net,
                SUM(volume_brut_t) as volume_brut,
                SUM(hectares_necessaires) as hectares_necessaires,
                ROUND(SUM(hectares_necessaires)::NUMERIC, 1) as hectares_arrondi,
                AVG(taux_couverture_cible) as taux_couverture_moyen,
                SUM(COALESCE(hectares_ajustes, hectares_necessaires)) as hectares_avec_couverture
            FROM plans_recolte
            WHERE campagne = %s AND is_active = TRUE
            GROUP BY mois, variete
            ORDER BY mois, variete
        """, (campagne,))
        
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        
        if rows:
            df = pd.DataFrame(rows)
            df = df.rename(columns={
                'mois': 'Mois',
                'variete': 'Variété',
                'volume_net': 'Volume Net (T)',
                'volume_brut': 'Volume Brut (T)',
                'hectares_necessaires': 'Ha Nécessaires',
                'hectares_arrondi': 'Ha Arrondi',
                'taux_couverture_moyen': 'Taux Couverture (%)',
                'hectares_avec_couverture': 'Ha Avec Couverture'
            })
            return df
        return pd.DataFrame()
    except Exception as e:
        st.error(f"Erreur : {e}")
        return pd.DataFrame()


# ==========================================
# 🆕 FONCTIONS NOUVEAUX ONGLETS
# ==========================================

# ========== MARQUE + TYPE ==========

@st.cache_data(ttl=60)
def get_marques_disponibles(campagne):
    """Liste des marques disponibles"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT DISTINCT marque
            FROM plans_recolte
            WHERE campagne = %s AND is_active = TRUE AND marque IS NOT NULL
            ORDER BY marque
        """, (campagne,))
        
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        
        return [row['marque'] for row in rows] if rows else []
    except Exception as e:
        st.error(f"Erreur : {e}")
        return []


@st.cache_data(ttl=60)
def get_types_pour_marque(campagne, marque):
    """Types produits disponibles pour une marque"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT DISTINCT type_produit
            FROM plans_recolte
            WHERE campagne = %s AND marque = %s AND is_active = TRUE AND type_produit IS NOT NULL
            ORDER BY type_produit
        """, (campagne, marque))
        
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        
        return [row['type_produit'] for row in rows] if rows else []
    except Exception as e:
        st.error(f"Erreur : {e}")
        return []


@st.cache_data(ttl=60)
def get_recap_marque_type(campagne, marque, type_produit):
    """Récap pour une combinaison Marque + Type"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Total annuel
        cursor.execute("""
            SELECT 
                COUNT(*) as nb_lignes,
                COUNT(DISTINCT mois) as nb_mois,
                SUM(volume_net_t) as total_volume_net,
                SUM(volume_brut_t) as total_volume_brut
            FROM plans_recolte
            WHERE campagne = %s AND marque = %s AND type_produit = %s AND is_active = TRUE
        """, (campagne, marque, type_produit))
        
        total = cursor.fetchone()
        
        # Détail par mois
        cursor.execute("""
            SELECT 
                mois,
                COUNT(*) as nb_lignes,
                SUM(volume_net_t) as volume_net
            FROM plans_recolte
            WHERE campagne = %s AND marque = %s AND type_produit = %s AND is_active = TRUE
            GROUP BY mois
            ORDER BY mois
        """, (campagne, marque, type_produit))
        
        detail = cursor.fetchall()
        cursor.close()
        conn.close()
        
        result = {
            'total': {
                'nb_lignes': total['nb_lignes'],
                'nb_mois': total['nb_mois'],
                'volume_net': float(total['total_volume_net'] or 0)
            },
            'detail': pd.DataFrame(detail) if detail else pd.DataFrame()
        }
        
        return result
    except Exception as e:
        st.error(f"Erreur : {e}")
        return None


def ajuster_volume_proportionnel(marque, type_produit, nouveau_total, campagne):
    """
    Ajuste le volume total d'une combinaison Marque+Type
    en répartissant proportionnellement sur tous les mois
    
    ⚠️ IMPORTANT : Ne modifie que volume_net_t
    Les colonnes GENERATED (volume_brut_t, hectares_necessaires) se recalculent auto
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Récupérer total actuel
        cursor.execute("""
            SELECT SUM(volume_net_t) as total_actuel
            FROM plans_recolte
            WHERE campagne = %s AND marque = %s AND type_produit = %s AND is_active = TRUE
        """, (campagne, marque, type_produit))
        
        total_actuel = float(cursor.fetchone()['total_actuel'] or 0)
        
        if total_actuel == 0:
            cursor.close()
            conn.close()
            return False, "❌ Total actuel = 0, impossible d'ajuster"
        
        # Calculer ratio
        nouveau_total_float = float(nouveau_total)
        ratio = nouveau_total_float / total_actuel
        
        # Mettre à jour UNIQUEMENT volume_net_t (les colonnes GENERATED se recalculent auto)
        updated_by = get_current_username()
        
        cursor.execute("""
            UPDATE plans_recolte
            SET volume_net_t = volume_net_t * %s,
                updated_by = %s,
                updated_at = CURRENT_TIMESTAMP
            WHERE campagne = %s 
              AND marque = %s 
              AND type_produit = %s 
              AND is_active = TRUE
        """, (ratio, updated_by, campagne, marque, type_produit))
        
        nb_updated = cursor.rowcount
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return True, f"✅ {nb_updated} ligne(s) ajustée(s) - Ratio: {ratio:.3f}"
        
    except Exception as e:
        if 'conn' in locals():
            conn.rollback()
            conn.close()
        return False, f"❌ Erreur : {str(e)}"


# ========== VARIÉTÉ ==========

@st.cache_data(ttl=60)
def get_varietes_disponibles(campagne):
    """Liste des variétés disponibles"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT DISTINCT variete
            FROM plans_recolte
            WHERE campagne = %s AND is_active = TRUE
            ORDER BY variete
        """, (campagne,))
        
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        
        return [row['variete'] for row in rows] if rows else []
    except Exception as e:
        st.error(f"Erreur : {e}")
        return []


@st.cache_data(ttl=60)
def get_recap_variete_detail(campagne, variete):
    """Récap détaillé pour une variété"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Total
        cursor.execute("""
            SELECT 
                COUNT(*) as nb_lignes,
                SUM(volume_net_t) as total_volume_net,
                AVG(dechets_pct) as dechets_moyen,
                AVG(rendement_t_ha) as rendement_moyen
            FROM plans_recolte
            WHERE campagne = %s AND variete = %s AND is_active = TRUE
        """, (campagne, variete))
        
        total = cursor.fetchone()
        
        # Détail par mois
        cursor.execute("""
            SELECT 
                mois,
                COUNT(*) as nb_lignes,
                SUM(volume_net_t) as volume_net,
                AVG(dechets_pct) as dechets_pct,
                AVG(rendement_t_ha) as rendement_t_ha
            FROM plans_recolte
            WHERE campagne = %s AND variete = %s AND is_active = TRUE
            GROUP BY mois
            ORDER BY mois
        """, (campagne, variete))
        
        detail = cursor.fetchall()
        cursor.close()
        conn.close()
        
        result = {
            'total': {
                'nb_lignes': total['nb_lignes'],
                'volume_net': float(total['total_volume_net'] or 0),
                'dechets_moyen': float(total['dechets_moyen'] or 0),
                'rendement_moyen': float(total['rendement_moyen'] or 0)
            },
            'detail': pd.DataFrame(detail) if detail else pd.DataFrame()
        }
        
        return result
    except Exception as e:
        st.error(f"Erreur : {e}")
        return None


def ajuster_dechets_variete(variete, nouveau_dechets_pct, campagne, mois_list=None):
    """
    Ajuste le taux de déchets pour une variété
    
    Args:
        variete: Nom de la variété
        nouveau_dechets_pct: Nouveau taux de déchets (%)
        campagne: Campagne
        mois_list: Liste de mois optionnelle (si None, applique sur tous)
    
    ⚠️ IMPORTANT : Ne modifie que dechets_pct
    La colonne GENERATED volume_brut_t se recalcule auto
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        updated_by = get_current_username()
        nouveau_dechets_float = float(nouveau_dechets_pct)
        
        if mois_list:
            # Appliquer sur certains mois uniquement
            placeholders = ','.join(['%s'] * len(mois_list))
            query = f"""
                UPDATE plans_recolte
                SET dechets_pct = %s,
                    updated_by = %s,
                    updated_at = CURRENT_TIMESTAMP
                WHERE campagne = %s 
                  AND variete = %s 
                  AND mois IN ({placeholders})
                  AND is_active = TRUE
            """
            params = [nouveau_dechets_float, updated_by, campagne, variete] + mois_list
        else:
            # Appliquer sur tous les mois
            query = """
                UPDATE plans_recolte
                SET dechets_pct = %s,
                    updated_by = %s,
                    updated_at = CURRENT_TIMESTAMP
                WHERE campagne = %s 
                  AND variete = %s 
                  AND is_active = TRUE
            """
            params = [nouveau_dechets_float, updated_by, campagne, variete]
        
        cursor.execute(query, params)
        nb_updated = cursor.rowcount
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return True, f"✅ {nb_updated} ligne(s) mise(s) à jour"
        
    except Exception as e:
        if 'conn' in locals():
            conn.rollback()
            conn.close()
        return False, f"❌ Erreur : {str(e)}"


def ajuster_rendement_variete(variete, nouveau_rendement, campagne, mois_list=None):
    """
    Ajuste le rendement pour une variété
    
    Args:
        variete: Nom de la variété
        nouveau_rendement: Nouveau rendement (T/ha)
        campagne: Campagne
        mois_list: Liste de mois optionnelle (si None, applique sur tous)
    
    ⚠️ IMPORTANT : Ne modifie que rendement_t_ha
    La colonne GENERATED hectares_necessaires se recalcule auto
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        updated_by = get_current_username()
        nouveau_rendement_float = float(nouveau_rendement)
        
        if mois_list:
            # Appliquer sur certains mois uniquement
            placeholders = ','.join(['%s'] * len(mois_list))
            query = f"""
                UPDATE plans_recolte
                SET rendement_t_ha = %s,
                    updated_by = %s,
                    updated_at = CURRENT_TIMESTAMP
                WHERE campagne = %s 
                  AND variete = %s 
                  AND mois IN ({placeholders})
                  AND is_active = TRUE
            """
            params = [nouveau_rendement_float, updated_by, campagne, variete] + mois_list
        else:
            # Appliquer sur tous les mois
            query = """
                UPDATE plans_recolte
                SET rendement_t_ha = %s,
                    updated_by = %s,
                    updated_at = CURRENT_TIMESTAMP
                WHERE campagne = %s 
                  AND variete = %s 
                  AND is_active = TRUE
            """
            params = [nouveau_rendement_float, updated_by, campagne, variete]
        
        cursor.execute(query, params)
        nb_updated = cursor.rowcount
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return True, f"✅ {nb_updated} ligne(s) mise(s) à jour"
        
    except Exception as e:
        if 'conn' in locals():
            conn.rollback()
            conn.close()
        return False, f"❌ Erreur : {str(e)}"


# ==========================================
# INTERFACE PRINCIPALE
# ==========================================

# Sélection campagne
campagne = st.selectbox(
    "📅 Campagne",
    options=[2026, 2027, 2028],
    index=0,
    key="select_campagne"
)

st.markdown("---")

# KPIs globaux
kpis = get_kpis_globaux(campagne)

if kpis:
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("📋 Lignes", f"{kpis['nb_lignes']:,}")
    
    with col2:
        st.metric("🌱 Variétés", kpis['nb_varietes'])
    
    with col3:
        st.metric("📦 Volume Net", f"{kpis['total_volume_net']:,.0f} T")
    
    with col4:
        st.metric("🌾 Hectares", f"{kpis['total_hectares_arrondi']:.1f} ha")
    
    st.markdown("---")

# ==========================================
# ONGLETS
# ==========================================

tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs([
    "📅 Par Mois",
    "🌱 Par Variété",
    "📦 Par Marque",
    "🏷️ Par Type",
    "🎯 Besoins",
    "⭐ Récap Marque+Type",  # NOUVEAU
    "⭐ Récap Variété"       # NOUVEAU
])

# ========== ONGLET 1 : PAR MOIS ==========
with tab1:
    st.subheader("📅 Récap par Mois")
    
    df_mois = get_recap_par_mois(campagne)
    
    if not df_mois.empty:
        st.dataframe(
            df_mois.drop(columns=['mois_numero']),
            use_container_width=True,
            hide_index=True
        )
    else:
        st.info("Aucune donnée pour cette campagne")

# ========== ONGLET 2 : PAR VARIÉTÉ ==========
with tab2:
    st.subheader("🌱 Récap par Variété")
    
    df_variete = get_recap_par_variete(campagne)
    
    if not df_variete.empty:
        st.dataframe(
            df_variete,
            use_container_width=True,
            hide_index=True
        )
    else:
        st.info("Aucune donnée pour cette campagne")

# ========== ONGLET 3 : PAR MARQUE ==========
with tab3:
    st.subheader("📦 Récap par Marque")
    
    df_marque = get_recap_par_marque(campagne)
    
    if not df_marque.empty:
        st.dataframe(
            df_marque,
            use_container_width=True,
            hide_index=True
        )
    else:
        st.info("Aucune donnée pour cette campagne")

# ========== ONGLET 4 : PAR TYPE ==========
with tab4:
    st.subheader("🏷️ Récap par Type Produit")
    
    df_type = get_recap_par_type(campagne)
    
    if not df_type.empty:
        st.dataframe(
            df_type,
            use_container_width=True,
            hide_index=True
        )
    else:
        st.info("Aucune donnée pour cette campagne")

# ========== ONGLET 5 : BESOINS ==========
with tab5:
    st.subheader("🎯 Besoins avec Couverture")
    
    df_besoins = get_besoins_avec_couverture(campagne)
    
    if not df_besoins.empty:
        st.dataframe(
            df_besoins,
            use_container_width=True,
            hide_index=True
        )
    else:
        st.info("Aucune donnée pour cette campagne")

# ========== ONGLET 6 : RÉCAP MARQUE+TYPE (NOUVEAU) ==========
with tab6:
    st.subheader("⭐ Récap Marque + Type")
    st.markdown("*Ajustement volume total avec répartition proportionnelle automatique*")
    
    marques = get_marques_disponibles(campagne)
    
    if marques:
        # Sélection Marque
        marque_selected = st.selectbox(
            "📦 Sélectionner Marque",
            options=marques,
            key="marque_recap"
        )
        
        # Sélection Type pour cette marque
        types = get_types_pour_marque(campagne, marque_selected)
        
        if types:
            type_selected = st.selectbox(
                "🏷️ Sélectionner Type Produit",
                options=types,
                key="type_recap"
            )
            
            st.markdown("---")
            
            # Charger récap
            recap = get_recap_marque_type(campagne, marque_selected, type_selected)
            
            if recap and recap['total']['nb_lignes'] > 0:
                total = recap['total']
                
                # Carte récap
                st.markdown(f"""
                <div class="recap-card">
                    <h3 style="margin:0; color:white;">{marque_selected} - {type_selected}</h3>
                    <hr style="border-color: rgba(255,255,255,0.3); margin: 1rem 0;">
                    <div style="display:flex; justify-content:space-around;">
                        <div>
                            <div style="font-size:2rem; font-weight:bold;">{total['volume_net']:.1f} T</div>
                            <div style="opacity:0.9;">Volume Net Annuel</div>
                        </div>
                        <div>
                            <div style="font-size:2rem; font-weight:bold;">{total['nb_mois']}</div>
                            <div style="opacity:0.9;">Mois</div>
                        </div>
                        <div>
                            <div style="font-size:2rem; font-weight:bold;">{total['nb_lignes']}</div>
                            <div style="opacity:0.9;">Lignes</div>
                        </div>
                    </div>
                </div>
                """, unsafe_allow_html=True)
                
                # Tableau détail mensuel
                if not recap['detail'].empty:
                    df_detail = recap['detail'].copy()
                    
                    # Ajouter % du total
                    df_detail['% Total'] = (df_detail['volume_net'] / total['volume_net'] * 100).round(1)
                    
                    df_detail = df_detail.rename(columns={
                        'mois': 'Mois',
                        'nb_lignes': 'Nb Lignes',
                        'volume_net': 'Volume Net (T)'
                    })
                    
                    st.markdown("**📊 Détail mensuel**")
                    st.dataframe(
                        df_detail,
                        use_container_width=True,
                        hide_index=True
                    )
                
                st.markdown("---")
                
                # Formulaire ajustement (seulement si CAN_EDIT)
                if CAN_EDIT:
                    st.markdown("### 🎯 Ajuster Volume Total")
                    
                    col1, col2 = st.columns([2, 1])
                    
                    with col1:
                        nouveau_total = st.number_input(
                            "Nouveau total annuel (T)",
                            min_value=0.0,
                            value=float(total['volume_net']),
                            step=10.0,
                            key="nouveau_total_mt"
                        )
                    
                    with col2:
                        if nouveau_total != total['volume_net']:
                            ratio = nouveau_total / total['volume_net']
                            delta = nouveau_total - total['volume_net']
                            variation_pct = (delta / total['volume_net']) * 100
                            
                            st.markdown(f"""
                            <div class="impact-card">
                                <strong>💡 Impact</strong><br>
                                Ratio: <strong>{ratio:.3f}</strong><br>
                                Delta: <strong>{delta:+.1f} T</strong><br>
                                Variation: <strong>{variation_pct:+.1f}%</strong>
                            </div>
                            """, unsafe_allow_html=True)
                    
                    if st.button("✅ Appliquer Répartition Proportionnelle", type="primary", use_container_width=True):
                        if nouveau_total == total['volume_net']:
                            st.warning("⚠️ Le nouveau total est identique à l'actuel")
                        else:
                            success, message = ajuster_volume_proportionnel(
                                marque_selected, type_selected, nouveau_total, campagne
                            )
                            
                            if success:
                                st.success(message)
                                st.balloons()
                                time.sleep(2)
                                st.cache_data.clear()  # Vider le cache
                                st.rerun()
                            else:
                                st.error(message)
                else:
                    st.info("🔒 Vous n'avez pas les droits de modification")
            else:
                st.warning("⚠️ Aucune donnée pour cette combinaison")
        else:
            st.warning(f"⚠️ Aucun type produit pour la marque {marque_selected}")
    else:
        st.warning("⚠️ Aucune marque disponible")

# ========== ONGLET 7 : RÉCAP VARIÉTÉ (NOUVEAU) ==========
with tab7:
    st.subheader("⭐ Récap Variété")
    st.markdown("*Modification en masse du taux de déchets ou rendement*")
    
    varietes = get_varietes_disponibles(campagne)
    
    if varietes:
        # Sélection Variété
        variete_selected = st.selectbox(
            "🌱 Sélectionner Variété",
            options=varietes,
            key="variete_recap"
        )
        
        st.markdown("---")
        
        # Charger récap
        recap = get_recap_variete_detail(campagne, variete_selected)
        
        if recap and recap['total']['nb_lignes'] > 0:
            total = recap['total']
            
            # Carte récap
            st.markdown(f"""
            <div class="recap-card">
                <h3 style="margin:0; color:white;">{variete_selected}</h3>
                <hr style="border-color: rgba(255,255,255,0.3); margin: 1rem 0;">
                <div style="display:grid; grid-template-columns: repeat(4, 1fr); gap: 1rem;">
                    <div>
                        <div style="font-size:2rem; font-weight:bold;">{total['volume_net']:.1f} T</div>
                        <div style="opacity:0.9;">Volume Net</div>
                    </div>
                    <div>
                        <div style="font-size:2rem; font-weight:bold;">{total['nb_lignes']}</div>
                        <div style="opacity:0.9;">Lignes</div>
                    </div>
                    <div>
                        <div style="font-size:2rem; font-weight:bold;">{total['dechets_moyen']:.1f}%</div>
                        <div style="opacity:0.9;">Déchets Moyen</div>
                    </div>
                    <div>
                        <div style="font-size:2rem; font-weight:bold;">{total['rendement_moyen']:.1f} T/ha</div>
                        <div style="opacity:0.9;">Rendement Moyen</div>
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)
            
            # Tableau détail mensuel
            if not recap['detail'].empty:
                df_detail = recap['detail'].copy()
                
                df_detail = df_detail.rename(columns={
                    'mois': 'Mois',
                    'nb_lignes': 'Nb Lignes',
                    'volume_net': 'Volume Net (T)',
                    'dechets_pct': 'Déchets (%)',
                    'rendement_t_ha': 'Rendement (T/ha)'
                })
                
                # Convertir colonnes numériques
                for col in ['Volume Net (T)', 'Déchets (%)', 'Rendement (T/ha)']:
                    if col in df_detail.columns:
                        df_detail[col] = pd.to_numeric(df_detail[col], errors='coerce')
                
                st.markdown("**📊 Détail mensuel**")
                st.dataframe(
                    df_detail,
                    use_container_width=True,
                    hide_index=True
                )
                
                # Liste des mois pour sélection optionnelle
                mois_disponibles = df_detail['Mois'].tolist()
            else:
                mois_disponibles = []
            
            st.markdown("---")
            
            # Formulaire modification (seulement si CAN_EDIT)
            if CAN_EDIT:
                st.markdown("### 🎯 Modifier en Masse")
                
                # Sélection mois (optionnelle)
                st.markdown("**📅 Sélection Mois (optionnel)**")
                appliquer_sur = st.radio(
                    "Appliquer sur :",
                    options=["Tous les mois", "Certains mois uniquement"],
                    horizontal=True,
                    key="appliquer_sur_variete"
                )
                
                mois_selectionnes = None
                if appliquer_sur == "Certains mois uniquement" and mois_disponibles:
                    mois_selectionnes = st.multiselect(
                        "Sélectionner mois",
                        options=mois_disponibles,
                        key="mois_selectionnes"
                    )
                    
                    if not mois_selectionnes:
                        st.warning("⚠️ Veuillez sélectionner au moins un mois")
                
                st.markdown("---")
                
                col1, col2 = st.columns(2)
                
                # Ajustement Déchets
                with col1:
                    st.markdown("**🗑️ Ajuster Taux Déchets**")
                    
                    nouveau_dechets = st.number_input(
                        "Nouveau taux (%)",
                        min_value=0.0,
                        max_value=100.0,
                        value=float(total['dechets_moyen']),
                        step=1.0,
                        key="nouveau_dechets"
                    )
                    
                    if st.button("✅ Appliquer Déchets", use_container_width=True, key="btn_dechets"):
                        if appliquer_sur == "Certains mois uniquement" and not mois_selectionnes:
                            st.error("❌ Veuillez sélectionner au moins un mois")
                        else:
                            success, message = ajuster_dechets_variete(
                                variete_selected, nouveau_dechets, campagne, mois_selectionnes
                            )
                            
                            if success:
                                st.success(message)
                                st.balloons()
                                time.sleep(2)
                                st.cache_data.clear()
                                st.rerun()
                            else:
                                st.error(message)
                
                # Ajustement Rendement
                with col2:
                    st.markdown("**🌾 Ajuster Rendement**")
                    
                    nouveau_rendement = st.number_input(
                        "Nouveau rendement (T/ha)",
                        min_value=0.0,
                        value=float(total['rendement_moyen']),
                        step=1.0,
                        key="nouveau_rendement"
                    )
                    
                    if st.button("✅ Appliquer Rendement", use_container_width=True, key="btn_rendement"):
                        if appliquer_sur == "Certains mois uniquement" and not mois_selectionnes:
                            st.error("❌ Veuillez sélectionner au moins un mois")
                        else:
                            success, message = ajuster_rendement_variete(
                                variete_selected, nouveau_rendement, campagne, mois_selectionnes
                            )
                            
                            if success:
                                st.success(message)
                                st.balloons()
                                time.sleep(2)
                                st.cache_data.clear()
                                st.rerun()
                            else:
                                st.error(message)
            else:
                st.info("🔒 Vous n'avez pas les droits de modification")
        else:
            st.warning("⚠️ Aucune donnée pour cette variété")
    else:
        st.warning("⚠️ Aucune variété disponible")

# ==========================================
# EXPORTS
# ==========================================

st.markdown("---")
st.subheader("📤 Exports")

col1, col2 = st.columns(2)

with col1:
    # Export Excel complet
    if st.button("📥 Export Excel complet", use_container_width=True):
        try:
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                if kpis:
                    pd.DataFrame([kpis]).to_excel(writer, sheet_name='KPIs', index=False)
                
                df_mois = get_recap_par_mois(campagne)
                if not df_mois.empty:
                    df_mois.to_excel(writer, sheet_name='Par Mois', index=False)
                
                df_variete = get_recap_par_variete(campagne)
                if not df_variete.empty:
                    df_variete.to_excel(writer, sheet_name='Par Variété', index=False)
                
                df_marque = get_recap_par_marque(campagne)
                if not df_marque.empty:
                    df_marque.to_excel(writer, sheet_name='Par Marque', index=False)
                
                df_type = get_recap_par_type(campagne)
                if not df_type.empty:
                    df_type.to_excel(writer, sheet_name='Par Type', index=False)
                
                df_besoins = get_besoins_avec_couverture(campagne)
                if not df_besoins.empty:
                    df_besoins.to_excel(writer, sheet_name='Besoins', index=False)
            
            st.download_button(
                "💾 Télécharger Excel",
                buffer.getvalue(),
                f"recaps_plan_recolte_{campagne}.xlsx",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )
        except Exception as e:
            st.error(f"Erreur export : {e}")

with col2:
    # Export besoins CSV
    df_besoins = get_besoins_avec_couverture(campagne)
    if not df_besoins.empty:
        csv = df_besoins.to_csv(index=False).encode('utf-8')
        st.download_button(
            "📥 Besoins CSV",
            csv,
            f"besoins_recolte_{campagne}.csv",
            "text/csv",
            use_container_width=True
        )

show_footer()
