"""
34_Prev_Besoins.py - Analyse des Besoins Campagne
=================================================
v2 - Optimisé avec intégration marge et couverture
   - Radio buttons (évite reset)
   - Couverture en semaines
   - Intégration prix/marge
   - Vue chronologique passages
"""

import streamlit as st
import pandas as pd
from datetime import datetime, date, timedelta
from database import get_connection
from components import show_footer
from auth import is_authenticated

st.set_page_config(page_title="Besoins Campagne - Culture Pom", page_icon="📊", layout="wide")

st.markdown("""
<style>
    .block-container { padding-top: 1.5rem !important; }
    .status-ok {
        background: linear-gradient(135deg, #e8f5e9 0%, #c8e6c9 100%);
        padding: 1rem; border-radius: 0.5rem; border-left: 4px solid #4caf50; margin: 0.3rem 0;
    }
    .status-warning {
        background: linear-gradient(135deg, #fff3e0 0%, #ffe0b2 100%);
        padding: 1rem; border-radius: 0.5rem; border-left: 4px solid #ff9800; margin: 0.3rem 0;
    }
    .status-danger {
        background: linear-gradient(135deg, #ffebee 0%, #ffcdd2 100%);
        padding: 1rem; border-radius: 0.5rem; border-left: 4px solid #f44336; margin: 0.3rem 0;
    }
    .info-card {
        background: linear-gradient(135deg, #e3f2fd 0%, #bbdefb 100%);
        padding: 1rem; border-radius: 0.5rem; border-left: 4px solid #2196f3; margin: 0.3rem 0;
    }
</style>
""", unsafe_allow_html=True)

if not is_authenticated():
    st.warning("⚠️ Veuillez vous connecter")
    st.stop()

# Constantes
DATE_FIN_CAMPAGNE = date(2026, 6, 30)

# ============================================================
# FONCTIONS
# ============================================================

@st.cache_data(ttl=60)
def get_couts_production():
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT type_atelier, cout_tonne FROM production_lignes WHERE is_active = TRUE AND cout_tonne IS NOT NULL")
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        return {row['type_atelier']: float(row['cout_tonne'] or 0) for row in rows} if rows else {}
    except:
        return {}

@st.cache_data(ttl=30)
def get_prix_ventes():
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'prix_ventes_previsions')")
        if not cursor.fetchone()['exists']:
            cursor.close()
            conn.close()
            return pd.DataFrame()
        
        cursor.execute("SELECT * FROM prix_ventes_previsions")
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        
        if rows:
            df = pd.DataFrame(rows)
            for col in ['prix_actuel', 'prix_2_semaines', 'prix_1_mois', 'prix_3_mois', 'prix_6_mois']:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
            return df
        return pd.DataFrame()
    except:
        return pd.DataFrame()

