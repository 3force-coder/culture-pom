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

st.set_page_config(page_title="Produits Finis - POMI", page_icon="📦", layout="wide")

# CSS compact
st.markdown("""
<style>
    .block-container {
        padding-top: 2rem !important;
        padding-bottom: 0.5rem !important;
        padding-left: 2rem !important;
        padding-right: 2rem !important;
    }
    h1, h2, h3, h4 {
        margin-top: 0.3rem !important;
        margin-bottom: 0.3rem !important;
    }
    .stSelectbox, .stButton, .stCheckbox {
        margin-bottom: 0.3rem !important;
        margin-top: 0.3rem !important;
    }
    [data-testid="stMetricValue"] {
        font-size: 1.4rem !important;
    }
    [data-testid="metric-container"] {
        padding: 0.3rem !important;
    }
    hr {
        margin-top: 0.5rem !important;
        margin-bottom: 0.5rem !important;
    }
</style>
""", unsafe_allow_html=True)

# ⭐ CONTRÔLE D'ACCÈS RBAC
require_access("STOCK")

st.title("📦 Stock Produits Finis")
st.caption("*Suivi des entrées/sorties par produit commercial — Modèle par mouvements*")
st.markdown("---")

# ============================================================================
# FONCTIONS UTILITAIRES
# ============================================================================

def format_number_fr(value):
    if pd.isna(value) or value is None:
        return "0"
    try:
        return f"{int(value):,}".replace(',', ' ')
    except (ValueError, TypeError):
        return str(value)

def format_tonnes(value):
    if pd.isna(value) or value is None:
        return "0.00 T"
    try:
        return f"{float(value):,.2f} T".replace(',', ' ')
    except (ValueError, TypeError):
        return str(value)

def format_kg(value):
    if pd.isna(value) or value is None:
        return "0 kg"
    try:
        return f"{float(value):,.0f} kg".replace(',', ' ')
    except (ValueError, TypeError):
        return str(value)

def normaliser_poids_kg(poids, unite):
    """Convertit un poids en KG quelle que soit l'unité source"""
    if not poids or poids == 0:
        return 0
    poids = float(poids)
    unite = (unite or 'KG').upper().strip()
    if unite == 'G':
        return poids / 1000
    elif unite == 'T':
        return poids * 1000
    else:  # KG par défaut
        return poids

# ============================================================================
# FONCTIONS BDD
# ============================================================================

def get_stock_actuel():
    """Calcule le stock actuel par produit (somme des mouvements)"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT 
                m.code_produit_commercial,
                COALESCE(pc.marque, '') as marque,
                COALESCE(pc.libelle, m.code_produit_commercial) as libelle,
                COALESCE(pc.code_variete, '') as variete,
                SUM(m.quantite_tonnes) as stock_tonnes,
                SUM(m.poids_total_kg) as stock_kg,
                SUM(m.nb_sur_emballages) as total_sur_emb,
                SUM(m.nb_uvc) as total_uvc,
                COUNT(*) FILTER (WHERE m.quantite_tonnes > 0) as nb_entrees,
                COUNT(*) FILTER (WHERE m.quantite_tonnes < 0) as nb_sorties,
                COALESCE(SUM(m.quantite_tonnes) FILTER (WHERE m.quantite_tonnes > 0), 0) as total_entrees_t,
                COALESCE(ABS(SUM(m.quantite_tonnes) FILTER (WHERE m.quantite_tonnes < 0)), 0) as total_sorties_t,
                MAX(m.date_mouvement) as dernier_mouvement
            FROM mouvements_produits_finis m
            LEFT JOIN ref_produits_commerciaux pc 
                ON m.code_produit_commercial = pc.code_produit
            GROUP BY m.code_produit_commercial, pc.marque, pc.libelle, pc.code_variete
            ORDER BY SUM(m.quantite_tonnes) DESC
        """)
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        
        if rows:
            df = pd.DataFrame(rows)
            for col in ['stock_tonnes', 'stock_kg', 'total_entrees_t', 'total_sorties_t', 
                        'total_sur_emb', 'total_uvc']:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
            return df
        return pd.DataFrame()
    except Exception as e:
        st.error(f"Erreur chargement stock : {str(e)}")
        return pd.DataFrame()


