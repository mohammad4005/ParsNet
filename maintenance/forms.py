from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import Group, User
import jdatetime
from .models import Equipment, EquipmentCategory, EquipmentControlItem, EquipmentSupply, ExternalRepairRecord, MaintenancePlan, WorkOrder


JALALI_DATE_WIDGET = forms.TextInput(attrs={
    "class": "jalali-date-input",
    "readonly": "readonly",
    "autocomplete": "off",
    "placeholder": "انتخاب از تقویم شمسی",
})
class EquipmentForm(forms.ModelForm):
    class Meta: model=Equipment; fields=["code","name","category","location","operating_unit","manufacturer","model_number","serial_number","capacity","criticality","status"]


class EquipmentCategoryForm(forms.ModelForm):
    class Meta:
        model = EquipmentCategory
        fields = ["name"]


class EquipmentControlItemForm(forms.ModelForm):
    next_due_date = forms.CharField(label="اولین تاریخ انجام", widget=JALALI_DATE_WIDGET)

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
    next_due_date = forms.CharField(label="تاریخ سرویس بعدی", widget=JALALI_DATE_WIDGET)
    class Meta: model=MaintenancePlan; fields=["equipment","checklist","frequency","next_due_date","active"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["equipment"].label = "تجهیزات"
        if self.instance and self.instance.next_due_date:
            self.initial["next_due_date"] = jdatetime.date.fromgregorian(date=self.instance.next_due_date).strftime("%Y/%m/%d")

    def clean_next_due_date(self):
        raw = self.cleaned_data["next_due_date"].translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789")).replace("-", "/")
        try:
            year, month, day = [int(part) for part in raw.split("/")]
            return jdatetime.date(year, month, day).togregorian()
        except (ValueError, TypeError):
            raise forms.ValidationError("تاریخ را به شکل ۱۴۰۵/۰۷/۰۱ وارد کنید.")


class ControlItemMultipleChoiceField(forms.ModelMultipleChoiceField):
    def label_from_instance(self, obj):
        return f"{obj.title} — {obj.get_frequency_display()}"


class EquipmentServicePlanForm(forms.Form):
    name = forms.CharField(label="نام برنامه سرویس", max_length=150, help_text="مثلاً بازدید هفتگی جرثقیل")
    frequency = forms.ChoiceField(label="تناوب اجرا", choices=MaintenancePlan.Frequency.choices)
    next_due_date = forms.CharField(label="اولین تاریخ اجرا", widget=JALALI_DATE_WIDGET)
    control_items = ControlItemMultipleChoiceField(
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


class EquipmentSupplyForm(forms.ModelForm):
    class Meta:
        model = EquipmentSupply
        fields = ["name", "unit", "stock_quantity", "minimum_quantity"]

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("minimum_quantity") is not None and cleaned.get("minimum_quantity") < 1:
            self.add_error("minimum_quantity", "حداقل موجودی باید دست‌کم یک باشد.")
        return cleaned


class MaintenanceReportFilterForm(forms.Form):
    STATUS_CHOICES = [
        ("all", "همه کارها"),
        ("completed", "فقط انجام‌شده"),
        ("overdue", "فقط عقب‌افتاده"),
    ]
    GROUP_CHOICES = [
        ("overall", "گزارش کلی و جامع"),
        ("equipment", "تفکیک‌شده برحسب دستگاه"),
        ("category", "تفکیک‌شده برحسب دسته‌بندی"),
    ]

    start_date = forms.CharField(label="از تاریخ", widget=JALALI_DATE_WIDGET)
    end_date = forms.CharField(label="تا تاریخ", widget=JALALI_DATE_WIDGET)
    status = forms.ChoiceField(label="وضعیت کار", choices=STATUS_CHOICES, initial="all")
    group_by = forms.ChoiceField(label="نوع گزارش", choices=GROUP_CHOICES, initial="overall")
    equipment = forms.ModelChoiceField(label="فقط این دستگاه", queryset=Equipment.objects.all(), required=False, empty_label="همه دستگاه‌ها")
    category = forms.ModelChoiceField(label="فقط این دسته", queryset=EquipmentCategory.objects.all(), required=False, empty_label="همه دسته‌ها")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.is_bound:
            from django.utils import timezone
            today = jdatetime.date.fromgregorian(date=timezone.localdate())
            self.initial["start_date"] = f"{today.year:04d}/{today.month:02d}/01"
            self.initial["end_date"] = today.strftime("%Y/%m/%d")

    @staticmethod
    def _clean_jalali(raw):
        value = raw.translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789")).replace("-", "/")
        year, month, day = [int(part) for part in value.split("/")]
        return jdatetime.date(year, month, day).togregorian()

    def clean_start_date(self):
        try: return self._clean_jalali(self.cleaned_data["start_date"])
        except (ValueError, TypeError): raise forms.ValidationError("تاریخ شروع را از تقویم انتخاب کنید.")

    def clean_end_date(self):
        try: return self._clean_jalali(self.cleaned_data["end_date"])
        except (ValueError, TypeError): raise forms.ValidationError("تاریخ پایان را از تقویم انتخاب کنید.")

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("start_date") and cleaned.get("end_date") and cleaned["start_date"] > cleaned["end_date"]:
            self.add_error("end_date", "تاریخ پایان باید بعد از تاریخ شروع باشد.")
        return cleaned


class ServiceWorksheetFilterForm(forms.Form):
    start_date = forms.CharField(label="از تاریخ", widget=JALALI_DATE_WIDGET)
    end_date = forms.CharField(label="تا تاریخ", widget=JALALI_DATE_WIDGET)
    equipment = forms.ModelChoiceField(label="دستگاه", queryset=Equipment.objects.all(), required=False, empty_label="همه دستگاه‌ها")
    category = forms.ModelChoiceField(label="دسته‌بندی", queryset=EquipmentCategory.objects.all(), required=False, empty_label="همه دسته‌ها")

    @staticmethod
    def _clean_jalali(raw):
        value = raw.translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789")).replace("-", "/")
        year, month, day = [int(part) for part in value.split("/")]
        return jdatetime.date(year, month, day).togregorian()

    def clean_start_date(self):
        try:
            return self._clean_jalali(self.cleaned_data["start_date"])
        except (ValueError, TypeError):
            raise forms.ValidationError("تاریخ شروع را از تقویم شمسی انتخاب کنید.")

    def clean_end_date(self):
        try:
            return self._clean_jalali(self.cleaned_data["end_date"])
        except (ValueError, TypeError):
            raise forms.ValidationError("تاریخ پایان را از تقویم شمسی انتخاب کنید.")

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("start_date") and cleaned.get("end_date") and cleaned["start_date"] > cleaned["end_date"]:
            self.add_error("end_date", "تاریخ پایان باید بعد از تاریخ شروع باشد.")
        return cleaned


class WorkOrderForm(forms.ModelForm):
    class Meta:
        model = WorkOrder
        fields = ["equipment", "title", "description", "priority", "repair_method", "status", "downtime_hours", "cost", "action_taken"]
        widgets = {"description": forms.Textarea(attrs={"rows": 4}), "action_taken": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["equipment"].label = "تجهیزات"


class WorkOrderProgressForm(forms.ModelForm):
    class Meta:
        model = WorkOrder
        fields = ["repair_method", "status", "action_taken", "downtime_hours", "cost"]
        widgets = {"action_taken": forms.Textarea(attrs={"rows": 3, "placeholder": "شرح اقدام واحد تعمیرات یا تعمیر انجام‌شده داخل شرکت"})}


class ExternalRepairForm(forms.ModelForm):
    sent_out_date = forms.CharField(label="تاریخ خروج از شرکت", required=False, widget=JALALI_DATE_WIDGET)
    returned_date = forms.CharField(label="تاریخ ورود مجدد به شرکت", required=False, widget=JALALI_DATE_WIDGET)

    class Meta:
        model = ExternalRepairRecord
        fields = ["repair_shop", "sent_out_date", "returned_date", "repair_description", "quality_status", "quality_note"]
        widgets = {
            "repair_description": forms.Textarea(attrs={"rows": 3}),
            "quality_note": forms.Textarea(attrs={"rows": 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name in ("sent_out_date", "returned_date"):
            date_value = self.initial.get(field_name) or getattr(self.instance, field_name, None)
            if date_value:
                self.initial[field_name] = jdatetime.date.fromgregorian(date=date_value).strftime("%Y/%m/%d")

    @staticmethod
    def _clean_optional_jalali(raw):
        if not raw:
            return None
        value = raw.translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789")).replace("-", "/")
        year, month, day = [int(part) for part in value.split("/")]
        return jdatetime.date(year, month, day).togregorian()

    def clean_sent_out_date(self):
        try:
            return self._clean_optional_jalali(self.cleaned_data.get("sent_out_date"))
        except (ValueError, TypeError):
            raise forms.ValidationError("تاریخ خروج را از تقویم شمسی انتخاب کنید.")

    def clean_returned_date(self):
        try:
            return self._clean_optional_jalali(self.cleaned_data.get("returned_date"))
        except (ValueError, TypeError):
            raise forms.ValidationError("تاریخ ورود را از تقویم شمسی انتخاب کنید.")

    def clean(self):
        cleaned = super().clean()
        sent = cleaned.get("sent_out_date")
        returned = cleaned.get("returned_date")
        if returned and not sent:
            self.add_error("sent_out_date", "ابتدا تاریخ خروج تجهیزات را ثبت کنید.")
        if sent and returned and returned < sent:
            self.add_error("returned_date", "تاریخ ورود نمی‌تواند قبل از تاریخ خروج باشد.")
        if cleaned.get("quality_status") != ExternalRepairRecord.QualityStatus.PENDING and not returned:
            self.add_error("quality_status", "نتیجه کنترل کیفیت پس از ثبت تاریخ ورود قابل انتخاب است.")
        return cleaned


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
