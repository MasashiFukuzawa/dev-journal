import { useEffect, useMemo, useState } from "react";
import {
	BrowserRouter,
	Navigate,
	Route,
	Routes,
	useParams,
} from "react-router-dom";
import { api } from "./api/client";
import { ChatPanel } from "./components/ChatPanel";
import { Layout } from "./components/Layout";
import { PhaseSection } from "./components/PhaseSection";
import type { ChatThread, DayDetail, IssueItem, IssueRef, ThreadInfo } from "./types";

type FilterMode = "all" | "yes" | "no";

interface Filters {
	confirmed: FilterMode;
	chat: FilterMode;
	unread: FilterMode;
}

const FILTER_STORAGE_KEY = "dev-journal:issue-filters";
const DEFAULT_FILTERS: Filters = { confirmed: "all", chat: "all", unread: "all" };

function issueKey(issue: IssueItem): string {
	return `${issue.repo}#${issue.issue_number}`;
}

function readFilters(): Filters {
	try {
		return { ...DEFAULT_FILTERS, ...JSON.parse(localStorage.getItem(FILTER_STORAGE_KEY) ?? "{}") };
	} catch {
		return DEFAULT_FILTERS;
	}
}

function matchesMode(value: boolean, mode: FilterMode): boolean {
	if (mode === "all") return true;
	return mode === "yes" ? value : !value;
}

function FilterGroup({
	label,
	value,
	onChange,
	offLabel = "無",
	onLabel = "有",
}: {
	label: string;
	value: FilterMode;
	onChange: (value: FilterMode) => void;
	offLabel?: string;
	onLabel?: string;
}) {
	const options: { value: FilterMode; label: string }[] = [
		{ value: "all", label: "全" },
		{ value: "no", label: offLabel },
		{ value: "yes", label: onLabel },
	];

	return (
		<div className="inline-flex items-center gap-1 rounded border border-border bg-surface px-1.5 py-1">
			<span
				className="px-1 text-[10px] text-ink-light"
				style={{ fontFamily: "var(--font-jetbrains)" }}
			>
				{label}
			</span>
			{options.map((option) => (
				<button
					key={option.value}
					type="button"
					onClick={() => onChange(option.value)}
					className={`min-w-7 rounded px-1.5 py-0.5 text-[11px] transition-colors ${
						value === option.value
							? "bg-cognac text-surface"
							: "text-ink-mid hover:bg-surface-hover"
					}`}
					style={{ fontFamily: "var(--font-jetbrains)" }}
				>
					{option.label}
				</button>
			))}
		</div>
	);
}

function Redirect() {
	const [latest, setLatest] = useState<string | null>(null);
	const [loading, setLoading] = useState(true);

	useEffect(() => {
		api.days
			.list()
			.then((days) => setLatest(days[0]?.date ?? null))
			.finally(() => setLoading(false));
	}, []);

	if (loading)
		return (
			<div
				className="p-6 text-ink-light italic"
				style={{ fontFamily: "var(--font-source-serif)" }}
			>
				読み込み中…
			</div>
		);
	if (!latest)
		return (
			<div
				className="p-6 text-ink-light italic"
				style={{ fontFamily: "var(--font-source-serif)" }}
			>
				データがありません。
			</div>
		);
	return <Navigate to={`/days/${latest}`} replace />;
}

interface DayViewProps {
	onAsk: (issue: IssueItem) => void;
	threadMap: Map<string, ThreadInfo>;
}

