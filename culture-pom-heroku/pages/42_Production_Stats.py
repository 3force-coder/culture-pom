import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import date, datetime, timedelta
import calendar

from auth import require_access, is_admin
from components import show_footer
from database import get_connection

# ── CONFIG PAGE ──────────────────────────────────────────────
st.set_page_config(page_title="Stats Production", page_icon="🏭", layout="wide")

st.markdown("""<style>
    .block-container {padding-top:2rem!important;padding-bottom:0.5rem!important;
        padding-left:2rem!important;padding-right:2rem!important;}
    h1,h2,h3,h4{margin-top:0.3rem!important;margin-bottom:0.3rem!important;}
    [data-testid="stMetricValue"]{font-size:1.4rem!important;}
    hr{margin-top:0.5rem!important;margin-bottom:0.5rem!important;}
    .ro-positif {color:#AFCA0A; font-weight:bold;}
    .ro-negatif {color:#e53935; font-weight:bold;}
    .kpi-box {background:#f8f9fa; border-radius:8px; padding:10px 14px;
              border-left:4px solid #AFCA0A; margin-bottom:6px;}
</style>""", unsafe_allow_html=True)

require_access("COMMERCIAL")
st.title("🏭 Production — Statistiques & Cadences")

# ── CONSTANTES ────────────────────────────────────────────────
COULEURS  = {'SBU1': '#AFCA0A', 'SBU2': '#FFEC00', 'BANC': '#1976D2', 'CARTONS': '#FF9800'}
LIGNES    = ['SBU1', 'SBU2', 'BANC', 'CARTONS']

# Valeurs par défaut si la table BDD n'existe pas encore
OBJECTIFS_DEFAUT = {'SBU1': 3.20, 'SBU2': 3.16, 'BANC': 4.00, 'CARTONS': 0.88}

# ── GESTION OBJECTIFS BDD ─────────────────────────────────────
@st.cache_data(ttl=60)
def load_objectifs_historique():
    """Charge tous les objectifs depuis la BDD avec leur plage de validité."""
    try:
        conn = get_connection()
        df = pd.read_sql("""
            SELECT ligne, objectif_cadence, date_debut, date_fin, created_by, created_at
            FROM production_objectifs
            ORDER BY ligne, date_debut DESC
        """, conn)
        conn.close()
        if not df.empty:
            df['date_debut'] = pd.to_datetime(df['date_debut']).dt.date
            df['date_fin']   = pd.to_datetime(df['date_fin']).dt.date
        return df
    except Exception:
        return pd.DataFrame()

def get_objectifs_pour_date(d: date, df_obj: pd.DataFrame) -> dict:
    """
    Retourne le dict {ligne: objectif} valide à la date d.
    Fallback sur OBJECTIFS_DEFAUT si aucun objectif BDD trouvé.
    """
    result = dict(OBJECTIFS_DEFAUT)
    if df_obj.empty:
        return result
    for ligne in LIGNES:
        ld = df_obj[df_obj['ligne'] == ligne]
        valid = ld[
            (ld['date_debut'] <= d) &
            ((ld['date_fin'].isna()) | (ld['date_fin'] >= d))
        ]
        if not valid.empty:
            result[ligne] = float(valid.iloc[0]['objectif_cadence'])
    return result

def get_objectifs_courants(df_obj: pd.DataFrame) -> dict:
    """Objectifs valides aujourd'hui."""
    return get_objectifs_pour_date(date.today(), df_obj)

def save_objectif(ligne: str, objectif: float, date_debut: date,
                  date_fin, user: str) -> bool:
    """
    Insère un nouvel objectif. Clôture automatiquement le précédent.
    """
    try:
        conn = get_connection()
        cur  = conn.cursor()
        cur.execute("""
            UPDATE production_objectifs
            SET date_fin = %s
            WHERE ligne = %s
              AND (date_fin IS NULL OR date_fin >= %s)
              AND date_debut < %s
        """, (date_debut - timedelta(days=1), ligne,
              date_debut, date_debut))
        cur.execute("""
            INSERT INTO production_objectifs
                (ligne, objectif_cadence, date_debut, date_fin, created_by)
            VALUES (%s, %s, %s, %s, %s)
        """, (ligne, float(objectif),
              date_debut, date_fin if date_fin else None, user))
        conn.commit()
        cur.close()
        conn.close()
        return True
    except Exception as e:
        st.error(f"Erreur BDD : {e}")
        return False

# ── CHARGEMENT DONNÉES ────────────────────────────────────────
@st.cache_data(ttl=300)
def load_data():
    try:
        conn = get_connection()
        df = pd.read_sql("""
            SELECT * FROM production_fiches
            ORDER BY date_production
        """, conn)
        conn.close()
        if not df.empty:
            df['date_production'] = pd.to_datetime(df['date_production'], errors='coerce')
            df['poids_tonne']     = pd.to_numeric(df['poids_tonne'],     errors='coerce')
            df['duree_h']         = pd.to_numeric(df['duree_h'],         errors='coerce')
            df['cadence']         = pd.to_numeric(df['cadence'],         errors='coerce')
        return df
    except Exception:
        return pd.DataFrame()

# ── FALLBACK : lire depuis fichier si BDD vide ────────────────
def load_from_excel(file):
    df = pd.read_excel(file, sheet_name='Saisie')
    df = df.dropna(how='all')
    df = df.rename(columns={
        'Date de production ': 'date_production',
        'Ligne de production ': 'ligne',
        'Heure début': 'heure_debut',
        'Heure Fin ': 'heure_fin',
        'Durée': 'duree',
        'Poids en kg': 'poids_kg',
        'Poids en Tonne': 'poids_tonne',
        'Cadence ': 'cadence',
        'Marque': 'marque',
        'Type': 'type_prod',
        'Poids': 'poids_format',
        'Variété': 'variete',
        'Opérateur': 'operateur',
        'Equipe ': 'equipe',
        'heure': 'heure_num',
    })
    df['date_production'] = pd.to_datetime(df['date_production'], errors='coerce')
    df['poids_tonne']     = pd.to_numeric(df['poids_tonne'], errors='coerce')
    df['cadence']         = pd.to_numeric(df['cadence'], errors='coerce')
    df['ligne']           = df['ligne'].str.strip().str.upper()

    def parse_duree(val):
        try:
            if hasattr(val, 'hour'):
                return val.hour + val.minute/60 + val.second/3600
            parts = str(val).split(':')
            return int(parts[0]) + int(parts[1])/60 + int(parts[2])/3600
        except:
            return None
    df['duree_h'] = df['duree'].apply(parse_duree)
    df['semaine']       = df['date_production'].dt.isocalendar().week.astype('Int64')
    df['annee']         = df['date_production'].dt.isocalendar().year.astype('Int64')
    df['annee_semaine'] = df['annee'].astype(str) + '-S' + df['semaine'].astype(str).str.zfill(2)
    df['jour_label']    = df['date_production'].dt.strftime('%d/%m')
    return df

