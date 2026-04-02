import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from database import get_connection
from components import show_footer
from auth import require_access, is_admin
import io
import time
import re

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
SEUIL_SITE_PLEIN = 85
SEUIL_SITE_CRITIQUE = 95
SEUIL_LOT_ANCIEN = 60
SEUIL_LOT_ATTENTION = 45
SEUIL_GRENAILLES = 10000

# ============================================================
# 🔧 FONCTIONS UTILITAIRES
# ============================================================

def format_number_fr(n):
    if pd.isna(n):
        return "0"
    return f"{int(n):,}".replace(",", " ")

def format_float_fr(n, decimals=1):
    if pd.isna(n):
        return "0"
    return f"{n:,.{decimals}f}".replace(",", " ").replace(".", ",")

def get_color_by_percent(pct):
    if pct >= SEUIL_SITE_CRITIQUE:
        return "#f44336"
    elif pct >= SEUIL_SITE_PLEIN:
        return "#ff9800"
    elif pct >= 70:
        return "#ffc107"
    else:
        return "#4caf50"

def get_status_emoji(pct):
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
    try:
        conn = get_connection()
        cursor = conn.cursor()
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
            'BRUT':      {'lots': 0, 'pallox': 0, 'tonnes': 0},
            'LAVE':      {'lots': 0, 'pallox': 0, 'tonnes': 0},
            'GRENAILLES':{'lots': 0, 'pallox': 0, 'tonnes': 0}
        }
        total_tonnes = total_pallox = total_lots = 0
        for row in rows:
            statut = row['statut'] if row['statut'] else 'BRUT'
            if statut in result:
                result[statut]['lots']   = int(row['nb_lots'] or 0)
                result[statut]['pallox'] = int(row['total_pallox'] or 0)
                result[statut]['tonnes'] = float(row['total_kg'] or 0) / 1000
                total_tonnes += result[statut]['tonnes']
                total_pallox += result[statut]['pallox']
                total_lots   += result[statut]['lots']
        cursor.execute("""
            SELECT COUNT(DISTINCT se.site_stockage) as nb_sites
            FROM stock_emplacements se JOIN lots_bruts l ON se.lot_id = l.id
            WHERE se.is_active = TRUE AND l.is_active = TRUE AND se.nombre_unites > 0
        """)
        nb_sites = cursor.fetchone()['nb_sites']
        cursor.execute("""
            SELECT COUNT(*) as nb_emplacements
            FROM stock_emplacements se JOIN lots_bruts l ON se.lot_id = l.id
            WHERE se.is_active = TRUE AND l.is_active = TRUE AND se.nombre_unites > 0
        """)
        nb_emplacements = cursor.fetchone()['nb_emplacements']
        cursor.close()
        conn.close()
        result['total'] = {
            'tonnes': total_tonnes, 'pallox': total_pallox,
            'lots': total_lots, 'sites': nb_sites, 'emplacements': nb_emplacements
        }
        return result
    except Exception as e:
        st.error(f"❌ Erreur KPIs : {str(e)}")
        return None

