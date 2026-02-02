"""
ÉTAPE 1 : POC Planning Lavage avec FullCalendar
================================================

PAGE DE TEST dans l'application Culture Pom
Déployée sur Heroku pour validation

⚠️ NE TOUCHE PAS à la DB - Données de test uniquement

Accès : Menu latéral → "🧪 Test Calendar POC"
"""

import streamlit as st
import streamlit.components.v1 as components
import json
from auth import is_authenticated
from components import show_footer

st.set_page_config(page_title="Test Calendar POC", page_icon="🧪", layout="wide")

# Authentification
if not is_authenticated():
    st.warning("⚠️ Veuillez vous connecter pour accéder à cette page")
    st.stop()

# ============================================================
# CSS COMPACT
# ============================================================
st.markdown("""
<style>
    .block-container {
        padding-top: 1rem !important;
        padding-bottom: 0.5rem !important;
    }
    h1, h2, h3 {
        margin-top: 0.3rem !important;
        margin-bottom: 0.3rem !important;
    }
</style>
""", unsafe_allow_html=True)

# ============================================================
# DONNÉES DE TEST (pas la vraie DB)
# ============================================================

def get_test_jobs():
    """4 jobs de test pour valider le POC"""
    return [
        {
            'id': 1,
            'variete': 'AGATA',
            'quantite_pallox': 5,
            'date': '2026-02-03',  # Lundi
            'heure_debut': '08:00',
            'heure_fin': '10:30',
            'ligne': 'LIGNE_1',
            'statut': 'PRÉVU'
        },
        {
            'id': 2,
            'variete': 'BINTJE',
            'quantite_pallox': 3,
            'date': '2026-02-03',  # Lundi
            'heure_debut': '10:30',
            'heure_fin': '12:00',
            'ligne': 'LIGNE_1',
            'statut': 'PRÉVU'
        },
        {
            'id': 3,
            'variete': 'CHARLOTTE',
            'quantite_pallox': 4,
            'date': '2026-02-04',  # Mardi
            'heure_debut': '08:00',
            'heure_fin': '10:00',
            'ligne': 'LIGNE_2',
            'statut': 'EN_COURS'
        },
        {
            'id': 4,
            'variete': 'ROSEVAL',
            'quantite_pallox': 6,
            'date': '2026-02-05',  # Mercredi
            'heure_debut': '14:00',
            'heure_fin': '17:00',
            'ligne': 'LIGNE_1',
            'statut': 'TERMINÉ'
        }
    ]

def get_test_lignes():
    """2 lignes de lavage de test"""
    return [
        {'code': 'LIGNE_1', 'libelle': 'Ligne principale', 'capacite': 13.0},
        {'code': 'LIGNE_2', 'libelle': 'Ligne secondaire', 'capacite': 6.0}
    ]

# ============================================================
# COMPOSANT FULLCALENDAR
# ============================================================

