from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from account.models import Profile
from .models import Quiz, Category, UserRank, AnswerTracking
from django.db.models import Q
from quiz.models import QuizSubmission
from django.contrib import messages
from django.utils import timezone
from django.db.models import Sum
import time

from .utils import get_hardest_topics, process_quiz_submission

# Create your views here.

@login_required
def all_quiz_view(request):

    quizzes = Quiz.objects.order_by('-created_at')
    categories = Category.objects.all()

    context = {"quizzes": quizzes, "categories": categories}
    return render(request, 'all-quiz.html', context)

@login_required
def search_view(request, category):

    # search by search bar
    if request.GET.get('q') != None:
        q = request.GET.get('q')
        query = Q(title__icontains=q) | Q(description__icontains=q)
        quizzes = Quiz.objects.filter(query).order_by('-created_at')
    
    # search by category
    elif category != " ":
        quizzes = Quiz.objects.filter(category__name=category).order_by('-created_at')
    
    else:
        quizzes = Quiz.objects.order_by('-created_at')


    categories = Category.objects.all()

    context = {"quizzes": quizzes, "categories": categories}
    return render(request, 'all-quiz.html', context)

# In your views.py
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.utils import timezone # Make sure timezone is imported
from django.db import transaction # Import transaction for atomicity

from .models import Quiz, QuizSubmission, Question, Choice, AnswerTracking # Ensure AnswerTracking is imported
# No need to import Sum here, as the signal handles question stat updates.


@login_required
def quiz_view(request, quiz_id):
    """
    Enhanced quiz view with:
    - Time tracking
    - Detailed submission handling (per-question)
    - Saves AnswerTracking instances
    - Progress tracking
    - Error handling
    """
    quiz = get_object_or_404(Quiz.objects.prefetch_related('question_set__choice_set'), pk=quiz_id)
    # prefetch_related('question_set__choice_set') is crucial for performance
    # It fetches all questions and their choices in a few queries,
    # preventing many individual database hits in the loop.

    # Store start time in session for accurate time_spent calculation
    # This ensures start_time persists across the POST request
    if 'quiz_start_time' not in request.session:
        request.session['quiz_start_time'] = timezone.now().isoformat() # Store as ISO format string

    if request.method == "POST":
        # Retrieve the start time from the session
        start_time_str = request.session.pop('quiz_start_time', None)
        if start_time_str:
            start_time = timezone.datetime.fromisoformat(start_time_str)
            time_spent = timezone.now() - start_time
        else:
            # Fallback if start time not found (e.g., session expired or direct POST)
            time_spent = timezone.timedelta(seconds=0)

        total_score = 0
        question_breakdown_data = {} # To populate QuizSubmission.question_breakdown JSONField

        # Use a database transaction to ensure all answers and the submission are saved atomically
        # If any part fails, everything rolls back.
        with transaction.atomic():
            # Create QuizSubmission first (score will be updated later)
            submission = QuizSubmission.objects.create(
                user=request.user,
                quiz=quiz,
                score=0, # Initial score, will be updated
                time_started=start_time,
                time_completed=timezone.now(),
                time_spent=time_spent
            )
 
            # Loop through all questions in the quiz to process answers
            for question in quiz.question_set.all():
                print(question)
                # The name of the input field in your HTML quiz form should match this:
                # e.g., <input type="radio" name="question_{{ question.id }}" value="{{ choice.id }}">
                selected_choice_id = request.POST.get(f'question_{question.id}')
                print(request.POST)
                print(selected_choice_id)
                is_correct = False
                selected_choice = None

                if selected_choice_id:
                    try:
                        selected_choice = Choice.objects.get(pk=selected_choice_id, question=question)
                        is_correct = selected_choice.is_correct
                        if is_correct:
                            total_score += question.mark # Add question's mark to total score
                    except Choice.DoesNotExist:
                        # Handle cases where selected_choice_id is invalid or doesn't belong to the question
                        # You might log this or handle it as an incorrect answer
                        pass # is_correct remains False

                # Create and save an AnswerTracking instance
                AnswerTracking.objects.create(
                    user=request.user,
                    question=question,
                    quiz_submission=submission, # Link to the current submission
                    selected_choice=selected_choice, # Will be None if no valid choice selected
                    is_correct=is_correct
                )

                # Populate question_breakdown for QuizSubmission
                question_breakdown_data[str(question.id)] = {
                    "selected_choice_id": selected_choice.id if selected_choice else None,
                    "selected_choice_text": selected_choice.text if selected_choice else None,
                    "correct_choice_id": question.choice_set.get(is_correct=True).id if question.choice_set.filter(is_correct=True).exists() else None,
                    "correct_choice_text": question.choice_set.get(is_correct=True).text if question.choice_set.filter(is_correct=True).exists() else None,
                    "is_correct": is_correct,
                    "mark_awarded": question.mark if is_correct else 0,
                    "question_text": question.text,
                    "question_theme": question.question_theme,
                }

            # Update the score and question breakdown on the QuizSubmission
            submission.score = total_score
            submission.question_breakdown = question_breakdown_data
            submission.save() # This save triggers the QuizSubmission post_save signal

            # Update user's progress (if 'userprofile' is connected and has this method)
            if hasattr(request.user, 'userprofile'):
                # Assuming update_quiz_progress expects a QuizSubmission instance
                request.user.userprofile.update_quiz_progress(submission)

            return redirect('quiz_result', submission_id=submission.id)

    # GET request - show quiz
    context = {
        'quiz': quiz,
        # 'questions': quiz.question_set.all().select_related('quiz'), # Not strictly needed if prefetch_related is used
        # We prefetch all questions and choices, so quiz.question_set.all() is fine
        'questions': quiz.question_set.all(),
        'user_progress': request.user.quizsubmission_set.filter(quiz=quiz).first() if request.user.is_authenticated else None
    }
    return render(request, 'quiz.html', context)


