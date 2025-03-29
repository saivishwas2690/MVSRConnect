import re

def validate_email(email):
    if email.endswith("@mvsrec.edu.in"):
        return True
    return False


def extract_rollno(email):
    match = re.match(r"^(\d+)@mvsrec\.edu\.in$", email)
    return match.group(1) if match else None

def extract_batch(rollno):
    year = rollno[4:6]
    return int(year) + 2004

def extract_role(email):
    if extract_rollno(email):
        return "Student"
    return "Teacher"
    

