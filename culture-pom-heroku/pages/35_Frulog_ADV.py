import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, date, timedelta
from database import get_connection
from components import show_footer
from auth import require_access
import plotly.graph_objects as go
import plotly.express as px
import io

st.set_page_config(page_title="Frulog ADV - POMI", page_icon="🧾", layout="wide")
st.markdown("""<style>
    .block-container {padding-top:2rem!important;padding-bottom:0.5rem!important;
        padding-left:2rem!important;padding-right:2rem!important;}
    h1,h2,h3,h4{margin-top:0.3rem!important;margin-bottom:0.3rem!important;}
    [data-testid="stMetricValue"]{font-size:1.4rem!important;}
    hr{margin-top:0.5rem!important;margin-bottom:0.5rem!important;}
</style>""", unsafe_allow_html=True)

require_access("COMMERCIAL")
st.title("🧾 Frulog — Stats ADV · Délais de Facturation")

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

fc1, fc2, fc3 = st.columns([2, 1.5, 1.5])
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

st.markdown("---")
DATE_DEB = date_deb
DATE_FIN = date_fin

# ============================================================================
# RÈGLE FILTRE no_de_bon
# Garder : bons SANS '/' OU se terminant par '/1'
# Exclure : /2, /3, ... (avoirs / refacturations)
# ============================================================================

FILTRE_BON = "(no_de_bon NOT LIKE '%/%' OR no_de_bon LIKE '%/1')"

# ============================================================================
# HELPERS COMMUNS
# ============================================================================

def to_days(v):
    """Convertit un intervalle PostgreSQL (timedelta ou int) en jours."""
    if v is None:
        return None
    if isinstance(v, timedelta):
        return v.days
    try:
        return int(v)
    except:
        return None


def get_kpis(df):
    if df.empty or 'delai_jours' not in df.columns:
        return {}
    s = df['delai_jours'].dropna()
    if s.empty:
        return {}
    return {
        'nb_facturees': len(df),
        'delai_moy':    s.mean(),
        'delai_med':    s.median(),
        'delai_max':    s.max(),
        'delai_min':    s.min(),
        'pct_moins_30': (s <= 30).mean() * 100,
        'pct_plus_60':  (s > 60).mean() * 100,
    }


def render_kpis_row(kpis, nb_nfact):
    nb_fact  = kpis.get('nb_facturees', 0)
    nb_total = nb_fact + nb_nfact
    pct_fact = nb_fact / max(nb_total, 1) * 100
    c1, c2, c3, c4, c5, c6 = st.columns(6)
    with c1: st.metric("✅ Facturées",    f"{nb_fact:,}".replace(',', ' '),  delta=f"{pct_fact:.0f}% du total")
    with c2: st.metric("❌ Non facturées", f"{nb_nfact:,}".replace(',', ' '))
    with c3: st.metric("⏱️ Délai moyen",  f"{kpis.get('delai_moy', 0):.1f} j")
    with c4: st.metric("📊 Délai médian", f"{kpis.get('delai_med', 0):.0f} j")
    with c5: st.metric("✅ ≤ 30 j",       f"{kpis.get('pct_moins_30', 0):.0f}%")
    with c6: st.metric("⚠️ > 60 j",       f"{kpis.get('pct_plus_60', 0):.0f}%")


