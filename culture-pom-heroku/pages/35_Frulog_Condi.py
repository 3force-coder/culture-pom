import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, date, timedelta
from database import get_connection
from components import show_footer
from auth import require_access
import plotly.express as px
import plotly.graph_objects as go
import io

st.set_page_config(page_title="Frulog Condi - POMI", page_icon="📈", layout="wide")
st.markdown("""<style>
    .block-container {padding-top:2rem!important;padding-bottom:0.5rem!important;
        padding-left:2rem!important;padding-right:2rem!important;}
    h1,h2,h3,h4{margin-top:0.3rem!important;margin-bottom:0.3rem!important;}
    [data-testid="stMetricValue"]{font-size:1.4rem!important;}
    hr{margin-top:0.5rem!important;margin-bottom:0.5rem!important;}
</style>""", unsafe_allow_html=True)

require_access("COMMERCIAL")
st.title("📈 Frulog — Conditionnement")

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

def cw_ventes(d1=None, d2=None):
    dd = d1 or DATE_DEB; df = d2 or DATE_FIN
    return f" AND date_charg >= '{dd}' AND date_charg <= '{df}'"

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

def get_analyse_ventes(table, d1=None, d2=None):
    try:
        conn = get_connection(); cur = conn.cursor()
        w = cw_ventes(d1, d2); r = {}
        cur.execute(f"""SELECT COUNT(*) as total, COUNT(*) FILTER (WHERE type IN ('E','C')) as nb_exp,
            COUNT(DISTINCT client) FILTER (WHERE type IN ('E','C')) as nb_clients,
            COALESCE(SUM(pds_net) FILTER (WHERE type IN ('E','C')),0) as pds_kg,
            COALESCE(SUM(montant) FILTER (WHERE type IN ('E','C')),0) as ca,
            COALESCE(AVG(prix) FILTER (WHERE type IN ('E','C') AND prix>0),0) as prix_moy,
            COUNT(DISTINCT variete) FILTER (WHERE type IN ('E','C')) as nb_varietes,
            MIN(date_charg) FILTER (WHERE type IN ('E','C')) as date_min,
            MAX(date_charg) FILTER (WHERE type IN ('E','C')) as date_max,
            COUNT(*) FILTER (WHERE code_produit_commercial IS NOT NULL AND type IN ('E','C')) as mappees,
            COUNT(*) FILTER (WHERE code_produit_commercial IS NULL AND type IN ('E','C')) as non_mappees
            FROM {table} WHERE 1=1 {w}""")
        r['kpis'] = cur.fetchone()
        queries = {
            'par_client':   f"SELECT client,COUNT(*) as nb,SUM(COALESCE(pds_net,0)) as pds_kg,SUM(COALESCE(montant,0)) as ca,AVG(prix) FILTER (WHERE prix>0) as prix_moy,MIN(date_charg) as premiere,MAX(date_charg) as derniere FROM {table} WHERE type IN ('E','C'){w} GROUP BY client ORDER BY pds_kg DESC",
            'par_variete':  f"SELECT variete,COUNT(*) as nb,SUM(COALESCE(pds_net,0)) as pds_kg,SUM(COALESCE(montant,0)) as ca,COUNT(DISTINCT client) as nb_clients,AVG(prix) FILTER (WHERE prix>0) as prix_moy FROM {table} WHERE type IN ('E','C') AND variete IS NOT NULL{w} GROUP BY variete ORDER BY pds_kg DESC",
            'par_mois':     f"SELECT EXTRACT(YEAR FROM date_charg)::int as annee,EXTRACT(MONTH FROM date_charg)::int as mois,SUM(COALESCE(pds_net,0)) as pds_kg,SUM(COALESCE(montant,0)) as ca FROM {table} WHERE type IN ('E','C') AND date_charg IS NOT NULL{w} GROUP BY 1,2 ORDER BY annee,mois",
            'par_semaine':  f"SELECT annee,semaine,SUM(COALESCE(pds_net,0)) as pds_kg,SUM(COALESCE(montant,0)) as ca FROM {table} WHERE type IN ('E','C') AND annee IS NOT NULL{w} GROUP BY annee,semaine ORDER BY annee,semaine",
            'par_produit':  f"SELECT COALESCE(code_produit_commercial,'❓ Non mappé') as produit,COUNT(*) as nb,SUM(COALESCE(pds_net,0)) as pds_kg,SUM(COALESCE(montant,0)) as ca FROM {table} WHERE type IN ('E','C'){w} GROUP BY 1 ORDER BY pds_kg DESC",
            'par_emballage':f"SELECT emballage,COUNT(*) as nb,SUM(COALESCE(pds_net,0)) as pds_kg FROM {table} WHERE type IN ('E','C') AND emballage IS NOT NULL{w} GROUP BY emballage ORDER BY pds_kg DESC",
            'par_calibre':  f"SELECT calibre,COUNT(*) as nb,SUM(COALESCE(pds_net,0)) as pds_kg,COUNT(DISTINCT client) as nb_clients FROM {table} WHERE type IN ('E','C') AND calibre IS NOT NULL{w} GROUP BY calibre ORDER BY pds_kg DESC",
            'par_vendeur':  f"SELECT vendeur,SUM(COALESCE(pds_net,0)) as pds_kg,SUM(COALESCE(montant,0)) as ca,COUNT(DISTINCT client) as nb_clients FROM {table} WHERE type IN ('E','C') AND vendeur IS NOT NULL{w} GROUP BY vendeur ORDER BY ca DESC",
        }
        for k2, sql in queries.items():
            cur.execute(sql); r[k2] = cur.fetchall()
        try:
            prev_start_full = DATE_DEB.replace(year=DATE_DEB.year - 1)
            prev_end_full   = DATE_FIN.replace(year=DATE_FIN.year - 1)
            cur.execute(f"""SELECT annee,semaine,SUM(COALESCE(pds_net,0)) as pds_kg,SUM(COALESCE(montant,0)) as ca
                FROM {table} WHERE type IN ('E','C') AND annee IS NOT NULL
                AND date_charg >= %s AND date_charg <= %s
                GROUP BY annee,semaine ORDER BY annee,semaine""", (prev_start_full, prev_end_full))
            r['par_semaine_n1_full'] = cur.fetchall()
        except: r['par_semaine_n1_full'] = []
        cur.close(); conn.close(); return r
    except Exception as e: st.error(str(e)); return None

