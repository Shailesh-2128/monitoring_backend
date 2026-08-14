from django import forms
from django.contrib import admin
from .models import Project


class ProjectAdminForm(forms.ModelForm):
    raw_github_token = forms.CharField(
        widget=forms.PasswordInput(render_value=True),
        required=False,
        label="GitHub Personal Access Token (PAT)",
        help_text="Enter GitHub PAT. Token is stored securely using Fernet encryption and never shown plain."
    )

    class Meta:
        model = Project
        fields = ['name', 'github_owner', 'github_repo', 'default_branch']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk and self.instance.github_token:
            self.fields['raw_github_token'].initial = self.instance.masked_token

    def save(self, commit=True):
        instance = super().save(commit=False)
        raw_token = self.cleaned_data.get('raw_github_token')
        # If token was edited and is not just the masked string placeholder
        if raw_token and not raw_token.startswith('ghp_...'):
            instance.set_token(raw_token)
        if commit:
            instance.save()
        return instance


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    form = ProjectAdminForm
    list_display = ('name', 'github_owner', 'github_repo', 'default_branch', 'has_token_display', 'masked_token', 'updated_at')
    list_filter = ('default_branch', 'created_at')
    search_fields = ('name', 'github_owner', 'github_repo')
    readonly_fields = ('created_at', 'updated_at', 'masked_token')

    @admin.display(boolean=True, description="Has Token")
    def has_token_display(self, obj):
        return obj.has_token
