const state = {
  mode: "day", // day | all
  dates: [],
  selectedDate: null,
  run: null,
  roles: [],
  selectedSlug: null,
  selectedSlugs: new Set(),
  application: null,
  activeTab: "docs",
};

const els = {
  modeDay: document.getElementById("mode-day"),
  modeAll: document.getElementById("mode-all"),
  dayControls: document.getElementById("day-controls"),
  dateSelect: document.getElementById("date-select"),
  runSummary: document.getElementById("run-summary"),
  runStatus: document.getElementById("run-status"),
  runAttempt: document.getElementById("run-attempt"),
  runHeadline: document.getElementById("run-headline"),
  runCounts: document.getElementById("run-counts"),
  runNotes: document.getElementById("run-notes"),
  runGit: document.getElementById("run-git"),
  roleListTitle: document.getElementById("role-list-title"),
  roleList: document.getElementById("role-list"),
  archiveSection: document.getElementById("archive-section"),
  archiveDetails: document.getElementById("archive-details"),
  archiveSummary: document.getElementById("archive-summary"),
  archiveList: document.getElementById("archive-list"),
  skippedSection: document.getElementById("skipped-section"),
  skippedContent: document.getElementById("skipped-content"),
  selectAll: document.getElementById("select-all"),
  selectedCount: document.getElementById("selected-count"),
  bulkStatus: document.getElementById("bulk-status"),
  bulkApply: document.getElementById("bulk-apply"),
  emptyState: document.getElementById("empty-state"),
  reportPanel: document.getElementById("report-panel"),
  reportTitle: document.getElementById("report-title"),
  reportSubtitle: document.getElementById("report-subtitle"),
  reportContent: document.getElementById("report-content"),
  closeReport: document.getElementById("close-report"),
  detailPanel: document.getElementById("detail-panel"),
  detailCompany: document.getElementById("detail-company"),
  detailTitle: document.getElementById("detail-title"),
  detailLocation: document.getElementById("detail-location"),
  detailDate: document.getElementById("detail-date"),
  detailUrl: document.getElementById("detail-url"),
  detailWhy: document.getElementById("detail-why"),
  listingLink: document.getElementById("listing-link"),
  prevRole: document.getElementById("prev-role"),
  nextRole: document.getElementById("next-role"),
  reviewNote: document.getElementById("review-note"),
  notesContent: document.getElementById("notes-content"),
  resumeContent: document.getElementById("resume-content"),
  coverContent: document.getElementById("cover-content"),
  resumeDocPdf: document.getElementById("resume-doc-pdf"),
  coverDocPdf: document.getElementById("cover-doc-pdf"),
  resumePdfLink: document.getElementById("resume-pdf-link"),
  coverPdfLink: document.getElementById("cover-pdf-link"),
  resumePdfFrame: document.getElementById("resume-pdf-frame"),
  coverPdfFrame: document.getElementById("cover-pdf-frame"),
  sidebarResizer: document.getElementById("sidebar-resizer"),
  app: document.querySelector(".app"),
};

const SIDEBAR_STORAGE_KEY = "review-ui-sidebar-width";
const SIDEBAR_DEFAULT = 360;
const SIDEBAR_MIN = 260;
const SIDEBAR_MAX = 560;

function clampSidebarWidth(width) {
  const maxForViewport = Math.min(SIDEBAR_MAX, Math.floor(window.innerWidth * 0.55));
  return Math.min(Math.max(width, SIDEBAR_MIN), Math.max(SIDEBAR_MIN, maxForViewport));
}

function setSidebarWidth(width, { persist = true } = {}) {
  const clamped = clampSidebarWidth(width);
  document.documentElement.style.setProperty("--sidebar-width", `${clamped}px`);
  if (els.sidebarResizer) {
    els.sidebarResizer.setAttribute("aria-valuenow", String(clamped));
  }
  if (persist) {
    localStorage.setItem(SIDEBAR_STORAGE_KEY, String(clamped));
  }
  return clamped;
}