@st.cache_data(ttl=30)
def get_besoins_complet():
    """Calcule les besoins avec intégration prix et marge"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        today = date.today()
        semaines_restantes = max(1, (DATE_FIN_CAMPAGNE - today).days / 7.0)
        semaine_courante = today.isocalendar()[1]
        annee_courante = today.year
        
        # Vérifier colonne tare_theorique_pct
        cursor.execute("SELECT EXISTS (SELECT FROM information_schema.columns WHERE table_name = 'lots_bruts' AND column_name = 'tare_theorique_pct')")
        tare_col = cursor.fetchone()['exists']
        tare_expr = "COALESCE(l.tare_lavage_totale_pct, l.tare_theorique_pct, 22)" if tare_col else "COALESCE(l.tare_lavage_totale_pct, 22)"
        
        query = f"""
            WITH conso_hebdo AS (
                SELECT code_produit_commercial, AVG(quantite_prevue_tonnes) as conso_hebdo
                FROM (
                    SELECT code_produit_commercial, quantite_prevue_tonnes,
                           ROW_NUMBER() OVER (PARTITION BY code_produit_commercial ORDER BY annee, semaine) as rn
                    FROM previsions_ventes
                    WHERE (annee = %s AND semaine >= %s) OR annee > %s
                ) sub WHERE rn <= 5
                GROUP BY code_produit_commercial
            ),
            affectations_detail AS (
                SELECT 
                    pa.code_produit_commercial,
                    COUNT(*) as nb_lots,
                    SUM(pa.quantite_affectee_tonnes) as total_brut,
                    SUM(pa.poids_net_estime_tonnes) as total_net,
                    SUM(pa.quantite_affectee_tonnes * COALESCE(l.prix_achat_euro_tonne, 0)) / 
                        NULLIF(SUM(pa.quantite_affectee_tonnes), 0) as prix_achat_moyen,
                    SUM(pa.quantite_affectee_tonnes * {tare_expr}) / 
                        NULLIF(SUM(pa.quantite_affectee_tonnes), 0) as tare_moyenne
                FROM previsions_affectations pa
                JOIN lots_bruts l ON pa.lot_id = l.id
                WHERE pa.is_active = TRUE
                GROUP BY pa.code_produit_commercial
            )
            SELECT 
                pc.code_produit,
                pc.marque,
                pc.type_produit,
                pc.libelle,
                pc.atelier,
                COALESCE(ch.conso_hebdo, 0) as conso_hebdo,
                COALESCE(ch.conso_hebdo, 0) * %s as besoin_campagne,
                COALESCE(ad.nb_lots, 0) as nb_lots,
                COALESCE(ad.total_brut, 0) as total_brut,
                COALESCE(ad.total_net, 0) as total_net,
                COALESCE(ad.prix_achat_moyen, 0) as prix_achat_moyen,
                COALESCE(ad.tare_moyenne, 22) as tare_moyenne,
                COALESCE(ad.total_net, 0) - (COALESCE(ch.conso_hebdo, 0) * %s) as solde,
                -- Couverture en semaines
                CASE 
                    WHEN COALESCE(ch.conso_hebdo, 0) > 0 
                    THEN COALESCE(ad.total_net, 0) / ch.conso_hebdo
                    ELSE 0 
                END as couverture_semaines
            FROM ref_produits_commerciaux pc
            LEFT JOIN conso_hebdo ch ON pc.code_produit = ch.code_produit_commercial
            LEFT JOIN affectations_detail ad ON pc.code_produit = ad.code_produit_commercial
            WHERE pc.is_active = TRUE
              AND (COALESCE(ch.conso_hebdo, 0) > 0 OR COALESCE(ad.total_net, 0) > 0)
            ORDER BY 
                CASE 
                    WHEN COALESCE(ad.total_net, 0) - (COALESCE(ch.conso_hebdo, 0) * %s) < -100 THEN 1
                    WHEN COALESCE(ad.total_net, 0) - (COALESCE(ch.conso_hebdo, 0) * %s) < 0 THEN 2
                    ELSE 3
                END,
                COALESCE(ad.total_net, 0) - (COALESCE(ch.conso_hebdo, 0) * %s) ASC
        """
        
        cursor.execute(query, (
            annee_courante, semaine_courante, annee_courante,
            semaines_restantes, semaines_restantes,
            semaines_restantes, semaines_restantes, semaines_restantes
        ))
        
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        
        if rows:
            df = pd.DataFrame(rows)
            numeric_cols = ['conso_hebdo', 'besoin_campagne', 'nb_lots', 'total_brut', 
                           'total_net', 'prix_achat_moyen', 'tare_moyenne', 'solde', 'couverture_semaines']
            for col in numeric_cols:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
            return df, semaines_restantes
        return pd.DataFrame(), semaines_restantes
        
    except Exception as e:
        st.error(f"Erreur: {str(e)}")
        return pd.DataFrame(), 0

@st.cache_data(ttl=30)
def get_lots_affectes_produit(code_produit):
    """Récupère les lots affectés à un produit avec dates"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT EXISTS (SELECT FROM information_schema.columns WHERE table_name = 'lots_bruts' AND column_name = 'tare_theorique_pct')")
        tare_col = cursor.fetchone()['exists']
        tare_expr = "COALESCE(l.tare_lavage_totale_pct, l.tare_theorique_pct, 22)" if tare_col else "COALESCE(l.tare_lavage_totale_pct, 22)"
        
        query = f"""
            SELECT 
                pa.id,
                l.code_lot_interne,
                v.nom_variete,
                pa.quantite_affectee_tonnes as poids_brut,
                pa.poids_net_estime_tonnes as poids_net,
                COALESCE(l.prix_achat_euro_tonne, 0) as prix_achat,
                {tare_expr} as tare_pct,
                pa.date_passage_prevue,
                l.date_entree_stock
            FROM previsions_affectations pa
            JOIN lots_bruts l ON pa.lot_id = l.id
            LEFT JOIN ref_varietes v ON l.code_variete = v.code_variete
            WHERE pa.code_produit_commercial = %s AND pa.is_active = TRUE
            ORDER BY pa.date_passage_prevue NULLS LAST, l.prix_achat_euro_tonne ASC
        """
        
        cursor.execute(query, (code_produit,))
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        
        if rows:
            df = pd.DataFrame(rows)
            for col in ['poids_brut', 'poids_net', 'prix_achat', 'tare_pct']:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
            return df
        return pd.DataFrame()
    except:
        return pd.DataFrame()