def get_comparaison_previsions():
    try:
        conn = get_connection(); cur = conn.cursor()
        w = cw_ventes()
        cur.execute(f"""WITH expedie AS (SELECT code_produit_commercial,annee,semaine,SUM(pds_net)/1000.0 as t FROM frulog_lignes_condi WHERE type IN ('E','C') AND code_produit_commercial IS NOT NULL{w} GROUP BY 1,2,3),
            prevu AS (SELECT code_produit_commercial,annee::int,semaine::int,quantite_prevue_tonnes as t FROM previsions_ventes)
            SELECT COALESCE(e.code_produit_commercial,p.code_produit_commercial) as produit,COALESCE(e.annee,p.annee) as annee,COALESCE(e.semaine,p.semaine) as semaine,COALESCE(p.t,0) as prevu_t,COALESCE(e.t,0) as expedie_t
            FROM expedie e FULL OUTER JOIN prevu p ON e.code_produit_commercial=p.code_produit_commercial AND e.annee=p.annee AND e.semaine=p.semaine
            WHERE COALESCE(e.annee,p.annee) IS NOT NULL ORDER BY 2,3""")
        rows = cur.fetchall(); cur.close(); conn.close()
        if rows:
            df = pd.DataFrame(rows)
            df['ecart_t'] = df['expedie_t'].astype(float) - df['prevu_t'].astype(float)
            df['taux'] = df.apply(lambda r: float(r['expedie_t'])/float(r['prevu_t'])*100 if float(r['prevu_t']) > 0 else None, axis=1)
            return df
        return pd.DataFrame()
    except: return pd.DataFrame()

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
    show_metric(cols[0], "🚚", "Expéditions", k['nb_exp'],     k_prev['nb_exp']     if k_prev else None)
    show_metric(cols[1], "⚖️", "Tonnage",     pds,            pds_p,               fmt_t)
    show_metric(cols[2], "💰", "CA",          ca,             ca_p,                fmt_k)
    show_metric(cols[3], "👥", "Clients",     k['nb_clients'], k_prev['nb_clients'] if k_prev else None)
    show_metric(cols[4], "🥔", "Variétés",    k['nb_varietes'],k_prev['nb_varietes']if k_prev else None)
    if k.get('date_min') and k.get('date_max'):
        st.caption(f"📅 {k['date_min'].strftime('%d/%m/%Y')} → {k['date_max'].strftime('%d/%m/%Y')} — Prix moy : {float(k['prix_moy']):,.0f} €/T".replace(',', ' '))

