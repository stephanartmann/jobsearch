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

def needs_login_check(url, page_content):
    """
    Use GPT-3.5-turbo to determine if login is needed based on URL and page content
    """
    try:
        prompt = f"""
        You are a web page analyzer. Analyze the URL and page content to determine if a login is required.
        
        URL: {url}
        
        Page content (first 1000 characters):
        {page_content[:1000]}
        
        Answer ONLY with 'yes' if login is required, or 'no' if not.
        """
        
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a web page analyzer."},
                {"role": "user", "content": prompt}
            ]
        )
        
        answer = response.choices[0].message.content.strip().lower()
        return answer != 'no'
    except Exception as e:
        print(f"Error checking login requirement: {str(e)}")
        return True

def get_job_listing_content(url):
    """Get job listing content using Selenium for LinkedIn links"""
    try:
        # Initialize Chrome driver
        service = Service(ChromeDriverManager().install())
        options = webdriver.ChromeOptions()
        options.add_argument('--headless')  # Run in headless mode
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        
        driver = webdriver.Chrome(service=service, options=options)
        
        # Navigate to URL first to check if login is needed
        driver.get(url)
        
        # Wait for page to load
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.TAG_NAME, 'body'))
        )
        
        # Get initial page content
        initial_content = driver.page_source
        
        # Check if login is needed
        if needs_login_check(url, initial_content):
            print(f"Login required for URL: {url}")
            # Login first
            if not login_to_linkedin(driver):
                return "Error: Failed to login to LinkedIn"
                
            # Navigate again after login
            driver.get(url)
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.TAG_NAME, 'body'))
            )
        
        # Get final page content
        page_content = driver.page_source
        
        # Close driver
        driver.quit()
        
        return page_content
    except Exception as e:
        return f"Error retrieving job listing: {str(e)}"

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
