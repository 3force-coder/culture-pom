import streamlit as st
import pandas as pd
from datetime import datetime
from database import get_connection
from components import show_footer
from auth import is_authenticated
from roles import is_admin

st.set_page_config(page_title="CRM Contacts - Culture Pom", page_icon="👥", layout="wide")

st.markdown("""
<style>
    .block-container { padding-top: 1.5rem !important; padding-bottom: 0.5rem !important; }
    h1, h2, h3, h4 { margin-top: 0.3rem !important; margin-bottom: 0.3rem !important; }
    .contact-principal { background-color: #e3f2fd; border-left: 4px solid #1976d2; padding: 0.8rem; border-radius: 4px; margin: 0.3rem 0; }
    .contact-normal { background-color: #f5f5f5; border-left: 4px solid #9e9e9e; padding: 0.8rem; border-radius: 4px; margin: 0.3rem 0; }
</style>
""", unsafe_allow_html=True)

if not is_authenticated():
    st.warning("⚠️ Veuillez vous connecter")
    st.stop()

st.title("👥 CRM - Gestion Contacts")
st.markdown("---")

# ==========================================
# FONCTIONS
# ==========================================

def get_magasins_dropdown():
    """Liste des magasins pour dropdown"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, code_magasin, enseigne || ' - ' || ville as nom 
            FROM crm_magasins 
            WHERE is_active = TRUE 
            ORDER BY enseigne, ville
        """)
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        return [(r[0], r[1], r[2]) for r in rows]
    except:
        return []

def get_contacts(filtres=None):
    """Récupère les contacts avec filtres"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        query = """
            SELECT 
                c.id, c.magasin_id, m.code_magasin, m.enseigne, m.ville,
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
                params.append(filtres['magasin_id'])
            if filtres.get('fonction') and filtres['fonction'] != 'Tous':
                query += " AND c.fonction = %s"
                params.append(filtres['fonction'])
            if filtres.get('recherche'):
                query += " AND (LOWER(c.nom) LIKE %s OR LOWER(c.prenom) LIKE %s OR LOWER(m.enseigne) LIKE %s)"
                search = f"%{filtres['recherche'].lower()}%"
                params.extend([search, search, search])
        
        query += " ORDER BY m.enseigne, m.ville, c.is_principal DESC, c.nom"
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        
        if rows:
            return pd.DataFrame(rows, columns=[
                'id', 'magasin_id', 'code_magasin', 'enseigne', 'ville',
                'nom', 'prenom', 'fonction', 'telephone', 'email',
                'is_principal', 'commentaires'
            ])
        return pd.DataFrame()
    except Exception as e:
        st.error(f"❌ Erreur : {str(e)}")
        return pd.DataFrame()

