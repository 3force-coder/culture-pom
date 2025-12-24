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
    .lot-card-prevu {
        background-color: #fff8e1;
        padding: 1rem;
        border-radius: 0.5rem;
        margin: 0.5rem 0;
        border-left: 4px solid #ff9800;
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

# Date fin campagne dynamique
def get_date_fin_campagne():
    today = date.today()
    if today.month >= 7:
        return date(today.year + 1, 6, 30)
    else:
        return date(today.year, 6, 30)

DATE_FIN_CAMPAGNE = get_date_fin_campagne()

def clear_data_cache():
    """Invalide tous les caches de données après modification"""
    _get_all_lots_raw.clear()
    get_affectations_existantes.clear()
    get_resume_par_produit.clear()
    get_varietes_disponibles.clear()
    get_producteurs_disponibles.clear()
    get_produits_commerciaux.clear()

# ============================================================
# FONCTIONS DONNÉES - LOGIQUE HYBRIDE STOCK RÉEL + LOTS PRÉVUS
# ============================================================

@st.cache_data(ttl=30)
def _get_all_lots_raw():
    """
    Charge tous les lots avec logique HYBRIDE:
    - Si lot a du stock réel dans stock_emplacements → utiliser ce tonnage (📍 En stock)
    - Si lot n'a PAS de stock réel → utiliser tonnage de lots_bruts (📋 Prévu)
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        query = """
            WITH affectations_par_lot AS (
                SELECT 
                    lot_id,
                    SUM(quantite_affectee_tonnes) as poids_affecte,
                    COUNT(*) FILTER (WHERE COALESCE(type_affectation, 'CT') = 'CT') as nb_ct,
                    COUNT(*) FILTER (WHERE type_affectation = 'LT') as nb_lt
                FROM previsions_affectations
                WHERE is_active = TRUE
                GROUP BY lot_id
            ),
            stock_reel AS (
                -- Stock réel depuis stock_emplacements (ce qui est vraiment sur site)
                SELECT 
                    lot_id,
                    SUM(COALESCE(poids_total_kg, 0)) / 1000 as stock_reel_tonnes,
                    COUNT(*) as nb_emplacements
                FROM stock_emplacements
                WHERE is_active = TRUE
                GROUP BY lot_id
            )
            SELECT 
                l.id as lot_id,
                l.code_lot_interne,
                l.nom_usage,
                l.code_variete,
                COALESCE(v.nom_variete, l.code_variete) as nom_variete,
                l.code_producteur,
                COALESCE(p.nom, l.code_producteur) as nom_producteur,
                l.poids_total_brut_kg / 1000 as poids_brut_lot_tonnes,
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
                COALESCE(a.poids_affecte, 0) as poids_affecte_tonnes,
                COALESCE(a.nb_ct, 0) as nb_affectations_ct,
                COALESCE(a.nb_lt, 0) as nb_affectations_lt,
                -- Stock réel (peut être NULL si lot prévu non reçu)
                sr.stock_reel_tonnes,
                sr.nb_emplacements,
                -- Type de stock: REEL si dans stock_emplacements, PREVU sinon
                CASE 
                    WHEN sr.stock_reel_tonnes IS NOT NULL AND sr.stock_reel_tonnes > 0 
                    THEN 'REEL'
                    ELSE 'PREVU'
                END as type_stock,
                -- Poids brut effectif: stock réel si dispo, sinon lot prévu
                CASE 
                    WHEN sr.stock_reel_tonnes IS NOT NULL AND sr.stock_reel_tonnes > 0 
                    THEN sr.stock_reel_tonnes
                    ELSE l.poids_total_brut_kg / 1000
                END as poids_brut_effectif_tonnes
            FROM lots_bruts l
            LEFT JOIN ref_varietes v ON l.code_variete = v.code_variete
            LEFT JOIN ref_producteurs p ON l.code_producteur = p.code_producteur
            LEFT JOIN affectations_par_lot a ON l.id = a.lot_id
            LEFT JOIN stock_reel sr ON l.id = sr.lot_id
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
            numeric_cols = ['poids_brut_lot_tonnes', 'prix_achat_euro_tonne', 'tare_pct', 
                           'poids_affecte_tonnes', 'nb_affectations_ct', 'nb_affectations_lt',
                           'stock_reel_tonnes', 'poids_brut_effectif_tonnes']
            for col in numeric_cols:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
            
            # Calculer disponible et net basés sur poids effectif
            df['poids_disponible_tonnes'] = df['poids_brut_effectif_tonnes'] - df['poids_affecte_tonnes']
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
            
            # Indicateur type stock
            df['type_stock_icon'] = df['type_stock'].apply(
                lambda x: '📍' if x == 'REEL' else '📋'
            )
            
            return df
        return pd.DataFrame()
        
    except Exception as e:
        st.error(f"Erreur lots: {str(e)}")
        return pd.DataFrame()


def get_lots_disponibles(varietes_filter=None, producteurs_filter=None, only_with_stock=True, include_prevu=True):
    """Récupère les lots disponibles avec filtres"""
    df = _get_all_lots_raw()
    
    if df.empty:
        return df
    
    # Appliquer filtres
    if varietes_filter and len(varietes_filter) > 0:
        df = df[df['nom_variete'].isin(varietes_filter)]
    
    if producteurs_filter and len(producteurs_filter) > 0:
        df = df[df['nom_producteur'].isin(producteurs_filter)]
    
    if only_with_stock:
        df = df[df['poids_disponible_tonnes'] > 0]
    
    if not include_prevu:
        df = df[df['type_stock'] == 'REEL']
    
    return df


@st.cache_data(ttl=120)
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


@st.cache_data(ttl=120)
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


@st.cache_data(ttl=120)
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
    """Récupère la consommation moyenne hebdomadaire d'un produit"""
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
    """Calcule le besoin total d'un produit jusqu'à fin de campagne"""
    try:
        today = date.today()
        nb_semaines = (DATE_FIN_CAMPAGNE - today).days / 7.0
        
        if nb_semaines <= 0:
            return 0.0
        
        conso_hebdo = get_conso_moyenne_produit(code_produit)
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
        
        lot_id = int(lot_id)
        
        # Récupérer l'emplacement_id principal du lot
        cursor.execute("""
            SELECT id as emplacement_id, statut_lavage
            FROM stock_emplacements
            WHERE lot_id = %s AND is_active = TRUE
            ORDER BY poids_total_kg DESC
            LIMIT 1
        """, (lot_id,))
        empl_result = cursor.fetchone()
        
        if empl_result:
            emplacement_id = empl_result['emplacement_id']
            statut_stock = empl_result['statut_lavage'] or 'BRUT'
        else:
            # Lot PRÉVU sans stock réel → créer un emplacement virtuel
            # Récupérer infos du lot pour créer l'emplacement
            cursor.execute("""
                SELECT code_lot_interne, site_stockage, emplacement_stockage,
                       nombre_unites, type_conditionnement, poids_total_brut_kg
                FROM lots_bruts WHERE id = %s
            """, (lot_id,))
            lot_info = cursor.fetchone()
            
            if lot_info:
                site = lot_info['site_stockage'] or 'THEORIQUE'
                empl = lot_info['emplacement_stockage'] or 'PREVU'
                
                # Créer l'emplacement virtuel
                cursor.execute("""
                    INSERT INTO stock_emplacements (
                        lot_id, site_stockage, emplacement_stockage,
                        nombre_unites, type_conditionnement, poids_total_kg,
                        statut_lavage, is_active
                    ) VALUES (%s, %s, %s, %s, %s, %s, 'BRUT', TRUE)
                    RETURNING id
                """, (
                    lot_id, site, empl,
                    lot_info['nombre_unites'] or 0,
                    lot_info['type_conditionnement'] or 'Pallox',
                    lot_info['poids_total_brut_kg'] or 0
                ))
                emplacement_id = cursor.fetchone()['id']
            else:
                # Fallback : créer un emplacement minimal
                cursor.execute("""
                    INSERT INTO stock_emplacements (
                        lot_id, site_stockage, emplacement_stockage,
                        nombre_unites, type_conditionnement, poids_total_kg,
                        statut_lavage, is_active
                    ) VALUES (%s, 'THEORIQUE', 'PREVU', 0, 'Pallox', 0, 'BRUT', TRUE)
                    RETURNING id
                """, (lot_id,))
                emplacement_id = cursor.fetchone()['id']
            
            statut_stock = 'BRUT'
        
        # Calcul poids net
        poids_net = float(quantite_tonnes) * (1 - float(tare_pct) / 100)
        
        # Calcul date fin estimée
        conso_hebdo = get_conso_moyenne_produit(code_produit)
        
        # Trouver la dernière date fin des affectations existantes
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


@st.cache_data(ttl=30)
def get_affectations_existantes():
    """Récupère TOUTES les affectations actives"""
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


@st.cache_data(ttl=60)
def get_resume_par_produit():
    """Calcule le résumé par produit avec solde et dates"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        today = date.today()
        nb_semaines_restantes = max(0, (DATE_FIN_CAMPAGNE - today).days / 7.0)
        semaine_courante = today.isocalendar()[1]
        annee_courante = today.year
        
        cursor.execute("""
            WITH conso_5_semaines AS (
                SELECT 
                    code_produit_commercial,
                    AVG(quantite_prevue_tonnes) as conso_hebdo
                FROM (
                    SELECT 
                        code_produit_commercial,
                        quantite_prevue_tonnes,
                        ROW_NUMBER() OVER (PARTITION BY code_produit_commercial ORDER BY annee, semaine) as rn
                    FROM previsions_ventes
                    WHERE (annee = %s AND semaine >= %s) OR annee > %s
                ) sub
                WHERE rn <= 5
                GROUP BY code_produit_commercial
            ),
            affectations_agg AS (
                SELECT 
                    code_produit_commercial,
                    SUM(quantite_affectee_tonnes) as total_brut,
                    SUM(poids_net_estime_tonnes) as total_net,
                    COUNT(*) as nb_lots,
                    MAX(date_fin_estimee) as date_fin_derniere
                FROM previsions_affectations
                WHERE is_active = TRUE
                GROUP BY code_produit_commercial
            ),
            produits_avec_prev AS (
                SELECT DISTINCT code_produit_commercial
                FROM previsions_ventes
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
                a.date_fin_derniere,
                COALESCE(c.conso_hebdo, 0) as conso_hebdo,
                COALESCE(c.conso_hebdo, 0) * %s as besoin_campagne,
                COALESCE(a.total_net, 0) - (COALESCE(c.conso_hebdo, 0) * %s) as solde
            FROM ref_produits_commerciaux pc
            JOIN produits_avec_prev pap ON pc.code_produit = pap.code_produit_commercial
            LEFT JOIN conso_5_semaines c ON pc.code_produit = c.code_produit_commercial
            LEFT JOIN affectations_agg a ON pc.code_produit = a.code_produit_commercial
            WHERE pc.is_active = TRUE
            ORDER BY pc.marque, pc.libelle
        """, (annee_courante, semaine_courante, annee_courante, nb_semaines_restantes, nb_semaines_restantes))
        
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        
        if rows:
            df = pd.DataFrame(rows)
            
            numeric_cols = ['total_brut', 'total_net', 'nb_lots', 'conso_hebdo', 'besoin_campagne', 'solde']
            for col in numeric_cols:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
            
            df['semaines_couvertes'] = df.apply(
                lambda r: float(r['total_net']) / float(r['conso_hebdo']) if r['conso_hebdo'] > 0 else 0,
                axis=1
            )
            
            df['statut'] = df['solde'].apply(
                lambda s: 'SURPLUS' if s > 0 else ('MANQUE' if s < 0 else 'EQUILIBRE')
            )
            
            return df
        return pd.DataFrame()
        
    except Exception as e:
        st.error(f"Erreur résumé: {str(e)}")
        return pd.DataFrame()


def get_totaux_par_type_stock():
    """Récupère les totaux par type de stock (réel vs prévu)"""
    df = _get_all_lots_raw()
    if df.empty:
        return {'reel': 0, 'prevu': 0, 'total': 0}
    
    df_dispo = df[df['poids_disponible_tonnes'] > 0]
    
    reel = df_dispo[df_dispo['type_stock'] == 'REEL']['poids_disponible_tonnes'].sum()
    prevu = df_dispo[df_dispo['type_stock'] == 'PREVU']['poids_disponible_tonnes'].sum()
    
    return {
        'reel': reel,
        'prevu': prevu,
        'total': reel + prevu
    }


# ============================================================
# INTERFACE
# ============================================================

col_title, col_refresh = st.columns([6, 1])
with col_title:
    st.title("📋 Affectations Prévisions (Long Terme)")
with col_refresh:
    if st.button("🔄", help="Rafraîchir les données"):
        clear_data_cache()
        st.rerun()

st.caption(f"Affectation des lots aux produits commerciaux • Fin campagne: {DATE_FIN_CAMPAGNE.strftime('%d/%m/%Y')}")
st.markdown("---")

# KPIs Globaux type de stock
totaux = get_totaux_par_type_stock()
col_k1, col_k2, col_k3 = st.columns(3)
with col_k1:
    st.metric("📍 Stock Réel Dispo", f"{totaux['reel']:.1f} T", help="Lots physiquement en stock")
with col_k2:
    st.metric("📋 Stock Prévu Dispo", f"{totaux['prevu']:.1f} T", help="Lots prévus/commandés non encore reçus")
with col_k3:
    st.metric("📦 Total Disponible", f"{totaux['total']:.1f} T")

st.markdown("---")

# Initialiser session state
if 'affectations_config' not in st.session_state:
    st.session_state.affectations_config = {}

tab1, tab2, tab3 = st.tabs(["➕ Nouvelle Affectation", "📊 Affectations Existantes", "📈 Résumé & Soldes"])

# ============================================================
# TAB 1: NOUVELLE AFFECTATION
# ============================================================

with tab1:
    # Section 1: Résumé soldes
    st.subheader("📊 Soldes par Produit (temps réel)")
    
    resume_df = get_resume_par_produit()
    
    if not resume_df.empty:
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
            st.metric("📊 Solde Global", f"{total_solde:.1f} T", 
                     delta="surplus" if total_solde > 0 else "manque" if total_solde < 0 else "équilibré")
        
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
    st.caption("📍 = Stock réel (sur site) | 📋 = Stock prévu (commandé/non reçu)")
    
    # Filtres
    col_f1, col_f2, col_f3, col_f4 = st.columns([2, 2, 1, 1])
    
    with col_f1:
        varietes = get_varietes_disponibles()
        filter_varietes = st.multiselect("🌱 Variétés", varietes, key="filter_varietes")
    
    with col_f2:
        producteurs = get_producteurs_disponibles()
        filter_producteurs = st.multiselect("👨‍🌾 Producteurs", producteurs, key="filter_producteurs")
    
    with col_f3:
        only_stock = st.checkbox("Dispo > 0", value=True, key="only_stock")
    
    with col_f4:
        include_prevu = st.checkbox("Inclure prévus", value=True, key="include_prevu", 
                                    help="Inclure les lots commandés non encore reçus")
    
    # Charger lots
    lots_df = get_lots_disponibles(
        varietes_filter=filter_varietes if filter_varietes else None,
        producteurs_filter=filter_producteurs if filter_producteurs else None,
        only_with_stock=only_stock,
        include_prevu=include_prevu
    )
    
    if not lots_df.empty:
        # Compter par type
        nb_reel = len(lots_df[lots_df['type_stock'] == 'REEL'])
        nb_prevu = len(lots_df[lots_df['type_stock'] == 'PREVU'])
        st.caption(f"📦 {len(lots_df)} lot(s) : {nb_reel} 📍réel + {nb_prevu} 📋prévu • 🔵=CT 🟣=LT")
        
        # Préparer affichage
        display_cols = [
            'lot_id', 'type_stock_icon', 'code_lot_interne', 'nom_usage', 'nom_producteur', 'nom_variete',
            'poids_brut_effectif_tonnes', 'poids_disponible_tonnes', 'poids_net_estime_tonnes',
            'tare_pct', 'prix_achat_euro_tonne', 'date_entree_stock', 'affectations'
        ]
        display_cols = [c for c in display_cols if c in lots_df.columns]
        df_display = lots_df[display_cols].copy()
        df_display = df_display.reset_index(drop=True)
        
        column_config = {
            'lot_id': None,
            'type_stock_icon': st.column_config.TextColumn('📦', width='small', help="📍=Réel, 📋=Prévu"),
            'code_lot_interne': st.column_config.TextColumn('Code Lot', width='medium'),
            'nom_usage': st.column_config.TextColumn('Nom Lot', width='medium'),
            'nom_producteur': st.column_config.TextColumn('Producteur', width='medium'),
            'nom_variete': st.column_config.TextColumn('Variété', width='small'),
            'poids_brut_effectif_tonnes': st.column_config.NumberColumn('Brut (T)', format="%.1f"),
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
            
            produits_df = get_produits_commerciaux()
            
            if produits_df.empty:
                st.error("❌ Aucun produit commercial actif")
            else:
                for row_idx in selected_rows:
                    lot = lots_df.iloc[row_idx]
                    lot_id = int(lot['lot_id'])
                    type_stock = lot['type_stock']
                    
                    card_class = "lot-card" if type_stock == 'REEL' else "lot-card-prevu"
                    type_label = "📍 En stock" if type_stock == 'REEL' else "📋 Prévu"
                    
                    with st.container():
                        st.markdown(f"""
                        <div class="{card_class}">
                            <strong>{lot['code_lot_interne']}</strong> - {lot['nom_usage'] or ''} <span style="float:right">{type_label}</span><br>
                            🌱 {lot['nom_variete']} | 👨‍🌾 {lot['nom_producteur'] or 'N/A'} | 
                            📦 Dispo: <strong>{lot['poids_disponible_tonnes']:.1f} T</strong>
                        </div>
                        """, unsafe_allow_html=True)
                        
                        col1, col2, col3 = st.columns([3, 2, 2])
                        
                        with col1:
                            produit_options = produits_df['display_name'].tolist()
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
                            selected_produit = produits_df.iloc[selected_produit_idx]
                            code_produit = selected_produit['code_produit']
                            tare = float(lot['tare_pct']) if pd.notna(lot['tare_pct']) else 22.0
                            poids_net = float(quantite) * (1 - tare / 100)
                            
                            solde_actuel = get_solde_produit(code_produit)
                            nouveau_solde = float(solde_actuel['solde']) + poids_net
                            
                            st.metric(
                                "📊 Solde après",
                                f"{nouveau_solde:.1f} T",
                                delta=f"+{poids_net:.1f} T net",
                                delta_color="normal"
                            )
                            
                            conso = get_conso_moyenne_produit(code_produit)
                            if conso > 0:
                                date_fin = calc_date_fin_lot(poids_net, conso)
                                if date_fin:
                                    st.caption(f"📅 Fin estimée: {date_fin.strftime('%d/%m/%Y')}")
                        
                        st.session_state.affectations_config[lot_id] = {
                            'produit_idx': selected_produit_idx,
                            'quantite': quantite
                        }
                
                # Récapitulatif
                st.markdown("---")
                st.subheader("3️⃣ Récapitulatif et Validation")
                
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
                        'Type': '📍' if lot['type_stock'] == 'REEL' else '📋',
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
                        'Type': st.column_config.TextColumn('📦', width='small'),
                        'Brut (T)': st.column_config.NumberColumn(format="%.1f"),
                        'Net Est. (T)': st.column_config.NumberColumn(format="%.1f"),
                        'Tare %': st.column_config.NumberColumn(format="%.1f%%")
                    },
                    use_container_width=True,
                    hide_index=True
                )
                
                # Totaux par type
                total_brut = df_recap['Brut (T)'].sum()
                total_net = df_recap['Net Est. (T)'].sum()
                nb_reel_sel = len([r for r in recap_data if r['Type'] == '📍'])
                nb_prevu_sel = len([r for r in recap_data if r['Type'] == '📋'])
                
                col_tot1, col_tot2, col_tot3, col_tot4 = st.columns(4)
                with col_tot1:
                    st.metric("📦 Total Brut", f"{total_brut:.1f} T")
                with col_tot2:
                    st.metric("✨ Total Net Estimé", f"{total_net:.1f} T")
                with col_tot3:
                    st.metric("📍 Stock Réel", nb_reel_sel)
                with col_tot4:
                    st.metric("📋 Stock Prévu", nb_prevu_sel)
                
                # Bouton validation
                st.markdown("---")
                
                if st.button("✅ Créer les affectations", type="primary", use_container_width=True):
                    success_count = 0
                    error_messages = []
                    
                    for row_idx in selected_rows:
                        lot = lots_df.iloc[row_idx]
                        lot_id = int(lot['lot_id'])
                        config = st.session_state.affectations_config.get(lot_id, {})
                        
                        produit_idx = config.get('produit_idx', 0)
                        produit = produits_df.iloc[produit_idx]
                        quantite = config.get('quantite', float(lot['poids_disponible_tonnes']))
                        
                        success, result = create_affectation(
                            produit['code_produit'],
                            lot_id,
                            quantite,
                            lot['tare_pct'],
                            lot['tare_source']
                        )
                        
                        if success:
                            success_count += 1
                        else:
                            error_messages.append(f"{lot['code_lot_interne']}: {result}")
                    
                    if success_count > 0:
                        st.success(f"✅ {success_count} affectation(s) créée(s)")
                        st.balloons()
                        st.session_state.affectations_config = {}
                        clear_data_cache()
                        st.rerun()
                    
                    if error_messages:
                        for msg in error_messages:
                            st.error(msg)
    else:
        st.info("Aucun lot disponible avec les filtres sélectionnés")

# ============================================================
# TAB 2: AFFECTATIONS EXISTANTES
# ============================================================

with tab2:
    st.subheader("📊 Affectations Existantes")
    
    affectations_df = get_affectations_existantes()
    
    if not affectations_df.empty:
        # Filtres
        col_f1, col_f2, col_f3 = st.columns(3)
        
        with col_f1:
            marques = ["Toutes"] + sorted(affectations_df['marque'].dropna().unique().tolist())
            filter_marque = st.selectbox("Filtrer par marque", marques, key="filter_marque_exist")
        
        with col_f2:
            types_aff = ["Tous", "CT", "LT"]
            filter_type = st.selectbox("Type", types_aff, key="filter_type_exist")
        
        with col_f3:
            varietes_aff = ["Toutes"] + sorted(affectations_df['nom_variete'].dropna().unique().tolist())
            filter_variete_aff = st.selectbox("Variété", varietes_aff, key="filter_variete_exist")
        
        # Appliquer filtres
        df_filtered = affectations_df.copy()
        if filter_marque != "Toutes":
            df_filtered = df_filtered[df_filtered['marque'] == filter_marque]
        if filter_type != "Tous":
            df_filtered = df_filtered[df_filtered['type_affectation'] == filter_type]
        if filter_variete_aff != "Toutes":
            df_filtered = df_filtered[df_filtered['nom_variete'] == filter_variete_aff]
        
        if not df_filtered.empty:
            st.caption(f"📋 {len(df_filtered)} affectation(s) • 🔵=CT 🟣=LT")
            
            # Affichage
            display_cols = [
                'id', 'type_affectation', 'marque', 'produit_libelle', 
                'code_lot_interne', 'nom_variete', 
                'quantite_affectee_tonnes', 'poids_net_estime_tonnes',
                'tare_utilisee_pct', 'date_debut_estimee', 'date_fin_estimee'
            ]
            df_show = df_filtered[display_cols].copy()
            
            df_show['type_icon'] = df_show['type_affectation'].apply(lambda x: '🔵' if x == 'CT' else '🟣')
            
            column_config = {
                'id': None,
                'type_affectation': None,
                'type_icon': st.column_config.TextColumn('Type', width='small'),
                'marque': 'Marque',
                'produit_libelle': 'Produit',
                'code_lot_interne': 'Lot',
                'nom_variete': 'Variété',
                'quantite_affectee_tonnes': st.column_config.NumberColumn('Brut (T)', format="%.1f"),
                'poids_net_estime_tonnes': st.column_config.NumberColumn('Net (T)', format="%.1f"),
                'tare_utilisee_pct': st.column_config.NumberColumn('Tare %', format="%.1f%%"),
                'date_debut_estimee': st.column_config.DateColumn('Début', format="DD/MM/YY"),
                'date_fin_estimee': st.column_config.DateColumn('Fin', format="DD/MM/YY")
            }
            
            event = st.dataframe(
                df_show,
                column_config=column_config,
                use_container_width=True,
                hide_index=True,
                on_select="rerun",
                selection_mode="multi-row",
                key="affectations_table"
            )
            
            selected_rows = event.selection.rows if hasattr(event, 'selection') else []
            
            if len(selected_rows) > 0:
                if st.button(f"🗑️ Supprimer {len(selected_rows)} affectation(s)", type="secondary"):
                    for idx in selected_rows:
                        affectation_id = int(df_filtered.iloc[idx]['id'])
                        delete_affectation(affectation_id)
                    st.success(f"✅ {len(selected_rows)} supprimée(s)")
                    clear_data_cache()
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
    
    # Récap type stock
    totaux = get_totaux_par_type_stock()
    st.info(f"**Stock disponible:** 📍 {totaux['reel']:.1f} T réel + 📋 {totaux['prevu']:.1f} T prévu = **{totaux['total']:.1f} T total**")
    
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
        else:
            st.info("Aucun produit correspondant aux filtres")
    else:
        st.info("Aucune donnée disponible")

show_footer()
