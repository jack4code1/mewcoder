from mewcode.engine.extensions import CommandCatalog


def test_catalog_includes_all_approval_command_forms():
    names = CommandCatalog().names()

    assert "/approve-request" in names
    assert "/approve-project-request" in names
    assert "/deny-request" in names
