"""
DEMO - External Dragging FullCalendar
Drag & Drop DIRECT : Jobs Streamlit → Calendrier ⚡
"""

import streamlit as st
import streamlit.components.v1 as components
from datetime import datetime, timedelta
from streamlit_calendar import fullcalendar_component

st.set_page_config(page_title="DEMO External Dragging", page_icon="🎯", layout="wide")

st.title("🎯 DEMO - External Dragging FullCalendar")
st.markdown("**Drag & Drop DIRECT** : Jobs → Calendrier ⚡")
st.markdown("---")

# ==========================================
# DONNÉES TEST
# ==========================================

# Jobs déjà planifiés (dans calendrier)
if 'events' not in st.session_state:
    st.session_state.events = [
        {
            'id': '1',
            'title': 'MONALISA 5P',
            'start': '2026-02-03T08:00:00',
            'end': '2026-02-03T09:00:00',
            'color': '#2e7d32',
            'extendedProps': {
                'lot_id': 1,
                'variete': 'MONALISA',
                'quantite_pallox': 5,
                'poids_brut_kg': 9500
            }
        }
    ]

# Jobs non planifiés (à drag & drop)
if 'jobs_non_planifies' not in st.session_state:
    st.session_state.jobs_non_planifies = [
        {
            'id': 101,
            'code_lot_interne': 'LOT_2025_AGATA_130',
            'variete': 'AGATA',
            'quantite_pallox': 6,
            'poids_brut_kg': 11400,
            'duree_minutes': 53
        },
        {
            'id': 102,
            'code_lot_interne': 'LOT_2025_ARTEMIS_045',
            'variete': 'ARTEMIS',
            'quantite_pallox': 4,
            'poids_brut_kg': 7600,
            'duree_minutes': 35
        },
        {
            'id': 103,
            'code_lot_interne': 'LOT_2025_NICOLA_078',
            'variete': 'NICOLA',
            'quantite_pallox': 5,
            'poids_brut_kg': 9500,
            'duree_minutes': 44
        }
    ]

# ==========================================
# LAYOUT 2 COLONNES
# ==========================================

col_jobs, col_calendar = st.columns([1, 2])

# ==========================================
# COLONNE 1 : JOBS NON PLANIFIÉS
# ==========================================

with col_jobs:
    st.subheader("📋 Jobs à planifier")
    st.markdown("*Drag & Drop vers le calendrier →*")
    
    if len(st.session_state.jobs_non_planifies) > 0:
        # Zone draggable
        draggable_html = """
        <div id="external-events">
        """
        
        for job in st.session_state.jobs_non_planifies:
            duree_h = job['duree_minutes'] // 60
            duree_m = job['duree_minutes'] % 60
            
            # Formater durée ISO
            duration_iso = f"{duree_h:02d}:{duree_m:02d}:00"
            
            draggable_html += f"""
            <div class="fc-event fc-h-event fc-daygrid-event fc-daygrid-block-event"
                 data-duration="{duration_iso}"
                 data-job-id="{job['id']}"
                 data-code-lot="{job['code_lot_interne']}"
                 data-variete="{job['variete']}"
                 data-quantite="{job['quantite_pallox']}"
                 data-poids="{job['poids_brut_kg']}"
                 style="cursor: move; margin: 8px 0; padding: 10px; background: #2e7d32; color: white; border-radius: 6px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
                
                <div style="font-weight: 600; margin-bottom: 4px;">
                    {job['code_lot_interne']}
                </div>
                
                <div style="font-size: 0.85em; opacity: 0.9;">
                    🌱 {job['variete']} | 📦 {job['quantite_pallox']}P | ⚖️ {job['poids_brut_kg']/1000:.1f}T
                </div>
                
                <div style="font-size: 0.8em; opacity: 0.8; margin-top: 4px;">
                    ⏱️ {duree_h}h{duree_m:02d}min
                </div>
            </div>
            """
        
        draggable_html += """
        </div>
        
        <script src='https://cdn.jsdelivr.net/npm/fullcalendar@6.1.10/index.global.min.js'></script>
        <script src='https://cdn.jsdelivr.net/npm/@fullcalendar/interaction@6.1.10/index.global.min.js'></script>
        
        <script>
            document.addEventListener('DOMContentLoaded', function() {
                var containerEl = document.getElementById('external-events');
                
                // Initialiser Draggable FullCalendar
                new FullCalendar.Draggable(containerEl, {
                    itemSelector: '.fc-event',
                    eventData: function(eventEl) {
                        return {
                            title: eventEl.getAttribute('data-code-lot'),
                            duration: eventEl.getAttribute('data-duration'),
                            backgroundColor: '#2e7d32',
                            borderColor: '#1b5e20',
                            extendedProps: {
                                job_id: parseInt(eventEl.getAttribute('data-job-id')),
                                code_lot_interne: eventEl.getAttribute('data-code-lot'),
                                variete: eventEl.getAttribute('data-variete'),
                                quantite_pallox: parseInt(eventEl.getAttribute('data-quantite')),
                                poids_brut_kg: parseFloat(eventEl.getAttribute('data-poids'))
                            }
                        };
                    }
                });
                
                console.log('Draggable initialized!');
            });
        </script>
        """
        
        components.html(draggable_html, height=400, scrolling=True)
    else:
        st.success("✅ Tous les jobs sont planifiés !")

