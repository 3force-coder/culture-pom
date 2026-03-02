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
            WHERE fl.type = 'E' 
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
            WHERE fl.type = 'E' 
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
    """Import complet fichier Excel Frulog avec upsert sur no_de_bon"""
    try:
        df = pd.read_excel(uploaded_file, sheet_name=0)
        if len(df) == 0:
            return False, "Fichier vide"

        df_r = df.rename(columns=COLONNES_MAPPING)
        known = list(COLONNES_MAPPING.values())
        cols_ok = [c for c in known if c in df_r.columns]
        df_c = df_r[cols_ok].copy()

        # Vérifier que no_de_bon est présent
        if 'no_de_bon' not in df_c.columns:
            return False, "Colonne 'No de bon' introuvable dans le fichier"

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

        # Charger les no_de_bon déjà en base avec leurs champs de comparaison
        cursor.execute("""
            SELECT no_de_bon, etat, pds_net, montant_euro, type, nb_col
            FROM frulog_lignes WHERE no_de_bon IS NOT NULL
        """)
        existing = {}
        for r in cursor.fetchall():
            existing[r['no_de_bon']] = {
                'etat': r['etat'], 'pds_net': float(r['pds_net']) if r['pds_net'] else None,
                'montant_euro': float(r['montant_euro']) if r['montant_euro'] else None,
                'type': r['type'], 'nb_col': r['nb_col']
            }

        # Colonnes pour insert/update
        data_cols = [c for c in cols_ok if c != 'no_de_bon']
        data_cols += ['code_produit_commercial', 'sur_emballage_id', 'annee', 'semaine']
        data_cols = list(dict.fromkeys(data_cols))

        # Colonnes de comparaison pour détecter les changements
        compare_keys = ['etat', 'pds_net', 'montant_euro', 'type', 'nb_col']

        nb_new = 0
        nb_updated = 0
        nb_unchanged = 0

        def to_python(val):
            if val is None or (isinstance(val, float) and np.isnan(val)) or val is pd.NaT:
                return None
            elif isinstance(val, (np.integer, np.int64)):
                return int(val)
            elif isinstance(val, (np.floating, np.float64)):
                return float(val)
            return val

        for _, row in df_c.iterrows():
            bon = to_python(row.get('no_de_bon'))
            if not bon:
                continue

            row_values = {col: to_python(row.get(col)) for col in data_cols}

            if bon in existing:
                # Comparer les champs clés
                ex = existing[bon]
                changed = False
                for k in compare_keys:
                    new_val = to_python(row.get(k))
                    old_val = ex.get(k)
                    # Comparaison tolérante aux types
                    if str(new_val) != str(old_val):
                        changed = True
                        break

                if changed:
                    # UPDATE
                    set_parts = [f"{col} = %s" for col in data_cols]
                    set_parts.append("import_id = %s")
                    vals = [row_values[col] for col in data_cols] + [import_id, bon]
                    cursor.execute(
                        f"UPDATE frulog_lignes SET {', '.join(set_parts)} WHERE no_de_bon = %s",
                        vals
                    )
                    nb_updated += 1
                else:
                    nb_unchanged += 1
            else:
                # INSERT
                all_cols = ['import_id', 'no_de_bon'] + data_cols
                all_vals = [import_id, bon] + [row_values[col] for col in data_cols]
                placeholders = ', '.join(['%s'] * len(all_cols))
                cursor.execute(
                    f"INSERT INTO frulog_lignes ({', '.join(all_cols)}) VALUES ({placeholders})",
                    all_vals
                )
                nb_new += 1

        conn.commit()
        nb_mapped = df_c['code_produit_commercial'].notna().sum()
        cursor.close(); conn.close()

        return True, (f"Import #{import_id} : {nb_total} lignes traitées → "
                      f"**{nb_new} nouvelles**, **{nb_updated} modifiées**, "
                      f"{nb_unchanged} inchangées. "
                      f"{nb_mapped}/{nb_total} mappées.")
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
                COALESCE(SUM(pds_net) FILTER (WHERE type='E' ), 0) as pds_kg,
                COUNT(*) FILTER (WHERE code_produit_commercial IS NOT NULL AND type='E') as mappees,
                COUNT(*) FILTER (WHERE code_produit_commercial IS NULL AND type='E' ) as non_mappees,
                COUNT(DISTINCT import_id) as nb_imports
            FROM frulog_lignes
        """)
        row = cursor.fetchone(); cursor.close(); conn.close()
        return row
    except: return None



def get_analyse_complete():
    """Toutes les données d'analyse en une seule connexion"""
    try:
        conn = get_connection(); cursor = conn.cursor()
        results = {}

        # KPIs globaux
        cursor.execute("""
            SELECT COUNT(*) as total,
                COUNT(*) FILTER (WHERE type='E') as nb_exp,
                COUNT(*) FILTER (WHERE type='A') as nb_avoirs,
                COUNT(DISTINCT client) FILTER (WHERE type='E') as nb_clients,
                COALESCE(SUM(pds_net) FILTER (WHERE type='E'), 0) as pds_kg,
                COALESCE(SUM(montant) FILTER (WHERE type='E'), 0) as ca_total,
                COALESCE(AVG(prix) FILTER (WHERE type='E' AND prix > 0), 0) as prix_moy,
                COUNT(*) FILTER (WHERE code_produit_commercial IS NOT NULL AND type='E') as mappees,
                COUNT(*) FILTER (WHERE code_produit_commercial IS NULL AND type='E') as non_mappees,
                COUNT(DISTINCT import_id) as nb_imports,
                MIN(date_charg) FILTER (WHERE type='E') as date_min,
                MAX(date_charg) FILTER (WHERE type='E') as date_max,
                SUM(nb_col) FILTER (WHERE type='E') as nb_col_total,
                SUM(nb_pal) FILTER (WHERE type='E') as nb_pal_total,
                COUNT(DISTINCT variete) FILTER (WHERE type='E') as nb_varietes
            FROM frulog_lignes
        """)
        results['kpis'] = cursor.fetchone()

        # Par client
        cursor.execute("""
            SELECT client, COUNT(*) as nb_lignes,
                   SUM(COALESCE(pds_net,0)) as pds_kg, SUM(COALESCE(montant,0)) as ca,
                   SUM(COALESCE(nb_col,0)) as colis, COUNT(DISTINCT variete) as nb_varietes,
                   AVG(prix) FILTER (WHERE prix > 0) as prix_moy,
                   MIN(date_charg) as premiere_expe, MAX(date_charg) as derniere_expe
            FROM frulog_lignes WHERE type='E' GROUP BY client ORDER BY pds_kg DESC
        """)
        results['par_client'] = cursor.fetchall()

        # Par variété
        cursor.execute("""
            SELECT variete, COUNT(*) as nb_lignes,
                   SUM(COALESCE(pds_net,0)) as pds_kg, SUM(COALESCE(montant,0)) as ca,
                   COUNT(DISTINCT client) as nb_clients,
                   AVG(prix) FILTER (WHERE prix > 0) as prix_moy
            FROM frulog_lignes WHERE type='E' AND variete IS NOT NULL
            GROUP BY variete ORDER BY pds_kg DESC
        """)
        results['par_variete'] = cursor.fetchall()

        # Par mois
        cursor.execute("""
            SELECT EXTRACT(YEAR FROM date_charg)::int as annee,
                   EXTRACT(MONTH FROM date_charg)::int as mois,
                   COUNT(*) as nb_lignes, SUM(COALESCE(pds_net,0)) as pds_kg,
                   SUM(COALESCE(montant,0)) as ca, COUNT(DISTINCT client) as nb_clients
            FROM frulog_lignes WHERE type='E' AND date_charg IS NOT NULL
            GROUP BY 1, 2 ORDER BY annee, mois
        """)
        results['par_mois'] = cursor.fetchall()

        # Par semaine
        cursor.execute("""
            SELECT annee, semaine, COUNT(*) as nb_lignes,
                   SUM(COALESCE(pds_net,0)) as pds_kg, SUM(COALESCE(montant,0)) as ca,
                   COUNT(DISTINCT client) as nb_clients
            FROM frulog_lignes WHERE type='E' AND annee IS NOT NULL
            GROUP BY annee, semaine ORDER BY annee, semaine
        """)
        results['par_semaine'] = cursor.fetchall()

        # Par produit commercial
        cursor.execute("""
            SELECT COALESCE(code_produit_commercial, '❓ Non mappé') as produit,
                   COUNT(*) as nb_lignes, SUM(COALESCE(pds_net,0)) as pds_kg,
                   SUM(COALESCE(montant,0)) as ca, SUM(COALESCE(nb_col,0)) as colis,
                   COUNT(DISTINCT client) as nb_clients
            FROM frulog_lignes WHERE type='E'
            GROUP BY 1 ORDER BY pds_kg DESC
        """)
        results['par_produit'] = cursor.fetchall()

        # Par emballage
        cursor.execute("""
            SELECT emballage, COUNT(*) as nb_lignes,
                   SUM(COALESCE(pds_net,0)) as pds_kg, SUM(COALESCE(montant,0)) as ca,
                   SUM(COALESCE(nb_col,0)) as colis
            FROM frulog_lignes WHERE type='E' AND emballage IS NOT NULL
            GROUP BY emballage ORDER BY pds_kg DESC
        """)
        results['par_emballage'] = cursor.fetchall()

        # Par calibre
        cursor.execute("""
            SELECT calibre, COUNT(*) as nb_lignes,
                   SUM(COALESCE(pds_net,0)) as pds_kg, SUM(COALESCE(montant,0)) as ca,
                   COUNT(DISTINCT client) as nb_clients
            FROM frulog_lignes WHERE type='E' AND calibre IS NOT NULL
            GROUP BY calibre ORDER BY pds_kg DESC
        """)
        results['par_calibre'] = cursor.fetchall()

        # Par depot
        cursor.execute("""
            SELECT depot, COUNT(*) as nb_lignes,
                   SUM(COALESCE(pds_net,0)) as pds_kg, SUM(COALESCE(montant,0)) as ca
            FROM frulog_lignes WHERE type='E' AND depot IS NOT NULL AND depot != '.'
            GROUP BY depot ORDER BY pds_kg DESC
        """)
        results['par_depot'] = cursor.fetchall()

        # Par vendeur
        cursor.execute("""
            SELECT vendeur, COUNT(*) as nb_lignes,
                   SUM(COALESCE(pds_net,0)) as pds_kg, SUM(COALESCE(montant,0)) as ca,
                   COUNT(DISTINCT client) as nb_clients
            FROM frulog_lignes WHERE type='E' AND vendeur IS NOT NULL
            GROUP BY vendeur ORDER BY ca DESC
        """)
        results['par_vendeur'] = cursor.fetchall()

        # Par année
        cursor.execute("""
            SELECT EXTRACT(YEAR FROM date_charg)::int as annee,
                   SUM(COALESCE(pds_net,0)) as pds_kg, SUM(COALESCE(montant,0)) as ca,
                   COUNT(DISTINCT client) as nb_clients, COUNT(*) as nb_lignes
            FROM frulog_lignes WHERE type='E' AND date_charg IS NOT NULL
            GROUP BY 1 ORDER BY annee
        """)
        results['par_annee'] = cursor.fetchall()

        # Croisé client × variété top 50
        cursor.execute("""
            SELECT client, variete, SUM(COALESCE(pds_net,0)) as pds_kg,
                   SUM(COALESCE(montant,0)) as ca
            FROM frulog_lignes WHERE type='E' AND variete IS NOT NULL
            GROUP BY client, variete ORDER BY pds_kg DESC LIMIT 50
        """)
        results['croise_client_variete'] = cursor.fetchall()

        cursor.close(); conn.close()
        return results
    except Exception as e:
        st.error(f"Erreur analyse : {str(e)}")
        return None


