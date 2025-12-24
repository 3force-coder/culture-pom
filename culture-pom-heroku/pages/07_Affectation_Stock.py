import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from database import get_connection
from components import show_footer
from auth import require_access

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
    .kpi-detail { font-size: 0.8rem; color: #666; }
    
    /* En-têtes tableau : gras et centré */
    [data-testid="stDataFrame"] th {
        font-weight: bold !important;
        text-align: center !important;
    }
    [data-testid="stDataFrame"] th div {
        font-weight: bold !important;
        text-align: center !important;
    }
</style>
""", unsafe_allow_html=True)

# ============================================================
# 🔒 CONTRÔLE D'ACCÈS RBAC
# ============================================================
require_access("COMMERCIAL")
# ============================================================


st.title("📦 Affectation Stock aux Prévisions")
st.markdown("*Affecter les lots BRUT ou LAVÉ aux prévisions de vente (5 semaines)*")
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
    """Retourne les 5 semaines de prévisions (S+1 à S+5)"""
    semaine_actuelle, annee_actuelle = get_semaine_actuelle()
    semaines = []
    
    for i in range(1, 6):  # 5 semaines au lieu de 3
        sem = semaine_actuelle + i
        annee = annee_actuelle
        if sem > 52:
            sem = sem - 52
            annee = annee + 1
        semaines.append((annee, sem))
    
    return semaines

def format_semaine(annee, semaine):
    return f"S{semaine:02d}/{annee}"


def get_previsions_par_produit():
    """
    Récupère les prévisions AGRÉGÉES par produit sur 5 semaines
    avec les affectations consolidées
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        semaines = get_semaines_previsions()
        conditions = " OR ".join([f"(pv.annee = {a} AND pv.semaine = {s})" for a, s in semaines])
        
        query = f"""
        SELECT 
            pv.code_produit_commercial,
            pc.marque,
            pc.libelle,
            
            -- Total prévu sur 5 semaines
            SUM(pv.quantite_prevue_tonnes) as prevu_total,
            
            -- Affecté LAVÉ (global)
            COALESCE((
                SELECT SUM(pa.poids_net_estime_tonnes) 
                FROM previsions_affectations pa 
                WHERE pa.code_produit_commercial = pv.code_produit_commercial 
                  AND pa.is_active = TRUE 
                  AND pa.statut_stock = 'LAVÉ'
            ), 0) as affecte_lave,
            
            -- Affecté BRUT brut (global)
            COALESCE((
                SELECT SUM(pa.quantite_affectee_tonnes) 
                FROM previsions_affectations pa 
                WHERE pa.code_produit_commercial = pv.code_produit_commercial 
                  AND pa.is_active = TRUE 
                  AND pa.statut_stock = 'BRUT'
            ), 0) as affecte_brut,
            
            -- Affecté BRUT net estimé (global)
            COALESCE((
                SELECT SUM(pa.poids_net_estime_tonnes) 
                FROM previsions_affectations pa 
                WHERE pa.code_produit_commercial = pv.code_produit_commercial 
                  AND pa.is_active = TRUE 
                  AND pa.statut_stock = 'BRUT'
            ), 0) as affecte_brut_net
            
        FROM previsions_ventes pv
        LEFT JOIN ref_produits_commerciaux pc ON pv.code_produit_commercial = pc.code_produit
        WHERE {conditions}
        GROUP BY pv.code_produit_commercial, pc.marque, pc.libelle
        ORDER BY pc.marque, pc.libelle
        """
        
        cursor.execute(query)
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        
        if rows:
            df = pd.DataFrame(rows)
            # Calculs
            df['total_affecte_net'] = df['affecte_lave'] + df['affecte_brut_net']
            df['delta'] = df['prevu_total'] - df['total_affecte_net']
            df['besoin_lavage'] = df['affecte_brut']
            
            # Convertir en numérique
            for col in ['prevu_total', 'affecte_lave', 'affecte_brut', 'affecte_brut_net', 
                        'total_affecte_net', 'delta', 'besoin_lavage']:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
            
            return df
        return pd.DataFrame()
        
    except Exception as e:
        st.error(f"❌ Erreur : {str(e)}")
        return pd.DataFrame()


def get_previsions_par_semaine(code_produit):
    """
    Récupère les prévisions par semaine pour un produit donné
    avec la répartition FIFO de l'affecté
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        semaines = get_semaines_previsions()
        conditions = " OR ".join([f"(annee = {a} AND semaine = {s})" for a, s in semaines])
        
        # Prévisions par semaine
        query = f"""
        SELECT annee, semaine, quantite_prevue_tonnes as prevu
        FROM previsions_ventes
        WHERE code_produit_commercial = %s AND ({conditions})
        ORDER BY annee, semaine
        """
        
        cursor.execute(query, (code_produit,))
        rows = cursor.fetchall()
        
        if not rows:
            cursor.close()
            conn.close()
            return pd.DataFrame()
        
        df = pd.DataFrame(rows)
        df['prevu'] = pd.to_numeric(df['prevu'], errors='coerce').fillna(0)
        
        # Total affecté pour ce produit
        cursor.execute("""
            SELECT COALESCE(SUM(poids_net_estime_tonnes), 0) as total_affecte
            FROM previsions_affectations
            WHERE code_produit_commercial = %s AND is_active = TRUE
        """, (code_produit,))
        
        result = cursor.fetchone()
        total_affecte = float(result['total_affecte']) if result else 0
        
        cursor.close()
        conn.close()
        
        # Répartition FIFO : on couvre les semaines les plus proches en premier
        reste_a_affecter = total_affecte
        couvert_list = []
        delta_list = []
        
        for _, row in df.iterrows():
            prevu = float(row['prevu'])
            if reste_a_affecter >= prevu:
                couvert = prevu
                reste_a_affecter -= prevu
            else:
                couvert = reste_a_affecter
                reste_a_affecter = 0
            
            couvert_list.append(couvert)
            delta_list.append(prevu - couvert)
        
        df['couvert'] = couvert_list
        df['delta'] = delta_list
        df['semaine_label'] = df.apply(lambda r: f"S{int(r['semaine']):02d}", axis=1)
        
        return df
        
    except Exception as e:
        st.error(f"❌ Erreur : {str(e)}")
        return pd.DataFrame()


def get_stock_par_lot():
    """Récupère le stock agrégé par LOT (LAVÉ + BRUT combinés) avec nom et producteur"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        query = """
        WITH stock_detail AS (
            SELECT 
                l.id as lot_id,
                l.code_lot_interne,
                l.nom_usage,
                l.code_producteur,
                COALESCE(p.nom, l.code_producteur) as producteur_nom,
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
            LEFT JOIN ref_producteurs p ON l.code_producteur = p.code_producteur
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
            code_producteur,
            producteur_nom,
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
        GROUP BY lot_id, code_lot_interne, nom_usage, code_producteur, producteur_nom, variete, code_variete
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


def get_affectations_par_produit(code_produit=None):
    """Récupère les affectations existantes (optionnellement filtrées par produit)"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        query = """
        SELECT 
            pa.id,
            pa.code_produit_commercial,
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
            l.nom_usage,
            l.code_producteur,
            COALESCE(v.nom_variete, l.code_variete) as variete,
            pc.marque,
            pc.libelle
        FROM previsions_affectations pa
        JOIN lots_bruts l ON pa.lot_id = l.id
        LEFT JOIN ref_varietes v ON l.code_variete = v.code_variete
        LEFT JOIN ref_produits_commerciaux pc ON pa.code_produit_commercial = pc.code_produit
        WHERE pa.is_active = TRUE
        """
        
        if code_produit:
            query += " AND pa.code_produit_commercial = %s"
            cursor.execute(query + " ORDER BY pa.created_at DESC", (code_produit,))
        else:
            cursor.execute(query + " ORDER BY pc.marque, pc.libelle, pa.created_at DESC")
        
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        
        if rows:
            return pd.DataFrame(rows)
        return pd.DataFrame()
        
    except Exception as e:
        st.error(f"❌ Erreur : {str(e)}")
        return pd.DataFrame()


def create_affectation(code_produit, lot_id, emplacement_id, 
                       statut_stock, quantite_tonnes,
                       poids_net_estime, tare_pct, tare_source):
    """Crée une nouvelle affectation CT (Court Terme) avec année/semaine courante"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Convertir types
        lot_id = int(lot_id)
        emplacement_id = int(emplacement_id)
        quantite_tonnes = float(quantite_tonnes)
        poids_net_estime = float(poids_net_estime) if poids_net_estime else None
        tare_pct = float(tare_pct) if tare_pct else None
        
        created_by = st.session_state.get('username', 'system')
        
        # Récupérer année et semaine courante (contrainte NOT NULL sur ces colonnes)
        semaine_courante, annee_courante = get_semaine_actuelle()
        
        cursor.execute("""
            INSERT INTO previsions_affectations (
                code_produit_commercial, annee, semaine,
                lot_id, emplacement_id, statut_stock,
                quantite_affectee_tonnes, quantite_affectee_pallox,
                poids_net_estime_tonnes, tare_utilisee_pct, tare_source,
                created_by, type_affectation
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, NULL, %s, %s, %s, %s, 'CT')
            RETURNING id
        """, (code_produit, annee_courante, semaine_courante, lot_id, emplacement_id, statut_stock,
              quantite_tonnes, poids_net_estime, tare_pct, tare_source,
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
    """Supprime (désactive) une affectation - SOFT DELETE"""
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
# ⭐ FONCTIONS STATUT DELTA
# ==========================================

def get_statut_delta(delta, prevu):
    """
    Calcule l'icône de statut basée sur le % de couverture
    
    ✅ Couvert : delta <= 0 (prévu couvert ou surplus)
    ⚠️ Manque partiel : 0 < delta < 50% du prévu
    ❌ Manque critique : delta >= 50% du prévu
    ➖ Pas de prévision : prevu = 0
    """
    if prevu == 0 or pd.isna(prevu):
        return "➖"  # Pas de prévision
    
    if delta <= 0:
        return "✅"  # Couvert ou surplus
    
    pct_manquant = (delta / prevu) * 100
    
    if pct_manquant < 50:
        return "⚠️"  # Manque < 50%
    else:
        return "❌"  # Manque >= 50%


def get_statut_counts(df, col_delta='delta', col_prevu='prevu_total'):
    """Compte les statuts par catégorie"""
    counts = {'ok': 0, 'warning': 0, 'critical': 0, 'none': 0}
    
    for _, row in df.iterrows():
        statut = get_statut_delta(row[col_delta], row[col_prevu])
        if statut == "✅":
            counts['ok'] += 1
        elif statut == "⚠️":
            counts['warning'] += 1
        elif statut == "❌":
            counts['critical'] += 1
        else:
            counts['none'] += 1
    
    return counts


# ==========================================
# KPIs GLOBAUX
# ==========================================

previsions_produits = get_previsions_par_produit()

if not previsions_produits.empty:
    # KPIs globaux
    col1, col2, col3, col4, col5 = st.columns(5)
    
    with col1:
        total_prevu = previsions_produits['prevu_total'].sum()
        st.metric("📊 Prévu 5 sem.", f"{total_prevu:.0f} T")
    
    with col2:
        total_affecte = previsions_produits['total_affecte_net'].sum()
        st.metric("📦 Total Affecté", f"{total_affecte:.0f} T")
    
    with col3:
        besoin_lavage = previsions_produits['besoin_lavage'].sum()
        st.metric("🧼 Besoin Lavage", f"{besoin_lavage:.0f} T")
    
    with col4:
        delta_total = previsions_produits['delta'].sum()
        delta_color = "normal" if delta_total <= 0 else "inverse"
        st.metric("📉 Delta Global", f"{delta_total:.0f} T", delta_color=delta_color)
    
    with col5:
        counts_global = get_statut_counts(previsions_produits)
        nb_complets = counts_global['ok']
        nb_total = len(previsions_produits)
        st.metric("✅ Produits OK", f"{nb_complets}/{nb_total}")

st.markdown("---")

# ==========================================
# ONGLETS
# ==========================================

tab1, tab2, tab3 = st.tabs(["📊 Vue Consolidée", "➕ Affecter un Lot", "📋 Affectations"])

# ==========================================
# ONGLET 1 : VUE CONSOLIDÉE PAR PRODUIT
# ==========================================

with tab1:
    st.subheader("📊 Vue Consolidée - Prévisions 5 semaines par Produit")
    
    if previsions_produits.empty:
        st.info("📭 Aucune prévision trouvée pour les 5 prochaines semaines")
    else:
        # Filtres
        col_f1, col_f2 = st.columns(2)
        
        with col_f1:
            marques_dispo = sorted(previsions_produits['marque'].dropna().unique().tolist())
            filtre_marque = st.selectbox("Filtrer par marque", ["Toutes"] + marques_dispo, key="filtre_marque_conso")
        
        with col_f2:
            # Filtre par statut
            filtre_statut = st.selectbox("Filtrer par statut", 
                ["Tous", "❌ Manque critique", "⚠️ Manque partiel", "✅ Couvert"],
                key="filtre_statut_conso")
        
        # Filtre produit multi-sélection avec recherche
        produits_dispo = sorted(previsions_produits['libelle'].dropna().unique().tolist())
        filtre_produits = st.multiselect(
            "🔍 Rechercher/Sélectionner produits",
            options=produits_dispo,
            default=[],
            key="filtre_produits_conso",
            placeholder="Tous les produits (ou tapez pour rechercher...)"
        )
        
        st.markdown("---")
        
        # Appliquer filtres
        df_filtered = previsions_produits.copy()
        if filtre_marque != "Toutes":
            df_filtered = df_filtered[df_filtered['marque'] == filtre_marque]
        
        if filtre_produits:
            df_filtered = df_filtered[df_filtered['libelle'].isin(filtre_produits)]
        
        # Ajouter colonne statut pour filtrage
        df_filtered['Statut'] = df_filtered.apply(
            lambda r: get_statut_delta(r['delta'], r['prevu_total']), axis=1
        )
        
        if filtre_statut == "❌ Manque critique":
            df_filtered = df_filtered[df_filtered['Statut'] == "❌"]
        elif filtre_statut == "⚠️ Manque partiel":
            df_filtered = df_filtered[df_filtered['Statut'] == "⚠️"]
        elif filtre_statut == "✅ Couvert":
            df_filtered = df_filtered[df_filtered['Statut'] == "✅"]
        
        if df_filtered.empty:
            st.warning("⚠️ Aucun résultat avec ces filtres")
        else:
            # Préparer affichage
            df_display = df_filtered.copy()
            df_display['Prévu 5s (T)'] = df_display['prevu_total'].round(1)
            df_display['LAVÉ (T)'] = df_display['affecte_lave'].round(1)
            df_display['BRUT net (T)'] = df_display['affecte_brut_net'].round(1)
            df_display['Total (T)'] = df_display['total_affecte_net'].round(1)
            df_display['Delta (T)'] = df_display['delta'].round(1)
            
            # % Lavé
            def calc_pct_lave(row):
                total = row['total_affecte_net']
                lave = row['affecte_lave']
                if total > 0:
                    pct = (lave / total) * 100
                    return f"{pct:.0f}%"
                elif lave == 0 and total == 0:
                    return "-"
                else:
                    return "100%"
            
            df_display['% Lavé'] = df_display.apply(calc_pct_lave, axis=1)
            
            # Affichage tableau avec sélection
            event = st.dataframe(
                df_display[['marque', 'libelle', 'Prévu 5s (T)', 'LAVÉ (T)', 
                           'BRUT net (T)', 'Total (T)', 'Delta (T)', '% Lavé', 'Statut']],
                column_config={
                    "marque": st.column_config.TextColumn("Marque", width="small"),
                    "libelle": st.column_config.TextColumn("Produit", width="large"),
                    "Prévu 5s (T)": st.column_config.NumberColumn("Prévu 5s", format="%.1f", help="Total prévu sur 5 semaines"),
                    "LAVÉ (T)": st.column_config.NumberColumn("LAVÉ", format="%.1f"),
                    "BRUT net (T)": st.column_config.NumberColumn("BRUT net*", format="%.1f"),
                    "Total (T)": st.column_config.NumberColumn("Total", format="%.1f"),
                    "Delta (T)": st.column_config.NumberColumn("Delta", format="%.1f"),
                    "% Lavé": st.column_config.TextColumn("% Lavé", width="small"),
                    "Statut": st.column_config.TextColumn("Statut", width="small"),
                },
                use_container_width=True,
                hide_index=True,
                on_select="rerun",
                selection_mode="single-row",
                key="table_previsions_produits"
            )
            
            st.caption("*BRUT net = estimation après tare (~22%)")
            
            # Si produit sélectionné → afficher vue par semaine
            selected_rows = event.selection.rows if hasattr(event, 'selection') else []
            
            if len(selected_rows) > 0:
                selected_idx = selected_rows[0]
                selected_row = df_display.iloc[selected_idx]
                code_produit = selected_row['code_produit_commercial']
                
                st.markdown("---")
                st.markdown(f"### 📅 Répartition par Semaine : **{selected_row['marque']} - {selected_row['libelle']}**")
                
                # Récupérer détail par semaine
                df_semaines = get_previsions_par_semaine(code_produit)
                
                if not df_semaines.empty:
                    # Afficher les métriques par semaine
                    cols = st.columns(len(df_semaines) + 1)
                    
                    for i, (_, sem_row) in enumerate(df_semaines.iterrows()):
                        with cols[i]:
                            delta_sem = sem_row['delta']
                            statut_sem = get_statut_delta(delta_sem, sem_row['prevu'])
                            
                            st.metric(
                                sem_row['semaine_label'],
                                f"{sem_row['couvert']:.0f} / {sem_row['prevu']:.0f} T",
                                f"{'-' if delta_sem > 0 else '+'}{abs(delta_sem):.0f} T",
                                delta_color="normal" if delta_sem <= 0 else "inverse"
                            )
                            st.markdown(f"<div style='text-align:center'>{statut_sem}</div>", unsafe_allow_html=True)
                    
                    # Total
                    with cols[-1]:
                        total_prevu_sem = df_semaines['prevu'].sum()
                        total_couvert = df_semaines['couvert'].sum()
                        delta_tot = df_semaines['delta'].sum()
                        
                        st.metric(
                            "🎯 Total",
                            f"{total_couvert:.0f} / {total_prevu_sem:.0f} T",
                            f"{'-' if delta_tot > 0 else '+'}{abs(delta_tot):.0f} T",
                            delta_color="normal" if delta_tot <= 0 else "inverse"
                        )
                
                # Boutons actions
                col1, col2 = st.columns(2)
                
                with col1:
                    if selected_row['delta'] > 0:
                        if st.button("📋 Créer tâche manque stock", type="secondary", use_container_width=True):
                            st.session_state['tache_prefill_titre'] = f"Manque stock {selected_row['marque']} {selected_row['libelle']}"
                            st.session_state['tache_prefill_source_type'] = 'prevision'
                            st.session_state['tache_prefill_source_label'] = f"{selected_row['marque']} - {selected_row['libelle']} - Delta: {selected_row['delta']:.1f}T"
                            st.switch_page("pages/17_Taches.py")
                
                with col2:
                    if st.button("➕ Affecter un lot à ce produit", type="primary", use_container_width=True):
                        st.session_state['produit_preselect'] = code_produit
                        st.session_state['produit_preselect_label'] = f"{selected_row['marque']} - {selected_row['libelle']}"
                        st.rerun()


# ==========================================
# ONGLET 2 : AFFECTER UN LOT
# ==========================================

with tab2:
    st.subheader("➕ Affecter un Lot à un Produit")
    
    # Étape 1 : Sélectionner produit
    st.markdown("### 1️⃣ Sélectionner le Produit Commercial")
    
    produits = get_produits_commerciaux()
    produit_options = [f"{p['marque']} - {p['libelle']}" for p in produits]
    produit_codes = [p['code_produit'] for p in produits]
    
    # Pré-sélection si vient de l'onglet 1
    default_idx = 0
    if 'produit_preselect' in st.session_state:
        try:
            default_idx = produit_codes.index(st.session_state['produit_preselect'])
        except ValueError:
            default_idx = 0
        # Nettoyer
        del st.session_state['produit_preselect']
        if 'produit_preselect_label' in st.session_state:
            del st.session_state['produit_preselect_label']
    
    selected_produit_idx = st.selectbox(
        "Produit commercial", 
        range(len(produit_options)), 
        format_func=lambda i: produit_options[i],
        index=default_idx,
        key="select_produit_affect"
    )
    selected_code_produit = produit_codes[selected_produit_idx] if produits else None
    
    # Afficher résumé prévisions du produit
    if selected_code_produit:
        produit_info = previsions_produits[previsions_produits['code_produit_commercial'] == selected_code_produit]
        if not produit_info.empty:
            p = produit_info.iloc[0]
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Prévu 5 sem.", f"{p['prevu_total']:.0f} T")
            with col2:
                st.metric("Affecté", f"{p['total_affecte_net']:.0f} T")
            with col3:
                st.metric("Delta", f"{p['delta']:.0f} T", 
                         delta_color="normal" if p['delta'] <= 0 else "inverse")
            with col4:
                statut = get_statut_delta(p['delta'], p['prevu_total'])
                st.metric("Statut", statut)
    
    st.markdown("---")
    
    # Étape 2 : Stock disponible PAR LOT
    st.markdown("### 2️⃣ Sélectionner le Lot")
    
    stock_par_lot = get_stock_par_lot()
    
    if stock_par_lot.empty:
        st.warning("⚠️ Aucun stock disponible")
    else:
        # Filtres améliorés
        col1, col2, col3 = st.columns(3)
        with col1:
            varietes = ["Toutes"] + sorted(stock_par_lot['variete'].dropna().unique().tolist())
            filtre_variete = st.selectbox("Variété", varietes, key="filtre_var_stock")
        with col2:
            sites = ["Tous"] + sorted(stock_par_lot['site_principal'].dropna().unique().tolist())
            filtre_site = st.selectbox("Site", sites, key="filtre_site_stock")
        with col3:
            producteurs = ["Tous"] + sorted(stock_par_lot['producteur_nom'].dropna().unique().tolist())
            filtre_producteur = st.selectbox("Producteur", producteurs, key="filtre_prod_stock")
        
        # ⭐ NOUVEAU : Champ de recherche texte
        recherche_lot = st.text_input(
            "🔍 Rechercher un lot (code, nom, producteur...)",
            placeholder="Ex: AGATA, BOSSELER, COLLOT...",
            key="recherche_lot"
        )
        
        # Appliquer filtres
        stock_filtre = stock_par_lot.copy()
        if filtre_variete != "Toutes":
            stock_filtre = stock_filtre[stock_filtre['variete'] == filtre_variete]
        if filtre_site != "Tous":
            stock_filtre = stock_filtre[stock_filtre['site_principal'] == filtre_site]
        if filtre_producteur != "Tous":
            stock_filtre = stock_filtre[stock_filtre['producteur_nom'] == filtre_producteur]
        
        # Recherche texte
        if recherche_lot:
            recherche_lower = recherche_lot.lower()
            stock_filtre = stock_filtre[
                stock_filtre['code_lot_interne'].str.lower().str.contains(recherche_lower, na=False) |
                stock_filtre['nom_usage'].str.lower().str.contains(recherche_lower, na=False) |
                stock_filtre['producteur_nom'].str.lower().str.contains(recherche_lower, na=False) |
                stock_filtre['variete'].str.lower().str.contains(recherche_lower, na=False)
            ]
        
        if not stock_filtre.empty:
            st.caption(f"💡 {len(stock_filtre)} lot(s) disponible(s)")
            
            # Préparer tableau
            df_stock = stock_filtre.copy().reset_index(drop=True)
            df_stock['_idx'] = df_stock.index
            
            # Colonnes affichage - ⭐ AJOUT Nom Lot et Producteur
            df_stock['Code Lot'] = df_stock['code_lot_interne']
            df_stock['Nom Lot'] = df_stock['nom_usage']
            df_stock['Producteur'] = df_stock['producteur_nom']
            df_stock['Variété'] = df_stock['variete']
            df_stock['Site'] = df_stock['site_principal']
            df_stock['LAVÉ (T)'] = df_stock['stock_lave_tonnes'].round(2)
            df_stock['BRUT (T)'] = df_stock['stock_brut_tonnes'].round(2)
            df_stock['BRUT net* (T)'] = df_stock['stock_brut_net_tonnes'].round(2)
            df_stock['Total net (T)'] = df_stock['total_net_tonnes'].round(2)
            df_stock['Tare %'] = df_stock['tare_moyenne_pct'].round(1)
            
            column_config = {
                "_idx": None,
                "lot_id": None,
                "Code Lot": st.column_config.TextColumn("Code Lot", width="medium"),
                "Nom Lot": st.column_config.TextColumn("Nom Lot", width="large"),
                "Producteur": st.column_config.TextColumn("Producteur", width="medium"),
                "Variété": st.column_config.TextColumn("Variété", width="medium"),
                "Site": st.column_config.TextColumn("Site", width="small"),
                "LAVÉ (T)": st.column_config.NumberColumn("LAVÉ", format="%.1f"),
                "BRUT (T)": st.column_config.NumberColumn("BRUT", format="%.1f"),
                "BRUT net* (T)": st.column_config.NumberColumn("BRUT net*", format="%.1f"),
                "Total net (T)": st.column_config.NumberColumn("Total net", format="%.1f"),
                "Tare %": st.column_config.NumberColumn("Tare %", format="%.1f"),
            }
            
            # Tableau sélectionnable
            event = st.dataframe(
                df_stock[['_idx', 'lot_id', 'Code Lot', 'Nom Lot', 'Producteur', 'Variété', 'Site', 
                         'LAVÉ (T)', 'BRUT (T)', 'BRUT net* (T)', 'Total net (T)', 'Tare %']],
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
                st.success(f"✅ Lot : **{selected_lot['Code Lot']}** - {selected_lot['Nom Lot']} ({selected_lot['Producteur']})")
                
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
                            empl_lave = get_premier_emplacement_lot(selected_lot['lot_id'], 'LAVÉ')
                            if empl_lave:
                                success, msg = create_affectation(
                                    code_produit=selected_code_produit,
                                    lot_id=selected_lot['lot_id'],
                                    emplacement_id=empl_lave['emplacement_id'],
                                    statut_stock='LAVÉ',
                                    quantite_tonnes=affecte_lave,
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
                            empl_brut = get_premier_emplacement_lot(selected_lot['lot_id'], 'BRUT')
                            if empl_brut:
                                success, msg = create_affectation(
                                    code_produit=selected_code_produit,
                                    lot_id=selected_lot['lot_id'],
                                    emplacement_id=empl_brut['emplacement_id'],
                                    statut_stock='BRUT',
                                    quantite_tonnes=affecte_brut_brut,
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
                                st.warning(f"⚠️ {besoin_lavage:.1f} T de BRUT à laver !")
                            
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
    
    affectations = get_affectations_par_produit()
    
    if affectations.empty:
        st.info("📭 Aucune affectation")
    else:
        # Filtres
        col1, col2 = st.columns(2)
        
        with col1:
            produits_aff = affectations.apply(
                lambda r: f"{r['marque']} - {r['libelle']}", axis=1
            ).unique().tolist()
            filtre_produit_aff = st.selectbox("Produit", ["Tous"] + produits_aff, key="filtre_prod_aff")
        
        with col2:
            types_aff = affectations['statut_stock'].unique().tolist()
            filtre_type_aff = st.selectbox("Type stock", ["Tous"] + types_aff, key="filtre_type_aff")
        
        df_aff = affectations.copy()
        if filtre_produit_aff != "Tous":
            df_aff['produit_label'] = df_aff.apply(lambda r: f"{r['marque']} - {r['libelle']}", axis=1)
            df_aff = df_aff[df_aff['produit_label'] == filtre_produit_aff]
        if filtre_type_aff != "Tous":
            df_aff = df_aff[df_aff['statut_stock'] == filtre_type_aff]
        
        st.caption(f"💡 {len(df_aff)} affectation(s)")
        
        # Affichage
        for _, row in df_aff.iterrows():
            with st.expander(f"#{row['id']} - {row['marque']} {row['libelle']} - {row['code_lot_interne']}"):
                col1, col2 = st.columns(2)
                
                with col1:
                    st.write(f"**Produit** : {row['marque']} - {row['libelle']}")
                    st.write(f"**Lot** : {row['code_lot_interne']}")
                    st.write(f"**Nom** : {row['nom_usage']}")
                    st.write(f"**Producteur** : {row['code_producteur']}")
                    st.write(f"**Variété** : {row['variete']}")
                
                with col2:
                    st.write(f"**Type** : {row['statut_stock']}")
                    st.write(f"**Quantité** : {row['quantite_affectee_tonnes']:.2f} T")
                    if row['statut_stock'] == 'BRUT':
                        st.write(f"**Net estimé** : {row['poids_net_estime_tonnes']:.2f} T")
                        tare = row['tare_utilisee_pct']
                        st.write(f"**Tare** : {tare:.1f}% ({row['tare_source']})" if tare else "N/A")
                    st.write(f"**Créé par** : {row['created_by']}")
                    st.write(f"**Date** : {row['created_at']}")
                
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
