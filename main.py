#!/usr/bin/python3
# -*- coding: utf-8 -*-
"""Main application."""

import sys

import PyQt5
from PyQt5.QtGui import QCloseEvent, QIcon
from PyQt5.QtWidgets import (QAction, QActionGroup, QApplication,
                             QDesktopWidget, QMainWindow, QMenu, QMessageBox,
                             QWidget, qApp)


class Sappy(QMainWindow):

    def __init__(self):
        super().__init__()
        self.initUI()

    def initUI(self):
        self.initWindow()
        self.setCentralWidget(SappyPlayer())
        self.createMenuBar()
        self.show()

    def initWindow(self):
        self.setWindowIcon(QIcon('sappy.ico'))
        self.setWindowIconText('Sappy')
        self.setWindowTitle('Sappy')
        self.setMinimumSize(400, 600)
        self.resize(400, 600)

    def createMenuBar(self):
        menubar = self.menuBar()
        fileMenu: QMenu = menubar.addMenu('&File')
        tasksMenu: QMenu = menubar.addMenu('&Tasks')
        optsMenu: QMenu = menubar.addMenu('&Options')
        helpMenu: QMenu = menubar.addMenu('&Help')

        openAct = QAction('&Open', self)
        exitAct = QAction('&Exit', self)

        exportTracksAct = QAction('Export tracks', self)
        importTracksAct = QAction('Import tracks', self)
        exportSampAct = QAction('Export samples', self)
        importSampAct = QAction('Import samples', self)
        assembleAct = QAction('Assemble song', self)
        editVoicesAct = QAction('Edit Voice Table', self)

        waveOutAct = QAction('WAV Driver', self)
        midiOutAct = QAction('MIDI Driver (WIP)', self)
        seekPlaylistAct = QAction('Seek by Playlist', self)
        gameboyMode = QAction('GB Mode', self)
        importLSTAct = QAction('Import LST file', self)
        setMIDIOutAct = QAction('Select MIDI device...', self)
        remapMIDIInstAct = QAction('Remap MIDI instruments...', self)
        settingsAct = QAction('Settings', self)

        aboutAct = QAction('About', self)
        onlineAct = QAction("Visit Kawa's Crap", self)

        outputActGroup = QActionGroup(self)

        exitAct.triggered.connect(qApp.quit)
        exitAct.triggered

        fileMenu.addAction(openAct)
        fileMenu.addSeparator()
        fileMenu.addAction(exitAct)
        tasksMenu.addAction(exportTracksAct)
        tasksMenu.addAction(importTracksAct)
        tasksMenu.addAction(exportSampAct)
        tasksMenu.addAction(importSampAct)
        tasksMenu.addAction(assembleAct)
        tasksMenu.addAction(editVoicesAct)
        optsMenu.addAction(waveOutAct)
        optsMenu.addAction(midiOutAct)
        optsMenu.addSeparator()
        optsMenu.addAction(seekPlaylistAct)
        optsMenu.addAction(gameboyMode)
        optsMenu.addSeparator()
        optsMenu.addAction(importLSTAct)
        optsMenu.addAction(setMIDIOutAct)
        optsMenu.addAction(remapMIDIInstAct)
        optsMenu.addSeparator()
        optsMenu.addAction(settingsAct)
        helpMenu.addAction(aboutAct)
        helpMenu.addAction(onlineAct)
        outputActGroup.addAction(waveOutAct)
        outputActGroup.addAction(midiOutAct)

    def closeEvent(self, event: QCloseEvent):
        self.cleanUp()
        event.accept()

    def cleanUp(self):
        pass


class SappyPlayer(QWidget):

    def __init__(self):
        super().__init__()
        self.initUI()

    def initUI(self):
        pass


if __name__ == '__main__':
    app = QApplication(sys.argv)
    main = Sappy()
    sys.exit(app.exec())