def get_occupation_globale():
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT COALESCE(SUM(capacite_max_pallox), 0) as capacite_totale,
                   COALESCE(SUM(capacite_max_tonnes), 0) as capacite_tonnes
            FROM ref_sites_stockage WHERE is_active = TRUE
        """)
        capacites = cursor.fetchone()
        capacite_totale = int(capacites['capacite_totale'] or 0)
        cursor.execute("""
            SELECT COALESCE(SUM(se.nombre_unites), 0) as occupe
            FROM stock_emplacements se JOIN lots_bruts l ON se.lot_id = l.id
            WHERE se.is_active = TRUE AND l.is_active = TRUE
        """)
        occupe = int(cursor.fetchone()['occupe'] or 0)
        cursor.close()
        conn.close()
        taux = (occupe / capacite_totale * 100) if capacite_totale > 0 else 0
        return {
            'capacite': capacite_totale, 'occupe': occupe,
            'disponible': max(0, capacite_totale - occupe), 'taux': round(taux, 1)
        }
    except Exception as e:
        st.error(f"❌ Erreur occupation : {str(e)}")
        return None

def get_alertes():
    try:
        conn = get_connection()
        cursor = conn.cursor()
        alertes = []
        cursor.execute("""
            SELECT rs.code_site, rs.capacite_max_pallox,
                   COALESCE(SUM(CASE WHEN l.is_active = TRUE THEN se.nombre_unites ELSE 0 END), 0) as occupe
            FROM ref_sites_stockage rs
            LEFT JOIN stock_emplacements se ON rs.code_site = se.site_stockage AND se.is_active = TRUE
            LEFT JOIN lots_bruts l ON se.lot_id = l.id
            WHERE rs.is_active = TRUE AND rs.capacite_max_pallox > 0
            GROUP BY rs.code_site, rs.capacite_max_pallox
            HAVING (COALESCE(SUM(CASE WHEN l.is_active = TRUE THEN se.nombre_unites ELSE 0 END), 0)::float / rs.capacite_max_pallox * 100) >= %s
        """, (SEUIL_SITE_CRITIQUE,))
        for row in cursor.fetchall():
            taux = (row['occupe'] / row['capacite_max_pallox'] * 100) if row['capacite_max_pallox'] > 0 else 0
            alertes.append({'type': 'critical', 'icon': '🔴',
                'message': f"Site {row['code_site']} CRITIQUE : {taux:.0f}% occupé ({row['occupe']}/{row['capacite_max_pallox']} pallox)"})
        cursor.execute("""
            SELECT rs.code_site, rs.capacite_max_pallox,
                   COALESCE(SUM(CASE WHEN l.is_active = TRUE THEN se.nombre_unites ELSE 0 END), 0) as occupe
            FROM ref_sites_stockage rs
            LEFT JOIN stock_emplacements se ON rs.code_site = se.site_stockage AND se.is_active = TRUE
            LEFT JOIN lots_bruts l ON se.lot_id = l.id
            WHERE rs.is_active = TRUE AND rs.capacite_max_pallox > 0
            GROUP BY rs.code_site, rs.capacite_max_pallox
            HAVING (COALESCE(SUM(CASE WHEN l.is_active = TRUE THEN se.nombre_unites ELSE 0 END), 0)::float / rs.capacite_max_pallox * 100) >= %s
               AND (COALESCE(SUM(CASE WHEN l.is_active = TRUE THEN se.nombre_unites ELSE 0 END), 0)::float / rs.capacite_max_pallox * 100) < %s
        """, (SEUIL_SITE_PLEIN, SEUIL_SITE_CRITIQUE))
        for row in cursor.fetchall():
            taux = (row['occupe'] / row['capacite_max_pallox'] * 100) if row['capacite_max_pallox'] > 0 else 0
            alertes.append({'type': 'warning', 'icon': '🟠',
                'message': f"Site {row['code_site']} quasi plein : {taux:.0f}% occupé"})
        cursor.execute("""
            SELECT l.code_lot_interne, COALESCE(v.nom_variete, l.code_variete) as variete, l.age_jours
            FROM lots_bruts l LEFT JOIN ref_varietes v ON l.code_variete = v.code_variete
            WHERE l.is_active = TRUE AND l.age_jours >= %s
              AND EXISTS (SELECT 1 FROM stock_emplacements se
                          WHERE se.lot_id = l.id AND se.is_active = TRUE AND se.nombre_unites > 0)
            ORDER BY l.age_jours DESC LIMIT 5
        """, (SEUIL_LOT_ANCIEN,))
        for row in cursor.fetchall():
            alertes.append({'type': 'warning', 'icon': '🟡',
                'message': f"Lot {row['code_lot_interne']} ({row['variete']}) : {row['age_jours']} jours en stock"})
        cursor.execute("""
            SELECT COALESCE(SUM(se.poids_total_kg), 0) as poids_grenailles
            FROM stock_emplacements se JOIN lots_bruts l ON se.lot_id = l.id
            WHERE se.is_active = TRUE AND l.is_active = TRUE AND se.statut_lavage = 'GRENAILLES'
        """)
        poids_gren = float(cursor.fetchone()['poids_grenailles'] or 0)
        if poids_gren >= SEUIL_GRENAILLES:
            alertes.append({'type': 'info', 'icon': '🌾',
                'message': f"Stock grenailles élevé : {poids_gren/1000:.1f} T à traiter"})
        cursor.close()
        conn.close()
        return alertes
    except Exception as e:
        st.error(f"❌ Erreur alertes : {str(e)}")
        return []

def get_top_sites(limit=10):
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT se.site_stockage, COUNT(DISTINCT se.lot_id) as nb_lots,
                   SUM(se.nombre_unites) as total_pallox, SUM(se.poids_total_kg) / 1000 as total_tonnes
            FROM stock_emplacements se JOIN lots_bruts l ON se.lot_id = l.id
            WHERE se.is_active = TRUE AND l.is_active = TRUE AND se.nombre_unites > 0
            GROUP BY se.site_stockage ORDER BY total_tonnes DESC LIMIT %s
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
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT rs.code_site, rs.code_emplacement, rs.nom_complet,
                   rs.capacite_max_pallox, rs.capacite_max_tonnes,
                   COALESCE(SUM(CASE WHEN l.is_active = TRUE THEN se.nombre_unites ELSE 0 END), 0) as occupe_pallox,
                   COALESCE(SUM(CASE WHEN l.is_active = TRUE THEN se.poids_total_kg ELSE 0 END), 0) as occupe_kg,
                   COUNT(DISTINCT CASE WHEN l.is_active = TRUE THEN se.lot_id ELSE NULL END) as nb_lots
            FROM ref_sites_stockage rs
            LEFT JOIN stock_emplacements se ON rs.code_site = se.site_stockage
                AND rs.code_emplacement = se.emplacement_stockage AND se.is_active = TRUE
            LEFT JOIN lots_bruts l ON se.lot_id = l.id
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
            for col in ['Capacité Max', 'Occupé', 'Nb Lots']:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0).astype(int)
            df['Poids (kg)'] = pd.to_numeric(df['Poids (kg)'], errors='coerce').fillna(0)
            df['Cap. Tonnes'] = pd.to_numeric(df['Cap. Tonnes'], errors='coerce').fillna(0)
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
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT l.id as lot_id, l.code_lot_interne, l.nom_usage,
                   COALESCE(v.nom_variete, l.code_variete) as variete,
                   COALESCE(p.nom, l.code_producteur) as producteur,
                   se.site_stockage, se.emplacement_stockage,
                   se.nombre_unites, se.poids_total_kg,
                   COALESCE(se.statut_lavage, 'BRUT') as statut_lavage,
                   se.type_conditionnement, l.calibre_min, l.calibre_max,
                   l.age_jours, l.date_entree_stock
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
            for col in ['nombre_unites', 'poids_total_kg', 'calibre_min', 'calibre_max', 'age_jours']:
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
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT se.site_stockage,
                   COUNT(DISTINCT se.emplacement_stockage) as nb_emplacements,
                   COUNT(DISTINCT se.lot_id) as nb_lots,
                   SUM(se.nombre_unites) as total_pallox,
                   SUM(se.poids_total_kg) / 1000 as total_tonnes,
                   SUM(CASE WHEN COALESCE(se.statut_lavage,'BRUT')='BRUT' THEN se.poids_total_kg ELSE 0 END)/1000 as tonnes_brut,
                   SUM(CASE WHEN se.statut_lavage='LAVE' THEN se.poids_total_kg ELSE 0 END)/1000 as tonnes_lave,
                   SUM(CASE WHEN se.statut_lavage='GRENAILLES' THEN se.poids_total_kg ELSE 0 END)/1000 as tonnes_gren
            FROM stock_emplacements se JOIN lots_bruts l ON se.lot_id = l.id
            WHERE se.is_active = TRUE AND l.is_active = TRUE AND se.nombre_unites > 0
            GROUP BY se.site_stockage ORDER BY total_tonnes DESC
        """)
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        if rows:
            df = pd.DataFrame(rows)
            df.columns = ['Site','Emplacements','Lots','Pallox','Total (T)','Brut (T)','Lavé (T)','Gren. (T)']
            for col in ['Emplacements','Lots','Pallox']:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0).astype(int)
            for col in ['Total (T)','Brut (T)','Lavé (T)','Gren. (T)']:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0).round(1)
            return df
        return pd.DataFrame()
    except Exception as e:
        st.error(f"❌ Erreur stock par site : {str(e)}")
        return pd.DataFrame()

