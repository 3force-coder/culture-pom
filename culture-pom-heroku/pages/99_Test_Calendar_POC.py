import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from streamlit_calendar import fullcalendar_component

st.set_page_config(page_title="Planning Lavage - 3 Modes", page_icon="🧼", layout="wide")

# CSS Culture Pom
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
    
    /* Jobs non planifiés - Expanders */
    .streamlit-expanderHeader {
        background-color: #f8f9fa !important;
        border-radius: 6px;
        font-weight: 600 !important;
    }
    
    /* Détail job */
    .detail-card {
        background: linear-gradient(135deg, #f0f7f0 0%, #e8f5e9 100%);
        padding: 1.5rem;
        border-radius: 8px;
        border-left: 5px solid #2e7d32;
        box-shadow: 0 2px 8px rgba(0,0,0,0.1);
    }
    
    .info-row {
        background-color: white;
        padding: 0.8rem;
        border-radius: 6px;
        margin: 0.5rem 0;
        display: flex;
        align-items: center;
        box-shadow: 0 1px 3px rgba(0,0,0,0.08);
    }
    
    .info-icon {
        margin-right: 0.8rem;
        font-size: 1.2em;
    }
    
    .info-label {
        color: #666;
        font-size: 0.85em;
        margin-right: 0.5rem;
    }
    
    .info-value {
        font-weight: 600;
        color: #2e7d32;
    }
    
    /* Métriques mode */
    .metric-badge {
        background-color: #2e7d32;
        color: white;
        padding: 0.3rem 0.8rem;
        border-radius: 20px;
        font-size: 0.9em;
        font-weight: 600;
        display: inline-block;
        margin: 0.2rem;
    }
</style>
""", unsafe_allow_html=True)

# ==========================================
# INITIALISATION SESSION STATE
# ==========================================

if 'jobs_planifies' not in st.session_state:
    st.session_state.jobs_planifies = [
        {
            'id': 1,
            'lot_id': 101,
            'code_lot_interne': 'LOT_2025_AGATA_130',
            'nom_usage': 'AGATA 35/50',
            'variete': 'AGATA',
            'producteur': 'BOSSELER',
            'calibre_min': 35,
            'calibre_max': 50,
            'site_stockage': 'SAINT_FLAVY',
            'quantite_pallox': 5,
            'poids_brut_kg': 9500,
            'date_prevue': '2026-02-03',
            'heure_debut': '06:00',
            'heure_fin': '08:30',
            'ligne_lavage': 'LIGNE_1',
            'statut': 'PRÉVU',
            'date_debut_reel': None,
            'duree_prevue_min': 150,
            'duree_reelle_min': None,
            'poids_lave_kg': None,
            'poids_grenailles_kg': None,
            'poids_dechets_kg': None,
            'poids_terre_kg': None,
            'tare_pct': None,
            'rendement_pct': None
        },
        {
            'id': 2,
            'lot_id': 102,
            'code_lot_interne': 'LOT_2025_BINTJE_045',
            'nom_usage': 'BINTJE 40/50',
            'variete': 'BINTJE',
            'producteur': 'EARL MARTIN',
            'calibre_min': 40,
            'calibre_max': 50,
            'site_stockage': 'SAINT_FLAVY',
            'quantite_pallox': 3,
            'poids_brut_kg': 5700,
            'date_prevue': '2026-02-03',
            'heure_debut': '08:30',
            'heure_fin': '10:00',
            'ligne_lavage': 'LIGNE_2',
            'statut': 'EN_COURS',
            'date_debut_reel': '2026-02-03 08:32',
            'duree_prevue_min': 90,
            'duree_reelle_min': None
        },
        {
            'id': 3,
            'lot_id': 103,
            'code_lot_interne': 'LOT_2025_CHARLOTTE_078',
            'nom_usage': 'CHARLOTTE 35/45',
            'variete': 'CHARLOTTE',
            'producteur': 'SCEA DUPONT',
            'calibre_min': 35,
            'calibre_max': 45,
            'site_stockage': 'SAINT_FLAVY',
            'quantite_pallox': 4,
            'poids_brut_kg': 7600,
            'date_prevue': '2026-02-03',
            'heure_debut': '10:00',
            'heure_fin': '11:50',
            'ligne_lavage': 'LIGNE_1',
            'statut': 'PRÉVU',
            'duree_prevue_min': 110
        }
    ]

if 'jobs_non_planifies' not in st.session_state:
    st.session_state.jobs_non_planifies = [
        {
            'id': 10,
            'lot_id': 201,
            'code_lot_interne': 'LOT_2025_MONALISA_156',
            'nom_usage': 'MONALISA 40/55',
            'variete': 'MONALISA',
            'producteur': 'GAEC LEFEBVRE',
            'calibre_min': 40,
            'calibre_max': 55,
            'site_stockage': 'SAINT_FLAVY',
            'quantite_pallox': 6,
            'poids_brut_kg': 11400
        },
        {
            'id': 11,
            'lot_id': 202,
            'code_lot_interne': 'LOT_2025_ARTEMIS_089',
            'nom_usage': 'ARTEMIS 35/50',
            'variete': 'ARTEMIS',
            'producteur': 'BOSSELER',
            'calibre_min': 35,
            'calibre_max': 50,
            'site_stockage': 'SAINT_FLAVY',
            'quantite_pallox': 4,
            'poids_brut_kg': 7600
        },
        {
            'id': 12,
            'lot_id': 203,
            'code_lot_interne': 'LOT_2025_NICOLA_034',
            'nom_usage': 'NICOLA 40/50',
            'variete': 'NICOLA',
            'producteur': 'EARL MARTIN',
            'calibre_min': 40,
            'calibre_max': 50,
            'site_stockage': 'SAINT_FLAVY',
            'quantite_pallox': 5,
            'poids_brut_kg': 9500
        },
        {
            'id': 13,
            'lot_id': 204,
            'code_lot_interne': 'LOT_2025_AGATA_167',
            'nom_usage': 'AGATA 30/40',
            'variete': 'AGATA',
            'producteur': 'SCEA DUPONT',
            'calibre_min': 30,
            'calibre_max': 40,
            'site_stockage': 'BEAUVOIR',
            'quantite_pallox': 3,
            'poids_brut_kg': 5700
        },
        {
            'id': 14,
            'lot_id': 205,
            'code_lot_interne': 'LOT_2025_BINTJE_198',
            'nom_usage': 'BINTJE 45/55',
            'variete': 'BINTJE',
            'producteur': 'GAEC LEFEBVRE',
            'calibre_min': 45,
            'calibre_max': 55,
            'site_stockage': 'SAINT_FLAVY',
            'quantite_pallox': 7,
            'poids_brut_kg': 13300
        }
    ]

if 'selected_job_id' not in st.session_state:
    st.session_state.selected_job_id = None

if 'job_counter' not in st.session_state:
    st.session_state.job_counter = 15

# ==========================================
# FONCTIONS MÉTIER
# ==========================================

def preparer_events_calendrier():
    """Convertit jobs planifiés en events FullCalendar"""
    events = []
    
    for job in st.session_state.jobs_planifies:
        # Couleur selon statut
        if job['statut'] == 'PRÉVU':
            color = '#2e7d32'  # Vert Culture Pom
        elif job['statut'] == 'EN_COURS':
            color = '#ff8c00'  # Orange
        else:
            color = '#9e9e9e'  # Gris
        
        event = {
            'id': str(job['id']),
            'title': f"{job['variete']} - {job['quantite_pallox']}P",
            'start': f"{job['date_prevue']}T{job['heure_debut']}:00",
            'end': f"{job['date_prevue']}T{job['heure_fin']}:00",
            'color': color,
            'extendedProps': {
                'ligne': job['ligne_lavage'],
                'statut': job['statut'],
                'code_lot': job['code_lot_interne']
            }
        }
        
        events.append(event)
    
    return events

def get_job_by_id(job_id):
    """Récupère un job par son ID"""
    for job in st.session_state.jobs_planifies:
        if job['id'] == job_id:
            return job
    return None

def get_varietes_disponibles():
    """Récupère toutes les variétés des jobs non planifiés"""
    varietes = set([j['variete'] for j in st.session_state.jobs_non_planifies])
    return sorted(list(varietes))

def get_producteurs_disponibles():
    """Récupère tous les producteurs des jobs non planifiés"""
    producteurs = set([j['producteur'] for j in st.session_state.jobs_non_planifies])
    return sorted(list(producteurs))

def filtrer_jobs_non_planifies(variete_filter, producteur_filter, recherche):
    """Filtre les jobs non planifiés selon critères"""
    jobs = st.session_state.jobs_non_planifies.copy()
    
    if variete_filter != "Toutes":
        jobs = [j for j in jobs if j['variete'] == variete_filter]
    
    if producteur_filter != "Tous":
        jobs = [j for j in jobs if j['producteur'] == producteur_filter]
    
    if recherche:
        recherche_lower = recherche.lower()
        jobs = [j for j in jobs if 
                recherche_lower in j['code_lot_interne'].lower() or 
                recherche_lower in j['nom_usage'].lower()]
    
    return jobs

def update_job_times(job_id, new_start, new_end):
    """Met à jour les horaires d'un job après drag & drop"""
    for job in st.session_state.jobs_planifies:
        if job['id'] == job_id:
            # Parser les nouvelles dates
            start_dt = datetime.fromisoformat(new_start.replace('Z', '+00:00'))
            end_dt = datetime.fromisoformat(new_end.replace('Z', '+00:00'))
            
            job['date_prevue'] = start_dt.strftime('%Y-%m-%d')
            job['heure_debut'] = start_dt.strftime('%H:%M')
            job['heure_fin'] = end_dt.strftime('%H:%M')
            
            # Recalculer durée
            duree_min = int((end_dt - start_dt).total_seconds() / 60)
            job['duree_prevue_min'] = duree_min
            
            return True
    return False

# ==========================================
# HEADER
# ==========================================

st.title("🧼 Planning Lavage")

# Métriques en haut
col1, col2, col3, col4 = st.columns(4)

nb_prevus = len([j for j in st.session_state.jobs_planifies if j['statut'] == 'PRÉVU'])
nb_en_cours = len([j for j in st.session_state.jobs_planifies if j['statut'] == 'EN_COURS'])
nb_termines = len([j for j in st.session_state.jobs_planifies if j['statut'] == 'TERMINÉ'])
nb_non_planifies = len(st.session_state.jobs_non_planifies)

with col1:
    st.metric("🎯 Jobs Prévus", nb_prevus)

with col2:
    st.metric("⚙️ Jobs En Cours", nb_en_cours)

with col3:
    st.metric("✅ Jobs Terminés", nb_termines)

with col4:
    st.metric("📦 Jobs à Planifier", nb_non_planifies)

st.markdown("---")

# ==========================================
# SÉLECTION MODE
# ==========================================

mode = st.radio(
    "Mode",
    ["📋 Planification", "🔄 Réorganisation"],
    horizontal=True,
    label_visibility="collapsed"
)

st.markdown("---")

# ==========================================
# MODE 1 : PLANIFICATION (3 colonnes)
# ==========================================

if mode == "📋 Planification":
    
    col_gauche, col_centre, col_droite = st.columns([2, 5, 3])
    
    # ===== COLONNE GAUCHE : FILTRES + JOBS NON PLANIFIÉS =====
    with col_gauche:
        st.markdown("### 🔍 Filtrer Jobs")
        
        # Filtres
        varietes = ["Toutes"] + get_varietes_disponibles()
        filtre_variete = st.selectbox("Variété", varietes, key="filtre_var_plan")
        
        producteurs = ["Tous"] + get_producteurs_disponibles()
        filtre_producteur = st.selectbox("Producteur", producteurs, key="filtre_prod_plan")
        
        recherche = st.text_input("🔎 Recherche", key="recherche_plan")
        
        st.markdown("---")
        
        # Appliquer filtres
        jobs_filtres = filtrer_jobs_non_planifies(filtre_variete, filtre_producteur, recherche)
        
        total_jobs = len(st.session_state.jobs_non_planifies)
        nb_filtres = len(jobs_filtres)
        
        st.markdown(f"### 📦 Jobs à Planifier ({nb_filtres}/{total_jobs})")
        
        if jobs_filtres:
            # Grouper par variété
            varietes_groupes = {}
            for job in jobs_filtres:
                var = job['variete']
                if var not in varietes_groupes:
                    varietes_groupes[var] = []
                varietes_groupes[var].append(job)
            
            # Afficher par variété avec expanders
            for variete, jobs_var in sorted(varietes_groupes.items()):
                with st.expander(f"🌱 {variete} ({len(jobs_var)} jobs)", expanded=len(varietes_groupes)==1):
                    for job in jobs_var:
                        st.markdown(f"**{job['nom_usage']}**")
                        st.caption(f"📦 {job['quantite_pallox']} pallox - ⚖️ {job['poids_brut_kg']/1000:.1f} T")
                        st.caption(f"👨‍🌾 {job['producteur']} - 📏 {job['calibre_min']}/{job['calibre_max']}")
                        
                        if st.button(f"➕ Planifier", key=f"plan_{job['id']}", use_container_width=True):
                            st.info("📅 Fonctionnalité de planification à implémenter")
                        
                        st.markdown("---")
        else:
            st.info("Aucun job ne correspond aux filtres")
    
    # ===== COLONNE CENTRE : CALENDRIER LECTURE SEULE =====
    with col_centre:
        st.markdown("### 📅 Planning (lecture seule)")
        st.caption("👉 Cliquez sur un job pour voir les détails")
        
        events = preparer_events_calendrier()
        
        # Calendrier LECTURE SEULE (editable=False)
        calendar_event = fullcalendar_component(
            events=events,
            editable=False,
            height=600,
            key="calendar_planification"
        )
        
        # Détecter clic
        if calendar_event and isinstance(calendar_event, dict) and calendar_event.get('type') == 'click':
            st.session_state.selected_job_id = calendar_event['job_id']
            st.rerun()
    
    # ===== COLONNE DROITE : DÉTAIL JOB =====
    with col_droite:
        st.markdown("### 📋 Détails Job")
        
        if st.session_state.selected_job_id:
            job = get_job_by_id(st.session_state.selected_job_id)
            
            if job:
                st.markdown(f"""
                <div class="detail-card">
                    <h3 style="color: #2e7d32; margin-top: 0;">🎯 Job #{job['id']}</h3>
                    <p style="font-size: 1.2em; font-weight: 700; margin: 0.5rem 0;">{job['variete']}</p>
                    <p style="color: #666; margin-bottom: 1rem;">{job['code_lot_interne']}</p>
                </div>
                """, unsafe_allow_html=True)
                
                # Informations avec icônes
                st.markdown(f"""
                <div class="info-row">
                    <span class="info-icon">📦</span>
                    <span class="info-label">Quantité:</span>
                    <span class="info-value">{job['quantite_pallox']} pallox</span>
                </div>
                """, unsafe_allow_html=True)
                
                st.markdown(f"""
                <div class="info-row">
                    <span class="info-icon">⚖️</span>
                    <span class="info-label">Poids:</span>
                    <span class="info-value">{job['poids_brut_kg']/1000:.1f} T</span>
                </div>
                """, unsafe_allow_html=True)
                
                st.markdown(f"""
                <div class="info-row">
                    <span class="info-icon">👨‍🌾</span>
                    <span class="info-label">Producteur:</span>
                    <span class="info-value">{job['producteur']}</span>
                </div>
                """, unsafe_allow_html=True)
                
                st.markdown(f"""
                <div class="info-row">
                    <span class="info-icon">📏</span>
                    <span class="info-label">Calibre:</span>
                    <span class="info-value">{job['calibre_min']}/{job['calibre_max']}</span>
                </div>
                """, unsafe_allow_html=True)
                
                st.markdown(f"""
                <div class="info-row">
                    <span class="info-icon">📅</span>
                    <span class="info-label">Date:</span>
                    <span class="info-value">{job['date_prevue']}</span>
                </div>
                """, unsafe_allow_html=True)
                
                st.markdown(f"""
                <div class="info-row">
                    <span class="info-icon">🕒</span>
                    <span class="info-label">Horaire:</span>
                    <span class="info-value">{job['heure_debut']} - {job['heure_fin']}</span>
                </div>
                """, unsafe_allow_html=True)
                
                st.markdown(f"""
                <div class="info-row">
                    <span class="info-icon">🔧</span>
                    <span class="info-label">Ligne:</span>
                    <span class="info-value">{job['ligne_lavage']}</span>
                </div>
                """, unsafe_allow_html=True)
                
                st.markdown(f"""
                <div class="info-row">
                    <span class="info-icon">🏷️</span>
                    <span class="info-label">Statut:</span>
                    <span class="metric-badge">{job['statut']}</span>
                </div>
                """, unsafe_allow_html=True)
                
                st.markdown("<br>", unsafe_allow_html=True)
                
                # Boutons actions selon statut
                if job['statut'] == 'PRÉVU':
                    if st.button("▶️ Démarrer Job", type="primary", use_container_width=True):
                        st.info("⚙️ Fonctionnalité de démarrage à implémenter")
                    
                    if st.button("📝 Modifier", use_container_width=True):
                        st.info("✏️ Fonctionnalité de modification à implémenter")
                
                elif job['statut'] == 'EN_COURS':
                    st.info(f"⏱️ Démarré: {job.get('date_debut_reel', 'N/A')}")
                    
                    if st.button("⏸️ Terminer Job", type="primary", use_container_width=True):
                        st.info("🏁 Fonctionnalité de terminaison à implémenter")
                
                elif job['statut'] == 'TERMINÉ':
                    st.success("✅ Job terminé")
                    
                    if job.get('rendement_pct'):
                        col1, col2 = st.columns(2)
                        with col1:
                            st.metric("Rendement", f"{job['rendement_pct']:.1f}%")
                        with col2:
                            st.metric("Tare", f"{job['tare_pct']:.1f}%")
            
            else:
                st.warning("Job introuvable")
        
        else:
            st.info("👈 Cliquez sur un job dans le calendrier pour voir les détails")

# ==========================================
# MODE 2 : RÉORGANISATION (plein écran drag & drop)
# ==========================================

elif mode == "🔄 Réorganisation":
    
    st.markdown("### 🔄 Mode Réorganisation - Drag & Drop Actif")
    st.caption("📌 Glissez-déposez les jobs pour réorganiser le planning")
    
    events = preparer_events_calendrier()
    
    # Calendrier ÉDITABLE (editable=True)
    calendar_event = fullcalendar_component(
        events=events,
        editable=True,
        height=700,
        key="calendar_reorganisation"
    )
    
    # Détecter drag & drop
    if calendar_event and isinstance(calendar_event, dict):
        
        if calendar_event.get('type') == 'drop':
            # Mise à jour après drag & drop
            job_id = calendar_event['job_id']
            new_start = calendar_event['new_start']
            new_end = calendar_event['new_end']
            
            if update_job_times(job_id, new_start, new_end):
                st.success(f"✅ Job #{job_id} déplacé avec succès")
                st.rerun()
            else:
                st.error(f"❌ Erreur lors du déplacement du job #{job_id}")
        
        elif calendar_event.get('type') == 'resize':
            # Mise à jour après redimensionnement
            job_id = calendar_event['job_id']
            new_start = calendar_event['new_start']
            new_end = calendar_event['new_end']
            
            if update_job_times(job_id, new_start, new_end):
                st.success(f"✅ Durée du job #{job_id} modifiée")
                st.rerun()
            else:
                st.error(f"❌ Erreur lors de la modification")
        
        elif calendar_event.get('type') == 'click':
            # Afficher détails en modal (ou panneau)
            st.session_state.selected_job_id = calendar_event['job_id']
            st.rerun()
    
    # Afficher détail job si sélectionné
    if st.session_state.selected_job_id:
        job = get_job_by_id(st.session_state.selected_job_id)
        
        if job:
            st.markdown("---")
            st.markdown(f"### 📋 Job sélectionné : #{job['id']} - {job['variete']}")
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.info(f"📦 {job['quantite_pallox']} pallox")
                st.info(f"⚖️ {job['poids_brut_kg']/1000:.1f} T")
            
            with col2:
                st.info(f"📅 {job['date_prevue']}")
                st.info(f"🕒 {job['heure_debut']} - {job['heure_fin']}")
            
            with col3:
                st.info(f"🔧 {job['ligne_lavage']}")
                st.info(f"🏷️ {job['statut']}")
            
            if st.button("❌ Fermer détails"):
                st.session_state.selected_job_id = None
                st.rerun()

st.markdown("---")
st.caption("POC - Données en session_state (pas DB) - FullCalendar gratuit avec drag & drop")
