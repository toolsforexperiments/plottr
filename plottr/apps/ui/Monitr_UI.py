# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file 'monitr.ui'
#
# Created by: PyQt5 UI code generator 5.9.2
#
# WARNING! All changes made in this file will be lost!

from plottr import QtCore, QtGui, QtWidgets

class Ui_MainWindow(object):
    def setupUi(self, MainWindow: QtWidgets.QMainWindow) -> None:
        MainWindow.setObjectName("MainWindow")
        MainWindow.resize(935, 569)
        self.centralwidget = QtWidgets.QWidget(MainWindow)
        self.centralwidget.setObjectName("centralwidget")
        self.verticalLayout = QtWidgets.QVBoxLayout(self.centralwidget)
        self.verticalLayout.setObjectName("verticalLayout")
        self.splitter = QtWidgets.QSplitter(self.centralwidget)
        self.splitter.setOrientation(QtCore.Qt.Horizontal)
        self.splitter.setObjectName("splitter")
        self.fileList = DataFileList(self.splitter)
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        sizePolicy.setHorizontalStretch(1)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.fileList.sizePolicy().hasHeightForWidth())
        self.fileList.setSizePolicy(sizePolicy)
        self.fileList.setAlternatingRowColors(False)
        self.fileList.setUniformRowHeights(True)
        self.fileList.setObjectName("fileList")
        self.fileContents = DataFileContent(self.splitter)
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        sizePolicy.setHorizontalStretch(2)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.fileContents.sizePolicy().hasHeightForWidth())
        self.fileContents.setSizePolicy(sizePolicy)
        self.fileContents.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.fileContents.setUniformRowHeights(True)
        self.fileContents.setAllColumnsShowFocus(False)
        self.fileContents.setObjectName("fileContents")
        self.verticalLayout.addWidget(self.splitter)
        MainWindow.setCentralWidget(self.centralwidget)
        self.menubar = QtWidgets.QMenuBar(MainWindow)
        self.menubar.setGeometry(QtCore.QRect(0, 0, 935, 22))
        self.menubar.setObjectName("menubar")
        MainWindow.setMenuBar(self.menubar)
        self.statusbar = QtWidgets.QStatusBar(MainWindow)
        self.statusbar.setObjectName("statusbar")
        MainWindow.setStatusBar(self.statusbar)
        self.monitorToolBar = MonitorToolBar(MainWindow)
        self.monitorToolBar.setObjectName("monitorToolBar")
        MainWindow.addToolBar(QtCore.Qt.TopToolBarArea, self.monitorToolBar)
        self.autoPlotNewAction = QtWidgets.QAction(MainWindow)
        self.autoPlotNewAction.setCheckable(True)
        self.autoPlotNewAction.setObjectName("autoPlotNewAction")
        self.monitorToolBar.addAction(self.autoPlotNewAction)

        self.retranslateUi(MainWindow)
        MainWindow.dataFileSelected.connect(self.fileContents.setData)
        self.fileList.dataFileSelected.connect(MainWindow.processFileSelection)
        self.fileContents.customContextMenuRequested['QPoint'].connect(self.fileContents.onCustomContextMenuRequested)
        self.fileContents.plotRequested.connect(MainWindow.plotSelected)
        self.fileList.itemSelectionChanged.connect(self.fileList.processSelection)
        self.fileList.newDataFilesFound.connect(MainWindow.onNewDataFilesFound)
        QtCore.QMetaObject.connectSlotsByName(MainWindow)

    def retranslateUi(self, MainWindow: QtWidgets.QMainWindow) -> None:
        _translate = QtCore.QCoreApplication.translate
        MainWindow.setWindowTitle(_translate("MainWindow", "Monitr"))
        self.fileList.setSortingEnabled(True)
        self.fileList.headerItem().setText(0, _translate("MainWindow", "Path"))
        self.fileContents.setSortingEnabled(True)
        self.fileContents.headerItem().setText(0, _translate("MainWindow", "Object"))
        self.fileContents.headerItem().setText(1, _translate("MainWindow", "Content"))
        self.fileContents.headerItem().setText(2, _translate("MainWindow", "Type"))
        self.monitorToolBar.setWindowTitle(_translate("MainWindow", "toolBar"))
        self.autoPlotNewAction.setText(_translate("MainWindow", "Auto-plot new"))
        self.autoPlotNewAction.setShortcut(_translate("MainWindow", "Ctrl+A"))

from .monitr import DataFileContent, DataFileList, MonitorToolBar
