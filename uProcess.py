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
import httplib
import traceback
import ConfigParser
from base64 import b16encode, b32decode

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
        
def pushoverMsg(msg):
    appkey = config.get("Pushover", "appkey")
    apikey = config.get("Pushover", "apikey")

    conn = httplib.HTTPSConnection("api.pushover.net:443")
    conn.request("POST", "/1/messages.json",
      urllib.urlencode({
        "token": appkey,
        "user": apikey,
        "message": msg,
      }), { "Content-type": "application/x-www-form-urlencoded" })
    conn.getresponse()
    return

def createLink(src, dst):
    try:
        if os.name == 'nt':
            import ctypes
            ctypes.windll.kernel32.CreateHardLinkW(dst, src, 0)
        else:
            os.link(src, dst)
    except Exception, e:
        logger.error(loggerHeader + "Linking failed: %s %s", (e, traceback.format_exc()))

def processMedia(mediaProcessor, output_dest):

    # couchpotato
    cp_host = config.get("Couchpotato", "host")
    cp_port = config.get("Couchpotato", "port")
    cp_baseurl = config.get("Couchpotato", "baseURL")
    cp_ssl = config.getboolean("Couchpotato", "ssl")
    cp_apikey = config.get("Couchpotato", "apikey")
    cp_usr = ''
    cp_pwr = ''

    # sickbeard
    sb_host = config.get("Sickbeard", "host")
    sb_port = config.get("Sickbeard", "port")
    sb_baseurl = config.get("Sickbeard", "baseURL")
    sb_ssl = config.getboolean("Sickbeard", "ssl")
    sb_usr = config.get("Sickbeard", "username")
    sb_pwr = config.get("Sickbeard", "password")

    baseURL = ''

    if mediaProcessor == "Couchpotato":
        if cp_baseurl:
            baseURL = cp_baseurl

        if cp_ssl:
            protocol = "https://"
        else:
            protocol = "http://"
            
        url = protocol + cp_host + ":" + cp_port + "/" + baseURL + "api/" + cp_apikey + "/renamer.scan/?async=1&movie_folder=" + output_dest
        myOpener = AuthURLOpener(cp_usr, cp_pwr)

    elif mediaProcessor == "Sickbeard":
        if sb_baseurl:
            baseURL = sb_baseurl

        if sb_ssl:
            protocol = "https://"
        else:
            protocol = "http://"

        url = protocol + sb_host + ":" + sb_port + "/" + baseURL + "home/postprocess/processEpisode?quiet=1&dir=" + output_dest
        myOpener = AuthURLOpener(sb_usr, sb_pwr)

    try:
        urlObj = myOpener.openit(url)
        logger.debug(loggerHeader + "Opening URL: %s", url)
    except Exception, e:
        logger.error(loggerHeader + "Unable to open URL: %s %s %s", (url, e, traceback.format_exc()))
        raise

    result = urlObj.readlines()
    for line in result:
        logger.debug(loggerHeader + line)

    timeout = time.time() + 60*2 # 2 min
    while os.path.exists(output_dest):

        if time.time() > timeout:
            logger.error(loggerHeader + "processMedia :: The output directory hasn't been deleted/processed after 2 minutes, check the logs at %s", mediaProcessor)
            if pushover_active:
                pushoverMsg("Output directory still exist for torrent " + os.path.split(output_dest)[1])

            break

        if os.path.isdir(output_dest) and not os.listdir(output_dest):
            os.rmdir(output_dest)

        elif os.listdir(output_dest):
            max_size = 1048576 * 200 # 200 mb
            for file in os.listdir(output_dest):
                file_path = os.path.join(output_dest, file)
                if os.path.getsize(file_path) <= max_size:
                    os.remove(file_path)

        time.sleep(10)

