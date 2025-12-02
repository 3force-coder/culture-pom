import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from database import get_connection
from components import show_footer
from auth import require_access

# ============================================================
# CSS CUSTOM
# ============================================================
st.markdown("""
<style>
    .block-container {
        padding-top: 1rem !important;
        padding-bottom: 0.5rem !important;
    }
    h1, h2, h3, h4 {
        margin-top: 0.3rem !important;
        margin-bottom: 0.3rem !important;
    }
    .success-box {
        background: linear-gradient(135deg, #c8e6c9 0%, #a5d6a7 100%);
        border-left: 4px solid #388e3c;
        padding: 1.5rem;
        border-radius: 10px;
        text-align: center;
        margin: 2rem 0;
    }
    .warning-box {
        background: linear-gradient(135deg, #fff3e0 0%, #ffcc80 100%);
        border-left: 4px solid #f57c00;
        padding: 1rem;
        border-radius: 8px;
        margin: 1rem 0;
    }
    .info-box {
        background: linear-gradient(135deg, #e3f2fd 0%, #bbdefb 100%);
        border-left: 4px solid #1976d2;
        padding: 1rem;
        border-radius: 8px;
        margin: 1rem 0;
    }
    .history-item {
        background: #fafafa;
        border-left: 3px solid #9e9e9e;
        padding: 0.8rem;
        margin: 0.5rem 0;
        border-radius: 4px;
        font-size: 0.9rem;
    }
    .history-item.creation {
        border-left-color: #4caf50;
    }
    .history-item.modification {
        border-left-color: #ff9800;
    }
</style>
""", unsafe_allow_html=True)

# ============================================================
# 🔒 CONTRÔLE D'ACCÈS RBAC (Admin uniquement)
# ============================================================
require_access("FINANCE")
# ============================================================

st.title("💰 Valorisation des Lots")
st.caption("*Qualification des lots : prix d'achat et tare*")
st.markdown("---")

# ============================================================
# FONCTIONS UTILITAIRES
# ============================================================

def get_lots_non_qualifies(filtre_nom=None, filtre_variete=None, filtre_producteur=None):
    """Récupère les lots sans prix OU sans tare"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        query = """
        SELECT 
            l.id,
            l.code_lot_interne,
            l.nom_usage,
            l.code_producteur,
            COALESCE(p.nom, l.code_producteur) as producteur_nom,
            l.code_variete,
            COALESCE(v.nom_variete, l.code_variete) as variete_nom,
            l.calibre_min,
            l.calibre_max,
            l.date_entree_stock,
            l.poids_total_brut_kg,
            l.prix_achat_euro_tonne,
            l.tare_achat_pct,
            l.valeur_lot_euro
        FROM lots_bruts l
        LEFT JOIN ref_producteurs p ON l.code_producteur = p.code_producteur
        LEFT JOIN ref_varietes v ON l.code_variete = v.code_variete
        WHERE l.is_active = TRUE
          AND (l.prix_achat_euro_tonne IS NULL 
               OR l.prix_achat_euro_tonne = 0
               OR l.tare_achat_pct IS NULL
               OR l.tare_achat_pct = 0)
        """
        
        conditions = []
        params = []
        
        if filtre_nom:
            conditions.append("l.nom_usage ILIKE %s")
            params.append(f"%{filtre_nom}%")
        
        if filtre_variete and filtre_variete != "Tous":
            conditions.append("COALESCE(v.nom_variete, l.code_variete) = %s")
            params.append(filtre_variete)
        
        if filtre_producteur and filtre_producteur != "Tous":
            conditions.append("COALESCE(p.nom, l.code_producteur) = %s")
            params.append(filtre_producteur)
        
        if conditions:
            query += " AND " + " AND ".join(conditions)
        
        query += " ORDER BY l.date_entree_stock DESC"
        
        cursor.execute(query, params if params else None)
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        
        if rows:
            df = pd.DataFrame(rows)
            numeric_cols = ['poids_total_brut_kg', 'prix_achat_euro_tonne', 'tare_achat_pct', 'valeur_lot_euro', 'calibre_min', 'calibre_max']
            for col in numeric_cols:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
            return df
        return pd.DataFrame()
        
    except Exception as e:
        st.error(f"❌ Erreur : {str(e)}")
        return pd.DataFrame()

def get_lots_qualifies(filtre_nom=None, filtre_variete=None, filtre_producteur=None):
    """Récupère les lots avec prix ET tare"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        query = """
        SELECT 
            l.id,
            l.code_lot_interne,
            l.nom_usage,
            l.code_producteur,
            COALESCE(p.nom, l.code_producteur) as producteur_nom,
            l.code_variete,
            COALESCE(v.nom_variete, l.code_variete) as variete_nom,
            l.calibre_min,
            l.calibre_max,
            l.date_entree_stock,
            l.poids_total_brut_kg,
            l.prix_achat_euro_tonne,
            l.tare_achat_pct,
            l.valeur_lot_euro,
            l.created_at,
            l.updated_at
        FROM lots_bruts l
        LEFT JOIN ref_producteurs p ON l.code_producteur = p.code_producteur
        LEFT JOIN ref_varietes v ON l.code_variete = v.code_variete
        WHERE l.is_active = TRUE
          AND l.prix_achat_euro_tonne IS NOT NULL 
          AND l.prix_achat_euro_tonne > 0
          AND l.tare_achat_pct IS NOT NULL
          AND l.tare_achat_pct > 0
        """
        
        conditions = []
        params = []
        
        if filtre_nom:
            conditions.append("l.nom_usage ILIKE %s")
            params.append(f"%{filtre_nom}%")
        
        if filtre_variete and filtre_variete != "Tous":
            conditions.append("COALESCE(v.nom_variete, l.code_variete) = %s")
            params.append(filtre_variete)
        
        if filtre_producteur and filtre_producteur != "Tous":
            conditions.append("COALESCE(p.nom, l.code_producteur) = %s")
            params.append(filtre_producteur)
        
        if conditions:
            query += " AND " + " AND ".join(conditions)
        
        query += " ORDER BY l.date_entree_stock DESC"
        
        cursor.execute(query, params if params else None)
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        
        if rows:
            df = pd.DataFrame(rows)
            numeric_cols = ['poids_total_brut_kg', 'prix_achat_euro_tonne', 'tare_achat_pct', 'valeur_lot_euro', 'calibre_min', 'calibre_max']
            for col in numeric_cols:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
            return df
        return pd.DataFrame()
        
    except Exception as e:
        st.error(f"❌ Erreur : {str(e)}")
        return pd.DataFrame()

def update_lot_valorisation(lot_id, prix_achat, tare_achat):
    """Met à jour le prix et la tare d'un lot"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Récupérer poids brut
        cursor.execute("SELECT poids_total_brut_kg FROM lots_bruts WHERE id = %s", (lot_id,))
        result = cursor.fetchone()
        
        if not result:
            return False, "❌ Lot introuvable"
        
        poids_brut = float(result['poids_total_brut_kg'])
        
        # Calculer valeur lot
        poids_net_paye = poids_brut * (1 - tare_achat / 100)
        valeur_lot = (poids_net_paye / 1000) * prix_achat
        
        # Update
        cursor.execute("""
            UPDATE lots_bruts
            SET prix_achat_euro_tonne = %s,
                tare_achat_pct = %s,
                valeur_lot_euro = %s,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
        """, (prix_achat, tare_achat, valeur_lot, lot_id))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return True, "✅ Lot mis à jour"
        
    except Exception as e:
        if 'conn' in locals():
            conn.rollback()
        return False, f"❌ Erreur : {str(e)}"

