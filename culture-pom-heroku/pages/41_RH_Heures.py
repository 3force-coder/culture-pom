import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import date, datetime, timedelta

from auth import require_access, is_admin
from components.header import show_header
from components.footer import show_footer
from database.connection import get_connection

# ============================================================
# CONFIGURATION PAGE
# ============================================================
st.set_page_config(
    page_title="Stats RH Heures — POMI",
    page_icon="👷",
    layout="wide"
)

# ============================================================
# CSS
# ============================================================
st.markdown("""
<style>
.kpi-vert  { background:#f0faf0; border-left:4px solid #AFCA0A; border-radius:6px; padding:12px 16px; margin-bottom:8px; }
.kpi-rouge { background:#fff0f0; border-left:4px solid #e53935; border-radius:6px; padding:12px 16px; margin-bottom:8px; }
.kpi-jaune { background:#fffbe6; border-left:4px solid #FFEC00; border-radius:6px; padding:12px 16px; margin-bottom:8px; }
.badge-hs  { background:#fff3cd; color:#856404; padding:2px 8px; border-radius:12px; font-size:0.8em; font-weight:600; }
.badge-abs { background:#f8d7da; color:#721c24; padding:2px 8px; border-radius:12px; font-size:0.8em; font-weight:600; }
.badge-ok  { background:#d4edda; color:#155724; padding:2px 8px; border-radius:12px; font-size:0.8em; font-weight:600; }
.info-box  { background:#e8f4f8; border:1px solid #bee5eb; border-radius:6px; padding:10px 14px; margin:8px 0; font-size:0.9em; }
.warn-box  { background:#fff3cd; border:1px solid #ffc107; border-radius:6px; padding:10px 14px; margin:8px 0; font-size:0.9em; }
</style>
""", unsafe_allow_html=True)

# ============================================================
# CONTRÔLE ACCÈS
# ============================================================
require_access("COMMERCIAL")
show_header("Stats RH — Heures & Pointages", "👷")

# ============================================================
# CONSTANTES LÉGALES (France)
# ============================================================
SEUIL_35H       = 35.0   # Durée légale hebdomadaire
SEUIL_HS_BONUS  = 8.0    # Heures supplémentaires bonifiées 25% (8 premières HS)
SEUIL_HS_BONUS2 = 8.0    # Au-delà : 50%
JOURS_SEMAINE   = 5
HEURES_JOUR_REF = 7.0    # Référence journée normale

# Jours fériés France 2025-2026
JOURS_FERIES = {
    date(2025, 1,  1), date(2025, 4, 21), date(2025, 5,  1), date(2025, 5,  8),
    date(2025, 5, 29), date(2025, 6,  9), date(2025, 7, 14), date(2025, 8, 15),
    date(2025, 11, 1), date(2025, 11,11), date(2025, 12,25),
    date(2026, 1,  1), date(2026, 4,  6), date(2026, 5,  1), date(2026, 5,  8),
    date(2026, 5, 14), date(2026, 5, 25), date(2026, 7, 14), date(2026, 8, 15),
    date(2026, 11, 1), date(2026, 11,11), date(2026, 12,25),
}

def jours_ouvres_semaine(annee: int, semaine: int) -> int:
    """Jours ouvrables réels (lun-ven hors fériés) d'une semaine ISO."""
    lundi = date.fromisocalendar(annee, semaine, 1)
    return sum(1 for i in range(5) if (lundi + timedelta(days=i)) not in JOURS_FERIES)

@st.cache_data(ttl=300)
def get_contrats() -> dict:
    """Retourne {matricule: heures_contrat} depuis rh_contrats. Défaut = 35H."""
    try:
        conn = get_connection()
        if not conn:
            return {}
        cur = conn.cursor()
        cur.execute("SELECT matricule, heures_contrat FROM rh_contrats WHERE is_active = TRUE")
        rows = cur.fetchall()
        cur.close(); conn.close()
        return {str(r['matricule']): float(r['heures_contrat']) for r in rows}
    except Exception:
        return {}

# Détection intérimaires/prestataires par préfixe matricule
PREFIXES_INTERIM = ('ANDYS', 'INT', 'EXT', 'TEMP')

def is_interimaire(matricule: str) -> bool:
    m = str(matricule).upper().strip()
    return any(m.startswith(p) for p in PREFIXES_INTERIM)

def type_salarie(matricule: str) -> str:
    return 'Intérimaire' if is_interimaire(matricule) else 'CDI/CDD'

# ============================================================
# LECTURE & NORMALISATION DU CSV
# ============================================================

def lire_csv_euroquartz(uploaded_file) -> tuple[pd.DataFrame, list[str]]:
    """
    Lit un CSV euroquartz (encodage latin1, séparateur auto).
    Retourne (DataFrame normalisé, liste de warnings).
    """
    warnings_list = []

    for enc in ['latin1', 'cp1252', 'utf-8']:
        try:
            uploaded_file.seek(0)
            df = pd.read_csv(uploaded_file, encoding=enc, sep=None, engine='python')
            break
        except UnicodeDecodeError:
            continue
    else:
        return pd.DataFrame(), ["Impossible de lire le fichier (encodage non reconnu)."]

    # Normaliser colonnes
    col_map = {
        'Matricule paye': 'matricule',
        'Matricule payé': 'matricule',
        'Nom': 'nom',
        'Prenom': 'prenom',
        'Prénom': 'prenom',
        'Date': 'date_str',
        'Atelier': 'atelier',
        'Site': 'site',
        'NB heures': 'heures_str',
        'Nb heures': 'heures_str',
        'NB Heures': 'heures_str',
    }
    df = df.rename(columns={k: v for k, v in col_map.items() if k in df.columns})

    colonnes_requises = ['matricule', 'nom', 'date_str', 'heures_str']
    manquantes = [c for c in colonnes_requises if c not in df.columns]
    if manquantes:
        return pd.DataFrame(), [f"Colonnes manquantes : {manquantes}"]

    df = df.dropna(subset=['matricule', 'date_str', 'heures_str'], how='any')

    # Convertir heures (virgule → point)
    df['nb_heures'] = (
        df['heures_str'].astype(str)
        .str.replace(',', '.', regex=False)
        .str.strip()
    )
    df['nb_heures'] = pd.to_numeric(df['nb_heures'], errors='coerce').fillna(0.0)

    # Convertir date
    df['date_pointage'] = pd.to_datetime(df['date_str'], dayfirst=True, errors='coerce').dt.date
    nb_dates_ko = df['date_pointage'].isna().sum()
    if nb_dates_ko > 0:
        warnings_list.append(f"{nb_dates_ko} ligne(s) avec date invalide ignorée(s).")
    df = df.dropna(subset=['date_pointage'])

    # Enrichir
    df['matricule']    = df['matricule'].astype(str).str.strip()
    df['nom']          = df.get('nom', pd.Series([''] * len(df))).fillna('').astype(str).str.strip()
    df['prenom']       = df.get('prenom', pd.Series([''] * len(df))).fillna('').astype(str).str.strip()
    df['atelier']      = df.get('atelier', pd.Series([''] * len(df))).fillna('').astype(str).str.strip()
    df['site']         = df.get('site', pd.Series([''] * len(df))).fillna('').astype(str).str.strip()
    df['type_salarie'] = df['matricule'].apply(type_salarie)

    df['date_dt']      = pd.to_datetime(df['date_pointage'])
    df['semaine']      = df['date_dt'].dt.isocalendar().week.astype(int)
    df['annee']        = df['date_dt'].dt.isocalendar().year.astype(int)
    df['annee_semaine']= df.apply(lambda r: f"{r['annee']}-S{r['semaine']:02d}", axis=1)

    return df, warnings_list


