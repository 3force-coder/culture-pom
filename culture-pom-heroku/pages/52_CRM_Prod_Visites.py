# pages/52_CRM_Prod_Visites.py
# CRM Producteurs - V1 #3 - Visites avec lien dépôt
# Tables : crm_prod_visites (FK ref_producteurs.id, crm_prod_depots.id,
#          crm_prod_types_visite.id, users_app.id pour intervenant)
# Pattern conforme POMI_REFERENCE_TECHNIQUE.md, calqué sur 23_CRM_Visites.py

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
    page_title="CRM Prod Visites - Culture Pom",
    page_icon="📅",
    layout="wide"
)

st.markdown("""
<style>
.block-container {padding-top:1.5rem!important;padding-bottom:0.5rem!important;
    padding-left:2rem!important;padding-right:2rem!important;}
h1,h2,h3,h4{margin-top:0.3rem!important;margin-bottom:0.3rem!important;}
[data-testid="stMetricValue"]{font-size:1.4rem!important;}
hr{margin-top:0.5rem!important;margin-bottom:0.5rem!important;}
.visite-planifiee {background:#fff8e1;border-left:4px solid #ffc107;
    padding:0.6rem 1rem;border-radius:4px;margin:0.3rem 0;}
.visite-effectuee {background:#e8f5e9;border-left:4px solid #4caf50;
    padding:0.6rem 1rem;border-radius:4px;margin:0.3rem 0;}
.visite-annulee {background:#fafafa;border-left:4px solid #9e9e9e;
    padding:0.6rem 1rem;border-radius:4px;margin:0.3rem 0;}
.visite-retard {background:#ffebee;border-left:4px solid #f44336;
    padding:0.6rem 1rem;border-radius:4px;margin:0.3rem 0;}
</style>
""", unsafe_allow_html=True)

# ============================================================
# CONTRÔLE ACCÈS
# ============================================================
require_access("CRM_PRODUCTEURS")

CAN_EDIT = can_edit("CRM_PRODUCTEURS")
CAN_DELETE = can_delete("CRM_PRODUCTEURS")

st.title("📅 CRM Producteurs — Visites")
st.markdown("*Suivi des visites commerciales / techniques (parcelle, dépôt, qualité, audit)*")
st.markdown("---")


# ============================================================
# UTILS
# ============================================================

def safe_int(value, default=0):
    """Cast sécurisé vers int, gère NaN."""
    if value is None:
        return default
    try:
        if pd.isna(value):
            return default
    except (TypeError, ValueError):
        pass
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def safe_str(value, default=''):
    if value is None:
        return default
    try:
        if pd.isna(value):
            return default
    except (TypeError, ValueError):
        pass
    return str(value)


# ============================================================
# FONCTIONS DB — RÉFÉRENTIELS
# ============================================================

def get_producteurs_dropdown():
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


def get_depots_for_producteur(producteur_id):
    """Liste des dépôts d'un producteur (pour ciblage visite)."""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, libelle, ville
            FROM crm_prod_depots
            WHERE producteur_id = %s AND is_active = TRUE
            ORDER BY libelle
        """, (int(producteur_id),))
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        return [(r['id'], r['libelle'], r['ville']) for r in rows]
    except Exception:
        return []


def get_types_visite():
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, code, libelle FROM crm_prod_types_visite
            WHERE is_active = TRUE ORDER BY ordre
        """)
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        return [(r['id'], r['code'], r['libelle']) for r in rows]
    except Exception as e:
        st.error(f"❌ Erreur types visite : {e}")
        return []


def get_intervenants():
    """Liste des utilisateurs Culture Pom pour intervenant_id (Q3)."""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, prenom || ' ' || nom AS libelle
            FROM users_app
            WHERE is_active = TRUE
            ORDER BY nom, prenom
        """)
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        return [(r['id'], r['libelle']) for r in rows]
    except Exception:
        return []


def get_mois_disponibles():
    """Mois ayant des visites (pour filtre Liste)."""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT DISTINCT TO_CHAR(date_visite, 'YYYY-MM') AS mois_code,
                   TO_CHAR(date_visite, 'YYYY-MM') AS mois_libelle
            FROM crm_prod_visites
            WHERE is_active = TRUE
            ORDER BY mois_code DESC
        """)
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        return [(r['mois_code'], r['mois_libelle']) for r in rows]
    except Exception:
        return []


