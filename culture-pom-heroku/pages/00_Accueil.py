import streamlit as st
import pandas as pd
from datetime import datetime, date
from components import show_footer
from database import get_connection

st.title("🏠 Accueil")
st.markdown("*POMI - Pilotage Opérationnel des Mouvements et Inventaires*")
st.markdown("---")

# Vérifier authentification
if not st.session_state.get('authenticated', False):
    st.warning("⚠️ Veuillez vous connecter")
    st.stop()

# ============================================================
# FONCTIONS TÂCHES
# ============================================================

def get_mes_taches():
    """Récupère les tâches de l'utilisateur connecté"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        username = st.session_state.get('username', '')
        today = date.today()
        
        # Mes tâches urgentes (à faire ou en cours)
        cursor.execute("""
            SELECT COUNT(*) as cnt FROM taches 
            WHERE assigne_a = %s 
            AND statut IN ('À faire', 'En cours') 
            AND priorite = 'Urgente'
            AND is_active = TRUE
        """, (username,))
        mes_urgentes = cursor.fetchone()['cnt']
        
        # Mes tâches en retard
        cursor.execute("""
            SELECT COUNT(*) as cnt FROM taches 
            WHERE assigne_a = %s 
            AND statut IN ('À faire', 'En cours') 
            AND date_echeance < %s
            AND is_active = TRUE
        """, (username, today))
        mes_retard = cursor.fetchone()['cnt']
        
        # Mes tâches du jour (échéance aujourd'hui)
        cursor.execute("""
            SELECT COUNT(*) as cnt FROM taches 
            WHERE assigne_a = %s 
            AND statut IN ('À faire', 'En cours') 
            AND date_echeance = %s
            AND is_active = TRUE
        """, (username, today))
        mes_jour = cursor.fetchone()['cnt']
        
        # Toutes mes tâches ouvertes
        cursor.execute("""
            SELECT COUNT(*) as cnt FROM taches 
            WHERE assigne_a = %s 
            AND statut IN ('À faire', 'En cours') 
            AND is_active = TRUE
        """, (username,))
        mes_ouvertes = cursor.fetchone()['cnt']
        
        # Liste des 5 prochaines tâches
        cursor.execute("""
            SELECT id, titre, priorite, statut, date_echeance, source_label
            FROM taches 
            WHERE assigne_a = %s 
            AND statut IN ('À faire', 'En cours') 
            AND is_active = TRUE
            ORDER BY 
                CASE priorite 
                    WHEN 'Urgente' THEN 1 
                    WHEN 'Haute' THEN 2 
                    WHEN 'Normale' THEN 3 
                    WHEN 'Basse' THEN 4 
                END,
                date_echeance ASC NULLS LAST
            LIMIT 5
        """, (username,))
        rows = cursor.fetchall()
        
        if rows:
            liste_taches = pd.DataFrame(rows)
        else:
            liste_taches = pd.DataFrame()
        
        cursor.close()
        conn.close()
        
        return {
            'urgentes': mes_urgentes,
            'retard': mes_retard,
            'jour': mes_jour,
            'ouvertes': mes_ouvertes,
            'liste': liste_taches
        }
        
    except Exception as e:
        return None

def get_taches_globales():
    """Récupère les stats globales des tâches (pour tous)"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        today = date.today()
        
        # Total ouvertes
        cursor.execute("""
            SELECT COUNT(*) as cnt FROM taches 
            WHERE statut IN ('À faire', 'En cours') 
            AND is_active = TRUE
        """)
        total_ouvertes = cursor.fetchone()['cnt']
        
        # Total urgentes
        cursor.execute("""
            SELECT COUNT(*) as cnt FROM taches 
            WHERE statut IN ('À faire', 'En cours') 
            AND priorite = 'Urgente'
            AND is_active = TRUE
        """)
        total_urgentes = cursor.fetchone()['cnt']
        
        # Total en retard
        cursor.execute("""
            SELECT COUNT(*) as cnt FROM taches 
            WHERE statut IN ('À faire', 'En cours') 
            AND date_echeance < %s
            AND is_active = TRUE
        """, (today,))
        total_retard = cursor.fetchone()['cnt']
        
        # Par utilisateur
        cursor.execute("""
            SELECT assigne_a, COUNT(*) as nb
            FROM taches 
            WHERE statut IN ('À faire', 'En cours') 
            AND is_active = TRUE
            AND assigne_a IS NOT NULL
            GROUP BY assigne_a
            ORDER BY nb DESC
        """)
        rows = cursor.fetchall()
        par_user = {row['assigne_a']: row['nb'] for row in rows} if rows else {}
        
        cursor.close()
        conn.close()
        
        return {
            'total_ouvertes': total_ouvertes,
            'total_urgentes': total_urgentes,
            'total_retard': total_retard,
            'par_user': par_user
        }
        
    except:
        return None

