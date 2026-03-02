import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, date
from database import get_connection
from components import show_footer
from auth import require_access
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
st.caption("*Conditionnement, Négoce & Achats*")

# ============================================================================
# FILTRE CAMPAGNE GLOBAL
# ============================================================================

def get_campagnes():
    """Génère la liste des campagnes : Campagne YYYY = 01/06/YYYY-1 au 31/05/YYYY"""
    now = datetime.now()
    current_year = now.year if now.month >= 6 else now.year - 1
    # Campagne en cours = current_year+1 (ex: si on est en mars 2026, campagne 2026 = juin 2025 → mai 2026)
    current_camp = current_year + 1
    camps = []
    for y in range(current_camp + 1, 2022, -1):  # future + actuelle + historique
        camps.append(y)
    return camps

def campagne_dates(year):
    """Retourne (date_debut, date_fin) pour une campagne"""
    return date(year - 1, 6, 1), date(year, 5, 31)

campagnes = get_campagnes()
camp_labels = {y: f"Campagne {y} ({y-1}/06 → {y}/05)" for y in campagnes}
camp_labels[0] = "🔓 Toutes les campagnes"

fc1, fc2 = st.columns([3, 1])
with fc1:
    sel_camp = st.selectbox("🗓️ Campagne", [0] + campagnes,
                           format_func=lambda y: camp_labels.get(y, str(y)),
                           key="filtre_campagne")
with fc2:
    if sel_camp:
        d1, d2 = campagne_dates(sel_camp)
        st.info(f"📅 {d1.strftime('%d/%m/%Y')} → {d2.strftime('%d/%m/%Y')}")
    else:
        st.info("📅 Aucun filtre de date")

# Variables globales de filtre
CAMP_DATE_MIN = campagne_dates(sel_camp)[0] if sel_camp else None
CAMP_DATE_MAX = campagne_dates(sel_camp)[1] if sel_camp else None

st.markdown("---")

# ============================================================================
# CONSTANTES — Mapping colonnes
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


def make_cle_produit(emballage, marque):
    e = str(emballage).strip().upper() if emballage and str(emballage).strip() != '.' else ''
    m = str(marque).strip().upper() if marque and str(marque).strip() != '.' else ''
    return f"{e}|{m}"


def to_python(val):
    if val is None or (isinstance(val, float) and np.isnan(val)) or val is pd.NaT:
        return None
    elif isinstance(val, (np.integer, np.int64)):
        return int(val)
    elif isinstance(val, (np.floating, np.float64)):
        return float(val)
    return val


def clean_text(x):
    if pd.isna(x) or str(x).strip() == '.':
        return None
    return str(x).strip()


def camp_where_ventes(prefix="", extra_and=True):
    """Génère la clause WHERE de campagne pour tables ventes (date_charg)"""
    if not CAMP_DATE_MIN:
        return ""
    p = f"{prefix}." if prefix else ""
    clause = f"{p}date_charg >= '{CAMP_DATE_MIN}' AND {p}date_charg <= '{CAMP_DATE_MAX}'"
    return f" AND {clause}" if extra_and else f" WHERE {clause}"


def camp_where_achat(prefix="", extra_and=True):
    """Génère la clause WHERE de campagne pour table achat (dt_chargmt)"""
    if not CAMP_DATE_MIN:
        return ""
    p = f"{prefix}." if prefix else ""
    clause = f"{p}dt_chargmt >= '{CAMP_DATE_MIN}' AND {p}dt_chargmt <= '{CAMP_DATE_MAX}'"
    return f" AND {clause}" if extra_and else f" WHERE {clause}"


# ============================================================================
# FONCTIONS BDD
# ============================================================================

def get_imports(source=None):
    try:
        conn = get_connection(); cursor = conn.cursor()
        where = f"WHERE source='{source}'" if source else ""
        cursor.execute(f"SELECT * FROM frulog_imports {where} ORDER BY date_import DESC LIMIT 50")
        rows = cursor.fetchall(); cursor.close(); conn.close()
        return pd.DataFrame(rows) if rows else pd.DataFrame()
    except: return pd.DataFrame()

def get_mapping_produit():
    try:
        conn = get_connection(); cursor = conn.cursor()
        cursor.execute("""SELECT fm.*, pc.libelle as libelle_produit, pc.marque as marque_produit
            FROM frulog_mapping_produit fm
            LEFT JOIN ref_produits_commerciaux pc ON fm.code_produit_commercial = pc.code_produit
            WHERE fm.is_active = TRUE ORDER BY fm.emballage, fm.marque""")
        rows = cursor.fetchall(); cursor.close(); conn.close()
        return pd.DataFrame(rows) if rows else pd.DataFrame()
    except: return pd.DataFrame()

def get_mapping_suremballage():
    try:
        conn = get_connection(); cursor = conn.cursor()
        cursor.execute("""SELECT fms.*, se.libelle as libelle_se, se.nb_uvc
            FROM frulog_mapping_suremballage fms
            LEFT JOIN ref_sur_emballages se ON fms.sur_emballage_id = se.id
            WHERE fms.is_active = TRUE ORDER BY fms.code_emballage""")
        rows = cursor.fetchall(); cursor.close(); conn.close()
        return pd.DataFrame(rows) if rows else pd.DataFrame()
    except: return pd.DataFrame()

def get_produits_commerciaux():
    try:
        conn = get_connection(); cursor = conn.cursor()
        cursor.execute("SELECT code_produit, marque, libelle FROM ref_produits_commerciaux WHERE is_active=TRUE ORDER BY marque, libelle")
        rows = cursor.fetchall(); cursor.close(); conn.close()
        return rows or []
    except: return []

def get_sur_emballages():
    try:
        conn = get_connection(); cursor = conn.cursor()
        cursor.execute("SELECT id, libelle, nb_uvc FROM ref_sur_emballages WHERE is_active=TRUE ORDER BY libelle")
        rows = cursor.fetchall(); cursor.close(); conn.close()
        return rows or []
    except: return []

def get_combinaisons_non_mappees_produit():
    try:
        conn = get_connection(); cursor = conn.cursor()
        cursor.execute(f"""SELECT fl.emballage, fl.marque, COUNT(*) as nb_lignes,
                   SUM(ABS(COALESCE(fl.pds_net, 0))) as pds_total_kg,
                   COUNT(DISTINCT fl.client) as nb_clients
            FROM frulog_lignes_condi fl
            WHERE fl.type = 'E' AND fl.code_produit_commercial IS NULL
            AND fl.emballage IS NOT NULL {camp_where_ventes('fl')}
            GROUP BY fl.emballage, fl.marque ORDER BY nb_lignes DESC""")
        rows = cursor.fetchall(); cursor.close(); conn.close()
        return pd.DataFrame(rows) if rows else pd.DataFrame()
    except: return pd.DataFrame()

def get_emballages_non_mappes_se():
    try:
        conn = get_connection(); cursor = conn.cursor()
        cursor.execute(f"""SELECT fl.emballage as code_emballage, COUNT(*) as nb_lignes,
                   SUM(COALESCE(fl.nb_col, 0)) as nb_col_total
            FROM frulog_lignes_condi fl
            WHERE fl.type = 'E' AND fl.sur_emballage_id IS NULL
            AND fl.emballage IS NOT NULL {camp_where_ventes('fl')}
            GROUP BY fl.emballage ORDER BY nb_lignes DESC""")
        rows = cursor.fetchall(); cursor.close(); conn.close()
        return pd.DataFrame(rows) if rows else pd.DataFrame()
    except: return pd.DataFrame()

