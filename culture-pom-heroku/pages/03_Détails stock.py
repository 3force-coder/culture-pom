import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime
from database import get_connection
from components import show_footer
from auth import require_access
import io

st.set_page_config(page_title="Détails Stock - Culture Pom", page_icon="📍", layout="wide")

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
    .stSelectbox, .stButton, .stCheckbox {
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
    .lot-card {
        background-color: #f0f2f6;
        padding: 1rem;
        border-radius: 0.5rem;
        margin: 0.5rem 0;
        border-left: 4px solid #1f77b4;
    }
</style>
""", unsafe_allow_html=True)

# ⭐ CONTRÔLE D'ACCÈS RBAC - UNE SEULE LIGNE
require_access("STOCK")

st.title("📍 Détails Stock par Lot")
st.caption("*Gestion des emplacements de stockage par lot*")
st.markdown("---")

# ============================================================================
# FONCTIONS UTILITAIRES
# ============================================================================

def format_number_fr(value):
    """Formate un nombre avec des espaces pour les milliers (format français)"""
    if pd.isna(value) or value is None:
        return "0"
    try:
        return f"{int(value):,}".replace(',', ' ')
    except:
        return str(value)

def format_float_fr(value, decimals=1):
    """Formate un float avec des espaces pour les milliers (format français)"""
    if pd.isna(value) or value is None:
        return "0.0"
    try:
        formatted = f"{float(value):,.{decimals}f}".replace(',', ' ')
        # Remplacer le point par une virgule pour la partie décimale si souhaité
        # formatted = formatted.replace('.', ',')
        return formatted
    except:
        return str(value)

def get_sites_stockage():
    """Récupère tous les sites de stockage actifs"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT DISTINCT code_site 
            FROM ref_sites_stockage 
            WHERE is_active = TRUE 
            ORDER BY code_site
        """)
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        return [row['code_site'] for row in rows]
    except Exception as e:
        st.error(f"❌ Erreur : {str(e)}")
        return []

def get_emplacements_by_site(site):
    """Récupère les emplacements d'un site donné"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT code_emplacement, nom_complet
            FROM ref_sites_stockage
            WHERE code_site = %s AND is_active = TRUE
            ORDER BY code_emplacement
        """, (site,))
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        return [(row['code_emplacement'], row['nom_complet']) for row in rows]
    except Exception as e:
        st.error(f"❌ Erreur : {str(e)}")
        return []

def get_lot_info(lot_id):
    """Récupère les infos d'un lot"""
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
                l.date_entree_stock,
                l.calibre_min,
                l.calibre_max,
                l.poids_total_brut_kg,
                l.statut,
                COALESCE((CURRENT_DATE - l.date_entree_stock::DATE), 0) as age_jours,
                COALESCE((SELECT SUM(se.poids_total_kg) FROM stock_emplacements se WHERE se.lot_id = l.id AND se.is_active = TRUE), 0) as poids_reel_stock_kg
            FROM lots_bruts l
            LEFT JOIN ref_varietes v ON l.code_variete = v.code_variete
            LEFT JOIN ref_producteurs p ON l.code_producteur = p.code_producteur
            WHERE l.id = %s AND l.is_active = TRUE
        """
        
        cursor.execute(query, (lot_id,))
        row = cursor.fetchone()
        cursor.close()
        conn.close()
        
        return dict(row) if row else None
        
    except Exception as e:
        st.error(f"❌ Erreur : {str(e)}")
        return None

def get_lot_emplacements(lot_id):
    """Récupère les emplacements d'un lot avec statut lavage emoji et calibres"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        query = """
            SELECT 
                se.id,
                se.site_stockage,
                se.emplacement_stockage,
                se.nombre_unites,
                se.type_conditionnement,
                se.poids_total_kg,
                se.statut_lavage,
                se.calibre_min,
                se.calibre_max,
                se.is_active
            FROM stock_emplacements se
            WHERE se.lot_id = %s AND se.is_active = TRUE
            ORDER BY se.site_stockage, se.emplacement_stockage
        """
        
        cursor.execute(query, (lot_id,))
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        
        if rows:
            df = pd.DataFrame(rows)
            # Convertir colonnes numériques
            numeric_cols = ['nombre_unites', 'poids_total_kg', 'calibre_min', 'calibre_max']
            for col in numeric_cols:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
            
            # ⭐ Ajouter emoji statut
            if 'statut_lavage' in df.columns:
                def get_statut_emoji(statut):
                    if statut == 'BRUT':
                        return '🟢 BRUT'
                    elif statut == 'LAVÉ':
                        return '🧼 LAVÉ'
                    elif statut == 'GRENAILLES':
                        return '🌾 GRENAILLES'
                    else:
                        return statut
                
                df['statut_lavage_display'] = df['statut_lavage'].apply(get_statut_emoji)
            
            return df
        return pd.DataFrame()
        
    except Exception as e:
        st.error(f"❌ Erreur : {str(e)}")
        return pd.DataFrame()

def get_lot_mouvements(lot_id, limit=10):
    """Récupère les derniers mouvements d'un lot"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        query = """
            SELECT 
                type_mouvement,
                site_origine,
                emplacement_origine,
                site_destination,
                emplacement_destination,
                quantite,
                type_conditionnement,
                poids_kg,
                user_action,
                created_by,
                notes,
                created_at
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
            df = pd.DataFrame(rows)
            # Convertir colonnes numériques
            numeric_cols = ['quantite', 'poids_kg']
            for col in numeric_cols:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
            return df
        return pd.DataFrame()
        
    except Exception as e:
        st.error(f"❌ Erreur : {str(e)}")
        return pd.DataFrame()

def add_emplacement(lot_id, site, emplacement, nombre_unites, type_cond, statut_lavage='BRUT', poids_total_saisi=None, calibre_min=None, calibre_max=None):
    """Ajoute un emplacement avec poids personnalisable et calibre"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Validation calibre
        if calibre_min is not None and calibre_max is not None:
            if calibre_min >= calibre_max:
                return False, "❌ Calibre min doit être inférieur à calibre max"
        
        # Calcul poids théorique selon type conditionnement
        if type_cond == 'Pallox':
            poids_unitaire_theorique = 1900.0
        elif type_cond == 'Petit Pallox':
            poids_unitaire_theorique = 1200.0
        elif type_cond == 'Big Bag':
            poids_unitaire_theorique = 1600.0
        else:
            poids_unitaire_theorique = 1900.0
        
        # Utiliser poids saisi OU calculer théorique
        if poids_total_saisi is not None:
            poids_total = float(poids_total_saisi)
        else:
            poids_total = nombre_unites * poids_unitaire_theorique
        
        # Calculer poids unitaire réel
        poids_unitaire_reel = poids_total / nombre_unites
        
        # Insérer emplacement avec calibre
        query = """
            INSERT INTO stock_emplacements (
                lot_id, site_stockage, emplacement_stockage, 
                nombre_unites, type_conditionnement, poids_total_kg, 
                poids_unitaire_reel, statut_lavage, calibre_min, calibre_max, is_active
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, TRUE)
        """
        
        cursor.execute(query, (
            int(lot_id), site, emplacement, 
            int(nombre_unites), type_cond, float(poids_total),
            float(poids_unitaire_reel), statut_lavage,
            int(calibre_min) if calibre_min is not None else None,
            int(calibre_max) if calibre_max is not None else None
        ))
        
        # Enregistrer mouvement avec notes calibre
        user = st.session_state.get('username', 'system')
        notes_calibre = f"Calibre: {calibre_min}-{calibre_max}" if calibre_min and calibre_max else ""
        
        query_mvt = """
            INSERT INTO stock_mouvements (
                lot_id, type_mouvement, site_destination, emplacement_destination,
                quantite, type_conditionnement, poids_kg, user_action, created_by, notes
            ) VALUES (%s, 'AJOUT', %s, %s, %s, %s, %s, %s, %s, %s)
        """
        
        cursor.execute(query_mvt, (
            int(lot_id), site, emplacement,
            int(nombre_unites), type_cond, float(poids_total), user, user, 
            f"{statut_lavage} {notes_calibre}".strip()
        ))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return True, "✅ Emplacement ajouté"
        
    except Exception as e:
        if 'conn' in locals():
            conn.rollback()
        return False, f"❌ Erreur : {str(e)}"

def transfer_emplacement(lot_id, empl_source_id, quantite_transfert, site_dest, empl_dest):
    """Transfère du stock d'un emplacement vers un autre"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Récupérer infos source
        cursor.execute("""
            SELECT site_stockage, emplacement_stockage, nombre_unites, 
                   type_conditionnement, poids_total_kg, statut_lavage
            FROM stock_emplacements
            WHERE id = %s AND is_active = TRUE
        """, (empl_source_id,))
        
        source = cursor.fetchone()
        
        if not source:
            return False, "❌ Emplacement source introuvable"
        
        if int(quantite_transfert) > int(source['nombre_unites']):
            return False, f"❌ Quantité insuffisante (disponible: {source['nombre_unites']})"
        
        # Calcul poids
        if source['type_conditionnement'] == 'Pallox':
            poids_unitaire = 1900.0
        elif source['type_conditionnement'] == 'Petit Pallox':
            poids_unitaire = 1200.0
        elif source['type_conditionnement'] == 'Big Bag':
            poids_unitaire = 1600.0
        else:
            poids_unitaire = 1900.0
        
        poids_transfere = quantite_transfert * poids_unitaire
        
        # Déduire de la source
        nouvelle_quantite_source = int(source['nombre_unites']) - int(quantite_transfert)
        nouveau_poids_source = nouvelle_quantite_source * poids_unitaire
        
        if nouvelle_quantite_source == 0:
            # Supprimer source
            cursor.execute("""
                UPDATE stock_emplacements 
                SET is_active = FALSE 
                WHERE id = %s
            """, (empl_source_id,))
        else:
            # Mettre à jour source
            cursor.execute("""
                UPDATE stock_emplacements 
                SET nombre_unites = %s, poids_total_kg = %s 
                WHERE id = %s
            """, (nouvelle_quantite_source, nouveau_poids_source, empl_source_id))
        
        # Vérifier si destination existe déjà
        cursor.execute("""
            SELECT id, nombre_unites, poids_total_kg
            FROM stock_emplacements
            WHERE lot_id = %s 
              AND site_stockage = %s 
              AND emplacement_stockage = %s 
              AND type_conditionnement = %s
              AND statut_lavage = %s
              AND is_active = TRUE
        """, (int(lot_id), site_dest, empl_dest, source['type_conditionnement'], source['statut_lavage']))
        
        dest_existant = cursor.fetchone()
        
        if dest_existant:
            # Ajouter à l'existant
            nouvelle_quantite_dest = int(dest_existant['nombre_unites']) + int(quantite_transfert)
            nouveau_poids_dest = float(dest_existant['poids_total_kg']) + poids_transfere
            
            cursor.execute("""
                UPDATE stock_emplacements 
                SET nombre_unites = %s, poids_total_kg = %s 
                WHERE id = %s
            """, (nouvelle_quantite_dest, nouveau_poids_dest, dest_existant['id']))
        else:
            # Créer nouveau
            cursor.execute("""
                INSERT INTO stock_emplacements (
                    lot_id, site_stockage, emplacement_stockage,
                    nombre_unites, type_conditionnement, poids_total_kg,
                    statut_lavage, is_active
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, TRUE)
            """, (int(lot_id), site_dest, empl_dest, int(quantite_transfert), 
                  source['type_conditionnement'], poids_transfere, source['statut_lavage']))
        
        # Enregistrer mouvement
        user = st.session_state.get('username', 'system')
        
        cursor.execute("""
            INSERT INTO stock_mouvements (
                lot_id, type_mouvement, 
                site_origine, emplacement_origine,
                site_destination, emplacement_destination,
                quantite, type_conditionnement, poids_kg, user_action, created_by
            ) VALUES (%s, 'TRANSFERT', %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (int(lot_id), source['site_stockage'], source['emplacement_stockage'],
              site_dest, empl_dest, int(quantite_transfert), 
              source['type_conditionnement'], poids_transfere, user, user))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return True, "✅ Transfert effectué"
        
    except Exception as e:
        if 'conn' in locals():
            conn.rollback()
        return False, f"❌ Erreur : {str(e)}"

def modify_emplacement(empl_id, nouvelle_quantite):
    """Modifie la quantité d'un emplacement (OBSOLÈTE - utiliser modify_emplacement_complet)"""
    # Rediriger vers la nouvelle fonction avec valeurs par défaut
    return modify_emplacement_complet(empl_id, nouvelle_quantite=nouvelle_quantite)

def modify_emplacement_complet(empl_id, nouvelle_quantite=None, nouveau_type=None, nouveau_statut=None, 
                               nouveau_poids=None, nouveau_calibre_min=None, nouveau_calibre_max=None):
    """Modifie complètement un emplacement avec traçabilité"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Validation calibre
        if nouveau_calibre_min is not None and nouveau_calibre_max is not None:
            if nouveau_calibre_min >= nouveau_calibre_max:
                return False, "❌ Calibre min doit être inférieur à calibre max"
        
        # Récupérer infos actuelles
        cursor.execute("""
            SELECT lot_id, site_stockage, emplacement_stockage, 
                   nombre_unites, type_conditionnement, poids_total_kg,
                   statut_lavage, calibre_min, calibre_max
            FROM stock_emplacements
            WHERE id = %s AND is_active = TRUE
        """, (empl_id,))
        
        empl = cursor.fetchone()
        
        if not empl:
            return False, "❌ Emplacement introuvable"
        
        # Préparer les nouvelles valeurs (garder anciennes si non spécifiées)
        final_quantite = int(nouvelle_quantite) if nouvelle_quantite is not None else int(empl['nombre_unites'])
        final_type = nouveau_type if nouveau_type is not None else empl['type_conditionnement']
        final_statut = nouveau_statut if nouveau_statut is not None else empl['statut_lavage']
        
        # Calcul poids
        if nouveau_poids is not None:
            final_poids = float(nouveau_poids)
        else:
            # Recalculer selon type
            if final_type == 'Pallox':
                poids_unitaire = 1900.0
            elif final_type == 'Petit Pallox':
                poids_unitaire = 1200.0
            elif final_type == 'Big Bag':
                poids_unitaire = 1600.0
            else:
                poids_unitaire = 1900.0
            final_poids = final_quantite * poids_unitaire
        
        # Calibre - garder ancien si non spécifié
        final_calibre_min = int(nouveau_calibre_min) if nouveau_calibre_min is not None else empl['calibre_min']
        final_calibre_max = int(nouveau_calibre_max) if nouveau_calibre_max is not None else empl['calibre_max']
        
        # Construire notes de modification pour traçabilité
        modifications = []
        if nouvelle_quantite is not None and int(nouvelle_quantite) != int(empl['nombre_unites']):
            modifications.append(f"Quantité: {empl['nombre_unites']}→{final_quantite}")
        if nouveau_type is not None and nouveau_type != empl['type_conditionnement']:
            modifications.append(f"Type: {empl['type_conditionnement']}→{final_type}")
        if nouveau_statut is not None and nouveau_statut != empl['statut_lavage']:
            modifications.append(f"Statut: {empl['statut_lavage']}→{final_statut}")
        if nouveau_poids is not None and abs(float(nouveau_poids) - float(empl['poids_total_kg'])) > 1:
            modifications.append(f"Poids: {empl['poids_total_kg']:.0f}→{final_poids:.0f}kg")
        if nouveau_calibre_min is not None or nouveau_calibre_max is not None:
            old_cal = f"{empl['calibre_min'] or '?'}-{empl['calibre_max'] or '?'}"
            new_cal = f"{final_calibre_min or '?'}-{final_calibre_max or '?'}"
            if old_cal != new_cal:
                modifications.append(f"Calibre: {old_cal}→{new_cal}")
        
        if not modifications:
            return True, "ℹ️ Aucune modification détectée"
        
        # Mettre à jour
        cursor.execute("""
            UPDATE stock_emplacements 
            SET nombre_unites = %s, 
                type_conditionnement = %s,
                poids_total_kg = %s,
                statut_lavage = %s,
                calibre_min = %s,
                calibre_max = %s,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
        """, (final_quantite, final_type, final_poids, final_statut, 
              final_calibre_min, final_calibre_max, empl_id))
        
        # Enregistrer mouvement de traçabilité
        user = st.session_state.get('username', 'system')
        notes_modif = " | ".join(modifications)
        
        cursor.execute("""
            INSERT INTO stock_mouvements (
                lot_id, type_mouvement, 
                site_destination, emplacement_destination,
                quantite, type_conditionnement, poids_kg, user_action, created_by,
                notes
            ) VALUES (%s, 'MODIFICATION', %s, %s, %s, %s, %s, %s, %s, %s)
        """, (int(empl['lot_id']), empl['site_stockage'], empl['emplacement_stockage'],
              final_quantite, final_type, final_poids, user, user, notes_modif))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return True, f"✅ Emplacement modifié ({len(modifications)} changement(s))"
        
    except Exception as e:
        if 'conn' in locals():
            conn.rollback()
        return False, f"❌ Erreur : {str(e)}"

def delete_emplacement(empl_id):
    """Supprime (soft delete) un emplacement"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Récupérer infos pour mouvement
        cursor.execute("""
            SELECT lot_id, site_stockage, emplacement_stockage, 
                   nombre_unites, type_conditionnement, poids_total_kg
            FROM stock_emplacements
            WHERE id = %s AND is_active = TRUE
        """, (empl_id,))
        
        empl = cursor.fetchone()
        
        if not empl:
            return False, "❌ Emplacement introuvable"
        
        # Soft delete
        cursor.execute("""
            UPDATE stock_emplacements 
            SET is_active = FALSE 
            WHERE id = %s
        """, (empl_id,))
        
        # Enregistrer mouvement
        user = st.session_state.get('username', 'system')
        
        cursor.execute("""
            INSERT INTO stock_mouvements (
                lot_id, type_mouvement, 
                site_origine, emplacement_origine,
                quantite, type_conditionnement, poids_kg, user_action, created_by
            ) VALUES (%s, 'SUPPRESSION', %s, %s, %s, %s, %s, %s, %s)
        """, (int(empl['lot_id']), empl['site_stockage'], empl['emplacement_stockage'],
              int(empl['nombre_unites']), empl['type_conditionnement'], 
              float(empl['poids_total_kg']), user, user))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return True, "✅ Emplacement supprimé"
        
    except Exception as e:
        if 'conn' in locals():
            conn.rollback()
        return False, f"❌ Erreur : {str(e)}"

def get_all_lots():
    """Récupère tous les lots actifs"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        query = """
            SELECT 
                l.id,
                l.code_lot_interne,
                l.nom_usage,
                COALESCE(v.nom_variete, l.code_variete) as nom_variete,
                COALESCE(p.nom, l.code_producteur) as nom_producteur,
                l.poids_total_brut_kg
            FROM lots_bruts l
            LEFT JOIN ref_varietes v ON l.code_variete = v.code_variete
            LEFT JOIN ref_producteurs p ON l.code_producteur = p.code_producteur
            WHERE l.is_active = TRUE
            ORDER BY l.code_lot_interne
        """
        
        cursor.execute(query)
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        
        if rows:
            df = pd.DataFrame(rows)
            # Convertir poids
            if 'poids_total_brut_kg' in df.columns:
                df['poids_total_brut_kg'] = pd.to_numeric(df['poids_total_brut_kg'], errors='coerce')
            return df
        return pd.DataFrame()
        
    except Exception as e:
        st.error(f"❌ Erreur : {str(e)}")
        return pd.DataFrame()


def get_recap_valorisation_lot(lot_id):
    """Récap valorisation détaillé pour un lot spécifique"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Infos lot de base (sans valeur_lot_euro)
        cursor.execute("""
            SELECT 
                prix_achat_euro_tonne,
                tare_achat_pct
            FROM lots_bruts
            WHERE id = %s AND is_active = TRUE
        """, (lot_id,))
        
        lot = cursor.fetchone()
        
        if not lot:
            cursor.close()
            conn.close()
            return None
        
        # ⭐ NOUVEAU : Calculer poids total depuis emplacements
        cursor.execute("""
            SELECT COALESCE(SUM(poids_total_kg), 0) as poids_total
            FROM stock_emplacements
            WHERE lot_id = %s AND is_active = TRUE
        """, (lot_id,))
        
        poids_result = cursor.fetchone()
        poids_brut = float(poids_result['poids_total']) if poids_result else 0.0
        
        # Vérifier si lot qualifié (prix + tare achat + poids emplacements)
        if not lot['prix_achat_euro_tonne'] or not lot['tare_achat_pct'] or poids_brut <= 0:
            cursor.close()
            conn.close()
            return None
        
        prix_achat = float(lot['prix_achat_euro_tonne'])
        tare_achat = float(lot['tare_achat_pct'])
        
        # Tare production réelle (si jobs lavage terminés pour ce lot)
        cursor.execute("""
            SELECT AVG(tare_reelle_pct) as tare_prod
            FROM lavages_jobs
            WHERE lot_id = %s 
              AND statut = 'TERMINÉ'
              AND tare_reelle_pct IS NOT NULL
        """, (lot_id,))
        
        tare_result = cursor.fetchone()
        
        # Flag lavage terminé (pour affichage écart)
        is_lavage_done = False
        
        if tare_result and tare_result['tare_prod']:
            tare_production = float(tare_result['tare_prod'])
            tare_prod_source = "✅ Mesurée"
            is_lavage_done = True
        else:
            tare_production = 22.0  # Standard
            tare_prod_source = "📊 Standard"
            is_lavage_done = False
        
        cursor.close()
        conn.close()
        
        # Calculs
        poids_net_paye = poids_brut * (1 - tare_achat / 100)
        poids_net_production = poids_brut * (1 - tare_production / 100)
        
        # ⭐ RECALCULER valeur lot avec nouveau poids
        valeur_lot = (poids_net_paye / 1000) * prix_achat
        
        # Écarts
        ecart_tare_vs_standard = tare_production - 22.0
        poids_gagne = (22.0 - tare_production) / 100 * poids_brut
        perte_vs_achat = poids_net_paye - poids_net_production
        
        return {
            'poids_brut': poids_brut / 1000,
            'tare_achat': tare_achat,
            'poids_net_paye': poids_net_paye / 1000,
            'valeur_lot': valeur_lot,
            'prix_achat': prix_achat,
            'tare_production': tare_production,
            'tare_prod_source': tare_prod_source,
            'poids_net_production': poids_net_production / 1000,
            'ecart_tare_vs_standard': ecart_tare_vs_standard,
            'poids_gagne': poids_gagne / 1000,
            'perte_vs_achat': perte_vs_achat / 1000,
            'is_lavage_done': is_lavage_done  # ⭐ NOUVEAU flag
        }
        
    except Exception as e:
        st.error(f"❌ Erreur récap valorisation : {str(e)}")
        return None

def get_lots_for_dropdown():
    """Récupère les lots pour dropdown avec format"""
    df = get_all_lots()
    if not df.empty:
        return {f"{row['id']} - {row['code_lot_interne']} - {row['nom_usage']}": row['id'] 
                for _, row in df.iterrows()}
    return {}

# ============================================================================
# ⭐ RÉCUPÉRATION LOT_ID DEPUIS QUERY PARAMS OU SESSION_STATE
# ============================================================================

# Récupérer depuis query params (navigation depuis page Lots)
query_params = st.query_params
lot_id_from_params = query_params.get("lot_id")

# Récupérer depuis session_state (sélection multiple page Lots)
selected_lots_from_session = st.session_state.get('selected_lots_for_details', [])

# ⭐ DÉTERMINER LOTS À AFFICHER
lots_to_display = []

if lot_id_from_params:
    # Navigation depuis page Lots (un seul lot)
    try:
        lots_to_display = [int(lot_id_from_params)]
    except:
        pass

if selected_lots_from_session and len(selected_lots_from_session) > 0:
    # Sélection multiple depuis page Lots
    lots_to_display = selected_lots_from_session

# ============================================================================
# AFFICHAGE - BOUCLE SUR TOUS LES LOTS SÉLECTIONNÉS
# ============================================================================

if len(lots_to_display) > 0:
    st.success(f"📦 **{len(lots_to_display)} lot(s) sélectionné(s)** depuis la page Lots")
    st.markdown("---")
    
    # ⭐ BOUCLE - AFFICHER CHAQUE LOT
    for idx, lot_id in enumerate(lots_to_display):
        # Séparateur entre lots
        if idx > 0:
            st.markdown("---")
            st.markdown("---")
        
        lot_info = get_lot_info(lot_id)
        
        if lot_info:
            # ⭐ Utiliser le poids réel depuis stock_emplacements (pas lots_bruts.poids_total_brut_kg qui est NULL)
            poids_reel = lot_info.get('poids_reel_stock_kg') or 0
            if poids_reel > 0:
                poids_display = f"{format_number_fr(poids_reel)} kg ({format_float_fr(poids_reel/1000)} T)"
            else:
                poids_display = "<em style='color: orange;'>Aucun emplacement - À créer ci-dessous</em>"
            
            # ⭐ CARTE INFO LOT
            st.markdown(f"""
            <div class="lot-card">
                <h3>📦 Lot #{lot_info['id']} - {lot_info['code_lot_interne']}</h3>
                <strong>Nom:</strong> {lot_info['nom_usage']}<br>
                <strong>Variété:</strong> {lot_info['nom_variete']}<br>
                <strong>Producteur:</strong> {lot_info['nom_producteur']}<br>
                <strong>Date entrée:</strong> {lot_info['date_entree_stock']}<br>
                <strong>Âge:</strong> {lot_info['age_jours']} jours<br>
                <strong>Poids total stock:</strong> {poids_display}
            </div>
            """, unsafe_allow_html=True)
            
            # KPIs emplacement
            df_empl = get_lot_emplacements(lot_id)
            
            if not df_empl.empty:
                st.markdown("---")
                
                # ============================================================================
                # ONGLETS PRINCIPAUX
                # ============================================================================
                
                tab1, tab2, tab3 = st.tabs(["📦 Emplacements", "📊 Valorisation", "📜 Historique"])
                
                # ============================================================================
                # ONGLET 1 : EMPLACEMENTS (KPIs + Tableau + Actions)
                # ============================================================================
                
                with tab1:
                    st.markdown(f"### 📦 Emplacements - Lot {lot_info['code_lot_interne']}")
                    
                col1, col2, col3, col4 = st.columns(4)
                
                with col1:
                    st.metric("📍 Emplacements", len(df_empl))
                
                with col2:
                    total_pallox = df_empl['nombre_unites'].sum()
                    st.metric("📦 Pallox total", format_number_fr(total_pallox))
                
                with col3:
                    total_tonnage = df_empl['poids_total_kg'].sum() / 1000
                    st.metric("⚖️ Tonnage", f"{format_float_fr(total_tonnage)} T")
                
                with col4:
                    statuts = df_empl['statut_lavage'].value_counts()
                    statut_principal = statuts.index[0] if len(statuts) > 0 else 'N/A'
                    
                    if statut_principal == 'BRUT':
                        emoji = '🟢'
                    elif statut_principal == 'LAVÉ':
                        emoji = '🧼'
                    elif statut_principal == 'GRENAILLES':
                        emoji = '🌾'
                    else:
                        emoji = '❓'
                    
                    st.metric("🏷️ Statut principal", f"{emoji} {statut_principal}")
                
                st.markdown("---")
                
                # Tableau emplacements avec calibres
                st.subheader(f"📋 Emplacements - Lot {lot_info['code_lot_interne']}")
                
                # ⭐ FILTRES CALIBRE (par seuil)
                with st.expander("🔍 Filtres calibre", expanded=False):
                    col_f1, col_f2, col_f3 = st.columns(3)
                    
                    with col_f1:
                        filtre_cal_min = st.number_input(
                            "Calibre min ≥", min_value=0, max_value=100, value=0,
                            key=f"filtre_cal_min_{lot_id}",
                            help="Afficher uniquement les emplacements avec calibre min ≥ cette valeur"
                        )
                    
                    with col_f2:
                        filtre_cal_max = st.number_input(
                            "Calibre max ≤", min_value=0, max_value=100, value=100,
                            key=f"filtre_cal_max_{lot_id}",
                            help="Afficher uniquement les emplacements avec calibre max ≤ cette valeur"
                        )
                    
                    with col_f3:
                        STATUTS_FILTRE = ["Tous", "BRUT", "LAVÉ", "GRENAILLES_BRUTES", "GRENAILLES_LAVÉES"]
                        filtre_statut = st.selectbox("Statut", STATUTS_FILTRE, key=f"filtre_statut_{lot_id}")
                
                # Appliquer filtres
                df_empl_filtre = df_empl.copy()
                
                if filtre_cal_min > 0:
                    df_empl_filtre = df_empl_filtre[
                        (df_empl_filtre['calibre_min'].fillna(0) >= filtre_cal_min)
                    ]
                
                if filtre_cal_max < 100:
                    df_empl_filtre = df_empl_filtre[
                        (df_empl_filtre['calibre_max'].fillna(100) <= filtre_cal_max)
                    ]
                
                if filtre_statut != "Tous":
                    df_empl_filtre = df_empl_filtre[
                        df_empl_filtre['statut_lavage'] == filtre_statut
                    ]
                
                # Message si filtrage actif
                if len(df_empl_filtre) != len(df_empl):
                    st.info(f"🔍 **{len(df_empl_filtre)}** emplacements affichés (sur {len(df_empl)} total)")
                
                # Créer colonne calibre formatée
                df_empl_filtre['calibre_display'] = df_empl_filtre.apply(
                    lambda row: f"{int(row['calibre_min'])}-{int(row['calibre_max'])}" 
                    if pd.notna(row['calibre_min']) and pd.notna(row['calibre_max']) 
                    else "-", axis=1
                )
                
                display_cols = ['id', 'site_stockage', 'emplacement_stockage', 'nombre_unites', 
                               'type_conditionnement', 'poids_total_kg', 'statut_lavage_display', 'calibre_display']
                
                df_display = df_empl_filtre[display_cols].copy()
                
                # Formatter les colonnes numériques
                df_display['nombre_unites_fmt'] = df_display['nombre_unites'].apply(format_number_fr)
                df_display['poids_total_kg_fmt'] = df_display['poids_total_kg'].apply(lambda x: format_number_fr(x) if pd.notna(x) else "0")
                
                df_display = df_display.rename(columns={
                    'id': 'ID',
                    'site_stockage': 'Site',
                    'emplacement_stockage': 'Emplacement',
                    'nombre_unites_fmt': 'Pallox',
                    'type_conditionnement': 'Type',
                    'poids_total_kg_fmt': 'Poids (kg)',
                    'statut_lavage_display': 'Statut',
                    'calibre_display': 'Calibre'
                })
                
                # Supprimer colonnes non formatées
                df_display = df_display.drop(['nombre_unites', 'poids_total_kg'], axis=1)
                
                st.dataframe(
                    df_display,
                    use_container_width=True,
                    hide_index=True
                )
                
                # ⭐ BOUTONS ACTIONS
                st.markdown("---")
                st.subheader(f"⚙️ Actions - Lot {lot_info['code_lot_interne']}")
                
                col1, col2, col3, col4 = st.columns(4)
                
                with col1:
                    if st.button(f"➕ Ajouter", key=f"btn_add_{lot_id}", use_container_width=True):
                        st.session_state[f'show_add_form_{lot_id}'] = True
                        st.rerun()
                
                with col2:
                    if st.button(f"🔄 Transférer", key=f"btn_transfer_{lot_id}", use_container_width=True):
                        st.session_state[f'show_transfer_form_{lot_id}'] = True
                        st.rerun()
                
                with col3:
                    if st.button(f"✏️ Modifier", key=f"btn_modify_{lot_id}", use_container_width=True):
                        st.session_state[f'show_modify_form_{lot_id}'] = True
                        st.rerun()
                
                with col4:
                    if st.button(f"🗑️ Supprimer", key=f"btn_delete_{lot_id}", use_container_width=True):
                        st.session_state[f'show_delete_form_{lot_id}'] = True
                        st.rerun()
                
                # ⭐ FORMULAIRE AJOUTER - AVEC CALIBRE ET STATUT
                if st.session_state.get(f'show_add_form_{lot_id}', False):
                    st.markdown("---")
                    st.markdown(f"##### ➕ Ajouter Emplacement - Lot {lot_info['code_lot_interne']}")
                    
                    # ⭐ Calculer nombre unités suggéré depuis lot (protégé NaN/None)
                    _poids_raw = lot_info.get('poids_total_brut_kg')
                    poids_brut_lot = float(_poids_raw) if pd.notna(_poids_raw) else 0.0
                    
                    # Estimer nombre pallox selon poids (Pallox standard 1900kg)
                    nombre_suggere = max(1, int(round(poids_brut_lot / 1900))) if poids_brut_lot > 0 else 1
                    
                    st.info(f"💡 **Poids total lot** : {format_number_fr(poids_brut_lot)} kg → Suggéré : **{nombre_suggere} Pallox**")
                    
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        sites = get_sites_stockage()
                        site = st.selectbox("Site *", options=[""] + sites, key=f"add_site_{lot_id}")
                        
                        if site:
                            emplacements = get_emplacements_by_site(site)
                            empl_options = [""] + [e[0] for e in emplacements]
                            emplacement = st.selectbox("Emplacement *", options=empl_options, key=f"add_empl_{lot_id}")
                        else:
                            emplacement = None
                    
                    with col2:
                        # ⭐ Pré-remplir avec nombre suggéré
                        nombre = st.number_input("Nombre unités *", min_value=1, value=nombre_suggere, key=f"add_nb_{lot_id}")
                        
                        # ⭐ Type par défaut Pallox (le plus courant)
                        TYPES = ["Pallox", "Petit Pallox", "Big Bag"]
                        type_cond = st.selectbox("Type *", options=TYPES, index=0, key=f"add_type_{lot_id}")
                        
                        # Calcul poids théorique
                        if type_cond == 'Pallox':
                            poids_unit_theorique = 1900
                        elif type_cond == 'Petit Pallox':
                            poids_unit_theorique = 1200
                        else:
                            poids_unit_theorique = 1600
                        
                        poids_theorique = nombre * poids_unit_theorique
                    
                    # ⭐ STATUT LAVAGE ET CALIBRE
                    st.markdown("---")
                    st.markdown("**🏷️ Statut et Calibre**")
                    
                    col_statut, col_cal_min, col_cal_max = st.columns([2, 1, 1])
                    
                    with col_statut:
                        STATUTS = ["BRUT", "LAVÉ", "GRENAILLES_BRUTES", "GRENAILLES_LAVÉES"]
                        statut_lavage = st.selectbox("Statut lavage *", options=STATUTS, index=0, key=f"add_statut_{lot_id}")
                    
                    with col_cal_min:
                        # Pré-remplir avec calibre du lot si disponible (gérer NaN)
                        cal_min_raw = lot_info.get('calibre_min')
                        cal_min_defaut = int(cal_min_raw) if pd.notna(cal_min_raw) else 0
                        calibre_min = st.number_input("Calibre min *", min_value=0, max_value=100, value=cal_min_defaut, key=f"add_cal_min_{lot_id}")
                    
                    with col_cal_max:
                        cal_max_raw = lot_info.get('calibre_max')
                        cal_max_defaut = int(cal_max_raw) if pd.notna(cal_max_raw) else 75
                        calibre_max = st.number_input("Calibre max *", min_value=0, max_value=100, value=cal_max_defaut, key=f"add_cal_max_{lot_id}")
                    
                    # Validation calibre
                    if calibre_min >= calibre_max:
                        st.error("❌ Calibre min doit être < calibre max")
                    
                    # ⭐ POIDS MODIFIABLE (ligne complète)
                    st.markdown("---")
                    st.markdown("**⚖️ Poids Total**")
                    
                    col_info, col_poids = st.columns([1, 1])
                    
                    with col_info:
                        st.info(f"💡 **Poids théorique** : {format_number_fr(poids_theorique)} kg\n\n({nombre} × {format_number_fr(poids_unit_theorique)} kg/unité)")
                    
                    with col_poids:
                        # ⭐ Clé dynamique pour forcer mise à jour quand nombre/type change
                        poids_total_saisi = st.number_input(
                            "Poids Total Réel (kg) *",
                            min_value=0.0,
                            value=float(poids_theorique),
                            step=100.0,
                            help="💡 Modifiez si pesée camion différente du théorique",
                            key=f"add_poids_{lot_id}_{nombre}_{type_cond}"
                        )
                        
                        # Afficher différence si modifié
                        if abs(poids_total_saisi - poids_theorique) > 1:
                            poids_unit_reel = poids_total_saisi / nombre
                            diff_pct = ((poids_total_saisi - poids_theorique) / poids_theorique) * 100
                            
                            if diff_pct > 0:
                                st.warning(f"⚠️ **Poids supérieur** : +{format_number_fr(abs(diff_pct))}%\n\nPoids moyen : **{format_number_fr(poids_unit_reel)} kg/unité**")
                            else:
                                st.warning(f"⚠️ **Poids inférieur** : -{format_number_fr(abs(diff_pct))}%\n\nPoids moyen : **{format_number_fr(poids_unit_reel)} kg/unité**")
                    
                    st.markdown("---")
                    
                    col_save, col_cancel = st.columns(2)
                    
                    with col_save:
                        can_save = calibre_min < calibre_max
                        if st.button("💾 Enregistrer", key=f"save_add_{lot_id}", type="primary", use_container_width=True, disabled=not can_save):
                            if site and emplacement and nombre and type_cond:
                                # ⭐ Passer le poids saisi, statut et calibre à la fonction
                                success, message = add_emplacement(
                                    lot_id, site, emplacement, nombre, type_cond,
                                    statut_lavage=statut_lavage,
                                    poids_total_saisi=poids_total_saisi,
                                    calibre_min=calibre_min,
                                    calibre_max=calibre_max
                                )
                                if success:
                                    st.success(message)
                                    st.session_state.pop(f'show_add_form_{lot_id}')
                                    st.rerun()
                                else:
                                    st.error(message)
                            else:
                                st.error("❌ Tous les champs sont obligatoires")
                    
                    with col_cancel:
                        if st.button("❌ Annuler", key=f"cancel_add_{lot_id}", use_container_width=True):
                            st.session_state.pop(f'show_add_form_{lot_id}')
                            st.rerun()
                
                # ⭐ FORMULAIRE TRANSFÉRER
                if st.session_state.get(f'show_transfer_form_{lot_id}', False):
                    st.markdown("---")
                    st.markdown(f"##### 🔄 Transférer Stock - Lot {lot_info['code_lot_interne']}")
                    
                    # Sélection source
                    empl_options = {f"{row['id']} - {row['site_stockage']} / {row['emplacement_stockage']} ({format_number_fr(row['nombre_unites'])} pallox)": row['id'] 
                                   for _, row in df_empl.iterrows()}
                    
                    selected_source = st.selectbox("Emplacement source *", options=[""] + list(empl_options.keys()), key=f"transfer_source_{lot_id}")
                    
                    if selected_source and selected_source != "":
                        empl_source_id = empl_options[selected_source]
                        
                        # Récupérer quantité max
                        empl_data = df_empl[df_empl['id'] == empl_source_id].iloc[0]
                        quantite_max = int(empl_data['nombre_unites'])
                        
                        col1, col2 = st.columns(2)
                        
                        with col1:
                            if quantite_max <= 1:
                                # 1 seul pallox : pas de slider possible (min == max), transfert total
                                quantite_transfert = 1
                                st.number_input(
                                    "Quantité à transférer *",
                                    min_value=1, max_value=1, value=1, disabled=True,
                                    key=f"transfer_qty_{lot_id}",
                                    help="1 seul pallox disponible : transfert total."
                                )
                            else:
                                quantite_transfert = st.slider(
                                    "Quantité à transférer *",
                                    min_value=1,
                                    max_value=quantite_max,
                                    value=min(5, quantite_max),
                                    key=f"transfer_qty_{lot_id}"
                                )
                        
                        with col2:
                            sites = get_sites_stockage()
                            site_dest = st.selectbox("Site destination *", options=[""] + sites, key=f"transfer_site_{lot_id}")
                            
                            if site_dest:
                                emplacements = get_emplacements_by_site(site_dest)
                                empl_options_dest = [""] + [e[0] for e in emplacements]
                                empl_dest = st.selectbox("Emplacement destination *", options=empl_options_dest, key=f"transfer_empl_{lot_id}")
                            else:
                                empl_dest = None
                        
                        col_save, col_cancel = st.columns(2)
                        
                        with col_save:
                            if st.button("💾 Transférer", key=f"save_transfer_{lot_id}", type="primary", use_container_width=True):
                                if site_dest and empl_dest:
                                    success, message = transfer_emplacement(lot_id, empl_source_id, quantite_transfert, site_dest, empl_dest)
                                    if success:
                                        st.success(message)
                                        st.session_state.pop(f'show_transfer_form_{lot_id}')
                                        st.rerun()
                                    else:
                                        st.error(message)
                                else:
                                    st.error("❌ Destination obligatoire")
                        
                        with col_cancel:
                            if st.button("❌ Annuler", key=f"cancel_transfer_{lot_id}", use_container_width=True):
                                st.session_state.pop(f'show_transfer_form_{lot_id}')
                                st.rerun()
                    else:
                        st.info("👆 Sélectionnez un emplacement source")
                
                # ⭐ FORMULAIRE MODIFIER COMPLET (type, quantité, statut, calibre, poids)
                if st.session_state.get(f'show_modify_form_{lot_id}', False):
                    st.markdown("---")
                    st.markdown(f"##### ✏️ Modifier Emplacement - Lot {lot_info['code_lot_interne']}")
                    
                    # Fonction helper pour convertir calibre (gère NaN)
                    def safe_int(val, default=0):
                        if pd.isna(val) or val is None:
                            return default
                        try:
                            return int(val)
                        except:
                            return default
                    
                    # Sélection emplacement avec plus d'infos
                    empl_options = {
                        f"{row['id']} - {row['site_stockage']}/{row['emplacement_stockage']} | {row['statut_lavage']} | {format_number_fr(row['nombre_unites'])} {row['type_conditionnement']} | {safe_int(row['calibre_min'])}-{safe_int(row['calibre_max'])}": row['id'] 
                        for _, row in df_empl.iterrows()
                    }
                    
                    selected_empl = st.selectbox("Emplacement à modifier *", options=[""] + list(empl_options.keys()), key=f"modify_empl_{lot_id}")
                    
                    if selected_empl and selected_empl != "":
                        empl_id = empl_options[selected_empl]
                        
                        # Récupérer données actuelles
                        empl_data = df_empl[df_empl['id'] == empl_id].iloc[0]
                        
                        st.info(f"📍 Valeurs actuelles : **{int(empl_data['nombre_unites'])} {empl_data['type_conditionnement']}** | **{empl_data['statut_lavage']}** | Calibre **{safe_int(empl_data['calibre_min'])}-{safe_int(empl_data['calibre_max'])}** | **{format_number_fr(empl_data['poids_total_kg'])} kg**")
                        
                        st.markdown("---")
                        
                        # ⭐ SECTION 1 : Type et Quantité
                        st.markdown("**📦 Type et Quantité**")
                        col1, col2 = st.columns(2)
                        
                        with col1:
                            TYPES = ["Pallox", "Petit Pallox", "Big Bag"]
                            type_actuel_idx = TYPES.index(empl_data['type_conditionnement']) if empl_data['type_conditionnement'] in TYPES else 0
                            nouveau_type = st.selectbox("Type conditionnement", options=TYPES, index=type_actuel_idx, key=f"modify_type_{lot_id}")
                        
                        with col2:
                            quantite_actuelle = int(empl_data['nombre_unites'])
                            nouvelle_quantite = st.number_input(
                                "Nombre unités",
                                min_value=1,
                                value=quantite_actuelle,
                                key=f"modify_qty_{lot_id}"
                            )
                        
                        # ⭐ SECTION 2 : Statut Lavage
                        st.markdown("---")
                        st.markdown("**🏷️ Statut Lavage**")
                        
                        STATUTS = ["BRUT", "LAVÉ", "GRENAILLES_BRUTES", "GRENAILLES_LAVÉES"]
                        statut_actuel_idx = STATUTS.index(empl_data['statut_lavage']) if empl_data['statut_lavage'] in STATUTS else 0
                        nouveau_statut = st.selectbox("Statut lavage", options=STATUTS, index=statut_actuel_idx, key=f"modify_statut_{lot_id}")
                        
                        if nouveau_statut != empl_data['statut_lavage']:
                            st.warning(f"⚠️ Changement de statut : **{empl_data['statut_lavage']}** → **{nouveau_statut}** (sera tracé dans l'historique)")
                        
                        # ⭐ SECTION 3 : Calibre
                        st.markdown("---")
                        st.markdown("**📏 Calibre**")
                        col_cal_min, col_cal_max = st.columns(2)
                        
                        with col_cal_min:
                            cal_min_val = empl_data['calibre_min']
                            cal_min_default = int(cal_min_val) if pd.notna(cal_min_val) else 0
                            nouveau_calibre_min = st.number_input(
                                "Calibre min",
                                min_value=0, max_value=100,
                                value=cal_min_default,
                                key=f"modify_cal_min_{lot_id}"
                            )
                        
                        with col_cal_max:
                            cal_max_val = empl_data['calibre_max']
                            cal_max_default = int(cal_max_val) if pd.notna(cal_max_val) else 75
                            nouveau_calibre_max = st.number_input(
                                "Calibre max",
                                min_value=0, max_value=100,
                                value=cal_max_default,
                                key=f"modify_cal_max_{lot_id}"
                            )
                        
                        # Validation calibre
                        if nouveau_calibre_min >= nouveau_calibre_max:
                            st.error("❌ Calibre min doit être < calibre max")
                        
                        # ⭐ SECTION 4 : Poids
                        st.markdown("---")
                        st.markdown("**⚖️ Poids**")
                        
                        # Calcul poids théorique selon nouveau type
                        if nouveau_type == 'Pallox':
                            poids_unit_theorique = 1900
                        elif nouveau_type == 'Petit Pallox':
                            poids_unit_theorique = 1200
                        else:
                            poids_unit_theorique = 1600
                        
                        poids_theorique = nouvelle_quantite * poids_unit_theorique
                        
                        col_info, col_poids = st.columns([1, 1])
                        
                        with col_info:
                            st.info(f"💡 **Poids théorique** : {format_number_fr(poids_theorique)} kg\n\n({nouvelle_quantite} × {poids_unit_theorique} kg)")
                        
                        with col_poids:
                            nouveau_poids = st.number_input(
                                "Poids Total (kg)",
                                min_value=0.0,
                                value=float(poids_theorique),
                                step=100.0,
                                key=f"modify_poids_{lot_id}_{nouvelle_quantite}_{nouveau_type}"
                            )
                        
                        st.markdown("---")
                        
                        col_save, col_cancel = st.columns(2)
                        
                        can_save = nouveau_calibre_min < nouveau_calibre_max
                        
                        with col_save:
                            if st.button("💾 Enregistrer", key=f"save_modify_{lot_id}", type="primary", use_container_width=True, disabled=not can_save):
                                success, message = modify_emplacement_complet(
                                    empl_id,
                                    nouvelle_quantite=nouvelle_quantite,
                                    nouveau_type=nouveau_type,
                                    nouveau_statut=nouveau_statut,
                                    nouveau_poids=nouveau_poids,
                                    nouveau_calibre_min=nouveau_calibre_min,
                                    nouveau_calibre_max=nouveau_calibre_max
                                )
                                if success:
                                    st.success(message)
                                    st.session_state.pop(f'show_modify_form_{lot_id}')
                                    st.rerun()
                                else:
                                    st.error(message)
                        
                        with col_cancel:
                            if st.button("❌ Annuler", key=f"cancel_modify_{lot_id}", use_container_width=True):
                                st.session_state.pop(f'show_modify_form_{lot_id}')
                                st.rerun()
                    else:
                        st.info("👆 Sélectionnez un emplacement")
                
                # ⭐ FORMULAIRE SUPPRIMER
                if st.session_state.get(f'show_delete_form_{lot_id}', False):
                    st.markdown("---")
                    st.markdown(f"##### 🗑️ Supprimer Emplacement - Lot {lot_info['code_lot_interne']}")
                    
                    # Sélection emplacement
                    empl_options = {f"{row['id']} - {row['site_stockage']} / {row['emplacement_stockage']} ({format_number_fr(row['nombre_unites'])} pallox)": row['id'] 
                                   for _, row in df_empl.iterrows()}
                    
                    selected_empl = st.selectbox("Emplacement à supprimer *", options=[""] + list(empl_options.keys()), key=f"delete_empl_{lot_id}")
                    
                    if selected_empl and selected_empl != "":
                        empl_id = empl_options[selected_empl]
                        
                        st.warning(f"⚠️ Confirmer la suppression de : **{selected_empl}**")
                        
                        col_confirm, col_cancel = st.columns(2)
                        
                        with col_confirm:
                            if st.button("✅ CONFIRMER", key=f"confirm_delete_{lot_id}", type="primary", use_container_width=True):
                                success, message = delete_emplacement(empl_id)
                                if success:
                                    st.success(message)
                                    st.session_state.pop(f'show_delete_form_{lot_id}')
                                    st.rerun()
                                else:
                                    st.error(message)
                        
                        with col_cancel:
                            if st.button("❌ ANNULER", key=f"cancel_delete_{lot_id}", use_container_width=True):
                                st.session_state.pop(f'show_delete_form_{lot_id}')
                                st.rerun()
                    else:
                        st.info("👆 Sélectionnez un emplacement")
                
                # Historique mouvements

                # ============================================================================
                # ONGLET 2 : VALORISATION
                # ============================================================================
                
                with tab2:
                    st.markdown(f"### 📊 Valorisation - Lot {lot_info['code_lot_interne']}")
                    
                    recap = get_recap_valorisation_lot(lot_id)
                    
                    if recap:
                        col1, col2 = st.columns(2)
                        
                        with col1:
                            st.markdown(f"""
                            <div style='background-color: #e3f2fd; padding: 1rem; border-radius: 0.5rem; border-left: 4px solid #2196f3; height: 300px;'>
                                <h4 style='margin-top: 0; color: #1976d2;'>💰 VALEUR ACHAT</h4>
                                <p style='margin: 0.3rem 0;'><strong>Poids total emplacements:</strong> {recap['poids_brut']:.1f} T</p>
                                <p style='margin: 0.3rem 0;'><strong>Tare achat négociée:</strong> {recap['tare_achat']:.1f}%</p>
                                <p style='margin: 0.3rem 0;'><strong>Poids net payé:</strong> {recap['poids_net_paye']:.1f} T</p>
                                <hr style='margin: 0.5rem 0;'>
                                <p style='margin: 0.3rem 0; font-size: 1.1rem;'><strong>Prix achat:</strong> {recap['prix_achat']:.2f} €/T</p>
                                <p style='margin: 0.3rem 0; font-size: 1.1rem;'><strong>Valeur lot:</strong> {recap['valeur_lot']:,.0f} €</p>
                            </div>
                            """, unsafe_allow_html=True)
                        
                        with col2:
                            # ⭐ Logique affichage écart selon si lot lavé ou non
                            if not recap.get('is_lavage_done'):
                                # Lot pas encore lavé : affichage neutre gris
                                color_ecart = "#757575"
                                titre_ecart = "⏳ LOT PAS ENCORE LAVÉ"
                                contenu_ecart = "<p style='margin: 0.3rem 0; color: #757575; font-style: italic;'>Les écarts vs standard 22% seront calculés après lavage</p>"
                            elif recap['ecart_tare_vs_standard'] < 0:
                                # Lot lavé avec bonne performance : vert
                                color_ecart = "#2e7d32"
                                titre_ecart = "✅ ÉCARTS vs Standard 22%"
                                contenu_ecart = f"<p style='margin: 0.3rem 0; color: {color_ecart};'><strong>Écart tare:</strong> {recap['ecart_tare_vs_standard']:+.1f} points</p><p style='margin: 0.3rem 0; color: {color_ecart};'><strong>Poids gagné/perdu:</strong> {recap['poids_gagne']:+.2f} T</p>"
                            else:
                                # Lot lavé avec mauvaise performance : rouge
                                color_ecart = "#d32f2f"
                                titre_ecart = "⚠️ ÉCARTS vs Standard 22%"
                                contenu_ecart = f"<p style='margin: 0.3rem 0; color: {color_ecart};'><strong>Écart tare:</strong> {recap['ecart_tare_vs_standard']:+.1f} points</p><p style='margin: 0.3rem 0; color: {color_ecart};'><strong>Poids gagné/perdu:</strong> {recap['poids_gagne']:+.2f} T</p>"
                            
                            st.markdown(f"""<div style='background-color: #fff3e0; padding: 1rem; border-radius: 0.5rem; border-left: 4px solid #ff9800; height: 300px;'>
<h4 style='margin-top: 0; color: #f57c00;'>🏭 MATIÈRE PREMIÈRE PRODUCTION</h4>
<p style='margin: 0.3rem 0;'><strong>Tare production:</strong> {recap['tare_production']:.1f}% <span style='font-size: 0.85rem;'>{recap['tare_prod_source']}</span></p>
<p style='margin: 0.3rem 0;'><strong>Poids net production:</strong> {recap['poids_net_production']:.1f} T</p>
<hr style='margin: 0.5rem 0;'>
<h4 style='margin-top: 0.5rem; margin-bottom: 0.3rem; color: {color_ecart};'>{titre_ecart}</h4>
{contenu_ecart}
<hr style='margin: 0.5rem 0;'>
<h4 style='margin-top: 0.5rem; margin-bottom: 0.3rem;'>vs Achat payé</h4>
<p style='margin: 0.3rem 0;'><strong>Perte production:</strong> {recap['perte_vs_achat']:.2f} T</p>
</div>""", unsafe_allow_html=True)
                        
                        st.caption("💡 **Tare achat** : Négociée avec producteur (valorisation financière) | **Tare production** : Réelle après lavage ou standard 22% (matière disponible)")
                    else:
                        st.info("📊 Lot non qualifié (prix/tare d'achat manquant ou aucun emplacement actif)")
                        st.caption("💡 Qualifiez ce lot dans la page **Valorisation** et ajoutez des emplacements pour voir le récap détaillé")
                
                # ============================================================================
                # ONGLET 3 : HISTORIQUE
                # ============================================================================
                
                with tab3:
                    st.markdown(f"### 📜 Historique - Lot {lot_info['code_lot_interne']}")
                    
                    df_mvt = get_lot_mouvements(lot_id)
                    
                    if not df_mvt.empty:
                        # Formatter colonnes numériques
                        df_mvt_display = df_mvt.copy()
                        
                        if 'quantite' in df_mvt_display.columns:
                            df_mvt_display['quantite'] = df_mvt_display['quantite'].apply(format_number_fr)
                        
                        if 'poids_kg' in df_mvt_display.columns:
                            df_mvt_display['poids_kg'] = df_mvt_display['poids_kg'].apply(lambda x: format_number_fr(x) if pd.notna(x) else "0")
                        
                        st.dataframe(df_mvt_display, use_container_width=True, hide_index=True)
                    else:
                        st.info("Aucun mouvement enregistré")
            
            else:
                st.warning(f"⚠️ Aucun emplacement pour le lot #{lot_id}")
                st.info("💡 Utilisez le bouton '➕ Ajouter' ci-dessous pour créer un emplacement")
                
                # Permettre ajout même si aucun emplacement
                if st.button(f"➕ Ajouter Premier Emplacement", key=f"btn_add_first_{lot_id}", use_container_width=True, type="primary"):
                    st.session_state[f'show_add_form_{lot_id}'] = True
                    st.rerun()
                
                # Formulaire ajout (même si aucun emplacement) - AVEC DONNÉES DU LOT
                if st.session_state.get(f'show_add_form_{lot_id}', False):
                    st.markdown("---")
                    st.markdown(f"##### ➕ Ajouter Emplacement - Lot {lot_info['code_lot_interne']}")
                    
                    # ⭐ Calculer nombre unités suggéré depuis lot (protégé NaN/None)
                    _poids_raw = lot_info.get('poids_total_brut_kg')
                    poids_brut_lot = float(_poids_raw) if pd.notna(_poids_raw) else 0.0
                    nombre_suggere = max(1, int(round(poids_brut_lot / 1900))) if poids_brut_lot > 0 else 1
                    
                    st.info(f"💡 **Poids total lot** : {format_number_fr(poids_brut_lot)} kg → Suggéré : **{nombre_suggere} Pallox**")
                    
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        sites = get_sites_stockage()
                        site = st.selectbox("Site *", options=[""] + sites, key=f"add_site_first_{lot_id}")
                        
                        if site:
                            emplacements = get_emplacements_by_site(site)
                            empl_options = [""] + [e[0] for e in emplacements]
                            emplacement = st.selectbox("Emplacement *", options=empl_options, key=f"add_empl_first_{lot_id}")
                        else:
                            emplacement = None
                    
                    with col2:
                        nombre = st.number_input("Nombre unités *", min_value=1, value=nombre_suggere, key=f"add_nb_first_{lot_id}")
                        
                        TYPES = ["Pallox", "Petit Pallox", "Big Bag"]
                        type_cond = st.selectbox("Type *", options=TYPES, index=0, key=f"add_type_first_{lot_id}")
                        
                        # Calcul poids théorique
                        if type_cond == 'Pallox':
                            poids_unit_theorique = 1900
                        elif type_cond == 'Petit Pallox':
                            poids_unit_theorique = 1200
                        else:
                            poids_unit_theorique = 1600
                        
                        poids_theorique = nombre * poids_unit_theorique
                    
                    # ⭐ STATUT LAVAGE ET CALIBRE
                    st.markdown("---")
                    st.markdown("**🏷️ Statut et Calibre**")
                    
                    col_statut, col_cal_min, col_cal_max = st.columns([2, 1, 1])
                    
                    with col_statut:
                        STATUTS = ["BRUT", "LAVÉ", "GRENAILLES_BRUTES", "GRENAILLES_LAVÉES"]
                        statut_lavage = st.selectbox("Statut lavage *", options=STATUTS, index=0, key=f"add_statut_first_{lot_id}")
                    
                    with col_cal_min:
                        cal_min_raw = lot_info.get('calibre_min')
                        cal_min_defaut = int(cal_min_raw) if pd.notna(cal_min_raw) else 0
                        calibre_min = st.number_input("Calibre min *", min_value=0, max_value=100, value=cal_min_defaut, key=f"add_cal_min_first_{lot_id}")
                    
                    with col_cal_max:
                        cal_max_raw = lot_info.get('calibre_max')
                        cal_max_defaut = int(cal_max_raw) if pd.notna(cal_max_raw) else 75
                        calibre_max = st.number_input("Calibre max *", min_value=0, max_value=100, value=cal_max_defaut, key=f"add_cal_max_first_{lot_id}")
                    
                    # Validation calibre
                    if calibre_min >= calibre_max:
                        st.error("❌ Calibre min doit être < calibre max")
                    
                    # ⭐ POIDS MODIFIABLE (ligne complète)
                    st.markdown("---")
                    st.markdown("**⚖️ Poids Total**")
                    
                    col_info, col_poids = st.columns([1, 1])
                    
                    with col_info:
                        st.info(f"💡 **Poids théorique** : {format_number_fr(poids_theorique)} kg\n\n({nombre} × {format_number_fr(poids_unit_theorique)} kg/unité)")
                    
                    with col_poids:
                        # ⭐ Clé dynamique pour forcer mise à jour quand nombre/type change
                        poids_total_saisi = st.number_input(
                            "Poids Total Réel (kg) *",
                            min_value=0.0,
                            value=float(poids_theorique),
                            step=100.0,
                            help="💡 Modifiez si pesée camion différente du théorique",
                            key=f"add_poids_first_{lot_id}_{nombre}_{type_cond}"
                        )
                        
                        # Afficher différence si modifié
                        if abs(poids_total_saisi - poids_theorique) > 1:
                            poids_unit_reel = poids_total_saisi / nombre
                            diff_pct = ((poids_total_saisi - poids_theorique) / poids_theorique) * 100
                            
                            if diff_pct > 0:
                                st.warning(f"⚠️ **Poids supérieur** : +{format_number_fr(abs(diff_pct))}%\n\nPoids moyen : **{format_number_fr(poids_unit_reel)} kg/unité**")
                            else:
                                st.warning(f"⚠️ **Poids inférieur** : -{format_number_fr(abs(diff_pct))}%\n\nPoids moyen : **{format_number_fr(poids_unit_reel)} kg/unité**")
                    
                    st.markdown("---")
                    
                    col_save, col_cancel = st.columns(2)
                    
                    with col_save:
                        can_save = calibre_min < calibre_max
                        if st.button("💾 Enregistrer", key=f"save_add_first_{lot_id}", type="primary", use_container_width=True, disabled=not can_save):
                            if site and emplacement and nombre and type_cond:
                                # ⭐ Passer le poids saisi, statut et calibre à la fonction
                                success, message = add_emplacement(
                                    lot_id, site, emplacement, nombre, type_cond,
                                    statut_lavage=statut_lavage,
                                    poids_total_saisi=poids_total_saisi,
                                    calibre_min=calibre_min,
                                    calibre_max=calibre_max
                                )
                                if success:
                                    st.success(message)
                                    st.session_state.pop(f'show_add_form_{lot_id}')
                                    st.rerun()
                                else:
                                    st.error(message)
                            else:
                                st.error("❌ Tous les champs sont obligatoires")
                    
                    with col_cancel:
                        if st.button("❌ Annuler", key=f"cancel_add_first_{lot_id}", use_container_width=True):
                            st.session_state.pop(f'show_add_form_{lot_id}')
                            st.rerun()
        
        else:
            st.error(f"❌ Lot #{lot_id} introuvable")

else:
    # Aucun lot sélectionné - Afficher sélection manuelle AVEC FILTRES
    st.info("ℹ️ Aucun lot sélectionné depuis la page Lots")
    st.markdown("---")
    st.subheader("🔍 Sélectionner un lot manuellement")
    
    # ⭐ CHARGER TOUS LES LOTS
    df_all_lots = get_all_lots()
    
    if not df_all_lots.empty:
        # ⭐ FILTRES (comme page 02_Lots)
        st.markdown("#### Filtres")
        col1, col2, col3 = st.columns(3)
        
        with col1:
            search_nom = st.text_input("Nom usage", key="filter_nom_manual", placeholder="Rechercher...")
        
        with col2:
            varietes = ['Toutes'] + sorted(df_all_lots['nom_variete'].dropna().unique().tolist())
            selected_variete = st.selectbox("Variété", varietes, key="filter_variete_manual")
        
        with col3:
            producteurs = ['Tous'] + sorted(df_all_lots['nom_producteur'].dropna().unique().tolist())
            selected_producteur = st.selectbox("Producteur", producteurs, key="filter_producteur_manual")
        
        # Appliquer filtres
        df_filtered = df_all_lots.copy()
        
        if search_nom:
            df_filtered = df_filtered[df_filtered['nom_usage'].str.contains(search_nom, case=False, na=False)]
        
        if selected_variete != 'Toutes':
            df_filtered = df_filtered[df_filtered['nom_variete'] == selected_variete]
        
        if selected_producteur != 'Tous':
            df_filtered = df_filtered[df_filtered['nom_producteur'] == selected_producteur]
        
        st.markdown("---")
        
        if not df_filtered.empty:
            st.info(f"📊 {len(df_filtered)} lot(s) affiché(s) sur {len(df_all_lots)} total")
            
            # Dropdown depuis lots filtrés
            lots_dict_filtered = {f"{row['id']} - {row['code_lot_interne']} - {row['nom_usage']}": row['id'] 
                                 for _, row in df_filtered.iterrows()}
            
            selected_lot_str = st.selectbox(
                "Choisir un lot",
                options=[""] + list(lots_dict_filtered.keys()),
                key="manual_lot_selection"
            )
            
            if selected_lot_str and selected_lot_str != "":
                selected_lot_id = lots_dict_filtered[selected_lot_str]
                
                if st.button("📦 Afficher ce lot", type="primary", use_container_width=True):
                    # Mettre en session_state et rerun
                    st.session_state.selected_lots_for_details = [selected_lot_id]
                    st.rerun()
        else:
            st.warning(f"⚠️ Aucun lot trouvé avec ces filtres")
    else:
        st.warning("⚠️ Aucun lot disponible")

show_footer()
