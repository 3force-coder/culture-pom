# pages/59_crm_negoce_litiges.py
# CRM Négoce-Export — Litiges (rattachés à une ligne de livraison)
# Tables : crm_neg_litiges, crm_neg_contrat_lignes, crm_neg_clients,
#          ref_varietes, ref_producteurs, lots_bruts, users_app
# Pattern POMI : RealDictCursor, requêtes paramétrées, pas de st.form, types natifs.
# Modèle v3 : D1=C un litige est rattaché à UNE LIGNE (crm_neg_litiges.ligne_id).
#   D2=A : client / variété / producteur HÉRITÉS automatiquement de la ligne choisie.

import streamlit as st
import pandas as pd
from datetime import datetime, date

from database import get_connection
from components import show_footer
from auth import require_access, can_edit, can_delete

st.set_page_config(page_title="CRM Négoce - Litiges", page_icon="🌍", layout="wide")

st.markdown("""
<style>
.block-container {padding-top:1.5rem!important;padding-bottom:0.5rem!important;
    padding-left:2rem!important;padding-right:2rem!important;}
h1,h2,h3,h4{margin-top:0.3rem!important;margin-bottom:0.3rem!important;}
[data-testid="stMetricValue"]{font-size:1.3rem!important;}
hr{margin-top:0.5rem!important;margin-bottom:0.5rem!important;}
.li-ouvert {background:#ffebee;border-left:4px solid #f44336;padding:0.5rem 0.9rem;border-radius:4px;margin:0.25rem 0;}
.li-encours {background:#fff8e1;border-left:4px solid #ffc107;padding:0.5rem 0.9rem;border-radius:4px;margin:0.25rem 0;}
.li-ferme {background:#e8f5e9;border-left:4px solid #4caf50;padding:0.5rem 0.9rem;border-radius:4px;margin:0.25rem 0;}
.badge {display:inline-block;padding:1px 8px;border-radius:10px;font-size:0.72rem;font-weight:600;background:#eee;}
.herit {background:#f6f8ec;border:1px solid #d9e3a8;border-radius:6px;padding:0.5rem 0.8rem;margin:0.3rem 0;font-size:0.9rem;}
</style>
""", unsafe_allow_html=True)

require_access("CRM_NEGOCE")
CAN_EDIT = can_edit("CRM_NEGOCE")
CAN_DELETE = can_delete("CRM_NEGOCE")

STATUTS_LITIGE = ['OUVERT', 'EN_COURS', 'FERME']
CSS_LITIGE = {'OUVERT': 'li-ouvert', 'EN_COURS': 'li-encours', 'FERME': 'li-ferme'}

st.title("🌍 CRM Négoce — Litiges")
st.markdown("*Litiges rattachés à une ligne de livraison (de l'ouverture à la fermeture)*")
st.markdown("---")


def _df(rows):
    return pd.DataFrame([dict(r) for r in rows]) if rows else pd.DataFrame()


def get_lignes_opts():
    """Lignes disponibles pour rattacher un litige, avec leur contexte (client/variété/producteur)."""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT l.id, l.client_id, l.variete_id, l.producteur_id,
                   l.periode_libelle, l.contrat_id,
                   c.code_client,
                   COALESCE(v.nom_variete, v.code_variete) AS variete,
                   COALESCE(pr.nom, pr.code_producteur) AS producteur,
                   COALESCE(ct.reference, CASE WHEN l.contrat_id IS NOT NULL THEN '#'||l.contrat_id::text END) AS contrat_ref
            FROM crm_neg_contrat_lignes l
            LEFT JOIN crm_neg_clients c ON l.client_id = c.id
            LEFT JOIN ref_varietes v ON l.variete_id = v.id
            LEFT JOIN ref_producteurs pr ON l.producteur_id = pr.id
            LEFT JOIN crm_neg_contrats ct ON l.contrat_id = ct.id
            WHERE l.is_active = TRUE
            ORDER BY l.id DESC
        """)
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        return [dict(r) for r in rows]
    except Exception:
        return []


def get_lots_opts():
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, code_lot_interne, COALESCE(nom_usage,'') AS nom_usage
            FROM lots_bruts WHERE COALESCE(is_active,TRUE)=TRUE
            ORDER BY code_lot_interne DESC LIMIT 500
        """)
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        return [(int(r['id']), f"{r['code_lot_interne']}" + (f" — {r['nom_usage']}" if r['nom_usage'] else "")) for r in rows]
    except Exception:
        return []