def sauver_mapping_produit(emballage, marque, code_produit, description=None):
    try:
        conn = get_connection(); cursor = conn.cursor()
        cle = make_cle_produit(emballage, marque)
        cursor.execute("""INSERT INTO frulog_mapping_produit (emballage, marque, cle_mapping, code_produit_commercial, description)
            VALUES (%s,%s,%s,%s,%s) ON CONFLICT (cle_mapping) DO UPDATE SET
            code_produit_commercial=EXCLUDED.code_produit_commercial, description=EXCLUDED.description, updated_at=CURRENT_TIMESTAMP
            RETURNING id""", (emballage, marque, cle, code_produit, description))
        mid = cursor.fetchone()['id']
        # MAJ toutes les lignes condi avec cette combinaison (pas que campagne)
        cursor.execute("""UPDATE frulog_lignes_condi SET code_produit_commercial=%s
            WHERE emballage=%s AND (marque=%s OR (%s IS NULL AND marque IS NULL))
            AND code_produit_commercial IS NULL""", (code_produit, emballage, marque, marque))
        updated = cursor.rowcount
        conn.commit(); cursor.close(); conn.close()
        return True, f"Mapping #{mid} OK ({updated} lignes mises à jour)"
    except Exception as e:
        if 'conn' in locals(): conn.rollback()
        return False, str(e)

def sauver_mapping_suremballage(code_emballage, sur_emballage_id, description=None):
    try:
        conn = get_connection(); cursor = conn.cursor()
        cursor.execute("""INSERT INTO frulog_mapping_suremballage (code_emballage, sur_emballage_id, description)
            VALUES (%s,%s,%s) ON CONFLICT (code_emballage) DO UPDATE SET
            sur_emballage_id=EXCLUDED.sur_emballage_id, description=EXCLUDED.description, updated_at=CURRENT_TIMESTAMP
            RETURNING id""", (code_emballage, sur_emballage_id, description))
        mid = cursor.fetchone()['id']
        cursor.execute("UPDATE frulog_lignes_condi SET sur_emballage_id=%s WHERE emballage=%s AND sur_emballage_id IS NULL",
                       (sur_emballage_id, code_emballage))
        updated = cursor.rowcount
        conn.commit(); cursor.close(); conn.close()
        return True, f"Mapping S-E #{mid} OK ({updated} lignes)"
    except Exception as e:
        if 'conn' in locals(): conn.rollback()
        return False, str(e)


# ============================================================================
# IMPORT VENTES (CONDI / NEGOCE)
# ============================================================================

def importer_ventes(uploaded_file, source, username='inconnu'):
    table = f"frulog_lignes_{source.lower()}"
    try:
        df = pd.read_excel(uploaded_file, sheet_name=0)
        if len(df) == 0: return False, "Fichier vide"
        df_r = df.rename(columns=COLONNES_VENTES)
        known = list(COLONNES_VENTES.values())
        cols_ok = [c for c in known if c in df_r.columns]
        df_c = df_r[cols_ok].copy()
        if 'no_de_bon' not in df_c.columns: return False, "Colonne 'No de bon' introuvable"
        if 'type' in df_c.columns:
            df_c = df_c[df_c['type'].isin(['E', 'A'])].copy()
        for col in VENTES_DATE_COLS:
            if col in df_c.columns: df_c[col] = pd.to_datetime(df_c[col], errors='coerce').dt.date
        for col in VENTES_INT_COLS:
            if col in df_c.columns: df_c[col] = pd.to_numeric(df_c[col], errors='coerce')
        for col in VENTES_NUM_COLS:
            if col in df_c.columns: df_c[col] = pd.to_numeric(df_c[col], errors='coerce')
        for col in ['type','produit','variete','categ','calibre','couleur','emballage','marque','client','depot']:
            if col in df_c.columns: df_c[col] = df_c[col].apply(clean_text)
        if 'date_charg' in df_c.columns:
            df_c['annee'] = df_c['date_charg'].apply(lambda d: d.isocalendar()[0] if pd.notna(d) and d is not None else None)
            df_c['semaine'] = df_c['date_charg'].apply(lambda d: d.isocalendar()[1] if pd.notna(d) and d is not None else None)
        conn = get_connection(); cursor = conn.cursor()
        nb_total = len(df_c)
        nb_e = len(df_c[df_c.get('type', pd.Series()) == 'E']) if 'type' in df_c.columns else 0
        nb_a = len(df_c[df_c.get('type', pd.Series()) == 'A']) if 'type' in df_c.columns else 0
        d_min = df_c['date_charg'].dropna().min() if 'date_charg' in df_c.columns else None
        d_max = df_c['date_charg'].dropna().max() if 'date_charg' in df_c.columns else None
        cursor.execute("""INSERT INTO frulog_imports (nom_fichier, source, nb_lignes_total, nb_lignes_type_e,
            nb_lignes_type_a, nb_lignes_sans_type, date_debut, date_fin, created_by)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id""",
            (uploaded_file.name, source, nb_total, nb_e, nb_a, nb_total-nb_e-nb_a, d_min, d_max, username))
        import_id = cursor.fetchone()['id']
        map_produit = {}; map_se = {}
        if source == 'CONDI':
            cursor.execute("SELECT cle_mapping, code_produit_commercial FROM frulog_mapping_produit WHERE is_active=TRUE")
            map_produit = {r['cle_mapping']: r['code_produit_commercial'] for r in cursor.fetchall()}
            cursor.execute("SELECT code_emballage, sur_emballage_id FROM frulog_mapping_suremballage WHERE is_active=TRUE")
            map_se = {r['code_emballage']: r['sur_emballage_id'] for r in cursor.fetchall()}
        if map_produit:
            df_c['code_produit_commercial'] = df_c.apply(
                lambda r: map_produit.get(make_cle_produit(r.get('emballage'), r.get('marque'))), axis=1)
        if map_se:
            df_c['sur_emballage_id'] = df_c['emballage'].apply(
                lambda e: map_se.get(str(e).strip().upper()) if e and str(e).strip() != '.' else None)
        cursor.execute(f"SELECT no_de_bon, etat, pds_net, montant, type, nb_col FROM {table} WHERE no_de_bon IS NOT NULL")
        existing = {r['no_de_bon']: r for r in cursor.fetchall()}
        data_cols = [c for c in cols_ok if c != 'no_de_bon'] + ['annee', 'semaine']
        if source == 'CONDI': data_cols += ['code_produit_commercial', 'sur_emballage_id']
        data_cols = list(dict.fromkeys(data_cols))
        compare_keys = ['etat', 'pds_net', 'montant', 'type', 'nb_col']
        nb_new = nb_updated = nb_unchanged = 0
        for _, row in df_c.iterrows():
            bon = to_python(row.get('no_de_bon'))
            if not bon: continue
            rv = {col: to_python(row.get(col)) for col in data_cols}
            if bon in existing:
                ex = existing[bon]
                if any(str(to_python(row.get(k))) != str(ex.get(k)) for k in compare_keys):
                    sp = [f"{col}=%s" for col in data_cols] + ["import_id=%s"]
                    vals = [rv[col] for col in data_cols] + [import_id, bon]
                    cursor.execute(f"UPDATE {table} SET {', '.join(sp)} WHERE no_de_bon=%s", vals)
                    nb_updated += 1
                else: nb_unchanged += 1
            else:
                ac = ['import_id', 'no_de_bon'] + data_cols
                av = [import_id, bon] + [rv[col] for col in data_cols]
                cursor.execute(f"INSERT INTO {table} ({', '.join(ac)}) VALUES ({', '.join(['%s']*len(ac))})", av)
                nb_new += 1
        conn.commit()
        nb_mapped = df_c['code_produit_commercial'].notna().sum() if 'code_produit_commercial' in df_c.columns else 0
        cursor.close(); conn.close()
        m = f" {nb_mapped}/{nb_total} mappées." if source == 'CONDI' else ""
        return True, f"Import #{import_id} ({source}) : {nb_total} lignes → **{nb_new} nouvelles**, **{nb_updated} modifiées**, {nb_unchanged} inchangées.{m}"
    except Exception as e:
        if 'conn' in locals(): conn.rollback()
        return False, f"Erreur : {str(e)}"


