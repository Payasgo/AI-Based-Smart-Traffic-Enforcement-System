# Release Readiness Checklist

Use this checklist before creating a GitHub Release or distributing an installer.

## Version and source

- [ ] Confirm the intended pull requests are merged into `master`.
- [ ] Confirm the release commit SHA and create an annotated version tag.
- [ ] Confirm the working tree and CI test suite are clean.
- [ ] Confirm Docker build and supported Windows packaging workflows pass.
- [ ] Record Python, OS, dependency and model-weight versions.

## Product claims

- [ ] Describe only features that are present in the tagged commit.
- [ ] Clearly label unvalidated or experimental detectors.
- [ ] Do not claim enforcement-grade accuracy, accident reduction or guaranteed
  evidence integrity without measured independent evidence.
- [ ] Explain that AI outputs require authorized human review.

## Installer and deployment

- [ ] Test install, first launch, camera selection and clean uninstall on a
  clean Windows 10/11 machine.
- [ ] Verify Python/runtime prerequisites and internet requirements.
- [ ] Verify the USB camera and multi-camera configuration examples.
- [ ] Verify logs, evidence directories and permissions.
- [ ] Scan and checksum release binaries and attached archives.

## Safety, privacy and operations

- [ ] Complete dashboard authentication and access-control review.
- [ ] Confirm evidence retention, access, export and deletion procedures.
- [ ] Confirm camera placement authorization and applicable privacy notices.
- [ ] Verify local jurisdictional rules and obtain required approvals.
- [ ] Confirm there is no unauthorized automatic challan submission.

## Release assets and notes

- [ ] Attach the tested installer and/or source deployment archive.
- [ ] Include SHA-256 checksums for downloadable assets.
- [ ] Link setup, calibration, limitations and troubleshooting documentation.
- [ ] State known limitations, tested hardware and test results.
- [ ] Provide a rollback path to the previous known-good version.

## Release classification

Choose one and state it clearly in the release notes:

- **Prototype/development:** intended for testing and evaluation; not for
  automatic enforcement.
- **Pilot:** limited, authorized and supervised field evaluation with documented
  acceptance criteria.
- **Production:** only after all applicable technical, security, legal and
  operational sign-offs.