# ── IMPORT FICHIER OU BDD ─────────────────────────────────────
# ── CHARGEMENT OBJECTIFS ─────────────────────────────────────
df_objectifs = load_objectifs_historique()
OBJECTIFS = get_objectifs_courants(df_objectifs)

with st.sidebar:
    # ── Objectifs cadences actuels ──
    st.markdown("### 🎯 Objectifs cadences (T/h)")
    for ligne in LIGNES:
        obj = OBJECTIFS.get(ligne, OBJECTIFS_DEFAUT[ligne])
        st.markdown(f"- **{ligne}** : {obj:.2f} T/h")

    # ── Interface admin : modifier un objectif ──
    if is_admin():
        st.markdown("---")
        with st.expander("⚙️ Modifier un objectif (Admin)"):
            with st.container():
                sel_ligne = st.selectbox("Atelier", LIGNES, key="obj_ligne")
                obj_val   = st.number_input(
                    "Nouvel objectif (T/h)",
                    min_value=0.10, max_value=10.0,
                    value=float(OBJECTIFS.get(sel_ligne, OBJECTIFS_DEFAUT[sel_ligne])),
                    step=0.01, format="%.2f", key="obj_val"
                )
                obj_debut = st.date_input("Valide à partir du", value=date.today(), key="obj_debut")
                obj_fin   = st.date_input(
                    "Jusqu'au (laisser vide = ouvert)",
                    value=None, key="obj_fin"
                )
                if st.button("💾 Enregistrer l'objectif", key="obj_save"):
                    user = st.session_state.get('username', 'admin')
                    if save_objectif(sel_ligne, obj_val, obj_debut, obj_fin, user):
                        st.success(f"✅ Objectif {sel_ligne} mis à jour : {obj_val:.2f} T/h dès le {obj_debut}")
                        st.cache_data.clear()
                        st.rerun()

        # ── Historique des objectifs ──
        if not df_objectifs.empty:
            with st.expander("📋 Historique objectifs"):
                st.dataframe(
                    df_objectifs[['ligne','objectif_cadence','date_debut','date_fin','created_by']]
                    .rename(columns={
                        'ligne':'Atelier','objectif_cadence':'Obj (T/h)',
                        'date_debut':'Début','date_fin':'Fin','created_by':'Par'
                    }),
                    use_container_width=True, hide_index=True
                )

# Chargement BDD — si vide, les onglets d'analyse afficheront un message
# L'import se fait dans l'onglet 📥 Import
df = load_data()

# ── FILTRES GLOBAUX ───────────────────────────────────────────
def campagne_dates(year):
    return date(year - 1, 6, 1), date(year, 5, 31)

def get_campagnes():
    now = datetime.now()
    cy = now.year + 1 if now.month >= 6 else now.year
    return list(range(cy + 1, 2022, -1))

campagnes = get_campagnes()

with st.container():
    fc1, fc2, fc3, fc4 = st.columns([2, 1.5, 1.5, 2])
    with fc1:
        camp_opts = [0] + campagnes
        camp_labels = {0: "🔓 Toutes", **{y: f"Camp. {y} ({y-1}/06→{y}/05)" for y in campagnes}}
        sel_camp = st.selectbox("🗓️ Campagne", camp_opts, format_func=lambda y: camp_labels[y], key="f_camp")
    with fc2:
        d_min = campagne_dates(sel_camp)[0] if sel_camp else date(2022, 1, 1)
        d_max = campagne_dates(sel_camp)[1] if sel_camp else date(2027, 12, 31)
        date_deb = st.date_input("📅 Du", value=d_min, min_value=d_min, max_value=d_max, key="f_deb")
    with fc3:
        date_fin = st.date_input("📅 Au", value=d_max, min_value=d_min, max_value=d_max, key="f_fin")
    with fc4:
        mode_compare = st.selectbox("🔀 Comparaison", [
            "Aucune", "📅 Campagne vs Campagne", "📆 Mois vs Mois", "📆 Semaine vs Semaine"
        ], key="f_compare")

COMP_DATES = None
if mode_compare == "📅 Campagne vs Campagne":
    cc1, cc2 = st.columns(2)
    with cc1: c1 = st.selectbox("Campagne A", campagnes, key="comp_c1")
    with cc2: c2 = st.selectbox("Campagne B", [c for c in campagnes if c != c1], key="comp_c2")
    d1a, d1b = campagne_dates(c1); d2a, d2b = campagne_dates(c2)
    COMP_DATES = (f"Camp. {c1}", d1a, d1b, f"Camp. {c2}", d2a, d2b)
elif mode_compare == "📆 Mois vs Mois":
    mois_names = {1:'Janvier',2:'Février',3:'Mars',4:'Avril',5:'Mai',6:'Juin',
                  7:'Juillet',8:'Août',9:'Septembre',10:'Octobre',11:'Novembre',12:'Décembre'}
    cm1, cm2, cm3, cm4 = st.columns(4)
    with cm1: ma = st.selectbox("Mois A", range(1,13), format_func=lambda m: mois_names[m], key="comp_ma")
    with cm2: ya = st.number_input("Année A", 2022, 2027, datetime.now().year, key="comp_ya")
    with cm3: mb = st.selectbox("Mois B", range(1,13), format_func=lambda m: mois_names[m], index=max(0, datetime.now().month-2), key="comp_mb")
    with cm4: yb = st.number_input("Année B", 2022, 2027, datetime.now().year-1, key="comp_yb")
    d1a = date(int(ya), int(ma), 1); d1b = date(int(ya), int(ma), calendar.monthrange(int(ya), int(ma))[1])
    d2a = date(int(yb), int(mb), 1); d2b = date(int(yb), int(mb), calendar.monthrange(int(yb), int(mb))[1])
    COMP_DATES = (f"{mois_names[ma]} {ya}", d1a, d1b, f"{mois_names[mb]} {yb}", d2a, d2b)
elif mode_compare == "📆 Semaine vs Semaine":
    cs1, cs2, cs3, cs4 = st.columns(4)
    with cs1: sa  = st.number_input("Semaine A", 1, 53, max(1, datetime.now().isocalendar()[1]-1), key="comp_sa")
    with cs2: ysa = st.number_input("Année A", 2022, 2027, datetime.now().year, key="comp_ysa")
    with cs3: sb  = st.number_input("Semaine B", 1, 53, max(1, datetime.now().isocalendar()[1]-1), key="comp_sb")
    with cs4: ysb = st.number_input("Année B", 2022, 2027, datetime.now().year-1, key="comp_ysb")
    d1a = date.fromisocalendar(int(ysa), int(sa), 1); d1b = d1a + timedelta(days=6)
    d2a = date.fromisocalendar(int(ysb), int(sb), 1); d2b = d2a + timedelta(days=6)
    COMP_DATES = (f"S{sa}/{ysa}", d1a, d1b, f"S{sb}/{ysb}", d2a, d2b)

st.markdown("---")
DATE_DEB = date_deb
DATE_FIN = date_fin