def render_evolution_mensuelle(df_fact, kpis, date_col, label_flux, tab_key):
    if df_fact.empty:
        st.info("📭 Pas de données facturées pour cette période.")
        return

    df2 = df_fact.copy()
    df2[date_col] = pd.to_datetime(df2[date_col], errors='coerce')
    df2['mois']   = df2[date_col].dt.month
    df2['annee']  = df2[date_col].dt.year
    agg = df2.groupby(['annee','mois']).agg(
        delai_moy=('delai_jours', 'mean'),
        delai_med=('delai_jours', 'median'),
        nb=('no_de_bon', 'count'),
    ).reset_index().sort_values(['annee','mois'])

    mois_noms = {1:'Jan',2:'Fév',3:'Mar',4:'Avr',5:'Mai',6:'Jun',
                 7:'Jul',8:'Aoû',9:'Sep',10:'Oct',11:'Nov',12:'Déc'}
    agg['label'] = agg['mois'].astype(int).map(mois_noms) + ' ' + agg['annee'].astype(int).astype(str).str[-2:]

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=agg['label'], y=agg['delai_moy'],
        mode='lines+markers+text', name='Délai moyen',
        line=dict(color='#1565C0', width=3), marker=dict(size=9),
        text=[f"{v:.0f}j" for v in agg['delai_moy']],
        textposition='top center', textfont=dict(size=9, color='#1565C0')
    ))
    fig.add_trace(go.Scatter(
        x=agg['label'], y=agg['delai_med'],
        mode='lines+markers+text', name='Délai médian',
        line=dict(color='#FF9800', width=2, dash='dot'), marker=dict(color='#FF9800', size=7),
        text=[f"{v:.0f}j" for v in agg['delai_med']],
        textposition='bottom center', textfont=dict(size=9, color='#E65100')
    ))
    fig.add_hline(y=30, line_dash="dash", line_color="#4CAF50",
                  annotation_text="30 j", annotation_position="right", annotation_font_color="#4CAF50")
    fig.add_hline(y=60, line_dash="dash", line_color="#F44336",
                  annotation_text="60 j", annotation_position="right", annotation_font_color="#F44336")
    fig.update_layout(title=f"Évolution du délai de facturation — {label_flux}",
                      height=420, xaxis_tickangle=-45,
                      legend=dict(orientation="h", yanchor="bottom", y=1.02),
                      yaxis_title="Jours")
    st.plotly_chart(fig, use_container_width=True)

    fig2 = go.Figure(go.Bar(
        x=agg['label'], y=agg['nb'], marker_color='#90CAF9',
        text=agg['nb'], textposition='outside', textfont_size=9
    ))
    fig2.update_layout(title="Volume mensuel — lignes facturées", height=280,
                       xaxis_tickangle=-45, showlegend=False)
    st.plotly_chart(fig2, use_container_width=True)

    st.markdown("##### 📊 Distribution globale des délais")
    fig3 = px.histogram(df_fact, x='delai_jours', nbins=40,
                        color_discrete_sequence=['#1565C0'],
                        labels={'delai_jours': 'Délai (jours)'},
                        title="Distribution des délais de facturation")
    fig3.add_vline(x=kpis['delai_moy'], line_dash="dash", line_color="#FF9800",
                   annotation_text=f"Moy. {kpis['delai_moy']:.0f}j", annotation_font_color="#E65100")
    fig3.add_vline(x=kpis['delai_med'], line_dash="dot", line_color="#4CAF50",
                   annotation_text=f"Méd. {kpis['delai_med']:.0f}j", annotation_font_color="#2E7D32")
    fig3.update_layout(height=320)
    st.plotly_chart(fig3, use_container_width=True)

    st.markdown("##### 📋 Détail mensuel")
    df_show = agg[['label','delai_moy','delai_med','nb']].copy()
    df_show.columns = ['Mois','Délai moy (j)','Délai méd (j)','Lignes']
    df_show['Délai moy (j)'] = df_show['Délai moy (j)'].round(1)
    df_show['Délai méd (j)'] = df_show['Délai méd (j)'].round(0).astype(int)
    st.dataframe(df_show, use_container_width=True, hide_index=True)
    buf = io.BytesIO()
    df_show.to_excel(buf, index=False, engine='openpyxl')
    st.download_button(f"📥 Export mensuel", buf.getvalue(),
                       f"delais_mensuels_{label_flux.lower()}.xlsx",
                       use_container_width=True, key=f"dl_mois_{tab_key}")


