from datetime import timedelta
from urllib.parse import urlencode
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import User
from django.db import transaction
from django.http import HttpResponse
from django.shortcuts import get_object_or_404,redirect,render
from django.utils import timezone
from .forms import AppUserForm,EquipmentCategoryForm,EquipmentControlItemForm,EquipmentForm,EquipmentServicePlanForm,EquipmentSupplyForm,ExternalRepairForm,MaintenancePlanForm,MaintenanceReportFilterForm,ServiceWorksheetFilterForm,WorkOrderForm,WorkOrderProgressForm
from .models import ChecklistItem,ChecklistTemplate,Equipment,EquipmentCategory,EquipmentControlItem,EquipmentControlLog,EquipmentSupply,EquipmentSupplyTransaction,ExternalRepairRecord,Inspection,InspectionResult,MaintenancePlan,WorkOrder
manager_required = user_passes_test(lambda u: u.is_superuser or u.groups.filter(name__in=["مدیر اصلی", "سرپرست نت"]).exists())

CONTROL_FREQUENCY_DAYS = {"daily": 1, "weekly": 7, "biweekly": 14, "monthly": 30, "bimonthly": 60, "quarterly": 91, "semiannual": 182, "annual": 365}


def _decorate_repair_history(orders):
    """Add the latest prior repair and a short-interval repeat warning to work orders."""
    orders = list(orders)
    last_closed = {}
    for order in sorted(orders, key=lambda item: item.reported_at):
        previous_date = last_closed.get(order.equipment_id)
        order.previous_repair_date = previous_date
        order.repeat_after_days = None
        if previous_date:
            days = (order.reported_at.date() - previous_date).days
            if 0 <= days <= 30:
                order.repeat_after_days = days
        try:
            external = order.external_repair
        except ExternalRepairRecord.DoesNotExist:
            external = None
        closed_date = external.returned_date if external and external.returned_date else (order.completed_at.date() if order.completed_at else None)
        if closed_date:
            last_closed[order.equipment_id] = max(last_closed.get(order.equipment_id, closed_date), closed_date)
    return sorted(orders, key=lambda item: item.reported_at, reverse=True)

@login_required
def dashboard(request):
    today=timezone.localdate()
    due=MaintenancePlan.objects.filter(active=True,next_due_date__lte=today).select_related("equipment","checklist")
    due_plans=list(due[:8])
    for plan in due_plans: plan.days_overdue=(today-plan.next_due_date).days
    controls=EquipmentControlItem.objects.filter(active=True,next_due_date__lte=today).select_related("equipment")
    due_controls=list(controls[:8])
    for item in due_controls: item.days_overdue=(today-item.next_due_date).days
    return render(request,"maintenance/dashboard.html",{"equipment_count":Equipment.objects.count(),"critical_count":Equipment.objects.filter(criticality="high").count(),"open_orders":WorkOrder.objects.exclude(status="done").count(),"due_plans":due_plans,"due_plans_count":due.count(),"due_controls":due_controls,"due_controls_count":controls.count(),"recent_orders":WorkOrder.objects.select_related("equipment")[:6]})
@login_required
def equipment_list(request):
    items=Equipment.objects.select_related("category");q=request.GET.get("q","").strip()
    if q: items=items.filter(name__icontains=q)|items.filter(code__icontains=q)
    return render(request,"maintenance/equipment_list.html",{"items":items,"query":q})
@login_required
@manager_required
def equipment_create(request):
    form=EquipmentForm(request.POST or None)
    if request.method=="POST" and form.is_valid(): form.save();messages.success(request,"تجهیزات جدید ثبت شد.");return redirect("equipment_list")
    return render(request,"maintenance/form.html",{"form":form,"title":"ثبت تجهیزات جدید","submit":"ثبت تجهیزات"})
@login_required
@manager_required
def category_list(request):
    form = EquipmentCategoryForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save(); messages.success(request, "دسته تجهیزات اضافه شد."); return redirect("category_list")
    return render(request, "maintenance/category_list.html", {"form": form, "categories": EquipmentCategory.objects.order_by("name")})
