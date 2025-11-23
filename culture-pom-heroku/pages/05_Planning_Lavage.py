import streamlit as st
import pandas as pd
import math
import time
from datetime import datetime, timedelta
from database import get_connection
from components import show_footer
from auth import is_authenticated, is_admin
import io

st.set_page_config(page_title="Planning Lavage - Culture Pom", page_icon="🧼", layout="wide")

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
    .job-card {
        background-color: #f0f2f6;
        padding: 1rem;
        border-radius: 0.5rem;
        margin: 0.5rem 0;
        border-left: 4px solid #1f77b4;
    }
    .job-card.en-cours {
        border-left-color: #ff7f0e;
        background-color: #fff3e0;
    }
    .job-card.termine {
        border-left-color: #2ca02c;
        background-color: #e8f5e9;
    }
</style>
""", unsafe_allow_html=True)

if not is_authenticated():
    st.warning("⚠️ Veuillez vous connecter pour accéder à cette page")
    st.stop()

st.title("🧼 Planning Lavage")
st.markdown("*Gestion des jobs de lavage - SAINT_FLAVY uniquement*")
st.markdown("---")

# ==========================================
# FONCTIONS UTILITAIRES
# ==========================================

def get_lots_bruts_disponibles():
    """Récupère les lots bruts disponibles pour lavage"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        query = """
        SELECT 
            l.id as lot_id,
            l.code_lot_interne,
            l.nom_usage,
            l.calibre_min,
            l.calibre_max,
            COALESCE(v.nom_variete, l.code_variete) as variete,
            se.id as emplacement_id,
            se.site_stockage,
            se.emplacement_stockage,
            se.nombre_unites,
            se.poids_total_kg,
            se.type_conditionnement
        FROM lots_bruts l
        JOIN stock_emplacements se ON l.id = se.lot_id
        LEFT JOIN ref_varietes v ON l.code_variete = v.code_variete
        WHERE se.is_active = TRUE 
          AND se.statut_lavage = 'BRUT'
          AND se.nombre_unites > 0
        ORDER BY l.code_lot_interne
        """
        
        cursor.execute(query)
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
            return df
        return pd.DataFrame()
        
    except Exception as e:
        st.error(f"❌ Erreur chargement lots : {str(e)}")
        return pd.DataFrame()

def get_emplacements_saint_flavy():
    """Récupère les emplacements disponibles à SAINT_FLAVY"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        query = """
        SELECT code_emplacement, nom_complet
        FROM ref_sites_stockage
        WHERE code_site = 'SAINT_FLAVY' AND is_active = TRUE
        ORDER BY code_emplacement
        """
        
        cursor.execute(query)
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        
        if rows:
            return [(row['code_emplacement'], row['nom_complet']) for row in rows]
        return []
        
    except Exception as e:
        st.error(f"❌ Erreur : {str(e)}")
        return []

def get_lignes_lavage():
    """Récupère les lignes de lavage actives"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT code, libelle, capacite_th, temps_transition_minutes
            FROM lavages_lignes
            WHERE is_active = TRUE
            ORDER BY code
        """)
        
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        
        return rows if rows else []
        
    except Exception as e:
        st.error(f"❌ Erreur : {str(e)}")
        return []

def get_kpis_lavage():
    """Récupère les KPIs de lavage"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Jobs prévus
        cursor.execute("SELECT COUNT(*) as nb FROM lavages_jobs WHERE statut = 'PRÉVU'")
        nb_prevus = cursor.fetchone()['nb']
        
        # Jobs en cours
        cursor.execute("SELECT COUNT(*) as nb FROM lavages_jobs WHERE statut = 'EN_COURS'")
        nb_en_cours = cursor.fetchone()['nb']
        
        # Jobs terminés
        cursor.execute("SELECT COUNT(*) as nb FROM lavages_jobs WHERE statut = 'TERMINÉ'")
        nb_termines = cursor.fetchone()['nb']
        
        # Temps total prévu
        cursor.execute("SELECT COALESCE(SUM(temps_estime_heures), 0) as total FROM lavages_jobs WHERE statut IN ('PRÉVU', 'EN_COURS')")
        temps_total = cursor.fetchone()['total']
        
        cursor.close()
        conn.close()
        
        return {
            'nb_prevus': nb_prevus,
            'nb_en_cours': nb_en_cours,
            'nb_termines': nb_termines,
            'temps_total': float(temps_total)
        }
        
    except Exception as e:
        st.error(f"❌ Erreur KPIs : {str(e)}")
        return None

def get_jobs_by_date(date):
    """Récupère les jobs pour une date donnée"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        query = """
        SELECT 
            lj.id,
            lj.lot_id,
            lj.code_lot_interne,
            lj.variete,
            lj.quantite_pallox,
            lj.poids_brut_kg,
            lj.ligne_lavage,
            lj.temps_estime_heures,
            lj.statut,
            lj.created_by,
            lj.notes
        FROM lavages_jobs lj
        WHERE lj.date_prevue = %s
        ORDER BY lj.ligne_lavage, lj.created_at
        """
        
        cursor.execute(query, (date,))
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        
        if rows:
            df = pd.DataFrame(rows)
            # Convertir colonnes numériques
            numeric_cols = ['quantite_pallox', 'poids_brut_kg', 'temps_estime_heures']
            for col in numeric_cols:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
            return df
        return pd.DataFrame()
        
    except Exception as e:
        st.error(f"❌ Erreur : {str(e)}")
        return pd.DataFrame()

def get_jobs_by_statut(statut):
    """Récupère les jobs par statut"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        query = """
        SELECT 
            lj.id,
            lj.lot_id,
            lj.code_lot_interne,
            lj.variete,
            lj.quantite_pallox,
            lj.poids_brut_kg,
            lj.date_prevue,
            lj.ligne_lavage,
            lj.temps_estime_heures,
            lj.statut,
            lj.created_by,
            lj.created_at,
            lj.date_activation,
            lj.date_terminaison,
            lj.poids_lave_net_kg,
            lj.poids_grenailles_kg,
            lj.poids_dechets_kg,
            lj.poids_terre_calcule_kg,
            lj.tare_reelle_pct,
            lj.rendement_pct,
            lj.site_destination,
            lj.emplacement_destination
        FROM lavages_jobs lj
        WHERE lj.statut = %s
        ORDER BY lj.date_prevue DESC, lj.created_at DESC
        """
        
        cursor.execute(query, (statut,))
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        
        if rows:
            df = pd.DataFrame(rows)
            # Convertir colonnes numériques
            numeric_cols = ['quantite_pallox', 'poids_brut_kg', 'temps_estime_heures',
                          'poids_lave_net_kg', 'poids_grenailles_kg', 'poids_dechets_kg',
                          'poids_terre_calcule_kg', 'tare_reelle_pct', 'rendement_pct']
            for col in numeric_cols:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
            return df
        return pd.DataFrame()
        
    except Exception as e:
        st.error(f"❌ Erreur : {str(e)}")
        return pd.DataFrame()

def create_job_lavage(lot_id, emplacement_id, quantite_pallox, poids_brut_kg, 
                     date_prevue, ligne_lavage, capacite_th, notes=""):
    """Crée un nouveau job de lavage"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Convertir tous les types en types Python natifs
        lot_id = int(lot_id)
        emplacement_id = int(emplacement_id)
        quantite_pallox = int(quantite_pallox)
        poids_brut_kg = float(poids_brut_kg)
        capacite_th = float(capacite_th)
        
        # Récupérer infos lot
        cursor.execute("""
            SELECT l.code_lot_interne, COALESCE(v.nom_variete, l.code_variete) as variete
            FROM lots_bruts l
            LEFT JOIN ref_varietes v ON l.code_variete = v.code_variete
            WHERE l.id = %s
        """, (lot_id,))
        lot_info = cursor.fetchone()
        
        # Calculer temps estimé
        temps_estime = (poids_brut_kg / 1000) / capacite_th  # heures
        
        # Insérer job
        created_by = st.session_state.get('username', 'system')
        
        query = """
        INSERT INTO lavages_jobs (
            lot_id, code_lot_interne, variete, quantite_pallox, poids_brut_kg,
            date_prevue, ligne_lavage, capacite_th, temps_estime_heures,
            statut, created_by, notes
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'PRÉVU', %s, %s)
        RETURNING id
        """
        
        cursor.execute(query, (
            lot_id, lot_info['code_lot_interne'], lot_info['variete'],
            quantite_pallox, poids_brut_kg, date_prevue, ligne_lavage,
            capacite_th, temps_estime, created_by, notes
        ))
        
        job_id = cursor.fetchone()['id']
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return True, f"✅ Job #{job_id} créé avec succès"
        
    except Exception as e:
        if 'conn' in locals():
            conn.rollback()
        return False, f"❌ Erreur : {str(e)}"

