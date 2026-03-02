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
    """Formate un nombre avec des espaces pour les milliers"""
    if pd.isna(value) or value is None:
        return "0"
    try:
        return f"{int(value):,}".replace(',', ' ')
    except (ValueError, TypeError):
        return str(value)

def format_tonnes(value):
    """Formate un tonnage"""
    if pd.isna(value) or value is None:
        return "0.00 T"
    try:
        return f"{float(value):,.2f} T".replace(',', ' ')
    except (ValueError, TypeError):
        return str(value)

# ============================================================================
# FONCTIONS BDD
# ============================================================================

def get_stock_actuel():
    """Calcule le stock actuel par produit commercial (somme des mouvements)"""
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
                COUNT(*) FILTER (WHERE m.type_mouvement IN ('PRODUCTION', 'CORRECTION_ENTREE')) as nb_entrees,
                COUNT(*) FILTER (WHERE m.type_mouvement IN ('EXPEDITION', 'CORRECTION_SORTIE', 'IMPORT_FRULOG')) as nb_sorties,
                SUM(m.quantite_tonnes) FILTER (WHERE m.quantite_tonnes > 0) as total_entrees,
                ABS(SUM(m.quantite_tonnes) FILTER (WHERE m.quantite_tonnes < 0)) as total_sorties,
                MAX(m.date_mouvement) as dernier_mouvement
            FROM mouvements_produits_finis m
            LEFT JOIN ref_produits_commerciaux pc 
                ON m.code_produit_commercial = pc.code_produit
            GROUP BY m.code_produit_commercial, pc.marque, pc.libelle, pc.code_variete
            ORDER BY stock_tonnes DESC
        """)
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        
        if rows:
            df = pd.DataFrame(rows)
            numeric_cols = ['stock_tonnes', 'total_entrees', 'total_sorties']
            for col in numeric_cols:
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
                COALESCE(SUM(quantite_tonnes), 0) as stock_total,
                COUNT(DISTINCT code_produit_commercial) FILTER (
                    WHERE code_produit_commercial IN (
                        SELECT code_produit_commercial 
                        FROM mouvements_produits_finis 
                        GROUP BY code_produit_commercial 
                        HAVING SUM(quantite_tonnes) > 0
                    )
                ) as nb_produits_en_stock
            FROM mouvements_produits_finis
        """)
        row = cursor.fetchone()
        stock_total = float(row['stock_total']) if row else 0
        
        # Nb produits avec stock positif
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
        cursor.execute("""
            SELECT 
                COALESCE(SUM(quantite_tonnes) FILTER (WHERE quantite_tonnes > 0), 0) as entrees_semaine,
                COALESCE(ABS(SUM(quantite_tonnes) FILTER (WHERE quantite_tonnes < 0)), 0) as sorties_semaine
            FROM mouvements_produits_finis
            WHERE annee = %s AND semaine = %s
        """, (date.today().isocalendar()[1], date.today().isocalendar()[1]))
        
        iso = date.today().isocalendar()
        cursor.execute("""
            SELECT 
                COALESCE(SUM(quantite_tonnes) FILTER (WHERE quantite_tonnes > 0), 0) as entrees_semaine,
                COALESCE(ABS(SUM(quantite_tonnes) FILTER (WHERE quantite_tonnes < 0)), 0) as sorties_semaine
            FROM mouvements_produits_finis
            WHERE annee = %s AND semaine = %s
        """, (iso[0], iso[1]))
        row_sem = cursor.fetchone()
        
        # Top 3 produits
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
        nb_mouvements = cursor.fetchone()['cnt']
        
        cursor.close()
        conn.close()
        
        return {
            'stock_total': stock_total,
            'nb_en_stock': nb_en_stock,
            'entrees_semaine': float(row_sem['entrees_semaine']) if row_sem else 0,
            'sorties_semaine': float(row_sem['sorties_semaine']) if row_sem else 0,
            'top3': top3 if top3 else [],
            'nb_mouvements': nb_mouvements
        }
    except Exception as e:
        st.error(f"Erreur KPIs : {str(e)}")
        return None


