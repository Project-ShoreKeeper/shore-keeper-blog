#!/usr/bin/env python3
"""
Halo 2 Native API Publisher for Shorekeeper Blog
Handles post creation, drafts, publishing, tag/category resolution, and markdown sync.
"""

import os
import sys
import json
import re
import argparse
import urllib.request
import urllib.parse
import urllib.error
from pathlib import Path
from typing import List, Dict, Optional, Any, Tuple

# Load environment variables from .env if present
def load_env(env_path: Optional[Path] = None):
    if env_path is None:
        env_path = Path(__file__).resolve().parent.parent / ".env"
    if env_path.exists():
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                k = k.strip()
                v = v.strip().strip("'\"")
                if k not in os.environ:
                    os.environ[k] = v

load_env()

BASE_URL = os.environ.get("HALO_BASE_URL", "http://127.0.0.1:8090").rstrip("/")
EXTERNAL_URL = os.environ.get("HALO_EXTERNAL_URL", "https://shore-keeper.com").rstrip("/")
PAT = os.environ.get("HALO_PAT", "").strip()


class HaloClient:
    def __init__(self, base_url: str = BASE_URL, token: str = PAT):
        self.base_url = base_url.rstrip("/")
        self.token = token
        if not self.token:
            raise ValueError("Halo PAT (Personal Access Token) is required. Set HALO_PAT in .env or pass token.")

    def _request(self, method: str, path: str, data: Optional[Dict] = None, params: Optional[Dict] = None) -> Any:
        url = f"{self.base_url}{path}"
        if params:
            query = "&".join(f"{urllib.parse.quote(str(k))}={urllib.parse.quote(str(v))}" for k, v in params.items())
            url += f"?{query}"

        body = json.dumps(data).encode("utf-8") if data is not None else None
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }

        req = urllib.request.Request(url, data=body, headers=headers, method=method.upper())
        try:
            with urllib.request.urlopen(req) as resp:
                raw = resp.read().decode("utf-8")
                if raw:
                    try:
                        return json.loads(raw)
                    except json.JSONDecodeError:
                        return raw
                return None
        except urllib.error.HTTPError as e:
            err_msg = e.read().decode("utf-8", errors="ignore")
            raise RuntimeError(f"Halo API Error [{e.code}] {path}: {err_msg}")

    # Tag Operations
    def list_tags(self) -> List[Dict]:
        res = self._request("GET", "/apis/content.halo.run/v1alpha1/tags")
        return res.get("items", []) if isinstance(res, dict) else []

    def get_or_create_tag(self, tag_name: str) -> str:
        """Finds a tag by displayName, slug, or metadata.name, or creates it."""
        tag_name_clean = tag_name.strip()
        slug_candidate = re.sub(r"[^a-zA-Z0-9_-]+", "-", tag_name_clean.lower()).strip("-") or "tag"
        
        tags = self.list_tags()
        for t in tags:
            spec = t.get("spec", {})
            meta = t.get("metadata", {})
            if (spec.get("displayName", "").lower() == tag_name_clean.lower() or
                spec.get("slug", "").lower() == slug_candidate.lower() or
                meta.get("name", "").lower() == tag_name_clean.lower()):
                return meta.get("name")

        # Create tag
        payload = {
            "apiVersion": "content.halo.run/v1alpha1",
            "kind": "Tag",
            "metadata": {
                "generateName": "tag-",
                "annotations": {
                    "content.halo.run/permalink-pattern": "/tags"
                }
            },
            "spec": {
                "displayName": tag_name_clean,
                "slug": slug_candidate,
                "cover": ""
            }
        }
        res = self._request("POST", "/apis/content.halo.run/v1alpha1/tags", data=payload)
        return res["metadata"]["name"]

    # Category Operations
    def list_categories(self) -> List[Dict]:
        res = self._request("GET", "/apis/content.halo.run/v1alpha1/categories")
        return res.get("items", []) if isinstance(res, dict) else []

    def resolve_category(self, cat_identifier: str) -> Optional[str]:
        """Finds category name (UUID) by displayName, slug, or metadata.name."""
        cats = self.list_categories()
        cat_id_clean = cat_identifier.strip().lower()
        for c in cats:
            spec = c.get("spec", {})
            meta = c.get("metadata", {})
            if (spec.get("displayName", "").lower() == cat_id_clean or
                spec.get("slug", "").lower() == cat_id_clean or
                meta.get("name", "").lower() == cat_id_clean):
                return meta.get("name")
        if cats:
            return cats[0]["metadata"]["name"]
        return None

    # Post Operations
    def list_posts(self, page: int = 1, size: int = 50) -> List[Dict]:
        res = self._request("GET", "/apis/api.console.halo.run/v1alpha1/posts", params={"page": page, "size": size})
        return res.get("items", []) if isinstance(res, dict) else []

    def get_post_by_slug(self, slug: str) -> Optional[Dict]:
        posts = self.list_posts(size=100)
        for item in posts:
            post = item.get("post", {})
            if post.get("spec", {}).get("slug") == slug:
                return post
        return None

    def create_post(
        self,
        title: str,
        content: str,
        slug: Optional[str] = None,
        tags: Optional[List[str]] = None,
        categories: Optional[List[str]] = None,
        cover: str = "",
        publish: bool = True,
        pinned: bool = False,
        priority: int = 0,
        excerpt: str = "",
        allow_comment: bool = True,
        raw_type: str = "markdown"
    ) -> Dict:
        if not slug:
            slug = re.sub(r"[^a-zA-Z0-9_-]+", "-", title.lower()).strip("-")
            if not slug:
                slug = "post"

        tag_names = []
        if tags:
            for t in tags:
                if t and t.strip():
                    tag_names.append(self.get_or_create_tag(t.strip()))

        category_names = []
        if categories:
            for c in categories:
                resolved = self.resolve_category(c.strip())
                if resolved:
                    category_names.append(resolved)
        else:
            default_cat = self.resolve_category("default")
            if default_cat:
                category_names.append(default_cat)

        html_content = markdown_to_html(content)

        payload = {
            "post": {
                "apiVersion": "content.halo.run/v1alpha1",
                "kind": "Post",
                "metadata": {
                    "generateName": "post-"
                },
                "spec": {
                    "title": title,
                    "slug": slug,
                    "allowComment": allow_comment,
                    "visible": "PUBLIC",
                    "publish": False,
                    "pinned": pinned,
                    "priority": priority,
                    "deleted": False,
                    "excerpt": {
                        "autoGenerate": not bool(excerpt),
                        "raw": excerpt
                    },
                    "tags": tag_names,
                    "categories": category_names,
                    "template": "",
                    "cover": cover
                }
            },
            "content": {
                "raw": content,
                "content": html_content,
                "rawType": raw_type
            }
        }

        draft_result = self._request("POST", "/apis/api.console.halo.run/v1alpha1/posts", data=payload)
        post_name = draft_result["metadata"]["name"]

        if publish:
            pub_result = self._request("PUT", f"/apis/api.console.halo.run/v1alpha1/posts/{post_name}/publish")
            return pub_result
        return draft_result

    def publish_post(self, post_name: str) -> Dict:
        return self._request("PUT", f"/apis/api.console.halo.run/v1alpha1/posts/{post_name}/publish")

    def unpublish_post(self, post_name: str) -> Dict:
        return self._request("PUT", f"/apis/api.console.halo.run/v1alpha1/posts/{post_name}/unpublish")

    def delete_post(self, post_name: str) -> Any:
        return self._request("DELETE", f"/apis/content.halo.run/v1alpha1/posts/{post_name}")


