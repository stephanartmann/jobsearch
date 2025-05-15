# %%
import os
import time
import logging
from datetime import datetime
from tools import *
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
import openai
from dotenv import load_dotenv
from typing import Callable,Optional

from utils import get_unread_emails


# Load environment variables
load_dotenv()

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

# %% Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('email_checker.log'),
        logging.StreamHandler()
    ]
)

# Interval in seconds (12 hours = 43200 seconds)
CHECK_INTERVAL = int(os.getenv('CHECK_INTERVAL', 43200))



def get_job_listing_content(url, username=None, password=None):
    """
    Get job listing content from a URL, handling login if necessary
    Returns: job information as markdown table or None if failed
    """
    try:
        driver = get_chrome_driver()
        page_content = get_page_content(driver,url)
        
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



def process_job_emails(email_contents: List[str],filter_callable:Optional[Callable[[str],bool]]=None) -> None:
    """
    Process job-related emails by extracting job links and generating summaries.
    
    Args:
        email_contents: List of email contents to process
        filter_callable: Optional callable to filter job emails
    """
    job_summaries = []
    
    for email_content in email_contents:
        # Check if email is job-related
        if filter_callable is not None and not filter_callable(email_content):
            print(f"Skipping non-job email")
            continue
            
        # Extract job links from email
        links = extract_job_links(email_content)
        
        for link in links:
            summary = summarize_job_listing(link)
            job_summaries.append(summary)
    
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

def process_new_mails():
    """
    Main function to periodically check for new emails and process them
    """
    try:
        logging.info("Starting email check...")
        process_job_emails(get_unread_emails(),filter_callable=is_job_email)
        logging.info("Email check completed successfully")
    except Exception as e:
        logging.error(f"Error during email check: {str(e)}")

def main():
    """
    Run periodic email checks
    """
    logging.info("Starting Email Checker Service")
    
    while True:
        try:
            process_new_mails()
            logging.info(f"Next check in {CHECK_INTERVAL/3600:.1f} hours")
            time.sleep(CHECK_INTERVAL)
        except KeyboardInterrupt:
            logging.info("Shutting down email checker service")
            break
        except Exception as e:
            logging.error(f"Unexpected error: {str(e)}")
            # Wait a bit before retrying
            time.sleep(60)

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

if __name__ == "__main__":
    main()

# %%
