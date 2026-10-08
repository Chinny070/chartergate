# v0.2.16
# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }

from genlayer import *

STATUS_SUBMITTED = "SUBMITTED"

MAX_U256 = 2**256 - 1
MAX_DAO_NAME = 120
MAX_DAO_DESCRIPTION = 2000
MAX_SECTION_ID = 64
MAX_SECTION_TITLE = 200
MAX_SECTION_BODY = 10000
MAX_PROPOSAL_TITLE = 200
MAX_PROPOSAL_DESCRIPTION = 10000
MAX_PROPOSAL_ACTION = 2000
MAX_PAGE_SIZE = 50

SECTION_ID_EXTRA_CHARS = "-_."


def _fail(code: str) -> None:
    raise gl.vm.UserError("EXPECTED:" + code)


def _require(cond: bool, code: str) -> None:
    if not cond:
        _fail(code)


def _str_arg(name: str, value) -> str:
    # GenVM does not enforce annotations, so caller input must be type-checked before any use.
    _require(isinstance(value, str), "INVALID_TYPE:" + name)
    return value


def _int_arg(name: str, value) -> int:
    # bool is an int subclass in Python, but is never a valid integer argument here.
    _require(isinstance(value, int) and not isinstance(value, bool), "INVALID_TYPE:" + name)
    _require(value >= 0 and value <= MAX_U256, "INTEGER_OUT_OF_RANGE:" + name)
    return int(value)


def _clean_text(name: str, value, max_len: int, code: str) -> str:
    cleaned = _str_arg(name, value).strip()
    _require(cleaned != "", code + "_EMPTY")
    _require(len(cleaned) <= max_len, code + "_TOO_LONG")
    return cleaned


def _validate_section_id(section_id) -> str:
    _str_arg("section_id", section_id)
    _require(section_id != "", "SECTION_ID_EMPTY")
    _require(len(section_id) <= MAX_SECTION_ID, "SECTION_ID_TOO_LONG")
    for ch in section_id:
        ok = (ch.isascii() and ch.isalnum()) or ch in SECTION_ID_EXTRA_CHARS
        _require(ok, "SECTION_ID_INVALID_CHARS")
    return section_id


def _next(value: u256) -> u256:
    _require(int(value) < MAX_U256, "COUNTER_OVERFLOW")
    return u256(int(value) + 1)


def _validate_page(offset, limit) -> tuple[int, int]:
    offset_i = _int_arg("offset", offset)
    limit_i = _int_arg("limit", limit)
    _require(limit_i >= 1, "PAGE_LIMIT_INVALID")
    _require(limit_i <= MAX_PAGE_SIZE, "PAGE_LIMIT_TOO_LARGE")
    return offset_i, limit_i


def _now() -> str:
    # Deterministic transaction datetime supplied by GenVM (not wall-clock time).
    return gl.message_raw["datetime"]


