import streamlit as st
import pandas as pd
from datetime import datetime
from database import get_connection
from components import show_footer
from auth import is_authenticated, is_admin
import streamlit.components.v1 as components

st.set_page_config(page_title="Emplacements - Culture Pom", page_icon="📦", layout="wide")

# CSS espacements réduits
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
    .stSelectbox, .stButton, .stCheckbox {
        margin-bottom: 0.3rem !important;
        margin-top: 0.3rem !important;
    }
</style>
""", unsafe_allow_html=True)

if not is_authenticated():
    st.warning("⚠️ Veuillez vous connecter pour accéder à cette page")
    st.stop()

# Bloc utilisateur sidebar
def show_user_info():
    if st.session_state.get('authenticated', False):
        with st.sidebar:
            st.markdown("---")
            st.write(f"👤 {st.session_state.get('name', 'Utilisateur')}")
            st.caption(f"📧 {st.session_state.get('email', '')}")
            st.caption(f"🔑 {st.session_state.get('role', 'USER')}")
            st.markdown("---")
            if st.button("🚪 Déconnexion", use_container_width=True, key="btn_logout_sidebar"):
                for key in list(st.session_state.keys()):
                    del st.session_state[key]
                st.rerun()

show_user_info()

# ============================================================================
# FONCTIONS
# ============================================================================

def get_sites_stockage():
    """Récupère la liste des sites de stockage depuis ref_sites_stockage"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        query = """
        SELECT DISTINCT code_site 
        FROM ref_sites_stockage 
        WHERE is_active = TRUE 
        ORDER BY code_site
        """
        
        cursor.execute(query)
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        
        if rows:
            return [row['code_site'] for row in rows]
        return []
    except Exception as e:
        st.error(f"❌ Erreur chargement sites : {str(e)}")
        return []

def get_emplacements_by_site(code_site):
    """Récupère les emplacements d'un site depuis ref_sites_stockage"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        query = """
        SELECT code_emplacement, nom_complet
        FROM ref_sites_stockage 
        WHERE code_site = %s AND is_active = TRUE 
        ORDER BY code_emplacement
        """
        
        cursor.execute(query, (code_site,))
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        
        if rows:
            return [(row['code_emplacement'], row['nom_complet']) for row in rows]
        return []
    except Exception as e:
        st.error(f"❌ Erreur chargement emplacements : {str(e)}")
        return []

def get_lot_info(lot_id):
    """Récupère les informations complètes d'un lot"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        query = """
        SELECT 
            l.id,
            l.code_lot_interne,
            l.nom_usage,
            COALESCE(v.nom_variete, l.code_variete) as nom_variete,
            p.nom as nom_producteur,
            l.date_entree_stock,
            l.nombre_unites,
            l.poids_total_brut_kg,
            l.valeur_lot_euro,
            l.statut as statut_libelle,
            COALESCE((CURRENT_DATE - l.date_entree_stock::DATE), 0) as age_jours
        FROM lots_bruts l
        LEFT JOIN ref_varietes v ON l.code_variete = v.code_variete
        LEFT JOIN ref_producteurs p ON l.code_producteur = p.code_producteur
        WHERE l.id = %s
        """
        
        cursor.execute(query, (lot_id,))
        result = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if result:
            return {
                'id': result['id'],
                'code_lot_interne': result['code_lot_interne'],
                'nom_usage': result['nom_usage'],
                'nom_variete': result['nom_variete'],
                'nom_producteur': result['nom_producteur'],
                'date_entree_stock': result['date_entree_stock'],
                'nombre_unites': result['nombre_unites'],
                'poids_total_brut_kg': result['poids_total_brut_kg'],
                'valeur_lot_euro': result['valeur_lot_euro'],
                'statut_libelle': result['statut_libelle'],
                'age_jours': int(result['age_jours']) if result['age_jours'] else 0
            }
        return None
    except Exception as e:
        st.error(f"❌ Erreur chargement lot : {str(e)}")
        return None

def get_lot_emplacements(lot_id):
    """Récupère tous les emplacements d'un lot"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        query = """
        SELECT 
            id,
            site_stockage,
            emplacement_stockage,
            nombre_unites,
            poids_total_kg,
            type_stock,
            type_conditionnement,
            statut_lavage,
            is_active,
            created_at,
            updated_at
        FROM stock_emplacements
        WHERE lot_id = %s AND is_active = TRUE
        ORDER BY created_at DESC
        """
        
        cursor.execute(query, (lot_id,))
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        
        if rows:
            df = pd.DataFrame(rows, columns=[
                'id', 'site_stockage', 'emplacement_stockage', 
                'nombre_unites', 'poids_total_kg', 'type_stock', 'type_conditionnement',
                'statut_lavage', 'is_active', 'created_at', 'updated_at'
            ])
            
            # ⭐ Ajouter colonnes calculées Lavé et Grenailles
            df['est_lave'] = df['statut_lavage'].apply(lambda x: 'OUI' if x == 'LAVÉ' else 'NON')
            df['est_grenailles'] = df['statut_lavage'].apply(lambda x: 'OUI' if x == 'GRENAILLES' else 'NON')
            
            return df
        return pd.DataFrame()
    except Exception as e:
        st.error(f"❌ Erreur chargement emplacements : {str(e)}")
        return pd.DataFrame()

def get_lot_mouvements(lot_id, limit=10):
    """Récupère les derniers mouvements d'un lot"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        query = """
        SELECT 
            type_mouvement,
            site_avant,
            site_apres,
            quantite_mouvement,
            description,
            created_at,
            created_by
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
            df = pd.DataFrame(rows, columns=[
                'type_mouvement', 'site_avant', 'site_apres',
                'quantite_mouvement', 'description', 'created_at', 'created_by'
            ])
            return df
        return pd.DataFrame()
    except Exception as e:
        st.error(f"❌ Erreur chargement mouvements : {str(e)}")
        return pd.DataFrame()

