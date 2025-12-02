"""
Page 16 - Suivi Affectations
Vue par producteur : qui a été affecté à quoi, récaps par producteur
VERSION 2.0 - Ajout onglet Producteurs Prioritaires
"""
import streamlit as st
import pandas as pd
from database import get_connection
from components import show_footer
from auth import require_access, can_edit, can_delete, get_current_username
import io

st.set_page_config(page_title="Suivi Affectations - Culture Pom", page_icon="📋", layout="wide")

# CSS - Police agrandie pour hectares
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
    .producteur-card {
        background: linear-gradient(135deg, #e8f5e9 0%, #c8e6c9 100%);
        padding: 1rem;
        border-radius: 0.5rem;
        margin: 0.5rem 0;
        border-left: 4px solid #4CAF50;
    }
    .big-hectares {
        font-size: 2rem !important;
        font-weight: bold !important;
        color: #2E7D32 !important;
    }
    .besoin-label {
        font-size: 1.1rem !important;
        color: #555 !important;
        font-weight: 500 !important;
    }
    .badge-recolte {
        background-color: #4CAF50;
        color: white;
        padding: 0.3rem 0.6rem;
        border-radius: 0.3rem;
        font-size: 0.85rem;
        font-weight: bold;
    }
    .badge-hiver {
        background-color: #2196F3;
        color: white;
        padding: 0.3rem 0.6rem;
        border-radius: 0.3rem;
        font-size: 0.85rem;
        font-weight: bold;
    }
    /* Style pour les indicateurs de couverture */
    .couverture-ok {
        background-color: #4CAF50;
        color: white;
        padding: 0.2rem 0.5rem;
        border-radius: 0.3rem;
        font-weight: bold;
    }
    .couverture-partiel {
        background-color: #FF9800;
        color: white;
        padding: 0.2rem 0.5rem;
        border-radius: 0.3rem;
        font-weight: bold;
    }
    .couverture-faible {
        background-color: #f44336;
        color: white;
        padding: 0.2rem 0.5rem;
        border-radius: 0.3rem;
        font-weight: bold;
    }
    /* Écart positif/négatif */
    .ecart-positif {
        color: #4CAF50;
        font-weight: bold;
    }
    .ecart-negatif {
        color: #f44336;
        font-weight: bold;
    }
</style>
""", unsafe_allow_html=True)

# Vérification authentification et permissions RBAC
require_access("PLANS_RECOLTE")

# Permissions utilisateur
CAN_EDIT = can_edit("PLANS_RECOLTE")
CAN_DELETE = can_delete("PLANS_RECOLTE")

st.title("📋 Suivi Affectations")
st.markdown("*Vue par producteur et récapitulatifs des affectations*")
st.markdown("---")

# ==========================================
# FONCTIONS EXISTANTES - INCHANGÉES
# ==========================================

@st.cache_data(ttl=60)
def get_recap_par_producteur(campagne):
    """Récap affectations par producteur"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                p.id,
                p.code_producteur,
                p.nom,
                p.ville,
                p.departement,
                COUNT(DISTINCT a.variete) as nb_varietes,
                COUNT(a.id) as nb_affectations,
                SUM(a.hectares_affectes) as total_hectares
            FROM plans_recolte_affectations a
            JOIN ref_producteurs p ON a.producteur_id = p.id
            WHERE a.campagne = %s
            GROUP BY p.id, p.code_producteur, p.nom, p.ville, p.departement
            ORDER BY SUM(a.hectares_affectes) DESC
        """, (campagne,))
        
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        
        if rows:
            df = pd.DataFrame(rows)
            df = df.rename(columns={
                'id': 'id',
                'code_producteur': 'Code',
                'nom': 'Producteur',
                'ville': 'Ville',
                'departement': 'Dept',
                'nb_varietes': 'Variétés',
                'nb_affectations': 'Affectations',
                'total_hectares': 'Total Ha'
            })
            for col in ['Variétés', 'Affectations', 'Total Ha']:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
            return df
        return pd.DataFrame()
    except Exception as e:
        st.error(f"Erreur : {e}")
        return pd.DataFrame()


def get_affectations_producteur(campagne, producteur_id):
    """Détail affectations pour un producteur - SANS CACHE pour édition"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                a.id,
                a.besoin_id,
                a.variete,
                a.mois,
                b.mois_numero,
                a.hectares_affectes,
                b.total_hectares_arrondi as ha_besoin_total,
                COALESCE(a.type_contrat, 'RÉCOLTE') as type_contrat,
                a.notes,
                a.created_at
            FROM plans_recolte_affectations a
            LEFT JOIN plans_recolte_besoins b ON a.besoin_id = b.id
            WHERE a.campagne = %s AND a.producteur_id = %s
            ORDER BY b.mois_numero, a.variete
        """, (campagne, producteur_id))
        
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        
        if rows:
            df = pd.DataFrame(rows)
            df = df.rename(columns={
                'id': 'id',
                'besoin_id': 'besoin_id',
                'variete': 'Variété',
                'mois': 'Mois',
                'mois_numero': 'mois_numero',
                'hectares_affectes': 'Hectares',
                'ha_besoin_total': 'Ha Besoin Total',
                'type_contrat': 'Type Contrat',
                'notes': 'Notes',
                'created_at': 'Date'
            })
            for col in ['Hectares', 'Ha Besoin Total']:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
            return df
        return pd.DataFrame()
    except Exception as e:
        st.error(f"Erreur : {e}")
        return pd.DataFrame()


@st.cache_data(ttl=60)
def get_recap_par_variete_producteur(campagne):
    """Tableau croisé Producteur × Variété"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                p.nom as producteur,
                a.variete,
                SUM(a.hectares_affectes) as hectares
            FROM plans_recolte_affectations a
            JOIN ref_producteurs p ON a.producteur_id = p.id
            WHERE a.campagne = %s
            GROUP BY p.nom, a.variete
            ORDER BY p.nom, a.variete
        """, (campagne,))
        
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        
        if rows:
            df = pd.DataFrame(rows)
            df = df.rename(columns={
                'producteur': 'Producteur',
                'variete': 'Variété',
                'hectares': 'Hectares'
            })
            if 'Hectares' in df.columns:
                df['Hectares'] = pd.to_numeric(df['Hectares'], errors='coerce')
            return df
        return pd.DataFrame()
    except Exception as e:
        st.error(f"Erreur : {e}")
        return pd.DataFrame()


@st.cache_data(ttl=60)
def get_recap_par_mois_producteur(campagne):
    """Tableau croisé Producteur × Mois"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                p.nom as producteur,
                a.mois,
                b.mois_numero,
                SUM(a.hectares_affectes) as hectares
            FROM plans_recolte_affectations a
            JOIN ref_producteurs p ON a.producteur_id = p.id
            LEFT JOIN plans_recolte_besoins b ON a.besoin_id = b.id
            WHERE a.campagne = %s
            GROUP BY p.nom, a.mois, b.mois_numero
            ORDER BY p.nom, b.mois_numero
        """, (campagne,))
        
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        
        if rows:
            df = pd.DataFrame(rows)
            df = df.rename(columns={
                'producteur': 'Producteur',
                'mois': 'Mois',
                'mois_numero': 'mois_numero',
                'hectares': 'Hectares'
            })
            for col in ['mois_numero', 'Hectares']:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
            return df
        return pd.DataFrame()
    except Exception as e:
        st.error(f"Erreur : {e}")
        return pd.DataFrame()


@st.cache_data(ttl=60)
def get_kpis_suivi(campagne):
    """KPIs de suivi"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT COUNT(DISTINCT producteur_id) as nb FROM plans_recolte_affectations WHERE campagne = %s
        """, (campagne,))
        nb_producteurs = cursor.fetchone()['nb']
        
        cursor.execute("""
            SELECT COUNT(*) as nb, SUM(hectares_affectes) as total FROM plans_recolte_affectations WHERE campagne = %s
        """, (campagne,))
        row = cursor.fetchone()
        nb_affectations = row['nb']
        total_ha = row['total'] or 0
        
        cursor.execute("""
            SELECT COUNT(DISTINCT variete) as nb FROM plans_recolte_affectations WHERE campagne = %s
        """, (campagne,))
        nb_varietes = cursor.fetchone()['nb']
        
        cursor.execute("""
            SELECT 
                COALESCE(type_contrat, 'RÉCOLTE') as type_contrat,
                SUM(hectares_affectes) as total_ha
            FROM plans_recolte_affectations 
            WHERE campagne = %s
            GROUP BY COALESCE(type_contrat, 'RÉCOLTE')
        """, (campagne,))
        
        ha_recolte = 0
        ha_hiver = 0
        for row in cursor.fetchall():
            if row['type_contrat'] == 'RÉCOLTE':
                ha_recolte = float(row['total_ha'] or 0)
            elif row['type_contrat'] == 'HIVER':
                ha_hiver = float(row['total_ha'] or 0)
        
        moyenne = total_ha / nb_producteurs if nb_producteurs > 0 else 0
        
        cursor.close()
        conn.close()
        
        return {
            'nb_producteurs': nb_producteurs,
            'nb_affectations': nb_affectations,
            'total_ha': float(total_ha),
            'nb_varietes': nb_varietes,
            'moyenne_ha': float(moyenne),
            'ha_recolte': ha_recolte,
            'ha_hiver': ha_hiver
        }
    except:
        return None


def get_producteurs_liste(campagne):
    """Liste producteurs avec affectations"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT DISTINCT p.id, p.nom
            FROM plans_recolte_affectations a
            JOIN ref_producteurs p ON a.producteur_id = p.id
            WHERE a.campagne = %s
            ORDER BY p.nom
        """, (campagne,))
        
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        
        return [(row['id'], row['nom']) for row in rows]
    except:
        return []


def modifier_affectation(affectation_id, hectares, type_contrat, notes):
    """Modifie une affectation"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        username = st.session_state.get('username', 'system')
        
        cursor.execute("""
            UPDATE plans_recolte_affectations 
            SET hectares_affectes = %s, type_contrat = %s, notes = %s, updated_by = %s, updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
        """, (hectares, type_contrat, notes, username, affectation_id))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        st.cache_data.clear()
        
        return True, "✅ Affectation modifiée"
    except Exception as e:
        return False, f"❌ Erreur : {e}"


def supprimer_affectation(affectation_id):
    """Supprime une affectation"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute("DELETE FROM plans_recolte_affectations WHERE id = %s", (affectation_id,))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        st.cache_data.clear()
        
        return True, "✅ Affectation supprimée"
    except Exception as e:
        return False, f"❌ Erreur : {e}"


# ==========================================
# NOUVELLES FONCTIONS - PRODUCTEURS PRIORITAIRES
# ==========================================

def get_producteurs_prioritaires(campagne):
    """Récupère les producteurs prioritaires avec leurs objectifs et affectations"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                po.id as objectif_id,
                po.producteur_id,
                p.code_producteur,
                p.nom as producteur_nom,
                p.ville,
                p.departement,
                po.hectares_souhaites,
                po.notes as objectif_notes,
                COALESCE(SUM(a.hectares_affectes), 0) as hectares_affectes
            FROM producteurs_objectifs po
            JOIN ref_producteurs p ON po.producteur_id = p.id
            LEFT JOIN plans_recolte_affectations a ON a.producteur_id = p.id AND a.campagne = po.campagne
            WHERE po.campagne = %s AND po.is_prioritaire = TRUE
            GROUP BY po.id, po.producteur_id, p.code_producteur, p.nom, p.ville, p.departement, 
                     po.hectares_souhaites, po.notes
            ORDER BY po.hectares_souhaites DESC
        """, (campagne,))
        
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        
        if rows:
            df = pd.DataFrame(rows)
            # Calculs dérivés
            df['hectares_souhaites'] = pd.to_numeric(df['hectares_souhaites'], errors='coerce').fillna(0)
            df['hectares_affectes'] = pd.to_numeric(df['hectares_affectes'], errors='coerce').fillna(0)
            df['ecart'] = df['hectares_affectes'] - df['hectares_souhaites']
            df['taux_couverture'] = (df['hectares_affectes'] / df['hectares_souhaites'] * 100).round(1)
            df['taux_couverture'] = df['taux_couverture'].fillna(0)
            return df
        return pd.DataFrame()
    except Exception as e:
        st.error(f"Erreur chargement prioritaires : {e}")
        return pd.DataFrame()


def get_detail_varietes_producteur(campagne, producteur_id):
    """Détail des hectares par variété pour un producteur"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                variete,
                SUM(hectares_affectes) as hectares
            FROM plans_recolte_affectations
            WHERE campagne = %s AND producteur_id = %s
            GROUP BY variete
            ORDER BY SUM(hectares_affectes) DESC
        """, (campagne, producteur_id))
        
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        
        if rows:
            df = pd.DataFrame(rows)
            df['hectares'] = pd.to_numeric(df['hectares'], errors='coerce')
            return df
        return pd.DataFrame()
    except:
        return pd.DataFrame()


def get_kpis_prioritaires(campagne):
    """KPIs spécifiques aux producteurs prioritaires"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                COUNT(po.id) as nb_prioritaires,
                COALESCE(SUM(po.hectares_souhaites), 0) as total_souhaites,
                COALESCE(SUM(aff.ha_affectes), 0) as total_affectes
            FROM producteurs_objectifs po
            LEFT JOIN (
                SELECT producteur_id, SUM(hectares_affectes) as ha_affectes
                FROM plans_recolte_affectations
                WHERE campagne = %s
                GROUP BY producteur_id
            ) aff ON aff.producteur_id = po.producteur_id
            WHERE po.campagne = %s AND po.is_prioritaire = TRUE
        """, (campagne, campagne))
        
        row = cursor.fetchone()
        
        # Ha affectés aux NON prioritaires
        cursor.execute("""
            SELECT COALESCE(SUM(a.hectares_affectes), 0) as ha_autres
            FROM plans_recolte_affectations a
            WHERE a.campagne = %s
              AND a.producteur_id NOT IN (
                  SELECT producteur_id FROM producteurs_objectifs 
                  WHERE campagne = %s AND is_prioritaire = TRUE
              )
        """, (campagne, campagne))
        
        ha_autres = cursor.fetchone()['ha_autres'] or 0
        
        cursor.close()
        conn.close()
        
        total_souhaites = float(row['total_souhaites'] or 0)
        total_affectes = float(row['total_affectes'] or 0)
        taux = (total_affectes / total_souhaites * 100) if total_souhaites > 0 else 0
        
        return {
            'nb_prioritaires': row['nb_prioritaires'] or 0,
            'total_souhaites': total_souhaites,
            'total_affectes': total_affectes,
            'taux_global': taux,
            'ecart_global': total_affectes - total_souhaites,
            'ha_autres': float(ha_autres)
        }
    except Exception as e:
        st.error(f"Erreur KPIs prioritaires : {e}")
        return None


def get_tous_producteurs():
    """Liste tous les producteurs pour sélection"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, code_producteur, nom, ville
            FROM ref_producteurs
            WHERE is_active = TRUE
            ORDER BY nom
        """)
        
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        
        return rows if rows else []
    except:
        return []


def ajouter_producteur_prioritaire(producteur_id, campagne, hectares_souhaites, notes=""):
    """Ajoute un producteur prioritaire"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        username = st.session_state.get('username', 'system')
        
        cursor.execute("""
            INSERT INTO producteurs_objectifs 
                (producteur_id, campagne, hectares_souhaites, is_prioritaire, notes, created_by)
            VALUES (%s, %s, %s, TRUE, %s, %s)
            ON CONFLICT (producteur_id, campagne) 
            DO UPDATE SET 
                hectares_souhaites = EXCLUDED.hectares_souhaites,
                is_prioritaire = TRUE,
                notes = EXCLUDED.notes,
                updated_by = EXCLUDED.created_by,
                updated_at = CURRENT_TIMESTAMP
        """, (producteur_id, campagne, hectares_souhaites, notes, username))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        st.cache_data.clear()
        return True, "✅ Producteur prioritaire ajouté"
    except Exception as e:
        return False, f"❌ Erreur : {e}"


def modifier_objectif_prioritaire(objectif_id, hectares_souhaites, notes):
    """Modifie les hectares souhaités d'un producteur prioritaire"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        username = st.session_state.get('username', 'system')
        
        cursor.execute("""
            UPDATE producteurs_objectifs 
            SET hectares_souhaites = %s, notes = %s, updated_by = %s, updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
        """, (hectares_souhaites, notes, username, objectif_id))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        st.cache_data.clear()
        return True, "✅ Objectif modifié"
    except Exception as e:
        return False, f"❌ Erreur : {e}"


def supprimer_producteur_prioritaire(objectif_id):
    """Retire un producteur de la liste prioritaire"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute("DELETE FROM producteurs_objectifs WHERE id = %s", (objectif_id,))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        st.cache_data.clear()
        return True, "✅ Producteur retiré des prioritaires"
    except Exception as e:
        return False, f"❌ Erreur : {e}"


# ==========================================
# SÉLECTEUR CAMPAGNE + KPIs
# ==========================================

col1, col2 = st.columns([1, 4])
with col1:
    campagne = st.selectbox("Campagne", [2026, 2025, 2027], index=0, key="campagne_suivi")

with col2:
    if st.button("🔄 Rafraîchir", key="btn_refresh_16"):
        st.cache_data.clear()
        st.rerun()

# KPIs généraux
kpis = get_kpis_suivi(campagne)

if kpis:
    col1, col2, col3, col4, col5 = st.columns(5)
    
    with col1:
        st.metric("👨‍🌾 Producteurs", kpis['nb_producteurs'])
    
    with col2:
        st.metric("📝 Affectations", kpis['nb_affectations'])
    
    with col3:
        st.metric("🌾 Total Ha", f"{kpis['total_ha']:,.1f}")
    
    with col4:
        st.metric("🌱 Variétés", kpis['nb_varietes'])
    
    with col5:
        st.metric("📊 Moy./Prod.", f"{kpis['moyenne_ha']:.1f} ha")

st.markdown("---")

# ==========================================
# ONGLETS - AJOUT PRIORITAIRES
# ==========================================

if 'onglet_actif_16' not in st.session_state:
    st.session_state.onglet_actif_16 = "⭐ Prioritaires"

onglet_selectionne = st.radio(
    "Navigation",
    options=[
        "⭐ Prioritaires",
        "👨‍🌾 Par Producteur",
        "🌱 Producteur × Variété",
        "📅 Producteur × Mois",
        "📋 Détail Producteur"
    ],
    index=[
        "⭐ Prioritaires",
        "👨‍🌾 Par Producteur",
        "🌱 Producteur × Variété",
        "📅 Producteur × Mois",
        "📋 Détail Producteur"
    ].index(st.session_state.onglet_actif_16) if st.session_state.onglet_actif_16 in [
        "⭐ Prioritaires",
        "👨‍🌾 Par Producteur",
        "🌱 Producteur × Variété",
        "📅 Producteur × Mois",
        "📋 Détail Producteur"
    ] else 0,
    horizontal=True,
    key="nav_onglets_16",
    label_visibility="collapsed"
)

st.session_state.onglet_actif_16 = onglet_selectionne

st.markdown("---")

# ==========================================
# TAB 0 : PRODUCTEURS PRIORITAIRES (NOUVEAU)
# ==========================================

if onglet_selectionne == "⭐ Prioritaires":
    st.subheader("⭐ Producteurs Prioritaires")
    st.markdown("*Suivi des producteurs prioritaires et de leurs objectifs*")
    
    # KPIs Prioritaires
    kpis_prio = get_kpis_prioritaires(campagne)
    
    if kpis_prio:
        col1, col2, col3, col4, col5 = st.columns(5)
        
        with col1:
            st.metric("⭐ Prioritaires", kpis_prio['nb_prioritaires'])
        
        with col2:
            st.metric("🎯 Ha Souhaités", f"{kpis_prio['total_souhaites']:,.1f}")
        
        with col3:
            st.metric("✅ Ha Affectés", f"{kpis_prio['total_affectes']:,.1f}")
        
        with col4:
            # Couleur selon taux
            taux = kpis_prio['taux_global']
            if taux >= 80:
                delta_color = "normal"
            elif taux >= 50:
                delta_color = "off"
            else:
                delta_color = "inverse"
            st.metric("📊 Taux Couverture", f"{taux:.0f}%")
        
        with col5:
            ecart = kpis_prio['ecart_global']
            st.metric("📉 Écart Global", f"{ecart:+,.1f} ha")
    
    # Info autres producteurs
    if kpis_prio and kpis_prio['ha_autres'] > 0:
        st.info(f"📌 **Autres producteurs (non prioritaires)** : {kpis_prio['ha_autres']:,.1f} ha affectés")
    
    st.markdown("---")
    
    # Tableau producteurs prioritaires
    df_prio = get_producteurs_prioritaires(campagne)
    
    if not df_prio.empty:
        st.markdown(f"### 📋 {len(df_prio)} Producteur(s) Prioritaire(s)")
        
        for _, row in df_prio.iterrows():
            # Calculer couleur badge
            taux = row['taux_couverture']
            if taux >= 80:
                badge_class = "couverture-ok"
                badge_text = f"✅ {taux:.0f}%"
            elif taux >= 50:
                badge_class = "couverture-partiel"
                badge_text = f"⚠️ {taux:.0f}%"
            else:
                badge_class = "couverture-faible"
                badge_text = f"❌ {taux:.0f}%"
            
            # Écart
            ecart = row['ecart']
            if ecart >= 0:
                ecart_class = "ecart-positif"
                ecart_text = f"+{ecart:.1f} ha"
            else:
                ecart_class = "ecart-negatif"
                ecart_text = f"{ecart:.1f} ha"
            
            # Expander pour chaque producteur
            with st.expander(
                f"**{row['producteur_nom']}** ({row['code_producteur']}) — "
                f"🎯 {row['hectares_souhaites']:.1f} ha souhaités | "
                f"✅ {row['hectares_affectes']:.1f} ha affectés | "
                f"{badge_text}"
            ):
                col1, col2, col3 = st.columns([2, 2, 1])
                
                with col1:
                    st.markdown(f"**Localisation** : {row['ville'] or ''} ({row['departement'] or ''})")
                    st.markdown(f"**Écart** : <span class='{ecart_class}'>{ecart_text}</span>", unsafe_allow_html=True)
                    if row['objectif_notes']:
                        st.markdown(f"**Notes** : {row['objectif_notes']}")
                
                with col2:
                    # Détail par variété
                    st.markdown("**Répartition par variété :**")
                    df_var = get_detail_varietes_producteur(campagne, row['producteur_id'])
                    if not df_var.empty:
                        for _, var_row in df_var.iterrows():
                            st.markdown(f"• {var_row['variete']} : **{var_row['hectares']:.1f} ha**")
                    else:
                        st.caption("Aucune affectation")
                
                with col3:
                    if CAN_EDIT:
                        if st.button("✏️ Modifier", key=f"edit_prio_{row['objectif_id']}"):
                            st.session_state[f'editing_prio_{row["objectif_id"]}'] = True
                            st.rerun()
                    
                    if CAN_DELETE:
                        if st.button("🗑️ Retirer", key=f"del_prio_{row['objectif_id']}"):
                            success, msg = supprimer_producteur_prioritaire(row['objectif_id'])
                            if success:
                                st.success(msg)
                                st.rerun()
                            else:
                                st.error(msg)
                
                # Formulaire modification si actif
                if st.session_state.get(f'editing_prio_{row["objectif_id"]}', False):
                    st.markdown("---")
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        new_ha = st.number_input(
                            "Hectares souhaités",
                            min_value=0.5,
                            value=float(row['hectares_souhaites']),
                            step=0.5,
                            key=f"edit_prio_ha_{row['objectif_id']}"
                        )
                    
                    with col2:
                        new_notes = st.text_input(
                            "Notes",
                            value=row['objectif_notes'] or "",
                            key=f"edit_prio_notes_{row['objectif_id']}"
                        )
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        if st.button("💾 Enregistrer", key=f"save_prio_{row['objectif_id']}", type="primary"):
                            success, msg = modifier_objectif_prioritaire(row['objectif_id'], new_ha, new_notes)
                            if success:
                                st.success(msg)
                                st.session_state.pop(f'editing_prio_{row["objectif_id"]}', None)
                                st.rerun()
                            else:
                                st.error(msg)
                    
                    with col2:
                        if st.button("❌ Annuler", key=f"cancel_prio_{row['objectif_id']}"):
                            st.session_state.pop(f'editing_prio_{row["objectif_id"]}', None)
                            st.rerun()
    else:
        st.info("Aucun producteur prioritaire défini pour cette campagne.")
    
    # ==========================================
    # SECTION AJOUT PRODUCTEUR PRIORITAIRE
    # ==========================================
    
    st.markdown("---")
    
    with st.expander("➕ Ajouter un producteur prioritaire", expanded=False):
        # Récupérer producteurs non encore prioritaires
        tous_producteurs = get_tous_producteurs()
        
        # IDs déjà prioritaires
        ids_prioritaires = set(df_prio['producteur_id'].tolist()) if not df_prio.empty else set()
        
        # Filtrer
        producteurs_dispo = [p for p in tous_producteurs if p['id'] not in ids_prioritaires]
        
        if producteurs_dispo:
            col1, col2 = st.columns(2)
            
            with col1:
                # Dropdown producteur
                options_prod = [""] + [f"{p['nom']} ({p['code_producteur']}) - {p['ville'] or ''}" for p in producteurs_dispo]
                selected_prod = st.selectbox("Producteur", options_prod, key="add_prio_prod")
            
            with col2:
                ha_souhaites = st.number_input(
                    "Hectares souhaités *",
                    min_value=0.5,
                    value=10.0,
                    step=0.5,
                    key="add_prio_ha"
                )
            
            notes_prio = st.text_input("Notes (optionnel)", key="add_prio_notes")
            
            if st.button("➕ Ajouter aux prioritaires", type="primary", key="btn_add_prio"):
                if not selected_prod:
                    st.error("❌ Veuillez sélectionner un producteur")
                else:
                    # Trouver l'ID
                    idx = options_prod.index(selected_prod) - 1
                    prod_id = producteurs_dispo[idx]['id']
                    
                    success, msg = ajouter_producteur_prioritaire(prod_id, campagne, ha_souhaites, notes_prio)
                    if success:
                        st.success(msg)
                        st.balloons()
                        st.rerun()
                    else:
                        st.error(msg)
        else:
            st.info("Tous les producteurs sont déjà dans la liste prioritaire.")


# ==========================================
# TAB 1 : RÉCAP PAR PRODUCTEUR
# ==========================================

elif onglet_selectionne == "👨‍🌾 Par Producteur":
    st.subheader("👨‍🌾 Récap par Producteur")
    
    df_prod = get_recap_par_producteur(campagne)
    
    if not df_prod.empty:
        df_display = df_prod.drop(columns=['id'])
        
        st.dataframe(
            df_display,
            column_config={
                "Code": st.column_config.TextColumn("Code", width="small"),
                "Producteur": st.column_config.TextColumn("Producteur", width="large"),
                "Ville": st.column_config.TextColumn("Ville", width="medium"),
                "Dept": st.column_config.TextColumn("Dept", width="small"),
                "Variétés": st.column_config.NumberColumn("Variétés", format="%d"),
                "Affectations": st.column_config.NumberColumn("Affectations", format="%d"),
                "Total Ha": st.column_config.NumberColumn("Total Ha", format="%.1f"),
            },
            use_container_width=True,
            hide_index=True
        )
        
        st.markdown(f"""
        **Totaux :** {len(df_prod)} producteurs | 
        {df_prod['Affectations'].sum()} affectations | 
        {df_prod['Total Ha'].sum():,.1f} ha
        """)
        
        st.markdown("#### 🏆 Top 10 Producteurs (hectares)")
        top10 = df_prod.head(10)[['Producteur', 'Total Ha']].set_index('Producteur')
        st.bar_chart(top10)
    else:
        st.info("Aucune affectation pour cette campagne")


# ==========================================
# TAB 2 : PRODUCTEUR × VARIÉTÉ
# ==========================================

elif onglet_selectionne == "🌱 Producteur × Variété":
    st.subheader("🌱 Tableau Croisé Producteur × Variété")
    
    df_cross = get_recap_par_variete_producteur(campagne)
    
    if not df_cross.empty:
        pivot = df_cross.pivot_table(
            index='Producteur', 
            columns='Variété', 
            values='Hectares',
            aggfunc='sum',
            fill_value=0
        )
        
        pivot['TOTAL'] = pivot.sum(axis=1)
        pivot = pivot.sort_values('TOTAL', ascending=False)
        
        st.dataframe(
            pivot.style.format("{:.1f}").background_gradient(cmap='Greens', axis=None),
            use_container_width=True
        )
        
        st.markdown(f"**{len(pivot)} producteurs** | **{len(pivot.columns)-1} variétés**")
    else:
        st.info("Aucune donnée")


# ==========================================
# TAB 3 : PRODUCTEUR × MOIS
# ==========================================

elif onglet_selectionne == "📅 Producteur × Mois":
    st.subheader("📅 Tableau Croisé Producteur × Mois")
    
    df_mois = get_recap_par_mois_producteur(campagne)
    
    if not df_mois.empty:
        pivot = df_mois.pivot_table(
            index='Producteur',
            columns='Mois',
            values='Hectares',
            aggfunc='sum',
            fill_value=0
        )
        
        pivot['TOTAL'] = pivot.sum(axis=1)
        pivot = pivot.sort_values('TOTAL', ascending=False)
        
        st.dataframe(
            pivot.style.format("{:.1f}").background_gradient(cmap='Blues', axis=None),
            use_container_width=True
        )
    else:
        st.info("Aucune donnée")


# ==========================================
# TAB 4 : DÉTAIL PRODUCTEUR
# ==========================================

elif onglet_selectionne == "📋 Détail Producteur":
    st.subheader("📋 Détail par Producteur")
    
    producteurs = get_producteurs_liste(campagne)
    
    if producteurs:
        options = [f"{nom} (ID:{id})" for id, nom in producteurs]
        selected = st.selectbox("Sélectionner un producteur", options, key="select_prod_detail")
        
        if selected:
            producteur_id = int(selected.split("ID:")[1].replace(")", ""))
            producteur_nom = selected.split(" (ID:")[0]
            
            df_detail = get_affectations_producteur(campagne, producteur_id)
            
            if not df_detail.empty:
                total_ha = df_detail['Hectares'].sum()
                st.markdown(f"### {producteur_nom}")
                st.metric("Total Hectares", f"{total_ha:.1f} ha")
                
                st.markdown("#### 📝 Affectations")
                
                for idx, row in df_detail.iterrows():
                    col1, col2, col3, col4, col5, col6 = st.columns([1, 2.5, 1.2, 1.3, 0.5, 0.5])
                    
                    with col1:
                        if row['Type Contrat'] == 'HIVER':
                            st.markdown(f'<span class="badge-hiver">❄️ HIVER</span>', unsafe_allow_html=True)
                        else:
                            st.markdown(f'<span class="badge-recolte">🌾 RÉCOLTE</span>', unsafe_allow_html=True)
                    
                    with col2:
                        st.markdown(f"**{row['Variété']}** - {row['Mois']}")
                        if row['Notes']:
                            st.caption(f"📝 {row['Notes']}")
                    
                    with col3:
                        st.markdown(f'<span class="big-hectares">{row["Hectares"]:.1f}</span>', unsafe_allow_html=True)
                    
                    with col4:
                        if row['Ha Besoin Total']:
                            st.markdown(f'<span class="besoin-label">Besoin: <b>{row["Ha Besoin Total"]:.1f}</b> ha</span>', unsafe_allow_html=True)
                    
                    with col5:
                        if CAN_EDIT:
                            if st.button("✏️", key=f"edit16_{row['id']}", help="Modifier"):
                                st.session_state[f'editing16_{row["id"]}'] = True
                                st.session_state.onglet_actif_16 = "📋 Détail Producteur"
                                st.rerun()
                    
                    with col6:
                        if CAN_DELETE:
                            if st.button("🗑️", key=f"del16_{row['id']}", help="Supprimer"):
                                success, msg = supprimer_affectation(row['id'])
                                if success:
                                    st.success(msg)
                                    st.session_state.onglet_actif_16 = "📋 Détail Producteur"
                                    st.rerun()
                                else:
                                    st.error(msg)
                    
                    # Formulaire modification
                    if st.session_state.get(f'editing16_{row["id"]}', False):
                        with st.container():
                            st.markdown("---")
                            col1, col2, col3 = st.columns(3)
                            
                            with col1:
                                new_ha = st.number_input(
                                    "Hectares",
                                    min_value=0.5,
                                    value=float(row['Hectares']),
                                    step=0.5,
                                    format="%.1f",
                                    key=f"edit16_ha_{row['id']}"
                                )
                            
                            with col2:
                                type_options = ['RÉCOLTE', 'HIVER']
                                current_type = row['Type Contrat'] if row['Type Contrat'] in type_options else 'RÉCOLTE'
                                new_type = st.selectbox(
                                    "Type Contrat",
                                    options=type_options,
                                    index=type_options.index(current_type),
                                    key=f"edit16_type_{row['id']}"
                                )
                            
                            with col3:
                                new_notes = st.text_input(
                                    "Notes",
                                    value=row['Notes'] or "",
                                    key=f"edit16_notes_{row['id']}"
                                )
                            
                            col1, col2 = st.columns(2)
                            
                            with col1:
                                if st.button("💾 Enregistrer", key=f"save16_edit_{row['id']}", type="primary"):
                                    success, msg = modifier_affectation(row['id'], new_ha, new_type, new_notes)
                                    if success:
                                        st.success(msg)
                                        st.session_state.pop(f'editing16_{row["id"]}', None)
                                        st.session_state.onglet_actif_16 = "📋 Détail Producteur"
                                        st.rerun()
                                    else:
                                        st.error(msg)
                            
                            with col2:
                                if st.button("❌ Annuler", key=f"cancel16_edit_{row['id']}"):
                                    st.session_state.pop(f'editing16_{row["id"]}', None)
                                    st.session_state.onglet_actif_16 = "📋 Détail Producteur"
                                    st.rerun()
                            
                            st.markdown("---")
                    
                    st.markdown("<hr style='margin: 0.3rem 0; border: none; border-top: 1px solid #eee;'>", unsafe_allow_html=True)
                
                # Récap par variété
                st.markdown("#### 🌱 Récap par Variété")
                recap_var = df_detail.groupby('Variété')['Hectares'].sum().reset_index()
                recap_var = recap_var.sort_values('Hectares', ascending=False)
                st.bar_chart(recap_var.set_index('Variété'))
                
                # Récap par type contrat
                st.markdown("#### 📊 Récap par Type Contrat")
                recap_type = df_detail.groupby('Type Contrat')['Hectares'].sum().reset_index()
                
                col1, col2 = st.columns(2)
                with col1:
                    st.bar_chart(recap_type.set_index('Type Contrat'))
                with col2:
                    st.dataframe(recap_type, hide_index=True)
            else:
                st.info(f"Aucune affectation pour {producteur_nom}")
    else:
        st.info("Aucun producteur avec affectations pour cette campagne")


# ==========================================
# EXPORTS
# ==========================================

st.markdown("---")
st.subheader("📤 Exports")

col1, col2, col3 = st.columns(3)

with col1:
    if st.button("📥 Export Excel complet", use_container_width=True, key="btn_export_excel"):
        try:
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                # Prioritaires
                df_prio = get_producteurs_prioritaires(campagne)
                if not df_prio.empty:
                    df_prio.to_excel(writer, sheet_name='Prioritaires', index=False)
                
                # Par producteur
                df_prod = get_recap_par_producteur(campagne)
                if not df_prod.empty:
                    df_prod.to_excel(writer, sheet_name='Par Producteur', index=False)
                
                # Croisé
                df_cross = get_recap_par_variete_producteur(campagne)
                if not df_cross.empty:
                    pivot = df_cross.pivot_table(
                        index='Producteur', columns='Variété', values='Hectares',
                        aggfunc='sum', fill_value=0
                    )
                    pivot.to_excel(writer, sheet_name='Producteur x Variété')
            
            st.download_button(
                "💾 Télécharger Excel",
                buffer.getvalue(),
                f"suivi_affectations_{campagne}.xlsx",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
                key="dl_excel"
            )
        except Exception as e:
            st.error(f"Erreur export : {e}")

with col2:
    df_prod = get_recap_par_producteur(campagne)
    if not df_prod.empty:
        csv = df_prod.to_csv(index=False).encode('utf-8')
        st.download_button(
            "📥 Producteurs CSV",
            csv,
            f"producteurs_affectations_{campagne}.csv",
            "text/csv",
            use_container_width=True,
            key="dl_csv"
        )

with col3:
    st.markdown("""
    <a href="/Affectation_Producteurs" target="_self">
        <button style="width:100%; padding:0.5rem; cursor:pointer;">
            ⬅️ Retour Affectations
        </button>
    </a>
    """, unsafe_allow_html=True)

show_footer()
