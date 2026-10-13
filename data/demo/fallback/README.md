# Recorded demo fallback

Actual synthetic offline run, mock LLM, native local HTTP ingestion and docs PRs. Open explorer-baseline.html, explorer-stale.html or explorer.html locally. In Word, use All Markup on redline-sstr.docx. These are drafts with human decisions pending; no tenant deployment or live service success is claimed.

index.json records the source run and every payload SHA256. The audit ZIP has its own exhaustive SHA256SUMS and immutable evidence snapshots. Ended mock source URLs may be unavailable; cite IDs/revisions and source snapshots instead. The support rate here is a mock lexical check; the reviewer's live unsupported-code claim observation is attributed separately in docs/REVIEW.md.

Run `uv run python tools/check_demo_pack.py` to verify hashes, judging links, the actual tracked Word insertions/deletions and audit ZIP. To refresh after an approved offline rehearsal: `uv run python tools/freeze_demo.py out/demo-rehearsal.log`. Do not overwrite fallbacks from a failed or paid run.