def get_recap_valorisation_global():
    """Récap valorisation global de tous les lots qualifiés"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Lots qualifiés (prix + tare achat)
        cursor.execute("""
            SELECT 
                COUNT(*) as nb_lots,
                SUM(poids_total_brut_kg) as poids_brut_total,
                AVG(tare_achat_pct) as tare_achat_moy,
                SUM(valeur_lot_euro) as valeur_totale
            FROM lots_bruts
            WHERE is_active = TRUE
              AND prix_achat_euro_tonne IS NOT NULL
              AND prix_achat_euro_tonne > 0
              AND tare_achat_pct IS NOT NULL
              AND tare_achat_pct > 0
        """)
        
        result = cursor.fetchone()
        
        if not result or result['nb_lots'] == 0:
            cursor.close()
            conn.close()
            return None
        
        nb_lots = int(result['nb_lots'])
        poids_brut_total = float(result['poids_brut_total']) / 1000  # Tonnes
        tare_achat_moy = float(result['tare_achat_moy'])
        valeur_totale = float(result['valeur_totale'])
        
        # Poids net payé (ce qu'on a payé au producteur)
        poids_net_paye = poids_brut_total * (1 - tare_achat_moy / 100)
        
        # Tare production moyenne réelle (jobs lavage terminés)
        cursor.execute("""
            SELECT AVG(tare_reelle_pct) as tare_prod_moy
            FROM lavages_jobs
            WHERE statut = 'TERMINÉ'
              AND tare_reelle_pct IS NOT NULL
        """)
        
        tare_prod_result = cursor.fetchone()
        
        if tare_prod_result and tare_prod_result['tare_prod_moy']:
            tare_prod_moy = float(tare_prod_result['tare_prod_moy'])
            tare_prod_source = "✅ Mesurée"
        else:
            tare_prod_moy = 22.0  # Standard
            tare_prod_source = "📊 Standard"
        
        # Poids net production (matière première disponible)
        poids_net_production = poids_brut_total * (1 - tare_prod_moy / 100)
        
        # Écarts
        perte_production = poids_net_paye - poids_net_production
        pct_perte = (perte_production / poids_net_paye * 100) if poids_net_paye > 0 else 0
        
        # Valeur MP réelle
        prix_achat_moyen = valeur_totale / poids_net_paye if poids_net_paye > 0 else 0
        valeur_mp_reelle = poids_net_production * prix_achat_moyen
        
        cursor.close()
        conn.close()
        
        return {
            'nb_lots': nb_lots,
            'poids_brut_total': poids_brut_total,
            'tare_achat_moy': tare_achat_moy,
            'poids_net_paye': poids_net_paye,
            'valeur_totale': valeur_totale,
            'tare_prod_moy': tare_prod_moy,
            'tare_prod_source': tare_prod_source,
            'poids_net_production': poids_net_production,
            'perte_production': perte_production,
            'pct_perte': pct_perte,
            'valeur_mp_reelle': valeur_mp_reelle
        }
        
    except Exception as e:
        st.error(f"❌ Erreur : {str(e)}")
        return None

def get_details_lots_qualifies():
    """Détails valorisation de chaque lot qualifié"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                l.id,
                l.code_lot_interne,
                l.nom_usage,
                COALESCE(v.nom_variete, l.code_variete) as variete,
                COALESCE(p.nom, l.code_producteur) as producteur,
                l.poids_total_brut_kg,
                l.prix_achat_euro_tonne,
                l.tare_achat_pct,
                l.valeur_lot_euro,
                l.date_entree_stock
            FROM lots_bruts l
            LEFT JOIN ref_varietes v ON l.code_variete = v.code_variete
            LEFT JOIN ref_producteurs p ON l.code_producteur = p.code_producteur
            WHERE l.is_active = TRUE
              AND l.prix_achat_euro_tonne IS NOT NULL
              AND l.prix_achat_euro_tonne > 0
              AND l.tare_achat_pct IS NOT NULL
              AND l.tare_achat_pct > 0
            ORDER BY l.date_entree_stock DESC
        """)
        
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        
        if not rows:
            return pd.DataFrame()
        
        df = pd.DataFrame(rows)
        
        # Convertir types
        numeric_cols = ['poids_total_brut_kg', 'prix_achat_euro_tonne', 'tare_achat_pct', 'valeur_lot_euro']
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
        
        # Calculer poids net payé
        df['poids_net_paye_kg'] = df['poids_total_brut_kg'] * (1 - df['tare_achat_pct'] / 100)
        
        # Tare production par lot (si jobs terminés)
        tares_prod = {}
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT lot_id, AVG(tare_reelle_pct) as tare_prod
            FROM lavages_jobs
            WHERE statut = 'TERMINÉ'
              AND tare_reelle_pct IS NOT NULL
            GROUP BY lot_id
        """)
        
        tares_rows = cursor.fetchall()
        cursor.close()
        conn.close()
        
        for row in tares_rows:
            tares_prod[row['lot_id']] = float(row['tare_prod'])
        
        # Appliquer tare production
        df['tare_production_pct'] = df['id'].apply(lambda x: tares_prod.get(x, 22.0))
        df['tare_prod_source'] = df['id'].apply(lambda x: "✅ Mesurée" if x in tares_prod else "📊 Standard")
        
        # Poids net production
        df['poids_net_production_kg'] = df['poids_total_brut_kg'] * (1 - df['tare_production_pct'] / 100)
        
        # Écart
        df['ecart_kg'] = df['poids_net_paye_kg'] - df['poids_net_production_kg']
        df['ecart_pct'] = (df['ecart_kg'] / df['poids_net_paye_kg'] * 100)
        
        return df
        
    except Exception as e:
        st.error(f"❌ Erreur : {str(e)}")
        return pd.DataFrame()

