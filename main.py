#!/usr/bin/python3
# -*- coding: utf-8 -*-
"""Main application."""

import sys

from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QAction, QApplication, QDesktopWidget, QMainWindow, QMenu, QMessageBox, QWidget, qApp


class Sappy(QMainWindow):

    def __init__(self):
        super().__init__()
        self.initUI()

    def initUI(self):

        self.statusBar()
        self.initMenuBar()

        impMenu = QMenu('Import', self)
        impAct = QAction('Import test', self)
        impMenu.addAction(impAct)

        exitAct = QAction(QIcon('exit.png'), '&Exit', self)
        exitAct.setShortcut('Ctrl+Q')
        exitAct.setStatusTip('Exit application')
        exitAct.triggered.connect(qApp.quit)

        self.resize(400, 600)
        self.setWindowIcon(QIcon('sappy.ico'))
        self.setWindowTitle('Sappy')
        self.show()

    def initMenuBar(self):
        menubar = self.menuBar()
        fileMenu = menubar.addMenu('&File')
        tasksMenu = menubar.addMenu('&Tasks')
        optsMenu = menubar.addMenu('&Options')
        helpMenu = menubar.addMenu('&Help')

        openAct = QAction('&Open', self)
        exitAct = QAction('&Exit', self)
        exitAct.triggered.connect(qApp.quit)
        fileMenu.addAction(openAct)
        fileMenu.addAction(exitAct)


if __name__ == '__main__':
    app = QApplication(sys.argv)
    main = Sappy()
    sys.exit(app.exec_())
