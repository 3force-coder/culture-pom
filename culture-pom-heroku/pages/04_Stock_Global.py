import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from database import get_connection
from components import show_footer
from auth import require_access
import io

st.set_page_config(page_title="Stock Global - Culture Pom", page_icon="📊", layout="wide")

# ============================================================
# 🎨 CSS PERSONNALISÉ
# ============================================================
st.markdown("""
<style>
    .block-container {
        padding-top: 1.5rem !important;
        padding-bottom: 0.5rem !important;
    }
    h1, h2, h3, h4 {
        margin-top: 0.3rem !important;
        margin-bottom: 0.3rem !important;
    }
    .stMetric {
        background-color: #f0f2f6;
        padding: 0.8rem;
        border-radius: 0.5rem;
    }
    
    /* Cartes statut stock */
    .status-card {
        padding: 1rem;
        border-radius: 0.5rem;
        text-align: center;
        margin-bottom: 0.5rem;
    }
    .status-brut {
        background: linear-gradient(135deg, #e8f5e9 0%, #c8e6c9 100%);
        border-left: 4px solid #4caf50;
    }
    .status-lave {
        background: linear-gradient(135deg, #e3f2fd 0%, #bbdefb 100%);
        border-left: 4px solid #2196f3;
    }
    .status-gren {
        background: linear-gradient(135deg, #fff8e1 0%, #ffecb3 100%);
        border-left: 4px solid #ffc107;
    }
    
    /* Alertes */
    .alert-box {
        padding: 0.8rem;
        border-radius: 0.5rem;
        margin-bottom: 0.5rem;
    }
    .alert-critical {
        background-color: #ffebee;
        border-left: 4px solid #f44336;
    }
    .alert-warning {
        background-color: #fff3e0;
        border-left: 4px solid #ff9800;
    }
    .alert-info {
        background-color: #e3f2fd;
        border-left: 4px solid #2196f3;
    }
    
    /* Barres de progression */
    .progress-bar {
        height: 20px;
        border-radius: 10px;
        background-color: #e0e0e0;
        overflow: hidden;
    }
    .progress-fill {
        height: 100%;
        border-radius: 10px;
        transition: width 0.3s ease;
    }
</style>
""", unsafe_allow_html=True)

# ============================================================
# 🔒 CONTRÔLE D'ACCÈS RBAC
# ============================================================
require_access("STOCK")

# ============================================================
# ⚙️ PARAMÈTRES CONFIGURABLES
# ============================================================
SEUIL_SITE_PLEIN = 85       # % pour alerte site plein
SEUIL_SITE_CRITIQUE = 95    # % pour alerte critique
SEUIL_LOT_ANCIEN = 60       # jours pour alerte lot ancien
SEUIL_LOT_ATTENTION = 45    # jours pour attention
SEUIL_GRENAILLES = 10000    # kg pour alerte grenailles élevé

# ============================================================
# 🔧 FONCTIONS UTILITAIRES
# ============================================================

def format_number_fr(n):
    """Formate un nombre avec séparateur de milliers français"""
    if pd.isna(n):
        return "0"
    return f"{int(n):,}".replace(",", " ")

def format_float_fr(n, decimals=1):
    """Formate un décimal français"""
    if pd.isna(n):
        return "0"
    return f"{n:,.{decimals}f}".replace(",", " ").replace(".", ",")

def get_color_by_percent(pct):
    """Retourne une couleur selon le pourcentage d'occupation"""
    if pct >= SEUIL_SITE_CRITIQUE:
        return "#f44336"  # Rouge
    elif pct >= SEUIL_SITE_PLEIN:
        return "#ff9800"  # Orange
    elif pct >= 70:
        return "#ffc107"  # Jaune
    else:
        return "#4caf50"  # Vert

def get_status_emoji(pct):
    """Retourne un emoji selon le pourcentage"""
    if pct >= SEUIL_SITE_CRITIQUE:
        return "🔴"
    elif pct >= SEUIL_SITE_PLEIN:
        return "🟠"
    elif pct >= 70:
        return "🟡"
    else:
        return "🟢"

# ============================================================
# 📊 FONCTIONS DE DONNÉES - TABLEAU DE BORD
# ============================================================

