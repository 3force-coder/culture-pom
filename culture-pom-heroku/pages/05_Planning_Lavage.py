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

def get_lots_bruts_disponibles():
    """Récupère les lots BRUT disponibles pour lavage"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT 
                se.id as emplacement_id,
                l.id as lot_id,
                l.code_lot_interne,
                l.nom_usage,
                COALESCE(v.nom_variete, l.code_variete) as variete,
                l.calibre_min,
                l.calibre_max,
                se.site_stockage,
                se.emplacement_stockage,
                se.nombre_unites,
                se.type_conditionnement,
                se.poids_total_kg,
                COALESCE(p.nom, l.code_producteur) as producteur
            FROM stock_emplacements se
            JOIN lots_bruts l ON se.lot_id = l.id
            LEFT JOIN ref_varietes v ON l.code_variete = v.code_variete
            LEFT JOIN ref_producteurs p ON l.code_producteur = p.code_producteur
            WHERE se.is_active = TRUE 
              AND se.statut_lavage = 'BRUT'
              AND se.nombre_unites > 0
            ORDER BY l.code_lot_interne
        """)
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        
        if rows:
            df = pd.DataFrame(rows)
            numeric_cols = ['nombre_unites', 'poids_total_kg', 'calibre_min', 'calibre_max']
            for col in numeric_cols:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
            return df
        return pd.DataFrame()
    except Exception as e:
        st.error(f"❌ Erreur : {str(e)}")
        return pd.DataFrame()

def get_lots_grenailles_disponibles():
    """Récupère les lots GRENAILLES_BRUTES disponibles pour lavage"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT 
                se.id as emplacement_id,
                l.id as lot_id,
                l.code_lot_interne,
                l.nom_usage,
                COALESCE(v.nom_variete, l.code_variete) as variete,
                l.calibre_min,
                l.calibre_max,
                se.site_stockage,
                se.emplacement_stockage,
                se.nombre_unites,
                se.type_conditionnement,
                se.poids_total_kg,
                COALESCE(p.nom, l.code_producteur) as producteur
            FROM stock_emplacements se
            JOIN lots_bruts l ON se.lot_id = l.id
            LEFT JOIN ref_varietes v ON l.code_variete = v.code_variete
            LEFT JOIN ref_producteurs p ON l.code_producteur = p.code_producteur
            WHERE se.is_active = TRUE 
              AND se.statut_lavage = 'GRENAILLES'
              AND se.nombre_unites > 0
            ORDER BY l.code_lot_interne
        """)
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        
        if rows:
            df = pd.DataFrame(rows)
            numeric_cols = ['nombre_unites', 'poids_total_kg', 'calibre_min', 'calibre_max']
            for col in numeric_cols:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
            return df
        return pd.DataFrame()
    except Exception as e:
        st.error(f"❌ Erreur : {str(e)}")
        return pd.DataFrame()

