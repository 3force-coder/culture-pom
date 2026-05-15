import streamlit as st
import streamlit.components.v1 as stc
import pandas as pd
from datetime import datetime, timedelta, time
from database import get_connection
from components import show_footer
from auth import require_access
from auth.roles import is_admin
import io
import math

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

# ============================================================
# 🔒 CONTRÔLE D'ACCÈS RBAC
# ============================================================
require_access("PRODUCTION")
# ============================================================


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
        return {i: {'debut': time(0, 0), 'fin': time(23, 59)} for i in range(6)}

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

def get_jobs_a_placer(ligne_lavage=None):
    """Récupère les jobs PRÉVU, filtrés par ligne si précisé.
    
    Pour les jobs multi-lot (is_multi_lot=TRUE), un champ 'lots_detail' (list de dicts)
    est joint pour afficher le détail des lots dans le Kanban.
    Pour les mono-lot, lots_detail contiendra 1 seul élément.
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Sous-requête json_agg : récupère le détail des lots fille en une seule passe
        # Pour les multi-lot : N éléments dans le JSON
        # Pour les mono-lot : 1 élément (créé par create_job_lavage Commit 2)
        # Pour les anciens jobs sans ligne fille : tableau vide → fallback sur les colonnes legacy
        base_query = """
            SELECT 
                lj.id, lj.lot_id, lj.code_lot_interne, lj.variete,
                lj.quantite_pallox, lj.poids_brut_kg, lj.temps_estime_heures,
                lj.date_prevue, lj.ligne_lavage as ligne_origine, lj.statut,
                lj.statut_source,
                COALESCE(lj.is_multi_lot, FALSE) as is_multi_lot,
                COALESCE(lj.nb_lots, 1) as nb_lots,
                COALESCE(p.nom, lj.producteur) as producteur,
                lj.type_tapis, lj.etiquette_grenailles, lj.etiquette_pallox, lj.calibre_seuil,
                COALESCE(
                    (SELECT json_agg(
                        json_build_object(
                            'lot_id', ljl.lot_id,
                            'emplacement_id', ljl.emplacement_id,
                            'code_lot_interne', ljl.code_lot_interne,
                            'variete', ljl.variete,
                            'producteur', ljl.producteur,
                            'quantite_pallox', ljl.quantite_pallox,
                            'poids_brut_kg', ljl.poids_brut_kg,
                            'type_conditionnement', ljl.type_conditionnement,
                            'calibre_min', ljl.calibre_min,
                            'calibre_max', ljl.calibre_max,
                            'ordre', ljl.ordre
                        ) ORDER BY ljl.ordre
                    )
                    FROM lavages_jobs_lots ljl
                    WHERE ljl.job_id = lj.id),
                    '[]'::json
                ) as lots_detail
            FROM lavages_jobs lj
            LEFT JOIN lots_bruts lb ON lj.lot_id = lb.id
            LEFT JOIN ref_producteurs p ON lb.code_producteur = p.code_producteur
            WHERE lj.statut = 'PRÉVU'
        """
        
        if ligne_lavage:
            cursor.execute(base_query + " AND lj.ligne_lavage = %s ORDER BY lj.date_prevue, lj.id",
                          (ligne_lavage,))
        else:
            cursor.execute(base_query + " ORDER BY lj.date_prevue, lj.id")
        
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        if rows:
            df = pd.DataFrame([dict(r) for r in rows])
            for col in ['quantite_pallox', 'poids_brut_kg', 'temps_estime_heures']:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
            return df
        return pd.DataFrame()
    except Exception as e:
        st.error(f"❌ Erreur get_jobs_a_placer : {str(e)}")
        return pd.DataFrame()

def get_planning_semaine(annee, semaine):
    """Récupère le planning d'une semaine donnée.
    
    Pour les jobs multi-lot (lj.lot_id NULL au parent), le producteur,
    code_lot et emplacement sont récupérés via la table fille (1er lot par ordre).
    Un champ 'lots_detail' (JSON) liste tous les lots fille (utile pour tooltips/détail).
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT 
                pe.id, pe.type_element, pe.job_id, pe.temps_custom_id,
                pe.date_prevue, pe.ligne_lavage, pe.ordre_jour,
                pe.heure_debut, pe.heure_fin, pe.duree_minutes,
                lj.id as lj_id,
                -- Pour multi-lot, code_lot_interne devient un label "BATCH (N lots)"
                CASE
                    WHEN COALESCE(lj.is_multi_lot, FALSE) AND COALESCE(lj.nb_lots, 1) > 1
                    THEN '📦 BATCH (' || lj.nb_lots || ' lots)'
                    ELSE lj.code_lot_interne
                END as code_lot_interne,
                lj.variete, lj.quantite_pallox,
                lj.poids_brut_kg, lj.capacite_th, lj.statut as job_statut,
                lj.date_activation, lj.date_terminaison,
                lj.temps_estime_heures, lj.statut_source,
                lj.type_tapis, lj.etiquette_grenailles, lj.etiquette_pallox, lj.calibre_seuil,
                COALESCE(lj.emplacement_id, ljl_first.emplacement_id) as emplacement_id,
                COALESCE(lj.is_multi_lot, FALSE) as is_multi_lot,
                COALESCE(lj.nb_lots, 1) as nb_lots,
                -- Producteur : prend la BDD via lots_bruts (mono) OU ljl_first (multi)
                COALESCE(p.nom, ljl_first.producteur, lj.producteur) as producteur,
                se.site_stockage as empl_site,
                se.emplacement_stockage as empl_code,
                STRING_AGG(DISTINCT pc.marque || ' ' || pc.libelle, ', ') as produits_affectes,
                tc.libelle as custom_libelle, tc.emoji as custom_emoji,
                -- Pour info : détail des lots fille (utile pour tooltip/audit)
                COALESCE(
                    (SELECT json_agg(
                        json_build_object(
                            'code_lot_interne', ljl2.code_lot_interne,
                            'producteur', ljl2.producteur,
                            'quantite_pallox', ljl2.quantite_pallox,
                            'poids_brut_kg', ljl2.poids_brut_kg,
                            'ordre', ljl2.ordre
                        ) ORDER BY ljl2.ordre)
                    FROM lavages_jobs_lots ljl2 WHERE ljl2.job_id = lj.id),
                    '[]'::json
                ) as lots_detail
            FROM lavages_planning_elements pe
            LEFT JOIN lavages_jobs lj ON pe.job_id = lj.id
            LEFT JOIN lots_bruts lb ON lj.lot_id = lb.id
            LEFT JOIN ref_producteurs p ON lb.code_producteur = p.code_producteur
            -- Pour multi-lot : on prend les infos du 1er lot fille (ordre=1)
            LEFT JOIN LATERAL (
                SELECT ljl.emplacement_id, ljl.producteur, ljl.lot_id
                FROM lavages_jobs_lots ljl
                WHERE ljl.job_id = lj.id
                ORDER BY ljl.ordre LIMIT 1
            ) ljl_first ON TRUE
            LEFT JOIN stock_emplacements se ON COALESCE(lj.emplacement_id, ljl_first.emplacement_id) = se.id
            LEFT JOIN previsions_affectations pa ON pa.lot_id = COALESCE(lj.lot_id, ljl_first.lot_id)
                AND pa.is_active = TRUE AND pa.statut_stock = 'BRUT'
            LEFT JOIN ref_produits_commerciaux pc ON pa.code_produit_commercial = pc.code_produit
            LEFT JOIN lavages_temps_customs tc ON pe.temps_custom_id = tc.id
            WHERE pe.annee = %s AND pe.semaine = %s
            GROUP BY pe.id, pe.type_element, pe.job_id, pe.temps_custom_id,
                pe.date_prevue, pe.ligne_lavage, pe.ordre_jour,
                pe.heure_debut, pe.heure_fin, pe.duree_minutes,
                lj.id, lj.code_lot_interne, lj.variete, lj.quantite_pallox,
                lj.poids_brut_kg, lj.capacite_th, lj.statut,
                lj.date_activation, lj.date_terminaison,
                lj.temps_estime_heures, lj.statut_source,
                lj.emplacement_id, lj.is_multi_lot, lj.nb_lots,
                ljl_first.emplacement_id, ljl_first.producteur,
                p.nom, lj.producteur, se.site_stockage, se.emplacement_stockage,
                tc.libelle, tc.emoji
            ORDER BY pe.date_prevue, pe.ligne_lavage, pe.ordre_jour
        """, (annee, semaine))
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        if rows:
            return pd.DataFrame([dict(r) for r in rows])
        return pd.DataFrame()
    except Exception as e:
        st.error(f"❌ Erreur chargement planning : {str(e)}")
        return pd.DataFrame()

def get_horaire_fin_jour(jour_semaine, horaires_config):
    """Retourne l'heure de fin pour un jour donné.
    
    Par défaut 23:59 (plage 24h activée pour supporter 3 équipes).
    """
    if jour_semaine in horaires_config:
        h_fin = horaires_config[jour_semaine]['fin']
        if isinstance(h_fin, time):
            return h_fin
    return time(23, 59)

def get_capacite_jour(ligne_code, capacite_th, jour_semaine, horaires_config):
    """Calcule la capacité totale en heures pour un jour donné.
    
    Plage par défaut 00:00 → 23:59 = ~24h (cohérent avec 3 équipes).
    """
    if jour_semaine not in horaires_config:
        return 24.0
    h_debut = horaires_config[jour_semaine]['debut']
    h_fin = horaires_config[jour_semaine]['fin']
    debut_h = h_debut.hour + h_debut.minute / 60 if isinstance(h_debut, time) else 0.0
    fin_h = h_fin.hour + h_fin.minute / 60 if isinstance(h_fin, time) else 23.983
    return fin_h - debut_h

def calculer_temps_utilise(planning_df, date_str, ligne):
    """Calcule le temps utilisé pour un jour/ligne"""
    if planning_df.empty:
        return 0.0
    mask = (planning_df['date_prevue'].astype(str) == date_str) & (planning_df['ligne_lavage'] == ligne)
    filtered = planning_df[mask]
    return filtered['duree_minutes'].sum() / 60 if not filtered.empty else 0.0

def trouver_prochain_creneau_libre(planning_df, date_cible, ligne, heure_souhaitee, duree_min):
    """
    Trouve le prochain créneau disponible pour placer un élément.
    Si l'heure souhaitée est libre → la retourne telle quelle.
    Si occupée → calcule automatiquement la prochaine heure libre sans bloquer.
    Retourne : (heure_time, ok:bool, message:str)
    """
    if planning_df.empty:
        return heure_souhaitee, True, ""

    date_str = str(date_cible)
    mask = (planning_df['date_prevue'].astype(str) == date_str) & (planning_df['ligne_lavage'] == ligne)
    elements = planning_df[mask]

    if elements.empty:
        return heure_souhaitee, True, ""

    debut_souhaite = heure_souhaitee.hour * 60 + heure_souhaitee.minute

    creneaux_occupes = []
    for _, elem in elements.iterrows():
        if pd.isna(elem['heure_debut']) or pd.isna(elem['heure_fin']):
            continue
        elem_debut = elem['heure_debut'].hour * 60 + elem['heure_debut'].minute
        elem_fin = elem['heure_fin'].hour * 60 + elem['heure_fin'].minute
        creneaux_occupes.append({'debut': elem_debut, 'fin': elem_fin})

    creneaux_occupes.sort(key=lambda x: x['debut'])

    fin_souhaitee = debut_souhaite + duree_min
    conflit = False
    dernier_fin = debut_souhaite

    for creneau in creneaux_occupes:
        if not (fin_souhaitee <= creneau['debut'] or debut_souhaite >= creneau['fin']):
            conflit = True
            dernier_fin = max(dernier_fin, creneau['fin'])

    if not conflit:
        return heure_souhaitee, True, ""

    prochain_debut = dernier_fin
    prochain_fin = prochain_debut + duree_min
    for creneau in creneaux_occupes:
        if creneau['debut'] < prochain_fin and creneau['fin'] > prochain_debut:
            prochain_debut = creneau['fin']
            prochain_fin = prochain_debut + duree_min

    heure_proposee = time(min(23, prochain_debut // 60), prochain_debut % 60)
    message = f"ℹ️ Repositionné à {heure_proposee.strftime('%H:%M')} (créneau {heure_souhaitee.strftime('%H:%M')} occupé)"
    return heure_proposee, True, message

def inserer_pause_dans_job(job_planning_id, temps_custom_id, duree_pause_min, annee, semaine,
                           heure_insertion=None):
    """
    Insère une pause à l'intérieur d'un job planifié.
    - heure_insertion : heure exacte d'insertion de la pause (datetime.time).
                        Si None : fallback sur heure_debut du job.
                        Doit être comprise dans [heure_debut, heure_fin[ du job.
    - heure_fin du job est étendue de duree_pause_min (peu importe où la pause est insérée)
    - Les éléments suivants (même date/ligne, heure_debut >= heure_fin originale du job)
      sont décalés en cascade de duree_pause_min
    
    Note : visuellement la pause s'affiche comme un bloc séparé dans le calendrier
    (limitation du rendu vertical actuel), mais ses heures réelles en BDD sont correctes.
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Récupérer le job planifié
        cursor.execute("""
            SELECT id, job_id, date_prevue, ligne_lavage,
                   heure_debut, heure_fin, duree_minutes
            FROM lavages_planning_elements
            WHERE id = %s AND type_element = 'JOB'
        """, (job_planning_id,))
        job_elem = cursor.fetchone()
        if not job_elem:
            return False, "❌ Élément job introuvable"

        h_deb_job = job_elem['heure_debut']
        h_fin_job = job_elem['heure_fin']
        if h_deb_job is None or h_fin_job is None:
            return False, "❌ Heures du job non définies"

        job_debut_min = h_deb_job.hour * 60 + h_deb_job.minute
        job_fin_min_orig = h_fin_job.hour * 60 + h_fin_job.minute
        
        # Déterminer l'heure d'insertion : paramètre fourni OU fallback heure_debut du job
        if heure_insertion is not None:
            pause_debut_min = heure_insertion.hour * 60 + heure_insertion.minute
            # Validation : doit être dans [heure_debut_job, heure_fin_job[
            if pause_debut_min < job_debut_min:
                return False, (f"❌ L'heure d'insertion ({heure_insertion.strftime('%H:%M')}) est "
                              f"avant le début du job ({h_deb_job.strftime('%H:%M')})")
            if pause_debut_min >= job_fin_min_orig:
                return False, (f"❌ L'heure d'insertion ({heure_insertion.strftime('%H:%M')}) est "
                              f"après ou égale à la fin du job ({h_fin_job.strftime('%H:%M')})")
        else:
            # Fallback : début du job
            pause_debut_min = job_debut_min
        
        pause_fin_min   = pause_debut_min + duree_pause_min
        pause_h_debut   = time(min(23, pause_debut_min // 60), pause_debut_min % 60)
        pause_h_fin     = time(min(23, pause_fin_min   // 60), pause_fin_min   % 60)

        # Nouvelle heure_fin du job = ancienne + durée pause (peu importe où la pause est dans le job)
        new_job_fin_min  = job_fin_min_orig + duree_pause_min
        new_job_h_fin    = time(min(23, new_job_fin_min // 60), new_job_fin_min % 60)

        created_by = st.session_state.get('username', 'system')

        # 1. Étendre heure_fin du job
        cursor.execute("""
            UPDATE lavages_planning_elements
            SET heure_fin = %s
            WHERE id = %s
        """, (new_job_h_fin, job_planning_id))

        # 2. Insérer la pause comme élément CUSTOM
        # IMPORTANT : pour un type_element CUSTOM, job_id DOIT être NULL
        # (contrainte BDD check_type_refs : un élément ne peut référencer
        #  qu'UN type de référence à la fois — soit JOB via job_id, soit CUSTOM via temps_custom_id)
        cursor.execute("""
            SELECT COALESCE(MAX(ordre_jour), 0) as max_ordre
            FROM lavages_planning_elements
            WHERE date_prevue = %s AND ligne_lavage = %s
        """, (job_elem['date_prevue'], job_elem['ligne_lavage']))
        next_ordre = (cursor.fetchone()['max_ordre'] or 0) + 1

        cursor.execute("""
            INSERT INTO lavages_planning_elements
            (type_element, job_id, temps_custom_id, annee, semaine,
             date_prevue, ligne_lavage, ordre_jour,
             heure_debut, heure_fin, duree_minutes, created_by)
            VALUES ('CUSTOM', NULL, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (temps_custom_id, annee, semaine,
              job_elem['date_prevue'], job_elem['ligne_lavage'], next_ordre,
              pause_h_debut, pause_h_fin, duree_pause_min, created_by))

        # 3. Cascade : décaler tous les éléments suivants
        # (heure_debut >= heure_fin ORIGINALE du job, exclu le job lui-même)
        cursor.execute("""
            SELECT id, heure_debut, heure_fin, duree_minutes
            FROM lavages_planning_elements
            WHERE date_prevue = %s
              AND ligne_lavage = %s
              AND id != %s
              AND heure_debut >= %s
            ORDER BY heure_debut
        """, (job_elem['date_prevue'], job_elem['ligne_lavage'],
              job_planning_id, h_fin_job))

        suivants = cursor.fetchall()
        nb_decales = 0
        for s in suivants:
            if s['heure_debut'] is None:
                continue
            s_debut_min = s['heure_debut'].hour * 60 + s['heure_debut'].minute
            s_duree     = int(s['duree_minutes'])
            new_s_debut = s_debut_min + duree_pause_min
            new_s_fin   = new_s_debut + s_duree
            new_s_h_deb = time(min(23, new_s_debut // 60), new_s_debut % 60)
            new_s_h_fin = time(min(23, new_s_fin   // 60), new_s_fin   % 60)
            cursor.execute("""
                UPDATE lavages_planning_elements
                SET heure_debut = %s, heure_fin = %s
                WHERE id = %s
            """, (new_s_h_deb, new_s_h_fin, s['id']))
            nb_decales += 1

        conn.commit()
        cursor.close()
        conn.close()

        msg = (f"✅ Pause insérée dans Job #{job_elem['job_id']} "
               f"({pause_h_debut.strftime('%H:%M')}→{pause_h_fin.strftime('%H:%M')}) "
               f"— Job étendu jusqu'à {new_job_h_fin.strftime('%H:%M')}")
        if nb_decales:
            msg += f" — {nb_decales} élément(s) suivant(s) décalé(s)"
        return True, msg

    except Exception as e:
        if 'conn' in locals():
            conn.rollback()
        return False, f"❌ Erreur : {str(e)}"


def get_lots_fille_du_job(job_id):
    """Récupère la liste des lignes filles (lavages_jobs_lots) d'un job batch.
    
    Retourne une liste de dicts avec les infos enrichies (producteur, site, emplacement)
    utiles pour l'UI de modification batch.
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT 
                ljl.id, ljl.lot_id, ljl.emplacement_id, ljl.ordre,
                ljl.code_lot_interne, ljl.variete, ljl.producteur,
                ljl.quantite_pallox, ljl.poids_brut_kg, ljl.type_conditionnement,
                ljl.calibre_min, ljl.calibre_max,
                se.site_stockage as site_stockage,
                se.emplacement_stockage as emplacement_stockage
            FROM lavages_jobs_lots ljl
            LEFT JOIN stock_emplacements se ON ljl.emplacement_id = se.id
            WHERE ljl.job_id = %s
            ORDER BY ljl.ordre
        """, (job_id,))
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        return [dict(r) for r in rows]
    except Exception:
        return []


def ajouter_element_planning(type_element, job_id, temps_custom_id, date_prevue, ligne_lavage, 
                             duree_minutes, annee, semaine, heure_debut_choisie):
    """Ajoute un élément au planning.
    
    Si l'élément dépasse minuit (heure_debut + duree > 24h00) :
      - Crée une partie J  : date_prevue=date, heure_debut, heure_fin=23:59, duree=(24h00-debut)
      - Crée une partie J+1 : date_prevue=date+1, heure_debut=00:00, heure_fin=reste, parent_element_id=<id partie J>
      - La FK CASCADE garantit que supprimer la partie J supprime aussi J+1 automatiquement.
    
    Si l'élément tient sur la journée : 1 seule ligne créée (comportement legacy).
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        heure_debut = heure_debut_choisie
        debut_minutes = heure_debut.hour * 60 + heure_debut.minute
        fin_minutes = debut_minutes + int(duree_minutes)
        created_by = st.session_state.get('username', 'system')
        MINUTES_PAR_JOUR = 24 * 60  # = 1440
        
        # ============================================================
        # CAS 1 : pas de chevauchement minuit (fin <= 24h00)
        # ============================================================
        if fin_minutes <= MINUTES_PAR_JOUR:
            cursor.execute("""
                SELECT COALESCE(MAX(ordre_jour), 0) as max_ordre
                FROM lavages_planning_elements
                WHERE date_prevue = %s AND ligne_lavage = %s
            """, (date_prevue, ligne_lavage))
            next_ordre = (cursor.fetchone()['max_ordre'] or 0) + 1
            
            # heure_fin entre 00:00 et 23:59 (gérer cas fin = 24:00 → 23:59)
            if fin_minutes == MINUTES_PAR_JOUR:
                heure_fin_brute = time(23, 59)
            else:
                heure_fin_brute = time(fin_minutes // 60, fin_minutes % 60)
            heure_fin = arrondir_quart_heure_sup(heure_fin_brute)
            # Sécurité : arrondi qui dépasserait minuit → on plafonne à 23:59
            if heure_fin == time(0, 0) and fin_minutes >= MINUTES_PAR_JOUR - 14:
                heure_fin = time(23, 59)
            
            cursor.execute("""
                INSERT INTO lavages_planning_elements 
                (type_element, job_id, temps_custom_id, annee, semaine, date_prevue, 
                 ligne_lavage, ordre_jour, heure_debut, heure_fin, duree_minutes, created_by)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
            """, (type_element, job_id, temps_custom_id, annee, semaine, date_prevue,
                  ligne_lavage, next_ordre, heure_debut, heure_fin, duree_minutes, created_by))
            new_id = cursor.fetchone()['id']
            conn.commit()
            cursor.close()
            conn.close()
            return True, f"✅ Placé ({heure_debut.strftime('%H:%M')} → {heure_fin.strftime('%H:%M')})"
        
        # ============================================================
        # CAS 2 : chevauchement minuit → découpage en 2 lignes liées
        # ============================================================
        # Partie J : du heure_debut jusqu'à 23:59
        duree_partie_j = MINUTES_PAR_JOUR - debut_minutes  # ex : 22h00 → 24h00 = 120min
        # Partie J+1 : de 00:00 jusqu'à (fin_minutes - 24h00)
        duree_partie_j1 = fin_minutes - MINUTES_PAR_JOUR  # ex : 26h00 - 24h00 = 120min
        
        date_j1 = date_prevue + timedelta(days=1)
        annee_j1, semaine_j1, _ = date_j1.isocalendar()
        
        # ordre_jour J
        cursor.execute("""
            SELECT COALESCE(MAX(ordre_jour), 0) as max_ordre
            FROM lavages_planning_elements
            WHERE date_prevue = %s AND ligne_lavage = %s
        """, (date_prevue, ligne_lavage))
        next_ordre_j = (cursor.fetchone()['max_ordre'] or 0) + 1
        
        # ordre_jour J+1
        cursor.execute("""
            SELECT COALESCE(MAX(ordre_jour), 0) as max_ordre
            FROM lavages_planning_elements
            WHERE date_prevue = %s AND ligne_lavage = %s
        """, (date_j1, ligne_lavage))
        next_ordre_j1 = (cursor.fetchone()['max_ordre'] or 0) + 1
        
        # INSERT partie J
        cursor.execute("""
            INSERT INTO lavages_planning_elements 
            (type_element, job_id, temps_custom_id, annee, semaine, date_prevue, 
             ligne_lavage, ordre_jour, heure_debut, heure_fin, duree_minutes, created_by)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (type_element, job_id, temps_custom_id, annee, semaine, date_prevue,
              ligne_lavage, next_ordre_j, heure_debut, time(23, 59),
              duree_partie_j, created_by))
        parent_id = int(cursor.fetchone()['id'])
        
        # INSERT partie J+1 (avec parent_element_id)
        heure_fin_j1 = time(duree_partie_j1 // 60, duree_partie_j1 % 60)
        cursor.execute("""
            INSERT INTO lavages_planning_elements 
            (type_element, job_id, temps_custom_id, annee, semaine, date_prevue, 
             ligne_lavage, ordre_jour, heure_debut, heure_fin, duree_minutes, created_by,
             parent_element_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (type_element, job_id, temps_custom_id, annee_j1, semaine_j1, date_j1,
              ligne_lavage, next_ordre_j1, time(0, 0), heure_fin_j1,
              duree_partie_j1, created_by, parent_id))
        
        conn.commit()
        cursor.close()
        conn.close()
        return True, (f"✅ Placé sur 2 jours ({heure_debut.strftime('%H:%M')} {date_prevue.strftime('%d/%m')} "
                      f"→ {heure_fin_j1.strftime('%H:%M')} {date_j1.strftime('%d/%m')})")
    except Exception as e:
        if 'conn' in locals():
            conn.rollback()
        return False, f"❌ Erreur : {str(e)}"

def retirer_element_planning(element_id):
    """Retire un élément du planning.
    
    Si l'élément est un CUSTOM (pause/maintenance/etc.) inséré DANS un job
    (heure_debut de l'élément comprise dans [heure_debut, heure_fin] d'un job
     de la même date/ligne), alors la suppression effectue l'opération inverse
    de inserer_pause_dans_job :
      - Réduit heure_fin du job de duree_minutes de la pause
      - Décale EN ARRIÈRE de duree_minutes les éléments suivants (qui démarrent
        après ou égal à l'heure_fin actuelle du job)
      - Puis DELETE la pause
    
    Sinon (élément JOB, ou CUSTOM en créneau libre) : DELETE simple.
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Récupérer l'élément à supprimer
        cursor.execute("""
            SELECT id, type_element, date_prevue, ligne_lavage,
                   heure_debut, duree_minutes
            FROM lavages_planning_elements
            WHERE id = %s
        """, (element_id,))
        elem = cursor.fetchone()
        if not elem:
            return False, "❌ Élément introuvable"
        
        msg_extra = ""
        
        # Si c'est un CUSTOM avec une heure_debut renseignée, chercher un job englobant
        if elem['type_element'] == 'CUSTOM' and elem['heure_debut'] is not None:
            duree_pause = int(elem['duree_minutes'])
            cursor.execute("""
                SELECT id, job_id, heure_debut, heure_fin
                FROM lavages_planning_elements
                WHERE date_prevue = %s
                  AND ligne_lavage = %s
                  AND type_element = 'JOB'
                  AND parent_element_id IS NULL
                  AND heure_debut <= %s
                  AND heure_fin   >= %s
                  AND id != %s
                ORDER BY heure_debut
                LIMIT 1
            """, (elem['date_prevue'], elem['ligne_lavage'],
                  elem['heure_debut'], elem['heure_debut'], element_id))
            job_englobant = cursor.fetchone()
            
            if job_englobant:
                # === RESTAURATION : opération inverse de inserer_pause_dans_job ===
                # 1. Réduire heure_fin du job de duree_pause
                h_fin_job = job_englobant['heure_fin']
                h_fin_min = h_fin_job.hour * 60 + h_fin_job.minute
                new_fin_min = h_fin_min - duree_pause
                if new_fin_min < 0:
                    # Cas pathologique : ne pas faire de calcul négatif
                    new_fin_h = h_fin_job
                else:
                    new_fin_h = time(new_fin_min // 60, new_fin_min % 60)
                cursor.execute("""
                    UPDATE lavages_planning_elements
                    SET heure_fin = %s
                    WHERE id = %s
                """, (new_fin_h, job_englobant['id']))
                
                # 2. Décaler EN ARRIÈRE de duree_pause les éléments suivants
                # (heure_debut >= heure_fin actuelle du job, donc placés après la pause)
                # On les décale de duree_pause vers l'arrière
                cursor.execute("""
                    SELECT id, heure_debut, heure_fin
                    FROM lavages_planning_elements
                    WHERE date_prevue = %s
                      AND ligne_lavage = %s
                      AND id != %s
                      AND id != %s
                      AND heure_debut >= %s
                    ORDER BY heure_debut
                """, (elem['date_prevue'], elem['ligne_lavage'],
                      element_id, job_englobant['id'], h_fin_job))
                suivants = cursor.fetchall()
                nb_decales = 0
                for s in suivants:
                    if s['heure_debut'] is None or s['heure_fin'] is None:
                        continue
                    s_deb_min = s['heure_debut'].hour * 60 + s['heure_debut'].minute
                    s_fin_min = s['heure_fin'].hour   * 60 + s['heure_fin'].minute
                    new_s_deb = max(0, s_deb_min - duree_pause)
                    new_s_fin = max(0, s_fin_min - duree_pause)
                    new_s_h_deb = time(new_s_deb // 60, new_s_deb % 60)
                    new_s_h_fin = time(new_s_fin // 60, new_s_fin % 60)
                    cursor.execute("""
                        UPDATE lavages_planning_elements
                        SET heure_debut = %s, heure_fin = %s
                        WHERE id = %s
                    """, (new_s_h_deb, new_s_h_fin, s['id']))
                    nb_decales += 1
                
                msg_extra = (f" — Job #{job_englobant['job_id']} restauré à {new_fin_h.strftime('%H:%M')}"
                             f"{f' ({nb_decales} élément(s) décalé(s) en arrière)' if nb_decales else ''}")
        
        # 3. Supprimer l'élément (la pause ou autre)
        cursor.execute("DELETE FROM lavages_planning_elements WHERE id = %s", (element_id,))
        conn.commit()
        cursor.close()
        conn.close()
        return True, f"✅ Retiré{msg_extra}"
    except Exception as e:
        if 'conn' in locals():
            conn.rollback()
        return False, f"❌ Erreur : {str(e)}"


def deplacer_element_planning(element_id, nouvelle_date, nouvelle_heure, planning_df, ligne_lavage, horaires_config):
    """
    Déplace un élément du planning vers un nouveau créneau.
    Décale en cascade tous les éléments suivants du même jour/ligne
    dont l'heure_debut < nouvelle heure de fin du job déplacé.
    
    Support chevauchement minuit (Commit 5b) :
    - Si l'élément déplacé est en réalité une partie J+1 (parent_element_id NOT NULL),
      on redirige le déplacement sur le parent.
    - Si la nouvelle position fait dépasser minuit, on découpe : update parent + crée/replace enfant J+1.
    - Si l'élément avait déjà un enfant J+1 et que la nouvelle position ne dépasse plus minuit,
      l'enfant J+1 est supprimé.
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Récupérer l'élément à déplacer (avec parent_element_id pour gérer le cas enfant)
        cursor.execute("""
            SELECT id, duree_minutes, ligne_lavage, annee, semaine,
                   type_element, job_id, temps_custom_id, parent_element_id
            FROM lavages_planning_elements
            WHERE id = %s
        """, (element_id,))
        elem = cursor.fetchone()
        if not elem:
            return False, "❌ Élément introuvable"
        
        # ============================================================
        # Cas particulier : on essaie de déplacer une partie J+1 (enfant)
        # → on redirige sur le parent (pas de déplacement d'enfant seul)
        # ============================================================
        if elem.get('parent_element_id'):
            # Rediriger : déplacer le parent à la place
            parent_id = int(elem['parent_element_id'])
            # On récupère la durée TOTALE (parent + enfant) car l'utilisateur voulait
            # déplacer l'ensemble logique
            cursor.execute("""
                SELECT duree_minutes FROM lavages_planning_elements WHERE id = %s
            """, (parent_id,))
            parent_row = cursor.fetchone()
            if not parent_row:
                return False, "❌ Parent introuvable"
            # Rappel récursif (la prochaine itération traitera le parent comme cas normal)
            cursor.close()
            conn.close()
            return deplacer_element_planning(parent_id, nouvelle_date, nouvelle_heure,
                                              planning_df, ligne_lavage, horaires_config)
        
        # ============================================================
        # Vérifier si l'élément avait déjà un enfant J+1 (chevauchement existant)
        # → on récupère la DURÉE TOTALE pour le repositionnement
        # ============================================================
        cursor.execute("""
            SELECT id, duree_minutes
            FROM lavages_planning_elements
            WHERE parent_element_id = %s
        """, (element_id,))
        enfant_existant = cursor.fetchone()
        
        if enfant_existant:
            # Durée totale = durée parent + durée enfant
            duree_totale = int(elem['duree_minutes']) + int(enfant_existant['duree_minutes'])
        else:
            duree_totale = int(elem['duree_minutes'])
        
        # ============================================================
        # Calculer la nouvelle position (potentiellement chevauchante)
        # ============================================================
        debut_min = nouvelle_heure.hour * 60 + nouvelle_heure.minute
        fin_min = debut_min + duree_totale
        MINUTES_PAR_JOUR = 24 * 60
        
        # Recalculer annee/semaine de la nouvelle date
        nouvelle_annee, nouvelle_semaine, _ = nouvelle_date.isocalendar()
        
        # CAS A : pas de chevauchement minuit
        if fin_min <= MINUTES_PAR_JOUR:
            # Calcul heure_fin sûr
            if fin_min == MINUTES_PAR_JOUR:
                nouvelle_heure_fin = time(23, 59)
            else:
                nouvelle_heure_fin = time(fin_min // 60, fin_min % 60)
            
            # Update parent vers son nouveau placement, durée TOTALE restaurée
            cursor.execute("""
                UPDATE lavages_planning_elements
                SET date_prevue = %s,
                    heure_debut = %s,
                    heure_fin = %s,
                    duree_minutes = %s,
                    annee = %s,
                    semaine = %s
                WHERE id = %s
            """, (nouvelle_date, nouvelle_heure, nouvelle_heure_fin,
                  duree_totale,
                  nouvelle_annee, nouvelle_semaine, element_id))
            
            # Si un enfant existait, on le supprime (CASCADE non utile car on a déjà update parent)
            if enfant_existant:
                cursor.execute("""
                    DELETE FROM lavages_planning_elements WHERE id = %s
                """, (int(enfant_existant['id']),))
        
        # CAS B : chevauchement minuit → recalculer le split
        else:
            duree_partie_j = MINUTES_PAR_JOUR - debut_min
            duree_partie_j1 = fin_min - MINUTES_PAR_JOUR
            date_j1 = nouvelle_date + timedelta(days=1)
            annee_j1, semaine_j1, _ = date_j1.isocalendar()
            heure_fin_j1 = time(duree_partie_j1 // 60, duree_partie_j1 % 60)
            
            # Update parent (partie J)
            cursor.execute("""
                UPDATE lavages_planning_elements
                SET date_prevue = %s,
                    heure_debut = %s,
                    heure_fin = %s,
                    duree_minutes = %s,
                    annee = %s,
                    semaine = %s
                WHERE id = %s
            """, (nouvelle_date, nouvelle_heure, time(23, 59),
                  duree_partie_j,
                  nouvelle_annee, nouvelle_semaine, element_id))
            
            # ordre_jour J+1
            cursor.execute("""
                SELECT COALESCE(MAX(ordre_jour), 0) as max_ordre
                FROM lavages_planning_elements
                WHERE date_prevue = %s AND ligne_lavage = %s
            """, (date_j1, ligne_lavage))
            next_ordre_j1 = (cursor.fetchone()['max_ordre'] or 0) + 1
            
            if enfant_existant:
                # Update l'enfant existant pour pointer sur la nouvelle date J+1
                cursor.execute("""
                    UPDATE lavages_planning_elements
                    SET date_prevue = %s,
                        heure_debut = %s,
                        heure_fin = %s,
                        duree_minutes = %s,
                        ordre_jour = %s,
                        annee = %s,
                        semaine = %s
                    WHERE id = %s
                """, (date_j1, time(0, 0), heure_fin_j1, duree_partie_j1,
                      next_ordre_j1, annee_j1, semaine_j1, int(enfant_existant['id'])))
            else:
                # Créer l'enfant J+1
                cursor.execute("""
                    INSERT INTO lavages_planning_elements 
                    (type_element, job_id, temps_custom_id, annee, semaine, date_prevue, 
                     ligne_lavage, ordre_jour, heure_debut, heure_fin, duree_minutes, created_by,
                     parent_element_id)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (elem['type_element'], elem.get('job_id'), elem.get('temps_custom_id'),
                      annee_j1, semaine_j1, date_j1, ligne_lavage, next_ordre_j1,
                      time(0, 0), heure_fin_j1, duree_partie_j1,
                      st.session_state.get('username', 'system'), element_id))

        # ============================================================
        # CASCADE : décaler les éléments suivants du jour J qui chevauchent
        # ============================================================
        # Note : on cascade UNIQUEMENT sur le jour J du nouveau placement
        # (les éléments du J+1 chevauchent éventuellement avec l'enfant, géré séparément)
        cursor.execute("""
            SELECT id, heure_debut, heure_fin, duree_minutes
            FROM lavages_planning_elements
            WHERE date_prevue = %s
              AND ligne_lavage = %s
              AND id != %s
              AND parent_element_id IS DISTINCT FROM %s
              AND heure_debut >= %s
            ORDER BY heure_debut
        """, (nouvelle_date, ligne_lavage, element_id, element_id, nouvelle_heure))
        suivants = cursor.fetchall()

        # Décaler en cascade uniquement les éléments qui chevauchent la nouvelle position
        # Curseur de temps : fin de l'élément déplacé (sur partie J seulement)
        if fin_min <= MINUTES_PAR_JOUR:
            curseur_temps = fin_min
        else:
            curseur_temps = MINUTES_PAR_JOUR  # le J est rempli jusqu'à minuit
        
        nb_decales = 0
        for s in suivants:
            if s['heure_debut'] is None:
                continue
            s_debut = s['heure_debut'].hour * 60 + s['heure_debut'].minute
            s_duree = int(s['duree_minutes'])

            if s_debut < curseur_temps:
                # Chevauchement → pousser après le curseur
                nouveau_debut = curseur_temps
                nouveau_fin = nouveau_debut + s_duree
                # Plafonner à 23:59 pour éviter de propager le chevauchement (cas rare)
                nouvelle_h_debut = time(min(23, nouveau_debut // 60), nouveau_debut % 60)
                if nouveau_fin >= MINUTES_PAR_JOUR:
                    nouvelle_h_fin = time(23, 59)
                else:
                    nouvelle_h_fin = time(nouveau_fin // 60, nouveau_fin % 60)
                cursor.execute("""
                    UPDATE lavages_planning_elements
                    SET heure_debut = %s, heure_fin = %s
                    WHERE id = %s
                """, (nouvelle_h_debut, nouvelle_h_fin, s['id']))
                curseur_temps = nouveau_fin
                nb_decales += 1
            else:
                # Plus de chevauchement : on s'arrête
                break

        conn.commit()
        cursor.close()
        conn.close()

        if fin_min > MINUTES_PAR_JOUR:
            date_j1 = nouvelle_date + timedelta(days=1)
            msg = f"✅ Déplacé sur 2 jours ({nouvelle_heure.strftime('%H:%M')} {nouvelle_date.strftime('%d/%m')} → {heure_fin_j1.strftime('%H:%M')} {date_j1.strftime('%d/%m')})"
        else:
            msg = f"✅ Déplacé à {nouvelle_heure.strftime('%H:%M')}"
        if nb_decales > 0:
            msg += f" — {nb_decales} élément(s) décalé(s) en cascade"
        return True, msg

    except Exception as e:
        if 'conn' in locals():
            conn.rollback()
        return False, f"❌ Erreur : {str(e)}"

def modifier_job(job_id, elem_planning_id, nouveau_pallox, poids_unit, nouvelle_cadence,
                 type_conditionnement=None, lots_updates=None):
    """
    Modifie quantité + cadence d'un job PRÉVU.
    Recalcule poids_brut_kg, temps_estime_heures et met à jour
    la durée dans lavages_planning_elements (heure_fin incluse).
    
    Propagation aux lignes filles (lavages_jobs_lots) :
    - Mono-lot : update la fille unique avec nouveau pallox + poids + type_conditionnement
    - Multi-lot (batch) :
        * Si lots_updates fourni (liste de dicts {fille_id, quantite_pallox}) :
            update direct de chaque fille avec son nouveau pallox.
            Le poids_brut_kg de la fille est recalculé avec son type_conditionnement
            actuel (POIDS_UNIT_MAP). Le type_conditionnement n'est PAS modifié.
            Le parent reçoit la somme des filles.
            'nouveau_pallox' et 'poids_unit' sont alors IGNORÉS (calculés depuis les filles).
        * Sinon (compat) : distribution pro-rata du nouveau total sur les filles existantes.
    
    Support chevauchement minuit (Commit 5b) :
    Si la nouvelle durée fait dépasser minuit, crée/met à jour/supprime l'enfant J+1
    de la même façon que deplacer_element_planning.
    """
    from datetime import time as dtime, timedelta
    
    # Mapping type_conditionnement → poids unitaire kg/pallox
    POIDS_UNIT_MAP = {'Pallox': 1900, 'Petit Pallox': 800, 'Big Bag': 1600}
    
    try:
        conn = get_connection()
        cursor = conn.cursor()

        # ============================================================
        # 1. Récupérer infos job + élément planning (SQL préfixée pour éviter ambiguïté)
        # ============================================================
        cursor.execute("""
            SELECT lj.statut AS statut,
                   pe.heure_debut AS heure_debut,
                   pe.date_prevue AS date_prevue,
                   pe.ligne_lavage AS ligne_lavage,
                   pe.parent_element_id AS parent_element_id,
                   COALESCE(lj.is_multi_lot, FALSE) AS is_multi_lot,
                   COALESCE(lj.nb_lots, 1) AS nb_lots
            FROM lavages_jobs lj
            LEFT JOIN lavages_planning_elements pe ON pe.job_id = lj.id
            WHERE lj.id = %s AND pe.id = %s
        """, (job_id, elem_planning_id))
        row = cursor.fetchone()
        if not row:
            return False, "❌ Job ou élément planning introuvable"
        if row['statut'] != 'PRÉVU':
            return False, f"❌ Impossible de modifier un job {row['statut']}"
        
        is_multi_lot = bool(row['is_multi_lot'])
        
        # Si on modifie depuis un élément enfant J+1, rediriger sur le parent
        if row['parent_element_id']:
            parent_elem_id = int(row['parent_element_id'])
            cursor.close()
            conn.close()
            return modifier_job(job_id, parent_elem_id, nouveau_pallox,
                                poids_unit, nouvelle_cadence, type_conditionnement,
                                lots_updates=lots_updates)
        
        # ============================================================
        # 2. Calcul des nouvelles valeurs PARENT selon le mode
        # ============================================================
        if is_multi_lot and lots_updates:
            # === Mode BATCH avec saisie fine par fille ===
            # On va recalculer le total parent à partir des updates des filles
            # Récupérer les types_conditionnement actuels des filles
            cursor.execute("""
                SELECT id, type_conditionnement
                FROM lavages_jobs_lots
                WHERE job_id = %s
            """, (job_id,))
            filles_actuelles = {int(f['id']): f for f in cursor.fetchall()}
            
            total_pallox = 0
            total_poids = 0.0
            for upd in lots_updates:
                fille_id = int(upd['fille_id'])
                qty = int(upd['quantite_pallox'])
                if fille_id not in filles_actuelles:
                    conn.rollback()
                    return False, f"❌ Lot fille {fille_id} introuvable pour ce job"
                if qty < 0:
                    conn.rollback()
                    return False, f"❌ Nb pallox négatif interdit (fille {fille_id})"
                type_cond_fille = str(filles_actuelles[fille_id]['type_conditionnement'] or 'Pallox')
                poids_unit_fille = POIDS_UNIT_MAP.get(type_cond_fille, 1900)
                poids_fille = qty * poids_unit_fille
                total_pallox += qty
                total_poids += poids_fille
            
            if total_pallox == 0:
                conn.rollback()
                return False, "❌ Le batch doit avoir au moins 1 pallox au total"
            
            nouveau_pallox_int = total_pallox
            nouveau_poids = total_poids
        else:
            # === Mode mono-lot OU batch sans lots_updates (compat pro-rata) ===
            nouveau_pallox_int = int(nouveau_pallox)
            nouveau_poids = float(nouveau_pallox_int) * float(poids_unit)
        
        nouveau_temps_h = (nouveau_poids / 1000) / float(nouvelle_cadence)
        nouveau_duree_min = int(round(nouveau_temps_h * 60))

        # ============================================================
        # 3. UPDATE lavages_jobs (parent)
        # ============================================================
        cursor.execute("""
            UPDATE lavages_jobs
            SET quantite_pallox = %s,
                poids_brut_kg   = %s,
                capacite_th     = %s,
                temps_estime_heures = %s
            WHERE id = %s AND statut = 'PRÉVU'
        """, (nouveau_pallox_int, nouveau_poids, float(nouvelle_cadence),
              nouveau_temps_h, job_id))
        
        # ============================================================
        # 4. Propagation aux lignes filles (lavages_jobs_lots)
        # ============================================================
        if not is_multi_lot:
            # MONO-LOT : update la fille unique (1 seule ligne attendue)
            if type_conditionnement:
                cursor.execute("""
                    UPDATE lavages_jobs_lots
                    SET quantite_pallox = %s,
                        poids_brut_kg = %s,
                        type_conditionnement = %s
                    WHERE job_id = %s
                """, (nouveau_pallox_int, nouveau_poids, type_conditionnement, job_id))
            else:
                cursor.execute("""
                    UPDATE lavages_jobs_lots
                    SET quantite_pallox = %s,
                        poids_brut_kg = %s
                    WHERE job_id = %s
                """, (nouveau_pallox_int, nouveau_poids, job_id))
        elif lots_updates:
            # === BATCH avec saisie fine : update direct de chaque fille ===
            for upd in lots_updates:
                fille_id = int(upd['fille_id'])
                qty = int(upd['quantite_pallox'])
                type_cond_fille = str(filles_actuelles[fille_id]['type_conditionnement'] or 'Pallox')
                poids_unit_fille = POIDS_UNIT_MAP.get(type_cond_fille, 1900)
                poids_fille = qty * poids_unit_fille
                cursor.execute("""
                    UPDATE lavages_jobs_lots
                    SET quantite_pallox = %s,
                        poids_brut_kg = %s
                    WHERE id = %s
                """, (qty, poids_fille, fille_id))
        else:
            # MULTI-LOT (batch) sans lots_updates : distribution pro-rata (compat ancien comportement)
            cursor.execute("""
                SELECT id, quantite_pallox, poids_brut_kg, ordre
                FROM lavages_jobs_lots
                WHERE job_id = %s
                ORDER BY ordre
            """, (job_id,))
            filles = cursor.fetchall()
            if not filles:
                conn.rollback()
                return False, "❌ Aucune ligne fille trouvée pour ce batch"
            
            # Distribution pro-rata des pallox sur les filles selon leurs quantites actuelles
            quantites_actuelles = [float(f['quantite_pallox']) for f in filles]
            nouveaux_pallox = _distribute_pro_rata(nouveau_pallox_int, quantites_actuelles)
            
            # Pour le poids, on calcule au pro-rata des poids actuels (= pro-rata du poids_unit déduit)
            # En multi-lot, le poids_unit peut différer entre filles (mix conditionnement).
            # On préserve donc le ratio poids_brut/quantite_pallox de chaque fille.
            # Si une fille passe à 0 pallox, son poids passe à 0.
            for fille, new_qty in zip(filles, nouveaux_pallox):
                if new_qty == 0:
                    new_poids = 0.0
                else:
                    qty_old = float(fille['quantite_pallox'])
                    poids_old = float(fille['poids_brut_kg'])
                    poids_unit_fille = poids_old / qty_old if qty_old > 0 else float(poids_unit)
                    new_poids = new_qty * poids_unit_fille
                cursor.execute("""
                    UPDATE lavages_jobs_lots
                    SET quantite_pallox = %s,
                        poids_brut_kg = %s
                    WHERE id = %s
                """, (new_qty, new_poids, fille['id']))

        # ============================================================
        # 4. Recalculer heure_fin du planning + gérer chevauchement minuit
        # ============================================================
        if not row['heure_debut']:
            # Pas d'heure de début enregistrée : on ne peut rien recalculer
            conn.commit()
            cursor.close()
            conn.close()
            return True, (f"✅ Job #{job_id} modifié — {nouveau_pallox_int} pallox, "
                          f"{nouveau_poids/1000:.1f} T, {nouveau_temps_h:.1f}h")
        
        h_deb = row['heure_debut']
        date_parent = row['date_prevue']
        ligne_lavage = row['ligne_lavage']
        debut_min = h_deb.hour * 60 + h_deb.minute
        fin_min = debut_min + nouveau_duree_min
        MINUTES_PAR_JOUR = 24 * 60
        
        # Vérifier si l'élément a déjà un enfant J+1 (chevauchement existant)
        cursor.execute("""
            SELECT id, duree_minutes
            FROM lavages_planning_elements
            WHERE parent_element_id = %s
        """, (elem_planning_id,))
        enfant_existant = cursor.fetchone()
        
        if fin_min <= MINUTES_PAR_JOUR:
            # CAS A : pas de chevauchement minuit après modif
            if fin_min == MINUTES_PAR_JOUR:
                nouvelle_heure_fin = dtime(23, 59)
            else:
                nouvelle_heure_fin = dtime(fin_min // 60, fin_min % 60)
            cursor.execute("""
                UPDATE lavages_planning_elements
                SET duree_minutes = %s, heure_fin = %s
                WHERE id = %s
            """, (nouveau_duree_min, nouvelle_heure_fin, elem_planning_id))
            # Si un enfant existait, on le supprime (la nouvelle durée tient sur la journée)
            if enfant_existant:
                cursor.execute("""
                    DELETE FROM lavages_planning_elements WHERE id = %s
                """, (int(enfant_existant['id']),))
        else:
            # CAS B : chevauchement minuit après modif → split parent + enfant J+1
            duree_partie_j = MINUTES_PAR_JOUR - debut_min
            duree_partie_j1 = fin_min - MINUTES_PAR_JOUR
            date_j1 = date_parent + timedelta(days=1)
            annee_j1, semaine_j1, _ = date_j1.isocalendar()
            heure_fin_j1 = dtime(duree_partie_j1 // 60, duree_partie_j1 % 60)
            
            # UPDATE parent (partie J)
            cursor.execute("""
                UPDATE lavages_planning_elements
                SET duree_minutes = %s, heure_fin = %s
                WHERE id = %s
            """, (duree_partie_j, dtime(23, 59), elem_planning_id))
            
            if enfant_existant:
                # UPDATE l'enfant existant pour pointer sur la nouvelle date J+1 avec nouvelle durée
                cursor.execute("""
                    SELECT COALESCE(MAX(ordre_jour), 0) AS max_ordre
                    FROM lavages_planning_elements
                    WHERE date_prevue = %s AND ligne_lavage = %s AND id != %s
                """, (date_j1, ligne_lavage, int(enfant_existant['id'])))
                next_ordre_j1 = (cursor.fetchone()['max_ordre'] or 0) + 1
                cursor.execute("""
                    UPDATE lavages_planning_elements
                    SET date_prevue = %s,
                        heure_debut = %s,
                        heure_fin = %s,
                        duree_minutes = %s,
                        ordre_jour = %s,
                        annee = %s,
                        semaine = %s
                    WHERE id = %s
                """, (date_j1, dtime(0, 0), heure_fin_j1, duree_partie_j1,
                      next_ordre_j1, annee_j1, semaine_j1, int(enfant_existant['id'])))
            else:
                # Récupérer infos parent pour créer un enfant cohérent
                cursor.execute("""
                    SELECT type_element, job_id, temps_custom_id
                    FROM lavages_planning_elements
                    WHERE id = %s
                """, (elem_planning_id,))
                parent_full = cursor.fetchone()
                cursor.execute("""
                    SELECT COALESCE(MAX(ordre_jour), 0) AS max_ordre
                    FROM lavages_planning_elements
                    WHERE date_prevue = %s AND ligne_lavage = %s
                """, (date_j1, ligne_lavage))
                next_ordre_j1 = (cursor.fetchone()['max_ordre'] or 0) + 1
                cursor.execute("""
                    INSERT INTO lavages_planning_elements
                    (type_element, job_id, temps_custom_id, annee, semaine, date_prevue,
                     ligne_lavage, ordre_jour, heure_debut, heure_fin, duree_minutes, created_by,
                     parent_element_id)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (parent_full['type_element'], parent_full.get('job_id'),
                      parent_full.get('temps_custom_id'),
                      annee_j1, semaine_j1, date_j1, ligne_lavage, next_ordre_j1,
                      dtime(0, 0), heure_fin_j1, duree_partie_j1,
                      st.session_state.get('username', 'system'), elem_planning_id))

        conn.commit()
        cursor.close()
        conn.close()
        msg_mode = f" ({row['nb_lots']} lots)" if is_multi_lot else ""
        return True, (f"✅ Job #{job_id}{msg_mode} modifié — {nouveau_pallox_int} pallox, "
                      f"{nouveau_poids/1000:.1f} T, {nouveau_temps_h:.1f}h")

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

def _distribute_pro_rata(total, parts):
    """Distribue 'total' (int) en parts proportionnelles à 'parts' (list de float).
    
    Utilise largest-remainder pour que sum(résultat) == total exactement.
    Retourne une list[int] de même longueur que 'parts'.
    
    Ex : _distribute_pro_rata(10, [0.6, 0.4]) → [6, 4]
    Ex : _distribute_pro_rata(10, [1, 1, 1]) → [4, 3, 3] (le 1er reçoit le reste)
    """
    if total == 0 or not parts:
        return [0] * len(parts)
    total_parts = sum(parts)
    if total_parts == 0:
        return [0] * len(parts)
    # Calculer la part flottante de chacun
    raw = [(p / total_parts) * total for p in parts]
    # Arrondi inférieur
    base = [int(r) for r in raw]
    # Reste à distribuer (par ordre décroissant de partie décimale)
    reste = total - sum(base)
    fractions = sorted(
        [(i, raw[i] - base[i]) for i in range(len(parts))],
        key=lambda x: -x[1]
    )
    for k in range(reste):
        idx = fractions[k % len(fractions)][0]
        base[idx] += 1
    return base


def terminer_job(job_id, 
                 # Sorties LAVÉ
                 nb_pallox_lave, type_cond_lave, poids_lave, calibre_min_lave, calibre_max_lave,
                 # Sorties GRENAILLES
                 nb_pallox_gren, type_cond_gren, poids_grenailles, calibre_min_gren, calibre_max_gren,
                 # Déchets (reste en kg)
                 poids_dechets,
                 # Destination
                 site_dest, emplacement_dest, notes=""):
    """Termine un job avec création stocks LAVÉ/GRENAILLES et déduction source.
    
    SUPPORT MULTI-LOT (Commit 4) :
      - Si job mono-lot : 1 itération sur 1 lot fille (comportement legacy)
      - Si job multi-lot : itère sur N lots fille avec distribution pro-rata stricte
        basée sur le poids_brut_kg de chaque lot fille
    
    Saisie GLOBALE des sorties (Q3) :
      - nb_pallox_lave + poids_lave = total batch LAVÉ
      - nb_pallox_gren + poids_grenailles = total batch GRENAILLES
      - Ces totaux sont répartis pro-rata sur chaque lot fille
    
    Si source = BRUT → crée LAVÉ + GRENAILLES_BRUTES par lot fille
    Si source = GRENAILLES_BRUTES → crée GRENAILLES_LAVÉES par lot fille (pas de sous-grenailles)
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # ============================================================
        # 1. Récupérer le job (parent)
        # ============================================================
        cursor.execute("""
            SELECT lj.id, lj.lot_id, lj.quantite_pallox, lj.poids_brut_kg,
                   lj.code_lot_interne, lj.ligne_lavage, lj.date_activation,
                   lj.variete, lj.emplacement_id, lj.statut_source,
                   COALESCE(lj.is_multi_lot, FALSE) as is_multi_lot,
                   COALESCE(lj.nb_lots, 1) as nb_lots
            FROM lavages_jobs lj
            WHERE lj.id = %s AND lj.statut = 'EN_COURS'
        """, (job_id,))
        job = cursor.fetchone()
        if not job:
            return False, "❌ Job introuvable ou pas EN_COURS"
        
        is_multi_lot = bool(job['is_multi_lot'])
        
        # ============================================================
        # 2. Récupérer les lots fille (1 si mono, N si multi)
        # ============================================================
        cursor.execute("""
            SELECT lot_id, emplacement_id, code_lot_interne, variete,
                   quantite_pallox, poids_brut_kg, ordre
            FROM lavages_jobs_lots
            WHERE job_id = %s
            ORDER BY ordre
        """, (job_id,))
        lots_fille = cursor.fetchall()
        
        # Fallback rétrocompat : si pas de ligne fille (anciens jobs créés avant Commit 1
        # ou si Commit 2 jamais déployé), on construit une fille fictive depuis lavages_jobs
        if not lots_fille:
            if not job['lot_id']:
                return False, "❌ Job sans détail de lots (ni table fille, ni lot_id sur parent)"
            lots_fille = [{
                'lot_id': job['lot_id'],
                'emplacement_id': job['emplacement_id'],
                'code_lot_interne': job['code_lot_interne'],
                'variete': job['variete'],
                'quantite_pallox': int(job['quantite_pallox']),
                'poids_brut_kg': float(job['poids_brut_kg']),
                'ordre': 1,
            }]
        
        # ============================================================
        # 3. Vérifier cohérence poids globaux
        # ============================================================
        poids_brut_total = float(job['poids_brut_kg'])
        statut_source = job['statut_source'] or 'BRUT'
        is_grenailles_source = (statut_source == 'GRENAILLES_BRUTES')
        
        # Convertir entrées en types natifs
        nb_pallox_lave = int(nb_pallox_lave) if nb_pallox_lave else 0
        nb_pallox_gren = int(nb_pallox_gren) if nb_pallox_gren else 0
        poids_lave = float(poids_lave) if poids_lave else 0.0
        poids_grenailles = float(poids_grenailles) if poids_grenailles else 0.0
        poids_dechets = float(poids_dechets) if poids_dechets else 0.0
        
        if is_grenailles_source:
            poids_grenailles = 0.0
            nb_pallox_gren = 0
            poids_terre = poids_brut_total - poids_lave - poids_dechets
            tare_reelle = ((poids_dechets + poids_terre) / poids_brut_total) * 100 if poids_brut_total > 0 else 0
            rendement = (poids_lave / poids_brut_total) * 100 if poids_brut_total > 0 else 0
        else:
            poids_terre = poids_brut_total - poids_lave - poids_grenailles - poids_dechets
            tare_reelle = ((poids_dechets + poids_terre) / poids_brut_total) * 100 if poids_brut_total > 0 else 0
            rendement = ((poids_lave + poids_grenailles) / poids_brut_total) * 100 if poids_brut_total > 0 else 0
        
        total_sorties = poids_lave + poids_grenailles + poids_dechets + poids_terre
        if abs(poids_brut_total - total_sorties) > 1:
            return False, f"❌ Poids incohérents ! Brut={poids_brut_total:.0f} vs Total={total_sorties:.0f}"
        
        # ============================================================
        # 4. Distribution pro-rata des pallox et poids sur les lots fille
        # ============================================================
        poids_brut_par_lot = [float(lf['poids_brut_kg']) for lf in lots_fille]
        
        # Pallox LAVÉ et GRENAILLES répartis pro-rata du poids_brut_kg de chaque fille
        pallox_lave_par_lot = _distribute_pro_rata(nb_pallox_lave, poids_brut_par_lot)
        pallox_gren_par_lot = _distribute_pro_rata(nb_pallox_gren, poids_brut_par_lot)
        
        # Poids LAVÉ et GRENAILLES répartis en float
        total_poids_brut = sum(poids_brut_par_lot)
        if total_poids_brut > 0:
            poids_lave_par_lot = [(p / total_poids_brut) * poids_lave for p in poids_brut_par_lot]
            poids_gren_par_lot = [(p / total_poids_brut) * poids_grenailles for p in poids_brut_par_lot]
        else:
            poids_lave_par_lot = [0.0] * len(lots_fille)
            poids_gren_par_lot = [0.0] * len(lots_fille)
        
        terminated_by = st.session_state.get('username', 'system')
        temps_reel_minutes = None
        if job['date_activation']:
            delta = datetime.now() - job['date_activation']
            temps_reel_minutes = int(delta.total_seconds() / 60)
        
        # ============================================================
        # 5. UPDATE lavages_jobs (totaux agrégés au parent)
        # ============================================================
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
        # 6. POUR CHAQUE LOT FILLE : déduction source + création stocks
        # ============================================================
        if is_grenailles_source:
            statut_sortie = 'GRENAILLES_LAVÉES'
            type_stock_sortie = 'GRENAILLES_LAVÉES'
            type_mvt_source = 'LAVAGE_GRENAILLES_REDUIT'
            type_mvt_sortie = 'LAVAGE_CREATION_GRENAILLES_LAVEES'
        else:
            statut_sortie = 'LAVÉ'
            type_stock_sortie = 'LAVÉ'
            type_mvt_source = 'LAVAGE_BRUT_REDUIT'
            type_mvt_sortie = 'LAVAGE_CREATION_LAVE'
        
        for i, lf in enumerate(lots_fille):
            lf_lot_id = int(lf['lot_id'])
            lf_emp_id = int(lf['emplacement_id']) if lf['emplacement_id'] else None
            lf_qty_brut = int(lf['quantite_pallox'])
            lf_poids_brut = float(lf['poids_brut_kg'])
            lf_pallox_lave = pallox_lave_par_lot[i]
            lf_pallox_gren = pallox_gren_par_lot[i]
            lf_poids_lave = poids_lave_par_lot[i]
            lf_poids_gren = poids_gren_par_lot[i]
            
            # 6a. Lire l'emplacement source de ce lot fille
            if lf_emp_id:
                cursor.execute("""
                    SELECT id, nombre_unites, poids_total_kg, site_stockage, emplacement_stockage, statut_lavage
                    FROM stock_emplacements
                    WHERE id = %s
                """, (lf_emp_id,))
            else:
                # Fallback : chercher via lot_id (anciens jobs sans emplacement_id)
                cursor.execute("""
                    SELECT id, nombre_unites, poids_total_kg, site_stockage, emplacement_stockage, statut_lavage
                    FROM stock_emplacements
                    WHERE lot_id = %s
                      AND statut_lavage IN ('BRUT', 'GRENAILLES_BRUTES')
                    ORDER BY is_active DESC, id
                    LIMIT 1
                """, (lf_lot_id,))
            stock_source = cursor.fetchone()
            if not stock_source:
                conn.rollback()
                cursor.close()
                conn.close()
                return False, f"❌ Stock source introuvable pour lot fille {lf_lot_id} (emplacement {lf_emp_id})"
            
            # S'assurer que le stock source a bien un statut_lavage
            if not stock_source['statut_lavage']:
                cursor.execute("""
                    UPDATE stock_emplacements 
                    SET statut_lavage = 'BRUT', type_stock = 'PRINCIPAL'
                    WHERE id = %s AND statut_lavage IS NULL
                """, (stock_source['id'],))
            
            # 6b. Créer le stock LAVÉ (ou GRENAILLES_LAVÉES) de la part fille
            if lf_pallox_lave > 0 and lf_poids_lave > 0:
                cursor.execute("""
                    INSERT INTO stock_emplacements 
                    (lot_id, site_stockage, emplacement_stockage, nombre_unites, 
                     type_conditionnement, poids_total_kg, type_stock, statut_lavage, 
                     calibre_min, calibre_max, lavage_job_id, is_active)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, TRUE)
                """, (lf_lot_id, site_dest, emplacement_dest, lf_pallox_lave, 
                      type_cond_lave, lf_poids_lave, type_stock_sortie, statut_sortie, 
                      int(calibre_min_lave), int(calibre_max_lave), job_id))
            
            # 6c. Créer stock GRENAILLES_BRUTES (si source BRUT et grenailles > 0)
            if not is_grenailles_source and lf_pallox_gren > 0 and lf_poids_gren > 0:
                cursor.execute("""
                    INSERT INTO stock_emplacements 
                    (lot_id, site_stockage, emplacement_stockage, nombre_unites, 
                     type_conditionnement, poids_total_kg, type_stock, statut_lavage, 
                     calibre_min, calibre_max, lavage_job_id, is_active)
                    VALUES (%s, %s, %s, %s, %s, %s, 'GRENAILLES', 'GRENAILLES_BRUTES', %s, %s, %s, TRUE)
                """, (lf_lot_id, site_dest, emplacement_dest, lf_pallox_gren, 
                      type_cond_gren, lf_poids_gren, 
                      int(calibre_min_gren), int(calibre_max_gren), job_id))
            
            # 6d. Déduire du stock source
            nouveau_nb = int(stock_source['nombre_unites']) - lf_qty_brut
            nouveau_poids = float(stock_source['poids_total_kg']) - lf_poids_brut
            if nouveau_nb <= 0:
                cursor.execute("""
                    UPDATE stock_emplacements
                    SET nombre_unites = 0, poids_total_kg = 0, is_active = FALSE
                    WHERE id = %s
                """, (stock_source['id'],))
            else:
                cursor.execute("""
                    UPDATE stock_emplacements
                    SET nombre_unites = %s, poids_total_kg = %s
                    WHERE id = %s
                """, (nouveau_nb, max(nouveau_poids, 0), stock_source['id']))
            
            # 6e. Mouvement réduction source
            cursor.execute("""
                INSERT INTO stock_mouvements 
                (lot_id, type_mouvement, site_origine, emplacement_origine,
                 quantite, type_conditionnement, poids_kg, user_action, notes, created_by)
                VALUES (%s, %s, %s, %s, %s, 'Pallox', %s, %s, %s, %s)
            """, (lf_lot_id, type_mvt_source,
                  stock_source['site_stockage'], stock_source['emplacement_stockage'],
                  lf_qty_brut, lf_poids_brut, terminated_by,
                  f"Job #{job_id} - Sortie lavage (lot {i+1}/{len(lots_fille)})", terminated_by))
            
            # 6f. Mouvement création sortie (LAVÉ ou GRENAILLES_LAVÉES)
            if lf_pallox_lave > 0:
                cursor.execute("""
                    INSERT INTO stock_mouvements 
                    (lot_id, type_mouvement, site_destination, emplacement_destination,
                     quantite, type_conditionnement, poids_kg, user_action, notes, created_by)
                    VALUES (%s, %s, %s, %s, %s, 'Pallox', %s, %s, %s, %s)
                """, (lf_lot_id, type_mvt_sortie, site_dest, emplacement_dest,
                      lf_pallox_lave, lf_poids_lave, terminated_by,
                      f"Job #{job_id} - Entrée {statut_sortie} (lot {i+1}/{len(lots_fille)})",
                      terminated_by))
            
            # 6g. Mouvement GRENAILLES_BRUTES (si source BRUT)
            if not is_grenailles_source and lf_pallox_gren > 0:
                cursor.execute("""
                    INSERT INTO stock_mouvements 
                    (lot_id, type_mouvement, site_destination, emplacement_destination,
                     quantite, type_conditionnement, poids_kg, user_action, notes, created_by)
                    VALUES (%s, 'LAVAGE_CREATION_GRENAILLES', %s, %s, %s, 'Pallox', %s, %s, %s, %s)
                """, (lf_lot_id, site_dest, emplacement_dest, lf_pallox_gren, 
                      lf_poids_gren, terminated_by,
                      f"Job #{job_id} - Entrée grenailles brutes (lot {i+1}/{len(lots_fille)})",
                      terminated_by))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        temps_str = f"{temps_reel_minutes // 60}h{temps_reel_minutes % 60:02d}" if temps_reel_minutes else "N/A"
        nb_lots_str = f" ({len(lots_fille)} lots)" if is_multi_lot else ""
        if is_grenailles_source:
            return True, f"✅ Terminé{nb_lots_str} ! Temps: {temps_str} - Rendement: {rendement:.1f}% - Stock GRENAILLES_LAVÉES créé"
        else:
            return True, f"✅ Terminé{nb_lots_str} ! Temps: {temps_str} - Rendement: {rendement:.1f}% - Stock LAVÉ créé"
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
    """Récupère les emplacements disponibles pour créer un job
    
    IMPORTANT: 
    - Filtre sur lots_bruts.is_active = TRUE
    - Calcule les réservations PAR EMPLACEMENT (pas par lot)
    - Inclut BRUT et GRENAILLES_BRUTES (peuvent être lavés)
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT 
                l.id as lot_id, 
                l.code_lot_interne, 
                l.nom_usage,
                l.code_producteur,
                COALESCE(p.nom, l.code_producteur) as producteur,
                l.calibre_min, 
                l.calibre_max,
                COALESCE(v.nom_variete, l.code_variete) as variete,
                se.id as emplacement_id, 
                se.site_stockage, 
                se.emplacement_stockage,
                se.statut_lavage,
                se.nombre_unites as stock_total,
                COALESCE(jobs_reserves.pallox_reserves, 0) as pallox_reserves,
                se.nombre_unites - COALESCE(jobs_reserves.pallox_reserves, 0) as nombre_unites,
                se.poids_total_kg - COALESCE(jobs_reserves.poids_reserve, 0) as poids_total_kg,
                se.type_conditionnement,
                STRING_AGG(DISTINCT pc.marque || ' ' || pc.libelle, ', ') as produits_affectes
            FROM lots_bruts l
            JOIN stock_emplacements se ON l.id = se.lot_id
            LEFT JOIN ref_varietes v ON l.code_variete = v.code_variete
            LEFT JOIN ref_producteurs p ON l.code_producteur = p.code_producteur
            LEFT JOIN previsions_affectations pa ON pa.lot_id = l.id
                AND pa.is_active = TRUE AND pa.statut_stock = 'BRUT'
            LEFT JOIN ref_produits_commerciaux pc ON pa.code_produit_commercial = pc.code_produit
            LEFT JOIN (
                SELECT emplacement_id,
                       SUM(quantite_pallox) as pallox_reserves,
                       SUM(poids_brut_kg) as poids_reserve
                FROM lavages_jobs
                WHERE statut IN ('PRÉVU', 'EN_COURS')
                  AND emplacement_id IS NOT NULL
                GROUP BY emplacement_id
            ) jobs_reserves ON se.id = jobs_reserves.emplacement_id
            WHERE l.is_active = TRUE
              AND se.is_active = TRUE 
              AND se.statut_lavage IN ('BRUT', 'GRENAILLES_BRUTES')
              AND (se.nombre_unites - COALESCE(jobs_reserves.pallox_reserves, 0)) > 0
            GROUP BY l.id, l.code_lot_interne, l.nom_usage, l.code_producteur,
                p.nom, l.calibre_min, l.calibre_max, v.nom_variete, l.code_variete,
                se.id, se.site_stockage, se.emplacement_stockage, se.statut_lavage,
                se.nombre_unites, jobs_reserves.pallox_reserves,
                se.poids_total_kg, jobs_reserves.poids_reserve, se.type_conditionnement
            ORDER BY l.code_lot_interne, se.site_stockage, se.emplacement_stockage
        """)
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        if rows:
            df = pd.DataFrame([dict(r) for r in rows])
            for col in ['nombre_unites', 'poids_total_kg', 'calibre_min', 'calibre_max', 'stock_total', 'pallox_reserves']:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
            return df
        return pd.DataFrame()
    except Exception as e:
        st.error(f"❌ Erreur get_lots_bruts_disponibles : {str(e)}")
        return pd.DataFrame()


def get_recap_produits_lavage():
    """
    Récapitulatif besoin de lavage par produit commercial.
    Pour chaque produit ayant des affectations BRUT :
    - Besoin NET    = SUM(affectations poids_net_estime) des lots BRUT
    - Stock LAVÉ    = stock LAVÉ existant sur les lots concernés
    - Jobs prévus   = tonnage brut jobs PRÉVU/EN_COURS × 78% (équiv NET)
    - Écart         = Besoin NET - Stock LAVÉ - Jobs prévus (>0 = manque)
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            WITH affectations_par_produit AS (
                SELECT
                    pa.code_produit_commercial,
                    pc.marque,
                    pc.libelle,
                    pc.marque || ' ' || pc.libelle as produit_label,
                    pa.lot_id,
                    SUM(pa.poids_net_estime_tonnes) as affecte_net_tonnes
                FROM previsions_affectations pa
                JOIN ref_produits_commerciaux pc ON pa.code_produit_commercial = pc.code_produit
                WHERE pa.is_active = TRUE
                  AND pa.statut_stock = 'BRUT'
                GROUP BY pa.code_produit_commercial, pc.marque, pc.libelle, pa.lot_id
            ),
            stock_lave_par_lot AS (
                SELECT lot_id, SUM(poids_total_kg) / 1000 as stock_lave_tonnes
                FROM stock_emplacements
                WHERE is_active = TRUE AND statut_lavage = 'LAVÉ' AND nombre_unites > 0
                GROUP BY lot_id
            ),
            jobs_par_lot AS (
                SELECT lot_id, SUM(poids_brut_kg) / 1000 * 0.78 as jobs_net_estime
                FROM lavages_jobs
                WHERE statut IN ('PRÉVU', 'EN_COURS')
                GROUP BY lot_id
            )
            SELECT
                app.code_produit_commercial,
                app.produit_label,
                SUM(app.affecte_net_tonnes) as affecte_net_tonnes,
                SUM(COALESCE(sl.stock_lave_tonnes, 0)) as stock_lave_tonnes,
                SUM(COALESCE(jp.jobs_net_estime, 0)) as jobs_net_estime,
                GREATEST(
                    SUM(app.affecte_net_tonnes)
                    - SUM(COALESCE(sl.stock_lave_tonnes, 0))
                    - SUM(COALESCE(jp.jobs_net_estime, 0)),
                    0
                ) as besoin_restant_tonnes
            FROM affectations_par_produit app
            LEFT JOIN stock_lave_par_lot sl ON app.lot_id = sl.lot_id
            LEFT JOIN jobs_par_lot jp ON app.lot_id = jp.lot_id
            GROUP BY app.code_produit_commercial, app.produit_label
            ORDER BY besoin_restant_tonnes DESC, app.produit_label
        """)
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        if rows:
            df = pd.DataFrame([dict(r) for r in rows])
            for col in ['affecte_net_tonnes', 'stock_lave_tonnes', 'jobs_net_estime', 'besoin_restant_tonnes']:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
            return df
        return pd.DataFrame()
    except Exception as e:
        st.error(f"❌ Erreur récap produits : {str(e)}")
        return pd.DataFrame()

def get_besoins_lavage_affectations():
    """
    Récupère les besoins de lavage basés sur les affectations
    
    Pour chaque lot avec affectations BRUT :
    - Affecté BRUT = somme des affectations BRUT (tonnes brut)
    - Stock LAVÉ = stock déjà lavé disponible (tonnes)
    - Besoin lavage = Affecté BRUT - Stock LAVÉ (si > 0)
    - Stock BRUT dispo = stock BRUT disponible pour jobs
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        query = """
        WITH affectations_brut AS (
            -- Affectations BRUT par lot
            SELECT 
                pa.lot_id,
                SUM(pa.quantite_affectee_tonnes) as affecte_brut_tonnes,
                SUM(pa.poids_net_estime_tonnes) as affecte_net_tonnes,
                STRING_AGG(DISTINCT pc.marque || ' ' || pc.libelle, ', ') as produits_liste,
                COUNT(DISTINCT pa.code_produit_commercial) as nb_produits
            FROM previsions_affectations pa
            LEFT JOIN ref_produits_commerciaux pc ON pa.code_produit_commercial = pc.code_produit
            WHERE pa.is_active = TRUE 
              AND pa.statut_stock = 'BRUT'
            GROUP BY pa.lot_id
        ),
        stock_lave AS (
            -- Stock LAVÉ disponible par lot
            SELECT 
                se.lot_id,
                SUM(se.poids_total_kg) / 1000 as stock_lave_tonnes,
                SUM(se.nombre_unites) as pallox_laves
            FROM stock_emplacements se
            WHERE se.is_active = TRUE
              AND se.statut_lavage = 'LAVÉ'
              AND se.nombre_unites > 0
            GROUP BY se.lot_id
        ),
        stock_brut AS (
            -- Stock BRUT disponible par lot (moins jobs réservés)
            SELECT 
                se.lot_id,
                SUM(se.nombre_unites - COALESCE(jobs.pallox_reserves, 0)) as pallox_brut_dispo,
                SUM(se.poids_total_kg - COALESCE(jobs.poids_reserve, 0)) / 1000 as brut_dispo_tonnes
            FROM stock_emplacements se
            LEFT JOIN (
                SELECT emplacement_id,
                       SUM(quantite_pallox) as pallox_reserves,
                       SUM(poids_brut_kg) as poids_reserve
                FROM lavages_jobs
                WHERE statut IN ('PRÉVU', 'EN_COURS')
                  AND emplacement_id IS NOT NULL
                GROUP BY emplacement_id
            ) jobs ON se.id = jobs.emplacement_id
            WHERE se.is_active = TRUE
              AND se.statut_lavage IN ('BRUT', 'GRENAILLES_BRUTES')
              AND (se.nombre_unites - COALESCE(jobs.pallox_reserves, 0)) > 0
            GROUP BY se.lot_id
        ),
        jobs_deja_crees AS (
            -- Jobs déjà créés par lot (PRÉVU ou EN_COURS)
            SELECT 
                lot_id,
                SUM(poids_brut_kg) / 1000 as jobs_prevus_tonnes,
                SUM(quantite_pallox) as jobs_prevus_pallox
            FROM lavages_jobs
            WHERE statut IN ('PRÉVU', 'EN_COURS')
            GROUP BY lot_id
        )
        SELECT 
            l.id as lot_id,
            l.code_lot_interne,
            l.nom_usage,
            l.code_producteur,
            COALESCE(p.nom, l.code_producteur) as producteur,
            COALESCE(v.nom_variete, l.code_variete) as variete,
            
            -- Affectations
            COALESCE(ab.affecte_brut_tonnes, 0) as affecte_brut_tonnes,
            COALESCE(ab.affecte_net_tonnes, 0) as affecte_net_tonnes,
            ab.produits_liste,
            COALESCE(ab.nb_produits, 0) as nb_produits,
            
            -- Stock LAVÉ existant
            COALESCE(sl.stock_lave_tonnes, 0) as stock_lave_tonnes,
            
            -- Stock BRUT disponible
            COALESCE(sb.pallox_brut_dispo, 0) as pallox_brut_dispo,
            COALESCE(sb.brut_dispo_tonnes, 0) as brut_dispo_tonnes,
            
            -- Jobs déjà créés
            COALESCE(jc.jobs_prevus_tonnes, 0) as jobs_prevus_tonnes,
            COALESCE(jc.jobs_prevus_pallox, 0) as jobs_prevus_pallox,
            
            -- Calcul besoin net de lavage
            -- Besoin = (Affecté NET - Stock LAVÉ - Jobs déjà prévus en équivalent net)
            -- Si < 0, pas de besoin
            GREATEST(
                COALESCE(ab.affecte_net_tonnes, 0) 
                - COALESCE(sl.stock_lave_tonnes, 0)
                - COALESCE(jc.jobs_prevus_tonnes, 0) * 0.78,  -- 78% rendement moyen
                0
            ) as besoin_lavage_net_tonnes
            
        FROM affectations_brut ab
        JOIN lots_bruts l ON ab.lot_id = l.id
        LEFT JOIN ref_varietes v ON l.code_variete = v.code_variete
        LEFT JOIN ref_producteurs p ON l.code_producteur = p.code_producteur
        LEFT JOIN stock_lave sl ON l.id = sl.lot_id
        LEFT JOIN stock_brut sb ON l.id = sb.lot_id
        LEFT JOIN jobs_deja_crees jc ON l.id = jc.lot_id
        WHERE l.is_active = TRUE
        ORDER BY 
            GREATEST(COALESCE(ab.affecte_net_tonnes, 0) - COALESCE(sl.stock_lave_tonnes, 0), 0) DESC,
            l.code_lot_interne
        """
        
        cursor.execute(query)
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        
        if rows:
            df = pd.DataFrame(rows)
            
            # Conversions numériques
            numeric_cols = ['affecte_brut_tonnes', 'affecte_net_tonnes', 'stock_lave_tonnes', 
                           'pallox_brut_dispo', 'brut_dispo_tonnes', 'jobs_prevus_tonnes', 
                           'jobs_prevus_pallox', 'besoin_lavage_net_tonnes', 'nb_produits']
            for col in numeric_cols:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
            
            # Filtrer lots avec un besoin > 0
            df = df[df['besoin_lavage_net_tonnes'] > 0.1]  # Seuil minimal 100 kg
            
            return df
        return pd.DataFrame()
        
    except Exception as e:
        st.error(f"❌ Erreur get_besoins_lavage_affectations : {str(e)}")
        return pd.DataFrame()


def get_etiquettes_historiques(type_etiquette):
    """Récupère la liste DISTINCT des étiquettes déjà saisies dans lavages_jobs.

    type_etiquette : 'grenailles' ou 'pallox'
    Retourne : liste de strings, triée par dernière utilisation décroissante.
    Les NULL et chaînes vides sont exclus. Limité à 100 entrées pour l'autocomplete.
    """
    if type_etiquette not in ('grenailles', 'pallox'):
        return []
    col = 'etiquette_grenailles' if type_etiquette == 'grenailles' else 'etiquette_pallox'
    try:
        conn = get_connection()
        cursor = conn.cursor()
        # Valeurs distinctes triées par dernière utilisation (id du dernier job qui l'a utilisée)
        cursor.execute(f"""
            SELECT {col} as etiq, MAX(id) as last_id
            FROM lavages_jobs
            WHERE {col} IS NOT NULL AND TRIM({col}) <> ''
            GROUP BY {col}
            ORDER BY last_id DESC
            LIMIT 100
        """)
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        return [r['etiq'] for r in rows]
    except Exception:
        return []


def _calculer_bornes_calibre(calibre_seuil):
    """Calcule les 4 bornes calibre_min/max_lave/gren à partir du seuil unique.

    Règle métier (validée Julien 2026-05) :
      - Borne haute fixée à 70
      - Grenailles : 0 → seuil
      - Lavé       : seuil → 70

    Si seuil est None : retourne (None, None, None, None) → comportement legacy
    (colonnes restent NULL, terminer_job utilise ce qui est saisi à la fin).

    Retourne : (calibre_min_lave, calibre_max_lave, calibre_min_gren, calibre_max_gren)
    """
    if calibre_seuil is None:
        return (None, None, None, None)
    s = int(calibre_seuil)
    return (s, 70, 0, s)


# ============================================================
# SUIVI EN COURS DE LAVAGE (Feature suivi temps réel + opérateur)
# Table : lavages_jobs_suivis
# ============================================================

def ajouter_suivi_pallox(job_id, type_sortie, nb_pallox, type_conditionnement,
                         poids_kg, operateur, notes=None):
    """Enregistre un suivi pallox saisi pendant le lavage en cours.

    type_sortie : 'LAVÉ' / 'GRENAILLES' / 'DÉCHETS' (contrainte BDD).
    nb_pallox   : 1 pour tap unitaire, N pour saisie groupée.
    operateur   : prénom (texte libre, alimente l'autocomplete au fil du temps).

    Vérifie que le job est bien EN_COURS avant l'INSERT.
    Retourne (ok, message).
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Vérification : le job doit être EN_COURS
        cursor.execute("SELECT statut FROM lavages_jobs WHERE id = %s", (int(job_id),))
        result = cursor.fetchone()
        if not result:
            return False, "❌ Job introuvable"
        if result['statut'] != 'EN_COURS':
            return False, f"❌ Saisie impossible : job {result['statut']} (doit être EN_COURS)"

        # Validation valeurs
        if type_sortie not in ('LAVÉ', 'GRENAILLES', 'DÉCHETS'):
            return False, f"❌ Type sortie invalide : {type_sortie}"
        nb_pallox = int(nb_pallox)
        if nb_pallox <= 0:
            return False, "❌ Nb pallox doit être > 0"
        poids_kg = float(poids_kg)
        if poids_kg < 0:
            return False, "❌ Poids négatif interdit"

        created_by = st.session_state.get('username', 'system')

        cursor.execute("""
            INSERT INTO lavages_jobs_suivis (
                job_id, type_sortie, nb_pallox, type_conditionnement,
                poids_kg, operateur, created_by, notes
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (int(job_id), type_sortie, nb_pallox, type_conditionnement,
              poids_kg, operateur, created_by, notes))
        suivi_id = int(cursor.fetchone()['id'])
        conn.commit()
        cursor.close()
        conn.close()

        # Message contextuel selon mono vs groupé
        if nb_pallox == 1:
            return True, f"✅ +1 pallox {type_sortie} ({poids_kg:.0f} kg)"
        else:
            return True, f"✅ +{nb_pallox} pallox {type_sortie} ({poids_kg:.0f} kg)"
    except Exception as e:
        if 'conn' in locals():
            conn.rollback()
        return False, f"❌ Erreur : {str(e)}"


def get_suivis_job(job_id):
    """Liste détaillée des suivis d'un job, triée du plus récent au plus ancien.

    Utile pour afficher l'historique sur la card + permettre la suppression
    d'une saisie erronée.

    Retourne une liste de dicts.
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, job_id, type_sortie, nb_pallox, type_conditionnement,
                   poids_kg, operateur, created_at, created_by, notes
            FROM lavages_jobs_suivis
            WHERE job_id = %s
            ORDER BY created_at DESC, id DESC
        """, (int(job_id),))
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        return [dict(r) for r in rows]
    except Exception:
        return []


def get_agregats_suivis_job(job_id):
    """Agrégats par type de sortie pour un job : nb_pallox + poids_kg total.

    Retourne un dict de la forme :
      {
        'LAVÉ':        {'nb_pallox': int, 'poids_kg': float},
        'GRENAILLES':  {'nb_pallox': int, 'poids_kg': float},
        'DÉCHETS':     {'nb_pallox': int, 'poids_kg': float},
        'operateur_dernier': str|None,  -- dernier opérateur ayant saisi (= "actuel")
        'nb_total_saisies': int,
      }

    Si aucun suivi : tous les compteurs sont à 0.
    """
    base = {
        'LAVÉ': {'nb_pallox': 0, 'poids_kg': 0.0},
        'GRENAILLES': {'nb_pallox': 0, 'poids_kg': 0.0},
        'DÉCHETS': {'nb_pallox': 0, 'poids_kg': 0.0},
        'operateur_dernier': None,
        'nb_total_saisies': 0,
    }
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT type_sortie,
                   SUM(nb_pallox) as nb_pallox,
                   SUM(poids_kg)  as poids_kg
            FROM lavages_jobs_suivis
            WHERE job_id = %s
            GROUP BY type_sortie
        """, (int(job_id),))
        for r in cursor.fetchall():
            t = r['type_sortie']
            if t in base:
                base[t]['nb_pallox'] = int(r['nb_pallox']) if r['nb_pallox'] else 0
                base[t]['poids_kg']  = float(r['poids_kg']) if r['poids_kg'] else 0.0

        # Dernier opérateur (= opérateur "actuel")
        cursor.execute("""
            SELECT operateur, COUNT(*) as nb
            FROM lavages_jobs_suivis
            WHERE job_id = %s
            GROUP BY operateur
        """, (int(job_id),))
        # Total saisies
        cursor.execute("""
            SELECT COUNT(*) as nb FROM lavages_jobs_suivis WHERE job_id = %s
        """, (int(job_id),))
        base['nb_total_saisies'] = int(cursor.fetchone()['nb'])

        # Le dernier opérateur ayant saisi
        cursor.execute("""
            SELECT operateur
            FROM lavages_jobs_suivis
            WHERE job_id = %s AND operateur IS NOT NULL AND TRIM(operateur) <> ''
            ORDER BY created_at DESC, id DESC
            LIMIT 1
        """, (int(job_id),))
        last_op = cursor.fetchone()
        if last_op:
            base['operateur_dernier'] = last_op['operateur']

        cursor.close()
        conn.close()
        return base
    except Exception:
        return base


def get_operateurs_historiques():
    """Liste DISTINCT des opérateurs déjà saisis dans lavages_jobs_suivis.

    Triée par fréquence (les plus utilisés en premier).
    Utile pour l'autocomplete dans le sélecteur opérateur.
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT operateur, COUNT(*) as nb
            FROM lavages_jobs_suivis
            WHERE operateur IS NOT NULL AND TRIM(operateur) <> ''
            GROUP BY operateur
            ORDER BY nb DESC, operateur ASC
            LIMIT 100
        """)
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        return [r['operateur'] for r in rows]
    except Exception:
        return []


def supprimer_suivi_pallox(suivi_id):
    """Supprime une saisie de suivi (correction d'erreur opérateur)."""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT job_id FROM lavages_jobs_suivis WHERE id = %s", (int(suivi_id),))
        result = cursor.fetchone()
        if not result:
            return False, "❌ Suivi introuvable"
        cursor.execute("DELETE FROM lavages_jobs_suivis WHERE id = %s", (int(suivi_id),))
        conn.commit()
        cursor.close()
        conn.close()
        return True, "✅ Saisie supprimée"
    except Exception as e:
        if 'conn' in locals():
            conn.rollback()
        return False, f"❌ Erreur : {str(e)}"


def ui_saisie_infos_metier_lavage(key_prefix):
    """Widget réutilisable pour saisir les 5 infos métier d'un job de lavage à la création.

    Champs collectés (tous obligatoires côté UI) :
      - type_tapis           : 'I' / 'E' / 'direct'
      - etiquette_grenailles : selectbox historique + option "➕ Nouvelle"
      - etiquette_pallox     : idem
      - calibre_seuil        : entier 1-69 (seuil de séparation gren/lavé)

    key_prefix : str unique pour préfixer les clés des widgets (ex : 'besoins', 'lots_brut').
                 Permet d'instancier ce bloc plusieurs fois sur la même page.

    Retourne : dict {
        'type_tapis': str|None,
        'etiquette_grenailles': str|None,
        'etiquette_pallox': str|None,
        'calibre_seuil': int|None,
        'is_valid': bool,        # True si les 4 champs sont remplis correctement
        'erreurs': list[str]     # liste des erreurs (vide si is_valid)
    }
    """
    st.markdown("##### 🏷️ Infos lavage (obligatoires)")
    
    col_t, col_c = st.columns([1, 1])
    
    with col_t:
        # Type tapis
        TAPIS_OPTS = ["-- Choisir --", "I", "E", "direct"]
        type_tapis_sel = st.selectbox(
            "🎢 Type de tapis *",
            TAPIS_OPTS,
            key=f"tapis_{key_prefix}",
        )
        type_tapis = None if type_tapis_sel == "-- Choisir --" else type_tapis_sel
    
    with col_c:
        # Calibre seuil
        cal_seuil = st.number_input(
            "📏 Calibre seuil (mm) *",
            min_value=0, max_value=69, value=0, step=1,
            key=f"calseuil_{key_prefix}",
            help="Seuil entre grenailles et lavé. Ex : 35 → grenailles 0-35, lavé 35-70."
        )
        calibre_seuil = int(cal_seuil) if cal_seuil > 0 else None
        if calibre_seuil is not None:
            st.caption(f"→ Grenailles : 0-{calibre_seuil} mm | Lavé : {calibre_seuil}-70 mm")
    
    # Étiquette grenailles : selectbox historique + "➕ Nouvelle"
    col_eg, col_ep = st.columns([1, 1])
    
    with col_eg:
        hist_gren = get_etiquettes_historiques('grenailles')
        opts_gren = ["-- Choisir --", "➕ Nouvelle étiquette..."] + hist_gren
        sel_gren = st.selectbox(
            "🏷️ Étiquette grenailles *",
            opts_gren,
            key=f"etiq_gren_sel_{key_prefix}",
        )
        if sel_gren == "➕ Nouvelle étiquette...":
            etiquette_grenailles = st.text_input(
                "Nouvelle étiquette grenailles",
                key=f"etiq_gren_new_{key_prefix}",
                placeholder="Ex : A123, GREN-2026-01..."
            ).strip() or None
        elif sel_gren == "-- Choisir --":
            etiquette_grenailles = None
        else:
            etiquette_grenailles = sel_gren
    
    with col_ep:
        hist_pal = get_etiquettes_historiques('pallox')
        opts_pal = ["-- Choisir --", "➕ Nouvelle étiquette..."] + hist_pal
        sel_pal = st.selectbox(
            "🏷️ Étiquette pallox *",
            opts_pal,
            key=f"etiq_pal_sel_{key_prefix}",
        )
        if sel_pal == "➕ Nouvelle étiquette...":
            etiquette_pallox = st.text_input(
                "Nouvelle étiquette pallox",
                key=f"etiq_pal_new_{key_prefix}",
                placeholder="Ex : B456, PAL-2026-01..."
            ).strip() or None
        elif sel_pal == "-- Choisir --":
            etiquette_pallox = None
        else:
            etiquette_pallox = sel_pal
    
    # Validation
    erreurs = []
    if not type_tapis:
        erreurs.append("Type de tapis")
    if not etiquette_grenailles:
        erreurs.append("Étiquette grenailles")
    if not etiquette_pallox:
        erreurs.append("Étiquette pallox")
    if calibre_seuil is None:
        erreurs.append("Calibre seuil")
    
    is_valid = len(erreurs) == 0
    
    if not is_valid:
        st.caption(f"⚠️ Champ(s) manquant(s) : {', '.join(erreurs)}")
    
    return {
        'type_tapis': type_tapis,
        'etiquette_grenailles': etiquette_grenailles,
        'etiquette_pallox': etiquette_pallox,
        'calibre_seuil': calibre_seuil,
        'is_valid': is_valid,
        'erreurs': erreurs,
    }


def create_job_lavage(lot_id, emplacement_id, quantite_pallox, poids_brut_kg, 
                     date_prevue, ligne_lavage, capacite_th, notes="",
                     type_tapis=None, etiquette_grenailles=None,
                     etiquette_pallox=None, calibre_seuil=None):
    """Crée un nouveau job de lavage MONO-LOT
    
    Schéma multi-lot (Commit 1) :
      - INSERT 1 ligne dans lavages_jobs (is_multi_lot=FALSE, nb_lots=1)
      - INSERT 1 ligne fille dans lavages_jobs_lots
    
    Vérifie que le stock disponible PAR EMPLACEMENT est suffisant
    Enregistre emplacement_id et statut_source
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()
        lot_id = int(lot_id)
        emplacement_id = int(emplacement_id)
        quantite_pallox = int(quantite_pallox)
        poids_brut_kg = float(poids_brut_kg)
        capacite_th = float(capacite_th)
        
        # ============================================================
        # VÉRIFICATION : Stock disponible PAR EMPLACEMENT suffisant ?
        # Réservations : soit via lavages_jobs (legacy mono-lot)
        # soit via lavages_jobs_lots (nouveau multi-lot)
        # ============================================================
        cursor.execute("""
            SELECT 
                se.nombre_unites as stock_total,
                se.statut_lavage,
                COALESCE(jobs.pallox_reserves, 0) as pallox_reserves,
                se.nombre_unites - COALESCE(jobs.pallox_reserves, 0) as stock_disponible
            FROM stock_emplacements se
            LEFT JOIN (
                -- Réservations issues des jobs mono-lot ET multi-lot
                -- Pour mono-lot : on lit lavages_jobs.quantite_pallox + emplacement_id
                -- Pour multi-lot : lavages_jobs_lots.quantite_pallox + emplacement_id
                SELECT emplacement_id, SUM(quantite_pallox) as pallox_reserves
                FROM (
                    -- Jobs mono-lot
                    SELECT lj.emplacement_id, lj.quantite_pallox
                    FROM lavages_jobs lj
                    WHERE lj.statut IN ('PRÉVU', 'EN_COURS')
                      AND lj.emplacement_id IS NOT NULL
                      AND COALESCE(lj.is_multi_lot, FALSE) = FALSE
                    UNION ALL
                    -- Jobs multi-lot (lecture via table fille)
                    SELECT ljl.emplacement_id, ljl.quantite_pallox
                    FROM lavages_jobs_lots ljl
                    JOIN lavages_jobs lj ON ljl.job_id = lj.id
                    WHERE lj.statut IN ('PRÉVU', 'EN_COURS')
                      AND lj.is_multi_lot = TRUE
                ) AS all_reservations
                GROUP BY emplacement_id
            ) jobs ON se.id = jobs.emplacement_id
            WHERE se.id = %s
        """, (emplacement_id,))
        stock_info = cursor.fetchone()
        
        if not stock_info:
            return False, "❌ Emplacement introuvable"
        
        stock_disponible = int(stock_info['stock_disponible']) if stock_info['stock_disponible'] else int(stock_info['stock_total'])
        if quantite_pallox > stock_disponible:
            return False, f"❌ Stock insuffisant : {quantite_pallox} demandés mais seulement {stock_disponible} disponibles (déjà {int(stock_info['pallox_reserves'])} réservés)"
        
        # Récupérer le statut_source (BRUT ou GRENAILLES_BRUTES)
        statut_source = stock_info['statut_lavage'] or 'BRUT'
        
        # Récupérer infos lot + producteur (utilisés pour info dans la fille)
        cursor.execute("""
            SELECT 
                l.code_lot_interne, 
                COALESCE(v.nom_variete, l.code_variete) as variete,
                COALESCE(p.nom, l.code_producteur) as producteur
            FROM lots_bruts l
            LEFT JOIN ref_varietes v ON l.code_variete = v.code_variete
            LEFT JOIN ref_producteurs p ON l.code_producteur = p.code_producteur
            WHERE l.id = %s
        """, (lot_id,))
        lot_info = cursor.fetchone()
        if not lot_info:
            return False, f"❌ Lot {lot_id} introuvable"
        
        # Récupérer type_conditionnement + calibres depuis stock_emplacements
        cursor.execute("""
            SELECT type_conditionnement, calibre_min, calibre_max
            FROM stock_emplacements
            WHERE id = %s
        """, (emplacement_id,))
        emp_info = cursor.fetchone()
        type_cond = emp_info.get('type_conditionnement') if emp_info else None
        calibre_min = emp_info.get('calibre_min') if emp_info else None
        calibre_max = emp_info.get('calibre_max') if emp_info else None
        
        temps_estime = (poids_brut_kg / 1000) / capacite_th
        created_by = st.session_state.get('username', 'system')
        
        # Note : calibre_seuil suffit pour stocker la règle de calibre de sortie.
        # Les 4 bornes (min/max lave/gren) sont recalculées côté Python via
        # _calculer_bornes_calibre() au moment où terminer_job en a besoin.
        
        # INSERT lavages_jobs (1 ligne parent mono-lot)
        cursor.execute("""
            INSERT INTO lavages_jobs (
                lot_id, emplacement_id, code_lot_interne, variete, quantite_pallox, poids_brut_kg,
                date_prevue, ligne_lavage, capacite_th, temps_estime_heures,
                statut, statut_source, is_multi_lot, nb_lots, created_by, notes,
                type_tapis, etiquette_grenailles, etiquette_pallox, calibre_seuil
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'PRÉVU', %s,
                      FALSE, 1, %s, %s,
                      %s, %s, %s, %s)
            RETURNING id
        """, (lot_id, emplacement_id, lot_info['code_lot_interne'], lot_info['variete'],
              quantite_pallox, poids_brut_kg, date_prevue, ligne_lavage,
              capacite_th, temps_estime, statut_source, created_by, notes,
              type_tapis, etiquette_grenailles, etiquette_pallox, calibre_seuil))
        job_id = int(cursor.fetchone()['id'])
        
        # INSERT lavages_jobs_lots (1 ligne fille)
        cursor.execute("""
            INSERT INTO lavages_jobs_lots (
                job_id, lot_id, emplacement_id, code_lot_interne, variete, producteur,
                quantite_pallox, poids_brut_kg, type_conditionnement, calibre_min, calibre_max,
                ordre
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 1)
        """, (job_id, lot_id, emplacement_id, lot_info['code_lot_interne'],
              lot_info['variete'], lot_info.get('producteur'),
              quantite_pallox, poids_brut_kg, type_cond, calibre_min, calibre_max))
        
        conn.commit()
        cursor.close()
        conn.close()
        return True, f"✅ Job #{job_id} créé"
    except Exception as e:
        if 'conn' in locals():
            conn.rollback()
        return False, f"❌ Erreur : {str(e)}"

def create_batch_jobs(lots_selection, date_prevue, ligne_lavage, cadence, notes="",
                     type_tapis=None, etiquette_grenailles=None,
                     etiquette_pallox=None, calibre_seuil=None):
    """
    Crée UN SEUL job multi-lot avec N lignes filles dans lavages_jobs_lots.
    
    Schéma multi-lot (Commit 1) :
      - 1 ligne lavages_jobs (is_multi_lot=TRUE, nb_lots=N, lot_id/emplacement_id NULL)
      - N lignes lavages_jobs_lots (le détail par lot source)
      - quantite_pallox et poids_brut_kg sur le parent = SUM des fille
    
    Validations métier :
      Q2 - Toutes les variétés doivent être identiques
      (Calibres min/max et types de conditionnement : MIX AUTORISÉ — chaque lot fille
       conserve ses propres calibres et conditionnement pour la traçabilité)
    
    Infos métier saisies à la création (tous optionnels en signature, obligatoires côté UI) :
      - type_tapis : 'I' / 'E' / 'direct'
      - etiquette_grenailles : texte libre (autocomplete)
      - etiquette_pallox : texte libre (autocomplete)
      - calibre_seuil : entier, seuil de séparation gren/lavé (ex : 35)
                       Stocké sur le parent et propagé en bornes 4 colonnes (borne haute=70).
    
    Si len(lots_selection) == 1 : délègue à create_job_lavage (mono-lot).
    
    lots_selection : liste de dicts avec keys requises :
        lot_id, emplacement_id, quantite_pallox, poids_brut_kg
    Keys optionnelles :
        type_conditionnement : si fourni, écrase la valeur récupérée de stock_emplacements
                               pour la ligne fille (permet à l'UI batch de spécifier
                               un conditionnement différent par lot)
    (Le reste — variete, calibres — est récupéré depuis la BDD)
    
    Retourne : (ok, message, batch_id)
    """
    import uuid
    
    # Délégation mono-lot si 1 seul lot
    if len(lots_selection) < 2:
        return False, "❌ create_batch_jobs requiert au moins 2 lots (utiliser create_job_lavage sinon)", None
    
    batch_id = str(uuid.uuid4())
    
    try:
        conn = get_connection()
        cursor = conn.cursor()
        created_by = st.session_state.get('username', 'system')
        
        # ============================================================
        # 1. ENRICHISSEMENT : récupérer variété + calibres + conditionnement
        #    pour CHAQUE lot depuis la BDD (source de vérité)
        # ============================================================
        enriched = []
        for lot in lots_selection:
            lot_id = int(lot['lot_id'])
            emplacement_id = int(lot['emplacement_id'])
            quantite_pallox = int(lot['quantite_pallox'])
            poids_brut_kg = float(lot['poids_brut_kg'])
            # Override optionnel du type_conditionnement par l'UI
            type_cond_override = lot.get('type_conditionnement')
            
            # Info lot (variété, code, producteur)
            cursor.execute("""
                SELECT 
                    l.code_lot_interne,
                    COALESCE(v.nom_variete, l.code_variete) as variete,
                    COALESCE(p.nom, l.code_producteur) as producteur
                FROM lots_bruts l
                LEFT JOIN ref_varietes v ON l.code_variete = v.code_variete
                LEFT JOIN ref_producteurs p ON l.code_producteur = p.code_producteur
                WHERE l.id = %s
            """, (lot_id,))
            lot_info = cursor.fetchone()
            if not lot_info:
                conn.rollback()
                return False, f"❌ Lot {lot_id} introuvable", None
            
            # Info emplacement (calibres, type_conditionnement, statut_lavage)
            cursor.execute("""
                SELECT type_conditionnement, calibre_min, calibre_max,
                       nombre_unites, statut_lavage
                FROM stock_emplacements
                WHERE id = %s
            """, (emplacement_id,))
            emp_info = cursor.fetchone()
            if not emp_info:
                conn.rollback()
                return False, f"❌ Emplacement {emplacement_id} introuvable", None
            
            # Type cond final = override UI si fourni, sinon valeur stock_emplacements
            type_cond_final = type_cond_override or emp_info.get('type_conditionnement')
            
            enriched.append({
                'lot_id': lot_id,
                'emplacement_id': emplacement_id,
                'quantite_pallox': quantite_pallox,
                'poids_brut_kg': poids_brut_kg,
                'code_lot_interne': lot_info['code_lot_interne'],
                'variete': lot_info['variete'],
                'producteur': lot_info.get('producteur'),
                'type_conditionnement': type_cond_final,
                'calibre_min': emp_info.get('calibre_min'),
                'calibre_max': emp_info.get('calibre_max'),
                'statut_lavage_emp': emp_info.get('statut_lavage'),
                'nombre_unites_emp': emp_info.get('nombre_unites'),
            })
        
        # ============================================================
        # 2. VALIDATION Q2 — 1 seule variété par batch
        # ============================================================
        varietes_distinctes = set(e['variete'] for e in enriched if e['variete'])
        if len(varietes_distinctes) > 1:
            conn.rollback()
            cursor.close()
            conn.close()
            return False, (f"❌ Variétés différentes dans le batch : "
                          f"{', '.join(sorted(varietes_distinctes))}. "
                          f"Un batch doit contenir une seule variété."), None
        
        variete_batch = next(iter(varietes_distinctes)) if varietes_distinctes else None
        
        # ============================================================
        # 3. Calibres + types conditionnement : MIX AUTORISÉ
        # ============================================================
        # Chaque ligne fille (lavages_jobs_lots) conserve ses propres calibre_min,
        # calibre_max et type_conditionnement pour la traçabilité.
        # Aucune validation d'uniformité ici : on accepte que des lots de calibres
        # ou conditionnements différents soient lavés dans le même batch.
        
        # ============================================================
        # 4. VÉRIFICATION STOCK pour chaque emplacement
        # ============================================================
        # On agrège par emplacement_id au cas où 2 lots du batch viennent du même emplacement
        besoin_par_emp = {}
        for e in enriched:
            besoin_par_emp[e['emplacement_id']] = besoin_par_emp.get(e['emplacement_id'], 0) + e['quantite_pallox']
        
        statuts_source = set()
        for emp_id, qty_demandee in besoin_par_emp.items():
            cursor.execute("""
                SELECT 
                    se.nombre_unites as stock_total,
                    se.statut_lavage,
                    COALESCE(jobs.pallox_reserves, 0) as pallox_reserves,
                    se.nombre_unites - COALESCE(jobs.pallox_reserves, 0) as stock_dispo
                FROM stock_emplacements se
                LEFT JOIN (
                    SELECT emplacement_id, SUM(quantite_pallox) as pallox_reserves
                    FROM (
                        SELECT lj.emplacement_id, lj.quantite_pallox
                        FROM lavages_jobs lj
                        WHERE lj.statut IN ('PRÉVU', 'EN_COURS')
                          AND lj.emplacement_id IS NOT NULL
                          AND COALESCE(lj.is_multi_lot, FALSE) = FALSE
                        UNION ALL
                        SELECT ljl.emplacement_id, ljl.quantite_pallox
                        FROM lavages_jobs_lots ljl
                        JOIN lavages_jobs lj ON ljl.job_id = lj.id
                        WHERE lj.statut IN ('PRÉVU', 'EN_COURS')
                          AND lj.is_multi_lot = TRUE
                    ) AS all_res
                    GROUP BY emplacement_id
                ) jobs ON se.id = jobs.emplacement_id
                WHERE se.id = %s
            """, (emp_id,))
            stock_info = cursor.fetchone()
            if not stock_info:
                conn.rollback()
                cursor.close()
                conn.close()
                return False, f"❌ Emplacement {emp_id} introuvable", None
            
            stock_dispo = int(stock_info['stock_dispo']) if stock_info['stock_dispo'] is not None else int(stock_info['stock_total'])
            if qty_demandee > stock_dispo:
                conn.rollback()
                cursor.close()
                conn.close()
                return False, (f"❌ Stock insuffisant emplacement {emp_id} : "
                              f"{qty_demandee} demandés, {stock_dispo} dispo "
                              f"(déjà {int(stock_info['pallox_reserves'])} réservés)"), None
            
            statuts_source.add(stock_info['statut_lavage'] or 'BRUT')
        
        # Statut source : si tous identiques, on prend la valeur. Sinon BRUT par défaut.
        statut_source_batch = next(iter(statuts_source)) if len(statuts_source) == 1 else 'BRUT'
        
        # ============================================================
        # 5. CALCULS AGRÉGATS
        # ============================================================
        capacite_th = float(cadence)
        total_quantite = sum(e['quantite_pallox'] for e in enriched)
        total_poids_kg = sum(e['poids_brut_kg'] for e in enriched)
        temps_estime = (total_poids_kg / 1000) / capacite_th
        nb_lots = len(enriched)
        
        # Note : calibre_seuil suffit. Les 4 bornes sont recalculées par
        # _calculer_bornes_calibre() côté Python quand on en a besoin.
        
        # ============================================================
        # 6. INSERT lavages_jobs (1 seule ligne PARENT multi-lot)
        # ============================================================
        cursor.execute("""
            INSERT INTO lavages_jobs (
                lot_id, emplacement_id, code_lot_interne, variete,
                quantite_pallox, poids_brut_kg,
                date_prevue, ligne_lavage, capacite_th, temps_estime_heures,
                statut, statut_source, is_multi_lot, nb_lots, batch_id,
                created_by, notes,
                type_tapis, etiquette_grenailles, etiquette_pallox, calibre_seuil
            ) VALUES (
                NULL, NULL, NULL, %s,
                %s, %s,
                %s, %s, %s, %s,
                'PRÉVU', %s, TRUE, %s, %s,
                %s, %s,
                %s, %s, %s, %s
            )
            RETURNING id
        """, (variete_batch,
              total_quantite, total_poids_kg,
              date_prevue, ligne_lavage, capacite_th, temps_estime,
              statut_source_batch, nb_lots, batch_id,
              created_by, notes,
              type_tapis, etiquette_grenailles, etiquette_pallox, calibre_seuil))
        job_id = int(cursor.fetchone()['id'])
        
        # ============================================================
        # 7. INSERT lavages_jobs_lots (N lignes FILLES)
        # ============================================================
        for ordre, e in enumerate(enriched, start=1):
            cursor.execute("""
                INSERT INTO lavages_jobs_lots (
                    job_id, lot_id, emplacement_id, code_lot_interne, variete, producteur,
                    quantite_pallox, poids_brut_kg, type_conditionnement,
                    calibre_min, calibre_max, ordre
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (job_id, e['lot_id'], e['emplacement_id'],
                  e['code_lot_interne'], e['variete'], e['producteur'],
                  e['quantite_pallox'], e['poids_brut_kg'], e['type_conditionnement'],
                  e['calibre_min'], e['calibre_max'], ordre))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        total_poids_t = total_poids_kg / 1000
        msg = (f"✅ Job batch #{job_id} créé — {nb_lots} lots — "
               f"{variete_batch} — {total_quantite} pallox — {total_poids_t:.1f} T")
        return True, msg, batch_id
    
    except Exception as e:
        if 'conn' in locals():
            conn.rollback()
            cursor.close()
            conn.close()
        return False, f"❌ Erreur : {str(e)}", None


def supprimer_job(job_id):
    """Supprime un job PRÉVU (suppression complète)"""
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
        # Inclut tous les types possibles : LAVÉ, GRENAILLES_BRUTES, GRENAILLES_LAVÉES
        cursor.execute("""
            DELETE FROM stock_emplacements 
            WHERE lavage_job_id = %s AND statut_lavage IN ('LAVÉ', 'GRENAILLES', 'GRENAILLES_BRUTES', 'GRENAILLES_LAVÉES')
        """, (job_id,))
        
        # ============================================================
        # 2. RESTAURER LE STOCK SOURCE
        # ============================================================
        # Utiliser emplacement_id du job si disponible, sinon chercher par lot_id
        if emplacement_id:
            cursor.execute("""
                SELECT id, nombre_unites, poids_total_kg, is_active, statut_lavage
                FROM stock_emplacements
                WHERE id = %s
            """, (emplacement_id,))
        else:
            # Fallback : chercher le stock source du lot (BRUT ou GRENAILLES_BRUTES selon statut_source)
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

tab1, tab2, tab3, tab4, tab5 = st.tabs(["📅 Planning Semaine", "📋 Liste Jobs", "➕ Créer Job", "🖨️ Imprimer", "⚙️ Admin"])

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
    jobs_a_placer = get_jobs_a_placer(st.session_state.selected_ligne)
    temps_customs = get_temps_customs()
    horaires_config = get_config_horaires()
    planning_df = get_planning_semaine(annee, semaine)
    lignes_dict = {l['code']: float(l['capacite_th']) for l in lignes} if lignes else {'LIGNE_1': 13.0, 'LIGNE_2': 6.0}
    
    # ============================================================
    # ⭐ BLOC SUIVI EN COURS DE LAVAGE PLEINE LARGEUR (avant Terminer)
    # Activation : clic sur le bouton "📊 Suivi" sur une card EN_COURS
    # ============================================================
    job_en_suivi = None
    job_elem_suivi = None
    for key in list(st.session_state.keys()):
        if key.startswith('show_suivi_') and st.session_state.get(key, False):
            try:
                job_id_to_track = int(float(key.replace('show_suivi_', '')))
            except (ValueError, TypeError):
                continue
            if not planning_df.empty:
                jrows = planning_df[(planning_df['job_id'] == job_id_to_track) & (planning_df['type_element'] == 'JOB')]
                if not jrows.empty:
                    job_en_suivi = job_id_to_track
                    job_elem_suivi = jrows.iloc[0]
                    break
    
    if job_en_suivi and job_elem_suivi is not None:
        e_s = job_elem_suivi
        st.markdown("---")
        col_h1, col_h2 = st.columns([5, 1])
        with col_h1:
            st.markdown(f"## 📊 Suivi en cours — Job #{job_en_suivi}")
        with col_h2:
            if st.button("✖ Fermer", key=f"close_suivi_{job_en_suivi}", use_container_width=True):
                st.session_state.pop(f'show_suivi_{job_en_suivi}', None)
                st.rerun()
        
        # Récap entête : variété, lot, quantité prévue
        variete_s  = e_s['variete']           if pd.notna(e_s.get('variete'))           else '-'
        code_lot_s = e_s['code_lot_interne']  if pd.notna(e_s.get('code_lot_interne'))  else '-'
        qty_prev_s = int(e_s['quantite_pallox']) if pd.notna(e_s.get('quantite_pallox')) else 0
        st.info(f"🌱 **{variete_s}** | 📦 Lot: {code_lot_s} | Prévu : **{qty_prev_s} pallox**")
        
        # === 1. Sélecteur opérateur actuel (session_state pour mémorisation locale) ===
        op_hist = get_operateurs_historiques()
        agreg_now = get_agregats_suivis_job(job_en_suivi)
        op_dernier = agreg_now.get('operateur_dernier') or ''
        
        # Clé session pour mémoriser l'opérateur courant du job en saisie
        ss_op_key = f"suivi_op_{job_en_suivi}"
        if ss_op_key not in st.session_state:
            st.session_state[ss_op_key] = op_dernier
        
        st.markdown("### 👷 Opérateur en poste")
        col_op1, col_op2 = st.columns([2, 3])
        with col_op1:
            opts_op = ["-- Choisir --", "➕ Nouvel opérateur..."] + op_hist
            # Préselection : opérateur dernier saisi si présent dans la liste
            try:
                idx_pre = opts_op.index(st.session_state[ss_op_key]) if st.session_state[ss_op_key] in op_hist else 0
            except ValueError:
                idx_pre = 0
            op_sel = st.selectbox(
                "Opérateur",
                opts_op,
                index=idx_pre,
                key=f"op_sel_{job_en_suivi}",
                label_visibility="collapsed",
            )
            if op_sel == "➕ Nouvel opérateur...":
                op_new = st.text_input(
                    "Prénom du nouvel opérateur",
                    key=f"op_new_{job_en_suivi}",
                    placeholder="Ex : Marc, Sophie..."
                ).strip()
                if op_new:
                    st.session_state[ss_op_key] = op_new
            elif op_sel != "-- Choisir --":
                st.session_state[ss_op_key] = op_sel
        with col_op2:
            op_courant = st.session_state.get(ss_op_key, '')
            if op_courant:
                st.success(f"👷 Opérateur courant : **{op_courant}** (sera enregistré sur les prochains pallox)")
            else:
                st.warning("⚠️ Aucun opérateur sélectionné — choisis ou tape un prénom à gauche avant de saisir")
        
        st.markdown("---")
        
        # === 2. Boutons rapides "+1 pallox" ===
        st.markdown("### ➕ Saisie rapide : +1 pallox")
        TYPES_COND_SUIVI = ["Pallox", "Petit Pallox", "Big Bag"]
        POIDS_UNIT_SUIVI = {"Pallox": 1900, "Petit Pallox": 800, "Big Bag": 1600}
        
        # Type cond par défaut = celui du job (lu via planning_df / lot fille si dispo)
        type_cond_defaut_suivi = "Pallox"
        # Tentative de lecture depuis planning_df
        if pd.notna(e_s.get('type_conditionnement')):
            type_cond_defaut_suivi = e_s['type_conditionnement']
        
        col_quick1, col_quick2, col_quick3 = st.columns(3)
        
        for col_q, type_lbl, type_db, default_w in [
            (col_quick1, "✨ LAVÉ",      "LAVÉ",       POIDS_UNIT_SUIVI[type_cond_defaut_suivi]),
            (col_quick2, "🌾 GRENAILLES","GRENAILLES", POIDS_UNIT_SUIVI[type_cond_defaut_suivi]),
            (col_quick3, "🗑️ DÉCHETS",  "DÉCHETS",    POIDS_UNIT_SUIVI[type_cond_defaut_suivi]),
        ]:
            with col_q:
                st.markdown(f"#### {type_lbl}")
                # Type cond modifiable par tap (default : type job)
                tc_key = f"quick_tc_{type_db}_{job_en_suivi}"
                try:
                    tc_idx = TYPES_COND_SUIVI.index(type_cond_defaut_suivi)
                except ValueError:
                    tc_idx = 0
                tc_sel = st.selectbox(
                    "Type cond.",
                    TYPES_COND_SUIVI,
                    index=tc_idx,
                    key=tc_key,
                    label_visibility="collapsed",
                )
                # Poids unitaire pré-rempli depuis type cond
                w_key = f"quick_w_{type_db}_{job_en_suivi}"
                if w_key not in st.session_state:
                    st.session_state[w_key] = float(POIDS_UNIT_SUIVI[tc_sel])
                # Sync : si type cond change, on resette le poids unit
                expected_w = float(POIDS_UNIT_SUIVI[tc_sel])
                # Si la valeur en session est exactement l'ancienne valeur théorique d'un autre type, on resync
                if st.session_state[w_key] not in [float(v) for v in POIDS_UNIT_SUIVI.values()] + [expected_w]:
                    pass  # opérateur a personnalisé : on garde
                poids_quick = st.number_input(
                    "Poids (kg)",
                    min_value=0.0, max_value=5000.0, step=10.0,
                    value=expected_w if st.session_state.get(f"_reset_{w_key}", False) else st.session_state[w_key],
                    key=w_key,
                )
                # Bouton +1
                btn_disabled = not bool(st.session_state.get(ss_op_key, '').strip())
                if st.button(f"➕1 {type_db}", key=f"quick_btn_{type_db}_{job_en_suivi}",
                             type="primary", use_container_width=True, disabled=btn_disabled):
                    ok, msg = ajouter_suivi_pallox(
                        job_id=job_en_suivi,
                        type_sortie=type_db,
                        nb_pallox=1,
                        type_conditionnement=tc_sel,
                        poids_kg=poids_quick,
                        operateur=st.session_state[ss_op_key],
                    )
                    if ok:
                        st.toast(msg, icon="✅")
                        st.rerun()
                    else:
                        st.error(msg)
                if btn_disabled:
                    st.caption("⚠️ Sélectionne un opérateur d'abord")
        
        st.markdown("---")
        
        # === 3. Saisie groupée (expander) ===
        with st.expander("📝 Saisie groupée (rattrapage de plusieurs pallox)"):
            col_g1, col_g2, col_g3, col_g4 = st.columns([1, 1, 1, 1])
            with col_g1:
                grp_type = st.selectbox(
                    "Type sortie",
                    ["LAVÉ", "GRENAILLES", "DÉCHETS"],
                    key=f"grp_type_{job_en_suivi}",
                )
            with col_g2:
                grp_nb = st.number_input(
                    "Nb pallox",
                    min_value=1, max_value=200, value=1, step=1,
                    key=f"grp_nb_{job_en_suivi}",
                )
            with col_g3:
                grp_tc = st.selectbox(
                    "Type cond.",
                    TYPES_COND_SUIVI,
                    index=TYPES_COND_SUIVI.index(type_cond_defaut_suivi) if type_cond_defaut_suivi in TYPES_COND_SUIVI else 0,
                    key=f"grp_tc_{job_en_suivi}",
                )
            with col_g4:
                grp_poids_total = st.number_input(
                    "Poids total (kg)",
                    min_value=0.0, max_value=200000.0,
                    value=float(grp_nb * POIDS_UNIT_SUIVI[grp_tc]),
                    step=100.0,
                    key=f"grp_poids_{job_en_suivi}",
                )
            grp_notes = st.text_input("Notes (optionnel)", key=f"grp_notes_{job_en_suivi}")
            grp_disabled = not bool(st.session_state.get(ss_op_key, '').strip())
            if st.button("✅ Enregistrer la saisie groupée", key=f"grp_btn_{job_en_suivi}",
                        type="primary", use_container_width=True, disabled=grp_disabled):
                ok, msg = ajouter_suivi_pallox(
                    job_id=job_en_suivi,
                    type_sortie=grp_type,
                    nb_pallox=grp_nb,
                    type_conditionnement=grp_tc,
                    poids_kg=grp_poids_total,
                    operateur=st.session_state[ss_op_key],
                    notes=grp_notes if grp_notes else None,
                )
                if ok:
                    st.toast(msg, icon="✅")
                    st.rerun()
                else:
                    st.error(msg)
            if grp_disabled:
                st.caption("⚠️ Sélectionne un opérateur d'abord")
        
        st.markdown("---")
        
        # === 4. Compteurs actuels + historique ===
        st.markdown("### 📊 État actuel du suivi")
        col_a1, col_a2, col_a3, col_a4 = st.columns(4)
        col_a1.metric("✨ Lavés",      f"{agreg_now['LAVÉ']['nb_pallox']} pal",
                     delta=f"{agreg_now['LAVÉ']['poids_kg']:.0f} kg")
        col_a2.metric("🌾 Grenailles", f"{agreg_now['GRENAILLES']['nb_pallox']} pal",
                     delta=f"{agreg_now['GRENAILLES']['poids_kg']:.0f} kg")
        col_a3.metric("🗑️ Déchets",   f"{agreg_now['DÉCHETS']['nb_pallox']} pal",
                     delta=f"{agreg_now['DÉCHETS']['poids_kg']:.0f} kg")
        # Progression : nb lavés / quantité prévue (Q-bis 2 = B)
        progression_pct = (agreg_now['LAVÉ']['nb_pallox'] / qty_prev_s * 100) if qty_prev_s > 0 else 0
        col_a4.metric("📊 Progression lavés", f"{progression_pct:.0f} %",
                     delta=f"{agreg_now['LAVÉ']['nb_pallox']} / {qty_prev_s}")
        
        # Historique avec suppression
        suivis_list = get_suivis_job(job_en_suivi)
        if suivis_list:
            st.markdown(f"##### 🕐 Historique ({len(suivis_list)} saisies)")
            for s in suivis_list[:20]:  # Limite à 20 affichées
                col_h_t, col_h_d, col_h_o, col_h_x = st.columns([1, 4, 2, 1])
                hh = s['created_at'].strftime('%H:%M')
                with col_h_t:
                    st.caption(hh)
                with col_h_d:
                    type_emoji = {'LAVÉ': '✨', 'GRENAILLES': '🌾', 'DÉCHETS': '🗑️'}.get(s['type_sortie'], '')
                    st.caption(f"{type_emoji} {s['nb_pallox']}× {s['type_sortie']} ({s['type_conditionnement'] or '?'}) — **{float(s['poids_kg']):.0f} kg**")
                with col_h_o:
                    st.caption(f"👷 {s['operateur'] or '?'}")
                with col_h_x:
                    if st.button("❌", key=f"del_suivi_{s['id']}", help="Supprimer cette saisie"):
                        ok_d, msg_d = supprimer_suivi_pallox(int(s['id']))
                        st.toast(msg_d, icon="✅" if ok_d else "❌")
                        st.rerun()
            if len(suivis_list) > 20:
                st.caption(f"... et {len(suivis_list) - 20} saisies plus anciennes (masquées)")
        else:
            st.caption("Aucune saisie pour ce job. Utilise les boutons rapides ci-dessus.")
        
        st.markdown("---")
        st.markdown("---")
    
    # ============================================================
    # ⭐ FORMULAIRE TERMINAISON EN PLEINE LARGEUR (avant calendrier)
    # ============================================================
    
    # Chercher si un job EN_COURS a son formulaire ouvert
    job_en_terminaison = None
    job_elem_data = None
    
    # Parcourir session_state pour trouver un show_finish actif
    for key in list(st.session_state.keys()):
        if key.startswith('show_finish_') and st.session_state.get(key, False):
            job_id_to_finish = int(float(key.replace('show_finish_', '')))
            # Chercher les données de ce job dans planning_df
            if not planning_df.empty:
                job_rows = planning_df[(planning_df['job_id'] == job_id_to_finish) & (planning_df['type_element'] == 'JOB')]
                if not job_rows.empty:
                    job_en_terminaison = job_id_to_finish
                    job_elem_data = job_rows.iloc[0]
                    break
    
    # Si un formulaire de terminaison est ouvert, l'afficher en pleine largeur
    if job_en_terminaison and job_elem_data is not None:
        elem = job_elem_data
        
        st.markdown("---")
        st.markdown(f"## 📝 Saisie résultats lavage - Job #{job_en_terminaison}")
        
        # Info job
        variete = elem['variete'] if pd.notna(elem.get('variete')) else '-'
        code_lot = elem['code_lot_interne'] if pd.notna(elem.get('code_lot_interne')) else '-'
        st.info(f"🌱 **{variete}** | 📦 Lot: {code_lot} | {int(elem['quantite_pallox'])} pallox")
        
        # Affichage read-only des 5 infos saisies à la création (Q6 : st.info compact)
        type_tapis_c = elem.get('type_tapis') if pd.notna(elem.get('type_tapis')) else None
        etiq_gren_c = elem.get('etiquette_grenailles') if pd.notna(elem.get('etiquette_grenailles')) else None
        etiq_pal_c = elem.get('etiquette_pallox') if pd.notna(elem.get('etiquette_pallox')) else None
        cal_seuil_c = elem.get('calibre_seuil') if pd.notna(elem.get('calibre_seuil')) else None
        if any([type_tapis_c, etiq_gren_c, etiq_pal_c, cal_seuil_c]):
            parts = []
            if type_tapis_c:
                parts.append(f"🎢 Tapis: **{type_tapis_c}**")
            if cal_seuil_c is not None:
                parts.append(f"📏 Gren 0-{int(cal_seuil_c)} mm / Lavé {int(cal_seuil_c)}-70 mm")
            if etiq_gren_c:
                parts.append(f"🏷️ Étiq gren: **{etiq_gren_c}**")
            if etiq_pal_c:
                parts.append(f"🏷️ Étiq pallox: **{etiq_pal_c}**")
            st.info("📋 Saisi à la création — " + " | ".join(parts))
        
        poids_brut = float(elem['poids_brut_kg']) if pd.notna(elem['poids_brut_kg']) else 0
        
        # ⭐ POIDS UNITAIRES CORRECTS
        TYPES_COND = ["Pallox", "Petit Pallox", "Big Bag"]
        POIDS_UNIT = {"Pallox": 1900, "Petit Pallox": 800, "Big Bag": 1600}
        
        # ⭐ Récupération des agrégats du suivi en cours (Q7-A : pré-remplissage modifiable)
        agreg_term = get_agregats_suivis_job(job_en_terminaison)
        nb_lave_suivi  = agreg_term['LAVÉ']['nb_pallox']
        nb_gren_suivi  = agreg_term['GRENAILLES']['nb_pallox']
        nb_dech_suivi  = agreg_term['DÉCHETS']['nb_pallox']
        poids_lave_suivi   = agreg_term['LAVÉ']['poids_kg']
        poids_gren_suivi   = agreg_term['GRENAILLES']['poids_kg']
        poids_dech_suivi   = agreg_term['DÉCHETS']['poids_kg']
        
        if agreg_term['nb_total_saisies'] > 0:
            st.success(
                f"📊 **Suivi en cours détecté** — pré-remplissage automatique : "
                f"✨ {nb_lave_suivi} lavés ({poids_lave_suivi:.0f} kg) • "
                f"🌾 {nb_gren_suivi} grenailles ({poids_gren_suivi:.0f} kg) • "
                f"🗑️ {nb_dech_suivi} déchets ({poids_dech_suivi:.0f} kg). "
                f"Les chiffres ci-dessous sont modifiables pour ajustement final."
            )
        
        st.markdown(f"### ⚖️ Poids brut en entrée : {poids_brut:,.0f} kg")
        st.markdown("---")
        
        # ============ LAYOUT 2 COLONNES PRINCIPALES ============
        col_lave, col_gren = st.columns(2)
        
        # ============ COLONNE LAVÉ ============
        with col_lave:
            st.markdown("### 🧼 Sortie LAVÉ")
            
            col_nb, col_type = st.columns([1, 2])
            with col_nb:
                # Pré-remplissage : suivi si dispo, sinon estimation 75% du brut
                default_nb_lave = nb_lave_suivi if nb_lave_suivi > 0 else max(1, int(poids_brut * 0.75 / 1900))
                nb_pallox_lave = st.number_input("Nb Pallox", min_value=0,
                    value=default_nb_lave,
                    key=f"nb_lave_full_{job_en_terminaison}")
            with col_type:
                type_lave = st.selectbox("Type conditionnement", TYPES_COND,
                    key=f"type_lave_full_{job_en_terminaison}")
            
            poids_unit_lave = POIDS_UNIT[type_lave]

            # ── Calculateur pesées individuelles ──
            with st.expander("🔢 Calculer depuis pesées individuelles"):
                st.caption("Saisir le poids de chaque pallox pesé (kg) séparé par des espaces ou virgules")
                pesees_lave_raw = st.text_input(
                    "Pesées (kg)", placeholder="ex: 1920 1850 1935 1780",
                    key=f"pesees_lave_{job_en_terminaison}")
                pesees_lave = []
                if pesees_lave_raw:
                    import re as _re
                    tokens = _re.split(r"[,;\s]+", pesees_lave_raw.strip())
                    for t in tokens:
                        try:
                            v = float(t)
                            if v > 0:
                                pesees_lave.append(v)
                        except ValueError:
                            pass
                if pesees_lave:
                    moy_lave = sum(pesees_lave) / len(pesees_lave)
                    poids_moy_lave_calc = moy_lave * nb_pallox_lave
                    col_pm1, col_pm2, col_pm3 = st.columns(3)
                    col_pm1.metric(f"Nb pesées", len(pesees_lave))
                    col_pm2.metric("Poids moyen/pallox", f"{moy_lave:,.0f} kg")
                    col_pm3.metric(f"→ Total ({nb_pallox_lave}p)", f"{poids_moy_lave_calc:,.0f} kg")
                    poids_lave_auto = poids_moy_lave_calc
                else:
                    poids_lave_auto = nb_pallox_lave * poids_unit_lave

            # Si pas de pesées, calcul auto
            if not pesees_lave_raw or not pesees_lave:
                # Si nb correspond au suivi, on utilise le poids du suivi (Q-bis 1 / Q7-A)
                if nb_lave_suivi > 0 and nb_pallox_lave == nb_lave_suivi and poids_lave_suivi > 0:
                    poids_lave_auto = poids_lave_suivi
                else:
                    poids_lave_auto = nb_pallox_lave * poids_unit_lave

            st.metric("⚖️ Poids retenu", f"{poids_lave_auto:,.0f} kg",
                help=f"{nb_pallox_lave} × {poids_unit_lave if not pesees_lave else int(sum(pesees_lave)/len(pesees_lave))} kg")
            p_lave = poids_lave_auto  # synchronisation automatique

            col_cal1, col_cal2 = st.columns(2)
            # Si calibre_seuil saisi à la création, on impose les bornes (read-only Q6)
            if cal_seuil_c is not None:
                cal_min_lave = int(cal_seuil_c)
                cal_max_lave = 70
                with col_cal1:
                    st.number_input("Calibre min (mm)", 0, 100, cal_min_lave,
                        key=f"cal_min_lave_full_{job_en_terminaison}", disabled=True,
                        help="Défini à la création — non modifiable")
                with col_cal2:
                    st.number_input("Calibre max (mm)", 0, 100, cal_max_lave,
                        key=f"cal_max_lave_full_{job_en_terminaison}", disabled=True,
                        help="Défini à la création — non modifiable")
            else:
                with col_cal1:
                    cal_min_lave = st.number_input("Calibre min (mm)", 0, 100, 35,
                        key=f"cal_min_lave_full_{job_en_terminaison}")
                with col_cal2:
                    cal_max_lave = st.number_input("Calibre max (mm)", 0, 100, 75,
                        key=f"cal_max_lave_full_{job_en_terminaison}")
        
        # ============ COLONNE GRENAILLES ============
        with col_gren:
            st.markdown("### 🌾 Sortie GRENAILLES")
            
            col_nb_g, col_type_g = st.columns([1, 2])
            with col_nb_g:
                # Pré-remplissage : suivi si dispo
                default_nb_gren = nb_gren_suivi if nb_gren_suivi > 0 else 0
                nb_pallox_gren = st.number_input("Nb Pallox", min_value=0,
                    value=default_nb_gren,
                    key=f"nb_gren_full_{job_en_terminaison}")
            with col_type_g:
                type_gren = st.selectbox("Type conditionnement", TYPES_COND,
                    key=f"type_gren_full_{job_en_terminaison}")

            if nb_pallox_gren > 0:
                poids_unit_gren = POIDS_UNIT[type_gren]

                # ── Calculateur pesées individuelles grenailles ──
                with st.expander("🔢 Calculer depuis pesées individuelles"):
                    st.caption("Saisir le poids de chaque pallox pesé (kg) séparé par des espaces ou virgules")
                    pesees_gren_raw = st.text_input(
                        "Pesées grenailles (kg)", placeholder="ex: 850 820 835",
                        key=f"pesees_gren_{job_en_terminaison}")
                    pesees_gren = []
                    if pesees_gren_raw:
                        import re as _re2
                        tokens_g = _re2.split("[,; ]+", pesees_gren_raw.strip())
                        for t in tokens_g:
                            try:
                                v = float(t)
                                if v > 0:
                                    pesees_gren.append(v)
                            except ValueError:
                                pass
                    if pesees_gren:
                        moy_gren = sum(pesees_gren) / len(pesees_gren)
                        poids_moy_gren_calc = moy_gren * nb_pallox_gren
                        col_gm1, col_gm2, col_gm3 = st.columns(3)
                        col_gm1.metric("Nb pesées", len(pesees_gren))
                        col_gm2.metric("Poids moyen/pallox", f"{moy_gren:,.0f} kg")
                        col_gm3.metric(f"→ Total ({nb_pallox_gren}p)", f"{poids_moy_gren_calc:,.0f} kg")
                        poids_gren_auto = poids_moy_gren_calc
                    else:
                        poids_gren_auto = nb_pallox_gren * poids_unit_gren

                if not pesees_gren_raw or not pesees_gren:
                    # Si nb correspond au suivi, on utilise le poids du suivi (Q-bis 1 / Q7-A)
                    if nb_gren_suivi > 0 and nb_pallox_gren == nb_gren_suivi and poids_gren_suivi > 0:
                        poids_gren_auto = poids_gren_suivi
                    else:
                        poids_gren_auto = nb_pallox_gren * poids_unit_gren

                st.metric("⚖️ Poids retenu", f"{poids_gren_auto:,.0f} kg",
                    help=f"{nb_pallox_gren} × {poids_unit_gren if not pesees_gren else int(sum(pesees_gren)/len(pesees_gren))} kg")
                p_gren = poids_gren_auto  # synchronisation automatique

                col_cal1_g, col_cal2_g = st.columns(2)
                # Si calibre_seuil saisi à la création, on impose les bornes (read-only Q6)
                if cal_seuil_c is not None:
                    cal_min_gren = 0
                    cal_max_gren = int(cal_seuil_c)
                    with col_cal1_g:
                        st.number_input("Calibre min (mm)", 0, 100, cal_min_gren,
                            key=f"cal_min_gren_full_{job_en_terminaison}", disabled=True,
                            help="Défini à la création — non modifiable")
                    with col_cal2_g:
                        st.number_input("Calibre max (mm)", 0, 100, cal_max_gren,
                            key=f"cal_max_gren_full_{job_en_terminaison}", disabled=True,
                            help="Défini à la création — non modifiable")
                else:
                    with col_cal1_g:
                        cal_min_gren = st.number_input("Calibre min (mm)", 0, 100, 20,
                            key=f"cal_min_gren_full_{job_en_terminaison}")
                    with col_cal2_g:
                        cal_max_gren = st.number_input("Calibre max (mm)", 0, 100, 35,
                            key=f"cal_max_gren_full_{job_en_terminaison}")
            else:
                p_gren = 0.0
                # Si calibre_seuil saisi à la création, on prend ses bornes même si pas de grenailles
                if cal_seuil_c is not None:
                    cal_min_gren = 0
                    cal_max_gren = int(cal_seuil_c)
                else:
                    cal_min_gren = 20
                    cal_max_gren = 35
                st.caption("ℹ️ Pas de grenailles — mettez Nb Pallox > 0 si besoin")
        
        st.markdown("---")
        
        # ============ DÉCHETS + RÉCAP ============
        col_dech, col_recap = st.columns([1, 2])
        
        with col_dech:
            st.markdown("### 🗑️ Déchets")

            col_nd1, col_nd2 = st.columns([1, 2])
            with col_nd1:
                # Pré-remplissage : suivi si dispo
                default_nb_dech = nb_dech_suivi if nb_dech_suivi > 0 else 0
                nb_pallox_dech = st.number_input("Nb Pallox", min_value=0,
                    value=default_nb_dech, key=f"nb_pallox_dech_{job_en_terminaison}")
            with col_nd2:
                type_dech = st.selectbox("Type conditionnement", TYPES_COND,
                    key=f"type_dech_full_{job_en_terminaison}")

            poids_unit_dech = POIDS_UNIT[type_dech]

            with st.expander("🔢 Calculer depuis pesées individuelles"):
                st.caption("Saisir le poids de chaque pallox pesé (kg) — espaces ou virgules")
                pesees_dech_raw = st.text_input(
                    "Pesées déchets (kg)", placeholder="ex: 1850 1920 1800",
                    key=f"pesees_dech_{job_en_terminaison}")
                pesees_dech = []
                if pesees_dech_raw:
                    import re as _re3
                    for t in _re3.split("[,; ]+", pesees_dech_raw.strip()):
                        try:
                            v = float(t)
                            if v > 0:
                                pesees_dech.append(v)
                        except ValueError:
                            pass
                if pesees_dech:
                    moy_dech = sum(pesees_dech) / len(pesees_dech)
                    poids_dech_calc = moy_dech * nb_pallox_dech
                    col_dd1, col_dd2, col_dd3 = st.columns(3)
                    col_dd1.metric("Nb pesées", len(pesees_dech))
                    col_dd2.metric("Poids moyen/pallox", f"{moy_dech:,.0f} kg")
                    col_dd3.metric(f"→ Total ({nb_pallox_dech}p)", f"{poids_dech_calc:,.0f} kg")
                    poids_dech_auto = poids_dech_calc
                else:
                    poids_dech_auto = nb_pallox_dech * poids_unit_dech

            if not pesees_dech_raw or not pesees_dech:
                # Si nb_pallox_dech correspond au suivi, on utilise le poids du suivi (Q-bis 1 = A)
                if nb_dech_suivi > 0 and nb_pallox_dech == nb_dech_suivi and poids_dech_suivi > 0:
                    poids_dech_auto = poids_dech_suivi
                else:
                    poids_dech_auto = nb_pallox_dech * poids_unit_dech

            st.metric("⚖️ Poids retenu", f"{poids_dech_auto:,.0f} kg",
                help=f"{nb_pallox_dech} × {poids_unit_dech if not pesees_dech else int(sum(pesees_dech)/len(pesees_dech))} kg")
            p_dech = poids_dech_auto

            p_terre = poids_brut - p_lave - p_gren - p_dech

            if p_terre < 0:
                st.error(f"❌ Terre : {p_terre:,.0f} kg (NÉGATIF !)")
                terre_ok = False
            else:
                st.success(f"✅ Terre : **{p_terre:,.0f} kg**")
                terre_ok = True
        
        with col_recap:
            st.markdown("### 📊 Récapitulatif")
            col_r1, col_r2, col_r3, col_r4 = st.columns(4)
            with col_r1:
                st.metric("Brut entrée", f"{poids_brut:,.0f} kg")
            with col_r2:
                st.metric("Lavé sortie", f"{p_lave:,.0f} kg")
            with col_r3:
                st.metric("Grenailles", f"{p_gren:,.0f} kg")
            with col_r4:
                st.metric("Déch+Terre", f"{p_dech + max(0, p_terre):,.0f} kg")
            
            if poids_brut > 0:
                rendement = ((p_lave + p_gren) / poids_brut) * 100
                st.info(f"📈 **Rendement : {rendement:.1f}%**")
        
        # Validation calibres
        calibres_ok = (cal_min_lave < cal_max_lave) and (nb_pallox_gren == 0 or cal_min_gren < cal_max_gren)
        if not calibres_ok:
            st.error("❌ Calibre min doit être < calibre max")
        
        st.markdown("---")
        
        # ============ DESTINATION + BOUTONS ============
        col_dest, col_btns = st.columns([2, 1])
        
        with col_dest:
            st.markdown("### 📍 Destination")
            empls = get_emplacements_saint_flavy()
            empl = st.selectbox("Emplacement stockage SAINT_FLAVY", [""] + [e[0] for e in empls], key=f"empl_full_{job_en_terminaison}")
        
        with col_btns:
            st.markdown("### ✅ Actions")
            can_validate = terre_ok and calibres_ok and empl != ""
            
            if st.button("✅ Valider terminaison", key=f"val_finish_full_{job_en_terminaison}", type="primary", disabled=not can_validate, use_container_width=True):
                success, msg = terminer_job(
                    job_en_terminaison,
                    nb_pallox_lave, type_lave, p_lave, cal_min_lave, cal_max_lave,
                    nb_pallox_gren, type_gren, p_gren, cal_min_gren, cal_max_gren,
                    p_dech,
                    "SAINT_FLAVY", empl
                )
                if success:
                    st.success(msg)
                    st.session_state.pop(f'show_finish_{job_en_terminaison}', None)
                    st.rerun()
                else:
                    st.error(msg)
            
            if st.button("❌ Annuler", key=f"cancel_full_{job_en_terminaison}", use_container_width=True):
                st.session_state.pop(f'show_finish_{job_en_terminaison}', None)
                st.rerun()
        
        st.markdown("---")
        st.markdown("---")
    
    # ============================================================
    # Bloc Modifier pleine largeur (même pattern que Terminer)
    # ============================================================
    elem_en_modif = None
    elem_data_modif = None
    for key in list(st.session_state.keys()):
        if key.startswith('show_edit_') and st.session_state.get(key, False):
            try:
                elem_id_to_edit = int(float(key.replace('show_edit_', '')))
            except (ValueError, TypeError):
                continue
            if not planning_df.empty:
                elem_rows = planning_df[planning_df['id'] == elem_id_to_edit]
                if not elem_rows.empty:
                    elem_en_modif = elem_id_to_edit
                    elem_data_modif = elem_rows.iloc[0]
                    break
    
    if elem_en_modif and elem_data_modif is not None:
        elem_e = elem_data_modif
        elem_id_edit = int(elem_e['id'])
        job_id_edit = int(elem_e['job_id'])
        is_multi_lot_edit = bool(elem_e.get('is_multi_lot', False))
        nb_lots_edit = int(elem_e.get('nb_lots', 1)) if pd.notna(elem_e.get('nb_lots')) else 1
        
        pallox_actuel = int(elem_e['quantite_pallox']) if pd.notna(elem_e['quantite_pallox']) else 1
        poids_brut_act = float(elem_e['poids_brut_kg']) if pd.notna(elem_e['poids_brut_kg']) else 0
        cadence_act = float(elem_e['capacite_th']) if pd.notna(elem_e.get('capacite_th')) and elem_e.get('capacite_th') else 13.0
        poids_unit_act = round(poids_brut_act / pallox_actuel) if pallox_actuel > 0 else 1900
        
        POIDS_UNIT_OPTS = {"Pallox (1900 kg)": 1900,
                           "Petit Pallox (800 kg)": 800,
                           "Big Bag (1600 kg)": 1600}
        POIDS_UNIT_MAP_UI = {'Pallox': 1900, 'Petit Pallox': 800, 'Big Bag': 1600}
        
        st.markdown("---")
        
        # ============================================================
        # BRANCHE BATCH : saisie fine par lot fille
        # ============================================================
        if is_multi_lot_edit:
            st.markdown(f"## ✏️ Modifier le job batch #{job_id_edit} ({nb_lots_edit} lots)")
            st.info(f"🌱 **{elem_e.get('variete', '-')}** | 📦 BATCH ({nb_lots_edit} lots) | Total actuel : {pallox_actuel} pallox | {poids_brut_act/1000:.1f} T")
            
            # Charger les filles depuis BDD
            filles_data = get_lots_fille_du_job(job_id_edit)
            if not filles_data:
                st.error("❌ Impossible de charger les lots fille de ce batch")
                st.stop()
            
            st.markdown("##### 📦 Composition du batch — Ajustez chaque lot")
            
            # Saisie par fille
            new_quantites_par_fille = {}
            for fille in filles_data:
                fille_id = int(fille['id'])
                code_lot = str(fille.get('code_lot_interne', ''))
                prod = str(fille.get('producteur', '') or '')
                site = str(fille.get('site_stockage', '') or '')
                empl = str(fille.get('emplacement_stockage', '') or '')
                type_cond_f = str(fille.get('type_conditionnement') or 'Pallox')
                poids_unit_f = POIDS_UNIT_MAP_UI.get(type_cond_f, 1900)
                qty_actuel = int(fille.get('quantite_pallox', 0))
                
                # Label enrichi
                loc_parts = []
                if prod: loc_parts.append(f"👤 {prod}")
                if site or empl: loc_parts.append(f"📍 {site}/{empl}".rstrip('/'))
                loc_str = " — ".join(loc_parts)
                
                st.markdown(f"**{code_lot}** — {loc_str}")
                
                col_f1, col_f2, col_f3 = st.columns([1.5, 1, 1])
                with col_f1:
                    st.text_input(
                        "Type cond.",
                        value=f"{type_cond_f} ({poids_unit_f} kg/p)",
                        disabled=True,
                        key=f"edit_fille_type_{fille_id}",
                        label_visibility="collapsed"
                    )
                with col_f2:
                    new_qty_key = f"edit_fille_qty_{fille_id}"
                    if new_qty_key not in st.session_state:
                        st.session_state[new_qty_key] = qty_actuel
                    new_qty = st.number_input(
                        "Nb pallox",
                        min_value=0,  # 0 autorisé (lot temporairement désactivé)
                        step=1,
                        key=new_qty_key,
                        label_visibility="collapsed"
                    )
                    new_quantites_par_fille[fille_id] = new_qty
                with col_f3:
                    new_poids_fille = new_qty * poids_unit_f
                    delta_kg = new_poids_fille - float(fille.get('poids_brut_kg', 0))
                    st.metric("Poids fille", f"{new_poids_fille/1000:.1f} T",
                              delta=f"{delta_kg/1000:+.1f} T" if delta_kg else None,
                              label_visibility="collapsed")
                st.markdown("<hr style='margin:0.3rem 0;border:none;border-top:1px solid #eee;'>",
                            unsafe_allow_html=True)
            
            # Total recalculé
            total_pallox = sum(new_quantites_par_fille.values())
            total_poids = sum(
                qty * POIDS_UNIT_MAP_UI.get(
                    str(next(f for f in filles_data if int(f['id']) == fid)['type_conditionnement'] or 'Pallox'),
                    1900)
                for fid, qty in new_quantites_par_fille.items()
            )
            
            # Cadence + récap
            col_rc1, col_rc2 = st.columns(2)
            with col_rc1:
                lignes_cap = {l['code']: float(l['capacite_th']) for l in get_lignes_lavage()}
                cap_max = lignes_cap.get(elem_e.get('ligne_lavage'), 13.0)
                new_cadence_key = f"edit_cadence_batch_{elem_id_edit}"
                if new_cadence_key not in st.session_state:
                    st.session_state[new_cadence_key] = float(min(cadence_act, 25.0))
                nouvelle_cadence = st.number_input(
                    "Cadence (T/h)",
                    min_value=0.5, max_value=25.0, step=0.5,
                    key=new_cadence_key,
                    help=f"Capacité nominale ligne : {cap_max} T/h. Max autorisé : 25 T/h."
                )
            with col_rc2:
                nouveau_temps = (total_poids / 1000) / nouvelle_cadence if nouvelle_cadence > 0 else 0
                col_m1, col_m2, col_m3 = st.columns(3)
                col_m1.metric("Total pallox", f"{total_pallox}p",
                              delta=f"{total_pallox - pallox_actuel:+d}p" if total_pallox != pallox_actuel else None)
                col_m2.metric("Poids total", f"{total_poids/1000:.1f} T",
                              delta=f"{(total_poids - poids_brut_act)/1000:+.1f} T")
                col_m3.metric("Temps estimé", f"{nouveau_temps:.1f} h")
            
            if total_pallox == 0:
                st.error("❌ Le batch doit avoir au moins 1 pallox au total (toutes les filles à 0 pallox)")
            
            col_ok_e, col_ann_e = st.columns(2)
            with col_ok_e:
                btn_disabled = (total_pallox == 0)
                if st.button("✅ Valider modification", key=f"edit_ok_batch_{elem_id_edit}",
                             type="primary", use_container_width=True, disabled=btn_disabled):
                    # Construire lots_updates
                    lots_updates = [
                        {'fille_id': fid, 'quantite_pallox': qty}
                        for fid, qty in new_quantites_par_fille.items()
                    ]
                    ok, msg_e = modifier_job(
                        job_id_edit, elem_id_edit,
                        total_pallox,  # nouveau_pallox = total (calculé pour cohérence parent)
                        poids_unit_act,  # poids_unit ignoré en mode batch+lots_updates mais on passe une valeur
                        nouvelle_cadence,
                        type_conditionnement=None,  # pas d'override en batch
                        lots_updates=lots_updates
                    )
                    if ok:
                        st.session_state.pop(f'show_edit_{elem_id_edit}', None)
                        for fid in new_quantites_par_fille:
                            st.session_state.pop(f"edit_fille_qty_{fid}", None)
                        st.session_state.pop(new_cadence_key, None)
                        st.success(msg_e)
                        st.rerun()
                    else:
                        st.error(msg_e)
            with col_ann_e:
                if st.button("❌ Annuler", key=f"edit_cancel_batch_{elem_id_edit}",
                             use_container_width=True):
                    st.session_state.pop(f'show_edit_{elem_id_edit}', None)
                    for fid in new_quantites_par_fille:
                        st.session_state.pop(f"edit_fille_qty_{fid}", None)
                    st.session_state.pop(new_cadence_key, None)
                    st.rerun()
        
        # ============================================================
        # BRANCHE MONO-LOT : saisie simple (comportement inchangé)
        # ============================================================
        else:
            st.markdown(f"## ✏️ Modifier le job #{job_id_edit}")
            variete_e = elem_e['variete'] if pd.notna(elem_e.get('variete')) else '-'
            code_lot_e = elem_e['code_lot_interne'] if pd.notna(elem_e.get('code_lot_interne')) else '-'
            st.info(f"🌱 **{variete_e}** | 📦 Lot: {code_lot_e} | Actuel : {pallox_actuel} pallox | {poids_brut_act/1000:.1f} T")
            
            col_e1, col_e2 = st.columns(2)
            with col_e1:
                closest_key = min(POIDS_UNIT_OPTS, key=lambda k: abs(POIDS_UNIT_OPTS[k] - poids_unit_act))
                type_cond_edit = st.selectbox(
                    "Type conditionnement",
                    list(POIDS_UNIT_OPTS.keys()),
                    index=list(POIDS_UNIT_OPTS.keys()).index(closest_key),
                    key=f"edit_type_full_{elem_id_edit}"
                )
                poids_unit_sel = POIDS_UNIT_OPTS[type_cond_edit]
                type_cond_to_pass = type_cond_edit.split(' (')[0]
                
                new_pallox_key = f"edit_pallox_full_{elem_id_edit}"
                if new_pallox_key not in st.session_state:
                    st.session_state[new_pallox_key] = pallox_actuel
                nouveau_pallox = st.number_input(
                    "Nb pallox", min_value=1,
                    step=1, key=new_pallox_key
                )
            
            with col_e2:
                lignes_cap = {l['code']: float(l['capacite_th']) for l in get_lignes_lavage()}
                cap_max = lignes_cap.get(elem_e.get('ligne_lavage'), 13.0)
                new_cadence_key = f"edit_cadence_full_{elem_id_edit}"
                if new_cadence_key not in st.session_state:
                    st.session_state[new_cadence_key] = float(min(cadence_act, 25.0))
                nouvelle_cadence = st.number_input(
                    "Cadence (T/h)", min_value=0.5,
                    max_value=25.0,
                    step=0.5, key=new_cadence_key,
                    help=f"Capacité nominale ligne : {cap_max} T/h. Max autorisé : 25 T/h."
                )
                nouveau_poids = nouveau_pallox * poids_unit_sel
                nouveau_temps = (nouveau_poids / 1000) / nouvelle_cadence
                col_m1, col_m2 = st.columns(2)
                col_m1.metric("Nouveau poids", f"{nouveau_poids/1000:.1f} T",
                              delta=f"{(nouveau_poids - poids_brut_act)/1000:+.1f} T")
                col_m2.metric("Nouveau temps", f"{nouveau_temps:.1f} h")
            
            col_ok_e, col_ann_e = st.columns(2)
            with col_ok_e:
                if st.button("✅ Valider modification", key=f"edit_ok_full_{elem_id_edit}",
                             type="primary", use_container_width=True):
                    ok, msg_e = modifier_job(
                        job_id_edit, elem_id_edit,
                        nouveau_pallox, poids_unit_sel, nouvelle_cadence,
                        type_conditionnement=type_cond_to_pass
                    )
                    if ok:
                        st.session_state.pop(f'show_edit_{elem_id_edit}', None)
                        st.session_state.pop(new_pallox_key, None)
                        st.session_state.pop(new_cadence_key, None)
                        st.success(msg_e)
                        st.rerun()
                    else:
                        st.error(msg_e)
            with col_ann_e:
                if st.button("❌ Annuler", key=f"edit_cancel_full_{elem_id_edit}",
                             use_container_width=True):
                    st.session_state.pop(f'show_edit_{elem_id_edit}', None)
                    st.session_state.pop(new_pallox_key, None)
                    st.session_state.pop(new_cadence_key, None)
                    st.rerun()
        
        st.markdown("---")
        st.markdown("---")
    
    # ============================================================
    # Layout principal calendrier
    # ============================================================
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
                statut_source = job.get('statut_source', 'BRUT')
                badge_source = "🔄" if statut_source == 'GRENAILLES_BRUTES' else "🥔"
                
                # Détection multi-lot (Commit 1+2)
                is_multi = bool(job.get('is_multi_lot', False))
                nb_lots = int(job.get('nb_lots', 1)) if pd.notna(job.get('nb_lots')) else 1
                lots_detail = job.get('lots_detail') or []
                
                if is_multi and nb_lots > 1 and lots_detail:
                    # ===== Carte BATCH multi-lot =====
                    # Liste compacte des lots fille
                    lots_lines = []
                    for ld in lots_detail:
                        prod_lab = ld.get('producteur') or '—'
                        lots_lines.append(
                            f"&nbsp;&nbsp;• {prod_lab} — {int(ld.get('quantite_pallox') or 0)}p"
                        )
                    lots_html = "<br>".join(lots_lines)
                    
                    st.markdown(
                        f"""<div class="job-card">
                        <strong>Job #{int(job['id'])} 📦 Batch ({nb_lots} lots) {badge_source}</strong><br>
                        🌱 {job['variete']}<br>
                        {lots_html}<br>
                        📦 Total {int(job['quantite_pallox'])}p - ⏱️ {job['temps_estime_heures']:.1f}h
                        </div>""",
                        unsafe_allow_html=True
                    )
                else:
                    # ===== Carte MONO-LOT (comportement legacy) =====
                    producteur_info = (
                        f"<br>👤 {job['producteur']}"
                        if pd.notna(job.get('producteur')) and job['producteur'] else ""
                    )
                    st.markdown(f"""<div class="job-card"><strong>Job #{int(job['id'])} {badge_source}</strong><br>
                    🌱 {job['variete']}{producteur_info}<br>📦 {int(job['quantite_pallox'])}p - ⏱️ {job['temps_estime_heures']:.1f}h</div>""", unsafe_allow_html=True)
                
                jours_options = ["Sélectionner..."] + [f"{['Lun','Mar','Mer','Jeu','Ven','Sam'][i]} {(week_start + timedelta(days=i)).strftime('%d/%m')}" for i in range(6)]
                jour_choisi = st.selectbox("Jour", jours_options, key=f"jour_job_{job['id']}", label_visibility="collapsed")
                
                if jour_choisi != "Sélectionner...":
                    jour_idx = jours_options.index(jour_choisi) - 1
                    date_cible = week_start + timedelta(days=jour_idx)
                    # Heure par défaut : 06:00 (plus pertinent métier que la 'debut' BDD qui peut être 00:00)
                    h_debut_jour = time(6, 0)
                    heure_saisie = st.time_input("Heure", value=h_debut_jour, step=900, key=f"heure_job_{job['id']}", label_visibility="collapsed")
                    duree_min = int(job['temps_estime_heures'] * 60)
                    
                    heure_optimale, _, msg_info = trouver_prochain_creneau_libre(planning_df, date_cible, st.session_state.selected_ligne, heure_saisie, duree_min)
                    if msg_info:
                        st.info(msg_info)
                    
                    # Plus de contrôle de fin de journée : chevauchement minuit géré automatiquement
                    # par ajouter_element_planning (création parent + enfant J+1)
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
        
        # ============================================================
        # BLOC UNIFIÉ DE PLANIFICATION (Commit 6)
        # 1 selectbox type + UI commune (mode, jour, heure/job, bouton)
        # ============================================================
        if not temps_customs:
            st.caption("Aucun temps custom — créez-en un via 'Gérer les temps customs' ci-dessous")
        else:
            # 1. Selectbox type (libellé + emoji + durée)
            tc_opts = {
                f"{tc['emoji']} {tc['libelle']} ({tc['duree_minutes']}min)": tc
                for tc in temps_customs
            }
            tc_label_sel = st.selectbox(
                "Type de temps",
                list(tc_opts.keys()),
                key="tc_unified_type",
                label_visibility="collapsed"
            )
            tc_sel = tc_opts[tc_label_sel]
            
            # 2. Mode insertion (créneau libre / dans un job)
            mode_tc = st.radio(
                "Mode d'insertion",
                ["Créneau libre", "Dans un job"],
                key="tc_unified_mode",
                horizontal=True,
                label_visibility="collapsed"
            )
            
            # 3. Selectbox jour
            jours_tc = ["Sélectionner..."] + [
                f"{['Lun','Mar','Mer','Jeu','Ven','Sam'][i]} {(week_start + timedelta(days=i)).strftime('%d/%m')}"
                for i in range(6)
            ]
            jour_tc = st.selectbox(
                "Jour",
                jours_tc,
                key="tc_unified_jour",
                label_visibility="collapsed"
            )
            
            if jour_tc != "Sélectionner...":
                jour_idx = jours_tc.index(jour_tc) - 1
                date_cible = week_start + timedelta(days=jour_idx)
                jour_str_tc = str(date_cible)
                
                if mode_tc == "Créneau libre":
                    # 4a. Heure cible (défaut 06:00)
                    heure_tc = st.time_input(
                        "Heure",
                        value=time(6, 0),
                        step=900,
                        key="tc_unified_heure",
                        label_visibility="collapsed"
                    )
                    heure_optimale_tc, _, msg_info_tc = trouver_prochain_creneau_libre(
                        planning_df, date_cible, st.session_state.selected_ligne,
                        heure_tc, tc_sel['duree_minutes']
                    )
                    if msg_info_tc:
                        st.info(msg_info_tc)
                    
                    if st.button("✅ Insérer", key="tc_unified_btn_libre",
                                 type="primary", use_container_width=True):
                        success, msg = ajouter_element_planning(
                            'CUSTOM', None, int(tc_sel['id']), date_cible,
                            st.session_state.selected_ligne,
                            tc_sel['duree_minutes'], annee, semaine, heure_optimale_tc
                        )
                        if success:
                            st.success(msg)
                            st.rerun()
                        else:
                            st.error(msg)
                
                else:
                    # 4b. Mode "Dans un job" — choisir le job cible
                    if not planning_df.empty:
                        mask_jobs = (
                            (planning_df['date_prevue'].astype(str) == jour_str_tc) &
                            (planning_df['ligne_lavage'] == st.session_state.selected_ligne) &
                            (planning_df['type_element'] == 'JOB') &
                            (planning_df['job_statut'].isin(['PRÉVU', 'EN_COURS']))
                        )
                        jobs_du_jour = planning_df[mask_jobs]
                    else:
                        jobs_du_jour = pd.DataFrame()
                    
                    if jobs_du_jour.empty:
                        st.caption("Aucun job PRÉVU/EN_COURS ce jour sur cette ligne")
                    else:
                        job_opts = {
                            f"Job #{int(r['job_id'])} — {r['variete']} "
                            f"({r['heure_debut'].strftime('%H:%M') if pd.notna(r['heure_debut']) else '?'} → "
                            f"{r['heure_fin'].strftime('%H:%M') if pd.notna(r['heure_fin']) else '?'})": int(r['id'])
                            for _, r in jobs_du_jour.iterrows()
                        }
                        job_sel_label = st.selectbox(
                            "Choisir le job",
                            list(job_opts.keys()),
                            key="tc_unified_job_cible",
                            label_visibility="collapsed"
                        )
                        job_planning_id_sel = job_opts[job_sel_label]
                        
                        # Récupérer heure_debut et heure_fin du job sélectionné pour le time_input
                        job_row_sel = jobs_du_jour[jobs_du_jour['id'] == job_planning_id_sel].iloc[0]
                        job_h_deb = job_row_sel['heure_debut'] if pd.notna(job_row_sel['heure_debut']) else time(8, 0)
                        job_h_fin = job_row_sel['heure_fin']   if pd.notna(job_row_sel['heure_fin'])   else time(12, 0)
                        
                        # time_input pour l'heure d'insertion (défaut = heure_debut du job)
                        heure_insertion_tc = st.time_input(
                            "Insérer la pause à :",
                            value=job_h_deb,
                            step=900,  # pas de 15 min
                            key=f"tc_unified_heure_pause_{job_planning_id_sel}"
                        )
                        
                        st.caption(
                            f"⏸️ Pause de {tc_sel['duree_minutes']} min insérée à "
                            f"{heure_insertion_tc.strftime('%H:%M')} — heure_fin du job étendue + "
                            f"éléments suivants décalés (job : {job_h_deb.strftime('%H:%M')} → {job_h_fin.strftime('%H:%M')})"
                        )
                        
                        if st.button("✅ Insérer pause", key="tc_unified_btn_job",
                                     type="primary", use_container_width=True):
                            success, msg = inserer_pause_dans_job(
                                job_planning_id_sel, int(tc_sel['id']),
                                tc_sel['duree_minutes'], annee, semaine,
                                heure_insertion=heure_insertion_tc
                            )
                            if success:
                                st.success(msg)
                                st.rerun()
                            else:
                                st.error(msg)
        
        # ============================================================
        # EXPANDER GESTION (créer + supprimer) — Commit 6
        # ============================================================
        with st.expander("⚙️ Gérer les temps customs"):
            # --- Créer un nouveau temps ---
            st.markdown("**➕ Créer un nouveau temps**")
            new_lib = st.text_input("Libellé", key="new_tc_lib")
            col_n1, col_n2 = st.columns(2)
            with col_n1:
                new_dur = st.number_input("Durée (min)", 5, 480, 20, key="new_tc_dur")
            with col_n2:
                new_emo = st.selectbox("Emoji", ["⚙️", "☕", "🔧", "🍽️", "⏸️", "🧹", "🔄"],
                                       key="new_tc_emo")
            if st.button("Créer", key="btn_create_tc", use_container_width=True) and new_lib:
                creer_temps_custom(new_lib.upper().replace(" ", "_")[:20], new_lib, new_emo, new_dur)
                st.rerun()
            
            # --- Supprimer un temps existant ---
            if is_admin() and temps_customs:
                st.markdown("---")
                st.markdown("**🗑️ Supprimer un temps existant**")
                for tc in temps_customs:
                    col_lab, col_btn = st.columns([4, 1])
                    with col_lab:
                        st.markdown(
                            f"{tc['emoji']} {tc['libelle']} ({tc['duree_minutes']}min)"
                        )
                    with col_btn:
                        if st.button("🗑️", key=f"del_tc_mgmt_{tc['id']}"):
                            supprimer_temps_custom(tc['id'])
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
                                
                                # Badge source BRUT vs GRENAILLES
                                statut_source = elem.get('statut_source', 'BRUT')
                                badge_source = " 🔄" if statut_source == 'GRENAILLES_BRUTES' else " 🥔"
                                
                                # Producteur
                                producteur = elem.get('producteur') or ''
                                producteur_ligne = f"<br>👤 {producteur}" if producteur else ""
                                
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
                                
                                # Emplacement source
                                empl_site = elem.get('empl_site') or ''
                                empl_code = elem.get('empl_code') or ''
                                empl_ligne = f"<br>📍 {empl_site}/{empl_code}" if empl_code else ""
                                # Produit affecté
                                produits_aff = elem.get('produits_affectes') or ''
                                produit_ligne = f"<br>🛒 {produits_aff}" if produits_aff else "<br><small>Sans affectation</small>"
                                
                                # Infos métier saisies à la création (1 ligne compacte)
                                # La vraie refonte des cards arrivera à l'Objectif 2 du sprint
                                infos_metier_parts = []
                                if pd.notna(elem.get('type_tapis')) and elem.get('type_tapis'):
                                    infos_metier_parts.append(f"🎢 {elem['type_tapis']}")
                                if pd.notna(elem.get('calibre_seuil')) and elem.get('calibre_seuil'):
                                    infos_metier_parts.append(f"📏 0-{int(elem['calibre_seuil'])}/{int(elem['calibre_seuil'])}-70")
                                if pd.notna(elem.get('etiquette_grenailles')) and elem.get('etiquette_grenailles'):
                                    infos_metier_parts.append(f"🏷️G:{elem['etiquette_grenailles']}")
                                if pd.notna(elem.get('etiquette_pallox')) and elem.get('etiquette_pallox'):
                                    infos_metier_parts.append(f"🏷️P:{elem['etiquette_pallox']}")
                                infos_metier_ligne = f"<br><small>{' | '.join(infos_metier_parts)}</small>" if infos_metier_parts else ""
                                
                                # Tooltip mouseover : détail complet (infos création + suivi si EN_COURS)
                                # Préservation des infos initiales même en cours (demande Julien)
                                tooltip_parts = []
                                tooltip_parts.append(f"Job #{int(elem['job_id'])} — {job_statut}")
                                tooltip_parts.append(f"🌱 Variété : {elem['variete']}")
                                if pd.notna(elem.get('code_lot_interne')):
                                    tooltip_parts.append(f"📦 Lot : {elem['code_lot_interne']}")
                                if producteur:
                                    tooltip_parts.append(f"👤 Producteur : {producteur}")
                                if empl_code:
                                    tooltip_parts.append(f"📍 Source : {empl_site}/{empl_code}")
                                if pd.notna(elem.get('quantite_pallox')):
                                    tooltip_parts.append(f"📦 Quantité prévue : {int(elem['quantite_pallox'])} pallox")
                                if pd.notna(elem.get('poids_brut_kg')):
                                    tooltip_parts.append(f"⚖️ Poids brut : {float(elem['poids_brut_kg'])/1000:.1f} T")
                                if pd.notna(elem.get('type_tapis')) and elem.get('type_tapis'):
                                    tooltip_parts.append(f"🎢 Tapis : {elem['type_tapis']}")
                                if pd.notna(elem.get('calibre_seuil')) and elem.get('calibre_seuil'):
                                    cs_t = int(elem['calibre_seuil'])
                                    tooltip_parts.append(f"📏 Calibres : Gren 0-{cs_t}mm / Lavé {cs_t}-70mm")
                                if pd.notna(elem.get('etiquette_grenailles')) and elem.get('etiquette_grenailles'):
                                    tooltip_parts.append(f"🏷️ Étiq grenailles : {elem['etiquette_grenailles']}")
                                if pd.notna(elem.get('etiquette_pallox')) and elem.get('etiquette_pallox'):
                                    tooltip_parts.append(f"🏷️ Étiq pallox : {elem['etiquette_pallox']}")
                                if produits_aff:
                                    tooltip_parts.append(f"🛒 Produit affecté : {produits_aff}")
                                # Ajout du suivi si EN_COURS
                                if job_statut == 'EN_COURS':
                                    try:
                                        ag_t = get_agregats_suivis_job(int(elem['job_id']))
                                        if ag_t['nb_total_saisies'] > 0:
                                            tooltip_parts.append("--- Suivi en cours ---")
                                            tooltip_parts.append(f"✨ Lavés : {ag_t['LAVÉ']['nb_pallox']} pal ({ag_t['LAVÉ']['poids_kg']:.0f} kg)")
                                            tooltip_parts.append(f"🌾 Grenailles : {ag_t['GRENAILLES']['nb_pallox']} pal ({ag_t['GRENAILLES']['poids_kg']:.0f} kg)")
                                            tooltip_parts.append(f"🗑️ Déchets : {ag_t['DÉCHETS']['nb_pallox']} pal ({ag_t['DÉCHETS']['poids_kg']:.0f} kg)")
                                            if ag_t.get('operateur_dernier'):
                                                tooltip_parts.append(f"👷 Opérateur : {ag_t['operateur_dernier']}")
                                    except Exception:
                                        pass
                                tooltip_text = "\n".join(tooltip_parts).replace('"', "'")

                                st.markdown(f"""<div class="{css_class}" title="{tooltip_text}">
                                    <strong>{h_deb}</strong> {statut_emoji}<br>
                                    Job #{int(elem['job_id'])}{badge_source}<br>
                                    🌱 {elem['variete']}{producteur_ligne}{empl_ligne}{produit_ligne}<br>
                                    📦 {int(elem['quantite_pallox']) if pd.notna(elem['quantite_pallox']) else '?'}p{infos_metier_ligne}<br>
                                    <small>→{h_fin}</small>
                                </div>""", unsafe_allow_html=True)
                                
                                # Boutons action selon statut
                                if job_statut == 'PRÉVU':
                                    col_start, col_edit, col_move, col_del = st.columns(4)
                                    with col_start:
                                        if st.button("▶️", key=f"start_{elem['id']}", help="Démarrer"):
                                            success, msg = demarrer_job(int(elem['job_id']))
                                            if success:
                                                st.success(msg)
                                                st.rerun()
                                            else:
                                                st.error(msg)
                                    with col_edit:
                                        if st.button("✏️", key=f"edit_{elem['id']}", help="Modifier quantité / cadence"):
                                            st.session_state[f'show_edit_{elem["id"]}'] = True
                                            st.rerun()
                                    with col_move:
                                        if st.button("🔀", key=f"move_{elem['id']}", help="Déplacer"):
                                            st.session_state[f'show_move_{elem["id"]}'] = not st.session_state.get(f'show_move_{elem["id"]}', False)
                                            st.rerun()
                                    with col_del:
                                        if st.button("❌", key=f"del_{elem['id']}", help="Retirer"):
                                            ok_del, msg_del = retirer_element_planning(int(elem['id']))
                                            st.toast(msg_del, icon="✅" if ok_del else "❌")
                                            st.rerun()
                                    
                                    # Note : le formulaire de modification s'affiche en pleine largeur
                                    # en haut de la page (voir bloc "show_edit" plus haut), comme pour Terminer.
                                    
                                    # Formulaire inline de déplacement
                                    if st.session_state.get(f'show_move_{elem["id"]}', False):
                                        elem_id_move = int(elem['id'])
                                        duree_move = int(elem['duree_minutes']) if pd.notna(elem['duree_minutes']) else 60
                                        
                                        jours_move = [f"{['Lun','Mar','Mer','Jeu','Ven','Sam'][k]} {(week_start + timedelta(days=k)).strftime('%d/%m')}" for k in range(6)]
                                        # Index du jour actuel
                                        try:
                                            date_elem_str = str(elem['date_prevue'])[:10]
                                            jour_actuel_idx = next((k for k in range(6) if str(week_start + timedelta(days=k)) == date_elem_str), 0)
                                        except:
                                            jour_actuel_idx = 0
                                        
                                        jour_cible_str = st.selectbox(
                                            "Nouveau jour",
                                            jours_move,
                                            index=jour_actuel_idx,
                                            key=f"move_jour_{elem_id_move}"
                                        )
                                        jour_cible_idx = jours_move.index(jour_cible_str)
                                        date_cible_move = week_start + timedelta(days=jour_cible_idx)
                                        
                                        # Heure par défaut : 06:00 pour le déplacement
                                        h_debut_defaut = time(6, 0)
                                        heure_cible = st.time_input(
                                            "Nouvelle heure",
                                            value=h_debut_defaut,
                                            step=900,
                                            key=f"move_heure_{elem_id_move}"
                                        )
                                        
                                        # On place à l'heure exacte saisie.
                                        # La cascade dans deplacer_element_planning gère les conflits.
                                        col_ok, col_ann = st.columns(2)
                                        with col_ok:
                                            if st.button("✅", key=f"move_ok_{elem_id_move}", type="primary", use_container_width=True):
                                                success, msg = deplacer_element_planning(
                                                    elem_id_move, date_cible_move, heure_cible,
                                                    planning_df, st.session_state.selected_ligne, horaires_config
                                                )
                                                if success:
                                                    st.session_state.pop(f'show_move_{elem_id_move}', None)
                                                    st.success(msg)
                                                    st.rerun()
                                                else:
                                                    st.error(msg)
                                        with col_ann:
                                            if st.button("✖", key=f"move_ann_{elem_id_move}", use_container_width=True):
                                                st.session_state.pop(f'show_move_{elem_id_move}', None)
                                                st.rerun()
                                
                                elif job_statut == 'EN_COURS':
                                    # Afficher temps écoulé
                                    if pd.notna(elem.get('date_activation')):
                                        delta = datetime.now() - elem['date_activation']
                                        minutes_ecoulees = int(delta.total_seconds() / 60)
                                        st.caption(f"⏱️ {minutes_ecoulees // 60}h{minutes_ecoulees % 60:02d} écoulées")
                                    
                                    # Suivi en cours : récap rapide opérateur + progression
                                    try:
                                        agreg_card = get_agregats_suivis_job(int(elem['job_id']))
                                        qty_prev_card = int(elem['quantite_pallox']) if pd.notna(elem.get('quantite_pallox')) else 0
                                        nb_lave_card = agreg_card['LAVÉ']['nb_pallox']
                                        nb_gren_card = agreg_card['GRENAILLES']['nb_pallox']
                                        nb_dech_card = agreg_card['DÉCHETS']['nb_pallox']
                                        op_actuel    = agreg_card.get('operateur_dernier')
                                        if op_actuel:
                                            st.caption(f"👷 **{op_actuel}**")
                                        if qty_prev_card > 0:
                                            pct = min(100, int(nb_lave_card / qty_prev_card * 100))
                                            st.progress(pct / 100,
                                                       text=f"Lavés : {nb_lave_card}/{qty_prev_card} ({pct}%)")
                                        if nb_lave_card or nb_gren_card or nb_dech_card:
                                            st.caption(f"✨{nb_lave_card} • 🌾{nb_gren_card} • 🗑️{nb_dech_card}")
                                    except Exception:
                                        pass
                                    
                                    col_suivi_btn, col_term_btn = st.columns(2)
                                    with col_suivi_btn:
                                        if st.button("📊 Suivi", key=f"suivi_{elem['id']}",
                                                    use_container_width=True, help="Saisir pallox en cours"):
                                            st.session_state[f'show_suivi_{int(elem["job_id"])}'] = True
                                            st.rerun()
                                    with col_term_btn:
                                        if st.button("⏹️ Terminer", key=f"finish_{elem['id']}",
                                                    type="primary", use_container_width=True):
                                            st.session_state[f'show_finish_{int(elem["job_id"])}'] = True
                                            st.rerun()
                                    
                                    # Note: Le formulaire de terminaison et le suivi s'affichent en pleine
                                    # largeur au-dessus du calendrier
                                
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
                                    ok_del, msg_del = retirer_element_planning(int(elem['id']))
                                    st.toast(msg_del, icon="✅" if ok_del else "❌")
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
                   created_by, created_at,
                   COALESCE(is_multi_lot, FALSE) as is_multi_lot,
                   COALESCE(nb_lots, 1) as nb_lots,
                   batch_id
            FROM lavages_jobs
            ORDER BY created_at DESC
            LIMIT 100
        """)
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        
        if rows:
            df = pd.DataFrame([dict(r) for r in rows])
            
            # Pour les jobs multi-lot : code_lot_interne est NULL → afficher "BATCH (N lots)"
            def _format_code_lot(row):
                if row.get('is_multi_lot') and (row.get('nb_lots') or 1) > 1:
                    return f"📦 BATCH ({int(row.get('nb_lots') or 0)} lots)"
                return row.get('code_lot_interne') or '—'
            df['code_lot_interne'] = df.apply(_format_code_lot, axis=1)
            
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
            
            # Masquer les colonnes techniques (is_multi_lot, nb_lots, batch_id) en affichage
            cols_to_show = [c for c in df.columns if c not in ('is_multi_lot', 'nb_lots', 'batch_id')]
            st.dataframe(df[cols_to_show], use_container_width=True, hide_index=True)
        else:
            st.info("Aucun job")
    except Exception as e:
        st.error(f"Erreur : {str(e)}")

# ============================================================
# ONGLET 3 : CRÉER JOB
# ============================================================

with tab3:
    st.subheader("➕ Créer un Job de Lavage")
    
    # Deux sous-onglets : Besoins basés sur affectations VS Tous les lots BRUT
    create_tab1, create_tab2 = st.tabs(["📊 Besoins Affectations", "📋 Tous les lots BRUT"])
    
    # ============================================================
    # SOUS-ONGLET 1 : BESOINS BASÉS SUR AFFECTATIONS
    # ============================================================
    with create_tab1:
        st.markdown("*Lots avec affectations BRUT nécessitant du lavage*")
        
        besoins_df = get_besoins_lavage_affectations()
        lots_dispo = get_lots_bruts_disponibles()
        
        if besoins_df.empty:
            st.info("📭 Aucun besoin de lavage basé sur les affectations")
        else:
            # Charger récap produits
            recap_produits_df = get_recap_produits_lavage()
            
            # KPIs globaux
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("📦 Lots avec besoin", len(besoins_df))
            with col2:
                total_besoin = besoins_df['besoin_lavage_net_tonnes'].sum()
                st.metric("🧼 Besoin total NET", f"{total_besoin:.1f} T")
            with col3:
                total_jobs = besoins_df['jobs_prevus_tonnes'].sum()
                st.metric("📋 Jobs déjà prévus", f"{total_jobs:.1f} T")
            with col4:
                total_lave = besoins_df['stock_lave_tonnes'].sum()
                st.metric("✅ Stock LAVÉ existant", f"{total_lave:.1f} T")
            
            st.markdown("---")
            
            # ============ RÉCAP PAR PRODUIT COMMERCIAL ============
            if not recap_produits_df.empty:
                with st.expander("📦 Récapitulatif besoin par produit commercial", expanded=True):
                    df_recap_disp = recap_produits_df.copy()
                    
                    # Colonne écart colorée
                    def format_ecart(row):
                        restant = row['besoin_restant_tonnes']
                        if restant <= 0:
                            return "✅ Couvert"
                        elif restant < 10:
                            return f"🟡 -{restant:.1f} T"
                        else:
                            return f"🔴 -{restant:.1f} T"
                    
                    df_recap_disp['Statut'] = df_recap_disp.apply(format_ecart, axis=1)
                    df_recap_disp = df_recap_disp.rename(columns={
                        'produit_label': 'Produit',
                        'affecte_net_tonnes': 'Besoin NET (T)',
                        'stock_lave_tonnes': 'Stock LAVÉ (T)',
                        'jobs_net_estime': 'Jobs prévus (T)',
                        'besoin_restant_tonnes': 'Reste à laver (T)'
                    })
                    df_recap_disp = df_recap_disp[['Produit', 'Besoin NET (T)', 'Stock LAVÉ (T)', 'Jobs prévus (T)', 'Reste à laver (T)', 'Statut']]
                    
                    for col in ['Besoin NET (T)', 'Stock LAVÉ (T)', 'Jobs prévus (T)', 'Reste à laver (T)']:
                        df_recap_disp[col] = df_recap_disp[col].round(1)
                    
                    st.dataframe(
                        df_recap_disp,
                        use_container_width=True,
                        hide_index=True,
                        column_config={
                            "Produit": st.column_config.TextColumn("Produit", width="large"),
                            "Besoin NET (T)": st.column_config.NumberColumn("Besoin NET (T)", format="%.1f"),
                            "Stock LAVÉ (T)": st.column_config.NumberColumn("Stock LAVÉ (T)", format="%.1f"),
                            "Jobs prévus (T)": st.column_config.NumberColumn("Jobs prévus (T)", format="%.1f"),
                            "Reste à laver (T)": st.column_config.NumberColumn("Reste à laver (T)", format="%.1f"),
                            "Statut": st.column_config.TextColumn("Statut", width="small"),
                        }
                    )
            
            st.markdown("---")
            
            # ============ FILTRES ============
            col_f1, col_f2 = st.columns(2)
            
            with col_f1:
                # Filtre produit commercial
                if not recap_produits_df.empty:
                    produits_options = sorted(recap_produits_df['produit_label'].dropna().unique().tolist())
                    f_produit_besoins = st.multiselect(
                        "🔍 Filtrer par produit commercial",
                        produits_options,
                        key="f_produit_besoins",
                        placeholder="Tous les produits..."
                    )
                else:
                    f_produit_besoins = []
            
            with col_f2:
                # Filtre variété
                varietes_besoins = ["Toutes"] + sorted(besoins_df['variete'].dropna().unique().tolist())
                f_var_besoins = st.selectbox("🔍 Filtrer par variété", varietes_besoins, key="f_var_besoins")
            
            # Appliquer filtres
            df_besoins = besoins_df.copy()
            
            if f_produit_besoins:
                # Trouver les lot_id correspondant aux produits sélectionnés
                if not recap_produits_df.empty:
                    codes_produits_sel = recap_produits_df[
                        recap_produits_df['produit_label'].isin(f_produit_besoins)
                    ]['code_produit_commercial'].tolist()
                    # Filtrer les lots dont produits_liste contient au moins un produit sélectionné
                    mask_produit = df_besoins['produits_liste'].apply(
                        lambda pl: any(p.strip() in str(pl) for p in f_produit_besoins) if pd.notna(pl) else False
                    )
                    df_besoins = df_besoins[mask_produit]
            
            if f_var_besoins != "Toutes":
                df_besoins = df_besoins[df_besoins['variete'] == f_var_besoins]
            
            st.markdown(f"**{len(df_besoins)} lot(s) avec besoin de lavage**")
            st.caption("💡 Besoin NET = Affecté NET - Stock LAVÉ - Jobs prévus × 78%")
            
            # Préparer tableau
            df_display_besoins = df_besoins[[
                'lot_id', 'code_lot_interne', 'nom_usage', 'producteur', 'variete',
                'affecte_net_tonnes', 'stock_lave_tonnes', 'jobs_prevus_tonnes',
                'besoin_lavage_net_tonnes', 'pallox_brut_dispo', 'brut_dispo_tonnes', 'produits_liste'
            ]].copy()
            
            # Tronquer
            df_display_besoins['nom_usage'] = df_display_besoins['nom_usage'].apply(
                lambda x: (str(x)[:18] + '..') if pd.notna(x) and len(str(x)) > 20 else x
            )
            df_display_besoins['producteur'] = df_display_besoins['producteur'].apply(
                lambda x: (str(x)[:15] + '..') if pd.notna(x) and len(str(x)) > 17 else x
            )
            
            # Formater nombres
            for col in ['affecte_net_tonnes', 'stock_lave_tonnes', 'jobs_prevus_tonnes', 'besoin_lavage_net_tonnes', 'brut_dispo_tonnes']:
                df_display_besoins[col] = df_display_besoins[col].apply(lambda x: f"{x:.1f}")
            
            df_display_besoins = df_display_besoins.rename(columns={
                'code_lot_interne': 'Code Lot',
                'nom_usage': 'Nom',
                'producteur': 'Producteur',
                'variete': 'Variété',
                'affecte_net_tonnes': 'Affecté NET',
                'stock_lave_tonnes': 'Stock LAVÉ',
                'jobs_prevus_tonnes': 'Jobs prévus',
                'besoin_lavage_net_tonnes': '🎯 Besoin NET',
                'pallox_brut_dispo': 'BRUT dispo',
                'brut_dispo_tonnes': 'BRUT (T)'
            })
            df_display_besoins = df_display_besoins.reset_index(drop=True)
            
            column_config_besoins = {
                "lot_id": None,
                "produits_liste": None,
                "Code Lot": st.column_config.TextColumn("Code Lot", width="small"),
                "Nom": st.column_config.TextColumn("Nom", width="medium"),
                "Producteur": st.column_config.TextColumn("Producteur", width="medium"),
                "Variété": st.column_config.TextColumn("Variété", width="small"),
                "Affecté NET": st.column_config.TextColumn("Affecté (T)", width="small", help="Tonnes NET affectées"),
                "Stock LAVÉ": st.column_config.TextColumn("LAVÉ (T)", width="small", help="Stock déjà lavé"),
                "Jobs prévus": st.column_config.TextColumn("Jobs (T)", width="small", help="Jobs PRÉVU/EN_COURS"),
                "🎯 Besoin NET": st.column_config.TextColumn("🎯 Besoin", width="small", help="Besoin de lavage NET"),
                "BRUT dispo": st.column_config.NumberColumn("Pallox", format="%d", width="small", help="Pallox BRUT disponibles"),
                "BRUT (T)": st.column_config.TextColumn("BRUT (T)", width="small", help="Tonnes BRUT disponibles")
            }
            
            event_besoins = st.dataframe(
                df_display_besoins, 
                column_config=column_config_besoins, 
                use_container_width=True, 
                hide_index=True, 
                on_select="rerun", 
                selection_mode="single-row", 
                key="besoins_create"
            )
            
            selected_besoins = event_besoins.selection.rows if hasattr(event_besoins, 'selection') else []
            
            if len(selected_besoins) > 0:
                row_besoin = df_besoins.iloc[selected_besoins[0]]
                lot_id_besoin = int(row_besoin['lot_id'])
                
                st.markdown("---")
                st.success(f"✅ **{row_besoin['code_lot_interne']}** - {row_besoin['variete']} | Besoin NET: **{row_besoin['besoin_lavage_net_tonnes']:.1f} T**")
                
                # Afficher les produits concernés
                if row_besoin['produits_liste']:
                    st.caption(f"📦 Produits : {row_besoin['produits_liste']}")
                
                # Récupérer les emplacements BRUT disponibles pour ce lot
                emplacements_lot = lots_dispo[lots_dispo['lot_id'] == lot_id_besoin]
                
                if emplacements_lot.empty:
                    st.warning("⚠️ Aucun emplacement BRUT disponible pour ce lot")
                else:
                    st.markdown("##### 📍 Emplacements BRUT disponibles")
                    
                    # Tableau emplacements
                    emplacements_lot = emplacements_lot.reset_index(drop=True)
                    df_empl = emplacements_lot[['emplacement_id', 'site_stockage', 'emplacement_stockage', 'stock_total', 'pallox_reserves', 'nombre_unites', 'poids_total_kg', 'type_conditionnement']].copy()
                    df_empl = df_empl.rename(columns={
                        'site_stockage': 'Site',
                        'emplacement_stockage': 'Emplacement',
                        'stock_total': 'Stock',
                        'pallox_reserves': 'Réservés',
                        'nombre_unites': 'Dispo',
                        'poids_total_kg': 'Poids (kg)',
                        'type_conditionnement': 'Type'
                    })
                    df_empl = df_empl.reset_index(drop=True)
                    
                    event_empl = st.dataframe(
                        df_empl,
                        column_config={
                            "emplacement_id": None,
                            "Site": st.column_config.TextColumn("Site", width="small"),
                            "Emplacement": st.column_config.TextColumn("Empl.", width="small"),
                            "Stock": st.column_config.NumberColumn("Stock", format="%d"),
                            "Réservés": st.column_config.NumberColumn("Rés.", format="%d"),
                            "Dispo": st.column_config.NumberColumn("Dispo", format="%d"),
                            "Poids (kg)": st.column_config.NumberColumn("Poids", format="%.0f"),
                            "Type": st.column_config.TextColumn("Type", width="small")
                        },
                        use_container_width=True,
                        hide_index=True,
                        on_select="rerun",
                        selection_mode="single-row",
                        key="empl_besoins_create"
                    )
                    
                    selected_empl = event_empl.selection.rows if hasattr(event_empl, 'selection') else []
                    
                    if len(selected_empl) > 0:
                        empl_data = emplacements_lot.iloc[selected_empl[0]]
                        empl_id = int(empl_data['emplacement_id'])
                        dispo = int(empl_data['nombre_unites'])
                        
                        st.markdown("---")
                        st.info(f"📍 Emplacement sélectionné : **{empl_data['site_stockage']} / {empl_data['emplacement_stockage']}** - {dispo} pallox disponibles")
                        
                        # Calculer quantité suggérée basée sur le besoin
                        besoin_tonnes = float(row_besoin['besoin_lavage_net_tonnes'])
                        poids_unit = {'Pallox': 1900, 'Petit Pallox': 800, 'Big Bag': 1600}.get(empl_data['type_conditionnement'], 1900)
                        rendement = 0.78  # Rendement moyen
                        
                        # Pallox suggérés pour couvrir le besoin NET
                        pallox_suggeres = math.ceil(besoin_tonnes * 1000 / (poids_unit * rendement))
                        pallox_suggeres = min(pallox_suggeres, dispo)  # Limiter au dispo
                        
                        col1, col2 = st.columns(2)
                        with col1:
                            # number_input + 2 boutons rapides (Tout + Suggéré) via callbacks
                            qty_key_b = "qty_besoins_create"
                            if qty_key_b not in st.session_state:
                                st.session_state[qty_key_b] = min(pallox_suggeres, dispo)
                            # Plafonner si la valeur dépasse le dispo actuel
                            if st.session_state[qty_key_b] > dispo:
                                st.session_state[qty_key_b] = dispo
                            
                            def _set_qty_b_tout():
                                st.session_state[qty_key_b] = dispo
                            def _set_qty_b_suggere():
                                st.session_state[qty_key_b] = pallox_suggeres
                            
                            type_cond_b = empl_data.get('type_conditionnement') or 'Pallox'
                            st.caption(
                                f"💡 Suggéré : **{pallox_suggeres}p** pour couvrir {besoin_tonnes:.1f}T NET — "
                                f"📦 {type_cond_b} ({poids_unit} kg/p, rendement {int(rendement*100)}%)"
                            )
                            col_qty_b, col_btn_t, col_btn_s = st.columns([2, 1, 1])
                            with col_qty_b:
                                quantite = st.number_input(
                                    "Pallox à laver",
                                    min_value=1, max_value=dispo,
                                    step=1, key=qty_key_b
                                )
                            with col_btn_t:
                                st.markdown("<br>", unsafe_allow_html=True)
                                st.button(f"Tout ({dispo}p)", key="btn_besoins_tout",
                                          on_click=_set_qty_b_tout,
                                          use_container_width=True)
                            with col_btn_s:
                                st.markdown("<br>", unsafe_allow_html=True)
                                st.button(f"Suggéré ({pallox_suggeres}p)",
                                          key="btn_besoins_suggere",
                                          on_click=_set_qty_b_suggere,
                                          use_container_width=True)
                            
                            date_prevue = st.date_input("Date prévue", datetime.now().date(), key="date_besoins_create")
                        
                        with col2:
                            lignes = get_lignes_lavage()
                            ligne_opts = [f"{l['code']} ({l['capacite_th']} T/h)" for l in lignes]
                            ligne_sel = st.selectbox("Ligne de lavage", ligne_opts, key="ligne_besoins_create")
                            
                            ligne_idx = ligne_opts.index(ligne_sel)
                            capacite_ligne = float(lignes[ligne_idx]['capacite_th'])
                            
                            cadence = st.number_input(
                                "⚡ Cadence (T/h)",
                                min_value=0.5,
                                max_value=25.0,
                                value=float(capacite_ligne),
                                step=0.5,
                                key="cadence_besoins_create",
                                help=f"Capacité nominale ligne : {capacite_ligne} T/h. Max autorisé : 25 T/h."
                            )
                            
                            poids_brut = quantite * poids_unit
                            poids_net_estime = poids_brut * rendement
                            temps_estime = (poids_brut / 1000) / cadence
                            
                            st.metric("Poids BRUT", f"{poids_brut:,.0f} kg ({poids_brut/1000:.1f} T)")
                            st.metric("NET estimé (~78%)", f"{poids_net_estime:,.0f} kg ({poids_net_estime/1000:.1f} T)")
                            st.metric("Temps estimé", f"{temps_estime:.1f} h")
                        
                        notes = st.text_input("Notes (optionnel)", key="notes_besoins_create")
                        
                        # Widget des 5 infos métier (obligatoires)
                        infos_metier = ui_saisie_infos_metier_lavage(key_prefix="besoins")
                        
                        if st.button("✅ Créer Job de Lavage", type="primary",
                                    use_container_width=True, key="btn_create_besoins",
                                    disabled=not infos_metier['is_valid']):
                            ligne_code = lignes[ligne_idx]['code']
                            success, message = create_job_lavage(
                                lot_id_besoin, empl_id, quantite, poids_brut,
                                date_prevue, ligne_code, cadence, notes,
                                type_tapis=infos_metier['type_tapis'],
                                etiquette_grenailles=infos_metier['etiquette_grenailles'],
                                etiquette_pallox=infos_metier['etiquette_pallox'],
                                calibre_seuil=infos_metier['calibre_seuil'],
                            )
                            if success:
                                st.success(message)
                                st.balloons()
                                st.rerun()
                            else:
                                st.error(message)
                    else:
                        st.info("👆 Sélectionnez un emplacement ci-dessus pour créer le job")
            else:
                st.info("👆 Sélectionnez un lot dans le tableau ci-dessus pour voir les détails et créer un job")
    
    # ============================================================
    # SOUS-ONGLET 2 : TOUS LES LOTS BRUT
    # ============================================================
    with create_tab2:
        st.markdown("*Tous les emplacements BRUT disponibles — sélection simple ou multi-lot*")
        
        lots_dispo = get_lots_bruts_disponibles()
        
        if not lots_dispo.empty:
            # ── FILTRES ──────────────────────────────────────────
            st.markdown("#### 🔍 Filtres")
            col1, col2, col3 = st.columns(3)
            with col1:
                varietes = ["Toutes"] + sorted(lots_dispo['variete'].dropna().unique().tolist())
                f_var = st.selectbox("Variété", varietes, key="f_var_create")
            with col2:
                producteurs = ["Tous"] + sorted(lots_dispo['producteur'].dropna().unique().tolist())
                f_prod = st.selectbox("Producteur", producteurs, key="f_prod_create")
            with col3:
                sites = ["Tous"] + sorted(lots_dispo['site_stockage'].dropna().unique().tolist())
                f_site = st.selectbox("Site", sites, key="f_site_create")

            col4, col5, col6 = st.columns(3)
            with col4:
                # Filtre type : BRUT / GRENAILLES / Tous
                type_opts = ["Tous", "🔵 BRUT uniquement", "🟠 GRENAILLES uniquement"]
                f_type = st.selectbox("Type stock", type_opts, key="f_type_create")
            with col5:
                # Filtre calibre min/max
                cal_min_vals = lots_dispo['calibre_min'].dropna()
                cal_max_vals = lots_dispo['calibre_max'].dropna()
                if not cal_min_vals.empty and not cal_max_vals.empty:
                    cal_global_min = int(cal_min_vals.min())
                    cal_global_max = int(cal_max_vals.max())
                    f_cal = st.slider("Calibre (mm)", cal_global_min, cal_global_max,
                                      (cal_global_min, cal_global_max), key="f_cal_create")
                else:
                    f_cal = None
            with col6:
                # Filtre produit commercial affecté
                produits_dispo = set()
                for p in lots_dispo['produits_affectes'].dropna():
                    for pp in str(p).split(','):
                        pp = pp.strip()
                        if pp:
                            produits_dispo.add(pp)
                produits_opts = sorted(produits_dispo)
                f_produit = st.multiselect("Produit affecté", produits_opts,
                                           key="f_produit_create",
                                           placeholder="Tous les produits...")

            lots_f = lots_dispo.copy()
            if f_var != "Toutes":
                lots_f = lots_f[lots_f['variete'] == f_var]
            if f_prod != "Tous":
                lots_f = lots_f[lots_f['producteur'] == f_prod]
            if f_site != "Tous":
                lots_f = lots_f[lots_f['site_stockage'] == f_site]
            if f_type == "🔵 BRUT uniquement":
                lots_f = lots_f[lots_f['statut_lavage'] == 'BRUT']
            elif f_type == "🟠 GRENAILLES uniquement":
                lots_f = lots_f[lots_f['statut_lavage'] == 'GRENAILLES_BRUTES']
            if f_cal:
                cal_lo, cal_hi = f_cal
                lots_f = lots_f[
                    (lots_f['calibre_min'].fillna(0) <= cal_hi) &
                    (lots_f['calibre_max'].fillna(999) >= cal_lo)
                ]
            if f_produit:
                mask_prod = lots_f['produits_affectes'].apply(
                    lambda x: any(p in str(x) for p in f_produit) if pd.notna(x) else False)
                lots_f = lots_f[mask_prod]
            
            st.markdown("---")
            
            if not lots_f.empty:
                st.markdown(f"**{len(lots_f)} emplacement(s)** — Sélection simple ou **multi-lignes** pour batch")
                st.caption("🔵 BRUT | 🟠 GRENAILLES_BRUTES — Ctrl+clic ou Shift+clic pour sélection multiple")

                POIDS_UNIT_MAP = {'Pallox': 1900, 'Petit Pallox': 800, 'Big Bag': 1600}

                df_display = lots_f[[
                    'lot_id', 'emplacement_id', 'code_lot_interne', 'nom_usage',
                    'producteur', 'variete', 'calibre_min', 'calibre_max',
                    'statut_lavage', 'site_stockage', 'emplacement_stockage',
                    'stock_total', 'pallox_reserves', 'nombre_unites',
                    'poids_total_kg', 'type_conditionnement', 'produits_affectes'
                ]].copy()

                df_display['Cal.'] = df_display.apply(
                    lambda r: f"{int(r['calibre_min'])}-{int(r['calibre_max'])}"
                    if pd.notna(r['calibre_min']) and pd.notna(r['calibre_max']) else "-", axis=1)
                df_display['statut_lavage'] = df_display['statut_lavage'].apply(
                    lambda x: '🔵 BRUT' if x == 'BRUT' else ('🟠 GREN' if x == 'GRENAILLES_BRUTES' else x))
                df_display['produits_affectes'] = df_display['produits_affectes'].apply(
                    lambda x: str(x)[:30] + '..' if pd.notna(x) and len(str(x)) > 32 else (x if pd.notna(x) else '—'))
                df_display['producteur'] = df_display['producteur'].apply(
                    lambda x: (str(x)[:14] + '..') if pd.notna(x) and len(str(x)) > 16 else x)

                df_display = df_display.rename(columns={
                    'code_lot_interne': 'Code Lot', 'nom_usage': 'Nom Lot',
                    'producteur': 'Producteur', 'variete': 'Variété',
                    'statut_lavage': 'Type', 'site_stockage': 'Site',
                    'emplacement_stockage': 'Empl.',
                    'stock_total': 'Stock', 'pallox_reserves': 'Rés.',
                    'nombre_unites': 'Dispo', 'poids_total_kg': 'Poids (kg)',
                    'produits_affectes': 'Produit affecté'
                }).reset_index(drop=True)

                column_config_t2 = {
                    "lot_id": None, "emplacement_id": None,
                    "calibre_min": None, "calibre_max": None,
                    "type_conditionnement": None,
                    "Code Lot": st.column_config.TextColumn("Code Lot", width="small"),
                    "Nom Lot": st.column_config.TextColumn("Nom", width="medium"),
                    "Producteur": st.column_config.TextColumn("Producteur", width="small"),
                    "Variété": st.column_config.TextColumn("Variété", width="small"),
                    "Cal.": st.column_config.TextColumn("Cal.(mm)", width="small"),
                    "Type": st.column_config.TextColumn("Type", width="small"),
                    "Site": st.column_config.TextColumn("Site", width="small"),
                    "Empl.": st.column_config.TextColumn("Empl.", width="small"),
                    "Stock": st.column_config.NumberColumn("Stock", format="%d"),
                    "Rés.": st.column_config.NumberColumn("Rés.", format="%d"),
                    "Dispo": st.column_config.NumberColumn("Dispo", format="%d"),
                    "Poids (kg)": st.column_config.NumberColumn("Poids kg", format="%.0f"),
                    "Produit affecté": st.column_config.TextColumn("Produit affecté", width="medium"),
                }

                event_t2 = st.dataframe(
                    df_display, column_config=column_config_t2,
                    use_container_width=True, hide_index=True,
                    on_select="rerun", selection_mode="multi-row",
                    key="lots_create"
                )

                selected_rows = event_t2.selection.rows if hasattr(event_t2, 'selection') else []

                if selected_rows:
                    st.markdown("---")
                    is_batch = len(selected_rows) > 1

                    # Récupérer les données de chaque ligne sélectionnée
                    lots_sel_data = []
                    for idx in selected_rows:
                        row_d = df_display.iloc[idx]
                        raw = lots_dispo[
                            (lots_dispo['lot_id'] == row_d['lot_id']) &
                            (lots_dispo['emplacement_id'] == row_d['emplacement_id'])
                        ]
                        if not raw.empty:
                            lots_sel_data.append(raw.iloc[0])

                    if not lots_sel_data:
                        st.warning("Aucune donnée récupérée")
                    else:
                        # ── Récap sélection ──
                        if is_batch:
                            st.info(f"📦 **{len(lots_sel_data)} lots sélectionnés** — Création d'un job batch")
                            recap_rows = []
                            for ld in lots_sel_data:
                                dispo_l = int(ld['nombre_unites'])
                                recap_rows.append({
                                    'Code Lot': ld['code_lot_interne'],
                                    'Variété': ld['variete'],
                                    'Calibre': f"{int(ld['calibre_min']) if pd.notna(ld['calibre_min']) else '?'}-{int(ld['calibre_max']) if pd.notna(ld['calibre_max']) else '?'}",
                                    'Dispo': dispo_l,
                                    'Poids dispo (T)': round(float(ld['poids_total_kg']) / 1000, 1),
                                })
                            st.dataframe(pd.DataFrame(recap_rows), hide_index=True, use_container_width=True)
                        else:
                            ld = lots_sel_data[0]
                            reserves = int(ld['pallox_reserves']) if pd.notna(ld['pallox_reserves']) else 0
                            dispo_s = int(ld['nombre_unites'])
                            type_emoji = '🔵' if ld['statut_lavage'] == 'BRUT' else '🟠'
                            if reserves > 0:
                                st.warning(f"⚠️ {type_emoji} **{ld['code_lot_interne']}** | {int(ld['stock_total'])} total, {reserves} réservés, **{dispo_s} dispo**")
                            else:
                                st.success(f"✅ {type_emoji} **{ld['code_lot_interne']}** — {ld['variete']} | **{dispo_s} pallox disponibles**")

                        # ── Paramètres communs ──
                        col_p1, col_p2 = st.columns(2)
                        with col_p1:
                            date_prevue_t2 = st.date_input("Date prévue", datetime.now().date(), key="date_create_t2")
                        with col_p2:
                            lignes_t2 = get_lignes_lavage()
                            ligne_opts_t2 = [f"{l['code']} ({l['capacite_th']} T/h)" for l in lignes_t2]
                            ligne_sel_t2 = st.selectbox("Ligne de lavage", ligne_opts_t2, key="ligne_create_t2")
                            ligne_idx_t2 = ligne_opts_t2.index(ligne_sel_t2)
                            cap_ligne_t2 = float(lignes_t2[ligne_idx_t2]['capacite_th'])

                        cadence_t2 = st.number_input(
                            "⚡ Cadence (T/h)",
                            min_value=0.5, max_value=25.0,
                            value=float(cap_ligne_t2), step=0.5, key="cadence_create_t2",
                            help=f"Capacité nominale ligne : {cap_ligne_t2} T/h. Max autorisé : 25 T/h.")

                        notes_t2 = st.text_input("Notes (optionnel)", key="notes_create_t2")

                        # ── Saisie quantités par lot ──
                        if is_batch:
                            st.markdown("##### 📦 Quantités par lot")
                        qtys = {}
                        TYPES_COND_BATCH = ["Pallox", "Petit Pallox", "Big Bag"]
                        for ld in lots_sel_data:
                            dispo_l = int(ld['nombre_unites'])
                            type_cond_bdd = str(ld.get('type_conditionnement', '')) or 'Pallox'
                            if is_batch:
                                # Label enrichi : code_lot — variété — producteur — site/empl
                                prod_l = str(ld.get('producteur', '') or '')
                                site_l = str(ld.get('site_stockage', '') or '')
                                empl_l = str(ld.get('emplacement_stockage', '') or '')
                                loc_str = ""
                                if site_l or empl_l:
                                    loc_str = f" — 📍 {site_l}/{empl_l}".rstrip('/')
                                prod_str = f" — 👤 {prod_l}" if prod_l else ""
                                
                                st.markdown(
                                    f"**{ld['code_lot_interne']}** — {ld['variete']}"
                                    f"{prod_str}{loc_str}"
                                )
                                col_q1, col_q2, col_q3 = st.columns([1.5, 1, 1])
                                with col_q1:
                                    # Selectbox type_conditionnement, pré-sélectionné sur valeur BDD
                                    default_idx = TYPES_COND_BATCH.index(type_cond_bdd) if type_cond_bdd in TYPES_COND_BATCH else 0
                                    type_cond_l = st.selectbox(
                                        "Type cond.",
                                        TYPES_COND_BATCH,
                                        index=default_idx,
                                        key=f"type_batch_{ld['lot_id']}_{ld['emplacement_id']}"
                                    )
                                with col_q2:
                                    # poids unit dépend du type cond sélectionné (peut changer si user override)
                                    poids_unit_l = POIDS_UNIT_MAP.get(type_cond_l, 1900)
                                    qty_l = st.number_input(
                                        "Pallox", 1, dispo_l,
                                        min(dispo_l, max(1, dispo_l)),
                                        key=f"qty_batch_{ld['lot_id']}_{ld['emplacement_id']}")
                                with col_q3:
                                    poids_l = qty_l * poids_unit_l
                                    st.metric("Poids", f"{poids_l/1000:.1f} T")
                                qtys[ld['lot_id']] = (qty_l, poids_l, ld, type_cond_l)
                                st.markdown("<hr style='margin:0.3rem 0;border:none;border-top:1px solid #eee;'>", unsafe_allow_html=True)
                            else:
                                # MONO-LOT inchangé
                                poids_unit_l = POIDS_UNIT_MAP.get(type_cond_bdd, 1900)
                                # number_input + bouton "Tout" via callback (pas de st.rerun manuel)
                                qty_key_t2 = "qty_create_t2_single"
                                if qty_key_t2 not in st.session_state:
                                    st.session_state[qty_key_t2] = min(5, dispo_l)
                                # Plafonner si la valeur en session dépasse le dispo actuel
                                if st.session_state[qty_key_t2] > dispo_l:
                                    st.session_state[qty_key_t2] = dispo_l
                                
                                def _set_qty_t2_tout():
                                    st.session_state[qty_key_t2] = dispo_l
                                
                                col_qty, col_btn = st.columns([3, 1])
                                with col_qty:
                                    qty_l = st.number_input(
                                        f"Pallox à laver ({ld.get('type_conditionnement') or 'Pallox'} — {poids_unit_l} kg/p)",
                                        min_value=1, max_value=dispo_l,
                                        step=1, key=qty_key_t2
                                    )
                                with col_btn:
                                    st.markdown("<br>", unsafe_allow_html=True)
                                    st.button(f"Tout ({dispo_l}p)", key="btn_t2_tout",
                                              on_click=_set_qty_t2_tout,
                                              use_container_width=True)
                                
                                poids_l = qty_l * poids_unit_l
                                col_m1, col_m2 = st.columns(2)
                                col_m1.metric("Poids total", f"{poids_l:,.0f} kg")
                                col_m2.metric("Temps estimé", f"{(poids_l/1000)/cadence_t2:.1f} h")
                                qtys[ld['lot_id']] = (qty_l, poids_l, ld)

                        # ── Récap batch ──
                        if is_batch:
                            total_poids_batch = sum(v[1] for v in qtys.values()) / 1000
                            temps_batch = total_poids_batch / cadence_t2
                            col_b1, col_b2, col_b3 = st.columns(3)
                            col_b1.metric("Poids total batch", f"{total_poids_batch:.1f} T")
                            col_b2.metric("Temps estimé", f"{temps_batch:.1f} h")
                            col_b3.metric("Nb lots", len(qtys))

                        # Widget des 5 infos métier (obligatoires)
                        infos_metier_t2 = ui_saisie_infos_metier_lavage(key_prefix="lots_brut")

                        # ── Bouton création ──
                        label_btn = "✅ Créer Batch" if is_batch else "✅ Créer Job"
                        if st.button(label_btn, type="primary",
                                     use_container_width=True, key="btn_create_t2",
                                     disabled=not infos_metier_t2['is_valid']):
                            ligne_code_t2 = lignes_t2[ligne_idx_t2]['code']
                            if is_batch:
                                lots_for_batch = [
                                    {
                                        'lot_id': ld['lot_id'],
                                        'emplacement_id': ld['emplacement_id'],
                                        'quantite_pallox': qtys[ld['lot_id']][0],
                                        'poids_brut_kg': qtys[ld['lot_id']][1],
                                        'type_conditionnement': qtys[ld['lot_id']][3],
                                    }
                                    for ld in lots_sel_data
                                ]
                                ok_b, msg_b, _ = create_batch_jobs(
                                    lots_for_batch, date_prevue_t2,
                                    ligne_code_t2, cadence_t2, notes_t2,
                                    type_tapis=infos_metier_t2['type_tapis'],
                                    etiquette_grenailles=infos_metier_t2['etiquette_grenailles'],
                                    etiquette_pallox=infos_metier_t2['etiquette_pallox'],
                                    calibre_seuil=infos_metier_t2['calibre_seuil'],
                                )
                                if ok_b:
                                    st.success(msg_b)
                                    st.balloons()
                                    st.rerun()
                                else:
                                    st.error(msg_b)
                            else:
                                ld = lots_sel_data[0]
                                qty_s, poids_s, _ = qtys[ld['lot_id']]
                                ok_s, msg_s = create_job_lavage(
                                    ld['lot_id'], ld['emplacement_id'],
                                    qty_s, poids_s,
                                    date_prevue_t2, ligne_code_t2,
                                    cadence_t2, notes_t2,
                                    type_tapis=infos_metier_t2['type_tapis'],
                                    etiquette_grenailles=infos_metier_t2['etiquette_grenailles'],
                                    etiquette_pallox=infos_metier_t2['etiquette_pallox'],
                                    calibre_seuil=infos_metier_t2['calibre_seuil'],
                                )
                                if ok_s:
                                    st.success(msg_s)
                                    st.balloons()
                                    st.rerun()
                                else:
                                    st.error(msg_s)
                else:
                    st.info("👆 Sélectionnez un ou plusieurs lots (Ctrl+clic) pour créer un job ou un batch")
            else:
                st.warning("Aucun lot avec ces filtres")
        else:
            st.warning("Aucun lot BRUT disponible")

# ============================================================
# ONGLET 4 : IMPRIMER
# ============================================================

with tab4:
    st.subheader("🖨️ Imprimer Planning Journée")
    st.caption("*Générer une fiche imprimable pour une équipe de lavage*")
    
    col1, col2, col3 = st.columns(3)
    
    # Charger les lignes de lavage
    lignes_print = get_lignes_lavage()
    
    with col1:
        date_print = st.date_input("📅 Jour", datetime.now().date(), key="print_date")
    
    with col2:
        if lignes_print:
            ligne_print_options = [f"{l['code']} - {l['libelle']} ({l['capacite_th']}T/h)" for l in lignes_print]
            selected_ligne_print = st.selectbox("🔵 Ligne de lavage", ligne_print_options, key="print_ligne")
            ligne_print_idx = ligne_print_options.index(selected_ligne_print)
            ligne_print_code = lignes_print[ligne_print_idx]['code']
            ligne_print_libelle = lignes_print[ligne_print_idx]['libelle']
            ligne_print_capacite = lignes_print[ligne_print_idx]['capacite_th']
        else:
            st.warning("Aucune ligne de lavage")
            ligne_print_code = None
    
    with col3:
        amplitude_options = ["Journée 24h (00h-23h59)", "Journée complète (5h-22h)", "Matin (5h-13h)", "Après-midi (13h-22h)", "Nuit (22h-06h)"]
        selected_amplitude = st.selectbox("⏰ Amplitude", amplitude_options, key="print_amplitude")
        
        if selected_amplitude == "Matin (5h-13h)":
            heure_debut_print = time(5, 0)
            heure_fin_print = time(13, 0)
        elif selected_amplitude == "Après-midi (13h-22h)":
            heure_debut_print = time(13, 0)
            heure_fin_print = time(22, 0)
        elif selected_amplitude == "Nuit (22h-06h)":
            # Plage chevauchant minuit : on imprime 22h00 → 23h59 + 00h00 → 06h00 sur le même PDF
            heure_debut_print = time(22, 0)
            heure_fin_print = time(6, 0)
        elif selected_amplitude == "Journée complète (5h-22h)":
            heure_debut_print = time(5, 0)
            heure_fin_print = time(22, 0)
        else:
            # Journée 24h (par défaut maintenant)
            heure_debut_print = time(0, 0)
            heure_fin_print = time(23, 59)
    
    st.markdown("---")
    
    # Charger les éléments planifiés pour ce jour/ligne
    if ligne_print_code:
        try:
            conn = get_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT 
                    lpe.id,
                    lpe.type_element,
                    lpe.heure_debut,
                    lpe.heure_fin,
                    lpe.duree_minutes,
                    lpe.ordre_jour,
                    lj.id as job_id,
                    lj.code_lot_interne,
                    lj.variete,
                    lj.quantite_pallox,
                    lj.poids_brut_kg,
                    lj.statut as job_statut,
                    ltc.libelle as custom_libelle,
                    ltc.emoji as custom_emoji
                FROM lavages_planning_elements lpe
                LEFT JOIN lavages_jobs lj ON lpe.job_id = lj.id
                LEFT JOIN lavages_temps_customs ltc ON lpe.temps_custom_id = ltc.id
                WHERE lpe.date_prevue = %s 
                  AND lpe.ligne_lavage = %s
                ORDER BY lpe.heure_debut, lpe.ordre_jour
            """, (date_print, ligne_print_code))
            
            elements_print = cursor.fetchall()
            cursor.close()
            conn.close()
            
            # Filtrer par amplitude horaire
            elements_filtres = []
            for el in elements_print:
                if el['heure_debut']:
                    h = el['heure_debut']
                    if isinstance(h, str):
                        h = datetime.strptime(h, "%H:%M:%S").time()
                    if heure_debut_print <= h < heure_fin_print:
                        elements_filtres.append(el)
                else:
                    elements_filtres.append(el)
            
            # Aperçu
            jour_fr = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"]
            jour_nom = jour_fr[date_print.weekday()]
            st.markdown(f"### 📋 Aperçu : {jour_nom} {date_print.strftime('%d/%m/%Y')} - {ligne_print_libelle}")
            st.markdown(f"**Amplitude** : {heure_debut_print.strftime('%H:%M')} → {heure_fin_print.strftime('%H:%M')} | **Capacité** : {ligne_print_capacite} T/h")
            
            if elements_filtres:
                st.markdown("---")
                
                for el in elements_filtres:
                    heure_deb = el['heure_debut'].strftime('%H:%M') if el['heure_debut'] else "--:--"
                    heure_f = el['heure_fin'].strftime('%H:%M') if el['heure_fin'] else "--:--"
                    duree = el['duree_minutes'] or 0
                    
                    if el['type_element'] == 'JOB':
                        statut_emoji = "🟢" if el['job_statut'] == 'PRÉVU' else ("🟠" if el['job_statut'] == 'EN_COURS' else "✅")
                        poids_t = (el['poids_brut_kg'] or 0) / 1000
                        st.markdown(f"""
                        **{heure_deb} → {heure_f}** ({duree} min) {statut_emoji}  
                        📦 **Job #{el['job_id']}** - {el['code_lot_interne']}  
                        🥔 {el['variete']}  
                        ⚖️ {el['quantite_pallox']} pallox ({poids_t:.2f} T)
                        """)
                    else:
                        st.markdown(f"""
                        **{heure_deb} → {heure_f}** ({duree} min)  
                        {el['custom_emoji'] or '⚙️'} **{el['custom_libelle']}**
                        """)
                    st.markdown("---")
                
                # Calcul temps total
                temps_total_min = sum(el['duree_minutes'] or 0 for el in elements_filtres)
                temps_jobs = sum(el['duree_minutes'] or 0 for el in elements_filtres if el['type_element'] == 'JOB')
                nb_jobs = len([el for el in elements_filtres if el['type_element'] == 'JOB'])
                poids_total = sum((el['poids_brut_kg'] or 0) for el in elements_filtres if el['type_element'] == 'JOB') / 1000
                
                st.markdown(f"**Résumé** : {nb_jobs} job(s) | {poids_total:.1f} T | Temps total : {temps_total_min} min ({temps_total_min/60:.1f}h)")
                
                st.markdown("---")
                
                # Bouton imprimer avec HTML
                if st.button("🖨️ Générer fiche imprimable", type="primary", use_container_width=True):
                    
                    # Générer HTML
                    rows_html = ""
                    for el in elements_filtres:
                        heure_deb = el['heure_debut'].strftime('%H:%M') if el['heure_debut'] else "--:--"
                        heure_f = el['heure_fin'].strftime('%H:%M') if el['heure_fin'] else "--:--"
                        duree = el['duree_minutes'] or 0
                        
                        if el['type_element'] == 'JOB':
                            statut = el['job_statut'] or ''
                            poids_t = (el['poids_brut_kg'] or 0) / 1000
                            rows_html += f"""
                            <tr>
                                <td style="text-align:center;font-weight:bold;">{heure_deb}</td>
                                <td style="text-align:center;">{heure_f}</td>
                                <td style="text-align:center;">{duree}</td>
                                <td>Job #{el['job_id']} - {el['code_lot_interne']}</td>
                                <td>{el['variete']}</td>
                                <td style="text-align:center;">{el['quantite_pallox']}</td>
                                <td style="text-align:center;">{poids_t:.2f} T</td>
                                <td style="text-align:center;">{statut}</td>
                                <td></td>
                            </tr>
                            """
                        else:
                            rows_html += f"""
                            <tr style="background-color:#e8f5e9;">
                                <td style="text-align:center;font-weight:bold;">{heure_deb}</td>
                                <td style="text-align:center;">{heure_f}</td>
                                <td style="text-align:center;">{duree}</td>
                                <td colspan="5">{el['custom_emoji'] or '⚙️'} {el['custom_libelle']}</td>
                                <td></td>
                            </tr>
                            """
                    
                    amplitude_txt = f"{heure_debut_print.strftime('%H:%M')} - {heure_fin_print.strftime('%H:%M')}"
                    jour_txt = f"{jour_nom} {date_print.strftime('%d/%m/%Y')}"
                    
                    html_content = f"""
                    <!DOCTYPE html>
                    <html>
                    <head>
                        <meta charset="UTF-8">
                        <title>Planning Lavage - {jour_txt}</title>
                        <style>
                            body {{ font-family: Arial, sans-serif; margin: 20px; font-size: 12px; }}
                            h1 {{ text-align: center; color: #333; margin-bottom: 5px; font-size: 18px; }}
                            h2 {{ text-align: center; color: #666; margin-top: 0; font-size: 14px; }}
                            .header-info {{ display: flex; justify-content: space-between; margin-bottom: 15px; padding: 10px; background: #f5f5f5; border-radius: 5px; }}
                            .header-info div {{ text-align: center; }}
                            .header-info strong {{ display: block; font-size: 14px; }}
                            table {{ width: 100%; border-collapse: collapse; margin-top: 10px; }}
                            th {{ background: #1976d2; color: white; padding: 8px; text-align: left; font-size: 11px; }}
                            td {{ border: 1px solid #ddd; padding: 6px; font-size: 11px; }}
                            tr:nth-child(even) {{ background: #fafafa; }}
                            .footer {{ margin-top: 20px; text-align: center; font-size: 10px; color: #999; }}
                            .signature {{ margin-top: 30px; display: flex; justify-content: space-around; }}
                            .signature div {{ width: 200px; border-top: 1px solid #333; padding-top: 5px; text-align: center; }}
                            @media print {{
                                body {{ margin: 10px; }}
                                .no-print {{ display: none; }}
                            }}
                        </style>
                    </head>
                    <body>
                        <h1>🧼 Planning Lavage</h1>
                        <h2>{ligne_print_libelle} ({ligne_print_code})</h2>
                        
                        <div class="header-info">
                            <div><strong>📅 Date</strong>{jour_txt}</div>
                            <div><strong>⏰ Amplitude</strong>{amplitude_txt}</div>
                            <div><strong>⚡ Capacité</strong>{ligne_print_capacite} T/h</div>
                            <div><strong>📦 Jobs</strong>{nb_jobs}</div>
                            <div><strong>⚖️ Tonnage</strong>{poids_total:.1f} T</div>
                        </div>
                        
                        <table>
                            <thead>
                                <tr>
                                    <th style="width:60px;">Début</th>
                                    <th style="width:60px;">Fin</th>
                                    <th style="width:50px;">Durée</th>
                                    <th>Lot / Opération</th>
                                    <th>Variété</th>
                                    <th style="width:60px;">Pallox</th>
                                    <th style="width:60px;">Poids</th>
                                    <th style="width:70px;">Statut</th>
                                    <th style="width:80px;">Validé ✓</th>
                                </tr>
                            </thead>
                            <tbody>
                                {rows_html}
                            </tbody>
                        </table>
                        
                        <div class="signature">
                            <div>Chef d'équipe</div>
                            <div>Opérateur lavage</div>
                            <div>Contrôle qualité</div>
                        </div>
                        
                        <div class="footer">
                            Imprimé le {datetime.now().strftime('%d/%m/%Y à %H:%M')} - Culture Pom
                        </div>
                        
                        <script>
                            window.onload = function() {{ window.print(); }}
                        </script>
                    </body>
                    </html>
                    """
                    
                    # Encodage base64 : evite tout conflit backtick/accolades dans le JS
                    import base64
                    html_b64 = base64.b64encode(html_content.encode('utf-8')).decode('ascii')
                    
                    stc.html(f"""
                    <button onclick="openPrint()" style="background:#AFCA0A;color:white;border:none;padding:10px 24px;border-radius:5px;cursor:pointer;font-size:14px;font-weight:bold;">
                        Ouvrir fenetre d'impression
                    </button>
                    <script>
                        function openPrint() {{
                            var b64 = "{html_b64}";
                            var html = decodeURIComponent(escape(atob(b64)));
                            var win = window.open('', '_blank');
                            win.document.open();
                            win.document.write(html);
                            win.document.close();
                        }}
                    </script>
                    """, height=60)
                    
                    st.success("✅ Cliquez sur le bouton ci-dessus pour ouvrir la fiche imprimable")
            
            else:
                st.info(f"📭 Aucun élément planifié pour {date_print.strftime('%d/%m/%Y')} sur {ligne_print_libelle} ({heure_debut_print.strftime('%H:%M')}-{heure_fin_print.strftime('%H:%M')})")
        
        except Exception as e:
            st.error(f"❌ Erreur : {str(e)}")

# ============================================================
# ONGLET 5 : ADMIN
# ============================================================

with tab5:
    if not is_admin():
        st.warning("⚠️ Accès réservé aux administrateurs")
    else:
        st.subheader("⚙️ Administration")
        
        admin_tab1, admin_tab2, admin_tab3 = st.tabs(["🗑️ Gestion Jobs", "🔧 Temps Customs", "📊 Statistiques"])
        
        # --- GESTION JOBS ---
        with admin_tab1:
            st.markdown("### 🗑️ Gestion des Jobs")
            
            col_prevus, col_encours, col_termines = st.columns(3)
            
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
                    jobs_prevus = cursor.fetchall()
                    cursor.close()
                    conn.close()
                    
                    if jobs_prevus:
                        for job in jobs_prevus:
                            col_info, col_btn = st.columns([4, 1])
                            with col_info:
                                st.markdown(f"**#{job['id']}** {job['variete']} {job['quantite_pallox']}p")
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
                    jobs_encours = cursor.fetchall()
                    cursor.close()
                    conn.close()
                    
                    if jobs_encours:
                        for job in jobs_encours:
                            col_info, col_btn = st.columns([4, 1])
                            with col_info:
                                st.markdown(f"**#{job['id']}** {job['variete']} {job['quantite_pallox']}p")
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
                    jobs_termines = cursor.fetchall()
                    cursor.close()
                    conn.close()
                    
                    if jobs_termines:
                        for job in jobs_termines:
                            col_info, col_btn = st.columns([4, 1])
                            with col_info:
                                rend = f"{job['rendement_pct']:.1f}%" if job['rendement_pct'] else "N/A"
                                st.markdown(f"**Job #{job['id']}** - {job['code_lot_interne']} - Rend: {rend}")
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
            temps_customs = get_temps_customs()
            for tc in temps_customs:
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

show_footer()
