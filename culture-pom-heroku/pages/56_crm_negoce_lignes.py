# pages/56_crm_negoce_lignes.py
# CRM Négoce-Export — Lignes (vue transversale)
# Table : crm_neg_contrat_lignes (contrat_id NULLABLE : ligne autonome OU de contrat)
# Pattern POMI : RealDictCursor, requêtes paramétrées, pas de st.form, types natifs.
# Modèle v3 / A1=C : une ligne peut exister seule (sans contrat) ou être rattachée à un contrat.
#   Cette page affiche TOUTES les lignes (filtrables), permet de créer des lignes autonomes,
#   et de les éditer. Les lignes rattachées à un contrat se gèrent aussi depuis la page 57.

import streamlit as st
import pandas as pd
from datetime import datetime, date

from database import get_connection
from components import show_footer
from auth import require_access, can_edit, can_delete

st.set_page_config(page_title="CRM Négoce - Lignes", page_icon="🌍", layout="wide")

st.markdown("""
<style>
.block-container {padding-top:1.5rem!important;padding-bottom:0.5rem!important;
    padding-left:2rem!important;padding-right:2rem!important;}
h1,h2,h3,h4{margin-top:0.3rem!important;margin-bottom:0.3rem!important;}
[data-testid="stMetricValue"]{font-size:1.3rem!important;}
hr{margin-top:0.5rem!important;margin-bottom:0.5rem!important;}
.badge {display:inline-block;padding:1px 8px;border-radius:10px;font-size:0.72rem;font-weight:600;background:#eee;}
</style>
""", unsafe_allow_html=True)

require_access("CRM_NEGOCE")
CAN_EDIT = can_edit("CRM_NEGOCE")
CAN_DELETE = can_delete("CRM_NEGOCE")

STATUTS_LIGNE = ['PREVUE', 'EN_COURS', 'LIVREE', 'FERMEE']

st.title("🌍 CRM Négoce — Lignes de livraison")
st.markdown("*Vue transversale : lignes autonomes ou rattachées à un contrat*")
st.markdown("---")


def _df(rows):
    return pd.DataFrame([dict(r) for r in rows]) if rows else pd.DataFrame()


def get_clients_opts():
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, code_client, raison_sociale FROM crm_neg_clients WHERE is_active=TRUE ORDER BY code_client")
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
        cursor.execute("SELECT id, COALESCE(nom, code_producteur) AS nom FROM ref_producteurs WHERE COALESCE(is_active,TRUE)=TRUE ORDER BY nom")
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        return [(int(r['id']), r['nom']) for r in rows]
    except Exception:
        return []


