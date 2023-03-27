import sys
sys.path.append('..\..')
import plottr
from plottr.data import DataDict
import unittest

class test_basic_fns(unittest.TestCase):

    def test_avg(self):
        """Basic Testing of Averaging function"""
        data_dict = DataDict(x=dict(unit='m'),y=dict(unit='m'),z = dict(axes=['x','y']))
        data_dict.add_data(x=[0,1,2], y = [0,1,2], z = [0,1,4])
        #Tests Basic averaging
        assert data_dict.avg('x') == 1
        assert data_dict.avg('y') == 1
        assert data_dict.avg('z') == 5/3

    def test_std(self):
        """Basic Testing of Standard Deviation function"""
        data_dict = DataDict(x=dict(unit='m'),y=dict(unit='m'),z = dict(axes=['x','y']))
        data_dict.add_data(x=[0,1,2], y = [0,1,2], z = [0,1,4])
        assert data_dict.std('x') == (2/3)**0.5
        assert data_dict.std('y') == (2/3)**0.5
        assert data_dict.std('z') == (26/3)**0.5
        assert data_dict.std('p') == None
        data_dict2 = DataDict()
        assert data_dict2.avg('x') == None

    def test_med(self):
        """Basic Testing of Median function"""
        data_dict = DataDict(x=dict(unit='m'),y=dict(unit='m'),z = dict(axes=['x','y']))
        data_dict.add_data(x=[0,1,2], y = [0,1,2], z = [0,1,4])
        assert data_dict.med('x') == 1
        assert data_dict.med('y') == 1
        assert data_dict.med('z') == 1
        assert data_dict.med('p') == None
        data_dict.add_data(x=[7],y=[4],z=[5])
        assert data_dict.med('x') == 1.5
        assert data_dict.med('y') == 1.5
        assert data_dict.med('z') == 2.5
        data_dict2 = DataDict()
        assert data_dict2.med('x') == None

    def test_normalize(self):
        """Basic Testing of normalizing function"""
        data_dict = DataDict(x=dict(unit='m'),y=dict(unit='m'),z = dict(axes=['x','y']))
        data_dict.add_data(x=[0,1,2], y = [0,1,2], z = [0,1,4])
        data_dict.normalize('x')
        assert data_dict.data_vals('x')[0] == 0
        assert data_dict.data_vals('x')[1] == 0.5
        assert data_dict.data_vals('x')[2] == 1
        data_dict.normalize('y')
        assert data_dict.data_vals('y')[0] == 0
        assert data_dict.data_vals('y')[1] == 0.5
        assert data_dict.data_vals('y')[2] == 1
        data_dict.normalize('z')
        assert data_dict.data_vals('z')[0] == 0
        assert data_dict.data_vals('z')[1] == 0.25
        assert data_dict.data_vals('z')[2] == 1
if __name__ == 'main':
    unittest.main()
