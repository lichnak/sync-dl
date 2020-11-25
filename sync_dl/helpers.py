import os
import json
import re
import logging

import sync_dl.config as cfg
from sync_dl.ytdlWrappers import downloadID,getIDs

def showPlaylist(metaData, printer, plPath, urlWithoutId = None):
    '''
    printer can be print or some level of logging
    urlWithoutId is added if you wish to print out all full urls
    '''
    
    for item in metaData.items():
        printer(f"{item[0]}: {item[1]}")

    currentDir = getLocalSongs(plPath)

    if urlWithoutId != None:
        printer(f"i: Link                                         ->   Local Title")
        for i,songId in enumerate(metaData['ids']):
            url = f"{urlWithoutId}{songId}"
            printer(f"{i}: {url}  ->  {currentDir[i]}")



def compareMetaData(metaData, printer):
    '''Tool for comparing ids held in metadata and their order compared to remote playlist ids'''
    remoteIds = getIDs(metaData["url"])
    localIds = metaData["ids"]
    printer(f"i: Local ID    -> j: Remote ID")

    for i,localId in enumerate(localIds):
        if localId in remoteIds:
            j = remoteIds.index(localId)
            printer(f"{i}: {localId} -> {j}: {localId}")

        else:
            printer(f"{i}: {localId} ->  : ")


    for j, remoteId in enumerate(remoteIds):
        if remoteId not in localIds:

            printer(f" :             -> {j}: {remoteId}")



def rename(metaData, printer, plPath, oldName, newName, index, newId):
    printer(f"Renaming {oldName} to {newName}")
    os.rename(f"{plPath}/{oldName}",f"{plPath}/{newName}")

    if index >= len(metaData["ids"]):
        metaData["ids"].append(newId)
    else:
        metaData["ids"][index] = newId

    printer("Renaming Complete")

def relabel(metaData, printer,plPath, oldName, oldIndex, newIndex, numDigets):
    '''
    used for changing the number of an element in the playlist
    will blank out old posistion in the metaData

    note this does NOT prevent you from overwriting numbering of 
    an existing song

    returns new name which is needed in some cases (ie when a song is temporarily moved)
    '''

    newName = re.sub(cfg.filePrependRE, f"{createNumLabel(newIndex,numDigets)}_" , oldName)
    songId = metaData['ids'][oldIndex]
    printer(f"Relabeling {oldName} to {newName}")
    os.rename(f"{plPath}/{oldName}",f"{plPath}/{newName}")


    if newIndex >= len(metaData["ids"]):
        metaData["ids"].append(songId)
    else:
        metaData["ids"][newIndex] = songId

    metaData['ids'][oldIndex] = ''

    printer("Relabeling Complete")
    return newName

def delete(metaData, plPath, name, index):
    logging.info(f"Deleting {name}")
    os.remove(f"{plPath}/{name}")

    del metaData["ids"][index]

    logging.debug("Deleting Complete")



def download(metaData,plPath, songId, index,numDigets):
    '''
    downloads song and adds it to metadata at index
    returns whether or not the download succeeded 
    '''
    num = createNumLabel(index,numDigets)

    logging.info(f"Dowloading song Id {songId}")
    if downloadID(songId,plPath,num):

        if index >= len(metaData["ids"]):
            metaData["ids"].append(songId)
        else:
            metaData["ids"][index] = songId
        
        logging.debug("Download Complete")
        return True
    return False

def createNumLabel(n,numDigets):
    n = str(n)
    lenN = len(n)
    if lenN>numDigets:
        raise Exception(f"Number Label Too large! Expected {numDigets} but got {lenN} digets")

    return (numDigets-lenN)*"0"+n


def _sortByNum(element):
    '''
    returns the number in front of each song file
    '''
    match = re.match(cfg.filePrependRE,element)

    return int(match.group()[:-1])

def _filterFunc(element):
    '''
    returns false for any string not preceded by some number followed by an underscore
    used for filtering non song files
    '''
    match = re.match(cfg.filePrependRE,element)
    if match:
        return True
    
    return False


def getLocalSongs(plPath):
    '''
    returns sanatized list of all songs in local playlist, in order
    '''
    currentDir = os.listdir(path=plPath) 
    currentDir = sorted(filter(_filterFunc,currentDir), key= _sortByNum) #sorted and sanitized dir
    return currentDir

def smartSyncNewOrder(localIds,remoteIds):
    '''
    used by smartSync, localIds will not be mutated but remtoeIds will
    output is newOrder, a list of tuples ( Id of song, where to find it )
    the "where to find it" is the number in the old ordering (None if song is to be downloaded)
    '''
    newOrder=[]

    localIdPairs = [(localIds[index],index) for index in range(len(localIds))] #contins ( Id of song, local order )

    while True:
        if len(localIdPairs)==0:
            newOrder.extend( (remoteId,None) for remoteId in remoteIds )
            break

        elif len(remoteIds)==0:
            newOrder.extend( localIdPairs )
            break

        remoteId=remoteIds[0]
        localId,localIndex = localIdPairs[0]

        if localId==remoteId:
            #remote song is already saved locally in correct posistion
            newOrder.append( localIdPairs.pop(0) )

            remoteId = remoteIds.pop(0) #must also remove this remote element

        elif localId not in remoteIds:
            # current local song has been removed from remote playlist, it must remain in current order
            newOrder.append( localIdPairs.pop(0) )

        
        # at this point the current local song and remote song arent the same, but the current local
        # song still exists remotly, hence we can insert the remote song into the current posistion
        elif remoteId in localIds:
            # remote song exists in local but in wrong place

            index = localIds[localIndex+1:].index(remoteId)+localIndex+1
            for i,_ in enumerate(localIdPairs):
                if localIdPairs[i][1]==index:
                    j = i
                    break

            newOrder.append( localIdPairs.pop(j) )
            remoteId = remoteIds.pop(0) #must also remove this remote element
            
            #checks if songs after the moved song are not in remote, if so they must be moved with it
            while j<len(localIdPairs) and (localIdPairs[j][0] not in remoteIds):
                newOrder.append( localIdPairs.pop(j) )
                


        else:
            newOrder.append( (remoteIds.pop(0),None) )
    
    return newOrder

