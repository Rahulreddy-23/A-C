# Dataverse schema

Solution prefix `dhf`. JSON columns are multiline text, preserving UTF-8 canonical JSON and arrays. Use application GUID primary keys and the alternate keys below; source IDs remain opaque text. Enable auditing and limit maker/editor access. Never update old evidence revisions in place.

| Table | Alternate key | Required columns | Relationships |
|---|---|---|---|
| Artifact | organization, sourceSystem, canonicalId, revision, contentHash | canonicalId, type, title, body, attributesJson, sourceUrl, retrievedAt UTC, contentHash SHA256, synthetic boolean | SnapshotMember → Artifact; TraceLink src/dst → Artifact revision |
| TraceLink | snapshot, srcCanonicalId, dstCanonicalId, type, origin | evidence, origin (`explicit`, `human_confirmed`, `ai_inferred`) | Snapshot; exact Artifact endpoints |
| EvidenceSnapshot | organization, snapshotNumber | at UTC, status (`building`, `complete`, `failed`), artifactCount, linkCount, canonicalGraphFile, checksum | Members, GenerationRuns |
| SnapshotMember | snapshot, canonicalId | artifact lookup | Snapshot, Artifact revision |
| DocumentSection | run, sectionId | docId, ordinal, mode, entity, query, queryFingerprint, factsJson, claimsJson, citedRevisionsJson, MarkdownFile, exactMarkdown SHA256, status, evidenceStatus, validationJson, promptRefsJson | Run; Proposal basis where relevant |
| GenerationRun | requestId | requestedBy, docId, docVersion, release, sourceSnapshot, templateId/version/hash, paramsJson, provider/model, state, seconds, calls, cacheHits, reservedUsd, settledUsd, manifestFile, MarkdownFile, DocxFile, PR URL | Snapshot, sections, proposals |
| Proposal | run, proposalId | rule L01/L02/L03, subjectId, text, kind=`suggested`, citationsJson, confidence decimal, status (`pending`, `accepted`, `rejected`), reviewer, rationale | Run, source Artifact; does not create a source link |
| DocumentBaseline | docsRepo, docId, tag | commit, approvedManifestFile, MarkdownFile, mergedPrId, reviewerEvidence, sourceSnapshot | latest version is selected by numeric vN, not lexical sort |
| CacheEntry | provider, model, promptId, promptVersion, promptHash, evidenceHash | validatedRawJson, createdAt, outputHash | reusable response; lookup before reserving budget |
| BudgetLedger | provider | spentUsd, outstandingReservedUsd, buildCapUsd=1.50, hardCapUsd=4.00, rowVersion | BudgetReservation and serialized generation queue |
| BudgetReservation | requestId, sectionId, chunkNumber | provider, upperInputTokens, maxOutputTokens, reservedUsd, actualUsd nullable, state | ledger; retain reservation after ambiguous provider failure |

Dataverse alternate keys cannot replace SHA256 canonicalization. Use the approved canonical/hash boundary below or store a separately verified canonical input plus hash; do not substitute a timestamp or random GUID for a content hash.

Snapshot commit protocol: create a `building` snapshot, normalize all evidence into immutable revisions, insert all membership and confirmed links, reject missing endpoints/duplicate canonical IDs, compare counts, then mark `complete`. Consumers select only complete snapshots. Keep deletions as absent membership, not destructive removal of Artifact history. A failed ingest must leave the prior complete snapshot active.

Budget protocol: place GenerationRun in a provider-specific serialized queue (concurrency 1). Read ledger with row version, reserve worst-case input/output cost, update ledger conditionally; conflicting updates retry the transaction, not a provider request. Before reservation check run cap 0.25, build cap 1.50, total spent plus reservations below 4.00. Cache hits do not reserve funds. Settle using provider usage; if usage is unavailable keep the conservative reservation. Disable retries on refused/truncated drafting calls.

The USD fields above describe the reference API ledger and are **not** the BD tenant's Copilot Credit meter. The four-table [day-1 MVP CSV](day1/mvp_columns.csv) records estimated prompt credits on GenerationRun; one operator checks Monitor after each run. M16 adds a separate serialized Copilot Credit ledger with a default 400-credit local cap and tenant-reported model/tokens. Do not infer native budget concurrency parity from a USD balance.
