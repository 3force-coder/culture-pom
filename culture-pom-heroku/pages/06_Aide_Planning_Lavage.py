import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, time
from database import get_connection
from components import show_footer
from auth import is_authenticated
from auth.roles import is_admin
import io
import math

st.set_page_config(page_title="Aide Planning Lavage - Culture Pom", page_icon="🗓️", layout="wide")

# ============================================================
# CSS CUSTOM
# ============================================================
st.markdown("""
<style>
    .block-container {
        padding-top: 1rem !important;
        padding-bottom: 0.5rem !important;
    }
    h1, h2, h3, h4 {
        margin-top: 0.3rem !important;
        margin-bottom: 0.3rem !important;
    }
    
    /* Centrage semaine */
    .semaine-center {
        text-align: center;
    }
    .semaine-center h2 {
        margin: 0 !important;
    }
    
    /* Cartes jobs/temps */
    .job-card {
        background: linear-gradient(135deg, #e3f2fd 0%, #bbdefb 100%);
        border-left: 4px solid #1976d2;
        padding: 0.6rem;
        border-radius: 8px;
        margin: 0.4rem 0;
        font-size: 0.85rem;
    }
    .custom-card {
        background: linear-gradient(135deg, #f3e5f5 0%, #e1bee7 100%);
        border-left: 4px solid #7b1fa2;
        padding: 0.6rem;
        border-radius: 8px;
        margin: 0.4rem 0;
        font-size: 0.85rem;
    }
    
    /* En-tête jour avec capacités */
    .day-header {
        background: #f5f5f5;
        padding: 0.5rem;
        border-radius: 8px 8px 0 0;
        text-align: center;
        font-weight: bold;
        border-bottom: 2px solid #1976d2;
    }
    .capacity-box {
        background: #fafafa;
        padding: 0.4rem;
        font-size: 0.75rem;
        border: 1px solid #e0e0e0;
        border-radius: 0 0 8px 8px;
        margin-bottom: 0.5rem;
    }
    
    /* Éléments planifiés */
    .planned-job {
        background: linear-gradient(135deg, #c8e6c9 0%, #a5d6a7 100%);
        border-left: 4px solid #388e3c;
        padding: 0.5rem;
        border-radius: 6px;
        margin: 0.3rem 0;
        font-size: 0.8rem;
    }
    .planned-custom {
        background: linear-gradient(135deg, #fff3e0 0%, #ffe0b2 100%);
        border-left: 4px solid #f57c00;
        padding: 0.5rem;
        border-radius: 6px;
        margin: 0.3rem 0;
        font-size: 0.8rem;
    }
    
    /* Indicateurs charge */
    .charge-low { color: #2e7d32; font-weight: bold; }
    .charge-medium { color: #f9a825; font-weight: bold; }
    .charge-high { color: #c62828; font-weight: bold; }
</style>
""", unsafe_allow_html=True)

if not is_authenticated():
    st.warning("⚠️ Veuillez vous connecter pour accéder à cette page")
    st.stop()

# ============================================================
# FONCTIONS UTILITAIRES
# ============================================================