def get_kpis():
    """Récupère les KPIs globaux"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Stock total
        cursor.execute("""
            SELECT 
                COALESCE(SUM(quantite_tonnes), 0) as stock_total_t,
                COALESCE(SUM(poids_total_kg), 0) as stock_total_kg,
                COALESCE(SUM(nb_uvc), 0) as stock_total_uvc
            FROM mouvements_produits_finis
        """)
        totaux = cursor.fetchone()
        
        # Nb produits en stock
        cursor.execute("""
            SELECT COUNT(*) as cnt FROM (
                SELECT code_produit_commercial 
                FROM mouvements_produits_finis 
                GROUP BY code_produit_commercial 
                HAVING SUM(quantite_tonnes) > 0
            ) sub
        """)
        nb_en_stock = cursor.fetchone()['cnt']
        
        # Entrées/Sorties semaine en cours
        iso = date.today().isocalendar()
        cursor.execute("""
            SELECT 
                COALESCE(SUM(quantite_tonnes) FILTER (WHERE quantite_tonnes > 0), 0) as entrees_sem,
                COALESCE(ABS(SUM(quantite_tonnes) FILTER (WHERE quantite_tonnes < 0)), 0) as sorties_sem
            FROM mouvements_produits_finis
            WHERE annee = %s AND semaine = %s
        """, (iso[0], iso[1]))
        sem = cursor.fetchone()
        
        # Top 3
        cursor.execute("""
            SELECT code_produit_commercial, SUM(quantite_tonnes) as stock
            FROM mouvements_produits_finis
            GROUP BY code_produit_commercial
            HAVING SUM(quantite_tonnes) > 0
            ORDER BY stock DESC
            LIMIT 3
        """)
        top3 = cursor.fetchall()
        
        # Total mouvements
        cursor.execute("SELECT COUNT(*) as cnt FROM mouvements_produits_finis")
        nb_mvt = cursor.fetchone()['cnt']
        
        cursor.close()
        conn.close()
        
        return {
            'stock_total_t': float(totaux['stock_total_t']) if totaux else 0,
            'stock_total_kg': float(totaux['stock_total_kg']) if totaux else 0,
            'stock_total_uvc': int(totaux['stock_total_uvc'] or 0) if totaux else 0,
            'nb_en_stock': nb_en_stock,
            'entrees_sem': float(sem['entrees_sem']) if sem else 0,
            'sorties_sem': float(sem['sorties_sem']) if sem else 0,
            'top3': top3 or [],
            'nb_mvt': nb_mvt
        }
    except Exception as e:
        st.error(f"Erreur KPIs : {str(e)}")
        return None


def get_mouvements(code_produit=None, type_mouvement=None, date_debut=None, date_fin=None, limit=200):
    """Récupère l'historique des mouvements"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        query = """
            SELECT 
                m.id, m.code_produit_commercial,
                COALESCE(pc.libelle, m.code_produit_commercial) as libelle_produit,
                m.type_mouvement, m.quantite_tonnes, m.poids_total_kg,
                m.nb_sur_emballages, m.nb_uvc, m.poids_unitaire_kg,
                COALESCE(se.libelle, '') as sur_emballage,
                m.date_mouvement, m.annee, m.semaine,
                m.source, m.reference, m.client, m.notes,
                m.created_by, m.created_at
            FROM mouvements_produits_finis m
            LEFT JOIN ref_produits_commerciaux pc ON m.code_produit_commercial = pc.code_produit
            LEFT JOIN ref_sur_emballages se ON m.sur_emballage_id = se.id
            WHERE 1=1
        """
        params = []
        
        if code_produit and code_produit != "Tous":
            query += " AND m.code_produit_commercial = %s"
            params.append(code_produit)
        if type_mouvement and type_mouvement != "Tous":
            query += " AND m.type_mouvement = %s"
            params.append(type_mouvement)
        if date_debut:
            query += " AND m.date_mouvement >= %s"
            params.append(date_debut)
        if date_fin:
            query += " AND m.date_mouvement <= %s"
            params.append(date_fin)
        
        query += f" ORDER BY m.date_mouvement DESC, m.id DESC LIMIT {int(limit)}"
        cursor.execute(query, params)
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        
        if rows:
            df = pd.DataFrame(rows)
            df['quantite_tonnes'] = pd.to_numeric(df['quantite_tonnes'], errors='coerce').fillna(0)
            return df
        return pd.DataFrame()
    except Exception as e:
        st.error(f"Erreur mouvements : {str(e)}")
        return pd.DataFrame()


def get_evolution_stock(nb_semaines=12):
    """Évolution du stock par semaine pour le graphique"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            WITH cumul AS (
                SELECT 
                    annee, semaine,
                    SUM(quantite_tonnes) as mvt_semaine,
                    SUM(SUM(quantite_tonnes)) OVER (ORDER BY annee, semaine) as stock_cumule
                FROM mouvements_produits_finis
                GROUP BY annee, semaine
            )
            SELECT * FROM cumul ORDER BY annee DESC, semaine DESC LIMIT %s
        """, (nb_semaines,))
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        
        if rows:
            df = pd.DataFrame(rows)
            df['semaine_label'] = df.apply(
                lambda r: f"S{int(r['semaine']):02d}/{int(r['annee'])}", axis=1)
            return df.sort_values(['annee', 'semaine'])
        return pd.DataFrame()
    except Exception as e:
        st.error(f"Erreur évolution : {str(e)}")
        return pd.DataFrame()


def get_produits_commerciaux_actifs():
    """Liste des produits commerciaux actifs avec poids"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT code_produit, marque, libelle, poids_unitaire, unite_poids
            FROM ref_produits_commerciaux
            WHERE is_active = TRUE
            ORDER BY marque, libelle
        """)
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        return rows if rows else []
    except Exception as e:
        return []


def get_sur_emballages_actifs():
    """Liste des sur-emballages actifs"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, code_sur_emballage, libelle, nb_uvc, prix_unitaire, cout_tonne
            FROM ref_sur_emballages
            WHERE is_active = TRUE
            ORDER BY libelle
        """)
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        return rows if rows else []
    except Exception as e:
        return []


def ajouter_mouvement(code_produit, type_mouvement, date_mouvement,
                      sur_emballage_id, nb_sur_emballages, nb_uvc, 
                      poids_unitaire_kg, poids_total_kg, quantite_tonnes,
                      source='MANUEL', reference=None, client=None, 
                      notes=None, created_by=None):
    """Ajoute un mouvement de stock produit fini"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        iso = date_mouvement.isocalendar()
        
        # Signe : positif pour entrée, négatif pour sortie
        if type_mouvement in ('EXPEDITION', 'CORRECTION_SORTIE', 'IMPORT_FRULOG'):
            quantite_tonnes = -abs(float(quantite_tonnes))
            poids_total_kg = -abs(float(poids_total_kg))
            nb_sur_emballages = -abs(int(nb_sur_emballages))
            nb_uvc = -abs(int(nb_uvc))
        else:
            quantite_tonnes = abs(float(quantite_tonnes))
            poids_total_kg = abs(float(poids_total_kg))
            nb_sur_emballages = abs(int(nb_sur_emballages))
            nb_uvc = abs(int(nb_uvc))
        
        cursor.execute("""
            INSERT INTO mouvements_produits_finis 
                (code_produit_commercial, type_mouvement, quantite_tonnes,
                 date_mouvement, annee, semaine, 
                 sur_emballage_id, nb_sur_emballages, nb_uvc,
                 poids_unitaire_kg, poids_total_kg,
                 source, reference, client, notes, created_by)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (
            code_produit, type_mouvement, quantite_tonnes,
            date_mouvement, iso[0], iso[1],
            sur_emballage_id, nb_sur_emballages, nb_uvc,
            poids_unitaire_kg, poids_total_kg,
            source, reference, client, notes, created_by
        ))
        
        new_id = cursor.fetchone()['id']
        conn.commit()
        cursor.close()
        conn.close()
        
        return True, f"Mouvement #{new_id} enregistré ({quantite_tonnes:+.2f} T / {nb_sur_emballages:+d} sur-emb.)"
    except Exception as e:
        if 'conn' in locals():
            conn.rollback()
        return False, f"Erreur : {str(e)}"


def supprimer_mouvement(mouvement_id):
    """Supprime un mouvement"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM mouvements_produits_finis WHERE id = %s", (mouvement_id,))
        if not cursor.fetchone():
            cursor.close()
            conn.close()
            return False, "Mouvement introuvable"
        
        cursor.execute("DELETE FROM mouvements_produits_finis WHERE id = %s", (mouvement_id,))
        conn.commit()
        cursor.close()
        conn.close()
        return True, f"Mouvement #{mouvement_id} supprimé"
    except Exception as e:
        if 'conn' in locals():
            conn.rollback()
        return False, f"Erreur : {str(e)}"


