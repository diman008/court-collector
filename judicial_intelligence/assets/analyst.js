"use strict";
(() => {
  let key = "";
  let selected = "";
  const $ = id => document.getElementById(id);
  const text = (tag, value, className = "") => {
    const n = document.createElement(tag);
    n.textContent = String(value ?? "");
    if (className) n.className = className;
    return n;
  };
  const paragraph = (container, value, className = "muted") => {
    container.append(text("p", value, className));
  };
  const message = value => { $("message").textContent = value || ""; };
  const clear = id => $(id).replaceChildren();
  const req = async (path, options = {}) => {
    if (!key) throw new Error("Сначала подключите ключ локального API.");
    const headers = new Headers(options.headers || {});
    headers.set("X-API-Key", key);
    const response = await fetch(path, {
      ...options, headers, cache: "no-store", credentials: "same-origin",
      redirect: "error", referrerPolicy: "no-referrer"
    });
    let result;
    try { result = await response.json(); } catch { result = {}; }
    if (!response.ok) {
      const error = typeof result.detail === "string" ? result.detail : "HTTP " + response.status;
      throw new Error(error);
    }
    return result;
  };
  const qp = (endpoint, values) => {
    const u = new URLSearchParams(values);
    return endpoint + "?" + u.toString();
  };
  const showError = error => { message("Ошибка: " + (error?.message || "запрос не выполнен")); };
  const pill = value => text("span", value, "pill");
  const item = title => {
    const el = document.createElement("article"); el.className = "item";
    el.append(text("h3", title));
    return el;
  };
  const meta = (container, ...items) => {
    const div = document.createElement("div"); div.className = "meta";
    items.filter(v => v !== undefined && v !== null && v !== "").forEach(v => div.append(pill(v)));
    container.append(div);
  };

  async function searchCases() {
    const q = $("query").value.trim();
    const data = await req(qp("/v1/cases", { q, limit: "60" }));
    clear("cases-list");
    const cases = data.results || [];
    if (!cases.length) {
      $("cases-list").append(text("li", "В локальной базе ничего не найдено.", "muted"));
      return;
    }
    for (const row of cases) {
      const li = document.createElement("li");
      const button = text("button", row.case_number);
      button.type = "button";
      button.className = row.case_number === selected ? "active" : "";
      const sub = text("small", [row.title, row.court].filter(Boolean).join(" · "));
      button.append(sub);
      button.addEventListener("click", () => loadDossier(row.case_number).catch(showError));
      li.append(button); $("cases-list").append(li);
    }
  }
  async function loadDossier(number) {
    const data = await req(qp("/v1/dossier", { case_number: number }));
    selected = data.case.case_number;
    $("case-heading").textContent = selected;
    $("case-court").textContent = data.case.court || "Суд не указан";
    for (const [id, value] of [
      ["count-files", data.counts.evidence_files],
      ["count-acts", data.counts.acts],
      ["count-mentions", data.counts.literal_mentions],
      ["count-norms", data.counts.norm_articles]
    ]) $(id).textContent = String(value ?? 0);
    clear("warnings");
    const unresolved = data.unresolved_checks || [];
    if (!unresolved.length) {
      $("warnings").append(text("li", "Нет диагностированных пробелов (это не доказательство подлинности)."));
    } else unresolved.forEach(w => $("warnings").append(text("li", w)));
    renderEvidence(data.evidence_files || []);
    renderTimeline(data.timeline?.acts || []);
    renderCitations(data.literal_references || [], data.mentions_truncated);
    document.querySelectorAll("#cases-list button").forEach(btn => {
      btn.classList.toggle("active", btn.firstChild?.textContent === selected);
    });
    message("Открыто дело " + selected + " · Источники не проверены независимо.");
  }
  function renderEvidence(files) {
    clear("evidence-list");
    if (!files.length) return paragraph($("evidence-list"), "Файлы не загружены.");
    for (const f of files) {
      const el = item(f.filename || f.id);
      meta(el, (f.file_format || "").toUpperCase(), f.source_kind, f.verification_status);
      paragraph(el, "SHA-256: " + f.file_sha256, "muted small");
      if (f.source_url) paragraph(el, "Указанный источник: " + f.source_url, "muted small");
      if (f.warnings?.length) f.warnings.forEach(w => paragraph(el, w, "muted small"));
      const verify = text("button", "Проверить целостность", "secondary");
      verify.type = "button";
      verify.addEventListener("click", async () => {
        try {
          const p = await req(qp("/v1/verification-packet", {case_number:selected,file_id:f.id}));
          message(p.stored_bytes_match_sha256
            ? "Хеш исходного файла совпадает. Электронная подпись НЕ проверена."
            : "ВНИМАНИЕ: хеш сохранённого файла НЕ совпадает с исходным.");
        } catch (e) { showError(e); }
      });
      el.append(verify); $("evidence-list").append(el);
    }
  }
  function renderTimeline(acts) {
    clear("timeline");
    if (!acts.length) return paragraph($("timeline"), "Для дела пока не внесено ни одного судебного акта.");
    for (const act of acts) {
      const el = item([act.act_date, act.court].filter(Boolean).join(" · "));
      meta(el, act.instance, act.act_type, act.reported_result, act.verification_status);
      if (act.relation_kind !== "unconfirmed") {
        paragraph(el, "Заявленная связь: " + act.relation_kind + " · источник требует проверки.", "muted small");
      }
      if (act.linked_file_id) paragraph(el, "Связанный файл: " + act.linked_file_id, "muted small");
      $("timeline").append(el);
    }
  }
  function renderCitations(mentions, truncated) {
    clear("citations");
    if (!mentions.length) return paragraph($("citations"), "Дословных упоминаний норм НК РФ не найдено.");
    for (const mention of mentions) {
      const el = item("Статья " + mention.article + " НК РФ");
      meta(el, mention.source_kind, mention.location_kind
        ? mention.location_kind + " #" + mention.location_index
        : "текстовый документ", mention.verification_status);
      el.append(text("div", mention.context || mention.quote, "quote"));
      paragraph(el, "Дословная цитата: " + mention.quote, "muted small");
      paragraph(el, "SHA-256: " + mention.sha256 + " · смещение: " +
        mention.offset_start + "–" + mention.offset_end, "muted small");
      if (mention.source_url) paragraph(el, "Заявленный источник: " + mention.source_url, "muted small");
      $("citations").append(el);
    }
    if (truncated) paragraph($("citations"), "Показаны первые 250 упоминаний каждого типа. Полный массив не выведен.");
  }
  $("session-form").addEventListener("submit", async event => {
    event.preventDefault();
    key = $("api-key").value;
    $("api-key").value = "";
    selected = "";
    try { await searchCases(); message("Соединение с локальным API успешно."); }
    catch (err) { key = ""; showError(err); }
  });
  $("disconnect").addEventListener("click", () => {
    key = ""; selected = ""; ["cases-list","evidence-list","timeline","citations","warnings"].forEach(clear);
    $("case-heading").textContent = "Выберите дело"; $("case-court").textContent = "";
    ["count-files","count-acts","count-mentions","count-norms"].forEach(id => $(id).textContent = "—");
    message("Ключ доступа удалён из памяти вкладки.");
  });
  $("search-form").addEventListener("submit", event => {
    event.preventDefault(); searchCases().catch(showError);
  });
  $("create-form").addEventListener("submit", async event => {
    event.preventDefault();
    try {
      const payload = { case_number: $("new-number").value, title: $("new-title").value,
                        court: $("new-court").value };
      const caseRow = await req("/v1/cases", {
        method: "POST", headers: {"Content-Type": "application/json"},
        body: JSON.stringify(payload)
      });
      await searchCases(); await loadDossier(caseRow.case_number);
      message("Локальная карточка создана. Подлинность данных не проверена.");
    } catch (err) { showError(err); }
  });
  $("upload-form").addEventListener("submit", async event => {
    event.preventDefault();
    if (!selected) return message("Выберите дело перед загрузкой.");
    const source = $("upload-file").files[0];
    if (!source || source.size > 8*1024*1024) return message("Нужен PDF или DOCX размером не более 8 МиБ.");
    const data = new FormData();
    data.append("case_number", selected);
    data.append("source_kind", "user_provided");
    data.append("file", source, source.name);
    const url = $("upload-url").value.trim(); if (url) data.append("source_url", url);
    try {
      const result = await req("/v1/evidence-files", {method:"POST",body:data});
      await loadDossier(selected);
      message(result.duplicate ? "Такой файл уже сохранён." : "Файл добавлен; источник и подпись не проверены.");
    } catch (err) { showError(err); }
  });
})();
