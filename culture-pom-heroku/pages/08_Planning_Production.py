import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from database import get_connection
from components import show_footer
from auth import is_authenticated
import io

st.set_page_config(page_title="Planning Production - Culture Pom", page_icon="🏭", layout="wide")

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
    .job-card {
        background-color: #f0f2f6;
        padding: 1rem;
        border-radius: 0.5rem;
        margin: 0.5rem 0;
        border-left: 4px solid #1f77b4;
    }
    .job-card.en-cours {
        border-left-color: #ff7f0e;
        background-color: #fff3e0;
    }
    .job-card.termine {
        border-left-color: #2ca02c;
        background-color: #e8f5e9;
    }
</style>
""", unsafe_allow_html=True)

if not is_authenticated():
    st.warning("⚠️ Veuillez vous connecter pour accéder à cette page")
    st.stop()

st.title("🏭 Planning Production")
st.markdown("*Gestion des jobs de production - Transformation en produits finis*")
st.markdown("---")

# ==========================================
# FONCTIONS UTILITAIRES
# ==========================================

def get_stock_lave_disponible():
    """Récupère le stock LAVÉ disponible pour production"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        query = """
        SELECT 
            l.id as lot_id,
            l.code_lot_interne,
            COALESCE(v.nom_variete, l.code_variete) as variete,
            se.id as emplacement_id,
            se.site_stockage,
            se.emplacement_stockage,
            se.nombre_unites,
            se.poids_total_kg,
            se.type_conditionnement,
            COALESCE(se.type_stock, se.statut_lavage, 'BRUT') as type_stock
        FROM lots_bruts l
        JOIN stock_emplacements se ON l.id = se.lot_id
        LEFT JOIN ref_varietes v ON l.code_variete = v.code_variete
        WHERE se.is_active = TRUE 
          AND COALESCE(se.type_stock, se.statut_lavage, 'BRUT') = 'LAVÉ'
          AND se.nombre_unites > 0
        ORDER BY l.code_lot_interne
        """
        
        cursor.execute(query)
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        
        if rows:
            df = pd.DataFrame(rows)
            numeric_cols = ['nombre_unites', 'poids_total_kg']
            for col in numeric_cols:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
            return df
        return pd.DataFrame()
        
    except Exception as e:
        st.error(f"❌ Erreur chargement stock : {str(e)}")
        return pd.DataFrame()

def get_affectations_pour_production():
    """Récupère les affectations disponibles pour production"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Vérifier si la table previsions_affectations existe
        cursor.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = 'previsions_affectations'
            )
        """)
        if not cursor.fetchone()['exists']:
            cursor.close()
            conn.close()
            return pd.DataFrame()
        
        query = """
        SELECT 
            pa.id as affectation_id,
            pa.lot_id,
            l.code_lot_interne,
            COALESCE(v.nom_variete, l.code_variete) as variete,
            pa.code_produit_commercial,
            pc.libelle as produit_libelle,
            pc.marque as produit_marque,
            pc.atelier as produit_atelier,
            pa.annee,
            pa.semaine,
            pa.quantite_affectee_tonnes,
            pa.poids_net_estime_tonnes,
            pa.statut_stock
        FROM previsions_affectations pa
        JOIN lots_bruts l ON pa.lot_id = l.id
        LEFT JOIN ref_varietes v ON l.code_variete = v.code_variete
        JOIN ref_produits_commerciaux pc ON pa.code_produit_commercial = pc.code_produit
        WHERE pa.is_active = TRUE
        ORDER BY pa.annee, pa.semaine, pa.code_produit_commercial
        """
        
        cursor.execute(query)
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        
        if rows:
            df = pd.DataFrame(rows)
            numeric_cols = ['quantite_affectee_tonnes', 'poids_net_estime_tonnes']
            for col in numeric_cols:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
            return df
        return pd.DataFrame()
        
    except Exception as e:
        st.error(f"❌ Erreur : {str(e)}")
        return pd.DataFrame()

def get_lignes_production():
    """Récupère les lignes de production actives"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT code, libelle, site, type_atelier, capacite_th, cout_tonne
            FROM production_lignes
            WHERE is_active = TRUE
            ORDER BY site, code
        """)
        
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        
        return rows if rows else []
        
    except Exception as e:
        st.error(f"❌ Erreur : {str(e)}")
        return []

def get_sur_emballages():
    """Récupère les sur-emballages actifs"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT code, libelle, volume_tonnes, cout_tonne
            FROM ref_sur_emballages
            WHERE is_active = TRUE
            ORDER BY libelle
        """)
        
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        
        return rows if rows else []
        
    except Exception as e:
        return []

def get_produits_commerciaux():
    """Récupère les produits commerciaux actifs"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT code_produit, marque, libelle, atelier, type_produit
            FROM ref_produits_commerciaux
            WHERE is_active = TRUE
            ORDER BY marque, libelle
        """)
        
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        
        return rows if rows else []
        
    except Exception as e:
        return []

def get_emplacements_site(site):
    """Récupère les emplacements d'un site"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT code_emplacement, nom_complet
            FROM ref_sites_stockage
            WHERE code_site = %s AND is_active = TRUE
            ORDER BY code_emplacement
        """, (site,))
        
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        
        return [(row['code_emplacement'], row['nom_complet']) for row in rows] if rows else []
        
    except Exception as e:
        return []

def get_kpis_production():
    """Récupère les KPIs de production"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Jobs prévus
        cursor.execute("SELECT COUNT(*) as nb FROM production_jobs WHERE statut = 'PRÉVU'")
        nb_prevus = cursor.fetchone()['nb']
        
        # Jobs en cours
        cursor.execute("SELECT COUNT(*) as nb FROM production_jobs WHERE statut = 'EN_COURS'")
        nb_en_cours = cursor.fetchone()['nb']
        
        # Jobs terminés
        cursor.execute("SELECT COUNT(*) as nb FROM production_jobs WHERE statut = 'TERMINÉ'")
        nb_termines = cursor.fetchone()['nb']
        
        # Tonnage prévu
        cursor.execute("SELECT COALESCE(SUM(quantite_entree_tonnes), 0) as total FROM production_jobs WHERE statut IN ('PRÉVU', 'EN_COURS')")
        tonnage_prevu = cursor.fetchone()['total']
        
        cursor.close()
        conn.close()
        
        return {
            'nb_prevus': nb_prevus,
            'nb_en_cours': nb_en_cours,
            'nb_termines': nb_termines,
            'tonnage_prevu': float(tonnage_prevu)
        }
        
    except Exception as e:
        return {'nb_prevus': 0, 'nb_en_cours': 0, 'nb_termines': 0, 'tonnage_prevu': 0}

