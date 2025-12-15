import streamlit as st
import pandas as pd
from datetime import datetime, date, timedelta
from database import get_connection
from components import show_footer
from auth import is_authenticated

st.set_page_config(page_title="Besoins Campagne - Culture Pom", page_icon="📊", layout="wide")

# CSS
st.markdown("""
<style>
    .block-container {
        padding-top: 1.5rem !important;
    }
    .besoin-ok {
        background-color: #e8f5e9;
        padding: 0.5rem;
        border-radius: 0.3rem;
        border-left: 4px solid #4caf50;
    }
    .besoin-warning {
        background-color: #fff3e0;
        padding: 0.5rem;
        border-radius: 0.3rem;
        border-left: 4px solid #ff9800;
    }
    .besoin-danger {
        background-color: #ffebee;
        padding: 0.5rem;
        border-radius: 0.3rem;
        border-left: 4px solid #f44336;
    }
</style>
""", unsafe_allow_html=True)

if not is_authenticated():
    st.warning("⚠️ Veuillez vous connecter pour accéder à cette page")
    st.stop()

# ============================================================
# FONCTIONS
# ============================================================

def get_besoins_par_produit(date_fin_campagne):
    """Calcule les besoins par produit jusqu'à fin de campagne"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Semaine courante
        today = date.today()
        semaine_courante = today.isocalendar()[1]
        annee_courante = today.year
        
        # Semaine fin campagne
        semaine_fin = date_fin_campagne.isocalendar()[1]
        annee_fin = date_fin_campagne.year
        
        query = """
            WITH besoins AS (
                SELECT 
                    pv.code_produit_commercial,
                    SUM(pv.quantite_prevue_tonnes) as besoin_total
                FROM previsions_ventes pv
                WHERE (pv.annee = %s AND pv.semaine >= %s)
                   OR (pv.annee > %s AND pv.annee < %s)
                   OR (pv.annee = %s AND pv.semaine <= %s)
                GROUP BY pv.code_produit_commercial
            ),
            affectations AS (
                SELECT 
                    pa.code_produit_commercial,
                    SUM(COALESCE(pa.poids_net_estime_tonnes, pa.quantite_affectee_tonnes * 0.78)) as stock_affecte
                FROM previsions_affectations pa
                WHERE pa.is_active = TRUE
                GROUP BY pa.code_produit_commercial
            ),
            conso_moyenne AS (
                SELECT 
                    pv.code_produit_commercial,
                    AVG(pv.quantite_prevue_tonnes) as conso_hebdo
                FROM previsions_ventes pv
                WHERE pv.annee = %s
                  AND pv.semaine >= %s - 5
                  AND pv.semaine <= %s
                GROUP BY pv.code_produit_commercial
            )
            SELECT 
                pc.code_produit,
                pc.marque,
                pc.type_produit,
                pc.libelle,
                pc.atelier,
                COALESCE(b.besoin_total, 0) as besoin_tonnes,
                COALESCE(a.stock_affecte, 0) as stock_affecte_tonnes,
                COALESCE(a.stock_affecte, 0) - COALESCE(b.besoin_total, 0) as difference,
                COALESCE(cm.conso_hebdo, 0) as conso_hebdo_moyenne,
                CASE 
                    WHEN COALESCE(a.stock_affecte, 0) - COALESCE(b.besoin_total, 0) >= 0 THEN 'OK'
                    WHEN COALESCE(a.stock_affecte, 0) - COALESCE(b.besoin_total, 0) > -100 THEN 'ATTENTION'
                    ELSE 'CRITIQUE'
                END as statut
            FROM ref_produits_commerciaux pc
            LEFT JOIN besoins b ON pc.code_produit = b.code_produit_commercial
            LEFT JOIN affectations a ON pc.code_produit = a.code_produit_commercial
            LEFT JOIN conso_moyenne cm ON pc.code_produit = cm.code_produit_commercial
            WHERE pc.is_active = TRUE
              AND COALESCE(b.besoin_total, 0) > 0
            ORDER BY difference ASC
        """
        
        cursor.execute(query, (
            annee_courante, semaine_courante,
            annee_courante, annee_fin,
            annee_fin, semaine_fin,
            annee_courante, semaine_courante, semaine_courante
        ))
        
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        
        if rows:
            df = pd.DataFrame(rows)
            for col in ['besoin_tonnes', 'stock_affecte_tonnes', 'difference', 'conso_hebdo_moyenne']:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
            return df
        return pd.DataFrame()
        
    except Exception as e:
        st.error(f"Erreur besoins: {str(e)}")
        return pd.DataFrame()

def get_besoins_par_semaine(code_produit, nb_semaines=12):
    """Récupère les besoins semaine par semaine pour un produit"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        today = date.today()
        semaine_courante = today.isocalendar()[1]
        annee_courante = today.year
        
        cursor.execute("""
            SELECT 
                annee,
                semaine,
                quantite_prevue_tonnes
            FROM previsions_ventes
            WHERE code_produit_commercial = %s
              AND ((annee = %s AND semaine >= %s) OR annee > %s)
            ORDER BY annee, semaine
            LIMIT %s
        """, (code_produit, annee_courante, semaine_courante, annee_courante, nb_semaines))
        
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        
        if rows:
            df = pd.DataFrame(rows)
            df['semaine_label'] = df.apply(lambda x: f"S{x['semaine']}/{x['annee']}", axis=1)
            df['quantite_prevue_tonnes'] = pd.to_numeric(df['quantite_prevue_tonnes'], errors='coerce').fillna(0)
            return df
        return pd.DataFrame()
        
    except Exception as e:
        st.error(f"Erreur semaines: {str(e)}")
        return pd.DataFrame()

