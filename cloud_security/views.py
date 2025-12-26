from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.core.mail import send_mail
from django.conf import settings
from .models import CustomUser, File, AccessLog, DDoSLog, FileAccessRequest
from .simple_face_recognition import SimpleFaceRecognition as FaceRecognition
from .federated_learning import DDoSDetector
import os
import mimetypes

face_recog = FaceRecognition()
ddos_detector = DDoSDetector()

def index_view(request):
    return render(request, 'index.html')

def register_view(request):
    if request.method == 'POST':
        username = request.POST['username']
        password = request.POST['password']
        email = request.POST.get('email', '')
        face_image = request.FILES.get('face_image')
        
        # Check if username already exists
        if CustomUser.objects.filter(username=username).exists():
            messages.error(request, 'Username already exists! Please choose a different username.')
            return render(request, 'register.html')
        
        if face_image:
            try:
                # Create user with email
                user = CustomUser.objects.create_user(
                    username=username, 
                    password=password,
                    email=email
                )
                
                # Save face image
                face_path = os.path.join(settings.MEDIA_ROOT, 'faces', f'user_{user.id}.jpg')
                os.makedirs(os.path.dirname(face_path), exist_ok=True)
                
                with open(face_path, 'wb+') as destination:
                    for chunk in face_image.chunks():
                        destination.write(chunk)
                
                # Register face
                if face_recog.register_face(face_path, user.id):
                    messages.success(request, 'Registration successful! Please login.')
                    return redirect('login')
                else:
                    user.delete()
                    messages.error(request, 'Face detection failed. Please try again with a clearer photo.')
            except Exception as e:
                messages.error(request, f'Registration failed: {str(e)}')
        else:
            messages.error(request, 'Please upload face image')
    
    return render(request, 'register.html')

def login_view(request):
    if request.method == 'POST':
        username = request.POST['username']
        password = request.POST['password']
        face_image = request.FILES.get('face_image')
        
        user = authenticate(request, username=username, password=password)
        
        if user is not None:
            if face_image:
                # Save temporary face image
                temp_face_path = os.path.join(settings.MEDIA_ROOT, 'temp', f'temp_{user.id}.jpg')
                os.makedirs(os.path.dirname(temp_face_path), exist_ok=True)
                
                with open(temp_face_path, 'wb+') as destination:
                    for chunk in face_image.chunks():
                        destination.write(chunk)
                
                # Verify face
                if face_recog.verify_face(temp_face_path, user.id):
                    login(request, user)
                    
                    # Log successful access
                    AccessLog.objects.create(
                        user=user,
                        status='success',
                        ip_address=get_client_ip(request)
                    )
                    
                    messages.success(request, 'Login successful!')
                    return redirect('dashboard')
                else:
                    AccessLog.objects.create(
                        user=user,
                        status='face_verification_failed',
                        ip_address=get_client_ip(request)
                    )
                    messages.error(request, 'Face verification failed!')
            else:
                messages.error(request, 'Please capture face image')
        else:
            messages.error(request, 'Invalid credentials')
    
    return render(request, 'login.html')

@login_required
def dashboard_view(request):
    # All files with owner names
    all_files = File.objects.all().select_related('user')
    user_files = File.objects.filter(user=request.user)
    shared_files = File.objects.filter(shared_with=request.user)
    pending_requests = FileAccessRequest.objects.filter(file__user=request.user, status='pending')
    
    # Get access status for each file
    file_access_status = {}
    for file in all_files:
        if file.user != request.user:
            access_request = FileAccessRequest.objects.filter(
                file=file, 
                requested_by=request.user
            ).first()
            file_access_status[file.id] = access_request.status if access_request else 'no_request'
    
    return render(request, 'dashboard.html', {
        'all_files': all_files,
        'files': user_files,
        'shared_files': shared_files,
        'pending_requests': pending_requests,
        'file_access_status': file_access_status
    })

@login_required
def upload_file_view(request):
    if request.method == 'POST' and request.FILES.get('file'):
        uploaded_file = request.FILES['file']
        face_image = request.FILES.get('face_verification')
        
        if not face_image:
            messages.error(request, 'Face verification required for upload!')
            return redirect('dashboard')
        
        # Verify face before upload
        temp_face_path = os.path.join(settings.MEDIA_ROOT, 'temp', f'upload_verify_{request.user.id}.jpg')
        os.makedirs(os.path.dirname(temp_face_path), exist_ok=True)
        
        with open(temp_face_path, 'wb+') as destination:
            for chunk in face_image.chunks():
                destination.write(chunk)
        
        if not face_recog.verify_face(temp_face_path, request.user.id):
            messages.error(request, 'Face verification failed! Upload cancelled.')
            return redirect('dashboard')
        
        # Create user directory if not exists
        user_upload_dir = os.path.join(settings.MEDIA_ROOT, 'files', str(request.user.id))
        os.makedirs(user_upload_dir, exist_ok=True)
        
        # Save file with unique name to avoid conflicts
        filename = uploaded_file.name
        file_path = os.path.join(user_upload_dir, filename)
        
        # Handle duplicate files
        counter = 1
        while os.path.exists(file_path):
            name, ext = os.path.splitext(filename)
            filename = f"{name}_{counter}{ext}"
            file_path = os.path.join(user_upload_dir, filename)
            counter += 1
        
        # Save the file
        with open(file_path, 'wb+') as destination:
            for chunk in uploaded_file.chunks():
                destination.write(chunk)
        
        # Save to database
        file_obj = File.objects.create(
            user=request.user,
            filename=filename,
            file_path=file_path,
            is_private=True
        )
        
        messages.success(request, f'File "{filename}" uploaded successfully with face verification!')
    
    return redirect('dashboard')