def markdown_to_html(md_text: str) -> str:
    """Basic Markdown to HTML converter with code block, table, and list support."""
    lines = md_text.split("\n")
    html_lines = []
    in_code = False
    code_lang = ""
    code_buf = []

    for line in lines:
        if line.startswith("```"):
            if in_code:
                in_code = False
                escaped_code = (
                    "\n".join(code_buf)
                    .replace("&", "&amp;")
                    .replace("<", "&lt;")
                    .replace(">", "&gt;")
                )
                cls = f' class="language-{code_lang}"' if code_lang else ""
                html_lines.append(f"<pre><code{cls}>{escaped_code}</code></pre>")
                code_buf = []
            else:
                in_code = True
                code_lang = line[3:].strip()
            continue

        if in_code:
            code_buf.append(line)
            continue

        if line.startswith("# "):
            html_lines.append(f"<h1>{line[2:]}</h1>")
        elif line.startswith("## "):
            html_lines.append(f"<h2>{line[3:]}</h2>")
        elif line.startswith("### "):
            html_lines.append(f"<h3>{line[4:]}</h3>")
        elif line.startswith("#### "):
            html_lines.append(f"<h4>{line[5:]}</h4>")
        elif line.startswith("> "):
            html_lines.append(f"<blockquote><p>{line[2:]}</p></blockquote>")
        elif line.startswith("- ") or line.startswith("* "):
            html_lines.append(f"<ul><li>{line[2:]}</li></ul>")
        elif line.strip() == "---":
            html_lines.append("<hr />")
        elif line.strip():
            p = line
            p = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", p)
            p = re.sub(r"\*(.+?)\*", r"<em>\1</em>", p)
            p = re.sub(r"`(.+?)`", r"<code>\1</code>", p)
            p = re.sub(r"\[(.+?)\]\((.+?)\)", r'<a href="\2">\1</a>', p)
            html_lines.append(f"<p>{p}</p>")
        else:
            html_lines.append("")

    return "\n".join(html_lines)