# In your views.py
def format_duration(td):
    if not td:
        return "N/A"
    total_seconds = int(td.total_seconds())
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60
    return f"{hours}h {minutes}m {seconds}s" if hours else f"{minutes}m {seconds}s"

from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.db.models import Sum, Avg, F, ExpressionWrapper, DurationField, Case, When, Count, FloatField
from django.utils import timezone
from datetime import timedelta
from django.db.models.functions import Coalesce

# Import your models
from .models import QuizSubmission, Quiz, Question, Choice, AnswerTracking, UserRank # Add UserRank if you use it for leaderboard_position
# from account.models import Student # Only if you're using Student for UserRank or other context
# from .utils import format_duration # Assuming you have this utility function

# quiz/views.py
from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from django.utils import timezone
from datetime import timedelta
from django.db.models.functions import Coalesce

# Import your models
from .models import QuizSubmission, Quiz, Question, Choice, AnswerTracking, UserRank




@login_required
def quiz_result_view(request, submission_id):
    submission = get_object_or_404(
        QuizSubmission.objects.select_related('quiz', 'user'),
        pk=submission_id,
        user=request.user
    )

    total_questions = submission.quiz.question_set.count()
    total_possible_marks = submission.quiz.question_set.aggregate(total_marks_sum=Sum('mark')).get('total_marks_sum') or 0

    score_percentage = (submission.score / total_possible_marks) * 100 if total_possible_marks else 0

    time_per_question = 0
    if submission.time_spent:
        time_seconds = submission.time_spent.total_seconds()
        time_per_question = time_seconds / total_questions if total_questions else 0

    leaderboard_position = None
    try:
        user_rank_obj = request.user.userrank
        leaderboard_position = user_rank_obj.rank
    except UserRank.DoesNotExist:
        leaderboard_position = None

    correct_question_ids = []
    user_answered_question_ids = set()
    user_selected_choices = set()

    answer_trackings = AnswerTracking.objects.filter(
        quiz_submission=submission,
        user=request.user
    ).select_related('question', 'selected_choice')

    for track_entry in answer_trackings:
        question_id = track_entry.question.id
        user_answered_question_ids.add(question_id)
        if track_entry.selected_choice:
            user_selected_choices.add(track_entry.selected_choice.id)
        if track_entry.is_correct:
            correct_question_ids.append(question_id)

    all_quiz_question_ids = set(Question.objects.filter(quiz=submission.quiz).values_list('id', flat=True))
    skipped_question_ids = list(all_quiz_question_ids - user_answered_question_ids)

    # --- Backend resolution for animation delay ---
    questions_with_delays = []
    for i, question in enumerate(submission.quiz.question_set.all()):
        # Calculate the delay here
        animation_delay = (i + 1) * 0.1 # i is 0-indexed, so (i+1) starts from 1
        question.animation_delay = animation_delay # Dynamically add attribute
        questions_with_delays.append(question)
    # --- End backend resolution ---


    context = {
        'submission': submission,
        'formatted_duration': format_duration(submission.time_spent),
        'score_percentage': round(score_percentage, 1),
        'total_questions': total_questions,
        'total_possible_marks': total_possible_marks,
        'percentage_score': round(score_percentage, 1), # Assuming this is the same as score_percentage
        'time_per_question': round(time_per_question, 1),
        'leaderboard_position': leaderboard_position,
        'quiz': submission.quiz,

        'correct_question_ids': correct_question_ids,
        'user_answered_question_ids': list(user_answered_question_ids),
        'user_selected_choices': list(user_selected_choices),
        'skipped_question_ids': skipped_question_ids,
        'questions_with_delays': questions_with_delays, # Pass the new list of questions
    }
    return render(request, 'quiz-result.html', context)


