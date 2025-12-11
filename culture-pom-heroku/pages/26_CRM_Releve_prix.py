import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, date, timedelta
from database import get_connection
from components import show_footer
from auth import is_authenticated, require_access, can_edit

st.set_page_config(page_title="Relevés de Prix - Culture Pom", page_icon="💰", layout="wide")

if not is_authenticated():
    st.warning("⚠️ Veuillez vous connecter")
    st.stop()

require_access("CRM")

st.markdown("""
<style>
    .block-container { padding-top: 1.5rem !important; }
    h1, h2, h3 { margin-top: 0.3rem !important; margin-bottom: 0.3rem !important; }
    .kpi-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        padding: 1rem;
        border-radius: 10px;
        text-align: center;
        margin: 0.3rem 0;
    }
    .kpi-value { font-size: 1.8rem; font-weight: bold; }
    .kpi-label { font-size: 0.85rem; opacity: 0.9; }
    .ligne-prix {
        background: #f8f9fa;
        padding: 0.8rem;
        border-radius: 8px;
        margin: 0.5rem 0;
        border-left: 4px solid #667eea;
    }
</style>
""", unsafe_allow_html=True)

st.title("💰 Relevés de Prix")
st.caption("Veille tarifaire et analyse des prix concurrents en magasin")
st.markdown("---")

# ==========================================
# FONCTIONS UTILITAIRES
# ==========================================

def safe_float(value, default=0.0):
    if value is None or pd.isna(value):
        return default
    try:
        return float(value)
    except:
        return default

def safe_int(value, default=0):
    if value is None or pd.isna(value):
        return default
    try:
        return int(value)
    except:
        return default

# ==========================================
# FONCTIONS DB - RÉFÉRENCES
# ==========================================

def get_magasins_dropdown():
    """Liste des magasins pour dropdown"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT m.id, 
                   COALESCE(e.libelle, m.nom_client) || ' - ' || m.ville || ' (' || COALESCE(m.departement, '??') || ')' as label
            FROM crm_magasins m
            LEFT JOIN ref_enseignes e ON m.enseigne_id = e.id
            WHERE m.is_active = TRUE
            ORDER BY COALESCE(e.libelle, m.nom_client), m.ville
        """)
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        return [(r['id'], r['label']) for r in rows]
    except Exception as e:
        st.error(f"Erreur magasins: {e}")
        return []

def get_marques_for_magasin(magasin_id):
    """Marques du magasin + La Championne + MDD"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        # Table renommée : crm_magasin_marques (sans 's' à magasin)
        cursor.execute("""
            SELECT DISTINCT m.id, m.nom
            FROM ref_marques_concurrentes m
            LEFT JOIN crm_magasin_marques mm ON m.id = mm.marque_id AND mm.is_active = TRUE
            WHERE m.is_active = TRUE
            AND (mm.magasin_id = %s OR m.nom IN ('La Championne', 'MDD'))
            ORDER BY 
                CASE WHEN m.nom = 'La Championne' THEN 0
                     WHEN m.nom = 'MDD' THEN 1
                     ELSE 2 END,
                m.nom
        """, (int(magasin_id),))
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        return [(r['id'], r['nom']) for r in rows]
    except Exception as e:
        st.error(f"Erreur marques: {e}")
        return []

def get_types_conditionnement():
    """Types de conditionnement"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, libelle FROM ref_types_conditionnement WHERE is_active = TRUE ORDER BY libelle")
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        return [(r['id'], r['libelle']) for r in rows]
    except:
        return []

def get_types_produit():
    """Types de produit pour relevés"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, libelle FROM ref_types_produit_releve WHERE is_active = TRUE ORDER BY ordre")
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        return [(r['id'], r['libelle']) for r in rows]
    except:
        return []

def create_type_conditionnement(libelle):
    """Ajoute un nouveau conditionnement"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        code = libelle.upper().replace(' ', '_').replace('/', '_')[:30]
        cursor.execute("""
            INSERT INTO ref_types_conditionnement (code, libelle)
            VALUES (%s, %s)
            ON CONFLICT (code) DO UPDATE SET is_active = TRUE
            RETURNING id
        """, (code, libelle.strip()))
        new_id = cursor.fetchone()['id']
        conn.commit()
        cursor.close()
        conn.close()
        return new_id
    except:
        return None

