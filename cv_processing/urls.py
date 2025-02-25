from django.urls import path
from .views import CVUploadView, CVSearchView,AnalyzeCVView,ChatbotView,homepage

urlpatterns = [
    path("", homepage, name="homepage"),
    path("api/upload-cv/", CVUploadView.as_view(), name="upload_cv_api"),
    path("api/search-cv/", CVSearchView.as_view(), name="search_cv"),
    path("api/analyze-cv/", AnalyzeCVView.as_view(), name="analyze_cv"),
    path("api/chatbot/", ChatbotView.as_view(), name="chatbot"),
]
