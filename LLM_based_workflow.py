from typing import Dict, List, Any, TypedDict, Optional, Literal
from langgraph.graph import StateGraph, END
from langchain.chat_models import init_chat_model
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.output_parsers import JsonOutputParser
from pydantic import BaseModel, Field
import json
import re

from tools import (
    get_chrome_driver,
    get_page_content,
    extract_job_links,
    login_to_linkedin,
    login_to_webpage
)

# Define the state schema for the workflow
class WorkflowState(TypedDict):
    email_content: str
    extracted_links: List[str]
    job_details: List[Dict[str, Any]]
    current_page_content: Optional[str]
    current_url: Optional[str]

# Define the output model for job details
class JobDetails(BaseModel):
    title: str = Field(description="Job title")
    company: str = Field(description="Company name")
    location: str = Field(description="Job location")
    description: str = Field(description="Job description")
    requirements: List[str] = Field(description="List of job requirements")
    salary: Optional[str] = Field(description="Salary range if available")
    application_deadline: Optional[str] = Field(description="Application deadline if available")
    application_url: str = Field(description="URL to apply for the job")
    source: str = Field(description="Source website of the job posting")

# Initialize the LLM
llm = init_chat_model(
    model="openai/gpt-4-turbo",
    temperature=0.1,
    model_kwargs={"model": "gpt-4-turbo"}
)

# Define the nodes of the workflow
def extract_links(state: WorkflowState) -> WorkflowState:
    """Extract job-related links from the email content."""
    email_content = state["email_content"]
    
    # Use regex to find URLs in the email
    url_pattern = r'https?://[^\s\n"]+'
    all_links = re.findall(url_pattern, email_content)
    
    # Filter for job-related links
    job_links = [
        link for link in all_links 
        if any(keyword in link.lower() for keyword in ['job', 'career', 'recruiting', 'hiring', 'apply'])
    ]
    
    return {
        **state,
        "extracted_links": job_links,
        "job_details": []
    }

def process_link(state: WorkflowState) -> WorkflowState:
    """Process a single link to extract job details."""
    if not state["extracted_links"]:
        return state
    
    current_url = state["extracted_links"].pop(0)
    driver = get_chrome_driver()
    
    try:
        # Get page content
        page_content = get_page_content(driver, current_url)
        
        # Check if login is required
        if any(login_indicator in page_content.lower() 
               for login_indicator in ['login', 'sign in', 'log in']):
            if 'linkedin.com' in current_url:
                login_to_linkedin(driver)
            else:
                # Try with generic login if credentials are available
                login_fields = {
                    "username_selector": "input[type='email'], input[name='email']",
                    "password_selector": "input[type='password']",
                    "submit_selector": "button[type='submit'], input[type='submit']"
                }
                login_to_webpage(driver, current_url, login_fields)
                
                # Refresh page content after login
                page_content = get_page_content(driver, current_url)
        
        return {
            **state,
            "current_page_content": page_content,
            "current_url": current_url
        }
    except Exception as e:
        print(f"Error processing {current_url}: {str(e)}")
        return state
    finally:
        driver.quit()

def extract_job_details(state: WorkflowState) -> WorkflowState:
    """Extract job details from the current page content using LLM."""
    if not state.get("current_page_content"):
        return state
    
    # Create a prompt for the LLM to extract job details
    prompt = """
    Extract the job details from the following webpage content. 
    Return the information in JSON format with the following structure:
    {
        "title": "Job Title",
        "company": "Company Name",
        "location": "Job Location",
        "description": "Job Description",
        "requirements": ["Requirement 1", "Requirement 2", ...],
        "salary": "Salary range if available",
        "application_deadline": "Deadline if available",
        "application_url": "URL to apply",
        "source": "Source website"
    }
    
    Webpage Content:
    {content}
    """
    
    messages = [
        ("system", "You are a helpful assistant that extracts job details from web pages."),
        ("human", prompt.format(content=state["current_page_content"][:10000]))  # Limit content size
    ]
    
    try:
        # Get response from LLM
        response = llm.invoke(messages)
        
        # Extract JSON from response
        json_str = response.content
        if '```json' in json_str:
            json_str = json_str.split('```json')[1].split('```')[0]
        
        # Parse and validate the job details using the Pydantic model
        job_detail = json.loads(json_str)
        job_detail['source'] = state["current_url"]
        
        # Validate the job details against our model
        validated_job = JobDetails(
            title=job_detail.get('title', ''),
            company=job_detail.get('company', ''),
            location=job_detail.get('location', ''),
            description=job_detail.get('description', ''),
            requirements=job_detail.get('requirements', []),
            salary=job_detail.get('salary'),
            application_deadline=job_detail.get('application_deadline'),
            application_url=job_detail.get('application_url', state["current_url"]),
            source=job_detail.get('source', state["current_url"])
        )
        
        # Convert the validated job back to a dictionary
        validated_job_dict = validated_job.dict()
        
        return {
            **state,
            "job_details": state["job_details"] + [validated_job_dict]
        }
    except Exception as e:
        print(f"Error extracting job details: {str(e)}")
        return state

def should_continue(state: WorkflowState) -> Literal["process_link", "end"]:
    """Determine if there are more links to process."""
    if state["extracted_links"]:
        return "process_link"
    return "end"

# Create the workflow
workflow = StateGraph(WorkflowState)

# Add nodes
workflow.add_node("extract_links", extract_links)
workflow.add_node("process_link", process_link)
workflow.add_node("extract_job_details", extract_job_details)

# Add edges
workflow.set_entry_point("extract_links")
workflow.add_edge("extract_links", "process_link")
workflow.add_conditional_edges(
    "process_link",
    should_continue,
    {
        "process_link": "extract_job_details",
        "end": END
    }
)
workflow.add_edge("extract_job_details", "process_link")

# Compile the workflow
app = workflow.compile()

def process_job_email(email_content: str) -> List[Dict[str, Any]]:
    """
    Process an email to extract job details from linked job sites.
    
    Args:
        email_content: The content of the email to process
        
    Returns:
        List of extracted job details
    """
    # Initialize the state
    initial_state = {
        "email_content": email_content,
        "extracted_links": [],
        "job_details": [],
        "current_page_content": None,
        "current_url": None
    }
    
    # Run the workflow
    for output in app.stream(initial_state):
        if "end" in output:
            break
    
    # Return the collected job details
    return output["end"][1].get("job_details", [])

# Example usage
if __name__ == "__main__":
    example_email = """
    Subject: Exciting Job Opportunity at TechCorp
    
    Hi there,
    
    I came across your profile and thought you might be interested in this position:
    
    - Senior Software Engineer: https://example.com/jobs/123
    - Another great opportunity: https://example.com/careers/456
    
    Best regards,
    Recruiter
    """
    
    job_details = process_job_email(example_email)
    print(f"Extracted {len(job_details)} job details:")
    for job in job_details:
        print(f"\n{job['title']} at {job['company']} - {job['location']}")
        print(f"Apply here: {job['application_url']}")
