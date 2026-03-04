import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, date, timedelta
from database import get_connection
from components import show_footer
from auth import require_access, is_admin
import plotly.express as px
import plotly.graph_objects as go
import io

st.set_page_config(page_title="Frulog - POMI", page_icon="📊", layout="wide")
st.markdown("""<style>
    .block-container {padding-top:2rem!important;padding-bottom:0.5rem!important;
        padding-left:2rem!important;padding-right:2rem!important;}
    h1,h2,h3,h4{margin-top:0.3rem!important;margin-bottom:0.3rem!important;}
    [data-testid="stMetricValue"]{font-size:1.4rem!important;}
    hr{margin-top:0.5rem!important;margin-bottom:0.5rem!important;}
</style>""", unsafe_allow_html=True)

require_access("COMMERCIAL")
st.title("📊 Frulog — Import & Analyse")

# ============================================================================
# FILTRES GLOBAUX : CAMPAGNE + DATE RANGE + COMPARAISON
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
        sel_camp = st.selectbox("🗓️ Campagne", camp_opts,
                               format_func=lambda y: camp_labels_map[y], key="f_camp")
    with fc2:
        d_min_camp = campagne_dates(sel_camp)[0] if sel_camp else date(2022, 1, 1)
        d_max_camp = campagne_dates(sel_camp)[1] if sel_camp else date(2027, 12, 31)
        date_deb = st.date_input("📅 Du", value=d_min_camp, min_value=d_min_camp,
                                 max_value=d_max_camp, key="f_deb")
    with fc3:
        date_fin = st.date_input("📅 Au", value=d_max_camp, min_value=d_min_camp,
                                 max_value=d_max_camp, key="f_fin")
    with fc4:
        mode_compare = st.selectbox("🔀 Comparaison", [
            "Aucune", "📅 Campagne vs Campagne", "📆 Mois vs Mois", "📆 Semaine vs Semaine"
        ], key="f_compare")

# Comparaison — paramètres
COMP_DATES = None  # (label1, d1_min, d1_max, label2, d2_min, d2_max) ou None
if mode_compare == "📅 Campagne vs Campagne":
    cc1, cc2 = st.columns(2)
    with cc1:
        c1 = st.selectbox("Campagne A", campagnes, key="comp_c1")
    with cc2:
        c2 = st.selectbox("Campagne B", [c for c in campagnes if c != c1], key="comp_c2")
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

# Variables globales filtre
DATE_DEB = date_deb
DATE_FIN = date_fin

# ============================================================================
# CONSTANTES
# ============================================================================

COLONNES_VENTES = {
    'No de bon':'no_de_bon','Type':'type','Date cmd':'date_cmd','Date charg':'date_charg',
    'Date livr':'date_livr','Date Créa':'date_crea','N°BlApp':'no_bl_app','N°Contrat':'no_contrat',
    'Client':'client','Ref client':'ref_client','Depot':'depot','Produit':'produit',
    'Variete':'variete','Categ':'categ','Calibre':'calibre','Couleur':'couleur',
    'Emballage':'emballage','Marque':'marque','Nb Col':'nb_col','Pds brut':'pds_brut',
    'Tare V':'tare_v','Pds net':'pds_net','Prix':'prix','UF':'uf','Tp.Px':'tp_px',
    'Fac.P':'fac_p','NB Pce':'nb_pce','Montant':'montant','Devise':'devise',
    'Montant EURO':'montant_euro','No Fact./Avoir':'no_fact_avoir','Dt Fac V':'dt_fac_v',
    'Etat':'etat','Typ V':'typ_v','Nb pal':'nb_pal','Nb pal sol':'nb_pal_sol',
    'Apporteur':'apporteur','Lot':'lot','Pds brut A':'pds_brut_a','Tare A':'tare_a',
    'Pds Ach':'pds_ach','Px Ach':'px_ach','Vehicule':'vehicule','Remorque':'remorque',
    'CMR':'cmr','BR':'br','BL.P':'bl_p','Bon Ach':'bon_ach','Fac Ach':'fac_ach',
    'Dt Fac A':'dt_fac_a','Dte Fab':'dte_fab','Agent':'agent','Vendeur':'vendeur',
    'TRPACHATS Val':'trp_achats_val','TRPINTER Val':'trp_inter_val',
    'CONDITMT Val':'conditmt_val','TRPVENTES Val':'trp_ventes_val',
    'TRPLITIGE Val':'trp_litige_val','PRESTABB Val':'presta_bb_val',
    'PRESTASACS Val':'presta_sacs_val','STOCKCULTU Val':'stock_cultu_val',
    'STOCKEXT Val':'stock_ext_val','STOCKTILLY Val':'stock_tilly_val',
    'COMVENTES Val':'com_ventes_val','DOUANES Val':'douanes_val',
    'EMBALLAGE Val':'emballage_val','EXPEDITION Val':'expedition_val',
    '111 Val':'col_111_val','Transport':'transport',
    'GTIN U':'gtin_u','GTIN P':'gtin_p','GTIN C':'gtin_c','GGN':'ggn','Dt.Expi':'dt_expi'
}
COLONNES_ACHAT = {
    'Date du bon':'date_du_bon','Dt chargmt':'dt_chargmt','No de Bon':'no_de_bon',
    'Vendeur':'vendeur','Apporteur':'apporteur','Famille':'famille','Dépôt':'depot',
    'Produit':'produit','Variété':'variete','Code Reg.':'code_reg','Catég.':'categ',
    'Couleur':'couleur','Embal.':'emballage','Marque':'marque','Calibre':'calibre',
    'Support':'support','Nb Pal':'nb_pal','Nb Colis':'nb_colis','Nb Col Sup.':'nb_col_sup',
    'Poids brut des fruits':'pds_brut','Poids net/Qté':'pds_net',
    'Prix achat':'prix_achat','U.A':'ua','U.C.':'uc',
    'Montant H.T.':'montant_ht','T. Px':'tp_px','Code Dev.':'code_dev',
    'Montant EURO':'montant_euro','No bon APP':'no_bon_app',
    'No Fact./Avoir':'no_fact_avoir','Lot':'lot','état':'etat',
    'Date facture':'date_facture','tare':'tare','Type':'type',
    'Référence':'reference','GGN':'ggn','Dt.Expi':'dt_expi'
}
VENTES_DATE_COLS = ['date_cmd','date_charg','date_livr','date_crea','dt_fac_v','dt_fac_a','dte_fab','dt_expi']
VENTES_INT_COLS = ['nb_col','nb_pce','etat','nb_pal','nb_pal_sol']
VENTES_NUM_COLS = ['pds_brut','tare_v','pds_net','prix','montant','montant_euro',
    'pds_brut_a','tare_a','pds_ach','px_ach','trp_achats_val','trp_inter_val',
    'conditmt_val','trp_ventes_val','trp_litige_val','presta_bb_val','presta_sacs_val',
    'stock_cultu_val','stock_ext_val','stock_tilly_val','com_ventes_val','douanes_val',
    'emballage_val','expedition_val','col_111_val']
ACHAT_DATE_COLS = ['date_du_bon','dt_chargmt','date_facture','dt_expi']
ACHAT_INT_COLS = ['nb_pal','nb_colis','nb_col_sup','etat']
ACHAT_NUM_COLS = ['pds_brut','pds_net','prix_achat','montant_ht','montant_euro','tare']

