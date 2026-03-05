import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from database import get_connection
from components import show_footer
from auth import require_access
import plotly.express as px
import plotly.graph_objects as go

st.set_page_config(page_title="Prévisions Ventes - Culture Pom", page_icon="📈", layout="wide")

# CSS compact
st.markdown("""
<style>
    .block-container {
        padding-top: 2rem !important;
        padding-bottom: 0.5rem !important;
    }
    h1, h2, h3, h4 {
        margin-top: 0.3rem !important;
        margin-bottom: 0.3rem !important;
    }
    /* Box bouton nouveau produit */
    .new-product-box {
        background-color: #e3f2fd;
        padding: 1rem;
        border-radius: 0.5rem;
        border-left: 4px solid #2196f3;
        margin: 1rem 0;
    }
    /* Légende estimation */
    .estimation-legend {
        background-color: #fff8e1;
        padding: 0.6rem 1rem;
        border-radius: 0.5rem;
        border-left: 4px solid #FFC107;
        margin: 0.5rem 0;
        font-size: 0.9rem;
    }
</style>
""", unsafe_allow_html=True)

# ============================================================
# 🔒 CONTRÔLE D'ACCÈS RBAC
# ============================================================
require_access("COMMERCIAL")
# ============================================================


st.title("📈 Prévisions de Ventes")
st.markdown("*Semaine en cours (lecture seule) + 5 semaines éditables — Estimations auto sur historique*")
st.markdown("---")

# ==========================================
# FONCTIONS UTILITAIRES
# ==========================================

def get_semaine_actuelle():
    """Retourne le numéro de semaine et l'année actuels"""
    today = datetime.now()
    iso_calendar = today.isocalendar()
    return iso_calendar[1], iso_calendar[0]  # (semaine, année)


def get_semaine_courante_et_editables():
    """
    Retourne :
      - semaine_courante : (annee, sem) — lecture seule
      - semaines_editables : [(annee, sem), ...] — S+1 à S+5, éditables
    """
    semaine_actuelle, annee_actuelle = get_semaine_actuelle()
    semaine_courante = (annee_actuelle, semaine_actuelle)

    semaines_editables = []
    for i in range(1, 6):  # S+1 à S+5
        sem = semaine_actuelle + i
        annee = annee_actuelle
        if sem > 52:
            sem = sem - 52
            annee = annee + 1
        semaines_editables.append((annee, sem))

    return semaine_courante, semaines_editables


def format_semaine(annee, semaine):
    """Formate une semaine pour affichage"""
    return f"S{semaine:02d}/{annee}"


def get_produits_commerciaux():
    """Récupère tous les produits commerciaux actifs"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT code_produit, marque, libelle, code_variete
            FROM ref_produits_commerciaux
            WHERE is_active = TRUE
            ORDER BY marque, libelle
        """)
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        if rows:
            return pd.DataFrame(rows)
        return pd.DataFrame()
    except Exception as e:
        st.error(f"❌ Erreur : {str(e)}")
        return pd.DataFrame()


def get_previsions(semaines):
    """
    Récupère les prévisions pour les semaines données.
    ✅ CORRECTION INJECTION SQL : requête paramétrée
    """
    if not semaines:
        return pd.DataFrame()
    try:
        conn = get_connection()
        cursor = conn.cursor()

        # ✅ Requête paramétrée — plus de f-string avec valeurs injectées
        conditions = " OR ".join(["(annee = %s AND semaine = %s)" for _ in semaines])
        params = [val for a, s in semaines for val in (a, s)]

        cursor.execute(f"""
            SELECT code_produit_commercial, annee, semaine, quantite_prevue_tonnes
            FROM previsions_ventes
            WHERE {conditions}
        """, params)
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        if rows:
            return pd.DataFrame(rows)
        return pd.DataFrame()
    except Exception as e:
        st.error(f"❌ Erreur : {str(e)}")
        return pd.DataFrame()


