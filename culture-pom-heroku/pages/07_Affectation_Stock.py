import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from database import get_connection
from components import show_footer
from auth import is_authenticated

st.set_page_config(page_title="Affectation Stock - Culture Pom", page_icon="📦", layout="wide")

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
    .delta-ok { color: #2ca02c; font-weight: bold; }
    .delta-warning { color: #ff7f0e; font-weight: bold; }
    .delta-danger { color: #d62728; font-weight: bold; }
</style>
""", unsafe_allow_html=True)

if not is_authenticated():
    st.warning("⚠️ Veuillez vous connecter pour accéder à cette page")
    st.stop()

st.title("📦 Affectation Stock aux Prévisions")
st.markdown("*Affecter les lots BRUT ou LAVÉ aux prévisions de vente*")
st.markdown("---")

# ==========================================
# FONCTIONS UTILITAIRES
# ==========================================

def get_semaine_actuelle():
    """Retourne le numéro de semaine et l'année actuels"""
    today = datetime.now()
    iso_calendar = today.isocalendar()
    return iso_calendar[1], iso_calendar[0]

def get_semaines_previsions():
    """Retourne les 3 semaines de prévisions (S+1, S+2, S+3)"""
    semaine_actuelle, annee_actuelle = get_semaine_actuelle()
    semaines = []
    
    for i in range(1, 4):
        sem = semaine_actuelle + i
        annee = annee_actuelle
        if sem > 52:
            sem = sem - 52
            annee = annee + 1
        semaines.append((annee, sem))
    
    return semaines

def format_semaine(annee, semaine):
    return f"S{semaine:02d}/{annee}"

def get_previsions_avec_affectations():
    """Récupère les prévisions avec les affectations consolidées"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        semaines = get_semaines_previsions()
        conditions = " OR ".join([f"(pv.annee = {a} AND pv.semaine = {s})" for a, s in semaines])
        
        query = f"""
        SELECT 
            pv.code_produit_commercial,
            pv.annee,
            pv.semaine,
            pc.marque,
            pc.libelle,
            pv.quantite_prevue_tonnes as prevu,
            
            -- Affecté LAVÉ
            COALESCE(SUM(CASE WHEN pa.statut_stock = 'LAVÉ' AND pa.is_active = TRUE 
                         THEN pa.quantite_affectee_tonnes ELSE 0 END), 0) as affecte_lave,
            
            -- Affecté BRUT (brut)
            COALESCE(SUM(CASE WHEN pa.statut_stock = 'BRUT' AND pa.is_active = TRUE 
                         THEN pa.quantite_affectee_tonnes ELSE 0 END), 0) as affecte_brut,
            
            -- Affecté BRUT net estimé
            COALESCE(SUM(CASE WHEN pa.statut_stock = 'BRUT' AND pa.is_active = TRUE 
                         THEN pa.poids_net_estime_tonnes ELSE 0 END), 0) as affecte_brut_net
            
        FROM previsions_ventes pv
        LEFT JOIN ref_produits_commerciaux pc ON pv.code_produit_commercial = pc.code_produit
        LEFT JOIN previsions_affectations pa ON pv.code_produit_commercial = pa.code_produit_commercial
            AND pv.annee = pa.annee AND pv.semaine = pa.semaine
        WHERE {conditions}
        GROUP BY pv.code_produit_commercial, pv.annee, pv.semaine, 
                 pc.marque, pc.libelle, pv.quantite_prevue_tonnes
        ORDER BY pv.annee, pv.semaine, pc.marque, pc.libelle
        """
        
        cursor.execute(query)
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        
        if rows:
            df = pd.DataFrame(rows)
            # Calculs
            df['total_affecte_net'] = df['affecte_lave'] + df['affecte_brut_net']
            df['delta'] = df['prevu'] - df['total_affecte_net']
            df['besoin_lavage'] = df['affecte_brut']
            
            # Convertir en numérique
            for col in ['prevu', 'affecte_lave', 'affecte_brut', 'affecte_brut_net', 
                        'total_affecte_net', 'delta', 'besoin_lavage']:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
            
            return df
        return pd.DataFrame()
        
    except Exception as e:
        st.error(f"❌ Erreur : {str(e)}")
        return pd.DataFrame()

def get_stock_disponible(type_stock=None):
    """Récupère le stock disponible (BRUT ou LAVÉ) avec calcul tare"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Filtre type stock
        type_filter = ""
        if type_stock:
            type_filter = f"AND COALESCE(se.type_stock, se.statut_lavage, 'BRUT') = '{type_stock}'"
        
        query = f"""
        SELECT 
            se.id as emplacement_id,
            se.lot_id,
            l.code_lot_interne,
            l.nom_usage,
            COALESCE(v.nom_variete, l.code_variete) as variete,
            l.code_variete,
            se.site_stockage,
            se.emplacement_stockage,
            se.nombre_unites,
            se.poids_total_kg,
            se.type_conditionnement,
            COALESCE(se.type_stock, se.statut_lavage, 'BRUT') as type_stock,
            
            -- Tare et source
            CASE 
                WHEN COALESCE(se.type_stock, se.statut_lavage) = 'LAVÉ' THEN 0
                WHEN lj.tare_reelle_pct IS NOT NULL THEN lj.tare_reelle_pct
                ELSE COALESCE(v.taux_dechet_moyen, 0.22) * 100
            END as tare_pct,
            
            CASE 
                WHEN COALESCE(se.type_stock, se.statut_lavage) = 'LAVÉ' THEN 'AUCUNE'
                WHEN lj.tare_reelle_pct IS NOT NULL THEN 'REELLE'
                ELSE 'THEORIQUE'
            END as tare_source,
            
            -- Quantité déjà affectée sur ce lot/emplacement
            COALESCE(aff.tonnes_affectees, 0) as deja_affecte_tonnes,
            COALESCE(aff.pallox_affectes, 0) as deja_affecte_pallox

        FROM stock_emplacements se
        JOIN lots_bruts l ON se.lot_id = l.id
        LEFT JOIN ref_varietes v ON l.code_variete = v.code_variete
        LEFT JOIN lavages_jobs lj ON se.lavage_job_id = lj.id AND lj.statut = 'TERMINÉ'
        LEFT JOIN (
            SELECT emplacement_id, 
                   SUM(quantite_affectee_tonnes) as tonnes_affectees,
                   SUM(quantite_affectee_pallox) as pallox_affectes
            FROM previsions_affectations
            WHERE is_active = TRUE
            GROUP BY emplacement_id
        ) aff ON se.id = aff.emplacement_id
        WHERE se.is_active = TRUE
          AND se.nombre_unites > 0
          {type_filter}
        ORDER BY l.code_lot_interne, se.site_stockage
        """
        
        cursor.execute(query)
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        
        if rows:
            df = pd.DataFrame(rows)
            
            # Conversions numériques
            numeric_cols = ['nombre_unites', 'poids_total_kg', 'tare_pct', 
                           'deja_affecte_tonnes', 'deja_affecte_pallox']
            for col in numeric_cols:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
            
            # Calculer disponible
            df['poids_dispo_kg'] = df['poids_total_kg'] - (df['deja_affecte_tonnes'] * 1000)
            df['poids_dispo_tonnes'] = df['poids_dispo_kg'] / 1000
            
            # Poids net estimé (après tare)
            df['poids_net_estime_kg'] = df.apply(
                lambda r: r['poids_dispo_kg'] if r['type_stock'] == 'LAVÉ' 
                else r['poids_dispo_kg'] * (1 - r['tare_pct'] / 100),
                axis=1
            )
            df['poids_net_estime_tonnes'] = df['poids_net_estime_kg'] / 1000
            
            # Filtrer ceux avec du stock disponible
            df = df[df['poids_dispo_kg'] > 0]
            
            return df
        return pd.DataFrame()
        
    except Exception as e:
        st.error(f"❌ Erreur : {str(e)}")
        return pd.DataFrame()

def get_stock_par_lot():
    """Récupère le stock agrégé par LOT (LAVÉ + BRUT combinés)"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        query = """
        WITH stock_detail AS (
            SELECT 
                se.lot_id,
                l.code_lot_interne,
                l.nom_usage,
                COALESCE(v.nom_variete, l.code_variete) as variete,
                l.code_variete,
                se.site_stockage,
                COALESCE(se.type_stock, se.statut_lavage, 'BRUT') as type_stock,
                se.poids_total_kg,
                
                -- Tare
                CASE 
                    WHEN COALESCE(se.type_stock, se.statut_lavage) = 'LAVÉ' THEN 0
                    WHEN lj.tare_reelle_pct IS NOT NULL THEN lj.tare_reelle_pct
                    ELSE COALESCE(v.taux_dechet_moyen, 0.22) * 100
                END as tare_pct,
                
                CASE 
                    WHEN COALESCE(se.type_stock, se.statut_lavage) = 'LAVÉ' THEN 'AUCUNE'
                    WHEN lj.tare_reelle_pct IS NOT NULL THEN 'REELLE'
                    ELSE 'THEORIQUE'
                END as tare_source,
                
                -- Déjà affecté sur cet emplacement
                COALESCE(aff.tonnes_affectees, 0) as deja_affecte_tonnes
                
            FROM stock_emplacements se
            JOIN lots_bruts l ON se.lot_id = l.id
            LEFT JOIN ref_varietes v ON l.code_variete = v.code_variete
            LEFT JOIN lavages_jobs lj ON se.lavage_job_id = lj.id AND lj.statut = 'TERMINÉ'
            LEFT JOIN (
                SELECT emplacement_id, SUM(quantite_affectee_tonnes) as tonnes_affectees
                FROM previsions_affectations
                WHERE is_active = TRUE
                GROUP BY emplacement_id
            ) aff ON se.id = aff.emplacement_id
            WHERE se.is_active = TRUE
              AND se.nombre_unites > 0
        )
        SELECT 
            lot_id,
            code_lot_interne,
            nom_usage,
            variete,
            code_variete,
            MIN(site_stockage) as site_principal,
            
            -- Stock LAVÉ disponible
            COALESCE(SUM(CASE WHEN type_stock = 'LAVÉ' 
                THEN (poids_total_kg - deja_affecte_tonnes * 1000) / 1000 
                ELSE 0 END), 0) as stock_lave_tonnes,
            
            -- Stock BRUT disponible (brut)
            COALESCE(SUM(CASE WHEN type_stock IN ('BRUT', 'GRENAILLES') 
                THEN (poids_total_kg - deja_affecte_tonnes * 1000) / 1000 
                ELSE 0 END), 0) as stock_brut_tonnes,
            
            -- Stock BRUT net estimé (après tare)
            COALESCE(SUM(CASE WHEN type_stock IN ('BRUT', 'GRENAILLES') 
                THEN (poids_total_kg - deja_affecte_tonnes * 1000) / 1000 * (1 - tare_pct / 100)
                ELSE 0 END), 0) as stock_brut_net_tonnes,
            
            -- Tare moyenne (pour les BRUT)
            COALESCE(AVG(CASE WHEN type_stock IN ('BRUT', 'GRENAILLES') THEN tare_pct END), 22) as tare_moyenne_pct,
            
            -- Source tare dominante
            MAX(CASE WHEN type_stock IN ('BRUT', 'GRENAILLES') THEN tare_source END) as tare_source
            
        FROM stock_detail
        WHERE (poids_total_kg - deja_affecte_tonnes * 1000) > 0
        GROUP BY lot_id, code_lot_interne, nom_usage, variete, code_variete
        HAVING (
            SUM(CASE WHEN type_stock = 'LAVÉ' THEN (poids_total_kg - deja_affecte_tonnes * 1000) ELSE 0 END) +
            SUM(CASE WHEN type_stock IN ('BRUT', 'GRENAILLES') THEN (poids_total_kg - deja_affecte_tonnes * 1000) ELSE 0 END)
        ) > 0
        ORDER BY code_lot_interne
        """
        
        cursor.execute(query)
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        
        if rows:
            df = pd.DataFrame(rows)
            
            # Conversions numériques
            numeric_cols = ['stock_lave_tonnes', 'stock_brut_tonnes', 'stock_brut_net_tonnes', 'tare_moyenne_pct']
            for col in numeric_cols:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
            
            # Total net = LAVÉ + BRUT net
            df['total_net_tonnes'] = df['stock_lave_tonnes'] + df['stock_brut_net_tonnes']
            
            return df
        return pd.DataFrame()
        
    except Exception as e:
        st.error(f"❌ Erreur get_stock_par_lot : {str(e)}")
        return pd.DataFrame()

def get_premier_emplacement_lot(lot_id, type_stock):
    """Récupère le premier emplacement disponible d'un lot pour un type de stock"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT se.id as emplacement_id, se.poids_total_kg
            FROM stock_emplacements se
            WHERE se.lot_id = %s
              AND se.is_active = TRUE
              AND se.nombre_unites > 0
              AND COALESCE(se.type_stock, se.statut_lavage, 'BRUT') = %s
            ORDER BY se.poids_total_kg DESC
            LIMIT 1
        """, (int(lot_id), type_stock))
        
        result = cursor.fetchone()
        cursor.close()
        conn.close()
        
        return result
        
    except Exception as e:
        st.error(f"❌ Erreur : {str(e)}")
        return None

def get_affectations_existantes():
    """Récupère les affectations existantes"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        query = """
        SELECT 
            pa.id,
            pa.code_produit_commercial,
            pa.annee,
            pa.semaine,
            pa.lot_id,
            pa.emplacement_id,
            pa.statut_stock,
            pa.quantite_affectee_tonnes,
            pa.quantite_affectee_pallox,
            pa.poids_net_estime_tonnes,
            pa.tare_utilisee_pct,
            pa.tare_source,
            pa.created_by,
            pa.created_at,
            l.code_lot_interne,
            COALESCE(v.nom_variete, l.code_variete) as variete,
            pc.marque,
            pc.libelle
        FROM previsions_affectations pa
        JOIN lots_bruts l ON pa.lot_id = l.id
        LEFT JOIN ref_varietes v ON l.code_variete = v.code_variete
        LEFT JOIN ref_produits_commerciaux pc ON pa.code_produit_commercial = pc.code_produit
        WHERE pa.is_active = TRUE
        ORDER BY pa.annee, pa.semaine, pc.marque, pa.created_at DESC
        """
        
        cursor.execute(query)
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        
        if rows:
            return pd.DataFrame(rows)
        return pd.DataFrame()
        
    except Exception as e:
        st.error(f"❌ Erreur : {str(e)}")
        return pd.DataFrame()

def create_affectation(code_produit, annee, semaine, lot_id, emplacement_id, 
                       statut_stock, quantite_tonnes, quantite_pallox,
                       poids_net_estime, tare_pct, tare_source):
    """Crée une nouvelle affectation"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Convertir types
        lot_id = int(lot_id)
        emplacement_id = int(emplacement_id)
        annee = int(annee)
        semaine = int(semaine)
        quantite_tonnes = float(quantite_tonnes)
        quantite_pallox = int(quantite_pallox) if quantite_pallox else None
        poids_net_estime = float(poids_net_estime) if poids_net_estime else None
        tare_pct = float(tare_pct) if tare_pct else None
        
        created_by = st.session_state.get('username', 'system')
        
        cursor.execute("""
            INSERT INTO previsions_affectations (
                code_produit_commercial, annee, semaine,
                lot_id, emplacement_id, statut_stock,
                quantite_affectee_tonnes, quantite_affectee_pallox,
                poids_net_estime_tonnes, tare_utilisee_pct, tare_source,
                created_by
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (code_produit, annee, semaine, lot_id, emplacement_id, statut_stock,
              quantite_tonnes, quantite_pallox, poids_net_estime, tare_pct, tare_source,
              created_by))
        
        new_id = cursor.fetchone()['id']
        conn.commit()
        cursor.close()
        conn.close()
        
        return True, f"✅ Affectation #{new_id} créée"
        
    except Exception as e:
        if 'conn' in locals():
            conn.rollback()
        return False, f"❌ Erreur : {str(e)}"

def delete_affectation(affectation_id):
    """Supprime (désactive) une affectation"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE previsions_affectations
            SET is_active = FALSE, updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
        """, (int(affectation_id),))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return True, "✅ Affectation supprimée"
        
    except Exception as e:
        if 'conn' in locals():
            conn.rollback()
        return False, f"❌ Erreur : {str(e)}"

def get_produits_commerciaux():
    """Récupère les produits commerciaux"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT code_produit, marque, libelle
            FROM ref_produits_commerciaux
            WHERE is_active = TRUE
            ORDER BY marque, libelle
        """)
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        return rows if rows else []
    except Exception as e:
        st.error(f"❌ Erreur : {str(e)}")
        return []

# ==========================================
# KPIs
# ==========================================

previsions = get_previsions_avec_affectations()

if not previsions.empty:
    col1, col2, col3, col4, col5 = st.columns(5)
    
    with col1:
        total_prevu = previsions['prevu'].sum()
        st.metric("📊 Total Prévu", f"{total_prevu:.0f} T")
    
    with col2:
        total_affecte = previsions['total_affecte_net'].sum()
        st.metric("📦 Total Affecté", f"{total_affecte:.0f} T")
    
    with col3:
        besoin_lavage = previsions['besoin_lavage'].sum()
        st.metric("🧼 Besoin Lavage", f"{besoin_lavage:.0f} T")
    
    with col4:
        delta_total = previsions['delta'].sum()
        delta_color = "normal" if delta_total <= 0 else "inverse"
        st.metric("📉 Delta Global", f"{delta_total:.0f} T", delta_color=delta_color)
    
    with col5:
        nb_complets = len(previsions[previsions['delta'] <= 0])
        nb_total = len(previsions)
        st.metric("✅ Prévisions OK", f"{nb_complets}/{nb_total}")

st.markdown("---")

# ==========================================
# ONGLETS
# ==========================================

tab1, tab2, tab3 = st.tabs(["📊 Vue Consolidée", "➕ Affecter un Lot", "📋 Affectations"])

# ==========================================
# ONGLET 1 : VUE CONSOLIDÉE
# ==========================================

with tab1:
    st.subheader("📊 Vue Consolidée - Prévisions vs Affectations")
    
    if previsions.empty:
        st.info("📭 Aucune prévision trouvée pour les 3 prochaines semaines")
    else:
        # Filtre semaine
        semaines_dispo = previsions.apply(lambda r: f"S{int(r['semaine']):02d}/{int(r['annee'])}", axis=1).unique().tolist()
        filtre_semaine = st.selectbox("Filtrer par semaine", ["Toutes"] + semaines_dispo, key="filtre_sem_conso")
        
        df_display = previsions.copy()
        if filtre_semaine != "Toutes":
            parts = filtre_semaine.split('/')
            sem = int(parts[0].replace('S', ''))
            annee = int(parts[1])
            df_display = df_display[(df_display['semaine'] == sem) & (df_display['annee'] == annee)]
        
        # Formater pour affichage
        df_display['Semaine'] = df_display.apply(lambda r: f"S{int(r['semaine']):02d}", axis=1)
        df_display['Prévu (T)'] = df_display['prevu'].round(1)
        df_display['LAVÉ (T)'] = df_display['affecte_lave'].round(1)
        df_display['BRUT (T)'] = df_display['affecte_brut'].round(1)
        df_display['BRUT net (T)'] = df_display['affecte_brut_net'].round(1)
        df_display['Total (T)'] = df_display['total_affecte_net'].round(1)
        df_display['Delta (T)'] = df_display['delta'].round(1)
        
        # Statut delta
        def statut_delta(delta):
            if delta <= 0:
                return "✅"
            elif delta <= 10:
                return "⚠️"
            else:
                return "❌"
        
        df_display['Statut'] = df_display['delta'].apply(statut_delta)
        
        # Affichage
        st.dataframe(
            df_display[['Semaine', 'marque', 'libelle', 'Prévu (T)', 'LAVÉ (T)', 
                       'BRUT (T)', 'BRUT net (T)', 'Total (T)', 'Delta (T)', 'Statut']],
            column_config={
                "Semaine": st.column_config.TextColumn("Sem", width="small"),
                "marque": st.column_config.TextColumn("Marque", width="small"),
                "libelle": st.column_config.TextColumn("Produit", width="large"),
                "Prévu (T)": st.column_config.NumberColumn("Prévu", format="%.1f"),
                "LAVÉ (T)": st.column_config.NumberColumn("LAVÉ", format="%.1f"),
                "BRUT (T)": st.column_config.NumberColumn("BRUT", format="%.1f"),
                "BRUT net (T)": st.column_config.NumberColumn("BRUT net*", format="%.1f", 
                    help="Estimation après tare"),
                "Total (T)": st.column_config.NumberColumn("Total", format="%.1f"),
                "Delta (T)": st.column_config.NumberColumn("Delta", format="%.1f"),
                "Statut": st.column_config.TextColumn("Statut", width="small"),
            },
            use_container_width=True,
            hide_index=True
        )
        
        st.caption("*BRUT net = estimation après application de la tare (réelle si connue, sinon théorique)")
        
        # Totaux par semaine
        st.markdown("---")
        st.markdown("### 📊 Totaux par Semaine")
        
        totaux = previsions.groupby(['annee', 'semaine']).agg({
            'prevu': 'sum',
            'affecte_lave': 'sum',
            'affecte_brut': 'sum',
            'total_affecte_net': 'sum',
            'delta': 'sum'
        }).reset_index()
        
        cols = st.columns(len(totaux) + 1)
        for i, (_, row) in enumerate(totaux.iterrows()):
            with cols[i]:
                sem_label = f"S{int(row['semaine']):02d}"
                delta = row['delta']
                st.metric(
                    sem_label,
                    f"{row['total_affecte_net']:.0f} / {row['prevu']:.0f} T",
                    f"Delta: {delta:.0f} T",
                    delta_color="normal" if delta <= 0 else "inverse"
                )
        
        with cols[-1]:
            st.metric(
                "🎯 Total",
                f"{totaux['total_affecte_net'].sum():.0f} / {totaux['prevu'].sum():.0f} T",
                f"Delta: {totaux['delta'].sum():.0f} T",
                delta_color="normal" if totaux['delta'].sum() <= 0 else "inverse"
            )

# ==========================================
# ONGLET 2 : AFFECTER UN LOT
# ==========================================

with tab2:
    st.subheader("➕ Affecter un Lot à une Prévision")
    
    # Étape 1 : Sélectionner prévision
    st.markdown("### 1️⃣ Sélectionner la Prévision")
    
    col1, col2 = st.columns(2)
    
    with col1:
        semaines = get_semaines_previsions()
        sem_options = [f"S{s:02d}/{a}" for a, s in semaines]
        selected_sem = st.selectbox("Semaine", sem_options, key="select_sem_affect")
        
        # Parser
        parts = selected_sem.split('/')
        selected_semaine = int(parts[0].replace('S', ''))
        selected_annee = int(parts[1])
    
    with col2:
        produits = get_produits_commerciaux()
        produit_options = [f"{p['marque']} - {p['libelle']}" for p in produits]
        produit_codes = [p['code_produit'] for p in produits]
        selected_produit_idx = st.selectbox("Produit", range(len(produit_options)), 
                                            format_func=lambda i: produit_options[i],
                                            key="select_produit_affect")
        selected_code_produit = produit_codes[selected_produit_idx] if produits else None
    
    st.markdown("---")
    
    # Étape 2 : Stock disponible PAR LOT (agrégé BRUT + LAVÉ)
    st.markdown("### 2️⃣ Sélectionner le Lot")
    st.caption("*Le tableau affiche le stock disponible par lot : LAVÉ + BRUT (avec estimation après tare)*")
    
    stock_par_lot = get_stock_par_lot()
    
    if stock_par_lot.empty:
        st.warning("⚠️ Aucun stock disponible")
    else:
        # Filtres
        col1, col2 = st.columns(2)
        with col1:
            varietes = ["Toutes"] + sorted(stock_par_lot['variete'].dropna().unique().tolist())
            filtre_variete = st.selectbox("Filtrer par variété", varietes, key="filtre_var_stock")
        with col2:
            sites = ["Tous"] + sorted(stock_par_lot['site_principal'].dropna().unique().tolist())
            filtre_site = st.selectbox("Filtrer par site", sites, key="filtre_site_stock")
        
        stock_filtre = stock_par_lot.copy()
        if filtre_variete != "Toutes":
            stock_filtre = stock_filtre[stock_filtre['variete'] == filtre_variete]
        if filtre_site != "Tous":
            stock_filtre = stock_filtre[stock_filtre['site_principal'] == filtre_site]
        
        if not stock_filtre.empty:
            st.caption(f"💡 {len(stock_filtre)} lot(s) disponible(s)")
            
            # Préparer tableau
            df_stock = stock_filtre.copy().reset_index(drop=True)
            df_stock['_idx'] = df_stock.index
            
            # Colonnes affichage
            df_stock['Code Lot'] = df_stock['code_lot_interne']
            df_stock['Variété'] = df_stock['variete']
            df_stock['Site'] = df_stock['site_principal']
            df_stock['LAVÉ (T)'] = df_stock['stock_lave_tonnes'].round(2)
            df_stock['BRUT (T)'] = df_stock['stock_brut_tonnes'].round(2)
            df_stock['BRUT net* (T)'] = df_stock['stock_brut_net_tonnes'].round(2)
            df_stock['Total net (T)'] = df_stock['total_net_tonnes'].round(2)
            df_stock['Tare moy %'] = df_stock['tare_moyenne_pct'].round(1)
            
            column_config = {
                "_idx": None,
                "lot_id": None,
                "Code Lot": st.column_config.TextColumn("Code Lot", width="large"),
                "Variété": st.column_config.TextColumn("Variété", width="medium"),
                "Site": st.column_config.TextColumn("Site", width="medium"),
                "LAVÉ (T)": st.column_config.NumberColumn("LAVÉ", format="%.1f", help="Stock déjà lavé"),
                "BRUT (T)": st.column_config.NumberColumn("BRUT", format="%.1f", help="Stock brut"),
                "BRUT net* (T)": st.column_config.NumberColumn("BRUT net*", format="%.1f", help="BRUT après tare estimée"),
                "Total net (T)": st.column_config.NumberColumn("Total net", format="%.1f", help="LAVÉ + BRUT net"),
                "Tare moy %": st.column_config.NumberColumn("Tare %", format="%.1f"),
            }
            
            # Tableau sélectionnable
            event = st.dataframe(
                df_stock[['_idx', 'lot_id', 'Code Lot', 'Variété', 'Site', 
                         'LAVÉ (T)', 'BRUT (T)', 'BRUT net* (T)', 'Total net (T)', 'Tare moy %']],
                column_config=column_config,
                use_container_width=True,
                hide_index=True,
                on_select="rerun",
                selection_mode="single-row",
                key="stock_table_affect"
            )
            
            selected_rows = event.selection.rows if hasattr(event, 'selection') else []
            
            st.markdown("---")
            
            # Étape 3 : Quantité et validation
            st.markdown("### 3️⃣ Quantité à Affecter (en tonnes NET)")
            
            if len(selected_rows) > 0:
                selected_idx = selected_rows[0]
                selected_lot = df_stock.iloc[selected_idx]
                
                # Résumé du lot
                st.success(f"✅ Lot sélectionné : **{selected_lot['Code Lot']}** - {selected_lot['Variété']}")
                
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("LAVÉ dispo", f"{selected_lot['LAVÉ (T)']:.1f} T")
                with col2:
                    st.metric("BRUT dispo", f"{selected_lot['BRUT (T)']:.1f} T", 
                              f"≈ {selected_lot['BRUT net* (T)']:.1f} T net")
                with col3:
                    st.metric("Total NET", f"{selected_lot['Total net (T)']:.1f} T")
                
                st.markdown("---")
                
                col1, col2 = st.columns(2)
                
                with col1:
                    mode_quantite = st.radio("Mode", ["Total disponible", "Quantité partielle"], 
                                             horizontal=True, key="mode_qte")
                
                with col2:
                    max_dispo = float(selected_lot['total_net_tonnes'])
                    
                    if mode_quantite == "Total disponible":
                        quantite_net = max_dispo
                        st.metric("Quantité NET à affecter", f"{quantite_net:.2f} T")
                    else:
                        quantite_net = st.number_input(
                            "Quantité NET (T)", 
                            min_value=0.1, 
                            max_value=max_dispo,
                            value=min(10.0, max_dispo),
                            step=0.5,
                            key="qte_partielle"
                        )
                
                # Détail de l'affectation
                st.markdown("#### 📊 Répartition automatique")
                
                stock_lave = float(selected_lot['stock_lave_tonnes'])
                stock_brut_net = float(selected_lot['stock_brut_net_tonnes'])
                tare_pct = float(selected_lot['tare_moyenne_pct'])
                
                # Logique : on prend d'abord le LAVÉ, puis le BRUT si besoin
                if quantite_net <= stock_lave:
                    affecte_lave = quantite_net
                    affecte_brut = 0
                    affecte_brut_brut = 0
                else:
                    affecte_lave = stock_lave
                    reste_net = quantite_net - stock_lave
                    affecte_brut = min(reste_net, stock_brut_net)
                    # Convertir net → brut (inverse de la tare)
                    if tare_pct < 100:
                        affecte_brut_brut = affecte_brut / (1 - tare_pct / 100)
                    else:
                        affecte_brut_brut = affecte_brut
                
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.info(f"🧼 **LAVÉ** : {affecte_lave:.2f} T")
                with col2:
                    if affecte_brut > 0:
                        st.warning(f"📦 **BRUT** : {affecte_brut_brut:.2f} T brut → {affecte_brut:.2f} T net")
                    else:
                        st.info("📦 **BRUT** : 0 T")
                with col3:
                    besoin_lavage = affecte_brut_brut if affecte_brut > 0 else 0
                    if besoin_lavage > 0:
                        st.error(f"🧼 **À laver** : {besoin_lavage:.1f} T")
                    else:
                        st.success("✅ Pas de lavage requis")
                
                # Bouton affecter
                st.markdown("---")
                
                col1, col2 = st.columns([2, 1])
                
                with col1:
                    if st.button("📦 Affecter ce lot", type="primary", use_container_width=True):
                        success_count = 0
                        error_msg = None
                        
                        # Créer affectation LAVÉ si > 0
                        if affecte_lave > 0:
                            # Récupérer le premier emplacement LAVÉ
                            empl_lave = get_premier_emplacement_lot(selected_lot['lot_id'], 'LAVÉ')
                            if empl_lave:
                                success, msg = create_affectation(
                                    code_produit=selected_code_produit,
                                    annee=selected_annee,
                                    semaine=selected_semaine,
                                    lot_id=selected_lot['lot_id'],
                                    emplacement_id=empl_lave['emplacement_id'],
                                    statut_stock='LAVÉ',
                                    quantite_tonnes=affecte_lave,
                                    quantite_pallox=None,
                                    poids_net_estime=affecte_lave,
                                    tare_pct=0,
                                    tare_source='AUCUNE'
                                )
                                if success:
                                    success_count += 1
                                else:
                                    error_msg = msg
                        
                        # Créer affectation BRUT si > 0
                        if affecte_brut_brut > 0 and error_msg is None:
                            # Récupérer le premier emplacement BRUT
                            empl_brut = get_premier_emplacement_lot(selected_lot['lot_id'], 'BRUT')
                            if empl_brut:
                                success, msg = create_affectation(
                                    code_produit=selected_code_produit,
                                    annee=selected_annee,
                                    semaine=selected_semaine,
                                    lot_id=selected_lot['lot_id'],
                                    emplacement_id=empl_brut['emplacement_id'],
                                    statut_stock='BRUT',
                                    quantite_tonnes=affecte_brut_brut,
                                    quantite_pallox=None,
                                    poids_net_estime=affecte_brut,
                                    tare_pct=tare_pct,
                                    tare_source=selected_lot.get('tare_source', 'THEORIQUE')
                                )
                                if success:
                                    success_count += 1
                                else:
                                    error_msg = msg
                        
                        if error_msg:
                            st.error(error_msg)
                        elif success_count > 0:
                            st.success(f"✅ {success_count} affectation(s) créée(s)")
                            st.balloons()
                            
                            if besoin_lavage > 0:
                                st.warning(f"⚠️ {besoin_lavage:.1f} T de BRUT à laver ! Pensez à créer un job lavage.")
                            
                            st.rerun()
                        else:
                            st.error("❌ Aucune affectation créée")
            else:
                st.info("👆 Sélectionnez un lot dans le tableau ci-dessus")
                st.button("📦 Affecter ce lot", type="primary", use_container_width=True, disabled=True)
        else:
            st.warning("⚠️ Aucun lot correspond aux filtres")

# ==========================================
# ONGLET 3 : AFFECTATIONS EXISTANTES
# ==========================================

with tab3:
    st.subheader("📋 Affectations Existantes")
    
    affectations = get_affectations_existantes()
    
    if affectations.empty:
        st.info("📭 Aucune affectation")
    else:
        # Filtres
        col1, col2 = st.columns(2)
        
        with col1:
            semaines_aff = affectations.apply(
                lambda r: f"S{int(r['semaine']):02d}/{int(r['annee'])}", axis=1
            ).unique().tolist()
            filtre_sem_aff = st.selectbox("Semaine", ["Toutes"] + semaines_aff, key="filtre_sem_aff")
        
        with col2:
            types_aff = affectations['statut_stock'].unique().tolist()
            filtre_type_aff = st.selectbox("Type stock", ["Tous"] + types_aff, key="filtre_type_aff")
        
        df_aff = affectations.copy()
        if filtre_sem_aff != "Toutes":
            parts = filtre_sem_aff.split('/')
            sem = int(parts[0].replace('S', ''))
            annee = int(parts[1])
            df_aff = df_aff[(df_aff['semaine'] == sem) & (df_aff['annee'] == annee)]
        if filtre_type_aff != "Tous":
            df_aff = df_aff[df_aff['statut_stock'] == filtre_type_aff]
        
        st.caption(f"💡 {len(df_aff)} affectation(s)")
        
        # Affichage
        for _, row in df_aff.iterrows():
            with st.expander(f"#{row['id']} - {row['marque']} {row['libelle']} - S{int(row['semaine']):02d}"):
                col1, col2 = st.columns(2)
                
                with col1:
                    st.write(f"**Produit** : {row['marque']} - {row['libelle']}")
                    st.write(f"**Semaine** : S{int(row['semaine']):02d}/{int(row['annee'])}")
                    st.write(f"**Lot** : {row['code_lot_interne']}")
                    st.write(f"**Variété** : {row['variete']}")
                
                with col2:
                    st.write(f"**Type** : {row['statut_stock']}")
                    st.write(f"**Quantité** : {row['quantite_affectee_tonnes']:.2f} T")
                    if row['statut_stock'] == 'BRUT':
                        st.write(f"**Net estimé** : {row['poids_net_estime_tonnes']:.2f} T")
                        st.write(f"**Tare** : {row['tare_utilisee_pct']:.1f}% ({row['tare_source']})")
                    st.write(f"**Créé par** : {row['created_by']}")
                
                # Bouton supprimer
                if st.button(f"🗑️ Supprimer", key=f"del_aff_{row['id']}"):
                    success, msg = delete_affectation(row['id'])
                    if success:
                        st.success(msg)
                        st.rerun()
                    else:
                        st.error(msg)

# ==========================================
# FOOTER
# ==========================================

show_footer()