def findTorrent(ut_handle, tr_hash):
    status, torrents = ut_handle.list()  # http://www.utorrent.com/community/developers/webapi#devs6

    for torrent in torrents['torrents']:
        if torrent[0] == tr_hash:
            tr_hash = torrent[0]      # hash
            tr_name = torrent[2]      # name
            tr_progress = torrent[4]  # progress in mils (100% = 1000)
            tr_ratio = torrent[7]     # ratio in mils (1.292 ratio = 1292)
            tr_label = torrent[11]    # label

    return tr_hash, tr_name, tr_progress, tr_ratio, tr_label

def ratioCheck(ut_handle, tr_hash, delete_ratio):
    deleted_torrents = []
    status, torrents = ut_handle.list()  # http://www.utorrent.com/community/developers/webapi#devs6

    for torrent in torrents['torrents']:
        if torrent[0] != tr_hash and torrent[7] >= delete_ratio and delete_ratio != 0:
            deleted_torrents.append(torrent[2])
            ut_handle.removedata(torrent[0])

    return deleted_torrents

def findFiles(ut_handle, hash, ignore_words):

    media_ext = tuple((config.get("Miscellaneous", "media") + config.get("Miscellaneous", "meta") + config.get("Miscellaneous", "other")).split('|'))
    archive_ext = tuple((config.get("Miscellaneous", "compressed")).split('|'))

    media_files = []
    extr_files = []

    status, data = ut_handle.getfiles(tr_hash) # http://www.utorrent.com/community/developers/webapi#devs7
    hash, files = data['files']

    for file in files:
        file_name = file[0]
        if not os.path.isfile(os.path.join(tr_dir, file_name)):
            logger.error(loggerHeader + "File: %s doesn't exist in: %s", file_name, tr_dir)
            continue

        if not any(word in file_name.lower() for word in ignore_words):
            if file_name.endswith(media_ext):
                media_files.append(file_name)

            elif file_name.endswith(archive_ext):
                extr_files.append(file_name)

    return media_files, extr_files

def processFile(input_file, output_file, file_action):
    if not os.path.exists(os.path.split(output_file)[0]):
        os.makedirs(os.path.split(output_file)[0])

    if file_action == "move":
        logger.info(loggerHeader + "Moving file: %s to: %s", os.path.split(input_file)[1], os.path.split(output_file)[0])
        shutil.move(input_file, output_file)
    elif file_action == "link":
        logger.info(loggerHeader + "Linking file: %s to: %s", os.path.split(input_file)[1], os.path.split(output_file)[0])
        createLink(input_file, output_file)
    elif file_action == "copy":
        logger.info(loggerHeader + "Copying file: %s to: %s", os.path.split(input_file)[1], os.path.split(output_file)[0])
        shutil.copy(input_file, output_file)

def extractFile(input_file, output_dest):
    if not os.path.exists(output_dest):
        os.makedirs(output_dest)

    logger.info(loggerHeader + "Extracting: %s to: %s", os.path.split(input_file)[1], output_dest)
    pyUnRAR2.RarFile(input_file).extract(path = output_dest, withSubpath = False, overwrite = True)