def get_moyenne_3_semaines_precedentes(semaines_cibles):
    """
    Pour chaque semaine cible, calcule la moyenne des quantités réelles
    des 3 semaines précédentes (depuis la base), par produit.

    Retourne un dict :
      { (annee, sem) : { code_produit : moyenne_float } }
    """
    if not semaines_cibles:
        return {}

    # Collecter toutes les semaines précédentes nécessaires
    semaines_a_chercher = set()
    for (annee, sem) in semaines_cibles:
        for i in range(1, 4):  # 3 semaines précédentes
            s = sem - i
            a = annee
            if s <= 0:
                s = s + 52
                a = a - 1
            semaines_a_chercher.add((a, s))

    if not semaines_a_chercher:
        return {}

    try:
        conn = get_connection()
        cursor = conn.cursor()

        semaines_list = list(semaines_a_chercher)
        conditions = " OR ".join(["(annee = %s AND semaine = %s)" for _ in semaines_list])
        params = [val for a, s in semaines_list for val in (a, s)]

        cursor.execute(f"""
            SELECT code_produit_commercial, annee, semaine, quantite_prevue_tonnes
            FROM previsions_ventes
            WHERE {conditions}
        """, params)
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
    except Exception as e:
        st.error(f"❌ Erreur calcul estimations : {str(e)}")
        return {}

    if not rows:
        return {}

    df_hist = pd.DataFrame(rows)

    result = {}
    for (annee, sem) in semaines_cibles:
        moyennes_produit = {}
        # Les 3 semaines précédentes de cette semaine cible
        semaines_prec = []
        for i in range(1, 4):
            s = sem - i
            a = annee
            if s <= 0:
                s = s + 52
                a = a - 1
            semaines_prec.append((a, s))

        # Filtrer l'historique sur ces 3 semaines
        mask = pd.Series([False] * len(df_hist))
        for (a, s) in semaines_prec:
            mask = mask | ((df_hist['annee'] == a) & (df_hist['semaine'] == s))
        df_prec = df_hist[mask]

        if not df_prec.empty:
            for code_produit, grp in df_prec.groupby('code_produit_commercial'):
                moyennes_produit[code_produit] = float(grp['quantite_prevue_tonnes'].mean())

        result[(annee, sem)] = moyennes_produit

    return result


def get_previsions_historique_complet():
    """Récupère TOUT l'historique des prévisions (passées + futures)"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT pv.code_produit_commercial, pv.annee, pv.semaine, pv.quantite_prevue_tonnes,
                   pc.marque, pc.libelle,
                   pv.created_at, pv.updated_at
            FROM previsions_ventes pv
            LEFT JOIN ref_produits_commerciaux pc ON pv.code_produit_commercial = pc.code_produit
            ORDER BY pv.annee, pv.semaine, pc.marque, pc.libelle
        """)
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        if rows:
            df = pd.DataFrame(rows)
            numeric_cols = ['annee', 'semaine', 'quantite_prevue_tonnes']
            for col in numeric_cols:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
            return df
        return pd.DataFrame()
    except Exception as e:
        st.error(f"❌ Erreur : {str(e)}")
        return pd.DataFrame()


def save_previsions(df_previsions):
    """Sauvegarde les prévisions (UPSERT)"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        updated = 0
        inserted = 0

        for _, row in df_previsions.iterrows():
            code_produit = row['code_produit']
            annee = int(row['annee'])
            semaine = int(row['semaine'])
            quantite = float(row['quantite']) if pd.notna(row['quantite']) else 0.0

            cursor.execute("""
                SELECT id FROM previsions_ventes
                WHERE code_produit_commercial = %s AND annee = %s AND semaine = %s
            """, (code_produit, annee, semaine))

            existing = cursor.fetchone()

            if existing:
                cursor.execute("""
                    UPDATE previsions_ventes
                    SET quantite_prevue_tonnes = %s, updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                """, (quantite, existing['id']))
                updated += 1
            else:
                cursor.execute("""
                    INSERT INTO previsions_ventes (code_produit_commercial, annee, semaine, quantite_prevue_tonnes)
                    VALUES (%s, %s, %s, %s)
                """, (code_produit, annee, semaine, quantite))
                inserted += 1

        conn.commit()
        cursor.close()
        conn.close()

        return True, f"✅ Enregistré : {updated} mis à jour, {inserted} créés"
    except Exception as e:
        if 'conn' in locals():
            conn.rollback()
        return False, f"❌ Erreur : {str(e)}"


def calculer_tendance_produit(df_hist, code_produit):
    """Calcule la tendance d'évolution pour un produit (moyenne des variations)"""
    df_prod = df_hist[df_hist['code_produit_commercial'] == code_produit].copy()

    if len(df_prod) < 2:
        return None, "Données insuffisantes"

    df_prod = df_prod.sort_values(['annee', 'semaine'])
    df_prod['variation'] = df_prod['quantite_prevue_tonnes'].diff()
    variations = df_prod['variation'].dropna()

    if len(variations) == 0:
        return None, "Pas de variation"

    variation_moyenne = variations.mean()
    variation_pct = (variation_moyenne / df_prod['quantite_prevue_tonnes'].mean() * 100) if df_prod['quantite_prevue_tonnes'].mean() > 0 else 0

    return variation_moyenne, variation_pct