def render_calendar(jobs, lignes, week_start):
    """
    Affiche le calendrier FullCalendar avec drag & drop
    """
    
    # Préparer événements pour FullCalendar
    events = []
    for job in jobs:
        # Couleur selon statut
        if job['statut'] == 'EN_COURS':
            color = '#ff9800'  # Orange
        elif job['statut'] == 'TERMINÉ':
            color = '#757575'  # Gris
        else:
            color = '#4caf50'  # Vert
        
        events.append({
            'id': str(job['id']),
            'title': f"Job #{job['id']} - {job['variete']} ({job['quantite_pallox']}p)",
            'start': f"{job['date']}T{job['heure_debut']}:00",
            'end': f"{job['date']}T{job['heure_fin']}:00",
            'resourceId': job['ligne'],
            'backgroundColor': color,
            'borderColor': color,
            'extendedProps': {
                'statut': job['statut'],
                'variete': job['variete'],
                'quantite': job['quantite_pallox'],
                'job_id': job['id']
            }
        })
    
    # Préparer ressources (lignes de lavage)
    resources = [
        {
            'id': l['code'],
            'title': f"{l['libelle']} ({l['capacite']} T/h)"
        }
        for l in lignes
    ]
    
    # HTML + JavaScript avec FullCalendar
    calendar_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <title>Planning Lavage POC</title>
        
        <!-- FullCalendar CSS -->
        <link href='https://cdn.jsdelivr.net/npm/fullcalendar@6.1.10/index.global.min.css' rel='stylesheet' />
        
        <style>
            body {{
                margin: 0;
                padding: 10px;
                font-family: 'Segoe UI', Arial, sans-serif;
                background: #fafafa;
            }}
            
            #calendar {{
                max-width: 100%;
                height: 600px;
                background: white;
                border-radius: 8px;
                padding: 10px;
                box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            }}
            
            /* Style des événements */
            .fc-event {{
                cursor: move !important;
                border-radius: 4px;
                padding: 4px;
                font-size: 0.85rem;
            }}
            
            .fc-event.statut-termine {{
                cursor: not-allowed !important;
                opacity: 0.6;
            }}
            
            /* Log des actions */
            #log {{
                position: fixed;
                top: 80px;
                right: 20px;
                background: white;
                border: 2px solid #1976d2;
                padding: 15px;
                border-radius: 8px;
                max-width: 320px;
                font-size: 13px;
                box-shadow: 0 4px 12px rgba(0,0,0,0.15);
                z-index: 1000;
            }}
            
            #log h4 {{
                margin: 0 0 10px 0;
                color: #1976d2;
                font-size: 14px;
            }}
            
            #log .log-entry {{
                margin: 6px 0;
                padding: 6px;
                background: #f5f5f5;
                border-radius: 4px;
                border-left: 3px solid #1976d2;
                font-size: 12px;
            }}
            
            #log .log-entry.success {{
                border-left-color: #4caf50;
                background: #e8f5e9;
            }}
            
            #log .log-entry.warning {{
                border-left-color: #ff9800;
                background: #fff3e0;
            }}
        </style>
    </head>
    <body>
        <!-- Log des actions -->
        <div id="log">
            <h4>📋 Log Actions</h4>
            <div id="log-content">
                <div class="log-entry">✅ Calendrier initialisé</div>
            </div>
        </div>
        
        <!-- Calendrier -->
        <div id='calendar'></div>
        
        <!-- FullCalendar JS -->
        <script src='https://cdn.jsdelivr.net/npm/fullcalendar@6.1.10/index.global.min.js'></script>
        
        <script>
        // Données
        const eventsData = {json.dumps(events)};
        const resourcesData = {json.dumps(resources)};
        
        // Fonction log
        function addLog(message, type = 'info') {{
            const logContent = document.getElementById('log-content');
            const entry = document.createElement('div');
            entry.className = 'log-entry ' + type;
            const time = new Date().toLocaleTimeString('fr-FR');
            entry.textContent = time + ' - ' + message;
            logContent.insertBefore(entry, logContent.firstChild);
            
            // Garder max 8 entrées
            while (logContent.children.length > 8) {{
                logContent.removeChild(logContent.lastChild);
            }}
        }}
        
        // Initialisation FullCalendar
        document.addEventListener('DOMContentLoaded', function() {{
            const calendarEl = document.getElementById('calendar');
            
            const calendar = new FullCalendar.Calendar(calendarEl, {{
                // Configuration de base
                initialView: 'resourceTimelineWeek',
                initialDate: '{week_start}',
                locale: 'fr',
                
                // Ressources et événements
                resources: resourcesData,
                events: eventsData,
                
                // ⭐ DRAG & DROP ACTIVÉ
                editable: true,
                droppable: true,
                eventResizableFromStart: true,
                
                // Plage horaire
                slotMinTime: '05:00:00',
                slotMaxTime: '22:00:00',
                slotDuration: '00:15:00',
                slotLabelInterval: '01:00:00',
                
                // Hauteur
                contentHeight: 550,
                
                // En-tête
                headerToolbar: {{
                    left: 'title',
                    center: '',
                    right: 'today prev,next'
                }},
                
                // Textes français
                buttonText: {{
                    today: "Aujourd'hui"
                }},
                
                // ⭐ CALLBACK: Événement déplacé (drag & drop)
                eventDrop: function(info) {{
                    const event = info.event;
                    const resource = event.getResources()[0];
                    
                    const message = `Job #${{event.extendedProps.job_id}} déplacé → ${{resource.title}} - ${{event.start.toLocaleDateString('fr-FR')}} ${{event.start.toLocaleTimeString('fr-FR', {{hour: '2-digit', minute: '2-digit'}})}}`;
                    addLog(message, 'success');
                    
                    // Envoyer à Streamlit
                    sendToStreamlit({{
                        action: 'move',
                        id: event.extendedProps.job_id,
                        newStart: event.start.toISOString(),
                        newEnd: event.end.toISOString(),
                        newLigne: resource.id
                    }});
                }},
                
                // ⭐ CALLBACK: Événement redimensionné (durée changée)
                eventResize: function(info) {{
                    const event = info.event;
                    const oldDuration = info.oldEvent.end - info.oldEvent.start;
                    const newDuration = event.end - event.start;
                    const durationChange = newDuration - oldDuration;
                    const minutes = Math.round(durationChange / 60000);
                    
                    const message = `Job #${{event.extendedProps.job_id}} redimensionné (${{minutes > 0 ? '+' : ''}}${{minutes}} min)`;
                    addLog(message, 'success');
                    
                    sendToStreamlit({{
                        action: 'resize',
                        id: event.extendedProps.job_id,
                        newEnd: event.end.toISOString(),
                        durationChange: durationChange
                    }});
                }},
                
                // Validation avant drop
                eventAllow: function(dropInfo, draggedEvent) {{
                    // Bloquer si TERMINÉ
                    if (draggedEvent.extendedProps.statut === 'TERMINÉ') {{
                        addLog('⛔ Job TERMINÉ non déplaçable', 'warning');
                        return false;
                    }}
                    return true;
                }},
                
                // Style et tooltip
                eventDidMount: function(info) {{
                    // Ajouter classe si terminé
                    if (info.event.extendedProps.statut === 'TERMINÉ') {{
                        info.el.classList.add('statut-termine');
                    }}
                    
                    // Tooltip
                    const props = info.event.extendedProps;
                    info.el.title = 
                        `${{props.variete}}\\n` +
                        `${{props.quantite}} pallox\\n` +
                        `Statut: ${{props.statut}}`;
                }}
            }});
            
            // Communication avec Streamlit
            function sendToStreamlit(data) {{
                window.parent.postMessage({{
                    type: 'streamlit:setComponentValue',
                    value: data
                }}, '*');
            }}
            
            // Rendre le calendrier
            calendar.render();
            addLog('Drag & drop activé - Testez !', 'success');
        }});
        </script>
    </body>
    </html>
    """
    
    # Afficher le composant et récupérer les modifications
    result = components.html(calendar_html, height=650, scrolling=False)
    
    return result

# ============================================================
# INTERFACE STREAMLIT
# ============================================================

st.title("🧪 ÉTAPE 1 : POC Planning Lavage")
st.caption("Test FullCalendar avec données fictives (pas la vraie DB)")

st.markdown("---")

# Alert
st.warning("""
⚠️ **PAGE DE TEST** : Données fictives uniquement - Ne touche pas à la DB Planning Lavage
""")

# Instructions
with st.expander("📖 Ce que tu dois tester", expanded=True):
    st.markdown("""
    ### ✅ Checklist de validation ÉTAPE 1
    
    **Affichage** :
    - [ ] Calendrier vue semaine (Lun-Sam)
    - [ ] 2 lignes : LIGNE_1 et LIGNE_2
    - [ ] 4 jobs avec couleurs (vert/orange/gris)
    - [ ] Heures 05:00 - 22:00
    
    **Interactions visuelles** :
    - [ ] Glisser Job #1 (AGATA vert) du lundi au mardi → **Se déplace visuellement**
    - [ ] Glisser Job #3 (CHARLOTTE orange) de LIGNE_2 vers LIGNE_1 → **Change de ligne**
    - [ ] Redimensionner Job #2 (tirer bord droit) → **Durée change**
    - [ ] Job #4 (ROSEVAL gris) refuse de bouger → **Bloqué**
    
    **Log JavaScript** (en haut à droite du calendrier) :
    - [ ] Affiche "Job #X déplacé" quand tu glisses
    - [ ] Affiche "Job #X redimensionné" quand tu agrandis
    
    💡 **Note ÉTAPE 1** : C'est juste un POC visuel
    - Les modifications NE sont PAS sauvegardées en DB
    - Le log Python en dessous ne s'affichera pas encore
    - L'ÉTAPE 2 ajoutera la communication JS → Python → DB
    
    ### 🎯 Validation
    
    Si tout fonctionne visuellement, dis-moi :  
    **"✅ ÉTAPE 1 validée, drag & drop fonctionne"**
    """)

st.markdown("---")

# Infos
col1, col2, col3 = st.columns(3)
with col1:
    st.metric("📦 Jobs test", "4")
with col2:
    st.metric("🔧 Lignes", "2")
with col3:
    st.metric("📅 Semaine", "03-08 Fév 2026")

st.markdown("---")

# Calendrier
jobs = get_test_jobs()
lignes = get_test_lignes()
week_start = "2026-02-03"  # Lundi

st.subheader("📅 Calendrier FullCalendar")

result = render_calendar(jobs, lignes, week_start)

# Afficher résultat si modification (pour ÉTAPE 2)
# Pour l'ÉTAPE 1, on vérifie juste visuellement que le drag & drop fonctionne
if result is not None and isinstance(result, dict):
    st.markdown("---")
    st.subheader("🔔 Modification détectée")
    
    action = result.get('action', '')
    job_id = result.get('id', 0)
    
    if action == 'move':
        st.success(f"✅ Job #{job_id} déplacé")
        with st.expander("Détails JSON"):
            st.json(result)
        
    elif action == 'resize':
        duration_change_min = int(result.get('durationChange', 0) / 60000)
        st.success(f"✅ Job #{job_id} redimensionné ({duration_change_min:+d} min)")
        with st.expander("Détails JSON"):
            st.json(result)
else:
    # Pour ÉTAPE 1 : Communication JS → Python sera implémentée à l'ÉTAPE 2
    st.info("""
    💡 **Pour l'ÉTAPE 1** : Vérifie visuellement que le drag & drop fonctionne
    
    - Glisse les jobs dans le calendrier
    - Regarde le **log en haut à droite** du calendrier (il affiche tes actions)
    - La sauvegarde en DB sera implémentée à l'ÉTAPE 2
    """)

# Debug
with st.expander("🔍 Données de test (Debug)"):
    st.write("**Jobs** :")
    st.dataframe(jobs, use_container_width=True)
    st.write("**Lignes** :")
    st.dataframe(lignes, use_container_width=True)

st.markdown("---")
st.info("**ÉTAPE 2** : Connexion vraie DB Planning Lavage (si ÉTAPE 1 OK)")

show_footer()
