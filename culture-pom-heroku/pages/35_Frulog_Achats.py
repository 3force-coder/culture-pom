import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, date, timedelta
from database import get_connection
from components import show_footer
from auth import require_access
import plotly.graph_objects as go
import io

st.set_page_config(page_title="Frulog Achats - POMI", page_icon="🛒", layout="wide")
st.markdown("""<style>
    .block-container {padding-top:2rem!important;padding-bottom:0.5rem!important;
        padding-left:2rem!important;padding-right:2rem!important;}
    h1,h2,h3,h4{margin-top:0.3rem!important;margin-bottom:0.3rem!important;}
    [data-testid="stMetricValue"]{font-size:1.4rem!important;}
    hr{margin-top:0.5rem!important;margin-bottom:0.5rem!important;}
</style>""", unsafe_allow_html=True)

require_access("COMMERCIAL")
st.title("🛒 Frulog — Achats")

# ============================================================================
# FILTRES GLOBAUX
# ============================================================================

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
        camp_labels_map = {0: "🔓 Toutes", **{y: f"Camp. {y} ({y-1}/06→{y}/05)" for y in campagnes}}
        sel_camp = st.selectbox("🗓️ Campagne", camp_opts, format_func=lambda y: camp_labels_map[y], key="f_camp")
    with fc2:
        d_min_camp = campagne_dates(sel_camp)[0] if sel_camp else date(2022, 1, 1)
        d_max_camp = campagne_dates(sel_camp)[1] if sel_camp else date(2027, 12, 31)
        date_deb = st.date_input("📅 Du", value=d_min_camp, min_value=d_min_camp, max_value=d_max_camp, key="f_deb")
    with fc3:
        date_fin = st.date_input("📅 Au", value=d_max_camp, min_value=d_min_camp, max_value=d_max_camp, key="f_fin")
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
    with cm4: yb = st.number_input("Année B", 2022, 2027, datetime.now().year - 1, key="comp_yb")
    import calendar
    d1a = date(int(ya), int(ma), 1); d1b = date(int(ya), int(ma), calendar.monthrange(int(ya), int(ma))[1])
    d2a = date(int(yb), int(mb), 1); d2b = date(int(yb), int(mb), calendar.monthrange(int(yb), int(mb))[1])
    COMP_DATES = (f"{mois_names[ma]} {ya}", d1a, d1b, f"{mois_names[mb]} {yb}", d2a, d2b)
elif mode_compare == "📆 Semaine vs Semaine":
    cs1, cs2, cs3, cs4 = st.columns(4)
    with cs1: sa = st.number_input("Semaine A", 1, 53, max(1, datetime.now().isocalendar()[1]-1), key="comp_sa")
    with cs2: ysa = st.number_input("Année A", 2022, 2027, datetime.now().year, key="comp_ysa")
    with cs3: sb = st.number_input("Semaine B", 1, 53, max(1, datetime.now().isocalendar()[1]-1), key="comp_sb")
    with cs4: ysb = st.number_input("Année B", 2022, 2027, datetime.now().year - 1, key="comp_ysb")
    d1a = date.fromisocalendar(int(ysa), int(sa), 1); d1b = d1a + timedelta(days=6)
    d2a = date.fromisocalendar(int(ysb), int(sb), 1); d2b = d2a + timedelta(days=6)
    COMP_DATES = (f"S{sa}/{ysa}", d1a, d1b, f"S{sb}/{ysb}", d2a, d2b)

st.markdown("---")
DATE_DEB = date_deb
DATE_FIN = date_fin

# ============================================================================
# HELPERS
# ============================================================================

def cw_achat(d1=None, d2=None):
    dd = d1 or DATE_DEB; df = d2 or DATE_FIN
    return f" AND dt_chargmt >= '{dd}' AND dt_chargmt <= '{df}'"

def sply_dates():
    try:
        today = date.today()
        actual_end = min(DATE_FIN, today)
        delta_days = (actual_end - DATE_DEB).days
        try: prev_start = DATE_DEB.replace(year=DATE_DEB.year - 1)
        except ValueError: prev_start = DATE_DEB.replace(year=DATE_DEB.year - 1, day=28)
        prev_end = prev_start + timedelta(days=delta_days)
        return prev_start, prev_end, DATE_DEB, actual_end
    except: return None, None, None, None

def fmt_t(v):
    v = float(v)
    if abs(v) >= 1000: return f"{v/1000:,.1f}kT".replace(',', ' ')
    return f"{v:,.0f}T".replace(',', ' ')

