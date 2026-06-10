# pages/55_CRM_Negoce_Clients.py
# CRM Négoce-Export — Clients / Contacts / Interactions
# Tables : crm_neg_clients, crm_neg_contacts, crm_neg_fonctions, crm_neg_interactions
# Pattern conforme POMI_REFERENCE_TECHNIQUE.md (RealDictCursor, pas de st.form,
# requêtes paramétrées, types Python natifs).
# Structure VOLONTAIREMENT distincte du CRM Producteurs (utilisateurs différents) :
#   master-détail (liste à gauche / fiche à droite) + 3 onglets dans la fiche.

import streamlit as st
import pandas as pd
from datetime import datetime, date

from database import get_connection
from components import show_footer
from auth import require_access, can_edit, can_delete

# ============================================================
# CONFIGURATION PAGE
# ============================================================
st.set_page_config(
    page_title="CRM Négoce - Culture Pom",
    page_icon="🌍",
    layout="wide"
)

st.markdown("""
<style>
.block-container {padding-top:1.5rem!important;padding-bottom:0.5rem!important;
    padding-left:2rem!important;padding-right:2rem!important;}
h1,h2,h3,h4{margin-top:0.3rem!important;margin-bottom:0.3rem!important;}
[data-testid="stMetricValue"]{font-size:1.3rem!important;}
hr{margin-top:0.5rem!important;margin-bottom:0.5rem!important;}
.client-row {padding:0.45rem 0.7rem;border-radius:6px;margin:0.2rem 0;
    border-left:4px solid #AFCA0A;background:#f6f8ec;}
.client-row-sel {padding:0.45rem 0.7rem;border-radius:6px;margin:0.2rem 0;
    border-left:4px solid #6E7F08;background:#AFCA0A;color:#1a1a1a;font-weight:600;}
.badge-cat {display:inline-block;padding:1px 8px;border-radius:10px;font-size:0.72rem;
    background:#FFEC00;color:#5a5a00;font-weight:600;}
.fiche-head {background:#f6f8ec;border:1px solid #d9e3a8;border-radius:8px;
    padding:0.8rem 1rem;margin-bottom:0.6rem;}
.inter-row {background:#f7f7f7;border-left:3px solid #7A7A7A;padding:0.5rem 0.8rem;
    border-radius:4px;margin:0.25rem 0;}
</style>
""", unsafe_allow_html=True)

# ============================================================
# CONTRÔLE ACCÈS
# ============================================================
require_access("CRM_NEGOCE")
CAN_EDIT = can_edit("CRM_NEGOCE")
CAN_DELETE = can_delete("CRM_NEGOCE")

TYPES_INTERACTION = ['RELANCE', 'SUIVI', 'PRESENTATION', 'PROPOSITION', 'VISITE', 'LITIGE', 'COMMANDE']

st.title("🌍 CRM Négoce-Export")
st.markdown("*Clients export, contacts et suivi commercial*")
st.markdown("---")


# ============================================================
# FONCTIONS DONNÉES
# ============================================================
def _df(rows):
    return pd.DataFrame([dict(r) for r in rows]) if rows else pd.DataFrame()


def get_users():
    """Comptes Culture Pom pour le référent interne (réutilise users_app)."""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id,
                   COALESCE(NULLIF(TRIM(COALESCE(prenom,'')||' '||COALESCE(nom,'')),''),
                            username, 'User #'||id::text) AS libelle
            FROM users_app WHERE is_active = TRUE ORDER BY libelle
        """)
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        return [(int(r['id']), str(r['libelle'])) for r in rows]
    except Exception:
        return []


def get_categories():
    """Catégories existantes (pour autocomplétion C1=A)."""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT DISTINCT categorie FROM crm_neg_clients
            WHERE categorie IS NOT NULL AND TRIM(categorie) <> '' ORDER BY categorie
        """)
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        return [r['categorie'] for r in rows]
    except Exception:
        return []


def get_pays_list():
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT DISTINCT pays FROM crm_neg_clients
            WHERE pays IS NOT NULL AND TRIM(pays) <> '' ORDER BY pays
        """)
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        return [r['pays'] for r in rows]
    except Exception:
        return []


def get_referents_list():
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT DISTINCT referent_interne FROM crm_neg_clients
            WHERE referent_interne IS NOT NULL AND TRIM(referent_interne) <> ''
            ORDER BY referent_interne
        """)
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        return [r['referent_interne'] for r in rows]
    except Exception:
        return []