def get_comparaison_previsions():
    """Expédié (Frulog) vs Prévu (prévisions_ventes)"""
    try:
        conn = get_connection(); cursor = conn.cursor()
        cursor.execute("""
            WITH expedie AS (
                SELECT code_produit_commercial, annee, semaine,
                       SUM(pds_net) / 1000.0 as tonnes_expediees
                FROM frulog_lignes
                WHERE type='E' AND code_produit_commercial IS NOT NULL
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
            ORDER BY COALESCE(e.annee, p.annee), COALESCE(e.semaine, p.semaine)
        """)
        rows = cursor.fetchall(); cursor.close(); conn.close()
        if rows:
            df = pd.DataFrame(rows)
            df['ecart_t'] = df['expedie_t'].astype(float) - df['prevu_t'].astype(float)
            df['taux_realisation'] = df.apply(
                lambda r: (float(r['expedie_t'])/float(r['prevu_t'])*100)
                          if float(r['prevu_t']) > 0 else None, axis=1)
            return df
        return pd.DataFrame()
    except Exception as e:
        st.error(f"Erreur comparaison : {str(e)}")
        return pd.DataFrame()


# ============================================================================
# CHARGEMENT DONNÉES
# ============================================================================

data = get_analyse_complete()

# ============================================================================
# KPIs
# ============================================================================

