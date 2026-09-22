from django.urls import path

from . import views

urlpatterns = [
    path("faqs/", views.FaqListView.as_view(), name="faq-list"),
    path("faqs/<int:pk>/", views.FaqDetailView.as_view(), name="faq-detail"),
]