def main(tr_dir, tr_hash):

    # uprocess
    output_dir = config.get("uProcess", "outputDirectory")
    file_action = config.get("uProcess", "fileAction")
    delete_finished = config.getboolean("uProcess", "deleteFinished")
    delete_ratio = config.getint("uProcess", "deleteRatio")
    ignore_label = (config.get("uProcess", "ignoreLabel")).split('|')

    # utorrent
    ut_host = "http://" + config.get("uTorrent", "host") + ":" + config.get("uTorrent", "port") + "/gui/"
    ut_usr = config.get("uTorrent", "username")
    ut_pwr = config.get("uTorrent", "password")

    # couchpotato
    cp_active = config.getboolean("Couchpotato", "active")
    cp_label = (config.get("Couchpotato", "label")).split('|')

    # sickbeard
    sb_active = config.getboolean("Sickbeard", "active")
    sb_label = (config.get("Sickbeard", "label")).split('|')

    # pushover
    pushover_active = config.getboolean("Pushover", "active")

    # miscellaneous
    ignore_words = (config.get("Miscellaneous", "ignore")).split('|')

    try:
        ut_handle = UTorrentClient(ut_host, ut_usr, ut_pwr)
    except Exception, e:
        logger.error(loggerHeader + "Failed to connect to uTorrent: %s", (ut_host, e, traceback.format_exc()))

    if ut_handle:
        tr_hash, tr_name, tr_progress, tr_ratio, tr_label = findTorrent(ut_handle, tr_hash)
        if tr_progress == 1000:
            if not any(word in tr_label for word in ignore_label):
                logger.info(loggerHeader + "Torrent Directory: %s", tr_dir)
                logger.info(loggerHeader + "Torrent Name: %s", tr_name)
                logger.debug(loggerHeader + "Torrent Hash: %s", tr_hash)

                if tr_label:
                    logger.info(loggerHeader + "Torrent Label: %s", tr_label)
                else:
                    tr_label = ''

                output_dest = os.path.join(output_dir, tr_label, tr_name)

                media_files, extr_files = findFiles(ut_handle, tr_hash, ignore_words)
                if media_files or extr_files:
                    if file_action == "move" or file_action == "link": # don't need to stop the torrent if we're copying
                        logger.debug(loggerHeader + "Stop seeding torrent with hash: %s", tr_hash)
                        ut_handle.stop(tr_hash)

                    for file in media_files:
                        input_file = os.path.join(tr_dir, file)
                        output_file = os.path.join(output_dest, file)
                        processFile(input_file, output_file, file_action)

                    for file in extr_files:
                        input_file = os.path.join(tr_dir, file)
                        extractFile(input_file, output_dest)

                    if cp_active or sb_active:
                        if any(word in tr_label for word in cp_label):
                            processMedia("Couchpotato", output_dest)

                        elif any(word in tr_label for word in sb_label):
                            processMedia("Sickbeard", output_dest)

                    if file_action == "move":
                        logger.debug(loggerHeader + "Removing torrent with hash: %s", tr_hash)
                        ut_handle.removedata(tr_hash)

                    elif file_action == "link":
                        logger.debug(loggerHeader + "Start seeding torrent with hash: %s", tr_hash)
                        ut_handle.start(tr_hash)

                deleted_torrents = ratioCheck(ut_handle, tr_hash, delete_ratio)
                if deleted_torrents:
                    for torrent in deleted_torrents:
                        logger.info(loggerHeader + "Ratio goal achieved, deleting torrent: %s", torrent)

                if delete_finished:
                    logger.debug(loggerHeader + "Removing torrent with hash: %s", tr_hash)
                    ut_handle.removedata(tr_hash)

                logger.info(loggerHeader + "Success! Everything done \n")

                if pushover_active:
                    pushoverMsg("Successfully processed torrent: " + tr_name)

            else:
                logger.error(loggerHeader + "uProcess is set to ignore label: %s \n", tr_label)
                sys.exit(-1)

        else:
            logger.error(loggerHeader + "Download hasn't completed for torrent: %s \n", tr_name)
            sys.exit(-1)

    else:
        logger.error(loggerHeader + "Couldn't connect to uTorrent \n")

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
    tr_dir = os.path.normpath((sys.argv[1]))                  # %D - The directory of the torrent, or in some cases a single file
    tr_hash = sys.argv[2]                                     # %I - The hash of the torrent

    if len(tr_hash) == 32:
        tr_hash = b16encode(b32decode(tr_hash))

    if not tr_dir:
        logger.error(loggerHeader + "Torrent directory is missing")
    elif not len(tr_hash) == 40:
        logger.error(loggerHeader + "Torrent hash is missing, or an invalid hash value has been passed")
    else:
        main(tr_dir, tr_hash)