@allow_storage
class CharterSection:
    section_id: str
    title: str
    body: str
    active: bool
    created_at: str
    updated_at: str

    def __init__(
        self,
        section_id: str,
        title: str,
        body: str,
        active: bool,
        created_at: str,
        updated_at: str,
    ):
        self.section_id = section_id
        self.title = title
        self.body = body
        self.active = active
        self.created_at = created_at
        self.updated_at = updated_at

    def to_dict(self) -> dict:
        return {
            "section_id": self.section_id,
            "title": self.title,
            "body": self.body,
            "active": self.active,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


@allow_storage
class CharterRevision:
    section_id: str
    charter_version: u256
    title: str
    body: str
    active: bool
    changed_at: str

    def __init__(
        self,
        section_id: str,
        charter_version: u256,
        title: str,
        body: str,
        active: bool,
        changed_at: str,
    ):
        self.section_id = section_id
        self.charter_version = charter_version
        self.title = title
        self.body = body
        self.active = active
        self.changed_at = changed_at

    def to_dict(self) -> dict:
        return {
            "section_id": self.section_id,
            "charter_version": int(self.charter_version),
            "title": self.title,
            "body": self.body,
            "active": self.active,
            "changed_at": self.changed_at,
        }


@allow_storage
class Proposal:
    proposal_id: u256
    proposer: Address
    title: str
    description: str
    requested_action: str
    created_at: str
    charter_version_at_submission: u256
    status: str

    def __init__(
        self,
        proposal_id: u256,
        proposer: Address,
        title: str,
        description: str,
        requested_action: str,
        created_at: str,
        charter_version_at_submission: u256,
        status: str,
    ):
        self.proposal_id = proposal_id
        self.proposer = proposer
        self.title = title
        self.description = description
        self.requested_action = requested_action
        self.created_at = created_at
        self.charter_version_at_submission = charter_version_at_submission
        self.status = status

    def to_dict(self) -> dict:
        return {
            "proposal_id": int(self.proposal_id),
            "proposer": self.proposer.as_hex,
            "title": self.title,
            "description": self.description,
            "requested_action": self.requested_action,
            "created_at": self.created_at,
            "charter_version_at_submission": int(self.charter_version_at_submission),
            "status": self.status,
        }


class CharterGate(gl.Contract):
    owner: Address
    dao_name: str
    dao_description: str
    charter_version: u256
    created_at: str
    updated_at: str

    sections: TreeMap[str, CharterSection]
    section_ids: DynArray[str]

    proposals: TreeMap[u256, Proposal]
    proposal_count: u256

    revisions: DynArray[CharterRevision]
    section_versions: TreeMap[str, DynArray[u256]]

    def __init__(self, dao_name: str, dao_description: str):
        now = _now()
        self.owner = gl.message.sender_address
        self.dao_name = _clean_text("dao_name", dao_name, MAX_DAO_NAME, "DAO_NAME")
        self.dao_description = _clean_text(
            "dao_description", dao_description, MAX_DAO_DESCRIPTION, "DAO_DESCRIPTION"
        )
        self.charter_version = u256(1)
        self.created_at = now
        self.updated_at = now
        self.proposal_count = u256(0)

    # -- internal helpers -----------------------------------------------------

    def _require_owner(self) -> None:
        _require(gl.message.sender_address == self.owner, "NOT_OWNER")

    def _get_section(self, section_id) -> CharterSection:
        _str_arg("section_id", section_id)
        section = self.sections.get(section_id)
        _require(section is not None, "SECTION_NOT_FOUND")
        return section

    def _record_revision(
        self, section_id: str, title: str, body: str, active: bool, version: u256, now: str
    ) -> None:
        # The log is append-only: the revision that produced charter version v is revisions[v - 2].
        self.revisions.append(CharterRevision(section_id, version, title, body, active, now))
        self.section_versions.get_or_insert_default(section_id).append(version)

    def _known_version(self, charter_version) -> int:
        n = _int_arg("charter_version", charter_version)
        _require(n >= 1 and n <= int(self.charter_version), "CHARTER_VERSION_NOT_FOUND")
        return n

    def _effective_revision(self, section_id: str, n: int):
        versions = self.section_versions.get(section_id)
        if versions is None:
            return None
        lo = 0
        hi = len(versions)
        while lo < hi:
            mid = (lo + hi) // 2
            if int(versions[mid]) <= n:
                lo = mid + 1
            else:
                hi = mid
        if lo == 0:
            return None
        return self.revisions[int(versions[lo - 1]) - 2]

    def _section_count_at(self, n: int) -> int:
        # Sections are appended in creation order, which is also charter-version order, so the
        # sections that existed at version n are always a prefix of section_ids.
        ids = self.section_ids
        lo = 0
        hi = len(ids)
        while lo < hi:
            mid = (lo + hi) // 2
            if int(self.section_versions[ids[mid]][0]) <= n:
                lo = mid + 1
            else:
                hi = mid
        return lo

    # -- charter management (owner only; Stage 1 bootstrap mechanism) --------

    @gl.public.write
    def add_charter_section(self, section_id: str, title: str, body: str) -> None:
        self._require_owner()
        _validate_section_id(section_id)
        _require(self.sections.get(section_id) is None, "SECTION_ID_EXISTS")
        title = _clean_text("title", title, MAX_SECTION_TITLE, "SECTION_TITLE")
        body = _clean_text("body", body, MAX_SECTION_BODY, "SECTION_BODY")
        next_version = _next(self.charter_version)

        now = _now()
        self.sections[section_id] = CharterSection(section_id, title, body, True, now, now)
        self.section_ids.append(section_id)
        self._record_revision(section_id, title, body, True, next_version, now)
        self.charter_version = next_version
        self.updated_at = now

    @gl.public.write
    def update_charter_section(self, section_id: str, title: str, body: str) -> None:
        self._require_owner()
        section = self._get_section(section_id)
        _require(section.active, "SECTION_INACTIVE")
        title = _clean_text("title", title, MAX_SECTION_TITLE, "SECTION_TITLE")
        body = _clean_text("body", body, MAX_SECTION_BODY, "SECTION_BODY")
        next_version = _next(self.charter_version)

        now = _now()
        section.title = title
        section.body = body
        section.updated_at = now
        self._record_revision(section_id, title, body, True, next_version, now)
        self.charter_version = next_version
        self.updated_at = now

    @gl.public.write
    def deactivate_charter_section(self, section_id: str) -> None:
        self._require_owner()
        section = self._get_section(section_id)
        _require(section.active, "SECTION_ALREADY_INACTIVE")
        next_version = _next(self.charter_version)

        now = _now()
        section.active = False
        section.updated_at = now
        self._record_revision(section_id, section.title, section.body, False, next_version, now)
        self.charter_version = next_version
        self.updated_at = now

    # -- proposals (any caller) ----------------------------------------------

    @gl.public.write
    def submit_proposal(self, title: str, description: str, requested_action: str) -> None:
        title = _clean_text("title", title, MAX_PROPOSAL_TITLE, "PROPOSAL_TITLE")
        description = _clean_text(
            "description", description, MAX_PROPOSAL_DESCRIPTION, "PROPOSAL_DESCRIPTION"
        )
        requested_action = _clean_text(
            "requested_action", requested_action, MAX_PROPOSAL_ACTION, "PROPOSAL_ACTION"
        )
        proposal_id = _next(self.proposal_count)

        self.proposals[proposal_id] = Proposal(
            proposal_id,
            gl.message.sender_address,
            title,
            description,
            requested_action,
            _now(),
            self.charter_version,
            STATUS_SUBMITTED,
        )
        self.proposal_count = proposal_id

    # -- reads ----------------------------------------------------------------

    @gl.public.view
    def get_dao_metadata(self) -> dict:
        return {
            "dao_name": self.dao_name,
            "dao_description": self.dao_description,
            "owner": self.owner.as_hex,
            "charter_version": int(self.charter_version),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "section_count": len(self.section_ids),
            "proposal_count": int(self.proposal_count),
        }

    @gl.public.view
    def get_charter_version(self) -> u256:
        return self.charter_version

    @gl.public.view
    def get_charter_section(self, section_id: str) -> dict:
        return self._get_section(section_id).to_dict()

    @gl.public.view
    def get_charter_section_count(self) -> u256:
        return u256(len(self.section_ids))

    @gl.public.view
    def get_charter_section_ids_page(self, offset: u256, limit: u256) -> list[str]:
        offset_i, limit_i = _validate_page(offset, limit)
        ids = self.section_ids
        return [ids[i] for i in range(offset_i, min(offset_i + limit_i, len(ids)))]

    @gl.public.view
    def get_charter_sections_page(self, offset: u256, limit: u256) -> list[dict]:
        offset_i, limit_i = _validate_page(offset, limit)
        ids = self.section_ids
        return [
            self._get_section(ids[i]).to_dict()
            for i in range(offset_i, min(offset_i + limit_i, len(ids)))
        ]

    @gl.public.view
    def get_charter_revision(self, charter_version: u256) -> dict:
        n = self._known_version(charter_version)
        _require(n >= 2, "CHARTER_VERSION_HAS_NO_REVISION")
        return self.revisions[n - 2].to_dict()

    @gl.public.view
    def get_charter_section_at_version(self, section_id: str, charter_version: u256) -> dict:
        _str_arg("section_id", section_id)
        n = self._known_version(charter_version)
        revision = self._effective_revision(section_id, n)
        _require(revision is not None, "SECTION_NOT_FOUND_AT_VERSION")
        return revision.to_dict()

    @gl.public.view
    def get_charter_section_count_at_version(self, charter_version: u256) -> u256:
        return u256(self._section_count_at(self._known_version(charter_version)))

    @gl.public.view
    def get_charter_sections_at_version_page(
        self, charter_version: u256, offset: u256, limit: u256
    ) -> list[dict]:
        n = self._known_version(charter_version)
        offset_i, limit_i = _validate_page(offset, limit)
        ids = self.section_ids
        count = self._section_count_at(n)
        return [
            self._effective_revision(ids[i], n).to_dict()
            for i in range(offset_i, min(offset_i + limit_i, count))
        ]

    @gl.public.view
    def get_proposal(self, proposal_id: u256) -> dict:
        proposal = self.proposals.get(u256(_int_arg("proposal_id", proposal_id)))
        _require(proposal is not None, "PROPOSAL_NOT_FOUND")
        return proposal.to_dict()

    @gl.public.view
    def get_proposal_count(self) -> u256:
        return self.proposal_count

    @gl.public.view
    def get_proposals_page(self, offset: u256, limit: u256) -> list[dict]:
        offset_i, limit_i = _validate_page(offset, limit)
        count = int(self.proposal_count)
        # Proposal ids are 1..count, so a page of offset 0 starts at id 1.
        return [
            self.proposals[u256(i + 1)].to_dict()
            for i in range(offset_i, min(offset_i + limit_i, count))
        ]
