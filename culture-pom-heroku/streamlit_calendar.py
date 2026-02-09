"""
Custom Streamlit Component - FullCalendar
Supporte : lecture (click), édition (drag & drop interne), external dragging (jobs Streamlit → calendrier)
"""

import streamlit.components.v1 as components
import json

def fullcalendar_component(events, editable=False, droppable=False, height=650, key=None, initial_date=None):
    """
    Composant FullCalendar
    
    Args:
        events: Liste [{id, title, start, end, color, extendedProps}, ...]
        editable: True = drag & drop interne activé, False = lecture seule
        droppable: True = accepte drop depuis externe (jobs Streamlit), False = non
        height: Hauteur du calendrier en pixels
        key: Clé unique Streamlit
        initial_date: Date ISO (YYYY-MM-DD) pour positionner la semaine initiale
    
    Returns:
        Dict événement : 
        - {'type': 'click', 'job_id': int, ...}
        - {'type': 'drop', 'job_id': int, ...} (drag interne)
        - {'type': 'resize', 'job_id': int, ...}
        - {'type': 'external_drop', 'job_data': {...}, 'start': str, 'end': str} (drag externe)
    
    Note: 
        Pour external dragging, Streamlit doit afficher les jobs avec attribut data-fc-event
        et les rendre draggables avec Draggable API FullCalendar
    """
    
    events_json = json.dumps(events)
    editable_str = "true" if editable else "false"
    droppable_str = "true" if droppable else "false"
    initial_date_js = f",\n                    initialDate: '{initial_date}'" if initial_date else ""
    
    # Ajouter CDN interaction si droppable
    interaction_cdn = ""
    if droppable:
        interaction_cdn = "<script src='https://cdn.jsdelivr.net/npm/@fullcalendar/interaction@6.1.10/index.global.min.js'></script>"
    
    editing_mode_class = "editing-mode" if editable else ""
    component_html = """
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <link href='https://cdn.jsdelivr.net/npm/fullcalendar@6.1.10/index.global.min.css' rel='stylesheet' />
        <script src='https://cdn.jsdelivr.net/npm/fullcalendar@6.1.10/index.global.min.js'></script>
        {interaction_cdn}
        <script src='https://cdn.jsdelivr.net/npm/fullcalendar@6.1.10/locales/fr.global.min.js'></script>
        
        <style>
            body {{
                margin: 0;
                padding: 0;
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                overflow: hidden;
            }}
            #calendar {{
                height: 100vh;
                padding: 15px;
            }}
            
            /* Theme Culture Pom */
            .fc {{
                background-color: #ffffff;
                border-radius: 8px;
@@ -170,62 +173,62 @@ def fullcalendar_component(events, editable=False, droppable=False, height=650,
                color: #666;
                font-size: 0.85em;
            }}
            
            .fc-timegrid-axis {{
                border-right: 1px solid #e0e0e0 !important;
            }}
            
            /* Mode édition */
            .editing-mode .fc-event {{
                cursor: move !important;
            }}
            
            .editing-mode .fc-event::after {{
                content: "⋮⋮";
                position: absolute;
                right: 4px;
                top: 50%;
                transform: translateY(-50%);
                font-size: 0.7em;
                opacity: 0.5;
            }}
        </style>
    </head>
    <body>
        <div id='calendar' class="{editing_mode_class}"></div>
        
        <script>
            // Communication Streamlit
            const Streamlit = window.parent.Streamlit;
            
            document.addEventListener('DOMContentLoaded', function() {{
                var calendarEl = document.getElementById('calendar');
                
                var calendar = new FullCalendar.Calendar(calendarEl, {{
                    // Config
                    initialView: 'timeGridWeek'{initial_date_js},
                    locale: 'fr',
                    
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
                    
                    // Heures
                    slotMinTime: '06:00:00',
                    slotMaxTime: '20:00:00',
                    allDaySlot: false,
                    
                    height: 'auto',
                    nowIndicator: true,
                    scrollTime: '08:00:00',
                    slotDuration: '00:30:00',
                    
                    // DRAG & DROP
@@ -301,34 +304,42 @@ def fullcalendar_component(events, editable=False, droppable=False, height=650,
                            if (info.event.extendedProps) {{
                                Object.assign(eventData, info.event.extendedProps);
                            }}
                            
                            Streamlit.setComponentValue(eventData);
                        }}
                    }}
                }});
                
                calendar.render();
                
                // Auto-scroll heure actuelle
                setTimeout(function() {{
                    var now = new Date();
                    calendar.scrollToTime(now.getHours() + ':' + now.getMinutes() + ':00');
                }}, 300);
                
                // Set frame height
                if (Streamlit) {{
                    Streamlit.setFrameHeight({height});
                }}
            }});
        </script>
    </body>
    </html>
    """.format(
        interaction_cdn=interaction_cdn,
        events_json=events_json,
        editable_str=editable_str,
        droppable_str=droppable_str,
        height=height,
        initial_date_js=initial_date_js,
        editing_mode_class=editing_mode_class,
    )
    
      component_value = components.html(
        component_html,
        height=height,
        scrolling=False,
        key=key
    )
    
    return component_value

