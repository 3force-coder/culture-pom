import streamlit as st
import pandas as pd
from datetime import datetime, date, timedelta
from database import get_connection
from components import show_footer
from auth import is_authenticated

st.set_page_config(page_title="Affectations Prévisions - Culture Pom", page_icon="📋", layout="wide")

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
        background-color: #f0f7ff;
        padding: 1rem;
        border-radius: 0.5rem;
        margin: 0.5rem 0;
        border-left: 4px solid #1976d2;
    }
    .surplus {
        background-color: #e8f5e9;
        color: #2e7d32;
        padding: 0.5rem;
        border-radius: 0.3rem;
    }
    .manque {
        background-color: #ffebee;
        color: #c62828;
        padding: 0.5rem;
        border-radius: 0.3rem;
    }
    .equilibre {
        background-color: #fff3e0;
        color: #ef6c00;
        padding: 0.5rem;
        border-radius: 0.3rem;
    }
</style>
""", unsafe_allow_html=True)

if not is_authenticated():
    st.warning("⚠️ Veuillez vous connecter pour accéder à cette page")
    st.stop()

# Date fin campagne
DATE_FIN_CAMPAGNE = date(2026, 6, 30)

# ============================================================
# FONCTIONS DONNÉES
# ============================================================

def get_lots_disponibles(varietes_filter=None, producteurs_filter=None, only_with_stock=True):
    """Récupère les lots disponibles pour affectation avec détail affectations existantes"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        query = """
            SELECT 
                l.id as lot_id,
                l.code_lot_interne,
                l.nom_usage,
                l.code_variete,
                COALESCE(v.nom_variete, l.code_variete) as nom_variete,
                l.code_producteur,
                COALESCE(p.nom, l.code_producteur) as nom_producteur,
                l.poids_total_brut_kg / 1000 as poids_brut_tonnes,
                l.prix_achat_euro_tonne,
                l.date_entree_stock,
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
                COALESCE((
                    SELECT SUM(pa.quantite_affectee_tonnes)
                    FROM previsions_affectations pa
                    WHERE pa.lot_id = l.id AND pa.is_active = TRUE
                ), 0) as poids_affecte_tonnes,
                COALESCE((
                    SELECT COUNT(*)
                    FROM previsions_affectations pa
                    WHERE pa.lot_id = l.id AND pa.is_active = TRUE
                      AND COALESCE(pa.type_affectation, 'CT') = 'CT'
                ), 0) as nb_affectations_ct,
                COALESCE((
                    SELECT COUNT(*)
                    FROM previsions_affectations pa
                    WHERE pa.lot_id = l.id AND pa.is_active = TRUE
                      AND pa.type_affectation = 'LT'
                ), 0) as nb_affectations_lt
            FROM lots_bruts l
            LEFT JOIN ref_varietes v ON l.code_variete = v.code_variete
            LEFT JOIN ref_producteurs p ON l.code_producteur = p.code_producteur
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
            numeric_cols = ['poids_brut_tonnes', 'prix_achat_euro_tonne', 'tare_pct', 
                           'poids_affecte_tonnes', 'nb_affectations_ct', 'nb_affectations_lt']
            for col in numeric_cols:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
            
            df['poids_disponible_tonnes'] = df['poids_brut_tonnes'] - df['poids_affecte_tonnes']
            df['poids_net_estime_tonnes'] = df['poids_disponible_tonnes'] * (1 - df['tare_pct'] / 100)
            
            # Indicateur affectations
            def affectation_status(row):
                ct = int(row['nb_affectations_ct'])
                lt = int(row['nb_affectations_lt'])
                if ct == 0 and lt == 0:
                    return ''
                parts = []
                if ct > 0:
                    parts.append(f"🔵{ct}")
                if lt > 0:
                    parts.append(f"🟣{lt}")
                return ' '.join(parts)
            
            df['affectations'] = df.apply(affectation_status, axis=1)
            
            if varietes_filter and len(varietes_filter) > 0:
                df = df[df['nom_variete'].isin(varietes_filter)]
            
            if producteurs_filter and len(producteurs_filter) > 0:
                df = df[df['nom_producteur'].isin(producteurs_filter)]
            
            if only_with_stock:
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

def get_producteurs_disponibles():
    """Récupère les producteurs des lots en stock"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT DISTINCT p.nom
            FROM lots_bruts l
            JOIN ref_producteurs p ON l.code_producteur = p.code_producteur
            WHERE l.is_active = TRUE AND l.poids_total_brut_kg > 0
            ORDER BY p.nom
        """)
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        return [row['nom'] for row in rows] if rows else []
    except:
        return []

def get_produits_commerciaux():
    """Récupère tous les produits commerciaux actifs"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                code_produit,
                marque,
                libelle,
                type_produit,
                atelier,
                prix_vente_tonne
            FROM ref_produits_commerciaux
            WHERE is_active = TRUE
            ORDER BY marque, libelle
        """)
        
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        
        if rows:
            df = pd.DataFrame(rows)
            df['display_name'] = df['marque'] + ' - ' + df['libelle'] + ' (' + df['type_produit'].fillna('') + ')'
            return df
        return pd.DataFrame()
        
    except Exception as e:
        st.error(f"Erreur produits: {str(e)}")
        return pd.DataFrame()

