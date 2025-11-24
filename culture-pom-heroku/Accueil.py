import streamlit as st
from auth import show_login, is_authenticated
from components import show_header, show_footer
from database import get_connection

st.set_page_config(
    page_title="Culture Pom - Accueil",
    page_icon="🥔",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Logo TOUT EN HAUT de la sidebar
st.logo('https://i.imgur.com/kuLXrHZ.png')

def main():
    if not is_authenticated():
        show_login()
    else:
        show_app()

def show_app():
    # Header principal
    show_header("Culture Pom", "Gestion de la Production")
    
    # Infos utilisateur dans la sidebar
    with st.sidebar:
        st.markdown("---")
        st.write(f"👤 {st.session_state['name']}")
        st.caption(f"📧 {st.session_state['email']}")
        st.caption(f"🔑 {st.session_state['role']}")
        st.markdown("---")
        
        # Bouton déconnexion
        if st.button("🚪 Déconnexion", use_container_width=True):
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()
    
    st.success(f"✅ Connecté en tant que **{st.session_state['name']}** ({st.session_state['role']})")
    
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
            
            # Tonnage total - CORRECTION: utiliser poids_lave_net_kg
            tonnage_tonnes = 0
            try:
                cursor.execute("SELECT COALESCE(SUM(poids_lave_net_kg), 0) as total FROM lots_bruts WHERE is_active = TRUE")
                result = cursor.fetchone()
                tonnage_total = result['total'] if result else 0
                tonnage_tonnes = tonnage_total / 1000
            except Exception as e:
                # Si poids_lave_net_kg échoue, essayer poids_total_brut_kg
                conn.rollback()
                try:
                    cursor.execute("SELECT COALESCE(SUM(poids_total_brut_kg), 0) as total FROM lots_bruts WHERE is_active = TRUE")
                    result = cursor.fetchone()
                    tonnage_total = result['total'] if result else 0
                    tonnage_tonnes = tonnage_total / 1000
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

if __name__ == "__main__":
    main()
