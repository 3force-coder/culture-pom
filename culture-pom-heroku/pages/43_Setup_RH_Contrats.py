import streamlit as st
import pandas as pd
from datetime import date

from auth import require_access, is_admin
from components.header import show_header
from components.footer import show_footer
from database.connection import get_connection

# ============================================================
# CONFIGURATION PAGE
# ============================================================
st.set_page_config(
    page_title="Setup RH Contrats — POMI",
    page_icon="⚙️",
    layout="wide"
)

st.markdown("""
<style>
.block-container {padding-top:2rem!important;padding-bottom:0.5rem!important;
    padding-left:2rem!important;padding-right:2rem!important;}
h1,h2,h3,h4{margin-top:0.3rem!important;margin-bottom:0.3rem!important;}
[data-testid="stMetricValue"]{font-size:1.4rem!important;}
hr{margin-top:0.5rem!important;margin-bottom:0.5rem!important;}
.info-box{background:#e8f4f8;border:1px solid #bee5eb;border-radius:6px;
    padding:10px 14px;margin:8px 0;font-size:0.9em;}
</style>
""", unsafe_allow_html=True)

# ============================================================
# CONTROLE ACCES — ADMIN uniquement
# ============================================================
require_access("STATS_RH")
show_header("Setup RH — Contrats collaborateurs", "⚙️")

if not is_admin():
    st.warning("⚠️ Cette page est réservée aux administrateurs.")
    show_footer()
    st.stop()

# ============================================================
# FONCTIONS BDD
# ============================================================

def create_table_if_needed():
    """Crée la table rh_contrats si elle n'existe pas."""
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS rh_contrats (
                id              SERIAL PRIMARY KEY,
                matricule       VARCHAR(50) NOT NULL,
                nom             VARCHAR(100),
                prenom          VARCHAR(100),
                heures_contrat  NUMERIC(5,2) NOT NULL DEFAULT 35.0,
                type_contrat    VARCHAR(20)  DEFAULT 'CDI',
                is_active       BOOLEAN      DEFAULT TRUE,
                created_at      TIMESTAMP    DEFAULT CURRENT_TIMESTAMP,
                updated_at      TIMESTAMP    DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(matricule)
            )
        """)
        conn.commit()
        cur.close()
        conn.close()
        return True
    except Exception as e:
        st.error(f"Erreur création table : {e}")
        return False


def get_tous_contrats() -> pd.DataFrame:
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT id, matricule, nom, prenom, heures_contrat, type_contrat, is_active,
                   updated_at
            FROM rh_contrats
            ORDER BY nom, prenom
        """)
        rows = cur.fetchall()
        cur.close(); conn.close()
        if not rows:
            return pd.DataFrame()
        return pd.DataFrame([dict(r) for r in rows])
    except Exception as e:
        st.error(f"Erreur lecture contrats : {e}")
        return pd.DataFrame()


def get_salaries_en_base() -> pd.DataFrame:
    """Récupère les salariés distincts depuis rh_pointages (sans contrat défini)."""
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT DISTINCT rp.matricule, rp.nom, rp.prenom
            FROM rh_pointages rp
            LEFT JOIN rh_contrats rc ON rc.matricule = rp.matricule
            WHERE rc.matricule IS NULL
              AND rp.type_salarie = 'CDI/CDD'
            ORDER BY rp.nom, rp.prenom
        """)
        rows = cur.fetchall()
        cur.close(); conn.close()
        if not rows:
            return pd.DataFrame()
        return pd.DataFrame([dict(r) for r in rows])
    except Exception:
        return pd.DataFrame()


def upsert_contrat(matricule: str, nom: str, prenom: str,
                   heures: float, type_contrat: str) -> tuple[bool, str]:
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO rh_contrats (matricule, nom, prenom, heures_contrat, type_contrat, is_active, updated_at)
            VALUES (%s, %s, %s, %s, %s, TRUE, CURRENT_TIMESTAMP)
            ON CONFLICT (matricule) DO UPDATE SET
                nom            = EXCLUDED.nom,
                prenom         = EXCLUDED.prenom,
                heures_contrat = EXCLUDED.heures_contrat,
                type_contrat   = EXCLUDED.type_contrat,
                is_active      = TRUE,
                updated_at     = CURRENT_TIMESTAMP
        """, (str(matricule).strip(), str(nom)[:100], str(prenom)[:100],
              float(heures), str(type_contrat)))
        conn.commit()
        cur.close(); conn.close()
        return True, f"✅ Contrat {matricule} — {prenom} {nom} enregistré ({heures}H)"
    except Exception as e:
        return False, f"❌ Erreur : {e}"


