from django.urls import path

from . import views

urlpatterns = [
    path("faqs/", views.FaqListView.as_view(), name="faq-list"),
    path("faqs/<int:pk>/", views.FaqDetailView.as_view(), name="faq-detail"),
    path("questions/", views.QuestionCreateView.as_view(), name="question-create"),
    path(
        "questions/<uuid:pk>/resolve/",
        views.QuestionResolveView.as_view(),
        name="question-resolve",
    ),
]
