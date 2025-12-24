import streamlit as st
import pandas as pd
from datetime import datetime, date
from database import get_connection
from components import show_footer
from auth import is_authenticated

st.set_page_config(page_title="Prévisions Dashboard - Culture Pom", page_icon="📊", layout="wide")

# CSS compact
st.markdown("""
<style>
    .block-container {
        padding-top: 1.5rem !important;
        padding-bottom: 0.5rem !important;
    }
    h1, h2, h3, h4 {
        margin-top: 0.3rem !important;
        margin-bottom: 0.3rem !important;
    }
    .metric-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 1rem;
        border-radius: 0.5rem;
        color: white;
        text-align: center;
    }
    .alert-card {
        padding: 0.8rem;
        border-radius: 0.5rem;
        margin: 0.3rem 0;
        border-left: 4px solid;
    }
    .alert-manque {
        background-color: #ffebee;
        border-left-color: #f44336;
    }
    .alert-surplus {
        background-color: #e8f5e9;
        border-left-color: #4caf50;
    }
    .alert-equilibre {
        background-color: #e3f2fd;
        border-left-color: #2196f3;
    }
</style>
""", unsafe_allow_html=True)

if not is_authenticated():
    st.warning("⚠️ Veuillez vous connecter pour accéder à cette page")
    st.stop()

# ============================================================
# CONSTANTES CAMPAGNE - DYNAMIQUES
# ============================================================

def get_campagne_info():
    """Calcule les dates de la campagne courante (Juillet N à Juin N+1)"""
    today = date.today()
    
    # Si on est entre Juillet et Décembre → campagne N / N+1
    # Si on est entre Janvier et Juin → campagne N-1 / N
    if today.month >= 7:
        annee_debut = today.year
        annee_fin = today.year + 1
    else:
        annee_debut = today.year - 1
        annee_fin = today.year
    
    date_debut = date(annee_debut, 7, 1)
    date_fin = date(annee_fin, 6, 30)
    
    semaines_restantes = max(0, (date_fin - today).days // 7)
    
    return {
        'annee_debut': annee_debut,
        'annee_fin': annee_fin,
        'date_debut': date_debut,
        'date_fin': date_fin,
        'semaines_restantes': semaines_restantes,
        'label': f"{annee_debut}-{annee_fin}"
    }

CAMPAGNE = get_campagne_info()

# ============================================================
# FONCTIONS DONNÉES
# ============================================================

def get_sites_production():
    """Récupère les sites de production distincts"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT DISTINCT site 
            FROM production_lignes 
            WHERE is_active = TRUE AND site IS NOT NULL
            ORDER BY site
        """)
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        return [row['site'] for row in rows] if rows else []
    except Exception as e:
        return []


