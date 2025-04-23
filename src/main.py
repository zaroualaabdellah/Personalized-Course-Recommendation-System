import streamlit as st
import pandas as pd
import os
import yaml
from crewai import Crew, Process

# Set environment variable to disable telemetry
os.environ["CREWAI_DISABLE_TELEMETRY"] = "true"

# Import local modules
from agent_loader import load_llm, create_agents
from task_factory import get_ad_campaign_task, get_ad_campaign_written_task, format_courses_list
from data_handler import load_courses_data

def main():
    st.set_page_config(page_title="Course Recommendation System", layout="wide")
    
    st.title("Personalized Course Recommendation System")
    st.write("Enter your details to get personalized course recommendations")
    
    # User input form
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
        
        submit_button = st.form_submit_button("Get Recommendations")
    
    if submit_button:
        with st.spinner("Analyzing your profile and finding the best courses for you..."):
            # Create student data
            student_data = {
                'Academic Goals': academic_goals,
                'Major': major,
                'Hobbies': hobbies,
                'Computer Skills': computer_skills,
                'Interest in Languages': interest_in_languages,
                'GPA': gpa
            }
            
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
                st.stop()
            
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
            except Exception as e:
                st.error(f"An error occurred during recommendation creation: {str(e)}")
                st.stop()
            
            # Display results in tabs
            st.success("Recommendations complete!")
            
            tab1, tab2 = st.tabs(["Selected Courses", "Detailed Recommendations"])
            
            with tab1:
                st.header("Selected Courses for You")
                st.markdown(targeting_result)
            
            with tab2:
                st.header("Why These Courses Are Perfect for You")
                st.markdown(copywriting_result)
            
            # Add download option
            results_df = pd.DataFrame([{
                'Profile': customer_description,
                'Recommended Courses': targeting_result,
                'Course Details': copywriting_result
            }])
            
            csv = results_df.to_csv(index=False)
            st.download_button(
                label="Download Recommendations",
                data=csv,
                file_name="course_recommendations.csv",
                mime="text/csv"
            )

if __name__ == "__main__":
    main()