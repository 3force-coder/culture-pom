"""
33_Prev_Simulation.py - Simulation Rentabilité par Produit
==========================================================
v5 - Radio buttons (évite reset tabs)
   - Évolution chronologique de la marge par lot
   - Suppression coût stockage
   - Prix vente min pour 10%
"""

import streamlit as st
import pandas as pd
from datetime import datetime, date, timedelta
from database import get_connection
from components import show_footer
from auth import is_authenticated

st.set_page_config(page_title="Simulation Rentabilité - Culture Pom", page_icon="💰", layout="wide")

st.markdown("""
<style>
    .block-container { padding-top: 1.5rem !important; }
    .profit-card {
        background: linear-gradient(135deg, #e8f5e9 0%, #c8e6c9 100%);
        padding: 1rem; border-radius: 0.5rem; border-left: 4px solid #4caf50; margin: 0.5rem 0;
    }
    .loss-card {
        background: linear-gradient(135deg, #ffebee 0%, #ffcdd2 100%);
        padding: 1rem; border-radius: 0.5rem; border-left: 4px solid #f44336; margin: 0.5rem 0;
    }
    .neutral-card {
        background: linear-gradient(135deg, #f5f5f5 0%, #eeeeee 100%);
        padding: 1rem; border-radius: 0.5rem; border-left: 4px solid #9e9e9e; margin: 0.5rem 0;
    }
    .info-card {
        background: linear-gradient(135deg, #e3f2fd 0%, #bbdefb 100%);
        padding: 1rem; border-radius: 0.5rem; border-left: 4px solid #2196f3; margin: 0.5rem 0;
    }
</style>
""", unsafe_allow_html=True)

if not is_authenticated():
    st.warning("⚠️ Veuillez vous connecter")
    st.stop()

DATE_FIN_CAMPAGNE = date(2026, 6, 30)

# ============================================================
# FONCTIONS DONNÉES
# ============================================================

@st.cache_data(ttl=60)
def get_couts_production():
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT DISTINCT type_atelier, cout_tonne
            FROM production_lignes
            WHERE is_active = TRUE AND cout_tonne IS NOT NULL
        """)
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        return {row['type_atelier']: float(row['cout_tonne'] or 0) for row in rows} if rows else {}
    except:
        return {}

@st.cache_data(ttl=30)
def get_prix_ventes_previsions():
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'prix_ventes_previsions')")
        if not cursor.fetchone()['exists']:
            cursor.close()
            conn.close()
            return pd.DataFrame()
        
        cursor.execute("""
            SELECT code_produit_commercial, prix_actuel, prix_2_semaines, 
                   prix_1_mois, prix_3_mois, prix_6_mois, date_maj
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
    except:
        return pd.DataFrame()

@st.cache_data(ttl=30)
def get_produits_avec_affectations():
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        today = date.today()
        nb_semaines = max(0, (DATE_FIN_CAMPAGNE - today).days / 7.0)
        semaine_courante = today.isocalendar()[1]
        annee_courante = today.year
        
        cursor.execute("SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'previsions_affectations')")
        if not cursor.fetchone()['exists']:
            cursor.close()
            conn.close()
            return pd.DataFrame()
        
        cursor.execute("SELECT EXISTS (SELECT FROM information_schema.columns WHERE table_name = 'lots_bruts' AND column_name = 'tare_theorique_pct')")
        tare_col = cursor.fetchone()['exists']
        tare_expr = "COALESCE(l.tare_lavage_totale_pct, l.tare_theorique_pct, 22)" if tare_col else "COALESCE(l.tare_lavage_totale_pct, 22)"
        
        query = f"""
            WITH conso_hebdo AS (
                SELECT code_produit_commercial, AVG(quantite_prevue_tonnes) as conso_hebdo
                FROM (
                    SELECT code_produit_commercial, quantite_prevue_tonnes,
                           ROW_NUMBER() OVER (PARTITION BY code_produit_commercial ORDER BY annee, semaine) as rn
                    FROM previsions_ventes
                    WHERE (annee = %s AND semaine >= %s) OR annee > %s
                ) sub WHERE rn <= 5
                GROUP BY code_produit_commercial
            ),
            affectations_detail AS (
                SELECT pa.code_produit_commercial, COUNT(*) as nb_lots,
                       SUM(pa.quantite_affectee_tonnes) as total_brut,
                       SUM(pa.poids_net_estime_tonnes) as total_net,
                       SUM(pa.quantite_affectee_tonnes * COALESCE(l.prix_achat_euro_tonne, 0)) / 
                           NULLIF(SUM(pa.quantite_affectee_tonnes), 0) as prix_achat_moyen,
                       SUM(pa.quantite_affectee_tonnes * {tare_expr}) / 
                           NULLIF(SUM(pa.quantite_affectee_tonnes), 0) as tare_moyenne
                FROM previsions_affectations pa
                JOIN lots_bruts l ON pa.lot_id = l.id
                WHERE pa.is_active = TRUE
                GROUP BY pa.code_produit_commercial
            )
            SELECT pc.code_produit, pc.marque, pc.libelle, pc.type_produit, pc.atelier,
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
            WHERE pc.is_active = TRUE AND (ch.conso_hebdo > 0 OR ad.total_net > 0)
            ORDER BY pc.marque, pc.libelle
        """
        
        cursor.execute(query, (annee_courante, semaine_courante, annee_courante, nb_semaines, nb_semaines))
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        
        if rows:
            df = pd.DataFrame(rows)
            for col in ['conso_hebdo', 'besoin_campagne', 'nb_lots', 'total_brut', 'total_net', 'prix_achat_moyen', 'tare_moyenne', 'solde']:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
            return df
        return pd.DataFrame()
    except Exception as e:
        st.error(f"Erreur: {str(e)}")
        return pd.DataFrame()

