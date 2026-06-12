#!/usr/bin/env python3
"""
Scheduler for Fathom → Notion → Email Workflow
Runs the workflow at specified times using the schedule library
"""

import os
import time
import schedule
import logging
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Import the workflow
from fathom_notion_workflow import FathomNotionWorkflow

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('workflow.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class WorkflowScheduler:
    """Manages scheduling of the Fathom-Notion workflow"""
    
    def __init__(self):
        """Initialize scheduler"""
        self.workflow = FathomNotionWorkflow()
        self.schedule_time = os.environ.get("SCHEDULE_TIME", "09:00")  # Default 9 AM
        logger.info(f"Scheduler initialized. Scheduled time: {self.schedule_time}")
    
    def job_wrapper(self):
        """Wrapper for scheduled job with error handling"""
        try:
            logger.info(f"[{datetime.now()}] Starting scheduled run...")
            self.workflow.run()
        except Exception as e:
            logger.error(f"Scheduled workflow error: {e}", exc_info=True)
    
    def start(self):
        """Start the scheduler and run indefinitely"""
        # Schedule the job
        schedule.every().day.at(self.schedule_time).do(self.job_wrapper)
        
        logger.info(f"Scheduler started. Next run: {self.schedule_time} daily")
        logger.info("Press Ctrl+C to stop")
        
        # Keep scheduler running
        try:
            while True:
                schedule.run_pending()
                time.sleep(60)  # Check every minute
        except KeyboardInterrupt:
            logger.info("Scheduler stopped by user")


def run_once():
    """Run the workflow once (for testing)"""
    logger.info("Running workflow once (test mode)...")
    workflow = FathomNotionWorkflow()
    workflow.run()


def main():
    """Main entry point"""
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "--once":
        # Run once for testing
        run_once()
    else:
        # Start scheduler
        scheduler = WorkflowScheduler()
        scheduler.start()


if __name__ == "__main__":
    main()
