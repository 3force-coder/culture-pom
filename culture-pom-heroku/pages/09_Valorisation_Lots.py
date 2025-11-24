import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from database import get_connection
from components import show_footer
from auth import is_authenticated
from auth.roles import is_admin

st.set_page_config(page_title="Valorisation Lots - Culture Pom", page_icon="💰", layout="wide")

# ============================================================
# CSS CUSTOM
# ============================================================
st.markdown("""
<style>
    .block-container {
        padding-top: 1rem !important;
        padding-bottom: 0.5rem !important;
    }
    h1, h2, h3, h4 {
        margin-top: 0.3rem !important;
        margin-bottom: 0.3rem !important;
    }
    .success-box {
        background: linear-gradient(135deg, #c8e6c9 0%, #a5d6a7 100%);
        border-left: 4px solid #388e3c;
        padding: 1.5rem;
        border-radius: 10px;
        text-align: center;
        margin: 2rem 0;
    }
    .warning-box {
        background: linear-gradient(135deg, #fff3e0 0%, #ffcc80 100%);
        border-left: 4px solid #f57c00;
        padding: 1rem;
        border-radius: 8px;
        margin: 1rem 0;
    }
    .info-box {
        background: linear-gradient(135deg, #e3f2fd 0%, #bbdefb 100%);
        border-left: 4px solid #1976d2;
        padding: 1rem;
        border-radius: 8px;
        margin: 1rem 0;
    }
    .history-item {
        background: #fafafa;
        border-left: 3px solid #9e9e9e;
        padding: 0.8rem;
        margin: 0.5rem 0;
        border-radius: 4px;
        font-size: 0.9rem;
    }
    .history-item.creation {
        border-left-color: #4caf50;
    }
    .history-item.modification {
        border-left-color: #ff9800;
    }
</style>
""", unsafe_allow_html=True)

# ============================================================
# AUTHENTIFICATION
# ============================================================

if not is_authenticated():
    st.warning("⚠️ Veuillez vous connecter pour accéder à cette page")
    st.stop()

if not is_admin():
    st.warning("⚠️ Accès réservé aux administrateurs (responsables achats)")
    st.stop()

st.title("💰 Valorisation des Lots")
st.caption("*Qualification des lots : prix d'achat et tare*")
st.markdown("---")

# ============================================================
# FONCTIONS UTILITAIRES
# ============================================================

