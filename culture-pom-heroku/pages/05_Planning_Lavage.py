import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from database import get_connection
from components import show_footer
from auth import is_authenticated
import io

st.set_page_config(page_title="Planning Lavage - Culture Pom", page_icon="🧼", layout="wide")

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

st.title("🧼 Planning Lavage")
st.markdown("*Gestion des jobs de lavage - SAINT_FLAVY uniquement*")
st.markdown("---")

# ==========================================
# FONCTIONS UTILITAIRES
# ==========================================

def get_lots_bruts_disponibles():
    """Récupère les lots bruts disponibles pour lavage"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        query = """
        SELECT 
            l.id as lot_id,
            l.code_lot_interne,
            l.nom_usage,
            COALESCE(v.nom_variete, l.code_variete) as variete,
            se.id as emplacement_id,
            se.site_stockage,
            se.emplacement_stockage,
            se.nombre_unites,
            se.poids_total_kg,
            se.type_conditionnement
        FROM lots_bruts l
        JOIN stock_emplacements se ON l.id = se.lot_id
        LEFT JOIN ref_varietes v ON l.code_variete = v.code_variete
        WHERE se.is_active = TRUE 
          AND se.statut_lavage = 'BRUT'
          AND se.nombre_unites > 0
        ORDER BY l.code_lot_interne
        """
        
        cursor.execute(query)
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        
        if rows:
            return pd.DataFrame(rows)
        return pd.DataFrame()
        
    except Exception as e:
        st.error(f"❌ Erreur chargement lots : {str(e)}")
        return pd.DataFrame()

def get_emplacements_saint_flavy():
    """Récupère les emplacements disponibles à SAINT_FLAVY"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        query = """
        SELECT code_emplacement, nom_complet
        FROM ref_sites_stockage
        WHERE code_site = 'SAINT_FLAVY' AND is_active = TRUE
        ORDER BY code_emplacement
        """
        
        cursor.execute(query)
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        
        if rows:
            return [(row['code_emplacement'], row['nom_complet']) for row in rows]
        return []
        
    except Exception as e:
        st.error(f"❌ Erreur : {str(e)}")
        return []

def get_lignes_lavage():
    """Récupère les lignes de lavage actives"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT code, libelle, capacite_th, temps_transition_minutes
            FROM lavages_lignes
            WHERE is_active = TRUE
            ORDER BY code
        """)
        
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        
        return rows if rows else []
        
    except Exception as e:
        st.error(f"❌ Erreur : {str(e)}")
        return []

def get_kpis_lavage():
    """Récupère les KPIs de lavage"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Jobs prévus
        cursor.execute("SELECT COUNT(*) as nb FROM lavages_jobs WHERE statut = 'PRÉVU'")
        nb_prevus = cursor.fetchone()['nb']
        
        # Jobs en cours
        cursor.execute("SELECT COUNT(*) as nb FROM lavages_jobs WHERE statut = 'EN_COURS'")
        nb_en_cours = cursor.fetchone()['nb']
        
        # Jobs terminés
        cursor.execute("SELECT COUNT(*) as nb FROM lavages_jobs WHERE statut = 'TERMINÉ'")
        nb_termines = cursor.fetchone()['nb']
        
        # Temps total prévu
        cursor.execute("SELECT COALESCE(SUM(temps_estime_heures), 0) as total FROM lavages_jobs WHERE statut IN ('PRÉVU', 'EN_COURS')")
        temps_total = cursor.fetchone()['total']
        
        cursor.close()
        conn.close()
        
        return {
            'nb_prevus': nb_prevus,
            'nb_en_cours': nb_en_cours,
            'nb_termines': nb_termines,
            'temps_total': float(temps_total)
        }
        
    except Exception as e:
        st.error(f"❌ Erreur KPIs : {str(e)}")
        return None

def get_jobs_by_date(date):
    """Récupère les jobs pour une date donnée"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        query = """
        SELECT 
            lj.id,
            lj.lot_id,
            lj.code_lot_interne,
            lj.variete,
            lj.quantite_pallox,
            lj.poids_brut_kg,
            lj.ligne_lavage,
            lj.temps_estime_heures,
            lj.statut,
            lj.created_by,
            lj.notes
        FROM lavages_jobs lj
        WHERE lj.date_prevue = %s
        ORDER BY lj.ligne_lavage, lj.created_at
        """
        
        cursor.execute(query, (date,))
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        
        if rows:
            return pd.DataFrame(rows)
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
            lj.id,
            lj.lot_id,
            lj.code_lot_interne,
            lj.variete,
            lj.quantite_pallox,
            lj.poids_brut_kg,
            lj.date_prevue,
            lj.ligne_lavage,
            lj.temps_estime_heures,
            lj.statut,
            lj.created_by,
            lj.created_at,
            lj.date_activation,
            lj.date_terminaison
        FROM lavages_jobs lj
        WHERE lj.statut = %s
        ORDER BY lj.date_prevue DESC, lj.created_at DESC
        """
        
        cursor.execute(query, (statut,))
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        
        if rows:
            return pd.DataFrame(rows)
        return pd.DataFrame()
        
    except Exception as e:
        st.error(f"❌ Erreur : {str(e)}")
        return pd.DataFrame()