from django.shortcuts import render, redirect
from .models import Category, QuizSubmission
from django.db.models import Prefetch

from django.db.models import Avg, Count
from .models import QuizSubmission, Category, Question

from django.shortcuts import render, redirect
from .models import Category, QuizSubmission, Question
from django.db.models import Avg, Count
from collections import defaultdict

from django.db.models import Avg, Count
from .models import QuizSubmission, Category, Question, Quiz

from django.shortcuts import render, redirect
from django.db.models import Avg, Count, F, Q, FloatField, ExpressionWrapper, IntegerField, Case, When
from .models import QuizSubmission, Question, Quiz, Category
from account.models import Student
from collections import defaultdict

# quiz_app/views.py

from django.shortcuts import render, redirect
from django.db.models import Avg, Count
from collections import defaultdict

# Import your models
from .models import QuizSubmission, Question, Category, Quiz, AnswerTracking

# Import the utility function
from .utils import get_hardest_topics, format_duration

def user_dashboard_view(request):
    user = request.user
    if not user.is_authenticated:
        return redirect('login')

    # Get all submissions
    submissions = QuizSubmission.objects.filter(user=user).select_related('quiz__category')
    total_exams = submissions.count()
    average_score = submissions.aggregate(avg_score=Avg('score'))['avg_score'] or 0

    # Get categories from attempted quizzes
    categories = Category.objects.filter(quiz__in=submissions.values_list('quiz', flat=True)).distinct()

    # Difficulty pie chart
    difficulty_counts = submissions.values('quiz__difficulty').annotate(count=Count('id'))
    difficulty_labels = [entry['quiz__difficulty'] for entry in difficulty_counts]
    difficulty_data = [entry['count'] for entry in difficulty_counts]

    # --- Identify Hardest Topics (Using the utility function) ---
    # Call the function to get the hardest topics for the current user
    # You can adjust the 'limit' as needed, e.g., limit=5 for top 5
    hardest_topics_for_user = get_hardest_topics(user=user, limit=3)
    print(hardest_topics_for_user)
    # --- Suggested Quizzes based on Hardest Topics ---
    hardest_theme_names = [t['theme'] for t in hardest_topics_for_user]
    
    print(hardest_theme_names)

    suggested_quizzes = Quiz.objects.filter(
        question__question_theme__in=hardest_theme_names
    ).distinct().order_by('?')[:6] # Order randomly, or by creation date, avg_score, etc.

    # Fallback to popular quizzes if no weak-theme-based suggestions were found
    if not suggested_quizzes.exists():
        suggested_quizzes = Quiz.objects.annotate(num_attempts=Count('quizsubmission')).order_by('-num_attempts')[:6]

    context = {
        'categories': categories,
        'submissions': submissions[:5],  # recent submissions
        'total_exams': total_exams,
        'average_score': round(average_score, 1),
        'difficulty_labels': difficulty_labels,
        'difficulty_data': difficulty_data,
        'hardest_topics_for_user': hardest_topics_for_user, # Pass the result to the template
        'suggested_quizzes': suggested_quizzes,
    }

    return render(request, 'user_dashboard.html', context)



