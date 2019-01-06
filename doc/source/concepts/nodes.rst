.. documentation for nodes and flowchart.

Nodes and Flowcharts
====================

The basic concept of modular data analyis as we use it in plottr consists of `Nodes` that are connected directionally to form a `Flowchart`. This terminology is adopted from the great `pyqtgraph <http://www.pyqtgraph.org>`_ project; we currently use their `Node` and `Flowchart` API under the hood as well. Executing the flowchart means that data flows through the nodes via connections that have been made between them, and gets modified in some way by each node along the way. The end product is then the fully processed data. This whole process is typically on-demand: If a modification of the data flow occurs somewhere in the flowchart -- e.g., due to user input -- then only 'downstream' nodes need to re-process data in order to keep the flowchart output up to date.