import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime
from database import get_connection
from components import show_footer
from auth import is_authenticated
import io

st.set_page_config(page_title="Détails Stock - Culture Pom", page_icon="📍", layout="wide")

# CSS compact
st.markdown("""
<style>
    .block-container {
        padding-top: 2rem !important;
        padding-bottom: 0.5rem !important;
        padding-left: 2rem !important;
        padding-right: 2rem !important;
    }
    h1, h2, h3, h4 {
        margin-top: 0.3rem !important;
        margin-bottom: 0.3rem !important;
        padding-top: 0 !important;
        padding-bottom: 0 !important;
    }
    .stSelectbox, .stButton, .stCheckbox {
        margin-bottom: 0.3rem !important;
        margin-top: 0.3rem !important;
    }
    .stDataFrame {
        margin-top: 0.5rem !important;
        margin-bottom: 0.5rem !important;
    }
    [data-testid="stMetricValue"] {
        font-size: 1.4rem !important;
    }
    [data-testid="metric-container"] {
        padding: 0.3rem !important;
    }
    hr {
        margin-top: 0.5rem !important;
        margin-bottom: 0.5rem !important;
    }
    [data-testid="column"] {
        padding: 0.2rem !important;
    }
    .lot-card {
        background-color: #f0f2f6;
        padding: 1rem;
        border-radius: 0.5rem;
        margin: 0.5rem 0;
        border-left: 4px solid #1f77b4;
    }
</style>
""", unsafe_allow_html=True)

if not is_authenticated():
    st.warning("⚠️ Veuillez vous connecter pour accéder à cette page")
    st.stop()

st.title("📍 Détails Stock par Lot")
st.caption("*Gestion des emplacements de stockage par lot*")
st.markdown("---")

# ============================================================================
# FONCTIONS UTILITAIRES
# ============================================================================

def get_sites_stockage():
    """Récupère tous les sites de stockage actifs"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT DISTINCT code_site 
            FROM ref_sites_stockage 
            WHERE is_active = TRUE 
            ORDER BY code_site
        """)
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        return [row['code_site'] for row in rows]
    except Exception as e:
        st.error(f"❌ Erreur : {str(e)}")
        return []

def get_emplacements_by_site(site):
    """Récupère les emplacements d'un site donné"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT code_emplacement, nom_complet
            FROM ref_sites_stockage
            WHERE code_site = %s AND is_active = TRUE
            ORDER BY code_emplacement
        """, (site,))
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        return [(row['code_emplacement'], row['nom_complet']) for row in rows]
    except Exception as e:
        st.error(f"❌ Erreur : {str(e)}")
        return []

