import os
import json
import logging
import httpx
from typing import Dict, Any, Optional

logger = logging.getLogger("healthai.ai_service")

# Candidate endpoints in order of priority (llama-server preferred for RTX 5090, Ollama as fallback)
def get_auth_headers() -> Dict[str, str]:
    """Returns headers for OpenAI-compatible HTTP requests including Authorization if OPENAI_API_KEY is configured."""
    headers = {
        "Content-Type": "application/json",
        "HTTP-Referer": "http://localhost:8000",
        "X-Title": "HealthAI Pharmacology Copilot",
    }
    api_key = os.getenv("OPENAI_API_KEY")
    if api_key:
        headers["Authorization"] = f"Bearer {api_key.strip()}"
    return headers


def get_reasoning_params(base_url: str = "") -> Dict[str, Any]:
    """
    Constructs provider-compliant reasoning parameters for OpenRouter, Groq, OpenAI,
    and local OpenAI-compatible backends (vLLM, llama-server).
    Properly adheres to OpenRouter's mutually exclusive reasoning.effort vs reasoning.max_tokens schema.
    """
    raw_effort = os.getenv("REASONING_EFFORT")
    has_explicit_effort = raw_effort is not None and bool(raw_effort.strip())
    if raw_effort and "#" in raw_effort:
        raw_effort = raw_effort.split("#")[0]
    effort = (raw_effort or "medium").strip().strip("'\"").lower()

    valid_efforts = {"max", "xhigh", "high", "medium", "low", "minimal", "none"}
    if effort not in valid_efforts:
        effort = "medium"

    raw_max = os.getenv("REASONING_MAX_TOKENS")
    has_explicit_max = raw_max is not None and bool(raw_max.strip())
    if raw_max and "#" in raw_max:
        raw_max = raw_max.split("#")[0]
    raw_max = (raw_max or "512").strip().strip("'\"")
    try:
        max_tokens = int(raw_max)
    except (ValueError, TypeError):
        max_tokens = 512

    active_base = (base_url or os.getenv("OPENAI_BASE_URL", "")).lower()
    is_openrouter = "openrouter.ai" in active_base

    if is_openrouter:
        # OpenRouter strictly enforces EITHER reasoning.effort OR reasoning.max_tokens (never both simultaneously)
        if has_explicit_max and not has_explicit_effort:
            return {
                "reasoning": {
                    "max_tokens": max_tokens
                }
            }
        reasoning_obj: Dict[str, Any] = {"effort": effort}
        if effort == "none":
            reasoning_obj["exclude"] = True
        return {
            "reasoning": reasoning_obj
        }

    # For OpenAI / Groq / other cloud providers
    if os.getenv("OPENAI_BASE_URL"):
        if effort in ("high", "medium", "low"):
            return {"reasoning_effort": effort}
        return {}

    # For local llama-server / vLLM (Unsloth Dynamic Qwen3.8 Jinja template)
    enable_thinking = effort != "none"
    return {
        "reasoning_effort": effort,
        "chat_template_kwargs": {
            "reasoning_effort": effort,
            "enable_thinking": enable_thinking,
        },
    }


def get_candidate_urls() -> list[str]:
    """Returns the ordered list of candidate base URLs to probe."""
    env_base = os.getenv("OPENAI_BASE_URL")
    candidates = [
        env_base,
        "http://127.0.0.1:8080/v1",   # llama-server (recommended for local RTX 5090)
        "http://127.0.0.1:11434/v1",  # Ollama OpenAI compatibility layer
    ]
    return [u.rstrip("/") for u in candidates if u]


DEFAULT_MODEL = os.getenv("OPENAI_MODEL", "Qwen3.8-27B-UD-Q6_K_M.gguf")

# Priority list for automatic model resolution if configured model is not installed
MODEL_PREFERENCES = [
    "qwen3.8:27b",
    "Qwen3.8-27B-UD-Q6_K_M",
    "qwen3.8",
    "qwen3.6:27b",
    "qwen3.6",
    "qwen3:27b",
    "qwen3:30b",
    "qwen3:32b",
    "qwen3",
    "qwen-3-32b",
    "qwen-2.5-32b",
    "qwen2.5:32b",
    "qwen2.5:14b",
    "qwen2.5:7b",
    "llama-3.3-70b-versatile",
    "llama3.3:70b",
    "llama3.1:8b",
    "llama3.1",
    "mistral-nemo",
]


_ACTIVE_ENDPOINT_CACHE: Optional[str] = None
_ACTIVE_MODEL_CACHE: Dict[str, str] = {}
_LAST_ENDPOINT_CHECK: float = 0.0