def get_lots_non_qualifies(filtre_variete=None, filtre_producteur=None, filtre_site=None):
    """Récupère les lots sans prix OU sans tare"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        query = """
        SELECT 
            l.id,
            l.code_lot_interne,
            l.nom_usage,
            l.code_producteur,
            COALESCE(p.nom, l.code_producteur) as producteur_nom,
            l.code_variete,
            COALESCE(v.nom_variete, l.code_variete) as variete_nom,
            l.calibre_min,
            l.calibre_max,
            l.date_entree_stock,
            l.poids_total_brut_kg,
            l.site_stockage,
            l.prix_achat_euro_tonne,
            l.tare_achat_pct,
            l.qualified_by,
            l.qualified_at
        FROM lots_bruts l
        LEFT JOIN ref_producteurs p ON l.code_producteur = p.code_producteur
        LEFT JOIN ref_varietes v ON l.code_variete = v.code_variete
        WHERE l.is_active = TRUE
          AND (l.prix_achat_euro_tonne IS NULL OR l.tare_achat_pct IS NULL)
        """
        
        params = []
        
        if filtre_variete and filtre_variete != "Tous":
            query += " AND l.code_variete = %s"
            params.append(filtre_variete)
        
        if filtre_producteur and filtre_producteur != "Tous":
            query += " AND l.code_producteur = %s"
            params.append(filtre_producteur)
        
        if filtre_site and filtre_site != "Tous":
            query += " AND l.site_stockage = %s"
            params.append(filtre_site)
        
        query += " ORDER BY l.date_entree_stock DESC, l.code_lot_interne"
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        
        if rows:
            df = pd.DataFrame(rows)
            numeric_cols = ['poids_total_brut_kg', 'prix_achat_euro_tonne', 'tare_achat_pct', 'calibre_min', 'calibre_max']
            for col in numeric_cols:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
            return df
        return pd.DataFrame()
    except Exception as e:
        st.error(f"❌ Erreur : {str(e)}")
        return pd.DataFrame()

def get_lots_qualifies(filtre_variete=None, filtre_producteur=None, filtre_site=None):
    """Récupère tous les lots qualifiés (avec prix ET tare)"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        query = """
        SELECT 
            l.id,
            l.code_lot_interne,
            l.nom_usage,
            l.code_producteur,
            COALESCE(p.nom, l.code_producteur) as producteur_nom,
            l.code_variete,
            COALESCE(v.nom_variete, l.code_variete) as variete_nom,
            l.calibre_min,
            l.calibre_max,
            l.date_entree_stock,
            l.poids_total_brut_kg,
            l.site_stockage,
            l.prix_achat_euro_tonne,
            l.tare_achat_pct,
            l.valeur_lot_euro,
            l.qualified_by,
            l.qualified_at
        FROM lots_bruts l
        LEFT JOIN ref_producteurs p ON l.code_producteur = p.code_producteur
        LEFT JOIN ref_varietes v ON l.code_variete = v.code_variete
        WHERE l.is_active = TRUE
          AND l.prix_achat_euro_tonne IS NOT NULL 
          AND l.tare_achat_pct IS NOT NULL
        """
        
        params = []
        
        if filtre_variete and filtre_variete != "Tous":
            query += " AND l.code_variete = %s"
            params.append(filtre_variete)
        
        if filtre_producteur and filtre_producteur != "Tous":
            query += " AND l.code_producteur = %s"
            params.append(filtre_producteur)
        
        if filtre_site and filtre_site != "Tous":
            query += " AND l.site_stockage = %s"
            params.append(filtre_site)
        
        query += " ORDER BY l.qualified_at DESC NULLS LAST, l.date_entree_stock DESC"
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        
        if rows:
            df = pd.DataFrame(rows)
            numeric_cols = ['poids_total_brut_kg', 'prix_achat_euro_tonne', 'tare_achat_pct', 'valeur_lot_euro']
            for col in numeric_cols:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
            return df
        return pd.DataFrame()
    except Exception as e:
        st.error(f"❌ Erreur : {str(e)}")
        return pd.DataFrame()

def get_filtres_options():
    """Récupère les options pour les filtres"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT DISTINCT l.code_variete 
            FROM lots_bruts l 
            WHERE l.is_active = TRUE AND l.code_variete IS NOT NULL
            ORDER BY l.code_variete
        """)
        varietes = ["Tous"] + [r['code_variete'] for r in cursor.fetchall()]
        
        cursor.execute("""
            SELECT DISTINCT l.code_producteur 
            FROM lots_bruts l 
            WHERE l.is_active = TRUE AND l.code_producteur IS NOT NULL
            ORDER BY l.code_producteur
        """)
        producteurs = ["Tous"] + [r['code_producteur'] for r in cursor.fetchall()]
        
        cursor.execute("""
            SELECT DISTINCT l.site_stockage 
            FROM lots_bruts l 
            WHERE l.is_active = TRUE AND l.site_stockage IS NOT NULL
            ORDER BY l.site_stockage
        """)
        sites = ["Tous"] + [r['site_stockage'] for r in cursor.fetchall()]
        
        cursor.close()
        conn.close()
        
        return varietes, producteurs, sites
    except Exception as e:
        return ["Tous"], ["Tous"], ["Tous"]

def sauvegarder_qualification(lot_id, prix, tare, is_modification=False, ancien_prix=None, ancienne_tare=None, ancienne_valeur=None):
    """Sauvegarde la qualification d'un lot avec historique"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        qualified_by = st.session_state.get('username', 'system')
        
        # Récupérer infos lot
        cursor.execute("SELECT code_lot_interne, poids_total_brut_kg FROM lots_bruts WHERE id = %s", (int(lot_id),))
        result = cursor.fetchone()
        code_lot = result['code_lot_interne'] if result else 'INCONNU'
        poids_kg = float(result['poids_total_brut_kg']) if result and result['poids_total_brut_kg'] else 0
        
        # Calculer valeur lot
        poids_tonnes = poids_kg / 1000
        nouvelle_valeur = poids_tonnes * float(prix) * (1 - float(tare) / 100) if prix and tare is not None else None
        
        # 1. Mettre à jour lots_bruts
        cursor.execute("""
            UPDATE lots_bruts
            SET prix_achat_euro_tonne = %s,
                tare_achat_pct = %s,
                valeur_lot_euro = %s,
                qualified_by = %s,
                qualified_at = CURRENT_TIMESTAMP,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
        """, (float(prix), float(tare), nouvelle_valeur, qualified_by, int(lot_id)))
        
        # 2. Enregistrer dans historique
        type_action = 'MODIFICATION' if is_modification else 'CREATION'
        
        cursor.execute("""
            INSERT INTO lots_qualifications_historique (
                lot_id, code_lot_interne,
                ancien_prix_euro_tonne, ancienne_tare_pct, ancienne_valeur_euro,
                nouveau_prix_euro_tonne, nouvelle_tare_pct, nouvelle_valeur_euro,
                type_action, modified_by
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            int(lot_id), code_lot,
            ancien_prix, ancienne_tare, ancienne_valeur,
            float(prix), float(tare), nouvelle_valeur,
            type_action, qualified_by
        ))
        
        conn.commit()
        cursor.close()
        conn.close()
        return True
    except Exception as e:
        if 'conn' in locals():
            conn.rollback()
        st.error(f"❌ Erreur sauvegarde lot {lot_id}: {str(e)}")
        return False

def get_historique_lot(lot_id):
    """Récupère l'historique des qualifications d'un lot"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                id,
                type_action,
                ancien_prix_euro_tonne,
                ancienne_tare_pct,
                ancienne_valeur_euro,
                nouveau_prix_euro_tonne,
                nouvelle_tare_pct,
                nouvelle_valeur_euro,
                modified_by,
                modified_at
            FROM lots_qualifications_historique
            WHERE lot_id = %s
            ORDER BY modified_at DESC
        """, (int(lot_id),))
        
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        
        return pd.DataFrame(rows) if rows else pd.DataFrame()
    except Exception as e:
        return pd.DataFrame()

def get_historique_global(limit=50):
    """Récupère l'historique global des qualifications"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                h.id,
                h.code_lot_interne,
                h.type_action,
                h.ancien_prix_euro_tonne,
                h.ancienne_tare_pct,
                h.nouveau_prix_euro_tonne,
                h.nouvelle_tare_pct,
                h.modified_by,
                h.modified_at
            FROM lots_qualifications_historique h
            ORDER BY h.modified_at DESC
            LIMIT %s
        """, (limit,))
        
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        
        return pd.DataFrame(rows) if rows else pd.DataFrame()
    except Exception as e:
        return pd.DataFrame()

def get_stats_prix_variete():
    """Stats prix par variété"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT 
                COALESCE(v.nom_variete, l.code_variete) as variete,
                COUNT(*) as nb_lots,
                ROUND(AVG(l.prix_achat_euro_tonne)::numeric, 2) as prix_moyen,
                ROUND(MIN(l.prix_achat_euro_tonne)::numeric, 2) as prix_min,
                ROUND(MAX(l.prix_achat_euro_tonne)::numeric, 2) as prix_max,
                ROUND(SUM(l.poids_total_brut_kg/1000)::numeric, 1) as tonnage_total
            FROM lots_bruts l
            LEFT JOIN ref_varietes v ON l.code_variete = v.code_variete
            WHERE l.is_active = TRUE AND l.prix_achat_euro_tonne IS NOT NULL
            GROUP BY COALESCE(v.nom_variete, l.code_variete)
            ORDER BY tonnage_total DESC
        """)
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        return pd.DataFrame(rows) if rows else pd.DataFrame()
    except:
        return pd.DataFrame()

def get_stats_prix_producteur():
    """Stats prix par producteur (top 20)"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT 
                COALESCE(p.nom, l.code_producteur) as producteur,
                COUNT(*) as nb_lots,
                ROUND(AVG(l.prix_achat_euro_tonne)::numeric, 2) as prix_moyen,
                ROUND(MIN(l.prix_achat_euro_tonne)::numeric, 2) as prix_min,
                ROUND(MAX(l.prix_achat_euro_tonne)::numeric, 2) as prix_max,
                ROUND(SUM(l.poids_total_brut_kg/1000)::numeric, 1) as tonnage_total
            FROM lots_bruts l
            LEFT JOIN ref_producteurs p ON l.code_producteur = p.code_producteur
            WHERE l.is_active = TRUE AND l.prix_achat_euro_tonne IS NOT NULL
            GROUP BY COALESCE(p.nom, l.code_producteur)
            ORDER BY tonnage_total DESC
            LIMIT 20
        """)
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        return pd.DataFrame(rows) if rows else pd.DataFrame()
    except:
        return pd.DataFrame()

def get_stats_tare_variete():
    """Stats tare par variété"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT 
                COALESCE(v.nom_variete, l.code_variete) as variete,
                COUNT(*) as nb_lots,
                ROUND(AVG(l.tare_achat_pct)::numeric, 1) as tare_moyenne,
                ROUND(MIN(l.tare_achat_pct)::numeric, 1) as tare_min,
                ROUND(MAX(l.tare_achat_pct)::numeric, 1) as tare_max
            FROM lots_bruts l
            LEFT JOIN ref_varietes v ON l.code_variete = v.code_variete
            WHERE l.is_active = TRUE AND l.tare_achat_pct IS NOT NULL
            GROUP BY COALESCE(v.nom_variete, l.code_variete)
            ORDER BY nb_lots DESC
        """)
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        return pd.DataFrame(rows) if rows else pd.DataFrame()
    except:
        return pd.DataFrame()

def get_evolution_prix_temps():
    """Évolution prix dans le temps"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT 
                DATE_TRUNC('week', l.date_entree_stock)::date as semaine,
                ROUND(AVG(l.prix_achat_euro_tonne)::numeric, 2) as prix_moyen,
                COUNT(*) as nb_lots,
                ROUND(SUM(l.poids_total_brut_kg/1000)::numeric, 1) as tonnage
            FROM lots_bruts l
            WHERE l.is_active = TRUE 
              AND l.prix_achat_euro_tonne IS NOT NULL
              AND l.date_entree_stock IS NOT NULL
            GROUP BY DATE_TRUNC('week', l.date_entree_stock)
            ORDER BY semaine DESC
            LIMIT 52
        """)
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        df = pd.DataFrame(rows) if rows else pd.DataFrame()
        if not df.empty:
            df = df.sort_values('semaine')
        return df
    except:
        return pd.DataFrame()

def get_evolution_tare_temps():
    """Évolution tare dans le temps"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT 
                DATE_TRUNC('week', l.date_entree_stock)::date as semaine,
                ROUND(AVG(l.tare_achat_pct)::numeric, 1) as tare_moyenne,
                COUNT(*) as nb_lots
            FROM lots_bruts l
            WHERE l.is_active = TRUE 
              AND l.tare_achat_pct IS NOT NULL
              AND l.date_entree_stock IS NOT NULL
            GROUP BY DATE_TRUNC('week', l.date_entree_stock)
            ORDER BY semaine DESC
            LIMIT 52
        """)
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        df = pd.DataFrame(rows) if rows else pd.DataFrame()
        if not df.empty:
            df = df.sort_values('semaine')
        return df
    except:
        return pd.DataFrame()

def get_kpis_valorisation():
    """KPIs globaux de valorisation"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) as total FROM lots_bruts WHERE is_active = TRUE")
        total_lots = cursor.fetchone()['total']
        
        cursor.execute("""
            SELECT COUNT(*) as qualifies 
            FROM lots_bruts 
            WHERE is_active = TRUE 
              AND prix_achat_euro_tonne IS NOT NULL 
              AND tare_achat_pct IS NOT NULL
        """)
        lots_qualifies = cursor.fetchone()['qualifies']
        
        lots_a_qualifier = total_lots - lots_qualifies
        
        cursor.execute("""
            SELECT COALESCE(SUM(valeur_lot_euro), 0) as valeur_totale
            FROM lots_bruts 
            WHERE is_active = TRUE 
              AND valeur_lot_euro IS NOT NULL
        """)
        valeur_totale = float(cursor.fetchone()['valeur_totale'])
        
        cursor.execute("""
            SELECT ROUND(AVG(prix_achat_euro_tonne)::numeric, 2) as prix_moyen
            FROM lots_bruts 
            WHERE is_active = TRUE AND prix_achat_euro_tonne IS NOT NULL
        """)
        result = cursor.fetchone()
        prix_moyen = float(result['prix_moyen']) if result['prix_moyen'] else 0
        
        cursor.execute("""
            SELECT ROUND(AVG(tare_achat_pct)::numeric, 1) as tare_moyenne
            FROM lots_bruts 
            WHERE is_active = TRUE AND tare_achat_pct IS NOT NULL
        """)
        result = cursor.fetchone()
        tare_moyenne = float(result['tare_moyenne']) if result['tare_moyenne'] else 0
        
        cursor.close()
        conn.close()
        
        return {
            'total_lots': total_lots,
            'lots_qualifies': lots_qualifies,
            'lots_a_qualifier': lots_a_qualifier,
            'valeur_totale': valeur_totale,
            'prix_moyen': prix_moyen,
            'tare_moyenne': tare_moyenne,
            'pct_qualifies': (lots_qualifies / total_lots * 100) if total_lots > 0 else 0
        }
    except Exception as e:
        st.error(f"Erreur KPIs: {str(e)}")
        return None