# ============================================================================
# AFFICHAGE - KPIs
# ============================================================================

kpis = get_kpis()

if kpis and kpis['nb_mvt'] > 0:
    col1, col2, col3, col4, col5 = st.columns(5)
    
    with col1:
        st.metric("📦 Stock Total", format_tonnes(kpis['stock_total_t']))
    with col2:
        st.metric("🏷️ Produits en Stock", kpis['nb_en_stock'])
    with col3:
        st.metric("📊 UVC en Stock", format_number_fr(kpis['stock_total_uvc']))
    with col4:
        st.metric("📥 Entrées Semaine", format_tonnes(kpis['entrees_sem']))
    with col5:
        st.metric("📤 Sorties Semaine", format_tonnes(kpis['sorties_sem']))
    
    if kpis['top3']:
        st.markdown("---")
        st.markdown("##### 🏆 Top 3 Produits en Stock")
        top_cols = st.columns(3)
        medals = ['🥇', '🥈', '🥉']
        for i, prod in enumerate(kpis['top3']):
            with top_cols[i]:
                st.metric(f"{medals[i]} {prod['code_produit_commercial'][:30]}",
                          format_tonnes(prod['stock']))
else:
    st.info("📭 Aucun mouvement enregistré — Commencez par saisir une entrée dans l'onglet '➕ Saisie'")

