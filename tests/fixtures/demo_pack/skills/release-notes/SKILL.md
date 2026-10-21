---
name: release-notes
description: Writes release notes from the git log since the last tag. Run it by hand with /release-notes before tagging a release.
disable-model-invocation: true
---

# Release notes

1. `git describe --tags --abbrev=0` gives the last tag.
2. Group commits since then into Added, Changed and Fixed.
