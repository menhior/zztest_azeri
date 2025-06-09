from django.db import models
import pandas as pd
from django.contrib.auth.models import User
from account.models import Student
from django.db.models import Sum
from django.db.models.signals import post_save
from django.dispatch import receiver
from smart_open import open
import io
from io import BytesIO





# Create your models here.
class Category(models.Model):
    name = models.CharField(max_length=15)

    class Meta:
        verbose_name_plural = 'Categories'

    def __str__(self):
        return self.name

class Quiz(models.Model):
    DIFFICULTY_CHOICES = (
        ('Very Easy', 'Very Easy'),
        ('Easy', 'Easy'),
        ('Medium', 'Medium'),
        ('Hard', 'Hard'),
        ('Very Hard', 'Very Hard')
    )
    
    title = models.CharField(max_length=255, null=True, blank=True)
    description = models.TextField(null=True, blank=True)
    grade = models.PositiveIntegerField(blank=True, null=True)
    category = models.ForeignKey(Category, on_delete=models.CASCADE)
    quiz_file = models.FileField(upload_to='quiz/', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)

    difficulty = models.CharField(max_length=20, choices=DIFFICULTY_CHOICES, default='Medium')

    # Add these fields
    avg_score = models.FloatField(null=True, blank=True)
    completion_rate = models.FloatField(null=True, blank=True)
    avg_time_spent = models.DurationField(null=True, blank=True)
    discrimination_index = models.FloatField(null=True, blank=True)
    
    def calculate_difficulty(self):
        """Auto-calculates based on question difficulties"""
        difficulties = {
            'Very Easy': 0,
            'Easy': 0,
            'Medium': 0,
            'Hard': 0,
            'Very Hard': 0
        }
        for q in self.question_set.all():
            difficulties[q.calculate_difficulty()] += 1
        return max(difficulties, key=difficulties.get)
    
    def update_completion_rate(self):
        total_users = User.objects.count()
        completed = self.quizsubmission_set.count()
        self.completion_rate = (completed / total_users) * 100 if total_users else 0
        self.save()
    
    def update_stats(self):
        submissions = self.quizsubmission_set.all()
        if submissions.exists():
            self.avg_score = submissions.aggregate(avg=Avg('score'))['avg']
            self.avg_time_spent = submissions.aggregate(avg=Avg('time_spent'))['avg']
            self.save()

    class Meta:
        verbose_name_plural = 'Quizzes'

    def __str__(self):
        return self.title

    # call the function on quiz save
    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if self.quiz_file:
            self.process_quiz_excel()

    def process_quiz_excel(self):
        # Read the uploaded file directly from memory
        file_content = self.quiz_file.read()
        
        # Use pandas to read the Excel data
        df = pd.read_excel(BytesIO(file_content))
        
        # Process each row (same as before)
        for index, row in df.iterrows():
            # Create or get the question with solution explanation
            question, _ = Question.objects.get_or_create(
                quiz=self,
                text=row['Question'],
                question_theme=row.get('Theme', ''),
                mark=row.get('Marks', 1),
                solution_explanation=row.get('Solution', '')
            )

            # Create all five choices
            Choice.objects.get_or_create(
                question=question,
                text=row['A'],
                is_correct=(row['Answer'] == 'A')
            )
            Choice.objects.get_or_create(
                question=question,
                text=row['B'],
                is_correct=(row['Answer'] == 'B')
            )
            Choice.objects.get_or_create(
                question=question,
                text=row['C'],
                is_correct=(row['Answer'] == 'C')
            )
            Choice.objects.get_or_create(
                question=question,
                text=row['D'],
                is_correct=(row['Answer'] == 'D')
            )
            Choice.objects.get_or_create(
                question=question,
                text=row['E'],
                is_correct=(row['Answer'] == 'E')
            )
            
