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

def get_jobs_a_placer(ligne_lavage=None):
    """Récupère les jobs PRÉVU, filtrés par ligne si précisé"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        if ligne_lavage:
            cursor.execute("""
                SELECT 
                    lj.id, lj.lot_id, lj.code_lot_interne, lj.variete,
                    lj.quantite_pallox, lj.poids_brut_kg, lj.temps_estime_heures,
                    lj.date_prevue, lj.ligne_lavage as ligne_origine, lj.statut,
                    lj.statut_source,
                    COALESCE(p.nom, lj.producteur) as producteur
                FROM lavages_jobs lj
                LEFT JOIN lots_bruts lb ON lj.lot_id = lb.id
                LEFT JOIN ref_producteurs p ON lb.code_producteur = p.code_producteur
                WHERE lj.statut = 'PRÉVU'
                  AND lj.ligne_lavage = %s
                ORDER BY lj.date_prevue, lj.id
            """, (ligne_lavage,))
        else:
            cursor.execute("""
                SELECT 
                    lj.id, lj.lot_id, lj.code_lot_interne, lj.variete,
                    lj.quantite_pallox, lj.poids_brut_kg, lj.temps_estime_heures,
                    lj.date_prevue, lj.ligne_lavage as ligne_origine, lj.statut,
                    lj.statut_source,
                    COALESCE(p.nom, lj.producteur) as producteur
                FROM lavages_jobs lj
                LEFT JOIN lots_bruts lb ON lj.lot_id = lb.id
                LEFT JOIN ref_producteurs p ON lb.code_producteur = p.code_producteur
                WHERE lj.statut = 'PRÉVU'
                ORDER BY lj.date_prevue, lj.id
            """)
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
    """Récupère le planning d'une semaine donnée"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT 
                pe.id, pe.type_element, pe.job_id, pe.temps_custom_id,
                pe.date_prevue, pe.ligne_lavage, pe.ordre_jour,
                pe.heure_debut, pe.heure_fin, pe.duree_minutes,
                lj.id as lj_id, lj.code_lot_interne, lj.variete, lj.quantite_pallox,
                lj.poids_brut_kg, lj.capacite_th, lj.statut as job_statut,
                lj.date_activation, lj.date_terminaison,
                lj.temps_estime_heures, lj.statut_source, lj.emplacement_id,
                COALESCE(p.nom, lj.producteur) as producteur,
                se.site_stockage as empl_site,
                se.emplacement_stockage as empl_code,
                STRING_AGG(DISTINCT pc.marque || ' ' || pc.libelle, ', ') as produits_affectes,
                tc.libelle as custom_libelle, tc.emoji as custom_emoji
            FROM lavages_planning_elements pe
            LEFT JOIN lavages_jobs lj ON pe.job_id = lj.id
            LEFT JOIN lots_bruts lb ON lj.lot_id = lb.id
            LEFT JOIN ref_producteurs p ON lb.code_producteur = p.code_producteur
            LEFT JOIN stock_emplacements se ON lj.emplacement_id = se.id
            LEFT JOIN previsions_affectations pa ON pa.lot_id = lj.lot_id
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
                lj.temps_estime_heures, lj.statut_source, lj.emplacement_id,
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