# ── FONCTIONS UTILITAIRES ─────────────────────────────────────
def filter_df(df, d_from, d_to):
    if df.empty:
        return df
    # Forcer datetime64 si nécessaire
    if not pd.api.types.is_datetime64_any_dtype(df['date_production']):
        df = df.copy()
        df['date_production'] = pd.to_datetime(df['date_production'], errors='coerce')
    # Comparer en Timestamp pour éviter TypeError datetime64 vs date
    ts_from = pd.Timestamp(d_from)
    ts_to   = pd.Timestamp(d_to) + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)
    mask = (df['date_production'] >= ts_from) & (df['date_production'] <= ts_to)
    return df[mask].copy()

def calc_semaine(df, semaine_col='semaine'):
    """KPIs agrégés par semaine + ligne, avec objectif valide à la date de la semaine."""
    rows = []
    for (sem, ann), g in df.groupby([semaine_col, 'annee']):
        # Date représentative = premier jour de la semaine dans le groupe
        date_ref = g['date_production'].dropna().min().date() if not g.empty else date.today()
        obj_sem  = get_objectifs_pour_date(date_ref, df_objectifs)
        for ligne in LIGNES:
            ld = g[g['ligne'] == ligne]
            t = ld['poids_tonne'].sum()
            h = ld['duree_h'].sum()
            cad = t/h if h > 0 else 0
            obj = obj_sem.get(ligne, OBJECTIFS_DEFAUT[ligne])
            ro  = (cad - obj) / obj * 100 if obj > 0 and cad > 0 else None
            rows.append({'semaine': sem, 'annee': ann,
                         'annee_semaine': f"{ann}-S{int(sem):02d}",
                         'ligne': ligne, 'tonnage': t,
                         'duree_h': h, 'cadence': cad,
                         'objectif': obj, 'ro_pct': ro})
    return pd.DataFrame(rows)

def calc_journalier(df):
    """KPIs journaliers, avec objectif valide à la date du jour."""
    rows = []
    for (jour, ligne), g in df.groupby(['jour_label', 'ligne']):
        t = g['poids_tonne'].sum()
        h = g['duree_h'].sum()
        cad = t/h if h > 0 else 0
        date_ref = g['date_production'].dropna().min().date() if not g.empty else date.today()
        obj = get_objectifs_pour_date(date_ref, df_objectifs).get(ligne, OBJECTIFS_DEFAUT[ligne])
        ro  = (cad - obj) / obj * 100 if obj > 0 and cad > 0 else None
        rows.append({'jour': jour, 'ligne': ligne,
                     'tonnage': t, 'duree_h': h,
                     'cadence': cad, 'objectif': obj, 'ro_pct': ro,
                     'date': g['date_production'].iloc[0]})
    return pd.DataFrame(rows).sort_values('date')

def ro_badge(val):
    if val is None: return "—"
    color = "#AFCA0A" if val >= 0 else "#e53935"
    sign  = "+" if val >= 0 else ""
    return f'<span style="color:{color};font-weight:bold">{sign}{val:.1f}%%</span>'

def color_ro(val):
    if pd.isna(val): return ''
    return f'color: {"#AFCA0A" if val >= 0 else "#e53935"}; font-weight:bold'

# ── IMPORT BDD (upsert) ──────────────────────────────────────
def upsert_production(df_import: pd.DataFrame, user: str) -> tuple:
    """
    Upsert des fiches de production en BDD.
    Clé unique : (date_production, ligne, heure_debut, type_prod, variete)
    Retourne (nb_inserted, nb_updated, nb_errors)
    """
    conn = get_connection()
    cur  = conn.cursor()
    inserted = updated = errors = 0

    for _, row in df_import.iterrows():
        try:
            cur.execute("""
                INSERT INTO production_fiches
                    (date_production, ligne, heure_debut, heure_fin,
                     duree_h, poids_kg, poids_tonne, cadence,
                     marque, type_prod, poids_format, variete,
                     operateur, equipe, heure_num,
                     semaine, annee, annee_semaine, jour_label,
                     imported_by)
                VALUES (%s,%s,%s,%s, %s,%s,%s,%s, %s,%s,%s,%s, %s,%s,%s, %s,%s,%s,%s, %s)
                ON CONFLICT (date_production, ligne, heure_debut, type_prod, variete)
                DO UPDATE SET
                    heure_fin     = EXCLUDED.heure_fin,
                    duree_h       = EXCLUDED.duree_h,
                    poids_kg      = EXCLUDED.poids_kg,
                    poids_tonne   = EXCLUDED.poids_tonne,
                    cadence       = EXCLUDED.cadence,
                    marque        = EXCLUDED.marque,
                    poids_format  = EXCLUDED.poids_format,
                    operateur     = EXCLUDED.operateur,
                    equipe        = EXCLUDED.equipe,
                    heure_num     = EXCLUDED.heure_num,
                    semaine       = EXCLUDED.semaine,
                    annee         = EXCLUDED.annee,
                    annee_semaine = EXCLUDED.annee_semaine,
                    jour_label    = EXCLUDED.jour_label,
                    imported_by   = EXCLUDED.imported_by
            """, (
                row.get('date_production'),
                str(row.get('ligne', '')),
                row.get('heure_debut'),
                row.get('heure_fin'),
                float(row['duree_h'])      if pd.notna(row.get('duree_h'))      else None,
                float(row['poids_kg'])     if pd.notna(row.get('poids_kg'))     else None,
                float(row['poids_tonne'])  if pd.notna(row.get('poids_tonne'))  else None,
                float(row['cadence'])      if pd.notna(row.get('cadence'))      else None,
                str(row.get('marque', '')),
                str(row.get('type_prod', '')),
                float(row['poids_format']) if pd.notna(row.get('poids_format')) else None,
                str(row.get('variete', '')),
                str(row.get('operateur', '')),
                str(row.get('equipe', '')),
                int(row['heure_num'])      if pd.notna(row.get('heure_num'))    else None,
                int(row['semaine'])        if pd.notna(row.get('semaine'))      else None,
                int(row['annee'])          if pd.notna(row.get('annee'))        else None,
                str(row.get('annee_semaine', '')),
                str(row.get('jour_label', '')),
                user,
            ))
            if cur.rowcount == 1:
                inserted += 1
            else:
                updated += 1
        except Exception:
            errors += 1
            conn.rollback()
            continue

    conn.commit()
    cur.close()
    conn.close()
    return inserted, updated, errors

# ── FILTRAGE PRINCIPAL ────────────────────────────────────────
df_filt = filter_df(df, DATE_DEB, DATE_FIN)

# ── ONGLETS ───────────────────────────────────────────────────
tab_import, tab_vue, tab_hebdo, tab_cadences, tab_journalier, tab_recettes = st.tabs([
    "📥 Import",
    "📊 Vue globale",
    "📈 Évolution hebdo",
    "⚡ Cadences R/O",
    "📅 Journalier S10",
    "🥔 Mix recettes",
])

