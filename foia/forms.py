from django import forms

from .models import (
    FOIARequest, FOIAScope, FOIASearchResult, FOIADetermination,
    FOIAAppeal, StatutoryExemption,
)


class FOIARequestForm(forms.ModelForm):
    date_received = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
    )
    statutory_deadline = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
    )

    class Meta:
        model = FOIARequest
        fields = [
            'request_number', 'status', 'priority',
            'requester_name', 'requester_email', 'requester_phone',
            'requester_organization',
            'subject', 'description', 'date_received', 'statutory_deadline',
            'assigned_to', 'reviewing_attorney',
        ]
        widgets = {
            'request_number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'FOIA-2026-001'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'priority': forms.Select(attrs={'class': 'form-select'}),
            'requester_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Requester name'}),
            'requester_email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Email'}),
            'requester_phone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Phone'}),
            'requester_organization': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Organization'}),
            'subject': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Request subject'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'placeholder': 'Records requested'}),
            'assigned_to': forms.Select(attrs={'class': 'form-select'}),
            'reviewing_attorney': forms.Select(attrs={'class': 'form-select'}),
        }


class FOIAScopeForm(forms.ModelForm):
    date_range_start = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
    )
    date_range_end = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
    )
    keywords_text = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control', 'rows': 3,
            'placeholder': 'One keyword or phrase per line',
        }),
        help_text='Enter search terms, one per line.',
    )
    company_names_text = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control', 'rows': 2,
            'placeholder': 'Company names, one per line',
        }),
    )
    contact_names_text = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control', 'rows': 2,
            'placeholder': 'Contact names, one per line',
        }),
    )

    class Meta:
        model = FOIAScope
        fields = ['scope_notes']
        widgets = {
            'scope_notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Additional scope notes'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            self.fields['keywords_text'].initial = '\n'.join(self.instance.keywords or [])
            self.fields['company_names_text'].initial = '\n'.join(self.instance.company_names or [])
            self.fields['contact_names_text'].initial = '\n'.join(self.instance.contact_names or [])
            self.fields['date_range_start'].initial = self.instance.date_range_start
            self.fields['date_range_end'].initial = self.instance.date_range_end

    def save(self, commit=True):
        obj = super().save(commit=False)
        obj.keywords = [k.strip() for k in self.cleaned_data.get('keywords_text', '').split('\n') if k.strip()]
        obj.company_names = [c.strip() for c in self.cleaned_data.get('company_names_text', '').split('\n') if c.strip()]
        obj.contact_names = [c.strip() for c in self.cleaned_data.get('contact_names_text', '').split('\n') if c.strip()]
        obj.date_range_start = self.cleaned_data.get('date_range_start')
        obj.date_range_end = self.cleaned_data.get('date_range_end')
        if commit:
            obj.save()
        return obj


class FOIADeterminationForm(forms.ModelForm):
    class Meta:
        model = FOIADetermination
        fields = ['decision', 'justification', 'redacted_content']
        widgets = {
            'decision': forms.Select(attrs={'class': 'form-select'}),
            'justification': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Legal justification for this determination'}),
            'redacted_content': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Redacted version (for partial release)'}),
        }

    exemptions = forms.ModelMultipleChoiceField(
        queryset=StatutoryExemption.objects.filter(is_active=True),
        required=False,
        widget=forms.CheckboxSelectMultiple,
    )


class FOIAAppealForm(forms.ModelForm):
    filed_date = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
    )
    hearing_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
    )
    decision_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
    )

    class Meta:
        model = FOIAAppeal
        fields = [
            'appeal_number', 'appeal_status', 'filed_date',
            'appellant_arguments', 'agency_response',
            'hearing_date', 'hearing_notes',
            'decision_date', 'decision_summary', 'lessons_learned',
        ]
        widgets = {
            'appeal_number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Appeal number'}),
            'appeal_status': forms.Select(attrs={'class': 'form-select'}),
            'appellant_arguments': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'agency_response': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'hearing_notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'decision_summary': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'lessons_learned': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }
