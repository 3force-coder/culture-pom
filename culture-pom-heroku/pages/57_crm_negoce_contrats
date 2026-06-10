# pages/57_CRM_Negoce_Contrats.py
# CRM Négoce-Export — Contrats de vente
# Tables : crm_neg_contrats, crm_neg_clients, crm_neg_propositions, ref_varietes, ref_producteurs
# Pattern POMI : RealDictCursor, requêtes paramétrées, pas de st.form, types natifs.

import streamlit as st
import pandas as pd
from datetime import datetime, date

from database import get_connection
from components import show_footer
from auth import require_access, can_edit, can_delete

st.set_page_config(page_title="CRM Négoce - Contrats", page_icon="🌍", layout="wide")

st.markdown("""
<style>
.block-container {padding-top:1.5rem!important;padding-bottom:0.5rem!important;
    padding-left:2rem!important;padding-right:2rem!important;}
h1,h2,h3,h4{margin-top:0.3rem!important;margin-bottom:0.3rem!important;}
[data-testid="stMetricValue"]{font-size:1.3rem!important;}
hr{margin-top:0.5rem!important;margin-bottom:0.5rem!important;}
.ct-brouillon {background:#fafafa;border-left:4px solid #9e9e9e;padding:0.5rem 0.9rem;border-radius:4px;margin:0.25rem 0;}
.ct-signe {background:#e8f5e9;border-left:4px solid #4caf50;padding:0.5rem 0.9rem;border-radius:4px;margin:0.25rem 0;}
.ct-solde {background:#e3f2fd;border-left:4px solid #1565c0;padding:0.5rem 0.9rem;border-radius:4px;margin:0.25rem 0;}
.badge {display:inline-block;padding:1px 8px;border-radius:10px;font-size:0.72rem;font-weight:600;background:#eee;}
</style>
""", unsafe_allow_html=True)

require_access("CRM_NEGOCE")
CAN_EDIT = can_edit("CRM_NEGOCE")
CAN_DELETE = can_delete("CRM_NEGOCE")

STATUTS_CONTRAT = ['BROUILLON', 'SIGNE', 'SOLDE']
CSS_STATUT = {'BROUILLON': 'ct-brouillon', 'SIGNE': 'ct-signe', 'SOLDE': 'ct-solde'}

st.title("🌍 CRM Négoce — Contrats de vente")
st.markdown("*Contrats de vente clients (saisie manuelle ou issus d'une proposition)*")
st.markdown("---")


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


def get_contrats(filtres=None):
    filtres = filtres or {}
    try:
        conn = get_connection()
        cursor = conn.cursor()
        query = """
            SELECT ct.id, ct.reference, ct.volume_t, ct.prix_eur_t, ct.calibre,
                   ct.periode_campagne, ct.statut, ct.proposition_id, ct.notes,
                   c.code_client, c.raison_sociale,
                   COALESCE(v.nom_variete, v.code_variete) AS variete,
                   COALESCE(pr.nom, pr.code_producteur) AS producteur
            FROM crm_neg_contrats ct
            JOIN crm_neg_clients c ON ct.client_id = c.id
            LEFT JOIN ref_varietes v ON ct.variete_id = v.id
            LEFT JOIN ref_producteurs pr ON ct.producteur_id = pr.id
            WHERE ct.is_active = TRUE
        """
        params = []
        if filtres.get('statut') and filtres['statut'] != '— Tous —':
            query += " AND ct.statut = %s"
            params.append(filtres['statut'])
        if filtres.get('client_id') and filtres['client_id'] != 0:
            query += " AND ct.client_id = %s"
            params.append(int(filtres['client_id']))
        query += " ORDER BY ct.id DESC"
        cursor.execute(query, tuple(params))
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        return _df(rows)
    except Exception as e:
        st.error(f"❌ Erreur get_contrats : {e}")
        return pd.DataFrame()


def get_contrat(contrat_id):
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM crm_neg_contrats WHERE id = %s", (int(contrat_id),))
        row = cursor.fetchone()
        cursor.close()
        conn.close()
        return dict(row) if row else None
    except Exception:
        return None