def get_kpis_globaux(site_filter=None):
    """Récupère les KPIs globaux du module prévisions - VERSION CORRIGÉE"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        today = date.today()
        semaine_courante = today.isocalendar()[1]
        annee_courante = today.year
        
        # KPI 1: Stock brut total (tonnes) - lots actifs
        query_stock = """
            SELECT COALESCE(SUM(poids_total_brut_kg), 0) / 1000 as stock_brut_tonnes
            FROM lots_bruts 
            WHERE is_active = TRUE
        """
        cursor.execute(query_stock)
        stock_brut = float(cursor.fetchone()['stock_brut_tonnes'] or 0)
        
        # KPI 2: Stock net estimé (avec tare moyenne 22%)
        stock_net = stock_brut * 0.78
        
        # KPI 3: Besoins jusqu'à fin campagne - REQUÊTE CORRIGÉE
        # On prend toutes les prévisions de la semaine courante jusqu'à fin juin de l'année de fin de campagne
        query_besoins = """
            SELECT COALESCE(SUM(quantite_prevue_tonnes), 0) as besoin_total
            FROM previsions_ventes
            WHERE (
                -- Semaines restantes cette année
                (annee = %s AND semaine >= %s)
                OR
                -- Toutes les semaines de l'année suivante jusqu'à S26 (fin juin)
                (annee = %s AND semaine <= 26)
            )
        """
        cursor.execute(query_besoins, (annee_courante, semaine_courante, CAMPAGNE['annee_fin']))
        besoin_total = float(cursor.fetchone()['besoin_total'] or 0)
        
        # KPI 4: Lots affectés
        query_affectes = """
            SELECT COUNT(DISTINCT lot_id) as nb_lots_affectes,
                   COALESCE(SUM(quantite_affectee_tonnes), 0) as tonnes_affectees
            FROM previsions_affectations
            WHERE is_active = TRUE
        """
        cursor.execute(query_affectes)
        result = cursor.fetchone()
        nb_lots_affectes = result['nb_lots_affectes'] or 0
        tonnes_affectees = float(result['tonnes_affectees'] or 0)
        
        # KPI 5: Produits avec prévisions actives
        query_produits = """
            SELECT COUNT(DISTINCT code_produit_commercial) as nb_produits
            FROM previsions_ventes
            WHERE (annee = %s AND semaine >= %s) OR (annee = %s AND semaine <= 26)
        """
        cursor.execute(query_produits, (annee_courante, semaine_courante, CAMPAGNE['annee_fin']))
        nb_produits = cursor.fetchone()['nb_produits'] or 0
        
        cursor.close()
        conn.close()
        
        return {
            'stock_brut_tonnes': stock_brut,
            'stock_net_tonnes': stock_net,
            'besoin_total_tonnes': besoin_total,
            'nb_lots_affectes': nb_lots_affectes,
            'tonnes_affectees': tonnes_affectees,
            'nb_produits': nb_produits,
            'semaines_restantes': CAMPAGNE['semaines_restantes'],
            'difference': stock_net - besoin_total
        }
        
    except Exception as e:
        st.error(f"Erreur KPIs: {str(e)}")
        return None


def get_alertes_produits(site_filter=None):
    """Récupère les alertes par produit (manque/surplus) - VERSION CORRIGÉE"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        today = date.today()
        semaine_courante = today.isocalendar()[1]
        annee_courante = today.year
        
        # Besoins par produit jusqu'à fin campagne
        query = f"""
            WITH besoins AS (
                SELECT 
                    pv.code_produit_commercial,
                    pc.marque,
                    pc.type_produit,
                    pc.atelier,
                    SUM(pv.quantite_prevue_tonnes) as besoin_tonnes
                FROM previsions_ventes pv
                JOIN ref_produits_commerciaux pc ON pv.code_produit_commercial = pc.code_produit
                WHERE (pv.annee = %s AND pv.semaine >= %s)
                   OR (pv.annee = %s AND pv.semaine <= 26)
                GROUP BY pv.code_produit_commercial, pc.marque, pc.type_produit, pc.atelier
            ),
            affectations AS (
                SELECT 
                    pa.code_produit_commercial,
                    SUM(COALESCE(pa.poids_net_estime_tonnes, pa.quantite_affectee_tonnes * 0.78)) as stock_affecte
                FROM previsions_affectations pa
                WHERE pa.is_active = TRUE
                GROUP BY pa.code_produit_commercial
            )
            SELECT 
                b.code_produit_commercial,
                b.marque,
                b.type_produit,
                b.atelier,
                b.besoin_tonnes,
                COALESCE(a.stock_affecte, 0) as stock_affecte,
                COALESCE(a.stock_affecte, 0) - b.besoin_tonnes as difference,
                CASE 
                    WHEN COALESCE(a.stock_affecte, 0) - b.besoin_tonnes < -50 THEN 'MANQUE'
                    WHEN COALESCE(a.stock_affecte, 0) - b.besoin_tonnes > 50 THEN 'SURPLUS'
                    ELSE 'EQUILIBRE'
                END as statut
            FROM besoins b
            LEFT JOIN affectations a ON b.code_produit_commercial = a.code_produit_commercial
            ORDER BY difference ASC
        """
        
        cursor.execute(query, (annee_courante, semaine_courante, CAMPAGNE['annee_fin']))
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        
        if rows:
            df = pd.DataFrame(rows)
            for col in ['besoin_tonnes', 'stock_affecte', 'difference']:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
            return df
        return pd.DataFrame()
        
    except Exception as e:
        st.error(f"Erreur alertes: {str(e)}")
        return pd.DataFrame()