def get_lot_info(lot_id):
    """Récupère les infos d'un lot"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        query = """
            SELECT 
                l.id,
                l.code_lot_interne,
                l.nom_usage,
                l.code_variete,
                COALESCE(v.nom_variete, l.code_variete) as nom_variete,
                l.code_producteur,
                COALESCE(p.nom, l.code_producteur) as nom_producteur,
                l.date_entree_stock,
                l.calibre_min,
                l.calibre_max,
                l.poids_total_brut_kg,
                l.statut,
                COALESCE((CURRENT_DATE - l.date_entree_stock::DATE), 0) as age_jours
            FROM lots_bruts l
            LEFT JOIN ref_varietes v ON l.code_variete = v.code_variete
            LEFT JOIN ref_producteurs p ON l.code_producteur = p.code_producteur
            WHERE l.id = %s AND l.is_active = TRUE
        """
        
        cursor.execute(query, (lot_id,))
        row = cursor.fetchone()
        cursor.close()
        conn.close()
        
        return dict(row) if row else None
        
    except Exception as e:
        st.error(f"❌ Erreur : {str(e)}")
        return None

def get_lot_emplacements(lot_id):
    """Récupère les emplacements d'un lot avec statut lavage emoji"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        query = """
            SELECT 
                se.id,
                se.site_stockage,
                se.emplacement_stockage,
                se.nombre_unites,
                se.type_conditionnement,
                se.poids_total_kg,
                se.statut_lavage,
                se.is_active
            FROM stock_emplacements se
            WHERE se.lot_id = %s AND se.is_active = TRUE
            ORDER BY se.site_stockage, se.emplacement_stockage
        """
        
        cursor.execute(query, (lot_id,))
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        
        if rows:
            df = pd.DataFrame(rows)
            # Convertir colonnes numériques
            numeric_cols = ['nombre_unites', 'poids_total_kg']
            for col in numeric_cols:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
            
            # ⭐ Ajouter emoji statut
            if 'statut_lavage' in df.columns:
                def get_statut_emoji(statut):
                    if statut == 'BRUT':
                        return '🟢 BRUT'
                    elif statut == 'LAVÉ':
                        return '🧼 LAVÉ'
                    elif statut == 'GRENAILLES':
                        return '🌾 GRENAILLES'
                    else:
                        return statut
                
                df['statut_lavage_display'] = df['statut_lavage'].apply(get_statut_emoji)
            
            return df
        return pd.DataFrame()
        
    except Exception as e:
        st.error(f"❌ Erreur : {str(e)}")
        return pd.DataFrame()

def get_lot_mouvements(lot_id, limit=10):
    """Récupère les derniers mouvements d'un lot"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        query = """
            SELECT 
                type_mouvement,
                site_origine,
                emplacement_origine,
                site_destination,
                emplacement_destination,
                quantite,
                type_conditionnement,
                poids_kg,
                user_action,
                notes,
                created_at
            FROM stock_mouvements
            WHERE lot_id = %s
            ORDER BY created_at DESC
            LIMIT %s
        """
        
        cursor.execute(query, (lot_id, limit))
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        
        if rows:
            df = pd.DataFrame(rows)
            # Convertir colonnes numériques
            numeric_cols = ['quantite', 'poids_kg']
            for col in numeric_cols:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
            return df
        return pd.DataFrame()
        
    except Exception as e:
        st.error(f"❌ Erreur : {str(e)}")
        return pd.DataFrame()

def add_emplacement(lot_id, site, emplacement, nombre_unites, type_cond, statut_lavage='BRUT'):
    """Ajoute un emplacement"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Calcul poids selon type conditionnement
        if type_cond == 'Pallox':
            poids_unitaire = 1900.0
        elif type_cond == 'Petit Pallox':
            poids_unitaire = 1200.0
        elif type_cond == 'Big Bag':
            poids_unitaire = 1600.0
        else:
            poids_unitaire = 1900.0
        
        poids_total = nombre_unites * poids_unitaire
        
        # Insérer emplacement
        query = """
            INSERT INTO stock_emplacements (
                lot_id, site_stockage, emplacement_stockage, 
                nombre_unites, type_conditionnement, poids_total_kg, 
                statut_lavage, is_active
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, TRUE)
        """
        
        cursor.execute(query, (
            int(lot_id), site, emplacement, 
            int(nombre_unites), type_cond, float(poids_total),
            statut_lavage
        ))
        
        # Enregistrer mouvement
        user = st.session_state.get('username', 'system')
        
        query_mvt = """
            INSERT INTO stock_mouvements (
                lot_id, type_mouvement, site_destination, emplacement_destination,
                quantite, type_conditionnement, poids_kg, user_action
            ) VALUES (%s, 'AJOUT', %s, %s, %s, %s, %s, %s)
        """
        
        cursor.execute(query_mvt, (
            int(lot_id), site, emplacement,
            int(nombre_unites), type_cond, float(poids_total), user
        ))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return True, "✅ Emplacement ajouté"
        
    except Exception as e:
        if 'conn' in locals():
            conn.rollback()
        return False, f"❌ Erreur : {str(e)}"

