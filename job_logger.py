import csv
import os
from datetime import datetime

# Path to log file
SKIPPED_LOG_PATH = "skipped_jobs.csv"

# Ensure headers are written only once
def initialize_log_file():
    if not os.path.exists(SKIPPED_LOG_PATH):
        with open(SKIPPED_LOG_PATH, mode='w', newline='', encoding='utf-8') as file:
            writer = csv.writer(file)
            writer.writerow(['Job ID', 'Title', 'Company', 'Reason', 'Search Term', 'Timestamp'])

# Function to log skipped job
def log_skipped_job(job_id: str, title: str, company: str, reason: str, search_term: str) -> None:
    try:
        initialize_log_file()
        with open(SKIPPED_LOG_PATH, mode='a', newline='', encoding='utf-8') as file:
            writer = csv.writer(file)
            writer.writerow([job_id, title, company, reason, search_term, datetime.now().isoformat()])
    except Exception as e:
        print(f"Failed to log skipped job {job_id}: {e}")
