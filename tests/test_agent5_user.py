from agents.agent5_traction import agent5_user


def _skeleton():
    return {
        "company_name": "Acme",
        "inputs": {"founder_name": "Ada", "founder_linkedin": "x"},
        "pre_call": {},
        "call_notes": {},
        "diligence": {},
    }


def test_prompt_includes_attendees_as_exclusion_context():
    deal = _skeleton()
    deal["call_notes"] = {
        "attendees": ["Ada Lovelace", "Charles Babbage"],
        "raw_transcript_or_notes": "discussion about Zoho as a reference customer",
    }
    prompt = agent5_user(deal)

    assert "Ada Lovelace" in prompt
    assert "Charles Babbage" in prompt
    assert "exclusion set" in prompt.lower()
    assert "Zoho" in prompt


def test_prompt_handles_missing_materials_gracefully():
    deal = _skeleton()
    prompt = agent5_user(deal)

    assert "[None recorded]" in prompt or "[None provided]" in prompt
    assert "CUSTOMER & TRACTION INTELLIGENCE" in prompt
    # no KeyError, no blank interpolations that would confuse the model
    assert "{" not in prompt and "}" not in prompt


def test_prompt_passes_diligence_materials_through():
    deal = _skeleton()
    deal["inputs"]["diligence_materials"] = "CONTRACT: MSA with BigCorp, $120k ACV"
    prompt = agent5_user(deal)

    assert "BigCorp" in prompt
    assert "$120k ACV" in prompt
