import streamlit as st
from auth import show_login, is_authenticated

st.set_page_config(
    page_title="Culture Pom",
    page_icon="🥔",
    layout="wide",
    initial_sidebar_state="collapsed" if not is_authenticated() else "expanded"
)

# ============================================================
# AUTHENTIFICATION - MASQUER SIDEBAR SI NON CONNECTÉ
# ============================================================

if not is_authenticated():
    st.markdown("""
    <style>
        [data-testid="stSidebar"] { display: none !important; }
        [data-testid="stSidebarCollapsedControl"] { display: none !important; }
        .stApp > header { display: none !important; }
        .main .block-container { max-width: 500px; padding-top: 5rem; }
    </style>
    """, unsafe_allow_html=True)
    
    show_login()
    st.stop()

# ============================================================
# FONCTION COMPTEUR TÂCHES
# ============================================================

def get_taches_sidebar_count():
    """Récupère le nombre de tâches ouvertes pour la sidebar"""
    try:
        from database import get_connection
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT COUNT(*) as cnt FROM taches 
            WHERE statut IN ('À faire', 'En cours') 
            AND priorite = 'Urgente' 
            AND is_active = TRUE
        """)
        urgentes = cursor.fetchone()['cnt']
        
        cursor.execute("""
            SELECT COUNT(*) as cnt FROM taches 
            WHERE statut IN ('À faire', 'En cours') 
            AND is_active = TRUE
        """)
        ouvertes = cursor.fetchone()['cnt']
        
        cursor.close()
        conn.close()
        
        return urgentes, ouvertes
    except:
        return 0, 0

# ============================================================
# ⭐ ALERTE TÂCHES - BANDEAU FIXE EN HAUT VIA CSS
# ============================================================

try:
    urgentes, ouvertes = get_taches_sidebar_count()
    
    if urgentes > 0:
        # Bandeau ROUGE urgent
        st.markdown(f"""
        <style>
            [data-testid="stSidebar"] > div:first-child {{
                padding-top: 70px !important;
            }}
            .taches-alert {{
                position: fixed;
                top: 0;
                left: 0;
                width: var(--sidebar-width, 300px);
                z-index: 999999;
                background: #ffcdd2;
                border-bottom: 2px solid #f44336;
                padding: 12px 16px;
                text-align: center;
                font-weight: bold;
                color: #b71c1c;
            }}
            .taches-alert a {{
                color: #b71c1c;
                text-decoration: none;
            }}
            .taches-alert a:hover {{
                text-decoration: underline;
            }}
        </style>
        <div class="taches-alert">
            🔴 {urgentes} tâche(s) urgente(s)<br>
            <a href="/Tâches" target="_self">📋 Voir les tâches</a>
        </div>
        """, unsafe_allow_html=True)
        
    elif ouvertes > 0:
        # Bandeau ORANGE warning
        st.markdown(f"""
        <style>
            [data-testid="stSidebar"] > div:first-child {{
                padding-top: 70px !important;
            }}
            .taches-alert {{
                position: fixed;
                top: 0;
                left: 0;
                width: var(--sidebar-width, 300px);
                z-index: 999999;
                background: #fff3e0;
                border-bottom: 2px solid #ff9800;
                padding: 12px 16px;
                text-align: center;
                font-weight: bold;
                color: #e65100;
            }}
            .taches-alert a {{
                color: #e65100;
                text-decoration: none;
            }}
            .taches-alert a:hover {{
                text-decoration: underline;
            }}
        </style>
        <div class="taches-alert">
            📋 {ouvertes} tâche(s) en attente<br>
            <a href="/Tâches" target="_self">Voir les tâches</a>
        </div>
        """, unsafe_allow_html=True)
        
    else:
        # Bandeau VERT ok
        st.markdown("""
        <style>
            [data-testid="stSidebar"] > div:first-child {
                padding-top: 55px !important;
            }
            .taches-alert {
                position: fixed;
                top: 0;
                left: 0;
                width: var(--sidebar-width, 300px);
                z-index: 999999;
                background: #e8f5e9;
                border-bottom: 2px solid #4caf50;
                padding: 10px 16px;
                text-align: center;
                font-weight: bold;
                color: #2e7d32;
            }
        </style>
        <div class="taches-alert">
            ✅ Aucune tâche en attente
        </div>
        """, unsafe_allow_html=True)
except:
    pass

# ============================================================
# LOGO
# ============================================================

st.logo('https://i.imgur.com/kuLXrHZ.png')

# ============================================================
# DÉFINITION DES PAGES
# ============================================================

pages = {
    "": [
        st.Page("pages/00_Accueil.py", title="Accueil", icon="🏠", default=True),
    ],
    "📋 Référentiels": [
        st.Page("pages/01_Sources.py", title="Sources", icon="📋"),
    ],
    "📦 Stock": [
        st.Page("pages/02_Lots.py", title="Lots", icon="📦"),
        st.Page("pages/03_Détails stock.py", title="Détails Stock", icon="🗃️"),
        st.Page("pages/04_Stock_Global.py", title="Stock Global", icon="📊"),
        st.Page("pages/10_Stock_Consommables.py", title="Consommables", icon="🏷️"),
    ],
    "🏭 Production": [
        st.Page("pages/05_Planning_Lavage.py", title="Planning Lavage", icon="🧼"),
        st.Page("pages/08_Planning_Production.py", title="Planning Production", icon="🏭"),
    ],
    "📈 Commercial": [
        st.Page("pages/06_Previsions_Ventes.py", title="Prévisions Ventes", icon="📈"),
        st.Page("pages/07_Affectation_Stock.py", title="Affectation Stock", icon="🔗"),
    ],
    "💰 Finance": [
        st.Page("pages/09_Valorisation_Lots.py", title="Valorisation Lots", icon="💰"),
    ],
    "📋 Inventaire": [
        st.Page("pages/11_Inventaire.py", title="Inventaires", icon="📋"),
        st.Page("pages/12_Saisie_Inventaire.py", title="Saisie Inventaire", icon="📱")
    ],
    "🌾 Plans Récolte": [
        st.Page("pages/13_Plan_Recolte.py", title="Plan Récolte", icon="🌾"),
        st.Page("pages/14_Recaps_Plan.py", title="Récaps Plan", icon="📊"),
        st.Page("pages/15_Affectation_Producteurs.py", title="Affectation Producteurs", icon="👨‍🌾"),
        st.Page("pages/16_Suivi_Affectations.py", title="Suivi Affectations", icon="📋"),
    ],
    "✅ Tâches": [
        st.Page("pages/17_Taches.py", title="Tâches", icon="📋"),
    ],
    "🔧 Admin": [
        st.Page("pages/99_Admin_Users.py", title="Admin Users", icon="👥"),
    ],
}

# ============================================================
# NAVIGATION
# ============================================================

pg = st.navigation(pages)

# ============================================================
# SIDEBAR - INFOS UTILISATEUR (EN BAS)
# ============================================================

with st.sidebar:
    st.markdown("---")
    st.write(f"👤 {st.session_state.get('name', 'Utilisateur')}")
    st.caption(f"📧 {st.session_state.get('email', '')}")
    st.caption(f"🔑 {st.session_state.get('role_libelle', st.session_state.get('role', 'USER'))}")
    st.markdown("---")
    
    if st.button("🚪 Déconnexion", use_container_width=True):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()

# ============================================================
# EXÉCUTION DE LA PAGE
# ============================================================

pg.run()
