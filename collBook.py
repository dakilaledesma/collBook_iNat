#!/usr/bin/env python3
# -*- coding: utf-8 -*-

#    This program is free software; you can redistribute it and/or
#    modify it under the terms of the GNU General Public License
#    as published by the Free Software Foundation; either version 3
#    of the License, or (at your option) any later version.
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#    You should have received a copy of the GNU General Public License
#    along with this program; if not, write to the Free Software
#    Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA

"""

collBook is the desktop companion to collNote. Combined they are seek to
provide a field-to-database solution designed for field biologists to gather
and format “born digital” field notes into database ready formats.

"""
__author__ = "Caleb Powell, Jacob Motley"
__credits__ = ["Caleb Powell, Jacob Motley, Dax Ledesma, Joey Shaw"]
__email__ = "calebadampowell@gmail.com"
__status__ = "Alpha"
__version__ = 'v0.1.8-alpha'

import sys
# define a static crash logging function
def log_crash():
    # imports only necessary for crash logging
    from os import path as os_path
    import logging
    import platform
    # determine if python environment is frozen by pyinstaller
    if getattr( sys, 'frozen', False ):
        # identify the application's location
        application_path = os.path.dirname(sys.executable)
        log_fn = os_path.join(application_path, 'crash_info.log')
    else:
        # running live
        log_fn = Path('crash_info.log')
    # additional contextual informantion
    context_info = {'cb_version':__version__,
                    'running_os':f'{platform.system()} {platform.release()}'}
    logging.basicConfig(format = '%(asctime)s, %(cb_version)s, %(running_os)s: %(message)s',
                        datefmt = '%m/%d/%Y %I:%M:%S %p',
                        filename = log_fn,
                        filemode='w',
                        level=logging.ERROR)

    # given an exception, log it then raise it for normal handling
    logging.error("Fatal error in main loop", exc_info=True, extra=context_info)

# wrap the rest of the imports with the exception logger
try:
    from io import StringIO
    from pathlib import Path
    from datetime import date
    import pandas as pd
    from PyQt5 import QtWidgets
    from PyQt5.QtWidgets import (QMainWindow, QTreeWidgetItem,
                                 QTreeWidgetItemIterator, QItemDelegate,
                                 QCompleter, QDialog, QScrollArea, QWidget,
                                 QGridLayout, QLabel, QWhatsThis)
    from PyQt5.QtWidgets import QMessageBox
    from PyQt5.QtGui import QWhatsThisClickedEvent
    from reportlab.platypus.doctemplate import LayoutError
    from ui.printlabels import LabelPDF
    from ui.pandastablemodel import PandasTableModel
    from ui.locality import locality
    from PyQt5.QtCore import QFile, Qt
    import qdarkstyle
    from ui.collBookUI import Ui_MainWindow
    from ui.settingsdialog import settingsWindow
    from ui.taxonomy import taxonomicVerification
    from ui.associatedtaxa import associatedTaxaMainWindow
    from ui.scinameinputdialog import sciNameDialog
    from ui.progressbar import progressBar
    from ui import aboutdialogUI
    
    # simple python script holding the API keys
    from ui import apiKeys
except Exception:
    # given an exception, log it then handle normally.
    log_crash()
    raise

class editorDelegate(QItemDelegate):
    """solution to the table_view editor clearing pre-existing cell values
    ref: https://stackoverflow.com/questions/39387842/not-displaying-old-value-when-editing-cell-in-a-qtablewidget"""
    def setEditorData(self, editor, index):
        editor.setAutoFillBackground(True)
        editor.setText(str(index.data()))


class aboutDialog(QDialog):
    """ a class to handle the about dialog"""
    def __init__(self):
        super().__init__()
        self.init_ui()
           
    def init_ui(self):
        ab = aboutdialogUI.Ui_Dialog()
        ab.setupUi(self)
        ab.label_collBookVersion.setText(f"version: {__version__}")
    
    def showLicense(self):
        """ used if the license button is pressed """
        ld = licenseDialog()        


class ScrollMessageBox(QMessageBox):
   def __init__(self, *args, **kwargs):
      QMessageBox.__init__(self, *args, **kwargs)
      chldn = self.children()
      scrll = QScrollArea(self)
      scrll.setWidgetResizable(True)
      grd = self.findChild(QGridLayout)
      lbl = QLabel(chldn[1].text(), self)
      lbl.setWordWrap(True)
      scrll.setWidget(lbl)
      scrll.setMinimumSize (500,300)
      grd.addWidget(scrll,0,1)
      chldn[1].setText('')
      self.exec_()

