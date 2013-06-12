#!/usr/bin/env python

#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#    
#    Creator of uProcess: jkaberg, https://github.com/jkaberg

import os
import sys
import shutil
import time
import logging
import urllib
import traceback
import ConfigParser

from utorrent.client import UTorrentClient
import pyUnRAR2
from pyUnRAR2.rar_exceptions import *

class AuthURLOpener(urllib.FancyURLopener):
    def __init__(self, user, pw):
        self.username = user
        self.password = pw
        self.numTries = 0
        urllib.FancyURLopener.__init__(self)

    def prompt_user_passwd(self, host, realm):
        if self.numTries == 0:
            self.numTries = 1
            return (self.username, self.password)
        else:
            return ('', '')

    def openit(self, url):
        self.numTries = 0
        return urllib.FancyURLopener.open(self, url)

def createLink(src, dst):
    try:
        if os.name == 'nt':
            import ctypes
            ctypes.windll.kernel32.CreateHardLinkW(dst, src, 0)
        else:
            os.link(src, dst)
    except Exception, e:
        logger.error(loggerHeader + "Linking failed: %s %s", (e, traceback.format_exc()))

def processMedia(mediaProcessor, outputDestination):
    if mediaProcessor == "couchpotato":
        try:
            baseURL = config.get("Couchpotato", "baseURL")
            logger.debug(loggerHeader + "processMedia :: URL base: %s", baseURL)
        except ConfigParser.NoOptionError:
            baseURL = ''

        if config.getboolean("Couchpotato", "ssl"):
            protocol = "https://"
        else:
            protocol = "http://"
        url = protocol + config.get("Couchpotato", "host") + ":" + config.get("Couchpotato", "port") + "/" + baseURL + "api/" + config.get("Couchpotato", "apikey") + "/renamer.scan/?async=1&movie_folder=" + outputDestination
        myOpener = AuthURLOpener(config.get("Couchpotato", "username"), config.get("Couchpotato", "password"))

    elif mediaProcessor == "sickbeard":
        try:
            baseURL = config.get("Sickbeard", "baseURL")
            logger.debug(loggerHeader + "processMedia :: URL base: %s %s %s", (baseURL, e, traceback.format_exc()))
        except ConfigParser.NoOptionError:
            baseURL = ''

        if config.getboolean("Sickbeard", "ssl"):
            protocol = "https://"
        else:
            protocol = "http://"
        url = protocol + config.get("Sickbeard", "host") + ":" + config.get("Sickbeard", "port") + "/" + baseURL + "home/postprocess/processEpisode?quiet=1&dir=" + outputDestination
        myOpener = AuthURLOpener(config.get("Sickbeard", "username"), config.get("Sickbeard", "password"))
    else:
        return

    try:
        urlObj = myOpener.openit(url)
        logger.debug(loggerHeader + "processMedia :: Opening URL: %s", url)
    except Exception, e:
        logger.error(loggerHeader + "processMedia :: Unable to open URL: %s %s %s", (url, e, traceback.format_exc()))
        raise

    result = urlObj.readlines()
    for line in result:
        logger.debug(loggerHeader + "processMedia :: " + line)

    # This is a ugly solution, we need a better one!!
    timeout = time.time() + 60*2 # 2 min time out
    while os.path.exists(outputDestination):
        if time.time() > timeout:
            logger.debug(loggerHeader + "processMedia :: The destination directory hasn't been deleted after 2 minutes, something is wrong")
            break
        time.sleep(2)

