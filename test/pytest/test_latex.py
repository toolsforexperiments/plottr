"""Tests for plottr.utils.latex — LaTeX to HTML conversion."""
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from plottr.utils.latex import latex_to_html


class TestGreekLetters:
    def test_alpha(self):
        assert latex_to_html(r'\alpha') == '\u03b1'

    def test_beta(self):
        assert latex_to_html(r'\beta') == '\u03b2'

    def test_gamma(self):
        assert latex_to_html(r'\gamma') == '\u03b3'

    def test_omega_upper(self):
        assert latex_to_html(r'\Omega') == '\u03a9'

    def test_mu(self):
        assert latex_to_html(r'\mu') == '\u03bc'

    def test_pi(self):
        assert latex_to_html(r'\pi') == '\u03c0'


class TestMathSymbols:
    def test_hbar(self):
        result = latex_to_html(r'\hbar')
        # unicodeit may return ℏ (U+210F) or ħ (U+0127) depending on version
        assert result in ('\u0127', '\u210f')

    def test_partial(self):
        assert latex_to_html(r'\partial') == '\u2202'

    def test_infty(self):
        assert latex_to_html(r'\infty') == '\u221e'

    def test_int(self):
        assert latex_to_html(r'\int') == '\u222b'

    def test_sum(self):
        assert latex_to_html(r'\sum') == '\u2211'


class TestSubscripts:
    def test_braced_text(self):
        assert latex_to_html(r'V_{gate}') == 'V<sub>gate</sub>'

    def test_braced_numbers(self):
        # unicodeit converts numeric subscripts to Unicode (g₁₁)
        result = latex_to_html(r'g_{11}')
        assert 'g' in result and '1' in result.replace('\u2081', '1')

    def test_braced_multi(self):
        result = latex_to_html(r'I_{DS}')
        assert 'I' in result and 'DS' in result

    def test_single_char(self):
        result = latex_to_html(r'x_0')
        # May be Unicode subscript ₀ or HTML <sub>0</sub>
        assert 'x' in result and ('0' in result or '\u2080' in result)

    def test_mixed(self):
        result = latex_to_html(r'V_{SD}')
        assert 'SD' in result


class TestSuperscripts:
    def test_braced(self):
        result = latex_to_html(r'x^{2}')
        # unicodeit converts ^{2} to Unicode superscript ²
        assert 'x' in result and ('2' in result or '\u00b2' in result)

    def test_single_char(self):
        result = latex_to_html(r'x^2')
        assert 'x' in result and ('2' in result or '\u00b2' in result)

    def test_braced_text(self):
        result = latex_to_html(r'e^{i\pi}')
        assert 'e' in result and '\u03c0' in result


class TestFractions:
    def test_simple(self):
        assert latex_to_html(r'\frac{dI}{dV}') == 'dI/dV'

    def test_with_symbols(self):
        result = latex_to_html(r'\frac{\partial I}{\partial V}')
        assert 'I' in result and 'V' in result and '/' in result


class TestSqrt:
    def test_simple(self):
        result = latex_to_html(r'\sqrt{x}')
        assert result == '\u221ax'


class TestDollarDelimiters:
    def test_stripped(self):
        result = latex_to_html(r'$\alpha$')
        assert result == '\u03b1'

    def test_inline(self):
        result = latex_to_html(r'Signal ($\mu$V)')
        assert '\u03bc' in result
        assert '$' not in result


class TestPassthrough:
    def test_plain_text(self):
        assert latex_to_html('voltage') == 'voltage'

    def test_empty(self):
        assert latex_to_html('') == ''

    def test_units(self):
        assert latex_to_html('mV') == 'mV'

    def test_with_parens(self):
        assert latex_to_html('amplitude (V)') == 'amplitude (V)'


class TestRealWorldLabels:
    """Labels commonly seen in quantum physics experiments."""

    def test_conductance(self):
        result = latex_to_html(r'g_{11}')
        assert '<sub>' in result or '\u2081' in result  # HTML or Unicode sub

    def test_gate_voltage(self):
        result = latex_to_html(r'V_{gate}')
        assert 'gate' in result
        assert '<sub>' in result

    def test_bias_voltage(self):
        result = latex_to_html(r'V_{SD}')
        assert 'SD' in result

    def test_differential_conductance(self):
        result = latex_to_html(r'$\frac{dI}{dV}$')
        assert 'dI/dV' in result

    def test_magnetic_field(self):
        result = latex_to_html(r'B_{field} (T)')
        assert '<sub>' in result
        assert '(T)' in result


class TestHypothesis:
    @given(st.text(min_size=0, max_size=100))
    @settings(max_examples=200)
    def test_never_crashes(self, text):
        """latex_to_html should never raise on any input."""
        result = latex_to_html(text)
        assert isinstance(result, str)

    @given(st.text(alphabet='abcdefghijklmnopqrstuvwxyz0123456789 .,()',
                   min_size=0, max_size=50))
    @settings(max_examples=100)
    def test_plain_text_passthrough(self, text):
        """Text without LaTeX commands should pass through mostly unchanged."""
        result = latex_to_html(text)
        # Without backslash, underscore, caret, or dollar, text should
        # be largely preserved (unicodeit may convert some symbols like -)
        if '\\' not in text and '_' not in text and '^' not in text and '$' not in text:
            # Allow unicodeit to change some characters (e.g., - to −)
            assert len(result) == len(text)