def get_evolution_marque(df_hist, marque):
    """Agrège l'évolution par marque"""
    df_marque = df_hist[df_hist['marque'] == marque].copy()

    if df_marque.empty:
        return pd.DataFrame()

    df_agg = df_marque.groupby(['annee', 'semaine']).agg({
        'quantite_prevue_tonnes': 'sum'
    }).reset_index()

    df_agg['semaine_label'] = df_agg.apply(lambda r: f"S{int(r['semaine']):02d}/{int(r['annee'])}", axis=1)

    return df_agg


# ==========================================
# CALCULS INITIAUX
# ==========================================

semaine_actuelle, annee_actuelle = get_semaine_actuelle()
semaine_courante, semaines_editables = get_semaine_courante_et_editables()
sc_annee, sc_sem = semaine_courante
toutes_semaines = [semaine_courante] + semaines_editables

# Produits
produits = get_produits_commerciaux()

# Prévisions pour toutes les semaines affichées (courante + éditables)
previsions_toutes = get_previsions(toutes_semaines)

# Prévisions pour la semaine courante uniquement (affichage lecture seule)
previsions_courante = get_previsions([semaine_courante])

# Prévisions pour les semaines éditables
previsions_editables = get_previsions(semaines_editables)

# Calcul des estimations (moyenne 3 semaines précédentes) pour les semaines éditables sans valeur
estimations = get_moyenne_3_semaines_precedentes(semaines_editables)

# ==========================================
# KPIs
# ==========================================

if not previsions_toutes.empty and not produits.empty:
    totaux_semaines = {}
    for annee, sem in toutes_semaines:
        mask = (previsions_toutes['annee'] == annee) & (previsions_toutes['semaine'] == sem)
        total = previsions_toutes.loc[mask, 'quantite_prevue_tonnes'].sum()
        totaux_semaines[f"S{sem:02d}"] = float(total) if pd.notna(total) else 0.0

    total_editables = sum(
        totaux_semaines.get(f"S{s:02d}", 0.0)
        for _, s in semaines_editables
    )
    nb_produits_prev = previsions_editables['code_produit_commercial'].nunique() if not previsions_editables.empty else 0

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        val_courante = totaux_semaines.get(f"S{sc_sem:02d}", 0.0)
        st.metric(f"📌 S{sc_sem:02d} (en cours)", f"{val_courante:.0f} T")

    with col2:
        sem1_a, sem1_s = semaines_editables[0]
        val1 = totaux_semaines.get(f"S{sem1_s:02d}", 0.0)
        st.metric(f"📊 S{sem1_s:02d}", f"{val1:.0f} T")

    with col3:
        st.metric("📈 Total 5 sem", f"{total_editables:.0f} T")

    with col4:
        st.metric("📦 Produits saisis", f"{nb_produits_prev}/{len(produits)}")

st.markdown("---")

# ==========================================
# ONGLETS
# ==========================================

tab1, tab2, tab3, tab4 = st.tabs([
    "📝 Saisie (S en cours + 5 semaines)",
    "📊 Vue consolidée",
    "📈 Statistiques",
    "📜 Historique"
])

# ==========================================
# ONGLET 1 : SAISIE
# ==========================================

