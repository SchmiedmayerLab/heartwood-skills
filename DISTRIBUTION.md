<!--

This source file is part of the Heartwood Skills open-source project

SPDX-FileCopyrightText: 2026 Schmiedmayer Lab at Stanford University

SPDX-License-Identifier: MIT

-->

# Catalog Distribution

The repository produces deterministic Agent Skill targets; a deployment publishes them through a separately administered TUF repository.
Heartwood does not trust a Git branch, workflow artifact, archive URL, or GitHub attestation as a Skill update channel.

## Release Boundary

1. Merge the Skill change through protected `main` after repository validation and code-owner review.
2. Run **Build Catalog Candidate** with the full merged commit.
3. Confirm that the workflow rebuilt the catalog, reran the complete suite, and produced a GitHub build-provenance attestation.
4. Import that exact candidate into a TUF signing event.
5. Publish the resulting metadata and content-addressed targets over HTTPS.
6. Verify the deployed repository with a clean Python-TUF client before adding or updating a Heartwood deployment source.

The candidate workflow does not sign or publish by itself.
This keeps repository write access separate from the update root of trust.

## Signing Roles

Use the upstream [TUF-on-CI](https://github.com/theupdateframework/tuf-on-ci) workflows and signing tools instead of maintaining a repository-specific signer.
Keep root keys offline and use a signature threshold appropriate for the maintainer group.
Store online snapshot and timestamp keys in an approved KMS or HSM-backed service with GitHub OpenID Connect authorization and a protected publication environment.
Targets metadata changes require the same reviewed candidate identity and full commit used by the catalog build.

The initial root ceremony records the role keys, thresholds, expiry windows, and repository endpoints.
Distribute the resulting root file to Heartwood deployments through a channel independent of the hosted TUF repository.

## Revocation

`revocations.toml` identifies a withdrawal by Skill name and exact complete-tree digest.
After review, rebuild the candidate and publish newer signed targets, snapshot, and timestamp metadata.
Heartwood applies the signed revocation during refresh and rechecks it before an installed catalog Skill is exposed to OpenHands.

Metadata and target retention must allow clients with an older trusted root to complete the TUF update sequence.
Do not delete historical root versions required for rotation.
