"""
plottr.utils.latex — Lightweight LaTeX-to-HTML conversion for plot labels.

Converts common LaTeX notation used in physics labels into HTML that Qt's
rich text renderer can display (for pyqtgraph axis labels, titles, etc.).

Uses ``unicodeit`` for Greek letters and math symbols, then converts
subscript/superscript braces to HTML ``<sub>``/``<sup>`` tags.
"""
import re

import unicodeit


def latex_to_html(text: str) -> str:
    """Convert LaTeX-like notation in *text* to HTML suitable for Qt rich text.

    Handles:
    - Greek letters: ``\\alpha`` → α, ``\\Omega`` → Ω, etc. (via unicodeit)
    - Math symbols: ``\\hbar`` → ℏ, ``\\partial`` → ∂, ``\\infty`` → ∞, etc.
    - Subscripts: ``V_{gate}`` → ``V<sub>gate</sub>``, ``g_{11}`` → ``g<sub>11</sub>``
    - Superscripts: ``x^{2}`` → ``x<sup>2</sup>``, ``x^2`` → ``x<sup>2</sup>``
    - Fractions: ``\\frac{dI}{dV}`` → ``dI/dV``
    - Square root: ``\\sqrt{x}`` → ``√x``
    - Dollar-sign math delimiters are stripped: ``$...$`` → contents

    The function is idempotent on plain text (no LaTeX) and safe to call on
    any string — if it contains no LaTeX commands, it passes through unchanged.

    :param text: input string, possibly containing LaTeX notation.
    :returns: HTML string suitable for Qt ``setHtml()`` or pyqtgraph labels.
    """
    if not text:
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

    # Convert subscripts and superscripts to HTML BEFORE unicodeit,
    # so unicodeit doesn't turn them into Unicode sub/superscript chars.
    # Braced: _{...} -> <sub>...</sub>, ^{...} -> <sup>...</sup>
    s = re.sub(r'_\{([^}]*)\}', r'<sub>\1</sub>', s)
    s = re.sub(r'\^\{([^}]*)\}', r'<sup>\1</sup>', s)
    # Single character: _x -> <sub>x</sub>, ^x -> <sup>x</sup>
    s = re.sub(r'_([a-zA-Z0-9])', r'<sub>\1</sub>', s)
    s = re.sub(r'\^([a-zA-Z0-9])', r'<sup>\1</sup>', s)

    # Apply unicodeit for Greek letters and math symbols.
    # Runs after sub/sup conversion so it processes content inside tags too.
    s = unicodeit.replace(s)

    return s
