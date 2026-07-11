import { useCallback, useState } from "react";

const STORAGE_KEY = "dev-journal:closed-issues";

function readClosedSet(): Record<string, true> {
	try {
		return JSON.parse(localStorage.getItem(STORAGE_KEY) ?? "{}") as Record<
			string,
			true
		>;
	} catch {
		return {};
	}
}

function writeClosedSet(set: Record<string, true>): void {
	localStorage.setItem(STORAGE_KEY, JSON.stringify(set));
}

export function useAccordionState() {
	const [closedSet, setClosedSet] =
		useState<Record<string, true>>(readClosedSet);

	const isClosed = useCallback((key: string) => key in closedSet, [closedSet]);

	const toggle = useCallback((key: string) => {
		setClosedSet((prev) => {
			const next = { ...prev };
			if (key in next) {
				delete next[key];
			} else {
				next[key] = true;
			}
			writeClosedSet(next);
			return next;
		});
	}, []);

	return { isClosed, toggle, closedSet };
}
