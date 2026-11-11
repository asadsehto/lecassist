// LecAssist teacher app: eLearning section. Talks only to the LecAssist API.
// Endpoints are listed in ui/teacher-app/README.md and at /docs.
const API = "";  // same server; set e.g. "http://127.0.0.1:8100" if served elsewhere

const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];
$$("svg.icon").forEach(svg => svg.setAttribute("aria-hidden", "true"));

async function api(path, options = {}) {
  const res = await fetch(API + path, options);
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    let msg = data.detail;
    if (Array.isArray(msg)) msg = msg.map(d => `${d.loc.at(-1)}: ${d.msg}`).join("; ");
    throw new Error(msg || `The server answered ${res.status}. Try again.`);
  }
  return data;
}

function el(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === "class") node.className = v;
    else if (k.startsWith("on")) node.addEventListener(k.slice(2), v);
    else node.setAttribute(k, v);
  }
  node.append(...children.filter(c => c !== null && c !== undefined));
  return node;
}

function icon(name) {
  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.setAttribute("class", "icon");
  svg.setAttribute("aria-hidden", "true");
  const use = document.createElementNS("http://www.w3.org/2000/svg", "use");
  use.setAttribute("href", "#i-" + name);
  svg.append(use);
  return svg;
}

function option(value, text) {
  return el("option", { value }, text);
}

// ---------- tab lists (Ask / Fill a form, and the form tabs) ----------
function tabList(tabs, onSelect) {
  const select = tab => {
    tabs.forEach(t => {
      const on = t === tab;
      t.setAttribute("aria-selected", on);
      t.tabIndex = on ? 0 : -1;
      $("#" + t.getAttribute("aria-controls")).hidden = !on;
    });
    onSelect?.(tab);
  };
  tabs.forEach((t, i) => {
    t.addEventListener("click", () => select(t));
    t.addEventListener("keydown", e => {
      const step = e.key === "ArrowRight" ? 1 : e.key === "ArrowLeft" ? -1 : 0;
      if (!step) return;
      const next = tabs[(i + step + tabs.length) % tabs.length];
      select(next);
      next.focus();
    });
  });
  return select;
}

const selectMode = tabList($$(".segmented [role=tab]"), tab => {
  if (tab.id === "mode-ask") $("#prompt").focus();
});
const selectFormTab = tabList($$(".tabs [role=tab]"), tab => {
  $("#form-result").hidden = true;
  if (tab.id === "tab-course") loadCategories();
});

// ---------- sidebar: coming soon ----------
const SOON = {
  lectures: ["mic", "Lectures", "Press record in class and LecAssist cleans the audio and writes a transcript in Urdu and English, with the teacher's voice separated from the students'.",
    ["Record, pause and resume in one file", "Import recordings from your phone", "Transcript lines linked to the audio"]],
  summaries: ["notes", "Summaries", "Every lecture becomes a summary, a list of key terms and the assignments and deadlines you announced.",
    ["Short, detailed or exam-focused notes", "Deadlines sent straight to eLearning after you approve", "Edit before anything is shared"]],
  marks: ["marks", "Marks", "Give LecAssist your marks sheet and it enters the marks into the LMS for you, after you approve.",
    ["Upload from an Excel sheet", "Check every row before it is submitted"]],
  messages: ["chat", "Telegram & WhatsApp", "Get summaries on your phone and give instructions like this page does, from a chat.",
    ["Summaries sent to the class group", "Approve actions with a Yes or No button"]],
  search: ["search", "Semester search", "Ask a question and get the answer from all your lectures, with the lecture and date it came from.",
    ["Search across every lecture", "Compare two lectures"]],
  quizzes: ["quiz", "Quizzes & papers", "Generate quizzes and full exam papers from what you actually taught.",
    ["Multiple choice and short questions", "Papers balanced across weeks"]],
};
const navItems = $$(".nav-item");
function showView(id) {
  ["view-ask", "view-form", "view-soon"].forEach(v => { $("#" + v).hidden = v !== id; });
  $(".segmented").hidden = id === "view-soon";
}
$$(".nav-item.soon").forEach(btn => btn.addEventListener("click", () => {
  const [ic, title, text, points] = SOON[btn.dataset.soon];
  $("#soon-icon use").setAttribute("href", "#i-" + ic);
  $("#soon-title").textContent = title;
  $("#soon-text").textContent = text;
  $("#soon-list").replaceChildren(...points.map(p => el("li", {}, p)));
  navItems.forEach(n => n.removeAttribute("aria-current"));
  btn.setAttribute("aria-current", "page");
  $(".page-head h1").textContent = title;
  $(".page-head .sub").textContent = "Planned for the next release.";
  showView("view-soon");
  $("#soon-back").focus();
}));
function backToElearning() {
  navItems.forEach(n => n.removeAttribute("aria-current"));
  navItems[0].setAttribute("aria-current", "page");
  $(".page-head h1").textContent = "eLearning";
  $(".page-head .sub").textContent = "Create assignments, upload material and create courses on the portal.";
  const askOn = $("#mode-ask").getAttribute("aria-selected") === "true";
  showView(askOn ? "view-ask" : "view-form");
}
navItems[0].addEventListener("click", e => { e.preventDefault(); backToElearning(); });
$("#soon-back").addEventListener("click", backToElearning);

