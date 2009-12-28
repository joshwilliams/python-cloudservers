# Copyright (c) 2009, Rackspace.
# See COPYING for details.

"""
ServerManager class.  Cloud Servers Entity Manager for Servers.

Provides interface for all Server operations as a component part of a Cloud Servers Service object.
"""

from datetime import datetime
import time

from com.rackspace.cloud.servers.api.client.entitymanager import EntityManager
from com.rackspace.cloud.servers.api.client.entitylist import EntityList

from com.rackspace.cloud.servers.api.client.errors import NotImplementedException, CloudServersAPIFault
from com.rackspace.cloud.servers.api.client.server import Server
from com.rackspace.cloud.servers.api.client.jsonwrapper import json
from com.rackspace.cloud.servers.api.client.backupschedule import BackupSchedule

class RebootType(object):
    """
    Just encloses hard/soft reboots so they can be referenced as
    rebootType.hard and rebootType.soft
    """
    hard = "HARD"
    soft = "SOFT"

"""
rebootType is just an instance of RebootType() for referring to hard/soft
reboots
"""
rebootType = RebootType()

class ServerManager(EntityManager):
    """
    Entity manager for servers.
    """
    def __init__(self, parent):
        super(ServerManager, self).__init__(parent, "servers")
        self._resizedServerIds = []

    #
    # Inherited
    #
    def create(self, server):
        """
        Create an actual server from the passed Server object
        """
        ret = self._POST(server.asJSON)
        # We update the object so it knows we're its manager
        # the manager property is ReadOnly so we're using an
        # internal variable here.  We're its manager, that's OK.
        server._manager = self
        server.initFromResultDict(ret["server"])

    # implemented in EntityManager
    #remove(self, server):
    #    self._DELETE(server.id)
    #    self.update(server) # get up-to-date status

    def update(self, server):
        server.initFromResultDict(self.serverDetails(server.id))
        server._manager = self

    def refresh(self, server):
        server.initFromResultDict(self.serverDetails(server.id))
        server._manager = self

    def find(self, id):
        """
        Find the server given by `id` and returns a Server object filled with
        data from the API or None if the `id` can't be found.
        """
        try:
            detailsDict = self.serverDetails(id)
        except CloudServersAPIFault, e:
            if e.code == 404:   # not found
                return None     # just return None
            else:               # some other exception, just re-raise
                raise

        retServer = Server("")
        retServer.initFromResultDict(detailsDict)
        retServer._manager = self
        return retServer

    def status(self, id):
        """
        Get current status of server with `id`, returns statusDict so that
        server can update itself.
        """
        statusDict = self.serverDetails(id)
        return(statusDict["status"])

    def serverDetails(self, id):
        """
        Gets details dictionary for server with `id`.  If the server can't
        be found, returns None
        """
        retDict = None
        ret = self._GET(id, { "now": str(datetime.now()) })
        try:
            retDict = ret["server"]
        except KeyError, e:
            retDict = None

        return retDict

    #
    # ServerManager specificCloudServersAPIFault
    #

    def _post_action(self, id, data):
        url_parts = (id, "action")
        print "url_parts: ", url_parts
        self._POST(data, url_parts)

    def _put_action(self, id, action):
        url_parts = (id, "action", action)
        self._PUT(id, url_parts)

    def _delete_action(self, id, action):
        self._DELETE(id, "action", action)

    def reboot(self, server, rebootType):
        """
        Reboot a server either "HARD", "SOFT".

        "SOFT" signals reboot with notification i.e. 'graceful'
        "HARD" forces reboot with no notification i.e. power cycle the server.
        """
        if rebootType in ("HARD", "SOFT"):
            id = server.id
            data = json.dumps({"reboot": {"type": rebootType}})
            self._post_action(id, data)
            self.refresh(server)    # get updated status
        else:
            raise InvalidArgumentsFault("Bad value %s passed for reboot type, must be 'HARD' or 'SOFT'", rebootType)

    def rebuild(self, server, imageId=None):
        """
        Rebuild a server, optionally specifying a different image.  If no new
        image is supplied, the original is used.
        """
        if not imageId:
            imageId = server.imageId
        data = json.dumps({"rebuild": {"imageId":imageId}})
        id = server.id
        self._post_action(id, data)

    def resize(self, server, flavorId):
        """
        Change a server to a different size/flavor.  A backup is kept of the
        original until you confirmResize or it recycles automatically (after
        24 hours).
        """
        if not flavorId:
            flavorId = server.flavorId
        data = json.dumps({"resize": {"flavorId":flavorId}})
        id = server.id
        print "data: ", data
        self._post_action(id, data)

    def confirmResize(self, server):
        """
        Confirm resized server, i.e. confirm that resize worked and it's OK to
        delete all backups made when resize was performed.
        """
        data = json.dumps({"confirmResize": None})
        id = server.id
        print "data: ", data
        self._post_action(id, data)


    def revertResize(self, server):
        """
        Revert a resize operation, restoring the server from the backup made
        when the resize was performed.
        """
        data = json.dumps({"revertResize": None})
        id = server.id
        print "data: ", data
        self._post_action(id, data)

    def shareIp (server, ipAddr, sharedIpGroupId, configureServer):
        url_parts = (id, "ips", "public", ipAddr)
        print "url_parts: ", url_parts
        data = json.dumps({"shareIp": {"sharedIpGroupId": sharedIpGroupId,"configureServer": configureServer}})
        print "data: ", data
        self._PUT(data, url_parts)

    def unshareIp (server, ipAddr):        
        self._DELETE(id, "ips", "public", ipAddr)

    def setSchedule(self, server, backupSchedule):
        url_parts = (server.id, "backup_schedule")
        self._POST(backupSchedule.asJSON, url_parts)

    def getSchedule(self, server):
        backupDict = self._GET(server.id, "backup_schedule")
        backupSchedule = BackupSchedule()
        backupSchedule.initFromResultDict(backupDict["backupSchedule"])
        return backupSchedule

    #
    ## Polling operations
    #
    def _serverInWaitState(self, server):
        
        # For Servers, the following are considered end states by the wait call: 
        end_states = ['ACTIVE', 'SUSPENDED', 'VERIFY_RESIZE', 'DELETED', 'ERROR', 'UNKNOWN']
        
        # Note that VERIFY_RESIZE can also serve as a start state, 
        # implementations are responsible for keeping track of whether this state should be 
        # treated as a start or end condition.        
        # if self._resizing(server):
        #     end_states.remove('VERIFY_RESIZE')

        try:
            end_states.index(server.status)
            inWaitState = False # if we made it this far, it's not in a wait state
        except ValueError:
            inWaitState = True
        return inWaitState
    
    def _wait(self, server):
        """
        Wait implementation
        """
        while self._serverInWaitState(server):
            try:
                self.refresh(server)
                print "Status: ", server.status, " Progress: ", server.progress
            except OverLimitFault as olf:
                # sleep until retry_after to avoid more OverLimitFaults
                timedelta = datetime.now - datetime.strptime(olf.retryAfter, '%Y-%m-%dT%H:%M:%SZ')                
                sleep((timedelta.days * 86400) + timedelta.seconds)
            except CloudServersFault:
                pass

    def wait (self, server, timeout=None):
        """
        For Servers, an end condition is determined by an end state such as 
        ACTIVE or ERROR and may also be determined by a progress setting of 100.

      	timeout is in milliseconds
        """
        if timeout==None:
            self._wait(server)
        else:
            print "start counting"
            result = self._timeout(self._wait, (server,), timeout_duration=timeout/1000.0)

    def notify (self, server, changeListener):
        raise NotImplementedException

    def stopNotify (self, server, changeListener):
        raise NotImplementedException

    #
    ## Support methods
    #
    def createEntityListFromResponse(self, response, detail=False):
        """
        Creates list of server objects from response to list command sent
        to API
        """
        theList = []
        data = response["servers"]
        for jsonObj in data:
            s = Server("")
            s.initFromResultDict(jsonObj)
            theList.append(s)

        return EntityList(theList, detail, self)