@st.cache_data(ttl=30)
def get_previsions_semaines(code_produit, nb_semaines=12):
    """Récupère les prévisions semaine par semaine"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        today = date.today()
        semaine_courante = today.isocalendar()[1]
        annee_courante = today.year
        
        cursor.execute("""
            SELECT annee, semaine, quantite_prevue_tonnes
            FROM previsions_ventes
            WHERE code_produit_commercial = %s
              AND ((annee = %s AND semaine >= %s) OR annee > %s)
            ORDER BY annee, semaine
            LIMIT %s
        """, (code_produit, annee_courante, semaine_courante, annee_courante, nb_semaines))
        
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        
        if rows:
            df = pd.DataFrame(rows)
            df['semaine_label'] = df.apply(lambda x: f"S{x['semaine']}", axis=1)
            df['quantite_prevue_tonnes'] = pd.to_numeric(df['quantite_prevue_tonnes'], errors='coerce').fillna(0)
            return df
        return pd.DataFrame()
    except:
        return pd.DataFrame()

@st.cache_data(ttl=30)
def get_stock_disponible_variete():
    """Stock disponible par variété (non affecté)"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT EXISTS (SELECT FROM information_schema.columns WHERE table_name = 'lots_bruts' AND column_name = 'tare_theorique_pct')")
        tare_col = cursor.fetchone()['exists']
        tare_expr = "COALESCE(l.tare_lavage_totale_pct, l.tare_theorique_pct, 22)" if tare_col else "COALESCE(l.tare_lavage_totale_pct, 22)"
        
        query = f"""
            WITH lots_stock AS (
                SELECT 
                    l.id,
                    v.nom_variete,
                    l.poids_total_brut_kg / 1000 as poids_brut,
                    (l.poids_total_brut_kg / 1000) * (1 - {tare_expr} / 100) as poids_net
                FROM lots_bruts l
                LEFT JOIN ref_varietes v ON l.code_variete = v.code_variete
                WHERE l.is_active = TRUE AND l.poids_total_brut_kg > 0
            ),
            affectations AS (
                SELECT lot_id, SUM(quantite_affectee_tonnes) as affecte
                FROM previsions_affectations
                WHERE is_active = TRUE
                GROUP BY lot_id
            )
            SELECT 
                ls.nom_variete,
                SUM(ls.poids_brut) as poids_brut_total,
                SUM(ls.poids_net) as poids_net_total,
                SUM(COALESCE(a.affecte, 0)) as affecte_total,
                SUM(ls.poids_brut - COALESCE(a.affecte, 0)) as disponible_brut
            FROM lots_stock ls
            LEFT JOIN affectations a ON ls.id = a.lot_id
            GROUP BY ls.nom_variete
            HAVING SUM(ls.poids_brut - COALESCE(a.affecte, 0)) > 0
            ORDER BY SUM(ls.poids_brut - COALESCE(a.affecte, 0)) DESC
        """
        
        cursor.execute(query)
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        
        if rows:
            df = pd.DataFrame(rows)
            for col in ['poids_brut_total', 'poids_net_total', 'affecte_total', 'disponible_brut']:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
            return df
        return pd.DataFrame()
    except:
        return pd.DataFrame()

