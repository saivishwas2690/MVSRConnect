from django.db import models
from accounts.models import User


class Course(models.Model):  
    name = models.CharField(max_length=255, null=False, blank=False)
    code = models.CharField(max_length=150, null=False, blank=False)
    Batch = models.IntegerField(null=False, blank=False)
    requires_guide = models.BooleanField(null=False, blank=False, default=False)
    requires_internship = models.BooleanField(null=False, blank=False, default=False)
    limit_per_prof = models.IntegerField(null=False, blank=False, default=0)
    limit_per_asst_prof = models.IntegerField(null=False, blank=False, default=0)
    domain_requirement = models.BooleanField(null=False, blank=False, default=False)
    date = models.DateTimeField(auto_now_add=True)
    rubrics = models.JSONField()  
    domains = models.JSONField(default=list, blank=True) 
    CO_finalized = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.name} ({self.code}) - Batch {self.Batch}"


class Project(models.Model):  
    title = models.CharField(max_length=255)
    description = models.TextField()
    course = models.ForeignKey(Course, on_delete=models.CASCADE)  
    guide = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True, limit_choices_to={'role': 'Teacher'}) 
    date = models.DateTimeField(auto_now_add=True)
    report = models.URLField(null=True, blank=True)
    abstract = models.URLField(null=True, blank=True)
    domain = models.CharField(max_length=255, null=True, blank=True)
    nick_name = models.CharField(max_length=255, null=True, blank=True)  
    marks = models.JSONField(null=True, blank=True)
    guide_approval_form = models.URLField(null=True, blank=True)

    def __str__(self):
        return self.title


class ProjectStudent(models.Model): 
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='students')
    student = models.ForeignKey(User, on_delete=models.CASCADE, limit_choices_to={'role': 'Student'})
    internship_name = models.CharField(max_length=255, null=True, blank=True)  

    def __str__(self):
        return f"{self.student.username} - {self.project.title}"

class CourseOutcome(models.Model):
    title = models.CharField(max_length=255, unique=True)
    description = models.TextField()

    def __str__(self):
        return f"{self.title}"
    
class ProjectCOs(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="categories")
    outcome = models.ForeignKey(CourseOutcome, on_delete=models.CASCADE) 

    def __str__(self):
        return f"{self.project.title} -> {self.outcome.title}" 
    

    


    