// ---------- connection status ----------
async function loadStatus() {
  const set = (id, ok, label) => {
    const dd = $("#" + id);
    dd.replaceChildren(el("span", { class: "dot " + (ok ? "ok" : "bad"), "aria-hidden": "true" }), el("span", {}, label));
  };
  try {
    const s = await api("/api/status");
    set("status-moodle", s.moodle, s.moodle ? "Connected" : "Not reachable");
    set("status-model", s.model_ok, s.model_ok ? s.model : "Ollama not running");
  } catch {
    set("status-moodle", false, "Not reachable");
  }
}

// ---------- Ask ----------
const TASKS = {
  assignment: {
    required: ["Course, e.g. AI101 (or choose it above)", "Week number", "Title", "Due date and time"],
    optional: ["Total marks, e.g. 20 marks", "Attach the question paper", "Instructions and other dates: use Edit in form"],
    example: "Create Lab 5 in AI101 week 5, due next Friday at 11:59 pm, 20 marks. Students should implement BFS and DFS.",
    placeholder: "Create Lab 5 in AI101 week 5, due next Friday at 11:59 pm",
    action: "Create assignment", files: true,
  },
  material: {
    required: ["Course, e.g. AI101 (or choose it above)", "Week number", "Title students see", "Attach the files"],
    optional: ["A note for students: use Edit in form"],
    example: "Upload these slides to AI101 week 3 as Week 3 slides.",
    placeholder: "Upload these slides to AI101 week 3 as Week 3 slides",
    action: "Upload material", files: true,
  },
  course: {
    required: ["Full name", "Short name, unique on the portal"],
    optional: ["Start date", "Number of weeks", "Description: use Edit in form"],
    example: "Create a course Data Mining, short name DM401, starting 1 December for 16 weeks.",
    placeholder: "Create a course Data Mining, short name DM401, starting 1 December",
    action: "Create course", files: false,
  },
};

const threadFor = task => $("#thread-" + task);
const promptBox = $("#prompt");
const attachInput = $("#attach");
const conversations = { assignment: [], material: [], course: [] };   // one chat per task
let files = [];          // File objects for this request
let busy = false;

const currentTask = () => $("input[name=task]:checked").value;

function showHints() {
  const t = TASKS[currentTask()];
  $("#hint-req").replaceChildren(...t.required.map(h => el("li", {}, icon("check"), h)));
  $("#hint-opt").replaceChildren(...t.optional.map(h => el("li", {}, h)));
  $("#example-text").textContent = "“" + t.example + "”";
  promptBox.placeholder = t.placeholder;
  $("#attach-label").hidden = !t.files;
}

function resetConversation(task = currentTask()) {
  conversations[task] = [];
  files = [];
  renderChips();
}

$$("input[name=task]").forEach(r => r.addEventListener("change", () => {
  showHints();
  $$(".thread").forEach(t => { t.hidden = t.dataset.task !== currentTask(); });
  $("#course-pick").hidden = currentTask() === "course";
  files = [];
  renderChips();
}));
$("#use-example").addEventListener("click", () => {
  promptBox.value = TASKS[currentTask()].example;
  autosize();
  promptBox.focus();
});

function renderChips() {
  $("#chips").replaceChildren(...files.map((f, i) => el("span", { class: "chip" },
    el("span", { title: f.name }, f.name),
    el("button", { type: "button", "aria-label": "Remove " + f.name, onclick: () => { files.splice(i, 1); renderChips(); } }, icon("x")),
  )));
}
attachInput.addEventListener("change", () => {
  files.push(...attachInput.files);
  attachInput.value = "";
  renderChips();
});

