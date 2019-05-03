from plottr.data.datadict import DataDict
from plottr.node.tools import flowchart, linearFlowchart
from plottr.node.node import Node


def test_basic_flowchart_and_nodes(qtbot):
    fc = flowchart()
    node = Node(name='node')

    fc.addNode(node, name=node.name())

    fc.connectTerminals(fc['dataIn'], node['dataIn'])
    fc.connectTerminals(node['dataOut'], fc['dataOut'])

    fc.setInput(dataIn='abcdef')
    assert fc.outputValues() == dict(dataOut='abcdef')

    for i in range(3):
        lst = [(f'node{j}', Node) for j in range(i)]
        fc = linearFlowchart(*lst)
        fc.setInput(dataIn='abcdef')
        assert fc.outputValues() == dict(dataOut='abcdef')

# def test_