def render_par_dim(df_fact, kpis, dim_col, dim_label, label_flux, tab_key):
    if df_fact.empty:
        st.info(f"📭 Pas de données pour cet axe.")
        return

    agg = df_fact.groupby(dim_col).agg(
        delai_moy=('delai_jours', 'mean'),
        delai_med=('delai_jours', 'median'),
        delai_max=('delai_jours', 'max'),
        nb=('no_de_bon', 'count'),
    ).reset_index().sort_values('delai_moy', ascending=False).reset_index(drop=True)

    seuil    = st.slider("⚠️ Seuil d'alerte (jours)", 10, 90, 45, 5, key=f"seuil_{tab_key}")
    nb_alert = (agg['delai_moy'] > seuil).sum()
    st.markdown("---")
    if nb_alert > 0:
        st.warning(f"⚠️ **{nb_alert} {dim_label.lower()}(s)** avec délai moyen > {seuil} j")

    colors = ['#F44336' if v > seuil else '#1565C0' for v in agg['delai_moy']]
    fig = go.Figure(go.Bar(
        y=agg[dim_col], x=agg['delai_moy'], orientation='h',
        marker_color=colors,
        text=[f"{v:.1f} j" for v in agg['delai_moy']],
        textposition='outside', textfont=dict(size=9)
    ))
    fig.add_vline(x=seuil, line_dash="dash", line_color="#FF9800",
                  annotation_text=f"Seuil {seuil} j", annotation_font_color="#E65100")
    fig.add_vline(x=kpis['delai_moy'], line_dash="dot", line_color="#9C27B0",
                  annotation_text=f"Moy. {kpis['delai_moy']:.0f} j",
                  annotation_position="bottom right", annotation_font_color="#6A1B9A")
    fig.update_layout(
        title=f"Délai moyen par {dim_label} — {label_flux}",
        height=max(400, len(agg) * 28),
        xaxis_title="Jours",
        yaxis=dict(autorange="reversed")
    )
    st.plotly_chart(fig, use_container_width=True)

    df_show = agg[[dim_col,'delai_moy','delai_med','delai_max','nb']].copy()
    df_show.columns = [dim_label,'Délai moy (j)','Délai méd (j)','Délai max (j)','Lignes']
    df_show['Délai moy (j)'] = df_show['Délai moy (j)'].round(1)
    df_show['Délai méd (j)'] = df_show['Délai méd (j)'].round(0).astype(int)
    df_show['Délai max (j)'] = df_show['Délai max (j)'].astype(int)
    st.dataframe(df_show, use_container_width=True, hide_index=True)

    if nb_alert > 0:
        with st.expander(f"⚠️ Détail des {nb_alert} en alerte (> {seuil} j)"):
            st.dataframe(
                df_show[df_show['Délai moy (j)'] > seuil].sort_values('Délai moy (j)', ascending=False),
                use_container_width=True, hide_index=True)

    buf = io.BytesIO()
    df_show.to_excel(buf, index=False, engine='openpyxl')
    st.download_button(f"📥 Export {dim_label}", buf.getvalue(),
                       f"delais_{dim_label.lower()}_{label_flux.lower()}.xlsx",
                       use_container_width=True, key=f"dl_dim_{tab_key}")


def render_non_facturees(df_nfact, date_col, dim_col, dim_label, label_flux, tab_key):
    if df_nfact.empty:
        st.success(f"✅ Toutes les lignes {label_flux} de la période sont facturées.")
        return

    nb_nfact  = len(df_nfact)
    # Montant : chercher la colonne disponible selon le flux
    montant_col = next((c for c in ['montant_ht','montant_euro','montant'] if c in df_nfact.columns), None)
    montant_val = df_nfact[montant_col].sum() if montant_col else 0

    n1, n2 = st.columns(2)
    with n1: st.metric("📋 Lignes non facturées", f"{nb_nfact:,}".replace(',', ' '))
    with n2: st.metric("💰 Montant en attente",   f"{montant_val:,.0f} €".replace(',', ' ') if montant_val else "—")
    st.markdown("---")

    df2 = df_nfact.copy()
    df2[date_col] = pd.to_datetime(df2[date_col], errors='coerce')
    today = pd.Timestamp(date.today())
    df2['jours_attente'] = (today - df2[date_col]).dt.days

    bins   = [0, 15, 30, 60, 90, 9999]
    labels = ['0-15 j','16-30 j','31-60 j','61-90 j','> 90 j']
    df2['tranche'] = pd.cut(df2['jours_attente'], bins=bins, labels=labels, right=True)
    tranche_count  = df2['tranche'].value_counts().reindex(labels).fillna(0)

    col_pie, col_info = st.columns([1, 1])
    with col_pie:
        colors_pie = ['#4CAF50','#8BC34A','#FF9800','#FF5722','#F44336']
        fig_pie = go.Figure(go.Pie(
            labels=tranche_count.index, values=tranche_count.values,
            marker_colors=colors_pie, textinfo='label+value+percent', hole=0.35
        ))
        fig_pie.update_layout(title="Ancienneté des lignes non facturées", height=360)
        st.plotly_chart(fig_pie, use_container_width=True)
    with col_info:
        st.markdown(f"##### Par {dim_label}")
        prod_nfact = df2.groupby(dim_col).agg(
            nb=('no_de_bon','count'),
            attente_moy=('jours_attente','mean')
        ).reset_index().sort_values('nb', ascending=False)
        prod_nfact.columns = [dim_label,'Lignes','Attente moy (j)']
        prod_nfact['Attente moy (j)'] = prod_nfact['Attente moy (j)'].round(0).astype(int)
        st.dataframe(prod_nfact, use_container_width=True, hide_index=True)

    st.markdown("---")
    st.markdown("##### 📋 Détail des lignes non facturées")
    cols_base = ['no_de_bon', dim_col, date_col, 'jours_attente']
    cols_opt  = ['variete','depot','type','client','montant','montant_euro','montant_ht','pds_net']
    cols_show = cols_base + [c for c in cols_opt if c in df2.columns and c != dim_col]
    rename_map = {
        'no_de_bon':'Bon', dim_col: dim_label, date_col:'Date expé',
        'jours_attente':'Jours att.', 'variete':'Variété', 'depot':'Dépôt',
        'type':'Type', 'client':'Client',
        'montant':'Montant (€)', 'montant_euro':'Montant (€)',
        'montant_ht':'Montant HT (€)', 'pds_net':'Poids net (kg)'
    }
    df_detail = df2[[c for c in cols_show if c in df2.columns]].sort_values('jours_attente', ascending=False)
    st.dataframe(
        df_detail.rename(columns=rename_map),
        use_container_width=True, hide_index=True,
        column_config={
            'Date expé':      st.column_config.DateColumn(format='DD/MM/YYYY'),
            'Montant (€)':    st.column_config.NumberColumn(format="%.0f €"),
            'Montant HT (€)': st.column_config.NumberColumn(format="%.0f €"),
            'Poids net (kg)': st.column_config.NumberColumn(format="%.0f"),
        }
    )
    buf = io.BytesIO()
    df_detail.rename(columns=rename_map).to_excel(buf, index=False, engine='openpyxl')
    st.download_button(f"📥 Export non facturées", buf.getvalue(),
                       f"non_facturees_{label_flux.lower()}.xlsx",
                       use_container_width=True, key=f"dl_nf_{tab_key}")

