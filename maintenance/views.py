from datetime import timedelta
from decimal import Decimal
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db.models import Count,Sum,Min
from django.shortcuts import get_object_or_404,redirect,render
from django.utils import timezone
from .forms import AppUserForm,EquipmentCategoryForm,EquipmentControlItemForm,EquipmentForm,EquipmentServicePlanForm,MaintenancePlanForm,WorkOrderForm
from .models import ChecklistItem,ChecklistTemplate,Equipment,EquipmentCategory,EquipmentControlItem,EquipmentControlLog,Inspection,InspectionResult,MaintenancePlan,WorkOrder
manager_required = user_passes_test(lambda u: u.is_superuser or u.groups.filter(name__in=["مدیر اصلی", "سرپرست نت"]).exists())

CONTROL_FREQUENCY_DAYS = {"daily": 1, "weekly": 7, "biweekly": 14, "monthly": 30, "bimonthly": 60, "quarterly": 91, "semiannual": 182, "annual": 365}

@login_required
def dashboard(request):
    today=timezone.localdate(); due=MaintenancePlan.objects.filter(active=True,next_due_date__lte=today).select_related("equipment","checklist")
    due_controls=EquipmentControlItem.objects.filter(active=True,next_due_date__lte=today).select_related("equipment")
    return render(request,"maintenance/dashboard.html",{"equipment_count":Equipment.objects.count(),"critical_count":Equipment.objects.filter(criticality="high").count(),"open_orders":WorkOrder.objects.exclude(status="done").count(),"due_plans":due[:6],"due_controls":due_controls[:6],"due_controls_count":due_controls.count(),"recent_orders":WorkOrder.objects.select_related("equipment")[:6]})
@login_required
def equipment_list(request):
    items=Equipment.objects.select_related("category");q=request.GET.get("q","").strip()
    if q: items=items.filter(name__icontains=q)|items.filter(code__icontains=q)
    return render(request,"maintenance/equipment_list.html",{"items":items,"query":q})
@login_required
@manager_required
def equipment_create(request):
    form=EquipmentForm(request.POST or None)
    if request.method=="POST" and form.is_valid(): form.save();messages.success(request,"تجهیز جدید ثبت شد.");return redirect("equipment_list")
    return render(request,"maintenance/form.html",{"form":form,"title":"ثبت تجهیز جدید","submit":"ثبت تجهیز"})
@login_required
@manager_required
def category_list(request):
    form = EquipmentCategoryForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save(); messages.success(request, "دسته تجهیز اضافه شد."); return redirect("category_list")
    return render(request, "maintenance/category_list.html", {"form": form, "categories": EquipmentCategory.objects.order_by("name")})
@login_required
def equipment_detail(request,pk):
    equipment=get_object_or_404(Equipment.objects.select_related("category"),pk=pk)
    plans=MaintenancePlan.objects.filter(equipment=equipment).select_related("checklist").prefetch_related("checklist__items")
    items=equipment.control_items.all()
    return render(request,"maintenance/equipment_detail.html",{"equipment":equipment,"plans":plans,"items":items,"today":timezone.localdate(),"control_form":EquipmentControlItemForm(initial={"next_due_date": timezone.localdate()}),"service_plan_form":EquipmentServicePlanForm(equipment=equipment)})
@login_required
@manager_required
def equipment_add_check_item(request,pk):
    equipment=get_object_or_404(Equipment,pk=pk)
    form = EquipmentControlItemForm(request.POST)
    if form.is_valid():
        item=form.save(commit=False); item.equipment=equipment; item.order=equipment.control_items.count()+1; item.save()
        messages.success(request,"مورد کنترل به فهرست همین دستگاه اضافه شد؛ هیچ برنامه سرویس جدیدی ایجاد نشد.")
    else:
        messages.error(request,"مورد کنترل ثبت نشد؛ اطلاعات واردشده را بررسی کنید.")
    return redirect("equipment_detail",pk=equipment.pk)
@login_required
@manager_required
def equipment_create_service_plan(request, pk):
    equipment = get_object_or_404(Equipment, pk=pk)
    form = EquipmentServicePlanForm(request.POST, equipment=equipment)
    if form.is_valid():
        name = form.cleaned_data["name"]
        selected_items = list(form.cleaned_data["control_items"])
        checklist = ChecklistTemplate.objects.create(name=f"{equipment.code} | {name}", category=equipment.category)
        for order, control in enumerate(selected_items, start=1):
            ChecklistItem.objects.create(template=checklist, title=control.title, help_text=control.help_text, order=order)
        MaintenancePlan.objects.create(
            equipment=equipment, checklist=checklist, service_name=name,
            frequency=form.cleaned_data["frequency"], next_due_date=form.cleaned_data["next_due_date"],
        )
        messages.success(request, f"برنامه سرویس «{name}» از {len(selected_items)} مورد کنترل ساخته شد.")
    else:
        messages.error(request, "برنامه سرویس ثبت نشد؛ اطلاعات را بررسی کنید.")
    return redirect("equipment_detail", pk=equipment.pk)
@login_required
def daily_controls(request):
    today=timezone.localdate()
    controls=EquipmentControlItem.objects.filter(active=True,next_due_date__lte=today).select_related("equipment")
    return render(request,"maintenance/daily_controls.html",{"controls":controls,"today":today})