with tab1:
    st.subheader(f"📝 Saisie des Prévisions — Semaine en cours : S{sc_sem:02d}/{sc_annee}")

    sem_labels_edit = [format_semaine(a, s) for a, s in semaines_editables]
    st.info(
        f"📌 **S{sc_sem:02d}** (lecture seule — semaine en cours) "
        f"| ✏️ **Éditables** : {', '.join(sem_labels_edit)}"
    )

    if produits.empty:
        st.warning("⚠️ Aucun produit commercial trouvé")
    else:
        # Box nouveau produit
        st.markdown("""
        <div class="new-product-box">
            <strong>🆕 Besoin d'ajouter un nouveau produit ?</strong><br>
            Les produits commerciaux se gèrent dans la page <strong>Sources</strong> → Table <strong>Produits Commerciaux</strong>
        </div>
        """, unsafe_allow_html=True)

        col_btn1, col_btn2, col_btn3 = st.columns([1, 1, 2])
        with col_btn1:
            if st.button("➕ Aller à Sources", type="secondary", use_container_width=True):
                st.session_state['source_table_target'] = 'Produits Commerciaux'
                st.switch_page("pages/01_Sources.py")

        st.markdown("---")

        # Légende estimation
        st.markdown("""
        <div class="estimation-legend">
            <strong>~ Estimation</strong> : valeur pré-remplie automatiquement (moyenne des 3 semaines précédentes en base).
            Modifiez-la puis enregistrez pour qu'elle devienne une prévision confirmée (le ~ disparaîtra).
        </div>
        """, unsafe_allow_html=True)

        # ---- Construire le DataFrame de saisie ----
        df_saisie = produits[['code_produit', 'marque', 'libelle']].copy()

        # Colonne semaine courante (lecture seule)
        col_sc = f"S{sc_sem:02d} 🔒"
        df_saisie[col_sc] = 0.0
        if not previsions_courante.empty:
            for idx, row in df_saisie.iterrows():
                mask = (
                    (previsions_courante['code_produit_commercial'] == row['code_produit']) &
                    (previsions_courante['annee'] == sc_annee) &
                    (previsions_courante['semaine'] == sc_sem)
                )
                vals = previsions_courante.loc[mask, 'quantite_prevue_tonnes']
                if len(vals) > 0:
                    df_saisie.loc[idx, col_sc] = float(vals.iloc[0])

        # Colonnes éditables S+1 à S+5
        # On trackera quelles cellules sont des estimations (pas encore en base)
        # via un dict : { col_name : set(code_produit) }
        cellules_estimation = {}

        for annee, sem in semaines_editables:
            col_name = f"S{sem:02d}"
            df_saisie[col_name] = 0.0

            produits_en_base = set()
            if not previsions_editables.empty:
                for idx, row in df_saisie.iterrows():
                    mask = (
                        (previsions_editables['code_produit_commercial'] == row['code_produit']) &
                        (previsions_editables['annee'] == annee) &
                        (previsions_editables['semaine'] == sem)
                    )
                    vals = previsions_editables.loc[mask, 'quantite_prevue_tonnes']
                    if len(vals) > 0:
                        df_saisie.loc[idx, col_name] = float(vals.iloc[0])
                        produits_en_base.add(row['code_produit'])

            # Pour les produits sans valeur en base : pré-remplir avec estimation
            moy_sem = estimations.get((annee, sem), {})
            produits_estimes = set()
            for idx, row in df_saisie.iterrows():
                if row['code_produit'] not in produits_en_base:
                    moy = moy_sem.get(row['code_produit'], 0.0)
                    df_saisie.loc[idx, col_name] = round(moy, 1)
                    if moy > 0:
                        produits_estimes.add(row['code_produit'])

            cellules_estimation[col_name] = produits_estimes

        # Colonne indicateur d'estimation (~) par semaine éditable
        # On crée une colonne "~ Sxx" qui affiche "~" si estimation
        # Ces colonnes sont disabled dans le data_editor
        for annee, sem in semaines_editables:
            col_name = f"S{sem:02d}"
            col_ind = f"~ S{sem:02d}"
            estimes = cellules_estimation.get(col_name, set())
            df_saisie[col_ind] = df_saisie['code_produit'].apply(
                lambda cp: "~" if cp in estimes else ""
            )

        # ---- Filtres ----
        col_f1, col_f2, col_info = st.columns([2, 2, 2])

        with col_f1:
            marques = ["Toutes"] + sorted(df_saisie['marque'].dropna().unique().tolist())
            filtre_marque = st.selectbox("Filtrer par marque", marques, key="filtre_marque_saisie")

        with col_f2:
            libelles = ["Tous"] + sorted(df_saisie['libelle'].dropna().unique().tolist())
            filtre_libelle = st.selectbox("Filtrer par libellé", libelles, key="filtre_libelle_saisie")

        df_filtre = df_saisie.copy()
        if filtre_marque != "Toutes":
            df_filtre = df_filtre[df_filtre['marque'] == filtre_marque]
        if filtre_libelle != "Tous":
            df_filtre = df_filtre[df_filtre['libelle'] == filtre_libelle]

        with col_info:
            nb_estim_total = sum(len(v) for v in cellules_estimation.values())
            st.caption(f"💡 {len(df_filtre)} produits | ~ {nb_estim_total} cellules estimées")

        df_edit = df_filtre.reset_index(drop=True)

        # ---- Configuration colonnes ----
        column_config = {
            "code_produit": st.column_config.TextColumn("Code", disabled=True, width="small"),
            "marque": st.column_config.TextColumn("Marque", disabled=True, width="small"),
            "libelle": st.column_config.TextColumn("Libellé", disabled=True, width="large"),
            col_sc: st.column_config.NumberColumn(
                col_sc,
                disabled=True,
                format="%.1f T",
                help="Semaine en cours — lecture seule"
            ),
        }

        # Colonnes éditables + indicateurs
        for annee, sem in semaines_editables:
            col_name = f"S{sem:02d}"
            col_ind = f"~ S{sem:02d}"
            column_config[col_name] = st.column_config.NumberColumn(
                col_name,
                min_value=0.0,
                max_value=9999.0,
                step=0.5,
                format="%.1f T",
                help=f"Prévision en tonnes pour la semaine {sem}/{annee}"
            )
            column_config[col_ind] = st.column_config.TextColumn(
                "~",
                disabled=True,
                width="small",
                help="~ = estimation automatique (moyenne des 3 sem. précédentes). Disparaît après enregistrement."
            )

        # Ordre des colonnes : code | marque | libelle | S_courante | [S+1, ~S+1, S+2, ~S+2, ...]
        cols_ordre = ["code_produit", "marque", "libelle", col_sc]
        for annee, sem in semaines_editables:
            cols_ordre.append(f"S{sem:02d}")
            cols_ordre.append(f"~ S{sem:02d}")

        df_edit = df_edit[cols_ordre]

        # Tableau éditable
        edited_df = st.data_editor(
            df_edit,
            column_config=column_config,
            use_container_width=True,
            hide_index=True,
            num_rows="fixed",
            key="previsions_editor"
        )

        # ---- Boutons ----
        col1, col2, col3 = st.columns([1, 1, 2])

        with col1:
            if st.button("💾 Enregistrer", type="primary", use_container_width=True):
                records = []
                for _, row in edited_df.iterrows():
                    for annee, sem in semaines_editables:
                        col_name = f"S{sem:02d}"
                        records.append({
                            'code_produit': row['code_produit'],
                            'annee': annee,
                            'semaine': sem,
                            'quantite': row[col_name]
                        })
                df_to_save = pd.DataFrame(records)
                success, msg = save_previsions(df_to_save)
                if success:
                    st.success(msg)
                    st.balloons()
                    st.rerun()
                else:
                    st.error(msg)

        with col2:
            if st.button("🔄 Actualiser", use_container_width=True):
                st.rerun()

        # ---- Totaux ----
        st.markdown("---")
        st.markdown("### 📊 Totaux par semaine")

        totaux = {}
        for annee, sem in semaines_editables:
            col_name = f"S{sem:02d}"
            totaux[col_name] = edited_df[col_name].sum()

        cols_totaux = st.columns(len(totaux) + 1)
        for i, (sem_label, total) in enumerate(totaux.items()):
            with cols_totaux[i]:
                st.metric(sem_label, f"{total:.1f} T")

        with cols_totaux[-1]:
            total_global = sum(totaux.values())
            st.metric("Total 5 sem", f"{total_global:.1f} T")


