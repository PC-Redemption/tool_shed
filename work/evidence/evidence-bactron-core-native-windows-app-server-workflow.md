# Bactron Core native Windows App Server workflow evidence

Date: 2026-08-25
Campaign: prove-bactron-core-native-windows-app-server-workflow
Gate: G4-WINDOWS-INSTALLED-WORKS
Result: passed

Bactron Core on the work PC is using the released Tool Shed v0.29.4 snapshot. Snapshot integrity is verified for content commit `8777b54f07cb04833d7b60ad1602ceab3576e787`; installed-skill synchronization reported the user skill current and unchanged.

Without PATH preparation, the project-scoped selector resolved the normal GUI-provided executable:

- path: `C:\Users\jong.SHELDONMFG\.vscode\extensions\openai.chatgpt-26.818.61809-win32-x64\bin\windows-x86_64\codex.exe`
- version: `0.149.0-alpha.4.3`
- SHA-256: `21f44f04e70d41d011268863d5109f5d7fc2862c14f390083e39ca3398b5ca47`
- qualification: exact project-reviewed workspace-write qualification
- authentication: ChatGPT
- model route: `gpt-5.6-terra`, medium reasoning, no API fallback

Core Campaign 017 used a preparation manifest with exactly two fresh declared paths: one Markdown target and one PNG target sourced from an existing product asset. One normal direct dispatcher run from the logged-in Windows console produced:

- journal final state `verified`, safe true
- one modified text file and one created PNG; no deleted or unexpected paths
- one deterministic verification command, passed once with exit code 0
- identical source and target PNG SHA-256 `e705cbb4eec0604f52312543918897c000a12234b455d7a0ab4276c27bef2e34`
- two model turns and two worker tool calls
- 38,324 input tokens, of which 29,184 were cached; 379 output; 73 reasoning output; 38,703 total
- weighted usage proxy 14,332.4 units
- 11.500 seconds model time, 12.343 seconds CAMP time, 13.031 seconds total dispatch
- zero dispatcher model tokens and no nested Codex execution

The direct path used 95.71% fewer input tokens than the 893,723-token nested-wrapper fixture. Campaigns 015 and 016 recorded the SSH-session sandbox and post-turn verification transport boundaries without replay after mutation; Campaign 017 is the fresh passing proof. Campaign 013 was not replayed and Bactron was not deployed.

A post-proof doctor rerun found no errors after deterministic index repair: snapshot integrity verified, indexes fresh, campaign/work state reconciled, and workspace boundary healthy. Remaining warnings are the intentional tracked PNG evidence and four pre-existing legacy external-evidence annotations unrelated to this campaign.
