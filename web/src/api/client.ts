import type {
	ChatThread,
	DayDetail,
	DayMeta,
	IssueItemFull,
	IssueRef,
} from "../types";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
	const res = await fetch(path, init);
	if (!res.ok) {
		const err = await res.json().catch(() => ({ detail: res.statusText }));
		throw new Error((err as { detail?: string }).detail ?? res.statusText);
	}
	return res.json() as Promise<T>;
}

export const api = {
	days: {
		list: () => request<DayMeta[]>("/api/days"),
		get: (date: string) => request<DayDetail>(`/api/days/${date}`),
	},
	issues: {
		getIssue: (repo: string, issueNumber: number) =>
			request<IssueItemFull>(`/api/issues/${repo}/${issueNumber}`),
		updateState: (repo: string, issueNumber: number, isConfirmed: boolean) =>
			request<{ repo: string; issue_number: number; is_confirmed: boolean }>(
				`/api/issues/${repo}/${issueNumber}/state`,
				{
					method: "PATCH",
					headers: { "Content-Type": "application/json" },
					body: JSON.stringify({ is_confirmed: isConfirmed }),
				},
			),
	},
	chat: {
		createThread: (issueRefs: IssueRef[]) =>
			request<ChatThread>("/api/chat/threads", {
				method: "POST",
				headers: { "Content-Type": "application/json" },
				body: JSON.stringify({ issue_refs: issueRefs }),
			}),
		getThreads: () => request<ChatThread[]>("/api/chat/threads"),
		getThread: (threadId: string) =>
			request<ChatThread>(`/api/chat/threads/${threadId}`),
		markRead: (threadId: string) =>
			request<{ id: string; last_read_assistant_message_id: number | null }>(
				`/api/chat/threads/${threadId}/read`,
				{ method: "POST" },
			),
		deleteThread: (threadId: string) =>
			request<void>(`/api/chat/threads/${threadId}`, { method: "DELETE" }),
		sendMessage: (threadId: string, content: string) =>
			request<{ status: string; message_id: number }>(
				`/api/chat/threads/${threadId}/messages`,
				{
					method: "POST",
					headers: { "Content-Type": "application/json" },
					body: JSON.stringify({ content }),
				},
			),
		pollMessageStatus: (threadId: string, messageId: number) =>
			request<{ status: string; content: string }>(
				`/api/chat/threads/${threadId}/messages/${messageId}/status`,
			),
	},
};
