import ts3lib, ts3defines, sip, copy
from ts3plugin import ts3plugin, PluginHost
from pytson import getPluginPath, getCurrentApiVersion
from traceback import format_exc
from bluscream import *
from pytsonui import setupUi
sip.setapi('QVariant', 2)
from PythonQt.QtCore import Qt# , QVariant
from PythonQt.QtSql import QSqlDatabase
from PythonQt.QtGui import QWidget, QTableWidgetItem, QComboBox, QIcon
from os import path
import time

class channelGroupManager(ts3plugin):
    name = "Channel Group Manager"
    try: apiVersion = getCurrentApiVersion()
    except: apiVersion = 21
    requestAutoload = False
    version = "1.0"
    author = "Bluscream, shitty720"
    description = ""
    offersConfigure = False
    commandKeyword = "cgm"
    infoTitle = "[b]Channel Members:[/b]"
    menuItems = [(ts3defines.PluginMenuType.PLUGIN_MENU_TYPE_GLOBAL, 0, "Toggle {}".format(name), ""), (ts3defines.PluginMenuType.PLUGIN_MENU_TYPE_CHANNEL, 0, "Manage Members", "")]
    hotkeys = []
    dbpath = path.join(getPluginPath(), "scripts", "channelGroupManager", "members.db")
    ui = path.join(getPluginPath(), "scripts", "channelGroupManager", "members.ui")
    dlg = None
    cgroups = {}
    requestedCGroups = False
    waitForDBID = {}
    toggle = True
    """
    def infoData(self, schid, id, atype):
        try:
            if atype == ts3defines.PluginItemType.PLUGIN_CHANNEL:
                
                if len(i) < 1: return
                else: return i
        except: return
    """
    def __init__(self):
        # if not self.toggle: self.stop(); return
        self.db = QSqlDatabase.addDatabase("QSQLITE", self.__class__.__name__)
        self.db.setDatabaseName(self.dbpath)
        if not self.db.isValid(): raise Exception("Database invalid")
        if not self.db.open(): raise Exception("Could not open database.")
        self.loadVars()
        if PluginHost.cfg.getboolean("general", "verbose"): ts3lib.printMessageToCurrentTab("{0}[color=orange]{1}[/color] Plugin for pyTSon by [url=https://github.com/{2}]Bluscream[/url] loaded.".format(timestamp(), self.name, self.author))

    def stop(self):
        self.db.close()
        self.db.delete()
        QSqlDatabase.removeDatabase(self.__class__.__name__)

    def execSQL(self, query):
        if PluginHost.cfg.getboolean("general", "verbose"): print(self.name, "> Query:", query)
        d = self.db.exec_(query)
        if PluginHost.cfg.getboolean("general", "verbose"): print(self.name, "> Result:", d)
        return d

    def dbInsert(self, schid, cid, clid, cgid, dbid=None, invokerName="", invokerUID="", name="", uid=""):
        if PluginHost.cfg.getboolean("general", "verbose"): ts3lib.printMessageToCurrentTab("dbInsert(schid={}, cid={}, clid={}, cgid={}, dbid={}, invokerName={}, invokerUID={}, name={}, uid={})".format(schid, cid, clid, cgid, dbid, invokerName, invokerUID, name, uid))
        for v in [schid, cid, clid, cgid]:
            if v is None: return
        (err, suid) = ts3lib.getServerVariable(schid, ts3defines.VirtualServerProperties.VIRTUALSERVER_UNIQUE_IDENTIFIER)
        uuid = "{}|{}".format(suid, cid)
        self.execSQL("CREATE TABLE IF NOT EXISTS `{}` (`TIMESTAMP` NUMERIC, `NAME` TEXT, `UID` TEXT, `DBID` NUMERIC UNIQUE, `CGID` NUMERIC, `INVOKERNAME` TEXT, `INVOKERUID` TEXT);".format(uuid))
        q = "INSERT OR REPLACE INTO '{}' (TIMESTAMP, NAME, UID, DBID, CGID, INVOKERNAME, INVOKERUID) VALUES ({}, '{}', '{}', {}, {}, '{}', '{}')".format(uuid, int(time.time()), name, uid, dbid, cgid, invokerName, invokerUID)
        self.execSQL(q)

    def purgeDB(self, schid):
        (err, suid) = ts3lib.getServerVariable(schid, ts3defines.VirtualServerProperties.VIRTUALSERVER_UNIQUE_IDENTIFIER)
        (err, clist) = ts3lib.getChannelList(schid)
        d = self.execSQL("SELECT name FROM sqlite_master WHERE type='table'")
        drop = []
        while d.next():
            name = d.value("name").split('|')
            uid = name[0];cid = int(name[1])
            if uid != suid: continue
            if PluginHost.cfg.getboolean("general", "verbose"): print(self.name, "> CID:", cid)
            if not cid in clist: drop.append(cid)
        for cid in drop:
            name = "{}|{}".format(suid,cid)
            if PluginHost.cfg.getboolean("general", "verbose"): print(self.name, "> Deleting Table:", name)
            self.execSQL("DROP TABLE '{}';".format(name))

    def loadVars(self, schid=False):
        if not schid: schid = ts3lib.getCurrentServerConnectionHandlerID()
        self.purgeDB(schid)
        # for cid in clist:
        if schid in self.cgroups: return
        self.cgroups[schid] = {"groups": {}}
        self.requestedCGroups = True
        ts3lib.requestChannelGroupList(schid)
        ts3lib.requestServerVariables(schid)
        if PluginHost.cfg.getboolean("general", "verbose"): print(self.name, ">", "requested vars for #", schid)

    def onConnectStatusChangeEvent(self, schid, newStatus, errorNumber):
        if not self.toggle: return
        if newStatus == ts3defines.ConnectStatus.STATUS_CONNECTION_ESTABLISHED: self.loadVars(schid)
        elif newStatus == ts3defines.ConnectStatus.STATUS_DISCONNECTED:
            if schid in self.cgroups: del self.cgroups[schid]

    def onServerUpdatedEvent(self, schid):
        if not self.toggle: return
        (err, dcgid) = ts3lib.getServerVariable(schid, ts3defines.VirtualServerPropertiesRare.VIRTUALSERVER_DEFAULT_CHANNEL_GROUP)
        (err, acgid) = ts3lib.getServerVariable(schid, ts3defines.VirtualServerPropertiesRare.VIRTUALSERVER_DEFAULT_CHANNEL_ADMIN_GROUP)
        self.cgroups[schid]["default"] = dcgid;self.cgroups[schid]["admin"] = acgid
        if PluginHost.cfg.getboolean("general", "verbose"): print(self.name, ">", "new default channel groups for #", schid, "default:", dcgid, "admin:", acgid)

    def onMenuItemEvent(self, schid, atype, menuItemID, selectedItemID):
        if menuItemID != 0: return
        if atype == ts3defines.PluginMenuType.PLUGIN_MENU_TYPE_CHANNEL:
            if not self.dlg: self.dlg = channelGroupMembersDialog(self, schid, selectedItemID)
            else: self.dlg.setup(self, schid, selectedItemID)
            self.dlg.show()
            self.dlg.raise_()
            self.dlg.activateWindow()
        elif atype == ts3defines.PluginMenuType.PLUGIN_MENU_TYPE_GLOBAL:
            self.toggle = not self.toggle
            ts3lib.printMessageToCurrentTab("{} set to [color=orange]{}[/color]".format(self.name, self.toggle))

    def onChannelGroupListEvent(self, schid, cgid, name, atype, iconID, saveDB):
        if not self.toggle: return
        if not self.requestedCGroups: return
        if atype == GroupType.TEMPLATE: return
        self.cgroups[schid]["groups"][cgid] = {}
        self.cgroups[schid]["groups"][cgid]["name"] = name
        self.cgroups[schid]["groups"][cgid]["icon"] = iconID
        if PluginHost.cfg.getboolean("general", "verbose"): print(self.name, ">", "new channelgroup for #", schid, "(", cgid, ")", ":", self.cgroups[schid]["groups"][cgid])

    def onChannelGroupListFinishedEvent(self, schid):
        if not self.toggle: return
        if self.requestedCGroups: self.requestedCGroups = False

    def onClientChannelGroupChangedEvent(self, schid, channelGroupID, channelID, clid, invokerClientID, invokerName, invokerUniqueIdentity):
        if not self.toggle: return
        if invokerClientID == 0: return
        if PluginHost.cfg.getboolean("general", "verbose"): print(self.name, ">", "channelGroupID:", channelGroupID, "channelID:", channelID, "clientID:", clid, "invokerClientID:", invokerClientID, "invokerName:", invokerName, "invokerUniqueIdentity:", invokerUniqueIdentity)
        if not schid in self.cgroups: return
        if "default" in self.cgroups[schid]:
            if channelGroupID == self.cgroups[schid]["default"]: return # TODO: Maybe reimplement
        (err, name) = ts3lib.getClientVariable(schid, clid, ts3defines.ClientProperties.CLIENT_NICKNAME)
        (err, uid) = ts3lib.getClientVariable(schid, clid, ts3defines.ClientProperties.CLIENT_UNIQUE_IDENTIFIER)
        (err, dbid) = ts3lib.getClientVariable(schid, clid, ts3defines.ClientPropertiesRare.CLIENT_DATABASE_ID)
        self.dbInsert(schid, channelID, clid, channelGroupID, dbid, invokerName, invokerUniqueIdentity, name, uid)

    def onNewChannelCreatedEvent(self, schid, cid, channelParentID, clid, name, uid):
        if not self.toggle: return
        if not schid in self.cgroups: return
        (err, sname) = ts3lib.getServerVariable(schid, ts3defines.VirtualServerProperties.VIRTUALSERVER_NAME)
        (err, suid) = ts3lib.getServerVariable(schid, ts3defines.VirtualServerProperties.VIRTUALSERVER_UNIQUE_IDENTIFIER)
        (err, dbid) = ts3lib.getClientVariable(schid, clid, ts3defines.ClientPropertiesRare.CLIENT_DATABASE_ID)
        if err != ts3defines.ERROR_ok or not dbid:
            if not schid in self.waitForDBID: self.waitForDBID[schid] = list()
            item = (uid, name, clid, cid, suid, sname)
            self.waitForDBID[schid].append(item)
            ts3lib.requestClientDBIDfromUID(schid, uid)
            return
        cgid = self.cgroups[schid]["admin"]
        # ts3lib.printMessageToCurrentTab("onNewChannelCreatedEvent > NEW CHANNEL CREATED BY {} as {}".format(clid, cgid))
        self.dbInsert(schid, cid, clid, cgid, dbid, sname, suid)

    def onClientDBIDfromUIDEvent(self, schid, uid, dbid):
        if not self.toggle: return
        if not schid in self.waitForDBID: return
        for item in self.waitForDBID[schid]:
            if item[0] != uid: continue
            # ts3lib.printMessageToCurrentTab(str(item))
            self.dbInsert(schid, item[3], item[2], self.cgroups[schid]["admin"], dbid, item[5], item[4], item[1], item[0])
            if len(self.waitForDBID[schid]) < 2: del self.waitForDBID[schid]
            # else: self.waitForDBID[schid].remove()
            return

