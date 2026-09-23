from django.db import migrations


def copy_existing_plan_items(apps, schema_editor):
    MaintenancePlan = apps.get_model("maintenance", "MaintenancePlan")
    EquipmentControlItem = apps.get_model("maintenance", "EquipmentControlItem")

    for plan in MaintenancePlan.objects.select_related("checklist").prefetch_related("checklist__items"):
        for checklist_item in plan.checklist.items.all():
            exists = EquipmentControlItem.objects.filter(
                equipment_id=plan.equipment_id,
                title=checklist_item.title,
            ).exists()
            if not exists:
                EquipmentControlItem.objects.create(
                    equipment_id=plan.equipment_id,
                    title=checklist_item.title,
                    help_text=checklist_item.help_text,
                    frequency=plan.frequency,
                    next_due_date=plan.next_due_date,
                    active=plan.active,
                    order=checklist_item.order,
                )


class Migration(migrations.Migration):
    dependencies = [("maintenance", "0002_equipmentcontrolitem_equipmentcontrollog")]

    operations = [migrations.RunPython(copy_existing_plan_items, migrations.RunPython.noop)]
