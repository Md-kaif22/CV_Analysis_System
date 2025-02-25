# CV Analysis System

## Overview
This project processes and analyzes CVs using OCR and AI, allowing users to query CV data via a chatbot.

## Installation
1. Clone this repository:
   ```sh
   git clone https://github.com/Md-kaif22/CV_Analysis_System.git
   cd cv_analysis
   
2. Create a Virtual Environment
     python -m venv venv
     source venv/bin/activate  # On Windows, use `venv\Scripts\activate`
   
3. Install dependencies:
     pip install -r requirements.txt
   
4. Apply migrations:
     python manage.py migrate
   
5. Run the server:
     python manage.py runserver
   
6. Open the UI at http://127.0.0.1:8000/

   **API Endpoints**
POST /api/upload-cv/ → Upload CV files
POST /api/analyze-cv/ → Process & extract CV data
POST /api/chatbot/ → Query CV information

   **Environment Variables**
Create a .env file based on .env.example and add:
    DJANGO_SECRET_KEY=your-secret-key
    OPENAI_API_KEY=your-api-key