# ============================================================================
# IMPORT ACHAT
# ============================================================================

def importer_achat(uploaded_file, username='inconnu'):
    try:
        df = pd.read_excel(uploaded_file, sheet_name=0)
        if len(df) == 0: return False, "Fichier vide"
        df_r = df.rename(columns=COLONNES_ACHAT)
        known = list(COLONNES_ACHAT.values())
        cols_ok = [c for c in known if c in df_r.columns]
        df_c = df_r[cols_ok].copy()
        if 'no_de_bon' not in df_c.columns: return False, "Colonne 'No de Bon' introuvable"
        for col in ACHAT_DATE_COLS:
            if col in df_c.columns: df_c[col] = pd.to_datetime(df_c[col], errors='coerce').dt.date
        for col in ACHAT_INT_COLS:
            if col in df_c.columns: df_c[col] = pd.to_numeric(df_c[col], errors='coerce')
        for col in ACHAT_NUM_COLS:
            if col in df_c.columns: df_c[col] = pd.to_numeric(df_c[col], errors='coerce')
        for col in ['vendeur','apporteur','produit','variete','emballage','marque','depot','calibre','type']:
            if col in df_c.columns: df_c[col] = df_c[col].apply(clean_text)
        date_col = 'dt_chargmt' if 'dt_chargmt' in df_c.columns else 'date_du_bon'
        if date_col in df_c.columns:
            df_c['annee'] = df_c[date_col].apply(lambda d: d.isocalendar()[0] if pd.notna(d) and d is not None else None)
            df_c['semaine'] = df_c[date_col].apply(lambda d: d.isocalendar()[1] if pd.notna(d) and d is not None else None)
        conn = get_connection(); cursor = conn.cursor()
        nb_total = len(df_c)
        nb_s = len(df_c[df_c.get('type', pd.Series()) == 'S']) if 'type' in df_c.columns else 0
        nb_a = len(df_c[df_c.get('type', pd.Series()) == 'A']) if 'type' in df_c.columns else 0
        d_min = df_c[date_col].dropna().min() if date_col in df_c.columns else None
        d_max = df_c[date_col].dropna().max() if date_col in df_c.columns else None
        cursor.execute("""INSERT INTO frulog_imports (nom_fichier, source, nb_lignes_total, nb_lignes_type_e,
            nb_lignes_type_a, nb_lignes_sans_type, date_debut, date_fin, created_by)
            VALUES (%s,'ACHAT',%s,%s,%s,%s,%s,%s,%s) RETURNING id""",
            (uploaded_file.name, nb_total, nb_s, nb_a, nb_total-nb_s-nb_a, d_min, d_max, username))
        import_id = cursor.fetchone()['id']
        cursor.execute("SELECT no_de_bon, etat, pds_net, montant_euro, type FROM frulog_lignes_achat WHERE no_de_bon IS NOT NULL")
        existing = {str(r['no_de_bon']): r for r in cursor.fetchall()}
        data_cols = [c for c in cols_ok if c != 'no_de_bon'] + ['annee', 'semaine']
        data_cols = list(dict.fromkeys(data_cols))
        compare_keys = ['etat', 'pds_net', 'montant_euro', 'type']
        nb_new = nb_updated = nb_unchanged = 0
        for _, row in df_c.iterrows():
            bon = str(to_python(row.get('no_de_bon')))
            if not bon or bon == 'None': continue
            rv = {col: to_python(row.get(col)) for col in data_cols}
            if bon in existing:
                ex = existing[bon]
                if any(str(to_python(row.get(k))) != str(ex.get(k)) for k in compare_keys):
                    sp = [f"{col}=%s" for col in data_cols] + ["import_id=%s"]
                    vals = [rv[col] for col in data_cols] + [import_id, bon]
                    cursor.execute(f"UPDATE frulog_lignes_achat SET {', '.join(sp)} WHERE no_de_bon=%s", vals)
                    nb_updated += 1
                else: nb_unchanged += 1
            else:
                ac = ['import_id', 'no_de_bon'] + data_cols
                av = [import_id, bon] + [rv[col] for col in data_cols]
                cursor.execute(f"INSERT INTO frulog_lignes_achat ({', '.join(ac)}) VALUES ({', '.join(['%s']*len(ac))})", av)
                nb_new += 1
        conn.commit(); cursor.close(); conn.close()
        return True, f"Import #{import_id} (ACHAT) : {nb_total} lignes → **{nb_new} nouvelles**, **{nb_updated} modifiées**, {nb_unchanged} inchangées."
    except Exception as e:
        if 'conn' in locals(): conn.rollback()
        return False, f"Erreur : {str(e)}"


# ============================================================================
# ANALYSE VENTES
# ============================================================================

def get_analyse_ventes(table):
    try:
        conn = get_connection(); cursor = conn.cursor()
        cw = camp_where_ventes()
        r = {}
        cursor.execute(f"""SELECT COUNT(*) as total, COUNT(*) FILTER (WHERE type='E') as nb_exp,
            COUNT(DISTINCT client) FILTER (WHERE type='E') as nb_clients,
            COALESCE(SUM(pds_net) FILTER (WHERE type='E'), 0) as pds_kg,
            COALESCE(SUM(montant) FILTER (WHERE type='E'), 0) as ca,
            COALESCE(AVG(prix) FILTER (WHERE type='E' AND prix > 0), 0) as prix_moy,
            COUNT(DISTINCT variete) FILTER (WHERE type='E') as nb_varietes,
            MIN(date_charg) FILTER (WHERE type='E') as date_min,
            MAX(date_charg) FILTER (WHERE type='E') as date_max,
            COUNT(*) FILTER (WHERE code_produit_commercial IS NOT NULL AND type='E') as mappees,
            COUNT(*) FILTER (WHERE code_produit_commercial IS NULL AND type='E') as non_mappees
            FROM {table} WHERE 1=1 {cw}""")
        r['kpis'] = cursor.fetchone()
        for key, sql in [
            ('par_client', f"SELECT client, COUNT(*) as nb, SUM(COALESCE(pds_net,0)) as pds_kg, SUM(COALESCE(montant,0)) as ca, AVG(prix) FILTER (WHERE prix>0) as prix_moy, MIN(date_charg) as premiere, MAX(date_charg) as derniere FROM {table} WHERE type='E' {cw} GROUP BY client ORDER BY pds_kg DESC"),
            ('par_variete', f"SELECT variete, COUNT(*) as nb, SUM(COALESCE(pds_net,0)) as pds_kg, SUM(COALESCE(montant,0)) as ca, COUNT(DISTINCT client) as nb_clients, AVG(prix) FILTER (WHERE prix>0) as prix_moy FROM {table} WHERE type='E' AND variete IS NOT NULL {cw} GROUP BY variete ORDER BY pds_kg DESC"),
            ('par_mois', f"SELECT EXTRACT(YEAR FROM date_charg)::int as annee, EXTRACT(MONTH FROM date_charg)::int as mois, SUM(COALESCE(pds_net,0)) as pds_kg, SUM(COALESCE(montant,0)) as ca FROM {table} WHERE type='E' AND date_charg IS NOT NULL {cw} GROUP BY 1,2 ORDER BY annee, mois"),
            ('par_semaine', f"SELECT annee, semaine, SUM(COALESCE(pds_net,0)) as pds_kg, SUM(COALESCE(montant,0)) as ca, COUNT(DISTINCT client) as nb_clients FROM {table} WHERE type='E' AND annee IS NOT NULL {cw} GROUP BY annee, semaine ORDER BY annee, semaine"),
            ('par_produit', f"SELECT COALESCE(code_produit_commercial, '❓ Non mappé') as produit, COUNT(*) as nb, SUM(COALESCE(pds_net,0)) as pds_kg, SUM(COALESCE(montant,0)) as ca FROM {table} WHERE type='E' {cw} GROUP BY 1 ORDER BY pds_kg DESC"),
            ('par_emballage', f"SELECT emballage, COUNT(*) as nb, SUM(COALESCE(pds_net,0)) as pds_kg FROM {table} WHERE type='E' AND emballage IS NOT NULL {cw} GROUP BY emballage ORDER BY pds_kg DESC"),
            ('par_calibre', f"SELECT calibre, COUNT(*) as nb, SUM(COALESCE(pds_net,0)) as pds_kg, COUNT(DISTINCT client) as nb_clients FROM {table} WHERE type='E' AND calibre IS NOT NULL {cw} GROUP BY calibre ORDER BY pds_kg DESC"),
            ('par_vendeur', f"SELECT vendeur, SUM(COALESCE(pds_net,0)) as pds_kg, SUM(COALESCE(montant,0)) as ca, COUNT(DISTINCT client) as nb_clients FROM {table} WHERE type='E' AND vendeur IS NOT NULL {cw} GROUP BY vendeur ORDER BY ca DESC"),
            ('par_annee', f"SELECT EXTRACT(YEAR FROM date_charg)::int as annee, SUM(COALESCE(pds_net,0)) as pds_kg, SUM(COALESCE(montant,0)) as ca, COUNT(DISTINCT client) as nb_clients, COUNT(*) as nb FROM {table} WHERE type='E' AND date_charg IS NOT NULL {cw} GROUP BY 1 ORDER BY annee"),
        ]:
            cursor.execute(sql); r[key] = cursor.fetchall()
        cursor.close(); conn.close()
        return r
    except Exception as e:
        st.error(f"Erreur : {str(e)}"); return None