def get_fonctions():
    """Liste des fonctions distinctes"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT fonction FROM crm_contacts WHERE is_active = TRUE AND fonction IS NOT NULL ORDER BY fonction")
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        return ['Tous'] + [r[0] for r in rows]
    except:
        return ['Tous']

def create_contact(data):
    """Crée un nouveau contact"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Si principal, retirer le principal existant
        if data.get('is_principal'):
            cursor.execute("""
                UPDATE crm_contacts SET is_principal = FALSE 
                WHERE magasin_id = %s AND is_principal = TRUE
            """, (data['magasin_id'],))
        
        cursor.execute("""
            INSERT INTO crm_contacts (
                magasin_id, nom, prenom, fonction, telephone, email, is_principal, commentaires
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (
            data['magasin_id'], data.get('nom'), data.get('prenom'),
            data.get('fonction'), data.get('telephone'), data.get('email'),
            data.get('is_principal', False), data.get('commentaires')
        ))
        
        contact_id = cursor.fetchone()[0]
        conn.commit()
        cursor.close()
        conn.close()
        
        return True, f"✅ Contact #{contact_id} créé"
    except Exception as e:
        return False, f"❌ Erreur : {str(e)}"

def update_contact(contact_id, data):
    """Met à jour un contact"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Si principal, retirer le principal existant
        if data.get('is_principal'):
            cursor.execute("""
                UPDATE crm_contacts SET is_principal = FALSE 
                WHERE magasin_id = %s AND is_principal = TRUE AND id != %s
            """, (data['magasin_id'], contact_id))
        
        cursor.execute("""
            UPDATE crm_contacts SET
                magasin_id = %s, nom = %s, prenom = %s, fonction = %s,
                telephone = %s, email = %s, is_principal = %s, commentaires = %s,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
        """, (
            data['magasin_id'], data.get('nom'), data.get('prenom'),
            data.get('fonction'), data.get('telephone'), data.get('email'),
            data.get('is_principal', False), data.get('commentaires'),
            contact_id
        ))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return True, "✅ Contact mis à jour"
    except Exception as e:
        return False, f"❌ Erreur : {str(e)}"

def delete_contact(contact_id):
    """Supprime (désactive) un contact"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
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

# ==========================================
# TAB 1 : LISTE
# ==========================================

with tab1:
    # Filtres
    magasins = get_magasins_dropdown()
    fonctions = get_fonctions()
    
    col1, col2, col3 = st.columns([2, 1, 2])
    
    with col1:
        mag_options = [(0, '', 'Tous les magasins')] + magasins
        filtre_magasin = st.selectbox("Magasin", mag_options, format_func=lambda x: x[2], key="f_mag")
    
    with col2:
        filtre_fonction = st.selectbox("Fonction", fonctions, key="f_fonc")
    
    with col3:
        filtre_recherche = st.text_input("🔍 Recherche (nom, prénom, enseigne)", key="f_search")
    
    filtres = {
        'magasin_id': filtre_magasin[0] if filtre_magasin else 0,
        'fonction': filtre_fonction,
        'recherche': filtre_recherche
    }
    
    st.markdown("---")
    
    # Chargement
    df = get_contacts(filtres)
    
    if not df.empty:
        st.markdown(f"**{len(df)} contact(s) trouvé(s)**")
        
        # Tableau
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
            
            # Affichage détail
            principal_class = "contact-principal" if contact['is_principal'] else "contact-normal"
            principal_txt = "⭐ Contact Principal" if contact['is_principal'] else ""
            
            st.markdown(f"""
            <div class="{principal_class}">
                <h4>{contact['prenom'] or ''} {contact['nom'] or ''} {principal_txt}</h4>
                <p><strong>Magasin :</strong> {contact['enseigne']} - {contact['ville']}</p>
                <p><strong>Fonction :</strong> {contact['fonction'] or '-'}</p>
                <p>📞 {contact['telephone'] or '-'} | 📧 {contact['email'] or '-'}</p>
            </div>
            """, unsafe_allow_html=True)
            
            if contact['commentaires']:
                st.info(f"💬 {contact['commentaires']}")
            
            # Boutons actions
            col_a, col_b, col_c = st.columns([1, 1, 2])
            
            with col_a:
                if st.button("✏️ Modifier", key="btn_edit_contact"):
                    st.session_state['edit_contact_id'] = contact['id']
                    st.session_state['edit_contact_data'] = contact.to_dict()
                    st.rerun()
            
            with col_b:
                if is_admin():
                    if st.button("🗑️ Supprimer", key="btn_del_contact", type="secondary"):
                        st.session_state['confirm_delete_contact'] = contact['id']
                        st.rerun()
            
            # Confirmation suppression
            if st.session_state.get('confirm_delete_contact') == contact['id']:
                st.warning(f"⚠️ Confirmer la suppression de {contact['prenom']} {contact['nom']} ?")
                col_yes, col_no = st.columns(2)
                with col_yes:
                    if st.button("✅ Confirmer", key="confirm_yes_c"):
                        success, msg = delete_contact(contact['id'])
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
        if 'edit_contact_id' in st.session_state:
            st.markdown("---")
            st.subheader("✏️ Modifier le contact")
            
            data = st.session_state['edit_contact_data']
            
            col1, col2 = st.columns(2)
            
            with col1:
                mag_list = [(m[0], m[1], m[2]) for m in magasins]
                current_mag = next((i for i, m in enumerate(mag_list) if m[0] == data.get('magasin_id')), 0)
                edit_magasin = st.selectbox("Magasin *", mag_list, index=current_mag, format_func=lambda x: x[2], key="edit_mag")
                edit_nom = st.text_input("Nom", value=data.get('nom', '') or '', key="edit_nom")
                edit_prenom = st.text_input("Prénom", value=data.get('prenom', '') or '', key="edit_prenom")
                edit_fonction = st.text_input("Fonction", value=data.get('fonction', '') or '', key="edit_fonc")
            
            with col2:
                edit_tel = st.text_input("Téléphone", value=data.get('telephone', '') or '', key="edit_tel")
                edit_email = st.text_input("Email", value=data.get('email', '') or '', key="edit_email")
                edit_principal = st.checkbox("Contact principal ⭐", value=bool(data.get('is_principal')), key="edit_princ")
            
            edit_comm = st.text_area("Commentaires", value=data.get('commentaires', '') or '', key="edit_comm_c")
            
            col_save, col_cancel = st.columns(2)
            
            with col_save:
                if st.button("💾 Enregistrer", type="primary", key="btn_save_edit_c"):
                    update_data = {
                        'magasin_id': edit_magasin[0],
                        'nom': edit_nom or None,
                        'prenom': edit_prenom or None,
                        'fonction': edit_fonction or None,
                        'telephone': edit_tel or None,
                        'email': edit_email or None,
                        'is_principal': edit_principal,
                        'commentaires': edit_comm or None
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
                if st.button("❌ Annuler", key="btn_cancel_edit_c"):
                    st.session_state.pop('edit_contact_id', None)
                    st.session_state.pop('edit_contact_data', None)
                    st.rerun()
    else:
        st.info("Aucun contact trouvé")

# ==========================================
# TAB 2 : NOUVEAU CONTACT
# ==========================================

with tab2:
    st.subheader("➕ Créer un nouveau contact")
    
    magasins = get_magasins_dropdown()
    
    if not magasins:
        st.warning("⚠️ Aucun magasin disponible. Créez d'abord un magasin.")
    else:
        col1, col2 = st.columns(2)
        
        with col1:
            new_magasin = st.selectbox("Magasin *", magasins, format_func=lambda x: x[2], key="new_mag")
            new_nom = st.text_input("Nom", key="new_nom")
            new_prenom = st.text_input("Prénom", key="new_prenom")
            new_fonction = st.text_input("Fonction", key="new_fonc")
        
        with col2:
            new_tel = st.text_input("Téléphone", key="new_tel")
            new_email = st.text_input("Email", key="new_email")
            new_principal = st.checkbox("Contact principal ⭐", key="new_princ")
        
        new_comm = st.text_area("Commentaires", key="new_comm_c")
        
        if st.button("✅ Créer le contact", type="primary", key="btn_create_c"):
            if not new_nom and not new_prenom:
                st.error("❌ Au moins un nom ou prénom est requis")
            else:
                data = {
                    'magasin_id': new_magasin[0],
                    'nom': new_nom or None,
                    'prenom': new_prenom or None,
                    'fonction': new_fonction or None,
                    'telephone': new_tel or None,
                    'email': new_email or None,
                    'is_principal': new_principal,
                    'commentaires': new_comm or None
                }
                success, msg = create_contact(data)
                if success:
                    st.success(msg)
                    st.balloons()
                else:
                    st.error(msg)

show_footer()
