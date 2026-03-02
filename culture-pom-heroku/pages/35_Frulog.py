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
st.caption("*Import fichiers Frulog, mapping produits & sur-emballages, analyse expéditions, comparaison prévisions*")
st.markdown("---")

# ============================================================================
# CONSTANTES
# ============================================================================

COLONNES_MAPPING = {
    'No de bon': 'no_de_bon', 'Type': 'type', 'Date cmd': 'date_cmd',
    'Date charg': 'date_charg', 'Date livr': 'date_livr', 'Date Créa': 'date_crea',
    'N°BlApp': 'no_bl_app', 'N°Contrat': 'no_contrat', 'Client': 'client',
    'Ref client': 'ref_client', 'Depot': 'depot', 'Produit': 'produit',
    'Variete': 'variete', 'Categ': 'categ', 'Calibre': 'calibre',
    'Couleur': 'couleur', 'Emballage': 'emballage', 'Marque': 'marque',
    'Nb Col': 'nb_col', 'Pds brut': 'pds_brut', 'Tare V': 'tare_v',
    'Pds net': 'pds_net', 'Prix': 'prix', 'UF': 'uf', 'Tp.Px': 'tp_px',
    'Fac.P': 'fac_p', 'NB Pce': 'nb_pce', 'Montant': 'montant',
    'Devise': 'devise', 'Montant EURO': 'montant_euro',
    'No Fact./Avoir': 'no_fact_avoir', 'Dt Fac V': 'dt_fac_v',
    'Etat': 'etat', 'Typ V': 'typ_v', 'Nb pal': 'nb_pal',
    'Nb pal sol': 'nb_pal_sol', 'Apporteur': 'apporteur', 'Lot': 'lot',
    'Pds brut A': 'pds_brut_a', 'Tare A': 'tare_a', 'Pds Ach': 'pds_ach',
    'Px Ach': 'px_ach', 'Vehicule': 'vehicule', 'Remorque': 'remorque',
    'CMR': 'cmr', 'BR': 'br', 'BL.P': 'bl_p', 'Bon Ach': 'bon_ach',
    'Fac Ach': 'fac_ach', 'Dt Fac A': 'dt_fac_a', 'Dte Fab': 'dte_fab',
    'Agent': 'agent', 'Vendeur': 'vendeur',
    'TRPACHATS Val': 'trp_achats_val', 'TRPINTER Val': 'trp_inter_val',
    'CONDITMT Val': 'conditmt_val', 'TRPVENTES Val': 'trp_ventes_val',
    'TRPLITIGE Val': 'trp_litige_val', 'PRESTABB Val': 'presta_bb_val',
    'PRESTASACS Val': 'presta_sacs_val', 'STOCKCULTU Val': 'stock_cultu_val',
    'STOCKEXT Val': 'stock_ext_val', 'STOCKTILLY Val': 'stock_tilly_val',
    'COMVENTES Val': 'com_ventes_val', 'DOUANES Val': 'douanes_val',
    'EMBALLAGE Val': 'emballage_val', 'EXPEDITION Val': 'expedition_val',
    '111 Val': 'col_111_val', 'Transport': 'transport',
    'GTIN U': 'gtin_u', 'GTIN P': 'gtin_p', 'GTIN C': 'gtin_c',
    'GGN': 'ggn', 'Dt.Expi': 'dt_expi'
}

DATE_COLS = ['date_cmd','date_charg','date_livr','date_crea','dt_fac_v','dt_fac_a','dte_fab','dt_expi']
INT_COLS = ['nb_col','nb_pce','etat','nb_pal','nb_pal_sol']
NUMERIC_COLS = ['pds_brut','tare_v','pds_net','prix','montant','montant_euro',
    'pds_brut_a','tare_a','pds_ach','px_ach','trp_achats_val','trp_inter_val',
    'conditmt_val','trp_ventes_val','trp_litige_val','presta_bb_val','presta_sacs_val',
    'stock_cultu_val','stock_ext_val','stock_tilly_val','com_ventes_val','douanes_val',
    'emballage_val','expedition_val','col_111_val']


def make_cle_produit(emballage, marque):
    """Clé mapping produit = emballage|marque"""
    e = str(emballage).strip().upper() if emballage and str(emballage).strip() != '.' else ''
    m = str(marque).strip().upper() if marque and str(marque).strip() != '.' else ''
    return f"{e}|{m}"


# ============================================================================
# FONCTIONS BDD
# ============================================================================

def get_imports():
    try:
        conn = get_connection(); cursor = conn.cursor()
        cursor.execute("SELECT * FROM frulog_imports ORDER BY date_import DESC LIMIT 50")
        rows = cursor.fetchall(); cursor.close(); conn.close()
        return pd.DataFrame(rows) if rows else pd.DataFrame()
    except: return pd.DataFrame()


def get_mapping_produit():
    try:
        conn = get_connection(); cursor = conn.cursor()
        cursor.execute("""
            SELECT fm.*, pc.libelle as libelle_produit, pc.marque as marque_produit
            FROM frulog_mapping_produit fm
            LEFT JOIN ref_produits_commerciaux pc ON fm.code_produit_commercial = pc.code_produit
            WHERE fm.is_active = TRUE ORDER BY fm.emballage, fm.marque
        """)
        rows = cursor.fetchall(); cursor.close(); conn.close()
        return pd.DataFrame(rows) if rows else pd.DataFrame()
    except: return pd.DataFrame()


def get_mapping_suremballage():
    try:
        conn = get_connection(); cursor = conn.cursor()
        cursor.execute("""
            SELECT fms.*, se.libelle as libelle_se, se.nb_uvc
            FROM frulog_mapping_suremballage fms
            LEFT JOIN ref_sur_emballages se ON fms.sur_emballage_id = se.id
            WHERE fms.is_active = TRUE ORDER BY fms.code_emballage
        """)
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
    """Combinaisons emballage+marque dans frulog_lignes sans mapping produit"""
    try:
        conn = get_connection(); cursor = conn.cursor()
        cursor.execute("""
            SELECT fl.emballage, fl.marque,
                   COUNT(*) as nb_lignes,
                   SUM(ABS(COALESCE(fl.pds_net, 0))) as pds_total_kg,
                   COUNT(DISTINCT fl.client) as nb_clients
            FROM frulog_lignes fl
            WHERE fl.type = 'E' AND fl.produit = 'PTC'
              AND fl.code_produit_commercial IS NULL
              AND fl.emballage IS NOT NULL
            GROUP BY fl.emballage, fl.marque
            ORDER BY nb_lignes DESC
        """)
        rows = cursor.fetchall(); cursor.close(); conn.close()
        return pd.DataFrame(rows) if rows else pd.DataFrame()
    except: return pd.DataFrame()


def get_emballages_non_mappes_se():
    """Codes emballage Frulog sans mapping sur-emballage"""
    try:
        conn = get_connection(); cursor = conn.cursor()
        cursor.execute("""
            SELECT fl.emballage as code_emballage,
                   COUNT(*) as nb_lignes,
                   SUM(COALESCE(fl.nb_col, 0)) as nb_col_total
            FROM frulog_lignes fl
            WHERE fl.type = 'E' AND fl.produit = 'PTC'
              AND fl.sur_emballage_id IS NULL
              AND fl.emballage IS NOT NULL
            GROUP BY fl.emballage
            ORDER BY nb_lignes DESC
        """)
        rows = cursor.fetchall(); cursor.close(); conn.close()
        return pd.DataFrame(rows) if rows else pd.DataFrame()
    except: return pd.DataFrame()


def sauver_mapping_produit(emballage, marque, code_produit, description=None):
    try:
        conn = get_connection(); cursor = conn.cursor()
        cle = make_cle_produit(emballage, marque)
        cursor.execute("""
            INSERT INTO frulog_mapping_produit (emballage, marque, cle_mapping, code_produit_commercial, description)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (cle_mapping) DO UPDATE SET
                code_produit_commercial = EXCLUDED.code_produit_commercial,
                description = EXCLUDED.description, updated_at = CURRENT_TIMESTAMP
            RETURNING id
        """, (emballage, marque, cle, code_produit, description))
        mid = cursor.fetchone()['id']
        # Mettre à jour les lignes existantes
        cursor.execute("""
            UPDATE frulog_lignes SET code_produit_commercial = %s
            WHERE emballage = %s AND (marque = %s OR (%s IS NULL AND marque IS NULL))
              AND code_produit_commercial IS NULL
        """, (code_produit, emballage, marque, marque))
        updated = cursor.rowcount
        conn.commit(); cursor.close(); conn.close()
        return True, f"Mapping #{mid} OK ({updated} lignes mises à jour)"
    except Exception as e:
        if 'conn' in locals(): conn.rollback()
        return False, str(e)


def modifier_mapping_produit(mapping_id, code_produit, description=None):
    try:
        conn = get_connection(); cursor = conn.cursor()
        cursor.execute("""
            UPDATE frulog_mapping_produit 
            SET code_produit_commercial = %s, description = %s, updated_at = CURRENT_TIMESTAMP
            WHERE id = %s RETURNING emballage, marque
        """, (code_produit, description, mapping_id))
        row = cursor.fetchone()
        if row:
            cursor.execute("""
                UPDATE frulog_lignes SET code_produit_commercial = %s
                WHERE emballage = %s AND (marque = %s OR (%s IS NULL AND marque IS NULL))
            """, (code_produit, row['emballage'], row['marque'], row['marque']))
        conn.commit(); cursor.close(); conn.close()
        return True, "Mapping modifié"
    except Exception as e:
        if 'conn' in locals(): conn.rollback()
        return False, str(e)