@st.cache_data(ttl=30)
def get_lots_affectes_chronologique(code_produit):
    """Récupère les lots affectés ordonnés par date de passage"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT EXISTS (SELECT FROM information_schema.columns WHERE table_name = 'lots_bruts' AND column_name = 'tare_theorique_pct')")
        tare_col = cursor.fetchone()['exists']
        tare_expr = "COALESCE(l.tare_lavage_totale_pct, l.tare_theorique_pct, 22)" if tare_col else "COALESCE(l.tare_lavage_totale_pct, 22)"
        
        query = f"""
            SELECT pa.id as affectation_id, pa.lot_id, l.code_lot_interne, v.nom_variete,
                   pa.quantite_affectee_tonnes as poids_brut,
                   pa.poids_net_estime_tonnes as poids_net,
                   COALESCE(l.prix_achat_euro_tonne, 0) as prix_achat,
                   {tare_expr} as tare_pct,
                   l.date_entree_stock, pa.date_passage_prevue
            FROM previsions_affectations pa
            JOIN lots_bruts l ON pa.lot_id = l.id
            LEFT JOIN ref_varietes v ON l.code_variete = v.code_variete
            WHERE pa.code_produit_commercial = %s AND pa.is_active = TRUE
            ORDER BY pa.date_passage_prevue NULLS LAST, l.date_entree_stock, l.prix_achat_euro_tonne ASC
        """
        
        cursor.execute(query, (code_produit,))
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        
        if rows:
            df = pd.DataFrame(rows)
            for col in ['poids_brut', 'poids_net', 'prix_achat', 'tare_pct']:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
            return df
        return pd.DataFrame()
    except Exception as e:
        st.error(f"Erreur: {str(e)}")
        return pd.DataFrame()

def get_lots_pour_tare():
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT EXISTS (SELECT FROM information_schema.columns WHERE table_name = 'lots_bruts' AND column_name = 'tare_theorique_pct')")
        col_exists = cursor.fetchone()['exists']
        
        if col_exists:
            query = """
                SELECT l.id, l.code_lot_interne, l.nom_usage, v.nom_variete,
                       l.poids_total_brut_kg / 1000 as poids_brut_tonnes,
                       l.tare_theorique_pct as tare_theorique,
                       COALESCE(l.tare_lavage_totale_pct, l.tare_theorique_pct, 22) as tare_utilisee,
                       CASE WHEN l.tare_theorique_pct IS NOT NULL THEN 'THÉORIQUE' ELSE 'DÉFAUT (22%)' END as source_tare
                FROM lots_bruts l
                LEFT JOIN ref_varietes v ON l.code_variete = v.code_variete
                WHERE l.is_active = TRUE AND l.poids_total_brut_kg > 0 AND l.tare_lavage_totale_pct IS NULL
                ORDER BY l.code_lot_interne
            """
        else:
            query = """
                SELECT l.id, l.code_lot_interne, l.nom_usage, v.nom_variete,
                       l.poids_total_brut_kg / 1000 as poids_brut_tonnes,
                       NULL::numeric as tare_theorique,
                       COALESCE(l.tare_lavage_totale_pct, 22) as tare_utilisee,
                       'DÉFAUT (22%)' as source_tare
                FROM lots_bruts l
                LEFT JOIN ref_varietes v ON l.code_variete = v.code_variete
                WHERE l.is_active = TRUE AND l.poids_total_brut_kg > 0 AND l.tare_lavage_totale_pct IS NULL
                ORDER BY l.code_lot_interne
            """
        
        cursor.execute(query)
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        
        if rows:
            df = pd.DataFrame(rows)
            for col in ['poids_brut_tonnes', 'tare_theorique', 'tare_utilisee']:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
            return df
        return pd.DataFrame()
    except:
        return pd.DataFrame()

def update_tare_theorique(lot_id, tare_pct):
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT EXISTS (SELECT FROM information_schema.columns WHERE table_name = 'lots_bruts' AND column_name = 'tare_theorique_pct')")
        if not cursor.fetchone()['exists']:
            cursor.close()
            conn.close()
            return False
        
        cursor.execute("UPDATE lots_bruts SET tare_theorique_pct = %s, updated_at = CURRENT_TIMESTAMP WHERE id = %s",
                      (float(tare_pct) if tare_pct else None, int(lot_id)))
        conn.commit()
        cursor.close()
        conn.close()
        return True
    except:
        return False

def save_prix_previsions(code_produit, prix_actuel, prix_2sem, prix_1mois, prix_3mois, prix_6mois):
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'prix_ventes_previsions')")
        if not cursor.fetchone()['exists']:
            cursor.close()
            conn.close()
            return False
        
        created_by = st.session_state.get('username', 'system')
        cursor.execute("""
            INSERT INTO prix_ventes_previsions 
                (code_produit_commercial, prix_actuel, prix_2_semaines, prix_1_mois, prix_3_mois, prix_6_mois, date_maj, created_by, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, CURRENT_DATE, %s, CURRENT_TIMESTAMP)
            ON CONFLICT (code_produit_commercial) DO UPDATE SET 
                prix_actuel = EXCLUDED.prix_actuel, prix_2_semaines = EXCLUDED.prix_2_semaines,
                prix_1_mois = EXCLUDED.prix_1_mois, prix_3_mois = EXCLUDED.prix_3_mois,
                prix_6_mois = EXCLUDED.prix_6_mois, date_maj = CURRENT_DATE, updated_at = CURRENT_TIMESTAMP
        """, (code_produit, prix_actuel, prix_2sem, prix_1mois, prix_3mois, prix_6mois, created_by))
        
        conn.commit()
        cursor.close()
        conn.close()
        return True
    except:
        return False

def update_cout_production(type_atelier, cout_tonne):
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE production_lignes SET cout_tonne = %s, updated_at = CURRENT_TIMESTAMP WHERE type_atelier = %s",
                      (float(cout_tonne), type_atelier))
        conn.commit()
        cursor.close()
        conn.close()
        return True
    except:
        return False

def calculer_marge(poids_net, prix_achat_brut, tare_pct, cout_prod, prix_vente):
    if poids_net <= 0 or prix_vente <= 0:
        return {'marge_tonne': 0, 'marge_totale': 0, 'marge_pct': 0, 'cout_revient': 0, 'cout_matiere_net': 0}
    
    cout_matiere_net = prix_achat_brut / (1 - tare_pct / 100) if tare_pct < 100 else prix_achat_brut
    cout_revient = cout_matiere_net + cout_prod
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

def get_prix_vente_pour_date(prix_row, date_passage, date_ref=None):
    """Retourne le prix de vente estimé selon la date de passage"""
    if date_ref is None:
        date_ref = date.today()
    
    if date_passage is None:
        return float(prix_row['prix_actuel']), "Actuel"
    
    if isinstance(date_passage, str):
        date_passage = datetime.strptime(date_passage, '%Y-%m-%d').date()
    
    delta_jours = (date_passage - date_ref).days
    
    if delta_jours <= 0:
        return float(prix_row['prix_actuel']), "Actuel"
    elif delta_jours <= 14:
        return float(prix_row['prix_2_semaines']) or float(prix_row['prix_actuel']), "+2 sem"
    elif delta_jours <= 45:
        return float(prix_row['prix_1_mois']) or float(prix_row['prix_actuel']), "+1 mois"
    elif delta_jours <= 120:
        return float(prix_row['prix_3_mois']) or float(prix_row['prix_actuel']), "+3 mois"
    else:
        return float(prix_row['prix_6_mois']) or float(prix_row['prix_actuel']), "+6 mois"

def calculer_prix_vente_cible(prix_achat_brut, tare_pct, cout_prod, marge_cible_pct=10):
    cout_matiere_net = prix_achat_brut / (1 - tare_pct / 100) if tare_pct < 100 else prix_achat_brut
    cout_revient = cout_matiere_net + cout_prod
    prix_vente_cible = cout_revient * (1 + marge_cible_pct / 100)
    return prix_vente_cible, cout_revient

# ============================================================
# INTERFACE
# ============================================================

st.title("💰 Simulation Rentabilité")
st.caption(f"Pilotage financier • Fin campagne: {DATE_FIN_CAMPAGNE.strftime('%d/%m/%Y')}")
st.markdown("---")

couts_prod = get_couts_production()
prix_previsions = get_prix_ventes_previsions()

# Navigation RADIO (évite reset des tabs)
onglet = st.radio(
    "Navigation",
    options=["📊 Marge par Produit", "📈 Évolution Chronologique", "💵 Simulation Achat", "⚙️ Paramétrage"],
    horizontal=True,
    label_visibility="collapsed"
)

st.markdown("---")

# ============================================================
# ONGLET 1: MARGE PAR PRODUIT
# ============================================================

if onglet == "📊 Marge par Produit":
    st.subheader("📊 Rentabilité par Produit")
    
    produits_df = get_produits_avec_affectations()
    
    if not produits_df.empty:
        produits_list = [f"{row['marque']} - {row['type_produit']}" for _, row in produits_df.iterrows()]
        selected_produit = st.selectbox("Sélectionner un produit", produits_list, key="marge_produit")
        
        if selected_produit:
            idx = produits_list.index(selected_produit)
            produit = produits_df.iloc[idx]
            
            st.markdown("---")
            
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("📦 Besoin campagne", f"{produit['besoin_campagne']:,.0f} T")
            with col2:
                st.metric("📋 Stock affecté", f"{produit['total_net']:,.0f} T", f"{int(produit['nb_lots'])} lots")
            with col3:
                solde = produit['solde']
                st.metric("⚖️ Solde", f"{solde:+,.0f} T", 
                         "SURPLUS" if solde > 0 else ("MANQUE" if solde < 0 else "OK"),
                         delta_color="normal" if solde >= 0 else "inverse")
            with col4:
                st.metric("📊 Tare moyenne", f"{produit['tare_moyenne']:.1f} %")
            
            st.markdown("---")
            
            col_cout1, col_cout2 = st.columns(2)
            
            with col_cout1:
                st.markdown("#### 💳 Structure de coûts")
                prix_achat = float(produit['prix_achat_moyen'])
                tare = float(produit['tare_moyenne'])
                atelier = produit['atelier'] or 'SBU'
                cout_prod = couts_prod.get(atelier, 45.0)
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
                code_produit = produit['code_produit']
                prix_produit = prix_previsions[prix_previsions['code_produit_commercial'] == code_produit] if not prix_previsions.empty else pd.DataFrame()
                
                if not prix_produit.empty:
                    px = prix_produit.iloc[0]
                    st.markdown(f"""
                    | Échéance | Prix €/T |
                    |----------|----------|
                    | Actuel | **{px['prix_actuel']:,.0f}** |
                    | +2 semaines | {px['prix_2_semaines']:,.0f} |
                    | +1 mois | {px['prix_1_mois']:,.0f} |
                    | +3 mois | {px['prix_3_mois']:,.0f} |
                    | +6 mois | {px['prix_6_mois']:,.0f} |
                    """)
                else:
                    st.warning("⚠️ Prix non renseignés")
            
            st.markdown("---")
            st.markdown("#### 💰 Marge par échéance")
            
            poids_net = float(produit['total_net'])
            
            if poids_net > 0 and not prix_produit.empty:
                px = prix_produit.iloc[0]
                echeances = [
                    ('Actuel', float(px['prix_actuel'])),
                    ('+2 semaines', float(px['prix_2_semaines'])),
                    ('+1 mois', float(px['prix_1_mois'])),
                    ('+3 mois', float(px['prix_3_mois'])),
                    ('+6 mois', float(px['prix_6_mois']))
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
                    df_display = df_marge.copy()
                    df_display['Prix vente €/T'] = df_display['Prix vente €/T'].apply(lambda x: f"{x:,.0f}")
                    df_display['Marge €/T'] = df_display['Marge €/T'].apply(lambda x: f"{x:+,.0f}")
                    df_display['Marge totale €'] = df_display['Marge totale €'].apply(lambda x: f"{x:+,.0f}")
                    df_display['Marge %'] = df_display['Marge %'].apply(lambda x: f"{x:+.1f}%")
                    st.dataframe(df_display, use_container_width=True, hide_index=True)
                    
                    st.markdown("##### 📊 Évolution de la marge")
                    chart_data = df_marge[['Échéance', 'Marge totale €']].set_index('Échéance')
                    st.bar_chart(chart_data)
    else:
        st.info("Aucun produit avec affectations")

# ============================================================
# ONGLET 2: ÉVOLUTION CHRONOLOGIQUE
# ============================================================

elif onglet == "📈 Évolution Chronologique":
    st.subheader("📈 Évolution de la Marge dans le Temps")
    st.markdown("*Marge mois par mois selon l'ordre de passage des lots*")
    
    produits_df = get_produits_avec_affectations()
    
    if not produits_df.empty:
        produits_list = [f"{row['marque']} - {row['type_produit']}" for _, row in produits_df.iterrows()]
        selected_produit = st.selectbox("Sélectionner un produit", produits_list, key="chrono_produit")
        
        if selected_produit:
            idx = produits_list.index(selected_produit)
            produit = produits_df.iloc[idx]
            code_produit = produit['code_produit']
            
            prix_produit = prix_previsions[prix_previsions['code_produit_commercial'] == code_produit] if not prix_previsions.empty else pd.DataFrame()
            lots_df = get_lots_affectes_chronologique(code_produit)
            
            atelier = produit['atelier'] or 'SBU'
            cout_prod = couts_prod.get(atelier, 45.0)
            
            st.markdown("---")
            
            if not lots_df.empty and not prix_produit.empty:
                prix_row = prix_produit.iloc[0]
                
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("📦 Lots à passer", len(lots_df))
                with col2:
                    st.metric("🏭 Coût production", f"{cout_prod:,.0f} €/T")
                with col3:
                    st.metric("💰 Prix actuel", f"{float(prix_row['prix_actuel']):,.0f} €/T")
                
                st.markdown("---")
                st.markdown("#### 📅 Évolution chronologique de la marge")
                
                chrono_data = []
                marge_cumulee = 0
                poids_cumule = 0
                cout_cumule = 0
                
                for i, (_, lot) in enumerate(lots_df.iterrows()):
                    prix_achat = float(lot['prix_achat'])
                    tare = float(lot['tare_pct'])
                    poids_net = float(lot['poids_net'])
                    date_passage = lot['date_passage_prevue']
                    
                    prix_vente, echeance_label = get_prix_vente_pour_date(prix_row, date_passage)
                    marge = calculer_marge(poids_net, prix_achat, tare, cout_prod, prix_vente)
                    
                    marge_cumulee += marge['marge_totale']
                    poids_cumule += poids_net
                    cout_cumule += marge['cout_revient'] * poids_net
                    marge_cumulee_pct = (marge_cumulee / cout_cumule * 100) if cout_cumule > 0 else 0
                    
                    if date_passage:
                        if isinstance(date_passage, str):
                            date_passage = datetime.strptime(date_passage, '%Y-%m-%d').date()
                        mois_label = date_passage.strftime('%b %Y')
                    else:
                        mois_label = "Non planifié"
                    
                    chrono_data.append({
                        'Ordre': i + 1,
                        'Mois': mois_label,
                        'Lot': lot['code_lot_interne'],
                        'Variété': lot['nom_variete'] or '-',
                        'Poids net (T)': poids_net,
                        'Prix achat €/T': prix_achat,
                        'Prix vente €/T': prix_vente,
                        'Échéance prix': echeance_label,
                        'Marge lot %': marge['marge_pct'],
                        'Marge lot €': marge['marge_totale'],
                        'Marge cumulée €': marge_cumulee,
                        'Marge cumulée %': marge_cumulee_pct
                    })
                
                df_chrono = pd.DataFrame(chrono_data)
                
                # Graphique
                st.markdown("##### 📊 Évolution de la marge cumulée")
                chart_data = df_chrono[['Ordre', 'Marge cumulée %']].copy()
                chart_data = chart_data.rename(columns={'Marge cumulée %': 'Marge %'})
                chart_data = chart_data.set_index('Ordre')
                st.line_chart(chart_data)
                st.caption("🎯 Objectif : maintenir la marge au-dessus de 10%")
                
                st.markdown("---")
                
                # Tableau
                st.markdown("##### 📋 Détail par lot (ordre chronologique)")
                df_display = df_chrono.copy()
                df_display['Poids net (T)'] = df_display['Poids net (T)'].apply(lambda x: f"{x:,.1f}")
                df_display['Prix achat €/T'] = df_display['Prix achat €/T'].apply(lambda x: f"{x:,.0f}")
                df_display['Prix vente €/T'] = df_display['Prix vente €/T'].apply(lambda x: f"{x:,.0f}")
                df_display['Marge lot %'] = df_display['Marge lot %'].apply(lambda x: f"{x:+.1f}%")
                df_display['Marge lot €'] = df_display['Marge lot €'].apply(lambda x: f"{x:+,.0f}")
                df_display['Marge cumulée €'] = df_display['Marge cumulée €'].apply(lambda x: f"{x:+,.0f}")
                df_display['Marge cumulée %'] = df_display['Marge cumulée %'].apply(lambda x: f"{x:+.1f}%")
                st.dataframe(df_display, use_container_width=True, hide_index=True)
                
                st.markdown("---")
                
                # Résumé
                st.markdown("#### 📊 Résumé")
                col_res1, col_res2, col_res3 = st.columns(3)
                
                marge_finale_pct = df_chrono.iloc[-1]['Marge cumulée %'] if not df_chrono.empty else 0
                marge_finale_eur = df_chrono.iloc[-1]['Marge cumulée €'] if not df_chrono.empty else 0
                
                with col_res1:
                    card_class = "profit-card" if marge_finale_pct >= 10 else ("loss-card" if marge_finale_pct < 0 else "neutral-card")
                    st.markdown(f"""
                    <div class="{card_class}">
                        <h4>Marge finale</h4>
                        <h2>{marge_finale_pct:+.1f}%</h2>
                        <p>{marge_finale_eur:+,.0f} €</p>
                    </div>
                    """, unsafe_allow_html=True)
                
                with col_res2:
                    lots_negatifs = df_chrono[df_chrono['Marge lot %'] < 0]
                    nb_negatifs = len(lots_negatifs)
                    if nb_negatifs > 0:
                        st.markdown(f"""
                        <div class="loss-card">
                            <h4>⚠️ Lots à marge négative</h4>
                            <h2>{nb_negatifs}</h2>
                            <p>Font baisser la rentabilité</p>
                        </div>
                        """, unsafe_allow_html=True)
                    else:
                        st.markdown(f"""
                        <div class="profit-card">
                            <h4>✅ Tous rentables</h4>
                            <h2>0</h2>
                            <p>Aucun lot négatif</p>
                        </div>
                        """, unsafe_allow_html=True)
                
                with col_res3:
                    meilleur = df_chrono.loc[df_chrono['Marge lot %'].idxmax()]
                    pire = df_chrono.loc[df_chrono['Marge lot %'].idxmin()]
                    st.markdown(f"""
                    <div class="info-card">
                        <h4>📊 Extrêmes</h4>
                        <p>🏆 <b>{meilleur['Lot']}</b> ({meilleur['Marge lot %']:+.1f}%)</p>
                        <p>⚠️ <b>{pire['Lot']}</b> ({pire['Marge lot %']:+.1f}%)</p>
                    </div>
                    """, unsafe_allow_html=True)
                
                if marge_finale_pct < 10:
                    st.markdown("---")
                    st.warning(f"""
                    ⚠️ **Marge finale < 10%** ({marge_finale_pct:.1f}%)
                    
                    **Solutions :** Passer les lots moins chers en premier, renégocier prix de vente, revoir affectations.
                    """)
                
            elif lots_df.empty:
                st.info("Aucun lot affecté à ce produit")
            else:
                st.warning("⚠️ Renseignez les prix de vente dans Paramétrage")
    else:
        st.info("Aucun produit avec affectations")

# ============================================================
# ONGLET 3: SIMULATION ACHAT
# ============================================================

elif onglet == "💵 Simulation Achat":
    st.subheader("💵 Simulation : Acheter le Manque")
    st.markdown("*Comparer acheter maintenant vs attendre*")
    
    produits_df = get_produits_avec_affectations()
    
    if not produits_df.empty:
        produits_manque = produits_df[produits_df['solde'] < 0].copy()
        
        if not produits_manque.empty:
            produits_list = [f"{row['marque']} - {row['type_produit']} ({row['solde']:+,.0f} T)" for _, row in produits_manque.iterrows()]
            selected = st.selectbox("Produit en manque", produits_list, key="select_manque")
            
            idx = produits_list.index(selected)
            produit = produits_manque.iloc[idx]
            manque = abs(float(produit['solde']))
            
            st.markdown("---")
            
            col_info1, col_info2, col_info3 = st.columns(3)
            with col_info1:
                st.metric("📦 Manque", f"{manque:,.0f} T net")
            with col_info2:
                atelier = produit['atelier'] or 'SBU'
                cout_prod = couts_prod.get(atelier, 45.0)
                st.metric("🏭 Coût prod", f"{cout_prod:,.0f} €/T")
            with col_info3:
                code_produit = produit['code_produit']
                prix_produit = prix_previsions[prix_previsions['code_produit_commercial'] == code_produit] if not prix_previsions.empty else pd.DataFrame()
                prix_actuel = float(prix_produit.iloc[0]['prix_actuel']) if not prix_produit.empty else 0
                st.metric("💰 Prix actuel", f"{prix_actuel:,.0f} €/T")
            
            st.markdown("---")
            st.markdown("#### ⚙️ Paramètres")
            
            col_param1, col_param2 = st.columns(2)
            
            with col_param1:
                st.markdown("##### 🅰️ Acheter MAINTENANT")
                prix_achat_a = st.number_input("Prix achat (€/T brut)", value=200.0, step=10.0, key="prix_a")
                tare_a = st.number_input("Tare (%)", value=22.0, step=1.0, key="tare_a")
            
            with col_param2:
                st.markdown("##### 🅱️ ATTENDRE")
                delai_options = {"2 semaines": 'prix_2_semaines', "1 mois": 'prix_1_mois', "3 mois": 'prix_3_mois', "6 mois": 'prix_6_mois'}
                delai_choice = st.selectbox("Délai", list(delai_options.keys()), key="delai")
                prix_achat_b = st.number_input(f"Prix achat dans {delai_choice} (€/T brut)", value=180.0, step=10.0, key="prix_b")
            
            st.markdown("---")
            
            if prix_actuel > 0:
                st.markdown("#### 📊 Résultats")
                
                col_res1, col_res2 = st.columns(2)
                
                with col_res1:
                    poids_brut_a = manque / (1 - tare_a / 100) if tare_a < 100 else manque
                    cout_achat_a = poids_brut_a * prix_achat_a
                    cout_prod_a = manque * cout_prod
                    cout_total_a = cout_achat_a + cout_prod_a
                    revenu_a = manque * prix_actuel
                    marge_a = revenu_a - cout_total_a
                    marge_pct_a = (marge_a / cout_total_a * 100) if cout_total_a > 0 else 0
                    prix_cible_a, _ = calculer_prix_vente_cible(prix_achat_a, tare_a, cout_prod, 10)
                    
                    card_class = "profit-card" if marge_pct_a >= 10 else ("loss-card" if marge_pct_a < 0 else "neutral-card")
                    st.markdown(f"""
                    <div class="{card_class}">
                        <h4>🅰️ MAINTENANT</h4>
                        <table style="width:100%">
                            <tr><td>Tonnage brut</td><td style="text-align:right"><b>{poids_brut_a:,.0f} T</b></td></tr>
                            <tr><td>Coût total</td><td style="text-align:right"><b>{cout_total_a:,.0f} €</b></td></tr>
                            <tr><td>Revenu</td><td style="text-align:right">{revenu_a:,.0f} €</td></tr>
                            <tr><td><b>MARGE</b></td><td style="text-align:right"><b>{marge_a:+,.0f} € ({marge_pct_a:+.1f}%)</b></td></tr>
                            <tr><td colspan="2"><hr></td></tr>
                            <tr><td>Prix min 10%</td><td style="text-align:right"><b>{prix_cible_a:,.0f} €/T</b></td></tr>
                        </table>
                    </div>
                    """, unsafe_allow_html=True)
                
                with col_res2:
                    col_prix = delai_options[delai_choice]
                    prix_vente_b = float(prix_produit.iloc[0][col_prix]) if not prix_produit.empty else prix_actuel
                    if prix_vente_b <= 0:
                        prix_vente_b = prix_actuel
                    
                    poids_brut_b = manque / (1 - tare_a / 100) if tare_a < 100 else manque
                    cout_achat_b = poids_brut_b * prix_achat_b
                    cout_prod_b = manque * cout_prod
                    cout_total_b = cout_achat_b + cout_prod_b
                    revenu_b = manque * prix_vente_b
                    marge_b = revenu_b - cout_total_b
                    marge_pct_b = (marge_b / cout_total_b * 100) if cout_total_b > 0 else 0
                    prix_cible_b, _ = calculer_prix_vente_cible(prix_achat_b, tare_a, cout_prod, 10)
                    
                    card_class = "profit-card" if marge_pct_b >= 10 else ("loss-card" if marge_pct_b < 0 else "neutral-card")
                    st.markdown(f"""
                    <div class="{card_class}">
                        <h4>🅱️ Attendre {delai_choice}</h4>
                        <table style="width:100%">
                            <tr><td>Tonnage brut</td><td style="text-align:right"><b>{poids_brut_b:,.0f} T</b></td></tr>
                            <tr><td>Coût total</td><td style="text-align:right"><b>{cout_total_b:,.0f} €</b></td></tr>
                            <tr><td>Revenu ({prix_vente_b:,.0f}€/T)</td><td style="text-align:right">{revenu_b:,.0f} €</td></tr>
                            <tr><td><b>MARGE</b></td><td style="text-align:right"><b>{marge_b:+,.0f} € ({marge_pct_b:+.1f}%)</b></td></tr>
                            <tr><td colspan="2"><hr></td></tr>
                            <tr><td>Prix min 10%</td><td style="text-align:right"><b>{prix_cible_b:,.0f} €/T</b></td></tr>
                        </table>
                    </div>
                    """, unsafe_allow_html=True)
                
                st.markdown("---")
                diff = marge_a - marge_b
                
                if marge_pct_a >= 10 and marge_pct_b >= 10:
                    if diff > 0:
                        st.success(f"✅ **Les 2 rentables (>10%). Maintenant = +{diff:,.0f} € de plus**")
                    else:
                        st.success(f"✅ **Les 2 rentables (>10%). Attendre = +{-diff:,.0f} € de plus**")
                elif marge_pct_a >= 10:
                    st.success(f"✅ **ACHETER MAINTENANT** - Seul scénario >10%")
                elif marge_pct_b >= 10:
                    st.warning(f"⏳ **ATTENDRE {delai_choice}** - Seul scénario >10%")
                else:
                    best = "maintenant" if marge_pct_a > marge_pct_b else f"dans {delai_choice}"
                    st.error(f"⚠️ **Aucun scénario >10%.** Meilleur: {best}")
            else:
                st.warning("⚠️ Renseignez les prix dans Paramétrage")
        else:
            st.success("✅ Aucun produit en manque !")
    else:
        st.info("Aucun produit avec affectations")

# ============================================================
# ONGLET 4: PARAMÉTRAGE
# ============================================================

elif onglet == "⚙️ Paramétrage":
    st.subheader("⚙️ Paramétrage")
    
    param_section = st.radio("Section", ["💰 Prix de Vente", "🏭 Coûts Production", "📊 Tare Lots"], horizontal=True, key="param_section")
    
    st.markdown("---")
    
    if param_section == "💰 Prix de Vente":
        st.markdown("#### 💰 Prix de Vente")
        
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT code_produit, marque, type_produit FROM ref_produits_commerciaux WHERE is_active = TRUE ORDER BY marque")
        produits = cursor.fetchall()
        cursor.close()
        conn.close()
        
        if produits:
            produits_options = [f"{p['marque']} - {p['type_produit']}" for p in produits]
            selected_prod = st.selectbox("Produit", produits_options, key="prix_produit")
            
            idx = produits_options.index(selected_prod)
            code_produit = produits[idx]['code_produit']
            prix_existants = prix_previsions[prix_previsions['code_produit_commercial'] == code_produit] if not prix_previsions.empty else pd.DataFrame()
            
            col1, col2 = st.columns(2)
            with col1:
                prix_actuel = st.number_input("Prix ACTUEL €/T", value=float(prix_existants.iloc[0]['prix_actuel']) if not prix_existants.empty else 0.0, step=10.0, key="p_actuel")
                prix_2sem = st.number_input("+2 SEMAINES €/T", value=float(prix_existants.iloc[0]['prix_2_semaines']) if not prix_existants.empty else 0.0, step=10.0, key="p_2sem")
                prix_1mois = st.number_input("+1 MOIS €/T", value=float(prix_existants.iloc[0]['prix_1_mois']) if not prix_existants.empty else 0.0, step=10.0, key="p_1mois")
            with col2:
                prix_3mois = st.number_input("+3 MOIS €/T", value=float(prix_existants.iloc[0]['prix_3_mois']) if not prix_existants.empty else 0.0, step=10.0, key="p_3mois")
                prix_6mois = st.number_input("+6 MOIS €/T", value=float(prix_existants.iloc[0]['prix_6_mois']) if not prix_existants.empty else 0.0, step=10.0, key="p_6mois")
            
            if st.button("💾 Enregistrer", type="primary", key="save_prix"):
                if save_prix_previsions(code_produit, prix_actuel, prix_2sem, prix_1mois, prix_3mois, prix_6mois):
                    st.success("✅ Prix enregistrés !")
                    get_prix_ventes_previsions.clear()
                    st.rerun()
    
    elif param_section == "🏭 Coûts Production":
        st.markdown("#### 🏭 Coûts Production")
        
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT type_atelier, cout_tonne FROM production_lignes WHERE is_active = TRUE ORDER BY type_atelier")
        lignes = cursor.fetchall()
        cursor.close()
        conn.close()
        
        if lignes:
            for ligne in lignes:
                col1, col2, col3 = st.columns([2, 2, 1])
                with col1:
                    st.markdown(f"**{ligne['type_atelier']}**")
                with col2:
                    new_cout = st.number_input("€/T", value=float(ligne['cout_tonne'] or 0), step=5.0, key=f"cout_{ligne['type_atelier']}", label_visibility="collapsed")
                with col3:
                    if st.button("💾", key=f"save_{ligne['type_atelier']}"):
                        if update_cout_production(ligne['type_atelier'], new_cout):
                            st.success("✅")
                            get_couts_production.clear()
                            st.rerun()
    
    elif param_section == "📊 Tare Lots":
        st.markdown("#### 📊 Tare Théorique par Lot")
        st.info("💡 **Lots brossés** : mettre 10% au lieu de 22%")
        
        lots_df = get_lots_pour_tare()
        
        if not lots_df.empty:
            st.success(f"📋 {len(lots_df)} lot(s) non lavés")
            
            col_f1, col_f2 = st.columns(2)
            with col_f1:
                varietes_list = sorted(lots_df['nom_variete'].dropna().unique().tolist())
                filter_var = st.multiselect("Filtrer variété", varietes_list, key="fv")
            with col_f2:
                filter_tare = st.selectbox("Filtrer tare", ["Tous", "Défaut (22%)", "Personnalisée"], key="ft")
            
            df_filtered = lots_df.copy()
            if filter_var:
                df_filtered = df_filtered[df_filtered['nom_variete'].isin(filter_var)]
            if filter_tare == "Défaut (22%)":
                df_filtered = df_filtered[df_filtered['tare_theorique'].isna()]
            elif filter_tare == "Personnalisée":
                df_filtered = df_filtered[df_filtered['tare_theorique'].notna()]
            
            st.markdown("---")
            
            if not df_filtered.empty:
                st.markdown("#### ⚡ Action rapide")
                col_a1, col_a2 = st.columns(2)
                with col_a1:
                    tare_groupe = st.number_input("Tare à appliquer (%)", value=10.0, step=1.0, key="tg")
                with col_a2:
                    st.markdown("<br>", unsafe_allow_html=True)
                    if st.button(f"🎯 Appliquer {tare_groupe:.0f}% aux {len(df_filtered)} lots", type="primary"):
                        success = 0
                        for _, lot in df_filtered.iterrows():
                            if update_tare_theorique(lot['id'], tare_groupe if tare_groupe != 22.0 else None):
                                success += 1
                        st.success(f"✅ {success} lot(s) mis à jour !")
                        st.rerun()
                
                st.markdown("---")
                st.markdown("#### 📝 Édition individuelle")
                
                for _, lot in df_filtered.head(20).iterrows():
                    col1, col2, col3, col4 = st.columns([3, 2, 2, 1])
                    with col1:
                        st.markdown(f"**{lot['code_lot_interne']}**")
                        st.caption(f"{lot['nom_variete']} • {lot['poids_brut_tonnes']:.0f} T")
                    with col2:
                        st.markdown(f"Actuelle: **{lot['tare_utilisee']:.0f}%**")
                    with col3:
                        default = float(lot['tare_theorique']) if pd.notna(lot['tare_theorique']) else 22.0
                        new_tare = st.number_input("", value=default, step=1.0, key=f"t_{lot['id']}", label_visibility="collapsed")
                    with col4:
                        if st.button("💾", key=f"s_{lot['id']}"):
                            if update_tare_theorique(lot['id'], new_tare if new_tare != 22.0 else None):
                                st.success("✅")
                                st.rerun()
                    st.markdown("---")

st.markdown("---")
show_footer()
