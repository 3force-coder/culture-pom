import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import date, datetime
import io
import re
import openpyxl

from auth import require_access, is_admin
from components import show_footer
from database import get_connection

# ============================================================
# CONFIGURATION PAGE
# ============================================================
st.set_page_config(
    page_title="Stats Maintenance — POMI",
    page_icon="🔧",
    layout="wide"
)

st.markdown("""<style>
    .block-container {padding-top:2rem!important;padding-bottom:0.5rem!important;
        padding-left:2rem!important;padding-right:2rem!important;}
    h1,h2,h3,h4{margin-top:0.3rem!important;margin-bottom:0.3rem!important;}
    [data-testid="stMetricValue"]{font-size:1.4rem!important;}
    hr{margin-top:0.5rem!important;margin-bottom:0.5rem!important;}
</style>""", unsafe_allow_html=True)

require_access("COMMERCIAL")
st.title("🔧 Maintenance — Statistiques & Interventions")

# ============================================================
# NORMALISATION TYPE DE PANNE
# ============================================================
TYPE_PANNE_NORM = {
    'correctif':                  'Correctif',
    'correctif suite préventif':  'Correctif suite préventif',
    'casse operateur':            'Casse opérateur',
    'réglage operateur':          'Réglage opérateur',
    'reglage operateur':          'Réglage opérateur',
    'suite vr':                   'Suite VR',
    'autre':                      'Autre',
}

def normaliser_type(val):
    if not val:
        return 'Autre'
    return TYPE_PANNE_NORM.get(str(val).strip().lower(), str(val).strip())

# ============================================================
# LECTURE EXCEL (openpyxl read_only)
# ============================================================
COL_MAP = {
    "Date d'intervention":              'date_intervention',
    'INTERVENANTS':                     'intervenants',
    'Machine':                          'machine',
    'Type de panne':                    'type_panne',
    'Analyse de panne (Défaillance)':   'analyse_panne',
    "Heure début d'intervention":       'heure_debut',
    "Heure fin d'intervention":         'heure_fin',
    "Temps d'arrêt production (en minutes)": 'temps_arret_min',
    'Operations réalisées':             'operations',
    'Remarques':                        'remarques',
    'Pièces utilisées / En commande':   'pieces_utilisees',
    "Etat de l'intervention":           'etat',
}

def lire_excel(file_bytes: bytes) -> pd.DataFrame:
    """Lit l'onglet Sheet1 du fichier Excel en mode read_only."""
    wb = openpyxl.load_workbook(io.BytesIO(file_bytes), read_only=True, data_only=True)
    ws = wb['Sheet1']
    rows_iter = ws.iter_rows(values_only=True)
    try:
        raw_headers = [str(h).strip() if h else '' for h in next(rows_iter)]
    except StopIteration:
        wb.close()
        return pd.DataFrame()

    col_idx = {raw_headers.index(src): dst
               for src, dst in COL_MAP.items() if src in raw_headers}

    records = []
    for row in rows_iter:
        if all(v is None for v in row):
            continue
        rec = {dst: (row[idx] if idx < len(row) else None)
               for idx, dst in col_idx.items()}
        records.append(rec)
    wb.close()

    df = pd.DataFrame(records)
    if df.empty:
        return df

    df['date_intervention'] = pd.to_datetime(df['date_intervention'], errors='coerce').dt.date
    df['temps_arret_min']   = pd.to_numeric(df['temps_arret_min'], errors='coerce').fillna(0).astype(int)
    df['type_panne']        = df['type_panne'].apply(normaliser_type)
    df['machine']           = df['machine'].fillna('').str.strip()
    df['intervenants']      = df['intervenants'].fillna('').str.strip()
    df['etat']              = df['etat'].fillna('').str.strip()

    # Colonnes analytiques
    df = df.dropna(subset=['date_intervention'])
    df['annee_semaine'] = df['date_intervention'].apply(
        lambda d: f"{d.isocalendar()[0]}-S{d.isocalendar()[1]:02d}"
    )
    df['mois'] = df['date_intervention'].apply(lambda d: d.strftime('%Y-%m'))
    return df


