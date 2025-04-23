import pandas as pd
import yaml

def load_student_data(file_path="data/student_data.csv"):
    """Load student data from CSV file."""
    return pd.read_csv(file_path)

def load_courses_data(file_path="config/courses.yaml"):
    """Load courses data from YAML file."""
    with open(file_path, 'r') as file:
        data = yaml.safe_load(file)
    return data['courses']

def format_student_description(student_row):
    """Format student data as a descriptive string."""
    return f"""
    Their academic goals are {student_row['Academic Goals']}.
    Their major is in {student_row['Major']}.
    Their Hobbies are {student_row['Hobbies']}.
    Their computer skills are {student_row['Computer Skills']}.
    Their interest in languages are {student_row['Interest in Languages']}.
    Their GPA is {student_row['GPA']}.
    """