def create_contrat(data):
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO crm_neg_contrats
                (reference, client_id, variete_id, producteur_id, volume_t, prix_eur_t,
                 calibre, periode_campagne, statut, notes, created_by)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id
        """, (
            data.get('reference'),
            int(data['client_id']),
            int(data['variete_id']) if data.get('variete_id') else None,
            int(data['producteur_id']) if data.get('producteur_id') else None,
            float(data['volume_t']) if data.get('volume_t') else None,
            float(data['prix_eur_t']) if data.get('prix_eur_t') else None,
            data.get('calibre'), data.get('periode_campagne'),
            data.get('statut') or 'BROUILLON', data.get('notes'),
            st.session_state.get('username', 'system')
        ))
        new_id = cursor.fetchone()['id']
        conn.commit()
        cursor.close()
        conn.close()
        return True, f"✅ Contrat #{new_id} créé"
    except Exception as e:
        if 'conn' in locals():
            conn.rollback()
        return False, f"❌ Erreur : {e}"


def update_contrat(contrat_id, data):
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE crm_neg_contrats SET
                reference=%s, variete_id=%s, producteur_id=%s, volume_t=%s, prix_eur_t=%s,
                calibre=%s, periode_campagne=%s, statut=%s, notes=%s, updated_at=CURRENT_TIMESTAMP
            WHERE id=%s
        """, (
            data.get('reference'),
            int(data['variete_id']) if data.get('variete_id') else None,
            int(data['producteur_id']) if data.get('producteur_id') else None,
            float(data['volume_t']) if data.get('volume_t') else None,
            float(data['prix_eur_t']) if data.get('prix_eur_t') else None,
            data.get('calibre'), data.get('periode_campagne'),
            data.get('statut'), data.get('notes'), int(contrat_id)
        ))
        conn.commit()
        cursor.close()
        conn.close()
        return True, "✅ Contrat mis à jour"
    except Exception as e:
        if 'conn' in locals():
            conn.rollback()
        return False, f"❌ Erreur : {e}"


def update_statut_contrat(contrat_id, statut):
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE crm_neg_contrats SET statut=%s, updated_at=CURRENT_TIMESTAMP WHERE id=%s",
                       (statut, int(contrat_id)))
        conn.commit()
        cursor.close()
        conn.close()
        return True, f"✅ Statut → {statut}"
    except Exception as e:
        if 'conn' in locals():
            conn.rollback()
        return False, f"❌ Erreur : {e}"


def supprimer_contrat(contrat_id):
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE crm_neg_contrats SET is_active=FALSE WHERE id=%s", (int(contrat_id),))
        conn.commit()
        cursor.close()
        conn.close()
        return True, "✅ Contrat supprimé"
    except Exception as e:
        if 'conn' in locals():
            conn.rollback()
        return False, f"❌ Erreur : {e}"


# ============================================================
# UI
# ============================================================
tab_liste, tab_creer = st.tabs(["📋 Contrats", "➕ Nouveau contrat"])

