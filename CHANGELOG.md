# Changelog

## Unreleased

- Unit format 1, specified in `docs/UNIT-1.md`: a strict subset of TOML 1.0, one file per unit, every key with
  its type and default, the keys reserved for later and refused by name, the directories, overrides and
  drop-ins, the stages, and the words of every finding.
- `alpha check [--root DIR] [FILE.unit ...]` reads and checks a root's units, or a package's units in their
  place among them, and prints every finding with its file and line, and a count.
- The repository's tools and CI: the toolchain pinned by digest (wolf 0.2.40, lupin 0.1.62, wolf-std
  `c339a471`), builds on both of wolf's compiled tiers, wolf tests on three machines, golden cases compared
  byte for byte, a public-text check, and a tiered workflow on Linux and macOS.
- `alpha --help` and `alpha --version`; any other word is a usage error, named on standard error with exit
  status 2.
