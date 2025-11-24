import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from database import get_connection
from components import show_footer
from auth import is_authenticated

st.set_page_config(page_title="Prévisions Ventes - Culture Pom", page_icon="📈", layout="wide")

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
    /* Style pour les cellules extrapolées */
    .extrapolated {
        background-color: #fff3e0 !important;
        font-style: italic;
    }
</style>
""", unsafe_allow_html=True)

if not is_authenticated():
    st.warning("⚠️ Veuillez vous connecter pour accéder à cette page")
    st.stop()

st.title("📈 Prévisions de Ventes")
st.markdown("*Saisie des prévisions à 3 semaines + extrapolation à 5 semaines*")
st.markdown("---")

# ==========================================
# FONCTIONS UTILITAIRES
# ==========================================

def get_semaine_actuelle():
    """Retourne le numéro de semaine et l'année actuels"""
    today = datetime.now()
    iso_calendar = today.isocalendar()
    return iso_calendar[1], iso_calendar[0]  # (semaine, année)

def get_semaines_a_saisir():
    """Retourne les 3 semaines à saisir (S+1, S+2, S+3)"""
    semaine_actuelle, annee_actuelle = get_semaine_actuelle()
    semaines = []
    
    for i in range(1, 4):  # S+1, S+2, S+3
        sem = semaine_actuelle + i
        annee = annee_actuelle
        
        # Gestion changement d'année
        if sem > 52:
            sem = sem - 52
            annee = annee + 1
        
        semaines.append((annee, sem))
    
    return semaines

def get_semaines_extrapolees(semaines_saisies):
    """Retourne les 2 semaines extrapolées (S+4, S+5)"""
    derniere_annee, derniere_sem = semaines_saisies[-1]
    semaines = []
    
    for i in range(1, 3):  # +1, +2 après la dernière saisie
        sem = derniere_sem + i
        annee = derniere_annee
        
        if sem > 52:
            sem = sem - 52
            annee = annee + 1
        
        semaines.append((annee, sem))
    
    return semaines

def format_semaine(annee, semaine):
    """Formate une semaine pour affichage"""
    return f"S{semaine:02d}/{annee}"

def get_produits_commerciaux():
    """Récupère tous les produits commerciaux actifs"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT code_produit, marque, libelle, code_variete
            FROM ref_produits_commerciaux
            WHERE is_active = TRUE
            ORDER BY marque, libelle
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

def get_previsions(semaines):
    """Récupère les prévisions pour les semaines données"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Construire la clause WHERE pour les semaines
        conditions = " OR ".join([f"(annee = {a} AND semaine = {s})" for a, s in semaines])
        
        cursor.execute(f"""
            SELECT code_produit_commercial, annee, semaine, quantite_prevue_tonnes
            FROM previsions_ventes
            WHERE {conditions}
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

def get_previsions_historique():
    """Récupère les prévisions passées"""
    try:
        semaine_actuelle, annee_actuelle = get_semaine_actuelle()
        
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT pv.code_produit_commercial, pv.annee, pv.semaine, pv.quantite_prevue_tonnes,
                   pc.marque, pc.libelle
            FROM previsions_ventes pv
            LEFT JOIN ref_produits_commerciaux pc ON pv.code_produit_commercial = pc.code_produit
            WHERE (pv.annee < %s) OR (pv.annee = %s AND pv.semaine <= %s)
            ORDER BY pv.annee DESC, pv.semaine DESC, pc.marque, pc.libelle
        """, (annee_actuelle, annee_actuelle, semaine_actuelle))
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        
        if rows:
            return pd.DataFrame(rows)
        return pd.DataFrame()
    except Exception as e:
        st.error(f"❌ Erreur : {str(e)}")
        return pd.DataFrame()