def deplacer_element_planning(element_id, nouvelle_date, nouvelle_heure, planning_df, ligne_lavage, horaires_config):
    """
    Déplace un élément du planning vers un nouveau créneau.
    Décale en cascade tous les éléments suivants du même jour/ligne
    dont l'heure_debut < nouvelle heure de fin du job déplacé.
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Récupérer l'élément à déplacer
        cursor.execute("""
            SELECT id, duree_minutes, ligne_lavage, annee, semaine
            FROM lavages_planning_elements
            WHERE id = %s
        """, (element_id,))
        elem = cursor.fetchone()
        if not elem:
            return False, "❌ Élément introuvable"

        duree = int(elem['duree_minutes'])

        # Calculer nouvelle heure_fin
        debut_min = nouvelle_heure.hour * 60 + nouvelle_heure.minute
        fin_min = debut_min + duree
        nouvelle_heure_fin = time(min(23, fin_min // 60), fin_min % 60)

        # Recalculer annee/semaine selon la nouvelle date
        nouvelle_annee, nouvelle_semaine, _ = nouvelle_date.isocalendar()

        # Mettre à jour l'élément déplacé
        cursor.execute("""
            UPDATE lavages_planning_elements
            SET date_prevue = %s,
                heure_debut = %s,
                heure_fin = %s,
                annee = %s,
                semaine = %s
            WHERE id = %s
        """, (nouvelle_date, nouvelle_heure, nouvelle_heure_fin,
              nouvelle_annee, nouvelle_semaine, element_id))

        # Cascade : uniquement les éléments dont heure_debut >= debut du job déplacé
        # Les éléments AVANT ne sont jamais touchés
        cursor.execute("""
            SELECT id, heure_debut, heure_fin, duree_minutes
            FROM lavages_planning_elements
            WHERE date_prevue = %s
              AND ligne_lavage = %s
              AND id != %s
              AND heure_debut >= %s
            ORDER BY heure_debut
        """, (nouvelle_date, ligne_lavage, element_id, nouvelle_heure))
        suivants = cursor.fetchall()

        # Décaler en cascade uniquement les éléments qui chevauchent la nouvelle position
        curseur_temps = fin_min  # Fin du job déplacé
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
                nouvelle_h_debut = time(min(23, nouveau_debut // 60), nouveau_debut % 60)
                nouvelle_h_fin = time(min(23, nouveau_fin // 60), nouveau_fin % 60)
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

        msg = f"✅ Déplacé à {nouvelle_heure.strftime('%H:%M')}"
        if nb_decales > 0:
            msg += f" — {nb_decales} élément(s) décalé(s) en cascade"
        return True, msg

    except Exception as e:
        if 'conn' in locals():
            conn.rollback()
        return False, f"❌ Erreur : {str(e)}"

def modifier_job(job_id, elem_planning_id, nouveau_pallox, poids_unit, nouvelle_cadence):
    """
    Modifie quantité + cadence d'un job PRÉVU.
    Recalcule poids_brut_kg, temps_estime_heures et met à jour
    la durée dans lavages_planning_elements (heure_fin incluse).
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Vérifier que le job est bien PRÉVU
        cursor.execute("SELECT statut, heure_debut FROM lavages_jobs lj "
                       "LEFT JOIN lavages_planning_elements pe ON pe.job_id = lj.id "
                       "WHERE lj.id = %s AND pe.id = %s", (job_id, elem_planning_id))
        row = cursor.fetchone()
        if not row:
            return False, "❌ Job ou élément planning introuvable"
        if row['statut'] != 'PRÉVU':
            return False, f"❌ Impossible de modifier un job {row['statut']}"

        nouveau_poids = float(nouveau_pallox) * float(poids_unit)
        nouveau_temps_h = (nouveau_poids / 1000) / float(nouvelle_cadence)
        nouveau_duree_min = int(round(nouveau_temps_h * 60))

        # Mettre à jour lavages_jobs
        cursor.execute("""
            UPDATE lavages_jobs
            SET quantite_pallox = %s,
                poids_brut_kg   = %s,
                capacite_th     = %s,
                temps_estime_heures = %s
            WHERE id = %s AND statut = 'PRÉVU'
        """, (int(nouveau_pallox), nouveau_poids, float(nouvelle_cadence),
              nouveau_temps_h, job_id))

        # Recalculer heure_fin dans planning_elements
        cursor.execute("""
            SELECT heure_debut FROM lavages_planning_elements WHERE id = %s
        """, (elem_planning_id,))
        pe_row = cursor.fetchone()
        if pe_row and pe_row['heure_debut']:
            h_deb = pe_row['heure_debut']
            debut_min = h_deb.hour * 60 + h_deb.minute
            fin_min = debut_min + nouveau_duree_min
            from datetime import time as dtime
            nouvelle_heure_fin = dtime(min(23, fin_min // 60), fin_min % 60)
            cursor.execute("""
                UPDATE lavages_planning_elements
                SET duree_minutes = %s, heure_fin = %s
                WHERE id = %s
            """, (nouveau_duree_min, nouvelle_heure_fin, elem_planning_id))

        conn.commit()
        cursor.close()
        conn.close()
        return True, (f"✅ Job #{job_id} modifié — {int(nouveau_pallox)} pallox, "
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

def terminer_job(job_id, 
                 # Sorties LAVÉ
                 nb_pallox_lave, type_cond_lave, poids_lave, calibre_min_lave, calibre_max_lave,
                 # Sorties GRENAILLES
                 nb_pallox_gren, type_cond_gren, poids_grenailles, calibre_min_gren, calibre_max_gren,
                 # Déchets (reste en kg)
                 poids_dechets,
                 # Destination
                 site_dest, emplacement_dest, notes=""):
    """Termine un job avec création stocks LAVÉ/GRENAILLES et déduction source
    
    Nouvelle version : prend en entrée les pallox + type + calibre pour chaque sortie.
    Le poids peut être ajusté par l'utilisateur après calcul auto.
    
    Si source = BRUT → crée LAVÉ + GRENAILLES_BRUTES
    Si source = GRENAILLES_BRUTES → crée GRENAILLES_LAVÉES (pas de sous-grenailles)
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Récupérer job complet avec emplacement_id et statut_source
        cursor.execute("""
            SELECT lj.lot_id, lj.quantite_pallox, lj.poids_brut_kg,
                   lj.code_lot_interne, lj.ligne_lavage, lj.date_activation,
                   lj.variete, lj.emplacement_id, lj.statut_source
            FROM lavages_jobs lj
            WHERE lj.id = %s AND lj.statut = 'EN_COURS'
        """, (job_id,))
        job = cursor.fetchone()
        if not job:
            return False, "❌ Job introuvable ou pas EN_COURS"
        
        # Récupérer l'emplacement source via emplacement_id du job (si disponible)
        # Sinon fallback sur l'ancienne méthode
        if job['emplacement_id']:
            # Sans is_active : l'emplacement peut avoir ete desactive si stock epuise
            # entre la creation du job et sa terminaison
            cursor.execute("""
                SELECT id, nombre_unites, poids_total_kg, site_stockage, emplacement_stockage, statut_lavage
                FROM stock_emplacements
                WHERE id = %s
            """, (job['emplacement_id'],))
        else:
            # Fallback pour anciens jobs sans emplacement_id
            # ORDER BY is_active DESC : priorite au stock encore actif
            cursor.execute("""
                SELECT id, nombre_unites, poids_total_kg, site_stockage, emplacement_stockage, statut_lavage
                FROM stock_emplacements
                WHERE lot_id = %s 
                  AND statut_lavage IN ('BRUT', 'GRENAILLES_BRUTES')
                ORDER BY is_active DESC, id
                LIMIT 1
            """, (job['lot_id'],))
        
        stock_source = cursor.fetchone()
        if not stock_source:
            return False, "❌ Stock source introuvable (emplacement_id absent de la base)"
        
        # Déterminer le type de source (BRUT ou GRENAILLES_BRUTES)
        statut_source = job['statut_source'] or stock_source['statut_lavage'] or 'BRUT'
        is_grenailles_source = (statut_source == 'GRENAILLES_BRUTES')
        
        # S'assurer que le stock source a bien un statut_lavage
        if not stock_source['statut_lavage']:
            cursor.execute("""
                UPDATE stock_emplacements 
                SET statut_lavage = 'BRUT', type_stock = 'PRINCIPAL'
                WHERE id = %s AND statut_lavage IS NULL
            """, (stock_source['id'],))
        
        # Calculs tares
        poids_brut = float(job['poids_brut_kg'])
        
        if is_grenailles_source:
            # Pour grenailles : pas de sous-grenailles, tout passe en lavé ou déchets
            poids_terre = poids_brut - poids_lave - poids_dechets
            poids_grenailles = 0  # Pas de sous-grenailles
            tare_reelle = ((poids_dechets + poids_terre) / poids_brut) * 100
            rendement = (poids_lave / poids_brut) * 100
        else:
            # Pour BRUT normal
            poids_terre = poids_brut - poids_lave - poids_grenailles - poids_dechets
            tare_reelle = ((poids_dechets + poids_terre) / poids_brut) * 100
            rendement = ((poids_lave + poids_grenailles) / poids_brut) * 100
        
        # Validation cohérence
        total_sorties = poids_lave + poids_grenailles + poids_dechets + poids_terre
        if abs(poids_brut - total_sorties) > 1:
            return False, f"❌ Poids incohérents ! Brut={poids_brut:.0f} vs Total={total_sorties:.0f}"
        
        # Calcul temps réel (en minutes)
        temps_reel_minutes = None
        if job['date_activation']:
            delta = datetime.now() - job['date_activation']
            temps_reel_minutes = int(delta.total_seconds() / 60)
        
        terminated_by = st.session_state.get('username', 'system')
        quantite_pallox = int(job['quantite_pallox'])
        
        # ============================================================
        # 1. METTRE À JOUR LE JOB
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
        # 2. CRÉER STOCK LAVÉ (ou GRENAILLES_LAVÉES si source = grenailles)
        # ============================================================
        if is_grenailles_source:
            # Source = GRENAILLES_BRUTES → créer GRENAILLES_LAVÉES
            statut_sortie = 'GRENAILLES_LAVÉES'
            type_stock_sortie = 'GRENAILLES_LAVÉES'
        else:
            # Source = BRUT → créer LAVÉ
            statut_sortie = 'LAVÉ'
            type_stock_sortie = 'LAVÉ'
        
        # Utiliser les paramètres pallox et type fournis par l'utilisateur
        cursor.execute("""
            INSERT INTO stock_emplacements 
            (lot_id, site_stockage, emplacement_stockage, nombre_unites, 
             type_conditionnement, poids_total_kg, type_stock, statut_lavage, 
             calibre_min, calibre_max, lavage_job_id, is_active)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, TRUE)
            RETURNING id
        """, (job['lot_id'], site_dest, emplacement_dest, int(nb_pallox_lave), 
              type_cond_lave, float(poids_lave), type_stock_sortie, statut_sortie, 
              int(calibre_min_lave), int(calibre_max_lave), job_id))
        stock_lave_id = cursor.fetchone()['id']
        
        # ============================================================
        # 3. CRÉER STOCK GRENAILLES_BRUTES (seulement si source = BRUT et grenailles > 0)
        # ============================================================
        stock_grenailles_id = None
        if not is_grenailles_source and poids_grenailles > 0 and nb_pallox_gren > 0:
            cursor.execute("""
                INSERT INTO stock_emplacements 
                (lot_id, site_stockage, emplacement_stockage, nombre_unites, 
                 type_conditionnement, poids_total_kg, type_stock, statut_lavage, 
                 calibre_min, calibre_max, lavage_job_id, is_active)
                VALUES (%s, %s, %s, %s, %s, %s, 'GRENAILLES', 'GRENAILLES_BRUTES', %s, %s, %s, TRUE)
                RETURNING id
            """, (job['lot_id'], site_dest, emplacement_dest, int(nb_pallox_gren), 
                  type_cond_gren, float(poids_grenailles), 
                  int(calibre_min_gren), int(calibre_max_gren), job_id))
            stock_grenailles_id = cursor.fetchone()['id']
        
        # ============================================================
        # 4. DÉDUIRE DU STOCK SOURCE
        # ============================================================
        nouveau_nb_unites = int(stock_source['nombre_unites']) - quantite_pallox
        nouveau_poids = float(stock_source['poids_total_kg']) - poids_brut
        
        if nouveau_nb_unites <= 0:
            # Stock épuisé - désactiver
            cursor.execute("""
                UPDATE stock_emplacements
                SET nombre_unites = 0, poids_total_kg = 0, is_active = FALSE
                WHERE id = %s
            """, (stock_source['id'],))
        else:
            # Stock restant
            cursor.execute("""
                UPDATE stock_emplacements
                SET nombre_unites = %s, poids_total_kg = %s
                WHERE id = %s
            """, (nouveau_nb_unites, nouveau_poids, stock_source['id']))
        
        # ============================================================
        # 5. ENREGISTRER MOUVEMENTS DE STOCK
        # ============================================================
        # Mouvement réduction source
        type_mvt_source = 'LAVAGE_GRENAILLES_REDUIT' if is_grenailles_source else 'LAVAGE_BRUT_REDUIT'
        cursor.execute("""
            INSERT INTO stock_mouvements 
            (lot_id, type_mouvement, site_origine, emplacement_origine,
             quantite, type_conditionnement, poids_kg, user_action, notes, created_by)
            VALUES (%s, %s, %s, %s, %s, 'Pallox', %s, %s, %s, %s)
        """, (job['lot_id'], type_mvt_source, stock_source['site_stockage'], stock_source['emplacement_stockage'], 
              quantite_pallox, poids_brut, terminated_by, f"Job #{job_id} - Sortie lavage", terminated_by))
        
        # Mouvement création sortie (LAVÉ ou GRENAILLES_LAVÉES)
        type_mvt_sortie = 'LAVAGE_CREATION_GRENAILLES_LAVEES' if is_grenailles_source else 'LAVAGE_CREATION_LAVE'
        cursor.execute("""
            INSERT INTO stock_mouvements 
            (lot_id, type_mouvement, site_destination, emplacement_destination,
             quantite, type_conditionnement, poids_kg, user_action, notes, created_by)
            VALUES (%s, %s, %s, %s, %s, 'Pallox', %s, %s, %s, %s)
        """, (job['lot_id'], type_mvt_sortie, site_dest, emplacement_dest, nb_pallox_lave, 
              poids_lave, terminated_by, f"Job #{job_id} - Entrée {statut_sortie}", terminated_by))
        
        # Mouvement GRENAILLES_BRUTES (seulement si source = BRUT et grenailles > 0)
        if not is_grenailles_source and poids_grenailles > 0:
            cursor.execute("""
                INSERT INTO stock_mouvements 
                (lot_id, type_mouvement, site_destination, emplacement_destination,
                 quantite, type_conditionnement, poids_kg, user_action, notes, created_by)
                VALUES (%s, 'LAVAGE_CREATION_GRENAILLES', %s, %s, %s, 'Pallox', %s, %s, %s, %s)
            """, (job['lot_id'], site_dest, emplacement_dest, nb_pallox_gren, 
                  poids_grenailles, terminated_by, f"Job #{job_id} - Entrée grenailles brutes", terminated_by))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        temps_str = f"{temps_reel_minutes // 60}h{temps_reel_minutes % 60:02d}" if temps_reel_minutes else "N/A"
        if is_grenailles_source:
            return True, f"✅ Terminé ! Temps: {temps_str} - Rendement: {rendement:.1f}% - Stock GRENAILLES_LAVÉES créé"
        else:
            return True, f"✅ Terminé ! Temps: {temps_str} - Rendement: {rendement:.1f}% - Stock LAVÉ créé"
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
                se.type_conditionnement
            FROM lots_bruts l
            JOIN stock_emplacements se ON l.id = se.lot_id
            LEFT JOIN ref_varietes v ON l.code_variete = v.code_variete
            LEFT JOIN ref_producteurs p ON l.code_producteur = p.code_producteur
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
            ORDER BY l.code_lot_interne, se.site_stockage, se.emplacement_stockage
        """)
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        if rows:
            df = pd.DataFrame(rows)
            for col in ['nombre_unites', 'poids_total_kg', 'calibre_min', 'calibre_max', 'stock_total', 'pallox_reserves']:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
            return df
        return pd.DataFrame()
    except:
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

def create_job_lavage(lot_id, emplacement_id, quantite_pallox, poids_brut_kg, 
                     date_prevue, ligne_lavage, capacite_th, notes=""):
    """Crée un nouveau job de lavage
    
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
        # ============================================================
        cursor.execute("""
            SELECT 
                se.nombre_unites as stock_total,
                se.statut_lavage,
                COALESCE(jobs.pallox_reserves, 0) as pallox_reserves,
                se.nombre_unites - COALESCE(jobs.pallox_reserves, 0) as stock_disponible
            FROM stock_emplacements se
            LEFT JOIN (
                SELECT emplacement_id, SUM(quantite_pallox) as pallox_reserves
                FROM lavages_jobs
                WHERE statut IN ('PRÉVU', 'EN_COURS')
                  AND emplacement_id IS NOT NULL
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
                lot_id, emplacement_id, code_lot_interne, variete, quantite_pallox, poids_brut_kg,
                date_prevue, ligne_lavage, capacite_th, temps_estime_heures,
                statut, statut_source, created_by, notes
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'PRÉVU', %s, %s, %s)
            RETURNING id
        """, (lot_id, emplacement_id, lot_info['code_lot_interne'], lot_info['variete'],
              quantite_pallox, poids_brut_kg, date_prevue, ligne_lavage,
              capacite_th, temps_estime, statut_source, created_by, notes))
        job_id = cursor.fetchone()['id']
        conn.commit()
        cursor.close()
        conn.close()
        return True, f"✅ Job #{job_id} créé"
    except Exception as e:
        if 'conn' in locals():
            conn.rollback()
        return False, f"❌ Erreur : {str(e)}"

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
        
        poids_brut = float(elem['poids_brut_kg']) if pd.notna(elem['poids_brut_kg']) else 0
        
        # ⭐ POIDS UNITAIRES CORRECTS
        TYPES_COND = ["Pallox", "Petit Pallox", "Big Bag"]
        POIDS_UNIT = {"Pallox": 1900, "Petit Pallox": 800, "Big Bag": 1600}
        
        st.markdown(f"### ⚖️ Poids brut en entrée : {poids_brut:,.0f} kg")
        st.markdown("---")
        
        # ============ LAYOUT 2 COLONNES PRINCIPALES ============
        col_lave, col_gren = st.columns(2)
        
        # ============ COLONNE LAVÉ ============
        with col_lave:
            st.markdown("### 🧼 Sortie LAVÉ")
            
            col_nb, col_type = st.columns([1, 2])
            with col_nb:
                nb_pallox_lave = st.number_input("Nb Pallox", min_value=0, value=max(1, int(poids_brut * 0.75 / 1900)), key=f"nb_lave_full_{job_en_terminaison}")
            with col_type:
                type_lave = st.selectbox("Type conditionnement", TYPES_COND, key=f"type_lave_full_{job_en_terminaison}")
            
            poids_lave_auto = nb_pallox_lave * POIDS_UNIT[type_lave]
            st.metric("Poids calculé", f"{poids_lave_auto:,.0f} kg", help=f"{nb_pallox_lave} × {POIDS_UNIT[type_lave]} kg")
            p_lave = st.number_input("Poids réel (kg)", 0.0, poids_brut*1.2, float(poids_lave_auto), step=100.0, key=f"p_lave_full_{job_en_terminaison}")
            
            col_cal1, col_cal2 = st.columns(2)
            with col_cal1:
                cal_min_lave = st.number_input("Calibre min (mm)", 0, 100, 35, key=f"cal_min_lave_full_{job_en_terminaison}")
            with col_cal2:
                cal_max_lave = st.number_input("Calibre max (mm)", 0, 100, 75, key=f"cal_max_lave_full_{job_en_terminaison}")
        
        # ============ COLONNE GRENAILLES ============
        with col_gren:
            st.markdown("### 🌾 Sortie GRENAILLES")
            
            col_nb_g, col_type_g = st.columns([1, 2])
            with col_nb_g:
                nb_pallox_gren = st.number_input("Nb Pallox", min_value=0, value=0, key=f"nb_gren_full_{job_en_terminaison}")
            with col_type_g:
                type_gren = st.selectbox("Type conditionnement", TYPES_COND, key=f"type_gren_full_{job_en_terminaison}")
            
            poids_gren_auto = nb_pallox_gren * POIDS_UNIT[type_gren]
            
            if nb_pallox_gren > 0:
                st.metric("Poids calculé", f"{poids_gren_auto:,.0f} kg", help=f"{nb_pallox_gren} × {POIDS_UNIT[type_gren]} kg")
                p_gren = st.number_input("Poids réel (kg)", 0.0, poids_brut, float(poids_gren_auto), step=100.0, key=f"p_gren_full_{job_en_terminaison}")
                
                col_cal1_g, col_cal2_g = st.columns(2)
                with col_cal1_g:
                    cal_min_gren = st.number_input("Calibre min (mm)", 0, 100, 20, key=f"cal_min_gren_full_{job_en_terminaison}")
                with col_cal2_g:
                    cal_max_gren = st.number_input("Calibre max (mm)", 0, 100, 35, key=f"cal_max_gren_full_{job_en_terminaison}")
            else:
                p_gren = 0.0
                cal_min_gren = 20
                cal_max_gren = 35
                st.caption("ℹ️ Pas de grenailles - mettez Nb Pallox > 0 si besoin")
        
        st.markdown("---")
        
        # ============ DÉCHETS + RÉCAP ============
        col_dech, col_recap = st.columns([1, 2])
        
        with col_dech:
            st.markdown("### 🗑️ Déchets")
            p_dech = st.number_input("Poids déchets (kg)", 0.0, poids_brut, poids_brut*0.05, step=50.0, key=f"p_dech_full_{job_en_terminaison}")
            
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
                producteur_info = f"<br>👤 {job['producteur']}" if pd.notna(job.get('producteur')) and job['producteur'] else ""
                st.markdown(f"""<div class="job-card"><strong>Job #{int(job['id'])} {badge_source}</strong><br>
                🌱 {job['variete']}{producteur_info}<br>📦 {int(job['quantite_pallox'])}p - ⏱️ {job['temps_estime_heures']:.1f}h</div>""", unsafe_allow_html=True)
                
                jours_options = ["Sélectionner..."] + [f"{['Lun','Mar','Mer','Jeu','Ven','Sam'][i]} {(week_start + timedelta(days=i)).strftime('%d/%m')}" for i in range(6)]
                jour_choisi = st.selectbox("Jour", jours_options, key=f"jour_job_{job['id']}", label_visibility="collapsed")
                
                if jour_choisi != "Sélectionner...":
                    jour_idx = jours_options.index(jour_choisi) - 1
                    date_cible = week_start + timedelta(days=jour_idx)
                    h_debut_jour = horaires_config.get(jour_idx, {}).get('debut', time(5, 0))
                    heure_saisie = st.time_input("Heure", value=h_debut_jour, step=900, key=f"heure_job_{job['id']}", label_visibility="collapsed")
                    duree_min = int(job['temps_estime_heures'] * 60)
                    
                    heure_optimale, _, msg_info = trouver_prochain_creneau_libre(planning_df, date_cible, st.session_state.selected_ligne, heure_saisie, duree_min)
                    if msg_info:
                        st.info(msg_info)
                    
                    h_fin_jour = get_horaire_fin_jour(jour_idx, horaires_config)
                    fin_minutes = heure_optimale.hour * 60 + heure_optimale.minute + duree_min
                    if fin_minutes > h_fin_jour.hour * 60 + h_fin_jour.minute:
                        st.error(f"⚠️ Dépasse fin journée même repositionné")
                    elif st.button("✅ Placer", key=f"confirm_job_{job['id']}", type="primary", use_container_width=True):
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
            
            jours_tc = ["Sélectionner..."] + [f"{['Lun','Mar','Mer','Jeu','Ven','Sam'][i]} {(week_start + timedelta(days=i)).strftime('%d/%m')}" for i in range(6)]
            jour_tc = st.selectbox("Jour", jours_tc, key=f"jour_tc_{tc['id']}", label_visibility="collapsed")
            if jour_tc != "Sélectionner...":
                jour_idx = jours_tc.index(jour_tc) - 1
                date_cible = week_start + timedelta(days=jour_idx)
                h_debut = horaires_config.get(jour_idx, {}).get('debut', time(5, 0))
                heure_tc = st.time_input("Heure", value=h_debut, step=900, key=f"heure_tc_{tc['id']}", label_visibility="collapsed")
                heure_optimale_tc, _, msg_info_tc = trouver_prochain_creneau_libre(planning_df, date_cible, st.session_state.selected_ligne, heure_tc, tc['duree_minutes'])
                if msg_info_tc:
                    st.info(msg_info_tc)
                if st.button("✅", key=f"confirm_tc_{tc['id']}", use_container_width=True):
                    success, msg = ajouter_element_planning('CUSTOM', None, int(tc['id']), date_cible, st.session_state.selected_ligne, tc['duree_minutes'], annee, semaine, heure_optimale_tc)
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

                                st.markdown(f"""<div class="{css_class}">
                                    <strong>{h_deb}</strong> {statut_emoji}<br>
                                    Job #{int(elem['job_id'])}{badge_source}<br>
                                    🌱 {elem['variete']}{producteur_ligne}{empl_ligne}{produit_ligne}<br>
                                    📦 {int(elem['quantite_pallox']) if pd.notna(elem['quantite_pallox']) else '?'}p<br>
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
                                            st.session_state[f'show_edit_{elem["id"]}'] = not st.session_state.get(f'show_edit_{elem["id"]}', False)
                                            st.rerun()
                                    with col_move:
                                        if st.button("🔀", key=f"move_{elem['id']}", help="Déplacer"):
                                            st.session_state[f'show_move_{elem["id"]}'] = not st.session_state.get(f'show_move_{elem["id"]}', False)
                                            st.rerun()
                                    with col_del:
                                        if st.button("❌", key=f"del_{elem['id']}", help="Retirer"):
                                            retirer_element_planning(int(elem['id']))
                                            st.rerun()
                                    
                                    # Formulaire inline modification quantité / cadence
                                    if st.session_state.get(f'show_edit_{elem["id"]}', False):
                                        elem_id_edit = int(elem['id'])
                                        job_id_edit  = int(elem['job_id'])
                                        pallox_actuel  = int(elem['quantite_pallox']) if pd.notna(elem['quantite_pallox']) else 1
                                        poids_brut_act = float(elem['poids_brut_kg'])  if pd.notna(elem['poids_brut_kg'])  else 0
                                        cadence_act    = float(elem['capacite_th'])    if pd.notna(elem.get('capacite_th')) and elem.get('capacite_th') else 13.0
                                        # Poids unitaire déduit
                                        poids_unit_act = round(poids_brut_act / pallox_actuel) if pallox_actuel > 0 else 1900

                                        st.markdown("**✏️ Modifier le job**")
                                        col_e1, col_e2 = st.columns(2)
                                        with col_e1:
                                            POIDS_UNIT_OPTS = {"Pallox (1900 kg)": 1900,
                                                               "Petit Pallox (800 kg)": 800,
                                                               "Big Bag (1600 kg)": 1600}
                                            # Pré-sélection type conditionnement le plus proche
                                            closest_key = min(POIDS_UNIT_OPTS, key=lambda k: abs(POIDS_UNIT_OPTS[k] - poids_unit_act))
                                            type_cond_edit = st.selectbox("Type cond.", list(POIDS_UNIT_OPTS.keys()),
                                                index=list(POIDS_UNIT_OPTS.keys()).index(closest_key),
                                                key=f"edit_type_{elem_id_edit}")
                                            poids_unit_sel = POIDS_UNIT_OPTS[type_cond_edit]
                                            nouveau_pallox = st.number_input(
                                                "Nb pallox", min_value=1, value=pallox_actuel,
                                                key=f"edit_pallox_{elem_id_edit}")
                                        with col_e2:
                                            lignes_cap = {l['code']: float(l['capacite_th']) for l in get_lignes_lavage()}
                                            cap_max = lignes_cap.get(elem['ligne_lavage'], 13.0)
                                            nouvelle_cadence = st.number_input(
                                                "Cadence (T/h)", min_value=0.5,
                                                max_value=float(cap_max),
                                                value=min(cadence_act, cap_max),
                                                step=0.5, key=f"edit_cadence_{elem_id_edit}")
                                            nouveau_poids = nouveau_pallox * poids_unit_sel
                                            nouveau_temps = (nouveau_poids / 1000) / nouvelle_cadence
                                            st.metric("Nouveau poids", f"{nouveau_poids/1000:.1f} T")
                                            st.metric("Nouveau temps", f"{nouveau_temps:.1f} h")

                                        col_ok_e, col_ann_e = st.columns(2)
                                        with col_ok_e:
                                            if st.button("✅ Valider", key=f"edit_ok_{elem_id_edit}",
                                                         type="primary", use_container_width=True):
                                                ok, msg_e = modifier_job(
                                                    job_id_edit, elem_id_edit,
                                                    nouveau_pallox, poids_unit_sel, nouvelle_cadence
                                                )
                                                if ok:
                                                    st.session_state.pop(f'show_edit_{elem_id_edit}', None)
                                                    st.success(msg_e)
                                                    st.rerun()
                                                else:
                                                    st.error(msg_e)
                                        with col_ann_e:
                                            if st.button("✖", key=f"edit_ann_{elem_id_edit}",
                                                         use_container_width=True):
                                                st.session_state.pop(f'show_edit_{elem_id_edit}', None)
                                                st.rerun()
                                    
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
                                        
                                        h_debut_defaut = horaires_config.get(jour_cible_idx, {}).get('debut', time(5, 0))
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
                                    
                                    if st.button("⏹️ Terminer", key=f"finish_{elem['id']}", type="primary", use_container_width=True):
                                        st.session_state[f'show_finish_{int(elem["job_id"])}'] = True
                                        st.rerun()
                                    
                                    # Note: Le formulaire de terminaison s'affiche en pleine largeur au-dessus du calendrier
                                
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
                            quantite = st.slider(
                                f"Pallox à laver (suggéré: {pallox_suggeres} pour couvrir {besoin_tonnes:.1f}T NET)", 
                                1, dispo, 
                                min(pallox_suggeres, dispo), 
                                key="qty_besoins_create"
                            )
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
                                max_value=float(capacite_ligne),
                                value=float(capacite_ligne),
                                step=0.5,
                                key="cadence_besoins_create",
                                help=f"Capacité max ligne : {capacite_ligne} T/h. Réduire si lot difficile (petit calibre, terre...)"
                            )
                            
                            poids_brut = quantite * poids_unit
                            poids_net_estime = poids_brut * rendement
                            temps_estime = (poids_brut / 1000) / cadence
                            
                            st.metric("Poids BRUT", f"{poids_brut:,.0f} kg ({poids_brut/1000:.1f} T)")
                            st.metric("NET estimé (~78%)", f"{poids_net_estime:,.0f} kg ({poids_net_estime/1000:.1f} T)")
                            st.metric("Temps estimé", f"{temps_estime:.1f} h")
                        
                        notes = st.text_input("Notes (optionnel)", key="notes_besoins_create")
                        
                        if st.button("✅ Créer Job de Lavage", type="primary", use_container_width=True, key="btn_create_besoins"):
                            ligne_code = lignes[ligne_idx]['code']
                            success, message = create_job_lavage(
                                lot_id_besoin, empl_id, quantite, poids_brut,
                                date_prevue, ligne_code, cadence, notes
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
    # SOUS-ONGLET 2 : TOUS LES LOTS BRUT (original)
    # ============================================================
    with create_tab2:
        st.markdown("*Tous les emplacements BRUT disponibles (avec ou sans affectation)*")
        
        lots_dispo = get_lots_bruts_disponibles()
        
        if not lots_dispo.empty:
            # ⭐ FILTRES AMÉLIORÉS
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
            
            lots_f = lots_dispo.copy()
            if f_var != "Toutes":
                lots_f = lots_f[lots_f['variete'] == f_var]
            if f_prod != "Tous":
                lots_f = lots_f[lots_f['producteur'] == f_prod]
            if f_site != "Tous":
                lots_f = lots_f[lots_f['site_stockage'] == f_site]
            
            st.markdown("---")
            
            if not lots_f.empty:
                st.markdown(f"**{len(lots_f)} emplacement(s) disponible(s)** - ⚠️ *Pallox Dispo = Stock - Jobs réservés (PRÉVU/EN_COURS)*")
                st.caption("🔵 BRUT = Stock initial | 🟠 GRENAILLES_BRUTES = Grenailles à re-laver")
                
                # ⭐ TABLEAU AMÉLIORÉ avec nom lot et producteur
                df_display = lots_f[['lot_id', 'emplacement_id', 'code_lot_interne', 'nom_usage', 'producteur', 'variete', 'statut_lavage', 'site_stockage', 'emplacement_stockage', 'stock_total', 'pallox_reserves', 'nombre_unites', 'poids_total_kg']].copy()
                
                # Formater statut_lavage pour affichage
                df_display['statut_lavage'] = df_display['statut_lavage'].apply(
                    lambda x: '🔵 BRUT' if x == 'BRUT' else ('🟠 GREN' if x == 'GRENAILLES_BRUTES' else x)
                )
                
                # Tronquer producteur si trop long
                df_display['producteur'] = df_display['producteur'].apply(
                    lambda x: (x[:15] + '..') if pd.notna(x) and len(str(x)) > 17 else x
                )
                
                df_display = df_display.rename(columns={
                    'code_lot_interne': 'Code Lot',
                    'nom_usage': 'Nom Lot',
                    'producteur': 'Producteur',
                    'variete': 'Variété',
                    'statut_lavage': 'Type',
                    'site_stockage': 'Site',
                    'emplacement_stockage': 'Empl.',
                    'stock_total': 'Stock',
                    'pallox_reserves': 'Réservés',
                    'nombre_unites': 'Dispo',
                    'poids_total_kg': 'Poids (kg)'
                })
                df_display = df_display.reset_index(drop=True)
                
                # Config colonnes pour masquer IDs et formater nombres
                column_config = {
                    "lot_id": None,
                    "emplacement_id": None,
                    "Code Lot": st.column_config.TextColumn("Code Lot", width="small"),
                    "Nom Lot": st.column_config.TextColumn("Nom Lot", width="medium"),
                    "Producteur": st.column_config.TextColumn("Producteur", width="medium"),
                    "Variété": st.column_config.TextColumn("Variété", width="small"),
                    "Type": st.column_config.TextColumn("Type", width="small", help="BRUT ou GRENAILLES à re-laver"),
                    "Site": st.column_config.TextColumn("Site", width="small"),
                    "Empl.": st.column_config.TextColumn("Empl.", width="small"),
                    "Stock": st.column_config.NumberColumn("Stock", format="%d", help="Pallox en stock physique"),
                    "Réservés": st.column_config.NumberColumn("Rés.", format="%d", help="Pallox réservés par jobs PRÉVU/EN_COURS"),
                    "Dispo": st.column_config.NumberColumn("Dispo", format="%d", help="Pallox disponibles pour nouveau job"),
                    "Poids (kg)": st.column_config.NumberColumn("Poids", format="%.0f")
                }
                
                event = st.dataframe(df_display, column_config=column_config, use_container_width=True, hide_index=True, on_select="rerun", selection_mode="single-row", key="lots_create")
                
                selected_rows = event.selection.rows if hasattr(event, 'selection') else []
                
                if len(selected_rows) > 0:
                    row = df_display.iloc[selected_rows[0]]
                    lot_data = lots_dispo[(lots_dispo['lot_id'] == row['lot_id']) & (lots_dispo['emplacement_id'] == row['emplacement_id'])].iloc[0]
                    
                    # Afficher info stock avec réservés + type
                    reserves = int(lot_data['pallox_reserves']) if pd.notna(lot_data['pallox_reserves']) else 0
                    dispo = int(lot_data['nombre_unites'])
                    total = int(lot_data['stock_total']) if pd.notna(lot_data['stock_total']) else dispo
                    type_source = lot_data['statut_lavage'] if pd.notna(lot_data['statut_lavage']) else 'BRUT'
                    type_emoji = '🔵' if type_source == 'BRUT' else '🟠'
                    
                    # ⭐ INFO COMPLÈTE avec nom lot et producteur
                    nom_lot = lot_data['nom_usage'] if pd.notna(lot_data['nom_usage']) else ''
                    producteur = lot_data['producteur'] if pd.notna(lot_data['producteur']) else ''
                    
                    st.markdown("---")
                    if reserves > 0:
                        st.warning(f"⚠️ {type_emoji} **{lot_data['code_lot_interne']}** - {nom_lot} | Producteur: {producteur} | {type_source} | Stock: {total}, Réservés: {reserves}, **Disponible: {dispo}**")
                    else:
                        st.success(f"✅ {type_emoji} **{lot_data['code_lot_interne']}** - {nom_lot} | {lot_data['variete']} | Producteur: {producteur} | **{dispo} pallox disponibles**")
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        # Le slider utilise le stock disponible (déjà calculé)
                        quantite = st.slider("Pallox à laver", 1, dispo, min(5, dispo), key="qty_create")
                        date_prevue = st.date_input("Date prévue", datetime.now().date(), key="date_create")
                    with col2:
                        lignes = get_lignes_lavage()
                        ligne_opts = [f"{l['code']} ({l['capacite_th']} T/h)" for l in lignes]
                        ligne_sel = st.selectbox("Ligne de lavage", ligne_opts, key="ligne_create")
                        
                        # ⭐ POIDS UNITAIRES CORRECTS
                        poids_unit = {'Pallox': 1900, 'Petit Pallox': 800, 'Big Bag': 1600}.get(lot_data['type_conditionnement'], 1900)
                        poids_brut = quantite * poids_unit
                        ligne_idx = ligne_opts.index(ligne_sel)
                        capacite_ligne = float(lignes[ligne_idx]['capacite_th'])
                        
                        cadence = st.number_input(
                            "⚡ Cadence (T/h)",
                            min_value=0.5,
                            max_value=float(capacite_ligne),
                            value=float(capacite_ligne),
                            step=0.5,
                            key="cadence_create",
                            help=f"Capacité max ligne : {capacite_ligne} T/h. Réduire si lot difficile (petit calibre, terre...)"
                        )
                        
                        temps_est = (poids_brut / 1000) / cadence
                        
                        st.metric("Poids total", f"{poids_brut:,} kg")
                        st.metric("Temps estimé", f"{temps_est:.1f}h")
                    
                    notes = st.text_input("Notes (optionnel)", key="notes_create_all")
                    
                    if st.button("✅ Créer Job", type="primary", use_container_width=True, key="btn_create_job_all"):
                        success, msg = create_job_lavage(lot_data['lot_id'], lot_data['emplacement_id'], quantite, poids_brut, date_prevue, lignes[ligne_idx]['code'], cadence, notes)
                        if success:
                            st.success(msg)
                            st.balloons()
                            st.rerun()
                        else:
                            st.error(msg)
                else:
                    st.info("👆 Sélectionnez un lot dans le tableau ci-dessus")
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
        amplitude_options = ["Journée complète (5h-22h)", "Matin (5h-13h)", "Après-midi (13h-22h)"]
        selected_amplitude = st.selectbox("⏰ Amplitude", amplitude_options, key="print_amplitude")
        
        if selected_amplitude == "Matin (5h-13h)":
            heure_debut_print = time(5, 0)
            heure_fin_print = time(13, 0)
        elif selected_amplitude == "Après-midi (13h-22h)":
            heure_debut_print = time(13, 0)
            heure_fin_print = time(22, 0)
        else:
            heure_debut_print = time(5, 0)
            heure_fin_print = time(22, 0)
    
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
