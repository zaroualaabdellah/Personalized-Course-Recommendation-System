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
                data[field] = "Not specified in CV"
        
        # Convert GPA to float if it's a string
        if isinstance(data['GPA'], str) and data['GPA'].replace('.', '', 1).isdigit():
            data['GPA'] = float(data['GPA'])
        elif not isinstance(data['GPA'], (int, float)):
            data['GPA'] = 3.0  # Default value
        
        return data
    except Exception as e:
        st.error(f"Error parsing CV analysis result: {str(e)}")
        st.write("Raw result:", result)
        # Return default values
        return {
            'Academic Goals': "Not specified in CV",
            'Major': "Not specified in CV",
            'Hobbies': "Not specified in CV",
            'Computer Skills': "Intermediate",
            'Interest in Languages': "Not specified in CV",
            'GPA': 3.0
        }

def run_recommendation(student_data, db_manager, user_id):
    """Run the recommendation system with the provided student data."""
    # Format student description
    customer_description = f"""
    Their academic goals are {student_data['Academic Goals']}.
    Their major is in {student_data['Major']}.
    Their Hobbies are {student_data['Hobbies']}.
    Their computer skills are {student_data['Computer Skills']}.
    Their interest in languages are {student_data['Interest in Languages']}.
    Their GPA is {student_data['GPA']}.
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
    st.text("Step 1/2: Analyzing your profile and selecting courses...")
    
    try:
        targeting_result = targeting_crew.kickoff()
        progress_bar1.progress(100)
    except Exception as e:
        st.error(f"An error occurred during course selection: {str(e)}")
        return None, None
    
    # Task 2: Generate recommendation campaign
    task2 = get_ad_campaign_written_task(
        agents['chief_recommendation_director'],
        targeting_result
    )
    
    # Add progress bar for second task
    progress_bar2 = st.progress(0)
    st.text("Step 2/2: Creating personalized recommendations...")
    
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
        st.error(f"An error occurred during recommendation creation: {str(e)}")
        return targeting_result, None

def show_user_dashboard(auth_manager, db_manager):
    """Show user dashboard with profile and history"""
    user = auth_manager.get_current_user()
    
    # Sidebar with user info and logout
    with st.sidebar:
        st.header(f"Welcome, {user.get('full_name', user.get('username', 'User'))}! 👋")
        st.write(f"**Username:** {user.get('username')}")
        st.write(f"**Email:** {user.get('email')}")
        
        st.markdown("---")
        
        if st.button("🔓 Logout", type="secondary"):
            auth_manager.logout()
        
        st.markdown("---")
        
        # Navigation
        page = st.radio("Navigate", ["Get Recommendations", "My History"])
    
    if page == "Get Recommendations":
        show_recommendation_page(db_manager, user['id'])
    else:
        show_history_page(db_manager, user['id'])

def show_recommendation_page(db_manager, user_id):
    """Show the main recommendation page"""
    st.title("Personalized Course Recommendation System")
    st.write("Get personalized course recommendations based on your profile")
    
    # Create tabs for different input methods
    tab1, tab2 = st.tabs(["Upload CV/Resume", "Fill Form"])
    
    student_data = None
    submit_pressed = False
    
    # Initialize LLM once for reuse
    llm = load_llm()
    
    # Tab 1: CV Upload
    with tab1:
        st.header("Upload your CV/Resume")
        uploaded_file = st.file_uploader("Choose a file", type=["pdf", "docx", "txt"])
        
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
                    st.error("Unsupported file format")
                    st.stop()
                
                # Show CV analysis in progress
                with st.spinner("Analyzing your CV..."):
                    st.success("File uploaded successfully!")
                    
                    # Use the CV analyzer agent to extract information
                    extracted_data = analyze_cv_with_agent(cv_text, llm)
                
                # Display extracted information for verification
                st.subheader("Extracted Information")
                st.info("Please verify and edit the extracted information if needed:")
                
                # Allow user to edit the extracted information
                academic_goals = st.text_area("Academic Goals", value=extracted_data['Academic Goals'])
                major = st.text_input("Major", value=extracted_data['Major'])
                hobbies = st.text_input("Hobbies", value=extracted_data['Hobbies'])
                
                # Determine index for computer skills dropdown
                skills_options = ["Beginner", "Intermediate", "Advanced", "Expert"]
                skill_index = 1  # Default to Intermediate
                if extracted_data['Computer Skills'] in skills_options:
                    skill_index = skills_options.index(extracted_data['Computer Skills'])
                
                computer_skills = st.selectbox("Computer Skills", 
                                              skills_options,
                                              index=skill_index)
                
                interest_in_languages = st.text_input("Interest in Languages", value=extracted_data['Interest in Languages'])
                gpa = st.slider("GPA", min_value=0.0, max_value=4.0, value=float(extracted_data['GPA']), step=0.1)
                
                # Update student data
                student_data = {
                    'Academic Goals': academic_goals,
                    'Major': major,
                    'Hobbies': hobbies,
                    'Computer Skills': computer_skills,
                    'Interest in Languages': interest_in_languages,
                    'GPA': gpa
                }
                
                submit_pressed = st.button("Get Recommendations", key="cv_submit")
                
            except Exception as e:
                st.error(f"Error processing file: {str(e)}")
    
    # Tab 2: Manual Form
    with tab2:
        st.header("Enter Your Information")
        
        with st.form("student_info_form"):
            col1, col2 = st.columns(2)
            
            with col1:
                academic_goals = st.text_area("Academic Goals", placeholder="E.g., To become a software engineer")
                major = st.text_input("Major", placeholder="E.g., Computer Science")
                hobbies = st.text_input("Hobbies", placeholder="E.g., Gaming, Reading")
            
            with col2:
                computer_skills = st.selectbox("Computer Skills", 
                                              ["Beginner", "Intermediate", "Advanced", "Expert"])
                interest_in_languages = st.text_input("Interest in Languages", placeholder="E.g., Spanish, Python")
                gpa = st.slider("GPA", min_value=0.0, max_value=4.0, value=3.0, step=0.1)
            
            form_submit = st.form_submit_button("Get Recommendations")
            
            if form_submit:
                student_data = {
                    'Academic Goals': academic_goals,
                    'Major': major,
                    'Hobbies': hobbies,
                    'Computer Skills': computer_skills,
                    'Interest in Languages': interest_in_languages,
                    'GPA': gpa
                }
                submit_pressed = True
    
    # Process recommendations if data is available and button is pressed
    if student_data and submit_pressed:
        with st.spinner("Analyzing your profile and finding the best courses for you..."):
            targeting_result, copywriting_result = run_recommendation(student_data, db_manager, user_id)
            
            if targeting_result:
                # Display results in tabs
                st.success("Recommendations complete!")
                
                result_tab1, result_tab2 = st.tabs(["Selected Courses", "Detailed Recommendations"])
                
                with result_tab1:
                    st.header("Selected Courses for You")
                    st.markdown(targeting_result)
                
                with result_tab2:
                    st.header("Why These Courses Are Perfect for You")
                    if copywriting_result:
                        st.markdown(copywriting_result)
                    else:
                        st.warning("Detailed recommendations could not be generated.")
                
                # Add download option
                results_df = pd.DataFrame([{
                    'Profile': json.dumps(student_data),
                    'Recommended Courses': str(targeting_result),
                    'Course Details': str(copywriting_result) if copywriting_result else "Not available"
                }])
                
                csv = results_df.to_csv(index=False)
                st.download_button(
                    label="Download Recommendations",
                    data=csv,
                    file_name="course_recommendations.csv",
                    mime="text/csv"
                )

def show_history_page(db_manager, user_id):
    """Show user's recommendation history"""
    st.title("My Recommendation History")
    
    recommendations = db_manager.get_user_recommendations(user_id)
    
    if not recommendations:
        st.info("You haven't generated any recommendations yet. Go to 'Get Recommendations' to start!")
        return
    
    st.write(f"You have {len(recommendations)} saved recommendations:")
    
    for i, rec in enumerate(recommendations, 1):
        with st.expander(f"Recommendation #{i} - {rec['created_at'].strftime('%Y-%m-%d %H:%M')}"):
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.subheader("Your Profile")
                profile = rec['student_profile']
                st.write(f"**Academic Goals:** {profile.get('Academic Goals', 'N/A')}")
                st.write(f"**Major:** {profile.get('Major', 'N/A')}")
                st.write(f"**Hobbies:** {profile.get('Hobbies', 'N/A')}")
                st.write(f"**Computer Skills:** {profile.get('Computer Skills', 'N/A')}")
                st.write(f"**Languages:** {profile.get('Interest in Languages', 'N/A')}")
                st.write(f"**GPA:** {profile.get('GPA', 'N/A')}")
            
            with col2:
                st.subheader("Recommended Courses")
                st.markdown(rec['recommended_courses'])
            
            if rec['course_details']:
                st.subheader("Course Details")
                st.markdown(rec['course_details'])

def main():
    st.set_page_config(
        page_title="Course Recommendation System", 
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