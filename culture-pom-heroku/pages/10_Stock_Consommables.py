"""
============================================================
PAGE STOCK CONSOMMABLES - VERSION CORRIGÉE
Culture Pom - 27/11/2025
============================================================

CORRECTIONS APPORTÉES :
1. Calcul valorisation : quantite × coefficient_conversion × prix_unitaire
2. KPIs dynamiques (réagissent aux filtres)
3. Affichage coefficient dans référentiel
4. Import compatible nouveau format Excel
"""

import streamlit as st
import pandas as pd
from datetime import datetime
from database import get_connection
from components import show_footer
from auth import is_authenticated
import io

st.set_page_config(page_title="Stock Consommables - Culture Pom", page_icon="📦", layout="wide")

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
</style>
""", unsafe_allow_html=True)

if not is_authenticated():
    st.warning("⚠️ Veuillez vous connecter")
    st.stop()

st.title("📦 Stock Consommables")
st.markdown("---")

# ==========================================
# FONCTION DE NORMALISATION (IDENTIQUE AU SCRIPT D'IMPORT)
# ==========================================

def normaliser_code(libelle):
    """
    Normalise un libellé en code unique.
    ⚠️ CETTE FONCTION DOIT ÊTRE IDENTIQUE AU SCRIPT D'IMPORT !
    """
    import pandas as pd
    
    if pd.isna(libelle) or not libelle:
        return "INCONNU"
    
    code = str(libelle).strip().upper()
    
    # Remplacements caractères spéciaux
    code = code.replace(' ', '_')
    code = code.replace('/', '_')
    code = code.replace('\\', '_')
    code = code.replace('(', '')
    code = code.replace(')', '')
    code = code.replace(',', '_')
    code = code.replace("'", '')
    code = code.replace('"', '')
    code = code.replace('+', '+')  # Garder le +
    code = code.replace('*', 'X')
    code = code.replace('.', '_')
    code = code.replace(':', '_')
    code = code.replace(';', '_')
    code = code.replace('&', '_ET_')
    code = code.replace('é', 'E')
    code = code.replace('è', 'E')
    code = code.replace('ê', 'E')
    code = code.replace('à', 'A')
    code = code.replace('â', 'A')
    code = code.replace('ô', 'O')
    code = code.replace('î', 'I')
    code = code.replace('ï', 'I')
    code = code.replace('ù', 'U')
    code = code.replace('û', 'U')
    code = code.replace('ç', 'C')
    
    # Supprimer doubles underscores
    while '__' in code:
        code = code.replace('__', '_')
    
    # Supprimer underscore en début/fin
    code = code.strip('_')
    
    # Limiter à 100 caractères
    return code[:100]

# ==========================================
# FONCTIONS BASE DE DONNÉES
# ==========================================

def get_kpis_consommables(site_filter=None, atelier_filter=None):
    """Récupère les KPIs - DYNAMIQUES selon filtres"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Construire WHERE clause
        where_conditions = ["sc.is_active = TRUE"]
        params = []
        
        if site_filter and site_filter != "Tous":
            where_conditions.append("sc.site = %s")
            params.append(site_filter)
        
        if atelier_filter and atelier_filter != "Tous":
            where_conditions.append("sc.atelier = %s")
            params.append(atelier_filter)
        
        where_clause = " AND ".join(where_conditions)
        
        # Nombre de références (dans le filtre)
        cursor.execute(f"""
            SELECT COUNT(DISTINCT sc.consommable_id) as nb 
            FROM stock_consommables sc
            WHERE {where_clause}
        """, params)
        nb_refs = cursor.fetchone()['nb']
        
        # Valeur totale CORRIGÉE : quantite × coefficient × prix
        cursor.execute(f"""
            SELECT COALESCE(SUM(
                sc.quantite * COALESCE(rc.coefficient_conversion, 1) * COALESCE(rc.prix_unitaire, 0)
            ), 0) as valeur
            FROM stock_consommables sc
            JOIN ref_consommables rc ON sc.consommable_id = rc.id
            WHERE {where_clause}
        """, params)
        valeur_totale = float(cursor.fetchone()['valeur'])
        
        # Nombre d'emplacements
        cursor.execute(f"""
            SELECT COUNT(*) as nb 
            FROM stock_consommables sc
            WHERE {where_clause}
        """, params)
        nb_emplacements = cursor.fetchone()['nb']
        
        # Alertes stock bas
        cursor.execute(f"""
            SELECT COUNT(*) as nb 
            FROM stock_consommables sc
            JOIN ref_consommables rc ON sc.consommable_id = rc.id
            WHERE {where_clause} AND rc.seuil_alerte > 0 AND sc.quantite <= rc.seuil_alerte
        """, params)
        nb_alertes = cursor.fetchone()['nb']
        
        cursor.close()
        conn.close()
        
        return {
            'nb_refs': nb_refs,
            'valeur_totale': valeur_totale,
            'nb_emplacements': nb_emplacements,
            'nb_alertes': nb_alertes
        }
    except Exception as e:
        st.error(f"❌ Erreur KPIs : {str(e)}")
        return None