def save_previsions(df_previsions):
    """Sauvegarde les prévisions (UPSERT)"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        updated = 0
        inserted = 0
        
        for _, row in df_previsions.iterrows():
            code_produit = row['code_produit']
            annee = int(row['annee'])
            semaine = int(row['semaine'])
            quantite = float(row['quantite']) if pd.notna(row['quantite']) else 0.0
            
            # Vérifier si existe déjà
            cursor.execute("""
                SELECT id FROM previsions_ventes
                WHERE code_produit_commercial = %s AND annee = %s AND semaine = %s
            """, (code_produit, annee, semaine))
            
            existing = cursor.fetchone()
            
            if existing:
                cursor.execute("""
                    UPDATE previsions_ventes
                    SET quantite_prevue_tonnes = %s, updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                """, (quantite, existing['id']))
                updated += 1
            else:
                cursor.execute("""
                    INSERT INTO previsions_ventes (code_produit_commercial, annee, semaine, quantite_prevue_tonnes)
                    VALUES (%s, %s, %s, %s)
                """, (code_produit, annee, semaine, quantite))
                inserted += 1
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return True, f"✅ Enregistré : {updated} mis à jour, {inserted} créés"
    except Exception as e:
        if 'conn' in locals():
            conn.rollback()
        return False, f"❌ Erreur : {str(e)}"

def calculer_extrapolation(valeurs):
    """Calcule l'extrapolation (moyenne des 3 semaines saisies)"""
    valeurs_valides = [v for v in valeurs if pd.notna(v) and v > 0]
    if len(valeurs_valides) > 0:
        return sum(valeurs_valides) / len(valeurs_valides)
    return 0.0

# ==========================================
# CALCULS
# ==========================================

# Semaines
semaine_actuelle, annee_actuelle = get_semaine_actuelle()
semaines_saisie = get_semaines_a_saisir()
semaines_extrapol = get_semaines_extrapolees(semaines_saisie)
toutes_semaines = semaines_saisie + semaines_extrapol

# Produits
produits = get_produits_commerciaux()

# Prévisions existantes pour les 3 semaines à saisir
previsions_existantes = get_previsions(semaines_saisie)

# ==========================================
# KPIs
# ==========================================

if not previsions_existantes.empty and not produits.empty:
    # Calculer totaux par semaine
    totaux_semaines = {}
    for annee, sem in semaines_saisie:
        mask = (previsions_existantes['annee'] == annee) & (previsions_existantes['semaine'] == sem)
        total = previsions_existantes.loc[mask, 'quantite_prevue_tonnes'].sum()
        totaux_semaines[f"S{sem:02d}"] = float(total) if pd.notna(total) else 0.0
    
    # Calculer extrapolation moyenne
    moyenne_extrapol = sum(totaux_semaines.values()) / 3 if len(totaux_semaines) == 3 else 0
    
    # Total 5 semaines
    total_5_sem = sum(totaux_semaines.values()) + (moyenne_extrapol * 2)
    
    # Nombre de produits avec prévision
    nb_produits_prev = previsions_existantes['code_produit_commercial'].nunique()
    
    # Affichage KPIs
    col1, col2, col3, col4, col5 = st.columns(5)
    
    with col1:
        sem1 = list(totaux_semaines.keys())[0] if totaux_semaines else "S?"
        val1 = list(totaux_semaines.values())[0] if totaux_semaines else 0
        st.metric(f"📊 {sem1}", f"{val1:.0f} T")
    
    with col2:
        sem2 = list(totaux_semaines.keys())[1] if len(totaux_semaines) > 1 else "S?"
        val2 = list(totaux_semaines.values())[1] if len(totaux_semaines) > 1 else 0
        st.metric(f"📊 {sem2}", f"{val2:.0f} T")
    
    with col3:
        sem3 = list(totaux_semaines.keys())[2] if len(totaux_semaines) > 2 else "S?"
        val3 = list(totaux_semaines.values())[2] if len(totaux_semaines) > 2 else 0
        st.metric(f"📊 {sem3}", f"{val3:.0f} T")
    
    with col4:
        st.metric("📈 Total 5 sem", f"{total_5_sem:.0f} T")
    
    with col5:
        st.metric("📦 Produits", f"{nb_produits_prev}/{len(produits)}")

st.markdown("---")

# ==========================================
# ONGLETS
# ==========================================

tab1, tab2, tab3 = st.tabs(["📝 Saisie (3 semaines)", "📊 Vue 5 semaines", "📜 Historique"])

# ==========================================
# ONGLET 1 : SAISIE
# ==========================================

with tab1:
    st.subheader(f"📝 Saisie des Prévisions - Semaine actuelle : S{semaine_actuelle:02d}/{annee_actuelle}")
    
    # Info semaines
    sem_labels = [format_semaine(a, s) for a, s in semaines_saisie]
    st.info(f"📅 Semaines à saisir : **{', '.join(sem_labels)}**")
    
    if produits.empty:
        st.warning("⚠️ Aucun produit commercial trouvé")
    else:
        # Construire le DataFrame pour la saisie
        # Colonnes : code_produit, marque, libelle, S49, S50, S51
        
        df_saisie = produits[['code_produit', 'marque', 'libelle']].copy()
        
        # Ajouter les colonnes pour chaque semaine
        for annee, sem in semaines_saisie:
            col_name = f"S{sem:02d}"
            df_saisie[col_name] = 0.0
            
            # Remplir avec les valeurs existantes
            if not previsions_existantes.empty:
                for idx, row in df_saisie.iterrows():
                    mask = (
                        (previsions_existantes['code_produit_commercial'] == row['code_produit']) &
                        (previsions_existantes['annee'] == annee) &
                        (previsions_existantes['semaine'] == sem)
                    )
                    vals = previsions_existantes.loc[mask, 'quantite_prevue_tonnes']
                    if len(vals) > 0:
                        df_saisie.loc[idx, col_name] = float(vals.iloc[0])
        
        # Filtre par marque
        marques = ["Toutes"] + sorted(df_saisie['marque'].dropna().unique().tolist())
        col_filtre, col_info = st.columns([2, 3])
        with col_filtre:
            filtre_marque = st.selectbox("Filtrer par marque", marques, key="filtre_marque_saisie")
        
        df_filtre = df_saisie.copy()
        if filtre_marque != "Toutes":
            df_filtre = df_filtre[df_filtre['marque'] == filtre_marque]
        
        with col_info:
            st.caption(f"💡 {len(df_filtre)} produits affichés")
        
        # Préparer pour édition
        df_edit = df_filtre.copy()
        df_edit = df_edit.reset_index(drop=True)
        
        # Configuration colonnes
        column_config = {
            "code_produit": st.column_config.TextColumn("Code Produit", disabled=True, width="medium"),
            "marque": st.column_config.TextColumn("Marque", disabled=True, width="small"),
            "libelle": st.column_config.TextColumn("Libellé", disabled=True, width="large"),
        }
        
        for annee, sem in semaines_saisie:
            col_name = f"S{sem:02d}"
            column_config[col_name] = st.column_config.NumberColumn(
                col_name,
                min_value=0.0,
                max_value=500.0,
                step=0.5,
                format="%.1f T",
                help=f"Prévision en tonnes pour la semaine {sem}/{annee}"
            )
        
        # Tableau éditable
        edited_df = st.data_editor(
            df_edit,
            column_config=column_config,
            use_container_width=True,
            hide_index=True,
            num_rows="fixed",
            key="previsions_editor"
        )
        
        # Bouton enregistrer
        col1, col2, col3 = st.columns([1, 1, 2])
        
        with col1:
            if st.button("💾 Enregistrer", type="primary", use_container_width=True):
                # Préparer les données pour sauvegarde
                records = []
                for _, row in edited_df.iterrows():
                    for annee, sem in semaines_saisie:
                        col_name = f"S{sem:02d}"
                        records.append({
                            'code_produit': row['code_produit'],
                            'annee': annee,
                            'semaine': sem,
                            'quantite': row[col_name]
                        })
                
                df_to_save = pd.DataFrame(records)
                success, msg = save_previsions(df_to_save)
                
                if success:
                    st.success(msg)
                    st.balloons()
                    st.rerun()
                else:
                    st.error(msg)
        
        with col2:
            if st.button("🔄 Actualiser", use_container_width=True):
                st.rerun()
        
        # Totaux en bas
        st.markdown("---")
        st.markdown("### 📊 Totaux par semaine")
        
        totaux = {}
        for annee, sem in semaines_saisie:
            col_name = f"S{sem:02d}"
            totaux[col_name] = edited_df[col_name].sum()
        
        cols_totaux = st.columns(len(totaux) + 1)
        for i, (sem, total) in enumerate(totaux.items()):
            with cols_totaux[i]:
                st.metric(sem, f"{total:.1f} T")
        
        with cols_totaux[-1]:
            total_global = sum(totaux.values())
            st.metric("Total 3 sem", f"{total_global:.1f} T")