if data and data['kpis'] and data['kpis']['total'] > 0:
    k = data['kpis']
    c1, c2, c3, c4, c5, c6 = st.columns(6)
    with c1: st.metric("🚚 Expéditions", f"{k['nb_exp']:,}".replace(',', ' '))
    with c2: st.metric("⚖️ Tonnage", f"{float(k['pds_kg'])/1000:,.0f} T".replace(',', ' '))
    with c3: st.metric("💰 CA", f"{float(k['ca_total'])/1000:,.0f} k€".replace(',', ' '))
    with c4: st.metric("👥 Clients", k['nb_clients'])
    with c5: st.metric("🥔 Variétés", k['nb_varietes'])
    with c6:
        tot = max(k['mappees'] + k['non_mappees'], 1)
        st.metric("🔗 Mapping", f"{k['mappees']*100/tot:.0f}%")
    
    if k['date_min'] and k['date_max']:
        st.caption(f"📅 Période : {k['date_min'].strftime('%d/%m/%Y')} → {k['date_max'].strftime('%d/%m/%Y')} — "
                   f"Prix moyen : {float(k['prix_moy']):,.0f} €/T — "
                   f"{int(k['nb_col_total'] or 0):,} colis — {int(k['nb_pal_total'] or 0):,} palettes".replace(',', ' '))

