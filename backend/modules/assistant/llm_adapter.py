"""VNGCloud MaaS LLM adapter for Google ADK.

Implements BaseLlm.generate_content_async by translating between
ADK's google.genai.types.Content format and OpenAI-compatible API.
"""
import json
import logging
from collections.abc import AsyncGenerator
from typing import Any

import google.genai.types as genai_types
from google.adk.models.base_llm import BaseLlm
from google.adk.models.llm_request import LlmRequest
from google.adk.models.llm_response import LlmResponse
from openai import AsyncOpenAI

from app.config import settings

logger = logging.getLogger(__name__)

# Map OpenAI finish_reason → genai FinishReason
_FINISH_REASON_MAP = {
    "stop": genai_types.FinishReason.STOP,
    "length": genai_types.FinishReason.MAX_TOKENS,
    "tool_calls": genai_types.FinishReason.STOP,
    "content_filter": genai_types.FinishReason.SAFETY,
}


class VngCloudLlm(BaseLlm):
    """ADK LLM adapter for VNGCloud MaaS (OpenAI-compatible API)."""

    def __init__(self, model: str | None = None, api_key: str | None = None, base_url: str | None = None):
        model_name = model or settings.LLM_MODEL
        super().__init__(model=model_name)
        self._api_key = api_key or settings.LLM_API_KEY
        self._base_url = base_url or settings.LLM_BASE_URL
        self._client: AsyncOpenAI | None = None

    def _get_client(self) -> AsyncOpenAI:
        if self._client is None:
            self._client = AsyncOpenAI(api_key=self._api_key, base_url=self._base_url)
        return self._client

    async def generate_content_async(
        self, llm_request: LlmRequest, stream: bool = False
    ) -> AsyncGenerator[LlmResponse, None]:
        messages = _adk_contents_to_openai(llm_request)
        tools = _adk_tools_to_openai(llm_request)
        config = llm_request.config or genai_types.GenerateContentConfig()

        try:
            if stream:
                async for response in self._generate_stream(messages, tools, config):
                    yield response
            else:
                response = await self._generate(messages, tools, config)
                yield response
        except Exception as e:
            logger.error(f"LLM call failed: {e}")
            yield LlmResponse(
                error_code="LLM_ERROR",
                error_message=str(e),
            )

    async def _generate(
        self, messages: list[dict], tools: list[dict] | None, config: genai_types.GenerateContentConfig
    ) -> LlmResponse:
        kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": config.temperature if config.temperature is not None else 0.7,
            "max_tokens": config.max_output_tokens if config.max_output_tokens else 2000,
        }
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"

        completion = await self._get_client().chat.completions.create(**kwargs)
        return _openai_response_to_adk(completion)

    async def _generate_stream(
        self, messages: list[dict], tools: list[dict] | None, config: genai_types.GenerateContentConfig
    ) -> AsyncGenerator[LlmResponse, None]:
        kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": config.temperature if config.temperature is not None else 0.7,
            "max_tokens": config.max_output_tokens if config.max_output_tokens else 2000,
            "stream": True,
        }
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"

        stream = await self._get_client().chat.completions.create(**kwargs)

        accumulated_content = ""
        tool_calls_acc: dict[int, dict] = {}
        finish_reason = None

        async for chunk in stream:
            delta = chunk.choices[0].delta if chunk.choices else None
            if delta is None:
                continue

            if delta.content:
                accumulated_content += delta.content

            # Accumulate tool calls across chunks
            if delta.tool_calls:
                for tc in delta.tool_calls:
                    idx = tc.index
                    if idx not in tool_calls_acc:
                        tool_calls_acc[idx] = {"id": tc.id or "", "type": "function", "function": {"name": "", "arguments": ""}}
                    if tc.id:
                        tool_calls_acc[idx]["id"] = tc.id
                    if tc.function:
                        if tc.function.name:
                            tool_calls_acc[idx]["function"]["name"] += tc.function.name
                        if tc.function.arguments:
                            tool_calls_acc[idx]["function"]["arguments"] += tc.function.arguments

            finish_reason = chunk.choices[0].finish_reason
            if finish_reason:
                break

        # Build ADK Content from accumulated response
        parts: list[genai_types.Part] = []
        if accumulated_content:
            parts.append(genai_types.Part(text=accumulated_content))

        # Add tool calls as function_call parts
        for tc in sorted(tool_calls_acc.values(), key=lambda x: x.get("index", 0)):
            try:
                args = json.loads(tc["function"]["arguments"]) if tc["function"]["arguments"] else {}
            except json.JSONDecodeError:
                args = {}
            parts.append(
                genai_types.Part(
                    function_call=genai_types.FunctionCall(
                        name=tc["function"]["name"],
                        args=args,
                    )
                )
            )

        content = genai_types.Content(role="model", parts=parts) if parts else None
        return LlmResponse(
            content=content,
            finish_reason=_FINISH_REASON_MAP.get(finish_reason or "", None),
            partial=False,
            turn_complete=True,
        )