def make_cle_produit(emb, mrq):
    e = str(emb).strip().upper() if emb and str(emb).strip() != '.' else ''
    m = str(mrq).strip().upper() if mrq and str(mrq).strip() != '.' else ''
    return f"{e}|{m}"

def to_python(val):
    if val is None or (isinstance(val, float) and np.isnan(val)) or val is pd.NaT: return None
    if isinstance(val, (np.integer, np.int64)): return int(val)
    if isinstance(val, (np.floating, np.float64)): return float(val)
    return val

def clean_text(x):
    if pd.isna(x) or str(x).strip() == '.': return None
    return str(x).strip()

def cw_ventes(d1=None, d2=None):
    """Clause WHERE campagne/daterange pour ventes"""
    dd = d1 or DATE_DEB; df = d2 or DATE_FIN
    return f" AND date_charg >= '{dd}' AND date_charg <= '{df}'"

def cw_achat(d1=None, d2=None):
    dd = d1 or DATE_DEB; df = d2 or DATE_FIN
    return f" AND dt_chargmt >= '{dd}' AND dt_chargmt <= '{df}'"

def sply_dates():
    """SPLY dynamique : même période N-1 calée sur aujourd'hui.
    Ex: si filtre = Camp 2026 (01/06/2025→31/05/2026) et aujourd'hui = 02/03/2026
    → Période N  = 01/06/2025 → 02/03/2026 (tronquée à aujourd'hui)
    → Période N-1 = 01/06/2024 → 02/03/2025 (même fenêtre, 1 an avant)
    """
    try:
        today = date.today()
        # Tronquer la fin de période à aujourd'hui si dans le futur
        actual_end = min(DATE_FIN, today)
        # Calculer le décalage en jours depuis le début de période
        delta_days = (actual_end - DATE_DEB).days
        # Période N-1 : même début -1 an, même durée
        try:
            prev_start = DATE_DEB.replace(year=DATE_DEB.year - 1)
        except ValueError:
            prev_start = DATE_DEB.replace(year=DATE_DEB.year - 1, day=28)
        prev_end = prev_start + timedelta(days=delta_days)
        return prev_start, prev_end, DATE_DEB, actual_end
    except: return None, None, None, None

# ============================================================================
# FONCTIONS BDD
# ============================================================================

def get_imports(source=None):
    try:
        conn = get_connection(); cur = conn.cursor()
        w = f"WHERE source='{source}'" if source else ""
        cur.execute(f"SELECT * FROM frulog_imports {w} ORDER BY date_import DESC LIMIT 50")
        rows = cur.fetchall(); cur.close(); conn.close()
        return pd.DataFrame(rows) if rows else pd.DataFrame()
    except: return pd.DataFrame()

def get_mapping_produit():
    try:
        conn = get_connection(); cur = conn.cursor()
        cur.execute("""SELECT fm.*, pc.libelle as libelle_produit
            FROM frulog_mapping_produit fm LEFT JOIN ref_produits_commerciaux pc ON fm.code_produit_commercial = pc.code_produit
            WHERE fm.is_active = TRUE ORDER BY fm.emballage, fm.marque""")
        rows = cur.fetchall(); cur.close(); conn.close()
        return pd.DataFrame(rows) if rows else pd.DataFrame()
    except: return pd.DataFrame()

def get_mapping_suremballage():
    try:
        conn = get_connection(); cur = conn.cursor()
        cur.execute("""SELECT fms.*, se.libelle as libelle_se, se.nb_uvc
            FROM frulog_mapping_suremballage fms LEFT JOIN ref_sur_emballages se ON fms.sur_emballage_id = se.id
            WHERE fms.is_active = TRUE ORDER BY fms.code_emballage""")
        rows = cur.fetchall(); cur.close(); conn.close()
        return pd.DataFrame(rows) if rows else pd.DataFrame()
    except: return pd.DataFrame()

def get_produits_commerciaux():
    try:
        conn = get_connection(); cur = conn.cursor()
        cur.execute("SELECT code_produit, marque, libelle FROM ref_produits_commerciaux WHERE is_active=TRUE ORDER BY marque, libelle")
        rows = cur.fetchall(); cur.close(); conn.close(); return rows or []
    except: return []

def get_sur_emballages():
    try:
        conn = get_connection(); cur = conn.cursor()
        cur.execute("SELECT id, libelle, nb_uvc FROM ref_sur_emballages WHERE is_active=TRUE ORDER BY libelle")
        rows = cur.fetchall(); cur.close(); conn.close(); return rows or []
    except: return []

def get_combinaisons_non_mappees():
    try:
        conn = get_connection(); cur = conn.cursor()
        cur.execute(f"""SELECT fl.emballage, fl.marque, fl.depot, COUNT(*) as nb_lignes,
            SUM(ABS(COALESCE(fl.pds_net, 0)))/1000 as tonnes, COUNT(DISTINCT fl.client) as nb_clients
            FROM frulog_lignes_condi fl WHERE fl.type IN ('E','C') AND fl.code_produit_commercial IS NULL
            AND fl.emballage IS NOT NULL {cw_ventes()} GROUP BY fl.emballage, fl.marque, fl.depot ORDER BY nb_lignes DESC""")
        rows = cur.fetchall(); cur.close(); conn.close()
        return pd.DataFrame(rows) if rows else pd.DataFrame()
    except: return pd.DataFrame()

def get_emballages_non_mappes_se():
    try:
        conn = get_connection(); cur = conn.cursor()
        cur.execute(f"""SELECT fl.emballage as code_emballage, COUNT(*) as nb_lignes, SUM(COALESCE(fl.nb_col,0)) as nb_col_total
            FROM frulog_lignes_condi fl WHERE fl.type IN ('E','C') AND fl.sur_emballage_id IS NULL
            AND fl.emballage IS NOT NULL {cw_ventes()} GROUP BY fl.emballage ORDER BY nb_lignes DESC""")
        rows = cur.fetchall(); cur.close(); conn.close()
        return pd.DataFrame(rows) if rows else pd.DataFrame()
    except: return pd.DataFrame()

def sauver_mapping_produit(emb, mrq, code_produit):
    try:
        conn = get_connection(); cur = conn.cursor()
        cle = make_cle_produit(emb, mrq)
        cur.execute("""INSERT INTO frulog_mapping_produit (emballage, marque, cle_mapping, code_produit_commercial)
            VALUES (%s,%s,%s,%s) ON CONFLICT (cle_mapping) DO UPDATE SET code_produit_commercial=EXCLUDED.code_produit_commercial, updated_at=CURRENT_TIMESTAMP
            RETURNING id""", (emb, mrq, cle, code_produit))
        mid = cur.fetchone()['id']
        cur.execute("UPDATE frulog_lignes_condi SET code_produit_commercial=%s WHERE emballage=%s AND (marque=%s OR (%s IS NULL AND marque IS NULL)) AND code_produit_commercial IS NULL",
                    (code_produit, emb, mrq, mrq))
        n = cur.rowcount; conn.commit(); cur.close(); conn.close()
        return True, f"Mapping #{mid} — {n} lignes mises à jour"
    except Exception as e:
        if 'conn' in locals(): conn.rollback()
        return False, str(e)

