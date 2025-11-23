import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from database import get_connection
from components import show_footer
from auth import is_authenticated
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode, JsCode

st.set_page_config(page_title="Aide Planning - Culture Pom", page_icon="🗓️", layout="wide")

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
        background-color: #f0f2f6;
        padding: 1rem;
        border-radius: 0.5rem;
        margin: 0.5rem 0;
    }
    .charge-green { color: #2ca02c; font-weight: bold; }
    .charge-yellow { color: #ff7f0e; font-weight: bold; }
    .charge-red { color: #d62728; font-weight: bold; }
    .day-card {
        background-color: #ffffff;
        border: 1px solid #e0e0e0;
        border-radius: 0.5rem;
        padding: 1rem;
        margin: 0.5rem 0;
    }
    .job-item {
        background-color: #f8f9fa;
        border-left: 4px solid #1f77b4;
        padding: 0.5rem;
        margin: 0.3rem 0;
        border-radius: 0.3rem;
    }
    .job-item.ligne2 {
        border-left-color: #2ca02c;
    }
</style>
""", unsafe_allow_html=True)

if not is_authenticated():
    st.warning("⚠️ Veuillez vous connecter pour accéder à cette page")
    st.stop()

st.title("🗓️ Aide Planning Lavage Hebdomadaire")
st.markdown("*Organisez vos jobs de lavage pour la semaine - Calculs automatiques de capacité*")
st.markdown("---")

# ==========================================
# FONCTIONS UTILITAIRES
# ==========================================

def get_week_dates(date):
    """Retourne les dates de la semaine (lundi à samedi)"""
    # Trouver le lundi de la semaine
    days_since_monday = date.weekday()
    monday = date - timedelta(days=days_since_monday)
    
    # Générer lundi à samedi
    week_dates = []
    for i in range(6):  # 0=lundi, 5=samedi
        week_dates.append(monday + timedelta(days=i))
    
    return week_dates

def get_week_number(date):
    """Retourne année et numéro de semaine ISO"""
    iso = date.isocalendar()
    return iso[0], iso[1]  # année, semaine

def calculate_capacity_hours(horaire_debut, horaire_fin):
    """Calcule la capacité en heures entre deux horaires"""
    try:
        h_debut = datetime.strptime(horaire_debut, "%H:%M")
        h_fin = datetime.strptime(horaire_fin, "%H:%M")
        delta = h_fin - h_debut
        return delta.total_seconds() / 3600
    except:
        return 17.0  # Valeur par défaut

def format_time(hours):
    """Convertit heures décimales en HH:MM"""
    h = int(hours)
    m = int((hours - h) * 60)
    return f"{h:02d}:{m:02d}"

def get_charge_color(percentage):
    """Retourne la classe CSS selon le % de charge"""
    if percentage < 60:
        return "🟢", "charge-green"
    elif percentage < 85:
        return "🟡", "charge-yellow"
    else:
        return "🔴", "charge-red"

def get_jobs_prevus_semaine(week_dates):
    """Récupère tous les jobs PRÉVU de la semaine"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        date_debut = week_dates[0]
        date_fin = week_dates[-1]
        
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
            lj.capacite_th,
            lj.temps_estime_heures,
            lj.created_at,
            l.nom_usage,
            l.calibre_min,
            l.calibre_max
        FROM lavages_jobs lj
        JOIN lots_bruts l ON lj.lot_id = l.id
        WHERE lj.statut = 'PRÉVU'
          AND lj.date_prevue >= %s
          AND lj.date_prevue <= %s
        ORDER BY lj.created_at
        """
        
        cursor.execute(query, (date_debut, date_fin))
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        
        if rows:
            df = pd.DataFrame(rows)
            # Convertir colonnes numériques
            numeric_cols = ['quantite_pallox', 'poids_brut_kg', 'temps_estime_heures', 'capacite_th', 'calibre_min', 'calibre_max']
            for col in numeric_cols:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
            return df
        return pd.DataFrame()
        
    except Exception as e:
        st.error(f"❌ Erreur chargement jobs : {str(e)}")
        return pd.DataFrame()

def get_planning_semaine(annee, semaine):
    """Récupère le planning sauvegardé pour une semaine"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT job_id, date_prevue, ligne_lavage, ordre_jour
            FROM lavages_planning_semaine
            WHERE annee = %s AND semaine = %s
            ORDER BY date_prevue, ligne_lavage, ordre_jour
        """, (annee, semaine))
        
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        
        if rows:
            return pd.DataFrame(rows)
        return pd.DataFrame()
        
    except Exception as e:
        # Table n'existe peut-être pas encore
        return pd.DataFrame()

def save_planning_semaine(annee, semaine, planning_data):
    """Sauvegarde le planning de la semaine"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Supprimer ancien planning
        cursor.execute("""
            DELETE FROM lavages_planning_semaine 
            WHERE annee = %s AND semaine = %s
        """, (annee, semaine))
        
        # Insérer nouveau planning
        created_by = st.session_state.get('username', 'system')
        
        for entry in planning_data:
            cursor.execute("""
                INSERT INTO lavages_planning_semaine
                (job_id, annee, semaine, date_prevue, ligne_lavage, ordre_jour, created_by)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (
                entry['job_id'],
                annee,
                semaine,
                entry['date'],
                entry['ligne'],
                entry['ordre'],
                created_by
            ))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return True, "✅ Planning sauvegardé"
        
    except Exception as e:
        if 'conn' in locals():
            conn.rollback()
        return False, f"❌ Erreur : {str(e)}"

# ==========================================
# INITIALISATION SESSION STATE
# ==========================================

if 'selected_week_date' not in st.session_state:
    st.session_state.selected_week_date = datetime.now().date()

if 'horaires_semaine' not in st.session_state:
    st.session_state.horaires_semaine = {
        'lundi': {'debut': '05:00', 'fin': '22:00'},
        'mardi': {'debut': '05:00', 'fin': '22:00'},
        'mercredi': {'debut': '05:00', 'fin': '22:00'},
        'jeudi': {'debut': '05:00', 'fin': '22:00'},
        'vendredi': {'debut': '05:00', 'fin': '22:00'},
        'samedi': {'debut': '05:00', 'fin': '20:00'}
    }

if 'planning_semaine' not in st.session_state:
    st.session_state.planning_semaine = {}

# ==========================================
# NAVIGATION SEMAINE
# ==========================================

col1, col2, col3 = st.columns([1, 3, 1])

with col1:
    if st.button("◀ Semaine précédente", use_container_width=True):
        st.session_state.selected_week_date -= timedelta(days=7)
        st.rerun()

with col2:
    week_dates = get_week_dates(st.session_state.selected_week_date)
    annee, semaine = get_week_number(week_dates[0])
    
    st.markdown(f"### 📅 Semaine {semaine} - {week_dates[0].strftime('%d/%m')} au {week_dates[-1].strftime('%d/%m/%Y')}")

with col3:
    if st.button("Semaine suivante ▶", use_container_width=True):
        st.session_state.selected_week_date += timedelta(days=7)
        st.rerun()

st.markdown("---")

# ==========================================
# CONFIGURATION HORAIRES
# ==========================================

with st.expander("⚙️ Configuration horaires de travail", expanded=False):
    st.markdown("*Définissez les horaires de travail pour chaque jour (calcul automatique des capacités)*")
    
    jours = ['lundi', 'mardi', 'mercredi', 'jeudi', 'vendredi', 'samedi']
    jours_fr = ['Lundi', 'Mardi', 'Mercredi', 'Jeudi', 'Vendredi', 'Samedi']
    
    for jour, jour_fr in zip(jours, jours_fr):
        col1, col2, col3, col4 = st.columns([2, 2, 2, 1])
        
        with col1:
            st.write(f"**{jour_fr}**")
        
        with col2:
            debut = st.text_input(
                "Début",
                value=st.session_state.horaires_semaine[jour]['debut'],
                key=f"debut_{jour}",
                label_visibility="collapsed"
            )
            st.session_state.horaires_semaine[jour]['debut'] = debut
        
        with col3:
            fin = st.text_input(
                "Fin",
                value=st.session_state.horaires_semaine[jour]['fin'],
                key=f"fin_{jour}",
                label_visibility="collapsed"
            )
            st.session_state.horaires_semaine[jour]['fin'] = fin
        
        with col4:
            capacite = calculate_capacity_hours(debut, fin)
            st.metric("", f"{capacite:.1f}h")

st.markdown("---")

# ==========================================
# CHARGER JOBS DE LA SEMAINE
# ==========================================

jobs_semaine = get_jobs_prevus_semaine(week_dates)

# Charger planning sauvegardé si existe
planning_sauvegarde = get_planning_semaine(annee, semaine)

# Initialiser planning de la semaine si vide
if not st.session_state.planning_semaine:
    st.session_state.planning_semaine = {
        date.strftime('%Y-%m-%d'): {
            'LIGNE_1': [],
            'LIGNE_2': []
        } for date in week_dates
    }
    
    # Charger depuis BDD si existe
    if not planning_sauvegarde.empty:
        for _, row in planning_sauvegarde.iterrows():
            date_str = row['date_prevue'].strftime('%Y-%m-%d')
            ligne = row['ligne_lavage']
            job_id = int(row['job_id'])
            
            if date_str in st.session_state.planning_semaine:
                if job_id not in st.session_state.planning_semaine[date_str][ligne]:
                    st.session_state.planning_semaine[date_str][ligne].append(job_id)

# ==========================================
# JOBS NON PLANIFIÉS
# ==========================================

st.subheader("📦 Jobs Non Planifiés")

if not jobs_semaine.empty:
    # Filtrer jobs déjà planifiés
    jobs_planifies_ids = []
    for date_jobs in st.session_state.planning_semaine.values():
        for ligne_jobs in date_jobs.values():
            jobs_planifies_ids.extend(ligne_jobs)
    
    jobs_non_planifies = jobs_semaine[~jobs_semaine['id'].isin(jobs_planifies_ids)]
    
    if not jobs_non_planifies.empty:
        st.info(f"🎯 {len(jobs_non_planifies)} job(s) à planifier - Sélectionnez un ou plusieurs jobs puis assignez-les à un jour/ligne")
        
        # Préparer DataFrame pour AgGrid
        df_display = jobs_non_planifies[[
            'id', 'code_lot_interne', 'nom_usage', 'variete',
            'quantite_pallox', 'poids_brut_kg', 'temps_estime_heures', 'ligne_lavage'
        ]].copy()
        
        df_display['poids_t'] = (df_display['poids_brut_kg'] / 1000).round(1)
        df_display['temps_h'] = df_display['temps_estime_heures'].round(1)
        
        df_display = df_display.rename(columns={
            'code_lot_interne': 'Code Lot',
            'nom_usage': 'Nom',
            'variete': 'Variété',
            'quantite_pallox': 'Pallox',
            'poids_t': 'Poids (T)',
            'temps_h': 'Temps (h)',
            'ligne_lavage': 'Ligne'
        })
        
        df_display = df_display[['id', 'Code Lot', 'Nom', 'Variété', 'Pallox', 'Poids (T)', 'Temps (h)', 'Ligne']]
        
        # Configuration AgGrid
        gb = GridOptionsBuilder.from_dataframe(df_display)
        gb.configure_selection(selection_mode='multiple', use_checkbox=True)
        gb.configure_column("id", hide=True)
        gb.configure_column("Code Lot", width=150)
        gb.configure_column("Nom", width=200)
        gb.configure_column("Variété", width=120)
        gb.configure_column("Pallox", width=80)
        gb.configure_column("Poids (T)", width=100)
        gb.configure_column("Temps (h)", width=100)
        gb.configure_column("Ligne", width=100)
        
        grid_options = gb.build()
        
        # Afficher grille
        grid_response = AgGrid(
            df_display,
            gridOptions=grid_options,
            update_mode=GridUpdateMode.SELECTION_CHANGED,
            height=300,
            theme='streamlit',
            enable_enterprise_modules=False
        )
        
        selected_rows = grid_response['selected_rows']
        
        if selected_rows is not None and len(selected_rows) > 0:
            st.success(f"✅ {len(selected_rows)} job(s) sélectionné(s)")
            
            # Formulaire d'assignation
            col1, col2, col3 = st.columns([2, 2, 1])
            
            with col1:
                jour_options = [f"{d.strftime('%A %d/%m')}" for d in week_dates]
                jour_options_fr = ['Lundi', 'Mardi', 'Mercredi', 'Jeudi', 'Vendredi', 'Samedi']
                jour_options_display = [f"{fr} {d.strftime('%d/%m')}" for fr, d in zip(jour_options_fr, week_dates)]
                
                selected_jour = st.selectbox("Assigner à quel jour ?", jour_options_display, key="assign_jour")
            
            with col2:
                selected_ligne = st.selectbox("Quelle ligne ?", ["LIGNE_1", "LIGNE_2"], key="assign_ligne")
            
            with col3:
                st.write("")
                st.write("")
                if st.button("✅ Assigner", type="primary", use_container_width=True):
                    # Récupérer l'index du jour
                    jour_idx = jour_options_display.index(selected_jour)
                    date_str = week_dates[jour_idx].strftime('%Y-%m-%d')
                    
                    # Ajouter les jobs au planning
                    for row in selected_rows:
                        job_id = int(row['id'])
                        if job_id not in st.session_state.planning_semaine[date_str][selected_ligne]:
                            st.session_state.planning_semaine[date_str][selected_ligne].append(job_id)
                    
                    st.success(f"✅ {len(selected_rows)} job(s) assigné(s) à {selected_jour} - {selected_ligne}")
                    st.rerun()
        else:
            st.info("👆 Cochez un ou plusieurs jobs dans le tableau ci-dessus")
    else:
        st.success("✅ Tous les jobs de la semaine sont planifiés !")
else:
    st.info("ℹ️ Aucun job PRÉVU pour cette semaine")

st.markdown("---")

# ==========================================
# PLANNING JOURNALIER
# ==========================================

st.subheader("📅 Planning de la Semaine")

jours_fr = ['Lundi', 'Mardi', 'Mercredi', 'Jeudi', 'Vendredi', 'Samedi']
jours_keys = ['lundi', 'mardi', 'mercredi', 'jeudi', 'vendredi', 'samedi']

# Calculs récap semaine
recap_semaine = {
    'LIGNE_1': {'temps': 0, 'capacite': 0, 'nb_jobs': 0},
    'LIGNE_2': {'temps': 0, 'capacite': 0, 'nb_jobs': 0}
}

for date, jour_fr, jour_key in zip(week_dates, jours_fr, jours_keys):
    date_str = date.strftime('%Y-%m-%d')
    
    st.markdown(f"### {jour_fr} {date.strftime('%d/%m/%Y')}")
    
    # Capacité du jour
    horaire = st.session_state.horaires_semaine[jour_key]
    capacite_jour = calculate_capacity_hours(horaire['debut'], horaire['fin'])
    
    st.caption(f"⏰ Horaires : {horaire['debut']} - {horaire['fin']} ({capacite_jour:.1f}h disponibles)")
    
    # Afficher par ligne
    for ligne in ['LIGNE_1', 'LIGNE_2']:
        ligne_label = "🔵 LIGNE_1 (13 T/h)" if ligne == 'LIGNE_1' else "🟢 LIGNE_2 (6 T/h)"
        
        st.markdown(f"**{ligne_label}**")
        
        jobs_jour_ligne = st.session_state.planning_semaine[date_str][ligne]
        
        if jobs_jour_ligne:
            # Récupérer infos jobs
            jobs_info = jobs_semaine[jobs_semaine['id'].isin(jobs_jour_ligne)]
            
            # Trier selon ordre dans la liste
            jobs_info['ordre'] = jobs_info['id'].apply(lambda x: jobs_jour_ligne.index(x))
            jobs_info = jobs_info.sort_values('ordre')
            
            # Calculer temps cumulé
            temps_cumule = 0
            heure_debut_str = horaire['debut']
            
            for idx, (_, job) in enumerate(jobs_info.iterrows()):
                job_id = int(job['id'])
                temps_job = float(job['temps_estime_heures'])
                poids = float(job['poids_brut_kg']) / 1000
                
                # Calculer heure fin
                h_debut = datetime.strptime(heure_debut_str, "%H:%M")
                h_fin = h_debut + timedelta(hours=temps_job)
                heure_fin_str = h_fin.strftime("%H:%M")
                
                # Afficher job
                col1, col2, col3, col4 = st.columns([3, 1, 1, 1])
                
                with col1:
                    st.markdown(f"**Job #{job_id}** - {job['code_lot_interne']} - {job['variete']}")
                    st.caption(f"{int(job['quantite_pallox'])} pallox • {poids:.1f} T • {temps_job:.1f}h • {heure_debut_str}-{heure_fin_str}")
                
                with col2:
                    if idx > 0:
                        if st.button("⬆️", key=f"up_{date_str}_{ligne}_{job_id}"):
                            # Échanger avec le job précédent
                            jobs_jour_ligne[idx], jobs_jour_ligne[idx-1] = jobs_jour_ligne[idx-1], jobs_jour_ligne[idx]
                            st.rerun()
                
                with col3:
                    if idx < len(jobs_jour_ligne) - 1:
                        if st.button("⬇️", key=f"down_{date_str}_{ligne}_{job_id}"):
                            # Échanger avec le job suivant
                            jobs_jour_ligne[idx], jobs_jour_ligne[idx+1] = jobs_jour_ligne[idx+1], jobs_jour_ligne[idx]
                            st.rerun()
                
                with col4:
                    if st.button("❌", key=f"remove_{date_str}_{ligne}_{job_id}"):
                        jobs_jour_ligne.remove(job_id)
                        st.rerun()
                
                # Préparer pour le prochain job (+ 20 min transition)
                temps_cumule += temps_job + 0.33  # 20 min = 0.33h
                h_prochain = h_fin + timedelta(minutes=20)
                heure_debut_str = h_prochain.strftime("%H:%M")
            
            # Indicateurs ligne
            temps_total = temps_cumule - 0.33 if temps_cumule > 0 else 0  # Retirer dernière transition
            temps_dispo = capacite_jour - temps_total
            charge_pct = (temps_total / capacite_jour * 100) if capacite_jour > 0 else 0
            
            emoji, css_class = get_charge_color(charge_pct)
            
            st.markdown(f"<div class='metric-card'>⏱️ Utilisé: <strong>{temps_total:.1f}h</strong> | 💚 Dispo: <strong>{temps_dispo:.1f}h</strong> | {emoji} Charge: <span class='{css_class}'>{charge_pct:.0f}%</span></div>", unsafe_allow_html=True)
            
            # Ajouter au récap
            recap_semaine[ligne]['temps'] += temps_total
            recap_semaine[ligne]['capacite'] += capacite_jour
            recap_semaine[ligne]['nb_jobs'] += len(jobs_jour_ligne)
            
        else:
            st.info(f"Aucun job planifié sur {ligne_label}")
            
            # Ajouter capacité même si vide
            recap_semaine[ligne]['capacite'] += capacite_jour
    
    st.markdown("---")

# ==========================================
# RÉCAPITULATIF SEMAINE
# ==========================================

st.subheader("📊 Récapitulatif Semaine")

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric("🔵 LIGNE_1 Planifié", f"{recap_semaine['LIGNE_1']['temps']:.1f}h")
    st.caption(f"Capacité: {recap_semaine['LIGNE_1']['capacite']:.1f}h")

with col2:
    charge_l1 = (recap_semaine['LIGNE_1']['temps'] / recap_semaine['LIGNE_1']['capacite'] * 100) if recap_semaine['LIGNE_1']['capacite'] > 0 else 0
    emoji_l1, _ = get_charge_color(charge_l1)
    st.metric(f"{emoji_l1} Charge LIGNE_1", f"{charge_l1:.0f}%")
    st.caption(f"{recap_semaine['LIGNE_1']['nb_jobs']} jobs")

with col3:
    st.metric("🟢 LIGNE_2 Planifié", f"{recap_semaine['LIGNE_2']['temps']:.1f}h")
    st.caption(f"Capacité: {recap_semaine['LIGNE_2']['capacite']:.1f}h")

with col4:
    charge_l2 = (recap_semaine['LIGNE_2']['temps'] / recap_semaine['LIGNE_2']['capacite'] * 100) if recap_semaine['LIGNE_2']['capacite'] > 0 else 0
    emoji_l2, _ = get_charge_color(charge_l2)
    st.metric(f"{emoji_l2} Charge LIGNE_2", f"{charge_l2:.0f}%")
    st.caption(f"{recap_semaine['LIGNE_2']['nb_jobs']} jobs")

st.markdown("---")

# ==========================================
# ACTIONS
# ==========================================

col1, col2, col3 = st.columns(3)

with col1:
    if st.button("💾 Sauvegarder Planning", type="primary", use_container_width=True):
        # Préparer données pour sauvegarde
        planning_data = []
        
        for date, jour_fr in zip(week_dates, jours_fr):
            date_str = date.strftime('%Y-%m-%d')
            
            for ligne in ['LIGNE_1', 'LIGNE_2']:
                jobs = st.session_state.planning_semaine[date_str][ligne]
                
                for ordre, job_id in enumerate(jobs, start=1):
                    planning_data.append({
                        'job_id': job_id,
                        'date': date,
                        'ligne': ligne,
                        'ordre': ordre
                    })
        
        if planning_data:
            success, message = save_planning_semaine(annee, semaine, planning_data)
            if success:
                st.success(message)
            else:
                st.error(message)
        else:
            st.warning("⚠️ Aucun job à sauvegarder")

with col2:
    if st.button("🔄 Réinitialiser Planning", use_container_width=True):
        st.session_state.planning_semaine = {
            date.strftime('%Y-%m-%d'): {
                'LIGNE_1': [],
                'LIGNE_2': []
            } for date in week_dates
        }
        st.success("✅ Planning réinitialisé")
        st.rerun()

with col3:
    if st.button("📄 Exporter (à venir)", disabled=True, use_container_width=True):
        st.info("Fonctionnalité d'export PDF à venir dans Phase 2")

show_footer()