def sply_bars(df_now, df_prev, x_col, y_col, title, color_now='#1565C0', color_prev='#FF9800', top_n=20, fmt_fn=None):
    df_n = df_now.head(top_n).copy()
    fig = go.Figure()
    if df_prev is not None and len(df_prev) > 0:
        df_p = pd.DataFrame(df_prev)
        if y_col in ('tonnes', 'tonnes_t') or y_col.endswith('_t'):
            df_p['val'] = df_p['pds_kg'].astype(float)/1000
        elif y_col in ('ca_k',) or y_col.endswith('_k'):
            df_p['val'] = df_p['ca'].astype(float)/1000
        elif 'pds_kg' in df_p.columns:
            df_p['val'] = df_p['pds_kg'].astype(float)/1000
        else:
            df_p['val'] = 0
        df_p_dict = dict(zip(df_p[x_col], df_p['val']))
        prev_vals = [df_p_dict.get(x, 0) for x in df_n[x_col]]
        t_p = [fmt_fn(v) if fmt_fn and v else '' for v in prev_vals]
        fig.add_trace(go.Bar(x=df_n[x_col], y=prev_vals, name="N-1", marker_color=color_prev,
            text=t_p, textposition='outside', textfont=dict(size=9, color='#E65100')))
    texts = [fmt_fn(v) if fmt_fn else f"{float(v):,.0f}".replace(',', ' ') for v in df_n[y_col]]
    fig.add_trace(go.Bar(x=df_n[x_col], y=df_n[y_col], name="Période", marker_color=color_now,
        text=texts, textposition='outside', textfont=dict(size=10, color='#0D47A1')))
    fig.update_layout(title=title, height=450, xaxis_tickangle=-45, barmode='group', legend=dict(orientation="h", yanchor="bottom", y=1.02))
    st.plotly_chart(fig, use_container_width=True)

