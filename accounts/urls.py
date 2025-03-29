from django.urls import path
from . import views

urlpatterns = [
    path("login/", views.login_user, name="login"),
    path("logout/", views.logout_user, name="logout"),
    path("csrf-token/", views.get_csrf_token, name="csrf-token"),
    path("", views.home, name="home"),
    path("createjobpost/", views.create_job_post, name="createjob"),
    path("verify-email/", views.send_verification_email, name="verify_email"),
    path("verify/<str:token>/", views.signup, name="verify_email"),
    path("getjobposts/<int:page_number>/", views.get_job_posts, name="jobposts"),
    path("jobsapi/", views.jobs_api, name="jobsapi"),
    path("profile/<int:id>/", views.profile, name="projectdetail"),
    path("search/", views.search, name="search"),
    path("news/", views.news, name="news"),
    path("editprofile/", views.edit_profile, name="editprofile"),
    
    path('skills/<str:query>/', views.skills_api, name='skills_api'),
    path('skills/', views.skills_api, name='skills_all'),
    path('interests/<str:query>/', views.interest_api, name='interest_api'),
    path('interests/', views.interest_api, name='interest_all'),
    
]


