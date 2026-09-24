from collections import defaultdict
from datetime import timedelta

from django.utils import timezone

from .models import EquipmentControlItem, EquipmentControlLog, Inspection, MaintenancePlan, WorkOrder


SERVICE_FREQUENCY_DAYS = {
    "daily": 1, "weekly": 7, "biweekly": 14, "monthly": 30,
    "bimonthly": 60, "quarterly": 91, "semiannual": 182, "annual": 365,
}


def build_service_worksheet_schedule(cleaned):
    start = cleaned["start_date"]
    end = cleaned["end_date"]
    plans = MaintenancePlan.objects.filter(active=True).select_related(
        "equipment__category", "checklist"
    ).prefetch_related("checklist__items")
    if cleaned.get("equipment"):
        plans = plans.filter(equipment=cleaned["equipment"])
    if cleaned.get("category"):
        plans = plans.filter(equipment__category=cleaned["category"])

    schedule = []
    for plan in plans:
        due_date = plan.next_due_date
        step = timedelta(days=SERVICE_FREQUENCY_DAYS[plan.frequency])
        if due_date < start:
            step_days = SERVICE_FREQUENCY_DAYS[plan.frequency]
            jumps = ((start - due_date).days + step_days - 1) // step_days
            due_date += timedelta(days=jumps * step_days)
        while due_date <= end:
            schedule.append({"plan": plan, "due_date": due_date})
            due_date += step
    schedule.sort(key=lambda row: (row["due_date"], row["plan"].equipment.code, row["plan"].display_name))
    return schedule


def _apply_equipment_filters(queryset, path, equipment, category):
    if equipment:
        queryset = queryset.filter(**{path: equipment})
    if category:
        queryset = queryset.filter(**{f"{path}__category": category})
    return queryset


def build_maintenance_report(cleaned):
    start = cleaned["start_date"]
    end = cleaned["end_date"]
    equipment = cleaned.get("equipment")
    category = cleaned.get("category")
    status = cleaned.get("status", "all")
    group_by = cleaned.get("group_by", "overall")
    overdue_until = min(end, timezone.localdate() - timedelta(days=1))

    completed_services = Inspection.objects.filter(
        performed_at__date__range=(start, end)
    ).select_related("plan__equipment__category", "plan__checklist", "performed_by")
    completed_services = _apply_equipment_filters(completed_services, "plan__equipment", equipment, category)

    completed_controls = EquipmentControlLog.objects.filter(
        performed_at__date__range=(start, end)
    ).select_related("control_item__equipment__category", "work_order")
    completed_controls = _apply_equipment_filters(completed_controls, "control_item__equipment", equipment, category)

    overdue_services = MaintenancePlan.objects.filter(
        active=True, next_due_date__range=(start, overdue_until)
    ).select_related("equipment__category", "checklist")
    overdue_services = _apply_equipment_filters(overdue_services, "equipment", equipment, category)

    overdue_controls = EquipmentControlItem.objects.filter(
        active=True, next_due_date__range=(start, overdue_until)
    ).select_related("equipment__category")
    overdue_controls = _apply_equipment_filters(overdue_controls, "equipment", equipment, category)

    work_orders = WorkOrder.objects.filter(
        reported_at__date__range=(start, end)
    ).select_related("equipment__category")
    work_orders = _apply_equipment_filters(work_orders, "equipment", equipment, category)

    completed_services = list(completed_services)
    completed_controls = list(completed_controls)
    overdue_services = list(overdue_services)
    overdue_controls = list(overdue_controls)
    work_orders = list(work_orders)
    today = timezone.localdate()
    for row in overdue_services + overdue_controls:
        row.days_overdue = max(0, (today - row.next_due_date).days)

    groups = defaultdict(lambda: {
        "completed_services": 0, "completed_controls": 0,
        "overdue_services": 0, "overdue_controls": 0, "work_orders": 0,
    })

    def identity(equipment_obj):
        if group_by == "equipment": return equipment_obj.name
        if group_by == "category": return equipment_obj.category.name
        return "مجموع کل مجموعه"

    if status in {"all", "completed"}:
        for row in completed_services: groups[identity(row.plan.equipment)]["completed_services"] += 1
        for row in completed_controls: groups[identity(row.control_item.equipment)]["completed_controls"] += 1
    if status in {"all", "overdue"}:
        for row in overdue_services: groups[identity(row.equipment)]["overdue_services"] += 1
        for row in overdue_controls: groups[identity(row.equipment)]["overdue_controls"] += 1
    for row in work_orders: groups[identity(row.equipment)]["work_orders"] += 1

    group_rows = []
    show_completed = status in {"all", "completed"}
    show_overdue = status in {"all", "overdue"}
    for label, values in sorted(groups.items()):
        values["label"] = label
        values["completed_total"] = (
            values["completed_services"] + values["completed_controls"]
        ) if show_completed else 0
        values["overdue_total"] = (
            values["overdue_services"] + values["overdue_controls"]
        ) if show_overdue else 0
        group_rows.append(values)

    return {
        "start_date": start,
        "end_date": end,
        "status": status,
        "group_by": group_by,
        "show_completed": show_completed,
        "show_overdue": show_overdue,
        "completed_services": completed_services if show_completed else [],
        "completed_controls": completed_controls if show_completed else [],
        "overdue_services": overdue_services if show_overdue else [],
        "overdue_controls": overdue_controls if show_overdue else [],
        "work_orders": work_orders,
        "group_rows": group_rows,
        "completed_total": (len(completed_services) + len(completed_controls)) if show_completed else 0,
        "overdue_total": (len(overdue_services) + len(overdue_controls)) if show_overdue else 0,
        "work_orders_total": len(work_orders),
        "equipment_filter": equipment,
        "category_filter": category,
    }
