from django.db.models.signals import post_save
from django.dispatch import receiver
from django.db.models import F # Import F for atomic updates
from .models import QuizSubmission, Question, AnswerTracking, UserRank


@receiver(post_save, sender=QuizSubmission)
def update_quiz_stats(sender, instance, created, **kwargs):
    """Updates quiz statistics after each submission"""
    # Assuming these methods exist and function correctly in your Quiz model
    # If they cause errors, it means your Quiz model needs those methods defined.
    instance.quiz.update_stats()
    instance.quiz.update_completion_rate()


@receiver(post_save, sender=AnswerTracking)
def update_question_and_quiz_difficulty(sender, instance, created, **kwargs):
    """
    Updates question performance metrics and triggers recalculation of
    Question mark and overall Quiz difficulty after each answer tracking.
    """
    if created:
        question = instance.question

        # 1. Update question attempt counts atomically
        # Using F() expressions for atomic updates to prevent race conditions
        # This saves the counts to the DB immediately
        question.times_attempted = F('times_attempted') + 1
        if instance.is_correct:
            question.times_correct = F('times_correct') + 1
        else:
            question.times_incorrect = F('times_incorrect') + 1
        question.save(update_fields=['times_attempted', 'times_correct', 'times_incorrect'])

        # 2. Reload the question to get the atomically updated counts
        # This is crucial because F() updates are not immediately reflected in the instance's Python attributes.
        question.refresh_from_db()

        # 3. Recalculate Question's mark based on new stats
        # question.calculate_difficulty() updates question.mark in memory and returns a string difficulty.
        old_mark = question.mark # Store current mark to check if it changed
        _ = question.calculate_difficulty() # Call the method; we don't store its string return value on Question

        if old_mark != question.mark:
            # Only save the mark if the calculation actually changed its value
            question.save(update_fields=['mark']) # Save the updated mark to the database

        # 4. Trigger Quiz difficulty recalculation
        # The Quiz's overall difficulty depends on its questions' characteristics.
        # Any change in a question's performance (and thus its mark/perceived difficulty)
        # should prompt the Quiz to recalculate its own difficulty.
        try:
            quiz = question.quiz # Get the related Quiz
            quiz.difficulty = quiz.calculate_difficulty() # Calculate Quiz's overall difficulty
            quiz.save(update_fields=['difficulty']) # Save only the difficulty field
        except Exception as e:
            # Handle cases where the related quiz might no longer exist or other errors.
            print(f"Error updating quiz difficulty for Quiz ID {question.quiz_id}: {e}")


@receiver(post_save, sender=QuizSubmission)
def update_user_rank(sender, instance, created, **kwargs):
    """Updates leaderboard when new submissions are made"""
    if created:
        UserRank.update_all_ranks()