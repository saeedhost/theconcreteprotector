from django.contrib import admin

from .models import *
class CameraAdmin(admin.ModelAdmin):
    list_display = ('id', 'name')

class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'access_type')

admin.site.register(Camera, CameraAdmin)
admin.site.register(UserProfile, UserProfileAdmin)

class OTPAdmin(admin.ModelAdmin):
    list_display = ('email', 'otp_value', 'created_at')
admin.site.register(OTP, OTPAdmin)