# ═══════════════════════════════════════════════════════════════
# ONGLET IMPORT
# ═══════════════════════════════════════════════════════════════
with tab_import:
    st.subheader("📥 Import fichier Excel production")
    st.caption("Fichier issu de l'onglet **Saisie** du classeur de fiches de production.")

    file_import = st.file_uploader(
        "Sélectionner le fichier Excel",
        type=['xlsx'], key="prod_import_file"
    )

    if file_import:
        # ── Lecture unique avec openpyxl read_only + cache session_state ──
        file_id = f"{file_import.name}_{file_import.size}"
        if st.session_state.get('prod_file_id') != file_id:
            with st.spinner("Lecture du fichier en cours…"):
                try:
                    file_bytes = file_import.read()
                    import io as _io
                    df_cache = load_from_excel(_io.BytesIO(file_bytes))
                    df_cache = df_cache.dropna(subset=['date_production', 'ligne', 'poids_tonne'])
                    st.session_state['prod_df_cache'] = df_cache
                    st.session_state['prod_file_id']  = file_id
                except Exception as e:
                    st.error(f"Erreur lecture fichier : {e}")
                    st.stop()

        df_preview = st.session_state.get('prod_df_cache', pd.DataFrame())

        if not df_preview.empty:
            sem_list = sorted(df_preview['annee_semaine'].dropna().unique())
            col_k1, col_k2, col_k3, col_k4 = st.columns(4)
            col_k1.metric("📅 Semaines", len(sem_list))
            col_k2.metric("🏭 Lignes", df_preview['ligne'].nunique())
            col_k3.metric("⚖️ Tonnage total", f"{df_preview['poids_tonne'].sum():.1f} T")
            col_k4.metric("📋 Fiches", len(df_preview))

            st.markdown("**Semaines dans le fichier :** " + " | ".join(sem_list))

            with st.expander("🔍 Aperçu des données (10 premières lignes)"):
                st.dataframe(
                    df_preview[['date_production','ligne','type_prod','variete',
                                 'poids_tonne','duree_h','cadence','marque','equipe']]
                    .head(10),
                    use_container_width=True, hide_index=True
                )

            st.markdown("---")
            st.info(
                "**Mode upsert** : les lignes existantes (même date + ligne + heure + type + variété) "
                "sont **mises à jour**. Les nouvelles lignes sont **ajoutées**. "
                "Aucune suppression de l'historique."
            )

            if st.button("⬆️ Importer en base de données", type="primary", key="prod_do_import"):
                user = st.session_state.get('username', 'inconnu')
                with st.spinner("Import en cours…"):
                    ins, upd, err = upsert_production(df_preview, user)
                if err == 0:
                    st.success(f"✅ Import terminé — {ins} ajoutées, {upd} mises à jour, 0 erreur")
                    st.cache_data.clear()
                    st.session_state.pop('prod_file_id', None)
                    st.rerun()
                else:
                    st.warning(f"⚠️ Import partiel — {ins} ajoutées, {upd} mises à jour, {err} erreurs")
    else:
        st.info("Glissez-déposez le fichier Excel pour commencer.")

    # ── Résumé de ce qui est déjà en BDD ──
    st.markdown("---")
    st.subheader("📊 Données actuellement en base")
    df_bdd_info = load_data()
    if not df_bdd_info.empty:
        bdd_sem = sorted(df_bdd_info['annee_semaine'].dropna().unique())
        col_b1, col_b2, col_b3 = st.columns(3)
        col_b1.metric("📅 Semaines en base", len(bdd_sem))
        col_b2.metric("📋 Fiches totales",   len(df_bdd_info))
        col_b3.metric("⚖️ Tonnage total",    f"{df_bdd_info['poids_tonne'].sum():.1f} T")
        if bdd_sem:
            st.markdown("**Semaines :** " + " | ".join(bdd_sem))
    else:
        st.info("Base vide — aucune fiche importée.")