def fmt_k(v):
    v = float(v)
    if abs(v) >= 1000: return f"{v/1000:,.1f}M€".replace(',', ' ')
    return f"{v:,.0f}k€".replace(',', ' ')

def pct_evol(v_new, v_old):
    if not v_old or float(v_old) == 0: return None
    return (float(v_new) - float(v_old)) / abs(float(v_old)) * 100

# ============================================================================
# FONCTIONS BDD
# ============================================================================

def get_analyse_achat(d1=None, d2=None):
    try:
        conn = get_connection(); cur = conn.cursor()
        w = cw_achat(d1, d2); r = {}
        cur.execute(f"""SELECT COUNT(*) as total,COUNT(DISTINCT apporteur) as nb_fournisseurs,
            COALESCE(SUM(pds_net),0) as pds_kg,COALESCE(SUM(montant_euro),0) as ca,
            COALESCE(AVG(prix_achat) FILTER (WHERE prix_achat>0),0) as prix_moy,
            COUNT(DISTINCT variete) as nb_varietes,MIN(dt_chargmt) as date_min,MAX(dt_chargmt) as date_max
            FROM frulog_lignes_achat WHERE 1=1{w}""")
        r['kpis'] = cur.fetchone()
        for k2, sql in {
            'par_fournisseur': f"SELECT apporteur,COUNT(*) as nb,SUM(COALESCE(pds_net,0)) as pds_kg,SUM(COALESCE(montant_euro,0)) as ca,AVG(prix_achat) FILTER (WHERE prix_achat>0) as prix_moy,COUNT(DISTINCT variete) as nb_varietes FROM frulog_lignes_achat WHERE 1=1{w} GROUP BY apporteur ORDER BY pds_kg DESC",
            'par_variete':     f"SELECT variete,COUNT(*) as nb,SUM(COALESCE(pds_net,0)) as pds_kg,SUM(COALESCE(montant_euro,0)) as ca,COUNT(DISTINCT apporteur) as nb_fournisseurs,AVG(prix_achat) FILTER (WHERE prix_achat>0) as prix_moy FROM frulog_lignes_achat WHERE variete IS NOT NULL{w} GROUP BY variete ORDER BY pds_kg DESC",
            'par_mois':        f"SELECT EXTRACT(YEAR FROM dt_chargmt)::int as annee,EXTRACT(MONTH FROM dt_chargmt)::int as mois,SUM(COALESCE(pds_net,0)) as pds_kg,SUM(COALESCE(montant_euro,0)) as ca FROM frulog_lignes_achat WHERE dt_chargmt IS NOT NULL{w} GROUP BY 1,2 ORDER BY annee,mois",
            'par_depot':       f"SELECT depot,COUNT(*) as nb,SUM(COALESCE(pds_net,0)) as pds_kg,SUM(COALESCE(montant_euro,0)) as ca FROM frulog_lignes_achat WHERE depot IS NOT NULL{w} GROUP BY depot ORDER BY pds_kg DESC",
        }.items():
            cur.execute(sql); r[k2] = cur.fetchall()
        cur.close(); conn.close(); return r
    except Exception as e: st.error(str(e)); return None

# ============================================================================
# HELPERS GRAPHIQUES
# ============================================================================

def render_kpis_sply(k, k_prev, label_prev):
    cols = st.columns(5)
    def show_metric(col, icon, name, val, val_prev, fmt_func=None):
        with col:
            v_str = fmt_func(val) if fmt_func else f"{int(val):,}".replace(',', ' ')
            delta = None
            if val_prev is not None and float(val_prev) > 0:
                p = pct_evol(val, val_prev)
                if p is not None: delta = f"{p:+.1f}% vs {label_prev}"
            st.metric(f"{icon} {name}", v_str, delta=delta)

    pds = float(k['pds_kg'])/1000; pds_p = float(k_prev['pds_kg'])/1000 if k_prev else None
    ca  = float(k['ca'])/1000;   ca_p  = float(k_prev['ca'])/1000  if k_prev else None
    show_metric(cols[0], "📋", "Lignes",       k['total'],          k_prev['total']          if k_prev else None)
    show_metric(cols[1], "⚖️", "Tonnage",      pds,                 pds_p,                   fmt_t)
    show_metric(cols[2], "💰", "Montant",      ca,                  ca_p,                    fmt_k)
    show_metric(cols[3], "🏭", "Fournisseurs", k['nb_fournisseurs'],k_prev['nb_fournisseurs']if k_prev else None)
    show_metric(cols[4], "🥔", "Variétés",     k['nb_varietes'],    k_prev['nb_varietes']    if k_prev else None)
    if k.get('date_min') and k.get('date_max'):
        st.caption(f"📅 {k['date_min'].strftime('%d/%m/%Y')} → {k['date_max'].strftime('%d/%m/%Y')} — Prix moy : {float(k['prix_moy']):,.0f} €/T".replace(',', ' '))

