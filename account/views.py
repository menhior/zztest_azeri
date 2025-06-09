from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods
from django.views.decorators.http import require_POST
from django.contrib.auth.models import User, auth
from django.http import JsonResponse
from .models import Profile
from quiz.models import QuizSubmission

from django.contrib import messages
from django.db import IntegrityError

from .models import *



def register(request):
    if request.method == 'POST':
        step = request.POST.get('step', '1')
        
        if step == '1':
            # Step 1: User type selection
            user_type = request.POST.get('user_type')
            if not user_type:
                messages.error(request, 'Please select a user type')
                return redirect('register')
            
            return render(request, 'register.html', {
                'user_type': user_type,
                'form_data': request.POST if 'form_data' in request.POST else None
            })
        
        elif step == '2':
            # Step 2: Actual registration
            user_type = request.POST.get('user_type')
              
            try:
                # Create base user (common for all types)
                user = User.objects.create_user(
                    username=request.POST.get('username'),
                    email=request.POST.get('email'),
                    password=request.POST.get('password1'),
                    first_name=request.POST.get('first_name'),
                    last_name=request.POST.get('last_name')
                )
                
                if user_type == 'teacher':
                    # Create teacher profile
                    teacher = Teacher.objects.create(
                        user=user,
                        gender=request.POST.get('gender'),
                        mobile=request.POST.get('mobile'),
                        subject=request.POST.get('subject'),  # From dropdown
                    )
                    messages.success(request, 'Teacher registration successful! Please login.')
                
                elif user_type == 'student':
                    # Create student profile
                    student = Student.objects.create(
                        user=user,
                        gender=request.POST.get('gender'),
                        mobile=request.POST.get('mobile'),
                        grade=request.POST.get('grade')
                    )
                    messages.success(request, 'Student registration successful! Please login.')
                
                elif user_type == 'parent':
                    # Create parent profile
                    parent = Parent.objects.create(
                        user=user,
                        gender=request.POST.get('gender'),
                        mobile=request.POST.get('mobile'),
                    )
                    
                    messages.success(request, 'Parent registration successful! Please login.')

                return redirect('login')
            
            except IntegrityError:
                messages.error(request, 'Username already exists')
            except Exception as e:
                messages.error(request, f'An error occurred: {str(e)}')
            
            # If error occurs, return with form data
            return render(request, 'register.html', {
                'user_type': user_type,
                'form_data': request.POST
            })
    
    # Initial GET request - show user type selection
    return render(request, 'register.html')
        
@login_required
def profile(request, username):
    user_object = get_object_or_404(User, username=username)
    profile = None
    role = None
    pending_requests = []
    
    if hasattr(user_object, 'student'):
        profile = user_object.student
        role = 'student'
        # Get pending requests where student is the receiver
        pending_requests = {
            'teachers': StudentTeacherRelation.objects.filter(student=profile, is_approved=False),
            'parents': StudentParentRelation.objects.filter(student=profile, is_approved=False)
        }
    elif hasattr(user_object, 'teacher'):
        profile = user_object.teacher
        role = 'teacher'
        pending_requests = {
            'students': StudentTeacherRelation.objects.filter(teacher=profile, is_approved=False)
        }
    elif hasattr(user_object, 'parent'):
        profile = user_object.parent
        role = 'parent'
        pending_requests = {
            'students': StudentParentRelation.objects.filter(parent=profile, is_approved=False)
        }
    
    context = {
        "profile_user": user_object,
        "user_profile": profile,
        "role": role,
        "pending_requests": pending_requests,
        "is_own_profile": (request.user == user_object),
    }
    return render(request, "profile.html", context)
 

