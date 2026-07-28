"""
核心 SSE 流式对话 + 中断检测 + 中断恢复 + 展示消息持久化

关键设计：
- 双模式流: stream_mode=["messages", "values"], subgraphs=True
- 输出格式: (namespace, mode, data) 三元组
- 中断检测在 messages 处理之前（values 流优先）
- display_messages 实时累积（用户消息 + 助手回复 + 工具调用）
- SSE 事件协议: token / tool_start / tool_args / tool_result / tool_end / interrupt / done
"""
import json
import re
import uuid
from typing import AsyncGenerator
from datetime import datetime

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from langgraph.types import Command

from ..agent_loader import agent_loader
from ...agent.schema import ChatRequest, ResumeRequest
from ...agent.log_utils import web_logger

router = APIRouter(prefix="/api/chat", tags=["chat"])


def sse_event(event: str, data: dict) -> str:
    """格式化 SSE 事件（严格遵循 event:/data: 协议）"""
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


async def stream_chat_response(
    message: str,
    thread_id: str,
    user_id: str = "default_user",
    resume_data: dict = None,
) -> AsyncGenerator[str, None]:
    """
    核心流式响应生成器

    双流模式（subgraphs=True 时输出为 3-tuple）：
    - (namespace, "values", data): 检测中断（interrupts 字段）
    - (namespace, "messages", data): 逐 token 输出 + 工具调用事件

    消息累积：
    - 实时将 assistant 回复追加到 display_messages
    - 流结束后持久化到 MongoDB
    """
    config = agent_loader.create_config(thread_id)

    # 加载已有消息（恢复场景）或初始化
    if resume_data:
        display_messages = await agent_loader.get_display_messages(thread_id)
        current_input = Command(resume=resume_data)
    else:
        display_messages = await agent_loader.get_display_messages(thread_id)
        display_messages.append({
            "id": str(uuid.uuid4()),
            "role": "user",
            "content": message,
            "timestamp": datetime.now().isoformat(),
        })
        current_input = {"messages": [{"role": "user", "content": message}]}

    # 当前助手消息累积缓冲
    assistant_content = ""
    tool_calls_buffer = []
    thinking_emitted = False
    planning_emitted = False  # 是否已发射过规划事件
    phase = "thinking"  # 当前阶段: thinking → planning → executing → reviewing → done

    try:
        # 发射“深度思考”事件（前端展示思考动画）
        yield sse_event("thinking", {"status": "start"})

        async for namespace, chunk_type, chunk in agent_loader.agent.astream(
            input=current_input,
            config=config,
            stream_mode=["messages", "values"],
            subgraphs=True,
        ):
            # ===== 中断检测（必须在 messages 处理之前）=====
            if chunk_type == "values":
                if isinstance(chunk, dict) and chunk.get("interrupts"):
                    for interrupt_item in chunk["interrupts"]:
                        interrupt_value = (
                            interrupt_item.value
                            if hasattr(interrupt_item, "value")
                            else interrupt_item
                        )
                        if isinstance(interrupt_value, dict):
                            # 判断中断类型
                            if interrupt_value.get("type") == "order_info_request":
                                yield sse_event("interrupt", {
                                    "interrupt_type": "order_info_supplement",
                                    "missing_fields": interrupt_value.get("missing_fields", []),
                                    "message": interrupt_value.get("message", ""),
                                    "extracted_data": interrupt_value.get("current_data", {}),
                                })
                            elif "action_requests" in interrupt_value:
                                yield sse_event("interrupt", {
                                    "interrupt_type": "hitl_approval",
                                    "tool_name": interrupt_value.get("tool_name", ""),
                                    "tool_args": interrupt_value.get("action_requests", {}),
                                    "order_data": interrupt_value.get("action_requests", {}),
                                })
                            else:
                                # 通用中断（interrupt_on 触发的审批）
                                yield sse_event("interrupt", {
                                    "interrupt_type": "hitl_approval",
                                    "tool_name": interrupt_value.get("tool_name", ""),
                                    "tool_args": interrupt_value.get("tool_args", interrupt_value),
                                    "order_data": interrupt_value.get("tool_args", interrupt_value),
                                })

                    # 保存当前累积的消息
                    if assistant_content:
                        display_messages.append({
                            "id": str(uuid.uuid4()),
                            "role": "assistant",
                            "content": assistant_content,
                            "toolCalls": tool_calls_buffer,
                            "timestamp": datetime.now().isoformat(),
                        })
                    await agent_loader.save_display_messages(thread_id, display_messages)
                    yield sse_event("done", {"thread_id": thread_id, "interrupted": True})
                    return
                continue

            # ===== Messages 流处理 =====
            if chunk_type == "messages":
                # chunk 格式: (message_chunk, metadata_dict)
                if isinstance(chunk, (list, tuple)) and len(chunk) >= 1:
                    token = chunk[0]
                else:
                    token = chunk

                if token is None:
                    continue

                token_type = getattr(token, "type", "")
                content = getattr(token, "content", "")
                tool_call_chunks = getattr(token, "tool_call_chunks", None)

                # AIMessage with tool_call_chunks → tool_start / tool_args
                if tool_call_chunks:
                    # 首次收到工具调用时结束 thinking 状态
                    if not thinking_emitted:
                        yield sse_event("thinking", {"status": "end"})
                        thinking_emitted = True
                    # 进入执行阶段
                    if phase in ("thinking", "planning"):
                        phase = "executing"
                        yield sse_event("phase", {"phase": "executing", "label": "⚙️ 执行中"})
                        # 更新 todo 状态为 executing
                        if planning_emitted:
                            yield sse_event("todo_update", {"phase": "executing", "status_change": "executing"})
                    for tc in tool_call_chunks:
                        if isinstance(tc, dict):
                            if tc.get("name"):
                                tool_calls_buffer.append({
                                    "id": tc.get("id", str(uuid.uuid4())),
                                    "name": tc["name"],
                                    "args": "",
                                    "status": "running",
                                })
                                yield sse_event("tool_start", {
                                    "name": tc["name"],
                                    "id": tc.get("id", ""),
                                })
                            if tc.get("args"):
                                # 追加到最近的 tool_call
                                if tool_calls_buffer:
                                    tool_calls_buffer[-1]["args"] += tc["args"]
                                yield sse_event("tool_args", {"args": tc["args"]})
                    continue

                # ToolMessage → tool_result / tool_end
                if token_type == "tool":
                    tool_name = getattr(token, "name", "unknown")
                    tool_content = content if isinstance(content, str) else str(content)
                    # 更新 buffer 中对应工具的状态
                    for tc in tool_calls_buffer:
                        if tc["name"] == tool_name and tc["status"] == "running":
                            tc["result"] = tool_content[:1000]
                            tc["status"] = "done"
                            break

                    # 检测 TODO 工具调用，发射任务列表更新事件
                    if "todo" in tool_name.lower() or "task" in tool_name.lower():
                        try:
                            # 尝试从工具参数中提取 todo 列表
                            todo_args = None
                            for tc in tool_calls_buffer:
                                if tc["name"] == tool_name and tc.get("args"):
                                    todo_args = tc["args"]
                                    break
                            if todo_args:
                                yield sse_event("todo_update", {
                                    "tool": tool_name,
                                    "args": todo_args[:2000],
                                    "result": tool_content[:500],
                                })
                        except Exception:
                            pass

                    yield sse_event("tool_result", {
                        "name": tool_name,
                        "content": tool_content[:2000],
                    })
                    yield sse_event("tool_end", {
                        "id": getattr(token, "tool_call_id", ""),
                    })
                    continue

                # AIMessage 纯文本 → token 事件
                if content and isinstance(content, str) and content.strip():
                    # 首次收到 token 时结束 thinking
                    if not thinking_emitted:
                        yield sse_event("thinking", {"status": "end"})
                        thinking_emitted = True
                    assistant_content += content

                    # === Harness 阶段检测 ===
                    # 检测 Planning 阶段（必须有明确的规划标题头 + 编号步骤）
                    if not planning_emitted and len(assistant_content) > 80:
                        # 严格匹配：必须含“任务规划”“执行计划”“Planning”等明确标题
                        has_plan_header = bool(re.search(r'(任务规划|执行计划|操作步骤|Planning|Plan)', assistant_content))
                        if has_plan_header:
                            # 提取编号列表项（排除纯能力描述）
                            plan_items = re.findall(r'[\d]+[.、)\]]\s*(?:\[[ x]?\]\s*)?(.+?)(?:\n|$)', assistant_content)
                            # 过滤太短的项（可能是列表装饰）
                            plan_items = [item for item in plan_items if len(item.strip()) > 4]
                            if len(plan_items) >= 2:
                                planning_emitted = True
                                phase = "planning"
                                todos = [{"id": f"plan-{i}", "content": item.strip(), "status": "pending"} for i, item in enumerate(plan_items)]
                                yield sse_event("todo_update", {
                                    "phase": "planning",
                                    "todos": todos,
                                })
                                yield sse_event("phase", {"phase": "planning", "label": "📝 规划中"})

                    # 检测 Review 阶段
                    if phase == "executing" and any(marker in content for marker in ["Review", "审查", "🔍", "验证结果", "总结"]):
                        phase = "reviewing"
                        yield sse_event("phase", {"phase": "reviewing", "label": "🔍 审查中"})

                    # 判断来源（通过 namespace 元组）
                    source = "main"
                    if namespace:
                        ns_str = str(namespace)
                        if "analyst" in ns_str:
                            source = "analyst"
                        elif "order" in ns_str:
                            source = "order"
                    yield sse_event("token", {"content": content, "source": source})

        # ===== 流正常结束 =====
        if assistant_content:
            display_messages.append({
                "id": str(uuid.uuid4()),
                "role": "assistant",
                "content": assistant_content,
                "toolCalls": tool_calls_buffer if tool_calls_buffer else None,
                "timestamp": datetime.now().isoformat(),
            })

        await agent_loader.save_display_messages(thread_id, display_messages)

        # 自动生成会话标题（首条消息前20字）
        if message:
            title = message[:20] + "..." if len(message) > 20 else message
            await agent_loader.save_conversation(thread_id, user_id, title)

        yield sse_event("done", {"thread_id": thread_id, "interrupted": False})

    except Exception as e:
        web_logger.error(f"Stream error for thread {thread_id}: {e}", exc_info=True)
        yield sse_event("error", {"message": f"服务内部错误: {str(e)[:200]}"})
        yield sse_event("done", {"thread_id": thread_id, "interrupted": False})