def get_conso_moyenne_produit(code_produit):
    """Récupère la consommation moyenne hebdomadaire d'un produit (5 prochaines semaines)"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        today = date.today()
        semaine_courante = today.isocalendar()[1]
        annee_courante = today.year
        
        cursor.execute("""
            WITH semaines_5_prochaines AS (
                SELECT 
                    quantite_prevue_tonnes,
                    ROW_NUMBER() OVER (ORDER BY annee, semaine) as rn
                FROM previsions_ventes
                WHERE code_produit_commercial = %s
                  AND ((annee = %s AND semaine >= %s) OR annee > %s)
            )
            SELECT AVG(quantite_prevue_tonnes) as conso_moyenne
            FROM semaines_5_prochaines
            WHERE rn <= 5
        """, (code_produit, annee_courante, semaine_courante, annee_courante))
        
        result = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if result and result['conso_moyenne']:
            return float(result['conso_moyenne'])
        return 0
        
    except:
        return 0

def get_besoin_total_produit(code_produit):
    """Calcule le besoin total d'un produit jusqu'à fin de campagne
    
    Formule: Besoin = Conso moyenne hebdo × Nombre de semaines restantes jusqu'au 30/06/2026
    """
    try:
        # 1. Calculer le nombre de semaines entre aujourd'hui et fin campagne
        today = date.today()
        nb_semaines = (DATE_FIN_CAMPAGNE - today).days / 7.0
        
        if nb_semaines <= 0:
            return 0.0
        
        # 2. Récupérer la consommation moyenne hebdomadaire
        conso_hebdo = get_conso_moyenne_produit(code_produit)
        
        # 3. Besoin = moyenne × nombre de semaines
        besoin = conso_hebdo * nb_semaines
        
        return float(besoin)
        
    except:
        return 0.0

def get_stock_affecte_produit(code_produit):
    """Récupère le stock net affecté pour un produit"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT COALESCE(SUM(poids_net_estime_tonnes), 0) as stock_net
            FROM previsions_affectations
            WHERE code_produit_commercial = %s AND is_active = TRUE
        """, (code_produit,))
        
        result = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if result and result['stock_net'] is not None:
            return float(result['stock_net'])
        return 0.0
        
    except:
        return 0.0

def calc_date_fin_lot(stock_tonnes, conso_hebdo, date_debut=None):
    """Calcule la date de fin d'un lot basée sur la consommation"""
    # Convertir en float pour éviter erreurs Decimal
    stock_tonnes = float(stock_tonnes) if stock_tonnes else 0
    conso_hebdo = float(conso_hebdo) if conso_hebdo else 0
    
    if not conso_hebdo or conso_hebdo <= 0:
        return None
    
    if date_debut is None:
        date_debut = date.today()
    
    jours_stock = (stock_tonnes / conso_hebdo) * 7
    return date_debut + timedelta(days=int(jours_stock))

def get_solde_produit(code_produit):
    """Calcule le solde (surplus/manque) d'un produit"""
    besoin = float(get_besoin_total_produit(code_produit) or 0)
    stock = float(get_stock_affecte_produit(code_produit) or 0)
    solde = stock - besoin
    
    if solde > 0:
        statut = 'SURPLUS'
    elif solde < 0:
        statut = 'MANQUE'
    else:
        statut = 'EQUILIBRE'
    
    return {
        'besoin_total': besoin,
        'stock_affecte': stock,
        'solde': solde,
        'statut': statut
    }