def create_type_produit(libelle):
    """Ajoute un nouveau type de produit"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        code = libelle.upper().replace(' ', '_').replace('/', '_')[:30]
        cursor.execute("SELECT COALESCE(MAX(ordre), 0) + 1 as next_ordre FROM ref_types_produit_releve")
        next_ordre = cursor.fetchone()['next_ordre']
        cursor.execute("""
            INSERT INTO ref_types_produit_releve (code, libelle, ordre)
            VALUES (%s, %s, %s)
            ON CONFLICT (code) DO UPDATE SET is_active = TRUE
            RETURNING id
        """, (code, libelle.strip(), next_ordre))
        new_id = cursor.fetchone()['id']
        conn.commit()
        cursor.close()
        conn.close()
        return new_id
    except:
        return None

# ==========================================
# FONCTIONS DB - RELEVÉS
# ==========================================

def get_or_create_releve(magasin_id, date_releve):
    """Récupère ou crée un relevé pour un magasin/date"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        username = st.session_state.get('username', 'system')
        
        # Chercher existant
        cursor.execute("""
            SELECT id FROM crm_releves_prix 
            WHERE magasin_id = %s AND date_releve = %s AND is_active = TRUE
        """, (int(magasin_id), date_releve))
        row = cursor.fetchone()
        
        if row:
            releve_id = row['id']
        else:
            # Créer nouveau
            cursor.execute("""
                INSERT INTO crm_releves_prix (magasin_id, date_releve, created_by)
                VALUES (%s, %s, %s)
                RETURNING id
            """, (int(magasin_id), date_releve, username))
            releve_id = cursor.fetchone()['id']
            conn.commit()
        
        cursor.close()
        conn.close()
        return releve_id
    except Exception as e:
        st.error(f"Erreur : {e}")
        return None

def add_ligne_releve(releve_id, marque_id, conditionnement_id, type_produit_id, poids_kg, is_bio, prix_unitaire):
    """Ajoute une ligne de prix au relevé"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Calculer prix/kg
        prix_kg = round(prix_unitaire / poids_kg, 2) if poids_kg > 0 else None
        
        cursor.execute("""
            INSERT INTO crm_releves_prix_lignes 
            (releve_id, marque_id, type_conditionnement_id, type_produit_id, poids_kg, is_bio, prix_unitaire, prix_kg)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (int(releve_id), int(marque_id), int(conditionnement_id), int(type_produit_id), 
              float(poids_kg), bool(is_bio), float(prix_unitaire), prix_kg))
        
        new_id = cursor.fetchone()['id']
        conn.commit()
        cursor.close()
        conn.close()
        return True, new_id
    except Exception as e:
        return False, str(e)

def get_lignes_releve(releve_id):
    """Récupère les lignes d'un relevé"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT 
                rpl.id, mc.nom as marque, tc.libelle as conditionnement,
                tp.libelle as type_produit, rpl.poids_kg, rpl.is_bio,
                rpl.prix_unitaire, rpl.prix_kg
            FROM crm_releves_prix_lignes rpl
            JOIN ref_marques_concurrentes mc ON rpl.marque_id = mc.id
            JOIN ref_types_conditionnement tc ON rpl.type_conditionnement_id = tc.id
            JOIN ref_types_produit_releve tp ON rpl.type_produit_id = tp.id
            WHERE rpl.releve_id = %s
            ORDER BY rpl.created_at DESC
        """, (int(releve_id),))
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        return pd.DataFrame(rows) if rows else pd.DataFrame()
    except:
        return pd.DataFrame()

