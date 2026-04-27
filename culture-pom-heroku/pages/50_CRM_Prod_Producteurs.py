# pages/50_CRM_Prod_Producteurs.py
# CRM Producteurs - V1 #1 - Fiche producteur enrichie
# Liée à ref_producteurs (lecture/édition limitée) + crm_prod_depots
# Pattern conforme POMI_REFERENCE_TECHNIQUE.md

import streamlit as st
import pandas as pd
from datetime import date

from database import get_connection
from components import show_footer
from auth import require_access, can_edit, can_delete

# ============================================================
# CONFIGURATION PAGE
# ============================================================
st.set_page_config(
    page_title="CRM Producteurs - Culture Pom",
    page_icon="🌾",
    layout="wide"
)

st.markdown("""
<style>
.block-container {padding-top:2rem!important;padding-bottom:0.5rem!important;
    padding-left:2rem!important;padding-right:2rem!important;}
h1,h2,h3,h4{margin-top:0.3rem!important;margin-bottom:0.3rem!important;}
[data-testid="stMetricValue"]{font-size:1.4rem!important;}
hr{margin-top:0.5rem!important;margin-bottom:0.5rem!important;}
.fiche-box {background:#f7faf0;border-left:4px solid #AFCA0A;
    border-radius:6px;padding:12px 16px;margin:8px 0;}
.depot-box {background:#fffbe6;border-left:4px solid #FFEC00;
    border-radius:6px;padding:10px 14px;margin:6px 0;}
.certif-ok {background:#d4edda;color:#155724;padding:2px 8px;
    border-radius:12px;font-size:0.85em;font-weight:600;}
.certif-ko {background:#f8d7da;color:#721c24;padding:2px 8px;
    border-radius:12px;font-size:0.85em;font-weight:600;}
</style>
""", unsafe_allow_html=True)

# ============================================================
# CONTRÔLE ACCÈS
# ============================================================
require_access("CRM_PRODUCTEURS")

CAN_EDIT = can_edit("CRM_PRODUCTEURS")
CAN_DELETE = can_delete("CRM_PRODUCTEURS")

st.title("🌾 CRM Producteurs — Fiches enrichies")
st.markdown("*Producteurs (source : ref_producteurs) + services, certifications, dépôts*")
st.markdown("---")


# ============================================================
# FONCTIONS DB — PRODUCTEURS
# ============================================================

def get_producteurs(filtres=None):
    """Liste des producteurs avec données enrichies + nb dépôts."""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        query = """
            SELECT
                p.id,
                p.code_producteur,
                p.nom,
                p.code_postal,
                p.ville,
                p.departement,
                p.telephone,
                p.email,
                p.statut,
                p.acheteur_referent,
                p.global_gap,
                p.certif_global_gap_numero,
                p.certif_global_gap_validite,
                p.has_big_bag,
                p.has_lavage,
                p.has_stockage,
                p.notes,
                COALESCE(d.nb_depots, 0) AS nb_depots
            FROM ref_producteurs p
            LEFT JOIN (
                SELECT producteur_id, COUNT(*) AS nb_depots
                FROM crm_prod_depots
                WHERE is_active = TRUE
                GROUP BY producteur_id
            ) d ON p.id = d.producteur_id
            WHERE p.is_active = TRUE
        """
        params = []

        if filtres:
            if filtres.get('search'):
                query += " AND (LOWER(p.nom) LIKE %s OR LOWER(p.code_producteur) LIKE %s OR LOWER(COALESCE(p.ville,'')) LIKE %s)"
                s = f"%{filtres['search'].lower()}%"
                params.extend([s, s, s])
            if filtres.get('departement') and filtres['departement'] != 'Tous':
                query += " AND p.departement = %s"
                params.append(filtres['departement'])
            if filtres.get('global_gap_only'):
                query += " AND p.global_gap = TRUE"
            if filtres.get('service_filter') and filtres['service_filter'] != 'Tous':
                if filtres['service_filter'] == 'Big bag':
                    query += " AND p.has_big_bag = TRUE"
                elif filtres['service_filter'] == 'Lavage':
                    query += " AND p.has_lavage = TRUE"
                elif filtres['service_filter'] == 'Stockage':
                    query += " AND p.has_stockage = TRUE"

        query += " ORDER BY p.nom"

        cursor.execute(query, params)
        rows = cursor.fetchall()
        cursor.close()
        conn.close()

        return pd.DataFrame(rows) if rows else pd.DataFrame()
    except Exception as e:
        st.error(f"❌ Erreur chargement producteurs : {e}")
        return pd.DataFrame()


