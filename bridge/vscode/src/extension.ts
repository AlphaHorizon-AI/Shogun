import * as vscode from 'vscode';

let socket: WebSocket | undefined;
let status: any;

const send = (type: string, payload: unknown) => socket?.send(JSON.stringify({ type, request_id: crypto.randomUUID(), timestamp: new Date().toISOString(), payload }));

async function connect(context: any) {
  const token = await vscode.window.showInputBox({ title: 'Pair Shogun IDE Bridge', prompt: 'Enter the one-time token shown in Katana → IDE Mode', password: true, ignoreFocusOut: true });
  if (!token) return;
  const configured = String(vscode.workspace.getConfiguration('shogun').get('bridgeUrl', 'ws://127.0.0.1:8000/api/v1/ide/bridge'));
  const url = new URL(configured);
  if (!['127.0.0.1', 'localhost', '::1'].includes(url.hostname)) throw new Error('Shogun IDE Bridge only permits localhost by default.');
  url.searchParams.set('token', token); socket = new WebSocket(url);
  socket.addEventListener('open', () => {
    status.text = '$(shield) Shogun IDE'; status.backgroundColor = new vscode.ThemeColor('statusBarItem.prominentBackground');
    const folder = vscode.workspace.workspaceFolders?.[0];
    if (folder) send('workspace.register', workspaceMetadata(folder));
  });
  socket.addEventListener('message', event => handleMessage(context, JSON.parse(String(event.data))));
  socket.addEventListener('close', () => { status.text = '$(debug-disconnect) Shogun IDE'; status.backgroundColor = undefined; });
  socket.addEventListener('error', () => vscode.window.showErrorMessage('Shogun IDE Bridge connection failed.'));
}

function workspaceMetadata(folder: any) {
  const tasks = vscode.tasks.fetchTasks().then((items: any[]) => items.map((item: any) => item.name));
  void tasks.then((available_tasks: string[]) => send('event', { type: 'workspace.tasks', available_tasks }));
  return { workspace_name: folder.name, workspace_root: folder.uri.fsPath, extension_version: '0.1.0', diagnostics_available: true };
}

async function handleMessage(context: any, message: any) {
  if (message.type !== 'request') return;
  const { request_id, action: type, payload } = message;
  try {
    let result: any;
    if (type === 'editor.context') {
      const editor=vscode.window.activeTextEditor;
      result={ active_file: editor?.document.uri.fsPath, selection: editor?.document.getText(editor.selection), open_tabs: vscode.window.tabGroups.all.flatMap((g: any) => g.tabs.map((t: any) => t.label)) };
    } else if (type === 'diagnostics.get') {
      result=vscode.languages.getDiagnostics().map(([uri, diagnostics]: [any, any[]]) => ({ file: uri.fsPath, diagnostics: diagnostics.map((d: any) => ({ message:d.message, severity:d.severity, source:d.source, code:d.code, range:d.range })) }));
    } else if (type === 'editor.open') {
      const root=vscode.workspace.workspaceFolders?.[0]?.uri; if (!root) throw new Error('No workspace open');
      const uri=vscode.Uri.joinPath(root, payload.path); await vscode.window.showTextDocument(uri); result={ opened:true };
    } else throw new Error(`Unsupported bridge request: ${type}`);
    socket?.send(JSON.stringify({ type:'response', request_id, timestamp:new Date().toISOString(), status:'success', payload:result }));
  } catch (error: any) { socket?.send(JSON.stringify({ type:'response', request_id, timestamp:new Date().toISOString(), status:'error', error:{ message:error.message } })); }
}

export function activate(context: any) {
  status=vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Left, 100); status.text='$(debug-disconnect) Shogun IDE'; status.command='shogun.connect'; status.show();
  context.subscriptions.push(status,
    vscode.commands.registerCommand('shogun.connect', () => connect(context)),
    vscode.commands.registerCommand('shogun.disconnect', () => socket?.close()),
    vscode.commands.registerCommand('shogun.openDashboard', () => vscode.env.openExternal(vscode.Uri.parse('http://127.0.0.1:8000/katana'))));
}
export function deactivate() { socket?.close(); }
