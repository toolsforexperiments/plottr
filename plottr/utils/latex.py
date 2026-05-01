"""
plottr.utils.latex — Lightweight LaTeX-to-HTML conversion for plot labels.

Converts common LaTeX notation used in physics labels into HTML that Qt's
rich text renderer can display (for pyqtgraph axis labels, titles, etc.).

Uses ``unicodeit`` for Greek letters and math symbols, then converts
subscript/superscript braces to HTML ``<sub>``/``<sup>`` tags.
"""
import re

import unicodeit


_LATEX_INDICATOR = re.compile(
    r'\\[a-zA-Z]'   # backslash command  (\alpha, \frac, …)
    r'|\$'           # dollar-sign math delimiter
    r'|_\{'          # braced subscript   _{...}
    r'|\^\{'         # braced superscript ^{...}
)


def latex_to_html(text: str) -> str:
    """Convert LaTeX-like notation in *text* to HTML suitable for Qt rich text.

    The conversion is only applied when the string contains recognisable LaTeX
    syntax — backslash commands (``\\alpha``), dollar-sign delimiters
    (``$…$``), or braced sub/superscripts (``_{…}``, ``^{…}``).  Plain text
    with ordinary underscores (e.g. ``gate_voltage``) passes through unchanged.

    Handles:
    - Greek letters: ``\\alpha`` → α, ``\\Omega`` → Ω, etc. (via unicodeit)
    - Math symbols: ``\\hbar`` → ℏ, ``\\partial`` → ∂, ``\\infty`` → ∞, etc.
    - Subscripts: ``V_{gate}`` → ``V<sub>gate</sub>``
    - Superscripts: ``x^{2}`` → ``x<sup>2</sup>``
    - Fractions: ``\\frac{dI}{dV}`` → ``dI/dV``
    - Square root: ``\\sqrt{x}`` → ``√x``
    - Dollar-sign math delimiters are stripped: ``$...$`` → contents

    :param text: input string, possibly containing LaTeX notation.
    :returns: HTML string suitable for Qt ``setHtml()`` or pyqtgraph labels.
    """
    if not text:
        return text

    # Only enter the conversion pipeline when the string looks like LaTeX.
    if not _LATEX_INDICATOR.search(text):
        return text

    s = text

    # Strip dollar-sign math delimiters
    s = re.sub(r'\$([^$]*)\$', r'\1', s)

    # Convert \frac{a}{b} -> a/b
    s = re.sub(r'\\frac\{([^}]*)\}\{([^}]*)\}', r'\1/\2', s)

    # Convert \sqrt{x} -> √x
    s = re.sub(r'\\sqrt\{([^}]*)\}', '\u221a\\1', s)

    # Convert \overline{x} -> x̅, \bar{x} -> x̅
    s = re.sub(r'\\(?:overline|bar)\{([^}]*)\}', '\\1\u0305', s)

    # Convert braced subscripts and superscripts to HTML BEFORE unicodeit,
    # so unicodeit doesn't turn them into Unicode sub/superscript chars.
    # Only braced forms (_{...}, ^{...}) — bare underscores are left alone.
    s = re.sub(r'_\{([^}]*)\}', r'<sub>\1</sub>', s)
    s = re.sub(r'\^\{([^}]*)\}', r'<sup>\1</sup>', s)

    # Apply unicodeit for Greek letters and math symbols.
    s = unicodeit.replace(s)

    return s