def get_contrats_opts():
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT ct.id, COALESCE(ct.reference, '#'||ct.id::text) AS ref, c.code_client
            FROM crm_neg_contrats ct JOIN crm_neg_clients c ON ct.client_id=c.id
            WHERE ct.is_active=TRUE ORDER BY ct.id DESC
        """)
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        return [(int(r['id']), f"{r['ref']} — {r['code_client']}") for r in rows]
    except Exception:
        return []


def get_lignes(filtres=None):
    filtres = filtres or {}
    try:
        conn = get_connection()
        cursor = conn.cursor()
        query = """
            SELECT l.id, l.contrat_id, l.statut, l.periode_libelle,
                   l.volume_prevu_t, l.volume_livre_t, l.prix_eur_t,
                   l.date_livraison_prevue, l.date_livraison_reelle, l.notes,
                   l.client_id, l.variete_id, l.producteur_id,
                   COALESCE(c.code_client, '—') AS code_client,
                   COALESCE(v.nom_variete, v.code_variete) AS variete,
                   COALESCE(pr.nom, pr.code_producteur) AS producteur,
                   COALESCE(ct.reference, CASE WHEN l.contrat_id IS NOT NULL THEN '#'||l.contrat_id::text END) AS contrat_ref
            FROM crm_neg_contrat_lignes l
            LEFT JOIN crm_neg_clients c ON l.client_id = c.id
            LEFT JOIN ref_varietes v ON l.variete_id = v.id
            LEFT JOIN ref_producteurs pr ON l.producteur_id = pr.id
            LEFT JOIN crm_neg_contrats ct ON l.contrat_id = ct.id
            WHERE l.is_active = TRUE
        """
        params = []
        if filtres.get('statut') and filtres['statut'] != '— Tous —':
            query += " AND l.statut = %s"
            params.append(filtres['statut'])
        if filtres.get('client_id') and filtres['client_id'] != 0:
            query += " AND l.client_id = %s"
            params.append(int(filtres['client_id']))
        if filtres.get('rattachement') == 'Autonomes':
            query += " AND l.contrat_id IS NULL"
        elif filtres.get('rattachement') == 'De contrat':
            query += " AND l.contrat_id IS NOT NULL"
        query += " ORDER BY l.date_livraison_prevue NULLS LAST, l.id DESC"
        cursor.execute(query, tuple(params))
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        return _df(rows)
    except Exception as e:
        st.error(f"❌ Erreur get_lignes : {e}")
        return pd.DataFrame()


def create_ligne(data):
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO crm_neg_contrat_lignes
                (contrat_id, client_id, variete_id, producteur_id, statut, periode_libelle,
                 volume_prevu_t, volume_livre_t, prix_eur_t, date_livraison_prevue,
                 date_livraison_reelle, notes, created_by)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, (
            int(data['contrat_id']) if data.get('contrat_id') else None,
            int(data['client_id']) if data.get('client_id') else None,
            int(data['variete_id']) if data.get('variete_id') else None,
            int(data['producteur_id']) if data.get('producteur_id') else None,
            data.get('statut') or 'PREVUE', data.get('periode_libelle'),
            float(data['volume_prevu_t']) if data.get('volume_prevu_t') else None,
            float(data['volume_livre_t']) if data.get('volume_livre_t') else None,
            float(data['prix_eur_t']) if data.get('prix_eur_t') else None,
            data.get('date_livraison_prevue'), data.get('date_livraison_reelle'),
            data.get('notes'), st.session_state.get('username', 'system')
        ))
        conn.commit()
        cursor.close()
        conn.close()
        return True, "✅ Ligne créée"
    except Exception as e:
        if 'conn' in locals():
            conn.rollback()
        return False, f"❌ Erreur : {e}"


def update_ligne(ligne_id, data):
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE crm_neg_contrat_lignes SET
                client_id=%s, variete_id=%s, producteur_id=%s, statut=%s, periode_libelle=%s,
                volume_prevu_t=%s, volume_livre_t=%s, prix_eur_t=%s,
                date_livraison_prevue=%s, date_livraison_reelle=%s, notes=%s,
                updated_at=CURRENT_TIMESTAMP
            WHERE id=%s
        """, (
            int(data['client_id']) if data.get('client_id') else None,
            int(data['variete_id']) if data.get('variete_id') else None,
            int(data['producteur_id']) if data.get('producteur_id') else None,
            data.get('statut'), data.get('periode_libelle'),
            float(data['volume_prevu_t']) if data.get('volume_prevu_t') else None,
            float(data['volume_livre_t']) if data.get('volume_livre_t') else None,
            float(data['prix_eur_t']) if data.get('prix_eur_t') else None,
            data.get('date_livraison_prevue'), data.get('date_livraison_reelle'),
            data.get('notes'), int(ligne_id)
        ))
        conn.commit()
        cursor.close()
        conn.close()
        return True, "✅ Ligne mise à jour"
    except Exception as e:
        if 'conn' in locals():
            conn.rollback()
        return False, f"❌ Erreur : {e}"


def supprimer_ligne(ligne_id):
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE crm_neg_contrat_lignes SET is_active=FALSE WHERE id=%s", (int(ligne_id),))
        conn.commit()
        cursor.close()
        conn.close()
        return True, "✅ Ligne supprimée"
    except Exception as e:
        if 'conn' in locals():
            conn.rollback()
        return False, f"❌ Erreur : {e}"


# ============================================================
# UI
# ============================================================
tab_liste, tab_creer = st.tabs(["📋 Lignes", "➕ Nouvelle ligne autonome"])