function autosize() {
  promptBox.style.height = "auto";
  promptBox.style.height = Math.min(promptBox.scrollHeight, 160) + "px";
}
promptBox.addEventListener("input", autosize);
promptBox.addEventListener("keydown", e => {
  if (e.key === "Enter" && !e.shiftKey && !e.isComposing) {
    e.preventDefault();
    $("#composer").requestSubmit();
  }
});

function scrollDown() {
  const box = $("#ask-scroll");
  box.scrollTo({ top: box.scrollHeight, behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth" });
}

function addMessage(role, text, extra, task = currentTask()) {
  const li = el("li", { class: "msg " + role }, el("div", { class: "bubble" }, text, extra));
  threadFor(task).append(li);
  scrollDown();
  return li;
}

async function uploadFiles() {
  if (!files.length) return [];
  const data = new FormData();
  files.forEach(f => data.append("files", f));
  const saved = await api("/api/uploads", { method: "POST", body: data });
  return saved.map(s => s.id);
}

$("#composer").addEventListener("submit", async e => {
  e.preventDefault();
  const text = promptBox.value.trim();
  if (!text || busy) {
    if (!text) promptBox.focus();
    return;
  }
  busy = true;
  $("#send").disabled = true;
  const task = currentTask();
  const conversation = conversations[task];
  const names = files.map(f => f.name).join(", ");
  addMessage("user", text, names ? el("span", { class: "files" }, "Attached: " + names) : null, task);
  promptBox.value = "";
  autosize();
  const working = addMessage("assistant working", "Thinking…", null, task);
  try {
    const fileIds = await uploadFiles();
    conversation.push({ role: "user", content: text });
    const res = await api("/api/agent/plan", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ messages: conversation, task, file_ids: fileIds,
        course_id: task !== "course" && $("#ask-course").value ? Number($("#ask-course").value) : null }),
    });
    working.remove();
    if (res.type === "plan") {
      conversation.push({ role: "assistant", content: "Ready to do it. Waiting for approval." });
      showPlan(res, task);
    } else {
      conversation.push({ role: "assistant", content: res.reply });
      addMessage("assistant", res.reply, null, task);
    }
  } catch (err) {
    working.remove();
    conversation.pop();
    addMessage("assistant", "Unable to read the request: " + err.message, null, task);
  } finally {
    busy = false;
    $("#send").disabled = false;
    promptBox.focus();
  }
});

const TITLES = { assignment: "New assignment", material: "New material", course: "New course" };
const DONE_LINK = { assignment: "Open assignment", material: "Open material", course: "Open course" };

function showPlan(plan, task) {
  const rows = el("dl", { class: "rows" }, ...plan.rows.flatMap(([k, v]) => [el("dt", {}, k), el("dd", {}, v)]));
  const approve = el("button", { type: "button", class: "btn btn-primary" }, TASKS[plan.task].action);
  const edit = el("button", { type: "button", class: "btn" }, "Edit in form");
  const discard = el("button", { type: "button", class: "btn" }, "Discard");
  const actions = el("div", { class: "plan-actions" }, discard, edit, approve);
  const card = el("div", { class: "plan", role: "group", "aria-label": TITLES[plan.task] },
    el("div", { class: "plan-head" }, icon(plan.task === "course" ? "course" : plan.task === "material" ? "upload" : "assignment"), TITLES[plan.task]),
    rows, actions);
  const li = el("li", { class: "msg assistant" }, card);
  threadFor(task).append(li);
  scrollDown();
  approve.focus();
  const sentFiles = files.slice();
  resetConversation(task);

  const finish = (cls, ...content) => {
    actions.replaceWith(el("div", { class: "plan-state " + cls }, ...content));
    scrollDown();
  };
  discard.addEventListener("click", () => {
    finish("muted", icon("x"), "Discarded. Nothing was changed on eLearning.");
    promptBox.focus();
  });
  edit.addEventListener("click", () => {
    finish("muted", icon("form"), "Moved to the form for editing.");
    openInForm(plan, sentFiles);
  });
  approve.addEventListener("click", async () => {
    [approve, edit, discard].forEach(b => (b.disabled = true));
    approve.textContent = "Working on eLearning…";
    try {
      const res = await api("/api/agent/run", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ plan_id: plan.plan_id }),
      });
      const link = res.url ? el("a", { href: res.url, target: "_blank", rel: "noopener" }, DONE_LINK[plan.task], icon("external")) : null;
      finish("ok", icon("check"), el("span", {}, res.message + ". "), link);
      if (plan.task === "course") loadCourses();
    } catch (err) {
      finish("err", icon("alert"), "Not done: " + err.message + " Nothing else was changed.");
    }
    promptBox.focus();
  });
}