function initSidebarResize() {
  if (!els.sidebarResizer) return;

  const saved = Number(localStorage.getItem(SIDEBAR_STORAGE_KEY));
  setSidebarWidth(Number.isFinite(saved) && saved > 0 ? saved : SIDEBAR_DEFAULT);

  let dragging = false;

  const onPointerMove = (event) => {
    if (!dragging) return;
    const bounds = els.app.getBoundingClientRect();
    setSidebarWidth(event.clientX - bounds.left, { persist: false });
  };

  const stopDragging = () => {
    if (!dragging) return;
    dragging = false;
    document.body.classList.remove("is-resizing-sidebar");
    const current = Number.parseFloat(
      getComputedStyle(document.documentElement).getPropertyValue("--sidebar-width")
    );
    setSidebarWidth(current);
    window.removeEventListener("pointermove", onPointerMove);
    window.removeEventListener("pointerup", stopDragging);
    window.removeEventListener("pointercancel", stopDragging);
  };

  els.sidebarResizer.addEventListener("pointerdown", (event) => {
    if (window.matchMedia("(max-width: 960px)").matches) return;
    dragging = true;
    document.body.classList.add("is-resizing-sidebar");
    els.sidebarResizer.setPointerCapture?.(event.pointerId);
    window.addEventListener("pointermove", onPointerMove);
    window.addEventListener("pointerup", stopDragging);
    window.addEventListener("pointercancel", stopDragging);
    event.preventDefault();
  });

  els.sidebarResizer.addEventListener("keydown", (event) => {
    const current = Number.parseFloat(
      getComputedStyle(document.documentElement).getPropertyValue("--sidebar-width")
    );
    if (event.key === "ArrowLeft") {
      setSidebarWidth(current - 16);
      event.preventDefault();
    } else if (event.key === "ArrowRight") {
      setSidebarWidth(current + 16);
      event.preventDefault();
    } else if (event.key === "Home") {
      setSidebarWidth(SIDEBAR_MIN);
      event.preventDefault();
    } else if (event.key === "End") {
      setSidebarWidth(SIDEBAR_MAX);
      event.preventDefault();
    }
  });

  window.addEventListener("resize", () => {
    const current = Number.parseFloat(
      getComputedStyle(document.documentElement).getPropertyValue("--sidebar-width")
    );
    setSidebarWidth(current);
  });
}

function fileUrl(path) {
  if (!path) return "#";
  let rel = path.replace(/\\/g, "/");
  const marker = "/applications/";
  const idx = rel.indexOf(marker);
  if (idx !== -1) {
    rel = rel.slice(idx + 1);
  } else if (rel.startsWith("/")) {
    return "#";
  }
  return `/files/${rel.split("/").map(encodeURIComponent).join("/")}`;
}

function statusLabel(status) {
  return (
    {
      to_apply: "To apply",
      applied: "Applied",
      needs_edit: "Needs edit",
      skipped: "Skipped",
      bad_url: "Failed verify",
    }[status] || ""
  );
}

function linkify(text) {
  return escapeHtml(String(text ?? "")).replace(/(https?:\/\/[^\s<]+)/g, (url) => {
    const cleaned = url.replace(/[.,);:\]]+$/g, "");
    const trailing = url.slice(cleaned.length);
    return `<a href="${cleaned}" target="_blank" rel="noopener">${cleaned}</a>${trailing}`;
  });
}

function linkifyHtml(html) {
  return String(html ?? "").replace(
    /(<a\b[^>]*>[\s\S]*?<\/a>)|(https?:\/\/[^\s<]+)/gi,
    (match, anchor, url) => {
      if (anchor) return anchor;
      const cleaned = url.replace(/[.,);:\]]+$/g, "");
      const trailing = url.slice(cleaned.length);
      return `<a href="${cleaned}" target="_blank" rel="noopener">${cleaned}</a>${trailing}`;
    }
  );
}

function extractHttpUrl(text) {
  const match = String(text ?? "").match(/https?:\/\/[^\s<]+/);
  if (!match) return "";
  return match[0].replace(/[.,);:\]]+$/g, "");
}

function listingUrlFromNotes(notes) {
  const listing = notes?.listing;
  if (!listing) return "";
  if (Array.isArray(listing)) {
    for (const item of listing) {
      const url = extractHttpUrl(item);
      if (url) return url;
    }
    return "";
  }
  return extractHttpUrl(listing);
}

function renderDayNotes(notes) {
  if (!els.runNotes) return;
  if (!notes?.length) {
    els.runNotes.hidden = true;
    els.runNotes.innerHTML = "";
    return;
  }
  els.runNotes.hidden = false;
  els.runNotes.innerHTML = `<strong>Day notes</strong><ul>${notes
    .map((item) => `<li>${linkify(item)}</li>`)
    .join("")}</ul>`;
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!response.ok) {
    throw new Error(`Request failed: ${response.status}`);
  }
  return response.json();
}