def get_departements():
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT DISTINCT departement
            FROM ref_producteurs
            WHERE is_active = TRUE AND departement IS NOT NULL AND departement != ''
            ORDER BY departement
        """)
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        return [r['departement'] for r in rows]
    except Exception:
        return []


def get_producteur_by_id(producteur_id):
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM ref_producteurs WHERE id = %s
        """, (int(producteur_id),))
        row = cursor.fetchone()
        cursor.close()
        conn.close()
        return dict(row) if row else None
    except Exception as e:
        st.error(f"❌ Erreur : {e}")
        return None


def update_producteur_enrichi(producteur_id, data):
    """Met à jour UNIQUEMENT les champs enrichis (services + certifs + notes + acheteur).
    Les champs core (nom, adresse, code) restent gérés depuis 01_Sources.py."""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE ref_producteurs SET
                has_big_bag = %s,
                has_lavage = %s,
                has_stockage = %s,
                global_gap = %s,
                certif_global_gap_numero = %s,
                certif_global_gap_validite = %s,
                acheteur_referent = %s,
                notes = %s,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
        """, (
            bool(data.get('has_big_bag', False)),
            bool(data.get('has_lavage', False)),
            bool(data.get('has_stockage', False)),
            bool(data.get('global_gap', False)),
            data.get('certif_global_gap_numero') or None,
            data.get('certif_global_gap_validite'),
            data.get('acheteur_referent') or None,
            data.get('notes') or None,
            int(producteur_id)
        ))
        conn.commit()
        cursor.close()
        conn.close()
        return True, "✅ Producteur mis à jour"
    except Exception as e:
        if 'conn' in locals():
            conn.rollback()
        return False, f"❌ Erreur : {e}"


# ============================================================
# FONCTIONS DB — DÉPÔTS
# ============================================================

def get_depots(producteur_id):
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, libelle, adresse, code_postal, ville, departement,
                   capacite_tonnes, latitude, longitude, notes
            FROM crm_prod_depots
            WHERE producteur_id = %s AND is_active = TRUE
            ORDER BY libelle
        """, (int(producteur_id),))
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        return rows if rows else []
    except Exception as e:
        st.error(f"❌ Erreur dépôts : {e}")
        return []


def create_depot(producteur_id, data):
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO crm_prod_depots (
                producteur_id, libelle, adresse, code_postal, ville, departement,
                capacite_tonnes, notes, created_by
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (
            int(producteur_id),
            data['libelle'],
            data.get('adresse') or None,
            data.get('code_postal') or None,
            data.get('ville') or None,
            data.get('departement') or None,
            float(data['capacite_tonnes']) if data.get('capacite_tonnes') else None,
            data.get('notes') or None,
            st.session_state.get('username', 'system')
        ))
        new_id = cursor.fetchone()['id']
        conn.commit()
        cursor.close()
        conn.close()
        return True, f"✅ Dépôt créé (id={new_id})"
    except Exception as e:
        if 'conn' in locals():
            conn.rollback()
        return False, f"❌ Erreur : {e}"


