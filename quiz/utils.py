# In your views.py or quiz/utils.py
from django.db.models import Sum, F, Case, When, FloatField, Avg, Count
from django.db.models.functions import Coalesce

# Import your models
from .models import QuizSubmission, Question, Category, Quiz, AnswerTracking

def get_hardest_topics(user, limit=3):
    """
    Calculates the hardest topics for a *specific user* based on their accuracy
    on questions within each theme, derived from AnswerTracking records.

    Args:
        user (User): The user for whom to calculate hardest topics. This argument is now required.
        limit (int, optional): The number of top hardest topics to return. Defaults to 3.

    Returns:
        list of dict: A list of dictionaries, each containing 'theme' and 'accuracy'.
                      Example: [{'theme': 'Algebra', 'accuracy': 30.5}, ...]
    """

    if not user:
        raise ValueError("A user must be provided to get user-specific hardest topics.")

    # Get all AnswerTracking records for the given user
    user_answer_trackings = AnswerTracking.objects.filter(user=user)

    # Aggregate these answers by the question's theme
    topic_stats = user_answer_trackings.values('question__question_theme').annotate(
        total_attempts_on_theme=Count('id'), # Count of unique AnswerTracking records for this user and theme
        total_correct_on_theme=Sum(Case(
            When(is_correct=True, then=1),
            default=0,
            output_field=FloatField()
        )),
        # Calculate accuracy for the theme for this user
        accuracy=Case(
            When(total_attempts_on_theme__gt=0, then=F('total_correct_on_theme') * 100.0 / F('total_attempts_on_theme')),
            default=0.0,
            output_field=FloatField()
        )
    ).order_by('accuracy') # Order by accuracy ascending to get hardest (lowest accuracy) first

    # Filter out topics with no attempts or where theme is null/empty
    topic_stats = topic_stats.exclude(total_attempts_on_theme=0) \
                             .exclude(question__question_theme__isnull=True) \
                             .exclude(question__question_theme='')

    # Limit the results
    hardest_topics = list(topic_stats[:limit])

    # Rename keys to be more descriptive and format accuracy
    formatted_topics = []
    for topic in hardest_topics:
        formatted_topics.append({
            'theme': topic['question__question_theme'], # Note the double underscore for related field
            'accuracy': round(topic['accuracy'], 2) if topic['accuracy'] is not None else 0.00
        })

    return formatted_topics


def process_quiz_submission(request, quiz_id):
    # ... (your existing quiz submission processing logic)
    quiz = Quiz.objects.get(id=quiz_id)
    user = request.user
    score = 0
    # Create the QuizSubmission instance
    submission = QuizSubmission.objects.create(
        user=user,
        quiz=quiz,
        score=0, # Initialize score, update later
        time_started=request.session.get(f'quiz_{quiz.id}_start_time') # Assuming you track start time
    )

    question_breakdown_data = {} # To populate QuizSubmission.question_breakdown

    for question in quiz.question_set.all(): # Loop through questions in the quiz
        user_answer_choice_id = request.POST.get(f'question_{question.id}') # Get user's selected choice

        is_correct = False
        if user_answer_choice_id:
            try:
                selected_choice = Choice.objects.get(id=user_answer_choice_id)
                is_correct = selected_choice.is_correct
                if is_correct:
                    score += question.mark # Add marks to score if correct
            except Choice.DoesNotExist:
                selected_choice = None # Handle cases where choice ID is invalid

        # Save an AnswerTracking instance for each question
        AnswerTracking.objects.create(
            user=user,
            question=question,
            quiz_submission=submission, # Link to the current QuizSubmission
            selected_choice=selected_choice,
            is_correct=is_correct,
            # time_spent_on_question=... # Populate if you track this
        )

        # Also populate question_breakdown for QuizSubmission
        question_breakdown_data[str(question.id)] = {
            "selected": selected_choice.text if selected_choice else None,
            "correct": is_correct,
            # "time_spent": ... # Add if tracked
        }

    submission.score = score
    submission.question_breakdown = question_breakdown_data
    submission.time_completed = timezone.now() # Assuming timezone.now() imported
    submission.save() # This save triggers the QuizSubmission post_save signal

    # ... (redirect or render results)


# Dummy format_duration function if you don't have it yet
def format_duration(duration):
    if duration is None:
        return "N/A"
    total_seconds = int(duration.total_seconds())
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60

    parts = []
    if hours > 0:
        parts.append(f"{hours}h")
    if minutes > 0:
        parts.append(f"{minutes}m")
    if seconds > 0 or not parts:
        parts.append(f"{seconds}s")
    return " ".join(parts)