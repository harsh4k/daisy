# AI permission approval — verified support and boundaries (T17)

Research checked on 2026-10-22. This describes supported interfaces, not proof
that Daisy has installed, trusted, or exercised them. Earlier claims that Codex
app-server lacked approval requests, that Codex HTTP permission hooks were
supported, and that missing upstream IDs made concurrent hook requests
inherently indistinguishable were incorrect.

## Installed versions and configuration

The installed executables successfully returned codex-cli 0.160.0 and Claude
Code 2.1.287. Codex user hooks.json already contains a trusted Caveman
PermissionRequest command hook; this is not a Daisy hook. Claude user
settings.json currently has no PermissionRequest entry.

These are CLI versions. Desktop versions and active desktop-session reload were
not verified. No credentials were read; no global configuration or trust records
were modified during this research.

## Supported routes

| Surface | Mechanism | Boundary |
|---|---|---|
| Codex runtime | Synchronous PermissionRequest command hook | New hook requires review and trust. |
| Codex app-server client | Server-initiated JSON-RPC approval requests | Works for a client owning the request lifecycle; arbitrary attachment to existing desktop requests is not established. |
| Claude Code | Synchronous PermissionRequest command hook | Documented for Code sessions including the Code desktop surface; ordinary Claude chat and Cowork are not established here. |
| Claude Code sandbox network prompt | Notification permission_prompt | PermissionRequest does not run for this prompt. Detection does not provide Allow/Deny. |

Codex supports command and mcp_tool handlers, not HTTP hooks. A command helper
is the smallest common supported mechanism.

Sources: [Codex hooks](https://learn.chatgpt.com/docs/hooks),
[Codex app-server](https://learn.chatgpt.com/docs/app-server),
[Claude Code hooks](https://code.claude.com/docs/en/hooks).

## Hook input and decision contract

Both command hooks receive JSON on stdin, including session_id, cwd,
hook_event_name, tool_name, and tool_input. Codex adds turn_id and model.
Treat tool input as untrusted display data; never execute it in Daisy.
Neither documented PermissionRequest payload supplies tool_use_id.

Allow once returns JSON on stdout with exit zero:

```json
{"hookSpecificOutput":{"hookEventName":"PermissionRequest","decision":{"behavior":"allow"}}}
```

Deny returns:

```json
{"hookSpecificOutput":{"hookEventName":"PermissionRequest","decision":{"behavior":"deny","message":"Denied in Daisy."}}}
```

No decision preserves the native permission flow. Exit code two alone is not a
portable denial for this event. Codex rejects updatedInput, updatedPermissions,
and interrupt on PermissionRequest; do not share Claude's richer schema blindly.
With multiple Codex decisions, denial wins. Preserve existing policy hooks,
managed settings, and approval policy. Daisy must not grant persistent rules.

Sources: [Codex PermissionRequest](https://learn.chatgpt.com/docs/hooks#permissionrequest),
[Claude PermissionRequest](https://code.claude.com/docs/en/hooks#permissionrequest).

## Exact request binding without an upstream ID

Each synchronous hook invocation already owns a unique stdin/stdout channel.
Generate a cryptographically random invocation ID in the helper and hold a live
connection to Daisy until answered. Bind the card to that ID and connection,
not only a session/tool/input tuple. Identical commands remain separate requests.

Required invariants:

- Authenticate local helper connections and restrict the endpoint to the current
  user; do not expose an unauthenticated approval API.
- Retain requests only while their invocation is live. Disconnection,
  cancellation, expiry, restart, or completion invalidates its buttons.
- Accept one answer per invocation. Never persist or reuse an old approval.
- Show provider, requested action, working directory, and session context.
  Provide a way to inspect clipped commands before approval.
- Keep the helper deadline shorter than the upstream timeout; invalidate cards
  before falling back to native prompts.
- When Daisy is unavailable, return no decision. Timeout never means Allow.
- Notifications announce requests; text, screenshots, and window titles are not
  an authorization transport.

The ID belongs to Daisy's transport. The live original helper channel binds its
answer to the actual upstream invocation.

## Proposed setup and activation

Add a distinct Daisy command hook to each supported user configuration without
changing existing hooks. Use a stable installed helper path and explicit provider
argument. Back up configuration; removal deletes only Daisy-owned entries.

Leave Caveman's command and trust record untouched. Codex skips new or changed
non-managed hooks until the user reviews and trusts them through /hooks. Never
manufacture trusted_hash entries, reuse another hook's trust, or enable bypass.
Show activation as pending until the new hook actually executes successfully.

Restart or create a session when needed: existing-session hot reload is not
established here. Installation cannot recover requests already pending before
the hook loaded. Claude Code 2.1.287 predates the documented 2.1.295 onFailure
option; do not configure that option without a separately verified upgrade.

Sources: [Codex trust](https://learn.chatgpt.com/docs/hooks#review-and-trust-hooks),
[Claude failure handling](https://code.claude.com/docs/en/hooks#block-the-action-when-a-hook-fails).

## App-server alternative

Codex app-server explicitly documents item/commandExecution/requestApproval,
item/fileChange/requestApproval, and item/permissions/requestApproval. JSON-RPC
IDs correlate responses; serverRequest/resolved clears requests. Grants must
stay within the requested subset and scope. This supports client-owned sessions;
it does not establish taking over the user's existing desktop approvals.

## Outside this implementation

Hermes and OpenCode were not re-verified in this task. Earlier research claimed
Hermes approval RPC and OpenCode HTTP/SSE permission routes. Their installed
versions, endpoints, authentication, expiry, and existing desktop compatibility
remain unverified here. Treat earlier claims as leads, not implementation facts.

## Evidence required before claiming success

Exercise real hooked requests from both installed tools. Prove Allow once and
Deny reach the exact invocation. Cover identical concurrent commands, multiple
sessions, stale buttons, helper/Daisy exit, unavailable endpoint, expiry, and
preservation of native approval and policy behavior. Synthetic inputs prove
transport only, not live integration or user-reviewed trust configuration.
