"""
POC COMPLET Planning Lavage - ÉTAPE 1.5
========================================

Workflow complet AVANT connexion DB :
- Démarrer/Arrêter jobs
- Modal qualification (poids, tares, rendement)
- Décalage automatique jobs suivants
- Zone drag & drop jobs non planifiés
- Communication bidirectionnelle JS ↔ Python

TEST avec données en session_state (pas DB)
"""

import streamlit as st
import streamlit.components.v1 as components
import json
from datetime import datetime, timedelta
from auth import is_authenticated
from components import show_footer

st.set_page_config(page_title="POC Planning Complet", page_icon="🧪", layout="wide")

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
    
    .job-non-planifie {
        background: white;
        border: 2px solid #2E7D32;
        border-radius: 8px;
        padding: 12px;
        margin: 8px 0;
        cursor: move;
        transition: all 0.2s;
    }
    .job-non-planifie:hover {
        background: #E8F5E9;
        transform: translateY(-2px);
        box-shadow: 0 4px 8px rgba(0,0,0,0.1);
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
            'statut': 'PRÉVU',
            'date_creation': datetime.now().isoformat()
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
            'statut': 'PRÉVU',
            'date_creation': datetime.now().isoformat()
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
            'date_debut_reel': (datetime.now() - timedelta(hours=1)).isoformat(),
            'date_creation': datetime.now().isoformat()
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
    return False, "❌ Job introuvable ou déjà démarré"

def terminer_job(job_id, poids_lave, poids_grenailles, poids_dechets):
    """Termine un job avec qualification"""
    for job in st.session_state.jobs_planifies:
        if job['id'] == job_id and job['statut'] == 'EN_COURS':
            # Calculs
            poids_brut = float(job['poids_estime_kg'])
            poids_terre = poids_brut - poids_lave - poids_grenailles - poids_dechets
            
            # Validation cohérence
            total = poids_lave + poids_grenailles + poids_dechets + poids_terre
            if abs(total - poids_brut) > 10:  # Tolérance 10kg
                return False, f"❌ Incohérence poids : Brut={poids_brut:.0f} vs Total={total:.0f}"
            
            # Calcul tare et rendement
            tare_pct = ((poids_dechets + poids_terre) / poids_brut) * 100
            rendement_pct = ((poids_lave + poids_grenailles) / poids_brut) * 100
            
            # Durée réelle
            debut = datetime.fromisoformat(job['date_debut_reel'])
            fin = datetime.now()
            duree_reelle_min = int((fin - debut).total_seconds() / 60)
            
            # Mise à jour job
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
            
            return True, f"✅ Job terminé - Rendement: {rendement_pct:.1f}%"
    
    return False, "❌ Job introuvable ou pas EN_COURS"

def decaler_jobs_suivants(job_termine, decalage_min):
    """Décale automatiquement les jobs suivants sur la même ligne"""
    if decalage_min == 0:
        return
    
    ligne = job_termine['ligne']
    date = job_termine['date']
    heure_fin = job_termine['heure_fin']
    
    for job in st.session_state.jobs_planifies:
        # Jobs suivants = même ligne, même jour, après job terminé
        if (job['ligne'] == ligne and 
            job['date'] == date and 
            job['heure_debut'] >= heure_fin and
            job['statut'] == 'PRÉVU'):
            
            # Convertir heures en datetime
            debut = datetime.strptime(f"{date} {job['heure_debut']}", "%Y-%m-%d %H:%M")
            fin = datetime.strptime(f"{date} {job['heure_fin']}", "%Y-%m-%d %H:%M")
            
            # Appliquer décalage
            nouveau_debut = debut + timedelta(minutes=decalage_min)
            nouveau_fin = fin + timedelta(minutes=decalage_min)
            
            # Mise à jour
            job['heure_debut'] = nouveau_debut.strftime("%H:%M")
            job['heure_fin'] = nouveau_fin.strftime("%H:%M")

def ajouter_job_calendrier(job_data, date, heure_debut, ligne):
    """Ajoute un job non planifié au calendrier"""
    # Calculer heure fin
    duree_min = int((float(job_data['poids_estime_kg']) / 1000) / 13.0 * 60)  # 13 T/h
    debut = datetime.strptime(f"{date} {heure_debut}", "%Y-%m-%d %H:%M")
    fin = debut + timedelta(minutes=duree_min)
    
    # Créer job planifié
    nouveau_job = {
        'id': st.session_state.job_counter,
        'variete': job_data['variete'],
        'lot_id': job_data['lot_id'],
        'quantite_pallox': job_data['quantite_pallox'],
        'poids_estime_kg': job_data['poids_estime_kg'],
        'date': date,
        'heure_debut': heure_debut,
        'heure_fin': fin.strftime("%H:%M"),
        'duree_prevue_min': duree_min,
        'ligne': ligne,
        'statut': 'PRÉVU',
        'date_creation': datetime.now().isoformat()
    }
    
    st.session_state.jobs_planifies.append(nouveau_job)
    st.session_state.job_counter += 1
    
    # Retirer de la liste non planifiés
    st.session_state.jobs_non_planifies = [
        j for j in st.session_state.jobs_non_planifies if j['id'] != job_data['id']
    ]
    
    return True, f"✅ Job #{nouveau_job['id']} ajouté au planning"

# ============================================================
# INTERFACE
# ============================================================

st.title("🧪 POC Planning COMPLET")
st.caption("Test workflow complet AVANT connexion DB")

# Tabs
tab1, tab2, tab3 = st.tabs(["📅 Calendrier", "⚙️ Actions Jobs", "📋 Jobs Non Planifiés"])

# ============================================================
# TAB 1 : CALENDRIER
# ============================================================

with tab1:
    st.subheader("📅 Planning avec Drag & Drop")
    
    # Préparer événements pour FullCalendar
    events = []
    for job in st.session_state.jobs_planifies:
        if job['statut'] == 'EN_COURS':
            color = '#FF6B35'
        elif job['statut'] == 'TERMINÉ':
            color = '#95A5A6'
        else:
            color = '#2ECC71'
        
        events.append({
            'id': str(job['id']),
            'title': f"[{job['ligne']}] #{job['id']} {job['variete']} ({job['quantite_pallox']}p)",
            'start': f"{job['date']}T{job['heure_debut']}:00",
            'end': f"{job['date']}T{job['heure_fin']}:00",
            'backgroundColor': color,
            'borderColor': color,
            'textColor': '#FFFFFF',
            'extendedProps': {
                'job_id': job['id'],
                'statut': job['statut'],
                'variete': job['variete'],
                'ligne': job['ligne']
            }
        })
    
    today = datetime.now().strftime('%Y-%m-%d')
    
    calendar_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <link href='https://cdn.jsdelivr.net/npm/fullcalendar@6.1.10/index.global.min.css' rel='stylesheet' />
        <style>
            body {{ margin: 0; padding: 10px; font-family: sans-serif; }}
            #calendar {{ background: white; padding: 20px; border-radius: 12px; }}
            
            .fc .fc-toolbar {{
                background: linear-gradient(135deg, #2E7D32 0%, #388E3C 100%);
                padding: 15px;
                border-radius: 8px;
                margin-bottom: 15px;
            }}
            .fc .fc-toolbar-title {{ color: white !important; }}
            .fc .fc-button {{
                background: rgba(255,255,255,0.2) !important;
                border: 1px solid rgba(255,255,255,0.3) !important;
                color: white !important;
            }}
            .fc-event {{ border-radius: 6px !important; cursor: move !important; }}
            .fc .fc-timegrid-now-indicator-line {{ border-color: #E74C3C !important; border-width: 2px !important; }}
        </style>
    </head>
    <body>
        <div id='calendar'></div>
        
        <script src='https://cdn.jsdelivr.net/npm/fullcalendar@6.1.10/index.global.min.js'></script>
        <script>
        const eventsData = {json.dumps(events)};
        
        document.addEventListener('DOMContentLoaded', function() {{
            const calendar = new FullCalendar.Calendar(document.getElementById('calendar'), {{
                initialView: 'timeGridWeek',
                initialDate: '{today}',
                locale: 'fr',
                events: eventsData,
                editable: true,
                nowIndicator: true,
                scrollTime: new Date().toTimeString().slice(0, 8),
                slotMinTime: '05:00:00',
                slotMaxTime: '22:00:00',
                height: 600,
                allDaySlot: false,
                
                headerToolbar: {{
                    left: 'prev,next today',
                    center: 'title',
                    right: 'timeGridWeek,timeGridDay'
                }},
                
                buttonText: {{
                    today: "Aujourd'hui",
                    week: 'Semaine',
                    day: 'Jour'
                }},
                
                eventDrop: function(info) {{
                    const event = info.event;
                    // Communication avec Streamlit
                    window.parent.postMessage({{
                        type: 'job_moved',
                        job_id: event.extendedProps.job_id,
                        new_start: event.start.toISOString(),
                        new_end: event.end.toISOString()
                    }}, '*');
                }},
                
                eventResize: function(info) {{
                    const event = info.event;
                    window.parent.postMessage({{
                        type: 'job_resized',
                        job_id: event.extendedProps.job_id,
                        new_end: event.end.toISOString()
                    }}, '*');
                }},
                
                eventAllow: function(dropInfo, draggedEvent) {{
                    return draggedEvent.extendedProps.statut !== 'TERMINÉ';
                }}
            }});
            
            calendar.render();
        }});
        </script>
    </body>
    </html>
    """
    
    components.html(calendar_html, height=650, scrolling=False)

# ============================================================
# TAB 2 : ACTIONS JOBS
# ============================================================

with tab2:
    st.subheader("⚙️ Gérer les Jobs")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("### ▶️ Démarrer Job")
        jobs_prevus = [j for j in st.session_state.jobs_planifies if j['statut'] == 'PRÉVU']
        
        if jobs_prevus:
            job_a_demarrer = st.selectbox(
                "Sélectionner job à démarrer",
                options=jobs_prevus,
                format_func=lambda j: f"Job #{j['id']} - {j['variete']} - {j['date']} {j['heure_debut']}",
                key='select_demarrer'
            )
            
            if st.button("▶️ Démarrer ce job", type="primary"):
                success, msg = demarrer_job(job_a_demarrer['id'])
                if success:
                    st.success(msg)
                    st.rerun()
                else:
                    st.error(msg)
        else:
            st.info("Aucun job PRÉVU")
    
    with col2:
        st.markdown("### ⏸️ Terminer Job")
        jobs_en_cours = [j for j in st.session_state.jobs_planifies if j['statut'] == 'EN_COURS']
        
        if jobs_en_cours:
            job_a_terminer = st.selectbox(
                "Sélectionner job à terminer",
                options=jobs_en_cours,
                format_func=lambda j: f"Job #{j['id']} - {j['variete']}",
                key='select_terminer'
            )
            
            st.markdown("---")
            st.markdown("#### 📊 Qualification du lavage")
            
            poids_brut = float(job_a_terminer['poids_estime_kg'])
            
            poids_lave = st.number_input(
                "Poids lavé net (kg) *",
                min_value=0.0,
                value=poids_brut * 0.75,
                step=100.0,
                key='poids_lave'
            )
            
            poids_grenailles = st.number_input(
                "Poids grenailles (kg) *",
                min_value=0.0,
                value=poids_brut * 0.05,
                step=10.0,
                key='poids_grenailles'
            )
            
            poids_dechets = st.number_input(
                "Poids déchets (kg) *",
                min_value=0.0,
                value=poids_brut * 0.05,
                step=10.0,
                key='poids_dechets'
            )
            
            poids_terre_calc = poids_brut - poids_lave - poids_grenailles - poids_dechets
            st.metric("Terre calculée", f"{poids_terre_calc:.0f} kg")
            
            if st.button("✅ Terminer et Qualifier", type="primary"):
                success, msg = terminer_job(
                    job_a_terminer['id'],
                    poids_lave,
                    poids_grenailles,
                    poids_dechets
                )
                if success:
                    st.success(msg)
                    st.balloons()
                    st.rerun()
                else:
                    st.error(msg)
        else:
            st.info("Aucun job EN_COURS")

# ============================================================
# TAB 3 : JOBS NON PLANIFIÉS
# ============================================================

with tab3:
    st.subheader("📋 Jobs en Attente de Planification")
    
    if st.session_state.jobs_non_planifies:
        st.info(f"💡 {len(st.session_state.jobs_non_planifies)} job(s) à planifier")
        
        for job in st.session_state.jobs_non_planifies:
            with st.expander(f"🆕 {job['variete']} - {job['lot_id']} ({job['quantite_pallox']} pallox)"):
                st.write(f"**Poids estimé** : {job['poids_estime_kg']/1000:.1f} T")
                
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    date_planif = st.date_input(
                        "Date",
                        value=datetime.now().date(),
                        key=f"date_{job['id']}"
                    )
                
                with col2:
                    heure_planif = st.time_input(
                        "Heure",
                        value=datetime.strptime("08:00", "%H:%M").time(),
                        key=f"heure_{job['id']}"
                    )
                
                with col3:
                    ligne_planif = st.selectbox(
                        "Ligne",
                        options=['LIGNE_1', 'LIGNE_2'],
                        key=f"ligne_{job['id']}"
                    )
                
                if st.button(f"➕ Ajouter au planning", key=f"add_{job['id']}", type="primary"):
                    success, msg = ajouter_job_calendrier(
                        job,
                        date_planif.strftime("%Y-%m-%d"),
                        heure_planif.strftime("%H:%M"),
                        ligne_planif
                    )
                    if success:
                        st.success(msg)
                        st.rerun()
                    else:
                        st.error(msg)
    else:
        st.success("✅ Tous les jobs sont planifiés !")

# ============================================================
# ÉTAT SYSTÈME
# ============================================================

st.markdown("---")
st.subheader("📊 État du Système")

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

# Debug
with st.expander("🔍 Données session (debug)"):
    st.json({
        'jobs_planifies': st.session_state.jobs_planifies,
        'jobs_non_planifies': st.session_state.jobs_non_planifies
    })

show_footer()
