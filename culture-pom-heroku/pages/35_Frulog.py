import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, date
from database import get_connection
from components import show_footer
from auth import require_access, is_admin

st.set_page_config(page_title="Frulog Import - POMI", page_icon="📥", layout="wide")
st.markdown("""<style>
    .block-container {padding-top:2rem!important;padding-bottom:0.5rem!important;
        padding-left:2rem!important;padding-right:2rem!important;}
    h1,h2,h3,h4{margin-top:0.3rem!important;margin-bottom:0.3rem!important;}
    [data-testid="stMetricValue"]{font-size:1.4rem!important;}
    hr{margin-top:0.5rem!important;margin-bottom:0.5rem!important;}
</style>""", unsafe_allow_html=True)

require_access("COMMERCIAL")
st.title("📥 Frulog — Import & Mapping")

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
VENTES_INT_COLS  = ['nb_col','nb_pce','etat','nb_pal','nb_pal_sol']
VENTES_NUM_COLS  = ['pds_brut','tare_v','pds_net','prix','montant','montant_euro',
    'pds_brut_a','tare_a','pds_ach','px_ach','trp_achats_val','trp_inter_val',
    'conditmt_val','trp_ventes_val','trp_litige_val','presta_bb_val','presta_sacs_val',
    'stock_cultu_val','stock_ext_val','stock_tilly_val','com_ventes_val','douanes_val',
    'emballage_val','expedition_val','col_111_val']
ACHAT_DATE_COLS = ['date_du_bon','dt_chargmt','date_facture','dt_expi']
ACHAT_INT_COLS  = ['nb_pal','nb_colis','nb_col_sup','etat']
ACHAT_NUM_COLS  = ['pds_brut','pds_net','prix_achat','montant_ht','montant_euro','tare']

# ============================================================================
# UTILITAIRES
# ============================================================================

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
        cur.execute("""SELECT fl.emballage, fl.marque, fl.depot, COUNT(*) as nb_lignes,
            SUM(ABS(COALESCE(fl.pds_net, 0)))/1000 as tonnes, COUNT(DISTINCT fl.client) as nb_clients
            FROM frulog_lignes_condi fl WHERE fl.type IN ('E','C') AND fl.code_produit_commercial IS NULL
            AND fl.emballage IS NOT NULL GROUP BY fl.emballage, fl.marque, fl.depot ORDER BY nb_lignes DESC""")
        rows = cur.fetchall(); cur.close(); conn.close()
        return pd.DataFrame(rows) if rows else pd.DataFrame()
    except: return pd.DataFrame()

