import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, date
from database import get_connection
from components import show_footer
from auth import require_access
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
    .positive-value {
        color: #2ca02c;
        font-weight: bold;
    }
    .negative-value {
        color: #d62728;
        font-weight: bold;
    }
</style>
""", unsafe_allow_html=True)

# ⭐ CONTRÔLE D'ACCÈS RBAC
require_access("STOCK")

st.title("📦 Stock Produits Finis")
st.caption("*Gestion et valorisation des produits finis*")
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
    except:
        return str(value)

def format_float_fr(value, decimals=2):
    """Formate un float avec des espaces pour les milliers"""
    if pd.isna(value) or value is None:
        return "0.00"
    try:
        return f"{float(value):,.{decimals}f}".replace(',', ' ')
    except:
        return str(value)

def format_currency(value):
    """Formate un montant en euros"""
    if pd.isna(value) or value is None:
        return "0.00 €"
    try:
        return f"{float(value):,.2f} €".replace(',', ' ')
    except:
        return str(value)

def get_kpis_produits_finis():
    """Récupère les KPIs globaux des produits finis"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # KPIs par statut
        cursor.execute("""
            SELECT 
                statut,
                COUNT(*) as nb_lignes,
                COALESCE(SUM(poids_total_kg), 0) as poids_total,
                COALESCE(SUM(nb_uvc_total), 0) as uvc_total,
                COALESCE(SUM(quantite_sur_emballages), 0) as sur_emb_total,
                COALESCE(SUM(cout_total), 0) as cout_total,
                COALESCE(SUM(prix_vente_total), 0) as ca_total,
                COALESCE(SUM(marge_brute), 0) as marge_totale
            FROM stock_produits_finis
            WHERE is_active = TRUE
            GROUP BY statut
        """)
        rows = cursor.fetchall()
        
        # Totaux globaux
        cursor.execute("""
            SELECT 
                COUNT(*) as nb_lignes,
                COALESCE(SUM(poids_total_kg), 0) as poids_total,
                COALESCE(SUM(nb_uvc_total), 0) as uvc_total,
                COALESCE(SUM(quantite_sur_emballages), 0) as sur_emb_total,
                COALESCE(SUM(cout_total), 0) as cout_total,
                COALESCE(SUM(prix_vente_total), 0) as ca_total,
                COALESCE(SUM(marge_brute), 0) as marge_totale
            FROM stock_produits_finis
            WHERE is_active = TRUE
        """)
        totaux = cursor.fetchone()
        
        cursor.close()
        conn.close()
        
        # Construire dict par statut
        kpis_statut = {}
        for row in rows:
            kpis_statut[row['statut']] = dict(row)
        
        return {
            'totaux': dict(totaux) if totaux else {},
            'par_statut': kpis_statut
        }
        
    except Exception as e:
        st.error(f"❌ Erreur KPIs : {str(e)}")
        return None

