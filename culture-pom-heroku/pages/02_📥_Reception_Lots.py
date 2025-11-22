import streamlit as st
from auth import is_authenticated
from components import show_header, show_footer

st.set_page_config(page_title='Réception Lots', page_icon='📥', layout='wide')

if not is_authenticated():
    st.error('🔒 Veuillez vous connecter')
    st.stop()

show_header('📥 Réception de Lots')

with st.sidebar:
    st.write(f"👤 {st.session_state['name']}")
    if st.button('🚪 Déconnexion'):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()

st.info('📝 Enregistrez un nouveau lot')

with st.form('form_reception'):
    nom_lot = st.text_input('Nom du lot *')
    code_variete = st.text_input('Code variété *')
    site = st.text_input('Site de stockage *')
    
    submitted = st.form_submit_button('✅ Enregistrer')
    
    if submitted:
        if nom_lot and code_variete and site:
            st.success(f'✅ Lot enregistré : {nom_lot}')
            st.balloons()
        else:
            st.error('❌ Remplissez tous les champs')

show_footer()