def create_affectation(code_produit, lot_id, quantite_tonnes, tare_pct, tare_source):
    """Crée une nouvelle affectation avec calcul de date fin"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Récupérer l'emplacement_id principal du lot (celui avec le plus de stock)
        cursor.execute("""
            SELECT id as emplacement_id, statut_lavage
            FROM stock_emplacements
            WHERE lot_id = %s AND is_active = TRUE
            ORDER BY poids_total_kg DESC
            LIMIT 1
        """, (int(lot_id),))
        empl_result = cursor.fetchone()
        
        if empl_result:
            emplacement_id = empl_result['emplacement_id']
            statut_stock = empl_result['statut_lavage'] or 'BRUT'
        else:
            # Si pas d'emplacement trouvé, on utilise NULL (le schéma doit le permettre)
            emplacement_id = None
            statut_stock = 'BRUT'
        
        # Calcul poids net
        poids_net = float(quantite_tonnes) * (1 - float(tare_pct) / 100)
        
        # Calcul date fin estimée basée sur conso
        conso_hebdo = get_conso_moyenne_produit(code_produit)
        
        # Trouver la dernière date fin des affectations existantes pour ce produit
        cursor.execute("""
            SELECT MAX(date_fin_estimee) as derniere_date
            FROM previsions_affectations
            WHERE code_produit_commercial = %s AND is_active = TRUE
        """, (code_produit,))
        result = cursor.fetchone()
        
        if result and result['derniere_date']:
            date_debut = result['derniere_date']
        else:
            date_debut = date.today()
        
        date_fin = calc_date_fin_lot(poids_net, conso_hebdo, date_debut)
        
        # Semaine/année courante
        today = date.today()
        semaine = today.isocalendar()[1]
        annee = today.year
        
        created_by = st.session_state.get('username', 'system')
        
        cursor.execute("""
            INSERT INTO previsions_affectations (
                code_produit_commercial, annee, semaine, lot_id, emplacement_id,
                statut_stock, quantite_affectee_tonnes, poids_net_estime_tonnes,
                tare_utilisee_pct, tare_source, type_affectation,
                date_debut_estimee, date_fin_estimee,
                is_active, created_by
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'LT', %s, %s, TRUE, %s)
            RETURNING id
        """, (
            code_produit, annee, semaine, int(lot_id), emplacement_id,
            statut_stock, float(quantite_tonnes), poids_net, float(tare_pct), tare_source,
            date_debut, date_fin, created_by
        ))
        
        result = cursor.fetchone()
        conn.commit()
        cursor.close()
        conn.close()
        
        return True, result['id']
        
    except Exception as e:
        if 'conn' in locals():
            conn.rollback()
        return False, str(e)

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
        return True
    except:
        return False

def get_affectations_existantes():
    """Récupère TOUTES les affectations actives (CT et LT)"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                pa.id,
                pa.code_produit_commercial,
                pc.marque,
                pc.libelle as produit_libelle,
                pc.type_produit,
                pc.atelier,
                pa.lot_id,
                l.code_lot_interne,
                l.nom_usage,
                l.code_variete,
                COALESCE(v.nom_variete, l.code_variete) as nom_variete,
                l.code_producteur,
                COALESCE(p.nom, l.code_producteur) as nom_producteur,
                pa.quantite_affectee_tonnes,
                pa.poids_net_estime_tonnes,
                pa.tare_utilisee_pct,
                pa.tare_source,
                pa.date_debut_estimee,
                pa.date_fin_estimee,
                COALESCE(pa.type_affectation, 'CT') as type_affectation,
                pa.annee,
                pa.semaine,
                pa.created_by,
                pa.created_at
            FROM previsions_affectations pa
            JOIN ref_produits_commerciaux pc ON pa.code_produit_commercial = pc.code_produit
            JOIN lots_bruts l ON pa.lot_id = l.id
            LEFT JOIN ref_varietes v ON l.code_variete = v.code_variete
            LEFT JOIN ref_producteurs p ON l.code_producteur = p.code_producteur
            WHERE pa.is_active = TRUE
            ORDER BY pa.type_affectation DESC, pc.marque, pc.libelle, pa.date_debut_estimee
        """)
        
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        
        if rows:
            df = pd.DataFrame(rows)
            numeric_cols = ['quantite_affectee_tonnes', 'poids_net_estime_tonnes', 'tare_utilisee_pct']
            for col in numeric_cols:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
            return df
        return pd.DataFrame()
        
    except Exception as e:
        st.error(f"Erreur affectations: {str(e)}")
        return pd.DataFrame()

def get_resume_par_produit():
    """Calcule le résumé par produit avec solde et dates"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Tous les produits avec prévisions
        cursor.execute("""
            WITH produits_avec_prev AS (
                SELECT DISTINCT pv.code_produit_commercial
                FROM previsions_ventes pv
            ),
            affectations_agg AS (
                SELECT 
                    pa.code_produit_commercial,
                    SUM(pa.quantite_affectee_tonnes) as total_brut,
                    SUM(pa.poids_net_estime_tonnes) as total_net,
                    COUNT(*) as nb_lots,
                    MAX(pa.date_fin_estimee) as date_fin_derniere
                FROM previsions_affectations pa
                WHERE pa.is_active = TRUE
                GROUP BY pa.code_produit_commercial
            )
            SELECT 
                pc.code_produit,
                pc.marque,
                pc.libelle,
                pc.type_produit,
                pc.atelier,
                COALESCE(a.total_brut, 0) as total_brut,
                COALESCE(a.total_net, 0) as total_net,
                COALESCE(a.nb_lots, 0) as nb_lots,
                a.date_fin_derniere
            FROM ref_produits_commerciaux pc
            JOIN produits_avec_prev pap ON pc.code_produit = pap.code_produit_commercial
            LEFT JOIN affectations_agg a ON pc.code_produit = a.code_produit_commercial
            WHERE pc.is_active = TRUE
            ORDER BY pc.marque, pc.libelle
        """)
        
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        
        if rows:
            df = pd.DataFrame(rows)
            
            # Convertir colonnes numériques Decimal -> float
            numeric_cols = ['total_brut', 'total_net', 'nb_lots']
            for col in numeric_cols:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
            
            # Ajouter conso hebdo, besoin total et solde
            result_data = []
            for _, row in df.iterrows():
                code_produit = row['code_produit']
                conso_hebdo = float(get_conso_moyenne_produit(code_produit) or 0)
                besoin_total = float(get_besoin_total_produit(code_produit) or 0)
                solde_info = get_solde_produit(code_produit)
                
                # Semaines couvertes (float conversion)
                total_net = float(row['total_net']) if pd.notna(row['total_net']) else 0.0
                semaines_couvertes = total_net / conso_hebdo if conso_hebdo > 0 else 0.0
                
                result_data.append({
                    'code_produit': code_produit,
                    'marque': row['marque'],
                    'libelle': row['libelle'],
                    'type_produit': row['type_produit'],
                    'atelier': row['atelier'],
                    'nb_lots': int(row['nb_lots']) if row['nb_lots'] else 0,
                    'total_brut': float(row['total_brut']) if row['total_brut'] else 0,
                    'total_net': total_net,
                    'conso_hebdo': float(conso_hebdo) if conso_hebdo else 0,
                    'semaines_couvertes': float(semaines_couvertes),
                    'besoin_campagne': float(besoin_total) if besoin_total else 0,
                    'solde': float(solde_info['solde']) if solde_info['solde'] else 0,
                    'statut': solde_info['statut'],
                    'date_fin_derniere': row['date_fin_derniere']
                })
            
            return pd.DataFrame(result_data)
        return pd.DataFrame()
        
    except Exception as e:
        st.error(f"Erreur résumé: {str(e)}")
        return pd.DataFrame()

