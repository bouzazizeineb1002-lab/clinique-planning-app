# app.py - Application Streamlit pour l'optimisation du planning clinique

import streamlit as st
import pulp
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import io

# Configuration de la page
st.set_page_config(
    page_title="Optimisation Planning Clinique",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Titre principal
st.title("🏥 Système d'Optimisation de Planning Chirurgical")
st.markdown("### Planification des patients électifs avec minimisation du temps libre")

# Initialisation des données dans session state
if 'patients' not in st.session_state:
    st.session_state.patients = []
if 'salles' not in st.session_state:
    st.session_state.salles = []
if 'chirurgiens' not in st.session_state:
    st.session_state.chirurgiens = []
if 'jours' not in st.session_state:
    st.session_state.jours = []
if 'compatibilite' not in st.session_state:
    st.session_state.compatibilite = {}
if 'planning_result' not in st.session_state:
    st.session_state.planning_result = None
if 'model_status' not in st.session_state:
    st.session_state.model_status = None

# Sidebar pour la navigation
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/3050/3050525.png", width=100)
    st.title("Navigation")
    
    page = st.radio(
        "Menu Principal",
        ["🏠 Accueil", 
         "👥 Gestion Patients", 
         "🚪 Gestion Salles", 
         "👨‍⚕️ Gestion Chirurgiens",
         "📅 Configuration Jours",
         "⚙️ Compatibilité",
         "🔧 Optimisation",
         "📊 Résultats"]
    )
    
    st.divider()
    st.caption("**Statut des données:**")
    col1, col2 = st.columns(2)
    with col1:
        st.metric("Patients", len(st.session_state.patients))
        st.metric("Salles", len(st.session_state.salles))
    with col2:
        st.metric("Chirurgiens", len(st.session_state.chirurgiens))
        st.metric("Jours", len(st.session_state.jours))
    
    if st.button("🗑️ Réinitialiser toutes les données"):
        for key in ['patients', 'salles', 'chirurgiens', 'jours', 'compatibilite', 'planning_result']:
            st.session_state[key] = [] if key != 'compatibilite' else {}
        st.rerun()

# =====================================================================
# PAGE ACCUEIL
# =====================================================================
if page == "🏠 Accueil":
    st.header("Bienvenue dans le système d'optimisation")
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.markdown("""
        ### 📋 Fonctionnalités principales
        
        1. **Gestion des données** :
           - Ajout/Modification des patients, salles, chirurgiens
           - Définition des compatibilités patient-chirurgien
           - Configuration des jours de planning
        
        2. **Optimisation automatique** :
           - Minimisation du temps libre des salles d'opération
           - Respect des contraintes de capacité
           - Allocation optimale des chirurgiens
        
        3. **Visualisation des résultats** :
           - Planning détaillé jour par jour
           - Statistiques d'utilisation
           - Export en différents formats
        
        ### 🚀 Pour commencer
        1. Ajoutez vos patients
        2. Configurez les salles et chirurgiens
        3. Définissez les jours de planning
        4. Lancez l'optimisation
        """)
    
    with col2:
        st.info("""
        **📊 Données actuelles:**
        - Patients: {} 
        - Salles: {}
        - Chirurgiens: {}
        - Jours: {}
        """.format(
            len(st.session_state.patients),
            len(st.session_state.salles),
            len(st.session_state.chirurgiens),
            len(st.session_state.jours)
        ))
        
        if st.session_state.planning_result:
            st.success("✅ Un planning optimisé est disponible")
            if st.button("📋 Voir le planning"):
                st.switch_page("📊 Résultats")
        else:
            st.warning("⚠️ Aucun planning généré")

# =====================================================================
# PAGE GESTION PATIENTS
# =====================================================================
elif page == "👥 Gestion Patients":
    st.header("👥 Gestion des Patients")
    
    tab1, tab2 = st.tabs(["➕ Ajouter Patient", "📋 Liste Patients"])
    
    with tab1:
        col1, col2 = st.columns(2)
        
        with col1:
            patient_id = st.text_input("ID Patient*", help="Identifiant unique du patient")
            nom = st.text_input("Nom*")
            prenom = st.text_input("Prénom*")
            age = st.number_input("Âge", min_value=0, max_value=120, value=40)
        
        with col2:
            duree = st.number_input(
                "Durée opération (minutes)*",
                min_value=15,
                max_value=480,
                value=120,
                help="Durée estimée de l'opération en minutes"
            )
            priorite = st.select_slider(
                "Priorité",
                options=[1, 2, 3, 4, 5],
                value=3,
                help="1 = Priorité la plus haute, 5 = Priorité la plus basse"
            )
            notes = st.text_area("Notes médicales")
        
        if st.button("💾 Enregistrer Patient", type="primary"):
            if patient_id and nom and prenom:
                nouveau_patient = {
                    'id': patient_id,
                    'nom': nom,
                    'prenom': prenom,
                    'age': age,
                    'duree': duree,
                    'priorite': priorite,
                    'notes': notes
                }
                
                # Vérifier si l'ID existe déjà
                ids_existants = [p['id'] for p in st.session_state.patients]
                if patient_id in ids_existants:
                    st.error(f"L'ID {patient_id} existe déjà!")
                else:
                    st.session_state.patients.append(nouveau_patient)
                    st.success(f"Patient {prenom} {nom} ajouté avec succès!")
                    st.rerun()
            else:
                st.error("Veuillez remplir les champs obligatoires (*)")
    
    with tab2:
        if st.session_state.patients:
            # Convertir en DataFrame pour l'affichage
            df_patients = pd.DataFrame(st.session_state.patients)
            
            # Formater l'affichage
            display_df = df_patients.copy()
            display_df['Durée'] = display_df['duree'].apply(lambda x: f"{x} min")
            display_df['Patient'] = display_df['nom'] + ' ' + display_df['prenom']
            
            st.dataframe(
                display_df[['id', 'Patient', 'age', 'Durée', 'priorite', 'notes']],
                use_container_width=True,
                hide_index=True
            )
            
            # Bouton de suppression
            patient_a_supprimer = st.selectbox(
                "Sélectionner un patient à supprimer",
                [f"{p['id']} - {p['nom']} {p['prenom']}" for p in st.session_state.patients],
                index=None,
                placeholder="Choisir un patient..."
            )
            
            if patient_a_supprimer and st.button("🗑️ Supprimer ce patient", type="secondary"):
                patient_id = patient_a_supprimer.split(" - ")[0]
                st.session_state.patients = [p for p in st.session_state.patients if p['id'] != patient_id]
                st.success("Patient supprimé!")
                st.rerun()
        else:
            st.info("Aucun patient enregistré. Ajoutez votre premier patient ci-dessus.")

# =====================================================================
# PAGE GESTION SALLES
# =====================================================================
elif page == "🚪 Gestion Salles":
    st.header("🚪 Gestion des Salles d'Opération")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Ajouter une Salle")
        
        salle_id = st.text_input("ID Salle*", key="salle_id")
        nom_salle = st.text_input("Nom de la Salle*", key="nom_salle")
        
        capacite_journaliere = st.number_input(
            "Capacité quotidienne (minutes)*",
            min_value=60,
            max_value=1440,
            value=480,
            help="Nombre maximum de minutes disponibles par jour"
        )
        
        equipements = st.multiselect(
            "Équipements disponibles",
            ["Imagerie", "Monitoring", "Ventilateur", "Scope", "Laser", "Robot", "Écran 4K"],
            default=["Monitoring", "Ventilateur"]
        )
        
        if st.button("➕ Ajouter Salle", type="primary"):
            if salle_id and nom_salle:
                nouvelle_salle = {
                    'id': salle_id,
                    'nom': nom_salle,
                    'capacite': capacite_journaliere,
                    'equipements': equipements
                }
                
                ids_existants = [s['id'] for s in st.session_state.salles]
                if salle_id in ids_existants:
                    st.error(f"L'ID {salle_id} existe déjà!")
                else:
                    st.session_state.salles.append(nouvelle_salle)
                    st.success(f"Salle {nom_salle} ajoutée!")
                    st.rerun()
            else:
                st.error("Veuillez remplir les champs obligatoires (*)")
    
    with col2:
        st.subheader("Salles disponibles")
        
        if st.session_state.salles:
            for salle in st.session_state.salles:
                with st.expander(f"🚪 {salle['nom']} ({salle['id']})"):
                    col_a, col_b = st.columns(2)
                    with col_a:
                        st.metric("Capacité", f"{salle['capacite']} min")
                        st.write(f"≈ {salle['capacite']/60:.1f} heures")
                    with col_b:
                        st.write("**Équipements:**")
                        for eq in salle['equipements']:
                            st.write(f"• {eq}")
                    
                    if st.button(f"Supprimer {salle['id']}", key=f"del_{salle['id']}"):
                        st.session_state.salles = [s for s in st.session_state.salles if s['id'] != salle['id']]
                        st.rerun()
        else:
            st.info("Aucune salle configurée. Ajoutez votre première salle.")

# =====================================================================
# PAGE GESTION CHIRURGIENS
# =====================================================================
elif page == "👨‍⚕️ Gestion Chirurgiens":
    st.header("👨‍⚕️ Gestion des Chirurgiens")
    
    tab1, tab2 = st.tabs(["Ajouter Chirurgien", "Liste Chirurgiens"])
    
    with tab1:
        col1, col2 = st.columns(2)
        
        with col1:
            chirurgien_id = st.text_input("ID Chirurgien*")
            nom_chir = st.text_input("Nom*")
            prenom_chir = st.text_input("Prénom*")
            specialite = st.selectbox(
                "Spécialité",
                ["Cardiologie", "Orthopédie", "Neurologie", "Chirurgie Générale", 
                 "Pédiatrie", "Traumatologie", "Plastique"]
            )
        
        with col2:
            disponibilite_quotidienne = st.number_input(
                "Disponibilité quotidienne (minutes)*",
                min_value=60,
                max_value=600,
                value=360,
                help="Nombre maximum de minutes de travail par jour"
            )
            competences = st.multiselect(
                "Compétences spécifiques",
                ["Microchirurgie", "Arthroscopie", "Laparoscopie", "Robotique", 
                 "Traumatologie lourde", "Pédiatrie", "Oncologie"]
            )
            matricule = st.text_input("Matricule/NRP")
        
        if st.button("👨‍⚕️ Ajouter Chirurgien", type="primary"):
            if chirurgien_id and nom_chir and prenom_chir:
                nouveau_chir = {
                    'id': chirurgien_id,
                    'nom': nom_chir,
                    'prenom': prenom_chir,
                    'specialite': specialite,
                    'disponibilite': disponibilite_quotidienne,
                    'competences': competences,
                    'matricule': matricule
                }
                
                ids_existants = [c['id'] for c in st.session_state.chirurgiens]
                if chirurgien_id in ids_existants:
                    st.error(f"L'ID {chirurgien_id} existe déjà!")
                else:
                    st.session_state.chirurgiens.append(nouveau_chir)
                    st.success(f"Chirurgien {prenom_chir} {nom_chir} ajouté!")
                    st.rerun()
            else:
                st.error("Veuillez remplir les champs obligatoires (*)")
    
    with tab2:
        if st.session_state.chirurgiens:
            df_chir = pd.DataFrame(st.session_state.chirurgiens)
            st.dataframe(
                df_chir[['id', 'nom', 'prenom', 'specialite', 'disponibilite', 'competences']],
                use_container_width=True,
                hide_index=True
            )
        else:
            st.info("Aucun chirurgien enregistré.")

# =====================================================================
# PAGE CONFIGURATION JOURS
# =====================================================================
elif page == "📅 Configuration Jours":
    st.header("📅 Configuration des Jours de Planning")
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.subheader("Définir les jours de planning")
        
        # Saisie du nombre de jours
        nb_jours = st.number_input(
            "Nombre de jours à planifier",
            min_value=1,
            max_value=14,
            value=5,
            help="Nombre de jours consécutifs pour le planning"
        )
        
        # Date de début
        date_debut = st.date_input(
            "Date de début du planning",
            datetime.now().date()
        )
        
        if st.button("📅 Générer les jours", type="primary"):
            st.session_state.jours = []
            for i in range(nb_jours):
                jour_date = date_debut + timedelta(days=i)
                jour_info = {
                    'numero': i + 1,
                    'date': jour_date.strftime("%Y-%m-%d"),
                    'jour_semaine': jour_date.strftime("%A"),
                    'label': f"Jour {i+1} ({jour_date.strftime('%d/%m/%Y')})"
                }
                st.session_state.jours.append(jour_info)
            st.success(f"{nb_jours} jours générés à partir du {date_debut.strftime('%d/%m/%Y')}")
            st.rerun()
    
    with col2:
        st.subheader("Jours configurés")
        if st.session_state.jours:
            for jour in st.session_state.jours:
                st.info(f"**{jour['label']}**")
        else:
            st.warning("Aucun jour configuré")

# =====================================================================
# PAGE COMPATIBILITE
# =====================================================================
elif page == "⚙️ Compatibilité":
    st.header("⚙️ Compatibilité Patients-Chirurgiens")
    st.markdown("Définir quels chirurgiens peuvent opérer quels patients")
    
    if not st.session_state.patients or not st.session_state.chirurgiens:
        st.error("Veuillez d'abord ajouter des patients et des chirurgiens")
    else:
        # Initialiser la matrice de compatibilité
        if 'compatibilite' not in st.session_state:
            st.session_state.compatibilite = {}
        
        # Créer un tableau de compatibilité
        st.subheader("Matrice de compatibilité")
        
        # Préparer les données
        patients_list = st.session_state.patients
        chirurgiens_list = st.session_state.chirurgiens
        
        # Créer un DataFrame pour l'affichage
        compat_data = []
        for patient in patients_list:
            row = {'Patient': f"{patient['id']} - {patient['nom']} {patient['prenom']}"}
            for chirurgien in chirurgiens_list:
                cle = (patient['id'], chirurgien['id'])
                # Valeur par défaut: compatible (1) si non défini
                valeur = st.session_state.compatibilite.get(cle, 1)
                row[chirurgien['id']] = valeur
            compat_data.append(row)
        
        df_compat = pd.DataFrame(compat_data)
        
        # Afficher avec possibilité d'édition
        edited_df = st.data_editor(
            df_compat,
            column_config={
                "Patient": st.column_config.TextColumn("Patient", width="medium"),
                **{ch['id']: st.column_config.CheckboxColumn(
                    ch['id'],
                    help=f"{ch['prenom']} {ch['nom']}",
                    default=True
                ) for ch in chirurgiens_list}
            },
            use_container_width=True,
            hide_index=True
        )
        
        # Sauvegarder les modifications
        if st.button("💾 Enregistrer les compatibilités"):
            for idx, row in edited_df.iterrows():
                patient_id = row['Patient'].split(" - ")[0]
                for chirurgien in chirurgiens_list:
                    chir_id = chirurgien['id']
                    cle = (patient_id, chir_id)
                    st.session_state.compatibilite[cle] = int(row[chir_id])
            st.success("Compatibilités enregistrées!")
        
        # Légende
        st.caption("✅ = Compatible (1)  ❌ = Non compatible (0)")

# =====================================================================
# PAGE OPTIMISATION
# =====================================================================
elif page == "🔧 Optimisation":
    st.header("🔧 Optimisation du Planning")
    
    # Vérifier les prérequis
    errors = []
    if not st.session_state.patients:
        errors.append("❌ Aucun patient défini")
    if not st.session_state.salles:
        errors.append("❌ Aucune salle définie")
    if not st.session_state.chirurgiens:
        errors.append("❌ Aucun chirurgien défini")
    if not st.session_state.jours:
        errors.append("❌ Aucun jour configuré")
    
    if errors:
        st.error("**Prérequis manquants:**")
        for error in errors:
            st.write(error)
        st.info("Veuillez compléter les données dans les onglets précédents")
    else:
        # Afficher un résumé
        st.subheader("Résumé des données")
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Patients", len(st.session_state.patients))
            duree_totale = sum(p['duree'] for p in st.session_state.patients)
            st.metric("Durée totale", f"{duree_totale} min")
        
        with col2:
            st.metric("Salles", len(st.session_state.salles))
            capacite_totale = sum(s['capacite'] * len(st.session_state.jours) for s in st.session_state.salles)
            st.metric("Capacité totale", f"{capacite_totale} min")
        
        with col3:
            st.metric("Chirurgiens", len(st.session_state.chirurgiens))
            st.metric("Jours", len(st.session_state.jours))
        
        # Paramètres d'optimisation
        st.subheader("Paramètres d'optimisation")
        
        col_a, col_b = st.columns(2)
        with col_a:
            time_limit = st.slider(
                "Limite de temps de calcul (secondes)",
                min_value=10,
                max_value=300,
                value=60
            )
        
        with col_b:
            objectif = st.selectbox(
                "Objectif principal",
                ["Minimiser temps libre", "Maximiser patients traités", "Équilibrer charge"]
            )
        
        # Bouton pour lancer l'optimisation
        st.divider()
        
        if st.button("🚀 Lancer l'optimisation", type="primary", use_container_width=True):
            with st.spinner("Optimisation en cours... Cela peut prendre quelques instants"):
                try:
                    # =============================================================
                    # ADAPTER VOTRE MODÈLE ICI
                    # =============================================================
                    
                    # 1. Préparer les données pour votre modèle
                    I = [p['id'] for p in st.session_state.patients]  # Patients
                    J = [s['id'] for s in st.session_state.salles]    # Salles
                    S = [c['id'] for c in st.session_state.chirurgiens] # Chirurgiens
                    K = [j['numero'] for j in st.session_state.jours]   # Jours
                    
                    # Durées des patients
                    t = {p['id']: p['duree'] for p in st.session_state.patients}
                    
                    # Capacités des salles (par jour)
                    b = {(j_id, k): next(s['capacite'] for s in st.session_state.salles if s['id'] == j_id)
                         for j_id in J for k in K}
                    
                    # Disponibilités des chirurgiens (par jour)
                    a = {(s_id, k): next(c['disponibilite'] for c in st.session_state.chirurgiens if c['id'] == s_id)
                         for s_id in S for k in K}
                    
                    # Matrice de compatibilité
                    m = {}
                    for patient in st.session_state.patients:
                        for chirurgien in st.session_state.chirurgiens:
                            cle = (patient['id'], chirurgien['id'])
                            m[cle] = st.session_state.compatibilite.get(cle, 1)
                    
                    # 2. Créer et résoudre le modèle
                    prob = pulp.LpProblem("ORS_idle_min", pulp.LpMinimize)
                    
                    # Variables
                    x = pulp.LpVariable.dicts('x', (I, J, K), cat='Binary')
                    y = pulp.LpVariable.dicts('y', (I, J, S, K), cat='Binary')
                    
                    # Objectif : minimiser temps libre
                    prob += pulp.lpSum(
                        b[(j, k)] - pulp.lpSum(t[i] * x[i][j][k] for i in I)
                        for j in J for k in K
                    ), "MinimizeIdleTime"
                    
                    # Contraintes
                    for i in I:
                        prob += pulp.lpSum(x[i][j][k] for j in J for k in K) <= 1, f"Once_{i}"
                    
                    for j in J:
                        for k in K:
                            prob += pulp.lpSum(t[i] * x[i][j][k] for i in I) <= b[(j, k)], f"ORcap_{j}_{k}"
                    
                    for s in S:
                        for k in K:
                            prob += pulp.lpSum(t[i] * y[i][j][s][k] for i in I for j in J) <= a[(s, k)], f"SurgeonCap_{s}_{k}"
                    
                    for i in I:
                        for j in J:
                            for s in S:
                                for k in K:
                                    prob += y[i][j][s][k] <= m.get((i, s), 0), f"Compat_{i}_{j}_{s}_{k}"
                    
                    for i in I:
                        for j in J:
                            for k in K:
                                prob += pulp.lpSum(y[i][j][s][k] for s in S) == x[i][j][k], f"Link_x_y_{i}_{j}_{k}"
                    
                    # Résoudre
                    solver = pulp.PULP_CBC_CMD(msg=False, timeLimit=time_limit)
                    prob.solve(solver)
                    
                    # 3. Traiter les résultats
                    planning_details = []
                    
                    for i in I:
                        scheduled = False
                        for j in J:
                            for k in K:
                                if pulp.value(x[i][j][k]) > 0.5:
                                    scheduled = True
                                    surgeons_assigned = [s for s in S if pulp.value(y[i][j][s][k]) > 0.5]
                                    
                                    # Récupérer les infos du patient
                                    patient_info = next(p for p in st.session_state.patients if p['id'] == i)
                                    salle_info = next(s for s in st.session_state.salles if s['id'] == j)
                                    jour_info = next(d for d in st.session_state.jours if d['numero'] == k)
                                    
                                    planning_details.append({
                                        'patient_id': i,
                                        'patient_nom': f"{patient_info['nom']} {patient_info['prenom']}",
                                        'patient_duree': patient_info['duree'],
                                        'salle_id': j,
                                        'salle_nom': salle_info['nom'],
                                        'jour_numero': k,
                                        'jour_date': jour_info['date'],
                                        'chirurgiens': ', '.join(surgeons_assigned),
                                        'statut': 'Planifié'
                                    })
                        
                        if not scheduled:
                            patient_info = next(p for p in st.session_state.patients if p['id'] == i)
                            planning_details.append({
                                'patient_id': i,
                                'patient_nom': f"{patient_info['nom']} {patient_info['prenom']}",
                                'patient_duree': patient_info['duree'],
                                'salle_id': '-',
                                'salle_nom': '-',
                                'jour_numero': '-',
                                'jour_date': '-',
                                'chirurgiens': '-',
                                'statut': 'Non planifié'
                            })
                    
                    # Calculer les statistiques
                    stats_utilisation = []
                    for j in J:
                        salle_info = next(s for s in st.session_state.salles if s['id'] == j)
                        for k in K:
                            jour_info = next(d for d in st.session_state.jours if d['numero'] == k)
                            used = sum(
                                p['patient_duree'] for p in planning_details 
                                if p['salle_id'] == j and p['jour_numero'] == k and p['statut'] == 'Planifié'
                            )
                            capacity = salle_info['capacite']
                            taux = (used / capacity * 100) if capacity > 0 else 0
                            
                            stats_utilisation.append({
                                'salle': salle_info['nom'],
                                'jour': f"Jour {k} ({jour_info['date']})",
                                'utilise': used,
                                'capacite': capacity,
                                'taux': round(taux, 1)
                            })
                    
                    # Stocker les résultats
                    st.session_state.planning_result = {
                        'details': planning_details,
                        'stats': stats_utilisation,
                        'status': pulp.LpStatus[prob.status],
                        'objective_value': pulp.value(prob.objective),
                        'model': prob
                    }
                    
                    st.session_state.model_status = pulp.LpStatus[prob.status]
                    
                    st.success("✅ Optimisation terminée avec succès!")
                    st.balloons()
                    
                except Exception as e:
                    st.error(f"❌ Erreur lors de l'optimisation: {str(e)}")
                    st.exception(e)

# =====================================================================
# PAGE RESULTATS
# =====================================================================
elif page == "📊 Résultats":
    st.header("📊 Résultats du Planning Optimisé")
    
    if not st.session_state.planning_result:
        st.warning("⚠️ Aucun résultat disponible. Veuillez d'abord lancer l'optimisation.")
        if st.button("Aller à l'optimisation"):
            st.switch_page("🔧 Optimisation")
    else:
        result = st.session_state.planning_result
        
        # Afficher le statut
        st.info(f"**Statut du modèle:** {result['status']}")
        if 'objective_value' in result:
            st.info(f"**Temps libre total:** {result['objective_value']:.1f} minutes")
        
        # Onglets pour différents types de visualisation
        tab1, tab2, tab3, tab4 = st.tabs(["📋 Planning détaillé", "📈 Statistiques", "🗓️ Vue par jour", "📤 Export"])
        
        with tab1:
            st.subheader("Planning détaillé des patients")
            
            # Convertir en DataFrame
            df_planning = pd.DataFrame(result['details'])
            
            # Formater l'affichage
            display_cols = ['patient_nom', 'patient_duree', 'salle_nom', 'jour_date', 'chirurgiens', 'statut']
            df_display = df_planning[display_cols].copy()
            df_display.columns = ['Patient', 'Durée (min)', 'Salle', 'Date', 'Chirurgien(s)', 'Statut']
            
            # Colorier les lignes selon le statut
            def color_row(row):
                if row['Statut'] == 'Planifié':
                    return ['background-color: #d4edda'] * len(row)
                else:
                    return ['background-color: #f8d7da'] * len(row)
            
            styled_df = df_display.style.apply(color_row, axis=1)
            st.dataframe(styled_df, use_container_width=True, hide_index=True)
            
            # Résumé
            col1, col2, col3 = st.columns(3)
            with col1:
                planifies = sum(1 for p in result['details'] if p['statut'] == 'Planifié')
                st.metric("Patients planifiés", planifies)
            with col2:
                non_planifies = sum(1 for p in result['details'] if p['statut'] == 'Non planifié')
                st.metric("Patients non planifiés", non_planifies)
            with col3:
                taux = (planifies / len(result['details']) * 100) if result['details'] else 0
                st.metric("Taux de planification", f"{taux:.1f}%")
        
        with tab2:
            st.subheader("Statistiques d'utilisation")
            
            if 'stats' in result:
                df_stats = pd.DataFrame(result['stats'])
                
                # Graphique à barres
                st.bar_chart(
                    df_stats.set_index('jour')['taux'],
                    color="#FF4B4B"
                )
                
                # Tableau détaillé
                st.dataframe(
                    df_stats[['salle', 'jour', 'utilise', 'capacite', 'taux']],
                    column_config={
                        'taux': st.column_config.ProgressColumn(
                            "Taux d'utilisation (%)",
                            format="%.1f%%",
                            min_value=0,
                            max_value=100
                        )
                    },
                    use_container_width=True,
                    hide_index=True
                )
        
        with tab3:
            st.subheader("Vue par jour et salle")
            
            # Filtrer par jour
            jours_uniques = sorted(set(p['jour_date'] for p in result['details'] if p['jour_date'] != '-'))
            jour_selectionne = st.selectbox("Sélectionner un jour", jours_uniques)
            
            # Filtrer les données
            planning_jour = [p for p in result['details'] if p['jour_date'] == jour_selectionne and p['statut'] == 'Planifié']
            
            if planning_jour:
                # Grouper par salle
                salles_jour = set(p['salle_nom'] for p in planning_jour if p['salle_nom'] != '-')
                
                for salle in salles_jour:
                    with st.expander(f"🚪 {salle}", expanded=True):
                        patients_salle = [p for p in planning_jour if p['salle_nom'] == salle]
                        
                        for patient in patients_salle:
                            col1, col2, col3 = st.columns([3, 2, 2])
                            with col1:
                                st.write(f"**{patient['patient_nom']}**")
                            with col2:
                                st.write(f"⏱️ {patient['patient_duree']} min")
                            with col3:
                                st.write(f"👨‍⚕️ {patient['chirurgiens']}")
                            st.divider()
            else:
                st.info(f"Aucun patient planifié pour le {jour_selectionne}")
        
        with tab4:
            st.subheader("Export des résultats")
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                # Export CSV
                csv = pd.DataFrame(result['details']).to_csv(index=False)
                st.download_button(
                    label="📥 Télécharger CSV",
                    data=csv,
                    file_name="planning_clinique.csv",
                    mime="text/csv",
                    use_container_width=True
                )
            
            with col2:
                # Export Excel
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    pd.DataFrame(result['details']).to_excel(writer, sheet_name='Planning', index=False)
                    if 'stats' in result:
                        pd.DataFrame(result['stats']).to_excel(writer, sheet_name='Statistiques', index=False)
                
                st.download_button(
                    label="📊 Télécharger Excel",
                    data=output.getvalue(),
                    file_name="planning_clinique.xlsx",
                    mime="application/vnd.ms-excel",
                    use_container_width=True
                )
            
            with col3:
                # Export JSON
                json_data = json.dumps(result, indent=2, default=str)
                st.download_button(
                    label="📋 Télécharger JSON",
                    data=json_data,
                    file_name="planning_clinique.json",
                    mime="application/json",
                    use_container_width=True
                )
            
            # Aperçu des données exportées
            st.subheader("Aperçu des données")
            with st.expander("Voir les données brutes"):
                st.json(result, expanded=False)

# =====================================================================
# PIED DE PAGE
# =====================================================================
st.divider()
st.caption("Système d'optimisation de planning clinique - v1.0 | Développé avec Streamlit et PuLP")