def get_stock_par_variete():
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT COALESCE(v.nom_variete, l.code_variete, 'Non défini') as variete,
                   COUNT(DISTINCT se.lot_id) as nb_lots,
                   SUM(se.nombre_unites) as total_pallox,
                   SUM(se.poids_total_kg)/1000 as total_tonnes,
                   SUM(CASE WHEN COALESCE(se.statut_lavage,'BRUT')='BRUT' THEN se.poids_total_kg ELSE 0 END)/1000 as tonnes_brut,
                   SUM(CASE WHEN se.statut_lavage='LAVE' THEN se.poids_total_kg ELSE 0 END)/1000 as tonnes_lave,
                   SUM(CASE WHEN se.statut_lavage='GRENAILLES' THEN se.poids_total_kg ELSE 0 END)/1000 as tonnes_gren
            FROM stock_emplacements se JOIN lots_bruts l ON se.lot_id = l.id
            LEFT JOIN ref_varietes v ON l.code_variete = v.code_variete
            WHERE se.is_active = TRUE AND l.is_active = TRUE AND se.nombre_unites > 0
            GROUP BY variete ORDER BY total_tonnes DESC
        """)
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        if rows:
            df = pd.DataFrame(rows)
            df.columns = ['Variété','Lots','Pallox','Total (T)','Brut (T)','Lavé (T)','Gren. (T)']
            df['Lots'] = pd.to_numeric(df['Lots'], errors='coerce').fillna(0).astype(int)
            df['Pallox'] = pd.to_numeric(df['Pallox'], errors='coerce').fillna(0).astype(int)
            for col in ['Total (T)','Brut (T)','Lavé (T)','Gren. (T)']:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0).round(1)
            return df
        return pd.DataFrame()
    except Exception as e:
        st.error(f"❌ Erreur stock par variété : {str(e)}")
        return pd.DataFrame()

def get_stock_par_producteur():
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT COALESCE(p.nom, l.code_producteur, 'Non défini') as producteur,
                   COUNT(DISTINCT se.lot_id) as nb_lots,
                   SUM(se.nombre_unites) as total_pallox,
                   SUM(se.poids_total_kg)/1000 as total_tonnes,
                   SUM(CASE WHEN COALESCE(se.statut_lavage,'BRUT')='BRUT' THEN se.poids_total_kg ELSE 0 END)/1000 as tonnes_brut,
                   SUM(CASE WHEN se.statut_lavage='LAVE' THEN se.poids_total_kg ELSE 0 END)/1000 as tonnes_lave
            FROM stock_emplacements se JOIN lots_bruts l ON se.lot_id = l.id
            LEFT JOIN ref_producteurs p ON l.code_producteur = p.code_producteur
            WHERE se.is_active = TRUE AND l.is_active = TRUE AND se.nombre_unites > 0
            GROUP BY producteur ORDER BY total_tonnes DESC
        """)
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        if rows:
            df = pd.DataFrame(rows)
            df.columns = ['Producteur','Lots','Pallox','Total (T)','Brut (T)','Lavé (T)']
            df['Lots'] = pd.to_numeric(df['Lots'], errors='coerce').fillna(0).astype(int)
            df['Pallox'] = pd.to_numeric(df['Pallox'], errors='coerce').fillna(0).astype(int)
            for col in ['Total (T)','Brut (T)','Lavé (T)']:
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
    try:
        conn = get_connection()
        cursor = conn.cursor()
        date_limite = datetime.now() - timedelta(days=jours)
        query = """
            SELECT sm.created_at, sm.type_mouvement, l.code_lot_interne,
                   COALESCE(v.nom_variete, l.code_variete) as variete,
                   sm.site_origine, sm.emplacement_origine,
                   sm.site_destination, sm.emplacement_destination,
                   sm.quantite, sm.poids_kg, sm.user_action
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
            df.columns = ['Date','Type','Lot','Variété','Site Origine','Empl. Origine',
                          'Site Dest.','Empl. Dest.','Quantité','Poids (kg)','Utilisateur']
            df['Quantité'] = pd.to_numeric(df['Quantité'], errors='coerce').fillna(0).astype(int)
            df['Poids (kg)'] = pd.to_numeric(df['Poids (kg)'], errors='coerce').fillna(0).round(0)
            return df
        return pd.DataFrame()
    except Exception as e:
        st.error(f"❌ Erreur mouvements : {str(e)}")
        return pd.DataFrame()

def get_stats_mouvements(jours=30):
    try:
        conn = get_connection()
        cursor = conn.cursor()
        date_limite = datetime.now() - timedelta(days=jours)
        cursor.execute("""
            SELECT type_mouvement, COUNT(*) as nb_operations,
                   COALESCE(SUM(poids_kg), 0) / 1000 as tonnage
            FROM stock_mouvements
            WHERE created_at >= %s
            GROUP BY type_mouvement ORDER BY nb_operations DESC
        """, (date_limite,))
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        if rows:
            df = pd.DataFrame(rows)
            df.columns = ['Type','Opérations','Tonnage (T)']
            df['Opérations'] = pd.to_numeric(df['Opérations'], errors='coerce').fillna(0).astype(int)
            df['Tonnage (T)'] = pd.to_numeric(df['Tonnage (T)'], errors='coerce').fillna(0).round(1)
            return df
        return pd.DataFrame()
    except Exception:
        return pd.DataFrame()

# ============================================================
# 📅 FONCTIONS STOCK À DATE
# ============================================================

def _parser_notes_modification(notes):
    """
    Parse le champ notes d'un mouvement MODIFICATION.
    Format : "Quantité: avant+après | Poids: avant+aprèskg"
    Ex : "Quantité: 10+11 | Poids: 19000+20900kg"
    Retourne (qty_apres, pds_apres_kg) — la valeur APRÈS qui est dans le champ
    et (qty_avant, pds_avant_kg) — la valeur AVANT pour annuler.
    """
    if not notes:
        return None, None, None, None
    try:
        m_qty = re.search(r'Quantit[eé]\s*:\s*(\d+)\s*\+\s*(\d+)', notes, re.IGNORECASE)
        m_pds = re.search(r'Poids\s*:\s*([\d.]+)\s*\+\s*([\d.]+)', notes, re.IGNORECASE)
        qty_avant  = int(m_qty.group(1))   if m_qty else None
        qty_apres  = int(m_qty.group(2))   if m_qty else None
        pds_avant  = float(m_pds.group(1)) if m_pds else None
        pds_apres  = float(m_pds.group(2)) if m_pds else None
        return qty_avant, qty_apres, pds_avant, pds_apres
    except Exception:
        return None, None, None, None


def get_stock_a_date(date_cible_ts):
    """
    Reconstruit le stock à une date donnée.

    Stratégie : partir de l'état ACTUEL de stock_emplacements (source de vérité),
    puis annuler tous les mouvements postérieurs à date_cible_ts.

    Annulation par type :
      AJOUT        → soustraire qty/pds de site_destination/emplacement_destination
      SUPPRESSION  → ajouter qty/pds sur site_origine/emplacement_origine
      TRANSFERT    → ajouter sur origine, soustraire sur destination
      MODIFICATION → lire notes "avant+après", recalculer le delta et l'annuler
                     (si notes non parsable : mouvement ignoré avec avertissement comptabilisé)
    """
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()

        # 1. État actuel de tous les emplacements (actifs ou non, pour remonter l'historique)
        cursor.execute("""
            SELECT se.lot_id,
                   lb.code_lot_interne, lb.nom_usage, lb.code_variete,
                   se.site_stockage, se.emplacement_stockage,
                   se.nombre_unites, se.poids_total_kg,
                   se.type_conditionnement
            FROM stock_emplacements se
            JOIN lots_bruts lb ON lb.id = se.lot_id
        """)
        empl_rows = cursor.fetchall()

        stock = {}   # (lot_id, site, empl) → {nombre_unites, poids_total_kg}
        meta  = {}   # (lot_id, site, empl) → infos affichage

        for r in empl_rows:
            k = (r['lot_id'], str(r['site_stockage'] or ''), str(r['emplacement_stockage'] or ''))
            stock[k] = {
                'nombre_unites':  float(r['nombre_unites'] or 0),
                'poids_total_kg': float(r['poids_total_kg'] or 0),
            }
            meta[k] = {
                'code_lot_interne':    r['code_lot_interne'],
                'nom_usage':           r['nom_usage'],
                'code_variete':        r['code_variete'],
                'type_conditionnement': r['type_conditionnement'],
            }

        # 2. Mouvements POSTÉRIEURS à la date cible (à annuler, du plus récent au plus ancien)
        cursor.execute("""
            SELECT lot_id, type_mouvement,
                   site_origine, emplacement_origine,
                   site_destination, emplacement_destination,
                   COALESCE(quantite, 0)   AS quantite,
                   COALESCE(poids_kg, 0.0) AS poids_kg,
                   notes, created_at
            FROM stock_mouvements
            WHERE created_at > %s
            ORDER BY created_at DESC
        """, (date_cible_ts,))
        mvt_rows = cursor.fetchall()
        cursor.close()
        conn.close()

        nb_modif_non_parsees = 0

        def _ensure(k):
            if k not in stock:
                stock[k] = {'nombre_unites': 0.0, 'poids_total_kg': 0.0}

        for r in mvt_rows:
            t   = r['type_mouvement']
            lid = r['lot_id']
            qty = float(r['quantite'])
            pds = float(r['poids_kg'])
            ori = (lid, str(r['site_origine']    or ''), str(r['emplacement_origine']    or ''))
            dst = (lid, str(r['site_destination'] or ''), str(r['emplacement_destination'] or ''))

            if t == 'AJOUT':
                _ensure(dst)
                stock[dst]['nombre_unites']  -= qty
                stock[dst]['poids_total_kg'] -= pds

            elif t == 'SUPPRESSION':
                _ensure(ori)
                stock[ori]['nombre_unites']  += qty
                stock[ori]['poids_total_kg'] += pds

            elif t == 'TRANSFERT':
                _ensure(ori); _ensure(dst)
                stock[ori]['nombre_unites']  += qty
                stock[ori]['poids_total_kg'] += pds
                stock[dst]['nombre_unites']  -= qty
                stock[dst]['poids_total_kg'] -= pds

            elif t == 'MODIFICATION':
                # qty/pds dans le champ = valeur APRÈS la modif
                # On lit notes pour obtenir la valeur AVANT
                qty_avant, qty_apres, pds_avant, pds_apres = _parser_notes_modification(r['notes'])
                if qty_avant is not None and pds_avant is not None:
                    # delta appliqué par la modif = apres - avant
                    # Pour annuler, on soustrait ce delta
                    _ensure(dst)
                    stock[dst]['nombre_unites']  -= (qty_apres - qty_avant)
                    stock[dst]['poids_total_kg'] -= (pds_apres - pds_avant)
                else:
                    nb_modif_non_parsees += 1

        # 3. Construire le DataFrame résultat (seulement emplacements > 0)
        records = []
        for (lot_id, site, empl), v in stock.items():
            nb = round(v['nombre_unites'])
            if nb <= 0 or not site:
                continue
            m = meta.get((lot_id, site, empl), {})
            records.append({
                'lot_id':               lot_id,
                'code_lot_interne':     m.get('code_lot_interne', ''),
                'nom_usage':            m.get('nom_usage', ''),
                'code_variete':         m.get('code_variete', ''),
                'site_stockage':        site,
                'emplacement_stockage': empl,
                'nombre_unites':        nb,
                'poids_total_kg':       round(v['poids_total_kg'], 1),
                'type_conditionnement': m.get('type_conditionnement', ''),
            })

        df = pd.DataFrame(records)
        return df, nb_modif_non_parsees

    except Exception as e:
        if conn:
            conn.close()
        st.error(f"❌ Erreur stock à date : {e}")
        return pd.DataFrame(), 0

# ============================================================
# ✏️ FONCTIONS MAJ EN MASSE
# ============================================================

def get_sites_emplacements_actifs():
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT DISTINCT site_stockage, emplacement_stockage
            FROM stock_emplacements WHERE is_active = true
            ORDER BY site_stockage, emplacement_stockage
        """)
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        return [dict(r) for r in rows]
    except Exception as e:
        st.error(f"❌ Erreur chargement sites : {e}")
        return []

