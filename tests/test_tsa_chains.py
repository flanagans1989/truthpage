"""app/core/tsa_chains.py — resolving a TSA authority URL to its bundled
chain file under certs/tsa/. Only FreeTSA is configured today, so this is
mostly a contract test for when a second authority is ever added."""
from app.core.tsa_chains import (
    all_bundled_chain_paths,
    chain_filename_for_authority,
    chain_path_for_authority,
)


class TestChainFilenameForAuthority:
    def test_freetsa_resolves_to_its_own_file(self):
        assert chain_filename_for_authority("https://freetsa.org/tsr") == "freetsa.org.pem"

    def test_unknown_authority_resolves_to_none(self):
        assert chain_filename_for_authority("https://not-a-real-tsa.example.com/tsr") is None

    def test_empty_or_none_resolves_to_none(self):
        assert chain_filename_for_authority(None) is None
        assert chain_filename_for_authority("") is None

    def test_path_for_authority_matches_filename(self):
        path = chain_path_for_authority("https://freetsa.org/tsr")
        assert path is not None
        assert path.name == "freetsa.org.pem"
        assert path.is_file()


class TestAllBundledChainPaths:
    def test_includes_freetsa(self):
        names = {p.name for p in all_bundled_chain_paths()}
        assert "freetsa.org.pem" in names