def sauver_mapping_suremballage(code_emballage, sur_emballage_id, description=None):
    try:
        conn = get_connection(); cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO frulog_mapping_suremballage (code_emballage, sur_emballage_id, description)
            VALUES (%s, %s, %s)
            ON CONFLICT (code_emballage) DO UPDATE SET
                sur_emballage_id = EXCLUDED.sur_emballage_id,
                description = EXCLUDED.description, updated_at = CURRENT_TIMESTAMP
            RETURNING id
        """, (code_emballage, sur_emballage_id, description))
        mid = cursor.fetchone()['id']
        cursor.execute("""
            UPDATE frulog_lignes SET sur_emballage_id = %s
            WHERE emballage = %s AND sur_emballage_id IS NULL
        """, (sur_emballage_id, code_emballage))
        updated = cursor.rowcount
        conn.commit(); cursor.close(); conn.close()
        return True, f"Mapping S-E #{mid} OK ({updated} lignes)"
    except Exception as e:
        if 'conn' in locals(): conn.rollback()
        return False, str(e)


def importer_fichier_frulog(uploaded_file, username='inconnu'):
    """Import complet fichier Excel Frulog"""
    try:
        df = pd.read_excel(uploaded_file, sheet_name=0)
        if len(df) == 0:
            return False, "Fichier vide"

        df_r = df.rename(columns=COLONNES_MAPPING)
        known = list(COLONNES_MAPPING.values())
        cols_ok = [c for c in known if c in df_r.columns]
        df_c = df_r[cols_ok].copy()

        for col in DATE_COLS:
            if col in df_c.columns:
                df_c[col] = pd.to_datetime(df_c[col], errors='coerce').dt.date
        for col in INT_COLS:
            if col in df_c.columns:
                df_c[col] = pd.to_numeric(df_c[col], errors='coerce')
        for col in NUMERIC_COLS:
            if col in df_c.columns:
                df_c[col] = pd.to_numeric(df_c[col], errors='coerce')

        text_cols = ['type','produit','variete','categ','calibre','couleur','emballage','marque','client','depot']
        for col in text_cols:
            if col in df_c.columns:
                df_c[col] = df_c[col].apply(
                    lambda x: None if pd.isna(x) or str(x).strip() == '.' else str(x).strip())

        if 'date_charg' in df_c.columns:
            df_c['annee'] = df_c['date_charg'].apply(
                lambda d: d.isocalendar()[0] if pd.notna(d) and d is not None else None)
            df_c['semaine'] = df_c['date_charg'].apply(
                lambda d: d.isocalendar()[1] if pd.notna(d) and d is not None else None)

        conn = get_connection(); cursor = conn.cursor()

        nb_total = len(df_c)
        nb_e = len(df_c[df_c.get('type', pd.Series()) == 'E']) if 'type' in df_c.columns else 0
        nb_a = len(df_c[df_c.get('type', pd.Series()) == 'A']) if 'type' in df_c.columns else 0
        d_min = df_c['date_charg'].dropna().min() if 'date_charg' in df_c.columns else None
        d_max = df_c['date_charg'].dropna().max() if 'date_charg' in df_c.columns else None

        cursor.execute("""
            INSERT INTO frulog_imports
                (nom_fichier, nb_lignes_total, nb_lignes_type_e, nb_lignes_type_a,
                 nb_lignes_sans_type, date_debut, date_fin, created_by)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id
        """, (uploaded_file.name, nb_total, nb_e, nb_a, nb_total-nb_e-nb_a, d_min, d_max, username))
        import_id = cursor.fetchone()['id']

        # Charger mappings existants
        cursor.execute("SELECT cle_mapping, code_produit_commercial FROM frulog_mapping_produit WHERE is_active=TRUE")
        map_produit = {r['cle_mapping']: r['code_produit_commercial'] for r in cursor.fetchall()}

        cursor.execute("SELECT code_emballage, sur_emballage_id FROM frulog_mapping_suremballage WHERE is_active=TRUE")
        map_se = {r['code_emballage']: r['sur_emballage_id'] for r in cursor.fetchall()}

        # Appliquer mappings
        df_c['code_produit_commercial'] = df_c.apply(
            lambda r: map_produit.get(make_cle_produit(r.get('emballage'), r.get('marque'))), axis=1)
        df_c['sur_emballage_id'] = df_c['emballage'].apply(
            lambda e: map_se.get(str(e).strip().upper()) if e and str(e).strip() != '.' else None)

        df_c['import_id'] = import_id
        insert_cols = ['import_id'] + cols_ok + ['code_produit_commercial', 'sur_emballage_id', 'annee', 'semaine']
        insert_cols = list(dict.fromkeys(insert_cols))

        placeholders = ', '.join(['%s'] * len(insert_cols))
        col_names = ', '.join(insert_cols)

        inserted = 0
        for _, row in df_c.iterrows():
            values = []
            for col in insert_cols:
                val = row.get(col)
                if val is None or (isinstance(val, float) and np.isnan(val)):
                    values.append(None)
                elif isinstance(val, (np.integer, np.int64)):
                    values.append(int(val))
                elif isinstance(val, (np.floating, np.float64)):
                    values.append(float(val))
                elif val is pd.NaT:
                    values.append(None)
                else:
                    values.append(val)
            cursor.execute(f"INSERT INTO frulog_lignes ({col_names}) VALUES ({placeholders})", values)
            inserted += 1

        conn.commit()
        nb_mapped = df_c['code_produit_commercial'].notna().sum()
        cursor.close(); conn.close()
        return True, f"Import #{import_id} : {inserted} lignes ({nb_e} expéd., {nb_a} avoirs). {nb_mapped}/{nb_total} mappées."
    except Exception as e:
        if 'conn' in locals(): conn.rollback()
        return False, f"Erreur : {str(e)}"


def get_kpis_frulog():
    try:
        conn = get_connection(); cursor = conn.cursor()
        cursor.execute("""
            SELECT COUNT(*) as total,
                COUNT(*) FILTER (WHERE type='E') as nb_exp,
                COUNT(DISTINCT client) FILTER (WHERE type='E') as nb_clients,
                COALESCE(SUM(pds_net) FILTER (WHERE type='E' AND produit='PTC'), 0) as pds_kg,
                COUNT(*) FILTER (WHERE code_produit_commercial IS NOT NULL AND type='E') as mappees,
                COUNT(*) FILTER (WHERE code_produit_commercial IS NULL AND type='E' AND produit='PTC') as non_mappees,
                COUNT(DISTINCT import_id) as nb_imports
            FROM frulog_lignes
        """)
        row = cursor.fetchone(); cursor.close(); conn.close()
        return row
    except: return None


def get_analyse_data(import_id=None):
    try:
        conn = get_connection(); cursor = conn.cursor()
        where = "WHERE fl.type='E' AND fl.produit='PTC'"
        params = []
        if import_id:
            where += " AND fl.import_id=%s"
            params.append(import_id)

        cursor.execute(f"""
            SELECT fl.client, COUNT(*) as nb, SUM(COALESCE(fl.pds_net,0)) as pds_kg,
                   SUM(COALESCE(fl.nb_col,0)) as colis, SUM(COALESCE(fl.montant_euro,0)) as ca
            FROM frulog_lignes fl {where} GROUP BY fl.client ORDER BY pds_kg DESC
        """, params)
        par_client = cursor.fetchall()

        cursor.execute(f"""
            SELECT fl.annee, fl.semaine, COUNT(*) as nb,
                   SUM(COALESCE(fl.pds_net,0)) as pds_kg, SUM(COALESCE(fl.nb_col,0)) as colis,
                   COUNT(DISTINCT fl.client) as clients
            FROM frulog_lignes fl {where} AND fl.annee IS NOT NULL
            GROUP BY fl.annee, fl.semaine ORDER BY fl.annee, fl.semaine
        """, params)
        par_semaine = cursor.fetchall()

        cursor.execute(f"""
            SELECT COALESCE(fl.code_produit_commercial, '❓ Non mappé') as produit,
                   COUNT(*) as nb, SUM(COALESCE(fl.pds_net,0)) as pds_kg,
                   SUM(COALESCE(fl.nb_col,0)) as colis
            FROM frulog_lignes fl {where}
            GROUP BY COALESCE(fl.code_produit_commercial, '❓ Non mappé') ORDER BY pds_kg DESC
        """, params)
        par_produit = cursor.fetchall()

        cursor.execute(f"""
            SELECT fl.variete, COUNT(*) as nb, SUM(COALESCE(fl.pds_net,0)) as pds_kg
            FROM frulog_lignes fl {where}
            GROUP BY fl.variete ORDER BY pds_kg DESC LIMIT 20
        """, params)
        par_variete = cursor.fetchall()

        cursor.close(); conn.close()
        return {
            'par_client': pd.DataFrame(par_client) if par_client else pd.DataFrame(),
            'par_semaine': pd.DataFrame(par_semaine) if par_semaine else pd.DataFrame(),
            'par_produit': pd.DataFrame(par_produit) if par_produit else pd.DataFrame(),
            'par_variete': pd.DataFrame(par_variete) if par_variete else pd.DataFrame()
        }
    except Exception as e:
        st.error(f"Erreur analyse : {str(e)}")
        return None


def get_comparaison_previsions():
    """Expédié (Frulog) vs Prévu (prévisions_ventes) par semaine/produit"""
    try:
        conn = get_connection(); cursor = conn.cursor()
        cursor.execute("""
            WITH expedie AS (
                SELECT code_produit_commercial, annee, semaine,
                       SUM(pds_net) / 1000.0 as tonnes_expediees
                FROM frulog_lignes
                WHERE type='E' AND produit='PTC' AND code_produit_commercial IS NOT NULL
                GROUP BY code_produit_commercial, annee, semaine
            ),
            prevu AS (
                SELECT code_produit_commercial, annee::int, semaine::int,
                       quantite_prevue_tonnes as tonnes_prevues
                FROM previsions_ventes
            )
            SELECT COALESCE(e.code_produit_commercial, p.code_produit_commercial) as produit,
                   COALESCE(e.annee, p.annee) as annee,
                   COALESCE(e.semaine, p.semaine) as semaine,
                   COALESCE(p.tonnes_prevues, 0) as prevu_t,
                   COALESCE(e.tonnes_expediees, 0) as expedie_t
            FROM expedie e
            FULL OUTER JOIN prevu p 
                ON e.code_produit_commercial = p.code_produit_commercial
                AND e.annee = p.annee AND e.semaine = p.semaine
            WHERE COALESCE(e.annee, p.annee) IS NOT NULL
            ORDER BY COALESCE(e.annee, p.annee), COALESCE(e.semaine, p.semaine), 
                     COALESCE(e.code_produit_commercial, p.code_produit_commercial)
        """)
        rows = cursor.fetchall(); cursor.close(); conn.close()
        if rows:
            df = pd.DataFrame(rows)
            df['ecart_t'] = df['expedie_t'].astype(float) - df['prevu_t'].astype(float)
            df['taux_realisation'] = df.apply(
                lambda r: (float(r['expedie_t']) / float(r['prevu_t']) * 100) 
                          if float(r['prevu_t']) > 0 else None, axis=1)
            return df
        return pd.DataFrame()
    except Exception as e:
        st.error(f"Erreur comparaison : {str(e)}")
        return pd.DataFrame()


# ============================================================================
# KPIs
# ============================================================================

kpis = get_kpis_frulog()
if kpis and kpis['total'] > 0:
    c1, c2, c3, c4, c5 = st.columns(5)
    with c1: st.metric("📊 Imports", kpis['nb_imports'])
    with c2: st.metric("🚚 Expéditions", kpis['nb_exp'])
    with c3: st.metric("⚖️ Tonnage", f"{float(kpis['pds_kg'])/1000:,.1f} T".replace(',', ' '))
    with c4: st.metric("👥 Clients", kpis['nb_clients'])
    with c5:
        tot = max(kpis['mappees'] + kpis['non_mappees'], 1)
        st.metric("🔗 Mapping", f"{kpis['mappees']*100/tot:.0f}%")

st.markdown("---")

tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📥 Import", "🔗 Mapping Produits", "📦 Mapping Sur-Emb.", "📈 Analyse", "🎯 Prévu vs Réel"
])

# ============================================================================
# TAB 1 : IMPORT
# ============================================================================

with tab1:
    st.subheader("📥 Importer un fichier Frulog")
    
    uploaded = st.file_uploader("Fichier Excel Frulog", type=['xlsx', 'xls'], key="frulog_upload")
    if uploaded:
        try:
            df_full = pd.read_excel(uploaded, sheet_name=0)
            pc1, pc2, pc3, pc4 = st.columns(4)
            with pc1: st.metric("Lignes", len(df_full))
            with pc2:
                nb_e = len(df_full[df_full['Type']=='E']) if 'Type' in df_full.columns else 0
                st.metric("Expéditions", nb_e)
            with pc3:
                nb_a = len(df_full[df_full['Type']=='A']) if 'Type' in df_full.columns else 0
                st.metric("Avoirs", nb_a)
            with pc4: st.metric("Colonnes", len(df_full.columns))
            
            st.dataframe(df_full.head(5), use_container_width=True, hide_index=True)
            
            if st.button("🚀 Lancer l'import", type="primary", use_container_width=True):
                uploaded.seek(0)
                with st.spinner("Import en cours..."):
                    ok, msg = importer_fichier_frulog(uploaded, st.session_state.get('username', 'inconnu'))
                if ok:
                    st.success(f"✅ {msg}")
                    st.rerun()
                else:
                    st.error(f"❌ {msg}")
        except Exception as e:
            st.error(f"Erreur lecture : {str(e)}")
    
    # Historique imports
    st.markdown("---")
    st.markdown("##### 📋 Historique des imports")
    df_imp = get_imports()
    if not df_imp.empty:
        st.dataframe(df_imp[['id','nom_fichier','date_import','nb_lignes_total',
                             'nb_lignes_type_e','nb_lignes_type_a','date_debut','date_fin','created_by']].rename(columns={
            'id':'ID','nom_fichier':'Fichier','date_import':'Date','nb_lignes_total':'Lignes',
            'nb_lignes_type_e':'Expéd.','nb_lignes_type_a':'Avoirs',
            'date_debut':'Début','date_fin':'Fin','created_by':'Par'
        }), use_container_width=True, hide_index=True)

# ============================================================================
# TAB 2 : MAPPING PRODUITS (emballage+marque → produit commercial)
# ============================================================================

with tab2:
    st.subheader("🔗 Mapping Emballage + Marque → Produit Commercial")
    
    # Non mappées en haut
    df_nm = get_combinaisons_non_mappees_produit()
    if not df_nm.empty:
        st.markdown(f"##### ⚠️ {len(df_nm)} combinaison(s) sans mapping")
        st.dataframe(df_nm.rename(columns={
            'emballage':'Emballage', 'marque':'Marque', 'nb_lignes':'Nb lignes',
            'pds_total_kg':'Pds total (kg)', 'nb_clients':'Nb clients'
        }), use_container_width=True, hide_index=True)
        
        st.markdown("---")
        st.markdown("##### ➕ Créer un mapping")
        produits = get_produits_commerciaux()
        if produits:
            ac1, ac2, ac3 = st.columns(3)
            with ac1:
                embs = sorted(df_nm['emballage'].dropna().unique().tolist())
                sel_emb = st.selectbox("Emballage Frulog", embs, key="mp_emb")
            with ac2:
                mrqs = sorted(df_nm['marque'].dropna().unique().tolist()) if 'marque' in df_nm.columns else []
                if mrqs:
                    sel_mrq = st.selectbox("Marque Frulog", ["(vide)"] + mrqs, key="mp_mrq")
                    sel_mrq = None if sel_mrq == "(vide)" else sel_mrq
                else:
                    sel_mrq = None
                    st.text("Marque : (vide)")
            with ac3:
                prod_labels = [f"{p['code_produit']} — {p['marque']} {p['libelle']}" for p in produits]
                prod_idx = st.selectbox("→ Produit POMI *", range(len(prod_labels)),
                                       format_func=lambda i: prod_labels[i], key="mp_prod")
                code_sel = produits[prod_idx]['code_produit']
            
            st.info(f"**{sel_emb}** | **{sel_mrq or '(vide)'}** → **{code_sel}**")
            
            if st.button("💾 Enregistrer", type="primary", key="btn_mp_save"):
                ok, msg = sauver_mapping_produit(sel_emb, sel_mrq, code_sel)
                if ok: st.success(f"✅ {msg}"); st.rerun()
                else: st.error(f"❌ {msg}")
    else:
        st.success("✅ Toutes les combinaisons sont mappées")
    
    # Mappings existants (modifiables)
    st.markdown("---")
    st.markdown("##### 📋 Mappings existants")
    df_mp = get_mapping_produit()
    if not df_mp.empty:
        produits = get_produits_commerciaux()
        prod_codes = [p['code_produit'] for p in produits]
        
        event = st.dataframe(
            df_mp[['id','emballage','marque','code_produit_commercial','libelle_produit']].rename(columns={
                'id':'ID','emballage':'Emballage','marque':'Marque',
                'code_produit_commercial':'Code Produit','libelle_produit':'Libellé'
            }), use_container_width=True, hide_index=True,
            on_select="rerun", selection_mode="single-row", key="table_mp"
        )
        
        sel = event.selection.rows if hasattr(event, 'selection') else []
        if sel:
            row_sel = df_mp.iloc[sel[0]]
            st.markdown(f"**Modifier** : {row_sel['emballage']} | {row_sel['marque'] or '(vide)'}")
            mod_c1, mod_c2 = st.columns(2)
            with mod_c1:
                prod_labels = [f"{p['code_produit']} — {p['marque']} {p['libelle']}" for p in produits]
                current_idx = prod_codes.index(row_sel['code_produit_commercial']) if row_sel['code_produit_commercial'] in prod_codes else 0
                new_idx = st.selectbox("Nouveau produit", range(len(prod_labels)),
                                      format_func=lambda i: prod_labels[i], index=current_idx, key="mp_mod_prod")
            with mod_c2:
                new_desc = st.text_input("Description", value=row_sel.get('description', '') or '', key="mp_mod_desc")
            
            if st.button("💾 Modifier", key="btn_mp_mod"):
                ok, msg = modifier_mapping_produit(int(row_sel['id']), produits[new_idx]['code_produit'], new_desc)
                if ok: st.success(f"✅ {msg}"); st.rerun()
                else: st.error(f"❌ {msg}")
    else:
        st.info("Aucun mapping produit configuré")

# ============================================================================
# TAB 3 : MAPPING SUR-EMBALLAGES (code emballage → sur-emballage)
# ============================================================================

with tab3:
    st.subheader("📦 Mapping Code Emballage → Sur-Emballage")
    
    df_nm_se = get_emballages_non_mappes_se()
    if not df_nm_se.empty:
        st.markdown(f"##### ⚠️ {len(df_nm_se)} code(s) emballage sans sur-emballage")
        st.dataframe(df_nm_se.rename(columns={
            'code_emballage':'Code Emballage', 'nb_lignes':'Nb lignes', 'nb_col_total':'Nb colis total'
        }), use_container_width=True, hide_index=True)
        
        st.markdown("---")
        st.markdown("##### ➕ Associer un sur-emballage")
        sur_embs = get_sur_emballages()
        if sur_embs:
            se1, se2 = st.columns(2)
            with se1:
                codes = sorted(df_nm_se['code_emballage'].tolist())
                sel_code = st.selectbox("Code emballage Frulog", codes, key="mse_code")
            with se2:
                se_labels = [f"{se['libelle']} ({se['nb_uvc']} UVC)" for se in sur_embs]
                se_idx = st.selectbox("→ Sur-emballage POMI *", range(len(se_labels)),
                                     format_func=lambda i: se_labels[i], key="mse_se")
                se_sel = sur_embs[se_idx]
            
            if st.button("💾 Enregistrer", type="primary", key="btn_mse_save"):
                ok, msg = sauver_mapping_suremballage(sel_code, int(se_sel['id']))
                if ok: st.success(f"✅ {msg}"); st.rerun()
                else: st.error(f"❌ {msg}")
        else:
            st.warning("Aucun sur-emballage dans le référentiel")
    else:
        st.success("✅ Tous les codes emballage sont associés")
    
    st.markdown("---")
    st.markdown("##### 📋 Associations existantes")
    df_mse = get_mapping_suremballage()
    if not df_mse.empty:
        st.dataframe(df_mse[['code_emballage','libelle_se','nb_uvc','description']].rename(columns={
            'code_emballage':'Code Emballage','libelle_se':'Sur-Emballage',
            'nb_uvc':'UVC','description':'Description'
        }), use_container_width=True, hide_index=True)

# ============================================================================
# TAB 4 : ANALYSE EXPÉDITIONS
# ============================================================================

with tab4:
    st.subheader("📈 Analyse des Expéditions")
    
    df_imp = get_imports()
    import_filter = None
    if not df_imp.empty:
        opts = ["Tous les imports"] + [
            f"#{int(r['id'])} — {r['nom_fichier']}" for _, r in df_imp.iterrows()
        ]
        sel = st.selectbox("Import", opts, key="ana_import")
        if sel != "Tous les imports":
            import_filter = int(sel.split('#')[1].split(' ')[0])
    
    data = get_analyse_data(import_filter)
    if data:
        # Évolution hebdo
        if not data['par_semaine'].empty:
            st.markdown("##### 📊 Évolution hebdomadaire")
            df_s = data['par_semaine'].copy()
            df_s['tonnes'] = df_s['pds_kg'].astype(float) / 1000
            df_s['label'] = df_s.apply(lambda r: f"S{int(r['semaine']):02d}/{int(r['annee'])}", axis=1)
            fig = go.Figure([go.Bar(x=df_s['label'], y=df_s['tonnes'], marker_color='#2196f3')])
            fig.update_layout(title="Expéditions PTC par semaine (T)", height=350,
                             xaxis_title="Semaine", yaxis_title="Tonnes")
            st.plotly_chart(fig, use_container_width=True)

        ac1, ac2 = st.columns(2)
        
        with ac1:
            if not data['par_client'].empty:
                st.markdown("##### 👥 Top 15 Clients")
                df_cli = data['par_client'].head(15).copy()
                df_cli['tonnes'] = df_cli['pds_kg'].astype(float) / 1000
                fig2 = px.bar(df_cli, x='client', y='tonnes', color='tonnes',
                             color_continuous_scale='blues')
                fig2.update_layout(height=400, xaxis_tickangle=-45, showlegend=False)
                st.plotly_chart(fig2, use_container_width=True)
        
        with ac2:
            if not data['par_variete'].empty:
                st.markdown("##### 🥔 Répartition variétés")
                df_v = data['par_variete'].head(10).copy()
                df_v['tonnes'] = df_v['pds_kg'].astype(float) / 1000
                fig3 = px.pie(df_v, names='variete', values='tonnes')
                fig3.update_layout(height=400)
                st.plotly_chart(fig3, use_container_width=True)
        
        if not data['par_produit'].empty:
            st.markdown("##### 🏷️ Par Produit Commercial")
            df_p = data['par_produit'].copy()
            df_p['tonnes'] = df_p['pds_kg'].astype(float) / 1000
            st.dataframe(
                df_p[['produit','nb','tonnes','colis']].rename(columns={
                    'produit':'Produit','nb':'Lignes','tonnes':'Tonnes','colis':'Colis'
                }), use_container_width=True, hide_index=True)
    else:
        st.info("📭 Importez des données pour voir les analyses")

# ============================================================================
# TAB 5 : PRÉVU VS RÉEL (comparaison prévisions)
# ============================================================================

with tab5:
    st.subheader("🎯 Prévu vs Réel — Fiabilité des Prévisions")
    st.caption("*Compare les prévisions commerciales avec les expéditions Frulog réelles*")
    
    df_comp = get_comparaison_previsions()
    
    if not df_comp.empty:
        # Fiabilité globale
        df_avec_prevu = df_comp[df_comp['prevu_t'].astype(float) > 0]
        if not df_avec_prevu.empty:
            taux_global = (df_avec_prevu['expedie_t'].astype(float).sum() / 
                          df_avec_prevu['prevu_t'].astype(float).sum()) * 100
        else:
            taux_global = 0
        
        total_prevu = df_comp['prevu_t'].astype(float).sum()
        total_exp = df_comp['expedie_t'].astype(float).sum()
        ecart = total_exp - total_prevu
        
        kc1, kc2, kc3, kc4 = st.columns(4)
        with kc1: st.metric("📊 Prévu total", f"{total_prevu:.1f} T")
        with kc2: st.metric("🚚 Expédié total", f"{total_exp:.1f} T")
        with kc3: st.metric("📐 Écart", f"{ecart:+.1f} T")
        with kc4: st.metric("🎯 Taux réalisation", f"{taux_global:.0f}%")
        
        st.markdown("---")
        
        # Fiabilité par semaine
        st.markdown("##### 📊 Fiabilité par semaine")
        df_sem = df_comp.groupby(['annee', 'semaine']).agg(
            prevu=('prevu_t', lambda x: x.astype(float).sum()),
            expedie=('expedie_t', lambda x: x.astype(float).sum())
        ).reset_index()
        df_sem['taux'] = df_sem.apply(
            lambda r: (r['expedie']/r['prevu']*100) if r['prevu'] > 0 else None, axis=1)
        df_sem['label'] = df_sem.apply(
            lambda r: f"S{int(r['semaine']):02d}/{int(r['annee'])}", axis=1)
        
        fig_comp = go.Figure()
        fig_comp.add_trace(go.Bar(x=df_sem['label'], y=df_sem['prevu'], name='Prévu',
                                  marker_color='#90CAF9'))
        fig_comp.add_trace(go.Bar(x=df_sem['label'], y=df_sem['expedie'], name='Expédié',
                                  marker_color='#1565C0'))
        fig_comp.update_layout(barmode='group', title="Prévu vs Expédié par semaine (T)",
                              height=400, xaxis_title="Semaine", yaxis_title="Tonnes")
        st.plotly_chart(fig_comp, use_container_width=True)
        
        # Taux par semaine
        if df_sem['taux'].notna().any():
            fig_taux = go.Figure()
            colors = ['#4CAF50' if t and 80 <= t <= 120 else '#FF9800' if t and (60 <= t < 80 or 120 < t <= 150) 
                      else '#F44336' for t in df_sem['taux']]
            fig_taux.add_trace(go.Bar(x=df_sem['label'], y=df_sem['taux'], marker_color=colors))
            fig_taux.add_hline(y=100, line_dash="dash", line_color="black", annotation_text="100%")
            fig_taux.update_layout(title="Taux de réalisation par semaine (%)",
                                  height=350, xaxis_title="Semaine", yaxis_title="%")
            st.plotly_chart(fig_taux, use_container_width=True)
        
        # Détail par produit
        st.markdown("---")
        st.markdown("##### 🏷️ Détail par produit")
        
        df_prod = df_comp.groupby('produit').agg(
            prevu=('prevu_t', lambda x: x.astype(float).sum()),
            expedie=('expedie_t', lambda x: x.astype(float).sum())
        ).reset_index()
        df_prod['ecart'] = df_prod['expedie'] - df_prod['prevu']
        df_prod['taux'] = df_prod.apply(
            lambda r: f"{r['expedie']/r['prevu']*100:.0f}%" if r['prevu'] > 0 else "—", axis=1)
        df_prod = df_prod.sort_values('prevu', ascending=False)
        
        st.dataframe(
            df_prod.rename(columns={
                'produit':'Produit', 'prevu':'Prévu (T)', 'expedie':'Expédié (T)',
                'ecart':'Écart (T)', 'taux':'Taux'
            }), use_container_width=True, hide_index=True
        )
        
        # Export
        st.markdown("---")
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine='openpyxl') as w:
            df_comp.to_excel(w, index=False, sheet_name='Détail')
            df_sem.to_excel(w, index=False, sheet_name='Par Semaine')
            df_prod.to_excel(w, index=False, sheet_name='Par Produit')
        st.download_button("📥 Export Excel complet", buf.getvalue(),
                          f"prevu_vs_reel_{datetime.now().strftime('%Y%m%d')}.xlsx",
                          "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                          use_container_width=True)
    else:
        st.info("📭 Aucune donnée de comparaison. Importez des données Frulog et vérifiez que les prévisions sont saisies.")

show_footer()