# ==========================================
# COLONNE 2 : CALENDRIER
# ==========================================

with col_calendar:
    st.subheader("📅 Calendrier")
    
    # Calendrier avec droppable=True
    calendar_event = fullcalendar_component(
        events=st.session_state.events,
        editable=True,
        droppable=True,  # ← Active external dragging
        height=600,
        key="calendar_demo"
    )
    
    # Traiter événements
    if calendar_event:
        st.markdown("---")
        st.subheader("📨 Dernier événement")
        
        event_type = calendar_event.get('type')
        
        if event_type == 'external_drop':
            st.success(f"🎯 **JOB DROPPÉ SUR CALENDRIER !**")
            
            job_id = calendar_event.get('job_id')
            code_lot = calendar_event.get('code_lot_interne')
            start = calendar_event.get('start')
            end = calendar_event.get('end')
            
            st.write(f"**Job ID** : {job_id}")
            st.write(f"**Code Lot** : {code_lot}")
            st.write(f"**Variété** : {calendar_event.get('variete')}")
            st.write(f"**Quantité** : {calendar_event.get('quantite_pallox')} pallox")
            st.write(f"**Poids** : {calendar_event.get('poids_brut_kg')} kg")
            st.write(f"**Début** : {start}")
            st.write(f"**Fin** : {end}")
            
            # Bouton pour confirmer planification
            if st.button("✅ Confirmer la planification", type="primary"):
                # Retirer de la liste non planifiés
                st.session_state.jobs_non_planifies = [
                    j for j in st.session_state.jobs_non_planifies 
                    if j['id'] != job_id
                ]
                
                # Ajouter au calendrier
                new_event = {
                    'id': str(job_id),
                    'title': code_lot,
                    'start': start,
                    'end': end,
                    'color': '#2e7d32',
                    'extendedProps': {
                        'lot_id': job_id,
                        'variete': calendar_event.get('variete'),
                        'quantite_pallox': calendar_event.get('quantite_pallox'),
                        'poids_brut_kg': calendar_event.get('poids_brut_kg')
                    }
                }
                
                st.session_state.events.append(new_event)
                
                st.success(f"✅ Job {code_lot} planifié !")
                st.balloons()
                st.rerun()
        
        elif event_type == 'click':
            st.info(f"👆 Clic sur job #{calendar_event.get('job_id')}")
            st.json(calendar_event)
        
        elif event_type == 'drop':
            st.info(f"🔄 Job #{calendar_event.get('job_id')} déplacé")
            st.json(calendar_event)
        
        elif event_type == 'resize':
            st.info(f"↔️ Job #{calendar_event.get('job_id')} redimensionné")
            st.json(calendar_event)

# ==========================================
# DEBUG
# ==========================================

with st.expander("🔍 Debug - État session"):
    st.write("**Events (calendrier)** :")
    st.json(st.session_state.events)
    
    st.write("**Jobs non planifiés** :")
    st.json(st.session_state.jobs_non_planifies)