# ==========================================
# ONGLET 2 : VUE 5 SEMAINES
# ==========================================

with tab2:
    st.subheader("📊 Vue à 5 Semaines (3 saisies + 2 extrapolées)")
    
    # Labels semaines
    sem_saisie_labels = [format_semaine(a, s) for a, s in semaines_saisie]
    sem_extrapol_labels = [format_semaine(a, s) for a, s in semaines_extrapol]
    
    st.info(f"📅 **Saisies** : {', '.join(sem_saisie_labels)} | **Extrapolées** : {', '.join(sem_extrapol_labels)}")
    
    if produits.empty:
        st.warning("⚠️ Aucun produit commercial trouvé")
    else:
        # Construire le DataFrame complet
        df_5sem = produits[['code_produit', 'marque', 'libelle']].copy()
        
        # Colonnes saisies
        for annee, sem in semaines_saisie:
            col_name = f"S{sem:02d}"
            df_5sem[col_name] = 0.0
            
            if not previsions_existantes.empty:
                for idx, row in df_5sem.iterrows():
                    mask = (
                        (previsions_existantes['code_produit_commercial'] == row['code_produit']) &
                        (previsions_existantes['annee'] == annee) &
                        (previsions_existantes['semaine'] == sem)
                    )
                    vals = previsions_existantes.loc[mask, 'quantite_prevue_tonnes']
                    if len(vals) > 0:
                        df_5sem.loc[idx, col_name] = float(vals.iloc[0])
        
        # Colonnes extrapolées (calculées)
        for annee, sem in semaines_extrapol:
            col_name = f"S{sem:02d}*"  # Astérisque pour indiquer extrapolé
            df_5sem[col_name] = 0.0
            
            # Calculer moyenne des 3 semaines saisies pour chaque produit
            for idx, row in df_5sem.iterrows():
                valeurs = [row[f"S{s:02d}"] for _, s in semaines_saisie]
                df_5sem.loc[idx, col_name] = calculer_extrapolation(valeurs)
        
        # Colonne Total 5 semaines
        cols_semaines = [f"S{s:02d}" for _, s in semaines_saisie] + [f"S{s:02d}*" for _, s in semaines_extrapol]
        df_5sem['Total 5 sem'] = df_5sem[cols_semaines].sum(axis=1)
        
        # Filtre par marque
        marques = ["Toutes"] + sorted(df_5sem['marque'].dropna().unique().tolist())
        filtre_marque_5 = st.selectbox("Filtrer par marque", marques, key="filtre_marque_5sem")
        
        df_filtre_5 = df_5sem.copy()
        if filtre_marque_5 != "Toutes":
            df_filtre_5 = df_filtre_5[df_filtre_5['marque'] == filtre_marque_5]
        
        # Configuration colonnes
        column_config_5 = {
            "code_produit": st.column_config.TextColumn("Code Produit", width="medium"),
            "marque": st.column_config.TextColumn("Marque", width="small"),
            "libelle": st.column_config.TextColumn("Libellé", width="large"),
            "Total 5 sem": st.column_config.NumberColumn("Total 5 sem", format="%.1f T"),
        }
        
        for annee, sem in semaines_saisie:
            col_name = f"S{sem:02d}"
            column_config_5[col_name] = st.column_config.NumberColumn(col_name, format="%.1f T")
        
        for annee, sem in semaines_extrapol:
            col_name = f"S{sem:02d}*"
            column_config_5[col_name] = st.column_config.NumberColumn(
                col_name, 
                format="%.1f T",
                help="⚡ Valeur extrapolée (moyenne des 3 semaines saisies)"
            )
        
        # Affichage
        st.dataframe(
            df_filtre_5,
            column_config=column_config_5,
            use_container_width=True,
            hide_index=True
        )
        
        # Totaux
        st.markdown("---")
        st.markdown("### 📊 Totaux par semaine")
        
        # Semaines saisies
        cols = st.columns(6)
        
        for i, (annee, sem) in enumerate(semaines_saisie):
            col_name = f"S{sem:02d}"
            total = df_5sem[col_name].sum()
            with cols[i]:
                st.metric(col_name, f"{total:.0f} T")
        
        # Semaines extrapolées
        for i, (annee, sem) in enumerate(semaines_extrapol):
            col_name = f"S{sem:02d}*"
            total = df_5sem[col_name].sum()
            with cols[3 + i]:
                st.metric(f"{col_name} ⚡", f"{total:.0f} T", help="Extrapolé")
        
        # Total global
        with cols[5]:
            total_5 = df_5sem['Total 5 sem'].sum()
            st.metric("🎯 Total", f"{total_5:.0f} T")
        
        # Légende
        st.caption("⚡ *Les colonnes avec astérisque (*) sont des valeurs extrapolées basées sur la moyenne des 3 semaines saisies*")

