import pytest
from packaging import version
import qcodes as qc
from numpy.testing import assert_array_equal


from plottr.data.datadict import DataDict
from plottr.node.tools import linearFlowchart
from plottr.data.qcodes_dataset import QCodesDSLoader
from plottr.node.data_selector import DataSelector
from plottr.node.grid import DataGridder, GridOption
from plottr.node.scaleunits import ScaleUnits


@pytest.mark.skipif(version.parse(qc.__version__)
                    < version.parse("0.20.0"),
                    reason="Requires QCoDes 0.20.0 or later")
def test_qcodes_flow_shaped_data(qtbot, dataset_with_shape):

    fc = linearFlowchart(
        ('Data loader', QCodesDSLoader),
        ('Data selection', DataSelector),
        ('Grid', DataGridder),
        ('Scale Units', ScaleUnits)
    )
    loader = fc.nodes()['Data loader']
    selector = fc.nodes()['Data selection']
    selector.selectedData = 'z_0'
    gridder = fc.nodes()['Grid']
    gridder.grid = (GridOption.metadataShape, {})

    loader.pathAndId = dataset_with_shape.path_to_db, dataset_with_shape.run_id
    loader.update()

    expected_shape = dataset_with_shape.description.shapes['z_0']

    datadict = fc.output()['dataOut']

    for key in ('x', 'y', 'z_0'):
        assert datadict[key]['values'].shape == expected_shape
        assert datadict.shapes()[key] == expected_shape
        assert_array_equal(
            datadict[key]['values'],
            dataset_with_shape.get_parameter_data()['z_0'][key]
        )
    assert datadict.shape() == expected_shape
