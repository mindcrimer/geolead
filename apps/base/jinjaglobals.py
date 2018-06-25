from snippets.template_backends.jinja2 import jinjafilter


@jinjafilter
def preprocess_content(content):
    if '<table' not in content:
        return content

    content = content.replace('<table', '<div class="table-wrap"><table')\
        .replace('</table>', '</table></div>')

    return content