st.markdown("---")

# ============================================================================
# ONGLETS
# ============================================================================

tab1, tab2, tab3, tab4 = st.tabs([
    "📊 Stock Actuel", "📋 Historique", "➕ Saisie Mouvement", "📈 Évolution"
])

# ============================================================================
# ONGLET 1 : STOCK ACTUEL
# ============================================================================

with tab1:
    st.subheader("📊 Stock Actuel par Produit")
    
    df_stock = get_stock_actuel()
    
    if not df_stock.empty:
        col_f1, col_f2 = st.columns(2)
        with col_f1:
            marques = ["Toutes"] + sorted(df_stock['marque'].unique().tolist())
            filtre_marque = st.selectbox("Marque", marques, key="stock_filtre_marque")
        with col_f2:
            opts = ["Tous", "En stock (>0)", "Rupture (≤0)"]
            filtre_stock = st.selectbox("Niveau", opts, key="stock_filtre_niveau")
        
        df_f = df_stock.copy()
        if filtre_marque != "Toutes":
            df_f = df_f[df_f['marque'] == filtre_marque]
        if filtre_stock == "En stock (>0)":
            df_f = df_f[df_f['stock_tonnes'] > 0]
        elif filtre_stock == "Rupture (≤0)":
            df_f = df_f[df_f['stock_tonnes'] <= 0]
        
        st.markdown(f"**{len(df_f)} produit(s)**")
        
        df_d = df_f.copy()
        df_d['Stock (T)'] = df_d['stock_tonnes'].apply(lambda x: f"{x:+.2f}")
        df_d['Stock (kg)'] = df_d['stock_kg'].apply(lambda x: f"{x:+,.0f}".replace(',', ' ') if pd.notna(x) else "0")
        df_d['UVC'] = df_d['total_uvc'].apply(lambda x: f"{int(x):,}".replace(',', ' ') if pd.notna(x) else "0")
        df_d['Sur-Emb.'] = df_d['total_sur_emb'].apply(lambda x: f"{int(x):+d}" if pd.notna(x) else "0")
        df_d['Entrées (T)'] = df_d['total_entrees_t'].apply(lambda x: f"{x:.2f}" if x > 0 else "-")
        df_d['Sorties (T)'] = df_d['total_sorties_t'].apply(lambda x: f"{x:.2f}" if x > 0 else "-")
        
        cols_show = ['code_produit_commercial', 'marque', 'libelle', 'Stock (T)', 'Stock (kg)',
                     'UVC', 'Sur-Emb.', 'Entrées (T)', 'Sorties (T)', 'dernier_mouvement']
        cols_show = [c for c in cols_show if c in df_d.columns]
        
        rename = {'code_produit_commercial': 'Code', 'marque': 'Marque', 'libelle': 'Libellé',
                  'dernier_mouvement': 'Dernier Mvt'}
        
        st.dataframe(
            df_d[cols_show].rename(columns=rename),
            use_container_width=True, hide_index=True,
            column_config={'Dernier Mvt': st.column_config.DateColumn(format='DD/MM/YYYY')}
        )
        
        st.markdown("---")
        col_e1, col_e2 = st.columns(2)
        with col_e1:
            csv = df_f.to_csv(index=False).encode('utf-8')
            st.download_button("📥 CSV", csv, f"stock_pf_{datetime.now().strftime('%Y%m%d')}.csv",
                              "text/csv", use_container_width=True)
        with col_e2:
            buf = io.BytesIO()
            with pd.ExcelWriter(buf, engine='openpyxl') as w:
                df_f.to_excel(w, index=False, sheet_name='Stock PF')
            st.download_button("📥 Excel", buf.getvalue(),
                              f"stock_pf_{datetime.now().strftime('%Y%m%d')}.xlsx",
                              "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                              use_container_width=True)
    else:
        st.info("📭 Aucun stock — Saisissez des mouvements dans l'onglet '➕ Saisie Mouvement'")

# ============================================================================
# ONGLET 2 : HISTORIQUE MOUVEMENTS
# ============================================================================

with tab2:
    st.subheader("📋 Historique des Mouvements")
    
    col_f1, col_f2, col_f3, col_f4 = st.columns(4)
    with col_f1:
        prods = get_produits_commerciaux_actifs()
        opts_prod = ["Tous"] + [p['code_produit'] for p in prods]
        fp = st.selectbox("Produit", opts_prod, key="hist_produit")
    with col_f2:
        types_mvt = ["Tous", "PRODUCTION", "EXPEDITION", "CORRECTION_ENTREE", 
                     "CORRECTION_SORTIE", "IMPORT_FRULOG"]
        ft = st.selectbox("Type", types_mvt, key="hist_type")
    with col_f3:
        dd = st.date_input("Du", value=None, key="hist_dd")
    with col_f4:
        df_val = st.date_input("Au", value=None, key="hist_df")
    
    df_mvt = get_mouvements(
        code_produit=fp if fp != "Tous" else None,
        type_mouvement=ft if ft != "Tous" else None,
        date_debut=dd, date_fin=df_val
    )
    
    if not df_mvt.empty:
        st.markdown(f"**{len(df_mvt)} mouvement(s)**")
        
        emojis = {'PRODUCTION': '🏭', 'EXPEDITION': '🚚', 'CORRECTION_ENTREE': '📥',
                  'CORRECTION_SORTIE': '📤', 'IMPORT_FRULOG': '📊'}
        
        df_md = df_mvt.copy()
        df_md['Type'] = df_md['type_mouvement'].apply(lambda t: f"{emojis.get(t, '❓')} {t}")
        df_md['Qté (T)'] = df_md['quantite_tonnes'].apply(lambda q: f"{q:+.2f}")
        df_md['Poids (kg)'] = df_md['poids_total_kg'].apply(
            lambda x: f"{x:+,.0f}".replace(',', ' ') if pd.notna(x) and x != 0 else "-")
        df_md['Nb S-E'] = df_md['nb_sur_emballages'].apply(
            lambda x: f"{int(x):+d}" if pd.notna(x) and x != 0 else "-")
        df_md['UVC'] = df_md['nb_uvc'].apply(
            lambda x: f"{int(x):+d}" if pd.notna(x) and x != 0 else "-")
        
        cols_mvt = ['id', 'date_mouvement', 'Type', 'code_produit_commercial',
                    'libelle_produit', 'Nb S-E', 'sur_emballage', 'UVC',
                    'Qté (T)', 'Poids (kg)', 'source', 'reference', 'client',
                    'notes', 'created_by']
        cols_mvt = [c for c in cols_mvt if c in df_md.columns]
        
        rename_mvt = {'id': 'ID', 'date_mouvement': 'Date', 'code_produit_commercial': 'Code',
                      'libelle_produit': 'Produit', 'sur_emballage': 'Sur-Emb.',
                      'source': 'Source', 'reference': 'Réf.', 'client': 'Client',
                      'notes': 'Notes', 'created_by': 'Par'}
        
        event = st.dataframe(
            df_md[cols_mvt].rename(columns=rename_mvt),
            use_container_width=True, hide_index=True,
            on_select="rerun", selection_mode="single-row", key="table_mvt",
            column_config={
                'Date': st.column_config.DateColumn(format='DD/MM/YYYY'),
                'ID': st.column_config.NumberColumn(width='small'),
            }
        )
        
        selected = event.selection.rows if hasattr(event, 'selection') else []
        if len(selected) > 0:
            sel = df_mvt.iloc[selected[0]]
            mid = int(sel['id'])
            st.warning(f"Mouvement #{mid} : {sel['type_mouvement']} | "
                      f"{sel['code_produit_commercial']} | {float(sel['quantite_tonnes']):+.2f} T")
            
            c1, c2 = st.columns([1, 3])
            with c1:
                if st.button("🗑️ Supprimer", type="secondary", key="btn_del_mvt"):
                    st.session_state['confirm_del'] = mid
            
            if st.session_state.get('confirm_del') == mid:
                st.error("Action irréversible. Le stock sera recalculé.")
                c_ok, c_no = st.columns(2)
                with c_ok:
                    if st.button("Oui, supprimer", key="btn_ok_del"):
                        ok, msg = supprimer_mouvement(mid)
                        if ok:
                            st.success(msg)
                            st.session_state.pop('confirm_del', None)
                            st.rerun()
                        else:
                            st.error(msg)
                with c_no:
                    if st.button("Annuler", key="btn_no_del"):
                        st.session_state.pop('confirm_del', None)
                        st.rerun()
        
        st.markdown("---")
        csv_m = df_mvt.to_csv(index=False).encode('utf-8')
        st.download_button("📥 Export Mouvements CSV", csv_m,
                          f"mvt_pf_{datetime.now().strftime('%Y%m%d')}.csv", "text/csv")
    else:
        st.info("📭 Aucun mouvement trouvé")

# ============================================================================
# ONGLET 3 : SAISIE MOUVEMENT
# ============================================================================

with tab3:
    st.subheader("➕ Saisir un Mouvement")
    
    produits = get_produits_commerciaux_actifs()
    sur_emballages = get_sur_emballages_actifs()
    
    if not produits:
        st.warning("Aucun produit commercial actif dans ref_produits_commerciaux")
    elif not sur_emballages:
        st.warning("Aucun sur-emballage actif dans ref_sur_emballages — "
                   "Ajoutez-en via Sources > Sur-Emballages")
    else:
        # --- Type de mouvement ---
        st.markdown("##### Type de mouvement")
        tc1, tc2 = st.columns(2)
        
        with tc1:
            type_opts = {
                "🏭 Entrée Production": "PRODUCTION",
                "🚚 Sortie Expédition": "EXPEDITION",
                "📥 Correction Entrée (+)": "CORRECTION_ENTREE",
                "📤 Correction Sortie (-)": "CORRECTION_SORTIE",
            }
            type_sel = st.selectbox("Type *", list(type_opts.keys()), key="s_type")
            type_mvt = type_opts[type_sel]
        
        with tc2:
            is_entree = type_mvt in ('PRODUCTION', 'CORRECTION_ENTREE')
            if is_entree:
                st.success("📥 Ce mouvement va **augmenter** le stock")
            else:
                st.error("📤 Ce mouvement va **diminuer** le stock")
        
        st.markdown("---")
        
        # --- Produit et Sur-emballage ---
        st.markdown("##### Produit et conditionnement")
        c1, c2, c3 = st.columns(3)
        
        with c1:
            prod_labels = [f"{p['code_produit']} — {p['marque']} {p['libelle']}" for p in produits]
            prod_idx = st.selectbox("Produit commercial *", range(len(prod_labels)),
                                   format_func=lambda i: prod_labels[i], key="s_prod")
            produit = produits[prod_idx]
            code_produit = produit['code_produit']
            # Poids unitaire du référentiel (converti en KG)
            poids_ref_kg = normaliser_poids_kg(produit['poids_unitaire'], produit['unite_poids'])
            # Afficher l'unité d'origine pour info
            unite_origine = (produit['unite_poids'] or 'KG').upper().strip()
            poids_origine = float(produit['poids_unitaire']) if produit['poids_unitaire'] else 0
        
        with c2:
            se_labels = [f"{se['libelle']} ({int(se['nb_uvc'])} UVC)" for se in sur_emballages]
            se_idx = st.selectbox("Sur-emballage *", range(len(se_labels)),
                                 format_func=lambda i: se_labels[i], key="s_se")
            sur_emb = sur_emballages[se_idx]
            nb_uvc_ref = int(sur_emb['nb_uvc'])
            se_id = int(sur_emb['id'])
        
        with c3:
            nb_se = st.number_input("Nombre de sur-emballages *",
                                    min_value=1, max_value=9999, value=1, step=1, key="s_nb")
        
        # --- Paramètres ajustables (pré-remplis depuis référentiel) ---
        st.markdown("---")
        st.markdown("##### ⚙️ Paramètres de calcul *(modifiables si besoin)*")
        
        if poids_ref_kg > 0:
            st.caption(f"Pré-rempli depuis le référentiel : {poids_origine} {unite_origine}/UVC, "
                      f"{nb_uvc_ref} UVC/{sur_emb['libelle']}")
        else:
            st.warning(f"⚠️ Poids unitaire non renseigné pour **{code_produit}** — "
                      f"saisissez-le ci-dessous pour continuer")
        
        pc1, pc2, pc3 = st.columns(3)
        
        with pc1:
            # Poids unitaire modifiable — en KG avec conversion si G
            poids_uvc_kg = st.number_input(
                "Poids unitaire UVC (kg) *",
                min_value=0.001,
                max_value=500.0,
                value=max(poids_ref_kg, 0.001),
                step=0.1,
                format="%.3f",
                key="s_poids_uvc",
                help="Poids d'une UVC en kilogrammes. Ex: filet 2,5kg → 2.500"
            )
        
        with pc2:
            # Nb UVC par sur-emballage modifiable
            nb_uvc_par_se = st.number_input(
                f"UVC par {sur_emb['libelle']} *",
                min_value=1,
                max_value=9999,
                value=nb_uvc_ref,
                step=1,
                key="s_nb_uvc",
                help=f"Nombre d'UVC dans un(e) {sur_emb['libelle']}. Référentiel : {nb_uvc_ref}"
            )
        
        with pc3:
            # Afficher si le poids a été modifié par rapport au référentiel
            if poids_uvc_kg != poids_ref_kg:
                st.info(f"⚡ Poids modifié : {poids_ref_kg:.3f} → {poids_uvc_kg:.3f} kg")
            if nb_uvc_par_se != nb_uvc_ref:
                st.info(f"⚡ UVC modifié : {nb_uvc_ref} → {nb_uvc_par_se}")
            if poids_uvc_kg == poids_ref_kg and nb_uvc_par_se == nb_uvc_ref:
                st.success("✅ Valeurs référentiel")
        
        # --- Calcul automatique ---
        total_uvc = nb_se * nb_uvc_par_se
        total_kg = total_uvc * poids_uvc_kg
        total_tonnes = total_kg / 1000
        
        st.markdown("---")
        st.markdown("##### 🧮 Calcul automatique")
        calc_c1, calc_c2, calc_c3, calc_c4 = st.columns(4)
        with calc_c1:
            st.metric("📦 Sur-emballages", f"{nb_se}")
        with calc_c2:
            st.metric("🏷️ UVC totales", f"{total_uvc:,}".replace(',', ' '))
        with calc_c3:
            st.metric("⚖️ Poids total", f"{total_kg:,.0f} kg".replace(',', ' '))
        with calc_c4:
            st.metric("📊 Tonnage", f"{total_tonnes:.3f} T")
        
        st.caption(
            f"*{nb_se} {sur_emb['libelle']}(s) × {nb_uvc_par_se} UVC × "
            f"{poids_uvc_kg:.3f} kg = {total_kg:,.0f} kg = {total_tonnes:.3f} T*".replace(',', ' ')
        )
        
        # --- Date et infos complémentaires ---
        st.markdown("---")
        st.markdown("##### Informations complémentaires")
        ic1, ic2, ic3 = st.columns(3)
        
        with ic1:
            date_mvt = st.date_input("Date *", value=date.today(), key="s_date")
        with ic2:
            ref = st.text_input("Référence (BL, job...)", key="s_ref")
        with ic3:
            client = st.text_input("Client", key="s_client")
        
        notes = st.text_area("Notes", height=68, key="s_notes")
        
        # --- Prévisualisation ---
        signe = "+" if is_entree else "-"
        st.info(
            f"**Récapitulatif** : {type_sel} | {code_produit} | "
            f"{signe}{nb_se} {sur_emb['libelle']}(s) | "
            f"{signe}{total_uvc} UVC | {signe}{total_tonnes:.3f} T | "
            f"{date_mvt.strftime('%d/%m/%Y')}"
        )
        
        # --- Validation ---
        can_save = True
        if poids_uvc_kg <= 0.001:
            st.error("Le poids unitaire doit être supérieur à 0")
            can_save = False
        if total_tonnes <= 0:
            st.error("Le tonnage calculé est nul")
            can_save = False
        
        # --- Enregistrer ---
        if st.button("💾 Enregistrer le mouvement", type="primary",
                    use_container_width=True, key="btn_save", disabled=not can_save):
            username = st.session_state.get('username', 'inconnu')
            
            ok, msg = ajouter_mouvement(
                code_produit=code_produit,
                type_mouvement=type_mvt,
                date_mouvement=date_mvt,
                sur_emballage_id=se_id,
                nb_sur_emballages=nb_se,
                nb_uvc=total_uvc,
                poids_unitaire_kg=poids_uvc_kg,
                poids_total_kg=total_kg,
                quantite_tonnes=total_tonnes,
                source='MANUEL',
                reference=ref if ref else None,
                client=client if client else None,
                notes=notes if notes else None,
                created_by=username
            )
            
            if ok:
                st.success(f"✅ {msg}")
                st.balloons()
                st.rerun()
            else:
                st.error(f"❌ {msg}")

# ============================================================================
# ONGLET 4 : ÉVOLUTION
# ============================================================================

with tab4:
    st.subheader("📈 Évolution du Stock")
    
    nb_sem = st.slider("Semaines", 4, 52, 12, key="evol_sem")
    df_evol = get_evolution_stock(nb_sem)
    
    if not df_evol.empty:
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=df_evol['semaine_label'], y=df_evol['stock_cumule'],
            mode='lines+markers', name='Stock cumulé (T)',
            line=dict(color='#2196f3', width=3), marker=dict(size=8),
            fill='tozeroy', fillcolor='rgba(33, 150, 243, 0.1)'))
        
        fig.add_trace(go.Bar(
            x=df_evol['semaine_label'], y=df_evol['mvt_semaine'],
            name='Mouvement net (T)', opacity=0.5,
            marker_color=df_evol['mvt_semaine'].apply(
                lambda x: '#4caf50' if x >= 0 else '#f44336').tolist()))
        
        fig.update_layout(title="Évolution hebdomadaire", xaxis_title="Semaine",
                         yaxis_title="Tonnes", height=450, showlegend=True,
                         legend=dict(orientation="h", yanchor="bottom", y=1.02))
        st.plotly_chart(fig, use_container_width=True)
        
        with st.expander("📊 Détail"):
            st.dataframe(df_evol[['semaine_label', 'mvt_semaine', 'stock_cumule']].rename(
                columns={'semaine_label': 'Semaine', 'mvt_semaine': 'Mvt Net (T)',
                         'stock_cumule': 'Stock Cumulé (T)'}),
                use_container_width=True, hide_index=True)
    else:
        st.info("📭 Pas assez de données pour le graphique")

show_footer()