# ==========================================
# ONGLET 3 : HISTORIQUE
# ==========================================

with tab3:
    st.subheader("📜 Historique des Prévisions")
    
    historique = get_previsions_historique()
    
    if historique.empty:
        st.info("📭 Aucune prévision passée trouvée")
    else:
        # Filtres
        col1, col2 = st.columns(2)
        
        with col1:
            annees = ["Toutes"] + sorted(historique['annee'].unique().tolist(), reverse=True)
            filtre_annee = st.selectbox("Année", annees, key="filtre_annee_hist")
        
        with col2:
            semaines = ["Toutes"] + sorted(historique['semaine'].unique().tolist(), reverse=True)
            filtre_semaine = st.selectbox("Semaine", semaines, key="filtre_semaine_hist")
        
        df_hist = historique.copy()
        if filtre_annee != "Toutes":
            df_hist = df_hist[df_hist['annee'] == filtre_annee]
        if filtre_semaine != "Toutes":
            df_hist = df_hist[df_hist['semaine'] == filtre_semaine]
        
        # Formater semaine
        df_hist['Semaine'] = df_hist.apply(lambda r: f"S{r['semaine']:02d}/{r['annee']}", axis=1)
        
        # Renommer colonnes
        df_display_hist = df_hist[['Semaine', 'marque', 'libelle', 'quantite_prevue_tonnes']].copy()
        df_display_hist = df_display_hist.rename(columns={
            'marque': 'Marque',
            'libelle': 'Libellé',
            'quantite_prevue_tonnes': 'Quantité (T)'
        })
        
        st.dataframe(df_display_hist, use_container_width=True, hide_index=True)
        
        # Stats
        st.markdown("---")
        st.markdown("### 📊 Statistiques Historique")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            nb_semaines = historique[['annee', 'semaine']].drop_duplicates().shape[0]
            st.metric("Semaines", nb_semaines)
        
        with col2:
            total_hist = historique['quantite_prevue_tonnes'].sum()
            st.metric("Volume Total", f"{total_hist:.0f} T")
        
        with col3:
            moy_semaine = total_hist / nb_semaines if nb_semaines > 0 else 0
            st.metric("Moyenne/Semaine", f"{moy_semaine:.0f} T")

# ==========================================
# FOOTER
# ==========================================

show_footer()
