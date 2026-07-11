import type { IssueItem, PhaseGroup, ThreadInfo } from "../types";
import { IssueCard } from "./IssueCard";

interface Props {
	phase: PhaseGroup;
	onToggleConfirmed: (issue: IssueItem) => void;
	onAsk?: (issue: IssueItem) => void;
	threadMap?: Map<string, ThreadInfo>;
}

function issueKey(repo: string, number: number): string {
	return `${repo}#${number}`;
}

export function PhaseSection({ phase, onToggleConfirmed, onAsk, threadMap }: Props) {
	const phaseKeys = phase.issues.map((i) => issueKey(i.repo, i.issue_number));
	const totalCount = phaseKeys.length;
	const confirmedCount = phase.issues.filter((issue) => issue.is_confirmed).length;

	return (
		<section className="mb-16">
			{phase.name && (
				<div className="mb-4 flex items-start gap-5">
					{/* Giant phase number */}
					<div className="w-16 shrink-0 pt-1 select-none" aria-hidden>
						<span
							className="block leading-none text-border text-[72px] font-extrabold tracking-[-4px]"
							style={{ fontFamily: "var(--font-fraunces)", lineHeight: 0.88 }}
						>
							{phase.order + 1}
						</span>
					</div>
					<div className="flex-1 pt-2">
						<div className="flex items-baseline gap-3">
							<h3
								className="text-[21px] font-bold text-ink leading-snug"
								style={{ fontFamily: "var(--font-fraunces)" }}
							>
								{phase.name}
							</h3>
							<span
								className="text-[12px] text-ink-light tabular-nums"
								style={{ fontFamily: "var(--font-jetbrains)" }}
							>
								{confirmedCount} / {totalCount}
							</span>
						</div>
						<hr className="mt-3 mb-3.5 border-border" />
					</div>
				</div>
			)}
			<div className="space-y-3">
				{phase.issues.map((issue) => {
					const key = issueKey(issue.repo, issue.issue_number);
					return (
						<IssueCard
							key={key}
							issue={issue}
							issueKey={key}
							isConfirmed={issue.is_confirmed}
							onToggleConfirmed={onToggleConfirmed}
							onAsk={onAsk}
							thread={threadMap?.get(key)}
						/>
					);
				})}
			</div>
		</section>
	);
}
