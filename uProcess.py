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
    timeout = time.time() + 60*2 # 2 min timeout
    while os.path.exists(outputDestination):
        if time.time() > timeout:
            logger.debug(loggerHeader + "processMedia :: The destination directory hasn't been deleted after 2 minutes, something is wrong")
            break
        time.sleep(2)

def main(inputDirectory, inputHash):

    # Extensions to use when searching directory s for files to process
    mediaExt = ('.mkv', '.avi', '.divx', '.xvid', '.m4v', '.mov', '.wmv', '.mp4', '.mpg', '.mpeg', '.vob', '.iso', '.nfo', '.sub', '.srt')
    # http://www.rarlab.com/otherfmt.htm
    archiveExt = ('.zip', 'part01.rar', '.rar', '.1', '.01', '.001', '.cab', '.arj', '.lzh', '.tar', '.tar.gz', '.gz', '.tar.bz2', '.bz2', '.ace', '.uue', '.jar', '.iso', '.7z', '.7')
    # An list of words that we don't want file names/directory's to contain
    ignoreWords = ['sample', 'subs', 'proof', 'screens']
    # Move, copy or link
    fileAction = config.get("uProcess", "fileAction")
    # Delete processed files from uTorrent
    deleteFinished = config.getboolean("uProcess", "deleteFinished")
    # If defined (not 0) will delete a torrent if ratio above, in mils)
    deleteRatio = config.getint("uProcess", "deleteRatio")
    # Define the uTorrent host
    uTorrentHost = "http://" + config.get("uTorrent", "host") + ":" + config.get("uTorrent", "port") + "/gui/"

    try: # Create an connection to the uTorrent Web UI
        uTorrent = UTorrentClient(uTorrentHost, config.get("uTorrent", "user"), config.get("uTorrent", "password"))
    except Exception, e:
        logger.error(loggerHeader + "Failed to connect to uTorrent: %s", (uTorrentHost, e, traceback.format_exc()))

    if uTorrent: # We poll uTorrent for a list of files matching the hash, and process them
        status, torrents = uTorrent.list()
        for torrent in torrents['torrents']:
            if torrent[0] == inputHash:
                inputName = torrent[2] # name
                inputProgress = torrent[4] # percent progress (100% = 1000)
                inputRatio = torrent[7] # ratio in 1000(1.292 ratio = 1292 value)
                inputLabel = torrent[11] # label
            elif torrent[7] >= deleteRatio and deleteRatio != 0 and torrent[0] != inputHash:
                logger.debug(loggerHeader + "Ratio goal achieved, deleting torrent: %s", torrent[2])
                uTorrent.removedata(torrent[0])


        logger.debug(loggerHeader + "Torrent Dir: %s", inputDirectory)
        logger.debug(loggerHeader + "Torrent Name: %s", inputName)
        logger.debug(loggerHeader + "Torrent Hash: %s", inputHash)
        if inputLabel:
            logger.debug(loggerHeader + "Torrent Label: %s", inputLabel)
        else:
            inputLabel = 'no_label'

        outputDestination = os.path.join(config.get("uProcess", "outputDirectory"), inputLabel, inputName)

        if not os.path.exists(outputDestination):
            os.makedirs(outputDestination)

        status, data = uTorrent.getfiles(inputHash)
        hash, files = data['files']
        if inputProgress == 1000:
            for file in files:
                fileName, fileSize, downloadedSize = file[:3]
                if os.path.isfile(inputDirectory):
                    inputFile = inputDirectory
                else:
                    inputFile = os.path.join(inputDirectory, fileName)

                outputFile = os.path.join(outputDestination, fileName)

                if fileName.lower().endswith(mediaExt) and not any(word in fileName.lower() for word in ignoreWords) and not any(word in inputDirectory.lower() for word in ignoreWords):
                    logger.debug(loggerHeader + "Found media file: %s", fileName)
                    if not os.path.isfile(outputFile):
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

                elif fileName.lower().endswith(archiveExt) and not any(word in fileName.lower() for word in ignoreWords) and not any(word in inputDirectory.lower() for word in ignoreWords):
                    logger.debug(loggerHeader + "Found compressed file: %s", fileName)
                    logger.info(loggerHeader + "Extracting %s to %s", compressedFile, outputDestination)
                    pyUnRAR2.RarFile(inputFile).extract(path = outputDestination, withSubpath = False, overwrite = True)
        else:
            logger.error(loggerHeader + "Download hasnt completed for torrent: %s", inputName)
            raise

        # Optionally process the outputDestination by calling Couchpotato/Sickbeard
        if config.getboolean("Couchpotato", "active") or config.getboolean("Sickbeard", "active"):

            if fileAction == "move" or fileAction == "link":
                logger.debug(loggerHeader + "Stop seeding torrent with hash: %s", inputHash)
                uTorrent.stop(inputHash)

            if inputLabel == config.get("Couchpotato", "label"):
                try:
                    logger.info(loggerHeader + "Calling Couchpotato to process directory: %s", outputDestination)
                    processMedia("couchpotato", outputDestination)
                except Exception, e:
                    logger.error(loggerHeader + "Couchpotato post process failed for directory: %s %s", outputDestination, (e, traceback.format_exc()))

            elif inputLabel == config.get("Sickbeard", "label"):
                try:
                    logger.info(loggerHeader + "Calling Sickbeard to process directory: %s", outputDestination)
                    processMedia("sickbeard", outputDestination)
                except Exception, e:
                    logger.error(loggerHeader + "Sickbeard post process failed for directory: %s %s", outputDestination, (e, traceback.format_exc()))
            
            if fileAction == "move":
                logger.debug(loggerHeader + "Removing torrent with hash: %s", inputHash)
                uTorrent.removedata(inputHash)
            elif fileAction == "link":
                logger.debug(loggerHeader + "Start seeding torrent with hash: %s", inputHash)
                uTorrent.start(inputHash)

        if deleteFinished:
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

    # usage: uProcess.py "%I"
    inputDirectory = sys.argv[1]                    # %D - The directory of the torrent
    inputHash = sys.argv[2]                         # %I - The hash of the torrent

    if not inputDirectory:
        logger.error(loggerHeader + "Torrent directory is missing")
    elif not len(inputHash) == 40:
        logger.error(loggerHeader + "Torrent hash is missing")
    else:
        main(inputDirectory, inputHash)