function renderMarkdown(target, markdown, emptyMessage) {
  if (!markdown) {
    target.innerHTML = `<p class="muted">${emptyMessage || "No content available."}</p>`;
    return;
  }
  target.innerHTML = linkifyHtml(marked.parse(markdown));
}

function renderNotesSections(notes) {
  if (!notes || Object.keys(notes).length === 0) {
    els.notesContent.innerHTML = "<p class='muted'>No notes.md for this application.</p>";
    return;
  }

  const sections = [
    ["listing", "Listing"],
    ["why it matched", "Why it matched"],
    ["tailoring highlights", "Tailoring highlights"],
    ["honest gaps", "Honest gaps"],
    ["generated files", "Generated files"],
  ];

  els.notesContent.innerHTML = sections
    .map(([key, title]) => {
      const value = notes[key];
      if (!value || (Array.isArray(value) && value.length === 0)) return "";
      if (Array.isArray(value)) {
        return `<section class="notes-section"><h4>${title}</h4><ul>${value
          .map((item) => `<li>${linkify(item)}</li>`)
          .join("")}</ul></section>`;
      }
      return `<section class="notes-section"><h4>${title}</h4><p>${linkify(value)}</p></section>`;
    })
    .join("");
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function classifyCountLabel(label) {
  const lower = String(label || "").toLowerCase();
  if (lower.includes("prepared") && !lower.includes("skipped")) return "prepared";
  if (lower.includes("duplicate")) return "duplicates";
  if (lower.includes("irrelevant") || lower.includes("ineligible")) return "irrelevant";
  if (lower.includes("bad") || lower.includes("unusable") || lower.includes("url")) return "bad_url";
  if (lower.includes("error") || lower.includes("note")) return "errors";
  if (lower.includes("found") || lower.includes("reviewed")) return "found";
  return "other";
}

function reportAvailability(kind) {
  const run = state.run || {};
  switch (kind) {
    case "prepared":
      return state.roles.some((role) => role.kind !== "bad_url");
    case "bad_url":
      return (
        state.roles.some((role) => role.kind === "bad_url") ||
        (run.skippedBadUrl || []).length > 0
      );
    case "duplicates":
      return (run.skippedDuplicates || []).length > 0;
    case "irrelevant":
      return (run.skippedIrrelevant || []).length > 0;
    case "errors":
      return (run.errorsNotes || []).length > 0 || Boolean(run.headline);
    case "found":
      return Boolean(run);
    default:
      return false;
  }
}

function renderListBlock(items, emptyMessage) {
  if (!items?.length) {
    return `<p class="muted">${escapeHtml(emptyMessage)}</p>`;
  }
  return `<ul>${items.map((item) => `<li>${linkify(item)}</li>`).join("")}</ul>`;
}

function renderRoleButtons(roles) {
  if (!roles.length) return `<p class="muted">No matching roles.</p>`;
  return `<ul class="report-role-list">${roles
    .map(
      (role) => `<li>
        <button type="button" class="button secondary report-role-open" data-slug="${escapeHtml(
          role.slug
        )}">
          ${escapeHtml(role.company)} — ${escapeHtml(role.roleTitle || "Untitled role")}
        </button>
        ${
          role.url
            ? `<a class="report-role-link" href="${escapeHtml(
                role.url
              )}" target="_blank" rel="noopener">Open listing</a>`
            : ""
        }
        ${
          role.skipReason || role.whyMatched
            ? `<p class="muted">${linkify(role.skipReason || role.whyMatched)}</p>`
            : ""
        }
      </li>`
    )
    .join("")}</ul>`;
}

function showMainPanel(panel) {
  els.emptyState.hidden = panel !== "empty";
  els.reportPanel.hidden = panel !== "report";
  els.detailPanel.hidden = panel !== "detail";
}

function closeReport() {
  document.querySelectorAll(".count-chip.is-active").forEach((chip) => {
    chip.classList.remove("is-active");
  });
  if (state.selectedSlug) {
    showMainPanel("detail");
  } else {
    showMainPanel("empty");
  }
}