# ============================================================
# INTERFACE
# ============================================================

st.title("📋 Affectations Prévisions (Long Terme)")
st.caption(f"Affectation des lots aux produits commerciaux • Fin campagne: {DATE_FIN_CAMPAGNE.strftime('%d/%m/%Y')}")
st.markdown("---")

# Initialiser session state
if 'affectations_config' not in st.session_state:
    st.session_state.affectations_config = {}

tab1, tab2, tab3 = st.tabs(["➕ Nouvelle Affectation", "📊 Affectations Existantes", "📈 Résumé & Soldes"])

# ============================================================
# TAB 1: NOUVELLE AFFECTATION
# ============================================================

with tab1:
    # Section 1: Résumé soldes en temps réel (important pour décider)
    st.subheader("📊 Soldes par Produit (temps réel)")
    
    resume_df = get_resume_par_produit()
    
    if not resume_df.empty:
        # KPIs rapides
        cols_solde = st.columns(4)
        
        nb_manque = len(resume_df[resume_df['statut'] == 'MANQUE'])
        nb_surplus = len(resume_df[resume_df['statut'] == 'SURPLUS'])
        nb_equilibre = len(resume_df[resume_df['statut'] == 'EQUILIBRE'])
        total_solde = resume_df['solde'].sum()
        
        with cols_solde[0]:
            st.metric("🔴 Manque", nb_manque, help="Produits avec stock insuffisant")
        with cols_solde[1]:
            st.metric("🟢 Surplus", nb_surplus, help="Produits avec surplus")
        with cols_solde[2]:
            st.metric("🟡 Équilibré", nb_equilibre)
        with cols_solde[3]:
            delta_color = "normal" if total_solde >= 0 else "inverse"
            st.metric("📊 Solde Global", f"{total_solde:.1f} T", 
                     delta="surplus" if total_solde > 0 else "manque" if total_solde < 0 else "équilibré")
        
        # Tableau soldes condensé (produits en manque prioritaires)
        with st.expander("🔍 Détail soldes par produit", expanded=False):
            df_soldes = resume_df[['marque', 'libelle', 'atelier', 'total_net', 'besoin_campagne', 'solde', 'statut']].copy()
            df_soldes = df_soldes.sort_values('solde')
            
            st.dataframe(
                df_soldes,
                column_config={
                    'marque': 'Marque',
                    'libelle': 'Produit',
                    'atelier': 'Atelier',
                    'total_net': st.column_config.NumberColumn('Affecté Net (T)', format="%.1f"),
                    'besoin_campagne': st.column_config.NumberColumn('Besoin (T)', format="%.1f"),
                    'solde': st.column_config.NumberColumn('Solde (T)', format="%.1f"),
                    'statut': 'Statut'
                },
                use_container_width=True,
                hide_index=True
            )
    
    st.markdown("---")
    
    # Section 2: Sélection lots
    st.subheader("1️⃣ Sélectionner les lots à affecter")
    
    # Filtres
    col_f1, col_f2, col_f3 = st.columns([2, 2, 1])
    
    with col_f1:
        varietes = get_varietes_disponibles()
        filter_varietes = st.multiselect("🌱 Variétés", varietes, key="filter_varietes")
    
    with col_f2:
        producteurs = get_producteurs_disponibles()
        filter_producteurs = st.multiselect("👨‍🌾 Producteurs", producteurs, key="filter_producteurs")
    
    with col_f3:
        only_stock = st.checkbox("Stock > 0", value=True, key="only_stock")
    
    # Charger lots
    lots_df = get_lots_disponibles(
        varietes_filter=filter_varietes if filter_varietes else None,
        producteurs_filter=filter_producteurs if filter_producteurs else None,
        only_with_stock=only_stock
    )
    
    if not lots_df.empty:
        st.caption(f"📦 {len(lots_df)} lot(s) disponible(s) • 🔵=CT 🟣=LT")
        
        # Préparer affichage avec colonne affectations
        display_cols = [
            'lot_id', 'code_lot_interne', 'nom_usage', 'nom_producteur', 'nom_variete',
            'poids_brut_tonnes', 'poids_disponible_tonnes', 'poids_net_estime_tonnes',
            'tare_pct', 'prix_achat_euro_tonne', 'date_entree_stock', 'affectations'
        ]
        # Garder seulement les colonnes existantes
        display_cols = [c for c in display_cols if c in lots_df.columns]
        df_display = lots_df[display_cols].copy()
        
        df_display = df_display.reset_index(drop=True)
        
        column_config = {
            'lot_id': None,
            'code_lot_interne': st.column_config.TextColumn('Code Lot', width='medium'),
            'nom_usage': st.column_config.TextColumn('Nom Lot', width='medium'),
            'nom_producteur': st.column_config.TextColumn('Producteur', width='medium'),
            'nom_variete': st.column_config.TextColumn('Variété', width='small'),
            'poids_brut_tonnes': st.column_config.NumberColumn('Brut (T)', format="%.1f"),
            'poids_disponible_tonnes': st.column_config.NumberColumn('Dispo (T)', format="%.1f"),
            'poids_net_estime_tonnes': st.column_config.NumberColumn('Net Est. (T)', format="%.1f"),
            'tare_pct': st.column_config.NumberColumn('Tare %', format="%.1f%%"),
            'prix_achat_euro_tonne': st.column_config.NumberColumn('Prix €/T', format="%.0f"),
            'date_entree_stock': st.column_config.DateColumn('Entrée', format="DD/MM/YY"),
            'affectations': st.column_config.TextColumn('Affecté', width='small', help="🔵=CT, 🟣=LT")
        }
        
        event = st.dataframe(
            df_display,
            column_config=column_config,
            use_container_width=True,
            hide_index=True,
            on_select="rerun",
            selection_mode="multi-row",
            key="lots_table"
        )
        
        selected_rows = event.selection.rows if hasattr(event, 'selection') else []
        
        if len(selected_rows) > 0:
            st.markdown("---")
            st.subheader(f"2️⃣ Configurer les {len(selected_rows)} lot(s) sélectionné(s)")
            
            # Charger produits
            produits_df = get_produits_commerciaux()
            
            if produits_df.empty:
                st.error("❌ Aucun produit commercial actif")
            else:
                # Configuration par lot
                for row_idx in selected_rows:
                    lot = lots_df.iloc[row_idx]
                    lot_id = int(lot['lot_id'])
                    
                    with st.container():
                        st.markdown(f"""
                        <div class="lot-card">
                            <strong>{lot['code_lot_interne']}</strong> - {lot['nom_usage'] or ''}<br>
                            🌱 {lot['nom_variete']} | 👨‍🌾 {lot['nom_producteur'] or 'N/A'} | 
                            📦 Dispo: <strong>{lot['poids_disponible_tonnes']:.1f} T</strong>
                        </div>
                        """, unsafe_allow_html=True)
                        
                        col1, col2, col3 = st.columns([3, 2, 2])
                        
                        with col1:
                            # Dropdown produit
                            produit_options = produits_df['display_name'].tolist()
                            
                            # Récupérer config existante ou défaut
                            current_config = st.session_state.affectations_config.get(lot_id, {})
                            default_idx = current_config.get('produit_idx', 0)
                            
                            selected_produit_idx = st.selectbox(
                                "📦 Produit destination *",
                                range(len(produit_options)),
                                format_func=lambda x: produit_options[x],
                                index=default_idx,
                                key=f"produit_{lot_id}"
                            )
                        
                        with col2:
                            # Quantité (défaut = tout disponible)
                            default_qty = current_config.get('quantite', float(lot['poids_disponible_tonnes']))
                            quantite = st.number_input(
                                "⚖️ Quantité brute (T)",
                                min_value=0.1,
                                max_value=float(lot['poids_disponible_tonnes']),
                                value=min(default_qty, float(lot['poids_disponible_tonnes'])),
                                step=0.1,
                                key=f"qty_{lot_id}"
                            )
                        
                        with col3:
                            # Afficher impact sur solde EN TEMPS RÉEL
                            selected_produit = produits_df.iloc[selected_produit_idx]
                            code_produit = selected_produit['code_produit']
                            tare = float(lot['tare_pct']) if pd.notna(lot['tare_pct']) else 22.0
                            poids_net = float(quantite) * (1 - tare / 100)
                            
                            # Solde actuel + impact
                            solde_actuel = get_solde_produit(code_produit)
                            nouveau_solde = float(solde_actuel['solde']) + poids_net
                            
                            st.metric(
                                "📊 Solde après",
                                f"{nouveau_solde:.1f} T",
                                delta=f"+{poids_net:.1f} T net",
                                delta_color="normal"
                            )
                            
                            # Date fin estimée
                            conso = get_conso_moyenne_produit(code_produit)
                            if conso > 0:
                                date_fin = calc_date_fin_lot(poids_net, conso)
                                if date_fin:
                                    st.caption(f"📅 Fin estimée: {date_fin.strftime('%d/%m/%Y')}")
                        
                        # Sauvegarder config
                        st.session_state.affectations_config[lot_id] = {
                            'produit_idx': selected_produit_idx,
                            'quantite': quantite
                        }
                
                # Récapitulatif et validation
                st.markdown("---")
                st.subheader("3️⃣ Récapitulatif et Validation")
                
                # Tableau récap
                recap_data = []
                for row_idx in selected_rows:
                    lot = lots_df.iloc[row_idx]
                    lot_id = int(lot['lot_id'])
                    config = st.session_state.affectations_config.get(lot_id, {})
                    
                    produit_idx = config.get('produit_idx', 0)
                    produit = produits_df.iloc[produit_idx]
                    quantite = config.get('quantite', float(lot['poids_disponible_tonnes']))
                    poids_net = quantite * (1 - float(lot['tare_pct']) / 100)
                    
                    recap_data.append({
                        'Lot': lot['code_lot_interne'],
                        'Variété': lot['nom_variete'],
                        'Produit': produit['display_name'],
                        'Brut (T)': quantite,
                        'Net Est. (T)': poids_net,
                        'Tare %': lot['tare_pct']
                    })
                
                df_recap = pd.DataFrame(recap_data)
                
                st.dataframe(
                    df_recap,
                    column_config={
                        'Brut (T)': st.column_config.NumberColumn(format="%.1f"),
                        'Net Est. (T)': st.column_config.NumberColumn(format="%.1f"),
                        'Tare %': st.column_config.NumberColumn(format="%.1f%%")
                    },
                    use_container_width=True,
                    hide_index=True
                )
                
                # Totaux
                total_brut = df_recap['Brut (T)'].sum()
                total_net = df_recap['Net Est. (T)'].sum()
                
                col_tot1, col_tot2, col_tot3 = st.columns(3)
                with col_tot1:
                    st.metric("📦 Total Brut", f"{total_brut:.1f} T")
                with col_tot2:
                    st.metric("✨ Total Net Estimé", f"{total_net:.1f} T")
                with col_tot3:
                    st.metric("📋 Nb Affectations", len(selected_rows))
                
                # Boutons validation
                col_btn1, col_btn2 = st.columns(2)
                
                with col_btn1:
                    if st.button("✅ Créer les affectations", type="primary", use_container_width=True):
                        success_count = 0
                        errors = []
                        
                        for row_idx in selected_rows:
                            lot = lots_df.iloc[row_idx]
                            lot_id = int(lot['lot_id'])
                            config = st.session_state.affectations_config.get(lot_id, {})
                            
                            produit_idx = config.get('produit_idx', 0)
                            code_produit = produits_df.iloc[produit_idx]['code_produit']
                            quantite = config.get('quantite', float(lot['poids_disponible_tonnes']))
                            tare = float(lot['tare_pct'])
                            tare_source = lot['tare_source']
                            
                            success, result = create_affectation(
                                code_produit, lot_id, quantite, tare, tare_source
                            )
                            
                            if success:
                                success_count += 1
                            else:
                                errors.append(f"Lot {lot['code_lot_interne']}: {result}")
                        
                        if success_count > 0:
                            st.success(f"✅ {success_count} affectation(s) créée(s) !")
                            st.balloons()
                            st.session_state.affectations_config = {}
                            st.rerun()
                        
                        for err in errors:
                            st.error(err)
                
                with col_btn2:
                    if st.button("🔄 Réinitialiser", use_container_width=True):
                        st.session_state.affectations_config = {}
                        st.rerun()
        else:
            st.info("👆 Sélectionnez un ou plusieurs lots dans le tableau")
    else:
        st.warning("Aucun lot disponible")

# ============================================================
# TAB 2: AFFECTATIONS EXISTANTES
# ============================================================

with tab2:
    st.subheader("📊 Affectations existantes")
    
    affectations_df = get_affectations_existantes()
    
    if not affectations_df.empty:
        # KPIs CT vs LT
        col_kpi1, col_kpi2, col_kpi3, col_kpi4 = st.columns(4)
        
        nb_ct = len(affectations_df[affectations_df['type_affectation'] == 'CT'])
        nb_lt = len(affectations_df[affectations_df['type_affectation'] == 'LT'])
        total_net_ct = affectations_df[affectations_df['type_affectation'] == 'CT']['poids_net_estime_tonnes'].sum()
        total_net_lt = affectations_df[affectations_df['type_affectation'] == 'LT']['poids_net_estime_tonnes'].sum()
        
        with col_kpi1:
            st.metric("🔵 Court Terme", nb_ct, help="Affectations semaines S+1 à S+3")
        with col_kpi2:
            st.metric("🟣 Long Terme", nb_lt, help="Affectations campagne")
        with col_kpi3:
            st.metric("📦 Net CT", f"{total_net_ct:.1f} T")
        with col_kpi4:
            st.metric("📦 Net LT", f"{total_net_lt:.1f} T")
        
        st.markdown("---")
        
        # Filtres
        col_f0, col_f1, col_f2, col_f3 = st.columns(4)
        
        with col_f0:
            types = ["Tous", "🔵 CT", "🟣 LT"]
            filter_type = st.selectbox("Type", types, key="filter_type_exist")
        
        with col_f1:
            marques = ["Toutes"] + sorted(affectations_df['marque'].dropna().unique().tolist())
            filter_marque = st.selectbox("Marque", marques, key="filter_marque_exist")
        
        with col_f2:
            produits = ["Tous"] + sorted(affectations_df['produit_libelle'].dropna().unique().tolist())
            filter_produit = st.selectbox("Produit", produits, key="filter_produit_exist")
        
        with col_f3:
            ateliers = ["Tous"] + sorted([a for a in affectations_df['atelier'].dropna().unique().tolist() if a])
            filter_atelier = st.selectbox("Atelier", ateliers, key="filter_atelier_exist")
        
        # Appliquer filtres
        df_filtered = affectations_df.copy()
        if filter_type == "🔵 CT":
            df_filtered = df_filtered[df_filtered['type_affectation'] == 'CT']
        elif filter_type == "🟣 LT":
            df_filtered = df_filtered[df_filtered['type_affectation'] == 'LT']
        if filter_marque != "Toutes":
            df_filtered = df_filtered[df_filtered['marque'] == filter_marque]
        if filter_produit != "Tous":
            df_filtered = df_filtered[df_filtered['produit_libelle'] == filter_produit]
        if filter_atelier != "Tous":
            df_filtered = df_filtered[df_filtered['atelier'] == filter_atelier]
        
        if not df_filtered.empty:
            st.markdown(f"**{len(df_filtered)} affectation(s)**")
            
            # Ajouter colonne Type visuelle + Semaine pour CT
            df_display = df_filtered.copy()
            df_display['type_display'] = df_display['type_affectation'].apply(
                lambda x: '🔵 CT' if x == 'CT' else '🟣 LT'
            )
            df_display['semaine_display'] = df_display.apply(
                lambda r: f"S{r['semaine']:02d}/{r['annee']}" if r['type_affectation'] == 'CT' else '-',
                axis=1
            )
            
            # Colonnes à afficher
            display_cols = [
                'id', 'type_display', 'semaine_display', 'marque', 'produit_libelle', 'atelier',
                'code_lot_interne', 'nom_variete', 'nom_producteur',
                'quantite_affectee_tonnes', 'poids_net_estime_tonnes', 'tare_utilisee_pct',
                'date_fin_estimee', 'created_by'
            ]
            
            # Garder seulement les colonnes qui existent
            display_cols = [c for c in display_cols if c in df_display.columns]
            df_show = df_display[display_cols].copy()
            
            column_config = {
                'id': st.column_config.NumberColumn('ID', width='small'),
                'type_display': st.column_config.TextColumn('Type', width='small'),
                'semaine_display': st.column_config.TextColumn('Sem.', width='small'),
                'marque': st.column_config.TextColumn('Marque', width='small'),
                'produit_libelle': st.column_config.TextColumn('Produit', width='medium'),
                'atelier': st.column_config.TextColumn('Atelier', width='small'),
                'code_lot_interne': st.column_config.TextColumn('Code Lot', width='medium'),
                'nom_variete': st.column_config.TextColumn('Variété', width='small'),
                'nom_producteur': st.column_config.TextColumn('Producteur', width='medium'),
                'quantite_affectee_tonnes': st.column_config.NumberColumn('Brut (T)', format="%.1f"),
                'poids_net_estime_tonnes': st.column_config.NumberColumn('Net (T)', format="%.1f"),
                'tare_utilisee_pct': st.column_config.NumberColumn('Tare %', format="%.1f%%"),
                'date_fin_estimee': st.column_config.DateColumn('Fin Est.', format="DD/MM/YY"),
                'created_by': st.column_config.TextColumn('Créé par', width='small')
            }
            
            event = st.dataframe(
                df_show,
                column_config=column_config,
                use_container_width=True,
                hide_index=True,
                on_select="rerun",
                selection_mode="multi-row",
                key="affectations_exist_table"
            )
            
            selected_rows = event.selection.rows if hasattr(event, 'selection') else []
            
            if len(selected_rows) > 0:
                if st.button(f"🗑️ Supprimer {len(selected_rows)} affectation(s)", type="secondary"):
                    for idx in selected_rows:
                        affectation_id = int(df_filtered.iloc[idx]['id'])
                        delete_affectation(affectation_id)
                    st.success(f"✅ {len(selected_rows)} supprimée(s)")
                    st.rerun()
            
            # Export
            st.markdown("---")
            csv = df_filtered.to_csv(index=False).encode('utf-8')
            st.download_button(
                "📥 Exporter CSV",
                csv,
                f"affectations_{date.today().strftime('%Y%m%d')}.csv",
                "text/csv"
            )
        else:
            st.info("Aucune affectation correspondant aux filtres")
    else:
        st.info("Aucune affectation. Utilisez l'onglet 'Nouvelle Affectation'.")