def sply_bars_a(df_now, df_prev_list, x_col, y_col, title, color_now='#E65100', color_prev='#42A5F5', top_n=20, fmt_fn=None):
    df_n = df_now.head(top_n).copy()
    fig = go.Figure()
    if df_prev_list and len(df_prev_list) > 0:
        dfp = pd.DataFrame(df_prev_list)
        if y_col in ('tonnes', 'tonnes_t') or y_col.endswith('_t'):
            dfp['val'] = dfp['pds_kg'].astype(float)/1000 if 'pds_kg' in dfp.columns else 0
        elif y_col in ('ca_k',) or y_col.endswith('_k'):
            dfp['val'] = dfp['ca'].astype(float)/1000 if 'ca' in dfp.columns else 0
        elif 'pds_kg' in dfp.columns:
            dfp['val'] = dfp['pds_kg'].astype(float)/1000
        else:
            dfp['val'] = 0
        pdict = dict(zip(dfp[x_col], dfp['val']))
        pv = [pdict.get(x, 0) for x in df_n[x_col]]
        fig.add_trace(go.Bar(x=df_n[x_col], y=pv, name="N-1", marker_color=color_prev,
            text=[fmt_fn(v) if fmt_fn and v else '' for v in pv], textposition='outside', textfont=dict(size=9, color='#1565C0')))
    texts = [fmt_fn(v) if fmt_fn else f"{float(v):,.0f}".replace(',', ' ') for v in df_n[y_col]]
    fig.add_trace(go.Bar(x=df_n[x_col], y=df_n[y_col], name="Période", marker_color=color_now,
        text=texts, textposition='outside', textfont=dict(size=10, color='#BF360C')))
    fig.update_layout(title=title, height=450, xaxis_tickangle=-45, barmode='group', legend=dict(orientation="h", yanchor="bottom", y=1.02))
    st.plotly_chart(fig, use_container_width=True)

