from django.contrib import admin
from .models import CustomUser, File, AccessLog, DDoSLog

@admin.register(CustomUser)
class CustomUserAdmin(admin.ModelAdmin):
    list_display = ['username', 'email', 'created_at']

@admin.register(File)
class FileAdmin(admin.ModelAdmin):
    list_display = ['filename', 'user', 'uploaded_at']

@admin.register(AccessLog)
class AccessLogAdmin(admin.ModelAdmin):
    list_display = ['user', 'access_time', 'status', 'ip_address']

@admin.register(DDoSLog)
class DDoSLogAdmin(admin.ModelAdmin):
    list_display = ['source_ip', 'attack_type', 'timestamp', 'blocked']
