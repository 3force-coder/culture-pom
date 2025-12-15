import streamlit as st
import pandas as pd
from datetime import datetime, date
from database import get_connection
from components import show_footer
from auth import is_authenticated

st.set_page_config(page_title="Simulation - Culture Pom", page_icon="💰", layout="wide")

# CSS
st.markdown("""
<style>
    .block-container {
        padding-top: 1.5rem !important;
    }
    .profit-positive {
        color: #4caf50;
        font-weight: bold;
    }
    .profit-negative {
        color: #f44336;
        font-weight: bold;
    }
</style>
""", unsafe_allow_html=True)

if not is_authenticated():
    st.warning("⚠️ Veuillez vous connecter pour accéder à cette page")
    st.stop()

# ============================================================
# FONCTIONS
# ============================================================

def get_lots_avec_rentabilite():
    """Récupère les lots avec calcul de rentabilité"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        query = """
            SELECT 
                l.id as lot_id,
                l.code_lot_interne,
                l.nom_usage,
                l.code_variete,
                v.nom_variete,
                l.poids_total_brut_kg / 1000 as poids_brut_tonnes,
                l.prix_achat_euro_tonne,
                COALESCE(l.tare_lavage_totale_pct, v.taux_dechet_moyen * 100, 22) as tare_pct,
                -- Poids net estimé
                (l.poids_total_brut_kg / 1000) * (1 - COALESCE(l.tare_lavage_totale_pct, v.taux_dechet_moyen * 100, 22) / 100) as poids_net_tonnes,
                -- Valeur achat
                (l.poids_total_brut_kg / 1000) * COALESCE(l.prix_achat_euro_tonne, 0) as valeur_achat
            FROM lots_bruts l
            LEFT JOIN ref_varietes v ON l.code_variete = v.code_variete
            WHERE l.is_active = TRUE
              AND l.poids_total_brut_kg > 0
            ORDER BY l.code_lot_interne
        """
        
        cursor.execute(query)
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        
        if rows:
            df = pd.DataFrame(rows)
            for col in ['poids_brut_tonnes', 'prix_achat_euro_tonne', 'tare_pct', 'poids_net_tonnes', 'valeur_achat']:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
            return df
        return pd.DataFrame()
        
    except Exception as e:
        st.error(f"Erreur lots: {str(e)}")
        return pd.DataFrame()

def get_prix_vente_echeances(code_produit=None):
    """Récupère les prix de vente par échéance"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        query = """
            SELECT 
                code_produit_commercial,
                echeance,
                prix_tonne
            FROM prix_ventes_evolution
            WHERE is_active = TRUE
        """
        
        if code_produit:
            query += f" AND code_produit_commercial = '{code_produit}'"
        
        query += " ORDER BY code_produit_commercial, echeance"
        
        cursor.execute(query)
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        
        if rows:
            df = pd.DataFrame(rows)
            df['prix_tonne'] = pd.to_numeric(df['prix_tonne'], errors='coerce').fillna(0)
            return df
        return pd.DataFrame()
        
    except Exception as e:
        st.error(f"Erreur prix: {str(e)}")
        return pd.DataFrame()

def get_couts_production():
    """Récupère les coûts de production par ligne"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT code, libelle, site, cout_tonne
            FROM production_lignes
            WHERE is_active = TRUE
            ORDER BY site, code
        """)
        
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        
        if rows:
            df = pd.DataFrame(rows)
            df['cout_tonne'] = pd.to_numeric(df['cout_tonne'], errors='coerce').fillna(0)
            return df
        return pd.DataFrame()
        
    except Exception as e:
        st.error(f"Erreur coûts: {str(e)}")
        return pd.DataFrame()

def get_produits_avec_prix():
    """Récupère les produits avec prix de vente"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                code_produit,
                marque,
                type_produit,
                libelle,
                atelier,
                prix_vente_tonne,
                CONCAT(marque, ' - ', type_produit) as ligne_prevision
            FROM ref_produits_commerciaux
            WHERE is_active = TRUE
            ORDER BY marque, type_produit
        """)
        
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        
        if rows:
            df = pd.DataFrame(rows)
            df['prix_vente_tonne'] = pd.to_numeric(df['prix_vente_tonne'], errors='coerce').fillna(0)
            return df
        return pd.DataFrame()
        
    except Exception as e:
        st.error(f"Erreur produits: {str(e)}")
        return pd.DataFrame()

def calculer_rentabilite(poids_brut, prix_achat, tare_pct, prix_vente, cout_prod=0):
    """Calcule la rentabilité d'un lot"""
    poids_net = poids_brut * (1 - tare_pct / 100)
    
    # Coût total = achat + production
    cout_achat = poids_brut * prix_achat
    cout_production = poids_net * cout_prod
    cout_total = cout_achat + cout_production
    
    # Revenu = vente du poids net
    revenu = poids_net * prix_vente
    
    # Marge
    marge = revenu - cout_total
    marge_pct = (marge / cout_total * 100) if cout_total > 0 else 0
    marge_tonne = marge / poids_net if poids_net > 0 else 0
    
    return {
        'poids_brut': poids_brut,
        'poids_net': poids_net,
        'cout_achat': cout_achat,
        'cout_production': cout_production,
        'cout_total': cout_total,
        'revenu': revenu,
        'marge': marge,
        'marge_pct': marge_pct,
        'marge_tonne': marge_tonne
    }