with tab_liste:
    if st.session_state.get('ct_msg'):
        st.success(st.session_state.pop('ct_msg'))

    cf1, cf2 = st.columns([1, 2])
    with cf1:
        f_statut = st.selectbox("Statut", ['— Tous —'] + STATUTS_CONTRAT, key="f_statut_ct")
    with cf2:
        clients_opts = [(0, '— Tous —')] + get_clients_opts()
        f_client = st.selectbox("Client", clients_opts, format_func=lambda x: x[1], key="f_client_ct")

    df = get_contrats({'statut': f_statut, 'client_id': f_client[0]})

    if not df.empty:
        k1, k2, k3, k4 = st.columns(4)
        k1.metric("Total", len(df))
        k2.metric("Signés", int((df['statut'] == 'SIGNE').sum()))
        k3.metric("Soldés", int((df['statut'] == 'SOLDE').sum()))
        vol = pd.to_numeric(df['volume_t'], errors='coerce').sum()
        k4.metric("Volume total", f"{vol:,.0f} T")

    st.markdown(f"**{len(df)} contrat(s)**")
    if df.empty:
        st.info("Aucun contrat.")
    else:
        edit_id = st.session_state.get('ct_edit_id')
        for _, ct in df.iterrows():
            css = CSS_STATUT.get(ct['statut'], 'ct-brouillon')
            vol = f"{float(ct['volume_t']):,.0f} T" if pd.notna(ct['volume_t']) else '—'
            prix = f"{float(ct['prix_eur_t']):,.0f} €/T" if pd.notna(ct['prix_eur_t']) else '—'
            ref = ct['reference'] or f"#{ct['id']}"
            lien_prop = f" · 💡 Prop. #{int(ct['proposition_id'])}" if pd.notna(ct['proposition_id']) else ""
            cal = f" · 📏 {ct['calibre']}" if ct['calibre'] else ""
            per = f" · 📅 {ct['periode_campagne']}" if ct['periode_campagne'] else ""
            st.markdown(
                f'<div class="{css}"><strong>{ref}</strong> — {ct["code_client"]} ({ct["raison_sociale"] or "—"})'
                f' &nbsp;<span class="badge">{ct["statut"]}</span>{lien_prop}<br>'
                f'🥔 {ct["variete"] or "—"} · 👨‍🌾 {ct["producteur"] or "—"} · {vol} · {prix}{cal}{per}</div>',
                unsafe_allow_html=True)
            if ct['notes']:
                st.caption(f"📝 {ct['notes']}")

            cols = st.columns([1, 1, 1, 1, 2])
            with cols[0]:
                if CAN_EDIT and st.button("✏️", key=f"edit_{ct['id']}", help="Modifier"):
                    st.session_state['ct_edit_id'] = int(ct['id'])
                    st.rerun()
            with cols[1]:
                if CAN_EDIT and ct['statut'] == 'BROUILLON' and st.button("✍️ Signer", key=f"sign_{ct['id']}"):
                    ok, msg = update_statut_contrat(ct['id'], 'SIGNE')
                    st.session_state['ct_msg'] = msg
                    st.rerun()
            with cols[2]:
                if CAN_EDIT and ct['statut'] == 'SIGNE' and st.button("✅ Solder", key=f"solde_{ct['id']}"):
                    ok, msg = update_statut_contrat(ct['id'], 'SOLDE')
                    st.session_state['ct_msg'] = msg
                    st.rerun()
            with cols[3]:
                if CAN_DELETE and st.button("🗑️", key=f"del_{ct['id']}", help="Supprimer"):
                    ok, msg = supprimer_contrat(ct['id'])
                    st.session_state['ct_msg'] = msg
                    st.rerun()
            st.markdown("<hr style='margin:0.2rem 0;'>", unsafe_allow_html=True)

        # --- Édition inline ---
        if edit_id:
            c = get_contrat(edit_id)
            if c:
                st.markdown("---")
                st.markdown(f"### ✏️ Modifier le contrat #{edit_id}")
                var_opts = [(None, '— Non définie —')] + get_varietes_opts()
                prod_opts = [(None, '— Non défini —')] + get_producteurs_opts()
                cur_var = next((i for i, o in enumerate(var_opts) if o[0] == c['variete_id']), 0)
                cur_prod = next((i for i, o in enumerate(prod_opts) if o[0] == c['producteur_id']), 0)
                ce1, ce2 = st.columns(2)
                with ce1:
                    e_ref = st.text_input("Référence", value=c['reference'] or '', key="e_ref_ct")
                    e_var = st.selectbox("Variété", var_opts, index=cur_var,
                                         format_func=lambda x: x[1], key="e_var_ct")
                    e_prod = st.selectbox("Producteur", prod_opts, index=cur_prod,
                                          format_func=lambda x: x[1], key="e_prod_ct")
                    e_cal = st.text_input("Calibre", value=c['calibre'] or '', key="e_cal_ct")
                with ce2:
                    e_vol = st.number_input("Volume (T)", min_value=0.0,
                                            value=float(c['volume_t'] or 0), step=1.0, key="e_vol_ct")
                    e_prix = st.number_input("Prix (€/T)", min_value=0.0,
                                             value=float(c['prix_eur_t'] or 0), step=1.0, key="e_prix_ct")
                    e_per = st.text_input("Période / campagne", value=c['periode_campagne'] or '', key="e_per_ct")
                    cur_st = STATUTS_CONTRAT.index(c['statut']) if c['statut'] in STATUTS_CONTRAT else 0
                    e_st = st.selectbox("Statut", STATUTS_CONTRAT, index=cur_st, key="e_st_ct")
                e_notes = st.text_area("Notes", value=c['notes'] or '', key="e_notes_ct", height=60)
                se1, se2, _ = st.columns([1, 1, 3])
                with se1:
                    if st.button("💾 Enregistrer", type="primary", key="btn_save_ct"):
                        ok, msg = update_contrat(edit_id, {
                            'reference': e_ref.strip() or None,
                            'variete_id': e_var[0], 'producteur_id': e_prod[0],
                            'volume_t': e_vol if e_vol > 0 else None,
                            'prix_eur_t': e_prix if e_prix > 0 else None,
                            'calibre': e_cal.strip() or None,
                            'periode_campagne': e_per.strip() or None,
                            'statut': e_st, 'notes': e_notes.strip() or None,
                        })
                        if ok:
                            st.session_state.pop('ct_edit_id', None)
                            st.session_state['ct_msg'] = msg
                            st.rerun()
                        else:
                            st.error(msg)
                with se2:
                    if st.button("✖ Annuler", key="btn_cancel_ct"):
                        st.session_state.pop('ct_edit_id', None)
                        st.rerun()

