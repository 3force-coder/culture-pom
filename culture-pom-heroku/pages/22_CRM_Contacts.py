import streamlit as st
import pandas as pd
from datetime import datetime
from database import get_connection
from components import show_footer
from auth import is_authenticated, require_access, can_edit, can_delete

st.set_page_config(page_title="CRM Contacts - Culture Pom", page_icon="👥", layout="wide")

if not is_authenticated():
    st.warning("⚠️ Veuillez vous connecter")
    st.stop()

require_access("CRM")

st.markdown("""
<style>
    .block-container { padding-top: 1.5rem !important; padding-bottom: 0.5rem !important; }
    h1, h2, h3, h4 { margin-top: 0.3rem !important; margin-bottom: 0.3rem !important; }
    .contact-principal { background-color: #e3f2fd; border-left: 4px solid #2196f3; padding: 0.8rem; border-radius: 4px; }
    .contact-normal { background-color: #f5f5f5; border-left: 4px solid #9e9e9e; padding: 0.8rem; border-radius: 4px; }
</style>
""", unsafe_allow_html=True)

st.title("👥 CRM - Gestion des Contacts")
st.markdown("---")

# ==========================================
# FONCTIONS
# ==========================================

def get_magasins_dropdown():
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, code_magasin, enseigne || ' - ' || ville as nom 
            FROM crm_magasins WHERE is_active = TRUE ORDER BY enseigne, ville
        """)
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        return [(r['id'], r['code_magasin'], r['nom']) for r in rows]
    except:
        return []

def get_contacts(filtres=None):
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        query = """
            SELECT 
                c.id, c.magasin_id, m.enseigne, m.ville,
                c.nom, c.prenom, c.fonction, c.telephone, c.email,
                c.is_principal, c.commentaires
            FROM crm_contacts c
            JOIN crm_magasins m ON c.magasin_id = m.id
            WHERE c.is_active = TRUE AND m.is_active = TRUE
        """
        params = []
        
        if filtres:
            if filtres.get('magasin_id') and filtres['magasin_id'] != 0:
                query += " AND c.magasin_id = %s"
                params.append(int(filtres['magasin_id']))  # ⭐ Conversion int
            if filtres.get('fonction') and filtres['fonction'] != 'Tous':
                query += " AND c.fonction = %s"
                params.append(filtres['fonction'])
            if filtres.get('search'):
                query += " AND (LOWER(c.nom) LIKE %s OR LOWER(c.prenom) LIKE %s OR LOWER(m.enseigne) LIKE %s)"
                search = f"%{filtres['search'].lower()}%"
                params.extend([search, search, search])
        
        query += " ORDER BY m.enseigne, c.is_principal DESC, c.nom"
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        
        if rows:
            return pd.DataFrame(rows)
        return pd.DataFrame()
    except Exception as e:
        st.error(f"❌ Erreur : {str(e)}")
        return pd.DataFrame()

def get_fonctions():
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT fonction FROM crm_contacts WHERE is_active = TRUE AND fonction IS NOT NULL ORDER BY fonction")
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        return [r['fonction'] for r in rows]
    except:
        return []

def create_contact(data):
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # ⭐ Conversion int pour magasin_id
        magasin_id = int(data['magasin_id'])
        
        # Si principal, retirer le principal existant
        if data.get('is_principal'):
            cursor.execute("UPDATE crm_contacts SET is_principal = FALSE WHERE magasin_id = %s", (magasin_id,))
        
        cursor.execute("""
            INSERT INTO crm_contacts (magasin_id, nom, prenom, fonction, telephone, email, is_principal, commentaires)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (
            magasin_id, data.get('nom'), data.get('prenom'),
            data.get('fonction'), data.get('telephone'), data.get('email'),
            bool(data.get('is_principal', False)), data.get('commentaires')
        ))
        
        contact_id = cursor.fetchone()['id']
        conn.commit()
        cursor.close()
        conn.close()
        
        return True, f"✅ Contact #{contact_id} créé"
    except Exception as e:
        return False, f"❌ Erreur : {str(e)}"

def update_contact(contact_id, data):
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # ⭐ Conversion int pour les IDs
        contact_id = int(contact_id)
        magasin_id = int(data['magasin_id'])
        
        # Si principal, retirer le principal existant
        if data.get('is_principal'):
            cursor.execute("UPDATE crm_contacts SET is_principal = FALSE WHERE magasin_id = %s AND id != %s", 
                          (magasin_id, contact_id))
        
        cursor.execute("""
            UPDATE crm_contacts SET
                magasin_id = %s, nom = %s, prenom = %s, fonction = %s,
                telephone = %s, email = %s, is_principal = %s, commentaires = %s,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
        """, (
            magasin_id, data.get('nom'), data.get('prenom'),
            data.get('fonction'), data.get('telephone'), data.get('email'),
            bool(data.get('is_principal', False)), data.get('commentaires'), contact_id
        ))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return True, "✅ Contact mis à jour"
    except Exception as e:
        return False, f"❌ Erreur : {str(e)}"

