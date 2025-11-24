import streamlit as st
import pandas as pd
from datetime import datetime
from database import get_connection
from components import show_footer
from auth import is_authenticated
import io

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
    .alerte-stock {
        background-color: #ffebee;
        border-left: 4px solid #f44336;
        padding: 0.5rem;
        border-radius: 0.25rem;
    }
</style>
""", unsafe_allow_html=True)

if not is_authenticated():
    st.warning("⚠️ Veuillez vous connecter pour accéder à cette page")
    st.stop()

st.title("📦 Stock Consommables")
st.markdown("*Gestion des emballages et consommables*")
st.markdown("---")

# ==========================================
# FONCTIONS UTILITAIRES
# ==========================================

def get_kpis_consommables():
    """Récupère les KPIs du stock consommables"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Nb références actives
        cursor.execute("SELECT COUNT(*) as nb FROM ref_consommables WHERE is_active = TRUE")
        nb_refs = cursor.fetchone()['nb']
        
        # Valeur totale stock
        cursor.execute("""
            SELECT COALESCE(SUM(sc.quantite * rc.prix_unitaire), 0) as valeur
            FROM stock_consommables sc
            JOIN ref_consommables rc ON sc.consommable_id = rc.id
            WHERE sc.is_active = TRUE AND rc.is_active = TRUE
        """)
        valeur_totale = float(cursor.fetchone()['valeur'])
        
        # Nb emplacements
        cursor.execute("SELECT COUNT(*) as nb FROM stock_consommables WHERE is_active = TRUE AND quantite > 0")
        nb_emplacements = cursor.fetchone()['nb']
        
        # Nb alertes stock
        cursor.execute("""
            SELECT COUNT(*) as nb
            FROM stock_consommables sc
            JOIN ref_consommables rc ON sc.consommable_id = rc.id
            WHERE sc.is_active = TRUE AND rc.is_active = TRUE
              AND sc.quantite <= rc.seuil_alerte AND rc.seuil_alerte > 0
        """)
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