def sauver_mapping_se(code, se_id):
    try:
        conn = get_connection(); cur = conn.cursor()
        cur.execute("""INSERT INTO frulog_mapping_suremballage (code_emballage, sur_emballage_id)
            VALUES (%s,%s) ON CONFLICT (code_emballage) DO UPDATE SET sur_emballage_id=EXCLUDED.sur_emballage_id, updated_at=CURRENT_TIMESTAMP
            RETURNING id""", (code, se_id))
        mid = cur.fetchone()['id']
        cur.execute("UPDATE frulog_lignes_condi SET sur_emballage_id=%s WHERE emballage=%s AND sur_emballage_id IS NULL", (se_id, code))
        n = cur.rowcount; conn.commit(); cur.close(); conn.close()
        return True, f"Mapping #{mid} — {n} lignes"
    except Exception as e:
        if 'conn' in locals(): conn.rollback()
        return False, str(e)

def supprimer_mapping_produit(mapping_id, emballage, marque):
    """Supprime un mapping produit et remet à NULL les lignes concernées"""
    try:
        conn = get_connection(); cur = conn.cursor()
        cur.execute("UPDATE frulog_lignes_condi SET code_produit_commercial=NULL WHERE emballage=%s AND (marque=%s OR (%s IS NULL AND marque IS NULL))",
                    (emballage, marque, marque))
        n = cur.rowcount
        cur.execute("DELETE FROM frulog_mapping_produit WHERE id=%s", (mapping_id,))
        conn.commit(); cur.close(); conn.close()
        return True, f"Mapping supprimé — {n} lignes remises à NULL"
    except Exception as e:
        if 'conn' in locals(): conn.rollback()
        return False, str(e)

def modifier_mapping_produit(mapping_id, emballage, marque, nouveau_code):
    """Modifie le produit commercial d'un mapping existant"""
    try:
        conn = get_connection(); cur = conn.cursor()
        cur.execute("UPDATE frulog_mapping_produit SET code_produit_commercial=%s, updated_at=CURRENT_TIMESTAMP WHERE id=%s",
                    (nouveau_code, mapping_id))
        cur.execute("UPDATE frulog_lignes_condi SET code_produit_commercial=%s WHERE emballage=%s AND (marque=%s OR (%s IS NULL AND marque IS NULL))",
                    (nouveau_code, emballage, marque, marque))
        n = cur.rowcount; conn.commit(); cur.close(); conn.close()
        return True, f"Mapping modifié — {n} lignes mises à jour"
    except Exception as e:
        if 'conn' in locals(): conn.rollback()
        return False, str(e)

def supprimer_mapping_se(mapping_id, code_emballage):
    """Supprime un mapping sur-emballage et remet à NULL les lignes concernées"""
    try:
        conn = get_connection(); cur = conn.cursor()
        cur.execute("UPDATE frulog_lignes_condi SET sur_emballage_id=NULL WHERE emballage=%s", (code_emballage,))
        n = cur.rowcount
        cur.execute("DELETE FROM frulog_mapping_suremballage WHERE id=%s", (mapping_id,))
        conn.commit(); cur.close(); conn.close()
        return True, f"Mapping supprimé — {n} lignes remises à NULL"
    except Exception as e:
        if 'conn' in locals(): conn.rollback()
        return False, str(e)

def modifier_mapping_se(mapping_id, code_emballage, nouveau_se_id):
    """Modifie le sur-emballage d'un mapping existant"""
    try:
        conn = get_connection(); cur = conn.cursor()
        cur.execute("UPDATE frulog_mapping_suremballage SET sur_emballage_id=%s, updated_at=CURRENT_TIMESTAMP WHERE id=%s",
                    (nouveau_se_id, mapping_id))
        cur.execute("UPDATE frulog_lignes_condi SET sur_emballage_id=%s WHERE emballage=%s",
                    (nouveau_se_id, code_emballage))
        n = cur.rowcount; conn.commit(); cur.close(); conn.close()
        return True, f"Mapping modifié — {n} lignes mises à jour"
    except Exception as e:
        if 'conn' in locals(): conn.rollback()
        return False, str(e)

# ============================================================================
# IMPORT VENTES
# ============================================================================

def importer_ventes(uploaded_file, source, username='inconnu'):
    table = f"frulog_lignes_{source.lower()}"
    try:
        df = pd.read_excel(uploaded_file, sheet_name=0)
        if len(df) == 0: return False, "Fichier vide"
        df_r = df.rename(columns=COLONNES_VENTES)
        cols_ok = [c for c in COLONNES_VENTES.values() if c in df_r.columns]
        df_c = df_r[cols_ok].copy()
        if 'no_de_bon' not in df_c.columns: return False, "Colonne 'No de bon' introuvable"
        if 'type' in df_c.columns: df_c = df_c[df_c['type'].isin(['E','A','C'])].copy()
        for col in VENTES_DATE_COLS:
            if col in df_c.columns: df_c[col] = pd.to_datetime(df_c[col], errors='coerce').dt.date
        for col in VENTES_INT_COLS:
            if col in df_c.columns: df_c[col] = pd.to_numeric(df_c[col], errors='coerce')
        for col in VENTES_NUM_COLS:
            if col in df_c.columns: df_c[col] = pd.to_numeric(df_c[col], errors='coerce')
        for col in ['type','produit','variete','categ','calibre','couleur','emballage','marque','client','depot']:
            if col in df_c.columns: df_c[col] = df_c[col].apply(clean_text)
        if 'date_charg' in df_c.columns:
            df_c['annee'] = df_c['date_charg'].apply(lambda d: d.isocalendar()[0] if pd.notna(d) else None)
            df_c['semaine'] = df_c['date_charg'].apply(lambda d: d.isocalendar()[1] if pd.notna(d) else None)
        conn = get_connection(); cur = conn.cursor()
        nb_total = len(df_c)
        nb_e = len(df_c[df_c.get('type',pd.Series())=='E']) if 'type' in df_c.columns else 0
        nb_a = len(df_c[df_c.get('type',pd.Series())=='A']) if 'type' in df_c.columns else 0
        nb_c = len(df_c[df_c.get('type',pd.Series())=='C']) if 'type' in df_c.columns else 0
        d_min = df_c['date_charg'].dropna().min() if 'date_charg' in df_c.columns else None
        d_max = df_c['date_charg'].dropna().max() if 'date_charg' in df_c.columns else None
        cur.execute("INSERT INTO frulog_imports (nom_fichier,source,nb_lignes_total,nb_lignes_type_e,nb_lignes_type_a,nb_lignes_sans_type,date_debut,date_fin,created_by) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id",
            (uploaded_file.name, source, nb_total, nb_e+nb_c, nb_a, nb_total-nb_e-nb_a-nb_c, d_min, d_max, username))
        import_id = cur.fetchone()['id']
        mp = {}; mse = {}
        if source == 'CONDI':
            cur.execute("SELECT cle_mapping,code_produit_commercial FROM frulog_mapping_produit WHERE is_active=TRUE")
            mp = {r['cle_mapping']:r['code_produit_commercial'] for r in cur.fetchall()}
            cur.execute("SELECT code_emballage,sur_emballage_id FROM frulog_mapping_suremballage WHERE is_active=TRUE")
            mse = {r['code_emballage']:r['sur_emballage_id'] for r in cur.fetchall()}
        if mp: df_c['code_produit_commercial'] = df_c.apply(lambda r: mp.get(make_cle_produit(r.get('emballage'),r.get('marque'))), axis=1)
        if mse: df_c['sur_emballage_id'] = df_c['emballage'].apply(lambda e: mse.get(str(e).strip().upper()) if e and str(e).strip()!='.' else None)
        cur.execute(f"SELECT no_de_bon,etat,pds_net,montant,type,nb_col FROM {table} WHERE no_de_bon IS NOT NULL")
        existing = {r['no_de_bon']:r for r in cur.fetchall()}
        data_cols = [c for c in cols_ok if c!='no_de_bon']+['annee','semaine']
        if source=='CONDI': data_cols += ['code_produit_commercial','sur_emballage_id']
        data_cols = list(dict.fromkeys(data_cols))
        nb_new=nb_upd=nb_unc=0
        for _,row in df_c.iterrows():
            bon = to_python(row.get('no_de_bon'))
            if not bon: continue
            rv = {c:to_python(row.get(c)) for c in data_cols}
            if bon in existing:
                ex = existing[bon]
                if any(str(to_python(row.get(k)))!=str(ex.get(k)) for k in ['etat','pds_net','montant','type','nb_col']):
                    sp=[f"{c}=%s" for c in data_cols]+["import_id=%s"]
                    cur.execute(f"UPDATE {table} SET {','.join(sp)} WHERE no_de_bon=%s", [rv[c] for c in data_cols]+[import_id,bon])
                    nb_upd+=1
                else: nb_unc+=1
            else:
                ac=['import_id','no_de_bon']+data_cols
                cur.execute(f"INSERT INTO {table} ({','.join(ac)}) VALUES ({','.join(['%s']*len(ac))})", [import_id,bon]+[rv[c] for c in data_cols])
                nb_new+=1
        conn.commit(); cur.close(); conn.close()
        m = f" {df_c['code_produit_commercial'].notna().sum()}/{nb_total} mappées." if source=='CONDI' and 'code_produit_commercial' in df_c.columns else ""
        return True, f"Import #{import_id} ({source}) : {nb_total} → **{nb_new} new**, **{nb_upd} maj**, {nb_unc} ident.{m}"
    except Exception as e:
        if 'conn' in locals(): conn.rollback()
        return False, str(e)

