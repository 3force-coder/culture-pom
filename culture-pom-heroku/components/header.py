import streamlit as st

def show_header(title='Culture Pom', subtitle=None):
    """Header simple et compact"""
    st.title(title)
    if subtitle:
        st.caption(subtitle)
    st.markdown('---')