@login_required
def equipment_detail(request,pk):
    equipment=get_object_or_404(Equipment.objects.select_related("category"),pk=pk)
    plans=MaintenancePlan.objects.filter(equipment=equipment).select_related("checklist").prefetch_related("checklist__items")
    items=equipment.control_items.all(); supplies=equipment.supplies.all()
    repair_history=_decorate_repair_history(WorkOrder.objects.filter(equipment=equipment).select_related("equipment","external_repair"))[:8]
    return render(request,"maintenance/equipment_detail.html",{"equipment":equipment,"plans":plans,"items":items,"supplies":supplies,"repair_history":repair_history,"today":timezone.localdate(),"control_form":EquipmentControlItemForm(initial={"next_due_date": timezone.localdate()}),"service_plan_form":EquipmentServicePlanForm(equipment=equipment),"supply_form":EquipmentSupplyForm()})
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
def equipment_add_supply(request, pk):
    equipment=get_object_or_404(Equipment,pk=pk)
    form=EquipmentSupplyForm(request.POST)
    if form.is_valid():
        quantity=form.cleaned_data["stock_quantity"]
        supply=EquipmentSupply.objects.filter(equipment=equipment,name__iexact=form.cleaned_data["name"]).first()
        if supply:
            supply.stock_quantity += quantity
            supply.unit=form.cleaned_data["unit"]; supply.minimum_quantity=form.cleaned_data["minimum_quantity"]
            supply.save(update_fields=["stock_quantity","unit","minimum_quantity"])
            message="موجودی وسیله قبلی افزایش یافت."
        else:
            supply=form.save(commit=False); supply.equipment=equipment; supply.save(); message="وسیله مورد نیاز به انبار این دستگاه اضافه شد."
        if quantity:
            EquipmentSupplyTransaction.objects.create(supply=supply,operation="add",quantity=quantity,performed_by=request.user)
        messages.success(request,message)
    else: messages.error(request,"وسیله ثبت نشد؛ اطلاعات را بررسی کنید.")
    return redirect("equipment_detail",pk=equipment.pk)
@login_required
def equipment_adjust_supply(request, pk, supply_pk):
    equipment=get_object_or_404(Equipment,pk=pk)
    try: quantity=int(request.POST.get("quantity",0))
    except (TypeError,ValueError): quantity=0
    operation=request.POST.get("operation")
    if quantity < 1 or operation not in {"add","consume"}:
        messages.error(request,"تعداد معتبر وارد کنید."); return redirect("equipment_detail",pk=equipment.pk)
    with transaction.atomic():
        supply=get_object_or_404(EquipmentSupply.objects.select_for_update(),pk=supply_pk,equipment=equipment)
        if operation == "consume" and quantity > supply.stock_quantity:
            messages.error(request,f"موجودی {supply.name} کافی نیست؛ فقط {supply.stock_quantity} {supply.unit} موجود است.")
            return redirect("equipment_detail",pk=equipment.pk)
        supply.stock_quantity += quantity if operation == "add" else -quantity
        supply.save(update_fields=["stock_quantity"])
        EquipmentSupplyTransaction.objects.create(supply=supply,operation=operation,quantity=quantity,performed_by=request.user)
    if supply.is_low_stock: messages.warning(request,f"هشدار کمبود: موجودی {supply.name} از حداقل مورد نیاز کمتر شده است.")
    else: messages.success(request,"گردش موجودی ثبت شد.")
    return redirect("equipment_detail",pk=equipment.pk)
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
def service_worksheets(request):
    import jdatetime
    from .reporting import build_service_worksheet_schedule,paginate_service_worksheets
    data=request.GET.copy()
    if not data:
        today=timezone.localdate(); end=today+timedelta(days=7)
        data={"start_date":jdatetime.date.fromgregorian(date=today).strftime("%Y/%m/%d"),"end_date":jdatetime.date.fromgregorian(date=end).strftime("%Y/%m/%d")}
    form=ServiceWorksheetFilterForm(data)
    schedule=build_service_worksheet_schedule(form.cleaned_data) if form.is_valid() else []
    worksheet_pages=paginate_service_worksheets(schedule)
    query_string=request.GET.urlencode() if request.GET else urlencode(data)
    return render(request,"maintenance/service_worksheets.html",{"form":form,"schedule":schedule,"worksheet_pages":worksheet_pages,"query_string":query_string})


@login_required
def service_worksheets_pdf(request):
    from .pdf_reports import build_service_worksheet_pdf
    from .reporting import build_service_worksheet_schedule
    form=ServiceWorksheetFilterForm(request.GET)
    if not form.is_valid(): return HttpResponse("فیلتر فرم بازدید معتبر نیست.",status=400,content_type="text/plain; charset=utf-8")
    content=build_service_worksheet_pdf(build_service_worksheet_schedule(form.cleaned_data),form.cleaned_data)
    response=HttpResponse(content,content_type="application/pdf")
    response["Content-Disposition"]='attachment; filename="parsnet-service-worksheets.pdf"'
    return response
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
        performer=User.objects.filter(pk=request.POST.get("performed_by"),is_active=True).first() or request.user
        inspection=Inspection.objects.create(plan=plan,notes=request.POST.get("notes",""),performed_by=performer); issue=False
        for item in items:
            result=request.POST.get(f"item_{item.id}");note=request.POST.get(f"note_{item.id}","")
            if result: InspectionResult.objects.create(inspection=inspection,item=item,result=result,note=note);issue|=result in {"issue","action"}
        if issue: WorkOrder.objects.create(equipment=plan.equipment,title=f"پیگیری سرویس: {plan.display_name}",description="مورد نیازمند اقدام در چک‌لیست سرویس ثبت شده است.")
        days={"daily":1,"weekly":7,"biweekly":14,"monthly":30,"bimonthly":60,"quarterly":91,"semiannual":182,"annual":365}[plan.frequency];plan.next_due_date+=timedelta(days=days);plan.save(update_fields=["next_due_date"]);messages.success(request,"چک‌لیست ثبت و سرویس بعدی به‌روزرسانی شد.");return redirect("dashboard")
    return render(request,"maintenance/inspection.html",{"plan":plan,"items":items,"performers":User.objects.filter(is_active=True).order_by("first_name","last_name","username")})
