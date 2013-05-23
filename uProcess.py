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

import os, sys, shutil, time, logging, subprocess, urllib, win32file, traceback, ConfigParser

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
            win32file.CreateHardLink(dst, src)
        else:
            os.link(src, dst)
    except Exception, e:
        logger.error(loggerHeader + "Linking failed: %s %s", (e, traceback.format_exc()))

def createDestination(outputDestination):
    if not os.path.exists(outputDestination):
        try:
            os.makedirs(outputDestination)
        except Exception, e:
            logger.error(loggerHeader + "Failed to create destination directory: %s %s %s", (outputDestination, e, traceback.format_exc()))
    return

def extractFile(compressedFile, outputDestination):
    logger.info(loggerHeader + "Extracting %s to %s", compressedFile, outputDestination)
    try:
        pyUnRAR2.RarFile(compressedFile).extract(path = outputDestination, withSubpath = False, overwrite = False)
    except Exception, e:
        logger.error("Failed to extract %s: %s %s", (compressedFile, e, traceback.format_exc()))
        return

def processFile(fileAction, inputFile, outputFile):
    if not os.path.isfile(outputFile):
        if fileAction == "move":
            try:
                logger.info(loggerHeader + "Moving file %s to %s", inputFile, outputFile)
                shutil.move(inputFile, outputFile)
            except Exception, e:
                logger.error(loggerHeader + "Failed to move file: %s to %s: %s %s", (inputFile, outputFile, e, traceback.format_exc()))
        elif fileAction == "link":
            try:
                logger.info(loggerHeader + "Linking file %s to %s", inputFile, outputFile)
                createLink(inputFile, outputFile)
            except Exception, e:
                logger.info(loggerHeader + "Failed to link file: %s to %s: %s %s", (inputFile, outputFile, e, traceback.format_exc()))
        else:
            try:
                logger.info(loggerHeader + "Copying file %s to %s", inputFile, outputFile)
                shutil.copy(inputFile, outputFile)
            except Exception, e:
                logger.error(loggerHeader + "Failed to copy file: %s to %s: %s %s", (inputFile, outputFile, e, traceback.format_exc()))
    else:
        logger.error(loggerHeader + "File already exists: %s", outputFile)
    return

def processMovie(outputDestination):
    try:
        baseURL = config.get("Couchpotato", "baseURL")
        logger.debug(loggerHeader + "processMovie :: URL base: %s", baseURL)
    except ConfigParser.NoOptionError:
        baseURL = ''

    if config.getboolean("Couchpotato", "ssl"):
        protocol = "https://"
    else:
        protocol = "http://"
    url = protocol + config.get("Couchpotato", "host") + ":" + config.get("Couchpotato", "port") + "/" + baseURL + "api/" + config.get("Couchpotato", "apikey") + "/renamer.scan/?async=1&movie_folder=" + outputDestination
    myOpener = AuthURLOpener(config.get("Couchpotato", "username"), config.get("Couchpotato", "password"))

    try:
        urlObj = myOpener.openit(url)
        logger.debug(loggerHeader + "processMovie :: Opening URL: %s", url)
    except IOError, e:
        logger.error(loggerHeader + "processMovie :: Unable to open URL: %s %s %s", (url, e, traceback.format_exc()))
        raise

    result = urlObj.readlines()
    for line in result:
        logger.info(loggerHeader + "processMovie :: " + line)

    # This is a ugly solution, we need a better one!!
    while os.path.exists(outputDestination):
        if not os.path.exists(outputDestination):
            break
        time.sleep(10)

def processEpisode(outputDestination):
    try:
        baseURL = config.get("Sickbeard", "baseURL")
        logger.debug(loggerHeader + "processEpisode :: URL base: %s %s %s", (baseURL, e, traceback.format_exc()))
    except ConfigParser.NoOptionError:
        baseURL = ''

    if config.getboolean("Sickbeard", "ssl"):
        protocol = "https://"
    else:
        protocol = "http://"
    url = protocol + config.get("Sickbeard", "host") + ":" + config.get("Sickbeard", "port") + "/" + baseURL + "home/postprocess/processEpisode?quiet=1&dir=" + outputDestination
    myOpener = AuthURLOpener(config.get("Sickbeard", "username"), config.get("Sickbeard", "password"))

    try:
        urlObj = myOpener.openit(url)
        logger.debug(loggerHeader + "processEpisode :: Opening URL: %s", url)
    except Exception, e:
        logger.error(loggerHeader + "processEpisode :: Unable to open URL: %s %s %s", (url, e, traceback.format_exc()))
        raise

    result = urlObj.readlines()
    for line in result:
        logger.debug(loggerHeader + "processEpisode :: " + line)

    # This is a ugly solution, we need a better one!!
    while os.path.exists(outputDestination):
        if not os.path.exists(outputDestination):
            break
        time.sleep(10)

