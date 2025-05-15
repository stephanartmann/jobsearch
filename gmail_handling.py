import os
from typing import Optional, List, Any
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from dotenv import load_dotenv
from logging import getLogger

load_dotenv()
logger = getLogger(__name__)

def get_gmail_service(
    token_path: Optional[str] = None,
    scopes: Optional[List[str]] = None
) -> Any:
    """
    Get Gmail service object using OAuth 2.0 authentication with environment variables.

    Args:
        token_path: Path to save OAuth token (optional, defaults to env variable)
        scopes: List of OAuth scopes to request

    Returns:
        Gmail API service object

    Raises:
        ValueError: If credentials are missing or invalid
    """
    scopes = scopes or ['https://www.googleapis.com/auth/gmail.readonly']
    creds = None
    
    try:
        # Load credentials from environment variables
        client_id = os.getenv('GMAIL_CLIENT_ID')
        client_secret = os.getenv('GMAIL_CLIENT_SECRET')
        refresh_token = os.getenv('GMAIL_REFRESH_TOKEN')
        
        if not all([client_id, client_secret, refresh_token]):
            raise ValueError("Missing Gmail API credentials in environment variables")
            
        # Create credentials object
        creds = Credentials(
            None,  # token will be refreshed
            refresh_token=refresh_token,
            token_uri='https://oauth2.googleapis.com/token',
            client_id=client_id,
            client_secret=client_secret
        )
        
        # Save token if needed
        if token_path is None:
            token_path = os.getenv('GMAIL_TOKEN_PATH', 'token.json')
        
        if not os.path.exists(token_path):
            with open(token_path, 'w') as token:
                token.write(creds.to_json())
        
        service = build('gmail', 'v1', credentials=creds)
        logger.info("Gmail service initialized successfully")
        return service
    except ValueError as e:
        logger.error(f"Credentials error: {str(e)}")
        raise
    except Exception as e:
        logger.error(f"Failed to get Gmail service: {str(e)}")
        raise