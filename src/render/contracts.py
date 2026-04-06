from __future__ import annotations


def render_blueprint_contract() -> dict:
    fact_item = {
        "id": "",
        "textZh": "",
    }
    return {
        "summaryZh": "",
        "subject": {
            "identityReadZh": "",
            "facts": [fact_item],
            "forbidden": [fact_item],
        },
        "world": {
            "summaryZh": "",
            "facts": [fact_item],
            "forbidden": [fact_item],
        },
        "action": {
            "summaryZh": "",
            "facts": [fact_item],
            "forbidden": [fact_item],
        },
        "wardrobe": {
            "summaryZh": "",
            "required": [fact_item],
            "optional": [fact_item],
            "forbidden": [fact_item],
        },
        "camera": {
            "summaryZh": "",
            "framing": "full_body",
            "aspectRatio": "4:5",
            "facts": [fact_item],
            "forbidden": [fact_item],
        },
        "integration": {
            "heroFactIds": [""],
            "supportingFactIds": [""],
            "negativeFactIds": [""],
            "conflictResolutionsZh": [""],
            "renderIntentZh": "",
        },
        "acceptanceChecksZh": [""],
    }