def importer_achat(uploaded_file, username='inconnu'):
    try:
        df = pd.read_excel(uploaded_file, sheet_name=0)
        if len(df)==0: return False, "Fichier vide"
        df_r = df.rename(columns=COLONNES_ACHAT)
        cols_ok = [c for c in COLONNES_ACHAT.values() if c in df_r.columns]
        df_c = df_r[cols_ok].copy()
        if 'no_de_bon' not in df_c.columns: return False, "Colonne introuvable"
        for col in ACHAT_DATE_COLS:
            if col in df_c.columns: df_c[col] = pd.to_datetime(df_c[col], errors='coerce').dt.date
        for col in ACHAT_INT_COLS:
            if col in df_c.columns: df_c[col] = pd.to_numeric(df_c[col], errors='coerce')
        for col in ACHAT_NUM_COLS:
            if col in df_c.columns: df_c[col] = pd.to_numeric(df_c[col], errors='coerce')
        for col in ['vendeur','apporteur','produit','variete','emballage','marque','depot','calibre','type']:
            if col in df_c.columns: df_c[col] = df_c[col].apply(clean_text)
        dc = 'dt_chargmt' if 'dt_chargmt' in df_c.columns else 'date_du_bon'
        if dc in df_c.columns:
            df_c['annee'] = df_c[dc].apply(lambda d: d.isocalendar()[0] if pd.notna(d) else None)
            df_c['semaine'] = df_c[dc].apply(lambda d: d.isocalendar()[1] if pd.notna(d) else None)
        conn = get_connection(); cur = conn.cursor()
        nt = len(df_c)
        cur.execute("INSERT INTO frulog_imports (nom_fichier,source,nb_lignes_total,nb_lignes_type_e,nb_lignes_type_a,nb_lignes_sans_type,date_debut,date_fin,created_by) VALUES (%s,'ACHAT',%s,%s,%s,%s,%s,%s,%s) RETURNING id",
            (uploaded_file.name, nt, len(df_c[df_c.get('type',pd.Series())=='S']) if 'type' in df_c.columns else 0, len(df_c[df_c.get('type',pd.Series())=='A']) if 'type' in df_c.columns else 0, 0, df_c[dc].dropna().min() if dc in df_c.columns else None, df_c[dc].dropna().max() if dc in df_c.columns else None, username))
        iid = cur.fetchone()['id']
        cur.execute("SELECT no_de_bon,etat,pds_net,montant_euro,type FROM frulog_lignes_achat WHERE no_de_bon IS NOT NULL")
        existing = {str(r['no_de_bon']):r for r in cur.fetchall()}
        data_cols = list(dict.fromkeys([c for c in cols_ok if c!='no_de_bon']+['annee','semaine']))
        nn=nu=nc=0
        for _,row in df_c.iterrows():
            bon = str(to_python(row.get('no_de_bon')))
            if not bon or bon=='None': continue
            rv = {c:to_python(row.get(c)) for c in data_cols}
            if bon in existing:
                if any(str(to_python(row.get(k)))!=str(existing[bon].get(k)) for k in ['etat','pds_net','montant_euro','type']):
                    sp=[f"{c}=%s" for c in data_cols]+["import_id=%s"]
                    cur.execute(f"UPDATE frulog_lignes_achat SET {','.join(sp)} WHERE no_de_bon=%s", [rv[c] for c in data_cols]+[iid,bon])
                    nu+=1
                else: nc+=1
            else:
                ac=['import_id','no_de_bon']+data_cols
                cur.execute(f"INSERT INTO frulog_lignes_achat ({','.join(ac)}) VALUES ({','.join(['%s']*len(ac))})", [iid,bon]+[rv[c] for c in data_cols])
                nn+=1
        conn.commit(); cur.close(); conn.close()
        return True, f"Import #{iid} (ACHAT) : {nt} → **{nn} new**, **{nu} maj**, {nc} ident."
    except Exception as e:
        if 'conn' in locals(): conn.rollback()
        return False, str(e)

