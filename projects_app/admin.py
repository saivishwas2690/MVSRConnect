from django.contrib import admin
from .models import Course, Project, ProjectStudent, CourseOutcome, ProjectCOs

@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'name', 'code', 'Batch', 'requires_guide', 'requires_internship',
        'limit_per_prof', 'limit_per_asst_prof', 'domain_requirement', 'date',
        'rubrics', 'domains', 'CO_finalized'
    )
    search_fields = ('name', 'code', 'Batch')
    list_filter = ('requires_guide', 'requires_internship', 'domain_requirement', 'Batch')
    ordering = ('-date',)
    readonly_fields = ('date',)

@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'title', 'description', 'course', 'guide', 'date', 'report',
        'abstract', 'domain', 'nick_name', 'marks', 'guide_approval_form'
    )
    search_fields = ('title', 'course', 'guide')
    list_filter = ('course', 'guide', 'date')
    ordering = ('-date',)
    readonly_fields = ('date',)

@admin.register(ProjectStudent)
class ProjectStudentAdmin(admin.ModelAdmin):
    list_display = ( 'id','project','student' )
    search_fields = ( 'project__title','student__user__username', )
    list_filter = ()


admin.site.register(CourseOutcome)
admin.site.register(ProjectCOs)





