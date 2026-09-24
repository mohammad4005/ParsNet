from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db.models.deletion import ProtectedError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import Equipment, EquipmentCategory, ExternalRepairRecord, WorkOrder


class RepairWorkflowTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="repair-user", password="test-pass")
        self.client.force_login(self.user)
        category = EquipmentCategory.objects.create(name="دسته آزمون")
        self.equipment = Equipment.objects.create(code="TEST-01", name="تجهیز آزمایشی", category=category)

    def test_external_repair_trip_is_saved_and_protected(self):
        order = WorkOrder.objects.create(
            equipment=self.equipment,
            title="خرابی آزمایشی",
            description="شرح خرابی",
        )
        progress = self.client.post(reverse("work_order_update", args=[order.pk]), {
            "repair_method": WorkOrder.RepairMethod.EXTERNAL,
            "status": WorkOrder.Status.IN_PROGRESS,
            "action_taken": "ارسال به تعمیرگاه",
            "downtime_hours": "0",
            "cost": "0",
        })
        self.assertRedirects(progress, reverse("work_order_detail", args=[order.pk]))
        order.refresh_from_db()
        self.assertEqual(order.repair_method, WorkOrder.RepairMethod.EXTERNAL)
        response = self.client.post(reverse("external_repair_update", args=[order.pk]), {
            "repair_shop": "تعمیرگاه نمونه",
            "sent_out_date": "1405/07/01",
            "returned_date": "1405/07/02",
            "repair_description": "تعویض قطعه معیوب",
            "quality_status": ExternalRepairRecord.QualityStatus.ACCEPTED,
            "quality_note": "کنترل ورودی تأیید شد",
        })
        self.assertRedirects(response, reverse("work_order_detail", args=[order.pk]))
        order.refresh_from_db()
        record = order.external_repair
        self.assertEqual(order.status, WorkOrder.Status.DONE)
        self.assertEqual(record.repair_shop, "تعمیرگاه نمونه")
        self.assertEqual(record.days_outside, 1)
        with self.assertRaises(ProtectedError):
            order.delete()

    def test_repeat_failure_warning_appears_within_thirty_days(self):
        previous = WorkOrder.objects.create(
            equipment=self.equipment,
            title="تعمیر قبلی",
            description="تعمیر شد",
            repair_method=WorkOrder.RepairMethod.INTERNAL,
            status=WorkOrder.Status.DONE,
            completed_at=timezone.now() - timedelta(days=14),
            reported_at=timezone.now() - timedelta(days=15),
        )
        current = WorkOrder.objects.create(
            equipment=self.equipment,
            title="خرابی مجدد",
            description="دوباره خراب شد",
            reported_at=timezone.now(),
        )
        response = self.client.get(reverse("work_order_detail", args=[current.pk]))
        self.assertContains(response, "هشدار خرابی تکراری")
        self.assertContains(response, "14 روز")
        self.assertContains(response, previous.title)
        list_response = self.client.get(reverse("work_order_list"))
        self.assertEqual(list_response.status_code, 200)
        self.assertContains(list_response, current.title)
