"""
33_Prev_Simulation.py - Simulation Rentabilité par Produit
==========================================================
Outil de pilotage financier :
- Marge par produit avec échéances de prix
- Simulation achat du manque
- Paramétrage prix/coûts/tares
"""

import streamlit as st
import pandas as pd
from datetime import datetime, date, timedelta
from database import get_connection
from components import show_footer
from auth import is_authenticated

st.set_page_config(page_title="Simulation Rentabilité - Culture Pom", page_icon="💰", layout="wide")

# CSS
st.markdown("""
<style>
    .block-container {
        padding-top: 1.5rem !important;
    }
    .profit-card {
        background: linear-gradient(135deg, #e8f5e9 0%, #c8e6c9 100%);
        padding: 1rem;
        border-radius: 0.5rem;
        border-left: 4px solid #4caf50;
        margin: 0.5rem 0;
    }
    .loss-card {
        background: linear-gradient(135deg, #ffebee 0%, #ffcdd2 100%);
        padding: 1rem;
        border-radius: 0.5rem;
        border-left: 4px solid #f44336;
        margin: 0.5rem 0;
    }
    .neutral-card {
        background: linear-gradient(135deg, #f5f5f5 0%, #eeeeee 100%);
        padding: 1rem;
        border-radius: 0.5rem;
        border-left: 4px solid #9e9e9e;
        margin: 0.5rem 0;
    }
</style>
""", unsafe_allow_html=True)

if not is_authenticated():
    st.warning("⚠️ Veuillez vous connecter pour accéder à cette page")
    st.stop()

# Date fin campagne
DATE_FIN_CAMPAGNE = date(2026, 6, 30)

# ============================================================
# FONCTIONS DONNÉES
# ============================================================

@st.cache_data(ttl=60)
def get_couts_production():
    """Récupère les coûts de production par type d'atelier"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT DISTINCT type_atelier, cout_tonne
            FROM production_lignes
            WHERE is_active = TRUE AND cout_tonne IS NOT NULL
            ORDER BY type_atelier
        """)
        
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        
        # Retourner dict {type_atelier: cout}
        if rows:
            return {row['type_atelier']: float(row['cout_tonne'] or 0) for row in rows}
        return {}
        
    except Exception as e:
        st.error(f"Erreur coûts production: {str(e)}")
        return {}

@st.cache_data(ttl=30)
def get_prix_ventes_previsions():
    """Récupère les prix de vente par produit et échéance"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                code_produit_commercial,
                prix_actuel,
                prix_2_semaines,
                prix_1_mois,
                prix_3_mois,
                prix_6_mois,
                date_maj
            FROM prix_ventes_previsions
        """)
        
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        
        if rows:
            df = pd.DataFrame(rows)
            for col in ['prix_actuel', 'prix_2_semaines', 'prix_1_mois', 'prix_3_mois', 'prix_6_mois']:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
            return df
        return pd.DataFrame()
        
    except Exception as e:
        # Table peut ne pas exister encore
        return pd.DataFrame()

