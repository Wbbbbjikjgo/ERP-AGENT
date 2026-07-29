"use client";

import { useState, useCallback, useRef } from "react";
import { v4 as uuidv4 } from "uuid";
import { ChatMessage, ToolCallInfo, SSEEvent, InterruptData, TodoItem } from "@/lib/types";
import { streamChat, resumeChat } from "@/lib/api";
import { useSSE } from "./useSSE";

const USER_ID = "user-001";
const USERNAME = "采购管理员";

export type HarnessPhase = "idle" | "thinking" | "planning" | "executing" | "reviewing" | "done";

export function useChat() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [streaming, setStreaming] = useState(false);
  const [thinking, setThinking] = useState(false);
  const [interrupted, setInterrupted] = useState(false);
  const [interruptData, setInterruptData] = useState<InterruptData | null>(null);
  const [threadId, setThreadId] = useState<string>(uuidv4());
  const [error, setError] = useState<string | null>(null);
  const [todoItems, setTodoItems] = useState<TodoItem[]>([]);
  const [todoVisible, setTodoVisible] = useState(false);
  const [phase, setPhase] = useState<HarnessPhase>("idle");
  const [phaseLabel, setPhaseLabel] = useState("");
  const [pendingQueue, setPendingQueue] = useState<string[]>([]);

  const assistantMsgRef = useRef<string>("");
  const toolCallsRef = useRef<ToolCallInfo[]>([]);
  const currentToolIdRef = useRef<string>("");
  const pendingQueueRef = useRef<string[]>([]);

  const resetAssistantState = useCallback(() => {
    assistantMsgRef.current = "";
    toolCallsRef.current = [];
    currentToolIdRef.current = "";
  }, []);

  const updateAssistantMessage = useCallback(() => {
    setMessages((prev) => {
      const lastMsg = prev[prev.length - 1];
      const updated: ChatMessage = {
        id: lastMsg?.role === "assistant" ? lastMsg.id : uuidv4(),
        role: "assistant",
        content: assistantMsgRef.current,
        toolCalls: [...toolCallsRef.current],
        timestamp: Date.now(),
      };
      if (lastMsg?.role === "assistant") {
        return [...prev.slice(0, -1), updated];
      }
      return [...prev, updated];
    });
  }, []);

  const handleEvent = useCallback(
    (event: SSEEvent) => {
      switch (event.type) {
        case "token":
          assistantMsgRef.current += event.content;
          updateAssistantMessage();
          break;

        case "tool_start": {
          const tc: ToolCallInfo = {
            id: event.id,
            name: event.name,
            args: "",
            status: "running",
          };
          toolCallsRef.current = [...toolCallsRef.current, tc];
          currentToolIdRef.current = event.id;
          updateAssistantMessage();
          break;
        }

        case "tool_args": {
          toolCallsRef.current = toolCallsRef.current.map((tc) =>
            tc.id === currentToolIdRef.current
              ? { ...tc, args: tc.args + event.args }
              : tc
          );
          updateAssistantMessage();
          break;
        }

        case "tool_result": {
          toolCallsRef.current = toolCallsRef.current.map((tc) =>
            tc.name === event.name && tc.status === "running"
              ? { ...tc, result: event.content, status: "done" as const }
              : tc
          );
          updateAssistantMessage();
          break;
        }

        case "tool_end": {
          toolCallsRef.current = toolCallsRef.current.map((tc) =>
            tc.id === event.id ? { ...tc, status: "done" as const } : tc
          );
          updateAssistantMessage();
          break;
        }

        case "interrupt":
          setInterrupted(true);
          setInterruptData(event.data);
          break;

        case "thinking":
          if (event.status === "start") {
            setThinking(true);
            setPhase("thinking");
            setPhaseLabel("💭 深度思考中");
          } else {
            // 延迟结束 thinking，保证动画至少显示 800ms
            setTimeout(() => setThinking(false), 800);
          }
          break;

        case "phase":
          setPhase(event.phase as HarnessPhase);
          setPhaseLabel(event.label);
          break;

        case "todo_update": {
          // 新格式：后端直接发送 todos 数组
          if (event.todos && Array.isArray(event.todos)) {
            const items: TodoItem[] = event.todos.map((t) => ({
              id: t.id || `todo-${Math.random().toString(36).slice(2)}`,
              content: t.content || "",
              status: (t.status as TodoItem["status"]) || "pending",
            }));
            setTodoItems(items);
            setTodoVisible(true);
          } else if (event.status_change === "executing") {
            // 执行阶段：将所有 pending 改为 in_progress
            setTodoItems((prev) =>
              prev.map((item) =>
                item.status === "pending" ? { ...item, status: "in_progress" as const } : item
              )
            );
          } else if (event.args) {
            // 兼容旧格式
            try {
              const args = JSON.parse(event.args);
              if (args.todos && Array.isArray(args.todos)) {
                const items: TodoItem[] = args.todos.map((t: Record<string, unknown>, i: number) => ({
                  id: (t.id as string) || `todo-${i}`,
                  content: (t.content as string) || "",
                  status: (t.status as TodoItem["status"]) || "pending",
                }));
                setTodoItems(items);
                setTodoVisible(true);
              }
            } catch {
              // 解析失败静默处理
            }
          }
          break;
        }

        case "done":
          setStreaming(false);
          setPhase("done");
          setPhaseLabel("✅ 完成");
          setTodoItems((prev) =>
            prev.map((item) =>
              item.status !== "cancelled" ? { ...item, status: "complete" as const } : item
            )
          );
          if (event.interrupted) {
            setInterrupted(true);
          }
          // 检查排队队列，有消息自动发出
          const q = pendingQueueRef.current;
          if (q.length > 0) {
            const next = q.shift()!;
            setPendingQueue([...q]);
            // 延迟一帧发送，确保 streaming 状态已更新
            setTimeout(() => doSend(next), 50);
          }
          break;
      }
    },
    [updateAssistantMessage]
  );

  const { start, abort } = useSSE({
    onEvent: handleEvent,
    onError: (err) => {
      setError(err.message);
      setStreaming(false);
    },
    onComplete: () => {
      setStreaming(false);
    },
  });

  // 实际的发送逻辑（非排队）
  const doSend = useCallback(
    (content: string) => {
      setError(null);
      setInterrupted(false);
      setInterruptData(null);
      setThinking(false);
      setTodoItems([]);
      setTodoVisible(false);
      setPhase("idle");
      setPhaseLabel("");
      resetAssistantState();

      const userMsg: ChatMessage = {
        id: uuidv4(),
        role: "user",
        content: content.trim(),
        timestamp: Date.now(),
      };
      setMessages((prev) => [...prev, userMsg]);
      setStreaming(true);

      start((onChunk, signal) =>
        streamChat(
          {
            message: content.trim(),
            thread_id: threadId,
            user_id: USER_ID,
            username: USERNAME,
          },
          onChunk,
          signal
        )
      );
    },
    [threadId, start, resetAssistantState]
  );

  const sendMessage = useCallback(
    (content: string) => {
      if (!content.trim()) return;

      if (streaming) {
        // 正在回答：加入排队队列，回答完后自动发送
        const q = [...pendingQueueRef.current, content.trim()];
        pendingQueueRef.current = q;
        setPendingQueue(q);
        return;
      }

      doSend(content.trim());
    },
    [streaming, doSend]
  );

  const resumeWith = useCallback(
    (resumeData: Record<string, unknown>) => {
      setInterrupted(false);
      setInterruptData(null);
      setStreaming(true);
      resetAssistantState();

      start((onChunk, signal) =>
        resumeChat(
          { thread_id: threadId, resume_data: resumeData },
          onChunk,
          signal
        )
      );
    },
    [threadId, start, resetAssistantState]
  );

  const newChat = useCallback(() => {
    abort();
    setMessages([]);
    setStreaming(false);
    setInterrupted(false);
    setInterruptData(null);
    setError(null);
    setThreadId(uuidv4());
    setPendingQueue([]);
    pendingQueueRef.current = [];
    resetAssistantState();
  }, [abort, resetAssistantState]);

  const loadThread = useCallback(
    (id: string, msgs: ChatMessage[]) => {
      abort();
      setThreadId(id);
      setMessages(msgs);
      setStreaming(false);
      setInterrupted(false);
      setInterruptData(null);
      setError(null);
      resetAssistantState();
    },
    [abort, resetAssistantState]
  );

  return {
    messages,
    streaming,
    thinking,
    interrupted,
    interruptData,
    threadId,
    error,
    todoItems,
    todoVisible,
    pendingQueue,
    phase,
    phaseLabel,
    sendMessage,
    resumeWith,
    newChat,
    loadThread,
    abort,
  };
}
