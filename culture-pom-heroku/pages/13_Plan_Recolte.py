import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime
import time
from database import get_connection
from components import show_footer
from auth import require_access, can_edit, can_delete, get_current_username
import io

st.set_page_config(page_title="Plan Récolte - Culture Pom", page_icon="🌾", layout="wide")

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
    .stSelectbox, .stButton, .stCheckbox {
        margin-bottom: 0.3rem !important;
        margin-top: 0.3rem !important;
    }
    [data-testid="stMetricValue"] {
        font-size: 1.3rem !important;
    }
    .taux-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 1rem;
        border-radius: 10px;
        color: white;
        margin: 0.5rem 0;
    }
    .taux-0 { background: linear-gradient(135deg, #ff6b6b 0%, #ee5a5a 100%); }
    .taux-100 { background: linear-gradient(135deg, #51cf66 0%, #40c057 100%); }
    .taux-200 { background: linear-gradient(135deg, #ffd43b 0%, #fab005 100%); }
</style>
""", unsafe_allow_html=True)

# Vérification authentification et permissions RBAC
require_access("PLANS_RECOLTE")

# Permissions utilisateur
CAN_EDIT = can_edit("PLANS_RECOLTE")
CAN_DELETE = can_delete("PLANS_RECOLTE")

st.title("🌾 Plan de Récolte")
st.markdown("*Gestion du plan prévisionnel par variété, marque et type*")
st.markdown("---")

# ==========================================
# CONFIGURATION
# ==========================================

CAMPAGNE_ACTUELLE = 2026

# Liste des mois possibles
MOIS_OPTIONS = [
    "2026-07", "2026-08", "2026-09", "2026-10", "2026-11", "2026-12",
    "2027-01", "2027-02", "2027-03", "2027-04", "2027-05", "2027-06"
]

MOIS_LABELS = {
    "2026-07": "Juillet 2026", "2026-08": "Août 2026", "2026-09": "Septembre 2026",
    "2026-10": "Octobre 2026", "2026-11": "Novembre 2026", "2026-12": "Décembre 2026",
    "2027-01": "Janvier 2027", "2027-02": "Février 2027", "2027-03": "Mars 2027",
    "2027-04": "Avril 2027", "2027-05": "Mai 2027", "2027-06": "Juin 2027"
}

# ==========================================
# FONCTIONS UTILITAIRES
# ==========================================

def get_mois_numero(mois_str):
    """Extrait le numéro de mois"""
    try:
        return int(mois_str.split('-')[1])
    except:
        return 0

def calculer_volume_brut(volume_net, dechets_pct):
    """Calcule le volume brut"""
    if pd.isna(volume_net) or volume_net == 0:
        return 0
    if pd.isna(dechets_pct):
        dechets_pct = 15
    return volume_net / (1 - dechets_pct / 100)

def calculer_hectares(volume_brut, rendement):
    """Calcule les hectares nécessaires"""
    if pd.isna(volume_brut) or volume_brut == 0:
        return 0
    if pd.isna(rendement) or rendement == 0:
        rendement = 40
    return volume_brut / rendement

def load_plan_data(campagne, show_inactive=False):
    """Charge les données du plan avec taux_couverture_cible"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        where_clause = f"WHERE campagne = {campagne}"
        if not show_inactive:
            where_clause += " AND is_active = TRUE"
        
        query = f"""
            SELECT id, campagne, mois, mois_numero, marque, type_produit, variete,
                   arrachage_quinzaine, volume_net_t, dechets_pct, volume_brut_t,
                   rendement_t_ha, hectares_necessaires, 
                   COALESCE(taux_couverture_cible, 100) as taux_couverture_cible,
                   COALESCE(hectares_ajustes, hectares_necessaires) as hectares_ajustes,
                   notes, is_active,
                   created_by, updated_by, created_at, updated_at
            FROM plans_recolte
            {where_clause}
            ORDER BY mois, marque, type_produit, variete
        """
        
        cursor.execute(query)
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        
        if rows:
            df = pd.DataFrame(rows)
            df.columns = ['id', 'campagne', 'mois', 'mois_numero', 'marque', 'type_produit', 
                         'variete', 'arrachage_quinzaine', 'volume_net_t', 'dechets_pct', 
                         'volume_brut_t', 'rendement_t_ha', 'hectares_necessaires',
                         'taux_couverture_cible', 'hectares_ajustes', 'notes',
                         'is_active', 'created_by', 'updated_by', 'created_at', 'updated_at']
            
            # Convertir colonnes numériques
            numeric_cols = ['volume_net_t', 'dechets_pct', 'volume_brut_t', 
                           'rendement_t_ha', 'hectares_necessaires', 
                           'taux_couverture_cible', 'hectares_ajustes']
            for col in numeric_cols:
                df[col] = pd.to_numeric(df[col], errors='coerce')
            
            return df
        return pd.DataFrame()
        
    except Exception as e:
        st.error(f"❌ Erreur chargement : {str(e)}")
        return pd.DataFrame()

def get_unique_values(df, column):
    """Récupère valeurs uniques triées"""
    if column not in df.columns:
        return []
    values = df[column].dropna().unique().tolist()
    return sorted([str(v) for v in values if str(v).strip()])


@st.cache_data(ttl=3600)
def get_varietes_referentielles():
    """Charge les variétés depuis ref_varietes (table dédiée) avec détection défensive.
    
    Si la table n'existe pas ou n'a pas de colonne nom compatible :
    retourne ([], None) → le code appelant fera fallback sur les valeurs du plan.
    
    Retourne (list[str] triée, nom_colonne_utilisée ou None).
    """
    # Candidats de noms de colonne (par ordre de préférence)
    candidats_col = ['nom', 'nom_variete', 'variete', 'libelle', 'name']
    try:
        conn = get_connection()
        cursor = conn.cursor()
        # 1. Vérifier que la table existe et trouver la bonne colonne
        cursor.execute("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = 'ref_varietes'
        """)
        rows = cursor.fetchall()
        if not rows:
            cursor.close()
            conn.close()
            return ([], None)
        # rows peut être tuple ou dict selon le curseur (RealDictCursor)
        cols = [r['column_name'] if hasattr(r, 'get') else r[0] for r in rows]
        col_nom = next((c for c in candidats_col if c in cols), None)
        if not col_nom:
            cursor.close()
            conn.close()
            return ([], None)
        # 2. Charger les variétés (uniquement actives si la colonne is_active existe)
        if 'is_active' in cols:
            where_clause = f"WHERE is_active = TRUE AND {col_nom} IS NOT NULL AND TRIM({col_nom}::text) <> ''"
        else:
            where_clause = f"WHERE {col_nom} IS NOT NULL AND TRIM({col_nom}::text) <> ''"
        cursor.execute(
            f"SELECT DISTINCT {col_nom} AS nom FROM ref_varietes {where_clause} ORDER BY 1"
        )
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        varietes = []
        for r in rows:
            v = r['nom'] if hasattr(r, 'get') else r[0]
            if v:
                varietes.append(str(v).strip())
        return (sorted(set(varietes)), col_nom)
    except Exception:
        return ([], None)


def save_changes(original_df, edited_df):
    """Sauvegarde les modifications"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        updates = 0
        username = get_current_username()
        
        for idx in edited_df.index:
            if idx not in original_df.index:
                continue
            
            row_id = int(edited_df.loc[idx, 'id'])
            changes = {}
            
            # Colonnes éditables
            editable_cols = ['mois', 'marque', 'type_produit', 'variete', 
                           'arrachage_quinzaine', 'volume_net_t', 'dechets_pct',
                           'rendement_t_ha', 'notes']
            
            for col in editable_cols:
                if col not in edited_df.columns:
                    continue
                
                old_val = original_df.loc[idx, col]
                new_val = edited_df.loc[idx, col]
                
                # Comparer en gérant les NaN
                if pd.isna(old_val) and pd.isna(new_val):
                    continue
                elif pd.isna(old_val) or pd.isna(new_val) or old_val != new_val:
                    # Conversion type Python natif
                    if pd.isna(new_val):
                        changes[col] = None
                    elif isinstance(new_val, (np.integer, np.int64)):
                        changes[col] = int(new_val)
                    elif isinstance(new_val, (np.floating, np.float64)):
                        changes[col] = float(new_val)
                    else:
                        changes[col] = new_val
            
            if changes:
                # ⭐ Mettre à jour mois_numero si le mois a changé
                if 'mois' in changes:
                    changes['mois_numero'] = get_mois_numero(changes['mois'])
                
                # ⭐ NE PAS inclure les colonnes GENERATED (calculées par PostgreSQL)
                # volume_brut_t, hectares_necessaires sont GENERATED ALWAYS AS
                for gen_col in ['volume_brut_t', 'hectares_necessaires', 'hectares_ajustes']:
                    changes.pop(gen_col, None)
                
                # ⭐ Convertir tous les types numpy en types Python natifs
                safe_changes = {}
                for k, v in changes.items():
                    if pd.isna(v) if not isinstance(v, str) else False:
                        safe_changes[k] = None
                    elif isinstance(v, (np.integer, np.int64, np.int32)):
                        safe_changes[k] = int(v)
                    elif isinstance(v, (np.floating, np.float64, np.float32)):
                        safe_changes[k] = float(v)
                    else:
                        safe_changes[k] = v
                changes = safe_changes
                
                # Construire UPDATE
                set_clause = ", ".join([f"{col} = %s" for col in changes.keys()])
                values = list(changes.values()) + [username, row_id]
                
                query = f"""
                    UPDATE plans_recolte 
                    SET {set_clause}, updated_by = %s, updated_at = CURRENT_TIMESTAMP 
                    WHERE id = %s
                """
                cursor.execute(query, values)
                updates += 1
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return True, f"✅ {updates} ligne(s) modifiée(s)"
        
    except Exception as e:
        if 'conn' in locals():
            conn.rollback()
        return False, f"❌ Erreur : {str(e)}"

def add_record(data):
    """Ajoute une nouvelle ligne.
    
    Note : volume_brut_t et hectares_necessaires sont des colonnes GENERATED ALWAYS AS
    côté BDD (calculées automatiquement par Postgres à partir de volume_net_t/dechets_pct
    et rendement_t_ha). Elles ne doivent PAS apparaître dans l'INSERT, sinon Postgres
    rejette avec "cannot insert a non-DEFAULT value into column".
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()
        username = get_current_username()
        
        mois_numero = get_mois_numero(data.get('mois', ''))
        
        query = """
            INSERT INTO plans_recolte (
                campagne, mois, mois_numero, marque, type_produit, variete,
                arrachage_quinzaine, volume_net_t, dechets_pct,
                rendement_t_ha, taux_couverture_cible, notes, created_by
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """
        
        cursor.execute(query, (
            CAMPAGNE_ACTUELLE,
            data.get('mois'),
            mois_numero,
            data.get('marque'),
            data.get('type_produit'),
            data.get('variete'),
            data.get('arrachage_quinzaine'),
            data.get('volume_net_t', 0),
            data.get('dechets_pct', 15),
            data.get('rendement_t_ha', 40),
            100,  # Taux par défaut = 100%
            data.get('notes'),
            username
        ))
        
        new_id = cursor.fetchone()['id']
        conn.commit()
        cursor.close()
        conn.close()
        
        return True, f"✅ Ligne #{new_id} ajoutée"
        
    except Exception as e:
        if 'conn' in locals():
            conn.rollback()
        return False, f"❌ Erreur : {str(e)}"

def delete_record(record_id):
    """Désactive une ligne (soft delete)"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        username = get_current_username()
        
        cursor.execute("""
            UPDATE plans_recolte 
            SET is_active = FALSE, updated_by = %s, updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
        """, (username, record_id))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return True, "✅ Ligne désactivée"
        
    except Exception as e:
        if 'conn' in locals():
            conn.rollback()
        return False, f"❌ Erreur : {str(e)}"

def reactivate_record(record_id):
    """Réactive une ligne"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        username = get_current_username()
        
        cursor.execute("""
            UPDATE plans_recolte 
            SET is_active = TRUE, updated_by = %s, updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
        """, (username, record_id))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return True, "✅ Ligne réactivée"
        
    except Exception as e:
        if 'conn' in locals():
            conn.rollback()
        return False, f"❌ Erreur : {str(e)}"

def update_taux_couverture(record_id, nouveau_taux):
    """Met à jour le taux de couverture d'une ligne ET recalcule hectares_ajustes"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        username = get_current_username()
        
        # Récupérer hectares_necessaires pour calculer hectares_ajustes
        cursor.execute("SELECT hectares_necessaires FROM plans_recolte WHERE id = %s", (record_id,))
        result = cursor.fetchone()
        hectares_base = float(result['hectares_necessaires'] or 0)
        
        # Calculer hectares_ajustes = hectares_base * taux / 100
        hectares_ajustes = hectares_base * nouveau_taux / 100
        
        # Mettre à jour taux ET hectares_ajustes
        cursor.execute("""
            UPDATE plans_recolte 
            SET taux_couverture_cible = %s,
                hectares_ajustes = %s,
                updated_by = %s, 
                updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
        """, (nouveau_taux, hectares_ajustes, username, record_id))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return True, f"✅ Taux mis à jour : {nouveau_taux}% ({hectares_ajustes:.2f} ha)"
        
    except Exception as e:
        if 'conn' in locals():
            conn.rollback()
        return False, f"❌ Erreur : {str(e)}"

def recalculer_besoins():
    """Recalcule les besoins agrégés"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT recalculer_besoins_recolte(%s)", (CAMPAGNE_ACTUELLE,))
        result = cursor.fetchone()
        nb_besoins = result['recalculer_besoins_recolte'] if isinstance(result, dict) else result[0]
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return True, f"✅ {nb_besoins} besoins recalculés"
        
    except Exception as e:
        if 'conn' in locals():
            conn.rollback()
        return False, f"❌ Erreur : {str(e)}"

# ==========================================
# CHARGEMENT DONNÉES
# ==========================================

# Toggle afficher inactifs
show_inactive = st.checkbox("👁️ Afficher lignes désactivées", value=False)

# Charger données
df_full = load_plan_data(CAMPAGNE_ACTUELLE, show_inactive)

if df_full.empty:
    st.warning(f"⚠️ Aucune donnée pour la campagne {CAMPAGNE_ACTUELLE}")
    st.info("💡 Utilisez le script d'import pour charger les données Excel")
    show_footer()
    st.stop()

# ==========================================
# KPIs
# ==========================================

df_actif = df_full[df_full['is_active'] == True] if 'is_active' in df_full.columns else df_full

col1, col2, col3, col4, col5, col6 = st.columns(6)

with col1:
    st.metric("📋 Lignes", len(df_actif))

with col2:
    total_net = df_actif['volume_net_t'].sum()
    st.metric("📦 Vol. Net", f"{total_net:,.0f} T")

with col3:
    total_brut = df_actif['volume_brut_t'].sum()
    st.metric("📦 Vol. Brut", f"{total_brut:,.0f} T")

with col4:
    total_ha = df_actif['hectares_necessaires'].sum()
    st.metric("🌾 Ha Base", f"{total_ha:,.1f}")

with col5:
    # Hectares ajustés (avec taux)
    total_ha_ajuste = df_actif['hectares_ajustes'].sum()
    delta = total_ha_ajuste - total_ha
    st.metric("🎯 Ha Ajustés", f"{total_ha_ajuste:,.1f}", 
              delta=f"{delta:+.1f}" if delta != 0 else None,
              delta_color="normal")

with col6:
    nb_varietes = df_actif['variete'].nunique()
    st.metric("🌱 Variétés", nb_varietes)

st.markdown("---")

# ==========================================
# ONGLETS PRINCIPAUX
# ==========================================

tab1, tab2, tab3 = st.tabs(["📋 Plan de Récolte", "🎯 Ajuster Couverture", "📊 Résumé Taux"])

# ==========================================
# ONGLET 1 : PLAN DE RÉCOLTE (Principal)
# ==========================================

with tab1:
    # FILTRES
    st.markdown("#### 🔍 Filtres")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        mois_options = ["Tous"] + get_unique_values(df_full, 'mois')
        filtre_mois = st.selectbox("Mois", mois_options, key="filtre_mois")
    
    with col2:
        marque_options = ["Tous"] + get_unique_values(df_full, 'marque')
        filtre_marque = st.selectbox("Marque", marque_options, key="filtre_marque")
    
    with col3:
        type_options = ["Tous"] + get_unique_values(df_full, 'type_produit')
        filtre_type = st.selectbox("Type", type_options, key="filtre_type")
    
    with col4:
        variete_options = ["Tous"] + get_unique_values(df_full, 'variete')
        filtre_variete = st.selectbox("Variété", variete_options, key="filtre_variete")
    
    # Appliquer filtres
    df = df_full.copy()
    if filtre_mois != "Tous":
        df = df[df['mois'] == filtre_mois]
    if filtre_marque != "Tous":
        df = df[df['marque'] == filtre_marque]
    if filtre_type != "Tous":
        df = df[df['type_produit'] == filtre_type]
    if filtre_variete != "Tous":
        df = df[df['variete'] == filtre_variete]
    
    # Afficher nombre résultats
    if len(df) != len(df_full):
        st.info(f"🔍 {len(df)} ligne(s) après filtrage (sur {len(df_full)} total)")
    
    st.markdown("---")
    
    # FORMULAIRE AJOUT
    if CAN_EDIT and st.session_state.get('show_add_form', False):
        st.subheader("➕ Ajouter une ligne")
        
        # Initialiser new_data
        if 'new_data' not in st.session_state:
            st.session_state.new_data = {}
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.session_state.new_data['mois'] = st.selectbox(
                "Mois *", 
                options=MOIS_OPTIONS,
                format_func=lambda x: MOIS_LABELS.get(x, x),
                key="add_mois"
            )
            
            st.session_state.new_data['marque'] = st.selectbox(
                "Marque *",
                options=[""] + get_unique_values(df_full, 'marque'),
                key="add_marque"
            )
            
            st.session_state.new_data['type_produit'] = st.selectbox(
                "Type produit *",
                options=[""] + get_unique_values(df_full, 'type_produit'),
                key="add_type"
            )
            
            # === Variété : autocomplete suggère + saisie libre ===
            # Source : ref_varietes (table dédiée) union avec les variétés du plan actuel
            varietes_ref, col_src = get_varietes_referentielles()
            varietes_plan = get_unique_values(df_full, 'variete')
            # Union sans doublons, ordre = ref d'abord puis nouvelles du plan
            suggestions = sorted(set(varietes_ref) | set(varietes_plan))
            
            OPT_LIBRE = "✏️ Autre — saisir manuellement"
            options_variete = [""] + suggestions + [OPT_LIBRE]
            
            choix_variete = st.selectbox(
                "Variété *",
                options=options_variete,
                key="add_variete_select"
            )
            
            if choix_variete == OPT_LIBRE:
                variete_saisie = st.text_input(
                    "Nom de la variété (saisie libre)",
                    key="add_variete_libre",
                    placeholder="Ex: Belami, Goldmarie..."
                ).strip()
                st.session_state.new_data['variete'] = variete_saisie
            else:
                st.session_state.new_data['variete'] = choix_variete
            
            # Caption explicative discrète
            if varietes_ref:
                st.caption(
                    f"🌱 {len(varietes_ref)} variété(s) chargée(s) depuis `ref_varietes`"
                    + (f" (+{len(set(varietes_plan) - set(varietes_ref))} du plan)"
                       if set(varietes_plan) - set(varietes_ref) else "")
                )
            elif varietes_plan:
                st.caption(
                    f"ℹ️ Suggestions issues du plan actuel ({len(varietes_plan)} variétés). "
                    f"Table `ref_varietes` non détectée."
                )
            else:
                st.caption("ℹ️ Aucune source de variétés. Utilisez « Autre » pour saisir librement.")
        
        with col2:
            st.session_state.new_data['arrachage_quinzaine'] = st.text_input(
                "Quinzaine arrachage",
                key="add_quinzaine"
            )
            
            st.session_state.new_data['volume_net_t'] = st.number_input(
                "Volume net (T) *",
                min_value=0.0,
                value=0.0,
                step=10.0,
                key="add_volume"
            )
            
            st.session_state.new_data['dechets_pct'] = st.number_input(
                "Déchets %",
                min_value=0.0,
                max_value=50.0,
                value=15.0,
                step=1.0,
                key="add_dechets"
            )
            
            st.session_state.new_data['rendement_t_ha'] = st.number_input(
                "Rendement T/ha",
                min_value=10.0,
                max_value=100.0,
                value=40.0,
                step=1.0,
                key="add_rendement"
            )
        
        st.session_state.new_data['notes'] = st.text_area("Notes", key="add_notes")
        
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("💾 Enregistrer", type="primary", use_container_width=True, key="btn_save_add"):
                # Validation
                if not st.session_state.new_data.get('marque'):
                    st.error("❌ Marque obligatoire")
                elif not st.session_state.new_data.get('type_produit'):
                    st.error("❌ Type produit obligatoire")
                elif not st.session_state.new_data.get('variete'):
                    st.error("❌ Variété obligatoire")
                elif st.session_state.new_data.get('volume_net_t', 0) <= 0:
                    st.error("❌ Volume net doit être > 0")
                else:
                    success, message = add_record(st.session_state.new_data)
                    if success:
                        st.success(message)
                        st.session_state.show_add_form = False
                        st.session_state.pop('new_data', None)
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error(message)
        
        with col2:
            if st.button("❌ Annuler", use_container_width=True, key="btn_cancel_add"):
                st.session_state.show_add_form = False
                st.session_state.pop('new_data', None)
                st.rerun()
        
        st.markdown("---")
    
    # TABLEAU PRINCIPAL
    col_title, col_btn1, col_btn2 = st.columns([3, 1, 1])
    
    with col_title:
        st.subheader(f"📋 Plan Récolte {CAMPAGNE_ACTUELLE}")
    
    with col_btn1:
        if CAN_EDIT:
            if st.button("➕ Ajouter", type="primary", use_container_width=True):
                st.session_state.show_add_form = not st.session_state.get('show_add_form', False)
                st.rerun()
    
    with col_btn2:
        if st.button("🔄 Actualiser", use_container_width=True):
            st.rerun()
    
    # Préparer DataFrame pour affichage
    df_display = df[[
        'id', 'mois', 'marque', 'type_produit', 'variete', 
        'arrachage_quinzaine', 'volume_net_t', 'dechets_pct', 
        'volume_brut_t', 'rendement_t_ha', 'hectares_necessaires',
        'taux_couverture_cible', 'hectares_ajustes', 'notes'
    ]].copy()
    
    # Renommer colonnes pour affichage
    df_display = df_display.rename(columns={
        'mois': 'Mois',
        'marque': 'Marque',
        'type_produit': 'Type',
        'variete': 'Variété',
        'arrachage_quinzaine': 'Quinzaine',
        'volume_net_t': 'Vol. Net (T)',
        'dechets_pct': 'Déchets %',
        'volume_brut_t': 'Vol. Brut (T)',
        'rendement_t_ha': 'Rdt T/ha',
        'hectares_necessaires': 'Ha Base',
        'taux_couverture_cible': 'Taux %',
        'hectares_ajustes': 'Ha Ajustés',
        'notes': 'Notes'
    })
    
    # Configuration colonnes
    column_config = {
        "id": None,  # Masquer
        "Mois": st.column_config.SelectboxColumn(
            "Mois",
            options=MOIS_OPTIONS,
            required=True
        ),
        "Marque": st.column_config.SelectboxColumn(
            "Marque",
            options=get_unique_values(df_full, 'marque'),
            required=True
        ),
        "Type": st.column_config.SelectboxColumn(
            "Type",
            options=get_unique_values(df_full, 'type_produit'),
            required=True
        ),
        "Variété": st.column_config.SelectboxColumn(
            "Variété",
            options=get_unique_values(df_full, 'variete'),
            required=True
        ),
        "Vol. Net (T)": st.column_config.NumberColumn(
            "Vol. Net (T)",
            format="%.1f",
            min_value=0
        ),
        "Déchets %": st.column_config.NumberColumn(
            "Déchets %",
            format="%.0f",
            min_value=0,
            max_value=50
        ),
        "Vol. Brut (T)": st.column_config.NumberColumn(
            "Vol. Brut (T)",
            format="%.1f",
            disabled=True
        ),
        "Rdt T/ha": st.column_config.NumberColumn(
            "Rdt T/ha",
            format="%.0f",
            min_value=10,
            max_value=100
        ),
        "Ha Base": st.column_config.NumberColumn(
            "Ha Base",
            format="%.2f",
            disabled=True
        ),
        "Taux %": st.column_config.NumberColumn(
            "Taux %",
            format="%d%%",
            disabled=True,
            help="Ajustable dans l'onglet 'Ajuster Couverture'"
        ),
        "Ha Ajustés": st.column_config.NumberColumn(
            "Ha Ajustés",
            format="%.2f",
            disabled=True,
            help="= Ha Base × Taux %"
        )
    }
    
    # Stocker original pour comparaison
    if 'original_df_plan' not in st.session_state:
        st.session_state.original_df_plan = df_display.copy()
    
    # Afficher tableau éditable
    if CAN_EDIT:
        edited_df = st.data_editor(
            df_display,
            column_config=column_config,
            use_container_width=True,
            num_rows="fixed",
            disabled=['id', 'Vol. Brut (T)', 'Ha Base', 'Taux %', 'Ha Ajustés'],
            hide_index=True,
            key="plan_editor"
        )
    else:
        st.dataframe(
            df_display,
            column_config=column_config,
            use_container_width=True,
            hide_index=True
        )
        edited_df = df_display
    
    # BOUTONS ACTIONS
    if CAN_EDIT:
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            if st.button("💾 Enregistrer modifs", type="primary", use_container_width=True):
                # Reconvertir noms colonnes
                edited_df_save = edited_df.rename(columns={
                    'Mois': 'mois', 'Marque': 'marque', 'Type': 'type_produit',
                    'Variété': 'variete', 'Quinzaine': 'arrachage_quinzaine',
                    'Vol. Net (T)': 'volume_net_t', 'Déchets %': 'dechets_pct',
                    'Vol. Brut (T)': 'volume_brut_t', 'Rdt T/ha': 'rendement_t_ha',
                    'Ha Base': 'hectares_necessaires', 'Taux %': 'taux_couverture_cible',
                    'Ha Ajustés': 'hectares_ajustes', 'Notes': 'notes'
                })
                
                original_df_save = st.session_state.original_df_plan.rename(columns={
                    'Mois': 'mois', 'Marque': 'marque', 'Type': 'type_produit',
                    'Variété': 'variete', 'Quinzaine': 'arrachage_quinzaine',
                    'Vol. Net (T)': 'volume_net_t', 'Déchets %': 'dechets_pct',
                    'Vol. Brut (T)': 'volume_brut_t', 'Rdt T/ha': 'rendement_t_ha',
                    'Ha Base': 'hectares_necessaires', 'Taux %': 'taux_couverture_cible',
                    'Ha Ajustés': 'hectares_ajustes', 'Notes': 'notes'
                })
                
                success, message = save_changes(original_df_save, edited_df_save)
                if success:
                    st.success(message)
                    st.session_state.original_df_plan = edited_df.copy()
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error(message)
        
        with col2:
            if st.button("🔄 Recalculer besoins", use_container_width=True, key="btn_recalc_plan"):
                success, message = recalculer_besoins()
                if success:
                    st.success(message)
                    st.balloons()
                else:
                    st.error(message)
    
    # GESTION ACTIVATION / DÉSACTIVATION
    if CAN_DELETE:
        st.markdown("---")
        st.subheader("🔒 Gestion activation")
        
        # Sélecteur de ligne
        options = [f"{row['id']} - {row['Mois']} | {row['Marque']} | {row['Variété']} ({row['Vol. Net (T)']:.0f}T)" 
                   for _, row in df_display.iterrows()]
        
        if options:
            selected = st.selectbox("Sélectionner une ligne", options, key="select_activation")
            
            col1, col2 = st.columns(2)
            
            with col1:
                if st.button("🔒 Désactiver", use_container_width=True):
                    record_id = int(selected.split(" - ")[0])
                    success, message = delete_record(record_id)
                    if success:
                        st.success(message)
                        st.rerun()
                    else:
                        st.error(message)
            
            with col2:
                if st.button("🔓 Réactiver", use_container_width=True):
                    record_id = int(selected.split(" - ")[0])
                    success, message = reactivate_record(record_id)
                    if success:
                        st.success(message)
                        st.rerun()
                    else:
                        st.error(message)

# ==========================================
# ONGLET 2 : AJUSTER COUVERTURE
# ==========================================

with tab2:
    st.subheader("🎯 Ajuster le Taux de Couverture Cible")
    
    st.markdown("""
    **Comment ça marche ?**
    - **0%** = La ligne est **ignorée** dans le calcul des besoins
    - **100%** = Besoin **normal** (par défaut)
    - **200%** = Besoin **doublé** (évolution client à la hausse)
    - **50%** = Besoin **réduit de moitié** (baisse prévue)
    
    👉 Sélectionnez une ligne, ajustez le taux, puis cliquez sur "**Recalculer besoins**" pour mettre à jour les pages 14-15-16.
    """)
    
    st.markdown("---")
    
    if not CAN_EDIT:
        st.warning("🔒 Vous n'avez pas les droits de modification")
    else:
        # Préparer données pour sélection
        df_taux = df_full[df_full['is_active'] == True].copy()
        
        if not df_taux.empty:
            # Créer DataFrame pour affichage
            df_taux_display = df_taux[[
                'id', 'mois', 'marque', 'type_produit', 'variete',
                'volume_net_t', 'hectares_necessaires', 'taux_couverture_cible', 'hectares_ajustes'
            ]].copy()
            
            df_taux_display = df_taux_display.rename(columns={
                'mois': 'Mois',
                'marque': 'Marque', 
                'type_produit': 'Type',
                'variete': 'Variété',
                'volume_net_t': 'Vol. Net (T)',
                'hectares_necessaires': 'Ha Base',
                'taux_couverture_cible': 'Taux %',
                'hectares_ajustes': 'Ha Ajustés'
            })
            
            # Filtres rapides
            col1, col2 = st.columns(2)
            with col1:
                filtre_mois_taux = st.selectbox(
                    "Filtrer par mois",
                    ["Tous"] + get_unique_values(df_full, 'mois'),
                    key="filtre_mois_taux"
                )
            with col2:
                filtre_variete_taux = st.selectbox(
                    "Filtrer par variété",
                    ["Tous"] + get_unique_values(df_full, 'variete'),
                    key="filtre_variete_taux"
                )
            
            # Appliquer filtres
            if filtre_mois_taux != "Tous":
                df_taux_display = df_taux_display[df_taux_display['Mois'] == filtre_mois_taux]
            if filtre_variete_taux != "Tous":
                df_taux_display = df_taux_display[df_taux_display['Variété'] == filtre_variete_taux]
            
            st.markdown(f"**{len(df_taux_display)} ligne(s)** - Sélectionnez une ligne :")
            
            # Tableau sélectionnable
            column_config_taux = {
                "id": None,
                "Mois": st.column_config.TextColumn("Mois"),
                "Marque": st.column_config.TextColumn("Marque"),
                "Type": st.column_config.TextColumn("Type"),
                "Variété": st.column_config.TextColumn("Variété"),
                "Vol. Net (T)": st.column_config.NumberColumn("Vol. Net (T)", format="%.0f"),
                "Ha Base": st.column_config.NumberColumn("Ha Base", format="%.2f"),
                "Taux %": st.column_config.NumberColumn("Taux %", format="%d%%"),
                "Ha Ajustés": st.column_config.NumberColumn("Ha Ajustés", format="%.2f")
            }
            
            event = st.dataframe(
                df_taux_display,
                column_config=column_config_taux,
                use_container_width=True,
                hide_index=True,
                on_select="rerun",
                selection_mode="single-row",
                key="taux_selector"
            )
            
            # Récupérer sélection
            selected_rows = event.selection.rows if hasattr(event, 'selection') else []
            
            st.markdown("---")
            
            if len(selected_rows) > 0:
                selected_idx = selected_rows[0]
                selected_row = df_taux_display.iloc[selected_idx]
                record_id = int(selected_row['id'])
                
                # Afficher détails
                st.success(f"✅ Ligne sélectionnée : **{selected_row['Marque']}** | {selected_row['Type']} | **{selected_row['Variété']}** - {selected_row['Mois']}")
                
                col1, col2 = st.columns([2, 1])
                
                with col1:
                    # Slider taux
                    current_taux = int(selected_row['Taux %'])
                    ha_base = float(selected_row['Ha Base'])
                    
                    nouveau_taux = st.slider(
                        "🎯 Taux de couverture cible",
                        min_value=0,
                        max_value=500,
                        value=current_taux,
                        step=10,
                        format="%d%%",
                        key="slider_taux",
                        help="0% = ignoré, 100% = normal, 200% = doublé"
                    )
                    
                    # Calcul impact
                    ha_nouveau = ha_base * nouveau_taux / 100
                    delta_ha = ha_nouveau - ha_base
                    
                    # Afficher impact
                    if nouveau_taux == 0:
                        st.warning(f"⚠️ **Taux 0%** : Cette ligne sera **ignorée** dans les besoins")
                    elif nouveau_taux < 100:
                        st.info(f"📉 **Réduction** : {ha_base:.2f} ha → **{ha_nouveau:.2f} ha** ({delta_ha:+.2f} ha)")
                    elif nouveau_taux == 100:
                        st.success(f"✅ **Normal** : {ha_nouveau:.2f} ha (pas de changement)")
                    else:
                        st.warning(f"📈 **Augmentation** : {ha_base:.2f} ha → **{ha_nouveau:.2f} ha** ({delta_ha:+.2f} ha)")
                
                with col2:
                    st.markdown("### 📊 Aperçu")
                    
                    # Carte visuelle
                    if nouveau_taux == 0:
                        color_class = "taux-0"
                        emoji = "🚫"
                    elif nouveau_taux == 100:
                        color_class = "taux-100"
                        emoji = "✅"
                    else:
                        color_class = "taux-200"
                        emoji = "📈" if nouveau_taux > 100 else "📉"
                    
                    st.markdown(f"""
                    <div class="taux-card {color_class}">
                        <h2 style="margin:0; text-align:center;">{emoji} {nouveau_taux}%</h2>
                        <p style="margin:0.5rem 0 0 0; text-align:center; font-size:1.2rem;">
                            <strong>{ha_nouveau:.2f} ha</strong>
                        </p>
                    </div>
                    """, unsafe_allow_html=True)
                
                # Bouton appliquer
                st.markdown("---")
                
                col1, col2, col3 = st.columns([1, 1, 2])
                
                with col1:
                    if st.button("💾 Appliquer ce taux", type="primary", use_container_width=True):
                        success, message = update_taux_couverture(record_id, nouveau_taux)
                        if success:
                            st.success(message)
                            time.sleep(1)
                            st.rerun()
                        else:
                            st.error(message)
                
                with col2:
                    if st.button("🔄 Recalculer besoins", use_container_width=True, key="btn_recalc_taux"):
                        success, message = recalculer_besoins()
                        if success:
                            st.success(message)
                            st.balloons()
                        else:
                            st.error(message)
            else:
                st.info("👆 Sélectionnez une ligne dans le tableau ci-dessus pour ajuster son taux")
        else:
            st.warning("Aucune ligne active")

# ==========================================
# ONGLET 3 : RÉSUMÉ TAUX
# ==========================================

with tab3:
    st.subheader("📊 Résumé des Taux de Couverture")
    
    df_actif = df_full[df_full['is_active'] == True].copy()
    
    if not df_actif.empty:
        # Résumé par taux
        st.markdown("#### Par niveau de taux")
        
        resume_taux = df_actif.groupby('taux_couverture_cible').agg({
            'id': 'count',
            'hectares_necessaires': 'sum',
            'hectares_ajustes': 'sum'
        }).reset_index()
        
        resume_taux.columns = ['Taux %', 'Nb Lignes', 'Ha Base', 'Ha Ajustés']
        resume_taux['Taux %'] = resume_taux['Taux %'].astype(int).astype(str) + '%'
        
        st.dataframe(
            resume_taux,
            column_config={
                "Taux %": st.column_config.TextColumn("Taux"),
                "Nb Lignes": st.column_config.NumberColumn("Nb Lignes", format="%d"),
                "Ha Base": st.column_config.NumberColumn("Ha Base", format="%.1f"),
                "Ha Ajustés": st.column_config.NumberColumn("Ha Ajustés", format="%.1f")
            },
            use_container_width=True,
            hide_index=True
        )
        
        # Lignes avec taux ≠ 100%
        st.markdown("---")
        st.markdown("#### ⚠️ Lignes avec taux ajusté (≠ 100%)")
        
        df_ajuste = df_actif[df_actif['taux_couverture_cible'] != 100].copy()
        
        if not df_ajuste.empty:
            df_ajuste_display = df_ajuste[[
                'mois', 'marque', 'type_produit', 'variete',
                'hectares_necessaires', 'taux_couverture_cible', 'hectares_ajustes'
            ]].copy()
            
            df_ajuste_display.columns = ['Mois', 'Marque', 'Type', 'Variété', 'Ha Base', 'Taux %', 'Ha Ajustés']
            
            st.dataframe(
                df_ajuste_display,
                column_config={
                    "Ha Base": st.column_config.NumberColumn("Ha Base", format="%.2f"),
                    "Taux %": st.column_config.NumberColumn("Taux %", format="%d%%"),
                    "Ha Ajustés": st.column_config.NumberColumn("Ha Ajustés", format="%.2f")
                },
                use_container_width=True,
                hide_index=True
            )
            
            st.info(f"📊 {len(df_ajuste)} ligne(s) avec taux ajusté")
        else:
            st.success("✅ Toutes les lignes sont à 100% (comportement normal)")
        
        # Totaux
        st.markdown("---")
        st.markdown("#### 📈 Impact Global")
        
        total_ha_base = df_actif['hectares_necessaires'].sum()
        total_ha_ajuste = df_actif['hectares_ajustes'].sum()
        delta = total_ha_ajuste - total_ha_base
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("🌾 Ha Base Total", f"{total_ha_base:,.1f}")
        
        with col2:
            st.metric("🎯 Ha Ajustés Total", f"{total_ha_ajuste:,.1f}")
        
        with col3:
            pct_change = (delta / total_ha_base * 100) if total_ha_base > 0 else 0
            st.metric(
                "📊 Écart", 
                f"{delta:+,.1f} ha",
                delta=f"{pct_change:+.1f}%",
                delta_color="normal"
            )

# ==========================================
# EXPORTS
# ==========================================

st.markdown("---")
st.subheader("📤 Exports")

col1, col2 = st.columns(2)

with col1:
    csv = df_full.to_csv(index=False).encode('utf-8')
    st.download_button(
        "📥 Export CSV",
        csv,
        f"plan_recolte_{CAMPAGNE_ACTUELLE}_{datetime.now().strftime('%Y%m%d')}.csv",
        "text/csv",
        use_container_width=True
    )

with col2:
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
        df_full.to_excel(writer, index=False, sheet_name='Plan')
    
    st.download_button(
        "📥 Export Excel",
        buffer.getvalue(),
        f"plan_recolte_{CAMPAGNE_ACTUELLE}_{datetime.now().strftime('%Y%m%d')}.xlsx",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True
    )

show_footer()
