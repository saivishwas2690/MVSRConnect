from django.shortcuts import render
from django.http import JsonResponse, HttpResponse
from django.contrib.auth.decorators import login_required
from django.core.files.base import ContentFile
from django.conf import settings
from django.shortcuts import render, get_object_or_404

from .models import Course, Project, ProjectStudent, CourseOutcome, ProjectCOs
from accounts.models import User, Batch
from .utils import extract_batch

import json
import os
import io
import re
import zipfile
import tempfile
import base64
import logging

import cloudinary
import cloudinary.uploader
from cloudinary.utils import cloudinary_url

import openpyxl
from openpyxl import Workbook

import google.generativeai as genai  # Assuming you're using this

from dotenv import load_dotenv  


load_dotenv()

logger = logging.getLogger(__name__)

cloudinary.config(
    cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME"),
    api_key=os.getenv("CLOUDINARY_API_KEY"),
    api_secret=os.getenv("CLOUDINARY_API_SECRET"),
    secure=True
)


genai.configure(api_key=os.getenv("GENAI_API_KEY"))


def find_section(data, roll_number):
    try:
        roll_number = int(roll_number.strip()) 
        for section, details in data.items():
            for r in details["range"]:
                start, end = map(int, r.split(" - "))  
                if start <= roll_number <= end:
                    return details["Name"]  
        return "Not Found" 
    except ValueError:
        return "Invalid Roll Number" 
    
@login_required
def create_course(request):
    if request.method == "GET":
        if request.user.role == "Incharge":
            return render(request, "createcourse.html", {"userdisplay": request.user.username})
        return JsonResponse({"error": "You are not authorized to create a course"}, status=403)
        
    if request.method == "POST":
        if request.user.role != "Incharge":
            return JsonResponse({"error": "You are not authorized to create a course"}, status=403)

        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON format"}, status=400)

        # Extract and validate data
        course_name = data.get("course_name", "").strip()
        course_code = data.get("code", "").strip()
        batch = data.get("batch")
        requires_guide = data.get("requires_guide", False)
        requires_internship = data.get("requires_internship", False)
        limit_per_prof = data.get("limit_per_prof", 0)
        limit_per_asst_prof = data.get("limit_per_asst_prof", 0)
        domain_requirement = data.get("domain_requirement", False)
        domains = data.get("domains", [])
        rubrics = data.get("rubrics", [])

        # Basic validations
        if not course_name or not course_code:
            return JsonResponse({"error": "Course name and code are required"}, status=400)
        
        if not isinstance(batch, int) or batch <= 0:
            return JsonResponse({"error": "Invalid batch year"}, status=400)
        
        if domain_requirement and not domains:
            return JsonResponse({"error": "Domains are required for this course"}, status=400)
        
        if not rubrics:
            return JsonResponse({"error": "Rubrics are required for a course"}, status=400)

        # Check for duplicate course codes
        if Course.objects.filter(code=course_code).exists():
            return JsonResponse({"error": "Course with this code already exists"}, status=409)

        # Assign rubric IDs
        for i, rubric in enumerate(rubrics, start=1):
            if not isinstance(rubric, dict) or "name" not in rubric or "total_marks" not in rubric:
                return JsonResponse({"error": "Invalid rubric format"}, status=400)
            rubric["id"] = i  

        # Create course (keeping model unchanged)
        course = Course.objects.create(
            name=course_name,
            code=course_code,
            Batch=batch,  # Kept unchanged as per your model
            requires_guide=requires_guide,
            requires_internship=requires_internship,
            limit_per_prof=limit_per_prof,
            limit_per_asst_prof=limit_per_asst_prof,
            domain_requirement=domain_requirement,
            rubrics=rubrics,
            domains=domains
        )

        return JsonResponse({"message": "Course created successfully", "course_id": course.id}, status=201)

def generate_project_marks(student_ids, rubrics):
    """
    Generates a project marks structure where all marks are initially set to zero.

    :param student_ids: List of student IDs
    :param rubrics: List of rubric dictionaries containing 'id'
    :return: List of dictionaries containing student IDs and their marks initialized to zero
    """
    project_marks = []

    for student_id in student_ids:
        marks_dict = {str(rubric["id"]): 0 for rubric in rubrics}  # Initialize all rubric marks to 0
        project_marks.append({"id": student_id, "marks": marks_dict})

    return project_marks

