# Changelog

## 0.3.0 — 2026-10-21

### Research

- Open an anomaly in Signals to trace the current and prior values, formulas, raw calculation inputs, exact SEC sources, and related movements. Optional retrieval selects period-matched annual filing passages and identifies missing management discussion explicitly.
- Record your own hypotheses, judge them supported, contradicted, or unresolved, attach source snapshots and notes, and export the investigation to Markdown. Reviews are stored locally against the exact evidence trail. No AI is required and passages do not establish causation.
- Explore reported-value revisions in Accounting Time Machine, including reversion trails and calculated effects on cash flow, growth, and margins.
- Review quarterly history and inspect TTM inputs. Missing or incompatible quarters leave totals unavailable. Compare two to four peers using a shared reporting end-year and exact fiscal dates.
- Compare up to five financial accounts on a chart, with separate dollar, percentage, and multiple scales.
- Improve loading/error feedback, source disclosures, keyboard navigation, narrow-window behavior, and reduced-motion support.

### Security and privacy

- Restrict the optional Streamlit source interface to 127.0.0.1 in configuration, launcher, and documented commands. Previously its default listener could expose credential-backed operations to reachable network clients. The native Mac API already used loopback and a per-launch token.
- Raise security minimums for certifi, Pillow and urllib3; update the development pytest requirement and release-build pip. The reviewed release environment has no known Python advisories; the full JavaScript audit, including development tools, is clean after updating Vite and source-map-js. RustSec reports no security vulnerabilities; maintenance notices and a Linux-only GLib unsoundness warning remain in the cross-platform lockfile. The withdrawn yoke-derive version was updated.
- Constrain investigation export to a fixed application folder, safe Markdown basenames, a 2 MB limit, and a unique new file.
- Clarify model-discovery network requests, trusted provider endpoint overrides, and separate locations for cache, reviews, exports, and keys.
- Package from committed source in a fresh staging folder and check the exact download for personal settings, cache, key paths, and developer paths.

### Distribution

Apple Silicon, macOS 14 or later. Preview build with an ad hoc signature; not notarized by Apple. Follow the first-launch instructions in the desktop guide. Existing app data is preserved when replacing the application.
