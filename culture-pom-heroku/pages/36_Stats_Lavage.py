import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, date
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import io
from database import get_connection
from components import show_footer
from auth import require_access

# ============================================================
# CONFIG PAGE
# ============================================================
st.set_page_config(page_title="Stats Lavage", page_icon="📊", layout="wide")
st.markdown("""<style>
    .block-container{padding-top:1.5rem!important;padding-bottom:0.5rem!important;
        padding-left:2rem!important;padding-right:2rem!important;}
    h1,h2,h3,h4{margin-top:0.3rem!important;margin-bottom:0.3rem!important;}
    [data-testid="stMetricValue"]{font-size:1.3rem!important;}
    hr{margin-top:0.4rem!important;margin-bottom:0.4rem!important;}
    .kpi-good{color:#2e7d32;font-weight:bold;}
    .kpi-warn{color:#f57c00;font-weight:bold;}
    .kpi-bad{color:#c62828;font-weight:bold;}
</style>""", unsafe_allow_html=True)

require_access("PRODUCTION")

# ============================================================
# COULEURS PROJET
# ============================================================
C_LAVE   = "#AFCA0A"
C_DECH   = "#e53935"
C_GREN   = "#f57c00"
C_TERRE  = "#795548"
C_OBJ    = "#1976d2"
C_BG     = "#f5f5f5"

# ============================================================
# UTILITAIRES
# ============================================================

def clean_variete(v):
    """Normalise une variété : strip + upper"""
    if pd.isna(v):
        return "INCONNUE"
    return str(v).strip().upper()

def safe_pct(num, den, default=0.0):
    if den and den > 0:
        return num / den * 100
    return default

def badge_rendement(r):
    if r >= 85: return "🟢"
    if r >= 75: return "🟡"
    return "🔴"

def kpi_delta(val, ref, unit="%", invert=False):
    """Retourne (delta_str, color)"""
    if ref is None or ref == 0:
        return "", "normal"
    delta = val - ref
    pct = delta / abs(ref) * 100
    sign = "+" if delta >= 0 else ""
    worse = delta > 0 if invert else delta < 0
    color = "inverse" if worse else "normal"
    return f"{sign}{pct:.1f}%", color

# ============================================================
# FONCTIONS IMPORT FICHIER
# ============================================================

@st.cache_data(show_spinner=False)
def charger_fichier_excel(file_bytes):
    """Charge et nettoie le fichier Excel historique"""
    df = pd.read_excel(io.BytesIO(file_bytes),
                       sheet_name='Saisi des données écarts de tri')

    # Nettoyage colonnes
    df = df.rename(columns={
        'SEM': 'semaine',
        'D': 'date',
        'ANNEES': 'annee',
        'VARIETE': 'variete',
        'Unnamed: 4': 'producteur',
        'NBR PALOX TRAVAILLE': 'pallox',
        'POIDS MOY PAL SALE': 'poids_moy_sale',
        'POIDS A LAVER': 'poids_brut',
        'POIDS DECHETS (KG)': 'poids_dechets',
        'GRENAILLES (KG)': 'poids_grenailles',
        'NBR PALOX LAVEE': 'pallox_laves',
        'POIDS MOY PAL LAVE': 'poids_moy_lave',
        'POIDS LAVE': 'poids_lave',
        'TERRE (KG)': 'poids_terre',
        'OBSERVATION': 'observation',
    })

    # Normalisation
    df['variete']    = df['variete'].apply(clean_variete)
    df['producteur'] = df['producteur'].apply(lambda x: str(x).strip().upper() if pd.notna(x) else '')
    df['date']       = pd.to_datetime(df['date'], errors='coerce')
    df['annee']      = pd.to_numeric(df['annee'], errors='coerce')
    df['semaine']    = pd.to_numeric(df['semaine'], errors='coerce')

    # Filtrer données exploitables (annee valide >= 2020, poids_brut renseigné)
    df = df[df['annee'] >= 2020].copy()
    df = df[df['poids_brut'].notna() & (df['poids_brut'] > 0)].copy()

    # Colonnes numériques
    num_cols = ['pallox','poids_moy_sale','poids_brut','poids_dechets','poids_grenailles',
                'pallox_laves','poids_moy_lave','poids_lave','poids_terre']
    for c in num_cols:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0)

    # Calculs dérivés
    df['rendement_pct']  = np.where(df['poids_brut'] > 0, df['poids_lave']  / df['poids_brut'] * 100, np.nan)
    df['pct_dechets']    = np.where(df['poids_brut'] > 0, df['poids_dechets'] / df['poids_brut'] * 100, np.nan)
    df['pct_grenailles'] = np.where(df['poids_brut'] > 0, df['poids_grenailles'] / df['poids_brut'] * 100, np.nan)
    df['pct_terre']      = np.where(df['poids_brut'] > 0, df['poids_terre']  / df['poids_brut'] * 100, np.nan)

    # Clip rendement aberrant
    df['rendement_pct']  = df['rendement_pct'].clip(0, 110)
    df['pct_dechets']    = df['pct_dechets'].clip(0, 100)
    df['pct_grenailles'] = df['pct_grenailles'].clip(0, 100)
    df['pct_terre']      = df['pct_terre'].clip(0, 100)

    return df


