# database.py
import mysql.connector
from mysql.connector import Error
import hashlib
import streamlit as st
from typing import Optional, Dict, Any
import os
from datetime import datetime

class DatabaseManager:
    def __init__(self):
        self.connection = None
        self.host = os.getenv('DB_HOST', 'localhost')
        self.database = os.getenv('DB_NAME', 'course_recommendation')
        self.username = os.getenv('DB_USER', 'root')
        self.password = os.getenv('DB_PASSWORD', '')
        self.port = os.getenv('DB_PORT', 3306)
    
    def connect(self):
        """Establish database connection"""
        try:
            self.connection = mysql.connector.connect(
                host=self.host,
                database=self.database,
                user=self.username,
                password=self.password,
                port=self.port
            )
            if self.connection.is_connected():
                return True
        except Error as e:
            st.error(f"Database connection error: {e}")
            return False
        return False
    
    def disconnect(self):
        """Close database connection"""
        if self.connection and self.connection.is_connected():
            self.connection.close()
    
    def create_tables(self):
        """Create necessary tables if they don't exist"""
        if not self.connect():
            return False
        
        try:
            cursor = self.connection.cursor()
            
            # Create users table
            create_users_table = """
            CREATE TABLE IF NOT EXISTS users (
                id INT AUTO_INCREMENT PRIMARY KEY,
                username VARCHAR(50) UNIQUE NOT NULL,
                email VARCHAR(100) UNIQUE NOT NULL,
                password_hash VARCHAR(255) NOT NULL,
                full_name VARCHAR(100),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_login TIMESTAMP NULL,
                is_active BOOLEAN DEFAULT TRUE
            )
            """
            
            # Create user_sessions table
            create_sessions_table = """
            CREATE TABLE IF NOT EXISTS user_sessions (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id INT,
                session_token VARCHAR(255) UNIQUE NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP,
                is_active BOOLEAN DEFAULT TRUE,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
            """
            
            # Create user_recommendations table to store recommendation history
            create_recommendations_table = """
            CREATE TABLE IF NOT EXISTS user_recommendations (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id INT,
                student_profile JSON,
                recommended_courses TEXT,
                course_details TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
            """
            
            cursor.execute(create_users_table)
            cursor.execute(create_sessions_table)
            cursor.execute(create_recommendations_table)
            
            self.connection.commit()
            return True
            
        except Error as e:
            st.error(f"Error creating tables: {e}")
            return False
        finally:
            cursor.close()
            self.disconnect()
    
    def hash_password(self, password: str) -> str:
        """Hash password using SHA-256"""
        return hashlib.sha256(password.encode()).hexdigest()
    
    def verify_password(self, password: str, password_hash: str) -> bool:
        """Verify password against hash"""
        return self.hash_password(password) == password_hash
    
    def create_user(self, username: str, email: str, password: str, full_name: str = None) -> bool:
        """Create a new user"""
        if not self.connect():
            return False
        
        try:
            cursor = self.connection.cursor()
            password_hash = self.hash_password(password)
            
            query = """
            INSERT INTO users (username, email, password_hash, full_name)
            VALUES (%s, %s, %s, %s)
            """
            
            cursor.execute(query, (username, email, password_hash, full_name))
            self.connection.commit()
            return True
            
        except Error as e:
            if "Duplicate entry" in str(e):
                st.error("Username or email already exists!")
            else:
                st.error(f"Error creating user: {e}")
            return False
        finally:
            cursor.close()
            self.disconnect()
    
    def authenticate_user(self, username: str, password: str) -> Optional[Dict[str, Any]]:
        """Authenticate user and return user data"""
        if not self.connect():
            return None
        
        try:
            cursor = self.connection.cursor(dictionary=True)
            
            query = """
            SELECT id, username, email, password_hash, full_name, is_active
            FROM users 
            WHERE username = %s AND is_active = TRUE
            """
            
            cursor.execute(query, (username,))
            user = cursor.fetchone()
            
            if user and self.verify_password(password, user['password_hash']):
                # Update last login
                update_query = "UPDATE users SET last_login = %s WHERE id = %s"
                cursor.execute(update_query, (datetime.now(), user['id']))
                self.connection.commit()
                
                # Remove password hash from returned data
                del user['password_hash']
                return user
            
            return None
            
        except Error as e:
            st.error(f"Authentication error: {e}")
            return None
        finally:
            cursor.close()
            self.disconnect()
    
    def save_recommendation(self, user_id: int, student_profile: dict, 
                          recommended_courses: str, course_details: str) -> bool:
        """Save user recommendation to database"""
        if not self.connect():
            return False
        
        try:
            cursor = self.connection.cursor()
            
            query = """
            INSERT INTO user_recommendations (user_id, student_profile, recommended_courses, course_details)
            VALUES (%s, %s, %s, %s)
            """
            
            import json
            profile_json = json.dumps(student_profile)
            cursor.execute(query, (user_id, profile_json, recommended_courses, course_details))
            self.connection.commit()
            return True
            
        except Error as e:
            st.error(f"Error saving recommendation: {e}")
            return False
        finally:
            cursor.close()
            self.disconnect()
    
    def get_user_recommendations(self, user_id: int) -> list:
        """Get user's recommendation history"""
        if not self.connect():
            return []
        
        try:
            cursor = self.connection.cursor(dictionary=True)
            
            query = """
            SELECT student_profile, recommended_courses, course_details, created_at
            FROM user_recommendations 
            WHERE user_id = %s 
            ORDER BY created_at DESC
            LIMIT 10
            """
            
            cursor.execute(query, (user_id,))
            recommendations = cursor.fetchall()
            
            # Parse JSON profile data
            for rec in recommendations:
                import json
                rec['student_profile'] = json.loads(rec['student_profile'])
            
            return recommendations
            
        except Error as e:
            st.error(f"Error fetching recommendations: {e}")
            return []
        finally:
            cursor.close()
            self.disconnect()


