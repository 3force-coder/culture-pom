"""
Page 11 - Inventaire Manager
Accès : ADMIN, USER (pas COMPTEUR)
Onglets : Créer, Valider, Historique, Gérer
"""

import streamlit as st
import pandas as pd
from datetime import datetime, date
from database import get_connection
from components import show_footer
from auth import is_authenticated, has_permission, is_compteur
import io

st.set_page_config(page_title="Inventaire - Culture Pom", page_icon="📦", layout="wide")

st.markdown("""
<style>
    .block-container { padding-top: 2rem !important; padding-bottom: 0.5rem !important; }
    h1, h2, h3, h4 { margin-top: 0.3rem !important; margin-bottom: 0.3rem !important; }
</style>
""", unsafe_allow_html=True)

# ============================================================
# SÉCURITÉ
# ============================================================

if not is_authenticated():
    st.warning("⚠️ Veuillez vous connecter")
    st.stop()

if not has_permission('inventaire'):
    st.error("❌ Vous n'avez pas accès à cette page")
    st.stop()

# COMPTEUR redirigé
if is_compteur():
    st.warning("📱 **Mode Compteur** - Accédez à la page **Saisie Inventaire**")
    st.info("👉 Menu latéral → **12 - Saisie Inventaire**")
    st.stop()

st.title("📋 Gestion des Inventaires")
st.markdown("*Création, validation et historique*")
st.markdown("---")

# ============================================================
# FONCTIONS
# ============================================================

def get_sites_disponibles():
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT site FROM stock_consommables WHERE is_active = TRUE AND site IS NOT NULL ORDER BY site")
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        return [row['site'] for row in rows] if rows else ["St Flavy"]
    except:
        return ["St Flavy"]

def get_kpis():
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT date_inventaire FROM inventaires WHERE type_inventaire = 'CONSOMMABLES' AND statut = 'VALIDE' ORDER BY date_inventaire DESC LIMIT 1")
        dernier = cursor.fetchone()
        
        cursor.execute("SELECT COUNT(*) as nb FROM inventaires WHERE type_inventaire = 'CONSOMMABLES' AND statut = 'EN_COURS'")
        en_cours = cursor.fetchone()['nb']
        
        cursor.execute("SELECT COUNT(*) as nb FROM inventaires WHERE type_inventaire = 'CONSOMMABLES' AND statut = 'VALIDE'")
        total = cursor.fetchone()['nb']
        
        cursor.close()
        conn.close()
        return {'dernier': dernier['date_inventaire'] if dernier else None, 'en_cours': en_cours, 'total': total}
    except:
        return None