def get_stock_total_disponible():
    """Récupère le stock total disponible (non affecté)"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                v.nom_variete,
                SUM(l.poids_total_brut_kg) / 1000 as poids_brut_tonnes,
                SUM(l.poids_total_brut_kg * (1 - COALESCE(l.tare_lavage_totale_pct, v.taux_dechet_moyen * 100, 22) / 100)) / 1000 as poids_net_tonnes,
                SUM(COALESCE((
                    SELECT SUM(pa.quantite_affectee_tonnes)
                    FROM previsions_affectations pa
                    WHERE pa.lot_id = l.id AND pa.is_active = TRUE
                ), 0)) as deja_affecte
            FROM lots_bruts l
            LEFT JOIN ref_varietes v ON l.code_variete = v.code_variete
            WHERE l.is_active = TRUE
            GROUP BY v.nom_variete
            HAVING SUM(l.poids_total_brut_kg) > 0
            ORDER BY poids_brut_tonnes DESC
        """)
        
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        
        if rows:
            df = pd.DataFrame(rows)
            for col in ['poids_brut_tonnes', 'poids_net_tonnes', 'deja_affecte']:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
            df['disponible_tonnes'] = df['poids_brut_tonnes'] - df['deja_affecte']
            return df
        return pd.DataFrame()
        
    except Exception as e:
        st.error(f"Erreur stock: {str(e)}")
        return pd.DataFrame()