def calculer_marge_produit(prix_achat, tare_pct, cout_prod, prix_vente):
    """Calcule la marge pour un produit"""
    if prix_vente <= 0:
        return 0, 0
    cout_matiere = prix_achat / (1 - tare_pct / 100) if tare_pct < 100 else prix_achat
    cout_revient = cout_matiere + cout_prod
    marge_pct = ((prix_vente - cout_revient) / cout_revient * 100) if cout_revient > 0 else 0
    return cout_revient, marge_pct

# ============================================================
# INTERFACE
# ============================================================

st.title("📊 Analyse des Besoins")

# Calcul dates
today = date.today()
semaines_restantes = max(1, (DATE_FIN_CAMPAGNE - today).days / 7.0)

st.caption(f"Campagne jusqu'au {DATE_FIN_CAMPAGNE.strftime('%d/%m/%Y')} • {semaines_restantes:.0f} semaines restantes")
st.markdown("---")

# Charger données
besoins_df, sem_rest = get_besoins_complet()
prix_df = get_prix_ventes()
couts_prod = get_couts_production()
stock_variete_df = get_stock_disponible_variete()

# KPIs globaux
if not besoins_df.empty:
    col1, col2, col3, col4 = st.columns(4)
    
    nb_critique = len(besoins_df[besoins_df['solde'] < -100])
    nb_attention = len(besoins_df[(besoins_df['solde'] >= -100) & (besoins_df['solde'] < 0)])
    nb_ok = len(besoins_df[besoins_df['solde'] >= 0])
    manque_total = abs(besoins_df[besoins_df['solde'] < 0]['solde'].sum())
    
    with col1:
        st.metric("🔴 Critique", nb_critique, help="Manque > 100T")
    with col2:
        st.metric("🟠 Attention", nb_attention, help="Manque < 100T")
    with col3:
        st.metric("🟢 OK", nb_ok, help="Stock suffisant")
    with col4:
        st.metric("📉 Manque total", f"{manque_total:,.0f} T")

st.markdown("---")

# Navigation RADIO
onglet = st.radio(
    "Navigation",
    options=["📋 Vue Synthèse", "🔍 Détail Produit", "📦 Stock Disponible"],
    horizontal=True,
    label_visibility="collapsed"
)

st.markdown("---")

# ============================================================
# ONGLET 1: VUE SYNTHÈSE
# ============================================================