def get_stock_kpis():
    """Récupère les KPIs détaillés par statut de lavage"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Stock par statut de lavage
        cursor.execute("""
            SELECT 
                COALESCE(se.statut_lavage, 'BRUT') as statut,
                COUNT(DISTINCT se.lot_id) as nb_lots,
                SUM(se.nombre_unites) as total_pallox,
                SUM(se.poids_total_kg) as total_kg
            FROM stock_emplacements se
            JOIN lots_bruts l ON se.lot_id = l.id
            WHERE se.is_active = TRUE AND l.is_active = TRUE AND se.nombre_unites > 0
            GROUP BY COALESCE(se.statut_lavage, 'BRUT')
        """)
        rows = cursor.fetchall()
        
        result = {
            'BRUT': {'lots': 0, 'pallox': 0, 'tonnes': 0},
            'LAVE': {'lots': 0, 'pallox': 0, 'tonnes': 0},
            'GRENAILLES': {'lots': 0, 'pallox': 0, 'tonnes': 0}
        }
        
        total_tonnes = 0
        total_pallox = 0
        total_lots = 0
        
        for row in rows:
            statut = row['statut'] if row['statut'] else 'BRUT'
            if statut in result:
                result[statut]['lots'] = int(row['nb_lots'] or 0)
                result[statut]['pallox'] = int(row['total_pallox'] or 0)
                result[statut]['tonnes'] = float(row['total_kg'] or 0) / 1000
                total_tonnes += result[statut]['tonnes']
                total_pallox += result[statut]['pallox']
                total_lots += result[statut]['lots']
        
        # Nombre de sites utilisés
        cursor.execute("""
            SELECT COUNT(DISTINCT se.site_stockage) as nb_sites
            FROM stock_emplacements se
            JOIN lots_bruts l ON se.lot_id = l.id
            WHERE se.is_active = TRUE AND l.is_active = TRUE AND se.nombre_unites > 0
        """)
        nb_sites = cursor.fetchone()['nb_sites']
        
        # Nombre d'emplacements utilisés
        cursor.execute("""
            SELECT COUNT(*) as nb_emplacements
            FROM stock_emplacements se
            JOIN lots_bruts l ON se.lot_id = l.id
            WHERE se.is_active = TRUE AND l.is_active = TRUE AND se.nombre_unites > 0
        """)
        nb_emplacements = cursor.fetchone()['nb_emplacements']
        
        cursor.close()
        conn.close()
        
        result['total'] = {
            'tonnes': total_tonnes,
            'pallox': total_pallox,
            'lots': total_lots,
            'sites': nb_sites,
            'emplacements': nb_emplacements
        }
        
        return result
        
    except Exception as e:
        st.error(f"❌ Erreur KPIs : {str(e)}")
        return None

def get_occupation_globale():
    """Calcule l'occupation globale des sites"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Capacité totale des sites
        cursor.execute("""
            SELECT 
                COALESCE(SUM(capacite_max_pallox), 0) as capacite_totale,
                COALESCE(SUM(capacite_max_tonnes), 0) as capacite_tonnes
            FROM ref_sites_stockage
            WHERE is_active = TRUE
        """)
        capacites = cursor.fetchone()
        capacite_totale = int(capacites['capacite_totale'] or 0)
        
        # Stock actuel
        cursor.execute("""
            SELECT COALESCE(SUM(se.nombre_unites), 0) as occupe
            FROM stock_emplacements se
            JOIN lots_bruts l ON se.lot_id = l.id
            WHERE se.is_active = TRUE AND l.is_active = TRUE
        """)
        occupe = int(cursor.fetchone()['occupe'] or 0)
        
        cursor.close()
        conn.close()
        
        taux = (occupe / capacite_totale * 100) if capacite_totale > 0 else 0
        disponible = max(0, capacite_totale - occupe)
        
        return {
            'capacite': capacite_totale,
            'occupe': occupe,
            'disponible': disponible,
            'taux': round(taux, 1)
        }
        
    except Exception as e:
        st.error(f"❌ Erreur occupation : {str(e)}")
        return None