def main(inputDirectory, inputName, inputHash, inputLabel):
    logger.debug(loggerHeader + "Torrent Dir: %s", inputDirectory)
    logger.debug(loggerHeader + "Torrent Name: %s", inputName)
    logger.debug(loggerHeader + "Torrent Hash: %s", inputHash)
    if inputLabel:
        logger.debug(loggerHeader + "Torrent Label: %s", inputLabel)
    else:
        inputLabel = ''

    # Extensions to use when searching directory s for files to process
    mediaExt = ('.mkv', '.avi', '.divx', '.xvid', '.mov', '.wmv', '.mp4', '.mpg', '.mpeg', '.vob', '.iso', '.nfo', '.sub', '.srt', '.jpg', '.jpeg', '.gif')
    # http://www.rarlab.com/otherfmt.htm
    archiveExt = ('.zip', 'part01.rar', '.rar', '.1', '.01', '.001', '.cab', '.arj', '.lzh', '.tar', '.tar.gz', '.gz', '.tar.bz2', '.bz2', '.ace', '.uue', '.jar', '.iso', '.7z', '.7')
    # An list of words that we don't want file names/directory's to contain
    ignoreWords = ['sample', 'subs', 'proof']
    # Move, copy or link
    fileAction = config.get("uProcess", "fileAction")
    # Destination for extracted, copied, moved or linked files
    outputDestination = os.path.join(config.get("uProcess", "outputDirectory"), inputLabel, inputName)
    # Define the uTorrent host
    uTorrentHost = "http://" + config.get("uTorrent", "host") + ":" + config.get("uTorrent", "port") + "/gui/"

    try: # Create an connection to the uTorrent Web UI
        uTorrent = UTorrentClient(uTorrentHost, config.get("uTorrent", "user"), config.get("uTorrent", "password"))
    except Exception, e:
        logger.error(loggerHeader + "Failed to connect to uTorrent: %s", (uTorrentHost, e, traceback.format_exc()))

    if uTorrent: # We poll uTorrent for a list of files matching the hash, and process them
        if fileAction == "move" or fileAction == "link":
            logger.debug(loggerHeader + "Stop seeding torrent with hash: %s", inputHash)
            uTorrent.stop(inputHash)

        createDestination(outputDestination)
        status, data = uTorrent.getfiles(inputHash)
        hash, files = data['files']
        for file in files:
            fileName, fileSize, downloadedSize = file[:3]
            if fileSize == downloadedSize:
                if os.path.isfile(inputDirectory):
                    inputFile = inputDirectory
                else:
                    inputFile = os.path.join(inputDirectory, fileName)
                outputFile = os.path.join(outputDestination, fileName)

                if fileName.lower().endswith(mediaExt) and not any(word in fileName.lower() for word in ignoreWords) and not any(word in inputDirectory.lower() for word in ignoreWords):
                    logger.debug(loggerHeader + "Found media file: %s", fileName)
                    processFile(fileAction, inputFile, outputFile)

                elif fileName.lower().endswith(archiveExt) and not any(word in fileName.lower() for word in ignoreWords) and not any(word in inputDirectory.lower() for word in ignoreWords):
                    logger.debug(loggerHeader + "Found compressed file: %s", fileName)
                    extractFile(inputFile, outputDestination)
            else:
                logger.error(loggerHeader + "Download hasnt completed for torrent: %s", inputName)
                raise
    else:
        logger.error(loggerHeader + "No connection with uTorrent")
        raise

    # Optionally process the outputDestination by calling Couchpotato
    if inputLabel == config.get("Couchpotato", "label") and config.getboolean("Couchpotato", "active"):
        try:
            logger.info(loggerHeader + "Calling Couchpotato to process directory: %s", outputDestination)
            processMovie(outputDestination)
        except Exception, e:
            logger.error(loggerHeader + "Couchpotato post process failed for directory: %s %s", outputDestination, (e, traceback.format_exc()))

    # Optionally process the outputDestination by calling Sickbeard
    elif inputLabel == config.get("Sickbeard", "label") and config.getboolean("Sickbeard", "active"):
        try:
            logger.info(loggerHeader + "Calling Sickbeard to process directory: %s", outputDestination)
            processEpisode(outputDestination)
        except Exception, e:
            logger.error(loggerHeader + "Sickbeard post process failed for directory: %s %s", outputDestination, (e, traceback.format_exc()))

    # Resume seeding in uTorrent if needed
    if uTorrent and fileAction == "move" or fileAction == "link":
        logger.debug(loggerHeader + "Start seeding torrent with hash: %s", inputHash)
        uTorrent.start(inputHash)

    logger.info(loggerHeader + "Success, all done!\n")

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

    # usage: uProcess.py "%D" "%N" "%I" "%L"
    inputDirectory = os.path.normpath(sys.argv[1])  # %D - Where the files are located
    inputName = sys.argv[2]                         # %N - The name of the torrent (as seen in uTorrent)
    inputHash = sys.argv[3]                         # %I - The hash of the torrent
    if sys.argv[4]:
        inputLabel = sys.argv[4]                    # %L - The label of the torrent
    else:
        inputLabel = False

    if not inputDirectory:
        logger.error(loggerHeader + "Torrent directory is missing")
    elif not inputName:
        logger.error(loggerHeader + "Torrent name is missing")
    elif not len(inputHash) == 40:
        logger.error(loggerHeader + "Torrent hash is missing")
    else:
        main(inputDirectory, inputName, inputHash, inputLabel)