# ============================================================================
# ANALYSE AVEC SPLY
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
            'par_client': f"SELECT client,COUNT(*) as nb,SUM(COALESCE(pds_net,0)) as pds_kg,SUM(COALESCE(montant,0)) as ca,AVG(prix) FILTER (WHERE prix>0) as prix_moy,MIN(date_charg) as premiere,MAX(date_charg) as derniere FROM {table} WHERE type IN ('E','C'){w} GROUP BY client ORDER BY pds_kg DESC",
            'par_variete': f"SELECT variete,COUNT(*) as nb,SUM(COALESCE(pds_net,0)) as pds_kg,SUM(COALESCE(montant,0)) as ca,COUNT(DISTINCT client) as nb_clients,AVG(prix) FILTER (WHERE prix>0) as prix_moy FROM {table} WHERE type IN ('E','C') AND variete IS NOT NULL{w} GROUP BY variete ORDER BY pds_kg DESC",
            'par_mois': f"SELECT EXTRACT(YEAR FROM date_charg)::int as annee,EXTRACT(MONTH FROM date_charg)::int as mois,SUM(COALESCE(pds_net,0)) as pds_kg,SUM(COALESCE(montant,0)) as ca FROM {table} WHERE type IN ('E','C') AND date_charg IS NOT NULL{w} GROUP BY 1,2 ORDER BY annee,mois",
            'par_semaine': f"SELECT annee,semaine,SUM(COALESCE(pds_net,0)) as pds_kg,SUM(COALESCE(montant,0)) as ca FROM {table} WHERE type IN ('E','C') AND annee IS NOT NULL{w} GROUP BY annee,semaine ORDER BY annee,semaine",
            'par_produit': f"SELECT COALESCE(code_produit_commercial,'❓ Non mappé') as produit,COUNT(*) as nb,SUM(COALESCE(pds_net,0)) as pds_kg,SUM(COALESCE(montant,0)) as ca FROM {table} WHERE type IN ('E','C'){w} GROUP BY 1 ORDER BY pds_kg DESC",
            'par_emballage': f"SELECT emballage,COUNT(*) as nb,SUM(COALESCE(pds_net,0)) as pds_kg FROM {table} WHERE type IN ('E','C') AND emballage IS NOT NULL{w} GROUP BY emballage ORDER BY pds_kg DESC",
            'par_calibre': f"SELECT calibre,COUNT(*) as nb,SUM(COALESCE(pds_net,0)) as pds_kg,COUNT(DISTINCT client) as nb_clients FROM {table} WHERE type IN ('E','C') AND calibre IS NOT NULL{w} GROUP BY calibre ORDER BY pds_kg DESC",
            'par_vendeur': f"SELECT vendeur,SUM(COALESCE(pds_net,0)) as pds_kg,SUM(COALESCE(montant,0)) as ca,COUNT(DISTINCT client) as nb_clients FROM {table} WHERE type IN ('E','C') AND vendeur IS NOT NULL{w} GROUP BY vendeur ORDER BY ca DESC",
        }
        for k2,sql in queries.items():
            cur.execute(sql); r[k2] = cur.fetchall()
        # Campagne N-1 COMPLETE (toutes semaines) pour graphique hebdo projection
        try:
            prev_start_full = DATE_DEB.replace(year=DATE_DEB.year - 1)
            prev_end_full = DATE_FIN.replace(year=DATE_FIN.year - 1)
            cur.execute(f"""SELECT annee,semaine,SUM(COALESCE(pds_net,0)) as pds_kg,SUM(COALESCE(montant,0)) as ca
                FROM {table} WHERE type IN ('E','C') AND annee IS NOT NULL
                AND date_charg >= %s AND date_charg <= %s
                GROUP BY annee,semaine ORDER BY annee,semaine""", (prev_start_full, prev_end_full))
            r['par_semaine_n1_full'] = cur.fetchall()
        except: r['par_semaine_n1_full'] = []
        cur.close(); conn.close(); return r
    except Exception as e: st.error(str(e)); return None

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
        for k2,sql in {
            'par_fournisseur': f"SELECT apporteur,COUNT(*) as nb,SUM(COALESCE(pds_net,0)) as pds_kg,SUM(COALESCE(montant_euro,0)) as ca,AVG(prix_achat) FILTER (WHERE prix_achat>0) as prix_moy,COUNT(DISTINCT variete) as nb_varietes FROM frulog_lignes_achat WHERE 1=1{w} GROUP BY apporteur ORDER BY pds_kg DESC",
            'par_variete': f"SELECT variete,COUNT(*) as nb,SUM(COALESCE(pds_net,0)) as pds_kg,SUM(COALESCE(montant_euro,0)) as ca,COUNT(DISTINCT apporteur) as nb_fournisseurs,AVG(prix_achat) FILTER (WHERE prix_achat>0) as prix_moy FROM frulog_lignes_achat WHERE variete IS NOT NULL{w} GROUP BY variete ORDER BY pds_kg DESC",
            'par_mois': f"SELECT EXTRACT(YEAR FROM dt_chargmt)::int as annee,EXTRACT(MONTH FROM dt_chargmt)::int as mois,SUM(COALESCE(pds_net,0)) as pds_kg,SUM(COALESCE(montant_euro,0)) as ca FROM frulog_lignes_achat WHERE dt_chargmt IS NOT NULL{w} GROUP BY 1,2 ORDER BY annee,mois",
            'par_depot': f"SELECT depot,COUNT(*) as nb,SUM(COALESCE(pds_net,0)) as pds_kg,SUM(COALESCE(montant_euro,0)) as ca FROM frulog_lignes_achat WHERE depot IS NOT NULL{w} GROUP BY depot ORDER BY pds_kg DESC",
        }.items():
            cur.execute(sql); r[k2] = cur.fetchall()
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
            df['ecart_t'] = df['expedie_t'].astype(float)-df['prevu_t'].astype(float)
            df['taux'] = df.apply(lambda r: float(r['expedie_t'])/float(r['prevu_t'])*100 if float(r['prevu_t'])>0 else None, axis=1)
            return df
        return pd.DataFrame()
    except: return pd.DataFrame()


# ============================================================================
# HELPERS GRAPHIQUES AVEC ÉTIQUETTES + SPLY
# ============================================================================

def fmt_t(v):
    """Formatte un tonnage"""
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

def bar_with_labels(x, y, name=None, color='#1565C0', fmt_fn=None):
    """Crée une trace bar avec étiquettes"""
    texts = [fmt_fn(v) if fmt_fn else f"{float(v):,.0f}".replace(',', ' ') for v in y]
    return go.Bar(x=x, y=y, name=name, marker_color=color, text=texts, textposition='outside', textfont_size=10)


def render_kpis_sply(k, k_prev, label_prev, is_achat=False):
    """KPIs avec SPLY"""
    cols = st.columns(5)
    def show_metric(col, icon, name, val, val_prev, fmt_func=None):
        with col:
            if fmt_func:
                v_str = fmt_func(val)
            else:
                v_str = f"{int(val):,}".replace(',', ' ')
            delta = None; delta_color = "normal"
            if val_prev is not None and float(val_prev) > 0:
                p = pct_evol(val, val_prev)
                if p is not None:
                    delta = f"{p:+.1f}% vs {label_prev}"
            st.metric(f"{icon} {name}", v_str, delta=delta)

    pds = float(k['pds_kg'])/1000; pds_p = float(k_prev['pds_kg'])/1000 if k_prev else None
    ca = float(k['ca'])/1000; ca_p = float(k_prev['ca'])/1000 if k_prev else None

    if is_achat:
        show_metric(cols[0], "📋", "Lignes", k['total'], k_prev['total'] if k_prev else None)
        show_metric(cols[1], "⚖️", "Tonnage", pds, pds_p, fmt_t)
        show_metric(cols[2], "💰", "Montant", ca, ca_p, fmt_k)
        show_metric(cols[3], "🏭", "Fournisseurs", k['nb_fournisseurs'], k_prev['nb_fournisseurs'] if k_prev else None)
        show_metric(cols[4], "🥔", "Variétés", k['nb_varietes'], k_prev['nb_varietes'] if k_prev else None)
    else:
        show_metric(cols[0], "🚚", "Expéditions", k['nb_exp'], k_prev['nb_exp'] if k_prev else None)
        show_metric(cols[1], "⚖️", "Tonnage", pds, pds_p, fmt_t)
        show_metric(cols[2], "💰", "CA", ca, ca_p, fmt_k)
        show_metric(cols[3], "👥", "Clients", k['nb_clients'], k_prev['nb_clients'] if k_prev else None)
        show_metric(cols[4], "🥔", "Variétés", k['nb_varietes'], k_prev['nb_varietes'] if k_prev else None)

    if k.get('date_min') and k.get('date_max'):
        st.caption(f"📅 {k['date_min'].strftime('%d/%m/%Y')} → {k['date_max'].strftime('%d/%m/%Y')} — Prix moy : {float(k['prix_moy']):,.0f} €/T".replace(',', ' '))