def render_analyse_ventes(data, data_prev, label_prev, label, show_produit=False):
    if not data or not data.get('kpis') or data['kpis']['total'] == 0:
        st.info(f"📭 Aucune donnée {label} pour cette période"); return
    k  = data['kpis']
    kp = data_prev['kpis'] if data_prev and data_prev.get('kpis') and data_prev['kpis']['total'] > 0 else None

    render_kpis_sply(k, kp, label_prev)
    if show_produit and k.get('mappees') is not None:
        tot = max(k['mappees'] + k['non_mappees'], 1)
        st.caption(f"🔗 Mapping : {k['mappees']*100/tot:.0f}% ({k['mappees']}/{tot})")
    st.markdown("---")

    vues = ["📊 Vue d'ensemble","👥 Clients","🥔 Variétés","📦 Emballages","📏 Calibres","👤 Vendeurs"]
    if show_produit: vues.insert(3, "🏷️ Produits")
    vue = st.radio("Analyser :", vues, horizontal=True, key=f"vue_{label}")
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
                df_mp = pd.DataFrame(data_prev['par_mois']); df_mp['tonnes'] = df_mp['pds_kg'].astype(float)/1000
                df_mp = df_mp.groupby('mois', as_index=False).agg({'tonnes':'sum'})
                df_mp['mois_label'] = df_mp['mois'].astype(int).map(mois_noms)
                fig.add_trace(go.Scatter(x=df_mp['mois_label'], y=df_mp['tonnes'], mode='lines+markers+text', name='N-1',
                    line=dict(color='#FF9800', width=2, dash='dot'), marker=dict(color='#FF9800', size=8),
                    text=[fmt_t(v) for v in df_mp['tonnes']], textposition='top center', textfont=dict(size=9, color='#E65100')))
            fig.add_trace(go.Scatter(x=df_m['mois_label'], y=df_m['tonnes'], mode='lines+markers+text', name='Période',
                line=dict(color='#1565C0', width=3), marker=dict(color='#1565C0', size=10), fill='tozeroy', fillcolor='rgba(21,101,192,0.1)',
                text=[fmt_t(v) for v in df_m['tonnes']], textposition='bottom center', textfont=dict(size=10, color='#1565C0')))
            ordre_mois = ['Jun','Jul','Aoû','Sep','Oct','Nov','Déc','Jan','Fév','Mar','Avr','Mai']
            fig.update_layout(title="Tonnage mensuel — N vs N-1", height=420,
                xaxis=dict(categoryorder='array', categoryarray=ordre_mois),
                legend=dict(orientation="h", yanchor="bottom", y=1.02))
            st.plotly_chart(fig, use_container_width=True)
        if data['par_semaine']:
            df_s = pd.DataFrame(data['par_semaine']); df_s['tonnes'] = df_s['pds_kg'].astype(float)/1000
            df_s = df_s.groupby('semaine', as_index=False).agg({'tonnes':'sum'})
            df_s['sem_label'] = df_s['semaine'].apply(lambda s: f"S{int(s):02d}")
            ordre_sem = [f"S{i:02d}" for i in list(range(23,53)) + list(range(1,23))]
            fig = go.Figure()
            sem_courante = date.today().isocalendar()[1]
            sem_courante_label = f"S{sem_courante:02d}"
            if data.get('par_semaine_n1_full'):
                df_sp = pd.DataFrame(data['par_semaine_n1_full']); df_sp['tonnes'] = df_sp['pds_kg'].astype(float)/1000
                df_sp = df_sp.groupby('semaine', as_index=False).agg({'tonnes':'sum'})
                df_sp['sem_label'] = df_sp['semaine'].apply(lambda s: f"S{int(s):02d}")
                fig.add_trace(go.Bar(x=df_sp['sem_label'], y=df_sp['tonnes'], name='N-1', marker_color='#FFB74D',
                    text=[fmt_t(v) for v in df_sp['tonnes']], textposition='outside', textfont=dict(size=7, color='#E65100')))
            fig.add_trace(go.Bar(x=df_s['sem_label'], y=df_s['tonnes'], name='Période', marker_color='#1565C0',
                text=[fmt_t(v) for v in df_s['tonnes']], textposition='outside', textfont=dict(size=7, color='#0D47A1')))
            if sem_courante_label in ordre_sem:
                idx_cur = ordre_sem.index(sem_courante_label)
                if idx_cur < len(ordre_sem) - 1:
                    fig.add_vrect(x0=ordre_sem[idx_cur], x1=ordre_sem[-1],
                        fillcolor="rgba(200,200,200,0.15)", line_width=0,
                        annotation_text="Projection N-1", annotation_position="top left",
                        annotation_font_size=9, annotation_font_color="#888")
            fig.update_layout(title="Tonnage hebdo — N vs N-1", height=420, barmode='group',
                xaxis=dict(tickangle=-45, categoryorder='array', categoryarray=ordre_sem),
                legend=dict(orientation="h", yanchor="bottom", y=1.02))
            st.plotly_chart(fig, use_container_width=True)

    elif vue == "👥 Clients":
        df = pd.DataFrame(data['par_client']); df['tonnes'] = df['pds_kg'].astype(float)/1000; df['ca_k'] = df['ca'].astype(float)/1000
        st.markdown(f"##### {len(df)} clients")
        sply_bars(df, prev_data('par_client'), 'client', 'tonnes', "Top 20 Clients (T)", fmt_fn=fmt_t)
        df_s = df.sort_values('ca', ascending=False).copy()
        df_s['pct'] = df_s['ca'].astype(float).cumsum()/max(df_s['ca'].astype(float).sum(),1)*100
        nb80 = len(df_s[df_s['pct']<=80])+1
        st.info(f"📊 **Pareto** : {nb80} clients = 80% du CA ({nb80*100//max(len(df),1)}% du portefeuille)")
        df_show = df[['client','tonnes','ca_k','prix_moy','premiere','derniere']].head(50).copy()
        if data_prev and data_prev.get('par_client'):
            dfp = pd.DataFrame(data_prev['par_client']); dfp['tonnes_prev'] = dfp['pds_kg'].astype(float)/1000
            dfp_dict = dict(zip(dfp['client'], dfp['tonnes_prev']))
            df_show['N-1 (T)'] = df_show['client'].map(dfp_dict)
            df_show['Evol %'] = df_show.apply(lambda r: f"{pct_evol(r['tonnes'], r.get('N-1 (T)')):.0f}%" if r.get('N-1 (T)') and pct_evol(r['tonnes'], r.get('N-1 (T)')) is not None else "—", axis=1)
        st.dataframe(df_show.rename(columns={'client':'Client','tonnes':'Tonnes','ca_k':'CA (k€)','prix_moy':'Prix moy','premiere':'1ère','derniere':'Dernière'}),
            use_container_width=True, hide_index=True, column_config={
                'Prix moy':st.column_config.NumberColumn(format="%.0f"),
                '1ère':st.column_config.DateColumn(format='DD/MM/YYYY'), 'Dernière':st.column_config.DateColumn(format='DD/MM/YYYY')})
        buf = io.BytesIO(); df.to_excel(buf, index=False, engine='openpyxl')
        st.download_button(f"📥 Export clients", buf.getvalue(), f"clients_condi.xlsx", use_container_width=True)

    elif vue == "🥔 Variétés" and data['par_variete']:
        df = pd.DataFrame(data['par_variete']); df['tonnes'] = df['pds_kg'].astype(float)/1000
        st.markdown(f"##### {len(df)} variétés")
        gc1, gc2 = st.columns(2)
        with gc1:
            fig = px.pie(df.head(15), names='variete', values='tonnes', title="Top 15 (T)")
            fig.update_traces(textinfo='label+value+percent', texttemplate='%{label}<br>%{value:,.0f}T<br>%{percent}')
            fig.update_layout(height=450); st.plotly_chart(fig, use_container_width=True)
        with gc2:
            sply_bars(df, prev_data('par_variete'), 'variete', 'tonnes', "Tonnage / variété", top_n=15, fmt_fn=fmt_t)
        st.dataframe(df[['variete','tonnes','nb_clients','prix_moy','nb']].head(30).rename(columns={
            'variete':'Variété','tonnes':'Tonnes','nb_clients':'Clients','prix_moy':'Prix moy','nb':'Lignes'}),
            use_container_width=True, hide_index=True, column_config={'Prix moy':st.column_config.NumberColumn(format="%.0f")})

    elif vue == "🏷️ Produits" and data.get('par_produit'):
        df = pd.DataFrame(data['par_produit']); df['tonnes'] = df['pds_kg'].astype(float)/1000; df['ca_k'] = df['ca'].astype(float)/1000
        sply_bars(df, prev_data('par_produit'), 'produit', 'tonnes', "Tonnage / produit", fmt_fn=fmt_t)
        st.dataframe(df[['produit','tonnes','ca_k','nb']].rename(columns={'produit':'Produit','tonnes':'Tonnes','ca_k':'CA (k€)','nb':'Lignes'}),
            use_container_width=True, hide_index=True)

    elif vue == "📦 Emballages" and data.get('par_emballage'):
        df = pd.DataFrame(data['par_emballage']); df['tonnes'] = df['pds_kg'].astype(float)/1000
        fig = px.pie(df.head(10), names='emballage', values='tonnes', title="Répartition emballages")
        fig.update_traces(textinfo='label+value+percent', texttemplate='%{label}<br>%{value:,.0f}T<br>%{percent}')
        fig.update_layout(height=400); st.plotly_chart(fig, use_container_width=True)
        st.dataframe(df[['emballage','tonnes','nb']].rename(columns={'emballage':'Emballage','tonnes':'Tonnes','nb':'Lignes'}),
            use_container_width=True, hide_index=True)

    elif vue == "📏 Calibres" and data.get('par_calibre'):
        df = pd.DataFrame(data['par_calibre']); df['tonnes'] = df['pds_kg'].astype(float)/1000
        sply_bars(df, prev_data('par_calibre'), 'calibre', 'tonnes', "Tonnage / calibre", color_now='#7B1FA2', color_prev='#FF9800', fmt_fn=fmt_t)
        st.dataframe(df[['calibre','tonnes','nb_clients','nb']].rename(columns={'calibre':'Calibre','tonnes':'Tonnes','nb_clients':'Clients','nb':'Lignes'}),
            use_container_width=True, hide_index=True)

    elif vue == "👤 Vendeurs" and data.get('par_vendeur'):
        df = pd.DataFrame(data['par_vendeur']); df['tonnes'] = df['pds_kg'].astype(float)/1000; df['ca_k'] = df['ca'].astype(float)/1000
        sply_bars(df, prev_data('par_vendeur'), 'vendeur', 'ca_k', "CA / vendeur (k€)", color_now='#2E7D32', color_prev='#FF9800', fmt_fn=fmt_k)
        st.dataframe(df[['vendeur','tonnes','ca_k','nb_clients']].rename(columns={'vendeur':'Vendeur','tonnes':'Tonnes','ca_k':'CA (k€)','nb_clients':'Clients'}),
            use_container_width=True, hide_index=True)

