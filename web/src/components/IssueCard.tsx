import type { IssueItem, ThreadInfo } from "../types";
import { DecisionList } from "./DecisionList";
import { LabelBadge } from "./LabelBadge";

function formatJst(isoUtc: string): string {
	try {
		return new Intl.DateTimeFormat("ja-JP", {
			timeZone: "Asia/Tokyo",
			month: "numeric",
			day: "numeric",
			hour: "2-digit",
			minute: "2-digit",
		}).format(new Date(isoUtc));
	} catch {
		return isoUtc;
	}
}

function repoShort(repo: string): string {
	return repo.split("/").pop() ?? repo;
}

interface Props {
	issue: IssueItem;
	issueKey: string;
	isConfirmed: boolean;
	onToggleConfirmed: (issue: IssueItem) => void;
	onAsk?: (issue: IssueItem) => void;
	thread?: ThreadInfo;
}

export function IssueCard({
	issue,
	isConfirmed,
	onToggleConfirmed,
	onAsk,
	thread,
}: Props) {
	const dd = issue.deep_dive;

	return (
		<div className="overflow-hidden rounded-r-lg border border-border border-l-[3px] border-l-cognac bg-surface">
			{/* Header — div+role to allow button children (avoid nested <button>) */}
			<div
				role="button"
				tabIndex={0}
				className="flex w-full flex-col gap-1.5 px-5 py-3.5 text-left transition-colors duration-100 hover:bg-cognac-pale cursor-pointer"
				onClick={() => onToggleConfirmed(issue)}
				onKeyDown={(e) => {
					if (e.key === "Enter" || e.key === " ") onToggleConfirmed(issue);
				}}
			>
				{/* Row 1: issue number + repo tag + ask button + chevron */}
				<div className="flex w-full items-center justify-between gap-2">
					<div className="flex items-center gap-2">
						<a
							href={issue.url}
							target="_blank"
							rel="noopener noreferrer"
							className="text-[13px] font-bold text-cognac hover:underline"
							style={{ fontFamily: "var(--font-fraunces)" }}
							onClick={(e) => e.stopPropagation()}
						>
							#{issue.issue_number}
						</a>
						<span
							className="rounded px-1.5 py-px text-[10px] text-ink-light border border-border-light bg-border-light"
							style={{ fontFamily: "var(--font-jetbrains)" }}
						>
							{repoShort(issue.repo)}
						</span>
						{onAsk && (
							<button
								type="button"
								className="rounded px-2 py-px text-[10px] font-semibold text-cognac border border-cognac/40 hover:bg-cognac hover:text-surface transition-colors duration-100"
								style={{ fontFamily: "var(--font-fraunces)" }}
								onClick={(e) => {
									e.stopPropagation();
									onAsk(issue);
								}}
							>
								質問する
							</button>
						)}
						{thread && (thread.messageCount > 0 || thread.hasPending) && (
							<span
								className="inline-flex items-center gap-1 rounded px-1.5 py-px text-[10px] text-ink-mid border border-border bg-surface"
								style={{ fontFamily: "var(--font-jetbrains)" }}
							>
								Chat {thread.messageCount}
							</span>
						)}
						{thread?.hasUnread && (
							<span
								className="inline-flex items-center rounded bg-cognac px-1.5 py-px text-[10px] font-semibold text-surface"
								style={{ fontFamily: "var(--font-jetbrains)" }}
							>
								未読 {thread.unreadCount}
							</span>
						)}
						{isConfirmed && (
							<span
								className="inline-flex items-center rounded border border-border bg-paper px-1.5 py-px text-[10px] text-ink-light"
								style={{ fontFamily: "var(--font-jetbrains)" }}
							>
								確認済み
							</span>
						)}
					</div>
					<svg
						className={`h-[11px] w-[11px] shrink-0 text-ink-light transition-transform duration-200 ${isConfirmed ? "" : "rotate-180"}`}
						fill="none"
						viewBox="0 0 24 24"
						stroke="currentColor"
						strokeWidth={2.5}
					>
						<path
							strokeLinecap="round"
							strokeLinejoin="round"
							d="M19 9l-7 7-7-7"
						/>
					</svg>
				</div>

				{/* Row 2: title */}
				<p
					className="text-[15px] font-semibold text-ink leading-snug"
					style={{ fontFamily: "var(--font-source-serif)" }}
				>
					{issue.title}
				</p>

				{/* Row 3: labels + date */}
				<div className="flex flex-wrap items-center gap-1.5">
					{issue.labels.map((l) => (
						<LabelBadge key={l} label={l} />
					))}
					<span
						className="text-[11px] text-ink-light"
						style={{ fontFamily: "var(--font-jetbrains)" }}
					>
						{formatJst(issue.closed_at)}
					</span>
				</div>
			</div>

			{/* Body */}
			{!isConfirmed && dd && (
				<div className="border-t border-border-light px-5 pb-5">
					<div className="mt-5 space-y-4">
						<div>
							<p
								className="mb-2 text-[10px] font-bold uppercase tracking-[0.14em] text-ink-light"
								style={{ fontFamily: "var(--font-fraunces)" }}
							>
								背景
							</p>
							<p className="text-[13.5px] leading-[1.72] text-ink">
								{dd.background}
							</p>
						</div>

						{dd.decisions.length > 0 && (
							<div>
								<p
									className="mb-2 text-[10px] font-bold uppercase tracking-[0.14em] text-ink-light"
									style={{ fontFamily: "var(--font-fraunces)" }}
								>
									決定事項
								</p>
								<DecisionList decisions={dd.decisions} />
							</div>
						)}

						{dd.constraints.length > 0 && (
							<div>
								<p
									className="mb-2 text-[10px] font-bold uppercase tracking-[0.14em] text-ink-light"
									style={{ fontFamily: "var(--font-fraunces)" }}
								>
									制約・前提
								</p>
								<ul className="list-disc list-inside space-y-1">
									{dd.constraints.map((c, i) => (
										<li
											key={i}
											className="text-[13.5px] leading-[1.72] text-ink"
										>
											{c}
										</li>
									))}
								</ul>
							</div>
						)}

						{dd.future.length > 0 && (
							<div>
								<p
									className="mb-2 text-[10px] font-bold uppercase tracking-[0.14em] text-ink-light"
									style={{ fontFamily: "var(--font-fraunces)" }}
								>
									今後の課題
								</p>
								<ul className="list-disc list-inside space-y-1">
									{dd.future.map((f, i) => (
										<li
											key={i}
											className="text-[13.5px] leading-[1.72] text-ink"
										>
											{f}
										</li>
									))}
								</ul>
							</div>
						)}
					</div>
				</div>
			)}

			{!isConfirmed && !dd && (
				<div className="border-t border-border-light px-5 py-4">
					<p className="text-[13.5px] italic text-ink-light">解説生成待ち</p>
				</div>
			)}
		</div>
	);
}
