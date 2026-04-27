# pages/51_CRM_Prod_Contacts.py
# CRM Producteurs - V1 #2 - Multi-contacts par producteur
# Tables : crm_prod_contacts (FK ref_producteurs.id, FK crm_prod_fonctions.id)
# Pattern conforme POMI_REFERENCE_TECHNIQUE.md, calqué sur 22_CRM_Contacts.py

import streamlit as st
import pandas as pd

from database import get_connection
from components import show_footer
from auth import require_access, can_edit, can_delete

# ============================================================
# CONFIGURATION PAGE
# ============================================================
st.set_page_config(
    page_title="CRM Prod Contacts - Culture Pom",
    page_icon="👥",
    layout="wide"
)

st.markdown("""
<style>
.block-container {padding-top:1.5rem!important;padding-bottom:0.5rem!important;
    padding-left:2rem!important;padding-right:2rem!important;}
h1,h2,h3,h4{margin-top:0.3rem!important;margin-bottom:0.3rem!important;}
.contact-principal {background-color:#f7faf0;border-left:4px solid #AFCA0A;
    padding:0.8rem;border-radius:4px;}
.contact-normal {background-color:#f5f5f5;border-left:4px solid #9e9e9e;
    padding:0.8rem;border-radius:4px;}
.fonction-admin {background:#e3f2fd;color:#1565c0;padding:2px 8px;
    border-radius:12px;font-size:0.85em;font-weight:600;}
.fonction-tech {background:#fff3e0;color:#e65100;padding:2px 8px;
    border-radius:12px;font-size:0.85em;font-weight:600;}
.fonction-comm {background:#f3e5f5;color:#6a1b9a;padding:2px 8px;
    border-radius:12px;font-size:0.85em;font-weight:600;}
</style>
""", unsafe_allow_html=True)

# ============================================================
# CONTRÔLE ACCÈS
# ============================================================
require_access("CRM_PRODUCTEURS")

CAN_EDIT = can_edit("CRM_PRODUCTEURS")
CAN_DELETE = can_delete("CRM_PRODUCTEURS")

st.title("👥 CRM Producteurs — Contacts")
st.markdown("*Gestion des contacts admin / technique / commercial par producteur*")
st.markdown("---")

# ============================================================
# CONSTANTES
# ============================================================
# Q1 : on n'expose que ces 3 fonctions, mais on accepte les autres si déjà en base
# (champ fonction_id en base pointe sur crm_prod_fonctions qui contient
#  ADMIN, TECH, COMM, DIRECTION, AUTRE — on filtre côté UI)
FONCTIONS_EXPOSEES = ['ADMIN', 'TECH', 'COMM']

FONCTION_BADGES = {
    'ADMIN': '<span class="fonction-admin">📋 Administratif</span>',
    'TECH': '<span class="fonction-tech">🔧 Technique</span>',
    'COMM': '<span class="fonction-comm">💼 Commercial</span>',
    'DIRECTION': '<span class="fonction-admin">🏢 Direction</span>',
    'AUTRE': '<span class="fonction-tech">📌 Autre</span>',
}


# ============================================================
# FONCTIONS DB
# ============================================================

def get_producteurs_dropdown():
    """Liste des producteurs pour dropdown."""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, code_producteur,
                   nom || COALESCE(' - ' || ville, '') AS libelle
            FROM ref_producteurs
            WHERE is_active = TRUE
            ORDER BY nom
        """)
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        return [(r['id'], r['code_producteur'], r['libelle']) for r in rows]
    except Exception as e:
        st.error(f"❌ Erreur producteurs : {e}")
        return []


def get_fonctions_dropdown():
    """Liste des fonctions exposées (Q1 = ADMIN/TECH/COMM uniquement)."""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, code, libelle
            FROM crm_prod_fonctions
            WHERE is_active = TRUE AND code = ANY(%s)
            ORDER BY ordre
        """, (FONCTIONS_EXPOSEES,))
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        return [(r['id'], r['code'], r['libelle']) for r in rows]
    except Exception as e:
        st.error(f"❌ Erreur fonctions : {e}")
        return []