async def resolve_active_endpoint() -> str:
    """
    Probes candidate endpoints (OPENAI_BASE_URL, llama-server on 8080, Ollama on 11434)
    with fast non-blocking connect timeouts and returns the first responsive OpenAI-compatible base URL.
    Caches the active endpoint for 15 seconds to avoid per-turn probe latency.
    """
    global _ACTIVE_ENDPOINT_CACHE, _LAST_ENDPOINT_CHECK
    import time

    env_base = os.getenv("OPENAI_BASE_URL")
    if env_base:
        return env_base.rstrip("/")

    now = time.time()
    if _ACTIVE_ENDPOINT_CACHE and (now - _LAST_ENDPOINT_CHECK < 15.0):
        return _ACTIVE_ENDPOINT_CACHE

    candidate_urls = get_candidate_urls()
    headers = get_auth_headers()

    for base_url in candidate_urls:
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(0.8, connect=0.35)) as client:
                res = await client.get(f"{base_url}/models", headers=headers)
                if res.status_code in (200, 401, 403):  # 401/403 means server exists but requires auth
                    _ACTIVE_ENDPOINT_CACHE = base_url
                    _LAST_ENDPOINT_CHECK = now
                    return base_url
        except Exception:
            continue

    # Fallback to Ollama or default
    _ACTIVE_ENDPOINT_CACHE = "http://localhost:11434/v1"
    _LAST_ENDPOINT_CHECK = now
    return _ACTIVE_ENDPOINT_CACHE


async def get_best_available_model(preferred_model: Optional[str] = None, base_url: Optional[str] = None) -> str:
    """
    Checks the active OpenAI-compatible instance for available models and returns
    the best matching model (defaulting to preferred_model, OPENAI_MODEL, or Qwen/Llama priority list).
    """
    env_model = os.getenv("OPENAI_MODEL")
    target = preferred_model or env_model or DEFAULT_MODEL
    active_url = base_url or await resolve_active_endpoint()

    # If an explicit OPENAI_BASE_URL is set (cloud API like Groq/OpenRouter/OpenAI), use configured model directly
    if os.getenv("OPENAI_BASE_URL") and (preferred_model or env_model):
        return target

    cache_key = f"{active_url}:{target}"
    if cache_key in _ACTIVE_MODEL_CACHE:
        return _ACTIVE_MODEL_CACHE[cache_key]

    url = f"{active_url}/models"
    headers = get_auth_headers()

    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(2.0, connect=0.5)) as client:
            res = await client.get(url, headers=headers)
            if res.status_code == 200:
                installed_data = res.json()
                installed_names = [m.get("id", "") for m in installed_data.get("data", [])]

                # Check if exact target or base name matches (case-insensitive)
                target_lower = target.lower()
                for name in installed_names:
                    name_lower = name.lower()
                    if target_lower == name_lower or target_lower in name_lower or name_lower in target_lower:
                        _ACTIVE_MODEL_CACHE[cache_key] = name
                        return name

                # Otherwise pick the highest priority model installed
                for pref in MODEL_PREFERENCES:
                    pref_lower = pref.lower()
                    for name in installed_names:
                        if pref_lower in name.lower():
                            logger.info(f"Auto-selected installed model: {name}")
                            _ACTIVE_MODEL_CACHE[cache_key] = name
                            return name

                if installed_names:
                    _ACTIVE_MODEL_CACHE[cache_key] = installed_names[0]
                    return installed_names[0]
    except Exception:
        pass

    _ACTIVE_MODEL_CACHE[cache_key] = target
    return target


def get_candidate_fallback_models(primary_model: str, base_url: str) -> list[str]:
    """Returns provider-compatible fallback model list for automatic failover."""
    candidates = [primary_model]
    active_base = (base_url or os.getenv("OPENAI_BASE_URL", "")).lower()

    if "openrouter.ai" in active_base:
        openrouter_fallbacks = [
            "qwen/qwen3.8-27b",
            "qwen/qwen3.8-27b-20260814",
            "qwen/qwen-2.5-72b-instruct",
            "qwen/qwen-2.5-coder-32b-instruct",
            "meta-llama/llama-3.3-70b-instruct",
        ]
        for m in openrouter_fallbacks:
            if m not in candidates:
                candidates.append(m)
    elif os.getenv("OPENAI_BASE_URL") and not any(h in active_base for h in ("localhost", "127.0.0.1", "0.0.0.0")):
        cloud_fallbacks = [
            "qwen/qwen3.8-27b",
            "qwen-2.5-72b-instruct",
            "llama-3.3-70b-versatile",
        ]
        for m in cloud_fallbacks:
            if m not in candidates:
                candidates.append(m)
    else:
        local_fallbacks = [
            "Qwen3.8-27B-UD-Q6_K_M.gguf",
            "qwen3.8-27b-ud-q6_k_m.gguf",
            "qwen3.8:27b",
            "qwen3.8",
            "qwen3.6:27b",
            "qwen3.6",
            "qwen3:27b",
            "qwen2.5:32b",
            "qwen2.5:14b",
            "llama3.3:70b",
            "llama3.1:8b",
        ]
        for m in local_fallbacks:
            if m not in candidates:
                candidates.append(m)
    return candidates


