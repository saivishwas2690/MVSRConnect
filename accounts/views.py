# Standard library imports
import json
import re
import secrets
import logging

# Django core imports
from django.http import JsonResponse, HttpResponse
from django.shortcuts import render, redirect
from django.views.decorators.csrf import csrf_protect, csrf_exempt
from django.middleware.csrf import get_token
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.hashers import make_password
from django.core.exceptions import ValidationError
from django.core.mail import send_mail
from django.core.validators import validate_email
from django.db import models
from django.db.models import Q
from django.conf import settings

# Django user model
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AbstractUser

# REST Framework
from rest_framework.response import Response

# Local apps
from .models import *
from projects_app.models import *
from .utils import (
    fetch_adzuna_jobs,
    validate_email,
    extract_rollno,
    extract_batch,
    extract_role
)


logger = logging.getLogger(__name__)

PLATFORMS = [platform[0] for platform in SocialLink.PLATFORM_CHOICES]



def user_display(request):
    if request.user.role == "Student":
        return request.user.roll_no
    else:
        return request.user.username
        


@login_required
def home(request):
    try:
        usedisplay = ""
        if request.user.role == "Student":
            usedisplay = request.user.roll_no
        else:
            usedisplay = request.user.username

        context = {"userdisplay": usedisplay}
        return render(request, "home.html", context)

    except Exception as e:
        logger.error(f"Error in home view: {str(e)}", exc_info=True)
        return JsonResponse({"error": "Internal Server Error"}, status=500)

def send_verification_email(request):
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            email = data.get("email")

            try:
                if not validate_email(email):
                    return JsonResponse({"error": "Email is not valid"}, status=400)
            except ValidationError:
                return JsonResponse({"error": "Email is not valid"}, status=400)

            if NewUser.objects.filter(email=email).exists():
                return JsonResponse({"error": "Email verification mail has been sent already, Please check in spam also."}, status=400)

            token = secrets.token_hex(16)
            HOST = settings.ALLOWED_HOSTS[0]
            verification_link = f"{HOST}/verify/{token}"

            subject = "MVSRConnect Email Verification"
            try:
                send_mail(subject, verification_link, settings.EMAIL_HOST_USER, [email])
            except Exception as e:
                logger.error(f"Failed to send email: {str(e)}", exc_info=True)
                return JsonResponse({"error": "Failed to send email"}, status=500)

            user = NewUser.objects.create(email=email, token=token)
            user.save()

            return JsonResponse({"success": "Verification email sent successfully"}, status=200)

        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON data"}, status=400)
        
        except IntegrityError:
            return JsonResponse({"error": "Database error"}, status=500)

        except Exception as e:
            logger.error(f"Unexpected error: {str(e)}", exc_info=True)
            return JsonResponse({"error": "Internal Server Error"}, status=500)
        


def send_reset_password_mail(request):
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            email = data.get("email")
            print(data)

            try:
                if not validate_email(email):
                    return JsonResponse({"error": "Invalid email"}, status=400)
            except ValidationError:
                return JsonResponse({"error": "Invalid email"}, status=400)

            try:
                user = User.objects.get(email=email)
            except User.DoesNotExist:
                return JsonResponse({"error": "User with this email does not exist"}, status=404)

        
            token = secrets.token_urlsafe(48)
            UserForgotPassword.objects.create(user=user, token=token)

            HOST = settings.ALLOWED_HOSTS[0] if settings.ALLOWED_HOSTS else "http://localhost:8000"
            reset_link = f"{HOST}/reset-password/{token}"

            subject = "MVSRConnect - Reset Your Password"
            message = f"Click the link below to reset your password:\n\n{reset_link}\n\nIf you did not request this, ignore this email."
            try:
                send_mail(subject, message, settings.EMAIL_HOST_USER, [email])
            except Exception as e:
                return JsonResponse({"error": "Failed to send email"}, status=500)

            return JsonResponse({"success": "Reset password link sent to your email"}, status=200)

        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON"}, status=400)
        
        except Exception as e:
            return JsonResponse({"error": "Something went wrong. Try again later."}, status=500)

    else:
        return JsonResponse({"error": "Method not allowed"}, status=405)
    
