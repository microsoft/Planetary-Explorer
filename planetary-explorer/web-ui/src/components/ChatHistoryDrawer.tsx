// Copyright (c) Microsoft Corporation.
// Licensed under the MIT license.

import React, { useRef, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  Download,
  FileDown,
  FileUp,
  FolderOpen,
  RefreshCw,
  Trash2,
  X,
} from 'lucide-react';

import {
  apiService,
  ChatHistoryAttachment,
  ChatHistorySession,
  ChatHistorySummary,
} from '../services/api';

interface ChatHistoryDrawerProps {
  activeSessionId: string;
  busy: boolean;
  enabled: boolean;
  open: boolean;
  onClose: () => void;
  onLoad: (session: ChatHistorySession) => boolean | void;
  onActiveSessionDeleted?: () => void;
}

function downloadBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 0);
}

function formatSavedAt(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return 'Unknown time';
  return new Intl.DateTimeFormat(undefined, {
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  }).format(date);
}

function formatBytes(value: number): string {
  if (!Number.isFinite(value) || value <= 0) return '0 B';
  const units = ['B', 'KB', 'MB', 'GB'];
  const unitIndex = Math.min(Math.floor(Math.log(value) / Math.log(1024)), units.length - 1);
  const amount = value / Math.pow(1024, unitIndex);
  return `${amount >= 10 || unitIndex === 0 ? amount.toFixed(0) : amount.toFixed(1)} ${units[unitIndex]}`;
}

function formatActionError(error: any): string {
  const detail = error?.response?.data?.detail;
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail)) {
    const messages = detail
      .map((item) => typeof item?.msg === 'string' ? item.msg : null)
      .filter(Boolean);
    if (messages.length > 0) return messages.join(' ');
  }
  return error?.message || 'History action failed.';
}