def get_users_opts():
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, COALESCE(NULLIF(TRIM(COALESCE(prenom,'')||' '||COALESCE(nom,'')),''),
                                username,'User #'||id::text) AS libelle
            FROM users_app WHERE is_active=TRUE ORDER BY libelle
        """)
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        return [(int(r['id']), r['libelle']) for r in rows]
    except Exception:
        return []


def get_litiges(filtres=None):
    filtres = filtres or {}
    try:
        conn = get_connection()
        cursor = conn.cursor()
        query = """
            SELECT li.id, li.ligne_id, li.date_ouverture, li.date_fermeture, li.motif,
                   li.conditions_resolution, li.statut, li.montant_en_jeu, li.historique,
                   c.code_client, c.raison_sociale,
                   COALESCE(v.nom_variete, v.code_variete) AS variete,
                   COALESCE(pr.nom, pr.code_producteur) AS producteur,
                   lb.code_lot_interne AS lot,
                   COALESCE(u.prenom||' '||u.nom, li.responsable_nom) AS responsable,
                   l.periode_libelle,
                   COALESCE(ct.reference, CASE WHEN l.contrat_id IS NOT NULL THEN '#'||l.contrat_id::text END) AS contrat_ref
            FROM crm_neg_litiges li
            JOIN crm_neg_clients c ON li.client_id = c.id
            LEFT JOIN ref_varietes v ON li.variete_id = v.id
            LEFT JOIN ref_producteurs pr ON li.producteur_id = pr.id
            LEFT JOIN lots_bruts lb ON li.lot_id = lb.id
            LEFT JOIN users_app u ON li.responsable_user_id = u.id
            LEFT JOIN crm_neg_contrat_lignes l ON li.ligne_id = l.id
            LEFT JOIN crm_neg_contrats ct ON l.contrat_id = ct.id
            WHERE li.is_active = TRUE
        """
        params = []
        if filtres.get('statut') and filtres['statut'] != '— Tous —':
            query += " AND li.statut = %s"
            params.append(filtres['statut'])
        if filtres.get('client_id') and filtres['client_id'] != 0:
            query += " AND li.client_id = %s"
            params.append(int(filtres['client_id']))
        query += " ORDER BY li.date_ouverture DESC, li.id DESC"
        cursor.execute(query, tuple(params))
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        return _df(rows)
    except Exception as e:
        st.error(f"❌ Erreur get_litiges : {e}")
        return pd.DataFrame()


def create_litige(data):
    """Crée un litige rattaché à une ligne. client/variété/producteur hérités (D2=A)."""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO crm_neg_litiges
                (client_id, ligne_id, date_ouverture, date_fermeture, motif,
                 conditions_resolution, statut, montant_en_jeu, lot_id,
                 producteur_id, variete_id, responsable_user_id, responsable_nom,
                 historique, created_by)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id
        """, (
            int(data['client_id']),
            int(data['ligne_id']) if data.get('ligne_id') else None,
            data['date_ouverture'], data.get('date_fermeture'),
            data.get('motif'), data.get('conditions_resolution'),
            data.get('statut') or 'OUVERT',
            float(data['montant_en_jeu']) if data.get('montant_en_jeu') else None,
            int(data['lot_id']) if data.get('lot_id') else None,
            int(data['producteur_id']) if data.get('producteur_id') else None,
            int(data['variete_id']) if data.get('variete_id') else None,
            int(data['responsable_user_id']) if data.get('responsable_user_id') else None,
            data.get('responsable_nom'), data.get('historique'),
            st.session_state.get('username', 'system')
        ))
        new_id = cursor.fetchone()['id']
        conn.commit()
        cursor.close()
        conn.close()
        return True, f"✅ Litige #{new_id} créé"
    except Exception as e:
        if 'conn' in locals():
            conn.rollback()
        return False, f"❌ Erreur : {e}"