def get_mouvements(code_produit=None, type_mouvement=None, date_debut=None, date_fin=None, limit=200):
    """Récupère l'historique des mouvements avec filtres"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        query = """
            SELECT 
                m.id,
                m.code_produit_commercial,
                COALESCE(pc.libelle, m.code_produit_commercial) as libelle_produit,
                m.type_mouvement,
                m.quantite_tonnes,
                m.date_mouvement,
                m.annee,
                m.semaine,
                m.source,
                m.reference,
                m.client,
                m.notes,
                m.created_by,
                m.created_at
            FROM mouvements_produits_finis m
            LEFT JOIN ref_produits_commerciaux pc 
                ON m.code_produit_commercial = pc.code_produit
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
    """Calcule l'évolution du stock par semaine pour le graphique"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            WITH semaines AS (
                SELECT DISTINCT annee, semaine 
                FROM mouvements_produits_finis
                ORDER BY annee, semaine
            ),
            cumul AS (
                SELECT 
                    annee,
                    semaine,
                    SUM(quantite_tonnes) as mouvement_semaine,
                    SUM(SUM(quantite_tonnes)) OVER (ORDER BY annee, semaine) as stock_cumule
                FROM mouvements_produits_finis
                GROUP BY annee, semaine
                ORDER BY annee, semaine
            )
            SELECT * FROM cumul ORDER BY annee DESC, semaine DESC LIMIT %s
        """, (nb_semaines,))
        
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        
        if rows:
            df = pd.DataFrame(rows)
            df['semaine_label'] = df.apply(
                lambda r: f"S{int(r['semaine']):02d}/{int(r['annee'])}", axis=1
            )
            df = df.sort_values(['annee', 'semaine'])
            return df
        return pd.DataFrame()
    except Exception as e:
        st.error(f"Erreur évolution : {str(e)}")
        return pd.DataFrame()


def get_produits_commerciaux_actifs():
    """Liste des produits commerciaux actifs pour les dropdowns"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT code_produit, marque, libelle
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


def ajouter_mouvement(code_produit, type_mouvement, quantite_tonnes, 
                      date_mouvement, source='MANUEL', reference=None, 
                      client=None, notes=None, created_by=None):
    """Ajoute un mouvement de stock produit fini"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Calculer année/semaine ISO
        iso = date_mouvement.isocalendar()
        annee = iso[0]
        semaine = iso[1]
        
        # Quantité : positive pour entrée, négative pour sortie
        if type_mouvement in ('EXPEDITION', 'CORRECTION_SORTIE', 'IMPORT_FRULOG'):
            quantite = -abs(float(quantite_tonnes))
        else:
            quantite = abs(float(quantite_tonnes))
        
        cursor.execute("""
            INSERT INTO mouvements_produits_finis 
                (code_produit_commercial, type_mouvement, quantite_tonnes,
                 date_mouvement, annee, semaine, source, reference, 
                 client, notes, created_by)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (
            code_produit, type_mouvement, quantite,
            date_mouvement, annee, semaine, source, reference,
            client, notes, created_by
        ))
        
        new_id = cursor.fetchone()['id']
        conn.commit()
        cursor.close()
        conn.close()
        
        return True, f"Mouvement #{new_id} enregistré ({quantite:+.2f} T)"
    except Exception as e:
        if 'conn' in locals():
            conn.rollback()
        return False, f"Erreur : {str(e)}"


def supprimer_mouvement(mouvement_id):
    """Supprime un mouvement (hard delete — traçabilité via logs si nécessaire)"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Vérifier existence
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

if kpis:
    col1, col2, col3, col4, col5 = st.columns(5)
    
    with col1:
        st.metric("📦 Stock Total", format_tonnes(kpis['stock_total']))
    
    with col2:
        st.metric("🏷️ Produits en Stock", kpis['nb_en_stock'])
    
    with col3:
        st.metric("📥 Entrées Semaine", format_tonnes(kpis['entrees_semaine']))
    
    with col4:
        st.metric("📤 Sorties Semaine", format_tonnes(kpis['sorties_semaine']))
    
    with col5:
        st.metric("📊 Total Mouvements", format_number_fr(kpis['nb_mouvements']))
    
    # Top 3 produits
    if kpis['top3']:
        st.markdown("---")
        st.markdown("##### 🏆 Top 3 Produits en Stock")
        top_cols = st.columns(3)
        medals = ['🥇', '🥈', '🥉']
        for i, prod in enumerate(kpis['top3']):
            with top_cols[i]:
                st.metric(
                    f"{medals[i]} {prod['code_produit_commercial'][:30]}",
                    format_tonnes(prod['stock'])
                )

else:
    st.info("📭 Aucun mouvement enregistré — Commencez par saisir une entrée en stock")

st.markdown("---")

# ============================================================================
# ONGLETS
# ============================================================================

tab1, tab2, tab3, tab4 = st.tabs([
    "📊 Stock Actuel", 
    "📋 Historique Mouvements", 
    "➕ Saisie Mouvement",
    "📈 Évolution"
])

# ============================================================================
# ONGLET 1 : STOCK ACTUEL
# ============================================================================

with tab1:
    st.subheader("📊 Stock Actuel par Produit")
    
    df_stock = get_stock_actuel()
    
    if not df_stock.empty:
        # Filtres
        col_f1, col_f2 = st.columns(2)
        with col_f1:
            marques = ["Toutes"] + sorted(df_stock['marque'].unique().tolist())
            filtre_marque = st.selectbox("Filtrer par marque", marques, key="stock_filtre_marque")
        with col_f2:
            options_stock = ["Tous", "En stock (>0)", "Rupture (=0)", "Négatif (<0)"]
            filtre_stock = st.selectbox("Filtrer par niveau", options_stock, key="stock_filtre_niveau")
        
        df_filtered = df_stock.copy()
        if filtre_marque != "Toutes":
            df_filtered = df_filtered[df_filtered['marque'] == filtre_marque]
        if filtre_stock == "En stock (>0)":
            df_filtered = df_filtered[df_filtered['stock_tonnes'] > 0]
        elif filtre_stock == "Rupture (=0)":
            df_filtered = df_filtered[df_filtered['stock_tonnes'] == 0]
        elif filtre_stock == "Négatif (<0)":
            df_filtered = df_filtered[df_filtered['stock_tonnes'] < 0]
        
        st.markdown(f"**{len(df_filtered)} produit(s) trouvé(s)**")
        
        # Préparer affichage
        df_display = df_filtered.copy()
        df_display['stock_display'] = df_display['stock_tonnes'].apply(lambda x: f"{x:+.2f} T")
        df_display['entrees'] = df_display['total_entrees'].apply(lambda x: f"{x:.2f} T" if pd.notna(x) and x > 0 else "-")
        df_display['sorties'] = df_display['total_sorties'].apply(lambda x: f"{x:.2f} T" if pd.notna(x) and x > 0 else "-")
        
        colonnes = ['code_produit_commercial', 'marque', 'libelle', 'variete',
                     'stock_display', 'entrees', 'sorties', 'nb_entrees', 'nb_sorties', 
                     'dernier_mouvement']
        noms = {
            'code_produit_commercial': 'Code Produit',
            'marque': 'Marque',
            'libelle': 'Libellé',
            'variete': 'Variété',
            'stock_display': 'Stock (T)',
            'entrees': 'Total Entrées',
            'sorties': 'Total Sorties',
            'nb_entrees': 'Nb Entrées',
            'nb_sorties': 'Nb Sorties',
            'dernier_mouvement': 'Dernier Mvt'
        }
        
        # Filtrer colonnes existantes
        colonnes = [c for c in colonnes if c in df_display.columns]
        df_show = df_display[colonnes].rename(columns=noms)
        
        st.dataframe(
            df_show,
            use_container_width=True,
            hide_index=True,
            column_config={
                'Dernier Mvt': st.column_config.DateColumn('Dernier Mvt', format='DD/MM/YYYY'),
            }
        )
        
        # Export
        st.markdown("---")
        col_exp1, col_exp2 = st.columns(2)
        with col_exp1:
            csv = df_filtered.to_csv(index=False).encode('utf-8')
            st.download_button(
                "📥 Export CSV",
                csv,
                f"stock_pf_{datetime.now().strftime('%Y%m%d')}.csv",
                "text/csv",
                use_container_width=True
            )
        with col_exp2:
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                df_filtered.to_excel(writer, index=False, sheet_name='Stock PF')
            st.download_button(
                "📥 Export Excel",
                buffer.getvalue(),
                f"stock_pf_{datetime.now().strftime('%Y%m%d')}.xlsx",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )
    else:
        st.info("📭 Aucun stock — Saisissez des mouvements dans l'onglet '➕ Saisie Mouvement'")

# ============================================================================
# ONGLET 2 : HISTORIQUE MOUVEMENTS
# ============================================================================

with tab2:
    st.subheader("📋 Historique des Mouvements")
    
    # Filtres
    col_f1, col_f2, col_f3, col_f4 = st.columns(4)
    
    with col_f1:
        produits_list = get_produits_commerciaux_actifs()
        options_produit = ["Tous"] + [p['code_produit'] for p in produits_list]
        filtre_produit = st.selectbox("Produit", options_produit, key="hist_produit")
    
    with col_f2:
        types_mvt = ["Tous", "PRODUCTION", "EXPEDITION", "CORRECTION_ENTREE", 
                     "CORRECTION_SORTIE", "IMPORT_FRULOG"]
        filtre_type = st.selectbox("Type", types_mvt, key="hist_type")
    
    with col_f3:
        date_deb = st.date_input("Du", value=None, key="hist_date_deb")
    
    with col_f4:
        date_end = st.date_input("Au", value=None, key="hist_date_fin")
    
    df_mouvements = get_mouvements(
        code_produit=filtre_produit if filtre_produit != "Tous" else None,
        type_mouvement=filtre_type if filtre_type != "Tous" else None,
        date_debut=date_deb,
        date_fin=date_end
    )
    
    if not df_mouvements.empty:
        st.markdown(f"**{len(df_mouvements)} mouvement(s)**")
        
        # Préparer affichage
        df_mvt_display = df_mouvements.copy()
        
        # Emoji type mouvement
        type_emojis = {
            'PRODUCTION': '🏭',
            'EXPEDITION': '🚚',
            'CORRECTION_ENTREE': '📥',
            'CORRECTION_SORTIE': '📤',
            'IMPORT_FRULOG': '📊'
        }
        df_mvt_display['type_display'] = df_mvt_display['type_mouvement'].apply(
            lambda t: f"{type_emojis.get(t, '❓')} {t}"
        )
        
        # Quantité avec couleur
        df_mvt_display['qte_display'] = df_mvt_display['quantite_tonnes'].apply(
            lambda q: f"+{q:.2f} T" if q > 0 else f"{q:.2f} T"
        )
        
        colonnes_mvt = ['id', 'date_mouvement', 'type_display', 'code_produit_commercial',
                        'libelle_produit', 'qte_display', 'source', 'reference', 
                        'client', 'notes', 'created_by']
        noms_mvt = {
            'id': 'ID',
            'date_mouvement': 'Date',
            'type_display': 'Type',
            'code_produit_commercial': 'Code Produit',
            'libelle_produit': 'Produit',
            'qte_display': 'Quantité',
            'source': 'Source',
            'reference': 'Référence',
            'client': 'Client',
            'notes': 'Notes',
            'created_by': 'Par'
        }
        
        colonnes_mvt = [c for c in colonnes_mvt if c in df_mvt_display.columns]
        df_mvt_show = df_mvt_display[colonnes_mvt].rename(columns=noms_mvt)
        
        event = st.dataframe(
            df_mvt_show,
            use_container_width=True,
            hide_index=True,
            on_select="rerun",
            selection_mode="single-row",
            key="table_mouvements",
            column_config={
                'Date': st.column_config.DateColumn('Date', format='DD/MM/YYYY'),
                'ID': st.column_config.NumberColumn('ID', width='small'),
            }
        )
        
        # Sélection pour suppression
        selected_rows = event.selection.rows if hasattr(event, 'selection') else []
        
        if len(selected_rows) > 0:
            selected_idx = selected_rows[0]
            selected_mvt = df_mouvements.iloc[selected_idx]
            mvt_id = int(selected_mvt['id'])
            
            st.warning(
                f"Mouvement #{mvt_id} sélectionné : "
                f"{selected_mvt['type_mouvement']} | "
                f"{selected_mvt['code_produit_commercial']} | "
                f"{float(selected_mvt['quantite_tonnes']):+.2f} T"
            )
            
            col_del1, col_del2 = st.columns([1, 3])
            with col_del1:
                if st.button("🗑️ Supprimer ce mouvement", type="secondary", key="btn_delete_mvt"):
                    st.session_state['confirm_delete_mvt'] = mvt_id
            
            if st.session_state.get('confirm_delete_mvt') == mvt_id:
                st.error("Cette action est irréversible. Le stock sera recalculé.")
                col_ok, col_cancel = st.columns(2)
                with col_ok:
                    if st.button("Oui, supprimer", key="btn_confirm_del_mvt"):
                        success, msg = supprimer_mouvement(mvt_id)
                        if success:
                            st.success(msg)
                            st.session_state.pop('confirm_delete_mvt', None)
                            st.rerun()
                        else:
                            st.error(msg)
                with col_cancel:
                    if st.button("Annuler", key="btn_cancel_del_mvt"):
                        st.session_state.pop('confirm_delete_mvt', None)
                        st.rerun()
        
        # Export mouvements
        st.markdown("---")
        csv_mvt = df_mouvements.to_csv(index=False).encode('utf-8')
        st.download_button(
            "📥 Export Mouvements CSV",
            csv_mvt,
            f"mouvements_pf_{datetime.now().strftime('%Y%m%d')}.csv",
            "text/csv"
        )
    else:
        st.info("📭 Aucun mouvement trouvé avec ces filtres")

# ============================================================================
# ONGLET 3 : SAISIE MOUVEMENT
# ============================================================================

with tab3:
    st.subheader("➕ Saisir un Mouvement")
    
    produits = get_produits_commerciaux_actifs()
    
    if not produits:
        st.warning("Aucun produit commercial actif trouvé dans ref_produits_commerciaux")
    else:
        # Type de mouvement
        st.markdown("##### Type de mouvement")
        type_col1, type_col2 = st.columns(2)
        
        with type_col1:
            type_options = {
                "🏭 Entrée Production": "PRODUCTION",
                "🚚 Sortie Expédition": "EXPEDITION",
                "📥 Correction Entrée (+)": "CORRECTION_ENTREE",
                "📤 Correction Sortie (-)": "CORRECTION_SORTIE",
            }
            type_selected = st.selectbox(
                "Type *",
                list(type_options.keys()),
                key="saisie_type"
            )
            type_mouvement = type_options[type_selected]
        
        with type_col2:
            is_entree = type_mouvement in ('PRODUCTION', 'CORRECTION_ENTREE')
            if is_entree:
                st.success("📥 Ce mouvement va **augmenter** le stock")
            else:
                st.error("📤 Ce mouvement va **diminuer** le stock")
        
        st.markdown("---")
        
        # Produit et quantité
        st.markdown("##### Détails")
        col1, col2, col3 = st.columns(3)
        
        with col1:
            prod_options = [f"{p['code_produit']} — {p['marque']} {p['libelle']}" for p in produits]
            prod_selected_idx = st.selectbox(
                "Produit commercial *",
                range(len(prod_options)),
                format_func=lambda i: prod_options[i],
                key="saisie_produit"
            )
            code_produit = produits[prod_selected_idx]['code_produit']
        
        with col2:
            quantite = st.number_input(
                "Quantité (tonnes) *",
                min_value=0.01,
                max_value=500.0,
                value=1.0,
                step=0.5,
                format="%.2f",
                key="saisie_quantite"
            )
        
        with col3:
            date_mvt = st.date_input(
                "Date *",
                value=date.today(),
                key="saisie_date"
            )
        
        # Infos complémentaires
        col4, col5 = st.columns(2)
        
        with col4:
            reference = st.text_input(
                "Référence (n° BL, n° job...)",
                key="saisie_reference"
            )
        
        with col5:
            client_mvt = st.text_input(
                "Client (si expédition)",
                key="saisie_client"
            )
        
        notes_mvt = st.text_area(
            "Notes",
            height=80,
            key="saisie_notes"
        )
        
        # Prévisualisation
        signe = "+" if is_entree else "-"
        st.info(
            f"**Prévisualisation** : {type_selected} | "
            f"{code_produit} | {signe}{quantite:.2f} T | "
            f"Date: {date_mvt.strftime('%d/%m/%Y')}"
        )
        
        # Bouton enregistrer
        if st.button("💾 Enregistrer le mouvement", type="primary", use_container_width=True, key="btn_save_mvt"):
            username = st.session_state.get('username', 'inconnu')
            
            success, msg = ajouter_mouvement(
                code_produit=code_produit,
                type_mouvement=type_mouvement,
                quantite_tonnes=quantite,
                date_mouvement=date_mvt,
                source='MANUEL',
                reference=reference if reference else None,
                client=client_mvt if client_mvt else None,
                notes=notes_mvt if notes_mvt else None,
                created_by=username
            )
            
            if success:
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
    
    nb_sem = st.slider("Nombre de semaines", 4, 52, 12, key="evol_nb_sem")
    
    df_evol = get_evolution_stock(nb_sem)
    
    if not df_evol.empty:
        # Graphique stock cumulé
        fig = go.Figure()
        
        fig.add_trace(go.Scatter(
            x=df_evol['semaine_label'],
            y=df_evol['stock_cumule'],
            mode='lines+markers',
            name='Stock cumulé (T)',
            line=dict(color='#2196f3', width=3),
            marker=dict(size=8),
            fill='tozeroy',
            fillcolor='rgba(33, 150, 243, 0.1)'
        ))
        
        # Barres entrées/sorties par semaine
        fig.add_trace(go.Bar(
            x=df_evol['semaine_label'],
            y=df_evol['mouvement_semaine'],
            name='Mouvement net (T)',
            marker_color=df_evol['mouvement_semaine'].apply(
                lambda x: '#4caf50' if x >= 0 else '#f44336'
            ).tolist(),
            opacity=0.5
        ))
        
        fig.update_layout(
            title="Stock Produits Finis — Évolution hebdomadaire",
            xaxis_title="Semaine",
            yaxis_title="Tonnes",
            height=450,
            showlegend=True,
            legend=dict(orientation="h", yanchor="bottom", y=1.02)
        )
        
        st.plotly_chart(fig, use_container_width=True)
        
        # Tableau détaillé
        with st.expander("📊 Détail par semaine"):
            df_evol_display = df_evol[['semaine_label', 'mouvement_semaine', 'stock_cumule']].copy()
            df_evol_display.columns = ['Semaine', 'Mouvement Net (T)', 'Stock Cumulé (T)']
            st.dataframe(df_evol_display, use_container_width=True, hide_index=True)
    else:
        st.info("📭 Pas assez de données pour afficher l'évolution")
        st.markdown("Saisissez des mouvements dans l'onglet '➕ Saisie Mouvement' pour voir le graphique.")

# ============================================================================
# FOOTER
# ============================================================================

show_footer()