def delete_ligne_releve(ligne_id):
    """Supprime une ligne de relevé"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM crm_releves_prix_lignes WHERE id = %s", (int(ligne_id),))
        conn.commit()
        cursor.close()
        conn.close()
        return True
    except:
        return False

def get_historique_releves(limit=50):
    """Récupère l'historique des relevés"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT 
                rp.id, rp.date_releve, 
                COALESCE(e.libelle, m.nom_client) as enseigne, 
                m.ville, m.departement,
                COUNT(rpl.id) as nb_lignes,
                rp.created_by, rp.created_at
            FROM crm_releves_prix rp
            JOIN crm_magasins m ON rp.magasin_id = m.id
            LEFT JOIN ref_enseignes e ON m.enseigne_id = e.id
            LEFT JOIN crm_releves_prix_lignes rpl ON rp.id = rpl.releve_id
            WHERE rp.is_active = TRUE
            GROUP BY rp.id, rp.date_releve, e.libelle, m.nom_client, m.ville, m.departement, rp.created_by, rp.created_at
            ORDER BY rp.date_releve DESC, rp.created_at DESC
            LIMIT %s
        """, (limit,))
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        return pd.DataFrame(rows) if rows else pd.DataFrame()
    except Exception as e:
        st.error(f"Erreur historique: {e}")
        return pd.DataFrame()

# ==========================================
# FONCTIONS DB - ANALYSES
# ==========================================

def get_all_releves_data():
    """Récupère toutes les données pour analyses"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM v_releves_prix_complet ORDER BY date_releve DESC")
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        if rows:
            df = pd.DataFrame(rows)
            # Convertir types
            for col in ['prix_unitaire', 'prix_kg', 'poids_kg', 'latitude', 'longitude']:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
            return df
        return pd.DataFrame()
    except:
        return pd.DataFrame()

