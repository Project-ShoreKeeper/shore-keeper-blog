# Shorekeeper Blog Lore & Posting Standards

When generating or publishing articles for `shore-keeper.com`, adhere to the standard established in "Chronicles of the Tethys Deep" and "Resonance of the Luminous Butterfly":

## 1. Structure & HTML Lore Container
Every lore chronicle must be wrapped in a `<div class="lore-article" style="line-height: 1.85; font-size: 16px;">` container.

### Hero Quote Card (Top of Article)
```html
<div style="text-align:center; padding: 25px 20px; background: radial-gradient(ellipse at center, rgba(56,189,248,0.12) 0%, rgba(129,140,248,0.04) 60%, transparent 80%); border-radius: 16px; border: 1px solid rgba(56,189,248,0.2); margin-bottom: 35px;">
  <h2 style="font-size: 26px; font-weight: 700; color: var(--moe-theme, #38bdf8); margin-bottom: 8px;">✦ Title / Theme ✦</h2>
  <p style="font-style: italic; color: #94a3b8; margin: 0 auto; max-width: 650px;">
    “Poetic excerpt or memorable quote.”
  </p>
</div>
```

### Thematic Sections
- Use Roman numeral headings with atmospheric emojis:
  - `<h2>🌌 I. Title</h2>`
  - `<h2>🦋 II. Title</h2>`
  - `<h2>💠 III. Title</h2>`
  - `<h2>✨ IV. Title</h2>`
- Section dividers: `<hr style="margin: 35px 0; border: 0; border-top: 1px dashed rgba(56,189,248,0.25);" />`
- Dialogue / key quotes: wrap in `<blockquote><p>“...”</p></blockquote>`

## 2. Frontmatter Standards
- `cover`: Default to `"/upload/1379245.jpg"` or a relevant lore illustration.
- `categories`: `[Chronicles]`
- `tags`: Include `Lore`, `Shorekeeper`, and specific sub-themes (e.g. `Black Shores`, `Sanctuary`, `Tethys`).
- `priority`: `1` (or higher if pinned).
- `excerpt`: Must provide a concise, poetic summary rather than auto-generation.

## 3. Publishing Workflow
- Save the markdown file in `posts/<slug>.md`.
- Execute publication via `python3 scripts/halo_publisher.py sync posts/<slug>.md`.