@st.cache_data(ttl=30)
def get_produits_avec_affectations():
    """Récupère les produits avec leurs affectations et calculs de marge"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Semaines restantes jusqu'à fin campagne
        today = date.today()
        nb_semaines = max(0, (DATE_FIN_CAMPAGNE - today).days / 7.0)
        semaine_courante = today.isocalendar()[1]
        annee_courante = today.year
        
        cursor.execute("""
            WITH conso_hebdo AS (
                SELECT 
                    code_produit_commercial,
                    AVG(quantite_prevue_tonnes) as conso_hebdo
                FROM (
                    SELECT 
                        code_produit_commercial,
                        quantite_prevue_tonnes,
                        ROW_NUMBER() OVER (PARTITION BY code_produit_commercial ORDER BY annee, semaine) as rn
                    FROM previsions_ventes
                    WHERE (annee = %s AND semaine >= %s) OR annee > %s
                ) sub
                WHERE rn <= 5
                GROUP BY code_produit_commercial
            ),
            affectations_detail AS (
                SELECT 
                    pa.code_produit_commercial,
                    COUNT(*) as nb_lots,
                    SUM(pa.quantite_affectee_tonnes) as total_brut,
                    SUM(pa.poids_net_estime_tonnes) as total_net,
                    -- Prix achat moyen pondéré
                    SUM(pa.quantite_affectee_tonnes * COALESCE(l.prix_achat_euro_tonne, 0)) / 
                        NULLIF(SUM(pa.quantite_affectee_tonnes), 0) as prix_achat_moyen,
                    -- Tare moyenne pondérée (réelle > théorique > 22%)
                    SUM(pa.quantite_affectee_tonnes * 
                        COALESCE(l.tare_lavage_totale_pct, l.tare_theorique_pct, 22)
                    ) / NULLIF(SUM(pa.quantite_affectee_tonnes), 0) as tare_moyenne
                FROM previsions_affectations pa
                JOIN lots_bruts l ON pa.lot_id = l.id
                WHERE pa.is_active = TRUE
                GROUP BY pa.code_produit_commercial
            )
            SELECT 
                pc.code_produit,
                pc.marque,
                pc.libelle,
                pc.type_produit,
                pc.atelier,
                COALESCE(ch.conso_hebdo, 0) as conso_hebdo,
                COALESCE(ch.conso_hebdo, 0) * %s as besoin_campagne,
                COALESCE(ad.nb_lots, 0) as nb_lots,
                COALESCE(ad.total_brut, 0) as total_brut,
                COALESCE(ad.total_net, 0) as total_net,
                COALESCE(ad.prix_achat_moyen, 0) as prix_achat_moyen,
                COALESCE(ad.tare_moyenne, 22) as tare_moyenne,
                COALESCE(ad.total_net, 0) - (COALESCE(ch.conso_hebdo, 0) * %s) as solde
            FROM ref_produits_commerciaux pc
            LEFT JOIN conso_hebdo ch ON pc.code_produit = ch.code_produit_commercial
            LEFT JOIN affectations_detail ad ON pc.code_produit = ad.code_produit_commercial
            WHERE pc.is_active = TRUE
              AND (ch.conso_hebdo > 0 OR ad.total_net > 0)
            ORDER BY pc.marque, pc.libelle
        """, (annee_courante, semaine_courante, annee_courante, nb_semaines, nb_semaines))
        
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        
        if rows:
            df = pd.DataFrame(rows)
            numeric_cols = ['conso_hebdo', 'besoin_campagne', 'nb_lots', 'total_brut', 
                           'total_net', 'prix_achat_moyen', 'tare_moyenne', 'solde']
            for col in numeric_cols:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
            return df
        return pd.DataFrame()
        
    except Exception as e:
        st.error(f"Erreur produits: {str(e)}")
        return pd.DataFrame()

def get_lots_pour_tare():
    """Récupère les lots pour modification de tare théorique"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                l.id,
                l.code_lot_interne,
                l.nom_usage,
                v.nom_variete,
                l.poids_total_brut_kg / 1000 as poids_brut_tonnes,
                l.tare_lavage_totale_pct as tare_reelle,
                l.tare_theorique_pct as tare_theorique,
                CASE 
                    WHEN l.tare_lavage_totale_pct IS NOT NULL THEN 'RÉELLE'
                    WHEN l.tare_theorique_pct IS NOT NULL THEN 'THÉORIQUE'
                    ELSE 'DÉFAUT (22%)'
                END as source_tare,
                COALESCE(l.tare_lavage_totale_pct, l.tare_theorique_pct, 22) as tare_utilisee
            FROM lots_bruts l
            LEFT JOIN ref_varietes v ON l.code_variete = v.code_variete
            WHERE l.is_active = TRUE
              AND l.poids_total_brut_kg > 0
              AND l.tare_lavage_totale_pct IS NULL
            ORDER BY l.code_lot_interne
        """)
        
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        
        if rows:
            df = pd.DataFrame(rows)
            for col in ['poids_brut_tonnes', 'tare_reelle', 'tare_theorique', 'tare_utilisee']:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
            return df
        return pd.DataFrame()
        
    except Exception as e:
        st.error(f"Erreur lots: {str(e)}")
        return pd.DataFrame()

def update_tare_theorique(lot_id, tare_pct):
    """Met à jour la tare théorique d'un lot"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE lots_bruts 
            SET tare_theorique_pct = %s, updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
        """, (float(tare_pct) if tare_pct else None, int(lot_id)))
        
        conn.commit()
        cursor.close()
        conn.close()
        return True
    except Exception as e:
        st.error(f"Erreur: {str(e)}")
        return False

def save_prix_previsions(code_produit, prix_actuel, prix_2sem, prix_1mois, prix_3mois, prix_6mois):
    """Sauvegarde ou met à jour les prix prévisionnels d'un produit"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        created_by = st.session_state.get('username', 'system')
        
        # UPSERT
        cursor.execute("""
            INSERT INTO prix_ventes_previsions 
                (code_produit_commercial, prix_actuel, prix_2_semaines, prix_1_mois, 
                 prix_3_mois, prix_6_mois, date_maj, created_by, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, CURRENT_DATE, %s, CURRENT_TIMESTAMP)
            ON CONFLICT (code_produit_commercial) 
            DO UPDATE SET 
                prix_actuel = EXCLUDED.prix_actuel,
                prix_2_semaines = EXCLUDED.prix_2_semaines,
                prix_1_mois = EXCLUDED.prix_1_mois,
                prix_3_mois = EXCLUDED.prix_3_mois,
                prix_6_mois = EXCLUDED.prix_6_mois,
                date_maj = CURRENT_DATE,
                updated_at = CURRENT_TIMESTAMP
        """, (code_produit, prix_actuel, prix_2sem, prix_1mois, prix_3mois, prix_6mois, created_by))
        
        conn.commit()
        cursor.close()
        conn.close()
        return True
    except Exception as e:
        st.error(f"Erreur: {str(e)}")
        return False