# ==========================================
# ONGLET 2 : VUE CONSOLIDÉE
# ==========================================

with tab2:
    st.subheader("📊 Vue Consolidée — S en cours + 5 semaines")

    labels_toutes = [f"S{sc_sem:02d} 🔒 (en cours)"] + [format_semaine(a, s) for a, s in semaines_editables]
    st.info(f"📅 {' | '.join(labels_toutes)}")

    if produits.empty:
        st.warning("⚠️ Aucun produit commercial trouvé")
    else:
        df_vue = produits[['code_produit', 'marque', 'libelle']].copy()

        # Semaine courante
        col_sc_vue = f"S{sc_sem:02d} (en cours)"
        df_vue[col_sc_vue] = 0.0
        if not previsions_courante.empty:
            for idx, row in df_vue.iterrows():
                mask = (
                    (previsions_courante['code_produit_commercial'] == row['code_produit']) &
                    (previsions_courante['annee'] == sc_annee) &
                    (previsions_courante['semaine'] == sc_sem)
                )
                vals = previsions_courante.loc[mask, 'quantite_prevue_tonnes']
                if len(vals) > 0:
                    df_vue.loc[idx, col_sc_vue] = float(vals.iloc[0])

        # Semaines éditables
        for annee, sem in semaines_editables:
            col_name = f"S{sem:02d}"
            df_vue[col_name] = 0.0
            if not previsions_editables.empty:
                for idx, row in df_vue.iterrows():
                    mask = (
                        (previsions_editables['code_produit_commercial'] == row['code_produit']) &
                        (previsions_editables['annee'] == annee) &
                        (previsions_editables['semaine'] == sem)
                    )
                    vals = previsions_editables.loc[mask, 'quantite_prevue_tonnes']
                    if len(vals) > 0:
                        df_vue.loc[idx, col_name] = float(vals.iloc[0])
            # Estimation si pas en base
            moy_sem = estimations.get((annee, sem), {})
            for idx, row in df_vue.iterrows():
                if df_vue.loc[idx, col_name] == 0.0:
                    moy = moy_sem.get(row['code_produit'], 0.0)
                    if moy > 0:
                        df_vue.loc[idx, col_name] = round(moy, 1)

        # Total
        cols_sem = [col_sc_vue] + [f"S{s:02d}" for _, s in semaines_editables]
        df_vue['Total 6 sem'] = df_vue[cols_sem].sum(axis=1)

        # Filtres
        col_f1, col_f2 = st.columns(2)
        with col_f1:
            marques = ["Toutes"] + sorted(df_vue['marque'].dropna().unique().tolist())
            filtre_marque_vue = st.selectbox("Filtrer par marque", marques, key="filtre_marque_vue")
        with col_f2:
            libelles = ["Tous"] + sorted(df_vue['libelle'].dropna().unique().tolist())
            filtre_libelle_vue = st.selectbox("Filtrer par libellé", libelles, key="filtre_libelle_vue")

        df_filtre_vue = df_vue.copy()
        if filtre_marque_vue != "Toutes":
            df_filtre_vue = df_filtre_vue[df_filtre_vue['marque'] == filtre_marque_vue]
        if filtre_libelle_vue != "Tous":
            df_filtre_vue = df_filtre_vue[df_filtre_vue['libelle'] == filtre_libelle_vue]

        column_config_vue = {
            "code_produit": st.column_config.TextColumn("Code", width="small"),
            "marque": st.column_config.TextColumn("Marque", width="small"),
            "libelle": st.column_config.TextColumn("Libellé", width="large"),
            col_sc_vue: st.column_config.NumberColumn(col_sc_vue, format="%.1f T"),
            "Total 6 sem": st.column_config.NumberColumn("Total 6 sem", format="%.1f T"),
        }
        for annee, sem in semaines_editables:
            col_name = f"S{sem:02d}"
            column_config_vue[col_name] = st.column_config.NumberColumn(col_name, format="%.1f T")

        st.dataframe(
            df_filtre_vue,
            column_config=column_config_vue,
            use_container_width=True,
            hide_index=True
        )

        # Totaux
        st.markdown("---")
        st.markdown("### 📊 Totaux par semaine")

        nb_cols = len(toutes_semaines) + 1
        cols_tot = st.columns(nb_cols)

        with cols_tot[0]:
            total_sc = df_vue[col_sc_vue].sum()
            st.metric(f"S{sc_sem:02d} 🔒", f"{total_sc:.0f} T")

        for i, (annee, sem) in enumerate(semaines_editables):
            col_name = f"S{sem:02d}"
            total = df_vue[col_name].sum()
            with cols_tot[i + 1]:
                st.metric(col_name, f"{total:.0f} T")

        with cols_tot[-1]:
            total_global = df_vue['Total 6 sem'].sum()
            st.metric("🎯 Total", f"{total_global:.0f} T")

        st.caption("~ Les valeurs sans saisie confirmée sont estimées à partir de la moyenne des 3 semaines précédentes.")