def filter_quiz_results(request, category_id):
    user = request.user
    submissions = QuizSubmission.objects.filter(
        user=user,
        quiz__category_id=category_id
    ).select_related('quiz')

    context = {
        'submissions': submissions,
    }
    return render(request, 'partials/_quiz_result_list.html', context)

from .filters import QuizSubmissionFilter  # Add this import at the top
from django.core.paginator import Paginator

# quiz/views.py (or wherever your quiz history view is)
from django.shortcuts import render, redirect
from django.db.models import Sum # Make sure to import Sum!
from django.core.paginator import Paginator # Make sure Paginator is imported
from .models import QuizSubmission, Quiz, Question # Ensure Quiz and Question are imported
from .filters import QuizSubmissionFilter # Ensure your filter is imported

from django.shortcuts import render, redirect
from django.db.models import Sum # Make sure Sum is imported if you're using it
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
#                                                            ^
#                                                            Notice the change here
# Assuming QuizSubmission and QuizSubmissionFilter are defined in your models.py or filters.py
# from .models import QuizSubmission
# from .filters import QuizSubmissionFilter # Or wherever your filter is defined

import math # Still keep if you use it elsewhere, otherwise it can be removed
import datetime # Import datetime to work with timedelta objects

# ... (other imports)
from django.shortcuts import render, redirect
from django.db.models import Sum
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
# from .models import QuizSubmission
# from .filters import QuizSubmissionFilter

import math
import datetime

# ... (other imports)
from django.shortcuts import render, redirect
from django.db.models import Sum
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
# from .models import QuizSubmission
# from .filters import QuizSubmissionFilter

