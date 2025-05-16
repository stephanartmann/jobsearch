from utils import get_chrome_driver, get_page_content_with_driver, login_to_linkedin, login_to_webpage
import requests
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from langchain_core.tools import tool

driver = get_chrome_driver()

@tool
def login_to_webpage(url:str, login_fields:Dict[str,str])->bool:
    """
    Handle login for any webpage using the provided selectors

    Args:
        url: URL to log in to
        login_fields: Dictionary of login field selectors, format: {"username_selector": "css selector for username", "password_selector": "css selector for password", "submit_selector": "css selector for submit button"}

    Returns:
        True if login was successful, False otherwise
    """
    if 'linkedin' in url:
        return login_to_linkedin(driver)
    return login_to_webpage(driver,url,login_fields)

@tool
def get_page_content(url:str)->str:
    """
    Get page content from a URL

    Args:
        url: URL to get content from

    Returns:
        Page content as a string
    """
    page_content = get_page_content_with_driver(driver,url)
    return page_content

@tool
def get_next_monday_connections(from_location: str, to_location: str) -> Dict:
    """
    Get transport connections for next Monday from opentransport API

    Args:
        from_location: Departure location
        to_location: Arrival location

    Returns:
        Dictionary containing the API response with connections
    """
    # Calculate next Monday's date
    today = datetime.now()
    days_until_monday = (7 - today.weekday()) % 7
    next_monday = today + timedelta(days=days_until_monday)
    next_monday_date = next_monday.strftime('%Y-%m-%d')

    # Set default time to 08:00
    time = "08:00"

    # Build API URL with parameters
    base_url = "http://transport.opendata.ch/v1/connections"
    params = {
        'from': from_location,
        'to': to_location,
        'date': next_monday_date,
        'time': time,
        'limit': 5  # Return up to 5 connections
    }

    # Make API request
    response = requests.get(base_url, params=params)
    response.raise_for_status()  # Raise exception for bad status codes
    
    return response.json()
    