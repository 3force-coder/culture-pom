import streamlit as st
import streamlit.components.v1 as stc
import pandas as pd
from datetime import datetime, timedelta, time
import time as time_module
from database import get_connection
from components import show_footer
from auth import require_access
from auth.roles import is_admin
import io
import math
import json

st.set_page_config(page_title="Planning Lavage - Culture Pom", page_icon="🧼", layout="wide")

require_access('planning_lavage')

# ============================================================
# TEST SIMPLE - AFFICHER CALENDRIER MINIMAL
# ============================================================

st.title("🧼 Planning Lavage - TEST DEBUG")

st.info("🔍 Test d'affichage du calendrier FullCalendar")

# HTML minimal
test_html = """
<!DOCTYPE html>
<html>
<head>
    <meta charset='utf-8'>
    <link href='https://cdn.jsdelivr.net/npm/fullcalendar@6.1.15/index.global.min.css' rel='stylesheet'>
    <script src='https://cdn.jsdelivr.net/npm/fullcalendar@6.1.15/index.global.min.js'></script>
    <style>
        body { margin: 0; padding: 10px; background: #f5f5f5; }
        #calendar { height: 600px; background: white; }
        h3 { color: #2c3e50; }
    </style>
</head>
<body>
    <h3>✅ Si tu vois ce texte, l'iframe charge !</h3>
    <div id='calendar'></div>
    <script>
        console.log('✅ JavaScript s\'exécute !');
        
        var calendar = new FullCalendar.Calendar(document.getElementById('calendar'), {
            initialView: 'timeGridWeek',
            locale: 'fr',
            headerToolbar: {
                left: 'prev,next',
                center: 'title',
                right: 'today'
            },
            events: [
                {
                    title: '🟢 Test Event',
                    start: '2026-02-03T10:00:00',
                    end: '2026-02-03T12:00:00',
                    backgroundColor: '#4caf50'
                }
            ]
        });
        
        calendar.render();
        console.log('✅ Calendrier rendu !');
    </script>
</body>
</html>
"""

st.markdown("### Test 1 : Iframe basique")
stc.html(test_html, height=700)

st.markdown("---")
st.markdown("### Ce que tu dois voir :")
st.markdown("""
1. ✅ Un titre "Si tu vois ce texte, l'iframe charge !"
2. ✅ Un calendrier FullCalendar avec un event vert "Test Event" lundi 3 février 10h-12h
3. ✅ Navigation prev/next qui fonctionne

**Si tu ne vois rien** = Problème avec stc.html() ou les CDN FullCalendar
""")

show_footer()
