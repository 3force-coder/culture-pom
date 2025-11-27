"""
Page 14 - Récaps Plan Récolte
KPIs globaux + 5 vues agrégées (Mois, Variété, Marque, Type, Croisé)
VERSION CORRIGÉE - Accès par nom de colonne (RealDictCursor)
"""
import streamlit as st
import pandas as pd
from database import get_connection
from components import show_footer
from auth import is_authenticated, has_access, can_edit, can_delete, get_current_username
import io

st.set_page_config(page_title="Récaps Plan - Culture Pom", page_icon="📊", layout="wide")

# CSS compact
st.markdown("""
<style>
    .block-container {
        padding-top: 2rem !important;
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
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
    }
    .stTabs [data-baseweb="tab"] {
        padding: 8px 16px;
    }
</style>
""", unsafe_allow_html=True)

# Vérification authentification
if not is_authenticated():
    st.warning("⚠️ Veuillez vous connecter pour accéder à cette page")
    st.stop()

# Vérification permissions
if not has_access("PLANS_RECOLTE"):
    st.error("🚫 Vous n'avez pas accès à cette page")
    st.stop()

# Permissions utilisateur
CAN_EDIT = can_edit("PLANS_RECOLTE")
CAN_DELETE = can_delete("PLANS_RECOLTE")

st.title("📊 Récaps Plan Récolte")
st.markdown("*Synthèses et analyses du plan de récolte*")
st.markdown("---")

# ==========================================
# FONCTIONS DE CHARGEMENT
# ==========================================

@st.cache_data(ttl=60)
def get_kpis_globaux(campagne):
    """KPIs globaux du plan"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                COUNT(*) as nb_lignes,
                COUNT(DISTINCT variete) as nb_varietes,
                COUNT(DISTINCT marque) as nb_marques,
                COUNT(DISTINCT type_produit) as nb_types,
                COALESCE(SUM(volume_net_t), 0) as total_volume_net,
                COALESCE(SUM(volume_brut_t), 0) as total_volume_brut,
                COALESCE(SUM(hectares_necessaires), 0) as total_hectares,
                COALESCE(CEIL(SUM(hectares_necessaires)), 0) as total_hectares_arrondi
            FROM plans_recolte
            WHERE campagne = %s AND is_active = TRUE
        """, (campagne,))
        
        row = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if row:
            # ✅ Accès par nom de colonne (RealDictCursor)
            return {
                'nb_lignes': row['nb_lignes'],
                'nb_varietes': row['nb_varietes'],
                'nb_marques': row['nb_marques'],
                'nb_types': row['nb_types'],
                'total_volume_net': float(row['total_volume_net']),
                'total_volume_brut': float(row['total_volume_brut']),
                'total_hectares': float(row['total_hectares']),
                'total_hectares_arrondi': int(row['total_hectares_arrondi'])
            }
        return None
    except Exception as e:
        st.error(f"Erreur KPIs : {e}")
        return None


@st.cache_data(ttl=60)
def get_recap_par_mois(campagne):
    """Récap par mois"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                mois,
                mois_numero,
                COUNT(*) as nb_lignes,
                COUNT(DISTINCT variete) as nb_varietes,
                SUM(volume_net_t) as volume_net,
                SUM(volume_brut_t) as volume_brut,
                SUM(hectares_necessaires) as hectares,
                CEIL(SUM(hectares_necessaires)) as hectares_arrondi
            FROM plans_recolte
            WHERE campagne = %s AND is_active = TRUE
            GROUP BY mois, mois_numero
            ORDER BY mois_numero
        """, (campagne,))
        
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        
        if rows:
            # ✅ Création DataFrame depuis dictionnaires + renommage
            df = pd.DataFrame(rows)
            df = df.rename(columns={
                'mois': 'Mois',
                'nb_lignes': 'Lignes',
                'nb_varietes': 'Variétés',
                'volume_net': 'Volume Net (T)',
                'volume_brut': 'Volume Brut (T)',
                'hectares': 'Hectares',
                'hectares_arrondi': 'Ha Arrondi'
            })
            return df
        return pd.DataFrame()
    except Exception as e:
        st.error(f"Erreur : {e}")
        return pd.DataFrame()