def _extract_json_from_llm_response(content: str) -> Dict[str, Any]:
    """
    Extracts and parses JSON object from LLM response, stripping Qwen3 / Unsloth thinking tags
    (<think>...</think>), markdown code blocks, or leading/trailing whitespace.
    """
    import re
    cleaned = (content or "").strip()
    if not cleaned:
        return {}

    # Direct JSON parse attempt
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # Strip Qwen3 / Unsloth Dynamic <think>...</think> or <thought>...</thought> tags
    without_thoughts = re.sub(r'<(think|thought|scratchpad|clinical_notes|reasoning)>.*?</\1>', '', cleaned, flags=re.DOTALL | re.IGNORECASE).strip()
    try:
        return json.loads(without_thoughts)
    except json.JSONDecodeError:
        pass

    # Extract from markdown fences ```json ... ``` or ``` ... ```
    if "```json" in without_thoughts:
        extracted = without_thoughts.split("```json", 1)[1].split("```", 1)[0].strip()
        try:
            return json.loads(extracted)
        except json.JSONDecodeError:
            pass
    elif "```" in without_thoughts:
        extracted = without_thoughts.split("```", 1)[1].split("```", 1)[0].strip()
        try:
            return json.loads(extracted)
        except json.JSONDecodeError:
            pass

    # Substring between first '{' and last '}'
    first_brace = without_thoughts.find('{')
    last_brace = without_thoughts.rfind('}')
    if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
        candidate = without_thoughts[first_brace:last_brace + 1]
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            pass

    raise json.JSONDecodeError("Could not extract valid JSON from LLM response", cleaned, 0)


