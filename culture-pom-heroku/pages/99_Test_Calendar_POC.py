"""
ÉTAPE 1.5 : POC Planning Lavage - Design Culture Pom
====================================================

Version améliorée avec :
- Design cohérent avec l'application
- Ligne heure actuelle (now indicator)
- Vue centrée sur aujourd'hui
- Couleurs et style Culture Pom
"""

import streamlit as st
import streamlit.components.v1 as components
import json
from datetime import datetime
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
# DONNÉES DE TEST
# ============================================================

def get_test_jobs():
    """4 jobs de test"""
    return [
        {
            'id': 1,
            'variete': 'AGATA',
            'quantite_pallox': 5,
            'date': '2026-02-03',
            'heure_debut': '06:00',
            'heure_fin': '08:30',
            'ligne': 'LIGNE_1',
            'statut': 'PRÉVU'
        },
        {
            'id': 2,
            'variete': 'BINTJE',
            'quantite_pallox': 3,
            'date': '2026-02-05',
            'heure_debut': '09:00',
            'heure_fin': '10:30',
            'ligne': 'LIGNE_1',
            'statut': 'PRÉVU'
        },
        {
            'id': 3,
            'variete': 'CHARLOTTE',
            'quantite_pallox': 4,
            'date': '2026-02-03',
            'heure_debut': '08:30',
            'heure_fin': '09:45',
            'ligne': 'LIGNE_2',
            'statut': 'EN_COURS'
        },
        {
            'id': 4,
            'variete': 'ROSEVAL',
            'quantite_pallox': 6,
            'date': '2026-02-02',
            'heure_debut': '14:00',
            'heure_fin': '17:00',
            'ligne': 'LIGNE_1',
            'statut': 'TERMINÉ'
        }
    ]

# ============================================================
# COMPOSANT FULLCALENDAR
# ============================================================