def parse_frontmatter(content: str) -> Tuple[Dict[str, Any], str]:
    """Extracts frontmatter metadata from Markdown text."""
    meta = {}
    body = content
    if content.startswith("---"):
        parts = content.split("---", 2)
        if len(parts) >= 3:
            fm_text = parts[1]
            body = parts[2].lstrip("\n")
            for line in fm_text.splitlines():
                line = line.strip()
                if not line or line.startswith("#") or ":" not in line:
                    continue
                k, v = line.split(":", 1)
                k = k.strip()
                v = v.strip().strip("'\"")
                if v.startswith("[") and v.endswith("]"):
                    items = [x.strip().strip("'\"") for x in v[1:-1].split(",") if x.strip()]
                    meta[k] = items
                elif v.lower() == "true":
                    meta[k] = True
                elif v.lower() == "false":
                    meta[k] = False
                elif v.isdigit():
                    meta[k] = int(v)
                else:
                    meta[k] = v
    return meta, body


def main():
    parser = argparse.ArgumentParser(description="Halo 2 Publisher CLI for Shorekeeper")
    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # Command: new
    p_new = subparsers.add_parser("new", help="Scaffold a new lore post markdown template")
    p_new.add_argument("slug", help="Slug for the new post")
    p_new.add_argument("--title", help="Title of the post")

    # Command: create
    p_create = subparsers.add_parser("create", help="Create and optionally publish a post")
    p_create.add_argument("--title", required=True, help="Post title")
    p_create.add_argument("--slug", help="Post slug")
    p_create.add_argument("--file", help="Path to markdown file for content")
    p_create.add_argument("--content", help="Inline markdown text")
    p_create.add_argument("--tags", help="Comma-separated tags (e.g. 'Lore,Shorekeeper')")
    p_create.add_argument("--categories", help="Comma-separated categories")
    p_create.add_argument("--cover", default="", help="Cover image URL")
    p_create.add_argument("--publish", action="store_true", default=True, help="Publish immediately")
    p_create.add_argument("--draft", action="store_false", dest="publish", help="Save as draft only")
    p_create.add_argument("--pinned", action="store_true", help="Pin post to top")
    p_create.add_argument("--priority", type=int, default=0, help="Priority sorting")
    p_create.add_argument("--excerpt", default="", help="Custom excerpt")

    # Command: sync
    p_sync = subparsers.add_parser("sync", help="Publish or sync a Markdown file with frontmatter")
    p_sync.add_argument("file", help="Path to .md file")

    # Command: list
    p_list = subparsers.add_parser("list", help="List recent posts")
    p_list.add_argument("--size", type=int, default=20, help="Number of posts to fetch")

    # Command: delete
    p_del = subparsers.add_parser("delete", help="Delete a post by its metadata.name")
    p_del.add_argument("name", help="Post resource name (e.g. post-xyz)")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    client = HaloClient()

    if args.command == "new":
        slug = args.slug.lower().strip()
        title = args.title or slug.replace("-", " ").title()
        target = Path("posts") / f"{slug}.md"
        if target.exists():
            print(f"⚠️ File already exists: {target}")
            sys.exit(1)
        template_file = Path("templates/lore_template.md")
        if template_file.exists():
            with open(template_file, "r", encoding="utf-8") as tf:
                tmpl = tf.read()
            tmpl = tmpl.replace('title: "Title of the Chronicle"', f'title: "{title}"')
            tmpl = tmpl.replace('slug: "slug-of-the-chronicle"', f'slug: "{slug}"')
        else:
            tmpl = f"---\ntitle: \"{title}\"\nslug: \"{slug}\"\ntags: [Lore, Shorekeeper]\ncategories: [Chronicles]\npublish: true\n---\n\n# {title}\n"
        
        target.parent.mkdir(parents=True, exist_ok=True)
        with open(target, "w", encoding="utf-8") as out:
            out.write(tmpl)
        print(f"✨ Created new post scaffold: {target}")

    elif args.command == "create":
        text = args.content or ""
        if args.file:
            with open(args.file, "r", encoding="utf-8") as f:
                text = f.read()

        tags = [t.strip() for t in args.tags.split(",")] if args.tags else []
        categories = [c.strip() for c in args.categories.split(",")] if args.categories else []

        res = client.create_post(
            title=args.title,
            content=text,
            slug=args.slug,
            tags=tags,
            categories=categories,
            cover=args.cover,
            publish=args.publish,
            pinned=args.pinned,
            priority=args.priority,
            excerpt=args.excerpt
        )
        post_meta = res.get("metadata", {})
        post_spec = res.get("spec", {})
        status = res.get("status", {})
        print(f"✨ Post '{post_spec.get('title')}' created successfully!")
        print(f"   Resource Name : {post_meta.get('name')}")
        print(f"   Phase         : {status.get('phase')}")
        print(f"   Permalink     : {EXTERNAL_URL}{status.get('permalink', '/archives/' + post_spec.get('slug', ''))}")

    elif args.command == "sync":
        p = Path(args.file)
        if not p.exists():
            print(f"❌ File not found: {args.file}")
            sys.exit(1)
        with open(p, "r", encoding="utf-8") as f:
            raw = f.read()
        meta, body = parse_frontmatter(raw)

        title = meta.get("title", p.stem.replace("-", " ").title())
        slug = meta.get("slug", p.stem)
        tags = meta.get("tags", [])
        if isinstance(tags, str):
            tags = [x.strip() for x in tags.split(",")]
        categories = meta.get("categories", [])
        if isinstance(categories, str):
            categories = [x.strip() for x in categories.split(",")]
        cover = meta.get("cover", "")
        publish = meta.get("publish", True)
        pinned = meta.get("pinned", False)
        priority = meta.get("priority", 0)
        excerpt = meta.get("excerpt", "")

        res = client.create_post(
            title=title,
            content=body,
            slug=slug,
            tags=tags,
            categories=categories,
            cover=cover,
            publish=publish,
            pinned=pinned,
            priority=priority,
            excerpt=excerpt
        )
        post_meta = res.get("metadata", {})
        post_spec = res.get("spec", {})
        status = res.get("status", {})
        print(f"✨ Post synced from '{args.file}'!")
        print(f"   Title         : {post_spec.get('title')}")
        print(f"   Resource Name : {post_meta.get('name')}")
        print(f"   Phase         : {status.get('phase')}")
        print(f"   Permalink     : {EXTERNAL_URL}{status.get('permalink', '/archives/' + post_spec.get('slug', ''))}")

    elif args.command == "list":
        posts = client.list_posts(size=args.size)
        print(f"{'TITLE':<45} {'SLUG':<30} {'PHASE':<12} {'RESOURCE NAME'}")
        print("-" * 110)
        for item in posts:
            p = item.get("post", {})
            title = p.get("spec", {}).get("title", "")[:42]
            slug = p.get("spec", {}).get("slug", "")[:28]
            phase = p.get("status", {}).get("phase", "UNKNOWN")
            name = p.get("metadata", {}).get("name", "")
            print(f"{title:<45} {slug:<30} {phase:<12} {name}")

    elif args.command == "delete":
        client.delete_post(args.name)
        print(f"🗑️ Post '{args.name}' deleted successfully.")

if __name__ == "__main__":
    main()
