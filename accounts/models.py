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
    # Programming Languages
    ('Python', 'Python'),
    ('Java', 'Java'),
    ('C++', 'C++'),
    ('C', 'C'),
    ('JavaScript', 'JavaScript'),
    ('TypeScript', 'TypeScript'),
    ('Go', 'Go'),
    ('Swift', 'Swift'),
    ('Kotlin', 'Kotlin'),
    ('Rust', 'Rust'),
    ('Ruby', 'Ruby'),
    ('PHP', 'PHP'),

    # Web Development
    ('HTML & CSS', 'HTML & CSS'),
    ('React.js', 'React.js'),
    ('Vue.js', 'Vue.js'),
    ('Angular', 'Angular'),
    ('Node.js', 'Node.js'),
    ('Django', 'Django'),
    ('Flask', 'Flask'),
    ('Spring Boot', 'Spring Boot'),
    ('FastAPI', 'FastAPI'),

    # Mobile Development
    ('Android Development', 'Android Development'),
    ('iOS Development', 'iOS Development'),
    ('Flutter', 'Flutter'),
    ('React Native', 'React Native'),

    # Data Science & Machine Learning
    ('Machine Learning', 'Machine Learning'),
    ('Deep Learning', 'Deep Learning'),
    ('Natural Language Processing (NLP)', 'Natural Language Processing (NLP)'),
    ('Computer Vision', 'Computer Vision'),
    ('Data Science', 'Data Science'),
    ('Big Data', 'Big Data'),
    ('Data Visualization', 'Data Visualization'),
    ('TensorFlow', 'TensorFlow'),
    ('PyTorch', 'PyTorch'),
    ('Scikit-learn', 'Scikit-learn'),
    ('Pandas & NumPy', 'Pandas & NumPy'),

    # Cybersecurity & Networking
    ('Cybersecurity', 'Cybersecurity'),
    ('Ethical Hacking', 'Ethical Hacking'),
    ('Network Security', 'Network Security'),
    ('Cryptography', 'Cryptography'),
    ('Penetration Testing', 'Penetration Testing'),
    ('Blockchain Security', 'Blockchain Security'),
    ('Web Security', 'Web Security'),
    ('Cloud Security', 'Cloud Security'),
    ('Digital Forensics', 'Digital Forensics'),

    # Cloud Computing & DevOps
    ('Cloud Computing', 'Cloud Computing'),
    ('AWS', 'AWS'),
    ('Google Cloud Platform (GCP)', 'Google Cloud Platform (GCP)'),
    ('Microsoft Azure', 'Microsoft Azure'),
    ('Docker', 'Docker'),
    ('Kubernetes', 'Kubernetes'),
    ('CI/CD Pipelines', 'CI/CD Pipelines'),

    # Software Engineering
    ('Software Development', 'Software Development'),
    ('Software Architecture', 'Software Architecture'),
    ('System Design', 'System Design'),
    ('Microservices', 'Microservices'),
    ('API Development', 'API Development'),
    ('Full Stack Development', 'Full Stack Development'),

    # Embedded Systems & IoT
    ('IoT', 'IoT'),
    ('Embedded Systems', 'Embedded Systems'),
    ('Arduino', 'Arduino'),
    ('Raspberry Pi', 'Raspberry Pi'),

    # Databases
    ('SQL', 'SQL'),
    ('PostgreSQL', 'PostgreSQL'),
    ('MongoDB', 'MongoDB'),
    ('MySQL', 'MySQL'),
    ('Firebase', 'Firebase'),
    ('Redis', 'Redis'),

    # AI & Robotics
    ('Artificial Intelligence', 'Artificial Intelligence'),
    ('Robotics', 'Robotics'),
    ('Autonomous Systems', 'Autonomous Systems'),
    ('Reinforcement Learning', 'Reinforcement Learning'),

    # Business & Soft Skills
    ('Project Management', 'Project Management'),
    ('Agile & Scrum', 'Agile & Scrum'),
    ('Technical Writing', 'Technical Writing'),
    ('Product Management', 'Product Management'),
    ('Business Analytics', 'Business Analytics'),

    # Game Development
    ('Game Development', 'Game Development'),
    ('Unity', 'Unity'),
    ('Unreal Engine', 'Unreal Engine'),

    # Quantum Computing
    ('Quantum Computing', 'Quantum Computing'),
]


    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='skills', blank=True, null=True)
    name = models.CharField(max_length=100, choices=SKILL_CHOICES)

    def __str__(self):
        return f"{self.user.username} - {self.name}"


class Interest(models.Model):
    INTEREST_CHOICES = [
    # Core Tech Interests
    ('AI & ML', 'AI & ML'),
    ('Competitive Programming', 'Competitive Programming'),
    ('Open Source', 'Open Source'),
    ('Cybersecurity', 'Cybersecurity'),
    ('Cloud Computing', 'Cloud Computing'),
    ('Software Development', 'Software Development'),
    ('Data Science', 'Data Science'),
    ('Blockchain Technology', 'Blockchain Technology'),
    ('Quantum Computing', 'Quantum Computing'),

    # Research & Innovation
    ('Research & Publications', 'Research & Publications'),
    ('Technical Blogging', 'Technical Blogging'),
    ('Mathematical Modeling', 'Mathematical Modeling'),
    ('Scientific Computing', 'Scientific Computing'),

    # Engineering & Hardware
    ('IoT', 'IoT'),
    ('Embedded Systems', 'Embedded Systems'),
    ('Robotics', 'Robotics'),
    ('Autonomous Systems', 'Autonomous Systems'),

    # Game Development & Graphics
    ('Game Development', 'Game Development'),
    ('3D Modeling', '3D Modeling'),
    ('Augmented Reality (AR)', 'Augmented Reality (AR)'),
    ('Virtual Reality (VR)', 'Virtual Reality (VR)'),

    # Business & Management
    ('Entrepreneurship', 'Entrepreneurship'),
    ('Product Management', 'Product Management'),
    ('Startup Culture', 'Startup Culture'),
    ('Stock Market & Trading', 'Stock Market & Trading'),
    ('Business Analytics', 'Business Analytics'),

    # Networking & Community Building
    ('Tech Meetups & Hackathons', 'Tech Meetups & Hackathons'),
    ('Public Speaking', 'Public Speaking'),
    ('Technical Writing', 'Technical Writing'),

    # Miscellaneous
    ('Ethical Hacking', 'Ethical Hacking'),
    ('Astronomy & Space Tech', 'Astronomy & Space Tech'),
    ('Biotechnology & Bioinformatics', 'Biotechnology & Bioinformatics'),
    ('Sustainable Tech', 'Sustainable Tech'),
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

