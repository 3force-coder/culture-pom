import streamlit as st
import pandas as pd
from datetime import datetime, date
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
    .ecart-positif { color: #2e7d32; font-weight: bold; }
    .ecart-negatif { color: #c62828; font-weight: bold; }
</style>
""", unsafe_allow_html=True)

if not is_authenticated():
    st.warning("⚠️ Veuillez vous connecter pour accéder à cette page")
    st.stop()

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
    
    def creer_inventaire(date_inv, site, compteur_1, compteur_2, user):
        """Crée un nouvel inventaire avec ses lignes"""
        try:
            conn = get_connection()
            cursor = conn.cursor()
            
            mois = date_inv.month
            annee = date_inv.year
            
            # Créer en-tête
            cursor.execute("""
                INSERT INTO inventaires (type_inventaire, date_inventaire, mois, annee, site,
                                        compteur_1, compteur_2, created_by)
                VALUES ('CONSOMMABLES', %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
            """, (date_inv, mois, annee, site if site != "Tous" else None, compteur_1, compteur_2, user))
            
            inventaire_id = cursor.fetchone()['id']
            
            # Récupérer stock et créer lignes
            df_stock = get_stock_pour_inventaire(site)
            nb_lignes = 0
            
            for _, row in df_stock.iterrows():
                # ⭐ Convertir types pandas en types Python natifs
                consommable_id = int(row['consommable_id'])
                stock_theorique = int(row['stock_theorique']) if pd.notna(row['stock_theorique']) else 0
                
                cursor.execute("""
                    INSERT INTO inventaires_consommables_lignes 
                    (inventaire_id, consommable_id, site, atelier, emplacement, stock_theorique)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, (inventaire_id, consommable_id, row['site'], row['atelier'], 
                      row['emplacement'], stock_theorique))
                nb_lignes += 1
            
            # Mettre à jour nb_lignes
            cursor.execute("UPDATE inventaires SET nb_lignes = %s WHERE id = %s", (nb_lignes, inventaire_id))
            
            conn.commit()
            cursor.close()
            conn.close()
            
            return True, f"✅ Inventaire #{inventaire_id} créé avec {nb_lignes} lignes"
        except Exception as e:
            if 'conn' in locals():
                conn.rollback()
            return False, f"❌ Erreur : {str(e)}"
    
    def get_lignes_inventaire(inventaire_id):
        """Récupère les lignes d'un inventaire"""
        try:
            conn = get_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT 
                    icl.id,
                    icl.consommable_id,
                    rc.code_consommable,
                    rc.libelle,
                    rc.unite_inventaire,
                    rc.prix_unitaire,
                    icl.site,
                    icl.atelier,
                    icl.emplacement,
                    icl.stock_theorique,
                    icl.stock_compte,
                    icl.ecart,
                    icl.ecart_valeur
                FROM inventaires_consommables_lignes icl
                JOIN ref_consommables rc ON icl.consommable_id = rc.id
                WHERE icl.inventaire_id = %s
                ORDER BY icl.site, icl.atelier, rc.libelle
            """, (inventaire_id,))
            
            rows = cursor.fetchall()
            cursor.close()
            conn.close()
            
            return pd.DataFrame(rows) if rows else pd.DataFrame()
        except:
            return pd.DataFrame()
    
    def sauvegarder_comptage(inventaire_id, lignes_comptees):
        """Sauvegarde le comptage"""
        try:
            conn = get_connection()
            cursor = conn.cursor()
            
            for ligne_id, stock_compte in lignes_comptees.items():
                if stock_compte is not None:
                    # ⭐ Convertir types Python natifs
                    ligne_id = int(ligne_id)
                    stock_compte = int(stock_compte)
                    
                    # Récupérer stock théorique et prix
                    cursor.execute("""
                        SELECT icl.stock_theorique, rc.prix_unitaire
                        FROM inventaires_consommables_lignes icl
                        JOIN ref_consommables rc ON icl.consommable_id = rc.id
                        WHERE icl.id = %s
                    """, (ligne_id,))
                    row = cursor.fetchone()
                    
                    if row:
                        stock_theo = int(row['stock_theorique']) if pd.notna(row['stock_theorique']) else 0
                        prix_unitaire = float(row['prix_unitaire']) if pd.notna(row['prix_unitaire']) else 0.0
                        
                        ecart = stock_compte - stock_theo
                        ecart_valeur = ecart * prix_unitaire
                        
                        cursor.execute("""
                            UPDATE inventaires_consommables_lignes
                            SET stock_compte = %s, ecart = %s, ecart_valeur = %s, updated_at = CURRENT_TIMESTAMP
                            WHERE id = %s
                        """, (stock_compte, ecart, ecart_valeur, ligne_id))
            
            conn.commit()
            cursor.close()
            conn.close()
            
            return True, "✅ Comptage enregistré"
        except Exception as e:
            if 'conn' in locals():
                conn.rollback()
            return False, f"❌ Erreur : {str(e)}"
    
    def valider_inventaire(inventaire_id, validateur):
        """Valide l'inventaire et met à jour le stock"""
        try:
            conn = get_connection()
            cursor = conn.cursor()
            
            # Récupérer les lignes comptées
            cursor.execute("""
                SELECT icl.id, icl.consommable_id, icl.site, icl.atelier, icl.emplacement,
                       icl.stock_theorique, icl.stock_compte, icl.ecart
                FROM inventaires_consommables_lignes icl
                WHERE icl.inventaire_id = %s AND icl.stock_compte IS NOT NULL
            """, (inventaire_id,))
            lignes = cursor.fetchall()
            
            nb_ecarts = 0
            valeur_ecart_total = 0
            
            for ligne in lignes:
                if ligne['ecart'] != 0:
                    nb_ecarts += 1
                    
                    # Mettre à jour le stock réel
                    cursor.execute("""
                        UPDATE stock_consommables
                        SET quantite = %s, updated_at = CURRENT_TIMESTAMP
                        WHERE consommable_id = %s AND site = %s 
                          AND COALESCE(atelier, '') = COALESCE(%s, '')
                          AND COALESCE(emplacement, '') = COALESCE(%s, '')
                    """, (ligne['stock_compte'], ligne['consommable_id'], ligne['site'],
                          ligne['atelier'], ligne['emplacement']))
                    
                    # Créer mouvement d'inventaire
                    cursor.execute("""
                        INSERT INTO stock_consommables_mouvements
                        (consommable_id, type_mouvement, site, atelier, emplacement,
                         quantite_avant, quantite_apres, quantite_mouvement,
                         reference_document, created_by)
                        VALUES (%s, 'INVENTAIRE', %s, %s, %s, %s, %s, %s, %s, %s)
                    """, (ligne['consommable_id'], ligne['site'], ligne['atelier'], ligne['emplacement'],
                          ligne['stock_theorique'], ligne['stock_compte'], ligne['ecart'],
                          f"INV-{inventaire_id}", validateur))
            
            # Calculer valeur écart total
            cursor.execute("""
                SELECT COALESCE(SUM(ABS(ecart_valeur)), 0) as total
                FROM inventaires_consommables_lignes
                WHERE inventaire_id = %s
            """, (inventaire_id,))
            valeur_ecart_total = float(cursor.fetchone()['total'])
            
            # Valider l'inventaire
            cursor.execute("""
                UPDATE inventaires
                SET statut = 'VALIDE', validateur = %s, validated_at = CURRENT_TIMESTAMP,
                    nb_ecarts = %s, valeur_ecart_total = %s
                WHERE id = %s
            """, (validateur, nb_ecarts, valeur_ecart_total, inventaire_id))
            
            conn.commit()
            cursor.close()
            conn.close()
            
            return True, f"✅ Inventaire validé - {nb_ecarts} écart(s), valeur: {valeur_ecart_total:.2f}€"
        except Exception as e:
            if 'conn' in locals():
                conn.rollback()
            return False, f"❌ Erreur : {str(e)}"
    
    def supprimer_inventaire(inventaire_id):
        """Supprime un inventaire EN_COURS (et ses lignes)"""
        try:
            conn = get_connection()
            cursor = conn.cursor()
            
            # Vérifier que l'inventaire est bien EN_COURS
            cursor.execute("""
                SELECT statut FROM inventaires WHERE id = %s
            """, (inventaire_id,))
            result = cursor.fetchone()
            
            if not result:
                return False, "❌ Inventaire non trouvé"
            
            if result['statut'] != 'EN_COURS':
                return False, "❌ Seuls les inventaires EN_COURS peuvent être supprimés"
            
            # Supprimer les lignes (CASCADE devrait le faire, mais on le fait explicitement)
            cursor.execute("""
                DELETE FROM inventaires_consommables_lignes WHERE inventaire_id = %s
            """, (inventaire_id,))
            
            # Supprimer l'inventaire
            cursor.execute("""
                DELETE FROM inventaires WHERE id = %s
            """, (inventaire_id,))
            
            conn.commit()
            cursor.close()
            conn.close()
            
            return True, "✅ Inventaire supprimé avec succès"
        except Exception as e:
            if 'conn' in locals():
                conn.rollback()
            return False, f"❌ Erreur : {str(e)}"
    
    # ==========================================
    # KPIs
    # ==========================================
    
    kpis_inv = get_kpis_inventaire_conso()
    
    if kpis_inv:
        col1, col2, col3 = st.columns(3)
        with col1:
            if kpis_inv['dernier']:
                st.metric("📅 Dernier inventaire", kpis_inv['dernier'].strftime('%d/%m/%Y'))
            else:
                st.metric("📅 Dernier inventaire", "Aucun")
        with col2:
            st.metric("🔄 En cours", kpis_inv['en_cours'])
        with col3:
            st.metric("✅ Total validés", kpis_inv['total'])
    
    st.markdown("---")
    
    # ==========================================
    # SOUS-ONGLETS INVENTAIRE CONSOMMABLES
    # ==========================================
    
    tab1, tab2, tab3, tab4, tab5 = st.tabs(["➕ Créer", "📝 Saisir", "✅ Valider", "📜 Historique", "🗑️ Gérer"])
    
    # ==========================================
    # ONGLET CRÉER
    # ==========================================
    
    with tab1:
        st.subheader("➕ Créer un nouvel inventaire")
        
        col1, col2 = st.columns(2)
        
        with col1:
            date_inventaire = st.date_input("Date de l'inventaire *", value=date.today(), key="inv_date")
            site_inv = st.selectbox("Site", ["Tous", "St Flavy", "Corroy", "La Motte-Tilly"], key="inv_site")
        
        with col2:
            compteur_1 = st.text_input("Compteur 1 (nom) *", key="inv_compteur1", placeholder="Prénom NOM")
            compteur_2 = st.text_input("Compteur 2 (nom)", key="inv_compteur2", placeholder="Prénom NOM")
        
        # Aperçu du stock à inventorier
        st.markdown("---")
        st.markdown("**Aperçu des références à inventorier :**")
        
        df_apercu = get_stock_pour_inventaire(site_inv if site_inv != "Tous" else None)
        if not df_apercu.empty:
            nb_avec_stock = len(df_apercu[df_apercu['stock_theorique'] > 0])
            nb_sans_stock = len(df_apercu[df_apercu['stock_theorique'] == 0])
            st.info(f"**{len(df_apercu)} référence(s)** : {nb_avec_stock} avec stock, {nb_sans_stock} à zéro")
            st.dataframe(df_apercu[['site', 'atelier', 'libelle', 'stock_theorique', 'unite_inventaire']].head(15),
                        use_container_width=True, hide_index=True)
        else:
            st.warning("⚠️ Aucune référence à inventorier")
        
        if st.button("🚀 Créer l'inventaire", type="primary", use_container_width=True, disabled=df_apercu.empty):
            if not compteur_1:
                st.error("❌ Le compteur 1 est obligatoire")
            else:
                user = st.session_state.get('username', 'system')
                success, msg = creer_inventaire(date_inventaire, site_inv, compteur_1, compteur_2, user)
                if success:
                    st.success(msg)
                    st.balloons()
                else:
                    st.error(msg)
    
    # ==========================================
    # ONGLET SAISIR
    # ==========================================
    
    with tab2:
        st.subheader("📝 Saisir le comptage")
        
        # Liste des inventaires en cours
        df_en_cours = get_inventaires_liste('EN_COURS')
        
        if not df_en_cours.empty:
            options_inv = [f"#{row['id']} - {row['date_inventaire']} - {row['site'] or 'Tous sites'} ({row['compteur_1']})" 
                          for _, row in df_en_cours.iterrows()]
            
            selected_inv = st.selectbox("Sélectionner l'inventaire", options_inv, key="saisie_inv_select")
            inv_id = int(selected_inv.split('#')[1].split(' ')[0])
            
            # Charger les lignes
            df_lignes = get_lignes_inventaire(inv_id)
            
            if not df_lignes.empty:
                st.markdown("---")
                st.markdown("**Saisissez les quantités comptées :**")
                
                # Créer un formulaire de saisie avec data_editor
                # ⭐ RETIRER stock_theorique pour ne pas influencer le comptage
                df_saisie = df_lignes[['id', 'libelle', 'site', 'atelier', 'emplacement', 
                                       'stock_compte', 'unite_inventaire']].copy()
                df_saisie = df_saisie.rename(columns={
                    'libelle': 'Consommable',
                    'site': 'Site',
                    'atelier': 'Atelier',
                    'emplacement': 'Emplacement',
                    'stock_compte': 'Stock Compté',
                    'unite_inventaire': 'Unité'
                })
                
                edited_df = st.data_editor(
                    df_saisie,
                    column_config={
                        'id': None,  # Masquer
                        'Stock Compté': st.column_config.NumberColumn("Stock Compté", min_value=0, required=True),
                    },
                    use_container_width=True,
                    hide_index=True,
                    key="saisie_editor"
                )
                
                # Calculer écarts
                nb_saisis = edited_df['Stock Compté'].notna().sum()
                st.info(f"**{nb_saisis}/{len(df_saisie)}** lignes saisies")
                
                if st.button("💾 Enregistrer le comptage", type="primary", use_container_width=True):
                    lignes_comptees = {}
                    for idx, row in edited_df.iterrows():
                        if pd.notna(row['Stock Compté']):
                            ligne_id = df_lignes.iloc[idx]['id']
                            lignes_comptees[ligne_id] = int(row['Stock Compté'])
                    
                    success, msg = sauvegarder_comptage(inv_id, lignes_comptees)
                    if success:
                        st.success(msg)
                        st.rerun()
                    else:
                        st.error(msg)
                
                # Export feuille de comptage vierge
                st.markdown("---")
                buffer = io.BytesIO()
                df_export = df_saisie.drop(columns=['id', 'Stock Compté'])
                df_export['Stock Compté'] = ''
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