def get_analyse_achat():
    try:
        conn = get_connection(); cursor = conn.cursor()
        cw = camp_where_achat()
        r = {}
        cursor.execute(f"""SELECT COUNT(*) as total, COUNT(DISTINCT apporteur) as nb_fournisseurs,
            COALESCE(SUM(pds_net), 0) as pds_kg, COALESCE(SUM(montant_euro), 0) as ca,
            COALESCE(AVG(prix_achat) FILTER (WHERE prix_achat > 0), 0) as prix_moy,
            COUNT(DISTINCT variete) as nb_varietes,
            MIN(dt_chargmt) as date_min, MAX(dt_chargmt) as date_max
            FROM frulog_lignes_achat WHERE 1=1 {cw}""")
        r['kpis'] = cursor.fetchone()
        for key, sql in [
            ('par_fournisseur', f"SELECT apporteur, COUNT(*) as nb, SUM(COALESCE(pds_net,0)) as pds_kg, SUM(COALESCE(montant_euro,0)) as ca, AVG(prix_achat) FILTER (WHERE prix_achat>0) as prix_moy, COUNT(DISTINCT variete) as nb_varietes FROM frulog_lignes_achat WHERE 1=1 {cw} GROUP BY apporteur ORDER BY pds_kg DESC"),
            ('par_variete', f"SELECT variete, COUNT(*) as nb, SUM(COALESCE(pds_net,0)) as pds_kg, SUM(COALESCE(montant_euro,0)) as ca, COUNT(DISTINCT apporteur) as nb_fournisseurs, AVG(prix_achat) FILTER (WHERE prix_achat>0) as prix_moy FROM frulog_lignes_achat WHERE variete IS NOT NULL {cw} GROUP BY variete ORDER BY pds_kg DESC"),
            ('par_mois', f"SELECT EXTRACT(YEAR FROM dt_chargmt)::int as annee, EXTRACT(MONTH FROM dt_chargmt)::int as mois, SUM(COALESCE(pds_net,0)) as pds_kg, SUM(COALESCE(montant_euro,0)) as ca FROM frulog_lignes_achat WHERE dt_chargmt IS NOT NULL {cw} GROUP BY 1,2 ORDER BY annee, mois"),
            ('par_depot', f"SELECT depot, COUNT(*) as nb, SUM(COALESCE(pds_net,0)) as pds_kg, SUM(COALESCE(montant_euro,0)) as ca FROM frulog_lignes_achat WHERE depot IS NOT NULL {cw} GROUP BY depot ORDER BY pds_kg DESC"),
            ('par_annee', f"SELECT EXTRACT(YEAR FROM dt_chargmt)::int as annee, SUM(COALESCE(pds_net,0)) as pds_kg, SUM(COALESCE(montant_euro,0)) as ca, COUNT(DISTINCT apporteur) as nb_fournisseurs, COUNT(*) as nb FROM frulog_lignes_achat WHERE dt_chargmt IS NOT NULL {cw} GROUP BY 1 ORDER BY annee"),
        ]:
            cursor.execute(sql); r[key] = cursor.fetchall()
        cursor.close(); conn.close()
        return r
    except Exception as e:
        st.error(f"Erreur : {str(e)}"); return None


def get_comparaison_previsions():
    try:
        conn = get_connection(); cursor = conn.cursor()
        cw = camp_where_ventes()
        cursor.execute(f"""WITH expedie AS (
                SELECT code_produit_commercial, annee, semaine, SUM(pds_net)/1000.0 as tonnes_exp
                FROM frulog_lignes_condi WHERE type='E' AND code_produit_commercial IS NOT NULL {cw}
                GROUP BY code_produit_commercial, annee, semaine),
            prevu AS (SELECT code_produit_commercial, annee::int, semaine::int, quantite_prevue_tonnes as tonnes_prev FROM previsions_ventes)
            SELECT COALESCE(e.code_produit_commercial, p.code_produit_commercial) as produit,
                   COALESCE(e.annee, p.annee) as annee, COALESCE(e.semaine, p.semaine) as semaine,
                   COALESCE(p.tonnes_prev, 0) as prevu_t, COALESCE(e.tonnes_exp, 0) as expedie_t
            FROM expedie e FULL OUTER JOIN prevu p
                ON e.code_produit_commercial=p.code_produit_commercial AND e.annee=p.annee AND e.semaine=p.semaine
            WHERE COALESCE(e.annee, p.annee) IS NOT NULL ORDER BY 2, 3""")
        rows = cursor.fetchall(); cursor.close(); conn.close()
        if rows:
            df = pd.DataFrame(rows)
            df['ecart_t'] = df['expedie_t'].astype(float) - df['prevu_t'].astype(float)
            df['taux'] = df.apply(lambda r: (float(r['expedie_t'])/float(r['prevu_t'])*100) if float(r['prevu_t'])>0 else None, axis=1)
            return df
        return pd.DataFrame()
    except: return pd.DataFrame()


# ============================================================================
# HELPER ANALYSE UI
# ============================================================================