def activer_job(job_id):
    """Active un job (PRÉVU → EN_COURS)"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        activated_by = st.session_state.get('username', 'system')
        
        cursor.execute("""
            UPDATE lavages_jobs
            SET statut = 'EN_COURS',
                date_activation = CURRENT_TIMESTAMP,
                activated_by = %s
            WHERE id = %s AND statut = 'PRÉVU'
        """, (activated_by, job_id))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return True, "✅ Job activé"
        
    except Exception as e:
        if 'conn' in locals():
            conn.rollback()
        return False, f"❌ Erreur : {str(e)}"

def terminer_job(job_id, poids_lave, poids_grenailles, poids_dechets,
                site_dest, emplacement_dest, notes=""):
    """Termine un job et crée les stocks résultants"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Récupérer job
        cursor.execute("""
            SELECT lot_id, quantite_pallox, poids_brut_kg,
                   code_lot_interne, ligne_lavage
            FROM lavages_jobs
            WHERE id = %s AND statut = 'EN_COURS'
        """, (job_id,))
        
        job = cursor.fetchone()
        if not job:
            return False, "❌ Job introuvable ou pas EN_COURS"
        
        # Calculs
        poids_brut = float(job['poids_brut_kg'])
        poids_terre = poids_brut - poids_lave - poids_grenailles - poids_dechets
        tare_reelle = ((poids_dechets + poids_terre) / poids_brut) * 100
        rendement = ((poids_lave + poids_grenailles) / poids_brut) * 100
        
        # Validation
        if abs(poids_brut - (poids_lave + poids_grenailles + poids_dechets + poids_terre)) > 1:
            return False, f"❌ Poids incohérents : Brut={poids_brut:.0f} vs Total={poids_lave+poids_grenailles+poids_dechets+poids_terre:.0f}"
        
        # Mettre à jour job
        terminated_by = st.session_state.get('username', 'system')
        
        cursor.execute("""
            UPDATE lavages_jobs
            SET statut = 'TERMINÉ',
                date_terminaison = CURRENT_TIMESTAMP,
                poids_lave_net_kg = %s,
                poids_grenailles_kg = %s,
                poids_dechets_kg = %s,
                poids_terre_calcule_kg = %s,
                tare_reelle_pct = %s,
                rendement_pct = %s,
                site_destination = %s,
                emplacement_destination = %s,
                terminated_by = %s,
                notes = %s
            WHERE id = %s
        """, (poids_lave, poids_grenailles, poids_dechets, poids_terre,
              tare_reelle, rendement, site_dest, emplacement_dest,
              terminated_by, notes, job_id))
        
        # === GESTION DES STOCKS ===
        
        # 1. Trouver stock BRUT source
        cursor.execute("""
            SELECT id, nombre_unites, site_stockage, emplacement_stockage, type_conditionnement
            FROM stock_emplacements
            WHERE lot_id = %s AND statut_lavage = 'BRUT' AND is_active = TRUE
            LIMIT 1
        """, (job['lot_id'],))
        
        stock_brut = cursor.fetchone()
        if not stock_brut:
            return False, "❌ Stock BRUT source introuvable"
        
        # 2. Déduire quantité du stock BRUT
        quantite_lavee = int(job['quantite_pallox'])
        nouvelle_quantite_brut = int(stock_brut['nombre_unites']) - quantite_lavee
        
        if nouvelle_quantite_brut < 0:
            return False, f"❌ Quantité insuffisante : {stock_brut['nombre_unites']} disponibles, {quantite_lavee} demandés"
        
        if nouvelle_quantite_brut == 0:
            # Désactiver l'emplacement vidé
            cursor.execute("""
                UPDATE stock_emplacements
                SET is_active = FALSE, updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
            """, (stock_brut['id'],))
        else:
            # Réduire quantité (recalcul poids selon type conditionnement)
            poids_unitaire = 1900 if stock_brut['type_conditionnement'] == 'Pallox' else 1200
            nouveau_poids_brut = nouvelle_quantite_brut * poids_unitaire
            
            cursor.execute("""
                UPDATE stock_emplacements
                SET nombre_unites = %s,
                    poids_total_kg = %s,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
            """, (nouvelle_quantite_brut, nouveau_poids_brut, stock_brut['id']))
        
        # 3. Créer stock LAVÉ (arrondi supérieur, toujours en pallox)
        pallox_lave = max(1, math.ceil(poids_lave / 1900))  # Minimum 1 pallox
        
        cursor.execute("""
            INSERT INTO stock_emplacements (
                lot_id, site_stockage, emplacement_stockage,
                nombre_unites, type_conditionnement, poids_total_kg,
                statut_lavage, lavage_job_id, is_active
            ) VALUES (%s, %s, %s, %s, %s, %s, 'LAVÉ', %s, TRUE)
        """, (job['lot_id'], site_dest, emplacement_dest, 
              pallox_lave, 'Pallox', float(poids_lave), int(job_id)))
        
        # 4. Créer stock GRENAILLES (si > 0, arrondi supérieur, toujours en pallox)
        if poids_grenailles > 0:
            pallox_grenailles = max(1, math.ceil(poids_grenailles / 1900))  # Minimum 1 pallox
            
            cursor.execute("""
                INSERT INTO stock_emplacements (
                    lot_id, site_stockage, emplacement_stockage,
                    nombre_unites, type_conditionnement, poids_total_kg,
                    statut_lavage, lavage_job_id, is_active
                ) VALUES (%s, %s, %s, %s, %s, %s, 'GRENAILLES', %s, TRUE)
            """, (job['lot_id'], site_dest, emplacement_dest + '_GREN',
                  pallox_grenailles, 'Pallox', float(poids_grenailles), int(job_id)))
        
        # 5. Créer mouvements traçabilité
        user = st.session_state.get('username', 'system')
        
        # Mouvement : Réduction stock BRUT
        cursor.execute("""
            INSERT INTO stock_mouvements (
                lot_id, type_mouvement, site_origine, emplacement_origine,
                quantite, type_conditionnement, poids_kg, user_action, created_by, notes
            ) VALUES (%s, 'LAVAGE_BRUT_REDUIT', %s, %s, %s, %s, %s, %s, %s, %s)
        """, (job['lot_id'], stock_brut['site_stockage'], stock_brut['emplacement_stockage'],
              -quantite_lavee, 'Pallox', -poids_brut, user, user, f"Job #{job_id} - Lavage {job['ligne_lavage']}"))
        
        # Mouvement : Création stock LAVÉ
        cursor.execute("""
            INSERT INTO stock_mouvements (
                lot_id, type_mouvement, site_destination, emplacement_destination,
                quantite, type_conditionnement, poids_kg, user_action, created_by, notes
            ) VALUES (%s, 'LAVAGE_CREATION_LAVE', %s, %s, %s, %s, %s, %s, %s, %s)
        """, (job['lot_id'], site_dest, emplacement_dest,
              quantite_lavee, 'Pallox', float(poids_lave), user, user, f"Job #{job_id} - Stock lavé"))
        
        # Mouvement : Création GRENAILLES (si > 0)
        if poids_grenailles > 0:
            cursor.execute("""
                INSERT INTO stock_mouvements (
                    lot_id, type_mouvement, site_destination, emplacement_destination,
                    quantite, type_conditionnement, poids_kg, user_action, created_by, notes
                ) VALUES (%s, 'LAVAGE_CREATION_GRENAILLES', %s, %s, %s, %s, %s, %s, %s, %s)
            """, (job['lot_id'], site_dest, emplacement_dest + '_GREN',
                  0, 'Vrac', float(poids_grenailles), user, user, f"Job #{job_id} - Grenailles"))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return True, f"✅ Job terminé - Rendement: {rendement:.1f}%"
        
    except Exception as e:
        if 'conn' in locals():
            conn.rollback()
        return False, f"❌ Erreur : {str(e)}"