if onglet == "📋 Vue Synthèse":
    st.subheader("📋 Besoins par Produit")
    
    if not besoins_df.empty:
        # Filtres
        col_f1, col_f2, col_f3 = st.columns(3)
        
        with col_f1:
            statuts = ["Tous", "🔴 Critique", "🟠 Attention", "🟢 OK"]
            filtre_statut = st.selectbox("Statut", statuts, key="f_statut")
        
        with col_f2:
            marques = ["Toutes"] + sorted(besoins_df['marque'].dropna().unique().tolist())
            filtre_marque = st.selectbox("Marque", marques, key="f_marque")
        
        with col_f3:
            types = ["Tous"] + sorted(besoins_df['type_produit'].dropna().unique().tolist())
            filtre_type = st.selectbox("Type", types, key="f_type")
        
        # Appliquer filtres
        df_filtered = besoins_df.copy()
        
        if filtre_statut == "🔴 Critique":
            df_filtered = df_filtered[df_filtered['solde'] < -100]
        elif filtre_statut == "🟠 Attention":
            df_filtered = df_filtered[(df_filtered['solde'] >= -100) & (df_filtered['solde'] < 0)]
        elif filtre_statut == "🟢 OK":
            df_filtered = df_filtered[df_filtered['solde'] >= 0]
        
        if filtre_marque != "Toutes":
            df_filtered = df_filtered[df_filtered['marque'] == filtre_marque]
        
        if filtre_type != "Tous":
            df_filtered = df_filtered[df_filtered['type_produit'] == filtre_type]
        
        st.markdown("---")
        
        if not df_filtered.empty:
            # Enrichir avec prix et marge
            enriched_data = []
            
            for _, row in df_filtered.iterrows():
                code = row['code_produit']
                prix_row = prix_df[prix_df['code_produit_commercial'] == code] if not prix_df.empty else pd.DataFrame()
                prix_vente = float(prix_row.iloc[0]['prix_actuel']) if not prix_row.empty else 0
                
                atelier = row['atelier'] or 'SBU'
                cout_prod = couts_prod.get(atelier, 45.0)
                cout_revient, marge_pct = calculer_marge_produit(
                    row['prix_achat_moyen'], row['tare_moyenne'], cout_prod, prix_vente
                )
                
                # Statut
                if row['solde'] < -100:
                    statut = "🔴"
                elif row['solde'] < 0:
                    statut = "🟠"
                else:
                    statut = "🟢"
                
                enriched_data.append({
                    'Statut': statut,
                    'Marque': row['marque'],
                    'Type': row['type_produit'],
                    'Conso/sem': row['conso_hebdo'],
                    'Besoin': row['besoin_campagne'],
                    'Affecté': row['total_net'],
                    'Solde': row['solde'],
                    'Couverture': row['couverture_semaines'],
                    'Prix vente': prix_vente,
                    'Marge %': marge_pct,
                    'code_produit': code
                })
            
            df_display = pd.DataFrame(enriched_data)
            
            # Formater
            df_show = df_display.drop(columns=['code_produit']).copy()
            df_show['Conso/sem'] = df_show['Conso/sem'].apply(lambda x: f"{x:.1f} T")
            df_show['Besoin'] = df_show['Besoin'].apply(lambda x: f"{x:,.0f} T")
            df_show['Affecté'] = df_show['Affecté'].apply(lambda x: f"{x:,.0f} T")
            df_show['Solde'] = df_show['Solde'].apply(lambda x: f"{x:+,.0f} T")
            df_show['Couverture'] = df_show['Couverture'].apply(lambda x: f"{x:.0f} sem")
            df_show['Prix vente'] = df_show['Prix vente'].apply(lambda x: f"{x:,.0f} €" if x > 0 else "—")
            df_show['Marge %'] = df_show['Marge %'].apply(lambda x: f"{x:+.1f}%" if x != 0 else "—")
            
            st.dataframe(df_show, use_container_width=True, hide_index=True)
            
            st.markdown("---")
            
            # Résumé par statut
            st.markdown("#### 📊 Résumé")
            
            col_r1, col_r2, col_r3 = st.columns(3)
            
            critiques = df_filtered[df_filtered['solde'] < -100]
            if not critiques.empty:
                with col_r1:
                    manque_crit = abs(critiques['solde'].sum())
                    st.markdown(f"""
                    <div class="status-danger">
                        <h4>🔴 Critiques ({len(critiques)})</h4>
                        <p>Manque total: <b>{manque_crit:,.0f} T</b></p>
                        <p>À traiter en priorité</p>
                    </div>
                    """, unsafe_allow_html=True)
            
            attention = df_filtered[(df_filtered['solde'] >= -100) & (df_filtered['solde'] < 0)]
            if not attention.empty:
                with col_r2:
                    manque_att = abs(attention['solde'].sum())
                    st.markdown(f"""
                    <div class="status-warning">
                        <h4>🟠 Attention ({len(attention)})</h4>
                        <p>Manque total: <b>{manque_att:,.0f} T</b></p>
                        <p>À surveiller</p>
                    </div>
                    """, unsafe_allow_html=True)
            
            ok = df_filtered[df_filtered['solde'] >= 0]
            if not ok.empty:
                with col_r3:
                    surplus = ok['solde'].sum()
                    st.markdown(f"""
                    <div class="status-ok">
                        <h4>🟢 OK ({len(ok)})</h4>
                        <p>Surplus total: <b>{surplus:,.0f} T</b></p>
                        <p>Stock suffisant</p>
                    </div>
                    """, unsafe_allow_html=True)
            
            # Export
            st.markdown("---")
            csv = df_filtered.to_csv(index=False).encode('utf-8')
            st.download_button("📥 Exporter CSV", csv, f"besoins_{date.today().strftime('%Y%m%d')}.csv", "text/csv")
        else:
            st.info("Aucun produit correspondant aux filtres")
    else:
        st.info("Aucune donnée disponible")

