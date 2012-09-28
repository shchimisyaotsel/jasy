#
# Jasy - Web Tooling Framework
# Copyright 2010-2012 Zynga Inc.
#

import re
import jasy.core.Console as Console

from pygments import highlight
from pygments.formatters import HtmlFormatter
from pygments.lexers import get_lexer_by_name

try:
    import misaka

    misakaExt = misaka.EXT_AUTOLINK | misaka.EXT_NO_INTRA_EMPHASIS | misaka.EXT_FENCED_CODE
    misakaRender = misaka.HTML_SKIP_STYLE | misaka.HTML_SMARTYPANTS

    def markdown2html(markdownStr):
        return misaka.html(markdownStr, misakaExt, misakaRender)

    supportsMarkdown = True

except:

    def markdown2html(markdownStr):
        return None

    supportsMarkdown = False


# By http://misaka.61924.nl/#toc_3
codeblock = re.compile(r'<pre(?: lang="([a-z0-9]+)")?><code(?: class="([a-z0-9]+).*?")?>(.*?)</code></pre>', re.IGNORECASE | re.DOTALL)

def code2highlight(html, tabsize=2):

    def unescape(html):
        html = html.replace('&lt;', '<')
        html = html.replace('&gt;', '>')
        html = html.replace('&amp;', '&')
        html = html.replace('&quot;', '"')
        return html.replace('&#39;', "'")

    def replace(match):
        language, classname, code = match.groups()
        if language is None:
            language = classname if classname else "javascript"
    
        lexer = get_lexer_by_name(language, tabsize=tabsize)
        formatter = HtmlFormatter(linenos="table")
    
        code = unescape(code)

        # for some reason pygments escapes our code once again so we need to reverse it twice
        return unescape(highlight(code, lexer, formatter))
    
    return codeblock.sub(replace, html)