# ============================================================
# IMPORT BDD
# ============================================================

def importer_pointages(df: pd.DataFrame, username: str) -> tuple[bool, str, int, int]:
    conn = get_connection()
    if not conn:
        return False, "Connexion BDD impossible.", 0, 0

    nb_insert = nb_update = 0
    try:
        cursor = conn.cursor()

        # CORRECTION BUG IMPORT MULTIPLE
        # La cle ON CONFLICT inclut l'atelier. Si l'atelier change entre
        # deux imports pour un meme salarie/jour, l'ancienne ligne reste
        # en base et les heures s'accumulent.
        # Solution : purger les lignes de la meme semaine pour ces matricules,
        # puis reinserer proprement.
        semaines_fichier = df['annee_semaine'].unique().tolist()
        matricules_fichier = df['matricule'].astype(str).str.strip().unique().tolist()
        nb_purge = 0
        for sem in semaines_fichier:
            cursor.execute(
                "DELETE FROM rh_pointages WHERE annee_semaine = %s AND matricule = ANY(%s)",
                (sem, matricules_fichier)
            )
            nb_purge += cursor.rowcount

        # INSERTION PROPRE
        for _, r in df.iterrows():
            try:
                cursor.execute("""
                    INSERT INTO rh_pointages
                        (matricule, nom, prenom, date_pointage, atelier, site,
                         nb_heures, semaine, annee, annee_semaine, type_salarie,
                         imported_by, imported_at)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,CURRENT_TIMESTAMP)
                    ON CONFLICT (matricule, date_pointage, atelier, site) DO UPDATE SET
                        nb_heures    = EXCLUDED.nb_heures,
                        nom          = EXCLUDED.nom,
                        prenom       = EXCLUDED.prenom,
                        semaine      = EXCLUDED.semaine,
                        annee        = EXCLUDED.annee,
                        annee_semaine= EXCLUDED.annee_semaine,
                        type_salarie = EXCLUDED.type_salarie,
                        imported_by  = EXCLUDED.imported_by,
                        imported_at  = CURRENT_TIMESTAMP
                    RETURNING (xmax = 0) AS inserted
                """, (
                    str(r['matricule']),
                    str(r['nom'])[:100],
                    str(r['prenom'])[:100],
                    r['date_pointage'],
                    str(r['atelier'])[:100],
                    str(r['site'])[:10],
                    float(r['nb_heures']),
                    int(r['semaine']),
                    int(r['annee']),
                    str(r['annee_semaine']),
                    str(r['type_salarie']),
                    username,
                ))
                res = cursor.fetchone()
                if res and res['inserted']:
                    nb_insert += 1
                else:
                    nb_update += 1
            except Exception:
                nb_update += 1
                conn.rollback()

        conn.commit()
        cursor.close()
        conn.close()
        purge_msg = f" ({nb_purge} lignes purgees avant reimport)" if nb_purge > 0 else ""
        return True, f"✅ {nb_insert} inserees / {nb_update} mises a jour{purge_msg}", nb_insert, nb_update
    except Exception as e:
        conn.rollback()
        conn.close()
        return False, f"Erreur BDD : {str(e)}", 0, 0

# ============================================================
# REQUÊTES BDD
# ============================================================

@st.cache_data(ttl=180)
def get_semaines_dispo_rh():
    conn = get_connection()
    if not conn:
        return []
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT DISTINCT annee_semaine, annee, semaine
            FROM rh_pointages
            WHERE annee_semaine IS NOT NULL
            ORDER BY annee DESC, semaine DESC
            LIMIT 104
        """)
        rows = cur.fetchall()
        cur.close(); conn.close()
        return [r['annee_semaine'] for r in rows]
    except Exception:
        conn.close(); return []


@st.cache_data(ttl=180)
def get_pointages_semaine(annee_semaine: str) -> pd.DataFrame:
    conn = get_connection()
    if not conn:
        return pd.DataFrame()
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT matricule, nom, prenom, date_pointage, atelier, site,
                   nb_heures, semaine, annee, annee_semaine, type_salarie
            FROM rh_pointages
            WHERE annee_semaine = %s
            ORDER BY nom, prenom, date_pointage, atelier
        """, (annee_semaine,))
        rows = cur.fetchall()
        cur.close(); conn.close()
        if not rows:
            return pd.DataFrame()
        df = pd.DataFrame([dict(r) for r in rows])
        if 'nb_heures' in df.columns:
            df['nb_heures'] = pd.to_numeric(df['nb_heures'], errors='coerce').fillna(0.0)
        return df
    except Exception:
        conn.close(); return pd.DataFrame()