def annuler_job_termine(job_id, raison):
    """
    Annule complètement un job terminé et rétablit le stock initial
    ADMIN ONLY
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # 1. Récupérer infos job
        cursor.execute("""
            SELECT lot_id, quantite_pallox, poids_brut_kg, 
                   site_destination, emplacement_destination
            FROM lavages_jobs
            WHERE id = %s AND statut = 'TERMINÉ'
        """, (job_id,))
        
        job = cursor.fetchone()
        if not job:
            return False, "❌ Job introuvable ou pas TERMINÉ"
        
        # 2. Supprimer stocks LAVÉ et GRENAILLES créés
        cursor.execute("""
            DELETE FROM stock_emplacements
            WHERE lavage_job_id = %s 
              AND statut_lavage IN ('LAVÉ', 'GRENAILLES')
        """, (job_id,))
        
        # 3. Restaurer stock BRUT
        cursor.execute("""
            SELECT id, nombre_unites, poids_total_kg, type_conditionnement
            FROM stock_emplacements
            WHERE lot_id = %s AND statut_lavage = 'BRUT' AND is_active = TRUE
            LIMIT 1
        """, (job['lot_id'],))
        
        stock_brut = cursor.fetchone()
        if stock_brut:
            # Calcul poids selon type
            poids_unitaire = 1900
            if stock_brut['type_conditionnement'] == 'Petit Pallox':
                poids_unitaire = 1200
            elif stock_brut['type_conditionnement'] == 'Big Bag':
                poids_unitaire = 1600
            
            nouvelle_quantite = int(stock_brut['nombre_unites']) + int(job['quantite_pallox'])
            nouveau_poids = nouvelle_quantite * poids_unitaire
            
            cursor.execute("""
                UPDATE stock_emplacements
                SET nombre_unites = %s,
                    poids_total_kg = %s,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
            """, (nouvelle_quantite, nouveau_poids, stock_brut['id']))
        
        # 4. Supprimer mouvements
        cursor.execute("""
            DELETE FROM stock_mouvements 
            WHERE lot_id = %s 
              AND (notes LIKE %s OR notes LIKE %s OR notes LIKE %s)
        """, (job['lot_id'], f"%Job #{job_id}%", f"%Job #{job_id}%", f"%Job #{job_id}%"))
        
        # 5. Marquer job ANNULÉ
        annule_par = st.session_state.get('username', 'system')
        
        cursor.execute("""
            UPDATE lavages_jobs
            SET statut = 'ANNULÉ',
                date_terminaison = NULL,
                poids_lave_net_kg = NULL,
                poids_grenailles_kg = NULL,
                poids_dechets_kg = NULL,
                poids_terre_calcule_kg = NULL,
                tare_reelle_pct = NULL,
                rendement_pct = NULL,
                terminated_by = NULL,
                notes = %s,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
        """, (f"[ANNULÉ par {annule_par}] Raison: {raison}", job_id))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return True, f"✅ Job #{job_id} annulé - Stock rétabli"
        
    except Exception as e:
        if 'conn' in locals():
            conn.rollback()
        return False, f"❌ Erreur : {str(e)}"

def supprimer_job(job_id):
    """
    Supprime un job PRÉVU ou EN_COURS (soft delete)
    ADMIN ONLY
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Vérifier statut
        cursor.execute("""
            SELECT statut FROM lavages_jobs WHERE id = %s
        """, (job_id,))
        
        result = cursor.fetchone()
        if not result:
            return False, "❌ Job introuvable"
        
        if result['statut'] not in ('PRÉVU', 'EN_COURS'):
            return False, f"❌ Impossible de supprimer un job {result['statut']}"
        
        # Soft delete
        supprime_par = st.session_state.get('username', 'system')
        
        cursor.execute("""
            UPDATE lavages_jobs
            SET statut = 'SUPPRIMÉ',
                notes = COALESCE(notes, '') || ' [SUPPRIMÉ par ' || %s || ']',
                updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
        """, (supprime_par, job_id))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return True, f"✅ Job #{job_id} supprimé"
        
    except Exception as e:
        if 'conn' in locals():
            conn.rollback()
        return False, f"❌ Erreur : {str(e)}"

# ==========================================
# AFFICHAGE - KPIs
# ==========================================

kpis = get_kpis_lavage()

if kpis:
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("🎯 Jobs Prévus", kpis['nb_prevus'])
    
    with col2:
        st.metric("⚙️ Jobs En Cours", kpis['nb_en_cours'])
    
    with col3:
        st.metric("✅ Jobs Terminés", kpis['nb_termines'])
    
    with col4:
        st.metric("⏱️ Temps Prévu/En Cours", f"{kpis['temps_total']:.1f}h")

st.markdown("---")

# ==========================================
# ONGLETS PRINCIPAUX
# ==========================================

tab1, tab2, tab3, tab4 = st.tabs(["📅 Calendrier", "📋 Liste Jobs", "➕ Créer Job", "⚙️ Admin"])

# ==========================================
# ONGLET 1 : CALENDRIER
# ==========================================