st.markdown("---")

tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "📥 Import", "🔗 Mapping Produits", "📦 Mapping Sur-Emb.",
    "📈 Vue d'ensemble", "🔍 Analyses détaillées", "🎯 Prévu vs Réel"
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
# TAB 2 : MAPPING PRODUITS
# ============================================================================

with tab2:
    st.subheader("🔗 Mapping Emballage + Marque → Produit Commercial")
    
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
# TAB 3 : MAPPING SUR-EMBALLAGES
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
# TAB 4 : VUE D'ENSEMBLE
# ============================================================================

with tab4:
    if not data:
        st.info("📭 Importez des données Frulog pour voir les analyses")
    else:
        st.subheader("📈 Vue d'ensemble")
        
        # Évolution annuelle
        if data['par_annee']:
            df_a = pd.DataFrame(data['par_annee'])
            df_a['tonnes'] = df_a['pds_kg'].astype(float) / 1000
            df_a['ca_k'] = df_a['ca'].astype(float) / 1000
            
            ga1, ga2 = st.columns(2)
            with ga1:
                fig_a = go.Figure()
                fig_a.add_trace(go.Bar(x=df_a['annee'].astype(str), y=df_a['tonnes'],
                                       marker_color='#1565C0', name='Tonnes'))
                fig_a.update_layout(title="Tonnage par année", height=350, xaxis_title="Année",
                                   yaxis_title="Tonnes")
                st.plotly_chart(fig_a, use_container_width=True)
            with ga2:
                fig_ca = go.Figure()
                fig_ca.add_trace(go.Bar(x=df_a['annee'].astype(str), y=df_a['ca_k'],
                                        marker_color='#2E7D32', name='CA k€'))
                fig_ca.update_layout(title="Chiffre d'affaires par année", height=350,
                                    xaxis_title="Année", yaxis_title="k€")
                st.plotly_chart(fig_ca, use_container_width=True)
            
            st.dataframe(df_a.rename(columns={
                'annee':'Année','tonnes':'Tonnes','ca_k':'CA (k€)',
                'nb_clients':'Clients','nb_lignes':'Expéditions'
            })[['Année','Tonnes','CA (k€)','Clients','Expéditions']],
                use_container_width=True, hide_index=True)

        # Évolution mensuelle
        if data['par_mois']:
            st.markdown("---")
            st.markdown("##### 📅 Évolution mensuelle")
            df_m = pd.DataFrame(data['par_mois'])
            df_m['tonnes'] = df_m['pds_kg'].astype(float) / 1000
            df_m['label'] = df_m.apply(lambda r: f"{int(r['mois']):02d}/{int(r['annee'])}", axis=1)
            
            fig_m = go.Figure()
            fig_m.add_trace(go.Scatter(x=df_m['label'], y=df_m['tonnes'], mode='lines+markers',
                                       line=dict(color='#1565C0', width=2), fill='tozeroy'))
            fig_m.update_layout(title="Tonnage mensuel", height=400,
                               xaxis_title="Mois", yaxis_title="Tonnes",
                               xaxis=dict(tickangle=-45))
            st.plotly_chart(fig_m, use_container_width=True)

        # Évolution hebdo (dernières 52 semaines)
        if data['par_semaine']:
            st.markdown("---")
            st.markdown("##### 📊 Évolution hebdomadaire")
            df_s = pd.DataFrame(data['par_semaine'])
            df_s['tonnes'] = df_s['pds_kg'].astype(float) / 1000
            df_s['label'] = df_s.apply(lambda r: f"S{int(r['semaine']):02d}/{int(r['annee'])}", axis=1)
            # Garder les 52 dernières semaines
            df_s_last = df_s.tail(52)
            
            fig_s = go.Figure()
            fig_s.add_trace(go.Bar(x=df_s_last['label'], y=df_s_last['tonnes'],
                                   marker_color='#42A5F5'))
            fig_s.update_layout(title="Expéditions par semaine — 12 derniers mois (T)",
                               height=400, xaxis_title="Semaine", yaxis_title="Tonnes",
                               xaxis=dict(tickangle=-45))
            st.plotly_chart(fig_s, use_container_width=True)

