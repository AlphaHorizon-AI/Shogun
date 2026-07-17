const STORAGE_KEY = 'shogun.samuraiDiagnostics';
const MAX_EVENTS = 250;
const DIAGNOSTIC_BUILD = '1.14.0-build76';

type DiagnosticEvent = {
  ts: string;
  event: string;
  details?: Record<string, unknown>;
};

let globalHandlersInstalled = false;

function readEvents(): DiagnosticEvent[] {
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    return raw ? JSON.parse(raw) : [];
  } catch {
    return [];
  }
}

function writeEvents(events: DiagnosticEvent[]) {
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(events.slice(-MAX_EVENTS)));
  } catch {
    // Ignore storage failures; diagnostics should never break the app.
  }
}

function cleanValue(value: unknown): unknown {
  if (value instanceof Error) {
    return { name: value.name, message: value.message, stack: value.stack };
  }
  if (value && typeof value === 'object') {
    try {
      return JSON.parse(JSON.stringify(value));
    } catch {
      return String(value);
    }
  }
  return value;
}

function elementSnapshot(element: Element, index: number) {
  const rect = element.getBoundingClientRect();
  const style = window.getComputedStyle(element);
  const centerX = rect.left + rect.width / 2;
  const centerY = rect.top + rect.height / 2;
  const topElement = rect.width > 0 && rect.height > 0
    ? document.elementFromPoint(centerX, centerY)
    : null;

  return {
    index,
    tag: element.tagName.toLowerCase(),
    text: element.textContent?.trim().replace(/\s+/g, ' ').slice(0, 80) || '',
    className: element.getAttribute('class') || '',
    rect: {
      left: Math.round(rect.left),
      top: Math.round(rect.top),
      width: Math.round(rect.width),
      height: Math.round(rect.height),
      right: Math.round(rect.right),
      bottom: Math.round(rect.bottom),
    },
    style: {
      display: style.display,
      visibility: style.visibility,
      opacity: style.opacity,
      pointerEvents: style.pointerEvents,
      zIndex: style.zIndex,
      color: style.color,
      backgroundColor: style.backgroundColor,
    },
    topElementAtCenter: topElement ? {
      tag: topElement.tagName.toLowerCase(),
      text: topElement.textContent?.trim().replace(/\s+/g, ' ').slice(0, 80) || '',
      className: topElement.getAttribute('class') || '',
      sameElement: topElement === element || element.contains(topElement),
    } : null,
  };
}

function findButtonsByText(text: string): Element[] {
  return Array.from(document.querySelectorAll('button, a')).filter(
    (element) => element.textContent?.trim().replace(/\s+/g, ' ') === text
  );
}

export function logSamuraiDiagnostic(event: string, details: Record<string, unknown> = {}) {
  if (typeof window === 'undefined') return;
  const entry: DiagnosticEvent = {
    ts: new Date().toISOString(),
    event,
    details: Object.fromEntries(
      Object.entries(details).map(([key, value]) => [key, cleanValue(value)])
    ),
  };
  writeEvents([...readEvents(), entry]);
  console.info('[SamuraiDiagnostics]', entry);
}

export function captureSamuraiSnapshot(reason: string) {
  if (typeof window === 'undefined') return;
  const fleetButtons = findButtonsByText('Fleet');
  const agentFlowButtons = findButtonsByText('Agent Flow');
  const nodePropertyButtons = Array.from(
    document.querySelectorAll('[title="Node Properties"], [aria-label^="Open properties"]')
  );
  const reactFlowNodes = Array.from(document.querySelectorAll('.react-flow__node'));
  const inspectorTitles = Array.from(document.querySelectorAll('h3')).filter(
    (element) => element.textContent?.trim() === 'Node Properties'
  );

  logSamuraiDiagnostic('samurai.snapshot', {
    reason,
    url: window.location.href,
    viewport: { width: window.innerWidth, height: window.innerHeight },
    document: {
      readyState: document.readyState,
      bodyClass: document.body.className,
      rootChildren: document.getElementById('root')?.children.length || 0,
    },
    counts: {
      fleetButtons: fleetButtons.length,
      agentFlowButtons: agentFlowButtons.length,
      nodePropertyButtons: nodePropertyButtons.length,
      reactFlowNodes: reactFlowNodes.length,
      inspectorTitles: inspectorTitles.length,
    },
    fleetButtons: fleetButtons.map(elementSnapshot),
    agentFlowButtons: agentFlowButtons.map(elementSnapshot),
    nodePropertyButtons: nodePropertyButtons.slice(0, 10).map(elementSnapshot),
    reactFlowNodes: reactFlowNodes.slice(0, 10).map(elementSnapshot),
    inspectorTitles: inspectorTitles.map(elementSnapshot),
  });
}

export function installSamuraiDiagnostics() {
  if (typeof window === 'undefined' || globalHandlersInstalled) return;
  globalHandlersInstalled = true;

  window.addEventListener('error', (event) => {
    logSamuraiDiagnostic('window.error', {
      message: event.message,
      filename: event.filename,
      lineno: event.lineno,
      colno: event.colno,
      error: event.error,
    });
  });

  window.addEventListener('unhandledrejection', (event) => {
    logSamuraiDiagnostic('window.unhandledrejection', {
      reason: event.reason,
    });
  });
}

export function clearSamuraiDiagnostics() {
  writeEvents([]);
  logSamuraiDiagnostic('diagnostics.cleared');
}

export function getSamuraiDiagnosticsText(): string {
  const events = readEvents();
  const header = [
    'SHOGUN SAMURAI DIAGNOSTICS',
    `diagnostic_build=${DIAGNOSTIC_BUILD}`,
    `created_at=${new Date().toISOString()}`,
    `url=${window.location.href}`,
    `user_agent=${navigator.userAgent}`,
    `events=${events.length}`,
    '',
  ];
  return header.concat(events.map((entry) => JSON.stringify(entry))).join('\n');
}

export async function copySamuraiDiagnostics(): Promise<boolean> {
  captureSamuraiSnapshot('copy');
  const text = getSamuraiDiagnosticsText();
  try {
    await navigator.clipboard.writeText(text);
    logSamuraiDiagnostic('diagnostics.copied', { length: text.length });
    return true;
  } catch {
    logSamuraiDiagnostic('diagnostics.copy_failed', { length: text.length });
    return false;
  }
}

export function downloadSamuraiDiagnostics() {
  captureSamuraiSnapshot('download');
  const text = getSamuraiDiagnosticsText();
  const blob = new Blob([text], { type: 'text/plain;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = `shogun-samurai-diagnostics-${new Date().toISOString().replace(/[:.]/g, '-')}.txt`;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
  logSamuraiDiagnostic('diagnostics.downloaded', { length: text.length });
}

export function getSamuraiDiagnosticBuild() {
  return DIAGNOSTIC_BUILD;
}
