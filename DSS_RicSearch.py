#
#
#
from json import dumps, loads, load
import os,sys,time,datetime,getopt,csv
import requests,json
from requests import Request, Session, get
from time import sleep
from collections import OrderedDict
from getpass import _raw_input as input
from getpass import getpass
from getpass import GetPassWarning

_userId = ''
_password = ''
_urlExtrations = 'https://hosted.datascopeapi.reuters.com/RestApi/v1/Extractions/Extract'
_urlAuthToken =  'https://hosted.datascopeapi.reuters.com/RestApi/v1/Authentication/RequestToken'

_authToken = ''
_instFilename = ''
_instList = []

_sleepTime = 2
_jsonFileName="DSS_RicSearch.json"
_instFilename = "inst.txt"

#
#
#
def timeNow():
    return str(datetime.datetime.strftime(datetime.datetime.now(), "%H:%M:%S") + "=== ")

#
#
#
def getAuthToken(username="",password=""):
    # Step 1
    print(timeNow() +  "*** Step 1 Request Authorization Token" )
    _header= {}
    _header['Prefer']='respond-async'
    _header['Content-Type']='application/json; odata.metadata=minimal'
    _data={'Credentials':{
        'Password':password,
        'Username':username
        }
    }
    _resp = requests.post( _urlAuthToken, json=_data, headers=_header )
    if _resp.status_code != 200:
        print(timeNow() + 'ERROR, Get Token failed with ' + str(_resp.status_code))
        sys.exit(-1)
    else:
         _jResp = _resp.json()
         _authToken = _jResp["value"]
         return _jResp["value"]

#
#
#
def onDemaonTNCExtractionReq(authToken):

    # Step 2
    print(timeNow() + "*** Step 2 Load the barebone T&C JSON HTTP Request payload from file")
    _token = 'Token ' + authToken
    _jReqBody = {}
    with open(_jsonFileName, "r") as filehandle:

        #
        # Depending on the version of Python being installed, the JSON load() function
        # may need to add an object_pairs_hook=OrderedDict argument to force JSON to
        # maintain the order of attributes in the HTTP request body
        #
        _jReqBody=load( filehandle, object_pairs_hook=OrderedDict )
        #_jReqBody=load( filehandle )

    # Step 3
    loadInstruments()


    # Step 4
    print(timeNow() +  '*** Step 4 Append each instrument to the InstrumentIdentifiers array' )
    for _inst in _instList:
        _jReqBody["ExtractionRequest"]["IdentifierList"]["InstrumentIdentifiers"].append( { "IdentifierType": _inst[0], "Identifier": _inst[1] } )

    _extractReqHeader = makeExtractHeader( _token )
    try:
        #Step 5
        print (timeNow() +   '*** Step 5 Post the T&C Request to DSS REST server and check response status')
        _resp = requests.post(_urlExtrations, data=None, json=_jReqBody, headers=_extractReqHeader)
        if _resp.status_code != 200:
            if _resp.status_code != 202:
                message="Error: Status Code:" + str(_resp.status_code) + " Message:" + _resp.text
                raise Exception(message)

            print(timeNow() + "Request message accepted. Please wait...")

            # Get location URL from response message header
            _location = _resp.headers['Location']

            # Pooling loop to check request status every 2 sec.
            while True:
                _resp = get( _location, headers=_extractReqHeader )
                _pollstatus = int(_resp.status_code)

                if _pollstatus==200:
                    break
                else:
                    print(timeNow() +  "Status:", _resp.headers['Status'])

                #wait 2 sec and re-request the status to check if it already completed
                sleep(_sleepTime)

        print(timeNow() + "Response message received")

        # Process Reponse JSON object
        _jResp = _resp.json()

        # Step 6
        print (timeNow() +  '*** Step 6 Extract the response message. Display the field values of each instrument to console')
        _fieldNames = _jReqBody["ExtractionRequest"]["ContentFieldNames"]
        _headerStr = "IdentifierType|Identifier"

        for i in range(len(_fieldNames)):
            _headerStr += "|" + str(_fieldNames[i])

        # Initialize exception intruments array to keep invalid instruemnts
        _ricExcepts = { 'RICException' :[] }

        # Write the result to the console
        print ("\n========")
        print(_headerStr)
        for i in range(len(_jResp["value"])):
            if 'Error' in _jResp["value"][i]:
                _ricExcepts['RICException'].append( _jResp["value"][i] )
                continue

            _outStr = _jResp["value"][i]["IdentifierType"] + "|" + _jResp["value"][i]["Identifier"]
            for j in range(len( _fieldNames )):
                _outStr += "|" + str( _jResp["value"][i][_fieldNames[j]] )

            print( _outStr )

        print ("========")

        if len(_ricExcepts['RICException']) > 0:
            print ('Search Exceptions:')
            for _rExcept in _ricExcepts['RICException']:
                _str = _rExcept['IdentifierType'] + ' ' + _rExcept['Identifier'] + ": " + _rExcept['Error']
                print(str(_str))

        print ('')

    except Exception as ex:
        print(timeNow() +  "Exception occrued:", ex)

    return

#
#
#
def loadInstruments():  # Step 3
    print(timeNow() +  '*** Step 3 Load the instrument file to a list' )
    identifyTypes = [ 'Isin', 'Sedol', 'Cusip' ]
    if _instFilename != '':
        print(timeNow() + 'Loading Instruments File:' + _instFilename)
        _inFile = open(_instFilename, "r")
        for line in _inFile:
            line = line[:-1]
            _lineElements = line.split(',')
            if len(_lineElements) == 2 :
                if _lineElements[0] in identifyTypes:
                    _instElement = [_lineElements[0], _lineElements[1]]
                    _instList.append(_instElement)

                else:
                    print('Invalid Identifier Type: ' + _lineElements[0] + ", Identifier: " + _lineElements[1] )

        print('')
        _inFile.close()

#
#
#
def makeExtractHeader( token):
    _header={}
    _header['Prefer']='respond-async, wait=5'
    _header['Content-Type']='application/json; odata.metadata=minimal'
    _header['Accept-Charset']='UTF-8'
    _header['Authorization'] = token
    return _header

#
#
#
def main():
    print(timeNow() + 'Started')
    _DSSUsername=input('\nEnter DSS Username:')
    _DSSPassword=getpass(prompt='Enter DSS Password:')
    try:
        # Step 1 Request Authorization Token
        try:
            _authToken = getAuthToken (_DSSUsername, _DSSPassword )
        except GetPassWarning as e:
            print(timeNow() + e)

        print(timeNow() + "Auth Token received")
        onDemaonTNCExtractionReq(_authToken)
        print(timeNow() +  "Extraction completed")

    except PermissionError as e:
        print(e)
    except Exception as ex:
        print("Exception occurred:", ex)

#
#
#
if __name__ == "__main__":
    main()
