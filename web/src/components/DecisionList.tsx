import type { Decision } from "../types";

const KIND_CONFIG: Record<
	string,
	{ label: string; bg: string; border: string; text: string; badge: string }
> = {
	adopted: {
		label: "採用",
		bg: "#eef7f2",
		border: "#276845",
		text: "#1a4a30",
		badge: "#276845",
	},
	rejected: {
		label: "却下",
		bg: "#fdf2f0",
		border: "#a83228",
		text: "#6e1e18",
		badge: "#a83228",
	},
	implemented: {
		label: "実装",
		bg: "#eef3fb",
		border: "#2756a0",
		text: "#1a356e",
		badge: "#2756a0",
	},
	out_of_scope: {
		label: "非スコープ",
		bg: "#f4f0fb",
		border: "#6b4ea0",
		text: "#3d2070",
		badge: "#6b4ea0",
	},
};

interface Props {
	decisions: Decision[];
}

export function DecisionList({ decisions }: Props) {
	if (decisions.length === 0) return null;
	return (
		<ul className="flex flex-col gap-1.5">
			{decisions.map((d, i) => {
				const cfg = KIND_CONFIG[d.kind] ?? KIND_CONFIG.implemented;
				return (
					<li
						key={i}
						className="flex items-start gap-2.5 px-2.5 py-2 text-[13px] leading-[1.6]"
						style={{
							background: cfg.bg,
							borderLeft: `3px solid ${cfg.border}`,
							color: cfg.text,
						}}
					>
						<span
							className="mt-0.5 shrink-0 rounded px-1.5 py-0.5 text-[9px] font-bold uppercase tracking-[0.1em] text-white"
							style={{
								fontFamily: "var(--font-fraunces)",
								background: cfg.badge,
							}}
						>
							{cfg.label}
						</span>
						<span>
							<span className="font-semibold">{d.title}</span>
							{d.reason && (
								<span className="ml-1 opacity-80">— {d.reason}</span>
							)}
						</span>
					</li>
				);
			})}
		</ul>
	);
}