def desactiver_contrat(contrat_id: int) -> tuple[bool, str]:
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            "UPDATE rh_contrats SET is_active = FALSE, updated_at = CURRENT_TIMESTAMP WHERE id = %s",
            (contrat_id,)
        )
        conn.commit()
        cur.close(); conn.close()
        return True, "✅ Contrat désactivé"
    except Exception as e:
        return False, f"❌ Erreur : {e}"


def import_contrats_depuis_pointages() -> tuple[int, int]:
    """Crée automatiquement des contrats 35H pour tous les CDI/CDD sans contrat."""
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO rh_contrats (matricule, nom, prenom, heures_contrat, type_contrat)
            SELECT DISTINCT ON (matricule)
                matricule, nom, prenom, 35.0, 'CDI'
            FROM rh_pointages
            WHERE type_salarie = 'CDI/CDD'
            ON CONFLICT (matricule) DO NOTHING
        """)
        nb = cur.rowcount
        conn.commit()
        cur.close(); conn.close()
        return nb, 0
    except Exception as e:
        st.error(str(e))
        return 0, 1

# ============================================================
# INITIALISATION TABLE
# ============================================================
create_table_if_needed()

# ============================================================
# ONGLETS
# ============================================================
tab_liste, tab_ajouter, tab_import_auto = st.tabs([
    "📋 Contrats existants",
    "➕ Ajouter / Modifier",
    "⚡ Import automatique",
])

# ──────────────────────────────────────────────────────────
# ONGLET 1 : LISTE DES CONTRATS
# ──────────────────────────────────────────────────────────
with tab_liste:
    st.subheader("📋 Contrats enregistrés")

    st.markdown("""
    <div class="info-box">
    Le contrat définit le <strong>seuil de déclenchement des heures supplémentaires</strong>.<br>
    • <strong>35H</strong> : HS dès la 36ème heure<br>
    • <strong>39H</strong> : HS dès la 40ème heure (les heures 35-39H ne sont pas des HS)
    </div>
    """, unsafe_allow_html=True)

    df_contrats = get_tous_contrats()

    if df_contrats.empty:
        st.info("Aucun contrat enregistré. Utilisez l'onglet **Import automatique** pour initialiser.")
    else:
        # KPIs
        actifs = df_contrats[df_contrats['is_active'] == True]
        c1, c2, c3 = st.columns(3)
        c1.metric("👷 Collaborateurs", len(actifs))
        c2.metric("📄 Contrats 35H", len(actifs[actifs['heures_contrat'] == 35.0]))
        c3.metric("📄 Contrats 39H", len(actifs[actifs['heures_contrat'] == 39.0]))

        st.markdown("---")

        # Filtre actifs/tous
        show_inactifs = st.checkbox("Afficher les inactifs", value=False)
        df_show = df_contrats if show_inactifs else actifs

        # Tableau éditable
        st.markdown("**Cliquez sur une ligne pour modifier :**")

        df_display = df_show[['id', 'matricule', 'nom', 'prenom',
                               'heures_contrat', 'type_contrat', 'is_active']].copy()
        df_display['heures_contrat'] = df_display['heures_contrat'].astype(float)

        edited = st.data_editor(
            df_display,
            use_container_width=True,
            hide_index=True,
            disabled=['id', 'matricule', 'nom', 'prenom'],
            column_config={
                'id':             st.column_config.NumberColumn('ID', width='small'),
                'matricule':      st.column_config.TextColumn('Matricule', width='small'),
                'nom':            st.column_config.TextColumn('Nom'),
                'prenom':         st.column_config.TextColumn('Prénom'),
                'heures_contrat': st.column_config.SelectboxColumn(
                    'Heures contrat',
                    options=[35.0, 37.5, 39.0],
                    width='medium'
                ),
                'type_contrat':   st.column_config.SelectboxColumn(
                    'Type',
                    options=['CDI', 'CDD', 'Apprenti', 'Stage'],
                    width='small'
                ),
                'is_active':      st.column_config.CheckboxColumn('Actif', width='small'),
            },
            key="editor_contrats"
        )

        if st.button("💾 Sauvegarder les modifications", type="primary"):
            nb_ok = nb_err = 0
            for _, row in edited.iterrows():
                ok, _ = upsert_contrat(
                    row['matricule'], row['nom'], row['prenom'],
                    row['heures_contrat'], row['type_contrat']
                )
                # Gérer is_active séparément
                if not row['is_active']:
                    desactiver_contrat(int(row['id']))
                if ok:
                    nb_ok += 1
                else:
                    nb_err += 1
            if nb_ok:
                st.success(f"✅ {nb_ok} contrat(s) mis à jour")
                st.cache_data.clear()
                st.rerun()
            if nb_err:
                st.error(f"❌ {nb_err} erreur(s)")


# ──────────────────────────────────────────────────────────
# ONGLET 2 : AJOUTER / MODIFIER UN CONTRAT
# ──────────────────────────────────────────────────────────
with tab_ajouter:
    st.subheader("➕ Ajouter ou modifier un contrat")

    # Récupérer salariés connus depuis pointages pour auto-complétion
    df_salaries = get_salaries_en_base()

    col1, col2 = st.columns(2)

    with col1:
        if not df_salaries.empty:
            options_sal = ["— Saisie manuelle —"] + [
                f"{r['matricule']} — {r['nom']} {r['prenom']}"
                for _, r in df_salaries.iterrows()
            ]
            choix = st.selectbox(
                "Salarié sans contrat (depuis pointages)",
                options_sal,
                key="choix_salarie"
            )
            if choix != "— Saisie manuelle —":
                mat_auto = choix.split(" — ")[0]
                nom_auto = choix.split(" — ")[1].split(" ")[0] if " — " in choix else ""
                pre_auto = " ".join(choix.split(" — ")[1].split(" ")[1:]) if " — " in choix else ""
            else:
                mat_auto = nom_auto = pre_auto = ""
        else:
            st.info("Tous les salariés CDI/CDD ont déjà un contrat.")
            mat_auto = nom_auto = pre_auto = ""

    with col2:
        st.markdown("**Ou saisie manuelle :**")
        matricule = st.text_input(
            "Matricule *",
            value=mat_auto if mat_auto else "",
            key="inp_matricule",
            help="Matricule exact de la pointeuse"
        )
        nom = st.text_input("Nom *", value=nom_auto, key="inp_nom")
        prenom = st.text_input("Prénom", value=pre_auto, key="inp_prenom")

    st.markdown("---")

    col3, col4 = st.columns(2)
    with col3:
        heures = st.selectbox(
            "Durée hebdomadaire contractuelle *",
            options=[35.0, 37.5, 39.0],
            index=0,
            format_func=lambda x: f"{x:.1f}H / semaine",
            key="inp_heures"
        )
    with col4:
        type_contrat = st.selectbox(
            "Type de contrat",
            options=['CDI', 'CDD', 'Apprenti', 'Stage'],
            key="inp_type"
        )

    st.markdown(f"""
    <div class="info-box">
    Pour ce contrat : les heures supplémentaires commenceront à partir de
    <strong>{heures + 1:.0f}H/semaine</strong>.
    </div>
    """, unsafe_allow_html=True)

    if st.button("💾 Enregistrer le contrat", type="primary", use_container_width=True):
        if not matricule or not nom:
            st.error("❌ Matricule et Nom sont obligatoires.")
        else:
            ok, msg = upsert_contrat(matricule, nom, prenom, heures, type_contrat)
            if ok:
                st.success(msg)
                st.cache_data.clear()
                st.rerun()
            else:
                st.error(msg)


# ──────────────────────────────────────────────────────────
# ONGLET 3 : IMPORT AUTOMATIQUE
# ──────────────────────────────────────────────────────────
with tab_import_auto:
    st.subheader("⚡ Import automatique depuis les pointages")

    st.markdown("""
    <div class="info-box">
    Cette action crée automatiquement un contrat <strong>35H CDI</strong> pour chaque
    collaborateur CDI/CDD présent dans les pointages et qui n'a pas encore de contrat défini.<br><br>
    <strong>Vous pourrez ensuite modifier les contrats 39H individuellement dans l'onglet "Contrats existants".</strong>
    </div>
    """, unsafe_allow_html=True)

    # Aperçu des salariés sans contrat
    df_sans = get_salaries_en_base()
    if df_sans.empty:
        st.success("✅ Tous les salariés CDI/CDD ont déjà un contrat.")
    else:
        st.warning(f"⚠️ {len(df_sans)} salarié(s) sans contrat :")
        st.dataframe(
            df_sans[['matricule', 'nom', 'prenom']],
            use_container_width=True,
            hide_index=True
        )

        st.markdown("---")

        if st.button(
            f"⚡ Créer {len(df_sans)} contrat(s) 35H par défaut",
            type="primary",
            use_container_width=True
        ):
            nb_cree, nb_err = import_contrats_depuis_pointages()
            if nb_cree > 0:
                st.success(f"✅ {nb_cree} contrat(s) créé(s) avec durée 35H par défaut.")
                st.info("💡 Pensez à mettre à jour les contrats 39H dans l'onglet **Contrats existants**.")
                st.cache_data.clear()
                st.rerun()
            else:
                st.info("Aucun nouveau contrat créé (déjà tous présents).")

show_footer()
