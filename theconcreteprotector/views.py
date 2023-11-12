from django.shortcuts import render, redirect
from storages.backends.s3boto3 import S3Boto3Storage
import boto3
import re

#User Auth Packages
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db.models import Q
from django.contrib import messages
from django.contrib.auth.decorators import user_passes_test


from django.core.exceptions import ObjectDoesNotExist
from cctv_model.models import Camera, UserProfile

#OTP packages
import random
import string
from datetime import datetime
from django.core.mail import send_mail
from cctv_model.models import OTP
from django.contrib.auth import get_user_model

#API
from rest_framework import generics
from rest_framework import status
from rest_framework.response import Response
from cctv_model.serializers import ImageSerializer
from datetime import datetime


def is_superuser(user):
    return user.is_superuser

@csrf_exempt
def user_login(request):
    if request.method == 'POST':
        username_or_email = request.POST.get('username_or_email')
        password = request.POST.get('password')
        if '@' in username_or_email:
            try:
                user = User.objects.get(email=username_or_email)
            except User.DoesNotExist:
                user = None
        else:
            user = authenticate(request, username=username_or_email, password=password)
        if user is not None:
            try:
                login(request, user)
                return redirect('Home')
            except ObjectDoesNotExist:
                messages.error(request, "No Account found")    
        else:
            messages.error(request, 'Invalid login credentials. Please try again.')
            return redirect('Login')
    return render(request, "login.html")


@csrf_exempt
def reset_password(request):
    data = {}
    if request.method == 'POST':
        valid_username = request.POST['valid_username']
        valid_email = request.POST['valid_email']

        try:
            User = get_user_model()
            user = User.objects.get(username=valid_username, email=valid_email)

            otp, created = OTP.objects.get_or_create(email=valid_email)
            if created:
                otp.otp_value = ''.join(random.choices(string.digits, k=6))
                otp.save()

            subject = 'Password Reset OTP'
            message = f'Your OTP for password reset: {otp.otp_value}'
            from_email = 'concreteprotectorcctv@gmail.com'
            recipient_list = [valid_email]
            send_mail(subject, message, from_email, recipient_list)

            new_password = request.POST['newpassword']
            data = {
                'valid_email': valid_email,
                'new_password': new_password,
            }
            return render(request, "verify-otp.html", data)

        except User.DoesNotExist:
            messages.error(request, 'Invalid username or email. Please provide valid credentials.')
            return redirect('ResetPsw')

    return render(request, "reset-password.html")



@csrf_exempt
def verify_otp(request):
    if request.method == 'POST':
        entered_otp = request.POST['valid_otp']
        email = request.POST['otp_email_object']

        try:
            otp = OTP.objects.get(email=email)
            if otp and otp.otp_value == entered_otp:
                User = get_user_model()
                user = User.objects.get(email=email)

                new_password = request.POST['new_password']
                user.set_password(new_password)
                user.save()

                otp.delete()

                messages.success(request, 'Password reset successfully.')
                return redirect('Login')
            else:
                messages.error(request, 'Invalid OTP.')
                return redirect('VerifyOtp')

        except OTP.DoesNotExist:
            messages.error(request, 'Expired OTP. Please request a new one.')
            return redirect('VerifyOtp')
    return render(request, "verify-otp.html")


@login_required(login_url="/login/")
def user_logout(request):
    logout(request)
    return redirect('Login')



@csrf_exempt
@login_required(login_url="/login/")
def home(request):
    calendar_date = None
    display_selected_camera_name = 'No camera'
    display_calendar_date = 'No date'
    
    storage = S3Boto3Storage()
    s3 = boto3.client('s3')
    bucket_folder_names = set()

    image_info_list = {}
    selected_images = []

    if request.method == 'POST':
        selected_camera_id = request.POST.get('selectedCamera')
        calendar_date_str = request.POST.get('calendar_date')
        display_calendar_date = calendar_date_str


        if selected_camera_id and calendar_date_str:
            try:
                selected_camera = Camera.objects.get(id=selected_camera_id)
                calendar_date = datetime.strptime(calendar_date_str, '%Y-%m-%d').date()
                display_selected_camera_name = selected_camera.name
                selected_images = get_selected_images(request, selected_camera.name, calendar_date)
            except Camera.DoesNotExist:
                messages.error(request, 'Invalid Camera selected.')
            except Exception as e:
                messages.error(request, f'An error occurred: {str(e)}')
    else:
        messages.success(request, 'Please select camera and date to view images.')

    try:
        for obj in s3.list_objects(Bucket=storage.bucket_name)['Contents']:
            folder_name = obj['Key'].split('/', 1)[0]
            bucket_folder_names.add(folder_name)

            if folder_name not in image_info_list:
                image_info_list[folder_name] = []

            image_info = {
                'url': storage.url(obj['Key']),
                'last_modified': obj['LastModified']
            }

            image_info_list[folder_name].append(image_info)
            camera, created = Camera.objects.get_or_create(name=folder_name)
    except:
            messages.error(request, 'No data uploaded yet!')

    camera_names_in_model = set(Camera.objects.values_list('name', flat=True))
    folders_to_delete = camera_names_in_model - bucket_folder_names
    Camera.objects.filter(name__in=folders_to_delete).delete()
    cameras = get_available_cameras(request.user)

    data = {
        'cameras': cameras,
        'selected_images': selected_images,
        'selected_camera_name': display_selected_camera_name,
        'selected_calendar_date': display_calendar_date,
    }
    return render(request, 'index.html', data)