with tab1:
    st.subheader("📅 Planning Journalier")
    
    # Sélecteur de date
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col1:
        if st.button("◀ Jour précédent"):
            if 'selected_date' not in st.session_state:
                st.session_state.selected_date = datetime.now().date()
            st.session_state.selected_date -= timedelta(days=1)
            st.rerun()
    
    with col2:
        if 'selected_date' not in st.session_state:
            st.session_state.selected_date = datetime.now().date()
        
        selected_date = st.date_input(
            "Date",
            value=st.session_state.selected_date,
            key="date_picker"
        )
        st.session_state.selected_date = selected_date
    
    with col3:
        if st.button("Jour suivant ▶"):
            st.session_state.selected_date += timedelta(days=1)
            st.rerun()
    
    st.markdown("---")
    
    # Charger jobs du jour
    jobs_jour = get_jobs_by_date(st.session_state.selected_date)
    
    if not jobs_jour.empty:
        # Grouper par ligne
        lignes = jobs_jour['ligne_lavage'].unique()
        
        for ligne in sorted(lignes):
            st.markdown(f"### 🔧 {ligne}")
            
            jobs_ligne = jobs_jour[jobs_jour['ligne_lavage'] == ligne]
            
            for _, job in jobs_ligne.iterrows():
                statut_class = ""
                if job['statut'] == 'EN_COURS':
                    statut_class = "en-cours"
                elif job['statut'] == 'TERMINÉ':
                    statut_class = "termine"
                
                st.markdown(f"""
                <div class="job-card {statut_class}">
                    <strong>Job #{job['id']}</strong> - {job['code_lot_interne']}<br>
                    📦 {job['quantite_pallox']} pallox - ⚖️ {job['poids_brut_kg']/1000:.1f} T<br>
                    🌱 {job['variete']}<br>
                    ⏱️ {job['temps_estime_heures']:.1f}h - 🏷️ {job['statut']}
                </div>
                """, unsafe_allow_html=True)
            
            st.markdown("<br>", unsafe_allow_html=True)
    else:
        st.info(f"📅 Aucun job prévu le {st.session_state.selected_date.strftime('%d/%m/%Y')}")

# ==========================================
# ONGLET 2 : LISTE JOBS
# ==========================================

with tab2:
    st.subheader("📋 Liste des Jobs")
    
    subtab1, subtab2, subtab3 = st.tabs(["🎯 PRÉVU", "⚙️ EN_COURS", "✅ TERMINÉ"])
    
    with subtab1:
        jobs_prevus = get_jobs_by_statut('PRÉVU')
        
        if not jobs_prevus.empty:
            for _, job in jobs_prevus.iterrows():
                with st.expander(f"Job #{job['id']} - {job['code_lot_interne']} - {job['date_prevue']}"):
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.write(f"**Lot** : {job['code_lot_interne']}")
                        st.write(f"**Variété** : {job['variete']}")
                        st.write(f"**Quantité** : {job['quantite_pallox']} pallox")
                        st.write(f"**Poids** : {job['poids_brut_kg']/1000:.1f} T")
                    
                    with col2:
                        st.write(f"**Date prévue** : {job['date_prevue']}")
                        st.write(f"**Ligne** : {job['ligne_lavage']}")
                        st.write(f"**Temps estimé** : {job['temps_estime_heures']:.1f}h")
                        st.write(f"**Créé par** : {job['created_by']}")
                    
                    if st.button(f"⚙️ Activer Job #{job['id']}", key=f"activate_{job['id']}"):
                        success, message = activer_job(job['id'])
                        if success:
                            st.success(message)
                            st.rerun()
                        else:
                            st.error(message)
        else:
            st.info("Aucun job prévu")
    
    with subtab2:
        jobs_en_cours = get_jobs_by_statut('EN_COURS')
        
        if not jobs_en_cours.empty:
            for _, job in jobs_en_cours.iterrows():
                with st.expander(f"Job #{job['id']} - {job['code_lot_interne']} - EN COURS"):
                    st.write(f"**Activé le** : {job['date_activation']}")
                    st.write(f"**Poids brut** : {job['poids_brut_kg']:.0f} kg")
                    
                    if st.button(f"✅ Terminer Job #{job['id']}", key=f"finish_{job['id']}"):
                        st.session_state[f'show_finish_form_{job['id']}'] = True
                        st.rerun()
                    
                    # Formulaire terminaison
                    if st.session_state.get(f'show_finish_form_{job['id']}', False):
                        st.markdown("---")
                        st.markdown("##### Saisir les tares réelles")
                        
                        col1, col2 = st.columns(2)
                        
                        with col1:
                            poids_lave = st.number_input(
                                "Poids lavé net (kg) *",
                                min_value=0.0,
                                value=float(job['poids_brut_kg']) * 0.75,
                                step=100.0,
                                key=f"poids_lave_{job['id']}"
                            )
                            
                            poids_grenailles = st.number_input(
                                "Poids grenailles (kg) *",
                                min_value=0.0,
                                value=float(job['poids_brut_kg']) * 0.05,
                                step=10.0,
                                key=f"poids_grenailles_{job['id']}"
                            )
                        
                        with col2:
                            poids_dechets = st.number_input(
                                "Poids déchets (kg) *",
                                min_value=0.0,
                                value=float(job['poids_brut_kg']) * 0.05,
                                step=10.0,
                                key=f"poids_dechets_{job['id']}"
                            )
                            
                            poids_terre_calc = float(job['poids_brut_kg']) - poids_lave - poids_grenailles - poids_dechets
                            st.metric("Terre calculée", f"{poids_terre_calc:.0f} kg")
                        
                        st.markdown("---")
                        
                        emplacements = get_emplacements_saint_flavy()
                        site_dest = "SAINT_FLAVY"
                        emplacement_dest = st.selectbox(
                            "Emplacement destination *",
                            options=[""] + [e[0] for e in emplacements],
                            key=f"empl_{job['id']}"
                        )
                        
                        notes_fin = st.text_area("Notes", key=f"notes_{job['id']}")
                        
                        col_save, col_cancel = st.columns(2)
                        
                        with col_save:
                            if st.button("💾 Valider", key=f"save_finish_{job['id']}", type="primary"):
                                if not emplacement_dest:
                                    st.error("❌ Emplacement obligatoire")
                                else:
                                    success, message = terminer_job(
                                        job['id'], poids_lave, poids_grenailles, poids_dechets,
                                        site_dest, emplacement_dest, notes_fin
                                    )
                                    if success:
                                        st.success(message)
                                        st.session_state.pop(f'show_finish_form_{job["id"]}')
                                        st.rerun()
                                    else:
                                        st.error(message)
                        
                        with col_cancel:
                            if st.button("❌ Annuler", key=f"cancel_finish_{job['id']}"):
                                st.session_state.pop(f'show_finish_form_{job["id"]}')
                                st.rerun()
        else:
            st.info("Aucun job en cours")
    
    with subtab3:
        jobs_termines = get_jobs_by_statut('TERMINÉ')
        
        if not jobs_termines.empty:
            st.dataframe(
                jobs_termines[['id', 'code_lot_interne', 'variete', 'poids_brut_kg', 'date_prevue', 'date_terminaison']],
                use_container_width=True,
                hide_index=True
            )
        else:
            st.info("Aucun job terminé")

