"""
Page 16 - Suivi Affectations
Vue par producteur : qui a été affecté à quoi, récaps par producteur
VERSION MODIFIÉE - Type contrat RÉCOLTE/HIVER + Police agrandie + Conservation onglet
"""
import streamlit as st
import pandas as pd
from database import get_connection
from components import show_footer
from auth import require_access, can_edit, can_delete, get_current_username
import io

st.set_page_config(page_title="Suivi Affectations - Culture Pom", page_icon="📋", layout="wide")

# CSS - Police agrandie pour hectares
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
    .producteur-card {
        background: linear-gradient(135deg, #e8f5e9 0%, #c8e6c9 100%);
        padding: 1rem;
        border-radius: 0.5rem;
        margin: 0.5rem 0;
        border-left: 4px solid #4CAF50;
    }
    /* ✅ NOUVEAU : Style pour les hectares agrandis */
    .big-hectares {
        font-size: 2rem !important;
        font-weight: bold !important;
        color: #2E7D32 !important;
    }
    .besoin-label {
        font-size: 1.1rem !important;
        color: #555 !important;
        font-weight: 500 !important;
    }
    /* Style pour les badges contrat */
    .badge-recolte {
        background-color: #4CAF50;
        color: white;
        padding: 0.3rem 0.6rem;
        border-radius: 0.3rem;
        font-size: 0.85rem;
        font-weight: bold;
    }
    .badge-hiver {
        background-color: #2196F3;
        color: white;
        padding: 0.3rem 0.6rem;
        border-radius: 0.3rem;
        font-size: 0.85rem;
        font-weight: bold;
    }
    /* ✅ NOUVEAU : Style pour radio horizontal comme onglets */
    div[data-testid="stHorizontalBlock"] > div[data-testid="column"] > div > div > div > div[role="radiogroup"] {
        gap: 0 !important;
    }
    div[data-testid="stHorizontalBlock"] > div[data-testid="column"] > div > div > div > div[role="radiogroup"] > label {
        background-color: #f0f2f6;
        padding: 0.5rem 1rem;
        border: 1px solid #ddd;
        margin: 0 !important;
        cursor: pointer;
    }
    div[data-testid="stHorizontalBlock"] > div[data-testid="column"] > div > div > div > div[role="radiogroup"] > label:first-child {
        border-radius: 0.5rem 0 0 0.5rem;
    }
    div[data-testid="stHorizontalBlock"] > div[data-testid="column"] > div > div > div > div[role="radiogroup"] > label:last-child {
        border-radius: 0 0.5rem 0.5rem 0;
    }
    div[data-testid="stHorizontalBlock"] > div[data-testid="column"] > div > div > div > div[role="radiogroup"] > label[data-checked="true"] {
        background-color: #4CAF50;
        color: white;
        border-color: #4CAF50;
    }
</style>
""", unsafe_allow_html=True)

# Vérification authentification et permissions RBAC
require_access("PLANS_RECOLTE")

# Permissions utilisateur
CAN_EDIT = can_edit("PLANS_RECOLTE")
CAN_DELETE = can_delete("PLANS_RECOLTE")

st.title("📋 Suivi Affectations")
st.markdown("*Vue par producteur et récapitulatifs des affectations*")
st.markdown("---")

# ==========================================
# FONCTIONS - CORRIGÉES POUR RealDictCursor
# ==========================================

@st.cache_data(ttl=60)
def get_recap_par_producteur(campagne):
    """Récap affectations par producteur"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                p.id,
                p.code_producteur,
                p.nom,
                p.ville,
                p.departement,
                COUNT(DISTINCT a.variete) as nb_varietes,
                COUNT(a.id) as nb_affectations,
                SUM(a.hectares_affectes) as total_hectares
            FROM plans_recolte_affectations a
            JOIN ref_producteurs p ON a.producteur_id = p.id
            WHERE a.campagne = %s
            GROUP BY p.id, p.code_producteur, p.nom, p.ville, p.departement
            ORDER BY SUM(a.hectares_affectes) DESC
        """, (campagne,))
        
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        
        if rows:
            df = pd.DataFrame(rows)
            df = df.rename(columns={
                'id': 'id',
                'code_producteur': 'Code',
                'nom': 'Producteur',
                'ville': 'Ville',
                'departement': 'Dept',
                'nb_varietes': 'Variétés',
                'nb_affectations': 'Affectations',
                'total_hectares': 'Total Ha'
            })
            for col in ['Variétés', 'Affectations', 'Total Ha']:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
            return df
        return pd.DataFrame()
    except Exception as e:
        st.error(f"Erreur : {e}")
        return pd.DataFrame()


def get_affectations_producteur(campagne, producteur_id):
    """Détail affectations pour un producteur - SANS CACHE pour édition"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # ✅ MODIFIÉ : Ajout type_contrat
        cursor.execute("""
            SELECT 
                a.id,
                a.besoin_id,
                a.variete,
                a.mois,
                b.mois_numero,
                a.hectares_affectes,
                b.total_hectares_arrondi as ha_besoin_total,
                COALESCE(a.type_contrat, 'RÉCOLTE') as type_contrat,
                a.notes,
                a.created_at
            FROM plans_recolte_affectations a
            LEFT JOIN plans_recolte_besoins b ON a.besoin_id = b.id
            WHERE a.campagne = %s AND a.producteur_id = %s
            ORDER BY b.mois_numero, a.variete
        """, (campagne, producteur_id))
        
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        
        if rows:
            df = pd.DataFrame(rows)
            df = df.rename(columns={
                'id': 'id',
                'besoin_id': 'besoin_id',
                'variete': 'Variété',
                'mois': 'Mois',
                'mois_numero': 'mois_numero',
                'hectares_affectes': 'Hectares',
                'ha_besoin_total': 'Ha Besoin Total',
                'type_contrat': 'Type Contrat',
                'notes': 'Notes',
                'created_at': 'Date'
            })
            for col in ['Hectares', 'Ha Besoin Total']:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
            return df
        return pd.DataFrame()
    except Exception as e:
        st.error(f"Erreur : {e}")
        return pd.DataFrame()


@st.cache_data(ttl=60)
def get_recap_par_variete_producteur(campagne):
    """Tableau croisé Producteur × Variété"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                p.nom as producteur,
                a.variete,
                SUM(a.hectares_affectes) as hectares
            FROM plans_recolte_affectations a
            JOIN ref_producteurs p ON a.producteur_id = p.id
            WHERE a.campagne = %s
            GROUP BY p.nom, a.variete
            ORDER BY p.nom, a.variete
        """, (campagne,))
        
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        
        if rows:
            df = pd.DataFrame(rows)
            df = df.rename(columns={
                'producteur': 'Producteur',
                'variete': 'Variété',
                'hectares': 'Hectares'
            })
            if 'Hectares' in df.columns:
                df['Hectares'] = pd.to_numeric(df['Hectares'], errors='coerce')
            return df
        return pd.DataFrame()
    except Exception as e:
        st.error(f"Erreur : {e}")
        return pd.DataFrame()