def get_stats_prix_variete():
    """Stats prix par variété"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                COALESCE(v.nom_variete, l.code_variete) as variete,
                COUNT(*) as nb_lots,
                AVG(l.prix_achat_euro_tonne) as prix_moyen,
                MIN(l.prix_achat_euro_tonne) as prix_min,
                MAX(l.prix_achat_euro_tonne) as prix_max,
                SUM(l.poids_total_brut_kg) / 1000 as tonnage_total
            FROM lots_bruts l
            LEFT JOIN ref_varietes v ON l.code_variete = v.code_variete
            WHERE l.is_active = TRUE
              AND l.prix_achat_euro_tonne IS NOT NULL
              AND l.prix_achat_euro_tonne > 0
            GROUP BY COALESCE(v.nom_variete, l.code_variete)
            ORDER BY nb_lots DESC, prix_moyen DESC
        """)
        
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        
        if rows:
            df = pd.DataFrame(rows)
            numeric_cols = ['prix_moyen', 'prix_min', 'prix_max', 'tonnage_total']
            for col in numeric_cols:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce').round(2)
            return df
        return pd.DataFrame()
        
    except Exception as e:
        st.error(f"❌ Erreur : {str(e)}")
        return pd.DataFrame()

def get_stats_prix_producteur():
    """Stats prix par producteur (top 20)"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                COALESCE(p.nom, l.code_producteur) as producteur,
                COUNT(*) as nb_lots,
                AVG(l.prix_achat_euro_tonne) as prix_moyen,
                MIN(l.prix_achat_euro_tonne) as prix_min,
                MAX(l.prix_achat_euro_tonne) as prix_max,
                SUM(l.poids_total_brut_kg) / 1000 as tonnage_total
            FROM lots_bruts l
            LEFT JOIN ref_producteurs p ON l.code_producteur = p.code_producteur
            WHERE l.is_active = TRUE
              AND l.prix_achat_euro_tonne IS NOT NULL
              AND l.prix_achat_euro_tonne > 0
            GROUP BY COALESCE(p.nom, l.code_producteur)
            ORDER BY nb_lots DESC, tonnage_total DESC
            LIMIT 20
        """)
        
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        
        if rows:
            df = pd.DataFrame(rows)
            numeric_cols = ['prix_moyen', 'prix_min', 'prix_max', 'tonnage_total']
            for col in numeric_cols:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce').round(2)
            return df
        return pd.DataFrame()
        
    except Exception as e:
        st.error(f"❌ Erreur : {str(e)}")
        return pd.DataFrame()

def get_stats_tare_variete():
    """Stats tare par variété"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                COALESCE(v.nom_variete, l.code_variete) as variete,
                COUNT(*) as nb_lots,
                AVG(l.tare_achat_pct) as tare_moyenne,
                MIN(l.tare_achat_pct) as tare_min,
                MAX(l.tare_achat_pct) as tare_max
            FROM lots_bruts l
            LEFT JOIN ref_varietes v ON l.code_variete = v.code_variete
            WHERE l.is_active = TRUE
              AND l.tare_achat_pct IS NOT NULL
              AND l.tare_achat_pct > 0
            GROUP BY COALESCE(v.nom_variete, l.code_variete)
            ORDER BY nb_lots DESC, tare_moyenne DESC
        """)
        
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        
        if rows:
            df = pd.DataFrame(rows)
            numeric_cols = ['tare_moyenne', 'tare_min', 'tare_max']
            for col in numeric_cols:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce').round(2)
            return df
        return pd.DataFrame()
        
    except Exception as e:
        st.error(f"❌ Erreur : {str(e)}")
        return pd.DataFrame()

