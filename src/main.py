import streamlit as st
import pandas as pd
import os
import yaml
import json
from crewai import Crew, Process
from PyPDF2 import PdfReader
import docx
from dotenv import load_dotenv

from data.database import AuthManager, DatabaseManager

# Load environment variables
load_dotenv()

# Set environment variable to disable telemetry
os.environ["CREWAI_DISABLE_TELEMETRY"] = "true"

# Import local modules
from agent_loader import load_llm, create_agents
from task_factory import get_ad_campaign_task, get_ad_campaign_written_task, format_courses_list, get_cv_analysis_task
from data_handler import load_courses_data

# Import authentication modules
 

def extract_text_from_pdf(pdf_file):
    """Extract text content from a PDF file."""
    pdf_reader = PdfReader(pdf_file)
    text = ""
    for page in pdf_reader.pages:
        text += page.extract_text() + "\n"
    return text

def extract_text_from_docx(docx_file):
    """Extract text content from a DOCX file."""
    doc = docx.Document(docx_file)
    full_text = []
    for para in doc.paragraphs:
        full_text.append(para.text)
    return '\n'.join(full_text)

def extract_text_from_txt(txt_file):
    """Extract text content from a TXT file."""
    return txt_file.getvalue().decode("utf-8")

def analyze_cv_with_agent(cv_text, llm):
    """
    Use the CV analyzer agent to extract information from CV text.
    """
    # Load agents
    agents = create_agents(llm)
    
    # Create task for CV analysis
    task = get_cv_analysis_task(agents['cv_analyzer_agent'], cv_text)
    
    # Create and run CV analysis crew
    cv_analysis_crew = Crew(
        agents=[agents['cv_analyzer_agent']],
        tasks=[task],
        verbose=True,
        process=Process.sequential
    )
    
    # Run analysis
    result = cv_analysis_crew.kickoff()
    
    # Parse JSON result into dictionary
    try:
        # Handle the CrewOutput object correctly
        if hasattr(result, 'raw'):
            # If result is a CrewOutput object with a raw attribute
            json_str = result.raw
        elif isinstance(result, str):
            # If result is already a string (fallback)
            json_str = result
        else:
            # Try to convert to string as last resort
            json_str = str(result)
        
        # Clean up the JSON string if needed
        if isinstance(json_str, str):
            json_start = json_str.find('{')
            json_end = json_str.rfind('}') + 1
            if json_start >= 0 and json_end > json_start:
                json_str = json_str[json_start:json_end]
        
        # Parse the JSON string
        data = json.loads(json_str)
        
        # Handle nested structures in the result
        if isinstance(data, dict):
            # Some fields might be lists or dicts, convert them to strings for simpler display
            if 'Hobbies' in data and isinstance(data['Hobbies'], list):
                data['Hobbies'] = ', '.join(data['Hobbies'])
                
            if 'Computer Skills' in data and isinstance(data['Computer Skills'], dict):
                # Try to determine overall skill level from components
                skill_levels = list(data['Computer Skills'].values())
                if "Advanced" in skill_levels:
                    data['Computer Skills'] = "Advanced"
                elif "Intermediate" in skill_levels:
                    data['Computer Skills'] = "Intermediate"
                else:
                    data['Computer Skills'] = "Beginner"
                
            if 'Interest in Languages' in data and isinstance(data['Interest in Languages'], list):
                data['Interest in Languages'] = ', '.join(data['Interest in Languages'])
                
            # Extract numeric GPA if it's in format like "3.7/4.0"
            if 'GPA' in data and isinstance(data['GPA'], str) and '/' in data['GPA']:
                try:
                    data['GPA'] = float(data['GPA'].split('/')[0])
                except:
                    data['GPA'] = 3.0  # Default
        
        # Ensure all required fields are present
        required_fields = ['Academic Goals', 'Major', 'Hobbies', 'Computer Skills', 'Interest in Languages', 'GPA']
        for field in required_fields:
            if field not in data:
                data[field] = "Non spécifié dans le CV"
        
        # Convert GPA to float if it's a string
        if isinstance(data['GPA'], str) and data['GPA'].replace('.', '', 1).isdigit():
            data['GPA'] = float(data['GPA'])
        elif not isinstance(data['GPA'], (int, float)):
            data['GPA'] = 3.0  # Default value
        
        return data
    except Exception as e:
        st.error(f"Erreur lors de l'analyse du CV : {str(e)}")
        st.write("Résultat brut :", result)
        # Return default values
        return {
            'Academic Goals': "Non spécifié dans le CV",
            'Major': "Non spécifié dans le CV",
            'Hobbies': "Non spécifié dans le CV",
            'Computer Skills': "Intermédiaire",
            'Interest in Languages': "Non spécifié dans le CV",
            'GPA': 3.0
        }

