from django.db import models
from django.contrib.auth.models import AbstractUser

class CustomUser(AbstractUser):
    facial_data_path = models.CharField(max_length=500, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    email = models.EmailField(blank=True)
    
class File(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    filename = models.CharField(max_length=255)
    file_path = models.CharField(max_length=500)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    is_private = models.BooleanField(default=True)
    shared_with = models.ManyToManyField(CustomUser, related_name='shared_files', blank=True)
    
class FileAccessRequest(models.Model):
    file = models.ForeignKey(File, on_delete=models.CASCADE)
    requested_by = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='access_requests')
    requested_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=[
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected')
    ], default='pending')
    face_verified = models.BooleanField(default=False)
    owner_response = models.BooleanField(null=True, blank=True)  # True=Accept, False=Reject
    
class AccessLog(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    access_time = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=50)
    ip_address = models.GenericIPAddressField()
    accessed_file = models.ForeignKey(File, on_delete=models.CASCADE, null=True, blank=True)
    
class DDoSLog(models.Model):
    source_ip = models.GenericIPAddressField()
    attack_type = models.CharField(max_length=100)
    timestamp = models.DateTimeField(auto_now_add=True)
    blocked = models.BooleanField(default=False)