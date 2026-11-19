"""Stdlib-urllib client of the LLM path (design doc, sections 3.1-3.4).

One function, :func:`transcribe`: N independent draws at low temperature of
the JSON spec of a prompt, through any OpenAI-compatible
``/chat/completions`` endpoint. No SDK, no dependency.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
import warnings

# Fixed preamble of the system prompt (design doc, section 3.2).
FIELD_RULES = (
    "You translate a quantum-chemistry request into exactly one JSON spec for the AMAC toolchain.\n"
    "Field rules:\n"
    "- Fill only the keys the user mentioned. Everything else is ABSENT, not default-valued: "
    "defaults are the executor's job, never yours.\n"
    "- Keys: software (only if the user named it), method, module, structure, method_args, "
    "module_args, options, handlers, ambiguities.\n"
    '- structure is exactly one of {"name": "<chemical formula>"}, {"xyz": "<xyz text>"}, '
    '{"file": "<path>"}; name is the chemical formula — map common words to formulas '
    "(eau, water -> H2O; methanol -> CH3OH; ammoniac, ammonia -> NH3; methane -> CH4).\n"
    '- method_args.dispersion is a model string, or an object {"value": <model>, ...damping '
    "parameters...}. For method dftb-3 with software dftb+ the user always states a dispersion "
    'model; write the explicit string "none" only when the user explicitly asks for no '
    "dispersion. For software deMonNano only model-1/model-2 exist and dispersion cannot be "
    'disabled: "none" is invalid there.\n'
    "- Values must come from the catalog below (choices, aliases); an unrecognizable token goes "
    "into ambiguities with the interpretation proposed, never silently rewritten.\n"
    "- ambiguities is a list of short strings, empty when there is no doubt.\n"
    "Respond with JSON only: no code fences, no comments, no keys outside the rules.\n"
)

_WORKED_EXAMPLES = (
    "Worked examples —\n"
    'prompt: "sp DFTB2 water d4"\n'
    'spec: {"method": "dftb-2", "module": "single-point", "structure": {"name": "H2O"}, '
    '"method_args": {"dispersion": "d4"}, "ambiguities": []}\n'
    'prompt: "calcul de DFTB 3 sur une molécule d\'eau avec dispersion b3-bj"\n'
    'spec: {"method": "dftb-3", "module": "single-point", "structure": {"name": "H2O"}, '
    '"method_args": {"dispersion": "d3-bj"}, '
    "\"ambiguities\": [\"'b3-bj' is not a valid choice, interpreted as 'd3-bj'\"]}"
)


def build_system_prompt(schema: dict) -> str:
    """Fixed preamble + field rules + schema + alias table + worked examples."""
    return (
        f"{FIELD_RULES}\n"
        f"Catalog schema (single source of truth):\n"
        f"{json.dumps(schema, indent=1, sort_keys=True)}\n\n"
        f"Alias table (alias -> canonical name):\n"
        f"{json.dumps(schema.get('aliases', {}), sort_keys=True)}\n\n"
        f"{_WORKED_EXAMPLES}"
    )


def _post(url: str, api_key: str, body: dict, timeout: float = 120.0) -> dict:
    """POST one chat completion request and return the parsed payload."""
    request = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def transcribe(
    prompt: str,
    schema: dict,
    api_key: str,
    url: str,
    n: int = 5,
    temperature: float = 0.2,
    model: str | None = None,
) -> list[tuple[dict, dict]]:
    """Draw up to N schema-constrained spec translations of ``prompt``.

    Each attempt is one chat completion with the spec schema as
    ``response_format`` (``json_schema``); a network, HTTP or JSON failure
    is discarded *with a warning* and redrawn, at most ``n`` total attempts.
    Problems never raise: the return value holds whatever parsed (possibly
    fewer than ``n`` entries).

    Args:
        prompt: Free-text request of the user.
        schema: The generated spec_schema.json content (drives the prompt).
        api_key: Bearer key of the endpoint.
        url: OpenAI-compatible /chat/completions URL.
        n: Number of draws (at most n API attempts).
        temperature: Sampling temperature (low: the vote, not the draw,
            decides — design doc, section 3.3).
        model: Optional model name sent to the endpoint.

    Returns:
        A list of ``(spec, raw_response)`` pairs, in draw order.
    """
    # Schema-constrained decoding (design doc, sections 3.1/3.3/3.4): the
    # actual spec schema is embedded in the request, not a bare json_object.
    body = {
        "messages": [
            {"role": "system", "content": build_system_prompt(schema)},
            {"role": "user", "content": prompt},
        ],
        "temperature": temperature,
        "response_format": {
            "type": "json_schema",
            "json_schema": {"name": "spec", "schema": schema},
        },
    }
    if model is not None:
        body["model"] = model

    samples: list[tuple[dict, dict]] = []
    for _ in range(n):
        if len(samples) >= n:
            break
        try:
            payload = _post(url, api_key, body)
            content = payload["choices"][0]["message"]["content"]
            spec = json.loads(content)
        except (urllib.error.URLError, OSError, KeyError, IndexError, ValueError) as error:
            # URLError covers HTTP errors; OSError covers socket timeouts.
            warnings.warn(f"transcribe: draw failed ({type(error).__name__}: {error}); redrawing")
            continue
        if not isinstance(spec, dict):
            warnings.warn("transcribe: the response is not a JSON object; redrawing")
            continue
        samples.append((spec, payload))
    return samples