# ═══════════════════════════════════════════════════════════════
# ONGLET 1 : VUE GLOBALE
# ═══════════════════════════════════════════════════════════════
with tab_vue:
    if df.empty:
        st.info("📤 Aucune donnée en base. Utilisez l'onglet 📥 **Import** pour charger les fiches de production.")
    else:

        if COMP_DATES:
            la, d1a, d1b, lb, d2a, d2b = COMP_DATES
            st.info(f"🔀 Comparaison : **{la}** vs **{lb}**")
            dfA = filter_df(df, d1a, d1b)
            dfB = filter_df(df, d2a, d2b)

            def render_vue_globale(d, label):
                st.markdown(f"### {label}")
                tot = d['poids_tonne'].sum()
                h_tot = d['duree_h'].sum()
                cad_moy = tot/h_tot if h_tot > 0 else 0
                nb_jours = d['date_production'].dt.date.nunique()
                c1,c2,c3,c4 = st.columns(4)
                c1.metric("🏭 Tonnage total", f"{tot:.1f} T")
                c2.metric("⏱ Heures prod.", f"{h_tot:.1f} h")
                c3.metric("⚡ Cadence moy.", f"{cad_moy:.2f} T/h")
                c4.metric("📅 Jours", nb_jours)
                # Par ligne
                rows = []
                for ligne in LIGNES:
                    ld = d[d['ligne'] == ligne]
                    t = ld['poids_tonne'].sum()
                    h = ld['duree_h'].sum()
                    cad = t/h if h > 0 else 0
                    obj = OBJECTIFS.get(ligne, OBJECTIFS_DEFAUT[ligne])
                    ro  = (cad - obj)/obj*100 if obj > 0 and cad > 0 else None
                    rows.append({'Ligne': ligne, 'Tonnage': round(t,1),
                                 'Heures': round(h,1), 'Cadence': round(cad,2),
                                 'Obj.': obj, 'R/O %%': round(ro,1) if ro is not None else None})
                st_df = pd.DataFrame(rows)
                st.dataframe(
                    st_df.style.applymap(color_ro, subset=['R/O %%']),
                    use_container_width=True, hide_index=True
                )

            colA, colB = st.columns(2)
            with colA: render_vue_globale(dfA, la)
            with colB: render_vue_globale(dfB, lb)

        else:
            # ── KPIs globaux ──
            tot = df_filt['poids_tonne'].sum()
            h_tot = df_filt['duree_h'].sum()
            cad_moy = tot/h_tot if h_tot > 0 else 0
            nb_sem = df_filt['annee_semaine'].nunique()
            nb_jours = df_filt['date_production'].dt.date.nunique()

            c1,c2,c3,c4,c5 = st.columns(5)
            c1.metric("🏭 Tonnage total",   f"{tot:.1f} T")
            c2.metric("📅 Semaines",         nb_sem)
            c3.metric("🗓 Jours prod.",       nb_jours)
            c4.metric("⏱ Heures totales",   f"{h_tot:.0f} h")
            c5.metric("⚡ Cadence moyenne",  f"{cad_moy:.2f} T/h")

            st.markdown("---")

            # ── KPIs par ligne ──
            st.subheader("Vue par atelier")
            cols = st.columns(4)
            for i, ligne in enumerate(LIGNES):
                ld = df_filt[df_filt['ligne'] == ligne]
                t  = ld['poids_tonne'].sum()
                h  = ld['duree_h'].sum()
                cad = t/h if h > 0 else 0
                obj = OBJECTIFS.get(ligne, OBJECTIFS_DEFAUT[ligne])
                ro  = (cad - obj)/obj*100 if obj > 0 and cad > 0 else None
                pct_tot = t/tot*100 if tot > 0 else 0
                with cols[i]:
                    sign = "+" if (ro or 0) >= 0 else ""
                    delta_color = "normal" if (ro or 0) >= 0 else "inverse"
                    st.metric(f"**{ligne}**",
                              f"{t:.1f} T",
                              delta=f"{sign}{ro:.1f}%% R/O" if ro is not None else None,
                              delta_color=delta_color)
                    st.caption(f"⚡ {cad:.2f} T/h (obj {obj}) | ⏱ {h:.0f}h | {pct_tot:.1f}%% du total")

            st.markdown("---")

            # ── Graphe camembert tonnage par ligne ──
            col_g1, col_g2 = st.columns(2)

            with col_g1:
                pie_data = []
                for ligne in LIGNES:
                    t = df_filt[df_filt['ligne'] == ligne]['poids_tonne'].sum()
                    if t > 0:
                        pie_data.append({'Ligne': ligne, 'Tonnage': t})
                if pie_data:
                    fig_pie = px.pie(pd.DataFrame(pie_data), names='Ligne', values='Tonnage',
                                     title="Répartition tonnage par atelier",
                                     color='Ligne',
                                     color_discrete_map=COULEURS,
                                     hole=0.4)
                    fig_pie.update_layout(height=340, margin=dict(t=50,b=10),
                                          paper_bgcolor='white')
                    st.plotly_chart(fig_pie, use_container_width=True)

            with col_g2:
                # Bar R/O par ligne
                ro_data = []
                for ligne in LIGNES:
                    ld = df_filt[df_filt['ligne'] == ligne]
                    t = ld['poids_tonne'].sum()
                    h = ld['duree_h'].sum()
                    cad = t/h if h > 0 else 0
                    obj = OBJECTIFS.get(ligne, OBJECTIFS_DEFAUT[ligne])
                    ro  = (cad - obj)/obj*100 if obj > 0 and cad > 0 else 0
                    ro_data.append({'Ligne': ligne, 'R/O (%%)': ro})
                df_ro = pd.DataFrame(ro_data)
                fig_ro = px.bar(df_ro, x='Ligne', y='R/O (%%)',
                                title="R/O Cadence par atelier (%%)",
                                color='R/O (%%)',
                                color_continuous_scale=['#e53935','#f5f5f5','#AFCA0A'],
                                color_continuous_midpoint=0,
                                text='R/O (%%)')
                fig_ro.update_traces(texttemplate='%%{text:.1f}%%', textposition='outside')
                fig_ro.add_hline(y=0, line_dash='dash', line_color='#7A7A7A')
                fig_ro.update_layout(height=340, margin=dict(t=50,b=10),
                                     paper_bgcolor='white', plot_bgcolor='white',
                                     coloraxis_showscale=False)
                st.plotly_chart(fig_ro, use_container_width=True)

            # ── Tableau récap par ligne ──
            st.markdown("---")
            rows = []
            for ligne in LIGNES:
                ld = df_filt[df_filt['ligne'] == ligne]
                t   = ld['poids_tonne'].sum()
                h   = ld['duree_h'].sum()
                cad = t/h if h > 0 else 0
                obj = OBJECTIFS.get(ligne, OBJECTIFS_DEFAUT[ligne])
                ro  = (cad - obj)/obj*100 if obj > 0 and cad > 0 else None
                rows.append({'Atelier': ligne,
                             'Tonnage (T)': round(t,1),
                             'Heures': round(h,1),
                             'Cadence (T/h)': round(cad,3),
                             'Objectif (T/h)': obj,
                             'R/O (%%)': round(ro,1) if ro is not None else None})
            df_rows = pd.DataFrame(rows)
            df_rows['R/O (%%)'] = pd.to_numeric(df_rows['R/O (%%)'], errors='coerce')
            st.dataframe(
                df_rows,
                use_container_width=True, hide_index=True,
                column_config={
                    'Cadence (T/h)':  st.column_config.NumberColumn(format="%.3f"),
                    'Objectif (T/h)': st.column_config.NumberColumn(format="%.2f"),
                    'R/O (%%)':       st.column_config.NumberColumn(format="%+.1f %%"),
                }
            )


# ═══════════════════════════════════════════════════════════════
# ONGLET 2 : ÉVOLUTION HEBDO
# ═══════════════════════════════════════════════════════════════
with tab_hebdo:
    if df.empty:
        st.info("📤 Aucune donnée en base. Utilisez l'onglet 📥 **Import** pour charger les fiches de production.")
    else:
        st.subheader("📈 Évolution hebdomadaire des tonnages")

        df_sem = calc_semaine(df_filt)

        if df_sem.empty:
            st.info("Aucune donnée.")
        else:
            # Pivot tonnage par semaine × ligne
            pivot_t = df_sem.pivot_table(index='annee_semaine', columns='ligne',
                                         values='tonnage', aggfunc='sum').fillna(0)
            pivot_t = pivot_t.reset_index().rename(columns={'annee_semaine': 'Semaine'})

            # Bar groupé tonnage
            fig_t = go.Figure()
            for ligne in LIGNES:
                if ligne in pivot_t.columns:
                    fig_t.add_trace(go.Bar(
                        name=ligne,
                        x=pivot_t['Semaine'],
                        y=pivot_t[ligne],
                        marker_color=COULEURS[ligne],
                        text=pivot_t[ligne].apply(lambda v: f"{v:.0f}T"),
                        textposition='auto',
                    ))
            fig_t.update_layout(
                barmode='stack',
                title="Tonnage réalisé par semaine & atelier",
                xaxis_title="Semaine", yaxis_title="Tonnes",
                plot_bgcolor='white', paper_bgcolor='white',
                height=400, xaxis_tickangle=-30,
                legend=dict(orientation='h', yanchor='bottom', y=1.02),
                margin=dict(t=60, b=60),
            )
            st.plotly_chart(fig_t, use_container_width=True)

            # Total hebdo avec évolution S vs S-1
            st.markdown("---")
            total_sem = df_sem.groupby('annee_semaine')['tonnage'].sum().reset_index()
            total_sem.columns = ['Semaine', 'Total (T)']
            total_sem['Évol. (T)'] = total_sem['Total (T)'].diff()
            total_sem['Évol. (%%)'] = total_sem['Total (T)'].pct_change() * 100

            col_g, col_t = st.columns([2, 1])
            with col_g:
                fig_line = px.line(total_sem, x='Semaine', y='Total (T)',
                                   markers=True, title="Tonnage total hebdomadaire",
                                   color_discrete_sequence=['#AFCA0A'])
                fig_line.update_traces(line_width=3, marker_size=8)
                fig_line.update_layout(plot_bgcolor='white', paper_bgcolor='white',
                                       height=300, margin=dict(t=50,b=50))
                st.plotly_chart(fig_line, use_container_width=True)
            with col_t:
                st.dataframe(
                    total_sem,
                    use_container_width=True, hide_index=True,
                    column_config={
                        'Total (T)':   st.column_config.NumberColumn(format="%.1f T"),
                        'Évol. (T)':   st.column_config.NumberColumn(format="%+.1f T"),
                        'Évol. (%%)':  st.column_config.NumberColumn(format="%+.1f %%"),
                    }
                )

            # Cadences hebdo par ligne
            st.markdown("---")
            st.subheader("⚡ Cadences hebdomadaires par atelier (T/h)")
            fig_cad = go.Figure()
            for ligne in LIGNES:
                ld = df_sem[df_sem['ligne'] == ligne].sort_values('annee_semaine')
                if ld.empty: continue
                fig_cad.add_trace(go.Scatter(
                    name=ligne,
                    x=ld['annee_semaine'], y=ld['cadence'],
                    mode='lines+markers',
                    line=dict(color=COULEURS[ligne], width=2),
                    marker=dict(size=8),
                ))
                # Ligne objectif
                fig_cad.add_hline(y=OBJECTIFS.get(ligne, OBJECTIFS_DEFAUT[ligne]), line_dash='dot',
                                   line_color=COULEURS[ligne], opacity=0.5,
                                   annotation_text=f"Obj {ligne}: {OBJECTIFS.get(ligne, OBJECTIFS_DEFAUT[ligne])}",
                                   annotation_position="right")
            fig_cad.update_layout(
                plot_bgcolor='white', paper_bgcolor='white', height=380,
                xaxis_tickangle=-30, margin=dict(t=30,b=60,r=120),
                legend=dict(orientation='h', yanchor='bottom', y=1.02),
            )
            st.plotly_chart(fig_cad, use_container_width=True)

            # Tableau R/O par ligne × semaine
            st.markdown("---")
            st.subheader("📋 Tableau R/O Cadence (%%)")
            pivot_ro = df_sem.pivot_table(index='annee_semaine', columns='ligne',
                                          values='ro_pct', aggfunc='mean')
            st.dataframe(
                pivot_ro.style.applymap(color_ro)
                              .format('{:+.1f}%%', na_rep='—'),
                use_container_width=True
            )


