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
        description=dedent(f"""\
            You're creating a targeted marketing campaign tailored to what we know about our student customers.

            For each student customer, we have to choose exactly three courses to promote in the next campaign.
            Make sure the selection is the best possible and aligned with the student customer,
            review, approve, ask clarifying question or delegate follow up work if
            necessary to make decisions. When delegating work send the full draft
            as part of the information.
            
            This is the list of all the courses participating in the campaign: {courses_list}.
            This is all we know so far from the student customer: {customer_description}.

            To start this campaign we will need to build first an understanding of our student customer.
            Once we have a profile about the student customers interests, lifestyle and means and needs,
            we have to select exactly three courses that have the highest chance to be bought by them.

            Your final answer MUST be exactly 3 courses from the list, each with a short description
            why it matches with this student customer. It must be formatted like this example:
            :
            :
            :
            """),
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