@login_required
def editProfile(request):
    user_object = request.user
    
    # Determine profile type
    if hasattr(user_object, 'student'):
        user_profile = user_object.student
        role = 'student'
    elif hasattr(user_object, 'teacher'):
        user_profile = user_object.teacher
        role = 'teacher'
    elif hasattr(user_object, 'parent'):
        user_profile = user_object.parent
        role = 'parent'
    else:
        raise Http404("Profile not found")

    if request.method == "POST":
        # Validate and update User model fields
        new_email = request.POST.get('email', '').strip()
        if new_email and new_email != user_object.email:
            if User.objects.filter(email=new_email).exclude(pk=user_object.pk).exists():
                messages.error(request, "Email already in use by another account")
                return redirect('edit_profile')
            user_object.email = new_email

        new_username = request.POST.get('username', '').strip()
        if new_username and new_username != user_object.username:
            if User.objects.filter(username=new_username).exclude(pk=user_object.pk).exists():
                messages.error(request, "Username already taken")
                return redirect('edit_profile')
            user_object.username = new_username

        # Validate mobile number
        mobile = request.POST.get('mobile', '').strip()
        if not mobile.isdigit() or len(mobile) < 10:
            messages.error(request, "Please enter a valid 10-digit mobile number")
            return redirect('edit_profile')

        # Validate grade for students
        if role == 'student':
            try:
                grade = int(request.POST.get('grade', 0))
                if not (1 <= grade <= 12):
                    raise ValueError
            except ValueError:
                messages.error(request, "Please enter a valid grade (1-12)")
                return redirect('edit_profile')
            user_profile.grade = grade

        # Update fields
        user_object.first_name = request.POST.get('firstname', user_object.first_name)
        user_object.last_name = request.POST.get('lastname', user_object.last_name)
        user_object.save()

        user_profile.gender = request.POST.get('gender', user_profile.gender)
        user_profile.mobile = mobile
        
        if role == 'teacher':
            user_profile.subject = request.POST.get('subject', user_profile.subject)
        
        user_profile.save()

        messages.success(request, "Profile updated successfully!")
        return redirect('profile', user_object.username)

    context = {
        'user_object': user_object,
        'user_profile': user_profile,
        'role': role,
        'is_own_profile': True
    }
    return render(request, 'profile-edit.html', context)


@login_required
def confirm_delete(request):
    """Renders the confirmation page"""
    return render(request, 'confirm.html', {
        'username': request.user.username,
        'full_name': request.user.get_full_name(),
        'role': 'student' if hasattr(request.user, 'student') 
               else 'teacher' if hasattr(request.user, 'teacher') 
               else 'parent'
    })


@login_required
@require_http_methods(["GET", "POST"])
def deleteProfile(request):
    user_object = request.user
    
    # GET request shows confirmation page
    if request.method == "GET":
        # Determine user role
        role = None
        if hasattr(user_object, 'student'):
            role = 'student'
        elif hasattr(user_object, 'teacher'):
            role = 'teacher'
        elif hasattr(user_object, 'parent'):
            role = 'parent'
            
        return render(request, 'confirm.html', {
            'username': user_object.username,
            'full_name': user_object.get_full_name(),
            'role': role
        })
    
    # POST request handles deletion
    else:
        # Verify confirmation
        if not request.POST.get('confirmation', False):
            messages.error(request, "Please check the confirmation box")
            return redirect('delete_profile')
        
        try:
            # Delete profile based on role
            if hasattr(user_object, 'student'):
                user_object.student.delete()
            elif hasattr(user_object, 'teacher'):
                user_object.teacher.delete()
            elif hasattr(user_object, 'parent'):
                user_object.parent.delete()
            
            # Store username for message before deletion
            username = user_object.username
            user_object.delete()
            
            # Logout and redirect
            logout(request)
            messages.success(request, f"Account {username} has been permanently deleted")
            return redirect('home')
            
        except Exception as e:
            messages.error(request, f"Deletion failed: {str(e)}")
            return redirect('profile', user_object.username)

def login(request):
    if request.user.is_authenticated:
        return redirect('profile', request.user.username)

    if request.method == "POST":
        username = request.POST['username']
        password = request.POST['password']

        user = auth.authenticate(username=username, password=password)

        if user is not None:
            auth.login(request, user)
            return redirect('profile', username)
        else:
            messages.info(request, 'Credentials Invalid!')
            return redirect('login')

    return render(request, "login.html")

@login_required
def logout(request):
    auth.logout(request)
    return redirect('login')