def create_tache(titre, description):
    """Crée une tâche"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        created_by = st.session_state.get('username', 'system')
        
        cursor.execute("""
            INSERT INTO taches (titre, description, statut, created_by, created_at)
            VALUES (%s, %s, 'A_FAIRE', %s, CURRENT_TIMESTAMP)
            RETURNING id
        """, (titre, description, created_by))
        
        tache_id = cursor.fetchone()['id']
        conn.commit()
        cursor.close()
        conn.close()
        
        return True, f"✅ Tâche #{tache_id} créée"
        
    except Exception as e:
        if 'conn' in locals():
            conn.rollback()
        return False, f"❌ Erreur: {str(e)}"

# ============================================================
# INTERFACE
# ============================================================

st.title("📊 Besoins Campagne")
st.markdown("*Calcul des besoins par produit jusqu'à fin de campagne*")

# Paramètres campagne
col_param1, col_param2 = st.columns([2, 1])

with col_param1:
    # Calculer la date fin campagne par défaut (30 juin de l'année en cours ou suivante)
    today = date.today()
    if today.month <= 6:
        # Avant juillet -> fin campagne = 30 juin de cette année
        default_fin = date(today.year, 6, 30)
    else:
        # Après juin -> fin campagne = 30 juin de l'année prochaine
        default_fin = date(today.year + 1, 6, 30)
    
    # S'assurer que la date par défaut est dans le futur
    if default_fin <= today:
        default_fin = date(today.year + 1, 6, 30)
    
    date_fin_campagne = st.date_input(
        "📅 Date fin de campagne",
        value=default_fin,
        min_value=today,
        max_value=date(2026, 6, 30)
    )

with col_param2:
    # Calculer semaines restantes
    today = date.today()
    semaines_restantes = max(0, (date_fin_campagne - today).days // 7)
    st.metric("Semaines restantes", semaines_restantes)

st.markdown("---")

# ============================================================
# KPIs GLOBAUX
# ============================================================

besoins_df = get_besoins_par_produit(date_fin_campagne)
stock_df = get_stock_total_disponible()

if not besoins_df.empty:
    col1, col2, col3, col4, col5 = st.columns(5)
    
    besoin_total = besoins_df['besoin_tonnes'].sum()
    stock_affecte = besoins_df['stock_affecte_tonnes'].sum()
    difference = stock_affecte - besoin_total
    
    nb_ok = len(besoins_df[besoins_df['statut'] == 'OK'])
    nb_attention = len(besoins_df[besoins_df['statut'] == 'ATTENTION'])
    nb_critique = len(besoins_df[besoins_df['statut'] == 'CRITIQUE'])
    
    with col1:
        st.metric("🎯 Besoin Total", f"{besoin_total:,.0f} T")
    
    with col2:
        st.metric("📦 Stock Affecté", f"{stock_affecte:,.0f} T")
    
    with col3:
        delta_color = "normal" if difference >= 0 else "inverse"
        st.metric("📈 Différence", f"{difference:+,.0f} T", delta_color=delta_color)
    
    with col4:
        if not stock_df.empty:
            stock_dispo = stock_df['disponible_tonnes'].sum()
            st.metric("📋 Stock Non Affecté", f"{stock_dispo:,.0f} T")
    
    with col5:
        st.metric("📊 Produits", f"{len(besoins_df)}")
    
    # Résumé statuts
    col_s1, col_s2, col_s3 = st.columns(3)
    
    with col_s1:
        st.markdown(f"""
        <div class="besoin-ok">
            <strong>✅ OK</strong>: {nb_ok} produits
        </div>
        """, unsafe_allow_html=True)
    
    with col_s2:
        st.markdown(f"""
        <div class="besoin-warning">
            <strong>⚠️ ATTENTION</strong>: {nb_attention} produits
        </div>
        """, unsafe_allow_html=True)
    
    with col_s3:
        st.markdown(f"""
        <div class="besoin-danger">
            <strong>🔴 CRITIQUE</strong>: {nb_critique} produits
        </div>
        """, unsafe_allow_html=True)

st.markdown("---")

# ============================================================
# ONGLETS
# ============================================================

tab1, tab2, tab3 = st.tabs(["📋 Par Produit", "📅 Par Semaine", "📦 Stock Disponible"])

# ============================================================
# TAB 1: BESOINS PAR PRODUIT
# ============================================================

with tab1:
    st.subheader("📋 Besoins par Produit")
    
    if not besoins_df.empty:
        # Filtres
        col_f1, col_f2 = st.columns(2)
        
        with col_f1:
            statut_filter = st.multiselect(
                "Filtrer par statut",
                ["OK", "ATTENTION", "CRITIQUE"],
                default=["CRITIQUE", "ATTENTION"],
                key="filter_statut"
            )
        
        with col_f2:
            marques = ["Toutes"] + sorted(besoins_df['marque'].dropna().unique().tolist())
            marque_filter = st.selectbox("Filtrer par marque", marques, key="filter_marque_besoin")
        
        # Appliquer filtres
        df_filtered = besoins_df.copy()
        
        if statut_filter:
            df_filtered = df_filtered[df_filtered['statut'].isin(statut_filter)]
        
        if marque_filter != "Toutes":
            df_filtered = df_filtered[df_filtered['marque'] == marque_filter]
        
        if not df_filtered.empty:
            # Préparer affichage
            df_display = df_filtered[[
                'marque', 'type_produit', 'besoin_tonnes', 'stock_affecte_tonnes',
                'difference', 'conso_hebdo_moyenne', 'statut'
            ]].copy()
            
            df_display.columns = [
                'Marque', 'Type Produit', 'Besoin (T)', 'Stock Affecté (T)',
                'Différence (T)', 'Conso Hebdo (T)', 'Statut'
            ]
            
            # Formater
            df_display['Besoin (T)'] = df_display['Besoin (T)'].apply(lambda x: f"{x:,.0f}")
            df_display['Stock Affecté (T)'] = df_display['Stock Affecté (T)'].apply(lambda x: f"{x:,.0f}")
            df_display['Différence (T)'] = df_display['Différence (T)'].apply(lambda x: f"{x:+,.0f}")
            df_display['Conso Hebdo (T)'] = df_display['Conso Hebdo (T)'].apply(lambda x: f"{x:.1f}")
            
            # Tableau avec sélection
            event = st.dataframe(
                df_display,
                use_container_width=True,
                hide_index=True,
                on_select="rerun",
                selection_mode="multi-row",
                key="besoins_table"
            )
            
            # Actions sur sélection
            selected_rows = event.selection.rows if hasattr(event, 'selection') else []
            
            if len(selected_rows) > 0:
                st.markdown("---")
                
                # Bouton créer tâche
                if st.button("📝 Créer tâche d'achat", type="primary", use_container_width=True):
                    for idx in selected_rows:
                        row = df_filtered.iloc[idx]
                        if row['difference'] < 0:
                            titre = f"ACHETER - {row['marque']} {row['type_produit']}"
                            desc = f"Manque estimé: {abs(row['difference']):,.0f} T jusqu'au {date_fin_campagne.strftime('%d/%m/%Y')}"
                            success, msg = create_tache(titre, desc)
                            if success:
                                st.success(msg)
                            else:
                                st.error(msg)
                    st.rerun()
            
            # Export
            csv = df_filtered.to_csv(index=False).encode('utf-8')
            st.download_button(
                "📥 Exporter CSV",
                csv,
                f"besoins_campagne_{date.today().strftime('%Y%m%d')}.csv",
                "text/csv"
            )
        else:
            st.info("Aucun produit correspondant aux filtres")
    else:
        st.info("Aucune prévision de vente disponible")

# ============================================================
# TAB 2: BESOINS PAR SEMAINE
# ============================================================

with tab2:
    st.subheader("📅 Prévisions par Semaine")
    
    if not besoins_df.empty:
        # Sélection produit
        produits_list = besoins_df.apply(lambda x: f"{x['marque']} - {x['type_produit']}", axis=1).tolist()
        selected_produit = st.selectbox("Sélectionner un produit", produits_list, key="select_produit_semaine")
        
        # Récupérer code produit
        idx = produits_list.index(selected_produit)
        code_produit = besoins_df.iloc[idx]['code_produit']
        
        # Charger données semaine
        semaines_df = get_besoins_par_semaine(code_produit, nb_semaines=16)
        
        if not semaines_df.empty:
            # Graphique
            st.markdown("#### 📈 Évolution des besoins")
            
            st.bar_chart(
                semaines_df.set_index('semaine_label')['quantite_prevue_tonnes'],
                use_container_width=True
            )
            
            # Tableau détaillé
            st.markdown("#### 📋 Détail par semaine")
            
            df_sem_display = semaines_df[['semaine_label', 'quantite_prevue_tonnes']].copy()
            df_sem_display.columns = ['Semaine', 'Quantité (T)']
            df_sem_display['Quantité (T)'] = df_sem_display['Quantité (T)'].apply(lambda x: f"{x:.1f}")
            
            st.dataframe(df_sem_display, use_container_width=True, hide_index=True)
            
            # Totaux
            total_sem = semaines_df['quantite_prevue_tonnes'].sum()
            moy_sem = semaines_df['quantite_prevue_tonnes'].mean()
            
            col1, col2 = st.columns(2)
            with col1:
                st.metric("Total sur la période", f"{total_sem:,.1f} T")
            with col2:
                st.metric("Moyenne hebdomadaire", f"{moy_sem:.1f} T/sem")
        else:
            st.info("Aucune prévision disponible pour ce produit")
    else:
        st.info("Aucune donnée disponible")

# ============================================================
# TAB 3: STOCK DISPONIBLE
# ============================================================

with tab3:
    st.subheader("📦 Stock Disponible par Variété")
    
    if not stock_df.empty:
        # KPIs stock
        col1, col2, col3 = st.columns(3)
        
        total_brut = stock_df['poids_brut_tonnes'].sum()
        total_dispo = stock_df['disponible_tonnes'].sum()
        total_affecte = stock_df['deja_affecte'].sum()
        
        with col1:
            st.metric("📦 Stock Brut Total", f"{total_brut:,.0f} T")
        with col2:
            st.metric("✅ Déjà Affecté", f"{total_affecte:,.0f} T")
        with col3:
            st.metric("📋 Disponible", f"{total_dispo:,.0f} T")
        
        st.markdown("---")
        
        # Tableau par variété
        df_stock_display = stock_df[[
            'nom_variete', 'poids_brut_tonnes', 'deja_affecte', 'disponible_tonnes'
        ]].copy()
        
        df_stock_display.columns = ['Variété', 'Stock Brut (T)', 'Affecté (T)', 'Disponible (T)']
        
        df_stock_display['Stock Brut (T)'] = df_stock_display['Stock Brut (T)'].apply(lambda x: f"{x:,.0f}")
        df_stock_display['Affecté (T)'] = df_stock_display['Affecté (T)'].apply(lambda x: f"{x:,.0f}")
        df_stock_display['Disponible (T)'] = df_stock_display['Disponible (T)'].apply(lambda x: f"{x:,.0f}")
        
        st.dataframe(df_stock_display, use_container_width=True, hide_index=True)
        
        # Graphique
        st.markdown("---")
        st.markdown("#### 📊 Répartition par variété")
        
        chart_data = stock_df[['nom_variete', 'disponible_tonnes']].copy()
        chart_data = chart_data[chart_data['disponible_tonnes'] > 0]
        chart_data = chart_data.set_index('nom_variete')
        
        if not chart_data.empty:
            st.bar_chart(chart_data['disponible_tonnes'], use_container_width=True)
    else:
        st.info("Aucun stock disponible")

st.markdown("---")

# ============================================================
# AIDE
# ============================================================

with st.expander("ℹ️ Aide et explications"):
    st.markdown(f"""
    ### Calcul des besoins
    
    **Période analysée**: De aujourd'hui ({date.today().strftime('%d/%m/%Y')}) jusqu'au {date_fin_campagne.strftime('%d/%m/%Y')}
    
    **Besoin** = Somme des prévisions de ventes sur la période
    
    **Stock affecté** = Somme des affectations actives (poids net estimé)
    
    **Différence** = Stock affecté - Besoin
    - ✅ **OK** : Différence ≥ 0 (stock suffisant)
    - ⚠️ **ATTENTION** : -100 T < Différence < 0 (manque léger)
    - 🔴 **CRITIQUE** : Différence ≤ -100 T (manque important)
    
    ### Actions
    
    - **Créer tâche d'achat** : Génère une tâche pour les produits sélectionnés en manque
    - **Exporter CSV** : Télécharge les données pour analyse externe
    
    ### Données nécessaires
    
    - Table `previsions_ventes` : Prévisions hebdomadaires par produit
    - Table `previsions_affectations` : Affectations lots → produits
    - Table `lots_bruts` : Stock de lots disponibles
    """)

show_footer()