@login_required
def create_project(request):
    if request.method == "GET":
        if request.user.role != "Student":
            return JsonResponse({"error": "You are not authorized to create a project"}, status=403)
        return render(request, "createproject.html", {"userdisplay": request.user.roll_no})

    elif request.method == "POST":
        if request.user.role != "Student":
            return JsonResponse({"error": "You are not authorized to create a project"}, status=403)

        data = json.loads(request.body)
        project_name = data.get("project_name")
        project_description = data.get("project_description")
        course_id = data.get("course_id")
        domain = data.get("domain")
        students = data.get("students")

        try:
            course = Course.objects.get(id=course_id)
        except Course.DoesNotExist:
            return JsonResponse({"error": "Course does not exist"}, status=400)

        if course.domain_requirement and not domain:
            return JsonResponse({"error": "Domain is required for this course"}, status=400)
        
        if course.domain_requirement and domain not in course.domains:
            return JsonResponse({"error": "Invalid domain"}, status=400)

        # Validate batch and section
        batches = {extract_batch(student["roll"]) for student in students}
        if len(batches) > 1:
            return JsonResponse({"error": "All students must be from the same batch"}, status=400)

        batch_no = batches.pop()
        try:
            batch_sections = Batch.objects.get(batch=batch_no).section_data
        except Batch.DoesNotExist:
            return JsonResponse({"error": f"Batch {batch_no} does not exist"}, status=400)

        # Validate students
        user_in_team = False
        sections = set()

        for student in students:
            roll_no = student.get("roll")
            internship = student.get("internship")

            student_obj = User.objects.filter(roll_no=roll_no).first()
            if not student_obj:
                return JsonResponse({"error": f"Student with roll number {roll_no} does not exist"}, status=400)

            if ProjectStudent.objects.filter(student__roll_no=roll_no, project__course=course).exists():
                return JsonResponse({"error": f"Student {roll_no} is already registered for this course"}, status=400)

            if request.user.roll_no == roll_no:
                user_in_team = True

            section = find_section(batch_sections, roll_no[-3:])
            sections.add(section)

            if course.requires_internship and not internship:
                return JsonResponse({"error": "Internship details are required for this course"}, status=400)

        if len(sections) > 1:
            return JsonResponse({"error": "All students must be from the same section"}, status=400)

        if not user_in_team:
            return JsonResponse({"error": "Please add yourself to the project team"}, status=400)

        section = sections.pop()

        # Generate project nickname
        existing_nicknames = Project.objects.filter(course=course, nick_name__startswith=section).values_list("nick_name", flat=True)
        project_numbers = [int(nick[1:]) for nick in existing_nicknames if nick[1:].isdigit()]
        next_number = max(project_numbers, default=0) + 1

        # Create project
        project = Project.objects.create(
            title=project_name,
            description=project_description,
            course=course,
            guide=None,
            domain=domain,
            nick_name=f"{section}{next_number}"
        )

        # Add students to project
        student_ids = []
        for student in students:
            student_obj = User.objects.get(roll_no=student["roll"])
            student_ids.append(student_obj.id)
            ProjectStudent.objects.create(
                project=project,
                student=student_obj,
                internship_name=student.get("internship")
            )

        # Generate and save marks
        project.marks = generate_project_marks(student_ids, course.rubrics)
        project.save()

        return JsonResponse({"message": "Project created successfully", "id": project.id}, status=201)

@login_required
def fetch_courses(request):
    if request.method == "POST":
        batch = request.user.batch
        courses = Course.objects.filter(Batch=batch)
        data = []
        for course in courses:
            data.append({
                "course_id": course.id,
                "name": course.name,
                "code": course.code,
                "requires_guide": course.requires_guide,
                "requires_internship": course.requires_internship,
                "limit_per_prof": course.limit_per_prof,
                "limit_per_asst_prof": course.limit_per_asst_prof,
                "domain_requirement": course.domain_requirement,
                "domains": course.domains
            })
        return JsonResponse({"courses": data}, status=200)

    else:
        return JsonResponse({"error": "Method not allowed"}, status=405)

@login_required
def view_projects(request):
    if request.method == "GET":
        userdisplay = request.user.username
        context = {
            "userdisplay": userdisplay
        }
        return render(request, "viewprojects.html", context)
    
@login_required
def get_projects(request):
    if request.method == "POST":
        data = json.loads(request.body)
        batch = data.get("batch")
        section = data.get("section")
        course_id = data.get("course_id")
        projects = Project.objects.filter(course_id=course_id, nick_name__startswith=section)
        project_data = []
        for project in projects:
            project_data.append({
                "title": project.title,
                "guide": project.guide.username if project.guide else None,
                "domain": project.domain,
                "nick_name": project.nick_name,
                "id": project.id
            })

        return JsonResponse({"projects": project_data}, status=200)
    else:
        return JsonResponse({"error": "Method not allowed"}, status=405)

@login_required
def fetch_batches(request):
    if request.method == "POST":
        all_batches = Batch.objects.all()
        batch_data = []
        for batch in all_batches:
            batch_data.append(batch.batch)

            sections = []
            for section in batch.section_data:
                details = batch.section_data[section]
                sections.append(details["Name"])
            all_courses = Course.objects.filter(Batch=batch.batch)
            courses = []
            for course in all_courses:
                courses.append({
                    "name": course.name,
                    "code": course.code,
                    "id": course.id
                })
            batch_data.append({
                "batch": batch.batch,
                "sections": sections,
                "courses": courses
            })
        context = {"batches": batch_data}
            
        return JsonResponse(context, status=200)
    else:
        return JsonResponse({"error": "Method not allowed"}, status=405)