class licenseDialog(QWidget):
   def __init__(self):
      super(licenseDialog,self).__init__()
      self.message = ("""collBook is free software; you can redistribute it and/or  \
modify it under the terms of the GNU General Public License  \
as published by the Free Software Foundation; either version 3  \
of the License, or (at your option) any later version.  \


collBook is distributed in the hope that it will be useful,  \
but WITHOUT ANY WARRANTY; without even the implied warranty of  \
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the  \
GNU General Public License for more details.  \


You should have received a copy of the GNU General Public License  \
along with this program; if not, write to the Free Software  \
Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA""")
      _ = ScrollMessageBox(QMessageBox.Information,"collBook license",self.message)


class MyMainWindow(QMainWindow):
    """
    A subclass of the QMainWindow with the eventFilter method.
    from: https://gist.github.com/stevenliebregt/8e4211937b671ac637b610650a11914f
    """

    def __init__(self, parent=None):
        super(MyMainWindow, self).__init__(parent)

    def eventFilter(self, obj, event):
        if event.type() == QWhatsThisClickedEvent:  # Catch the TouchBegin event.
            print('We have a touch begin')
            return True
        elif event.type() == QEvent.TouchEnd:  # Catch the TouchEnd event.
            print('We have a touch end')
            return True

        return super(MyMainWindow, self).eventFilter(obj, event)

class MyWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.init_ui()

    def init_ui(self):
        self.w = Ui_MainWindow()
        self.setWindowState(Qt.WindowMaximized)
        self.w.setupUi(self)
        self.w.version = __version__
        self.status_bar = self.statusBar()
        self.statusBar = progressBar(self.status_bar)
        self.statusBar.initProgressBar(self.status_bar)
        self.progress_bar = self.statusBar.progressBar
        self.m = PandasTableModel(self)
        self.tree_widget = self.w.tree_widget  # The nav tree widget.
        self.site_tree_widget = self.w.treeWidget_sitesToApply  # site selection tree widget in "all records view"
        self.settings = settingsWindow(self)  # settingsWindow
        self.associatedTaxaWindow = associatedTaxaMainWindow(self)  # associatedTaxaWindow
        self.associatedTaxaWindow.setWindowModality(Qt.ApplicationModal)
        self.lineEdit_sciName = self.w.lineEdit_sciName
        self.form_view = self.w.formView
        self.table_view = self.w.table_view
        self.table_view.setItemDelegate(editorDelegate(self.table_view))  # use flipped proxy delegate
        self.form_view.init_ui(self, self.w)
        self.tax = taxonomicVerification(self.settings, self, apiKeys.tropicos_API_key)  # taxonomic verifier
        self.p = LabelPDF(self.settings)
        self.p.initLogoCanvas()  # alter this to happen based on settings changes
        self.pdf_preview = self.w.pdf_preview
        self.pdf_preview.initViewer(self)
        self.m.new_Records(True)
        self.table_view.setModel(self.m)
        self.locality = locality(self, apiKeys.google_API_key)
        self.w.action_Open.triggered.connect(self.m.open_CSV)
        self.w.action_Save_As.triggered.connect(self.m.save_CSV)
        self.w.action_New_Records.triggered.connect(self.m.new_Records)
        self.w.action_undo.triggered.connect(self.m.undo)
        self.w.action_redo.triggered.connect(self.m.redo)
        self.w.action_About_collBook.triggered.connect(self.callAboutDialog)
        
        self.w.action_Context_Help.triggered.connect(QWhatsThis.enterWhatsThisMode)
        
        self.w.action_Exit.triggered.connect(lambda: sys.exit(app.exec_()))
        self.w.action_Settings.triggered.connect(self.toggleSettings)
        self.w.button_associatedTaxa.clicked.connect(self.toggleAssociated)
        self.w.action_Reverse_Geolocate.triggered.connect(self.m.geoRef)
        self.w.toolButton_reverseGeolocate.clicked.connect(self.m.geoRef)
        self.w.action_Verify_Taxonomy.triggered.connect(self.m.verifyTaxButton)
        self.w.toolButton_verifyTaxonomy.clicked.connect(self.m.verifyTaxButton)
        self.w.action_Verify_All.triggered.connect(self.m.verifyAllButton)
        self.w.action_Export_Labels.triggered.connect(self.exportLabels)
        self.w.pushButton_newSite.clicked.connect(self.m.addNewSite)
        self.w.pushButton_newSpecimen.clicked.connect(self.m.addNewSpecimen)
        self.w.pushButton_newSpecimen_2.clicked.connect(self.m.addNewSpecimen)  # copy of above, except placed on specimen view
        self.w.pushButton_duplicateSpecimen.clicked.connect(self.m.duplicateSpecimen)
        self.w.pushButton_deleteSite.clicked.connect(self.m.deleteSite)
        self.w.pushButton_deleteRecord.clicked.connect(self.m.deleteSpecimen)
        self.w.toolButton_sitesToApply_SelectNone.clicked.connect(self.clearSitesToApply)
        self.w.toolButton_sitesToApply_SelectAll.clicked.connect(self.selectAllSitesToApply)
        self.w.action_Export_Records.triggered.connect(self.exportRecords)
        #self.w.actionTestFunction.triggered.connect(self.timeitTest)  # a test function button for debugging or time testing
        #self.w.actionTestFunction.triggered.connect(self.m.assignCatalogNumbers)        
        self.w.actionTestFunction.triggered.connect(self.userSciNameInput)
        # update the preview window as dataframe changes
        self.m.dataChanged.connect(self.updatePreview)
        self.updateAutoComplete()
        self.versionCheck()
        
    def versionCheck(self):
        """ checks the github repo's latest release version number against
        local and offers the user to visit the new release page if different"""
        #  be sure to only do this once a day.
        today = str(date.today())
        lastChecked = self.settings.get('date_versionCheck', today)
        self.w.date_versionCheck = today
        if today != lastChecked:
            import requests
            from requests.exceptions import ConnectionError
            import webbrowser
            apiURL = 'https://api.github.com/repos/CapPow/collBook/releases/latest'
            try:
                apiCall = requests.get(apiURL)
                status = str(apiCall)
            except ConnectionError:
                #  if no internet, don't bother the user.
                return
            result = apiCall.json()
            if '200' in status:  # if the return looks bad, don't bother user
                url = result['html_url']
                version = result['tag_name']
                if version.lower() != self.w.version.lower():
                    message = f'A new version ( {version} ) of collBook has been released. Would you like to visit the release page?'
                    title = 'collBook Version'
                    answer = self.userAsk(message, title, inclHalt = False)
                    if answer:# == QMessageBox.Yes:
                        link=url
                        self.showMinimized() #  hide the app about to pop up.
                        #  instead display a the new release
                        webbrowser.open(link,autoraise=1)
            self.settings.saveSettings()  # save the new version check date

    def callAboutDialog(self):
        ab = aboutDialog()
        ab.exec_()
        #result = dialog.exec_()

    def toggleSettings(self):
        if self.settings.isHidden():
            self.settings.show()
        else:
            self.settings.hide()

    def toggleAssociated(self):
        if self.associatedTaxaWindow.isHidden():
            self.associatedTaxaWindow.populateAssociatedTaxa()
            selType, siteNum, specimenNum = self.getTreeSelectionType()
            self.associatedTaxaWindow.setWindowTitle('Associated taxa')
            self.associatedTaxaWindow.associatedMainWin.label_UserMsg.setText(f'Select associated taxa for site {siteNum}')
            self.associatedTaxaWindow.show()
        else:
            self.associatedTaxaWindow.associatedList.clear()
            self.associatedTaxaWindow.close()

    def getTreeSelectionType(self):
        """ checks the tree_widget's type of selection """
        # TODO alter selType to become a custom attribute of mainWindow, setting it upon changes. This should reduce checks with this function
        try:
            itemSelected = self.tree_widget.currentItem()
            text = itemSelected.text(0).split('(')[0].strip()
        except AttributeError as e:  # if not force "All Records"
            text = "All Records"
        siteNum = None
        specimenNum = None
        if text == "All Records":
            selType = 'allRec'
        elif "Site" in text:
            selType = 'site'
            siteNum = text.replace('Site ','').strip()
        elif "-" in text:
            selType = 'specimen'
            siteNum, specimenNum = text.split('-')
            
        return selType, siteNum, specimenNum

    def updateTableView(self):
        """ updates the table_view, and form_view's current tab
        called after tree_widget's selection change """
        # TODO rename this, as it does more than upates tableview. Basically alters scope of user's view
        selType, siteNum, specimenNum = self.getTreeSelectionType()
        rowsToHide = self.m.getRowsToHide(selType, siteNum, specimenNum)
        rowNums = range(self.m.rowCount())
        for row in rowNums:
            if row not in rowsToHide:
                self.table_view.showRow(row)
            else:
                self.table_view.hideRow(row)

        if selType != 'allRec':
            topVisible = [x for x in rowNums if x not in rowsToHide]
            try:
                #TODO make consideration for avoiding this if the last action was an edit.
                topVisible = min(topVisible)
                self.table_view.selectRow(topVisible)
            except ValueError:
                self.table_view.clearSelection()
        self.updatePreview()
        if selType == 'site':
            self.statusBar.label_status.setText("  Site View  ")
            self.form_view.setCurrentIndex(1) #swap to site tab
        elif selType == 'specimen':
            self.statusBar.label_status.setText("Specimen View")
            self.form_view.setCurrentIndex(2) #swap to specimen tab
        else: #  probably all records
            self.statusBar.label_status.setText(" All Records  ")
            self.form_view.setCurrentIndex(0) #all records
        self.form_view.fillFormFields()

    def selectTreeWidgetItemByIndex(self, i):
        """ helper function called when form_view's tab index is clicked Is 
        intended to change the user's view to all records when the all records
        tab is clicked """
        if i == 0:
            self.selectTreeWidgetItemByName('All Records')

    def selectTreeWidgetItemByName(self, name):
        """ selects an item on the nav tree_widget. Permits site selection without
        the parenthetical (n) value. ie: 'Site 5' would find 'Site 5 (12)' """
        iterator = QTreeWidgetItemIterator(self.tree_widget, QTreeWidgetItemIterator.All)
        if name[:5] == 'Site ':  # handle changing record counts at set siteNumbers
            name = name.split('(')[0].strip()
        while iterator.value():
            item = iterator.value()
            if name in item.text(0):
                self.tree_widget.setCurrentItem(item,1)
                break
            iterator +=1

    def expandCurrentTreeWidgetItem(self):
        """ expands the currently selected tree_widget item """
        itemSelected = self.tree_widget.currentItem()
        selectionIndex = self.tree_widget.indexFromItem(itemSelected)
        self.tree_widget.expand(selectionIndex)

    def setTreeSelectionByType(self, selType, siteNum, specimenNum):
        """ sets tree selection using the returned values of
        getTreeSelectionType called by pandastablemodel when redoing
        or undoing other df states """
        if selType == 'allRec':
            text = "All Records"
        elif selType == 'site':
            text = f'Site {siteNum}'
        elif selType == 'specimen':
            text = f'{siteNum}-{specimenNum}'
        self.selectTreeWidgetItemByName(text)

    def timeitTest(self):
        """ debugging / improving space for testing various functions or their timings """

        from datetime import datetime
        a = datetime.now()
        iterCount = 10000
        for i in range(iterCount):
            listComp = [x for x in range(0, self.m.rowCount()) if not self.table_view.isRowHidden(x)]
        b = datetime.now()
        listCompTime = b - a
        listCompTime = int((listCompTime.total_seconds() / iterCount) * 1000000) # microseconds
        print(f'listComp = {listCompTime} (µs)')
        a = datetime.now()
        for i in range(iterCount):
            treeSel = self.m.getRowsToProcess(*self.getTreeSelectionType())
        b = datetime.now()
        treeSelTime = b - a
        treeSelTime = int((treeSelTime.total_seconds() / iterCount) * 1000000) # microseconds
        print(f'treeSel = {treeSelTime} (µs)')

    def getVisibleRows(self):
        """ returns a list of indicies which are visible """
        visibleRows = [x for x in range(0, self.m.rowCount()) if not self.table_view.isRowHidden(x)]
        return visibleRows
    
    def getVisibleRowData(self):
        """ queries the table_view for selected rows 
        and returns associated rowData """
        rowsVisible = self.getVisibleRows()
        if rowsVisible:
            rowData = self.m.retrieveRowData(rowsVisible)
            rowData = self.m.getSelectedLabelDict(rowData)
        else:
            rowData = None
        return rowData

    def userSciNameInput(self, title = "", message = ""):
        """ opens a cusotm user dialog and requests a scientificName """
        dlg = sciNameDialog()
        res = dlg.textBox(self.wordList, message, title)
        return res

    # TODO for simplicity, move all userASK and userNOTIFY functions into mainWindow and alter calls in other modules to use it.
    def userAsk(self, text, title='', inclHalt=True, retry=False, detailText=None):
        """ a general user dialog with yes / cancel options"""
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Question)
        msg.setText(text)
        msg.setWindowTitle(title)
        if retry:
            msg.setIcon(QMessageBox.Warning)
            msg.setStandardButtons(QMessageBox.Retry | QMessageBox.Cancel)
        else:
            msg.setStandardButtons(QMessageBox.No | QMessageBox.Yes)
        if detailText != None:
            msg.setDetailedText(detailText)
        if inclHalt:
            halt = msg.addButton('Halt Process', QtWidgets.QMessageBox.ResetRole)
            halt.clicked.connect(self.statusBar.flipCancelSwitch)
        msg.setDefaultButton(QMessageBox.No)
        reply = msg.exec_()
        if reply == QMessageBox.Yes:
            return True
        elif reply == QMessageBox.No:
            return False
        elif reply == QMessageBox.Cancel:
            return False
        elif reply == QMessageBox.Retry:
            return True
        else:
            return "cancel"


    def userNotice(self, text, title='', detailText = None, retry=False, inclHalt=True):
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Warning)
        msg.setText(text)
        if detailText != None:
            msg.setDetailedText(detailText)
        #msg.setInformativeText("This is additional information")
        msg.setWindowTitle(title)
        if retry:
            msg.setStandardButtons(QMessageBox.Ok | QMessageBox.Retry)
        else:
            msg.setStandardButtons(QMessageBox.Ok)            
        if inclHalt:
            halt = msg.addButton('Halt Process', QtWidgets.QMessageBox.ResetRole)
            halt.clicked.connect(self.statusBar.flipCancelSwitch)
        reply = msg.exec_()
        return reply
        

    def exportRecords(self):
        """ saves a pdf file of the labels AND a csv of the records prepared for
        SERNEC upload. """
        saved = False  # have both files successfully saved? (not yet)
        # show the dialog
        while saved is False:
            if not self.testRunLabels():
                return False
            chosenFileName, _ =  QtWidgets.QFileDialog.getSaveFileName(self, "Export Labels", "", "Label PDFs (*.pdf)")
            if chosenFileName == "":  # The user probably pressed Cancel
                return None
            else:
                fileName = chosenFileName               
                fileExtension = Path(chosenFileName).suffix
                if fileExtension != '':
                    fileName = fileName.replace(fileExtension,'')
                csvFileName = f'{fileName}.csv'
                pdfFileName = f'{fileName}.pdf'
                if Path(csvFileName).is_file():
                    message = f'Record file named: "{csvFileName}" already exist! OVERWRITE the Record (csv) file?'
                    title = 'Export Records'
                    answer = self.userAsk(message, title)
                    if answer:
                        readyToSave = True  # have we settled on the fileName(S)?
                    else: 
                        readyToSave = False # have we settled on the fileName(S)?
                else:
                    readyToSave = True # have we settled on the fileName(S)?
                if readyToSave:  # if fileName(s) are settled...
                    self.m.assignCatalogNumbers()  # the assignCatalogNumber function checks user settings before applying
                    rowsToProcess = self.m.getRowsToProcess(*self.getTreeSelectionType())
                    # Permission flag handles cases where pdf preview is open, yet user wants to overwrite the open file.
                    permission = False
                    while permission == False:
                        try:
                            labelSuccess = self.exportLabels(fileName = pdfFileName)
                            if labelSuccess:
                                outDF = self.m.datatable.iloc[rowsToProcess, ]
                                outDF = outDF.loc[outDF['specimenNumber'] != '#']
                                csvName = csvFileName
                                self.m.export_CSV(df = outDF, fileName = csvFileName)
                                saved = True
                                permission = True
                        except PermissionError:
                            #  Note, under this condition the catalog numbers might be assigned yet not used.
                            title = "Permission Error"
                            msg = f"Attempting to overwrite a file which is open in another program. Export cannot proceed until you close that program."
                            details = f'One or both of the following files may be open in another program. It must be closed to proceed with the export.\n{pdfFileName}\n{csvFileName}'
                            askReply = self.userAsk(msg, title, retry=True, inclHalt=False, detailText=details)
                            if askReply:
                                permission = False
                            else:
                                # even though not saved or permissed, do this to break loops
                                permission = True
                                saved = True

    def testRunLabels(self):
        """ Tests generating the labels to ensure the contents all fit.
        Returns True or False depending on test's results."""
        try:
            # generate test labels and toss them out. to test for oversize warnings
            self.p.genLabelPreview(self.getVisibleRowData())
            return True
        except LayoutError:
            msg = QMessageBox()
            msg.setIcon(QMessageBox.Warning)
            msg.setText("""The content of one or more of your labels is too large for the label dimentions. Alter your settings, and try again.""")
            msg.setWindowTitle('Label Generation Error')
            msg.setStandardButtons(QMessageBox.Ok)
            msg.exec_()
            return False

    def exportLabels(self, fileName = None):
        """ bundles records up and passes them to printlabels.genPrintLabelPDFs() """
        try:
            rowsToProcess = self.m.getRowsToProcess(*self.getTreeSelectionType())
            outDF = self.m.datatable.iloc[rowsToProcess, ]
            outDict = self.m.getSelectedLabelDict(outDF)
            self.p.genPrintLabelPDFs(outDict, defaultFileName = fileName)
            return True
        except LayoutError:
            from PyQt5.QtWidgets import QMessageBox
            msg = QMessageBox()
            msg.setIcon(QMessageBox.Warning)
            msg.setText("""The content of one or more of your labels is too large for the label dimentions. Alter your settings, and try again.""")
            msg.setWindowTitle('Label Export Error')
            msg.setStandardButtons(QMessageBox.Ok)
            msg.exec_()
            return False


    def updatePreview(self):
        """ updates the pdf preview window """
        #TODO modify this to be called from within the pdfviewer class
        rowData = self.getVisibleRowData()
        selType, siteNum, specimenNum = self.getTreeSelectionType()
        errorType = False
        if (isinstance(rowData, list)) & (selType != 'allRec'):
            if (selType == 'site') & (len(rowData) > 1):
                rowData = [rowData[1]]  # only want first row, but other functions expect a list
            else:
                rowData = [rowData[0]]
            try:
                pdfBytes = self.p.genLabelPreview(rowData)  # retrieves the pdf in Bytes
            except LayoutError:  # Not enough space on label for the content
                pdfBytes = None
                errorType = 'oversize'
        else:  # there is not appropriate row data to preview
            pdfBytes = None
            errorType = 'preview' # display generic "Preview window text"
        self.pdf_preview.load_preview(pdfBytes, errorType)  # starts the loading display process  
        #self.settings.setMaxZoom()

    def updatePreviewZoom(self, val):
        """ changes the value_Zoom setting stored in self.settings, used by
        pdfviewer.py to determine the size of the preview window. Additionally,
        updates the label_zoomLevel's text in MainWindow """
        try:
            self.settings.setMaxZoom()
            self.updatePreview()  # update the pdfPreview (this could get cpu intensive)
        except AttributeError:
            pass  # It gets called too early on start up, this skips it

    def updateAutoComplete(self):
        """ updates the Completer's reference text based on the kingdom """

        value_Kingdom = self.settings.get('value_Kingdom', 'Plantae')
        if value_Kingdom == 'Plantae':
            nameCol = 'complete_name'
        if value_Kingdom == 'Fungi':
            nameCol = 'normalized_name'
        stream = QFile(f':/rc_/{value_Kingdom}_Reference.csv')
        if stream.open(QFile.ReadOnly):
            df = StringIO(str(stream.readAll(), 'utf-8'))
            stream.close()     
        # completer.setCompletionMode(QCompleter.InlineCompletion)