def create_job_lavage(lot_id, emplacement_id, quantite_pallox, poids_brut_kg, 
                     date_prevue, ligne_lavage, capacite_th, notes=""):
    """Crée un nouveau job de lavage"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Récupérer infos lot
        cursor.execute("""
            SELECT l.code_lot_interne, COALESCE(v.nom_variete, l.code_variete) as variete
            FROM lots_bruts l
            LEFT JOIN ref_varietes v ON l.code_variete = v.code_variete
            WHERE l.id = %s
        """, (lot_id,))
        lot_info = cursor.fetchone()
        
        # Calculer temps estimé
        temps_estime = (poids_brut_kg / 1000) / capacite_th  # heures
        
        # Insérer job
        created_by = st.session_state.get('username', 'system')
        
        query = """
        INSERT INTO lavages_jobs (
            lot_id, code_lot_interne, variete, quantite_pallox, poids_brut_kg,
            date_prevue, ligne_lavage, capacite_th, temps_estime_heures,
            statut, created_by, notes
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'PRÉVU', %s, %s)
        RETURNING id
        """
        
        cursor.execute(query, (
            lot_id, lot_info['code_lot_interne'], lot_info['variete'],
            quantite_pallox, poids_brut_kg, date_prevue, ligne_lavage,
            capacite_th, temps_estime, created_by, notes
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
            UPDATE lavages_jobs
            SET statut = 'EN_COURS',
                date_activation = CURRENT_TIMESTAMP,
                activated_by = %s
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

def terminer_job(job_id, poids_lave, poids_grenailles, poids_dechets,
                site_dest, emplacement_dest, notes=""):
    """Termine un job et crée les stocks résultants"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Récupérer job
        cursor.execute("""
            SELECT lot_id, quantite_pallox, poids_brut_kg,
                   code_lot_interne, ligne_lavage
            FROM lavages_jobs
            WHERE id = %s AND statut = 'EN_COURS'
        """, (job_id,))
        
        job = cursor.fetchone()
        if not job:
            return False, "❌ Job introuvable ou pas EN_COURS"
        
        # Calculs
        poids_brut = float(job['poids_brut_kg'])
        poids_terre = poids_brut - poids_lave - poids_grenailles - poids_dechets
        tare_reelle = ((poids_dechets + poids_terre) / poids_brut) * 100
        rendement = ((poids_lave + poids_grenailles) / poids_brut) * 100
        
        # Validation
        if abs(poids_brut - (poids_lave + poids_grenailles + poids_dechets + poids_terre)) > 1:
            return False, f"❌ Poids incohérents : Brut={poids_brut:.0f} vs Total={poids_lave+poids_grenailles+poids_dechets+poids_terre:.0f}"
        
        # Mettre à jour job
        terminated_by = st.session_state.get('username', 'system')
        
        cursor.execute("""
            UPDATE lavages_jobs
            SET statut = 'TERMINÉ',
                date_terminaison = CURRENT_TIMESTAMP,
                poids_lave_net_kg = %s,
                poids_grenailles_kg = %s,
                poids_dechets_kg = %s,
                poids_terre_calcule_kg = %s,
                tare_reelle_pct = %s,
                rendement_pct = %s,
                site_destination = %s,
                emplacement_destination = %s,
                terminated_by = %s,
                notes = %s
            WHERE id = %s
        """, (poids_lave, poids_grenailles, poids_dechets, poids_terre,
              tare_reelle, rendement, site_dest, emplacement_dest,
              terminated_by, notes, job_id))
        
        # TODO: Créer les nouveaux stock_emplacements (LAVÉ + GRENAILLES)
        # TODO: Déduire du stock BRUT source
        # TODO: Créer mouvements de stock
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return True, f"✅ Job terminé - Rendement: {rendement:.1f}%"
        
    except Exception as e:
        if 'conn' in locals():
            conn.rollback()
        return False, f"❌ Erreur : {str(e)}"

# ==========================================
# AFFICHAGE - KPIs
# ==========================================

kpis = get_kpis_lavage()