def get_fonctions():
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, code, libelle FROM crm_neg_fonctions WHERE is_active = TRUE ORDER BY id")
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        return [(int(r['id']), r['code'], r['libelle']) for r in rows]
    except Exception:
        return []


def get_clients(filtres=None):
    filtres = filtres or {}
    try:
        conn = get_connection()
        cursor = conn.cursor()
        query = """
            SELECT c.id, c.code_client, c.raison_sociale, c.categorie, c.langue,
                   c.pays, c.ville, c.referent_interne, c.is_active,
                   COALESCE(u.prenom||' '||u.nom, c.referent_interne) AS referent_aff,
                   (SELECT COUNT(*) FROM crm_neg_contacts ct WHERE ct.client_id = c.id AND ct.is_active) AS nb_contacts
            FROM crm_neg_clients c
            LEFT JOIN users_app u ON c.referent_user_id = u.id
            WHERE 1=1
        """
        params = []
        if not filtres.get('inclure_inactifs'):
            query += " AND c.is_active = TRUE"
        if filtres.get('categorie') and filtres['categorie'] != '— Toutes —':
            query += " AND c.categorie = %s"
            params.append(filtres['categorie'])
        if filtres.get('pays') and filtres['pays'] != '— Tous —':
            query += " AND c.pays = %s"
            params.append(filtres['pays'])
        if filtres.get('referent') and filtres['referent'] != '— Tous —':
            query += " AND c.referent_interne = %s"
            params.append(filtres['referent'])
        if filtres.get('langue') and filtres['langue'] != '— Toutes —':
            query += " AND c.langue = %s"
            params.append(filtres['langue'])
        if filtres.get('recherche'):
            query += " AND (c.code_client ILIKE %s OR c.raison_sociale ILIKE %s)"
            like = f"%{filtres['recherche']}%"
            params.extend([like, like])
        query += " ORDER BY c.code_client"
        cursor.execute(query, tuple(params))
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        return _df(rows)
    except Exception as e:
        st.error(f"❌ Erreur get_clients : {e}")
        return pd.DataFrame()


def get_client(client_id):
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT c.*, COALESCE(u.prenom||' '||u.nom, c.referent_interne) AS referent_aff
            FROM crm_neg_clients c
            LEFT JOIN users_app u ON c.referent_user_id = u.id
            WHERE c.id = %s
        """, (int(client_id),))
        row = cursor.fetchone()
        cursor.close()
        conn.close()
        return dict(row) if row else None
    except Exception:
        return None


def get_langues_list():
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT DISTINCT langue FROM crm_neg_clients
            WHERE langue IS NOT NULL AND TRIM(langue) <> '' ORDER BY langue
        """)
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        return [r['langue'] for r in rows]
    except Exception:
        return []


def create_client(data):
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO crm_neg_clients (
                code_client, raison_sociale, categorie, langue, siret, tva,
                montant_assurance_credit, conditions_paiement, telephone, email,
                pays, ville, code_postal, adresse_facturation, adresse_depot,
                referent_interne, referent_user_id, debut_campagne, notes, created_by
            ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            RETURNING id
        """, (
            data['code_client'], data.get('raison_sociale'), data.get('categorie') or 'PROSPECT',
            data.get('langue'), data.get('siret'), data.get('tva'),
            float(data['montant_assurance_credit']) if data.get('montant_assurance_credit') else None,
            data.get('conditions_paiement'), data.get('telephone'), data.get('email'),
            data.get('pays'), data.get('ville'), data.get('code_postal'),
            data.get('adresse_facturation'), data.get('adresse_depot'),
            data.get('referent_interne'),
            int(data['referent_user_id']) if data.get('referent_user_id') else None,
            data.get('debut_campagne'), data.get('notes'),
            st.session_state.get('username', 'system')
        ))
        new_id = cursor.fetchone()['id']
        conn.commit()
        cursor.close()
        conn.close()
        return True, f"✅ Client #{new_id} créé", new_id
    except Exception as e:
        if 'conn' in locals():
            conn.rollback()
        return False, f"❌ Erreur : {e}", None


def update_client(client_id, data):
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE crm_neg_clients SET
                raison_sociale=%s, categorie=%s, langue=%s, siret=%s, tva=%s,
                montant_assurance_credit=%s, conditions_paiement=%s, telephone=%s, email=%s,
                pays=%s, ville=%s, code_postal=%s, adresse_facturation=%s, adresse_depot=%s,
                referent_interne=%s, referent_user_id=%s, debut_campagne=%s, notes=%s,
                updated_at=CURRENT_TIMESTAMP
            WHERE id=%s
        """, (
            data.get('raison_sociale'), data.get('categorie'), data.get('langue'),
            data.get('siret'), data.get('tva'),
            float(data['montant_assurance_credit']) if data.get('montant_assurance_credit') else None,
            data.get('conditions_paiement'), data.get('telephone'), data.get('email'),
            data.get('pays'), data.get('ville'), data.get('code_postal'),
            data.get('adresse_facturation'), data.get('adresse_depot'),
            data.get('referent_interne'),
            int(data['referent_user_id']) if data.get('referent_user_id') else None,
            data.get('debut_campagne'), data.get('notes'), int(client_id)
        ))
        conn.commit()
        cursor.close()
        conn.close()
        return True, "✅ Client mis à jour"
    except Exception as e:
        if 'conn' in locals():
            conn.rollback()
        return False, f"❌ Erreur : {e}"