@st.cache_data(ttl=180)
def get_pointages_periode(date_debut: date, date_fin: date) -> pd.DataFrame:
    conn = get_connection()
    if not conn:
        return pd.DataFrame()
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT matricule, nom, prenom, date_pointage, atelier, site,
                   nb_heures, semaine, annee, annee_semaine, type_salarie
            FROM rh_pointages
            WHERE date_pointage BETWEEN %s AND %s
            ORDER BY date_pointage, nom
        """, (date_debut, date_fin))
        rows = cur.fetchall()
        cur.close(); conn.close()
        if not rows:
            return pd.DataFrame()
        df = pd.DataFrame([dict(r) for r in rows])
        if 'nb_heures' in df.columns:
            df['nb_heures'] = pd.to_numeric(df['nb_heures'], errors='coerce').fillna(0.0)
        return df
    except Exception:
        conn.close(); return pd.DataFrame()


# ============================================================
# CALCULS MÉTIER
# ============================================================

def calcul_hebdo(df: pd.DataFrame, contrats: dict = None) -> pd.DataFrame:
    """
    Agrege par salarie x semaine, calcule heures sup, statut.
    contrats : {matricule: heures_contrat} — si None, charge depuis BDD.
    Le seuil HS est personnalise par contrat (35H ou 39H).
    Les jours attendus tiennent compte des jours feries.
    """
    if df.empty:
        return pd.DataFrame()

    if contrats is None:
        contrats = get_contrats()

    # Heures totales par salarie x semaine
    grp = (
        df.groupby(['annee_semaine', 'annee', 'semaine', 'matricule', 'nom', 'prenom', 'type_salarie'])
        ['nb_heures'].sum()
        .reset_index()
        .rename(columns={'nb_heures': 'total_heures'})
    )
    grp['total_heures'] = grp['total_heures'].astype(float)

    # Jours travailles
    jours = (
        df.groupby(['annee_semaine', 'matricule'])
        ['date_pointage'].nunique()
        .reset_index()
        .rename(columns={'date_pointage': 'jours_travailles'})
    )
    grp = grp.merge(jours, on=['annee_semaine', 'matricule'], how='left')

    # Seuil contrat par salarie (35H par defaut)
    grp['seuil_contrat'] = grp['matricule'].apply(
        lambda m: contrats.get(str(m), SEUIL_35H)
    )

    # Jours ouvres reels de la semaine (hors feries)
    grp['jours_ouvres'] = grp.apply(
        lambda r: jours_ouvres_semaine(int(r['annee']), int(r['semaine'])), axis=1
    )

    # Heures supplementaires (au-dela du contrat)
    grp['hs_total']   = (grp['total_heures'] - grp['seuil_contrat']).clip(lower=0)
    grp['hs_25pct']   = grp['hs_total'].clip(upper=SEUIL_HS_BONUS)
    grp['hs_50pct']   = (grp['hs_total'] - SEUIL_HS_BONUS).clip(lower=0)

    # Ecart vs contrat
    grp['ecart_35h']  = grp['total_heures'] - grp['seuil_contrat']

    # Statut individuel — reference = jours_ouvres (et non 5 fixe)
    def statut(row):
        if row['total_heures'] >= row['seuil_contrat']:
            if row['hs_total'] > 0:
                return 'HS'
            return 'OK'
        # Moins que le contrat -> verifier si absence ou jour ferie
        if row['jours_travailles'] < row['jours_ouvres']:
            return 'ABSENCE'
        return 'SOUS_35H'

    grp['statut'] = grp.apply(statut, axis=1)

    # Nom complet
    grp['salarie'] = grp['nom'] + ' ' + grp['prenom']

    return grp

def calcul_absenteisme(df: pd.DataFrame, nb_salaries_ref: int,
                       annee: int = None, semaine: int = None) -> dict:
    """
    Calcule un taux d'absenteisme hebdomadaire.
    Tient compte des jours feries : les jours attendus = jours_ouvres x nb_salaries.
    annee, semaine : si fournis, calcul exact des jours ouvres de la semaine.
    """
    if df.empty or nb_salaries_ref == 0:
        return {}

    # Jours ouvres reels (hors feries) si semaine connue, sinon 5 par defaut
    if annee and semaine:
        jo = jours_ouvres_semaine(int(annee), int(semaine))
    else:
        jo = JOURS_SEMAINE

    jours_total_attendus = nb_salaries_ref * jo
    jours_reels = df.groupby('matricule')['date_pointage'].nunique().sum()
    taux = max(0, (jours_total_attendus - jours_reels) / jours_total_attendus * 100) if jours_total_attendus > 0 else 0
    return {
        'jours_attendus': jours_total_attendus,
        'jours_ouvres_semaine': jo,
        'jours_reels': int(jours_reels),
        'jours_manquants': int(max(0, jours_total_attendus - jours_reels)),
        'taux_pct': round(taux, 1),
    }

# ============================================================
# COMPOSANTS VISUELS
# ============================================================

def badge_statut(s: str) -> str:
    mapping = {
        'HS':      '<span class="badge-hs">⬆ HS</span>',
        'ABSENCE': '<span class="badge-abs">⚠ Absence</span>',
        'OK':      '<span class="badge-ok">✓ OK</span>',
        'SOUS_35H':'<span class="badge-abs">↓ &lt;35H</span>',
    }
    return mapping.get(s, s)


def graphe_heures_semaine(df_hebdo: pd.DataFrame, titre: str = "Heures totales / salarié"):
    """Bar chart horizontal trié par heures décroissantes, ligne 35H."""
    if df_hebdo.empty:
        return
    df_s = df_hebdo.sort_values('total_heures', ascending=True).tail(40)
    colors = df_s['statut'].map(
        {'HS': '#ff9800', 'ABSENCE': '#e53935', 'OK': '#AFCA0A', 'SOUS_35H': '#f06292'}
    ).fillna('#AFCA0A')

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=df_s['total_heures'],
        y=df_s['salarie'],
        orientation='h',
        marker_color=colors.tolist(),
        text=df_s['total_heures'].apply(lambda x: f"{x:.1f}h"),
        textposition='outside',
        name='Heures',
    ))
    fig.add_vline(x=35, line_dash='dash', line_color='#1976d2', line_width=2,
                  annotation_text='35H légales', annotation_position='top right')
    fig.update_layout(
        title=titre,
        plot_bgcolor='white', paper_bgcolor='white',
        height=max(350, len(df_s) * 30 + 80),
        xaxis_title='Heures',
        yaxis_title='',
        margin=dict(t=50, b=20, l=160, r=60),
        showlegend=False,
    )
    st.plotly_chart(fig, use_container_width=True, key=f"rh_chart_1_{id(fig)}")


def graphe_hs_detail(df_hebdo: pd.DataFrame):
    """Décomposition HS 25% / 50% par salarié."""
    df_hs = df_hebdo[df_hebdo['hs_total'] > 0].sort_values('hs_total', ascending=False)
    if df_hs.empty:
        st.info("Aucune heure supplémentaire cette semaine.")
        return

    fig = go.Figure()
    fig.add_trace(go.Bar(
        name='HS majorées 25%%',
        x=df_hs['salarie'], y=df_hs['hs_25pct'],
        marker_color='#ff9800',
        text=df_hs['hs_25pct'].apply(lambda x: f"{x:.1f}h" if x > 0 else ''),
        textposition='inside',
    ))
    fig.add_trace(go.Bar(
        name='HS majorées 50%%',
        x=df_hs['salarie'], y=df_hs['hs_50pct'],
        marker_color='#e53935',
        text=df_hs['hs_50pct'].apply(lambda x: f"{x:.1f}h" if x > 0 else ''),
        textposition='inside',
    ))
    fig.update_layout(
        barmode='stack',
        title='Décomposition heures supplémentaires (législation française)',
        plot_bgcolor='white', paper_bgcolor='white',
        height=350,
        xaxis_tickangle=-35,
        margin=dict(t=50, b=80),
        legend=dict(orientation='h', yanchor='bottom', y=1.02),
    )
    st.plotly_chart(fig, use_container_width=True, key=f"rh_chart_2_{id(fig)}")


def graphe_evolution_hebdo(df: pd.DataFrame):
    """Évolution du total heures semaine × semaine."""
    if df.empty or 'annee_semaine' not in df.columns:
        return
    grp = (
        df.groupby('annee_semaine')
        .agg(total_heures=('nb_heures', 'sum'),
             nb_salaries=('matricule', 'nunique'))
        .reset_index()
        .sort_values('annee_semaine')
    )
    grp['moy_par_salarie'] = (grp['total_heures'] / grp['nb_salaries']).round(2)

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=grp['annee_semaine'], y=grp['total_heures'],
        name='Total heures', marker_color='#AFCA0A',
        yaxis='y', text=grp['total_heures'].apply(lambda x: f"{x:.0f}h"),
        textposition='outside',
    ))
    fig.add_trace(go.Scatter(
        x=grp['annee_semaine'], y=grp['moy_par_salarie'],
        name='Moy/salarié', line=dict(color='#1976d2', width=2),
        mode='lines+markers', yaxis='y2',
    ))
    fig.add_hline(y=35, line_dash='dash', line_color='#e53935', line_width=1,
                  annotation_text='35H', yref='y2')
    fig.update_layout(
        title='Évolution hebdomadaire — Total heures & moyenne/salarié',
        plot_bgcolor='white', paper_bgcolor='white',
        height=380,
        xaxis_tickangle=-45,
        yaxis=dict(title='Total heures', side='left'),
        yaxis2=dict(title='Moy/salarié (h)', side='right', overlaying='y'),
        legend=dict(orientation='h', yanchor='bottom', y=1.02),
        margin=dict(t=60, b=60),
    )
    st.plotly_chart(fig, use_container_width=True, key=f"rh_chart_3_{id(fig)}")


def graphe_repartition_site(df: pd.DataFrame):
    grp = df.groupby('site')['nb_heures'].sum().reset_index()
    fig = px.pie(grp, names='site', values='nb_heures',
                 title='Répartition heures par site',
                 color_discrete_sequence=['#AFCA0A', '#FFEC00', '#7A7A7A'],
                 hole=0.35)
    fig.update_traces(textinfo='label+percent+value',
                      texttemplate='%{label}<br>%{value:.0f}h (%{percent})')
    fig.update_layout(height=320, margin=dict(t=40, b=10))
    st.plotly_chart(fig, use_container_width=True, key=f"rh_chart_4_{id(fig)}")


def graphe_repartition_atelier(df: pd.DataFrame):
    grp = df.groupby('atelier')['nb_heures'].sum().reset_index().sort_values('nb_heures', ascending=True)
    fig = px.bar(grp, x='nb_heures', y='atelier', orientation='h',
                 title='Heures par atelier',
                 color_discrete_sequence=['#AFCA0A'],
                 text=grp['nb_heures'].apply(lambda x: f"{x:.0f}h"))
    fig.update_traces(textposition='outside')
    fig.update_layout(
        plot_bgcolor='white', paper_bgcolor='white',
        height=max(280, len(grp) * 30 + 60),
        margin=dict(t=40, b=20, l=120),
        xaxis_title='Heures',
    )
    st.plotly_chart(fig, use_container_width=True, key=f"rh_chart_5_{id(fig)}")


def graphe_radar_salarie(df_hebdo: pd.DataFrame, matricule: str):
    """Radar hebdomadaire d'un salarié vs moyenne équipe."""
    row = df_hebdo[df_hebdo['matricule'] == matricule]
    if row.empty:
        return
    row = row.iloc[0]
    moy = df_hebdo['total_heures'].mean()
    max_h = df_hebdo['total_heures'].max()

    categories = ['Heures totales', 'vs Moyenne', 'vs Max', 'Jours présents', 'HS']
    vals_sal = [
        min(row['total_heures'] / 45 * 5, 5),
        min(row['total_heures'] / max(moy, 1) * 5, 5),
        min(row['total_heures'] / max(max_h, 1) * 5, 5),
        row['jours_travailles'],
        min(row['hs_total'] / 10 * 5, 5),
    ]
    vals_moy = [
        min(moy / 45 * 5, 5),
        5, min(moy / max(max_h, 1) * 5, 5),
        JOURS_SEMAINE, 0,
    ]

    fig = go.Figure()
    fig.add_trace(go.Scatterpolar(
        r=vals_sal, theta=categories, fill='toself',
        name=f"{row['salarie']}", line_color='#AFCA0A',
    ))
    fig.add_trace(go.Scatterpolar(
        r=vals_moy, theta=categories, fill='toself',
        name='Moyenne équipe', line_color='#7A7A7A', opacity=0.4,
    ))
    fig.update_layout(
        polar=dict(radialaxis=dict(visible=True, range=[0, 5])),
        title=f"Profil semaine — {row['salarie']}",
        height=350, showlegend=True,
    )
    st.plotly_chart(fig, use_container_width=True, key=f"rh_chart_6_{id(fig)}")