class Question(models.Model):
    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE)
    question_theme = models.CharField(max_length=200, null=True, blank=True) 
    text = models.TextField(null=True, blank=True)
    mark = models.PositiveIntegerField(default=10)
    solution_explanation = models.CharField(max_length=1000, null=True, blank=True)


    # Add these fields for performance tracking
    times_attempted = models.PositiveIntegerField(default=0)
    times_correct = models.PositiveIntegerField(default=0)
    times_incorrect = models.PositiveIntegerField(default=0)
    avg_time_spent = models.FloatField(null=True, blank=True)  # in seconds
    discrimination_index = models.FloatField(null=True, blank=True)  # (-1 to 1)
    last_updated = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return self.text[:50]
    
    def calculate_difficulty(self):
        if self.times_attempted == 0:
            return 'Medium'
        ratio = self.times_correct / self.times_attempted
        if ratio >= 0.8: 
            self.mark = 2
            return 'Very Easy'
        elif ratio >= 0.6: 
            self.mark = 5
            return 'Easy'
        elif ratio >= 0.4: 
            self.mark = 10
            return 'Medium'
        elif ratio >= 0.2: 
            self.mark = 15
            return 'Hard'
        else: 
            self.mark = 25
            return 'Very Hard'

    def calculate_discrimination(self):
        """Item Discrimination Index (27% rule)"""
        top = self.quiz.top_performers()[:int(self.quiz.submissions.count()*0.27)]
        bottom = self.quiz.bottom_performers()[:int(self.quiz.submissions.count()*0.27)]
        
        top_correct = self.answer_set.filter(user__in=top, is_correct=True).count()
        bottom_correct = self.answer_set.filter(user__in=bottom, is_correct=True).count()
        
        self.discrimination_index = (top_correct/len(top)) - (bottom_correct/len(bottom)) if top and bottom else None
        self.save()

class Choice(models.Model):
    question = models.ForeignKey(Question, on_delete=models.CASCADE)
    text = models.CharField(max_length=255, null=True, blank=True)
    is_correct = models.BooleanField(default=False)
    

    def __str__(self):
        return f"{self.question.text[:50]}, {self.text[:20]}"

class QuizSubmission(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE)
    score = models.IntegerField()
    submitted_at = models.DateTimeField(auto_now_add=True)
 
    # Add these fields
    time_started = models.DateTimeField(null=True, blank=True)
    time_completed = models.DateTimeField(null=True, blank=True)
    time_spent = models.DurationField(null=True, blank=True)
    question_breakdown = models.JSONField(default=dict)  # Stores per-question data
    
    
    class Meta:
        ordering = ['-submitted_at']
        indexes = [
            models.Index(fields=['user', 'quiz']),
        ]

    @property
    def accuracy_rate(self):
        try:
            # Get the total possible marks for the quiz associated with this submission
            # Check if there are questions to avoid ZeroDivisionError
            if self.quiz.question_set.exists():
                total_possible_marks_agg = self.quiz.question_set.aggregate(total_sum=Sum('mark'))
                total_possible_marks = total_possible_marks_agg.get('total_sum')
                
                if total_possible_marks is not None and total_possible_marks > 0:
                    accuracy = (self.score / total_possible_marks) * 100
                    return round(accuracy, 2) # Round to 2 decimal places
                else:
                    return 0.00 # If total possible marks is 0 or None, accuracy is 0
            else:
                return 0.00 # If no questions in the quiz, accuracy is 0
        except Exception: # Catch broader exceptions for robustness
            # You might want to log this exception for debugging
            return 0.00 # Return 0.00 or None if an error occurs
        
    def save(self, *args, **kwargs):
        if self.time_started and self.time_completed:
            self.time_spent = self.time_completed - self.time_started
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.user}, {self.quiz.title}"