# ============================================================
# KPIs
# ============================================================

kpis = get_kpis_valorisation()

if kpis:
    col1, col2, col3, col4, col5, col6 = st.columns(6)
    
    with col1:
        st.metric("📦 Total Lots", kpis['total_lots'])
    with col2:
        st.metric("✅ Qualifiés", kpis['lots_qualifies'])
    with col3:
        st.metric("⏳ À qualifier", kpis['lots_a_qualifier'])
    with col4:
        st.metric("💰 Valeur Stock", f"{kpis['valeur_totale']:,.0f} €")
    with col5:
        st.metric("📈 Prix Moyen", f"{kpis['prix_moyen']:.0f} €/T")
    with col6:
        st.metric("📉 Tare Moyenne", f"{kpis['tare_moyenne']:.1f} %")

st.markdown("---")

# ============================================================
# ONGLETS
# ============================================================

tab1, tab2, tab3, tab4 = st.tabs(["📝 Qualification", "🔧 Modifier", "📊 Statistiques", "📜 Historique"])

# ============================================================
# ONGLET 1 : QUALIFICATION (lots non qualifiés)
# ============================================================

with tab1:
    
    varietes, producteurs, sites = get_filtres_options()
    
    st.markdown("### 🔍 Filtres")
    col_f1, col_f2, col_f3 = st.columns(3)
    
    with col_f1:
        filtre_variete_q = st.selectbox("Variété", varietes, key="filtre_var_q")
    with col_f2:
        filtre_producteur_q = st.selectbox("Producteur", producteurs, key="filtre_prod_q")
    with col_f3:
        filtre_site_q = st.selectbox("Site", sites, key="filtre_site_q")
    
    st.markdown("---")
    
    df_lots = get_lots_non_qualifies(filtre_variete_q, filtre_producteur_q, filtre_site_q)
    
    if df_lots.empty:
        st.markdown("""
        <div class="success-box">
            <h2>🎉 Bravo !</h2>
            <h3>Tous les lots sont qualifiés</h3>
            <p>Aucun lot en attente de qualification avec les filtres actuels.</p>
            <p>Consultez l'onglet <strong>📊 Statistiques</strong> pour analyser vos données<br>
            ou <strong>🔧 Modifier</strong> pour corriger un lot existant.</p>
        </div>
        """, unsafe_allow_html=True)
    else:
        nb_lots = len(df_lots)
        st.markdown(f"### ⏳ {nb_lots} lot(s) à qualifier")
        
        st.markdown("""
        <div class="warning-box">
            <strong>📝 Instructions :</strong> Renseignez le <strong>Prix (€/T)</strong> et la <strong>Tare (%)</strong> pour chaque lot, puis cliquez sur <strong>💾 Enregistrer</strong>.
        </div>
        """, unsafe_allow_html=True)
        
        df_edit = df_lots[[
            'id', 'code_lot_interne', 'nom_usage', 'producteur_nom', 'variete_nom',
            'calibre_min', 'calibre_max', 'date_entree_stock', 'poids_total_brut_kg',
            'site_stockage', 'prix_achat_euro_tonne', 'tare_achat_pct'
        ]].copy()
        
        df_edit = df_edit.rename(columns={
            'code_lot_interne': 'Code Lot',
            'nom_usage': 'Nom',
            'producteur_nom': 'Producteur',
            'variete_nom': 'Variété',
            'calibre_min': 'Cal Min',
            'calibre_max': 'Cal Max',
            'date_entree_stock': 'Date Entrée',
            'poids_total_brut_kg': 'Poids (kg)',
            'site_stockage': 'Site',
            'prix_achat_euro_tonne': 'Prix (€/T)',
            'tare_achat_pct': 'Tare (%)'
        })
        
        column_config = {
            'id': None,
            'Code Lot': st.column_config.TextColumn('Code Lot', disabled=True, width="medium"),
            'Nom': st.column_config.TextColumn('Nom', disabled=True, width="medium"),
            'Producteur': st.column_config.TextColumn('Producteur', disabled=True, width="medium"),
            'Variété': st.column_config.TextColumn('Variété', disabled=True, width="small"),
            'Cal Min': st.column_config.NumberColumn('Cal Min', disabled=True, format="%d", width="small"),
            'Cal Max': st.column_config.NumberColumn('Cal Max', disabled=True, format="%d", width="small"),
            'Date Entrée': st.column_config.DateColumn('Date Entrée', disabled=True, width="small"),
            'Poids (kg)': st.column_config.NumberColumn('Poids (kg)', disabled=True, format="%.0f", width="small"),
            'Site': st.column_config.TextColumn('Site', disabled=True, width="small"),
            'Prix (€/T)': st.column_config.NumberColumn('Prix (€/T)', min_value=50, max_value=1500, step=10, format="%.0f", width="small"),
            'Tare (%)': st.column_config.NumberColumn('Tare (%)', min_value=0, max_value=100, step=1, format="%.1f", width="small")
        }
        
        edited_df = st.data_editor(
            df_edit,
            column_config=column_config,
            use_container_width=True,
            hide_index=True,
            num_rows="fixed",
            key="qualif_editor"
        )
        
        col_btn1, col_btn2 = st.columns([1, 4])
        
        with col_btn1:
            if st.button("💾 Enregistrer", type="primary", use_container_width=True, key="save_qualif"):
                modifications = 0
                erreurs = 0
                
                for idx, row in edited_df.iterrows():
                    lot_id = row['id']
                    new_prix = row['Prix (€/T)']
                    new_tare = row['Tare (%)']
                    
                    if pd.notna(new_prix) and pd.notna(new_tare):
                        if sauvegarder_qualification(lot_id, new_prix, new_tare, is_modification=False):
                            modifications += 1
                        else:
                            erreurs += 1
                
                if modifications > 0:
                    st.success(f"✅ {modifications} lot(s) qualifié(s) avec succès !")
                    st.balloons()
                    st.rerun()
                elif erreurs > 0:
                    st.error(f"❌ {erreurs} erreur(s) lors de l'enregistrement")
                else:
                    st.info("ℹ️ Renseignez Prix ET Tare pour qualifier un lot")
        
        with col_btn2:
            if st.button("🔄 Actualiser", use_container_width=False, key="refresh_qualif"):
                st.rerun()