def tableau_hs_synthetique(df_hebdo: pd.DataFrame):
    """Tableau récapitulatif HS avec coûts indicatifs."""
    df_hs = df_hebdo[df_hebdo['hs_total'] > 0].copy()
    if df_hs.empty:
        st.info("Aucune heure supplémentaire à afficher.")
        return
    df_hs = df_hs.sort_values('hs_total', ascending=False)
    df_hs['hs_total_fmt']   = df_hs['hs_total'].apply(lambda x: f"{x:.2f}h")
    df_hs['total_fmt']      = df_hs['total_heures'].apply(lambda x: f"{x:.2f}h")
    df_hs['ecart_fmt']      = df_hs['ecart_35h'].apply(lambda x: f"+{x:.2f}h" if x >= 0 else f"{x:.2f}h")

    cols = ['salarie', 'type_salarie', 'total_fmt', 'hs_total_fmt', 'hs_25pct', 'hs_50pct', 'ecart_fmt', 'jours_travailles']
    df_display = df_hs[cols].rename(columns={
        'salarie':          'Salarié',
        'type_salarie':     'Statut',
        'total_fmt':        'Total heures',
        'hs_total_fmt':     'HS total',
        'hs_25pct':         'HS +25%%',
        'hs_50pct':         'HS +50%%',
        'ecart_fmt':        'Écart 35H',
        'jours_travailles': 'Jours',
    })
    st.dataframe(
        df_display,
        use_container_width=True,
        hide_index=True,
        column_config={
            'HS +25%%': st.column_config.NumberColumn(format="%.2f h"),
            'HS +50%%': st.column_config.NumberColumn(format="%.2f h"),
        }
    )


