from django.contrib import admin
from .models import *
class ChecklistItemInline(admin.TabularInline): model=ChecklistItem; extra=1
@admin.register(ChecklistTemplate)
class ChecklistTemplateAdmin(admin.ModelAdmin): list_display=("name","category","active"); inlines=[ChecklistItemInline]
@admin.register(Equipment)
class EquipmentAdmin(admin.ModelAdmin): list_display=("code","name","category","location","criticality","status"); list_filter=("category","criticality","status"); search_fields=("code","name")
@admin.register(EquipmentControlItem)
class EquipmentControlItemAdmin(admin.ModelAdmin): list_display=("equipment", "title", "frequency", "next_due_date", "active"); list_filter=("frequency", "active"); search_fields=("equipment__name", "title")
@admin.register(WorkOrder)
class WorkOrderAdmin(admin.ModelAdmin): list_display=("id","title","equipment","repair_method","priority","status","reported_at"); list_filter=("repair_method","priority","status")
@admin.register(ExternalRepairRecord)
class ExternalRepairRecordAdmin(admin.ModelAdmin): list_display=("work_order","repair_shop","sent_out_date","returned_date","quality_status"); list_filter=("quality_status","repair_shop"); search_fields=("work_order__equipment__name","work_order__equipment__code","repair_shop")
admin.site.register([EquipmentCategory,EquipmentControlLog,EquipmentSupply,EquipmentSupplyTransaction,MaintenancePlan,Inspection,InspectionResult])