def reset_password_with_token(request, token):
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            token = data.get("token")
            new_password = data.get("new_password")

            if not token or not new_password:
                return JsonResponse({"error": "Token and new password are required"}, status=400)

            try:
                reset_obj = UserForgotPassword.objects.get(token=token, is_used=False)
            except UserForgotPassword.DoesNotExist:
                return JsonResponse({"error": "Invalid or used token"}, status=404)

            if reset_obj.is_expired():
                return JsonResponse({"error": "Token expired"}, status=400)

            user = reset_obj.user
            user.password = make_password(new_password)
            user.save()

            reset_obj.is_used = True
            reset_obj.save()

            return JsonResponse({"success": "Password has been reset successfully"}, status=200)

        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON"}, status=400)

        except Exception as e:
            return JsonResponse({"error": "Internal server error"}, status=500)
    elif request.method == "GET":
        return render (request, "changepassword.html")
    else:
        return JsonResponse({"error": "Method not allowed"}, status=400)

def login_user(request):
    if request.method == "POST":
        try:
            data = request.POST.dict()
            email = data.get("email")
            password = data.get("password")

            if not email or not password:
                return JsonResponse({"error": "Email and password are required"}, status=400)

            user = authenticate(request, username=email, password=password)
            if user:
                login(request, user)
                return redirect("/")
            
            return JsonResponse({"error": "Invalid credentials"}, status=400)

        except Exception as e:
            logger.error(f"Login error: {str(e)}", exc_info=True)
            return JsonResponse({"error": "Internal Server Error"}, status=500)

    return render(request, "login.html")

def signup(request, token):
    if request.method == "POST":
        try:
            data = json.loads(request.body)

            required_fields = ["firstname", "lastname", "username", "password", "designation", "token"]
            missing_fields = [field for field in required_fields if not data.get(field)]
            if missing_fields:
                return JsonResponse({"error": f"Missing fields: {', '.join(missing_fields)}"}, status=400)

            first_name = data["firstname"]
            last_name = data["lastname"]
            username = data["username"]
            password = data["password"]
            designation = data["designation"]
            token = data["token"]

            user = NewUser.objects.filter(token=token).first()
            if not user:
                return JsonResponse({"error": "Invalid token"}, status=400)

            email = user.email
            role = extract_role(email)

            if role == "Student":
                designation = "NA"
                rollno = extract_rollno(email)
                batch = extract_batch(email, rollno)
            else:
                if designation not in ["Professor", "Assistant Professor"]: 
                    return JsonResponse({"error": "Invalid designation"}, status=400)
                rollno = None
                batch = None

            User = get_user_model()

            new_user = User.objects.create_user(
                first_name=first_name,
                last_name=last_name,
                username=username,
                email=email,
                password=password,
                roll_no=rollno,
                role=role,
                batch=batch,
                designation=designation
            )

            user.delete()  # Remove temporary user entry

            authenticated_user = authenticate(request, username=email, password=password)
            if authenticated_user:
                login(request, authenticated_user)
                return JsonResponse({"message": "success"}, status=200)

            return JsonResponse({"error": "Authentication failed after signup"}, status=400)

        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON data"}, status=400)
        except Exception as e:
            logger.error(f"Signup error: {str(e)}", exc_info=True)
            return JsonResponse({"error": "Internal Server Error"}, status=500)

    elif request.method == "GET":
        email = NewUser.objects.get(token=token).email
        designations = []
        role = extract_role(email)
        if role == "Student":
            designations = ["Student"]
        else:
            designations = ["Assistant Professor", "Professor"]
        return render(request, "signup.html", {"designations": designations})