# ═══════════════════════════════════════════════════════════════
# ONGLET 3 : CADENCES R/O PAR LIGNE (vue détaillée)
# ═══════════════════════════════════════════════════════════════
with tab_cadences:
    if df.empty:
        st.info("📤 Aucune donnée en base. Utilisez l'onglet 📥 **Import** pour charger les fiches de production.")
    else:
        st.subheader("⚡ R/O Cadence — Semaines + Journalier semaine courante")

        # Sélection semaine focus
        semaines_dispo = sorted(df_filt['annee_semaine'].dropna().unique(), reverse=True)
        sem_focus = st.selectbox("Semaine focus (journalier)", semaines_dispo, key="cad_sem") if semaines_dispo else None

        df_sem_all = calc_semaine(df_filt)

        for ligne in LIGNES:
            with st.expander(f"**{ligne}** — Obj : {OBJECTIFS.get(ligne, OBJECTIFS_DEFAUT[ligne])} T/h", expanded=(ligne == 'SBU1')):
                ld_sem = df_sem_all[df_sem_all['ligne'] == ligne].sort_values('annee_semaine')
                ld_jour = calc_journalier(df_filt[
                    (df_filt['ligne'] == ligne) &
                    (df_filt['annee_semaine'] == sem_focus)
                ]) if sem_focus else pd.DataFrame()

                fig = go.Figure()

                # Barres hebdo
                if not ld_sem.empty:
                    colors = ['#AFCA0A' if r >= 0 else '#e53935'
                              for r in ld_sem['ro_pct'].fillna(0)]
                    fig.add_trace(go.Bar(
                        name='Cadence hebdo',
                        x=ld_sem['annee_semaine'],
                        y=ld_sem['cadence'],
                        marker_color=colors,
                        text=ld_sem['cadence'].apply(lambda v: f"{v:.2f}"),
                        textposition='outside',
                        opacity=0.85,
                    ))

                # Points journaliers
                if not ld_jour.empty:
                    fig.add_trace(go.Scatter(
                        name=f'Journalier {sem_focus}',
                        x=ld_jour['jour'],
                        y=ld_jour['cadence'],
                        mode='lines+markers',
                        line=dict(color='#1976D2', width=2, dash='dot'),
                        marker=dict(size=10, color='#1976D2'),
                    ))

                # Ligne objectif
                fig.add_hline(y=OBJECTIFS.get(ligne, OBJECTIFS_DEFAUT[ligne]), line_dash='dash',
                              line_color='#7A7A7A',
                              annotation_text=f"Obj: {OBJECTIFS.get(ligne, OBJECTIFS_DEFAUT[ligne])} T/h",
                              annotation_position="right")

                fig.update_layout(
                    plot_bgcolor='white', paper_bgcolor='white',
                    height=320, margin=dict(t=20, b=50, r=100),
                    xaxis_tickangle=-30,
                    legend=dict(orientation='h', yanchor='bottom', y=1.02),
                )
                st.plotly_chart(fig, use_container_width=True)

                # Tableau récap
                rows = []
                for _, r in ld_sem.iterrows():
                    rows.append({
                        'Période': r['annee_semaine'],
                        'Cadence': round(r['cadence'], 2),
                        'Tonnage': round(r['tonnage'], 1),
                        'Heures': round(r['duree_h'], 1),
                        'R/O (%%)': round(r['ro_pct'], 1) if pd.notna(r['ro_pct']) else None,
                    })
                if not ld_jour.empty:
                    for _, r in ld_jour.iterrows():
                        rows.append({
                            'Période': f"  {r['jour']} ↳",
                            'Cadence': round(r['cadence'], 2),
                            'Tonnage': round(r['tonnage'], 1),
                            'Heures': round(r['duree_h'], 1),
                            'R/O (%%)': round(r['ro_pct'], 1) if pd.notna(r['ro_pct']) else None,
                        })
                if rows:
                    st.dataframe(
                        pd.DataFrame(rows),
                        use_container_width=True, hide_index=True,
                        column_config={
                            'Cadence':  st.column_config.NumberColumn(format="%.2f T/h"),
                            'Objectif': st.column_config.NumberColumn(format="%.2f T/h"),
                            'R/O (%%)': st.column_config.NumberColumn(format="%+.1f %%"),
                        }
                    )