async function openInForm(plan, sentFiles) {
  selectMode($("#mode-form"));
  selectFormTab($("#tab-" + plan.task));
  const form = $("#form-" + plan.task);
  const f = plan.form;
  for (const [name, value] of Object.entries(f)) {
    const field = form.elements[name];
    if (field && name !== "section" && name !== "course_id") field.value = value;
  }
  if (f.description && form.elements.show_description) form.elements.show_description.checked = true;
  if (f.course_id) {
    form.elements.course_id.value = f.course_id;
    await loadWeeks(form);
    form.elements.section.value = f.section;
  }
  const fileInput = form.elements.attachments || form.elements.files;
  if (fileInput && sentFiles.length) {
    const dt = new DataTransfer();
    sentFiles.forEach(file => dt.items.add(file));
    fileInput.files = dt.files;
  }
  form.querySelector("input, select, textarea").focus();
}

// ---------- dropdowns ----------
async function loadCourses() {
  const selects = $$(".course-select");
  try {
    const courses = await api("/api/courses");
    selects.forEach(sel => {
      const keep = sel.value;
      sel.replaceChildren(option("", "Choose a course"),
        ...courses.map(c => option(c.id, `${c.shortname} · ${c.fullname}`)));
      sel.value = keep;
    });
    const pick = $("#ask-course");
    const picked = pick.value;
    pick.replaceChildren(option("", "Not chosen, I'll name it"),
      ...courses.map(c => option(c.id, `${c.shortname} · ${c.fullname}`)));
    pick.value = picked;
  } catch {
    selects.forEach(sel => sel.replaceChildren(option("", "Unable to load courses")));
  }
}

async function loadWeeks(form) {
  const course = form.elements.course_id;
  const week = form.elements.section;
  week.disabled = true;
  if (!course.value) {
    week.replaceChildren(option("", "Choose a course first"));
    return;
  }
  week.replaceChildren(option("", "Loading weeks…"));
  try {
    const weeks = await api(`/api/courses/${course.value}/weeks`);
    week.replaceChildren(option("", "Choose a week"), ...weeks.map(w => option(w.section, w.name)));
    week.disabled = false;
  } catch {
    week.replaceChildren(option("", "Unable to load weeks"));
  }
}
$$(".course-select").forEach(sel => sel.addEventListener("change", () => loadWeeks(sel.form)));

let categoriesLoaded = false;
async function loadCategories() {
  if (categoriesLoaded) return;
  categoriesLoaded = true;
  const sel = $("#category-select");
  try {
    const cats = await api("/api/categories");
    sel.replaceChildren(...(cats.length > 1 ? [option("", "Choose a category")] : []), ...cats.map(c => option(c.id, c.name)));
  } catch (e) {
    categoriesLoaded = false;
    sel.replaceChildren(option("", "Unable to load categories"));
  }
}

// ---------- Fill a form ----------
function setError(field, msg) {
  const label = field.closest("label");
  $(".field-error", label)?.remove();
  field.removeAttribute("aria-invalid");
  field.removeAttribute("aria-describedby");
  if (!msg) return;
  const id = "err-" + field.form.id + "-" + field.name;
  field.setAttribute("aria-invalid", "true");
  field.setAttribute("aria-describedby", id);
  label.append(el("span", { class: "field-error", id }, icon("alert"), msg));
}

function validate(form) {
  let first = null;
  const fail = (field, msg) => { setError(field, msg); first ??= field; };
  $$("input, select, textarea", form).forEach(f => f.name && setError(f, ""));
  $$("[required]", form).forEach(f => {
    const empty = f.type === "file" ? f.files.length === 0 : !f.value.trim();
    if (empty) fail(f, f.type === "file" ? "Choose at least one file." : "Fill in this field.");
  });
  const v = name => form.elements[name]?.value;
  if (form.dataset.kind === "assignment") {
    if (v("allow_from") && v("due") && v("allow_from") >= v("due")) fail(form.elements.due, "Set the due date after the opening date.");
    if (v("cutoff") && v("due") && v("cutoff") < v("due")) fail(form.elements.cutoff, "Set the cut-off on or after the due date.");
    if (!form.elements.file_submissions.checked && !form.elements.online_text.checked)
      fail(form.elements.file_submissions, "Choose at least one way for students to submit.");
  }
  if (form.dataset.kind === "course" && v("end") && v("start") && v("end") <= v("start"))
    fail(form.elements.end, "Set the end date after the start date.");
  first?.focus();
  return !first;
}