def render_calendar(jobs):
    """Calendrier FullCalendar avec design Culture Pom"""
    
    # Préparer événements
    events = []
    for job in jobs:
        # Couleurs selon statut (palette Culture Pom)
        if job['statut'] == 'EN_COURS':
            color = '#FF6B35'  # Orange Culture Pom
            text_color = '#FFFFFF'
        elif job['statut'] == 'TERMINÉ':
            color = '#95A5A6'  # Gris
            text_color = '#FFFFFF'
        else:
            color = '#2ECC71'  # Vert Culture Pom
            text_color = '#FFFFFF'
        
        events.append({
            'id': str(job['id']),
            'title': f"[{job['ligne']}] {job['variete']} ({job['quantite_pallox']}p)",
            'start': f"{job['date']}T{job['heure_debut']}:00",
            'end': f"{job['date']}T{job['heure_fin']}:00",
            'backgroundColor': color,
            'borderColor': color,
            'textColor': text_color,
            'extendedProps': {
                'statut': job['statut'],
                'variete': job['variete'],
                'quantite': job['quantite_pallox'],
                'job_id': job['id'],
                'ligne': job['ligne']
            }
        })
    
    # Date actuelle pour initialisation
    today = datetime.now().strftime('%Y-%m-%d')
    
    calendar_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <title>Planning Lavage</title>
        <link href='https://cdn.jsdelivr.net/npm/fullcalendar@6.1.10/index.global.min.css' rel='stylesheet' />
        
        <style>
            * {{
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }}
            
            body {{
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                background: #FAFAFA;
                padding: 0;
            }}
            
            #calendar {{
                background: white;
                border-radius: 12px;
                padding: 20px;
                box-shadow: 0 1px 3px rgba(0,0,0,0.08);
                margin: 10px;
            }}
            
            /* ===== STYLE CULTURE POM ===== */
            
            /* Header */
            .fc .fc-toolbar {{
                background: linear-gradient(135deg, #2E7D32 0%, #388E3C 100%);
                padding: 15px 20px;
                border-radius: 8px;
                margin-bottom: 15px;
            }}
            
            .fc .fc-toolbar-title {{
                color: white !important;
                font-size: 1.4rem !important;
                font-weight: 600 !important;
            }}
            
            .fc .fc-button {{
                background: rgba(255,255,255,0.2) !important;
                border: 1px solid rgba(255,255,255,0.3) !important;
                color: white !important;
                border-radius: 6px !important;
                padding: 8px 16px !important;
                font-weight: 500 !important;
                transition: all 0.2s !important;
            }}
            
            .fc .fc-button:hover {{
                background: rgba(255,255,255,0.3) !important;
                border-color: rgba(255,255,255,0.5) !important;
            }}
            
            .fc .fc-button-active {{
                background: rgba(255,255,255,0.4) !important;
                border-color: rgba(255,255,255,0.6) !important;
            }}
            
            /* Jours de la semaine */
            .fc .fc-col-header-cell {{
                background: #F5F5F5;
                padding: 12px 8px;
                font-weight: 600;
                color: #2E7D32;
                border: none !important;
            }}
            
            .fc .fc-col-header-cell-cushion {{
                color: #2E7D32;
                font-size: 0.9rem;
            }}
            
            /* Grille horaire */
            .fc .fc-timegrid-slot {{
                height: 3em !important;
                border-color: #E8E8E8 !important;
            }}
            
            .fc .fc-timegrid-slot-label {{
                color: #666;
                font-size: 0.85rem;
                font-weight: 500;
            }}
            
            /* Aujourd'hui */
            .fc .fc-day-today {{
                background: rgba(46, 125, 50, 0.03) !important;
            }}
            
            /* ⭐ LIGNE HEURE ACTUELLE (NOW INDICATOR) */
            .fc .fc-timegrid-now-indicator-line {{
                border-color: #E74C3C !important;
                border-width: 2px !important;
            }}
            
            .fc .fc-timegrid-now-indicator-arrow {{
                border-color: #E74C3C !important;
                border-width: 6px !important;
            }}
            
            /* Événements */
            .fc-event {{
                cursor: move !important;
                border-radius: 6px !important;
                padding: 6px 8px !important;
                font-size: 0.85rem !important;
                font-weight: 500 !important;
                border: none !important;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1) !important;
                transition: all 0.2s !important;
            }}
            
            .fc-event:hover {{
                transform: translateY(-1px);
                box-shadow: 0 4px 8px rgba(0,0,0,0.15) !important;
            }}
            
            .fc-event.statut-termine {{
                cursor: not-allowed !important;
                opacity: 0.7 !important;
            }}
            
            .fc-event-title {{
                font-weight: 600 !important;
            }}
            
            /* Scrollbar personnalisé */
            .fc-scroller::-webkit-scrollbar {{
                width: 8px;
                height: 8px;
            }}
            
            .fc-scroller::-webkit-scrollbar-track {{
                background: #F5F5F5;
                border-radius: 4px;
            }}
            
            .fc-scroller::-webkit-scrollbar-thumb {{
                background: #2E7D32;
                border-radius: 4px;
            }}
            
            .fc-scroller::-webkit-scrollbar-thumb:hover {{
                background: #1B5E20;
            }}
            
            /* Log Actions */
            #log {{
                position: fixed;
                top: 80px;
                right: 20px;
                background: white;
                border: 2px solid #2E7D32;
                border-radius: 10px;
                padding: 15px;
                max-width: 320px;
                box-shadow: 0 4px 12px rgba(0,0,0,0.1);
                z-index: 1000;
            }}
            
            #log h4 {{
                margin: 0 0 12px 0;
                color: #2E7D32;
                font-size: 15px;
                font-weight: 600;
            }}
            
            #log .log-entry {{
                margin: 8px 0;
                padding: 8px 10px;
                background: #F5F5F5;
                border-radius: 6px;
                border-left: 3px solid #2E7D32;
                font-size: 12px;
                color: #333;
            }}
            
            #log .log-entry.success {{
                border-left-color: #2ECC71;
                background: #E8F5E9;
            }}
            
            #log .log-entry.warning {{
                border-left-color: #FF6B35;
                background: #FFF3E0;
            }}
        </style>
    </head>
    <body>
        <!-- Log Actions -->
        <div id="log">
            <h4>📋 Log Actions</h4>
            <div id="log-content">
                <div class="log-entry">✅ Calendrier initialisé</div>
            </div>
        </div>
        
        <!-- Calendrier -->
        <div id='calendar'></div>
        
        <script src='https://cdn.jsdelivr.net/npm/fullcalendar@6.1.10/index.global.min.js'></script>
        
        <script>
        const eventsData = {json.dumps(events)};
        
        function addLog(message, type = 'info') {{
            const logContent = document.getElementById('log-content');
            const entry = document.createElement('div');
            entry.className = 'log-entry ' + type;
            const time = new Date().toLocaleTimeString('fr-FR');
            entry.textContent = time + ' - ' + message;
            logContent.insertBefore(entry, logContent.firstChild);
            
            while (logContent.children.length > 8) {{
                logContent.removeChild(logContent.lastChild);
            }}
        }}
        
        document.addEventListener('DOMContentLoaded', function() {{
            const calendarEl = document.getElementById('calendar');
            
            const calendar = new FullCalendar.Calendar(calendarEl, {{
                initialView: 'timeGridWeek',
                initialDate: '{today}',  // ⭐ Date actuelle
                locale: 'fr',
                
                events: eventsData,
                
                editable: true,
                droppable: true,
                eventResizableFromStart: true,
                
                slotMinTime: '05:00:00',
                slotMaxTime: '22:00:00',
                slotDuration: '00:15:00',
                slotLabelInterval: '01:00:00',
                
                // ⭐ SCROLL AUTO vers heure actuelle
                scrollTime: new Date().toTimeString().slice(0, 8),
                
                height: 700,
                allDaySlot: false,
                
                // ⭐ LIGNE HEURE ACTUELLE
                nowIndicator: true,
                
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
                    const message = `Job #${{event.extendedProps.job_id}} déplacé → ${{event.start.toLocaleDateString('fr-FR')}} ${{event.start.toLocaleTimeString('fr-FR', {{hour: '2-digit', minute: '2-digit'}})}}`;
                    addLog(message, 'success');
                }},
                
                eventResize: function(info) {{
                    const event = info.event;
                    const oldDuration = info.oldEvent.end - info.oldEvent.start;
                    const newDuration = event.end - event.start;
                    const durationChange = newDuration - oldDuration;
                    const minutes = Math.round(durationChange / 60000);
                    
                    const message = `Job #${{event.extendedProps.job_id}} redimensionné (${{minutes > 0 ? '+' : ''}}${{minutes}} min)`;
                    addLog(message, 'success');
                }},
                
                eventAllow: function(dropInfo, draggedEvent) {{
                    if (draggedEvent.extendedProps.statut === 'TERMINÉ') {{
                        addLog('⛔ Job TERMINÉ non déplaçable', 'warning');
                        return false;
                    }}
                    return true;
                }},
                
                eventDidMount: function(info) {{
                    if (info.event.extendedProps.statut === 'TERMINÉ') {{
                        info.el.classList.add('statut-termine');
                    }}
                    
                    const props = info.event.extendedProps;
                    info.el.title = 
                        `${{props.ligne}}\\n` +
                        `${{props.variete}}\\n` +
                        `${{props.quantite}} pallox\\n` +
                        `Statut: ${{props.statut}}`;
                }}
            }});
            
            calendar.render();
            addLog('Drag & drop activé !', 'success');
        }});
        </script>
    </body>
    </html>
    """
    
    result = components.html(calendar_html, height=750, scrolling=False)
    return result

# ============================================================
# INTERFACE
# ============================================================

st.title("🧪 POC Planning - Design Culture Pom")
st.caption("Version améliorée avec design cohérent")

st.markdown("---")

# Comparaison design
with st.expander("🎨 Améliorations design appliquées", expanded=True):
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("### ❌ AVANT")
        st.markdown("""
        - Header bleu basique
        - Couleurs FullCalendar par défaut
        - Vue fixe semaine 03-08 Fév
        - Pas de ligne heure actuelle
        - Style générique
        """)
    
    with col2:
        st.markdown("### ✅ APRÈS")
        st.markdown("""
        - **Header vert Culture Pom** (dégradé)
        - **Couleurs cohérentes** (vert/orange/gris)
        - **Vue sur aujourd'hui** (02/02/2026 19h35)
        - **Ligne rouge heure actuelle** ⭐
        - **Scroll auto** vers heure actuelle
        - **Style Culture Pom** (arrondi, ombres)
        """)

st.markdown("---")

# Infos
col1, col2, col3 = st.columns(3)
with col1:
    st.metric("📦 Jobs test", "4")
with col2:
    st.metric("📅 Vue", "Aujourd'hui")
with col3:
    st.metric("🎨 Design", "Culture Pom")

st.markdown("---")

# Calendrier
st.subheader("📅 Calendrier Planning Lavage")

jobs = get_test_jobs()
result = render_calendar(jobs)

# Message
if result is not None and isinstance(result, dict):
    st.markdown("---")
    st.success("🔔 Modification détectée (sera implémenté ÉTAPE 2)")
else:
    st.info("""
    💡 **Design amélioré** :
    
    - **Ligne rouge** = Heure actuelle (19h35)
    - **Vue centrée** sur aujourd'hui (02/02)
    - **Couleurs** cohérentes avec Culture Pom
    - **Header vert** au lieu de bleu
    - **Scroll auto** vers l'heure actuelle
    
    **Glisse les jobs pour tester !** Le design reste cohérent.
    """)

st.markdown("---")

# Validation
st.success("""
✅ **ÉTAPE 1 validée** - Le calendrier fonctionne !

🎨 **Design amélioré** - Cohérence Culture Pom

➡️ **Prochaine étape** : ÉTAPE 2 - Connexion vraie DB Planning Lavage
""")

show_footer()