def tableau_absences(df_hebdo: pd.DataFrame):
    """Tableau salariés avec jours manquants."""
    df_abs = df_hebdo[df_hebdo['jours_travailles'] < JOURS_SEMAINE].copy()
    if df_abs.empty:
        st.success("✅ Tous les salariés sont présents les 5 jours.")
        return
    df_abs = df_abs.sort_values('jours_travailles')
    df_abs['jours_manquants'] = JOURS_SEMAINE - df_abs['jours_travailles']
    df_abs['heures_manquantes'] = (df_abs['jours_manquants'] * HEURES_JOUR_REF).round(2)

    df_display = df_abs[['salarie', 'type_salarie', 'jours_travailles', 'jours_manquants',
                          'heures_manquantes', 'total_heures']].rename(columns={
        'salarie':           'Salarié',
        'type_salarie':      'Statut',
        'jours_travailles':  'Jours présents',
        'jours_manquants':   'Jours manquants',
        'heures_manquantes': 'Heures manquantes (est.)',
        'total_heures':      'Total heures',
    })
    st.dataframe(df_display, use_container_width=True, hide_index=True,
                 column_config={
                     'Total heures': st.column_config.NumberColumn(format="%.2f h"),
                     'Heures manquantes (est.)': st.column_config.NumberColumn(format="%.2f h"),
                 })


# ============================================================
# FILTRE SITE GLOBAL
# ============================================================
SITES_OPTIONS = {
    "🏭 Tous les sites": None,
    "COR — Corroy":          "COR",
    "LMT — La Motte-Tilly":  "LMT",
    "SFY — Saint-Flavy":     "SFY",
    "MAIN — Maintenance":    "MAIN",
}

col_site_f, _ = st.columns([2, 6])
with col_site_f:
    site_label = st.selectbox(
        "🏭 Site",
        options=list(SITES_OPTIONS.keys()),
        index=0,
        key="rh_filtre_site",
    )
FILTRE_SITE = SITES_OPTIONS[site_label]

def appliquer_filtre_site(df: pd.DataFrame) -> pd.DataFrame:
    """Filtre le DataFrame sur le site sélectionné globalement."""
    if FILTRE_SITE is None or df.empty or 'site' not in df.columns:
        return df
    return df[df['site'].str.upper().str.strip() == FILTRE_SITE]

st.markdown("---")

# ============================================================
# ONGLETS PRINCIPAUX
# ============================================================

# Charger les contrats une fois pour toute la page
_contrats_page = get_contrats()

tab_import, tab_semaine, tab_evolution, tab_salarie, tab_ateliers = st.tabs([
    "📥 Import",
    "📅 Semaine",
    "📈 Évolution",
    "👤 Par salarié",
    "🏭 Ateliers & Sites",
])

# ────────────────────────────────────────────────────────────
# ONGLET 1 : IMPORT
# ────────────────────────────────────────────────────────────
with tab_import:
    st.subheader("📥 Import pointages Euroquartz")

    st.markdown("""
    <div class="info-box">
    📌 Importez le fichier CSV exporté depuis <strong>Euroquartz</strong> (pointeuse).<br>
    Format attendu : <em>Matricule paye, Nom, Prenom, Date, Atelier, Site, NB heures</em><br>
    Encodage latin1 détecté automatiquement. Les doublons sont mis à jour.
    </div>
    """, unsafe_allow_html=True)

    uploaded = st.file_uploader(
        "Sélectionner le fichier CSV Euroquartz",
        type=['csv', 'txt'],
        key="rh_upload"
    )

    if uploaded:
        df_prev, warns = lire_csv_euroquartz(uploaded)

        for w in warns:
            st.warning(w)

        if not df_prev.empty:
            # KPIs aperçu
            c1, c2, c3, c4, c5 = st.columns(5)
            c1.metric("Lignes", len(df_prev))
            c2.metric("Salariés", df_prev['matricule'].nunique())
            c3.metric("Semaines", df_prev['annee_semaine'].nunique())
            c4.metric("Sites", df_prev['site'].nunique())
            c5.metric("Intérimaires", len(df_prev[df_prev['type_salarie'] == 'Intérimaire']['matricule'].unique()))

            # Semaines détectées
            sems = sorted(df_prev['annee_semaine'].unique())
            st.caption(f"Semaines détectées : {', '.join(sems)}")

            with st.expander("Aperçu des données (20 premières lignes)"):
                cols_ap = ['matricule', 'nom', 'prenom', 'date_pointage', 'annee_semaine',
                           'atelier', 'site', 'nb_heures', 'type_salarie']
                st.dataframe(df_prev[cols_ap].head(20), use_container_width=True, hide_index=True)

            # Résumé hebdo en aperçu
            hebdo = calcul_hebdo(df_prev, contrats=_contrats_page)
            if not hebdo.empty:
                nb_hs    = len(hebdo[hebdo['statut'] == 'HS'])
                nb_abs   = len(hebdo[hebdo['statut'] == 'ABSENCE'])
                nb_ok    = len(hebdo[hebdo['statut'] == 'OK'])
                st.markdown("**Résumé semaine :**")
                col_s1, col_s2, col_s3 = st.columns(3)
                col_s1.metric("✅ À 35H ou plus (hors HS)", nb_ok)
                col_s2.metric("⬆ Avec heures supp", nb_hs)
                col_s3.metric("⚠ Absences / <35H", nb_abs)

            if st.button("🚀 Importer dans la base", type="primary", use_container_width=True):
                with st.spinner("Import en cours…"):
                    ok, msg, nb_ins, nb_sk = importer_pointages(
                        df_prev, st.session_state.get('username', '?')
                    )
                if ok:
                    st.success(msg)
                    st.cache_data.clear()
                else:
                    st.error(msg)

    # Info dernier import
    try:
        conn_info = get_connection()
        if conn_info:
            cur = conn_info.cursor()
            cur.execute("""
                SELECT imported_by, MAX(imported_at) as derniere_maj, COUNT(*) as nb_total
                FROM rh_pointages
                GROUP BY imported_by
                ORDER BY MAX(imported_at) DESC
                LIMIT 1
            """)
            last = cur.fetchone()
            cur.close(); conn_info.close()
            if last:
                st.caption(
                    f"Dernier import : {last['derniere_maj'].strftime('%d/%m/%Y %H:%M')} "
                    f"par {last['imported_by']} — {last['nb_total']} lignes en base"
                )
    except Exception:
        pass


# ────────────────────────────────────────────────────────────
# ONGLET 2 : SEMAINE
# ────────────────────────────────────────────────────────────
with tab_semaine:
    st.subheader("📅 Analyse par semaine")

    semaines = get_semaines_dispo_rh()
    if not semaines:
        st.info("Aucune donnée en base. Effectuez un import.")
    else:
        col_sel1, col_sel2 = st.columns([2, 2])
        with col_sel1:
            sem_choisie = st.selectbox("Semaine", semaines, index=0, key="sem_analyse")
        with col_sel2:
            filtre_type = st.selectbox("Type de salarié", ["Tous", "CDI/CDD", "Intérimaire"], key="sem_type")

        df_sem = appliquer_filtre_site(get_pointages_semaine(sem_choisie))

        if df_sem.empty:
            st.info(f"Aucune donnée pour la semaine {sem_choisie}.")
        else:
            if filtre_type != "Tous":
                df_sem = df_sem[df_sem['type_salarie'] == filtre_type]

            df_hebdo = calcul_hebdo(df_sem, contrats=_contrats_page)

            if df_hebdo.empty:
                st.info("Aucune donnée après filtrage.")
            else:
                # ── KPIs ──
                st.markdown("---")
                total_h   = df_hebdo['total_heures'].sum()
                moy_h     = df_hebdo['total_heures'].mean()
                total_hs  = df_hebdo['hs_total'].sum()
                nb_sal    = len(df_hebdo)
                nb_hs     = len(df_hebdo[df_hebdo['hs_total'] > 0])
                nb_abs    = len(df_hebdo[df_hebdo['jours_travailles'] < JOURS_SEMAINE])
                abs_info  = calcul_absenteisme(df_sem, nb_sal, annee=df_sem['annee'].iloc[0] if not df_sem.empty else None, semaine=df_sem['semaine'].iloc[0] if not df_sem.empty else None)

                c1, c2, c3, c4, c5, c6 = st.columns(6)
                c1.metric("👷 Effectif", nb_sal)
                c2.metric("⏱ Total heures", f"{total_h:.0f}h")
                c3.metric("📊 Moy/salarié", f"{moy_h:.1f}h",
                          delta=f"{moy_h - 35:+.1f}h vs 35H")
                c4.metric("⬆ Heures supp", f"{total_hs:.1f}h",
                          delta=f"{nb_hs} salariés concernés")
                c5.metric("⚠ Absences", nb_abs)
                c6.metric("📉 Taux absentéisme",
                          f"{abs_info.get('taux_pct', 0):.1f}%")

                st.markdown("---")

                # ── Graphes principaux ──
                col_g1, col_g2 = st.columns([3, 2])
                with col_g1:
                    graphe_heures_semaine(df_hebdo)
                with col_g2:
                    graphe_repartition_site(df_sem)

                # ── Heures supplémentaires ──
                st.markdown("---")
                st.subheader("⬆ Heures supplémentaires")
                st.markdown("""
                <div class="warn-box">
                ⚖️ Législation française : au-delà de 35H/semaine → HS majorées <strong>+25%%</strong>
                pour les 8 premières heures, puis <strong>+50%%</strong> au-delà.
                </div>
                """, unsafe_allow_html=True)

                col_hs1, col_hs2 = st.columns([3, 2])
                with col_hs1:
                    graphe_hs_detail(df_hebdo)
                with col_hs2:
                    tableau_hs_synthetique(df_hebdo)

                # ── Absences / <35H ──
                st.markdown("---")
                st.subheader("⚠ Absences & Sous-35H")
                tableau_absences(df_hebdo)

                # ── Détail lignes ──
                with st.expander("📋 Détail des pointages bruts"):
                    st.dataframe(
                        df_sem[['nom', 'prenom', 'date_pointage', 'atelier', 'site', 'nb_heures', 'type_salarie']]
                        .sort_values(['nom', 'date_pointage']),
                        use_container_width=True, hide_index=True,
                        column_config={'nb_heures': st.column_config.NumberColumn(format="%.2f h")}
                    )