def render_analyse_ventes(data, data_prev, label_prev, label, show_produit=False):
    if not data or not data.get('kpis') or data['kpis']['total'] == 0:
        st.info(f"📭 Aucune donnée {label} pour cette période")
        return
    k = data['kpis']; kp = data_prev['kpis'] if data_prev and data_prev.get('kpis') and data_prev['kpis']['total'] > 0 else None

    render_kpis_sply(k, kp, label_prev)
    if show_produit and k.get('mappees') is not None:
        tot = max(k['mappees']+k['non_mappees'], 1)
        st.caption(f"🔗 Mapping : {k['mappees']*100/tot:.0f}% ({k['mappees']}/{tot})")
    st.markdown("---")

    vues = ["📊 Vue d'ensemble","👥 Clients","🥔 Variétés","📦 Emballages","📏 Calibres","👤 Vendeurs"]
    if show_produit: vues.insert(3, "🏷️ Produits")
    vue = st.radio("Analyser :", vues, horizontal=True, key=f"vue_{label}")
    st.markdown("---")

    # Helper SPLY pour barres côte à côte
    def sply_bars(df_now, df_prev, x_col, y_col, title, color_now='#1565C0', color_prev='#FF9800', top_n=20, fmt_fn=None):
        df_n = df_now.head(top_n).copy()
        fig = go.Figure()
        if df_prev is not None and len(df_prev) > 0:
            df_p = pd.DataFrame(df_prev)
            # Calculer la valeur N-1 selon le type de y_col
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
            fig.add_trace(go.Bar(x=df_n[x_col], y=prev_vals, name=f"N-1", marker_color=color_prev,
                text=t_p, textposition='outside', textfont=dict(size=9, color='#E65100')))
        texts = [fmt_fn(v) if fmt_fn else f"{float(v):,.0f}".replace(',', ' ') for v in df_n[y_col]]
        fig.add_trace(go.Bar(x=df_n[x_col], y=df_n[y_col], name="Période", marker_color=color_now,
            text=texts, textposition='outside', textfont=dict(size=10, color='#0D47A1')))
        fig.update_layout(title=title, height=450, xaxis_tickangle=-45, barmode='group', legend=dict(orientation="h", yanchor="bottom", y=1.02))
        st.plotly_chart(fig, use_container_width=True)

    prev_data = lambda key: data_prev.get(key) if data_prev else None

    if vue == "📊 Vue d'ensemble":
        mois_noms = {1:'Jan',2:'Fév',3:'Mar',4:'Avr',5:'Mai',6:'Jun',7:'Jul',8:'Aoû',9:'Sep',10:'Oct',11:'Nov',12:'Déc'}
        if data['par_mois']:
            df_m = pd.DataFrame(data['par_mois']); df_m['tonnes'] = df_m['pds_kg'].astype(float)/1000
            # Agréger par mois (au cas où plusieurs années dans la période)
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
            # Ordre campagne : S23→S52 puis S01→S22
            ordre_sem = [f"S{i:02d}" for i in list(range(23,53)) + list(range(1,23))]
            fig = go.Figure()
            # Semaine courante ISO
            from datetime import date
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
            # Zone grisée après semaine courante (futur = SPLY only)
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
        # Pareto
        df_s = df.sort_values('ca', ascending=False).copy()
        df_s['pct'] = df_s['ca'].astype(float).cumsum()/max(df_s['ca'].astype(float).sum(),1)*100
        nb80 = len(df_s[df_s['pct']<=80])+1
        st.info(f"📊 **Pareto** : {nb80} clients = 80% du CA ({nb80*100//max(len(df),1)}% du portefeuille)")
        # Tableau avec évolution SPLY
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
        st.download_button(f"📥 Export {label}", buf.getvalue(), f"clients_{label}.xlsx", use_container_width=True)

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

    elif vue == "🏷️ Produits" and show_produit and data.get('par_produit'):
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


def render_analyse_achat(data, data_prev, label_prev):
    if not data or not data.get('kpis') or data['kpis']['total'] == 0:
        st.info("📭 Aucune donnée Achat pour cette période")
        return
    k = data['kpis']; kp = data_prev['kpis'] if data_prev and data_prev.get('kpis') and data_prev['kpis']['total']>0 else None
    render_kpis_sply(k, kp, label_prev, is_achat=True)
    st.markdown("---")
    vue = st.radio("Analyser :", ["📊 Vue d'ensemble","🏭 Fournisseurs","🥔 Variétés","🏢 Dépôts"], horizontal=True, key="vue_achat")
    st.markdown("---")

    prev_data = lambda key: data_prev.get(key) if data_prev else None

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
            pv = [pdict.get(x,0) for x in df_n[x_col]]
            fig.add_trace(go.Bar(x=df_n[x_col], y=pv, name="N-1", marker_color=color_prev,
                text=[fmt_fn(v) if fmt_fn and v else '' for v in pv], textposition='outside', textfont=dict(size=9, color='#1565C0')))
        texts = [fmt_fn(v) if fmt_fn else f"{float(v):,.0f}".replace(',', ' ') for v in df_n[y_col]]
        fig.add_trace(go.Bar(x=df_n[x_col], y=df_n[y_col], name="Période", marker_color=color_now,
            text=texts, textposition='outside', textfont=dict(size=10, color='#BF360C')))
        fig.update_layout(title=title, height=450, xaxis_tickangle=-45, barmode='group', legend=dict(orientation="h", yanchor="bottom", y=1.02))
        st.plotly_chart(fig, use_container_width=True)

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
        st.download_button("📥 Export", buf.getvalue(), f"fournisseurs.xlsx", use_container_width=True)

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
# ONGLETS
# ============================================================================

tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "📥 Import", "🔗 Mapping Produits", "📦 Mapping Sur-Emb.",
    "📈 Condi", "🏪 Négoce", "🛒 Achats"
])