@login_required
def project_detail(request, id):
    if request.method == "GET":
        try:
            project = get_object_or_404(Project, id=id)
            students = ProjectStudent.objects.filter(project=project)
            data = []
            username = ""
            if request.user.role == "Student":
                userdisplay = request.user.roll_no
            else:
                userdisplay = request.user.username
            for student in students:
                data.append({
                    "name": student.student.username,
                    "roll": student.student.roll_no,
                    "id": student.student.id,
                    "internship": student.internship_name
                })

            context = {
                "userdisplay": userdisplay,
                # "project_title": project.title,
                # "project_description": project.description,
                # "project_members": data,
                # "project_domain": project.domain,
                # "project_nick_name": project.nick_name,
                # "project_id": project.id,
                # "project_guide": project.guide.username if project.guide else None,
                # "project_report": project.report,
                # "project_abstract": project.abstract,
                # "project_guide_id": project.guide.id if project.guide else None

            }
            return render(request, "project.html", context)
        except Exception as e:
            logger.error(f"Error fetching project details: {e}")
            return JsonResponse({"error": "An error occurred while fetching project details."}, status=500)

    elif request.method == "POST":
        try:
            project = get_object_or_404(Project, id=id)
            course = Course.objects.get(id=project.course.id)
            current_user = request.user 
            show_be_guide_button = False
            if current_user.role == "Teacher" and course.requires_guide == True and project.guide == None:
                limit_asst = course.limit_per_asst_prof
                limit_prof = course.limit_per_prof 
                count = Project.objects.filter(course=course, guide=current_user).count()

                user_limit = limit_prof if current_user.designation == "Professor" else limit_asst
                if count < user_limit:
                    show_be_guide_button = True 

            data = {}
            data["show_be_guide_button"] = show_be_guide_button
            data["id"] = project.id
            data["title"] = project.title
            data["description"] = project.description
            data["domain"] = project.domain
            data["nick_name"] = project.nick_name
            data["guide"] = project.guide.username if project.guide else None
            data["course"] = {"id": course.id, 
                              "name": course.name, 
                              "code": course.code, 
                              }
            team_members_data = []
            students = ProjectStudent.objects.filter(project=project)
            for student in students:
                team_members_data.append({
                    "id": student.student.id,
                    "name": student.student.username,
                    "roll_no": student.student.roll_no,
                    "internship": student.internship_name
                })
            data["team_members"] = team_members_data

            data["guide"] = {
                "id": project.guide.id if project.guide else None,
                "name": project.guide.username if project.guide else None,
                "designation": project.guide.designation if project.guide else None
            }

            data["documents"] = {
                "abstract": project.abstract if project.abstract else None,
                "report": project.report if project.report else None,
                "guide_approval_form": project.guide_approval_form if project.guide_approval_form else None
            }

            data["show_evaluate"] = True if request.user.role == "Incharge" else False
            data["guide_required"] = project.course.requires_guide
            data["internship_required"] = project.course.requires_internship
            data["domain_required"] = project.course.domain_requirement
            data["domain"] = project.domain

            upload_documents = False
            for student in students:
                if student.student.id == request.user.id:
                    upload_documents = True


            data["show_upload_documents"] = upload_documents
            # data["status"] = "Evaluated" if project.is_evaluated else "Not Evaluated"

            return JsonResponse(data, status=200)
        except Exception as e:
            logger.error(f"Error fetching project details (FETCH request): {e}")
            return JsonResponse({"error": "An error occurred while fetching project data."}, status=500)

def search_team_members(request):
    if request.method == "POST":
        data = json.loads(request.body)
        query = data.get("search_query")
        course_id = data.get("course_id")

        course = Course.objects.get(id=int(course_id))
        if not course:
            return JsonResponse({"error": "Course not found"}, status=404)
        
        students = User.objects.filter(roll_no__icontains=query)
        print(students)

        data = []
        for student in students:
            is_eligible = not ProjectStudent.objects.filter(student=student, project__course=course).exists()
            data.append({
                "id" : student.id,
                "name" : student.username,
                "roll_no" : student.roll_no,
                "is_eligible" : is_eligible,
            })
        return JsonResponse(data, safe=False, status=200)
    