def get_produits_finis(statut_filter=None, produit_filter=None, date_debut=None, date_fin=None):
    """Récupère la liste des produits finis avec jointures"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        query = """
            SELECT 
                spf.id,
                spf.production_job_id,
                spf.code_produit_commercial,
                spf.lot_origine,
                spf.sur_emballage_id,
                COALESCE(se.libelle, '(Aucun)') as sur_emballage_libelle,
                COALESCE(se.nb_uvc, 0) as uvc_par_suremb,
                spf.quantite_sur_emballages,
                spf.nb_uvc_total,
                spf.poids_total_kg,
                spf.cout_matiere_premiere,
                spf.cout_production,
                spf.cout_sur_emballage,
                spf.cout_total,
                spf.prix_vente_unitaire,
                spf.prix_vente_total,
                spf.marge_brute,
                spf.marge_pct,
                spf.statut,
                spf.date_production,
                spf.date_expedition,
                spf.site_stockage,
                spf.emplacement,
                spf.notes,
                spf.created_by,
                spf.created_at
            FROM stock_produits_finis spf
            LEFT JOIN ref_sur_emballages se ON spf.sur_emballage_id = se.id
            WHERE spf.is_active = TRUE
        """
        
        params = []
        
        if statut_filter and statut_filter != "Tous":
            query += " AND spf.statut = %s"
            params.append(statut_filter)
        
        if produit_filter and produit_filter != "Tous":
            query += " AND spf.code_produit_commercial = %s"
            params.append(produit_filter)
        
        if date_debut:
            query += " AND spf.date_production >= %s"
            params.append(date_debut)
        
        if date_fin:
            query += " AND spf.date_production <= %s"
            params.append(date_fin)
        
        query += " ORDER BY spf.date_production DESC, spf.id DESC"
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        
        if rows:
            df = pd.DataFrame(rows)
            # Convertir colonnes numériques
            numeric_cols = ['quantite_sur_emballages', 'nb_uvc_total', 'poids_total_kg',
                           'cout_matiere_premiere', 'cout_production', 'cout_sur_emballage',
                           'cout_total', 'prix_vente_unitaire', 'prix_vente_total',
                           'marge_brute', 'marge_pct']
            for col in numeric_cols:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
            return df
        return pd.DataFrame()
        
    except Exception as e:
        st.error(f"❌ Erreur : {str(e)}")
        return pd.DataFrame()

def get_produits_commerciaux_list():
    """Liste des produits commerciaux distincts"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT DISTINCT code_produit_commercial 
            FROM stock_produits_finis 
            WHERE is_active = TRUE AND code_produit_commercial IS NOT NULL
            ORDER BY code_produit_commercial
        """)
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        return [row['code_produit_commercial'] for row in rows]
    except:
        return []

def get_sur_emballages_list():
    """Liste des sur-emballages actifs"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, code_sur_emballage, libelle, nb_uvc, prix_unitaire
            FROM ref_sur_emballages
            WHERE is_active = TRUE
            ORDER BY libelle
        """)
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        return rows if rows else []
    except:
        return []

def update_statut_produit(produit_id, nouveau_statut, date_expedition=None):
    """Met à jour le statut d'un produit fini"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        if nouveau_statut == 'EXPÉDIÉ' and date_expedition:
            cursor.execute("""
                UPDATE stock_produits_finis
                SET statut = %s, date_expedition = %s, updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
            """, (nouveau_statut, date_expedition, produit_id))
        else:
            cursor.execute("""
                UPDATE stock_produits_finis
                SET statut = %s, updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
            """, (nouveau_statut, produit_id))
        
        conn.commit()
        cursor.close()
        conn.close()
        return True, f"✅ Statut mis à jour : {nouveau_statut}"
    except Exception as e:
        if 'conn' in locals():
            conn.rollback()
        return False, f"❌ Erreur : {str(e)}"