# ============================================================================
# TAB 1 : IMPORT
# ============================================================================
with tab1:
    imp_type = st.radio("Type :", ["📈 Condi", "🏪 Négoce", "🛒 Achats"], horizontal=True, key="imp_type")
    st.markdown("---")

    if imp_type == "📈 Condi":
        up = st.file_uploader("Fichier Excel Ventes Condi", type=['xlsx','xls'], key="up_condi")
        if up:
            try:
                up.seek(0); dfc = pd.read_excel(up, sheet_name=0)
                c1,c2,c3,c4 = st.columns(4)
                with c1: st.metric("Lignes", len(dfc))
                with c2: st.metric("E", len(dfc[dfc['Type']=='E']) if 'Type' in dfc.columns else 0)
                with c3: st.metric("C", len(dfc[dfc['Type']=='C']) if 'Type' in dfc.columns else 0)
                with c4: st.metric("A", len(dfc[dfc['Type']=='A']) if 'Type' in dfc.columns else 0)
                st.dataframe(dfc.head(3), use_container_width=True, hide_index=True)
                if st.button("🚀 Importer CONDI", type="primary", use_container_width=True):
                    up.seek(0)
                    with st.spinner("Import..."): ok, msg = importer_ventes(up, 'CONDI', st.session_state.get('username','?'))
                    if ok: st.success(f"✅ {msg}"); st.rerun()
                    else: st.error(f"❌ {msg}")
            except Exception as e: st.error(str(e))

    elif imp_type == "🏪 Négoce":
        up = st.file_uploader("Fichier Excel Ventes Négoce", type=['xlsx','xls'], key="up_negoce")
        if up:
            try:
                up.seek(0); dfc = pd.read_excel(up, sheet_name=0)
                c1,c2 = st.columns(2)
                with c1: st.metric("Lignes", len(dfc))
                with c2: st.metric("E", len(dfc[dfc['Type']=='E']) if 'Type' in dfc.columns else 0)
                st.dataframe(dfc.head(3), use_container_width=True, hide_index=True)
                if st.button("🚀 Importer NÉGOCE", type="primary", use_container_width=True):
                    up.seek(0)
                    with st.spinner("Import..."): ok, msg = importer_ventes(up, 'NEGOCE', st.session_state.get('username','?'))
                    if ok: st.success(f"✅ {msg}"); st.rerun()
                    else: st.error(f"❌ {msg}")
            except Exception as e: st.error(str(e))

    else:
        up = st.file_uploader("Fichier Excel Achats", type=['xlsx','xls'], key="up_achat")
        if up:
            try:
                up.seek(0); dfc = pd.read_excel(up, sheet_name=0)
                c1,c2,c3 = st.columns(3)
                with c1: st.metric("Lignes", len(dfc))
                with c2: st.metric("S", len(dfc[dfc['Type']=='S']) if 'Type' in dfc.columns else 0)
                with c3: st.metric("A", len(dfc[dfc['Type']=='A']) if 'Type' in dfc.columns else 0)
                st.dataframe(dfc.head(3), use_container_width=True, hide_index=True)
                if st.button("🚀 Importer ACHATS", type="primary", use_container_width=True):
                    up.seek(0)
                    with st.spinner("Import..."): ok, msg = importer_achat(up, st.session_state.get('username','?'))
                    if ok: st.success(f"✅ {msg}"); st.rerun()
                    else: st.error(f"❌ {msg}")
            except Exception as e: st.error(str(e))

    st.markdown("---")
    st.markdown("##### 📋 Historique")
    dfi = get_imports()
    if not dfi.empty:
        cols_show = [c for c in ['id','source','nom_fichier','date_import','nb_lignes_total','nb_lignes_type_e','nb_lignes_type_a','date_debut','date_fin'] if c in dfi.columns]
        st.dataframe(dfi[cols_show].rename(columns={'id':'ID','source':'Type','nom_fichier':'Fichier','date_import':'Date',
            'nb_lignes_total':'Lignes','nb_lignes_type_e':'E/S','nb_lignes_type_a':'Avoirs','date_debut':'Début','date_fin':'Fin'}),
            use_container_width=True, hide_index=True)

# ============================================================================
# TAB 2 : MAPPING PRODUITS (INLINE)
# ============================================================================
with tab2:
    st.subheader("🔗 Mapping Emballage + Marque → Produit")
    st.caption("*Condi — cliquez une ligne pour mapper*")
    df_nm = get_combinaisons_non_mappees()
    produits = get_produits_commerciaux()
    if not df_nm.empty:
        st.markdown(f"##### ⚠️ {len(df_nm)} combinaison(s) non mappée(s)")
        event = st.dataframe(
            df_nm.rename(columns={'emballage':'Emballage','marque':'Marque','depot':'Dépôt','nb_lignes':'Lignes','tonnes':'Tonnes','nb_clients':'Clients'}),
            use_container_width=True, hide_index=True, on_select="rerun", selection_mode="single-row", key="tbl_nm",
            column_config={'Tonnes':st.column_config.NumberColumn(format="%.1f")})
        sel = event.selection.rows if hasattr(event, 'selection') else []
        if sel and produits:
            r = df_nm.iloc[sel[0]]
            st.markdown(f"**→ `{r['emballage']}` | `{r.get('marque','(vide)')}`** — {r['nb_lignes']} lignes, {float(r['tonnes']):.1f} T")
            pl = [f"{p['code_produit']} — {p['marque']} {p['libelle']}" for p in produits]
            pi = st.selectbox("Produit POMI", range(len(pl)), format_func=lambda i: pl[i], key="mp_sel")
            if st.button("💾 Enregistrer", type="primary", key="btn_mp"):
                ok, msg = sauver_mapping_produit(r['emballage'], r.get('marque'), produits[pi]['code_produit'])
                if ok: st.success(f"✅ {msg}"); st.rerun()
                else: st.error(f"❌ {msg}")
    else:
        st.success("✅ Tout est mappé pour cette période")
    st.markdown("---")
    st.markdown("##### 📋 Mappings existants")
    dfm = get_mapping_produit()
    if not dfm.empty:
        cols_show = ['emballage','marque','code_produit_commercial','libelle_produit']
        st.dataframe(dfm[cols_show].rename(columns={
            'emballage':'Emballage','marque':'Marque','code_produit_commercial':'Code','libelle_produit':'Libellé'}),
            use_container_width=True, hide_index=True)
        if is_admin():
            st.markdown("##### ✏️ Modifier / Supprimer un mapping (Admin)")
            mapping_labels = [f"{r['emballage']} | {r.get('marque','(vide)')} → {r['code_produit_commercial']}" for _, r in dfm.iterrows()]
            sel_idx = st.selectbox("Mapping à modifier", range(len(mapping_labels)), format_func=lambda i: mapping_labels[i], key="admin_mp_sel")
            sel_row = dfm.iloc[sel_idx]
            c_mod, c_del = st.columns(2)
            with c_mod:
                pl = [f"{p['code_produit']} — {p['marque']} {p['libelle']}" for p in produits] if produits else []
                if pl:
                    cur_idx = next((i for i, p in enumerate(produits) if p['code_produit'] == sel_row['code_produit_commercial']), 0)
                    new_pi = st.selectbox("Nouveau produit", range(len(pl)), index=cur_idx, format_func=lambda i: pl[i], key="admin_mp_new")
                    if st.button("✏️ Modifier", key="btn_mod_mp"):
                        ok, msg = modifier_mapping_produit(int(sel_row['id']), sel_row['emballage'], sel_row.get('marque'), produits[new_pi]['code_produit'])
                        if ok: st.success(f"✅ {msg}"); st.rerun()
                        else: st.error(f"❌ {msg}")
            with c_del:
                st.warning(f"Supprimer : **{sel_row['emballage']}** | **{sel_row.get('marque','(vide)')}**")
                if st.button("🗑️ Supprimer", type="secondary", key="btn_del_mp"):
                    ok, msg = supprimer_mapping_produit(int(sel_row['id']), sel_row['emballage'], sel_row.get('marque'))
                    if ok: st.success(f"✅ {msg}"); st.rerun()
                    else: st.error(f"❌ {msg}")