def get_csrf_token(request):
    return JsonResponse({"csrfToken": get_token(request)})
@login_required
def logout_user(request):
    logout(request)
    return redirect("/")

@login_required
def profile(request, id):
    try:
        user = User.objects.get(id=id)
    except ObjectDoesNotExist:
        return JsonResponse({"error": "User not found"}, status=404)
    except Exception as e:
        logger.error(f"Error fetching user: {str(e)}", exc_info=True)
        return JsonResponse({"error": "Internal Server Error"}, status=500)

    if request.method == "GET":
        display_edit_button = request.user.id == id
        userdisplay = user_display(request)
        return render(request, "profile.html", {"userdisplay": userdisplay, "display_edit_button": display_edit_button})

    try:
        if user.role == "Student":
            data = {
                "name": f"{user.first_name} {user.last_name}",
                "department": user.department,
                "batch": user.batch,
                "roll_no": user.roll_no,
                "email": user.email,
                "skills": list(Skill.objects.filter(user=user).values("id", "name")),
                "interests": list(Interest.objects.filter(user=user).values("id", "name")),
                "personal_projects": list(PersonalProject.objects.filter(user=user).values("id", "title", "description", "link")),
                "social_links": list(SocialLink.objects.filter(user=user).values("id", "platform", "url")),
                "academic_projects": [
                    {
                        "id": projectobj.project.id,
                        "title": projectobj.project.title,
                        "course_name": projectobj.project.course.name,
                        "course_id": projectobj.project.course.code,
                        "guide_required": projectobj.project.course.requires_guide,
                        "guide": projectobj.project.guide.username if projectobj.project.guide else None,
                        "guide_id": projectobj.project.guide.id if projectobj.project.guide else None,
                    }
                    for projectobj in ProjectStudent.objects.filter(student=user)
                ],
            }
        else:
            data = {
                "name": f"{user.first_name} {user.last_name}",
                "department": user.department,
                "email": user.email,
                "skills": list(Skill.objects.filter(user=user).values("id", "name")),
                "interests": list(Interest.objects.filter(user=user).values("id", "name")),
                "personal_projects": list(PersonalProject.objects.filter(user=user).values("id", "title", "description", "link")),
                "social_links": list(SocialLink.objects.filter(user=user).values("id", "platform", "url")),
                "academic_projects": [
                    {
                        "id": project.id,
                        "title": project.title,
                        "course_name": project.course.name,
                        "course_id": project.course.code,
                        "guide_required": project.course.requires_guide,
                        "guide": project.guide.username if project.guide else None,
                        "guide_id": project.guide.id if project.guide else None,
                    }
                    for project in Project.objects.filter(guide=user)
                ],
            }

        return JsonResponse(data, safe=False, status=200)

    except Exception as e:
        logger.error(f"Error fetching user profile: {str(e)}", exc_info=True)
        return JsonResponse({"error": "Internal Server Error"}, status=500)

def get_job_posts(request, page_number):
    if request.method == "GET":
        try:
            post_per_call = 2
            start_index = (page_number - 1) * post_per_call  # Adjust for 0-based index
            end_index = start_index + post_per_call

            job_posts = JobPost.objects.all().order_by('-created_at')[start_index:end_index]  # Use slicing for pagination

            if not job_posts:
                return JsonResponse({"message": "No job posts available"}, status=200)

            data = [
                {
                    "author": job_post.author.username,
                    "company": job_post.company,
                    "jobrole": job_post.jobrole,
                    "content": job_post.content,
                    "created_at": job_post.created_at.strftime("%Y-%m-%d"),
                    "link": job_post.link
                }
                for job_post in job_posts
            ]

            return JsonResponse(data, safe=False, status=200)

        except EmptyPage:
            return JsonResponse({"error": "Page number out of range"}, status=200)
        except Exception as e:
            logger.error(f"Error fetching job posts: {str(e)}", exc_info=True)
            return JsonResponse({"error": "Internal Server Error"}, status=500)
        
