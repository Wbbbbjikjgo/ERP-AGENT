"use client";

import { useRef, useCallback } from "react";
import { SSEParser } from "@/lib/sse-parser";
import { SSEEvent } from "@/lib/types";

interface UseSSEOptions {
  onEvent: (event: SSEEvent) => void;
  onError?: (error: Error) => void;
  onComplete?: () => void;
}

export function useSSE({ onEvent, onError, onComplete }: UseSSEOptions) {
  const parserRef = useRef(new SSEParser());
  const abortRef = useRef<AbortController | null>(null);

  const handleChunk = useCallback(
    (chunk: string) => {
      const events = parserRef.current.parse(chunk);
      for (const event of events) {
        onEvent(event);
      }
    },
    [onEvent]
  );

  const start = useCallback(
    async (fetchFn: (onChunk: (c: string) => void, signal: AbortSignal) => Promise<void>) => {
      // 取消之前的请求
      abortRef.current?.abort();
      const controller = new AbortController();
      abortRef.current = controller;
      parserRef.current.reset();

      try {
        await fetchFn(handleChunk, controller.signal);
        onComplete?.();
      } catch (err: unknown) {
        if (err instanceof Error && err.name === "AbortError") {
          return; // 用户主动取消
        }
        onError?.(err instanceof Error ? err : new Error(String(err)));
      }
    },
    [handleChunk, onError, onComplete]
  );

  const abort = useCallback(() => {
    abortRef.current?.abort();
    abortRef.current = null;
  }, []);

  return { start, abort };
}