def quiz_history_view(request):
    user = request.user
    if not user.is_authenticated:
        return redirect('login')

    submissions_base_qs = QuizSubmission.objects.filter(user=user).select_related('quiz', 'quiz__category').order_by('-submitted_at')

    quiz_filter = QuizSubmissionFilter(request.GET, queryset=submissions_base_qs)
    filtered_submissions_qs = quiz_filter.qs

    processed_submissions = []
    for submission in filtered_submissions_qs:
        # Calculate total_possible_marks
        total_marks_aggregation = submission.quiz.question_set.aggregate(total_marks_sum=Sum('mark'))
        submission.total_possible_marks = total_marks_aggregation.get('total_marks_sum') or 0

        # Calculate score_percentage
        if submission.total_possible_marks > 0:
            submission.score_percentage = (submission.score / submission.total_possible_marks) * 100
        else:
            submission.score_percentage = 0

        # Determine if the score is successful (e.g., >= 70%)
        submission.is_successful_score = (submission.score_percentage >= 70)

        # --- REVISED CODE FOR TIME SPENT FORMATTING ---
        if submission.time_spent and isinstance(submission.time_spent, datetime.timedelta):
            total_seconds = int(submission.time_spent.total_seconds()) # Get total seconds as an integer

            if total_seconds >= 3600: # If time is 1 hour (3600 seconds) or more
                hours = total_seconds // 3600
                remaining_seconds_after_hours = total_seconds % 3600
                minutes = remaining_seconds_after_hours // 60
                
                # Format: "X hours Y mins"
                submission.formatted_time_spent = f"{hours} hour{'s' if hours != 1 else ''} {minutes} min{'s' if minutes != 1 else ''}"
            elif total_seconds > 0: # If time is less than 1 hour but more than 0 seconds
                minutes = total_seconds // 60
                seconds = total_seconds % 60
                
                # Format: "X mins Y secs"
                submission.formatted_time_spent = f"{minutes} min{'s' if minutes != 1 else ''} {seconds} sec{'s' if seconds != 1 else ''}"
            else: # If time is 0 seconds
                submission.formatted_time_spent = "0 mins"
        else:
            submission.formatted_time_spent = "0 mins" # Default if time_spent is None or not a timedelta
        # --- END REVISED CODE ---

        processed_submissions.append(submission)

    paginator = Paginator(processed_submissions, 10)
    page_number = request.GET.get('page')
    try:
        page_obj = paginator.page(page_number)
    except PageNotAnInteger:
        page_obj = paginator.page(1)
    except EmptyPage:
        page_obj = paginator.page(paginator.num_pages)

    context = {
        'submissions': page_obj,
        'filter': quiz_filter,
        'submissions_count': filtered_submissions_qs.count()
    }
    return render(request, 'quiz_history.html', context)


import json
from datetime import timedelta
import calendar
from collections import defaultdict
from django.db.models import Sum, Count, Avg, F, Q, FloatField, ExpressionWrapper, IntegerField, Case, When
from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model
from django.utils.timezone import localdate, now
from django.db import models
from django.db.models.functions import Coalesce 

# IMPORTANT: Ensure these models are correctly imported from your app's models.py
from .models import QuizSubmission, Category, Quiz, Question, UserRank, AnswerTracking 

User = get_user_model() 