# ============================================================
# SECTION 1 : BIENVENUE
# ============================================================

st.success(f"✅ Bienvenue **{st.session_state.get('name', 'Utilisateur')}** !")

# ============================================================
# SECTION 2 : MES TÂCHES (prioritaire)
# ============================================================

st.markdown("---")
st.markdown("### 📋 Mes tâches")

mes_taches = get_mes_taches()

if mes_taches:
    # KPIs personnels
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        if mes_taches['urgentes'] > 0:
            st.error(f"🔴 **{mes_taches['urgentes']}** urgente(s)")
        else:
            st.success("🔴 **0** urgente")
    
    with col2:
        if mes_taches['retard'] > 0:
            st.error(f"⏰ **{mes_taches['retard']}** en retard")
        else:
            st.success("⏰ **0** en retard")
    
    with col3:
        if mes_taches['jour'] > 0:
            st.warning(f"📅 **{mes_taches['jour']}** aujourd'hui")
        else:
            st.info("📅 **0** aujourd'hui")
    
    with col4:
        st.info(f"📋 **{mes_taches['ouvertes']}** ouverte(s)")
    
    # Liste des prochaines tâches
    if not mes_taches['liste'].empty:
        st.markdown("#### 🎯 Prochaines tâches à traiter")
        
        df = mes_taches['liste'].copy()
        
        # Formater pour affichage
        df['Priorité'] = df['priorite'].apply(lambda x: {
            'Urgente': '🔴 Urgente',
            'Haute': '🟠 Haute',
            'Normale': '🟡 Normale',
            'Basse': '🟢 Basse'
        }.get(x, x))
        
        df['Échéance'] = df['date_echeance'].apply(
            lambda x: x.strftime('%d/%m/%Y') if pd.notna(x) else '-'
        )
        
        df['Source'] = df['source_label'].apply(lambda x: x if pd.notna(x) else '-')
        
        # Afficher tableau simplifié
        st.dataframe(
            df[['titre', 'Priorité', 'statut', 'Échéance', 'Source']].rename(columns={
                'titre': 'Titre',
                'statut': 'Statut'
            }),
            use_container_width=True,
            hide_index=True
        )
        
        # Bouton vers page Tâches
        if st.button("📋 Voir toutes mes tâches", type="primary", use_container_width=True):
            st.switch_page("pages/17_Taches.py")
    else:
        st.success("🎉 Aucune tâche en attente ! Bon travail !")
        
        if st.button("📋 Aller à la page Tâches", use_container_width=True):
            st.switch_page("pages/17_Taches.py")

else:
    st.info("Module tâches non disponible")

# ============================================================
# SECTION 3 : VUE GLOBALE TÂCHES (pour managers)
# ============================================================