@login_required
def perform_control(request,pk):
    item=get_object_or_404(EquipmentControlItem.objects.select_related("equipment"),pk=pk,active=True)
    if request.method == "POST":
        result=request.POST.get("result")
        note=request.POST.get("note", "").strip()
        if result not in EquipmentControlLog.Result.values:
            messages.error(request, "نتیجه کنترل را انتخاب کنید.")
        else:
            log=EquipmentControlLog.objects.create(control_item=item,result=result,note=note)
            if result in {"issue", "action"}:
                log.work_order=WorkOrder.objects.create(equipment=item.equipment,title=f"پیگیری کنترل: {item.title}",description=(note or f"در کنترل دوره‌ای «{item.title}» نتیجه «{log.get_result_display()}» ثبت شده است."),priority="normal")
                log.save(update_fields=["work_order"])
                messages.warning(request, "کنترل ثبت شد و درخواست تعمیر برای واحد تعمیرات ایجاد شد.")
            else:
                messages.success(request, "کنترل با موفقیت ثبت شد.")
            item.next_due_date = max(item.next_due_date, timezone.localdate()) + timedelta(days=CONTROL_FREQUENCY_DAYS[item.frequency])
            item.save(update_fields=["next_due_date"])
            return redirect("daily_controls")
    return render(request,"maintenance/perform_control.html",{"item":item})
@login_required
def plan_list(request): return render(request,"maintenance/plan_list.html",{"plans":MaintenancePlan.objects.select_related("equipment","checklist")})
@login_required
@manager_required
def plan_create(request):
    form=MaintenancePlanForm(request.POST or None)
    if request.method=="POST" and form.is_valid(): form.save();messages.success(request,"برنامه سرویس ثبت شد.");return redirect("plan_list")
    return render(request,"maintenance/form.html",{"form":form,"title":"تعریف برنامه سرویس","submit":"ثبت برنامه"})
@login_required
def inspect_plan(request,pk):
    plan=get_object_or_404(MaintenancePlan.objects.select_related("equipment","checklist"),pk=pk);items=plan.checklist.items.all()
    if request.method=="POST":
        inspection=Inspection.objects.create(plan=plan,notes=request.POST.get("notes","")); issue=False
        for item in items:
            result=request.POST.get(f"item_{item.id}");note=request.POST.get(f"note_{item.id}","")
            if result: InspectionResult.objects.create(inspection=inspection,item=item,result=result,note=note);issue|=result in {"issue","action"}
        if issue: WorkOrder.objects.create(equipment=plan.equipment,title=f"پیگیری سرویس: {plan.display_name}",description="مورد نیازمند اقدام در چک‌لیست سرویس ثبت شده است.")
        days={"daily":1,"weekly":7,"biweekly":14,"monthly":30,"bimonthly":60,"quarterly":91,"semiannual":182,"annual":365}[plan.frequency];plan.next_due_date+=timedelta(days=days);plan.save(update_fields=["next_due_date"]);messages.success(request,"چک‌لیست ثبت و سرویس بعدی به‌روزرسانی شد.");return redirect("dashboard")
    return render(request,"maintenance/inspection.html",{"plan":plan,"items":items})
@login_required
def work_order_list(request): return render(request,"maintenance/work_order_list.html",{"orders":WorkOrder.objects.select_related("equipment")})
@login_required
def work_order_create(request):
    form=WorkOrderForm(request.POST or None)
    if request.method=="POST" and form.is_valid():
        order=form.save(commit=False)
        if order.status=="done":order.completed_at=timezone.now()
        order.save();messages.success(request,"درخواست تعمیر ثبت شد.");return redirect("work_order_list")
    return render(request,"maintenance/form.html",{"form":form,"title":"ثبت درخواست تعمیر","submit":"ثبت درخواست"})
@login_required
def reports(request):
    rows=WorkOrder.objects.values("equipment__name","equipment__code").annotate(count=Count("id"),downtime=Sum("downtime_hours"),cost=Sum("cost")).order_by("-downtime")[:10]
    today=timezone.localdate(); plans=MaintenancePlan.objects.select_related("equipment","checklist")
    return render(request,"maintenance/reports.html",{"by_equipment":rows,"plans":plans,"equipment_count":Equipment.objects.count(),"scheduled_services":plans.count(),"overdue_services":plans.filter(active=True,next_due_date__lt=today).count(),"total_cost":WorkOrder.objects.aggregate(value=Sum("cost"))["value"] or Decimal("0"),"total_downtime":WorkOrder.objects.aggregate(value=Sum("downtime_hours"))["value"] or Decimal("0"),"completed_services":Inspection.objects.count()})

@login_required
@user_passes_test(lambda u: u.is_superuser)
def user_list(request):
    from django.contrib.auth.models import User
    return render(request,"maintenance/user_list.html",{"users":User.objects.prefetch_related("groups").order_by("username")})

@login_required
@user_passes_test(lambda u: u.is_superuser)
def user_create(request):
    form=AppUserForm(request.POST or None)
    if request.method=="POST" and form.is_valid():
        form.save();messages.success(request,"کاربر جدید با سطح دسترسی مشخص‌شده ایجاد شد.");return redirect("user_list")
    return render(request,"maintenance/form.html",{"form":form,"title":"ساخت کاربر جدید","submit":"ایجاد کاربر"})