# ============================================================
# FONCTIONS DONNÉES POMI (BDD)
# ============================================================

@st.cache_data(ttl=120, show_spinner=False)
def get_jobs_termines_pomi():
    """Récupère tous les jobs TERMINÉ avec leurs données de résultat"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT
                lj.id,
                lj.code_lot_interne,
                lj.variete,
                COALESCE(p.nom, lj.producteur) as producteur,
                lj.ligne_lavage,
                lj.statut_source,
                lj.quantite_pallox,
                lj.poids_brut_kg,
                lj.poids_lave_net_kg,
                lj.poids_grenailles_kg,
                lj.poids_dechets_kg,
                lj.poids_terre_calcule_kg,
                lj.rendement_pct,
                lj.tare_reelle_pct,
                lj.temps_estime_heures,
                lj.capacite_th,
                lj.date_prevue,
                lj.date_activation,
                lj.date_terminaison,
                lj.notes
            FROM lavages_jobs lj
            LEFT JOIN lots_bruts lb ON lj.lot_id = lb.id
            LEFT JOIN ref_producteurs p ON lb.code_producteur = p.code_producteur
            WHERE lj.statut = 'TERMINÉ'
              AND lj.poids_brut_kg > 0
            ORDER BY lj.date_terminaison DESC
        """)
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        if rows:
            df = pd.DataFrame([dict(r) for r in rows])
            num_cols = ['poids_brut_kg','poids_lave_net_kg','poids_grenailles_kg',
                        'poids_dechets_kg','poids_terre_calcule_kg','rendement_pct',
                        'tare_reelle_pct','temps_estime_heures','capacite_th','quantite_pallox']
            for c in num_cols:
                if c in df.columns:
                    df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0)
            df['date_terminaison'] = pd.to_datetime(df['date_terminaison'], errors='coerce')
            df['date_activation']  = pd.to_datetime(df['date_activation'],  errors='coerce')
            df['date_prevue']      = pd.to_datetime(df['date_prevue'],       errors='coerce')
            # Colonnes calculées
            df['semaine'] = df['date_terminaison'].dt.isocalendar().week.astype('Int64')
            df['annee']   = df['date_terminaison'].dt.year
            df['date']    = df['date_terminaison'].dt.normalize()
            # Temps réel (minutes)
            df['temps_reel_min'] = (df['date_terminaison'] - df['date_activation']).dt.total_seconds() / 60
            df['temps_reel_h']   = df['temps_reel_min'] / 60
            # Cadence réelle T/h
            df['cadence_reelle'] = np.where(
                df['temps_reel_h'] > 0,
                df['poids_brut_kg'] / 1000 / df['temps_reel_h'],
                np.nan
            )
            # Renommage pour cohérence avec onglet fichier
            df['poids_brut']      = df['poids_brut_kg']
            df['poids_lave']      = df['poids_lave_net_kg']
            df['poids_dechets']   = df['poids_dechets_kg']
            df['poids_grenailles']= df['poids_grenailles_kg']
            df['poids_terre']     = df['poids_terre_calcule_kg']
            df['pallox']          = df['quantite_pallox']
            df['pct_dechets']     = np.where(df['poids_brut'] > 0, df['poids_dechets'] / df['poids_brut'] * 100, np.nan)
            df['pct_grenailles']  = np.where(df['poids_brut'] > 0, df['poids_grenailles'] / df['poids_brut'] * 100, np.nan)
            df['pct_terre']       = np.where(df['poids_brut'] > 0, df['poids_terre'] / df['poids_brut'] * 100, np.nan)
            return df
        return pd.DataFrame()
    except Exception as e:
        st.error(f"❌ Erreur chargement POMI : {str(e)}")
        return pd.DataFrame()


# ============================================================
# FONCTIONS GRAPHIQUES (partagées onglet 1 et 2)
# ============================================================

def chart_volumes_hebdo(df_semaines):
    """Histogramme empilé volumes par semaine"""
    fig = go.Figure()
    fig.add_bar(name="Lavé", x=df_semaines['label'], y=df_semaines['poids_lave']/1000,
                marker_color=C_LAVE)
    fig.add_bar(name="Déchets", x=df_semaines['label'], y=df_semaines['poids_dechets']/1000,
                marker_color=C_DECH)
    fig.add_bar(name="Grenailles", x=df_semaines['label'], y=df_semaines['poids_grenailles']/1000,
                marker_color=C_GREN)
    fig.add_bar(name="Terre", x=df_semaines['label'], y=df_semaines['poids_terre']/1000,
                marker_color=C_TERRE)
    fig.update_layout(barmode='stack', height=320,
                      title="Évolution hebdomadaire des volumes (T)",
                      yaxis_title="Tonnes", xaxis_title="",
                      margin=dict(l=0,r=0,t=35,b=0), legend=dict(orientation="h",y=-0.15))
    return fig

