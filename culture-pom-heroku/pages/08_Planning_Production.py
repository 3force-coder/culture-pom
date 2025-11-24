import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, time
from database import get_connection
from components import show_footer
from auth import is_authenticated
from auth.roles import is_admin
import io
import math

st.set_page_config(page_title="Planning Production - Culture Pom", page_icon="🏭", layout="wide")

# ============================================================
# CSS CUSTOM (identique lavage)
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
    
    .semaine-center { text-align: center; }
    
    .job-card {
        background: linear-gradient(135deg, #fff3e0 0%, #ffcc80 100%);
        border-left: 4px solid #f57c00;
        padding: 0.6rem;
        border-radius: 8px;
        margin: 0.4rem 0;
        font-size: 0.85rem;
    }
    .custom-card {
        background: linear-gradient(135deg, #e8eaf6 0%, #c5cae9 100%);
        border-left: 4px solid #3f51b5;
        padding: 0.6rem;
        border-radius: 8px;
        margin: 0.4rem 0;
        font-size: 0.85rem;
    }
    
    .day-header {
        background: #f5f5f5;
        padding: 0.5rem;
        border-radius: 8px 8px 0 0;
        text-align: center;
        font-weight: bold;
        border-bottom: 2px solid #f57c00;
    }
    .capacity-box {
        background: #fafafa;
        padding: 0.4rem;
        font-size: 0.75rem;
        border: 1px solid #e0e0e0;
        border-radius: 0 0 8px 8px;
        margin-bottom: 0.5rem;
    }
    
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
        background: linear-gradient(135deg, #e8eaf6 0%, #c5cae9 100%);
        border-left: 4px solid #3f51b5;
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

def get_lignes_production():
    """Récupère les lignes de production actives"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT code, libelle, capacite_th, site, type_atelier
            FROM production_lignes 
            WHERE is_active = TRUE 
            ORDER BY site, code
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
            FROM production_temps_customs 
            WHERE is_active = TRUE 
            ORDER BY id
        """)
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        return rows if rows else []
    except:
        return []

def get_config_horaires(ligne_code):
    """Récupère la configuration des horaires pour une ligne"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT jour_semaine, heure_debut, heure_fin 
            FROM production_config_horaires 
            WHERE ligne_code = %s AND is_active = TRUE 
            ORDER BY jour_semaine
        """, (ligne_code,))
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        config = {}
        for row in rows:
            config[row['jour_semaine']] = {'debut': row['heure_debut'], 'fin': row['heure_fin']}
        return config
    except:
        return {i: {'debut': time(5, 0), 'fin': time(22, 0) if i < 5 else time(20, 0)} for i in range(6)}

def get_kpis_production():
    """Récupère les KPIs de production"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) as nb FROM production_jobs WHERE statut = 'PRÉVU'")
        nb_prevus = cursor.fetchone()['nb']
        cursor.execute("SELECT COUNT(*) as nb FROM production_jobs WHERE statut = 'EN_COURS'")
        nb_en_cours = cursor.fetchone()['nb']
        cursor.execute("SELECT COUNT(*) as nb FROM production_jobs WHERE statut = 'TERMINÉ'")
        nb_termines = cursor.fetchone()['nb']
        cursor.execute("SELECT COALESCE(SUM(temps_estime_heures), 0) as total FROM production_jobs WHERE statut IN ('PRÉVU', 'EN_COURS')")
        temps_total = cursor.fetchone()['total']
        cursor.close()
        conn.close()
        return {'nb_prevus': nb_prevus, 'nb_en_cours': nb_en_cours, 'nb_termines': nb_termines, 'temps_total': float(temps_total) if temps_total else 0}
    except:
        return None

def get_jobs_a_placer():
    """Récupère les jobs PRÉVU non encore planifiés"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT 
                pj.id, pj.lot_id, pj.code_lot_interne, pj.variete,
                pj.code_produit_commercial, pj.quantite_entree_tonnes, 
                pj.temps_estime_heures, pj.date_prevue, 
                pj.ligne_production as ligne_origine, pj.statut,
                pc.libelle as produit_libelle, pc.marque
            FROM production_jobs pj
            LEFT JOIN ref_produits_commerciaux pc ON pj.code_produit_commercial = pc.code_produit
            WHERE pj.statut = 'PRÉVU'
            ORDER BY pj.date_prevue, pj.id
        """)
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        if rows:
            df = pd.DataFrame(rows)
            for col in ['quantite_entree_tonnes', 'temps_estime_heures']:
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
                pe.date_prevue, pe.ligne_production, pe.ordre_jour,
                pe.heure_debut, pe.heure_fin, pe.duree_minutes,
                pj.code_lot_interne, pj.variete, pj.code_produit_commercial,
                pj.quantite_entree_tonnes, pj.statut as job_statut,
                pj.date_activation, pj.date_terminaison, pj.temps_estime_heures,
                pc.libelle as produit_libelle, pc.marque,
                tc.libelle as custom_libelle, tc.emoji as custom_emoji
            FROM production_planning_elements pe
            LEFT JOIN production_jobs pj ON pe.job_id = pj.id
            LEFT JOIN ref_produits_commerciaux pc ON pj.code_produit_commercial = pc.code_produit
            LEFT JOIN production_temps_customs tc ON pe.temps_custom_id = tc.id
            WHERE pe.annee = %s AND pe.semaine = %s
            ORDER BY pe.date_prevue, pe.ligne_production, pe.ordre_jour
        """, (annee, semaine))
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        if rows:
            return pd.DataFrame(rows)
        return pd.DataFrame()
    except:
        return pd.DataFrame()

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
    mask = (planning_df['date_prevue'].astype(str) == date_str) & (planning_df['ligne_production'] == ligne)
    filtered = planning_df[mask]
    return filtered['duree_minutes'].sum() / 60 if not filtered.empty else 0.0

