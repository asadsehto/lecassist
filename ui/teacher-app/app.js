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
  if (tab.id === "mode-lectures") loadLectures();
});
const selectFormTab = tabList($$(".tabs [role=tab]"), tab => {
  $("#form-result").hidden = true;
  if (tab.id === "tab-course") loadCategories();
});

// ---------- sidebar ----------
const SOON = {
  marks: ["marks", "Marks", "Give LecAssist your marks sheet and it enters the marks into the LMS for you, after you approve.",
    ["Upload from an Excel sheet", "Check every row before it is submitted"]],
  messages: ["chat", "Telegram & WhatsApp", "Get summaries on your phone and give instructions like this app does, from a chat.",
    ["Summaries sent to the class group", "Approve actions with a Yes or No button"]],
  search: ["search", "Semester search", "Ask a question and get the answer from all your lectures, with the lecture and date it came from.",
    ["Search across every lecture", "Compare two lectures"]],
  quizzes: ["quiz", "Quizzes & papers", "Generate quizzes and full exam papers from what you actually taught.",
    ["Multiple choice and short questions", "Papers balanced across weeks"]],
};
const PAGES = {
  record: ["Record lecture", "Record or upload a lecture. LecAssist writes the summary and finds what eLearning needs."],
  elearning: ["eLearning", "Approve what your lectures need, ask for a task, or fill a form."],
};
const navItems = $$(".nav-item");
function showView(id) {
  ["view-record", "view-lectures", "view-ask", "view-form", "view-soon"].forEach(v => { $("#" + v).hidden = v !== id; });
  $(".segmented").hidden = !["view-lectures", "view-ask", "view-form"].includes(id);
}
function openPage(name) {
  navItems.forEach(n => n.dataset.page === name ? n.setAttribute("aria-current", "page") : n.removeAttribute("aria-current"));
  if (PAGES[name]) {
    $(".page-head h1").textContent = PAGES[name][0];
    $(".page-head .sub").textContent = PAGES[name][1];
  }
  if (name === "record") showView("view-record");
  if (name === "elearning") {
    const tab = $(".segmented [aria-selected=true]");
    showView($("#" + tab.getAttribute("aria-controls")).id);
    if (tab.id === "mode-lectures") loadLectures();
  }
}
$$(".nav-item[data-page]").forEach(a => a.addEventListener("click", e => { e.preventDefault(); openPage(a.dataset.page); }));
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
$("#soon-back").addEventListener("click", () => openPage("elearning"));

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

// ---------- jobs: an agent running on the server ----------
// The agent's tools ask approve(); the question shows here with Approve / Decline.
const sleep = ms => new Promise(r => setTimeout(r, ms));
const plain = text => (text || "").replace(/\*\*/g, "");  // the model writes **bold**

async function followJob(jobId, box, onDone) {
  let shownQuestion = null;
  let shownApprovals = 0;
  const status = el("p", { class: "job-status" });
  box.append(status);
  for (;;) {
    let job;
    try {
      job = await api("/api/jobs/" + jobId);
    } catch (err) {
      status.textContent = "Lost contact with LecAssist: " + err.message;
      return;
    }
    while (shownApprovals < job.approvals.length) {
      const a = job.approvals[shownApprovals++];
      box.querySelector(".approval.open")?.remove();
      box.insertBefore(el("div", { class: "approval " + (a.approved ? "ok" : "muted") },
        icon(a.approved ? "check" : "x"), el("span", {}, (a.approved ? "Approved: " : "Declined: ") + a.action)), status);
    }
    if (job.question && job.question !== shownQuestion) {
      shownQuestion = job.question;
      box.insertBefore(approvalCard(jobId, job.question), status);
      scrollDown();
    }
    if (!job.question) shownQuestion = null;
    status.textContent = job.state === "working"
      ? (job.question ? "Waiting for your approval…" : (job.stage || "Thinking") + "…") : "";
    status.hidden = job.state !== "working";
    if (job.state === "done" || job.state === "error") {
      onDone(job);
      return;
    }
    await sleep(1200);
  }
}

function approvalCard(jobId, question) {
  const yes = el("button", { type: "button", class: "btn btn-primary" }, "Approve");
  const no = el("button", { type: "button", class: "btn" }, "Decline");
  const card = el("div", { class: "approval open", role: "group", "aria-label": "Needs your approval" },
    el("p", { class: "approval-title" }, icon("alert"), "Needs your approval"),
    el("p", { class: "approval-text" }, question),
    el("div", { class: "approval-actions" }, no, yes));
  const answer = async approve => {
    yes.disabled = no.disabled = true;
    try {
      await api(`/api/jobs/${jobId}/answer`, {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ approve }),
      });
    } catch (err) {
      yes.disabled = no.disabled = false;
      card.append(el("p", { class: "field-error" }, icon("alert"), err.message));
    }
  };
  yes.addEventListener("click", () => answer(true));
  no.addEventListener("click", () => answer(false));
  setTimeout(() => yes.focus(), 0);
  return card;
}

