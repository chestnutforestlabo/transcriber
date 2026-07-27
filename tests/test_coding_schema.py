import copy

import pytest
from coding.schema import CodingValidationError, validate_coding_result


@pytest.fixture
def valid_coding():
    """Return one schema-valid result containing label overlap."""
    return {
        "version": 1,
        "audio": "walk.wav",
        "intervals": [
            {
                "id": "iv-0001",
                "label": "会話",
                "start": 1.0,
                "end": 3.0,
                "source": "llm",
                "note": "",
            },
            {
                "id": "iv-0002",
                "label": "AI説明",
                "start": 2.0,
                "end": 2.5,
                "source": "auto",
                "note": "",
            },
        ],
        "events": [
            {
                "id": "ev-0001",
                "label": "AI情報の共有",
                "time": 3.0,
                "end": 4.0,
                "speaker": "視覚障害者",
                "tags": ["周囲の話題"],
                "attrs": {
                    "co_labels": ["話題提示"],
                    "ai_reference": "within_30s",
                },
                "text": "AIが石垣と言っていたね",
                "note": "",
            },
            {
                "id": "ev-0002",
                "label": "同行者からの周囲説明",
                "time": 5.0,
                "end": 6.0,
                "speaker": "同行者",
                "tags": ["周囲の話題"],
                "attrs": {"co_labels": [], "response_type": "自発"},
                "text": "右に赤い門があります",
                "note": "",
            },
        ],
    }


def test_valid_coding_schema_accepts_overlap_between_label_lanes(valid_coding):
    """Different interval label lanes may overlap in time."""
    validate_coding_result(valid_coding, duration_sec=10.0)


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (
            lambda data: data["intervals"][0].update(label="未知"),
            "allowed interval label",
        ),
        (
            lambda data: data["intervals"][0].update(end=1.0),
            "start < end",
        ),
        (
            lambda data: data["events"][0]["attrs"].update(co_labels=[]),
            "AI情報の共有 requires",
        ),
        (
            lambda data: data["events"][1]["attrs"].pop("response_type"),
            "同行者からの周囲説明 requires",
        ),
        (
            lambda data: data["events"].reverse(),
            "monotonically ordered",
        ),
    ],
)
def test_invalid_coding_schema_reports_semantic_error(
    valid_coding,
    mutation,
    message,
):
    """Vocabulary, timing, ordering, and conditional attrs are enforced."""
    data = copy.deepcopy(valid_coding)
    mutation(data)

    with pytest.raises(CodingValidationError, match=message):
        validate_coding_result(data, duration_sec=10.0)