def get_alertes():
    """Récupère les alertes actives"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        alertes = []
        
        # Sites critiques (>95%)
        cursor.execute("""
            SELECT 
                rs.code_site,
                rs.capacite_max_pallox,
                COALESCE(SUM(se.nombre_unites), 0) as occupe
            FROM ref_sites_stockage rs
            LEFT JOIN stock_emplacements se ON rs.code_site = se.site_stockage 
                AND se.is_active = TRUE
            LEFT JOIN lots_bruts l ON se.lot_id = l.id AND l.is_active = TRUE
            WHERE rs.is_active = TRUE AND rs.capacite_max_pallox > 0
            GROUP BY rs.code_site, rs.capacite_max_pallox
            HAVING (COALESCE(SUM(se.nombre_unites), 0)::float / rs.capacite_max_pallox * 100) >= %s
        """, (SEUIL_SITE_CRITIQUE,))
        
        for row in cursor.fetchall():
            taux = (row['occupe'] / row['capacite_max_pallox'] * 100) if row['capacite_max_pallox'] > 0 else 0
            alertes.append({
                'type': 'critical',
                'icon': '🔴',
                'message': f"Site {row['code_site']} CRITIQUE : {taux:.0f}% occupé ({row['occupe']}/{row['capacite_max_pallox']} pallox)"
            })
        
        # Sites pleins (>85%)
        cursor.execute("""
            SELECT 
                rs.code_site,
                rs.capacite_max_pallox,
                COALESCE(SUM(se.nombre_unites), 0) as occupe
            FROM ref_sites_stockage rs
            LEFT JOIN stock_emplacements se ON rs.code_site = se.site_stockage 
                AND se.is_active = TRUE
            LEFT JOIN lots_bruts l ON se.lot_id = l.id AND l.is_active = TRUE
            WHERE rs.is_active = TRUE AND rs.capacite_max_pallox > 0
            GROUP BY rs.code_site, rs.capacite_max_pallox
            HAVING (COALESCE(SUM(se.nombre_unites), 0)::float / rs.capacite_max_pallox * 100) >= %s
                AND (COALESCE(SUM(se.nombre_unites), 0)::float / rs.capacite_max_pallox * 100) < %s
        """, (SEUIL_SITE_PLEIN, SEUIL_SITE_CRITIQUE))
        
        for row in cursor.fetchall():
            taux = (row['occupe'] / row['capacite_max_pallox'] * 100) if row['capacite_max_pallox'] > 0 else 0
            alertes.append({
                'type': 'warning',
                'icon': '🟠',
                'message': f"Site {row['code_site']} quasi plein : {taux:.0f}% occupé"
            })
        
        # Lots anciens (>60 jours)
        cursor.execute("""
            SELECT 
                l.code_lot_interne,
                COALESCE(v.nom_variete, l.code_variete) as variete,
                l.age_jours
            FROM lots_bruts l
            LEFT JOIN ref_varietes v ON l.code_variete = v.code_variete
            WHERE l.is_active = TRUE 
                AND l.age_jours >= %s
                AND EXISTS (
                    SELECT 1 FROM stock_emplacements se 
                    WHERE se.lot_id = l.id AND se.is_active = TRUE AND se.nombre_unites > 0
                )
            ORDER BY l.age_jours DESC
            LIMIT 5
        """, (SEUIL_LOT_ANCIEN,))
        
        for row in cursor.fetchall():
            alertes.append({
                'type': 'warning',
                'icon': '🟡',
                'message': f"Lot {row['code_lot_interne']} ({row['variete']}) : {row['age_jours']} jours en stock"
            })
        
        # Stock grenailles élevé
        cursor.execute("""
            SELECT COALESCE(SUM(se.poids_total_kg), 0) as poids_grenailles
            FROM stock_emplacements se
            JOIN lots_bruts l ON se.lot_id = l.id
            WHERE se.is_active = TRUE AND l.is_active = TRUE
                AND se.statut_lavage = 'GRENAILLES'
        """)
        poids_gren = float(cursor.fetchone()['poids_grenailles'] or 0)
        
        if poids_gren >= SEUIL_GRENAILLES:
            alertes.append({
                'type': 'info',
                'icon': '🌾',
                'message': f"Stock grenailles élevé : {poids_gren/1000:.1f} T à traiter"
            })
        
        cursor.close()
        conn.close()
        
        return alertes
        
    except Exception as e:
        st.error(f"❌ Erreur alertes : {str(e)}")
        return []

def get_top_sites(limit=10):
    """Récupère le top des sites par tonnage"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                se.site_stockage,
                COUNT(DISTINCT se.lot_id) as nb_lots,
                SUM(se.nombre_unites) as total_pallox,
                SUM(se.poids_total_kg) / 1000 as total_tonnes
            FROM stock_emplacements se
            JOIN lots_bruts l ON se.lot_id = l.id
            WHERE se.is_active = TRUE AND l.is_active = TRUE AND se.nombre_unites > 0
            GROUP BY se.site_stockage
            ORDER BY total_tonnes DESC
            LIMIT %s
        """, (limit,))
        
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        
        if rows:
            df = pd.DataFrame(rows)
            df.columns = ['Site', 'Lots', 'Pallox', 'Tonnes']
            for col in ['Lots', 'Pallox']:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0).astype(int)
            df['Tonnes'] = pd.to_numeric(df['Tonnes'], errors='coerce').fillna(0).round(1)
            return df
        return pd.DataFrame()
        
    except Exception as e:
        st.error(f"❌ Erreur top sites : {str(e)}")
        return pd.DataFrame()

# ============================================================
# 🏭 FONCTIONS DE DONNÉES - CAPACITÉS
# ============================================================

def get_capacites_sites():
    """Récupère les capacités détaillées par site/emplacement"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                rs.code_site,
                rs.code_emplacement,
                rs.nom_complet,
                rs.capacite_max_pallox,
                rs.capacite_max_tonnes,
                COALESCE(SUM(se.nombre_unites), 0) as occupe_pallox,
                COALESCE(SUM(se.poids_total_kg), 0) as occupe_kg,
                COUNT(DISTINCT se.lot_id) as nb_lots
            FROM ref_sites_stockage rs
            LEFT JOIN stock_emplacements se ON rs.code_site = se.site_stockage 
                AND rs.code_emplacement = se.emplacement_stockage
                AND se.is_active = TRUE
            LEFT JOIN lots_bruts l ON se.lot_id = l.id AND l.is_active = TRUE
            WHERE rs.is_active = TRUE
            GROUP BY rs.code_site, rs.code_emplacement, rs.nom_complet, 
                     rs.capacite_max_pallox, rs.capacite_max_tonnes
            ORDER BY rs.code_site, rs.code_emplacement
        """)
        
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        
        if rows:
            df = pd.DataFrame(rows)
            df.columns = ['Site', 'Emplacement', 'Nom', 'Capacité Max', 'Cap. Tonnes', 
                         'Occupé', 'Poids (kg)', 'Nb Lots']
            
            # Conversions numériques
            for col in ['Capacité Max', 'Occupé', 'Nb Lots']:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0).astype(int)
            df['Poids (kg)'] = pd.to_numeric(df['Poids (kg)'], errors='coerce').fillna(0)
            df['Cap. Tonnes'] = pd.to_numeric(df['Cap. Tonnes'], errors='coerce').fillna(0)
            
            # Calculs
            df['Disponible'] = (df['Capacité Max'] - df['Occupé']).clip(lower=0)
            df['Taux (%)'] = ((df['Occupé'] / df['Capacité Max']) * 100).where(df['Capacité Max'] > 0, 0).round(1)
            df['Tonnage'] = (df['Poids (kg)'] / 1000).round(1)
            
            return df
        return pd.DataFrame()
        
    except Exception as e:
        st.error(f"❌ Erreur capacités : {str(e)}")
        return pd.DataFrame()

# ============================================================
# 📦 FONCTIONS DE DONNÉES - STOCK COMPLET
# ============================================================

def get_stock_complet():
    """Récupère tous les emplacements avec détails"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                l.id as lot_id,
                l.code_lot_interne,
                l.nom_usage,
                COALESCE(v.nom_variete, l.code_variete) as variete,
                COALESCE(p.nom, l.code_producteur) as producteur,
                se.site_stockage,
                se.emplacement_stockage,
                se.nombre_unites,
                se.poids_total_kg,
                COALESCE(se.statut_lavage, 'BRUT') as statut_lavage,
                se.type_conditionnement,
                l.calibre_min,
                l.calibre_max,
                l.age_jours,
                l.date_entree_stock
            FROM stock_emplacements se
            JOIN lots_bruts l ON se.lot_id = l.id
            LEFT JOIN ref_varietes v ON l.code_variete = v.code_variete
            LEFT JOIN ref_producteurs p ON l.code_producteur = p.code_producteur
            WHERE se.is_active = TRUE AND l.is_active = TRUE AND se.nombre_unites > 0
            ORDER BY l.code_lot_interne, se.site_stockage
        """)
        
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        
        if rows:
            df = pd.DataFrame(rows)
            # Conversions numériques
            numeric_cols = ['nombre_unites', 'poids_total_kg', 'calibre_min', 'calibre_max', 'age_jours']
            for col in numeric_cols:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
            return df
        return pd.DataFrame()
        
    except Exception as e:
        st.error(f"❌ Erreur stock complet : {str(e)}")
        return pd.DataFrame()

# ============================================================
# 📍 FONCTIONS DE DONNÉES - VUES AGRÉGÉES
# ============================================================

def get_stock_par_site():
    """Stock agrégé par site avec statuts"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                se.site_stockage,
                COUNT(DISTINCT se.emplacement_stockage) as nb_emplacements,
                COUNT(DISTINCT se.lot_id) as nb_lots,
                SUM(se.nombre_unites) as total_pallox,
                SUM(se.poids_total_kg) / 1000 as total_tonnes,
                SUM(CASE WHEN COALESCE(se.statut_lavage, 'BRUT') = 'BRUT' THEN se.poids_total_kg ELSE 0 END) / 1000 as tonnes_brut,
                SUM(CASE WHEN se.statut_lavage = 'LAVE' THEN se.poids_total_kg ELSE 0 END) / 1000 as tonnes_lave,
                SUM(CASE WHEN se.statut_lavage = 'GRENAILLES' THEN se.poids_total_kg ELSE 0 END) / 1000 as tonnes_gren
            FROM stock_emplacements se
            JOIN lots_bruts l ON se.lot_id = l.id
            WHERE se.is_active = TRUE AND l.is_active = TRUE AND se.nombre_unites > 0
            GROUP BY se.site_stockage
            ORDER BY total_tonnes DESC
        """)
        
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        
        if rows:
            df = pd.DataFrame(rows)
            df.columns = ['Site', 'Emplacements', 'Lots', 'Pallox', 'Total (T)', 
                         'Brut (T)', 'Lavé (T)', 'Gren. (T)']
            for col in ['Emplacements', 'Lots', 'Pallox']:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0).astype(int)
            for col in ['Total (T)', 'Brut (T)', 'Lavé (T)', 'Gren. (T)']:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0).round(1)
            return df
        return pd.DataFrame()
        
    except Exception as e:
        st.error(f"❌ Erreur stock par site : {str(e)}")
        return pd.DataFrame()

def get_stock_par_variete():
    """Stock agrégé par variété avec statuts"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                COALESCE(v.nom_variete, l.code_variete, 'Non défini') as variete,
                COUNT(DISTINCT se.lot_id) as nb_lots,
                SUM(se.nombre_unites) as total_pallox,
                SUM(se.poids_total_kg) / 1000 as total_tonnes,
                SUM(CASE WHEN COALESCE(se.statut_lavage, 'BRUT') = 'BRUT' THEN se.poids_total_kg ELSE 0 END) / 1000 as tonnes_brut,
                SUM(CASE WHEN se.statut_lavage = 'LAVE' THEN se.poids_total_kg ELSE 0 END) / 1000 as tonnes_lave,
                SUM(CASE WHEN se.statut_lavage = 'GRENAILLES' THEN se.poids_total_kg ELSE 0 END) / 1000 as tonnes_gren
            FROM stock_emplacements se
            JOIN lots_bruts l ON se.lot_id = l.id
            LEFT JOIN ref_varietes v ON l.code_variete = v.code_variete
            WHERE se.is_active = TRUE AND l.is_active = TRUE AND se.nombre_unites > 0
            GROUP BY variete
            ORDER BY total_tonnes DESC
        """)
        
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        
        if rows:
            df = pd.DataFrame(rows)
            df.columns = ['Variété', 'Lots', 'Pallox', 'Total (T)', 
                         'Brut (T)', 'Lavé (T)', 'Gren. (T)']
            df['Lots'] = pd.to_numeric(df['Lots'], errors='coerce').fillna(0).astype(int)
            df['Pallox'] = pd.to_numeric(df['Pallox'], errors='coerce').fillna(0).astype(int)
            for col in ['Total (T)', 'Brut (T)', 'Lavé (T)', 'Gren. (T)']:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0).round(1)
            return df
        return pd.DataFrame()
        
    except Exception as e:
        st.error(f"❌ Erreur stock par variété : {str(e)}")
        return pd.DataFrame()

def get_stock_par_producteur():
    """Stock agrégé par producteur"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                COALESCE(p.nom, l.code_producteur, 'Non défini') as producteur,
                COUNT(DISTINCT se.lot_id) as nb_lots,
                SUM(se.nombre_unites) as total_pallox,
                SUM(se.poids_total_kg) / 1000 as total_tonnes,
                SUM(CASE WHEN COALESCE(se.statut_lavage, 'BRUT') = 'BRUT' THEN se.poids_total_kg ELSE 0 END) / 1000 as tonnes_brut,
                SUM(CASE WHEN se.statut_lavage = 'LAVE' THEN se.poids_total_kg ELSE 0 END) / 1000 as tonnes_lave
            FROM stock_emplacements se
            JOIN lots_bruts l ON se.lot_id = l.id
            LEFT JOIN ref_producteurs p ON l.code_producteur = p.code_producteur
            WHERE se.is_active = TRUE AND l.is_active = TRUE AND se.nombre_unites > 0
            GROUP BY producteur
            ORDER BY total_tonnes DESC
        """)
        
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        
        if rows:
            df = pd.DataFrame(rows)
            df.columns = ['Producteur', 'Lots', 'Pallox', 'Total (T)', 'Brut (T)', 'Lavé (T)']
            df['Lots'] = pd.to_numeric(df['Lots'], errors='coerce').fillna(0).astype(int)
            df['Pallox'] = pd.to_numeric(df['Pallox'], errors='coerce').fillna(0).astype(int)
            for col in ['Total (T)', 'Brut (T)', 'Lavé (T)']:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0).round(1)
            return df
        return pd.DataFrame()
        
    except Exception as e:
        st.error(f"❌ Erreur stock par producteur : {str(e)}")
        return pd.DataFrame()

# ============================================================
# 📜 FONCTIONS DE DONNÉES - HISTORIQUE
# ============================================================

def get_mouvements_globaux(jours=30, type_mvt=None):
    """Récupère les mouvements de stock"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        date_limite = datetime.now() - timedelta(days=jours)
        
        query = """
            SELECT 
                sm.created_at,
                sm.type_mouvement,
                l.code_lot_interne,
                COALESCE(v.nom_variete, l.code_variete) as variete,
                sm.site_origine,
                sm.emplacement_origine,
                sm.site_destination,
                sm.emplacement_destination,
                sm.quantite,
                sm.poids_kg,
                sm.user_action
            FROM stock_mouvements sm
            JOIN lots_bruts l ON sm.lot_id = l.id
            LEFT JOIN ref_varietes v ON l.code_variete = v.code_variete
            WHERE sm.created_at >= %s
        """
        params = [date_limite]
        
        if type_mvt and type_mvt != "Tous":
            query += " AND sm.type_mouvement = %s"
            params.append(type_mvt)
        
        query += " ORDER BY sm.created_at DESC LIMIT 500"
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        
        if rows:
            df = pd.DataFrame(rows)
            df.columns = ['Date', 'Type', 'Lot', 'Variété', 'Site Origine', 'Empl. Origine',
                         'Site Dest.', 'Empl. Dest.', 'Quantité', 'Poids (kg)', 'Utilisateur']
            df['Quantité'] = pd.to_numeric(df['Quantité'], errors='coerce').fillna(0).astype(int)
            df['Poids (kg)'] = pd.to_numeric(df['Poids (kg)'], errors='coerce').fillna(0).round(0)
            return df
        return pd.DataFrame()
        
    except Exception as e:
        st.error(f"❌ Erreur mouvements : {str(e)}")
        return pd.DataFrame()