# ============================================================
# FONCTIONS DB — VISITES
# ============================================================

def get_visites(filtres=None):
    try:
        conn = get_connection()
        cursor = conn.cursor()
        query = """
            SELECT
                v.id, v.date_visite, v.statut,
                v.compte_rendu, v.note_qualite_pdt,
                v.actions_suivre, v.prochaine_visite_date,
                p.id AS producteur_id, p.code_producteur, p.nom AS producteur_nom, p.ville,
                v.depot_id, d.libelle AS depot_libelle,
                v.type_visite_id, tv.libelle AS type_visite, tv.code AS type_visite_code,
                v.intervenant_id, COALESCE(u.prenom || ' ' || u.nom, '—') AS intervenant
            FROM crm_prod_visites v
            JOIN ref_producteurs p ON v.producteur_id = p.id
            LEFT JOIN crm_prod_depots d ON v.depot_id = d.id
            LEFT JOIN crm_prod_types_visite tv ON v.type_visite_id = tv.id
            LEFT JOIN users_app u ON v.intervenant_id = u.id
            WHERE v.is_active = TRUE AND p.is_active = TRUE
        """
        params = []
        if filtres:
            if filtres.get('producteur_id') and filtres['producteur_id'] != 0:
                query += " AND v.producteur_id = %s"
                params.append(int(filtres['producteur_id']))
            if filtres.get('intervenant_id') and filtres['intervenant_id'] != 0:
                query += " AND v.intervenant_id = %s"
                params.append(int(filtres['intervenant_id']))
            if filtres.get('statut') and filtres['statut'] != 'Tous':
                query += " AND v.statut = %s"
                params.append(filtres['statut'])
            if filtres.get('type_visite_id') and filtres['type_visite_id'] != 0:
                query += " AND v.type_visite_id = %s"
                params.append(int(filtres['type_visite_id']))
            if filtres.get('mois') and filtres['mois'] != 'Tous':
                query += " AND TO_CHAR(v.date_visite, 'YYYY-MM') = %s"
                params.append(filtres['mois'])

        query += " ORDER BY v.date_visite DESC"
        cursor.execute(query, params)
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        return pd.DataFrame(rows) if rows else pd.DataFrame()
    except Exception as e:
        st.error(f"❌ Erreur chargement visites : {e}")
        return pd.DataFrame()


def get_planning_semaine():
    """Visites planifiées sur les 7 prochains jours."""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT
                v.id, v.date_visite, v.statut,
                p.nom AS producteur_nom, p.ville,
                d.libelle AS depot_libelle,
                COALESCE(u.prenom || ' ' || u.nom, '—') AS intervenant,
                tv.libelle AS type_visite
            FROM crm_prod_visites v
            JOIN ref_producteurs p ON v.producteur_id = p.id
            LEFT JOIN crm_prod_depots d ON v.depot_id = d.id
            LEFT JOIN crm_prod_types_visite tv ON v.type_visite_id = tv.id
            LEFT JOIN users_app u ON v.intervenant_id = u.id
            WHERE v.is_active = TRUE AND p.is_active = TRUE
              AND v.statut = 'PLANIFIEE'
              AND v.date_visite BETWEEN CURRENT_DATE AND CURRENT_DATE + INTERVAL '7 days'
            ORDER BY v.date_visite, p.nom
        """)
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        return rows if rows else []
    except Exception as e:
        st.error(f"❌ Erreur planning : {e}")
        return []


def get_planning_mois(annee_mois):
    """Visites du mois donné (format 'YYYY-MM')."""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT
                v.id, v.date_visite, v.statut,
                p.nom AS producteur_nom, p.ville,
                d.libelle AS depot_libelle,
                COALESCE(u.prenom || ' ' || u.nom, '—') AS intervenant,
                tv.libelle AS type_visite
            FROM crm_prod_visites v
            JOIN ref_producteurs p ON v.producteur_id = p.id
            LEFT JOIN crm_prod_depots d ON v.depot_id = d.id
            LEFT JOIN crm_prod_types_visite tv ON v.type_visite_id = tv.id
            LEFT JOIN users_app u ON v.intervenant_id = u.id
            WHERE v.is_active = TRUE AND p.is_active = TRUE
              AND TO_CHAR(v.date_visite, 'YYYY-MM') = %s
            ORDER BY v.date_visite, p.nom
        """, (annee_mois,))
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        return rows if rows else []
    except Exception as e:
        st.error(f"❌ Erreur planning mois : {e}")
        return []