# ============================================================
# TAB 3: RÉSUMÉ & SOLDES
# ============================================================

with tab3:
    st.subheader("📈 Résumé par Produit & Soldes jusqu'à fin campagne")
    st.caption(f"Fin de campagne: {DATE_FIN_CAMPAGNE.strftime('%d/%m/%Y')}")
    
    resume_df = get_resume_par_produit()
    
    if not resume_df.empty:
        # Filtres
        col_f1, col_f2 = st.columns(2)
        
        with col_f1:
            ateliers = ["Tous"] + sorted([a for a in resume_df['atelier'].dropna().unique().tolist() if a])
            filter_atelier_resume = st.selectbox("Filtrer par atelier", ateliers, key="filter_atelier_resume")
        
        with col_f2:
            statuts = ["Tous", "MANQUE", "SURPLUS", "EQUILIBRE"]
            filter_statut = st.selectbox("Filtrer par statut", statuts, key="filter_statut_resume")
        
        # Appliquer filtres
        df_resume = resume_df.copy()
        if filter_atelier_resume != "Tous":
            df_resume = df_resume[df_resume['atelier'] == filter_atelier_resume]
        if filter_statut != "Tous":
            df_resume = df_resume[df_resume['statut'] == filter_statut]
        
        if not df_resume.empty:
            # KPIs
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.metric("📦 Total Net Affecté", f"{df_resume['total_net'].sum():.1f} T")
            with col2:
                st.metric("📊 Besoin Campagne", f"{df_resume['besoin_campagne'].sum():.1f} T")
            with col3:
                solde_total = df_resume['solde'].sum()
                st.metric("📈 Solde Global", f"{solde_total:.1f} T", 
                         delta="surplus" if solde_total > 0 else "manque" if solde_total < 0 else "équilibré")
            with col4:
                st.metric("📋 Produits", len(df_resume))
            
            st.markdown("---")
            
            # Tableau détaillé
            df_display = df_resume[[
                'marque', 'libelle', 'atelier', 'nb_lots',
                'total_brut', 'total_net', 'conso_hebdo',
                'semaines_couvertes', 'besoin_campagne', 'solde', 'statut', 'date_fin_derniere'
            ]].copy()
            
            # Trier par solde (manques en premier)
            df_display = df_display.sort_values('solde')
            
            column_config = {
                'marque': st.column_config.TextColumn('Marque', width='small'),
                'libelle': st.column_config.TextColumn('Produit', width='medium'),
                'atelier': st.column_config.TextColumn('Atelier', width='small'),
                'nb_lots': st.column_config.NumberColumn('Lots', width='small'),
                'total_brut': st.column_config.NumberColumn('Brut (T)', format="%.1f"),
                'total_net': st.column_config.NumberColumn('Net (T)', format="%.1f"),
                'conso_hebdo': st.column_config.NumberColumn('Conso/Sem', format="%.1f"),
                'semaines_couvertes': st.column_config.NumberColumn('Sem. Couv.', format="%.1f"),
                'besoin_campagne': st.column_config.NumberColumn('Besoin (T)', format="%.1f"),
                'solde': st.column_config.NumberColumn('Solde (T)', format="%.1f"),
                'statut': st.column_config.TextColumn('Statut', width='small'),
                'date_fin_derniere': st.column_config.DateColumn('Fin Dernière', format="DD/MM/YY")
            }
            
            st.dataframe(
                df_display,
                column_config=column_config,
                use_container_width=True,
                hide_index=True
            )
            
            # Détail par produit (lots séquentiels)
            st.markdown("---")
            st.subheader("🔍 Détail séquentiel par produit")
            
            produit_selected = st.selectbox(
                "Sélectionner un produit",
                df_resume['libelle'].tolist(),
                key="detail_produit"
            )
            
            if produit_selected:
                # Récupérer les affectations du produit
                produit_info = df_resume[df_resume['libelle'] == produit_selected].iloc[0]
                code_produit = produit_info['code_produit']
                
                # Afficher infos produit
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("🏷️ Marque", produit_info['marque'])
                with col2:
                    st.metric("📦 Conso/Sem", f"{produit_info['conso_hebdo']:.1f} T")
                with col3:
                    st.metric("📊 Besoin Total", f"{produit_info['besoin_campagne']:.1f} T")
                with col4:
                    solde = produit_info['solde']
                    st.metric("📈 Solde", f"{solde:.1f} T", 
                             delta="surplus" if solde > 0 else "manque" if solde < 0 else "ok")
                
                st.markdown("---")
                
                # Affectations du produit
                affectations_df_local = get_affectations_existantes()
                if not affectations_df_local.empty:
                    aff_produit = affectations_df_local[affectations_df_local['code_produit_commercial'] == code_produit].copy()
                    
                    if not aff_produit.empty:
                        aff_produit = aff_produit.sort_values('date_debut_estimee')
                        
                        st.markdown("**📋 Séquence des lots affectés:** (🔵=CT 🟣=LT)")
                        
                        # Timeline des lots
                        for i, (_, aff) in enumerate(aff_produit.iterrows()):
                            date_debut = aff['date_debut_estimee']
                            date_fin = aff['date_fin_estimee']
                            type_aff = aff['type_affectation'] if 'type_affectation' in aff else 'CT'
                            type_icon = '🔵' if type_aff == 'CT' else '🟣'
                            
                            date_debut_str = date_debut.strftime('%d/%m/%y') if pd.notna(date_debut) else '?'
                            date_fin_str = date_fin.strftime('%d/%m/%y') if pd.notna(date_fin) else '?'
                            
                            col1, col2, col3 = st.columns([1, 3, 2])
                            
                            with col1:
                                st.markdown(f"**{type_icon} Lot {i+1}**")
                            
                            with col2:
                                st.markdown(f"""
                                🏷️ **{aff['code_lot_interne']}** - {aff['nom_usage'] or ''}  
                                🌱 {aff['nom_variete']} | 👨‍🌾 {aff['nom_producteur'] or 'N/A'}
                                """)
                            
                            with col3:
                                st.markdown(f"""
                                📦 **{aff['quantite_affectee_tonnes']:.1f}T** brut → **{aff['poids_net_estime_tonnes']:.1f}T** net  
                                📅 {date_debut_str} → **{date_fin_str}**
                                """)
                            
                            st.markdown("---")
                        
                        # Solde final
                        solde = produit_info['solde']
                        if solde < 0:
                            st.error(f"❌ **MANQUE**: {abs(solde):.1f} T à affecter pour couvrir la campagne jusqu'au {DATE_FIN_CAMPAGNE.strftime('%d/%m/%Y')}")
                        elif solde > 0:
                            st.success(f"✅ **SURPLUS**: {solde:.1f} T au-delà du besoin campagne")
                        else:
                            st.warning(f"⚖️ **ÉQUILIBRÉ**: Stock = Besoin")
                    else:
                        st.info("Aucune affectation pour ce produit")
                else:
                    st.info("Aucune affectation enregistrée")
        else:
            st.info("Aucun produit correspondant aux filtres")
    else:
        st.info("Aucune donnée disponible")

show_footer()