# ============================================================================
# TAB 5 : ANALYSES DÉTAILLÉES
# ============================================================================

with tab5:
    if not data:
        st.info("📭 Importez des données Frulog")
    else:
        vue = st.radio("Analyser par :", ["👥 Clients", "🥔 Variétés", "🏷️ Produits", "📦 Emballages",
                                          "📏 Calibres", "🏢 Dépôts", "👤 Vendeurs", "🔀 Croisé Client×Variété"],
                       horizontal=True)
        st.markdown("---")
        
        def fmt_t(kg):
            return f"{float(kg)/1000:,.1f}".replace(',', ' ')
        def fmt_k(v):
            return f"{float(v)/1000:,.0f}".replace(',', ' ')
        def fmt_prix(v):
            return f"{float(v):,.0f}".replace(',', ' ') if v else "—"
        
        # --- CLIENTS ---
        if vue == "👥 Clients" and data['par_client']:
            df = pd.DataFrame(data['par_client'])
            df['tonnes'] = df['pds_kg'].astype(float) / 1000
            df['ca_k'] = df['ca'].astype(float) / 1000
            
            st.markdown(f"##### 👥 {len(df)} clients")
            
            gc1, gc2 = st.columns(2)
            with gc1:
                fig = px.bar(df.head(20), x='client', y='tonnes', title="Top 20 Clients (Tonnage)",
                            color='tonnes', color_continuous_scale='blues')
                fig.update_layout(height=450, xaxis_tickangle=-45, showlegend=False)
                st.plotly_chart(fig, use_container_width=True)
            with gc2:
                fig2 = px.bar(df.head(20), x='client', y='ca_k', title="Top 20 Clients (CA k€)",
                             color='ca_k', color_continuous_scale='greens')
                fig2.update_layout(height=450, xaxis_tickangle=-45, showlegend=False)
                st.plotly_chart(fig2, use_container_width=True)
            
            # Pareto
            df_sorted = df.sort_values('ca', ascending=False).copy()
            df_sorted['ca_cumul'] = df_sorted['ca'].astype(float).cumsum()
            ca_total = df_sorted['ca'].astype(float).sum()
            df_sorted['pct_cumul'] = df_sorted['ca_cumul'] / ca_total * 100
            nb_80 = len(df_sorted[df_sorted['pct_cumul'] <= 80]) + 1
            st.info(f"📊 **Pareto** : {nb_80} clients représentent 80% du CA ({nb_80*100//len(df)}% du portefeuille)")
            
            st.dataframe(df[['client','tonnes','ca_k','colis','nb_varietes','prix_moy',
                            'premiere_expe','derniere_expe']].rename(columns={
                'client':'Client','tonnes':'Tonnes','ca_k':'CA (k€)','colis':'Colis',
                'nb_varietes':'Variétés','prix_moy':'Prix moy (€/T)',
                'premiere_expe':'1ère expéd.','derniere_expe':'Dernière'
            }).head(50), use_container_width=True, hide_index=True,
                column_config={
                    'Prix moy (€/T)': st.column_config.NumberColumn(format="%.0f"),
                    '1ère expéd.': st.column_config.DateColumn(format='DD/MM/YYYY'),
                    'Dernière': st.column_config.DateColumn(format='DD/MM/YYYY'),
                })
            
            # Export
            buf = io.BytesIO()
            df.to_excel(buf, index=False, engine='openpyxl')
            st.download_button("📥 Export clients complet", buf.getvalue(),
                              f"clients_frulog_{datetime.now().strftime('%Y%m%d')}.xlsx",
                              use_container_width=True)
        
        # --- VARIÉTÉS ---
        elif vue == "🥔 Variétés" and data['par_variete']:
            df = pd.DataFrame(data['par_variete'])
            df['tonnes'] = df['pds_kg'].astype(float) / 1000
            df['ca_k'] = df['ca'].astype(float) / 1000
            
            st.markdown(f"##### 🥔 {len(df)} variétés")
            
            gv1, gv2 = st.columns(2)
            with gv1:
                fig = px.pie(df.head(15), names='variete', values='tonnes',
                            title="Top 15 Variétés (Tonnage)")
                fig.update_layout(height=450)
                st.plotly_chart(fig, use_container_width=True)
            with gv2:
                fig2 = px.bar(df.head(15), x='variete', y='prix_moy',
                             title="Prix moyen par variété (€/T)", color='prix_moy',
                             color_continuous_scale='YlOrRd')
                fig2.update_layout(height=450, showlegend=False)
                st.plotly_chart(fig2, use_container_width=True)
            
            st.dataframe(df[['variete','tonnes','ca_k','nb_clients','prix_moy','nb_lignes']].rename(columns={
                'variete':'Variété','tonnes':'Tonnes','ca_k':'CA (k€)',
                'nb_clients':'Clients','prix_moy':'Prix moy (€/T)','nb_lignes':'Expéditions'
            }).head(30), use_container_width=True, hide_index=True,
                column_config={'Prix moy (€/T)': st.column_config.NumberColumn(format="%.0f")})
        
        # --- PRODUITS COMMERCIAUX ---
        elif vue == "🏷️ Produits" and data['par_produit']:
            df = pd.DataFrame(data['par_produit'])
            df['tonnes'] = df['pds_kg'].astype(float) / 1000
            df['ca_k'] = df['ca'].astype(float) / 1000
            
            st.markdown(f"##### 🏷️ Par Produit Commercial")
            fig = px.bar(df, x='produit', y='tonnes', title="Tonnage par produit",
                        color='tonnes', color_continuous_scale='blues')
            fig.update_layout(height=400, xaxis_tickangle=-45, showlegend=False)
            st.plotly_chart(fig, use_container_width=True)
            
            st.dataframe(df[['produit','tonnes','ca_k','colis','nb_clients','nb_lignes']].rename(columns={
                'produit':'Produit','tonnes':'Tonnes','ca_k':'CA (k€)',
                'colis':'Colis','nb_clients':'Clients','nb_lignes':'Lignes'
            }), use_container_width=True, hide_index=True)
        
        # --- EMBALLAGES ---
        elif vue == "📦 Emballages" and data['par_emballage']:
            df = pd.DataFrame(data['par_emballage'])
            df['tonnes'] = df['pds_kg'].astype(float) / 1000
            
            st.markdown(f"##### 📦 {len(df)} types d'emballage")
            fig = px.pie(df.head(10), names='emballage', values='tonnes',
                        title="Répartition par emballage (Tonnage)")
            fig.update_layout(height=400)
            st.plotly_chart(fig, use_container_width=True)
            
            st.dataframe(df[['emballage','tonnes','colis','nb_lignes']].rename(columns={
                'emballage':'Emballage','tonnes':'Tonnes','colis':'Colis','nb_lignes':'Lignes'
            }), use_container_width=True, hide_index=True)
        
        # --- CALIBRES ---
        elif vue == "📏 Calibres" and data['par_calibre']:
            df = pd.DataFrame(data['par_calibre'])
            df['tonnes'] = df['pds_kg'].astype(float) / 1000
            
            st.markdown(f"##### 📏 {len(df)} calibres")
            fig = px.bar(df, x='calibre', y='tonnes', title="Tonnage par calibre",
                        color='tonnes', color_continuous_scale='purples')
            fig.update_layout(height=400, showlegend=False)
            st.plotly_chart(fig, use_container_width=True)
            
            st.dataframe(df[['calibre','tonnes','nb_clients','nb_lignes']].rename(columns={
                'calibre':'Calibre','tonnes':'Tonnes','nb_clients':'Clients','nb_lignes':'Lignes'
            }), use_container_width=True, hide_index=True)
        
        # --- DÉPÔTS ---
        elif vue == "🏢 Dépôts" and data['par_depot']:
            df = pd.DataFrame(data['par_depot'])
            df['tonnes'] = df['pds_kg'].astype(float) / 1000
            df['ca_k'] = df['ca'].astype(float) / 1000
            
            st.markdown(f"##### 🏢 {len(df)} dépôts")
            fig = px.bar(df.head(20), x='depot', y='tonnes', title="Top 20 Dépôts (Tonnage)",
                        color='tonnes', color_continuous_scale='oranges')
            fig.update_layout(height=400, xaxis_tickangle=-45, showlegend=False)
            st.plotly_chart(fig, use_container_width=True)
            
            st.dataframe(df[['depot','tonnes','ca_k','nb_lignes']].head(30).rename(columns={
                'depot':'Dépôt','tonnes':'Tonnes','ca_k':'CA (k€)','nb_lignes':'Lignes'
            }), use_container_width=True, hide_index=True)
        
        # --- VENDEURS ---
        elif vue == "👤 Vendeurs" and data['par_vendeur']:
            df = pd.DataFrame(data['par_vendeur'])
            df['tonnes'] = df['pds_kg'].astype(float) / 1000
            df['ca_k'] = df['ca'].astype(float) / 1000
            
            st.markdown(f"##### 👤 {len(df)} vendeurs")
            fig = px.bar(df, x='vendeur', y='ca_k', title="CA par vendeur (k€)",
                        color='ca_k', color_continuous_scale='greens')
            fig.update_layout(height=400, showlegend=False)
            st.plotly_chart(fig, use_container_width=True)
            
            st.dataframe(df[['vendeur','tonnes','ca_k','nb_clients','nb_lignes']].rename(columns={
                'vendeur':'Vendeur','tonnes':'Tonnes','ca_k':'CA (k€)',
                'nb_clients':'Clients','nb_lignes':'Lignes'
            }), use_container_width=True, hide_index=True)
        
        # --- CROISÉ CLIENT × VARIÉTÉ ---
        elif vue == "🔀 Croisé Client×Variété" and data['croise_client_variete']:
            df = pd.DataFrame(data['croise_client_variete'])
            df['tonnes'] = df['pds_kg'].astype(float) / 1000
            df['ca_k'] = df['ca'].astype(float) / 1000
            
            st.markdown("##### 🔀 Top 50 combinaisons Client × Variété")
            st.dataframe(df[['client','variete','tonnes','ca_k']].rename(columns={
                'client':'Client','variete':'Variété','tonnes':'Tonnes','ca_k':'CA (k€)'
            }), use_container_width=True, hide_index=True)
            
            # Heatmap top 10 clients × top 10 variétés
            top_clients = df.groupby('client')['pds_kg'].sum().nlargest(10).index.tolist()
            top_var = df.groupby('variete')['pds_kg'].sum().nlargest(10).index.tolist()
            df_heat = df[df['client'].isin(top_clients) & df['variete'].isin(top_var)]
            
            if not df_heat.empty:
                pivot = df_heat.pivot_table(values='tonnes', index='client', columns='variete', fill_value=0)
                fig = px.imshow(pivot, title="Heatmap Top 10 Clients × Top 10 Variétés (T)",
                               color_continuous_scale='Blues', aspect='auto')
                fig.update_layout(height=500)
                st.plotly_chart(fig, use_container_width=True)