def verifier_chevauchement(planning_df, date_prevue, ligne_production, heure_debut, duree_minutes):
    """Vérifie si le créneau demandé chevauche un élément existant"""
    jour_str = str(date_prevue)
    if planning_df.empty:
        return True, None, None
    mask = (planning_df['date_prevue'].astype(str) == jour_str) & (planning_df['ligne_production'] == ligne_production)
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

def get_horaire_fin_jour(jour_semaine, horaires_config):
    """Retourne l'heure de fin pour un jour donné"""
    if jour_semaine in horaires_config:
        h_fin = horaires_config[jour_semaine]['fin']
        if isinstance(h_fin, time):
            return h_fin
    return time(22, 0) if jour_semaine < 5 else time(20, 0)

def ajouter_element_planning(type_element, job_id, temps_custom_id, date_prevue, ligne_production, 
                             duree_minutes, annee, semaine, heure_debut_choisie):
    """Ajoute un élément au planning"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT COALESCE(MAX(ordre_jour), 0) as max_ordre
            FROM production_planning_elements
            WHERE date_prevue = %s AND ligne_production = %s
        """, (date_prevue, ligne_production))
        result = cursor.fetchone()
        next_ordre = (result['max_ordre'] or 0) + 1
        
        debut_minutes = heure_debut_choisie.hour * 60 + heure_debut_choisie.minute
        fin_minutes = debut_minutes + duree_minutes
        heure_fin_brute = time(min(23, fin_minutes // 60), fin_minutes % 60)
        heure_fin = arrondir_quart_heure_sup(heure_fin_brute)
        created_by = st.session_state.get('username', 'system')
        
        cursor.execute("""
            INSERT INTO production_planning_elements 
            (type_element, job_id, temps_custom_id, annee, semaine, date_prevue, 
             ligne_production, ordre_jour, heure_debut, heure_fin, duree_minutes, created_by)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (type_element, job_id, temps_custom_id, annee, semaine, date_prevue,
              ligne_production, next_ordre, heure_debut_choisie, heure_fin, duree_minutes, created_by))
        conn.commit()
        cursor.close()
        conn.close()
        return True, f"✅ Placé ({heure_debut_choisie.strftime('%H:%M')} → {heure_fin.strftime('%H:%M')})"
    except Exception as e:
        if 'conn' in locals():
            conn.rollback()
        return False, f"❌ Erreur : {str(e)}"

def retirer_element_planning(element_id):
    """Retire un élément du planning"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM production_planning_elements WHERE id = %s", (element_id,))
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
            UPDATE production_jobs
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

def get_emplacements_site(site_code):
    """Récupère les emplacements d'un site"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT code_emplacement, nom_complet
            FROM ref_sites_stockage
            WHERE code_site = %s AND is_active = TRUE
            ORDER BY code_emplacement
        """, (site_code,))
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        return [(r['code_emplacement'], r['nom_complet']) for r in rows] if rows else []
    except:
        return []

def terminer_job(job_id, quantite_sortie, numero_lot_sortie, site_dest, emplacement_dest, notes=""):
    """Termine un job et crée le stock produit fini"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Récupérer job
        cursor.execute("""
            SELECT lot_id, quantite_entree_tonnes, code_lot_interne, 
                   code_produit_commercial, ligne_production, date_activation
            FROM production_jobs
            WHERE id = %s AND statut = 'EN_COURS'
        """, (job_id,))
        job = cursor.fetchone()
        if not job:
            return False, "❌ Job introuvable ou pas EN_COURS"
        
        terminated_by = st.session_state.get('username', 'system')
        
        # Mettre à jour job
        cursor.execute("""
            UPDATE production_jobs
            SET statut = 'TERMINÉ',
                date_terminaison = CURRENT_TIMESTAMP,
                quantite_sortie_tonnes = %s,
                numero_lot_sortie = %s,
                site_destination = %s,
                emplacement_destination = %s,
                terminated_by = %s,
                notes = %s
            WHERE id = %s
        """, (quantite_sortie, numero_lot_sortie, site_dest, emplacement_dest,
              terminated_by, notes, job_id))
        
        # Créer stock produit fini
        cursor.execute("""
            INSERT INTO stock_emplacements 
            (lot_id, site_stockage, emplacement_stockage, nombre_unites,
             type_conditionnement, poids_total_kg, type_stock, 
             code_produit_commercial, numero_lot_produit, production_job_id, is_active)
            VALUES (%s, %s, %s, 1, 'PRODUIT_FINI', %s, 'PRODUIT_FINI', %s, %s, %s, TRUE)
        """, (job['lot_id'], site_dest, emplacement_dest, 
              quantite_sortie * 1000,
              job['code_produit_commercial'], numero_lot_sortie, job_id))
        
        # Mouvement stock
        cursor.execute("""
            INSERT INTO stock_mouvements (lot_id, type_mouvement, site_destination, 
                                          emplacement_destination, poids_kg, user_action, notes)
            VALUES (%s, 'PRODUCTION_SORTIE', %s, %s, %s, %s, %s)
        """, (job['lot_id'], site_dest, emplacement_dest, quantite_sortie * 1000,
              terminated_by, f"Job #{job_id} - Produit fini"))
        
        conn.commit()
        cursor.close()
        conn.close()
        return True, f"✅ Job terminé - {quantite_sortie:.2f} T produites"
    except Exception as e:
        if 'conn' in locals():
            conn.rollback()
        return False, f"❌ Erreur : {str(e)}"

def supprimer_job(job_id):
    """Supprime un job PRÉVU"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT statut FROM production_jobs WHERE id = %s", (job_id,))
        result = cursor.fetchone()
        if not result:
            return False, "❌ Job introuvable"
        if result['statut'] != 'PRÉVU':
            return False, f"❌ Impossible de supprimer un job {result['statut']}"
        cursor.execute("DELETE FROM production_planning_elements WHERE job_id = %s", (job_id,))
        cursor.execute("DELETE FROM production_jobs WHERE id = %s", (job_id,))
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
        cursor.execute("""
            UPDATE production_jobs
            SET statut = 'PRÉVU',
                date_activation = NULL,
                activated_by = NULL
            WHERE id = %s AND statut = 'EN_COURS'
        """, (job_id,))
        conn.commit()
        cursor.close()
        conn.close()
        return True, "✅ Job remis en PRÉVU"
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
            INSERT INTO production_temps_customs (code, libelle, emoji, duree_minutes, created_by)
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
    """Supprime un temps custom"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE production_temps_customs SET is_active = FALSE WHERE id = %s", (temps_id,))
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

if 'prod_current_week_start' not in st.session_state:
    st.session_state.prod_current_week_start = get_monday_of_week(datetime.now().date())
if 'prod_selected_ligne' not in st.session_state:
    lignes_init = get_lignes_production()
    st.session_state.prod_selected_ligne = lignes_init[0]['code'] if lignes_init else 'SBU_1'

# ============================================================
# HEADER + KPIs
# ============================================================

st.title("🏭 Planning Production")
st.caption("*Gestion des jobs de production - Transformation en produits finis*")

kpis = get_kpis_production()
if kpis:
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("🎯 Jobs Prévus", kpis['nb_prevus'])
    col2.metric("⚙️ Jobs En Cours", kpis['nb_en_cours'])
    col3.metric("✅ Jobs Terminés", kpis['nb_termines'])
    col4.metric("⏱️ Temps Prévu", f"{kpis['temps_total']:.1f}h")

st.markdown("---")

# ============================================================
# ONGLETS PRINCIPAUX
# ============================================================

tab1, tab2, tab3, tab4 = st.tabs(["📅 Planning Semaine", "📋 Liste Jobs", "➕ Créer Job", "⚙️ Admin"])

# ============================================================
# ONGLET 1 : PLANNING SEMAINE
# ============================================================

with tab1:
    # Contrôles
    col_ligne, col_nav_prev, col_semaine, col_nav_next, col_refresh = st.columns([2, 0.5, 2, 0.5, 1])
    
    lignes = get_lignes_production()
    with col_ligne:
        if lignes:
            ligne_options = [f"{l['code']} ({l['capacite_th']} T/h)" for l in lignes]
            selected_idx = next((i for i, l in enumerate(lignes) if l['code'] == st.session_state.prod_selected_ligne), 0)
            selected = st.selectbox("🔵 Ligne", ligne_options, index=selected_idx, key="ligne_select")
            st.session_state.prod_selected_ligne = lignes[ligne_options.index(selected)]['code']
    
    with col_nav_prev:
        if st.button("◀", key="prev_week", use_container_width=True):
            st.session_state.prod_current_week_start -= timedelta(weeks=1)
            st.rerun()
    
    with col_semaine:
        week_start = st.session_state.prod_current_week_start
        week_end = week_start + timedelta(days=5)
        annee, semaine, _ = week_start.isocalendar()
        st.markdown(f"""<div class="semaine-center"><h3>Semaine {semaine}</h3>
        <small>{week_start.strftime('%d/%m')} → {week_end.strftime('%d/%m/%Y')}</small></div>""", unsafe_allow_html=True)
    
    with col_nav_next:
        if st.button("▶", key="next_week", use_container_width=True):
            st.session_state.prod_current_week_start += timedelta(weeks=1)
            st.rerun()
    
    with col_refresh:
        if st.button("🔄", key="refresh", use_container_width=True):
            st.rerun()
    
    st.markdown("---")
    
    # Chargement données
    jobs_a_placer = get_jobs_a_placer()
    temps_customs = get_temps_customs()
    horaires_config = get_config_horaires(st.session_state.prod_selected_ligne)
    planning_df = get_planning_semaine(annee, semaine)
    lignes_dict = {l['code']: float(l['capacite_th']) for l in lignes} if lignes else {}
    
    # Layout principal
    col_left, col_right = st.columns([1, 4])
    
    # COLONNE GAUCHE : JOBS À PLACER
    with col_left:
        st.markdown("### 📦 Jobs à placer")
        
        jobs_planifies_ids = planning_df[planning_df['type_element'] == 'JOB']['job_id'].dropna().astype(int).tolist() if not planning_df.empty else []
        jobs_non_planifies = jobs_a_placer[~jobs_a_placer['id'].isin(jobs_planifies_ids)] if not jobs_a_placer.empty else pd.DataFrame()
        
        if jobs_non_planifies.empty:
            st.info("✅ Tous les jobs planifiés")
        else:
            for _, job in jobs_non_planifies.iterrows():
                temps_h = job['temps_estime_heures'] if pd.notna(job['temps_estime_heures']) else 1.0
                qte = job['quantite_entree_tonnes'] if pd.notna(job['quantite_entree_tonnes']) else 0
                produit = job.get('produit_libelle', job['code_produit_commercial'])
                
                st.markdown(f"""<div class="job-card"><strong>Job #{int(job['id'])}</strong><br>
                📦 {produit}<br>⚖️ {qte:.1f}T - ⏱️ {temps_h:.1f}h</div>""", unsafe_allow_html=True)
                
                jours_options = ["Sélectionner..."] + [f"{['Lun','Mar','Mer','Jeu','Ven','Sam'][i]} {(week_start + timedelta(days=i)).strftime('%d/%m')}" for i in range(6)]
                jour_choisi = st.selectbox("Jour", jours_options, key=f"jour_job_{job['id']}", label_visibility="collapsed")
                
                if jour_choisi != "Sélectionner...":
                    jour_idx = jours_options.index(jour_choisi) - 1
                    date_cible = week_start + timedelta(days=jour_idx)
                    h_debut_jour = horaires_config.get(jour_idx, {}).get('debut', time(5, 0))
                    heure_debut = st.time_input("Heure", value=h_debut_jour, step=900, key=f"heure_job_{job['id']}", label_visibility="collapsed")
                    duree_min = int(temps_h * 60)
                    
                    ok, msg_ch, _ = verifier_chevauchement(planning_df, date_cible, st.session_state.prod_selected_ligne, heure_debut, duree_min)
                    if not ok:
                        st.error(msg_ch)
                    else:
                        h_fin_jour = get_horaire_fin_jour(jour_idx, horaires_config)
                        fin_minutes = heure_debut.hour * 60 + heure_debut.minute + duree_min
                        if fin_minutes > h_fin_jour.hour * 60 + h_fin_jour.minute:
                            st.error("⚠️ Dépasse fin journée")
                        elif st.button("✅ Placer", key=f"confirm_job_{job['id']}", type="primary", use_container_width=True):
                            success, msg = ajouter_element_planning('JOB', int(job['id']), None, date_cible, st.session_state.prod_selected_ligne, duree_min, annee, semaine, heure_debut)
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
                ok, msg_ch, _ = verifier_chevauchement(planning_df, date_cible, st.session_state.prod_selected_ligne, heure_tc, tc['duree_minutes'])
                if not ok:
                    st.error(msg_ch)
                elif st.button("✅", key=f"confirm_tc_{tc['id']}", use_container_width=True):
                    success, msg = ajouter_element_planning('CUSTOM', None, int(tc['id']), date_cible, st.session_state.prod_selected_ligne, tc['duree_minutes'], annee, semaine, heure_tc)
                    if success:
                        st.rerun()
        
        with st.expander("➕ Créer temps"):
            new_lib = st.text_input("Libellé", key="new_tc_lib")
            new_dur = st.number_input("Durée (min)", 5, 480, 20, key="new_tc_dur")
            new_emo = st.selectbox("Emoji", ["⚙️", "☕", "🔧", "🍽️", "⏸️", "🧹"], key="new_tc_emo")
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
                
                # Capacités par ligne
                cap_html = ""
                for lc in sorted(lignes_dict.keys()):
                    ligne_horaires = get_config_horaires(lc)
                    cap_tot = get_capacite_jour(lc, lignes_dict[lc], i, ligne_horaires)
                    temps_ut = calculer_temps_utilise(planning_df, jour_str, lc)
                    temps_di = max(0, cap_tot - temps_ut)
                    charge = (temps_ut / cap_tot * 100) if cap_tot > 0 else 0
                    emoji = "🟢" if charge < 50 else "🟡" if charge < 80 else "🔴"
                    code_court = lc.replace('SBU_', 'S').replace('ENSACH_', 'E')[:3]
                    cap_html += f"<div><strong>{code_court}</strong>: {temps_di:.1f}h {emoji}</div>"
                st.markdown(f"""<div class="capacity-box">{cap_html}</div>""", unsafe_allow_html=True)
                
                # Éléments planifiés
                ligne_aff = st.session_state.prod_selected_ligne
                if not planning_df.empty:
                    mask = (planning_df['date_prevue'].astype(str) == jour_str) & (planning_df['ligne_production'] == ligne_aff)
                    elements = planning_df[mask].sort_values('heure_debut')
                    
                    if elements.empty:
                        st.caption("_Vide_")
                    else:
                        for _, elem in elements.iterrows():
                            h_deb = elem['heure_debut'].strftime('%H:%M') if pd.notna(elem['heure_debut']) else '--:--'
                            h_fin = elem['heure_fin'].strftime('%H:%M') if pd.notna(elem['heure_fin']) else '--:--'
                            
                            if elem['type_element'] == 'JOB':
                                job_statut = elem.get('job_statut', 'PRÉVU')
                                
                                if job_statut == 'EN_COURS':
                                    css_class = "planned-encours"
                                    statut_emoji = "⏱️"
                                elif job_statut == 'TERMINÉ':
                                    css_class = "planned-termine"
                                    statut_emoji = "✅"
                                else:
                                    css_class = "planned-prevu"
                                    statut_emoji = "🟢"
                                
                                produit_aff = elem.get('produit_libelle', elem.get('code_produit_commercial', '?'))
                                qte_aff = elem['quantite_entree_tonnes'] if pd.notna(elem['quantite_entree_tonnes']) else 0
                                
                                st.markdown(f"""<div class="{css_class}">
                                    <strong>{h_deb}</strong> {statut_emoji}<br>
                                    Job #{int(elem['job_id'])}<br>
                                    📦 {produit_aff}<br>
                                    ⚖️ {qte_aff:.1f}T<br>
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
                                    if pd.notna(elem.get('date_activation')):
                                        delta = datetime.now() - elem['date_activation']
                                        minutes_ecoulees = int(delta.total_seconds() / 60)
                                        st.caption(f"⏱️ {minutes_ecoulees // 60}h{minutes_ecoulees % 60:02d}")
                                    
                                    if st.button("⏹️ Terminer", key=f"finish_{elem['id']}", type="primary", use_container_width=True):
                                        st.session_state[f'show_finish_prod_{elem["job_id"]}'] = True
                                        st.rerun()
                                    
                                    if st.session_state.get(f'show_finish_prod_{elem["job_id"]}', False):
                                        with st.expander("📝 Terminer job", expanded=True):
                                            qte_entree = float(elem['quantite_entree_tonnes']) if pd.notna(elem['quantite_entree_tonnes']) else 0
                                            
                                            qte_sortie = st.number_input("Qté produite (T)", 0.0, qte_entree * 1.5, qte_entree, step=0.1, key=f"qte_out_{elem['id']}")
                                            
                                            lot_code = elem.get('code_lot_interne', 'LOT')
                                            num_lot_defaut = f"PF_{lot_code}_{datetime.now().strftime('%Y%m%d')}"
                                            num_lot = st.text_input("N° lot sortie", num_lot_defaut, key=f"num_lot_{elem['id']}")
                                            
                                            ligne_info = next((l for l in lignes if l['code'] == ligne_aff), None)
                                            site_dest = ligne_info['site'] if ligne_info else 'SAINT_FLAVY'
                                            st.info(f"📍 Site : {site_dest}")
                                            
                                            empls = get_emplacements_site(site_dest)
                                            empl = st.selectbox("Emplacement", [""] + [e[0] for e in empls], key=f"empl_{elem['id']}")
                                            
                                            notes_fin = st.text_area("Notes", key=f"notes_{elem['id']}")
                                            
                                            col_val, col_ann = st.columns(2)
                                            with col_val:
                                                if st.button("✅ Valider", key=f"val_finish_{elem['id']}", type="primary"):
                                                    if not empl:
                                                        st.warning("⚠️ Emplacement requis")
                                                    else:
                                                        success, msg = terminer_job(int(elem['job_id']), qte_sortie, num_lot, site_dest, empl, notes_fin)
                                                        if success:
                                                            st.success(msg)
                                                            st.session_state.pop(f'show_finish_prod_{elem["job_id"]}', None)
                                                            st.rerun()
                                                        else:
                                                            st.error(msg)
                                            with col_ann:
                                                if st.button("❌", key=f"cancel_finish_{elem['id']}"):
                                                    st.session_state.pop(f'show_finish_prod_{elem["job_id"]}', None)
                                                    st.rerun()
                            
                            else:
                                st.markdown(f"""<div class="planned-custom">
                                    <strong>{h_deb}</strong><br>
                                    {elem['custom_emoji']} {elem['custom_libelle']}<br>
                                    <small>→{h_fin}</small>
                                </div>""", unsafe_allow_html=True)
                                if st.button("❌", key=f"del_tc_elem_{elem['id']}", help="Retirer"):
                                    retirer_element_planning(int(elem['id']))
                                    st.rerun()
                else:
                    st.caption("_Vide_")

# ============================================================
# ONGLET 2 : LISTE JOBS
# ============================================================

with tab2:
    st.subheader("📋 Liste des Jobs de Production")
    
    subtab1, subtab2, subtab3 = st.tabs(["🟢 PRÉVU", "🟠 EN_COURS", "⬜ TERMINÉ"])
    
    with subtab1:
        jobs_prevus = get_jobs_a_placer()
        if not jobs_prevus.empty:
            st.dataframe(
                jobs_prevus[['id', 'code_lot_interne', 'variete', 'produit_libelle', 'quantite_entree_tonnes', 'date_prevue']].rename(columns={
                    'id': 'Job', 'code_lot_interne': 'Lot', 'variete': 'Variété', 
                    'produit_libelle': 'Produit', 'quantite_entree_tonnes': 'Qté (T)', 'date_prevue': 'Date'
                }),
                use_container_width=True,
                hide_index=True
            )
        else:
            st.info("Aucun job prévu")
    
    with subtab2:
        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute("""
                SELECT pj.id, pj.code_lot_interne, pj.variete, pc.libelle as produit,
                       pj.quantite_entree_tonnes, pj.date_activation, pj.ligne_production
                FROM production_jobs pj
                LEFT JOIN ref_produits_commerciaux pc ON pj.code_produit_commercial = pc.code_produit
                WHERE pj.statut = 'EN_COURS'
                ORDER BY pj.date_activation DESC
            """)
            jobs_en_cours = cursor.fetchall()
            cursor.close()
            conn.close()
            
            if jobs_en_cours:
                df = pd.DataFrame(jobs_en_cours)
                st.dataframe(df, use_container_width=True, hide_index=True)
            else:
                st.info("Aucun job en cours")
        except Exception as e:
            st.error(f"Erreur : {str(e)}")
    
    with subtab3:
        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute("""
                SELECT pj.id, pj.code_lot_interne, pc.libelle as produit,
                       pj.quantite_entree_tonnes as entree, pj.quantite_sortie_tonnes as sortie,
                       pj.numero_lot_sortie, pj.date_terminaison
                FROM production_jobs pj
                LEFT JOIN ref_produits_commerciaux pc ON pj.code_produit_commercial = pc.code_produit
                WHERE pj.statut = 'TERMINÉ'
                ORDER BY pj.date_terminaison DESC
                LIMIT 50
            """)
            jobs_termines = cursor.fetchall()
            cursor.close()
            conn.close()
            
            if jobs_termines:
                df = pd.DataFrame(jobs_termines)
                st.dataframe(df, use_container_width=True, hide_index=True)
            else:
                st.info("Aucun job terminé")
        except Exception as e:
            st.error(f"Erreur : {str(e)}")

# ============================================================
# ONGLET 3 : CRÉER JOB
# ============================================================

with tab3:
    st.subheader("➕ Créer un Job de Production")
    st.caption("*Depuis stock LAVÉ disponible*")
    
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT 
                se.id, se.lot_id, se.site_stockage, se.emplacement_stockage,
                se.nombre_unites, se.poids_total_kg, se.type_conditionnement,
                l.code_lot_interne, l.nom_usage,
                COALESCE(v.nom_variete, l.code_variete) as variete
            FROM stock_emplacements se
            JOIN lots_bruts l ON se.lot_id = l.id
            LEFT JOIN ref_varietes v ON l.code_variete = v.code_variete
            WHERE se.is_active = TRUE 
              AND (se.statut_lavage = 'LAVÉ' OR se.type_stock = 'LAVÉ')
              AND se.poids_total_kg > 0
            ORDER BY l.code_lot_interne
        """)
        stock_lave = cursor.fetchall()
        cursor.close()
        conn.close()
        
        if stock_lave:
            df_stock = pd.DataFrame(stock_lave)
            
            st.dataframe(
                df_stock[['lot_id', 'code_lot_interne', 'variete', 'site_stockage', 'poids_total_kg']].rename(columns={
                    'lot_id': 'Lot ID', 'code_lot_interne': 'Code Lot', 'variete': 'Variété',
                    'site_stockage': 'Site', 'poids_total_kg': 'Poids (kg)'
                }),
                use_container_width=True,
                hide_index=True
            )
            
            st.markdown("---")
            
            col1, col2 = st.columns(2)
            
            with col1:
                lot_options = [f"{r['code_lot_interne']} - {r['variete']} ({r['poids_total_kg']/1000:.1f}T)" for _, r in df_stock.iterrows()]
                selected_lot_str = st.selectbox("Stock LAVÉ source", ["Sélectionner..."] + lot_options, key="create_lot")
                
                if selected_lot_str != "Sélectionner...":
                    idx = lot_options.index(selected_lot_str)
                    selected_stock = df_stock.iloc[idx]
                    poids_dispo_t = float(selected_stock['poids_total_kg']) / 1000
                    
                    quantite = st.number_input("Quantité (T)", 0.1, poids_dispo_t, min(poids_dispo_t, 5.0), step=0.1, key="create_qte")
            
            with col2:
                try:
                    conn = get_connection()
                    cursor = conn.cursor()
                    cursor.execute("""
                        SELECT code_produit, libelle, marque, atelier
                        FROM ref_produits_commerciaux
                        WHERE is_active = TRUE
                        ORDER BY marque, libelle
                    """)
                    produits = cursor.fetchall()
                    cursor.close()
                    conn.close()
                    
                    if produits:
                        prod_options = [f"{p['marque']} - {p['libelle']}" for p in produits]
                        selected_prod_str = st.selectbox("Produit à fabriquer", ["Sélectionner..."] + prod_options, key="create_prod")
                        
                        if selected_prod_str != "Sélectionner...":
                            prod_idx = prod_options.index(selected_prod_str)
                            selected_prod = produits[prod_idx]
                except:
                    st.error("Erreur chargement produits")
                
                date_prevue = st.date_input("Date prévue", datetime.now().date(), key="create_date")
            
            if lignes:
                ligne_create_options = [f"{l['code']} - {l['libelle']} ({l['capacite_th']}T/h)" for l in lignes]
                selected_ligne_create = st.selectbox("Ligne de production", ligne_create_options, key="create_ligne")
                ligne_idx = ligne_create_options.index(selected_ligne_create)
                ligne_code = lignes[ligne_idx]['code']
                capacite = float(lignes[ligne_idx]['capacite_th'])
            
            notes_create = st.text_area("Notes", key="create_notes")
            
            if st.button("✅ Créer le Job", type="primary", use_container_width=True, key="btn_create_job"):
                if selected_lot_str == "Sélectionner...":
                    st.error("❌ Sélectionnez un stock")
                elif selected_prod_str == "Sélectionner...":
                    st.error("❌ Sélectionnez un produit")
                else:
                    try:
                        conn = get_connection()
                        cursor = conn.cursor()
                        
                        temps_estime = quantite / capacite
                        created_by = st.session_state.get('username', 'system')
                        
                        cursor.execute("""
                            INSERT INTO production_jobs (
                                lot_id, code_lot_interne, variete, code_produit_commercial,
                                quantite_entree_tonnes, date_prevue, ligne_production,
                                capacite_th, temps_estime_heures, statut, created_by, notes
                            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'PRÉVU', %s, %s)
                            RETURNING id
                        """, (
                            int(selected_stock['lot_id']),
                            selected_stock['code_lot_interne'],
                            selected_stock['variete'],
                            selected_prod['code_produit'],
                            quantite,
                            date_prevue,
                            ligne_code,
                            capacite,
                            temps_estime,
                            created_by,
                            notes_create
                        ))
                        
                        job_id = cursor.fetchone()['id']
                        conn.commit()
                        cursor.close()
                        conn.close()
                        
                        st.success(f"✅ Job #{job_id} créé avec succès !")
                        st.balloons()
                        st.rerun()
                    except Exception as e:
                        if 'conn' in locals():
                            conn.rollback()
                        st.error(f"❌ Erreur : {str(e)}")
        else:
            st.warning("⚠️ Aucun stock LAVÉ disponible")
    except Exception as e:
        st.error(f"Erreur : {str(e)}")

# ============================================================
# ONGLET 4 : ADMIN
# ============================================================

with tab4:
    if not is_admin():
        st.warning("⚠️ Accès réservé aux administrateurs")
    else:
        st.subheader("⚙️ Administration Production")
        
        admin_tab1, admin_tab2 = st.tabs(["🗑️ Gestion Jobs", "🔧 Temps Customs"])
        
        with admin_tab1:
            st.markdown("### Gestion des Jobs")
            
            col_prevus, col_encours = st.columns(2)
            
            with col_prevus:
                st.markdown("#### 🟢 PRÉVU - Supprimer")
                try:
                    conn = get_connection()
                    cursor = conn.cursor()
                    cursor.execute("""
                        SELECT id, code_lot_interne, quantite_entree_tonnes, date_prevue
                        FROM production_jobs
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
                                st.markdown(f"**#{job['id']}** {job['code_lot_interne']} - {job['quantite_entree_tonnes']:.1f}T")
                            with col_btn:
                                if st.button("🗑️", key=f"del_job_{job['id']}"):
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
                st.markdown("#### 🟠 EN_COURS - Annuler")
                try:
                    conn = get_connection()
                    cursor = conn.cursor()
                    cursor.execute("""
                        SELECT id, code_lot_interne, quantite_entree_tonnes, date_activation
                        FROM production_jobs
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
                                st.markdown(f"**#{job['id']}** {job['code_lot_interne']}")
                            with col_btn:
                                if st.button("↩️", key=f"cancel_{job['id']}"):
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
        
        with admin_tab2:
            st.markdown("### Temps Customs")
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
            st.markdown("#### ➕ Créer temps custom")
            col1, col2, col3 = st.columns(3)
            with col1:
                new_lib_admin = st.text_input("Libellé", key="new_tc_lib_admin")
            with col2:
                new_dur_admin = st.number_input("Durée (min)", 5, 480, 20, key="new_tc_dur_admin")
            with col3:
                new_emo_admin = st.selectbox("Emoji", ["⚙️", "☕", "🔧", "🍽️", "⏸️", "🧹", "🔄"], key="new_tc_emo_admin")
            if st.button("✅ Créer", key="btn_create_tc_admin") and new_lib_admin:
                creer_temps_custom(new_lib_admin.upper().replace(" ", "_")[:20], new_lib_admin, new_emo_admin, new_dur_admin)
                st.success("✅ Créé")
                st.rerun()

show_footer()
