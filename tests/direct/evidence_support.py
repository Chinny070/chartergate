"""Shared fixtures and helpers for the Stage 2 evidence tests. No real network is ever used: the direct
harness mocks `gl.nondet.web.get`, `gl.nondet.web.render` and `gl.nondet.exec_prompt`."""

import json

import pytest

from conftest import MISSION, TRANSPARENCY

PROPOSAL = (
    "Fund Atlas Protocol",
    "Support an open-source developer tool that makes contract testing faster.",
    "Grant funding to Atlas Protocol",
)

URL = "https://atlas.example.org/tokenomics"
URL_PATTERN = r"atlas\.example\.org"
CLAIM_NUMBERED = "Atlas team token allocation is 46%."
CLAIM_PLAIN = "Atlas discloses its team token allocation."

T_EVIDENCE = "2026-10-08T21:30:00Z"


def page(team="46%", footer="Rendered at 12:01 session abc123", extra=""):
    """A realistic tokenomics page. Footer/session noise is deliberately part of it."""
    return (
        "<html><head><title>Atlas tokenomics</title>"
        "<style>.t{color:red}</style><script>var session='abc123';</script></head>"
        "<body><h1>Atlas Tokenomics</h1><ul>"
        f"<li>Team: {team}</li><li>Community: 30%</li><li>Treasury: 24%</li></ul>"
        f"{extra}<footer>{footer}</footer></body></html>"
    )


def mock_page(vm, html=None, *, status=200, body=None, pattern=URL_PATTERN):
    vm.mock_web(pattern, {"status": status, "body": html if body is None else body})


def mock_answer(vm, *, supported=True, fact="team_token_allocation", value="46%", excerpt="Team: 46%", raw=None):
    """What the (mocked) LLM returns for the extraction prompt."""
    payload = raw if raw is not None else {"supported": supported, "fact": fact, "value": value, "excerpt": excerpt}
    vm.mock_llm(r"CLAIM TO CHECK", payload if isinstance(payload, str) else json.dumps(payload))


def reset(vm):
    vm.clear_mocks()


@pytest.fixture
def atlas(charter, direct_vm, direct_alice):
    """Charter v4 (s1, s2 added, s1 updated). Alice has submitted proposal 1 under charter v4 and is the active sender."""
    charter.add_charter_section(*MISSION)  # "1"  -> v2
    charter.add_charter_section(*TRANSPARENCY)  # "2"  -> v3
    charter.update_charter_section("1", "Mission", "Updated mission text")  # -> v4
    direct_vm.sender = direct_alice
    direct_vm.warp(T_EVIDENCE)
    charter.submit_proposal(*PROPOSAL)
    return charter


@pytest.fixture
def web(direct_vm):
    """A verified-looking source: static page + a matching LLM answer."""
    mock_page(direct_vm, page())
    mock_answer(direct_vm)
    return direct_vm


def submit(c, **overrides):
    args = dict(proposal_id=1, source_url=URL, source_kind="STATIC_WEB", claim=CLAIM_NUMBERED, related_section_id="2")
    args.update(overrides)
    return c.submit_evidence(args["proposal_id"], args["source_url"], args["source_kind"], args["claim"], args["related_section_id"])


def snapshot(c):
    """Everything observable that evidence must never alter: charter, revisions, proposals."""
    version = c.get_charter_version()
    return {
        "sections": c.get_charter_sections_page(0, 50),
        "revisions": [c.get_charter_revision(v) for v in range(2, version + 1)],
        "proposals": c.get_proposals_page(0, 50),
        "version": version,
    }
