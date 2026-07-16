"""Shared rich-text configuration for ``ProseEditorField`` usages.

Centralising the extension set keeps every editable body (About section,
project case studies) on the same allow-list, and — because ``sanitize=True``
derives its nh3 clean-up rules from exactly these extensions — guarantees the
stored HTML can never contain a tag the editor itself cannot produce.
"""

RICH_TEXT_EXTENSIONS: dict[str, bool | dict[str, object]] = {
    "Bold": True,
    "Italic": True,
    "Underline": True,
    "Strike": True,
    "Heading": {"levels": [2, 3, 4]},
    "BulletList": True,
    "OrderedList": True,
    "ListItem": True,
    "Blockquote": True,
    "HorizontalRule": True,
    "Link": {"enableTarget": True},
}