def render_analyse_ventes(data, label, show_produit=False):
    if not data or not data.get('kpis') or not data['kpis'] or data['kpis']['total'] == 0:
        st.info(f"📭 Aucune donnée {label}" + (" pour cette campagne" if sel_camp else ""))
        return
    k = data['kpis']
    c1, c2, c3, c4, c5 = st.columns(5)
    with c1: st.metric("🚚 Expéditions", f"{k['nb_exp']:,}".replace(',', ' '))
    with c2: st.metric("⚖️ Tonnage", f"{float(k['pds_kg'])/1000:,.0f} T".replace(',', ' '))
    with c3: st.metric("💰 CA", f"{float(k['ca'])/1000:,.0f} k€".replace(',', ' '))
    with c4: st.metric("👥 Clients", k['nb_clients'])
    with c5: st.metric("🥔 Variétés", k['nb_varietes'])
    if k['date_min'] and k['date_max']:
        st.caption(f"📅 {k['date_min'].strftime('%d/%m/%Y')} → {k['date_max'].strftime('%d/%m/%Y')} — Prix moy : {float(k['prix_moy']):,.0f} €/T".replace(',', ' '))
    if show_produit and k.get('mappees') is not None:
        tot = max(k['mappees'] + k['non_mappees'], 1)
        st.caption(f"🔗 Mapping : {k['mappees']*100/tot:.0f}% ({k['mappees']}/{tot})")
    st.markdown("---")
    vues = ["📊 Vue d'ensemble", "👥 Clients", "🥔 Variétés", "📦 Emballages", "📏 Calibres", "👤 Vendeurs"]
    if show_produit: vues.insert(3, "🏷️ Produits")
    vue = st.radio("Analyser par :", vues, horizontal=True, key=f"vue_{label}")
    st.markdown("---")

    if vue == "📊 Vue d'ensemble":
        if data['par_annee']:
            df_a = pd.DataFrame(data['par_annee']); df_a['tonnes'] = df_a['pds_kg'].astype(float)/1000; df_a['ca_k'] = df_a['ca'].astype(float)/1000
            ga1, ga2 = st.columns(2)
            with ga1:
                fig = go.Figure([go.Bar(x=df_a['annee'].astype(str), y=df_a['tonnes'], marker_color='#1565C0')])
                fig.update_layout(title="Tonnage / année", height=350); st.plotly_chart(fig, use_container_width=True)
            with ga2:
                fig = go.Figure([go.Bar(x=df_a['annee'].astype(str), y=df_a['ca_k'], marker_color='#2E7D32')])
                fig.update_layout(title="CA / année (k€)", height=350); st.plotly_chart(fig, use_container_width=True)
        if data['par_mois']:
            df_m = pd.DataFrame(data['par_mois']); df_m['tonnes'] = df_m['pds_kg'].astype(float)/1000
            df_m['label'] = df_m.apply(lambda r: f"{int(r['mois']):02d}/{int(r['annee'])}", axis=1)
            fig = go.Figure([go.Scatter(x=df_m['label'], y=df_m['tonnes'], mode='lines+markers', line=dict(color='#1565C0', width=2), fill='tozeroy')])
            fig.update_layout(title="Tonnage mensuel", height=400, xaxis=dict(tickangle=-45)); st.plotly_chart(fig, use_container_width=True)
        if data['par_semaine']:
            df_s = pd.DataFrame(data['par_semaine']).tail(52); df_s['tonnes'] = df_s['pds_kg'].astype(float)/1000
            df_s['label'] = df_s.apply(lambda r: f"S{int(r['semaine']):02d}/{int(r['annee'])}", axis=1)
            fig = go.Figure([go.Bar(x=df_s['label'], y=df_s['tonnes'], marker_color='#42A5F5')])
            fig.update_layout(title="Expéditions / semaine (T)", height=400, xaxis=dict(tickangle=-45)); st.plotly_chart(fig, use_container_width=True)

    elif vue == "👥 Clients" and data['par_client']:
        df = pd.DataFrame(data['par_client']); df['tonnes'] = df['pds_kg'].astype(float)/1000; df['ca_k'] = df['ca'].astype(float)/1000
        st.markdown(f"##### {len(df)} clients")
        gc1, gc2 = st.columns(2)
        with gc1:
            fig = px.bar(df.head(20), x='client', y='tonnes', title="Top 20 (T)", color='tonnes', color_continuous_scale='blues')
            fig.update_layout(height=450, xaxis_tickangle=-45, showlegend=False); st.plotly_chart(fig, use_container_width=True)
        with gc2:
            fig = px.bar(df.head(20), x='client', y='ca_k', title="Top 20 (k€)", color='ca_k', color_continuous_scale='greens')
            fig.update_layout(height=450, xaxis_tickangle=-45, showlegend=False); st.plotly_chart(fig, use_container_width=True)
        df_s = df.sort_values('ca', ascending=False).copy()
        df_s['pct_cumul'] = df_s['ca'].astype(float).cumsum() / max(df_s['ca'].astype(float).sum(), 1) * 100
        nb_80 = len(df_s[df_s['pct_cumul'] <= 80]) + 1
        st.info(f"📊 **Pareto** : {nb_80} clients = 80% du CA ({nb_80*100//max(len(df),1)}% du portefeuille)")
        st.dataframe(df[['client','tonnes','ca_k','prix_moy','premiere','derniere']].head(50).rename(columns={
            'client':'Client','tonnes':'Tonnes','ca_k':'CA (k€)','prix_moy':'Prix moy','premiere':'1ère','derniere':'Dernière'
        }), use_container_width=True, hide_index=True, column_config={
            'Prix moy': st.column_config.NumberColumn(format="%.0f"),
            '1ère': st.column_config.DateColumn(format='DD/MM/YYYY'),
            'Dernière': st.column_config.DateColumn(format='DD/MM/YYYY')})
        buf = io.BytesIO(); df.to_excel(buf, index=False, engine='openpyxl')
        st.download_button(f"📥 Export clients {label}", buf.getvalue(), f"clients_{label}_{datetime.now().strftime('%Y%m%d')}.xlsx", use_container_width=True)

    elif vue == "🥔 Variétés" and data['par_variete']:
        df = pd.DataFrame(data['par_variete']); df['tonnes'] = df['pds_kg'].astype(float)/1000
        st.markdown(f"##### {len(df)} variétés")
        gv1, gv2 = st.columns(2)
        with gv1:
            fig = px.pie(df.head(15), names='variete', values='tonnes', title="Top 15 (T)")
            fig.update_layout(height=450); st.plotly_chart(fig, use_container_width=True)
        with gv2:
            fig = px.bar(df.head(15), x='variete', y='prix_moy', title="Prix moy / variété", color='prix_moy', color_continuous_scale='YlOrRd')
            fig.update_layout(height=450, showlegend=False); st.plotly_chart(fig, use_container_width=True)
        st.dataframe(df[['variete','tonnes','nb_clients','prix_moy','nb']].head(30).rename(columns={
            'variete':'Variété','tonnes':'Tonnes','nb_clients':'Clients','prix_moy':'Prix moy','nb':'Lignes'
        }), use_container_width=True, hide_index=True, column_config={'Prix moy': st.column_config.NumberColumn(format="%.0f")})

    elif vue == "🏷️ Produits" and show_produit and data.get('par_produit'):
        df = pd.DataFrame(data['par_produit']); df['tonnes'] = df['pds_kg'].astype(float)/1000; df['ca_k'] = df['ca'].astype(float)/1000
        fig = px.bar(df, x='produit', y='tonnes', title="Tonnage / produit", color='tonnes', color_continuous_scale='blues')
        fig.update_layout(height=400, xaxis_tickangle=-45, showlegend=False); st.plotly_chart(fig, use_container_width=True)
        st.dataframe(df[['produit','tonnes','ca_k','nb']].rename(columns={'produit':'Produit','tonnes':'Tonnes','ca_k':'CA (k€)','nb':'Lignes'}), use_container_width=True, hide_index=True)

    elif vue == "📦 Emballages" and data.get('par_emballage'):
        df = pd.DataFrame(data['par_emballage']); df['tonnes'] = df['pds_kg'].astype(float)/1000
        fig = px.pie(df.head(10), names='emballage', values='tonnes', title="Répartition emballages")
        fig.update_layout(height=400); st.plotly_chart(fig, use_container_width=True)
        st.dataframe(df[['emballage','tonnes','nb']].rename(columns={'emballage':'Emballage','tonnes':'Tonnes','nb':'Lignes'}), use_container_width=True, hide_index=True)

    elif vue == "📏 Calibres" and data.get('par_calibre'):
        df = pd.DataFrame(data['par_calibre']); df['tonnes'] = df['pds_kg'].astype(float)/1000
        fig = px.bar(df, x='calibre', y='tonnes', title="Tonnage / calibre", color='tonnes', color_continuous_scale='purples')
        fig.update_layout(height=400, showlegend=False); st.plotly_chart(fig, use_container_width=True)
        st.dataframe(df[['calibre','tonnes','nb_clients','nb']].rename(columns={'calibre':'Calibre','tonnes':'Tonnes','nb_clients':'Clients','nb':'Lignes'}), use_container_width=True, hide_index=True)

    elif vue == "👤 Vendeurs" and data.get('par_vendeur'):
        df = pd.DataFrame(data['par_vendeur']); df['tonnes'] = df['pds_kg'].astype(float)/1000; df['ca_k'] = df['ca'].astype(float)/1000
        fig = px.bar(df, x='vendeur', y='ca_k', title="CA / vendeur (k€)", color='ca_k', color_continuous_scale='greens')
        fig.update_layout(height=400, showlegend=False); st.plotly_chart(fig, use_container_width=True)
        st.dataframe(df[['vendeur','tonnes','ca_k','nb_clients']].rename(columns={'vendeur':'Vendeur','tonnes':'Tonnes','ca_k':'CA (k€)','nb_clients':'Clients'}), use_container_width=True, hide_index=True)