# ============================================================
# INTERFACE
# ============================================================

st.title("💰 Simulation Rentabilité")
st.markdown("*Simuler la rentabilité des lots selon différents scénarios de prix*")
st.markdown("---")

# ============================================================
# PARAMÈTRES SIMULATION
# ============================================================

st.subheader("⚙️ Paramètres de simulation")

col_param1, col_param2, col_param3 = st.columns(3)

with col_param1:
    # Prix de vente par défaut
    prix_vente_defaut = st.number_input(
        "Prix vente par défaut (€/T)",
        min_value=0.0,
        value=250.0,
        step=10.0,
        help="Prix de vente si non défini pour le produit"
    )

with col_param2:
    # Coût production par défaut
    cout_prod_defaut = st.number_input(
        "Coût production (€/T net)",
        min_value=0.0,
        value=50.0,
        step=5.0,
        help="Coût de lavage + conditionnement"
    )

with col_param3:
    # Échéance prix
    echeance_options = ["ACTUEL", "2_SEMAINES", "1_MOIS", "3_MOIS", "6_MOIS"]
    echeance_selected = st.selectbox(
        "Échéance prix de vente",
        echeance_options,
        help="Utiliser le prix à cette échéance si disponible"
    )

st.markdown("---")

# ============================================================
# ONGLETS
# ============================================================

tab1, tab2, tab3 = st.tabs(["📊 Par Lot", "📈 Par Produit", "⚖️ Comparaison"])

# ============================================================
# TAB 1: RENTABILITÉ PAR LOT
# ============================================================

with tab1:
    st.subheader("📊 Rentabilité par Lot")
    
    lots_df = get_lots_avec_rentabilite()
    
    if not lots_df.empty:
        # Calculer rentabilité pour chaque lot
        resultats = []
        
        for _, lot in lots_df.iterrows():
            renta = calculer_rentabilite(
                float(lot['poids_brut_tonnes']),
                float(lot['prix_achat_euro_tonne'] or 0),
                float(lot['tare_pct']),
                prix_vente_defaut,
                cout_prod_defaut
            )
            
            resultats.append({
                'Code Lot': lot['code_lot_interne'],
                'Variété': lot['nom_variete'],
                'Brut (T)': lot['poids_brut_tonnes'],
                'Net (T)': renta['poids_net'],
                'Tare %': lot['tare_pct'],
                'Prix Achat €/T': lot['prix_achat_euro_tonne'],
                'Coût Total €': renta['cout_total'],
                'Revenu €': renta['revenu'],
                'Marge €': renta['marge'],
                'Marge %': renta['marge_pct'],
                'Marge €/T': renta['marge_tonne']
            })
        
        df_renta = pd.DataFrame(resultats)
        
        # KPIs globaux
        col1, col2, col3, col4 = st.columns(4)
        
        total_brut = df_renta['Brut (T)'].sum()
        total_net = df_renta['Net (T)'].sum()
        total_marge = df_renta['Marge €'].sum()
        marge_moy = df_renta['Marge %'].mean()
        
        with col1:
            st.metric("📦 Stock Total Brut", f"{total_brut:,.0f} T")
        with col2:
            st.metric("⚖️ Stock Total Net", f"{total_net:,.0f} T")
        with col3:
            color = "normal" if total_marge >= 0 else "inverse"
            st.metric("💰 Marge Totale", f"{total_marge:,.0f} €", delta_color=color)
        with col4:
            st.metric("📈 Marge Moyenne", f"{marge_moy:.1f} %")
        
        st.markdown("---")
        
        # Formater tableau
        df_display = df_renta.copy()
        df_display['Brut (T)'] = df_display['Brut (T)'].apply(lambda x: f"{x:,.1f}")
        df_display['Net (T)'] = df_display['Net (T)'].apply(lambda x: f"{x:,.1f}")
        df_display['Tare %'] = df_display['Tare %'].apply(lambda x: f"{x:.1f}%")
        df_display['Prix Achat €/T'] = df_display['Prix Achat €/T'].apply(lambda x: f"{x:,.0f}" if x > 0 else "-")
        df_display['Coût Total €'] = df_display['Coût Total €'].apply(lambda x: f"{x:,.0f}")
        df_display['Revenu €'] = df_display['Revenu €'].apply(lambda x: f"{x:,.0f}")
        df_display['Marge €'] = df_display['Marge €'].apply(lambda x: f"{x:+,.0f}")
        df_display['Marge %'] = df_display['Marge %'].apply(lambda x: f"{x:+.1f}%")
        df_display['Marge €/T'] = df_display['Marge €/T'].apply(lambda x: f"{x:+,.0f}")
        
        # Tableau
        st.dataframe(df_display, use_container_width=True, hide_index=True)
        
        # Export
        csv = df_renta.to_csv(index=False).encode('utf-8')
        st.download_button(
            "📥 Exporter CSV",
            csv,
            f"rentabilite_lots_{date.today().strftime('%Y%m%d')}.csv",
            "text/csv"
        )
        
    else:
        st.info("Aucun lot disponible pour la simulation")