# ────────────────────────────────────────────────────────────
# ONGLET 3 : ÉVOLUTION
# ────────────────────────────────────────────────────────────
with tab_evolution:
    st.subheader("📈 Évolution dans le temps")

    col_e1, col_e2 = st.columns(2)
    with col_e1:
        date_ev_debut = st.date_input(
            "Depuis le", value=date.today() - timedelta(days=120), key="ev_debut"
        )
    with col_e2:
        date_ev_fin = st.date_input(
            "Jusqu'au", value=date.today(), key="ev_fin"
        )

    df_ev = appliquer_filtre_site(get_pointages_periode(date_ev_debut, date_ev_fin))

    if df_ev.empty:
        st.info("Aucune donnée pour cette période.")
    else:
        # ── KPIs ──
        nb_sems = df_ev['annee_semaine'].nunique()
        total_h = float(df_ev['nb_heures'].sum())
        moy_sem = total_h / nb_sems if nb_sems else 0

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("📅 Semaines", nb_sems)
        c2.metric("⏱ Total heures", f"{total_h:.0f}h")
        c3.metric("📊 Moy/semaine", f"{moy_sem:.0f}h")
        c4.metric("👷 Salariés distincts", df_ev['matricule'].nunique())

        st.markdown("---")
        graphe_evolution_hebdo(df_ev)

        # ── HS dans le temps ──
        st.markdown("---")
        st.subheader("⬆ Évolution des heures supplémentaires")

        df_hebdo_ev = calcul_hebdo(df_ev, contrats=_contrats_page)
        if not df_hebdo_ev.empty:
            hs_par_sem = (
                df_hebdo_ev.groupby('annee_semaine')
                .agg(hs_total=('hs_total', 'sum'),
                     nb_sal_hs=('hs_total', lambda x: (x > 0).sum()),
                     nb_sal_total=('matricule', 'count'))
                .reset_index()
                .sort_values('annee_semaine')
            )
            hs_par_sem['pct_sal_hs'] = (hs_par_sem['nb_sal_hs'] / hs_par_sem['nb_sal_total'] * 100).round(1)

            fig_hs = go.Figure()
            fig_hs.add_trace(go.Bar(
                x=hs_par_sem['annee_semaine'], y=hs_par_sem['hs_total'],
                name='Total HS (h)', marker_color='#ff9800',
                text=hs_par_sem['hs_total'].apply(lambda x: f"{x:.0f}h"),
                textposition='outside',
            ))
            fig_hs.add_trace(go.Scatter(
                x=hs_par_sem['annee_semaine'], y=hs_par_sem['pct_sal_hs'],
                name='%% salariés en HS', line=dict(color='#e53935', width=2),
                mode='lines+markers', yaxis='y2',
            ))
            fig_hs.update_layout(
                barmode='group', plot_bgcolor='white', paper_bgcolor='white',
                height=360, xaxis_tickangle=-45,
                yaxis=dict(title='Heures supplémentaires'),
                yaxis2=dict(title='%% salariés en HS', side='right', overlaying='y',
                            ticksuffix='%%'),
                legend=dict(orientation='h', yanchor='bottom', y=1.02),
                margin=dict(t=60, b=60),
            )
            st.plotly_chart(fig_hs, use_container_width=True, key=f"rh_chart_7_{id(fig_hs)}")

        # ── Taux absentéisme dans le temps ──
        st.markdown("---")
        st.subheader("📉 Absentéisme hebdomadaire")

        if not df_hebdo_ev.empty:
            abs_par_sem = (
                df_hebdo_ev.groupby('annee_semaine')
                .agg(nb_abs=('statut', lambda x: (x.isin(['ABSENCE', 'SOUS_35H'])).sum()),
                     nb_total=('matricule', 'count'))
                .reset_index()
            )
            abs_par_sem['taux_abs'] = (abs_par_sem['nb_abs'] / abs_par_sem['nb_total'] * 100).round(1)
            abs_par_sem = abs_par_sem.sort_values('annee_semaine')

            fig_abs = px.area(
                abs_par_sem, x='annee_semaine', y='taux_abs',
                title="Taux d'absentéisme/sous-35H par semaine (%%)",
                labels={'annee_semaine': 'Semaine', 'taux_abs': 'Taux (%%)'},
                color_discrete_sequence=['#e53935'],
            )
            fig_abs.add_hline(y=5, line_dash='dash', line_color='#ff9800',
                              annotation_text='Seuil alerte 5%%')
            fig_abs.update_layout(
                plot_bgcolor='white', paper_bgcolor='white',
                height=320, xaxis_tickangle=-45, margin=dict(t=50, b=60),
            )
            st.plotly_chart(fig_abs, use_container_width=True, key=f"rh_chart_8_{id(fig_abs)}")

        # ── Comparaison N vs N-1 ──
        st.markdown("---")
        st.subheader("🔀 Comparaison N vs N-1")

        semaines_ev = sorted(df_ev['annee_semaine'].unique())
        if semaines_ev:
            sem_cmp = st.selectbox("Semaine de référence", semaines_ev, key="ev_cmp")
            # Chercher la même semaine N-1
            parts = sem_cmp.split('-S')
            if len(parts) == 2:
                sem_n1 = f"{int(parts[0]) - 1}-S{parts[1]}"
                df_n1 = appliquer_filtre_site(get_pointages_semaine(sem_n1))
                df_n = appliquer_filtre_site(get_pointages_semaine(sem_cmp))
                if not df_n.empty:
                    h_n  = float(df_n['nb_heures'].sum())
                    sal_n = df_n['matricule'].nunique()
                    hs_n  = calcul_hebdo(df_n, contrats=_contrats_page)['hs_total'].sum() if not calcul_hebdo(df_n, contrats=_contrats_page).empty else 0
                    h_n1 = float(df_n1['nb_heures'].sum()) if not df_n1.empty else None

                    col_c1, col_c2 = st.columns(2)
                    with col_c1:
                        st.markdown(f"**{sem_cmp}**")
                        st.metric("Total heures", f"{h_n:.0f}h",
                                  delta=f"{h_n - h_n1:+.0f}h vs N-1" if h_n1 else "N-1 non dispo")
                        st.metric("Salariés présents", sal_n)
                        st.metric("Heures supp totales", f"{hs_n:.1f}h")
                    with col_c2:
                        if not df_n1.empty:
                            st.markdown(f"**{sem_n1} (N-1)**")
                            h1_n1 = float(df_n1['nb_heures'].sum())
                            sal_n1 = df_n1['matricule'].nunique()
                            hs_n1 = calcul_hebdo(df_n1, contrats=_contrats_page)['hs_total'].sum() if not calcul_hebdo(df_n1, contrats=_contrats_page).empty else 0
                            st.metric("Total heures", f"{h1_n1:.0f}h")
                            st.metric("Salariés présents", sal_n1)
                            st.metric("Heures supp totales", f"{hs_n1:.1f}h")
                        else:
                            st.info(f"Pas de données pour {sem_n1}.")


