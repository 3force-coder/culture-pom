import streamlit as st
import streamlit.components.v1 as stc
from components import show_footer
from auth import is_authenticated

st.set_page_config(page_title="Planning Lavage - DEBUG V3", page_icon="🧼", layout="wide")

if not is_authenticated():
    st.warning("⚠️ Veuillez vous connecter")
    st.stop()

st.title("🧼 Planning Lavage - TEST DEBUG V3 CORRIGÉ")
st.info("🔍 Version avec apostrophes ÉCHAPPÉES !")

# HTML avec apostrophes échappées
test_html = """<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Test FullCalendar</title>
    <script src="https://cdn.jsdelivr.net/npm/fullcalendar@5.11.0/main.min.js"></script>
    <link href="https://cdn.jsdelivr.net/npm/fullcalendar@5.11.0/main.min.css" rel="stylesheet">
    <script src="https://cdn.jsdelivr.net/npm/fullcalendar@5.11.0/locales/fr.js"></script>
    <style>
        body { margin: 0; padding: 20px; background: white; font-family: Arial, sans-serif; }
        .box { background: lightblue; padding: 15px; margin-bottom: 20px; border-radius: 8px; }
        #calendar { height: 600px; background: white; }
    </style>
</head>
<body>
    <div class="box">
        <h3>✅ L'iframe charge - Tu vois ce texte !</h3>
        <p id="status">Chargement FullCalendar...</p>
    </div>
    
    <div id="calendar"></div>
    
    <script>
        console.log('Script démarre');
        
        if (typeof FullCalendar !== 'undefined') {
            document.getElementById('status').innerHTML = '✅ FullCalendar chargé ! Version: ' + FullCalendar.version;
            
            var calendarEl = document.getElementById('calendar');
            var calendar = new FullCalendar.Calendar(calendarEl, {
                initialView: 'timeGridWeek',
                locale: 'fr',
                firstDay: 1,
                headerToolbar: {
                    left: 'prev,next today',
                    center: 'title',
                    right: 'timeGridWeek,timeGridDay'
                },
                buttonText: {
                    today: 'Aujourd\\'hui',
                    week: 'Semaine',
                    day: 'Jour'
                },
                events: [
                    {
                        title: '🟢 Test Lundi',
                        start: '2026-02-03T10:00:00',
                        end: '2026-02-03T12:00:00',
                        backgroundColor: '#4caf50'
                    },
                    {
                        title: '🔵 Test Mardi',
                        start: '2026-02-04T14:00:00',
                        end: '2026-02-04T16:30:00',
                        backgroundColor: '#2196f3'
                    },
                    {
                        title: '🟡 Test Mercredi',
                        start: '2026-02-05T08:00:00',
                        end: '2026-02-05T11:00:00',
                        backgroundColor: '#ffc107'
                    }
                ]
            });
            
            calendar.render();
            console.log('Calendrier rendu avec succès !');
        } else {
            document.getElementById('status').innerHTML = '❌ FullCalendar NON chargé';
            console.error('FullCalendar non disponible');
        }
    </script>
</body>
</html>"""

stc.html(test_html, height=800)

st.markdown("---")
st.markdown("### 🎯 Tu dois voir :")
st.markdown("- ✅ Boîte bleue : 'FullCalendar chargé'")
st.markdown("- ✅ Calendrier avec 3 events colorés")
st.markdown("- ✅ Bouton 'Aujourd\\'hui' fonctionnel")

show_footer()