def get_emplacements_pour_maj(site_filtre, emplacement_filtre=None):
    try:
        conn = get_connection()
        cursor = conn.cursor()
        params = [site_filtre]
        filtre_empl = ""
        if emplacement_filtre:
            filtre_empl = "AND se.emplacement_stockage = %s"
            params.append(emplacement_filtre)
        cursor.execute(f"""
            SELECT se.id, se.lot_id, lb.code_lot_interne, lb.nom_usage, lb.code_variete,
                   se.site_stockage, se.emplacement_stockage,
                   se.nombre_unites, se.poids_total_kg, se.poids_unitaire_reel,
                   se.type_conditionnement, se.statut_lavage
            FROM stock_emplacements se JOIN lots_bruts lb ON lb.id = se.lot_id
            WHERE se.is_active = true AND se.nombre_unites > 0 AND se.site_stockage = %s
              {filtre_empl}
            ORDER BY se.emplacement_stockage, lb.nom_usage
        """, params)
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        return pd.DataFrame([dict(r) for r in rows]) if rows else pd.DataFrame()
    except Exception as e:
        st.error(f"❌ Erreur chargement emplacements : {e}")
        return pd.DataFrame()

def appliquer_maj_masse(modifications, username):
    """
    Applique les modifications en masse.
    Notes au format "Quantité: avant+après | Poids: avant+aprèskg"
    pour permettre la reconstruction stock à date.
    """
    conn = None
    nb_ok, nb_err = 0, 0
    erreurs = []
    try:
        conn = get_connection()
        cursor = conn.cursor()
        for modif in modifications:
            try:
                eid        = int(modif['id'])
                nb_new     = int(modif['nombre_unites_new'])
                pds_new    = float(modif['poids_total_kg_new'])
                pu_new     = float(modif['poids_unitaire_reel_new']) if modif.get('poids_unitaire_reel_new') else None
                statut_new = str(modif['statut_lavage_new']) if modif.get('statut_lavage_new') else None
                nb_old     = int(modif['nombre_unites_old'])
                pds_old    = float(modif['poids_total_kg_old'])

                cursor.execute("""
                    UPDATE stock_emplacements
                    SET nombre_unites = %s, poids_total_kg = %s,
                        poids_unitaire_reel = %s, statut_lavage = %s,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s AND is_active = true
                """, (nb_new, pds_new, pu_new, statut_new, eid))

                # Notes parsables pour reconstruction stock à date
                notes_trace = f"Quantité: {nb_old}+{nb_new} | Poids: {pds_old}+{pds_new}kg"

                cursor.execute("""
                    INSERT INTO stock_mouvements (
                        lot_id, type_mouvement, quantite, poids_kg,
                        site_destination, emplacement_destination,
                        description, notes, created_by, user_action
                    )
                    SELECT se.lot_id, 'MODIFICATION', %s, %s,
                           se.site_stockage, se.emplacement_stockage,
                           'MAJ en masse via Stock Global', %s, %s, %s
                    FROM stock_emplacements se WHERE se.id = %s
                """, (nb_new, pds_new, notes_trace, username, username, eid))

                nb_ok += 1
            except Exception as e_ligne:
                nb_err += 1
                erreurs.append(f"ID {modif.get('id','?')} : {e_ligne}")
        conn.commit()
        cursor.close()
        conn.close()
        return nb_ok, nb_err, erreurs
    except Exception as e:
        if conn:
            conn.rollback()
            conn.close()
        return 0, len(modifications), [f"Erreur transaction : {e}"]