@login_required
def available_guides(request):
    try:
        if request.method == "POST":
            try:
                data = json.loads(request.body)
                course_id = data.get("course_id")

                course = Course.objects.get(id=int(course_id))
                if not course:
                    return JsonResponse({"error": "Course not found"}, status=404)

                if not course.requires_guide:
                    return JsonResponse({"error": "Course does not require a guide"}, status=400)

                limit_prof = course.limit_per_prof
                limit_asst_prof = course.limit_per_asst_prof

                faculty_users = User.objects.filter(designation__in=["Professor", "Asst. Professor"])

                response_data = []
                for faculty_user in faculty_users:
                    try:
                        availability_status = "Available"
                        limit = limit_prof if faculty_user.designation == "Professor" else limit_asst_prof
                        count_of_current_projects = Project.objects.filter(guide=faculty_user, course=course).count()

                        if count_of_current_projects < limit and count_of_current_projects > 0:
                            availability_status = "Limited"
                        elif count_of_current_projects == limit:
                            availability_status = "Full"

                        response_data.append({
                            "id": faculty_user.id,
                            "name": faculty_user.username,
                            "availability_status": availability_status,
                            "max_projects": limit,
                            "current_projects": count_of_current_projects,
                        })
                    except Exception as faculty_error:
                        logger.error(f"Error processing faculty {faculty_user.id}: {faculty_error}")

                return JsonResponse(response_data, safe=False, status=200)

            except Course.DoesNotExist:
                logger.error(f"Course with ID {course_id} not found.")
                return JsonResponse({"error": "Course not found"}, status=404)

            except json.JSONDecodeError:
                logger.error("Invalid JSON received in request body.")
                return JsonResponse({"error": "Invalid JSON format"}, status=400)

            except Exception as e:
                logger.error(f"Unexpected error in available_guides: {e}")
                return JsonResponse({"error": "An unexpected error occurred"}, status=500)

    except Exception as e:
        logger.error(f"Critical error in available_guides: {e}")
        return JsonResponse({"error": "Something went wrong", "details": str(e)}, status=500)

@login_required
def upload_document(request):
    if request.method == "POST":
        if request.user.role != "Student":
            return JsonResponse({"error": "You are not authorized to upload a document"}, status=403)
        
        try:
            data = json.loads(request.body)
            project_id = data.get("project_id")
            document_type = data.get("document_type")
            base64_file = data.get("document")  # This is the base64 string

            if not all([project_id, document_type, base64_file]):
                return JsonResponse({"error": "Missing required fields"}, status=400)

            if document_type not in ["abstract", "report", "guide_approval_form"]:
                return JsonResponse({"error": "Invalid document type"}, status=400)
            # Convert base64 to file object
            try:
                project = Project.objects.get(id=project_id)
                if document_type == "abstract":
                    if project.abstract is not None:
                        return JsonResponse({"error": "You have already uploaded abstract"}, status=400)
                if document_type == "guide_approval_form":
                    if project.guide_approval_form is not None:
                        return JsonResponse({"error": "You have already uploaded guide approval form"}, status=400)
                if document_type == "report":
                    if project.report is not None:
                        return JsonResponse({"error": "You have already uploaded report"}, status=400)
                
                # Update project with the new file URL
                if document_type == "guide_approval_form" and project.course.requires_guide == False:
                    return JsonResponse({"error": "The course does not require a Guide"}, status=400)
                
                # Verify that the user is part of the project team
                if not ProjectStudent.objects.filter(project=project, student=request.user).exists():
                    return JsonResponse({"error": "You are not authorized to upload documents for this project"}, status=403)
                    
                # Create a temporary file name
                file_name = f"{project_id}_{document_type}_{request.user.id}" + ".pdf"
                # Upload to Cloudinary
                response = cloudinary.uploader.upload(
                    f"data:application/pdf;base64,{base64_file}",
                    resource_type="raw",
                    public_id=file_name.split('.')[0],
                    format="pdf"
                )

                # Get the secure URL from Cloudinary
                file_url = response.get('secure_url')

                if not file_url:
                    raise Exception("Failed to get URL from Cloudinary")


                # Update the appropriate field
                if document_type == "abstract":
                    project.abstract = file_url
                    project.save()
                elif document_type == "guide_approval_form":
                    project.guide_approval_form = file_url
                    project.save()
                else:
                    project.report = file_url
                    project.save()
                

                return JsonResponse({
                    "success": True,
                    "message": "Document uploaded successfully",
                    "file_url": file_url
                })

            except Project.DoesNotExist:
                return JsonResponse({"error": "Project not found"}, status=404)
            except Exception as e:
                return JsonResponse({"error": f"Failed to upload document: {str(e)}"}, status=500)

        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON data"}, status=400)
        except Exception as e:
            return JsonResponse({"error": "An unexpected error occurred"}, status=500)

    return JsonResponse({"error": "Method not allowed"}, status=405)