def get_jobs_by_date(date):
    """Récupère les jobs pour une date donnée"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        query = """
        SELECT 
            pj.id,
            pj.lot_id,
            pj.code_lot_interne,
            pj.variete,
            pj.code_produit_commercial,
            pc.libelle as produit_libelle,
            pj.quantite_entree_tonnes,
            pj.ligne_production,
            pl.libelle as ligne_libelle,
            pj.temps_estime_heures,
            pj.sur_emballage,
            pj.statut,
            pj.created_by
        FROM production_jobs pj
        LEFT JOIN ref_produits_commerciaux pc ON pj.code_produit_commercial = pc.code_produit
        LEFT JOIN production_lignes pl ON pj.ligne_production = pl.code
        WHERE pj.date_prevue = %s
        ORDER BY pj.ligne_production, pj.created_at
        """
        
        cursor.execute(query, (date,))
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        
        if rows:
            df = pd.DataFrame(rows)
            numeric_cols = ['quantite_entree_tonnes', 'temps_estime_heures']
            for col in numeric_cols:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
            return df
        return pd.DataFrame()
        
    except Exception as e:
        st.error(f"❌ Erreur : {str(e)}")
        return pd.DataFrame()

def get_jobs_by_statut(statut):
    """Récupère les jobs par statut"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        query = """
        SELECT 
            pj.id,
            pj.lot_id,
            pj.code_lot_interne,
            pj.variete,
            pj.code_produit_commercial,
            pc.libelle as produit_libelle,
            pc.marque as produit_marque,
            pj.quantite_entree_tonnes,
            pj.date_prevue,
            pj.ligne_production,
            pl.libelle as ligne_libelle,
            pj.temps_estime_heures,
            pj.sur_emballage,
            pj.statut,
            pj.created_by,
            pj.created_at,
            pj.date_activation,
            pj.date_terminaison,
            pj.quantite_sortie_tonnes,
            pj.numero_lot_sortie
        FROM production_jobs pj
        LEFT JOIN ref_produits_commerciaux pc ON pj.code_produit_commercial = pc.code_produit
        LEFT JOIN production_lignes pl ON pj.ligne_production = pl.code
        WHERE pj.statut = %s
        ORDER BY pj.date_prevue DESC, pj.created_at DESC
        """
        
        cursor.execute(query, (statut,))
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        
        if rows:
            df = pd.DataFrame(rows)
            numeric_cols = ['quantite_entree_tonnes', 'temps_estime_heures', 'quantite_sortie_tonnes']
            for col in numeric_cols:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
            return df
        return pd.DataFrame()
        
    except Exception as e:
        st.error(f"❌ Erreur : {str(e)}")
        return pd.DataFrame()

def create_job_production(lot_id, code_lot_interne, variete, code_produit, 
                          quantite_tonnes, date_prevue, ligne_production, 
                          capacite_th, sur_emballage=None, affectation_id=None, notes=""):
    """Crée un nouveau job de production"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Convertir types
        lot_id = int(lot_id)
        quantite_tonnes = float(quantite_tonnes)
        capacite_th = float(capacite_th)
        
        # Calculer temps estimé
        temps_estime = quantite_tonnes / capacite_th  # heures
        
        created_by = st.session_state.get('username', 'system')
        
        query = """
        INSERT INTO production_jobs (
            lot_id, code_lot_interne, variete, code_produit_commercial,
            quantite_entree_tonnes, date_prevue, ligne_production, capacite_th,
            temps_estime_heures, sur_emballage, affectation_id,
            statut, created_by, notes
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'PRÉVU', %s, %s)
        RETURNING id
        """
        
        cursor.execute(query, (
            lot_id, code_lot_interne, variete, code_produit,
            quantite_tonnes, date_prevue, ligne_production, capacite_th,
            temps_estime, sur_emballage, affectation_id,
            created_by, notes
        ))
        
        job_id = cursor.fetchone()['id']
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return True, f"✅ Job #{job_id} créé avec succès"
        
    except Exception as e:
        if 'conn' in locals():
            conn.rollback()
        return False, f"❌ Erreur : {str(e)}"

