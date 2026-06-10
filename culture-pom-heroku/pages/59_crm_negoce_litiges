# pages/59_CRM_Negoce_Litiges.py
# CRM Négoce-Export — Litiges & Lignes ouvertes
# Tables : crm_neg_litiges, crm_neg_lignes_ouvertes, crm_neg_clients,
#          ref_varietes, ref_producteurs, lots_bruts, users_app
# Pattern POMI : RealDictCursor, requêtes paramétrées, pas de st.form, types natifs.

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
.lo-ouvert {background:#f6f8ec;border-left:4px solid #AFCA0A;padding:0.5rem 0.9rem;border-radius:4px;margin:0.25rem 0;}
.lo-ferme {background:#fafafa;border-left:4px solid #9e9e9e;padding:0.5rem 0.9rem;border-radius:4px;margin:0.25rem 0;}
.badge {display:inline-block;padding:1px 8px;border-radius:10px;font-size:0.72rem;font-weight:600;background:#eee;}
</style>
""", unsafe_allow_html=True)

require_access("CRM_NEGOCE")
CAN_EDIT = can_edit("CRM_NEGOCE")
CAN_DELETE = can_delete("CRM_NEGOCE")

STATUTS_LITIGE = ['OUVERT', 'EN_COURS', 'FERME']
CSS_LITIGE = {'OUVERT': 'li-ouvert', 'EN_COURS': 'li-encours', 'FERME': 'li-ferme'}
STATUTS_LIGNE = ['OUVERT', 'FERME']
CSS_LIGNE = {'OUVERT': 'lo-ouvert', 'FERME': 'lo-ferme'}

st.title("🌍 CRM Négoce — Litiges & Lignes ouvertes")
st.markdown("*Suivi des litiges (ouverture → fermeture) et des flux commerciaux actifs*")
st.markdown("---")


def _df(rows):
    return pd.DataFrame([dict(r) for r in rows]) if rows else pd.DataFrame()


# --- Helpers selects ---
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


def get_lots_opts():
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, code_lot_interne, COALESCE(nom_usage, '') AS nom_usage
            FROM lots_bruts WHERE COALESCE(is_active, TRUE) = TRUE
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
            FROM users_app WHERE is_active = TRUE ORDER BY libelle
        """)
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        return [(int(r['id']), r['libelle']) for r in rows]
    except Exception:
        return []


# ============================================================
# LITIGES
# ============================================================
def get_litiges(filtres=None):
    filtres = filtres or {}
    try:
        conn = get_connection()
        cursor = conn.cursor()
        query = """
            SELECT l.id, l.date_ouverture, l.date_fermeture, l.motif, l.conditions_resolution,
                   l.statut, l.montant_en_jeu, l.responsable_nom, l.historique,
                   c.code_client, c.raison_sociale,
                   COALESCE(v.nom_variete, v.code_variete) AS variete,
                   COALESCE(pr.nom, pr.code_producteur) AS producteur,
                   lb.code_lot_interne AS lot,
                   COALESCE(u.prenom||' '||u.nom, l.responsable_nom) AS responsable
            FROM crm_neg_litiges l
            JOIN crm_neg_clients c ON l.client_id = c.id
            LEFT JOIN ref_varietes v ON l.variete_id = v.id
            LEFT JOIN ref_producteurs pr ON l.producteur_id = pr.id
            LEFT JOIN lots_bruts lb ON l.lot_id = lb.id
            LEFT JOIN users_app u ON l.responsable_user_id = u.id
            WHERE l.is_active = TRUE
        """
        params = []
        if filtres.get('statut') and filtres['statut'] != '— Tous —':
            query += " AND l.statut = %s"
            params.append(filtres['statut'])
        if filtres.get('client_id') and filtres['client_id'] != 0:
            query += " AND l.client_id = %s"
            params.append(int(filtres['client_id']))
        query += " ORDER BY l.date_ouverture DESC, l.id DESC"
        cursor.execute(query, tuple(params))
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        return _df(rows)
    except Exception as e:
        st.error(f"❌ Erreur get_litiges : {e}")
        return pd.DataFrame()


def create_litige(data):
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO crm_neg_litiges
                (client_id, date_ouverture, date_fermeture, motif, conditions_resolution,
                 statut, montant_en_jeu, lot_id, producteur_id, variete_id,
                 responsable_user_id, responsable_nom, historique, created_by)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id
        """, (
            int(data['client_id']), data['date_ouverture'], data.get('date_fermeture'),
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
                montant_en_jeu=%s, lot_id=%s, producteur_id=%s, variete_id=%s,
                responsable_user_id=%s, historique=%s, updated_at=CURRENT_TIMESTAMP
            WHERE id=%s
        """, (
            data.get('date_fermeture'), data.get('motif'), data.get('conditions_resolution'),
            data.get('statut'),
            float(data['montant_en_jeu']) if data.get('montant_en_jeu') else None,
            int(data['lot_id']) if data.get('lot_id') else None,
            int(data['producteur_id']) if data.get('producteur_id') else None,
            int(data['variete_id']) if data.get('variete_id') else None,
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
# LIGNES OUVERTES
# ============================================================
def get_lignes(filtres=None):
    filtres = filtres or {}
    try:
        conn = get_connection()
        cursor = conn.cursor()
        query = """
            SELECT lo.id, lo.statut, lo.volume_prevu_t, lo.volume_livre_t,
                   lo.prix_indicatif_eur_t, lo.date_ouverture, lo.date_fermeture, lo.notes,
                   c.code_client, c.raison_sociale,
                   COALESCE(v.nom_variete, v.code_variete) AS variete,
                   COALESCE(pr.nom, pr.code_producteur) AS producteur
            FROM crm_neg_lignes_ouvertes lo
            JOIN crm_neg_clients c ON lo.client_id = c.id
            LEFT JOIN ref_varietes v ON lo.variete_id = v.id
            LEFT JOIN ref_producteurs pr ON lo.producteur_id = pr.id
            WHERE 1=1
        """
        params = []
        if filtres.get('statut') and filtres['statut'] != '— Tous —':
            query += " AND lo.statut = %s"
            params.append(filtres['statut'])
        if filtres.get('client_id') and filtres['client_id'] != 0:
            query += " AND lo.client_id = %s"
            params.append(int(filtres['client_id']))
        query += " ORDER BY lo.statut, lo.date_ouverture DESC, lo.id DESC"
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
            INSERT INTO crm_neg_lignes_ouvertes
                (client_id, variete_id, producteur_id, statut, volume_prevu_t,
                 volume_livre_t, prix_indicatif_eur_t, date_ouverture, notes, created_by)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id
        """, (
            int(data['client_id']),
            int(data['variete_id']) if data.get('variete_id') else None,
            int(data['producteur_id']) if data.get('producteur_id') else None,
            data.get('statut') or 'OUVERT',
            float(data['volume_prevu_t']) if data.get('volume_prevu_t') else None,
            float(data['volume_livre_t']) if data.get('volume_livre_t') else None,
            float(data['prix_indicatif_eur_t']) if data.get('prix_indicatif_eur_t') else None,
            data.get('date_ouverture'), data.get('notes'),
            st.session_state.get('username', 'system')
        ))
        new_id = cursor.fetchone()['id']
        conn.commit()
        cursor.close()
        conn.close()
        return True, f"✅ Ligne ouverte #{new_id} créée"
    except Exception as e:
        if 'conn' in locals():
            conn.rollback()
        return False, f"❌ Erreur : {e}"


def update_ligne(ligne_id, data):
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE crm_neg_lignes_ouvertes SET
                variete_id=%s, producteur_id=%s, statut=%s, volume_prevu_t=%s,
                volume_livre_t=%s, prix_indicatif_eur_t=%s, date_fermeture=%s,
                notes=%s, updated_at=CURRENT_TIMESTAMP
            WHERE id=%s
        """, (
            int(data['variete_id']) if data.get('variete_id') else None,
            int(data['producteur_id']) if data.get('producteur_id') else None,
            data.get('statut'),
            float(data['volume_prevu_t']) if data.get('volume_prevu_t') else None,
            float(data['volume_livre_t']) if data.get('volume_livre_t') else None,
            float(data['prix_indicatif_eur_t']) if data.get('prix_indicatif_eur_t') else None,
            data.get('date_fermeture'), data.get('notes'), int(ligne_id)
        ))
        conn.commit()
        cursor.close()
        conn.close()
        return True, "✅ Ligne mise à jour"
    except Exception as e:
        if 'conn' in locals():
            conn.rollback()
        return False, f"❌ Erreur : {e}"


def fermer_ligne(ligne_id):
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE crm_neg_lignes_ouvertes
            SET statut='FERME', date_fermeture=CURRENT_DATE, updated_at=CURRENT_TIMESTAMP
            WHERE id=%s
        """, (int(ligne_id),))
        conn.commit()
        cursor.close()
        conn.close()
        return True, "✅ Ligne fermée"
    except Exception as e:
        if 'conn' in locals():
            conn.rollback()
        return False, f"❌ Erreur : {e}"


def supprimer_ligne(ligne_id):
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM crm_neg_lignes_ouvertes WHERE id=%s", (int(ligne_id),))
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
tab_litiges, tab_lignes = st.tabs(["⚖️ Litiges", "📈 Lignes ouvertes"])

# ------------------------------------------------------------
# ONGLET LITIGES
# ------------------------------------------------------------
with tab_litiges:
    if st.session_state.get('li_msg'):
        st.success(st.session_state.pop('li_msg'))

    cf1, cf2 = st.columns([1, 2])
    with cf1:
        f_statut = st.selectbox("Statut", ['— Tous —'] + STATUTS_LITIGE, key="f_statut_li")
    with cf2:
        clients_opts = [(0, '— Tous —')] + get_clients_opts()
        f_client = st.selectbox("Client", clients_opts, format_func=lambda x: x[1], key="f_client_li")

    df = get_litiges({'statut': f_statut, 'client_id': f_client[0]})
    if not df.empty:
        k1, k2, k3, k4 = st.columns(4)
        k1.metric("Total", len(df))
        k2.metric("Ouverts", int((df['statut'] == 'OUVERT').sum()))
        k3.metric("En cours", int((df['statut'] == 'EN_COURS').sum()))
        montant = pd.to_numeric(df['montant_en_jeu'], errors='coerce').sum()
        k4.metric("Montant en jeu", f"{montant:,.0f} €")

    # --- Création ---
    if CAN_EDIT:
        with st.expander("➕ Nouveau litige"):
            clients_opts2 = get_clients_opts()
            if clients_opts2:
                li1, li2 = st.columns(2)
                with li1:
                    nl_client = st.selectbox("Client *", clients_opts2, format_func=lambda x: x[1], key="nl_client")
                    nl_douv = st.date_input("Date d'ouverture *", value=date.today(), key="nl_douv")
                    nl_statut = st.selectbox("Statut", STATUTS_LITIGE, key="nl_statut")
                    nl_montant = st.number_input("Montant en jeu (€)", min_value=0.0, value=0.0, step=100.0, key="nl_montant")
                    users_opts = [(None, '— Aucun —')] + get_users_opts()
                    nl_resp = st.selectbox("Responsable du suivi", users_opts, format_func=lambda x: x[1], key="nl_resp")
                with li2:
                    var_opts = [(None, '— Non définie —')] + get_varietes_opts()
                    nl_var = st.selectbox("Variété", var_opts, format_func=lambda x: x[1], key="nl_var")
                    prod_opts = [(None, '— Non défini —')] + get_producteurs_opts()
                    nl_prod = st.selectbox("Producteur", prod_opts, format_func=lambda x: x[1], key="nl_prod")
                    lot_opts = [(None, '— Aucun —')] + get_lots_opts()
                    nl_lot = st.selectbox("Lot concerné", lot_opts, format_func=lambda x: x[1], key="nl_lot")
                nl_motif = st.text_area("Motif", key="nl_motif", height=70)
                nl_hist = st.text_area("Historique des échanges", key="nl_hist", height=70)
                nl_cond = st.text_area("Conditions de résolution", key="nl_cond", height=60)
                if st.button("✅ Créer le litige", type="primary", key="btn_create_li"):
                    ok, msg = create_litige({
                        'client_id': nl_client[0], 'date_ouverture': nl_douv,
                        'statut': nl_statut,
                        'montant_en_jeu': nl_montant if nl_montant > 0 else None,
                        'responsable_user_id': nl_resp[0],
                        'responsable_nom': nl_resp[1] if nl_resp[0] else None,
                        'variete_id': nl_var[0], 'producteur_id': nl_prod[0], 'lot_id': nl_lot[0],
                        'motif': nl_motif.strip() or None,
                        'historique': nl_hist.strip() or None,
                        'conditions_resolution': nl_cond.strip() or None,
                    })
                    if ok:
                        for k in list(st.session_state.keys()):
                            if k.startswith('nl_'):
                                st.session_state.pop(k, None)
                        st.session_state['li_msg'] = msg
                        st.rerun()
                    else:
                        st.error(msg)

    st.markdown(f"**{len(df)} litige(s)**")
    if df.empty:
        st.info("Aucun litige.")
    else:
        for _, l in df.iterrows():
            css = CSS_LITIGE.get(l['statut'], 'li-ouvert')
            douv = pd.to_datetime(l['date_ouverture']).strftime('%d/%m/%Y')
            dferm = f" → fermé le {pd.to_datetime(l['date_fermeture']).strftime('%d/%m/%Y')}" if pd.notna(l['date_fermeture']) else ""
            montant = f" · 💶 {float(l['montant_en_jeu']):,.0f} €" if pd.notna(l['montant_en_jeu']) else ""
            contexte = " · ".join(filter(None, [
                f"🥔 {l['variete']}" if l['variete'] else None,
                f"👨‍🌾 {l['producteur']}" if l['producteur'] else None,
                f"📦 {l['lot']}" if l['lot'] else None,
            ]))
            st.markdown(
                f'<div class="{css}"><strong>{l["code_client"]}</strong> ({l["raison_sociale"] or "—"})'
                f' &nbsp;<span class="badge">{l["statut"]}</span> · ouvert le {douv}{dferm}{montant}<br>'
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
                    ok, msg = supprimer_litige(l['id'])
                    st.session_state['li_msg'] = msg
                    st.rerun()
            st.markdown("<hr style='margin:0.2rem 0;'>", unsafe_allow_html=True)

        # --- Édition litige ---
        edit_id = st.session_state.get('li_edit_id')
        if edit_id:
            # On relit le détail complet pour l'édition (ids des FK)
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
                var_opts = [(None, '— Non définie —')] + get_varietes_opts()
                prod_opts = [(None, '— Non défini —')] + get_producteurs_opts()
                lot_opts = [(None, '— Aucun —')] + get_lots_opts()
                users_opts = [(None, '— Aucun —')] + get_users_opts()
                iv = next((i for i, o in enumerate(var_opts) if o[0] == lit['variete_id']), 0)
                ip = next((i for i, o in enumerate(prod_opts) if o[0] == lit['producteur_id']), 0)
                il = next((i for i, o in enumerate(lot_opts) if o[0] == lit['lot_id']), 0)
                iu = next((i for i, o in enumerate(users_opts) if o[0] == lit['responsable_user_id']), 0)
                ist = STATUTS_LITIGE.index(lit['statut']) if lit['statut'] in STATUTS_LITIGE else 0
                ee1, ee2 = st.columns(2)
                with ee1:
                    e_statut = st.selectbox("Statut", STATUTS_LITIGE, index=ist, key="e_statut_li")
                    e_dferm = st.date_input("Date de fermeture", value=lit['date_fermeture'], key="e_dferm_li")
                    e_montant = st.number_input("Montant en jeu (€)", min_value=0.0,
                                                value=float(lit['montant_en_jeu'] or 0), step=100.0, key="e_montant_li")
                    e_resp = st.selectbox("Responsable", users_opts, index=iu, format_func=lambda x: x[1], key="e_resp_li")
                with ee2:
                    e_var = st.selectbox("Variété", var_opts, index=iv, format_func=lambda x: x[1], key="e_var_li")
                    e_prod = st.selectbox("Producteur", prod_opts, index=ip, format_func=lambda x: x[1], key="e_prod_li")
                    e_lot = st.selectbox("Lot", lot_opts, index=il, format_func=lambda x: x[1], key="e_lot_li")
                e_motif = st.text_area("Motif", value=lit['motif'] or '', key="e_motif_li", height=60)
                e_hist = st.text_area("Historique", value=lit['historique'] or '', key="e_hist_li", height=70)
                e_cond = st.text_area("Conditions de résolution", value=lit['conditions_resolution'] or '', key="e_cond_li", height=60)
                se1, se2, _ = st.columns([1, 1, 3])
                with se1:
                    if st.button("💾 Enregistrer", type="primary", key="btn_save_li"):
                        ok, msg = update_litige(edit_id, {
                            'statut': e_statut, 'date_fermeture': e_dferm,
                            'montant_en_jeu': e_montant if e_montant > 0 else None,
                            'responsable_user_id': e_resp[0],
                            'variete_id': e_var[0], 'producteur_id': e_prod[0], 'lot_id': e_lot[0],
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

# ------------------------------------------------------------
# ONGLET LIGNES OUVERTES
# ------------------------------------------------------------
with tab_lignes:
    if st.session_state.get('lo_msg'):
        st.success(st.session_state.pop('lo_msg'))

    st.caption("Flux commercial actif : un client achète une variété d'un producteur (relation récurrente à suivre).")

    cf1, cf2 = st.columns([1, 2])
    with cf1:
        f_statut_lo = st.selectbox("Statut", ['— Tous —'] + STATUTS_LIGNE, key="f_statut_lo")
    with cf2:
        clients_opts_lo = [(0, '— Tous —')] + get_clients_opts()
        f_client_lo = st.selectbox("Client", clients_opts_lo, format_func=lambda x: x[1], key="f_client_lo")

    df_lo = get_lignes({'statut': f_statut_lo, 'client_id': f_client_lo[0]})
    if not df_lo.empty:
        k1, k2, k3 = st.columns(3)
        k1.metric("Total", len(df_lo))
        k2.metric("Ouvertes", int((df_lo['statut'] == 'OUVERT').sum()))
        vol = pd.to_numeric(df_lo['volume_prevu_t'], errors='coerce').sum()
        k3.metric("Volume prévu total", f"{vol:,.0f} T")

    # --- Création ---
    if CAN_EDIT:
        with st.expander("➕ Nouvelle ligne ouverte"):
            clients_opts3 = get_clients_opts()
            if clients_opts3:
                lo1, lo2 = st.columns(2)
                with lo1:
                    no_client = st.selectbox("Client *", clients_opts3, format_func=lambda x: x[1], key="no_client")
                    var_opts2 = [(None, '— Non définie —')] + get_varietes_opts()
                    no_var = st.selectbox("Variété", var_opts2, format_func=lambda x: x[1], key="no_var")
                    prod_opts2 = [(None, '— Non défini —')] + get_producteurs_opts()
                    no_prod = st.selectbox("Producteur", prod_opts2, format_func=lambda x: x[1], key="no_prod")
                    no_date = st.date_input("Date d'ouverture", value=date.today(), key="no_date")
                with lo2:
                    no_vprev = st.number_input("Volume prévu (T)", min_value=0.0, value=0.0, step=1.0, key="no_vprev")
                    no_vlivr = st.number_input("Volume déjà livré (T)", min_value=0.0, value=0.0, step=1.0, key="no_vlivr")
                    no_prix = st.number_input("Prix indicatif (€/T)", min_value=0.0, value=0.0, step=1.0, key="no_prix")
                no_notes = st.text_area("Notes", key="no_notes", height=60)
                if st.button("✅ Créer la ligne", type="primary", key="btn_create_lo"):
                    ok, msg = create_ligne({
                        'client_id': no_client[0], 'variete_id': no_var[0], 'producteur_id': no_prod[0],
                        'statut': 'OUVERT', 'date_ouverture': no_date,
                        'volume_prevu_t': no_vprev if no_vprev > 0 else None,
                        'volume_livre_t': no_vlivr if no_vlivr > 0 else None,
                        'prix_indicatif_eur_t': no_prix if no_prix > 0 else None,
                        'notes': no_notes.strip() or None,
                    })
                    if ok:
                        for k in list(st.session_state.keys()):
                            if k.startswith('no_'):
                                st.session_state.pop(k, None)
                        st.session_state['lo_msg'] = msg
                        st.rerun()
                    else:
                        st.error(msg)

    st.markdown(f"**{len(df_lo)} ligne(s)**")
    if df_lo.empty:
        st.info("Aucune ligne ouverte.")
    else:
        for _, lo in df_lo.iterrows():
            css = CSS_LIGNE.get(lo['statut'], 'lo-ouvert')
            vprev = f"{float(lo['volume_prevu_t']):,.0f} T" if pd.notna(lo['volume_prevu_t']) else '—'
            vlivr = f"{float(lo['volume_livre_t']):,.0f} T" if pd.notna(lo['volume_livre_t']) else '0 T'
            prix = f" · {float(lo['prix_indicatif_eur_t']):,.0f} €/T" if pd.notna(lo['prix_indicatif_eur_t']) else ""
            douv = pd.to_datetime(lo['date_ouverture']).strftime('%d/%m/%Y') if pd.notna(lo['date_ouverture']) else '—'
            st.markdown(
                f'<div class="{css}"><strong>{lo["code_client"]}</strong> ({lo["raison_sociale"] or "—"})'
                f' &nbsp;<span class="badge">{lo["statut"]}</span><br>'
                f'🥔 {lo["variete"] or "—"} · 👨‍🌾 {lo["producteur"] or "—"} · '
                f'livré {vlivr} / prévu {vprev}{prix} · depuis le {douv}</div>',
                unsafe_allow_html=True)
            if lo['notes']:
                st.caption(f"📝 {lo['notes']}")

            cols = st.columns([1, 1, 1, 3])
            with cols[0]:
                if CAN_EDIT and st.button("✏️", key=f"edit_lo_{lo['id']}", help="Modifier"):
                    st.session_state['lo_edit_id'] = int(lo['id'])
                    st.rerun()
            with cols[1]:
                if CAN_EDIT and lo['statut'] == 'OUVERT' and st.button("🔒 Fermer", key=f"close_lo_{lo['id']}"):
                    ok, msg = fermer_ligne(lo['id'])
                    st.session_state['lo_msg'] = msg
                    st.rerun()
            with cols[2]:
                if CAN_DELETE and st.button("🗑️", key=f"del_lo_{lo['id']}", help="Supprimer"):
                    ok, msg = supprimer_ligne(lo['id'])
                    st.session_state['lo_msg'] = msg
                    st.rerun()
            st.markdown("<hr style='margin:0.2rem 0;'>", unsafe_allow_html=True)

        # --- Édition ligne ouverte ---
        edit_lo = st.session_state.get('lo_edit_id')
        if edit_lo:
            conn = get_connection()
            cur = conn.cursor()
            cur.execute("SELECT * FROM crm_neg_lignes_ouvertes WHERE id=%s", (int(edit_lo),))
            lor = cur.fetchone()
            cur.close()
            conn.close()
            if lor:
                lor = dict(lor)
                st.markdown("---")
                st.markdown(f"### ✏️ Modifier la ligne #{edit_lo}")
                var_opts3 = [(None, '— Non définie —')] + get_varietes_opts()
                prod_opts3 = [(None, '— Non défini —')] + get_producteurs_opts()
                iv = next((i for i, o in enumerate(var_opts3) if o[0] == lor['variete_id']), 0)
                ip = next((i for i, o in enumerate(prod_opts3) if o[0] == lor['producteur_id']), 0)
                ist = STATUTS_LIGNE.index(lor['statut']) if lor['statut'] in STATUTS_LIGNE else 0
                ed1, ed2 = st.columns(2)
                with ed1:
                    e_var = st.selectbox("Variété", var_opts3, index=iv, format_func=lambda x: x[1], key="e_var_lo")
                    e_prod = st.selectbox("Producteur", prod_opts3, index=ip, format_func=lambda x: x[1], key="e_prod_lo")
                    e_statut = st.selectbox("Statut", STATUTS_LIGNE, index=ist, key="e_statut_lo")
                with ed2:
                    e_vprev = st.number_input("Volume prévu (T)", min_value=0.0,
                                              value=float(lor['volume_prevu_t'] or 0), step=1.0, key="e_vprev_lo")
                    e_vlivr = st.number_input("Volume livré (T)", min_value=0.0,
                                              value=float(lor['volume_livre_t'] or 0), step=1.0, key="e_vlivr_lo")
                    e_prix = st.number_input("Prix indicatif (€/T)", min_value=0.0,
                                             value=float(lor['prix_indicatif_eur_t'] or 0), step=1.0, key="e_prix_lo")
                e_notes = st.text_area("Notes", value=lor['notes'] or '', key="e_notes_lo", height=60)
                sf1, sf2, _ = st.columns([1, 1, 3])
                with sf1:
                    if st.button("💾 Enregistrer", type="primary", key="btn_save_lo"):
                        ok, msg = update_ligne(edit_lo, {
                            'variete_id': e_var[0], 'producteur_id': e_prod[0], 'statut': e_statut,
                            'volume_prevu_t': e_vprev if e_vprev > 0 else None,
                            'volume_livre_t': e_vlivr if e_vlivr > 0 else None,
                            'prix_indicatif_eur_t': e_prix if e_prix > 0 else None,
                            'date_fermeture': date.today() if e_statut == 'FERME' else None,
                            'notes': e_notes.strip() or None,
                        })
                        if ok:
                            st.session_state.pop('lo_edit_id', None)
                            st.session_state['lo_msg'] = msg
                            st.rerun()
                        else:
                            st.error(msg)
                with sf2:
                    if st.button("✖ Annuler", key="btn_cancel_lo"):
                        st.session_state.pop('lo_edit_id', None)
                        st.rerun()

show_footer()
