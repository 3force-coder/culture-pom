import streamlit as st
import streamlit.components.v1 as components
from auth import show_login, is_authenticated

st.set_page_config(
    page_title="POMI",
    page_icon="🥔",
    layout="wide",
    initial_sidebar_state="collapsed" if not is_authenticated() else "expanded"
)

# ============================================================
# AUTHENTIFICATION
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
# LOGO
# ============================================================

st.logo('https://i.imgur.com/kuLXrHZ.png')

# ============================================================
# ⭐ CSS + JS POUR REPLIER LES MENUS PAR DÉFAUT
# ============================================================

st.markdown("""
<style>
    /* Style compact pour la sidebar */
    [data-testid="stSidebarNav"] {
        padding-top: 0.5rem;
    }
    
    /* Réduire l'espacement des groupes */
    [data-testid="stSidebarNav"] > ul {
        padding: 0;
    }
</style>
""", unsafe_allow_html=True)

# ⭐ Script pour replier tous les groupes au chargement
# Utilise session_state pour ne l'exécuter qu'une fois par session
if 'nav_collapsed' not in st.session_state:
    components.html("""
    <script>
        // Fonction pour replier les menus
        function collapseNavGroups() {
            const details = parent.document.querySelectorAll('[data-testid="stSidebarNav"] details');
            if (details.length > 0) {
                details.forEach(function(detail) {
                    detail.removeAttribute('open');
                });
            } else {
                // Réessayer si la sidebar n'est pas encore chargée
                setTimeout(collapseNavGroups, 100);
            }
        }
        
        // Lancer après un court délai
        setTimeout(collapseNavGroups, 200);
    </script>
    """, height=0)
    st.session_state['nav_collapsed'] = True

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
    "📊 Statistiques": [
    st.Page("pages/35_Frulog.py",           title="Import & Mapping",   icon="📥"),
    st.Page("pages/35_Frulog_Condi.py",     title="Stats Condi",        icon="📈"),
    st.Page("pages/35_Frulog_Negoce.py",    title="Stats Négoce",       icon="🏪"),
    st.Page("pages/35_Frulog_Achats.py",    title="Stats Achats",       icon="🛒"),
    st.Page("pages/35_Frulog_ADV.py",       title="Stats ADV",          icon="🧾"),
    st.Page("pages/40_Supply_Stats.py",     title="Stats Supply",       icon="🚛"),
    st.Page("pages/41_RH_Heures.py",        title="Stats RH Heures",    icon="👷"),
    st.Page("pages/42_Production_Stats.py", title="Stats Production",   icon="🏭"),
    st.Page("pages/43_Maintenance_Stats.py", title="Stats Maintenance", icon="🔧")
],
    "📦 Stock": [
        st.Page("pages/02_Lots.py", title="Lots", icon="📦"),
        st.Page("pages/03_Détails stock.py", title="Détails Stock", icon="🗃️"),
        st.Page("pages/04_Stock_Global.py", title="Stock Global", icon="📊"),
        st.Page("pages/04b_Produits_Finis.py", title="Produits Finis", icon="📦"),
        st.Page("pages/10_Stock_Consommables.py", title="Consommables", icon="🏷️"),
    ],
    "🏭 Production": [
        st.Page("pages/05_Planning_Lavage.py", title="Planning Lavage", icon="🧼"),
        st.Page("pages/05b_Planning_Lavage_Bis.py", title="Lavage Bis", icon="🧼"),
        st.Page("pages/08_Planning_Production.py", title="Planning Production", icon="🏭"),
    ],
    "📈 Commercial": [
        st.Page("pages/06_Previsions_Ventes.py", title="Prévisions Ventes", icon="📈"),
        st.Page("pages/07_Affectation_Stock.py", title="Affectation Stock", icon="🔗"),
    ],
        "📊 Prévisions": [
        st.Page("pages/31_Prev_Dashboard.py", title="Dashboard Prév.", icon="📊"),
        st.Page("pages/32_Prev_Affectations.py", title="Affectations", icon="📋"),
        st.Page("pages/33_Prev_Simulation.py", title="Simulation", icon="💰"),
        st.Page("pages/34_Prev_Besoins.py", title="Besoins", icon="🎯"),
    ],
    "🛒 CRM": [
        st.Page("pages/20_CRM_Dashboard.py", title="Dashboard CRM", icon="📊"),
        st.Page("pages/21_CRM_Magasins.py", title="Clients", icon="🏪"),
        st.Page("pages/22_CRM_Contacts.py", title="Contacts", icon="👥"),
        st.Page("pages/23_CRM_Visites.py", title="Visites", icon="📅"),
        st.Page("pages/24_CRM_Animations.py", title="Animations", icon="🎉"),
        st.Page("pages/25_CRM_Statistics.py", title="Statistiques", icon="📈"),
        st.Page("pages/26_CRM_Releve_prix.py", title="Relevé de Prix", icon="💰"),
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
         st.Page("pages/99_Test_Calendar_POC.py", title="Admin calendar", icon="👥"),
    ],
}

# ============================================================
# NAVIGATION
# ============================================================

pg = st.navigation(pages)

# ============================================================
# SIDEBAR - INFOS UTILISATEUR
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