def desactiver_client(client_id):
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE crm_neg_clients SET is_active=FALSE WHERE id=%s", (int(client_id),))
        conn.commit()
        cursor.close()
        conn.close()
        return True, "✅ Client désactivé"
    except Exception as e:
        if 'conn' in locals():
            conn.rollback()
        return False, f"❌ Erreur : {e}"


def get_contacts(client_id):
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT ct.id, ct.nom, ct.prenom, ct.telephone, ct.email, ct.is_principal,
                   ct.notes, f.libelle AS fonction, f.code AS fonction_code, ct.fonction_id
            FROM crm_neg_contacts ct
            LEFT JOIN crm_neg_fonctions f ON ct.fonction_id = f.id
            WHERE ct.client_id = %s AND ct.is_active = TRUE
            ORDER BY ct.is_principal DESC, f.id, ct.nom
        """, (int(client_id),))
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        return _df(rows)
    except Exception:
        return pd.DataFrame()


def create_contact(data):
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO crm_neg_contacts
                (client_id, nom, prenom, fonction_id, telephone, email, is_principal, notes, created_by)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, (
            int(data['client_id']), data.get('nom'), data.get('prenom'),
            int(data['fonction_id']) if data.get('fonction_id') else None,
            data.get('telephone'), data.get('email'),
            bool(data.get('is_principal')), data.get('notes'),
            st.session_state.get('username', 'system')
        ))
        conn.commit()
        cursor.close()
        conn.close()
        return True, "✅ Contact ajouté"
    except Exception as e:
        if 'conn' in locals():
            conn.rollback()
        return False, f"❌ Erreur : {e}"


def supprimer_contact(contact_id):
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE crm_neg_contacts SET is_active=FALSE WHERE id=%s", (int(contact_id),))
        conn.commit()
        cursor.close()
        conn.close()
        return True, "✅ Contact supprimé"
    except Exception as e:
        if 'conn' in locals():
            conn.rollback()
        return False, f"❌ Erreur : {e}"


def get_interactions(client_id=None, limit=200):
    """Interactions d'un client, ou toutes (vue transversale) si client_id None."""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        if client_id:
            cursor.execute("""
                SELECT i.id, i.date_interaction, i.type_interaction, i.commentaire,
                       ct.nom AS contact_nom, ct.prenom AS contact_prenom
                FROM crm_neg_interactions i
                LEFT JOIN crm_neg_contacts ct ON i.contact_id = ct.id
                WHERE i.client_id = %s
                ORDER BY i.date_interaction DESC, i.id DESC
            """, (int(client_id),))
        else:
            cursor.execute("""
                SELECT i.id, i.date_interaction, i.type_interaction, i.commentaire,
                       c.code_client, c.raison_sociale,
                       ct.nom AS contact_nom, ct.prenom AS contact_prenom
                FROM crm_neg_interactions i
                JOIN crm_neg_clients c ON i.client_id = c.id
                LEFT JOIN crm_neg_contacts ct ON i.contact_id = ct.id
                ORDER BY i.date_interaction DESC, i.id DESC
                LIMIT %s
            """, (int(limit),))
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        return _df(rows)
    except Exception:
        return pd.DataFrame()


