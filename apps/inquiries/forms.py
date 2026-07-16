from django import forms

from .models import Inquiry


class InquiryForm(forms.ModelForm):
    class Meta:
        model = Inquiry
        fields = [
            "full_name",
            "email",
            "phone",
            "company",
            "buyer_type",
            "service",
            "project_desc",
            "budget_range",
            "website",
        ]
        widgets = {
            "website": forms.HiddenInput(),
            "project_desc": forms.Textarea(
                attrs={"rows": 5, "placeholder": "Tell us about your project…"}
            ),
            "full_name": forms.TextInput(attrs={"placeholder": "Your full name"}),
            "email": forms.EmailInput(attrs={"placeholder": "your@email.com"}),
            "phone": forms.TextInput(attrs={"placeholder": "+44 7700 000000"}),
            "company": forms.TextInput(attrs={"placeholder": "Company or organisation (optional)"}),
            "budget_range": forms.TextInput(attrs={"placeholder": "e.g. £50k–£100k (optional)"}),
        }
        labels = {
            "buyer_type": "I am a",
            "project_desc": "Project description",
            "budget_range": "Approximate budget",
            "full_name": "Full name",
        }