# ────────────────────────────────────────────────────────────
# ONGLET 4 : PAR SALARIÉ
# ────────────────────────────────────────────────────────────
with tab_salarie:
    st.subheader("👤 Analyse individuelle")

    semaines_sal = get_semaines_dispo_rh()
    if not semaines_sal:
        st.info("Aucune donnée. Effectuez un import.")
    else:
        col_sal1, col_sal2 = st.columns(2)
        with col_sal1:
            sem_sal = st.selectbox("Semaine", semaines_sal, key="sal_sem")
        df_sal_sem = appliquer_filtre_site(get_pointages_semaine(sem_sal))
        df_heb_sal = calcul_hebdo(df_sal_sem, contrats=_contrats_page) if not df_sal_sem.empty else pd.DataFrame()

        salaries_list = []
        if not df_heb_sal.empty:
            salaries_list = sorted(df_heb_sal['salarie'].unique())

        with col_sal2:
            sal_choisi = st.selectbox("Salarié", salaries_list, key="sal_choisi") if salaries_list else None

        if sal_choisi and not df_heb_sal.empty:
            row_sal = df_heb_sal[df_heb_sal['salarie'] == sal_choisi].iloc[0]
            mat = row_sal['matricule']

            # Fiche individuelle
            col_fi1, col_fi2 = st.columns([2, 2])
            with col_fi1:
                st.markdown(f"### {sal_choisi}")
                st.markdown(f"Matricule : `{mat}` — {row_sal['type_salarie']}")
                st.markdown(f"Semaine : **{sem_sal}**")
                st.markdown("---")
                st.metric("Total heures", f"{row_sal['total_heures']:.2f}h",
                          delta=f"{row_sal['ecart_35h']:+.2f}h vs 35H")
                st.metric("Jours travaillés", f"{row_sal['jours_travailles']} / {JOURS_SEMAINE}")
                if row_sal['hs_total'] > 0:
                    st.metric("Heures supplémentaires", f"{row_sal['hs_total']:.2f}h",
                              delta=f"+25%%: {row_sal['hs_25pct']:.2f}h | +50%%: {row_sal['hs_50pct']:.2f}h")
                else:
                    st.metric("Heures supplémentaires", "0h")

            with col_fi2:
                graphe_radar_salarie(df_heb_sal, mat)

            # Détail journalier
            st.markdown("---")
            st.subheader("📆 Détail journalier")
            df_sal_detail = df_sal_sem[df_sal_sem['matricule'] == mat].copy()
            df_sal_detail = df_sal_detail.sort_values('date_pointage')

            # Graphe jours
            grp_j = df_sal_detail.groupby('date_pointage')['nb_heures'].sum().reset_index()
            fig_j = px.bar(grp_j, x='date_pointage', y='nb_heures',
                           title="Heures par jour",
                           color_discrete_sequence=['#AFCA0A'],
                           text=grp_j['nb_heures'].apply(lambda x: f"{x:.2f}h"))
            fig_j.add_hline(y=HEURES_JOUR_REF, line_dash='dash', line_color='#1976d2',
                            annotation_text=f'{HEURES_JOUR_REF}H/jour')
            fig_j.update_traces(textposition='outside')
            fig_j.update_layout(
                plot_bgcolor='white', paper_bgcolor='white',
                height=300, margin=dict(t=40, b=40),
                xaxis_title='', yaxis_title='Heures',
            )
            st.plotly_chart(fig_j, use_container_width=True, key=f"rh_chart_9_{id(fig_j)}")

            # Détail ateliers
            st.dataframe(
                df_sal_detail[['date_pointage', 'atelier', 'site', 'nb_heures']]
                .rename(columns={'date_pointage': 'Date', 'atelier': 'Atelier',
                                 'site': 'Site', 'nb_heures': 'Heures'}),
                use_container_width=True, hide_index=True,
                column_config={'Heures': st.column_config.NumberColumn(format="%.2f h")}
            )

            # Historique multi-semaines salarié
            st.markdown("---")
            st.subheader("📊 Historique du salarié")
            df_hist = get_pointages_periode(
                date.today() - timedelta(days=180), date.today()
            )
            if not df_hist.empty:
                df_hist_sal = df_hist[df_hist['matricule'] == mat]
                if not df_hist_sal.empty:
                    df_hh = calcul_hebdo(df_hist_sal, contrats=_contrats_page)
                    if not df_hh.empty:
                        df_hh = df_hh.sort_values('annee_semaine')
                        fig_hist = go.Figure()
                        fig_hist.add_trace(go.Bar(
                            x=df_hh['annee_semaine'], y=df_hh['total_heures'],
                            name='Heures',
                            marker_color=df_hh['statut'].map(
                                {'HS': '#ff9800', 'ABSENCE': '#e53935',
                                 'OK': '#AFCA0A', 'SOUS_35H': '#f06292'}
                            ).fillna('#AFCA0A'),
                            text=df_hh['total_heures'].apply(lambda x: f"{x:.0f}h"),
                            textposition='outside',
                        ))
                        fig_hist.add_hline(y=35, line_dash='dash', line_color='#1976d2',
                                           annotation_text='35H')
                        fig_hist.update_layout(
                            title=f"Historique 6 mois — {sal_choisi}",
                            plot_bgcolor='white', paper_bgcolor='white',
                            height=300, xaxis_tickangle=-45, margin=dict(t=50, b=60),
                        )
                        st.plotly_chart(fig_hist, use_container_width=True, key=f"rh_chart_10_{id(fig_hist)}")


# ────────────────────────────────────────────────────────────
# ONGLET 5 : ATELIERS & SITES
# ────────────────────────────────────────────────────────────
with tab_ateliers:
    st.subheader("🏭 Analyse par atelier & site")

    semaines_at = get_semaines_dispo_rh()
    if not semaines_at:
        st.info("Aucune donnée. Effectuez un import.")
    else:
        col_at1, col_at2 = st.columns([2, 2])
        with col_at1:
            sem_at = st.selectbox("Semaine", semaines_at, key="at_sem")
        with col_at2:
            granularite = st.radio("Granularité", ["Semaine", "Par jour"], horizontal=True, key="at_gran")

        df_at = appliquer_filtre_site(get_pointages_semaine(sem_at))

        if df_at.empty:
            st.info(f"Aucune donnée pour {sem_at}.")
        else:
            col_a1, col_a2 = st.columns(2)
            with col_a1:
                graphe_repartition_atelier(df_at)
            with col_a2:
                graphe_repartition_site(df_at)

            # Heatmap atelier × jour
            st.markdown("---")
            st.subheader("🗓 Heatmap Atelier × Jour")

            df_hm = df_at.copy()
            df_hm['jour_semaine'] = pd.to_datetime(df_hm['date_pointage']).dt.strftime('%a %d/%m')
            pivot = df_hm.pivot_table(
                index='atelier', columns='jour_semaine',
                values='nb_heures', aggfunc='sum', fill_value=0
            )
            pivot = pivot.reindex(sorted(pivot.columns), axis=1)

            fig_hm = px.imshow(
                pivot,
                title="Heures par atelier et par jour",
                color_continuous_scale='YlGn',
                text_auto='.0f',
                aspect='auto',
            )
            fig_hm.update_layout(
                height=max(300, len(pivot) * 35 + 100),
                margin=dict(t=50, b=40, l=130),
                coloraxis_colorbar_title='Heures',
            )
            st.plotly_chart(fig_hm, use_container_width=True, key=f"rh_chart_11_{id(fig_hm)}")

            # Tableau récap
            st.markdown("---")
            grp_recap = (
                df_at.groupby(['site', 'atelier'])
                .agg(
                    nb_heures=('nb_heures', 'sum'),
                    nb_salaries=('matricule', 'nunique'),
                    nb_lignes=('nb_heures', 'count'),
                )
                .reset_index()
                .sort_values(['site', 'nb_heures'], ascending=[True, False])
                .rename(columns={
                    'site': 'Site', 'atelier': 'Atelier',
                    'nb_heures': 'Total heures',
                    'nb_salaries': 'Salariés',
                    'nb_lignes': 'Pointages',
                })
            )
            grp_recap['Moy/salarié'] = (grp_recap['Total heures'] / grp_recap['Salariés']).round(2)
            st.dataframe(
                grp_recap, use_container_width=True, hide_index=True,
                column_config={
                    'Total heures': st.column_config.NumberColumn(format="%.2f h"),
                    'Moy/salarié': st.column_config.NumberColumn(format="%.2f h"),
                }
            )

# ============================================================
# FOOTER
# ============================================================
show_footer()
