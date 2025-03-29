from django.urls import path
from . import views

urlpatterns = [
    path("createcourse/", views.create_course, name="createcourse"),
    path("createproject/", views.create_project, name="createproject"),
    path("fetchcourses/", views.fetch_courses, name="fetchcourses"),
    path("fetchbatches/", views.fetch_batches, name="fetchbatches"),
    path("viewprojects/", views.view_projects, name="viewprojects"),
    path('getprojects/', views.get_projects, name='getprojects'),
    path("<int:id>/", views.project_detail, name="projectdetail"),
    path("availableguides/", views.available_guides, name="available-guides"),
    path("searchteammembers/", views.search_team_members, name="searchteammembers"),
    path("uploadfile/", views.upload_document, name="uploadfile"),
    path("evaluate/<int:id>/", views.evaluate, name="evaluate"),
    path("evaluate/<int:id>/save/", views.save_marks, name="evaluate"),
    path("assignguide/", views.assign_guide, name='assignguide'),
    path("courses/", views.get_courses, name="getcourses"),

    path("courseoutcomes/", views.course_outcomes, name="course_outcomes"),
    path("viewcoursedashboard/<int:id>/", views.view_course_dashboard, name="view_course_dashboard"),
    path("coursedashboard/", views.course_dashboard, name='course_dashboard'),
    path("predictoutcomes/", views.predict_outcomes, name="predict_outcomes"),
    path("downloadmarks/<int:course_id>/", views.export_marks_excel, name="downloadmarks")

]


