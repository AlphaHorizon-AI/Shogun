() => {
  const visible = (element) => Boolean(element.offsetWidth || element.offsetHeight || element.getClientRects().length);
  const text = (document.body?.innerText || '').replace(/\s+/g, ' ').trim().slice(0, 20000);
  const pick = (element, index) => ({
    index,
    tag: element.tagName.toLowerCase(),
    label: (element.innerText || element.value || element.getAttribute('aria-label') || element.name || '')
      .trim().slice(0, 240),
    selector: element.id
      ? `#${CSS.escape(element.id)}`
      : element.name ? `${element.tagName.toLowerCase()}[name="${CSS.escape(element.name)}"]` : null,
    type: element.type || null,
    href: element.href || null,
    disabled: Boolean(element.disabled),
  });
  const clickable = [...document.querySelectorAll('button,a,[role="button"],input[type="submit"]')]
    .filter(visible).slice(0, 200).map(pick);
  const fields = [...document.querySelectorAll('input,textarea,select')]
    .filter(visible).slice(0, 200).map(pick);
  const forms = [...document.forms].slice(0, 50).map((form, index) => ({
    form_id: form.id || `form_${index}`,
    action: form.action,
    method: form.method,
    fields: [...form.elements].map((element, fieldIndex) => pick(element, fieldIndex)),
  }));
  const dialogs = [...document.querySelectorAll('dialog,[role="dialog"],[aria-modal="true"]')]
    .filter(visible).map(pick);
  const tables = [...document.querySelectorAll('table')].filter(visible).slice(0, 50).map((table, index) => ({
    index,
    headers: [...table.querySelectorAll('th')].map((element) => element.innerText.trim()),
    row_count: table.querySelectorAll('tbody tr').length,
  }));
  const errors = [...document.querySelectorAll('[role="alert"],.error,.alert-danger,[class*="error"]')]
    .filter(visible).slice(0, 30).map((element) => element.innerText.trim()).filter(Boolean);
  const passwordFields = fields.filter((item) => item.type === 'password').length;
  return {
    visible_text: text,
    clickable_elements: clickable,
    form_fields: fields.map((item) => item.type === 'password' ? { ...item, label: '[PASSWORD FIELD]' } : item),
    forms,
    dialogs,
    tables,
    errors,
    state_flags: {
      login_page: passwordFields > 0,
      modal_open: dialogs.length > 0,
      error_banner: errors.length > 0,
    },
  };
}
