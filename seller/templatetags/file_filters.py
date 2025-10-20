import json
from django import template
from django.utils.html import escapejs

register = template.Library()


@register.filter
def docs_json(documents):
    """
    Serialize documents queryset to JSON string.
    Each document must have `file` (or url), `name`, and ext extracted from filename.
    """
    docs_list = []
    for doc in documents:
        url = doc.file.url if hasattr(doc, "file") else ""
        name = doc.name if hasattr(doc, "name") else url.split("/")[-1]
        ext = "." + name.split(".")[-1] if "." in name else ""
        docs_list.append(
            {
                "name": name,
                "url": url,
                "ext": ext.lower(),
            }
        )
    return escapejs(json.dumps(docs_list))
