"""Build hooks for the documentation site.

Wired in through `hooks:` in mkdocs.yml, so a local `mkdocs serve` and the CI
build behave identically. A fix that only runs in the deploy workflow is a fix
nobody can reproduce.
"""

from __future__ import annotations

import shutil
from pathlib import Path


def on_post_build(config, **kwargs) -> None:
    """Put the sitemap in every directory that holds a page.

    Material fetches a sitemap for every `<link rel="alternate">` on the page,
    resolved RELATIVE to that alternate's own URL:

        kt = (e) => En(new URL("sitemap.xml", e))

    The i18n plugin emits one alternate per locale, pointing at THE SAME PAGE
    in that locale. So on the home page the browser asks for
    `zh-TW/sitemap.xml`; on `/journey/` it asks for `journey/sitemap.xml`,
    `zh-TW/journey/sitemap.xml` and `ja/journey/sitemap.xml`. The plugin
    writes one sitemap, at the site root, so all of them 404 on every page
    view. Material swallows the error and carries on, which is why the site
    works and why nothing but a console full of 404s ever said so.

    This walks the built site and copies the sitemap next to every
    `index.html`. The first version of this hook listed the locale roots
    instead, which fixed the three 404s on the home page and left three more
    on every sub-page: a guard that is a list stops being true the moment
    someone adds a page.

    The copies are byte-identical on purpose. Material uses the sitemap to
    learn which URLs belong to the site, and that set is the same whichever
    page asks: the root sitemap already lists all pages in all three
    languages. A per-directory sitemap listing only its own page would be a
    smaller, more plausible-looking file that told Material something less
    true.
    """
    site = Path(config["site_dir"])
    sitemap = site / "sitemap.xml"
    if not sitemap.exists():
        return

    for page in site.rglob("index.html"):
        target = page.parent / "sitemap.xml"
        if not target.exists():
            shutil.copy2(sitemap, target)