@login_required
def request_file_access_view(request, file_id):
    file_obj = get_object_or_404(File, id=file_id)
    face_image = request.FILES.get('face_image')
    
    if not face_image:
        messages.error(request, 'Face verification required for access request!')
        return redirect('dashboard')
    
    # Verify face for access request
    temp_face_path = os.path.join(settings.MEDIA_ROOT, 'temp', f'access_request_{request.user.id}.jpg')
    os.makedirs(os.path.dirname(temp_face_path), exist_ok=True)
    
    with open(temp_face_path, 'wb+') as destination:
        for chunk in face_image.chunks():
            destination.write(chunk)
    
    if not face_recog.verify_face(temp_face_path, request.user.id):
        messages.error(request, 'Face verification failed! Access request cancelled.')
        return redirect('dashboard')
    
    # Create access request
    access_request, created = FileAccessRequest.objects.get_or_create(
        file=file_obj,
        requested_by=request.user,
        defaults={'face_verified': True, 'status': 'pending'}
    )
    
    if created:
        # Send email to file owner
        send_access_request_email(file_obj.user, request.user, file_obj)
        messages.success(request, f'Access request sent to {file_obj.user.username}! Waiting for approval.')
    else:
        if access_request.status == 'pending':
            messages.info(request, 'Access request already pending!')
        elif access_request.status == 'approved':
            messages.info(request, 'You already have access to this file!')
        else:
            # If rejected, create new request
            access_request.status = 'pending'
            access_request.save()
            send_access_request_email(file_obj.user, request.user, file_obj)
            messages.info(request, 'New access request sent!')
    
    return redirect('dashboard')

@login_required
def handle_access_request_view(request, request_id, action):
    access_request = get_object_or_404(FileAccessRequest, id=request_id, file__user=request.user)
    
    if action == 'approve':
        access_request.status = 'approved'
        access_request.owner_response = True
        access_request.file.shared_with.add(access_request.requested_by)
        
        # Send approval email to requester
        send_access_approval_email(access_request.requested_by, access_request.file, request.user)
        
        messages.success(request, f'Access granted to {access_request.requested_by.username}! Email sent.')
        
    elif action == 'reject':
        access_request.status = 'rejected'
        access_request.owner_response = False
        
        # Send rejection email to requester
        send_access_rejection_email(access_request.requested_by, access_request.file, request.user)
        
        messages.success(request, f'Access denied to {access_request.requested_by.username}! Email sent.')
    
    access_request.save()
    return redirect('dashboard')

@login_required
def download_file_view(request, file_id):
    file_obj = get_object_or_404(File, id=file_id)
    face_image = request.FILES.get('face_image')
    
    # Check if user has access (owner OR approved access)
    has_access = (
        file_obj.user == request.user or 
        file_obj.shared_with.filter(id=request.user.id).exists()
    )
    
    if not has_access:
        # Check if there's a pending or rejected request
        access_request = FileAccessRequest.objects.filter(
            file=file_obj, 
            requested_by=request.user
        ).first()
        
        if access_request:
            if access_request.status == 'pending':
                messages.error(request, 'Your access request is still pending approval!')
            elif access_request.status == 'rejected':
                messages.error(request, 'Your access request was rejected by the file owner!')
        else:
            messages.error(request, 'You need to request access first!')
        
        return redirect('dashboard')
    
    if not face_image:
        messages.error(request, 'Face verification required to download!')
        return redirect('dashboard')
    
    # Verify face before download
    temp_face_path = os.path.join(settings.MEDIA_ROOT, 'temp', f'download_verify_{request.user.id}.jpg')
    os.makedirs(os.path.dirname(temp_face_path), exist_ok=True)
    
    with open(temp_face_path, 'wb+') as destination:
        for chunk in face_image.chunks():
            destination.write(chunk)
    
    if not face_recog.verify_face(temp_face_path, request.user.id):
        messages.error(request, 'Face verification failed! Download cancelled.')
        return redirect('dashboard')
    
    # Check if file exists
    if not os.path.exists(file_obj.file_path):
        messages.error(request, 'File not found on server!')
        return redirect('dashboard')
    
    try:
        # Serve file using HttpResponse
        with open(file_obj.file_path, 'rb') as file:
            file_data = file.read()
        
        # Detect MIME type
        mime_type, _ = mimetypes.guess_type(file_obj.filename)
        if not mime_type:
            mime_type = 'application/octet-stream'
        
        response = HttpResponse(file_data, content_type=mime_type)
        response['Content-Disposition'] = f'attachment; filename="{file_obj.filename}"'
        
        # Log access
        AccessLog.objects.create(
            user=request.user,
            status='file_download',
            ip_address=get_client_ip(request),
            accessed_file=file_obj
        )
        
        return response
        
    except Exception as e:
        messages.error(request, f'Download failed: {str(e)}')
        return redirect('dashboard')

