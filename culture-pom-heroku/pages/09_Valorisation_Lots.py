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
    .stat-card {
        background: #f5f5f5;
        padding: 1rem;
        border-radius: 8px;
        text-align: center;
        margin: 0.5rem 0;
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
            # Convertir colonnes numériques
            numeric_cols = ['poids_total_brut_kg', 'prix_achat_euro_tonne', 'tare_achat_pct', 'calibre_min', 'calibre_max']
            for col in numeric_cols:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
            return df
        return pd.DataFrame()
    except Exception as e:
        st.error(f"❌ Erreur : {str(e)}")
        return pd.DataFrame()

def get_tous_les_lots_qualifies():
    """Récupère tous les lots qualifiés (avec prix ET tare)"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
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
        ORDER BY l.date_entree_stock DESC
        """)
        
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
        
        # Variétés
        cursor.execute("""
            SELECT DISTINCT l.code_variete 
            FROM lots_bruts l 
            WHERE l.is_active = TRUE AND l.code_variete IS NOT NULL
            ORDER BY l.code_variete
        """)
        varietes = ["Tous"] + [r['code_variete'] for r in cursor.fetchall()]
        
        # Producteurs
        cursor.execute("""
            SELECT DISTINCT l.code_producteur 
            FROM lots_bruts l 
            WHERE l.is_active = TRUE AND l.code_producteur IS NOT NULL
            ORDER BY l.code_producteur
        """)
        producteurs = ["Tous"] + [r['code_producteur'] for r in cursor.fetchall()]
        
        # Sites
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

