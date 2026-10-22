# Install MemRelay on the user machine (checklist — do not run until machines are online)

Prepared for the next turn. **Do not install yet** unless ListMachines shows a connected desktop and the user asked to install.

## Preconditions

- [ ] `ListMachines` shows a connected desktop (or macOS/Windows as applicable)
- [ ] User explicitly asked to install on that machine
- [ ] Network can reach GitHub + PyPI (or mirrors in CN)

## Steps (macOS / Linux)

1. Ensure [uv](https://docs.astral.sh/uv/) is installed.
2. `uv tool install basic-memory`
3. `uv tool install "git+https://github.com/theosunny/memrelay#subdirectory=packages/core"`
4. `memrelay init`
5. Confirm default: `memrelay doctor` → `review.mode: auto`
6. Optional strict: edit config.toml → `[review] mode = "strict"`
7. `memrelay connect --all` (preview + confirm each client)
8. Restart agents; ask one “what do you know about me?”
9. Optional: `memrelay capture all` then `memrelay status`
10. Optional: `memrelay autostart install --dry-run` then install if wanted

## Windows (PowerShell)

Same as README: install uv via astral script, then the same `uv tool install` lines, `memrelay init`, `connect --all`.

## Rollback

- `memrelay connect rollback <agent>` for client MCP config
- Uninstall: `uv tool uninstall memrelay` (and basic-memory if unused)