@login_required
def detect_ddos_view(request):
    if request.method == 'POST':
        # Simulate network features
        network_features = [
            request.POST.get('packet_count', 0),
            request.POST.get('byte_count', 0),
            request.POST.get('protocol', 0),
            request.POST.get('duration', 0),
            request.POST.get('source_port', 0),
            request.POST.get('dest_port', 0),
            request.POST.get('packet_rate', 0),
            request.POST.get('byte_rate', 0),
            request.POST.get('flag_count', 0),
            request.POST.get('unique_ips', 0)
        ]
        
        is_ddos = ddos_detector.detect_ddos(network_features)
        
        if is_ddos:
            DDoSLog.objects.create(
                source_ip=get_client_ip(request),
                attack_type='suspected_ddos'
            )
        
        return JsonResponse({'is_ddos': is_ddos})

def logout_view(request):
    logout(request)
    return redirect('index')

# Email Functions (same as before)
def send_access_request_email(file_owner, requester, file_obj):
    """Send email notification for access request to file owner"""
    subject = f'🔐 File Access Request - {file_obj.filename}'
    message = f"""
    Hi {file_owner.username},

    📋 ACCESS REQUEST DETAILS:
    • User: {requester.username}
    • File: {file_obj.filename}
    • Requested: {file_obj.uploaded_at.strftime('%Y-%m-%d %H:%M')}

    🎯 ACTION REQUIRED:
    Please login to your dashboard to approve or reject this request.

    🔗 Quick Links:
    • Dashboard: http://127.0.0.1:8000/dashboard/

    Cloud Security System
    🔒 Secure File Sharing
    """
    
    try:
        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            [file_owner.email],
            fail_silently=False,
        )
        print(f"✅ Email sent to {file_owner.email}")
    except Exception as e:
        print(f"❌ Email failed: {e}")
        print("=" * 50)
        print("📧 EMAIL (FALLBACK)")
        print("=" * 50)
        print(f"TO: {file_owner.email}")
        print(f"SUBJECT: {subject}")
        print(f"MESSAGE: {message}")
        print("=" * 50)

def send_access_approval_email(requester, file_obj, file_owner):
    """Send approval email to requester"""
    subject = f'✅ Access Approved - {file_obj.filename}'
    message = f"""
    Hi {requester.username},

    🎉 GREAT NEWS!
    Your access request has been APPROVED by {file_owner.username}.

    📁 FILE DETAILS:
    • File: {file_obj.filename}
    • Owner: {file_owner.username}

    🚀 NEXT STEPS:
    You can now download the file with face verification from your dashboard.

    Cloud Security System
    🔒 Secure File Sharing
    """
    
    try:
        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            [requester.email],
            fail_silently=False,
        )
        print(f"✅ Approval email sent to {requester.email}")
    except Exception as e:
        print(f"❌ Approval email failed: {e}")
        print("=" * 50)
        print("📧 APPROVAL EMAIL (FALLBACK)")
        print("=" * 50)
        print(f"TO: {requester.email}")
        print(f"SUBJECT: {subject}")
        print(f"MESSAGE: {message}")
        print("=" * 50)

def send_access_rejection_email(requester, file_obj, file_owner):
    """Send rejection email to requester"""
    subject = f'❌ Access Denied - {file_obj.filename}'
    message = f"""
    Hi {requester.username},

    📋 REQUEST UPDATE:
    Your access request has been REJECTED by {file_owner.username}.

    📁 FILE DETAILS:
    • File: {file_obj.filename}
    • Owner: {file_owner.username}

    ℹ️ NOTE:
    You will not be able to access this file.

    Cloud Security System
    🔒 Secure File Sharing
    """
    
    try:
        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            [requester.email],
            fail_silently=False,
        )
        print(f"✅ Rejection email sent to {requester.email}")
    except Exception as e:
        print(f"❌ Rejection email failed: {e}")
        print("=" * 50)
        print("📧 REJECTION EMAIL (FALLBACK)")
        print("=" * 50)
        print(f"TO: {requester.email}")
        print(f"SUBJECT: {subject}")
        print(f"MESSAGE: {message}")
        print("=" * 50)

# Utility Functions
def get_client_ip(request):
    """Get the client's IP address from request"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip