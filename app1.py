# app.py - Version complète avec ordonnancement horaire et compatibilité
# ============================================================================
# IMPORTS
# ============================================================================
import streamlit as st
import pulp
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import json
import io

# ============================================================================
# FONCTION D'ORDONNANCEMENT HORAIRE - POST-TRAITEMENT
# ============================================================================
def appliquer_ordonnancement_horaire(planning_brut, heure_debut="08:00", 
                                     heure_fin="18:00", pause=15, 
                                     regle_ordre="duree_desc"):
    """
    RÈGLE D'ORDONNANCEMENT ACADÉMIQUE - Post-traitement du modèle MILP
    
    Cette fonction applique la règle LPT (Longest Processing Time) standard :
    1. Groupe les patients par salle et jour
    2. Trie par durée décroissante (règle LPT)
    3. Assigne les heures de début/fin de manière séquentielle
    4. Ajoute des pauses entre interventions
    
    Args:
        planning_brut: Résultat du modèle d'optimisation MILP
        heure_debut: "HH:MM" début des opérations
        heure_fin: "HH:MM" fin des opérations  
        pause: minutes entre interventions
        regle_ordre: 'duree_desc' (LPT), 'priorite', 'fifo', 'mixte'
    
    Returns:
        Planning horaire complet avec heures précises
    """
    # Conversion heures en minutes
    h_debut = int(heure_debut.split(':')[0])*60 + int(heure_debut.split(':')[1])
    h_fin = int(heure_fin.split(':')[0])*60 + int(heure_fin.split(':')[1])
    capacite = h_fin - h_debut
    
    # Initialisation
    planning_final = []
    patients_non_planifies = []
    
    # 1. Séparer patients planifiés/non-planifiés
    for patient in planning_brut:
        if patient.get('statut') == 'Planifié':
            planning_final.append(patient)
        else:
            patients_non_planifies.append(patient)
    
    # 2. Grouper par salle et jour
    groupes = {}
    for patient in planning_final:
        cle = (patient.get('salle_id'), patient.get('jour_numero'))
        if cle not in groupes:
            groupes[cle] = []
        groupes[cle].append(patient)
    
    # Réinitialiser planning_final
    planning_final = []
    
    # 3. Pour chaque groupe, appliquer la règle d'ordonnancement
    for (salle_id, jour_numero), patients in groupes.items():
        
        # RÈGLE DE TRI (cœur de l'ordonnancement)
        if regle_ordre == 'duree_desc':
            # RÈGLE LPT : Longest Processing Time First
            patients_tries = sorted(patients, 
                                   key=lambda x: x.get('patient_duree', 0), 
                                   reverse=True)
        
        elif regle_ordre == 'priorite':
            # Règle par priorité clinique
            patients_tries = sorted(patients, 
                                   key=lambda x: x.get('priorite', 999))
        
        elif regle_ordre == 'fifo':
            # First In First Out (par ID patient)
            patients_tries = sorted(patients, 
                                   key=lambda x: x.get('patient_id', ''))
        
        elif regle_ordre == 'mixte':
            # Règle hybride : priorité puis durée
            patients_tries = sorted(patients,
                                   key=lambda x: (x.get('priorite', 999), 
                                                 -x.get('patient_duree', 0)))
        
        else:
            # Par défaut : LPT
            patients_tries = sorted(patients, 
                                   key=lambda x: x.get('patient_duree', 0), 
                                   reverse=True)
        
        # 4. Assignation séquentielle des heures
        heure_courante = h_debut
        
        for patient in patients_tries:
            duree = patient.get('patient_duree', 0)
            
            # Vérifier capacité horaire
            if heure_courante + duree <= h_debut + capacite:
                # Calcul des heures
                h_debut_patient = heure_courante
                h_fin_patient = heure_courante + duree
                
                # Formatage HH:MM
                patient['heure_debut'] = f"{h_debut_patient//60:02d}:{h_debut_patient%60:02d}"
                patient['heure_fin'] = f"{h_fin_patient//60:02d}:{h_fin_patient%60:02d}"
                
                # Stockage en minutes pour tri
                patient['heure_debut_min'] = h_debut_patient
                patient['heure_fin_min'] = h_fin_patient
                
                planning_final.append(patient)
                
                # Incrémentation avec pause
                heure_courante = h_fin_patient + pause
            else:
                # Capacité insuffisante
                patient['statut'] = 'Non planifié (hors créneau)'
                patient['heure_debut'] = 'N/A'
                patient['heure_fin'] = 'N/A'
                planning_final.append(patient)
    
    # 5. Ajouter patients non planifiés originaux
    for patient in patients_non_planifies:
        patient['heure_debut'] = 'N/A'
        patient['heure_fin'] = 'N/A'
        planning_final.append(patient)
    
    return planning_final