# ============================================================
# 🎨 INTERFACE - TITRE
# ============================================================

st.title("📊 Stock Global")
st.markdown("*Vue d'ensemble analytique du stock*")
st.markdown("---")

# ============================================================
# 📊 ONGLETS PRINCIPAUX
# ============================================================

tab1, tab2, tab3, tab4, tab5, tab_date, tab_maj = st.tabs([
    "📊 Tableau de Bord",
    "🏭 Capacités Sites",
    "📦 Vue Stock",
    "📍 Vues Agrégées",
    "📜 Historique",
    "📅 Stock à date",
    "✏️ MAJ en masse",
])

# ============================================================
# ONGLET 1 : TABLEAU DE BORD
# ============================================================

with tab1:
    kpis = get_stock_kpis()
    occupation = get_occupation_globale()
    alertes = get_alertes()

    if kpis:
        st.subheader("📈 Indicateurs Clés")
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("🟢 Stock BRUT",  f"{kpis['BRUT']['tonnes']:,.1f} T",      f"{kpis['BRUT']['pallox']:,} pallox")
        with col2:
            st.metric("🧼 Stock LAVÉ",  f"{kpis['LAVE']['tonnes']:,.1f} T",      f"{kpis['LAVE']['pallox']:,} pallox")
        with col3:
            st.metric("🌾 Grenailles",  f"{kpis['GRENAILLES']['tonnes']:,.1f} T", f"{kpis['GRENAILLES']['pallox']:,} pallox")
        with col4:
            if occupation:
                emoji = get_status_emoji(occupation['taux'])
                st.metric(f"{emoji} Occupation", f"{occupation['taux']:.1f}%", f"{occupation['disponible']:,} places libres")

        st.markdown("---")
        col1, col2, col3, col4 = st.columns(4)
        with col1: st.metric("📦 Total Stock",   f"{kpis['total']['tonnes']:,.1f} T")
        with col2: st.metric("🎯 Total Pallox",  f"{kpis['total']['pallox']:,}")
        with col3: st.metric("📋 Lots en Stock", f"{kpis['total']['lots']}")
        with col4: st.metric("🏭 Sites Utilisés",f"{kpis['total']['sites']}")

        st.markdown("---")
        st.subheader("📊 Répartition par Statut")
        col1, col2, col3 = st.columns(3)
        total_tonnes = kpis['total']['tonnes'] if kpis['total']['tonnes'] > 0 else 1
        with col1:
            pct = kpis['BRUT']['tonnes'] / total_tonnes * 100
            st.markdown(f'<div class="status-card status-brut"><h3>🟢 BRUT</h3><h2>{pct:.1f}%</h2><p>{kpis["BRUT"]["tonnes"]:,.1f} T | {kpis["BRUT"]["pallox"]:,} pallox</p></div>', unsafe_allow_html=True)
        with col2:
            pct = kpis['LAVE']['tonnes'] / total_tonnes * 100
            st.markdown(f'<div class="status-card status-lave"><h3>🧼 LAVÉ</h3><h2>{pct:.1f}%</h2><p>{kpis["LAVE"]["tonnes"]:,.1f} T | {kpis["LAVE"]["pallox"]:,} pallox</p></div>', unsafe_allow_html=True)
        with col3:
            pct = kpis['GRENAILLES']['tonnes'] / total_tonnes * 100
            st.markdown(f'<div class="status-card status-gren"><h3>🌾 GRENAILLES</h3><h2>{pct:.1f}%</h2><p>{kpis["GRENAILLES"]["tonnes"]:,.1f} T | {kpis["GRENAILLES"]["pallox"]:,} pallox</p></div>', unsafe_allow_html=True)

        st.markdown("---")
        col1, col2 = st.columns([1, 1])
        with col1:
            st.subheader("⚠️ Alertes Actives")
            if alertes:
                for alerte in alertes:
                    st.markdown(f'<div class="alert-box alert-{alerte["type"]}">{alerte["icon"]} {alerte["message"]}</div>', unsafe_allow_html=True)
            else:
                st.success("✅ Aucune alerte - Tout est normal !")
        with col2:
            st.subheader("🏆 Top 10 Sites")
            top_sites = get_top_sites(10)
            if not top_sites.empty:
                st.dataframe(top_sites, use_container_width=True, hide_index=True,
                    column_config={"Tonnes": st.column_config.NumberColumn(format="%.1f T")})
            else:
                st.info("Aucun site avec stock")

# ============================================================
# ONGLET 2 : CAPACITÉS SITES
# ============================================================

