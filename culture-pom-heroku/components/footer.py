import streamlit as st
from datetime import datetime

def show_footer():
    """Footer Culture Pom avec emoji drapeau français"""
    st.markdown('---')
    year = datetime.now().year
    
    st.markdown(
        f"""
        <div style="text-align: center; color: #666; font-size: 0.85rem; padding: 1rem 0;">
            <div style="margin-bottom: 0.3rem;">
                Réalisé avec passion 🇫🇷 pour <span style="font-weight: 600; color: #2E7D32;">Culture Pom</span>
            </div>
            <div style="color: #999; font-size: 0.8rem;">
                par <span style="font-weight: 600; color: #2E7D32;">3Force Consulting</span> © {year}
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )