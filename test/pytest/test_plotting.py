import matplotlib.pyplot as plt
import numpy as np
import os
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from plottr.data.datadict import MeshgridDataDict, DataDict
from plottr.plot.mpl.plotting import PlotType, colorplot2d


def test_colorplot2d_scatter_rgba_error():
    """
    Check that scatter plots are not trying to plot 1x3 and 1x4
    z arrays as rgb(a) colors.

    """
    fig, ax = plt.subplots(1, 1)
    x = np.array([[0.0, 11.11111111, 22.22222222, 33.33333333]])
    y = np.array(
        [
            [
                0.0,
                0.0,
                0.0,
                0.0,
            ]
        ]
    )
    z = np.array([[5.08907021, 4.93923391, 5.11400073, 5.0925613]])
    colorplot2d(ax, x, y, z, PlotType.scatter2d)

    x = np.array([[0.0, 11.11111111, 22.22222222]])
    y = np.array([[0.0, 0.0, 0.0]])
    z = np.array([[5.08907021, 4.93923391, 5.11400073]])
    colorplot2d(ax, x, y, z, PlotType.scatter2d)


# -- Axis orientation tests --

def _make_asymmetric_meshgrid():
    """5×3 meshgrid with unique Z per position."""
    x = np.linspace(-2, 2, 5)
    y = np.linspace(10, 30, 3)
    xx, yy = np.meshgrid(x, y, indexing='ij')
    zz = xx + 100 * yy
    dd = MeshgridDataDict(
        z=dict(values=zz, axes=['x', 'y']),
        x=dict(values=xx), y=dict(values=yy),
    )
    dd.validate()
    return dd, xx, yy, zz


class TestAxisOrientation:
    """Verify that 2D image plots have correct X/Y axis orientation."""

    def test_pyqtgraph_image_data_shape(self, qtbot):
        from plottr.plot.pyqtgraph.plots import PlotWithColorbar
        _, xx, yy, zz = _make_asymmetric_meshgrid()
        plot = PlotWithColorbar()
        qtbot.addWidget(plot)
        plot.setImage(xx, yy, zz)
        # pyqtgraph uses col-major ordering: the first array axis (x, 5 points)
        # maps to the horizontal display axis, the second (y, 3 points) to the
        # vertical one. No transpose is applied, so the shape is unchanged.
        assert plot.img.image.shape == (5, 3)

    def test_pyqtgraph_image_rect(self, qtbot):
        from plottr.plot.pyqtgraph.plots import PlotWithColorbar
        from plottr import QtCore
        _, xx, yy, zz = _make_asymmetric_meshgrid()
        plot = PlotWithColorbar()
        qtbot.addWidget(plot)
        plot.setImage(xx, yy, zz)
        expected = QtCore.QRectF(
            xx.min(), yy.min(), xx.max() - xx.min(), yy.max() - yy.min()
        )
        assert abs(expected.width() - (xx.max() - xx.min())) < 0.01
        assert abs(expected.height() - (yy.max() - yy.min())) < 0.01

    def test_pyqtgraph_reversed_x(self, qtbot):
        from plottr.plot.pyqtgraph.plots import PlotWithColorbar
        x = np.linspace(2, -2, 5)
        y = np.linspace(10, 30, 3)
        xx, yy = np.meshgrid(x, y, indexing='ij')
        zz = xx + 100 * yy
        plot = PlotWithColorbar()
        qtbot.addWidget(plot)
        plot.setImage(xx, yy, zz)
        assert plot.img.image.shape == (5, 3)  # no transpose, only a flip
        # x is decreasing -> the data is flipped along axis 0 so that the
        # smallest x ends up at the left (image index 0).
        np.testing.assert_array_equal(plot.img.image, zz[::-1, :])

    def test_pyqtgraph_orientation_matches_mpl(self, qtbot):
        """The pixel that pyqtgraph and matplotlib place at the bottom-left
        corner must encode the same (x, y) data location."""
        from plottr.plot.pyqtgraph.plots import PlotWithColorbar
        from plottr.plot.mpl.plotting import plotImage
        _, xx, yy, zz = _make_asymmetric_meshgrid()

        fig, ax = plt.subplots()
        im = plotImage(ax, xx, yy, zz)
        mpl_arr = np.asarray(im.get_array())
        plt.close(fig)

        plot = PlotWithColorbar()
        qtbot.addWidget(plot)
        plot.setImage(xx, yy, zz)
        pg_img = plot.img.image

        # matplotlib (origin='lower'): bottom-left = mpl_arr[0, 0],
        # one step right = +x, one step up = +y.
        # pyqtgraph (col-major): bottom-left = pg_img[0, 0],
        # one step right (axis 0) = +x, one step up (axis 1) = +y.
        assert pg_img[0, 0] == mpl_arr[0, 0]
        assert pg_img[1, 0] == mpl_arr[0, 1]   # +x step
        assert pg_img[0, 1] == mpl_arr[1, 0]   # +y step

    def test_pyqtgraph_axis_order_after_xyselector(self, qtbot):
        """Regression: data stored with the y-role axis first must still be
        displayed with the x-role axis horizontal (matches matplotlib).

        Reproduces the case where the array is laid out as
        ``[axisA, axisB]`` but the user assigns ``axisB`` to x and ``axisA``
        to y. ``XYSelector`` reorders the axes; the plot backend must not
        re-introduce a transpose.
        """
        from plottr.plot.pyqtgraph.plots import PlotWithColorbar
        from plottr.node.dim_reducer import XYSelector

        n_a, n_b = 7, 4
        a = np.linspace(0, 6, n_a)
        b = np.linspace(-3, 0, n_b)
        aa, bb = np.meshgrid(a, b, indexing='ij')   # shape (n_a, n_b)
        ai = np.arange(n_a)[:, None] * np.ones((1, n_b))
        bi = np.ones((n_a, 1)) * np.arange(n_b)[None, :]
        zz = bi * 1000 + ai                          # encodes (b_idx, a_idx)

        dd = MeshgridDataDict(
            signal=dict(values=zz, axes=['a', 'b']),
            a=dict(values=aa), b=dict(values=bb),
        )
        dd.validate()

        sel = XYSelector(name='sel_orient')
        sel._xyAxes = ('b', 'a')   # b -> x-axis, a -> y-axis
        out = sel.process(dataIn=dd)['dataOut']
        inds = out.axes('signal')
        x = out.data_vals(inds[0])
        y = out.data_vals(inds[1])
        z = out.data_vals('signal')

        plot = PlotWithColorbar()
        qtbot.addWidget(plot)
        plot.setImage(x, y, z)
        img = plot.img.image

        # horizontal step (axis 0) should change the x-role index (b -> +1000)
        assert img[1, 0] - img[0, 0] == 1000
        # vertical step (axis 1) should change the y-role index (a -> +1)
        assert img[0, 1] - img[0, 0] == 1

    def test_mpl_and_pyqtgraph_consistency(self, qtbot):
        _, xx, yy, zz = _make_asymmetric_meshgrid()
        from plottr.plot.mpl.plotting import plotImage
        fig, ax = plt.subplots()
        plotImage(ax, xx, yy, zz)
        plt.close(fig)
        from plottr.plot.pyqtgraph.plots import PlotWithColorbar
        plot = PlotWithColorbar()
        qtbot.addWidget(plot)
        plot.setImage(xx, yy, zz)
        assert plot.img is not None and plot.img.image is not None


# -- Complex splitting tests --

class TestComplexSplitting:
    """Verify complex data is split correctly for 1D and 2D."""

    @staticmethod
    def _make_complex_1d():
        x = np.linspace(0, 10, 50)
        z = np.sin(x) + 1j * np.cos(x)
        dd = DataDict(z=dict(values=z, axes=['x']), x=dict(values=x))
        dd.validate()
        return dd

    def test_detected(self):
        assert np.iscomplexobj(self._make_complex_1d().data_vals('z'))

    def test_split_real(self):
        from plottr.plot.base import ComplexRepresentation, PlotItem, PlotDataType, AutoFigureMaker
        dd = self._make_complex_1d()
        item = PlotItem([dd.data_vals('x'), dd.data_vals('z')], 0, 0,
                         PlotDataType.line1d, ['x', 'z'], None)
        fm = AutoFigureMaker()
        fm.complexRepresentation = ComplexRepresentation.real
        result = fm._splitComplexData(item)
        assert len(result) == 1
        assert not np.iscomplexobj(result[0].data[-1])

    def test_split_real_and_imag(self):
        from plottr.plot.base import ComplexRepresentation, PlotItem, PlotDataType, AutoFigureMaker
        dd = self._make_complex_1d()
        z = dd.data_vals('z')
        item = PlotItem([dd.data_vals('x'), z], 0, 0,
                         PlotDataType.line1d, ['x', 'z'], None)
        fm = AutoFigureMaker()
        fm.complexRepresentation = ComplexRepresentation.realAndImag
        result = fm._splitComplexData(item)
        assert len(result) == 2
        np.testing.assert_array_equal(result[0].data[-1], z.real)
        np.testing.assert_array_equal(result[1].data[-1], z.imag)

    def test_split_mag_and_phase(self):
        from plottr.plot.base import ComplexRepresentation, PlotItem, PlotDataType, AutoFigureMaker
        dd = self._make_complex_1d()
        z = dd.data_vals('z')
        item = PlotItem([dd.data_vals('x'), z], 0, 0,
                         PlotDataType.line1d, ['x', 'z'], None)
        fm = AutoFigureMaker()
        fm.complexRepresentation = ComplexRepresentation.magAndPhase
        result = fm._splitComplexData(item)
        assert len(result) == 2
        np.testing.assert_array_almost_equal(result[0].data[-1], np.abs(z))
        np.testing.assert_array_almost_equal(result[1].data[-1], np.angle(z))


# -- Matplotlib first-plot-not-blank tests --

class TestMplFirstPlot:
    """Verify mpl backend renders on first setData (plotType is set)."""

    def test_2d_sets_plotType(self, qtbot):
        from plottr.plot.mpl.autoplot import AutoPlot
        w = AutoPlot()
        qtbot.addWidget(w)
        x = np.linspace(-1, 1, 10)
        y = np.linspace(0, 5, 8)
        xx, yy = np.meshgrid(x, y, indexing='ij')
        data = MeshgridDataDict(
            z=dict(values=xx**2 + yy, axes=['x', 'y']),
            x=dict(values=xx), y=dict(values=yy),
        )
        w.setData(data)
        assert w.plotType is not PlotType.empty

    def test_1d_sets_plotType(self, qtbot):
        from plottr.plot.mpl.autoplot import AutoPlot
        w = AutoPlot()
        qtbot.addWidget(w)
        x = np.linspace(0, 10, 50)
        data = MeshgridDataDict(
            y=dict(values=np.sin(x), axes=['x']), x=dict(values=x),
        )
        w.setData(data)
        assert w.plotType is not PlotType.empty

    def test_repeated_setData(self, qtbot):
        from plottr.plot.mpl.autoplot import AutoPlot
        w = AutoPlot()
        qtbot.addWidget(w)
        x = np.linspace(-1, 1, 10)
        y = np.linspace(0, 5, 8)
        xx, yy = np.meshgrid(x, y, indexing='ij')
        data = MeshgridDataDict(
            z=dict(values=xx**2 + yy, axes=['x', 'y']),
            x=dict(values=xx), y=dict(values=yy),
        )
        w.setData(data)
        t1 = w.plotType
        w.setData(data)
        assert w.plotType == t1


# -- Pyqtgraph complex mode switching tests --

class TestPyqtgraphComplexModes:
    """Verify pyqtgraph backend handles complex mode switching for 1D data."""

    @staticmethod
    def _make_complex_1d():
        x = np.linspace(0, 10, 50)
        z = np.sin(x) + 1j * np.cos(x)
        return MeshgridDataDict(
            z=dict(values=z, axes=['x']), x=dict(values=x),
        )

    def test_complex_detected_as_imagData(self, qtbot):
        """1D complex data should set imagData=True."""
        from plottr.plot.pyqtgraph.autoplot import AutoPlot
        w = AutoPlot(parent=None)
        qtbot.addWidget(w)
        w.setData(self._make_complex_1d())
        assert w.figOptions.imagData is True

    def test_all_complex_options_available(self, qtbot):
        """All complex representations should be in the toolbar menu."""
        from plottr.plot.pyqtgraph.autoplot import AutoPlot
        from plottr.plot.base import ComplexRepresentation
        w = AutoPlot(parent=None)
        qtbot.addWidget(w)
        w.setData(self._make_complex_1d())

        # Find the Complex button's menu
        menu_labels = self._get_complex_menu_labels(w)
        assert ComplexRepresentation.real.label in menu_labels
        assert ComplexRepresentation.realAndImag.label in menu_labels
        assert ComplexRepresentation.realAndImagSeparate.label in menu_labels
        assert ComplexRepresentation.magAndPhase.label in menu_labels

    def test_switch_to_real_and_back(self, qtbot):
        """After switching to Real, should be able to switch back to Real/Imag."""
        from plottr.plot.pyqtgraph.autoplot import AutoPlot
        from plottr.plot.base import ComplexRepresentation
        w = AutoPlot(parent=None)
        qtbot.addWidget(w)
        w.setData(self._make_complex_1d())

        # Switch to Real
        w.figOptions.complexRepresentation = ComplexRepresentation.real
        w._refreshPlot()

        # imagData should still be True (data is still complex)
        assert w.figOptions.imagData is True

        # All options should still be available
        menu_labels = self._get_complex_menu_labels(w)
        assert ComplexRepresentation.realAndImag.label in menu_labels

        # Switch back
        w.figOptions.complexRepresentation = ComplexRepresentation.realAndImag
        w._refreshPlot()
        assert w.figOptions.complexRepresentation == ComplexRepresentation.realAndImag

    def test_separate_re_im_mode(self, qtbot):
        """realAndImagSeparate should create 2 subplots for 1D data."""
        from plottr.plot.pyqtgraph.autoplot import AutoPlot
        from plottr.plot.base import ComplexRepresentation
        w = AutoPlot(parent=None)
        qtbot.addWidget(w)
        w.setData(self._make_complex_1d())

        w.figOptions.complexRepresentation = ComplexRepresentation.realAndImagSeparate
        w._refreshPlot()

        # Should have 2 subplots (one for Real, one for Imag)
        assert w.fmWidget is not None
        assert len(w.fmWidget.subPlots) == 2

    def test_non_complex_only_shows_real(self, qtbot):
        """Non-complex 1D data should only offer Real in the menu."""
        from plottr.plot.pyqtgraph.autoplot import AutoPlot
        from plottr.plot.base import ComplexRepresentation
        w = AutoPlot(parent=None)
        qtbot.addWidget(w)
        x = np.linspace(0, 10, 50)
        data = MeshgridDataDict(
            y=dict(values=np.sin(x), axes=['x']), x=dict(values=x),
        )
        w.setData(data)
        assert w.figOptions.imagData is False
        menu_labels = self._get_complex_menu_labels(w)
        assert menu_labels == [ComplexRepresentation.real.label]

    @staticmethod
    def _get_complex_menu_labels(w):
        """Extract labels from the Complex button's popup menu."""
        # The Complex button is at action index 1 in the toolbar
        toolbar = w.figConfig
        actions = toolbar.actions()
        for a in actions:
            widget = toolbar.widgetForAction(a)
            if isinstance(widget, __import__('plottr').QtWidgets.QToolButton):
                menu = widget.menu()
                if menu is not None:
                    return [ma.text() for ma in menu.actions()]
        return []


# -- Default grid selection tests --

class TestGridDefaults:
    """Verify setDefaults picks a sensible grid option for the input data."""

    def test_ddh5_without_shape_meta_defaults_to_guessShape(self, qtbot):
        """A dataset without ``qcodes_shape`` metadata (e.g. a normal ddh5
        file) must default to ``guessShape`` rather than being left at the
        ``noGrid`` default.

        Regression: the base ``setDefaults`` used to call
        ``meta_val('qcodes_shape')`` unconditionally, which raised
        ``KeyError`` for ddh5 data and aborted defaults setup, leaving the
        gridder at ``noGrid`` ("No grid").
        """
        from plottr.apps.autoplot import autoplot
        from plottr.node.grid import GridOption
        x = np.linspace(0, 1, 5)
        y = np.linspace(0, 1, 4)
        xx, yy = np.meshgrid(x, y, indexing='ij')
        data = MeshgridDataDict(
            z=dict(values=xx + yy, axes=['x', 'y']),
            x=dict(values=xx), y=dict(values=yy),
        )
        data.validate()
        assert '__qcodes_shape__' not in data  # no qcodes shape metadata

        fc, win = autoplot(inputData=data)
        qtbot.addWidget(win)
        option, _ = fc.nodes()['Grid'].grid
        assert option is GridOption.guessShape

        roles = fc.nodes()['Dimension assignment'].dimensionRoles
        assert roles  # dimension roles were assigned, defaults completed