with tab2:
    st.subheader("🏭 Capacités par Site / Emplacement")
    df_capacites = get_capacites_sites()
    if not df_capacites.empty:
        sites = ["Tous"] + sorted(df_capacites['Site'].unique().tolist())
        filtre_site = st.selectbox("Filtrer par site", sites, key="filtre_site_capa")
        df_filtered = df_capacites.copy()
        if filtre_site != "Tous":
            df_filtered = df_filtered[df_filtered['Site'] == filtre_site]
        st.markdown("---")
        for site in df_filtered['Site'].unique():
            with st.expander(f"📍 {site}", expanded=(filtre_site != "Tous")):
                df_site = df_filtered[df_filtered['Site'] == site]
                total_capa   = df_site['Capacité Max'].sum()
                total_occupe = df_site['Occupé'].sum()
                taux_site    = (total_occupe / total_capa * 100) if total_capa > 0 else 0
                col1, col2, col3, col4 = st.columns(4)
                with col1: st.metric("Capacité",   f"{total_capa:,} pallox")
                with col2: st.metric("Occupé",     f"{total_occupe:,} pallox")
                with col3: st.metric("Disponible", f"{total_capa - total_occupe:,} pallox")
                with col4: st.metric(f"{get_status_emoji(taux_site)} Taux", f"{taux_site:.1f}%")
                st.markdown("---")
                st.dataframe(
                    df_site[['Emplacement','Nom','Capacité Max','Occupé','Disponible','Taux (%)','Tonnage','Nb Lots']].copy(),
                    use_container_width=True, hide_index=True,
                    column_config={
                        "Taux (%)": st.column_config.ProgressColumn("Taux (%)", min_value=0, max_value=100, format="%.1f%%"),
                        "Tonnage":  st.column_config.NumberColumn(format="%.1f T")
                    }
                )
        st.markdown("---")
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            df_capacites.to_excel(writer, index=False, sheet_name='Capacités')
        st.download_button("📥 Exporter les capacités (Excel)", buffer.getvalue(),
            f"capacites_sites_{datetime.now().strftime('%Y%m%d')}.xlsx",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True)
    else:
        st.warning("⚠️ Aucune donnée de capacité")

# ============================================================
# ONGLET 3 : VUE STOCK COMPLÈTE
# ============================================================

with tab3:
    st.subheader("📦 Vue Stock Complète")
    df_stock = get_stock_complet()
    if not df_stock.empty:
        col1, col2, col3, col4 = st.columns(4)
        with col1: filtre_statut     = st.selectbox("Statut",  ["Tous","BRUT","LAVE","GRENAILLES"], key="filtre_statut_stock")
        with col2: filtre_site_stock = st.selectbox("Site",    ["Tous"] + sorted(df_stock['site_stockage'].unique().tolist()), key="filtre_site_stock")
        with col3: filtre_variete    = st.selectbox("Variété", ["Toutes"] + sorted(df_stock['variete'].dropna().unique().tolist()), key="filtre_variete_stock")
        with col4: filtre_age        = st.selectbox("Âge",     ["Tous","< 30 jours","30-60 jours","> 60 jours"], key="filtre_age_stock")

        df_filtered = df_stock.copy()
        if filtre_statut     != "Tous":    df_filtered = df_filtered[df_filtered['statut_lavage'] == filtre_statut]
        if filtre_site_stock != "Tous":    df_filtered = df_filtered[df_filtered['site_stockage'] == filtre_site_stock]
        if filtre_variete    != "Toutes":  df_filtered = df_filtered[df_filtered['variete'] == filtre_variete]
        if filtre_age == "< 30 jours":    df_filtered = df_filtered[df_filtered['age_jours'] < 30]
        elif filtre_age == "30-60 jours": df_filtered = df_filtered[(df_filtered['age_jours'] >= 30) & (df_filtered['age_jours'] <= 60)]
        elif filtre_age == "> 60 jours":  df_filtered = df_filtered[df_filtered['age_jours'] > 60]

        st.markdown("---")
        col1, col2, col3 = st.columns(3)
        with col1: st.info(f"**{len(df_filtered)}** emplacements")
        with col2: st.info(f"**{df_filtered['nombre_unites'].sum():,.0f}** pallox | **{df_filtered['poids_total_kg'].sum()/1000:,.1f}** T")
        with col3: st.info(f"**{df_filtered['lot_id'].nunique()}** lots distincts")

        df_display = df_filtered.copy()
        df_display['Tonnes']  = df_display['poids_total_kg'] / 1000
        df_display['Calibre'] = df_display.apply(
            lambda r: f"{int(r['calibre_min'])}-{int(r['calibre_max'])}"
            if pd.notna(r['calibre_min']) and pd.notna(r['calibre_max']) else "", axis=1)
        df_display['Statut']  = df_display['statut_lavage'].apply(
            lambda s: "🟢 BRUT" if s == "BRUT" else ("🧼 LAVÉ" if s == "LAVE" else "🌾 GREN"))

        st.dataframe(
            df_display[['code_lot_interne','variete','producteur','site_stockage',
                        'emplacement_stockage','nombre_unites','Tonnes','Statut','Calibre','age_jours']].rename(columns={
                'code_lot_interne':'Lot','variete':'Variété','producteur':'Producteur',
                'site_stockage':'Site','emplacement_stockage':'Emplacement',
                'nombre_unites':'Pallox','age_jours':'Âge (j)'}),
            use_container_width=True, hide_index=True,
            column_config={"Tonnes": st.column_config.NumberColumn(format="%.1f")}
        )
        st.markdown("---")
        col1, col2 = st.columns(2)
        with col1:
            st.download_button("📥 Exporter CSV", df_filtered.to_csv(index=False).encode('utf-8'),
                f"stock_complet_{datetime.now().strftime('%Y%m%d')}.csv", "text/csv", use_container_width=True)
        with col2:
            buf = io.BytesIO()
            with pd.ExcelWriter(buf, engine='openpyxl') as w: df_filtered.to_excel(w, index=False, sheet_name='Stock')
            st.download_button("📥 Exporter Excel", buf.getvalue(),
                f"stock_complet_{datetime.now().strftime('%Y%m%d')}.xlsx",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)
    else:
        st.warning("⚠️ Aucun stock trouvé")

# ============================================================
# ONGLET 4 : VUES AGRÉGÉES
# ============================================================