@login_required
def create_job_post(request):
    if request.method == "GET":
        display_edit_button = request.user.id == id
        userdisplay = user_display(request)
        return render(request, "createjobpost.html", {"userdisplay": userdisplay, "display_edit_button": display_edit_button})
    if request.method == "POST":
        try:
            
            data = json.loads(request.body)
            company = data.get("company")
            jobrole = data.get("jobrole")
            content = data.get("content")
            link = data.get("link")


            if not company or not jobrole or not content or link:
                return JsonResponse({"error": "Missing required fields"}, status=400)

            job_post = JobPost(
                author=request.user,
                company=company,
                jobrole=jobrole,
                content=content,
                link=link
            )
            job_post.save()

            return JsonResponse({"success": "Job post created successfully"}, status=201)

        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON data"}, status=400)
        except Exception as e:
            logger.error(f"Error creating job post: {str(e)}", exc_info=True)
            return JsonResponse({"error": "Internal Server Error"}, status=500)

    return JsonResponse({"error": "Invalid request method"}, status=405)

@login_required
def jobs_api(request):
    if request.method == 'GET':
        try:
            userdisplay = user_display(request)
            return render(request, 'jobs.html', {"userdisplay": userdisplay})
        except Exception as e:
            logger.error(f"Error in GET /jobs_api: {str(e)}", exc_info=True)
            return JsonResponse({"error": "Internal Server Error"}, status=500)

    if request.method == 'POST':
        try:
            jobs_data = fetch_adzuna_jobs()

            if not jobs_data or 'results' not in jobs_data:
                return JsonResponse([], safe=False, status=200)

            formatted_jobs = [
                {
                    'id': job.get('id'),
                    'title': job.get('title'),
                    'company': job.get('company', {}).get('display_name', 'Unknown'),
                    'location': job.get('location', {}).get('display_name', 'Unknown'),
                    'description': job.get('description', 'No description available'),
                    'salary': job.get('salary_min', 'Not specified'),
                    'url': job.get('redirect_url', '#'),
                    'posted_date': job.get('created', 'Unknown')
                }
                for job in jobs_data.get('results', [])
            ]

            return JsonResponse(formatted_jobs, safe=False, status=200)

        except Exception as e:
            logger.error(f"Error in POST /jobs_api: {str(e)}", exc_info=True)
            return JsonResponse({"error": "Internal Server Error"}, status=500)

    return JsonResponse({"error": "Invalid request method"}, status=405)
      
def search(request):
    if request.method == "GET":
        try:
            query = request.GET.get("q", "").strip()  # Ensure query is not None
            
            if not query:  
                return JsonResponse({"error": "Query parameter 'q' is required"}, status=400)

            users = User.objects.filter(
                Q(username__icontains=query) | 
                Q(first_name__icontains=query) | 
                Q(last_name__icontains=query)
            )

            data = [
                {
                    "id": user.id,
                    "name": user.username,
                    "role": user.role,
                    "email": user.email,
                    "batch": user.batch,
                }
                for user in users
            ]

            return JsonResponse(data, safe=False, status=200)

        except Exception as e:
            logger.error(f"Error in search function: {str(e)}", exc_info=True)
            return JsonResponse({"error": "Internal Server Error"}, status=500)

    return JsonResponse({"error": "Invalid request method"}, status=405)
    
def news(request):
    data = [
        {
            "title" : "MVSR Connect is now live",
            "content" : "MVSR Connect is now live. You can now find jobs and projects on the platform.",
            "created_at" : "2024-01-01"
        },
        {
            "title" : "MVSR Connect is now live",
            "content" : "MVSR Connect is now live. You can now find jobs and projects on the platform.",
            "created_at" : "2024-01-01"
        },
        {
            "title" : "MVSR Connect is now live",
            "content" : "MVSR Connect is now live. You can now find jobs and projects on the platform.",
            "created_at" : "2024-01-01"
        }
    ]
    return JsonResponse(data, safe=False, status=200)

