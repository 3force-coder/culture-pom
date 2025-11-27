"""
Page 15 - Affectation Producteurs
Affecter des hectares (entiers) aux producteurs pour chaque besoin (Variété × Mois)
VERSION CORRIGÉE - Accès dictionnaires pour RealDictCursor
"""
import streamlit as st
import pandas as pd
from database import get_connection
from components import show_footer
from auth import is_authenticated, has_access, can_edit, can_delete, get_current_username
from datetime import datetime

st.set_page_config(page_title="Affectation Producteurs - Culture Pom", page_icon="👨‍🌾", layout="wide")

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
    .affectation-card {
        background-color: #f8f9fa;
        padding: 0.8rem;
        border-radius: 0.5rem;
        margin: 0.3rem 0;
        border-left: 4px solid #4CAF50;
    }
    .besoin-selected {
        background-color: #e3f2fd;
        padding: 1rem;
        border-radius: 0.5rem;
        border: 2px solid #2196F3;
        margin: 0.5rem 0;
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

st.title("👨‍🌾 Affectation Producteurs")
st.markdown("*Affecter des hectares aux producteurs pour chaque besoin (Variété × Mois)*")
st.markdown("---")

# ==========================================
# FONCTIONS - CORRIGÉES POUR RealDictCursor
# ==========================================

def get_besoins(campagne, filtre_statut="Tous", filtre_variete="Toutes"):
    """Récupère les besoins avec filtres"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        query = """
            SELECT 
                id,
                variete,
                mois,
                mois_numero,
                total_volume_net_t,
                total_volume_brut_t,
                total_hectares_arrondi,
                total_hectares_affectes,
                taux_couverture_pct,
                is_complet
            FROM plans_recolte_besoins
            WHERE campagne = %s
        """
        params = [campagne]
        
        if filtre_statut == "Incomplets":
            query += " AND is_complet = FALSE"
        elif filtre_statut == "Complets":
            query += " AND is_complet = TRUE"
        
        if filtre_variete != "Toutes":
            query += " AND variete = %s"
            params.append(filtre_variete)
        
        query += " ORDER BY mois_numero, variete"
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        
        if rows:
            # ✅ CORRIGÉ : RealDictCursor retourne des dictionnaires
            df = pd.DataFrame(rows)
            df = df.rename(columns={
                'id': 'id',
                'variete': 'Variété',
                'mois': 'Mois',
                'mois_numero': 'mois_numero',
                'total_volume_net_t': 'Vol. Net (T)',
                'total_volume_brut_t': 'Vol. Brut (T)',
                'total_hectares_arrondi': 'Ha Besoin',
                'total_hectares_affectes': 'Ha Affectés',
                'taux_couverture_pct': 'Couverture %',
                'is_complet': 'Complet'
            })
            # Convertir colonnes numériques
            for col in ['Vol. Net (T)', 'Vol. Brut (T)', 'Ha Besoin', 'Ha Affectés', 'Couverture %']:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
            return df
        return pd.DataFrame()
    except Exception as e:
        st.error(f"Erreur : {e}")
        return pd.DataFrame()


def get_varietes_besoins(campagne):
    """Liste des variétés avec besoins"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT DISTINCT variete FROM plans_recolte_besoins 
            WHERE campagne = %s ORDER BY variete
        """, (campagne,))
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        # ✅ CORRIGÉ : Accès par nom de colonne
        return [row['variete'] for row in rows]
    except:
        return []


def get_affectations_besoin(besoin_id):
    """Récupère les affectations pour un besoin"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                a.id,
                a.producteur_id,
                p.code_producteur,
                p.nom as producteur_nom,
                a.hectares_affectes,
                a.notes,
                a.created_by,
                a.created_at
            FROM plans_recolte_affectations a
            JOIN ref_producteurs p ON a.producteur_id = p.id
            WHERE a.besoin_id = %s
            ORDER BY a.created_at DESC
        """, (besoin_id,))
        
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        
        if rows:
            # ✅ CORRIGÉ : RealDictCursor retourne des dictionnaires
            df = pd.DataFrame(rows)
            df = df.rename(columns={
                'id': 'id',
                'producteur_id': 'producteur_id',
                'code_producteur': 'Code Producteur',
                'producteur_nom': 'Producteur',
                'hectares_affectes': 'Hectares',
                'notes': 'Notes',
                'created_by': 'Créé par',
                'created_at': 'Date'
            })
            # Convertir colonnes numériques
            if 'Hectares' in df.columns:
                df['Hectares'] = pd.to_numeric(df['Hectares'], errors='coerce')
            return df
        return pd.DataFrame()
    except Exception as e:
        st.error(f"Erreur : {e}")
        return pd.DataFrame()


def get_producteurs_actifs():
    """Liste des producteurs actifs"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, code_producteur, nom, ville, departement
            FROM ref_producteurs
            WHERE is_active = TRUE
            ORDER BY nom
        """)
        
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        
        if rows:
            # ✅ CORRIGÉ : Accès par nom de colonne
            return [
                {
                    'id': row['id'],
                    'code': row['code_producteur'],
                    'nom': row['nom'],
                    'ville': row['ville'],
                    'dept': row['departement'],
                    'display': f"{row['code_producteur']} - {row['nom']} ({row['departement'] or ''})"
                }
                for row in rows
            ]
        return []
    except Exception as e:
        st.error(f"Erreur : {e}")
        return []


def get_besoin_info(besoin_id):
    """Récupère les infos d'un besoin"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT campagne, mois, variete, total_hectares_arrondi, 
                   total_hectares_affectes, taux_couverture_pct
            FROM plans_recolte_besoins
            WHERE id = %s
        """, (besoin_id,))
        
        row = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if row:
            # ✅ CORRIGÉ : Accès par nom de colonne
            return {
                'campagne': row['campagne'],
                'mois': row['mois'],
                'variete': row['variete'],
                'ha_besoin': row['total_hectares_arrondi'],
                'ha_affectes': row['total_hectares_affectes'],
                'couverture': float(row['taux_couverture_pct']) if row['taux_couverture_pct'] else 0
            }
        return None
    except:
        return None


def ajouter_affectation(besoin_id, campagne, mois, variete, producteur_id, hectares, notes=""):
    """Ajoute une affectation"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        username = st.session_state.get('username', 'system')
        
        cursor.execute("""
            INSERT INTO plans_recolte_affectations (
                besoin_id, campagne, mois, variete, producteur_id,
                hectares_affectes, notes, created_by, updated_by
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (besoin_id, campagne, mois, variete, producteur_id, 
              hectares, notes, username, username))
        
        # ✅ CORRIGÉ : Accès par nom de colonne
        new_id = cursor.fetchone()['id']
        conn.commit()
        cursor.close()
        conn.close()
        
        return True, f"✅ Affectation #{new_id} créée ({hectares} ha)"
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
        
        return True, "✅ Affectation supprimée"
    except Exception as e:
        return False, f"❌ Erreur : {e}"


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
        
        return True, "✅ Affectation modifiée"
    except Exception as e:
        return False, f"❌ Erreur : {e}"


def get_kpis_affectations(campagne):
    """KPIs globaux affectations"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                COUNT(*) as nb_besoins,
                SUM(CASE WHEN is_complet THEN 1 ELSE 0 END) as nb_complets,
                SUM(total_hectares_arrondi) as total_besoin,
                SUM(total_hectares_affectes) as total_affectes
            FROM plans_recolte_besoins
            WHERE campagne = %s
        """, (campagne,))
        
        row = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if row:
            # ✅ CORRIGÉ : Accès par nom de colonne
            total_besoin = int(row['total_besoin']) if row['total_besoin'] else 0
            total_affectes = int(row['total_affectes']) if row['total_affectes'] else 0
            return {
                'nb_besoins': row['nb_besoins'],
                'nb_complets': row['nb_complets'] or 0,
                'total_besoin': total_besoin,
                'total_affectes': total_affectes,
                'couverture': (total_affectes / total_besoin * 100) if total_besoin > 0 else 0
            }
        return None
    except:
        return None


# ==========================================
# SÉLECTEUR CAMPAGNE + KPIs
# ==========================================

col1, col2 = st.columns([1, 4])
with col1:
    campagne = st.selectbox("Campagne", [2026, 2025, 2027], index=0, key="campagne_affectation")

# KPIs
kpis = get_kpis_affectations(campagne)

if kpis:
    col1, col2, col3, col4, col5 = st.columns(5)
    
    with col1:
        st.metric("🎯 Besoins", kpis['nb_besoins'])
    
    with col2:
        st.metric("✅ Complets", kpis['nb_complets'])
    
    with col3:
        st.metric("🌾 Ha à affecter", f"{kpis['total_besoin']:,}")
    
    with col4:
        st.metric("👨‍🌾 Ha affectés", f"{kpis['total_affectes']:,}")
    
    with col5:
        color = "normal" if kpis['couverture'] < 50 else ("off" if kpis['couverture'] < 100 else "inverse")
        st.metric("📊 Couverture", f"{kpis['couverture']:.1f} %")

st.markdown("---")

# ==========================================
# SECTION 1 : SÉLECTION BESOIN
# ==========================================

st.subheader("1️⃣ Sélectionner un besoin")

# Filtres
col1, col2, col3 = st.columns([1, 1, 2])

with col1:
    varietes_dispo = ["Toutes"] + get_varietes_besoins(campagne)
    filtre_variete = st.selectbox("Variété", varietes_dispo, key="filtre_var")

with col2:
    filtre_statut = st.selectbox("Statut", ["Tous", "Incomplets", "Complets"], key="filtre_stat")

with col3:
    if st.button("🔄 Rafraîchir", key="refresh_besoins"):
        st.rerun()

# Charger besoins
df_besoins = get_besoins(campagne, filtre_statut, filtre_variete)

if not df_besoins.empty:
    st.markdown(f"**{len(df_besoins)} besoin(s)** - 👇 Cliquez sur une ligne pour la sélectionner")
    
    # Préparer affichage
    df_display = df_besoins.drop(columns=['mois_numero']).copy()
    
    # Ajouter colonne "Reste"
    df_display['Reste'] = df_display['Ha Besoin'] - df_display['Ha Affectés']
    
    # Configuration colonnes
    column_config = {
        "id": None,  # Masquer
        "Variété": st.column_config.TextColumn("Variété", width="medium"),
        "Mois": st.column_config.TextColumn("Mois", width="small"),
        "Vol. Net (T)": st.column_config.NumberColumn("Vol. Net", format="%.0f"),
        "Vol. Brut (T)": st.column_config.NumberColumn("Vol. Brut", format="%.0f"),
        "Ha Besoin": st.column_config.NumberColumn("Ha Besoin", format="%d"),
        "Ha Affectés": st.column_config.NumberColumn("Ha Affectés", format="%d"),
        "Reste": st.column_config.NumberColumn("Reste", format="%d"),
        "Couverture %": st.column_config.ProgressColumn("Couverture", format="%.0f%%", min_value=0, max_value=100),
        "Complet": st.column_config.CheckboxColumn("✓"),
    }
    
    # Tableau avec sélection
    event = st.dataframe(
        df_display,
        column_config=column_config,
        use_container_width=True,
        hide_index=True,
        on_select="rerun",
        selection_mode="single-row",
        key="besoins_table"
    )
    
    # Récupérer sélection
    selected_rows = event.selection.rows if hasattr(event, 'selection') else []
    
    if len(selected_rows) > 0:
        selected_idx = selected_rows[0]
        selected_besoin = df_besoins.iloc[selected_idx]
        besoin_id = int(selected_besoin['id'])
        
        # Stocker en session
        st.session_state['selected_besoin_id'] = besoin_id
        st.session_state['selected_besoin_info'] = {
            'variete': selected_besoin['Variété'],
            'mois': selected_besoin['Mois'],
            'ha_besoin': int(selected_besoin['Ha Besoin']),
            'ha_affectes': int(selected_besoin['Ha Affectés']),
            'reste': int(selected_besoin['Ha Besoin'] - selected_besoin['Ha Affectés'])
        }
else:
    st.info("Aucun besoin pour cette campagne. Lancez 'Recalculer besoins' dans la page Plan Récolte.")
    st.stop()

# ==========================================
# SECTION 2 : DÉTAILS BESOIN SÉLECTIONNÉ
# ==========================================

st.markdown("---")

if 'selected_besoin_id' in st.session_state and st.session_state['selected_besoin_id']:
    besoin_id = st.session_state['selected_besoin_id']
    info = st.session_state.get('selected_besoin_info', {})
    
    st.subheader("2️⃣ Besoin sélectionné")
    
    # Afficher infos besoin
    st.markdown(f"""
    <div class="besoin-selected">
        <h4>🌱 {info.get('variete', '?')} - 📅 {info.get('mois', '?')}</h4>
        <p>
            <strong>Besoin :</strong> {info.get('ha_besoin', 0)} ha | 
            <strong>Affectés :</strong> {info.get('ha_affectes', 0)} ha | 
            <strong>Reste :</strong> {info.get('reste', 0)} ha
        </p>
    </div>
    """, unsafe_allow_html=True)
    
    # ==========================================
    # AFFECTATIONS EXISTANTES
    # ==========================================
    
    st.markdown("#### 👨‍🌾 Affectations actuelles")
    
    df_affectations = get_affectations_besoin(besoin_id)
    
    if not df_affectations.empty:
        for idx, row in df_affectations.iterrows():
            col1, col2, col3, col4 = st.columns([3, 1, 1, 1])
            
            with col1:
                st.markdown(f"**{row['Producteur']}** ({row['Code Producteur']})")
                if row['Notes']:
                    st.caption(f"📝 {row['Notes']}")
            
            with col2:
                st.metric("Hectares", f"{row['Hectares']} ha", label_visibility="collapsed")
            
            with col3:
                if CAN_EDIT:
                    if st.button("✏️", key=f"edit_{row['id']}", help="Modifier"):
                        st.session_state[f'editing_{row["id"]}'] = True
                        st.rerun()
            
            with col4:
                if CAN_EDIT:
                    if st.button("🗑️", key=f"del_{row['id']}", help="Supprimer"):
                        success, msg = supprimer_affectation(row['id'])
                        if success:
                            st.success(msg)
                            st.rerun()
                        else:
                            st.error(msg)
            
            # Formulaire modification si édition active
            if st.session_state.get(f'editing_{row["id"]}', False):
                with st.container():
                    st.markdown("---")
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        new_ha = st.number_input(
                            "Hectares",
                            min_value=1,
                            value=int(row['Hectares']),
                            step=1,
                            key=f"edit_ha_{row['id']}"
                        )
                    
                    with col2:
                        new_notes = st.text_input(
                            "Notes",
                            value=row['Notes'] or "",
                            key=f"edit_notes_{row['id']}"
                        )
                    
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        if st.button("💾 Enregistrer", key=f"save_edit_{row['id']}", type="primary"):
                            success, msg = modifier_affectation(row['id'], new_ha, new_notes)
                            if success:
                                st.success(msg)
                                st.session_state.pop(f'editing_{row["id"]}', None)
                                st.rerun()
                            else:
                                st.error(msg)
                    
                    with col2:
                        if st.button("❌ Annuler", key=f"cancel_edit_{row['id']}"):
                            st.session_state.pop(f'editing_{row["id"]}', None)
                            st.rerun()
                    
                    st.markdown("---")
            
            st.markdown("<hr style='margin: 0.3rem 0; border: none; border-top: 1px solid #eee;'>", unsafe_allow_html=True)
        
        # Total
        total_ha = df_affectations['Hectares'].sum()
        st.markdown(f"**Total affecté :** {total_ha} ha sur {info.get('ha_besoin', 0)} ha")
    else:
        st.info("Aucune affectation pour ce besoin")
    
    # ==========================================
    # AJOUTER AFFECTATION
    # ==========================================
    
    if CAN_EDIT:
        st.markdown("---")
        st.markdown("#### ➕ Nouvelle affectation")
        
        reste = info.get('reste', 0)
        
        if reste <= 0:
            st.success("✅ Ce besoin est entièrement couvert !")
        else:
            # Charger producteurs
            producteurs = get_producteurs_actifs()
            
            if producteurs:
                col1, col2 = st.columns(2)
                
                with col1:
                    # Dropdown producteurs avec recherche
                    prod_options = ["-- Sélectionner --"] + [p['display'] for p in producteurs]
                    selected_prod = st.selectbox(
                        "Producteur *",
                        prod_options,
                        key="new_producteur"
                    )
                
                with col2:
                    # Hectares (entiers uniquement)
                    hectares = st.number_input(
                        f"Hectares * (max suggéré: {reste})",
                        min_value=1,
                        max_value=1000,
                        value=min(reste, 10) if reste > 0 else 1,
                        step=1,
                        key="new_hectares"
                    )
                
                notes = st.text_input("Notes (optionnel)", key="new_notes")
                
                # Bouton ajouter
                if st.button("✅ Ajouter l'affectation", type="primary", use_container_width=True):
                    if selected_prod == "-- Sélectionner --":
                        st.error("❌ Veuillez sélectionner un producteur")
                    else:
                        # Trouver ID producteur
                        prod_idx = prod_options.index(selected_prod) - 1  # -1 car "-- Sélectionner --"
                        producteur_id = producteurs[prod_idx]['id']
                        
                        # Récupérer infos besoin
                        besoin_info = get_besoin_info(besoin_id)
                        
                        if besoin_info:
                            success, msg = ajouter_affectation(
                                besoin_id,
                                besoin_info['campagne'],
                                besoin_info['mois'],
                                besoin_info['variete'],
                                producteur_id,
                                hectares,
                                notes
                            )
                            
                            if success:
                                st.success(msg)
                                st.balloons()
                                # Rafraîchir infos
                                st.rerun()
                            else:
                                st.error(msg)
                        else:
                            st.error("❌ Besoin introuvable")
            else:
                st.warning("⚠️ Aucun producteur actif trouvé")
    else:
        st.info("🔒 Vous n'avez pas les droits pour ajouter des affectations")

else:
    st.info("👆 Sélectionnez un besoin dans le tableau ci-dessus")

# ==========================================
# SECTION 3 : AFFECTATION RAPIDE (multi)
# ==========================================

st.markdown("---")

with st.expander("⚡ Affectation rapide (plusieurs besoins)", expanded=False):
    st.markdown("""
    **Mode rapide** : Affectez le même producteur à plusieurs besoins d'une variété.
    """)
    
    if CAN_EDIT:
        col1, col2 = st.columns(2)
        
        with col1:
            # Sélection variété
            varietes = get_varietes_besoins(campagne)
            variete_rapide = st.selectbox("Variété", varietes, key="rapide_variete")
        
        with col2:
            # Sélection producteur
            producteurs = get_producteurs_actifs()
            prod_options_rapide = ["-- Sélectionner --"] + [p['display'] for p in producteurs]
            prod_rapide = st.selectbox("Producteur", prod_options_rapide, key="rapide_prod")
        
        # Charger besoins incomplets pour cette variété
        if variete_rapide:
            df_rapide = get_besoins(campagne, "Incomplets", variete_rapide)
            
            if not df_rapide.empty:
                st.markdown(f"**{len(df_rapide)} besoin(s) incomplet(s) pour {variete_rapide}**")
                
                # Tableau avec checkbox
                df_rapide['Sélectionner'] = False
                df_rapide['Ha à affecter'] = 1
                # ✅ CORRIGÉ : Créer 'Reste' AVANT de l'utiliser
                df_rapide['Reste'] = df_rapide['Ha Besoin'] - df_rapide['Ha Affectés']
                
                edited = st.data_editor(
                    df_rapide[['Sélectionner', 'Mois', 'Ha Besoin', 'Ha Affectés', 'Reste', 'Ha à affecter']],
                    column_config={
                        "Sélectionner": st.column_config.CheckboxColumn("✓", default=False),
                        "Ha à affecter": st.column_config.NumberColumn("Ha à affecter", min_value=1, max_value=100, step=1),
                    },
                    hide_index=True,
                    key="rapide_editor"
                )
                
                if st.button("✅ Affecter sélection", type="primary"):
                    if prod_rapide == "-- Sélectionner --":
                        st.error("❌ Sélectionnez un producteur")
                    else:
                        # Trouver producteur
                        prod_idx = prod_options_rapide.index(prod_rapide) - 1
                        producteur_id = producteurs[prod_idx]['id']
                        
                        # Affecter chaque ligne sélectionnée
                        nb_ok = 0
                        for idx, row in edited.iterrows():
                            if row['Sélectionner']:
                                besoin = df_rapide.iloc[idx]
                                success, _ = ajouter_affectation(
                                    int(besoin['id']),
                                    campagne,
                                    besoin['Mois'],
                                    variete_rapide,
                                    producteur_id,
                                    int(row['Ha à affecter']),
                                    ""
                                )
                                if success:
                                    nb_ok += 1
                        
                        if nb_ok > 0:
                            st.success(f"✅ {nb_ok} affectation(s) créée(s)")
                            st.rerun()
            else:
                st.success(f"✅ Tous les besoins pour {variete_rapide} sont complets !")
    else:
        st.info("🔒 Mode lecture seule")

show_footer()
