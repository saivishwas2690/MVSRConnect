import requests
from django.conf import settings
import re

def fetch_adzuna_jobs():
    base_url = "https://api.adzuna.com/v1/api/jobs/in/search/1"
    params = {
        'app_id': settings.ADZUNA_APP_ID,
        'app_key': settings.ADZUNA_API_KEY,
        'results_per_page': 10,
        'what': 'software developer',
        'where': 'india',
        'content-type': 'application/json'
    }
    
    try:
        response = requests.get(base_url, params=params)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        print(f"Error fetching jobs: {e}")
        return None
    
def validate_email(email):
    if email.endswith("@mvsrec.edu.in"):
        return True
    return False

def extract_rollno(email):
    match = re.match(r"^(\d+)@mvsrec\.edu\.in$", email)
    return match.group(1) if match else None

def extract_batch(email, rollno):
    year = rollno[4:6]
    return int(year) + 2004

def extract_role(email):
    if extract_rollno(email):
        return "Student"
    return "Teacher"
    
