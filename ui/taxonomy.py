#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sun Jan 11 10:33:55 2019

@authors: Caleb Powell, Jacob Motley

"""
import pandas as pd
import re
import Resources_rc
from PyQt5.QtWidgets import QMessageBox
from PyQt5.QtCore import QFile
import pykew.powo as powo
from pykew.powo_terms import Name as powoName

import datetime
import time
import requests
from requests.exceptions import ReadTimeout
import json

class taxonomicVerification():
    def __init__(self, settings, parent, editable = True, *args):
        super(taxonomicVerification, self).__init__()
        self.parent = parent
        self.settings = settings       
        # precompile regex cleaning string to save time.
        self.strNormRegex = re.compile('[^a-z ]')
        # container to store this session's alignments. Addressing feedback
        # from Alaina Krakowiak concerning redundant alignment dialogs.
        # structured as: {'input sci name':('aligned sci name', 'alignedauthority')}
        self.readTaxonomicSettings()
        self.sessionAlignments = {}
    
    def readTaxonomicSettings(self):
        """ Fetches the most up-to-date taxonomy relevant settings"""
        # TODO check if this is redundant, shouldn't the settings window "Save and exit" button establish these changes?
        # meaning, whenever this was called the function could just go straight to the settings module and use it?
        # additionally, this may be reloading the local alignments excessively
        # The function is called in pandastablemodel (at least)
        #which service to utalize to make alignments
        self.TaxAlignSource = self.settings.get('value_TaxAlignSource')
        # how to handle name reccomendations
        self.NameChangePolicy = self.settings.get('value_NameChangePolicy')
        # how to handle authority reccomendations
        self.AuthChangePolicy = self.settings.get('value_AuthChangePolicy')
        # tnrs score threshold
        self.value_TNRS_Threshold = self.settings.get('value_TNRS_Threshold')
        # which kingdom we're interested in
        current_value_Kingdom = self.settings.get('value_Kingdom')
        try:  # see if it's necessary to reload the local_Reference
            if self.value_Kingdom != current_value_Kingdom:
                raise AttributeError # force exception and boolean into same outcome
        except AttributeError:  # load the local reference
            self.value_Kingdom = current_value_Kingdom
            if '(local)' in self.TaxAlignSource:       
                self.loadLocalRef()

    def loadLocalRef(self):
        from io import StringIO
        stream = QFile(f':/rc_/{self.value_Kingdom}_Reference.csv')
        if stream.open(QFile.ReadOnly):
            df = StringIO(str(stream.readAll(), 'utf-8'))
            stream.close()
            self.local_Reference = pd.read_csv(df, encoding = 'utf-8', dtype = 'str')

    def retrieveAlignment(self, querySciName, retrieveAuth=False):
        """ parses the settings for the proper alignment policy.
        Returns tuple of aligned name and aligned authority.
        Can optionally be used to retrieve the authority of a potentially
        unaccepted taxon. """
        if self.TaxAlignSource == 'Catalog of Life (web API)':
            result = self.getCOLWeb(querySciName, retrieveAuth)
        elif self.TaxAlignSource == 'ITIS (local)':
            result = self.getITISLocal(querySciName, retrieveAuth)
        elif self.TaxAlignSource == 'ITIS (web API)':
            result = self.getITISWeb(querySciName, retrieveAuth)
        elif self.TaxAlignSource == 'Taxonomic Name Resolution Service (web API)':
            result = self.getTNRS(querySciName, retrieveAuth)
        elif self.TaxAlignSource == 'Plants of the World (web API)':
            result = self.getPoWOWeb(querySciName, retrieveAuth)
        elif self.TaxAlignSource == 'MycoBank (local)':
            result = self.getMycoBankLocal(querySciName, retrieveAuth)
        elif self.TaxAlignSource == 'MycoBank (web API)':
            result = self.getMycoBankWeb(querySciName, retrieveAuth)
        else:
            result = (None, None, None)

        if retrieveAuth:
            result = result[1]
        return result

    def updateSessionAlignments(self, querySciName, results):
        """ updates the session alignments dict to remember alignments.
        these sesson alignments are reset when program opens or settings are
        saved"""

        self.sessionAlignments[querySciName] = results

    def verifyTaxonomy(self, rowData):
        """general method to align taxonomy and retrieve authority.
        accepts a df row argument, treats it as a dictionary and makes
        refinements. Returning a the modified argument."""
        for col in rowData.keys():
            rowData[col] = str(rowData[col])

        if rowData['scientificName'] in ['', None]:
            return rowData

        try:
            # ensure the first word is capitalized regardless
            rowData['scientificName'] = rowData['scientificName'].capitalize()
            rowNum = f"{rowData['siteNumber']}-{rowData['specimenNumber']}"
            scientificName = rowData['scientificName']
            scientificNameAuthorship = rowData['scientificNameAuthorship'].strip()
            querySciName = self.normalizeStrInput(scientificName)
            #  check with the session results before moving on.
            sessionResults =  self.sessionAlignments.get(querySciName, False)
            if sessionResults:
                sessionName, sessionAuth, sessionFamily = sessionResults
                rowData['scientificName'] = sessionName
                rowData['scientificNameAuthorship'] = sessionAuth
                rowData['family'] = sessionFamily
                return rowData

            result = self.retrieveAlignment(querySciName)
            if result == (False, False, False):
                # if the alignment failed to respond
                return rowData
            resultSciName, resultAuthor, resultFam = result
            # Decide how to handle resulting data
            keptResult = False  # flag to det if the alignment result was kept
            changeAuth = False  # flag to determine if the authority needs altered.
            if resultSciName is None:  # if no scientificName was returned
                message = f'No {self.value_Kingdom} results for "{scientificName}" (# {rowNum}) found using {self.TaxAlignSource}.\n This may be a typo, would you like to reenter the name?'
                reply = self.parent.userSciNameInput(f'{rowNum}: Taxonomic alignment', message)
                if reply:
                    rowData['scientificName'] = reply
                    rowData = self.verifyTaxonomy(rowData)
                return rowData
            # if the returned result is not the scientificName, check policies
            if resultSciName.lower() != scientificName.lower():
                if self.NameChangePolicy == 'Accept all suggestions':
                    rowData['scientificName'] = resultSciName
                    rowData['family'] = resultFam
                    changeAuth = True
                    keptResult = True
                elif self.NameChangePolicy == 'Always ask':
                    message = f'Change {scientificName} to {resultSciName} at record {rowNum}?'
                    answer = self.parent.userAsk(message, 'Taxonomic alignment')
                    if answer:
                        rowData['scientificName'] = resultSciName
                        rowData['family'] = resultFam
                        keptResult = True
                        changeAuth = True
            # the returned result is equal to the scientificName...
            else:  # treat it as if we kept the returned result
                keptResult = True
                rowData['family'] = resultFam
            if changeAuth:
                # if the scientificName changed already, update the author
                rowData['scientificNameAuthorship'] = resultAuthor
            else:
                if not keptResult:
                    # condition to retrieve authority for potentially non-accepted name
                    # in favor of simplicity, the family name will not be updated under this condition
                    resultAuthor = self.retrieveAlignment(querySciName, retrieveAuth=True)

                if resultAuthor.lower() not in [scientificNameAuthorship.lower(), None]:
                    # if the authors don't match check user policies
                    # conditional actions based on AuthChangePolicy
                    if self.AuthChangePolicy == 'Accept all suggestions':
                        rowData['scientificNameAuthorship'] = resultAuthor
                    elif self.AuthChangePolicy == 'Fill blanks':
                        if scientificNameAuthorship == '':  # if it is blank fill it
                            rowData['scientificNameAuthorship'] = resultAuthor
                        else:  # if not blank, ask.
                            message = f'Update author of {rowData["scientificName"]} from:\n{scientificNameAuthorship} to {resultAuthor} at record {rowNum}?'
                            answer = self.parent.userAsk(message, 'Authority alignment')
                            if answer:
                                rowData['scientificNameAuthorship'] = resultAuthor

                    elif self.AuthChangePolicy == 'Always ask':
                        if scientificNameAuthorship == '':  # custom dialog box if the field was empty. 'Always ask' may be annoying!
                            message = f'Fill in blank author of {rowData["scientificName"]} to {resultAuthor} at record {rowNum}?'
                        else:
                            message = f'Update author of {rowData["scientificName"]} from:\n{scientificNameAuthorship} to {resultAuthor} at record {rowNum}?'
                        answer = self.parent.userAsk(message, 'Authority alignment')
                        if answer:
                            rowData['scientificNameAuthorship'] = resultAuthor
            # update sessionAlignments to remember these results for this session
            results = (rowData['scientificName'],
                       rowData['scientificNameAuthorship'],
                       rowData['family'])
            self.sessionAlignments[querySciName] = results
        except:
            pass
        return rowData

    def normalizeStrInput(self, inputStr, retrieveAuth=False):
        """ returns a normalized a scientificName based on string input.
        is used to prepare queries """
        # Strip non-alpha characters
        # Strip additional whitespace from ends
        toCleanString = inputStr.lower()
        toCleanString = self.strNormRegex.sub('', toCleanString).strip()
        wordList = toCleanString.split()
        if len(wordList) > 2:
            omitList = ['var', 'ssp', 'subsp', 'x', 'f']
            toCleanString = ' '.join([x for x in wordList if x not in omitList])
        outputStr = toCleanString
        
        return outputStr

    def getITISLocal(self, inputStr, retrieveAuth=False):
        """ uses local itis reference csv to attempt alignments """
        try:
            df = self.local_Reference
        except AttributeError:
            self.loadLocalRef()
            df = self.local_Reference

        result = (None, None, None)

        if retrieveAuth:
            acceptedRow = df[df['normalized_name'] == inputStr]
        else:
            try:
                tsn_accepted = df[df['normalized_name'] == inputStr]['tsn_accepted'].values[0]
            except IndexError:
                return result
            acceptedRow = df[df['tsn'] == tsn_accepted]
            
        if len(acceptedRow) > 0:
            try:
                acceptedName = acceptedRow['complete_name'].values[0]
            except IndexError:
                acceptedName = inputStr
            try:
                acceptedAuthor = acceptedRow['taxon_author_id'].values[0]
            except IndexError:
                acceptedAuthor = ""
            try:
                family = acceptedRow['family'].values[0]
            except IndexError:
                family = ""
            result = (acceptedName, acceptedAuthor, family)
        return result

    def getITISWeb(self, inputStr, retrieveAuth=False):
        """ https://www.itis.gov/ws_description.html """
        print('go get ITIS data')
        
    def getMycoBankLocal(self, inputStr, retrieveAuth=False):
        """ uses local reference csv to attempt alignments """
        try:
            df = self.local_Reference
        except AttributeError:
            self.loadLocalRef()
            df = self.local_Reference

        result = (None, None, None)
        
        if retrieveAuth:
            acceptedRow = df[df['normalized_name'] == inputStr]
        else:
            try:
                acceptedName = df[df['normalized_name'] == inputStr]['Accepted_name'].values[0]
            except IndexError:
                return result
            acceptedRow = df[df['Accepted_name'] == acceptedName]
        if len(acceptedRow) > 0:
            try:
                acceptedName = acceptedRow['Accepted_name'].values[0]
            except IndexError:
                acceptedName = inputStr
            try:
                acceptedAuthor = acceptedRow['Authors'].values[0]
            except IndexError:
                acceptedAuthor = ""
            try:
                family = acceptedRow['family'].values[0]
            except IndexError:
                family = ""
            acceptedName = acceptedName.capitalize()
            result = (acceptedName, acceptedAuthor, family)
        return result

    def getMycoBankWeb(self, inputStr, retrieveAuth=False):
        """http://www.mycobank.org/Services/Generic/Help.aspx?s=searchservice"""
        print('go get mycobank data')

    def getCOLWeb(self, inputStr, retrieveAuth=False, timeout = 5):
        """ uses Catalog of life reference to attempt alignments
        retrieveAuth: boolean, forces retrieval of authorship regardless of name status"""
        
        result = (None, None)
        #result = (None, None, None)
        
        # a list of urls for col, starting with most recent and then specifying current year, then current year -1
        urlInputStr = inputStr.replace(' ','%20')
        urlList = [f'http://webservice.catalogueoflife.org/col/webservice?name={urlInputStr}&format=json&response=full',
                   f'http://webservice.catalogueoflife.org/annual-checklist/{datetime.datetime.now().year}/webservice?name={urlInputStr}&format=json&response=full',
                   f'http://webservice.catalogueoflife.org/annual-checklist/{datetime.datetime.now().year - 1 }/webservice?name={urlInputStr}&format=json&response=full']

        for url in urlList:
            try:
                response = requests.get(url, timeout = timeout)
                time.sleep(1)  # use a sleep to be polite to the service
            except ReadTimeout:
                message = 'Catalog of Life request timed out. This may be an internet connectivity problem, or an issue with the service. No changes have been made.'
                details = 'Check internet connection, or try a different alignment service. If you do not have internet connectivity, use the local alignment service.'
                notice = self.parent.userNotice(message, 'Taxonomic alignment', inclHalt=True, retry=True)
                if notice == QMessageBox.Retry:  # if clicked retry, do it.
                    timeout += 2
                    # add to timeout before retrying
                    return self.getCOLWeb(inputStr, retrieveAuth, timeout = timeout)
                else:
                    return False
            if response.status_code == requests.codes.ok:
                # returns a list of "results" each result is a seperate dict
                data = response.json().get('results')
                # restrict results to the best answer for the appropriate kingdom regardless of accepted_name status
                # COL returns classifications for accepted names, otherwise it is nested under the key "accepted_name"
                data = [x for x in data if
                               x.get('classification', [{}])[0].get('name', '') == self.value_Kingdom or
                               x.get('accepted_name', {}).get('classification', [{}])[0].get('name', '') == self.value_Kingdom][0]

                if retrieveAuth:
                    resultName = data.get('name')
                    resultAuth = data.get('author')
                    family = None
                    result = (resultName, resultAuth, family)
                    return result
                else:
                    try:
                        # if there is an 'accepted_name' key, retrieve that entry
                        if data.get('accepted_name', False):
                            data = data.get('accepted_name')
                            print('name was not accepted')
                        # otherwise the existing 'data' should already hold the accepted name
                        if data.get('name_status','') != 'accepted name':
                            # verify to be sure, raise exception if something managed to fail here
                            raise Exception
                        classifications = data.get('classification', False)
                        if classifications:
                            # if there are classifications, retrieve the family name
                            family = [x for x in classifications if x.get('rank', '') == 'Family'][0].get('name', '')
                        else:
                            family = None
                        acceptedName = data.get('name')
                        acceptedAuthor = data.get('name_html').split('</i> ')[1].strip()
                        
                        result = (acceptedName, acceptedAuthor, family)
                        #result = (acceptedName, acceptedAuthor)
                        return result
                    except Exception as e:
                        print(e)
                        pass
        return result

    def getTNRS(self, inputStr, retrieveAuth=False, timeout = 5):
        """ uses the Taxonomic Name Resolution Service API 
        hosted through iPlant."""

        #result = (None, None)
        result = (None, None, None)
        score = 0
        urlInputStr = inputStr.replace(' ','%20')
        # TODO add an optional dialog box with a list of the top returned results. Allow user to pick from list.
        url = f'http://tnrs.iplantc.org/tnrsm-svc/matchNames?retrieve=best&names={urlInputStr}'
        try:
            response = requests.get(url, timeout = timeout)
        except ReadTimeout:
            message = 'Taxonomic Name Resolution Service request timed out. This may be an internet connectivity problem, or an issue with the service. No changes have been made.'
            details = 'Check internet connection, or try a different alignment service. If you do not have internet connectivity, use the local alignment service.'
            notice = self.parent.userNotice(message, 'Taxonomic alignment', inclHalt=True, retry=True)
            if notice == QMessageBox.Retry:  # if clicked retry, do it.
                timeout += 2
                # add to timeout before retrying
                return self.getTNRS(inputStr, retrieveAuth, timeout = timeout)
            else:
                return False
        if response.status_code == requests.codes.ok:
            data = response.json().get('items', None)[0]
            time.sleep(1)  # use a sleep to be polite to the service

            try:
                if retrieveAuth:
                    # if authority requested for potentially non-accepted name
                    acceptedName = data.get('nameScientific', None)
                    acceptedAuthor = data.get('authorAttributed', None)
                    family = None
                else:
                    # otherwise, retrieve accepted details.
                    acceptedName = data.get('acceptedName', None)
                    acceptedAuthor = data.get('acceptedAuthor', None)
                    family = data.get('family', None)
                score = float(data.get('scientificScore', 0)) # the confidence in the return
            except Exception as e:
                print(e)
                pass
            if score >= float(self.value_TNRS_Threshold)/100:
                result = (acceptedName, acceptedAuthor, family)

        return result

    def getPoWOWeb(self, inputStr, retrieveAuth=False, timeout=1):
        """ uses Plants of the World reference to attempt alignments """
        # see: http://www.plantsoftheworldonline.org/search-help
        # build the query with specified kingdom
        query = { powoName.full_name: inputStr, powoName.kingdom: self.value_Kingdom }
        results = powo.search(query)  #produces iterator full of dicts
        # build dummy target_record in case no appropriate entries are found
        target_record = {'name':None, 'author':None, 'family':None}
        # iterate over results until appropriate target_record is found
        try:
            for entry in results:
                if retrieveAuth:
                    # if seeking authorship of a potentially un-accepted query
                    target_record = entry
                    break
                elif entry.get('accepted', False):
                    # if entry is accepted
                    target_record = entry
                    break
                else:
                    # otherwise check the entry for a synonymOf entry
                    syn_record = entry.get('synonymOf', False)
                    # sadly synonymOf entries do not return the family name
                    if isinstance(syn_record , dict) and syn_record.get('accepted', False):
                        # search Powo again for the accepted synonym
                        query = { powoName.full_name: syn_record['name'], powoName.kingdom: self.value_Kingdom }
                        target_record_results = powo.search(query)
                        for result in target_record_results:
                            # if the query results are accepted, store it and break out
                            if result.get('accepted', False):
                                target_record = result
                                break
                        break
        except AttributeError:
            # no results returned from the query
            pass
        resultName = target_record.get('name', None)
        resultAuthor = target_record.get('author', None)
        resultFamily = target_record.get('family', None)
        return (resultName, resultAuthor, resultFamily)
