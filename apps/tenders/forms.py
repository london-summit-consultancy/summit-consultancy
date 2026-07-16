from django import forms
from django.contrib.auth import get_user_model

from .models import Tender

User = get_user_model()


class TenderForm(forms.ModelForm):
    """Create/update form. ``reference``, ``created_by`` and ``status`` are
    managed by the model / dedicated views, never edited here."""

    class Meta:
        model = Tender
        fields = [
            "title",
            "client_name",
            "client_email",
            "sector",
            "description",
            "deadline",
            "estimated_value",
            "assigned_to",
            "notes",
        ]
        widgets = {
            "deadline": forms.DateInput(attrs={"type": "date"}),
            "estimated_value": forms.NumberInput(attrs={"step": "0.01", "min": "0"}),
            "assigned_to": forms.CheckboxSelectMultiple,
        }

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        # Only active staff can be assigned to a tender.
        self.fields["assigned_to"].queryset = User.objects.filter(
            is_active=True, is_staff=True
        ).order_by("full_name", "email")
        self.fields["assigned_to"].required = False
        self.fields["client_email"].required = False
        self.fields["deadline"].required = False
        self.fields["estimated_value"].required = False
        self.fields["notes"].required = False

        # Apply the brand input styling to plain widgets (prose editors and the
        # checkbox list bring their own markup and are styled in the template).
        for name in (
            "title",
            "client_name",
            "client_email",
            "sector",
            "deadline",
            "estimated_value",
        ):
            self.fields[name].widget.attrs.setdefault("class", "field-input")