def create_interaction(data):
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO crm_neg_interactions
                (client_id, contact_id, date_interaction, type_interaction, commentaire, created_by)
            VALUES (%s,%s,%s,%s,%s,%s)
        """, (
            int(data['client_id']),
            int(data['contact_id']) if data.get('contact_id') else None,
            data['date_interaction'], data.get('type_interaction') or 'SUIVI',
            data.get('commentaire'), st.session_state.get('username', 'system')
        ))
        conn.commit()
        cursor.close()
        conn.close()
        return True, "✅ Interaction enregistrée"
    except Exception as e:
        if 'conn' in locals():
            conn.rollback()
        return False, f"❌ Erreur : {e}"


# ============================================================
# ONGLETS PRINCIPAUX
# ============================================================
tab_clients, tab_inter = st.tabs(["🏢 Clients & Contacts", "📜 Interactions (vue globale)"])

# ------------------------------------------------------------
# ONGLET 1 — CLIENTS (master-détail) + contacts + interactions client
# ------------------------------------------------------------
with tab_clients:
    col_liste, col_detail = st.columns([1, 2])

    # ----- COLONNE GAUCHE : filtres + liste -----
    with col_liste:
        st.markdown("#### 🔎 Filtres")
        cats = ['— Toutes —'] + get_categories()
        f_cat = st.selectbox("Catégorie", cats, key="f_cat_neg")
        pays_opts = ['— Tous —'] + get_pays_list()
        f_pays = st.selectbox("Pays", pays_opts, key="f_pays_neg")
        ref_opts = ['— Tous —'] + get_referents_list()
        f_ref = st.selectbox("Référent", ref_opts, key="f_ref_neg")
        lang_opts = ['— Toutes —'] + get_langues_list()
        f_lang = st.selectbox("Langue", lang_opts, key="f_lang_neg")
        f_search = st.text_input("Recherche (code / nom)", key="f_search_neg")
        f_inact = st.checkbox("Inclure inactifs", value=False, key="f_inact_neg")

        df_clients = get_clients({
            'categorie': f_cat, 'pays': f_pays, 'referent': f_ref, 'langue': f_lang,
            'recherche': f_search, 'inclure_inactifs': f_inact
        })
        st.markdown(f"**{len(df_clients)} client(s)**")

        if df_clients.empty:
            st.info("Aucun client.")
        else:
            for _, c in df_clients.iterrows():
                sel = st.session_state.get('neg_client_sel') == int(c['id'])
                label = f"{c['code_client']} — {c['raison_sociale'] or '—'}"
                meta = f"{c['categorie'] or '—'} · {c['pays'] or '—'} · 👤{int(c['nb_contacts'])}"
                if st.button(f"{label}\n\n{meta}", key=f"selc_{c['id']}",
                             use_container_width=True,
                             type="primary" if sel else "secondary"):
                    st.session_state['neg_client_sel'] = int(c['id'])
                    st.session_state.pop('neg_edit_mode', None)
                    st.rerun()

        st.markdown("---")
        if CAN_EDIT and st.button("➕ Nouveau client", use_container_width=True, key="btn_new_client"):
            st.session_state['neg_client_sel'] = 'NEW'
            st.session_state.pop('neg_edit_mode', None)
            st.rerun()

    # ----- COLONNE DROITE : fiche détail -----
    with col_detail:
        sel = st.session_state.get('neg_client_sel')

        # --- Création d'un nouveau client ---
        if sel == 'NEW':
            st.markdown("### ➕ Nouveau client négoce")
            if st.session_state.get('neg_create_msg'):
                st.success(st.session_state.pop('neg_create_msg'))
            cc1, cc2 = st.columns(2)
            with cc1:
                nc_code = st.text_input("Code client *", key="nc_code")
                nc_rs = st.text_input("Raison sociale", key="nc_rs")
                # Catégorie : champ libre avec autocomplétion (C1=A)
                nc_cat = st.text_input("Catégorie", value="PROSPECT", key="nc_cat",
                                       help="Catégories existantes : " + ", ".join(get_categories()[:10]))
                nc_lang = st.text_input("Langue", key="nc_lang")
                nc_pays = st.text_input("Pays", key="nc_pays")
                nc_ville = st.text_input("Ville", key="nc_ville")
                nc_cp = st.text_input("Code postal", key="nc_cp")
            with cc2:
                nc_tva = st.text_input("N° TVA", key="nc_tva")
                nc_siret = st.text_input("SIRET", key="nc_siret")
                nc_assur = st.number_input("Montant assurance crédit (€)", min_value=0.0,
                                           value=0.0, step=1000.0, key="nc_assur")
                nc_cond = st.text_input("Conditions de paiement", key="nc_cond")
                nc_tel = st.text_input("Téléphone", key="nc_tel")
                nc_email = st.text_input("Email", key="nc_email")
                users = get_users()
                ref_opts2 = [(None, '— Aucun —')] + [(u[0], u[1]) for u in users]
                nc_ref = st.selectbox("Référent interne", ref_opts2,
                                      format_func=lambda x: x[1], key="nc_ref")
            nc_campagne = st.text_input("Début de campagne", key="nc_campagne",
                                        placeholder="ex : Commencera Debut Sept")
            nc_adr_f = st.text_area("Adresse de facturation", key="nc_adrf", height=60)
            nc_adr_d = st.text_area("Adresse de dépôt", key="nc_adrd", height=60)
            nc_notes = st.text_area("Notes", key="nc_notes", height=60)

            is_creating = st.session_state.get('is_creating_client', False)
            colb1, colb2 = st.columns([1, 1])
            with colb1:
                if st.button("✅ Créer le client", type="primary", key="btn_create_client",
                             disabled=is_creating):
                    if not nc_code.strip():
                        st.error("Le code client est obligatoire.")
                    else:
                        st.session_state['is_creating_client'] = True
                        ok, msg, new_id = create_client({
                            'code_client': nc_code.strip(),
                            'raison_sociale': nc_rs.strip() or None,
                            'categorie': nc_cat.strip() or 'PROSPECT',
                            'langue': nc_lang.strip() or None,
                            'siret': nc_siret.strip() or None,
                            'tva': nc_tva.strip() or None,
                            'montant_assurance_credit': nc_assur if nc_assur > 0 else None,
                            'conditions_paiement': nc_cond.strip() or None,
                            'telephone': nc_tel.strip() or None,
                            'email': nc_email.strip() or None,
                            'pays': nc_pays.strip() or None,
                            'ville': nc_ville.strip() or None,
                            'code_postal': nc_cp.strip() or None,
                            'adresse_facturation': nc_adr_f.strip() or None,
                            'adresse_depot': nc_adr_d.strip() or None,
                            'referent_interne': nc_ref[1] if nc_ref[0] else None,
                            'referent_user_id': nc_ref[0],
                            'debut_campagne': nc_campagne.strip() or None,
                            'notes': nc_notes.strip() or None,
                        })
                        st.session_state.pop('is_creating_client', None)
                        if ok:
                            for k in list(st.session_state.keys()):
                                if k.startswith('nc_'):
                                    st.session_state.pop(k, None)
                            st.session_state['neg_client_sel'] = new_id
                            st.session_state['neg_detail_msg'] = msg
                            st.rerun()
                        else:
                            st.error(msg)
            with colb2:
                if st.button("✖ Annuler", key="btn_cancel_create"):
                    st.session_state.pop('neg_client_sel', None)
                    st.rerun()

        # --- Aucun client sélectionné ---
        elif not sel:
            st.info("👈 Sélectionne un client dans la liste, ou crée-en un nouveau.")

        # --- Fiche d'un client existant ---
        else:
            client = get_client(sel)
            if not client:
                st.error("Client introuvable.")
            else:
                if st.session_state.get('neg_detail_msg'):
                    st.success(st.session_state.pop('neg_detail_msg'))

                statut_badge = "" if client['is_active'] else " 🔴 INACTIF"
                st.markdown(
                    f'<div class="fiche-head"><strong>🏢 {client["raison_sociale"] or client["code_client"]}</strong>{statut_badge}'
                    f'<br><span class="badge-cat">{client["categorie"] or "—"}</span> '
                    f'&nbsp; Code : {client["code_client"]} '
                    f'&nbsp; | &nbsp; {client["pays"] or "—"} '
                    f'&nbsp; | &nbsp; Référent : {client["referent_aff"] or "—"}</div>',
                    unsafe_allow_html=True
                )

                sub_fiche, sub_contacts, sub_inter = st.tabs(
                    ["📋 Fiche", "👥 Contacts", "📜 Interactions"])

                # === SOUS-ONGLET FICHE ===
                with sub_fiche:
                    edit_mode = st.session_state.get('neg_edit_mode') == int(sel)
                    if not edit_mode:
                        d1, d2 = st.columns(2)
                        with d1:
                            st.markdown(f"**Raison sociale :** {client['raison_sociale'] or '—'}")
                            st.markdown(f"**Catégorie :** {client['categorie'] or '—'}")
                            st.markdown(f"**Langue :** {client['langue'] or '—'}")
                            st.markdown(f"**Pays / Ville :** {client['pays'] or '—'} / {client['ville'] or '—'}")
                            st.markdown(f"**Code postal :** {client['code_postal'] or '—'}")
                            st.markdown(f"**Téléphone :** {client['telephone'] or '—'}")
                            st.markdown(f"**Email :** {client['email'] or '—'}")
                        with d2:
                            st.markdown(f"**N° TVA :** {client['tva'] or '—'}")
                            st.markdown(f"**SIRET :** {client['siret'] or '—'}")
                            assur = client['montant_assurance_credit']
                            st.markdown(f"**Assurance crédit :** {('%.0f €' % float(assur)) if assur else '—'}")
                            st.markdown(f"**Conditions paiement :** {client['conditions_paiement'] or '—'}")
                            st.markdown(f"**Référent :** {client['referent_aff'] or '—'}")
                            st.markdown(f"**Début campagne :** {client['debut_campagne'] or '—'}")
                        if client['adresse_facturation']:
                            st.markdown(f"**Adresse facturation :** {client['adresse_facturation']}")
                        if client['adresse_depot']:
                            st.markdown(f"**Adresse dépôt :** {client['adresse_depot']}")
                        if client['notes']:
                            st.info(f"📝 {client['notes']}")

                        ca, cb, _ = st.columns([1, 1, 2])
                        with ca:
                            if CAN_EDIT and st.button("✏️ Modifier", key="btn_edit_client"):
                                st.session_state['neg_edit_mode'] = int(sel)
                                st.rerun()
                        with cb:
                            if CAN_DELETE and client['is_active'] and st.button(
                                    "🗑️ Désactiver", key="btn_deact_client"):
                                ok, msg = desactiver_client(sel)
                                st.session_state['neg_detail_msg'] = msg
                                st.rerun()
                    else:
                        # Mode édition
                        e1, e2 = st.columns(2)
                        with e1:
                            e_rs = st.text_input("Raison sociale", value=client['raison_sociale'] or '', key="e_rs")
                            e_cat = st.text_input("Catégorie", value=client['categorie'] or '', key="e_cat",
                                                  help="Existantes : " + ", ".join(get_categories()[:10]))
                            e_lang = st.text_input("Langue", value=client['langue'] or '', key="e_lang")
                            e_pays = st.text_input("Pays", value=client['pays'] or '', key="e_pays")
                            e_ville = st.text_input("Ville", value=client['ville'] or '', key="e_ville")
                            e_cp = st.text_input("Code postal", value=client['code_postal'] or '', key="e_cp")
                            e_tel = st.text_input("Téléphone", value=client['telephone'] or '', key="e_tel")
                            e_email = st.text_input("Email", value=client['email'] or '', key="e_email")
                        with e2:
                            e_tva = st.text_input("N° TVA", value=client['tva'] or '', key="e_tva")
                            e_siret = st.text_input("SIRET", value=client['siret'] or '', key="e_siret")
                            e_assur = st.number_input("Assurance crédit (€)", min_value=0.0,
                                                      value=float(client['montant_assurance_credit'] or 0),
                                                      step=1000.0, key="e_assur")
                            e_cond = st.text_input("Conditions paiement",
                                                   value=client['conditions_paiement'] or '', key="e_cond")
                            users = get_users()
                            ref_opts2 = [(None, '— Aucun —')] + [(u[0], u[1]) for u in users]
                            cur_ref_idx = 0
                            for idx, o in enumerate(ref_opts2):
                                if o[0] == client['referent_user_id']:
                                    cur_ref_idx = idx
                                    break
                            e_ref = st.selectbox("Référent interne", ref_opts2,
                                                 index=cur_ref_idx,
                                                 format_func=lambda x: x[1], key="e_ref")
                            e_campagne = st.text_input("Début campagne",
                                                       value=client['debut_campagne'] or '', key="e_campagne")
                        e_adrf = st.text_area("Adresse facturation",
                                              value=client['adresse_facturation'] or '', key="e_adrf", height=60)
                        e_adrd = st.text_area("Adresse dépôt",
                                              value=client['adresse_depot'] or '', key="e_adrd", height=60)
                        e_notes = st.text_area("Notes", value=client['notes'] or '', key="e_notes", height=60)

                        se1, se2, _ = st.columns([1, 1, 2])
                        with se1:
                            if st.button("💾 Enregistrer", type="primary", key="btn_save_client"):
                                ok, msg = update_client(sel, {
                                    'raison_sociale': e_rs.strip() or None,
                                    'categorie': e_cat.strip() or None,
                                    'langue': e_lang.strip() or None,
                                    'siret': e_siret.strip() or None,
                                    'tva': e_tva.strip() or None,
                                    'montant_assurance_credit': e_assur if e_assur > 0 else None,
                                    'conditions_paiement': e_cond.strip() or None,
                                    'telephone': e_tel.strip() or None,
                                    'email': e_email.strip() or None,
                                    'pays': e_pays.strip() or None,
                                    'ville': e_ville.strip() or None,
                                    'code_postal': e_cp.strip() or None,
                                    'adresse_facturation': e_adrf.strip() or None,
                                    'adresse_depot': e_adrd.strip() or None,
                                    'referent_interne': e_ref[1] if e_ref[0] else None,
                                    'referent_user_id': e_ref[0],
                                    'debut_campagne': e_campagne.strip() or None,
                                    'notes': e_notes.strip() or None,
                                })
                                if ok:
                                    st.session_state.pop('neg_edit_mode', None)
                                    st.session_state['neg_detail_msg'] = msg
                                    st.rerun()
                                else:
                                    st.error(msg)
                        with se2:
                            if st.button("✖ Annuler", key="btn_cancel_edit"):
                                st.session_state.pop('neg_edit_mode', None)
                                st.rerun()

                # === SOUS-ONGLET CONTACTS ===
                with sub_contacts:
                    df_ct = get_contacts(sel)
                    if df_ct.empty:
                        st.caption("Aucun contact pour ce client.")
                    else:
                        for _, ct in df_ct.iterrows():
                            princ = "⭐ " if ct['is_principal'] else ""
                            nom_complet = f"{ct['prenom'] or ''} {ct['nom'] or ''}".strip() or '—'
                            cca, ccb = st.columns([5, 1])
                            with cca:
                                st.markdown(
                                    f"{princ}**{nom_complet}** — _{ct['fonction'] or '—'}_  \n"
                                    f"📞 {ct['telephone'] or '—'} &nbsp; ✉️ {ct['email'] or '—'}")
                            with ccb:
                                if CAN_DELETE and st.button("🗑️", key=f"delct_{ct['id']}"):
                                    ok, msg = supprimer_contact(ct['id'])
                                    st.toast(msg, icon="✅" if ok else "❌")
                                    st.rerun()
                            st.markdown("<hr style='margin:0.2rem 0;'>", unsafe_allow_html=True)

                    if CAN_EDIT:
                        with st.expander("➕ Ajouter un contact"):
                            fonctions = get_fonctions()
                            fct_opts = [(None, '— Fonction —')] + [(f[0], f"{f[2]}") for f in fonctions]
                            nct1, nct2 = st.columns(2)
                            with nct1:
                                nct_prenom = st.text_input("Prénom", key="nct_prenom")
                                nct_nom = st.text_input("Nom", key="nct_nom")
                                nct_fct = st.selectbox("Fonction", fct_opts,
                                                       format_func=lambda x: x[1], key="nct_fct")
                            with nct2:
                                nct_tel = st.text_input("Téléphone", key="nct_tel")
                                nct_email = st.text_input("Email", key="nct_email")
                                nct_princ = st.checkbox("Contact principal", key="nct_princ")
                            if st.button("✅ Ajouter le contact", key="btn_add_ct", type="primary"):
                                if not (nct_nom.strip() or nct_prenom.strip()):
                                    st.error("Renseigne au moins un nom ou prénom.")
                                else:
                                    ok, msg = create_contact({
                                        'client_id': sel,
                                        'nom': nct_nom.strip() or None,
                                        'prenom': nct_prenom.strip() or None,
                                        'fonction_id': nct_fct[0],
                                        'telephone': nct_tel.strip() or None,
                                        'email': nct_email.strip() or None,
                                        'is_principal': nct_princ,
                                    })
                                    if ok:
                                        for k in list(st.session_state.keys()):
                                            if k.startswith('nct_'):
                                                st.session_state.pop(k, None)
                                        st.toast(msg, icon="✅")
                                        st.rerun()
                                    else:
                                        st.error(msg)

                # === SOUS-ONGLET INTERACTIONS (du client) ===
                with sub_inter:
                    if CAN_EDIT:
                        with st.expander("➕ Nouvelle interaction", expanded=False):
                            df_ct_i = get_contacts(sel)
                            ct_opts = [(None, '— Aucun contact précis —')]
                            if not df_ct_i.empty:
                                for _, ct in df_ct_i.iterrows():
                                    nom = f"{ct['prenom'] or ''} {ct['nom'] or ''}".strip() or '—'
                                    ct_opts.append((int(ct['id']), nom))
                            ni1, ni2 = st.columns(2)
                            with ni1:
                                ni_date = st.date_input("Date", value=date.today(), key="ni_date")
                                ni_type = st.selectbox("Type", TYPES_INTERACTION, key="ni_type")
                            with ni2:
                                ni_contact = st.selectbox("Contact lié", ct_opts,
                                                          format_func=lambda x: x[1], key="ni_contact")
                                ni_type_libre = st.text_input("Ou type libre (optionnel)", key="ni_type_libre")
                            ni_comm = st.text_area("Commentaire", key="ni_comm", height=80)
                            if st.button("✅ Enregistrer l'interaction", key="btn_add_inter", type="primary"):
                                ok, msg = create_interaction({
                                    'client_id': sel,
                                    'contact_id': ni_contact[0],
                                    'date_interaction': ni_date,
                                    'type_interaction': (ni_type_libre.strip() or ni_type),
                                    'commentaire': ni_comm.strip() or None,
                                })
                                if ok:
                                    for k in list(st.session_state.keys()):
                                        if k.startswith('ni_'):
                                            st.session_state.pop(k, None)
                                    st.toast(msg, icon="✅")
                                    st.rerun()
                                else:
                                    st.error(msg)

                    df_i = get_interactions(sel)
                    if df_i.empty:
                        st.caption("Aucune interaction enregistrée.")
                    else:
                        for _, it in df_i.iterrows():
                            d_aff = pd.to_datetime(it['date_interaction']).strftime('%d/%m/%Y')
                            contact_aff = ""
                            if it.get('contact_nom') or it.get('contact_prenom'):
                                contact_aff = f" · 👤 {(it.get('contact_prenom') or '')} {(it.get('contact_nom') or '')}".rstrip()
                            comm = it['commentaire'] or ''
                            st.markdown(
                                f'<div class="inter-row"><strong>{d_aff}</strong> '
                                f'<span class="badge-cat">{it["type_interaction"]}</span>{contact_aff}'
                                f'<br>{comm}</div>',
                                unsafe_allow_html=True)

# ------------------------------------------------------------
# ONGLET 2 — INTERACTIONS (vue transversale)
# ------------------------------------------------------------
with tab_inter:
    st.markdown("#### 📜 Toutes les interactions (200 dernières)")
    df_all = get_interactions(None, limit=200)
    if df_all.empty:
        st.info("Aucune interaction enregistrée.")
    else:
        types_dispo = ['— Tous —'] + sorted(df_all['type_interaction'].dropna().unique().tolist())
        fi_type = st.selectbox("Filtrer par type", types_dispo, key="fi_type_glob")
        df_show = df_all.copy()
        if fi_type != '— Tous —':
            df_show = df_show[df_show['type_interaction'] == fi_type]
        df_show['date_interaction'] = pd.to_datetime(df_show['date_interaction']).dt.strftime('%d/%m/%Y')
        df_show['client'] = df_show['code_client'].astype(str) + ' — ' + df_show['raison_sociale'].fillna('—')
        cols = ['date_interaction', 'type_interaction', 'client', 'commentaire']
        st.dataframe(df_show[cols].rename(columns={
            'date_interaction': 'Date', 'type_interaction': 'Type',
            'client': 'Client', 'commentaire': 'Commentaire'
        }), use_container_width=True, hide_index=True)

show_footer()