// ---------- Ask ----------
const TASKS = {
  assignment: {
    required: ["Course, e.g. AI101 (or choose it above)", "Week number", "Title", "Due date and time"],
    optional: ["Attach the question paper", "Marks, instructions and other dates: use Fill a form"],
    example: "Create Lab 5 in AI101 week 5, due next Friday at 11:59 pm.",
    placeholder: "Create Lab 5 in AI101 week 5, due next Friday at 11:59 pm",
    files: true,
  },
  material: {
    required: ["Course, e.g. AI101 (or choose it above)", "Week number", "Title students see", "Attach the files"],
    optional: ["A note for students: use Fill a form"],
    example: "Upload these slides to AI101 week 3 as Week 3 slides.",
    placeholder: "Upload these slides to AI101 week 3 as Week 3 slides",
    files: true,
  },
  course: {
    required: ["Full name", "Short name, unique on the portal"],
    optional: ["Number of weeks", "Description and dates: use Fill a form"],
    example: "Create a course Data Mining, short name DM401, for 16 weeks.",
    placeholder: "Create a course Data Mining, short name DM401",
    files: false,
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

async function uploadFiles(list) {
  if (!list.length) return [];
  const data = new FormData();
  list.forEach(f => data.append("files", f));
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
  const box = el("div", { class: "agent-turn" });
  const li = el("li", { class: "msg assistant" }, box);
  threadFor(task).append(li);
  scrollDown();
  try {
    const fileIds = await uploadFiles(files);
    files = [];
    renderChips();
    conversation.push({ role: "user", content: text });
    const job = await api("/api/agent/ask", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ messages: conversation, task, file_ids: fileIds,
        course_id: task !== "course" && $("#ask-course").value ? Number($("#ask-course").value) : null }),
    });
    await followJob(job.id, box, done => {
      const reply = done.state === "done" ? done.result : "Not done: " + done.error;
      conversation.push({ role: "assistant", content: reply || "" });
      box.append(el("div", { class: "bubble" }, plain(reply) || "Done."));
      if (task === "course" && done.approvals.some(a => a.approved)) loadCourses();
      scrollDown();
    });
  } catch (err) {
    conversation.pop();
    box.append(el("div", { class: "bubble" }, "Unable to start: " + err.message));
  } finally {
    busy = false;
    $("#send").disabled = false;
    promptBox.focus();
  }
});

// ---------- Record lecture ----------
let recorder = null;
let chunks = [];
let timer = null;
let seconds = 0;
let lectureFiles = [];

const recBtn = $("#rec-start");
const pauseBtn = $("#rec-pause");
const stopBtn = $("#rec-stop");
const clock = () => `${String(Math.floor(seconds / 60)).padStart(2, "0")}:${String(seconds % 60).padStart(2, "0")}`;

function recordState(state) {
  $("#rec-panel").dataset.state = state;
  recBtn.hidden = state !== "idle";
  pauseBtn.hidden = stopBtn.hidden = state === "idle";
  pauseBtn.replaceChildren(icon(state === "paused" ? "mic" : "pause"), state === "paused" ? "Resume" : "Pause");
  $("#rec-label").textContent = { idle: "Ready to record", recording: "Recording", paused: "Paused" }[state];
}

function checkWhere() {
  const form = $("#record-form");
  let ok = true;
  [form.elements.course_id, form.elements.section].forEach(f => {
    setError(f, f.value ? "" : "Choose this before recording.");
    if (!f.value) ok = false;
  });
  if (!ok) (form.elements.course_id.value ? form.elements.section : form.elements.course_id).focus();
  return ok;
}

recBtn.addEventListener("click", async () => {
  if (!checkWhere()) return;
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    recorder = new MediaRecorder(stream);
    chunks = [];
    recorder.ondataavailable = e => e.data.size && chunks.push(e.data);
    recorder.onstop = () => {
      stream.getTracks().forEach(t => t.stop());
      const type = recorder.mimeType || "audio/webm";
      const ext = type.includes("mp4") ? "m4a" : "webm";
      sendLecture(new File(chunks, `lecture-${Date.now()}.${ext}`, { type }));
    };
    recorder.start(1000);
    seconds = 0;
    $("#rec-time").textContent = clock();
    timer = setInterval(() => {
      if (recorder?.state === "recording") { seconds++; $("#rec-time").textContent = clock(); }
    }, 1000);
    recordState("recording");
  } catch (err) {
    $("#rec-label").textContent = "Unable to use the microphone: " + err.message;
  }
});
pauseBtn.addEventListener("click", () => {
  if (recorder.state === "recording") { recorder.pause(); recordState("paused"); }
  else { recorder.resume(); recordState("recording"); }
});
stopBtn.addEventListener("click", () => {
  clearInterval(timer);
  recorder.stop();
  recordState("idle");
});
$("#rec-file").addEventListener("change", e => {
  const file = e.target.files[0];
  e.target.value = "";
  if (file && checkWhere()) sendLecture(file);
});
$("#lecture-files").addEventListener("change", e => {
  lectureFiles.push(...e.target.files);
  e.target.value = "";
  renderLectureFiles();
});
function renderLectureFiles() {
  $("#lecture-chips").replaceChildren(...lectureFiles.map((f, i) => el("span", { class: "chip" },
    el("span", { title: f.name }, f.name),
    el("button", { type: "button", "aria-label": "Remove " + f.name, onclick: () => { lectureFiles.splice(i, 1); renderLectureFiles(); } }, icon("x")),
  )));
}

