import os
import logging
from sys import argv
import shelve
import re
import ntpath
from random import randint

from sync_dl.ytdlWrappers import getIDs, downloadID
from sync_dl.plManagement import editPlaylist, correctStateCorruption
from sync_dl.helpers import createNumLabel, smartSyncNewOrder,showPlaylist, getLocalSongs, rename, compareMetaData, relabel
import sync_dl.config as cfg

def newPlaylist(plPath,url):
    if not os.path.exists(plPath):
        os.makedirs(plPath)

    elif len(os.listdir(path=plPath))!=0:
        logging.error(f"Directory Is Not Empty, Cannot Make Playlist in {plPath}")
        print("Directory Is Not Empty, Cannot Make Playlist Here")
        return


    ids = getIDs(url)
    numDidgets = len(str(len(ids))) #needed for creating starting number for auto ordering ie) 001, 0152

    with shelve.open(f"{plPath}/{cfg.metaDataName}", 'c',writeback=True) as metaData:
        metaData["url"] = url
        metaData["ids"] = []

        invalidSongs = 0
        for i,vidId in enumerate(ids):
            num = createNumLabel(i,numDidgets)

            if not downloadID(vidId,plPath,num):
                invalidSongs+=1


            metaData["ids"].append(vidId)
            print([item for item in metaData.items()])

        print(f"Downloaded {len(ids)-invalidSongs}/{len(ids)} Songs")


def smartSync(plPath):
    '''
    Syncs to remote playlist however will Not delete local songs (will reorder). Songs not in remote (ie ones deleted) 
    will be after the song they are currently after in local
    Example 1
        Local order: A B C D 
        Remote order: A 1 B C 2

        Local becomes: A 1 B C D 2

        notice D was removed from remote but is still after C in Local
    
    Example 2
        Local order: A B C D 
        Remote order: A 1 C B 2

        Local becomes: A 1 C D B 2

        notice C and B where swapped and D was deleted from Remote
    
    see test_smartSyncNewOrder in tests.py for more examples
    '''

    correctStateCorruption(plPath)

    existingFiles = os.listdir(path=f"{plPath}")
    if cfg.metaDataName not in existingFiles:
        print("Current Directory is Not Existing Playlist")
        return


    with shelve.open(f"{plPath}/{cfg.metaDataName}", 'c',writeback=True) as metaData:
        url = metaData["url"]
        localIds = metaData["ids"]

    remoteIds = getIDs(url)


    newOrder = smartSyncNewOrder(localIds,remoteIds)

    editPlaylist(plPath,newOrder)


def hardSync():
    '''Syncs to remote playlist will delete local songs'''

def appendNew():
    '''will append new songs in remote playlist to local playlist in order that they appear'''

def manualAdd(plPath, songPath, posistion):
    '''put song in posistion in the playlist'''

    correctStateCorruption(plPath)

    currentDir = getLocalSongs(plPath)

    with shelve.open(f"{plPath}/{cfg.metaDataName}", 'c',writeback=True) as metaData:

        idsLen = len(metaData["ids"])
        numDidgets = len(str( idsLen + 1 ))

        #clamp posistion
        if posistion > idsLen:
            posistion = idsLen
        elif posistion < 0:
            posistion = 0

        #shifting elements
        for i in reversed(range(posistion, idsLen)):
            oldName = currentDir[i]

            newName = re.sub(cfg.filePrependRE, f"{createNumLabel(i+1,numDidgets)}_" , oldName)

            rename(metaData,logging.info,plPath,oldName,newName,i+1,metaData["ids"][i])

            metaData["ids"][i] = '' #wiped in case of crash, this blank entries can be removed restoring state


        newSongName = f"{createNumLabel(i+1,numDidgets)}_" + ntpath.basename(songPath)

        rename(metaData,logging.info,plPath,songPath,newSongName,posistion,metaData["ids"][i])

def swap(plPath, index1, index2):
    '''moves song to provided posistion, shifting all below it down'''
    correctStateCorruption(plPath)

    currentDir = getLocalSongs(plPath)


    with shelve.open(f"{plPath}/{cfg.metaDataName}", 'c',writeback=True) as metaData:

        idsLen = len(metaData["ids"])
        numDidgets = len(str( idsLen + 1 ))

 
        #shift index1 out of the way (to idsLen)

        oldName = currentDir[index1]
        shiftedName = re.sub(cfg.filePrependRE, f"{createNumLabel(idsLen,numDidgets)}_" , oldName)

        relabel(metaData,logging.info,plPath,oldName,index1,idsLen,numDidgets)

        #move index2 to index1's old location

        oldName = currentDir[index2]
        relabel(metaData,logging.info,plPath,oldName,index2,index1,numDidgets)

        #move index1 (now =idsLen) to index2's old location

        oldName = shiftedName
        relabel(metaData,logging.info,plPath,oldName,idsLen,index2,numDidgets)

        del metaData["ids"][idsLen]

def move(plPath, currentIndex, newIndex):
    correctStateCorruption(plPath)

    currentDir = getLocalSongs(plPath)

    with shelve.open(f"{plPath}/{cfg.metaDataName}", 'c',writeback=True) as metaData:

        idsLen = len(metaData["ids"])
        numDidgets = len(str( idsLen + 1 ))

        for i in reversed(range(newIndex,idsLen)):
            #shift index1 out of the way (to idsLen)
            oldName = currentDir[i]
            shiftedName = re.sub(cfg.filePrependRE, f"{createNumLabel(i+1,numDidgets)}_" , oldName)

            
            rename(metaData,logging.info,plPath,oldName,shiftedName,idsLen,metaData["ids"][i])
            metaData["ids"][i] = '' #wiped in case of crash, this blank entries can be removed restoring state



def shuffle(plPath):
    '''randomizes playlist order'''
    correctStateCorruption(plPath)

    with shelve.open(f"{plPath}/{cfg.metaDataName}", 'c',writeback=True) as metaData:

        plLen = len(metaData["ids"])
        ids = metaData["ids"]

        avalibleNums = [i for i in range(plLen)]
        newOrder = []
        for _ in range(plLen):
            oldIndex = avalibleNums.pop(randint(0,len(avalibleNums)-1))
            newOrder.append( (ids[oldIndex],oldIndex) )
    
    editPlaylist(plPath, newOrder)

    







if __name__ == "__main__":

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.FileHandler("debug.log"),
            logging.StreamHandler()
        ]
    )

    if len(argv)!=3:
        raise Exception(f"2 arguments needed (playlist name and url path) but {len(argv) - 1} provided")

    logging.info("Application Launched")
    path = f'./{argv[1]}'
    url = argv[2]

    try:
        os.stat(path)
    except:
        os.mkdir(path)    

    while True:
        task = input("1) create playlist, 2) smart sync, 3) view playList 4) correct state corruption 5) compare metadata: ")
        if task == '1':
            newPlaylist(path, url)

        if task == '2':
            smartSync(path)

        if task == '3':
            with shelve.open(f"{path}/{cfg.metaDataName}", 'c',writeback=True) as metaData:
                showPlaylist(metaData,print,path,"https://www.youtube.com/watch?v=")
        
        if task == '4':
            correctStateCorruption(path)

        if task == '5':
            with shelve.open(f"{path}/{cfg.metaDataName}", 'c',writeback=True) as metaData:
                compareMetaData(metaData,print)