# ============================================================
# ONGLET 2 : MODIFIER (lots déjà qualifiés)
# ============================================================

with tab2:
    st.markdown("### 🔧 Modifier un lot qualifié")
    
    st.markdown("""
    <div class="info-box">
        <strong>ℹ️ Information :</strong> Vous pouvez modifier le prix et/ou la tare d'un lot déjà qualifié. 
        Toutes les modifications sont enregistrées dans l'<strong>📜 Historique</strong>.
    </div>
    """, unsafe_allow_html=True)
    
    varietes, producteurs, sites = get_filtres_options()
    
    col_f1, col_f2, col_f3 = st.columns(3)
    with col_f1:
        filtre_variete_m = st.selectbox("Variété", varietes, key="filtre_var_m")
    with col_f2:
        filtre_producteur_m = st.selectbox("Producteur", producteurs, key="filtre_prod_m")
    with col_f3:
        filtre_site_m = st.selectbox("Site", sites, key="filtre_site_m")
    
    st.markdown("---")
    
    df_qualifies = get_lots_qualifies(filtre_variete_m, filtre_producteur_m, filtre_site_m)
    
    if df_qualifies.empty:
        st.info("Aucun lot qualifié avec ces filtres")
    else:
        st.markdown(f"**{len(df_qualifies)} lot(s) qualifié(s)**")
        
        # Préparer DataFrame pour édition
        df_edit_m = df_qualifies[[
            'id', 'code_lot_interne', 'nom_usage', 'producteur_nom', 'variete_nom',
            'date_entree_stock', 'poids_total_brut_kg', 'site_stockage',
            'prix_achat_euro_tonne', 'tare_achat_pct', 'valeur_lot_euro',
            'qualified_by', 'qualified_at'
        ]].copy()
        
        df_edit_m = df_edit_m.rename(columns={
            'code_lot_interne': 'Code Lot',
            'nom_usage': 'Nom',
            'producteur_nom': 'Producteur',
            'variete_nom': 'Variété',
            'date_entree_stock': 'Date Entrée',
            'poids_total_brut_kg': 'Poids (kg)',
            'site_stockage': 'Site',
            'prix_achat_euro_tonne': 'Prix (€/T)',
            'tare_achat_pct': 'Tare (%)',
            'valeur_lot_euro': 'Valeur (€)',
            'qualified_by': 'Par',
            'qualified_at': 'Le'
        })
        
        # Stocker original pour comparaison
        df_original_m = df_edit_m.copy()
        
        column_config_m = {
            'id': None,
            'Code Lot': st.column_config.TextColumn('Code Lot', disabled=True, width="medium"),
            'Nom': st.column_config.TextColumn('Nom', disabled=True, width="medium"),
            'Producteur': st.column_config.TextColumn('Producteur', disabled=True, width="small"),
            'Variété': st.column_config.TextColumn('Variété', disabled=True, width="small"),
            'Date Entrée': st.column_config.DateColumn('Date Entrée', disabled=True, width="small"),
            'Poids (kg)': st.column_config.NumberColumn('Poids (kg)', disabled=True, format="%.0f", width="small"),
            'Site': st.column_config.TextColumn('Site', disabled=True, width="small"),
            'Prix (€/T)': st.column_config.NumberColumn('Prix (€/T)', min_value=50, max_value=1500, step=10, format="%.0f", width="small"),
            'Tare (%)': st.column_config.NumberColumn('Tare (%)', min_value=0, max_value=100, step=1, format="%.1f", width="small"),
            'Valeur (€)': st.column_config.NumberColumn('Valeur (€)', disabled=True, format="%.0f", width="small"),
            'Par': st.column_config.TextColumn('Par', disabled=True, width="small"),
            'Le': st.column_config.DatetimeColumn('Le', disabled=True, width="small")
        }
        
        edited_df_m = st.data_editor(
            df_edit_m,
            column_config=column_config_m,
            use_container_width=True,
            hide_index=True,
            num_rows="fixed",
            key="modif_editor"
        )
        
        col_btn1, col_btn2 = st.columns([1, 4])
        
        with col_btn1:
            if st.button("💾 Enregistrer modifications", type="primary", use_container_width=True, key="save_modif"):
                modifications = 0
                
                for idx in edited_df_m.index:
                    lot_id = edited_df_m.loc[idx, 'id']
                    new_prix = edited_df_m.loc[idx, 'Prix (€/T)']
                    new_tare = edited_df_m.loc[idx, 'Tare (%)']
                    
                    # Récupérer anciennes valeurs
                    orig_row = df_qualifies[df_qualifies['id'] == lot_id].iloc[0]
                    old_prix = float(orig_row['prix_achat_euro_tonne']) if pd.notna(orig_row['prix_achat_euro_tonne']) else None
                    old_tare = float(orig_row['tare_achat_pct']) if pd.notna(orig_row['tare_achat_pct']) else None
                    old_valeur = float(orig_row['valeur_lot_euro']) if pd.notna(orig_row['valeur_lot_euro']) else None
                    
                    # Vérifier si modification
                    prix_changed = (new_prix != old_prix) if old_prix else False
                    tare_changed = (new_tare != old_tare) if old_tare else False
                    
                    if prix_changed or tare_changed:
                        if sauvegarder_qualification(
                            lot_id, new_prix, new_tare,
                            is_modification=True,
                            ancien_prix=old_prix,
                            ancienne_tare=old_tare,
                            ancienne_valeur=old_valeur
                        ):
                            modifications += 1
                
                if modifications > 0:
                    st.success(f"✅ {modifications} lot(s) modifié(s) avec succès !")
                    st.rerun()
                else:
                    st.info("ℹ️ Aucune modification détectée")
        
        with col_btn2:
            if st.button("🔄 Actualiser", use_container_width=False, key="refresh_modif"):
                st.rerun()