@router.post("/stream")
async def chat_stream(request: ChatRequest):
    """SSE 流式对话端点"""
    await agent_loader.initialize()

    thread_id = request.thread_id or agent_loader.generate_thread_id()

    return StreamingResponse(
        stream_chat_response(
            message=request.message,
            thread_id=thread_id,
            user_id=request.user_id,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Thread-Id": thread_id,
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/{thread_id}/resume")
async def chat_resume(thread_id: str, request: ResumeRequest):
    """中断恢复端点"""
    await agent_loader.initialize()

    return StreamingResponse(
        stream_chat_response(
            message="",
            thread_id=thread_id,
            resume_data=request.resume,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Thread-Id": thread_id,
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/{thread_id}/state")
async def chat_state(thread_id: str):
    """获取 Agent 状态（是否处于中断中）"""
    await agent_loader.initialize()
    config = agent_loader.create_config(thread_id)
    try:
        state = await agent_loader.agent.aget_state(config)
        is_interrupted = bool(state.next) if state else False
        return {"thread_id": thread_id, "interrupted": is_interrupted}
    except Exception:
        return {"thread_id": thread_id, "interrupted": False}


@router.get("/{thread_id}/history")
async def chat_history(thread_id: str):
    """获取对话消息历史"""
    messages = await agent_loader.get_display_messages(thread_id)
    return {"thread_id": thread_id, "messages": messages}
