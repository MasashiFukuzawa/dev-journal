export interface DayMeta {
	date: string;
	issue_count: number;
	phase_count: number;
}

export interface Decision {
	kind: "adopted" | "rejected" | "implemented" | "out_of_scope";
	title: string;
	reason: string;
}

export interface DeepDive {
	background: string;
	decisions: Decision[];
	constraints: string[];
	future: string[];
}

export interface IssueItem {
	issue_number: number;
	repo: string;
	title: string;
	url: string;
	closed_at: string;
	labels: string[];
	deep_dive: DeepDive | null;
	is_confirmed: boolean;
}

export interface IssueComment {
	author: string;
	body: string;
	created_at: string;
}

export interface IssueItemFull extends IssueItem {
	body: string | null;
	comments: IssueComment[];
}

export interface PhaseGroup {
	name: string | null;
	order: number;
	issues: IssueItem[];
}

export interface DayDetail {
	date: string;
	phases: PhaseGroup[];
}

export interface IssueRef {
	repo: string;
	issue_number: number;
}

export interface ChatMessage {
	id: number;
	thread_id: string;
	role: "user" | "assistant";
	content: string;
	status?: string;
	created_at: string;
}

export interface ChatThread {
	id: string;
	created_at: string;
	title: string | null;
	issue_refs: IssueRef[];
	messages: ChatMessage[];
	message_count?: number;
	has_pending?: boolean;
	unread_count?: number;
	has_unread?: boolean;
	last_message_at?: string | null;
}

export interface ThreadInfo {
	messageCount: number;
	hasPending: boolean;
	hasUnread: boolean;
	unreadCount: number;
}