# ============================================================
# ONGLET 3 : STATISTIQUES
# ============================================================

with tab3:
    st.subheader("📊 Statistiques de Valorisation")
    
    stat_tab1, stat_tab2, stat_tab3, stat_tab4 = st.tabs([
        "💶 Prix par Variété", 
        "🏭 Prix par Producteur",
        "📉 Tare par Variété",
        "📈 Évolution Temporelle"
    ])
    
    with stat_tab1:
        st.markdown("### 💶 Prix d'achat par Variété")
        df_prix_var = get_stats_prix_variete()
        
        if not df_prix_var.empty:
            st.dataframe(
                df_prix_var.rename(columns={
                    'variete': 'Variété', 'nb_lots': 'Nb Lots',
                    'prix_moyen': 'Prix Moyen (€/T)', 'prix_min': 'Prix Min',
                    'prix_max': 'Prix Max', 'tonnage_total': 'Tonnage (T)'
                }),
                use_container_width=True, hide_index=True
            )
            st.markdown("---")
            st.markdown("#### 📊 Prix moyen par variété")
            df_chart = df_prix_var.head(15).sort_values('prix_moyen', ascending=True)
            st.bar_chart(df_chart.set_index('variete')['prix_moyen'], use_container_width=True)
        else:
            st.info("Aucune donnée disponible")
    
    with stat_tab2:
        st.markdown("### 🏭 Prix d'achat par Producteur (Top 20)")
        df_prix_prod = get_stats_prix_producteur()
        
        if not df_prix_prod.empty:
            st.dataframe(
                df_prix_prod.rename(columns={
                    'producteur': 'Producteur', 'nb_lots': 'Nb Lots',
                    'prix_moyen': 'Prix Moyen (€/T)', 'prix_min': 'Prix Min',
                    'prix_max': 'Prix Max', 'tonnage_total': 'Tonnage (T)'
                }),
                use_container_width=True, hide_index=True
            )
            st.markdown("---")
            st.markdown("#### 📊 Prix moyen par producteur (Top 15)")
            df_chart = df_prix_prod.head(15).sort_values('prix_moyen', ascending=True)
            st.bar_chart(df_chart.set_index('producteur')['prix_moyen'], use_container_width=True)
        else:
            st.info("Aucune donnée disponible")
    
    with stat_tab3:
        st.markdown("### 📉 Tare d'achat par Variété")
        df_tare_var = get_stats_tare_variete()
        
        if not df_tare_var.empty:
            st.dataframe(
                df_tare_var.rename(columns={
                    'variete': 'Variété', 'nb_lots': 'Nb Lots',
                    'tare_moyenne': 'Tare Moyenne (%)', 'tare_min': 'Tare Min', 'tare_max': 'Tare Max'
                }),
                use_container_width=True, hide_index=True
            )
            st.markdown("---")
            st.markdown("#### 📊 Tare moyenne par variété")
            df_chart = df_tare_var.head(15).sort_values('tare_moyenne', ascending=False)
            st.bar_chart(df_chart.set_index('variete')['tare_moyenne'], use_container_width=True)
        else:
            st.info("Aucune donnée disponible")
    
    with stat_tab4:
        st.markdown("### 📈 Évolution dans le temps")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("#### Prix moyen par semaine")
            df_evol_prix = get_evolution_prix_temps()
            if not df_evol_prix.empty:
                st.line_chart(df_evol_prix.set_index('semaine')['prix_moyen'], use_container_width=True)
                if len(df_evol_prix) >= 4:
                    recent = df_evol_prix['prix_moyen'].tail(4).mean()
                    ancien = df_evol_prix['prix_moyen'].head(4).mean()
                    tendance = ((recent - ancien) / ancien * 100) if ancien > 0 else 0
                    if tendance > 0:
                        st.success(f"📈 Tendance : +{tendance:.1f}%")
                    else:
                        st.error(f"📉 Tendance : {tendance:.1f}%")
            else:
                st.info("Aucune donnée disponible")
        
        with col2:
            st.markdown("#### Tare moyenne par semaine")
            df_evol_tare = get_evolution_tare_temps()
            if not df_evol_tare.empty:
                st.line_chart(df_evol_tare.set_index('semaine')['tare_moyenne'], use_container_width=True)
                if len(df_evol_tare) >= 4:
                    recent = df_evol_tare['tare_moyenne'].tail(4).mean()
                    ancien = df_evol_tare['tare_moyenne'].head(4).mean()
                    tendance = recent - ancien
                    if tendance < 0:
                        st.success(f"📉 Tendance tare : {tendance:.1f}% (amélioration)")
                    else:
                        st.warning(f"📈 Tendance tare : +{tendance:.1f}%")
            else:
                st.info("Aucune donnée disponible")
        
        st.markdown("---")
        st.markdown("#### 📦 Tonnage entré par semaine")
        df_evol_prix = get_evolution_prix_temps()
        if not df_evol_prix.empty and 'tonnage' in df_evol_prix.columns:
            st.bar_chart(df_evol_prix.set_index('semaine')['tonnage'], use_container_width=True)