@login_required
def evaluate(request, id):
    try:
        if request.method == "POST":
            try:
                if request.user.role != "Incharge":
                    return JsonResponse({"error": "You can not view this page"}, status=403)

                current_project = Project.objects.get(id=id)
                current_course = current_project.course

                rubrics = current_course.rubrics
                rubrics_json = {r["name"]: r for r in rubrics}

                data = {
                    "title": current_project.title,
                    "batch_name": current_project.nick_name,
                    "course_name": current_course.name,
                    "course_id": current_course.id,
                    "rubrics": rubrics
                }

                project_marks = current_project.marks
                students = []

                for s in project_marks:
                    try:
                        student_id = s["id"]
                        student_obj = User.objects.get(id=student_id)
                        students.append({
                            "id": student_id,
                            "name": student_obj.username,
                            "roll_no": student_obj.roll_no,
                            "marks": s["marks"]
                        })
                    except User.DoesNotExist:
                        logger.error(f"Student with ID {student_id} not found.")
                    except KeyError as key_err:
                        logger.error(f"Missing key in project marks: {key_err}")

                data["students"] = students
                return JsonResponse(data, status=200)

            except Project.DoesNotExist:
                logger.error(f"Project with ID {id} not found.")
                return JsonResponse({"error": "Project not found"}, status=404)

            except Exception as e:
                logger.error(f"Unexpected error in evaluate (FETCH): {e}")
                return JsonResponse({"error": "An unexpected error occurred"}, status=500)

        elif request.method == "GET":
            try:
                userdisplay = request.user.username
                context = {"userdisplay": userdisplay}
                return render(request, "evaluate.html", context)
            except Exception as e:
                logger.error(f"Error rendering evaluate.html: {e}")
                return JsonResponse({"error": "Error loading page"}, status=500)

        else:
            return JsonResponse({"error": "Method not allowed"}, status=400)

    except Exception as e:
        logger.error(f"Critical error in evaluate function: {e}")
        return JsonResponse({"error": "Something went wrong", "details": str(e)}, status=500)

@login_required
def save_marks(request, id):
    try:
        if request.method == "POST":
            try:
                if request.user.role != "Incharge":
                    return JsonResponse({"error": "You are not authorized to assign marks"}, status=400)

                data = json.loads(request.body)
                marks_data = data.get("marks", [])

                converted_data = [
                    {
                        "id": int(student["student_id"]),
                        "marks": {rubric["rubric_id"]: rubric["marks"] for rubric in student.get("rubrics", [])}
                    }
                    for student in marks_data
                ]

                try:
                    project = Project.objects.get(id=id)
                    project.marks = converted_data
                    project.save()
                    return JsonResponse({"message": "Marks saved successfully"}, status=200)

                except Project.DoesNotExist:
                    logger.error(f"Project with ID {id} not found.")
                    return JsonResponse({"error": "Project not found"}, status=404)

            except KeyError as key_err:
                logger.error(f"Missing key in request data: {key_err}")
                return JsonResponse({"error": f"Missing key: {key_err}"}, status=400)

            except json.JSONDecodeError:
                logger.error("Invalid JSON format in request body.")
                return JsonResponse({"error": "Invalid JSON format"}, status=400)

            except Exception as e:
                logger.error(f"Unexpected error in save_marks (POST): {e}")
                return JsonResponse({"error": "An unexpected error occurred"}, status=500)

        else:
            return JsonResponse({"error": "Method not allowed"}, status=400)

    except Exception as e:
        logger.error(f"Critical error in save_marks function: {e}")
        return JsonResponse({"error": "Something went wrong", "details": str(e)}, status=500)
    
@login_required
def assign_guide(request):
    try:
        if request.method == "POST":
            try:
                if request.user.role == "Student":
                    return JsonResponse({"error": "You cannot be a guide"}, status=400)

                current_user = request.user
                data = json.loads(request.body)
                project_id = data.get("project_id")

                try:
                    project = Project.objects.get(id=project_id)
                except Project.DoesNotExist:
                    logger.error(f"Project with ID {project_id} not found.")
                    return JsonResponse({"error": "Project not found"}, status=404)

                course = project.course
                limit_asst = course.limit_per_asst_prof
                limit_prof = course.limit_per_prof
                count = Project.objects.filter(course=course, guide=current_user).count()

                user_limit = limit_prof if current_user.designation == "Professor" else limit_asst

                if count < user_limit and project.guide is None:
                    project.guide = current_user
                    project.save()
                    return JsonResponse({"message": "You are assigned as guide to the Project"}, status=200)
                else:
                    return JsonResponse({"error": "Cannot assign guide"}, status=400)

            except KeyError as key_err:
                logger.error(f"Missing key in request data: {key_err}")
                return JsonResponse({"error": f"Missing key: {key_err}"}, status=400)

            except json.JSONDecodeError:
                logger.error("Invalid JSON format in request body.")
                return JsonResponse({"error": "Invalid JSON format"}, status=400)

            except Exception as e:
                logger.error(f"Unexpected error in assign_guide (POST): {e}")
                return JsonResponse({"error": "An unexpected error occurred"}, status=500)

        return JsonResponse({"error": "Method not allowed"}, status=400)

    except Exception as e:
        logger.error(f"Critical error in assign_guide function: {e}")
        return JsonResponse({"error": "Something went wrong", "details": str(e)}, status=500)