# ==========================================
# ONGLET 3 : CRÉER JOB
# ==========================================

with tab3:
    st.subheader("➕ Créer un Job de Lavage")
    st.markdown("*Sélectionnez un lot BRUT puis cliquez sur 'Créer Job'*")
    
    # Charger lots disponibles
    lots_dispo = get_lots_bruts_disponibles()
    
    if not lots_dispo.empty:
        # Filtres
        col1, col2 = st.columns(2)
        
        with col1:
            varietes_disponibles = ["Tous"] + sorted(lots_dispo['variete'].dropna().unique().tolist())
            filtre_variete = st.selectbox("Filtrer par variété", varietes_disponibles, key="filtre_var_create")
        
        with col2:
            sites_disponibles = ["Tous"] + sorted(lots_dispo['site_stockage'].dropna().unique().tolist())
            filtre_site = st.selectbox("Filtrer par site", sites_disponibles, key="filtre_site_create")
        
        # Appliquer filtres
        lots_filtres = lots_dispo.copy()
        if filtre_variete != "Tous":
            lots_filtres = lots_filtres[lots_filtres['variete'] == filtre_variete]
        if filtre_site != "Tous":
            lots_filtres = lots_filtres[lots_filtres['site_stockage'] == filtre_site]
        
        if not lots_filtres.empty:
            st.markdown("---")
            st.markdown(f"**{len(lots_filtres)} lot(s) disponible(s)** - 👇 Sélectionnez un lot dans le tableau")
            
            # Créer DataFrame pour affichage
            df_display = lots_filtres[[
                'lot_id', 'emplacement_id', 'code_lot_interne', 'nom_usage', 
                'variete', 'calibre_min', 'calibre_max',
                'site_stockage', 'emplacement_stockage', 'nombre_unites', 
                'poids_total_kg', 'type_conditionnement'
            ]].copy()
            
            # Garder index original
            df_display = df_display.reset_index(drop=False)
            df_display = df_display.rename(columns={'index': '_idx'})
            
            # Renommer pour affichage
            df_display = df_display.rename(columns={
                'code_lot_interne': 'Code Lot',
                'nom_usage': 'Nom Lot',
                'variete': 'Variété',
                'calibre_min': 'Cal Min',
                'calibre_max': 'Cal Max',
                'site_stockage': 'Site',
                'emplacement_stockage': 'Emplacement',
                'nombre_unites': 'Pallox',
                'poids_total_kg': 'Poids (kg)',
                'type_conditionnement': 'Type'
            })
            
            # Configuration colonnes
            column_config = {
                "_idx": None,  # Masquer
                "lot_id": None,  # Masquer
                "emplacement_id": None,  # Masquer
                "Code Lot": st.column_config.TextColumn("Code Lot", width="large"),
                "Nom Lot": st.column_config.TextColumn("Nom Lot", width="medium"),
                "Variété": st.column_config.TextColumn("Variété", width="medium"),
                "Cal Min": st.column_config.NumberColumn("Cal Min", format="%d"),
                "Cal Max": st.column_config.NumberColumn("Cal Max", format="%d"),
                "Site": st.column_config.TextColumn("Site", width="medium"),
                "Emplacement": st.column_config.TextColumn("Emplacement", width="medium"),
                "Pallox": st.column_config.NumberColumn("Pallox", format="%d"),
                "Poids (kg)": st.column_config.NumberColumn("Poids (kg)", format="%.0f"),
                "Type": st.column_config.TextColumn("Type", width="small")
            }
            
            # Tableau avec sélection
            event = st.dataframe(
                df_display,
                column_config=column_config,
                use_container_width=True,
                hide_index=True,
                on_select="rerun",
                selection_mode="single-row",
                key="lots_table_create"
            )
            
            # Récupérer sélection
            selected_rows = event.selection.rows if hasattr(event, 'selection') else []
            
            st.markdown("---")
            
            # Bouton créer job (actif seulement si sélection)
            if len(selected_rows) > 0:
                selected_idx = selected_rows[0]
                selected_row = df_display.iloc[selected_idx]
                
                st.success(f"✅ Lot sélectionné : **{selected_row['Code Lot']}** - {selected_row['Variété']} ({int(selected_row['Pallox'])} pallox)")
                
                if st.button("➕ Créer Job de Lavage", type="primary", use_container_width=True, key="btn_show_create_form"):
                    st.session_state['selected_lot_original_idx'] = selected_row['_idx']
                    st.session_state['show_create_form'] = True
                    st.rerun()
            else:
                st.info("👆 Veuillez sélectionner un lot dans le tableau ci-dessus")
                st.button("➕ Créer Job de Lavage", type="primary", use_container_width=True, disabled=True, key="btn_create_disabled")
            
            # Formulaire de création si lot sélectionné
            if st.session_state.get('show_create_form', False) and 'selected_lot_original_idx' in st.session_state:
                st.markdown("---")
                st.markdown("### 📋 Paramètres du Job de Lavage")
                
                original_idx = st.session_state['selected_lot_original_idx']
                lot_data = lots_dispo.loc[original_idx]
                
                # Infos lot
                st.info(f"**Lot** : {lot_data['code_lot_interne']} - {lot_data['variete']} - {lot_data['site_stockage']}/{lot_data['emplacement_stockage']}")
                
                col1, col2 = st.columns(2)
                
                with col1:
                    quantite = st.slider(
                        "Quantité à laver (pallox) *",
                        min_value=1,
                        max_value=int(lot_data['nombre_unites']),
                        value=min(5, int(lot_data['nombre_unites'])),
                        key="quantite_create"
                    )
                    
                    date_prevue = st.date_input(
                        "Date prévue *",
                        value=datetime.now().date(),
                        key="date_prevue_create"
                    )
                
                with col2:
                    lignes = get_lignes_lavage()
                    if lignes:
                        ligne_options = [f"{l['code']} - {l['libelle']} ({l['capacite_th']}T/h)" for l in lignes]
                        selected_ligne = st.selectbox("Ligne de lavage *", options=ligne_options, key="ligne_create")
                        
                        # Calculer poids et temps
                        if lot_data['type_conditionnement'] == 'Pallox':
                            poids_unitaire = 1900
                        elif lot_data['type_conditionnement'] == 'Petit Pallox':
                            poids_unitaire = 1200
                        elif lot_data['type_conditionnement'] == 'Big Bag':
                            poids_unitaire = 1600
                        else:
                            poids_unitaire = 1900
                        
                        poids_brut = quantite * poids_unitaire
                        
                        ligne_idx = ligne_options.index(selected_ligne)
                        capacite = float(lignes[ligne_idx]['capacite_th'])
                        temps_estime = (poids_brut / 1000) / capacite
                        
                        st.metric("Poids brut à laver", f"{poids_brut:,.0f} kg ({poids_brut/1000:.1f} T)")
                        st.metric("Temps estimé", f"{temps_estime:.1f} heures")
                    else:
                        st.error("❌ Aucune ligne de lavage disponible")
                        ligne_code = None
                        capacite = None
                
                notes = st.text_area("Notes (optionnel)", key="notes_create_form")
                
                col_save, col_cancel = st.columns(2)
                
                with col_save:
                    if st.button("✅ Créer le Job", type="primary", use_container_width=True, key="btn_create_job"):
                        if lignes:
                            ligne_code = lignes[ligne_idx]['code']
                            
                            success, message = create_job_lavage(
                                lot_data['lot_id'],
                                lot_data['emplacement_id'],
                                quantite,
                                poids_brut,
                                date_prevue,
                                ligne_code,
                                capacite,
                                notes
                            )
                            
                            if success:
                                st.success(message)
                                st.balloons()
                                st.session_state.pop('show_create_form', None)
                                st.session_state.pop('selected_lot_original_idx', None)
                                st.rerun()
                            else:
                                st.error(message)
                        else:
                            st.error("❌ Impossible de créer le job : aucune ligne de lavage")
                
                with col_cancel:
                    if st.button("❌ Annuler", use_container_width=True, key="btn_cancel_create"):
                        st.session_state.pop('show_create_form', None)
                        st.session_state.pop('selected_lot_original_idx', None)
                        st.rerun()
        else:
            st.warning(f"⚠️ Aucun lot disponible avec les filtres : {filtre_variete} / {filtre_site}")
    else:
        st.warning("⚠️ Aucun lot BRUT disponible pour lavage")