with tab_liste:
    if st.session_state.get('lg56_msg'):
        st.success(st.session_state.pop('lg56_msg'))

    cf1, cf2, cf3 = st.columns(3)
    with cf1:
        f_statut = st.selectbox("Statut", ['— Tous —'] + STATUTS_LIGNE, key="f_statut_l56")
    with cf2:
        clients_opts = [(0, '— Tous —')] + get_clients_opts()
        f_client = st.selectbox("Client", clients_opts, format_func=lambda x: x[1], key="f_client_l56")
    with cf3:
        f_ratt = st.selectbox("Rattachement", ['— Toutes —', 'Autonomes', 'De contrat'], key="f_ratt_l56")

    df = get_lignes({'statut': f_statut, 'client_id': f_client[0], 'rattachement': f_ratt})

    if not df.empty:
        k1, k2, k3, k4 = st.columns(4)
        k1.metric("Total", len(df))
        k2.metric("Autonomes", int(df['contrat_id'].isna().sum()))
        vp = pd.to_numeric(df['volume_prevu_t'], errors='coerce').sum()
        vl = pd.to_numeric(df['volume_livre_t'], errors='coerce').sum()
        k3.metric("Volume prévu", f"{vp:,.0f} T")
        k4.metric("Volume livré", f"{vl:,.0f} T")

    st.markdown(f"**{len(df)} ligne(s)** — cliquez pour éditer")
    if df.empty:
        st.info("Aucune ligne.")
    else:
        df_table = pd.DataFrame({
            'Client': df['code_client'],
            'Contrat': df['contrat_ref'].fillna('— autonome —'),
            'Période': df['periode_libelle'].fillna('—'),
            'Variété': df['variete'].fillna('—'),
            'Producteur': df['producteur'].fillna('—'),
            'Statut': df['statut'],
            'Prévu (T)': pd.to_numeric(df['volume_prevu_t'], errors='coerce'),
            'Livré (T)': pd.to_numeric(df['volume_livre_t'], errors='coerce'),
        })
        event = st.dataframe(df_table, use_container_width=True, hide_index=True,
                             on_select="rerun", selection_mode="single-row", key="tbl_lignes56")
        rows = event.selection.rows if event and event.selection else []
        if rows:
            lid = int(df.iloc[rows[0]]['id'])
            if st.session_state.get('lg56_edit') != lid:
                st.session_state['lg56_edit'] = lid
                st.rerun()

    # Édition inline
    edit_id = st.session_state.get('lg56_edit')
    if edit_id:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT * FROM crm_neg_contrat_lignes WHERE id=%s", (int(edit_id),))
        lr = cur.fetchone()
        cur.close()
        conn.close()
        if lr:
            lr = dict(lr)
            st.markdown("---")
            ce1, ce2 = st.columns([5, 1])
            with ce1:
                rattach = f"contrat #{lr['contrat_id']}" if lr['contrat_id'] else "autonome"
                st.markdown(f"### ✏️ Ligne #{edit_id} ({rattach})")
            with ce2:
                if st.button("✖ Fermer", key="close_l56", use_container_width=True):
                    st.session_state.pop('lg56_edit', None)
                    st.rerun()
            client_opts2 = [(None, '— Aucun —')] + get_clients_opts()
            var_opts = [(None, '— Non définie —')] + get_varietes_opts()
            prod_opts = [(None, '— Non défini —')] + get_producteurs_opts()
            ic = next((i for i, o in enumerate(client_opts2) if o[0] == lr['client_id']), 0)
            iv = next((i for i, o in enumerate(var_opts) if o[0] == lr['variete_id']), 0)
            ip = next((i for i, o in enumerate(prod_opts) if o[0] == lr['producteur_id']), 0)
            ist = STATUTS_LIGNE.index(lr['statut']) if lr['statut'] in STATUTS_LIGNE else 0
            ed1, ed2 = st.columns(2)
            with ed1:
                e_client = st.selectbox("Client", client_opts2, index=ic, format_func=lambda x: x[1], key="e_client_l56")
                e_per = st.text_input("Période / mois", value=lr['periode_libelle'] or '', key="e_per_l56")
                e_var = st.selectbox("Variété", var_opts, index=iv, format_func=lambda x: x[1], key="e_var_l56")
                e_prod = st.selectbox("Producteur", prod_opts, index=ip, format_func=lambda x: x[1], key="e_prod_l56")
                e_statut = st.selectbox("Statut", STATUTS_LIGNE, index=ist, key="e_statut_l56")
            with ed2:
                e_vprev = st.number_input("Volume prévu (T)", min_value=0.0, value=float(lr['volume_prevu_t'] or 0), step=1.0, key="e_vprev_l56")
                e_vlivr = st.number_input("Volume livré (T)", min_value=0.0, value=float(lr['volume_livre_t'] or 0), step=1.0, key="e_vlivr_l56")
                e_prix = st.number_input("Prix (€/T)", min_value=0.0, value=float(lr['prix_eur_t'] or 0), step=1.0, key="e_prix_l56")
                e_dprev = st.date_input("Date livraison prévue", value=lr['date_livraison_prevue'], key="e_dprev_l56")
                e_dreel = st.date_input("Date livraison réelle", value=lr['date_livraison_reelle'], key="e_dreel_l56")
            e_notes = st.text_area("Notes", value=lr['notes'] or '', key="e_notes_l56", height=50)
            es1, es2, _ = st.columns([1, 1, 3])
            with es1:
                if st.button("💾 Enregistrer", type="primary", key="save_l56"):
                    ok, msg = update_ligne(edit_id, {
                        'client_id': e_client[0], 'variete_id': e_var[0], 'producteur_id': e_prod[0],
                        'statut': e_statut, 'periode_libelle': e_per.strip() or None,
                        'volume_prevu_t': e_vprev if e_vprev > 0 else None,
                        'volume_livre_t': e_vlivr if e_vlivr > 0 else None,
                        'prix_eur_t': e_prix if e_prix > 0 else None,
                        'date_livraison_prevue': e_dprev, 'date_livraison_reelle': e_dreel,
                        'notes': e_notes.strip() or None,
                    })
                    if ok:
                        st.session_state.pop('lg56_edit', None)
                        st.session_state['lg56_msg'] = msg
                        st.rerun()
                    else:
                        st.error(msg)
            with es2:
                if CAN_DELETE and st.button("🗑️ Supprimer", key="del_l56"):
                    supprimer_ligne(edit_id)
                    st.session_state.pop('lg56_edit', None)
                    st.session_state['lg56_msg'] = "✅ Ligne supprimée"
                    st.rerun()

