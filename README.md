# Job Monitoring System

This system automatically monitors your email for new job listings, processes them, and sends a summarized report to your specified email address.

## Setup Instructions

### Using Dev Container

1. Open the Command Palette (Ctrl+Shift+P) and run:
   - "Dev Containers: Reopen in Container" (if you already have the project open)
   - OR "Dev Containers: Open Folder in Container" (if you want to open a new folder in a container)

2. The container will automatically:
   - Build the development environment
   - Install all dependencies
   - Configure VS Code extensions
   - Set up Chrome and ChromeDriver for Selenium

### Manual Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Create a `.env` file in the project root with the following variables:
```
OPENAI_API_KEY=your_openai_api_key
SENDER_EMAIL=your_email@gmail.com
SENDER_PASSWORD=your_app_specific_password
RECIPIENT_EMAIL=recipient_email@example.com
```

3. Set up Gmail API:
   - Go to Google Cloud Console (https://console.cloud.google.com/)
   - Create a new project
   - Enable Gmail API
   - Create credentials (OAuth 2.0 Client IDs)
   - Download the credentials.json file and place it in the project root

4. Run the script:
```bash
python job_monitor.py
```

## Features

- Automatically checks for new emails
- Extracts job listing links from emails
- Uses OpenAI's GPT to summarize job listings
- Creates a formatted summary table
- Sends summaries to specified email address
- Handles LinkedIn authentication for protected job listings

## Configuration

All configuration is done through the `.env` file. The main settings are:

- OpenAI API Configuration
- Gmail API Configuration
- Email Configuration (for sending summaries)
- LinkedIn Configuration (for job listings)
- Optional Configuration (check interval, max emails to process)
- Logging Configuration

## Note

- For Gmail, you'll need to use an App Password instead of your regular password
- The script needs to be run periodically (e.g., using cron) to check for new emails
- Make sure to handle your API keys and passwords securely
- The `.env` file should never be committed to version control