def get_consommation_semaine():
    """Récupère la consommation par semaine (12 prochaines semaines)"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        today = date.today()
        semaine_courante = today.isocalendar()[1]
        annee_courante = today.year
        
        query = """
            SELECT 
                pv.semaine,
                pv.annee,
                SUM(pv.quantite_prevue_tonnes) as total_tonnes
            FROM previsions_ventes pv
            WHERE (pv.annee = %s AND pv.semaine >= %s)
               OR (pv.annee > %s)
            GROUP BY pv.annee, pv.semaine
            ORDER BY pv.annee, pv.semaine
            LIMIT 12
        """
        
        cursor.execute(query, (annee_courante, semaine_courante, annee_courante))
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        
        if rows:
            df = pd.DataFrame(rows)
            df['total_tonnes'] = pd.to_numeric(df['total_tonnes'], errors='coerce').fillna(0)
            df['semaine_label'] = df.apply(
                lambda r: f"S{int(r['semaine']):02d}", axis=1
            )
            return df
        return pd.DataFrame()
        
    except Exception as e:
        return pd.DataFrame()


def get_stock_par_marque():
    """Récupère le stock affecté par marque"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        query = """
            SELECT 
                pc.marque,
                SUM(COALESCE(pa.poids_net_estime_tonnes, pa.quantite_affectee_tonnes * 0.78)) as tonnes_affectees
            FROM previsions_affectations pa
            JOIN ref_produits_commerciaux pc ON pa.code_produit_commercial = pc.code_produit
            WHERE pa.is_active = TRUE
            GROUP BY pc.marque
            ORDER BY tonnes_affectees DESC
        """
        
        cursor.execute(query)
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        
        if rows:
            df = pd.DataFrame(rows)
            df['tonnes_affectees'] = pd.to_numeric(df['tonnes_affectees'], errors='coerce').fillna(0)
            return df
        return pd.DataFrame()
        
    except Exception as e:
        return pd.DataFrame()


# ============================================================
# INTERFACE
# ============================================================

st.title("📊 Dashboard Prévisions")
st.markdown(f"*Vue synthétique des prévisions et affectations - Campagne {CAMPAGNE['label']}*")

# Filtres
col_site, col_refresh = st.columns([4, 1])

with col_site:
    sites = get_sites_production()
    site_options = ["Tous les sites"] + sites
    selected_site = st.selectbox("🏭 Site", site_options, key="filter_site")
    site_filter = None if selected_site == "Tous les sites" else selected_site

with col_refresh:
    st.write("")
    if st.button("🔄 Actualiser", use_container_width=True):
        st.rerun()

st.markdown("---")

# ============================================================
# KPIs PRINCIPAUX
# ============================================================

kpis = get_kpis_globaux(site_filter)

if kpis:
    col1, col2, col3, col4, col5, col6 = st.columns(6)
    
    with col1:
        st.metric(
            "📦 Stock Brut",
            f"{kpis['stock_brut_tonnes']:,.0f} T",
            help="Tonnage brut total en stock"
        )
    
    with col2:
        st.metric(
            "⚖️ Stock Net Estimé",
            f"{kpis['stock_net_tonnes']:,.0f} T",
            help="Tonnage net estimé (après tare ~22%)"
        )
    
    with col3:
        st.metric(
            "🎯 Besoin Campagne",
            f"{kpis['besoin_total_tonnes']:,.0f} T",
            help=f"Besoin total jusqu'au {CAMPAGNE['date_fin'].strftime('%d/%m/%Y')}"
        )
    
    with col4:
        diff = kpis['difference']
        delta_color = "normal" if diff >= 0 else "inverse"
        st.metric(
            "📈 Différence",
            f"{diff:+,.0f} T",
            delta=f"{'SURPLUS' if diff > 0 else 'MANQUE' if diff < 0 else 'ÉQUILIBRE'}",
            delta_color=delta_color
        )
    
    with col5:
        st.metric(
            "📋 Lots Affectés",
            f"{kpis['nb_lots_affectes']}",
            help="Nombre de lots avec affectation"
        )
    
    with col6:
        st.metric(
            "📅 Semaines Restantes",
            f"{kpis['semaines_restantes']}",
            help=f"Semaines jusqu'au {CAMPAGNE['date_fin'].strftime('%d/%m/%Y')}"
        )

st.markdown("---")

# ============================================================
# ALERTES PAR PRODUIT
# ============================================================

st.subheader("🚨 Alertes par Produit")

alertes_df = get_alertes_produits(site_filter)

if not alertes_df.empty:
    # Compter les alertes
    nb_manque = len(alertes_df[alertes_df['statut'] == 'MANQUE'])
    nb_surplus = len(alertes_df[alertes_df['statut'] == 'SURPLUS'])
    nb_equilibre = len(alertes_df[alertes_df['statut'] == 'EQUILIBRE'])
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown(f"""
        <div class="alert-card alert-manque">
            <strong>🔴 MANQUE</strong><br>
            <span style="font-size: 1.5rem;">{nb_manque}</span> produits
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        st.markdown(f"""
        <div class="alert-card alert-equilibre">
            <strong>🔵 ÉQUILIBRE</strong><br>
            <span style="font-size: 1.5rem;">{nb_equilibre}</span> produits
        </div>
        """, unsafe_allow_html=True)
    
    with col3:
        st.markdown(f"""
        <div class="alert-card alert-surplus">
            <strong>🟢 SURPLUS</strong><br>
            <span style="font-size: 1.5rem;">{nb_surplus}</span> produits
        </div>
        """, unsafe_allow_html=True)
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    # Tableau des alertes critiques (MANQUE uniquement)
    alertes_critiques = alertes_df[alertes_df['statut'] == 'MANQUE'].head(10)
    
    if not alertes_critiques.empty:
        st.markdown("#### ⚠️ Produits en Manque (Top 10)")
        
        df_display = alertes_critiques[['marque', 'type_produit', 'besoin_tonnes', 'stock_affecte', 'difference']].copy()
        df_display.columns = ['Marque', 'Type Produit', 'Besoin (T)', 'Stock Affecté (T)', 'Manque (T)']
        
        df_display['Besoin (T)'] = df_display['Besoin (T)'].apply(lambda x: f"{x:,.0f}")
        df_display['Stock Affecté (T)'] = df_display['Stock Affecté (T)'].apply(lambda x: f"{x:,.0f}")
        df_display['Manque (T)'] = df_display['Manque (T)'].apply(lambda x: f"{x:,.0f}")
        
        st.dataframe(df_display, use_container_width=True, hide_index=True)
    
    # Tableau des surplus
    alertes_surplus = alertes_df[alertes_df['statut'] == 'SURPLUS'].head(5)
    
    if not alertes_surplus.empty:
        st.markdown("#### 📈 Produits en Surplus (Top 5)")
        
        df_display = alertes_surplus[['marque', 'type_produit', 'besoin_tonnes', 'stock_affecte', 'difference']].copy()
        df_display.columns = ['Marque', 'Type Produit', 'Besoin (T)', 'Stock Affecté (T)', 'Surplus (T)']
        
        df_display['Besoin (T)'] = df_display['Besoin (T)'].apply(lambda x: f"{x:,.0f}")
        df_display['Stock Affecté (T)'] = df_display['Stock Affecté (T)'].apply(lambda x: f"{x:,.0f}")
        df_display['Surplus (T)'] = df_display['Surplus (T)'].apply(lambda x: f"+{x:,.0f}")
        
        st.dataframe(df_display, use_container_width=True, hide_index=True)