# ============================================================================
# FONCTIONS BDD
# ============================================================================

def get_achat_delais():
    """Achats : dt_chargmt → date_facture. Bons sans /2 /3."""
    try:
        conn = get_connection(); cur = conn.cursor()
        cur.execute(f"""
            SELECT
                no_de_bon, apporteur, variete, depot,
                dt_chargmt, date_facture,
                montant_euro, montant_ht, pds_net, type,
                CASE
                    WHEN date_facture IS NOT NULL AND dt_chargmt IS NOT NULL
                    THEN (date_facture - dt_chargmt)
                    ELSE NULL
                END AS delai_jours
            FROM frulog_lignes_achat
            WHERE dt_chargmt >= %s AND dt_chargmt <= %s
              AND {FILTRE_BON}
            ORDER BY dt_chargmt DESC
        """, (DATE_DEB, DATE_FIN))
        rows = cur.fetchall(); cur.close(); conn.close()
        if not rows:
            return pd.DataFrame(), pd.DataFrame()
        df = pd.DataFrame(rows)
        df['delai_jours'] = df['delai_jours'].apply(to_days)
        df_fact  = df[df['delai_jours'].notna() & (df['delai_jours'] >= 0)].copy()
        df_nfact = df[df['date_facture'].isna()].copy()
        return df_fact, df_nfact
    except Exception as e:
        st.error(f"Erreur Achats : {e}"); return pd.DataFrame(), pd.DataFrame()


def get_ventes_delais(table):
    """
    Ventes Condi/Négoce : date_charg → dt_fac_v.
    Toutes lignes (pas de filtre type). Bons sans /2 /3.
    """
    try:
        conn = get_connection(); cur = conn.cursor()
        cur.execute(f"""
            SELECT
                no_de_bon, client, apporteur, variete, depot, vendeur,
                date_charg, dt_fac_v,
                montant, montant_euro, pds_net, type,
                CASE
                    WHEN dt_fac_v IS NOT NULL AND date_charg IS NOT NULL
                    THEN (dt_fac_v - date_charg)
                    ELSE NULL
                END AS delai_jours
            FROM {table}
            WHERE date_charg >= %s AND date_charg <= %s
              AND {FILTRE_BON}
            ORDER BY date_charg DESC
        """, (DATE_DEB, DATE_FIN))
        rows = cur.fetchall(); cur.close(); conn.close()
        if not rows:
            return pd.DataFrame(), pd.DataFrame()
        df = pd.DataFrame(rows)
        df['delai_jours'] = df['delai_jours'].apply(to_days)
        df_fact  = df[df['delai_jours'].notna() & (df['delai_jours'] >= 0)].copy()
        df_nfact = df[df['dt_fac_v'].isna()].copy()
        return df_fact, df_nfact
    except Exception as e:
        st.error(f"Erreur {table} : {e}"); return pd.DataFrame(), pd.DataFrame()