def update_cout_production(type_atelier, cout_tonne):
    """Met à jour le coût de production d'un atelier"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE production_lignes 
            SET cout_tonne = %s, updated_at = CURRENT_TIMESTAMP
            WHERE type_atelier = %s
        """, (float(cout_tonne), type_atelier))
        
        conn.commit()
        cursor.close()
        conn.close()
        return True
    except Exception as e:
        st.error(f"Erreur: {str(e)}")
        return False

def calculer_marge(poids_net, prix_achat_brut, tare_pct, cout_prod, prix_vente):
    """Calcule la marge pour un volume donné"""
    if poids_net <= 0:
        return {'marge_tonne': 0, 'marge_totale': 0, 'marge_pct': 0, 'cout_revient': 0}
    
    # Coût matière ramené au net
    cout_matiere_net = prix_achat_brut / (1 - tare_pct / 100) if tare_pct < 100 else prix_achat_brut
    
    # Coût de revient total par tonne net
    cout_revient = cout_matiere_net + cout_prod
    
    # Marge
    marge_tonne = prix_vente - cout_revient
    marge_totale = marge_tonne * poids_net
    marge_pct = (marge_tonne / cout_revient * 100) if cout_revient > 0 else 0
    
    return {
        'cout_matiere_net': cout_matiere_net,
        'cout_prod': cout_prod,
        'cout_revient': cout_revient,
        'marge_tonne': marge_tonne,
        'marge_totale': marge_totale,
        'marge_pct': marge_pct
    }

# ============================================================
# INTERFACE
# ============================================================

st.title("💰 Simulation Rentabilité")
st.caption(f"Pilotage financier par produit • Fin campagne: {DATE_FIN_CAMPAGNE.strftime('%d/%m/%Y')}")
st.markdown("---")

# Charger données
couts_prod = get_couts_production()
prix_previsions = get_prix_ventes_previsions()

tab1, tab2, tab3 = st.tabs(["📊 Marge par Produit", "💵 Simulation Manque", "⚙️ Paramétrage"])

# ============================================================
# TAB 1: MARGE PAR PRODUIT
# ============================================================

