import { SSEEvent } from "./types";

/**
 * SSE 流解析器
 * 将原始文本块解析为结构化的 SSE 事件
 */
export class SSEParser {
  private buffer: string = "";

  /**
   * 输入原始文本块，返回解析出的事件数组
   */
  parse(chunk: string): SSEEvent[] {
    this.buffer += chunk;
    const events: SSEEvent[] = [];
    const lines = this.buffer.split("\n");

    // 保留最后一个可能不完整的行
    this.buffer = lines.pop() || "";

    let currentEvent = "";
    let currentData = "";

    for (const line of lines) {
      if (line.startsWith("event:")) {
        currentEvent = line.slice(6).trim();
      } else if (line.startsWith("data:")) {
        currentData = line.slice(5).trim();
      } else if (line === "" && currentEvent && currentData) {
        // 空行表示事件结束
        try {
          const parsed = JSON.parse(currentData);
          const event: SSEEvent = { type: currentEvent, ...parsed };
          events.push(event);
        } catch {
          // 非 JSON data，构造简单事件
          if (currentEvent === "token") {
            events.push({
              type: "token",
              content: currentData,
              source: "main",
            });
          }
        }
        currentEvent = "";
        currentData = "";
      }
    }

    return events;
  }

  reset(): void {
    this.buffer = "";
  }
}
