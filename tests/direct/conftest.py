import pytest

CONTRACT_PATH = "contracts/charter_gate.py"
DAO_NAME = "Atlas DAO"
DAO_DESCRIPTION = "A DAO that funds open-source infrastructure."

MISSION = ("1", "Mission", "Fund open-source infrastructure that creates measurable value for developers.")
TRANSPARENCY = (
    "2",
    "Transparency",
    "Funding recipients must disclose material token allocations and conflicts of interest.",
)


@pytest.fixture
def charter(direct_vm, direct_deploy, direct_owner):
    """CharterGate deployed by `direct_owner`, who is left as the active sender."""
    direct_vm.sender = direct_owner
    return direct_deploy(CONTRACT_PATH, DAO_NAME, DAO_DESCRIPTION)


@pytest.fixture
def seeded(charter):
    """Owner is the active sender and sections 1 and 2 exist (charter_version == 3)."""
    charter.add_charter_section(*MISSION)
    charter.add_charter_section(*TRANSPARENCY)
    return charter


def hex_of(address) -> str:
    """Lower-case 0x address for either an Address or raw 20 bytes (fixtures use both)."""
    from genlayer.py.types import Address

    if not hasattr(address, "as_hex"):
        address = Address(address)
    return address.as_hex.lower()