@st.cache_data(ttl=60)
def get_recap_par_mois_producteur(campagne):
    """Tableau croisé Producteur × Mois"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                p.nom as producteur,
                a.mois,
                b.mois_numero,
                SUM(a.hectares_affectes) as hectares
            FROM plans_recolte_affectations a
            JOIN ref_producteurs p ON a.producteur_id = p.id
            LEFT JOIN plans_recolte_besoins b ON a.besoin_id = b.id
            WHERE a.campagne = %s
            GROUP BY p.nom, a.mois, b.mois_numero
            ORDER BY p.nom, b.mois_numero
        """, (campagne,))
        
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        
        if rows:
            df = pd.DataFrame(rows)
            df = df.rename(columns={
                'producteur': 'Producteur',
                'mois': 'Mois',
                'mois_numero': 'mois_numero',
                'hectares': 'Hectares'
            })
            for col in ['mois_numero', 'Hectares']:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
            return df
        return pd.DataFrame()
    except Exception as e:
        st.error(f"Erreur : {e}")
        return pd.DataFrame()


@st.cache_data(ttl=60)
def get_kpis_suivi(campagne):
    """KPIs de suivi - ✅ MODIFIÉ : Ajout KPIs par type contrat"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Producteurs affectés
        cursor.execute("""
            SELECT COUNT(DISTINCT producteur_id) as nb FROM plans_recolte_affectations WHERE campagne = %s
        """, (campagne,))
        nb_producteurs = cursor.fetchone()['nb']
        
        # Total affectations
        cursor.execute("""
            SELECT COUNT(*) as nb, SUM(hectares_affectes) as total FROM plans_recolte_affectations WHERE campagne = %s
        """, (campagne,))
        row = cursor.fetchone()
        nb_affectations = row['nb']
        total_ha = row['total'] or 0
        
        # Variétés couvertes
        cursor.execute("""
            SELECT COUNT(DISTINCT variete) as nb FROM plans_recolte_affectations WHERE campagne = %s
        """, (campagne,))
        nb_varietes = cursor.fetchone()['nb']
        
        # ✅ NOUVEAU : Hectares par type de contrat
        cursor.execute("""
            SELECT 
                COALESCE(type_contrat, 'RÉCOLTE') as type_contrat,
                SUM(hectares_affectes) as total_ha
            FROM plans_recolte_affectations 
            WHERE campagne = %s
            GROUP BY COALESCE(type_contrat, 'RÉCOLTE')
        """, (campagne,))
        
        ha_recolte = 0
        ha_hiver = 0
        for row in cursor.fetchall():
            if row['type_contrat'] == 'RÉCOLTE':
                ha_recolte = float(row['total_ha'] or 0)
            elif row['type_contrat'] == 'HIVER':
                ha_hiver = float(row['total_ha'] or 0)
        
        # Moyenne par producteur
        moyenne = total_ha / nb_producteurs if nb_producteurs > 0 else 0
        
        cursor.close()
        conn.close()
        
        return {
            'nb_producteurs': nb_producteurs,
            'nb_affectations': nb_affectations,
            'total_ha': float(total_ha),
            'nb_varietes': nb_varietes,
            'moyenne_ha': float(moyenne),
            'ha_recolte': ha_recolte,
            'ha_hiver': ha_hiver
        }
    except:
        return None


def get_producteurs_liste(campagne):
    """Liste producteurs avec affectations"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT DISTINCT p.id, p.nom
            FROM plans_recolte_affectations a
            JOIN ref_producteurs p ON a.producteur_id = p.id
            WHERE a.campagne = %s
            ORDER BY p.nom
        """, (campagne,))
        
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        
        return [(row['id'], row['nom']) for row in rows]
    except:
        return []


# ==========================================
# FONCTIONS D'ÉDITION - ✅ MODIFIÉ : Ajout type_contrat
# ==========================================

def modifier_affectation(affectation_id, hectares, type_contrat, notes):
    """Modifie une affectation - ✅ MODIFIÉ : Ajout type_contrat"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        username = st.session_state.get('username', 'system')
        
        cursor.execute("""
            UPDATE plans_recolte_affectations 
            SET hectares_affectes = %s, type_contrat = %s, notes = %s, updated_by = %s, updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
        """, (hectares, type_contrat, notes, username, affectation_id))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        # Vider le cache pour rafraîchir les données
        st.cache_data.clear()
        
        return True, "✅ Affectation modifiée"
    except Exception as e:
        return False, f"❌ Erreur : {e}"