with tab4:
    subtab1, subtab2, subtab3 = st.tabs(["📍 Par Site","🌱 Par Variété","👤 Par Producteur"])
    with subtab1:
        st.subheader("📍 Stock par Site")
        df_site = get_stock_par_site()
        if not df_site.empty:
            st.dataframe(df_site, use_container_width=True, hide_index=True,
                column_config={c: st.column_config.NumberColumn(format="%.1f") for c in ["Total (T)","Brut (T)","Lavé (T)","Gren. (T)"]})
            col1, col2 = st.columns(2)
            with col1: st.info(f"**{len(df_site)}** sites utilisés")
            with col2: st.info(f"**{df_site['Total (T)'].sum():,.1f}** T total")
            buf = io.BytesIO()
            with pd.ExcelWriter(buf, engine='openpyxl') as w: df_site.to_excel(w, index=False, sheet_name='Par Site')
            st.download_button("📥 Exporter", buf.getvalue(), f"stock_par_site_{datetime.now().strftime('%Y%m%d')}.xlsx",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    with subtab2:
        st.subheader("🌱 Stock par Variété")
        df_variete = get_stock_par_variete()
        if not df_variete.empty:
            st.dataframe(df_variete, use_container_width=True, hide_index=True,
                column_config={c: st.column_config.NumberColumn(format="%.1f") for c in ["Total (T)","Brut (T)","Lavé (T)","Gren. (T)"]})
            col1, col2 = st.columns(2)
            with col1: st.info(f"**{len(df_variete)}** variétés en stock")
            with col2: st.info(f"**{df_variete['Lots'].sum()}** lots total")
            buf = io.BytesIO()
            with pd.ExcelWriter(buf, engine='openpyxl') as w: df_variete.to_excel(w, index=False, sheet_name='Par Variété')
            st.download_button("📥 Exporter", buf.getvalue(), f"stock_par_variete_{datetime.now().strftime('%Y%m%d')}.xlsx",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    with subtab3:
        st.subheader("👤 Stock par Producteur")
        df_producteur = get_stock_par_producteur()
        if not df_producteur.empty:
            st.dataframe(df_producteur, use_container_width=True, hide_index=True,
                column_config={c: st.column_config.NumberColumn(format="%.1f") for c in ["Total (T)","Brut (T)","Lavé (T)"]})
            col1, col2 = st.columns(2)
            with col1: st.info(f"**{len(df_producteur)}** producteurs")
            with col2: st.info(f"**{df_producteur['Total (T)'].sum():,.1f}** T total")
            buf = io.BytesIO()
            with pd.ExcelWriter(buf, engine='openpyxl') as w: df_producteur.to_excel(w, index=False, sheet_name='Par Producteur')
            st.download_button("📥 Exporter", buf.getvalue(), f"stock_par_producteur_{datetime.now().strftime('%Y%m%d')}.xlsx",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

# ============================================================
# ONGLET 5 : HISTORIQUE MOUVEMENTS
# ============================================================

with tab5:
    st.subheader("📜 Historique des Mouvements")
    col1, col2 = st.columns(2)
    with col1:
        periodes = {"7 jours": 7, "30 jours": 30, "90 jours": 90, "365 jours": 365}
        periode_label = st.selectbox("Période", list(periodes.keys()), index=1)
        jours = periodes[periode_label]
    with col2:
        types_mvt = ["Tous","AJOUT","TRANSFERT","MODIFICATION","SUPPRESSION","LAVAGE_CREATION","LAVAGE_DEDUCTION"]
        type_filtre = st.selectbox("Type de mouvement", types_mvt)
    st.markdown("---")
    df_stats = get_stats_mouvements(jours)
    if not df_stats.empty:
        st.markdown("##### 📊 Statistiques par type")
        cols = st.columns(len(df_stats))
        for i, (_, row) in enumerate(df_stats.iterrows()):
            with cols[i % len(cols)]:
                st.metric(row['Type'], f"{row['Opérations']} ops", f"{row['Tonnage (T)']:.1f} T")
    st.markdown("---")
    df_mvt = get_mouvements_globaux(jours, type_filtre if type_filtre != "Tous" else None)
    if not df_mvt.empty:
        st.dataframe(df_mvt, use_container_width=True, hide_index=True,
            column_config={
                "Date": st.column_config.DatetimeColumn(format="DD/MM/YY HH:mm"),
                "Poids (kg)": st.column_config.NumberColumn(format="%.0f")
            })
        st.info(f"**{len(df_mvt)}** mouvements affichés (max 500)")
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine='openpyxl') as w: df_mvt.to_excel(w, index=False, sheet_name='Mouvements')
        st.download_button("📥 Exporter l'historique", buf.getvalue(),
            f"mouvements_{datetime.now().strftime('%Y%m%d')}.xlsx",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)
    else:
        st.info(f"Aucun mouvement sur les {jours} derniers jours")

# ============================================================
# ONGLET 6 : STOCK À DATE
# ============================================================

with tab_date:
    st.subheader("📅 Stock à une date donnée")
    st.caption(
        "Reconstruction du stock à partir de l'état actuel, en annulant tous les mouvements "
        "postérieurs à la date choisie. Les MODIFICATION sont reconstituées grâce au champ notes."
    )

    col_d1, col_d2 = st.columns([2, 3])
    with col_d1:
        date_cible = st.date_input("Date de référence", value=datetime.today().date(), key="stock_date_cible")
        date_cible_ts = datetime.combine(date_cible, datetime.max.time())
    with col_d2:
        st.markdown("<br>", unsafe_allow_html=True)
        btn_calculer = st.button("🔍 Calculer le stock à cette date", key="btn_stock_date")

    if btn_calculer:
        with st.spinner("Reconstruction en cours..."):
            df_date, nb_non_parsees = get_stock_a_date(date_cible_ts)

        if df_date.empty:
            st.warning("Aucun stock reconstitué pour cette date.")
        else:
            if nb_non_parsees > 0:
                st.warning(
                    f"⚠️ {nb_non_parsees} mouvement(s) MODIFICATION avec notes non parsables ont été ignorés. "
                    "Ces mouvements correspondent à d'anciennes modifications dont le format notes diffère. "
                    "Le stock affiché peut présenter de légères imprécisions sur les périodes concernées."
                )

            sites_dispo = sorted(df_date['site_stockage'].unique().tolist())
            filtre_site_date = st.multiselect("Filtrer par site", options=sites_dispo, default=[], key="filtre_site_date_result")
            if filtre_site_date:
                df_date = df_date[df_date['site_stockage'].isin(filtre_site_date)]

            col_k1, col_k2, col_k3, col_k4 = st.columns(4)
            col_k1.metric("Emplacements",   f"{len(df_date):,}")
            col_k2.metric("Lots distincts", f"{df_date['lot_id'].nunique():,}")
            col_k3.metric("Total pallox",   f"{int(df_date['nombre_unites'].sum()):,}")
            col_k4.metric("Total (t)",      f"{df_date['poids_total_kg'].sum()/1000:,.1f}")

            st.markdown("---")
            st.markdown("**Agrégé par site / emplacement**")
            df_agg = (
                df_date
                .groupby(['site_stockage','emplacement_stockage'], as_index=False)
                .agg(nb_lots=('lot_id','nunique'), nombre_unites=('nombre_unites','sum'), poids_total_kg=('poids_total_kg','sum'))
                .sort_values(['site_stockage','emplacement_stockage'])
            )
            df_agg['Poids (t)'] = (df_agg['poids_total_kg'] / 1000).round(1)
            st.dataframe(
                df_agg.rename(columns={
                    'site_stockage':'Site','emplacement_stockage':'Emplacement',
                    'nb_lots':'Lots','nombre_unites':'Pallox','poids_total_kg':'Poids (kg)',
                }),
                use_container_width=True, hide_index=True,
                column_config={
                    "Poids (kg)": st.column_config.NumberColumn(format="%.0f"),
                    "Poids (t)":  st.column_config.NumberColumn(format="%.1f"),
                }
            )

            with st.expander("📋 Détail par lot"):
                st.dataframe(
                    df_date[['site_stockage','emplacement_stockage','code_lot_interne','nom_usage',
                              'code_variete','nombre_unites','poids_total_kg','type_conditionnement']]
                    .sort_values(['site_stockage','emplacement_stockage','nom_usage'])
                    .rename(columns={
                        'site_stockage':'Site','emplacement_stockage':'Emplacement',
                        'code_lot_interne':'Code lot','nom_usage':'Nom lot',
                        'code_variete':'Variété','nombre_unites':'Pallox',
                        'poids_total_kg':'Poids (kg)','type_conditionnement':'Conditionnement',
                    }),
                    use_container_width=True, hide_index=True,
                )

            buf = io.BytesIO()
            with pd.ExcelWriter(buf, engine='openpyxl') as w:
                df_agg.to_excel(w, index=False, sheet_name='Agrégé')
                df_date.to_excel(w, index=False, sheet_name='Détail lots')
            st.download_button("📥 Exporter (Excel)", buf.getvalue(),
                f"stock_au_{date_cible.strftime('%Y%m%d')}.xlsx",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

# ============================================================
# ONGLET 7 : MAJ EN MASSE
# ============================================================

with tab_maj:
    st.subheader("✏️ Mise à jour stock en masse")

    if not is_admin():
        st.warning("🔒 Accès réservé aux administrateurs.")
        st.stop()

    st.caption("Modifier les quantités et poids de plusieurs lots d'un même site en une seule action.")

    donnees_sites = get_sites_emplacements_actifs()
    sites_uniques = sorted(list({r['site_stockage'] for r in donnees_sites}))

    col_f1, col_f2 = st.columns(2)
    with col_f1:
        site_sel = st.selectbox("Site *", options=[""] + sites_uniques, key="maj_site_sel",
            format_func=lambda x: "— Sélectionner —" if x == "" else x)
    with col_f2:
        empl_options = sorted(list({r['emplacement_stockage'] for r in donnees_sites
            if (not site_sel or r['site_stockage'] == site_sel)}))
        empl_sel = st.selectbox("Emplacement (optionnel)", options=[""] + empl_options, key="maj_empl_sel",
            format_func=lambda x: "Tous les emplacements" if x == "" else x)

    if not site_sel:
        st.info("Sélectionner un site pour commencer.")
    else:
        df_maj = get_emplacements_pour_maj(site_sel, empl_sel if empl_sel else None)
        if df_maj.empty:
            st.warning("Aucun emplacement actif trouvé pour cette sélection.")
        else:
            st.markdown(f"**{len(df_maj)} lot(s)** — `{site_sel}`" + (f" / `{empl_sel}`" if empl_sel else ""))

            df_original = df_maj[['id','nombre_unites','poids_total_kg']].copy()
            df_original.rename(columns={'nombre_unites':'nb_old','poids_total_kg':'poids_old'}, inplace=True)

            colonnes_edition = {
                'site_stockage':        st.column_config.TextColumn("Site",         disabled=True),
                'emplacement_stockage': st.column_config.TextColumn("Emplacement",  disabled=True),
                'code_lot_interne':     st.column_config.TextColumn("Code lot",     disabled=True),
                'nom_usage':            st.column_config.TextColumn("Nom lot",      disabled=True),
                'code_variete':         st.column_config.TextColumn("Variété",      disabled=True),
                'nombre_unites':        st.column_config.NumberColumn("Pallox",          min_value=0, step=1),
                'poids_total_kg':       st.column_config.NumberColumn("Poids (kg)",      min_value=0.0, step=100.0, format="%.1f"),
                'poids_unitaire_reel':  st.column_config.NumberColumn("Poids unit. (kg)",min_value=0.0, step=10.0,  format="%.1f"),
                'statut_lavage':        st.column_config.SelectboxColumn("Statut lavage",
                    # Toutes les valeurs observées en base (ne pas en retirer pour éviter la perte de données)
                    options=['BRUT','LAVÉ','LAVÉ ','LAVE','GRENAILLES_BRUTES','GRENAILLES','EN_COURS','RESERVE'],
                    required=False),
                'type_conditionnement': st.column_config.TextColumn("Conditionnement", disabled=True),
            }

            df_edited = st.data_editor(
                df_maj[['id'] + list(colonnes_edition.keys())].copy(),
                column_config=colonnes_edition,
                disabled=['id'], hide_index=True, use_container_width=True,
                key="data_editor_maj_masse", num_rows="fixed",
            )

            st.markdown("---")
            df_merged  = df_edited.merge(df_original, on='id', how='left')
            df_changed = df_merged[
                (df_merged['nombre_unites'] != df_merged['nb_old']) |
                (df_merged['poids_total_kg'].round(1) != df_merged['poids_old'].round(1))
            ]

            if df_changed.empty:
                st.info("Aucune modification détectée.")
            else:
                st.markdown(f"**{len(df_changed)} ligne(s) modifiée(s) :**")
                st.dataframe(
                    df_changed[['code_lot_interne','nom_usage','site_stockage','emplacement_stockage',
                                'nb_old','nombre_unites','poids_old','poids_total_kg']].rename(columns={
                        'code_lot_interne':'Code lot','nom_usage':'Nom lot',
                        'site_stockage':'Site','emplacement_stockage':'Emplacement',
                        'nb_old':'Pallox avant','nombre_unites':'Pallox après',
                        'poids_old':'Poids avant (kg)','poids_total_kg':'Poids après (kg)',
                    }),
                    use_container_width=True, hide_index=True,
                )

                if st.button(f"💾 Confirmer {len(df_changed)} modification(s)",
                             key="btn_confirmer_maj_masse", type="primary"):
                    modifications = [{
                        'id':                    int(row['id']),
                        'nombre_unites_new':     int(row['nombre_unites']),
                        'poids_total_kg_new':    float(row['poids_total_kg']),
                        'poids_unitaire_reel_new': float(row['poids_unitaire_reel']) if pd.notna(row.get('poids_unitaire_reel')) else None,
                        'statut_lavage_new':     row.get('statut_lavage'),
                        'nombre_unites_old':     int(row['nb_old']),
                        'poids_total_kg_old':    float(row['poids_old']),
                    } for _, row in df_changed.iterrows()]

                    username = st.session_state.get('username', 'inconnu')
                    with st.spinner("Enregistrement..."):
                        nb_ok, nb_err, erreurs = appliquer_maj_masse(modifications, username)
                        time.sleep(0.3)
                    if nb_err == 0:
                        st.success(f"✅ {nb_ok} emplacement(s) mis à jour.")
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error(f"⚠️ {nb_ok} OK — {nb_err} erreur(s) :")
                        for e in erreurs:
                            st.error(e)

# ============================================================
# FOOTER
# ============================================================

show_footer()
