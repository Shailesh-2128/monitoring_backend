from rest_framework import serializers
from .models import Project


class ProjectSerializer(serializers.ModelSerializer):
    github_token = serializers.CharField(write_only=True, required=False, allow_blank=True)
    has_token = serializers.BooleanField(read_only=True)
    masked_token = serializers.CharField(read_only=True)

    class Meta:
        model = Project
        fields = [
            'id',
            'name',
            'github_owner',
            'github_repo',
            'github_token',
            'default_branch',
            'has_token',
            'masked_token',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def create(self, validated_data):
        token = validated_data.pop('github_token', '')
        project = Project(**validated_data)
        if token:
            project.set_token(token)
        project.save()
        return project

    def update(self, instance, validated_data):
        token = validated_data.pop('github_token', None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        if token is not None:
            instance.set_token(token)
        instance.save()
        return instance
