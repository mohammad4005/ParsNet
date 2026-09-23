from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import Group, User
import jdatetime
from .models import Equipment, EquipmentCategory, EquipmentControlItem, MaintenancePlan, WorkOrder
class EquipmentForm(forms.ModelForm):
    class Meta: model=Equipment; fields=["code","name","category","location","operating_unit","manufacturer","model_number","serial_number","capacity","criticality","status"]


class EquipmentCategoryForm(forms.ModelForm):
    class Meta:
        model = EquipmentCategory
        fields = ["name"]


class EquipmentControlItemForm(forms.ModelForm):
    next_due_date = forms.CharField(label="اولین تاریخ انجام", help_text="مانند ۱۴۰۵/۰۷/۰۱")

    class Meta:
        model = EquipmentControlItem
        fields = ["title", "help_text", "frequency", "next_due_date", "active"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        date_value = self.initial.get("next_due_date") or getattr(self.instance, "next_due_date", None)
        if date_value:
            self.initial["next_due_date"] = jdatetime.date.fromgregorian(date=date_value).strftime("%Y/%m/%d")

    def clean_next_due_date(self):
        raw = self.cleaned_data["next_due_date"].translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789")).replace("-", "/")
        try:
            year, month, day = [int(part) for part in raw.split("/")]
            return jdatetime.date(year, month, day).togregorian()
        except (ValueError, TypeError):
            raise forms.ValidationError("تاریخ را به شکل ۱۴۰۵/۰۷/۰۱ وارد کنید.")
class MaintenancePlanForm(forms.ModelForm):
    next_due_date = forms.CharField(label="تاریخ سرویس بعدی", help_text="مانند ۱۴۰۵/۰۷/۰۱")
    class Meta: model=MaintenancePlan; fields=["equipment","checklist","frequency","next_due_date","active"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.next_due_date:
            self.initial["next_due_date"] = jdatetime.date.fromgregorian(date=self.instance.next_due_date).strftime("%Y/%m/%d")

    def clean_next_due_date(self):
        raw = self.cleaned_data["next_due_date"].translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789")).replace("-", "/")
        try:
            year, month, day = [int(part) for part in raw.split("/")]
            return jdatetime.date(year, month, day).togregorian()
        except (ValueError, TypeError):
            raise forms.ValidationError("تاریخ را به شکل ۱۴۰۵/۰۷/۰۱ وارد کنید.")


class EquipmentServicePlanForm(forms.Form):
    name = forms.CharField(label="نام برنامه سرویس", max_length=150, help_text="مثلاً بازدید هفتگی جرثقیل")
    frequency = forms.ChoiceField(label="تناوب اجرا", choices=MaintenancePlan.Frequency.choices)
    next_due_date = forms.CharField(label="اولین تاریخ اجرا", help_text="مانند ۱۴۰۵/۰۷/۰۱")
    control_items = forms.ModelMultipleChoiceField(
        label="موارد کنترل این برنامه",
        queryset=EquipmentControlItem.objects.none(),
        widget=forms.CheckboxSelectMultiple,
        help_text="یک یا چند مورد را از فهرست کنترل همین دستگاه انتخاب کنید.",
    )

    def __init__(self, *args, equipment=None, **kwargs):
        super().__init__(*args, **kwargs)
        if equipment:
            self.fields["control_items"].queryset = equipment.control_items.filter(active=True)
        if not self.is_bound:
            from django.utils import timezone
            self.initial["next_due_date"] = jdatetime.date.fromgregorian(date=timezone.localdate()).strftime("%Y/%m/%d")

    def clean_next_due_date(self):
        raw = self.cleaned_data["next_due_date"].translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789")).replace("-", "/")
        try:
            year, month, day = [int(part) for part in raw.split("/")]
            return jdatetime.date(year, month, day).togregorian()
        except (ValueError, TypeError):
            raise forms.ValidationError("تاریخ را به شکل ۱۴۰۵/۰۷/۰۱ وارد کنید.")
class WorkOrderForm(forms.ModelForm):
    class Meta: model=WorkOrder; fields=["equipment","title","description","priority","status","downtime_hours","cost","action_taken"]; widgets={"description":forms.Textarea(attrs={"rows":4}),"action_taken":forms.Textarea(attrs={"rows":3})}


class AppUserForm(UserCreationForm):
    role = forms.ModelChoiceField(queryset=Group.objects.all(), label="سطح دسترسی")
    class Meta:
        model = User
        fields = ["username", "first_name", "last_name", "email"]

    def save(self, commit=True):
        user = super().save(commit=commit)
        if commit:
            user.groups.add(self.cleaned_data["role"])
        return user