def get_evolution_prix_temps():
    """Évolution prix dans le temps (par semaine)"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                EXTRACT(WEEK FROM date_entree_stock) as semaine,
                EXTRACT(YEAR FROM date_entree_stock) as annee,
                AVG(prix_achat_euro_tonne) as prix_moyen,
                COUNT(*) as nb_lots
            FROM lots_bruts
            WHERE is_active = TRUE
              AND prix_achat_euro_tonne IS NOT NULL
              AND prix_achat_euro_tonne > 0
              AND date_entree_stock IS NOT NULL
            GROUP BY EXTRACT(WEEK FROM date_entree_stock), EXTRACT(YEAR FROM date_entree_stock)
            ORDER BY annee, semaine
        """)
        
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        
        if rows:
            df = pd.DataFrame(rows)
            df['semaine'] = df['annee'].astype(str) + '-S' + df['semaine'].astype(int).astype(str)
            numeric_cols = ['prix_moyen']
            for col in numeric_cols:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce').round(2)
            return df[['semaine', 'prix_moyen', 'nb_lots']]
        return pd.DataFrame()
        
    except Exception as e:
        st.error(f"❌ Erreur : {str(e)}")
        return pd.DataFrame()

def get_evolution_tare_temps():
    """Évolution tare dans le temps (par semaine)"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                EXTRACT(WEEK FROM date_entree_stock) as semaine,
                EXTRACT(YEAR FROM date_entree_stock) as annee,
                AVG(tare_achat_pct) as tare_moyenne,
                COUNT(*) as nb_lots
            FROM lots_bruts
            WHERE is_active = TRUE
              AND tare_achat_pct IS NOT NULL
              AND tare_achat_pct > 0
              AND date_entree_stock IS NOT NULL
            GROUP BY EXTRACT(WEEK FROM date_entree_stock), EXTRACT(YEAR FROM date_entree_stock)
            ORDER BY annee, semaine
        """)
        
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        
        if rows:
            df = pd.DataFrame(rows)
            df['semaine'] = df['annee'].astype(str) + '-S' + df['semaine'].astype(int).astype(str)
            numeric_cols = ['tare_moyenne']
            for col in numeric_cols:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce').round(2)
            return df[['semaine', 'tare_moyenne', 'nb_lots']]
        return pd.DataFrame()
        
    except Exception as e:
        st.error(f"❌ Erreur : {str(e)}")
        return pd.DataFrame()

