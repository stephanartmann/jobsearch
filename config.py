import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# OpenAI API configuration
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')

# Email configuration
EMAIL_ADDRESS = os.getenv('EMAIL_ADDRESS')
EMAIL_PASSWORD = os.getenv('EMAIL_PASSWORD')
TARGET_EMAIL = os.getenv('TARGET_EMAIL')

# Gmail API configuration
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']

# Job tracking
CHECK_INTERVAL = 3600  # Check every hour in seconds

# Summary prompt for OpenAI
SUMMARY_PROMPT = """Please analyze the following job posting and provide a concise summary including:
1. Job Title
2. Company Name
3. Location
4. Key Responsibilities
5. Required Qualifications
6. Salary Range (if available)

Format the response as a markdown table with these columns:
| Job Title | Company | Location | Key Responsibilities | Qualifications | Salary |

Job posting text:
{job_text}

Summary:"""
