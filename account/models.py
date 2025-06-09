from django.db import models
from django.contrib.auth.models import User




class Student(models.Model): 
    user=models.OneToOneField(User,on_delete=models.CASCADE)
    gender = models.CharField(max_length=6, blank=True, null=True)
    mobile = models.CharField(max_length=20,null=False)
    grade = models.PositiveIntegerField(blank=True, null=True)
    date_created = models.DateTimeField(auto_now_add=True, null=True)
   
   # Relationships with teachers and parents
    teachers = models.ManyToManyField('Teacher', through='StudentTeacherRelation', related_name='students')
    parents = models.ManyToManyField('Parent', through='StudentParentRelation', related_name='students')
   
    @property 
    def get_name(self):
        return self.user.first_name+" "+self.user.last_name
    @property
    def get_instance(self):
        return self
    def __str__(self):
        return self.user.first_name

class Teacher(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    gender = models.CharField(max_length=6, blank=True, null=True)
    mobile = models.CharField(max_length=20, null=False)
    subject = models.CharField(max_length=50, null=True)  # Stores subject from dropdown
    
    @property
    def get_name(self):
        return f"{self.user.first_name} {self.user.last_name}"
        
    def __str__(self):
        return self.user.first_name



class Parent(models.Model):
    user=models.OneToOneField(User,on_delete=models.CASCADE)
    gender = models.CharField(max_length=6, blank=True, null=True)
    mobile = models.CharField(max_length=20,null=False)

    @property
    def get_name(self):
        return self.user.first_name+" "+self.user.last_name
    @property
    def get_instance(self):
        return self
    def __str__(self):
        return self.user.first_name

class StudentTeacherRelation(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    teacher = models.ForeignKey(Teacher, on_delete=models.CASCADE)
    subject = models.CharField(max_length=50)
    # Removed subject ForeignKey since it's now stored in Teacher model
    is_approved = models.BooleanField(default=False)
    request_date = models.DateTimeField(auto_now_add=True)
    approval_date = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ('student', 'teacher')  # Removed subject from unique_together

    def __str__(self):
        # Get subject from the teacher model directly
        return f"{self.student} - {self.teacher} ({self.teacher.subject}) - {'Approved' if self.is_approved else 'Pending'}"

    def save(self, *args, **kwargs):
        """Automatically set subject from teacher if not provided"""
        if not self.subject and self.teacher_id:
            self.subject = self.teacher.subject
        super().save(*args, **kwargs)

    @property
    def subject(self):
        """Helper property to access the teacher's subject"""
        return self.teacher.subject

class StudentParentRelation(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    parent = models.ForeignKey(Parent, on_delete=models.CASCADE)
    is_approved = models.BooleanField(default=False)
    request_date = models.DateTimeField(auto_now_add=True)  # Automatically set when the request is made
    approval_date = models.DateTimeField(null=True, blank=True)  # Set when the request is approved


class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, null=True, verbose_name='User Object') #verbose_name
    bio = models.TextField(blank=True, null=True)
    location = models.CharField(max_length=100, blank=True, null=True)
    GENDER = (
        ('Male', 'Male'),
        ('Female', 'Female'),
    )
    gender = models.CharField(max_length=6, choices=GENDER, blank=True, null=True)

    def __str__(self):
        return self.user.username
    
    @property
    def full_name(self):
        return f"{self.user.first_name} {self.user.last_name}"