def create_visite(data):
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO crm_prod_visites (
                producteur_id, depot_id, type_visite_id, intervenant_id,
                date_visite, statut, compte_rendu, note_qualite_pdt,
                prochaine_visite_date, actions_suivre, created_by
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (
            int(data['producteur_id']),
            int(data['depot_id']) if data.get('depot_id') else None,
            int(data['type_visite_id']) if data.get('type_visite_id') else None,
            int(data['intervenant_id']) if data.get('intervenant_id') else None,
            data['date_visite'],
            data['statut'],
            (data.get('compte_rendu') or '').strip() or None,
            int(data['note_qualite_pdt']) if data.get('note_qualite_pdt') else None,
            data.get('prochaine_visite_date'),
            (data.get('actions_suivre') or '').strip() or None,
            st.session_state.get('username', 'system')
        ))
        new_id = cursor.fetchone()['id']
        conn.commit()
        cursor.close()
        conn.close()
        return True, f"✅ Visite #{new_id} créée"
    except Exception as e:
        if 'conn' in locals():
            conn.rollback()
        return False, f"❌ Erreur : {e}"


def update_visite(visite_id, data):
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE crm_prod_visites SET
                producteur_id = %s, depot_id = %s,
                type_visite_id = %s, intervenant_id = %s,
                date_visite = %s, statut = %s,
                compte_rendu = %s, note_qualite_pdt = %s,
                prochaine_visite_date = %s, actions_suivre = %s,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
        """, (
            int(data['producteur_id']),
            int(data['depot_id']) if data.get('depot_id') else None,
            int(data['type_visite_id']) if data.get('type_visite_id') else None,
            int(data['intervenant_id']) if data.get('intervenant_id') else None,
            data['date_visite'],
            data['statut'],
            (data.get('compte_rendu') or '').strip() or None,
            int(data['note_qualite_pdt']) if data.get('note_qualite_pdt') else None,
            data.get('prochaine_visite_date'),
            (data.get('actions_suivre') or '').strip() or None,
            int(visite_id)
        ))
        conn.commit()
        cursor.close()
        conn.close()
        return True, "✅ Visite mise à jour"
    except Exception as e:
        if 'conn' in locals():
            conn.rollback()
        return False, f"❌ Erreur : {e}"


def delete_visite(visite_id):
    """Soft delete."""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE crm_prod_visites SET is_active = FALSE,
                                         updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
        """, (int(visite_id),))
        conn.commit()
        cursor.close()
        conn.close()
        return True, "✅ Visite supprimée"
    except Exception as e:
        if 'conn' in locals():
            conn.rollback()
        return False, f"❌ Erreur : {e}"


def get_kpis_visites():
    try:
        conn = get_connection()
        cursor = conn.cursor()
        kpis = {}
        cursor.execute("""
            SELECT COUNT(*) AS n FROM crm_prod_visites
            WHERE is_active = TRUE AND statut = 'PLANIFIEE'
        """)
        kpis['planifiees'] = cursor.fetchone()['n']
        cursor.execute("""
            SELECT COUNT(*) AS n FROM crm_prod_visites
            WHERE is_active = TRUE AND statut = 'EFFECTUEE'
              AND date_visite >= DATE_TRUNC('month', CURRENT_DATE)
        """)
        kpis['effectuees_mois'] = cursor.fetchone()['n']
        cursor.execute("""
            SELECT COUNT(*) AS n FROM crm_prod_visites
            WHERE is_active = TRUE AND statut = 'PLANIFIEE'
              AND date_visite BETWEEN CURRENT_DATE AND CURRENT_DATE + INTERVAL '7 days'
        """)
        kpis['semaine'] = cursor.fetchone()['n']
        cursor.execute("""
            SELECT COUNT(*) AS n FROM crm_prod_visites
            WHERE is_active = TRUE AND statut = 'PLANIFIEE'
              AND date_visite < CURRENT_DATE
        """)
        kpis['retard'] = cursor.fetchone()['n']
        cursor.close()
        conn.close()
        return kpis
    except Exception as e:
        st.error(f"❌ Erreur KPIs : {e}")
        return {}


# ============================================================
# AFFICHAGE KPIs
# ============================================================