with tab1:
    st.subheader("📊 Rentabilité par Produit")
    
    produits_df = get_produits_avec_affectations()
    
    if not produits_df.empty:
        # Filtre produit
        produits_list = [f"{row['marque']} - {row['type_produit']}" for _, row in produits_df.iterrows()]
        selected_produit = st.selectbox("Sélectionner un produit", produits_list)
        
        if selected_produit:
            idx = produits_list.index(selected_produit)
            produit = produits_df.iloc[idx]
            
            st.markdown("---")
            
            # KPIs
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.metric("📦 Besoin campagne", f"{produit['besoin_campagne']:,.0f} T")
            
            with col2:
                st.metric("📋 Stock affecté", f"{produit['total_net']:,.0f} T", 
                         f"{int(produit['nb_lots'])} lots")
            
            with col3:
                solde = produit['solde']
                delta_color = "normal" if solde >= 0 else "inverse"
                st.metric("⚖️ Solde", f"{solde:+,.0f} T", 
                         "SURPLUS" if solde > 0 else ("MANQUE" if solde < 0 else "ÉQUILIBRE"),
                         delta_color=delta_color)
            
            with col4:
                st.metric("📊 Tare moyenne", f"{produit['tare_moyenne']:.1f} %")
            
            st.markdown("---")
            
            # Détails coûts
            col_cout1, col_cout2 = st.columns(2)
            
            with col_cout1:
                st.markdown("#### 💳 Structure de coûts")
                
                prix_achat = float(produit['prix_achat_moyen'])
                tare = float(produit['tare_moyenne'])
                atelier = produit['atelier'] or 'SBU'
                cout_prod = couts_prod.get(atelier, 45.0)
                
                # Coût matière ramené au net
                cout_matiere_net = prix_achat / (1 - tare / 100) if tare < 100 else prix_achat
                cout_revient = cout_matiere_net + cout_prod
                
                st.markdown(f"""
                | Élément | Valeur |
                |---------|--------|
                | Prix achat moyen (brut) | **{prix_achat:,.0f} €/T** |
                | Tare moyenne | **{tare:.1f} %** |
                | → Coût matière (net) | **{cout_matiere_net:,.0f} €/T** |
                | Coût production ({atelier}) | **{cout_prod:,.0f} €/T** |
                | **COÛT DE REVIENT** | **{cout_revient:,.0f} €/T** |
                """)
            
            with col_cout2:
                st.markdown("#### 📈 Prix de vente")
                
                # Récupérer prix du produit
                code_produit = produit['code_produit']
                prix_produit = prix_previsions[prix_previsions['code_produit_commercial'] == code_produit] if not prix_previsions.empty else pd.DataFrame()
                
                if not prix_produit.empty:
                    prix_row = prix_produit.iloc[0]
                    st.markdown(f"""
                    | Échéance | Prix €/T |
                    |----------|----------|
                    | Actuel | **{prix_row['prix_actuel']:,.0f}** |
                    | +2 semaines | {prix_row['prix_2_semaines']:,.0f} |
                    | +1 mois | {prix_row['prix_1_mois']:,.0f} |
                    | +3 mois | {prix_row['prix_3_mois']:,.0f} |
                    | +6 mois | {prix_row['prix_6_mois']:,.0f} |
                    """)
                else:
                    st.warning("⚠️ Prix non renseignés. Allez dans l'onglet Paramétrage.")
            
            st.markdown("---")
            
            # Tableau des marges par échéance
            st.markdown("#### 💰 Marge par échéance de prix")
            
            poids_net = float(produit['total_net'])
            
            if poids_net > 0 and not prix_produit.empty:
                prix_row = prix_produit.iloc[0]
                
                echeances = [
                    ('Actuel', float(prix_row['prix_actuel'])),
                    ('+2 semaines', float(prix_row['prix_2_semaines'])),
                    ('+1 mois', float(prix_row['prix_1_mois'])),
                    ('+3 mois', float(prix_row['prix_3_mois'])),
                    ('+6 mois', float(prix_row['prix_6_mois']))
                ]
                
                marge_data = []
                for echeance, prix_vente in echeances:
                    if prix_vente > 0:
                        marge = calculer_marge(poids_net, prix_achat, tare, cout_prod, prix_vente)
                        marge_data.append({
                            'Échéance': echeance,
                            'Prix vente €/T': prix_vente,
                            'Marge €/T': marge['marge_tonne'],
                            'Marge totale €': marge['marge_totale'],
                            'Marge %': marge['marge_pct']
                        })
                
                if marge_data:
                    df_marge = pd.DataFrame(marge_data)
                    
                    # Formater pour affichage
                    df_display = df_marge.copy()
                    df_display['Prix vente €/T'] = df_display['Prix vente €/T'].apply(lambda x: f"{x:,.0f}")
                    df_display['Marge €/T'] = df_display['Marge €/T'].apply(lambda x: f"{x:+,.0f}")
                    df_display['Marge totale €'] = df_display['Marge totale €'].apply(lambda x: f"{x:+,.0f}")
                    df_display['Marge %'] = df_display['Marge %'].apply(lambda x: f"{x:+.1f}%")
                    
                    st.dataframe(df_display, use_container_width=True, hide_index=True)
                    
                    # Graphique simple
                    st.markdown("##### 📊 Évolution de la marge")
                    chart_data = df_marge[['Échéance', 'Marge totale €']].set_index('Échéance')
                    st.bar_chart(chart_data)
                else:
                    st.info("Renseignez les prix de vente dans l'onglet Paramétrage")
            else:
                if poids_net <= 0:
                    st.info("Aucun stock affecté à ce produit")
                else:
                    st.info("Renseignez les prix de vente dans l'onglet Paramétrage")
    else:
        st.info("Aucun produit avec affectations ou prévisions")