def run_recommendation(student_data, db_manager, user_id):
    """Run the recommendation system with the provided student data."""
    # Format student description
    customer_description = f"""
    Leurs objectifs académiques sont {student_data['Academic Goals']}.
    Leur spécialité est en {student_data['Major']}.
    Leurs loisirs sont {student_data['Hobbies']}.
    Leurs compétences informatiques sont {student_data['Computer Skills']}.
    Leur intérêt pour les langues est {student_data['Interest in Languages']}.
    Leur moyenne générale est {student_data['GPA']}.
    """
    
    # Load courses data
    courses_data = load_courses_data()
    courses_list = format_courses_list(courses_data)
    
    # Set up LLM
    llm = load_llm()
    
    # Load agents
    agents = create_agents(llm)
    
    # Task 1: Select top 3 relevant courses
    task1 = get_ad_campaign_task(
        agents['chief_recommendation_director'],
        customer_description, 
        courses_list
    )
    
    # Create and run first crew
    targeting_crew = Crew(
        agents=[
            agents['student_profiler'], 
            agents['course_specialist'], 
            agents['chief_recommendation_director']
        ],
        tasks=[task1],
        verbose=True,
        process=Process.sequential
    )
    
    # Add progress bar for first task
    progress_bar1 = st.progress(0)
    st.text("Étape 1/2 : Analyse de votre profil et sélection des cours...")
    
    try:
        targeting_result = targeting_crew.kickoff()
        progress_bar1.progress(100)
    except Exception as e:
        st.error(f"Une erreur s'est produite lors de la sélection des cours : {str(e)}")
        return None, None
    
    # Task 2: Generate recommendation campaign
    task2 = get_ad_campaign_written_task(
        agents['chief_recommendation_director'],
        targeting_result
    )
    
    # Add progress bar for second task
    progress_bar2 = st.progress(0)
    st.text("Étape 2/2 : Création de recommandations personnalisées...")
    
    # Create and run second crew
    copywriting_crew = Crew(
        agents=[
            agents['campaign_agent'], 
            agents['chief_recommendation_director']
        ],
        tasks=[task2],
        verbose=True,
        process=Process.sequential
    )
    
    try:
        copywriting_result = copywriting_crew.kickoff()
        progress_bar2.progress(100)
        
        # Save recommendation to database
        db_manager.save_recommendation(
            user_id, 
            student_data, 
            str(targeting_result), 
            str(copywriting_result)
        )
        
        return targeting_result, copywriting_result
    except Exception as e:
        st.error(f"Une erreur s'est produite lors de la création des recommandations : {str(e)}")
        return targeting_result, None

def show_user_dashboard(auth_manager, db_manager):
    """Show user dashboard with profile and history"""
    user = auth_manager.get_current_user()
    
    # Sidebar with user info and logout
    with st.sidebar:
        st.header(f"Bienvenue, {user.get('full_name', user.get('username', 'Utilisateur'))} ! 👋")
        st.write(f"**Nom d'utilisateur :** {user.get('username')}")
        st.write(f"**Email :** {user.get('email')}")
        
        st.markdown("---")
        
        if st.button("🔓 Déconnexion", type="secondary"):
            auth_manager.logout()
        
        st.markdown("---")
        
        # Navigation
        page = st.radio("Navigation", ["Obtenir des Recommandations", "Mon Historique"])
    
    if page == "Obtenir des Recommandations":
        show_recommendation_page(db_manager, user['id'])
    else:
        show_history_page(db_manager, user['id'])