# ============================================================
# TAB 2: RENTABILITÉ PAR PRODUIT
# ============================================================

with tab2:
    st.subheader("📈 Rentabilité par Produit")
    
    produits_df = get_produits_avec_prix()
    
    if not produits_df.empty:
        # Sélection produit
        lignes = produits_df['ligne_prevision'].tolist()
        selected = st.selectbox("Sélectionner un produit", lignes, key="select_produit_renta")
        
        produit = produits_df[produits_df['ligne_prevision'] == selected].iloc[0]
        
        st.markdown("---")
        
        # Infos produit
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.markdown(f"**Code**: `{produit['code_produit']}`")
            st.markdown(f"**Marque**: {produit['marque']}")
        
        with col2:
            st.markdown(f"**Type**: {produit['type_produit']}")
            st.markdown(f"**Atelier**: {produit['atelier'] or 'Non défini'}")
        
        with col3:
            prix_actuel = float(produit['prix_vente_tonne'] or 0)
            st.metric("Prix vente actuel", f"{prix_actuel:,.0f} €/T" if prix_actuel > 0 else "Non défini")
        
        st.markdown("---")
        
        # Simulation avec prix personnalisé
        st.markdown("#### Simulation")
        
        col_sim1, col_sim2 = st.columns(2)
        
        with col_sim1:
            prix_sim = st.number_input(
                "Prix de vente simulé (€/T)",
                min_value=0.0,
                value=prix_actuel if prix_actuel > 0 else prix_vente_defaut,
                step=10.0,
                key="prix_sim_produit"
            )
            
            tonnage_sim = st.number_input(
                "Tonnage net à simuler (T)",
                min_value=1.0,
                value=100.0,
                step=10.0,
                key="tonnage_sim"
            )
        
        with col_sim2:
            # Calcul avec tare moyenne 22%
            tare_moy = 22.0
            tonnage_brut = tonnage_sim / (1 - tare_moy / 100)
            
            renta = calculer_rentabilite(
                tonnage_brut,
                200.0,  # Prix achat moyen estimé
                tare_moy,
                prix_sim,
                cout_prod_defaut
            )
            
            st.metric("Tonnage brut nécessaire", f"{tonnage_brut:,.1f} T")
            st.metric("Revenu estimé", f"{renta['revenu']:,.0f} €")
            
            marge_color = "normal" if renta['marge'] >= 0 else "inverse"
            st.metric("Marge estimée", f"{renta['marge']:+,.0f} €", delta_color=marge_color)
        
        # Tableau comparaison échéances
        st.markdown("---")
        st.markdown("#### Comparaison par échéance de prix")
        
        prix_evol_df = get_prix_vente_echeances(produit['code_produit'])
        
        if not prix_evol_df.empty:
            comparaison = []
            
            for _, prix_row in prix_evol_df.iterrows():
                renta_ech = calculer_rentabilite(
                    tonnage_brut,
                    200.0,
                    tare_moy,
                    float(prix_row['prix_tonne']),
                    cout_prod_defaut
                )
                
                comparaison.append({
                    'Échéance': prix_row['echeance'],
                    'Prix €/T': float(prix_row['prix_tonne']),
                    'Revenu €': renta_ech['revenu'],
                    'Marge €': renta_ech['marge'],
                    'Marge %': renta_ech['marge_pct']
                })
            
            df_comp = pd.DataFrame(comparaison)
            
            df_comp['Prix €/T'] = df_comp['Prix €/T'].apply(lambda x: f"{x:,.0f}")
            df_comp['Revenu €'] = df_comp['Revenu €'].apply(lambda x: f"{x:,.0f}")
            df_comp['Marge €'] = df_comp['Marge €'].apply(lambda x: f"{x:+,.0f}")
            df_comp['Marge %'] = df_comp['Marge %'].apply(lambda x: f"{x:+.1f}%")
            
            st.dataframe(df_comp, use_container_width=True, hide_index=True)
        else:
            st.info("Aucune évolution de prix enregistrée pour ce produit. Utilisez la page Sources pour renseigner les prix.")
    else:
        st.info("Aucun produit disponible")

