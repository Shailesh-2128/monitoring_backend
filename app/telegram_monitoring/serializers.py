from rest_framework import serializers
from .models import TelegramConfig, TelegramSubscriber, TelegramNotificationLog


class TelegramConfigSerializer(serializers.ModelSerializer):
    class Meta:
        model = TelegramConfig
        fields = [
            'id', 'bot_token', 'bot_username', 'webhook_secret',
            'cpu_threshold', 'ram_threshold', 'disk_threshold',
            'notify_server_overload', 'notify_github_push',
            'created_at', 'updated_at'
        ]
        extra_kwargs = {
            'bot_token': {'write_only': False}  # Shown for admin configuration
        }


class TelegramSubscriberSerializer(serializers.ModelSerializer):
    username = serializers.SerializerMethodField()

    class Meta:
        model = TelegramSubscriber
        fields = [
            'id', 'username', 'chat_id', 'telegram_username',
            'first_name', 'last_name', 'verification_token',
            'is_verified', 'connected_at', 'notifications_enabled', 'created_at'
        ]

    def get_username(self, obj):
        return obj.user.username if obj.user else 'Anonymous'


class TelegramNotificationLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = TelegramNotificationLog
        fields = '__all__'
