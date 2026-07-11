import { useEffect, useState } from "react";
import { api } from "../api/client";
import type { DayMeta } from "../types";
import { DayTabs } from "./DayTabs";

interface Props {
	children: React.ReactNode;
	activeDate?: string;
}

export function Layout({ children, activeDate = "" }: Props) {
	const [days, setDays] = useState<DayMeta[]>([]);

	useEffect(() => {
		api.days.list().then(setDays).catch(console.error);
	}, []);

	return (
		<div className="flex h-screen bg-paper">
			{/* Sidebar */}
			<aside className="hidden w-52 shrink-0 flex-col border-r border-border bg-surface md:flex">
				<div className="flex items-center justify-between border-b border-border px-5 py-5">
					<p
						className="text-[10px] font-bold uppercase tracking-[0.18em] text-cognac"
						style={{ fontFamily: "var(--font-fraunces)" }}
					>
						dev-journal
					</p>
				</div>
				<nav className="flex-1 overflow-y-auto p-3">
					<DayTabs days={days} activeDate={activeDate} />
				</nav>
			</aside>

			{/* Main */}
			<div className="flex flex-1 flex-col overflow-hidden">
				{/* Mobile: horizontal day tabs */}
				<div className="border-b border-border bg-surface px-3 py-2 md:hidden">
					<DayTabs days={days} activeDate={activeDate} />
				</div>

				<main className="flex-1 overflow-y-auto p-4 md:p-10">{children}</main>
			</div>
		</div>
	);
}