function openCountReport(kind, label) {
  if (!reportAvailability(kind)) return;

  const run = state.run || {};
  const dateLabel = state.selectedDate || "this day";
  let title = label;
  let subtitle = `From the ${dateLabel} daily run`;
  let content = "";

  if (kind === "prepared") {
    const roles = state.roles.filter((role) => role.kind !== "bad_url");
    title = "Prepared applications";
    subtitle = `${roles.length} prepared role(s) for ${dateLabel}`;
    content = renderRoleButtons(roles);
    els.roleListTitle.scrollIntoView({ behavior: "smooth", block: "start" });
  } else if (kind === "bad_url") {
    const roles = state.roles.filter((role) => role.kind === "bad_url");
    title = "Failed URL verification";
    subtitle = "Listings the verifier rejected — open them manually if needed";
    content = `
      ${renderRoleButtons(roles)}
      <section class="notes-section">
        <h4>Raw report lines</h4>
        ${renderListBlock(run.skippedBadUrl, "No bad-URL lines in this report.")}
      </section>`;
    els.skippedSection.hidden = false;
    document.getElementById("skipped-details")?.setAttribute("open", "");
  } else if (kind === "duplicates") {
    title = "Skipped duplicates";
    content = renderListBlock(run.skippedDuplicates, "No duplicate skips recorded.");
    els.skippedSection.hidden = false;
    document.getElementById("skipped-details")?.setAttribute("open", "");
  } else if (kind === "irrelevant") {
    title = "Skipped irrelevant / ineligible";
    content = renderListBlock(run.skippedIrrelevant, "No irrelevant skips recorded.");
    els.skippedSection.hidden = false;
    document.getElementById("skipped-details")?.setAttribute("open", "");
  } else if (kind === "errors") {
    title = "Errors & day notes";
    subtitle = run.status ? `Run status: ${run.status}` : subtitle;
    content = `
      <section class="notes-section">
        <h4>Headline / failure reason</h4>
        <p>${linkify(run.headline || "No headline recorded.")}</p>
      </section>
      <section class="notes-section">
        <h4>Errors / notes</h4>
        ${renderListBlock(run.errorsNotes, "No error notes recorded for this day.")}
      </section>
      <section class="notes-section">
        <h4>Delivery</h4>
        <ul>
          <li>Pushed to main: ${escapeHtml(run.pushedToMain || "unknown")}</li>
          <li>Commit: ${escapeHtml(run.gitCommit || "n/a")}</li>
          <li>Attempt: ${escapeHtml(run.attempt || "n/a")}</li>
        </ul>
      </section>`;
    if (els.runNotes && !els.runNotes.hidden) {
      els.runNotes.scrollIntoView({ behavior: "smooth", block: "nearest" });
    }
  } else if (kind === "found") {
    title = "Search overview";
    const countRows = Object.entries(run.counts || {})
      .map(([key, value]) => `<li><strong>${escapeHtml(String(value))}</strong> ${escapeHtml(key)}</li>`)
      .join("");
    content = `
      <section class="notes-section">
        <h4>Headline</h4>
        <p>${linkify(run.headline || "No headline recorded.")}</p>
      </section>
      <section class="notes-section">
        <h4>Counts</h4>
        <ul>${countRows || "<li class='muted'>No counts recorded.</li>"}</ul>
      </section>`;
  } else {
    return;
  }

  els.reportTitle.textContent = title;
  els.reportSubtitle.textContent = subtitle;
  els.reportContent.innerHTML = content;
  showMainPanel("report");

  document.querySelectorAll(".count-chip").forEach((chip) => {
    chip.classList.toggle("is-active", chip.dataset.kind === kind);
  });

  els.reportContent.querySelectorAll(".report-role-open").forEach((button) => {
    button.addEventListener("click", () => selectRole(button.dataset.slug));
  });
}

function renderCounts(counts) {
  const entries = Object.entries(counts || {});
  if (!entries.length) {
    els.runCounts.innerHTML = "";
    return;
  }
  els.runCounts.innerHTML = entries
    .map(([label, value]) => {
      const kind = classifyCountLabel(label);
      const available = reportAvailability(kind) && kind !== "other";
      return `<button type="button" class="count-chip ${available ? "is-clickable" : ""}" data-kind="${kind}" data-label="${escapeHtml(
        label
      )}" ${available ? "" : "disabled"}>
        <strong>${value}</strong>${escapeHtml(label)}
      </button>`;
    })
    .join("");

  els.runCounts.querySelectorAll(".count-chip.is-clickable").forEach((chip) => {
    chip.addEventListener("click", () => openCountReport(chip.dataset.kind, chip.dataset.label));
  });
}

