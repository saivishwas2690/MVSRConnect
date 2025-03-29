from django.contrib.auth.models import AbstractUser
from django.db import models


class NewUser(models.Model):
    email = models.CharField(max_length=100, unique=True)
    token = models.CharField(max_length=1000, unique=True)


class User(AbstractUser):

    ROLE_CHOICES = [
        ('Teacher', 'Teacher'),
        ('Student', 'Student'),
        ('Incharge', 'Incharge'),
    ]
    DESIGNATION_CHOICES = [
        ('Professor', 'Professor'),
        ('Asst. Professor', 'Asst. Professor'),
        ('NA', 'NA'),
    ]
    DEPARTMENT_CHOICES = [
        ('CSE', 'CSE'),
        ('IT', 'IT')
    ]

    roll_no = models.CharField(max_length=20, unique=True, blank=True, null=True)
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default='Student')
    batch = models.PositiveIntegerField(blank=True, null=True)
    designation = models.CharField(max_length=20, choices=DESIGNATION_CHOICES, blank=True, null=True)
    department = models.CharField(max_length=50, choices=DEPARTMENT_CHOICES, blank=True, null=True)


    def __str__(self):
        return self.username
    

class JobPost(models.Model):
    author = models.ForeignKey(User, on_delete=models.CASCADE)
    company = models.CharField(max_length=100)
    jobrole = models.CharField(max_length=100)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    link = models.CharField(max_length=1000, blank=True, null=True)


    def __str__(self):
        return self.title
    
class Batch(models.Model):
    batch = models.IntegerField(unique=True)
    section_data = models.JSONField(default=dict)

    def __str__(self):
        return str(self.batch)
    
class PersonalProject(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='personal_projects')
    title = models.CharField(max_length=255)
    description = models.TextField()
    link = models.URLField(max_length=255, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} - {self.title}"


class Skill(models.Model):
    SKILL_CHOICES = [
        ('Python', 'Python'),
        ('Java', 'Java'),
        ('C++', 'C++'),
        ('Web Development', 'Web Development'),
        ('Machine Learning', 'Machine Learning'),
        ('Data Science', 'Data Science'),
        ('Cybersecurity', 'Cybersecurity'),
        ('Cloud Computing', 'Cloud Computing'),
        ('Blockchain', 'Blockchain'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='skills', blank=True, null=True)
    name = models.CharField(max_length=100, choices=SKILL_CHOICES)

    def __str__(self):
        return f"{self.user.username} - {self.name}"


class Interest(models.Model):
    INTEREST_CHOICES = [
        ('AI & ML', 'AI & ML'),
        ('Competitive Programming', 'Competitive Programming'),
        ('Open Source', 'Open Source'),
        ('Cybersecurity', 'Cybersecurity'),
        ('IoT', 'IoT'),
        ('Cloud Computing', 'Cloud Computing'),
        ('Software Development', 'Software Development'),
        ('Research & Publications', 'Research & Publications'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='interests', blank=True, null=True)
    name = models.CharField(max_length=100, choices=INTEREST_CHOICES)

    def __str__(self):
        return f"{self.user.username} - {self.name}"




class SocialLink(models.Model):
    PLATFORM_CHOICES = [
        ('GitHub', 'GitHub'),
        ('LinkedIn', 'LinkedIn'),
        ('Hugging Face', 'Hugging Face'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='social_links', null=True, blank=True)
    platform = models.CharField(max_length=50, choices=PLATFORM_CHOICES)
    url = models.URLField(max_length=255)

    def __str__(self):
        return f"{self.user.username} - {self.platform}"