@login_required
def get_courses(request):
    try:
        if request.method == "GET":
            try:
                userdisplay = request.user.username
                context = {"userdisplay": userdisplay}

                if request.user.role == "Incharge":
                    return render(request, "viewcourses.html", context)
                else:
                    return JsonResponse({"error": "Cannot view this page"}, status=400)
            except Exception as e:
                logger.error(f"Error in get_courses (GET request): {e}")
                return JsonResponse({"error": "An unexpected error occurred"}, status=500)

        elif request.method == "POST":
            try:
                courses_data = []
                all_courses = Course.objects.all()

                for c in all_courses:
                    courses_data.append({
                        "title": c.name,
                        "batch": c.Batch,
                        "code": c.code,
                        "id": c.id,
                        "requires_guide": c.requires_guide,
                        "requires_internship": c.requires_internship,
                        "limit_for_asst_prof": c.limit_per_asst_prof,
                        "limit_for_prof": c.limit_per_prof,
                        "rubrics": c.rubrics,
                        "domains": c.domains,
                        "requires_domain": c.domain_requirement,
                        "course_creation_date": c.date
                    })

                return JsonResponse({"data": courses_data}, status=200)

            except Exception as e:
                logger.error(f"Error in get_courses (FETCH request): {e}")
                return JsonResponse({"error": "An unexpected error occurred"}, status=500)

        return JsonResponse({"error": "Method not allowed"}, status=400)

    except Exception as e:
        logger.error(f"Critical error in get_courses function: {e}")
        return JsonResponse({"error": "Something went wrong", "details": str(e)}, status=500)

@login_required
def view_course_dashboard(request, id):
    try:
        if request.method == "GET":
            try:
                userdisplay = request.user.username
                context = {"userdisplay": userdisplay}

                if request.user.role == "Incharge":
                    return render(request, "coursedashboard.html", context)
                else:
                    return JsonResponse({"error": "Cannot view this page"}, status=400)
            except Exception as e:
                logger.error(f"Error in view_course_dashboard (GET request) for course ID {id}: {e}")
                return JsonResponse({"error": "An unexpected error occurred"}, status=500)

        return JsonResponse({"error": "Method not allowed"}, status=400)

    except Exception as e:
        logger.error(f"Critical error in view_course_dashboard function: {e}")
        return JsonResponse({"error": "Something went wrong", "details": str(e)}, status=500)

@login_required
def course_dashboard(request):
    try:
        if request.method == "POST":
            try:
                data = json.loads(request.body)
                course_id = data.get("course_id")

                if not course_id:
                    return JsonResponse({"error": "Course ID is required"}, status=400)

                current_course = Course.objects.get(id=course_id)

                course_data = {}
                course_data["title"] = current_course.name
                course_data["batch"] = current_course.Batch
                course_data["code"] = current_course.code
                course_data["requires_guide"] = current_course.requires_guide
                course_data["requires_internship"] = current_course.requires_internship
                course_data["limit_for_asst_prof"] = current_course.limit_per_asst_prof
                course_data["limit_for prof"] = current_course.limit_per_prof
                course_data["rubrics"] = current_course.rubrics
                course_data["domains"] = current_course.domains
                course_data["requires_domain"] = current_course.domain_requirement
                course_data["course_creation_date"] = current_course.date

                all_projects = Project.objects.filter(course_id=course_id)

                course_data["Projects"] = []
                for p in all_projects:
                    section = p.nick_name[0] if p.nick_name else "N/A"
                    course_data["Projects"].append({
                        "project_id": p.id,
                        "project_domain": p.domain if current_course.domain_requirement else None,
                        "Projects_title": p.title,
                        "Project_section": section,
                        "Project_nickname": p.nick_name
                    })

                return JsonResponse(course_data, status=200)

            except json.JSONDecodeError:
                logger.error("Invalid JSON data in request")
                return JsonResponse({"error": "Invalid JSON format"}, status=400)
            except Course.DoesNotExist:
                logger.error(f"Course with ID {course_id} not found")
                return JsonResponse({"error": "Course not found"}, status=404)
            except Exception as e:
                logger.error(f"Error in course_dashboard: {e}")
                return JsonResponse({"error": "An unexpected error occurred"}, status=500)

        return JsonResponse({"error": "Method not allowed"}, status=400)

    except Exception as e:
        logger.critical(f"Critical error in course_dashboard function: {e}")
        return JsonResponse({"error": "Something went wrong", "details": str(e)}, status=500)
        