def update_depot(depot_id, data):
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE crm_prod_depots SET
                libelle = %s, adresse = %s, code_postal = %s,
                ville = %s, departement = %s,
                capacite_tonnes = %s, notes = %s,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
        """, (
            data['libelle'],
            data.get('adresse') or None,
            data.get('code_postal') or None,
            data.get('ville') or None,
            data.get('departement') or None,
            float(data['capacite_tonnes']) if data.get('capacite_tonnes') else None,
            data.get('notes') or None,
            int(depot_id)
        ))
        conn.commit()
        cursor.close()
        conn.close()
        return True, "✅ Dépôt mis à jour"
    except Exception as e:
        if 'conn' in locals():
            conn.rollback()
        return False, f"❌ Erreur : {e}"


def delete_depot(depot_id):
    """Soft delete."""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE crm_prod_depots SET is_active = FALSE,
                                       updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
        """, (int(depot_id),))
        conn.commit()
        cursor.close()
        conn.close()
        return True, "✅ Dépôt supprimé"
    except Exception as e:
        if 'conn' in locals():
            conn.rollback()
        return False, f"❌ Erreur : {e}"


# ============================================================
# KPIs
# ============================================================

def get_kpis():
    try:
        conn = get_connection()
        cursor = conn.cursor()
        kpis = {}

        cursor.execute("SELECT COUNT(*) AS n FROM ref_producteurs WHERE is_active = TRUE")
        kpis['total'] = cursor.fetchone()['n']

        cursor.execute("SELECT COUNT(*) AS n FROM ref_producteurs WHERE is_active = TRUE AND global_gap = TRUE")
        kpis['global_gap'] = cursor.fetchone()['n']

        cursor.execute("""
            SELECT COUNT(*) AS n FROM ref_producteurs
            WHERE is_active = TRUE
              AND (has_big_bag = TRUE OR has_lavage = TRUE OR has_stockage = TRUE)
        """)
        kpis['avec_services'] = cursor.fetchone()['n']

        cursor.execute("SELECT COUNT(*) AS n FROM crm_prod_depots WHERE is_active = TRUE")
        kpis['nb_depots'] = cursor.fetchone()['n']

        cursor.execute("""
            SELECT COUNT(*) AS n FROM ref_producteurs
            WHERE is_active = TRUE AND global_gap = TRUE
              AND certif_global_gap_validite IS NOT NULL
              AND certif_global_gap_validite <= CURRENT_DATE + INTERVAL '60 days'
        """)
        kpis['certifs_expirent'] = cursor.fetchone()['n']

        cursor.close()
        conn.close()
        return kpis
    except Exception as e:
        st.error(f"❌ Erreur KPIs : {e}")
        return {}


# ============================================================
# FONCTION D'AFFICHAGE FICHE — définie AVANT utilisation
# ============================================================