def get_contacts(filtres=None):
    """Liste contacts avec JOIN producteur + fonction."""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        query = """
            SELECT
                c.id, c.producteur_id, c.fonction_id,
                p.code_producteur, p.nom AS producteur_nom, p.ville,
                f.code AS fonction_code, f.libelle AS fonction_libelle,
                c.nom, c.prenom, c.telephone, c.email,
                c.is_principal, c.commentaires
            FROM crm_prod_contacts c
            JOIN ref_producteurs p ON c.producteur_id = p.id
            LEFT JOIN crm_prod_fonctions f ON c.fonction_id = f.id
            WHERE c.is_active = TRUE AND p.is_active = TRUE
        """
        params = []
        if filtres:
            if filtres.get('producteur_id') and filtres['producteur_id'] != 0:
                query += " AND c.producteur_id = %s"
                params.append(int(filtres['producteur_id']))
            if filtres.get('fonction_code') and filtres['fonction_code'] != 'Toutes':
                query += " AND f.code = %s"
                params.append(filtres['fonction_code'])
            if filtres.get('search'):
                query += """ AND (LOWER(c.nom) LIKE %s OR LOWER(c.prenom) LIKE %s
                           OR LOWER(p.nom) LIKE %s)"""
                s = f"%{filtres['search'].lower()}%"
                params.extend([s, s, s])

        query += " ORDER BY p.nom, c.is_principal DESC, c.nom"
        cursor.execute(query, params)
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        return pd.DataFrame(rows) if rows else pd.DataFrame()
    except Exception as e:
        st.error(f"❌ Erreur chargement contacts : {e}")
        return pd.DataFrame()


def create_contact(data):
    """Crée un contact. Si is_principal, retire le principal existant."""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        producteur_id = int(data['producteur_id'])

        if data.get('is_principal'):
            cursor.execute("""
                UPDATE crm_prod_contacts SET is_principal = FALSE
                WHERE producteur_id = %s
            """, (producteur_id,))

        cursor.execute("""
            INSERT INTO crm_prod_contacts (
                producteur_id, fonction_id, nom, prenom,
                telephone, email, is_principal, commentaires, created_by
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (
            producteur_id,
            int(data['fonction_id']) if data.get('fonction_id') else None,
            (data.get('nom') or '').strip() or None,
            (data.get('prenom') or '').strip() or None,
            (data.get('telephone') or '').strip() or None,
            (data.get('email') or '').strip() or None,
            bool(data.get('is_principal', False)),
            (data.get('commentaires') or '').strip() or None,
            st.session_state.get('username', 'system')
        ))
        new_id = cursor.fetchone()['id']
        conn.commit()
        cursor.close()
        conn.close()
        return True, f"✅ Contact #{new_id} créé"
    except Exception as e:
        if 'conn' in locals():
            conn.rollback()
        return False, f"❌ Erreur : {e}"


def update_contact(contact_id, data):
    try:
        conn = get_connection()
        cursor = conn.cursor()
        contact_id = int(contact_id)
        producteur_id = int(data['producteur_id'])

        if data.get('is_principal'):
            cursor.execute("""
                UPDATE crm_prod_contacts SET is_principal = FALSE
                WHERE producteur_id = %s AND id != %s
            """, (producteur_id, contact_id))

        cursor.execute("""
            UPDATE crm_prod_contacts SET
                producteur_id = %s, fonction_id = %s,
                nom = %s, prenom = %s,
                telephone = %s, email = %s,
                is_principal = %s, commentaires = %s,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
        """, (
            producteur_id,
            int(data['fonction_id']) if data.get('fonction_id') else None,
            (data.get('nom') or '').strip() or None,
            (data.get('prenom') or '').strip() or None,
            (data.get('telephone') or '').strip() or None,
            (data.get('email') or '').strip() or None,
            bool(data.get('is_principal', False)),
            (data.get('commentaires') or '').strip() or None,
            contact_id
        ))
        conn.commit()
        cursor.close()
        conn.close()
        return True, "✅ Contact mis à jour"
    except Exception as e:
        if 'conn' in locals():
            conn.rollback()
        return False, f"❌ Erreur : {e}"


def delete_contact(contact_id):
    """Soft delete."""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE crm_prod_contacts SET is_active = FALSE,
                                          updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
        """, (int(contact_id),))
        conn.commit()
        cursor.close()
        conn.close()
        return True, "✅ Contact supprimé"
    except Exception as e:
        if 'conn' in locals():
            conn.rollback()
        return False, f"❌ Erreur : {e}"