# ============================================================
# BDD : UPSERT
# ============================================================
def upsert_interventions(df: pd.DataFrame, username: str) -> tuple:
    """Upsert depuis DataFrame normalisé. Retourne (inserted, updated, errors)."""
    conn = get_connection()
    if not conn:
        return 0, 0, 1
    inserted = updated = errors = 0
    try:
        cur = conn.cursor()
        for _, r in df.iterrows():
            try:
                cur.execute("""
                    INSERT INTO maintenance_interventions
                        (date_intervention, intervenants, machine, type_panne,
                         analyse_panne, heure_debut, heure_fin, temps_arret_min,
                         operations, remarques, pieces_utilisees, etat,
                         imported_by, imported_at)
                    VALUES (%s,%s,%s,%s, %s,%s,%s,%s, %s,%s,%s,%s, %s, CURRENT_TIMESTAMP)
                    ON CONFLICT (date_intervention, machine, heure_debut, analyse_panne)
                    DO UPDATE SET
                        intervenants      = EXCLUDED.intervenants,
                        type_panne        = EXCLUDED.type_panne,
                        heure_fin         = EXCLUDED.heure_fin,
                        temps_arret_min   = EXCLUDED.temps_arret_min,
                        operations        = EXCLUDED.operations,
                        remarques         = EXCLUDED.remarques,
                        pieces_utilisees  = EXCLUDED.pieces_utilisees,
                        etat              = EXCLUDED.etat,
                        imported_by       = EXCLUDED.imported_by,
                        imported_at       = CURRENT_TIMESTAMP
                    RETURNING (xmax = 0) AS is_insert
                """, (
                    r['date_intervention'],
                    str(r.get('intervenants') or '')[:200],
                    str(r.get('machine') or '')[:200],
                    str(r.get('type_panne') or '')[:100],
                    str(r.get('analyse_panne') or '')[:500] if r.get('analyse_panne') else None,
                    str(r.get('heure_debut') or '')[:20] if r.get('heure_debut') else None,
                    str(r.get('heure_fin') or '')[:20] if r.get('heure_fin') else None,
                    int(r.get('temps_arret_min') or 0),
                    str(r.get('operations') or '')[:1000] if r.get('operations') else None,
                    str(r.get('remarques') or '')[:500] if r.get('remarques') else None,
                    str(r.get('pieces_utilisees') or '')[:500] if r.get('pieces_utilisees') else None,
                    str(r.get('etat') or '')[:100],
                    username,
                ))
                res = cur.fetchone()
                if res and res['is_insert']:
                    inserted += 1
                else:
                    updated += 1
            except Exception:
                errors += 1
                conn.rollback()
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        conn.rollback()
        conn.close()
        return inserted, updated, errors + 1
    return inserted, updated, errors


# ============================================================
# BDD : LECTURE
# ============================================================
@st.cache_data(ttl=180)
def load_interventions() -> pd.DataFrame:
    try:
        conn = get_connection()
        df = pd.read_sql("""
            SELECT id, date_intervention, intervenants, machine, type_panne,
                   analyse_panne, heure_debut, heure_fin, temps_arret_min,
                   operations, remarques, pieces_utilisees, etat, imported_at
            FROM maintenance_interventions
            ORDER BY date_intervention DESC, machine
        """, conn)
        conn.close()
        if not df.empty:
            df['date_intervention'] = pd.to_datetime(df['date_intervention'], errors='coerce').dt.date
            df['temps_arret_min']   = pd.to_numeric(df['temps_arret_min'], errors='coerce').fillna(0).astype(int)
            df['annee_semaine'] = df['date_intervention'].apply(
                lambda d: f"{d.isocalendar()[0]}-S{d.isocalendar()[1]:02d}" if d else None
            )
            df['mois'] = df['date_intervention'].apply(
                lambda d: d.strftime('%Y-%m') if d else None
            )
        return df
    except Exception:
        return pd.DataFrame()