# ═══════════════════════════════════════════════════════════════
# ONGLET 4 : JOURNALIER (semaine sélectionnée)
# ═══════════════════════════════════════════════════════════════
with tab_journalier:
    if df.empty:
        st.info("📤 Aucune donnée en base. Utilisez l'onglet 📥 **Import** pour charger les fiches de production.")
    else:
        semaines_j = sorted(df_filt['annee_semaine'].dropna().unique(), reverse=True)
        if not semaines_j:
            st.info("Aucune donnée.")
        else:
            sem_j = st.selectbox("Semaine", semaines_j, key="jour_sem")
            df_j = df_filt[df_filt['annee_semaine'] == sem_j].copy()
            df_jour = calc_journalier(df_j)

            if df_jour.empty:
                st.info("Pas de données pour cette semaine.")
            else:
                # KPIs semaine
                tot_j = df_j['poids_tonne'].sum()
                h_j   = df_j['duree_h'].sum()
                cad_j = tot_j/h_j if h_j > 0 else 0
                nb_j  = df_j['date_production'].dt.date.nunique()

                c1,c2,c3,c4 = st.columns(4)
                c1.metric("🏭 Tonnage semaine", f"{tot_j:.1f} T")
                c2.metric("📅 Jours actifs",    nb_j)
                c3.metric("⏱ Heures totales",  f"{h_j:.0f} h")
                c4.metric("⚡ Cadence moy.",    f"{cad_j:.2f} T/h")

                st.markdown("---")

                # KPIs par atelier
                st.subheader(f"Vue par atelier — {sem_j}")
                cols_a = st.columns(4)
                for i, ligne in enumerate(LIGNES):
                    ld = df_j[df_j['ligne'] == ligne]
                    t  = ld['poids_tonne'].sum()
                    h  = ld['duree_h'].sum()
                    cad = t/h if h > 0 else 0
                    obj = OBJECTIFS.get(ligne, OBJECTIFS_DEFAUT[ligne])
                    ro  = (cad - obj)/obj*100 if obj > 0 and cad > 0 else None
                    with cols_a[i]:
                        sign = "+" if (ro or 0) >= 0 else ""
                        delta_color = "normal" if (ro or 0) >= 0 else "inverse"
                        st.metric(ligne, f"{t:.1f} T",
                                  delta=f"{sign}{ro:.1f}%% R/O" if ro is not None else None,
                                  delta_color=delta_color)
                        st.caption(f"{cad:.2f} T/h | {h:.0f}h | obj {obj}")

                st.markdown("---")

                # Graphe tonnages journaliers par ligne
                pivot_j = df_jour.pivot_table(index='jour', columns='ligne',
                                              values='tonnage', aggfunc='sum').fillna(0)

                # Réordonner par date
                ordre_jours = df_j.drop_duplicates('jour_label').sort_values('date_production')['jour_label'].tolist()
                pivot_j = pivot_j.reindex([j for j in ordre_jours if j in pivot_j.index])
                pivot_j = pivot_j.reset_index()

                fig_j = go.Figure()
                for ligne in LIGNES:
                    if ligne in pivot_j.columns:
                        fig_j.add_trace(go.Bar(
                            name=ligne, x=pivot_j['jour'], y=pivot_j[ligne],
                            marker_color=COULEURS[ligne],
                            text=pivot_j[ligne].apply(lambda v: f"{v:.0f}T" if v > 0 else ""),
                            textposition='auto',
                        ))
                # Total par jour
                if len(pivot_j) > 0:
                    cols_lignes = [c for c in LIGNES if c in pivot_j.columns]
                    pivot_j['total'] = pivot_j[cols_lignes].sum(axis=1)
                    fig_j.add_trace(go.Scatter(
                        name='Total', x=pivot_j['jour'], y=pivot_j['total'],
                        mode='lines+markers+text',
                        text=pivot_j['total'].apply(lambda v: f"{v:.0f}T"),
                        textposition='top center',
                        line=dict(color='#424242', width=2, dash='dot'),
                        marker=dict(size=8),
                    ))
                fig_j.update_layout(
                    barmode='stack', title=f"Tonnages journaliers — {sem_j}",
                    plot_bgcolor='white', paper_bgcolor='white',
                    height=380, xaxis_title="Jour", yaxis_title="Tonnes",
                    legend=dict(orientation='h', yanchor='bottom', y=1.02),
                    margin=dict(t=60,b=50),
                )
                st.plotly_chart(fig_j, use_container_width=True)

                # Graphe cadences journalières
                fig_cad_j = go.Figure()
                for ligne in ['SBU1','SBU2','BANC']:
                    ld = df_jour[df_jour['ligne'] == ligne]
                    if ld.empty: continue
                    # Couleur point vert/rouge selon R/O
                    colors_pt = ['#AFCA0A' if (r or 0) >= 0 else '#e53935'
                                 for r in ld['ro_pct']]
                    fig_cad_j.add_trace(go.Scatter(
                        name=ligne, x=ld['jour'], y=ld['cadence'],
                        mode='lines+markers',
                        line=dict(color=COULEURS[ligne], width=2),
                        marker=dict(size=10, color=colors_pt, line=dict(width=2, color='white')),
                    ))
                    fig_cad_j.add_hline(y=OBJECTIFS.get(ligne, OBJECTIFS_DEFAUT[ligne]), line_dash='dot',
                                        line_color=COULEURS[ligne], opacity=0.4)
                fig_cad_j.update_layout(
                    title=f"Cadences journalières — {sem_j}",
                    plot_bgcolor='white', paper_bgcolor='white',
                    height=340, xaxis_title="Jour", yaxis_title="T/h",
                    legend=dict(orientation='h', yanchor='bottom', y=1.02),
                    margin=dict(t=60,b=50),
                )
                st.plotly_chart(fig_cad_j, use_container_width=True)

                # Tableau détail journalier par ligne
                st.markdown("---")
                st.subheader("📋 Détail journalier par atelier")
                pivot_tab = df_jour.pivot_table(
                    index='jour', columns='ligne',
                    values=['tonnage','cadence','ro_pct'],
                    aggfunc='first'
                ).round(2)
                st.dataframe(pivot_tab, use_container_width=True)