def delete_contact(contact_id):
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # ⭐ CORRECTION : Conversion int() pour éviter numpy.int64
        contact_id = int(contact_id)
        
        cursor.execute("UPDATE crm_contacts SET is_active = FALSE, updated_at = CURRENT_TIMESTAMP WHERE id = %s", (contact_id,))
        conn.commit()
        cursor.close()
        conn.close()
        return True, "✅ Contact supprimé"
    except Exception as e:
        return False, f"❌ Erreur : {str(e)}"

# ==========================================
# ONGLETS
# ==========================================

tab1, tab2 = st.tabs(["📋 Liste Contacts", "➕ Nouveau Contact"])

with tab1:
    magasins = get_magasins_dropdown()
    fonctions = get_fonctions()
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        mag_options = [(0, '', 'Tous les magasins')] + magasins
        filtre_magasin = st.selectbox("Magasin", mag_options, format_func=lambda x: x[2], key="f_mag_c")
    with col2:
        filtre_fonction = st.selectbox("Fonction", ['Tous'] + fonctions, key="f_fonc_c")
    with col3:
        filtre_search = st.text_input("🔍 Recherche", key="f_search_c")
    
    filtres = {
        'magasin_id': filtre_magasin[0] if filtre_magasin else 0,
        'fonction': filtre_fonction,
        'search': filtre_search
    }
    
    st.markdown("---")
    
    df = get_contacts(filtres)
    
    if not df.empty:
        st.markdown(f"**{len(df)} contact(s) trouvé(s)**")
        
        display_df = df[['enseigne', 'ville', 'nom', 'prenom', 'fonction', 'telephone', 'email', 'is_principal']].copy()
        display_df['is_principal'] = display_df['is_principal'].apply(lambda x: '⭐' if x else '')
        display_df.columns = ['Enseigne', 'Ville', 'Nom', 'Prénom', 'Fonction', 'Téléphone', 'Email', '⭐']
        display_df = display_df.fillna('')
        
        event = st.dataframe(
            display_df,
            use_container_width=True,
            hide_index=True,
            on_select="rerun",
            selection_mode="single-row",
            key="contacts_table"
        )
        
        selected_rows = event.selection.rows if hasattr(event, 'selection') else []
        
        if len(selected_rows) > 0:
            idx = selected_rows[0]
            contact = df.iloc[idx]
            
            st.markdown("---")
            
            card_class = "contact-principal" if contact['is_principal'] else "contact-normal"
            principal_badge = "⭐ Contact Principal" if contact['is_principal'] else ""
            
            st.markdown(f"""
            <div class="{card_class}">
                <h4>{contact['prenom'] or ''} {contact['nom'] or ''} {principal_badge}</h4>
                <p><strong>Magasin :</strong> {contact['enseigne']} - {contact['ville']}</p>
                <p><strong>Fonction :</strong> {contact['fonction'] or 'N/A'}</p>
                <p>📞 {contact['telephone'] or 'N/A'} | ✉️ {contact['email'] or 'N/A'}</p>
            </div>
            """, unsafe_allow_html=True)
            
            if contact['commentaires']:
                st.info(f"💬 {contact['commentaires']}")
            
            col_a, col_b, col_c = st.columns([1, 1, 2])
            
            with col_a:
                if can_edit("CRM"):
                    if st.button("✏️ Modifier", key="btn_edit_c"):
                        # ⭐ Conversion int pour stocker en session
                        st.session_state['edit_contact_id'] = int(contact['id'])
                        st.session_state['edit_contact_data'] = contact.to_dict()
                        st.rerun()
            
            with col_b:
                if can_delete("CRM"):
                    if st.button("🗑️ Supprimer", key="btn_del_c", type="secondary"):
                        # ⭐ Conversion int pour stocker en session
                        st.session_state['confirm_delete_contact'] = int(contact['id'])
                        st.rerun()
            
            # ⭐ Comparaison avec int converti
            if st.session_state.get('confirm_delete_contact') == int(contact['id']):
                st.warning("⚠️ Confirmer la suppression ?")
                col_yes, col_no = st.columns(2)
                with col_yes:
                    if st.button("✅ Confirmer", key="confirm_yes_c"):
                        # ⭐ L'ID est déjà un int dans session_state
                        success, msg = delete_contact(st.session_state['confirm_delete_contact'])
                        if success:
                            st.success(msg)
                            st.session_state.pop('confirm_delete_contact', None)
                            st.rerun()
                        else:
                            st.error(msg)
                with col_no:
                    if st.button("❌ Annuler", key="confirm_no_c"):
                        st.session_state.pop('confirm_delete_contact', None)
                        st.rerun()
        
        # Formulaire modification
        if 'edit_contact_id' in st.session_state and can_edit("CRM"):
            st.markdown("---")
            st.subheader("✏️ Modifier le contact")
            
            data = st.session_state['edit_contact_data']
            
            col1, col2 = st.columns(2)
            
            with col1:
                current_mag = next((i for i, m in enumerate(magasins) if m[0] == data.get('magasin_id')), 0)
                edit_magasin = st.selectbox("Magasin *", magasins, index=current_mag, format_func=lambda x: x[2], key="edit_mag_c")
                edit_nom = st.text_input("Nom", value=data.get('nom', '') or '', key="edit_nom_c")
                edit_prenom = st.text_input("Prénom", value=data.get('prenom', '') or '', key="edit_pren_c")
                edit_fonction = st.text_input("Fonction", value=data.get('fonction', '') or '', key="edit_fonc_c")
            
            with col2:
                edit_tel = st.text_input("Téléphone", value=data.get('telephone', '') or '', key="edit_tel_c")
                edit_email = st.text_input("Email", value=data.get('email', '') or '', key="edit_email_c")
                edit_principal = st.checkbox("Contact principal", value=data.get('is_principal', False), key="edit_princ_c")
            
            edit_comments = st.text_area("Commentaires", value=data.get('commentaires', '') or '', key="edit_com_c")
            
            col_save, col_cancel = st.columns(2)
            
            with col_save:
                if st.button("💾 Enregistrer", type="primary", key="btn_save_c"):
                    if not edit_nom and not edit_prenom:
                        st.error("❌ Nom ou prénom requis")
                    else:
                        update_data = {
                            'magasin_id': edit_magasin[0],
                            'nom': edit_nom or None, 'prenom': edit_prenom or None,
                            'fonction': edit_fonction or None, 'telephone': edit_tel or None,
                            'email': edit_email or None, 'is_principal': edit_principal,
                            'commentaires': edit_comments or None
                        }
                        success, msg = update_contact(st.session_state['edit_contact_id'], update_data)
                        if success:
                            st.success(msg)
                            st.session_state.pop('edit_contact_id', None)
                            st.session_state.pop('edit_contact_data', None)
                            st.rerun()
                        else:
                            st.error(msg)
            
            with col_cancel:
                if st.button("❌ Annuler", key="btn_cancel_c"):
                    st.session_state.pop('edit_contact_id', None)
                    st.session_state.pop('edit_contact_data', None)
                    st.rerun()
    else:
        st.info("Aucun contact trouvé")

