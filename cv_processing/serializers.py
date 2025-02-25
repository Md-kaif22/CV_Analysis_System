from rest_framework import serializers
from .models import UploadedCV

class UploadedCVSerializer(serializers.ModelSerializer):
    class Meta:
        model = UploadedCV
        fields = '__all__'
