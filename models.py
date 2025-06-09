from django.db import models

from django.contrib.auth.models import User

from phonenumber_field.modelfields import PhoneNumberField

from django.utils.text import slugify

class Student(models.Model): 
    user=models.OneToOneField(User,on_delete=models.CASCADE)
    profile_pic= models.ImageField(upload_to='profile_pic/Student/',null=True,blank=True)
    address = models.CharField(max_length=40)
    mobile = models.CharField(max_length=20,null=False)
    grade = models.PositiveIntegerField()
    date_created = models.DateTimeField(auto_now_add=True, null=True)
    device = models.CharField(max_length=200, null=True, blank=True)
   
   # Relationships with teachers and parents
    teachers = models.ManyToManyField('Teacher', through='StudentTeacherRelation', related_name='students')
    parents = models.ManyToManyField('Parent', through='StudentParentRelation', related_name='students')
   
    def has_purchased(self, exam):
        return Purchase.objects.filter(student=self, exam=exam).exists()
   
    @property 
    def get_name(self):
        return self.user.first_name+" "+self.user.last_name
    @property
    def get_instance(self):
        return self
    def __str__(self):
        return self.user.first_name



class Teacher(models.Model):
    user=models.OneToOneField(User,on_delete=models.CASCADE)
    profile_pic= models.ImageField(upload_to='profile_pic/Teacher/',null=True,blank=True)
    address = models.CharField(max_length=40)
    mobile = models.CharField(max_length=20,null=False)
    status= models.BooleanField(default=False)
    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    subjects = (
    ('Azerbaijani Language and Literature', 'Azerbaijani Language and Literature'),
    ('Mathematics', 'Mathematics'),
    ('Physics', 'Physics'),
    ('Chemistry', 'Chemistry'),
    ('Biology', 'Biology'),
    ('History of Azerbaijan', 'History of Azerbaijan'),
    ('Geography', 'Geography'),
    ('English Language', 'English Language'),
    ('Russian Language', 'Russian Language'),
    ('Computer Science', 'Computer Science'),
    ('Physical Education', 'Physical Education'),
    ('Fine Arts', 'Fine Arts'),
    ('Music', 'Music'),
    ('Civic Education', 'Civic Education'),
)
    subject = models.CharField(max_length=55, choices=subjects)

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
    subject = models.CharField(max_length=55, choices=Teacher.subjects) # Add subject field
    is_approved = models.BooleanField(default=False)
    request_date = models.DateTimeField(auto_now_add=True)  # Automatically set when the request is made
    approval_date = models.DateTimeField(null=True, blank=True)  # Set when the request is approved

    class Meta:
        unique_together = ('student', 'teacher', 'subject')

class Parent(models.Model):
    user=models.OneToOneField(User,on_delete=models.CASCADE)
    profile_pic= models.ImageField(upload_to='profile_pic/Teacher/',null=True,blank=True)
    address = models.CharField(max_length=40)
    mobile = models.CharField(max_length=20,null=False)
    status= models.BooleanField(default=False)
    student = models.ForeignKey(Student, on_delete=models.CASCADE)

    @property
    def get_name(self):
        return self.user.first_name+" "+self.user.last_name
    @property
    def get_instance(self):
        return self
    def __str__(self):
        return self.user.first_name


class StudentParentRelation(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    parent = models.ForeignKey(Parent, on_delete=models.CASCADE)
    is_approved = models.BooleanField(default=False)
    request_date = models.DateTimeField(auto_now_add=True)  # Automatically set when the request is made
    approval_date = models.DateTimeField(null=True, blank=True)  # Set when the request is approved


        

class Exam_Topic(models.Model):
    title = models.CharField(max_length= 20)

    @property
    def image_url(self):
        """Returns the URL to the topic's image"""
        return f'/static/exam_topics/{self.title.lower()}.jpg'

    def __str__(self):
        return self.title


class Exam(models.Model):
    exam_name = models.CharField(max_length=50)
    slug = models.SlugField(unique=True, blank=True, verbose_name="Slug")  # For SEO-friendly URLs
    exam_topic = models.ManyToManyField(Exam_Topic)
    image = models.ImageField(upload_to='images/', null=True, blank=True)
    description = models.CharField(max_length=500, null=True, blank=True)
    question_number = models.PositiveIntegerField()
    total_marks = models.PositiveIntegerField()
    passing_mark = models.PositiveIntegerField()
    time_limit = models.PositiveIntegerField()
    price = models.DecimalField(default = 0, max_digits=6, decimal_places=2, verbose_name="Price", null=True, blank=True)  # Better for currency

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.exam_name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.exam_name

    @property
    def get_comments(self):
        return self.comments.all().order_by('-timestamp')

    @property
    def imageURL(self):
        try:
            url = self.image.url
        except:
            url = ''
        return url

    @property
    def first_topic_image(self):
        """
        Returns the image URL of the first associated topic
        Returns empty string if no topics exist or if image is not available
        """
        first_topic = self.exam_topic.first()  # Get the first topic
        if first_topic:
            return first_topic.image_url  # Uses the image_url property from Exam_Topic
        return ''

    def get_absolute_url(self):
        return reverse('exam', kwargs={
            'pk': self.pk,
            })
    

class Order(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE) 
    date_bought = models.DateTimeField(auto_now_add=True)
    complete = models.BooleanField(default=False)
    transaction_id = models.CharField(max_length=100, null=True)

    def __str__(self):
        return str('Order Number # ' + str(self.id))

    @property
    def get_cart_total(self):
        orderitems = self.orderitem_set.all()
        total = sum([item.get_total for item in orderitems])
        return total

    @property
    def get_cart_items(self):
        return self.orderitem_set.count()
  
class OrderItem(models.Model):
    exam = models.ForeignKey('Exam', on_delete=models.SET_NULL, null=True,)
    order = models.ForeignKey('Order', on_delete=models.CASCADE,)
    date_added = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return str('Items of ' + str(self.order))
        """return str('Order Number # ' + str(self.order.id))"""

    @property
    def get_total(self):
        total = self.exam.price  
        return total

class Exam_Statistic(models.Model):
   exam = models.OneToOneField('Exam', on_delete=models.CASCADE, related_name='statistics')  # Connect to exam
   passing_rate = models.FloatField(null=True, blank=True)
   dif_cat = (('Very Easy','Very Easy'),('Easy','Easy'),('Medium','Medium'),('Hard','Hard'), ('Very Hard','Very Hard'))
   difficulty = models.CharField(max_length=20,choices=dif_cat)
   

   def __str__(self):
        return f"Statistics for {self.exam.exam_name}"

   def __str__(self):
        return self.exam_name

   def save(self, *args, **kwargs):
        #... (your existing save method code)

        # Calculate and update statistics
        self.calculate_difficulty()
        self.calculate_pass_rate()

   def calculate_difficulty(self):
        """Calculates the difficulty based on the percentage of correct answers."""
        results = self.result_set.all()
        if results.count() > 0:
            total_questions = self.question_number * results.count()
            total_correct_answers = sum(result.num_correct_answers for result in results)
            percentage_correct = (total_correct_answers / total_questions) * 100

            # Assign difficulty level based on percentage_correct
            if percentage_correct < self.passing_mark:  # Use passing_mark from exam
                difficulty_level = "Very Hard"
            elif percentage_correct < 70:
                difficulty_level = "Hard"
            elif percentage_correct < 80:
                difficulty_level = "Medium"
            elif percentage_correct < 90:  # Use percentage_correct here, not difficulty_level
                difficulty_level = "Easy"
            else:
                difficulty_level = "Very Easy"

            # Update or create exam_Statistics
            stats, created = Exam_Statistics.objects.get_or_create(exam=self)
            stats.difficulty = difficulty_level
            stats.save()
        else:
            # Handle cases with no results (e.g., set default difficulty)
            pass

   def calculate_pass_rate(self):
        """Calculates the pass rate of the test."""
        results = self.result_set.all()
        if results.count() > 0:
            passing_results = results.filter(score__gte=self.passing_mark)
            pass_rate = (passing_results.count() / results.count()) * 100

            # Update or create exam_Statistics
            stats, created = Exam_Statistics.objects.get_or_create(exam=self)
            stats.passing_rate = pass_rate
            stats.save()
        else:
            # Handle cases with no results (e.g., set pass_rate to 0)
            pass

    # Remember to call these methods whenever you want to update the difficulty and pass rate
    # For example, you could call them after creating a new Result or in a scheduled task

class Question(models.Model):
    DIFFICULTY_CHOICES = (
        ('Very Easy', 'Very Easy'),
        ('Easy', 'Easy'),
        ('Medium', 'Medium'),
        ('Hard', 'Hard'),
        ('Very Hard', 'Very Hard')
    )
    ANSWER_CHOICES = (
        ('1', '1'),
        ('2', '2'),
        ('3', '3'),
        ('4', '4'),
        ('5', '5')
    )

    exam = models.ManyToManyField('Exam', related_name='questions')
    question_theme = models.CharField(max_length=600)
    difficulty = models.CharField(max_length=20, choices=DIFFICULTY_CHOICES, default='Medium')
    marks = models.PositiveIntegerField()
    question = models.CharField(max_length=600)
    option1 = models.CharField(max_length=200)
    option2 = models.CharField(max_length=200)
    option3 = models.CharField(max_length=200)
    option4 = models.CharField(max_length=200)
    option5 = models.CharField(max_length=200)
    answer = models.CharField(max_length=200, choices=ANSWER_CHOICES)
    solution_explanation = models.CharField(max_length=1000)
    
    # New fields for tracking performance
    times_answered = models.PositiveIntegerField(default=0)
    times_correct = models.PositiveIntegerField(default=0)
    times_incorrect = models.PositiveIntegerField(default=0)
    last_difficulty_calculation = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['question_theme']

    def __str__(self):
        return f"{self.question[:50]}... (Theme: {self.question_theme})"

    def calculate_difficulty(self):
        """Automatically calculates question difficulty based on answer statistics"""
        if self.times_answered == 0:
            return 'Medium'  # Default difficulty
        
        correct_percentage = (self.times_correct / self.times_answered) * 100
        
        if correct_percentage >= 90:
            return 'Very Easy'
        elif correct_percentage >= 70:
            return 'Easy'
        elif correct_percentage >= 50:
            return 'Medium'
        elif correct_percentage >= 30:
            return 'Hard'
        else:
            return 'Very Hard'
    
    def update_difficulty(self, save=True):
        """Updates the difficulty rating and saves the question"""
        self.difficulty = self.calculate_difficulty()
        self.last_difficulty_calculation = timezone.now()
        if save:
            self.save()
    
    def record_answer(self, is_correct, save=True):
        """Records an answer attempt and updates statistics"""
        self.times_answered += 1
        if is_correct:
            self.times_correct += 1
        else:
            self.times_incorrect += 1
        
        # Recalculate difficulty after significant attempts
        if self.times_answered % 5 == 0:  # Recalculate every 5 attempts
            self.update_difficulty(save=False)
        
        if save:
            self.save()

class Result(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    exam = models.ForeignKey(Exam, on_delete=models.CASCADE, null=True, blank=True)
    date = models.DateTimeField(auto_now_add=True)  # Capture the date and time of the result
    time_taken = models.DurationField()  # Store the time taken for the test
    num_questions = models.PositiveIntegerField()  # Store the total number of questions
    num_correct_answers = models.PositiveIntegerField()  # Store the number of correct answers
    num_incorrect_answers = models.PositiveIntegerField()  # Store the number of incorrect answers
    error_topics = models.JSONField(default=dict)  # Store topics/subjects with errors as a JSON object
    # Example: {"math": ["algebra", "calculus"], "science": ["physics"]}
    average_time_per_question = models.DurationField(null=True, blank=True)  # Calculate and store the average time per question
    score = models.FloatField()  # Store the overall score
    percentage_score = models.FloatField(verbose_name="Percentage Score", editable=False, null=True, blank=True)

    def __str__(self):
        return f"{self.student.name} - {self.exam.name}: {self.score}"

    def process_question_responses(self):
        for response in self.question_responses.all():
            response.question.record_answer(response.is_correct)

    def save(self, *args, **kwargs):
        # Calculate average time per question when saving
        is_new = not self.pk
        
        if self.num_questions > 0:
            self.average_time_per_question = self.time_taken / self.num_questions
            self.percentage_score = (self.score / self.exam.total_marks) * 100
        super().save(*args, **kwargs)

        if is_new and hasattr(self, 'question_responses'):
            self.process_question_responses()



class Comment(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    timestamp = models.DateTimeField(auto_now_add=True)
    content = models.TextField()
    exam = models.ForeignKey('Exam', related_name='comments', on_delete=models.CASCADE)

    def __str__(self):
        return self.user.username