def show_recommendation_page(db_manager, user_id):
    """Show the main recommendation page"""
    st.title("Système de Recommandation de Cours Personnalisé")
    st.write("Obtenez des recommandations de cours personnalisées basées sur votre profil")
    
    # Create tabs for different input methods
    tab1, tab2 = st.tabs(["Télécharger CV/Résumé", "Remplir le Formulaire"])
    
    student_data = None
    submit_pressed = False
    
    # Initialize LLM once for reuse
    llm = load_llm()
    
    # Tab 1: CV Upload
    with tab1:
        st.header("Téléchargez votre CV/Résumé")
        uploaded_file = st.file_uploader("Choisissez un fichier", type=["pdf", "docx", "txt"])
        
        if uploaded_file is not None:
            try:
                # Extract text based on file type
                if uploaded_file.name.endswith('.pdf'):
                    cv_text = extract_text_from_pdf(uploaded_file)
                elif uploaded_file.name.endswith('.docx'):
                    cv_text = extract_text_from_docx(uploaded_file)
                elif uploaded_file.name.endswith('.txt'):
                    cv_text = extract_text_from_txt(uploaded_file)
                else:
                    st.error("Format de fichier non pris en charge")
                    st.stop()
                
                # Show CV analysis in progress
                with st.spinner("Analyse de votre CV..."):
                    st.success("Fichier téléchargé avec succès !")
                    
                    # Use the CV analyzer agent to extract information
                    extracted_data = analyze_cv_with_agent(cv_text, llm)
                
                # Display extracted information for verification
                st.subheader("Informations Extraites")
                st.info("Veuillez vérifier et modifier les informations extraites si nécessaire :")
                
                # Allow user to edit the extracted information
                academic_goals = st.text_area("Objectifs Académiques", value=extracted_data['Academic Goals'])
                major = st.text_input("Spécialité", value=extracted_data['Major'])
                hobbies = st.text_input("Loisirs", value=extracted_data['Hobbies'])
                
                # Determine index for computer skills dropdown
                skills_options = ["Débutant", "Intermédiaire", "Avancé", "Expert"]
                skill_mapping = {
                    "Beginner": "Débutant",
                    "Intermediate": "Intermédiaire", 
                    "Advanced": "Avancé",
                    "Expert": "Expert"
                }
                
                # Map English to French if needed
                current_skill = extracted_data['Computer Skills']
                if current_skill in skill_mapping:
                    current_skill = skill_mapping[current_skill]
                
                skill_index = 1  # Default to Intermédiaire
                if current_skill in skills_options:
                    skill_index = skills_options.index(current_skill)
                
                computer_skills = st.selectbox("Compétences Informatiques", 
                                              skills_options,
                                              index=skill_index)
                
                interest_in_languages = st.text_input("Intérêt pour les Langues", value=extracted_data['Interest in Languages'])
                gpa = st.slider("Moyenne Générale", min_value=0.0, max_value=4.0, value=float(extracted_data['GPA']), step=0.1)
                
                # Map French back to English for internal processing
                skill_reverse_mapping = {
                    "Débutant": "Beginner",
                    "Intermédiaire": "Intermediate",
                    "Avancé": "Advanced",
                    "Expert": "Expert"
                }
                
                # Update student data
                student_data = {
                    'Academic Goals': academic_goals,
                    'Major': major,
                    'Hobbies': hobbies,
                    'Computer Skills': skill_reverse_mapping.get(computer_skills, computer_skills),
                    'Interest in Languages': interest_in_languages,
                    'GPA': gpa
                }
                
                submit_pressed = st.button("Obtenir des Recommandations", key="cv_submit")
                
            except Exception as e:
                st.error(f"Erreur lors du traitement du fichier : {str(e)}")
    
    # Tab 2: Manual Form
    with tab2:
        st.header("Saisissez Vos Informations")
        
        with st.form("student_info_form"):
            col1, col2 = st.columns(2)
            
            with col1:
                academic_goals = st.text_area("Objectifs Académiques", placeholder="Ex: Devenir ingénieur logiciel")
                major = st.text_input("Spécialité", placeholder="Ex: Informatique")
                hobbies = st.text_input("Loisirs", placeholder="Ex: Jeux vidéo, Lecture")
            
            with col2:
                computer_skills = st.selectbox("Compétences Informatiques", 
                                              ["Débutant", "Intermédiaire", "Avancé", "Expert"])
                interest_in_languages = st.text_input("Intérêt pour les Langues", placeholder="Ex: Espagnol, Python")
                gpa = st.slider("Moyenne Générale", min_value=0.0, max_value=4.0, value=3.0, step=0.1)
            
            form_submit = st.form_submit_button("Obtenir des Recommandations")
            
            if form_submit:
                # Map French to English for internal processing
                skill_mapping = {
                    "Débutant": "Beginner",
                    "Intermédiaire": "Intermediate",
                    "Avancé": "Advanced",
                    "Expert": "Expert"
                }
                
                student_data = {
                    'Academic Goals': academic_goals,
                    'Major': major,
                    'Hobbies': hobbies,
                    'Computer Skills': skill_mapping.get(computer_skills, computer_skills),
                    'Interest in Languages': interest_in_languages,
                    'GPA': gpa
                }
                submit_pressed = True
    
    # Process recommendations if data is available and button is pressed
    if student_data and submit_pressed:
        with st.spinner("Analyse de votre profil et recherche des meilleurs cours pour vous..."):
            targeting_result, copywriting_result = run_recommendation(student_data, db_manager, user_id)
            
            if targeting_result:
                # Display results in tabs
                st.success("Recommandations terminées !")
                
                result_tab1, result_tab2 = st.tabs(["Cours Sélectionnés", "Recommandations Détaillées"])
                
                with result_tab1:
                    st.header("Cours Sélectionnés pour Vous")
                    st.markdown(targeting_result)
                
                with result_tab2:
                    st.header("Pourquoi Ces Cours Sont Parfaits pour Vous")
                    if copywriting_result:
                        st.markdown(copywriting_result)
                    else:
                        st.warning("Les recommandations détaillées n'ont pas pu être générées.")
                
                # Add download option
                results_df = pd.DataFrame([{
                    'Profil': json.dumps(student_data),
                    'Cours Recommandés': str(targeting_result),
                    'Détails des Cours': str(copywriting_result) if copywriting_result else "Non disponible"
                }])
                
                csv = results_df.to_csv(index=False)
                st.download_button(
                    label="Télécharger les Recommandations",
                    data=csv,
                    file_name="recommandations_cours.csv",
                    mime="text/csv"
                )

