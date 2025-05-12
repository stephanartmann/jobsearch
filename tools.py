import os
import time
from datetime import datetime
import pandas as pd
import openai
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2 import service_account
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# OpenAI API configuration
openai.api_key = os.getenv('OPENAI_API_KEY')

# Gmail API configuration
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']

# Email and LinkedIn configuration
SENDER_EMAIL = os.getenv('SENDER_EMAIL')
SENDER_PASSWORD = os.getenv('SENDER_PASSWORD')
RECIPIENT_EMAIL = os.getenv('RECIPIENT_EMAIL')

# LinkedIn configuration
LINKEDIN_EMAIL = os.getenv('LINKEDIN_EMAIL')
LINKEDIN_PASSWORD = os.getenv('LINKEDIN_PASSWORD')
LINKEDIN_LOGIN_URL = 'https://www.linkedin.com/login'

# Prompt for job summarization
definition_prompt = """
You are a job listing summarizer. For each job listing, extract and summarize the following information:
1. Job Title
2. Company Name
3. Location
4. Job Type (Full-time, Part-time, etc.)
5. Key Responsibilities (top 3)
6. Required Skills (top 3)
7. Salary Range (if available)

Format the output as a markdown table with these columns:
| Job Title | Company | Location | Type | Key Responsibilities | Required Skills | Salary |

For each job, provide a concise summary of 1-2 sentences.
"""

def get_gmail_service():
    creds = None
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        with open('token.json', 'w') as token:
            token.write(creds.to_json())
    return build('gmail', 'v1', credentials=creds)

def extract_job_links(email_content):
    soup = BeautifulSoup(email_content, 'html.parser')
    links = []
    for link in soup.find_all('a'):
        href = link.get('href')
        if href and ('job' in href.lower() or 'apply' in href.lower()):
            links.append(href)
    return links

def login_to_linkedin(driver):
    """Login to LinkedIn using credentials"""
    try:
        driver.get(LINKEDIN_LOGIN_URL)
        
        # Wait for email field and enter email
        email_field = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, 'username'))
        )
        email_field.send_keys(LINKEDIN_EMAIL)
        
        # Enter password
        password_field = driver.find_element(By.ID, 'password')
        password_field.send_keys(LINKEDIN_PASSWORD)
        
        # Click login button
        login_button = driver.find_element(By.XPATH, "//button[@type='submit']")
        login_button.click()
        
        # Wait for login to complete
        time.sleep(5)
        
        return True
    except Exception as e:
        print(f"Error logging into LinkedIn: {str(e)}")
        return False

def analyze_webpage(url, page_content):
    """
    Use GPT-4 to analyze the webpage and determine if it's a job page or login page
    Returns: (is_job_page: bool, is_login_page: bool, login_fields: dict)
    """
    try:
        prompt = f"""
        You are a web page analyzer. Analyze the URL and page content to determine:
        1. If this is a job listing page
        2. If this is a login page
        3. If it's a login page, identify the username and password field selectors
        
        URL: {url}
        
        Page content (first 1000 characters):
        {page_content[:1000]}
        
        Format your response as JSON:
        {{
            "is_job_page": true/false,
            "is_login_page": true/false,
            "login_fields": {{
                "username_selector": "CSS selector",
                "password_selector": "CSS selector",
                "submit_selector": "CSS selector"
            }}
        }}
        """
        
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a web page analyzer."},
                {"role": "user", "content": prompt}
            ]
        )
        
        result = response.choices[0].message.content.strip()
        analysis = eval(result)  # Safely evaluate the JSON response
        return (analysis["is_job_page"], analysis["is_login_page"], analysis["login_fields"])
    except Exception as e:
        print(f"Error analyzing webpage: {str(e)}")
        return (False, False, {})


def login_to_webpage(driver, url, login_fields, username, password):
    """
    Handle login for any webpage using the provided selectors
    Returns: True if login was successful, False otherwise
    """
    try:
        driver.get(url)
        
        # Wait for username field and enter username
        username_field = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, login_fields["username_selector"]))
        )
        username_field.send_keys(username)
        
        # Enter password
        password_field = driver.find_element(By.CSS_SELECTOR, login_fields["password_selector"])
        password_field.send_keys(password)
        
        # Click login button
        login_button = driver.find_element(By.CSS_SELECTOR, login_fields["submit_selector"])
        login_button.click()
        
        # Wait for login to complete
        time.sleep(15)
        
        # Check if login was successful by looking for common error indicators
        error_elements = driver.find_elements(By.CSS_SELECTOR, ".error, .alert-error")
        return len(error_elements) == 0
    except Exception as e:
        print(f"Error logging into webpage: {str(e)}")
        return False