def sauvegarder_qualification(lot_id, prix, tare):
    """Sauvegarde la qualification d'un lot"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        qualified_by = st.session_state.get('username', 'system')
        
        # Calculer valeur lot
        cursor.execute("SELECT poids_total_brut_kg FROM lots_bruts WHERE id = %s", (lot_id,))
        result = cursor.fetchone()
        poids_kg = float(result['poids_total_brut_kg']) if result and result['poids_total_brut_kg'] else 0
        
        # Valeur = (poids en tonnes) * prix * (1 - tare%)
        poids_tonnes = poids_kg / 1000
        valeur = poids_tonnes * float(prix) * (1 - float(tare) / 100) if prix and tare is not None else None
        
        cursor.execute("""
            UPDATE lots_bruts
            SET prix_achat_euro_tonne = %s,
                tare_achat_pct = %s,
                valeur_lot_euro = %s,
                qualified_by = %s,
                qualified_at = CURRENT_TIMESTAMP,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
        """, (prix, tare, valeur, qualified_by, int(lot_id)))
        
        conn.commit()
        cursor.close()
        conn.close()
        return True
    except Exception as e:
        if 'conn' in locals():
            conn.rollback()
        st.error(f"❌ Erreur sauvegarde lot {lot_id}: {str(e)}")
        return False

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
        
        # Total lots
        cursor.execute("SELECT COUNT(*) as total FROM lots_bruts WHERE is_active = TRUE")
        total_lots = cursor.fetchone()['total']
        
        # Lots qualifiés
        cursor.execute("""
            SELECT COUNT(*) as qualifies 
            FROM lots_bruts 
            WHERE is_active = TRUE 
              AND prix_achat_euro_tonne IS NOT NULL 
              AND tare_achat_pct IS NOT NULL
        """)
        lots_qualifies = cursor.fetchone()['qualifies']
        
        # Lots à qualifier
        lots_a_qualifier = total_lots - lots_qualifies
        
        # Valeur totale stock qualifié
        cursor.execute("""
            SELECT COALESCE(SUM(valeur_lot_euro), 0) as valeur_totale
            FROM lots_bruts 
            WHERE is_active = TRUE 
              AND valeur_lot_euro IS NOT NULL
        """)
        valeur_totale = float(cursor.fetchone()['valeur_totale'])
        
        # Prix moyen global
        cursor.execute("""
            SELECT ROUND(AVG(prix_achat_euro_tonne)::numeric, 2) as prix_moyen
            FROM lots_bruts 
            WHERE is_active = TRUE AND prix_achat_euro_tonne IS NOT NULL
        """)
        result = cursor.fetchone()
        prix_moyen = float(result['prix_moyen']) if result['prix_moyen'] else 0
        
        # Tare moyenne globale
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
        color = "normal" if kpis['lots_a_qualifier'] == 0 else "inverse"
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

tab1, tab2 = st.tabs(["📝 Qualification", "📊 Statistiques"])

# ============================================================
# ONGLET 1 : QUALIFICATION
# ============================================================

with tab1:
    
    # Charger les options de filtres
    varietes, producteurs, sites = get_filtres_options()
    
    # Filtres
    st.markdown("### 🔍 Filtres")
    col_f1, col_f2, col_f3 = st.columns(3)
    
    with col_f1:
        filtre_variete = st.selectbox("Variété", varietes, key="filtre_var")
    with col_f2:
        filtre_producteur = st.selectbox("Producteur", producteurs, key="filtre_prod")
    with col_f3:
        filtre_site = st.selectbox("Site", sites, key="filtre_site")
    
    st.markdown("---")
    
    # Charger lots non qualifiés
    df_lots = get_lots_non_qualifies(filtre_variete, filtre_producteur, filtre_site)
    
    if df_lots.empty:
        # Message positif si tout est qualifié
        st.markdown("""
        <div class="success-box">
            <h2>🎉 Bravo !</h2>
            <h3>Tous les lots sont qualifiés</h3>
            <p>Aucun lot en attente de qualification avec les filtres actuels.</p>
            <p>Consultez l'onglet <strong>📊 Statistiques</strong> pour analyser vos données.</p>
        </div>
        """, unsafe_allow_html=True)
        
        # Afficher quand même la section modification si besoin
        with st.expander("🔧 Modifier un lot déjà qualifié"):
            st.caption("*Pour corriger prix ou tare d'un lot déjà qualifié*")
            
            df_qualifies = get_tous_les_lots_qualifies()
            if not df_qualifies.empty:
                lot_options = [f"{r['code_lot_interne']} - {r['variete_nom']} ({r['prix_achat_euro_tonne']:.0f}€/T, {r['tare_achat_pct']:.1f}%)" 
                              for _, r in df_qualifies.head(50).iterrows()]
                
                selected_lot_str = st.selectbox("Sélectionner un lot", ["Choisir..."] + lot_options)
                
                if selected_lot_str != "Choisir...":
                    idx = lot_options.index(selected_lot_str)
                    lot_data = df_qualifies.iloc[idx]
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        new_prix = st.number_input(
                            "Prix (€/T)", 
                            min_value=50.0, 
                            max_value=1500.0, 
                            value=float(lot_data['prix_achat_euro_tonne'] or 200),
                            step=10.0,
                            key="mod_prix"
                        )
                    with col2:
                        new_tare = st.number_input(
                            "Tare (%)", 
                            min_value=0.0, 
                            max_value=100.0, 
                            value=float(lot_data['tare_achat_pct'] or 20),
                            step=1.0,
                            key="mod_tare"
                        )
                    
                    if st.button("💾 Mettre à jour", type="primary"):
                        if sauvegarder_qualification(lot_data['id'], new_prix, new_tare):
                            st.success("✅ Lot mis à jour")
                            st.rerun()
    else:
        # Lots à qualifier
        nb_lots = len(df_lots)
        st.markdown(f"### ⏳ {nb_lots} lot(s) à qualifier")
        
        st.markdown("""
        <div class="warning-box">
            <strong>📝 Instructions :</strong> Renseignez le <strong>Prix (€/T)</strong> et la <strong>Tare (%)</strong> pour chaque lot, puis cliquez sur <strong>💾 Enregistrer</strong>.
        </div>
        """, unsafe_allow_html=True)
        
        # Préparer le DataFrame pour édition
        df_edit = df_lots[[
            'id', 'code_lot_interne', 'nom_usage', 'producteur_nom', 'variete_nom',
            'calibre_min', 'calibre_max', 'date_entree_stock', 'poids_total_brut_kg',
            'site_stockage', 'prix_achat_euro_tonne', 'tare_achat_pct'
        ]].copy()
        
        # Renommer colonnes pour affichage
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
        
        # Stocker original pour comparaison
        if 'df_original_qualif' not in st.session_state:
            st.session_state.df_original_qualif = df_edit.copy()
        
        # Configuration colonnes
        column_config = {
            'id': None,  # Masquer
            'Code Lot': st.column_config.TextColumn('Code Lot', disabled=True, width="medium"),
            'Nom': st.column_config.TextColumn('Nom', disabled=True, width="medium"),
            'Producteur': st.column_config.TextColumn('Producteur', disabled=True, width="medium"),
            'Variété': st.column_config.TextColumn('Variété', disabled=True, width="small"),
            'Cal Min': st.column_config.NumberColumn('Cal Min', disabled=True, format="%d", width="small"),
            'Cal Max': st.column_config.NumberColumn('Cal Max', disabled=True, format="%d", width="small"),
            'Date Entrée': st.column_config.DateColumn('Date Entrée', disabled=True, width="small"),
            'Poids (kg)': st.column_config.NumberColumn('Poids (kg)', disabled=True, format="%.0f", width="small"),
            'Site': st.column_config.TextColumn('Site', disabled=True, width="small"),
            'Prix (€/T)': st.column_config.NumberColumn(
                'Prix (€/T)', 
                min_value=50, 
                max_value=1500, 
                step=10,
                format="%.0f",
                width="small",
                required=True
            ),
            'Tare (%)': st.column_config.NumberColumn(
                'Tare (%)', 
                min_value=0, 
                max_value=100, 
                step=1,
                format="%.1f",
                width="small",
                required=True
            )
        }
        
        # Tableau éditable
        edited_df = st.data_editor(
            df_edit,
            column_config=column_config,
            use_container_width=True,
            hide_index=True,
            num_rows="fixed",
            key="qualif_editor"
        )
        
        # Boutons
        col_btn1, col_btn2 = st.columns([1, 4])
        
        with col_btn1:
            if st.button("💾 Enregistrer", type="primary", use_container_width=True):
                # Trouver les modifications
                modifications = 0
                erreurs = 0
                
                for idx, row in edited_df.iterrows():
                    lot_id = row['id']
                    new_prix = row['Prix (€/T)']
                    new_tare = row['Tare (%)']
                    
                    # Vérifier si valeurs renseignées
                    if pd.notna(new_prix) and pd.notna(new_tare):
                        # Vérifier si différent de l'original ou si était vide
                        orig_row = df_lots[df_lots['id'] == lot_id].iloc[0]
                        orig_prix = orig_row['prix_achat_euro_tonne']
                        orig_tare = orig_row['tare_achat_pct']
                        
                        if (pd.isna(orig_prix) or pd.isna(orig_tare) or 
                            float(new_prix) != float(orig_prix or 0) or 
                            float(new_tare) != float(orig_tare or 0)):
                            
                            if sauvegarder_qualification(lot_id, new_prix, new_tare):
                                modifications += 1
                            else:
                                erreurs += 1
                
                if modifications > 0:
                    st.success(f"✅ {modifications} lot(s) qualifié(s) avec succès !")
                    st.balloons()
                    st.session_state.pop('df_original_qualif', None)
                    st.rerun()
                elif erreurs > 0:
                    st.error(f"❌ {erreurs} erreur(s) lors de l'enregistrement")
                else:
                    st.info("ℹ️ Aucune modification détectée")
        
        with col_btn2:
            if st.button("🔄 Actualiser", use_container_width=False):
                st.session_state.pop('df_original_qualif', None)
                st.rerun()

# ============================================================
# ONGLET 2 : STATISTIQUES
# ============================================================

with tab2:
    st.subheader("📊 Statistiques de Valorisation")
    
    # Sous-onglets stats
    stat_tab1, stat_tab2, stat_tab3, stat_tab4 = st.tabs([
        "💶 Prix par Variété", 
        "🏭 Prix par Producteur",
        "📉 Tare par Variété",
        "📈 Évolution Temporelle"
    ])
    
    # --- PRIX PAR VARIÉTÉ ---
    with stat_tab1:
        st.markdown("### 💶 Prix d'achat par Variété")
        
        df_prix_var = get_stats_prix_variete()
        
        if not df_prix_var.empty:
            # Tableau
            st.dataframe(
                df_prix_var.rename(columns={
                    'variete': 'Variété',
                    'nb_lots': 'Nb Lots',
                    'prix_moyen': 'Prix Moyen (€/T)',
                    'prix_min': 'Prix Min',
                    'prix_max': 'Prix Max',
                    'tonnage_total': 'Tonnage (T)'
                }),
                use_container_width=True,
                hide_index=True
            )
            
            st.markdown("---")
            
            # Graphique barres
            st.markdown("#### 📊 Prix moyen par variété")
            df_chart = df_prix_var.head(15).sort_values('prix_moyen', ascending=True)
            st.bar_chart(df_chart.set_index('variete')['prix_moyen'], use_container_width=True)
        else:
            st.info("Aucune donnée disponible")
    
    # --- PRIX PAR PRODUCTEUR ---
    with stat_tab2:
        st.markdown("### 🏭 Prix d'achat par Producteur (Top 20)")
        
        df_prix_prod = get_stats_prix_producteur()
        
        if not df_prix_prod.empty:
            st.dataframe(
                df_prix_prod.rename(columns={
                    'producteur': 'Producteur',
                    'nb_lots': 'Nb Lots',
                    'prix_moyen': 'Prix Moyen (€/T)',
                    'prix_min': 'Prix Min',
                    'prix_max': 'Prix Max',
                    'tonnage_total': 'Tonnage (T)'
                }),
                use_container_width=True,
                hide_index=True
            )
            
            st.markdown("---")
            
            # Graphique
            st.markdown("#### 📊 Prix moyen par producteur (Top 15)")
            df_chart = df_prix_prod.head(15).sort_values('prix_moyen', ascending=True)
            st.bar_chart(df_chart.set_index('producteur')['prix_moyen'], use_container_width=True)
        else:
            st.info("Aucune donnée disponible")
    
    # --- TARE PAR VARIÉTÉ ---
    with stat_tab3:
        st.markdown("### 📉 Tare d'achat par Variété")
        
        df_tare_var = get_stats_tare_variete()
        
        if not df_tare_var.empty:
            st.dataframe(
                df_tare_var.rename(columns={
                    'variete': 'Variété',
                    'nb_lots': 'Nb Lots',
                    'tare_moyenne': 'Tare Moyenne (%)',
                    'tare_min': 'Tare Min',
                    'tare_max': 'Tare Max'
                }),
                use_container_width=True,
                hide_index=True
            )
            
            st.markdown("---")
            
            # Graphique
            st.markdown("#### 📊 Tare moyenne par variété")
            df_chart = df_tare_var.head(15).sort_values('tare_moyenne', ascending=False)
            st.bar_chart(df_chart.set_index('variete')['tare_moyenne'], use_container_width=True)
        else:
            st.info("Aucune donnée disponible")
    
    # --- ÉVOLUTION TEMPORELLE ---
    with stat_tab4:
        st.markdown("### 📈 Évolution dans le temps")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("#### Prix moyen par semaine")
            df_evol_prix = get_evolution_prix_temps()
            
            if not df_evol_prix.empty:
                st.line_chart(df_evol_prix.set_index('semaine')['prix_moyen'], use_container_width=True)
                
                # Tendance
                if len(df_evol_prix) >= 4:
                    recent = df_evol_prix['prix_moyen'].tail(4).mean()
                    ancien = df_evol_prix['prix_moyen'].head(4).mean()
                    tendance = ((recent - ancien) / ancien * 100) if ancien > 0 else 0
                    if tendance > 0:
                        st.success(f"📈 Tendance : +{tendance:.1f}% (4 dernières vs 4 premières semaines)")
                    else:
                        st.error(f"📉 Tendance : {tendance:.1f}%")
            else:
                st.info("Aucune donnée disponible")
        
        with col2:
            st.markdown("#### Tare moyenne par semaine")
            df_evol_tare = get_evolution_tare_temps()
            
            if not df_evol_tare.empty:
                st.line_chart(df_evol_tare.set_index('semaine')['tare_moyenne'], use_container_width=True)
                
                # Tendance
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
        
        # Tonnage par semaine
        st.markdown("#### 📦 Tonnage entré par semaine")
        df_evol_prix = get_evolution_prix_temps()
        if not df_evol_prix.empty and 'tonnage' in df_evol_prix.columns:
            st.bar_chart(df_evol_prix.set_index('semaine')['tonnage'], use_container_width=True)

show_footer()
