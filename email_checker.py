# %%
import os
import time
import logging
from datetime import datetime
from job_monitor import main as job_monitor_main

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

def check_emails():
    """
    Main function to periodically check for new emails
    """
    try:
        logging.info("Starting email check...")
        job_monitor_main()
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
            check_emails()
            logging.info(f"Next check in {CHECK_INTERVAL/3600:.1f} hours")
            time.sleep(CHECK_INTERVAL)
        except KeyboardInterrupt:
            logging.info("Shutting down email checker service")
            break
        except Exception as e:
            logging.error(f"Unexpected error: {str(e)}")
            # Wait a bit before retrying
            time.sleep(60)

if __name__ == "__main__":
    main()

# %%