@st.cache_data(ttl=60)
def get_recap_par_variete(campagne):
    """Récap par variété"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                variete,
                COUNT(*) as nb_lignes,
                COUNT(DISTINCT mois) as nb_mois,
                SUM(volume_net_t) as volume_net,
                SUM(volume_brut_t) as volume_brut,
                SUM(hectares_necessaires) as hectares,
                CEIL(SUM(hectares_necessaires)) as hectares_arrondi
            FROM plans_recolte
            WHERE campagne = %s AND is_active = TRUE
            GROUP BY variete
            ORDER BY SUM(volume_net_t) DESC
        """, (campagne,))
        
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        
        if rows:
            df = pd.DataFrame(rows)
            df = df.rename(columns={
                'variete': 'Variété',
                'nb_lignes': 'Lignes',
                'nb_mois': 'Mois',
                'volume_net': 'Volume Net (T)',
                'volume_brut': 'Volume Brut (T)',
                'hectares': 'Hectares',
                'hectares_arrondi': 'Ha Arrondi'
            })
            return df
        return pd.DataFrame()
    except Exception as e:
        st.error(f"Erreur : {e}")
        return pd.DataFrame()


@st.cache_data(ttl=60)
def get_recap_par_marque(campagne):
    """Récap par marque"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                COALESCE(marque, '(Non défini)') as marque,
                COUNT(*) as nb_lignes,
                COUNT(DISTINCT variete) as nb_varietes,
                SUM(volume_net_t) as volume_net,
                SUM(volume_brut_t) as volume_brut,
                SUM(hectares_necessaires) as hectares,
                CEIL(SUM(hectares_necessaires)) as hectares_arrondi
            FROM plans_recolte
            WHERE campagne = %s AND is_active = TRUE
            GROUP BY marque
            ORDER BY SUM(volume_net_t) DESC
        """, (campagne,))
        
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        
        if rows:
            df = pd.DataFrame(rows)
            df = df.rename(columns={
                'marque': 'Marque',
                'nb_lignes': 'Lignes',
                'nb_varietes': 'Variétés',
                'volume_net': 'Volume Net (T)',
                'volume_brut': 'Volume Brut (T)',
                'hectares': 'Hectares',
                'hectares_arrondi': 'Ha Arrondi'
            })
            return df
        return pd.DataFrame()
    except Exception as e:
        st.error(f"Erreur : {e}")
        return pd.DataFrame()


@st.cache_data(ttl=60)
def get_recap_par_type(campagne):
    """Récap par type produit"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                COALESCE(type_produit, '(Non défini)') as type_produit,
                COUNT(*) as nb_lignes,
                COUNT(DISTINCT variete) as nb_varietes,
                SUM(volume_net_t) as volume_net,
                SUM(volume_brut_t) as volume_brut,
                SUM(hectares_necessaires) as hectares,
                CEIL(SUM(hectares_necessaires)) as hectares_arrondi
            FROM plans_recolte
            WHERE campagne = %s AND is_active = TRUE
            GROUP BY type_produit
            ORDER BY SUM(volume_net_t) DESC
        """, (campagne,))
        
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        
        if rows:
            df = pd.DataFrame(rows)
            df = df.rename(columns={
                'type_produit': 'Type Produit',
                'nb_lignes': 'Lignes',
                'nb_varietes': 'Variétés',
                'volume_net': 'Volume Net (T)',
                'volume_brut': 'Volume Brut (T)',
                'hectares': 'Hectares',
                'hectares_arrondi': 'Ha Arrondi'
            })
            return df
        return pd.DataFrame()
    except Exception as e:
        st.error(f"Erreur : {e}")
        return pd.DataFrame()


@st.cache_data(ttl=60)
def get_recap_croise(campagne):
    """Récap croisé variété × mois"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                variete,
                mois,
                mois_numero,
                SUM(volume_net_t) as volume_net,
                SUM(hectares_necessaires) as hectares
            FROM plans_recolte
            WHERE campagne = %s AND is_active = TRUE
            GROUP BY variete, mois, mois_numero
            ORDER BY variete, mois_numero
        """, (campagne,))
        
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        
        if rows:
            df = pd.DataFrame(rows)
            df = df.rename(columns={
                'variete': 'Variété',
                'mois': 'Mois',
                'volume_net': 'Volume Net',
                'hectares': 'Hectares'
            })
            return df
        return pd.DataFrame()
    except Exception as e:
        st.error(f"Erreur : {e}")
        return pd.DataFrame()