def chart_rendements_hebdo(df_semaines):
    """Ligne rendement + barres % déchets/grenailles"""
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_bar(name="% Déchets", x=df_semaines['label'], y=df_semaines['pct_dechets'],
                marker_color=C_DECH, opacity=0.7, secondary_y=False)
    fig.add_bar(name="% Grenailles", x=df_semaines['label'], y=df_semaines['pct_grenailles'],
                marker_color=C_GREN, opacity=0.7, secondary_y=False)
    fig.add_scatter(name="Rendement %", x=df_semaines['label'], y=df_semaines['rendement_pct'],
                    mode='lines+markers', line=dict(color=C_LAVE, width=3),
                    marker=dict(size=8), secondary_y=True)
    fig.update_yaxes(title_text="% Déchets / Grenailles", secondary_y=False, range=[0, 30])
    fig.update_yaxes(title_text="Rendement %", secondary_y=True, range=[50, 100])
    fig.update_layout(height=320, barmode='group',
                      title="Rendement & Taux déchets/grenailles par semaine",
                      margin=dict(l=0,r=0,t=35,b=0), legend=dict(orientation="h",y=-0.15))
    return fig

def chart_rendement_varietes(df_var):
    """Barres horizontales rendement par variété"""
    df_s = df_var.sort_values('rendement_pct')
    colors = [C_LAVE if r >= 85 else C_GREN if r >= 75 else C_DECH
              for r in df_s['rendement_pct']]
    fig = go.Figure(go.Bar(
        x=df_s['rendement_pct'], y=df_s['variete'],
        orientation='h', marker_color=colors,
        text=df_s['rendement_pct'].apply(lambda x: f"{x:.1f}%"),
        textposition='outside'
    ))
    fig.add_vline(x=80, line_dash="dash", line_color="gray", annotation_text="Obj 80%")
    fig.update_layout(height=max(280, len(df_s)*30),
                      title="Rendement par variété (%)",
                      xaxis=dict(range=[0,105]), margin=dict(l=0,r=0,t=35,b=0))
    return fig

def chart_decompo_varietes(df_var):
    """Barres empilées % déchets + grenailles + terre par variété"""
    df_s = df_var.sort_values('rendement_pct', ascending=False)
    fig = go.Figure()
    fig.add_bar(name="% Déchets",    x=df_s['variete'], y=df_s['pct_dechets'],    marker_color=C_DECH)
    fig.add_bar(name="% Grenailles", x=df_s['variete'], y=df_s['pct_grenailles'], marker_color=C_GREN)
    fig.add_bar(name="% Terre",      x=df_s['variete'], y=df_s['pct_terre'],      marker_color=C_TERRE)
    fig.update_layout(barmode='stack', height=320,
                      title="Décomposition des pertes par variété (%)",
                      yaxis_title="%", margin=dict(l=0,r=0,t=35,b=0),
                      legend=dict(orientation="h",y=-0.15))
    return fig

def chart_journalier(df_jours):
    """Volumes + rendement journaliers"""
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_bar(name="Poids à laver", x=df_jours['date_str'],
                y=df_jours['poids_brut']/1000, marker_color="#90a4ae", secondary_y=False)
    fig.add_bar(name="Poids lavé",    x=df_jours['date_str'],
                y=df_jours['poids_lave']/1000, marker_color=C_LAVE, secondary_y=False)
    fig.add_scatter(name="Rendement %", x=df_jours['date_str'], y=df_jours['rendement_pct'],
                    mode='lines+markers', line=dict(color=C_OBJ, width=2),
                    marker=dict(size=7), secondary_y=True)
    fig.update_yaxes(title_text="Tonnes", secondary_y=False)
    fig.update_yaxes(title_text="Rendement %", secondary_y=True, range=[50,100])
    fig.update_layout(height=320, barmode='group',
                      title="Volumes journaliers — Lavé vs À laver",
                      margin=dict(l=0,r=0,t=35,b=0), legend=dict(orientation="h",y=-0.15))
    return fig

def chart_cadence(df_jours, objectif_th=13.0, heures_jour=13.0):
    """Cadence réalisée vs objectif"""
    obj_jour = objectif_th * heures_jour
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_bar(name="Cadence (T/h)", x=df_jours['date_str'], y=df_jours['cadence'],
                marker_color=C_LAVE, secondary_y=False)
    fig.add_hline(y=objectif_th, line_dash="dash", line_color=C_OBJ,
                  annotation_text=f"Obj {objectif_th} T/h")
    fig.update_yaxes(title_text="T/h", secondary_y=False)
    fig.update_layout(height=280, title="Cadence réalisée vs Objectif (T/h)",
                      margin=dict(l=0,r=0,t=35,b=0))
    return fig

def chart_evolution_varietes(df_evol):
    """Lignes évolution rendement par variété sur semaines"""
    fig = px.line(df_evol, x='label', y='rendement_pct', color='variete',
                  markers=True, title="Évolution rendements par variété",
                  labels={'label': 'Semaine', 'rendement_pct': 'Rendement %', 'variete': 'Variété'},
                  height=350)
    fig.add_hline(y=80, line_dash="dash", line_color="gray", annotation_text="Obj 80%")
    fig.update_layout(margin=dict(l=0,r=0,t=35,b=0), legend=dict(orientation="h",y=-0.2))
    return fig


# ============================================================
# BLOC ANALYSE COMMUN (utilisé par onglet 1 et onglet 2)
# ============================================================