# ============================================================
# ONGLET 2: DÉTAIL PRODUIT
# ============================================================

elif onglet == "🔍 Détail Produit":
    st.subheader("🔍 Analyse Détaillée par Produit")
    
    if not besoins_df.empty:
        # Sélection produit
        produits_list = [f"{row['marque']} - {row['type_produit']}" for _, row in besoins_df.iterrows()]
        selected = st.selectbox("Sélectionner un produit", produits_list, key="detail_produit")
        
        idx = produits_list.index(selected)
        produit = besoins_df.iloc[idx]
        code_produit = produit['code_produit']
        
        st.markdown("---")
        
        # KPIs produit
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("📈 Conso hebdo", f"{produit['conso_hebdo']:.1f} T/sem")
        
        with col2:
            st.metric("📦 Besoin campagne", f"{produit['besoin_campagne']:,.0f} T")
        
        with col3:
            solde = produit['solde']
            delta_color = "normal" if solde >= 0 else "inverse"
            st.metric("⚖️ Solde", f"{solde:+,.0f} T", delta_color=delta_color)
        
        with col4:
            couv = produit['couverture_semaines']
            st.metric("📅 Couverture", f"{couv:.0f} sem", 
                     f"sur {sem_rest:.0f}" if couv < sem_rest else "OK")
        
        st.markdown("---")
        
        # 2 colonnes : Coûts et Prévisions
        col_left, col_right = st.columns(2)
        
        with col_left:
            st.markdown("#### 💰 Analyse financière")
            
            prix_row = prix_df[prix_df['code_produit_commercial'] == code_produit] if not prix_df.empty else pd.DataFrame()
            prix_vente = float(prix_row.iloc[0]['prix_actuel']) if not prix_row.empty else 0
            
            atelier = produit['atelier'] or 'SBU'
            cout_prod = couts_prod.get(atelier, 45.0)
            prix_achat = produit['prix_achat_moyen']
            tare = produit['tare_moyenne']
            
            cout_matiere = prix_achat / (1 - tare / 100) if tare < 100 else prix_achat
            cout_revient = cout_matiere + cout_prod
            marge_pct = ((prix_vente - cout_revient) / cout_revient * 100) if cout_revient > 0 and prix_vente > 0 else 0
            
            # Card marge
            if marge_pct >= 10:
                card_class = "status-ok"
                icon = "✅"
            elif marge_pct >= 0:
                card_class = "status-warning"
                icon = "⚠️"
            else:
                card_class = "status-danger"
                icon = "🔴"
            
            st.markdown(f"""
            <div class="{card_class}">
                <h4>{icon} Marge: {marge_pct:+.1f}%</h4>
                <table style="width:100%">
                    <tr><td>Prix achat moyen</td><td style="text-align:right">{prix_achat:,.0f} €/T</td></tr>
                    <tr><td>Tare moyenne</td><td style="text-align:right">{tare:.1f}%</td></tr>
                    <tr><td>→ Coût matière net</td><td style="text-align:right">{cout_matiere:,.0f} €/T</td></tr>
                    <tr><td>Coût production</td><td style="text-align:right">{cout_prod:,.0f} €/T</td></tr>
                    <tr><td><b>Coût de revient</b></td><td style="text-align:right"><b>{cout_revient:,.0f} €/T</b></td></tr>
                    <tr><td colspan="2"><hr></td></tr>
                    <tr><td>Prix de vente</td><td style="text-align:right"><b>{prix_vente:,.0f} €/T</b></td></tr>
                </table>
            </div>
            """, unsafe_allow_html=True)
            
            if marge_pct < 10:
                prix_cible = cout_revient * 1.10
                st.info(f"💡 Prix vente min pour 10%: **{prix_cible:,.0f} €/T**")
        
        with col_right:
            st.markdown("#### 📈 Prévisions semaines")
            
            prev_df = get_previsions_semaines(code_produit, 12)
            
            if not prev_df.empty:
                st.bar_chart(prev_df.set_index('semaine_label')['quantite_prevue_tonnes'])
                
                col_t1, col_t2 = st.columns(2)
                with col_t1:
                    st.metric("Total 12 sem", f"{prev_df['quantite_prevue_tonnes'].sum():,.0f} T")
                with col_t2:
                    st.metric("Moyenne", f"{prev_df['quantite_prevue_tonnes'].mean():.1f} T/sem")
            else:
                st.info("Aucune prévision disponible")
        
        st.markdown("---")
        
        # Lots affectés
        st.markdown("#### 📦 Lots affectés")
        
        lots_df = get_lots_affectes_produit(code_produit)
        
        if not lots_df.empty:
            st.success(f"{len(lots_df)} lot(s) affecté(s) • {lots_df['poids_net'].sum():,.0f} T net")
            
            # Tableau lots
            df_lots_show = lots_df[['code_lot_interne', 'nom_variete', 'poids_brut', 'poids_net', 
                                    'prix_achat', 'tare_pct', 'date_passage_prevue']].copy()
            df_lots_show.columns = ['Lot', 'Variété', 'Brut (T)', 'Net (T)', 'Prix €/T', 'Tare %', 'Passage prévu']
            
            df_lots_show['Brut (T)'] = df_lots_show['Brut (T)'].apply(lambda x: f"{x:.1f}")
            df_lots_show['Net (T)'] = df_lots_show['Net (T)'].apply(lambda x: f"{x:.1f}")
            df_lots_show['Prix €/T'] = df_lots_show['Prix €/T'].apply(lambda x: f"{x:,.0f}")
            df_lots_show['Tare %'] = df_lots_show['Tare %'].apply(lambda x: f"{x:.0f}%")
            df_lots_show['Passage prévu'] = df_lots_show['Passage prévu'].apply(
                lambda x: x.strftime('%d/%m/%Y') if pd.notna(x) else "—"
            )
            
            st.dataframe(df_lots_show, use_container_width=True, hide_index=True)
            
            # Analyse prix
            prix_min = lots_df['prix_achat'].min()
            prix_max = lots_df['prix_achat'].max()
            prix_moy = lots_df['prix_achat'].mean()
            
            st.markdown(f"""
            **Analyse prix lots:** Min {prix_min:,.0f} €/T • Moy {prix_moy:,.0f} €/T • Max {prix_max:,.0f} €/T
            """)
        else:
            st.warning("⚠️ Aucun lot affecté")
            st.info("👉 Allez sur la page **Affectations** pour affecter des lots")
        
        # Actions rapides
        st.markdown("---")
        st.markdown("#### ⚡ Actions rapides")
        
        col_a1, col_a2 = st.columns(2)
        
        with col_a1:
            if st.button("📋 Aller aux Affectations", use_container_width=True):
                st.switch_page("pages/32_Prev_Affectations.py")
        
        with col_a2:
            if st.button("💰 Aller à Simulation", use_container_width=True):
                st.switch_page("pages/33_Prev_Simulation.py")
    else:
        st.info("Aucune donnée disponible")