def get_available_cameras(user):
    is_super_admin = user.is_superuser
    if is_super_admin:
        return Camera.objects.all()
    try:
        user_profile = UserProfile.objects.get(user=user)
        if user_profile.access_type == 'allCameras':
            return Camera.objects.all()
        return user_profile.cameras.all()
    except ObjectDoesNotExist:
        print("User profile does not exist.")
    return []



def get_selected_images(request, camera_name, calendar_date):
    storage = S3Boto3Storage()
    s3 = boto3.client('s3')
    image_info_list = {}

    date_pattern = r'\d{4}-\d{2}-\d{2}'
    bucket_folder_names = set()
    try:
        for obj in s3.list_objects(Bucket=storage.bucket_name)['Contents']:
            folder_name = obj['Key'].split('/', 1)[0]
            bucket_folder_names.add(folder_name)

            if folder_name not in image_info_list:
                image_info_list[folder_name] = []

            image_info = {
                'url': storage.url(obj['Key']),
                'last_modified': obj['LastModified']
            }
            
            date_match = re.search(date_pattern, obj['Key'])
            if date_match:
                image_date_str = date_match.group(0)
                image_info['image_date'] = datetime.strptime(image_date_str, '%Y-%m-%d').date()
            else:
                image_info['image_date'] = None
                
            image_info_list[folder_name].append(image_info)
            
    except Exception as e:
        messages.error(request, f'Error: {str(e)}')
        return []
    
    images_for_date = [image for image in image_info_list.get(camera_name, []) if image.get('image_date') == calendar_date]
    
    if not images_for_date:
        messages.error(request, f'The selected camera has no image on {calendar_date}')
    return images_for_date



@csrf_exempt
@user_passes_test(is_superuser, login_url="/login/")
def add_user(request):
    data = {}
    if request.method == 'POST':
        username = request.POST.get('username')
        email = request.POST.get('email')
        password = request.POST.get('password')
        c_password = request.POST.get('c_password')
        accessType = request.POST.get('accessType')
        selected_cameras = request.POST.getlist('selected_cameras')

        if password != c_password:
            messages.error(request, 'Password and confirm password do not match.')
            return redirect('AddUser')
        
        try:
            existing_user = User.objects.get(Q(username=username) | Q(email=email))
            if existing_user.username == username:
                messages.error(request, "An account already exists with this username")
            else:
                messages.error(request, "An account already exists with this email")
            return redirect('AddUser')
        
        except User.DoesNotExist:

            user = User.objects.create_user(username, email, password)
            profile = UserProfile.objects.create(user=user)

            if accessType == 'allCameras':
                profile.access_type = 'allCameras'
            elif accessType == 'chooseCamera':
                profile.access_type = 'chooseCamera'
                selected_cameras = request.POST.getlist('selected_cameras')
                for camera_id in selected_cameras:
                    print("Cameras: ", camera_id)
                    profile.cameras.add(Camera.objects.get(id=camera_id))

            profile.save()
            messages.success(request, "User Added successfully")
            return redirect('AddUser')
        
    cameras = Camera.objects.all()
    data = {
        'cameras': cameras,
    }
    return render(request, 'add-user.html', data)



@login_required(login_url="/login/")
def users_list(request):
    data = {}
    if request.user.is_superuser:
        users = User.objects.filter(is_superuser=False)
    else:
        users = User.objects.all()
    data = {
        'users' : users
    }
    return render(request, "users-list.html", data)



@login_required(login_url="/login/")
def user_profile(request, pk):
    cameras = 0
    if request.user.is_superuser:
        user = request.user
        cameras = Camera.objects.all()
    else:
        user = User.objects.get(id=pk)
        user_profile = UserProfile.objects.get(user=user)
        if user_profile.access_type == 'allCameras':
            cameras = Camera.objects.all()
        else:
            cameras = user_profile.cameras.all()

    count_cameras = cameras.count()

    data = {
        'user': user,
        'count_cameras': count_cameras,
    }
    return render(request, "user-profile.html", data)


@user_passes_test(is_superuser, login_url="/login/")
def list_user_profile(request, pk):
    user = User.objects.get(id=pk)
    user_profile = UserProfile.objects.get(user=user)
    if user_profile.access_type == 'allCameras':
        cameras = Camera.objects.all()
    else:
        cameras = user_profile.cameras.all()

    count_cameras = cameras.count()

    data = {
        'user': user,
        'count_cameras': count_cameras,
    }
    return render(request, "user-profile.html", data)


@user_passes_test(is_superuser, login_url="/login/")
def delete_user(request, pk):
    user = User.objects.get(id=pk)
    user.delete()
    return users_list(request)


"""
#GET api here
class CameraImageListAPIView(generics.ListAPIView):
    serializer_class = ImageSerializer

    def get_queryset(self):
        camera_name = self.request.query_params.get('camera_name', None)
        date_str = self.request.query_params.get('date', None)

        if camera_name and date_str:
            try:
                camera = Camera.objects.get(name=camera_name)
                calendar_date = datetime.strptime(date_str, '%Y-%m-%d').date()
                images = get_selected_images(self.request, camera.name, calendar_date)
                return images
            except Camera.DoesNotExist:
                return []
        else:
            return []

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        serializer = ImageSerializer(queryset, many=True)  # Serialize the list of dictionaries
        return Response(serializer.data, status=status.HTTP_200_OK)


# http://127.0.0.1:2234/api/images/?camera_name=Camera1&date=2023-10-10 

"""

"""
class CameraImageListAPIView(generics.ListAPIView):
    serializer_class = ImageSerializer

    def get_queryset(self):
        camera_name = self.request.query_params.get('camera_name', None)
        from_date_str = self.request.query_params.get('from_date', None)

        if camera_name and from_date_str:
            try:
                camera = Camera.objects.get(name=camera_name)
                from_date = datetime.strptime(from_date_str, '%Y-%m-%d').date()
                today = datetime.now().date()
                images = get_images_in_date_range(self.request, camera.name, from_date, today)
                return images
            except Camera.DoesNotExist:
                return []
        else:
            return []

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        serializer = ImageSerializer(queryset, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
"""

class CameraImageListAPIView(generics.ListAPIView):
    serializer_class = ImageSerializer

    def get_queryset(self):
        camera_name = self.request.query_params.get('camera_name', None)
        from_date_str = self.request.query_params.get('from_date', None)

        if from_date_str:
            try:
                from_date = datetime.strptime(from_date_str, '%Y-%m-%d').date()
                today = datetime.now().date()

                if camera_name:
                    # Filter images for the specified camera
                    camera = Camera.objects.get(name=camera_name)
                    images = get_images_in_date_range(self.request, camera.name, from_date, today)
                else:
                    # If no camera_name is provided, get images from all cameras
                    all_cameras = Camera.objects.all()
                    images = []
                    for camera in all_cameras:
                        images += get_images_in_date_range(self.request, camera.name, from_date, today)

                return images

            except Camera.DoesNotExist:
                return []
        else:
            return []

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        serializer = ImageSerializer(queryset, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

def get_images_in_date_range(request, camera_name, from_date, to_date):
    storage = S3Boto3Storage()
    s3 = boto3.client('s3')
    image_info_list = {}
    date_pattern = r'\d{4}-\d{2}-\d{2}'
    bucket_folder_names = set()

    try:
        for obj in s3.list_objects(Bucket=storage.bucket_name)['Contents']:
            folder_name = obj['Key'].split('/', 1)[0]
            bucket_folder_names.add(folder_name)

            if folder_name not in image_info_list:
                image_info_list[folder_name] = []

            image_info = {
                'url': storage.url(obj['Key']),
                'last_modified': obj['LastModified']
            }

            date_match = re.search(date_pattern, obj['Key'])
            if date_match:
                image_date_str = date_match.group(0)
                image_info['image_date'] = datetime.strptime(image_date_str, '%Y-%m-%d').date()
            else:
                image_info['image_date'] = None

            image_info_list[folder_name].append(image_info)

    except Exception as e:
        messages.error(request, f'Error: {str(e)}')
        return []

    images_in_range = [
        image for image in image_info_list.get(camera_name, [])
        if from_date <= image.get('image_date') <= to_date
    ]

    if not images_in_range:
        messages.error(request, f'The selected camera has no images between {from_date} and {to_date}')
    return images_in_range

#http://127.0.0.1:2234/api/images/?camera_name=Camera1&from_date=2023-10-10