def afficher_analyse(df, source="fichier", objectif_th=13.0, heures_jour=13.0):
    """
    Affiche l'analyse complète à partir d'un DataFrame normalisé.
    Colonnes attendues : semaine, annee, date, variete, producteur, pallox,
        poids_brut, poids_lave, poids_dechets, poids_grenailles, poids_terre,
        rendement_pct, pct_dechets, pct_grenailles, pct_terre
    Pour source='pomi' : colonnes supplémentaires cadence_reelle, temps_reel_h, code_lot_interne
    """
    if df.empty:
        st.info("Aucune donnée à afficher.")
        return

    # ========== FILTRES ==========
    col_f1, col_f2, col_f3 = st.columns(3)
    annees_dispo = sorted(df['annee'].dropna().unique().tolist(), reverse=True)
    annees_dispo_int = [int(a) for a in annees_dispo]

    with col_f1:
        annee_sel = st.selectbox("Année", annees_dispo_int,
                                  key=f"annee_{source}")
    df_ann = df[df['annee'] == annee_sel].copy()
    semaines_dispo = sorted(df_ann['semaine'].dropna().unique().tolist())

    with col_f2:
        sem_min, sem_max = int(min(semaines_dispo)), int(max(semaines_dispo))
        if sem_min == sem_max:
            sems_sel = [sem_min]
            st.info(f"Semaine {sem_min} uniquement")
        else:
            sems_sel = st.select_slider(
                "Semaines",
                options=semaines_dispo,
                value=(sem_min, sem_max),
                key=f"sems_{source}"
            )
            if isinstance(sems_sel, (int, float)):
                sems_sel = (sems_sel, sems_sel)
            sems_sel = list(range(int(sems_sel[0]), int(sems_sel[1]) + 1))

    df_filt = df_ann[df_ann['semaine'].isin(sems_sel)].copy()

    with col_f3:
        varietes_dispo = ["Toutes"] + sorted(df_filt['variete'].dropna().unique().tolist())
        var_sel = st.multiselect("Variétés", varietes_dispo[1:],
                                  key=f"var_{source}",
                                  placeholder="Toutes les variétés")
    if var_sel:
        df_filt = df_filt[df_filt['variete'].isin(var_sel)].copy()

    if df_filt.empty:
        st.warning("Aucune donnée avec ces filtres.")
        return

    st.markdown("---")

    # ========== ONGLETS ANALYSE ==========
    t1, t2, t3, t4, t5 = st.tabs([
        "📈 Vue hebdomadaire",
        "📅 Vue journalière",
        "🌱 Par variété",
        "📦 Par lot",
        "📋 Tableau détaillé"
    ])

    # ─────────────────────────────────────────
    # TAB 1 : VUE HEBDOMADAIRE
    # ─────────────────────────────────────────
    with t1:
        # Agrégation par semaine
        df_sem = df_filt.groupby('semaine').agg(
            poids_brut=('poids_brut', 'sum'),
            poids_lave=('poids_lave', 'sum'),
            poids_dechets=('poids_dechets', 'sum'),
            poids_grenailles=('poids_grenailles', 'sum'),
            poids_terre=('poids_terre', 'sum'),
            pallox=('pallox', 'sum'),
            nb_lignes=('poids_brut', 'count'),
        ).reset_index()
        df_sem['rendement_pct']  = df_sem['poids_lave']  / df_sem['poids_brut'] * 100
        df_sem['pct_dechets']    = df_sem['poids_dechets']    / df_sem['poids_brut'] * 100
        df_sem['pct_grenailles'] = df_sem['poids_grenailles'] / df_sem['poids_brut'] * 100
        df_sem['pct_terre']      = df_sem['poids_terre']      / df_sem['poids_brut'] * 100
        df_sem['label']          = "S" + df_sem['semaine'].astype(str)
        df_sem = df_sem.sort_values('semaine')

        # KPIs de la dernière semaine sélectionnée
        sem_ref = df_sem.iloc[-1] if len(df_sem) > 0 else None
        sem_prec = df_sem.iloc[-2] if len(df_sem) > 1 else None

        if sem_ref is not None:
            col1, col2, col3, col4, col5, col6 = st.columns(6)
            lave_t = sem_ref['poids_lave'] / 1000
            ref_lave = sem_prec['poids_lave'] / 1000 if sem_prec is not None else None
            delta_lave, d_col = kpi_delta(lave_t, ref_lave)
            col1.metric("🧼 Tonnes lavées", f"{lave_t:.1f} T",
                        delta=delta_lave if delta_lave else None, delta_color=d_col)

            col2.metric("📦 Pallox traités", f"{int(sem_ref['pallox'])}")

            rend = sem_ref['rendement_pct']
            ref_rend = sem_prec['rendement_pct'] if sem_prec is not None else None
            delta_rend, d_col2 = kpi_delta(rend, ref_rend)
            col3.metric("📈 Rendement", f"{rend:.1f}%",
                        delta=delta_rend if delta_rend else None, delta_color=d_col2)

            dech = sem_ref['pct_dechets']
            ref_dech = sem_prec['pct_dechets'] if sem_prec is not None else None
            delta_dech, d_col3 = kpi_delta(dech, ref_dech, invert=True)
            col4.metric("🗑️ % Déchets", f"{dech:.1f}%",
                        delta=delta_dech if delta_dech else None, delta_color=d_col3)

            gren = sem_ref['pct_grenailles']
            col5.metric("🌾 % Grenailles", f"{gren:.1f}%")

            brut_t = sem_ref['poids_brut'] / 1000
            col6.metric("⚖️ Tonnes brut", f"{brut_t:.1f} T")

        st.markdown("---")

        # Graphiques côte à côte
        col_g1, col_g2 = st.columns(2)
        with col_g1:
            st.plotly_chart(chart_volumes_hebdo(df_sem), use_container_width=True)
        with col_g2:
            st.plotly_chart(chart_rendements_hebdo(df_sem), use_container_width=True)

        # Tableau récap semaines
        st.markdown("#### Tableau récapitulatif par semaine")
        df_tab = df_sem[['label','poids_brut','poids_lave','poids_dechets',
                          'poids_grenailles','poids_terre','pallox',
                          'rendement_pct','pct_dechets','pct_grenailles','pct_terre']].copy()
        for c in ['poids_brut','poids_lave','poids_dechets','poids_grenailles','poids_terre']:
            df_tab[c] = (df_tab[c] / 1000).round(1)
        for c in ['rendement_pct','pct_dechets','pct_grenailles','pct_terre']:
            df_tab[c] = df_tab[c].round(1)
        df_tab = df_tab.rename(columns={
            'label':'Semaine','poids_brut':'Brut (T)','poids_lave':'Lavé (T)',
            'poids_dechets':'Déchets (T)','poids_grenailles':'Gren. (T)',
            'poids_terre':'Terre (T)','pallox':'Pallox',
            'rendement_pct':'Rend %','pct_dechets':'%Déch',
            'pct_grenailles':'%Gren','pct_terre':'%Terre'
        })
        st.dataframe(df_tab, use_container_width=True, hide_index=True)

        # Évolution multi-semaines par variété (si > 1 semaine)
        if len(df_sem) > 1:
            st.markdown("#### Évolution rendements par variété")
            df_evol = df_filt.groupby(['semaine','variete']).agg(
                poids_brut=('poids_brut','sum'), poids_lave=('poids_lave','sum')
            ).reset_index()
            df_evol['rendement_pct'] = df_evol['poids_lave'] / df_evol['poids_brut'] * 100
            df_evol['label'] = "S" + df_evol['semaine'].astype(str)
            # Garder variétés avec au moins 2 occurrences
            var_multi = df_evol.groupby('variete').size()
            var_multi = var_multi[var_multi >= 2].index.tolist()
            df_evol = df_evol[df_evol['variete'].isin(var_multi)]
            if not df_evol.empty:
                st.plotly_chart(chart_evolution_varietes(df_evol), use_container_width=True)

    # ─────────────────────────────────────────
    # TAB 2 : VUE JOURNALIÈRE
    # ─────────────────────────────────────────
    with t2:
        df_filt['date_dt'] = pd.to_datetime(df_filt['date'], errors='coerce')
        df_jour = df_filt.groupby('date_dt').agg(
            poids_brut=('poids_brut','sum'),
            poids_lave=('poids_lave','sum'),
            poids_dechets=('poids_dechets','sum'),
            poids_grenailles=('poids_grenailles','sum'),
            poids_terre=('poids_terre','sum'),
            pallox=('pallox','sum'),
        ).reset_index().sort_values('date_dt')
        df_jour['rendement_pct']  = df_jour['poids_lave']  / df_jour['poids_brut'] * 100
        df_jour['pct_dechets']    = df_jour['poids_dechets']    / df_jour['poids_brut'] * 100
        df_jour['pct_grenailles'] = df_jour['poids_grenailles'] / df_jour['poids_brut'] * 100
        df_jour['date_str']       = df_jour['date_dt'].dt.strftime('%d/%m')

        # Cadence : T/h = poids_brut / 1000 / heures_jour
        df_jour['cadence'] = df_jour['poids_brut'] / 1000 / heures_jour

        col_g1, col_g2 = st.columns(2)
        with col_g1:
            st.plotly_chart(chart_journalier(df_jour), use_container_width=True)
        with col_g2:
            st.plotly_chart(chart_cadence(df_jour, objectif_th, heures_jour),
                            use_container_width=True)

        # Tableau journalier détaillé
        st.markdown("#### Détail journalier")
        df_jtab = df_jour[['date_str','pallox','poids_brut','poids_lave',
                             'rendement_pct','pct_dechets','pct_grenailles',
                             'pct_terre','cadence']].copy()
        for c in ['poids_brut','poids_lave']:
            df_jtab[c] = (df_jtab[c] / 1000).round(1)
        for c in ['rendement_pct','pct_dechets','pct_grenailles','pct_terre','cadence']:
            df_jtab[c] = df_jtab[c].round(1)
        df_jtab = df_jtab.rename(columns={
            'date_str':'Date','pallox':'Pallox',
            'poids_brut':'Brut (T)','poids_lave':'Lavé (T)',
            'rendement_pct':'Rend %','pct_dechets':'%Déch',
            'pct_grenailles':'%Gren','pct_terre':'%Terre',
            'cadence':'Cad. T/h'
        })
        st.dataframe(df_jtab, use_container_width=True, hide_index=True)

        # Objectif cadence personnalisable
        st.markdown("---")
        col_obj1, col_obj2 = st.columns(2)
        with col_obj1:
            obj_custom = st.number_input("⚡ Objectif cadence (T/h)", 1.0, 30.0,
                                          objectif_th, 0.5, key=f"obj_{source}")
        with col_obj2:
            h_custom = st.number_input("⏱️ Heures de marche / jour", 1.0, 24.0,
                                        heures_jour, 0.5, key=f"hj_{source}")
        obj_jour_t = obj_custom * h_custom
        cum_lave = df_jour['poids_lave'].sum() / 1000
        cum_obj  = obj_jour_t * len(df_jour)
        ecart_pct = (cum_lave / cum_obj - 1) * 100 if cum_obj > 0 else 0
        cadence_moy = (df_jour['poids_brut'].sum() / 1000) / (h_custom * len(df_jour)) if len(df_jour) > 0 else 0
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Obj. volume période", f"{cum_obj:.0f} T")
        col2.metric("Volume réalisé", f"{cum_lave:.1f} T",
                    delta=f"{ecart_pct:+.1f}%",
                    delta_color="normal" if ecart_pct >= 0 else "inverse")
        col3.metric("Cadence moy. réalisée", f"{cadence_moy:.2f} T/h")
        col4.metric("Meilleur jour",
                    f"{df_jour['poids_lave'].max()/1000:.1f} T" if not df_jour.empty else "N/A")

    # ─────────────────────────────────────────
    # TAB 3 : PAR VARIÉTÉ
    # ─────────────────────────────────────────
    with t3:
        df_var = df_filt.groupby('variete').agg(
            poids_brut=('poids_brut','sum'),
            poids_lave=('poids_lave','sum'),
            poids_dechets=('poids_dechets','sum'),
            poids_grenailles=('poids_grenailles','sum'),
            poids_terre=('poids_terre','sum'),
            pallox=('pallox','sum'),
            nb_lavages=('poids_brut','count'),
        ).reset_index()
        df_var['rendement_pct']  = df_var['poids_lave']  / df_var['poids_brut'] * 100
        df_var['pct_dechets']    = df_var['poids_dechets']    / df_var['poids_brut'] * 100
        df_var['pct_grenailles'] = df_var['poids_grenailles'] / df_var['poids_brut'] * 100
        df_var['pct_terre']      = df_var['poids_terre']      / df_var['poids_brut'] * 100
        df_var = df_var[df_var['poids_brut'] > 0]

        col_g1, col_g2 = st.columns(2)
        with col_g1:
            st.plotly_chart(chart_rendement_varietes(df_var), use_container_width=True)
        with col_g2:
            st.plotly_chart(chart_decompo_varietes(df_var), use_container_width=True)

        # Tableau variétés
        st.markdown("#### Tableau par variété")
        df_vtab = df_var[['variete','nb_lavages','pallox','poids_brut','poids_lave',
                           'rendement_pct','pct_dechets','pct_grenailles','pct_terre']].copy()
        for c in ['poids_brut','poids_lave']:
            df_vtab[c] = (df_vtab[c] / 1000).round(1)
        for c in ['rendement_pct','pct_dechets','pct_grenailles','pct_terre']:
            df_vtab[c] = df_vtab[c].round(1)
        df_vtab['Statut'] = df_vtab['rendement_pct'].apply(
            lambda r: "🟢 Bon" if r >= 85 else ("🟡 Correct" if r >= 75 else "🔴 Critique"))
        df_vtab = df_vtab.rename(columns={
            'variete':'Variété','nb_lavages':'Lavages','pallox':'Pallox',
            'poids_brut':'Brut (T)','poids_lave':'Lavé (T)',
            'rendement_pct':'Rend %','pct_dechets':'%Déch',
            'pct_grenailles':'%Gren','pct_terre':'%Terre'
        }).sort_values('Rend %', ascending=False)
        st.dataframe(df_vtab, use_container_width=True, hide_index=True)

        # Synthèse points forts / points d'attention
        st.markdown("---")
        col_pts1, col_pts2 = st.columns(2)
        with col_pts1:
            st.markdown("#### ✅ Points forts")
            top3 = df_var.nlargest(3, 'rendement_pct')
            for _, r in top3.iterrows():
                vol = r['poids_lave'] / 1000
                st.success(f"**{r['variete']}** : {r['rendement_pct']:.1f}% rend. — {vol:.1f} T lavées")
        with col_pts2:
            st.markdown("#### ⚠️ Points d'attention")
            bot3 = df_var.nsmallest(3, 'rendement_pct')
            for _, r in bot3.iterrows():
                vol = r['poids_lave'] / 1000
                dech = r['pct_dechets']
                gren = r['pct_grenailles']
                st.error(f"**{r['variete']}** : {r['rendement_pct']:.1f}% rend. — {dech:.1f}% déch., {gren:.1f}% gren.")

    # ─────────────────────────────────────────
    # TAB 4 : PAR LOT
    # ─────────────────────────────────────────
    with t4:
        # Colonne identifiant lot selon la source
        if source == 'pomi':
            id_col = 'code_lot_interne'
            label_lot = "Code lot"
        else:
            # Dans fichier historique, pas de N° lot fiable → on utilise variete+producteur+date
            if 'producteur' in df_filt.columns:
                df_filt['lot_label'] = df_filt['variete'] + " | " + df_filt['producteur'].fillna('') + " | " + pd.to_datetime(df_filt['date'], errors='coerce').dt.strftime('%d/%m/%Y').fillna('')
            else:
                df_filt['lot_label'] = df_filt['variete'] + " | " + pd.to_datetime(df_filt['date'], errors='coerce').dt.strftime('%d/%m/%Y').fillna('')
            id_col = 'lot_label'
            label_lot = "Lot (Variété | Producteur | Date)"

        lots_dispo = sorted(df_filt[id_col].dropna().unique().tolist())
        lot_sel = st.selectbox(f"🔍 Sélectionner un lot", lots_dispo, key=f"lot_{source}")

        df_lot = df_filt[df_filt[id_col] == lot_sel].copy()

        if not df_lot.empty:
            row = df_lot.iloc[0]

            # Fiche lot
            st.markdown(f"### 📦 Fiche lot — {lot_sel}")
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Poids brut", f"{df_lot['poids_brut'].sum()/1000:.2f} T")
            col2.metric("Poids lavé",  f"{df_lot['poids_lave'].sum()/1000:.2f} T")
            col3.metric("Rendement",   f"{df_lot['poids_lave'].sum()/df_lot['poids_brut'].sum()*100:.1f}%")
            col4.metric("Pallox",      f"{int(df_lot['pallox'].sum())}")

            col5, col6, col7, col8 = st.columns(4)
            col5.metric("% Déchets",    f"{df_lot['poids_dechets'].sum()/df_lot['poids_brut'].sum()*100:.1f}%")
            col6.metric("% Grenailles", f"{df_lot['poids_grenailles'].sum()/df_lot['poids_brut'].sum()*100:.1f}%")
            col7.metric("% Terre",      f"{df_lot['poids_terre'].sum()/df_lot['poids_brut'].sum()*100:.1f}%")
            if source == 'pomi' and 'cadence_reelle' in df_lot.columns:
                cad_moy = df_lot['cadence_reelle'].mean()
                col8.metric("Cadence moy.", f"{cad_moy:.1f} T/h" if not np.isnan(cad_moy) else "N/A")
            else:
                col8.metric("Variété", str(row.get('variete', '-')))

            # Détails spécifiques POMI
            if source == 'pomi':
                st.markdown("---")
                col_d1, col_d2, col_d3 = st.columns(3)
                with col_d1:
                    st.markdown(f"**Ligne lavage** : {row.get('ligne_lavage', 'N/A')}")
                    st.markdown(f"**Source** : {row.get('statut_source', 'BRUT')}")
                with col_d2:
                    if pd.notna(row.get('date_activation')) and pd.notna(row.get('date_terminaison')):
                        duree = (row['date_terminaison'] - row['date_activation']).total_seconds() / 3600
                        st.markdown(f"**Temps réel** : {duree:.1f}h")
                        st.markdown(f"**Temps estimé** : {row.get('temps_estime_heures', 'N/A')} h")
                with col_d3:
                    if pd.notna(row.get('date_prevue')):
                        st.markdown(f"**Date prévue** : {pd.Timestamp(row['date_prevue']).strftime('%d/%m/%Y')}")
                    if pd.notna(row.get('date_terminaison')):
                        st.markdown(f"**Terminé le** : {pd.Timestamp(row['date_terminaison']).strftime('%d/%m/%Y %H:%M')}")
                if row.get('notes'):
                    st.info(f"📝 {row['notes']}")

            # Si plusieurs lignes pour ce lot (lot en plusieurs passes)
            if len(df_lot) > 1:
                st.markdown("---")
                st.markdown("#### Détail des passes")
                df_lot_disp = df_lot[['date','variete','pallox','poids_brut','poids_lave',
                                       'rendement_pct','pct_dechets','pct_grenailles','pct_terre']].copy()
                for c in ['poids_brut','poids_lave']:
                    df_lot_disp[c] = (df_lot_disp[c] / 1000).round(2)
                for c in ['rendement_pct','pct_dechets','pct_grenailles','pct_terre']:
                    df_lot_disp[c] = df_lot_disp[c].round(1)
                st.dataframe(df_lot_disp, use_container_width=True, hide_index=True)

            # Graphique mini bilan lot
            total_b = df_lot['poids_brut'].sum()
            val_lave  = df_lot['poids_lave'].sum()
            val_dech  = df_lot['poids_dechets'].sum()
            val_gren  = df_lot['poids_grenailles'].sum()
            val_terre = df_lot['poids_terre'].sum()
            fig_lot = go.Figure(go.Pie(
                labels=["Lavé", "Déchets", "Grenailles", "Terre"],
                values=[val_lave, val_dech, val_gren, val_terre],
                marker_colors=[C_LAVE, C_DECH, C_GREN, C_TERRE],
                textinfo='label+percent',
                hole=0.4
            ))
            fig_lot.update_layout(height=280, title=f"Répartition sortie lavage",
                                  margin=dict(l=0,r=0,t=35,b=0),
                                  showlegend=False)
            st.plotly_chart(fig_lot, use_container_width=True)

    # ─────────────────────────────────────────
    # TAB 5 : TABLEAU DÉTAILLÉ
    # ─────────────────────────────────────────
    with t5:
        cols_disp = ['semaine','date','variete']
        if 'producteur' in df_filt.columns:
            cols_disp.append('producteur')
        if source == 'pomi' and 'code_lot_interne' in df_filt.columns:
            cols_disp.insert(2, 'code_lot_interne')
        cols_disp += ['pallox','poids_brut','poids_lave','poids_dechets',
                      'poids_grenailles','poids_terre',
                      'rendement_pct','pct_dechets','pct_grenailles','pct_terre']
        if source == 'pomi' and 'cadence_reelle' in df_filt.columns:
            cols_disp.append('cadence_reelle')
        df_detail = df_filt[[c for c in cols_disp if c in df_filt.columns]].copy()
        for c in ['poids_brut','poids_lave','poids_dechets','poids_grenailles','poids_terre']:
            if c in df_detail.columns:
                df_detail[c] = (df_detail[c] / 1000).round(2)
        for c in ['rendement_pct','pct_dechets','pct_grenailles','pct_terre']:
            if c in df_detail.columns:
                df_detail[c] = df_detail[c].round(1)
        if 'cadence_reelle' in df_detail.columns:
            df_detail['cadence_reelle'] = df_detail['cadence_reelle'].round(2)
        st.dataframe(df_detail, use_container_width=True, hide_index=True)

        # Export CSV
        csv = df_detail.to_csv(index=False, sep=';', decimal=',').encode('utf-8-sig')
        st.download_button("⬇️ Export CSV", csv,
                           f"stats_lavage_{source}_{annee_sel}.csv",
                           "text/csv", use_container_width=False)


# ============================================================
# PAGE PRINCIPALE
# ============================================================

st.title("📊 Statistiques Lavage")

tab_fichier, tab_pomi = st.tabs([
    "📂 Onglet 1 — Historique fichier",
    "🔗 Onglet 2 — Données POMI"
])

# ============================================================
# ONGLET 1 — IMPORT FICHIER HISTORIQUE
# ============================================================
with tab_fichier:
    st.subheader("📂 Analyse depuis fichier Excel")
    st.caption("Import du fichier *ST_FLAVY - écart de tri.xlsx* ou tout fichier au même format.")

    col_up, col_cfg = st.columns([2, 1])

    with col_up:
        uploaded = st.file_uploader(
            "📎 Importer le fichier Excel",
            type=['xlsx', 'xls'],
            key="upload_stats_lavage",
            help="Feuille attendue : 'Saisi des données écarts de tri'"
        )

    with col_cfg:
        st.markdown("**⚙️ Paramètres objectif**")
        obj_th_f  = st.number_input("Obj. cadence (T/h)", 1.0, 30.0, 13.0, 0.5, key="obj_f")
        h_jour_f  = st.number_input("Heures marche / jour", 1.0, 24.0, 13.0, 0.5, key="hj_f")

    if uploaded:
        try:
            with st.spinner("Chargement..."):
                df_hist = charger_fichier_excel(uploaded.read())
            st.success(f"✅ {len(df_hist)} lignes chargées — "
                       f"{df_hist['annee'].nunique()} année(s), "
                       f"{df_hist['variete'].nunique()} variétés")
            st.markdown("---")
            afficher_analyse(df_hist, source="fichier",
                             objectif_th=obj_th_f, heures_jour=h_jour_f)
        except Exception as e:
            st.error(f"❌ Erreur à l'import : {str(e)}")
    else:
        st.info("👆 Importez le fichier Excel pour démarrer l'analyse.")

# ============================================================
# ONGLET 2 — DONNÉES POMI (BDD)
# ============================================================
with tab_pomi:
    st.subheader("🔗 Analyse depuis POMI")
    st.caption("Données issues des jobs de lavage terminés sur la plateforme POMI. "
               "Indépendant de l'historique fichier — aucun croisement entre les deux sources.")

    col_cfg2_1, col_cfg2_2 = st.columns([3, 1])
    with col_cfg2_2:
        st.markdown("**⚙️ Paramètres objectif**")
        obj_th_p = st.number_input("Obj. cadence (T/h)", 1.0, 30.0, 13.0, 0.5, key="obj_p")
        h_jour_p = st.number_input("Heures marche / jour", 1.0, 24.0, 13.0, 0.5, key="hj_p")
        if st.button("🔄 Rafraîchir", key="refresh_pomi"):
            st.cache_data.clear()
            st.rerun()

    with col_cfg2_1:
        with st.spinner("Chargement des données POMI..."):
            df_pomi = get_jobs_termines_pomi()

    if df_pomi.empty:
        st.info("📭 Aucun job de lavage terminé dans POMI pour le moment.\n\n"
                "Les statistiques apparaîtront ici dès que des jobs seront terminés depuis le planning.")
    else:
        nb_jobs = len(df_pomi)
        total_t = df_pomi['poids_brut'].sum() / 1000
        rend_moy = df_pomi['poids_lave'].sum() / df_pomi['poids_brut'].sum() * 100
        st.success(f"✅ **{nb_jobs} jobs terminés** — {total_t:.1f} T lavées — Rendement moyen : {rend_moy:.1f}%")
        st.markdown("---")
        afficher_analyse(df_pomi, source="pomi",
                         objectif_th=obj_th_p, heures_jour=h_jour_p)

show_footer()