@st.cache_data(ttl=60)
def get_besoins_avec_couverture(campagne):
    """Récupère les besoins avec taux de couverture"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # ✅ CORRIGÉ : Nom de table plans_recolte_besoins (pas besoins_recolte)
        cursor.execute("""
            SELECT 
                b.id,
                b.variete,
                b.mois,
                b.mois_numero,
                b.volume_net_t,
                b.volume_brut_t,
                b.total_hectares_arrondi as hectares_besoin,
                COALESCE(b.hectares_affectes, 0) as hectares_affectes,
                COALESCE(b.taux_couverture_pct, 0) as couverture_pct,
                COALESCE(b.is_complet, FALSE) as complet
            FROM plans_recolte_besoins b
            WHERE b.campagne = %s AND b.is_active = TRUE
            ORDER BY b.mois_numero, b.variete
        """, (campagne,))
        
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        
        if rows:
            df = pd.DataFrame(rows)
            df = df.rename(columns={
                'variete': 'Variété',
                'mois': 'Mois',
                'volume_net_t': 'Volume Net (T)',
                'volume_brut_t': 'Volume Brut (T)',
                'hectares_besoin': 'Ha Besoin',
                'hectares_affectes': 'Ha Affectés',
                'couverture_pct': 'Couverture %',
                'complet': 'Complet'
            })
            return df
        return pd.DataFrame()
    except Exception as e:
        st.error(f"Erreur besoins : {e}")
        return pd.DataFrame()


@st.cache_data(ttl=60)
def get_campagnes_disponibles():
    """Liste des campagnes avec données"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT DISTINCT campagne 
            FROM plans_recolte 
            WHERE is_active = TRUE
            ORDER BY campagne DESC
        """)
        
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        
        return [row['campagne'] for row in rows] if rows else []
    except Exception as e:
        st.error(f"Erreur : {e}")
        return []


# ==========================================
# SÉLECTEUR CAMPAGNE
# ==========================================

campagnes = get_campagnes_disponibles()

if not campagnes:
    st.warning("⚠️ Aucune campagne disponible. Créez d'abord un plan de récolte.")
    show_footer()
    st.stop()

col1, col2 = st.columns([2, 1])

with col1:
    campagne = st.selectbox("Campagne", campagnes, key="campagne_recap")

with col2:
    if st.button("🔄 Rafraîchir", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

st.markdown("---")

# ==========================================
# KPIs GLOBAUX
# ==========================================

kpis = get_kpis_globaux(campagne)

if kpis:
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("📋 Lignes plan", kpis['nb_lignes'])
    
    with col2:
        st.metric("🌾 Variétés", kpis['nb_varietes'])
    
    with col3:
        st.metric("📦 Volume Net", f"{kpis['total_volume_net']:,.0f} T")
    
    with col4:
        st.metric("🚜 Hectares", f"{kpis['total_hectares_arrondi']:,} ha")
    
    # Ligne 2
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("🏷️ Marques", kpis['nb_marques'])
    
    with col2:
        st.metric("📂 Types", kpis['nb_types'])
    
    with col3:
        st.metric("📦 Volume Brut", f"{kpis['total_volume_brut']:,.0f} T")
    
    with col4:
        rendement_moyen = kpis['total_volume_net'] / kpis['total_hectares'] if kpis['total_hectares'] > 0 else 0
        st.metric("📊 Rdt moyen", f"{rendement_moyen:.1f} T/ha")
else:
    st.warning("⚠️ Impossible de charger les KPIs")

st.markdown("---")

# ==========================================
# ONGLETS
# ==========================================

tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "📅 Par Mois", 
    "🌾 Par Variété", 
    "🏷️ Par Marque",
    "📂 Par Type",
    "📊 Croisé (Variété×Mois)",
    "🎯 Besoins & Couverture"
])

# ==========================================
# TAB 1 : PAR MOIS
# ==========================================

with tab1:
    st.subheader("📅 Récap par Mois")
    
    df_mois = get_recap_par_mois(campagne)
    
    if not df_mois.empty:
        # Masquer colonne technique
        df_display = df_mois.drop(columns=['mois_numero'], errors='ignore')
        
        st.dataframe(
            df_display,
            column_config={
                "Mois": st.column_config.TextColumn("Mois", width="medium"),
                "Lignes": st.column_config.NumberColumn("Lignes", format="%d"),
                "Variétés": st.column_config.NumberColumn("Variétés", format="%d"),
                "Volume Net (T)": st.column_config.NumberColumn("Volume Net (T)", format="%.1f"),
                "Volume Brut (T)": st.column_config.NumberColumn("Volume Brut (T)", format="%.1f"),
                "Hectares": st.column_config.NumberColumn("Hectares", format="%.1f"),
                "Ha Arrondi": st.column_config.NumberColumn("Ha Arrondi", format="%d"),
            },
            use_container_width=True,
            hide_index=True
        )
        
        # Graphique
        st.markdown("#### 📊 Évolution mensuelle")
        chart_data = df_display[['Mois', 'Volume Net (T)', 'Hectares']].set_index('Mois')
        st.line_chart(chart_data)
    else:
        st.info("Aucune donnée")

# ==========================================
# TAB 2 : PAR VARIÉTÉ
# ==========================================

with tab2:
    st.subheader("🌾 Récap par Variété")
    
    df_variete = get_recap_par_variete(campagne)
    
    if not df_variete.empty:
        st.dataframe(
            df_variete,
            column_config={
                "Variété": st.column_config.TextColumn("Variété", width="medium"),
                "Lignes": st.column_config.NumberColumn("Lignes", format="%d"),
                "Mois": st.column_config.NumberColumn("Mois", format="%d"),
                "Volume Net (T)": st.column_config.NumberColumn("Volume Net (T)", format="%.1f"),
                "Volume Brut (T)": st.column_config.NumberColumn("Volume Brut (T)", format="%.1f"),
                "Hectares": st.column_config.NumberColumn("Hectares", format="%.1f"),
                "Ha Arrondi": st.column_config.NumberColumn("Ha Arrondi", format="%d"),
            },
            use_container_width=True,
            hide_index=True
        )
        
        # Graphique top 10
        st.markdown("#### 📊 Top 10 Variétés (Volume Net)")
        top10 = df_variete.head(10)[['Variété', 'Volume Net (T)']].set_index('Variété')
        st.bar_chart(top10)
    else:
        st.info("Aucune donnée")

# ==========================================
# TAB 3 : PAR MARQUE
# ==========================================

with tab3:
    st.subheader("🏷️ Récap par Marque")
    
    df_marque = get_recap_par_marque(campagne)
    
    if not df_marque.empty:
        st.dataframe(
            df_marque,
            column_config={
                "Marque": st.column_config.TextColumn("Marque", width="medium"),
                "Lignes": st.column_config.NumberColumn("Lignes", format="%d"),
                "Variétés": st.column_config.NumberColumn("Variétés", format="%d"),
                "Volume Net (T)": st.column_config.NumberColumn("Volume Net (T)", format="%.1f"),
                "Volume Brut (T)": st.column_config.NumberColumn("Volume Brut (T)", format="%.1f"),
                "Hectares": st.column_config.NumberColumn("Hectares", format="%.1f"),
                "Ha Arrondi": st.column_config.NumberColumn("Ha Arrondi", format="%d"),
            },
            use_container_width=True,
            hide_index=True
        )
        
        # Graphique
        st.markdown("#### 📊 Répartition par Marque")
        chart_marque = df_marque[['Marque', 'Volume Net (T)']].set_index('Marque')
        st.bar_chart(chart_marque)
    else:
        st.info("Aucune donnée")

# ==========================================
# TAB 4 : PAR TYPE
# ==========================================

with tab4:
    st.subheader("📂 Récap par Type Produit")
    
    df_type = get_recap_par_type(campagne)
    
    if not df_type.empty:
        st.dataframe(
            df_type,
            column_config={
                "Type Produit": st.column_config.TextColumn("Type Produit", width="medium"),
                "Lignes": st.column_config.NumberColumn("Lignes", format="%d"),
                "Variétés": st.column_config.NumberColumn("Variétés", format="%d"),
                "Volume Net (T)": st.column_config.NumberColumn("Volume Net (T)", format="%.1f"),
                "Volume Brut (T)": st.column_config.NumberColumn("Volume Brut (T)", format="%.1f"),
                "Hectares": st.column_config.NumberColumn("Hectares", format="%.1f"),
                "Ha Arrondi": st.column_config.NumberColumn("Ha Arrondi", format="%d"),
            },
            use_container_width=True,
            hide_index=True
        )
        
        # Graphique
        st.markdown("#### 📊 Répartition par Type")
        chart_type = df_type[['Type Produit', 'Volume Net (T)']].set_index('Type Produit')
        st.bar_chart(chart_type)
    else:
        st.info("Aucune donnée")

# ==========================================
# TAB 5 : CROISÉ VARIÉTÉ × MOIS
# ==========================================

with tab5:
    st.subheader("📊 Vue Croisée Variété × Mois")
    
    df_croise = get_recap_croise(campagne)
    
    if not df_croise.empty:
        # Choix affichage
        metric_choice = st.radio(
            "Afficher",
            ["Hectares (arrondi)", "Volume Net (T)"],
            horizontal=True
        )
        
        value_col = 'Hectares' if metric_choice == "Hectares (arrondi)" else 'Volume Net'
        
        # Pivot table
        pivot = df_croise.pivot_table(
            index='Variété',
            columns='Mois',
            values=value_col,
            aggfunc='sum',
            fill_value=0
        )
        
        # Réordonner les colonnes par mois_numero
        mois_order = df_croise.drop_duplicates('Mois').sort_values('mois_numero')['Mois'].tolist()
        pivot = pivot.reindex(columns=[m for m in mois_order if m in pivot.columns])
        
        # Ajouter total par variété
        pivot['TOTAL'] = pivot.sum(axis=1)
        
        # Ajouter total par mois
        pivot.loc['TOTAL'] = pivot.sum()
        
        # Afficher
        st.dataframe(
            pivot.style.format("{:.0f}").background_gradient(cmap='YlOrRd', subset=pivot.columns[:-1]),
            use_container_width=True
        )
        
        st.info(f"💡 {len(pivot)-1} variétés × {len(pivot.columns)-1} mois")
    else:
        st.info("Aucune donnée")

# ==========================================
# TAB 6 : BESOINS & COUVERTURE
# ==========================================

with tab6:
    st.subheader("🎯 Besoins & Taux de Couverture")
    st.markdown("*Suivi des affectations producteurs par besoin (Variété × Mois)*")
    
    df_besoins = get_besoins_avec_couverture(campagne)
    
    if not df_besoins.empty:
        # KPIs couverture
        total_besoin = df_besoins['Ha Besoin'].sum()
        total_affecte = df_besoins['Ha Affectés'].sum()
        nb_complets = df_besoins['Complet'].sum()
        nb_total = len(df_besoins)
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("🎯 Besoins", f"{nb_total}")
        
        with col2:
            st.metric("🌾 Ha à affecter", f"{total_besoin:,.0f}")
        
        with col3:
            st.metric("✅ Ha affectés", f"{total_affecte:,.0f}")
        
        with col4:
            taux_global = (total_affecte / total_besoin * 100) if total_besoin > 0 else 0
            st.metric("📊 Couverture globale", f"{taux_global:.1f} %")
        
        st.markdown("---")
        
        # Filtres
        col1, col2 = st.columns(2)
        
        with col1:
            varietes_dispo = ["Toutes"] + sorted(df_besoins['Variété'].unique().tolist())
            filtre_variete = st.selectbox("Filtrer variété", varietes_dispo, key="filtre_var_besoins")
        
        with col2:
            filtre_statut = st.selectbox("Filtrer statut", ["Tous", "Complets", "Incomplets"], key="filtre_statut")
        
        # Appliquer filtres
        df_filtered = df_besoins.copy()
        if filtre_variete != "Toutes":
            df_filtered = df_filtered[df_filtered['Variété'] == filtre_variete]
        if filtre_statut == "Complets":
            df_filtered = df_filtered[df_filtered['Complet'] == True]
        elif filtre_statut == "Incomplets":
            df_filtered = df_filtered[df_filtered['Complet'] == False]
        
        # Masquer colonnes techniques
        df_display = df_filtered.drop(columns=['mois_numero', 'id'], errors='ignore')
        
        # Afficher avec couleurs conditionnelles
        def highlight_couverture(val):
            if isinstance(val, (int, float)):
                if val >= 100:
                    return 'background-color: #c8e6c9'  # Vert clair
                elif val >= 50:
                    return 'background-color: #fff9c4'  # Jaune clair
                else:
                    return 'background-color: #ffcdd2'  # Rouge clair
            return ''
        
        st.dataframe(
            df_display.style.applymap(highlight_couverture, subset=['Couverture %']),
            column_config={
                "Variété": st.column_config.TextColumn("Variété", width="medium"),
                "Mois": st.column_config.TextColumn("Mois", width="small"),
                "Volume Net (T)": st.column_config.NumberColumn("Vol. Net (T)", format="%.1f"),
                "Volume Brut (T)": st.column_config.NumberColumn("Vol. Brut (T)", format="%.1f"),
                "Ha Besoin": st.column_config.NumberColumn("Ha Besoin", format="%d"),
                "Ha Affectés": st.column_config.NumberColumn("Ha Affectés", format="%d"),
                "Couverture %": st.column_config.NumberColumn("Couverture %", format="%.1f"),
                "Complet": st.column_config.CheckboxColumn("Complet"),
            },
            use_container_width=True,
            hide_index=True
        )
        
        st.markdown(f"**{len(df_filtered)} besoin(s)** | ✅ {nb_complets} complets | ⏳ {nb_total - nb_complets} à affecter")
    else:
        st.info("Aucun besoin calculé. Lancez 'Recalculer besoins' dans la page Plan Récolte.")

# ==========================================
# EXPORTS
# ==========================================

st.markdown("---")
st.subheader("📤 Exports")

col1, col2, col3 = st.columns(3)

with col1:
    # Export Excel complet
    if st.button("📥 Export Excel complet", use_container_width=True):
        try:
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                if kpis:
                    pd.DataFrame([kpis]).to_excel(writer, sheet_name='KPIs', index=False)
                
                df_mois = get_recap_par_mois(campagne)
                if not df_mois.empty:
                    df_mois.to_excel(writer, sheet_name='Par Mois', index=False)
                
                df_variete = get_recap_par_variete(campagne)
                if not df_variete.empty:
                    df_variete.to_excel(writer, sheet_name='Par Variété', index=False)
                
                df_marque = get_recap_par_marque(campagne)
                if not df_marque.empty:
                    df_marque.to_excel(writer, sheet_name='Par Marque', index=False)
                
                df_type = get_recap_par_type(campagne)
                if not df_type.empty:
                    df_type.to_excel(writer, sheet_name='Par Type', index=False)
                
                df_besoins = get_besoins_avec_couverture(campagne)
                if not df_besoins.empty:
                    df_besoins.to_excel(writer, sheet_name='Besoins', index=False)
            
            st.download_button(
                "💾 Télécharger Excel",
                buffer.getvalue(),
                f"recaps_plan_recolte_{campagne}.xlsx",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )
        except Exception as e:
            st.error(f"Erreur export : {e}")

with col2:
    # Export besoins CSV
    df_besoins = get_besoins_avec_couverture(campagne)
    if not df_besoins.empty:
        csv = df_besoins.to_csv(index=False).encode('utf-8')
        st.download_button(
            "📥 Besoins CSV",
            csv,
            f"besoins_recolte_{campagne}.csv",
            "text/csv",
            use_container_width=True
        )

with col3:
    # Bouton vers affectations
    st.markdown("""
    <a href="/Affectation_Producteurs" target="_self">
        <button style="width:100%; padding:0.5rem; cursor:pointer;">
            ➡️ Affecter Producteurs
        </button>
    </a>
    """, unsafe_allow_html=True)

show_footer()