def get_stock_consommables(site_filter=None, atelier_filter=None):
    """Récupère le stock consommables"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        query = """
        SELECT 
            sc.id,
            rc.code_consommable,
            rc.libelle,
            sc.site,
            sc.atelier,
            sc.emplacement,
            sc.quantite,
            rc.unite_inventaire,
            rc.prix_unitaire,
            (sc.quantite * rc.prix_unitaire) as valeur,
            rc.seuil_alerte,
            CASE WHEN sc.quantite <= rc.seuil_alerte AND rc.seuil_alerte > 0 THEN TRUE ELSE FALSE END as alerte
        FROM stock_consommables sc
        JOIN ref_consommables rc ON sc.consommable_id = rc.id
        WHERE sc.is_active = TRUE AND rc.is_active = TRUE
        """
        
        params = []
        if site_filter and site_filter != "Tous":
            query += " AND sc.site = %s"
            params.append(site_filter)
        if atelier_filter and atelier_filter != "Tous":
            query += " AND sc.atelier = %s"
            params.append(atelier_filter)
        
        query += " ORDER BY sc.site, sc.atelier, rc.libelle"
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        
        if rows:
            df = pd.DataFrame(rows)
            return df
        return pd.DataFrame()
    except Exception as e:
        st.error(f"❌ Erreur chargement stock : {str(e)}")
        return pd.DataFrame()

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
    except:
        return [], []

def get_consommables_dropdown():
    """Récupère les consommables pour dropdown"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, code_consommable, libelle, prix_unitaire
            FROM ref_consommables
            WHERE is_active = TRUE
            ORDER BY libelle
        """)
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        
        return rows if rows else []
    except:
        return []

def get_referentiel_consommables():
    """Récupère le référentiel complet"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, code_consommable, libelle, unite_inventaire,
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
    """Ajoute une entrée de stock (livraison)"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Vérifier si emplacement existe déjà
        cursor.execute("""
            SELECT id, quantite FROM stock_consommables
            WHERE consommable_id = %s AND site = %s 
              AND COALESCE(atelier, '') = COALESCE(%s, '')
              AND COALESCE(emplacement, '') = COALESCE(%s, '')
              AND is_active = TRUE
        """, (consommable_id, site, atelier, emplacement))
        
        existing = cursor.fetchone()
        
        if existing:
            # Mise à jour
            quantite_avant = existing['quantite']
            quantite_apres = quantite_avant + quantite
            
            cursor.execute("""
                UPDATE stock_consommables
                SET quantite = %s, updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
            """, (quantite_apres, existing['id']))
        else:
            # Création
            quantite_avant = 0
            quantite_apres = quantite
            
            cursor.execute("""
                INSERT INTO stock_consommables (consommable_id, site, atelier, emplacement, quantite)
                VALUES (%s, %s, %s, %s, %s)
            """, (consommable_id, site, atelier, emplacement, quantite))
        
        # Enregistrer mouvement
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
        
        return True, f"✅ Entrée enregistrée : +{quantite} unités"
    except Exception as e:
        if 'conn' in locals():
            conn.rollback()
        return False, f"❌ Erreur : {str(e)}"

def ajuster_stock(consommable_id, site, atelier, emplacement, nouvelle_quantite, motif, user):
    """Ajuste le stock (correction)"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Récupérer stock actuel
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
        
        # Enregistrer mouvement
        cursor.execute("""
            INSERT INTO stock_consommables_mouvements 
            (consommable_id, type_mouvement, site, atelier, emplacement,
             quantite_avant, quantite_apres, quantite_mouvement,
             notes, created_by)
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
    """Sauvegarde ou crée un consommable"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        if consommable_id:
            # Update
            cursor.execute("""
                UPDATE ref_consommables
                SET libelle = %s, unite_inventaire = %s, fournisseur_principal = %s,
                    prix_unitaire = %s, seuil_alerte = %s, updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
            """, (data['libelle'], data['unite_inventaire'], data['fournisseur_principal'],
                  data['prix_unitaire'], data['seuil_alerte'], consommable_id))
        else:
            # Insert
            cursor.execute("""
                INSERT INTO ref_consommables (code_consommable, libelle, unite_inventaire,
                    fournisseur_principal, prix_unitaire, seuil_alerte)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (data['code_consommable'], data['libelle'], data['unite_inventaire'],
                  data['fournisseur_principal'], data['prix_unitaire'], data['seuil_alerte']))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return True, "✅ Enregistré avec succès"
    except Exception as e:
        if 'conn' in locals():
            conn.rollback()
        return False, f"❌ Erreur : {str(e)}"

def importer_stock_excel(df_import):
    """Importe le stock depuis Excel"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        nb_refs_created = 0
        nb_stock_created = 0
        errors = []
        
        for idx, row in df_import.iterrows():
            try:
                site = str(row.get('Site', '')).strip()
                atelier = str(row.get('Atelier', '')).strip() if pd.notna(row.get('Atelier')) else None
                reference = str(row.get('Reference', '')).strip()
                quantite = int(row.get('Quantite', 0)) if pd.notna(row.get('Quantite')) else 0
                unite = str(row.get('Unite', 'Unité')).strip() if pd.notna(row.get('Unite')) else 'Unité'
                prix = float(row.get('Prix', 0)) if pd.notna(row.get('Prix')) else 0
                fournisseur = str(row.get('Fournisseur', '')).strip() if pd.notna(row.get('Fournisseur')) else None
                
                if not reference or not site:
                    continue
                
                # Créer code consommable
                code = reference.upper().replace(' ', '_')[:50]
                
                # Vérifier/créer référence
                cursor.execute("SELECT id FROM ref_consommables WHERE code_consommable = %s", (code,))
                ref_existing = cursor.fetchone()
                
                if ref_existing:
                    consommable_id = ref_existing['id']
                else:
                    cursor.execute("""
                        INSERT INTO ref_consommables (code_consommable, libelle, unite_inventaire, fournisseur_principal, prix_unitaire)
                        VALUES (%s, %s, %s, %s, %s)
                        RETURNING id
                    """, (code, reference, unite, fournisseur, prix))
                    consommable_id = cursor.fetchone()['id']
                    nb_refs_created += 1
                
                # Créer stock si quantité > 0
                if quantite > 0:
                    # Vérifier si stock existe déjà
                    cursor.execute("""
                        SELECT id FROM stock_consommables 
                        WHERE consommable_id = %s AND site = %s 
                          AND COALESCE(atelier, '') = COALESCE(%s, '')
                          AND emplacement IS NULL
                    """, (consommable_id, site, atelier))
                    existing = cursor.fetchone()
                    
                    if existing:
                        cursor.execute("""
                            UPDATE stock_consommables 
                            SET quantite = %s, updated_at = CURRENT_TIMESTAMP
                            WHERE id = %s
                        """, (quantite, existing['id']))
                    else:
                        cursor.execute("""
                            INSERT INTO stock_consommables (consommable_id, site, atelier, emplacement, quantite)
                            VALUES (%s, %s, %s, NULL, %s)
                        """, (consommable_id, site, atelier, quantite))
                    nb_stock_created += 1
                    
            except Exception as e:
                errors.append(f"Ligne {idx+1}: {str(e)}")
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return True, f"✅ Import terminé : {nb_refs_created} références créées, {nb_stock_created} stocks importés", errors
    except Exception as e:
        if 'conn' in locals():
            conn.rollback()
        return False, f"❌ Erreur import : {str(e)}", []

# ==========================================
# KPIs
# ==========================================

kpis = get_kpis_consommables()

if kpis:
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("📋 Références", kpis['nb_refs'])
    with col2:
        # Format français : espace pour milliers, 2 décimales
        valeur_str = f"{kpis['valeur_totale']:,.2f}".replace(",", " ")
        st.metric("💰 Valeur Stock", f"{valeur_str} €")
    with col3:
        st.metric("📍 Emplacements", kpis['nb_emplacements'])
    with col4:
        if kpis['nb_alertes'] > 0:
            st.metric("⚠️ Alertes Stock", kpis['nb_alertes'], delta=f"-{kpis['nb_alertes']}", delta_color="inverse")
        else:
            st.metric("✅ Alertes Stock", 0)

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
    
    sites, ateliers = get_sites_ateliers()
    
    col1, col2, col3 = st.columns(3)
    with col1:
        site_filter = st.selectbox("Site", ["Tous"] + sites, key="filter_site")
    with col2:
        atelier_filter = st.selectbox("Atelier", ["Tous"] + ateliers, key="filter_atelier")
    with col3:
        if st.button("🔄 Actualiser", key="btn_refresh_stock"):
            st.rerun()
    
    df_stock = get_stock_consommables(site_filter, atelier_filter)
    
    if not df_stock.empty:
        # Renommer colonnes
        df_display = df_stock.rename(columns={
            'code_consommable': 'Code',
            'libelle': 'Libellé',
            'site': 'Site',
            'atelier': 'Atelier',
            'emplacement': 'Emplacement',
            'quantite': 'Quantité',
            'unite_inventaire': 'Unité',
            'prix_unitaire': 'Prix Unit.',
            'valeur': 'Valeur €',
            'alerte': 'Alerte'
        })
        
        # Afficher avec mise en forme
        st.dataframe(
            df_display[['Code', 'Libellé', 'Site', 'Atelier', 'Emplacement', 'Quantité', 'Unité', 'Prix Unit.', 'Valeur €']],
            use_container_width=True,
            hide_index=True
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
        st.info("📭 Aucun stock trouvé. Utilisez l'onglet **Import** pour charger les données initiales.")

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
            emplacement = st.text_input("Emplacement", key="entree_emplacement", placeholder="Ex: A1, B2...")
        
        with col2:
            quantite = st.number_input("Quantité *", min_value=1, value=1, key="entree_qte")
            fournisseur = st.text_input("Fournisseur", key="entree_fournisseur")
            reference_bl = st.text_input("N° BL / Référence", key="entree_bl")
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
        st.warning("⚠️ Aucun consommable dans le référentiel. Créez-en d'abord dans l'onglet **Référentiel** ou importez via **Import**.")

# ==========================================
# ONGLET 3: AJUSTEMENT
# ==========================================

with tab3:
    st.subheader("🔧 Ajustement de Stock")
    
    df_stock_ajust = get_stock_consommables()
    
    if not df_stock_ajust.empty:
        # Sélection de l'emplacement à ajuster
        options = []
        for _, row in df_stock_ajust.iterrows():
            loc = f"{row['site']}"
            if row['atelier']:
                loc += f" / {row['atelier']}"
            if row['emplacement']:
                loc += f" / {row['emplacement']}"
            options.append(f"{row['libelle']} - {loc} (Qté: {row['quantite']})")
        
        selected = st.selectbox("Sélectionner l'emplacement à ajuster", options, key="ajust_select")
        idx = options.index(selected)
        row_selected = df_stock_ajust.iloc[idx]
        
        col1, col2 = st.columns(2)
        with col1:
            st.info(f"**Stock actuel** : {row_selected['quantite']} {row_selected['unite_inventaire']}")
            nouvelle_qte = st.number_input("Nouvelle quantité", min_value=0, 
                                           value=int(row_selected['quantite']), key="ajust_qte")
        with col2:
            motif = st.text_area("Motif de l'ajustement *", key="ajust_motif", 
                                placeholder="Ex: Erreur de comptage, casse...")
        
        ecart = nouvelle_qte - row_selected['quantite']
        if ecart != 0:
            st.warning(f"📊 Écart : {'+' if ecart > 0 else ''}{ecart} unités")
        
        if st.button("✅ Valider l'ajustement", type="primary", use_container_width=True, key="btn_ajust"):
            if not motif:
                st.error("❌ Le motif est obligatoire")
            else:
                # Récupérer consommable_id
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
    
    # Vérifier si admin
    is_admin = st.session_state.get('role') == 'ADMIN'
    
    df_ref = get_referentiel_consommables()
    
    if not df_ref.empty:
        df_ref_display = df_ref.rename(columns={
            'code_consommable': 'Code',
            'libelle': 'Libellé',
            'unite_inventaire': 'Unité',
            'fournisseur_principal': 'Fournisseur',
            'prix_unitaire': 'Prix (€)',
            'seuil_alerte': 'Seuil Alerte',
            'is_active': 'Actif'
        })
        
        st.dataframe(df_ref_display[['Code', 'Libellé', 'Unité', 'Fournisseur', 'Prix (€)', 'Seuil Alerte', 'Actif']],
                    use_container_width=True, hide_index=True)
        
        st.info(f"**{len(df_ref)} référence(s)** dans le catalogue")
    
    # Formulaire ajout/modification (Admin only)
    if is_admin:
        st.markdown("---")
        st.markdown("### ➕ Ajouter / Modifier une référence")
        
        col1, col2 = st.columns(2)
        with col1:
            code = st.text_input("Code *", key="ref_code", placeholder="Ex: BOBINE_FILET_5KG")
            libelle = st.text_input("Libellé *", key="ref_libelle")
            unite = st.selectbox("Unité", ["Unité", "Bobines", "Poches", "Palettes", "Rouleaux", "Cartons", "ML"], key="ref_unite")
        with col2:
            fournisseur = st.text_input("Fournisseur principal", key="ref_fournisseur")
            prix = st.number_input("Prix unitaire (€)", min_value=0.0, value=0.0, step=0.01, key="ref_prix")
            seuil = st.number_input("Seuil alerte", min_value=0, value=0, key="ref_seuil")
        
        if st.button("💾 Enregistrer", type="primary", use_container_width=True, key="btn_save_ref"):
            if not code or not libelle:
                st.error("❌ Code et Libellé sont obligatoires")
            else:
                data = {
                    'code_consommable': code.upper().replace(' ', '_'),
                    'libelle': libelle,
                    'unite_inventaire': unite,
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
    **Format attendu du fichier Excel :**
    | Site | Atelier | Reference | Quantite | Unite | Prix | Fournisseur |
    |------|---------|-----------|----------|-------|------|-------------|
    | St Flavy | COMMUN | Palette 100*120 | 975 | Unité | 7.5 | TVE |
    """)
    
    uploaded_file = st.file_uploader("Choisir un fichier Excel", type=['xlsx', 'xls'], key="upload_conso")
    
    if uploaded_file:
        try:
            # Lire le fichier avec header ligne 0 (format standard)
            df_upload = pd.read_excel(uploaded_file, header=0)
            
            # Vérifier les colonnes requises
            colonnes_requises = ['Site', 'Atelier', 'Reference', 'Quantite']
            colonnes_presentes = [col for col in colonnes_requises if col in df_upload.columns]
            
            if len(colonnes_presentes) < 4:
                st.error(f"❌ Colonnes manquantes. Trouvées: {list(df_upload.columns)}")
                st.info("Le fichier doit contenir au minimum : Site, Atelier, Reference, Quantite")
            else:
                # Filtrer lignes valides (avec Site non vide)
                df_clean = df_upload[df_upload['Site'].notna() & 
                                     ~df_upload['Site'].astype(str).str.contains('Total|TOTAL', na=False)].copy()
                
                # Préparer pour import
                df_import = df_clean[['Site', 'Atelier', 'Reference', 'Quantite']].copy()
                df_import['Quantite'] = pd.to_numeric(df_import['Quantite'], errors='coerce').fillna(0).astype(int)
                
                # Ajouter colonnes optionnelles si présentes
                if 'Unite' in df_upload.columns:
                    df_import['Unite'] = df_clean['Unite'].fillna('Unité')
                else:
                    df_import['Unite'] = 'Unité'
                    
                if 'Prix' in df_upload.columns:
                    df_import['Prix'] = pd.to_numeric(df_clean['Prix'], errors='coerce').fillna(0)
                else:
                    df_import['Prix'] = 0
                    
                if 'Fournisseur' in df_upload.columns:
                    df_import['Fournisseur'] = df_clean['Fournisseur']
                else:
                    df_import['Fournisseur'] = None
                
                st.markdown("### Aperçu des données à importer")
                st.dataframe(df_import.head(20), use_container_width=True, hide_index=True)
                st.info(f"**{len(df_import)} lignes** détectées")
                
                if st.button("🚀 Lancer l'import", type="primary", use_container_width=True):
                    success, msg, errors = importer_stock_excel(df_import)
                    if success:
                        st.success(msg)
                        if errors:
                            with st.expander("⚠️ Avertissements"):
                                for err in errors[:20]:
                                    st.warning(err)
                        st.balloons()
                        st.rerun()
                    else:
                        st.error(msg)
                    
        except Exception as e:
            st.error(f"❌ Erreur lecture fichier : {str(e)}")
            st.info("Vérifiez que le fichier contient les colonnes : Site, Atelier, Reference, Quantite")

show_footer()
