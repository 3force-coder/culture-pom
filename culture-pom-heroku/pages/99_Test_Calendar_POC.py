import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import json
import streamlit.components.v1 as components

st.set_page_config(page_title="POC Planning Lavage - 3 Colonnes", page_icon="🧼", layout="wide")

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
    
    /* Jobs non planifiés */
    .job-non-planifie {
        background-color: #f8f9fa;
        padding: 0.8rem;
        border-radius: 0.5rem;
        margin-bottom: 0.5rem;
        border-left: 4px solid #6c757d;
    }
    .job-non-planifie:hover {
        background-color: #e9ecef;
    }
    
    /* Détail job */
    .job-detail {
        background-color: #f0f7f0;
        padding: 1rem;
        border-radius: 0.5rem;
        border-left: 4px solid #2e7d32;
    }
    .metric-box {
        background-color: #fff;
        padding: 0.5rem;
        border-radius: 0.3rem;
        margin: 0.3rem 0;
    }
</style>
""", unsafe_allow_html=True)

st.title("🧼 POC Planning Lavage - 3 Colonnes + Filtres")
st.markdown("---")

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
            'duree_reelle_min': None,
            'poids_lave_kg': None,
            'poids_grenailles_kg': None,
            'poids_dechets_kg': None,
            'poids_terre_kg': None,
            'tare_pct': None,
            'rendement_pct': None
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
            'date_debut_reel': None,
            'duree_prevue_min': 110,
            'duree_reelle_min': None,
            'poids_lave_kg': None,
            'poids_grenailles_kg': None,
            'poids_dechets_kg': None,
            'poids_terre_kg': None,
            'tare_pct': None,
            'rendement_pct': None
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

if 'job_counter' not in st.session_state:
    st.session_state.job_counter = 15

if 'selected_job_id' not in st.session_state:
    st.session_state.selected_job_id = None

# ==========================================
# FONCTIONS MÉTIER
# ==========================================

def demarrer_job(job_id):
    """Démarre un job : PRÉVU → EN_COURS"""
    for job in st.session_state.jobs_planifies:
        if job['id'] == job_id and job['statut'] == 'PRÉVU':
            job['statut'] = 'EN_COURS'
            job['date_debut_reel'] = datetime.now().strftime('%Y-%m-%d %H:%M')
            return True, f"✅ Job #{job_id} démarré"
    return False, "❌ Job introuvable ou déjà démarré"

def terminer_job(job_id, poids_lave, poids_grenailles, poids_dechets):
    """Termine un job : calculs + décalage automatique"""
    for job in st.session_state.jobs_planifies:
        if job['id'] == job_id and job['statut'] == 'EN_COURS':
            poids_brut = job['poids_brut_kg']
            
            # Calcul terre
            poids_terre = poids_brut - (poids_lave + poids_grenailles + poids_dechets)
            
            # Validation cohérence (tolérance 10 kg)
            total_calc = poids_lave + poids_grenailles + poids_dechets + poids_terre
            if abs(total_calc - poids_brut) > 10:
                return False, f"❌ Incohérence poids : Brut={poids_brut:.0f} vs Total={total_calc:.0f}"
            
            # Calculs
            tare_pct = ((poids_dechets + poids_terre) / poids_brut) * 100
            rendement_pct = ((poids_lave + poids_grenailles) / poids_brut) * 100
            
            # Durée réelle
            debut = datetime.strptime(job['date_debut_reel'], '%Y-%m-%d %H:%M')
            fin = datetime.now()
            duree_reelle_min = int((fin - debut).total_seconds() / 60)
            
            # MAJ job
            job['statut'] = 'TERMINÉ'
            job['duree_reelle_min'] = duree_reelle_min
            job['poids_lave_kg'] = poids_lave
            job['poids_grenailles_kg'] = poids_grenailles
            job['poids_dechets_kg'] = poids_dechets
            job['poids_terre_kg'] = poids_terre
            job['tare_pct'] = tare_pct
            job['rendement_pct'] = rendement_pct
            
            # Décalage automatique
            decalage_min = duree_reelle_min - job['duree_prevue_min']
            if decalage_min != 0:
                decaler_jobs_suivants(job['date_prevue'], job['ligne_lavage'], job['heure_fin'], decalage_min)
            
            return True, f"✅ Job terminé - Rendement: {rendement_pct:.1f}%"
    
    return False, "❌ Job introuvable ou pas EN_COURS"

def decaler_jobs_suivants(date_job, ligne, heure_fin_job, decalage_min):
    """Décale les jobs suivants sur même ligne/jour"""
    for job in st.session_state.jobs_planifies:
        if (job['date_prevue'] == date_job and 
            job['ligne_lavage'] == ligne and 
            job['heure_debut'] >= heure_fin_job and
            job['statut'] == 'PRÉVU'):
            
            # Décaler heure_debut et heure_fin
            debut = datetime.strptime(f"{date_job} {job['heure_debut']}", '%Y-%m-%d %H:%M')
            fin = datetime.strptime(f"{date_job} {job['heure_fin']}", '%Y-%m-%d %H:%M')
            
            nouveau_debut = debut + timedelta(minutes=decalage_min)
            nouveau_fin = fin + timedelta(minutes=decalage_min)
            
            job['heure_debut'] = nouveau_debut.strftime('%H:%M')
            job['heure_fin'] = nouveau_fin.strftime('%H:%M')

def ajouter_job_calendrier(job_data, date_prevue, heure_debut, ligne):
    """Planifie un job non planifié"""
    poids_kg = job_data['poids_brut_kg']
    duree_min = int((poids_kg / 1000) / 13.0 * 60)  # 13 T/h
    
    heure_debut_dt = datetime.strptime(f"{date_prevue} {heure_debut}", '%Y-%m-%d %H:%M')
    heure_fin_dt = heure_debut_dt + timedelta(minutes=duree_min)
    
    nouveau_job = {
        'id': st.session_state.job_counter,
        'lot_id': job_data['lot_id'],
        'code_lot_interne': job_data['code_lot_interne'],
        'nom_usage': job_data['nom_usage'],
        'variete': job_data['variete'],
        'producteur': job_data['producteur'],
        'calibre_min': job_data['calibre_min'],
        'calibre_max': job_data['calibre_max'],
        'site_stockage': job_data['site_stockage'],
        'quantite_pallox': job_data['quantite_pallox'],
        'poids_brut_kg': poids_kg,
        'date_prevue': date_prevue,
        'heure_debut': heure_debut,
        'heure_fin': heure_fin_dt.strftime('%H:%M'),
        'ligne_lavage': ligne,
        'statut': 'PRÉVU',
        'date_debut_reel': None,
        'duree_prevue_min': duree_min,
        'duree_reelle_min': None,
        'poids_lave_kg': None,
        'poids_grenailles_kg': None,
        'poids_dechets_kg': None,
        'poids_terre_kg': None,
        'tare_pct': None,
        'rendement_pct': None
    }
    
    st.session_state.jobs_planifies.append(nouveau_job)
    st.session_state.jobs_non_planifies = [j for j in st.session_state.jobs_non_planifies if j['id'] != job_data['id']]
    st.session_state.job_counter += 1
    
    return True, f"✅ Job #{nouveau_job['id']} planifié"

# ==========================================
# DONNÉES FILTRES
# ==========================================

def get_varietes_disponibles():
    """Récupère toutes les variétés des jobs non planifiés"""
    varietes = set([j['variete'] for j in st.session_state.jobs_non_planifies])
    return sorted(list(varietes))

def get_producteurs_disponibles():
    """Récupère tous les producteurs des jobs non planifiés"""
    producteurs = set([j['producteur'] for j in st.session_state.jobs_non_planifies])
    return sorted(list(producteurs))

def get_calibres_disponibles():
    """Récupère tous les calibres uniques"""
    calibres = set()
    for j in st.session_state.jobs_non_planifies:
        calibres.add(f"{j['calibre_min']}/{j['calibre_max']}")
    return sorted(list(calibres))

def get_sites_disponibles():
    """Récupère tous les sites de stockage"""
    sites = set([j['site_stockage'] for j in st.session_state.jobs_non_planifies])
    return sorted(list(sites))

def filtrer_jobs_non_planifies(variete_filter, producteur_filter, calibre_filter, site_filter, recherche):
    """Filtre les jobs non planifiés selon critères"""
    jobs = st.session_state.jobs_non_planifies.copy()
    
    if variete_filter != "Toutes":
        jobs = [j for j in jobs if j['variete'] == variete_filter]
    
    if producteur_filter != "Tous":
        jobs = [j for j in jobs if j['producteur'] == producteur_filter]
    
    if calibre_filter != "Tous":
        jobs = [j for j in jobs if f"{j['calibre_min']}/{j['calibre_max']}" == calibre_filter]
    
    if site_filter != "Tous":
        jobs = [j for j in jobs if j['site_stockage'] == site_filter]
    
    if recherche:
        recherche_lower = recherche.lower()
        jobs = [j for j in jobs if 
                recherche_lower in j['code_lot_interne'].lower() or 
                recherche_lower in j['nom_usage'].lower()]
    
    return jobs

# ==========================================
# PRÉPARATION EVENTS FULLCALENDAR
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
                'statut': job['statut']
            }
        }
        
        events.append(event)
    
    return events

# ==========================================
# LAYOUT 3 COLONNES
# ==========================================

col_gauche, col_centre, col_droite = st.columns([2, 5, 3])

# ==========================================
# COLONNE GAUCHE : FILTRES + JOBS NON PLANIFIÉS
# ==========================================

with col_gauche:
    st.markdown("### 🔍 Filtrer Jobs à Planifier")
    
    # Filtres
    varietes = ["Toutes"] + get_varietes_disponibles()
    filtre_variete = st.selectbox("Variété", varietes, key="filtre_variete")
    
    producteurs = ["Tous"] + get_producteurs_disponibles()
    filtre_producteur = st.selectbox("Producteur", producteurs, key="filtre_producteur")
    
    calibres = ["Tous"] + get_calibres_disponibles()
    filtre_calibre = st.selectbox("Calibre", calibres, key="filtre_calibre")
    
    sites = ["Tous"] + get_sites_disponibles()
    filtre_site = st.selectbox("Site", sites, key="filtre_site")
    
    recherche = st.text_input("🔎 Recherche (code/nom)", key="recherche")
    
    st.markdown("---")
    
    # Appliquer filtres
    jobs_filtres = filtrer_jobs_non_planifies(
        filtre_variete, filtre_producteur, filtre_calibre, filtre_site, recherche
    )
    
    total_jobs = len(st.session_state.jobs_non_planifies)
    nb_filtres = len(jobs_filtres)
    
    st.markdown(f"### 📋 Jobs à Planifier ({nb_filtres}/{total_jobs})")
    
    if jobs_filtres:
        for job in jobs_filtres:
            with st.container():
                st.markdown(f"""
                <div class="job-non-planifie">
                    <strong>{job['variete']}</strong> - {job['code_lot_interne']}<br>
                    📦 {job['quantite_pallox']} pallox - ⚖️ {job['poids_brut_kg']/1000:.1f} T<br>
                    👨‍🌾 {job['producteur']}<br>
                    📏 {job['calibre_min']}/{job['calibre_max']}
                </div>
                """, unsafe_allow_html=True)
                
                if st.button(f"➕ Planifier", key=f"plan_{job['id']}", use_container_width=True):
                    st.session_state[f'show_form_plan_{job["id"]}'] = True
                    st.rerun()
                
                # Formulaire planification
                if st.session_state.get(f'show_form_plan_{job["id"]}', False):
                    date_plan = st.date_input("Date", value=datetime.now().date(), key=f"date_{job['id']}")
                    heure_plan = st.time_input("Heure", value=datetime.strptime("08:00", "%H:%M").time(), key=f"heure_{job['id']}")
                    ligne_plan = st.selectbox("Ligne", ["LIGNE_1", "LIGNE_2"], key=f"ligne_{job['id']}")
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        if st.button("✅ OK", key=f"ok_{job['id']}", use_container_width=True):
                            success, msg = ajouter_job_calendrier(
                                job, 
                                date_plan.strftime('%Y-%m-%d'), 
                                heure_plan.strftime('%H:%M'),
                                ligne_plan
                            )
                            if success:
                                st.success(msg)
                                st.session_state.pop(f'show_form_plan_{job["id"]}')
                                st.rerun()
                            else:
                                st.error(msg)
                    
                    with col2:
                        if st.button("❌", key=f"cancel_{job['id']}", use_container_width=True):
                            st.session_state.pop(f'show_form_plan_{job["id"]}')
                            st.rerun()
                
                st.markdown("<br>", unsafe_allow_html=True)
    else:
        st.info("Aucun job ne correspond aux filtres")

# ==========================================
# COLONNE CENTRE : CALENDRIER FULLCALENDAR
# ==========================================

with col_centre:
    st.markdown("### 📅 Planning Lavage")
    
    events = preparer_events_calendrier()
    events_json = json.dumps(events)
    
    # HTML FullCalendar avec gestion clic
    calendar_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <link href='https://cdn.jsdelivr.net/npm/fullcalendar@6.1.10/index.global.min.css' rel='stylesheet' />
        <script src='https://cdn.jsdelivr.net/npm/fullcalendar@6.1.10/index.global.min.js'></script>
        <style>
            #calendar {{
                max-width: 100%;
                margin: 0 auto;
                font-family: Arial, sans-serif;
            }}
            .fc {{
                background-color: white;
            }}
            .fc-header-toolbar {{
                margin-bottom: 1em !important;
            }}
            .fc-daygrid-day-number {{
                color: #2e7d32 !important;
                font-weight: bold;
            }}
            .fc-col-header-cell-cushion {{
                color: #2e7d32 !important;
                font-weight: bold;
            }}
            .fc-timegrid-now-indicator-line {{
                border-color: #ff8c00 !important;
                border-width: 2px !important;
            }}
            .fc-event {{
                cursor: pointer;
            }}
            .fc-event:hover {{
                opacity: 0.8;
            }}
        </style>
    </head>
    <body>
        <div id='calendar'></div>
        
        <script>
            document.addEventListener('DOMContentLoaded', function() {{
                var calendarEl = document.getElementById('calendar');
                
                var calendar = new FullCalendar.Calendar(calendarEl, {{
                    initialView: 'timeGridWeek',
                    locale: 'fr',
                    headerToolbar: {{
                        left: 'prev,next today',
                        center: 'title',
                        right: 'timeGridWeek,timeGridDay'
                    }},
                    slotMinTime: '06:00:00',
                    slotMaxTime: '20:00:00',
                    allDaySlot: false,
                    height: 'auto',
                    nowIndicator: true,
                    scrollTime: '08:00:00',
                    events: {events_json},
                    eventClick: function(info) {{
                        // Envoyer l'ID du job cliqué à Streamlit
                        var jobId = info.event.id;
                        
                        // Communication via query params (workaround)
                        var newUrl = window.location.origin + window.location.pathname + '?selected_job=' + jobId;
                        window.parent.postMessage({{
                            type: 'streamlit:setComponentValue',
                            value: jobId
                        }}, '*');
                        
                        // Alternative : stocker dans localStorage
                        localStorage.setItem('selected_job_id', jobId);
                    }}
                }});
                
                calendar.render();
                
                // Auto-scroll aujourd'hui
                setTimeout(function() {{
                    calendar.scrollToTime(new Date().getHours() + ':00:00');
                }}, 500);
            }});
        </script>
    </body>
    </html>
    """
    
    # Afficher calendrier
    components.html(calendar_html, height=650, scrolling=True)
    
    # Workaround : Sélection manuelle sous calendrier
    st.markdown("---")
    st.markdown("**Sélectionner un job** *(cliquer dans calendrier à venir)*")
    
    jobs_options = {f"#{j['id']} - {j['code_lot_interne']} - {j['variete']}": j['id'] 
                    for j in st.session_state.jobs_planifies}
    
    if jobs_options:
        selected_label = st.selectbox(
            "Job à afficher",
            options=[""] + list(jobs_options.keys()),
            key="manual_job_select"
        )
        
        if selected_label:
            st.session_state.selected_job_id = jobs_options[selected_label]