@login_required
def course_outcomes(request):
    try:
        if request.method == "POST":
            try:
                if request.user.role != "Incharge":
                    return JsonResponse({"error": "You can not view this page"}, status=400)
                
                data = json.loads(request.body)
                course_id = data.get("id")

                if not course_id:
                    return JsonResponse({"error": "Course ID is required"}, status=400)

                data = {}
                finalized_flag = False

                course = Course.objects.get(id=course_id)

                if course.CO_finalized:
                    finalized_flag = True 

                data["finalized"] = finalized_flag
                data["all_course_outcome"] = []

                all_COs = CourseOutcome.objects.all()
                for c in all_COs:
                    data["all_course_outcome"].append({
                        "CO_name": c.title,
                        "CO_description": c.description
                    })

                if not finalized_flag:
                    return JsonResponse(data, status=200)

                projects = Project.objects.filter(course_id=course_id) 
                data["Projects"] = []

                for p in projects:
                    try:
                        CO = ProjectCOs.objects.get(project=p).outcome
                        COname = CO.title 
                    except ObjectDoesNotExist:
                        logger.warning(f"No Course Outcome found for Project ID {p.id}")
                        COname = None  

                    data["Projects"].append({
                        "projectname": p.title,
                        "projectid": p.id,
                        "projectnickname": p.nick_name,
                        "projectdomain": p.domain if p.domain else None,
                        "projectCO": COname,
                        "Project_section": p.nick_name[0] if p.nick_name else "N/A"
                    })

                return JsonResponse(data, status=200)

            except json.JSONDecodeError:
                logger.error("Invalid JSON data in request")
                return JsonResponse({"error": "Invalid JSON format"}, status=400)
            except Course.DoesNotExist:
                logger.error(f"Course with ID {course_id} not found")
                return JsonResponse({"error": "Course not found"}, status=404)
            except Exception as e:
                logger.error(f"Unexpected error in course_outcomes: {e}")
                return JsonResponse({"error": "An unexpected error occurred"}, status=500)

        return JsonResponse({"error": "Method not allowed"}, status=400)

    except Exception as e:
        logger.critical(f"Critical error in course_outcomes function: {e}")
        return JsonResponse({"error": "Something went wrong", "details": str(e)}, status=500)

def extract_key_value_pairs(s):
    pattern = r"(\d+):(\d+)"
    matches = re.findall(pattern, s)
    if not matches:
        return None
    return {int(k): int(v) for k, v in matches}

@login_required
def predict_outcomes(request):
    try:
        if request.method == "POST":
            try:
                if request.user.role != "Incharge":
                    return JsonResponse({"error": "You are not allowed to perform this operation"}, status=400)

                data = json.loads(request.body)
                course_id = data.get("course_id")

                if not course_id:
                    return JsonResponse({"error": "Course ID is required"}, status=400)

                try:
                    course = Course.objects.get(id=course_id)
                except Course.DoesNotExist:
                    logger.error(f"Course with ID {course_id} not found")
                    return JsonResponse({"error": "Course not found"}, status=404)

                if course.CO_finalized:
                    return JsonResponse({"error": "COs already finalized"}, status=400)

                course_outcomes_dictionary = {}
                COs_description = "These are the Course Outcomes:\n\n"
                all_COs = CourseOutcome.objects.all()

                for c in all_COs:
                    id = c.id
                    title = c.title
                    description = c.description
                    course_outcomes_dictionary[id] = title
                    COs_description += f"{id}. {title}: {description}\n"

                Projects_description = "These are the Projects with descriptions:\n\n"
                all_projects = Project.objects.filter(course_id=course_id)

                for p in all_projects:
                    project_id = p.id
                    project_description = p.description
                    project_title = p.title
                    Projects_description += f"{project_id}. {project_title}: {project_description}\n"

                instructions = '''Instructions:  
- Use only the Project ID and the Course Outcome ID in your final output.  
- Format the response as:  
  ProjectID : CourseOutcomeID  
- Example Mapping:  
  10:7  
  11:4  
  12:5    
  13:8   
  14:3     
  15:6  
  16:7  
  17:7    
  18:7    
  19:9   

Now, generate the correct mappings.  
                          '''
                model = genai.GenerativeModel('gemini-2.0-flash-thinking-exp')

                final_prompt = COs_description + Projects_description + instructions

                try:
                    response = model.generate_content(final_prompt)
                    LLM_response = response.text
                except Exception as e:
                    logger.error(f"Gemini API error: {e}")
                    return JsonResponse({"error": "AI model failed to generate predictions. Try again later."}, status=500)

                ProjecttoCO = extract_key_value_pairs(LLM_response)

                if ProjecttoCO is None:
                    return JsonResponse({"error": "Try again Later"}, status=200)

                data = {"Projects": []}

                for p in all_projects:
                    try:
                        COID = ProjecttoCO[p.id]
                        COname = course_outcomes_dictionary[COID]
                    except KeyError:
                        logger.warning(f"Missing Course Outcome mapping for Project ID {p.id}")
                        continue  # Skip this project if mapping is missing

                    data["Projects"].append({
                        "projectname": p.title,
                        "projectid": p.id,
                        "projectnickname": p.nick_name,
                        "projectdomain": p.domain if p.domain else None,
                        "projectCO": COname,
                        "Project_section": p.nick_name[0] if p.nick_name else "N/A"
                    })

                    # try:
                    #     ProjectCOs.objects.create(
                    #         project=p,
                    #         outcome=CourseOutcome.objects.get(id=COID)
                    #     )
                    # except ObjectDoesNotExist:
                    #     logger.error(f"CourseOutcome with ID {COID} not found")
                    #     continue

                # course.CO_finalized = True
                # course.save()

                return JsonResponse(data, status=200)

            except json.JSONDecodeError:
                logger.error("Invalid JSON data in request")
                return JsonResponse({"error": "Invalid JSON format"}, status=400)
            except Exception as e:
                logger.error(f"Unexpected error in predict_outcomes: {e}")
                return JsonResponse({"error": "An unexpected error occurred"}, status=500)

        return JsonResponse({"error": "Method not allowed"}, status=400)

    except Exception as e:
        logger.critical(f"Critical error in predict_outcomes function: {e}")
        return JsonResponse({"error": "Something went wrong", "details": str(e)}, status=500)
    
