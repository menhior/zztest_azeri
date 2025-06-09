from django.contrib import admin
from .models import *

# Register your models here.
admin.site.register(Profile)
admin.site.register(Student)
admin.site.register(Teacher)
admin.site.register(Parent)
admin.site.register(StudentTeacherRelation)
admin.site.register(StudentParentRelation)