# Changelog

## Unreleased

- The repository's tools and CI: the toolchain pinned by digest (wolf 0.2.40, lupin 0.1.62, wolf-std
  `c339a471`), builds on both of wolf's compiled tiers, wolf tests on three machines, golden cases compared
  byte for byte, a public-text check, and a tiered workflow on Linux and macOS.
- `alpha --help` and `alpha --version`; any other word is a usage error, named on standard error with exit
  status 2.
