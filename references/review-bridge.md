# Goal Ledger MCP App review bridge

Use this reference when native planning controls are unavailable or `pro_review_delivery` is `mcp-app`.

## Contents

- [Purpose](#purpose)
- [Security boundary](#security-boundary)
- [What is actually one-time](#what-is-actually-one-time)
- [Runtime requirements](#runtime-requirements)
- [Detailed one-time setup](#detailed-one-time-setup)
- [Automatic Codex-driven setup](#automatic-codex-driven-setup)
- [Verify the connection](#verify-the-connection)
- [What changes for each review](#what-changes-for-each-review)
- [Planning controls](#planning-controls)
- [Run one GPT Pro review](#run-one-gpt-pro-review)
- [Credential and data handling](#credential-and-data-handling)
- [Fallback and recovery](#fallback-and-recovery)
- [Troubleshooting](#troubleshooting)
- [Validation](#validation)

## Purpose

Goal Ledger ships its own MCP server and MCP App widget. It does not depend on DevSpace, a separate Codex plugin, or the legacy `$pro` skill. The bridge provides:

- six real checkbox controls for the independent planning choices;
- bounded round, stage, delivery, gate, model-family, and effort selectors;
- direct GPT Pro access to the existing deterministic review packet without a browser file upload;
- immutable response capture back into the selected Pro round;
- the same ZIP, manifest, response, and reconciliation custody used by browser delivery.

The MCP App is an optional transport. Canonical state remains in `goal.md`, `progress.md`, and the Pro evidence directory.

## Security boundary

Run one review-bound server process per prepared stage and round. The process may:

- read `request.md`, `packet-manifest.json`, `state.json`, and `context-packet.zip` for that round;
- expose only ZIP members listed by the exact manifest;
- record one `mcp-app` transport attempt and submission;
- write one immutable `response.md`, response metadata, and the normal state transition.

It may not:

- read arbitrary repository paths or follow a path supplied by ChatGPT;
- expose the live repository, Git operations, credentials, or secrets outside the packet;
- run shell commands;
- create, edit, or delete source files;
- change the goal contract or reconcile its own review;
- replace a different stored response.

The bridge verifies the ZIP hash, member set, member byte counts and hashes, `START-HERE.md`, and request hash before every packet read. A changed packet fails closed.

Prefer OpenAI Secure MCP Tunnel. It is outbound-only and keeps the local MCP server off the public internet. Do not expose the review bridge through an anonymous public tunnel. A public HTTPS deployment requires a separately reviewed OAuth 2.1 resource-server design and is outside this skill's default path.

## What is actually one-time

The setup has three durable pieces and two repeatable pieces:

| Item | Frequency | Where it lives |
| --- | --- | --- |
| Install `tunnel-client` | Once per machine, then update normally | Local executable on `PATH` |
| Create and associate the OpenAI tunnel | Once per owner/workspace trust boundary | OpenAI Platform; identified by one `tunnel_id` |
| Create the private `Codex Goal Ledger` developer-mode app | Once per ChatGPT workspace | ChatGPT Settings → Plugins |
| Store the Tunnels-only runtime key and run the client | Once per machine, then automatic runtime injection | OS secret manager; process environment only while the client starts |
| Bind the tunnel to the current planning mode or exact review packet | Planning start or once per review round | A local `tunnel-client` profile and running process |

The ChatGPT app is not recreated for every goal. It stays attached to the same `tunnel_id`. What changes per review is the local stdio command behind that tunnel. Goal Ledger prints that command, and a new profile binds it to exactly one goal, stage, and round.

Use only one active Goal Ledger client profile for a tunnel during personal operation. Stop the planning profile before starting a review-bound profile, and stop the review profile after the response is stored.

## Runtime requirements

The bridge uses the official Python MCP SDK and the OpenAI Secure MCP Tunnel client:

- Python 3.11 or newer;
- `mcp>=1.27,<2` in the Python runtime that launches the skill;
- current `tunnel-client` when ChatGPT must reach the private server;
- a Platform tunnel ID and runtime API key;
- ChatGPT developer mode and Tunnels Read + Use permission.

The permission layers are independent:

- creating or editing a tunnel requires **Tunnels Read + Manage** in the selected Platform organization;
- running `tunnel-client` and selecting the tunnel while creating the ChatGPT app require **Tunnels Read + Use**;
- ChatGPT developer mode is a separate account or workspace permission;
- Enterprise and Education users may need a ChatGPT workspace administrator plus a Platform organization owner or RBAC administrator.

For a personal account, select the personal Platform organization belonging to that account and associate the tunnel with the ChatGPT workspace in which the app will be used. A tunnel associated only with a Platform organization may not appear in a different ChatGPT workspace.

Check the bundled server without contacting ChatGPT:

```bash
python3 scripts/run_review_bridge.py check
```

Check a prepared round and require the tunnel client:

```bash
python3 scripts/run_review_bridge.py check \
  --goal-dir docs/goals/<goal-slug> \
  --stage plan --round 1 \
  --require-tunnel-client
```

Never write an API key, tunnel credential, or bearer token into the goal ledger, generated command, submission metadata, dashboard, or Git.

## Automatic Codex-driven setup

Prefer the installer-owned bootstrap when the user authorizes the review bridge:

```bash
python3 scripts/install_skill.py --with-agents --with-review-bridge
```

The first run installs the skill, checks the machine, and tells the active Codex task to continue account setup. Codex must perform the remaining sequence in the same task instead of handing the user a wall of terminal commands:

1. Check `tunnel-client`, the Python MCP runtime, the existing tunnel profile, Keychain, managed runtime, and any recorded ChatGPT app connection.
2. On macOS, use Safari first because it can reuse the owner's authenticated ChatGPT and Platform sessions; use Chrome if Safari is unavailable. On Windows or Linux, use Chrome. Never try to control the ChatGPT desktop/classic app from Codex.
3. Create or select one private Platform tunnel associated with the intended personal organization and ChatGPT workspace.
4. Prepare a restricted runtime key with **Tunnels Read + Use** and every non-tunnel permission—model, file, vector-store, prompt, dataset, fine-tuning, assistant, thread, eval, and media—set to **None**. Ask for action-time confirmation immediately before creating the key.
5. Do not add API credits or a billing method. The key authenticates `tunnel-client` to the tunnel control plane; it is not used for model inference. GPT Pro work continues to use the owner's ChatGPT subscription and its normal usage limits.
6. On macOS, copy the one-time key, then run the bootstrap so it stores the value in login Keychain, clears the clipboard, creates the profile, runs `doctor`, and starts the managed runtime:

   ```bash
   python3 scripts/install_skill.py --replace --with-review-bridge \
     --review-bridge-tunnel-id tunnel_0123456789abcdef \
     --review-bridge-key-from-clipboard
   ```

   The Keychain service name is `codex-goal-ledger-tunnel-client`. The raw key must never appear in the command, profile, installer output, ledger, or Git.
7. Verify `process_running`, `healthy`, and `ready` are all true before opening ChatGPT app creation.
8. Open ChatGPT **Settings → Security and login**. Ask for action-time confirmation immediately before enabling Developer mode.
9. Open <https://chatgpt.com/plugins>, create `Codex Goal Ledger`, select **Tunnel**, select the existing Goal Ledger tunnel, choose **No Auth**, acknowledge the private-app warning, and connect it. Do not publish it.
10. If ChatGPT's first discovery pass stops the managed runtime or leaves Create spinning, rerun `setup_review_bridge.py start`, verify ready, and refresh the existing creation page. Do not create a second tunnel, key, or app.
11. Verify ChatGPT visibly says `Connected to Codex Goal Ledger` and discovers the five bounded tools. Record the connector only after that visible proof:

   ```bash
   python3 scripts/setup_review_bridge.py record-chatgpt-app \
     --tunnel-id tunnel_0123456789abcdef \
     --connector-id asdk_app_0123456789abcdef
   python3 scripts/setup_review_bridge.py check --require-chatgpt-app
   ```

All local operations are idempotent. A later install reuses the Keychain item, tunnel, app record, profile, and managed runtime. Account mutations are never silent: key creation and Developer mode/app connection remain explicit confirmation points.

## Detailed one-time setup

### 1. Confirm the local Goal Ledger runtime

Run from the installed skill directory or replace the path with the repository checkout while developing:

```bash
GOAL_LEDGER_SKILL="${CODEX_HOME:-$HOME/.codex}/skills/codex-goal-ledger"
python3 "$GOAL_LEDGER_SKILL/scripts/run_review_bridge.py" check
python3 "$GOAL_LEDGER_SKILL/scripts/run_review_bridge.py" print-command
```

The first command must report `Goal Ledger MCP App runtime is ready.` The second prints an unbound planning-mode stdio command. It contains local executable and skill paths, but no API key or tunnel credential.

If the Python check fails, use a Python 3.11-or-newer environment and install the official MCP SDK into that same environment:

```bash
python3 -m pip install 'mcp>=1.27,<2'
```

Re-run the check with the exact Python interpreter that will appear in the printed stdio command.

### 2. Install the official `tunnel-client`

Use the download supplied by [OpenAI Platform tunnel settings](https://platform.openai.com/settings/organization/tunnels) or the matching asset from the [latest `openai/tunnel-client` release](https://github.com/openai/tunnel-client/releases/latest). Do not pin this runbook to an old release URL.

1. Download the archive for the machine's operating system and CPU architecture.
2. Download `SHA256SUMS.txt` from the same release.
3. Verify the archive before extracting it.
4. Put the `tunnel-client` executable on `PATH`.

macOS example after downloading the correct archive and extracting it:

```bash
shasum -a 256 /path/to/downloaded-archive
mkdir -p "$HOME/.local/bin"
install -m 0755 /path/to/tunnel-client "$HOME/.local/bin/tunnel-client"
tunnel-client --version
tunnel-client help quickstart
```

Linux uses the same flow; `sha256sum` may be available instead of `shasum -a 256`.

Windows PowerShell example:

```powershell
Get-FileHash C:\path\to\downloaded-archive -Algorithm SHA256
New-Item -ItemType Directory -Force "$HOME\bin" | Out-Null
Copy-Item C:\path\to\tunnel-client.exe "$HOME\bin\tunnel-client.exe"
& "$HOME\bin\tunnel-client.exe" --version
& "$HOME\bin\tunnel-client.exe" help quickstart
```

Add the chosen directory to the user's `PATH` if a new terminal cannot find the executable. Goal Ledger does not require a particular package manager. Homebrew is acceptable if it supplies the official OpenAI binary, but the supported fallback is the Platform download or latest official release rather than an invented formula name.

Then run:

```bash
python3 "$GOAL_LEDGER_SKILL/scripts/run_review_bridge.py" check --require-tunnel-client
```

### 3. Select the correct OpenAI identities before creating anything

You need both a Platform organization and a ChatGPT workspace. They may have similar names but are separate scopes.

1. Open [Platform tunnel settings](https://platform.openai.com/settings/organization/tunnels).
2. Verify the organization selector shows the Platform organization that should own the tunnel.
3. Verify the target ChatGPT workspace—the one in which GPT Pro reviews will run—is known and available for association.
4. If permission is missing, request:
   - **Tunnels Read + Manage** for the person creating the tunnel;
   - **Tunnels Read + Use** for the person running the client and creating the ChatGPT app;
   - ChatGPT developer-mode access from the ChatGPT workspace administrator when applicable.

New role assignments can take time to propagate. Do not recreate tunnels or keys repeatedly while waiting for an administrator-granted role to appear.

### 4. Create the private tunnel

In Platform tunnel settings:

1. Create a tunnel with a recognizable name such as `codex-goal-ledger-local`.
2. Associate it with the Platform organization that owns it.
3. Associate it with the ChatGPT workspace where the `Codex Goal Ledger` app will be created.
4. Keep the association narrow; do not add unrelated organizations or workspaces.
5. Copy the resulting `tunnel_id`. It has the form `tunnel_...` and is an identifier, not the runtime secret.

Store the tunnel ID in a local password-manager note or operator configuration. It may appear in local tunnel profiles, but it should not be added to goal artifacts merely for convenience.

### 5. Create a tunnel runtime API key

Create the key from the **Runtime API keys** area linked by the tunnel setup. Name it narrowly, for example `goal-ledger-tunnel-client`.

Set only **Tunnels Read + Use**. Set every unrelated API category to **None**. Do not add credits for this bridge. Use this runtime key only as `CONTROL_PLANE_API_KEY`. Do not use an organization admin key for the long-running client, and do not expose the value to ChatGPT, Codex chat, the ledger, a shell script committed to Git, or the `--mcp-command` string.

On macOS, prefer the installer bootstrap over a long-lived shell export: copy the newly displayed key once, run `setup_review_bridge.py bootstrap --key-from-clipboard`, and let it save the value to login Keychain and clear the clipboard. The profile still contains only `env:CONTROL_PLANE_API_KEY`; the bootstrap injects the secret into the `doctor` and managed-runtime processes without printing it.

Load it only into the current terminal session.

macOS with zsh:

```zsh
read -s "CONTROL_PLANE_API_KEY?OpenAI tunnel runtime key: "
export CONTROL_PLANE_API_KEY
echo
```

Linux with bash:

```bash
read -rsp 'OpenAI tunnel runtime key: ' CONTROL_PLANE_API_KEY
export CONTROL_PLANE_API_KEY
echo
```

Windows PowerShell 7:

```powershell
$env:CONTROL_PLANE_API_KEY = Read-Host 'OpenAI tunnel runtime key' -MaskInput
```

For unattended use, load the variable from the operating system's secret manager or a permission-restricted secret file supported by `tunnel-client`. Never put the raw key in `goal.md`, `progress.md`, `config.toml`, a tunnel profile, or shell history.

### 6. Create the stable planning profile

Print the unbound planning command:

```bash
python3 "$GOAL_LEDGER_SKILL/scripts/run_review_bridge.py" print-command
```

Copy that entire output. Assign it as one shell value without adding the runtime key:

```bash
MCP_COMMAND='paste the exact print-command output here'
```

Create the named profile, replacing the example tunnel ID with the real one:

```bash
tunnel-client init \
  --sample sample_mcp_stdio_local \
  --profile goal-ledger-planning \
  --tunnel-id tunnel_0123456789abcdef0123456789abcdef \
  --mcp-command "$MCP_COMMAND"

tunnel-client doctor --profile goal-ledger-planning --explain
```

`doctor` must resolve the profile, runtime key, tunnel identity, and local stdio server. If the profile name already exists, inspect it with `tunnel-client profiles list` and use `tunnel-client profiles edit goal-ledger-planning` or create a new, clearly named profile; do not overwrite an unrelated profile blindly.

### 7. Start the client and verify readiness

Keep this command running while connecting ChatGPT:

```bash
tunnel-client run --profile goal-ledger-planning
```

The client opens only an outbound HTTPS connection to OpenAI and starts the Goal Ledger MCP process over local stdio. It does not open a public inbound port.

Use the health and admin URLs printed by the running client. The expected states are:

- `/healthz`: HTTP 200, meaning the client process is alive;
- `/readyz`: HTTP 200, meaning startup checks and downstream MCP readiness succeeded;
- `/ui`: the loopback-only operator dashboard shows the client connected and polling.

Do not expose the local admin UI beyond loopback merely to make setup easier.

### 8. Enable ChatGPT developer mode

In the target ChatGPT workspace:

1. Open ChatGPT on the web.
2. Go to **Settings → Security and login**.
3. Turn on **Developer mode**.
4. If the toggle is missing or disabled, stop and ask the workspace administrator to permit developer mode. Tunnel permissions alone do not grant it.

### 9. Create the private ChatGPT app

Leave `tunnel-client run --profile goal-ledger-planning` running, then:

1. Open **Settings → Plugins**, or go to <https://chatgpt.com/plugins>.
2. Select the plus button to create a developer-mode app.
3. Choose **Tunnel** for the connection type.
4. Select the Goal Ledger tunnel. If it is not listed, paste the exact `tunnel_id` only if the UI offers that field.
5. Set Authentication to **No Auth**. The OpenAI tunnel is the private transport boundary; the local stdio server has no separate OAuth endpoint.
6. Set the name to `Codex Goal Ledger`.
7. Set the description to `Interactive Goal Ledger planning controls and immutable GPT Pro review packets.`
8. Acknowledge the private, unreviewed-app warning and create the app.
9. Press **Connect** in the final ChatGPT connection dialog.
10. Confirm ChatGPT discovers exactly these five tools:
   - `open_goal_ledger`
   - `get_review_status`
   - `read_review_file`
   - `begin_pro_review`
   - `submit_pro_review_response`

Do not publish the app. This is a private developer-mode connection for the owner or authorized workspace.

### 10. Choose an app permission level

For a personal account, set the `Codex Goal Ledger` app to **Ask before making changes**. That allows read-only packet inspection while keeping submission and response-custody writes confirmable. **Always ask** is also valid when maximum prompting is desired. Workspace administrators may enforce a different default or per-app policy.

The app permission setting is separate from Codex sandbox approvals and separate from Fable's Anthropic export approval.

## Verify the connection

Open a new ChatGPT conversation, attach the `Codex Goal Ledger` app from the composer tool menu, and ask:

```text
Open the Goal Ledger planning controls.
```

Success means:

1. ChatGPT invokes `open_goal_ledger`.
2. The Goal Ledger widget appears.
3. It shows planning mode, six checkboxes, review selectors, and the implementation preset control.
4. The tunnel admin UI remains healthy and ready.
5. No repository path, API key, or arbitrary file tool appears in the tool list.

This verifies only the unbound planning mode. A packet-bound review is separately checked against the exact packet hash when that review is prepared.

If tools or metadata change in a future Goal Ledger release, keep the client running, open **Settings → Plugins → Codex Goal Ledger**, choose **Refresh**, and verify the five-tool boundary again. Normal goal or packet changes do not require an app refresh because the tool definitions stay stable.

## What changes for each review

The durable `tunnel_id` and ChatGPT app stay the same. For every prepared Pro stage and round:

1. stop the currently running planning or prior-round client;
2. use `run_review_bridge.py check` on the exact round;
3. use `run_review_bridge.py print-command` on the exact round;
4. create a uniquely named profile such as `goal-ledger-<slug>-plan-r1` using that command and the existing tunnel ID;
5. run `doctor --explain` for that profile;
6. start that profile and perform the review;
7. stop it after `response-received` is durably stored.

Do not reuse a packet-bound profile for another goal, stage, or round. Keeping the old profile is useful recovery evidence because it retains the exact local command; it contains no runtime API key when configured as documented.

Official setup references:

- <https://developers.openai.com/apps-sdk/deploy/connect-chatgpt>
- <https://developers.openai.com/api/docs/guides/secure-mcp-tunnels>

## Planning controls

Use native `request_user_input` controls first inside Codex Plan mode. Use the MCP App planning widget when Goal Ledger is running in a ChatGPT surface without those controls or when the user explicitly chooses the app.

Print the unbound planning-server command:

```bash
python3 scripts/run_review_bridge.py print-command
```

Configure the tunnel profile with that exact printed command, run `tunnel-client doctor`, then keep `tunnel-client run` healthy. In the ChatGPT conversation, enable the `Codex Goal Ledger` app and ask it to call `open_goal_ledger`.

The widget renders actual checkboxes and bounded selectors. **Use these selections** posts one structured user message into the conversation. Treat that message as the answer to the planning checkpoint, validate the values, and record them in the normal goal artifacts. The planning widget has no filesystem scope and does not modify the ledger itself.

## Run one GPT Pro review

Prepare the normal immutable packet first:

```bash
python3 scripts/run_pro_review.py prepare docs/goals/<goal-slug> \
  --stage plan --round 1 \
  --decision "Approve this plan for implementation." \
  --context-file path/to/operative-plan.md
```

Check it and print the manifest-bound stdio command:

```bash
python3 scripts/run_review_bridge.py check \
  --goal-dir docs/goals/<goal-slug> --stage plan --round 1

python3 scripts/run_review_bridge.py print-command \
  --goal-dir docs/goals/<goal-slug> --stage plan --round 1
```

Use the printed command as the tunnel profile's `--mcp-command`, run `tunnel-client doctor --explain`, then start `tunnel-client run`. Do not substitute a command for another goal, stage, round, or packet.

Example profile creation after assigning the printed command to `MCP_COMMAND`:

```bash
tunnel-client init \
  --sample sample_mcp_stdio_local \
  --profile goal-ledger-example-plan-r1 \
  --tunnel-id tunnel_0123456789abcdef0123456789abcdef \
  --mcp-command "$MCP_COMMAND"

tunnel-client doctor --profile goal-ledger-example-plan-r1 --explain
tunnel-client run --profile goal-ledger-example-plan-r1
```

The example tunnel ID is intentionally invalid for real use. Substitute the existing Goal Ledger tunnel ID, but never substitute another review command after the profile has been used to record submission custody.

In ChatGPT:

1. Start or focus a clean conversation in a visibly selected GPT Pro or Pro Extended mode.
2. Enable the `Codex Goal Ledger` app and call `open_goal_ledger`.
3. Verify the displayed packet digest matches `packet-manifest.json`.
4. Choose the visible Pro label, enter a thread title or URL, and press **Begin exact-packet review**. This records the ready MCP attempt and submission custody.
5. Press **Ask Pro to review now**. The widget posts the exact instruction to read every listed member, obey `START-HERE.md`, and call `submit_pro_review_response` with the complete answer. Every successful `read_review_file` call creates a packet- and member-hash-bound receipt; response submission remains locked until all receipts exist.
6. Wait for the stored state to become `response-received`. If Pro returns the answer but omits the final tool call, paste the complete answer into the widget's manual response fallback once.
7. Stop the round-bound tunnel process after the response is safely stored.
8. Reconcile locally with `run_pro_review.py reconcile`; the bridge never reconciles or approves itself.

## Credential and data handling

The trust boundary is easiest to audit when these values stay separate:

| Value | Secret? | Where it may live | Where it must not live |
| --- | --- | --- | --- |
| `tunnel_id` | Identifier, not an API secret | Local tunnel profile, password-manager note | Unnecessary goal prose or screenshots |
| `CONTROL_PLANE_API_KEY` | Yes | Process environment or OS secret manager | Git, goal files, ChatGPT, Codex chat, dashboard, `--mcp-command` |
| Goal Ledger stdio command | No secret by design | Tunnel profile and local recovery notes | Public docs when it contains personal local paths |
| `context-packet.zip` | Potentially private review data | Exact Pro evidence round and tunnel tool responses | Unscoped public endpoint or unrelated app |
| Pro response | Potentially private review data | Immutable round evidence and local reconciliation | A second transport or unrelated conversation |

The runtime API key authenticates the local client to the OpenAI tunnel control plane. It is not a ChatGPT subscription credential, does not log ChatGPT in, and must never be embedded in the MCP packet.

Creating or using this restricted tunnel key does not itself invoke a paid model endpoint. Keep API credits disabled and all non-tunnel permissions at None. Model work performed in the connected ChatGPT conversation is governed by the owner's ChatGPT subscription and its normal rate limits.

Goal Ledger's bridge re-verifies the packet SHA-256 and every manifest member before every read. The tunnel transports those allowed MCP requests; it does not expand the server's filesystem authority.

## Fallback and recovery

Before submission, a failed MCP bridge may fall back to the configured browser or owner-handoff lane. Record the failed `mcp-app` attempt with `run_pro_review.py record-attempt`; do not claim that the packet was submitted.

After `submission.json` exists:

- never upload or submit the packet again through Safari, Chrome, or another app;
- restart the identical manifest-bound bridge command;
- `begin_pro_review` reuses an existing MCP submission instead of duplicating it;
- preserve `packet-read-receipts/`; missing or stale receipts prevent response acceptance;
- a byte-identical response retry is accepted, while a different response is rejected;
- continue from `state.json` and the existing ChatGPT conversation.

If the bridge cannot be provisioned because developer mode, tunnel permission, an API key, or `tunnel-client` is unavailable, use `auto-ui` or `owner-handoff`. Do not mark the goal blocked merely because the optional MCP transport is unavailable while another authorized transport remains.

## Troubleshooting

### `tunnel-client` is not found

- Run `tunnel-client --version` in a new terminal.
- Verify the install directory is on `PATH`.
- Run `python3 scripts/run_review_bridge.py check --require-tunnel-client` again.
- Use the Platform download or latest official release if no trusted package-manager entry exists.

### `doctor` says the runtime key is missing

- Load `CONTROL_PLANE_API_KEY` in the same terminal that runs `doctor` and `run`.
- Confirm it is a **runtime API key**, not an organization admin key.
- Do not paste the key into the profile YAML to make the error disappear.

### Platform says tunnel access is required

- Check the selected Platform organization.
- Creating or editing needs Tunnels Read + Manage.
- Running and selecting needs Tunnels Read + Use.
- Ask an organization owner or RBAC administrator to grant the missing role.
- Allow administrator-granted role changes time to propagate before retrying.

### The tunnel is healthy but absent in ChatGPT

- Confirm it is associated with the target ChatGPT workspace, not only the Platform organization.
- Confirm the app creator has Tunnels Read + Use.
- Confirm developer mode is enabled in that same ChatGPT workspace.
- For Enterprise or Education, ask the workspace administrator to check developer-mode and connected-app policy.

### The app exists but its tools are missing or stale

- Keep the correct tunnel profile running and ready.
- Open Settings → Plugins → `Codex Goal Ledger` and choose **Refresh**.
- Verify exactly the five bounded tools listed in the setup section.
- If extra shell or generic filesystem tools appear, stop and remove the incorrect app connection rather than continuing.

### `/healthz` passes but `/readyz` fails

- Run `tunnel-client doctor --profile <name> --explain`.
- Verify the printed Python executable and Goal Ledger script still exist.
- Run the exact stdio command directly; it should stay running as an MCP server rather than exit with an import or packet error.
- For a review profile, rerun `run_review_bridge.py check` against the exact goal, stage, and round.

### A review packet changed after the profile was created

- Do not bypass the hash failure.
- If submission has not occurred, prepare the intended packet again, print a new command, and create a new profile.
- If `submission.json` exists, preserve the submitted packet and recover only with its identical profile and bytes. A revised packet is a new review round.

### The client stopped while Pro was answering

- Restart the identical packet-bound profile.
- Reopen the same ChatGPT conversation.
- Do not call `begin_pro_review` through another transport.
- Record the response only once; a byte-identical retry is safe, while a different response is rejected.

### App creation spins and the managed runtime disappears

- Run `python3 scripts/setup_review_bridge.py start`.
- Require `process_running`, `healthy`, and `ready` before continuing.
- Refresh the existing ChatGPT creation URL. If it contains an `asdk_app_...` connector id, creation already succeeded; complete the Connect dialog rather than creating another app.
- Record the connector only after ChatGPT visibly reports `Connected to Codex Goal Ledger` and lists the bounded actions.

### No developer mode, tunnel permission, or runtime key is available

Select `auto-ui` or the checksum-bound owner handoff before submission. MCP availability is a transport capability, not a scientific gate, and must not block an otherwise authorized review route.

## Validation

Run:

```bash
python3 scripts/run_review_bridge.py check
python3 scripts/setup_review_bridge.py check --require-chatgpt-app
python3 scripts/test_review_bridge.py
python3 scripts/test_setup_review_bridge.py
python3 scripts/test_pro_review.py
python3 scripts/run_pro_review.py check docs/goals/<goal-slug>
```

The bridge is ready only when:

- the tool list contains exactly the bounded Goal Ledger tools and no shell or generic file tools;
- the widget resource uses `text/html;profile=mcp-app`;
- packet tampering and unlisted member paths fail;
- an MCP submission records transport `mcp-app` and the exact packet hash;
- a complete response is immutable and remains subject to normal local reconciliation and review gates.