def render_analyse_achat(data, data_prev, label_prev):
    if not data or not data.get('kpis') or data['kpis']['total'] == 0:
        st.info("📭 Aucune donnée Achat pour cette période"); return
    k  = data['kpis']
    kp = data_prev['kpis'] if data_prev and data_prev.get('kpis') and data_prev['kpis']['total'] > 0 else None
    render_kpis_sply(k, kp, label_prev)
    st.markdown("---")
    vue = st.radio("Analyser :", ["📊 Vue d'ensemble", "🏭 Fournisseurs", "🥔 Variétés", "🏢 Dépôts"], horizontal=True, key="vue_achat")
    st.markdown("---")

    prev_data = lambda key: data_prev.get(key) if data_prev else None

    if vue == "📊 Vue d'ensemble":
        mois_noms = {1:'Jan',2:'Fév',3:'Mar',4:'Avr',5:'Mai',6:'Jun',7:'Jul',8:'Aoû',9:'Sep',10:'Oct',11:'Nov',12:'Déc'}
        if data['par_mois']:
            df_m = pd.DataFrame(data['par_mois']); df_m['tonnes'] = df_m['pds_kg'].astype(float)/1000
            df_m = df_m.groupby('mois', as_index=False).agg({'tonnes':'sum'})
            df_m['mois_label'] = df_m['mois'].astype(int).map(mois_noms)
            fig = go.Figure()
            if data_prev and data_prev.get('par_mois'):
                dfmp = pd.DataFrame(data_prev['par_mois']); dfmp['tonnes'] = dfmp['pds_kg'].astype(float)/1000
                dfmp = dfmp.groupby('mois', as_index=False).agg({'tonnes':'sum'})
                dfmp['mois_label'] = dfmp['mois'].astype(int).map(mois_noms)
                fig.add_trace(go.Scatter(x=dfmp['mois_label'], y=dfmp['tonnes'], mode='lines+markers+text', name='N-1',
                    line=dict(color='#42A5F5', width=2, dash='dot'), marker=dict(color='#42A5F5', size=8),
                    text=[fmt_t(v) for v in dfmp['tonnes']], textposition='top center', textfont=dict(size=9, color='#1565C0')))
            fig.add_trace(go.Scatter(x=df_m['mois_label'], y=df_m['tonnes'], mode='lines+markers+text', name='Période',
                line=dict(color='#E65100', width=3), marker=dict(color='#E65100', size=10), fill='tozeroy', fillcolor='rgba(230,81,0,0.1)',
                text=[fmt_t(v) for v in df_m['tonnes']], textposition='bottom center', textfont=dict(size=10, color='#E65100')))
            ordre_mois = ['Jun','Jul','Aoû','Sep','Oct','Nov','Déc','Jan','Fév','Mar','Avr','Mai']
            fig.update_layout(title="Tonnage mensuel — N vs N-1", height=420,
                xaxis=dict(categoryorder='array', categoryarray=ordre_mois),
                legend=dict(orientation="h", yanchor="bottom", y=1.02))
            st.plotly_chart(fig, use_container_width=True)

    elif vue == "🏭 Fournisseurs" and data.get('par_fournisseur'):
        df = pd.DataFrame(data['par_fournisseur']); df['tonnes'] = df['pds_kg'].astype(float)/1000; df['ca_k'] = df['ca'].astype(float)/1000
        st.markdown(f"##### {len(df)} fournisseurs")
        sply_bars_a(df, prev_data('par_fournisseur'), 'apporteur', 'tonnes', "Top 20 Fournisseurs (T)", fmt_fn=fmt_t)
        st.dataframe(df[['apporteur','tonnes','ca_k','prix_moy','nb_varietes','nb']].head(50).rename(columns={
            'apporteur':'Fournisseur','tonnes':'Tonnes','ca_k':'Montant (k€)','prix_moy':'Prix moy','nb_varietes':'Variétés','nb':'Lignes'}),
            use_container_width=True, hide_index=True, column_config={'Prix moy':st.column_config.NumberColumn(format="%.0f")})
        buf = io.BytesIO(); df.to_excel(buf, index=False, engine='openpyxl')
        st.download_button("📥 Export", buf.getvalue(), "fournisseurs.xlsx", use_container_width=True)

    elif vue == "🥔 Variétés" and data.get('par_variete'):
        df = pd.DataFrame(data['par_variete']); df['tonnes'] = df['pds_kg'].astype(float)/1000
        st.markdown(f"##### {len(df)} variétés")
        sply_bars_a(df, prev_data('par_variete'), 'variete', 'tonnes', "Top 15 Variétés (T)", top_n=15, fmt_fn=fmt_t)
        st.dataframe(df[['variete','tonnes','nb_fournisseurs','prix_moy','nb']].head(30).rename(columns={
            'variete':'Variété','tonnes':'Tonnes','nb_fournisseurs':'Fourn.','prix_moy':'Prix moy','nb':'Lignes'}),
            use_container_width=True, hide_index=True, column_config={'Prix moy':st.column_config.NumberColumn(format="%.0f")})

    elif vue == "🏢 Dépôts" and data.get('par_depot'):
        df = pd.DataFrame(data['par_depot']); df['tonnes'] = df['pds_kg'].astype(float)/1000; df['ca_k'] = df['ca'].astype(float)/1000
        sply_bars_a(df, prev_data('par_depot'), 'depot', 'tonnes', "Top 20 Dépôts (T)", fmt_fn=fmt_t)
        st.dataframe(df[['depot','tonnes','ca_k','nb']].head(30).rename(columns={'depot':'Dépôt','tonnes':'Tonnes','ca_k':'Montant (k€)','nb':'Lignes'}),
            use_container_width=True, hide_index=True)

# ============================================================================
# RENDU
# ============================================================================

if COMP_DATES:
    la, d1a, d1b, lb, d2a, d2b = COMP_DATES
    st.info(f"🔀 Comparaison : **{la}** vs **{lb}**")
    da = get_analyse_achat(d1a, d1b)
    db = get_analyse_achat(d2a, d2b)
    render_analyse_achat(da, db, lb)
else:
    sp1, sp2, now1, now2 = sply_dates()
    dn = get_analyse_achat(now1, now2) if now1 else get_analyse_achat()
    dp = get_analyse_achat(sp1, sp2) if sp1 else None
    lp = f"{sp1.strftime('%d/%m/%Y')}→{sp2.strftime('%d/%m/%Y')}" if sp1 else "N-1"
    render_analyse_achat(dn, dp, lp)

show_footer()