# Error calling method onClientDBIDfromUIDEvent of plugin Channel Group Manager: Traceback (most recent call last):
    #   File "C:/Users/blusc/AppData/Roaming/TS3Client/plugins/pyTSon/scripts\pluginhost.py", line 395, in invokePlugins
    #     ret.append(meth(*args))
    #   File "C:/Users/blusc/AppData/Roaming/TS3Client/plugins/pyTSon/scripts\channelGroupManager\__init__.py", line 174, in onClientDBIDfromUIDEvent
    #     else: self.waitForDBID[schid].remove()
    # TypeError: remove() takes exactly one argument (0 given)

    def onDelChannelEvent(self, schid, channelID, invokerID, invokerName, invokerUniqueIdentifier):
        if not self.toggle: return
        if not schid in self.cgroups: return
        (err, suid) = ts3lib.getServerVariable(schid, ts3defines.VirtualServerProperties.VIRTUALSERVER_UNIQUE_IDENTIFIER)
        self.execSQL("DROP TABLE IF EXISTS '{}|{}';".format(suid,channelID))

    def processCommand(self, schid, cmd):
        cmd = cmd.split(' ', 1)
        command = cmd[0].lower()
        if command == "info":
            print(self.cgroups)
            print("toggle:", self.toggle)
            print("waitForDBID", self.waitForDBID)
            return True