# ============================================================================
# FONCTIONS ACTIONS SUR EMPLACEMENTS
# ============================================================================

def add_emplacement(lot_id, site_stockage, emplacement_stockage, nombre_unites, poids_total_kg, type_stock="PRINCIPAL", type_conditionnement=None):
    """Ajoute un nouvel emplacement pour un lot"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Insérer l'emplacement
        query = """
        INSERT INTO stock_emplacements 
        (lot_id, site_stockage, emplacement_stockage, nombre_unites, poids_total_kg, type_stock, type_conditionnement, is_active, created_at, updated_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, TRUE, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        RETURNING id
        """
        
        cursor.execute(query, (lot_id, site_stockage, emplacement_stockage, nombre_unites, poids_total_kg, type_stock, type_conditionnement))
        emplacement_id = cursor.fetchone()['id']
        
        # Enregistrer le mouvement
        mouvement_query = """
        INSERT INTO stock_mouvements
        (lot_id, type_mouvement, site_apres, quantite_mouvement, description, created_at, created_by)
        VALUES (%s, 'AJOUT', %s, %s, %s, CURRENT_TIMESTAMP, %s)
        """
        
        description = f"Ajout emplacement {site_stockage}/{emplacement_stockage}"
        created_by = st.session_state.get('username', 'system')
        
        cursor.execute(mouvement_query, (lot_id, f"{site_stockage}/{emplacement_stockage}", nombre_unites, description, created_by))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return True, f"✅ Emplacement ajouté avec succès (ID: {emplacement_id})"
        
    except Exception as e:
        if 'conn' in locals():
            conn.rollback()
            conn.close()
        
        error_msg = str(e).lower()
        
        # Erreur colonne manquante type_conditionnement
        if "type_conditionnement" in error_msg and "does not exist" in error_msg:
            return False, "❌ La colonne 'type_conditionnement' n'existe pas dans la table. Veuillez exécuter le script SQL de mise à jour."
        
        # Erreur code_lot_interne
        elif "code_lot_interne" in error_msg:
            return False, "❌ Erreur structure table : colonne 'code_lot_interne' manquante. Veuillez vérifier la structure de la base de données."
        
        # Autres erreurs
        else:
            return False, f"❌ Erreur : {str(e)}"

def update_emplacement(emplacement_id, nombre_unites=None, poids_total_kg=None, type_conditionnement=None):
    """Modifie la quantité d'un emplacement"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Récupérer les anciennes valeurs
        cursor.execute("SELECT lot_id, nombre_unites, poids_total_kg, site_stockage, emplacement_stockage FROM stock_emplacements WHERE id = %s", (emplacement_id,))
        old_data = cursor.fetchone()
        
        if not old_data:
            return False, "❌ Emplacement introuvable"
        
        # Préparer les mises à jour
        updates = []
        values = []
        
        if nombre_unites is not None:
            updates.append("nombre_unites = %s")
            values.append(nombre_unites)
        
        if poids_total_kg is not None:
            updates.append("poids_total_kg = %s")
            values.append(poids_total_kg)
        
        if type_conditionnement is not None:
            updates.append("type_conditionnement = %s")
            values.append(type_conditionnement)
        
        if not updates:
            return False, "❌ Aucune modification à apporter"
        
        updates.append("updated_at = CURRENT_TIMESTAMP")
        values.append(emplacement_id)
        
        # Mettre à jour
        query = f"UPDATE stock_emplacements SET {', '.join(updates)} WHERE id = %s"
        cursor.execute(query, values)
        
        # Enregistrer le mouvement
        description = f"Modification {old_data['site_stockage']}/{old_data['emplacement_stockage']}"
        if nombre_unites is not None:
            description += f" : {old_data['nombre_unites']} → {nombre_unites} pallox"
        
        mouvement_query = """
        INSERT INTO stock_mouvements
        (lot_id, type_mouvement, site_apres, quantite_mouvement, description, created_at, created_by)
        VALUES (%s, 'MODIFICATION', %s, %s, %s, CURRENT_TIMESTAMP, %s)
        """
        
        created_by = st.session_state.get('username', 'system')
        cursor.execute(mouvement_query, (
            old_data['lot_id'], 
            f"{old_data['site_stockage']}/{old_data['emplacement_stockage']}", 
            nombre_unites or old_data['nombre_unites'],
            description, 
            created_by
        ))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return True, "✅ Emplacement modifié avec succès"
        
    except Exception as e:
        if 'conn' in locals():
            conn.rollback()
        return False, f"❌ Erreur : {str(e)}"

def delete_emplacement(emplacement_id):
    """Supprime (soft delete) un emplacement"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Récupérer les infos pour le mouvement
        cursor.execute("SELECT lot_id, nombre_unites, site_stockage, emplacement_stockage FROM stock_emplacements WHERE id = %s", (emplacement_id,))
        data = cursor.fetchone()
        
        if not data:
            return False, "❌ Emplacement introuvable"
        
        # Soft delete
        cursor.execute("UPDATE stock_emplacements SET is_active = FALSE, updated_at = CURRENT_TIMESTAMP WHERE id = %s", (emplacement_id,))
        
        # Enregistrer le mouvement
        description = f"Suppression {data['site_stockage']}/{data['emplacement_stockage']}"
        
        mouvement_query = """
        INSERT INTO stock_mouvements
        (lot_id, type_mouvement, site_avant, quantite_mouvement, description, created_at, created_by)
        VALUES (%s, 'SUPPRESSION', %s, %s, %s, CURRENT_TIMESTAMP, %s)
        """
        
        created_by = st.session_state.get('username', 'system')
        cursor.execute(mouvement_query, (
            data['lot_id'],
            f"{data['site_stockage']}/{data['emplacement_stockage']}",
            data['nombre_unites'],
            description,
            created_by
        ))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return True, "✅ Emplacement supprimé avec succès"
        
    except Exception as e:
        if 'conn' in locals():
            conn.rollback()
        return False, f"❌ Erreur : {str(e)}"

def transfer_emplacement(emplacement_source_id, site_destination, emplacement_destination, quantite_transfert, poids_transfert, type_conditionnement=None):
    """Transfère une quantité de pallox d'un emplacement vers un autre"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Récupérer l'emplacement source
        cursor.execute("""
            SELECT lot_id, site_stockage, emplacement_stockage, nombre_unites, poids_total_kg, type_stock, type_conditionnement
            FROM stock_emplacements 
            WHERE id = %s AND is_active = TRUE
        """, (emplacement_source_id,))
        
        source = cursor.fetchone()
        
        if not source:
            return False, "❌ Emplacement source introuvable"
        
        # Validation : quantité suffisante ?
        if source['nombre_unites'] < quantite_transfert:
            return False, f"❌ Quantité insuffisante (disponible: {source['nombre_unites']} pallox)"
        
        if source['poids_total_kg'] < poids_transfert:
            return False, f"❌ Poids insuffisant (disponible: {source['poids_total_kg']:.1f} kg)"
        
        # 1. Diminuer l'emplacement source
        new_nb_source = source['nombre_unites'] - quantite_transfert
        new_poids_source = source['poids_total_kg'] - poids_transfert
        
        if new_nb_source > 0:
            # Mettre à jour
            cursor.execute("""
                UPDATE stock_emplacements 
                SET nombre_unites = %s, poids_total_kg = %s, updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
            """, (new_nb_source, new_poids_source, emplacement_source_id))
        else:
            # Vider complètement (soft delete)
            cursor.execute("""
                UPDATE stock_emplacements 
                SET is_active = FALSE, updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
            """, (emplacement_source_id,))
        
        # 2. Chercher ou créer l'emplacement destination
        cursor.execute("""
            SELECT id, nombre_unites, poids_total_kg
            FROM stock_emplacements
            WHERE lot_id = %s AND site_stockage = %s AND emplacement_stockage = %s AND is_active = TRUE
        """, (source['lot_id'], site_destination, emplacement_destination))
        
        destination = cursor.fetchone()
        
        # Utiliser type_conditionnement du formulaire ou celui de la source
        type_cond_final = type_conditionnement if type_conditionnement else source.get('type_conditionnement')
        
        if destination:
            # Augmenter l'emplacement destination existant
            new_nb_dest = destination['nombre_unites'] + quantite_transfert
            new_poids_dest = destination['poids_total_kg'] + poids_transfert
            
            cursor.execute("""
                UPDATE stock_emplacements
                SET nombre_unites = %s, poids_total_kg = %s, updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
            """, (new_nb_dest, new_poids_dest, destination['id']))
        else:
            # Créer nouvel emplacement destination
            cursor.execute("""
                INSERT INTO stock_emplacements
                (lot_id, site_stockage, emplacement_stockage, nombre_unites, poids_total_kg, type_stock, type_conditionnement, is_active, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, TRUE, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """, (source['lot_id'], site_destination, emplacement_destination, quantite_transfert, poids_transfert, source['type_stock'], type_cond_final))
        
        # 3. Enregistrer le mouvement
        description = f"Transfert {source['site_stockage']}/{source['emplacement_stockage']} → {site_destination}/{emplacement_destination}"
        
        mouvement_query = """
        INSERT INTO stock_mouvements
        (lot_id, type_mouvement, site_avant, site_apres, quantite_mouvement, description, created_at, created_by)
        VALUES (%s, 'TRANSFERT', %s, %s, %s, %s, CURRENT_TIMESTAMP, %s)
        """
        
        created_by = st.session_state.get('username', 'system')
        cursor.execute(mouvement_query, (
            source['lot_id'],
            f"{source['site_stockage']}/{source['emplacement_stockage']}",
            f"{site_destination}/{emplacement_destination}",
            quantite_transfert,
            description,
            created_by
        ))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return True, f"✅ Transfert effectué : {quantite_transfert} pallox ({poids_transfert:.1f} kg)"
        
    except Exception as e:
        if 'conn' in locals():
            conn.rollback()
        return False, f"❌ Erreur : {str(e)}"

# ============================================================================
# INTERFACE
# ============================================================================

# ⭐ Récupérer les IDs des lots sélectionnés depuis session_state
selected_lot_ids = st.session_state.get('selected_lots_for_emplacements', [])

if not selected_lot_ids:
    st.error("❌ Aucun lot sélectionné")
    st.info("💡 Veuillez cocher un ou plusieurs lots dans la page Stock, puis cliquer sur 'Voir Emplacements'")
    if st.button("← Retour à la liste des lots", use_container_width=True):
        st.switch_page("pages/02_Stock.py")
    st.stop()

# Vérifier que ce sont bien des entiers
try:
    selected_lot_ids = [int(lot_id) for lot_id in selected_lot_ids]
except:
    st.error("❌ IDs de lots invalides")
    if st.button("← Retour à la liste des lots", use_container_width=True):
        st.switch_page("pages/02_Stock.py")
    st.stop()

# ============================================================================
# TITRE & NAVIGATION
# ============================================================================

col_title, col_back = st.columns([4, 1])

with col_title:
    nb_lots = len(selected_lot_ids)
    if nb_lots == 1:
        st.title(f"📦 Emplacements du Lot")
    else:
        st.title(f"📦 Emplacements de {nb_lots} Lots")

with col_back:
    if st.button("← Retour Stock", use_container_width=True):
        st.switch_page("pages/02_Stock.py")

st.markdown("---")

# ============================================================================
# VUE D'ENSEMBLE CONSOLIDÉE (tous les lots)
# ============================================================================

st.subheader("📊 Vue Consolidée")

# Calculer totaux pour tous les lots
total_lots = len(selected_lot_ids)
total_pallox_global = 0
total_tonnage_global = 0
total_emplacements_global = 0

# Charger données de tous les lots
lots_data = []

for lot_id in selected_lot_ids:
    lot_info = get_lot_info(lot_id)
    if lot_info:
        emplacements_df = get_lot_emplacements(lot_id)
        
        nb_emplacements = len(emplacements_df)
        total_pallox = emplacements_df['nombre_unites'].sum() if not emplacements_df.empty else 0
        total_tonnage = (emplacements_df['poids_total_kg'].sum() / 1000) if not emplacements_df.empty and 'poids_total_kg' in emplacements_df.columns else 0
        
        lots_data.append({
            'lot_id': lot_id,
            'lot_info': lot_info,
            'emplacements_df': emplacements_df,
            'nb_emplacements': nb_emplacements,
            'total_pallox': total_pallox,
            'total_tonnage': total_tonnage
        })
        
        total_pallox_global += total_pallox
        total_tonnage_global += total_tonnage
        total_emplacements_global += nb_emplacements

# KPIs Consolidés
col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric("📦 Total Lots", total_lots)

with col2:
    st.metric("📦 Total Pallox", f"{int(total_pallox_global)}")

with col3:
    st.metric("⚖️ Total Tonnage", f"{total_tonnage_global:.1f} T")

with col4:
    st.metric("📍 Total Emplacements", total_emplacements_global)

st.markdown("---")

# ============================================================================
# DÉTAIL PAR LOT (Vue Compacte avec Expanders)
# ============================================================================

st.subheader("📍 Détail par Lot")

for lot_data in lots_data:
    lot_info = lot_data['lot_info']
    emplacements_df = lot_data['emplacements_df']
    
    # ⭐ EXPANDER POUR CHAQUE LOT - Fermé par défaut pour meilleure lisibilité
    with st.expander(
        f"🔽 {lot_info['code_lot_interne']} - {lot_info['nom_usage']} "
        f"({int(lot_data['total_pallox'])} pallox, {lot_data['total_tonnage']:.1f}T)",
        expanded=False
    ):
        
        # Infos lot (compact - 2 colonnes)
        col1, col2 = st.columns(2)
        
        with col1:
            st.write(f"**Variété** : {lot_info['nom_variete'] or 'N/A'}")
            st.write(f"**Producteur** : {lot_info['nom_producteur'] or 'N/A'}")
            st.write(f"**Âge** : {lot_info['age_jours']} jours")
        
        with col2:
            statut_display = lot_info['statut_libelle'] or "N/A"
            # Ajouter emoji selon le statut
            if statut_display == "EN_STOCK":
                statut_display = "📦 En stock"
            st.write(f"**Statut** : {statut_display}")
            valeur_display = f"{lot_info['valeur_lot_euro']:,.0f} €" if lot_info['valeur_lot_euro'] else "N/A"
            st.write(f"**Valeur** : {valeur_display}")
            st.write(f"**Emplacements** : {lot_data['nb_emplacements']}")
        
        st.markdown("---")
        
        # ⭐ BOUTON AJOUTER EMPLACEMENT
        col_add, col_space = st.columns([1, 3])
        
        with col_add:
            if st.button(f"➕ Ajouter du stock sur le lot", key=f"btn_add_empl_{lot_data['lot_id']}", use_container_width=True, type="primary"):
                st.session_state[f'show_add_form_{lot_data["lot_id"]}'] = not st.session_state.get(f'show_add_form_{lot_data["lot_id"]}', False)
                st.rerun()
        
        # ⭐ FORMULAIRE AJOUT EMPLACEMENT
        if st.session_state.get(f'show_add_form_{lot_data["lot_id"]}', False):
            st.markdown("#### ➕ Ajouter du stock sur le lot")
            
            # Charger les sites disponibles
            sites_disponibles = get_sites_stockage()
            
            if not sites_disponibles:
                st.warning("⚠️ Aucun site de stockage trouvé dans les références. Veuillez d'abord ajouter des sites dans la page Sources.")
            else:
                col1, col2 = st.columns(2)
                
                with col1:
                    new_site = st.selectbox(
                        "Site de stockage *",
                        options=[""] + sites_disponibles,
                        key=f"new_site_{lot_data['lot_id']}"
                    )
                    
                    # Type de conditionnement
                    new_type_conditionnement = st.selectbox(
                        "Type de conditionnement *",
                        options=["", "Pallox", "Petit Pallox", "Big Bag"],
                        key=f"new_type_cond_{lot_data['lot_id']}"
                    )
                    
                    new_nombre_unites = st.number_input("Nombre d'unités *", min_value=0, value=0, step=1, key=f"new_nb_{lot_data['lot_id']}")
                
                with col2:
                    # Charger emplacements pour le site sélectionné
                    if new_site:
                        emplacements_disponibles = get_emplacements_by_site(new_site)
                        empl_options = [""] + [e[0] for e in emplacements_disponibles]
                    else:
                        empl_options = [""]
                    
                    new_emplacement = st.selectbox(
                        "Emplacement *",
                        options=empl_options,
                        key=f"new_empl_{lot_data['lot_id']}"
                    )
                    
                    # Calcul automatique du poids total
                    poids_unitaire = 0
                    if new_type_conditionnement == "Pallox":
                        poids_unitaire = 1900
                    elif new_type_conditionnement == "Petit Pallox":
                        poids_unitaire = 1200
                    elif new_type_conditionnement == "Big Bag":
                        poids_unitaire = 1600
                    
                    poids_total_calcule = poids_unitaire * new_nombre_unites
                    
                    # Afficher le poids calculé (non éditable)
                    st.metric("Poids total calculé", f"{poids_total_calcule} kg")
                
                new_type = st.selectbox(
                    "Type de stock",
                    options=["PRINCIPAL", "SECONDAIRE", "RESERVE"],
                    key=f"new_type_{lot_data['lot_id']}"
                )
                
                col_save, col_cancel = st.columns(2)
                
                with col_save:
                    if st.button("💾 Enregistrer", key=f"btn_save_add_{lot_data['lot_id']}", use_container_width=True, type="primary"):
                        # Validation
                        if not new_site or not new_emplacement or not new_type_conditionnement or new_nombre_unites <= 0:
                            st.error("❌ Tous les champs obligatoires doivent être remplis avec des valeurs > 0")
                        else:
                            success, message = add_emplacement(
                                lot_data['lot_id'],
                                new_site,
                                new_emplacement,
                                new_nombre_unites,
                                poids_total_calcule,
                                new_type,
                                new_type_conditionnement
                            )
                            
                            if success:
                                st.success(message)
                                st.session_state[f'show_add_form_{lot_data["lot_id"]}'] = False
                                st.rerun()
                            else:
                                st.error(message)
                
                with col_cancel:
                    if st.button("❌ Annuler", key=f"btn_cancel_add_{lot_data['lot_id']}", use_container_width=True):
                        st.session_state[f'show_add_form_{lot_data["lot_id"]}'] = False
                        st.rerun()
            
            st.markdown("---")
        
        # Tableau emplacements
        if not emplacements_df.empty:
            # Formatter poids en tonnes AVANT de sélectionner les colonnes
            emplacements_df['poids_total_t'] = emplacements_df['poids_total_kg'].apply(
                lambda x: f"{x/1000:.1f} T" if pd.notna(x) else "N/A"
            )
            
            # Afficher : Site, Emplacement, Pallox, Type conditionnement, Poids (T), Lavé, Grenailles, Type stock
            display_df = emplacements_df[[
                'site_stockage', 
                'emplacement_stockage', 
                'nombre_unites', 
                'type_conditionnement', 
                'poids_total_t',  # ⭐ Poids en tonnes (déjà formaté)
                'est_lave', 
                'est_grenailles', 
                'type_stock'
            ]].copy()
            
            # Renommer colonnes (dans le BON ordre)
            display_df.columns = ['Site', 'Emplacement', 'Pallox', 'Type Cond.', 'Poids', 'Lavé', 'Grenailles', 'Type']
            
            # Afficher tableau
            st.dataframe(
                display_df,
                use_container_width=True,
                hide_index=True
            )
            
            # ⭐ ACTIONS SUR EMPLACEMENTS
            st.markdown("#### ⚙️ Actions sur les emplacements")
            
            # Dropdown pour sélectionner l'emplacement
            emplacement_options = []
            for idx, row in emplacements_df.iterrows():
                label = f"{row['site_stockage']} / {row['emplacement_stockage']} ({int(row['nombre_unites'])} pallox)"
                emplacement_options.append((row['id'], label))
            
            if emplacement_options:
                selected_empl = st.selectbox(
                    "Sélectionner un emplacement",
                    options=[opt[0] for opt in emplacement_options],
                    format_func=lambda x: next(opt[1] for opt in emplacement_options if opt[0] == x),
                    key=f"select_empl_{lot_data['lot_id']}"
                )
                
                # Récupérer les données de l'emplacement sélectionné
                empl_data = emplacements_df[emplacements_df['id'] == selected_empl].iloc[0]
                
                # Boutons d'actions
                col_modify, col_transfer, col_delete, col_space = st.columns([1, 1, 1, 1])
                
                with col_modify:
                    if st.button("✏️ Modifier", key=f"btn_modify_{lot_data['lot_id']}", use_container_width=True, type="secondary"):
                        st.session_state[f'show_modify_form_{lot_data["lot_id"]}'] = not st.session_state.get(f'show_modify_form_{lot_data["lot_id"]}', False)
                        st.session_state[f'show_transfer_form_{lot_data["lot_id"]}'] = False
                        st.session_state[f'selected_empl_id_{lot_data["lot_id"]}'] = selected_empl
                        st.rerun()
                
                with col_transfer:
                    if st.button("🔄 Transférer", key=f"btn_transfer_{lot_data['lot_id']}", use_container_width=True, type="secondary"):
                        st.session_state[f'show_transfer_form_{lot_data["lot_id"]}'] = not st.session_state.get(f'show_transfer_form_{lot_data["lot_id"]}', False)
                        st.session_state[f'show_modify_form_{lot_data["lot_id"]}'] = False
                        st.session_state[f'selected_empl_id_{lot_data["lot_id"]}'] = selected_empl
                        st.rerun()
                
                with col_delete:
                    if st.button("🗑️ Supprimer", key=f"btn_delete_{lot_data['lot_id']}", use_container_width=True, type="secondary"):
                        if st.session_state.get(f'confirm_delete_{lot_data["lot_id"]}_{selected_empl}', False):
                            success, message = delete_emplacement(selected_empl)
                            if success:
                                st.success(message)
                                st.session_state.pop(f'confirm_delete_{lot_data["lot_id"]}_{selected_empl}', None)
                                st.rerun()
                            else:
                                st.error(message)
                        else:
                            st.session_state[f'confirm_delete_{lot_data["lot_id"]}_{selected_empl}'] = True
                            st.rerun()
                
                # Message de confirmation suppression
                if st.session_state.get(f'confirm_delete_{lot_data["lot_id"]}_{selected_empl}', False):
                    st.warning(f"⚠️ Confirmer la suppression de {empl_data['site_stockage']} / {empl_data['emplacement_stockage']} ? Cliquez à nouveau sur 'Supprimer'")
                
                # ⭐ FORMULAIRE MODIFICATION
                if st.session_state.get(f'show_modify_form_{lot_data["lot_id"]}', False) and st.session_state.get(f'selected_empl_id_{lot_data["lot_id"]}') == selected_empl:
                    st.markdown("##### ✏️ Modifier l'emplacement")
                    
                    # Récupérer type_conditionnement actuel (peut être None)
                    current_type_cond = empl_data.get('type_conditionnement', 'Pallox')
                    if not current_type_cond or current_type_cond == '':
                        current_type_cond = 'Pallox'  # Défaut si vide
                    
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        # Type de conditionnement
                        mod_type_conditionnement = st.selectbox(
                            "Type de conditionnement *",
                            options=["Pallox", "Petit Pallox", "Big Bag"],
                            index=["Pallox", "Petit Pallox", "Big Bag"].index(current_type_cond) if current_type_cond in ["Pallox", "Petit Pallox", "Big Bag"] else 0,
                            key=f"mod_type_cond_{lot_data['lot_id']}"
                        )
                        
                        mod_nombre_unites = st.number_input(
                            "Nombre de pallox *",
                            min_value=0,
                            value=int(empl_data['nombre_unites']),
                            step=1,
                            key=f"mod_nb_{lot_data['lot_id']}"
                        )
                    
                    with col2:
                        # Calcul automatique du poids selon type conditionnement
                        mod_poids_unitaire = 0
                        if mod_type_conditionnement == "Pallox":
                            mod_poids_unitaire = 1900
                        elif mod_type_conditionnement == "Petit Pallox":
                            mod_poids_unitaire = 1200
                        elif mod_type_conditionnement == "Big Bag":
                            mod_poids_unitaire = 1600
                        
                        mod_poids_calcule = mod_poids_unitaire * mod_nombre_unites
                        
                        # Afficher le poids calculé (non éditable)
                        st.metric("Poids total calculé", f"{mod_poids_calcule} kg")
                    
                    col_save, col_cancel = st.columns(2)
                    
                    with col_save:
                        if st.button("💾 Enregistrer", key=f"btn_save_mod_{lot_data['lot_id']}", use_container_width=True, type="primary"):
                            success, message = update_emplacement(
                                selected_empl,
                                nombre_unites=mod_nombre_unites,
                                poids_total_kg=mod_poids_calcule,
                                type_conditionnement=mod_type_conditionnement
                            )
                            
                            if success:
                                st.success(message)
                                st.session_state[f'show_modify_form_{lot_data["lot_id"]}'] = False
                                st.rerun()
                            else:
                                st.error(message)
                    
                    with col_cancel:
                        if st.button("❌ Annuler", key=f"btn_cancel_mod_{lot_data['lot_id']}", use_container_width=True):
                            st.session_state[f'show_modify_form_{lot_data["lot_id"]}'] = False
                            st.rerun()
                
                # ⭐ FORMULAIRE TRANSFERT
                if st.session_state.get(f'show_transfer_form_{lot_data["lot_id"]}', False) and st.session_state.get(f'selected_empl_id_{lot_data["lot_id"]}') == selected_empl:
                    st.markdown("##### 🔄 Transférer des pallox")
                    
                    st.info(f"📍 Source : **{empl_data['site_stockage']} / {empl_data['emplacement_stockage']}** - Disponible : {int(empl_data['nombre_unites'])} pallox ({empl_data['poids_total_kg']:.1f} kg)")
                    
                    # Charger les sites disponibles
                    sites_disponibles = get_sites_stockage()
                    
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        transfer_site = st.selectbox(
                            "Site destination *",
                            options=[""] + sites_disponibles,
                            key=f"transfer_site_{lot_data['lot_id']}"
                        )
                        
                        # Type de conditionnement (même logique que ajout)
                        transfer_type_conditionnement = st.selectbox(
                            "Type de conditionnement *",
                            options=["", "Pallox", "Petit Pallox", "Big Bag"],
                            key=f"transfer_type_cond_{lot_data['lot_id']}"
                        )
                        
                        transfer_quantite = st.number_input(
                            "Quantité à transférer (pallox) *",
                            min_value=1,
                            max_value=int(empl_data['nombre_unites']),
                            value=min(1, int(empl_data['nombre_unites'])),
                            step=1,
                            key=f"transfer_qty_{lot_data['lot_id']}",
                            help=f"Maximum disponible : {int(empl_data['nombre_unites'])} pallox"
                        )
                    
                    with col2:
                        # Charger emplacements pour le site destination sélectionné
                        if transfer_site:
                            emplacements_dest = get_emplacements_by_site(transfer_site)
                            empl_dest_options = [""] + [e[0] for e in emplacements_dest]
                        else:
                            empl_dest_options = [""]
                        
                        dest_emplacement = st.selectbox(
                            "Emplacement destination *",
                            options=empl_dest_options,
                            key=f"transfer_empl_{lot_data['lot_id']}"
                        )
                        
                        # Calcul automatique du poids total selon type conditionnement
                        transfer_poids_unitaire = 0
                        if transfer_type_conditionnement == "Pallox":
                            transfer_poids_unitaire = 1900
                        elif transfer_type_conditionnement == "Petit Pallox":
                            transfer_poids_unitaire = 1200
                        elif transfer_type_conditionnement == "Big Bag":
                            transfer_poids_unitaire = 1600
                        
                        transfer_poids_calcule = transfer_poids_unitaire * transfer_quantite
                        
                        # Afficher le poids calculé (non éditable)
                        st.metric("Poids à transférer", f"{transfer_poids_calcule} kg")
                    
                    col_save, col_cancel = st.columns(2)
                    
                    with col_save:
                        if st.button("🚚 Transférer", key=f"btn_save_transfer_{lot_data['lot_id']}", use_container_width=True, type="primary"):
                            # Validation
                            if not transfer_site or not dest_emplacement or not transfer_type_conditionnement:
                                st.error("❌ Site, emplacement et type de conditionnement sont obligatoires")
                            elif transfer_quantite <= 0:
                                st.error("❌ Quantité doit être > 0")
                            elif transfer_quantite > empl_data['nombre_unites']:
                                st.error(f"❌ Quantité trop élevée (max: {int(empl_data['nombre_unites'])} pallox)")
                            elif transfer_poids_calcule > empl_data['poids_total_kg']:
                                st.error(f"❌ Poids calculé trop élevé (max: {empl_data['poids_total_kg']:.1f} kg)")
                            else:
                                success, message = transfer_emplacement(
                                    selected_empl,
                                    transfer_site,
                                    dest_emplacement,
                                    transfer_quantite,
                                    transfer_poids_calcule,
                                    transfer_type_conditionnement
                                )
                                
                                if success:
                                    st.success(message)
                                    st.session_state[f'show_transfer_form_{lot_data["lot_id"]}'] = False
                                    st.rerun()
                                else:
                                    st.error(message)
                    
                    with col_cancel:
                        if st.button("❌ Annuler", key=f"btn_cancel_transfer_{lot_data['lot_id']}", use_container_width=True):
                            st.session_state[f'show_transfer_form_{lot_data["lot_id"]}'] = False
                            st.rerun()
            
            st.markdown("---")
            
            # Historique (5 derniers mouvements seulement)
            st.markdown("**📜 Historique récent**")
            mouvements_df = get_lot_mouvements(lot_data['lot_id'], limit=5)
            
            if not mouvements_df.empty:
                display_mouvements = mouvements_df.copy()
                
                display_mouvements['Date'] = pd.to_datetime(display_mouvements['created_at']).dt.strftime('%d/%m %H:%M')
                
                type_labels = {
                    'CREATION_LOT': '🆕 Création',
                    'TRANSFERT_DEPART': '🚚 Départ',
                    'TRANSFERT_ARRIVEE': '📥 Arrivée',
                    'DIVISION_LOT': '✂️ Division',
                    'LAVAGE': '🧼 Lavage',
                    'AJUSTEMENT_MANUEL': '✏️ Ajustement',
                    'VENTE': '💰 Vente',
                    'PERTE': '⚠️ Perte'
                }
                display_mouvements['Type'] = display_mouvements['type_mouvement'].map(type_labels)
                
                display_mouvements['Trajet'] = display_mouvements.apply(
                    lambda row: f"{row['site_avant'] or '-'} → {row['site_apres'] or '-'}",
                    axis=1
                )
                
                final_df = display_mouvements[['Date', 'Type', 'Trajet']]
                
                st.dataframe(
                    final_df,
                    use_container_width=True,
                    hide_index=True,
                    height=150
                )
            else:
                st.caption("Aucun mouvement enregistré")
        else:
            st.warning("⚠️ Aucun emplacement trouvé pour ce lot")

st.markdown("---")

# ============================================================================
# ACTIONS RAPIDES
# ============================================================================

st.subheader("⚡ Actions Rapides")

col1, col2, col3 = st.columns(3)

with col1:
    if st.button("🚚 Créer un Transfert", use_container_width=True, type="primary"):
        st.info("🚧 Fonctionnalité disponible en Phase B (Planning Transferts)")

with col2:
    if st.button("📊 Voir Historique Complet", use_container_width=True):
        st.info("🚧 Fonctionnalité disponible en Phase C (Historique Stock)")

with col3:
    if st.button("← Retour à la Liste", use_container_width=True):
        st.switch_page("pages/02_Stock.py")

# Footer
show_footer()
