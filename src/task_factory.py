from crewai import Task
from textwrap import dedent

def format_courses_list(courses_data):
    """Format courses data as a string list."""
    course_list = []
    for course in courses_data:
        course_str = f'"{course["name"]}" - Offered by {course["provider"]} on {course["platform"]}'
        course_list.append(course_str)
    return "\n".join(course_list)

def get_ad_campaign_task(agent, customer_description, courses_list):
    """Create task for selecting top 3 courses for a student."""
    return Task(
        description = dedent(f"""\ 
                        You're creating a targeted marketing campaign tailored to what we know about our student customers.

                        For each student customer, we have to choose exactly three courses to promote in the next campaign.
                        Make sure the selection is the best possible and aligned with the student customer.

                        This is the list of all the courses participating in the campaign: {courses_list}.
                        This is all we know so far from the student customer: {customer_description}.

                        To start this campaign, we need to build an understanding of our student customer,
                        then select exactly three courses that have the highest chance to be bought by them.

                        Your final answer MUST be a **plain list of exactly 3 course names**, nothing else.
                        No descriptions, no explanations, no formatting. Just the course names, each on a new line.
                        """)
                        ,
        agent=agent,
        expected_output='A refined finalized version of the marketing campaign in markdown format'
    )

def get_ad_campaign_written_task(agent, selection):
    """Create task for writing promotional content for selected courses."""
    return Task(
        description=dedent(f"""\
            You're creating a targeted marketing campaign tailored to what we know about our student customer.

            For each student customer, we have chosen three courses to promote in the next campaign.
            This selection is tailored specifically to the customer: {selection},

            To end this campaign succesfully we will need a promotional message advertising these courses to the student customer with the ultimate intent that they buy from us.
            This message should be around 3 paragraphs, so that it can be easily integrated into the full letter. For example:
            Interested in learning data science, get yourself enrolled in this course from Harvard University.
            Take Your career to the next level with the help of this course.

            You need to review, approve, and delegate follow up work if necessary to have the complete promotional message. When delegating work send the full draft
            as part of the information.

            Your final answer MUST include the 3 courses from the list, each with a short promotional message.
            """),
        agent=agent,
        expected_output='A refined finalized version of the marketing campaign in markdown format'
    )

def get_cv_analysis_task(agent, cv_text):
    """Create task for extracting information from a CV/resume."""
    return Task(
        description=dedent(f"""\
            You're tasked with analyzing a curriculum vitae (CV) or resume to extract key information about the student.
            
            Here is the complete text extracted from the CV:
            
            ```
            {cv_text}
            ```
            
            Please extract the following information:
            
            1. Academic Goals: What are the student's career or academic aspirations? Look for objectives, goals, or career summary sections.
            2. Major: What is their field of study or academic specialization?
            3. Hobbies/Interests: What activities or interests are mentioned outside of academics?
            4. Computer Skills: What is their level of computer proficiency? Categorize as Beginner, Intermediate, Advanced, or Expert.
            5. Language Skills: What languages are they proficient in or interested in learning?
            6. GPA: What is their Grade Point Average (if mentioned)? If not mentioned, use 3.0 as default.
            
            If any information is not explicitly mentioned in the CV, use your best judgment to infer it from the available context.
            If you absolutely cannot find or infer a piece of information, indicate "Not specified in CV".
            
            Format your response as a structured JSON object with the following fields:
            - Academic Goals
            - Major
            - Hobbies
            - Computer Skills
            - Interest in Languages
            - GPA
            
            Your final answer should be a well-structured JSON object containing all the extracted information.
            """),
        agent=agent,
        expected_output='A JSON object containing extracted information from the CV'
    )