def get_emballages_non_mappes_se():
    try:
        conn = get_connection(); cur = conn.cursor()
        cur.execute("""SELECT fl.emballage as code_emballage, COUNT(*) as nb_lignes, SUM(COALESCE(fl.nb_col,0)) as nb_col_total
            FROM frulog_lignes_condi fl WHERE fl.type IN ('E','C') AND fl.sur_emballage_id IS NULL
            AND fl.emballage IS NOT NULL GROUP BY fl.emballage ORDER BY nb_lignes DESC""")
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
# FONCTIONS IMPORT
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
            df_c['annee']   = df_c['date_charg'].apply(lambda d: d.isocalendar()[0] if pd.notna(d) else None)
            df_c['semaine'] = df_c['date_charg'].apply(lambda d: d.isocalendar()[1] if pd.notna(d) else None)
        conn = get_connection(); cur = conn.cursor()
        nb_total = len(df_c)
        nb_e = len(df_c[df_c.get('type', pd.Series()) == 'E']) if 'type' in df_c.columns else 0
        nb_a = len(df_c[df_c.get('type', pd.Series()) == 'A']) if 'type' in df_c.columns else 0
        nb_c = len(df_c[df_c.get('type', pd.Series()) == 'C']) if 'type' in df_c.columns else 0
        d_min = df_c['date_charg'].dropna().min() if 'date_charg' in df_c.columns else None
        d_max = df_c['date_charg'].dropna().max() if 'date_charg' in df_c.columns else None
        cur.execute("INSERT INTO frulog_imports (nom_fichier,source,nb_lignes_total,nb_lignes_type_e,nb_lignes_type_a,nb_lignes_sans_type,date_debut,date_fin,created_by) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id",
            (uploaded_file.name, source, nb_total, nb_e+nb_c, nb_a, nb_total-nb_e-nb_a-nb_c, d_min, d_max, username))
        import_id = cur.fetchone()['id']
        mp = {}; mse = {}
        if source == 'CONDI':
            cur.execute("SELECT cle_mapping,code_produit_commercial FROM frulog_mapping_produit WHERE is_active=TRUE")
            mp = {r['cle_mapping']: r['code_produit_commercial'] for r in cur.fetchall()}
            cur.execute("SELECT code_emballage,sur_emballage_id FROM frulog_mapping_suremballage WHERE is_active=TRUE")
            mse = {r['code_emballage']: r['sur_emballage_id'] for r in cur.fetchall()}
        if mp:  df_c['code_produit_commercial'] = df_c.apply(lambda r: mp.get(make_cle_produit(r.get('emballage'), r.get('marque'))), axis=1)
        if mse: df_c['sur_emballage_id'] = df_c['emballage'].apply(lambda e: mse.get(str(e).strip().upper()) if e and str(e).strip() != '.' else None)
        cur.execute(f"SELECT no_de_bon,etat,pds_net,montant,type,nb_col FROM {table} WHERE no_de_bon IS NOT NULL")
        existing = {r['no_de_bon']: r for r in cur.fetchall()}
        data_cols = [c for c in cols_ok if c != 'no_de_bon'] + ['annee', 'semaine']
        if source == 'CONDI': data_cols += ['code_produit_commercial', 'sur_emballage_id']
        data_cols = list(dict.fromkeys(data_cols))
        nb_new = nb_upd = nb_unc = 0
        for _, row in df_c.iterrows():
            bon = to_python(row.get('no_de_bon'))
            if not bon: continue
            rv = {c: to_python(row.get(c)) for c in data_cols}
            if bon in existing:
                ex = existing[bon]
                if any(str(to_python(row.get(k))) != str(ex.get(k)) for k in ['etat','pds_net','montant','type','nb_col']):
                    sp = [f"{c}=%s" for c in data_cols] + ["import_id=%s"]
                    cur.execute(f"UPDATE {table} SET {','.join(sp)} WHERE no_de_bon=%s", [rv[c] for c in data_cols] + [import_id, bon])
                    nb_upd += 1
                else: nb_unc += 1
            else:
                ac = ['import_id','no_de_bon'] + data_cols
                cur.execute(f"INSERT INTO {table} ({','.join(ac)}) VALUES ({','.join(['%s']*len(ac))})", [import_id, bon] + [rv[c] for c in data_cols])
                nb_new += 1
        conn.commit(); cur.close(); conn.close()
        m = f" {df_c['code_produit_commercial'].notna().sum()}/{nb_total} mappées." if source == 'CONDI' and 'code_produit_commercial' in df_c.columns else ""
        return True, f"Import #{import_id} ({source}) : {nb_total} → **{nb_new} new**, **{nb_upd} maj**, {nb_unc} ident.{m}"
    except Exception as e:
        if 'conn' in locals(): conn.rollback()
        return False, str(e)

def importer_achat(uploaded_file, username='inconnu'):
    try:
        df = pd.read_excel(uploaded_file, sheet_name=0)
        if len(df) == 0: return False, "Fichier vide"
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
            df_c['annee']   = df_c[dc].apply(lambda d: d.isocalendar()[0] if pd.notna(d) else None)
            df_c['semaine'] = df_c[dc].apply(lambda d: d.isocalendar()[1] if pd.notna(d) else None)
        conn = get_connection(); cur = conn.cursor()
        nt = len(df_c)
        cur.execute("INSERT INTO frulog_imports (nom_fichier,source,nb_lignes_total,nb_lignes_type_e,nb_lignes_type_a,nb_lignes_sans_type,date_debut,date_fin,created_by) VALUES (%s,'ACHAT',%s,%s,%s,%s,%s,%s,%s) RETURNING id",
            (uploaded_file.name, nt, len(df_c[df_c.get('type', pd.Series()) == 'S']) if 'type' in df_c.columns else 0,
             len(df_c[df_c.get('type', pd.Series()) == 'A']) if 'type' in df_c.columns else 0, 0,
             df_c[dc].dropna().min() if dc in df_c.columns else None,
             df_c[dc].dropna().max() if dc in df_c.columns else None, username))
        iid = cur.fetchone()['id']
        cur.execute("SELECT no_de_bon,etat,pds_net,montant_euro,type FROM frulog_lignes_achat WHERE no_de_bon IS NOT NULL")
        existing = {str(r['no_de_bon']): r for r in cur.fetchall()}
        data_cols = list(dict.fromkeys([c for c in cols_ok if c != 'no_de_bon'] + ['annee', 'semaine']))
        nn = nu = nc = 0
        for _, row in df_c.iterrows():
            bon = str(to_python(row.get('no_de_bon')))
            if not bon or bon == 'None': continue
            rv = {c: to_python(row.get(c)) for c in data_cols}
            if bon in existing:
                if any(str(to_python(row.get(k))) != str(existing[bon].get(k)) for k in ['etat','pds_net','montant_euro','type']):
                    sp = [f"{c}=%s" for c in data_cols] + ["import_id=%s"]
                    cur.execute(f"UPDATE frulog_lignes_achat SET {','.join(sp)} WHERE no_de_bon=%s", [rv[c] for c in data_cols] + [iid, bon])
                    nu += 1
                else: nc += 1
            else:
                ac = ['import_id','no_de_bon'] + data_cols
                cur.execute(f"INSERT INTO frulog_lignes_achat ({','.join(ac)}) VALUES ({','.join(['%s']*len(ac))})", [iid, bon] + [rv[c] for c in data_cols])
                nn += 1
        conn.commit(); cur.close(); conn.close()
        return True, f"Import #{iid} (ACHAT) : {nt} → **{nn} new**, **{nu} maj**, {nc} ident."
    except Exception as e:
        if 'conn' in locals(): conn.rollback()
        return False, str(e)

# ============================================================================
# ONGLETS
# ============================================================================

tab1, tab2, tab3 = st.tabs(["📥 Import", "🔗 Mapping Produits", "📦 Mapping Sur-Emb."])

