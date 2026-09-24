(() => {
  const months = ["فروردین", "اردیبهشت", "خرداد", "تیر", "مرداد", "شهریور", "مهر", "آبان", "آذر", "دی", "بهمن", "اسفند"];
  const weekDays = ["ش", "ی", "د", "س", "چ", "پ", "ج"];
  const fa = value => String(value).replace(/\d/g, d => "۰۱۲۳۴۵۶۷۸۹"[d]);
  const en = value => String(value).replace(/[۰-۹]/g, d => "۰۱۲۳۴۵۶۷۸۹".indexOf(d));
  const pad = value => String(value).padStart(2, "0");
  const persianParts = date => {
    const parts = new Intl.DateTimeFormat("en-US-u-ca-persian", {year: "numeric", month: "numeric", day: "numeric"}).formatToParts(date);
    const read = type => Number(parts.find(part => part.type === type).value);
    return {year: read("year"), month: read("month"), day: read("day")};
  };
  const findGregorian = (year, month, day) => {
    const cursor = new Date(Date.UTC(year + 621, 1, 20));
    for (let i = 0; i < 380; i += 1) {
      const parts = persianParts(cursor);
      if (parts.year === year && parts.month === month && parts.day === day) return new Date(cursor);
      cursor.setUTCDate(cursor.getUTCDate() + 1);
    }
    return null;
  };
  const parseValue = value => {
    const match = en(value).match(/(\d{4})\D(\d{1,2})\D(\d{1,2})/);
    return match ? {year: Number(match[1]), month: Number(match[2]), day: Number(match[3])} : null;
  };

  let activeInput = null;
  let viewYear = 0;
  let viewMonth = 0;
  const modal = document.createElement("div");
  modal.className = "jalali-picker-backdrop";
  modal.innerHTML = `<div class="jalali-picker" role="dialog" aria-modal="true" aria-label="انتخاب تاریخ شمسی">
    <div class="jalali-picker-header"><button type="button" data-move="1" aria-label="ماه بعد">‹</button><b class="jalali-picker-title"></b><button type="button" data-move="-1" aria-label="ماه قبل">›</button></div>
    <div class="jalali-weekdays">${weekDays.map(day => `<span>${day}</span>`).join("")}</div>
    <div class="jalali-days"></div>
    <div class="jalali-picker-actions"><button type="button" class="jalali-today">امروز</button><button type="button" class="jalali-close">بستن</button></div>
  </div>`;
  document.body.appendChild(modal);

  const render = () => {
    modal.querySelector(".jalali-picker-title").textContent = `${months[viewMonth - 1]} ${fa(viewYear)}`;
    const days = modal.querySelector(".jalali-days");
    days.innerHTML = "";
    const first = findGregorian(viewYear, viewMonth, 1);
    if (!first) return;
    const nextYear = viewMonth === 12 ? viewYear + 1 : viewYear;
    const nextMonth = viewMonth === 12 ? 1 : viewMonth + 1;
    const next = findGregorian(nextYear, nextMonth, 1);
    const monthLength = Math.round((next - first) / 86400000);
    const offset = (first.getUTCDay() + 1) % 7;
    const selected = parseValue(activeInput?.value || "");
    const today = persianParts(new Date());
    for (let i = 0; i < offset; i += 1) days.appendChild(document.createElement("span"));
    for (let day = 1; day <= monthLength; day += 1) {
      const button = document.createElement("button");
      button.type = "button";
      button.textContent = fa(day);
      if (today.year === viewYear && today.month === viewMonth && today.day === day) {
        button.classList.add("today");
        button.setAttribute("aria-label", `${fa(day)}، امروز`);
        button.title = "امروز";
      }
      if (selected && selected.year === viewYear && selected.month === viewMonth && selected.day === day) button.classList.add("selected");
      button.addEventListener("click", () => {
        activeInput.value = fa(`${viewYear}/${pad(viewMonth)}/${pad(day)}`);
        activeInput.dispatchEvent(new Event("change", {bubbles: true}));
        modal.classList.remove("open");
      });
      days.appendChild(button);
    }
  };
  const open = input => {
    activeInput = input;
    const selected = parseValue(input.value);
    const today = persianParts(new Date());
    viewYear = selected?.year || today.year;
    viewMonth = selected?.month || today.month;
    render();
    modal.classList.add("open");
  };
  document.addEventListener("click", event => {
    const input = event.target.closest(".jalali-date-input");
    if (input) open(input);
  });
  document.addEventListener("keydown", event => {
    if ((event.key === "Enter" || event.key === " ") && event.target.classList?.contains("jalali-date-input")) { event.preventDefault(); open(event.target); }
    if (event.key === "Escape") modal.classList.remove("open");
  });
  modal.addEventListener("click", event => { if (event.target === modal) modal.classList.remove("open"); });
  modal.querySelector(".jalali-close").addEventListener("click", () => modal.classList.remove("open"));
  modal.querySelector(".jalali-today").addEventListener("click", () => {
    const today = persianParts(new Date());
    activeInput.value = fa(`${today.year}/${pad(today.month)}/${pad(today.day)}`);
    activeInput.dispatchEvent(new Event("change", {bubbles: true}));
    modal.classList.remove("open");
  });
  modal.querySelectorAll("[data-move]").forEach(button => button.addEventListener("click", () => {
    viewMonth += Number(button.dataset.move);
    if (viewMonth < 1) { viewMonth = 12; viewYear -= 1; }
    if (viewMonth > 12) { viewMonth = 1; viewYear += 1; }
    render();
  }));
})();