with tab2:
    if not can_edit("CRM"):
        st.warning("⚠️ Vous n'avez pas les droits pour créer un contact")
    else:
        st.subheader("➕ Créer un contact")
        
        magasins = get_magasins_dropdown()
        
        if not magasins:
            st.warning("⚠️ Aucun magasin disponible")
        else:
            col1, col2 = st.columns(2)
            
            with col1:
                new_magasin = st.selectbox("Magasin *", magasins, format_func=lambda x: x[2], key="new_mag_c")
                new_nom = st.text_input("Nom", key="new_nom_c")
                new_prenom = st.text_input("Prénom", key="new_pren_c")
                new_fonction = st.text_input("Fonction", key="new_fonc_c")
            
            with col2:
                new_tel = st.text_input("Téléphone", key="new_tel_c")
                new_email = st.text_input("Email", key="new_email_c")
                new_principal = st.checkbox("Contact principal", key="new_princ_c")
            
            new_comments = st.text_area("Commentaires", key="new_com_c")
            
            if st.button("✅ Créer le contact", type="primary", key="btn_create_c"):
                if not new_nom and not new_prenom:
                    st.error("❌ Nom ou prénom requis")
                else:
                    data = {
                        'magasin_id': new_magasin[0],
                        'nom': new_nom or None, 'prenom': new_prenom or None,
                        'fonction': new_fonction or None, 'telephone': new_tel or None,
                        'email': new_email or None, 'is_principal': new_principal,
                        'commentaires': new_comments or None
                    }
                    success, msg = create_contact(data)
                    if success:
                        st.success(msg)
                        st.balloons()
                    else:
                        st.error(msg)

show_footer()