def activer_job(job_id):
    """Active un job (PRÉVU → EN_COURS)"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        activated_by = st.session_state.get('username', 'system')
        
        cursor.execute("""
            UPDATE production_jobs
            SET statut = 'EN_COURS',
                date_activation = CURRENT_TIMESTAMP,
                activated_by = %s,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = %s AND statut = 'PRÉVU'
        """, (activated_by, job_id))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return True, "✅ Job activé"
        
    except Exception as e:
        if 'conn' in locals():
            conn.rollback()
        return False, f"❌ Erreur : {str(e)}"

def terminer_job(job_id, quantite_sortie, numero_lot_sortie, site_dest, emplacement_dest, notes=""):
    """Termine un job et crée le stock produit fini"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Récupérer job
        cursor.execute("""
            SELECT lot_id, code_produit_commercial, quantite_entree_tonnes
            FROM production_jobs
            WHERE id = %s AND statut = 'EN_COURS'
        """, (job_id,))
        
        job = cursor.fetchone()
        if not job:
            return False, "❌ Job introuvable ou pas EN_COURS"
        
        terminated_by = st.session_state.get('username', 'system')
        
        # Mettre à jour job
        cursor.execute("""
            UPDATE production_jobs
            SET statut = 'TERMINÉ',
                date_terminaison = CURRENT_TIMESTAMP,
                quantite_sortie_tonnes = %s,
                numero_lot_sortie = %s,
                site_destination = %s,
                emplacement_destination = %s,
                terminated_by = %s,
                notes = %s,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
        """, (quantite_sortie, numero_lot_sortie, site_dest, emplacement_dest,
              terminated_by, notes, job_id))
        
        # Créer stock produit fini
        cursor.execute("""
            INSERT INTO stock_emplacements (
                lot_id, site_stockage, emplacement_stockage,
                nombre_unites, poids_total_kg, type_conditionnement,
                type_stock, code_produit_commercial, numero_lot_produit,
                production_job_id, is_active
            ) VALUES (%s, %s, %s, 1, %s, 'PRODUIT_FINI', 'PRODUIT_FINI', %s, %s, %s, TRUE)
        """, (
            job['lot_id'], site_dest, emplacement_dest,
            quantite_sortie * 1000,  # Convertir tonnes en kg
            job['code_produit_commercial'], numero_lot_sortie, job_id
        ))
        
        # Enregistrer mouvement
        cursor.execute("""
            INSERT INTO stock_mouvements (
                lot_id, type_mouvement, site_destination, emplacement_destination,
                quantite, poids_kg, user_action, notes
            ) VALUES (%s, 'PRODUCTION_SORTIE', %s, %s, 1, %s, %s, %s)
        """, (
            job['lot_id'], site_dest, emplacement_dest,
            quantite_sortie * 1000, terminated_by,
            f"Production job #{job_id} - {job['code_produit_commercial']}"
        ))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return True, f"✅ Job terminé - {quantite_sortie:.2f} T produites"
        
    except Exception as e:
        if 'conn' in locals():
            conn.rollback()
        return False, f"❌ Erreur : {str(e)}"

