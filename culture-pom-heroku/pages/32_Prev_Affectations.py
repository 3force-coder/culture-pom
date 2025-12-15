import streamlit as st
import pandas as pd
from datetime import datetime, date
from database import get_connection
from components import show_footer
from auth import is_authenticated

st.set_page_config(page_title="Affectations - Culture Pom", page_icon="📋", layout="wide")

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
    .lot-card {
        background-color: #f8f9fa;
        padding: 0.8rem;
        border-radius: 0.5rem;
        margin: 0.3rem 0;
        border-left: 4px solid #1976d2;
    }
    .lot-card.ct {
        border-left-color: #ff9800;
        background-color: #fff8e1;
    }
    .lot-card.lt {
        border-left-color: #4caf50;
        background-color: #e8f5e9;
    }
</style>
""", unsafe_allow_html=True)

if not is_authenticated():
    st.warning("⚠️ Veuillez vous connecter pour accéder à cette page")
    st.stop()

# ============================================================
# FONCTIONS DONNÉES
# ============================================================

def get_sites_production():
    """Récupère les sites de production"""
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
        return [row['site'] for row in rows] if rows else ['SAINT_FLAVY', 'CORROY']
    except:
        return ['SAINT_FLAVY', 'CORROY']

def get_produits_par_marque_type():
    """Récupère les produits groupés par marque + type"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        query = """
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
        """
        
        cursor.execute(query)
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        
        if rows:
            return pd.DataFrame(rows)
        return pd.DataFrame()
        
    except Exception as e:
        st.error(f"Erreur produits: {str(e)}")
        return pd.DataFrame()

def get_lots_disponibles(variete_filter=None):
    """Récupère les lots disponibles pour affectation"""
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
                l.code_producteur,
                l.poids_total_brut_kg / 1000 as poids_brut_tonnes,
                l.prix_achat_euro_tonne,
                l.date_entree_stock,
                -- Tare prioritaire
                COALESCE(
                    l.tare_lavage_totale_pct,
                    v.taux_dechet_moyen * 100,
                    22
                ) as tare_pct,
                CASE 
                    WHEN l.tare_lavage_totale_pct IS NOT NULL THEN 'LOT'
                    WHEN v.taux_dechet_moyen IS NOT NULL THEN 'VARIETE'
                    ELSE 'DEFAUT'
                END as tare_source,
                -- Poids déjà affecté
                COALESCE((
                    SELECT SUM(pa.quantite_affectee_tonnes)
                    FROM previsions_affectations pa
                    WHERE pa.lot_id = l.id AND pa.is_active = TRUE
                ), 0) as poids_affecte_tonnes
            FROM lots_bruts l
            LEFT JOIN ref_varietes v ON l.code_variete = v.code_variete
            WHERE l.is_active = TRUE
              AND l.poids_total_brut_kg > 0
            ORDER BY l.date_entree_stock DESC, l.code_lot_interne
        """
        
        cursor.execute(query)
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        
        if rows:
            df = pd.DataFrame(rows)
            # Convertir colonnes numériques
            numeric_cols = ['poids_brut_tonnes', 'prix_achat_euro_tonne', 'tare_pct', 'poids_affecte_tonnes']
            for col in numeric_cols:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
            
            # Calculer poids disponible et poids net
            df['poids_disponible_tonnes'] = df['poids_brut_tonnes'] - df['poids_affecte_tonnes']
            df['poids_net_estime_tonnes'] = df['poids_disponible_tonnes'] * (1 - df['tare_pct'] / 100)
            
            # Filtrer variété si demandé
            if variete_filter and variete_filter != "Toutes":
                df = df[df['nom_variete'] == variete_filter]
            
            # Filtrer lots avec stock disponible
            df = df[df['poids_disponible_tonnes'] > 0]
            
            return df
        return pd.DataFrame()
        
    except Exception as e:
        st.error(f"Erreur lots: {str(e)}")
        return pd.DataFrame()

def get_varietes_disponibles():
    """Récupère les variétés des lots en stock"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT DISTINCT v.nom_variete
            FROM lots_bruts l
            JOIN ref_varietes v ON l.code_variete = v.code_variete
            WHERE l.is_active = TRUE AND l.poids_total_brut_kg > 0
            ORDER BY v.nom_variete
        """)
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        return [row['nom_variete'] for row in rows] if rows else []
    except:
        return []

