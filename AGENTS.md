# Project Guidelines: Shorekeeper Sanctuary Blog

## System Architecture
- **Framework:** Halo 2.26.0 running in Docker Compose with PostgreSQL and Caddy.
- **Theme:** `theme-moesora` (custom anime/aesthetic blog theme).
- **Domain:** `https://shore-keeper.com` / local port `8090`.

## Publishing Policy
- **NEVER** manually inject raw records into the PostgreSQL database without complete CRD metadata.
- **ALWAYS** publish posts using the dedicated REST API tool:
  `python3 scripts/halo_publisher.py sync posts/<file.md>`
- **Styling Guide:** Follow `.gemini/rules/blog_style_guide.md` and `templates/lore_template.md` for consistent aesthetic formatting.
