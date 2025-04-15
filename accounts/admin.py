from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User, JobPost, Batch, Skill, Interest, SocialLink, PersonalProject, NewUser, UserForgotPassword

class UserAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (
        ('Additional Info', {'fields': ('role', 'designation', 'roll_no', 'batch')}),
    )
    list_display = ('id', 'username', 'email', 'first_name', 'last_name', 'role', 'designation', 'batch')
    list_filter = ('role', 'designation', 'batch')

admin.site.register(User, UserAdmin)

admin.site.register(JobPost)
admin.site.register(Batch)
admin.site.register(Skill)
admin.site.register(Interest)
admin.site.register(SocialLink)
admin.site.register(PersonalProject)
admin.site.register(NewUser)
admin.site.register(UserForgotPassword)