# ============================================================
# ONGLET 3: STOCK DISPONIBLE
# ============================================================

elif onglet == "📦 Stock Disponible":
    st.subheader("📦 Stock Disponible par Variété")
    st.markdown("*Stock brut non encore affecté à un produit*")
    
    if not stock_variete_df.empty:
        # KPIs
        col1, col2, col3 = st.columns(3)
        
        total_brut = stock_variete_df['poids_brut_total'].sum()
        total_affecte = stock_variete_df['affecte_total'].sum()
        total_dispo = stock_variete_df['disponible_brut'].sum()
        
        with col1:
            st.metric("📦 Stock brut total", f"{total_brut:,.0f} T")
        with col2:
            st.metric("✅ Déjà affecté", f"{total_affecte:,.0f} T")
        with col3:
            st.metric("📋 Disponible", f"{total_dispo:,.0f} T")
        
        st.markdown("---")
        
        # Tableau
        df_stock_show = stock_variete_df[['nom_variete', 'poids_brut_total', 'affecte_total', 'disponible_brut']].copy()
        df_stock_show.columns = ['Variété', 'Stock brut (T)', 'Affecté (T)', 'Disponible (T)']
        
        df_stock_show['Stock brut (T)'] = df_stock_show['Stock brut (T)'].apply(lambda x: f"{x:,.0f}")
        df_stock_show['Affecté (T)'] = df_stock_show['Affecté (T)'].apply(lambda x: f"{x:,.0f}")
        df_stock_show['Disponible (T)'] = df_stock_show['Disponible (T)'].apply(lambda x: f"{x:,.0f}")
        
        st.dataframe(df_stock_show, use_container_width=True, hide_index=True)
        
        # Graphique
        st.markdown("---")
        st.markdown("#### 📊 Répartition")
        
        chart_df = stock_variete_df[['nom_variete', 'disponible_brut']].copy()
        chart_df = chart_df[chart_df['disponible_brut'] > 10]  # Filtrer petites valeurs
        chart_df = chart_df.set_index('nom_variete')
        
        if not chart_df.empty:
            st.bar_chart(chart_df['disponible_brut'])
        
        # Lien rapide
        st.markdown("---")
        if st.button("📋 Aller aux Affectations pour affecter ce stock", use_container_width=True):
            st.switch_page("pages/32_Prev_Affectations.py")
    else:
        st.info("Aucun stock disponible")

# ============================================================
# AIDE
# ============================================================

st.markdown("---")

with st.expander("ℹ️ Aide et explications"):
    st.markdown(f"""
    ### Calcul des besoins
    
    **Période**: Aujourd'hui → {DATE_FIN_CAMPAGNE.strftime('%d/%m/%Y')} ({sem_rest:.0f} semaines)
    
    **Formules:**
    - **Conso hebdo** = Moyenne des 5 prochaines semaines de prévisions
    - **Besoin** = Conso hebdo × {sem_rest:.0f} semaines
    - **Solde** = Stock affecté - Besoin
    - **Couverture** = Stock affecté / Conso hebdo (en semaines)
    
    **Statuts:**
    - 🔴 **Critique**: Manque > 100 T
    - 🟠 **Attention**: Manque ≤ 100 T
    - 🟢 **OK**: Stock suffisant
    
    ### Marge
    
    - **Coût matière net** = Prix achat / (1 - Tare%)
    - **Coût revient** = Coût matière + Coût production
    - **Marge %** = (Prix vente - Coût revient) / Coût revient × 100
    
    ### Actions recommandées
    
    1. **Produits critiques** → Acheter ou réaffecter lots
    2. **Marge < 10%** → Revoir affectations (lots moins chers) ou prix vente
    3. **Couverture faible** → Anticiper achats
    """)

show_footer()