function DayView({ onAsk, threadMap }: DayViewProps) {
	const { date } = useParams<{ date: string }>();
	const [detail, setDetail] = useState<DayDetail | null>(null);
	const [loading, setLoading] = useState(true);
	const [error, setError] = useState<string | null>(null);
	const [filters, setFilters] = useState<Filters>(readFilters);

	useEffect(() => {
		if (!date) return;
		setLoading(true);
		setError(null);
		api.days
			.get(date)
			.then(setDetail)
			.catch((e: Error) => setError(e.message))
			.finally(() => setLoading(false));
	}, [date]);

	function updateFilter(key: keyof Filters, value: FilterMode) {
		setFilters((prev) => {
			const next = { ...prev, [key]: value };
			localStorage.setItem(FILTER_STORAGE_KEY, JSON.stringify(next));
			return next;
		});
	}

	async function toggleConfirmed(issue: IssueItem) {
		const nextValue = !issue.is_confirmed;
		setDetail((prev) =>
			prev
				? {
						...prev,
						phases: prev.phases.map((phase) => ({
							...phase,
							issues: phase.issues.map((item) =>
								item.repo === issue.repo && item.issue_number === issue.issue_number
									? { ...item, is_confirmed: nextValue }
									: item,
							),
						})),
					}
				: prev,
		);
		try {
			await api.issues.updateState(issue.repo, issue.issue_number, nextValue);
		} catch (e) {
			setError(e instanceof Error ? e.message : "確認状態の更新に失敗しました");
			setDetail((prev) =>
				prev
					? {
							...prev,
							phases: prev.phases.map((phase) => ({
								...phase,
								issues: phase.issues.map((item) =>
									item.repo === issue.repo && item.issue_number === issue.issue_number
										? { ...item, is_confirmed: !nextValue }
										: item,
								),
							})),
						}
					: prev,
			);
		}
	}

	return (
		<Layout activeDate={date ?? ""}>
			{loading && (
				<p
					className="text-ink-light italic"
					style={{ fontFamily: "var(--font-source-serif)" }}
				>
					読み込み中…
				</p>
			)}
			{error && <p className="text-[#a83228]">{error}</p>}
			{detail && (() => {
				const allIssues = detail.phases.flatMap((p) => p.issues);
				const totalCount = allIssues.length;
				const filteredPhases = detail.phases
					.map((phase) => ({
						...phase,
						issues: phase.issues.filter((issue) => {
							const thread = threadMap.get(issueKey(issue));
							return (
								matchesMode(issue.is_confirmed, filters.confirmed) &&
								matchesMode(Boolean(thread && thread.messageCount > 0), filters.chat) &&
								matchesMode(Boolean(thread?.hasUnread), filters.unread)
							);
						}),
					}))
					.filter((phase) => phase.issues.length > 0);

				return (
					<div>
						<div className="mb-10 pb-10 border-b-2 border-border">
							<p
								className="text-[10px] font-bold uppercase tracking-[0.18em] text-cognac mb-2.5"
								style={{ fontFamily: "var(--font-fraunces)" }}
							>
								Engineering Log
							</p>
							<h2
								className="text-[40px] font-extrabold text-ink leading-[1.1] tracking-[-0.5px]"
								style={{ fontFamily: "var(--font-fraunces)" }}
							>
								{detail.date}
							</h2>
							<div className="mt-4 flex gap-2.5 flex-wrap">
								<span
									className="inline-flex items-center gap-1.5 px-2.5 py-1 border border-border rounded-sm text-[11px] text-ink-mid bg-surface"
									style={{ fontFamily: "var(--font-jetbrains)" }}
								>
									<span className="w-1.5 h-1.5 rounded-full bg-cognac shrink-0" />
									{totalCount} Issues
								</span>
							</div>
							<div className="mt-4 flex flex-wrap gap-2">
								<FilterGroup
									label="確認"
									value={filters.confirmed}
									onChange={(value) => updateFilter("confirmed", value)}
									offLabel="未"
									onLabel="済"
								/>
								<FilterGroup
									label="Chat"
									value={filters.chat}
									onChange={(value) => updateFilter("chat", value)}
								/>
								<FilterGroup
									label="未読"
									value={filters.unread}
									onChange={(value) => updateFilter("unread", value)}
								/>
							</div>
						</div>
						{filteredPhases.length === 0 && (
							<p
								className="text-[13px] text-ink-light italic"
								style={{ fontFamily: "var(--font-source-serif)" }}
							>
								条件に一致するIssueはありません。
							</p>
						)}
						{filteredPhases.map((phase) => (
							<PhaseSection
								key={`${phase.order}-${phase.name ?? ""}`}
								phase={phase}
								onToggleConfirmed={toggleConfirmed}
								onAsk={onAsk}
								threadMap={threadMap}
							/>
						))}
					</div>
				);
			})()}
		</Layout>
	);
}

function RootRedirect() {
	return (
		<Layout>
			<Redirect />
		</Layout>
	);
}

export default function App() {
	const [chatOpen, setChatOpen] = useState(false);
	const [chatIssueRefs, setChatIssueRefs] = useState<IssueRef[]>([]);
	const [threads, setThreads] = useState<ChatThread[]>([]);

	useEffect(() => {
		const fetch = () => api.chat.getThreads().then(setThreads).catch(console.error);
		fetch();
		const id = setInterval(fetch, 10_000);
		return () => clearInterval(id);
	}, []);

	const threadMap = useMemo(() => {
		const map = new Map<string, ThreadInfo>();
		for (const thread of threads) {
			const messageCount = thread.message_count ?? thread.messages?.length ?? 0;
			const hasPending = thread.has_pending ?? thread.messages?.some(m => m.status === "pending") ?? false;
			const hasUnread = thread.has_unread ?? false;
			const unreadCount = thread.unread_count ?? 0;
			for (const ref of thread.issue_refs) {
				const key = `${ref.repo}#${ref.issue_number}`;
				const existing = map.get(key);
				if (!existing || (hasUnread && !existing.hasUnread) || (hasPending && !existing.hasPending) || messageCount > existing.messageCount) {
					map.set(key, { messageCount, hasPending, hasUnread, unreadCount });
				}
			}
		}
		return map;
	}, [threads]);

	function handleAsk(issue: IssueItem) {
		setChatIssueRefs([{ repo: issue.repo, issue_number: issue.issue_number }]);
		setChatOpen(true);
	}

	return (
		<BrowserRouter>
			<Routes>
				<Route path="/" element={<RootRedirect />} />
				<Route path="/days/:date" element={<DayView onAsk={handleAsk} threadMap={threadMap} />} />
			</Routes>
			<ChatPanel
				isOpen={chatOpen}
				onClose={() => setChatOpen(false)}
				issueRefs={chatIssueRefs}
			/>
		</BrowserRouter>
	);
}
