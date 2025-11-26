import streamlit as st
import pandas as pd
from datetime import datetime, date
from database import get_connection
from components import show_footer
from auth import is_authenticated
from auth import has_permission, is_compteur
import io

st.set_page_config(page_title="Inventaire - Culture Pom", page_icon="📦", layout="wide")

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
    .ecart-positif { color: #2e7d32; font-weight: bold; }
    .ecart-negatif { color: #c62828; font-weight: bold; }
</style>
""", unsafe_allow_html=True)

# ============================================================
# ✅ VÉRIFICATIONS DE SÉCURITÉ
# ============================================================

# Vérification authentification
if not is_authenticated():
    st.warning("⚠️ Veuillez vous connecter pour accéder à cette page")
    st.stop()

# Vérification permission inventaire
if not has_permission('inventaire'):
    st.error("❌ Vous n'avez pas accès à cette page")
    st.info("🔒 Cette page nécessite les droits d'accès à l'inventaire")
    st.stop()

# Message pour le rôle COMPTEUR
if is_compteur():
    st.info("📋 Mode Compteur - Saisie Inventaire uniquement")

# ============================================================
# FIN VÉRIFICATIONS - RESTE DU CODE INCHANGÉ
# ============================================================

st.title("📋 Inventaire")
st.markdown("*Gestion des inventaires périodiques*")
st.markdown("---")

# ==========================================
# ONGLETS PRINCIPAUX PAR TYPE D'INVENTAIRE
# ==========================================

main_tab1, main_tab2 = st.tabs(["📦 Inventaire Consommables", "🥔 Inventaire Lots (à venir)"])

# ==========================================
# INVENTAIRE CONSOMMABLES
# ==========================================

with main_tab1:
    
    # ==========================================
    # FONCTIONS
    # ==========================================
    
    def get_kpis_inventaire_conso():
        """KPIs inventaires consommables"""
        try:
            conn = get_connection()
            cursor = conn.cursor()
            
            # Dernier inventaire validé
            cursor.execute("""
                SELECT date_inventaire, validated_at 
                FROM inventaires 
                WHERE type_inventaire = 'CONSOMMABLES' AND statut = 'VALIDE'
                ORDER BY date_inventaire DESC LIMIT 1
            """)
            dernier = cursor.fetchone()
            
            # Inventaire en cours
            cursor.execute("""
                SELECT COUNT(*) as nb 
                FROM inventaires 
                WHERE type_inventaire = 'CONSOMMABLES' AND statut = 'EN_COURS'
            """)
            en_cours = cursor.fetchone()['nb']
            
            # Total inventaires
            cursor.execute("""
                SELECT COUNT(*) as nb 
                FROM inventaires 
                WHERE type_inventaire = 'CONSOMMABLES' AND statut = 'VALIDE'
            """)
            total = cursor.fetchone()['nb']
            
            cursor.close()
            conn.close()
            
            return {
                'dernier': dernier['date_inventaire'] if dernier else None,
                'en_cours': en_cours,
                'total': total
            }
        except:
            return None
    
    def get_inventaires_liste(statut=None):
        """Liste des inventaires"""
        try:
            conn = get_connection()
            cursor = conn.cursor()
            
            query = """
                SELECT id, date_inventaire, mois, annee, site, statut,
                       compteur_1, compteur_2, validateur, nb_lignes, nb_ecarts,
                       valeur_ecart_total, created_at, validated_at
                FROM inventaires
                WHERE type_inventaire = 'CONSOMMABLES'
            """
            if statut:
                query += f" AND statut = '{statut}'"
            query += " ORDER BY date_inventaire DESC"
            
            cursor.execute(query)
            rows = cursor.fetchall()
            cursor.close()
            conn.close()
            
            return pd.DataFrame(rows) if rows else pd.DataFrame()
        except:
            return pd.DataFrame()
    
    def get_stock_pour_inventaire(site=None):
        """Récupère TOUTES les références pour inventaire (y compris stock = 0)"""
        try:
            conn = get_connection()
            cursor = conn.cursor()
            
            if site and site != "Tous":
                # Site spécifique : toutes les références avec leur stock sur ce site (ou 0)
                query = """
                    SELECT 
                        rc.id as consommable_id,
                        rc.code_consommable,
                        rc.libelle,
                        rc.unite_inventaire,
                        rc.prix_unitaire,
                        %s as site,
                        COALESCE(sc.atelier, 'COMMUN') as atelier,
                        sc.emplacement,
                        COALESCE(sc.quantite, 0) as stock_theorique
                    FROM ref_consommables rc
                    LEFT JOIN stock_consommables sc ON rc.id = sc.consommable_id 
                        AND sc.site = %s AND sc.is_active = TRUE
                    WHERE rc.is_active = TRUE
                    ORDER BY rc.libelle
                """
                cursor.execute(query, (site, site))
            else:
                # Tous sites : références avec stock + références sans aucun stock
                query = """
                    WITH refs_avec_stock AS (
                        SELECT 
                            rc.id as consommable_id,
                            rc.code_consommable,
                            rc.libelle,
                            rc.unite_inventaire,
                            rc.prix_unitaire,
                            sc.site,
                            sc.atelier,
                            sc.emplacement,
                            sc.quantite as stock_theorique
                        FROM ref_consommables rc
                        JOIN stock_consommables sc ON rc.id = sc.consommable_id AND sc.is_active = TRUE
                        WHERE rc.is_active = TRUE
                    ),
                    refs_sans_stock AS (
                        SELECT 
                            rc.id as consommable_id,
                            rc.code_consommable,
                            rc.libelle,
                            rc.unite_inventaire,
                            rc.prix_unitaire,
                            'St Flavy' as site,
                            'COMMUN' as atelier,
                            NULL::text as emplacement,
                            0 as stock_theorique
                        FROM ref_consommables rc
                        WHERE rc.is_active = TRUE
                          AND rc.id NOT IN (SELECT DISTINCT consommable_id FROM stock_consommables WHERE is_active = TRUE)
                    )
                    SELECT * FROM refs_avec_stock
                    UNION ALL
                    SELECT * FROM refs_sans_stock
                    ORDER BY site, atelier, libelle
                """
                cursor.execute(query)
            
            rows = cursor.fetchall()
            cursor.close()
            conn.close()
            
            return pd.DataFrame(rows) if rows else pd.DataFrame()
        except Exception as e:
            st.error(f"❌ Erreur : {str(e)}")
            return pd.DataFrame()
    
    def creer_inventaire(date_inv, site, compteur_1, compteur_2, mois, annee):
        """Crée un inventaire et ses lignes"""
        try:
            conn = get_connection()
            cursor = conn.cursor()
            
            # Créer inventaire
            created_by = st.session_state.get('username', 'system')
            cursor.execute("""
                INSERT INTO inventaires (type_inventaire, date_inventaire, mois, annee, site, 
                                        statut, compteur_1, compteur_2, created_by)
                VALUES ('CONSOMMABLES', %s, %s, %s, %s, 'EN_COURS', %s, %s, %s)
                RETURNING id
            """, (date_inv, mois, annee, site if site != "Tous" else None, compteur_1, compteur_2, created_by))
            
            inv_id = cursor.fetchone()['id']
            
            # Charger références stock
            df_stock = get_stock_pour_inventaire(site if site != "Tous" else None)
            
            if df_stock.empty:
                conn.rollback()
                return False, "❌ Aucune référence trouvée pour l'inventaire"
            
            # Insérer lignes
            for _, row in df_stock.iterrows():
                cursor.execute("""
                    INSERT INTO inventaires_lignes (inventaire_id, consommable_id, site, atelier, 
                                                   emplacement, stock_theorique, prix_unitaire)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (inv_id, row['consommable_id'], row['site'], row['atelier'], 
                     row['emplacement'], row['stock_theorique'], row['prix_unitaire']))
            
            # Mettre à jour nb_lignes
            cursor.execute("UPDATE inventaires SET nb_lignes = %s WHERE id = %s", (len(df_stock), inv_id))
            
            conn.commit()
            cursor.close()
            conn.close()
            
            return True, f"✅ Inventaire #{inv_id} créé avec {len(df_stock)} références"
        except Exception as e:
            if 'conn' in locals():
                conn.rollback()
            return False, f"❌ Erreur : {str(e)}"
    
    def get_lignes_inventaire(inventaire_id):
        """Récupère les lignes d'un inventaire avec détails consommable"""
        try:
            conn = get_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT 
                    il.id,
                    rc.code_consommable,
                    rc.libelle,
                    rc.unite_inventaire,
                    il.site,
                    il.atelier,
                    il.emplacement,
                    il.stock_theorique,
                    il.stock_compte,
                    il.ecart,
                    il.prix_unitaire,
                    il.ecart_valeur
                FROM inventaires_lignes il
                JOIN ref_consommables rc ON il.consommable_id = rc.id
                WHERE il.inventaire_id = %s
                ORDER BY rc.libelle
            """, (inventaire_id,))
            
            rows = cursor.fetchall()
            cursor.close()
            conn.close()
            
            if rows:
                df = pd.DataFrame(rows)
                # Conversion types numériques
                for col in ['stock_theorique', 'stock_compte', 'ecart', 'prix_unitaire', 'ecart_valeur']:
                    if col in df.columns:
                        df[col] = pd.to_numeric(df[col], errors='coerce')
                return df
            return pd.DataFrame()
        except:
            return pd.DataFrame()
    
    def sauvegarder_comptages(inventaire_id, df_modif):
        """Sauvegarde les comptages et calcule les écarts"""
        try:
            conn = get_connection()
            cursor = conn.cursor()
            
            nb_updates = 0
            
            for idx, row in df_modif.iterrows():
                ligne_id = row['id']
                stock_compte = row['stock_compte']
                
                if pd.notna(stock_compte):
                    stock_theo = row['stock_theorique']
                    ecart = stock_compte - stock_theo
                    prix_unit = row['prix_unitaire']
                    ecart_valeur = ecart * prix_unit
                    
                    cursor.execute("""
                        UPDATE inventaires_lignes
                        SET stock_compte = %s, ecart = %s, ecart_valeur = %s
                        WHERE id = %s
                    """, (stock_compte, ecart, ecart_valeur, ligne_id))
                    nb_updates += 1
            
            # Recalculer les totaux de l'inventaire
            cursor.execute("""
                UPDATE inventaires
                SET nb_ecarts = (
                    SELECT COUNT(*) FROM inventaires_lignes 
                    WHERE inventaire_id = %s AND ecart != 0 AND ecart IS NOT NULL
                ),
                valeur_ecart_total = (
                    SELECT COALESCE(SUM(ABS(ecart_valeur)), 0) 
                    FROM inventaires_lignes 
                    WHERE inventaire_id = %s AND ecart_valeur IS NOT NULL
                )
                WHERE id = %s
            """, (inventaire_id, inventaire_id, inventaire_id))
            
            conn.commit()
            cursor.close()
            conn.close()
            
            return True, f"✅ {nb_updates} comptage(s) sauvegardé(s)"
        except Exception as e:
            if 'conn' in locals():
                conn.rollback()
            return False, f"❌ Erreur : {str(e)}"
    
    def valider_inventaire(inventaire_id, validateur):
        """Valide l'inventaire et met à jour le stock réel"""
        try:
            conn = get_connection()
            cursor = conn.cursor()
            
            # Récupérer les lignes avec écarts
            cursor.execute("""
                SELECT consommable_id, site, atelier, emplacement, stock_compte, ecart
                FROM inventaires_lignes
                WHERE inventaire_id = %s AND ecart IS NOT NULL
            """, (inventaire_id,))
            
            lignes = cursor.fetchall()
            
            # Mettre à jour le stock pour chaque ligne
            for ligne in lignes:
                # Chercher la ligne de stock correspondante
                cursor.execute("""
                    SELECT id FROM stock_consommables
                    WHERE consommable_id = %s AND site = %s AND atelier = %s 
                      AND (emplacement = %s OR (emplacement IS NULL AND %s IS NULL))
                      AND is_active = TRUE
                """, (ligne['consommable_id'], ligne['site'], ligne['atelier'], 
                     ligne['emplacement'], ligne['emplacement']))
                
                stock_existant = cursor.fetchone()
                
                if stock_existant:
                    # Mettre à jour
                    cursor.execute("""
                        UPDATE stock_consommables
                        SET quantite = %s, updated_at = CURRENT_TIMESTAMP
                        WHERE id = %s
                    """, (ligne['stock_compte'], stock_existant['id']))
                else:
                    # Créer nouvelle ligne si stock_compte > 0
                    if ligne['stock_compte'] > 0:
                        cursor.execute("""
                            INSERT INTO stock_consommables 
                            (consommable_id, site, atelier, emplacement, quantite, is_active)
                            VALUES (%s, %s, %s, %s, %s, TRUE)
                        """, (ligne['consommable_id'], ligne['site'], ligne['atelier'], 
                             ligne['emplacement'], ligne['stock_compte']))
            
            # Valider l'inventaire
            cursor.execute("""
                UPDATE inventaires
                SET statut = 'VALIDE', validateur = %s, validated_at = CURRENT_TIMESTAMP
                WHERE id = %s
            """, (validateur, inventaire_id))
            
            conn.commit()
            cursor.close()
            conn.close()
            
            return True, f"✅ Inventaire validé - Stock mis à jour pour {len(lignes)} ligne(s)"
        except Exception as e:
            if 'conn' in locals():
                conn.rollback()
            return False, f"❌ Erreur : {str(e)}"
    
    def supprimer_inventaire(inventaire_id):
        """Supprime un inventaire EN_COURS et ses lignes"""
        try:
            conn = get_connection()
            cursor = conn.cursor()
            
            # Vérifier statut
            cursor.execute("SELECT statut FROM inventaires WHERE id = %s", (inventaire_id,))
            result = cursor.fetchone()
            
            if not result:
                return False, "❌ Inventaire introuvable"
            
            if result['statut'] != 'EN_COURS':
                return False, "❌ Seuls les inventaires EN_COURS peuvent être supprimés"
            
            # Supprimer lignes puis inventaire
            cursor.execute("DELETE FROM inventaires_lignes WHERE inventaire_id = %s", (inventaire_id,))
            cursor.execute("DELETE FROM inventaires WHERE id = %s", (inventaire_id,))
            
            conn.commit()
            cursor.close()
            conn.close()
            
            return True, f"✅ Inventaire #{inventaire_id} supprimé"
        except Exception as e:
            if 'conn' in locals():
                conn.rollback()
            return False, f"❌ Erreur : {str(e)}"
    
    # ==========================================
    # INTERFACE - KPIs
    # ==========================================
    
    kpis = get_kpis_inventaire_conso()
    
    if kpis:
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("📅 Dernier inventaire", kpis['dernier'] or "Aucun")
        with col2:
            st.metric("🔄 En cours", kpis['en_cours'])
        with col3:
            st.metric("✅ Total validés", kpis['total'])
    
    st.markdown("---")
    
    # ==========================================
    # ONGLETS
    # ==========================================
    
    tab1, tab2, tab3, tab4, tab5 = st.tabs(["➕ Créer", "📝 Saisir", "✅ Valider", "📜 Historique", "🗑️ Gérer"])
    
    # ==========================================
    # ONGLET CRÉER
    # ==========================================
    
    with tab1:
        st.subheader("➕ Créer un nouvel inventaire")
        
        col1, col2 = st.columns(2)
        
        with col1:
            date_inv = st.date_input("Date de l'inventaire *", value=date.today(), key="date_inv")
            
            sites = ["Tous", "St Flavy", "Morette", "Ste Livrade"]
            site_sel = st.selectbox("Site *", sites, key="site_inv")
        
        with col2:
            mois = date_inv.month
            annee = date_inv.year
            
            st.text_input("Mois", value=f"{mois:02d}", disabled=True)
            st.text_input("Année", value=str(annee), disabled=True)
        
        st.markdown("---")
        
        compteur_1 = st.text_input("Nom compteur 1 *", key="compteur1")
        compteur_2 = st.text_input("Nom compteur 2 (optionnel)", key="compteur2")
        
        st.markdown("---")
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("✅ Créer l'inventaire", type="primary", use_container_width=True):
                if not compteur_1:
                    st.error("❌ Le nom du compteur 1 est obligatoire")
                else:
                    success, msg = creer_inventaire(date_inv, site_sel, compteur_1, 
                                                    compteur_2 if compteur_2 else None, mois, annee)
                    if success:
                        st.success(msg)
                        st.balloons()
                    else:
                        st.error(msg)
        
        with col2:
            st.button("↩️ Réinitialiser", use_container_width=True, disabled=True)
    
    # ==========================================
    # ONGLET SAISIR
    # ==========================================
    
    with tab2:
        st.subheader("📝 Saisir les comptages")
        
        # Charger inventaires en cours
        df_en_cours = get_inventaires_liste('EN_COURS')
        
        if not df_en_cours.empty:
            # Sélection inventaire
            options_inv = [f"#{row['id']} - {row['date_inventaire']} - {row['site'] or 'Tous sites'} - {row['compteur_1']}" 
                          for _, row in df_en_cours.iterrows()]
            
            selected_inv = st.selectbox("Sélectionner l'inventaire", options_inv, key="saisie_inv_select")
            inv_id = int(selected_inv.split('#')[1].split(' ')[0])
            
            # Charger lignes
            df_lignes = get_lignes_inventaire(inv_id)
            
            if not df_lignes.empty:
                # Préparer pour affichage
                df_saisie = df_lignes.copy()
                df_saisie['stock_compte'] = df_saisie['stock_compte'].fillna('')
                
                df_saisie_display = df_saisie[['id', 'libelle', 'site', 'atelier', 'emplacement', 
                                               'unite_inventaire', 'stock_theorique', 'stock_compte']].copy()
                df_saisie_display.columns = ['id', 'Consommable', 'Site', 'Atelier', 'Emplacement', 
                                             'Unité', 'Stock Théo.', 'Stock Compté']
                
                st.info(f"📦 {len(df_lignes)} références à compter")
                
                # Filtres
                col_f1, col_f2 = st.columns(2)
                with col_f1:
                    sites_uniques = ['Tous'] + sorted(df_saisie_display['Site'].unique().tolist())
                    filtre_site = st.selectbox("Filtrer par site", sites_uniques, key="filtre_site_saisie")
                
                with col_f2:
                    ateliers_uniques = ['Tous'] + sorted(df_saisie_display['Atelier'].dropna().unique().tolist())
                    filtre_atelier = st.selectbox("Filtrer par atelier", ateliers_uniques, key="filtre_atelier_saisie")
                
                # Appliquer filtres
                df_filtre = df_saisie_display.copy()
                if filtre_site != 'Tous':
                    df_filtre = df_filtre[df_filtre['Site'] == filtre_site]
                if filtre_atelier != 'Tous':
                    df_filtre = df_filtre[df_filtre['Atelier'] == filtre_atelier]
                
                st.markdown("---")
                
                # Tableau éditable
                edited_df = st.data_editor(
                    df_filtre,
                    column_config={
                        "id": None,
                        "Stock Compté": st.column_config.NumberColumn("Stock Compté", min_value=0, step=1)
                    },
                    use_container_width=True,
                    hide_index=True,
                    disabled=['Consommable', 'Site', 'Atelier', 'Emplacement', 'Unité', 'Stock Théo.'],
                    key=f"editor_saisie_{inv_id}"
                )
                
                # Bouton sauvegarder
                if st.button("💾 Sauvegarder les comptages", type="primary", use_container_width=True):
                    # Fusionner avec données complètes
                    df_complet = df_saisie.copy()
                    for idx, row in edited_df.iterrows():
                        ligne_id = row['id']
                        stock_compte_saisie = row['Stock Compté']
                        
                        if stock_compte_saisie != '':
                            df_complet.loc[df_complet['id'] == ligne_id, 'stock_compte'] = float(stock_compte_saisie)
                    
                    success, msg = sauvegarder_comptages(inv_id, df_complet)
                    if success:
                        st.success(msg)
                        st.rerun()
                    else:
                        st.error(msg)
                
                # Export feuille de comptage vierge
                st.markdown("---")
                buffer = io.BytesIO()
                df_export = df_saisie.drop(columns=['id', 'stock_compte'])
                df_export['stock_compte'] = ''
                with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                    df_export.to_excel(writer, index=False, sheet_name='Comptage')
                st.download_button("📄 Exporter feuille de comptage", buffer.getvalue(),
                                  f"feuille_comptage_{inv_id}.xlsx", use_container_width=True)
        else:
            st.info("📭 Aucun inventaire en cours. Créez-en un dans l'onglet **Créer**.")
    
    # ==========================================
    # ONGLET VALIDER
    # ==========================================
    
    with tab3:
        st.subheader("✅ Valider l'inventaire")
        
        df_en_cours = get_inventaires_liste('EN_COURS')
        
        if not df_en_cours.empty:
            options_inv = [f"#{row['id']} - {row['date_inventaire']} - {row['site'] or 'Tous sites'}" 
                          for _, row in df_en_cours.iterrows()]
            
            selected_inv = st.selectbox("Sélectionner l'inventaire à valider", options_inv, key="valid_inv_select")
            inv_id = int(selected_inv.split('#')[1].split(' ')[0])
            
            # Charger les lignes avec écarts
            df_lignes = get_lignes_inventaire(inv_id)
            
            if not df_lignes.empty:
                # Calculer stats
                nb_comptees = df_lignes['stock_compte'].notna().sum()
                nb_total = len(df_lignes)
                
                if nb_comptees < nb_total:
                    st.warning(f"⚠️ Comptage incomplet : {nb_comptees}/{nb_total} lignes saisies")
                
                # Afficher les écarts
                df_ecarts = df_lignes[df_lignes['ecart'].notna() & (df_lignes['ecart'] != 0)].copy()
                
                if not df_ecarts.empty:
                    st.markdown("### 📊 Écarts détectés")
                    
                    df_ecarts_display = df_ecarts[['libelle', 'site', 'atelier', 'stock_theorique', 
                                                   'stock_compte', 'ecart', 'ecart_valeur']].copy()
                    df_ecarts_display.columns = ['Consommable', 'Site', 'Atelier', 'Théorique', 
                                                'Compté', 'Écart', 'Valeur €']
                    
                    st.dataframe(df_ecarts_display, use_container_width=True, hide_index=True)
                    
                    total_ecart_valeur = df_ecarts['ecart_valeur'].abs().sum()
                    st.warning(f"**{len(df_ecarts)} écart(s)** - Valeur totale : **{total_ecart_valeur:,.2f} €**")
                else:
                    st.success("✅ Aucun écart détecté !")
                
                st.markdown("---")
                
                # Validation
                validateur = st.text_input("Nom du validateur *", key="validateur_nom")
                
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("✅ Valider et mettre à jour le stock", type="primary", use_container_width=True):
                        if not validateur:
                            st.error("❌ Le nom du validateur est obligatoire")
                        elif nb_comptees == 0:
                            st.error("❌ Aucune ligne n'a été comptée")
                        else:
                            success, msg = valider_inventaire(inv_id, validateur)
                            if success:
                                st.success(msg)
                                st.balloons()
                            else:
                                st.error(msg)
                
                with col2:
                    if st.button("❌ Annuler l'inventaire", type="secondary", use_container_width=True):
                        try:
                            conn = get_connection()
                            cursor = conn.cursor()
                            cursor.execute("UPDATE inventaires SET statut = 'ANNULE' WHERE id = %s", (inv_id,))
                            conn.commit()
                            cursor.close()
                            conn.close()
                            st.success("✅ Inventaire annulé")
                            st.rerun()
                        except Exception as e:
                            st.error(f"❌ Erreur : {str(e)}")
        else:
            st.info("📭 Aucun inventaire en cours à valider")
    
    # ==========================================
    # ONGLET HISTORIQUE
    # ==========================================
    
    with tab4:
        st.subheader("📜 Historique des inventaires")
        
        df_historique = get_inventaires_liste()
        
        if not df_historique.empty:
            df_hist_display = df_historique[['id', 'date_inventaire', 'site', 'statut', 
                                             'compteur_1', 'compteur_2', 'validateur',
                                             'nb_lignes', 'nb_ecarts', 'valeur_ecart_total']].copy()
            df_hist_display.columns = ['ID', 'Date', 'Site', 'Statut', 'Compteur 1', 'Compteur 2',
                                       'Validateur', 'Nb Lignes', 'Nb Écarts', 'Valeur Écarts €']
            
            st.dataframe(df_hist_display, use_container_width=True, hide_index=True)
            
            # Stats
            nb_valides = len(df_historique[df_historique['statut'] == 'VALIDE'])
            total_ecarts = df_historique[df_historique['statut'] == 'VALIDE']['nb_ecarts'].sum()
            
            st.info(f"**{nb_valides} inventaire(s) validé(s)** - Total écarts historiques : {total_ecarts}")
            
            # Export
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                df_hist_display.to_excel(writer, index=False, sheet_name='Historique')
            st.download_button("📥 Exporter l'historique", buffer.getvalue(),
                              f"historique_inventaires_{datetime.now().strftime('%Y%m%d')}.xlsx",
                              use_container_width=True)
        else:
            st.info("📭 Aucun inventaire dans l'historique")
    
    # ==========================================
    # ONGLET GÉRER (SUPPRIMER)
    # ==========================================
    
    with tab5:
        st.subheader("🗑️ Gérer les inventaires")
        st.markdown("*Supprimer un inventaire en cours (non validé)*")
        
        # Liste des inventaires en cours uniquement
        df_a_supprimer = get_inventaires_liste('EN_COURS')
        
        if not df_a_supprimer.empty:
            st.warning("⚠️ **Attention** : La suppression est définitive et irréversible.")
            
            st.markdown("---")
            st.markdown("**Inventaires en cours :**")
            
            # Afficher les inventaires en cours
            df_display_sup = df_a_supprimer[['id', 'date_inventaire', 'site', 'compteur_1', 'compteur_2', 'nb_lignes']].copy()
            df_display_sup.columns = ['ID', 'Date', 'Site', 'Compteur 1', 'Compteur 2', 'Nb Lignes']
            
            st.dataframe(df_display_sup, use_container_width=True, hide_index=True)
            
            st.markdown("---")
            
            # Sélection et suppression
            options_sup = [f"#{row['id']} - {row['date_inventaire']} - {row['site'] or 'Tous sites'}" 
                          for _, row in df_a_supprimer.iterrows()]
            
            selected_sup = st.selectbox("Sélectionner l'inventaire à supprimer", options_sup, key="sup_inv_select")
            inv_id_sup = int(selected_sup.split('#')[1].split(' ')[0])
            
            # Confirmation
            confirm = st.checkbox("✅ Je confirme vouloir supprimer cet inventaire", key="confirm_delete")
            
            col1, col2 = st.columns(2)
            with col1:
                if st.button("🗑️ Supprimer l'inventaire", type="primary", use_container_width=True, 
                            disabled=not confirm):
                    success, msg = supprimer_inventaire(inv_id_sup)
                    if success:
                        st.success(msg)
                        st.rerun()
                    else:
                        st.error(msg)
            
            with col2:
                st.button("↩️ Annuler", use_container_width=True, disabled=True)
        else:
            st.info("📭 Aucun inventaire en cours à gérer")
            st.markdown("*Seuls les inventaires avec le statut EN_COURS peuvent être supprimés.*")

# ==========================================
# INVENTAIRE LOTS (À VENIR)
# ==========================================

with main_tab2:
    st.info("🚧 **Module en cours de développement**\n\nL'inventaire des lots bruts sera disponible prochainement.")

show_footer()