def show_history_page(db_manager, user_id):
    """Show user's recommendation history"""
    st.title("Mon Historique de Recommandations")
    
    recommendations = db_manager.get_user_recommendations(user_id)
    
    if not recommendations:
        st.info("Vous n'avez encore généré aucune recommandation. Allez dans 'Obtenir des Recommandations' pour commencer !")
        return
    
    st.write(f"Vous avez {len(recommendations)} recommandations sauvegardées :")
    
    for i, rec in enumerate(recommendations, 1):
        with st.expander(f"Recommandation #{i} - {rec['created_at'].strftime('%d/%m/%Y %H:%M')}"):
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.subheader("Votre Profil")
                profile = rec['student_profile']
                st.write(f"**Objectifs Académiques :** {profile.get('Academic Goals', 'N/A')}")
                st.write(f"**Spécialité :** {profile.get('Major', 'N/A')}")
                st.write(f"**Loisirs :** {profile.get('Hobbies', 'N/A')}")
                st.write(f"**Compétences Informatiques :** {profile.get('Computer Skills', 'N/A')}")
                st.write(f"**Langues :** {profile.get('Interest in Languages', 'N/A')}")
                st.write(f"**Moyenne :** {profile.get('GPA', 'N/A')}")
            
            with col2:
                st.subheader("Cours Recommandés")
                st.markdown(rec['recommended_courses'])
            
            if rec['course_details']:
                st.subheader("Détails des Cours")
                st.markdown(rec['course_details'])

def main():
    st.set_page_config(
        page_title="Système de Recommandation de Cours", 
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    # Initialize database and auth managers
    db_manager = DatabaseManager()
    auth_manager = AuthManager(db_manager)
    
    # Initialize session state
    auth_manager.init_session_state()
    
    # Create database tables if they don't exist
    db_manager.create_tables()
    
    # Check if user is logged in
    if not auth_manager.is_logged_in():
        auth_manager.login_page()
    else:
        show_user_dashboard(auth_manager, db_manager)

if __name__ == "__main__":
    main()