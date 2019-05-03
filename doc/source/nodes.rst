.. documentation for nodes and flowchart.

Nodes and Flowcharts
====================

The basic concept of modular data analyis as we use it in plottr consists of `Nodes` that are connected directionally to form a `Flowchart`. This terminology is adopted from the great `pyqtgraph <http://www.pyqtgraph.org>`_ project; we currently use their `Node` and `Flowchart` API under the hood as well. Executing the flowchart means that data flows through the nodes via connections that have been made between them, and gets modified in some way by each node along the way. The end product is then the fully processed data. This whole process is typically on-demand: If a modification of the data flow occurs somewhere in the flowchart -- e.g., due to user input -- then only 'downstream' nodes need to re-process data in order to keep the flowchart output up to date.


Setting up flowcharts
---------------------

TBD.


Creating custom nodes
---------------------

The following are some general notes. For an example see the notebook ``Custom nodes`` under ``doc/examples``.

The class :class:`plottr.node.node.Node` forms the basis for all nodes in plottr. It is an extension of ``pyqtgraph``'s Node class with some additional tools, and  defaults.


Basics:
^^^^^^^
The actual data processing the node is supposed to do is implemented in :meth:`plottr.node.node.Node.process`.


Defaults:
^^^^^^^^^

Per default, we use an input terminal (``dataIn``), and one output terminal (``dataOut``). Can be overwritten via the attribute :attr:`plottr.node.node.Node.terminals`.

User options:
^^^^^^^^^^^^^

We use ``property`` for user options. i.e., we implement a setter and getter function (e.g., with the ``@property`` decorator). The setter can be decorated with :meth:`plottr.node.node.updateOption` to automatically process the option change on assignment.

Synchronizing Node and UI:
^^^^^^^^^^^^^^^^^^^^^^^^^^

The UI widget is automatically instantiated when :attr:`plottr.node.node.Node.uiClass` is set to an appropriate node widget class, and :attr:`plottr.node.node.Node.useUi` is ``True``.

Messaging between Node and Node UI is implemented through Qt signals/slots. Any update to a node property is signalled automatically when the property setter is decorated with :meth:`plottr.node.node.updateOption`. A setter decorated with ``@updateOption('myOption')`` will, on assignment of the new value, call the function assigned to ``plottr.node.node.NodeWidget.optSetter['myOption']``.

Vice versa, there are tools to notify the node of changes made through the UI. Any trigger (such as a widget signal) can be connected to the UI by calling the functions :meth:`plottr.node.node.NodeWidget.signalOption` with the option name (say, ``myOption``) as argument, or :meth:`plottr.node.node.NodeWidget.signalAllOptions`. In the first case, the value of the option is taken by calling ``plottr.node.node.NodeWidget.optGetter['myOption']()``, and then the name of the option and that value are emitted through :meth:`plottr.node.node.updateGuiFromNode`; this is connected to :meth:`plottr.node.node.Node.setOption` by default. Similarly, :meth:`plottr.node.node.NodeWidget.signalAllOptions` results in a signal leading to :meth:`plottr.node.node.Node.setOptions`.

The implementation of the suitable triggers for emitting the option value and assigning functions to entries in ``optSetters`` and ``optGetters`` is up to the re-implementation.


Example implementation:
^^^^^^^^^^^^^^^^^^^^^^^

The implementation of a custom node with GUI can then looks something like this::

    class MyNode(Node):

        useUi = True
        uiClass = MyNodeGui

        ...

        @property
        def myOption(self):
            return self._myOption

        # the name in the decorator should match the name of the
        # property to make sure communication goes well.
        @myOption.setter
        @updateOption('myOption')
        def myOption(self, value):
            # this could include validation, etc.
            self._myOption = value

        ...


That is essentially all that is needed for the Node; only the process function that does something depending on the value of ``myOption`` is missing here. The UI class might then look like this::

    class MyNodeGui(NodeWidget):

        def __init__(self, parent=None):
            # this is a Qt requirement
            super().__init__(parent)

            somehowSetUpWidget()

            self.optSetters = {
                'myOption' : self.setMyOption,
            }
            self.optGetters = {
                'myOption' : self.getMyOption,
            }

            # often the trigger will be a valueChanged function or so,
            # that returns a value. Since the signalOption function
            # doesn't require one, we can use a lambda to bypass, if necessary.
            self.somethingChanged.connect(lambda x: self.signalOption('myOption'))

        def setMyOption(self, value):
            doSomething()

        def getMyOption(self):
            return getInfoNeeded()


This node can then already be used, with the UI if desired, in a flowchart.

API documentation for the node module
-------------------------------------

.. automodule:: plottr.node.node
    :members: