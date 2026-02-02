"""
POC Planning Lavage - Version UX Finale
========================================

Structure comme page actuelle :
- Boutons contextuels sur chaque job du calendrier
- Liste jobs non planifiés à gauche (drag)
- Calendrier à droite (drop)
- Modal qualification après arrêt

Données en session_state (pas DB)
"""

import streamlit as st
from datetime import datetime, timedelta
from auth import is_authenticated
from components import show_footer

st.set_page_config(page_title="POC Planning Lavage", page_icon="🧪", layout="wide")

if not is_authenticated():
    st.warning("⚠️ Veuillez vous connecter")
    st.stop()

# ============================================================
# CSS
# ============================================================
st.markdown("""
<style>
    .block-container {
        padding-top: 1rem !important;
    }
    h1, h2, h3 { margin: 0.5rem 0 !important; }
    
    /* Jobs non planifiés */
    .job-card {
        background: white;
        border: 2px solid #2E7D32;
        border-radius: 8px;
        padding: 12px;
        margin: 8px 0;
        cursor: grab;
        transition: all 0.2s;
    }
    .job-card:hover {
        background: #E8F5E9;
        transform: translateY(-2px);
        box-shadow: 0 4px 8px rgba(0,0,0,0.1);
    }
    .job-card:active {
        cursor: grabbing;
    }
    
    /* Zone de drop */
    .drop-zone {
        border: 3px dashed #2E7D32;
        border-radius: 12px;
        padding: 20px;
        background: rgba(46, 125, 50, 0.05);
        min-height: 400px;
    }
</style>
""", unsafe_allow_html=True)

# ============================================================
# INITIALISATION SESSION STATE
# ============================================================

if 'jobs_planifies' not in st.session_state:
    st.session_state.jobs_planifies = [
        {
            'id': 1,
            'variete': 'AGATA',
            'lot_id': 'LOT_2025_AGATA_130',
            'quantite_pallox': 5,
            'poids_estime_kg': 9500,
            'date': '2026-02-03',
            'heure_debut': '06:00',
            'heure_fin': '08:30',
            'duree_prevue_min': 150,
            'ligne': 'LIGNE_1',
            'statut': 'PRÉVU'
        },
        {
            'id': 2,
            'variete': 'BINTJE',
            'lot_id': 'LOT_2025_BINTJE_045',
            'quantite_pallox': 3,
            'poids_estime_kg': 5700,
            'date': '2026-02-03',
            'heure_debut': '08:30',
            'heure_fin': '10:00',
            'duree_prevue_min': 90,
            'ligne': 'LIGNE_1',
            'statut': 'PRÉVU'
        },
        {
            'id': 3,
            'variete': 'CHARLOTTE',
            'lot_id': 'LOT_2025_CHARLOTTE_089',
            'quantite_pallox': 4,
            'poids_estime_kg': 7600,
            'date': '2026-02-03',
            'heure_debut': '08:30',
            'heure_fin': '10:00',
            'duree_prevue_min': 90,
            'ligne': 'LIGNE_2',
            'statut': 'EN_COURS',
            'date_debut_reel': (datetime.now() - timedelta(hours=1)).isoformat()
        }
    ]

if 'jobs_non_planifies' not in st.session_state:
    st.session_state.jobs_non_planifies = [
        {
            'id': 10,
            'variete': 'MONALISA',
            'lot_id': 'LOT_2025_MONALISA_234',
            'quantite_pallox': 6,
            'poids_estime_kg': 11400
        },
        {
            'id': 11,
            'variete': 'ARTEMIS',
            'lot_id': 'LOT_2025_ARTEMIS_156',
            'quantite_pallox': 4,
            'poids_estime_kg': 7600
        },
        {
            'id': 12,
            'variete': 'NICOLA',
            'lot_id': 'LOT_2025_NICOLA_078',
            'quantite_pallox': 5,
            'poids_estime_kg': 9500
        }
    ]

if 'job_counter' not in st.session_state:
    st.session_state.job_counter = 20

# ============================================================
# FONCTIONS MÉTIER
# ============================================================

def demarrer_job(job_id):
    """Démarre un job : PRÉVU → EN_COURS"""
    for job in st.session_state.jobs_planifies:
        if job['id'] == job_id and job['statut'] == 'PRÉVU':
            job['statut'] = 'EN_COURS'
            job['date_debut_reel'] = datetime.now().isoformat()
            return True, f"✅ Job #{job_id} démarré"
    return False, "❌ Impossible de démarrer ce job"

def terminer_job(job_id, poids_lave, poids_grenailles, poids_dechets):
    """Termine un job avec qualification"""
    for job in st.session_state.jobs_planifies:
        if job['id'] == job_id and job['statut'] == 'EN_COURS':
            # Calculs
            poids_brut = float(job['poids_estime_kg'])
            poids_terre = poids_brut - poids_lave - poids_grenailles - poids_dechets
            
            # Validation
            total = poids_lave + poids_grenailles + poids_dechets + poids_terre
            if abs(total - poids_brut) > 10:
                return False, f"❌ Incohérence : Brut={poids_brut:.0f} vs Total={total:.0f}"
            
            # Calculs tare/rendement
            tare_pct = ((poids_dechets + poids_terre) / poids_brut) * 100
            rendement_pct = ((poids_lave + poids_grenailles) / poids_brut) * 100
            
            # Durée réelle
            debut = datetime.fromisoformat(job['date_debut_reel'])
            fin = datetime.now()
            duree_reelle_min = int((fin - debut).total_seconds() / 60)
            
            # Mise à jour
            job['statut'] = 'TERMINÉ'
            job['date_fin_reel'] = fin.isoformat()
            job['duree_reelle_min'] = duree_reelle_min
            job['poids_lave_kg'] = poids_lave
            job['poids_grenailles_kg'] = poids_grenailles
            job['poids_dechets_kg'] = poids_dechets
            job['poids_terre_kg'] = poids_terre
            job['tare_pct'] = round(tare_pct, 2)
            job['rendement_pct'] = round(rendement_pct, 2)
            
            # Décalage jobs suivants
            decalage_min = duree_reelle_min - job['duree_prevue_min']
            decaler_jobs_suivants(job, decalage_min)
            
            return True, f"✅ Terminé - Rendement: {rendement_pct:.1f}% - Décalage: {decalage_min:+d} min"
    
    return False, "❌ Job introuvable"

def decaler_jobs_suivants(job_termine, decalage_min):
    """Décale jobs suivants sur même ligne"""
    if decalage_min == 0:
        return
    
    ligne = job_termine['ligne']
    date = job_termine['date']
    heure_fin = job_termine['heure_fin']
    
    for job in st.session_state.jobs_planifies:
        if (job['ligne'] == ligne and 
            job['date'] == date and 
            job['heure_debut'] >= heure_fin and
            job['statut'] == 'PRÉVU'):
            
            debut = datetime.strptime(f"{date} {job['heure_debut']}", "%Y-%m-%d %H:%M")
            fin = datetime.strptime(f"{date} {job['heure_fin']}", "%Y-%m-%d %H:%M")
            
            nouveau_debut = debut + timedelta(minutes=decalage_min)
            nouveau_fin = fin + timedelta(minutes=decalage_min)
            
            job['heure_debut'] = nouveau_debut.strftime("%H:%M")
            job['heure_fin'] = nouveau_fin.strftime("%H:%M")

# ============================================================
# FONCTION AFFICHAGE JOB AVEC BOUTONS
# ============================================================

def afficher_job_card(job):
    """Affiche une carte job avec boutons d'action"""
    
    # Couleur selon statut
    if job['statut'] == 'EN_COURS':
        bg_color = "#FFF3E0"
        border_color = "#FF6B35"
        icon = "⚙️"
    elif job['statut'] == 'TERMINÉ':
        bg_color = "#F5F5F5"
        border_color = "#95A5A6"
        icon = "✅"
    else:
        bg_color = "#E8F5E9"
        border_color = "#2ECC71"
        icon = "🎯"
    
    with st.container():
        st.markdown(f"""
        <div style="background: {bg_color}; border-left: 4px solid {border_color}; 
                    padding: 12px; border-radius: 8px; margin: 8px 0;">
            <strong>{icon} Job #{job['id']} - {job['variete']}</strong><br>
            <small>{job['lot_id']}</small><br>
            🕐 {job['heure_debut']} - {job['heure_fin']} ({job['duree_prevue_min']} min)<br>
            📦 {job['quantite_pallox']} pallox - ⚖️ {job['poids_estime_kg']/1000:.1f} T
        </div>
        """, unsafe_allow_html=True)
        
        # Boutons d'action
        col_btn1, col_btn2 = st.columns(2)
        
        if job['statut'] == 'PRÉVU':
            with col_btn1:
                if st.button(f"▶️ Démarrer", key=f"start_{job['id']}", use_container_width=True, type="primary"):
                    success, msg = demarrer_job(job['id'])
                    if success:
                        st.success(msg)
                        st.rerun()
                    else:
                        st.error(msg)
        
        elif job['statut'] == 'EN_COURS':
            with col_btn1:
                if st.button(f"⏸️ Arrêter", key=f"stop_{job['id']}", use_container_width=True, type="secondary"):
                    st.session_state[f'show_modal_{job['id']}'] = True
                    st.rerun()
            
            # Modal qualification
            if st.session_state.get(f'show_modal_{job['id']}', False):
                st.markdown("---")
                st.markdown("#### 📊 Qualification du Lavage")
                
                poids_brut = float(job['poids_estime_kg'])
                
                col1, col2 = st.columns(2)
                with col1:
                    poids_lave = st.number_input(
                        "Poids lavé (kg) *",
                        min_value=0.0,
                        value=poids_brut * 0.75,
                        step=100.0,
                        key=f"lave_{job['id']}"
                    )
                    poids_grenailles = st.number_input(
                        "Grenailles (kg) *",
                        min_value=0.0,
                        value=poids_brut * 0.05,
                        step=10.0,
                        key=f"gren_{job['id']}"
                    )
                
                with col2:
                    poids_dechets = st.number_input(
                        "Déchets (kg) *",
                        min_value=0.0,
                        value=poids_brut * 0.05,
                        step=10.0,
                        key=f"dech_{job['id']}"
                    )
                    poids_terre = poids_brut - poids_lave - poids_grenailles - poids_dechets
                    st.metric("Terre calculée", f"{poids_terre:.0f} kg")
                
                col_save, col_cancel = st.columns(2)
                with col_save:
                    if st.button("✅ Valider", key=f"save_{job['id']}", type="primary", use_container_width=True):
                        success, msg = terminer_job(job['id'], poids_lave, poids_grenailles, poids_dechets)
                        if success:
                            st.success(msg)
                            st.balloons()
                            st.session_state.pop(f'show_modal_{job['id']}')
                            st.rerun()
                        else:
                            st.error(msg)
                
                with col_cancel:
                    if st.button("❌ Annuler", key=f"cancel_{job['id']}", use_container_width=True):
                        st.session_state.pop(f'show_modal_{job['id']}')
                        st.rerun()
        
        elif job['statut'] == 'TERMINÉ':
            # Afficher résultats
            if 'rendement_pct' in job:
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Rendement", f"{job['rendement_pct']:.1f}%")
                with col2:
                    st.metric("Tare", f"{job['tare_pct']:.1f}%")
                with col3:
                    st.metric("Durée", f"{job['duree_reelle_min']} min")

# ============================================================
# INTERFACE
# ============================================================

st.title("🧪 POC Planning Lavage - UX Finale")
st.caption("Boutons sur calendrier + Drag & Drop jobs non planifiés")

# Métriques
col1, col2, col3, col4 = st.columns(4)
with col1:
    nb_prevus = len([j for j in st.session_state.jobs_planifies if j['statut'] == 'PRÉVU'])
    st.metric("🎯 PRÉVU", nb_prevus)
with col2:
    nb_en_cours = len([j for j in st.session_state.jobs_planifies if j['statut'] == 'EN_COURS'])
    st.metric("⚙️ EN_COURS", nb_en_cours)
with col3:
    nb_termines = len([j for j in st.session_state.jobs_planifies if j['statut'] == 'TERMINÉ'])
    st.metric("✅ TERMINÉ", nb_termines)
with col4:
    nb_attente = len(st.session_state.jobs_non_planifies)
    st.metric("📋 En attente", nb_attente)

st.markdown("---")

# ============================================================
# LAYOUT : LISTE + CALENDRIER
# ============================================================

col_left, col_right = st.columns([1, 3])

# ============================================================
# COLONNE GAUCHE : JOBS NON PLANIFIÉS
# ============================================================

with col_left:
    st.subheader("📋 Jobs à Planifier")
    st.caption(f"{len(st.session_state.jobs_non_planifies)} job(s)")
    
    if st.session_state.jobs_non_planifies:
        for job in st.session_state.jobs_non_planifies:
            with st.container():
                st.markdown(f"""
                <div class="job-card">
                    <strong>{job['variete']}</strong><br>
                    <small>{job['lot_id']}</small><br>
                    📦 {job['quantite_pallox']} pallox<br>
                    ⚖️ {job['poids_estime_kg']/1000:.1f} T
                </div>
                """, unsafe_allow_html=True)
                
                # Formulaire planification rapide
                with st.expander("➕ Planifier", expanded=False):
                    date_planif = st.date_input(
                        "Date",
                        value=datetime.now().date(),
                        key=f"date_{job['id']}"
                    )
                    
                    col_h, col_l = st.columns(2)
                    with col_h:
                        heure_planif = st.time_input(
                            "Heure",
                            value=datetime.strptime("08:00", "%H:%M").time(),
                            key=f"heure_{job['id']}"
                        )
                    with col_l:
                        ligne_planif = st.selectbox(
                            "Ligne",
                            options=['LIGNE_1', 'LIGNE_2'],
                            key=f"ligne_{job['id']}"
                        )
                    
                    if st.button("✅ Ajouter", key=f"add_{job['id']}", type="primary", use_container_width=True):
                        # Calcul durée
                        duree_min = int((float(job['poids_estime_kg']) / 1000) / 13.0 * 60)
                        debut = datetime.combine(date_planif, heure_planif)
                        fin = debut + timedelta(minutes=duree_min)
                        
                        # Nouveau job
                        nouveau_job = {
                            'id': st.session_state.job_counter,
                            'variete': job['variete'],
                            'lot_id': job['lot_id'],
                            'quantite_pallox': job['quantite_pallox'],
                            'poids_estime_kg': job['poids_estime_kg'],
                            'date': date_planif.strftime("%Y-%m-%d"),
                            'heure_debut': heure_planif.strftime("%H:%M"),
                            'heure_fin': fin.strftime("%H:%M"),
                            'duree_prevue_min': duree_min,
                            'ligne': ligne_planif,
                            'statut': 'PRÉVU'
                        }
                        
                        st.session_state.jobs_planifies.append(nouveau_job)
                        st.session_state.job_counter += 1
                        
                        # Retirer de non planifiés
                        st.session_state.jobs_non_planifies = [
                            j for j in st.session_state.jobs_non_planifies if j['id'] != job['id']
                        ]
                        
                        st.success(f"✅ Job #{nouveau_job['id']} ajouté")
                        st.rerun()
    else:
        st.success("✅ Tous les jobs sont planifiés !")
    
    st.markdown("---")
    st.info("💡 **Prochaine version** : Drag & drop de la liste vers le calendrier")

# ============================================================
# COLONNE DROITE : CALENDRIER AVEC ACTIONS
# ============================================================

with col_right:
    st.subheader("📅 Planning")
    
    # Grouper jobs par jour
    jobs_par_jour = {}
    for job in st.session_state.jobs_planifies:
        date = job['date']
        if date not in jobs_par_jour:
            jobs_par_jour[date] = []
        jobs_par_jour[date].append(job)
    
    # Afficher par jour
    for date in sorted(jobs_par_jour.keys()):
        date_obj = datetime.strptime(date, "%Y-%m-%d")
        st.markdown(f"### 📆 {date_obj.strftime('%A %d/%m/%Y')}")
        
        # Grouper par ligne
        jobs_ligne1 = [j for j in jobs_par_jour[date] if j['ligne'] == 'LIGNE_1']
        jobs_ligne2 = [j for j in jobs_par_jour[date] if j['ligne'] == 'LIGNE_2']
        
        col_l1, col_l2 = st.columns(2)
        
        with col_l1:
            st.markdown("#### 🔧 LIGNE_1")
            if jobs_ligne1:
                for job in sorted(jobs_ligne1, key=lambda j: j['heure_debut']):
                    afficher_job_card(job)
            else:
                st.info("Aucun job")
        
        with col_l2:
            st.markdown("#### 🔧 LIGNE_2")
            if jobs_ligne2:
                for job in sorted(jobs_ligne2, key=lambda j: j['heure_debut']):
                    afficher_job_card(job)
            else:
                st.info("Aucun job")
        
# Debug
with st.expander("🔍 Debug"):
    st.json({
        'jobs_planifies': st.session_state.jobs_planifies,
        'jobs_non_planifies': st.session_state.jobs_non_planifies
    })

show_footer()