with tab_creer:
    if not CAN_EDIT:
        st.warning("⚠️ Droits insuffisants.")
    else:
        st.subheader("➕ Nouvelle ligne autonome")
        st.caption("Pour ajouter une ligne à un contrat, passez plutôt par la page Contrats. "
                   "Ici, vous pouvez aussi rattacher la ligne à un contrat existant si besoin.")
        if st.session_state.get('lg56_create_msg'):
            st.success(st.session_state.pop('lg56_create_msg'))
        clients_opts3 = get_clients_opts()
        if not clients_opts3:
            st.info("Aucun client négoce. Créez-en d'abord dans la page Clients.")
        else:
            cn1, cn2 = st.columns(2)
            with cn1:
                n_client = st.selectbox("Client *", clients_opts3, format_func=lambda x: x[1], key="n_client_l56")
                contrat_opts = [(None, '— Aucun (ligne autonome) —')] + get_contrats_opts()
                n_contrat = st.selectbox("Rattacher à un contrat", contrat_opts, format_func=lambda x: x[1], key="n_contrat_l56")
                n_per = st.text_input("Période / mois", key="n_per_l56", placeholder="ex : Mars 2026")
                var_opts2 = [(None, '— Non définie —')] + get_varietes_opts()
                n_var = st.selectbox("Variété", var_opts2, format_func=lambda x: x[1], key="n_var_l56")
                prod_opts2 = [(None, '— Non défini —')] + get_producteurs_opts()
                n_prod = st.selectbox("Producteur", prod_opts2, format_func=lambda x: x[1], key="n_prod_l56")
            with cn2:
                n_statut = st.selectbox("Statut", STATUTS_LIGNE, key="n_statut_l56")
                n_vprev = st.number_input("Volume prévu (T)", min_value=0.0, value=0.0, step=1.0, key="n_vprev_l56")
                n_vlivr = st.number_input("Volume livré (T)", min_value=0.0, value=0.0, step=1.0, key="n_vlivr_l56")
                n_prix = st.number_input("Prix (€/T)", min_value=0.0, value=0.0, step=1.0, key="n_prix_l56")
                n_dprev = st.date_input("Date livraison prévue", value=None, key="n_dprev_l56")
            n_notes = st.text_area("Notes", key="n_notes_l56", height=50)
            is_creating = st.session_state.get('is_creating_l56', False)
            if st.button("✅ Créer la ligne", type="primary", key="btn_create_l56", disabled=is_creating):
                st.session_state['is_creating_l56'] = True
                ok, msg = create_ligne({
                    'contrat_id': n_contrat[0], 'client_id': n_client[0],
                    'variete_id': n_var[0], 'producteur_id': n_prod[0],
                    'statut': n_statut, 'periode_libelle': n_per.strip() or None,
                    'volume_prevu_t': n_vprev if n_vprev > 0 else None,
                    'volume_livre_t': n_vlivr if n_vlivr > 0 else None,
                    'prix_eur_t': n_prix if n_prix > 0 else None,
                    'date_livraison_prevue': n_dprev,
                })
                st.session_state.pop('is_creating_l56', None)
                if ok:
                    for k in list(st.session_state.keys()):
                        if k.startswith('n_') and k.endswith('_l56'):
                            st.session_state.pop(k, None)
                    st.session_state['lg56_create_msg'] = msg
                    st.rerun()
                else:
                    st.error(msg)

show_footer()