kpis = get_kpis_visites()
if kpis:
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("📋 Planifiées", kpis.get('planifiees', 0))
    c2.metric("✅ Effectuées (ce mois)", kpis.get('effectuees_mois', 0))
    c3.metric("📅 Cette semaine", kpis.get('semaine', 0))
    if kpis.get('retard', 0) > 0:
        c4.metric("⚠️ En retard", kpis['retard'],
                  delta=f"-{kpis['retard']}", delta_color="inverse")
    else:
        c4.metric("✅ Pas de retard", 0)

st.markdown("---")

# ============================================================
# DROPDOWNS (chargés une fois)
# ============================================================
producteurs = get_producteurs_dropdown()
types_visite = get_types_visite()
intervenants = get_intervenants()
mois_dispos = get_mois_disponibles()

# ============================================================
# ONGLETS
# ============================================================

tab1, tab2, tab3 = st.tabs(["📋 Liste", "📅 Planning", "➕ Nouvelle"])


# ----- TAB 1 — Liste avec filtres et édition -----
with tab1:
    st.subheader("📋 Liste des visites")

    if not producteurs:
        st.info("Aucun producteur en base. Crée d'abord un producteur dans la page **Producteurs**.")
    else:
        # ----- Filtres -----
        prod_opts = [(0, '', 'Tous')] + producteurs
        type_opts = [(0, '', 'Tous')] + [(t[0], t[1], t[2]) for t in types_visite]
        interv_opts = [(0, 'Tous')] + intervenants
        mois_opts = ['Tous'] + [m[0] for m in mois_dispos]

        f1, f2, f3, f4, f5 = st.columns(5)
        with f1:
            f_prod = st.selectbox("Producteur", prod_opts,
                                  format_func=lambda x: x[2], key="f_prod_v")
        with f2:
            f_type = st.selectbox("Type visite", type_opts,
                                  format_func=lambda x: x[2], key="f_type_v")
        with f3:
            f_interv = st.selectbox("Intervenant", interv_opts,
                                    format_func=lambda x: x[1], key="f_interv_v")
        with f4:
            f_statut = st.selectbox("Statut",
                                    ['Tous', 'PLANIFIEE', 'EFFECTUEE', 'ANNULEE'],
                                    key="f_statut_v")
        with f5:
            f_mois = st.selectbox("Mois", mois_opts, key="f_mois_v")

        df = get_visites({
            'producteur_id': f_prod[0],
            'type_visite_id': f_type[0],
            'intervenant_id': f_interv[0],
            'statut': f_statut,
            'mois': f_mois,
        })

        st.markdown("---")

        if df.empty:
            st.info("Aucune visite trouvée.")
        else:
            st.markdown(f"**{len(df)} visite(s) trouvée(s)**")

            # ----- Formulaire édition au-dessus de la liste -----
            if 'edit_pvisite_id' in st.session_state and CAN_EDIT:
                st.markdown("### ✏️ Modifier la visite")
                data = st.session_state['edit_pvisite_data']

                col1, col2 = st.columns(2)
                with col1:
                    cur_prod_idx = next((i for i, p in enumerate(producteurs)
                                         if p[0] == safe_int(data.get('producteur_id'))), 0)
                    edit_prod = st.selectbox("Producteur *", producteurs, index=cur_prod_idx,
                                             format_func=lambda x: x[2], key="edit_prod_v")

                    # Dépôts dynamiques selon producteur sélectionné
                    depots_prod = get_depots_for_producteur(edit_prod[0])
                    dep_opts = [(None, '— Aucun dépôt —', '')] + depots_prod
                    cur_dep_idx = next((i for i, d in enumerate(dep_opts)
                                        if d[0] == safe_int(data.get('depot_id')) or
                                        (d[0] is None and not data.get('depot_id'))), 0)
                    edit_dep = st.selectbox("Dépôt (optionnel)", dep_opts, index=cur_dep_idx,
                                            format_func=lambda x: x[1], key="edit_dep_v")

                    type_opts_edit = [(None, '', '— Non défini —')] + \
                        [(t[0], t[1], t[2]) for t in types_visite]
                    cur_type_idx = next((i for i, t in enumerate(type_opts_edit)
                                         if t[0] == safe_int(data.get('type_visite_id'))), 0)
                    edit_type = st.selectbox("Type visite", type_opts_edit, index=cur_type_idx,
                                             format_func=lambda x: x[2], key="edit_type_v")

                    interv_opts_edit = [(None, '— Non assigné —')] + intervenants
                    cur_int_idx = next((i for i, it in enumerate(interv_opts_edit)
                                        if it[0] == safe_int(data.get('intervenant_id'))), 0)
                    edit_interv = st.selectbox("Intervenant", interv_opts_edit,
                                               index=cur_int_idx,
                                               format_func=lambda x: x[1],
                                               key="edit_interv_v")

                with col2:
                    edit_date = st.date_input("Date visite *",
                                              value=data.get('date_visite') or date.today(),
                                              key="edit_date_v")
                    edit_statut = st.selectbox(
                        "Statut",
                        ['PLANIFIEE', 'EFFECTUEE', 'ANNULEE'],
                        index=['PLANIFIEE', 'EFFECTUEE', 'ANNULEE'].index(
                            data.get('statut') or 'PLANIFIEE'
                        ),
                        key="edit_statut_v"
                    )
                    edit_note = st.slider("Note qualité PDT (0-10)", 0, 10,
                                          safe_int(data.get('note_qualite_pdt'), 0),
                                          key="edit_note_v")
                    edit_proch = st.date_input("Prochaine visite",
                                               value=data.get('prochaine_visite_date'),
                                               key="edit_proch_v")

                edit_cr = st.text_area("Compte-rendu",
                                       value=safe_str(data.get('compte_rendu'), ''),
                                       key="edit_cr_v", height=120)
                edit_actions = st.text_area("Actions à suivre",
                                            value=safe_str(data.get('actions_suivre'), ''),
                                            key="edit_act_v", height=80)

                col_save, col_cancel = st.columns(2)
                with col_save:
                    is_saving = st.session_state.get('is_saving_v', False)
                    if st.button("💾 Enregistrer", type="primary", key="btn_save_v",
                                 disabled=is_saving):
                        st.session_state['is_saving_v'] = True
                        ok, msg = update_visite(
                            st.session_state['edit_pvisite_id'],
                            {
                                'producteur_id': edit_prod[0],
                                'depot_id': edit_dep[0],
                                'type_visite_id': edit_type[0],
                                'intervenant_id': edit_interv[0],
                                'date_visite': edit_date,
                                'statut': edit_statut,
                                'compte_rendu': edit_cr,
                                'note_qualite_pdt': edit_note if edit_note > 0 else None,
                                'prochaine_visite_date': edit_proch,
                                'actions_suivre': edit_actions,
                            }
                        )
                        if ok:
                            st.success(msg)
                            st.session_state.pop('edit_pvisite_id', None)
                            st.session_state.pop('edit_pvisite_data', None)
                            st.session_state.pop('is_saving_v', None)
                            st.rerun()
                        else:
                            st.session_state.pop('is_saving_v', None)
                            st.error(msg)
                with col_cancel:
                    if st.button("❌ Annuler", key="btn_cancel_v"):
                        st.session_state.pop('edit_pvisite_id', None)
                        st.session_state.pop('edit_pvisite_data', None)
                        st.session_state.pop('is_saving_v', None)
                        st.rerun()
                st.markdown("---")

            # ----- Tableau -----
            display_df = df[['date_visite', 'statut', 'producteur_nom', 'ville',
                             'depot_libelle', 'type_visite', 'intervenant',
                             'note_qualite_pdt']].copy()
            display_df['date_visite'] = pd.to_datetime(display_df['date_visite']).dt.strftime('%d/%m/%Y')
            display_df.columns = ['Date', 'Statut', 'Producteur', 'Ville',
                                  'Dépôt', 'Type', 'Intervenant', 'Note PDT']
            display_df = display_df.fillna('')

            event = st.dataframe(
                display_df, use_container_width=True, hide_index=True,
                on_select="rerun", selection_mode="single-row",
                key="visites_prod_table"
            )

            selected_rows = event.selection.rows if hasattr(event, 'selection') else []
            if len(selected_rows) > 0:
                idx = selected_rows[0]
                visite = df.iloc[idx]

                st.markdown("---")

                # Carte selon statut
                statut = visite['statut']
                date_v = pd.to_datetime(visite['date_visite']).date() if visite['date_visite'] else None
                en_retard = (statut == 'PLANIFIEE' and date_v and date_v < date.today())

                if en_retard:
                    card_class = "visite-retard"
                elif statut == 'PLANIFIEE':
                    card_class = "visite-planifiee"
                elif statut == 'EFFECTUEE':
                    card_class = "visite-effectuee"
                else:
                    card_class = "visite-annulee"

                date_str = date_v.strftime('%d/%m/%Y') if date_v else '—'
                note = safe_int(visite.get('note_qualite_pdt'), 0)
                note_display = f"⭐ {note}/10" if note > 0 else ''

                st.markdown(f"""
                <div class="{card_class}">
                    <strong>📅 {date_str}</strong> — {visite['producteur_nom']} ({visite['ville'] or '—'})<br>
                    <strong>Type :</strong> {visite.get('type_visite') or '—'}
                    {' &nbsp; | &nbsp; <strong>Dépôt :</strong> ' + str(visite['depot_libelle']) if visite.get('depot_libelle') else ''}
                    <br>
                    <strong>Intervenant :</strong> {visite.get('intervenant') or '—'}
                    &nbsp; | &nbsp; <strong>Statut :</strong> {statut}
                    &nbsp; {note_display}
                </div>
                """, unsafe_allow_html=True)

                if visite.get('compte_rendu'):
                    st.info(f"📝 {visite['compte_rendu']}")
                if visite.get('actions_suivre'):
                    st.warning(f"🎯 Actions à suivre : {visite['actions_suivre']}")
                if visite.get('prochaine_visite_date'):
                    proch = pd.to_datetime(visite['prochaine_visite_date']).strftime('%d/%m/%Y')
                    st.caption(f"📅 Prochaine visite prévue : {proch}")

                col_a, col_b, _ = st.columns([1, 1, 2])
                with col_a:
                    if CAN_EDIT and st.button("✏️ Modifier", key="btn_edit_v"):
                        st.session_state['edit_pvisite_id'] = int(visite['id'])
                        st.session_state['edit_pvisite_data'] = visite.to_dict()
                        st.rerun()
                with col_b:
                    if CAN_DELETE and st.button("🗑️ Supprimer", key="btn_del_v",
                                                type="secondary"):
                        st.session_state['confirm_delete_pvisite'] = int(visite['id'])
                        st.rerun()

                if st.session_state.get('confirm_delete_pvisite') == int(visite['id']):
                    st.warning("⚠️ Confirmer la suppression ?")
                    cy, cn = st.columns(2)
                    with cy:
                        if st.button("✅ Confirmer", key="confirm_yes_v"):
                            ok, msg = delete_visite(st.session_state['confirm_delete_pvisite'])
                            if ok:
                                st.success(msg)
                                st.session_state.pop('confirm_delete_pvisite', None)
                                st.rerun()
                            else:
                                st.error(msg)
                    with cn:
                        if st.button("❌ Annuler", key="confirm_no_v"):
                            st.session_state.pop('confirm_delete_pvisite', None)
                            st.rerun()