def get_kpis():
    """KPIs globaux"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(DISTINCT releve_id) FROM v_releves_prix_complet")
        nb_releves = cursor.fetchone()[0] or 0
        
        cursor.execute("SELECT COUNT(*) FROM v_releves_prix_complet")
        nb_lignes = cursor.fetchone()[0] or 0
        
        cursor.execute("SELECT COUNT(DISTINCT magasin_id) FROM v_releves_prix_complet")
        nb_magasins = cursor.fetchone()[0] or 0
        
        cursor.execute("SELECT ROUND(AVG(prix_kg)::numeric, 2) FROM v_releves_prix_complet")
        prix_kg_moyen = cursor.fetchone()[0] or 0
        
        cursor.close()
        conn.close()
        
        return {
            'nb_releves': nb_releves,
            'nb_lignes': nb_lignes,
            'nb_magasins': nb_magasins,
            'prix_kg_moyen': float(prix_kg_moyen)
        }
    except:
        return {'nb_releves': 0, 'nb_lignes': 0, 'nb_magasins': 0, 'prix_kg_moyen': 0}

def get_stats_by_departement():
    """Stats par département pour carte"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT 
                departement,
                COUNT(DISTINCT magasin_id) as nb_magasins,
                COUNT(*) as nb_releves,
                ROUND(AVG(prix_kg)::numeric, 2) as prix_kg_moyen,
                MIN(prix_kg) as prix_kg_min,
                MAX(prix_kg) as prix_kg_max
            FROM v_releves_prix_complet
            WHERE departement IS NOT NULL
            GROUP BY departement
            ORDER BY departement
        """)
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        return pd.DataFrame(rows) if rows else pd.DataFrame()
    except:
        return pd.DataFrame()

# ==========================================
# INTERFACE - ONGLETS
# ==========================================

tab1, tab2, tab3 = st.tabs(["📝 Nouveau Relevé", "📋 Historique", "📊 Analyses"])

# ==========================================
# ONGLET 1 : NOUVEAU RELEVÉ
# ==========================================

with tab1:
    if not can_edit("CRM"):
        st.warning("⚠️ Vous n'avez pas les droits pour saisir un relevé")
    else:
        st.subheader("📝 Saisir un relevé de prix")
        
        # Sélection magasin et date
        col1, col2 = st.columns(2)
        
        magasins = get_magasins_dropdown()
        
        with col1:
            if magasins:
                magasin_options = [(0, "-- Sélectionner un magasin --")] + magasins
                selected_magasin = st.selectbox(
                    "🏪 Magasin *",
                    options=magasin_options,
                    format_func=lambda x: x[1],
                    key="sel_magasin"
                )
            else:
                st.warning("Aucun magasin disponible")
                selected_magasin = (0, "")
        
        with col2:
            date_releve = st.date_input("📅 Date du relevé *", value=date.today(), key="sel_date")
        
        st.markdown("---")
        
        # Si magasin sélectionné
        if selected_magasin[0] > 0:
            magasin_id = selected_magasin[0]
            
            # Récupérer/créer le relevé
            releve_id = get_or_create_releve(magasin_id, date_releve)
            
            if releve_id:
                # Charger les références
                marques = get_marques_for_magasin(magasin_id)
                conditionnements = get_types_conditionnement()
                types_produit = get_types_produit()
                
                # ==========================================
                # FORMULAIRE AJOUT LIGNE
                # ==========================================
                st.markdown("#### ➕ Ajouter un produit")
                
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    # Marque
                    if marques:
                        marque_options = [(0, "-- Marque --")] + marques
                        sel_marque = st.selectbox("🏷️ Marque *", marque_options, format_func=lambda x: x[1], key="add_marque")
                    else:
                        st.warning("Aucune marque pour ce magasin")
                        sel_marque = (0, "")
                    
                    # Type produit
                    if types_produit:
                        type_options = [(0, "-- Type produit --")] + types_produit + [(-1, "➕ Nouveau type...")]
                        sel_type = st.selectbox("🥔 Type produit *", type_options, format_func=lambda x: x[1], key="add_type")
                        
                        if sel_type[0] == -1:
                            new_type = st.text_input("Nouveau type", key="new_type_input")
                            if st.button("Ajouter type", key="btn_add_type"):
                                if new_type:
                                    new_id = create_type_produit(new_type)
                                    if new_id:
                                        st.success(f"✅ Type '{new_type}' ajouté")
                                        st.rerun()
                    else:
                        sel_type = (0, "")
                
                with col2:
                    # Conditionnement
                    if conditionnements:
                        cond_options = [(0, "-- Conditionnement --")] + conditionnements + [(-1, "➕ Nouveau...")]
                        sel_cond = st.selectbox("📦 Conditionnement *", cond_options, format_func=lambda x: x[1], key="add_cond")
                        
                        if sel_cond[0] == -1:
                            new_cond = st.text_input("Nouveau conditionnement", key="new_cond_input")
                            if st.button("Ajouter", key="btn_add_cond"):
                                if new_cond:
                                    new_id = create_type_conditionnement(new_cond)
                                    if new_id:
                                        st.success(f"✅ '{new_cond}' ajouté")
                                        st.rerun()
                    else:
                        sel_cond = (0, "")
                    
                    # Poids
                    poids_kg = st.number_input("⚖️ Poids (kg) *", min_value=0.1, max_value=50.0, value=2.0, step=0.5, key="add_poids")
                
                with col3:
                    # Bio
                    is_bio = st.checkbox("🌱 Bio", key="add_bio")
                    
                    # Prix
                    prix_unitaire = st.number_input("💰 Prix unitaire (€) *", min_value=0.01, max_value=100.0, value=2.99, step=0.10, format="%.2f", key="add_prix")
                    
                    # Prix/kg calculé
                    if poids_kg > 0:
                        prix_kg = prix_unitaire / poids_kg
                        st.metric("Prix/kg", f"{prix_kg:.2f} €")
                
                # Bouton ajouter
                if st.button("➕ Ajouter au relevé", type="primary", key="btn_add_ligne"):
                    # Validation
                    errors = []
                    if sel_marque[0] <= 0:
                        errors.append("Marque obligatoire")
                    if sel_type[0] <= 0:
                        errors.append("Type produit obligatoire")
                    if sel_cond[0] <= 0:
                        errors.append("Conditionnement obligatoire")
                    if poids_kg <= 0:
                        errors.append("Poids invalide")
                    if prix_unitaire <= 0:
                        errors.append("Prix invalide")
                    
                    if errors:
                        st.error("❌ " + ", ".join(errors))
                    else:
                        success, result = add_ligne_releve(
                            releve_id, sel_marque[0], sel_cond[0], sel_type[0],
                            poids_kg, is_bio, prix_unitaire
                        )
                        if success:
                            st.success("✅ Ligne ajoutée")
                            st.rerun()
                        else:
                            st.error(f"❌ {result}")
                
                # ==========================================
                # LIGNES DU RELEVÉ EN COURS
                # ==========================================
                st.markdown("---")
                st.markdown("#### 📋 Lignes du relevé")
                
                df_lignes = get_lignes_releve(releve_id)
                
                if not df_lignes.empty:
                    # Afficher chaque ligne avec bouton supprimer
                    for idx, row in df_lignes.iterrows():
                        col1, col2, col3 = st.columns([4, 1, 1])
                        
                        with col1:
                            bio_tag = "🌱 " if row['is_bio'] else ""
                            st.markdown(f"""
                            <div class="ligne-prix">
                                <strong>{bio_tag}{row['marque']}</strong> - {row['type_produit']}<br>
                                {row['conditionnement']} {row['poids_kg']}kg → 
                                <strong>{row['prix_unitaire']:.2f}€</strong> ({row['prix_kg']:.2f}€/kg)
                            </div>
                            """, unsafe_allow_html=True)
                        
                        with col2:
                            st.write(f"**{row['prix_kg']:.2f}€/kg**")
                        
                        with col3:
                            if st.button("🗑️", key=f"del_{row['id']}"):
                                if delete_ligne_releve(row['id']):
                                    st.rerun()
                    
                    st.info(f"📊 **{len(df_lignes)} produit(s)** dans ce relevé")
                else:
                    st.info("Aucun produit ajouté. Utilisez le formulaire ci-dessus.")
        else:
            st.info("👆 Sélectionnez un magasin pour commencer")

# ==========================================
# ONGLET 2 : HISTORIQUE
# ==========================================

with tab2:
    st.subheader("📋 Historique des relevés")
    
    df_hist = get_historique_releves(100)
    
    if not df_hist.empty:
        st.info(f"📊 **{len(df_hist)} relevé(s)**")
        
        # Tableau
        df_display = df_hist.copy()
        df_display['date_releve'] = pd.to_datetime(df_display['date_releve']).dt.strftime('%d/%m/%Y')
        df_display = df_display.rename(columns={
            'date_releve': 'Date',
            'enseigne': 'Enseigne',
            'ville': 'Ville',
            'departement': 'Dept',
            'nb_lignes': 'Produits',
            'created_by': 'Par'
        })
        
        st.dataframe(
            df_display[['Date', 'Enseigne', 'Ville', 'Dept', 'Produits', 'Par']],
            use_container_width=True,
            hide_index=True
        )
    else:
        st.info("Aucun relevé enregistré")

# ==========================================
# ONGLET 3 : ANALYSES
# ==========================================

with tab3:
    st.subheader("📊 Analyses des prix")
    
    # KPIs
    kpis = get_kpis()
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-value">{kpis['nb_releves']}</div>
            <div class="kpi-label">📝 Relevés</div>
        </div>
        """, unsafe_allow_html=True)
    with col2:
        st.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-value">{kpis['nb_lignes']}</div>
            <div class="kpi-label">📦 Produits</div>
        </div>
        """, unsafe_allow_html=True)
    with col3:
        st.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-value">{kpis['nb_magasins']}</div>
            <div class="kpi-label">🏪 Magasins</div>
        </div>
        """, unsafe_allow_html=True)
    with col4:
        st.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-value">{kpis['prix_kg_moyen']:.2f}€</div>
            <div class="kpi-label">💰 Prix/kg moyen</div>
        </div>
        """, unsafe_allow_html=True)
    
    st.markdown("---")
    
    # Charger données
    df_all = get_all_releves_data()
    
    if not df_all.empty:
        # Filtres
        st.markdown("#### 🔍 Filtres")
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            types_produit_list = ["Tous"] + sorted(df_all['type_produit'].dropna().unique().tolist())
            f_type = st.selectbox("Type produit", types_produit_list, key="f_type")
        
        with col2:
            cond_list = ["Tous"] + sorted(df_all['conditionnement'].dropna().unique().tolist())
            f_cond = st.selectbox("Conditionnement", cond_list, key="f_cond")
        
        with col3:
            marques_list = ["Toutes"] + sorted(df_all['marque'].dropna().unique().tolist())
            f_marque = st.selectbox("Marque", marques_list, key="f_marque")
        
        with col4:
            f_bio = st.selectbox("Bio", ["Tous", "Bio", "Conventionnel"], key="f_bio")
        
        # Appliquer filtres
        df_filtered = df_all.copy()
        if f_type != "Tous":
            df_filtered = df_filtered[df_filtered['type_produit'] == f_type]
        if f_cond != "Tous":
            df_filtered = df_filtered[df_filtered['conditionnement'] == f_cond]
        if f_marque != "Toutes":
            df_filtered = df_filtered[df_filtered['marque'] == f_marque]
        if f_bio != "Tous":
            df_filtered = df_filtered[df_filtered['categorie_bio'] == f_bio]
        
        st.info(f"📊 **{len(df_filtered)} ligne(s)** après filtrage")
        
        st.markdown("---")
        
        # Sous-onglets analyses
        ana1, ana2, ana3, ana4 = st.tabs(["📈 Évolution", "🏪 Par enseigne", "🗺️ Par département", "📊 Bio vs Conv."])
        
        # ==========================================
        # ANALYSE 1 : ÉVOLUTION TEMPORELLE
        # ==========================================
        with ana1:
            st.markdown("##### 📈 Évolution des prix dans le temps")
            
            if not df_filtered.empty and 'date_releve' in df_filtered.columns:
                # Grouper par date
                df_evol = df_filtered.groupby('date_releve').agg({
                    'prix_kg': 'mean',
                    'prix_unitaire': 'mean',
                    'ligne_id': 'count'
                }).reset_index()
                df_evol.columns = ['Date', 'Prix/kg moyen', 'Prix unit. moyen', 'Nb produits']
                df_evol = df_evol.sort_values('Date')
                
                st.line_chart(df_evol.set_index('Date')['Prix/kg moyen'])
                
                st.dataframe(df_evol, use_container_width=True, hide_index=True)
            else:
                st.info("Pas assez de données")
        
        # ==========================================
        # ANALYSE 2 : PAR ENSEIGNE
        # ==========================================
        with ana2:
            st.markdown("##### 🏪 Prix par enseigne")
            
            if not df_filtered.empty:
                df_ens = df_filtered.groupby('enseigne').agg({
                    'prix_kg': ['mean', 'min', 'max', 'count'],
                    'magasin_id': 'nunique'
                }).reset_index()
                df_ens.columns = ['Enseigne', 'Prix/kg moyen', 'Min', 'Max', 'Nb relevés', 'Nb magasins']
                df_ens = df_ens.sort_values('Prix/kg moyen')
                
                # Graphique barres
                st.bar_chart(df_ens.set_index('Enseigne')['Prix/kg moyen'])
                
                st.dataframe(df_ens, use_container_width=True, hide_index=True)
            else:
                st.info("Pas assez de données")
        
        # ==========================================
        # ANALYSE 3 : PAR DÉPARTEMENT (CARTE)
        # ==========================================
        with ana3:
            st.markdown("##### 🗺️ Prix par département")
            
            df_dept = get_stats_by_departement()
            
            if not df_dept.empty:
                # KPIs par département
                col1, col2 = st.columns(2)
                with col1:
                    st.metric("Départements couverts", len(df_dept))
                with col2:
                    st.metric("Prix/kg moyen global", f"{df_dept['prix_kg_moyen'].mean():.2f}€")
                
                # Tableau
                df_dept_display = df_dept.rename(columns={
                    'departement': 'Dept',
                    'nb_magasins': 'Magasins',
                    'nb_releves': 'Relevés',
                    'prix_kg_moyen': 'Prix/kg moy.',
                    'prix_kg_min': 'Min',
                    'prix_kg_max': 'Max'
                })
                st.dataframe(df_dept_display, use_container_width=True, hide_index=True)
                
                # Carte si coordonnées disponibles
                df_geo = df_filtered[df_filtered['latitude'].notna() & df_filtered['longitude'].notna()].copy()
                if not df_geo.empty:
                    st.markdown("**Carte des relevés**")
                    map_df = pd.DataFrame({
                        'lat': df_geo['latitude'].astype(float),
                        'lon': df_geo['longitude'].astype(float)
                    })
                    st.map(map_df, zoom=5)
            else:
                st.info("Pas de données par département")
        
        # ==========================================
        # ANALYSE 4 : BIO VS CONVENTIONNEL
        # ==========================================
        with ana4:
            st.markdown("##### 📊 Comparaison Bio vs Conventionnel")
            
            if not df_all.empty:
                df_bio = df_all.groupby('categorie_bio').agg({
                    'prix_kg': ['mean', 'min', 'max', 'count']
                }).reset_index()
                df_bio.columns = ['Catégorie', 'Prix/kg moyen', 'Min', 'Max', 'Nb produits']
                
                if len(df_bio) >= 2:
                    col1, col2 = st.columns(2)
                    
                    bio_row = df_bio[df_bio['Catégorie'] == 'Bio']
                    conv_row = df_bio[df_bio['Catégorie'] == 'Conventionnel']
                    
                    with col1:
                        if not bio_row.empty:
                            st.markdown(f"""
                            <div class="kpi-card" style="background: linear-gradient(135deg, #56ab2f 0%, #a8e063 100%);">
                                <div class="kpi-value">{bio_row['Prix/kg moyen'].values[0]:.2f}€</div>
                                <div class="kpi-label">🌱 Bio ({int(bio_row['Nb produits'].values[0])} produits)</div>
                            </div>
                            """, unsafe_allow_html=True)
                    
                    with col2:
                        if not conv_row.empty:
                            st.markdown(f"""
                            <div class="kpi-card" style="background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);">
                                <div class="kpi-value">{conv_row['Prix/kg moyen'].values[0]:.2f}€</div>
                                <div class="kpi-label">🥔 Conventionnel ({int(conv_row['Nb produits'].values[0])} produits)</div>
                            </div>
                            """, unsafe_allow_html=True)
                    
                    # Écart
                    if not bio_row.empty and not conv_row.empty:
                        ecart = bio_row['Prix/kg moyen'].values[0] - conv_row['Prix/kg moyen'].values[0]
                        pct = (ecart / conv_row['Prix/kg moyen'].values[0]) * 100
                        st.info(f"📊 **Écart Bio/Conv.** : +{ecart:.2f}€/kg (+{pct:.1f}%)")
                
                st.dataframe(df_bio, use_container_width=True, hide_index=True)
            else:
                st.info("Pas assez de données")
    else:
        st.info("📊 Aucune donnée disponible. Commencez par saisir des relevés dans l'onglet 'Nouveau Relevé'.")

show_footer()