#		completer.maxVisibleItems=10
#		completer.setCaseSensitivity(Qt.CaseInsensitive)
		# make the completer selection also erase the text edit
 #       completer.activated.connect(self.cleartext,type=Qt.QueuedConnection)
        
        wordList = pd.read_csv(df, encoding = 'utf-8', dtype = 'str')
        wordList = wordList[nameCol].str.capitalize().tolist()
        self.wordList = sorted(wordList)
        
        completer = QCompleter(self.wordList, self.lineEdit_sciName)
        completer.setCaseSensitivity(Qt.CaseInsensitive)
        self.lineEdit_sciName.setCompleter(completer)

        completerAssociated = QCompleter(self.wordList, self.associatedTaxaWindow.lineEdit_newAssociatedTaxa)
        completerAssociated .setCaseSensitivity(Qt.CaseInsensitive)
        self.associatedTaxaWindow.associatedMainWin.lineEdit_newAssociatedTaxa.setCompleter(completerAssociated)
       
    def getSelectSitesToApply(self):
        """ queries the site_tree_widget to determine which are checked """
        fieldNumbers = self.m.getSiteSpecimens()
        siteNumbers = list(set([x[0] for x in fieldNumbers]))
        if self.w.radioButton_applyAllRecords.isChecked():
            return siteNumbers
        else:
            siteNumbers = []
            iterator = QTreeWidgetItemIterator(self.site_tree_widget, QTreeWidgetItemIterator.Checked)
            while iterator.value():
                siteText = iterator.value().text(0)
                siteNum = siteText.split()[-1]
                siteNumbers.append(siteNum)
                iterator += 1
            return siteNumbers
        
    def selectAllSitesToApply(self):
        """ checks all objects in site_tree_widget, may be useful if the user
        wants to select all but a few in the list"""
        iterator = QTreeWidgetItemIterator(self.site_tree_widget, QTreeWidgetItemIterator.NotChecked)
        while iterator.value():
            obj = iterator.value()
            obj.setCheckState(0, Qt.Checked)
            iterator += 1

    def clearSitesToApply(self):
        """ unchecks all objects in site_tree_widget """
        iterator = QTreeWidgetItemIterator(self.site_tree_widget, QTreeWidgetItemIterator.Checked)
        while iterator.value():
            obj = iterator.value()
            obj.setCheckState(0, Qt.Unchecked)
            iterator += 1

    def populateTreeWidget(self):
        """ populates the navigation TreeWidget with the records nested 
        within sites. Also populates site_tree_widget with site numbers"""
        # store the current selection(s)
        itemSelected = self.tree_widget.currentItem()
        sites_Selected = self.getSelectSitesToApply()
        sites_Selected = [f'Site {x}' for x in sites_Selected]
        try:
            text = itemSelected.text(0)
        except AttributeError:
            text = 'All Records'
        self.tree_widget.clear()
        self.site_tree_widget.clear()
        fieldNumbers = self.m.getSiteSpecimens()
        siteNumbers = list(set([x[0] for x in fieldNumbers]))
        try:
            siteNumbers.sort(key = int)
        except ValueError:
            pass
        # build a hierarchical structure of QTreeWidgetItem(s) to fill the tree with
        self.tree_widget.addTopLevelItem(QTreeWidgetItem(["All Records"]))
        for siteNum in siteNumbers:
            site_tree_text = f'Site {siteNum}'
            site_tree_item = QTreeWidgetItem([site_tree_text])
            if site_tree_text in sites_Selected:
                site_tree_item.setCheckState(0, Qt.Checked)  # update site_tree_widget
            else:
                site_tree_item.setCheckState(0, Qt.Unchecked)  # update site_tree_widget
            self.site_tree_widget.addTopLevelItems([site_tree_item]) # fill in site_tree_widget
            
            # now start on the navigation "tree_widget" object.            
            specimenNumbers = list(set([y for x, y in fieldNumbers if x == siteNum and y != '#']))
            specimenNumbers.sort(key = int)
            site = QTreeWidgetItem([f'Site {siteNum} ({len(specimenNumbers)})'])
            siteChildren = []
            for i in specimenNumbers:
                # where i is a specimen number for a site
                label = [f'{siteNum}-{i}']
                child = QTreeWidgetItem(label)
                siteChildren.append(child)
            site.addChildren(siteChildren)
            # add the list of sites (with children) to the master list
            self.tree_widget.addTopLevelItems([site])
        # return to the selection (if it exists)
        self.selectTreeWidgetItemByName(text)
    

# wrap GUI's main loop with the exception logger
try:
    app = QtWidgets.QApplication(sys.argv)
    w = MyWindow()
    if w.settings.get('value_DarkTheme', False):
        app.setStyleSheet(qdarkstyle.load_stylesheet_pyqt5())
    w.show()
    sys.exit(app.exec_())
except Exception:
    # given an exception, log it then handle normally.
    log_crash()
    raise