class UserRank(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    rank = models.IntegerField(null=True, blank=True)
    total_score = models.IntegerField(null=True, blank=True)
    
    # Add these fields
    weekly_progress = models.IntegerField(default=0)
    topic_mastery = models.JSONField(default=dict)
    accuracy_rate = models.FloatField(null=True, blank=True)
    last_updated = models.DateTimeField(auto_now=True, null=True, blank=True)
    streak_count = models.PositiveIntegerField(default=0)
    last_active = models.DateField(auto_now_add=True, null=True, blank=True)

    class Meta:
        verbose_name = "User Ranking"
        verbose_name_plural = "User Rankings"
        ordering = ['rank']
        indexes = [
            models.Index(fields=['rank']),
            models.Index(fields=['total_score']),
        ]

    def __str__(self):
        return f"{self.user.username} (Rank #{self.rank})"

    def update_activity_streak(self):
        today = timezone.now().date()
        if self.last_active == today - timedelta(days=1):
            self.streak_count += 1
        elif self.last_active < today - timedelta(days=1):
            self.streak_count = 1
        self.last_active = today
        self.save()

    @classmethod
    def update_user_rank(cls, user):
        """Update rank for a specific user"""
        user_submissions = QuizSubmission.objects.filter(user=user)
        
        total_score = user_submissions.aggregate(
            total=Coalesce(Sum('score'), 0)
        )['total']
        
        accuracy = user_submissions.aggregate(
            acc=Coalesce(
                Sum(Case(
                    When(score__gt=0, then=1),
                    default=0,
                    output_field=FloatField()
                )) / Count('id') * 100,
                0
            )
        )['acc']
        
        week_ago = timezone.now() - timedelta(days=7)
        weekly_progress = user_submissions.filter(
            submitted_at__gte=week_ago
        ).aggregate(
            total=Coalesce(Sum('score'), 0)
        )['total']
        
        user_rank, _ = cls.objects.get_or_create(user=user)
        user_rank.total_score = total_score
        user_rank.weekly_progress = weekly_progress
        user_rank.accuracy_rate = accuracy
        user_rank.save()

    @classmethod
    def update_all_ranks(cls):
        """Full leaderboard recalculation"""
        user_data = QuizSubmission.objects.values('user').annotate(
            total_score=Coalesce(Sum('score'), 0),
            total_attempts=Count('id'),
            correct_attempts=Sum(Case(
                When(score__gt=0, then=1),
                default=0,
                output_field=FloatField()
            ))
        ).order_by('-total_score')

        week_ago = timezone.now() - timedelta(days=7)
        weekly_data = QuizSubmission.objects.filter(
            submitted_at__gte=week_ago
        ).values('user').annotate(
            weekly_score=Coalesce(Sum('score'), 0)
        )
        weekly_scores = {item['user']: item['weekly_score'] for item in weekly_data}

        rank = 1
        for entry in user_data:
            user_id = entry['user']
            user_rank, _ = cls.objects.get_or_create(user_id=user_id)
            user_rank.rank = rank
            user_rank.total_score = entry['total_score']
            user_rank.weekly_progress = weekly_scores.get(user_id, 0)
            
            if entry['total_attempts'] > 0:
                user_rank.accuracy_rate = (
                    entry['correct_attempts'] / entry['total_attempts'] * 100
                )
            
            user_rank.update_activity_streak()
            user_rank.save()
            rank += 1

    @classmethod
    def get_leaderboard(cls, limit=10):
        return cls.objects.select_related('user').order_by('rank')[:limit]


    def update_leaderboard():
        # Count the sum of scores for all users
        user_scores = (QuizSubmission.objects.values('user').annotate(total_score=Sum('score')).order_by('-total_score'))

        # Update rank based on the sorted list
        rank = 1
        for entry in user_scores:
            user_id = entry['user']
            total_score = entry['total_score']

            user_rank, created = UserRank.objects.get_or_create(user_id=user_id)
            user_rank.rank = rank
            user_rank.total_score = total_score
            user_rank.save()

            rank += 1
        
        
class StudentProgress(models.Model):
    user = models.OneToOneField(Student, on_delete=models.CASCADE)
    streak_days = models.PositiveIntegerField(default=0)
    last_active = models.DateField(auto_now=True, null=True, blank=True)
    mastery_levels = models.JSONField(default=dict)  # Tracks topic mastery
    # Example: {"Algebra": 0.75, "Geometry": 0.92}
    
    def update_streak(self):
        today = timezone.now().date()
        if self.last_active == today - timedelta(days=1):
            self.streak_days += 1
        elif self.last_active < today - timedelta(days=1):
            self.streak_days = 1
        self.last_active = today
        self.save()
        
        
class AnswerTracking(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    question = models.ForeignKey(Question, on_delete=models.CASCADE)
    quiz_submission = models.ForeignKey(QuizSubmission, on_delete=models.CASCADE, null=True, blank=True) # Link to the submission if desired
    selected_choice = models.ForeignKey('Choice', on_delete=models.SET_NULL, null=True, blank=True)
    is_correct = models.BooleanField()
    attempted_at = models.DateTimeField(auto_now_add=True)
    # time_spent_on_question = models.DurationField(null=True, blank=True) # Optional: if you track this per question

    class Meta:
        verbose_name_plural = 'Answer Trackings'
        unique_together = ('user', 'question', 'quiz_submission') # Prevent duplicate tracking if needed
        ordering = ['-attempted_at']

    def __str__(self):
        return f"{self.user.username} - Q: {self.question.id} - Correct: {self.is_correct}"