class channelGroupMembersDialog(QWidget): # TODO: https://stackoverflow.com/questions/1332110/selecting-qcombobox-in-qtablewidget
    def __init__(self, channelGroupManager, schid, cid, parent=None):
        try:
            super(QWidget, self).__init__(parent)
            setupUi(self, channelGroupManager.ui)
            self.setAttribute(Qt.WA_DeleteOnClose)
            self.setup(channelGroupManager, schid, cid)
        except: ts3lib.logMessage(format_exc(), ts3defines.LogLevel.LogLevel_ERROR, "pyTSon", 0)

    def setup(self, channelGroupManager, schid, cid):
            self.schid = schid
            self.cid = cid
            cgroups = channelGroupManager.cgroups
            cgroups = cgroups[schid]
            cgroups = cgroups["groups"]
            self.cgroups = cgroups
            self.db = channelGroupManager.db
            self.execSQL = channelGroupManager.execSQL
            (err, cname) = ts3lib.getChannelVariable(schid, cid, ts3defines.ChannelProperties.CHANNEL_NAME)
            self.setWindowTitle("Members of \"{}\"".format(cname))
            self.tbl_members.setColumnWidth(0, 130)
            self.tbl_members.setColumnWidth(1, 250)
            self.tbl_members.setColumnWidth(2, 215)
            self.tbl_members.setColumnWidth(3, 50)
            self.tbl_members.setColumnWidth(4, 140)
            self.setupTable()

    def setupTable(self):
        try:
            self.tbl_members.clearContents()
            self.tbl_members.setRowCount(0)
            cache = ts3client.ServerCache(self.schid)
            (err, suid) = ts3lib.getServerVariable(self.schid, ts3defines.VirtualServerProperties.VIRTUALSERVER_UNIQUE_IDENTIFIER)
            q = self.execSQL("SELECT * FROM '{}|{}'".format(suid, self.cid))
            while q.next():
                pos = self.tbl_members.rowCount
                if PluginHost.cfg.getboolean("general", "verbose"): print(pos)
                self.tbl_members.insertRow(pos)
                self.tbl_members.setItem(pos, 0, QTableWidgetItem(datetime.utcfromtimestamp(q.value("timestamp")).strftime('%Y-%m-%d %H:%M:%S')))
                self.tbl_members.setItem(pos, 1, QTableWidgetItem(q.value("name")))
                self.tbl_members.setItem(pos, 2, QTableWidgetItem(q.value("uid")))
                self.tbl_members.setItem(pos, 3, QTableWidgetItem(str(q.value("dbid"))))
                box = QComboBox()
                box.connect("currentIndexChanged(int index)", self.currentIndexChanged)
                i = 0
                for cgroup in self.cgroups:
                    icon = QIcon(cache.icon(self.cgroups[cgroup]["icon"]))
                    text = "{} ({})".format(self.cgroups[cgroup]["name"], cgroup)
                    box.addItem(icon, text)
                    box.setItemData(i, cgroup)
                    if cgroup == q.value("cgid"): box.setCurrentIndex(i)
                    i += 1
                self.tbl_members.setCellWidget(pos, 4, box)
                self.tbl_members.setItem(pos, 5, QTableWidgetItem("{} ({})".format(q.value("invokername"), q.value("INVOKERUID"))))
        except: ts3lib.logMessage(format_exc(), ts3defines.LogLevel.LogLevel_ERROR, "pyTSon", 0)

    def currentIndexChanged(self, i):
        try:
            # schid, cgid, cid, cldbid
            schid = self.schid
            # cgid = ?
            cid = self.cid
            # cldbid = ?
            if PluginHost.cfg.getboolean("general", "verbose"): print("test", i)
            row = self.tbl_members.currentRow()
            if PluginHost.cfg.getboolean("general", "verbose"): print("row:", row)
            # item = self.tbl_members.itemAt(const QPoint &point)
            # item = self.tbl_members.selectedItems()
            # print("item:", item)
            # self.tbl_members.at
            # ts3lib.requestSetClientChannelGroup(self.schid, [item.itemData], [self.channel], [self.dbid])
        except: ts3lib.logMessage(format_exc(), ts3defines.LogLevel.LogLevel_ERROR, "pyTSon", 0)

    def on_btn_close_clicked(self): self.close()

    def on_btn_reload_clicked(self): self.setupTable()
