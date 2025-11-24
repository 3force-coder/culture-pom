import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, time
from database import get_connection
from components import show_footer
from auth import is_authenticated
from auth.roles import is_admin
import io
import math

st.set_page_config(page_title="Planning Lavage - Culture Pom", page_icon="🧼", layout="wide")

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
    
    /* Centrage semaine */
    .semaine-center {
        text-align: center;
    }
    
    /* Cartes jobs à placer */
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
    
    /* Jobs planifiés par statut */
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
    
    /* Animation pulse pour EN_COURS */
    @keyframes pulse {
        0% { box-shadow: 0 0 0 0 rgba(255, 152, 0, 0.4); }
        70% { box-shadow: 0 0 0 10px rgba(255, 152, 0, 0); }
        100% { box-shadow: 0 0 0 0 rgba(255, 152, 0, 0); }
    }
    
    /* Indicateurs charge */
    .charge-low { color: #2e7d32; font-weight: bold; }
    .charge-medium { color: #f9a825; font-weight: bold; }
    .charge-high { color: #c62828; font-weight: bold; }
    
    /* Stats temps */
    .temps-ok { color: #2e7d32; }
    .temps-warning { color: #f57c00; }
    .temps-bad { color: #c62828; }
</style>
""", unsafe_allow_html=True)

if not is_authenticated():
    st.warning("⚠️ Veuillez vous connecter pour accéder à cette page")
    st.stop()

# ============================================================
# FONCTIONS UTILITAIRES
# ============================================================

def arrondir_quart_heure_sup(heure_obj):
    """Arrondit une heure au quart d'heure supérieur"""
    minutes = heure_obj.minute
    if minutes % 15 == 0:
        return heure_obj
    nouveau_minutes = ((minutes // 15) + 1) * 15
    if nouveau_minutes >= 60:
        nouvelle_heure = heure_obj.hour + 1
        nouveau_minutes = 0
        if nouvelle_heure >= 24:
            nouvelle_heure = 23
            nouveau_minutes = 45
        return time(nouvelle_heure, nouveau_minutes)
    return time(heure_obj.hour, nouveau_minutes)

def get_lignes_lavage():
    """Récupère les lignes de lavage actives"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT code, libelle, capacite_th 
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

def get_temps_customs():
    """Récupère les temps customs actifs"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, code, libelle, emoji, duree_minutes 
            FROM lavages_temps_customs 
            WHERE is_active = TRUE 
            ORDER BY id
        """)
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        return rows if rows else []
    except Exception as e:
        return []

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

def get_config_horaires():
    """Récupère la configuration des horaires par jour"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT jour_semaine, heure_debut, heure_fin 
            FROM lavages_config_horaires 
            WHERE is_active = TRUE 
            ORDER BY jour_semaine
        """)
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        config = {}
        for row in rows:
            config[row['jour_semaine']] = {'debut': row['heure_debut'], 'fin': row['heure_fin']}
        return config
    except:
        return {i: {'debut': time(5, 0), 'fin': time(22, 0) if i < 5 else time(20, 0)} for i in range(6)}

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
        return {'nb_prevus': nb_prevus, 'nb_en_cours': nb_en_cours, 'nb_termines': nb_termines, 'temps_total': float(temps_total)}
    except Exception as e:
        return None

def get_jobs_a_placer():
    """Récupère les jobs PRÉVU non encore planifiés"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT 
                lj.id, lj.lot_id, lj.code_lot_interne, lj.variete,
                lj.quantite_pallox, lj.poids_brut_kg, lj.temps_estime_heures,
                lj.date_prevue, lj.ligne_lavage as ligne_origine, lj.statut
            FROM lavages_jobs lj
            WHERE lj.statut = 'PRÉVU'
            ORDER BY lj.date_prevue, lj.id
        """)
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        if rows:
            df = pd.DataFrame(rows)
            for col in ['quantite_pallox', 'poids_brut_kg', 'temps_estime_heures']:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
            return df
        return pd.DataFrame()
    except Exception as e:
        return pd.DataFrame()

def get_planning_semaine(annee, semaine):
    """Récupère le planning d'une semaine donnée"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT 
                pe.id, pe.type_element, pe.job_id, pe.temps_custom_id,
                pe.date_prevue, pe.ligne_lavage, pe.ordre_jour,
                pe.heure_debut, pe.heure_fin, pe.duree_minutes,
                lj.code_lot_interne, lj.variete, lj.quantite_pallox,
                lj.poids_brut_kg, lj.statut as job_statut,
                lj.date_activation, lj.date_terminaison,
                lj.temps_estime_heures,
                tc.libelle as custom_libelle, tc.emoji as custom_emoji
            FROM lavages_planning_elements pe
            LEFT JOIN lavages_jobs lj ON pe.job_id = lj.id
            LEFT JOIN lavages_temps_customs tc ON pe.temps_custom_id = tc.id
            WHERE pe.annee = %s AND pe.semaine = %s
            ORDER BY pe.date_prevue, pe.ligne_lavage, pe.ordre_jour
        """, (annee, semaine))
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        if rows:
            return pd.DataFrame(rows)
        return pd.DataFrame()
    except:
        return pd.DataFrame()

def get_horaire_fin_jour(jour_semaine, horaires_config):
    """Retourne l'heure de fin pour un jour donné"""
    if jour_semaine in horaires_config:
        h_fin = horaires_config[jour_semaine]['fin']
        if isinstance(h_fin, time):
            return h_fin
    return time(22, 0) if jour_semaine < 5 else time(20, 0)

def get_capacite_jour(ligne_code, capacite_th, jour_semaine, horaires_config):
    """Calcule la capacité totale en heures pour un jour donné"""
    if jour_semaine not in horaires_config:
        return 17.0
    h_debut = horaires_config[jour_semaine]['debut']
    h_fin = horaires_config[jour_semaine]['fin']
    debut_h = h_debut.hour + h_debut.minute / 60 if isinstance(h_debut, time) else 5.0
    fin_h = h_fin.hour + h_fin.minute / 60 if isinstance(h_fin, time) else 22.0
    return fin_h - debut_h

def calculer_temps_utilise(planning_df, date_str, ligne):
    """Calcule le temps utilisé pour un jour/ligne"""
    if planning_df.empty:
        return 0.0
    mask = (planning_df['date_prevue'].astype(str) == date_str) & (planning_df['ligne_lavage'] == ligne)
    filtered = planning_df[mask]
    return filtered['duree_minutes'].sum() / 60 if not filtered.empty else 0.0

def verifier_chevauchement(planning_df, date_prevue, ligne_lavage, heure_debut, duree_minutes):
    """Vérifie si le créneau demandé chevauche un élément existant"""
    jour_str = str(date_prevue)
    if planning_df.empty:
        return True, None, None
    mask = (planning_df['date_prevue'].astype(str) == jour_str) & (planning_df['ligne_lavage'] == ligne_lavage)
    elements = planning_df[mask]
    if elements.empty:
        return True, None, None
    debut_minutes = heure_debut.hour * 60 + heure_debut.minute
    fin_minutes = debut_minutes + duree_minutes
    for _, elem in elements.iterrows():
        if pd.isna(elem['heure_debut']) or pd.isna(elem['heure_fin']):
            continue
        elem_debut = elem['heure_debut'].hour * 60 + elem['heure_debut'].minute
        elem_fin = elem['heure_fin'].hour * 60 + elem['heure_fin'].minute
        if debut_minutes < elem_fin and fin_minutes > elem_debut:
            prochaine_heure = arrondir_quart_heure_sup(elem['heure_fin'])
            return False, f"⚠️ Créneau occupé ! Prochaine heure : **{prochaine_heure.strftime('%H:%M')}**", prochaine_heure
    return True, None, None

def ajouter_element_planning(type_element, job_id, temps_custom_id, date_prevue, ligne_lavage, 
                             duree_minutes, annee, semaine, heure_debut_choisie):
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
        heure_fin_brute = time(min(23, fin_minutes // 60), fin_minutes % 60)
        heure_fin = arrondir_quart_heure_sup(heure_fin_brute)
        created_by = st.session_state.get('username', 'system')
        cursor.execute("""
            INSERT INTO lavages_planning_elements 
            (type_element, job_id, temps_custom_id, annee, semaine, date_prevue, 
             ligne_lavage, ordre_jour, heure_debut, heure_fin, duree_minutes, created_by)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (type_element, job_id, temps_custom_id, annee, semaine, date_prevue,
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
    """Retire un élément du planning"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM lavages_planning_elements WHERE id = %s", (element_id,))
        conn.commit()
        cursor.close()
        conn.close()
        return True, "✅ Retiré"
    except Exception as e:
        if 'conn' in locals():
            conn.rollback()
        return False, f"❌ Erreur : {str(e)}"

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
    """Termine un job avec calcul temps réel"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Récupérer job
        cursor.execute("""
            SELECT lot_id, quantite_pallox, poids_brut_kg,
                   code_lot_interne, ligne_lavage, date_activation
            FROM lavages_jobs
            WHERE id = %s AND statut = 'EN_COURS'
        """, (job_id,))
        job = cursor.fetchone()
        if not job:
            return False, "❌ Job introuvable ou pas EN_COURS"
        
        # Calculs tares
        poids_brut = float(job['poids_brut_kg'])
        poids_terre = poids_brut - poids_lave - poids_grenailles - poids_dechets
        tare_reelle = ((poids_dechets + poids_terre) / poids_brut) * 100
        rendement = ((poids_lave + poids_grenailles) / poids_brut) * 100
        
        # Validation
        if abs(poids_brut - (poids_lave + poids_grenailles + poids_dechets + poids_terre)) > 1:
            return False, f"❌ Poids incohérents !"
        
        # Calcul temps réel (en minutes)
        temps_reel_minutes = None
        if job['date_activation']:
            delta = datetime.now() - job['date_activation']
            temps_reel_minutes = int(delta.total_seconds() / 60)
        
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
        
        conn.commit()
        cursor.close()
        conn.close()
        
        temps_str = f"{temps_reel_minutes // 60}h{temps_reel_minutes % 60:02d}" if temps_reel_minutes else "N/A"
        return True, f"✅ Terminé ! Temps réel: {temps_str} - Rendement: {rendement:.1f}%"
    except Exception as e:
        if 'conn' in locals():
            conn.rollback()
        return False, f"❌ Erreur : {str(e)}"

def get_emplacements_saint_flavy():
    """Récupère les emplacements disponibles à SAINT_FLAVY"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT code_emplacement, nom_complet
            FROM ref_sites_stockage
            WHERE code_site = 'SAINT_FLAVY' AND is_active = TRUE
            ORDER BY code_emplacement
        """)
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        return [(row['code_emplacement'], row['nom_complet']) for row in rows] if rows else []
    except:
        return []

def get_lots_bruts_disponibles():
    """Récupère les lots bruts disponibles pour créer un job"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT 
                l.id as lot_id, l.code_lot_interne, l.nom_usage,
                l.calibre_min, l.calibre_max,
                COALESCE(v.nom_variete, l.code_variete) as variete,
                se.id as emplacement_id, se.site_stockage, se.emplacement_stockage,
                se.nombre_unites, se.poids_total_kg, se.type_conditionnement
            FROM lots_bruts l
            JOIN stock_emplacements se ON l.id = se.lot_id
            LEFT JOIN ref_varietes v ON l.code_variete = v.code_variete
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
            for col in ['nombre_unites', 'poids_total_kg', 'calibre_min', 'calibre_max']:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
            return df
        return pd.DataFrame()
    except:
        return pd.DataFrame()

def create_job_lavage(lot_id, emplacement_id, quantite_pallox, poids_brut_kg, 
                     date_prevue, ligne_lavage, capacite_th, notes=""):
    """Crée un nouveau job de lavage"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        lot_id = int(lot_id)
        emplacement_id = int(emplacement_id)
        quantite_pallox = int(quantite_pallox)
        poids_brut_kg = float(poids_brut_kg)
        capacite_th = float(capacite_th)
        
        cursor.execute("""
            SELECT l.code_lot_interne, COALESCE(v.nom_variete, l.code_variete) as variete
            FROM lots_bruts l
            LEFT JOIN ref_varietes v ON l.code_variete = v.code_variete
            WHERE l.id = %s
        """, (lot_id,))
        lot_info = cursor.fetchone()
        temps_estime = (poids_brut_kg / 1000) / capacite_th
        created_by = st.session_state.get('username', 'system')
        
        cursor.execute("""
            INSERT INTO lavages_jobs (
                lot_id, code_lot_interne, variete, quantite_pallox, poids_brut_kg,
                date_prevue, ligne_lavage, capacite_th, temps_estime_heures,
                statut, created_by, notes
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'PRÉVU', %s, %s)
            RETURNING id
        """, (lot_id, lot_info['code_lot_interne'], lot_info['variete'],
              quantite_pallox, poids_brut_kg, date_prevue, ligne_lavage,
              capacite_th, temps_estime, created_by, notes))
        job_id = cursor.fetchone()['id']
        conn.commit()
        cursor.close()
        conn.close()
        return True, f"✅ Job #{job_id} créé"
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

def generer_html_jour(planning_df, date_obj, ligne, lignes_info):
    """Génère le HTML pour impression"""
    jours_fr = ['Lundi', 'Mardi', 'Mercredi', 'Jeudi', 'Vendredi', 'Samedi', 'Dimanche']
    jour_nom = jours_fr[date_obj.weekday()]
    html = f"""<!DOCTYPE html><html><head><meta charset="UTF-8">
    <title>Planning {ligne} - {date_obj.strftime('%d/%m/%Y')}</title>
    <style>
        @page {{ size: A4 portrait; margin: 15mm; }}
        body {{ font-family: Arial; margin: 0; padding: 20px; }}
        h1 {{ color: #1976d2; border-bottom: 3px solid #1976d2; }}
        .element {{ border-left: 5px solid #388e3c; padding: 12px; margin: 10px 0; background: #f9f9f9; }}
        .element-custom {{ border-left-color: #7b1fa2; background: #f3e5f5; }}
        .horaire {{ font-weight: bold; color: #1976d2; }}
    </style></head><body>
    <h1>🗓️ PLANNING LAVAGE - {ligne}</h1>
    <p><strong>📅</strong> {jour_nom} {date_obj.strftime('%d/%m/%Y')}</p>"""
    
    jour_str = str(date_obj)
    if not planning_df.empty:
        mask = (planning_df['date_prevue'].astype(str) == jour_str) & (planning_df['ligne_lavage'] == ligne)
        elements = planning_df[mask].sort_values('heure_debut')
    else:
        elements = pd.DataFrame()
    
    if elements.empty:
        html += "<p style='color:#666;'>Aucun élément</p>"
    else:
        for _, elem in elements.iterrows():
            h_debut = elem['heure_debut'].strftime('%H:%M') if pd.notna(elem['heure_debut']) else '--:--'
            h_fin = elem['heure_fin'].strftime('%H:%M') if pd.notna(elem['heure_fin']) else '--:--'
            if elem['type_element'] == 'JOB':
                html += f"""<div class="element"><span class="horaire">{h_debut} → {h_fin}</span>
                <br><strong>Job #{int(elem['job_id'])} - {elem['variete']}</strong>
                <br>📦 {int(elem['quantite_pallox'])} pallox</div>"""
            else:
                html += f"""<div class="element element-custom"><span class="horaire">{h_debut} → {h_fin}</span>
                <br><strong>{elem['custom_emoji']} {elem['custom_libelle']}</strong></div>"""
    
    html += f"<p style='margin-top:30px;border-top:1px solid #ddd;padding-top:10px;font-size:0.9em;'>Imprimé le {datetime.now().strftime('%d/%m/%Y %H:%M')}</p></body></html>"
    return html

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

st.title("🧼 Planning Lavage")
st.caption("*Gestion des jobs de lavage - SAINT_FLAVY*")

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

tab1, tab2, tab3, tab4 = st.tabs(["📅 Planning Semaine", "📋 Liste Jobs", "➕ Créer Job", "⚙️ Admin"])

# ============================================================
# ONGLET 1 : PLANNING SEMAINE (fusionné de page 06)
# ============================================================

with tab1:
    # Contrôles
    col_ligne, col_nav_prev, col_semaine, col_nav_next, col_refresh = st.columns([2, 0.5, 2, 0.5, 1])
    
    lignes = get_lignes_lavage()
    with col_ligne:
        if lignes:
            ligne_options = [f"{l['code']} ({l['capacite_th']} T/h)" for l in lignes]
            selected_idx = next((i for i, l in enumerate(lignes) if l['code'] == st.session_state.selected_ligne), 0)
            selected = st.selectbox("🔵 Ligne", ligne_options, index=selected_idx, key="ligne_select")
            st.session_state.selected_ligne = lignes[ligne_options.index(selected)]['code']
    
    with col_nav_prev:
        if st.button("◀", key="prev_week", use_container_width=True):
            st.session_state.current_week_start -= timedelta(weeks=1)
            st.rerun()
    
    with col_semaine:
        week_start = st.session_state.current_week_start
        week_end = week_start + timedelta(days=5)
        annee, semaine, _ = week_start.isocalendar()
        st.markdown(f"""<div class="semaine-center"><h3>Semaine {semaine}</h3>
        <small>{week_start.strftime('%d/%m')} → {week_end.strftime('%d/%m/%Y')}</small></div>""", unsafe_allow_html=True)
    
    with col_nav_next:
        if st.button("▶", key="next_week", use_container_width=True):
            st.session_state.current_week_start += timedelta(weeks=1)
            st.rerun()
    
    with col_refresh:
        if st.button("🔄", key="refresh", use_container_width=True):
            st.rerun()
    
    st.markdown("---")
    
    # Chargement données
    jobs_a_placer = get_jobs_a_placer()
    temps_customs = get_temps_customs()
    horaires_config = get_config_horaires()
    planning_df = get_planning_semaine(annee, semaine)
    lignes_dict = {l['code']: float(l['capacite_th']) for l in lignes} if lignes else {'LIGNE_1': 13.0, 'LIGNE_2': 6.0}
    
    # Layout principal
    col_left, col_right = st.columns([1, 4])
    
    # COLONNE GAUCHE
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
                
                jours_options = ["Sélectionner..."] + [f"{['Lun','Mar','Mer','Jeu','Ven','Sam'][i]} {(week_start + timedelta(days=i)).strftime('%d/%m')}" for i in range(6)]
                jour_choisi = st.selectbox("Jour", jours_options, key=f"jour_job_{job['id']}", label_visibility="collapsed")
                
                if jour_choisi != "Sélectionner...":
                    jour_idx = jours_options.index(jour_choisi) - 1
                    date_cible = week_start + timedelta(days=jour_idx)
                    h_debut_jour = horaires_config.get(jour_idx, {}).get('debut', time(5, 0))
                    heure_debut = st.time_input("Heure", value=h_debut_jour, step=900, key=f"heure_job_{job['id']}", label_visibility="collapsed")
                    duree_min = int(job['temps_estime_heures'] * 60)
                    
                    ok, msg_ch, _ = verifier_chevauchement(planning_df, date_cible, st.session_state.selected_ligne, heure_debut, duree_min)
                    if not ok:
                        st.error(msg_ch)
                    else:
                        h_fin_jour = get_horaire_fin_jour(jour_idx, horaires_config)
                        fin_minutes = heure_debut.hour * 60 + heure_debut.minute + duree_min
                        if fin_minutes > h_fin_jour.hour * 60 + h_fin_jour.minute:
                            st.error(f"⚠️ Dépasse fin journée")
                        elif st.button("✅ Placer", key=f"confirm_job_{job['id']}", type="primary", use_container_width=True):
                            success, msg = ajouter_element_planning('JOB', int(job['id']), None, date_cible, st.session_state.selected_ligne, duree_min, annee, semaine, heure_debut)
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
            
            jours_tc = ["Sélectionner..."] + [f"{['Lun','Mar','Mer','Jeu','Ven','Sam'][i]} {(week_start + timedelta(days=i)).strftime('%d/%m')}" for i in range(6)]
            jour_tc = st.selectbox("Jour", jours_tc, key=f"jour_tc_{tc['id']}", label_visibility="collapsed")
            if jour_tc != "Sélectionner...":
                jour_idx = jours_tc.index(jour_tc) - 1
                date_cible = week_start + timedelta(days=jour_idx)
                h_debut = horaires_config.get(jour_idx, {}).get('debut', time(5, 0))
                heure_tc = st.time_input("Heure", value=h_debut, step=900, key=f"heure_tc_{tc['id']}", label_visibility="collapsed")
                ok, msg_ch, _ = verifier_chevauchement(planning_df, date_cible, st.session_state.selected_ligne, heure_tc, tc['duree_minutes'])
                if not ok:
                    st.error(msg_ch)
                elif st.button("✅", key=f"confirm_tc_{tc['id']}", use_container_width=True):
                    success, msg = ajouter_element_planning('CUSTOM', None, int(tc['id']), date_cible, st.session_state.selected_ligne, tc['duree_minutes'], annee, semaine, heure_tc)
                    if success:
                        st.rerun()
        
        with st.expander("➕ Créer temps"):
            new_lib = st.text_input("Libellé", key="new_tc_lib")
            new_dur = st.number_input("Durée (min)", 5, 480, 20, key="new_tc_dur")
            new_emo = st.selectbox("Emoji", ["⚙️", "☕", "🔧", "🍽️", "⏸️"], key="new_tc_emo")
            if st.button("Créer", key="btn_create_tc") and new_lib:
                creer_temps_custom(new_lib.upper().replace(" ", "_")[:20], new_lib, new_emo, new_dur)
                st.rerun()
    
    # COLONNE DROITE : CALENDRIER
    with col_right:
        jour_cols = st.columns(6)
        jours_noms = ['Lun', 'Mar', 'Mer', 'Jeu', 'Ven', 'Sam']
        
        for i, col_jour in enumerate(jour_cols):
            jour_date = week_start + timedelta(days=i)
            jour_str = str(jour_date)
            
            with col_jour:
                st.markdown(f"""<div class="day-header">{jours_noms[i]} {jour_date.strftime('%d/%m')}</div>""", unsafe_allow_html=True)
                
                # Capacités
                cap_html = ""
                for lc in sorted(lignes_dict.keys()):
                    cap_tot = get_capacite_jour(lc, lignes_dict[lc], i, horaires_config)
                    temps_ut = calculer_temps_utilise(planning_df, jour_str, lc)
                    temps_di = max(0, cap_tot - temps_ut)
                    charge = (temps_ut / cap_tot * 100) if cap_tot > 0 else 0
                    emoji = "🟢" if charge < 50 else "🟡" if charge < 80 else "🔴"
                    cap_html += f"<div><strong>{lc.replace('LIGNE_','L')}</strong>: {temps_di:.1f}h {emoji}</div>"
                st.markdown(f"""<div class="capacity-box">{cap_html}</div>""", unsafe_allow_html=True)
                
                # Éléments planifiés
                ligne_aff = st.session_state.selected_ligne
                if not planning_df.empty:
                    mask = (planning_df['date_prevue'].astype(str) == jour_str) & (planning_df['ligne_lavage'] == ligne_aff)
                    elements = planning_df[mask].sort_values('heure_debut')
                    
                    if elements.empty:
                        st.caption("_Vide_")
                    else:
                        for _, elem in elements.iterrows():
                            h_deb = elem['heure_debut'].strftime('%H:%M') if pd.notna(elem['heure_debut']) else '--:--'
                            h_fin = elem['heure_fin'].strftime('%H:%M') if pd.notna(elem['heure_fin']) else '--:--'
                            
                            if elem['type_element'] == 'JOB':
                                job_statut = elem.get('job_statut', 'PRÉVU')
                                
                                # Couleur selon statut
                                if job_statut == 'EN_COURS':
                                    css_class = "planned-encours"
                                    statut_emoji = "⏱️"
                                elif job_statut == 'TERMINÉ':
                                    css_class = "planned-termine"
                                    statut_emoji = "✅"
                                else:
                                    css_class = "planned-prevu"
                                    statut_emoji = "🟢"
                                
                                st.markdown(f"""<div class="{css_class}">
                                    <strong>{h_deb}</strong> {statut_emoji}<br>
                                    Job #{int(elem['job_id'])}<br>
                                    🌱 {elem['variete']}<br>
                                    📦 {int(elem['quantite_pallox']) if pd.notna(elem['quantite_pallox']) else '?'}p<br>
                                    <small>→{h_fin}</small>
                                </div>""", unsafe_allow_html=True)
                                
                                # Boutons action selon statut
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
                                    # Afficher temps écoulé
                                    if pd.notna(elem.get('date_activation')):
                                        delta = datetime.now() - elem['date_activation']
                                        minutes_ecoulees = int(delta.total_seconds() / 60)
                                        st.caption(f"⏱️ {minutes_ecoulees // 60}h{minutes_ecoulees % 60:02d} écoulées")
                                    
                                    if st.button("⏹️ Terminer", key=f"finish_{elem['id']}", type="primary", use_container_width=True):
                                        st.session_state[f'show_finish_{elem["job_id"]}'] = True
                                        st.rerun()
                                    
                                    # Popup tares
                                    if st.session_state.get(f'show_finish_{elem["job_id"]}', False):
                                        with st.expander("📝 Saisie tares", expanded=True):
                                            poids_brut = float(elem['poids_brut_kg']) if pd.notna(elem['poids_brut_kg']) else 0
                                            p_lave = st.number_input("Lavé (kg)", 0.0, poids_brut, poids_brut*0.75, key=f"p_lave_{elem['id']}")
                                            p_gren = st.number_input("Grenailles (kg)", 0.0, poids_brut, poids_brut*0.05, key=f"p_gren_{elem['id']}")
                                            p_dech = st.number_input("Déchets (kg)", 0.0, poids_brut, poids_brut*0.05, key=f"p_dech_{elem['id']}")
                                            p_terre = poids_brut - p_lave - p_gren - p_dech
                                            st.metric("Terre", f"{p_terre:.0f} kg")
                                            
                                            empls = get_emplacements_saint_flavy()
                                            empl = st.selectbox("Emplacement", [""] + [e[0] for e in empls], key=f"empl_{elem['id']}")
                                            
                                            if st.button("✅ Valider", key=f"val_finish_{elem['id']}", type="primary"):
                                                if empl:
                                                    success, msg = terminer_job(int(elem['job_id']), p_lave, p_gren, p_dech, "SAINT_FLAVY", empl)
                                                    if success:
                                                        st.success(msg)
                                                        st.session_state.pop(f'show_finish_{elem["job_id"]}', None)
                                                        st.rerun()
                                                    else:
                                                        st.error(msg)
                                                else:
                                                    st.warning("⚠️ Emplacement requis")
                                            
                                            if st.button("Annuler", key=f"cancel_{elem['id']}"):
                                                st.session_state.pop(f'show_finish_{elem["job_id"]}', None)
                                                st.rerun()
                                
                                elif job_statut == 'TERMINÉ':
                                    # Afficher stats temps
                                    if pd.notna(elem.get('temps_estime_heures')) and pd.notna(elem.get('date_activation')) and pd.notna(elem.get('date_terminaison')):
                                        temps_prevu = float(elem['temps_estime_heures']) * 60
                                        delta = elem['date_terminaison'] - elem['date_activation']
                                        temps_reel = delta.total_seconds() / 60
                                        ecart = temps_reel - temps_prevu
                                        color = "temps-ok" if ecart <= 0 else "temps-warning" if ecart < 15 else "temps-bad"
                                        st.markdown(f"<small class='{color}'>Prévu: {temps_prevu:.0f}' | Réel: {temps_reel:.0f}'</small>", unsafe_allow_html=True)
                            else:
                                # Temps custom
                                st.markdown(f"""<div class="planned-custom">
                                    <strong>{h_deb}</strong><br>
                                    {elem['custom_emoji']} {elem['custom_libelle']}<br>
                                    <small>→{h_fin}</small>
                                </div>""", unsafe_allow_html=True)
                                if st.button("❌", key=f"del_{elem['id']}"):
                                    retirer_element_planning(int(elem['id']))
                                    st.rerun()
                else:
                    st.caption("_Vide_")
    
    # Footer planning
    st.markdown("---")
    col_f1, col_f2, col_f3, col_f4 = st.columns([1, 1, 1, 2])
    with col_f1:
        if st.button("🗑️ Réinit. semaine", use_container_width=True):
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute("DELETE FROM lavages_planning_elements WHERE annee = %s AND semaine = %s", (annee, semaine))
            conn.commit()
            st.rerun()
    with col_f2:
        jours_print = [f"{jours_noms[i]} {(week_start + timedelta(days=i)).strftime('%d/%m')}" for i in range(6)]
        jour_print = st.selectbox("Jour", jours_print, key="jour_print", label_visibility="collapsed")
    with col_f3:
        jour_idx = jours_print.index(jour_print)
        date_print = week_start + timedelta(days=jour_idx)
        html_content = generer_html_jour(planning_df, date_print, st.session_state.selected_ligne, lignes_dict)
        st.download_button("🖨️ Imprimer", html_content, f"planning_{date_print.strftime('%Y%m%d')}.html", "text/html", use_container_width=True)
    with col_f4:
        if not planning_df.empty:
            total_l1 = planning_df[planning_df['ligne_lavage'] == 'LIGNE_1']['duree_minutes'].sum() / 60
            total_l2 = planning_df[planning_df['ligne_lavage'] == 'LIGNE_2']['duree_minutes'].sum() / 60
            st.markdown(f"**📊** L1={total_l1:.1f}h | L2={total_l2:.1f}h")

# ============================================================
# ONGLET 2 : LISTE JOBS
# ============================================================

with tab2:
    st.subheader("📋 Historique des Jobs")
    
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, code_lot_interne, variete, quantite_pallox, poids_brut_kg,
                   date_prevue, ligne_lavage, temps_estime_heures, statut,
                   date_activation, date_terminaison, rendement_pct, tare_reelle_pct,
                   created_by, created_at
            FROM lavages_jobs
            ORDER BY created_at DESC
            LIMIT 100
        """)
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        
        if rows:
            df = pd.DataFrame(rows)
            
            # Filtres
            col1, col2 = st.columns(2)
            with col1:
                statuts = ["Tous"] + df['statut'].unique().tolist()
                filtre_statut = st.selectbox("Statut", statuts, key="filtre_statut_liste")
            with col2:
                varietes = ["Toutes"] + df['variete'].dropna().unique().tolist()
                filtre_variete = st.selectbox("Variété", varietes, key="filtre_variete_liste")
            
            if filtre_statut != "Tous":
                df = df[df['statut'] == filtre_statut]
            if filtre_variete != "Toutes":
                df = df[df['variete'] == filtre_variete]
            
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.info("Aucun job")
    except Exception as e:
        st.error(f"Erreur : {str(e)}")

# ============================================================
# ONGLET 3 : CRÉER JOB
# ============================================================

with tab3:
    st.subheader("➕ Créer un Job de Lavage")
    
    lots_dispo = get_lots_bruts_disponibles()
    
    if not lots_dispo.empty:
        # Filtres
        col1, col2 = st.columns(2)
        with col1:
            varietes = ["Toutes"] + sorted(lots_dispo['variete'].dropna().unique().tolist())
            f_var = st.selectbox("Variété", varietes, key="f_var_create")
        with col2:
            sites = ["Tous"] + sorted(lots_dispo['site_stockage'].dropna().unique().tolist())
            f_site = st.selectbox("Site", sites, key="f_site_create")
        
        lots_f = lots_dispo.copy()
        if f_var != "Toutes":
            lots_f = lots_f[lots_f['variete'] == f_var]
        if f_site != "Tous":
            lots_f = lots_f[lots_f['site_stockage'] == f_site]
        
        if not lots_f.empty:
            st.markdown(f"**{len(lots_f)} lot(s) disponible(s)**")
            
            df_display = lots_f[['lot_id', 'emplacement_id', 'code_lot_interne', 'variete', 'site_stockage', 'nombre_unites', 'poids_total_kg']].copy()
            df_display = df_display.reset_index(drop=True)
            
            event = st.dataframe(df_display, use_container_width=True, hide_index=True, on_select="rerun", selection_mode="single-row", key="lots_create")
            
            selected_rows = event.selection.rows if hasattr(event, 'selection') else []
            
            if len(selected_rows) > 0:
                row = df_display.iloc[selected_rows[0]]
                lot_data = lots_dispo[lots_dispo['lot_id'] == row['lot_id']].iloc[0]
                
                st.success(f"✅ Sélectionné : {lot_data['code_lot_interne']} - {lot_data['variete']}")
                
                col1, col2 = st.columns(2)
                with col1:
                    quantite = st.slider("Pallox", 1, int(lot_data['nombre_unites']), min(5, int(lot_data['nombre_unites'])), key="qty_create")
                    date_prevue = st.date_input("Date", datetime.now().date(), key="date_create")
                with col2:
                    lignes = get_lignes_lavage()
                    ligne_opts = [f"{l['code']} ({l['capacite_th']} T/h)" for l in lignes]
                    ligne_sel = st.selectbox("Ligne", ligne_opts, key="ligne_create")
                    
                    poids_unit = {'Pallox': 1900, 'Petit Pallox': 1200, 'Big Bag': 1600}.get(lot_data['type_conditionnement'], 1900)
                    poids_brut = quantite * poids_unit
                    ligne_idx = ligne_opts.index(ligne_sel)
                    capacite = float(lignes[ligne_idx]['capacite_th'])
                    temps_est = (poids_brut / 1000) / capacite
                    
                    st.metric("Poids", f"{poids_brut:,} kg")
                    st.metric("Temps estimé", f"{temps_est:.1f}h")
                
                if st.button("✅ Créer Job", type="primary", use_container_width=True, key="btn_create_job"):
                    success, msg = create_job_lavage(lot_data['lot_id'], lot_data['emplacement_id'], quantite, poids_brut, date_prevue, lignes[ligne_idx]['code'], capacite)
                    if success:
                        st.success(msg)
                        st.balloons()
                        st.rerun()
                    else:
                        st.error(msg)
            else:
                st.info("👆 Sélectionnez un lot")
        else:
            st.warning("Aucun lot avec ces filtres")
    else:
        st.warning("Aucun lot BRUT disponible")

# ============================================================
# ONGLET 4 : ADMIN
# ============================================================

with tab4:
    if not is_admin():
        st.warning("⚠️ Accès réservé aux administrateurs")
    else:
        st.subheader("⚙️ Administration")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("### 🔧 Temps Customs")
            temps_customs = get_temps_customs()
            for tc in temps_customs:
                st.markdown(f"- {tc['emoji']} **{tc['libelle']}** ({tc['duree_minutes']} min)")
        
        with col2:
            st.markdown("### 📊 Statistiques")
            try:
                conn = get_connection()
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT 
                        AVG(rendement_pct) as rend_moy,
                        AVG(tare_reelle_pct) as tare_moy
                    FROM lavages_jobs 
                    WHERE statut = 'TERMINÉ' AND rendement_pct IS NOT NULL
                """)
                stats = cursor.fetchone()
                cursor.close()
                conn.close()
                
                if stats and stats['rend_moy']:
                    st.metric("Rendement moyen", f"{stats['rend_moy']:.1f}%")
                    st.metric("Tare moyenne", f"{stats['tare_moy']:.1f}%")
                else:
                    st.info("Pas encore de stats")
            except:
                st.info("Pas de stats disponibles")

show_footer()