def transfer_emplacement(lot_id, empl_source_id, quantite_transfert, site_dest, empl_dest):
    """Transfère du stock d'un emplacement vers un autre"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Récupérer infos source
        cursor.execute("""
            SELECT site_stockage, emplacement_stockage, nombre_unites, 
                   type_conditionnement, poids_total_kg, statut_lavage
            FROM stock_emplacements
            WHERE id = %s AND is_active = TRUE
        """, (empl_source_id,))
        
        source = cursor.fetchone()
        
        if not source:
            return False, "❌ Emplacement source introuvable"
        
        if int(quantite_transfert) > int(source['nombre_unites']):
            return False, f"❌ Quantité insuffisante (disponible: {source['nombre_unites']})"
        
        # Calcul poids
        if source['type_conditionnement'] == 'Pallox':
            poids_unitaire = 1900.0
        elif source['type_conditionnement'] == 'Petit Pallox':
            poids_unitaire = 1200.0
        elif source['type_conditionnement'] == 'Big Bag':
            poids_unitaire = 1600.0
        else:
            poids_unitaire = 1900.0
        
        poids_transfere = quantite_transfert * poids_unitaire
        
        # Déduire de la source
        nouvelle_quantite_source = int(source['nombre_unites']) - int(quantite_transfert)
        nouveau_poids_source = nouvelle_quantite_source * poids_unitaire
        
        if nouvelle_quantite_source == 0:
            # Supprimer source
            cursor.execute("""
                UPDATE stock_emplacements 
                SET is_active = FALSE 
                WHERE id = %s
            """, (empl_source_id,))
        else:
            # Mettre à jour source
            cursor.execute("""
                UPDATE stock_emplacements 
                SET nombre_unites = %s, poids_total_kg = %s 
                WHERE id = %s
            """, (nouvelle_quantite_source, nouveau_poids_source, empl_source_id))
        
        # Vérifier si destination existe déjà
        cursor.execute("""
            SELECT id, nombre_unites, poids_total_kg
            FROM stock_emplacements
            WHERE lot_id = %s 
              AND site_stockage = %s 
              AND emplacement_stockage = %s 
              AND type_conditionnement = %s
              AND statut_lavage = %s
              AND is_active = TRUE
        """, (int(lot_id), site_dest, empl_dest, source['type_conditionnement'], source['statut_lavage']))
        
        dest_existant = cursor.fetchone()
        
        if dest_existant:
            # Ajouter à l'existant
            nouvelle_quantite_dest = int(dest_existant['nombre_unites']) + int(quantite_transfert)
            nouveau_poids_dest = float(dest_existant['poids_total_kg']) + poids_transfere
            
            cursor.execute("""
                UPDATE stock_emplacements 
                SET nombre_unites = %s, poids_total_kg = %s 
                WHERE id = %s
            """, (nouvelle_quantite_dest, nouveau_poids_dest, dest_existant['id']))
        else:
            # Créer nouveau
            cursor.execute("""
                INSERT INTO stock_emplacements (
                    lot_id, site_stockage, emplacement_stockage,
                    nombre_unites, type_conditionnement, poids_total_kg,
                    statut_lavage, is_active
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, TRUE)
            """, (int(lot_id), site_dest, empl_dest, int(quantite_transfert), 
                  source['type_conditionnement'], poids_transfere, source['statut_lavage']))
        
        # Enregistrer mouvement
        user = st.session_state.get('username', 'system')
        
        cursor.execute("""
            INSERT INTO stock_mouvements (
                lot_id, type_mouvement, 
                site_origine, emplacement_origine,
                site_destination, emplacement_destination,
                quantite, type_conditionnement, poids_kg, user_action
            ) VALUES (%s, 'TRANSFERT', %s, %s, %s, %s, %s, %s, %s, %s)
        """, (int(lot_id), source['site_stockage'], source['emplacement_stockage'],
              site_dest, empl_dest, int(quantite_transfert), 
              source['type_conditionnement'], poids_transfere, user))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return True, "✅ Transfert effectué"
        
    except Exception as e:
        if 'conn' in locals():
            conn.rollback()
        return False, f"❌ Erreur : {str(e)}"

def modify_emplacement(empl_id, nouvelle_quantite):
    """Modifie la quantité d'un emplacement"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Récupérer infos
        cursor.execute("""
            SELECT lot_id, site_stockage, emplacement_stockage, 
                   nombre_unites, type_conditionnement
            FROM stock_emplacements
            WHERE id = %s AND is_active = TRUE
        """, (empl_id,))
        
        empl = cursor.fetchone()
        
        if not empl:
            return False, "❌ Emplacement introuvable"
        
        # Calcul poids
        if empl['type_conditionnement'] == 'Pallox':
            poids_unitaire = 1900.0
        elif empl['type_conditionnement'] == 'Petit Pallox':
            poids_unitaire = 1200.0
        elif empl['type_conditionnement'] == 'Big Bag':
            poids_unitaire = 1600.0
        else:
            poids_unitaire = 1900.0
        
        nouveau_poids = nouvelle_quantite * poids_unitaire
        
        # Mettre à jour
        cursor.execute("""
            UPDATE stock_emplacements 
            SET nombre_unites = %s, poids_total_kg = %s 
            WHERE id = %s
        """, (int(nouvelle_quantite), float(nouveau_poids), empl_id))
        
        # Enregistrer mouvement
        user = st.session_state.get('username', 'system')
        
        cursor.execute("""
            INSERT INTO stock_mouvements (
                lot_id, type_mouvement, 
                site_destination, emplacement_destination,
                quantite, type_conditionnement, poids_kg, user_action,
                notes
            ) VALUES (%s, 'MODIFICATION', %s, %s, %s, %s, %s, %s, %s)
        """, (int(empl['lot_id']), empl['site_stockage'], empl['emplacement_stockage'],
              int(nouvelle_quantite), empl['type_conditionnement'], float(nouveau_poids), user,
              f"Ancienne quantité: {empl['nombre_unites']}"))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return True, "✅ Emplacement modifié"
        
    except Exception as e:
        if 'conn' in locals():
            conn.rollback()
        return False, f"❌ Erreur : {str(e)}"

def delete_emplacement(empl_id):
    """Supprime (soft delete) un emplacement"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Récupérer infos pour mouvement
        cursor.execute("""
            SELECT lot_id, site_stockage, emplacement_stockage, 
                   nombre_unites, type_conditionnement, poids_total_kg
            FROM stock_emplacements
            WHERE id = %s AND is_active = TRUE
        """, (empl_id,))
        
        empl = cursor.fetchone()
        
        if not empl:
            return False, "❌ Emplacement introuvable"
        
        # Soft delete
        cursor.execute("""
            UPDATE stock_emplacements 
            SET is_active = FALSE 
            WHERE id = %s
        """, (empl_id,))
        
        # Enregistrer mouvement
        user = st.session_state.get('username', 'system')
        
        cursor.execute("""
            INSERT INTO stock_mouvements (
                lot_id, type_mouvement, 
                site_origine, emplacement_origine,
                quantite, type_conditionnement, poids_kg, user_action
            ) VALUES (%s, 'SUPPRESSION', %s, %s, %s, %s, %s, %s)
        """, (int(empl['lot_id']), empl['site_stockage'], empl['emplacement_stockage'],
              int(empl['nombre_unites']), empl['type_conditionnement'], 
              float(empl['poids_total_kg']), user))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return True, "✅ Emplacement supprimé"
        
    except Exception as e:
        if 'conn' in locals():
            conn.rollback()
        return False, f"❌ Erreur : {str(e)}"

def get_all_lots():
    """Récupère tous les lots actifs"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        query = """
            SELECT 
                l.id,
                l.code_lot_interne,
                l.nom_usage,
                COALESCE(v.nom_variete, l.code_variete) as nom_variete,
                COALESCE(p.nom, l.code_producteur) as nom_producteur
            FROM lots_bruts l
            LEFT JOIN ref_varietes v ON l.code_variete = v.code_variete
            LEFT JOIN ref_producteurs p ON l.code_producteur = p.code_producteur
            WHERE l.is_active = TRUE
            ORDER BY l.code_lot_interne
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

def get_lots_for_dropdown():
    """Récupère les lots pour dropdown avec format"""
    df = get_all_lots()
    if not df.empty:
        return {f"{row['id']} - {row['code_lot_interne']} - {row['nom_usage']}": row['id'] 
                for _, row in df.iterrows()}
    return {}

# ============================================================================
# ⭐ RÉCUPÉRATION LOT_ID DEPUIS QUERY PARAMS OU SESSION_STATE
# ============================================================================

# Récupérer depuis query params (navigation depuis page Lots)
query_params = st.query_params
lot_id_from_params = query_params.get("lot_id")

# Récupérer depuis session_state (sélection multiple page Lots)
selected_lots_from_session = st.session_state.get('selected_lots_for_details', [])

# ⭐ DÉTERMINER LOTS À AFFICHER
lots_to_display = []

if lot_id_from_params:
    # Navigation depuis page Lots (un seul lot)
    try:
        lots_to_display = [int(lot_id_from_params)]
    except:
        pass

if selected_lots_from_session and len(selected_lots_from_session) > 0:
    # Sélection multiple depuis page Lots
    lots_to_display = selected_lots_from_session