# ============================================================================
# CONFIGURATION STREAMLIT
# ============================================================================
st.set_page_config(
    page_title="Planning Chirurgical Optimisé",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ============================================================================
# INITIALISATION DES DONNÉES
# ============================================================================
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
if 'planning_final' not in st.session_state:
    st.session_state.planning_final = None
if 'parametres_ordo' not in st.session_state:
    st.session_state.parametres_ordo = {}

# ============================================================================
# SIDEBAR - NAVIGATION
# ============================================================================
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/3050/3050525.png", width=80)
    st.title("Navigation")
    
    page = st.radio(
        "Menu",
        ["🏠 Accueil", 
         "👥 Patients", 
         "🚪 Salles", 
         "👨‍⚕️ Chirurgiens",
         "⚖️ Compatibilité",  # NOUVELLE PAGE
         "📅 Configuration",
         "🔧 Optimisation",
         "📋 Planning Final"]
    )
    
    st.divider()
    st.caption("Statut des données :")
    col1, col2 = st.columns(2)
    with col1:
        st.metric("Patients", len(st.session_state.patients))
        st.metric("Salles", len(st.session_state.salles))
    with col2:
        st.metric("Chirurgiens", len(st.session_state.chirurgiens))
        compat_count = len(st.session_state.compatibilite)
        st.metric("Compatibilités", compat_count)
    
    if st.button("🔄 Réinitialiser", type="secondary"):
        for key in ['patients', 'salles', 'chirurgiens', 'jours', 'compatibilite', 'planning_final']:
            st.session_state[key] = [] if key != 'compatibilite' else {}
        st.rerun()

# ============================================================================
# PAGE ACCUEIL
# ============================================================================
if page == "🏠 Accueil":
    st.title("🏥 Système de Planification Chirurgicale")
    st.markdown("### Optimisation avec ordonnancement horaire intégré")
    
    col1, col2 = st.columns([3, 1])
    
    with col1:
        st.markdown("""
        ### 📋 Fonctionnalités
        
        **1. Gestion des données :**
        - Patients, salles, chirurgiens
        - Compatibilités patient-chirurgien
        - Jours de planning
        
        **2. Optimisation automatique :**
        - Modèle mathématique MILP pour l'allocation
        - Règle LPT (Longest Processing Time) pour l'ordonnancement horaire
        - Intégration transparente des deux étapes
        
        **3. Planning final :**
        - **Un seul planning complet** avec heures de début/fin
        - Export en CSV/Excel
        - Vue par jour et par salle
        """)
        
        st.info("""
        **Note importante :**  
        Le planning journalier (sans heures) est généré automatiquement  
        mais **non affiché**. Seul le planning horaire final est présenté.
        """)
    
    with col2:
        st.subheader("📊 Données")
        stats_data = {
            "Donnée": ["Patients", "Salles", "Chirurgiens", "Compatibilités", "Planning"],
            "Valeur": [
                len(st.session_state.patients),
                len(st.session_state.salles),
                len(st.session_state.chirurgiens),
                len(st.session_state.compatibilite),
                "✅" if st.session_state.planning_final else "❌"
            ]
        }
        st.table(pd.DataFrame(stats_data))

# ============================================================================
# PAGE PATIENTS
# ============================================================================
elif page == "👥 Patients":
    st.header("👥 Gestion des Patients")
    
    with st.form("form_patient"):
        col1, col2 = st.columns(2)
        
        with col1:
            patient_id = st.text_input("ID Patient*")
            nom = st.text_input("Nom*")
            prenom = st.text_input("Prénom*")
            age = st.number_input("Âge", 0, 120, 45)
        
        with col2:
            duree = st.number_input("Durée opération (min)*", 15, 480, 120)
            priorite = st.selectbox("Priorité", [1, 2, 3, 4, 5], 
                                   help="1 = Plus urgent, 5 = Moins urgent")
            type_interv = st.selectbox("Type", ["Cardiaque", "Orthopédique", "Générale", "Neurologique"])
        
        if st.form_submit_button("💾 Enregistrer"):
            if patient_id and nom and prenom:
                # Vérifier si ID existe déjà
                ids_existants = [p['id'] for p in st.session_state.patients]
                if patient_id in ids_existants:
                    st.error(f"ID {patient_id} existe déjà !")
                else:
                    st.session_state.patients.append({
                        'id': patient_id,
                        'nom': nom,
                        'prenom': prenom,
                        'age': age,
                        'duree': duree,
                        'priorite': priorite,
                        'type': type_interv
                    })
                    st.success(f"Patient {prenom} {nom} ajouté")
                    st.rerun()
    
    if st.session_state.patients:
        st.subheader("Liste des patients")
        df = pd.DataFrame(st.session_state.patients)
        st.dataframe(df[['id', 'nom', 'prenom', 'duree', 'priorite', 'type']], 
                    use_container_width=True)

# ============================================================================
# PAGE SALLES
# ============================================================================
elif page == "🚪 Salles":
    st.header("🚪 Gestion des Salles")
    
    with st.form("form_salle"):
        salle_id = st.text_input("ID Salle*")
        nom_salle = st.text_input("Nom Salle*")
        capacite = st.number_input("Capacité (min/jour)*", 240, 1440, 480,
                                 help="Capacité quotidienne en minutes (ex: 480 = 8h)")
        
        if st.form_submit_button("➕ Ajouter"):
            if salle_id and nom_salle:
                # Vérifier si ID existe déjà
                ids_existants = [s['id'] for s in st.session_state.salles]
                if salle_id in ids_existants:
                    st.error(f"ID {salle_id} existe déjà !")
                else:
                    st.session_state.salles.append({
                        'id': salle_id,
                        'nom': nom_salle,
                        'capacite': capacite
                    })
                    st.success(f"Salle {nom_salle} ajoutée")
                    st.rerun()
    
    if st.session_state.salles:
        st.subheader("Salles disponibles")
        df = pd.DataFrame(st.session_state.salles)
        st.dataframe(df, use_container_width=True)

# ============================================================================
# PAGE CHIRURGIENS
# ============================================================================
elif page == "👨‍⚕️ Chirurgiens":
    st.header("👨‍⚕️ Gestion des Chirurgiens")
    
    with st.form("form_chir"):
        chir_id = st.text_input("ID Chirurgien*")
        nom = st.text_input("Nom*")
        prenom = st.text_input("Prénom*")
        specialite = st.selectbox("Spécialité", 
                                 ["Cardiologie", "Orthopédie", "Générale", 
                                  "Neurologie", "Pédiatrie", "Traumatologie"])
        disponibilite = st.number_input("Disponibilité (min/jour)*", 240, 600, 360,
                                       help="Disponibilité quotidienne en minutes")
        
        if st.form_submit_button("👨‍⚕️ Ajouter"):
            if chir_id and nom and prenom:
                # Vérifier si ID existe déjà
                ids_existants = [c['id'] for c in st.session_state.chirurgiens]
                if chir_id in ids_existants:
                    st.error(f"ID {chir_id} existe déjà !")
                else:
                    st.session_state.chirurgiens.append({
                        'id': chir_id,
                        'nom': nom,
                        'prenom': prenom,
                        'specialite': specialite,
                        'disponibilite': disponibilite
                    })
                    st.success(f"Chirurgien {prenom} {nom} ajouté")
                    st.rerun()
    
    if st.session_state.chirurgiens:
        st.subheader("Chirurgiens disponibles")
        df = pd.DataFrame(st.session_state.chirurgiens)
        st.dataframe(df, use_container_width=True)

# ============================================================================
# PAGE COMPATIBILITÉ (NOUVELLE PAGE)
# ============================================================================
elif page == "⚖️ Compatibilité":
    st.header("⚖️ Compatibilité Patients-Chirurgiens")
    
    if not st.session_state.patients or not st.session_state.chirurgiens:
        st.warning("Ajoutez d'abord des patients et des chirurgiens")
    else:
        # Initialisation si vide
        if not st.session_state.compatibilite:
            # Par défaut, tous compatibles (1)
            for patient in st.session_state.patients:
                for chirurgien in st.session_state.chirurgiens:
                    cle = (patient['id'], chirurgien['id'])
                    st.session_state.compatibilite[cle] = 1
        
        # Interface pour modifier les compatibilités
        st.subheader("Matrice de compatibilité")
        st.write("Cocher = Compatible (1), Décocher = Non compatible (0)")
        
        # Créer un DataFrame pour l'éditeur
        compat_data = []
        for patient in st.session_state.patients:
            row = {'Patient': f"{patient['id']} - {patient['prenom']} {patient['nom']}"}
            for chirurgien in st.session_state.chirurgiens:
                cle = (patient['id'], chirurgien['id'])
                valeur = st.session_state.compatibilite.get(cle, 1)
                row[chirurgien['id']] = bool(valeur)
            compat_data.append(row)
        
        df_compat = pd.DataFrame(compat_data)
        
        # Éditeur interactif
        edited_df = st.data_editor(
            df_compat,
            column_config={
                "Patient": st.column_config.TextColumn("Patient", width="medium"),
                **{ch['id']: st.column_config.CheckboxColumn(
                    f"{ch['id']} ({ch['prenom']})",
                    default=True,
                    help=f"{ch['prenom']} {ch['nom']} - {ch['specialite']}"
                ) for ch in st.session_state.chirurgiens}
            },
            use_container_width=True,
            hide_index=True
        )
        
        # Sauvegarder les modifications
        if st.button("💾 Enregistrer les compatibilités"):
            for idx, row in edited_df.iterrows():
                patient_id = row['Patient'].split(" - ")[0]
                for chirurgien in st.session_state.chirurgiens:
                    chir_id = chirurgien['id']
                    cle = (patient_id, chir_id)
                    st.session_state.compatibilite[cle] = int(row[chir_id])
            st.success("Compatibilités enregistrées !")
        
        # Statistiques
        st.subheader("📊 Statistiques de compatibilité")
        total_compat = len(st.session_state.compatibilite)
        compat_oui = sum(1 for v in st.session_state.compatibilite.values() if v == 1)
        compat_non = total_compat - compat_oui
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total paires", total_compat)
        with col2:
            st.metric("Compatibles", compat_oui)
        with col3:
            taux = (compat_oui / total_compat * 100) if total_compat > 0 else 0
            st.metric("Taux compatibilité", f"{taux:.1f}%")

# ============================================================================
# PAGE CONFIGURATION
# ============================================================================
elif page == "📅 Configuration":
    st.header("📅 Configuration du Planning")
    
    col1, col2 = st.columns(2)
    
    with col1:
        # Jours de planning
        st.subheader("Jours de planning")
        nb_jours = st.number_input("Nombre de jours", 1, 14, 5)
        date_debut = st.date_input("Date de début", datetime.now())
        
        if st.button("📅 Générer les jours"):
            st.session_state.jours = []
            for i in range(nb_jours):
                date_jour = date_debut + timedelta(days=i)
                st.session_state.jours.append({
                    'numero': i + 1,
                    'date': date_jour.strftime("%Y-%m-%d"),
                    'jour_semaine': date_jour.strftime("%A"),
                    'label': f"Jour {i+1} ({date_jour.strftime('%d/%m/%Y')})"
                })
            st.success(f"{nb_jours} jours générés")
    
    with col2:
        # Aperçu configuration
        st.subheader("Aperçu configuration")
        
        if st.session_state.jours:
            st.write("**Jours configurés :**")
            for jour in st.session_state.jours:
                st.write(f"• {jour['label']}")
        else:
            st.info("Aucun jour configuré")
        
        if st.session_state.compatibilite:
            st.write(f"**Compatibilités :** {len(st.session_state.compatibilite)} paires")

# ============================================================================
# PAGE OPTIMISATION (MODÈLE + ORDONNANCEMENT INTÉGRÉ)
# ============================================================================
elif page == "🔧 Optimisation":
    st.header("🔧 Optimisation et Ordonnancement")
    
    # Vérification prérequis
    if not st.session_state.patients:
        st.error("❌ Ajoutez d'abord des patients")
        st.stop()
    if not st.session_state.salles:
        st.error("❌ Ajoutez d'abord des salles")
        st.stop()
    if not st.session_state.chirurgiens:
        st.error("❌ Ajoutez d'abord des chirurgiens")
        st.stop()
    if not st.session_state.jours:
        st.error("❌ Configurez d'abord les jours")
        st.stop()
    
    # PARAMÈTRES D'ORDONNANCEMENT
    st.subheader("⏰ Paramètres d'ordonnancement horaire")
    
    with st.expander("Configuration des créneaux", expanded=True):
        col1, col2 = st.columns(2)
        
        with col1:
            heure_debut = st.time_input(
                "Heure de début",
                value=datetime.strptime("08:00", "%H:%M").time()
            )
            heure_fin = st.time_input(
                "Heure de fin",
                value=datetime.strptime("18:00", "%H:%M").time()
            )
        
        with col2:
            pause = st.number_input("Pause entre interventions (min)", 0, 60, 15)
            regle = st.selectbox(
                "Règle d'ordre dans la journée",
                [
                    ("duree_desc", "LPT - Durée décroissante"),
                    ("priorite", "Priorité clinique"),
                    ("fifo", "FIFO - Premier arrivé"),
                    ("mixte", "Hybride (priorité puis durée)")
                ],
                format_func=lambda x: x[1]
            )
    
    # BOUTON D'OPTIMISATION
    st.divider()
    
    if st.button("🚀 Lancer l'optimisation complète", type="primary", use_container_width=True):
        with st.spinner("Optimisation en cours (modèle + ordonnancement)..."):
            try:
                # ============================================================
                # ÉTAPE 1 : MODÈLE MATHÉMATIQUE (VOTRE CODE ACTUEL)
                # ============================================================
                
                # Préparation des données pour le modèle
                I = [p['id'] for p in st.session_state.patients]
                J = [s['id'] for s in st.session_state.salles]
                S = [c['id'] for c in st.session_state.chirurgiens]
                K = [j['numero'] for j in st.session_state.jours]
                
                # Durées patients
                t = {p['id']: p['duree'] for p in st.session_state.patients}
                
                # Capacités salles
                b = {(j_id, k): next(s['capacite'] for s in st.session_state.salles if s['id'] == j_id)
                     for j_id in J for k in K}
                
                # Disponibilités chirurgiens
                a = {(s_id, k): next(c['disponibilite'] for c in st.session_state.chirurgiens if c['id'] == s_id)
                     for s_id in S for k in K}
                
                # MATRICE DE COMPATIBILITÉ (m) - CORRECTION ICI
                m = {}
                for patient in st.session_state.patients:
                    for chirurgien in st.session_state.chirurgiens:
                        cle = (patient['id'], chirurgien['id'])
                        # Utiliser la valeur de compatibilité (0 ou 1)
                        m[cle] = st.session_state.compatibilite.get(cle, 1)
                
                # Création du modèle MILP
                prob = pulp.LpProblem("Planning_Clinique", pulp.LpMinimize)
                
                # Variables
                x = pulp.LpVariable.dicts('x', (I, J, K), cat='Binary')
                y = pulp.LpVariable.dicts('y', (I, J, S, K), cat='Binary')
                
                # Objectif : minimiser temps libre
                prob += pulp.lpSum(
                    b[(j, k)] - pulp.lpSum(t[i] * x[i][j][k] for i in I)
                    for j in J for k in K
                )
                
                # Contraintes
                for i in I:
                    prob += pulp.lpSum(x[i][j][k] for j in J for k in K) <= 1, f"Once_{i}"
                
                for j in J:
                    for k in K:
                        prob += pulp.lpSum(t[i] * x[i][j][k] for i in I) <= b[(j, k)], f"ORcap_{j}_{k}"
                
                for s in S:
                    for k in K:
                        prob += pulp.lpSum(t[i] * y[i][j][s][k] for i in I for j in J) <= a[(s, k)], f"SurgeonCap_{s}_{k}"
                
                # CONTRAINTE DE COMPATIBILITÉ - CORRECTION ICI
                for i in I:
                    for j in J:
                        for s in S:
                            for k in K:
                                prob += y[i][j][s][k] <= m.get((i, s), 0), f"Compat_{i}_{j}_{s}_{k}"
                
                for i in I:
                    for j in J:
                        for k in K:
                            prob += pulp.lpSum(y[i][j][s][k] for s in S) == x[i][j][k], f"Link_x_y_{i}_{j}_{k}"
                
                # Résolution
                solver = pulp.PULP_CBC_CMD(msg=False, timeLimit=60)
                prob.solve(solver)
                
                # ============================================================
                # ÉTAPE 2 : RÉCUPÉRATION RÉSULTATS MODÈLE
                # ============================================================
                planning_details = []
                
                for i in I:
                    scheduled = False
                    for j in J:
                        for k in K:
                            if pulp.value(x[i][j][k]) > 0.5:
                                scheduled = True
                                surgeons = [s for s in S if pulp.value(y[i][j][s][k]) > 0.5]
                                
                                # Infos patient
                                patient_info = next(p for p in st.session_state.patients if p['id'] == i)
                                salle_info = next(s for s in st.session_state.salles if s['id'] == j)
                                jour_info = next(d for d in st.session_state.jours if d['numero'] == k)
                                
                                planning_details.append({
                                    'patient_id': i,
                                    'patient_nom': f"{patient_info['nom']} {patient_info['prenom']}",
                                    'patient_duree': patient_info['duree'],
                                    'priorite': patient_info.get('priorite', 3),
                                    'salle_id': j,
                                    'salle_nom': salle_info['nom'],
                                    'jour_numero': k,
                                    'jour_date': jour_info['date'],
                                    'chirurgiens': ', '.join(surgeons),
                                    'statut': 'Planifié'
                                })
                    
                    if not scheduled:
                        patient_info = next(p for p in st.session_state.patients if p['id'] == i)
                        planning_details.append({
                            'patient_id': i,
                            'patient_nom': f"{patient_info['nom']} {patient_info['prenom']}",
                            'patient_duree': patient_info['duree'],
                            'priorite': patient_info.get('priorite', 3),
                            'salle_id': '',
                            'salle_nom': '',
                            'jour_numero': '',
                            'jour_date': '',
                            'chirurgiens': '',
                            'statut': 'Non planifié'
                        })
                
                # ============================================================
                # ÉTAPE 3 : ORDONNANCEMENT HORAIRE (POST-TRAITEMENT)
                # ============================================================
                planning_avec_heures = appliquer_ordonnancement_horaire(
                    planning_details,
                    heure_debut=heure_debut.strftime("%H:%M"),
                    heure_fin=heure_fin.strftime("%H:%M"),
                    pause=pause,
                    regle_ordre=regle[0]
                )
                
                # ============================================================
                # ÉTAPE 4 : SAUVEGARDE FINALE
                # ============================================================
                st.session_state.planning_final = planning_avec_heures
                st.session_state.parametres_ordo = {
                    'regle': regle[1],
                    'heure_debut': heure_debut.strftime("%H:%M"),
                    'heure_fin': heure_fin.strftime("%H:%M"),
                    'pause': pause,
                    'modele_statut': pulp.LpStatus[prob.status],
                    'modele_objectif': pulp.value(prob.objective),
                    'compatibilite_utilisee': True
                }
                
                st.success("✅ Optimisation et ordonnancement terminés !")
                st.balloons()
                
                # Redirection automatique vers le planning
                st.rerun()
                
            except Exception as e:
                st.error(f"Erreur : {str(e)}")
                st.exception(e)

# ============================================================================
# PAGE PLANNING FINAL
# ============================================================================
elif page == "📋 Planning Final":
    st.header("📋 Planning Chirurgical Complet")
    
    if not st.session_state.planning_final:
        st.warning("""
        ⚠️ Aucun planning disponible.
        
        Veuillez :
        1. Ajouter des patients, salles, chirurgiens
        2. Configurer les compatibilités
        3. Configurer les jours
        4. Aller dans '🔧 Optimisation'
        5. Lancer l'optimisation complète
        """)
        
        if st.button("Aller à l'optimisation"):
            st.rerun()
    else:
        # Afficher les paramètres utilisés
        if st.session_state.parametres_ordo:
            params = st.session_state.parametres_ordo
            
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Règle", params.get('regle', 'LPT'))
            with col2:
                st.metric("Plage horaire", f"{params.get('heure_debut')}-{params.get('heure_fin')}")
            with col3:
                st.metric("Pause", f"{params.get('pause')} min")
            with col4:
                st.metric("Statut modèle", params.get('modele_statut', 'N/A'))
        
        # Créer le DataFrame final
        planning_data = []
        
        for rdv in st.session_state.planning_final:
            if rdv.get('heure_debut') != 'N/A':
                planning_data.append({
                    'Patient': rdv.get('patient_nom', ''),
                    'Durée (min)': rdv.get('patient_duree', 0),
                    'Priorité': rdv.get('priorite', 'N/A'),
                    'Salle': rdv.get('salle_nom', ''),
                    'Date': rdv.get('jour_date', ''),
                    'Début': rdv.get('heure_debut', ''),
                    'Fin': rdv.get('heure_fin', ''),
                    'Chirurgien(s)': rdv.get('chirurgiens', ''),
                    'Statut': '✅ Planifié'
                })
            else:
                planning_data.append({
                    'Patient': rdv.get('patient_nom', ''),
                    'Durée (min)': rdv.get('patient_duree', 0),
                    'Priorité': rdv.get('priorite', 'N/A'),
                    'Salle': 'N/A',
                    'Date': 'N/A',
                    'Début': 'N/A',
                    'Fin': 'N/A',
                    'Chirurgien(s)': 'N/A',
                    'Statut': '❌ ' + rdv.get('statut', 'Non planifié')
                })
        
        df_final = pd.DataFrame(planning_data)
        
        # Trier par date puis heure
        if 'Début' in df_final.columns:
            df_final['tri_date'] = pd.to_datetime(df_final['Date'])
            df_final['tri_heure'] = df_final['Début'].apply(
                lambda x: int(x.split(':')[0])*60 + int(x.split(':')[1]) 
                if ':' in str(x) else 9999
            )
            df_final = df_final.sort_values(['tri_date', 'tri_heure'])
            df_final = df_final.drop(['tri_date', 'tri_heure'], axis=1)
        
        # AFFICHAGE PRINCIPAL
        st.subheader("Planning horaire complet")
        
        # Onglets
        tab1, tab2, tab3 = st.tabs(["📋 Tableau complet", "🗓️ Vue par jour", "📊 Statistiques"])
        
        with tab1:
            # Tableau principal
            st.dataframe(
                df_final,
                column_config={
                    "Début": st.column_config.TextColumn("Heure début", width="small"),
                    "Fin": st.column_config.TextColumn("Heure fin", width="small"),
                    "Statut": st.column_config.TextColumn(
                        "Statut",
                        help="✅ = Avec créneau horaire, ❌ = Sans créneau"
                    )
                },
                use_container_width=True,
                hide_index=True
            )
            
            # Export
            csv_data = df_final.to_csv(index=False, encoding='utf-8-sig')
            st.download_button(
                "📥 Télécharger CSV",
                csv_data,
                "planning_chirurgical.csv",
                "text/csv"
            )
        
        with tab2:
            # Vue par jour
            jours_planifies = sorted(set(
                rdv['jour_date'] for rdv in st.session_state.planning_final 
                if rdv.get('heure_debut') != 'N/A'
            ))
            
            if jours_planifies:
                jour_selectionne = st.selectbox("Choisir un jour", jours_planifies)
                
                # Filtrer pour ce jour
                rdvs_jour = [
                    rdv for rdv in st.session_state.planning_final
                    if rdv.get('jour_date') == jour_selectionne and rdv.get('heure_debut') != 'N/A'
                ]
                
                if rdvs_jour:
                    # Afficher par salle
                    for salle in sorted(set(r['salle_nom'] for r in rdvs_jour)):
                        with st.expander(f"🚪 {salle}", expanded=True):
                            rdvs_salle = [
                                r for r in rdvs_jour 
                                if r['salle_nom'] == salle
                            ]
                            rdvs_salle.sort(key=lambda x: x.get('heure_debut_min', 0))
                            
                            for rdv in rdvs_salle:
                                col1, col2, col3 = st.columns([4, 3, 3])
                                with col1:
                                    st.write(f"**{rdv['patient_nom']}**")
                                with col2:
                                    st.write(f"🕒 {rdv['heure_debut']} - {rdv['heure_fin']}")
                                with col3:
                                    st.write(f"⏱️ {rdv['patient_duree']} min")
                                
                                # Barre de progression pour visualisation
                                duree = rdv['patient_duree']
                                duree_max = 600  # 10h en minutes
                                progression = min(duree /