def get_historique_modifications(lot_id=None, limit=20):
    """Historique des modifications de valorisation"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        if lot_id:
            cursor.execute("""
                SELECT 
                    l.code_lot_interne,
                    l.nom_usage,
                    l.updated_at,
                    l.prix_achat_euro_tonne,
                    l.tare_achat_pct,
                    l.valeur_lot_euro
                FROM lots_bruts l
                WHERE l.id = %s
                  AND l.prix_achat_euro_tonne IS NOT NULL
                ORDER BY l.updated_at DESC
                LIMIT %s
            """, (lot_id, limit))
        else:
            cursor.execute("""
                SELECT 
                    l.code_lot_interne,
                    l.nom_usage,
                    l.updated_at,
                    l.prix_achat_euro_tonne,
                    l.tare_achat_pct,
                    l.valeur_lot_euro
                FROM lots_bruts l
                WHERE l.prix_achat_euro_tonne IS NOT NULL
                ORDER BY l.updated_at DESC
                LIMIT %s
            """, (limit,))
        
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        
        if rows:
            df = pd.DataFrame(rows)
            numeric_cols = ['prix_achat_euro_tonne', 'tare_achat_pct', 'valeur_lot_euro']
            for col in numeric_cols:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
            return df
        return pd.DataFrame()
        
    except Exception as e:
        st.error(f"❌ Erreur : {str(e)}")
        return pd.DataFrame()

# ============================================================
# KPIs PRINCIPAUX
# ============================================================

lots_non_qualifies = get_lots_non_qualifies()
lots_qualifies = get_lots_qualifies()

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric("📝 Lots Non Qualifiés", len(lots_non_qualifies))

with col2:
    st.metric("✅ Lots Qualifiés", len(lots_qualifies))

with col3:
    total_lots = len(lots_non_qualifies) + len(lots_qualifies)
    if total_lots > 0:
        pct_qualifies = (len(lots_qualifies) / total_lots) * 100
        st.metric("📊 Taux Qualification", f"{pct_qualifies:.0f}%")
    else:
        st.metric("📊 Taux Qualification", "0%")

with col4:
    if not lots_qualifies.empty:
        valeur_totale = lots_qualifies['valeur_lot_euro'].sum()
        st.metric("💰 Valeur Totale", f"{valeur_totale:,.0f} €")
    else:
        st.metric("💰 Valeur Totale", "0 €")

st.markdown("---")

# ============================================================
# ONGLETS PRINCIPAUX
# ============================================================

tab1, tab2, tab3, tab4 = st.tabs(["📝 Qualification", "🔧 Modifier", "📊 Statistiques", "📜 Historique"])

# ============================================================
# ONGLET 1 : QUALIFICATION (lots non qualifiés)
# ============================================================

with tab1:
    st.subheader("📝 Lots à Qualifier")
    st.caption("*Lots sans prix d'achat OU sans tare*")
    
    if not lots_non_qualifies.empty:
        # Filtres
        col1, col2, col3 = st.columns(3)
        
        with col1:
            filtre_nom = st.text_input("🔍 Nom lot", key="filtre_nom_qual")
        
        with col2:
            varietes_dispo = ["Tous"] + sorted(lots_non_qualifies['variete_nom'].dropna().unique().tolist())
            filtre_variete = st.selectbox("🌱 Variété", varietes_dispo, key="filtre_var_qual")
        
        with col3:
            producteurs_dispo = ["Tous"] + sorted(lots_non_qualifies['producteur_nom'].dropna().unique().tolist())
            filtre_producteur = st.selectbox("🏭 Producteur", producteurs_dispo, key="filtre_prod_qual")
        
        # Appliquer filtres
        if filtre_nom or filtre_variete != "Tous" or filtre_producteur != "Tous":
            lots_non_qualifies = get_lots_non_qualifies(filtre_nom, filtre_variete, filtre_producteur)
        
        if not lots_non_qualifies.empty:
            st.markdown(f"**{len(lots_non_qualifies)} lot(s) à qualifier**")
            
            # Affichage
            for idx, lot in lots_non_qualifies.iterrows():
                with st.expander(f"📦 {lot['code_lot_interne']} - {lot['nom_usage']} - {lot['variete_nom']}"):
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.write(f"**Variété** : {lot['variete_nom']}")
                        st.write(f"**Producteur** : {lot['producteur_nom']}")
                        st.write(f"**Poids brut** : {lot['poids_total_brut_kg']:,.0f} kg ({lot['poids_total_brut_kg']/1000:.1f} T)")
                        st.write(f"**Entrée stock** : {lot['date_entree_stock']}")
                    
                    with col2:
                        # Formulaire qualification
                        prix_actuel = float(lot['prix_achat_euro_tonne']) if pd.notna(lot['prix_achat_euro_tonne']) else 0.0
                        tare_actuelle = float(lot['tare_achat_pct']) if pd.notna(lot['tare_achat_pct']) else 0.0
                        
                        prix = st.number_input(
                            "Prix achat (€/T) *",
                            min_value=0.0,
                            value=prix_actuel,
                            step=10.0,
                            key=f"prix_{lot['id']}"
                        )
                        
                        tare = st.number_input(
                            "Tare achat (%) *",
                            min_value=0.0,
                            max_value=100.0,
                            value=tare_actuelle,
                            step=0.5,
                            key=f"tare_{lot['id']}"
                        )
                        
                        if prix > 0 and tare > 0:
                            poids_net = float(lot['poids_total_brut_kg']) * (1 - tare / 100)
                            valeur = (poids_net / 1000) * prix
                            st.info(f"💰 Valeur lot : **{valeur:,.2f} €**")
                        
                        if st.button("✅ Qualifier", key=f"qualify_{lot['id']}", type="primary", use_container_width=True):
                            if prix <= 0:
                                st.error("❌ Prix obligatoire")
                            elif tare <= 0:
                                st.error("❌ Tare obligatoire")
                            else:
                                success, message = update_lot_valorisation(lot['id'], prix, tare)
                                if success:
                                    st.success(message)
                                    st.rerun()
                                else:
                                    st.error(message)
        else:
            st.success("🎉 Tous les lots sont qualifiés !")
    else:
        st.markdown("""
        <div class='success-box'>
            <h2 style='margin: 0;'>🎉 Excellent !</h2>
            <p style='font-size: 1.2rem; margin: 0.5rem 0 0 0;'>Tous les lots sont qualifiés</p>
        </div>
        """, unsafe_allow_html=True)

# ============================================================
# ONGLET 2 : MODIFIER (lots qualifiés)
# ============================================================

with tab2:
    st.subheader("🔧 Modifier Lots Qualifiés")
    
    if not lots_qualifies.empty:
        # Filtres
        col1, col2, col3 = st.columns(3)
        
        with col1:
            filtre_nom_modif = st.text_input("🔍 Nom lot", key="filtre_nom_modif")
        
        with col2:
            varietes_dispo = ["Tous"] + sorted(lots_qualifies['variete_nom'].dropna().unique().tolist())
            filtre_variete_modif = st.selectbox("🌱 Variété", varietes_dispo, key="filtre_var_modif")
        
        with col3:
            producteurs_dispo = ["Tous"] + sorted(lots_qualifies['producteur_nom'].dropna().unique().tolist())
            filtre_producteur_modif = st.selectbox("🏭 Producteur", producteurs_dispo, key="filtre_prod_modif")
        
        # Appliquer filtres
        if filtre_nom_modif or filtre_variete_modif != "Tous" or filtre_producteur_modif != "Tous":
            lots_qualifies = get_lots_qualifies(filtre_nom_modif, filtre_variete_modif, filtre_producteur_modif)
        
        if not lots_qualifies.empty:
            st.markdown(f"**{len(lots_qualifies)} lot(s) qualifié(s)**")
            
            # Tableau éditable
            df_edit = lots_qualifies[['id', 'code_lot_interne', 'nom_usage', 'variete_nom', 'producteur_nom', 'poids_total_brut_kg', 'prix_achat_euro_tonne', 'tare_achat_pct', 'valeur_lot_euro']].copy()
            
            df_display = df_edit.rename(columns={
                'code_lot_interne': 'Code',
                'nom_usage': 'Nom',
                'variete_nom': 'Variété',
                'producteur_nom': 'Producteur',
                'poids_total_brut_kg': 'Poids (kg)',
                'prix_achat_euro_tonne': 'Prix (€/T)',
                'tare_achat_pct': 'Tare (%)',
                'valeur_lot_euro': 'Valeur (€)'
            })
            
            column_config = {
                "id": None,
                "Code": st.column_config.TextColumn("Code", disabled=True),
                "Nom": st.column_config.TextColumn("Nom", disabled=True),
                "Variété": st.column_config.TextColumn("Variété", disabled=True),
                "Producteur": st.column_config.TextColumn("Producteur", disabled=True),
                "Poids (kg)": st.column_config.NumberColumn("Poids (kg)", format="%.0f", disabled=True),
                "Prix (€/T)": st.column_config.NumberColumn("Prix (€/T)", format="%.2f", min_value=0),
                "Tare (%)": st.column_config.NumberColumn("Tare (%)", format="%.2f", min_value=0, max_value=100),
                "Valeur (€)": st.column_config.NumberColumn("Valeur (€)", format="%.2f", disabled=True)
            }
            
            edited_df = st.data_editor(
                df_display,
                column_config=column_config,
                use_container_width=True,
                hide_index=True,
                num_rows="fixed",
                key="editor_modif"
            )
            
            st.markdown("---")
            
            col_btn1, col_btn2 = st.columns([1, 4])
            
            with col_btn1:
                if st.button("💾 Enregistrer", type="primary", use_container_width=False, key="save_modif"):
                    modifications = 0
                    
                    for idx in edited_df.index:
                        lot_id = int(df_display.loc[idx, 'id'])
                        old_prix = float(df_display.loc[idx, 'Prix (€/T)'])
                        old_tare = float(df_display.loc[idx, 'Tare (%)'])
                        new_prix = float(edited_df.loc[idx, 'Prix (€/T)'])
                        new_tare = float(edited_df.loc[idx, 'Tare (%)'])
                        
                        if old_prix != new_prix or old_tare != new_tare:
                            success, message = update_lot_valorisation(lot_id, new_prix, new_tare)
                            if success:
                                modifications += 1
                    
                    if modifications > 0:
                        st.success(f"✅ {modifications} lot(s) modifié(s) avec succès !")
                        st.rerun()
                    else:
                        st.info("ℹ️ Aucune modification détectée")
            
            with col_btn2:
                if st.button("🔄 Actualiser", use_container_width=False, key="refresh_modif"):
                    st.rerun()
        else:
            st.info("Aucun lot qualifié avec ces filtres")
    else:
        st.warning("⚠️ Aucun lot qualifié à modifier")

# ============================================================
# ONGLET 3 : STATISTIQUES
# ============================================================

with tab3:
    st.subheader("📊 Statistiques de Valorisation")
    
    # ⭐ SOUS-ONGLETS
    stat_tab1, stat_tab2, stat_tab3, stat_tab4, stat_tab5, stat_tab6 = st.tabs([
        "📊 Vue Globale",
        "📋 Détails par Lot",
        "💶 Prix par Variété", 
        "🏭 Prix par Producteur",
        "📉 Tare par Variété",
        "📈 Évolution Temporelle"
    ])
    
    # ============================================================
    # SOUS-ONGLET 1 : VUE GLOBALE (récap déplacé ici)
    # ============================================================
    
    with stat_tab1:
        st.markdown("### 📊 Récap Valorisation Stock Complet")
        
        recap = get_recap_valorisation_global()
        
        if recap:
            col1, col2 = st.columns(2)
            
            with col1:
                # ✅ HAUTEUR FIXE : min-height: 250px
                st.markdown("""
                <div style='background-color: #e3f2fd; padding: 1rem; border-radius: 0.5rem; border-left: 4px solid #2196f3; min-height: 250px;'>
                    <h4 style='margin-top: 0; color: #1976d2;'>💰 VALEUR ACHAT</h4>
                    <p style='margin: 0.3rem 0;'><strong>Poids brut total:</strong> {:.1f} T</p>
                    <p style='margin: 0.3rem 0;'><strong>Tare achat moyenne:</strong> {:.1f}%</p>
                    <p style='margin: 0.3rem 0;'><strong>Poids net payé:</strong> {:.1f} T</p>
                    <hr style='margin: 0.5rem 0;'>
                    <p style='margin: 0.3rem 0; font-size: 1.1rem;'><strong>Valeur stock:</strong> {:,.0f} €</p>
                </div>
                """.format(
                    recap['poids_brut_total'],
                    recap['tare_achat_moy'],
                    recap['poids_net_paye'],
                    recap['valeur_totale']
                ), unsafe_allow_html=True)
            
            with col2:
                # ✅ HAUTEUR FIXE : min-height: 250px
                st.markdown("""
                <div style='background-color: #fff3e0; padding: 1rem; border-radius: 0.5rem; border-left: 4px solid #ff9800; min-height: 250px;'>
                    <h4 style='margin-top: 0; color: #f57c00;'>🏭 MATIÈRE PREMIÈRE PRODUCTION</h4>
                    <p style='margin: 0.3rem 0;'><strong>Tare production moyenne:</strong> {:.1f}% <span style='font-size: 0.85rem;'>{}</span></p>
                    <p style='margin: 0.3rem 0;'><strong>Poids net production:</strong> {:.1f} T</p>
                    <hr style='margin: 0.5rem 0;'>
                    <h4 style='margin-top: 0.5rem; margin-bottom: 0.3rem; color: #d32f2f;'>📈 ÉCARTS</h4>
                    <p style='margin: 0.3rem 0;'><strong>Perte production:</strong> {:.1f} T ({:.1f}%)</p>
                    <p style='margin: 0.3rem 0;'><strong>Valeur MP réelle:</strong> {:,.0f} €</p>
                </div>
                """.format(
                    recap['tare_prod_moy'],
                    recap['tare_prod_source'],
                    recap['poids_net_production'],
                    recap['perte_production'],
                    recap['pct_perte'],
                    recap['valeur_mp_reelle']
                ), unsafe_allow_html=True)
            
            st.caption("💡 **Tare achat** : Négociée avec producteur (ce qu'on a payé) | **Tare production** : Réelle après lavage ou standard 22% (matière disponible)")
        else:
            st.info("📊 Aucun lot qualifié pour calculer les statistiques globales")
    
    # ============================================================
    # SOUS-ONGLET 2 : DÉTAILS PAR LOT (nouveau)
    # ============================================================
    
    with stat_tab2:
        st.markdown("### 📋 Détails Valorisation par Lot")
        
        df_details = get_details_lots_qualifies()
        
        if not df_details.empty:
            st.markdown(f"**{len(df_details)} lot(s) qualifié(s)**")
            
            # Formater pour affichage
            df_display = df_details[[
                'id', 'code_lot_interne', 'variete', 'producteur',
                'poids_total_brut_kg', 'tare_achat_pct', 'poids_net_paye_kg',
                'tare_production_pct', 'tare_prod_source', 'poids_net_production_kg',
                'ecart_kg', 'ecart_pct', 'valeur_lot_euro'
            ]].copy()
            
            df_display['poids_total_brut_kg'] = df_display['poids_total_brut_kg'] / 1000
            df_display['poids_net_paye_kg'] = df_display['poids_net_paye_kg'] / 1000
            df_display['poids_net_production_kg'] = df_display['poids_net_production_kg'] / 1000
            df_display['ecart_kg'] = df_display['ecart_kg'] / 1000
            
            df_display = df_display.rename(columns={
                'code_lot_interne': 'Code Lot',
                'variete': 'Variété',
                'producteur': 'Producteur',
                'poids_total_brut_kg': 'Poids Brut (T)',
                'tare_achat_pct': 'Tare Achat (%)',
                'poids_net_paye_kg': 'Poids Payé (T)',
                'tare_production_pct': 'Tare Prod (%)',
                'tare_prod_source': 'Source',
                'poids_net_production_kg': 'Poids Prod (T)',
                'ecart_kg': 'Écart (T)',
                'ecart_pct': 'Écart (%)',
                'valeur_lot_euro': 'Valeur (€)'
            })
            
            column_config = {
                "id": None,
                "Code Lot": st.column_config.TextColumn("Code Lot", width="medium"),
                "Variété": st.column_config.TextColumn("Variété", width="small"),
                "Producteur": st.column_config.TextColumn("Producteur", width="medium"),
                "Poids Brut (T)": st.column_config.NumberColumn("Poids Brut (T)", format="%.1f"),
                "Tare Achat (%)": st.column_config.NumberColumn("Tare Achat (%)", format="%.1f"),
                "Poids Payé (T)": st.column_config.NumberColumn("Poids Payé (T)", format="%.1f"),
                "Tare Prod (%)": st.column_config.NumberColumn("Tare Prod (%)", format="%.1f"),
                "Source": st.column_config.TextColumn("Source", width="small"),
                "Poids Prod (T)": st.column_config.NumberColumn("Poids Prod (T)", format="%.1f"),
                "Écart (T)": st.column_config.NumberColumn("Écart (T)", format="%.2f"),
                "Écart (%)": st.column_config.NumberColumn("Écart (%)", format="%.1f"),
                "Valeur (€)": st.column_config.NumberColumn("Valeur (€)", format="%.0f")
            }
            
            # Tableau avec sélection
            event = st.dataframe(
                df_display,
                column_config=column_config,
                use_container_width=True,
                hide_index=True,
                on_select="rerun",
                selection_mode="single-row",
                key="table_details_lots"
            )
            
            # Bouton voir détails si sélection
            selected_rows = event.selection.rows if hasattr(event, 'selection') else []
            
            if len(selected_rows) > 0:
                selected_idx = selected_rows[0]
                selected_lot_id = int(df_display.iloc[selected_idx]['id'])
                selected_code = df_display.iloc[selected_idx]['Code Lot']
                
                st.success(f"✅ Lot sélectionné : **{selected_code}**")
                
                if st.button("👁️ Voir Détails Complets", type="primary", use_container_width=True, key="btn_voir_details"):
                    # Stocker dans session_state (même méthode que page 02)
                    st.session_state.selected_lots_for_emplacements = [selected_lot_id]
                    st.switch_page("pages/03_Détails stock.py")
            else:
                st.info("👆 Sélectionnez un lot pour voir ses détails complets")
        else:
            st.info("📊 Aucun lot qualifié")
    
    # ============================================================
    # SOUS-ONGLET 3 : PRIX PAR VARIÉTÉ
    # ============================================================
    
    with stat_tab3:
        st.markdown("### 💶 Prix d'achat par Variété")
        df_prix_var = get_stats_prix_variete()
        
        if not df_prix_var.empty:
            st.dataframe(
                df_prix_var.rename(columns={
                    'variete': 'Variété', 'nb_lots': 'Nb Lots',
                    'prix_moyen': 'Prix Moyen (€/T)', 'prix_min': 'Prix Min',
                    'prix_max': 'Prix Max', 'tonnage_total': 'Tonnage (T)'
                }),
                use_container_width=True, hide_index=True
            )
            st.markdown("---")
            st.markdown("#### 📊 Prix moyen par variété")
            df_chart = df_prix_var.head(15).sort_values('prix_moyen', ascending=True)
            st.bar_chart(df_chart.set_index('variete')['prix_moyen'], use_container_width=True)
        else:
            st.info("Aucune donnée disponible")
    
    # ============================================================
    # SOUS-ONGLET 4 : PRIX PAR PRODUCTEUR
    # ============================================================
    
    with stat_tab4:
        st.markdown("### 🏭 Prix d'achat par Producteur (Top 20)")
        df_prix_prod = get_stats_prix_producteur()
        
        if not df_prix_prod.empty:
            st.dataframe(
                df_prix_prod.rename(columns={
                    'producteur': 'Producteur', 'nb_lots': 'Nb Lots',
                    'prix_moyen': 'Prix Moyen (€/T)', 'prix_min': 'Prix Min',
                    'prix_max': 'Prix Max', 'tonnage_total': 'Tonnage (T)'
                }),
                use_container_width=True, hide_index=True
            )
            st.markdown("---")
            st.markdown("#### 📊 Prix moyen par producteur (Top 15)")
            df_chart = df_prix_prod.head(15).sort_values('prix_moyen', ascending=True)
            st.bar_chart(df_chart.set_index('producteur')['prix_moyen'], use_container_width=True)
        else:
            st.info("Aucune donnée disponible")
    
    # ============================================================
    # SOUS-ONGLET 5 : TARE PAR VARIÉTÉ
    # ============================================================
    
    with stat_tab5:
        st.markdown("### 📉 Tare d'achat par Variété")
        df_tare_var = get_stats_tare_variete()
        
        if not df_tare_var.empty:
            st.dataframe(
                df_tare_var.rename(columns={
                    'variete': 'Variété', 'nb_lots': 'Nb Lots',
                    'tare_moyenne': 'Tare Moyenne (%)', 'tare_min': 'Tare Min', 'tare_max': 'Tare Max'
                }),
                use_container_width=True, hide_index=True
            )
            st.markdown("---")
            st.markdown("#### 📊 Tare moyenne par variété")
            df_chart = df_tare_var.head(15).sort_values('tare_moyenne', ascending=False)
            st.bar_chart(df_chart.set_index('variete')['tare_moyenne'], use_container_width=True)
        else:
            st.info("Aucune donnée disponible")
    
    # ============================================================
    # SOUS-ONGLET 6 : ÉVOLUTION TEMPORELLE
    # ============================================================
    
    with stat_tab6:
        st.markdown("### 📈 Évolution dans le temps")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("#### Prix moyen par semaine")
            df_evol_prix = get_evolution_prix_temps()
            if not df_evol_prix.empty:
                st.line_chart(df_evol_prix.set_index('semaine')['prix_moyen'], use_container_width=True)
                if len(df_evol_prix) >= 4:
                    recent = df_evol_prix['prix_moyen'].tail(4).mean()
                    ancien = df_evol_prix['prix_moyen'].head(4).mean()
                    tendance = ((recent - ancien) / ancien * 100) if ancien > 0 else 0
                    if tendance > 0:
                        st.success(f"📈 Tendance : +{tendance:.1f}%")
                    else:
                        st.error(f"📉 Tendance : {tendance:.1f}%")
            else:
                st.info("Pas assez de données")
        
        with col2:
            st.markdown("#### Tare moyenne par semaine")
            df_evol_tare = get_evolution_tare_temps()
            if not df_evol_tare.empty:
                st.line_chart(df_evol_tare.set_index('semaine')['tare_moyenne'], use_container_width=True)
                if len(df_evol_tare) >= 4:
                    recent = df_evol_tare['tare_moyenne'].tail(4).mean()
                    ancien = df_evol_tare['tare_moyenne'].head(4).mean()
                    tendance = ((recent - ancien) / ancien * 100) if ancien > 0 else 0
                    if tendance > 0:
                        st.error(f"📈 Tendance : +{tendance:.1f}%")
                    else:
                        st.success(f"📉 Tendance : {tendance:.1f}%")
            else:
                st.info("Pas assez de données")

# ============================================================
# ONGLET 4 : HISTORIQUE
# ============================================================

with tab4:
    st.subheader("📜 Historique des Modifications")
    
    df_historique = get_historique_modifications(limit=50)
    
    if not df_historique.empty:
        st.markdown(f"**{len(df_historique)} modification(s) récente(s)**")
        
        for idx, row in df_historique.iterrows():
            st.markdown(f"""
            <div class='history-item modification'>
                <strong>{row['code_lot_interne']}</strong> - {row['nom_usage']}<br>
                <small>📅 {row['updated_at']}</small><br>
                💶 Prix : {row['prix_achat_euro_tonne']:.2f} €/T | 
                📉 Tare : {row['tare_achat_pct']:.1f}% | 
                💰 Valeur : {row['valeur_lot_euro']:,.0f} €
            </div>
            """, unsafe_allow_html=True)
    else:
        st.info("Aucun historique disponible")

show_footer()
