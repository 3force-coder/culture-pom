# pages/57_crm_negoce_contrats.py
# CRM Négoce-Export — Contrats de vente (en-tête + lignes de livraison + avancement)
# Tables : crm_neg_contrats, crm_neg_contrat_lignes, crm_neg_clients,
#          crm_neg_propositions, ref_varietes, ref_producteurs
# Pattern POMI : RealDictCursor, requêtes paramétrées, pas de st.form, types natifs.
# Modèle v3 : un contrat (en-tête : volume total, prix global, période) se décompose
#   en lignes de livraison (volume prévu/livré, statut PREVUE..FERMEE, variété/producteur).
#   Avancement = somme(volume_livre) / volume_total (C1=A).
#   Contrat SOLDE auto quand toutes ses lignes sont LIVREE/FERMEE (C2=A).

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
.fiche-head {background:#f6f8ec;border:1px solid #d9e3a8;border-radius:8px;padding:0.8rem 1rem;margin-bottom:0.6rem;}
.lg-prevue {background:#fff8e1;border-left:3px solid #ffc107;padding:0.4rem 0.8rem;border-radius:4px;margin:0.2rem 0;}
.lg-encours {background:#e3f2fd;border-left:3px solid #1565c0;padding:0.4rem 0.8rem;border-radius:4px;margin:0.2rem 0;}
.lg-livree {background:#e8f5e9;border-left:3px solid #4caf50;padding:0.4rem 0.8rem;border-radius:4px;margin:0.2rem 0;}
.lg-fermee {background:#fafafa;border-left:3px solid #9e9e9e;padding:0.4rem 0.8rem;border-radius:4px;margin:0.2rem 0;}
</style>
""", unsafe_allow_html=True)

require_access("CRM_NEGOCE")
CAN_EDIT = can_edit("CRM_NEGOCE")
CAN_DELETE = can_delete("CRM_NEGOCE")

STATUTS_CONTRAT = ['BROUILLON', 'SIGNE', 'SOLDE']
CSS_CONTRAT = {'BROUILLON': 'ct-brouillon', 'SIGNE': 'ct-signe', 'SOLDE': 'ct-solde'}
STATUTS_LIGNE = ['PREVUE', 'EN_COURS', 'LIVREE', 'FERMEE']
CSS_LIGNE = {'PREVUE': 'lg-prevue', 'EN_COURS': 'lg-encours', 'LIVREE': 'lg-livree', 'FERMEE': 'lg-fermee'}

st.title("🌍 CRM Négoce — Contrats de vente")
st.markdown("*Contrats avec lignes de livraison échelonnées et suivi d'avancement*")
st.markdown("---")


def _df(rows):
    return pd.DataFrame([dict(r) for r in rows]) if rows else pd.DataFrame()


# ---------- Selects ----------
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


# ---------- Contrats ----------
def get_contrats(filtres=None):
    filtres = filtres or {}
    try:
        conn = get_connection()
        cursor = conn.cursor()
        query = """
            SELECT ct.id, ct.reference, ct.volume_t, ct.prix_eur_t, ct.periode_campagne,
                   ct.statut, ct.proposition_id, ct.notes,
                   c.code_client, c.raison_sociale,
                   COALESCE(SUM(l.volume_livre_t), 0) AS volume_livre_total,
                   COUNT(l.id) AS nb_lignes
            FROM crm_neg_contrats ct
            JOIN crm_neg_clients c ON ct.client_id = c.id
            LEFT JOIN crm_neg_contrat_lignes l ON l.contrat_id = ct.id AND l.is_active = TRUE
            WHERE ct.is_active = TRUE
        """
        params = []
        if filtres.get('statut') and filtres['statut'] != '— Tous —':
            query += " AND ct.statut = %s"
            params.append(filtres['statut'])
        if filtres.get('client_id') and filtres['client_id'] != 0:
            query += " AND ct.client_id = %s"
            params.append(int(filtres['client_id']))
        query += """ GROUP BY ct.id, ct.reference, ct.volume_t, ct.prix_eur_t, ct.periode_campagne,
                     ct.statut, ct.proposition_id, ct.notes, c.code_client, c.raison_sociale
                     ORDER BY ct.id DESC"""
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
        cursor.execute("""
            SELECT ct.*, c.code_client, c.raison_sociale
            FROM crm_neg_contrats ct JOIN crm_neg_clients c ON ct.client_id = c.id
            WHERE ct.id = %s
        """, (int(contrat_id),))
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
                (reference, client_id, volume_t, prix_eur_t, periode_campagne, statut, notes, created_by)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id
        """, (
            data.get('reference'), int(data['client_id']),
            float(data['volume_t']) if data.get('volume_t') else None,
            float(data['prix_eur_t']) if data.get('prix_eur_t') else None,
            data.get('periode_campagne'), data.get('statut') or 'BROUILLON',
            data.get('notes'), st.session_state.get('username', 'system')
        ))
        new_id = cursor.fetchone()['id']
        conn.commit()
        cursor.close()
        conn.close()
        return True, f"✅ Contrat #{new_id} créé", new_id
    except Exception as e:
        if 'conn' in locals():
            conn.rollback()
        return False, f"❌ Erreur : {e}", None


def update_contrat(contrat_id, data):
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE crm_neg_contrats SET
                reference=%s, volume_t=%s, prix_eur_t=%s, periode_campagne=%s,
                statut=%s, notes=%s, updated_at=CURRENT_TIMESTAMP
            WHERE id=%s
        """, (
            data.get('reference'),
            float(data['volume_t']) if data.get('volume_t') else None,
            float(data['prix_eur_t']) if data.get('prix_eur_t') else None,
            data.get('periode_campagne'), data.get('statut'), data.get('notes'),
            int(contrat_id)
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


# ---------- Lignes d'un contrat ----------
def get_lignes_contrat(contrat_id):
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT l.id, l.statut, l.periode_libelle, l.volume_prevu_t, l.volume_livre_t,
                   l.prix_eur_t, l.date_livraison_prevue, l.date_livraison_reelle, l.notes,
                   COALESCE(v.nom_variete, v.code_variete) AS variete,
                   COALESCE(pr.nom, pr.code_producteur) AS producteur,
                   l.variete_id, l.producteur_id
            FROM crm_neg_contrat_lignes l
            LEFT JOIN ref_varietes v ON l.variete_id = v.id
            LEFT JOIN ref_producteurs pr ON l.producteur_id = pr.id
            WHERE l.contrat_id = %s AND l.is_active = TRUE
            ORDER BY l.date_livraison_prevue NULLS LAST, l.id
        """, (int(contrat_id),))
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        return _df(rows)
    except Exception:
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
            int(data['contrat_id']),
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
        return True, "✅ Ligne ajoutée"
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
                variete_id=%s, producteur_id=%s, statut=%s, periode_libelle=%s,
                volume_prevu_t=%s, volume_livre_t=%s, prix_eur_t=%s,
                date_livraison_prevue=%s, date_livraison_reelle=%s, notes=%s,
                updated_at=CURRENT_TIMESTAMP
            WHERE id=%s
        """, (
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


def recalculer_statut_contrat(contrat_id):
    """C2=A : si toutes les lignes actives sont LIVREE/FERMEE (et au moins une ligne),
    passe le contrat à SOLDE. Sinon, si SOLDE mais qu'une ligne rouvre, repasse à SIGNE."""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT COUNT(*) AS total,
                   SUM(CASE WHEN statut IN ('LIVREE','FERMEE') THEN 1 ELSE 0 END) AS closes
            FROM crm_neg_contrat_lignes WHERE contrat_id=%s AND is_active=TRUE
        """, (int(contrat_id),))
        r = cursor.fetchone()
        cursor.execute("SELECT statut FROM crm_neg_contrats WHERE id=%s", (int(contrat_id),))
        cur_statut = cursor.fetchone()['statut']
        new_statut = cur_statut
        if r['total'] and r['total'] == r['closes']:
            new_statut = 'SOLDE'
        elif cur_statut == 'SOLDE':
            new_statut = 'SIGNE'  # une ligne a rouvert
        if new_statut != cur_statut:
            cursor.execute("UPDATE crm_neg_contrats SET statut=%s, updated_at=CURRENT_TIMESTAMP WHERE id=%s",
                           (new_statut, int(contrat_id)))
            conn.commit()
        cursor.close()
        conn.close()
        return new_statut
    except Exception:
        return None


# ============================================================
# UI
# ============================================================
tab_liste, tab_creer = st.tabs(["📋 Contrats", "➕ Nouveau contrat"])

with tab_liste:
    if st.session_state.get('ct_msg'):
        st.success(st.session_state.pop('ct_msg'))

    sel = st.session_state.get('ct_sel')

    # ===== FICHE CONTRAT (en haut) =====
    if sel:
        c = get_contrat(sel)
        if not c:
            st.error("Contrat introuvable.")
            st.session_state.pop('ct_sel', None)
        else:
            cc1, cc2 = st.columns([5, 1])
            with cc2:
                if st.button("✖ Fermer", key="close_ct", use_container_width=True):
                    st.session_state.pop('ct_sel', None)
                    st.session_state.pop('ct_edit_entete', None)
                    st.rerun()
            ref = c['reference'] or f"#{c['id']}"
            vt = float(c['volume_t'] or 0)
            df_l = get_lignes_contrat(sel)
            vol_livre = pd.to_numeric(df_l['volume_livre_t'], errors='coerce').sum() if not df_l.empty else 0.0
            vol_prevu_lignes = pd.to_numeric(df_l['volume_prevu_t'], errors='coerce').sum() if not df_l.empty else 0.0
            avancement = (vol_livre / vt * 100) if vt > 0 else 0

            st.markdown(
                f'<div class="fiche-head"><strong>📄 Contrat {ref}</strong> '
                f'<span class="badge">{c["statut"]}</span><br>'
                f'🏢 {c["code_client"]} — {c["raison_sociale"] or "—"} '
                f'&nbsp;|&nbsp; Volume total : {vt:,.0f} T '
                f'&nbsp;|&nbsp; Prix global : {(("%.0f €/T" % float(c["prix_eur_t"])) if c["prix_eur_t"] else "—")} '
                f'&nbsp;|&nbsp; Période : {c["periode_campagne"] or "—"}</div>',
                unsafe_allow_html=True)

            # Avancement
            ca1, ca2, ca3, ca4 = st.columns(4)
            ca1.metric("Volume total", f"{vt:,.0f} T")
            ca2.metric("Volume livré", f"{vol_livre:,.0f} T")
            ca3.metric("Reste à livrer", f"{max(0, vt - vol_livre):,.0f} T")
            ca4.metric("Avancement", f"{avancement:.0f} %")
            if vt > 0:
                st.progress(min(1.0, vol_livre / vt))
            if abs(vol_prevu_lignes - vt) > 0.5 and vt > 0:
                st.caption(f"ℹ️ Somme des volumes prévus des lignes : {vol_prevu_lignes:,.0f} T (vs {vt:,.0f} T au contrat)")

            # Actions en-tête
            cact = st.columns([1, 1, 1, 3])
            with cact[0]:
                if CAN_EDIT and st.button("✏️ En-tête", key="edit_entete_ct"):
                    st.session_state['ct_edit_entete'] = int(sel)
                    st.rerun()
            with cact[1]:
                if CAN_EDIT and c['statut'] == 'BROUILLON' and st.button("✍️ Signer", key="sign_ct"):
                    update_statut_contrat(sel, 'SIGNE')
                    st.session_state['ct_msg'] = "✅ Contrat signé"
                    st.rerun()
            with cact[2]:
                if CAN_DELETE and st.button("🗑️ Suppr.", key="del_ct"):
                    supprimer_contrat(sel)
                    st.session_state.pop('ct_sel', None)
                    st.session_state['ct_msg'] = "✅ Contrat supprimé"
                    st.rerun()

            # Édition en-tête
            if st.session_state.get('ct_edit_entete') == int(sel):
                st.markdown("##### ✏️ Modifier l'en-tête")
                ee1, ee2 = st.columns(2)
                with ee1:
                    e_ref = st.text_input("Référence", value=c['reference'] or '', key="e_ref_ct")
                    e_vol = st.number_input("Volume total (T)", min_value=0.0,
                                            value=float(c['volume_t'] or 0), step=10.0, key="e_vol_ct")
                    e_statut = st.selectbox("Statut", STATUTS_CONTRAT,
                                            index=STATUTS_CONTRAT.index(c['statut']) if c['statut'] in STATUTS_CONTRAT else 0,
                                            key="e_statut_ct")
                with ee2:
                    e_prix = st.number_input("Prix global (€/T)", min_value=0.0,
                                             value=float(c['prix_eur_t'] or 0), step=1.0, key="e_prix_ct")
                    e_per = st.text_input("Période globale", value=c['periode_campagne'] or '', key="e_per_ct")
                e_notes = st.text_area("Notes", value=c['notes'] or '', key="e_notes_ct", height=60)
                es1, es2, _ = st.columns([1, 1, 3])
                with es1:
                    if st.button("💾 Enregistrer", type="primary", key="save_entete_ct"):
                        ok, msg = update_contrat(sel, {
                            'reference': e_ref.strip() or None,
                            'volume_t': e_vol if e_vol > 0 else None,
                            'prix_eur_t': e_prix if e_prix > 0 else None,
                            'periode_campagne': e_per.strip() or None,
                            'statut': e_statut, 'notes': e_notes.strip() or None,
                        })
                        if ok:
                            st.session_state.pop('ct_edit_entete', None)
                            st.session_state['ct_msg'] = msg
                            st.rerun()
                        else:
                            st.error(msg)
                with es2:
                    if st.button("✖ Annuler", key="cancel_entete_ct"):
                        st.session_state.pop('ct_edit_entete', None)
                        st.rerun()

            # ===== LIGNES DE LIVRAISON =====
            st.markdown("#### 📦 Lignes de livraison")
            if df_l.empty:
                st.caption("Aucune ligne. Ajoutez les échéances de livraison ci-dessous.")
            else:
                for _, lg in df_l.iterrows():
                    css = CSS_LIGNE.get(lg['statut'], 'lg-prevue')
                    vp = f"{float(lg['volume_prevu_t']):,.0f} T" if pd.notna(lg['volume_prevu_t']) else '—'
                    vl = f"{float(lg['volume_livre_t']):,.0f} T" if pd.notna(lg['volume_livre_t']) else '0 T'
                    prix = f" · {float(lg['prix_eur_t']):,.0f} €/T" if pd.notna(lg['prix_eur_t']) else ""
                    dprev = f" · prévu {pd.to_datetime(lg['date_livraison_prevue']).strftime('%d/%m/%Y')}" if pd.notna(lg['date_livraison_prevue']) else ""
                    dreel = f" · livré {pd.to_datetime(lg['date_livraison_reelle']).strftime('%d/%m/%Y')}" if pd.notna(lg['date_livraison_reelle']) else ""
                    st.markdown(
                        f'<div class="{css}"><strong>{lg["periode_libelle"] or "Ligne"}</strong> '
                        f'<span class="badge">{lg["statut"]}</span> · '
                        f'🥔 {lg["variete"] or "—"} · 👨‍🌾 {lg["producteur"] or "—"} · '
                        f'livré {vl} / prévu {vp}{prix}{dprev}{dreel}</div>',
                        unsafe_allow_html=True)
                    lc = st.columns([1, 1, 6])
                    with lc[0]:
                        if CAN_EDIT and st.button("✏️", key=f"edit_lg_{lg['id']}", help="Modifier la ligne"):
                            st.session_state['lg_edit_id'] = int(lg['id'])
                            st.rerun()
                    with lc[1]:
                        if CAN_DELETE and st.button("🗑️", key=f"del_lg_{lg['id']}", help="Supprimer la ligne"):
                            supprimer_ligne(lg['id'])
                            recalculer_statut_contrat(sel)
                            st.session_state['ct_msg'] = "✅ Ligne supprimée"
                            st.rerun()

            # Édition d'une ligne
            edit_lg = st.session_state.get('lg_edit_id')
            if edit_lg:
                conn = get_connection()
                cur = conn.cursor()
                cur.execute("SELECT * FROM crm_neg_contrat_lignes WHERE id=%s", (int(edit_lg),))
                lgr = cur.fetchone()
                cur.close()
                conn.close()
                if lgr:
                    lgr = dict(lgr)
                    st.markdown(f"##### ✏️ Modifier la ligne #{edit_lg}")
                    var_opts = [(None, '— Non définie —')] + get_varietes_opts()
                    prod_opts = [(None, '— Non défini —')] + get_producteurs_opts()
                    iv = next((i for i, o in enumerate(var_opts) if o[0] == lgr['variete_id']), 0)
                    ip = next((i for i, o in enumerate(prod_opts) if o[0] == lgr['producteur_id']), 0)
                    ist = STATUTS_LIGNE.index(lgr['statut']) if lgr['statut'] in STATUTS_LIGNE else 0
                    el1, el2 = st.columns(2)
                    with el1:
                        l_per = st.text_input("Période / mois", value=lgr['periode_libelle'] or '', key="l_per")
                        l_var = st.selectbox("Variété", var_opts, index=iv, format_func=lambda x: x[1], key="l_var")
                        l_prod = st.selectbox("Producteur", prod_opts, index=ip, format_func=lambda x: x[1], key="l_prod")
                        l_statut = st.selectbox("Statut", STATUTS_LIGNE, index=ist, key="l_statut")
                    with el2:
                        l_vprev = st.number_input("Volume prévu (T)", min_value=0.0,
                                                  value=float(lgr['volume_prevu_t'] or 0), step=1.0, key="l_vprev")
                        l_vlivr = st.number_input("Volume livré (T)", min_value=0.0,
                                                  value=float(lgr['volume_livre_t'] or 0), step=1.0, key="l_vlivr")
                        l_prix = st.number_input("Prix (€/T)", min_value=0.0,
                                                 value=float(lgr['prix_eur_t'] or 0), step=1.0, key="l_prix")
                        l_dprev = st.date_input("Date livraison prévue", value=lgr['date_livraison_prevue'], key="l_dprev")
                        l_dreel = st.date_input("Date livraison réelle", value=lgr['date_livraison_reelle'], key="l_dreel")
                    l_notes = st.text_area("Notes", value=lgr['notes'] or '', key="l_notes", height=50)
                    ls1, ls2, _ = st.columns([1, 1, 3])
                    with ls1:
                        if st.button("💾 Enregistrer la ligne", type="primary", key="save_lg"):
                            ok, msg = update_ligne(edit_lg, {
                                'variete_id': l_var[0], 'producteur_id': l_prod[0],
                                'statut': l_statut, 'periode_libelle': l_per.strip() or None,
                                'volume_prevu_t': l_vprev if l_vprev > 0 else None,
                                'volume_livre_t': l_vlivr if l_vlivr > 0 else None,
                                'prix_eur_t': l_prix if l_prix > 0 else None,
                                'date_livraison_prevue': l_dprev,
                                'date_livraison_reelle': l_dreel,
                                'notes': l_notes.strip() or None,
                            })
                            if ok:
                                st.session_state.pop('lg_edit_id', None)
                                recalculer_statut_contrat(sel)
                                st.session_state['ct_msg'] = msg
                                st.rerun()
                            else:
                                st.error(msg)
                    with ls2:
                        if st.button("✖ Annuler", key="cancel_lg"):
                            st.session_state.pop('lg_edit_id', None)
                            st.rerun()

            # Ajout d'une ligne
            if CAN_EDIT:
                with st.expander("➕ Ajouter une ligne de livraison"):
                    var_opts2 = [(None, '— Non définie —')] + get_varietes_opts()
                    prod_opts2 = [(None, '— Non défini —')] + get_producteurs_opts()
                    al1, al2 = st.columns(2)
                    with al1:
                        a_per = st.text_input("Période / mois", key="a_per", placeholder="ex : Mars 2026")
                        a_var = st.selectbox("Variété", var_opts2, format_func=lambda x: x[1], key="a_var")
                        a_prod = st.selectbox("Producteur", prod_opts2, format_func=lambda x: x[1], key="a_prod")
                        a_statut = st.selectbox("Statut", STATUTS_LIGNE, key="a_statut")
                    with al2:
                        a_vprev = st.number_input("Volume prévu (T)", min_value=0.0, value=0.0, step=1.0, key="a_vprev")
                        a_vlivr = st.number_input("Volume livré (T)", min_value=0.0, value=0.0, step=1.0, key="a_vlivr")
                        a_prix = st.number_input("Prix (€/T)", min_value=0.0, value=0.0, step=1.0, key="a_prix")
                        a_dprev = st.date_input("Date livraison prévue", value=None, key="a_dprev")
                    a_notes = st.text_area("Notes", key="a_notes", height=50)
                    if st.button("✅ Ajouter la ligne", type="primary", key="add_lg"):
                        ok, msg = create_ligne({
                            'contrat_id': sel, 'client_id': c['client_id'],
                            'variete_id': a_var[0], 'producteur_id': a_prod[0],
                            'statut': a_statut, 'periode_libelle': a_per.strip() or None,
                            'volume_prevu_t': a_vprev if a_vprev > 0 else None,
                            'volume_livre_t': a_vlivr if a_vlivr > 0 else None,
                            'prix_eur_t': a_prix if a_prix > 0 else None,
                            'date_livraison_prevue': a_dprev,
                        })
                        if ok:
                            for k in list(st.session_state.keys()):
                                if k.startswith('a_'):
                                    st.session_state.pop(k, None)
                            recalculer_statut_contrat(sel)
                            st.session_state['ct_msg'] = msg
                            st.rerun()
                        else:
                            st.error(msg)
        st.markdown("---")

    # ===== LISTE DES CONTRATS =====
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

    st.markdown(f"**{len(df)} contrat(s)** — cliquez une ligne pour ouvrir la fiche en haut")
    if df.empty:
        st.info("Aucun contrat.")
    else:
        df_table = pd.DataFrame({
            'Réf.': df['reference'].fillna('').replace('', None).fillna(df['id'].apply(lambda x: f"#{x}")),
            'Client': df['code_client'].astype(str) + ' — ' + df['raison_sociale'].fillna('—'),
            'Statut': df['statut'],
            'Vol. total (T)': pd.to_numeric(df['volume_t'], errors='coerce'),
            'Vol. livré (T)': pd.to_numeric(df['volume_livre_total'], errors='coerce'),
            'Lignes': df['nb_lignes'].astype(int),
        })
        event = st.dataframe(df_table, use_container_width=True, hide_index=True,
                             on_select="rerun", selection_mode="single-row", key="tbl_contrats")
        rows = event.selection.rows if event and event.selection else []
        if rows:
            cid = int(df.iloc[rows[0]]['id'])
            if st.session_state.get('ct_sel') != cid:
                st.session_state['ct_sel'] = cid
                st.session_state.pop('ct_edit_entete', None)
                st.session_state.pop('lg_edit_id', None)
                st.rerun()

with tab_creer:
    if not CAN_EDIT:
        st.warning("⚠️ Droits insuffisants.")
    else:
        st.subheader("➕ Nouveau contrat")
        if st.session_state.get('ct_create_msg'):
            st.success(st.session_state.pop('ct_create_msg'))
            st.caption("Ouvrez le contrat dans la liste pour lui ajouter des lignes de livraison.")
        clients_opts2 = get_clients_opts()
        if not clients_opts2:
            st.info("Aucun client négoce. Créez-en d'abord dans la page Clients.")
        else:
            cn1, cn2 = st.columns(2)
            with cn1:
                n_client = st.selectbox("Client *", clients_opts2, format_func=lambda x: x[1], key="n_client_ct")
                n_ref = st.text_input("Référence", key="n_ref_ct", placeholder="(optionnel)")
                n_vol = st.number_input("Volume total (T)", min_value=0.0, value=0.0, step=10.0, key="n_vol_ct")
            with cn2:
                n_prix = st.number_input("Prix global (€/T)", min_value=0.0, value=0.0, step=1.0, key="n_prix_ct")
                n_per = st.text_input("Période globale", key="n_per_ct", placeholder="ex : Sept 2026 - Juin 2027")
                n_statut = st.selectbox("Statut", STATUTS_CONTRAT, key="n_statut_ct")
            n_notes = st.text_area("Notes", key="n_notes_ct", height=60)
            is_creating = st.session_state.get('is_creating_ct', False)
            if st.button("✅ Créer le contrat", type="primary", key="btn_create_ct", disabled=is_creating):
                st.session_state['is_creating_ct'] = True
                ok, msg, new_id = create_contrat({
                    'reference': n_ref.strip() or None, 'client_id': n_client[0],
                    'volume_t': n_vol if n_vol > 0 else None,
                    'prix_eur_t': n_prix if n_prix > 0 else None,
                    'periode_campagne': n_per.strip() or None,
                    'statut': n_statut, 'notes': n_notes.strip() or None,
                })
                st.session_state.pop('is_creating_ct', None)
                if ok:
                    for k in list(st.session_state.keys()):
                        if k.startswith('n_') and k.endswith('_ct'):
                            st.session_state.pop(k, None)
                    st.session_state['ct_create_msg'] = msg
                    st.session_state['ct_sel'] = new_id
                    st.rerun()
                else:
                    st.error(msg)

show_footer()