else:
    st.info("Aucune donnée de prévision disponible. Vérifiez que la table `previsions_ventes` contient des données pour la période courante.")

st.markdown("---")

# ============================================================
# GRAPHIQUES
# ============================================================

col_chart1, col_chart2 = st.columns(2)

with col_chart1:
    st.subheader("📈 Prévisions par Semaine")
    
    conso_df = get_consommation_semaine()
    
    if not conso_df.empty:
        st.bar_chart(
            conso_df.set_index('semaine_label')['total_tonnes'],
            use_container_width=True
        )
    else:
        st.info("Aucune donnée de prévision")

with col_chart2:
    st.subheader("🏷️ Stock Affecté par Marque")
    
    stock_marque_df = get_stock_par_marque()
    
    if not stock_marque_df.empty and stock_marque_df['tonnes_affectees'].sum() > 0:
        chart_data = stock_marque_df.set_index('marque')['tonnes_affectees']
        st.bar_chart(chart_data, use_container_width=True)
    else:
        st.info("Aucune affectation en cours")

st.markdown("---")

# ============================================================
# RACCOURCIS NAVIGATION
# ============================================================

st.subheader("🔗 Accès Rapide")

col1, col2, col3 = st.columns(3)

with col1:
    st.markdown("""
    **📋 Affectations**  
    Gérer les affectations lots → produits
    """)
    if st.button("→ Aller aux Affectations", key="nav_affectations", use_container_width=True):
        st.switch_page("pages/32_Prev_Affectations.py")

with col2:
    st.markdown("""
    **💰 Simulation**  
    Simuler la rentabilité et scénarios
    """)
    if st.button("→ Aller à Simulation", key="nav_simulation", use_container_width=True):
        st.switch_page("pages/33_Prev_Simulation.py")

with col3:
    st.markdown("""
    **📊 Besoins**  
    Calcul détaillé des besoins campagne
    """)
    if st.button("→ Aller aux Besoins", key="nav_besoins", use_container_width=True):
        st.switch_page("pages/34_Prev_Besoins.py")

st.markdown("---")

# ============================================================
# INFORMATIONS CAMPAGNE
# ============================================================

with st.expander("ℹ️ Informations Campagne"):
    st.markdown(f"""
    **Campagne actuelle** : {CAMPAGNE['label']}  
    **Période** : {CAMPAGNE['date_debut'].strftime('%d/%m/%Y')} → {CAMPAGNE['date_fin'].strftime('%d/%m/%Y')}  
    **Fin de campagne** : Semaine 26 ({CAMPAGNE['date_fin'].strftime('%d/%m/%Y')})
    
    **Calculs utilisés** :
    - **Tare** : Priorité = Réelle (lavage) > Lot > Variété > 22% défaut
    - **Stock net** = Stock brut × (1 - Tare%)
    - **Date fin lot** = Date début + (Stock / Conso hebdo × 7 jours)
    - **Surplus/Manque** = Stock affecté net - Besoin campagne
    
    **Seuils d'alerte** :
    - 🔴 MANQUE : Différence < -50 T
    - 🔵 ÉQUILIBRE : -50 T ≤ Différence ≤ +50 T
    - 🟢 SURPLUS : Différence > +50 T
    """)

show_footer()
