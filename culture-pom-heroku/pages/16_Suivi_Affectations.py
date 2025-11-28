"""
Page 16 - Suivi Affectations
Vue par producteur : qui a été affecté à quoi, récaps par producteur
VERSION MODIFIÉE - Support hectares décimaux + édition dans Détail Producteur
"""
import streamlit as st
import pandas as pd
from database import get_connection
from components import show_footer
from auth import is_authenticated, has_access, can_edit, can_delete, get_current_username
import io

st.set_page_config(page_title="Suivi Affectations - Culture Pom", page_icon="📋", layout="wide")

# CSS
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
            # ✅ CORRIGÉ : RealDictCursor retourne des dictionnaires
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
            # Convertir colonnes numériques
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
        
        cursor.execute("""
            SELECT 
                a.id,
                a.besoin_id,
                a.variete,
                a.mois,
                b.mois_numero,
                a.hectares_affectes,
                b.total_hectares_arrondi as ha_besoin_total,
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
            # ✅ CORRIGÉ : RealDictCursor retourne des dictionnaires
            df = pd.DataFrame(rows)
            df = df.rename(columns={
                'id': 'id',
                'besoin_id': 'besoin_id',
                'variete': 'Variété',
                'mois': 'Mois',
                'mois_numero': 'mois_numero',
                'hectares_affectes': 'Hectares',
                'ha_besoin_total': 'Ha Besoin Total',
                'notes': 'Notes',
                'created_at': 'Date'
            })
            # Convertir colonnes numériques
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
            # ✅ CORRIGÉ : RealDictCursor retourne des dictionnaires
            df = pd.DataFrame(rows)
            df = df.rename(columns={
                'producteur': 'Producteur',
                'variete': 'Variété',
                'hectares': 'Hectares'
            })
            # Convertir colonnes numériques
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
            # ✅ CORRIGÉ : RealDictCursor retourne des dictionnaires
            df = pd.DataFrame(rows)
            df = df.rename(columns={
                'producteur': 'Producteur',
                'mois': 'Mois',
                'mois_numero': 'mois_numero',
                'hectares': 'Hectares'
            })
            # Convertir colonnes numériques
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
    """KPIs de suivi"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Producteurs affectés
        cursor.execute("""
            SELECT COUNT(DISTINCT producteur_id) as nb FROM plans_recolte_affectations WHERE campagne = %s
        """, (campagne,))
        # ✅ CORRIGÉ : Accès par nom de colonne
        nb_producteurs = cursor.fetchone()['nb']
        
        # Total affectations
        cursor.execute("""
            SELECT COUNT(*) as nb, SUM(hectares_affectes) as total FROM plans_recolte_affectations WHERE campagne = %s
        """, (campagne,))
        row = cursor.fetchone()
        # ✅ CORRIGÉ : Accès par nom de colonne
        nb_affectations = row['nb']
        total_ha = row['total'] or 0
        
        # Variétés couvertes
        cursor.execute("""
            SELECT COUNT(DISTINCT variete) as nb FROM plans_recolte_affectations WHERE campagne = %s
        """, (campagne,))
        # ✅ CORRIGÉ : Accès par nom de colonne
        nb_varietes = cursor.fetchone()['nb']
        
        # Moyenne par producteur
        moyenne = total_ha / nb_producteurs if nb_producteurs > 0 else 0
        
        cursor.close()
        conn.close()
        
        return {
            'nb_producteurs': nb_producteurs,
            'nb_affectations': nb_affectations,
            'total_ha': float(total_ha),  # ✅ MODIFIÉ : float() pour décimaux
            'nb_varietes': nb_varietes,
            'moyenne_ha': float(moyenne)
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
        
        # ✅ CORRIGÉ : Accès par nom de colonne
        return [(row['id'], row['nom']) for row in rows]
    except:
        return []


# ==========================================
# FONCTIONS D'ÉDITION (NOUVELLES)
# ==========================================

def modifier_affectation(affectation_id, hectares, notes):
    """Modifie une affectation"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        username = st.session_state.get('username', 'system')
        
        cursor.execute("""
            UPDATE plans_recolte_affectations 
            SET hectares_affectes = %s, notes = %s, updated_by = %s, updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
        """, (hectares, notes, username, affectation_id))
        
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

# KPIs
kpis = get_kpis_suivi(campagne)

if kpis:
    col1, col2, col3, col4, col5 = st.columns(5)
    
    with col1:
        st.metric("👨‍🌾 Producteurs", kpis['nb_producteurs'])
    
    with col2:
        st.metric("📝 Affectations", kpis['nb_affectations'])
    
    with col3:
        # ✅ MODIFIÉ : Format décimal
        st.metric("🌾 Total Ha", f"{kpis['total_ha']:,.1f}")
    
    with col4:
        st.metric("🌱 Variétés", kpis['nb_varietes'])
    
    with col5:
        # ✅ MODIFIÉ : Format décimal
        st.metric("📊 Moy./Prod.", f"{kpis['moyenne_ha']:.1f} ha")

st.markdown("---")

# ==========================================
# ONGLETS
# ==========================================

tab1, tab2, tab3, tab4 = st.tabs([
    "👨‍🌾 Par Producteur",
    "🌱 Producteur × Variété",
    "📅 Producteur × Mois",
    "📋 Détail Producteur"
])

# ==========================================
# TAB 1 : RÉCAP PAR PRODUCTEUR
# ==========================================

with tab1:
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
                # ✅ MODIFIÉ : Format décimal
                "Total Ha": st.column_config.NumberColumn("Total Ha", format="%.1f"),
            },
            use_container_width=True,
            hide_index=True
        )
        
        # Totaux - ✅ MODIFIÉ : Format décimal
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

with tab2:
    st.subheader("🌱 Tableau Producteur × Variété")
    
    df_cross = get_recap_par_variete_producteur(campagne)
    
    if not df_cross.empty:
        # Pivot
        pivot = df_cross.pivot_table(
            index='Producteur',
            columns='Variété',
            values='Hectares',
            aggfunc='sum',
            fill_value=0
        )
        
        # Ajouter totaux
        pivot['TOTAL'] = pivot.sum(axis=1)
        pivot.loc['TOTAL'] = pivot.sum()
        
        # Trier par total décroissant
        pivot = pivot.sort_values('TOTAL', ascending=False)
        
        # ✅ MODIFIÉ : Format décimal
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

with tab3:
    st.subheader("📅 Tableau Producteur × Mois")
    
    df_mois = get_recap_par_mois_producteur(campagne)
    
    if not df_mois.empty:
        # Pivot
        pivot = df_mois.pivot_table(
            index='Producteur',
            columns='Mois',
            values='Hectares',
            aggfunc='sum',
            fill_value=0
        )
        
        # Réordonner colonnes par mois_numero
        mois_order = df_mois.drop_duplicates('Mois').sort_values('mois_numero')['Mois'].tolist()
        pivot = pivot.reindex(columns=[m for m in mois_order if m in pivot.columns])
        
        # Ajouter totaux
        pivot['TOTAL'] = pivot.sum(axis=1)
        pivot.loc['TOTAL'] = pivot.sum()
        
        # Trier par total décroissant
        pivot = pivot.sort_values('TOTAL', ascending=False)
        
        # ✅ MODIFIÉ : Format décimal
        st.dataframe(
            pivot.style.format("{:.1f}").background_gradient(cmap='Blues', subset=pivot.columns[:-1]),
            use_container_width=True
        )
    else:
        st.info("Aucune donnée")

# ==========================================
# TAB 4 : DÉTAIL PRODUCTEUR (AVEC ÉDITION)
# ==========================================

with tab4:
    st.subheader("📋 Détail par Producteur")
    
    producteurs = get_producteurs_liste(campagne)
    
    if producteurs:
        # Sélecteur producteur
        prod_options = ["-- Sélectionner --"] + [f"{p[1]}" for p in producteurs]
        selected_prod = st.selectbox("Producteur", prod_options, key="detail_prod")
        
        if selected_prod != "-- Sélectionner --":
            prod_idx = prod_options.index(selected_prod) - 1
            producteur_id = producteurs[prod_idx][0]
            producteur_nom = producteurs[prod_idx][1]
            
            # Charger affectations
            df_detail = get_affectations_producteur(campagne, producteur_id)
            
            if not df_detail.empty:
                # KPIs producteur - ✅ MODIFIÉ : Format décimal
                total_ha = df_detail['Hectares'].sum()
                nb_varietes = df_detail['Variété'].nunique()
                nb_mois = df_detail['Mois'].nunique()
                
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    st.metric("🌾 Total Ha", f"{total_ha:,.1f}")
                
                with col2:
                    st.metric("🌱 Variétés", nb_varietes)
                
                with col3:
                    st.metric("📅 Mois", nb_mois)
                
                st.markdown("---")
                
                # ==========================================
                # AFFICHAGE AVEC ÉDITION
                # ==========================================
                
                st.markdown("#### 📝 Affectations")
                
                if CAN_EDIT:
                    st.info("💡 Cliquez sur ✏️ pour modifier ou 🗑️ pour supprimer une affectation")
                
                for idx, row in df_detail.iterrows():
                    col1, col2, col3, col4, col5 = st.columns([2, 1, 1, 0.5, 0.5])
                    
                    with col1:
                        st.markdown(f"**{row['Variété']}** - {row['Mois']}")
                        if row['Notes']:
                            st.caption(f"📝 {row['Notes']}")
                    
                    with col2:
                        # ✅ MODIFIÉ : Format décimal
                        st.metric("Ha", f"{row['Hectares']:.1f}", label_visibility="collapsed")
                    
                    with col3:
                        if row['Ha Besoin Total']:
                            st.caption(f"Besoin: {row['Ha Besoin Total']:.1f} ha")
                    
                    with col4:
                        if CAN_EDIT:
                            if st.button("✏️", key=f"edit16_{row['id']}", help="Modifier"):
                                st.session_state[f'editing16_{row["id"]}'] = True
                                st.rerun()
                    
                    with col5:
                        if CAN_DELETE:
                            if st.button("🗑️", key=f"del16_{row['id']}", help="Supprimer"):
                                success, msg = supprimer_affectation(row['id'])
                                if success:
                                    st.success(msg)
                                    st.rerun()
                                else:
                                    st.error(msg)
                    
                    # Formulaire modification si édition active
                    if st.session_state.get(f'editing16_{row["id"]}', False):
                        with st.container():
                            st.markdown("---")
                            col1, col2 = st.columns(2)
                            
                            with col1:
                                # ✅ MODIFIÉ : Décimaux par pas de 0.5
                                new_ha = st.number_input(
                                    "Hectares",
                                    min_value=0.5,
                                    value=float(row['Hectares']),
                                    step=0.5,
                                    format="%.1f",
                                    key=f"edit16_ha_{row['id']}"
                                )
                            
                            with col2:
                                new_notes = st.text_input(
                                    "Notes",
                                    value=row['Notes'] or "",
                                    key=f"edit16_notes_{row['id']}"
                                )
                            
                            col1, col2 = st.columns(2)
                            
                            with col1:
                                if st.button("💾 Enregistrer", key=f"save16_edit_{row['id']}", type="primary"):
                                    success, msg = modifier_affectation(row['id'], new_ha, new_notes)
                                    if success:
                                        st.success(msg)
                                        st.session_state.pop(f'editing16_{row["id"]}', None)
                                        st.rerun()
                                    else:
                                        st.error(msg)
                            
                            with col2:
                                if st.button("❌ Annuler", key=f"cancel16_edit_{row['id']}"):
                                    st.session_state.pop(f'editing16_{row["id"]}', None)
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
    # Export Excel complet
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
    # Export CSV producteurs
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
    # Lien retour affectations
    st.markdown("""
    <a href="/Affectation_Producteurs" target="_self">
        <button style="width:100%; padding:0.5rem; cursor:pointer;">
            ⬅️ Retour Affectations
        </button>
    </a>
    """, unsafe_allow_html=True)

show_footer()