# ==========================================
# ONGLET 3 : STATISTIQUES
# ==========================================

with tab3:
    st.subheader("📈 Statistiques Détaillées")

    hist_complet = get_previsions_historique_complet()

    if hist_complet.empty:
        st.info("📭 Aucune donnée historique trouvée")
    else:
        hist_complet['semaine_label'] = hist_complet.apply(
            lambda r: f"S{int(r['semaine']):02d}/{int(r['annee'])}", axis=1
        )

        st.markdown("### 📊 Vue d'ensemble")

        col1, col2, col3, col4 = st.columns(4)

        with col1:
            nb_semaines_total = hist_complet[['annee', 'semaine']].drop_duplicates().shape[0]
            st.metric("📅 Semaines", nb_semaines_total)

        with col2:
            volume_total = hist_complet['quantite_prevue_tonnes'].sum()
            st.metric("📦 Volume Total", f"{volume_total:.0f} T")

        with col3:
            moy_semaine = volume_total / nb_semaines_total if nb_semaines_total > 0 else 0
            st.metric("📊 Moy/Semaine", f"{moy_semaine:.0f} T")

        with col4:
            nb_produits = hist_complet['code_produit_commercial'].nunique()
            st.metric("🏷️ Produits", nb_produits)

        st.markdown("---")
        st.markdown("### 🔍 Analyse détaillée")

        col_sel1, col_sel2 = st.columns(2)

        with col_sel1:
            type_analyse = st.radio(
                "Type d'analyse",
                ["Par Produit", "Par Marque"],
                horizontal=True,
                key="type_analyse"
            )

        if type_analyse == "Par Produit":
            with col_sel2:
                produits_dispo = sorted(hist_complet[['code_produit_commercial', 'libelle']].drop_duplicates().apply(
                    lambda r: f"{r['code_produit_commercial']} - {r['libelle']}", axis=1
                ).tolist())

                if produits_dispo:
                    produit_selectionne = st.selectbox(
                        "Sélectionner un produit",
                        produits_dispo,
                        key="produit_stats"
                    )

                    code_produit = produit_selectionne.split(" - ")[0]
                    df_produit = hist_complet[hist_complet['code_produit_commercial'] == code_produit].copy()
                    df_produit = df_produit.sort_values(['annee', 'semaine'])

                    st.markdown("#### 📈 Évolution dans le temps")

                    fig = px.line(
                        df_produit,
                        x='semaine_label',
                        y='quantite_prevue_tonnes',
                        title=f"Évolution des prévisions - {produit_selectionne}",
                        labels={'semaine_label': 'Semaine', 'quantite_prevue_tonnes': 'Quantité (T)'},
                        markers=True
                    )
                    fig.update_layout(xaxis_tickangle=-45, height=400)
                    st.plotly_chart(fig, use_container_width=True)

                    st.markdown("#### 📊 Métriques")

                    col_m1, col_m2, col_m3, col_m4 = st.columns(4)

                    with col_m1:
                        total_produit = df_produit['quantite_prevue_tonnes'].sum()
                        st.metric("Volume Total", f"{total_produit:.1f} T")

                    with col_m2:
                        moy_produit = df_produit['quantite_prevue_tonnes'].mean()
                        st.metric("Moyenne", f"{moy_produit:.1f} T")

                    with col_m3:
                        max_produit = df_produit['quantite_prevue_tonnes'].max()
                        st.metric("Maximum", f"{max_produit:.1f} T")

                    with col_m4:
                        min_produit = df_produit['quantite_prevue_tonnes'].min()
                        st.metric("Minimum", f"{min_produit:.1f} T")

                    variation_moy, variation_pct = calculer_tendance_produit(hist_complet, code_produit)

                    if variation_moy is not None:
                        st.markdown("#### 📉 Tendance")

                        col_t1, col_t2 = st.columns(2)

                        with col_t1:
                            tendance_color = "normal" if abs(variation_pct) < 5 else ("inverse" if variation_pct < 0 else "normal")
                            st.metric(
                                "Variation moyenne",
                                f"{variation_moy:+.2f} T/semaine",
                                delta=f"{variation_pct:+.1f}%",
                                delta_color=tendance_color
                            )

                        with col_t2:
                            if variation_pct > 5:
                                st.success("📈 Tendance à la hausse")
                            elif variation_pct < -5:
                                st.warning("📉 Tendance à la baisse")
                            else:
                                st.info("➡️ Tendance stable")
                    else:
                        st.info("📊 Données insuffisantes pour calculer la tendance")

        else:  # Par Marque
            with col_sel2:
                marques_dispo = sorted(hist_complet['marque'].dropna().unique().tolist())

                if marques_dispo:
                    marque_selectionnee = st.selectbox(
                        "Sélectionner une marque",
                        marques_dispo,
                        key="marque_stats"
                    )

                    df_marque_agg = get_evolution_marque(hist_complet, marque_selectionnee)

                    if not df_marque_agg.empty:
                        fig_marque = px.line(
                            df_marque_agg,
                            x='semaine_label',
                            y='quantite_prevue_tonnes',
                            title=f"Évolution — {marque_selectionnee}",
                            labels={'semaine_label': 'Semaine', 'quantite_prevue_tonnes': 'Quantité (T)'},
                            markers=True
                        )
                        fig_marque.update_layout(xaxis_tickangle=-45, height=400)
                        st.plotly_chart(fig_marque, use_container_width=True)

                        # Répartition par produit
                        repartition = hist_complet[hist_complet['marque'] == marque_selectionnee].groupby('libelle').agg(
                            quantite_prevue_tonnes=('quantite_prevue_tonnes', 'sum')
                        ).reset_index()

                        fig_pie = px.pie(
                            repartition,
                            values='quantite_prevue_tonnes',
                            names='libelle',
                            title=f"Répartition des volumes - {marque_selectionnee}"
                        )
                        st.plotly_chart(fig_pie, use_container_width=True)
                    else:
                        st.warning("⚠️ Aucune donnée pour cette marque")