async def ask_local_llm(
    system_prompt: str,
    user_prompt: str,
    model: Optional[str] = None,
    max_tokens: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Sends a prompt to the active OpenAI-compatible instance (local llama-server/Ollama or cloud provider like Groq)
    and enforces a JSON response using structured outputs / JSON Object mode with Qwen3 hyperparameter tuning.
    Includes automatic failover for cloud rate limits (429) or model unavailability.
    """
    base_url = await resolve_active_endpoint()
    primary_model = await get_best_available_model(model, base_url=base_url)
    url = f"{base_url}/chat/completions"
    headers = get_auth_headers()
    token_limit = max_tokens if max_tokens is not None else int(os.getenv("OPENAI_MAX_TOKENS", "8192"))

    models_to_try = get_candidate_fallback_models(primary_model, base_url)
    last_error = None
    reasoning_cfg = get_reasoning_params(base_url)

    for attempt_model in models_to_try:
        payload = {
            "model": attempt_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "stream": False,
            "response_format": {"type": "json_object"},
            "temperature": 0.0,
            "top_p": 0.80,
            "max_tokens": token_limit,
            **reasoning_cfg,
        }

        try:
            async with httpx.AsyncClient(timeout=180.0) as client:
                response = await client.post(url, json=payload, headers=headers)
                if response.status_code in (429, 404, 503) and attempt_model != models_to_try[-1]:
                    logger.warning(f"AI query on {attempt_model} returned {response.status_code}. Retrying on fallback model...")
                    continue
                response.raise_for_status()
                data = response.json()

                # OpenAI structure: choices[0].message.content
                message_content = data.get("choices", [{}])[0].get("message", {}).get("content", "{}")
                return _extract_json_from_llm_response(message_content)
        except httpx.ConnectError as ce:
            last_error = ce
            break
        except Exception as ex:
            last_error = ex
            if attempt_model != models_to_try[-1]:
                continue
            break

    if isinstance(last_error, httpx.ConnectError):
        logger.error(f"Failed to connect to AI server at {base_url}. Is it running?")
        raise RuntimeError(
            f"Cannot connect to AI service at {base_url}. "
            "Please ensure local llama-server (start_llama_server.bat) is running or OPENAI_API_KEY/OPENAI_BASE_URL are configured."
        )
    raise RuntimeError(f"Error executing AI request: {str(last_error)}")


async def stream_local_llm_chat(
    messages: list[Dict[str, Any]],
    system_prompt: Optional[str] = None,
    model: Optional[str] = None,
    temperature: float = 0.2,
    top_p: float = 0.85,
    max_tokens: Optional[int] = None,
    tools: Optional[list[Dict[str, Any]]] = None,
):
    """
    Streams chat completion tokens and reasoning deltas from active OpenAI-compatible endpoint
    (llama-server on 8080, Ollama on 11434, or Cloud LLM like Groq) using SSE.
    Yields dictionary chunks: {'type': 'content'|'reasoning'|'tool_call'|'done'|'error', 'data': ...}
    Includes resilient fallback across models upon rate limits (429) or transient errors.
    """
    base_url = await resolve_active_endpoint()
    primary_model = await get_best_available_model(model, base_url=base_url)
    url = f"{base_url}/chat/completions"
    headers = get_auth_headers()
    token_limit = max_tokens if max_tokens is not None else int(os.getenv("OPENAI_MAX_TOKENS", "8192"))

    full_messages = []
    if system_prompt:
        full_messages.append({"role": "system", "content": system_prompt})
    full_messages.extend(messages)

    models_to_try = get_candidate_fallback_models(primary_model, base_url)
    last_error_msg = None
    reasoning_cfg = get_reasoning_params(base_url)

    for attempt_model in models_to_try:
        payload: Dict[str, Any] = {
            "model": attempt_model,
            "messages": full_messages,
            "stream": True,
            "temperature": temperature,
            "top_p": top_p,
            "max_tokens": token_limit,
            "stop": ["<|im_end|>", "<|endoftext|>", "<|im_start|>"],
            **reasoning_cfg,
        }

        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"

        stream_succeeded = False
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(180.0, connect=5.0)) as client:
                async with client.stream("POST", url, json=payload, headers=headers) as response:
                    if response.status_code in (429, 404, 503) and attempt_model != models_to_try[-1]:
                        err_text = await response.aread()
                        logger.warning(f"AI Stream for {attempt_model} returned {response.status_code} ({err_text.decode('utf-8', errors='ignore')[:120]}). Trying fallback model...")
                        last_error_msg = f"Model {attempt_model} unavailable ({response.status_code})."
                        continue

                    if response.status_code != 200:
                        err_text = await response.aread()
                        logger.error(f"AI Stream returned status {response.status_code}: {err_text.decode('utf-8', errors='ignore')}")
                        if attempt_model != models_to_try[-1]:
                            continue
                        yield {"type": "error", "data": f"AI Server returned status {response.status_code}"}
                        return

                    stream_succeeded = True
                    async for line in response.aiter_lines():
                        line = line.strip()
                        if not line:
                            continue
                        if line.startswith("data: "):
                            data_str = line[6:].strip()
                            if data_str == "[DONE]":
                                yield {"type": "done", "data": "[DONE]"}
                                return
                            try:
                                chunk = json.loads(data_str)
                                choices = chunk.get("choices", [])
                                if not choices:
                                    continue
                                delta = choices[0].get("delta", {})

                                # 1. Reasoning / Thinking delta
                                reasoning = delta.get("reasoning") or delta.get("reasoning_content") or delta.get("thought") or delta.get("thinking")
                                if reasoning:
                                    yield {"type": "reasoning", "data": reasoning}

                                # 2. Standard content delta
                                content = delta.get("content")
                                if content:
                                    yield {"type": "content", "data": content}

                                # 3. Tool call deltas
                                tool_calls = delta.get("tool_calls")
                                if tool_calls:
                                    yield {"type": "tool_call_delta", "data": tool_calls}

                                # 4. Finish reason
                                finish_reason = choices[0].get("finish_reason")
                                if finish_reason:
                                    yield {"type": "finish_reason", "data": finish_reason}
                            except json.JSONDecodeError:
                                continue
            if stream_succeeded:
                return
        except httpx.ConnectError:
            logger.error(f"Cannot connect to AI service at {base_url}")
            yield {
                "type": "error",
                "data": f"Cannot connect to AI engine at {base_url}. Please ensure local server is running or cloud credentials are set in .env."
            }
            return
        except Exception as e:
            logger.warning(f"Notice during AI streaming on {attempt_model}: {e}")
            last_error_msg = str(e)
            if attempt_model != models_to_try[-1]:
                continue
            yield {"type": "error", "data": last_error_msg or "AI streaming interrupted"}
            return


async def preload_and_warmup_model() -> None:
    """
    Called upon server startup in a non-blocking background task to warm the active model.
    """
    try:
        base_url = await resolve_active_endpoint()
        model_name = await get_best_available_model(base_url=base_url)
        logger.info(f"[*] AI model '{model_name}' active at {base_url}.")
    except Exception as e:
        logger.warning(f"AI model initialization notice: {e}")