# auth.py
import streamlit as st
import uuid
from datetime import datetime, timedelta

class AuthManager:
    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager
    
    def init_session_state(self):
        """Initialize session state variables"""
        if 'logged_in' not in st.session_state:
            st.session_state.logged_in = False
        if 'user_data' not in st.session_state:
            st.session_state.user_data = None
        if 'session_token' not in st.session_state:
            st.session_state.session_token = None
    
    def login_page(self):
        """Display login page"""
        # Create three columns to center content
        col1, col2, col3 = st.columns([1, 2, 1])
        with col3:
            st.image("logo/logo4.png", width=250)
            st.markdown("<h1 style='text-align: center;'>🎓 Course Recommendation System</h1>", unsafe_allow_html=True)

        st.markdown("---")
        
        # Create tabs for login and registration
        login_tab, register_tab = st.tabs(["Login", "Register"])
        
        with login_tab:
            st.header("Login to Your Account")
            
            with st.form("login_form"):
                username = st.text_input("Username")
                password = st.text_input("Password", type="password")
                login_button = st.form_submit_button("Login")
                
                if login_button:
                    if username and password:
                        user_data = self.db.authenticate_user(username, password)
                        if user_data:
                            st.session_state.logged_in = True
                            st.session_state.user_data = user_data
                            st.success("Login successful!")
                            st.rerun()
                        else:
                            st.error("Invalid username or password!")
                    else:
                        st.error("Please enter both username and password!")
        
        with register_tab:
            st.header("Create New Account")
            
            with st.form("register_form"):
                new_username = st.text_input("Username", key="reg_username")
                new_email = st.text_input("Email", key="reg_email")
                new_full_name = st.text_input("Full Name", key="reg_full_name")
                new_password = st.text_input("Password", type="password", key="reg_password")
                confirm_password = st.text_input("Confirm Password", type="password", key="reg_confirm")
                register_button = st.form_submit_button("Register")
                
                if register_button:
                    if not all([new_username, new_email, new_password, confirm_password]):
                        st.error("Please fill in all required fields!")
                    elif new_password != confirm_password:
                        st.error("Passwords do not match!")
                    elif len(new_password) < 6:
                        st.error("Password must be at least 6 characters long!")
                    else:
                        if self.db.create_user(new_username, new_email, new_password, new_full_name):
                            st.success("Account created successfully! Please login.")
                        else:
                            st.error("Failed to create account. Username or email may already exist.")
    
    def logout(self):
        """Logout user"""
        st.session_state.logged_in = False
        st.session_state.user_data = None
        st.session_state.session_token = None
        st.rerun()
    
    def is_logged_in(self) -> bool:
        """Check if user is logged in"""
        return st.session_state.get('logged_in', False)
    
    def get_current_user(self) -> dict:
        """Get current user data"""
        return st.session_state.get('user_data', {})


# requirements.txt additions
"""
Add these to your requirements.txt:
mysql-connector-python==8.0.33
python-dotenv==1.0.0
"""

# .env file (create this file in your project root)
"""
DB_HOST=localhost
DB_NAME=course_recommendation
DB_USER=root
DB_PASSWORD=
DB_PORT=3306
"""