def get_stats_mouvements(jours=30):
    """Statistiques des mouvements"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        date_limite = datetime.now() - timedelta(days=jours)
        
        cursor.execute("""
            SELECT 
                type_mouvement,
                COUNT(*) as nb_operations,
                COALESCE(SUM(poids_kg), 0) / 1000 as tonnage
            FROM stock_mouvements
            WHERE created_at >= %s
            GROUP BY type_mouvement
            ORDER BY nb_operations DESC
        """, (date_limite,))
        
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        
        if rows:
            df = pd.DataFrame(rows)
            df.columns = ['Type', 'Opérations', 'Tonnage (T)']
            df['Opérations'] = pd.to_numeric(df['Opérations'], errors='coerce').fillna(0).astype(int)
            df['Tonnage (T)'] = pd.to_numeric(df['Tonnage (T)'], errors='coerce').fillna(0).round(1)
            return df
        return pd.DataFrame()
        
    except Exception as e:
        return pd.DataFrame()

# ============================================================
# 🎨 INTERFACE - TITRE
# ============================================================

st.title("📊 Stock Global")
st.markdown("*Vue d'ensemble analytique du stock*")
st.markdown("---")

# ============================================================
# 📊 ONGLETS PRINCIPAUX
# ============================================================

tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📊 Tableau de Bord",
    "🏭 Capacités Sites", 
    "📦 Vue Stock",
    "📍 Vues Agrégées",
    "📜 Historique"
])

# ============================================================
# ONGLET 1 : TABLEAU DE BORD
# ============================================================

with tab1:
    # Charger les données
    kpis = get_stock_kpis()
    occupation = get_occupation_globale()
    alertes = get_alertes()
    
    if kpis:
        # ===== KPIs PRINCIPAUX =====
        st.subheader("📈 Indicateurs Clés")
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric(
                "🟢 Stock BRUT",
                f"{kpis['BRUT']['tonnes']:,.1f} T",
                f"{kpis['BRUT']['pallox']:,} pallox"
            )
        
        with col2:
            st.metric(
                "🧼 Stock LAVÉ",
                f"{kpis['LAVE']['tonnes']:,.1f} T",
                f"{kpis['LAVE']['pallox']:,} pallox"
            )
        
        with col3:
            st.metric(
                "🌾 Grenailles",
                f"{kpis['GRENAILLES']['tonnes']:,.1f} T",
                f"{kpis['GRENAILLES']['pallox']:,} pallox"
            )
        
        with col4:
            if occupation:
                emoji = get_status_emoji(occupation['taux'])
                st.metric(
                    f"{emoji} Occupation",
                    f"{occupation['taux']:.1f}%",
                    f"{occupation['disponible']:,} places libres"
                )
        
        st.markdown("---")
        
        # ===== KPIs SECONDAIRES =====
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("📦 Total Stock", f"{kpis['total']['tonnes']:,.1f} T")
        with col2:
            st.metric("🎯 Total Pallox", f"{kpis['total']['pallox']:,}")
        with col3:
            st.metric("📋 Lots en Stock", f"{kpis['total']['lots']}")
        with col4:
            st.metric("🏭 Sites Utilisés", f"{kpis['total']['sites']}")
        
        st.markdown("---")
        
        # ===== RÉPARTITION PAR STATUT =====
        st.subheader("📊 Répartition par Statut")
        
        col1, col2, col3 = st.columns(3)
        
        total_tonnes = kpis['total']['tonnes'] if kpis['total']['tonnes'] > 0 else 1
        
        with col1:
            pct_brut = (kpis['BRUT']['tonnes'] / total_tonnes * 100)
            st.markdown(f"""
            <div class="status-card status-brut">
                <h3>🟢 BRUT</h3>
                <h2>{pct_brut:.1f}%</h2>
                <p>{kpis['BRUT']['tonnes']:,.1f} T | {kpis['BRUT']['pallox']:,} pallox</p>
            </div>
            """, unsafe_allow_html=True)
        
        with col2:
            pct_lave = (kpis['LAVE']['tonnes'] / total_tonnes * 100)
            st.markdown(f"""
            <div class="status-card status-lave">
                <h3>🧼 LAVÉ</h3>
                <h2>{pct_lave:.1f}%</h2>
                <p>{kpis['LAVE']['tonnes']:,.1f} T | {kpis['LAVE']['pallox']:,} pallox</p>
            </div>
            """, unsafe_allow_html=True)
        
        with col3:
            pct_gren = (kpis['GRENAILLES']['tonnes'] / total_tonnes * 100)
            st.markdown(f"""
            <div class="status-card status-gren">
                <h3>🌾 GRENAILLES</h3>
                <h2>{pct_gren:.1f}%</h2>
                <p>{kpis['GRENAILLES']['tonnes']:,.1f} T | {kpis['GRENAILLES']['pallox']:,} pallox</p>
            </div>
            """, unsafe_allow_html=True)
        
        st.markdown("---")
        
        # ===== ALERTES =====
        col1, col2 = st.columns([1, 1])
        
        with col1:
            st.subheader("⚠️ Alertes Actives")
            
            if alertes:
                for alerte in alertes:
                    css_class = f"alert-{alerte['type']}"
                    st.markdown(f"""
                    <div class="alert-box {css_class}">
                        {alerte['icon']} {alerte['message']}
                    </div>
                    """, unsafe_allow_html=True)
            else:
                st.success("✅ Aucune alerte - Tout est normal !")
        
        with col2:
            st.subheader("🏆 Top 10 Sites")
            
            top_sites = get_top_sites(10)
            if not top_sites.empty:
                st.dataframe(
                    top_sites,
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "Tonnes": st.column_config.NumberColumn(format="%.1f T")
                    }
                )
            else:
                st.info("Aucun site avec stock")

# ============================================================
# ONGLET 2 : CAPACITÉS SITES
# ============================================================

with tab2:
    st.subheader("🏭 Capacités par Site / Emplacement")
    
    df_capacites = get_capacites_sites()
    
    if not df_capacites.empty:
        # Filtre par site
        sites = ["Tous"] + sorted(df_capacites['Site'].unique().tolist())
        filtre_site = st.selectbox("Filtrer par site", sites, key="filtre_site_capa")
        
        df_filtered = df_capacites.copy()
        if filtre_site != "Tous":
            df_filtered = df_filtered[df_filtered['Site'] == filtre_site]
        
        st.markdown("---")
        
        # Affichage avec barres de progression
        for site in df_filtered['Site'].unique():
            with st.expander(f"📍 {site}", expanded=(filtre_site != "Tous")):
                df_site = df_filtered[df_filtered['Site'] == site]
                
                # Totaux du site
                total_capa = df_site['Capacité Max'].sum()
                total_occupe = df_site['Occupé'].sum()
                taux_site = (total_occupe / total_capa * 100) if total_capa > 0 else 0
                
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("Capacité", f"{total_capa:,} pallox")
                with col2:
                    st.metric("Occupé", f"{total_occupe:,} pallox")
                with col3:
                    st.metric("Disponible", f"{total_capa - total_occupe:,} pallox")
                with col4:
                    emoji = get_status_emoji(taux_site)
                    st.metric(f"{emoji} Taux", f"{taux_site:.1f}%")
                
                st.markdown("---")
                
                # Tableau détaillé
                df_display = df_site[['Emplacement', 'Nom', 'Capacité Max', 'Occupé', 
                                      'Disponible', 'Taux (%)', 'Tonnage', 'Nb Lots']].copy()
                
                st.dataframe(
                    df_display,
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "Taux (%)": st.column_config.ProgressColumn(
                            "Taux (%)",
                            min_value=0,
                            max_value=100,
                            format="%.1f%%"
                        ),
                        "Tonnage": st.column_config.NumberColumn(format="%.1f T")
                    }
                )
        
        # Export
        st.markdown("---")
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            df_capacites.to_excel(writer, index=False, sheet_name='Capacités')
        
        st.download_button(
            "📥 Exporter les capacités (Excel)",
            buffer.getvalue(),
            f"capacites_sites_{datetime.now().strftime('%Y%m%d')}.xlsx",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True
        )
    else:
        st.warning("⚠️ Aucune donnée de capacité")

# ============================================================
# ONGLET 3 : VUE STOCK COMPLÈTE
# ============================================================

with tab3:
    st.subheader("📦 Vue Stock Complète")
    
    df_stock = get_stock_complet()
    
    if not df_stock.empty:
        # Filtres
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            statuts = ["Tous", "BRUT", "LAVE", "GRENAILLES"]
            filtre_statut = st.selectbox("Statut", statuts, key="filtre_statut_stock")
        
        with col2:
            sites = ["Tous"] + sorted(df_stock['site_stockage'].unique().tolist())
            filtre_site_stock = st.selectbox("Site", sites, key="filtre_site_stock")
        
        with col3:
            varietes = ["Toutes"] + sorted(df_stock['variete'].dropna().unique().tolist())
            filtre_variete = st.selectbox("Variété", varietes, key="filtre_variete_stock")
        
        with col4:
            ages = ["Tous", "< 30 jours", "30-60 jours", "> 60 jours"]
            filtre_age = st.selectbox("Âge", ages, key="filtre_age_stock")
        
        # Appliquer filtres
        df_filtered = df_stock.copy()
        
        if filtre_statut != "Tous":
            df_filtered = df_filtered[df_filtered['statut_lavage'] == filtre_statut]
        
        if filtre_site_stock != "Tous":
            df_filtered = df_filtered[df_filtered['site_stockage'] == filtre_site_stock]
        
        if filtre_variete != "Toutes":
            df_filtered = df_filtered[df_filtered['variete'] == filtre_variete]
        
        if filtre_age == "< 30 jours":
            df_filtered = df_filtered[df_filtered['age_jours'] < 30]
        elif filtre_age == "30-60 jours":
            df_filtered = df_filtered[(df_filtered['age_jours'] >= 30) & (df_filtered['age_jours'] <= 60)]
        elif filtre_age == "> 60 jours":
            df_filtered = df_filtered[df_filtered['age_jours'] > 60]
        
        st.markdown("---")
        
        # Résumé
        total_tonnes = df_filtered['poids_total_kg'].sum() / 1000
        total_pallox = df_filtered['nombre_unites'].sum()
        nb_lots = df_filtered['lot_id'].nunique()
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.info(f"**{len(df_filtered)}** emplacements")
        with col2:
            st.info(f"**{total_pallox:,.0f}** pallox | **{total_tonnes:,.1f}** T")
        with col3:
            st.info(f"**{nb_lots}** lots distincts")
        
        # Tableau
        df_display = df_filtered.copy()
        df_display['Tonnes'] = df_display['poids_total_kg'] / 1000
        df_display['Calibre'] = df_display.apply(
            lambda r: f"{int(r['calibre_min'])}-{int(r['calibre_max'])}" 
            if pd.notna(r['calibre_min']) and pd.notna(r['calibre_max']) else "", 
            axis=1
        )
        
        # Emoji statut
        df_display['Statut'] = df_display['statut_lavage'].apply(
            lambda s: "🟢 BRUT" if s == "BRUT" else ("🧼 LAVÉ" if s == "LAVE" else "🌾 GREN")
        )
        
        columns_display = ['code_lot_interne', 'variete', 'producteur', 'site_stockage', 
                          'emplacement_stockage', 'nombre_unites', 'Tonnes', 'Statut', 
                          'Calibre', 'age_jours']
        
        st.dataframe(
            df_display[columns_display].rename(columns={
                'code_lot_interne': 'Lot',
                'variete': 'Variété',
                'producteur': 'Producteur',
                'site_stockage': 'Site',
                'emplacement_stockage': 'Emplacement',
                'nombre_unites': 'Pallox',
                'age_jours': 'Âge (j)'
            }),
            use_container_width=True,
            hide_index=True,
            column_config={
                "Tonnes": st.column_config.NumberColumn(format="%.1f")
            }
        )
        
        # Exports
        st.markdown("---")
        col1, col2 = st.columns(2)
        
        with col1:
            csv = df_filtered.to_csv(index=False).encode('utf-8')
            st.download_button(
                "📥 Exporter CSV",
                csv,
                f"stock_complet_{datetime.now().strftime('%Y%m%d')}.csv",
                "text/csv",
                use_container_width=True
            )
        
        with col2:
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                df_filtered.to_excel(writer, index=False, sheet_name='Stock')
            
            st.download_button(
                "📥 Exporter Excel",
                buffer.getvalue(),
                f"stock_complet_{datetime.now().strftime('%Y%m%d')}.xlsx",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )
    else:
        st.warning("⚠️ Aucun stock trouvé")

# ============================================================
# ONGLET 4 : VUES AGRÉGÉES
# ============================================================

with tab4:
    subtab1, subtab2, subtab3 = st.tabs(["📍 Par Site", "🌱 Par Variété", "👤 Par Producteur"])
    
    with subtab1:
        st.subheader("📍 Stock par Site")
        
        df_site = get_stock_par_site()
        
        if not df_site.empty:
            st.dataframe(
                df_site,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Total (T)": st.column_config.NumberColumn(format="%.1f"),
                    "Brut (T)": st.column_config.NumberColumn(format="%.1f"),
                    "Lavé (T)": st.column_config.NumberColumn(format="%.1f"),
                    "Gren. (T)": st.column_config.NumberColumn(format="%.1f")
                }
            )
            
            col1, col2 = st.columns(2)
            with col1:
                st.info(f"**{len(df_site)}** sites utilisés")
            with col2:
                st.info(f"**{df_site['Total (T)'].sum():,.1f}** T total")
            
            # Export
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                df_site.to_excel(writer, index=False, sheet_name='Par Site')
            
            st.download_button(
                "📥 Exporter",
                buffer.getvalue(),
                f"stock_par_site_{datetime.now().strftime('%Y%m%d')}.xlsx",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
    
    with subtab2:
        st.subheader("🌱 Stock par Variété")
        
        df_variete = get_stock_par_variete()
        
        if not df_variete.empty:
            st.dataframe(
                df_variete,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Total (T)": st.column_config.NumberColumn(format="%.1f"),
                    "Brut (T)": st.column_config.NumberColumn(format="%.1f"),
                    "Lavé (T)": st.column_config.NumberColumn(format="%.1f"),
                    "Gren. (T)": st.column_config.NumberColumn(format="%.1f")
                }
            )
            
            col1, col2 = st.columns(2)
            with col1:
                st.info(f"**{len(df_variete)}** variétés en stock")
            with col2:
                st.info(f"**{df_variete['Lots'].sum()}** lots total")
            
            # Export
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                df_variete.to_excel(writer, index=False, sheet_name='Par Variété')
            
            st.download_button(
                "📥 Exporter",
                buffer.getvalue(),
                f"stock_par_variete_{datetime.now().strftime('%Y%m%d')}.xlsx",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
    
    with subtab3:
        st.subheader("👤 Stock par Producteur")
        
        df_producteur = get_stock_par_producteur()
        
        if not df_producteur.empty:
            st.dataframe(
                df_producteur,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Total (T)": st.column_config.NumberColumn(format="%.1f"),
                    "Brut (T)": st.column_config.NumberColumn(format="%.1f"),
                    "Lavé (T)": st.column_config.NumberColumn(format="%.1f")
                }
            )
            
            col1, col2 = st.columns(2)
            with col1:
                st.info(f"**{len(df_producteur)}** producteurs")
            with col2:
                st.info(f"**{df_producteur['Total (T)'].sum():,.1f}** T total")
            
            # Export
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                df_producteur.to_excel(writer, index=False, sheet_name='Par Producteur')
            
            st.download_button(
                "📥 Exporter",
                buffer.getvalue(),
                f"stock_par_producteur_{datetime.now().strftime('%Y%m%d')}.xlsx",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

# ============================================================
# ONGLET 5 : HISTORIQUE MOUVEMENTS
# ============================================================

with tab5:
    st.subheader("📜 Historique des Mouvements")
    
    # Filtres
    col1, col2 = st.columns(2)
    
    with col1:
        periodes = {"7 jours": 7, "30 jours": 30, "90 jours": 90, "365 jours": 365}
        periode_label = st.selectbox("Période", list(periodes.keys()), index=1)
        jours = periodes[periode_label]
    
    with col2:
        types_mvt = ["Tous", "AJOUT", "TRANSFERT", "MODIFICATION", "SUPPRESSION", 
                     "LAVAGE_CREATION", "LAVAGE_DEDUCTION"]
        type_filtre = st.selectbox("Type de mouvement", types_mvt)
    
    st.markdown("---")
    
    # Stats
    df_stats = get_stats_mouvements(jours)
    
    if not df_stats.empty:
        st.markdown("##### 📊 Statistiques par type")
        
        cols = st.columns(len(df_stats))
        for i, (_, row) in enumerate(df_stats.iterrows()):
            with cols[i % len(cols)]:
                st.metric(row['Type'], f"{row['Opérations']} ops", f"{row['Tonnage (T)']:.1f} T")
    
    st.markdown("---")
    
    # Tableau mouvements
    df_mvt = get_mouvements_globaux(jours, type_filtre if type_filtre != "Tous" else None)
    
    if not df_mvt.empty:
        st.dataframe(
            df_mvt,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Date": st.column_config.DatetimeColumn(format="DD/MM/YY HH:mm"),
                "Poids (kg)": st.column_config.NumberColumn(format="%.0f")
            }
        )
        
        st.info(f"**{len(df_mvt)}** mouvements affichés (max 500)")
        
        # Export
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            df_mvt.to_excel(writer, index=False, sheet_name='Mouvements')
        
        st.download_button(
            "📥 Exporter l'historique",
            buffer.getvalue(),
            f"mouvements_{datetime.now().strftime('%Y%m%d')}.xlsx",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True
        )
    else:
        st.info(f"Aucun mouvement sur les {jours} derniers jours")

# ============================================================
# FOOTER
# ============================================================

show_footer()
