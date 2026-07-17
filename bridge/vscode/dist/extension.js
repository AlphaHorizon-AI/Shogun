"use strict";
var __createBinding = (this && this.__createBinding) || (Object.create ? (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    var desc = Object.getOwnPropertyDescriptor(m, k);
    if (!desc || ("get" in desc ? !m.__esModule : desc.writable || desc.configurable)) {
      desc = { enumerable: true, get: function() { return m[k]; } };
    }
    Object.defineProperty(o, k2, desc);
}) : (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    o[k2] = m[k];
}));
var __setModuleDefault = (this && this.__setModuleDefault) || (Object.create ? (function(o, v) {
    Object.defineProperty(o, "default", { enumerable: true, value: v });
}) : function(o, v) {
    o["default"] = v;
});
var __importStar = (this && this.__importStar) || (function () {
    var ownKeys = function(o) {
        ownKeys = Object.getOwnPropertyNames || function (o) {
            var ar = [];
            for (var k in o) if (Object.prototype.hasOwnProperty.call(o, k)) ar[ar.length] = k;
            return ar;
        };
        return ownKeys(o);
    };
    return function (mod) {
        if (mod && mod.__esModule) return mod;
        var result = {};
        if (mod != null) for (var k = ownKeys(mod), i = 0; i < k.length; i++) if (k[i] !== "default") __createBinding(result, mod, k[i]);
        __setModuleDefault(result, mod);
        return result;
    };
})();
Object.defineProperty(exports, "__esModule", { value: true });
exports.activate = activate;
exports.deactivate = deactivate;
const vscode = __importStar(require("vscode"));
let socket;
let status;
const send = (type, payload) => socket?.send(JSON.stringify({ type, request_id: crypto.randomUUID(), timestamp: new Date().toISOString(), payload }));
async function connect(context) {
    const token = await vscode.window.showInputBox({ title: 'Pair Shogun IDE Bridge', prompt: 'Enter the one-time token shown in Katana → IDE Mode', password: true, ignoreFocusOut: true });
    if (!token)
        return;
    const configured = String(vscode.workspace.getConfiguration('shogun').get('bridgeUrl', 'ws://127.0.0.1:8000/api/v1/ide/bridge'));
    const url = new URL(configured);
    if (!['127.0.0.1', 'localhost', '::1'].includes(url.hostname))
        throw new Error('Shogun IDE Bridge only permits localhost by default.');
    url.searchParams.set('token', token);
    socket = new WebSocket(url);
    socket.addEventListener('open', () => {
        status.text = '$(shield) Shogun IDE';
        status.backgroundColor = new vscode.ThemeColor('statusBarItem.prominentBackground');
        const folder = vscode.workspace.workspaceFolders?.[0];
        if (folder)
            send('workspace.register', workspaceMetadata(folder));
    });
    socket.addEventListener('message', event => handleMessage(context, JSON.parse(String(event.data))));
    socket.addEventListener('close', () => { status.text = '$(debug-disconnect) Shogun IDE'; status.backgroundColor = undefined; });
    socket.addEventListener('error', () => vscode.window.showErrorMessage('Shogun IDE Bridge connection failed.'));
}
function workspaceMetadata(folder) {
    const tasks = vscode.tasks.fetchTasks().then((items) => items.map((item) => item.name));
    void tasks.then((available_tasks) => send('event', { type: 'workspace.tasks', available_tasks }));
    return { workspace_name: folder.name, workspace_root: folder.uri.fsPath, extension_version: '0.1.0', diagnostics_available: true };
}
async function handleMessage(context, message) {
    if (message.type !== 'request')
        return;
    const { request_id, action: type, payload } = message;
    try {
        let result;
        if (type === 'editor.context') {
            const editor = vscode.window.activeTextEditor;
            result = { active_file: editor?.document.uri.fsPath, selection: editor?.document.getText(editor.selection), open_tabs: vscode.window.tabGroups.all.flatMap((g) => g.tabs.map((t) => t.label)) };
        }
        else if (type === 'diagnostics.get') {
            result = vscode.languages.getDiagnostics().map(([uri, diagnostics]) => ({ file: uri.fsPath, diagnostics: diagnostics.map((d) => ({ message: d.message, severity: d.severity, source: d.source, code: d.code, range: d.range })) }));
        }
        else if (type === 'editor.open') {
            const root = vscode.workspace.workspaceFolders?.[0]?.uri;
            if (!root)
                throw new Error('No workspace open');
            const uri = vscode.Uri.joinPath(root, payload.path);
            await vscode.window.showTextDocument(uri);
            result = { opened: true };
        }
        else
            throw new Error(`Unsupported bridge request: ${type}`);
        socket?.send(JSON.stringify({ type: 'response', request_id, timestamp: new Date().toISOString(), status: 'success', payload: result }));
    }
    catch (error) {
        socket?.send(JSON.stringify({ type: 'response', request_id, timestamp: new Date().toISOString(), status: 'error', error: { message: error.message } }));
    }
}
function activate(context) {
    status = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Left, 100);
    status.text = '$(debug-disconnect) Shogun IDE';
    status.command = 'shogun.connect';
    status.show();
    context.subscriptions.push(status, vscode.commands.registerCommand('shogun.connect', () => connect(context)), vscode.commands.registerCommand('shogun.disconnect', () => socket?.close()), vscode.commands.registerCommand('shogun.openDashboard', () => vscode.env.openExternal(vscode.Uri.parse('http://127.0.0.1:8000/katana'))));
}
function deactivate() { socket?.close(); }