@login_required
def stats_page(request, user_pk):
    target_user = get_object_or_404(User, pk=user_pk)

    if target_user != request.user and not request.user.is_staff:
        return render(request, "403.html", status=403) 

    categories = Category.objects.all()
    
    active_category = None
    category_id = request.GET.get('category')
    if category_id:
        active_category = get_object_or_404(Category, id=category_id)
        base_submissions = QuizSubmission.objects.filter(user=target_user, quiz__category=active_category)
    else:
        base_submissions = QuizSubmission.objects.filter(user=target_user)

    submissions = base_submissions.select_related('quiz') 
    user_rank = UserRank.objects.filter(user=target_user).first()

    # --- Basic Stats ---
    total_quizzes = submissions.count()
    avg_score = submissions.aggregate(avg=Avg('score'))['avg'] or 0
    avg_time = submissions.aggregate(avg=Avg('time_spent'))['avg']
    avg_time_minutes = avg_time.total_seconds() / 60 if avg_time else 0

    # --- Accuracy Calculation ---
    user_answered_questions = AnswerTracking.objects.filter(quiz_submission__user=target_user)
    if active_category:
        user_answered_questions = user_answered_questions.filter(question__quiz__category=active_category)
    
    total_answers_tracked = user_answered_questions.count()
    correct_answers_tracked = user_answered_questions.filter(is_correct=True).count()
    accuracy = (correct_answers_tracked / total_answers_tracked) * 100 if total_answers_tracked > 0 else 0

    # --- MONTHLY PERFORMANCE CALCULATION ---
    today_date = localdate() 
    monthly_data_for_chart = [] 
    
    for i in range(11, -1, -1): 
        target_date = today_date - timedelta(days=30 * i) 
        
        month_start_date = target_date.replace(day=1)
        last_day_of_month = calendar.monthrange(month_start_date.year, month_start_date.month)[1]
        month_end_date = month_start_date.replace(day=last_day_of_month)

        month_sum = submissions.filter(
            submitted_at__date__gte=month_start_date,
            submitted_at__date__lte=month_end_date
        ).aggregate(
            total_score=Sum('score')
        )['total_score'] or 0
        
        monthly_data_for_chart.append({
            'month_label': month_start_date.strftime('%b %Y'), 
            'score': month_sum
        })
    
    chart_labels = [entry['month_label'] for entry in monthly_data_for_chart]
    chart_data = [entry['score'] for entry in monthly_data_for_chart]

    max_monthly_chart_score = max(chart_data) if chart_data else 0
    if max_monthly_chart_score == 0:
        chart_max_score = 100 
    else:
        chart_max_score = max_monthly_chart_score * 1.1 

    # --- Monthly Comparison for Score Summary ---
    current_month_start = today_date.replace(day=1)
    previous_month_end = current_month_start - timedelta(days=1)
    previous_month_start = previous_month_end.replace(day=1)
    
    this_month_score = submissions.filter(
        submitted_at__date__gte=current_month_start
    ).aggregate(total=Sum('score'))['total'] or 0
    
    last_month_score = submissions.filter(
        submitted_at__date__gte=previous_month_start,
        submitted_at__date__lt=current_month_start 
    ).aggregate(total=Sum('score'))['total'] or 0

    max_comparison_score = max(this_month_score, last_month_score, 1) 
    this_month_percentage = (this_month_score / max_comparison_score) * 100
    last_month_percentage = (last_month_score / max_comparison_score) * 100

    # --- Top Performing Quizzes ---
    top_quizzes = Quiz.objects.filter(quizsubmission__user=target_user)
    if active_category:
        top_quizzes = top_quizzes.filter(category=active_category)
    top_quizzes = top_quizzes.annotate(
        avg_score_val=Avg('quizsubmission__score', filter=models.Q(quizsubmission__user=target_user)), 
        attempt_count=Count('quizsubmission', filter=models.Q(quizsubmission__user=target_user)) 
    ).order_by('-avg_score_val')[:5]

    # --- Areas Needing Improvement (Top wrong themes) ---
    incorrect_answers_qs = AnswerTracking.objects.filter(
        quiz_submission__user=target_user,
        is_correct=False
    )
    if active_category:
        incorrect_answers_qs = incorrect_answers_qs.filter(question__quiz__category=active_category)

    top_wrong_themes = incorrect_answers_qs.values('question__question_theme').annotate(
        error_count=Count('id')
    ).order_by('-error_count')[:5]

    # Convert to a list of theme names for filtering
    top_wrong_theme_names = [item['question__question_theme'] for item in top_wrong_themes if item['question__question_theme']]
    
    # Pass this to the context for display
    top_wrong_themes_display = [(item['question__question_theme'], item['error_count']) for item in top_wrong_themes if item['question__question_theme']]

    # --- Suggested Quizzes based on Top Wrong Themes ---
    suggested_quizzes = []
    if top_wrong_theme_names:
        # Find quizzes that contain questions from these "wrong" themes
        suggested_quizzes = Quiz.objects.filter(
            question__question_theme__in=top_wrong_theme_names
        ).distinct().order_by('?')[:6] # Order randomly for variety

    # Fallback if no quizzes are found based on weak themes or if there are no weak themes yet
    if not suggested_quizzes:
        # Suggest popular quizzes or recently added ones
        # For popularity, let's count unique submissions
        suggested_quizzes = Quiz.objects.annotate(
            num_attempts=Count('quizsubmission', distinct=True)
        ).order_by('-num_attempts', '-created_at')[:6] # Fallback to popular or recent

    # --- Best Performing Areas (Top correct themes) ---
    correct_answers_qs = AnswerTracking.objects.filter(
        quiz_submission__user=target_user,
        is_correct=True
    )
    if active_category:
        correct_answers_qs = correct_answers_qs.filter(question__quiz__category=active_category)

    top_correct_themes = correct_answers_qs.values('question__question_theme').annotate(
        correct_count=Count('id')
    ).order_by('-correct_count')[:5] 

    top_correct_themes = [(item['question__question_theme'], item['correct_count']) for item in top_correct_themes if item['question__question_theme']]

    # --- Average Time Spent by Question Topic (Inferring from QuizSubmission time) ---
    theme_time_data = defaultdict(lambda: {'total_time_seconds': 0, 'question_count': 0})

    relevant_submissions = QuizSubmission.objects.filter(user=target_user)
    if active_category:
        relevant_submissions = relevant_submissions.filter(quiz__category=active_category)

    relevant_submissions = relevant_submissions.annotate(
        num_questions_in_quiz=Count('quiz__question', distinct=True) 
    ).filter(num_questions_in_quiz__gt=0, time_spent__isnull=False) 
    
    for sub in relevant_submissions:
        if sub.time_spent and sub.num_questions_in_quiz > 0:
            time_per_q_seconds = sub.time_spent.total_seconds() / sub.num_questions_in_quiz

            questions_in_this_quiz = Question.objects.filter(quiz=sub.quiz)
            
            if active_category:
                questions_in_this_quiz = questions_in_this_quiz.filter(quiz__category=active_category)

            for q in questions_in_this_quiz:
                if q.question_theme:
                    theme_time_data[q.question_theme]['total_time_seconds'] += time_per_q_seconds
                    theme_time_data[q.question_theme]['question_count'] += 1

    # Format and store all average times
    all_avg_time_per_theme = []
    for theme, data in theme_time_data.items():
        if data['question_count'] > 0:
            avg_seconds = data['total_time_seconds'] / data['question_count']
            all_avg_time_per_theme.append({
                'theme': theme,
                'avg_time_seconds': round(avg_seconds, 2),
                'avg_time_minutes': round(avg_seconds / 60, 2)
            })

    # --- Split into Longest and Quickest ---
    # Sort for longest (descending)
    top_5_longest_time_themes = sorted(all_avg_time_per_theme, 
                                       key=lambda x: x['avg_time_seconds'], 
                                       reverse=True)[:5]

    # Sort for quickest (ascending)
    top_5_quickest_time_themes = sorted(all_avg_time_per_theme, 
                                        key=lambda x: x['avg_time_seconds'])[:5]

    total_score = submissions.aggregate(total=Sum('score'))['total'] or 0

    context = {
        'target_user': target_user,
        'categories': categories,
        'active_category': active_category,
        
        'total_quizzes': total_quizzes,
        'avg_score': round(avg_score, 2),
        'avg_time_minutes': round(avg_time_minutes, 2),
        'accuracy': round(accuracy, 2),
        'total_score': total_score,

        'this_month_score': this_month_score,
        'last_month_score': last_month_score,
        'max_monthly_score': max_comparison_score, 
        'this_month_percentage': this_month_percentage,
        'last_month_percentage': last_month_percentage,
        
        'top_quizzes': top_quizzes, 
        'top_wrong_themes': top_wrong_themes_display, # Use the display-ready list
        'top_correct_themes': top_correct_themes, 
        
        # New context variables for time statistics
        'top_5_longest_time_themes': top_5_longest_time_themes,
        'top_5_quickest_time_themes': top_5_quickest_time_themes,
        
        'chart_labels': json.dumps(chart_labels),
        'chart_data': json.dumps(chart_data),
        'chart_max_score': chart_max_score, 

        # Add suggested quizzes to context
        'suggested_quizzes': suggested_quizzes, 
    }

    return render(request, 'stats_page.html', context)