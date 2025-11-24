import streamlit as st
from components import show_footer
from database import get_connection

st.title("🏠 Accueil")
st.markdown("*Gestion de la Production - Culture Pom*")
st.markdown("---")

# Vérifier authentification
if not st.session_state.get('authenticated', False):
    st.warning("⚠️ Veuillez vous connecter")
    st.stop()

st.success(f"✅ Connecté en tant que **{st.session_state.get('name', 'Utilisateur')}** ({st.session_state.get('role', 'USER')})")

st.markdown("---")
st.markdown("### 📈 Aperçu rapide")

col1, col2, col3 = st.columns(3)

conn = get_connection()
if conn:
    try:
        cursor = conn.cursor()
        
        # Lots actifs
        cursor.execute("SELECT COUNT(*) as nb FROM lots_bruts WHERE is_active = TRUE")
        result = cursor.fetchone()
        nb_lots_actifs = result['nb'] if result else 0
        
        # Tonnage total
        tonnage_tonnes = 0
        try:
            cursor.execute("SELECT COALESCE(SUM(poids_total_brut_kg), 0) as total FROM lots_bruts WHERE is_active = TRUE")
            result = cursor.fetchone()
            tonnage_total = result['total'] if result else 0
            tonnage_tonnes = float(tonnage_total) / 1000
        except:
            conn.rollback()
            tonnage_tonnes = 0
        
        # Nombre variétés distinctes
        cursor.execute("SELECT COUNT(DISTINCT code_variete) as nb FROM lots_bruts WHERE is_active = TRUE")
        result = cursor.fetchone()
        nb_varietes = result['nb'] if result else 0
        
        cursor.close()
        conn.close()
        
        with col1:
            st.metric("📦 Lots actifs", f"{nb_lots_actifs:,}")
        
        with col2:
            st.metric("⚖️ Tonnage total", f"{tonnage_tonnes:,.1f} T")
        
        with col3:
            st.metric("🌱 Variétés", nb_varietes)
            
    except Exception as e:
        st.warning(f"⚠️ Erreur base de données : {str(e)}")
        if conn:
            conn.rollback()
            conn.close()
else:
    st.warning("⚠️ Connexion à la base de données en attente...")

st.markdown("---")
st.info("👈 Utilisez le menu de navigation dans la barre latérale pour accéder aux différentes fonctionnalités.")

show_footer()
