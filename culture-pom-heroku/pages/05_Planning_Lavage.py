import streamlit as st
import streamlit.components.v1 as stc
import pandas as pd
from datetime import datetime, timedelta, time
from database import get_connection
from components import show_footer
from auth import require_access
from auth.roles import is_admin
import io

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
    
    /* Cartes jobs */
    .job-card {
        background: linear-gradient(135deg, #e3f2fd 0%, #bbdefb 100%);
        border-left: 4px solid #1976d2;
        padding: 0.6rem;
        border-radius: 8px;
        margin: 0.4rem 0;
        font-size: 0.85rem;
    }
    .custom-card {
        background: linear-gradient(135deg, #f3e5f5 0%, #e1bee7 100%);
        border-left: 4px solid #7b1fa2;
        padding: 0.6rem;
        border-radius: 8px;
        margin: 0.4rem 0;
        font-size: 0.85rem;
    }
    
    /* En-tête jour */
    .day-header {
        background: #f5f5f5;
        padding: 0.5rem;
        border-radius: 8px 8px 0 0;
        text-align: center;
        font-weight: bold;
        border-bottom: 2px solid #1976d2;
    }
    .capacity-box {
        background: #fafafa;
        padding: 0.4rem;
        font-size: 0.75rem;
        border: 1px solid #e0e0e0;
        border-radius: 0 0 8px 8px;
        margin-bottom: 0.5rem;
    }
    
    /* Jobs planifiés */
    .planned-prevu {
        background: linear-gradient(135deg, #c8e6c9 0%, #a5d6a7 100%);
        border-left: 4px solid #388e3c;
        padding: 0.5rem;
        border-radius: 6px;
        margin: 0.3rem 0;
        font-size: 0.8rem;
    }
    .planned-encours {
        background: linear-gradient(135deg, #fff3e0 0%, #ffcc80 100%);
        border-left: 4px solid #f57c00;
        padding: 0.5rem;
        border-radius: 6px;
        margin: 0.3rem 0;
        font-size: 0.8rem;
        animation: pulse 2s infinite;
    }
    .planned-termine {
        background: linear-gradient(135deg, #f5f5f5 0%, #e0e0e0 100%);
        border-left: 4px solid #757575;
        padding: 0.5rem;
        border-radius: 6px;
        margin: 0.3rem 0;
        font-size: 0.8rem;
    }
    .planned-custom {
        background: linear-gradient(135deg, #e1bee7 0%, #ce93d8 100%);
        border-left: 4px solid #7b1fa2;
        padding: 0.5rem;
        border-radius: 6px;
        margin: 0.3rem 0;
        font-size: 0.8rem;
    }
    
    @keyframes pulse {
        0% { box-shadow: 0 0 0 0 rgba(255, 152, 0, 0.4); }
        70% { box-shadow: 0 0 0 10px rgba(255, 152, 0, 0); }
        100% { box-shadow: 0 0 0 0 rgba(255, 152, 0, 0); }
    }
</style>
""", unsafe_allow_html=True)

# ============================================================
# 🔒 RBAC
# ============================================================
require_access("PRODUCTION")

# ============================================================
# FONCTIONS UTILITAIRES
# ============================================================

def get_lignes_lavage():
    """Récupère les lignes de lavage actives"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT code, libelle, capacite_th FROM lavages_lignes WHERE is_active = TRUE ORDER BY code")
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        return rows if rows else []
    except Exception as e:
        st.error(f"❌ Erreur : {str(e)}")
        return []

def get_temps_customs():
    """Récupère les temps customs actifs"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, code, libelle, emoji, duree_minutes FROM lavages_temps_customs WHERE is_active = TRUE ORDER BY id")
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        return rows if rows else []
    except:
        return []

def get_kpis_lavage():
    """Récupère les KPIs de lavage"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) as nb FROM lavages_jobs WHERE statut = 'PRÉVU'")
        nb_prevus = cursor.fetchone()['nb']
        
        cursor.execute("SELECT COUNT(*) as nb FROM lavages_jobs WHERE statut = 'EN_COURS'")
        nb_en_cours = cursor.fetchone()['nb']
        
        cursor.execute("SELECT COUNT(*) as nb FROM lavages_jobs WHERE statut = 'TERMINÉ'")
        nb_termines = cursor.fetchone()['nb']
        
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

def get_planning_semaine(ligne_code, week_start):
    """Charge le planning d'une semaine pour une ligne"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        week_end = week_start + timedelta(days=6)
        annee, semaine, _ = week_start.isocalendar()
        
        query = """
        SELECT 
            pe.id, pe.type_element, pe.date_prevue, pe.ligne_lavage,
            pe.heure_debut, pe.heure_fin, pe.duree_minutes, pe.ordre_jour,
            pe.job_id, pe.temps_custom_id,
            j.code_lot_interne, j.variete, j.quantite_pallox, j.statut as job_statut,
            j.temps_estime_heures, j.date_activation, j.date_terminaison,
            tc.libelle as custom_libelle, tc.emoji as custom_emoji
        FROM lavages_planning_elements pe
        LEFT JOIN lavages_jobs j ON pe.job_id = j.id
        LEFT JOIN lavages_temps_customs tc ON pe.temps_custom_id = tc.id
        WHERE pe.date_prevue BETWEEN %s AND %s
          AND pe.ligne_lavage = %s
        ORDER BY pe.date_prevue, pe.ordre_jour, pe.heure_debut
        """
        
        cursor.execute(query, (week_start, week_end, ligne_code))
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        
        if rows:
            df = pd.DataFrame(rows)
            numeric_cols = ['quantite_pallox', 'temps_estime_heures', 'duree_minutes', 'ordre_jour']
            for col in numeric_cols:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
            return df
        return pd.DataFrame()
    except Exception as e:
        st.error(f"❌ Erreur : {str(e)}")
        return pd.DataFrame()

def get_jobs_a_placer(ligne_code):
    """Récupère les jobs PRÉVU pour une ligne"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, code_lot_interne, variete, quantite_pallox, poids_brut_kg,
                   temps_estime_heures, date_prevue
            FROM lavages_jobs
            WHERE statut = 'PRÉVU' AND ligne_lavage = %s
            ORDER BY date_prevue, id
        """, (ligne_code,))
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        
        if rows:
            df = pd.DataFrame(rows)
            numeric_cols = ['quantite_pallox', 'poids_brut_kg', 'temps_estime_heures']
            for col in numeric_cols:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
            return df
        return pd.DataFrame()
    except:
        return pd.DataFrame()

def ajouter_element_planning(type_element, job_id, temps_custom_id, date_prevue, ligne_lavage,
                             duree_minutes, annee, semaine, heure_debut_choisie, parent_job_id=None):
    """Ajoute un élément au planning"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT COALESCE(MAX(ordre_jour), 0) as max_ordre
            FROM lavages_planning_elements
            WHERE date_prevue = %s AND ligne_lavage = %s
        """, (date_prevue, ligne_lavage))
        result = cursor.fetchone()
        next_ordre = (result['max_ordre'] or 0) + 1
        
        heure_debut = heure_debut_choisie
        debut_minutes = heure_debut.hour * 60 + heure_debut.minute
        fin_minutes = debut_minutes + duree_minutes
        heure_fin = time(min(23, fin_minutes // 60), fin_minutes % 60)
        
        created_by = st.session_state.get('username', 'system')
        
        cursor.execute("""
            INSERT INTO lavages_planning_elements 
            (type_element, job_id, temps_custom_id, parent_job_id, annee, semaine, date_prevue,
             ligne_lavage, ordre_jour, heure_debut, heure_fin, duree_minutes, created_by)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (type_element, job_id, temps_custom_id, parent_job_id, annee, semaine, date_prevue,
              ligne_lavage, next_ordre, heure_debut, heure_fin, duree_minutes, created_by))
        
        conn.commit()
        cursor.close()
        conn.close()
        return True, f"✅ Placé ({heure_debut.strftime('%H:%M')} → {heure_fin.strftime('%H:%M')})"
    except Exception as e:
        if 'conn' in locals():
            conn.rollback()
        return False, f"❌ Erreur : {str(e)}"

def retirer_element_planning(element_id):
    """Retire un élément du planning + temps customs associés"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Supprimer les temps customs liés (parent_job_id)
        cursor.execute("DELETE FROM lavages_planning_elements WHERE parent_job_id = %s", (element_id,))
        
        # Supprimer l'élément principal
        cursor.execute("DELETE FROM lavages_planning_elements WHERE id = %s", (element_id,))
        
        conn.commit()
        cursor.close()
        conn.close()
        return True, "✅ Retiré"
    except Exception as e:
        if 'conn' in locals():
            conn.rollback()
        return False, f"❌ Erreur : {str(e)}"

def trouver_prochain_creneau_libre(planning_df, date_cible, ligne, heure_souhaitee, duree_min):
    """
    Trouve le prochain créneau disponible pour placer un élément.
    Si l'heure souhaitée est libre, la retourne.
    Sinon, trouve automatiquement le prochain créneau libre après les chevauchements.
    """
    if planning_df.empty:
        return heure_souhaitee, True, ""
    
    date_str = str(date_cible)
    mask = (planning_df['date_prevue'].astype(str) == date_str) & (planning_df['ligne_lavage'] == ligne)
    elements = planning_df[mask]
    
    if elements.empty:
        return heure_souhaitee, True, ""
    
    # Convertir heure souhaitée en minutes
    debut_souhaite = heure_souhaitee.hour * 60 + heure_souhaitee.minute
    
    # Collecter tous les créneaux occupés
    creneaux_occupes = []
    for _, elem in elements.iterrows():
        if pd.isna(elem['heure_debut']) or pd.isna(elem['heure_fin']):
            continue
        elem_debut = elem['heure_debut'].hour * 60 + elem['heure_debut'].minute
        elem_fin = elem['heure_fin'].hour * 60 + elem['heure_fin'].minute
        
        # Récupérer le libellé pour affichage
        if pd.notna(elem.get('custom_libelle')):
            libelle = f"🔧 {elem['custom_libelle']}"
        elif pd.notna(elem.get('variete')):
            libelle = f"🌱 {elem['variete']}"
        else:
            libelle = "élément"
        
        creneaux_occupes.append({
            'debut': elem_debut,
            'fin': elem_fin,
            'libelle': libelle,
            'heure_debut_str': elem['heure_debut'].strftime('%H:%M'),
            'heure_fin_str': elem['heure_fin'].strftime('%H:%M')
        })
    
    # Trier par heure de début
    creneaux_occupes.sort(key=lambda x: x['debut'])
    
    # Vérifier si l'heure souhaitée est libre
    fin_souhaitee = debut_souhaite + duree_min
    conflit = False
    dernier_fin = debut_souhaite
    
    for creneau in creneaux_occupes:
        # Chevauchement ?
        if not (fin_souhaitee <= creneau['debut'] or debut_souhaite >= creneau['fin']):
            conflit = True
            dernier_fin = max(dernier_fin, creneau['fin'])
    
    # Si pas de conflit, retourner l'heure souhaitée
    if not conflit:
        return heure_souhaitee, True, ""
    
    # Sinon, trouver le prochain créneau libre après tous les conflits
    # Chercher à partir de la fin du dernier élément en conflit
    prochain_debut = dernier_fin
    
    # Vérifier que ce nouveau créneau ne chevauche pas d'autres éléments
    prochain_fin = prochain_debut + duree_min
    for creneau in creneaux_occupes:
        if creneau['debut'] < prochain_fin and creneau['fin'] > prochain_debut:
            # Conflit avec un autre élément, décaler encore
            prochain_debut = creneau['fin']
            prochain_fin = prochain_debut + duree_min
    
    # Convertir minutes en time
    heure_proposee = time(prochain_debut // 60, prochain_debut % 60)
    
    # Message informatif
    message = f"ℹ️ Repositionné à {heure_proposee.strftime('%H:%M')} (créneau {heure_souhaitee.strftime('%H:%M')} occupé)"
    
    return heure_proposee, True, message

def recalculer_heures_fin_job(job_planning_id):
    """Recalcule heure_fin du job en incluant les temps customs intercalés"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Récupérer le job parent
        cursor.execute("""
            SELECT date_prevue, ligne_lavage, heure_debut, duree_minutes, job_id
            FROM lavages_planning_elements
            WHERE id = %s
        """, (job_planning_id,))
        job_elem = cursor.fetchone()
        
        if not job_elem:
            return
        
        # Récupérer les temps customs de ce job (parent_job_id)
        cursor.execute("""
            SELECT duree_minutes
            FROM lavages_planning_elements
            WHERE parent_job_id = %s
            ORDER BY ordre_jour
        """, (job_planning_id,))
        customs = cursor.fetchall()
        
        # Calculer durée totale
        duree_job = int(job_elem['duree_minutes'])
        duree_customs = sum([int(c['duree_minutes']) for c in customs])
        duree_totale = duree_job + duree_customs
        
        # Recalculer heure_fin
        h_debut = job_elem['heure_debut']
        debut_min = h_debut.hour * 60 + h_debut.minute
        fin_min = debut_min + duree_totale
        heure_fin = time(min(23, fin_min // 60), fin_min % 60)
        
        # Mettre à jour
        cursor.execute("""
            UPDATE lavages_planning_elements
            SET heure_fin = %s, duree_minutes = %s
            WHERE id = %s
        """, (heure_fin, duree_totale, job_planning_id))
        
        conn.commit()
        cursor.close()
        conn.close()
    except Exception as e:
        if 'conn' in locals():
            conn.rollback()
        st.error(f"❌ Erreur recalcul : {str(e)}")

def demarrer_job(job_id):
    """Démarre un job (PRÉVU → EN_COURS)"""
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
        return True, "▶️ Job démarré !"
    except Exception as e:
        if 'conn' in locals():
            conn.rollback()
        return False, f"❌ Erreur : {str(e)}"

# ============================================================
# ✅ PHASE 1 : FONCTIONS ADMIN
# ============================================================

def supprimer_job(job_id):
    """Supprime un job PRÉVU (DELETE complet)"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Vérifier que le job est PRÉVU
        cursor.execute("SELECT statut FROM lavages_jobs WHERE id = %s", (job_id,))
        result = cursor.fetchone()
        if not result:
            return False, "❌ Job introuvable"
        if result['statut'] != 'PRÉVU':
            return False, f"❌ Impossible de supprimer un job {result['statut']}"
        
        # Supprimer du planning si présent
        cursor.execute("DELETE FROM lavages_planning_elements WHERE job_id = %s", (job_id,))
        
        # Supprimer le job
        cursor.execute("DELETE FROM lavages_jobs WHERE id = %s", (job_id,))
        
        conn.commit()
        cursor.close()
        conn.close()
        return True, "✅ Job supprimé"
    except Exception as e:
        if 'conn' in locals():
            conn.rollback()
        return False, f"❌ Erreur : {str(e)}"

def annuler_job_en_cours(job_id):
    """Annule un job EN_COURS : remet en PRÉVU"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Vérifier que le job est EN_COURS
        cursor.execute("SELECT statut FROM lavages_jobs WHERE id = %s", (job_id,))
        result = cursor.fetchone()
        if not result:
            return False, "❌ Job introuvable"
        if result['statut'] != 'EN_COURS':
            return False, f"❌ Ce job est {result['statut']}, pas EN_COURS"
        
        # Remettre en PRÉVU
        cursor.execute("""
            UPDATE lavages_jobs
            SET statut = 'PRÉVU',
                date_activation = NULL,
                activated_by = NULL
            WHERE id = %s
        """, (job_id,))
        
        conn.commit()
        cursor.close()
        conn.close()
        return True, "✅ Job remis en PRÉVU"
    except Exception as e:
        if 'conn' in locals():
            conn.rollback()
        return False, f"❌ Erreur : {str(e)}"

def annuler_job_termine(job_id):
    """Annule un job TERMINÉ : remet en PRÉVU, restaure le stock source, supprime stocks créés
    
    Gère les deux cas :
    - Source BRUT → supprime LAVÉ + GRENAILLES_BRUTES
    - Source GRENAILLES_BRUTES → supprime GRENAILLES_LAVÉES
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Vérifier que le job est TERMINÉ + récupérer emplacement_id et statut_source
        cursor.execute("""
            SELECT statut, lot_id, quantite_pallox, poids_brut_kg, emplacement_id, statut_source
            FROM lavages_jobs WHERE id = %s
        """, (job_id,))
        result = cursor.fetchone()
        if not result:
            return False, "❌ Job introuvable"
        if result['statut'] != 'TERMINÉ':
            return False, f"❌ Ce job est {result['statut']}, pas TERMINÉ"
        
        lot_id = result['lot_id']
        quantite_pallox = int(result['quantite_pallox'])
        poids_brut = float(result['poids_brut_kg'])
        emplacement_id = result['emplacement_id']
        statut_source = result['statut_source'] or 'BRUT'
        
        # ============================================================
        # 1. SUPPRIMER LES STOCKS CRÉÉS PAR CE JOB
        # ============================================================
        cursor.execute("""
            DELETE FROM stock_emplacements 
            WHERE lavage_job_id = %s AND statut_lavage IN ('LAVÉ', 'GRENAILLES', 'GRENAILLES_BRUTES', 'GRENAILLES_LAVÉES')
        """, (job_id,))
        
        # ============================================================
        # 2. RESTAURER LE STOCK SOURCE
        # ============================================================
        if emplacement_id:
            cursor.execute("""
                SELECT id, nombre_unites, poids_total_kg, is_active, statut_lavage
                FROM stock_emplacements
                WHERE id = %s
            """, (emplacement_id,))
        else:
            # Fallback : chercher le stock source du lot
            cursor.execute("""
                SELECT id, nombre_unites, poids_total_kg, is_active, statut_lavage
                FROM stock_emplacements
                WHERE lot_id = %s AND (statut_lavage = %s OR statut_lavage IS NULL)
                ORDER BY id
                LIMIT 1
            """, (lot_id, statut_source))
        
        stock_source = cursor.fetchone()
        
        if stock_source:
            # Restaurer les quantités
            nouveau_nb = int(stock_source['nombre_unites']) + quantite_pallox
            nouveau_poids = float(stock_source['poids_total_kg']) + poids_brut
            cursor.execute("""
                UPDATE stock_emplacements
                SET nombre_unites = %s, poids_total_kg = %s, is_active = TRUE
                WHERE id = %s
            """, (nouveau_nb, nouveau_poids, stock_source['id']))
        
        # ============================================================
        # 3. SUPPRIMER LES MOUVEMENTS DE STOCK LIÉS
        # ============================================================
        cursor.execute("""
            DELETE FROM stock_mouvements 
            WHERE notes LIKE %s
        """, (f"Job #{job_id}%",))
        
        # ============================================================
        # 4. REMETTRE LE JOB EN PRÉVU
        # ============================================================
        cursor.execute("""
            UPDATE lavages_jobs
            SET statut = 'PRÉVU',
                date_activation = NULL,
                date_terminaison = NULL,
                activated_by = NULL,
                terminated_by = NULL,
                poids_lave_net_kg = NULL,
                poids_grenailles_kg = NULL,
                poids_dechets_kg = NULL,
                poids_terre_calcule_kg = NULL,
                tare_reelle_pct = NULL,
                rendement_pct = NULL,
                site_destination = NULL,
                emplacement_destination = NULL
            WHERE id = %s
        """, (job_id,))
        
        conn.commit()
        cursor.close()
        conn.close()
        return True, f"✅ Job annulé - Stock {statut_source} restauré (+{quantite_pallox} pallox)"
    except Exception as e:
        if 'conn' in locals():
            conn.rollback()
        return False, f"❌ Erreur : {str(e)}"

def creer_temps_custom(code, libelle, emoji, duree_minutes):
    """Crée un nouveau temps custom"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        created_by = st.session_state.get('username', 'system')
        cursor.execute("""
            INSERT INTO lavages_temps_customs (code, libelle, emoji, duree_minutes, created_by)
            VALUES (%s, %s, %s, %s, %s)
        """, (code, libelle, emoji, duree_minutes, created_by))
        conn.commit()
        cursor.close()
        conn.close()
        return True, "✅ Créé"
    except Exception as e:
        if 'conn' in locals():
            conn.rollback()
        return False, f"❌ Erreur : {str(e)}"

def supprimer_temps_custom(temps_id):
    """Supprime (désactive) un temps custom"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE lavages_temps_customs SET is_active = FALSE WHERE id = %s", (temps_id,))
        conn.commit()
        cursor.close()
        conn.close()
        return True, "✅ Supprimé"
    except Exception as e:
        if 'conn' in locals():
            conn.rollback()
        return False, f"❌ Erreur : {str(e)}"

# ============================================================
# INITIALISATION SESSION STATE
# ============================================================

def get_monday_of_week(date_obj):
    return date_obj - timedelta(days=date_obj.weekday())

if 'current_week_start' not in st.session_state:
    st.session_state.current_week_start = get_monday_of_week(datetime.now().date())
if 'selected_ligne' not in st.session_state:
    st.session_state.selected_ligne = 'LIGNE_1'

# ============================================================
# HEADER + KPIs
# ============================================================

st.title("🧼 Planning Lavage V8 - Phase 1")
st.caption("*Gestion jobs lavage - Architecture pause intercalée + Admin*")

kpis = get_kpis_lavage()
if kpis:
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("🎯 Jobs Prévus", kpis['nb_prevus'])
    col2.metric("⚙️ Jobs En Cours", kpis['nb_en_cours'])
    col3.metric("✅ Jobs Terminés", kpis['nb_termines'])
    col4.metric("⏱️ Temps Prévu/En Cours", f"{kpis['temps_total']:.1f}h")

st.markdown("---")

# ============================================================
# ONGLETS PRINCIPAUX
# ============================================================

tab1, tab2, tab3, tab4 = st.tabs(["📅 Planning Semaine", "📋 Jobs à Placer", "⚙️ Admin", "ℹ️ Phase 1"])

# ============================================================
# ONGLET 1 : PLANNING SEMAINE
# ============================================================

with tab1:
    # Contrôles
    col_ligne, col_prev, col_semaine, col_next = st.columns([2, 0.5, 2, 0.5])
    
    lignes = get_lignes_lavage()
    with col_ligne:
        if lignes:
            ligne_options = [f"{l['code']} ({l['capacite_th']} T/h)" for l in lignes]
            selected_idx = next((i for i, l in enumerate(lignes) if l['code'] == st.session_state.selected_ligne), 0)
            selected = st.selectbox("Ligne", ligne_options, index=selected_idx, label_visibility="collapsed", key="ligne_select")
            st.session_state.selected_ligne = lignes[ligne_options.index(selected)]['code']
    
    with col_prev:
        if st.button("◀️", use_container_width=True):
            st.session_state.current_week_start -= timedelta(days=7)
            st.rerun()
    
    with col_semaine:
        week_start = st.session_state.current_week_start
        week_end = week_start + timedelta(days=4)
        st.markdown(f"<div style='text-align:center;font-weight:bold;'>Semaine du {week_start.strftime('%d/%m')} au {week_end.strftime('%d/%m')}</div>", unsafe_allow_html=True)
    
    with col_next:
        if st.button("▶️", use_container_width=True):
            st.session_state.current_week_start += timedelta(days=7)
            st.rerun()
    
    st.markdown("---")
    
    # Charger planning
    annee, semaine, _ = week_start.isocalendar()
    planning_df = get_planning_semaine(st.session_state.selected_ligne, week_start)
    jobs_a_placer = get_jobs_a_placer(st.session_state.selected_ligne)
    temps_customs = get_temps_customs()
    
    # Layout
    col_left, col_right = st.columns([1, 4])
    
    # GAUCHE : Jobs à placer + Temps customs
    with col_left:
        st.markdown("### 📦 Jobs à placer")
        
        jobs_planifies_ids = planning_df[planning_df['type_element'] == 'JOB']['job_id'].dropna().astype(int).tolist() if not planning_df.empty else []
        jobs_non_planifies = jobs_a_placer[~jobs_a_placer['id'].isin(jobs_planifies_ids)] if not jobs_a_placer.empty else pd.DataFrame()
        
        if jobs_non_planifies.empty:
            st.info("✅ Tous les jobs planifiés")
        else:
            for _, job in jobs_non_planifies.iterrows():
                st.markdown(f"""<div class="job-card"><strong>Job #{int(job['id'])}</strong><br>
                🌱 {job['variete']}<br>📦 {int(job['quantite_pallox'])}p - ⏱️ {job['temps_estime_heures']:.1f}h</div>""", unsafe_allow_html=True)
                
                jours_options = ["Sélectionner..."] + [f"{['Lun','Mar','Mer','Jeu','Ven'][i]} {(week_start + timedelta(days=i)).strftime('%d/%m')}" for i in range(5)]
                jour_choisi = st.selectbox("Jour", jours_options, key=f"jour_job_{job['id']}", label_visibility="collapsed")
                
                if jour_choisi != "Sélectionner...":
                    jour_idx = jours_options.index(jour_choisi) - 1
                    date_cible = week_start + timedelta(days=jour_idx)
                    heure_saisie = st.time_input("Heure", value=time(4, 0), step=900, key=f"heure_job_{job['id']}", label_visibility="collapsed")
                    duree_min = int(job['temps_estime_heures'] * 60)
                    
                    # Trouver le prochain créneau libre (auto-repositionnement)
                    heure_optimale, ok, msg_info = trouver_prochain_creneau_libre(planning_df, date_cible, st.session_state.selected_ligne, heure_saisie, duree_min)
                    
                    if msg_info:
                        st.info(msg_info)
                    
                    if st.button("✅ Placer", key=f"confirm_job_{job['id']}", type="primary", use_container_width=True):
                        success, msg = ajouter_element_planning('JOB', int(job['id']), None, date_cible, st.session_state.selected_ligne, duree_min, annee, semaine, heure_optimale)
                        if success:
                            st.success(msg)
                            st.rerun()
                        else:
                            st.error(msg)
                st.markdown("<hr style='margin:0.3rem 0;border:none;border-top:1px solid #eee;'>", unsafe_allow_html=True)
        
        st.markdown("---")
        st.markdown("### 🔧 Temps customs")
        
        for tc in temps_customs:
            col_tc, col_del = st.columns([5, 1])
            with col_tc:
                st.markdown(f"""<div class="custom-card">{tc['emoji']} {tc['libelle']} ({tc['duree_minutes']}min)</div>""", unsafe_allow_html=True)
            with col_del:
                if is_admin() and st.button("🗑️", key=f"del_tc_{tc['id']}"):
                    supprimer_temps_custom(tc['id'])
                    st.rerun()
            
            jours_tc = ["Sélectionner..."] + [f"{['Lun','Mar','Mer','Jeu','Ven'][i]} {(week_start + timedelta(days=i)).strftime('%d/%m')}" for i in range(5)]
            jour_tc = st.selectbox("Jour", jours_tc, key=f"jour_tc_{tc['id']}", label_visibility="collapsed")
            if jour_tc != "Sélectionner...":
                jour_idx = jours_tc.index(jour_tc) - 1
                date_cible = week_start + timedelta(days=jour_idx)
                heure_saisie_tc = st.time_input("Heure", value=time(4, 0), step=900, key=f"heure_tc_{tc['id']}", label_visibility="collapsed")
                
                # Trouver le prochain créneau libre (auto-repositionnement)
                heure_optimale_tc, ok, msg_info_tc = trouver_prochain_creneau_libre(planning_df, date_cible, st.session_state.selected_ligne, heure_saisie_tc, tc['duree_minutes'])
                
                if msg_info_tc:
                    st.info(msg_info_tc)
                
                if st.button("✅", key=f"confirm_tc_{tc['id']}", use_container_width=True):
                    success, msg = ajouter_element_planning('CUSTOM', None, int(tc['id']), date_cible, st.session_state.selected_ligne, tc['duree_minutes'], annee, semaine, heure_optimale_tc)
                    if success:
                        st.rerun()
    
    # DROITE : Calendrier
    with col_right:
        jour_cols = st.columns(5)
        jours_noms = ['Lun', 'Mar', 'Mer', 'Jeu', 'Ven']
        
        for i, col_jour in enumerate(jour_cols):
            jour_date = week_start + timedelta(days=i)
            jour_str = str(jour_date)
            
            with col_jour:
                st.markdown(f"""<div class="day-header">{jours_noms[i]} {jour_date.strftime('%d/%m')}</div>""", unsafe_allow_html=True)
                
                # Éléments planifiés
                if not planning_df.empty:
                    mask = (planning_df['date_prevue'].astype(str) == jour_str) & (planning_df['ligne_lavage'] == st.session_state.selected_ligne)
                    elements = planning_df[mask].sort_values('heure_debut')
                    
                    if elements.empty:
                        st.caption("_Vide_")
                    else:
                        for _, elem in elements.iterrows():
                            h_deb = elem['heure_debut'].strftime('%H:%M') if pd.notna(elem['heure_debut']) else '--:--'
                            h_fin = elem['heure_fin'].strftime('%H:%M') if pd.notna(elem['heure_fin']) else '--:--'
                            
                            if elem['type_element'] == 'JOB':
                                job_statut = elem.get('job_statut', 'PRÉVU')
                                css_class = "planned-prevu" if job_statut == 'PRÉVU' else "planned-encours" if job_statut == 'EN_COURS' else "planned-termine"
                                statut_emoji = "🟢" if job_statut == 'PRÉVU' else "⏱️" if job_statut == 'EN_COURS' else "✅"
                                
                                st.markdown(f"""<div class="{css_class}">
                                    <strong>{h_deb}</strong> {statut_emoji}<br>
                                    Job #{int(elem['job_id'])}<br>
                                    🌱 {elem['variete']}<br>
                                    📦 {int(elem['quantite_pallox']) if pd.notna(elem['quantite_pallox']) else '?'}p<br>
                                    <small>→{h_fin}</small>
                                </div>""", unsafe_allow_html=True)
                                
                                if job_statut == 'PRÉVU':
                                    col_start, col_del = st.columns(2)
                                    with col_start:
                                        if st.button("▶️", key=f"start_{elem['id']}", help="Démarrer"):
                                            success, msg = demarrer_job(int(elem['job_id']))
                                            if success:
                                                st.success(msg)
                                                st.rerun()
                                            else:
                                                st.error(msg)
                                    with col_del:
                                        if st.button("❌", key=f"del_{elem['id']}", help="Retirer"):
                                            retirer_element_planning(int(elem['id']))
                                            st.rerun()
                            else:
                                # Temps custom
                                st.markdown(f"""<div class="planned-custom">
                                    <strong>{h_deb}</strong><br>
                                    {elem['custom_emoji']} {elem['custom_libelle']}<br>
                                    <small>→{h_fin}</small>
                                </div>""", unsafe_allow_html=True)
                                
                                if st.button("❌", key=f"del_custom_{elem['id']}", help="Retirer"):
                                    retirer_element_planning(int(elem['id']))
                                    st.rerun()
                else:
                    st.caption("_Vide_")

# ============================================================
# ONGLET 2 : JOBS À PLACER
# ============================================================

with tab2:
    st.subheader("📋 Liste des Jobs PRÉVU")
    st.caption("Tous les jobs en attente de placement")
    
    jobs_prevus = get_jobs_a_placer(st.session_state.selected_ligne)
    
    if not jobs_prevus.empty:
        for _, job in jobs_prevus.iterrows():
            with st.expander(f"Job #{int(job['id'])} - {job['code_lot_interne']} - {job['variete']}"):
                col1, col2 = st.columns(2)
                
                with col1:
                    st.write(f"**Lot** : {job['code_lot_interne']}")
                    st.write(f"**Variété** : {job['variete']}")
                    st.write(f"**Quantité** : {int(job['quantite_pallox'])} pallox")
                
                with col2:
                    st.write(f"**Poids** : {job['poids_brut_kg']:.0f} kg")
                    st.write(f"**Temps estimé** : {job['temps_estime_heures']:.1f}h")
                    st.write(f"**Date prévue** : {job['date_prevue']}")
    else:
        st.info("Aucun job PRÉVU")

# ============================================================
# ONGLET 3 : ADMIN ✅ PHASE 1
# ============================================================

with tab3:
    if not is_admin():
        st.warning("⚠️ Accès réservé aux administrateurs")
    else:
        st.subheader("⚙️ Administration")
        
        admin_tab1, admin_tab2, admin_tab3 = st.tabs(["🗑️ Gestion Jobs", "🔧 Temps Customs", "📊 Statistiques"])
        
        # --- GESTION JOBS ---
        with admin_tab1:
            st.markdown("### 🗑️ Gestion des Jobs")
            
            col_prevus, col_encours, col_termines = st.columns(3)
            
            # PRÉVU
            with col_prevus:
                st.markdown("#### 🟢 PRÉVU")
                st.caption("Supprimer définitivement")
                try:
                    conn = get_connection()
                    cursor = conn.cursor()
                    cursor.execute("""
                        SELECT id, code_lot_interne, variete, quantite_pallox, date_prevue
                        FROM lavages_jobs
                        WHERE statut = 'PRÉVU'
                        ORDER BY date_prevue DESC
                        LIMIT 15
                    """)
                    jobs_prevus_admin = cursor.fetchall()
                    cursor.close()
                    conn.close()
                    
                    if jobs_prevus_admin:
                        for job in jobs_prevus_admin:
                            col_info, col_btn = st.columns([4, 1])
                            with col_info:
                                st.markdown(f"**#{job['id']}** {job['variete']} {int(job['quantite_pallox'])}p")
                            with col_btn:
                                if st.button("🗑️", key=f"del_job_{job['id']}", help="Supprimer"):
                                    success, msg = supprimer_job(job['id'])
                                    if success:
                                        st.success(msg)
                                        st.rerun()
                                    else:
                                        st.error(msg)
                    else:
                        st.info("Aucun")
                except Exception as e:
                    st.error(f"Erreur : {str(e)}")
            
            # EN_COURS
            with col_encours:
                st.markdown("#### 🟠 EN_COURS")
                st.caption("Remettre en PRÉVU")
                try:
                    conn = get_connection()
                    cursor = conn.cursor()
                    cursor.execute("""
                        SELECT id, code_lot_interne, variete, quantite_pallox, date_activation
                        FROM lavages_jobs
                        WHERE statut = 'EN_COURS'
                        ORDER BY date_activation DESC
                        LIMIT 15
                    """)
                    jobs_encours_admin = cursor.fetchall()
                    cursor.close()
                    conn.close()
                    
                    if jobs_encours_admin:
                        for job in jobs_encours_admin:
                            col_info, col_btn = st.columns([4, 1])
                            with col_info:
                                st.markdown(f"**#{job['id']}** {job['variete']} {int(job['quantite_pallox'])}p")
                            with col_btn:
                                if st.button("↩️", key=f"cancel_encours_{job['id']}", help="Annuler"):
                                    success, msg = annuler_job_en_cours(job['id'])
                                    if success:
                                        st.success(msg)
                                        st.rerun()
                                    else:
                                        st.error(msg)
                    else:
                        st.info("Aucun")
                except Exception as e:
                    st.error(f"Erreur : {str(e)}")
            
            # TERMINÉ
            with col_termines:
                st.markdown("#### ⬜ TERMINÉ")
                st.caption("✅ Restaure le stock BRUT")
                try:
                    conn = get_connection()
                    cursor = conn.cursor()
                    cursor.execute("""
                        SELECT id, code_lot_interne, variete, quantite_pallox, 
                               date_terminaison, rendement_pct
                        FROM lavages_jobs
                        WHERE statut = 'TERMINÉ'
                        ORDER BY date_terminaison DESC
                        LIMIT 20
                    """)
                    jobs_termines_admin = cursor.fetchall()
                    cursor.close()
                    conn.close()
                    
                    if jobs_termines_admin:
                        for job in jobs_termines_admin:
                            col_info, col_btn = st.columns([4, 1])
                            with col_info:
                                rend = f"{job['rendement_pct']:.1f}%" if job['rendement_pct'] else "N/A"
                                st.markdown(f"**#{job['id']}** {job['code_lot_interne']} - Rend: {rend}")
                            with col_btn:
                                if st.button("↩️", key=f"cancel_job_{job['id']}", help="Annuler"):
                                    success, msg = annuler_job_termine(job['id'])
                                    if success:
                                        st.success(msg)
                                        st.rerun()
                                    else:
                                        st.error(msg)
                    else:
                        st.info("Aucun job TERMINÉ")
                except Exception as e:
                    st.error(f"Erreur : {str(e)}")
        
        # --- TEMPS CUSTOMS ---
        with admin_tab2:
            st.markdown("### 🔧 Temps Customs")
            temps_customs_all = get_temps_customs()
            for tc in temps_customs_all:
                col_info, col_del = st.columns([5, 1])
                with col_info:
                    st.markdown(f"- {tc['emoji']} **{tc['libelle']}** ({tc['duree_minutes']} min)")
                with col_del:
                    if st.button("🗑️", key=f"del_tc_admin_{tc['id']}"):
                        supprimer_temps_custom(tc['id'])
                        st.rerun()
            
            st.markdown("---")
            st.markdown("#### ➕ Créer un temps custom")
            col1, col2, col3 = st.columns(3)
            with col1:
                new_lib = st.text_input("Libellé", key="new_tc_lib_admin")
            with col2:
                new_dur = st.number_input("Durée (min)", 5, 480, 20, key="new_tc_dur_admin")
            with col3:
                new_emo = st.selectbox("Emoji", ["⚙️", "☕", "🔧", "🍽️", "⏸️", "🧹", "🔄"], key="new_tc_emo_admin")
            if st.button("✅ Créer", key="btn_create_tc_admin") and new_lib:
                creer_temps_custom(new_lib.upper().replace(" ", "_")[:20], new_lib, new_emo, new_dur)
                st.success("✅ Créé")
                st.rerun()
        
        # --- STATISTIQUES ---
        with admin_tab3:
            st.markdown("### 📊 Statistiques Lavage")
            try:
                conn = get_connection()
                cursor = conn.cursor()
                
                # Stats globales
                cursor.execute("""
                    SELECT 
                        COUNT(*) as nb_jobs,
                        AVG(rendement_pct) as rend_moy,
                        AVG(tare_reelle_pct) as tare_moy,
                        SUM(poids_brut_kg) as tonnage_total
                    FROM lavages_jobs 
                    WHERE statut = 'TERMINÉ' AND rendement_pct IS NOT NULL
                """)
                stats = cursor.fetchone()
                
                if stats and stats['nb_jobs'] > 0:
                    col1, col2, col3, col4 = st.columns(4)
                    col1.metric("Jobs terminés", stats['nb_jobs'])
                    col2.metric("Rendement moyen", f"{stats['rend_moy']:.1f}%")
                    col3.metric("Tare moyenne", f"{stats['tare_moy']:.1f}%")
                    col4.metric("Tonnage lavé", f"{stats['tonnage_total']/1000:.1f} T")
                    
                    st.markdown("---")
                    st.markdown("#### Par variété")
                    cursor.execute("""
                        SELECT 
                            variete,
                            COUNT(*) as nb_jobs,
                            AVG(rendement_pct) as rend_moy,
                            AVG(tare_reelle_pct) as tare_moy
                        FROM lavages_jobs 
                        WHERE statut = 'TERMINÉ' AND rendement_pct IS NOT NULL
                        GROUP BY variete
                        ORDER BY nb_jobs DESC
                    """)
                    stats_var = cursor.fetchall()
                    if stats_var:
                        df_stats = pd.DataFrame(stats_var)
                        df_stats.columns = ['Variété', 'Nb Jobs', 'Rendement %', 'Tare %']
                        st.dataframe(df_stats, use_container_width=True, hide_index=True)
                else:
                    st.info("Pas encore de statistiques")
                
                cursor.close()
                conn.close()
            except Exception as e:
                st.error(f"Erreur : {str(e)}")

# ============================================================
# ONGLET 4 : INFO PHASE 1
# ============================================================

with tab4:
    st.subheader("ℹ️ Phase 1 - Admin & Validation Stock")
    
    st.markdown("""
    ### ✅ Nouveautés Phase 1
    
    **1. Onglet Admin complet** ⚙️
    - **Gestion Jobs** :
      - Supprimer job PRÉVU (DELETE complet)
      - Annuler job EN_COURS → PRÉVU
      - Annuler job TERMINÉ → Restaure stock BRUT
    - **Temps Customs** : CRUD complet
    - **Statistiques** : Stats globales + par variété
    
    **2. Architecture pause intercalée** ⏸️
    - Temps customs avec `parent_job_id`
    - Recalcul automatique heure_fin du job
    - Pause intercalée rallonge job principal
    
    ### 📋 Prochaines Phases
    
    **Phase 2** : Statut source + Producteur
    - Gestion BRUT vs GRENAILLES_BRUTES
    - Affichage producteur dans cards
    - Dénormalisation producteur
    
    **Phase 3** : Créer Job + Liste complète
    - Onglet dédié "Créer Job"
    - Section besoins affectations
    - Liste tous statuts (PRÉVU/EN_COURS/TERMINÉ)
    
    **Phase 4** : Stats + Imprimer
    - Onglet Stats & Recap
    - Onglet Imprimer (PDF)
    - Arrondi quart d'heure
    """)

show_footer()