# ============================================================
# TAB 2: SIMULATION MANQUE
# ============================================================

with tab2:
    st.subheader("💵 Simulation : Acheter le Manque")
    st.markdown("*Comparer l'impact financier d'acheter maintenant vs attendre*")
    
    produits_df = get_produits_avec_affectations()
    
    if not produits_df.empty:
        # Filtrer produits en manque
        produits_manque = produits_df[produits_df['solde'] < 0].copy()
        
        if not produits_manque.empty:
            # Sélection produit
            produits_list = [f"{row['marque']} - {row['type_produit']} ({row['solde']:+,.0f} T)" 
                            for _, row in produits_manque.iterrows()]
            selected = st.selectbox("Produit en manque", produits_list, key="select_manque")
            
            idx = produits_list.index(selected)
            produit = produits_manque.iloc[idx]
            manque = abs(float(produit['solde']))
            
            st.markdown("---")
            
            # Infos produit
            col_info1, col_info2, col_info3 = st.columns(3)
            
            with col_info1:
                st.metric("📦 Manque à couvrir", f"{manque:,.0f} T net")
            
            with col_info2:
                atelier = produit['atelier'] or 'SBU'
                cout_prod = couts_prod.get(atelier, 45.0)
                st.metric("🏭 Coût production", f"{cout_prod:,.0f} €/T")
            
            with col_info3:
                code_produit = produit['code_produit']
                prix_produit = prix_previsions[prix_previsions['code_produit_commercial'] == code_produit] if not prix_previsions.empty else pd.DataFrame()
                prix_actuel = float(prix_produit.iloc[0]['prix_actuel']) if not prix_produit.empty else 0
                st.metric("💰 Prix vente actuel", f"{prix_actuel:,.0f} €/T")
            
            st.markdown("---")
            
            # Paramètres simulation
            st.markdown("#### ⚙️ Paramètres de simulation")
            
            col_param1, col_param2 = st.columns(2)
            
            with col_param1:
                st.markdown("##### 🅰️ Scénario A : Acheter MAINTENANT")
                
                prix_achat_a = st.number_input(
                    "Prix achat estimé (€/T brut)",
                    min_value=0.0,
                    value=200.0,
                    step=10.0,
                    key="prix_achat_a"
                )
                
                tare_a = st.number_input(
                    "Tare estimée (%)",
                    min_value=0.0,
                    max_value=50.0,
                    value=22.0,
                    step=1.0,
                    key="tare_a"
                )
            
            with col_param2:
                st.markdown("##### 🅱️ Scénario B : ATTENDRE")
                
                delai_mois = st.selectbox(
                    "Délai d'attente",
                    options=[1, 2, 3, 6],
                    format_func=lambda x: f"{x} mois",
                    key="delai_mois"
                )
                
                prix_achat_b = st.number_input(
                    f"Prix achat estimé dans {delai_mois} mois (€/T brut)",
                    min_value=0.0,
                    value=180.0,
                    step=10.0,
                    key="prix_achat_b"
                )
                
                cout_stockage = st.number_input(
                    "Coût stockage (€/T/mois)",
                    min_value=0.0,
                    value=5.0,
                    step=1.0,
                    key="cout_stockage"
                )
            
            st.markdown("---")
            
            # Calculs et résultats
            if prix_actuel > 0:
                st.markdown("#### 📊 Résultats de la simulation")
                
                col_res1, col_res2 = st.columns(2)
                
                # Scénario A : Acheter maintenant
                with col_res1:
                    poids_brut_a = manque / (1 - tare_a / 100) if tare_a < 100 else manque
                    cout_achat_a = poids_brut_a * prix_achat_a
                    cout_prod_a = manque * cout_prod
                    cout_total_a = cout_achat_a + cout_prod_a
                    revenu_a = manque * prix_actuel
                    marge_a = revenu_a - cout_total_a
                    marge_pct_a = (marge_a / cout_total_a * 100) if cout_total_a > 0 else 0
                    
                    card_class = "profit-card" if marge_a >= 0 else "loss-card"
                    
                    st.markdown(f"""
                    <div class="{card_class}">
                        <h4>🅰️ Acheter MAINTENANT</h4>
                        <table style="width:100%">
                            <tr><td>Tonnage brut</td><td style="text-align:right"><b>{poids_brut_a:,.0f} T</b></td></tr>
                            <tr><td>Coût achat</td><td style="text-align:right">{cout_achat_a:,.0f} €</td></tr>
                            <tr><td>Coût production</td><td style="text-align:right">{cout_prod_a:,.0f} €</td></tr>
                            <tr><td><b>Coût total</b></td><td style="text-align:right"><b>{cout_total_a:,.0f} €</b></td></tr>
                            <tr><td>Revenu (prix actuel)</td><td style="text-align:right">{revenu_a:,.0f} €</td></tr>
                            <tr><td colspan="2"><hr></td></tr>
                            <tr><td><b>MARGE</b></td><td style="text-align:right"><b>{marge_a:+,.0f} € ({marge_pct_a:+.1f}%)</b></td></tr>
                        </table>
                    </div>
                    """, unsafe_allow_html=True)
                
                # Scénario B : Attendre
                with col_res2:
                    # Prix de vente selon délai
                    if not prix_produit.empty:
                        if delai_mois == 1:
                            prix_vente_b = float(prix_produit.iloc[0]['prix_1_mois'])
                        elif delai_mois == 3:
                            prix_vente_b = float(prix_produit.iloc[0]['prix_3_mois'])
                        elif delai_mois == 6:
                            prix_vente_b = float(prix_produit.iloc[0]['prix_6_mois'])
                        else:
                            prix_vente_b = prix_actuel
                    else:
                        prix_vente_b = prix_actuel
                    
                    if prix_vente_b <= 0:
                        prix_vente_b = prix_actuel
                    
                    poids_brut_b = manque / (1 - tare_a / 100) if tare_a < 100 else manque
                    cout_achat_b = poids_brut_b * prix_achat_b
                    cout_prod_b = manque * cout_prod
                    cout_stock_b = manque * cout_stockage * delai_mois
                    cout_total_b = cout_achat_b + cout_prod_b + cout_stock_b
                    revenu_b = manque * prix_vente_b
                    marge_b = revenu_b - cout_total_b
                    marge_pct_b = (marge_b / cout_total_b * 100) if cout_total_b > 0 else 0
                    
                    card_class = "profit-card" if marge_b >= 0 else "loss-card"
                    
                    st.markdown(f"""
                    <div class="{card_class}">
                        <h4>🅱️ Attendre {delai_mois} mois</h4>
                        <table style="width:100%">
                            <tr><td>Tonnage brut</td><td style="text-align:right"><b>{poids_brut_b:,.0f} T</b></td></tr>
                            <tr><td>Coût achat</td><td style="text-align:right">{cout_achat_b:,.0f} €</td></tr>
                            <tr><td>Coût production</td><td style="text-align:right">{cout_prod_b:,.0f} €</td></tr>
                            <tr><td>Coût stockage ({delai_mois} mois)</td><td style="text-align:right">{cout_stock_b:,.0f} €</td></tr>
                            <tr><td><b>Coût total</b></td><td style="text-align:right"><b>{cout_total_b:,.0f} €</b></td></tr>
                            <tr><td>Revenu (prix +{delai_mois}m: {prix_vente_b:,.0f}€)</td><td style="text-align:right">{revenu_b:,.0f} €</td></tr>
                            <tr><td colspan="2"><hr></td></tr>
                            <tr><td><b>MARGE</b></td><td style="text-align:right"><b>{marge_b:+,.0f} € ({marge_pct_b:+.1f}%)</b></td></tr>
                        </table>
                    </div>
                    """, unsafe_allow_html=True)
                
                # Recommandation
                st.markdown("---")
                diff = marge_a - marge_b
                
                if diff > 0:
                    st.success(f"✅ **RECOMMANDATION : Acheter MAINTENANT** (+{diff:,.0f} € par rapport à attendre)")
                elif diff < 0:
                    st.warning(f"⏳ **RECOMMANDATION : ATTENDRE {delai_mois} mois** (+{-diff:,.0f} € par rapport à maintenant)")
                else:
                    st.info("🔵 Les deux scénarios sont équivalents")
            else:
                st.warning("⚠️ Renseignez les prix de vente dans l'onglet Paramétrage")
        else:
            st.success("✅ Aucun produit en manque ! Tous les besoins sont couverts.")
    else:
        st.info("Aucun produit avec affectations")

