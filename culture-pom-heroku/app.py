import streamlit as st
from auth import show_login, is_authenticated

st.set_page_config(
    page_title="Culture Pom",
    page_icon="🥔",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Logo TOUT EN HAUT de la sidebar
st.logo('https://i.imgur.com/kuLXrHZ.png')

# ============================================================
# AUTHENTIFICATION
# ============================================================

if not is_authenticated():
    show_login()
    st.stop()

# ============================================================
# SIDEBAR - INFOS UTILISATEUR
# ============================================================

with st.sidebar:
    st.markdown("---")
    st.write(f"👤 {st.session_state.get('name', 'Utilisateur')}")
    st.caption(f"📧 {st.session_state.get('email', '')}")
    st.caption(f"🔑 {st.session_state.get('role', 'USER')}")
    st.markdown("---")
    
    # Bouton déconnexion
    if st.button("🚪 Déconnexion", use_container_width=True):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()

# ============================================================
# DÉFINITION DES PAGES - NOMS EXACTS DES FICHIERS
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
    ],
}

# ============================================================
# NAVIGATION
# ============================================================

pg = st.navigation(pages)
pg.run()