@login_required
def export_marks_excel(request, course_id):
    if request.method != "GET":
        return JsonResponse({"error": "Method not allowed"}, status=400)

    try:

        if request.user.role != "Incharge":
            return JsonResponse({"error": "You cannot view marks"}, status=400)
        # Get Course Data
        try:
            course = Course.objects.get(id=course_id)
        except Course.DoesNotExist:
            return JsonResponse({"error": "Course not found"}, status=404)

        course_name = course.name.replace(" ", "_")  
        course_batch = course.Batch
        projects = Project.objects.filter(course_id=course_id)
        rubrics = course.rubrics if isinstance(course.rubrics, list) else []  

        # Get Batch Section Data
        try:
            batch_obj = Batch.objects.get(batch=course_batch)
            section_data = batch_obj.section_data
        except Batch.DoesNotExist:
            return JsonResponse({"error": "Batch not found"}, status=404)

        sections = {section["Name"]: [] for section in section_data.values()}

        # Group projects by section
        for project in projects:
            section = project.nick_name[0] if project.nick_name else "Unknown"
            if section in sections:
                sections[section].append(project)

        # Create ZIP file in memory
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
            for section, section_projects in sections.items():
                if not section_projects:
                    continue  

                workbook = Workbook()
                sheet = workbook.active
                sheet.title = f"Section {section}"

                # Add headers
                headers = ["Project Nickname", "Project Title", "Student Roll No"]
                headers += [rubric["name"] for rubric in rubrics]
                headers.append("Total Marks")
                sheet.append(headers)

                # Add project marks
                for project in section_projects:
                    for member in project.marks:
                        student_id = member.get("id")

                        try:
                            student_obj = User.objects.get(id=student_id)
                            student_roll_no = student_obj.roll_no
                        except ObjectDoesNotExist:
                            student_roll_no = "Unknown"

                        row = [project.nick_name, project.title, student_roll_no]
                        total_marks = 0

                        for rubric in rubrics:
                            rubric_id = str(rubric["id"])
                            marks = member["marks"].get(rubric_id, 0)
                            row.append(marks)
                            total_marks += marks

                        row.append(total_marks)
                        sheet.append(row)

                # Save workbook to a BytesIO stream
                excel_stream = io.BytesIO()
                workbook.save(excel_stream)
                excel_stream.seek(0)

                # Add Excel file to ZIP archive
                file_name = f"{course_name}_Batch_{course_batch}_Section_{section}.xlsx"
                file_name = file_name.replace(" ", "_")
                zip_file.writestr(file_name, excel_stream.getvalue())

        # Ensure proper ZIP extension
        zip_filename = f"{course_name}_Batch_{course_batch}_Marks.zip"

        # Reset ZIP buffer and send response
        zip_buffer.seek(0)
        response = HttpResponse(zip_buffer.getvalue(), content_type="application/zip")
        response["Content-Disposition"] = f'attachment; filename={zip_filename}'

        return response

    except Exception as e:
        return JsonResponse({"error": f"An unexpected error occurred: {str(e)}"}, status=500)
    

def finalize_outcomes(request):
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=400)
    
    try:
        if request.user.role != "Incharge":
            return JsonResponse({"error": "You are not allowed to perform this operation"}, status=400)
        
        data = json.loads(request.body)
        course_id = data.get("course_id")
        course = Course.objects.get(id=course_id)
        if course.CO_finalized:
            return JsonResponse({"error": "Outcomes already finalized"}, status=400)

        projects = data.get("projects")
        

        for project in projects:
            project_id = project.get("project_id")
            CO_name = project.get("co_name")

            try:
                project_obj = Project.objects.get(id=project_id)
            except Project.DoesNotExist:
                return JsonResponse({"error": "Project not found"}, status=404)
            
            try:
                CO_obj = CourseOutcome.objects.get(title=CO_name)
            except CourseOutcome.DoesNotExist:
                return JsonResponse({"error": "Course Outcome not found"}, status=404)
            
            try:
                ProjectCOs.objects.create(
                    project=project_obj,
                    outcome=CO_obj
                )
            except Exception as e:
                return JsonResponse({"error": f"An unexpected error occurred: {str(e)}"}, status=500)
            
        course.CO_finalized = True
        course.save()
            
        return JsonResponse({"message": "Outcomes finalized successfully"}, status=200)
    
    except Exception as e:
        return JsonResponse({"error": f"An unexpected error occurred: "}, status=500)