from dataclasses import asdict, dataclass, is_dataclass
from typing import Any

from agents import ItemHelpers
from openai.types.responses import ResponseTextDeltaEvent


@dataclass(slots=True)
class NormalizedRunEvent:
    """
    系统内部统一事件结构。

    类似 Java record：
    public record NormalizedRunEvent(...) {}
    """

    event_type: str
    data: dict[str, Any]
    event_name: str | None = None
    persist: bool = True


def normalize_stream_event(
    event: Any,
    run_id: str,
) -> NormalizedRunEvent | None:
    sdk_event_type = getattr(event, "type", None)

    if sdk_event_type == "raw_response_event":
        if isinstance(event.data, ResponseTextDeltaEvent):
            return NormalizedRunEvent(
                event_type="token.delta",
                data={
                    "run_id": run_id,
                    "delta": event.data.delta or "",
                },
                event_name="response.output_text.delta",
                persist=False,
            )

        return None

    if sdk_event_type == "agent_updated_stream_event":
        return NormalizedRunEvent(
            event_type="agent.updated",
            data={
                "run_id": run_id,
                "agent_name": event.new_agent.name,
            },
            event_name=sdk_event_type,
        )

    if sdk_event_type != "run_item_stream_event":
        return None

    item = event.item
    item_type = getattr(item, "type", "unknown")
    event_name = getattr(event, "name", None)

    if item_type == "tool_call_item":
        raw_item = to_jsonable(
            getattr(item, "raw_item", None)
        )

        return NormalizedRunEvent(
            event_type="tool.called",
            event_name=event_name,
            data={
                "run_id": run_id,
                "tool_name": extract_tool_name(raw_item),
                "arguments": extract_tool_arguments(raw_item),
                "raw_item": raw_item,
            },
        )

    if item_type == "tool_call_output_item":
        return NormalizedRunEvent(
            event_type="tool.output",
            event_name=event_name,
            data={
                "run_id": run_id,
                "output": to_jsonable(
                    getattr(item, "output", None)
                ),
                "raw_item": to_jsonable(
                    getattr(item, "raw_item", None)
                ),
            },
        )

    if item_type == "message_output_item":
        return NormalizedRunEvent(
            event_type="message.completed",
            event_name=event_name,
            data={
                "run_id": run_id,
                "content": ItemHelpers.text_message_output(item),
            },
        )

    return NormalizedRunEvent(
        event_type="run.item",
        event_name=event_name,
        data={
            "run_id": run_id,
            "item_type": item_type,
            "item": to_jsonable(item),
        },
    )


def to_jsonable(value: Any) -> Any:
    if value is None:
        return None

    if isinstance(value, (str, int, float, bool)):
        return value

    if isinstance(value, dict):
        return {
            str(key): to_jsonable(item)
            for key, item in value.items()
        }

    if isinstance(value, (list, tuple)):
        return [
            to_jsonable(item)
            for item in value
        ]

    model_dump = getattr(value, "model_dump", None)

    if callable(model_dump):
        return model_dump(mode="json")

    if is_dataclass(value):
        return asdict(value)

    return repr(value)


def extract_tool_name(raw_item: Any) -> str:
    if not isinstance(raw_item, dict):
        return "unknown_tool"

    direct_name = raw_item.get("name")

    if isinstance(direct_name, str):
        return direct_name

    function_data = raw_item.get("function")

    if isinstance(function_data, dict):
        function_name = function_data.get("name")

        if isinstance(function_name, str):
            return function_name

    return "unknown_tool"


def extract_tool_arguments(raw_item: Any) -> Any:
    if not isinstance(raw_item, dict):
        return None

    if "arguments" in raw_item:
        return raw_item["arguments"]

    function_data = raw_item.get("function")

    if isinstance(function_data, dict):
        return function_data.get("arguments")

    return None