def get_kpis():
    try:
        conn = get_connection()
        cursor = conn.cursor()
        kpis = {}
        cursor.execute("""
            SELECT COUNT(*) AS n FROM crm_prod_contacts c
            JOIN ref_producteurs p ON c.producteur_id = p.id
            WHERE c.is_active = TRUE AND p.is_active = TRUE
        """)
        kpis['total'] = cursor.fetchone()['n']

        cursor.execute("""
            SELECT COUNT(*) AS n FROM crm_prod_contacts c
            JOIN ref_producteurs p ON c.producteur_id = p.id
            WHERE c.is_active = TRUE AND p.is_active = TRUE AND c.is_principal = TRUE
        """)
        kpis['principaux'] = cursor.fetchone()['n']

        cursor.execute("""
            SELECT COUNT(DISTINCT c.producteur_id) AS n FROM crm_prod_contacts c
            JOIN ref_producteurs p ON c.producteur_id = p.id
            WHERE c.is_active = TRUE AND p.is_active = TRUE
        """)
        kpis['producteurs_avec_contacts'] = cursor.fetchone()['n']

        cursor.execute("""
            SELECT f.code, COUNT(*) AS n
            FROM crm_prod_contacts c
            JOIN ref_producteurs p ON c.producteur_id = p.id
            LEFT JOIN crm_prod_fonctions f ON c.fonction_id = f.id
            WHERE c.is_active = TRUE AND p.is_active = TRUE
            GROUP BY f.code
        """)
        rows = cursor.fetchall()
        kpis['par_fonction'] = {r['code'] or 'AUCUNE': r['n'] for r in rows}

        cursor.close()
        conn.close()
        return kpis
    except Exception as e:
        st.error(f"❌ Erreur KPIs : {e}")
        return {}


# ============================================================
# AFFICHAGE KPIs
# ============================================================

kpis = get_kpis()
if kpis:
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("👥 Contacts total", kpis.get('total', 0))
    c2.metric("⭐ Contacts principaux", kpis.get('principaux', 0))
    c3.metric("🏭 Producteurs couverts", kpis.get('producteurs_avec_contacts', 0))
    pf = kpis.get('par_fonction', {})
    c4.metric("📋 ADMIN / TECH / COMM",
              f"{pf.get('ADMIN', 0)} / {pf.get('TECH', 0)} / {pf.get('COMM', 0)}")

st.markdown("---")

# ============================================================
# ONGLETS
# ============================================================

tab1, tab2 = st.tabs(["📋 Liste contacts", "➕ Nouveau contact"])

producteurs = get_producteurs_dropdown()
fonctions = get_fonctions_dropdown()