function renderSkipped(run) {
  if (!run) {
    els.skippedSection.hidden = true;
    return;
  }

  const blocks = [];
  if (run.skippedDuplicates?.length) {
    blocks.push(
      `<h4>Duplicates</h4><ul>${run.skippedDuplicates.map((item) => `<li>${linkify(item)}</li>`).join("")}</ul>`
    );
  }
  if (run.skippedBadUrl?.length) {
    blocks.push(
      `<h4>Failed URL verify (still try opening)</h4><ul>${run.skippedBadUrl
        .map((item) => `<li>${linkify(item)}</li>`)
        .join("")}</ul>`
    );
  }
  if (run.skippedIrrelevant?.length) {
    blocks.push(
      `<h4>Irrelevant / excluded</h4><ul>${run.skippedIrrelevant.map((item) => `<li>${linkify(item)}</li>`).join("")}</ul>`
    );
  }

  if (!blocks.length) {
    els.skippedSection.hidden = true;
    return;
  }

  els.skippedSection.hidden = false;
  els.skippedContent.innerHTML = blocks.join("");
}

function isArchivedRole(role) {
  const status = role.review?.status;
  return status === "applied" || status === "skipped";
}

function activeRoles() {
  return state.roles.filter((role) => !isArchivedRole(role));
}

function archivedRoles() {
  // Archive is scoped to the current view (selected day, or all apps).
  return state.roles.filter((role) => isArchivedRole(role));
}

function findRole(slug) {
  return state.roles.find((role) => role.slug === slug) || null;
}

function syncRoleReview(slug, review) {
  const role = state.roles.find((item) => item.slug === slug);
  if (role) role.review = review;
}

function updateSelectedCount() {
  const selectable = activeRoles();
  els.selectedCount.textContent = `${state.selectedSlugs.size} selected`;
  const allSelected =
    selectable.length > 0 && selectable.every((role) => state.selectedSlugs.has(role.slug));
  els.selectAll.checked = allSelected;
  els.selectAll.indeterminate =
    state.selectedSlugs.size > 0 && state.selectedSlugs.size < selectable.length;
}

function roleItemHtml(role) {
  const isFailed = role.kind === "bad_url";
  const status = isFailed ? "bad_url" : role.review?.status;
  const statusHtml = status
    ? `<span class="role-status ${status}">${statusLabel(status)}</span>`
    : "";
  const metaBits = [
    role.location,
    role.dateFound ? `Found ${role.dateFound}` : "",
    isFailed ? "Verifier failed — open listing manually" : "",
  ]
    .filter(Boolean)
    .join(" · ");

  return `<li class="role-item-wrap">
    <input class="role-check" type="checkbox" data-slug="${escapeHtml(role.slug)}" ${
      state.selectedSlugs.has(role.slug) ? "checked" : ""
    } />
    <button class="role-item ${isFailed ? "bad-url" : ""} ${
      role.slug === state.selectedSlug ? "active" : ""
    }" data-slug="${escapeHtml(role.slug)}" type="button">
      <div class="role-company">${escapeHtml(role.company)}</div>
      <div class="role-title">${escapeHtml(role.roleTitle || "Untitled role")}</div>
      <div class="role-meta">${escapeHtml(metaBits || "No location / date")}</div>
      ${statusHtml}
    </button>
  </li>`;
}

function bindRoleList(container) {
  container.querySelectorAll(".role-item").forEach((button) => {
    button.addEventListener("click", () => selectRole(button.dataset.slug));
  });
  container.querySelectorAll(".role-check").forEach((checkbox) => {
    checkbox.addEventListener("change", () => {
      if (checkbox.checked) state.selectedSlugs.add(checkbox.dataset.slug);
      else state.selectedSlugs.delete(checkbox.dataset.slug);
      updateSelectedCount();
    });
  });
}

function renderRoleList() {
  const active = activeRoles();
  const archived = archivedRoles();

  els.roleList.innerHTML = active.length
    ? active.map(roleItemHtml).join("")
    : `<li class="muted empty-role-note">No active roles in this view.</li>`;
  bindRoleList(els.roleList);

  if (archived.length) {
    els.archiveSection.hidden = false;
    const appliedCount = archived.filter((role) => role.review?.status === "applied").length;
    const skippedCount = archived.filter((role) => role.review?.status === "skipped").length;
    els.archiveSummary.textContent = `Archive (${archived.length}) · ${appliedCount} applied · ${skippedCount} skipped`;
    els.archiveList.innerHTML = archived.map(roleItemHtml).join("");
    bindRoleList(els.archiveList);
    if (archived.some((role) => role.slug === state.selectedSlug)) {
      els.archiveDetails.open = true;
    }
  } else {
    els.archiveSection.hidden = true;
    els.archiveList.innerHTML = "";
    els.archiveSummary.textContent = "Archive";
  }

  updateSelectedCount();
}

