interface Props {
	label: string;
}

export function LabelBadge({ label }: Props) {
	return (
		<span
			className="inline-block rounded px-1.5 py-px text-[9px] text-ink-light border border-border-light bg-border-light"
			style={{ fontFamily: "var(--font-jetbrains)" }}
		>
			{label}
		</span>
	);
}
