from datetime import timedelta
from decimal import Decimal
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db.models import Count,Sum,Min
from django.shortcuts import get_object_or_404,redirect,render
from django.utils import timezone
from .forms import AppUserForm,EquipmentForm,MaintenancePlanForm,WorkOrderForm
from .models import ChecklistItem,ChecklistTemplate,Equipment,Inspection,InspectionResult,MaintenancePlan,WorkOrder
manager_required = user_passes_test(lambda u: u.is_superuser or u.groups.filter(name__in=["مدیر اصلی", "سرپرست نت"]).exists())

@login_required
def dashboard(request):
    today=timezone.localdate(); due=MaintenancePlan.objects.filter(active=True,next_due_date__lte=today).select_related("equipment","checklist")
    return render(request,"maintenance/dashboard.html",{"equipment_count":Equipment.objects.count(),"critical_count":Equipment.objects.filter(criticality="high").count(),"open_orders":WorkOrder.objects.exclude(status="done").count(),"due_plans":due[:6],"recent_orders":WorkOrder.objects.select_related("equipment")[:6]})
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
def equipment_detail(request,pk):
    equipment=get_object_or_404(Equipment.objects.select_related("category"),pk=pk)
    plans=MaintenancePlan.objects.filter(equipment=equipment).select_related("checklist")
    items=ChecklistItem.objects.filter(template__maintenanceplan__equipment=equipment).distinct()
    return render(request,"maintenance/equipment_detail.html",{"equipment":equipment,"plans":plans,"items":items})
@login_required
@manager_required
def equipment_add_check_item(request,pk):
    equipment=get_object_or_404(Equipment,pk=pk)
    title=request.POST.get("title","").strip()
    if title:
        checklist,_=ChecklistTemplate.objects.get_or_create(name=f"کنترل‌های اختصاصی {equipment.name}",category=equipment.category)
        ChecklistItem.objects.create(template=checklist,title=title,order=checklist.items.count()+1)
        MaintenancePlan.objects.get_or_create(equipment=equipment,checklist=checklist,defaults={"frequency":"monthly","next_due_date":timezone.localdate()})
        messages.success(request,"مورد کنترل به چک‌لیست این دستگاه اضافه شد.")
    return redirect("equipment_detail",pk=equipment.pk)
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
        if issue: WorkOrder.objects.create(equipment=plan.equipment,title=f"پیگیری سرویس: {plan.checklist.name}",description="مورد نیازمند اقدام در چک‌لیست سرویس ثبت شده است.")
        days={"daily":1,"weekly":7,"monthly":30,"semiannual":182,"annual":365}[plan.frequency];plan.next_due_date+=timedelta(days=days);plan.save(update_fields=["next_due_date"]);messages.success(request,"چک‌لیست ثبت و سرویس بعدی به‌روزرسانی شد.");return redirect("dashboard")
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