def get_sites_ateliers():
    """Récupère la liste des sites et ateliers"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT DISTINCT site FROM stock_consommables WHERE is_active = TRUE ORDER BY site")
        sites = [row['site'] for row in cursor.fetchall()]
        
        cursor.execute("SELECT DISTINCT atelier FROM stock_consommables WHERE atelier IS NOT NULL AND is_active = TRUE ORDER BY atelier")
        ateliers = [row['atelier'] for row in cursor.fetchall()]
        
        cursor.close()
        conn.close()
        
        return sites, ateliers
    except Exception as e:
        return [], []

def get_stock_consommables(site_filter=None, atelier_filter=None):
    """Récupère le stock avec valorisation CORRIGÉE"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        where_conditions = ["sc.is_active = TRUE"]
        params = []
        
        if site_filter and site_filter != "Tous":
            where_conditions.append("sc.site = %s")
            params.append(site_filter)
        
        if atelier_filter and atelier_filter != "Tous":
            where_conditions.append("sc.atelier = %s")
            params.append(atelier_filter)
        
        where_clause = " AND ".join(where_conditions)
        
        # CORRECTION : calcul avec coefficient
        query = f"""
            SELECT 
                rc.code_consommable,
                rc.libelle,
                sc.site,
                sc.atelier,
                sc.emplacement,
                sc.quantite,
                rc.unite_inventaire,
                COALESCE(rc.coefficient_conversion, 1) as coefficient,
                rc.unite_facturation,
                rc.prix_unitaire,
                (sc.quantite * COALESCE(rc.coefficient_conversion, 1) * COALESCE(rc.prix_unitaire, 0)) as valeur,
                CASE WHEN rc.seuil_alerte > 0 AND sc.quantite <= rc.seuil_alerte THEN TRUE ELSE FALSE END as alerte
            FROM stock_consommables sc
            JOIN ref_consommables rc ON sc.consommable_id = rc.id
            WHERE {where_clause}
            ORDER BY rc.libelle, sc.site
        """
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        
        if rows:
            df = pd.DataFrame(rows)
            # Convertir types
            for col in ['quantite', 'coefficient', 'prix_unitaire', 'valeur']:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
            return df
        return pd.DataFrame()
    except Exception as e:
        st.error(f"❌ Erreur : {str(e)}")
        return pd.DataFrame()

def get_consommables_dropdown():
    """Liste des consommables pour dropdown"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, code_consommable, libelle 
            FROM ref_consommables 
            WHERE is_active = TRUE 
            ORDER BY libelle
        """)
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        return rows if rows else []
    except Exception as e:
        return []

def get_referentiel_consommables():
    """Récupère le référentiel complet avec coefficient"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, code_consommable, libelle, unite_inventaire,
                   COALESCE(coefficient_conversion, 1) as coefficient_conversion,
                   unite_facturation,
                   fournisseur_principal, prix_unitaire, seuil_alerte, is_active
            FROM ref_consommables
            ORDER BY libelle
        """)
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        
        if rows:
            return pd.DataFrame(rows)
        return pd.DataFrame()
    except Exception as e:
        st.error(f"❌ Erreur : {str(e)}")
        return pd.DataFrame()