@require_POST
def send_connection_request(request):
    receiver_id = request.POST.get('receiver_id')
    request_type = request.POST.get('request_type')
    
    try:
        receiver = User.objects.get(id=receiver_id)
        
        # Validate request based on sender type
        if request_type == 'teacher_student':
            if not hasattr(request.user, 'teacher'):
                raise ValueError("Only teachers can send teacher-student requests")
            sender_model = request.user.teacher
            receiver_model = receiver.student
            relation_model = StudentTeacherRelation
        elif request_type == 'student_teacher':
            if not hasattr(request.user, 'student'):
                raise ValueError("Only students can send student-teacher requests")
            sender_model = request.user.student
            receiver_model = receiver.teacher
            relation_model = StudentTeacherRelation
        elif request_type == 'parent_student':
            if not hasattr(request.user, 'parent'):
                raise ValueError("Only parents can send parent-student requests")
            sender_model = request.user.parent
            receiver_model = receiver.student
            relation_model = StudentParentRelation
        elif request_type == 'student_parent':
            if not hasattr(request.user, 'student'):
                raise ValueError("Only students can send student-parent requests")
            sender_model = request.user.student
            receiver_model = receiver.parent
            relation_model = StudentParentRelation
        else:
            raise ValueError("Invalid request type")
        
        # Create the relation
        relation_data = {
            'student': sender_model if request_type.endswith('_parent') else receiver_model,
            request_type.split('_')[0]: sender_model,
            'is_approved': False
        }
        
        if request_type in ['teacher_student', 'student_teacher']:
            relation_data['subject'] = sender_model.subject if hasattr(sender_model, 'subject') else receiver_model.subject
        
        relation, created = relation_model.objects.get_or_create(
            **{k: v for k, v in relation_data.items() if k != 'subject'},
            defaults=relation_data
        )
        
        if created:
            return JsonResponse({'success': True, 'message': 'Request sent successfully'})
        return JsonResponse({'success': False, 'error': 'Request already exists'})
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

def handle_connection_request(request, relation_id, action):
    try:
        # Determine which relation model to use based on URL
        if 'teacher' in request.path:
            relation = get_object_or_404(StudentTeacherRelation, id=relation_id)
            relation_type = 'teacher'
        else:
            relation = get_object_or_404(StudentParentRelation, id=relation_id)
            relation_type = 'parent'
        
        # Verify the current user can handle this request
        if not (request.user == relation.student.user or 
                (relation_type == 'teacher' and request.user == relation.teacher.user) or
                (relation_type == 'parent' and request.user == relation.parent.user)):
            raise PermissionDenied
        
        if action == 'approve':
            relation.is_approved = True
            relation.approval_date = timezone.now()
            relation.save()
            messages.success(request, 'Request approved successfully')
        elif action == 'reject':
            relation.delete()
            messages.success(request, 'Request rejected')
        else:
            messages.error(request, 'Invalid action')
            
    except Exception as e:
        messages.error(request, f'Error: {str(e)}')
    
    return redirect('profile', username=request.user.username)




@login_required
@require_POST
def send_connection_request(request):
    try:
        receiver_id = request.POST.get('receiver_id')
        receiver = User.objects.get(id=receiver_id)
        
        # Determine request type based on sender's role
        if hasattr(request.user, 'teacher'):
            # Teacher sending to student
            StudentTeacherRelation.objects.create(
                teacher=request.user.teacher,
                student=receiver.student,
                subject=request.user.teacher.subject,
                is_approved=False
            )
        elif hasattr(request.user, 'parent'):
            # Parent sending to student
            StudentParentRelation.objects.create(
                parent=request.user.parent,
                student=receiver.student,
                is_approved=False
            )
        elif hasattr(request.user, 'student'):
            # Student sending to teacher/parent
            if hasattr(receiver, 'teacher'):
                StudentTeacherRelation.objects.create(
                    student=request.user.student,
                    teacher=receiver.teacher,
                    subject=receiver.teacher.subject,
                    is_approved=False
                )
            elif hasattr(receiver, 'parent'):
                StudentParentRelation.objects.create(
                    student=request.user.student,
                    parent=receiver.parent,
                    is_approved=False
                )
        
        return JsonResponse({'status': 'success'})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)})

@login_required
def approve_connection(request, relation_type, pk):
    try:
        if relation_type == 'teacher':
            relation = StudentTeacherRelation.objects.get(pk=pk)
            if request.user != relation.student.user:
                raise PermissionDenied
        else:
            relation = StudentParentRelation.objects.get(pk=pk)
            if request.user != relation.student.user:
                raise PermissionDenied
        
        relation.is_approved = True
        relation.save()
        messages.success(request, 'Connection approved')
    except Exception as e:
        messages.error(request, f'Error: {str(e)}')
    
    return redirect('profile', username=request.user.username)

@login_required
def reject_connection(request, relation_type, pk):
    try:
        if relation_type == 'teacher':
            relation = StudentTeacherRelation.objects.get(pk=pk)
            if request.user != relation.student.user:
                raise PermissionDenied
        else:
            relation = StudentParentRelation.objects.get(pk=pk)
            if request.user != relation.student.user:
                raise PermissionDenied
        
        relation.delete()
        messages.success(request, 'Connection rejected')
    except Exception as e:
        messages.error(request, f'Error: {str(e)}')
    
    return redirect('profile', username=request.user.username)