def _adk_contents_to_openai(llm_request: LlmRequest) -> list[dict]:
    """Convert ADK contents list to OpenAI messages format."""
    messages: list[dict] = []

    # Extract system instruction from config
    config = llm_request.config
    if config and config.system_instruction:
        parts = config.system_instruction.parts if hasattr(config.system_instruction, "parts") else []
        text = " ".join(p.text for p in parts if hasattr(p, "text") and p.text)
        if text:
            messages.append({"role": "system", "content": text})

    # Convert conversation contents
    for content in llm_request.contents or []:
        if content.role == "user":
            text = _extract_text(content)
            if text:
                messages.append({"role": "user", "content": text})
        elif content.role == "model":
            parts_list = []
            tool_calls = []
            for part in content.parts or []:
                if hasattr(part, "text") and part.text:
                    parts_list.append({"type": "text", "text": part.text})
                if hasattr(part, "function_call") and part.function_call:
                    fc = part.function_call
                    try:
                        args_str = json.dumps(fc.args) if isinstance(fc.args, dict) else str(fc.args)
                    except Exception:
                        args_str = "{}"
                    tool_calls.append({
                        "id": getattr(fc, "id", f"call_{len(tool_calls)}"),
                        "type": "function",
                        "function": {"name": fc.name, "arguments": args_str},
                    })
            if parts_list or tool_calls:
                msg: dict = {"role": "assistant", "content": None}
                if parts_list:
                    msg["content"] = " ".join(p.get("text", "") for p in parts_list)
                if tool_calls:
                    msg["tool_calls"] = tool_calls
                messages.append(msg)
        elif content.role == "tool":
            for part in content.parts or []:
                if hasattr(part, "function_response") and part.function_response:
                    fr = part.function_response
                    result = fr.response
                    if isinstance(result, dict):
                        result = json.dumps(result, ensure_ascii=False)
                    messages.append({
                        "role": "tool",
                        "tool_call_id": getattr(fr, "id", fr.name),
                        "content": result,
                    })

    return messages


def _adk_tools_to_openai(llm_request: LlmRequest) -> list[dict] | None:
    """Convert ADK tools to OpenAI function definitions."""
    if not llm_request.tools_dict:
        return None

    openai_tools = []
    for tool_name, tool in llm_request.tools_dict.items():
        # Extract function schema from ADK tool
        func_decl = _get_tool_function_declaration(tool)
        if func_decl:
            openai_tools.append({"type": "function", "function": func_decl})
    return openai_tools if openai_tools else None


def _get_tool_function_declaration(tool: Any) -> dict | None:
    """Extract OpenAI function declaration from an ADK BaseTool or FunctionTool."""
    name = getattr(tool, "name", None)
    description = getattr(tool, "description", None)

    if name is None:
        return None

    # Try to get schema from tool
    parameters = {"type": "object", "properties": {}, "required": []}

    if hasattr(tool, "_function") and hasattr(tool._function, "__annotations__"):
        annotations = tool._function.__annotations__
        import inspect
        sig = inspect.signature(tool._function)
        for param_name, param in sig.parameters.items():
            if param_name in ("return", "tool_context", "ctx"):
                continue
            param_type = annotations.get(param_name, "string")
            json_type = _python_type_to_json(param_type)
            parameters["properties"][param_name] = json_type
            if param.default is inspect.Parameter.empty:
                parameters["required"].append(param_name)

    if not parameters["required"]:
        del parameters["required"]

    return {
        "name": name,
        "description": description or "",
        "parameters": parameters,
    }


def _python_type_to_json(py_type: Any) -> dict:
    """Map Python type hints to JSON Schema types."""
    origin = getattr(py_type, "__origin__", None)
    if origin is None:
        type_name = getattr(py_type, "__name__", str(py_type))
    else:
        type_name = origin.__name__

    type_map = {
        "str": {"type": "string"},
        "int": {"type": "integer"},
        "float": {"type": "number"},
        "bool": {"type": "boolean"},
        "list": {"type": "array", "items": {"type": "string"}},
        "dict": {"type": "object"},
    }
    return type_map.get(type_name, {"type": "string"})


def _openai_response_to_adk(completion: Any) -> LlmResponse:
    """Convert OpenAI chat completion to ADK LlmResponse."""
    choice = completion.choices[0]
    message = choice.message

    parts: list[genai_types.Part] = []

    if message.content:
        parts.append(genai_types.Part(text=message.content))

    if message.tool_calls:
        for tc in message.tool_calls:
            try:
                args = json.loads(tc.function.arguments) if tc.function.arguments else {}
            except json.JSONDecodeError:
                args = {}
            parts.append(
                genai_types.Part(
                    function_call=genai_types.FunctionCall(
                        id=tc.id,
                        name=tc.function.name,
                        args=args,
                    )
                )
            )

    finish_reason = _FINISH_REASON_MAP.get(choice.finish_reason or "", None)

    usage = None
    if completion.usage:
        usage = genai_types.GenerateContentResponseUsageMetadata(
            prompt_token_count=completion.usage.prompt_tokens,
            candidates_token_count=completion.usage.completion_tokens,
            total_token_count=completion.usage.total_tokens,
        )

    return LlmResponse(
        content=genai_types.Content(role="model", parts=parts) if parts else None,
        finish_reason=finish_reason,
        usage_metadata=usage,
        partial=False,
        turn_complete=True,
    )


def _extract_text(content: Any) -> str:
    """Extract text from a genai Content object."""
    parts = getattr(content, "parts", []) or []
    texts = []
    for p in parts:
        if hasattr(p, "text") and p.text:
            texts.append(p.text)
    return " ".join(texts)