def update_litige(litige_id, data):
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE crm_neg_litiges SET
                date_fermeture=%s, motif=%s, conditions_resolution=%s, statut=%s,
                montant_en_jeu=%s, lot_id=%s, responsable_user_id=%s, historique=%s,
                updated_at=CURRENT_TIMESTAMP
            WHERE id=%s
        """, (
            data.get('date_fermeture'), data.get('motif'), data.get('conditions_resolution'),
            data.get('statut'),
            float(data['montant_en_jeu']) if data.get('montant_en_jeu') else None,
            int(data['lot_id']) if data.get('lot_id') else None,
            int(data['responsable_user_id']) if data.get('responsable_user_id') else None,
            data.get('historique'), int(litige_id)
        ))
        conn.commit()
        cursor.close()
        conn.close()
        return True, "✅ Litige mis à jour"
    except Exception as e:
        if 'conn' in locals():
            conn.rollback()
        return False, f"❌ Erreur : {e}"


def supprimer_litige(litige_id):
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE crm_neg_litiges SET is_active=FALSE WHERE id=%s", (int(litige_id),))
        conn.commit()
        cursor.close()
        conn.close()
        return True, "✅ Litige supprimé"
    except Exception as e:
        if 'conn' in locals():
            conn.rollback()
        return False, f"❌ Erreur : {e}"


# ============================================================
# UI
# ============================================================
tab_liste, tab_creer = st.tabs(["📋 Litiges", "➕ Nouveau litige"])

with tab_liste:
    if st.session_state.get('li_msg'):
        st.success(st.session_state.pop('li_msg'))

    cf1, cf2 = st.columns([1, 2])
    with cf1:
        f_statut = st.selectbox("Statut", ['— Tous —'] + STATUTS_LITIGE, key="f_statut_li")
    with cf2:
        # Clients ayant au moins un litige (simple : tous les clients)
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT id, code_client, raison_sociale FROM crm_neg_clients WHERE is_active=TRUE ORDER BY code_client")
        clients_all = [(int(r['id']), f"{r['code_client']} — {r['raison_sociale'] or '—'}") for r in cur.fetchall()]
        cur.close()
        conn.close()
        clients_opts = [(0, '— Tous —')] + clients_all
        f_client = st.selectbox("Client", clients_opts, format_func=lambda x: x[1], key="f_client_li")

    df = get_litiges({'statut': f_statut, 'client_id': f_client[0]})
    if not df.empty:
        k1, k2, k3, k4 = st.columns(4)
        k1.metric("Total", len(df))
        k2.metric("Ouverts", int((df['statut'] == 'OUVERT').sum()))
        k3.metric("En cours", int((df['statut'] == 'EN_COURS').sum()))
        montant = pd.to_numeric(df['montant_en_jeu'], errors='coerce').sum()
        k4.metric("Montant en jeu", f"{montant:,.0f} €")

    st.markdown(f"**{len(df)} litige(s)**")
    if df.empty:
        st.info("Aucun litige.")
    else:
        for _, l in df.iterrows():
            css = CSS_LITIGE.get(l['statut'], 'li-ouvert')
            douv = pd.to_datetime(l['date_ouverture']).strftime('%d/%m/%Y')
            dferm = f" → fermé le {pd.to_datetime(l['date_fermeture']).strftime('%d/%m/%Y')}" if pd.notna(l['date_fermeture']) else ""
            montant = f" · 💶 {float(l['montant_en_jeu']):,.0f} €" if pd.notna(l['montant_en_jeu']) else ""
            ligne_ctx = ""
            if pd.notna(l['ligne_id']):
                bits = [b for b in [l['periode_libelle'], l['contrat_ref'] and f"contrat {l['contrat_ref']}"] if b]
                ligne_ctx = f" · 📦 Ligne #{int(l['ligne_id'])}" + (f" ({', '.join(bits)})" if bits else "")
            contexte = " · ".join(filter(None, [
                f"🥔 {l['variete']}" if l['variete'] else None,
                f"👨‍🌾 {l['producteur']}" if l['producteur'] else None,
                f"📦 {l['lot']}" if l['lot'] else None,
            ]))
            st.markdown(
                f'<div class="{css}"><strong>{l["code_client"]}</strong> ({l["raison_sociale"] or "—"})'
                f' &nbsp;<span class="badge">{l["statut"]}</span> · ouvert le {douv}{dferm}{montant}{ligne_ctx}<br>'
                f'{("⚖️ " + (l["motif"] or "")) if l["motif"] else ""}'
                f'{("<br>" + contexte) if contexte else ""}'
                f'{("<br>👤 Responsable : " + l["responsable"]) if l["responsable"] else ""}</div>',
                unsafe_allow_html=True)
            if l['conditions_resolution']:
                st.caption(f"🤝 Résolution : {l['conditions_resolution']}")
            if l['historique']:
                st.caption(f"📜 Historique : {l['historique']}")

            cols = st.columns([1, 1, 4])
            with cols[0]:
                if CAN_EDIT and st.button("✏️", key=f"edit_li_{l['id']}", help="Modifier"):
                    st.session_state['li_edit_id'] = int(l['id'])
                    st.rerun()
            with cols[1]:
                if CAN_DELETE and st.button("🗑️", key=f"del_li_{l['id']}", help="Supprimer"):
                    supprimer_litige(l['id'])
                    st.session_state['li_msg'] = "✅ Litige supprimé"
                    st.rerun()
            st.markdown("<hr style='margin:0.2rem 0;'>", unsafe_allow_html=True)

        # Édition (champs propres au litige ; le rattachement ligne n'est pas modifié ici)
        edit_id = st.session_state.get('li_edit_id')
        if edit_id:
            conn = get_connection()
            cur = conn.cursor()
            cur.execute("SELECT * FROM crm_neg_litiges WHERE id=%s", (int(edit_id),))
            lit = cur.fetchone()
            cur.close()
            conn.close()
            if lit:
                lit = dict(lit)
                st.markdown("---")
                st.markdown(f"### ✏️ Modifier le litige #{edit_id}")
                lot_opts = [(None, '— Aucun —')] + get_lots_opts()
                users_opts = [(None, '— Aucun —')] + get_users_opts()
                il = next((i for i, o in enumerate(lot_opts) if o[0] == lit['lot_id']), 0)
                iu = next((i for i, o in enumerate(users_opts) if o[0] == lit['responsable_user_id']), 0)
                ist = STATUTS_LITIGE.index(lit['statut']) if lit['statut'] in STATUTS_LITIGE else 0
                ee1, ee2 = st.columns(2)
                with ee1:
                    e_statut = st.selectbox("Statut", STATUTS_LITIGE, index=ist, key="e_statut_li")
                    e_dferm = st.date_input("Date de fermeture", value=lit['date_fermeture'], key="e_dferm_li")
                    e_montant = st.number_input("Montant en jeu (€)", min_value=0.0,
                                                value=float(lit['montant_en_jeu'] or 0), step=100.0, key="e_montant_li")
                with ee2:
                    e_lot = st.selectbox("Lot concerné", lot_opts, index=il, format_func=lambda x: x[1], key="e_lot_li")
                    e_resp = st.selectbox("Responsable", users_opts, index=iu, format_func=lambda x: x[1], key="e_resp_li")
                e_motif = st.text_area("Motif", value=lit['motif'] or '', key="e_motif_li", height=60)
                e_hist = st.text_area("Historique", value=lit['historique'] or '', key="e_hist_li", height=70)
                e_cond = st.text_area("Conditions de résolution", value=lit['conditions_resolution'] or '', key="e_cond_li", height=60)
                se1, se2, _ = st.columns([1, 1, 3])
                with se1:
                    if st.button("💾 Enregistrer", type="primary", key="btn_save_li"):
                        ok, msg = update_litige(edit_id, {
                            'statut': e_statut, 'date_fermeture': e_dferm,
                            'montant_en_jeu': e_montant if e_montant > 0 else None,
                            'lot_id': e_lot[0], 'responsable_user_id': e_resp[0],
                            'motif': e_motif.strip() or None,
                            'historique': e_hist.strip() or None,
                            'conditions_resolution': e_cond.strip() or None,
                        })
                        if ok:
                            st.session_state.pop('li_edit_id', None)
                            st.session_state['li_msg'] = msg
                            st.rerun()
                        else:
                            st.error(msg)
                with se2:
                    if st.button("✖ Annuler", key="btn_cancel_li"):
                        st.session_state.pop('li_edit_id', None)
                        st.rerun()

with tab_creer:
    if not CAN_EDIT:
        st.warning("⚠️ Droits insuffisants pour créer un litige.")
    else:
        st.subheader("➕ Nouveau litige")
        if st.session_state.get('li_create_msg'):
            st.success(st.session_state.pop('li_create_msg'))
            st.caption("Voir l'onglet « Litiges ».")

        lignes = get_lignes_opts()
        if not lignes:
            st.info("Aucune ligne de livraison disponible. Créez d'abord une ligne (page Lignes ou Contrats) — "
                    "un litige se rattache obligatoirement à une ligne.")
        else:
            # Sélecteur de ligne (le litige hérite de son client/variété/producteur)
            def fmt_ligne(lg):
                bits = [lg['code_client'] or '—']
                if lg.get('contrat_ref'):
                    bits.append(f"contrat {lg['contrat_ref']}")
                if lg.get('periode_libelle'):
                    bits.append(lg['periode_libelle'])
                if lg.get('variete'):
                    bits.append(lg['variete'])
                return f"Ligne #{lg['id']} — " + " · ".join(bits)

            ligne_choisie = st.selectbox("Ligne concernée *", lignes, format_func=fmt_ligne, key="nl_ligne")

            # Héritage auto (D2=A) : affichage du contexte hérité
            st.markdown(
                f'<div class="herit">↳ Hérité de la ligne : '
                f'<strong>Client</strong> {ligne_choisie["code_client"] or "—"} · '
                f'<strong>Variété</strong> {ligne_choisie["variete"] or "—"} · '
                f'<strong>Producteur</strong> {ligne_choisie["producteur"] or "—"}</div>',
                unsafe_allow_html=True)

            nl1, nl2 = st.columns(2)
            with nl1:
                nl_douv = st.date_input("Date d'ouverture *", value=date.today(), key="nl_douv")
                nl_statut = st.selectbox("Statut", STATUTS_LITIGE, key="nl_statut")
                nl_montant = st.number_input("Montant en jeu (€)", min_value=0.0, value=0.0, step=100.0, key="nl_montant")
            with nl2:
                lot_opts2 = [(None, '— Aucun —')] + get_lots_opts()
                nl_lot = st.selectbox("Lot concerné", lot_opts2, format_func=lambda x: x[1], key="nl_lot")
                users_opts2 = [(None, '— Aucun —')] + get_users_opts()
                nl_resp = st.selectbox("Responsable du suivi", users_opts2, format_func=lambda x: x[1], key="nl_resp")
            nl_motif = st.text_area("Motif", key="nl_motif", height=70)
            nl_hist = st.text_area("Historique des échanges", key="nl_hist", height=70)
            nl_cond = st.text_area("Conditions de résolution", key="nl_cond", height=60)

            is_creating = st.session_state.get('is_creating_li', False)
            if st.button("✅ Créer le litige", type="primary", key="btn_create_li", disabled=is_creating):
                if not ligne_choisie.get('client_id'):
                    st.error("La ligne choisie n'a pas de client associé. Renseignez le client de la ligne d'abord.")
                else:
                    st.session_state['is_creating_li'] = True
                    ok, msg = create_litige({
                        'client_id': ligne_choisie['client_id'],       # hérité
                        'ligne_id': ligne_choisie['id'],
                        'variete_id': ligne_choisie['variete_id'],     # hérité
                        'producteur_id': ligne_choisie['producteur_id'],  # hérité
                        'date_ouverture': nl_douv, 'statut': nl_statut,
                        'montant_en_jeu': nl_montant if nl_montant > 0 else None,
                        'lot_id': nl_lot[0],
                        'responsable_user_id': nl_resp[0],
                        'responsable_nom': nl_resp[1] if nl_resp[0] else None,
                        'motif': nl_motif.strip() or None,
                        'historique': nl_hist.strip() or None,
                        'conditions_resolution': nl_cond.strip() or None,
                    })
                    st.session_state.pop('is_creating_li', None)
                    if ok:
                        for k in list(st.session_state.keys()):
                            if k.startswith('nl_'):
                                st.session_state.pop(k, None)
                        st.session_state['li_create_msg'] = msg
                        st.rerun()
                    else:
                        st.error(msg)

show_footer()