# ============================================================
# TAB 3: PARAMÉTRAGE
# ============================================================

with tab3:
    st.subheader("⚙️ Paramétrage")
    
    subtab1, subtab2, subtab3 = st.tabs(["💰 Prix de Vente", "🏭 Coûts Production", "📊 Tare Lots"])
    
    # ----------------------------------------------------------
    # SUBTAB 1: Prix de vente
    # ----------------------------------------------------------
    with subtab1:
        st.markdown("#### 💰 Prix de Vente par Produit")
        st.caption("Renseignez les prix actuels et prévisionnels par échéance")
        
        # Liste produits
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT code_produit, marque, type_produit, libelle
            FROM ref_produits_commerciaux
            WHERE is_active = TRUE
            ORDER BY marque, type_produit
        """)
        produits = cursor.fetchall()
        cursor.close()
        conn.close()
        
        if produits:
            produits_options = [f"{p['marque']} - {p['type_produit']}" for p in produits]
            selected_prod = st.selectbox("Produit", produits_options, key="prix_produit")
            
            idx = produits_options.index(selected_prod)
            code_produit = produits[idx]['code_produit']
            
            # Charger prix existants
            prix_existants = prix_previsions[prix_previsions['code_produit_commercial'] == code_produit] if not prix_previsions.empty else pd.DataFrame()
            
            col1, col2 = st.columns(2)
            
            with col1:
                default_actuel = float(prix_existants.iloc[0]['prix_actuel']) if not prix_existants.empty else 0.0
                prix_actuel = st.number_input("Prix ACTUEL (€/T)", value=default_actuel, step=10.0, key="p_actuel")
                
                default_2sem = float(prix_existants.iloc[0]['prix_2_semaines']) if not prix_existants.empty else 0.0
                prix_2sem = st.number_input("Prix +2 SEMAINES (€/T)", value=default_2sem, step=10.0, key="p_2sem")
                
                default_1mois = float(prix_existants.iloc[0]['prix_1_mois']) if not prix_existants.empty else 0.0
                prix_1mois = st.number_input("Prix +1 MOIS (€/T)", value=default_1mois, step=10.0, key="p_1mois")
            
            with col2:
                default_3mois = float(prix_existants.iloc[0]['prix_3_mois']) if not prix_existants.empty else 0.0
                prix_3mois = st.number_input("Prix +3 MOIS (€/T)", value=default_3mois, step=10.0, key="p_3mois")
                
                default_6mois = float(prix_existants.iloc[0]['prix_6_mois']) if not prix_existants.empty else 0.0
                prix_6mois = st.number_input("Prix +6 MOIS (€/T)", value=default_6mois, step=10.0, key="p_6mois")
                
                if not prix_existants.empty:
                    st.caption(f"Dernière MAJ: {prix_existants.iloc[0]['date_maj']}")
            
            if st.button("💾 Enregistrer les prix", type="primary", key="save_prix"):
                if save_prix_previsions(code_produit, prix_actuel, prix_2sem, prix_1mois, prix_3mois, prix_6mois):
                    st.success("✅ Prix enregistrés !")
                    get_prix_ventes_previsions.clear()
                    st.rerun()
    
    # ----------------------------------------------------------
    # SUBTAB 2: Coûts production
    # ----------------------------------------------------------
    with subtab2:
        st.markdown("#### 🏭 Coûts de Production par Atelier")
        st.caption("Coût de transformation (lavage + conditionnement) par tonne nette")
        
        # Charger lignes production
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT DISTINCT type_atelier, cout_tonne
            FROM production_lignes
            WHERE is_active = TRUE
            ORDER BY type_atelier
        """)
        lignes = cursor.fetchall()
        cursor.close()
        conn.close()
        
        if lignes:
            for ligne in lignes:
                col1, col2, col3 = st.columns([2, 2, 1])
                
                with col1:
                    st.markdown(f"**{ligne['type_atelier']}**")
                
                with col2:
                    new_cout = st.number_input(
                        "Coût €/T",
                        value=float(ligne['cout_tonne'] or 0),
                        step=5.0,
                        key=f"cout_{ligne['type_atelier']}",
                        label_visibility="collapsed"
                    )
                
                with col3:
                    if st.button("💾", key=f"save_cout_{ligne['type_atelier']}"):
                        if update_cout_production(ligne['type_atelier'], new_cout):
                            st.success("✅")
                            get_couts_production.clear()
                            st.rerun()
        else:
            st.info("Aucune ligne de production configurée")
    
    # ----------------------------------------------------------
    # SUBTAB 3: Tare lots
    # ----------------------------------------------------------
    with subtab3:
        st.markdown("#### 📊 Tare Théorique par Lot")
        st.caption("Modifier la tare estimée pour les lots non lavés (ex: 10% pour brossé)")
        
        lots_df = get_lots_pour_tare()
        
        if not lots_df.empty:
            st.info(f"📋 {len(lots_df)} lot(s) non lavés disponibles")
            
            # Filtre rapide
            col_filter1, col_filter2 = st.columns(2)
            
            with col_filter1:
                varietes_list = sorted(lots_df['nom_variete'].dropna().unique().tolist())
                filter_variete = st.multiselect(
                    "Filtrer par variété",
                    options=varietes_list,
                    key="filter_var_tare"
                )
            
            with col_filter2:
                filter_tare = st.selectbox(
                    "Filtrer par tare",
                    options=["Tous", "Tare par défaut (22%)", "Tare personnalisée"],
                    key="filter_tare_type"
                )
            
            # Appliquer filtres
            df_filtered = lots_df.copy()
            
            if filter_variete:
                df_filtered = df_filtered[df_filtered['nom_variete'].isin(filter_variete)]
            
            if filter_tare == "Tare par défaut (22%)":
                df_filtered = df_filtered[df_filtered['tare_theorique'].isna()]
            elif filter_tare == "Tare personnalisée":
                df_filtered = df_filtered[df_filtered['tare_theorique'].notna()]
            
            st.markdown("---")
            
            if not df_filtered.empty:
                # Limiter affichage
                max_display = 20
                df_to_show = df_filtered.head(max_display)
                
                if len(df_filtered) > max_display:
                    st.warning(f"Affichage limité aux {max_display} premiers lots. Utilisez les filtres.")
                
                # Édition inline
                for _, lot in df_to_show.iterrows():
                    col1, col2, col3, col4 = st.columns([3, 2, 2, 1])
                    
                    with col1:
                        st.markdown(f"**{lot['code_lot_interne']}**")
                        st.caption(f"{lot['nom_variete']} • {lot['poids_brut_tonnes']:.0f} T")
                    
                    with col2:
                        st.markdown(f"Tare actuelle: **{lot['tare_utilisee']:.0f}%**")
                        st.caption(lot['source_tare'])
                    
                    with col3:
                        default_tare = float(lot['tare_theorique']) if pd.notna(lot['tare_theorique']) else 22.0
                        new_tare = st.number_input(
                            "Nouvelle tare %",
                            min_value=0.0,
                            max_value=50.0,
                            value=default_tare,
                            step=1.0,
                            key=f"tare_{lot['id']}",
                            label_visibility="collapsed"
                        )
                    
                    with col4:
                        if st.button("💾", key=f"save_tare_{lot['id']}"):
                            # NULL si 22% (revenir au défaut)
                            tare_to_save = new_tare if new_tare != 22.0 else None
                            if update_tare_theorique(lot['id'], tare_to_save):
                                st.success("✅")
                                st.rerun()
                    
                    st.markdown("---")
                
                # Action groupée
                st.markdown("#### ⚡ Action rapide")
                
                col_action1, col_action2 = st.columns(2)
                
                with col_action1:
                    tare_groupe = st.number_input(
                        "Tare à appliquer (%)",
                        min_value=0.0,
                        max_value=50.0,
                        value=10.0,
                        step=1.0,
                        key="tare_groupe"
                    )
                
                with col_action2:
                    if st.button(f"🎯 Appliquer {tare_groupe:.0f}% aux {len(df_filtered)} lots filtrés", 
                                type="secondary"):
                        success_count = 0
                        for _, lot in df_filtered.iterrows():
                            tare_to_save = tare_groupe if tare_groupe != 22.0 else None
                            if update_tare_theorique(lot['id'], tare_to_save):
                                success_count += 1
                        
                        st.success(f"✅ {success_count} lot(s) mis à jour !")
                        st.rerun()
            else:
                st.info("Aucun lot ne correspond aux filtres")
        else:
            st.info("Aucun lot non lavé disponible")

st.markdown("---")
show_footer()
