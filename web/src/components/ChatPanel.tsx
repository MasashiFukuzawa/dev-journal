import "highlight.js/styles/github.css";
import { useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import rehypeHighlight from "rehype-highlight";
import remarkGfm from "remark-gfm";
import { api } from "../api/client";
import type { ChatMessage, IssueRef } from "../types";

interface Props {
	isOpen: boolean;
	onClose: () => void;
	issueRefs: IssueRef[];
}

function repoShort(repo: string): string {
	return repo.split("/").pop() ?? repo;
}

function resolveIssueUrl(num: number, issueRefs: IssueRef[]): string | null {
	const exact = issueRefs.find((r) => r.issue_number === num);
	if (exact) return `https://github.com/${exact.repo}/issues/${num}`;
	if (issueRefs.length > 0)
		return `https://github.com/${issueRefs[0].repo}/issues/${num}`;
	return null;
}

function injectIssueLinks(content: string, issueRefs: IssueRef[]): string {
	if (issueRefs.length === 0) return content;
	const parts = content.split(/(```[\s\S]*?```|`[^`]*`)/g);
	return parts
		.map((part, i) => {
			if (i % 2 === 1) return part;
			return part.replace(/#(\d+)/g, (match, numStr) => {
				const url = resolveIssueUrl(Number(numStr), issueRefs);
				return url ? `[${match}](${url})` : match;
			});
		})
		.join("");
}

function IssueLinkedText({
	content,
	issueRefs,
}: {
	content: string;
	issueRefs: IssueRef[];
}) {
	if (issueRefs.length === 0) return <>{content}</>;
	const parts = content.split(/(#\d+)/g);
	return (
		<>
			{parts.map((part, i) => {
				if (i % 2 === 1) {
					const num = Number(part.slice(1));
					const url = resolveIssueUrl(num, issueRefs);
					if (url) {
						return (
							<a
								key={i}
								href={url}
								target="_blank"
								rel="noreferrer"
								className="underline decoration-surface/60 hover:decoration-surface"
							>
								{part}
							</a>
						);
					}
				}
				return part;
			})}
		</>
	);
}

function formatJst(iso: string): string {
	try {
		return new Intl.DateTimeFormat("ja-JP", {
			timeZone: "Asia/Tokyo",
			month: "numeric",
			day: "numeric",
			hour: "2-digit",
			minute: "2-digit",
		}).format(new Date(iso));
	} catch {
		return iso;
	}
}

function MarkdownContent({
	content,
	issueRefs,
}: {
	content: string;
	issueRefs: IssueRef[];
}) {
	const processedContent = injectIssueLinks(content, issueRefs);
	return (
		<ReactMarkdown
			remarkPlugins={[remarkGfm]}
			rehypePlugins={[rehypeHighlight]}
			components={{
				h1: ({ children }) => (
					<h1 className="text-[15px] font-bold text-ink mt-3 mb-2 first:mt-0 leading-[1.4]">
						{children}
					</h1>
				),
				h2: ({ children }) => (
					<h2 className="text-[14px] font-bold text-ink mt-2.5 mb-1.5 first:mt-0 leading-[1.4]">
						{children}
					</h2>
				),
				h3: ({ children }) => (
					<h3 className="text-[13.5px] font-semibold text-ink mt-2 mb-1 first:mt-0 leading-[1.4]">
						{children}
					</h3>
				),
				p: ({ children }) => <p className="mb-2 last:mb-0">{children}</p>,
				ul: ({ children }) => (
					<ul className="list-disc pl-5 mb-2 last:mb-0 space-y-0.5">
						{children}
					</ul>
				),
				ol: ({ children }) => (
					<ol className="list-decimal pl-5 mb-2 last:mb-0 space-y-0.5">
						{children}
					</ol>
				),
				li: ({ children }) => <li className="leading-[1.7]">{children}</li>,
				a: ({ href, children }) => (
					<a
						href={href}
						target="_blank"
						rel="noreferrer"
						className="text-cognac underline decoration-cognac/50 hover:decoration-cognac"
					>
						{children}
					</a>
				),
				blockquote: ({ children }) => (
					<blockquote className="border-l-2 border-cognac/40 pl-3 italic text-ink-light my-2">
						{children}
					</blockquote>
				),
				table: ({ children }) => (
					<div className="overflow-x-auto max-w-full my-2">
						<table className="border-collapse text-[12.5px] min-w-0">
							{children}
						</table>
					</div>
				),
				th: ({ children }) => (
					<th className="border border-border px-2 py-1 bg-border-light text-left font-semibold whitespace-nowrap">
						{children}
					</th>
				),
				td: ({ children }) => (
					<td className="border border-border px-2 py-1 break-all">
						{children}
					</td>
				),
				pre: ({ children }) => (
					<pre
						className="bg-black/[0.06] rounded-md px-3 py-2.5 overflow-x-auto max-w-full mb-2 last:mb-0 text-[12px] leading-[1.6]"
						style={{ fontFamily: "var(--font-jetbrains)" }}
					>
						{children}
					</pre>
				),
				code: ({ className, children, ...props }) => {
					if (/language-/.test(className ?? "")) {
						return (
							<code className={className} {...props}>
								{children}
							</code>
						);
					}
					return (
						<code
							className="px-1.5 py-0.5 rounded text-[12px] bg-black/[0.07]"
							style={{ fontFamily: "var(--font-jetbrains)" }}
							{...props}
						>
							{children}
						</code>
					);
				},
			}}
		>
			{processedContent}
		</ReactMarkdown>
	);
}

export function ChatPanel({ isOpen, onClose, issueRefs }: Props) {
	const [threadId, setThreadId] = useState<string | null>(null);
	const [messages, setMessages] = useState<ChatMessage[]>([]);
	const [loadingThread, setLoadingThread] = useState(false);
	const [input, setInput] = useState("");
	const [sending, setSending] = useState(false);
	const [error, setError] = useState<string | null>(null);
	const pollingIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
	const messagesEndRef = useRef<HTMLDivElement>(null);
	const textareaRef = useRef<HTMLTextAreaElement>(null);

	useEffect(() => {
		if ("Notification" in window && Notification.permission === "default") {
			Notification.requestPermission();
		}
	}, []);

	useEffect(() => {
		if (!isOpen || issueRefs.length === 0) return;

		let cancelled = false;
		setMessages([]);
		setLoadingThread(true);
		setInput("");
		setError(null);
		api.chat
			.createThread(issueRefs)
			.then(async (thread) => {
				if (cancelled) return;
				setThreadId(thread.id);
				setMessages(thread.messages ?? []);
				setLoadingThread(false);
				await api.chat.markRead(thread.id).catch(console.error);
			})
			.catch((e: Error) => {
				if (cancelled) return;
				setError(e.message);
				setLoadingThread(false);
			});

		return () => {
			cancelled = true;
		};
	}, [isOpen, issueRefs]);

	useEffect(() => {
		if (isOpen) {
			setTimeout(() => textareaRef.current?.focus(), 100);
		} else {
			if (pollingIntervalRef.current) {
				clearInterval(pollingIntervalRef.current);
				pollingIntervalRef.current = null;
			}
			setSending(false);
		}
	}, [isOpen]);

	useEffect(() => {
		messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
	}, [messages, sending]);

	useEffect(() => {
		return () => {
			if (pollingIntervalRef.current) {
				clearInterval(pollingIntervalRef.current);
			}
		};
	}, []);

	async function sendMessage() {
		if (!threadId || !input.trim() || sending) return;
		const content = input.trim();
		setInput("");
		setError(null);
		setSending(true);

		setMessages((prev) => [
			...prev,
			{
				id: Date.now(),
				thread_id: threadId,
				role: "user",
				content,
				created_at: new Date().toISOString(),
			},
		]);

		try {
			const { message_id } = await api.chat.sendMessage(threadId, content);
			const capturedThreadId = threadId;

			const intervalId = setInterval(async () => {
				try {
					const { status, content: responseContent } =
						await api.chat.pollMessageStatus(capturedThreadId, message_id);

					if (status === "done") {
						clearInterval(intervalId);
						pollingIntervalRef.current = null;
						const assistantMessage = {
							id: message_id,
							thread_id: capturedThreadId,
							role: "assistant" as const,
							content: responseContent,
							created_at: new Date().toISOString(),
						};
						setMessages((prev) => [...prev, assistantMessage]);
						setSending(false);
						await api.chat.markRead(capturedThreadId).catch(console.error);
						if (
							document.hidden &&
							"Notification" in window &&
							Notification.permission === "granted"
						) {
							new Notification("Claudeから回答が届きました", {
								body: "dev-journal チャットを確認してください",
							});
						}
					} else if (status === "error") {
						clearInterval(intervalId);
						pollingIntervalRef.current = null;
						setError(responseContent || "エラーが発生しました");
						setSending(false);
					}
				} catch (e) {
					clearInterval(intervalId);
					pollingIntervalRef.current = null;
					setError(e instanceof Error ? e.message : "エラーが発生しました");
					setSending(false);
				}
			}, 400);

			pollingIntervalRef.current = intervalId;
		} catch (e) {
			setError(e instanceof Error ? e.message : "エラーが発生しました");
			setSending(false);
		}
	}

	function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
		if (
			e.key === "Enter" &&
			(e.metaKey || e.ctrlKey) &&
			!e.nativeEvent.isComposing
		) {
			e.preventDefault();
			sendMessage();
		}
	}

	return (
		<>
			{isOpen && (
				<button
					type="button"
					aria-label="チャットを閉じる"
					className="fixed inset-0 z-40 w-full cursor-default bg-black/40 md:hidden"
					onClick={onClose}
				/>
			)}

			<div
				className={`fixed inset-y-0 right-0 z-50 flex flex-col bg-surface border-l border-border shadow-xl transition-transform duration-200 ease-in-out
					w-[calc(100%-48px)] md:w-[420px]
					${isOpen ? "translate-x-0" : "translate-x-full"}`}
			>
				<div className="flex items-center justify-between border-b border-border px-4 py-3 shrink-0">
					<div className="flex flex-wrap items-center gap-1.5 flex-1 min-w-0 mr-2">
						{issueRefs.map((ref) => (
							<a
								key={`${ref.repo}#${ref.issue_number}`}
								href={`https://github.com/${ref.repo}/issues/${ref.issue_number}`}
								target="_blank"
								rel="noopener noreferrer"
								className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] bg-cognac-pale border border-cognac/30 text-cognac hover:bg-cognac/10 transition-colors"
								style={{ fontFamily: "var(--font-jetbrains)" }}
							>
								<span>{repoShort(ref.repo)}</span>
								<span className="text-cognac/60">#</span>
								<span>{ref.issue_number}</span>
							</a>
						))}
					</div>
					<div className="flex items-center gap-1">
						<button
							type="button"
							onClick={onClose}
							aria-label="閉じる"
							className="shrink-0 rounded p-1.5 text-ink-light hover:bg-surface-hover"
						>
							<svg
								className="h-4 w-4"
								fill="none"
								viewBox="0 0 24 24"
								stroke="currentColor"
								strokeWidth={2}
								aria-hidden="true"
							>
								<path
									strokeLinecap="round"
									strokeLinejoin="round"
									d="M6 18L18 6M6 6l12 12"
								/>
							</svg>
						</button>
					</div>
				</div>

				<div className="flex-1 overflow-y-auto px-4 py-4 space-y-4">
					{loadingThread && (
						<div className="flex h-full items-center justify-center">
							<p className="text-center text-[13px] text-ink-light italic">
								履歴を読み込み中…
							</p>
						</div>
					)}

					{messages.length === 0 && !sending && !error && !loadingThread && (
						<div className="flex h-full items-center justify-center">
							<p className="text-center text-[13px] text-ink-light italic">
								Issue について質問してください
							</p>
						</div>
					)}

					{messages.map((msg) => (
						<div
							key={msg.id}
							className={`group flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
						>
							<div className={`max-w-[88%] min-w-0 ${msg.role === "user" ? "items-end" : "items-start"} flex flex-col gap-1`}>
								<div className="px-1">
									<span
										className="text-[10px] text-ink-light"
										style={{ fontFamily: "var(--font-jetbrains)" }}
									>
										{formatJst(msg.created_at)}
									</span>
								</div>
								<div
									className={`rounded-lg px-3.5 py-2.5 text-[13.5px] leading-[1.7] break-words
										${
											msg.role === "user"
												? "bg-cognac text-surface whitespace-pre-wrap"
												: "bg-border-light text-ink border border-border"
										}`}
									style={{ fontFamily: "var(--font-source-serif)" }}
								>
									{msg.role === "assistant" ? (
										msg.status === "error" ? (
											<span className="italic text-ink-light">
												{msg.content || "(応答エラー)"}
											</span>
										) : (
											<MarkdownContent
												content={msg.content}
												issueRefs={issueRefs}
											/>
										)
									) : (
										<IssueLinkedText
											content={msg.content}
											issueRefs={issueRefs}
										/>
									)}
								</div>
							</div>
						</div>
					))}

					{sending && (
						<div className="flex justify-start">
							<div className="max-w-[85%] rounded-lg px-3.5 py-2.5 text-[13.5px] leading-[1.7] bg-border-light text-ink border border-border">
								<span className="text-ink-light italic">考え中…</span>
							</div>
						</div>
					)}

					{error && (
						<div className="rounded-lg border border-red-200 bg-red-50 px-3.5 py-2.5 text-[13px] text-red-700">
							{error}
						</div>
					)}

					<div ref={messagesEndRef} />
				</div>

				<div className="shrink-0 border-t border-border px-4 py-3">
					<div className="flex items-end gap-2">
						<textarea
							ref={textareaRef}
							value={input}
							onChange={(e) => setInput(e.target.value)}
							onKeyDown={handleKeyDown}
							disabled={sending || !threadId}
							placeholder="質問を入力… (⌘+Enter / Ctrl+Enter で送信)"
							rows={2}
							className="flex-1 resize-none rounded-lg border border-border bg-paper px-3 py-2 text-[13.5px] leading-[1.6] text-ink placeholder:text-ink-light/60 focus:border-cognac/50 focus:outline-none focus:ring-1 focus:ring-cognac/30 disabled:opacity-50"
							style={{ fontFamily: "var(--font-source-serif)" }}
						/>
						<button
							type="button"
							onClick={sendMessage}
							disabled={sending || !threadId || !input.trim()}
							className="shrink-0 rounded-lg bg-cognac px-3 py-2 text-[13px] font-semibold text-surface transition-opacity hover:opacity-90 disabled:opacity-40"
							style={{ fontFamily: "var(--font-fraunces)" }}
						>
							送信
						</button>
					</div>
					<p
						className="mt-1.5 text-[10px] text-ink-light/70"
						style={{ fontFamily: "var(--font-jetbrains)" }}
					>
						⌘+Enter / Ctrl+Enter で送信 · Enter で改行
					</p>
				</div>
			</div>
		</>
	);
}