if kpis:
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("🎯 Jobs Prévus", kpis['nb_prevus'])
    
    with col2:
        st.metric("⚙️ Jobs En Cours", kpis['nb_en_cours'])
    
    with col3:
        st.metric("✅ Jobs Terminés", kpis['nb_termines'])
    
    with col4:
        st.metric("⏱️ Temps Prévu/En Cours", f"{kpis['temps_total']:.1f}h")

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
        if st.button("◀ Jour précédent"):
            if 'selected_date' not in st.session_state:
                st.session_state.selected_date = datetime.now().date()
            st.session_state.selected_date -= timedelta(days=1)
            st.rerun()
    
    with col2:
        if 'selected_date' not in st.session_state:
            st.session_state.selected_date = datetime.now().date()
        
        selected_date = st.date_input(
            "Date",
            value=st.session_state.selected_date,
            key="date_picker"
        )
        st.session_state.selected_date = selected_date
    
    with col3:
        if st.button("Jour suivant ▶"):
            st.session_state.selected_date += timedelta(days=1)
            st.rerun()
    
    st.markdown("---")
    
    # Charger jobs du jour
    jobs_jour = get_jobs_by_date(st.session_state.selected_date)
    
    if not jobs_jour.empty:
        # Grouper par ligne
        lignes = jobs_jour['ligne_lavage'].unique()
        
        for ligne in sorted(lignes):
            st.markdown(f"### 🔧 {ligne}")
            
            jobs_ligne = jobs_jour[jobs_jour['ligne_lavage'] == ligne]
            
            for _, job in jobs_ligne.iterrows():
                statut_class = ""
                if job['statut'] == 'EN_COURS':
                    statut_class = "en-cours"
                elif job['statut'] == 'TERMINÉ':
                    statut_class = "termine"
                
                st.markdown(f"""
                <div class="job-card {statut_class}">
                    <strong>Job #{job['id']}</strong> - {job['code_lot_interne']}<br>
                    📦 {job['quantite_pallox']} pallox - ⚖️ {job['poids_brut_kg']/1000:.1f} T<br>
                    🌱 {job['variete']}<br>
                    ⏱️ {job['temps_estime_heures']:.1f}h - 🏷️ {job['statut']}
                </div>
                """, unsafe_allow_html=True)
            
            st.markdown("<br>", unsafe_allow_html=True)
    else:
        st.info(f"📅 Aucun job prévu le {st.session_state.selected_date.strftime('%d/%m/%Y')}")

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
                with st.expander(f"Job #{job['id']} - {job['code_lot_interne']} - {job['date_prevue']}"):
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.write(f"**Lot** : {job['code_lot_interne']}")
                        st.write(f"**Variété** : {job['variete']}")
                        st.write(f"**Quantité** : {job['quantite_pallox']} pallox")
                        st.write(f"**Poids** : {job['poids_brut_kg']/1000:.1f} T")
                    
                    with col2:
                        st.write(f"**Date prévue** : {job['date_prevue']}")
                        st.write(f"**Ligne** : {job['ligne_lavage']}")
                        st.write(f"**Temps estimé** : {job['temps_estime_heures']:.1f}h")
                        st.write(f"**Créé par** : {job['created_by']}")
                    
                    if st.button(f"⚙️ Activer Job #{job['id']}", key=f"activate_{job['id']}"):
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
                with st.expander(f"Job #{job['id']} - {job['code_lot_interne']} - EN COURS"):
                    st.write(f"**Activé le** : {job['date_activation']}")
                    st.write(f"**Poids brut** : {job['poids_brut_kg']:.0f} kg")
                    
                    if st.button(f"✅ Terminer Job #{job['id']}", key=f"finish_{job['id']}"):
                        st.session_state[f'show_finish_form_{job['id']}'] = True
                        st.rerun()
                    
                    # Formulaire terminaison
                    if st.session_state.get(f'show_finish_form_{job['id']}', False):
                        st.markdown("---")
                        st.markdown("##### Saisir les tares réelles")
                        
                        col1, col2 = st.columns(2)
                        
                        with col1:
                            poids_lave = st.number_input(
                                "Poids lavé net (kg) *",
                                min_value=0.0,
                                value=float(job['poids_brut_kg']) * 0.75,
                                step=100.0,
                                key=f"poids_lave_{job['id']}"
                            )
                            
                            poids_grenailles = st.number_input(
                                "Poids grenailles (kg) *",
                                min_value=0.0,
                                value=float(job['poids_brut_kg']) * 0.05,
                                step=10.0,
                                key=f"poids_grenailles_{job['id']}"
                            )
                        
                        with col2:
                            poids_dechets = st.number_input(
                                "Poids déchets (kg) *",
                                min_value=0.0,
                                value=float(job['poids_brut_kg']) * 0.05,
                                step=10.0,
                                key=f"poids_dechets_{job['id']}"
                            )
                            
                            poids_terre_calc = float(job['poids_brut_kg']) - poids_lave - poids_grenailles - poids_dechets
                            st.metric("Terre calculée", f"{poids_terre_calc:.0f} kg")
                        
                        st.markdown("---")
                        
                        emplacements = get_emplacements_saint_flavy()
                        site_dest = "SAINT_FLAVY"
                        emplacement_dest = st.selectbox(
                            "Emplacement destination *",
                            options=[""] + [e[0] for e in emplacements],
                            key=f"empl_{job['id']}"
                        )
                        
                        notes_fin = st.text_area("Notes", key=f"notes_{job['id']}")
                        
                        col_save, col_cancel = st.columns(2)
                        
                        with col_save:
                            if st.button("💾 Valider", key=f"save_finish_{job['id']}", type="primary"):
                                if not emplacement_dest:
                                    st.error("❌ Emplacement obligatoire")
                                else:
                                    success, message = terminer_job(
                                        job['id'], poids_lave, poids_grenailles, poids_dechets,
                                        site_dest, emplacement_dest, notes_fin
                                    )
                                    if success:
                                        st.success(message)
                                        st.session_state.pop(f'show_finish_form_{job["id"]}')
                                        st.rerun()
                                    else:
                                        st.error(message)
                        
                        with col_cancel:
                            if st.button("❌ Annuler", key=f"cancel_finish_{job['id']}"):
                                st.session_state.pop(f'show_finish_form_{job["id"]}')
                                st.rerun()
        else:
            st.info("Aucun job en cours")
    
    with subtab3:
        jobs_termines = get_jobs_by_statut('TERMINÉ')
        
        if not jobs_termines.empty:
            st.dataframe(
                jobs_termines[['id', 'code_lot_interne', 'variete', 'poids_brut_kg', 'date_prevue', 'date_terminaison']],
                use_container_width=True,
                hide_index=True
            )
        else:
            st.info("Aucun job terminé")

