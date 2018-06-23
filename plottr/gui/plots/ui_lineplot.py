# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file 'lineplot.ui'
#
# Created by: PyQt5 UI code generator 5.6
#
# WARNING! All changes made in this file will be lost!

from PyQt5 import QtCore, QtGui, QtWidgets

class Ui_LinePlot(object):
    def setupUi(self, LinePlot):
        LinePlot.setObjectName("LinePlot")
        LinePlot.resize(748, 449)
        self.horizontalLayout_2 = QtWidgets.QHBoxLayout(LinePlot)
        self.horizontalLayout_2.setObjectName("horizontalLayout_2")
        self.widgetLayout = QtWidgets.QHBoxLayout()
        self.widgetLayout.setObjectName("widgetLayout")
        self.plotOptionLayout = QtWidgets.QVBoxLayout()
        self.plotOptionLayout.setObjectName("plotOptionLayout")
        self.xaxis_label = QtWidgets.QLabel(LinePlot)
        self.xaxis_label.setObjectName("xaxis_label")
        self.plotOptionLayout.addWidget(self.xaxis_label)
        self.comboBox = QtWidgets.QComboBox(LinePlot)
        self.comboBox.setMinimumSize(QtCore.QSize(200, 0))
        self.comboBox.setObjectName("comboBox")
        self.plotOptionLayout.addWidget(self.comboBox)
        self.curvesLabel = QtWidgets.QLabel(LinePlot)
        self.curvesLabel.setObjectName("curvesLabel")
        self.plotOptionLayout.addWidget(self.curvesLabel)
        self.curveSelection = QtWidgets.QFrame(LinePlot)
        self.curveSelection.setMinimumSize(QtCore.QSize(0, 200))
        self.curveSelection.setFrameShape(QtWidgets.QFrame.StyledPanel)
        self.curveSelection.setFrameShadow(QtWidgets.QFrame.Raised)
        self.curveSelection.setObjectName("curveSelection")
        self.plotOptionLayout.addWidget(self.curveSelection)
        spacerItem = QtWidgets.QSpacerItem(20, 40, QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Expanding)
        self.plotOptionLayout.addItem(spacerItem)
        self.widgetLayout.addLayout(self.plotOptionLayout)
        self.plot = MPLPlot(LinePlot)
        self.plot.setObjectName("plot")
        self.widgetLayout.addWidget(self.plot)
        self.widgetLayout.setStretch(0, 1)
        self.widgetLayout.setStretch(1, 3)
        self.horizontalLayout_2.addLayout(self.widgetLayout)

        self.retranslateUi(LinePlot)
        QtCore.QMetaObject.connectSlotsByName(LinePlot)

    def retranslateUi(self, LinePlot):
        _translate = QtCore.QCoreApplication.translate
        LinePlot.setWindowTitle(_translate("LinePlot", "Form"))
        self.xaxis_label.setText(_translate("LinePlot", "X-Axis"))
        self.curvesLabel.setText(_translate("LinePlot", "Curves"))

from .mpl import MPLPlot