# ============================================================================
# AFFICHAGE - BOUCLE SUR TOUS LES LOTS SÉLECTIONNÉS
# ============================================================================

if len(lots_to_display) > 0:
    st.success(f"📦 **{len(lots_to_display)} lot(s) sélectionné(s)** depuis la page Lots")
    st.markdown("---")
    
    # ⭐ BOUCLE - AFFICHER CHAQUE LOT
    for idx, lot_id in enumerate(lots_to_display):
        # Séparateur entre lots
        if idx > 0:
            st.markdown("---")
            st.markdown("---")
        
        lot_info = get_lot_info(lot_id)
        
        if lot_info:
            # ⭐ CARTE INFO LOT
            st.markdown(f"""
            <div class="lot-card">
                <h3>📦 Lot #{lot_info['id']} - {lot_info['code_lot_interne']}</h3>
                <strong>Nom:</strong> {lot_info['nom_usage']}<br>
                <strong>Variété:</strong> {lot_info['nom_variete']}<br>
                <strong>Producteur:</strong> {lot_info['nom_producteur']}<br>
                <strong>Date entrée:</strong> {lot_info['date_entree_stock']}<br>
                <strong>Âge:</strong> {lot_info['age_jours']} jours
            </div>
            """, unsafe_allow_html=True)
            
            # KPIs emplacement
            df_empl = get_lot_emplacements(lot_id)
            
            if not df_empl.empty:
                col1, col2, col3, col4 = st.columns(4)
                
                with col1:
                    st.metric("📍 Emplacements", len(df_empl))
                
                with col2:
                    total_pallox = df_empl['nombre_unites'].sum()
                    st.metric("📦 Pallox total", int(total_pallox))
                
                with col3:
                    total_tonnage = df_empl['poids_total_kg'].sum() / 1000
                    st.metric("⚖️ Tonnage", f"{total_tonnage:.1f} T")
                
                with col4:
                    statuts = df_empl['statut_lavage'].value_counts()
                    statut_principal = statuts.index[0] if len(statuts) > 0 else 'N/A'
                    
                    if statut_principal == 'BRUT':
                        emoji = '🟢'
                    elif statut_principal == 'LAVÉ':
                        emoji = '🧼'
                    elif statut_principal == 'GRENAILLES':
                        emoji = '🌾'
                    else:
                        emoji = '❓'
                    
                    st.metric("🏷️ Statut principal", f"{emoji} {statut_principal}")
                
                st.markdown("---")
                
                # Tableau emplacements
                st.subheader(f"📋 Emplacements - Lot {lot_info['code_lot_interne']}")
                
                display_cols = ['id', 'site_stockage', 'emplacement_stockage', 'nombre_unites', 
                               'type_conditionnement', 'poids_total_kg', 'statut_lavage_display']
                
                df_display = df_empl[display_cols].copy()
                
                df_display = df_display.rename(columns={
                    'id': 'ID',
                    'site_stockage': 'Site',
                    'emplacement_stockage': 'Emplacement',
                    'nombre_unites': 'Pallox',
                    'type_conditionnement': 'Type',
                    'poids_total_kg': 'Poids (kg)',
                    'statut_lavage_display': 'Statut'
                })
                
                st.dataframe(
                    df_display,
                    use_container_width=True,
                    hide_index=True
                )
                
                # ⭐ BOUTONS ACTIONS
                st.markdown("---")
                st.subheader(f"⚙️ Actions - Lot {lot_info['code_lot_interne']}")
                
                col1, col2, col3, col4 = st.columns(4)
                
                with col1:
                    if st.button(f"➕ Ajouter", key=f"btn_add_{lot_id}", use_container_width=True):
                        st.session_state[f'show_add_form_{lot_id}'] = True
                        st.rerun()
                
                with col2:
                    if st.button(f"🔄 Transférer", key=f"btn_transfer_{lot_id}", use_container_width=True):
                        st.session_state[f'show_transfer_form_{lot_id}'] = True
                        st.rerun()
                
                with col3:
                    if st.button(f"✏️ Modifier", key=f"btn_modify_{lot_id}", use_container_width=True):
                        st.session_state[f'show_modify_form_{lot_id}'] = True
                        st.rerun()
                
                with col4:
                    if st.button(f"🗑️ Supprimer", key=f"btn_delete_{lot_id}", use_container_width=True):
                        st.session_state[f'show_delete_form_{lot_id}'] = True
                        st.rerun()
                
                # ⭐ FORMULAIRE AJOUTER
                if st.session_state.get(f'show_add_form_{lot_id}', False):
                    st.markdown("---")
                    st.markdown(f"##### ➕ Ajouter Emplacement - Lot {lot_info['code_lot_interne']}")
                    
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        sites = get_sites_stockage()
                        site = st.selectbox("Site *", options=[""] + sites, key=f"add_site_{lot_id}")
                        
                        if site:
                            emplacements = get_emplacements_by_site(site)
                            empl_options = [""] + [e[0] for e in emplacements]
                            emplacement = st.selectbox("Emplacement *", options=empl_options, key=f"add_empl_{lot_id}")
                        else:
                            emplacement = None
                    
                    with col2:
                        nombre = st.number_input("Nombre unités *", min_value=1, value=5, key=f"add_nb_{lot_id}")
                        
                        TYPES = ["Pallox", "Petit Pallox", "Big Bag"]
                        type_cond = st.selectbox("Type *", options=TYPES, key=f"add_type_{lot_id}")
                        
                        # Calcul auto poids
                        if type_cond == 'Pallox':
                            poids_unit = 1900
                        elif type_cond == 'Petit Pallox':
                            poids_unit = 1200
                        else:
                            poids_unit = 1600
                        
                        poids_calc = nombre * poids_unit
                        st.metric("Poids calculé", f"{poids_calc:,.0f} kg")
                    
                    col_save, col_cancel = st.columns(2)
                    
                    with col_save:
                        if st.button("💾 Enregistrer", key=f"save_add_{lot_id}", type="primary", use_container_width=True):
                            if site and emplacement and nombre and type_cond:
                                success, message = add_emplacement(lot_id, site, emplacement, nombre, type_cond)
                                if success:
                                    st.success(message)
                                    st.session_state.pop(f'show_add_form_{lot_id}')
                                    st.rerun()
                                else:
                                    st.error(message)
                            else:
                                st.error("❌ Tous les champs sont obligatoires")
                    
                    with col_cancel:
                        if st.button("❌ Annuler", key=f"cancel_add_{lot_id}", use_container_width=True):
                            st.session_state.pop(f'show_add_form_{lot_id}')
                            st.rerun()
                
                # ⭐ FORMULAIRE TRANSFÉRER
                if st.session_state.get(f'show_transfer_form_{lot_id}', False):
                    st.markdown("---")
                    st.markdown(f"##### 🔄 Transférer Stock - Lot {lot_info['code_lot_interne']}")
                    
                    # Sélection source
                    empl_options = {f"{row['id']} - {row['site_stockage']} / {row['emplacement_stockage']} ({int(row['nombre_unites'])} pallox)": row['id'] 
                                   for _, row in df_empl.iterrows()}
                    
                    selected_source = st.selectbox("Emplacement source *", options=[""] + list(empl_options.keys()), key=f"transfer_source_{lot_id}")
                    
                    if selected_source and selected_source != "":
                        empl_source_id = empl_options[selected_source]
                        
                        # Récupérer quantité max
                        empl_data = df_empl[df_empl['id'] == empl_source_id].iloc[0]
                        quantite_max = int(empl_data['nombre_unites'])
                        
                        col1, col2 = st.columns(2)
                        
                        with col1:
                            quantite_transfert = st.slider(
                                "Quantité à transférer *",
                                min_value=1,
                                max_value=quantite_max,
                                value=min(5, quantite_max),
                                key=f"transfer_qty_{lot_id}"
                            )
                        
                        with col2:
                            sites = get_sites_stockage()
                            site_dest = st.selectbox("Site destination *", options=[""] + sites, key=f"transfer_site_{lot_id}")
                            
                            if site_dest:
                                emplacements = get_emplacements_by_site(site_dest)
                                empl_options_dest = [""] + [e[0] for e in emplacements]
                                empl_dest = st.selectbox("Emplacement destination *", options=empl_options_dest, key=f"transfer_empl_{lot_id}")
                            else:
                                empl_dest = None
                        
                        col_save, col_cancel = st.columns(2)
                        
                        with col_save:
                            if st.button("💾 Transférer", key=f"save_transfer_{lot_id}", type="primary", use_container_width=True):
                                if site_dest and empl_dest:
                                    success, message = transfer_emplacement(lot_id, empl_source_id, quantite_transfert, site_dest, empl_dest)
                                    if success:
                                        st.success(message)
                                        st.session_state.pop(f'show_transfer_form_{lot_id}')
                                        st.rerun()
                                    else:
                                        st.error(message)
                                else:
                                    st.error("❌ Site et emplacement destination obligatoires")
                        
                        with col_cancel:
                            if st.button("❌ Annuler", key=f"cancel_transfer_{lot_id}", use_container_width=True):
                                st.session_state.pop(f'show_transfer_form_{lot_id}')
                                st.rerun()
                    else:
                        st.info("👆 Sélectionnez un emplacement source")
                
                # ⭐ FORMULAIRE MODIFIER
                if st.session_state.get(f'show_modify_form_{lot_id}', False):
                    st.markdown("---")
                    st.markdown(f"##### ✏️ Modifier Quantité - Lot {lot_info['code_lot_interne']}")
                    
                    # Sélection emplacement
                    empl_options = {f"{row['id']} - {row['site_stockage']} / {row['emplacement_stockage']} ({int(row['nombre_unites'])} pallox)": row['id'] 
                                   for _, row in df_empl.iterrows()}
                    
                    selected_empl = st.selectbox("Emplacement *", options=[""] + list(empl_options.keys()), key=f"modify_empl_{lot_id}")
                    
                    if selected_empl and selected_empl != "":
                        empl_id = empl_options[selected_empl]
                        
                        empl_data = df_empl[df_empl['id'] == empl_id].iloc[0]
                        quantite_actuelle = int(empl_data['nombre_unites'])
                        
                        nouvelle_quantite = st.number_input(
                            f"Nouvelle quantité (actuelle: {quantite_actuelle}) *",
                            min_value=0,
                            value=quantite_actuelle,
                            step=1,
                            key=f"modify_qty_{lot_id}"
                        )
                        
                        col_save, col_cancel = st.columns(2)
                        
                        with col_save:
                            if st.button("💾 Modifier", key=f"save_modify_{lot_id}", type="primary", use_container_width=True):
                                if nouvelle_quantite != quantite_actuelle:
                                    success, message = modify_emplacement(empl_id, nouvelle_quantite)
                                    if success:
                                        st.success(message)
                                        st.session_state.pop(f'show_modify_form_{lot_id}')
                                        st.rerun()
                                    else:
                                        st.error(message)
                                else:
                                    st.info("ℹ️ Quantité inchangée")
                        
                        with col_cancel:
                            if st.button("❌ Annuler", key=f"cancel_modify_{lot_id}", use_container_width=True):
                                st.session_state.pop(f'show_modify_form_{lot_id}')
                                st.rerun()
                    else:
                        st.info("👆 Sélectionnez un emplacement")
                
                # ⭐ FORMULAIRE SUPPRIMER
                if st.session_state.get(f'show_delete_form_{lot_id}', False):
                    st.markdown("---")
                    st.markdown(f"##### 🗑️ Supprimer Emplacement - Lot {lot_info['code_lot_interne']}")
                    
                    # Sélection emplacement
                    empl_options = {f"{row['id']} - {row['site_stockage']} / {row['emplacement_stockage']} ({int(row['nombre_unites'])} pallox)": row['id'] 
                                   for _, row in df_empl.iterrows()}
                    
                    selected_empl = st.selectbox("Emplacement à supprimer *", options=[""] + list(empl_options.keys()), key=f"delete_empl_{lot_id}")
                    
                    if selected_empl and selected_empl != "":
                        empl_id = empl_options[selected_empl]
                        
                        st.warning(f"⚠️ Confirmer la suppression de : **{selected_empl}**")
                        
                        col_confirm, col_cancel = st.columns(2)
                        
                        with col_confirm:
                            if st.button("✅ CONFIRMER", key=f"confirm_delete_{lot_id}", type="primary", use_container_width=True):
                                success, message = delete_emplacement(empl_id)
                                if success:
                                    st.success(message)
                                    st.session_state.pop(f'show_delete_form_{lot_id}')
                                    st.rerun()
                                else:
                                    st.error(message)
                        
                        with col_cancel:
                            if st.button("❌ ANNULER", key=f"cancel_delete_{lot_id}", use_container_width=True):
                                st.session_state.pop(f'show_delete_form_{lot_id}')
                                st.rerun()
                    else:
                        st.info("👆 Sélectionnez un emplacement")
                
                # Historique mouvements
                st.markdown("---")
                st.subheader(f"📜 Historique (10 derniers) - Lot {lot_info['code_lot_interne']}")
                
                df_mvt = get_lot_mouvements(lot_id)
                
                if not df_mvt.empty:
                    st.dataframe(df_mvt, use_container_width=True, hide_index=True)
                else:
                    st.info("Aucun mouvement enregistré")
            
            else:
                st.warning(f"⚠️ Aucun emplacement pour le lot #{lot_id}")
                st.info("💡 Utilisez le bouton '➕ Ajouter' ci-dessous pour créer un emplacement")
                
                # Permettre ajout même si aucun emplacement
                if st.button(f"➕ Ajouter Premier Emplacement", key=f"btn_add_first_{lot_id}", use_container_width=True, type="primary"):
                    st.session_state[f'show_add_form_{lot_id}'] = True
                    st.rerun()
                
                # Formulaire ajout (même si aucun emplacement)
                if st.session_state.get(f'show_add_form_{lot_id}', False):
                    st.markdown("---")
                    st.markdown(f"##### ➕ Ajouter Emplacement - Lot {lot_info['code_lot_interne']}")
                    
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        sites = get_sites_stockage()
                        site = st.selectbox("Site *", options=[""] + sites, key=f"add_site_first_{lot_id}")
                        
                        if site:
                            emplacements = get_emplacements_by_site(site)
                            empl_options = [""] + [e[0] for e in emplacements]
                            emplacement = st.selectbox("Emplacement *", options=empl_options, key=f"add_empl_first_{lot_id}")
                        else:
                            emplacement = None
                    
                    with col2:
                        nombre = st.number_input("Nombre unités *", min_value=1, value=5, key=f"add_nb_first_{lot_id}")
                        
                        TYPES = ["Pallox", "Petit Pallox", "Big Bag"]
                        type_cond = st.selectbox("Type *", options=TYPES, key=f"add_type_first_{lot_id}")
                        
                        if type_cond == 'Pallox':
                            poids_unit = 1900
                        elif type_cond == 'Petit Pallox':
                            poids_unit = 1200
                        else:
                            poids_unit = 1600
                        
                        poids_calc = nombre * poids_unit
                        st.metric("Poids calculé", f"{poids_calc:,.0f} kg")
                    
                    col_save, col_cancel = st.columns(2)
                    
                    with col_save:
                        if st.button("💾 Enregistrer", key=f"save_add_first_{lot_id}", type="primary", use_container_width=True):
                            if site and emplacement and nombre and type_cond:
                                success, message = add_emplacement(lot_id, site, emplacement, nombre, type_cond)
                                if success:
                                    st.success(message)
                                    st.session_state.pop(f'show_add_form_{lot_id}')
                                    st.rerun()
                                else:
                                    st.error(message)
                            else:
                                st.error("❌ Tous les champs sont obligatoires")
                    
                    with col_cancel:
                        if st.button("❌ Annuler", key=f"cancel_add_first_{lot_id}", use_container_width=True):
                            st.session_state.pop(f'show_add_form_{lot_id}')
                            st.rerun()
        
        else:
            st.error(f"❌ Lot #{lot_id} introuvable")

else:
    # Aucun lot sélectionné - Afficher sélection manuelle
    st.info("ℹ️ Aucun lot sélectionné depuis la page Lots")
    st.markdown("---")
    st.subheader("🔍 Sélectionner un lot manuellement")
    
    lots_dict = get_lots_for_dropdown()
    
    if lots_dict:
        selected_lot_str = st.selectbox(
            "Choisir un lot",
            options=[""] + list(lots_dict.keys()),
            key="manual_lot_selection"
        )
        
        if selected_lot_str and selected_lot_str != "":
            selected_lot_id = lots_dict[selected_lot_str]
            
            if st.button("📦 Afficher ce lot", type="primary", use_container_width=True):
                # Mettre en session_state et rerun
                st.session_state.selected_lots_for_details = [selected_lot_id]
                st.rerun()
    else:
        st.warning("⚠️ Aucun lot disponible")

show_footer()