def ajouter_entree_stock(consommable_id, site, atelier, emplacement, quantite, fournisseur, reference_bl, notes, user):
    """Ajoute une entrée de stock"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, quantite FROM stock_consommables
            WHERE consommable_id = %s AND site = %s 
              AND COALESCE(atelier, '') = COALESCE(%s, '')
              AND COALESCE(emplacement, '') = COALESCE(%s, '')
              AND is_active = TRUE
        """, (consommable_id, site, atelier, emplacement))
        
        existing = cursor.fetchone()
        
        if existing:
            quantite_avant = existing['quantite']
            quantite_apres = quantite_avant + quantite
            cursor.execute("""
                UPDATE stock_consommables
                SET quantite = %s, updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
            """, (quantite_apres, existing['id']))
        else:
            quantite_avant = 0
            quantite_apres = quantite
            cursor.execute("""
                INSERT INTO stock_consommables (consommable_id, site, atelier, emplacement, quantite)
                VALUES (%s, %s, %s, %s, %s)
            """, (consommable_id, site, atelier, emplacement, quantite))
        
        # Mouvement
        cursor.execute("""
            INSERT INTO stock_consommables_mouvements 
            (consommable_id, type_mouvement, site, atelier, emplacement,
             quantite_avant, quantite_apres, quantite_mouvement,
             reference_document, fournisseur, notes, created_by)
            VALUES (%s, 'ENTREE', %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (consommable_id, site, atelier, emplacement, quantite_avant, quantite_apres, quantite, reference_bl, fournisseur, notes, user))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return True, f"✅ Entrée : +{quantite} unités"
    except Exception as e:
        if 'conn' in locals():
            conn.rollback()
        return False, f"❌ Erreur : {str(e)}"

def ajuster_stock(consommable_id, site, atelier, emplacement, nouvelle_quantite, motif, user):
    """Ajuste le stock"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, quantite FROM stock_consommables
            WHERE consommable_id = %s AND site = %s 
              AND COALESCE(atelier, '') = COALESCE(%s, '')
              AND COALESCE(emplacement, '') = COALESCE(%s, '')
              AND is_active = TRUE
        """, (consommable_id, site, atelier, emplacement))
        
        existing = cursor.fetchone()
        
        if existing:
            quantite_avant = existing['quantite']
            quantite_mouvement = nouvelle_quantite - quantite_avant
            cursor.execute("""
                UPDATE stock_consommables
                SET quantite = %s, updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
            """, (nouvelle_quantite, existing['id']))
        else:
            quantite_avant = 0
            quantite_mouvement = nouvelle_quantite
            cursor.execute("""
                INSERT INTO stock_consommables (consommable_id, site, atelier, emplacement, quantite)
                VALUES (%s, %s, %s, %s, %s)
            """, (consommable_id, site, atelier, emplacement, nouvelle_quantite))
        
        cursor.execute("""
            INSERT INTO stock_consommables_mouvements 
            (consommable_id, type_mouvement, site, atelier, emplacement,
             quantite_avant, quantite_apres, quantite_mouvement, notes, created_by)
            VALUES (%s, 'AJUSTEMENT', %s, %s, %s, %s, %s, %s, %s, %s)
        """, (consommable_id, site, atelier, emplacement, quantite_avant, nouvelle_quantite, quantite_mouvement, motif, user))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return True, f"✅ Stock ajusté : {quantite_avant} → {nouvelle_quantite}"
    except Exception as e:
        if 'conn' in locals():
            conn.rollback()
        return False, f"❌ Erreur : {str(e)}"

def sauvegarder_consommable(consommable_id, data):
    """Sauvegarde un consommable"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        if consommable_id:
            cursor.execute("""
                UPDATE ref_consommables
                SET libelle = %s, unite_inventaire = %s, fournisseur_principal = %s,
                    prix_unitaire = %s, seuil_alerte = %s, 
                    coefficient_conversion = %s, unite_facturation = %s,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
            """, (data['libelle'], data['unite_inventaire'], data['fournisseur_principal'],
                  data['prix_unitaire'], data['seuil_alerte'], 
                  data.get('coefficient_conversion', 1), data.get('unite_facturation'),
                  consommable_id))
        else:
            cursor.execute("""
                INSERT INTO ref_consommables (code_consommable, libelle, unite_inventaire,
                    fournisseur_principal, prix_unitaire, seuil_alerte, coefficient_conversion, unite_facturation)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (data['code_consommable'], data['libelle'], data['unite_inventaire'],
                  data['fournisseur_principal'], data['prix_unitaire'], data['seuil_alerte'],
                  data.get('coefficient_conversion', 1), data.get('unite_facturation')))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return True, "✅ Enregistré"
    except Exception as e:
        if 'conn' in locals():
            conn.rollback()
        return False, f"❌ Erreur : {str(e)}"

# ==========================================
# FILTRES GLOBAUX (en haut)
# ==========================================

sites, ateliers = get_sites_ateliers()

col_f1, col_f2, col_f3 = st.columns([2, 2, 1])
with col_f1:
    site_global = st.selectbox("🏭 Site", ["Tous"] + sites, key="global_site")
with col_f2:
    atelier_global = st.selectbox("🔧 Atelier", ["Tous"] + ateliers, key="global_atelier")
with col_f3:
    if st.button("🔄 Actualiser", use_container_width=True):
        st.rerun()

st.markdown("---")

# ==========================================
# KPIs DYNAMIQUES
# ==========================================

kpis = get_kpis_consommables(site_global, atelier_global)

if kpis:
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("📋 Références", kpis['nb_refs'])
    with col2:
        valeur_str = f"{kpis['valeur_totale']:,.2f}".replace(",", " ")
        st.metric("💰 Valeur Stock", f"{valeur_str} €")
    with col3:
        st.metric("📍 Emplacements", kpis['nb_emplacements'])
    with col4:
        if kpis['nb_alertes'] > 0:
            st.metric("⚠️ Alertes", kpis['nb_alertes'], delta=f"-{kpis['nb_alertes']}", delta_color="inverse")
        else:
            st.metric("✅ Alertes", 0)

st.markdown("---")

# ==========================================
# ONGLETS
# ==========================================

tab1, tab2, tab3, tab4, tab5 = st.tabs(["📦 Vue Stock", "📥 Entrée", "🔧 Ajustement", "📋 Référentiel", "📤 Import"])

# ==========================================
# ONGLET 1: VUE STOCK
# ==========================================

with tab1:
    st.subheader("📦 Stock Consommables")
    
    df_stock = get_stock_consommables(site_global, atelier_global)
    
    if not df_stock.empty:
        # Renommer pour affichage
        df_display = df_stock.rename(columns={
            'code_consommable': 'Code',
            'libelle': 'Libellé',
            'site': 'Site',
            'atelier': 'Atelier',
            'emplacement': 'Emplacement',
            'quantite': 'Qté Inv.',
            'unite_inventaire': 'Unité Inv.',
            'coefficient': 'Coef.',
            'unite_facturation': 'Unité Fact.',
            'prix_unitaire': 'Prix Unit.',
            'valeur': 'Valeur €',
            'alerte': 'Alerte'
        })
        
        # Colonnes à afficher
        cols_display = ['Code', 'Libellé', 'Site', 'Atelier', 'Qté Inv.', 'Unité Inv.', 'Coef.', 'Prix Unit.', 'Valeur €']
        
        st.dataframe(
            df_display[cols_display],
            use_container_width=True,
            hide_index=True,
            column_config={
                'Coef.': st.column_config.NumberColumn(format="%.2f"),
                'Prix Unit.': st.column_config.NumberColumn(format="%.2f €"),
                'Valeur €': st.column_config.NumberColumn(format="%.2f €")
            }
        )
        
        # Total
        total_valeur = df_stock['valeur'].sum()
        total_valeur_str = f"{total_valeur:,.2f}".replace(",", " ")
        st.info(f"**{len(df_stock)} ligne(s)** - Valeur totale : **{total_valeur_str} €**")
        
        # Export
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            df_display.to_excel(writer, index=False, sheet_name='Stock')
        st.download_button("📥 Exporter Excel", buffer.getvalue(), 
                          f"stock_consommables_{datetime.now().strftime('%Y%m%d')}.xlsx",
                          use_container_width=True)
    else:
        st.info("📭 Aucun stock trouvé. Utilisez l'onglet **Import** pour charger les données.")

# ==========================================
# ONGLET 2: ENTRÉE
# ==========================================

with tab2:
    st.subheader("📥 Entrée de Stock (Livraison)")
    
    consommables = get_consommables_dropdown()
    
    if consommables:
        col1, col2 = st.columns(2)
        
        with col1:
            conso_options = [f"{c['libelle']} ({c['code_consommable']})" for c in consommables]
            selected_conso = st.selectbox("Consommable *", conso_options, key="entree_conso")
            conso_idx = conso_options.index(selected_conso)
            conso_id = consommables[conso_idx]['id']
            
            site = st.selectbox("Site *", ["St Flavy", "Corroy", "La Motte-Tilly"], key="entree_site")
            atelier = st.text_input("Atelier", key="entree_atelier", placeholder="Ex: COMMUN, BANC COUSEUR...")
            emplacement = st.text_input("Emplacement", key="entree_emplacement")
        
        with col2:
            quantite = st.number_input("Quantité *", min_value=1, value=1, key="entree_qte")
            fournisseur = st.text_input("Fournisseur", key="entree_fournisseur")
            reference_bl = st.text_input("N° BL", key="entree_bl")
            notes = st.text_area("Notes", key="entree_notes", height=68)
        
        if st.button("✅ Enregistrer l'entrée", type="primary", use_container_width=True):
            user = st.session_state.get('username', 'system')
            success, msg = ajouter_entree_stock(conso_id, site, atelier if atelier else None, 
                                                emplacement if emplacement else None,
                                                quantite, fournisseur, reference_bl, notes, user)
            if success:
                st.success(msg)
                st.balloons()
            else:
                st.error(msg)
    else:
        st.warning("⚠️ Aucun consommable. Utilisez l'onglet **Import** d'abord.")

# ==========================================
# ONGLET 3: AJUSTEMENT
# ==========================================

with tab3:
    st.subheader("🔧 Ajustement de Stock")
    
    df_stock_ajust = get_stock_consommables()
    
    if not df_stock_ajust.empty:
        options = []
        for _, row in df_stock_ajust.iterrows():
            loc = f"{row['site']}"
            if row['atelier']:
                loc += f" / {row['atelier']}"
            options.append(f"{row['libelle']} - {loc} (Qté: {row['quantite']})")
        
        selected = st.selectbox("Sélectionner l'emplacement", options, key="ajust_select")
        idx = options.index(selected)
        row_selected = df_stock_ajust.iloc[idx]
        
        col1, col2 = st.columns(2)
        with col1:
            st.info(f"**Stock actuel** : {row_selected['quantite']} {row_selected['unite_inventaire']}")
            nouvelle_qte = st.number_input("Nouvelle quantité", min_value=0, 
                                           value=int(row_selected['quantite']), key="ajust_qte")
        with col2:
            motif = st.text_area("Motif *", key="ajust_motif", placeholder="Ex: Erreur comptage...")
        
        ecart = nouvelle_qte - row_selected['quantite']
        if ecart != 0:
            st.warning(f"📊 Écart : {'+' if ecart > 0 else ''}{ecart} unités")
        
        if st.button("✅ Valider", type="primary", use_container_width=True, key="btn_ajust"):
            if not motif:
                st.error("❌ Motif obligatoire")
            else:
                conn = get_connection()
                cursor = conn.cursor()
                cursor.execute("SELECT id FROM ref_consommables WHERE code_consommable = %s", 
                              (row_selected['code_consommable'],))
                conso = cursor.fetchone()
                cursor.close()
                conn.close()
                
                if conso:
                    user = st.session_state.get('username', 'system')
                    success, msg = ajuster_stock(conso['id'], row_selected['site'], 
                                                 row_selected['atelier'], row_selected['emplacement'],
                                                 nouvelle_qte, motif, user)
                    if success:
                        st.success(msg)
                        st.rerun()
                    else:
                        st.error(msg)
    else:
        st.info("📭 Aucun stock à ajuster")

# ==========================================
# ONGLET 4: RÉFÉRENTIEL
# ==========================================

with tab4:
    st.subheader("📋 Référentiel Consommables")
    
    is_admin = st.session_state.get('role') == 'ADMIN'
    
    df_ref = get_referentiel_consommables()
    
    if not df_ref.empty:
        df_ref_display = df_ref.rename(columns={
            'code_consommable': 'Code',
            'libelle': 'Libellé',
            'unite_inventaire': 'Unité Inv.',
            'coefficient_conversion': 'Coef.',
            'unite_facturation': 'Unité Fact.',
            'fournisseur_principal': 'Fournisseur',
            'prix_unitaire': 'Prix (€)',
            'seuil_alerte': 'Seuil',
            'is_active': 'Actif'
        })
        
        st.dataframe(
            df_ref_display[['Code', 'Libellé', 'Unité Inv.', 'Coef.', 'Unité Fact.', 'Fournisseur', 'Prix (€)', 'Seuil', 'Actif']],
            use_container_width=True, 
            hide_index=True,
            column_config={
                'Coef.': st.column_config.NumberColumn(format="%.2f"),
                'Prix (€)': st.column_config.NumberColumn(format="%.2f")
            }
        )
        
        st.info(f"**{len(df_ref)} référence(s)** dans le catalogue")
    
    # Formulaire ajout (Admin)
    if is_admin:
        st.markdown("---")
        st.markdown("### ➕ Ajouter une référence")
        
        col1, col2 = st.columns(2)
        with col1:
            libelle = st.text_input("Libellé *", key="ref_libelle", 
                                   help="Le code sera généré automatiquement depuis le libellé")
            
            # ⭐ Générer code automatiquement depuis libellé
            code_genere = normaliser_code(libelle) if libelle else ""
            st.text_input("Code (auto-généré)", value=code_genere, disabled=True, key="ref_code_display",
                         help="Code généré automatiquement - non modifiable pour cohérence")
            
            unite = st.selectbox("Unité inventaire", ["Unité", "Bobines", "Poches", "Palettes", "Rouleaux", "Aiguilles", "Bobine"], key="ref_unite")
            coef = st.number_input("Coefficient conversion", min_value=0.0, value=1.0, step=0.1, key="ref_coef",
                                  help="Ex: 280 si 1 poche = 280 Big Bags")
        with col2:
            unite_fact = st.text_input("Unité facturation", key="ref_unite_fact", placeholder="Ex: au mille sac")
            fournisseur = st.text_input("Fournisseur", key="ref_fournisseur")
            prix = st.number_input("Prix unitaire (€)", min_value=0.0, value=0.0, step=0.01, key="ref_prix")
            seuil = st.number_input("Seuil alerte", min_value=0, value=0, key="ref_seuil")
        
        if st.button("💾 Enregistrer", type="primary", use_container_width=True, key="btn_save_ref"):
            if not libelle:
                st.error("❌ Libellé obligatoire")
            elif not code_genere:
                st.error("❌ Impossible de générer le code")
            else:
                data = {
                    'code_consommable': code_genere,  # ⭐ Code normalisé
                    'libelle': libelle,
                    'unite_inventaire': unite,
                    'coefficient_conversion': coef,
                    'unite_facturation': unite_fact if unite_fact else None,
                    'fournisseur_principal': fournisseur,
                    'prix_unitaire': prix,
                    'seuil_alerte': seuil
                }
                success, msg = sauvegarder_consommable(None, data)
                if success:
                    st.success(msg)
                    st.rerun()
                else:
                    st.error(msg)
    else:
        st.info("ℹ️ Seuls les administrateurs peuvent modifier le référentiel")

# ==========================================
# ONGLET 5: IMPORT
# ==========================================

with tab5:
    st.subheader("📤 Import Excel")
    
    st.markdown("""
    **Format attendu** (fichier modele_import_inventaire.xlsx) :
    | Site | Atelier INV | Référence | Stock | UNITE INVENTAIRE | Fournisseur | Stock ramené | Unité facturation | Prix |
    
    💡 **Pour un import complet avec coefficients**, utilisez le script Python `import_consommables_complet.py`
    """)
    
    uploaded_file = st.file_uploader("Fichier Excel", type=['xlsx', 'xls'], key="upload_conso")
    
    if uploaded_file:
        try:
            df_upload = pd.read_excel(uploaded_file, header=0)
            
            st.markdown("### Aperçu")
            st.dataframe(df_upload.head(10), use_container_width=True, hide_index=True)
            st.info(f"**{len(df_upload)} lignes** détectées")
            
            # Vérifier colonnes
            has_coef_columns = all(col in df_upload.columns for col in ['Stock ramené à unité de facturation', 'Prix'])
            
            if has_coef_columns:
                st.success("✅ Fichier avec coefficients détecté")
                st.warning("⚠️ Pour un import complet avec coefficients et remise à zéro, utilisez le script Python.")
            else:
                st.info("ℹ️ Format simplifié détecté (sans coefficients)")
                
        except Exception as e:
            st.error(f"❌ Erreur : {str(e)}")

show_footer()