def render_analyse_achat(data):
    if not data or not data.get('kpis') or not data['kpis'] or data['kpis']['total'] == 0:
        st.info("📭 Aucune donnée Achat" + (" pour cette campagne" if sel_camp else ""))
        return
    k = data['kpis']
    c1, c2, c3, c4, c5 = st.columns(5)
    with c1: st.metric("📋 Lignes", f"{k['total']:,}".replace(',', ' '))
    with c2: st.metric("⚖️ Tonnage", f"{float(k['pds_kg'])/1000:,.0f} T".replace(',', ' '))
    with c3: st.metric("💰 Montant", f"{float(k['ca'])/1000:,.0f} k€".replace(',', ' '))
    with c4: st.metric("🏭 Fournisseurs", k['nb_fournisseurs'])
    with c5: st.metric("🥔 Variétés", k['nb_varietes'])
    if k['date_min'] and k['date_max']:
        st.caption(f"📅 {k['date_min'].strftime('%d/%m/%Y')} → {k['date_max'].strftime('%d/%m/%Y')} — Prix achat moy : {float(k['prix_moy']):,.0f} €/T".replace(',', ' '))
    st.markdown("---")
    vue = st.radio("Analyser par :", ["📊 Vue d'ensemble", "🏭 Fournisseurs", "🥔 Variétés", "🏢 Dépôts"], horizontal=True, key="vue_achat")
    st.markdown("---")

    if vue == "📊 Vue d'ensemble":
        if data['par_annee']:
            df_a = pd.DataFrame(data['par_annee']); df_a['tonnes'] = df_a['pds_kg'].astype(float)/1000; df_a['ca_k'] = df_a['ca'].astype(float)/1000
            ga1, ga2 = st.columns(2)
            with ga1:
                fig = go.Figure([go.Bar(x=df_a['annee'].astype(str), y=df_a['tonnes'], marker_color='#E65100')])
                fig.update_layout(title="Tonnage / année", height=350); st.plotly_chart(fig, use_container_width=True)
            with ga2:
                fig = go.Figure([go.Bar(x=df_a['annee'].astype(str), y=df_a['ca_k'], marker_color='#BF360C')])
                fig.update_layout(title="Montant / année (k€)", height=350); st.plotly_chart(fig, use_container_width=True)
        if data['par_mois']:
            df_m = pd.DataFrame(data['par_mois']); df_m['tonnes'] = df_m['pds_kg'].astype(float)/1000
            df_m['label'] = df_m.apply(lambda r: f"{int(r['mois']):02d}/{int(r['annee'])}", axis=1)
            fig = go.Figure([go.Scatter(x=df_m['label'], y=df_m['tonnes'], mode='lines+markers', line=dict(color='#E65100', width=2), fill='tozeroy')])
            fig.update_layout(title="Tonnage mensuel", height=400, xaxis=dict(tickangle=-45)); st.plotly_chart(fig, use_container_width=True)

    elif vue == "🏭 Fournisseurs" and data.get('par_fournisseur'):
        df = pd.DataFrame(data['par_fournisseur']); df['tonnes'] = df['pds_kg'].astype(float)/1000; df['ca_k'] = df['ca'].astype(float)/1000
        st.markdown(f"##### {len(df)} fournisseurs")
        gf1, gf2 = st.columns(2)
        with gf1:
            fig = px.bar(df.head(20), x='apporteur', y='tonnes', title="Top 20 (T)", color='tonnes', color_continuous_scale='oranges')
            fig.update_layout(height=450, xaxis_tickangle=-45, showlegend=False); st.plotly_chart(fig, use_container_width=True)
        with gf2:
            fig = px.bar(df.head(20), x='apporteur', y='prix_moy', title="Prix moy (€/T)", color='prix_moy', color_continuous_scale='YlOrRd')
            fig.update_layout(height=450, xaxis_tickangle=-45, showlegend=False); st.plotly_chart(fig, use_container_width=True)
        st.dataframe(df[['apporteur','tonnes','ca_k','prix_moy','nb_varietes','nb']].head(50).rename(columns={
            'apporteur':'Fournisseur','tonnes':'Tonnes','ca_k':'Montant (k€)','prix_moy':'Prix moy','nb_varietes':'Variétés','nb':'Lignes'
        }), use_container_width=True, hide_index=True, column_config={'Prix moy': st.column_config.NumberColumn(format="%.0f")})
        buf = io.BytesIO(); df.to_excel(buf, index=False, engine='openpyxl')
        st.download_button("📥 Export fournisseurs", buf.getvalue(), f"fournisseurs_{datetime.now().strftime('%Y%m%d')}.xlsx", use_container_width=True)

    elif vue == "🥔 Variétés" and data.get('par_variete'):
        df = pd.DataFrame(data['par_variete']); df['tonnes'] = df['pds_kg'].astype(float)/1000
        st.markdown(f"##### {len(df)} variétés")
        gv1, gv2 = st.columns(2)
        with gv1:
            fig = px.pie(df.head(15), names='variete', values='tonnes', title="Top 15 (T)")
            fig.update_layout(height=450); st.plotly_chart(fig, use_container_width=True)
        with gv2:
            fig = px.bar(df.head(15), x='variete', y='prix_moy', title="Prix moy / variété", color='prix_moy', color_continuous_scale='YlOrRd')
            fig.update_layout(height=450, showlegend=False); st.plotly_chart(fig, use_container_width=True)
        st.dataframe(df[['variete','tonnes','nb_fournisseurs','prix_moy','nb']].head(30).rename(columns={
            'variete':'Variété','tonnes':'Tonnes','nb_fournisseurs':'Fournisseurs','prix_moy':'Prix moy','nb':'Lignes'
        }), use_container_width=True, hide_index=True, column_config={'Prix moy': st.column_config.NumberColumn(format="%.0f")})

    elif vue == "🏢 Dépôts" and data.get('par_depot'):
        df = pd.DataFrame(data['par_depot']); df['tonnes'] = df['pds_kg'].astype(float)/1000; df['ca_k'] = df['ca'].astype(float)/1000
        st.markdown(f"##### {len(df)} dépôts")
        fig = px.bar(df.head(20), x='depot', y='tonnes', title="Top 20 (T)", color='tonnes', color_continuous_scale='oranges')
        fig.update_layout(height=400, xaxis_tickangle=-45, showlegend=False); st.plotly_chart(fig, use_container_width=True)
        st.dataframe(df[['depot','tonnes','ca_k','nb']].head(30).rename(columns={'depot':'Dépôt','tonnes':'Tonnes','ca_k':'Montant (k€)','nb':'Lignes'}), use_container_width=True, hide_index=True)


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
    imp_type = st.radio("Type d'import :", ["📈 Ventes Condi", "🏪 Ventes Négoce", "🛒 Achats"], horizontal=True, key="imp_type")
    st.markdown("---")

    if imp_type == "📈 Ventes Condi":
        st.subheader("📈 Import Ventes Conditionnement")
        up = st.file_uploader("Fichier Excel Ventes Condi", type=['xlsx','xls'], key="up_condi")
        if up:
            try:
                up.seek(0); df_count = pd.read_excel(up, sheet_name=0)
                c1, c2, c3 = st.columns(3)
                nb_e = len(df_count[df_count['Type']=='E']) if 'Type' in df_count.columns else 0
                nb_a = len(df_count[df_count['Type']=='A']) if 'Type' in df_count.columns else 0
                with c1: st.metric("Lignes total", len(df_count))
                with c2: st.metric("Expéditions (E)", nb_e)
                with c3: st.metric("Avoirs (A)", nb_a)
                st.dataframe(df_count.head(3), use_container_width=True, hide_index=True)
                if st.button("🚀 Importer CONDI", type="primary", use_container_width=True):
                    up.seek(0)
                    with st.spinner("Import CONDI..."): ok, msg = importer_ventes(up, 'CONDI', st.session_state.get('username','inconnu'))
                    if ok: st.success(f"✅ {msg}"); st.rerun()
                    else: st.error(f"❌ {msg}")
            except Exception as e: st.error(f"Erreur : {str(e)}")

    elif imp_type == "🏪 Ventes Négoce":
        st.subheader("🏪 Import Ventes Négoce")
        up = st.file_uploader("Fichier Excel Ventes Négoce", type=['xlsx','xls'], key="up_negoce")
        if up:
            try:
                up.seek(0); df_count = pd.read_excel(up, sheet_name=0)
                c1, c2 = st.columns(2)
                nb_e = len(df_count[df_count['Type']=='E']) if 'Type' in df_count.columns else 0
                with c1: st.metric("Lignes total", len(df_count))
                with c2: st.metric("Expéditions (E)", nb_e)
                st.dataframe(df_count.head(3), use_container_width=True, hide_index=True)
                if st.button("🚀 Importer NÉGOCE", type="primary", use_container_width=True):
                    up.seek(0)
                    with st.spinner("Import NÉGOCE..."): ok, msg = importer_ventes(up, 'NEGOCE', st.session_state.get('username','inconnu'))
                    if ok: st.success(f"✅ {msg}"); st.rerun()
                    else: st.error(f"❌ {msg}")
            except Exception as e: st.error(f"Erreur : {str(e)}")

    else:
        st.subheader("🛒 Import Achats")
        up = st.file_uploader("Fichier Excel Achats", type=['xlsx','xls'], key="up_achat")
        if up:
            try:
                up.seek(0); df_count = pd.read_excel(up, sheet_name=0)
                c1, c2, c3 = st.columns(3)
                nb_s = len(df_count[df_count['Type']=='S']) if 'Type' in df_count.columns else 0
                nb_a = len(df_count[df_count['Type']=='A']) if 'Type' in df_count.columns else 0
                with c1: st.metric("Lignes total", len(df_count))
                with c2: st.metric("Achats (S)", nb_s)
                with c3: st.metric("Avoirs (A)", nb_a)
                st.dataframe(df_count.head(3), use_container_width=True, hide_index=True)
                if st.button("🚀 Importer ACHATS", type="primary", use_container_width=True):
                    up.seek(0)
                    with st.spinner("Import ACHATS..."): ok, msg = importer_achat(up, st.session_state.get('username','inconnu'))
                    if ok: st.success(f"✅ {msg}"); st.rerun()
                    else: st.error(f"❌ {msg}")
            except Exception as e: st.error(f"Erreur : {str(e)}")

    st.markdown("---")
    st.markdown("##### 📋 Historique des imports")
    df_imp = get_imports()
    if not df_imp.empty:
        cols_show = [c for c in ['id','source','nom_fichier','date_import','nb_lignes_total','nb_lignes_type_e','nb_lignes_type_a','date_debut','date_fin','created_by'] if c in df_imp.columns]
        st.dataframe(df_imp[cols_show].rename(columns={
            'id':'ID','source':'Type','nom_fichier':'Fichier','date_import':'Date','nb_lignes_total':'Lignes',
            'nb_lignes_type_e':'E/S','nb_lignes_type_a':'Avoirs','date_debut':'Début','date_fin':'Fin','created_by':'Par'
        }), use_container_width=True, hide_index=True)