# ==========================================
# AFFICHAGE - KPIs
# ==========================================

kpis = get_kpis_production()

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric("🎯 Jobs Prévus", kpis['nb_prevus'])

with col2:
    st.metric("⚙️ Jobs En Cours", kpis['nb_en_cours'])

with col3:
    st.metric("✅ Jobs Terminés", kpis['nb_termines'])

with col4:
    st.metric("📦 Tonnage Prévu", f"{kpis['tonnage_prevu']:.1f} T")

st.markdown("---")

# ==========================================
# ONGLETS PRINCIPAUX
# ==========================================

tab1, tab2, tab3 = st.tabs(["📅 Calendrier", "📋 Liste Jobs", "➕ Créer Job"])

# ==========================================
# ONGLET 1 : CALENDRIER
# ==========================================

with tab1:
    st.subheader("📅 Planning Journalier")
    
    # Sélecteur de date
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col1:
        if st.button("◀ Jour précédent", key="prev_day_prod"):
            if 'selected_date_prod' not in st.session_state:
                st.session_state.selected_date_prod = datetime.now().date()
            st.session_state.selected_date_prod -= timedelta(days=1)
            st.rerun()
    
    with col2:
        if 'selected_date_prod' not in st.session_state:
            st.session_state.selected_date_prod = datetime.now().date()
        
        selected_date = st.date_input(
            "Date",
            value=st.session_state.selected_date_prod,
            key="date_picker_prod"
        )
        st.session_state.selected_date_prod = selected_date
    
    with col3:
        if st.button("Jour suivant ▶", key="next_day_prod"):
            st.session_state.selected_date_prod += timedelta(days=1)
            st.rerun()
    
    st.markdown("---")
    
    # Charger jobs du jour
    jobs_jour = get_jobs_by_date(st.session_state.selected_date_prod)
    
    if not jobs_jour.empty:
        # Grouper par ligne
        lignes = jobs_jour['ligne_production'].unique()
        
        for ligne in sorted(lignes):
            ligne_libelle = jobs_jour[jobs_jour['ligne_production'] == ligne]['ligne_libelle'].iloc[0]
            st.markdown(f"### 🔧 {ligne} - {ligne_libelle}")
            
            jobs_ligne = jobs_jour[jobs_jour['ligne_production'] == ligne]
            
            for _, job in jobs_ligne.iterrows():
                statut_class = ""
                if job['statut'] == 'EN_COURS':
                    statut_class = "en-cours"
                elif job['statut'] == 'TERMINÉ':
                    statut_class = "termine"
                
                st.markdown(f"""
                <div class="job-card {statut_class}">
                    <strong>Job #{job['id']}</strong> - {job['code_lot_interne']}<br>
                    📦 {job['produit_libelle']}<br>
                    ⚖️ {job['quantite_entree_tonnes']:.2f} T<br>
                    🌱 {job['variete']}<br>
                    ⏱️ {job['temps_estime_heures']:.1f}h - 🏷️ {job['statut']}
                </div>
                """, unsafe_allow_html=True)
            
            st.markdown("<br>", unsafe_allow_html=True)
    else:
        st.info(f"📅 Aucun job prévu le {st.session_state.selected_date_prod.strftime('%d/%m/%Y')}")

# ==========================================
# ONGLET 2 : LISTE JOBS
# ==========================================