role = st.session_state.get('role', '')
if role in ['SUPER_ADMIN', 'ADMIN', 'MANAGER']:
    st.markdown("---")
    st.markdown("### 👥 Vue globale des tâches")
    
    taches_globales = get_taches_globales()
    
    if taches_globales:
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("📋 Total ouvertes", taches_globales['total_ouvertes'])
        
        with col2:
            if taches_globales['total_urgentes'] > 0:
                st.metric("🔴 Urgentes", taches_globales['total_urgentes'], 
                         delta=f"{taches_globales['total_urgentes']} à traiter", delta_color="inverse")
            else:
                st.metric("🔴 Urgentes", 0)
        
        with col3:
            if taches_globales['total_retard'] > 0:
                st.metric("⏰ En retard", taches_globales['total_retard'],
                         delta=f"{taches_globales['total_retard']} en retard", delta_color="inverse")
            else:
                st.metric("⏰ En retard", 0)
        
        # Répartition par utilisateur
        if taches_globales['par_user']:
            st.markdown("#### Charge par utilisateur")
            cols = st.columns(min(len(taches_globales['par_user']), 4))
            for i, (user, nb) in enumerate(taches_globales['par_user'].items()):
                with cols[i % 4]:
                    st.metric(f"👤 {user}", f"{nb} tâche(s)")

# ============================================================
# SECTION 4 : APERÇU STOCK
# ============================================================

st.markdown("---")
st.markdown("### 📦 Aperçu Stock")

col1, col2, col3 = st.columns(3)

conn = get_connection()
if conn:
    try:
        cursor = conn.cursor()
        
        # Lots actifs
        cursor.execute("SELECT COUNT(*) as nb FROM lots_bruts WHERE is_active = TRUE")
        result = cursor.fetchone()
        nb_lots_actifs = result['nb'] if result else 0
        
        # Tonnage total (depuis stock_emplacements avec JOIN lots actifs)
        tonnage_tonnes = 0
        try:
            cursor.execute("""
                SELECT COALESCE(SUM(se.poids_total_kg), 0) as total 
                FROM stock_emplacements se
                JOIN lots_bruts l ON se.lot_id = l.id
                WHERE se.is_active = TRUE AND l.is_active = TRUE
            """)
            result = cursor.fetchone()
            tonnage_total = result['total'] if result else 0
            tonnage_tonnes = float(tonnage_total) / 1000
        except:
            conn.rollback()
            tonnage_tonnes = 0
        
        # Nombre variétés distinctes
        cursor.execute("SELECT COUNT(DISTINCT code_variete) as nb FROM lots_bruts WHERE is_active = TRUE")
        result = cursor.fetchone()
        nb_varietes = result['nb'] if result else 0
        
        cursor.close()
        conn.close()
        
        with col1:
            st.metric("📦 Lots actifs", f"{nb_lots_actifs:,}")
        
        with col2:
            st.metric("⚖️ Tonnage total", f"{tonnage_tonnes:,.1f} T")
        
        with col3:
            st.metric("🌱 Variétés", nb_varietes)
            
    except Exception as e:
        st.warning(f"⚠️ Erreur base de données : {str(e)}")
        if conn:
            conn.rollback()
            conn.close()
else:
    st.warning("⚠️ Connexion à la base de données en attente...")

# ============================================================
# NAVIGATION RAPIDE
# ============================================================

st.markdown("---")
st.markdown("### 🚀 Accès rapides")

col1, col2, col3, col4 = st.columns(4)

with col1:
    if st.button("📦 Stock Global", use_container_width=True):
        st.switch_page("pages/04_Stock_Global.py")

with col2:
    if st.button("🧼 Planning Lavage", use_container_width=True):
        st.switch_page("pages/05_Planning_Lavage.py")

with col3:
    if st.button("🔗 Affectation Stock", use_container_width=True):
        st.switch_page("pages/07_Affectation_Stock.py")

with col4:
    if st.button("📋 Tâches", use_container_width=True):
        st.switch_page("pages/17_Taches.py")

show_footer()
