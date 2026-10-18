from memrelay import hf


def probe_factory(up):
    calls = []

    def probe(url):
        calls.append(url)
        return url in up

    return probe, calls


def test_explicit_and_off():
    assert hf.resolve_endpoint("https://m.example/", {}, use_cache=False) == "https://m.example"
    assert hf.resolve_endpoint("off", {}, use_cache=False) is None
    assert hf.resolve_endpoint("", {}, use_cache=False) is None


def test_auto_keeps_user_choice():
    probe, calls = probe_factory(set())
    assert hf.resolve_endpoint("auto", {"HF_ENDPOINT": "https://mine"}, probe, use_cache=False) is None
    assert calls == []


def test_auto_official_reachable():
    probe, calls = probe_factory({hf.OFFICIAL})
    assert hf.resolve_endpoint("auto", {}, probe, use_cache=False) is None
    assert calls == [hf.OFFICIAL]


def test_auto_falls_back_to_mirror():
    probe, _ = probe_factory({"https://hf-mirror.com"})
    assert hf.resolve_endpoint("auto", {}, probe, use_cache=False) == "https://hf-mirror.com"


def test_auto_nothing_reachable():
    probe, _ = probe_factory(set())
    assert hf.resolve_endpoint("auto", {}, probe, use_cache=False) is None


def test_backend_env_sets_mirror(home, monkeypatch):
    from memrelay.backend import BasicMemoryBackend
    from memrelay.config import Config
    from memrelay.vault import Vault

    monkeypatch.delenv("HF_ENDPOINT", raising=False)
    cfg = Config(vault=home / "v", hf_endpoint="https://hf-mirror.com")
    env = BasicMemoryBackend(cfg, Vault(cfg.vault)).env()
    assert env["HF_ENDPOINT"] == "https://hf-mirror.com"
    assert env["BASIC_MEMORY_CONFIG_DIR"].endswith("basic-memory")
    assert "PYTEST_CURRENT_TEST" not in env
