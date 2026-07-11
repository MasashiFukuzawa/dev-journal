import { useNavigate } from "react-router-dom";
import type { DayMeta } from "../types";

function formatTabDate(date: string): string {
	const [, m, d] = date.split("-");
	return `${parseInt(m, 10)}/${parseInt(d, 10)}`;
}

interface Props {
	days: DayMeta[];
	activeDate: string;
}

export function DayTabs({ days, activeDate }: Props) {
	const navigate = useNavigate();

	return (
		<div className="flex gap-0.5 overflow-x-auto pb-1 scrollbar-none md:flex-col md:overflow-x-visible md:pb-0">
			{days.map((day) => {
				const isActive = day.date === activeDate;
				return (
					<button
						key={day.date}
						type="button"
						onClick={() => navigate(`/days/${day.date}`)}
						className={`shrink-0 rounded px-3 py-2 text-left transition-colors duration-100 ${
							isActive
								? "bg-cognac-pale text-cognac"
								: "text-ink-mid hover:bg-surface-hover hover:text-ink"
						}`}
					>
						<span
							className="block text-[13px] font-semibold"
							style={{
								fontFamily: isActive ? "var(--font-fraunces)" : undefined,
							}}
						>
							{formatTabDate(day.date)}
						</span>
						<span
							className="block text-[11px] text-ink-light"
							style={{ fontFamily: "var(--font-jetbrains)" }}
						>
							{day.issue_count}件
						</span>
					</button>
				);
			})}
		</div>
	);
}