# ============================================================
# TAB 3: COMPARAISON SCÉNARIOS
# ============================================================

with tab3:
    st.subheader("⚖️ Comparaison de scénarios")
    
    st.markdown("""
    Comparez la rentabilité selon différents scénarios :
    - **Vendre maintenant** vs **Attendre 1 mois**
    - Impact d'une variation de prix
    - Seuil de rentabilité
    """)
    
    st.markdown("---")
    
    col_sc1, col_sc2 = st.columns(2)
    
    with col_sc1:
        st.markdown("#### Scénario A: Vendre maintenant")
        
        prix_a = st.number_input("Prix vente A (€/T)", value=250.0, step=10.0, key="prix_a")
        tonnage_a = st.number_input("Tonnage A (T net)", value=100.0, step=10.0, key="tonnage_a")
        
        renta_a = calculer_rentabilite(
            tonnage_a / 0.78,  # Brut estimé
            200.0,
            22.0,
            prix_a,
            cout_prod_defaut
        )
        
        st.markdown("---")
        st.metric("💰 Marge Scénario A", f"{renta_a['marge']:+,.0f} €")
        st.metric("📈 Marge % A", f"{renta_a['marge_pct']:+.1f} %")
    
    with col_sc2:
        st.markdown("#### Scénario B: Attendre")
        
        prix_b = st.number_input("Prix vente B (€/T)", value=280.0, step=10.0, key="prix_b")
        tonnage_b = st.number_input("Tonnage B (T net)", value=100.0, step=10.0, key="tonnage_b")
        
        # Ajouter coût stockage
        cout_stockage = st.number_input("Coût stockage (€/T/mois)", value=5.0, step=1.0, key="cout_stockage")
        mois_attente = st.number_input("Mois d'attente", value=1, min_value=1, max_value=6, key="mois_attente")
        
        cout_stock_total = tonnage_b * cout_stockage * mois_attente
        
        renta_b = calculer_rentabilite(
            tonnage_b / 0.78,
            200.0,
            22.0,
            prix_b,
            cout_prod_defaut + (cout_stockage * mois_attente)  # Ajouter stockage au coût
        )
        
        st.markdown("---")
        st.metric("💰 Marge Scénario B", f"{renta_b['marge']:+,.0f} €")
        st.metric("📈 Marge % B", f"{renta_b['marge_pct']:+.1f} %")
    
    # Comparaison
    st.markdown("---")
    st.markdown("#### 📊 Résultat")
    
    diff_marge = renta_b['marge'] - renta_a['marge']
    
    if diff_marge > 0:
        st.success(f"✅ **Scénario B (Attendre)** est plus rentable de **{diff_marge:+,.0f} €**")
    elif diff_marge < 0:
        st.warning(f"⚠️ **Scénario A (Vendre maintenant)** est plus rentable de **{-diff_marge:+,.0f} €**")
    else:
        st.info("🔵 Les deux scénarios sont équivalents")
    
    # Seuil de rentabilité
    st.markdown("---")
    st.markdown("#### 📉 Seuil de rentabilité")
    
    # Prix minimum pour marge = 0
    tonnage_seuil = st.number_input("Tonnage (T net)", value=100.0, step=10.0, key="tonnage_seuil")
    tonnage_brut_seuil = tonnage_seuil / 0.78
    
    cout_total_seuil = (tonnage_brut_seuil * 200) + (tonnage_seuil * cout_prod_defaut)
    prix_seuil = cout_total_seuil / tonnage_seuil if tonnage_seuil > 0 else 0
    
    st.metric("Prix de vente minimum (marge = 0)", f"{prix_seuil:,.0f} €/T")

st.markdown("---")

# ============================================================
# INFORMATIONS
# ============================================================

with st.expander("ℹ️ Formules de calcul"):
    st.markdown("""
    **Poids net** = Poids brut × (1 - Tare%)
    
    **Coût total** = (Poids brut × Prix achat) + (Poids net × Coût production)
    
    **Revenu** = Poids net × Prix vente
    
    **Marge** = Revenu - Coût total
    
    **Marge %** = (Marge / Coût total) × 100
    
    **Marge €/T** = Marge / Poids net
    
    ---
    
    **⚠️ Note**: Les prix et coûts doivent être renseignés dans:
    - `ref_produits_commerciaux.prix_vente_tonne`
    - `production_lignes.cout_tonne`
    - `prix_ventes_evolution` pour les échéances
    """)

show_footer()