# ============================================================================
# TAB 2 : MAPPING PRODUITS — INLINE
# ============================================================================

with tab2:
    st.subheader("🔗 Mapping Emballage + Marque → Produit Commercial")
    st.caption("*Applicable aux données Condi — sélectionnez une ligne pour mapper*")

    df_nm = get_combinaisons_non_mappees_produit()
    produits = get_produits_commerciaux()

    if not df_nm.empty:
        st.markdown(f"##### ⚠️ {len(df_nm)} combinaison(s) sans mapping")
        event = st.dataframe(
            df_nm.rename(columns={
                'emballage':'Emballage','marque':'Marque','nb_lignes':'Nb lignes',
                'pds_total_kg':'Pds total (kg)','nb_clients':'Nb clients'
            }),
            use_container_width=True, hide_index=True,
            on_select="rerun", selection_mode="single-row", key="table_nm"
        )

        sel = event.selection.rows if hasattr(event, 'selection') else []
        if sel and produits:
            row_sel = df_nm.iloc[sel[0]]
            st.markdown("---")
            st.markdown(f"**Mapper : `{row_sel['emballage']}` | `{row_sel.get('marque', '(vide)')}`** ({row_sel['nb_lignes']} lignes, {row_sel['nb_clients']} clients)")
            prod_labels = [f"{p['code_produit']} — {p['marque']} {p['libelle']}" for p in produits]
            prod_idx = st.selectbox("→ Produit POMI", range(len(prod_labels)),
                                   format_func=lambda i: prod_labels[i], key="mp_prod_inline")
            if st.button("💾 Enregistrer le mapping", type="primary", key="btn_mp_inline"):
                ok, msg = sauver_mapping_produit(row_sel['emballage'], row_sel.get('marque'), produits[prod_idx]['code_produit'])
                if ok: st.success(f"✅ {msg}"); st.rerun()
                else: st.error(f"❌ {msg}")
    else:
        st.success("✅ Toutes les combinaisons sont mappées" + (" pour cette campagne" if sel_camp else ""))

    st.markdown("---")
    st.markdown("##### 📋 Mappings existants")
    df_mp = get_mapping_produit()
    if not df_mp.empty:
        st.dataframe(df_mp[['emballage','marque','code_produit_commercial','libelle_produit']].rename(columns={
            'emballage':'Emballage','marque':'Marque','code_produit_commercial':'Code Produit','libelle_produit':'Libellé'
        }), use_container_width=True, hide_index=True)

