from django.contrib import admin
from django.urls import path
from theconcreteprotector import views
from .views import CameraImageListAPIView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', views.home, name="Home"),
    path('login/', views.user_login, name="Login"),
    path('reset-password/', views.reset_password, name="ResetPsw"),
    path('verify-otp/', views.verify_otp, name="VerifyOtp"),

    path('logout/', views.user_logout, name="Logout"),
    path('add-user/', views.add_user, name="AddUser"),
    path('users-list/', views.users_list, name="UsersList"), 
    path('user-profile/<int:pk>', views.user_profile, name='UserProfile'),
    path('list-user-profile/<int:pk>', views.list_user_profile, name='ListUserProfile'),
    path('delete-user/<int:pk>', views.delete_user, name='DeleteUser'),
    path('api/images/', CameraImageListAPIView.as_view(), name='camera-images-api'),

]
