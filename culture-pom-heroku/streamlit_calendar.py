"""
Custom Streamlit Component - FullCalendar
Supporte : lecture (click), édition (drag & drop interne), external dragging (jobs Streamlit → calendrier)
"""

import streamlit.components.v1 as components
import json

def fullcalendar_component(events, editable=False, droppable=False, height=650, key=None):
    """
    Composant FullCalendar
    
    Args:
        events: Liste [{id, title, start, end, color, extendedProps}, ...]
        editable: True = drag & drop interne activé, False = lecture seule
        droppable: True = accepte drop depuis externe (jobs Streamlit), False = non
        height: Hauteur du calendrier en pixels
        key: Clé unique Streamlit
    
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
    
    # Ajouter CDN interaction si droppable
    interaction_cdn = ""
    if droppable:
        interaction_cdn = "<script src='https://cdn.jsdelivr.net/npm/@fullcalendar/interaction@6.1.10/index.global.min.js'></script>"
    
    component_html = f"""
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
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            }}
            
            .fc-header-toolbar {{
                margin-bottom: 1.2em !important;
                background: linear-gradient(135deg, #2e7d32 0%, #388e3c 100%);
                padding: 15px !important;
                border-radius: 8px 8px 0 0;
            }}
            
            .fc-toolbar-title {{
                color: white !important;
                font-weight: 600 !important;
                font-size: 1.4em !important;
                text-shadow: 0 1px 2px rgba(0,0,0,0.2);
            }}
            
            .fc-button {{
                background-color: rgba(255,255,255,0.2) !important;
                border: 1px solid rgba(255,255,255,0.3) !important;
                color: white !important;
                font-weight: 500 !important;
                border-radius: 6px !important;
                padding: 8px 16px !important;
                transition: all 0.2s ease;
            }}
            
            .fc-button:hover {{
                background-color: rgba(255,255,255,0.3) !important;
                border-color: rgba(255,255,255,0.5) !important;
                transform: translateY(-1px);
            }}
            
            .fc-button-active {{
                background-color: #1b5e20 !important;
                border-color: #1b5e20 !important;
            }}
            
            /* Jours */
            .fc-col-header {{
                background-color: #f5f5f5;
            }}
            
            .fc-col-header-cell-cushion {{
                color: #2e7d32 !important;
                font-weight: 600 !important;
                padding: 12px 4px !important;
            }}
            
            .fc-daygrid-day-number {{
                color: #2e7d32 !important;
                font-weight: 600;
                padding: 8px !important;
            }}
            
            /* Aujourd'hui */
            .fc-day-today {{
                background-color: #e8f5e9 !important;
            }}
            
            /* Ligne heure actuelle */
            .fc-timegrid-now-indicator-line {{
                border-color: #ff6f00 !important;
                border-width: 2px !important;
            }}
            
            .fc-timegrid-now-indicator-arrow {{
                border-color: #ff6f00 !important;
            }}
            
            /* Events */
            .fc-event {{
                border-radius: 6px !important;
                border: none !important;
                padding: 4px 6px !important;
                font-size: 0.85em !important;
                font-weight: 500 !important;
                cursor: pointer !important;
                transition: all 0.2s ease;
                box-shadow: 0 1px 3px rgba(0,0,0,0.12);
            }}
            
            .fc-event:hover {{
                transform: translateY(-2px);
                box-shadow: 0 4px 12px rgba(0,0,0,0.15);
            }}
            
            .fc-event-dragging {{
                opacity: 0.7 !important;
                cursor: move !important;
                box-shadow: 0 6px 16px rgba(0,0,0,0.2) !important;
            }}
            
            .fc-event-resizing {{
                opacity: 0.8 !important;
            }}
            
            /* Timegrid */
            .fc-timegrid-slot {{
                height: 3.5em !important;
            }}
            
            .fc-timegrid-slot-label {{
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
        <div id='calendar' class="{('editing-mode' if editable else '')}"></div>
        
        <script>
            // Communication Streamlit
            const Streamlit = window.parent.Streamlit;
            
            document.addEventListener('DOMContentLoaded', function() {{
                var calendarEl = document.getElementById('calendar');
                
                var calendar = new FullCalendar.Calendar(calendarEl, {{
                    // Config
                    initialView: 'timeGridWeek',
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
                    editable: {editable_str},
                    droppable: {droppable_str},  // Accepte drop depuis externe si true
                    
                    // Events
                    events: {events_json},
                    
                    // EVENT CLICK
                    eventClick: function(info) {{
                        console.log('Event clicked:', info.event.id);
                        
                        if (Streamlit) {{
                            Streamlit.setComponentValue({{
                                type: 'click',
                                job_id: parseInt(info.event.id),
                                title: info.event.title,
                                start: info.event.start.toISOString(),
                                end: info.event.end ? info.event.end.toISOString() : null,
                                color: info.event.backgroundColor,
                                extendedProps: info.event.extendedProps
                            }});
                        }}
                    }},
                    
                    // EVENT DROP
                    eventDrop: function(info) {{
                        console.log('Event dropped');
                        
                        if (Streamlit) {{
                            Streamlit.setComponentValue({{
                                type: 'drop',
                                job_id: parseInt(info.event.id),
                                old_start: info.oldEvent.start.toISOString(),
                                old_end: info.oldEvent.end ? info.oldEvent.end.toISOString() : null,
                                new_start: info.event.start.toISOString(),
                                new_end: info.event.end ? info.event.end.toISOString() : null,
                                delta_minutes: Math.round((info.event.start - info.oldEvent.start) / 60000)
                            }});
                        }}
                    }},
                    
                    // EVENT RESIZE
                    eventResize: function(info) {{
                        console.log('Event resized');
                        
                        if (Streamlit) {{
                            Streamlit.setComponentValue({{
                                type: 'resize',
                                job_id: parseInt(info.event.id),
                                old_end: info.oldEvent.end ? info.oldEvent.end.toISOString() : null,
                                new_start: info.event.start.toISOString(),
                                new_end: info.event.end ? info.event.end.toISOString() : null
                            }});
                        }}
                    }},
                    
                    // EVENT RECEIVE (job externe droppé depuis Streamlit)
                    eventReceive: function(info) {{
                        console.log('External event received:', info.event);
                        
                        if (Streamlit) {{
                            // Récupérer toutes les données de l'événement
                            var eventData = {{
                                type: 'external_drop',
                                start: info.event.start.toISOString(),
                                end: info.event.end ? info.event.end.toISOString() : null,
                                title: info.event.title
                            }};
                            
                            // Ajouter extendedProps si présents
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
    """
    
    component_value = components.html(
        component_html,
        height=height,
        scrolling=False
    )
    
    return component_value
