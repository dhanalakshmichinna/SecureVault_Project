from django.urls import path
from . import views

urlpatterns = [
    path('', views.index_view, name='index'),
    path('register/', views.register_view, name='register'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('dashboard/', views.dashboard_view, name='dashboard'),
    path('upload/', views.upload_file_view, name='upload_file'),
    path('request-access/<int:file_id>/', views.request_file_access_view, name='request_access'),
    path('handle-request/<int:request_id>/<str:action>/', views.handle_access_request_view, name='handle_access_request'),
    path('download-file/<int:file_id>/', views.download_file_view, name='download_file'),
    path('detect-ddos/', views.detect_ddos_view, name='detect_ddos'),
]