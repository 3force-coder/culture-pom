# pages/58_CRM_Negoce_Propositions.py
# CRM Négoce-Export — Propositions de vente (convertibles en contrat)
# Tables : crm_neg_propositions, crm_neg_contrats, crm_neg_clients, crm_neg_contacts,
#          ref_varietes, ref_producteurs
# Pattern POMI : RealDictCursor, requêtes paramétrées, pas de st.form, types natifs.

import streamlit as st
import pandas as pd
from datetime import datetime, date

from database import get_connection
from components import show_footer
from auth import require_access, can_edit, can_delete

st.set_page_config(page_title="CRM Négoce - Propositions", page_icon="🌍", layout="wide")

st.markdown("""
<style>
.block-container {padding-top:1.5rem!important;padding-bottom:0.5rem!important;
    padding-left:2rem!important;padding-right:2rem!important;}
h1,h2,h3,h4{margin-top:0.3rem!important;margin-bottom:0.3rem!important;}
[data-testid="stMetricValue"]{font-size:1.3rem!important;}
hr{margin-top:0.5rem!important;margin-bottom:0.5rem!important;}
.prop-emise {background:#fff8e1;border-left:4px solid #ffc107;padding:0.5rem 0.9rem;border-radius:4px;margin:0.25rem 0;}
.prop-acceptee {background:#e8f5e9;border-left:4px solid #4caf50;padding:0.5rem 0.9rem;border-radius:4px;margin:0.25rem 0;}
.prop-refusee {background:#fafafa;border-left:4px solid #9e9e9e;padding:0.5rem 0.9rem;border-radius:4px;margin:0.25rem 0;}
.prop-expiree {background:#ffebee;border-left:4px solid #f44336;padding:0.5rem 0.9rem;border-radius:4px;margin:0.25rem 0;}
.badge {display:inline-block;padding:1px 8px;border-radius:10px;font-size:0.72rem;font-weight:600;}
</style>
""", unsafe_allow_html=True)

require_access("CRM_NEGOCE")
CAN_EDIT = can_edit("CRM_NEGOCE")
CAN_DELETE = can_delete("CRM_NEGOCE")

STATUTS_PROP = ['EMISE', 'ACCEPTEE', 'REFUSEE', 'EXPIREE']
CSS_STATUT = {'EMISE': 'prop-emise', 'ACCEPTEE': 'prop-acceptee',
              'REFUSEE': 'prop-refusee', 'EXPIREE': 'prop-expiree'}

st.title("🌍 CRM Négoce — Propositions de vente")
st.markdown("*Propositions commerciales, convertibles en contrat*")
st.markdown("---")


# ============================================================
# FONCTIONS DONNÉES
# ============================================================
def _df(rows):
    return pd.DataFrame([dict(r) for r in rows]) if rows else pd.DataFrame()


def get_clients_opts():
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, code_client, raison_sociale FROM crm_neg_clients
            WHERE is_active = TRUE ORDER BY code_client
        """)
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        return [(int(r['id']), f"{r['code_client']} — {r['raison_sociale'] or '—'}") for r in rows]
    except Exception:
        return []


def get_contacts_opts(client_id):
    if not client_id:
        return []
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, COALESCE(prenom||' ','')||COALESCE(nom,'') AS nom_complet
            FROM crm_neg_contacts WHERE client_id = %s AND is_active = TRUE ORDER BY nom
        """, (int(client_id),))
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        return [(int(r['id']), (r['nom_complet'] or '—').strip()) for r in rows]
    except Exception:
        return []


def get_varietes_opts():
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, COALESCE(nom_variete, code_variete) AS nom FROM ref_varietes ORDER BY nom")
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        return [(int(r['id']), r['nom']) for r in rows]
    except Exception:
        return []


def get_producteurs_opts():
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, COALESCE(nom, code_producteur) AS nom FROM ref_producteurs
            WHERE COALESCE(is_active, TRUE) = TRUE ORDER BY nom
        """)
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        return [(int(r['id']), r['nom']) for r in rows]
    except Exception:
        return []


def get_propositions(filtres=None):
    filtres = filtres or {}
    try:
        conn = get_connection()
        cursor = conn.cursor()
        query = """
            SELECT p.id, p.date_proposition, p.volume_t, p.prix_eur_t, p.statut,
                   p.ligne_id, p.notes,
                   c.code_client, c.raison_sociale,
                   COALESCE(v.nom_variete, v.code_variete) AS variete,
                   COALESCE(pr.nom, pr.code_producteur) AS producteur,
                   COALESCE(ct.prenom||' ','')||COALESCE(ct.nom,'') AS contact
            FROM crm_neg_propositions p
            JOIN crm_neg_clients c ON p.client_id = c.id
            LEFT JOIN ref_varietes v ON p.variete_id = v.id
            LEFT JOIN ref_producteurs pr ON p.producteur_id = pr.id
            LEFT JOIN crm_neg_contacts ct ON p.contact_id = ct.id
            WHERE p.is_active = TRUE
        """
        params = []
        if filtres.get('statut') and filtres['statut'] != '— Tous —':
            query += " AND p.statut = %s"
            params.append(filtres['statut'])
        if filtres.get('client_id') and filtres['client_id'] != 0:
            query += " AND p.client_id = %s"
            params.append(int(filtres['client_id']))
        query += " ORDER BY p.date_proposition DESC, p.id DESC"
        cursor.execute(query, tuple(params))
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        return _df(rows)
    except Exception as e:
        st.error(f"❌ Erreur get_propositions : {e}")
        return pd.DataFrame()


def create_proposition(data):
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO crm_neg_propositions
                (client_id, contact_id, variete_id, producteur_id, date_proposition,
                 volume_t, prix_eur_t, statut, notes, created_by)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id
        """, (
            int(data['client_id']),
            int(data['contact_id']) if data.get('contact_id') else None,
            int(data['variete_id']) if data.get('variete_id') else None,
            int(data['producteur_id']) if data.get('producteur_id') else None,
            data['date_proposition'],
            float(data['volume_t']) if data.get('volume_t') else None,
            float(data['prix_eur_t']) if data.get('prix_eur_t') else None,
            data.get('statut') or 'EMISE',
            data.get('notes'),
            st.session_state.get('username', 'system')
        ))
        new_id = cursor.fetchone()['id']
        conn.commit()
        cursor.close()
        conn.close()
        return True, f"✅ Proposition #{new_id} créée"
    except Exception as e:
        if 'conn' in locals():
            conn.rollback()
        return False, f"❌ Erreur : {e}"


def update_statut_proposition(prop_id, statut):
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE crm_neg_propositions SET statut=%s WHERE id=%s",
                       (statut, int(prop_id)))
        conn.commit()
        cursor.close()
        conn.close()
        return True, f"✅ Statut → {statut}"
    except Exception as e:
        if 'conn' in locals():
            conn.rollback()
        return False, f"❌ Erreur : {e}"


def supprimer_proposition(prop_id):
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE crm_neg_propositions SET is_active=FALSE WHERE id=%s", (int(prop_id),))
        conn.commit()
        cursor.close()
        conn.close()
        return True, "✅ Proposition supprimée"
    except Exception as e:
        if 'conn' in locals():
            conn.rollback()
        return False, f"❌ Erreur : {e}"


def convertir_en_ligne(prop_id):
    """Crée une LIGNE autonome (statut PREVUE) depuis une proposition, lie les deux,
    et passe la proposition en ACCEPTEE. La ligne est autonome (contrat_id NULL, Q1=A).
    Mapping : volume -> volume_prevu_t, prix -> prix_eur_t, client/variété/producteur repris.
    Transaction unique."""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        # Lire la proposition
        cursor.execute("""
            SELECT client_id, variete_id, producteur_id, volume_t, prix_eur_t, ligne_id
            FROM crm_neg_propositions WHERE id = %s
        """, (int(prop_id),))
        p = cursor.fetchone()
        if not p:
            cursor.close()
            conn.close()
            return False, "Proposition introuvable", None
        if p['ligne_id']:
            cursor.close()
            conn.close()
            return False, f"Cette proposition est déjà liée à la ligne #{p['ligne_id']}", None
        # Créer la ligne autonome (contrat_id NULL)
        cursor.execute("""
            INSERT INTO crm_neg_contrat_lignes
                (contrat_id, client_id, variete_id, producteur_id, statut,
                 volume_prevu_t, prix_eur_t, notes, created_by)
            VALUES (NULL,%s,%s,%s,'PREVUE',%s,%s,%s,%s) RETURNING id
        """, (
            p['client_id'], p['variete_id'], p['producteur_id'],
            p['volume_t'], p['prix_eur_t'],
            f"Issue de la proposition #{int(prop_id)}",
            st.session_state.get('username', 'system')
        ))
        ligne_id = cursor.fetchone()['id']
        # Lier la proposition à la ligne + passer ACCEPTEE
        cursor.execute("""
            UPDATE crm_neg_propositions SET ligne_id=%s, statut='ACCEPTEE' WHERE id=%s
        """, (ligne_id, int(prop_id)))
        conn.commit()
        cursor.close()
        conn.close()
        return True, f"✅ Ligne #{ligne_id} créée depuis la proposition", ligne_id
    except Exception as e:
        if 'conn' in locals():
            conn.rollback()
        return False, f"❌ Erreur conversion : {e}", None


# ============================================================
# UI
# ============================================================
tab_liste, tab_creer = st.tabs(["📋 Propositions", "➕ Nouvelle proposition"])

# ----- LISTE -----
with tab_liste:
    if st.session_state.get('prop_msg'):
        st.success(st.session_state.pop('prop_msg'))

    cf1, cf2, cf3 = st.columns([1, 2, 2])
    with cf1:
        f_statut = st.selectbox("Statut", ['— Tous —'] + STATUTS_PROP, key="f_statut_prop")
    with cf2:
        clients_opts = [(0, '— Tous —')] + get_clients_opts()
        f_client = st.selectbox("Client", clients_opts, format_func=lambda x: x[1], key="f_client_prop")

    df = get_propositions({'statut': f_statut, 'client_id': f_client[0]})

    # KPIs
    if not df.empty:
        k1, k2, k3, k4 = st.columns(4)
        k1.metric("Total", len(df))
        k2.metric("Émises", int((df['statut'] == 'EMISE').sum()))
        k3.metric("Acceptées", int((df['statut'] == 'ACCEPTEE').sum()))
        vol = pd.to_numeric(df['volume_t'], errors='coerce').sum()
        k4.metric("Volume total", f"{vol:,.0f} T")

    st.markdown(f"**{len(df)} proposition(s)**")
    if df.empty:
        st.info("Aucune proposition.")
    else:
        for _, p in df.iterrows():
            css = CSS_STATUT.get(p['statut'], 'prop-emise')
            d_aff = pd.to_datetime(p['date_proposition']).strftime('%d/%m/%Y')
            vol = f"{float(p['volume_t']):,.0f} T" if pd.notna(p['volume_t']) else '—'
            prix = f"{float(p['prix_eur_t']):,.0f} €/T" if pd.notna(p['prix_eur_t']) else '—'
            lien_ligne = f" · 📦 Ligne #{int(p['ligne_id'])}" if pd.notna(p['ligne_id']) else ""
            st.markdown(
                f'<div class="{css}"><strong>{d_aff}</strong> — {p["code_client"]} ({p["raison_sociale"] or "—"})'
                f' &nbsp;<span class="badge" style="background:#eee">{p["statut"]}</span>{lien_ligne}<br>'
                f'🥔 {p["variete"] or "—"} · 👨‍🌾 {p["producteur"] or "—"} · {vol} · {prix}'
                f'{(" · 👤 " + p["contact"]) if p["contact"] and p["contact"].strip() else ""}</div>',
                unsafe_allow_html=True)
            if p['notes']:
                st.caption(f"📝 {p['notes']}")

            cols = st.columns([1, 1, 1, 3])
            # Conversion en ligne autonome (si pas déjà liée et statut EMISE/ACCEPTEE)
            with cols[0]:
                if CAN_EDIT and pd.isna(p['ligne_id']) and p['statut'] in ('EMISE', 'ACCEPTEE'):
                    if st.button("📦 Convertir en ligne", key=f"conv_{p['id']}",
                                 help="Créer une ligne autonome depuis cette proposition"):
                        ok, msg, lid = convertir_en_ligne(p['id'])
                        st.session_state['prop_msg'] = msg
                        st.rerun()
            with cols[1]:
                if CAN_EDIT and p['statut'] == 'EMISE':
                    if st.button("✅ Accepter", key=f"acc_{p['id']}"):
                        ok, msg = update_statut_proposition(p['id'], 'ACCEPTEE')
                        st.session_state['prop_msg'] = msg
                        st.rerun()
            with cols[2]:
                if CAN_EDIT and p['statut'] == 'EMISE':
                    if st.button("❌ Refuser", key=f"ref_{p['id']}"):
                        ok, msg = update_statut_proposition(p['id'], 'REFUSEE')
                        st.session_state['prop_msg'] = msg
                        st.rerun()
            with cols[3]:
                if CAN_DELETE:
                    if st.button("🗑️", key=f"del_{p['id']}", help="Supprimer"):
                        ok, msg = supprimer_proposition(p['id'])
                        st.session_state['prop_msg'] = msg
                        st.rerun()
            st.markdown("<hr style='margin:0.2rem 0;'>", unsafe_allow_html=True)