def get_job_listing_content(url, username=None, password=None):
    """
    Get job listing content from a URL, handling login if necessary
    Returns: job information as markdown table or None if failed
    """
    try:
        # Initialize Chrome driver
        service = Service(ChromeDriverManager().install())
        options = webdriver.ChromeOptions()
        options.add_argument('--headless')  # Run in headless mode
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        
        driver = webdriver.Chrome(service=service, options=options)
        
        # Get initial page content
        driver.get(url)
        time.sleep(3)  # Wait for content to load
        page_content = driver.page_source
        
        # Analyze the page to determine its type
        is_job_page, is_login_page, login_fields = analyze_webpage(url, page_content)
        
        if is_job_page:
            # Extract job information directly
            prompt = f"""
            {definition_prompt}
            
            Extract job information from this web page content:
            {page_content}
            """
            
            response = openai.ChatCompletion.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "You are a job listing analyzer."},
                    {"role": "user", "content": prompt}
                ]
            )
            
            job_info = response.choices[0].message.content.strip()
            driver.quit()
            return job_info
        
        elif is_login_page:
            if not username or not password:
                print("Login credentials required but not provided")
                driver.quit()
                return None
            
            # Perform login
            if login_to_webpage(driver, url, login_fields, username, password):
                # Get content after login
                time.sleep(3)  # Wait for content to load after login
                post_login_content = driver.page_source
                
                # Analyze again to confirm we have job content
                is_job_page, _, _ = analyze_webpage(url, post_login_content)
                
                if is_job_page:
                    prompt = f"""
                    {definition_prompt}
                    
                    Extract job information from this web page content:
                    {post_login_content}
                    """
                    
                    response = openai.ChatCompletion.create(
                        model="gpt-4",
                        messages=[
                            {"role": "system", "content": "You are a job listing analyzer."},
                            {"role": "user", "content": prompt}
                        ]
                    )
                    
                    job_info = response.choices[0].message.content.strip()
                    driver.quit()
                    return job_info
                else:
                    print("Login successful but no job content found")
                    driver.quit()
                    return None
            else:
                print("Login failed")
                driver.quit()
                return None
        
        else:
            print("Page is neither a job listing nor a login page")
            driver.quit()
            return None
    
    except Exception as e:
        print(f"Error getting job listing content: {str(e)}")
        return None

def summarize_job_listing(url):
    try:
        # Get job listing content
        content = get_job_listing_content(url)
        if "Error" in content:
            return content
            
        soup = BeautifulSoup(content, 'html.parser')
        
        # Extract main content
        content = "\n".join([p.get_text() for p in soup.find_all(['p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6'])])
        
        # Generate summary using OpenAI
        prompt = f"{definition_prompt}\n\nJob Listing:\n{content}\n\nGenerate summary:"
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are a job listing summarizer."},
                {"role": "user", "content": prompt}
            ]
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"Error processing URL: {str(e)}"

def send_email(subject, body):
    try:
        msg = MIMEMultipart()
        msg['From'] = SENDER_EMAIL
        msg['To'] = RECIPIENT_EMAIL
        msg['Subject'] = subject
        
        msg.attach(MIMEText(body, 'html'))
        
        with smtplib.SMTP('smtp.gmail.com', 587) as server:
            server.starttls()
            server.login(SENDER_EMAIL, SENDER_PASSWORD)
            server.send_message(msg)
        return True
    except Exception as e:
        print(f"Error sending email: {str(e)}")
        return False

def is_job_email(email_content):
    """
    Use OpenAI to determine if an email is job-related
    """
    try:
        prompt = f"""
        You are an email classifier. Analyze this email content and determine if it is a job-related email.
        An email is considered job-related if it contains:
        1. Job listings or job opportunities
        2. Recruiting or hiring information
        3. Job application instructions
        4. Career opportunities
        
        Email content:
        {email_content}
        
        Respond ONLY with 'yes' if it's job-related, or 'no' if it's not.
        """
        
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are an email classifier."},
                {"role": "user", "content": prompt}
            ]
        )
        
        answer = response.choices[0].message.content.strip().lower()
        return answer == 'yes'
    except Exception as e:
        print(f"Error classifying email: {str(e)}")
        return False

def main():
    # Initialize Gmail service
    service = get_gmail_service()
    
    # Get unread emails
    results = service.users().messages().list(userId='me', q='is:unread').execute()
    messages = results.get('messages', [])
    
    if not messages:
        print("No new emails found.")
        return
    
    job_summaries = []
    
    for message in messages:
        msg = service.users().messages().get(userId='me', id=message['id']).execute()
        email_content = msg['snippet']
        
        # Check if email is job-related
        if not is_job_email(email_content):
            print(f"Skipping non-job email: {msg['id']}")
            continue
            
        # Extract job links from email
        links = extract_job_links(email_content)
        
        for link in links:
            summary = summarize_job_listing(link)
            job_summaries.append(summary)
            
        # Mark email as read
        service.users().messages().modify(
            userId='me',
            id=message['id'],
            body={'removeLabelIds': ['UNREAD']}
        ).execute()
    
    if job_summaries:
        # Create summary table
        summary_table = "\n".join(job_summaries)
        
        # Send summary email
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        subject = f"New Job Listings Summary - {current_time}"
        
        send_email(subject, summary_table)
        print(f"Sent summary email with {len(job_summaries)} job listings")
    else:
        print("No job listings found in new emails.")

if __name__ == "__main__":
    main()