const ChatHistoryDrawer: React.FC<ChatHistoryDrawerProps> = ({
  activeSessionId,
  busy,
  enabled,
  open,
  onClose,
  onLoad,
  onActiveSessionDeleted,
}) => {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [actionKey, setActionKey] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  const historyQuery = useQuery({
    queryKey: ['chat-history-sessions'],
    queryFn: () => apiService.listChatSessions(),
    enabled: enabled && open,
    staleTime: 0,
  });
  const sessions = historyQuery.data || [];
  const activeSession = sessions.find((session) => session.sessionId === activeSessionId);

  const runAction = async (key: string, action: () => Promise<void>) => {
    setActionKey(key);
    setActionError(null);
    try {
      await action();
    } catch (error: any) {
      setActionError(formatActionError(error));
    } finally {
      setActionKey(null);
    }
  };

  const openSession = (sessionId: string) => runAction(`open:${sessionId}`, async () => {
    const session = await apiService.getChatSession(sessionId);
    if (onLoad(session) !== false) {
      onClose();
    }
  });

  const exportSession = (session: ChatHistorySummary) => runAction(`export:${session.sessionId}`, async () => {
    const blob = await apiService.exportChatSession(session.sessionId);
    downloadBlob(blob, `planetary-explorer-${session.sessionId}.zip`);
  });

  const deleteSession = (session: ChatHistorySummary) => runAction(`delete:${session.sessionId}`, async () => {
    if (!window.confirm(`Delete “${session.title}” and its saved files?`)) return;
    await apiService.deleteChatSession(session.sessionId);
    await historyQuery.refetch();
    if (session.sessionId === activeSessionId) {
      onActiveSessionDeleted?.();
      onClose();
    }
  });

  const uploadFile = (file: File) => runAction('upload', async () => {
    await apiService.uploadChatFile(activeSessionId, file);
    await historyQuery.refetch();
  });

  const downloadAttachment = (
    session: ChatHistorySummary,
    attachment: ChatHistoryAttachment,
  ) => runAction(`file:${attachment.id}`, async () => {
    const blob = await apiService.downloadChatFile(session.sessionId, attachment.id);
    downloadBlob(blob, attachment.name);
  });

  const deleteAttachment = (
    session: ChatHistorySummary,
    attachment: ChatHistoryAttachment,
  ) => runAction(`delete-file:${attachment.id}`, async () => {
    if (!window.confirm(`Delete “${attachment.name}”?`)) return;
    await apiService.deleteChatFile(session.sessionId, attachment.id);
    await historyQuery.refetch();
  });

  if (!open) return null;

  return (
    <>
      <button
        className="chat-history-backdrop"
        type="button"
        aria-label="Close saved sessions"
        onClick={onClose}
      />
      <aside className="chat-history-drawer" aria-label="Saved chat sessions">
        <div className="chat-history-drawer-header">
          <div>
            <span className="chat-history-eyebrow">Workspace archive</span>
            <h2>Saved sessions</h2>
          </div>
          <div className="chat-history-header-actions">
            <button
              type="button"
              className="chat-history-icon-button"
              title="Refresh saved sessions"
              aria-label="Refresh saved sessions"
              onClick={() => historyQuery.refetch()}
              disabled={busy || historyQuery.isFetching}
            >
              <RefreshCw size={17} aria-hidden="true" />
            </button>
            <button
              type="button"
              className="chat-history-icon-button"
              title="Close"
              aria-label="Close saved sessions"
              onClick={onClose}
            >
              <X size={18} aria-hidden="true" />
            </button>
          </div>
        </div>

        {actionError && <div className="chat-history-error" role="alert">{actionError}</div>}

        {activeSession && (
          <section className="chat-history-current" aria-label="Current saved session">
            <div className="chat-history-section-heading">
              <span>Current session</span>
              <span>{activeSession.messageCount} messages</span>
            </div>
            <strong>{activeSession.title}</strong>
            <div className="chat-history-current-actions">
              <button
                type="button"
                onClick={() => fileInputRef.current?.click()}
                disabled={busy || actionKey !== null}
              >
                <FileUp size={16} aria-hidden="true" />
                Add data file
              </button>
              <button
                type="button"
                onClick={() => exportSession(activeSession)}
                disabled={busy || actionKey !== null}
              >
                <FileDown size={16} aria-hidden="true" />
                Test bundle
              </button>
              <input
                ref={fileInputRef}
                type="file"
                hidden
                onChange={(event) => {
                  const file = event.target.files?.[0];
                  if (file) uploadFile(file);
                  event.target.value = '';
                }}
              />
            </div>

            {activeSession.attachments.length > 0 && (
              <div className="chat-history-files">
                {activeSession.attachments.map((attachment) => (
                  <div className="chat-history-file" key={attachment.id}>
                    <div>
                      <span>{attachment.name}</span>
                      <small>{formatBytes(attachment.size)}</small>
                    </div>
                    <div>
                      <button
                        type="button"
                        title={`Download ${attachment.name}`}
                        aria-label={`Download ${attachment.name}`}
                        onClick={() => downloadAttachment(activeSession, attachment)}
                        disabled={busy || actionKey !== null}
                      >
                        <Download size={15} aria-hidden="true" />
                      </button>
                      <button
                        type="button"
                        title={`Delete ${attachment.name}`}
                        aria-label={`Delete ${attachment.name}`}
                        onClick={() => deleteAttachment(activeSession, attachment)}
                        disabled={busy || actionKey !== null}
                      >
                        <Trash2 size={15} aria-hidden="true" />
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </section>
        )}

        <div className="chat-history-list" aria-live="polite">
          {historyQuery.isLoading && <div className="chat-history-empty">Loading saved sessions…</div>}
          {historyQuery.isError && (
            <div className="chat-history-error" role="alert">Saved sessions could not be loaded.</div>
          )}
          {!historyQuery.isLoading && !historyQuery.isError && sessions.length === 0 && (
            <div className="chat-history-empty">No saved sessions yet.</div>
          )}
          {sessions.map((session) => (
            <article
              className={`chat-history-session${session.sessionId === activeSessionId ? ' active' : ''}`}
              key={session.sessionId}
            >
              <button
                type="button"
                className="chat-history-session-main"
                onClick={() => openSession(session.sessionId)}
                disabled={busy || actionKey !== null}
              >
                <span className="chat-history-session-title">{session.title}</span>
                <span className="chat-history-session-meta">
                  {formatSavedAt(session.updatedAt)} · {session.messageCount} messages
                  {session.attachments.length > 0 ? ` · ${session.attachments.length} files` : ''}
                </span>
              </button>
              <div className="chat-history-session-actions">
                <button
                  type="button"
                  title="Open session"
                  aria-label={`Open ${session.title}`}
                  onClick={() => openSession(session.sessionId)}
                  disabled={busy || actionKey !== null}
                >
                  <FolderOpen size={16} aria-hidden="true" />
                </button>
                <button
                  type="button"
                  title="Download test bundle"
                  aria-label={`Download ${session.title} test bundle`}
                  onClick={() => exportSession(session)}
                  disabled={busy || actionKey !== null}
                >
                  <Download size={16} aria-hidden="true" />
                </button>
                <button
                  type="button"
                  title="Delete session"
                  aria-label={`Delete ${session.title}`}
                  onClick={() => deleteSession(session)}
                  disabled={busy || actionKey !== null}
                >
                  <Trash2 size={16} aria-hidden="true" />
                </button>
              </div>
            </article>
          ))}
        </div>
      </aside>
    </>
  );
};

export default ChatHistoryDrawer;