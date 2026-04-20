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

    # Convert \frac{a}{b} -> a/b (before unicodeit, which doesn't handle it)
    s = re.sub(r'\\frac\{([^}]*)\}\{([^}]*)\}', r'\1/\2', s)

    # Convert \sqrt{x} -> √x
    s = re.sub(r'\\sqrt\{([^}]*)\}', '\u221a\\1', s)

    # Convert \overline{x} -> x̅, \bar{x} -> x̅
    s = re.sub(r'\\(?:overline|bar)\{([^}]*)\}', '\\1\u0305', s)

    # Apply unicodeit for Greek letters and math symbols
    s = unicodeit.replace(s)

    # Convert remaining subscripts: _{...} -> <sub>...</sub>
    # Must come after unicodeit (which handles single-char numeric subscripts)
    s = re.sub(r'_\{([^}]*)\}', r'<sub>\1</sub>', s)
    # Single character subscript without braces (only if not already converted)
    s = re.sub(r'_([a-zA-Z0-9])', r'<sub>\1</sub>', s)

    # Convert remaining superscripts: ^{...} -> <sup>...</sup>
    s = re.sub(r'\^\{([^}]*)\}', r'<sup>\1</sup>', s)
    # Single character superscript without braces
    s = re.sub(r'\^([a-zA-Z0-9])', r'<sup>\1</sup>', s)

    # Clean up any remaining backslashes from unrecognized commands
    # (leave them as-is — better to show \foo than nothing)

    return s