# ============================================================================
# TAB 1 : IMPORT
# ============================================================================
with tab1:
    imp_type = st.radio("Type :", ["📈 Condi", "🏪 Négoce", "🛒 Achats"], horizontal=True, key="imp_type")
    st.markdown("---")

    # Lecture unique par fichier — évite double pd.read_excel et erreur 400 Heroku
    def _lire_fichier_unique(up, cache_key):
        """Lit le fichier Excel une seule fois et le met en cache session_state.
        Utilise getvalue() pour éviter l'erreur 400 sur Heroku."""
        file_id = f"{up.name}_{up.size}"
        if st.session_state.get(cache_key + "_id") != file_id:
            with st.spinner("Lecture du fichier..."):
                import io as _sio
                file_bytes = up.getvalue()
                dfc = pd.read_excel(_sio.BytesIO(file_bytes), sheet_name=0)
                st.session_state[cache_key] = dfc
                st.session_state[cache_key + "_id"] = file_id
        return st.session_state.get(cache_key)

    if imp_type == "📈 Condi":
        up = st.file_uploader("Fichier Excel Ventes Condi", type=['xlsx','xls'], key="up_condi")
        if up:
            try:
                dfc = _lire_fichier_unique(up, "frulog_cache_condi")
                if dfc is not None:
                    c1,c2,c3,c4 = st.columns(4)
                    with c1: st.metric("Lignes", len(dfc))
                    with c2: st.metric("E", len(dfc[dfc['Type']=='E']) if 'Type' in dfc.columns else 0)
                    with c3: st.metric("C", len(dfc[dfc['Type']=='C']) if 'Type' in dfc.columns else 0)
                    with c4: st.metric("A", len(dfc[dfc['Type']=='A']) if 'Type' in dfc.columns else 0)
                    st.dataframe(dfc.head(3), use_container_width=True, hide_index=True)
                    if st.button("🚀 Importer CONDI", type="primary", use_container_width=True):
                        import io as _sio2
                        up_bytes = _sio2.BytesIO(up.getvalue()); up_bytes.name = up.name
                        with st.spinner("Import..."): ok, msg = importer_ventes(up_bytes, 'CONDI', st.session_state.get('username','?'))
                        if ok:
                            st.session_state.pop("frulog_cache_condi", None)
                            st.session_state.pop("frulog_cache_condi_id", None)
                            st.success(f"✅ {msg}"); st.rerun()
                        else: st.error(f"❌ {msg}")
            except Exception as e: st.error(str(e))

    elif imp_type == "🏪 Négoce":
        up = st.file_uploader("Fichier Excel Ventes Négoce", type=['xlsx','xls'], key="up_negoce")
        if up:
            try:
                dfc = _lire_fichier_unique(up, "frulog_cache_negoce")
                if dfc is not None:
                    c1,c2 = st.columns(2)
                    with c1: st.metric("Lignes", len(dfc))
                    with c2: st.metric("E", len(dfc[dfc['Type']=='E']) if 'Type' in dfc.columns else 0)
                    st.dataframe(dfc.head(3), use_container_width=True, hide_index=True)
                    if st.button("🚀 Importer NÉGOCE", type="primary", use_container_width=True):
                        import io as _sio3
                        up_bytes = _sio3.BytesIO(up.getvalue()); up_bytes.name = up.name
                        with st.spinner("Import..."): ok, msg = importer_ventes(up_bytes, 'NEGOCE', st.session_state.get('username','?'))
                        if ok:
                            st.session_state.pop("frulog_cache_negoce", None)
                            st.session_state.pop("frulog_cache_negoce_id", None)
                            st.success(f"✅ {msg}"); st.rerun()
                        else: st.error(f"❌ {msg}")
            except Exception as e: st.error(str(e))

    else:
        up = st.file_uploader("Fichier Excel Achats", type=['xlsx','xls'], key="up_achat")
        if up:
            try:
                dfc = _lire_fichier_unique(up, "frulog_cache_achat")
                if dfc is not None:
                    c1,c2,c3 = st.columns(3)
                    with c1: st.metric("Lignes", len(dfc))
                    with c2: st.metric("S", len(dfc[dfc['Type']=='S']) if 'Type' in dfc.columns else 0)
                    with c3: st.metric("A", len(dfc[dfc['Type']=='A']) if 'Type' in dfc.columns else 0)
                    st.dataframe(dfc.head(3), use_container_width=True, hide_index=True)
                    if st.button("🚀 Importer ACHATS", type="primary", use_container_width=True):
                        import io as _sio4
                        up_bytes = _sio4.BytesIO(up.getvalue()); up_bytes.name = up.name
                        with st.spinner("Import..."): ok, msg = importer_achat(up_bytes, st.session_state.get('username','?'))
                        if ok:
                            st.session_state.pop("frulog_cache_achat", None)
                            st.session_state.pop("frulog_cache_achat_id", None)
                            st.success(f"✅ {msg}"); st.rerun()
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
# TAB 2 : MAPPING PRODUITS
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
            column_config={'Tonnes': st.column_config.NumberColumn(format="%.1f")})
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
        st.success("✅ Tout est mappé")
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
# TAB 3 : MAPPING SUR-EMBALLAGES
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
        st.success("✅ Tout est associé")
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

show_footer()