const shown = sel => sel.options[sel.selectedIndex]?.text || "";
const when = value => value ? new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(new Date(value)) : "";
const day = value => value ? new Intl.DateTimeFormat(undefined, { dateStyle: "medium" }).format(new Date(value + "T00:00")) : "";
const fileNames = input => [...input.files].map(f => f.name).join(", ");
const yes = box => (box.checked ? "Yes" : "No");

function summary(form) {
  const e = form.elements;
  if (form.dataset.kind === "course") return [["Full name", e.fullname.value], ["Short name", e.shortname.value],
    ["Category", shown(e.category_id)], ["Starts", day(e.start.value)], ["Ends", day(e.end.value)],
    ["Weeks", e.weeks.value], ["Shown to students", yes(e.visible)]];
  const where = [["Course", shown(e.course_id)], ["Week", shown(e.section)]];
  if (form.dataset.kind === "assignment") return [...where, ["Title", e.name.value], ["Due", when(e.due.value)],
    ["Opens", when(e.allow_from.value)], ["Late work until", when(e.cutoff.value)], ["Marks", e.max_grade.value],
    ["Files", fileNames(e.attachments)], ["Shown to students", yes(e.visible)]];
  return [...where, ["Title", e.name.value], ["Files", fileNames(e.files)], ["Shown to students", yes(e.visible)]];
}

function confirmWith(kind, rows) {
  const dialog = $("#confirm");
  $("#confirm-title").textContent = { assignment: "Create this assignment?", material: "Upload this material?", course: "Create this course?" }[kind];
  $("#confirm-ok").textContent = TASKS[kind].action;
  $("#confirm-list").replaceChildren(...rows.filter(([, v]) => v).flatMap(([k, v]) => [el("dt", {}, k), el("dd", {}, v)]));
  return new Promise(resolve => {
    dialog.addEventListener("close", () => resolve(dialog.returnValue === "ok"), { once: true });
    dialog.showModal();
    $("#confirm-ok").focus();
  });
}

function buildRequest(form) {
  const e = form.elements;
  if (form.dataset.kind === "course") {
    return {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        fullname: e.fullname.value, shortname: e.shortname.value, category_id: Number(e.category_id.value),
        start: e.start.value + "T00:00", end: e.end.value ? e.end.value + "T00:00" : null,
        weeks: Number(e.weeks.value), summary: e.summary.value, visible: e.visible.checked,
      }),
    };
  }
  const data = new FormData(form);
  $$('input[type="checkbox"]', form).forEach(c => data.set(c.name, c.checked ? "true" : "false"));
  return { method: "POST", body: data };
}

function formResult(ok, text, url) {
  const box = $("#form-result");
  box.className = "notice " + (ok ? "ok" : "err");
  box.replaceChildren(icon(ok ? "check" : "alert"), el("span", {}, text),
    url ? el("a", { href: url, target: "_blank", rel: "noopener" }, "Open on eLearning") : null);
  box.hidden = false;
  box.scrollIntoView({ block: "nearest" });
}

$$("form[data-endpoint]").forEach(form => form.addEventListener("submit", async ev => {
  ev.preventDefault();
  $("#form-result").hidden = true;
  if (!validate(form) || !(await confirmWith(form.dataset.kind, summary(form)))) return;
  const button = $('button[type="submit"]', form);
  const label = button.textContent;
  button.disabled = true;
  button.textContent = "Working on eLearning…";
  try {
    const res = await api(form.dataset.endpoint, buildRequest(form));
    formResult(true, res.message + ".", res.url);
    $$('input[name="name"], input[type="file"], textarea', form).forEach(f => (f.value = ""));
    if (form.dataset.kind === "course") { form.reset(); setToday(); loadCourses(); }
  } catch (e) {
    formResult(false, "Not done: " + e.message);
  } finally {
    button.disabled = false;
    button.textContent = label;
  }
}));

function setToday() {
  const d = new Date();
  $("#form-course").elements.start.value =
    `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

showHints();
setToday();
loadCourses();
loadStatus();