# ============================================================================
# TAB 6 : PRÉVU VS RÉEL
# ============================================================================

with tab6:
    st.subheader("🎯 Prévu vs Réel — Fiabilité des Prévisions")
    
    df_comp = get_comparaison_previsions()
    
    if not df_comp.empty:
        df_avec_prevu = df_comp[df_comp['prevu_t'].astype(float) > 0]
        taux_global = ((df_avec_prevu['expedie_t'].astype(float).sum() /
                       df_avec_prevu['prevu_t'].astype(float).sum()) * 100) if not df_avec_prevu.empty else 0
        total_prevu = df_comp['prevu_t'].astype(float).sum()
        total_exp = df_comp['expedie_t'].astype(float).sum()
        ecart = total_exp - total_prevu
        
        kc1, kc2, kc3, kc4 = st.columns(4)
        with kc1: st.metric("📊 Prévu", f"{total_prevu:.1f} T")
        with kc2: st.metric("🚚 Expédié", f"{total_exp:.1f} T")
        with kc3: st.metric("📐 Écart", f"{ecart:+.1f} T")
        with kc4: st.metric("🎯 Réalisation", f"{taux_global:.0f}%")
        
        st.markdown("---")
        
        # Par semaine
        st.markdown("##### 📊 Prévu vs Expédié par semaine")
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
        fig_comp.update_layout(barmode='group', title="Prévu vs Expédié (T)",
                              height=400, xaxis_title="Semaine", yaxis_title="Tonnes")
        st.plotly_chart(fig_comp, use_container_width=True)
        
        # Taux fiabilité coloré
        if df_sem['taux'].notna().any():
            fig_t = go.Figure()
            colors = ['#4CAF50' if t and 80 <= t <= 120 else '#FF9800' if t and (60 <= t < 80 or 120 < t <= 150)
                      else '#F44336' for t in df_sem['taux']]
            fig_t.add_trace(go.Bar(x=df_sem['label'], y=df_sem['taux'], marker_color=colors))
            fig_t.add_hline(y=100, line_dash="dash", line_color="black", annotation_text="100%")
            fig_t.update_layout(title="Taux de réalisation par semaine (%)", height=350)
            st.plotly_chart(fig_t, use_container_width=True)
        
        # Par produit
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
        
        st.dataframe(df_prod.rename(columns={
            'produit':'Produit','prevu':'Prévu (T)','expedie':'Expédié (T)',
            'ecart':'Écart (T)','taux':'Taux'
        }), use_container_width=True, hide_index=True)
        
        # Export
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine='openpyxl') as w:
            df_comp.to_excel(w, index=False, sheet_name='Détail')
            df_sem.to_excel(w, index=False, sheet_name='Par Semaine')
            df_prod.to_excel(w, index=False, sheet_name='Par Produit')
        st.download_button("📥 Export Excel", buf.getvalue(),
                          f"prevu_vs_reel_{datetime.now().strftime('%Y%m%d')}.xlsx",
                          use_container_width=True)
    else:
        st.info("📭 Aucune donnée. Importez des données Frulog et/ou saisissez des prévisions.")

show_footer()