# ==========================================
# ONGLET 4 : ADMIN
# ==========================================

with tab4:
    st.subheader("⚙️ Administration des Jobs")
    
    # Vérifier permissions ADMIN
    if not is_admin():
        st.warning("⚠️ Accès réservé aux administrateurs")
        st.stop()
    
    st.markdown("*Fonctions de gestion avancées des jobs de lavage*")
    st.markdown("---")
    
    # Sous-onglets : Annuler | Supprimer
    subtab_annuler, subtab_supprimer = st.tabs(["🔄 Annuler Job Terminé", "🗑️ Supprimer Job"])
    
    # ===== ANNULER JOB TERMINÉ =====
    with subtab_annuler:
        st.markdown("### 🔄 Annuler un Job Terminé")
        st.warning("⚠️ **Attention** : Cette action rétablit le stock initial et supprime tous les stocks créés (LAVÉ/GRENAILLES)")
        
        # Charger jobs terminés
        jobs_termines = get_jobs_by_statut('TERMINÉ')
        
        if not jobs_termines.empty:
            # Tableau jobs terminés
            st.markdown("**Jobs terminés disponibles :**")
            
            display_jobs = jobs_termines[['id', 'code_lot_interne', 'variete', 'quantite_pallox', 
                                          'poids_brut_kg', 'date_terminaison', 'rendement_pct']].copy()
            
            # Formatter
            display_jobs['poids_brut_kg'] = display_jobs['poids_brut_kg'].apply(lambda x: f"{x/1000:.1f} T" if pd.notna(x) else "N/A")
            display_jobs['rendement_pct'] = display_jobs['rendement_pct'].apply(lambda x: f"{x:.1f}%" if pd.notna(x) else "N/A")
            display_jobs.columns = ['ID', 'Lot', 'Variété', 'Pallox', 'Poids', 'Date terminaison', 'Rendement']
            
            st.dataframe(display_jobs, use_container_width=True, hide_index=True)
            
            st.markdown("---")
            
            # Formulaire annulation
            col1, col2 = st.columns([2, 1])
            
            with col1:
                job_options = [f"Job #{row['id']} - {row['code_lot_interne']} ({int(row['quantite_pallox'])} pallox)" 
                              for _, row in jobs_termines.iterrows()]
                
                selected_job = st.selectbox(
                    "Sélectionner le job à annuler",
                    options=range(len(jobs_termines)),
                    format_func=lambda x: job_options[x],
                    key="select_job_annuler"
                )
                
                raison = st.text_area(
                    "Raison de l'annulation * (obligatoire)",
                    placeholder="Ex: Erreur de saisie tares, problème qualité...",
                    key="raison_annulation"
                )
            
            with col2:
                st.metric("Job sélectionné", f"#{jobs_termines.iloc[selected_job]['id']}")
                st.metric("Lot", jobs_termines.iloc[selected_job]['code_lot_interne'])
                st.metric("Pallox à rétablir", int(jobs_termines.iloc[selected_job]['quantite_pallox']))
            
            st.markdown("---")
            
            if st.button("⚠️ ANNULER LE JOB", type="secondary", use_container_width=True, key="btn_annuler_job"):
                if not raison or len(raison.strip()) < 10:
                    st.error("❌ Raison obligatoire (minimum 10 caractères)")
                else:
                    job_id = jobs_termines.iloc[selected_job]['id']
                    
                    with st.spinner("Annulation en cours..."):
                        success, message = annuler_job_termine(job_id, raison)
                    
                    if success:
                        st.success(message)
                        st.balloons()
                        time.sleep(2)
                        st.rerun()
                    else:
                        st.error(message)
        else:
            st.info("📭 Aucun job terminé disponible")
    
    # ===== SUPPRIMER JOB =====
    with subtab_supprimer:
        st.markdown("### 🗑️ Supprimer un Job")
        st.warning("⚠️ **Attention** : Cette action supprime définitivement le job (PRÉVU ou EN_COURS)")
        
        # Charger jobs actifs
        jobs_prevus = get_jobs_by_statut('PRÉVU')
        jobs_en_cours = get_jobs_by_statut('EN_COURS')
        
        jobs_actifs = pd.concat([jobs_prevus, jobs_en_cours], ignore_index=True) if not jobs_prevus.empty or not jobs_en_cours.empty else pd.DataFrame()
        
        if not jobs_actifs.empty:
            # Tableau jobs actifs
            st.markdown("**Jobs actifs disponibles :**")
            
            display_jobs = jobs_actifs[['id', 'statut', 'code_lot_interne', 'variete', 
                                        'quantite_pallox', 'date_prevue', 'ligne_lavage']].copy()
            
            display_jobs.columns = ['ID', 'Statut', 'Lot', 'Variété', 'Pallox', 'Date prévue', 'Ligne']
            
            st.dataframe(display_jobs, use_container_width=True, hide_index=True)
            
            st.markdown("---")
            
            # Formulaire suppression
            col1, col2 = st.columns([2, 1])
            
            with col1:
                job_options = [f"Job #{row['id']} - {row['statut']} - {row['code_lot_interne']} ({int(row['quantite_pallox'])} pallox)" 
                              for _, row in jobs_actifs.iterrows()]
                
                selected_job = st.selectbox(
                    "Sélectionner le job à supprimer",
                    options=range(len(jobs_actifs)),
                    format_func=lambda x: job_options[x],
                    key="select_job_supprimer"
                )
            
            with col2:
                st.metric("Job sélectionné", f"#{jobs_actifs.iloc[selected_job]['id']}")
                st.metric("Statut", jobs_actifs.iloc[selected_job]['statut'])
                st.metric("Lot", jobs_actifs.iloc[selected_job]['code_lot_interne'])
            
            st.markdown("---")
            
            if st.button("🗑️ SUPPRIMER LE JOB", type="secondary", use_container_width=True, key="btn_supprimer_job"):
                job_id = jobs_actifs.iloc[selected_job]['id']
                
                with st.spinner("Suppression en cours..."):
                    success, message = supprimer_job(job_id)
                
                if success:
                    st.success(message)
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error(message)
        else:
            st.info("📭 Aucun job actif (PRÉVU/EN_COURS) disponible")

show_footer()