# ============================================================================
# SOUS-ONGLETS CONDI
# ============================================================================

sous = st.radio("", ["📊 Analyse", "🎯 Prévu vs Réel"], horizontal=True, key="csous")
st.markdown("---")

if sous == "📊 Analyse":
    if COMP_DATES:
        la, d1a, d1b, lb, d2a, d2b = COMP_DATES
        st.info(f"🔀 Comparaison : **{la}** vs **{lb}**")
        data_a = get_analyse_ventes('frulog_lignes_condi', d1a, d1b)
        data_b = get_analyse_ventes('frulog_lignes_condi', d2a, d2b)
        render_analyse_ventes(data_a, data_b, lb, "condi", show_produit=True)
    else:
        sp1, sp2, now1, now2 = sply_dates()
        data_now  = get_analyse_ventes('frulog_lignes_condi', now1, now2) if now1 else get_analyse_ventes('frulog_lignes_condi')
        data_prev = get_analyse_ventes('frulog_lignes_condi', sp1, sp2) if sp1 else None
        label_prev = f"{sp1.strftime('%d/%m/%Y')}→{sp2.strftime('%d/%m/%Y')}" if sp1 else "N-1"
        render_analyse_ventes(data_now, data_prev, label_prev, "condi", show_produit=True)

else:
    df_comp = get_comparaison_previsions()
    if not df_comp.empty:
        da = df_comp[df_comp['prevu_t'].astype(float) > 0]
        tg = da['expedie_t'].astype(float).sum()/max(da['prevu_t'].astype(float).sum(), 0.001)*100 if not da.empty else 0
        tp = df_comp['prevu_t'].astype(float).sum(); te = df_comp['expedie_t'].astype(float).sum()
        k1, k2, k3, k4 = st.columns(4)
        with k1: st.metric("Prévu",      f"{tp:.1f} T")
        with k2: st.metric("Expédié",    f"{te:.1f} T")
        with k3: st.metric("Écart",      f"{te-tp:+.1f} T")
        with k4: st.metric("Réalisation",f"{tg:.0f}%")
        st.markdown("---")
        ds = df_comp.groupby(['annee','semaine']).agg(
            prevu=('prevu_t', lambda x: x.astype(float).sum()),
            expedie=('expedie_t', lambda x: x.astype(float).sum())
        ).reset_index()
        ds['label'] = ds.apply(lambda r: f"S{int(r['semaine']):02d}", axis=1)
        fig = go.Figure()
        fig.add_trace(go.Bar(x=ds['label'], y=ds['prevu'], name='Prévu', marker_color='#90CAF9',
            text=[f"{v:.0f}" for v in ds['prevu']], textposition='outside', textfont_size=9))
        fig.add_trace(go.Bar(x=ds['label'], y=ds['expedie'], name='Expédié', marker_color='#1565C0',
            text=[f"{v:.0f}" for v in ds['expedie']], textposition='outside', textfont_size=9))
        fig.update_layout(barmode='group', title="Prévu vs Expédié (T)", height=400)
        st.plotly_chart(fig, use_container_width=True)
        ds['taux'] = ds.apply(lambda r: r['expedie']/r['prevu']*100 if r['prevu'] > 0 else None, axis=1)
        if ds['taux'].notna().any():
            colors = ['#4CAF50' if t and 80<=t<=120 else '#FF9800' if t and (60<=t<80 or 120<t<=150) else '#F44336' for t in ds['taux']]
            ft = go.Figure([go.Bar(x=ds['label'], y=ds['taux'], marker_color=colors,
                text=[f"{v:.0f}%" if v else "" for v in ds['taux']], textposition='outside', textfont_size=10)])
            ft.add_hline(y=100, line_dash="dash"); ft.update_layout(title="Taux réalisation (%)", height=350)
            st.plotly_chart(ft, use_container_width=True)
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine='openpyxl') as w:
            df_comp.to_excel(w, index=False, sheet_name='Détail'); ds.to_excel(w, index=False, sheet_name='Semaine')
        st.download_button("📥 Export", buf.getvalue(), "prevu_vs_reel.xlsx", use_container_width=True)
    else:
        st.info("📭 Aucune donnée prévision")

show_footer()