# ============================================================
# FILTRES GLOBAUX
# ============================================================
df = load_interventions()

col_f1, col_f2, col_f3 = st.columns([2, 1, 1])
with col_f1:
    machines_dispo = ['Toutes les machines'] + sorted(df['machine'].dropna().unique().tolist()) if not df.empty else ['Toutes les machines']
    filtre_machine = st.selectbox("🔩 Machine", machines_dispo, key="maint_machine")
with col_f2:
    types_dispo = ['Tous types'] + sorted(df['type_panne'].dropna().unique().tolist()) if not df.empty else ['Tous types']
    filtre_type = st.selectbox("🏷️ Type de panne", types_dispo, key="maint_type")
with col_f3:
    interv_dispo = ['Tous'] + sorted(set(
        i.strip() for cell in df['intervenants'].dropna() for i in cell.split(';')
    )) if not df.empty else ['Tous']
    filtre_interv = st.selectbox("👷 Intervenant", interv_dispo, key="maint_interv")

def appliquer_filtres(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    if filtre_machine != 'Toutes les machines':
        df = df[df['machine'] == filtre_machine]
    if filtre_type != 'Tous types':
        df = df[df['type_panne'] == filtre_type]
    if filtre_interv != 'Tous':
        df = df[df['intervenants'].str.contains(filtre_interv, na=False)]
    return df

st.markdown("---")

# ============================================================
# ONGLETS
# ============================================================
tab_import, tab_vue, tab_machines, tab_detail = st.tabs([
    "📥 Import",
    "📊 Vue globale",
    "🔩 Par machine",
    "📋 Détail interventions",
])


# ────────────────────────────────────────────────────────────
# ONGLET IMPORT
# ────────────────────────────────────────────────────────────
with tab_import:
    st.subheader("📥 Import fichier Excel interventions")
    st.caption("Fichier **Saisie_interventions_site_de_Saint_Flavy.xlsx** — onglet Sheet1")

    file_up = st.file_uploader(
        "Sélectionner le fichier Excel",
        type=['xlsx'], key="maint_import_file"
    )

    if file_up:
        file_id = f"{file_up.name}_{file_up.size}"
        if st.session_state.get('maint_file_id') != file_id:
            with st.spinner("Lecture du fichier en cours…"):
                try:
                    file_bytes = file_up.read()
                    df_cache = lire_excel(file_bytes)
                    st.session_state['maint_df_cache'] = df_cache
                    st.session_state['maint_file_id']  = file_id
                except Exception as e:
                    st.error(f"Erreur lecture : {e}")
                    st.stop()

        df_prev = st.session_state.get('maint_df_cache', pd.DataFrame())

        if not df_prev.empty:
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("📋 Interventions", len(df_prev))
            c2.metric("🔩 Machines", df_prev['machine'].nunique())
            c3.metric("⏱️ Arrêt total", f"{df_prev['temps_arret_min'].sum():.0f} min")
            c4.metric("📅 Période",
                      f"{df_prev['date_intervention'].min()} → {df_prev['date_intervention'].max()}")

            with st.expander("🔍 Aperçu (10 premières lignes)"):
                st.dataframe(
                    df_prev[['date_intervention','machine','type_panne','intervenants',
                              'temps_arret_min','etat']].head(10),
                    use_container_width=True, hide_index=True
                )

            st.info(
                "**Mode upsert** — clé unique : date + machine + heure début + analyse panne. "
                "Les lignes existantes sont mises à jour, les nouvelles ajoutées. "
                "Aucun historique supprimé."
            )

            if st.button("⬆️ Importer en base de données", type="primary", key="maint_do_import"):
                user = st.session_state.get('username', 'inconnu')
                with st.spinner("Import en cours…"):
                    ins, upd, err = upsert_interventions(df_prev, user)
                if err == 0:
                    st.success(f"✅ {ins} ajoutées, {upd} mises à jour, 0 erreur")
                    st.cache_data.clear()
                    st.session_state.pop('maint_file_id', None)
                    st.rerun()
                else:
                    st.warning(f"⚠️ {ins} ajoutées, {upd} mises à jour, {err} erreurs")
    else:
        st.info("Glissez-déposez le fichier Excel pour commencer.")

    st.markdown("---")
    st.subheader("📊 Données actuellement en base")
    df_info = load_interventions()
    if not df_info.empty:
        c1, c2, c3 = st.columns(3)
        c1.metric("📋 Interventions", len(df_info))
        c2.metric("🔩 Machines distinctes", df_info['machine'].nunique())
        c3.metric("⏱️ Arrêt total", f"{df_info['temps_arret_min'].sum():.0f} min")
    else:
        st.info("Base vide — aucune intervention importée.")


# ────────────────────────────────────────────────────────────
# ONGLET VUE GLOBALE
# ────────────────────────────────────────────────────────────
with tab_vue:
    if df.empty:
        st.info("📤 Aucune donnée en base. Utilisez l'onglet 📥 **Import** pour charger les interventions.")
    else:
        df_f = appliquer_filtres(df.copy())

        # KPIs
        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("📋 Interventions",      len(df_f))
        c2.metric("🔩 Machines touchées",  df_f['machine'].nunique())
        c3.metric("⏱️ Arrêt total",        f"{df_f['temps_arret_min'].sum():.0f} min")
        c4.metric("⏱️ Arrêt moyen/inter.", f"{df_f['temps_arret_min'].mean():.0f} min")
        nb_correctif = len(df_f[df_f['type_panne'] == 'Correctif'])
        c5.metric("🔴 Correctifs",         f"{nb_correctif} ({100*nb_correctif/max(len(df_f),1):.0f}%%)")

        st.markdown("---")
        col_g1, col_g2 = st.columns(2)

        # Évolution mensuelle
        with col_g1:
            grp_mois = (df_f.groupby('mois')
                        .agg(nb_inter=('id','count'), arret_total=('temps_arret_min','sum'))
                        .reset_index().sort_values('mois'))
            fig = go.Figure()
            fig.add_trace(go.Bar(
                x=grp_mois['mois'], y=grp_mois['nb_inter'],
                name='Nb interventions', marker_color='#AFCA0A',
                text=grp_mois['nb_inter'], textposition='outside',
            ))
            fig.add_trace(go.Scatter(
                x=grp_mois['mois'], y=grp_mois['arret_total'],
                name='Arrêt (min)', line=dict(color='#e53935', width=2),
                mode='lines+markers', yaxis='y2',
            ))
            fig.update_layout(
                title='Évolution mensuelle — Interventions & Arrêts',
                plot_bgcolor='white', paper_bgcolor='white', height=350,
                xaxis_tickangle=-45,
                yaxis=dict(title='Nb interventions'),
                yaxis2=dict(title='Arrêt (min)', overlaying='y', side='right'),
                legend=dict(orientation='h', y=1.1),
            )
            st.plotly_chart(fig, use_container_width=True, key="vue_evol_mensuelle")

        # Répartition par type de panne
        with col_g2:
            grp_type = df_f.groupby('type_panne').size().reset_index(name='nb')
            fig2 = px.pie(
                grp_type, names='type_panne', values='nb',
                title='Répartition par type de panne',
                color_discrete_sequence=px.colors.qualitative.Set2,
                hole=0.35,
            )
            fig2.update_traces(textinfo='percent+label+value')
            fig2.update_layout(height=350, margin=dict(t=40,b=20))
            st.plotly_chart(fig2, use_container_width=True, key="vue_type_panne")

        st.markdown("---")
        col_g3, col_g4 = st.columns(2)

        # Top machines par nb interventions
        with col_g3:
            grp_mach = (df_f.groupby('machine')
                        .agg(nb=('id','count'), arret=('temps_arret_min','sum'))
                        .reset_index().sort_values('arret', ascending=True).tail(15))
            fig3 = px.bar(
                grp_mach, x='arret', y='machine', orientation='h',
                title='Top 15 machines — Arrêt cumulé (min)',
                labels={'arret':'Arrêt (min)', 'machine':'Machine'},
                color_discrete_sequence=['#AFCA0A'], text='arret',
            )
            fig3.update_traces(textposition='outside')
            fig3.update_layout(plot_bgcolor='white', paper_bgcolor='white',
                               height=max(300, len(grp_mach)*35+60),
                               margin=dict(t=40,b=20,l=160))
            st.plotly_chart(fig3, use_container_width=True, key="vue_top_machines")

        # Répartition par intervenant
        with col_g4:
            # Éclater les multi-intervenants
            rows_interv = []
            for _, r in df_f.iterrows():
                for i in str(r['intervenants']).split(';'):
                    i = i.strip()
                    if i:
                        rows_interv.append({'intervenant': i, 'arret': r['temps_arret_min']})
            if rows_interv:
                df_interv = pd.DataFrame(rows_interv)
                grp_interv = (df_interv.groupby('intervenant')
                              .agg(nb=('arret','count'), arret=('arret','sum'))
                              .reset_index().sort_values('nb', ascending=True))
                fig4 = px.bar(
                    grp_interv, x='nb', y='intervenant', orientation='h',
                    title='Interventions par technicien',
                    labels={'nb':'Nb interventions', 'intervenant':'Technicien'},
                    color_discrete_sequence=['#7A7A7A'], text='nb',
                )
                fig4.update_traces(textposition='outside')
                fig4.update_layout(plot_bgcolor='white', paper_bgcolor='white',
                                   height=max(300, len(grp_interv)*35+60),
                                   margin=dict(t=40,b=20,l=120))
                st.plotly_chart(fig4, use_container_width=True, key="vue_intervenants")


# ────────────────────────────────────────────────────────────
# ONGLET PAR MACHINE
# ────────────────────────────────────────────────────────────
with tab_machines:
    if df.empty:
        st.info("📤 Aucune donnée en base. Utilisez l'onglet 📥 **Import** pour charger les interventions.")
    else:
        df_f = appliquer_filtres(df.copy())

        # Tableau récap par machine
        grp = (df_f.groupby('machine')
               .agg(
                   nb_inter=('id','count'),
                   arret_total=('temps_arret_min','sum'),
                   arret_moy=('temps_arret_min','mean'),
                   derniere=('date_intervention','max'),
               )
               .reset_index()
               .sort_values('arret_total', ascending=False))
        grp['arret_moy'] = grp['arret_moy'].round(0).astype(int)

        st.subheader("📊 Récapitulatif par machine")
        st.dataframe(
            grp.rename(columns={
                'machine':      'Machine',
                'nb_inter':     'Nb interventions',
                'arret_total':  'Arrêt total (min)',
                'arret_moy':    'Arrêt moyen (min)',
                'derniere':     'Dernière intervention',
            }),
            use_container_width=True, hide_index=True,
            column_config={
                'Arrêt total (min)':  st.column_config.NumberColumn(format="%d min"),
                'Arrêt moyen (min)':  st.column_config.NumberColumn(format="%d min"),
            }
        )

        st.markdown("---")
        # Détail pour une machine sélectionnée
        machines_list = sorted(df_f['machine'].dropna().unique().tolist())
        if machines_list:
            machine_sel = st.selectbox("🔍 Détail pour la machine", machines_list, key="mach_detail_sel")
            df_mach = df_f[df_f['machine'] == machine_sel].sort_values('date_intervention', ascending=False)

            col_m1, col_m2, col_m3 = st.columns(3)
            col_m1.metric("Interventions",    len(df_mach))
            col_m2.metric("Arrêt total",      f"{df_mach['temps_arret_min'].sum()} min")
            col_m3.metric("Dernière inter.",  str(df_mach['date_intervention'].max()))

            # Évolution mensuelle machine
            grp_m = (df_mach.groupby('mois')
                     .agg(nb=('id','count'), arret=('temps_arret_min','sum'))
                     .reset_index().sort_values('mois'))
            if len(grp_m) > 1:
                fig_m = px.bar(
                    grp_m, x='mois', y='nb',
                    title=f'Interventions mensuelles — {machine_sel}',
                    color_discrete_sequence=['#AFCA0A'], text='nb',
                )
                fig_m.update_traces(textposition='outside')
                fig_m.update_layout(plot_bgcolor='white', paper_bgcolor='white',
                                    height=280, xaxis_tickangle=-45)
                st.plotly_chart(fig_m, use_container_width=True, key="mach_evol_mensuelle")

            # Tableau des interventions
            st.dataframe(
                df_mach[['date_intervention','type_panne','intervenants',
                          'analyse_panne','temps_arret_min','operations','etat']]
                .rename(columns={
                    'date_intervention': 'Date',
                    'type_panne':        'Type',
                    'intervenants':      'Technicien(s)',
                    'analyse_panne':     'Analyse / Défaillance',
                    'temps_arret_min':   'Arrêt (min)',
                    'operations':        'Opérations réalisées',
                    'etat':              'État',
                }),
                use_container_width=True, hide_index=True,
                column_config={'Arrêt (min)': st.column_config.NumberColumn(format="%d min")}
            )


# ────────────────────────────────────────────────────────────
# ONGLET DÉTAIL INTERVENTIONS
# ────────────────────────────────────────────────────────────
with tab_detail:
    if df.empty:
        st.info("📤 Aucune donnée en base. Utilisez l'onglet 📥 **Import** pour charger les interventions.")
    else:
        df_f = appliquer_filtres(df.copy())

        col_d1, col_d2 = st.columns(2)
        with col_d1:
            dates_dispo = sorted(df_f['date_intervention'].dropna().unique(), reverse=True)
            date_min = dates_dispo[-1] if dates_dispo else date.today()
            date_max = dates_dispo[0]  if dates_dispo else date.today()
            date_deb = st.date_input("Depuis le", value=date_min, key="det_deb")
        with col_d2:
            date_fin = st.date_input("Jusqu'au",  value=date_max, key="det_fin")

        df_det = df_f[
            (df_f['date_intervention'] >= date_deb) &
            (df_f['date_intervention'] <= date_fin)
        ].sort_values('date_intervention', ascending=False)

        st.markdown(f"**{len(df_det)} interventions** sur la période")

        st.dataframe(
            df_det[['date_intervention','machine','type_panne','intervenants',
                     'analyse_panne','temps_arret_min','operations',
                     'pieces_utilisees','etat']]
            .rename(columns={
                'date_intervention': 'Date',
                'machine':           'Machine',
                'type_panne':        'Type',
                'intervenants':      'Technicien(s)',
                'analyse_panne':     'Analyse / Défaillance',
                'temps_arret_min':   'Arrêt (min)',
                'operations':        'Opérations réalisées',
                'pieces_utilisees':  'Pièces',
                'etat':              'État',
            }),
            use_container_width=True, hide_index=True,
            height=500,
            column_config={'Arrêt (min)': st.column_config.NumberColumn(format="%d min")}
        )

        # Export CSV
        csv = df_det.to_csv(index=False, sep=';', encoding='utf-8-sig')
        st.download_button(
            "⬇️ Exporter CSV",
            data=csv,
            file_name=f"maintenance_{date_deb}_{date_fin}.csv",
            mime='text/csv',
            key="det_export_csv"
        )

# ============================================================
# FOOTER
# ============================================================
show_footer()