function setReviewButtons(status) {
  document.querySelectorAll(".review-btn").forEach((button) => {
    button.classList.toggle("active", button.dataset.status === status);
  });
}

async function saveReviewStatus(status) {
  if (!state.selectedSlug) return;
  const payload = {
    slug: state.selectedSlug,
    status,
    note: els.reviewNote.value.trim(),
  };
  const result = await api("/api/review-state", {
    method: "POST",
    body: JSON.stringify(payload),
  });

  syncRoleReview(state.selectedSlug, result.review);
  setReviewButtons(status);
  renderRoleList();
  if (status === "applied" || status === "skipped") {
    els.archiveDetails.open = true;
  }
}

let noteTimer;
function queueReviewNoteSave() {
  clearTimeout(noteTimer);
  noteTimer = setTimeout(() => {
    const active = document.querySelector(".review-btn.active");
    const status = active ? active.dataset.status : undefined;
    if (!state.selectedSlug) return;
    api("/api/review-state", {
      method: "POST",
      body: JSON.stringify({
        slug: state.selectedSlug,
        status,
        note: els.reviewNote.value.trim(),
      }),
    }).then((result) => {
      syncRoleReview(state.selectedSlug, result.review);
      renderRoleList();
    });
  }, 400);
}

function setActiveTab(tabName) {
  state.activeTab = tabName;
  document.querySelectorAll(".tab").forEach((tab) => {
    tab.classList.toggle("active", tab.dataset.tab === tabName);
  });
  document.querySelectorAll(".tab-panel").forEach((panel) => {
    panel.classList.toggle("active", panel.id === `tab-${tabName}`);
  });
}

function renderDetailFromRole(role) {
  const listingUrl = role.url || "";

  els.detailCompany.textContent = role.company;
  els.detailTitle.textContent = role.roleTitle || "Untitled role";
  els.detailLocation.textContent = role.location || "";
  els.detailDate.textContent = role.dateFound ? `Found ${role.dateFound}` : "";
  els.detailWhy.innerHTML = linkify(
    role.whyMatched || "No match summary available for this application."
  );

  if (listingUrl) {
    els.listingLink.href = listingUrl;
    els.listingLink.style.visibility = "visible";
    els.detailUrl.hidden = false;
    els.detailUrl.innerHTML = `<a href="${escapeHtml(
      listingUrl
    )}" target="_blank" rel="noopener">${escapeHtml(listingUrl)}</a>`;
  } else {
    els.listingLink.href = "#";
    els.listingLink.style.visibility = "hidden";
    els.detailUrl.hidden = true;
    els.detailUrl.innerHTML = "";
  }

  const resumePdf = role.resumePdf || state.application?.files?.resumePdf || "";
  const coverPdf = role.coverLetterPdf || state.application?.files?.coverPdf || "";
  const resumeUrl = fileUrl(resumePdf);
  const coverUrl = fileUrl(coverPdf);

  els.resumeDocPdf.href = resumeUrl;
  els.coverDocPdf.href = coverUrl;
  els.resumePdfLink.href = resumeUrl;
  els.coverPdfLink.href = coverUrl;
  els.resumePdfFrame.src = resumePdf ? resumeUrl : "";
  els.coverPdfFrame.src = coverPdf ? coverUrl : "";

  els.resumeDocPdf.style.visibility = resumePdf ? "visible" : "hidden";
  els.coverDocPdf.style.visibility = coverPdf ? "visible" : "hidden";

  els.reviewNote.value = role.review?.note || "";
  setReviewButtons(role.review?.status || "");
}

function renderApplication(application) {
  renderNotesSections(application.notes);
  renderMarkdown(els.resumeContent, application.resumeMarkdown, "No resume markdown found.");
  renderMarkdown(els.coverContent, application.coverMarkdown, "No cover letter markdown found.");

  const role = findRole(state.selectedSlug);
  if (role) {
    if (!role.resumePdf && application.files.resumePdf) role.resumePdf = application.files.resumePdf;
    if (!role.coverLetterPdf && application.files.coverPdf) {
      role.coverLetterPdf = application.files.coverPdf;
    }
    if (!role.url) {
      const fromNotes = listingUrlFromNotes(application.notes);
      if (fromNotes) role.url = fromNotes;
    }
    renderDetailFromRole(role);
  }
}