# ----- CRÉATION -----
with tab_creer:
    if not CAN_EDIT:
        st.warning("⚠️ Droits insuffisants pour créer une proposition.")
    else:
        st.subheader("➕ Nouvelle proposition")
        if st.session_state.get('prop_create_msg'):
            st.success(st.session_state.pop('prop_create_msg'))
            st.caption("Formulaire réinitialisé. Voir l'onglet « Propositions ».")

        clients_opts2 = get_clients_opts()
        if not clients_opts2:
            st.info("Aucun client négoce. Créez-en d'abord dans la page Clients.")
        else:
            cp1, cp2 = st.columns(2)
            with cp1:
                np_client = st.selectbox("Client *", clients_opts2,
                                         format_func=lambda x: x[1], key="np_client")
                contacts_opts = [(None, '— Aucun —')] + get_contacts_opts(np_client[0])
                np_contact = st.selectbox("Personne contactée", contacts_opts,
                                          format_func=lambda x: x[1], key="np_contact")
                var_opts = [(None, '— Non définie —')] + get_varietes_opts()
                np_var = st.selectbox("Variété", var_opts, format_func=lambda x: x[1], key="np_var")
                prod_opts = [(None, '— Non défini —')] + get_producteurs_opts()
                np_prod = st.selectbox("Producteur", prod_opts, format_func=lambda x: x[1], key="np_prod")
            with cp2:
                np_date = st.date_input("Date *", value=date.today(), key="np_date")
                np_vol = st.number_input("Volume (T)", min_value=0.0, value=0.0, step=1.0, key="np_vol")
                np_prix = st.number_input("Prix (€/T)", min_value=0.0, value=0.0, step=1.0, key="np_prix")
                np_statut = st.selectbox("Statut", STATUTS_PROP, key="np_statut")
            np_notes = st.text_area("Notes", key="np_notes", height=70)

            is_creating = st.session_state.get('is_creating_prop', False)
            if st.button("✅ Créer la proposition", type="primary", key="btn_create_prop",
                         disabled=is_creating):
                st.session_state['is_creating_prop'] = True
                ok, msg = create_proposition({
                    'client_id': np_client[0],
                    'contact_id': np_contact[0],
                    'variete_id': np_var[0],
                    'producteur_id': np_prod[0],
                    'date_proposition': np_date,
                    'volume_t': np_vol if np_vol > 0 else None,
                    'prix_eur_t': np_prix if np_prix > 0 else None,
                    'statut': np_statut,
                    'notes': np_notes.strip() or None,
                })
                st.session_state.pop('is_creating_prop', None)
                if ok:
                    for k in list(st.session_state.keys()):
                        if k.startswith('np_'):
                            st.session_state.pop(k, None)
                    st.session_state['prop_create_msg'] = msg
                    st.rerun()
                else:
                    st.error(msg)

show_footer()
