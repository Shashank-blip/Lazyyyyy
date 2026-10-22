"""Verdict parsing and rank fusion. These stay offline from Gemma and Tiger."""

from app.judge import brief_lines, normalize_verdicts, parse_items, parse_json_object
from app.ollama_client import explain_ollama_error
from app.search import rrf_fusion


def test_parse_json_object_strips_fences():
    payload = parse_json_object('```json\n{"items": ["one"]}\n```')
    assert payload == {"items": ["one"]}


def test_parse_items_drops_blanks_and_rejects_a_ninth():
    assert parse_items({"items": [" a ", "", "b"]}) == ["a", "b"]
    try:
        parse_items({"items": [str(i) for i in range(9)]})
    except ValueError as exc:
        assert "eight" in str(exc)
    else:
        raise AssertionError("expected a limit error")


def test_normalize_verdicts_keeps_only_known_matches():
    payload = {
        "verdicts": [
            {"index": 0, "verdict": "pardoned", "summary": "Skip it.", "script": "nope"},
            {
                "index": 1,
                "verdict": "two minutes",
                "summary": "Priya is waiting.",
                "script": "Thursday.",
                "matched_id": 99,
            },
            {
                "index": 2,
                "verdict": "merge",
                "summary": "Same lease.",
                "matched_index": 1,
                "matched_id": 5,
            },
        ]
    }
    verdicts = normalize_verdicts(payload, 3, allowed_ids={5})
    assert verdicts[0]["verdict"] == "pardon"
    assert verdicts[0]["script"] == ""
    assert verdicts[1]["verdict"] == "two_minutes"
    assert verdicts[1]["script"] == "Thursday."
    assert verdicts[1]["matched_id"] is None
    assert verdicts[2]["matched_id"] == 5
    assert verdicts[2]["matched_index"] == 1


def test_merge_without_a_target_becomes_a_pardon():
    payload = {"verdicts": [{"index": 0, "verdict": "merge", "summary": "Same."}]}
    verdicts = normalize_verdicts(payload, 1, allowed_ids=set())
    assert verdicts[0]["verdict"] == "pardon"


def test_incomplete_verdicts_fail():
    try:
        normalize_verdicts({"verdicts": []}, 1, set())
    except ValueError:
        return
    raise AssertionError("expected an error")


def test_brief_falls_back_when_the_model_skips_a_line():
    verdicts = [
        {"verdict": "pardon"},
        {"verdict": "pardon"},
        {"verdict": "two_minutes"},
    ]
    assert brief_lines({}, verdicts) == ("2 can wait.", "One thing needs two minutes.")


def test_cloud_auth_failure_names_the_key():
    message = explain_ollama_error("unauthorized", 401, embed=False)
    assert "OLLAMA_API_KEY" in message


def test_memory_failure_names_the_hosted_model():
    message = explain_ollama_error("unable to allocate CPU_REPACK buffer", 500, embed=False)
    assert "gemma4" in message


def test_rrf_prefers_a_row_both_searches_found():
    keyword = [{"id": 1, "body": "a"}, {"id": 2, "body": "b"}]
    semantic = [{"id": 2, "body": "b"}, {"id": 3, "body": "c"}]
    fused = rrf_fusion(keyword, semantic, limit=3)
    assert fused[0]["id"] == 2
    assert [row["id"] for row in fused] == [2, 1, 3]
