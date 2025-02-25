from django.db import models
import os

class Candidate(models.Model):
    name = models.CharField(max_length=255)
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=20, blank=True, null=True)
    linkedin = models.URLField(blank=True, null=True)
    github = models.URLField(blank=True, null=True)
    summary = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.name

class Education(models.Model):
    candidate = models.ForeignKey(Candidate, on_delete=models.CASCADE, related_name="education")
    degree = models.CharField(max_length=255)
    university = models.CharField(max_length=255)
    year = models.IntegerField()

    def __str__(self):
        return f"{self.degree} at {self.university}"

class Experience(models.Model):
    candidate = models.ForeignKey(Candidate, on_delete=models.CASCADE, related_name="experience")
    job_title = models.CharField(max_length=255)
    company = models.CharField(max_length=255)
    start_date = models.DateField()
    end_date = models.DateField(blank=True, null=True)
    description = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.job_title} at {self.company}"

class Skill(models.Model):
    candidate = models.ForeignKey(Candidate, on_delete=models.CASCADE, related_name="skills")
    name = models.CharField(max_length=100)

    def __str__(self):
        return self.name
    

def cv_upload_path(instance, filename):
    """Generate path for uploaded CVs."""
    return os.path.join('uploads/cvs/', filename)

class UploadedCV(models.Model):
    file = models.FileField(upload_to=cv_upload_path)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    extracted_text = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.file.name