with tab2:
    st.subheader("📋 Liste des Jobs")
    
    subtab1, subtab2, subtab3 = st.tabs(["🎯 PRÉVU", "⚙️ EN_COURS", "✅ TERMINÉ"])
    
    with subtab1:
        jobs_prevus = get_jobs_by_statut('PRÉVU')
        
        if not jobs_prevus.empty:
            for _, job in jobs_prevus.iterrows():
                with st.expander(f"Job #{job['id']} - {job['produit_libelle']} - {job['date_prevue']}"):
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.write(f"**Lot** : {job['code_lot_interne']}")
                        st.write(f"**Variété** : {job['variete']}")
                        st.write(f"**Produit** : {job['produit_marque']} - {job['produit_libelle']}")
                        st.write(f"**Quantité** : {job['quantite_entree_tonnes']:.2f} T")
                    
                    with col2:
                        st.write(f"**Date prévue** : {job['date_prevue']}")
                        st.write(f"**Ligne** : {job['ligne_libelle']}")
                        st.write(f"**Temps estimé** : {job['temps_estime_heures']:.1f}h")
                        st.write(f"**Créé par** : {job['created_by']}")
                    
                    if st.button(f"⚙️ Activer Job #{job['id']}", key=f"activate_prod_{job['id']}"):
                        success, message = activer_job(job['id'])
                        if success:
                            st.success(message)
                            st.rerun()
                        else:
                            st.error(message)
        else:
            st.info("Aucun job prévu")
    
    with subtab2:
        jobs_en_cours = get_jobs_by_statut('EN_COURS')
        
        if not jobs_en_cours.empty:
            for _, job in jobs_en_cours.iterrows():
                with st.expander(f"Job #{job['id']} - {job['produit_libelle']} - EN COURS"):
                    st.write(f"**Activé le** : {job['date_activation']}")
                    st.write(f"**Quantité entrée** : {job['quantite_entree_tonnes']:.2f} T")
                    
                    if st.button(f"✅ Terminer Job #{job['id']}", key=f"finish_prod_{job['id']}"):
                        st.session_state[f'show_finish_form_prod_{job["id"]}'] = True
                        st.rerun()
                    
                    # Formulaire terminaison
                    if st.session_state.get(f'show_finish_form_prod_{job["id"]}', False):
                        st.markdown("---")
                        st.markdown("##### Résultats de production")
                        
                        col1, col2 = st.columns(2)
                        
                        with col1:
                            quantite_sortie = st.number_input(
                                "Quantité produite (T) *",
                                min_value=0.0,
                                value=float(job['quantite_entree_tonnes']),
                                step=0.1,
                                key=f"qte_sortie_{job['id']}"
                            )
                            
                            # Générer numéro lot automatique
                            default_lot = f"PF_{job['code_lot_interne']}_{datetime.now().strftime('%Y%m%d')}"
                            numero_lot = st.text_input(
                                "Numéro lot sortie *",
                                value=default_lot,
                                key=f"num_lot_{job['id']}"
                            )
                        
                        with col2:
                            # Site destination (récupérer depuis ligne production)
                            lignes = get_lignes_production()
                            ligne_info = next((l for l in lignes if l['code'] == job['ligne_production']), None)
                            site_dest = ligne_info['site'] if ligne_info else 'SAINT_FLAVY'
                            
                            st.write(f"**Site** : {site_dest}")
                            
                            emplacements = get_emplacements_site(site_dest)
                            emplacement_dest = st.selectbox(
                                "Emplacement destination *",
                                options=[""] + [e[0] for e in emplacements],
                                key=f"empl_prod_{job['id']}"
                            )
                        
                        notes_fin = st.text_area("Notes", key=f"notes_prod_{job['id']}")
                        
                        col_save, col_cancel = st.columns(2)
                        
                        with col_save:
                            if st.button("💾 Valider", key=f"save_finish_prod_{job['id']}", type="primary"):
                                if not emplacement_dest:
                                    st.error("❌ Emplacement obligatoire")
                                elif not numero_lot:
                                    st.error("❌ Numéro de lot obligatoire")
                                else:
                                    success, message = terminer_job(
                                        job['id'], quantite_sortie, numero_lot,
                                        site_dest, emplacement_dest, notes_fin
                                    )
                                    if success:
                                        st.success(message)
                                        st.balloons()
                                        st.session_state.pop(f'show_finish_form_prod_{job["id"]}')
                                        st.rerun()
                                    else:
                                        st.error(message)
                        
                        with col_cancel:
                            if st.button("❌ Annuler", key=f"cancel_finish_prod_{job['id']}"):
                                st.session_state.pop(f'show_finish_form_prod_{job["id"]}')
                                st.rerun()
        else:
            st.info("Aucun job en cours")
    
    with subtab3:
        jobs_termines = get_jobs_by_statut('TERMINÉ')
        
        if not jobs_termines.empty:
            st.dataframe(
                jobs_termines[['id', 'code_lot_interne', 'produit_libelle', 'quantite_entree_tonnes', 
                              'quantite_sortie_tonnes', 'numero_lot_sortie', 'date_prevue', 'date_terminaison']],
                use_container_width=True,
                hide_index=True,
                column_config={
                    'id': 'Job #',
                    'code_lot_interne': 'Lot Source',
                    'produit_libelle': 'Produit',
                    'quantite_entree_tonnes': st.column_config.NumberColumn('Entrée (T)', format="%.2f"),
                    'quantite_sortie_tonnes': st.column_config.NumberColumn('Sortie (T)', format="%.2f"),
                    'numero_lot_sortie': 'N° Lot Sortie',
                    'date_prevue': 'Date Prévue',
                    'date_terminaison': 'Terminé le'
                }
            )
        else:
            st.info("Aucun job terminé")