# ==========================================
# COLONNE DROITE : DÉTAIL JOB
# ==========================================

with col_droite:
    st.markdown("### 📋 Détails Job")
    
    if st.session_state.selected_job_id:
        # Trouver le job sélectionné
        job_detail = None
        for j in st.session_state.jobs_planifies:
            if j['id'] == st.session_state.selected_job_id:
                job_detail = j
                break
        
        if job_detail:
            st.markdown(f"""
            <div class="job-detail">
                <h4>🎯 Job #{job_detail['id']}</h4>
                <strong>{job_detail['variete']}</strong><br>
                {job_detail['code_lot_interne']}<br><br>
                
                📦 {job_detail['quantite_pallox']} pallox<br>
                ⚖️ {job_detail['poids_brut_kg']/1000:.1f} T<br>
                👨‍🌾 {job_detail['producteur']}<br>
                📏 {job_detail['calibre_min']}/{job_detail['calibre_max']}<br><br>
                
                📅 {job_detail['date_prevue']}<br>
                🕒 {job_detail['heure_debut']} - {job_detail['heure_fin']}<br>
                🔧 {job_detail['ligne_lavage']}<br>
                🏷️ <strong>{job_detail['statut']}</strong>
            </div>
            """, unsafe_allow_html=True)
            
            st.markdown("<br>", unsafe_allow_html=True)
            
            # ACTIONS SELON STATUT
            if job_detail['statut'] == 'PRÉVU':
                if st.button("▶️ Démarrer Job", type="primary", use_container_width=True):
                    success, msg = demarrer_job(job_detail['id'])
                    if success:
                        st.success(msg)
                        st.rerun()
                    else:
                        st.error(msg)
            
            elif job_detail['statut'] == 'EN_COURS':
                st.info(f"⏱️ Démarré : {job_detail['date_debut_reel']}")
                
                if st.button("⏸️ Terminer Job", type="primary", use_container_width=True):
                    st.session_state[f'show_qualification_{job_detail["id"]}'] = True
                    st.rerun()
                
                # Modal qualification
                if st.session_state.get(f'show_qualification_{job_detail["id"]}', False):
                    st.markdown("---")
                    st.markdown("**📊 Qualification Tares**")
                    
                    poids_lave = st.number_input(
                        "Poids lavé net (kg) *",
                        min_value=0.0,
                        value=float(job_detail['poids_brut_kg']) * 0.75,
                        step=100.0,
                        key=f"lave_{job_detail['id']}"
                    )
                    
                    poids_grenailles = st.number_input(
                        "Poids grenailles (kg) *",
                        min_value=0.0,
                        value=float(job_detail['poids_brut_kg']) * 0.05,
                        step=10.0,
                        key=f"gren_{job_detail['id']}"
                    )
                    
                    poids_dechets = st.number_input(
                        "Poids déchets (kg) *",
                        min_value=0.0,
                        value=float(job_detail['poids_brut_kg']) * 0.05,
                        step=10.0,
                        key=f"dech_{job_detail['id']}"
                    )
                    
                    poids_terre_calc = job_detail['poids_brut_kg'] - poids_lave - poids_grenailles - poids_dechets
                    st.metric("Terre calculée", f"{poids_terre_calc:.0f} kg")
                    
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        if st.button("✅ Valider", type="primary", use_container_width=True, key=f"valid_{job_detail['id']}"):
                            success, msg = terminer_job(job_detail['id'], poids_lave, poids_grenailles, poids_dechets)
                            if success:
                                st.success(msg)
                                st.session_state.pop(f'show_qualification_{job_detail["id"]}')
                                st.rerun()
                            else:
                                st.error(msg)
                    
                    with col2:
                        if st.button("❌ Annuler", use_container_width=True, key=f"annul_{job_detail['id']}"):
                            st.session_state.pop(f'show_qualification_{job_detail["id"]}')
                            st.rerun()
            
            elif job_detail['statut'] == 'TERMINÉ':
                st.markdown("---")
                st.markdown("**📊 Résultats**")
                
                st.markdown(f"""
                <div class="metric-box">
                    <strong>Rendement</strong><br>
                    {job_detail['rendement_pct']:.1f}%
                </div>
                <div class="metric-box">
                    <strong>Tare réelle</strong><br>
                    {job_detail['tare_pct']:.1f}%
                </div>
                <div class="metric-box">
                    <strong>Durée réelle</strong><br>
                    {job_detail['duree_reelle_min']} min ({job_detail['duree_reelle_min']//60}h{job_detail['duree_reelle_min']%60:02d})
                </div>
                """, unsafe_allow_html=True)
                
                st.markdown("---")
                st.markdown(f"""
                **Détails poids** :<br>
                • Lavé : {job_detail['poids_lave_kg']:.0f} kg<br>
                • Grenailles : {job_detail['poids_grenailles_kg']:.0f} kg<br>
                • Déchets : {job_detail['poids_dechets_kg']:.0f} kg<br>
                • Terre : {job_detail['poids_terre_kg']:.0f} kg
                """, unsafe_allow_html=True)
        
        else:
            st.info("Job sélectionné introuvable")
    
    else:
        st.info("👈 Sélectionnez un job dans le calendrier ou le dropdown")

st.markdown("---")
st.caption("POC - Données en session_state (pas DB)")
