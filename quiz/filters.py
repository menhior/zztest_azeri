import django_filters
from .models import QuizSubmission

class QuizSubmissionFilter(django_filters.FilterSet):
    quiz__title = django_filters.CharFilter(lookup_expr='icontains', label='Quiz Title')
    quiz__category__name = django_filters.CharFilter(lookup_expr='icontains', label='Quiz Category')

    class Meta:
        model = QuizSubmission
        fields = ['quiz__title', 'quiz__category__name']
 