def main(inputDirectory, inputHash):

    searchExt = tuple((config.get("Miscellaneous", "media") + config.get("Miscellaneous", "meta") + config.get("Miscellaneous", "other")).split(','))
    archiveExt = tuple((config.get("Miscellaneous", "compressed")).split(','))
    ignoreWords = (config.get("Miscellaneous", "ignore")).split(',')
    fileAction = config.get("uProcess", "fileAction")
    deleteFinished = config.getboolean("uProcess", "deleteFinished")
    deleteRatio = config.getint("uProcess", "deleteRatio")
    uTorrentHost = "http://" + config.get("uTorrent", "host") + ":" + config.get("uTorrent", "port") + "/gui/"

    try:
        uTorrent = UTorrentClient(uTorrentHost, config.get("uTorrent", "user"), config.get("uTorrent", "password"))
    except Exception, e:
        logger.error(loggerHeader + "Failed to connect to uTorrent: %s", (uTorrentHost, e, traceback.format_exc()))

    if uTorrent:
        status, torrents = uTorrent.list()  # http://www.utorrent.com/community/developers/webapi#devs6
        for torrent in torrents['torrents']:
            if torrent[0] == inputHash:     # hash
                inputName = torrent[2]      # name
                inputProgress = torrent[4]  # progress in mils (100% = 1000)
                inputRatio = torrent[7]     # ratio in mils (1.292 ratio = 1292)
                inputLabel = torrent[11]    # label
            elif torrent[7] >= deleteRatio and deleteRatio != 0 and torrent[0] != inputHash:
                logger.debug(loggerHeader + "Ratio goal achieved, deleting torrent: %s", torrent[2])
                uTorrent.removedata(torrent[0])


        logger.debug(loggerHeader + "Torrent Directory: %s", inputDirectory)
        logger.debug(loggerHeader + "Torrent Name: %s", inputName)
        logger.debug(loggerHeader + "Torrent Hash: %s", inputHash)
        if inputLabel:
            logger.debug(loggerHeader + "Torrent Label: %s", inputLabel)
        else:
            inputLabel = 'no_label'

        outputDestination = os.path.join(config.get("uProcess", "outputDirectory"), inputLabel, inputName)

        if not os.path.exists(outputDestination):
            os.makedirs(outputDestination)

        status, data = uTorrent.getfiles(inputHash) # http://www.utorrent.com/community/developers/webapi#devs7
        hash, files = data['files']
        if inputProgress == 1000:
            for file in files:
                fileName, fileSize, downloadedSize = file[:3]

                fileName = fileName.lower()

                if os.path.isfile(inputDirectory):
                    inputFile = inputDirectory
                else:
                    inputFile = os.path.join(inputDirectory, fileName)

                outputFile = os.path.join(outputDestination, fileName)

                if not any(word in fileName for word in ignoreWords):
                    if fileName.endswith(searchExt):
                        if os.path.isfile(outputFile):
                            logger.debug(loggerHeader + "File already exists in: %s, deleting the old file: %s", outputDestination, fileName)
                            os.remove(outputFile)
                        logger.debug(loggerHeader + "Found media file: %s", fileName)
                        if fileAction == "move":
                            logger.info(loggerHeader + "Moving file %s to %s", inputFile, outputFile)
                            shutil.move(inputFile, outputFile)
                        elif fileAction == "link":
                            logger.info(loggerHeader + "Linking file %s to %s", inputFile, outputFile)
                            createLink(inputFile, outputFile)
                        elif fileAction == "copy":
                            logger.info(loggerHeader + "Copying file %s to %s", inputFile, outputFile)
                            shutil.copy(inputFile, outputFile)
                        else:
                            logger.error(loggerHeader + "File action not found")

                    elif fileName.endswith(archiveExt):
                        logger.debug(loggerHeader + "Found compressed file: %s", fileName)
                        logger.info(loggerHeader + "Extracting %s to %s", inputFile, outputDestination)
                        pyUnRAR2.RarFile(inputFile).extract(path = outputDestination, withSubpath = False, overwrite = True)
        else:
            logger.error(loggerHeader + "Download hasn't completed for torrent: %s", inputName)
            raise

        if (config.getboolean("Couchpotato", "active") or config.getboolean("Sickbeard", "active")) and (inputLabel == config.get("Couchpotato", "label") or inputLabel == config.get("Sickbeard", "label")):
            if fileAction == "move" or fileAction == "link":
                logger.debug(loggerHeader + "Stop seeding torrent with hash: %s", inputHash)
                uTorrent.stop(inputHash)

            if inputLabel == config.get("Couchpotato", "label"):
                processMedia("couchpotato", outputDestination)

            elif inputLabel == config.get("Sickbeard", "label"):
                processMedia("sickbeard", outputDestination)
            
            if fileAction == "move":
                logger.debug(loggerHeader + "Removing torrent with hash: %s", inputHash)
                uTorrent.removedata(inputHash)
            elif fileAction == "link":
                logger.debug(loggerHeader + "Start seeding torrent with hash: %s", inputHash)
                uTorrent.start(inputHash)

        if deleteFinished and fileAction != "move":
            logger.debug(loggerHeader + "Removing torrent with hash: %s", inputHash)
            uTorrent.removedata(inputHash)

        logger.info(loggerHeader + "Success, all done!\n")
    else:
        logger.error(loggerHeader + "No connection with uTorrent\n")
        raise

if __name__ == "__main__":

    config = ConfigParser.ConfigParser()
    configFilename = os.path.normpath(os.path.join(os.path.dirname(sys.argv[0]), "config.cfg"))
    config.read(configFilename)

    logfile = os.path.normpath(os.path.join(os.path.dirname(sys.argv[0]), "uProcess.log"))
    loggerHeader = "uProcess :: "
    loggerFormat = logging.Formatter('%(asctime)s %(levelname)-8s %(message)s', '%b-%d %H:%M:%S')
    logger = logging.getLogger('uProcess')

    loggerStd = logging.StreamHandler()
    loggerStd.setFormatter(loggerFormat)

    loggerHdlr = logging.FileHandler(logfile)
    loggerHdlr.setFormatter(loggerFormat)
    loggerHdlr.setLevel(logging.INFO)

    if config.getboolean("uProcess", "debug"):
        logger.setLevel(logging.DEBUG)
        loggerHdlr.setLevel(logging.DEBUG)
        loggerStd.setLevel(logging.DEBUG)
    else:
        logger.setLevel(logging.INFO)
        loggerHdlr.setLevel(logging.INFO)
        loggerStd.setLevel(logging.INFO)

    logger.addHandler(loggerStd)
    logger.addHandler(loggerHdlr)

    if not os.path.isfile(configFilename):
        logger.error(loggerHeader + "Config file not found: " + configFilename)
        raise
    else:
        logger.info(loggerHeader + "Config loaded: " + configFilename)

    # usage: uProcess.py "%D" "%I" 
    inputDirectory = os.path.normpath((sys.argv[1]).lower())    # %D - The directory of the torrent, or in some cases a single file
    inputHash = sys.argv[2]                                     # %I - The hash of the torrent

    if not inputDirectory:
        logger.error(loggerHeader + "Torrent directory is missing")
    elif not len(inputHash) == 40:
        logger.error(loggerHeader + "Torrent hash is missing or an invalid hash value has been passed")
    else:
        main(inputDirectory, inputHash)
