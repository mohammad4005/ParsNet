from django.db import models
from django.utils import timezone


class EquipmentCategory(models.Model):
    name = models.CharField("نام دسته", max_length=100, unique=True)
    class Meta: verbose_name = "دسته تجهیز"; verbose_name_plural = "دسته‌های تجهیز"
    def __str__(self): return self.name


class Equipment(models.Model):
    class Criticality(models.TextChoices): LOW="low","کم"; MEDIUM="medium","متوسط"; HIGH="high","بحرانی"
    class Status(models.TextChoices): ACTIVE="active","فعال"; OUT_OF_SERVICE="out","خارج از سرویس"; STOPPED="stopped","متوقف"
    code=models.CharField("کد تجهیز",max_length=40,unique=True); name=models.CharField("نام تجهیز",max_length=160)
    category=models.ForeignKey(EquipmentCategory,verbose_name="دسته",on_delete=models.PROTECT); location=models.CharField("محل استقرار",max_length=150,blank=True)
    operating_unit=models.CharField("واحد بهره‌بردار",max_length=150,blank=True); manufacturer=models.CharField("سازنده",max_length=120,blank=True)
    model_number=models.CharField("مدل",max_length=100,blank=True); serial_number=models.CharField("شماره سریال",max_length=100,blank=True); capacity=models.CharField("ظرفیت",max_length=100,blank=True)
    criticality=models.CharField("درجه اهمیت",max_length=10,choices=Criticality.choices,default=Criticality.MEDIUM); status=models.CharField("وضعیت",max_length=10,choices=Status.choices,default=Status.ACTIVE)
    created_at=models.DateTimeField(auto_now_add=True)
    class Meta: verbose_name="تجهیز"; verbose_name_plural="تجهیزات"; ordering=["code"]
    def __str__(self): return f"{self.code} - {self.name}"


class EquipmentControlItem(models.Model):
    """A recurring control belonging to one specific piece of equipment."""
    class Frequency(models.TextChoices):
        DAILY = "daily", "روزانه"
        WEEKLY = "weekly", "هفتگی"
        BIWEEKLY = "biweekly", "هر دو هفته"
        MONTHLY = "monthly", "ماهانه"
        BIMONTHLY = "bimonthly", "هر دو ماه"
        QUARTERLY = "quarterly", "سه‌ماهه"
        SEMIANNUAL = "semiannual", "شش‌ماهه"
        ANNUAL = "annual", "سالانه"

    equipment = models.ForeignKey(Equipment, related_name="control_items", on_delete=models.CASCADE, verbose_name="تجهیز")
    title = models.CharField("مورد کنترل", max_length=255)
    help_text = models.CharField("راهنما", max_length=255, blank=True)
    frequency = models.CharField("تناوب انجام", max_length=20, choices=Frequency.choices, default=Frequency.MONTHLY)
    next_due_date = models.DateField("تاریخ انجام بعدی", default=timezone.localdate)
    active = models.BooleanField("فعال", default=True)
    order = models.PositiveIntegerField("ترتیب", default=1)

    class Meta:
        verbose_name = "مورد کنترل تجهیز"
        verbose_name_plural = "موارد کنترل تجهیزات"
        ordering = ["order", "id"]

    def __str__(self):
        return f"{self.equipment} — {self.title}"


class EquipmentControlLog(models.Model):
    class Result(models.TextChoices):
        PASS = "pass", "تأیید شد"
        ISSUE = "issue", "مشکل دارد"
        ACTION = "action", "نیاز به اقدام"
        NA = "na", "قابل بررسی نبود"

    control_item = models.ForeignKey(EquipmentControlItem, related_name="logs", on_delete=models.CASCADE, verbose_name="مورد کنترل")
    result = models.CharField("نتیجه", max_length=10, choices=Result.choices)
    note = models.CharField("توضیح", max_length=300, blank=True)
    performed_at = models.DateTimeField("زمان ثبت", default=timezone.now)
    work_order = models.ForeignKey("WorkOrder", null=True, blank=True, on_delete=models.SET_NULL, verbose_name="درخواست تعمیر ایجادشده")

    class Meta:
        verbose_name = "ثبت کنترل تجهیز"
        verbose_name_plural = "ثبت‌های کنترل تجهیزات"
        ordering = ["-performed_at"]


class EquipmentSupply(models.Model):
    equipment = models.ForeignKey(Equipment, related_name="supplies", on_delete=models.CASCADE, verbose_name="تجهیز")
    name = models.CharField("نام وسیله یا قطعه", max_length=160)
    unit = models.CharField("واحد شمارش", max_length=30, default="عدد")
    stock_quantity = models.PositiveIntegerField("موجودی انبار", default=0)
    minimum_quantity = models.PositiveIntegerField("حداقل موجودی مورد نیاز", default=1)

    class Meta:
        verbose_name = "وسیله مورد نیاز تجهیز"
        verbose_name_plural = "وسایل مورد نیاز تجهیزات"
        ordering = ["name"]
        constraints = [models.UniqueConstraint(fields=["equipment", "name"], name="unique_equipment_supply")]

    @property
    def is_low_stock(self):
        return self.stock_quantity < self.minimum_quantity

    def __str__(self):
        return f"{self.name} — {self.equipment}"


class EquipmentSupplyTransaction(models.Model):
    class Operation(models.TextChoices):
        ADD = "add", "افزایش موجودی"
        CONSUME = "consume", "مصرف"

    supply = models.ForeignKey(EquipmentSupply, related_name="transactions", on_delete=models.CASCADE, verbose_name="وسیله")
    operation = models.CharField("نوع عملیات", max_length=10, choices=Operation.choices)
    quantity = models.PositiveIntegerField("تعداد")
    performed_by = models.ForeignKey("auth.User", null=True, on_delete=models.SET_NULL, verbose_name="ثبت‌کننده")
    created_at = models.DateTimeField("زمان ثبت", default=timezone.now)

    class Meta:
        verbose_name = "گردش موجودی تجهیز"
        verbose_name_plural = "گردش موجودی تجهیزات"
        ordering = ["-created_at"]


class ChecklistTemplate(models.Model):
    name=models.CharField("نام چک‌لیست",max_length=150); category=models.ForeignKey(EquipmentCategory,verbose_name="دسته تجهیز",on_delete=models.CASCADE,null=True,blank=True); active=models.BooleanField("فعال",default=True)
    class Meta: verbose_name="الگوی چک‌لیست"; verbose_name_plural="الگوهای چک‌لیست"
    def __str__(self): return self.name


class ChecklistItem(models.Model):
    template=models.ForeignKey(ChecklistTemplate,related_name="items",on_delete=models.CASCADE); title=models.CharField("مورد کنترل",max_length=255); help_text=models.CharField("راهنما",max_length=255,blank=True); order=models.PositiveIntegerField("ترتیب",default=1); required=models.BooleanField("اجباری",default=True)
    class Meta: verbose_name="مورد چک‌لیست"; verbose_name_plural="موارد چک‌لیست"; ordering=["order","id"]
    def __str__(self): return self.title


class MaintenancePlan(models.Model):
    class Frequency(models.TextChoices): DAILY="daily","روزانه"; WEEKLY="weekly","هفتگی"; BIWEEKLY="biweekly","هر دو هفته"; MONTHLY="monthly","ماهانه"; BIMONTHLY="bimonthly","هر دو ماه"; QUARTERLY="quarterly","سه‌ماهه"; SEMIANNUAL="semiannual","شش‌ماهه"; ANNUAL="annual","سالانه"
    service_name=models.CharField("نام برنامه سرویس",max_length=150,blank=True)
    equipment=models.ForeignKey(Equipment,verbose_name="تجهیز",on_delete=models.CASCADE); checklist=models.ForeignKey(ChecklistTemplate,verbose_name="چک‌لیست",on_delete=models.PROTECT); frequency=models.CharField("تناوب",max_length=20,choices=Frequency.choices); next_due_date=models.DateField("تاریخ سرویس بعدی"); active=models.BooleanField("فعال",default=True)
    class Meta: verbose_name="برنامه سرویس"; verbose_name_plural="برنامه‌های سرویس"; ordering=["next_due_date"]

    @property
    def display_name(self):
        return self.service_name or self.checklist.name


class WorkOrder(models.Model):
    class Priority(models.TextChoices): NORMAL="normal","عادی"; URGENT="urgent","اضطراری"; LONG_TERM="long","درازمدت"
    class Status(models.TextChoices): NEW="new","جدید"; IN_PROGRESS="progress","در حال انجام"; DONE="done","تکمیل‌شده"
    equipment=models.ForeignKey(Equipment,verbose_name="تجهیز",on_delete=models.PROTECT); title=models.CharField("عنوان درخواست",max_length=180); description=models.TextField("شرح مشکل"); priority=models.CharField("اولویت",max_length=10,choices=Priority.choices,default=Priority.NORMAL); status=models.CharField("وضعیت",max_length=12,choices=Status.choices,default=Status.NEW)
    reported_at=models.DateTimeField("زمان اعلام",default=timezone.now); downtime_hours=models.DecimalField("مدت توقف (ساعت)",max_digits=7,decimal_places=2,default=0); cost=models.DecimalField("هزینه تعمیرات",max_digits=14,decimal_places=0,default=0); action_taken=models.TextField("اقدام انجام‌شده",blank=True); completed_at=models.DateTimeField("زمان اتمام",null=True,blank=True)
    class Meta: verbose_name="درخواست کار"; verbose_name_plural="درخواست‌های کار"; ordering=["-reported_at"]


class Inspection(models.Model):
    plan=models.ForeignKey(MaintenancePlan,on_delete=models.CASCADE); performed_at=models.DateTimeField(default=timezone.now); notes=models.TextField(blank=True)
    performed_by=models.ForeignKey("auth.User",null=True,blank=True,on_delete=models.SET_NULL,verbose_name="مسئول انجام")


class InspectionResult(models.Model):
    class Result(models.TextChoices): PASS="pass","تأیید شد"; ISSUE="issue","مشکل دارد"; ACTION="action","نیاز به اقدام"; NA="na","قابل بررسی نبود"
    inspection=models.ForeignKey(Inspection,related_name="results",on_delete=models.CASCADE); item=models.ForeignKey(ChecklistItem,on_delete=models.PROTECT); result=models.CharField(max_length=10,choices=Result.choices); note=models.CharField(max_length=300,blank=True)