async function sendLecture(audio) {
  const form = $("#record-form");
  const data = new FormData();
  data.append("audio", audio);
  data.append("course_id", form.elements.course_id.value);
  data.append("week", form.elements.section.value);
  try {
    data.append("file_ids", (await uploadFiles(lectureFiles)).join(","));
    lectureFiles = [];
    renderLectureFiles();
    const res = await api("/api/lectures", { method: "POST", body: data });
    renderLecture(res.lecture, $("#record-results"), true);
  } catch (err) {
    $("#record-results").prepend(el("div", { class: "notice err" }, icon("alert"), "Not sent: " + err.message));
  }
}

// One lecture: summary, then the agent's approvals and what it did.
const following = new Set();
function renderLecture(lec, into, atTop) {
  const summary = el("pre", { class: "summary" }, lec.summary || "");
  const agentBox = el("div", { class: "agent-turn" });
  const transcript = el("details", { class: "transcript" }, el("summary", {}, "Transcript"), el("p", {}, lec.transcript || ""));
  transcript.hidden = !lec.transcript;
  summary.hidden = !lec.summary;
  const card = el("article", { class: "lecture" },
    el("header", {}, el("h3", {}, `${lec.course} · Week ${lec.week}`), el("span", { class: "hint" }, lec.recorded)),
    lec.files.length ? el("p", { class: "hint" }, "Files: " + lec.files.join(", ")) : null,
    summary, transcript, agentBox);
  atTop ? into.prepend(card) : into.append(card);
  if (!lec.job) return;
  if (["done", "error"].includes(lec.job.state)) {
    lec.job.approvals.forEach(a => agentBox.append(el("div", { class: "approval " + (a.approved ? "ok" : "muted") },
      icon(a.approved ? "check" : "x"), el("span", {}, (a.approved ? "Approved: " : "Declined: ") + a.action))));
    agentBox.append(el("div", { class: "bubble" }, lec.job.state === "done" ? plain(lec.job.result) : "Not done: " + lec.job.error));
    return;
  }
  if (following.has(lec.job.id + into.id)) return;
  following.add(lec.job.id + into.id);
  // fill in transcript and summary as soon as they exist
  const refresh = setInterval(async () => {
    const all = await api("/api/lectures").catch(() => []);
    const now = all.find(x => x.id === lec.id);
    if (!now) return;
    if (now.transcript) { transcript.hidden = false; transcript.querySelector("p").textContent = now.transcript; }
    if (now.summary) { summary.hidden = false; summary.textContent = now.summary; }
  }, 3000);
  followJob(lec.job.id, agentBox, done => {
    clearInterval(refresh);
    following.delete(lec.job.id + into.id);
    api("/api/lectures").then(all => {
      const now = all.find(x => x.id === lec.id);
      if (now?.summary) { summary.hidden = false; summary.textContent = now.summary; }
      if (now?.transcript) { transcript.hidden = false; transcript.querySelector("p").textContent = now.transcript; }
    }).catch(() => {});
    agentBox.append(el("div", { class: "bubble" }, done.state === "done" ? plain(done.result) : "Not done: " + done.error));
  });
}

async function loadLectures() {
  const list = $("#lecture-list");
  try {
    const lectures = await api("/api/lectures");
    list.replaceChildren();
    if (!lectures.length) {
      list.append(el("div", { class: "empty" }, el("p", { class: "empty-title" }, "No lectures yet"),
        el("p", { class: "hint" }, "Record a lecture and its summary and actions show up here for approval."),
        el("button", { type: "button", class: "btn btn-primary", onclick: () => openPage("record") }, icon("mic"), "Record a lecture")));
      return;
    }
    lectures.forEach(lec => renderLecture(lec, list, false));
  } catch (err) {
    list.replaceChildren(el("div", { class: "notice err" }, icon("alert"), "Unable to load lectures: " + err.message));
  }
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
openPage(location.hash === "#elearning" ? "elearning" : "record");
