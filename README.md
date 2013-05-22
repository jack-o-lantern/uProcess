uProcess
========

a tiny python post processer for uTorrent

About:
---------
I initially made uProcess to be a "learn by doing" project, but has this far been proven a good utility to automate downloads using uTorrent. Feel free to fork me, make changes and what not :-)

Features:
---------
- Extract downloaded content - [List of supported archives](http://www.rarlab.com/otherfmt.htm "List of supported archives")
- Move, copy or (hard)link files that doesn't need extraction
- Multi OS compatible (Windows, Linux, OSX)
- Optionally calls Couchpotato or Sickbbeard when done (for additional post-processing)

Requirements:
---------
- [uTorrent 2.2.1 Build 25302](https://www.google.com/webhp?sourceid=chrome-instant&ion=1&ie=UTF-8#sclient=psy-ab&q=uTorrent+2.2.1+Build+25302&oq=uTorrent+2.2.1+Build+25302&gs_l=serp.12..0l2j0i30l2.6844.6844.0.8160.1.1.0.0.0.0.69.69.1.1.0...0.0...1c.1.14.psy-ab.ZcSwjn9xAbA&pbx=1&fp=1&biw=1920&bih=955&ion=1&bav=on.2,or.r_cp.r_qf.&cad=b
 "uTorrent 2.2.1 Build 25302")+ (confirmed), might work on earlier versions
- uTorrent Web UI activated
- [Python 2.7](http://www.python.org/download/releases/2.7/ "Python 2.7")

Usage:
---------
- Make sure you've installed uTorrent and Python correctly
- Grab uProcess [here](https://github.com/jkaberg/uProcess/archive/master.zip "here")
- Extract uProcess to any location, in this example C:\Downloaders\uProcess
- Setup uTorrent to use Web UI (Options->Preferences->Advanced->Web UI), note down user/password and listening port
- Edit the config.cfg file in C:\Downloaders\uProcess to your preferences
- Goto uTorrent again, in Options->Preferences->Advanced->Run Program, where it says "run this program when torrent finishes" add: C:\Python27\pythonw.exe C:\Downloaders\uProcess\uProcess.py "%D" "%N" "%I" "%L"
- DONE! ;)

Not working!?
---------
- Create an ticket over at the [issue tracker](https://github.com/jkaberg/uProcess/issues "issue tracker")