# ============================================================================
# TAB 3 : MAPPING SUR-EMBALLAGES — INLINE
# ============================================================================

with tab3:
    st.subheader("📦 Mapping Code Emballage → Sur-Emballage")
    st.caption("*Applicable aux données Condi — sélectionnez une ligne pour mapper*")

    df_nm_se = get_emballages_non_mappes_se()
    sur_embs = get_sur_emballages()

    if not df_nm_se.empty:
        st.markdown(f"##### ⚠️ {len(df_nm_se)} code(s) sans sur-emballage")
        event_se = st.dataframe(
            df_nm_se.rename(columns={'code_emballage':'Code Emballage','nb_lignes':'Nb lignes','nb_col_total':'Nb colis'}),
            use_container_width=True, hide_index=True,
            on_select="rerun", selection_mode="single-row", key="table_nm_se"
        )

        sel_se = event_se.selection.rows if hasattr(event_se, 'selection') else []
        if sel_se and sur_embs:
            row_se = df_nm_se.iloc[sel_se[0]]
            st.markdown("---")
            st.markdown(f"**Mapper : `{row_se['code_emballage']}`** ({row_se['nb_lignes']} lignes)")
            se_labels = [f"{se['libelle']} ({se['nb_uvc']} UVC)" for se in sur_embs]
            se_idx = st.selectbox("→ Sur-emballage POMI", range(len(se_labels)),
                                 format_func=lambda i: se_labels[i], key="mse_se_inline")
            if st.button("💾 Enregistrer", type="primary", key="btn_mse_inline"):
                ok, msg = sauver_mapping_suremballage(row_se['code_emballage'], int(sur_embs[se_idx]['id']))
                if ok: st.success(f"✅ {msg}"); st.rerun()
                else: st.error(f"❌ {msg}")
    else:
        st.success("✅ Tous les codes sont associés" + (" pour cette campagne" if sel_camp else ""))

    st.markdown("---")
    st.markdown("##### 📋 Associations existantes")
    df_mse = get_mapping_suremballage()
    if not df_mse.empty:
        st.dataframe(df_mse[['code_emballage','libelle_se','nb_uvc','description']].rename(columns={
            'code_emballage':'Code','libelle_se':'Sur-Emballage','nb_uvc':'UVC','description':'Description'
        }), use_container_width=True, hide_index=True)

# ============================================================================
# TAB 4 : CONDI
# ============================================================================

with tab4:
    st.subheader("📈 Analyse Conditionnement")
    sous = st.radio("", ["📊 Analyse", "🎯 Prévu vs Réel"], horizontal=True, key="condi_sous")
    st.markdown("---")

    if sous == "📊 Analyse":
        data_condi = get_analyse_ventes('frulog_lignes_condi')
        render_analyse_ventes(data_condi, "condi", show_produit=True)
    else:
        df_comp = get_comparaison_previsions()
        if not df_comp.empty:
            df_avec = df_comp[df_comp['prevu_t'].astype(float) > 0]
            taux_g = (df_avec['expedie_t'].astype(float).sum() / max(df_avec['prevu_t'].astype(float).sum(), 0.001) * 100) if not df_avec.empty else 0
            tot_p = df_comp['prevu_t'].astype(float).sum(); tot_e = df_comp['expedie_t'].astype(float).sum()
            k1, k2, k3, k4 = st.columns(4)
            with k1: st.metric("📊 Prévu", f"{tot_p:.1f} T")
            with k2: st.metric("🚚 Expédié", f"{tot_e:.1f} T")
            with k3: st.metric("📐 Écart", f"{tot_e-tot_p:+.1f} T")
            with k4: st.metric("🎯 Réalisation", f"{taux_g:.0f}%")
            st.markdown("---")
            df_sem = df_comp.groupby(['annee','semaine']).agg(
                prevu=('prevu_t', lambda x: x.astype(float).sum()),
                expedie=('expedie_t', lambda x: x.astype(float).sum())).reset_index()
            df_sem['label'] = df_sem.apply(lambda r: f"S{int(r['semaine']):02d}/{int(r['annee'])}", axis=1)
            fig = go.Figure()
            fig.add_trace(go.Bar(x=df_sem['label'], y=df_sem['prevu'], name='Prévu', marker_color='#90CAF9'))
            fig.add_trace(go.Bar(x=df_sem['label'], y=df_sem['expedie'], name='Expédié', marker_color='#1565C0'))
            fig.update_layout(barmode='group', title="Prévu vs Expédié (T)", height=400)
            st.plotly_chart(fig, use_container_width=True)
            df_sem['taux'] = df_sem.apply(lambda r: (r['expedie']/r['prevu']*100) if r['prevu']>0 else None, axis=1)
            if df_sem['taux'].notna().any():
                colors = ['#4CAF50' if t and 80<=t<=120 else '#FF9800' if t and (60<=t<80 or 120<t<=150) else '#F44336' for t in df_sem['taux']]
                fig_t = go.Figure([go.Bar(x=df_sem['label'], y=df_sem['taux'], marker_color=colors)])
                fig_t.add_hline(y=100, line_dash="dash", line_color="black")
                fig_t.update_layout(title="Taux réalisation / semaine (%)", height=350)
                st.plotly_chart(fig_t, use_container_width=True)
            st.markdown("---")
            df_pr = df_comp.groupby('produit').agg(prevu=('prevu_t', lambda x: x.astype(float).sum()), expedie=('expedie_t', lambda x: x.astype(float).sum())).reset_index()
            df_pr['ecart'] = df_pr['expedie'] - df_pr['prevu']
            df_pr['taux'] = df_pr.apply(lambda r: f"{r['expedie']/r['prevu']*100:.0f}%" if r['prevu']>0 else "—", axis=1)
            st.dataframe(df_pr.sort_values('prevu', ascending=False).rename(columns={'produit':'Produit','prevu':'Prévu (T)','expedie':'Expédié (T)','ecart':'Écart (T)','taux':'Taux'}), use_container_width=True, hide_index=True)
            buf = io.BytesIO()
            with pd.ExcelWriter(buf, engine='openpyxl') as w:
                df_comp.to_excel(w, index=False, sheet_name='Détail'); df_sem.to_excel(w, index=False, sheet_name='Par Semaine'); df_pr.to_excel(w, index=False, sheet_name='Par Produit')
            st.download_button("📥 Export Excel", buf.getvalue(), f"prevu_vs_reel_{datetime.now().strftime('%Y%m%d')}.xlsx", use_container_width=True)
        else:
            st.info("📭 Aucune donnée. Importez des données Condi et/ou saisissez des prévisions.")

# ============================================================================
# TAB 5 : NÉGOCE
# ============================================================================

with tab5:
    st.subheader("🏪 Analyse Négoce")
    data_negoce = get_analyse_ventes('frulog_lignes_negoce')
    render_analyse_ventes(data_negoce, "negoce", show_produit=False)

# ============================================================================
# TAB 6 : ACHATS
# ============================================================================

with tab6:
    st.subheader("🛒 Analyse Achats")
    data_achat = get_analyse_achat()
    render_analyse_achat(data_achat)

show_footer()