# ----- TAB 2 — Planning -----
with tab2:
    sub_sem, sub_mois = st.tabs(["📅 Cette semaine", "🗓️ Par mois"])

    with sub_sem:
        st.subheader("📅 Visites planifiées (7 prochains jours)")
        sem = get_planning_semaine()
        if not sem:
            st.info("Aucune visite planifiée cette semaine.")
        else:
            # Groupement par date
            par_date = {}
            for v in sem:
                d = v['date_visite']
                par_date.setdefault(d, []).append(v)

            for d in sorted(par_date.keys()):
                date_str = d.strftime('%A %d/%m/%Y') if hasattr(d, 'strftime') else str(d)
                with st.expander(f"📅 {date_str} ({len(par_date[d])} visite(s))",
                                 expanded=True):
                    for v in par_date[d]:
                        depot = f" — Dépôt {v['depot_libelle']}" if v.get('depot_libelle') else ''
                        st.markdown(f"""
                        - **{v['producteur_nom']}** ({v['ville'] or '—'}){depot}
                          — {v.get('type_visite') or '—'} — {v.get('intervenant') or '—'}
                        """)

    with sub_mois:
        st.subheader("🗓️ Planning par mois")
        if not mois_dispos:
            st.info("Aucune visite enregistrée.")
        else:
            mois_choisi = st.selectbox("Mois", [m[0] for m in mois_dispos],
                                       key="planning_mois_select")
            visites_mois = get_planning_mois(mois_choisi)
            if not visites_mois:
                st.info("Aucune visite ce mois.")
            else:
                df_mois = pd.DataFrame(visites_mois)
                df_mois['date_visite'] = pd.to_datetime(df_mois['date_visite']).dt.strftime('%d/%m/%Y')
                df_show = df_mois[['date_visite', 'statut', 'producteur_nom',
                                   'ville', 'depot_libelle', 'type_visite',
                                   'intervenant']].copy()
                df_show.columns = ['Date', 'Statut', 'Producteur', 'Ville',
                                   'Dépôt', 'Type', 'Intervenant']
                df_show = df_show.fillna('')
                st.dataframe(df_show, use_container_width=True, hide_index=True)


# ----- TAB 3 — Nouvelle visite -----
with tab3:
    if not CAN_EDIT:
        st.warning("⚠️ Droits insuffisants pour créer une visite.")
    elif not producteurs:
        st.warning("⚠️ Aucun producteur disponible.")
    else:
        st.subheader("➕ Nouvelle visite")

        # Pré-sélection contexte depuis page 50 (Q6)
        preselect_prod_id = st.session_state.get('new_pvisite_producteur_id')
        default_prod_idx = 0
        if preselect_prod_id:
            for i, p in enumerate(producteurs):
                if p[0] == preselect_prod_id:
                    default_prod_idx = i
                    break
            st.session_state.pop('new_pvisite_producteur_id', None)
            st.info(f"📌 Producteur pré-sélectionné depuis la fiche : "
                    f"**{producteurs[default_prod_idx][2]}**")

        col1, col2 = st.columns(2)
        with col1:
            new_prod = st.selectbox("Producteur *", producteurs,
                                    index=default_prod_idx,
                                    format_func=lambda x: x[2], key="new_prod_v")

            # Dépôts dynamiques
            depots_prod = get_depots_for_producteur(new_prod[0])
            dep_opts = [(None, '— Aucun dépôt —', '')] + depots_prod
            new_dep = st.selectbox("Dépôt (optionnel)", dep_opts,
                                   format_func=lambda x: x[1], key="new_dep_v")

            type_opts_new = [(None, '', '— Non défini —')] + \
                [(t[0], t[1], t[2]) for t in types_visite]
            new_type = st.selectbox("Type visite", type_opts_new,
                                    format_func=lambda x: x[2], key="new_type_v")

            interv_opts_new = [(None, '— Non assigné —')] + intervenants
            new_interv = st.selectbox("Intervenant", interv_opts_new,
                                      format_func=lambda x: x[1], key="new_interv_v")

        with col2:
            new_date = st.date_input("Date visite *", value=date.today(), key="new_date_v")
            new_statut = st.selectbox("Statut",
                                      ['PLANIFIEE', 'EFFECTUEE', 'ANNULEE'],
                                      key="new_statut_v")
            new_note = st.slider("Note qualité PDT (0-10, si visite dépôt)",
                                 0, 10, 0, key="new_note_v")
            new_proch = st.date_input("Prochaine visite (optionnel)", value=None,
                                      key="new_proch_v")

        new_cr = st.text_area("Compte-rendu", key="new_cr_v", height=120,
                              placeholder="Observations, qualité PDT, état parcelle, "
                                          "dates plantation/arrachage prévues...")
        new_actions = st.text_area("Actions à suivre", key="new_actions_v", height=80)

        is_creating = st.session_state.get('is_creating_v', False)
        if st.button("✅ Créer la visite", type="primary", key="btn_create_v",
                     disabled=is_creating):
            st.session_state['is_creating_v'] = True
            ok, msg = create_visite({
                'producteur_id': new_prod[0],
                'depot_id': new_dep[0],
                'type_visite_id': new_type[0],
                'intervenant_id': new_interv[0],
                'date_visite': new_date,
                'statut': new_statut,
                'compte_rendu': new_cr,
                'note_qualite_pdt': new_note if new_note > 0 else None,
                'prochaine_visite_date': new_proch,
                'actions_suivre': new_actions,
            })
            if ok:
                st.success(msg)
                for k in list(st.session_state.keys()):
                    if k.startswith('new_') and k.endswith('_v'):
                        st.session_state.pop(k, None)
                st.session_state.pop('is_creating_v', None)
                st.rerun()
            else:
                st.session_state.pop('is_creating_v', None)
                st.error(msg)

show_footer()