@login_required
def work_order_list(request):
    orders=_decorate_repair_history(WorkOrder.objects.select_related("equipment","external_repair"))
    return render(request,"maintenance/work_order_list.html",{"orders":orders})
@login_required
def work_order_create(request):
    form=WorkOrderForm(request.POST or None)
    if request.method=="POST" and form.is_valid():
        order=form.save(commit=False)
        if order.status=="done":order.completed_at=timezone.now()
        order.save();messages.success(request,"درخواست تعمیر ثبت شد.");return redirect("work_order_list")
    return render(request,"maintenance/form.html",{"form":form,"title":"ثبت درخواست تعمیر","submit":"ثبت درخواست"})


@login_required
def work_order_detail(request, pk):
    order=get_object_or_404(WorkOrder.objects.select_related("equipment__category","external_repair"),pk=pk)
    equipment_orders=_decorate_repair_history(WorkOrder.objects.filter(equipment=order.equipment).select_related("equipment","external_repair"))
    current=next((item for item in equipment_orders if item.pk == order.pk),order)
    history=equipment_orders[:12]
    try: external=order.external_repair
    except ExternalRepairRecord.DoesNotExist: external=None
    return render(request,"maintenance/work_order_detail.html",{
        "order":current,"history":history,"external":external,
        "progress_form":WorkOrderProgressForm(instance=order),
        "external_form":ExternalRepairForm(instance=external),
    })


@login_required
def work_order_update(request, pk):
    order=get_object_or_404(WorkOrder,pk=pk)
    form=WorkOrderProgressForm(request.POST,instance=order)
    if form.is_valid():
        order=form.save(commit=False)
        if order.status == WorkOrder.Status.DONE:
            order.completed_at=order.completed_at or timezone.now()
        else:
            order.completed_at=None
        order.save()
        messages.success(request,"وضعیت و اقدام واحد تعمیرات به‌روزرسانی شد.")
    else:
        messages.error(request,"اطلاعات تعمیر به‌روزرسانی نشد؛ موارد فرم را بررسی کنید.")
    return redirect("work_order_detail",pk=order.pk)


@login_required
def external_repair_update(request, pk):
    order=get_object_or_404(WorkOrder,pk=pk)
    if order.repair_method != WorkOrder.RepairMethod.EXTERNAL:
        messages.error(request,"ابتدا روش انجام تعمیر را روی «برون‌سپاری به تعمیرگاه» قرار دهید.")
        return redirect("work_order_detail",pk=order.pk)
    try: external=order.external_repair
    except ExternalRepairRecord.DoesNotExist: external=None
    form=ExternalRepairForm(request.POST,instance=external)
    if form.is_valid():
        record=form.save(commit=False); record.work_order=order; record.recorded_by=request.user; record.save()
        if record.sent_out_date and order.status == WorkOrder.Status.NEW:
            order.status=WorkOrder.Status.IN_PROGRESS
        if record.returned_date and record.quality_status == ExternalRepairRecord.QualityStatus.ACCEPTED:
            order.status=WorkOrder.Status.DONE; order.completed_at=order.completed_at or timezone.now()
        elif record.quality_status == ExternalRepairRecord.QualityStatus.REJECTED:
            order.status=WorkOrder.Status.IN_PROGRESS; order.completed_at=None
        order.save(update_fields=["status","completed_at"])
        messages.success(request,"اطلاعات خروج، ورود و کنترل تعمیرگاه ثبت شد.")
    else:
        messages.error(request,"اطلاعات تعمیرگاه ثبت نشد؛ تاریخ‌ها و نتیجه کنترل را بررسی کنید.")
    return redirect("work_order_detail",pk=order.pk)
@login_required
def reports(request):
    import jdatetime
    from .reporting import build_maintenance_report
    data=request.GET.copy()
    if not data:
        today=jdatetime.date.fromgregorian(date=timezone.localdate())
        data={"start_date":f"{today.year:04d}/{today.month:02d}/01","end_date":today.strftime("%Y/%m/%d"),"status":"all","group_by":"overall"}
    form=MaintenanceReportFilterForm(data)
    report=build_maintenance_report(form.cleaned_data) if form.is_valid() else None
    query_string=request.GET.urlencode() if request.GET else urlencode(data)
    return render(request,"maintenance/reports.html",{"form":form,"report":report,"query_string":query_string})

@login_required
def reports_pdf(request):
    from .pdf_reports import build_report_pdf
    from .reporting import build_maintenance_report
    form=MaintenanceReportFilterForm(request.GET)
    if not form.is_valid(): return HttpResponse("فیلتر گزارش معتبر نیست.",status=400,content_type="text/plain; charset=utf-8")
    content=build_report_pdf(build_maintenance_report(form.cleaned_data))
    response=HttpResponse(content,content_type="application/pdf")
    response["Content-Disposition"]='attachment; filename="parsnet-maintenance-report.pdf"'
    return response

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