def get_inventaires_liste(statut=None):
    try:
        conn = get_connection()
        cursor = conn.cursor()
        query = """
            SELECT id, date_inventaire, mois, annee, site, statut,
                   compteur_1, compteur_2, validateur, nb_lignes, nb_ecarts,
                   valeur_ecart_total, created_at, validated_at
            FROM inventaires WHERE type_inventaire = 'CONSOMMABLES'
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

def get_nb_refs_site(site):
    """Compte les références affectées à un site (même stock = 0)"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT COUNT(*) as nb FROM stock_consommables 
            WHERE site = %s AND is_active = TRUE
        """, (site,))
        result = cursor.fetchone()
        cursor.close()
        conn.close()
        return result['nb'] if result else 0
    except:
        return 0

def creer_inventaire(date_inv, site, compteur_1, compteur_2, mois, annee):
    """Crée inventaire + lignes (toutes refs affectées au site, même stock = 0)"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Vérifier pas d'inventaire en cours sur ce site
        cursor.execute("""
            SELECT id FROM inventaires 
            WHERE type_inventaire = 'CONSOMMABLES' AND statut = 'EN_COURS' AND site = %s
        """, (site,))
        if cursor.fetchone():
            return False, f"❌ Un inventaire est déjà en cours pour {site}"
        
        created_by = st.session_state.get('username', 'system')
        
        # Créer inventaire
        cursor.execute("""
            INSERT INTO inventaires (type_inventaire, date_inventaire, mois, annee, site, 
                                    statut, compteur_1, compteur_2, created_by)
            VALUES ('CONSOMMABLES', %s, %s, %s, %s, 'EN_COURS', %s, %s, %s)
            RETURNING id
        """, (date_inv, mois, annee, site, compteur_1, compteur_2, created_by))
        inv_id = cursor.fetchone()['id']
        
        # ⭐ Charger TOUTES les refs affectées au site (même stock = 0)
        cursor.execute("""
            SELECT 
                sc.consommable_id, sc.site, sc.atelier, sc.emplacement,
                sc.quantite as stock_theorique,
                COALESCE(sc.coefficient_conversion, 1.0) as coefficient_conversion
            FROM stock_consommables sc
            WHERE sc.is_active = TRUE AND sc.site = %s
        """, (site,))
        rows = cursor.fetchall()
        
        if not rows:
            conn.rollback()
            return False, f"❌ Aucune référence affectée à {site}"
        
        # Insérer lignes avec coefficient
        for row in rows:
            cursor.execute("""
                INSERT INTO inventaires_consommables_lignes 
                (inventaire_id, consommable_id, site, atelier, emplacement, 
                 stock_theorique, coefficient_conversion)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (inv_id, row['consommable_id'], row['site'], row['atelier'],
                  row['emplacement'], row['stock_theorique'], row['coefficient_conversion']))
        
        # Mettre à jour nb_lignes
        cursor.execute("UPDATE inventaires SET nb_lignes = %s WHERE id = %s", (len(rows), inv_id))
        
        conn.commit()
        cursor.close()
        conn.close()
        return True, f"✅ Inventaire #{inv_id} créé avec {len(rows)} références"
    except Exception as e:
        if 'conn' in locals():
            conn.rollback()
        return False, f"❌ Erreur : {str(e)}"

def get_lignes_inventaire(inventaire_id):
    """Récupère lignes avec détails pour validation"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT 
                il.id, rc.code_consommable, rc.libelle, rc.unite_inventaire,
                il.site, il.atelier, il.stock_theorique, il.stock_compte,
                il.ecart, rc.prix_unitaire, il.coefficient_conversion, il.ecart_valeur
            FROM inventaires_consommables_lignes il
            JOIN ref_consommables rc ON il.consommable_id = rc.id
            WHERE il.inventaire_id = %s
            ORDER BY rc.libelle
        """, (inventaire_id,))
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        
        if rows:
            df = pd.DataFrame(rows)
            for col in ['stock_theorique', 'stock_compte', 'ecart', 'prix_unitaire', 'coefficient_conversion', 'ecart_valeur']:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
            return df
        return pd.DataFrame()
    except:
        return pd.DataFrame()

def valider_inventaire(inventaire_id, validateur):
    """Valide inventaire et met à jour stock (conserve coefficient existant)"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Récupérer lignes comptées
        cursor.execute("""
            SELECT il.consommable_id, il.site, il.atelier, il.stock_compte,
                   il.ecart, il.coefficient_conversion, rc.prix_unitaire
            FROM inventaires_consommables_lignes il
            JOIN ref_consommables rc ON il.consommable_id = rc.id
            WHERE il.inventaire_id = %s AND il.stock_compte IS NOT NULL
        """, (inventaire_id,))
        lignes = cursor.fetchall()
        
        if not lignes:
            return False, "❌ Aucune ligne comptée"
        
        nb_ecarts = 0
        valeur_ecart_total = 0.0
        
        # Mettre à jour stock (quantité seulement, PAS coefficient)
        for ligne in lignes:
            cursor.execute("""
                UPDATE stock_consommables
                SET quantite = %s, updated_at = CURRENT_TIMESTAMP
                WHERE consommable_id = %s AND site = %s AND atelier = %s AND is_active = TRUE
            """, (ligne['stock_compte'], ligne['consommable_id'], ligne['site'], ligne['atelier']))
            
            # Calculer écarts
            ecart = ligne['ecart'] or 0
            if ecart != 0:
                nb_ecarts += 1
                coef = float(ligne['coefficient_conversion'] or 1)
                prix = float(ligne['prix_unitaire'] or 0)
                valeur_ecart_total += abs(ecart * coef * prix)
        
        # Valider inventaire
        cursor.execute("""
            UPDATE inventaires
            SET statut = 'VALIDE', validateur = %s, validated_at = CURRENT_TIMESTAMP,
                nb_ecarts = %s, valeur_ecart_total = %s
            WHERE id = %s
        """, (validateur, nb_ecarts, valeur_ecart_total, inventaire_id))
        
        conn.commit()
        cursor.close()
        conn.close()
        return True, f"✅ Inventaire validé - {len(lignes)} ligne(s), {nb_ecarts} écart(s)"
    except Exception as e:
        if 'conn' in locals():
            conn.rollback()
        return False, f"❌ Erreur : {str(e)}"

def supprimer_inventaire(inventaire_id):
    """Supprime inventaire EN_COURS"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT statut FROM inventaires WHERE id = %s", (inventaire_id,))
        result = cursor.fetchone()
        if not result or result['statut'] != 'EN_COURS':
            return False, "❌ Seuls les inventaires EN_COURS peuvent être supprimés"
        
        cursor.execute("DELETE FROM inventaires_consommables_lignes WHERE inventaire_id = %s", (inventaire_id,))
        cursor.execute("DELETE FROM inventaires WHERE id = %s", (inventaire_id,))
        
        conn.commit()
        cursor.close()
        conn.close()
        return True, f"✅ Inventaire #{inventaire_id} supprimé"
    except Exception as e:
        if 'conn' in locals():
            conn.rollback()
        return False, f"❌ Erreur : {str(e)}"

# ============================================================
# INTERFACE
# ============================================================

# KPIs
kpis = get_kpis()
if kpis:
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("📅 Dernier inventaire", kpis['dernier'] or "Aucun")
    with col2:
        st.metric("🔄 En cours", kpis['en_cours'])
    with col3:
        st.metric("✅ Validés", kpis['total'])

st.markdown("---")

# Onglets
tab1, tab2, tab3, tab4 = st.tabs(["➕ Créer", "✅ Valider", "📜 Historique", "🗑️ Gérer"])

# ==========================================
# ONGLET CRÉER
# ==========================================

with tab1:
    st.subheader("➕ Créer un inventaire")
    
    col1, col2 = st.columns(2)
    
    with col1:
        date_inv = st.date_input("Date *", value=date.today())
        sites = get_sites_disponibles()
        site_sel = st.selectbox("Site *", sites)
        
        # Afficher nb références
        nb_refs = get_nb_refs_site(site_sel)
        st.info(f"📦 **{nb_refs} références** à compter sur {site_sel}")
    
    with col2:
        mois = date_inv.month
        annee = date_inv.year
        st.text_input("Mois", value=f"{mois:02d}", disabled=True)
        st.text_input("Année", value=str(annee), disabled=True)
    
    st.markdown("---")
    
    compteur_1 = st.text_input("Compteur 1 *")
    compteur_2 = st.text_input("Compteur 2 (optionnel)")
    
    st.markdown("---")
    
    if st.button("✅ Créer l'inventaire", type="primary", use_container_width=True):
        if not compteur_1:
            st.error("❌ Le compteur 1 est obligatoire")
        elif nb_refs == 0:
            st.error(f"❌ Aucune référence affectée à {site_sel}")
        else:
            success, msg = creer_inventaire(date_inv, site_sel, compteur_1, compteur_2 or None, mois, annee)
            if success:
                st.success(msg)
                st.balloons()
            else:
                st.error(msg)

# ==========================================
# ONGLET VALIDER
# ==========================================

with tab2:
    st.subheader("✅ Valider un inventaire")
    
    df_en_cours = get_inventaires_liste('EN_COURS')
    
    if not df_en_cours.empty:
        options = [f"#{row['id']} - {row['date_inventaire']} - {row['site']} ({row['nb_lignes']} lignes)" 
                   for _, row in df_en_cours.iterrows()]
        selected = st.selectbox("Sélectionner l'inventaire", options)
        inv_id = int(selected.split('#')[1].split(' ')[0])
        
        df_lignes = get_lignes_inventaire(inv_id)
        
        if not df_lignes.empty:
            nb_comptees = df_lignes['stock_compte'].notna().sum()
            nb_total = len(df_lignes)
            
            st.progress(nb_comptees / nb_total if nb_total > 0 else 0)
            st.write(f"**{nb_comptees}/{nb_total}** lignes comptées")
            
            if nb_comptees < nb_total:
                st.warning(f"⚠️ Comptage incomplet - {nb_total - nb_comptees} ligne(s) non comptée(s)")
            
            # Écarts
            df_ecarts = df_lignes[df_lignes['ecart'].notna() & (df_lignes['ecart'] != 0)].copy()
            
            if not df_ecarts.empty:
                st.markdown("### 📊 Écarts détectés")
                
                # ⭐ Valorisation avec coefficient
                df_ecarts['valeur_ecart'] = df_ecarts['ecart'] * df_ecarts['coefficient_conversion'] * df_ecarts['prix_unitaire']
                
                df_display = df_ecarts[['libelle', 'atelier', 'stock_theorique', 'stock_compte', 'ecart', 'valeur_ecart']].copy()
                df_display.columns = ['Consommable', 'Atelier', 'Théo', 'Compté', 'Écart', 'Valeur €']
                st.dataframe(df_display, use_container_width=True, hide_index=True)
                
                total_ecart = df_ecarts['valeur_ecart'].abs().sum()
                st.warning(f"**{len(df_ecarts)} écart(s)** - Valeur totale : **{total_ecart:,.2f} €**")
            else:
                st.success("✅ Aucun écart détecté !")
            
            st.markdown("---")
            
            validateur = st.text_input("Nom du validateur *")
            
            col1, col2 = st.columns(2)
            with col1:
                if st.button("✅ Valider et mettre à jour le stock", type="primary", use_container_width=True):
                    if not validateur:
                        st.error("❌ Validateur obligatoire")
                    elif nb_comptees == 0:
                        st.error("❌ Aucune ligne comptée")
                    else:
                        success, msg = valider_inventaire(inv_id, validateur)
                        if success:
                            st.success(msg)
                            st.balloons()
                            st.rerun()
                        else:
                            st.error(msg)
            
            with col2:
                if st.button("❌ Annuler l'inventaire", use_container_width=True):
                    try:
                        conn = get_connection()
                        cursor = conn.cursor()
                        cursor.execute("UPDATE inventaires SET statut = 'ANNULE' WHERE id = %s", (inv_id,))
                        conn.commit()
                        cursor.close()
                        conn.close()
                        st.success("Inventaire annulé")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Erreur : {e}")
    else:
        st.info("📭 Aucun inventaire en cours à valider")

# ==========================================
# ONGLET HISTORIQUE
# ==========================================

with tab3:
    st.subheader("📜 Historique des inventaires")
    
    df_hist = get_inventaires_liste()
    
    if not df_hist.empty:
        df_display = df_hist[['id', 'date_inventaire', 'site', 'statut', 'compteur_1', 
                              'validateur', 'nb_lignes', 'nb_ecarts', 'valeur_ecart_total']].copy()
        df_display.columns = ['ID', 'Date', 'Site', 'Statut', 'Compteur', 'Validateur', 
                              'Lignes', 'Écarts', 'Valeur €']
        st.dataframe(df_display, use_container_width=True, hide_index=True)
        
        # Export
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            df_display.to_excel(writer, index=False)
        st.download_button("📥 Exporter historique", buffer.getvalue(), 
                          f"historique_inventaires_{datetime.now().strftime('%Y%m%d')}.xlsx")
    else:
        st.info("📭 Aucun historique")

# ==========================================
# ONGLET GÉRER (SUPPRIMER)
# ==========================================

with tab4:
    st.subheader("🗑️ Supprimer un inventaire")
    
    df_en_cours = get_inventaires_liste('EN_COURS')
    
    if not df_en_cours.empty:
        st.warning("⚠️ La suppression est définitive et irréversible")
        
        options = [f"#{row['id']} - {row['date_inventaire']} - {row['site']}" 
                   for _, row in df_en_cours.iterrows()]
        selected = st.selectbox("Inventaire à supprimer", options, key="sup_select")
        inv_id = int(selected.split('#')[1].split(' ')[0])
        
        confirm = st.checkbox("✅ Je confirme vouloir supprimer cet inventaire")
        
        if st.button("🗑️ Supprimer définitivement", type="primary", disabled=not confirm):
            success, msg = supprimer_inventaire(inv_id)
            if success:
                st.success(msg)
                st.rerun()
            else:
                st.error(msg)
    else:
        st.info("📭 Aucun inventaire en cours à supprimer")

# ==========================================
# INVENTAIRE LOTS (FUTURE)
# ==========================================

st.markdown("---")
st.markdown("### 🥔 Inventaire Lots")
st.info("🚧 Module en développement")

show_footer()