# ============================================================================
# TAB 3 : MAPPING SUR-EMBALLAGES (INLINE)
# ============================================================================
with tab3:
    st.subheader("📦 Mapping Emballage → Sur-Emballage")
    st.caption("*Condi — cliquez une ligne pour mapper*")
    df_nse = get_emballages_non_mappes_se()
    sur_embs = get_sur_emballages()
    if not df_nse.empty:
        st.markdown(f"##### ⚠️ {len(df_nse)} code(s) non associé(s)")
        ev = st.dataframe(
            df_nse.rename(columns={'code_emballage':'Code','nb_lignes':'Lignes','nb_col_total':'Colis'}),
            use_container_width=True, hide_index=True, on_select="rerun", selection_mode="single-row", key="tbl_se")
        ss = ev.selection.rows if hasattr(ev, 'selection') else []
        if ss and sur_embs:
            rs = df_nse.iloc[ss[0]]
            st.markdown(f"**→ `{rs['code_emballage']}`** — {rs['nb_lignes']} lignes")
            sl = [f"{s['libelle']} ({s['nb_uvc']} UVC)" for s in sur_embs]
            si = st.selectbox("Sur-emballage POMI", range(len(sl)), format_func=lambda i: sl[i], key="mse_sel")
            if st.button("💾 Enregistrer", type="primary", key="btn_se"):
                ok, msg = sauver_mapping_se(rs['code_emballage'], int(sur_embs[si]['id']))
                if ok: st.success(f"✅ {msg}"); st.rerun()
                else: st.error(f"❌ {msg}")
    else:
        st.success("✅ Tout est associé pour cette période")
    st.markdown("---")
    st.markdown("##### 📋 Associations")
    dfse = get_mapping_suremballage()
    if not dfse.empty:
        st.dataframe(dfse[['code_emballage','libelle_se','nb_uvc']].rename(columns={
            'code_emballage':'Code','libelle_se':'Sur-Emballage','nb_uvc':'UVC'}),
            use_container_width=True, hide_index=True)
        if is_admin():
            st.markdown("##### ✏️ Modifier / Supprimer une association (Admin)")
            se_labels = [f"{r['code_emballage']} → {r.get('libelle_se','?')}" for _, r in dfse.iterrows()]
            sel_se_idx = st.selectbox("Association à modifier", range(len(se_labels)), format_func=lambda i: se_labels[i], key="admin_se_sel")
            sel_se_row = dfse.iloc[sel_se_idx]
            c_mod2, c_del2 = st.columns(2)
            with c_mod2:
                if sur_embs:
                    sl2 = [f"{s['libelle']} ({s['nb_uvc']} UVC)" for s in sur_embs]
                    cur_se_idx = next((i for i, s in enumerate(sur_embs) if int(s['id']) == int(sel_se_row['sur_emballage_id'])), 0)
                    new_sei = st.selectbox("Nouveau sur-emballage", range(len(sl2)), index=cur_se_idx, format_func=lambda i: sl2[i], key="admin_se_new")
                    if st.button("✏️ Modifier", key="btn_mod_se"):
                        ok, msg = modifier_mapping_se(int(sel_se_row['id']), sel_se_row['code_emballage'], int(sur_embs[new_sei]['id']))
                        if ok: st.success(f"✅ {msg}"); st.rerun()
                        else: st.error(f"❌ {msg}")
            with c_del2:
                st.warning(f"Supprimer : **{sel_se_row['code_emballage']}**")
                if st.button("🗑️ Supprimer", type="secondary", key="btn_del_se"):
                    ok, msg = supprimer_mapping_se(int(sel_se_row['id']), sel_se_row['code_emballage'])
                    if ok: st.success(f"✅ {msg}"); st.rerun()
                    else: st.error(f"❌ {msg}")

# ============================================================================
# TAB 4 : CONDI
# ============================================================================
with tab4:
    st.subheader("📈 Conditionnement")
    sous = st.radio("", ["📊 Analyse","🎯 Prévu vs Réel"], horizontal=True, key="csous")
    st.markdown("---")
    if sous == "📊 Analyse":
        # Mode comparaison ?
        if COMP_DATES:
            la, d1a, d1b, lb, d2a, d2b = COMP_DATES
            st.info(f"🔀 Comparaison : **{la}** vs **{lb}**")
            data_a = get_analyse_ventes('frulog_lignes_condi', d1a, d1b)
            data_b = get_analyse_ventes('frulog_lignes_condi', d2a, d2b)
            render_analyse_ventes(data_a, data_b, lb, "condi", show_produit=True)
        else:
            # SPLY automatique — tronqué à aujourd'hui
            sp1, sp2, now1, now2 = sply_dates()
            data_now = get_analyse_ventes('frulog_lignes_condi', now1, now2) if now1 else get_analyse_ventes('frulog_lignes_condi')
            data_prev = get_analyse_ventes('frulog_lignes_condi', sp1, sp2) if sp1 else None
            label_prev = f"{sp1.strftime('%d/%m/%Y')}→{sp2.strftime('%d/%m/%Y')}" if sp1 else "N-1"
            render_analyse_ventes(data_now, data_prev, label_prev, "condi", show_produit=True)
    else:
        df_comp = get_comparaison_previsions()
        if not df_comp.empty:
            da = df_comp[df_comp['prevu_t'].astype(float)>0]
            tg = da['expedie_t'].astype(float).sum()/max(da['prevu_t'].astype(float).sum(),0.001)*100 if not da.empty else 0
            tp = df_comp['prevu_t'].astype(float).sum(); te = df_comp['expedie_t'].astype(float).sum()
            k1,k2,k3,k4 = st.columns(4)
            with k1: st.metric("Prévu", f"{tp:.1f} T")
            with k2: st.metric("Expédié", f"{te:.1f} T")
            with k3: st.metric("Écart", f"{te-tp:+.1f} T")
            with k4: st.metric("Réalisation", f"{tg:.0f}%")
            st.markdown("---")
            ds = df_comp.groupby(['annee','semaine']).agg(prevu=('prevu_t',lambda x:x.astype(float).sum()),expedie=('expedie_t',lambda x:x.astype(float).sum())).reset_index()
            ds['label'] = ds.apply(lambda r: f"S{int(r['semaine']):02d}", axis=1)
            fig = go.Figure()
            fig.add_trace(go.Bar(x=ds['label'], y=ds['prevu'], name='Prévu', marker_color='#90CAF9',
                text=[f"{v:.0f}" for v in ds['prevu']], textposition='outside', textfont_size=9))
            fig.add_trace(go.Bar(x=ds['label'], y=ds['expedie'], name='Expédié', marker_color='#1565C0',
                text=[f"{v:.0f}" for v in ds['expedie']], textposition='outside', textfont_size=9))
            fig.update_layout(barmode='group', title="Prévu vs Expédié (T)", height=400)
            st.plotly_chart(fig, use_container_width=True)
            ds['taux'] = ds.apply(lambda r: r['expedie']/r['prevu']*100 if r['prevu']>0 else None, axis=1)
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

# ============================================================================
# TAB 5 : NÉGOCE
# ============================================================================
with tab5:
    st.subheader("🏪 Négoce")
    if COMP_DATES:
        la, d1a, d1b, lb, d2a, d2b = COMP_DATES
        st.info(f"🔀 Comparaison : **{la}** vs **{lb}**")
        da = get_analyse_ventes('frulog_lignes_negoce', d1a, d1b)
        db = get_analyse_ventes('frulog_lignes_negoce', d2a, d2b)
        render_analyse_ventes(da, db, lb, "negoce")
    else:
        sp1, sp2, now1, now2 = sply_dates()
        dn = get_analyse_ventes('frulog_lignes_negoce', now1, now2) if now1 else get_analyse_ventes('frulog_lignes_negoce')
        dp = get_analyse_ventes('frulog_lignes_negoce', sp1, sp2) if sp1 else None
        lp = f"{sp1.strftime('%d/%m/%Y')}→{sp2.strftime('%d/%m/%Y')}" if sp1 else "N-1"
        render_analyse_ventes(dn, dp, lp, "negoce")

# ============================================================================
# TAB 6 : ACHATS
# ============================================================================
with tab6:
    st.subheader("🛒 Achats")
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