# ----- TAB 1 — Liste -----
with tab1:
    st.subheader("📋 Liste des contacts")

    if not producteurs:
        st.info("Aucun producteur en base. Crée d'abord un producteur dans la page **Producteurs**.")
    else:
        # Filtres
        prod_options = [(0, '', 'Tous les producteurs')] + producteurs
        f_col1, f_col2, f_col3 = st.columns(3)
        with f_col1:
            f_prod = st.selectbox("Producteur", prod_options,
                                  format_func=lambda x: x[2], key="f_prod_c")
        with f_col2:
            fonctions_codes = ['Toutes'] + [f[1] for f in fonctions]
            f_fonc = st.selectbox("Fonction", fonctions_codes, key="f_fonc_c")
        with f_col3:
            f_search = st.text_input("🔍 Recherche", key="f_search_c")

        df = get_contacts({
            'producteur_id': f_prod[0] if f_prod else 0,
            'fonction_code': f_fonc,
            'search': f_search,
        })

        st.markdown("---")

        if df.empty:
            st.info("Aucun contact trouvé.")
        else:
            st.markdown(f"**{len(df)} contact(s) trouvé(s)**")

            display_df = df[['producteur_nom', 'ville', 'nom', 'prenom',
                             'fonction_libelle', 'telephone', 'email', 'is_principal']].copy()
            display_df['is_principal'] = display_df['is_principal'].apply(lambda x: '⭐' if x else '')
            display_df.columns = ['Producteur', 'Ville', 'Nom', 'Prénom',
                                  'Fonction', 'Téléphone', 'Email', '⭐']
            display_df = display_df.fillna('')

            event = st.dataframe(
                display_df,
                use_container_width=True, hide_index=True,
                on_select="rerun", selection_mode="single-row",
                key="contacts_prod_table"
            )

            selected_rows = event.selection.rows if hasattr(event, 'selection') else []

            if len(selected_rows) > 0:
                idx = selected_rows[0]
                contact = df.iloc[idx]

                st.markdown("---")
                card_class = "contact-principal" if contact['is_principal'] else "contact-normal"
                principal_badge = "⭐ Contact Principal" if contact['is_principal'] else ""
                fonction_badge = FONCTION_BADGES.get(contact.get('fonction_code'), '')

                st.markdown(f"""
                <div class="{card_class}">
                    <h4>{contact['prenom'] or ''} {contact['nom'] or ''} {principal_badge}</h4>
                    <p><strong>Producteur :</strong> {contact['producteur_nom']} — {contact['ville'] or ''}</p>
                    <p><strong>Fonction :</strong> {fonction_badge or contact.get('fonction_libelle') or 'N/A'}</p>
                    <p>📞 {contact['telephone'] or 'N/A'} | ✉️ {contact['email'] or 'N/A'}</p>
                </div>
                """, unsafe_allow_html=True)

                if contact['commentaires']:
                    st.info(f"💬 {contact['commentaires']}")

                col_a, col_b, _ = st.columns([1, 1, 2])
                with col_a:
                    if CAN_EDIT and st.button("✏️ Modifier", key="btn_edit_pc"):
                        st.session_state['edit_pcontact_id'] = int(contact['id'])
                        st.session_state['edit_pcontact_data'] = contact.to_dict()
                        st.rerun()
                with col_b:
                    if CAN_DELETE and st.button("🗑️ Supprimer", key="btn_del_pc",
                                                type="secondary"):
                        st.session_state['confirm_delete_pcontact'] = int(contact['id'])
                        st.rerun()

                # Confirmation suppression
                if st.session_state.get('confirm_delete_pcontact') == int(contact['id']):
                    st.warning("⚠️ Confirmer la suppression ?")
                    col_y, col_n = st.columns(2)
                    with col_y:
                        if st.button("✅ Confirmer", key="confirm_yes_pc"):
                            ok, msg = delete_contact(st.session_state['confirm_delete_pcontact'])
                            if ok:
                                st.success(msg)
                                st.session_state.pop('confirm_delete_pcontact', None)
                                st.rerun()
                            else:
                                st.error(msg)
                    with col_n:
                        if st.button("❌ Annuler", key="confirm_no_pc"):
                            st.session_state.pop('confirm_delete_pcontact', None)
                            st.rerun()

            # Formulaire modification
            if 'edit_pcontact_id' in st.session_state and CAN_EDIT:
                st.markdown("---")
                st.subheader("✏️ Modifier le contact")
                data = st.session_state['edit_pcontact_data']

                col1, col2 = st.columns(2)
                with col1:
                    current_prod = next((i for i, p in enumerate(producteurs)
                                         if p[0] == data.get('producteur_id')), 0)
                    edit_prod = st.selectbox("Producteur *", producteurs, index=current_prod,
                                             format_func=lambda x: x[2], key="edit_prod_pc")

                    fonc_opts = [(None, '', '-- Aucune --')] + fonctions
                    current_fonc = next((i for i, f in enumerate(fonc_opts)
                                         if f[0] == data.get('fonction_id')), 0)
                    edit_fonc = st.selectbox("Fonction", fonc_opts, index=current_fonc,
                                             format_func=lambda x: x[2], key="edit_fonc_pc")

                    edit_nom = st.text_input("Nom", value=data.get('nom', '') or '', key="edit_nom_pc")
                    edit_prenom = st.text_input("Prénom", value=data.get('prenom', '') or '',
                                                key="edit_prenom_pc")

                with col2:
                    edit_tel = st.text_input("Téléphone", value=data.get('telephone', '') or '',
                                             key="edit_tel_pc")
                    edit_email = st.text_input("Email", value=data.get('email', '') or '',
                                               key="edit_email_pc")
                    edit_principal = st.checkbox("⭐ Contact principal",
                                                 value=bool(data.get('is_principal', False)),
                                                 key="edit_princ_pc")

                edit_comments = st.text_area("Commentaires", value=data.get('commentaires', '') or '',
                                             key="edit_comm_pc")

                col_save, col_cancel = st.columns(2)
                with col_save:
                    is_saving = st.session_state.get('is_saving_pc', False)
                    if st.button("💾 Enregistrer", type="primary", key="btn_save_pc",
                                 disabled=is_saving):
                        if not edit_nom and not edit_prenom:
                            st.error("❌ Nom ou prénom requis")
                        else:
                            st.session_state['is_saving_pc'] = True
                            update_data = {
                                'producteur_id': edit_prod[0],
                                'fonction_id': edit_fonc[0],
                                'nom': edit_nom, 'prenom': edit_prenom,
                                'telephone': edit_tel, 'email': edit_email,
                                'is_principal': edit_principal,
                                'commentaires': edit_comments,
                            }
                            ok, msg = update_contact(
                                st.session_state['edit_pcontact_id'], update_data
                            )
                            if ok:
                                st.success(msg)
                                st.session_state.pop('edit_pcontact_id', None)
                                st.session_state.pop('edit_pcontact_data', None)
                                st.session_state.pop('is_saving_pc', None)
                                st.rerun()
                            else:
                                st.session_state.pop('is_saving_pc', None)
                                st.error(msg)
                with col_cancel:
                    if st.button("❌ Annuler", key="btn_cancel_pc"):
                        st.session_state.pop('edit_pcontact_id', None)
                        st.session_state.pop('edit_pcontact_data', None)
                        st.session_state.pop('is_saving_pc', None)
                        st.rerun()