function renderFailedUrlDetail(role) {
  setActiveTab("notes");
  els.notesContent.innerHTML = `
    <section class="notes-section">
      <h4>Failed URL verification</h4>
      <p>The automation could not verify this listing, but you can still open it manually.</p>
    </section>
    <section class="notes-section">
      <h4>Reason</h4>
      <p>${linkify(role.skipReason || role.whyMatched || "Verifier failed")}</p>
    </section>
    <section class="notes-section">
      <h4>Listing URL</h4>
      <p>${
        role.url
          ? `<a href="${escapeHtml(role.url)}" target="_blank" rel="noopener">${escapeHtml(role.url)}</a>`
          : "No URL captured in the daily report."
      }</p>
    </section>`;
  els.resumeContent.innerHTML =
    "<p class='muted'>No tailored resume — this listing was skipped before materials were generated.</p>";
  els.coverContent.innerHTML =
    "<p class='muted'>No cover letter — this listing was skipped before materials were generated.</p>";
  els.resumePdfFrame.src = "";
  els.coverPdfFrame.src = "";
  els.resumeDocPdf.style.visibility = "hidden";
  els.coverDocPdf.style.visibility = "hidden";
}

async function selectRole(slug) {
  state.selectedSlug = slug;
  state.application = null;
  document.querySelectorAll(".count-chip.is-active").forEach((chip) => {
    chip.classList.remove("is-active");
  });
  renderRoleList();

  const role = findRole(slug);
  if (!role) return;

  showMainPanel("detail");
  renderDetailFromRole(role);

  if (role.kind === "bad_url") {
    renderFailedUrlDetail(role);
    return;
  }

  setActiveTab("docs");

  try {
    state.application = await api(`/api/applications/${encodeURIComponent(slug)}`);
    renderApplication(state.application);
  } catch (error) {
    els.notesContent.innerHTML = `<p class="muted">Could not load application files: ${escapeHtml(
      error.message
    )}</p>`;
    els.resumeContent.innerHTML = `<p class="muted">Could not load resume.</p>`;
    els.coverContent.innerHTML = `<p class="muted">Could not load cover letter.</p>`;
  }
}

function moveRole(offset) {
  if (!state.selectedSlug) return;
  const archived = archivedRoles();
  const pool = archived.some((role) => role.slug === state.selectedSlug)
    ? archived
    : activeRoles();
  if (!pool.length) return;
  const index = pool.findIndex((role) => role.slug === state.selectedSlug);
  const next = pool[index + offset];
  if (next) selectRole(next.slug);
}

function resetSelection() {
  state.selectedSlug = null;
  state.selectedSlugs = new Set();
  state.application = null;
  document.querySelectorAll(".count-chip.is-active").forEach((chip) => {
    chip.classList.remove("is-active");
  });
  showMainPanel("empty");
}

async function loadDailyRun(runDate) {
  state.selectedDate = runDate;
  state.run = await api(`/api/daily-runs/${runDate}`);
  state.roles = state.run.roles || [];
  resetSelection();

  els.runSummary.hidden = false;
  els.runStatus.textContent = state.run.status || "unknown";
  els.runStatus.className = `badge ${(state.run.status || "").replace(/\s+/g, "-")}`;
  els.runAttempt.textContent = state.run.attempt || "";
  els.runHeadline.textContent = state.run.headline || "No headline in this daily report.";
  renderCounts(state.run.counts);
  renderDayNotes(state.run.errorsNotes);
  els.runGit.textContent = [
    state.run.gitCommit ? `Commit: ${state.run.gitCommit}` : "",
    state.run.pushedToMain ? `Pushed to main: ${state.run.pushedToMain}` : "",
    state.run.sourceKind ? `Source: ${state.run.sourceKind}` : "",
  ]
    .filter(Boolean)
    .join(" · ");

  const failedCount = activeRoles().filter((role) => role.kind === "bad_url").length;
  const activeCount = activeRoles().length;
  els.roleListTitle.textContent =
    failedCount > 0
      ? `Active roles (${activeCount}) · ${failedCount} failed verify`
      : `Active roles (${activeCount})`;
  renderSkipped(state.run);
  renderRoleList();

  if (activeRoles().length === 1) {
    selectRole(activeRoles()[0].slug);
  }
}

