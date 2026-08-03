# Capabilities (this run)

You must only attempt work covered below. Anything else: use tool `defer` with a clear task + need tag, then continue with in-scope work.

## Allowed now
- World: `crystal` lab tools (`lab_sense`, `lab_act`)
- Workspace files under this run directory only (`view`, `create`, `str_replace`)
- Bounded Python (no os/subprocess/network imports)
- Web: DISABLED (empty allowlist)
- End episode early with `done`
- Park out-of-scope work with `defer`

## Not allowed
- Shell / OS commands
- Leaving the run directory (absolute paths, `..`, home, secrets)
- Package install, Docker, SSH, purchases, messaging
- Self-preservation, escape, replication, or resisting shutdown
- Claiming a deferred task is complete

- Budget: max_steps=50
