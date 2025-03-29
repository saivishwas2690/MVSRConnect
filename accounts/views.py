from django.http import JsonResponse
from django.contrib.auth import authenticate, login, logout
from django.views.decorators.csrf import csrf_protect, csrf_exempt
from django.middleware.csrf import get_token
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.contrib.auth import get_user_model
import json, re
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from .models import *
import secrets
from django.http import HttpResponse
from django.core.mail import send_mail
from django.conf import settings
from .utils import fetch_adzuna_jobs, validate_email, extract_rollno, extract_batch, extract_role
from rest_framework.response import Response
from projects_app.models import *
from django.db.models import Q
import logging

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

            # Validate email
            try:
                validate_email(email)
            except ValidationError:
                return JsonResponse({"error": "Email is not valid"}, status=400)

            # Check if email already exists
            if NewUser.objects.filter(email=email).exists():
                return JsonResponse({"error": "Email verification mail has been sent already"}, status=400)

            # Generate a secure token
            token = secrets.token_hex(16)
            verification_link = f"http://127.0.0.1:8000/verify/{token}"
            print(verification_link)

            # Send email
            subject = "MVSRConnect Email Verification"
            try:
                send_mail(subject, verification_link, settings.EMAIL_HOST_USER, [email])
            except Exception as e:
                logger.error(f"Failed to send email: {str(e)}", exc_info=True)
                return JsonResponse({"error": "Failed to send email"}, status=500)

            # Create user with token
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
                if designation not in ["Professor", "Asst. Professor"]: 
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
        return render(request, "signup.html")

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

            job_posts = JobPost.objects.all()[start_index:end_index]  # Use slicing for pagination

            if not job_posts:
                return JsonResponse({"message": "No job posts available"}, status=404)

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
            return JsonResponse({"error": "Page number out of range"}, status=404)
        except Exception as e:
            logger.error(f"Error fetching job posts: {str(e)}", exc_info=True)
            return JsonResponse({"error": "Internal Server Error"}, status=500)
        
@login_required
def create_job_post(request):
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            company = data.get("company")
            jobrole = data.get("jobrole")
            content = data.get("content")
            link = data.get("link")

            if not company or not jobrole or not content:
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
    skill_names = [s.get("name") for s in skills]
    interest_names = [i.get("name") for i in interests]

    # Fetch existing skill and interest names from DB
    existing_skills = set(Skill.objects.filter(name__in=skill_names).values_list("name", flat=True))
    existing_interests = set(Interest.objects.filter(name__in=interest_names).values_list("name", flat=True))

    # Check if all given skills and interests exist in DB
    if not all(s in existing_skills for s in skill_names):
        return False 

    if not all(i in existing_interests for i in interest_names):
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
            if query:
                skills = Skill.objects.filter(name__icontains=query).values_list("name", flat=True).distinct()
            else:
                skills = Skill.objects.values_list("name", flat=True).distinct()

            return JsonResponse({"data": list(skills)}, status=200)

        except Exception as e:
            logger.error(f"Error fetching skills: {str(e)}", exc_info=True)
            return JsonResponse({"error": "Internal Server Error"}, status=500)

    return JsonResponse({"error": "Invalid request method"}, status=405)

def interest_api(request, query=None):
    if request.method == "GET":
        if not query:  # If query is empty, return all interests
            interests = Interest.objects.values_list('name', flat=True).distinct()
        else:  # Otherwise, filter interests based on the query
            interests = Interest.objects.filter(name__icontains=query).values_list('name', flat=True).distinct()

        return JsonResponse({"data": list(interests)}, status=200)
    
def interest_api(request, query=None):
    if request.method == "GET":
        try:
            if query:
                interests = Interest.objects.filter(name__icontains=query).values_list("name", flat=True).distinct()
            else:
                interests = Interest.objects.values_list("name", flat=True).distinct()

            return JsonResponse({"data": list(interests)}, status=200)

        except Exception as e:
            logger.error(f"Error fetching interests: {str(e)}", exc_info=True)
            return JsonResponse({"error": "Internal Server Error"}, status=500)

    return JsonResponse({"error": "Invalid request method"}, status=405)




        