def supprimer_affectation(affectation_id):
    """Supprime une affectation"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute("DELETE FROM plans_recolte_affectations WHERE id = %s", (affectation_id,))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        # Vider le cache pour rafraîchir les données
        st.cache_data.clear()
        
        return True, "✅ Affectation supprimée"
    except Exception as e:
        return False, f"❌ Erreur : {e}"


# ==========================================
# SÉLECTEUR CAMPAGNE + KPIs
# ==========================================

col1, col2 = st.columns([1, 4])
with col1:
    campagne = st.selectbox("Campagne", [2026, 2025, 2027], index=0, key="campagne_suivi")

with col2:
    if st.button("🔄 Rafraîchir"):
        st.cache_data.clear()
        st.rerun()

# KPIs - ✅ MODIFIÉ : Ajout KPIs par type contrat
kpis = get_kpis_suivi(campagne)

if kpis:
    # Ligne 1 : KPIs généraux
    col1, col2, col3, col4, col5 = st.columns(5)
    
    with col1:
        st.metric("👨‍🌾 Producteurs", kpis['nb_producteurs'])
    
    with col2:
        st.metric("📝 Affectations", kpis['nb_affectations'])
    
    with col3:
        st.metric("🌾 Total Ha", f"{kpis['total_ha']:,.1f}")
    
    with col4:
        st.metric("🌱 Variétés", kpis['nb_varietes'])
    
    with col5:
        st.metric("📊 Moy./Prod.", f"{kpis['moyenne_ha']:.1f} ha")
    
    # ✅ NOUVEAU : Ligne 2 - KPIs par type de contrat
    st.markdown("---")
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("🌾 Ha RÉCOLTE", f"{kpis['ha_recolte']:,.1f}", help="Récupération à la récolte")
    
    with col2:
        st.metric("❄️ Ha HIVER", f"{kpis['ha_hiver']:,.1f}", help="Récupération en saison")
    
    with col3:
        # Pourcentage récolte
        pct_recolte = (kpis['ha_recolte'] / kpis['total_ha'] * 100) if kpis['total_ha'] > 0 else 0
        st.metric("📊 % Récolte", f"{pct_recolte:.0f}%")
    
    with col4:
        # Pourcentage hiver
        pct_hiver = (kpis['ha_hiver'] / kpis['total_ha'] * 100) if kpis['total_ha'] > 0 else 0
        st.metric("📊 % Hiver", f"{pct_hiver:.0f}%")

st.markdown("---")

# ==========================================
# ONGLETS - ✅ CORRIGÉ : st.radio au lieu de st.tabs pour conserver l'état
# ==========================================

# Initialiser l'onglet actif dans session_state
if 'onglet_actif_16' not in st.session_state:
    st.session_state.onglet_actif_16 = "👨‍🌾 Par Producteur"

# Radio horizontal qui ressemble à des onglets
onglet_selectionne = st.radio(
    "Navigation",
    options=[
        "👨‍🌾 Par Producteur",
        "🌱 Producteur × Variété",
        "📅 Producteur × Mois",
        "📋 Détail Producteur"
    ],
    index=[
        "👨‍🌾 Par Producteur",
        "🌱 Producteur × Variété",
        "📅 Producteur × Mois",
        "📋 Détail Producteur"
    ].index(st.session_state.onglet_actif_16),
    horizontal=True,
    key="nav_onglets_16",
    label_visibility="collapsed"
)

# Mémoriser l'onglet sélectionné
st.session_state.onglet_actif_16 = onglet_selectionne

st.markdown("---")

# ==========================================
# TAB 1 : RÉCAP PAR PRODUCTEUR
# ==========================================

if onglet_selectionne == "👨‍🌾 Par Producteur":
    st.subheader("👨‍🌾 Récap par Producteur")
    
    df_prod = get_recap_par_producteur(campagne)
    
    if not df_prod.empty:
        # Masquer colonne id
        df_display = df_prod.drop(columns=['id'])
        
        st.dataframe(
            df_display,
            column_config={
                "Code": st.column_config.TextColumn("Code", width="small"),
                "Producteur": st.column_config.TextColumn("Producteur", width="large"),
                "Ville": st.column_config.TextColumn("Ville", width="medium"),
                "Dept": st.column_config.TextColumn("Dept", width="small"),
                "Variétés": st.column_config.NumberColumn("Variétés", format="%d"),
                "Affectations": st.column_config.NumberColumn("Affectations", format="%d"),
                "Total Ha": st.column_config.NumberColumn("Total Ha", format="%.1f"),
            },
            use_container_width=True,
            hide_index=True
        )
        
        st.markdown(f"""
        **Totaux :** {len(df_prod)} producteurs | 
        {df_prod['Affectations'].sum()} affectations | 
        {df_prod['Total Ha'].sum():,.1f} ha
        """)
        
        # Top 10
        st.markdown("#### 🏆 Top 10 Producteurs (hectares)")
        top10 = df_prod.head(10)[['Producteur', 'Total Ha']].set_index('Producteur')
        st.bar_chart(top10)
    else:
        st.info("Aucune affectation pour cette campagne")

# ==========================================
# TAB 2 : PRODUCTEUR × VARIÉTÉ
# ==========================================

elif onglet_selectionne == "🌱 Producteur × Variété":
    st.subheader("🌱 Tableau Producteur × Variété")
    
    df_cross = get_recap_par_variete_producteur(campagne)
    
    if not df_cross.empty:
        pivot = df_cross.pivot_table(
            index='Producteur',
            columns='Variété',
            values='Hectares',
            aggfunc='sum',
            fill_value=0
        )
        
        pivot['TOTAL'] = pivot.sum(axis=1)
        pivot.loc['TOTAL'] = pivot.sum()
        pivot = pivot.sort_values('TOTAL', ascending=False)
        
        st.dataframe(
            pivot.style.format("{:.1f}").background_gradient(cmap='Greens', subset=pivot.columns[:-1]),
            use_container_width=True
        )
        
        st.info(f"💡 {len(pivot)-1} producteurs × {len(pivot.columns)-1} variétés")
    else:
        st.info("Aucune donnée")

# ==========================================
# TAB 3 : PRODUCTEUR × MOIS
# ==========================================

elif onglet_selectionne == "📅 Producteur × Mois":
    st.subheader("📅 Tableau Producteur × Mois")
    
    df_mois = get_recap_par_mois_producteur(campagne)
    
    if not df_mois.empty:
        pivot = df_mois.pivot_table(
            index='Producteur',
            columns='Mois',
            values='Hectares',
            aggfunc='sum',
            fill_value=0
        )
        
        mois_order = df_mois.drop_duplicates('Mois').sort_values('mois_numero')['Mois'].tolist()
        pivot = pivot.reindex(columns=[m for m in mois_order if m in pivot.columns])
        
        pivot['TOTAL'] = pivot.sum(axis=1)
        pivot.loc['TOTAL'] = pivot.sum()
        pivot = pivot.sort_values('TOTAL', ascending=False)
        
        st.dataframe(
            pivot.style.format("{:.1f}").background_gradient(cmap='Blues', subset=pivot.columns[:-1]),
            use_container_width=True
        )
    else:
        st.info("Aucune donnée")

# ==========================================
# TAB 4 : DÉTAIL PRODUCTEUR (AVEC ÉDITION)
# ==========================================

elif onglet_selectionne == "📋 Détail Producteur":
    st.subheader("📋 Détail par Producteur")
    
    producteurs = get_producteurs_liste(campagne)
    
    if producteurs:
        # ✅ MODIFIÉ : Mémoriser le producteur sélectionné
        if 'selected_producteur_index' not in st.session_state:
            st.session_state.selected_producteur_index = 0
        
        prod_options = ["-- Sélectionner --"] + [f"{p[1]}" for p in producteurs]
        selected_prod = st.selectbox(
            "Producteur", 
            prod_options, 
            index=st.session_state.selected_producteur_index,
            key="detail_prod"
        )
        
        # Mémoriser l'index sélectionné
        if selected_prod != "-- Sélectionner --":
            st.session_state.selected_producteur_index = prod_options.index(selected_prod)
        
        if selected_prod != "-- Sélectionner --":
            prod_idx = prod_options.index(selected_prod) - 1
            producteur_id = producteurs[prod_idx][0]
            producteur_nom = producteurs[prod_idx][1]
            
            # Charger affectations
            df_detail = get_affectations_producteur(campagne, producteur_id)
            
            if not df_detail.empty:
                # KPIs producteur
                total_ha = df_detail['Hectares'].sum()
                nb_varietes = df_detail['Variété'].nunique()
                nb_mois = df_detail['Mois'].nunique()
                
                # ✅ NOUVEAU : Comptage par type contrat
                ha_recolte_prod = df_detail[df_detail['Type Contrat'] == 'RÉCOLTE']['Hectares'].sum()
                ha_hiver_prod = df_detail[df_detail['Type Contrat'] == 'HIVER']['Hectares'].sum()
                
                col1, col2, col3, col4, col5 = st.columns(5)
                
                with col1:
                    st.metric("🌾 Total Ha", f"{total_ha:,.1f}")
                
                with col2:
                    st.metric("🌱 Variétés", nb_varietes)
                
                with col3:
                    st.metric("📅 Mois", nb_mois)
                
                with col4:
                    st.metric("🌾 Récolte", f"{ha_recolte_prod:,.1f} ha")
                
                with col5:
                    st.metric("❄️ Hiver", f"{ha_hiver_prod:,.1f} ha")
                
                st.markdown("---")
                
                # ==========================================
                # AFFICHAGE AVEC ÉDITION - ✅ MODIFIÉ
                # ==========================================
                
                st.markdown("#### 📝 Affectations")
                
                if CAN_EDIT:
                    st.info("💡 Cliquez sur ✏️ pour modifier ou 🗑️ pour supprimer une affectation")
                
                for idx, row in df_detail.iterrows():
                    # ✅ MODIFIÉ : Nouvelle disposition avec type contrat
                    col1, col2, col3, col4, col5, col6 = st.columns([1, 2.5, 1.2, 1.3, 0.5, 0.5])
                    
                    # Badge type contrat
                    with col1:
                        if row['Type Contrat'] == 'HIVER':
                            st.markdown(f'<span class="badge-hiver">❄️ HIVER</span>', unsafe_allow_html=True)
                        else:
                            st.markdown(f'<span class="badge-recolte">🌾 RÉCOLTE</span>', unsafe_allow_html=True)
                    
                    with col2:
                        st.markdown(f"**{row['Variété']}** - {row['Mois']}")
                        if row['Notes']:
                            st.caption(f"📝 {row['Notes']}")
                    
                    # ✅ MODIFIÉ : Hectares plus gros
                    with col3:
                        st.markdown(f'<span class="big-hectares">{row["Hectares"]:.1f}</span>', unsafe_allow_html=True)
                    
                    # ✅ MODIFIÉ : Besoin plus visible
                    with col4:
                        if row['Ha Besoin Total']:
                            st.markdown(f'<span class="besoin-label">Besoin: <b>{row["Ha Besoin Total"]:.1f}</b> ha</span>', unsafe_allow_html=True)
                    
                    with col5:
                        if CAN_EDIT:
                            if st.button("✏️", key=f"edit16_{row['id']}", help="Modifier"):
                                st.session_state[f'editing16_{row["id"]}'] = True
                                st.session_state.onglet_actif_16 = "📋 Détail Producteur"  # ✅ FORCER ONGLET
                                st.rerun()
                    
                    with col6:
                        if CAN_DELETE:
                            if st.button("🗑️", key=f"del16_{row['id']}", help="Supprimer"):
                                success, msg = supprimer_affectation(row['id'])
                                if success:
                                    st.success(msg)
                                    st.session_state.onglet_actif_16 = "📋 Détail Producteur"  # ✅ FORCER ONGLET
                                    st.rerun()
                                else:
                                    st.error(msg)
                    
                    # Formulaire modification si édition active
                    if st.session_state.get(f'editing16_{row["id"]}', False):
                        with st.container():
                            st.markdown("---")
                            col1, col2, col3 = st.columns(3)
                            
                            with col1:
                                new_ha = st.number_input(
                                    "Hectares",
                                    min_value=0.5,
                                    value=float(row['Hectares']),
                                    step=0.5,
                                    format="%.1f",
                                    key=f"edit16_ha_{row['id']}"
                                )
                            
                            with col2:
                                # ✅ NOUVEAU : Dropdown type contrat
                                type_options = ['RÉCOLTE', 'HIVER']
                                current_type = row['Type Contrat'] if row['Type Contrat'] in type_options else 'RÉCOLTE'
                                new_type = st.selectbox(
                                    "Type Contrat",
                                    options=type_options,
                                    index=type_options.index(current_type),
                                    key=f"edit16_type_{row['id']}"
                                )
                            
                            with col3:
                                new_notes = st.text_input(
                                    "Notes",
                                    value=row['Notes'] or "",
                                    key=f"edit16_notes_{row['id']}"
                                )
                            
                            col1, col2 = st.columns(2)
                            
                            with col1:
                                if st.button("💾 Enregistrer", key=f"save16_edit_{row['id']}", type="primary"):
                                    # ✅ MODIFIÉ : Passer type_contrat
                                    success, msg = modifier_affectation(row['id'], new_ha, new_type, new_notes)
                                    if success:
                                        st.success(msg)
                                        st.session_state.pop(f'editing16_{row["id"]}', None)
                                        st.session_state.onglet_actif_16 = "📋 Détail Producteur"  # ✅ FORCER ONGLET
                                        st.rerun()
                                    else:
                                        st.error(msg)
                            
                            with col2:
                                if st.button("❌ Annuler", key=f"cancel16_edit_{row['id']}"):
                                    st.session_state.pop(f'editing16_{row["id"]}', None)
                                    st.session_state.onglet_actif_16 = "📋 Détail Producteur"  # ✅ FORCER ONGLET
                                    st.rerun()
                            
                            st.markdown("---")
                    
                    st.markdown("<hr style='margin: 0.3rem 0; border: none; border-top: 1px solid #eee;'>", unsafe_allow_html=True)
                
                # ==========================================
                # RÉCAP PAR VARIÉTÉ
                # ==========================================
                
                st.markdown("#### 🌱 Récap par Variété")
                recap_var = df_detail.groupby('Variété')['Hectares'].sum().reset_index()
                recap_var = recap_var.sort_values('Hectares', ascending=False)
                
                st.bar_chart(recap_var.set_index('Variété'))
                
                # ✅ NOUVEAU : Récap par type contrat
                st.markdown("#### 📊 Récap par Type Contrat")
                recap_type = df_detail.groupby('Type Contrat')['Hectares'].sum().reset_index()
                
                col1, col2 = st.columns(2)
                with col1:
                    st.bar_chart(recap_type.set_index('Type Contrat'))
                with col2:
                    st.dataframe(recap_type, hide_index=True)
                
            else:
                st.info(f"Aucune affectation pour {producteur_nom}")
    else:
        st.info("Aucun producteur avec affectations pour cette campagne")

# ==========================================
# EXPORTS
# ==========================================

st.markdown("---")
st.subheader("📤 Exports")

col1, col2, col3 = st.columns(3)

with col1:
    if st.button("📥 Export Excel complet", use_container_width=True):
        try:
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                df_prod = get_recap_par_producteur(campagne)
                if not df_prod.empty:
                    df_prod.to_excel(writer, sheet_name='Par Producteur', index=False)
                
                df_cross = get_recap_par_variete_producteur(campagne)
                if not df_cross.empty:
                    pivot = df_cross.pivot_table(
                        index='Producteur', columns='Variété', values='Hectares',
                        aggfunc='sum', fill_value=0
                    )
                    pivot.to_excel(writer, sheet_name='Producteur x Variété')
                
                df_mois = get_recap_par_mois_producteur(campagne)
                if not df_mois.empty:
                    pivot_mois = df_mois.pivot_table(
                        index='Producteur', columns='Mois', values='Hectares',
                        aggfunc='sum', fill_value=0
                    )
                    pivot_mois.to_excel(writer, sheet_name='Producteur x Mois')
            
            st.download_button(
                "💾 Télécharger Excel",
                buffer.getvalue(),
                f"suivi_affectations_{campagne}.xlsx",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )
        except Exception as e:
            st.error(f"Erreur export : {e}")

with col2:
    df_prod = get_recap_par_producteur(campagne)
    if not df_prod.empty:
        csv = df_prod.to_csv(index=False).encode('utf-8')
        st.download_button(
            "📥 Producteurs CSV",
            csv,
            f"producteurs_affectations_{campagne}.csv",
            "text/csv",
            use_container_width=True
        )

with col3:
    st.markdown("""
    <a href="/Affectation_Producteurs" target="_self">
        <button style="width:100%; padding:0.5rem; cursor:pointer;">
            ⬅️ Retour Affectations
        </button>
    </a>
    """, unsafe_allow_html=True)

show_footer()