# ==========================================
# ONGLET 3 : CRÉER JOB
# ==========================================

with tab3:
    st.subheader("➕ Créer un Job de Production")
    
    # Deux modes : depuis affectation ou manuel
    mode = st.radio(
        "Mode de création",
        ["📋 Depuis une affectation", "✏️ Création manuelle"],
        horizontal=True,
        key="mode_creation_prod"
    )
    
    st.markdown("---")
    
    if mode == "📋 Depuis une affectation":
        # Charger affectations
        affectations = get_affectations_pour_production()
        
        if not affectations.empty:
            st.markdown("**Affectations disponibles** - Sélectionnez pour créer un job")
            
            # Tableau affectations
            df_display = affectations[[
                'affectation_id', 'lot_id', 'code_lot_interne', 'variete',
                'code_produit_commercial', 'produit_libelle', 'produit_marque',
                'semaine', 'poids_net_estime_tonnes', 'statut_stock'
            ]].copy()
            
            df_display = df_display.rename(columns={
                'code_lot_interne': 'Lot',
                'variete': 'Variété',
                'produit_libelle': 'Produit',
                'produit_marque': 'Marque',
                'semaine': 'Sem.',
                'poids_net_estime_tonnes': 'Tonnage Net',
                'statut_stock': 'Type Stock'
            })
            
            event = st.dataframe(
                df_display,
                use_container_width=True,
                hide_index=True,
                on_select="rerun",
                selection_mode="single-row",
                column_config={
                    'affectation_id': None,
                    'lot_id': None,
                    'code_produit_commercial': None,
                    'Tonnage Net': st.column_config.NumberColumn(format="%.2f T")
                },
                key="affectations_table_prod"
            )
            
            selected_rows = event.selection.rows if hasattr(event, 'selection') else []
            
            if len(selected_rows) > 0:
                selected_idx = selected_rows[0]
                selected_aff = affectations.iloc[selected_idx]
                
                st.success(f"✅ Affectation sélectionnée : {selected_aff['produit_libelle']} - {selected_aff['poids_net_estime_tonnes']:.2f} T")
                
                if st.button("➕ Créer Job depuis cette affectation", type="primary", key="btn_create_from_aff"):
                    st.session_state['selected_affectation'] = selected_aff.to_dict()
                    st.session_state['show_create_form_prod'] = True
                    st.rerun()
        else:
            st.info("Aucune affectation disponible. Créez d'abord des affectations sur la page 07.")
    
    else:
        # Mode manuel
        stock_lave = get_stock_lave_disponible()
        
        if not stock_lave.empty:
            st.markdown("**Stock LAVÉ disponible** - Sélectionnez pour créer un job")
            
            # Tableau stock
            df_display = stock_lave[[
                'lot_id', 'emplacement_id', 'code_lot_interne', 'variete',
                'site_stockage', 'emplacement_stockage', 'poids_total_kg'
            ]].copy()
            
            df_display['poids_tonnes'] = df_display['poids_total_kg'] / 1000
            
            df_display = df_display.rename(columns={
                'code_lot_interne': 'Lot',
                'variete': 'Variété',
                'site_stockage': 'Site',
                'emplacement_stockage': 'Emplacement',
                'poids_tonnes': 'Tonnage'
            })
            
            event = st.dataframe(
                df_display,
                use_container_width=True,
                hide_index=True,
                on_select="rerun",
                selection_mode="single-row",
                column_config={
                    'lot_id': None,
                    'emplacement_id': None,
                    'poids_total_kg': None,
                    'Tonnage': st.column_config.NumberColumn(format="%.2f T")
                },
                key="stock_table_prod"
            )
            
            selected_rows = event.selection.rows if hasattr(event, 'selection') else []
            
            if len(selected_rows) > 0:
                selected_idx = selected_rows[0]
                selected_stock = stock_lave.iloc[selected_idx]
                
                st.success(f"✅ Stock sélectionné : {selected_stock['code_lot_interne']} - {selected_stock['poids_total_kg']/1000:.2f} T")
                
                if st.button("➕ Créer Job manuel", type="primary", key="btn_create_manual"):
                    st.session_state['selected_stock_prod'] = selected_stock.to_dict()
                    st.session_state['show_create_form_prod_manual'] = True
                    st.rerun()
        else:
            st.warning("⚠️ Aucun stock LAVÉ disponible pour production")
    
    # ==========================================
    # FORMULAIRE CRÉATION (depuis affectation)
    # ==========================================
    if st.session_state.get('show_create_form_prod', False) and 'selected_affectation' in st.session_state:
        st.markdown("---")
        st.markdown("### 📋 Paramètres du Job")
        
        aff = st.session_state['selected_affectation']
        
        st.info(f"**Produit** : {aff['produit_marque']} - {aff['produit_libelle']} | **Lot** : {aff['code_lot_interne']} | **Tonnage** : {aff['poids_net_estime_tonnes']:.2f} T")
        
        col1, col2 = st.columns(2)
        
        with col1:
            quantite = st.number_input(
                "Quantité à produire (T) *",
                min_value=0.1,
                max_value=float(aff['poids_net_estime_tonnes']),
                value=float(aff['poids_net_estime_tonnes']),
                step=0.1,
                key="qte_prod_aff"
            )
            
            date_prevue = st.date_input(
                "Date prévue *",
                value=datetime.now().date(),
                key="date_prod_aff"
            )
        
        with col2:
            lignes = get_lignes_production()
            
            # Filtrer par atelier du produit si possible
            atelier_produit = aff.get('produit_atelier')
            if atelier_produit:
                lignes_filtrees = [l for l in lignes if l['type_atelier'] == atelier_produit]
                if not lignes_filtrees:
                    lignes_filtrees = lignes
            else:
                lignes_filtrees = lignes
            
            if lignes_filtrees:
                ligne_options = [f"{l['code']} - {l['libelle']} ({l['site']}, {l['capacite_th']}T/h)" for l in lignes_filtrees]
                selected_ligne = st.selectbox("Ligne de production *", options=ligne_options, key="ligne_prod_aff")
                
                ligne_idx = ligne_options.index(selected_ligne)
                capacite = float(lignes_filtrees[ligne_idx]['capacite_th'])
                temps_estime = quantite / capacite
                
                st.metric("Temps estimé", f"{temps_estime:.1f} heures")
            else:
                st.error("❌ Aucune ligne de production disponible")
                capacite = None
            
            # Sur-emballage
            sur_emballages = get_sur_emballages()
            if sur_emballages:
                se_options = ["(Aucun)"] + [f"{s['code']} - {s['libelle']}" for s in sur_emballages]
                selected_se = st.selectbox("Sur-emballage", options=se_options, key="se_prod_aff")
                sur_emb_code = None if selected_se == "(Aucun)" else sur_emballages[se_options.index(selected_se) - 1]['code']
            else:
                sur_emb_code = None
        
        notes = st.text_area("Notes", key="notes_prod_aff")
        
        col_save, col_cancel = st.columns(2)
        
        with col_save:
            if st.button("✅ Créer le Job", type="primary", use_container_width=True, key="btn_create_job_aff"):
                if capacite:
                    ligne_code = lignes_filtrees[ligne_idx]['code']
                    
                    success, message = create_job_production(
                        aff['lot_id'], aff['code_lot_interne'], aff['variete'],
                        aff['code_produit_commercial'], quantite, date_prevue,
                        ligne_code, capacite, sur_emb_code, aff['affectation_id'], notes
                    )
                    
                    if success:
                        st.success(message)
                        st.balloons()
                        st.session_state.pop('show_create_form_prod', None)
                        st.session_state.pop('selected_affectation', None)
                        st.rerun()
                    else:
                        st.error(message)
        
        with col_cancel:
            if st.button("❌ Annuler", use_container_width=True, key="btn_cancel_aff"):
                st.session_state.pop('show_create_form_prod', None)
                st.session_state.pop('selected_affectation', None)
                st.rerun()
    
    # ==========================================
    # FORMULAIRE CRÉATION (manuel)
    # ==========================================
    if st.session_state.get('show_create_form_prod_manual', False) and 'selected_stock_prod' in st.session_state:
        st.markdown("---")
        st.markdown("### 📋 Paramètres du Job (Manuel)")
        
        stock = st.session_state['selected_stock_prod']
        
        st.info(f"**Lot** : {stock['code_lot_interne']} | **Variété** : {stock['variete']} | **Stock** : {stock['poids_total_kg']/1000:.2f} T")
        
        col1, col2 = st.columns(2)
        
        with col1:
            # Sélection produit
            produits = get_produits_commerciaux()
            if produits:
                prod_options = [f"{p['code_produit']} - {p['marque']} {p['libelle']}" for p in produits]
                selected_prod = st.selectbox("Produit à fabriquer *", options=prod_options, key="prod_manual")
                prod_idx = prod_options.index(selected_prod)
                code_produit = produits[prod_idx]['code_produit']
            else:
                st.error("❌ Aucun produit commercial disponible")
                code_produit = None
            
            quantite = st.number_input(
                "Quantité à produire (T) *",
                min_value=0.1,
                max_value=float(stock['poids_total_kg']) / 1000,
                value=min(float(stock['poids_total_kg']) / 1000, 5.0),
                step=0.1,
                key="qte_prod_manual"
            )
            
            date_prevue = st.date_input(
                "Date prévue *",
                value=datetime.now().date(),
                key="date_prod_manual"
            )
        
        with col2:
            lignes = get_lignes_production()
            if lignes:
                ligne_options = [f"{l['code']} - {l['libelle']} ({l['site']}, {l['capacite_th']}T/h)" for l in lignes]
                selected_ligne = st.selectbox("Ligne de production *", options=ligne_options, key="ligne_prod_manual")
                
                ligne_idx = ligne_options.index(selected_ligne)
                capacite = float(lignes[ligne_idx]['capacite_th'])
                temps_estime = quantite / capacite
                
                st.metric("Temps estimé", f"{temps_estime:.1f} heures")
            else:
                st.error("❌ Aucune ligne de production disponible")
                capacite = None
            
            # Sur-emballage
            sur_emballages = get_sur_emballages()
            if sur_emballages:
                se_options = ["(Aucun)"] + [f"{s['code']} - {s['libelle']}" for s in sur_emballages]
                selected_se = st.selectbox("Sur-emballage", options=se_options, key="se_prod_manual")
                sur_emb_code = None if selected_se == "(Aucun)" else sur_emballages[se_options.index(selected_se) - 1]['code']
            else:
                sur_emb_code = None
        
        notes = st.text_area("Notes", key="notes_prod_manual")
        
        col_save, col_cancel = st.columns(2)
        
        with col_save:
            if st.button("✅ Créer le Job", type="primary", use_container_width=True, key="btn_create_job_manual"):
                if capacite and code_produit:
                    ligne_code = lignes[ligne_idx]['code']
                    
                    success, message = create_job_production(
                        stock['lot_id'], stock['code_lot_interne'], stock['variete'],
                        code_produit, quantite, date_prevue,
                        ligne_code, capacite, sur_emb_code, None, notes
                    )
                    
                    if success:
                        st.success(message)
                        st.balloons()
                        st.session_state.pop('show_create_form_prod_manual', None)
                        st.session_state.pop('selected_stock_prod', None)
                        st.rerun()
                    else:
                        st.error(message)
        
        with col_cancel:
            if st.button("❌ Annuler", use_container_width=True, key="btn_cancel_manual"):
                st.session_state.pop('show_create_form_prod_manual', None)
                st.session_state.pop('selected_stock_prod', None)
                st.rerun()

show_footer()