def afficher_fiche_producteur(prod):
    """Fiche détail producteur avec édition et gestion des dépôts."""
    st.markdown(f"### 👨‍🌾 {prod['nom']}")
    st.caption(f"Code : `{prod.get('code_producteur', '')}`  |  ID : {prod['id']}")

    # ----- Données core (lecture seule) -----
    with st.expander("📍 Coordonnées (gérées dans Sources)", expanded=False):
        st.markdown(f"""
        - **Adresse** : {prod.get('adresse') or '—'}
        - **CP / Ville** : {prod.get('code_postal') or '—'} {prod.get('ville') or '—'}
        - **Département** : {prod.get('departement') or '—'}
        - **Téléphone** : {prod.get('telephone') or '—'}
        - **Email** : {prod.get('email') or '—'}
        - **Contact** : {prod.get('prenom_contact') or ''} {prod.get('nom_contact') or '—'}
        - **SIRET** : {prod.get('siret') or '—'}
        """)
        st.caption("Pour modifier ces champs, va dans **01_Sources → Producteurs**.")

    # ----- Édition champs enrichis -----
    st.markdown("#### ✏️ Données CRM")

    if not CAN_EDIT:
        st.info("Lecture seule — droits insuffisants pour modifier.")

    e_col1, e_col2 = st.columns(2)

    with e_col1:
        st.markdown("**🏭 Services proposés**")
        e_big_bag = st.checkbox("Mise en big bag", value=bool(prod.get('has_big_bag')),
                                disabled=not CAN_EDIT, key=f"bb_{prod['id']}")
        e_lavage = st.checkbox("Lavage", value=bool(prod.get('has_lavage')),
                               disabled=not CAN_EDIT, key=f"lv_{prod['id']}")
        e_stockage = st.checkbox("Stockage", value=bool(prod.get('has_stockage')),
                                 disabled=not CAN_EDIT, key=f"st_{prod['id']}")

        e_acheteur = st.text_input("Acheteur référent",
                                   value=prod.get('acheteur_referent') or '',
                                   disabled=not CAN_EDIT, key=f"ach_{prod['id']}")

    with e_col2:
        st.markdown("**📜 Certifications Global GAP**")
        e_gap = st.checkbox("Certifié Global GAP", value=bool(prod.get('global_gap')),
                            disabled=not CAN_EDIT, key=f"gap_{prod['id']}")
        e_gap_num = st.text_input("N° certificat",
                                  value=prod.get('certif_global_gap_numero') or '',
                                  disabled=not CAN_EDIT or not e_gap,
                                  key=f"gnum_{prod['id']}")
        e_gap_val = st.date_input("Date validité",
                                  value=prod.get('certif_global_gap_validite'),
                                  disabled=not CAN_EDIT or not e_gap,
                                  key=f"gval_{prod['id']}")

        # Indicateur visuel
        if e_gap and prod.get('certif_global_gap_validite'):
            val = prod['certif_global_gap_validite']
            jours = (val - date.today()).days
            if jours < 0:
                st.markdown(f'<span class="certif-ko">⛔ Certif expirée ({-jours}j)</span>',
                            unsafe_allow_html=True)
            elif jours < 60:
                st.markdown(f'<span class="certif-ko">⚠️ Expire dans {jours}j</span>',
                            unsafe_allow_html=True)
            else:
                st.markdown(f'<span class="certif-ok">✅ Valide ({jours}j)</span>',
                            unsafe_allow_html=True)

    e_notes = st.text_area("Notes", value=prod.get('notes') or '',
                           disabled=not CAN_EDIT, key=f"nt_{prod['id']}")

    if CAN_EDIT:
        if st.button("💾 Enregistrer les modifications", type="primary",
                     key=f"save_{prod['id']}"):
            data = {
                'has_big_bag': e_big_bag,
                'has_lavage': e_lavage,
                'has_stockage': e_stockage,
                'global_gap': e_gap,
                'certif_global_gap_numero': e_gap_num if e_gap else None,
                'certif_global_gap_validite': e_gap_val if e_gap else None,
                'acheteur_referent': e_acheteur,
                'notes': e_notes,
            }
            ok, msg = update_producteur_enrichi(prod['id'], data)
            if ok:
                st.success(msg)
                st.rerun()
            else:
                st.error(msg)

    # ----- Dépôts -----
    st.markdown("---")
    st.markdown("#### 📦 Dépôts du producteur")

    depots = get_depots(prod['id'])

    if not depots:
        st.info("Aucun dépôt enregistré pour ce producteur.")
    else:
        for dep in depots:
            with st.expander(f"📦 {dep['libelle']} — {dep.get('ville') or ''}"):
                d1, d2 = st.columns(2)
                with d1:
                    st.markdown(f"**Adresse** : {dep.get('adresse') or '—'}")
                    st.markdown(f"**CP / Ville** : {dep.get('code_postal') or '—'} {dep.get('ville') or '—'}")
                    st.markdown(f"**Département** : {dep.get('departement') or '—'}")
                with d2:
                    cap = dep.get('capacite_tonnes')
                    st.markdown(f"**Capacité** : {f'{cap} T' if cap else '—'}")
                    if dep.get('notes'):
                        st.markdown(f"**Notes** : {dep['notes']}")

                if CAN_EDIT or CAN_DELETE:
                    bcol1, bcol2 = st.columns(2)
                    with bcol1:
                        if CAN_EDIT and st.button("✏️ Modifier", key=f"edit_dep_{dep['id']}"):
                            st.session_state['edit_dep_id'] = dep['id']
                            st.session_state['edit_dep_data'] = dict(dep)
                            st.rerun()
                    with bcol2:
                        if CAN_DELETE and st.button("🗑️ Supprimer", key=f"del_dep_{dep['id']}"):
                            ok, msg = delete_depot(dep['id'])
                            if ok:
                                st.success(msg)
                                st.rerun()
                            else:
                                st.error(msg)

    # Formulaire édition dépôt
    if st.session_state.get('edit_dep_id'):
        st.markdown("##### ✏️ Modifier le dépôt")
        d = st.session_state.get('edit_dep_data', {})
        ed_col1, ed_col2 = st.columns(2)
        with ed_col1:
            ed_lib = st.text_input("Libellé *", value=d.get('libelle', ''), key="ed_lib")
            ed_adr = st.text_input("Adresse", value=d.get('adresse', '') or '', key="ed_adr")
            ed_cp = st.text_input("Code postal", value=d.get('code_postal', '') or '', key="ed_cp")
        with ed_col2:
            ed_ville = st.text_input("Ville", value=d.get('ville', '') or '', key="ed_ville")
            ed_dept = st.text_input("Département", value=d.get('departement', '') or '', key="ed_dept")
            ed_cap = st.number_input("Capacité (T)",
                                     value=float(d.get('capacite_tonnes') or 0),
                                     min_value=0.0, step=10.0, key="ed_cap")
        ed_notes = st.text_area("Notes", value=d.get('notes', '') or '', key="ed_notes")

        bs1, bs2 = st.columns(2)
        with bs1:
            if st.button("💾 Enregistrer", type="primary", key="ed_save"):
                if not ed_lib:
                    st.error("Libellé obligatoire")
                else:
                    ok, msg = update_depot(st.session_state['edit_dep_id'], {
                        'libelle': ed_lib, 'adresse': ed_adr, 'code_postal': ed_cp,
                        'ville': ed_ville, 'departement': ed_dept,
                        'capacite_tonnes': ed_cap if ed_cap > 0 else None,
                        'notes': ed_notes
                    })
                    if ok:
                        st.success(msg)
                        st.session_state.pop('edit_dep_id', None)
                        st.session_state.pop('edit_dep_data', None)
                        st.rerun()
                    else:
                        st.error(msg)
        with bs2:
            if st.button("❌ Annuler", key="ed_cancel"):
                st.session_state.pop('edit_dep_id', None)
                st.session_state.pop('edit_dep_data', None)
                st.rerun()

    # Formulaire ajout dépôt
    if CAN_EDIT and not st.session_state.get('edit_dep_id'):
        with st.expander("➕ Ajouter un dépôt", expanded=False):
            n_col1, n_col2 = st.columns(2)
            with n_col1:
                n_lib = st.text_input("Libellé *", key=f"new_lib_{prod['id']}")
                n_adr = st.text_input("Adresse", key=f"new_adr_{prod['id']}")
                n_cp = st.text_input("Code postal", key=f"new_cp_{prod['id']}")
            with n_col2:
                n_ville = st.text_input("Ville", key=f"new_ville_{prod['id']}")
                n_dept = st.text_input("Département", key=f"new_dept_{prod['id']}")
                n_cap = st.number_input("Capacité (T)", value=0.0, min_value=0.0, step=10.0,
                                        key=f"new_cap_{prod['id']}")
            n_notes = st.text_area("Notes", key=f"new_notes_{prod['id']}")

            if st.button("✅ Créer le dépôt", type="primary", key=f"new_save_{prod['id']}"):
                if not n_lib:
                    st.error("Libellé obligatoire")
                else:
                    ok, msg = create_depot(prod['id'], {
                        'libelle': n_lib, 'adresse': n_adr, 'code_postal': n_cp,
                        'ville': n_ville, 'departement': n_dept,
                        'capacite_tonnes': n_cap if n_cap > 0 else None,
                        'notes': n_notes
                    })
                    if ok:
                        st.success(msg)
                        st.rerun()
                    else:
                        st.error(msg)