async function loadAllApplications() {
  state.run = null;
  const payload = await api("/api/applications");
  state.roles = payload.roles || [];
  resetSelection();

  els.runSummary.hidden = false;
  els.runStatus.textContent = "all";
  els.runStatus.className = "badge available";
  els.runAttempt.textContent = "";
  els.runHeadline.textContent = `Browsing all ${state.roles.length} applications in the repo.`;
  els.runCounts.innerHTML = "";
  renderDayNotes([]);
  els.runGit.textContent = "Includes tracked-jobs.json and applications/ folders.";
  els.roleListTitle.textContent = `Active roles (${activeRoles().length})`;
  renderSkipped(null);
  renderRoleList();
}

function setMode(mode) {
  state.mode = mode;
  els.modeDay.classList.toggle("active", mode === "day");
  els.modeAll.classList.toggle("active", mode === "all");
  els.dayControls.hidden = mode !== "day";

  if (mode === "all") {
    return loadAllApplications();
  }
  const runDate = els.dateSelect.value || state.selectedDate || state.dates[0]?.date;
  if (runDate) return loadDailyRun(runDate);
  return Promise.resolve();
}

async function applyBulkStatus() {
  const status = els.bulkStatus.value;
  if (!status) {
    alert("Choose a bulk status first.");
    return;
  }
  if (!state.selectedSlugs.size) {
    alert("Select one or more applications first.");
    return;
  }

  const result = await api("/api/review-state/bulk", {
    method: "POST",
    body: JSON.stringify({
      slugs: Array.from(state.selectedSlugs),
      status,
    }),
  });

  const bySlug = Object.fromEntries(result.updated.map((item) => [item.slug, item.review]));
  Object.entries(bySlug).forEach(([slug, review]) => syncRoleReview(slug, review));
  if (state.selectedSlug && bySlug[state.selectedSlug]) {
    setReviewButtons(bySlug[state.selectedSlug].status || "");
  }
  renderRoleList();
  if (status === "applied" || status === "skipped") {
    els.archiveDetails.open = true;
  }
}

async function init() {
  initSidebarResize();

  const index = await api("/api/daily-runs");
  state.dates = index.dates || [];
  els.dateSelect.innerHTML = state.dates
    .map((entry) => `<option value="${entry.date}">${escapeHtml(entry.label || entry.date)}</option>`)
    .join("");

  if (!state.dates.length) {
    await setMode("all");
    return;
  }

  const preferred =
    state.dates.find((entry) => entry.date === "2026-07-21") ||
    state.dates.find((entry) => entry.date === index.defaultDate) ||
    state.dates[0];
  els.dateSelect.value = preferred.date;
  await setMode("day");
}

els.modeDay.addEventListener("click", () => setMode("day"));
els.modeAll.addEventListener("click", () => setMode("all"));

els.dateSelect.addEventListener("change", async (event) => {
  await loadDailyRun(event.target.value);
});

els.selectAll.addEventListener("change", () => {
  const selectable = activeRoles();
  if (els.selectAll.checked) {
    selectable.forEach((role) => state.selectedSlugs.add(role.slug));
  } else {
    selectable.forEach((role) => state.selectedSlugs.delete(role.slug));
  }
  renderRoleList();
});

els.bulkApply.addEventListener("click", () => {
  applyBulkStatus().catch((error) => alert(error.message));
});

els.closeReport?.addEventListener("click", closeReport);

document.querySelectorAll(".tab").forEach((tab) => {
  tab.addEventListener("click", () => setActiveTab(tab.dataset.tab));
});

document.querySelectorAll(".review-btn").forEach((button) => {
  button.addEventListener("click", () => saveReviewStatus(button.dataset.status));
});

els.reviewNote.addEventListener("input", queueReviewNoteSave);
els.prevRole.addEventListener("click", () => moveRole(-1));
els.nextRole.addEventListener("click", () => moveRole(1));

document.addEventListener("keydown", (event) => {
  if (event.target.matches("input, textarea, select")) return;
  if (event.key === "ArrowLeft") moveRole(-1);
  if (event.key === "ArrowRight") moveRole(1);
});

init().catch((error) => {
  document.body.innerHTML = `<main style="padding:40px;font-family:system-ui"><h1>Review UI failed to start</h1><p>${escapeHtml(
    error.message
  )}</p></main>`;
});