def get_affectations_produit(code_produit, type_affectation=None):
    """Récupère les affectations pour un produit"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        query = """
            SELECT 
                pa.id,
                pa.lot_id,
                l.code_lot_interne,
                l.nom_usage,
                l.code_variete,
                v.nom_variete,
                pa.quantite_affectee_tonnes,
                pa.tare_utilisee_pct,
                pa.tare_source,
                pa.poids_net_estime_tonnes,
                pa.type_affectation,
                pa.site,
                pa.date_debut_estimee,
                pa.date_fin_estimee,
                pa.created_at,
                pa.created_by
            FROM previsions_affectations pa
            JOIN lots_bruts l ON pa.lot_id = l.id
            LEFT JOIN ref_varietes v ON l.code_variete = v.code_variete
            WHERE pa.code_produit_commercial = %s
              AND pa.is_active = TRUE
        """
        
        params = [code_produit]
        
        if type_affectation:
            query += " AND pa.type_affectation = %s"
            params.append(type_affectation)
        
        query += " ORDER BY pa.date_debut_estimee NULLS LAST, pa.created_at"
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        
        if rows:
            df = pd.DataFrame(rows)
            for col in ['quantite_affectee_tonnes', 'tare_utilisee_pct', 'poids_net_estime_tonnes']:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
            return df
        return pd.DataFrame()
        
    except Exception as e:
        st.error(f"Erreur affectations: {str(e)}")
        return pd.DataFrame()

def get_conso_moyenne_produit(code_produit):
    """Récupère la consommation moyenne 5 semaines pour un produit"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT AVG(quantite_prevue_tonnes) as conso_moyenne
            FROM previsions_ventes
            WHERE code_produit_commercial = %s
              AND annee = EXTRACT(YEAR FROM CURRENT_DATE)
              AND semaine >= EXTRACT(WEEK FROM CURRENT_DATE) - 5
              AND semaine <= EXTRACT(WEEK FROM CURRENT_DATE)
        """, (code_produit,))
        
        result = cursor.fetchone()
        cursor.close()
        conn.close()
        
        return float(result['conso_moyenne'] or 0) if result else 0
        
    except:
        return 0

def create_affectation(code_produit, lot_id, quantite_tonnes, site, type_affectation='LT'):
    """Crée une nouvelle affectation"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Récupérer infos lot pour calcul tare
        cursor.execute("""
            SELECT 
                l.poids_total_brut_kg / 1000 as poids_brut,
                COALESCE(l.tare_lavage_totale_pct, v.taux_dechet_moyen * 100, 22) as tare_pct,
                CASE 
                    WHEN l.tare_lavage_totale_pct IS NOT NULL THEN 'LOT'
                    WHEN v.taux_dechet_moyen IS NOT NULL THEN 'VARIETE'
                    ELSE 'DEFAUT'
                END as tare_source
            FROM lots_bruts l
            LEFT JOIN ref_varietes v ON l.code_variete = v.code_variete
            WHERE l.id = %s
        """, (lot_id,))
        
        lot_info = cursor.fetchone()
        if not lot_info:
            return False, "Lot introuvable"
        
        tare_pct = float(lot_info['tare_pct'])
        tare_source = lot_info['tare_source']
        poids_net = float(quantite_tonnes) * (1 - tare_pct / 100)
        
        # Calculer date début et fin estimées
        conso_hebdo = get_conso_moyenne_produit(code_produit)
        date_debut = date.today()
        
        if conso_hebdo > 0:
            jours_stock = (poids_net / conso_hebdo) * 7
            date_fin = date.today() + pd.Timedelta(days=int(jours_stock))
        else:
            date_fin = None
        
        created_by = st.session_state.get('username', 'system')
        
        # Insérer
        cursor.execute("""
            INSERT INTO previsions_affectations (
                code_produit_commercial, lot_id, quantite_affectee_tonnes,
                tare_utilisee_pct, tare_source, poids_net_estime_tonnes,
                type_affectation, site, date_debut_estimee, date_fin_estimee,
                created_by, is_active
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, TRUE)
            RETURNING id
        """, (
            code_produit, int(lot_id), float(quantite_tonnes),
            tare_pct, tare_source, poids_net,
            type_affectation, site, date_debut, date_fin,
            created_by
        ))
        
        new_id = cursor.fetchone()['id']
        conn.commit()
        cursor.close()
        conn.close()
        
        return True, f"✅ Affectation #{new_id} créée ({quantite_tonnes:.1f}T brut → {poids_net:.1f}T net)"
        
    except Exception as e:
        if 'conn' in locals():
            conn.rollback()
        return False, f"❌ Erreur: {str(e)}"

