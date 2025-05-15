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
from typing import List, Dict, Optional, Any
import logging

from gmail_handling import get_gmail_service


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Constants
DEFAULT_CHROME_OPTIONS = {
    'headless': True,
    'no_sandbox': True,
    'disable_dev_shm_usage': True
}

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

def get_chrome_driver() -> webdriver.Chrome:
    """Initialize Chrome driver"""
    service = Service(ChromeDriverManager().install())
    options = webdriver.ChromeOptions()
    options.add_argument('--headless')  # Run in headless mode
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    driver = webdriver.Chrome(service=service, options=options)
    return driver
    except Exception as e:
        logger.error(f"Failed to initialize Chrome driver: {str(e)}")
        raise

def get_page_content(driver: webdriver.Chrome, url: str) -> str:
    """
    Get page content from a URL

    Args:
        driver: Selenium WebDriver instance
        url: URL to retrieve content from

    Returns:
        Page content as a string
    """
    driver.get(url)
    time.sleep(3)  # Wait for content to load
    page_content = driver.page_source
    return page_content

def extract_job_links(
    content: str,
    keywords: List[str] = ['job', 'apply'],
    min_link_length: int = 10
) -> List[str]:
    """
    Extract job-related links from HTML content.

    Args:
        content: HTML content to parse
        keywords: List of keywords to match in links
        min_link_length: Minimum length for valid links

    Returns:
        List of extracted job-related links
    """
    soup = BeautifulSoup(content, 'html.parser')
    links = []
    
    try:
        for link in soup.find_all('a'):
            href = link.get('href')
        if href and any([keyword in href.lower() for keyword in keywords]):
                links.append(href)
        
        logger.info(f"Extracted {len(links)} job-related links")
        return links
    except Exception as e:
        logger.error(f"Error extracting links: {str(e)}")
        return []

def login_to_linkedin(driver:webdriver.Chrome)->bool:
    """
    Login to LinkedIn using provided credentials.

    Args:
        driver: Selenium WebDriver instance


    Returns:
        True if login was successful, False otherwise
    """
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
        
        # Wait for successful login (e.g., check for profile page)
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, 'profile-nav-item'))
        )
        
        logger.info("LinkedIn login successful")
        return True
    except Exception as e:
        logger.error(f"LinkedIn login failed: {str(e)}")
        return False




def login_to_webpage(driver:webdriver.Chrome, url:str, login_fields:Dict[str,str])->bool:
    """
    Handle login for any webpage using the provided selectors

    Args:
        driver: Selenium WebDriver instance
        url: URL to log in to
        login_fields: Dictionary of login field selectors, format: {"username_selector": "css selector for username", "password_selector": "css selector for password", "submit_selector": "css selector for submit button"}

    Returns:
        True if login was successful, False otherwise
    """
    try:
        driver.get(url)

        username = os.getenv('GENERIC_LOGIN_EMAIL')
        password = os.getenv('GENERIC_LOGIN_PASSWORD')
        
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

def send_email(subject:str,body:str)->bool:
    """
    Send an email using SMTP

    Args:
        subject: Email subject
        body: Email body

    Returns:
        True if email was sent successfully, False otherwise
    """
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

def get_unread_emails() -> List[str]:
    """
    Retrieve content of unread emails from Gmail.
    
    Returns:
        List of email contents (snippets) from unread emails
    """
    # Initialize Gmail service
    service = get_gmail_service()
    
    # Get unread emails
    results = service.users().messages().list(userId='me', q='is:unread').execute()
    messages = results.get('messages', [])
    
    if not messages:
        print("No new emails found.")
        return []
    
    email_contents = []
    
    for message in messages:
        msg = service.users().messages().get(userId='me', id=message['id']).execute()
        email_content = msg['snippet']
        email_contents.append(email_content)
        
    # Mark emails as read
    for message in messages:
        service.users().messages().modify(
            userId='me',
            id=message['id'],
            body={'removeLabelIds': ['UNREAD']}
        ).execute()
    
    return email_contents