def valid_profile_info(data):
    skills = data.get("skills", [])  # List of dicts [{'name': 'Python'}, {'name': 'ML'}]
    interests = data.get("interests", [])  # List of dicts [{'name': 'AI & ML'}, {'name': 'Open Source'}]

    # Extract only skill names from dictionaries
    skill_names = {s.get("name") for s in skills}
    interest_names = {i.get("name") for i in interests}

    # Use predefined skill and interest choices instead of DB queries
    valid_skills = {s[0] for s in Skill.SKILL_CHOICES}  # Extract valid skill names
    valid_interests = {i[0] for i in Interest.INTEREST_CHOICES}  # Extract valid interest names

    # Check if all given skills and interests exist in predefined lists
    if not skill_names.issubset(valid_skills):
        return False

    if not interest_names.issubset(valid_interests):
        return False

    return True
@login_required
def edit_profile(request):
    if request.method == "GET":
        return render(request, "editprofile.html")

    if request.method == "POST":
        try:
            data = json.loads(request.body)
            user_id = data.get("id")

            current_user = request.user
            if current_user.id != user_id:
                return JsonResponse({"error": "You are not authorized to edit this profile"}, status=403)

            user = current_user

            if not valid_profile_info(data):
                return JsonResponse({"error": "Enter valid details"}, status=400)

            # Delete old entries
            Skill.objects.filter(user=user).delete()
            Interest.objects.filter(user=user).delete()
            SocialLink.objects.filter(user=user).delete()
            PersonalProject.objects.filter(user=user).delete()

            skills = data.get("skills", [])
            interests = data.get("interests", [])
            social_links = data.get("social_links", [])
            personal_projects = data.get("personal_projects", [])

            # Add new data
            Skill.objects.bulk_create([Skill(user=user, name=skill["name"]) for skill in skills])
            Interest.objects.bulk_create([Interest(user=user, name=interest["name"]) for interest in interests])
            SocialLink.objects.bulk_create([
                SocialLink(user=user, platform=link["platform"], url=link["url"])
                for link in social_links if link["platform"] in PLATFORMS
            ])
            PersonalProject.objects.bulk_create([
                PersonalProject(user=user, title=project["title"], description=project["description"], link=project["link"])
                for project in personal_projects
            ])

            return JsonResponse({"success": "Profile updated successfully"}, status=200)

        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON data"}, status=400)

        except Exception as e:
            logger.error(f"Error editing profile: {str(e)}", exc_info=True)
            return JsonResponse({"error": "Internal Server Error"}, status=500)

def skills_api(request, query=None):
    if request.method == "GET":
        try:
            all_skills = [skill[0] for skill in Skill.SKILL_CHOICES]  # Extract skill names
            if query:
                filtered_skills = [skill for skill in all_skills if query.lower() in skill.lower()]
            else:
                filtered_skills = all_skills  # Return all skills if no query is provided

            return JsonResponse({"data": filtered_skills}, status=200)

        except Exception as e:
            return JsonResponse({"error": "Internal Server Error"}, status=500)

    return JsonResponse({"error": "Invalid request method"}, status=405)

def interest_api(request, query=None):
    if request.method == "GET":
        try:
            all_interests = [interest[0] for interest in Interest.INTEREST_CHOICES]  # Extract interest names
            if query:
                filtered_interests = [interest for interest in all_interests if query.lower() in interest.lower()]
            else:
                filtered_interests = all_interests  # Return all interests if no query is provided

            return JsonResponse({"data": filtered_interests}, status=200)

        except Exception as e:
            return JsonResponse({"error": "Internal Server Error"}, status=500)

    return JsonResponse({"error": "Invalid request method"}, status=405)
    




        