# ==========================================
# ONGLET 3 : CRÉER JOB
# ==========================================

with tab3:
    st.subheader("➕ Créer un Job de Lavage")
    
    # Charger lots disponibles
    lots_dispo = get_lots_bruts_disponibles()
    
    if not lots_dispo.empty:
        # Sélection lot
        lot_options = [""] + [
            f"{row['code_lot_interne']} - {row['variete']} - {row['site_stockage']}/{row['emplacement_stockage']} ({int(row['nombre_unites'])} pallox)"
            for _, row in lots_dispo.iterrows()
        ]
        
        selected_lot_str = st.selectbox("Lot à laver *", options=lot_options, key="select_lot")
        
        if selected_lot_str:
            # Extraire index du lot
            lot_idx = lot_options.index(selected_lot_str) - 1
            lot_data = lots_dispo.iloc[lot_idx]
            
            col1, col2 = st.columns(2)
            
            with col1:
                quantite = st.slider(
                    "Quantité à laver (pallox) *",
                    min_value=1,
                    max_value=int(lot_data['nombre_unites']),
                    value=min(5, int(lot_data['nombre_unites'])),
                    key="quantite"
                )
                
                date_prevue = st.date_input(
                    "Date prévue *",
                    value=datetime.now().date(),
                    key="date_prevue"
                )
            
            with col2:
                lignes = get_lignes_lavage()
                ligne_options = [f"{l['code']} - {l['libelle']} ({l['capacite_th']}T/h)" for l in lignes]
                selected_ligne = st.selectbox("Ligne de lavage *", options=ligne_options, key="ligne")
                
                # Calculer poids et temps
                if lot_data['type_conditionnement'] == 'Pallox':
                    poids_unitaire = 1900
                elif lot_data['type_conditionnement'] == 'Petit Pallox':
                    poids_unitaire = 1200
                elif lot_data['type_conditionnement'] == 'Big Bag':
                    poids_unitaire = 1600
                else:
                    poids_unitaire = 1900
                
                poids_brut = quantite * poids_unitaire
                
                ligne_idx = ligne_options.index(selected_ligne)
                capacite = lignes[ligne_idx]['capacite_th']
                temps_estime = (poids_brut / 1000) / capacite
                
                st.metric("Poids brut à laver", f"{poids_brut:.0f} kg ({poids_brut/1000:.1f} T)")
                st.metric("Temps estimé", f"{temps_estime:.1f} heures")
            
            notes = st.text_area("Notes (optionnel)", key="notes_create")
            
            if st.button("✅ Créer le Job", type="primary", use_container_width=True):
                ligne_code = lignes[ligne_idx]['code']
                
                success, message = create_job_lavage(
                    lot_data['lot_id'],
                    lot_data['emplacement_id'],
                    quantite,
                    poids_brut,
                    date_prevue,
                    ligne_code,
                    capacite,
                    notes
                )
                
                if success:
                    st.success(message)
                    st.balloons()
                    st.rerun()
                else:
                    st.error(message)
    else:
        st.warning("⚠️ Aucun lot BRUT disponible pour lavage")

show_footer()
