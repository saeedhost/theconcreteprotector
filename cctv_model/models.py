from django.db import models
from django.contrib.auth.models import User

class Camera(models.Model):
    name = models.CharField(max_length=255)

class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    access_type = models.CharField(max_length=255, choices=[('allCameras', 'All cameras'), ('chooseCamera', 'Choose cameras access')])
    cameras = models.ManyToManyField(Camera)

    def __str__(self):
        return self.user.username
    
class OTP(models.Model):
    email = models.EmailField(unique=True)
    otp_value = models.CharField(max_length=6)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.email