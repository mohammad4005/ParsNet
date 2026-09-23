from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from maintenance.models import (
    ChecklistItem,
    ChecklistTemplate,
    Equipment,
    EquipmentCategory,
    EquipmentControlItem,
    EquipmentControlLog,
    EquipmentSupply,
    EquipmentSupplyTransaction,
    Inspection,
    InspectionResult,
    MaintenancePlan,
    WorkOrder,
)


class Command(BaseCommand):
    help = "حذف کامل اطلاعات عملیاتی پارس‌نت با حفظ کاربران و سطوح دسترسی"

    def add_arguments(self, parser):
        parser.add_argument(
            "--confirm",
            help="برای اجرای حذف باید عبارت CLEAR-PARSNET وارد شود.",
        )
        parser.add_argument(
            "--show-counts",
            action="store_true",
            help="فقط تعداد رکوردهای قابل حذف را نمایش می‌دهد.",
        )

    def handle(self, *args, **options):
        models = [
            EquipmentCategory,
            Equipment,
            EquipmentControlItem,
            EquipmentControlLog,
            EquipmentSupply,
            EquipmentSupplyTransaction,
            ChecklistTemplate,
            ChecklistItem,
            MaintenancePlan,
            Inspection,
            InspectionResult,
            WorkOrder,
        ]
        counts = {model._meta.verbose_name_plural: model.objects.count() for model in models}
        total = sum(counts.values())

        if options["show_counts"]:
            for label, count in counts.items():
                self.stdout.write(f"{label}: {count}")
            self.stdout.write(self.style.WARNING(f"مجموع رکوردهای عملیاتی: {total}"))
            return

        if options["confirm"] != "CLEAR-PARSNET":
            raise CommandError("حذف اجرا نشد. از --confirm CLEAR-PARSNET استفاده کنید.")

        with transaction.atomic():
            InspectionResult.objects.all().delete()
            Inspection.objects.all().delete()
            EquipmentControlLog.objects.all().delete()
            EquipmentSupplyTransaction.objects.all().delete()
            WorkOrder.objects.all().delete()
            MaintenancePlan.objects.all().delete()
            EquipmentControlItem.objects.all().delete()
            EquipmentSupply.objects.all().delete()
            Equipment.objects.all().delete()
            ChecklistItem.objects.all().delete()
            ChecklistTemplate.objects.all().delete()
            EquipmentCategory.objects.all().delete()

        self.stdout.write(self.style.SUCCESS(f"{total} رکورد عملیاتی حذف شد؛ کاربران و دسترسی‌ها حفظ شدند."))