# ============================================================
# AFFICHAGE KPIs
# ============================================================

kpis = get_kpis()
if kpis:
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("👨‍🌾 Producteurs", kpis.get('total', 0))
    c2.metric("✅ Global GAP", kpis.get('global_gap', 0))
    c3.metric("🏭 Avec services", kpis.get('avec_services', 0))
    c4.metric("📦 Dépôts", kpis.get('nb_depots', 0))
    if kpis.get('certifs_expirent', 0) > 0:
        c5.metric("⚠️ Certifs <60j", kpis['certifs_expirent'],
                  delta=f"-{kpis['certifs_expirent']}", delta_color="inverse")
    else:
        c5.metric("✅ Certifs OK", 0)

st.markdown("---")

# ============================================================
# ONGLETS
# ============================================================

tab1, tab2 = st.tabs(["📋 Liste & Fiche", "📊 Vue tableau"])


# ----- TAB 1 — Liste + sélection + fiche détail -----
with tab1:
    st.subheader("📋 Producteurs")

    departements = get_departements()
    fcol1, fcol2, fcol3, fcol4 = st.columns([2, 1, 1, 1])

    with fcol1:
        f_search = st.text_input("🔍 Recherche (nom, code, ville)", key="prod_search")
    with fcol2:
        f_dept = st.selectbox("Département", ['Tous'] + departements, key="prod_dept")
    with fcol3:
        f_service = st.selectbox("Service", ['Tous', 'Big bag', 'Lavage', 'Stockage'], key="prod_service")
    with fcol4:
        f_gap = st.checkbox("Global GAP uniquement", key="prod_gap_only")

    filtres = {
        'search': f_search,
        'departement': f_dept,
        'service_filter': f_service,
        'global_gap_only': f_gap,
    }

    df_prod = get_producteurs(filtres)

    st.markdown(f"**{len(df_prod)} producteur(s) trouvé(s)**")

    if df_prod.empty:
        st.info("Aucun producteur ne correspond aux filtres.")
    else:
        col_list, col_fiche = st.columns([1, 1])

        with col_list:
            display_df = df_prod[[
                'code_producteur', 'nom', 'ville', 'departement',
                'global_gap', 'has_big_bag', 'has_lavage', 'has_stockage', 'nb_depots'
            ]].copy()
            for c in ['global_gap', 'has_big_bag', 'has_lavage', 'has_stockage']:
                display_df[c] = display_df[c].apply(lambda x: '✅' if x else '')
            display_df.columns = ['Code', 'Nom', 'Ville', 'Dept',
                                  'GAP', 'BBag', 'Lav', 'Stock', 'Dépôts']

            event = st.dataframe(
                display_df.fillna(''),
                use_container_width=True,
                hide_index=True,
                on_select="rerun",
                selection_mode="single-row",
                key="prod_table"
            )

            if event.selection.rows:
                selected_idx = event.selection.rows[0]
                selected_id = int(df_prod.iloc[selected_idx]['id'])
                st.session_state['prod_selected_id'] = selected_id

        with col_fiche:
            selected_id = st.session_state.get('prod_selected_id')
            if not selected_id:
                st.info("👈 Sélectionne un producteur dans le tableau pour voir sa fiche")
            else:
                prod = get_producteur_by_id(selected_id)
                if not prod:
                    st.error("Producteur introuvable (peut-être supprimé entre-temps)")
                    st.session_state.pop('prod_selected_id', None)
                else:
                    afficher_fiche_producteur(prod)


# ----- TAB 2 — Vue tableau complète + export -----
with tab2:
    st.subheader("📊 Vue tableau complète")

    df_all = get_producteurs(None)

    if df_all.empty:
        st.info("Aucun producteur en base.")
    else:
        export_df = df_all.copy()
        for col in ['global_gap', 'has_big_bag', 'has_lavage', 'has_stockage']:
            if col in export_df.columns:
                export_df[col] = export_df[col].apply(lambda x: 'OUI' if x else 'NON')

        st.dataframe(export_df, use_container_width=True, hide_index=True)

        csv = export_df.to_csv(index=False).encode('utf-8')
        st.download_button(
            "📥 Exporter CSV",
            data=csv,
            file_name=f"crm_producteurs_{date.today().isoformat()}.csv",
            mime="text/csv"
        )


show_footer()