# ============================================================
# ONGLET 4 : HISTORIQUE
# ============================================================

with tab4:
    st.markdown("### 📜 Historique des qualifications")
    
    st.markdown("""
    <div class="info-box">
        <strong>ℹ️ Traçabilité :</strong> Toutes les créations et modifications de qualification sont enregistrées ici.
    </div>
    """, unsafe_allow_html=True)
    
    # Sélection nombre d'entrées
    nb_entries = st.selectbox("Afficher les dernières", [25, 50, 100, 200], index=1, key="hist_limit")
    
    df_hist = get_historique_global(limit=nb_entries)
    
    if df_hist.empty:
        st.info("Aucun historique disponible")
    else:
        # Afficher tableau
        df_hist_display = df_hist.copy()
        df_hist_display = df_hist_display.rename(columns={
            'code_lot_interne': 'Code Lot',
            'type_action': 'Action',
            'ancien_prix_euro_tonne': 'Ancien Prix',
            'ancienne_tare_pct': 'Ancienne Tare',
            'nouveau_prix_euro_tonne': 'Nouveau Prix',
            'nouvelle_tare_pct': 'Nouvelle Tare',
            'modified_by': 'Par',
            'modified_at': 'Date'
        })
        
        column_config_h = {
            'id': None,
            'Code Lot': st.column_config.TextColumn('Code Lot', width="medium"),
            'Action': st.column_config.TextColumn('Action', width="small"),
            'Ancien Prix': st.column_config.NumberColumn('Ancien Prix', format="%.0f €/T", width="small"),
            'Ancienne Tare': st.column_config.NumberColumn('Ancienne Tare', format="%.1f %%", width="small"),
            'Nouveau Prix': st.column_config.NumberColumn('Nouveau Prix', format="%.0f €/T", width="small"),
            'Nouvelle Tare': st.column_config.NumberColumn('Nouvelle Tare', format="%.1f %%", width="small"),
            'Par': st.column_config.TextColumn('Par', width="small"),
            'Date': st.column_config.DatetimeColumn('Date', width="medium")
        }
        
        st.dataframe(
            df_hist_display[['Code Lot', 'Action', 'Ancien Prix', 'Ancienne Tare', 'Nouveau Prix', 'Nouvelle Tare', 'Par', 'Date']],
            column_config=column_config_h,
            use_container_width=True,
            hide_index=True
        )
        
        # Stats historique
        st.markdown("---")
        col1, col2, col3 = st.columns(3)
        
        with col1:
            nb_creations = len(df_hist[df_hist['type_action'] == 'CREATION'])
            st.metric("🆕 Créations", nb_creations)
        
        with col2:
            nb_modifs = len(df_hist[df_hist['type_action'] == 'MODIFICATION'])
            st.metric("✏️ Modifications", nb_modifs)
        
        with col3:
            users = df_hist['modified_by'].nunique()
            st.metric("👥 Utilisateurs", users)

show_footer()
