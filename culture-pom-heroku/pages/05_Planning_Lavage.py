import streamlit as st
import streamlit.components.v1 as stc
from components import show_footer
from auth import require_access

st.set_page_config(page_title="Planning Lavage - DEBUG V3", page_icon="🧼", layout="wide")

require_access('planning_lavage')

st.title("🧼 Planning Lavage - TEST DEBUG V3")
st.info("🔍 Test avec syntaxe JavaScript CORRIGÉE")

# ✅ CORRECTION : Utiliser triple quotes et éviter f-string pour éviter les conflits d'accolades
test_html = """
<!DOCTYPE html>
<html>
<head>
    <meta charset='utf-8'>
    <title>Test FullCalendar V3</title>
    
    <script src='https://cdn.jsdelivr.net/npm/fullcalendar@5.11.0/main.min.js'></script>
    <link href='https://cdn.jsdelivr.net/npm/fullcalendar@5.11.0/main.min.css' rel='stylesheet' />
    <script src='https://cdn.jsdelivr.net/npm/fullcalendar@5.11.0/locales/fr.js'></script>
    
    <style>
        body { 
            margin: 0; 
            padding: 20px; 
            background: #f5f5f5;
            font-family: Arial, sans-serif;
        }
        .status {
            background: #e3f2fd;
            padding: 15px;
            border-radius: 8px;
            margin-bottom: 20px;
            border-left: 5px solid #2196f3;
        }
        .status h3 {
            margin: 0 0 10px 0;
            color: #1976d2;
        }
        .status p {
            margin: 5px 0;
            color: #555;
            font-size: 14px;
        }
        #calendar { 
            height: 600px; 
            background: white;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }
        .success { color: #4caf50; font-weight: bold; }
        .error { color: #f44336; font-weight: bold; }
    </style>
</head>
<body>
    <div class="status">
        <h3>📊 Status de chargement</h3>
        <p id="step1">1. ✅ HTML chargé</p>
        <p id="step2">2. ⏳ Chargement FullCalendar...</p>
        <p id="step3">3. ⏳ Initialisation calendrier...</p>
        <p id="step4">4. ⏳ Rendu calendrier...</p>
    </div>
    
    <div id='calendar'></div>
    
    <script>
        console.log('=== DÉBUT TEST V3 ===');
        
        // Étape 2
        if (typeof FullCalendar !== 'undefined') {
            document.getElementById('step2').innerHTML = '2. <span class="success">✅ FullCalendar chargé (v' + FullCalendar.version + ')</span>';
            console.log('✅ FullCalendar version:', FullCalendar.version);
        } else {
            document.getElementById('step2').innerHTML = '2. <span class="error">❌ FullCalendar NON chargé</span>';
            console.error('❌ FullCalendar non disponible');
        }
        
        // Étape 3
        try {
            document.getElementById('step3').innerHTML = '3. <span class="success">✅ Initialisation...</span>';
            
            var calendarEl = document.getElementById('calendar');
            
            var calendar = new FullCalendar.Calendar(calendarEl, {
                initialView: 'timeGridWeek',
                locale: 'fr',
                firstDay: 1,
                slotMinTime: '06:00:00',
                slotMaxTime: '20:00:00',
                allDaySlot: false,
                nowIndicator: true,
                headerToolbar: {
                    left: 'prev,next today',
                    center: 'title',
                    right: 'timeGridWeek,timeGridDay'
                },
                buttonText: {
                    today: 'Aujourd\'hui',
                    week: 'Semaine',
                    day: 'Jour'
                },
                events: [
                    {
                        title: '🟢 Job Test Lundi',
                        start: '2026-02-03T10:00:00',
                        end: '2026-02-03T12:00:00',
                        backgroundColor: '#4caf50'
                    },
                    {
                        title: '🔵 Job Test Mardi',
                        start: '2026-02-04T14:00:00',
                        end: '2026-02-04T16:30:00',
                        backgroundColor: '#2196f3'
                    },
                    {
                        title: '🟡 Job Test Mercredi',
                        start: '2026-02-05T08:00:00',
                        end: '2026-02-05T11:00:00',
                        backgroundColor: '#ffc107'
                    }
                ]
            });
            
            document.getElementById('step3').innerHTML = '3. <span class="success">✅ Calendrier initialisé</span>';
            console.log('✅ Calendrier initialisé');
            
            // Étape 4
            document.getElementById('step4').innerHTML = '4. <span class="success">⏳ Rendu en cours...</span>';
            calendar.render();
            document.getElementById('step4').innerHTML = '4. <span class="success">✅ Calendrier rendu avec succès !</span>';
            console.log('✅ Calendrier rendu !');
            
        } catch(err) {
            document.getElementById('step3').innerHTML = '3. <span class="error">❌ Erreur: ' + err.message + '</span>';
            document.getElementById('step4').innerHTML = '4. <span class="error">❌ Rendu impossible</span>';
            console.error('❌ ERREUR:', err);
        }
        
        console.log('=== FIN TEST V3 ===');
    </script>
</body>
</html>
"""

stc.html(test_html, height=850)

st.markdown("---")
st.markdown("### ✅ Ce que tu dois voir :")
st.markdown("""
**Status box VERTE** :
1. ✅ HTML chargé
2. ✅ FullCalendar chargé (v5.11.0)
3. ✅ Calendrier initialisé
4. ✅ Calendrier rendu avec succès !

**Calendrier avec 3 events** :
- 🟢 Job Test Lundi (3 fév 10h-12h)
- 🔵 Job Test Mardi (4 fév 14h-16h30)
- 🟡 Job Test Mercredi (5 fév 8h-11h)
""")

st.markdown("---")
st.success("✅ Cette version utilise des guillemets simples et évite les conflits de syntaxe !")

show_footer()