# ----- TAB 2 — Nouveau contact -----
with tab2:
    if not CAN_EDIT:
        st.warning("⚠️ Droits insuffisants pour créer un contact.")
    elif not producteurs:
        st.warning("⚠️ Aucun producteur disponible. Crée d'abord un producteur.")
    else:
        st.subheader("➕ Créer un contact")
        st.info(f"📋 {len(producteurs)} producteur(s) disponible(s)")

        # Pré-sélection si on vient de la page 50 via session_state
        preselect_id = st.session_state.get('new_pcontact_producteur_id')
        default_prod_idx = 0
        if preselect_id:
            for i, p in enumerate(producteurs):
                if p[0] == preselect_id:
                    default_prod_idx = i
                    break
            st.session_state.pop('new_pcontact_producteur_id', None)

        col1, col2 = st.columns(2)
        with col1:
            new_prod = st.selectbox("Producteur *", producteurs,
                                    index=default_prod_idx,
                                    format_func=lambda x: x[2], key="new_prod_pc")

            fonc_opts = [(None, '', '-- Aucune --')] + fonctions
            new_fonc = st.selectbox("Fonction", fonc_opts,
                                    format_func=lambda x: x[2], key="new_fonc_pc")

            new_nom = st.text_input("Nom", key="new_nom_pc")
            new_prenom = st.text_input("Prénom", key="new_prenom_pc")

        with col2:
            new_tel = st.text_input("Téléphone", key="new_tel_pc")
            new_email = st.text_input("Email", key="new_email_pc")
            new_principal = st.checkbox("⭐ Contact principal", key="new_princ_pc")

        new_comments = st.text_area("Commentaires", key="new_comm_pc")

        is_creating = st.session_state.get('is_creating_pc', False)
        if st.button("✅ Créer le contact", type="primary", key="btn_create_pc",
                     disabled=is_creating):
            if not new_nom and not new_prenom:
                st.error("❌ Nom ou prénom requis")
            else:
                st.session_state['is_creating_pc'] = True
                ok, msg = create_contact({
                    'producteur_id': new_prod[0],
                    'fonction_id': new_fonc[0],
                    'nom': new_nom, 'prenom': new_prenom,
                    'telephone': new_tel, 'email': new_email,
                    'is_principal': new_principal,
                    'commentaires': new_comments,
                })
                if ok:
                    st.success(msg)
                    for k in list(st.session_state.keys()):
                        if k.startswith('new_') and k.endswith('_pc'):
                            st.session_state.pop(k, None)
                    st.session_state.pop('is_creating_pc', None)
                    st.rerun()
                else:
                    st.session_state.pop('is_creating_pc', None)
                    st.error(msg)

show_footer()