def delete_affectation(affectation_id):
    """Supprime (désactive) une affectation"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE previsions_affectations
            SET is_active = FALSE, updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
        """, (affectation_id,))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return True, "✅ Affectation supprimée"
        
    except Exception as e:
        if 'conn' in locals():
            conn.rollback()
        return False, f"❌ Erreur: {str(e)}"

def create_tache_from_selection(type_tache, description, lots_ids=None, produit_code=None):
    """Crée une tâche depuis la sélection"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        created_by = st.session_state.get('username', 'system')
        
        # Construire le titre
        if type_tache == "ACHETER":
            titre = f"ACHETER - {description}"
        elif type_tache == "VENDRE":
            titre = f"VENDRE - {description}"
        else:
            titre = description
        
        # Insérer dans taches
        cursor.execute("""
            INSERT INTO taches (titre, description, statut, created_by, created_at)
            VALUES (%s, %s, 'A_FAIRE', %s, CURRENT_TIMESTAMP)
            RETURNING id
        """, (titre, description, created_by))
        
        tache_id = cursor.fetchone()['id']
        conn.commit()
        cursor.close()
        conn.close()
        
        return True, f"✅ Tâche #{tache_id} créée: {titre}"
        
    except Exception as e:
        if 'conn' in locals():
            conn.rollback()
        return False, f"❌ Erreur: {str(e)}"

# ============================================================
# INTERFACE
# ============================================================

st.title("📋 Affectations Lots → Produits")
st.markdown("*Gérer les affectations de lots aux produits commerciaux*")

# ============================================================
# SIDEBAR - SÉLECTION PRODUIT
# ============================================================

with st.sidebar:
    st.header("🎯 Sélection Produit")
    
    # Charger produits
    produits_df = get_produits_par_marque_type()
    
    if not produits_df.empty:
        # Filtre marque
        marques = ["Toutes"] + sorted(produits_df['marque'].dropna().unique().tolist())
        selected_marque = st.selectbox("Marque", marques, key="filter_marque")
        
        # Filtrer produits par marque
        if selected_marque != "Toutes":
            produits_filtrés = produits_df[produits_df['marque'] == selected_marque]
        else:
            produits_filtrés = produits_df
        
        # Sélection produit
        if not produits_filtrés.empty:
            produit_options = produits_filtrés['ligne_prevision'].tolist()
            selected_ligne = st.selectbox("Ligne de prévision", produit_options, key="select_produit")
            
            # Récupérer code_produit sélectionné
            selected_produit = produits_filtrés[produits_filtrés['ligne_prevision'] == selected_ligne].iloc[0]
            code_produit = selected_produit['code_produit']
            
            st.markdown("---")
            st.markdown(f"**Code**: `{code_produit}`")
            if selected_produit['atelier']:
                st.markdown(f"**Atelier**: {selected_produit['atelier']}")
            if selected_produit['prix_vente_tonne']:
                st.markdown(f"**Prix vente**: {selected_produit['prix_vente_tonne']:.0f} €/T")
            
            # Conso moyenne
            conso_moy = get_conso_moyenne_produit(code_produit)
            st.metric("Conso moyenne (5 sem)", f"{conso_moy:.1f} T/sem")
        else:
            code_produit = None
            st.warning("Aucun produit trouvé")
    else:
        code_produit = None
        st.warning("Aucun produit disponible")
    
    st.markdown("---")
    
    # Filtre site
    sites = get_sites_production()
    selected_site = st.selectbox("🏭 Site", sites, key="select_site")
    
    # Toggle CT/LT
    st.markdown("---")
    show_ct = st.checkbox("Afficher CT (court terme)", value=True)
    show_lt = st.checkbox("Afficher LT (long terme)", value=True)

# ============================================================
# CONTENU PRINCIPAL
# ============================================================

if code_produit:
    st.markdown(f"### 📦 Affectations pour: **{selected_ligne}**")
    
    # Onglets
    tab1, tab2 = st.tabs(["📋 Affectations actuelles", "➕ Nouvelle affectation"])
    
    # ============================================================
    # TAB 1: AFFECTATIONS ACTUELLES
    # ============================================================
    
    with tab1:
        # Charger affectations
        type_filter = None
        if show_ct and not show_lt:
            type_filter = 'CT'
        elif show_lt and not show_ct:
            type_filter = 'LT'
        
        affectations_df = get_affectations_produit(code_produit, type_filter)
        
        if not affectations_df.empty:
            # KPIs affectations
            col1, col2, col3, col4 = st.columns(4)
            
            total_brut = affectations_df['quantite_affectee_tonnes'].sum()
            total_net = affectations_df['poids_net_estime_tonnes'].sum()
            nb_lots = len(affectations_df)
            
            with col1:
                st.metric("📦 Lots affectés", nb_lots)
            with col2:
                st.metric("⚖️ Tonnage brut", f"{total_brut:,.0f} T")
            with col3:
                st.metric("📊 Tonnage net", f"{total_net:,.0f} T")
            with col4:
                if conso_moy > 0:
                    semaines = total_net / conso_moy
                    st.metric("📅 Stock en semaines", f"{semaines:.1f}")
                else:
                    st.metric("📅 Stock en semaines", "-")
            
            st.markdown("---")
            
            # Tableau avec sélection pour suppression
            st.markdown("#### Liste des affectations (ordre de consommation)")
            
            # Préparer affichage
            df_display = affectations_df[[
                'id', 'code_lot_interne', 'nom_variete', 'quantite_affectee_tonnes',
                'poids_net_estime_tonnes', 'tare_utilisee_pct', 'type_affectation',
                'date_debut_estimee', 'date_fin_estimee'
            ]].copy()
            
            df_display.columns = [
                'ID', 'Code Lot', 'Variété', 'Brut (T)', 'Net (T)', 
                'Tare %', 'Type', 'Début', 'Fin'
            ]
            
            # Formater
            df_display['Brut (T)'] = df_display['Brut (T)'].apply(lambda x: f"{x:,.1f}")
            df_display['Net (T)'] = df_display['Net (T)'].apply(lambda x: f"{x:,.1f}")
            df_display['Tare %'] = df_display['Tare %'].apply(lambda x: f"{x:.1f}%")
            
            # Afficher avec sélection
            event = st.dataframe(
                df_display,
                use_container_width=True,
                hide_index=True,
                on_select="rerun",
                selection_mode="multi-row",
                key="affectations_table"
            )
            
            # Actions sur sélection
            selected_rows = event.selection.rows if hasattr(event, 'selection') else []
            
            if len(selected_rows) > 0:
                st.markdown("---")
                col_del, col_task = st.columns(2)
                
                with col_del:
                    if st.button("🗑️ Supprimer sélection", type="secondary", use_container_width=True):
                        for idx in selected_rows:
                            affectation_id = affectations_df.iloc[idx]['id']
                            success, msg = delete_affectation(int(affectation_id))
                            if success:
                                st.success(msg)
                            else:
                                st.error(msg)
                        st.rerun()
                
                with col_task:
                    if st.button("📝 Créer tâche", use_container_width=True):
                        st.session_state['show_task_form'] = True
                
                # Formulaire tâche
                if st.session_state.get('show_task_form', False):
                    with st.form("task_form"):
                        st.markdown("##### Créer une tâche")
                        
                        type_tache = st.selectbox("Type", ["ACHETER", "VENDRE", "AUTRE"])
                        description = st.text_area("Description")
                        
                        if st.form_submit_button("✅ Créer"):
                            if description:
                                success, msg = create_tache_from_selection(type_tache, description)
                                if success:
                                    st.success(msg)
                                    st.session_state['show_task_form'] = False
                                    st.rerun()
                                else:
                                    st.error(msg)
                            else:
                                st.error("Description obligatoire")
        else:
            st.info("Aucune affectation pour ce produit. Utilisez l'onglet '➕ Nouvelle affectation' pour en créer.")
    
    # ============================================================
    # TAB 2: NOUVELLE AFFECTATION
    # ============================================================
    
    with tab2:
        st.markdown("#### 📦 Sélectionner un lot à affecter")
        
        # Filtres lots
        col_filter1, col_filter2 = st.columns(2)
        
        with col_filter1:
            varietes = ["Toutes"] + get_varietes_disponibles()
            filter_variete = st.selectbox("Filtrer par variété", varietes, key="filter_variete_lot")
        
        with col_filter2:
            filter_dispo = st.checkbox("Uniquement lots avec stock disponible", value=True)
        
        # Charger lots
        lots_df = get_lots_disponibles(filter_variete if filter_variete != "Toutes" else None)
        
        if not lots_df.empty:
            st.markdown(f"**{len(lots_df)} lot(s) disponible(s)**")
            
            # Préparer affichage
            df_lots_display = lots_df[[
                'lot_id', 'code_lot_interne', 'nom_variete', 'poids_brut_tonnes',
                'poids_disponible_tonnes', 'poids_net_estime_tonnes', 'tare_pct',
                'prix_achat_euro_tonne', 'date_entree_stock'
            ]].copy()
            
            df_lots_display.columns = [
                'ID', 'Code Lot', 'Variété', 'Brut Total (T)', 
                'Disponible (T)', 'Net Estimé (T)', 'Tare %',
                'Prix Achat €/T', 'Date Entrée'
            ]
            
            # Formater
            for col in ['Brut Total (T)', 'Disponible (T)', 'Net Estimé (T)']:
                df_lots_display[col] = df_lots_display[col].apply(lambda x: f"{x:,.1f}")
            df_lots_display['Tare %'] = df_lots_display['Tare %'].apply(lambda x: f"{x:.1f}%")
            df_lots_display['Prix Achat €/T'] = df_lots_display['Prix Achat €/T'].apply(
                lambda x: f"{x:,.0f}" if pd.notna(x) and x > 0 else "-"
            )
            
            # Tableau avec sélection
            event_lots = st.dataframe(
                df_lots_display,
                use_container_width=True,
                hide_index=True,
                on_select="rerun",
                selection_mode="single-row",
                key="lots_table"
            )
            
            selected_lot_rows = event_lots.selection.rows if hasattr(event_lots, 'selection') else []
            
            if len(selected_lot_rows) > 0:
                st.markdown("---")
                
                selected_lot_idx = selected_lot_rows[0]
                selected_lot = lots_df.iloc[selected_lot_idx]
                
                st.success(f"✅ Lot sélectionné: **{selected_lot['code_lot_interne']}** - {selected_lot['nom_variete']}")
                
                # Formulaire affectation
                col_form1, col_form2 = st.columns(2)
                
                with col_form1:
                    max_dispo = float(selected_lot['poids_disponible_tonnes'])
                    quantite = st.number_input(
                        "Quantité à affecter (T brut)",
                        min_value=0.1,
                        max_value=max_dispo,
                        value=min(100.0, max_dispo),
                        step=10.0,
                        key="quantite_affectation"
                    )
                    
                    # Calcul net estimé
                    tare = float(selected_lot['tare_pct'])
                    net_estime = quantite * (1 - tare / 100)
                    st.info(f"📊 Net estimé: **{net_estime:,.1f} T** (tare {tare:.1f}%)")
                
                with col_form2:
                    type_aff = st.selectbox(
                        "Type d'affectation",
                        ["LT - Long terme (prévision)", "CT - Court terme (réel)"],
                        key="type_affectation"
                    )
                    type_code = 'LT' if 'LT' in type_aff else 'CT'
                    
                    # Calcul semaines
                    if conso_moy > 0:
                        semaines_lot = net_estime / conso_moy
                        st.info(f"📅 Durée estimée: **{semaines_lot:.1f} semaines**")
                
                # Bouton créer
                if st.button("✅ Créer l'affectation", type="primary", use_container_width=True, key="btn_create_affectation"):
                    success, msg = create_affectation(
                        code_produit,
                        int(selected_lot['lot_id']),
                        quantite,
                        selected_site,
                        type_code
                    )
                    
                    if success:
                        st.success(msg)
                        st.balloons()
                        st.rerun()
                    else:
                        st.error(msg)
            else:
                st.info("👆 Sélectionnez un lot dans le tableau ci-dessus")
        else:
            st.warning("Aucun lot disponible avec les filtres actuels")

else:
    st.info("👈 Sélectionnez un produit dans la barre latérale pour commencer")

st.markdown("---")

# ============================================================
# RÉSUMÉ GLOBAL
# ============================================================

with st.expander("📊 Résumé global des affectations"):
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                pc.marque,
                COUNT(DISTINCT pa.lot_id) as nb_lots,
                SUM(pa.quantite_affectee_tonnes) as tonnes_brut,
                SUM(pa.poids_net_estime_tonnes) as tonnes_net
            FROM previsions_affectations pa
            JOIN ref_produits_commerciaux pc ON pa.code_produit_commercial = pc.code_produit
            WHERE pa.is_active = TRUE
            GROUP BY pc.marque
            ORDER BY tonnes_brut DESC
        """)
        
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        
        if rows:
            df_resume = pd.DataFrame(rows)
            df_resume.columns = ['Marque', 'Nb Lots', 'Tonnes Brut', 'Tonnes Net']
            
            for col in ['Tonnes Brut', 'Tonnes Net']:
                df_resume[col] = pd.to_numeric(df_resume[col], errors='coerce').fillna(0)
                df_resume[col] = df_resume[col].apply(lambda x: f"{x:,.0f}")
            
            st.dataframe(df_resume, use_container_width=True, hide_index=True)
        else:
            st.info("Aucune affectation enregistrée")
            
    except Exception as e:
        st.error(f"Erreur: {str(e)}")

show_footer()