# ═══════════════════════════════════════════════════════════════
# ONGLET 5 : MIX RECETTES
# ═══════════════════════════════════════════════════════════════
with tab_recettes:
    if df.empty:
        st.info("📤 Aucune donnée en base. Utilisez l'onglet 📥 **Import** pour charger les fiches de production.")
    else:
        st.subheader("🥔 Mix recettes & variétés")

        if COMP_DATES:
            la, d1a, d1b, lb, d2a, d2b = COMP_DATES
            st.info(f"🔀 Comparaison : **{la}** vs **{lb}**")
            dfA = filter_df(df, d1a, d1b)
            dfB = filter_df(df, d2a, d2b)

            def render_mix(d, label):
                st.markdown(f"### {label}")
                # Par type (regroupé PDP / CHAMP)
                d['famille'] = d['marque'].apply(
                    lambda m: 'PDP' if str(m).strip().upper() == 'PDP'
                    else ('Championne' if 'CHAMP' in str(m).upper() else 'CP'))
                fam = d.groupby('famille')['poids_tonne'].sum().reset_index()
                fig_f = px.pie(fam, names='famille', values='poids_tonne',
                               color='famille',
                               color_discrete_map={'PDP':'#AFCA0A','Championne':'#FFEC00','CP':'#1976D2'},
                               hole=0.4, title=f"Mix PDP / Championne — {label}")
                fig_f.update_layout(height=280, margin=dict(t=50,b=10))
                st.plotly_chart(fig_f, use_container_width=True)

                # Top variétés
                var = d.groupby('variete')['poids_tonne'].sum().sort_values(ascending=False).head(8).reset_index()
                fig_v = px.bar(var, x='poids_tonne', y='variete', orientation='h',
                               title=f"Top variétés — {label}",
                               color='poids_tonne',
                               color_continuous_scale=['#FFEC00','#AFCA0A'],
                               labels={'poids_tonne':'Tonnes','variete':'Variété'})
                fig_v.update_layout(height=300, margin=dict(t=50,b=10),
                                    plot_bgcolor='white', paper_bgcolor='white',
                                    coloraxis_showscale=False, yaxis_autorange='reversed')
                st.plotly_chart(fig_v, use_container_width=True)

            colA, colB = st.columns(2)
            with colA: render_mix(dfA, la)
            with colB: render_mix(dfB, lb)

        else:
            col_r1, col_r2 = st.columns(2)

            # Marques
            with col_r1:
                df_filt2 = df_filt.copy()
                df_filt2['famille'] = df_filt2['marque'].apply(
                    lambda m: 'PDP' if str(m).strip().upper() == 'PDP'
                    else ('Championne' if 'CHAMP' in str(m).upper() else str(m)))
                fam = df_filt2.groupby('famille')['poids_tonne'].sum().reset_index()
                fig_fam = px.pie(fam, names='famille', values='poids_tonne',
                                 color='famille',
                                 color_discrete_map={'PDP':'#AFCA0A','Championne':'#FFEC00'},
                                 hole=0.4, title="Répartition PDP / Championne / CP")
                fig_fam.update_layout(height=320, margin=dict(t=50,b=10), paper_bgcolor='white')
                st.plotly_chart(fig_fam, use_container_width=True)

            with col_r2:
                # Top variétés
                var = df_filt.groupby('variete')['poids_tonne'].sum().sort_values(ascending=False).head(10).reset_index()
                fig_var = px.bar(var, x='poids_tonne', y='variete', orientation='h',
                                 title="Top 10 variétés (T)",
                                 color='poids_tonne',
                                 color_continuous_scale=['#FFEC00','#AFCA0A'],
                                 labels={'poids_tonne':'Tonnes','variete':'Variété'})
                fig_var.update_layout(height=320, margin=dict(t=50,b=10),
                                      plot_bgcolor='white', paper_bgcolor='white',
                                      coloraxis_showscale=False, yaxis_autorange='reversed')
                st.plotly_chart(fig_var, use_container_width=True)

            st.markdown("---")

            # PDP vs Championne par semaine
            st.subheader("📈 PDP vs Championne — Évolution hebdo")
            df_filt3 = df_filt.copy()
            df_filt3['famille'] = df_filt3['marque'].apply(
                lambda m: 'PDP' if str(m).strip().upper() == 'PDP'
                else ('Championne' if 'CHAMP' in str(m).upper() else 'CP'))
            sem_fam = df_filt3.groupby(['annee_semaine','famille'])['poids_tonne'].sum().reset_index()
            fig_sf = px.bar(sem_fam, x='annee_semaine', y='poids_tonne',
                            color='famille', barmode='group',
                            color_discrete_map={'PDP':'#AFCA0A','Championne':'#FFEC00','CP':'#1976D2'},
                            labels={'annee_semaine':'Semaine','poids_tonne':'Tonnes'},
                            title="Tonnage PDP / Championne / CP par semaine")
            fig_sf.update_layout(plot_bgcolor='white', paper_bgcolor='white',
                                 height=360, xaxis_tickangle=-30,
                                 legend=dict(orientation='h', yanchor='bottom', y=1.02),
                                 margin=dict(t=60,b=60))
            st.plotly_chart(fig_sf, use_container_width=True)

            # Tableau cadences PDP vs CHAMP par type (style slide 13)
            st.markdown("---")
            st.subheader("⚡ Cadences PDP vs Championne par type de recette")

            sem_focus_r = st.selectbox("Semaine focus", semaines_dispo if semaines_dispo else [''], key="rec_sem")
            df_r = df_filt[df_filt['annee_semaine'] == sem_focus_r].copy() if sem_focus_r else df_filt.copy()
            df_r = df_r[df_r['ligne'].isin(['SBU1','SBU2'])]

            # Catégoriser type de recette
            def cat_recette(t):
                t = str(t).upper()
                if 'FOUR' in t or 'POTAGE' in t: return 'Four'
                if 'FRITE' in t: return 'Frites'
                if 'VAPEUR' in t and 'JAUNE' in t: return 'Vapeur Jaune'
                if 'VAPEUR' in t and 'ROUGE' in t: return 'Vapeur Rouge'
                if 'GRENAL' in t or 'GRENIL' in t: return 'Grenailles'
                return 'Autre'

            df_r['recette'] = df_r['type_prod'].apply(cat_recette)
            df_r['famille'] = df_r['marque'].apply(
                lambda m: 'PDP' if str(m).strip().upper() == 'PDP' else 'Championne')

            rows_rec = []
            for (recette, fam), g in df_r.groupby(['recette','famille']):
                t = g['poids_tonne'].sum()
                h = g['duree_h'].sum()
                cad = t/h if h > 0 else 0
                rows_rec.append({'Recette': recette, 'Famille': fam,
                                 'Tonnage (T)': round(t,1),
                                 'Cadence (T/h)': round(cad,2)})
            if rows_rec:
                df_rec = pd.DataFrame(rows_rec)
                pivot_rec = df_rec.pivot_table(index='Recette', columns='Famille',
                                               values=['Tonnage (T)','Cadence (T/h)'],
                                               aggfunc='first').round(2)
                st.dataframe(pivot_rec, use_container_width=True)

                # Graphe cadences PDP vs Champ
                pdp  = df_rec[df_rec['Famille']=='PDP']
                chmp = df_rec[df_rec['Famille']=='Championne']
                if not pdp.empty and not chmp.empty:
                    fig_rec = go.Figure()
                    fig_rec.add_trace(go.Bar(name='PDP', x=pdp['Recette'], y=pdp['Cadence (T/h)'],
                                             marker_color='#AFCA0A',
                                             text=pdp['Cadence (T/h)'].apply(lambda v: f"{v:.2f}"),
                                             textposition='outside'))
                    fig_rec.add_trace(go.Bar(name='Championne', x=chmp['Recette'], y=chmp['Cadence (T/h)'],
                                             marker_color='#FFEC00',
                                             text=chmp['Cadence (T/h)'].apply(lambda v: f"{v:.2f}"),
                                             textposition='outside'))
                    fig_rec.update_layout(barmode='group', title="Cadences PDP vs Championne par recette (T/h)",
                                          plot_bgcolor='white', paper_bgcolor='white',
                                          height=340, margin=dict(t=60,b=50),
                                          legend=dict(orientation='h', yanchor='bottom', y=1.02))
                    st.plotly_chart(fig_rec, use_container_width=True)

    # ── FOOTER ────────────────────────────────────────────────────
show_footer()