def create_job_lavage(lot_id, emplacement_id, ligne_lavage, quantite_pallox, poids_brut_kg,
                      date_prevue, capacite_th, statut_source, producteur="", notes=""):
    """Crée un nouveau job de lavage (BRUT ou GRENAILLES_BRUTES)"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Convertir types
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
        temps_estime = (poids_brut_kg / 1000) / capacite_th
        
        # Insérer job
        created_by = st.session_state.get('username', 'system')
        
        cursor.execute("""
            INSERT INTO lavages_jobs (
                lot_id, code_lot_interne, variete, quantite_pallox, poids_brut_kg,
                date_prevue, ligne_lavage, capacite_th, temps_estime_heures,
                statut, statut_source, producteur, created_by, notes
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'PRÉVU', %s, %s, %s, %s)
            RETURNING id
        """, (
            lot_id, lot_info['code_lot_interne'], lot_info['variete'],
            quantite_pallox, poids_brut_kg, date_prevue, ligne_lavage,
            capacite_th, temps_estime, statut_source, producteur, created_by, notes
        ))
        
        job_id = cursor.fetchone()['id']
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return True, f"✅ Job #{job_id} créé ({statut_source})"
    except Exception as e:
        if 'conn' in locals():
            conn.rollback()
        return False, f"❌ Erreur : {str(e)}"

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
            pe.job_id, pe.temps_custom_id, pe.producteur as pe_producteur,
            j.code_lot_interne, j.variete, j.quantite_pallox, j.statut as job_statut,
            j.temps_estime_heures, j.date_activation, j.date_terminaison, j.producteur,
            j.statut_source,
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
                   temps_estime_heures, date_prevue, producteur, statut_source
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
    """Ajoute un élément au planning avec dénormalisation producteur"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Récupérer producteur si c'est un JOB (dénormalisation pour performance)
        producteur = None
        if type_element == 'JOB' and job_id:
            cursor.execute("SELECT producteur FROM lavages_jobs WHERE id = %s", (job_id,))
            result = cursor.fetchone()
            if result:
                producteur = result.get('producteur')
        
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
            (type_element, job_id, temps_custom_id, parent_job_id, producteur, annee, semaine, date_prevue,
             ligne_lavage, ordre_jour, heure_debut, heure_fin, duree_minutes, created_by)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (type_element, job_id, temps_custom_id, parent_job_id, producteur, annee, semaine, date_prevue,
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

def terminer_job(job_id, poids_lave, poids_grenailles, poids_dechets,
                site_dest, emplacement_dest, notes=""):
    """Termine un job EN_COURS → TERMINÉ
    
    Gère automatiquement selon statut_source :
    - BRUT : crée stock LAVÉ + GRENAILLES_BRUTES
    - GRENAILLES_BRUTES : crée stock GRENAILLES_LAVÉES
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Récupérer infos job
        cursor.execute("""
            SELECT lot_id, quantite_pallox, poids_brut_kg, code_lot_interne,
                   emplacement_id, statut, statut_source, variete, producteur
            FROM lavages_jobs
            WHERE id = %s
        """, (job_id,))
        
        job = cursor.fetchone()
        if not job:
            return False, "❌ Job introuvable"
        if job['statut'] != 'EN_COURS':
            return False, f"❌ Ce job est {job['statut']}, pas EN_COURS"
        
        # Convertir types
        poids_lave = float(poids_lave)
        poids_grenailles = float(poids_grenailles)
        poids_dechets = float(poids_dechets)
        poids_brut = float(job['poids_brut_kg'])
        quantite_pallox = int(job['quantite_pallox'])
        lot_id = int(job['lot_id'])
        emplacement_id = job['emplacement_id']
        statut_source = job['statut_source'] or 'BRUT'
        
        # Calculs
        poids_terre = poids_brut - poids_lave - poids_grenailles - poids_dechets
        tare_reelle = ((poids_dechets + poids_terre) / poids_brut) * 100 if poids_brut > 0 else 0
        rendement = ((poids_lave + poids_grenailles) / poids_brut) * 100 if poids_brut > 0 else 0
        
        # Validation cohérence
        if abs(poids_terre) > 100:
            return False, f"❌ Incohérent : Terre = {poids_terre:.0f} kg (vérifier saisie)"
        
        # Mettre à jour le job
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
        
        # ============================================================
        # WORKFLOW DIFFÉRENCIÉ SELON STATUT_SOURCE
        # ============================================================
        
        if statut_source == 'BRUT':
            # ========== CAS 1 : SOURCE BRUT → LAVÉ + GRENAILLES_BRUTES ==========
            
            # Créer stock LAVÉ
            if poids_lave > 0:
                nb_unites_lave = int(poids_lave / 1900)  # Estimation pallox lavés
                cursor.execute("""
                    INSERT INTO stock_emplacements (
                        lot_id, site_stockage, emplacement_stockage,
                        nombre_unites, type_conditionnement, poids_total_kg,
                        statut_lavage, lavage_job_id, is_active
                    ) VALUES (%s, %s, %s, %s, 'Pallox', %s, 'LAVÉ', %s, TRUE)
                """, (lot_id, site_dest, emplacement_dest, nb_unites_lave, poids_lave, job_id))
                
                # Mouvement LAVÉ
                cursor.execute("""
                    INSERT INTO stock_mouvements (
                        lot_id, type_mouvement, site_destination, emplacement_destination,
                        quantite, type_conditionnement, poids_kg, user_action, notes
                    ) VALUES (%s, 'LAVAGE_CREE_LAVE', %s, %s, %s, 'Pallox', %s, %s, %s)
                """, (lot_id, site_dest, emplacement_dest, nb_unites_lave, poids_lave,
                      terminated_by, f"Job #{job_id} - BRUT → LAVÉ"))
            
            # Créer stock GRENAILLES_BRUTES (pas GRENAILLES)
            if poids_grenailles > 0:
                nb_unites_gren = int(poids_grenailles / 1200)  # Estimation petit pallox grenailles
                cursor.execute("""
                    INSERT INTO stock_emplacements (
                        lot_id, site_stockage, emplacement_stockage,
                        nombre_unites, type_conditionnement, poids_total_kg,
                        statut_lavage, lavage_job_id, is_active
                    ) VALUES (%s, %s, %s, %s, 'Petit Pallox', %s, 'GRENAILLES', %s, TRUE)
                """, (lot_id, site_dest, emplacement_dest, nb_unites_gren, poids_grenailles, job_id))
                
                # Mouvement GRENAILLES
                cursor.execute("""
                    INSERT INTO stock_mouvements (
                        lot_id, type_mouvement, site_destination, emplacement_destination,
                        quantite, type_conditionnement, poids_kg, user_action, notes
                    ) VALUES (%s, 'LAVAGE_CREE_GRENAILLES', %s, %s, %s, 'Petit Pallox', %s, %s, %s)
                """, (lot_id, site_dest, emplacement_dest, nb_unites_gren, poids_grenailles,
                      terminated_by, f"Job #{job_id} - BRUT → GRENAILLES"))
        
        else:
            # ========== CAS 2 : SOURCE GRENAILLES_BRUTES → GRENAILLES_LAVÉES ==========
            
            # Créer stock GRENAILLES_LAVÉES (statut spécifique)
            if poids_lave > 0:
                nb_unites_gren_lavees = int(poids_lave / 1200)
                cursor.execute("""
                    INSERT INTO stock_emplacements (
                        lot_id, site_stockage, emplacement_stockage,
                        nombre_unites, type_conditionnement, poids_total_kg,
                        statut_lavage, lavage_job_id, is_active
                    ) VALUES (%s, %s, %s, %s, 'Petit Pallox', %s, 'GRENAILLES_LAVÉES', %s, TRUE)
                """, (lot_id, site_dest, emplacement_dest, nb_unites_gren_lavees, poids_lave, job_id))
                
                # Mouvement GRENAILLES_LAVÉES
                cursor.execute("""
                    INSERT INTO stock_mouvements (
                        lot_id, type_mouvement, site_destination, emplacement_destination,
                        quantite, type_conditionnement, poids_kg, user_action, notes
                    ) VALUES (%s, 'LAVAGE_GRENAILLES_CREE_LAVEES', %s, %s, %s, 'Petit Pallox', %s, %s, %s)
                """, (lot_id, site_dest, emplacement_dest, nb_unites_gren_lavees, poids_lave,
                      terminated_by, f"Job #{job_id} - GRENAILLES → LAVÉES"))
            
            # Note : Pas de grenailles secondaires (déchets uniquement)
        
        # ============================================================
        # DÉDUIRE DU STOCK SOURCE (commun aux 2 cas)
        # ============================================================
        
        if emplacement_id:
            # Déduire quantité du stock source
            cursor.execute("""
                UPDATE stock_emplacements
                SET nombre_unites = nombre_unites - %s,
                    poids_total_kg = poids_total_kg - %s
                WHERE id = %s
            """, (quantite_pallox, poids_brut, emplacement_id))
            
            # Vérifier si stock épuisé
            cursor.execute("SELECT nombre_unites FROM stock_emplacements WHERE id = %s", (emplacement_id,))
            result = cursor.fetchone()
            if result and result['nombre_unites'] <= 0:
                cursor.execute("UPDATE stock_emplacements SET is_active = FALSE WHERE id = %s", (emplacement_id,))
            
            # Mouvement déduction
            cursor.execute("""
                INSERT INTO stock_mouvements (
                    lot_id, type_mouvement, quantite, type_conditionnement, poids_kg,
                    user_action, notes
                ) VALUES (%s, 'LAVAGE_DEDUIT_SOURCE', %s, 'Pallox', %s, %s, %s)
            """, (lot_id, quantite_pallox, poids_brut, terminated_by,
                  f"Job #{job_id} - Déduit stock {statut_source}"))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        type_resultat = "LAVÉ + GRENAILLES" if statut_source == 'BRUT' else "GRENAILLES_LAVÉES"
        return True, f"✅ Job terminé - {type_resultat} créés (Rdt: {rendement:.1f}%)"
        
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

st.title("🧼 Planning Lavage V8 - Phase 5")
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

tab1, tab2, tab3, tab4, tab5 = st.tabs(["📅 Planning Semaine", "📋 Jobs à Placer", "⚙️ Admin", "➕ Créer Job", "ℹ️ Info"])

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
                producteur_info = f" - 👤 {job['producteur']}" if pd.notna(job.get('producteur')) and job['producteur'] else ""
                statut_source = job.get('statut_source', 'BRUT')
                badge_source = "🔄" if statut_source == 'GRENAILLES_BRUTES' else "🥔"
                st.markdown(f"""<div class="job-card"><strong>Job #{int(job['id'])} {badge_source}</strong><br>
                🌱 {job['variete']}{producteur_info}<br>📦 {int(job['quantite_pallox'])}p - ⏱️ {job['temps_estime_heures']:.1f}h</div>""", unsafe_allow_html=True)
                
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
                                
                                # Déterminer producteur (pe_producteur en priorité, sinon j.producteur)
                                producteur = elem.get('pe_producteur') or elem.get('producteur') or ''
                                producteur_ligne = f"<br>👤 {producteur}" if producteur else ""
                                
                                # Badge statut_source
                                statut_source = elem.get('statut_source', 'BRUT')
                                badge_source = " 🔄" if statut_source == 'GRENAILLES_BRUTES' else " 🥔"
                                
                                st.markdown(f"""<div class="{css_class}">
                                    <strong>{h_deb}</strong> {statut_emoji}<br>
                                    Job #{int(elem['job_id'])}{badge_source}<br>
                                    🌱 {elem['variete']}{producteur_ligne}<br>
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
                                
                                elif job_statut == 'EN_COURS':
                                    # ✅ PHASE 5 : Bouton Terminer
                                    if st.button("✅ Terminer", key=f"finish_{elem['id']}", help="Terminer le job", use_container_width=True):
                                        st.session_state[f'show_finish_form_{elem["id"]}'] = True
                                        st.rerun()
                                    
                                    # Formulaire terminaison
                                    if st.session_state.get(f'show_finish_form_{elem["id"]}', False):
                                        st.markdown("---")
                                        st.markdown("**📋 Saisir les tares**")
                                        
                                        job_id = int(elem['job_id'])
                                        poids_brut = float(elem['poids_brut_kg']) if pd.notna(elem['poids_brut_kg']) else 0
                                        source_type = elem.get('statut_source', 'BRUT')
                                        
                                        if source_type == 'BRUT':
                                            st.caption("🥔 Source BRUT → Stock LAVÉ + GRENAILLES_BRUTES")
                                        else:
                                            st.caption("🔄 Source GRENAILLES → Stock GRENAILLES_LAVÉES")
                                        
                                        col1, col2 = st.columns(2)
                                        
                                        with col1:
                                            poids_lave = st.number_input(
                                                "Poids lavé (kg) *",
                                                min_value=0.0,
                                                value=poids_brut * 0.75,
                                                step=10.0,
                                                key=f"lave_{elem['id']}"
                                            )
                                            
                                            poids_grenailles = st.number_input(
                                                "Poids grenailles (kg) *",
                                                min_value=0.0,
                                                value=poids_brut * 0.05 if source_type == 'BRUT' else 0.0,
                                                step=10.0,
                                                key=f"gren_{elem['id']}",
                                                disabled=(source_type != 'BRUT')
                                            )
                                        
                                        with col2:
                                            poids_dechets = st.number_input(
                                                "Poids déchets (kg) *",
                                                min_value=0.0,
                                                value=poids_brut * 0.05,
                                                step=10.0,
                                                key=f"dech_{elem['id']}"
                                            )
                                            
                                            poids_terre_calc = poids_brut - poids_lave - poids_grenailles - poids_dechets
                                            st.metric("Terre calculée", f"{poids_terre_calc:.0f} kg")
                                        
                                        st.markdown("---")
                                        
                                        emplacements = [
                                            ("A-01", "Saint Flavy - Zone A-01"),
                                            ("A-02", "Saint Flavy - Zone A-02"),
                                            ("B-01", "Saint Flavy - Zone B-01")
                                        ]
                                        emplacement_dest = st.selectbox(
                                            "Emplacement destination *",
                                            options=[""] + [e[0] for e in emplacements],
                                            format_func=lambda x: dict(emplacements).get(x, "Sélectionner...") if x else "Sélectionner...",
                                            key=f"empl_{elem['id']}"
                                        )
                                        
                                        notes_fin = st.text_area("Notes", key=f"notes_{elem['id']}")
                                        
                                        col_save, col_cancel = st.columns(2)
                                        
                                        with col_save:
                                            if st.button("💾 Valider", key=f"save_{elem['id']}", type="primary"):
                                                if not emplacement_dest:
                                                    st.error("❌ Emplacement obligatoire")
                                                else:
                                                    success, message = terminer_job(
                                                        job_id, poids_lave, poids_grenailles, poids_dechets,
                                                        "SAINT_FLAVY", emplacement_dest, notes_fin
                                                    )
                                                    if success:
                                                        st.success(message)
                                                        st.balloons()
                                                        st.session_state.pop(f'show_finish_form_{elem["id"]}')
                                                        st.rerun()
                                                    else:
                                                        st.error(message)
                                        
                                        with col_cancel:
                                            if st.button("❌ Annuler", key=f"cancel_{elem['id']}"):
                                                st.session_state.pop(f'show_finish_form_{elem["id"]}')
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
            statut_source = job.get('statut_source', 'BRUT')
            badge_source = "🔄 GRENAILLES" if statut_source == 'GRENAILLES_BRUTES' else "🥔 BRUT"
            with st.expander(f"Job #{int(job['id'])} - {job['code_lot_interne']} - {job['variete']} ({badge_source})"):
                col1, col2 = st.columns(2)
                
                with col1:
                    st.write(f"**Lot** : {job['code_lot_interne']}")
                    st.write(f"**Variété** : {job['variete']}")
                    st.write(f"**Quantité** : {int(job['quantite_pallox'])} pallox")
                    if pd.notna(job.get('producteur')) and job['producteur']:
                        st.write(f"**Producteur** : 👤 {job['producteur']}")
                
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
# ONGLET 4 : CRÉER JOB ✅ PHASE 4
# ============================================================

with tab4:
    st.subheader("➕ Créer un Job de Lavage")
    
    # Choix type source
    col1, col2 = st.columns(2)
    
    with col1:
        type_source = st.radio(
            "Type de source",
            options=["BRUT 🥔", "GRENAILLES 🔄"],
            horizontal=True,
            key="type_source_create"
        )
    
    statut_source = "BRUT" if "BRUT" in type_source else "GRENAILLES_BRUTES"
    
    st.markdown("---")
    
    # Charger lots selon type
    if statut_source == "BRUT":
        lots_dispo = get_lots_bruts_disponibles()
        st.info("📦 Sélection de **pommes de terre brutes** (BRUT) pour lavage primaire")
    else:
        lots_dispo = get_lots_grenailles_disponibles()
        st.info("🔄 Sélection de **grenailles brutes** (GRENAILLES_BRUTES) pour lavage secondaire")
    
    if not lots_dispo.empty:
        # Filtres
        col_f1, col_f2 = st.columns(2)
        
        with col_f1:
            varietes = ["Tous"] + sorted(lots_dispo['variete'].dropna().unique().tolist())
            filtre_var = st.selectbox("Filtrer par variété", varietes, key="fvar_create")
        
        with col_f2:
            sites = ["Tous"] + sorted(lots_dispo['site_stockage'].dropna().unique().tolist())
            filtre_site = st.selectbox("Filtrer par site", sites, key="fsite_create")
        
        # Appliquer filtres
        lots_filtres = lots_dispo.copy()
        if filtre_var != "Tous":
            lots_filtres = lots_filtres[lots_filtres['variete'] == filtre_var]
        if filtre_site != "Tous":
            lots_filtres = lots_filtres[lots_filtres['site_stockage'] == filtre_site]
        
        if not lots_filtres.empty:
            st.markdown(f"**{len(lots_filtres)} emplacement(s) disponible(s)**")
            
            # Tableau sélection
            df_display = lots_filtres[[
                'emplacement_id', 'lot_id', 'code_lot_interne', 'nom_usage',
                'variete', 'calibre_min', 'calibre_max', 'producteur',
                'site_stockage', 'emplacement_stockage',
                'nombre_unites', 'poids_total_kg', 'type_conditionnement'
            ]].copy()
            
            df_display = df_display.reset_index(drop=False).rename(columns={'index': '_idx'})
            
            df_display = df_display.rename(columns={
                'code_lot_interne': 'Code Lot',
                'nom_usage': 'Nom Lot',
                'variete': 'Variété',
                'calibre_min': 'Cal Min',
                'calibre_max': 'Cal Max',
                'producteur': 'Producteur',
                'site_stockage': 'Site',
                'emplacement_stockage': 'Empl',
                'nombre_unites': 'Unités',
                'poids_total_kg': 'Poids (kg)',
                'type_conditionnement': 'Type'
            })
            
            column_config = {
                "_idx": None,
                "emplacement_id": None,
                "lot_id": None,
                "Code Lot": st.column_config.TextColumn("Code Lot", width="medium"),
                "Nom Lot": st.column_config.TextColumn("Nom Lot", width="medium"),
                "Variété": st.column_config.TextColumn("Variété", width="medium"),
                "Cal Min": st.column_config.NumberColumn("Cal Min", format="%d"),
                "Cal Max": st.column_config.NumberColumn("Cal Max", format="%d"),
                "Producteur": st.column_config.TextColumn("Producteur", width="medium"),
                "Site": st.column_config.TextColumn("Site", width="small"),
                "Empl": st.column_config.TextColumn("Empl", width="small"),
                "Unités": st.column_config.NumberColumn("Unités", format="%d"),
                "Poids (kg)": st.column_config.NumberColumn("Poids (kg)", format="%.0f"),
                "Type": st.column_config.TextColumn("Type", width="small")
            }
            
            event = st.dataframe(
                df_display,
                column_config=column_config,
                use_container_width=True,
                hide_index=True,
                on_select="rerun",
                selection_mode="single-row",
                key="lots_create_table"
            )
            
            selected_rows = event.selection.rows if hasattr(event, 'selection') else []
            
            st.markdown("---")
            
            if len(selected_rows) > 0:
                selected_idx = selected_rows[0]
                selected_row = df_display.iloc[selected_idx]
                
                badge = "🥔" if statut_source == "BRUT" else "🔄"
                st.success(f"✅ Sélectionné : **{selected_row['Code Lot']}** - {selected_row['Variété']} ({int(selected_row['Unités'])} unités) {badge}")
                
                if st.button("➕ Créer Job de Lavage", type="primary", use_container_width=True, key="btn_show_form_create"):
                    st.session_state['selected_empl_idx_create'] = selected_row['_idx']
                    st.session_state['show_create_form_job'] = True
                    st.rerun()
            else:
                st.info("👆 Sélectionnez un emplacement dans le tableau")
                st.button("➕ Créer Job de Lavage", type="primary", use_container_width=True, disabled=True, key="btn_create_disabled")
            
            # Formulaire création
            if st.session_state.get('show_create_form_job', False) and 'selected_empl_idx_create' in st.session_state:
                st.markdown("---")
                st.markdown("### 📋 Paramètres du Job")
                
                original_idx = st.session_state['selected_empl_idx_create']
                empl_data = lots_filtres.loc[original_idx]
                
                badge = "🥔 BRUT" if statut_source == "BRUT" else "🔄 GRENAILLES"
                st.info(f"**Source** : {badge}  \n**Lot** : {empl_data['code_lot_interne']} - {empl_data['variete']}  \n**Emplacement** : {empl_data['site_stockage']}/{empl_data['emplacement_stockage']}")
                
                col1, col2 = st.columns(2)
                
                with col1:
                    quantite = st.slider(
                        "Quantité à laver *",
                        min_value=1,
                        max_value=int(empl_data['nombre_unites']),
                        value=min(5, int(empl_data['nombre_unites'])),
                        key="qte_create"
                    )
                    
                    date_prevue = st.date_input(
                        "Date prévue *",
                        value=datetime.now().date(),
                        key="date_create"
                    )
                
                with col2:
                    lignes = get_lignes_lavage()
                    if lignes:
                        ligne_opts = [f"{l['code']} ({l['capacite_th']} T/h)" for l in lignes]
                        sel_ligne = st.selectbox("Ligne de lavage *", ligne_opts, key="ligne_create")
                        
                        # Calcul poids
                        type_cond = empl_data['type_conditionnement']
                        if type_cond == 'Pallox':
                            poids_unit = 1900
                        elif type_cond == 'Petit Pallox':
                            poids_unit = 1200
                        elif type_cond == 'Big Bag':
                            poids_unit = 1600
                        else:
                            poids_unit = 1900
                        
                        poids_brut = quantite * poids_unit
                        
                        ligne_idx = ligne_opts.index(sel_ligne)
                        capacite = float(lignes[ligne_idx]['capacite_th'])
                        temps_est = (poids_brut / 1000) / capacite
                        ligne_code = lignes[ligne_idx]['code']
                        
                        st.metric("Poids brut", f"{poids_brut:,.0f} kg ({poids_brut/1000:.1f} T)")
                        st.metric("Temps estimé", f"{temps_est:.1f} heures")
                    else:
                        st.error("❌ Aucune ligne disponible")
                
                notes = st.text_area("Notes (optionnel)", key="notes_create_job")
                
                col_save, col_cancel = st.columns(2)
                
                with col_save:
                    if st.button("✅ Créer le Job", type="primary", use_container_width=True, key="btn_save_create"):
                        if lignes:
                            producteur = empl_data.get('producteur', '')
                            
                            success, message = create_job_lavage(
                                empl_data['lot_id'],
                                empl_data['emplacement_id'],
                                ligne_code,
                                quantite,
                                poids_brut,
                                date_prevue,
                                capacite,
                                statut_source,
                                producteur,
                                notes
                            )
                            
                            if success:
                                st.success(message)
                                st.balloons()
                                st.session_state.pop('show_create_form_job', None)
                                st.session_state.pop('selected_empl_idx_create', None)
                                st.rerun()
                            else:
                                st.error(message)
                        else:
                            st.error("❌ Impossible : aucune ligne")
                
                with col_cancel:
                    if st.button("❌ Annuler", use_container_width=True, key="btn_cancel_create"):
                        st.session_state.pop('show_create_form_job', None)
                        st.session_state.pop('selected_empl_idx_create', None)
                        st.rerun()
        else:
            st.warning(f"⚠️ Aucun emplacement avec filtres : {filtre_var} / {filtre_site}")
    else:
        if statut_source == "BRUT":
            st.warning("⚠️ Aucun lot BRUT disponible")
        else:
            st.warning("⚠️ Aucun lot GRENAILLES disponible")

# ============================================================
# ONGLET 5 : INFO PHASES 3-4
# ============================================================

with tab5:
    st.subheader("ℹ️ Planning Lavage V8 - Phases 1 à 5")
    
    st.markdown("""
    ### ✅ Phase 5 (ACTUELLE) - Workflow Grenailles
    
    **1. Terminaison différenciée** 🔄
    - Détection automatique statut_source
    - BRUT → Crée LAVÉ + GRENAILLES_BRUTES
    - GRENAILLES_BRUTES → Crée GRENAILLES_LAVÉES
    
    **2. Interface terminaison** ✅
    - Bouton "Terminer" sur jobs EN_COURS
    - Formulaire saisie tares
    - Calcul automatique terre
    - Validation emplacement destination
    
    **3. Stocks créés selon source** 📦
    - **Source BRUT** 🥔:
      - Stock LAVÉ (statut_lavage = 'LAVÉ')
      - Stock GRENAILLES_BRUTES (statut_lavage = 'GRENAILLES')
    - **Source GRENAILLES** 🔄:
      - Stock GRENAILLES_LAVÉES (statut_lavage = 'GRENAILLES_LAVÉES')
      - Pas de grenailles secondaires
    
    **4. Traçabilité complète** 🔗
    - lavage_job_id dans stock_emplacements
    - Mouvements stocks différenciés
    - Déduction stock source automatique
    
    ### ✅ Phase 4 - Créer Job
    
    **1. Onglet dédié "Créer Job"** ➕
    - Interface complète création jobs
    - Choix type source : BRUT 🥔 ou GRENAILLES 🔄
    - Affichage emplacements disponibles selon type
    - Filtres variété + site
    
    **2. Sélection intelligente** 🎯
    - BRUT : Emplacements statut_lavage = 'BRUT'
    - GRENAILLES : Emplacements statut_lavage = 'GRENAILLES'
    - Tableau avec sélection unique
    - Validation stock disponible
    
    **3. Création job avec statut_source** 📝
    - Formulaire paramètres (quantité, date, ligne)
    - Calcul auto poids et temps
    - Job créé avec bon statut_source
    - Producteur copié automatiquement
    
    ### ✅ Phase 3 - Badges Statut Source
    
    **1. Gestion statut_source** 🥔🔄
    - **BRUT** : Pommes de terre brutes (lot d'origine) → 🥔
    - **GRENAILLES_BRUTES** : Grenailles à relaver → 🔄
    - Badge visuel partout (calendrier, listes, cards)
    
    **2. Affichage différencié** 🎨
    - **Calendrier** : "Job #123 🥔" ou "Job #456 🔄"
    - **Jobs à placer** : Badge dans titre card
    - **Liste Jobs PRÉVU** : Badge dans expander "(🥔 BRUT)"
    
    ### ✅ Phase 2 - Producteur
    
    **1. Affichage producteur** 👤
    - Partout : calendrier, listes, jobs à placer
    - Dénormalisation dans planning_elements
    - Performance optimale (pas de JOIN)
    
    **2. Auto-repositionnement** 🎯
    - Détecte créneaux occupés
    - Propose prochain créneau libre
    - Plus d'erreur chevauchement
    
    ### ✅ Phase 1 - Admin & Validation
    
    **1. Onglet Admin complet** ⚙️
    - Supprimer, annuler, restaurer jobs
    - CRUD temps customs
    - Statistiques globales + par variété
    
    **2. Architecture planning** 📅
    - Pause intercalée automatique
    - Validation stock par emplacement
    - Recalcul heures fin automatique
    
    ### 🎯 Workflow Complet (Phases 1-5)
    
    **Lavage BRUT** 🥔
    1. Créer Job source BRUT (Phase 4) ✅
    2. Badge 🥔 visible partout (Phase 3) ✅
    3. Placer dans planning (Phase 1) ✅
    4. Démarrer job → EN_COURS (Phase 1) ✅
    5. Terminer job → TERMINÉ (Phase 5) ✅
       - Stock LAVÉ créé
       - Stock GRENAILLES_BRUTES créé
       - Stock BRUT déduit
    
    **Lavage GRENAILLES** 🔄
    1. Créer Job source GRENAILLES (Phase 4) ✅
    2. Badge 🔄 visible partout (Phase 3) ✅
    3. Placer dans planning (Phase 1) ✅
    4. Démarrer job → EN_COURS (Phase 1) ✅
    5. Terminer job → TERMINÉ (Phase 5) ✅
       - Stock GRENAILLES_LAVÉES créé
       - Stock GRENAILLES déduit
    
    ### 📊 Types de Stock (5 statuts)
    
    | Statut | Description | Provenance |
    |--------|-------------|------------|
    | BRUT | Pommes de terre brutes | Achat/Récolte |
    | LAVÉ | Pommes de terre lavées commercialisables | Job BRUT |
    | GRENAILLES | Grenailles brutes (petit calibre) | Job BRUT |
    | GRENAILLES_LAVÉES | Grenailles lavées commercialisables | Job GRENAILLES |
    | TERMINÉ | Épuisé | Vente/Utilisation |
    
    ### 🔄 Cycle Complet Grenailles
    
    ```
    BRUT (10T)
      ↓ [Job #1 BRUT]
      ├→ LAVÉ (7.5T)
      └→ GRENAILLES (0.5T)
           ↓ [Job #2 GRENAILLES]
           └→ GRENAILLES_LAVÉES (0.4T)
    ```
    
    Ce système gère le cycle complet de transformation des pommes de terre !
    """)

show_footer()
