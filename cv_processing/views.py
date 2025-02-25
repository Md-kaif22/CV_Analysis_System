from django.db.models import Q
import os
import logging
import fitz
import docx
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from rest_framework.views import APIView
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework import status
from .models import *
from .serializers import *
import openai
import time
from openai import OpenAI, RateLimitError, OpenAIError
import json
from django.conf import settings
from django.shortcuts import render


class CVUploadView(APIView):
    parser_classes = (MultiPartParser, FormParser)
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        """Handles CV file upload and stores extracted text."""
        file_serializer = UploadedCVSerializer(data=request.data)
        
        if file_serializer.is_valid():
            cv_instance = file_serializer.save()

            # Extract text
            extracted_text = self.extract_text(cv_instance.file.path)
            cv_instance.extracted_text = extracted_text
            cv_instance.save()

            return Response({
                "id": cv_instance.id,
                "file": cv_instance.file.url,
                "uploaded_at": cv_instance.uploaded_at,
                "extracted_text": extracted_text 
            }, status=status.HTTP_201_CREATED)

        return Response(file_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def extract_text(self, file_path):
        """Extract text from PDF or DOCX."""
        ext = os.path.splitext(file_path)[1].lower()
        text = ""

        if ext == ".pdf":
            text = self.extract_text_from_pdf(file_path)
        elif ext == ".docx":
            text = self.extract_text_from_docx(file_path)
        else:
            text = "Unsupported file format"

        return text

    def extract_text_from_pdf(self, pdf_path):
        """Extract text from a PDF file."""
        text = ""
        with fitz.open(pdf_path) as doc:
            for page in doc:
                text += page.get_text("text") + "\n"
        return text.strip()

    def extract_text_from_docx(self, docx_path):
        """Extract text from a DOCX file."""
        doc = docx.Document(docx_path)
        return "\n".join([para.text for para in doc.paragraphs]).strip()


class CVSearchView(APIView):
    """Search for CVs based on keyword."""
    permission_classes = [AllowAny]

    def get(self, request):
        keyword = request.GET.get("q", "")

        if not keyword:
            return Response({"error": "Please provide a search keyword."}, status=status.HTTP_400_BAD_REQUEST)

        results = UploadedCV.objects.filter(Q(extracted_text__icontains=keyword))

        if not results.exists():
            return Response({"message": "No matching CVs found."}, status=status.HTTP_404_NOT_FOUND)

        serialized_data = UploadedCVSerializer(results, many=True).data
        return Response(serialized_data, status=status.HTTP_200_OK)

openai.api_key = os.getenv("OPENAI_API_KEY")

logger = logging.getLogger(__name__)

class AnalyzeCVView(APIView):
    """APIView for analyzing CVs and extracting structured data."""

    def analyze_text_with_llm(self, text):
        """Calls OpenAI API to extract structured CV data."""
        api_key = getattr(settings, "OPENAI_API_KEY", None)
        if not api_key:
            logger.error("OpenAI API key is missing in settings.")
            return {"error": "OpenAI API key not configured"}

        client = OpenAI(api_key=api_key)
        max_retries = 3
        retry_delay = 5

        prompt = f"""
        Extract the following details from this CV in JSON format:
        {{
            "name": "Full name of the candidate",
            "email": "Email address",
            "phone": "Phone number",
            "linkedin": "LinkedIn profile URL",
            "github": "GitHub profile URL (if available)",
            "summary": "Short professional summary",
            "education": [
                {{
                    "degree": "Degree name",
                    "university": "University name",
                    "year": "Completion year"
                }}
            ],
            "experience": [
                {{
                    "job_title": "Job title",
                    "company": "Company name",
                    "start_date": "YYYY-MM-DD",
                    "end_date": "YYYY-MM-DD or null if present"
                }}
            ],
            "skills": ["Skill1", "Skill2", "Skill3"]
        }}

        CV TEXT:
        {text}
        """

        for attempt in range(max_retries):
            try:
                response = client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=[{"role": "user", "content": prompt}],
                    response_format="json"
                )
                return json.loads(response.choices[0].message.content)

            except RateLimitError:
                if attempt < max_retries - 1:
                    logger.warning(f"Rate limit exceeded. Retrying in {retry_delay} seconds...")
                    time.sleep(retry_delay)
                else:
                    return {"error": "Rate limit exceeded. Please try again later."}

            except OpenAIError as e:
                logger.error(f"OpenAI API error: {str(e)}")
                return {"error": f"OpenAI API error: {str(e)}"}

    def post(self, request, *args, **kwargs):
        """Analyze a CV and store structured data in DB."""
        cv_id = request.data.get("cv_id")
        cv_instance = UploadedCV.objects.filter(id=cv_id).first()

        if not cv_instance:
            return Response({"error": "CV not found"}, status=status.HTTP_404_NOT_FOUND)

        if not cv_instance.extracted_text:
            return Response({"error": "No extracted text found"}, status=status.HTTP_400_BAD_REQUEST)

        analysis_result = self.analyze_text_with_llm(cv_instance.extracted_text)

        if "error" in analysis_result:
            return Response(analysis_result, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        candidate, created = Candidate.objects.update_or_create(
            email=analysis_result.get("email"),
            defaults={
                "name": analysis_result.get("name"),
                "phone": analysis_result.get("phone"),
                "linkedin": analysis_result.get("linkedin"),
                "github": analysis_result.get("github"),
                "summary": analysis_result.get("summary"),
            }
        )

        Education.objects.filter(candidate=candidate).delete() 
        education_entries = [
            Education(candidate=candidate, degree=edu["degree"], university=edu["university"], year=edu["year"])
            for edu in analysis_result.get("education", [])
        ]
        Education.objects.bulk_create(education_entries)

        Experience.objects.filter(candidate=candidate).delete()  
        experience_entries = [
            Experience(candidate=candidate, job_title=exp["job_title"], company=exp["company"],
                       start_date=exp["start_date"], end_date=exp.get("end_date"))
            for exp in analysis_result.get("experience", [])
        ]
        Experience.objects.bulk_create(experience_entries)

        Skill.objects.filter(candidate=candidate).delete()
        skill_entries = [Skill(candidate=candidate, name=skill) for skill in analysis_result.get("skills", [])]
        Skill.objects.bulk_create(skill_entries)

        return Response({
            "message": "CV analyzed and stored successfully",
            "candidate_id": candidate.id
        }, status=status.HTTP_200_OK)


class ChatbotView(APIView):
    """Chatbot API for querying CV data."""
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        """Handles user queries and returns relevant CV data."""
        query = request.data.get("query", "").strip()

        if not query:
            return Response({"error": "Query is required."}, status=400)

        # Use LLM to interpret query
        structured_query = self.interpret_query_with_llm(query)
        if "error" in structured_query:
            return Response(structured_query, status=500)

        # Fetch candidates based on structured query
        candidates = self.get_matching_candidates(structured_query)

        return Response({"query": query, "results": candidates}, status=200)

    def interpret_query_with_llm(self, query):
        """Uses OpenAI to interpret the user query into a structured format."""
        api_key = openai.api_key
        if not api_key:
            logger.error("OpenAI API key is missing.")
            return {"error": "OpenAI API key not configured"}

        client = openai.OpenAI(api_key=api_key)
        prompt = f"""
        Convert this natural language query into structured JSON format:

        QUERY: "{query}"

        Example Output:
        {{
            "skills": ["Python", "Django"],
            "education": {{"degree": "Bachelor", "field": "Computer Science"}},
            "experience": {{"min_years": 3}}
        }}

        If no specific filter is mentioned, return an empty JSON object {{}}.
        """

        for attempt in range(3):  # Retry in case of API failures
            try:
                response = client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=[{"role": "user", "content": prompt}],
                    response_format="json"
                )
                return json.loads(response.choices[0].message.content)

            except openai.RateLimitError:
                if attempt < 2:
                    time.sleep(5)
                else:
                    return {"error": "Rate limit exceeded. Try again later."}

            except openai.OpenAIError as e:
                return {"error": f"OpenAI API error: {str(e)}"}

    def get_matching_candidates(self, filters):
        """Fetch candidates based on structured query filters."""
        queryset = Candidate.objects.all()

        if "skills" in filters:
            skill_names = filters["skills"]
            queryset = queryset.filter(skills__name__in=skill_names).distinct()

        if "education" in filters:
            education_filter = filters["education"]
            queryset = queryset.filter(
                education__degree__icontains=education_filter.get("degree", ""),
                education__university__icontains=education_filter.get("field", "")
            ).distinct()

        if "experience" in filters and "min_years" in filters["experience"]:
            min_years = filters["experience"]["min_years"]
            queryset = queryset.filter(experience__start_date__lte=f"{2025-min_years}-01-01").distinct()

        return [
            {
                "name": candidate.name,
                "email": candidate.email,
                "skills": [skill.name for skill in candidate.skills.all()],
                "education": [
                    {"degree": edu.degree, "university": edu.university, "year": edu.year}
                    for edu in candidate.education.all()
                ],
                "experience": [
                    {"job_title": exp.job_title, "company": exp.company, "start_date": exp.start_date}
                    for exp in candidate.experience.all()
                ]
            }
            for candidate in queryset
        ]

def homepage(request):
    return render(request, "homepage.html")