def update_valorisation_produit(produit_id, prix_vente_unitaire, cout_mp=None, cout_prod=None, cout_suremb=None):
    """Met à jour la valorisation d'un produit fini"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Récupérer nb_uvc_total pour calculer prix_vente_total
        cursor.execute("SELECT nb_uvc_total, cout_matiere_premiere, cout_production, cout_sur_emballage FROM stock_produits_finis WHERE id = %s", (produit_id,))
        row = cursor.fetchone()
        
        if not row:
            return False, "❌ Produit introuvable"
        
        nb_uvc = float(row['nb_uvc_total'] or 0)
        
        # Coûts : utiliser nouvelles valeurs ou existantes
        cout_mp_final = float(cout_mp) if cout_mp is not None else float(row['cout_matiere_premiere'] or 0)
        cout_prod_final = float(cout_prod) if cout_prod is not None else float(row['cout_production'] or 0)
        cout_suremb_final = float(cout_suremb) if cout_suremb is not None else float(row['cout_sur_emballage'] or 0)
        
        # Calculs
        cout_total = cout_mp_final + cout_prod_final + cout_suremb_final
        prix_vente_total = prix_vente_unitaire * nb_uvc
        marge_brute = prix_vente_total - cout_total
        marge_pct = (marge_brute / cout_total * 100) if cout_total > 0 else 0
        
        cursor.execute("""
            UPDATE stock_produits_finis
            SET prix_vente_unitaire = %s,
                prix_vente_total = %s,
                cout_matiere_premiere = %s,
                cout_production = %s,
                cout_sur_emballage = %s,
                cout_total = %s,
                marge_brute = %s,
                marge_pct = %s,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
        """, (prix_vente_unitaire, prix_vente_total, cout_mp_final, cout_prod_final,
              cout_suremb_final, cout_total, marge_brute, marge_pct, produit_id))
        
        conn.commit()
        cursor.close()
        conn.close()
        return True, f"✅ Valorisation mise à jour - Marge: {marge_brute:.2f}€ ({marge_pct:.1f}%)"
    except Exception as e:
        if 'conn' in locals():
            conn.rollback()
        return False, f"❌ Erreur : {str(e)}"

def delete_produit_fini(produit_id):
    """Supprime (soft delete) un produit fini"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE stock_produits_finis
            SET is_active = FALSE, updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
        """, (produit_id,))
        
        conn.commit()
        cursor.close()
        conn.close()
        return True, "✅ Produit supprimé"
    except Exception as e:
        if 'conn' in locals():
            conn.rollback()
        return False, f"❌ Erreur : {str(e)}"

# ============================================================================
# AFFICHAGE - KPIs
# ============================================================================

kpis = get_kpis_produits_finis()

if kpis and kpis['totaux']:
    totaux = kpis['totaux']
    par_statut = kpis['par_statut']
    
    # KPIs principaux
    col1, col2, col3, col4, col5 = st.columns(5)
    
    with col1:
        st.metric("📦 Lignes Stock", format_number_fr(totaux.get('nb_lignes', 0)))
    
    with col2:
        poids_t = float(totaux.get('poids_total', 0)) / 1000
        st.metric("⚖️ Poids Total", f"{format_float_fr(poids_t, 1)} T")
    
    with col3:
        st.metric("📊 UVC Total", format_number_fr(totaux.get('uvc_total', 0)))
    
    with col4:
        ca = float(totaux.get('ca_total', 0))
        st.metric("💰 CA Potentiel", format_currency(ca))
    
    with col5:
        marge = float(totaux.get('marge_totale', 0))
        cout = float(totaux.get('cout_total', 0))
        marge_pct = (marge / cout * 100) if cout > 0 else 0
        st.metric("📈 Marge Totale", format_currency(marge), f"{marge_pct:.1f}%")
    
    st.markdown("---")
    
    # KPIs par statut
    st.markdown("##### 📊 Répartition par Statut")
    
    statuts_cols = st.columns(3)
    statut_icons = {'EN_STOCK': '🟢', 'EXPÉDIÉ': '🚚', 'CONSOMMÉ': '⚫'}
    
    for i, (statut, icon) in enumerate(statut_icons.items()):
        with statuts_cols[i]:
            data = par_statut.get(statut, {})
            nb = data.get('nb_lignes', 0)
            poids = float(data.get('poids_total', 0)) / 1000
            ca = float(data.get('ca_total', 0))
            st.metric(f"{icon} {statut}", f"{nb} lignes", f"{poids:.1f}T | {format_currency(ca)}")

else:
    st.info("📭 Aucun produit fini en stock")

st.markdown("---")

# ============================================================================
# FILTRES
# ============================================================================

st.markdown("#### 🔍 Filtres")

col1, col2, col3, col4 = st.columns(4)

with col1:
    statuts = ["Tous", "EN_STOCK", "EXPÉDIÉ", "CONSOMMÉ"]
    filtre_statut = st.selectbox("Statut", statuts, key="filter_statut")

with col2:
    produits = ["Tous"] + get_produits_commerciaux_list()
    filtre_produit = st.selectbox("Produit", produits, key="filter_produit")

with col3:
    date_debut = st.date_input("Date début", value=None, key="filter_date_debut")

with col4:
    date_fin = st.date_input("Date fin", value=None, key="filter_date_fin")

st.markdown("---")

# ============================================================================
# TABLEAU DES PRODUITS FINIS
# ============================================================================

df = get_produits_finis(
    statut_filter=filtre_statut if filtre_statut != "Tous" else None,
    produit_filter=filtre_produit if filtre_produit != "Tous" else None,
    date_debut=date_debut,
    date_fin=date_fin
)

if not df.empty:
    st.markdown(f"#### 📋 Liste des Produits Finis ({len(df)} résultats)")
    
    # Préparer affichage
    df_display = df.copy()
    
    # Formater colonnes
    df_display['poids_kg'] = df_display['poids_total_kg'].apply(lambda x: f"{x:,.0f}".replace(',', ' '))
    df_display['cout'] = df_display['cout_total'].apply(lambda x: f"{x:,.2f}€".replace(',', ' '))
    df_display['prix_vente'] = df_display['prix_vente_total'].apply(lambda x: f"{x:,.2f}€".replace(',', ' '))
    df_display['marge'] = df_display['marge_brute'].apply(lambda x: f"{x:,.2f}€".replace(',', ' '))
    df_display['marge_%'] = df_display['marge_pct'].apply(lambda x: f"{x:.1f}%")
    
    # Emoji statut
    def statut_emoji(s):
        if s == 'EN_STOCK':
            return '🟢 EN_STOCK'
        elif s == 'EXPÉDIÉ':
            return '🚚 EXPÉDIÉ'
        elif s == 'CONSOMMÉ':
            return '⚫ CONSOMMÉ'
        return s
    
    df_display['statut_display'] = df_display['statut'].apply(statut_emoji)
    
    # Colonnes à afficher
    colonnes_affichage = [
        'id', 'date_production', 'code_produit_commercial', 'lot_origine',
        'sur_emballage_libelle', 'quantite_sur_emballages', 'nb_uvc_total',
        'poids_kg', 'cout', 'prix_vente', 'marge', 'marge_%',
        'statut_display', 'site_stockage', 'emplacement'
    ]
    
    # Renommer colonnes
    colonnes_rename = {
        'id': 'ID',
        'date_production': 'Date Prod.',
        'code_produit_commercial': 'Produit',
        'lot_origine': 'Lot Origine',
        'sur_emballage_libelle': 'Sur-Emb.',
        'quantite_sur_emballages': 'Qté S-E',
        'nb_uvc_total': 'UVC',
        'poids_kg': 'Poids (kg)',
        'cout': 'Coût',
        'prix_vente': 'PV Total',
        'marge': 'Marge',
        'marge_%': 'Marge %',
        'statut_display': 'Statut',
        'site_stockage': 'Site',
        'emplacement': 'Empl.'
    }
    
    df_show = df_display[colonnes_affichage].rename(columns=colonnes_rename)
    
    # Config colonnes
    column_config = {
        'ID': st.column_config.NumberColumn('ID', width='small'),
        'Date Prod.': st.column_config.DateColumn('Date Prod.', format='DD/MM/YYYY'),
        'Produit': st.column_config.TextColumn('Produit', width='medium'),
        'UVC': st.column_config.NumberColumn('UVC', format='%d'),
        'Qté S-E': st.column_config.NumberColumn('Qté S-E', format='%d'),
    }
    
    # Tableau avec sélection
    event = st.dataframe(
        df_show,
        column_config=column_config,
        use_container_width=True,
        hide_index=True,
        on_select="rerun",
        selection_mode="single-row",
        key="table_produits_finis"
    )
    
    # Récupérer sélection
    selected_rows = event.selection.rows if hasattr(event, 'selection') else []
    
    st.markdown("---")
    
    # ============================================================================
    # ACTIONS SUR SÉLECTION
    # ============================================================================
    
    if len(selected_rows) > 0:
        selected_idx = selected_rows[0]
        selected_row = df.iloc[selected_idx]
        produit_id = int(selected_row['id'])
        
        st.success(f"✅ Sélectionné : **{selected_row['code_produit_commercial']}** - Lot: {selected_row['lot_origine']} (ID: {produit_id})")
        
        # Onglets d'actions
        tab1, tab2, tab3 = st.tabs(["📊 Détails", "💰 Valorisation", "🔧 Actions"])
        
        with tab1:
            # Détails du produit
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.markdown("**📦 Produit**")
                st.write(f"Code : {selected_row['code_produit_commercial']}")
                st.write(f"Lot origine : {selected_row['lot_origine']}")
                st.write(f"Date production : {selected_row['date_production']}")
            
            with col2:
                st.markdown("**📊 Quantités**")
                st.write(f"Sur-emballage : {selected_row['sur_emballage_libelle']}")
                st.write(f"Qté sur-emb. : {int(selected_row['quantite_sur_emballages'])}")
                st.write(f"UVC total : {int(selected_row['nb_uvc_total'])}")
                st.write(f"Poids : {format_number_fr(selected_row['poids_total_kg'])} kg")
            
            with col3:
                st.markdown("**📍 Stockage**")
                st.write(f"Site : {selected_row['site_stockage']}")
                st.write(f"Emplacement : {selected_row['emplacement']}")
                st.write(f"Statut : {selected_row['statut']}")
                if selected_row['date_expedition']:
                    st.write(f"Expédié le : {selected_row['date_expedition']}")
        
        with tab2:
            st.markdown("##### 💰 Valorisation")
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("**Coûts actuels**")
                st.write(f"• Matière première : {format_currency(selected_row['cout_matiere_premiere'])}")
                st.write(f"• Production : {format_currency(selected_row['cout_production'])}")
                st.write(f"• Sur-emballage : {format_currency(selected_row['cout_sur_emballage'])}")
                st.write(f"**• TOTAL : {format_currency(selected_row['cout_total'])}**")
            
            with col2:
                st.markdown("**Prix de vente**")
                st.write(f"• Prix unitaire/UVC : {format_currency(selected_row['prix_vente_unitaire'])}")
                st.write(f"• Nb UVC : {int(selected_row['nb_uvc_total'])}")
                st.write(f"**• PV TOTAL : {format_currency(selected_row['prix_vente_total'])}**")
                
                marge = selected_row['marge_brute']
                marge_pct = selected_row['marge_pct']
                color = "positive-value" if marge >= 0 else "negative-value"
                st.markdown(f"**• MARGE : <span class='{color}'>{format_currency(marge)} ({marge_pct:.1f}%)</span>**", unsafe_allow_html=True)
            
            st.markdown("---")
            st.markdown("##### ✏️ Modifier la valorisation")
            
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                new_prix_unit = st.number_input(
                    "Prix vente/UVC (€)",
                    min_value=0.0,
                    value=float(selected_row['prix_vente_unitaire'] or 0),
                    step=0.01,
                    key="edit_prix_unit"
                )
            
            with col2:
                new_cout_mp = st.number_input(
                    "Coût MP (€)",
                    min_value=0.0,
                    value=float(selected_row['cout_matiere_premiere'] or 0),
                    step=0.01,
                    key="edit_cout_mp"
                )
            
            with col3:
                new_cout_prod = st.number_input(
                    "Coût Prod (€)",
                    min_value=0.0,
                    value=float(selected_row['cout_production'] or 0),
                    step=0.01,
                    key="edit_cout_prod"
                )
            
            with col4:
                new_cout_suremb = st.number_input(
                    "Coût Sur-Emb (€)",
                    min_value=0.0,
                    value=float(selected_row['cout_sur_emballage'] or 0),
                    step=0.01,
                    key="edit_cout_suremb"
                )
            
            # Prévisualisation
            new_cout_total = new_cout_mp + new_cout_prod + new_cout_suremb
            new_pv_total = new_prix_unit * int(selected_row['nb_uvc_total'])
            new_marge = new_pv_total - new_cout_total
            new_marge_pct = (new_marge / new_cout_total * 100) if new_cout_total > 0 else 0
            
            st.info(f"📊 **Prévisualisation** : PV Total = {format_currency(new_pv_total)} | Coût = {format_currency(new_cout_total)} | Marge = {format_currency(new_marge)} ({new_marge_pct:.1f}%)")
            
            if st.button("💾 Enregistrer Valorisation", type="primary", key="btn_save_valo"):
                success, msg = update_valorisation_produit(
                    produit_id, new_prix_unit, new_cout_mp, new_cout_prod, new_cout_suremb
                )
                if success:
                    st.success(msg)
                    st.rerun()
                else:
                    st.error(msg)
        
        with tab3:
            st.markdown("##### 🔧 Actions")
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.markdown("**📤 Changer Statut**")
                statut_actuel = selected_row['statut']
                
                if statut_actuel == 'EN_STOCK':
                    if st.button("🚚 Marquer Expédié", key="btn_expedier", use_container_width=True):
                        st.session_state['show_expedition_form'] = True
                    
                    if st.session_state.get('show_expedition_form', False):
                        date_exp = st.date_input("Date expédition", value=date.today(), key="date_exp")
                        col_ok, col_cancel = st.columns(2)
                        with col_ok:
                            if st.button("✅ Valider", key="btn_val_exp"):
                                success, msg = update_statut_produit(produit_id, 'EXPÉDIÉ', date_exp)
                                if success:
                                    st.success(msg)
                                    st.session_state.pop('show_expedition_form', None)
                                    st.rerun()
                                else:
                                    st.error(msg)
                        with col_cancel:
                            if st.button("❌", key="btn_cancel_exp"):
                                st.session_state.pop('show_expedition_form', None)
                                st.rerun()
                
                elif statut_actuel == 'EXPÉDIÉ':
                    st.info("📦 Produit déjà expédié")
                    if st.button("↩️ Remettre EN_STOCK", key="btn_retour_stock"):
                        success, msg = update_statut_produit(produit_id, 'EN_STOCK')
                        if success:
                            st.success(msg)
                            st.rerun()
                        else:
                            st.error(msg)
            
            with col2:
                st.markdown("**⚫ Consommer**")
                if statut_actuel != 'CONSOMMÉ':
                    if st.button("⚫ Marquer Consommé", key="btn_consommer", use_container_width=True):
                        success, msg = update_statut_produit(produit_id, 'CONSOMMÉ')
                        if success:
                            st.success(msg)
                            st.rerun()
                        else:
                            st.error(msg)
                else:
                    st.info("Produit déjà consommé")
            
            with col3:
                st.markdown("**🗑️ Supprimer**")
                if st.button("🗑️ Supprimer", key="btn_delete", type="secondary", use_container_width=True):
                    st.session_state['confirm_delete'] = True
                
                if st.session_state.get('confirm_delete', False):
                    st.warning("⚠️ Confirmer la suppression ?")
                    col_ok, col_cancel = st.columns(2)
                    with col_ok:
                        if st.button("✅ Oui, supprimer", key="btn_confirm_del"):
                            success, msg = delete_produit_fini(produit_id)
                            if success:
                                st.success(msg)
                                st.session_state.pop('confirm_delete', None)
                                st.rerun()
                            else:
                                st.error(msg)
                    with col_cancel:
                        if st.button("❌ Annuler", key="btn_cancel_del"):
                            st.session_state.pop('confirm_delete', None)
                            st.rerun()
    
    else:
        st.info("👆 Sélectionnez une ligne dans le tableau pour voir les détails et actions")
    
    # ============================================================================
    # EXPORT
    # ============================================================================
    
    st.markdown("---")
    st.markdown("#### 📤 Exports")
    
    col1, col2 = st.columns(2)
    
    with col1:
        # Export CSV
        csv = df.to_csv(index=False).encode('utf-8')
        st.download_button(
            "📥 Télécharger CSV",
            csv,
            f"produits_finis_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
            "text/csv",
            use_container_width=True
        )
    
    with col2:
        # Export Excel
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Produits Finis')
        
        st.download_button(
            "📥 Télécharger Excel",
            buffer.getvalue(),
            f"produits_finis_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True
        )

else:
    st.info("📭 Aucun produit fini trouvé avec ces filtres")
    
    # Afficher quand même si la table est vide
    if filtre_statut == "Tous" and filtre_produit == "Tous" and not date_debut and not date_fin:
        st.markdown("---")
        st.markdown("💡 **Les produits finis sont créés automatiquement lors de la terminaison des jobs de production.**")
        st.markdown("→ Allez dans **Planning Production** pour créer et terminer des jobs.")

show_footer()
