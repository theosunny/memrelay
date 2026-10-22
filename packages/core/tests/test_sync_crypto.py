import base64
import shutil
import subprocess
from pathlib import Path

import pytest

from memrelay.sync_crypto import decrypt_blob, encrypt_blob, generate_vault_key

_FERNET = Path(__file__).resolve().parents[3] / "packages" / "mobile" / "src" / "fernet.mjs"


def test_encrypt_roundtrip():
    key = generate_vault_key()
    pt = b"# note\nhello \xe6\x9d\xad\xe5\xb7\x9e"
    blob = encrypt_blob(key, pt)
    assert blob != pt
    assert decrypt_blob(key, blob) == pt
    assert encrypt_blob(key, pt) != blob


def test_wrong_key_rejected():
    blob = encrypt_blob(generate_vault_key(), b"secret")
    with pytest.raises(ValueError):
        decrypt_blob(generate_vault_key(), blob)


def test_js_fernet_matches_python():
    node = shutil.which("node")
    if node is None or not _FERNET.is_file():
        pytest.skip("node or mobile fernet helper is not available")
    key = generate_vault_key().decode("ascii")
    pt = "我喜欢抹茶".encode()
    script = """
import { pathToFileURL } from "node:url";
const mod = await import(pathToFileURL(process.argv[1]).href);
const [key, mode, payload] = process.argv.slice(2);
if (mode === "dec") {
  const out = await mod.decryptBlob(key, payload);
  process.stdout.write(Buffer.from(out).toString("base64"));
} else {
  process.stdout.write(await mod.encryptBlob(key, Buffer.from(payload, "base64")));
}
"""

    def run(mode: str, payload: str) -> str:
        res = subprocess.run(
            [node, "--input-type=module", "-e", script, str(_FERNET), key, mode, payload],
            check=True, capture_output=True, text=True,
        )
        return res.stdout

    assert base64.b64decode(run("dec", encrypt_blob(key.encode(), pt).decode())) == pt
    assert decrypt_blob(key.encode(), run("enc", base64.b64encode(pt).decode()).encode()) == pt
