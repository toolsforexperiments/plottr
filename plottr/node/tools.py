"""tools.py

tools for working with flowcharts and nodes.
"""
from typing import Type, Tuple

from plottr import Flowchart
from plottr.node import Node

__author__ = 'Wolfgang Pfaff'
__license__ = 'MIT'


def flowchart() -> Flowchart:
    """Create a blank flowchart instance

    :return: new Flowchart, with terminals ``dataIn`` and
             ``dataOut``.
    """
    fc = Flowchart(
        terminals=dict(
            dataIn=dict(io='in'),
            dataOut=dict(io='out'),
        )
    )
    return fc


def linearFlowchart(*nodes: Tuple[str, Type[Node]]) \
        -> Flowchart:
    """Create a flowchart with linearly connected nodes

    :param node: Nodes, in the order in which they will be connected.
                 given in format (name, NodeClass). Nodes will be instantiated
                 in this function. If no nodes are given, the input of the
                 flowchart is directly connected to the output.
    :return: Flowchart with the specified connections made.
    """
    fc = flowchart()

    nNodes = len(nodes)
    instances = []

    if nNodes == 0:
        fc.connectTerminals(fc['dataIn'], fc['dataOut'])
        return fc

    for i, (name, cls) in enumerate(nodes):
        node = cls(name=name)
        instances.append(node)
        fc.addNode(node, name=name)

        if i == 0:
            fc.connectTerminals(fc['dataIn'], node['dataIn'])
        else:
            fc.connectTerminals(instances[i - 1]['dataOut'], node['dataIn'])

        if i == nNodes - 1:
            fc.connectTerminals(node['dataOut'], fc['dataOut'])

    return fc