# ==========================================
# ONGLET 4 : HISTORIQUE
# ==========================================

with tab4:
    st.subheader("📜 Historique des Prévisions")

    hist_complet_tab4 = get_previsions_historique_complet()

    if hist_complet_tab4.empty:
        st.info("📭 Aucune prévision trouvée")
    else:
        hist_complet_tab4['semaine_label'] = hist_complet_tab4.apply(
            lambda r: f"S{int(r['semaine']):02d}/{int(r['annee'])}", axis=1
        )

        col1, col2 = st.columns(2)

        with col1:
            annees = ["Toutes"] + sorted(hist_complet_tab4['annee'].unique().tolist(), reverse=True)
            filtre_annee = st.selectbox("Année", annees, key="filtre_annee_hist")

        with col2:
            semaines_hist = ["Toutes"] + sorted(hist_complet_tab4['semaine'].unique().tolist(), reverse=True)
            filtre_semaine = st.selectbox("Semaine", semaines_hist, key="filtre_semaine_hist")

        df_hist = hist_complet_tab4.copy()
        if filtre_annee != "Toutes":
            df_hist = df_hist[df_hist['annee'] == filtre_annee]
        if filtre_semaine != "Toutes":
            df_hist = df_hist[df_hist['semaine'] == filtre_semaine]

        df_display_hist = df_hist[['semaine_label', 'marque', 'libelle', 'quantite_prevue_tonnes']].copy()
        df_display_hist = df_display_hist.rename(columns={
            'semaine_label': 'Semaine',
            'marque': 'Marque',
            'libelle': 'Libellé',
            'quantite_prevue_tonnes': 'Quantité (T)'
        })

        st.dataframe(df_display_hist, use_container_width=True, hide_index=True)

        st.markdown("---")
        st.markdown("### 📊 Statistiques Historique")

        col1, col2, col3 = st.columns(3)

        with col1:
            nb_semaines = df_hist[['annee', 'semaine']].drop_duplicates().shape[0]
            st.metric("Semaines", nb_semaines)

        with col2:
            total_hist = df_hist['quantite_prevue_tonnes'].sum()
            st.metric("Volume Total", f"{total_hist:.0f} T")

        with col3:
            moy_semaine = total_hist / nb_semaines if nb_semaines > 0 else 0
            st.metric("Moyenne/Semaine", f"{moy_semaine:.0f} T")


# ==========================================
# FOOTER
# ==========================================

show_footer()