with tab_creer:
    if not CAN_EDIT:
        st.warning("⚠️ Droits insuffisants pour créer un contrat.")
    else:
        st.subheader("➕ Nouveau contrat")
        if st.session_state.get('ct_create_msg'):
            st.success(st.session_state.pop('ct_create_msg'))
            st.caption("Formulaire réinitialisé. Voir l'onglet « Contrats ».")

        clients_opts2 = get_clients_opts()
        if not clients_opts2:
            st.info("Aucun client négoce. Créez-en d'abord dans la page Clients.")
        else:
            cc1, cc2 = st.columns(2)
            with cc1:
                nc_client = st.selectbox("Client *", clients_opts2,
                                         format_func=lambda x: x[1], key="nc_client_ct")
                nc_ref = st.text_input("Référence contrat", key="nc_ref_ct",
                                       placeholder="(optionnel)")
                var_opts = [(None, '— Non définie —')] + get_varietes_opts()
                nc_var = st.selectbox("Variété", var_opts, format_func=lambda x: x[1], key="nc_var_ct")
                prod_opts = [(None, '— Non défini —')] + get_producteurs_opts()
                nc_prod = st.selectbox("Producteur", prod_opts, format_func=lambda x: x[1], key="nc_prod_ct")
            with cc2:
                nc_vol = st.number_input("Volume (T)", min_value=0.0, value=0.0, step=1.0, key="nc_vol_ct")
                nc_prix = st.number_input("Prix (€/T)", min_value=0.0, value=0.0, step=1.0, key="nc_prix_ct")
                nc_cal = st.text_input("Calibre", key="nc_cal_ct")
                nc_per = st.text_input("Période / campagne", key="nc_per_ct")
                nc_st = st.selectbox("Statut", STATUTS_CONTRAT, key="nc_st_ct")
            nc_notes = st.text_area("Notes", key="nc_notes_ct", height=70)

            is_creating = st.session_state.get('is_creating_ct', False)
            if st.button("✅ Créer le contrat", type="primary", key="btn_create_ct",
                         disabled=is_creating):
                st.session_state['is_creating_ct'] = True
                ok, msg = create_contrat({
                    'reference': nc_ref.strip() or None,
                    'client_id': nc_client[0],
                    'variete_id': nc_var[0], 'producteur_id': nc_prod[0],
                    'volume_t': nc_vol if nc_vol > 0 else None,
                    'prix_eur_t': nc_prix if nc_prix > 0 else None,
                    'calibre': nc_cal.strip() or None,
                    'periode_campagne': nc_per.strip() or None,
                    'statut': nc_st, 'notes': nc_notes.strip() or None,
                })
                st.session_state.pop('is_creating_ct', None)
                if ok:
                    for k in list(st.session_state.keys()):
                        if k.startswith('nc_') and k.endswith('_ct'):
                            st.session_state.pop(k, None)
                    st.session_state['ct_create_msg'] = msg
                    st.rerun()
                else:
                    st.error(msg)

show_footer()