def arrondir_quart_heure_sup(heure_obj):
    """
    Arrondit une heure au quart d'heure supérieur
    5h43 → 5h45, 6h10 → 6h15, 7h00 → 7h00
    """
    minutes = heure_obj.minute
    if minutes % 15 == 0:
        return heure_obj
    
    # Arrondir au quart d'heure supérieur
    nouveau_minutes = ((minutes // 15) + 1) * 15
    
    if nouveau_minutes >= 60:
        # Passer à l'heure suivante
        nouvelle_heure = heure_obj.hour + 1
        nouveau_minutes = 0
        if nouvelle_heure >= 24:
            nouvelle_heure = 23
            nouveau_minutes = 45
        return time(nouvelle_heure, nouveau_minutes)
    else:
        return time(heure_obj.hour, nouveau_minutes)

def get_lignes_lavage():
    """Récupère les lignes de lavage actives"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT code, libelle, capacite_th 
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

def get_temps_customs():
    """Récupère les temps customs actifs"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, code, libelle, emoji, duree_minutes 
            FROM lavages_temps_customs 
            WHERE is_active = TRUE 
            ORDER BY id
        """)
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        return rows if rows else []
    except Exception as e:
        st.error(f"❌ Erreur : {str(e)}")
        return []

def supprimer_temps_custom(temps_id):
    """Supprime (désactive) un temps custom"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE lavages_temps_customs 
            SET is_active = FALSE 
            WHERE id = %s
        """, (temps_id,))
        conn.commit()
        cursor.close()
        conn.close()
        return True, "✅ Temps custom supprimé"
    except Exception as e:
        if 'conn' in locals():
            conn.rollback()
        return False, f"❌ Erreur : {str(e)}"

def get_config_horaires():
    """Récupère la configuration des horaires par jour"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT jour_semaine, heure_debut, heure_fin 
            FROM lavages_config_horaires 
            WHERE is_active = TRUE 
            ORDER BY jour_semaine
        """)
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        
        config = {}
        for row in rows:
            config[row['jour_semaine']] = {
                'debut': row['heure_debut'],
                'fin': row['heure_fin']
            }
        return config
    except Exception as e:
        return {i: {'debut': time(5, 0), 'fin': time(22, 0) if i < 5 else time(20, 0)} for i in range(6)}

def get_jobs_a_placer():
    """Récupère les jobs PRÉVU non encore planifiés cette semaine"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                lj.id,
                lj.lot_id,
                lj.code_lot_interne,
                lj.variete,
                lj.quantite_pallox,
                lj.poids_brut_kg,
                lj.temps_estime_heures,
                lj.date_prevue,
                lj.ligne_lavage as ligne_origine
            FROM lavages_jobs lj
            WHERE lj.statut = 'PRÉVU'
            ORDER BY lj.date_prevue, lj.id
        """)
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        
        if rows:
            df = pd.DataFrame(rows)
            numeric_cols = ['quantite_pallox', 'poids_brut_kg', 'temps_estime_heures']
            for col in numeric_cols:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
            return df
        return pd.DataFrame()
    except Exception as e:
        st.error(f"❌ Erreur : {str(e)}")
        return pd.DataFrame()

def get_planning_semaine(annee, semaine):
    """Récupère le planning d'une semaine donnée"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                pe.id,
                pe.type_element,
                pe.job_id,
                pe.temps_custom_id,
                pe.date_prevue,
                pe.ligne_lavage,
                pe.ordre_jour,
                pe.heure_debut,
                pe.heure_fin,
                pe.duree_minutes,
                lj.code_lot_interne,
                lj.variete,
                lj.quantite_pallox,
                lj.poids_brut_kg,
                tc.libelle as custom_libelle,
                tc.emoji as custom_emoji
            FROM lavages_planning_elements pe
            LEFT JOIN lavages_jobs lj ON pe.job_id = lj.id
            LEFT JOIN lavages_temps_customs tc ON pe.temps_custom_id = tc.id
            WHERE pe.annee = %s AND pe.semaine = %s
            ORDER BY pe.date_prevue, pe.ligne_lavage, pe.ordre_jour
        """, (annee, semaine))
        
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        
        if rows:
            df = pd.DataFrame(rows)
            return df
        return pd.DataFrame()
    except Exception as e:
        return pd.DataFrame()

def verifier_chevauchement(planning_df, date_prevue, ligne_lavage, heure_debut, duree_minutes):
    """
    Vérifie si le créneau demandé chevauche un élément existant.
    Retourne (ok, message, prochaine_heure_dispo)
    """
    jour_str = str(date_prevue)
    
    if planning_df.empty:
        return True, None, None
    
    mask = (planning_df['date_prevue'].astype(str) == jour_str) & (planning_df['ligne_lavage'] == ligne_lavage)
    elements = planning_df[mask]
    
    if elements.empty:
        return True, None, None
    
    # Calculer l'heure de fin demandée
    debut_minutes = heure_debut.hour * 60 + heure_debut.minute
    fin_minutes = debut_minutes + duree_minutes
    
    # Vérifier chevauchement avec chaque élément
    for _, elem in elements.iterrows():
        if pd.isna(elem['heure_debut']) or pd.isna(elem['heure_fin']):
            continue
        
        elem_debut = elem['heure_debut'].hour * 60 + elem['heure_debut'].minute
        elem_fin = elem['heure_fin'].hour * 60 + elem['heure_fin'].minute
        
        # Chevauchement si : début demandé < fin existant ET fin demandée > début existant
        if debut_minutes < elem_fin and fin_minutes > elem_debut:
            # Trouver la prochaine heure disponible (fin de cet élément arrondie au quart d'heure)
            prochaine_heure = arrondir_quart_heure_sup(elem['heure_fin'])
            return False, f"⚠️ Créneau occupé ! Prochaine heure disponible : **{prochaine_heure.strftime('%H:%M')}**", prochaine_heure
    
    return True, None, None

def get_horaire_fin_jour(jour_semaine, horaires_config):
    """Retourne l'heure de fin pour un jour donné"""
    if jour_semaine in horaires_config:
        h_fin = horaires_config[jour_semaine]['fin']
        if isinstance(h_fin, time):
            return h_fin
    return time(22, 0) if jour_semaine < 5 else time(20, 0)

def get_capacite_jour(ligne_code, capacite_th, jour_semaine, horaires_config):
    """Calcule la capacité totale en heures pour un jour donné"""
    if jour_semaine not in horaires_config:
        return 17.0
    
    h_debut = horaires_config[jour_semaine]['debut']
    h_fin = horaires_config[jour_semaine]['fin']
    
    if isinstance(h_debut, time):
        debut_h = h_debut.hour + h_debut.minute / 60
    else:
        debut_h = 5.0
    
    if isinstance(h_fin, time):
        fin_h = h_fin.hour + h_fin.minute / 60
    else:
        fin_h = 22.0
    
    return fin_h - debut_h

def calculer_temps_utilise(planning_df, date_str, ligne):
    """Calcule le temps utilisé pour un jour/ligne"""
    if planning_df.empty:
        return 0.0
    
    mask = (planning_df['date_prevue'].astype(str) == date_str) & (planning_df['ligne_lavage'] == ligne)
    filtered = planning_df[mask]
    
    if filtered.empty:
        return 0.0
    
    return filtered['duree_minutes'].sum() / 60

def get_creneaux_disponibles(planning_df, date_prevue, ligne_lavage, jour_semaine, horaires_config):
    """
    Retourne la liste des créneaux horaires disponibles pour un jour/ligne
    Format: [(heure_debut, label), ...]
    """
    jour_str = str(date_prevue)
    
    # Heure de début et fin de journée
    if jour_semaine in horaires_config:
        h_debut_jour = horaires_config[jour_semaine]['debut']
        h_fin_jour = horaires_config[jour_semaine]['fin']
    else:
        h_debut_jour = time(5, 0)
        h_fin_jour = time(22, 0) if jour_semaine < 5 else time(20, 0)
    
    creneaux = []
    
    # Premier créneau = début de journée
    creneaux.append((h_debut_jour, f"{h_debut_jour.strftime('%H:%M')} (début journée)"))
    
    # Créneaux après chaque élément existant (arrondi au quart d'heure)
    if not planning_df.empty:
        mask = (planning_df['date_prevue'].astype(str) == jour_str) & (planning_df['ligne_lavage'] == ligne_lavage)
        elements = planning_df[mask].sort_values('ordre_jour')
        
        for _, elem in elements.iterrows():
            if pd.notna(elem['heure_fin']):
                h_fin_arrondi = arrondir_quart_heure_sup(elem['heure_fin'])
                
                # Générer le label
                if elem['type_element'] == 'JOB':
                    label = f"{h_fin_arrondi.strftime('%H:%M')} (après Job #{int(elem['job_id'])})"
                else:
                    label = f"{h_fin_arrondi.strftime('%H:%M')} (après {elem['custom_emoji']} {elem['custom_libelle']})"
                
                creneaux.append((h_fin_arrondi, label))
    
    return creneaux

def ajouter_element_planning(type_element, job_id, temps_custom_id, date_prevue, ligne_lavage, 
                             duree_minutes, annee, semaine, heure_debut_choisie):
    """Ajoute un élément au planning avec heure de début choisie"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Déterminer l'ordre (basé sur heure_debut)
        cursor.execute("""
            SELECT COALESCE(MAX(ordre_jour), 0) as max_ordre
            FROM lavages_planning_elements
            WHERE date_prevue = %s AND ligne_lavage = %s
        """, (date_prevue, ligne_lavage))
        result = cursor.fetchone()
        next_ordre = (result['max_ordre'] or 0) + 1
        
        # Utiliser l'heure choisie
        heure_debut = heure_debut_choisie
        
        # Calculer heure fin et arrondir au quart d'heure
        debut_minutes = heure_debut.hour * 60 + heure_debut.minute
        fin_minutes = debut_minutes + duree_minutes
        heure_fin_brute = time(min(23, fin_minutes // 60), fin_minutes % 60)
        heure_fin = arrondir_quart_heure_sup(heure_fin_brute)
        
        # Insérer
        created_by = st.session_state.get('username', 'system')
        
        cursor.execute("""
            INSERT INTO lavages_planning_elements 
            (type_element, job_id, temps_custom_id, annee, semaine, date_prevue, 
             ligne_lavage, ordre_jour, heure_debut, heure_fin, duree_minutes, created_by)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (type_element, job_id, temps_custom_id, annee, semaine, date_prevue,
              ligne_lavage, next_ordre, heure_debut, heure_fin, duree_minutes, created_by))
        
        new_id = cursor.fetchone()['id']
        conn.commit()
        cursor.close()
        conn.close()
        
        return True, f"✅ Élément ajouté ({heure_debut.strftime('%H:%M')} → {heure_fin.strftime('%H:%M')})"
    except Exception as e:
        if 'conn' in locals():
            conn.rollback()
        return False, f"❌ Erreur : {str(e)}"

def retirer_element_planning(element_id):
    """Retire un élément du planning"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM lavages_planning_elements WHERE id = %s", (element_id,))
        conn.commit()
        cursor.close()
        conn.close()
        return True, "✅ Élément retiré"
    except Exception as e:
        if 'conn' in locals():
            conn.rollback()
        return False, f"❌ Erreur : {str(e)}"

def creer_temps_custom(code, libelle, emoji, duree_minutes):
    """Crée un nouveau temps custom"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        created_by = st.session_state.get('username', 'system')
        cursor.execute("""
            INSERT INTO lavages_temps_customs (code, libelle, emoji, duree_minutes, created_by)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id
        """, (code, libelle, emoji, duree_minutes, created_by))
        new_id = cursor.fetchone()['id']
        conn.commit()
        cursor.close()
        conn.close()
        return True, f"✅ Temps custom créé"
    except Exception as e:
        if 'conn' in locals():
            conn.rollback()
        return False, f"❌ Erreur : {str(e)}"

def generer_html_jour(planning_df, date_obj, ligne, lignes_info):
    """Génère le contenu HTML pour impression d'un jour"""
    jours_fr = ['Lundi', 'Mardi', 'Mercredi', 'Jeudi', 'Vendredi', 'Samedi', 'Dimanche']
    jour_nom = jours_fr[date_obj.weekday()]
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>Planning {ligne} - {date_obj.strftime('%d/%m/%Y')}</title>
        <style>
            @page {{ size: A4 portrait; margin: 15mm; }}
            body {{ font-family: Arial, sans-serif; margin: 0; padding: 20px; }}
            h1 {{ color: #1976d2; border-bottom: 3px solid #1976d2; padding-bottom: 10px; margin-bottom: 20px; }}
            .info {{ background: #f5f5f5; padding: 15px; border-radius: 8px; margin-bottom: 20px; }}
            .element {{ border-left: 5px solid #388e3c; padding: 12px 15px; margin: 10px 0; background: #f9f9f9; border-radius: 0 8px 8px 0; }}
            .element-custom {{ border-left-color: #f57c00; background: #fff8e1; }}
            .horaire {{ font-weight: bold; color: #1976d2; font-size: 1.1em; display: inline-block; min-width: 120px; }}
            .duree {{ color: #666; font-size: 0.9em; }}
            .details {{ margin-top: 5px; color: #333; }}
            .footer {{ margin-top: 40px; padding-top: 15px; border-top: 1px solid #ddd; font-size: 0.85em; color: #666; }}
            .recap {{ background: #e3f2fd; padding: 15px; border-radius: 8px; margin-top: 30px; font-weight: bold; }}
        </style>
    </head>
    <body>
        <h1>🗓️ PLANNING LAVAGE - {ligne}</h1>
        <div class="info">
            <strong>📅 Date :</strong> {jour_nom} {date_obj.strftime('%d/%m/%Y')}<br>
            <strong>⏰ Horaires :</strong> 05:00 - 22:00
        </div>
    """
    
    jour_str = str(date_obj)
    
    if not planning_df.empty:
        mask = (planning_df['date_prevue'].astype(str) == jour_str) & (planning_df['ligne_lavage'] == ligne)
        elements = planning_df[mask].sort_values('heure_debut')
    else:
        elements = pd.DataFrame()
    
    if elements.empty:
        html += "<p style='color: #666; font-style: italic; text-align: center; padding: 40px;'>Aucun élément planifié pour ce jour</p>"
        temps_total = 0
    else:
        for _, elem in elements.iterrows():
            css_class = "element" if elem['type_element'] == 'JOB' else "element element-custom"
            
            if elem['type_element'] == 'JOB':
                contenu = f"""
                    <div class="details">
                        <strong>Job #{int(elem['job_id'])} - {elem['variete']}</strong><br>
                        📦 {int(elem['quantite_pallox'])} pallox - ⚖️ {float(elem['poids_brut_kg'])/1000:.1f} T<br>
                        🏷️ Code lot : {elem['code_lot_interne']}
                    </div>
                """
            else:
                contenu = f"""
                    <div class="details">
                        <strong>{elem['custom_emoji']} {elem['custom_libelle']}</strong>
                    </div>
                """
            
            h_debut = elem['heure_debut'].strftime('%H:%M') if pd.notna(elem['heure_debut']) else '--:--'
            h_fin = elem['heure_fin'].strftime('%H:%M') if pd.notna(elem['heure_fin']) else '--:--'
            
            html += f"""
            <div class="{css_class}">
                <span class="horaire">{h_debut} → {h_fin}</span>
                <span class="duree">({int(elem['duree_minutes'])} min)</span>
                {contenu}
            </div>
            """
        
        temps_total = elements['duree_minutes'].sum() / 60
    
    html += f"""
        <div class="recap">📊 RÉCAPITULATIF : {temps_total:.1f}h planifié</div>
        <div class="footer">Imprimé le {datetime.now().strftime('%d/%m/%Y à %H:%M')} | Culture Pom - Planning Lavage</div>
    </body>
    </html>
    """
    
    return html

# ============================================================
# INITIALISATION SESSION STATE
# ============================================================

def get_monday_of_week(date_obj):
    return date_obj - timedelta(days=date_obj.weekday())

if 'current_week_start' not in st.session_state:
    st.session_state.current_week_start = get_monday_of_week(datetime.now().date())

if 'selected_ligne' not in st.session_state:
    st.session_state.selected_ligne = 'LIGNE_1'

# ============================================================
# HEADER
# ============================================================

st.title("🗓️ Aide Planning Lavage")

# ============================================================
# CONTRÔLES PRINCIPAUX
# ============================================================

col_ligne, col_nav_prev, col_semaine, col_nav_next, col_refresh = st.columns([2, 0.5, 2, 0.5, 1])

lignes = get_lignes_lavage()
with col_ligne:
    if lignes:
        ligne_options = [f"{l['code']} ({l['capacite_th']} T/h)" for l in lignes]
        selected_idx = 0
        for i, l in enumerate(lignes):
            if l['code'] == st.session_state.selected_ligne:
                selected_idx = i
                break
        
        selected = st.selectbox("🔵 Ligne affichée", ligne_options, index=selected_idx, key="ligne_select")
        st.session_state.selected_ligne = lignes[ligne_options.index(selected)]['code']

with col_nav_prev:
    st.write("")
    if st.button("◀", key="prev_week", use_container_width=True):
        st.session_state.current_week_start -= timedelta(weeks=1)
        st.rerun()

with col_semaine:
    week_start = st.session_state.current_week_start
    week_end = week_start + timedelta(days=5)
    annee, semaine, _ = week_start.isocalendar()
    # ⭐ CENTRÉ avec HTML
    st.markdown(f"""
    <div class="semaine-center">
        <h2>Semaine {semaine}</h2>
        <small style="color: #666;">{week_start.strftime('%d/%m')} → {week_end.strftime('%d/%m/%Y')}</small>
    </div>
    """, unsafe_allow_html=True)

with col_nav_next:
    st.write("")
    if st.button("▶", key="next_week", use_container_width=True):
        st.session_state.current_week_start += timedelta(weeks=1)
        st.rerun()

with col_refresh:
    st.write("")
    if st.button("🔄", key="refresh", use_container_width=True, help="Actualiser"):
        st.rerun()

st.markdown("---")

# ============================================================
# CHARGEMENT DES DONNÉES
# ============================================================

jobs_a_placer = get_jobs_a_placer()
temps_customs = get_temps_customs()
horaires_config = get_config_horaires()
planning_df = get_planning_semaine(annee, semaine)

lignes_dict = {l['code']: float(l['capacite_th']) for l in lignes} if lignes else {'LIGNE_1': 13.0, 'LIGNE_2': 6.0}

# ============================================================
# LAYOUT PRINCIPAL
# ============================================================

col_left, col_right = st.columns([1, 4])

# ============================================================
# COLONNE GAUCHE
# ============================================================

with col_left:
    # ----------------------------------------
    # SECTION JOBS À PLACER
    # ----------------------------------------
    st.markdown("### 📦 Jobs à placer")
    
    jobs_planifies_ids = []
    if not planning_df.empty:
        jobs_planifies_ids = planning_df[planning_df['type_element'] == 'JOB']['job_id'].dropna().astype(int).tolist()
    
    jobs_non_planifies = jobs_a_placer[~jobs_a_placer['id'].isin(jobs_planifies_ids)] if not jobs_a_placer.empty else pd.DataFrame()
    
    if jobs_non_planifies.empty:
        st.info("✅ Tous les jobs sont planifiés")
    else:
        for _, job in jobs_non_planifies.iterrows():
            with st.container():
                st.markdown(f"""
                <div class="job-card">
                    <strong>Job #{int(job['id'])}</strong><br>
                    🌱 {job['variete']}<br>
                    📦 {int(job['quantite_pallox'])} pallox<br>
                    ⏱️ {job['temps_estime_heures']:.1f}h ({int(job['temps_estime_heures'] * 60)} min)
                </div>
                """, unsafe_allow_html=True)
                
                # Sélection jour
                jours_options = ["Sélectionner jour..."]
                for i in range(6):
                    jour_date = week_start + timedelta(days=i)
                    jour_nom = ['Lun', 'Mar', 'Mer', 'Jeu', 'Ven', 'Sam'][i]
                    jours_options.append(f"{jour_nom} {jour_date.strftime('%d/%m')}")
                
                jour_choisi = st.selectbox(
                    "Jour",
                    jours_options,
                    key=f"jour_job_{job['id']}",
                    label_visibility="collapsed"
                )
                
                if jour_choisi != "Sélectionner jour...":
                    jour_idx = jours_options.index(jour_choisi) - 1
                    date_cible = week_start + timedelta(days=jour_idx)
                    
                    # ⭐ SÉLECTION HEURE DE DÉBUT avec st.time_input natif
                    h_debut_jour = horaires_config.get(jour_idx, {}).get('debut', time(5, 0))
                    heure_debut = st.time_input(
                        "Heure début",
                        value=h_debut_jour,
                        step=900,  # 15 minutes
                        key=f"heure_job_{job['id']}",
                        label_visibility="collapsed"
                    )
                    
                    duree_min = int(job['temps_estime_heures'] * 60)
                    
                    # ⭐ VÉRIFICATION CHEVAUCHEMENT
                    ok, msg_chevauche, _ = verifier_chevauchement(
                        planning_df, date_cible, st.session_state.selected_ligne, heure_debut, duree_min
                    )
                    
                    if not ok:
                        st.error(msg_chevauche)
                    else:
                        # ⭐ VÉRIFICATION DURÉE SUFFISANTE
                        h_fin_jour = get_horaire_fin_jour(jour_idx, horaires_config)
                        debut_minutes = heure_debut.hour * 60 + heure_debut.minute
                        fin_minutes = debut_minutes + duree_min
                        fin_jour_minutes = h_fin_jour.hour * 60 + h_fin_jour.minute
                        
                        if fin_minutes > fin_jour_minutes:
                            st.error(f"⚠️ Fin prévue {fin_minutes//60}h{fin_minutes%60:02d} > fin journée {h_fin_jour.strftime('%H:%M')}")
                        else:
                            if st.button(f"✅ Placer", key=f"confirm_job_{job['id']}", type="primary", use_container_width=True):
                                success, msg = ajouter_element_planning(
                                    'JOB', int(job['id']), None, date_cible, 
                                    st.session_state.selected_ligne, duree_min, annee, semaine, heure_debut
                                )
                                if success:
                                    st.success(msg)
                                    st.rerun()
                                else:
                                    st.error(msg)
                
                st.markdown("<hr style='margin: 0.5rem 0; border: none; border-top: 1px solid #eee;'>", unsafe_allow_html=True)
    
    st.markdown("---")
    
    # ----------------------------------------
    # SECTION TEMPS CUSTOMS
    # ----------------------------------------
    st.markdown("### 🔧 Temps customs")
    
    if not temps_customs:
        st.warning("⚠️ Aucun temps custom")
    else:
        for tc in temps_customs:
            with st.container():
                col_tc, col_del = st.columns([5, 1])
                
                with col_tc:
                    st.markdown(f"""
                    <div class="custom-card">
                        <strong>{tc['emoji']} {tc['libelle']}</strong><br>
                        ⏱️ {tc['duree_minutes']} min
                    </div>
                    """, unsafe_allow_html=True)
                
                # ⭐ BOUTON SUPPRIMER (admins uniquement)
                with col_del:
                    if is_admin():
                        if st.button("🗑️", key=f"del_tc_{tc['id']}", help="Supprimer"):
                            success, msg = supprimer_temps_custom(tc['id'])
                            if success:
                                st.success(msg)
                                st.rerun()
                            else:
                                st.error(msg)
                
                # Sélection jour
                jours_options_tc = ["Sélectionner jour..."]
                for i in range(6):
                    jour_date = week_start + timedelta(days=i)
                    jour_nom = ['Lun', 'Mar', 'Mer', 'Jeu', 'Ven', 'Sam'][i]
                    jours_options_tc.append(f"{jour_nom} {jour_date.strftime('%d/%m')}")
                
                jour_choisi_tc = st.selectbox(
                    "Jour",
                    jours_options_tc,
                    key=f"jour_tc_{tc['id']}",
                    label_visibility="collapsed"
                )
                
                if jour_choisi_tc != "Sélectionner jour...":
                    jour_idx = jours_options_tc.index(jour_choisi_tc) - 1
                    date_cible = week_start + timedelta(days=jour_idx)
                    
                    # ⭐ SÉLECTION HEURE DE DÉBUT avec st.time_input natif
                    h_debut_jour = horaires_config.get(jour_idx, {}).get('debut', time(5, 0))
                    heure_debut = st.time_input(
                        "Heure début",
                        value=h_debut_jour,
                        step=900,  # 15 minutes
                        key=f"heure_tc_{tc['id']}",
                        label_visibility="collapsed"
                    )
                    
                    duree_min = int(tc['duree_minutes'])
                    
                    # ⭐ VÉRIFICATION CHEVAUCHEMENT
                    ok, msg_chevauche, _ = verifier_chevauchement(
                        planning_df, date_cible, st.session_state.selected_ligne, heure_debut, duree_min
                    )
                    
                    if not ok:
                        st.error(msg_chevauche)
                    else:
                        # ⭐ VÉRIFICATION DURÉE SUFFISANTE
                        h_fin_jour = get_horaire_fin_jour(jour_idx, horaires_config)
                        debut_minutes = heure_debut.hour * 60 + heure_debut.minute
                        fin_minutes = debut_minutes + duree_min
                        fin_jour_minutes = h_fin_jour.hour * 60 + h_fin_jour.minute
                        
                        if fin_minutes > fin_jour_minutes:
                            st.error(f"⚠️ Durée insuffisante !")
                        else:
                            if st.button(f"✅ Placer", key=f"confirm_tc_{tc['id']}", type="primary", use_container_width=True):
                                success, msg = ajouter_element_planning(
                                    'CUSTOM', None, int(tc['id']), date_cible,
                                    st.session_state.selected_ligne, duree_min, annee, semaine, heure_debut
                                )
                                if success:
                                    st.success(msg)
                                    st.rerun()
                                else:
                                    st.error(msg)
    
    # Créer temps custom
    st.markdown("---")
    with st.expander("➕ Créer temps custom"):
        new_libelle = st.text_input("Libellé", key="new_tc_libelle")
        new_duree = st.number_input("Durée (min)", min_value=5, max_value=480, value=20, step=5, key="new_tc_duree")
        new_emoji = st.selectbox("Emoji", ["⚙️", "☕", "🔧", "🍽️", "🚿", "📋", "⏸️"], key="new_tc_emoji")
        
        if st.button("Créer", key="btn_create_tc", use_container_width=True):
            if new_libelle:
                code = new_libelle.upper().replace(" ", "_")[:20]
                success, msg = creer_temps_custom(code, new_libelle, new_emoji, new_duree)
                if success:
                    st.success(msg)
                    st.rerun()
                else:
                    st.error(msg)
            else:
                st.warning("⚠️ Libellé requis")

# ============================================================
# COLONNE DROITE : CALENDRIER
# ============================================================

with col_right:
    jour_cols = st.columns(6)
    jours_noms = ['Lundi', 'Mardi', 'Mercredi', 'Jeudi', 'Vendredi', 'Samedi']
    
    for i, col_jour in enumerate(jour_cols):
        jour_date = week_start + timedelta(days=i)
        jour_str = str(jour_date)
        jour_semaine_idx = i
        
        with col_jour:
            st.markdown(f"""
            <div class="day-header">
                {jours_noms[i][:3]} {jour_date.strftime('%d/%m')}
            </div>
            """, unsafe_allow_html=True)
            
            # Capacités des 2 lignes EN HAUT
            capacites_html = ""
            for ligne_code in sorted(lignes_dict.keys()):
                capacite_th = lignes_dict[ligne_code]
                cap_totale = get_capacite_jour(ligne_code, capacite_th, jour_semaine_idx, horaires_config)
                temps_utilise = calculer_temps_utilise(planning_df, jour_str, ligne_code)
                temps_dispo = max(0, cap_totale - temps_utilise)
                charge_pct = (temps_utilise / cap_totale * 100) if cap_totale > 0 else 0
                
                if charge_pct < 50:
                    charge_class = "charge-low"
                    emoji = "🟢"
                elif charge_pct < 80:
                    charge_class = "charge-medium"
                    emoji = "🟡"
                else:
                    charge_class = "charge-high"
                    emoji = "🔴"
                
                ligne_short = ligne_code.replace('LIGNE_', 'L')
                capacites_html += f"<div><strong>{ligne_short}</strong>: {temps_dispo:.1f}h <span class='{charge_class}'>{charge_pct:.0f}%{emoji}</span></div>"
            
            st.markdown(f"""
            <div class="capacity-box">
                {capacites_html}
            </div>
            """, unsafe_allow_html=True)
            
            # Éléments planifiés
            ligne_affichee = st.session_state.selected_ligne
            
            if not planning_df.empty:
                mask = (planning_df['date_prevue'].astype(str) == jour_str) & (planning_df['ligne_lavage'] == ligne_affichee)
                elements_jour = planning_df[mask].sort_values('heure_debut')
                
                if elements_jour.empty:
                    st.caption("_Vide_")
                else:
                    for _, elem in elements_jour.iterrows():
                        h_debut = elem['heure_debut'].strftime('%H:%M') if pd.notna(elem['heure_debut']) else '--:--'
                        h_fin = elem['heure_fin'].strftime('%H:%M') if pd.notna(elem['heure_fin']) else '--:--'
                        
                        if elem['type_element'] == 'JOB':
                            st.markdown(f"""
                            <div class="planned-job">
                                <strong>{h_debut}</strong><br>
                                Job #{int(elem['job_id'])}<br>
                                🌱 {elem['variete']}<br>
                                📦 {int(elem['quantite_pallox']) if pd.notna(elem['quantite_pallox']) else '?'}p<br>
                                <small>→{h_fin}</small>
                            </div>
                            """, unsafe_allow_html=True)
                        else:
                            st.markdown(f"""
                            <div class="planned-custom">
                                <strong>{h_debut}</strong><br>
                                {elem['custom_emoji']} {elem['custom_libelle']}<br>
                                <small>→{h_fin}</small>
                            </div>
                            """, unsafe_allow_html=True)
                        
                        if st.button("❌", key=f"del_{elem['id']}", help="Retirer"):
                            success, msg = retirer_element_planning(int(elem['id']))
                            if success:
                                st.rerun()
                            else:
                                st.error(msg)
            else:
                st.caption("_Vide_")

# ============================================================
# FOOTER
# ============================================================

st.markdown("---")

col_f1, col_f2, col_f3, col_f4 = st.columns([1, 1, 1, 2])

with col_f1:
    if st.button("🗑️ Réinit. semaine", use_container_width=True):
        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute("""
                DELETE FROM lavages_planning_elements 
                WHERE annee = %s AND semaine = %s
            """, (annee, semaine))
            conn.commit()
            cursor.close()
            conn.close()
            st.success("✅ Semaine réinitialisée")
            st.rerun()
        except Exception as e:
            st.error(f"❌ Erreur : {str(e)}")

with col_f2:
    jours_print = [f"{jours_noms[i][:3]} {(week_start + timedelta(days=i)).strftime('%d/%m')}" for i in range(6)]
    jour_print = st.selectbox("Jour", jours_print, key="jour_print", label_visibility="collapsed")

with col_f3:
    jour_idx = jours_print.index(jour_print)
    date_print = week_start + timedelta(days=jour_idx)
    
    html_content = generer_html_jour(planning_df, date_print, st.session_state.selected_ligne, lignes_dict)
    
    st.download_button(
        "🖨️ Imprimer jour",
        html_content,
        file_name=f"planning_{st.session_state.selected_ligne}_{date_print.strftime('%Y%m%d')}.html",
        mime="text/html",
        use_container_width=True
    )

with col_f4:
    if not planning_df.empty:
        total_l1 = planning_df[planning_df['ligne_lavage'] == 'LIGNE_1']['duree_minutes'].sum() / 60
        total_l2 = planning_df[planning_df['ligne_lavage'] == 'LIGNE_2']['duree_minutes'].sum() / 60
        st.markdown(f"**📊 Semaine** : L1={total_l1:.1f}h | L2={total_l2:.1f}h")
    else:
        st.markdown("**📊 Semaine** : Aucun élément")

show_footer()