# ============================================================================
# CHARGEMENT
# ============================================================================

with st.spinner("Chargement des données..."):
    df_achat_f, df_achat_nf = get_achat_delais()
    df_condi_f, df_condi_nf = get_ventes_delais('frulog_lignes_condi')
    df_nego_f,  df_nego_nf  = get_ventes_delais('frulog_lignes_negoce')

kpis_achat = get_kpis(df_achat_f)
kpis_condi = get_kpis(df_condi_f)
kpis_nego  = get_kpis(df_nego_f)

# ============================================================================
# ONGLETS PRINCIPAUX
# ============================================================================

tab_achat, tab_condi, tab_nego = st.tabs(["🛒 Achats", "📈 Condi", "🏪 Négoce"])

# ─────────────────────────────────────────────────────────────────────────────
# ACHATS
# ─────────────────────────────────────────────────────────────────────────────
with tab_achat:
    nb_total_achat = len(df_achat_f) + len(df_achat_nf)
    if nb_total_achat == 0:
        st.warning("📭 Aucune donnée Achat pour cette période.")
    else:
        st.caption("Délai = **Date facture** − **Date chargement** · Bons originaux uniquement (exclu /2, /3…)")
        if kpis_achat:
            render_kpis_row(kpis_achat, len(df_achat_nf))
        st.markdown("---")

        sub1, sub2, sub3 = st.tabs([
            "📅 Évolution mensuelle",
            "🏭 Par Producteur",
            f"❌ Non facturées ({len(df_achat_nf)})"
        ])
        with sub1:
            render_evolution_mensuelle(df_achat_f, kpis_achat, 'dt_chargmt', 'Achats', 'achat_mois')
        with sub2:
            render_par_dim(df_achat_f, kpis_achat, 'apporteur', 'Producteur', 'Achats', 'achat_prod')
        with sub3:
            render_non_facturees(df_achat_nf, 'dt_chargmt', 'apporteur', 'Producteur', 'Achats', 'achat_nf')

# ─────────────────────────────────────────────────────────────────────────────
# CONDI
# ─────────────────────────────────────────────────────────────────────────────
with tab_condi:
    nb_total_condi = len(df_condi_f) + len(df_condi_nf)
    if nb_total_condi == 0:
        st.warning("📭 Aucune donnée Condi pour cette période.")
    else:
        st.caption("Délai = **Date facture vente** − **Date chargement** · Bons originaux uniquement (exclu /2, /3…)")
        if kpis_condi:
            render_kpis_row(kpis_condi, len(df_condi_nf))
        st.markdown("---")

        sub1, sub2, sub3 = st.tabs([
            "📅 Évolution mensuelle",
            "👥 Par Client",
            f"❌ Non facturées ({len(df_condi_nf)})"
        ])
        with sub1:
            render_evolution_mensuelle(df_condi_f, kpis_condi, 'date_charg', 'Condi', 'condi_mois')
        with sub2:
            render_par_dim(df_condi_f, kpis_condi, 'client', 'Client', 'Condi', 'condi_client')
        with sub3:
            render_non_facturees(df_condi_nf, 'date_charg', 'client', 'Client', 'Condi', 'condi_nf')

# ─────────────────────────────────────────────────────────────────────────────
# NÉGOCE
# ─────────────────────────────────────────────────────────────────────────────
with tab_nego:
    nb_total_nego = len(df_nego_f) + len(df_nego_nf)
    if nb_total_nego == 0:
        st.warning("📭 Aucune donnée Négoce pour cette période.")
    else:
        st.caption("Délai = **Date facture vente** − **Date chargement** · Bons originaux uniquement (exclu /2, /3…)")
        if kpis_nego:
            render_kpis_row(kpis_nego, len(df_nego_nf))
        st.markdown("---")

        sub1, sub2, sub3 = st.tabs([
            "📅 Évolution mensuelle",
            "👥 Par Client",
            f"❌ Non facturées ({len(df_nego_nf)})"
        ])
        with sub1:
            render_evolution_mensuelle(df_nego_f, kpis_nego, 'date_charg', 'Négoce', 'nego_mois')
        with sub2:
            render_par_dim(df_nego_f, kpis_nego, 'client', 'Client', 'Négoce', 'nego_client')
        with sub3:
            render_non_facturees(df_nego_nf, 'date_charg', 'client', 'Client', 'Négoce', 'nego_nf')

show_footer()
