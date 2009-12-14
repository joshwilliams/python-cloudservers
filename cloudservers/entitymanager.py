# Copyright (c) 2009, Rackspace.
# See COPYING for details.


"""
EntityManager base class.  EntityManagers belong to a CloudServersService object and
one is provided for each type of managed Entity: Servers, Images, Flavors, and
Shared IP Group.
"""
import sys

from cloudservers.consts import DEFAULT_PAGE_SIZE, BEGINNING_OF_TIME
from cloudservers.entitylist import EntityList
from cloudservers.errors import BadMethodFault
from cloudservers.shared.utils import build_url, find_in_list
from cloudservers.shared.cslogging import cslogger

_bmf = BadMethodFault

class EntityManager(object):
    """
    EntityManager defines the base functionality of an entity manager and
    provides a standardized way of encapsulating the HTTP operations.

    Note that not all calls may be supported by all entity managers (you are
    not allowed to delete a Flavor, for example) and that it is possible for
    entity managers to extend the base interface with additional calls.

    See the documentation for those managers for details.
    """
    def __init__(self, cloudServersService, requestPrefix, responseKey=None):
        """
        Create the Entity manager.

        Each entity manager has its own `_requestPrefix` used to build API
        calls.

        Since not every entity type uses the `_requestPrefix` to retrieve
        data from the API's response object, we can send in an optional
        responseKey.  If there's no responseKey, it defaults to the requestPrefix.

        The responseKey is only necessary, so far, on Shared IP Groups.
        """
        # TBD: what's currently referred to as "cloudServersService", really is our owner
        self._cloudServersService = cloudServersService
        self._requestPrefix = requestPrefix

        #
        ## responseKey is used to handle cases where the key into the returned
        ## response is not the same as the url component used to make
        ## requests
        #
        if responseKey:
            self._responseKey = responseKey
        else:
            self._responseKey = requestPrefix

    #
    ## These methods hide that we're calling our _cloudServersService to do everything
    #
    def _POST(self, data, *url_parts):
        """
        Put together a full POST request and send to our cloudServersService.
        """
        url = build_url(self._requestPrefix, *url_parts)
        # print "entitymanager._POST, url == ", url, data
        retVal = self._cloudServersService.POST(url, data=data)
        return(retVal)

    def _DELETE(self, id, *url_parts):
        """
        Put together a full DELETE request and send it on via our cloudServersService
        """
        url = build_url(self._requestPrefix, id, *url_parts)
        retVal = self._cloudServersService.DELETE(url)
        return retVal

    def _GET(self, url, params=None):
        url = build_url(self._requestPrefix, url)
        retVal = self._cloudServersService.GET(url,params)
        return retVal

    def _PUT(self, *url_parts):
        url = build_url(self._requestPrefix, *url_parts)
        retVal = self._cloudServersService.PUT(url)
        return retVal

    #
    #  CRUD Operations
    #
    # The default implementation of the CRUD operations raises a
    # BadMethodFault exception.
    #
    # For those classes that shouldn't implement these methods, this is the
    # correct exception.
    #
    # For those methods inherited from EntityManager, if the child class does
    # not provide a method by design, it must explicitly raise BadMethodFault.

    def create(self, entity):
        "Create entity, implemented by child classes."
        raise _bmf(self.__class__)

    def remove(self, entity):
        "Remove entity."
        self._DELETE(entity.id)

    def update(self, entity):
        "Update entity, implemented by child classes."
        raise _bmf(self.__class__)

    def refresh(self, entity):
        "Refresh entity, implemented by child classes."
        raise _bmf(self.__class__)

    def find(self, id):
        """
        Find entity by `id`.
        """
        raise _bmf

    #
    # Polling Operations
    #
    def wait (self, entity):
        "wait, implemented by child classes."
        raise _bmf

    def waitT (self, entity, timeout):
        "wait with timeout, implemented by child classes."
        raise _bmf

    def notify (self, entity, changeListener):
        "notify, implemented by child classes."
        raise _bmf

    def stopNotify (self, entity, changeListener):
        "stopNotify, implemented by child classes."
        raise _bmf

    #
    # Lists
    #
    def _createList(self, detail=False, offset=0, limit=DEFAULT_PAGE_SIZE, lastModified=BEGINNING_OF_TIME):
        """
        Master function that can perform all possible combinations.

        Called by publicly accessible methods to do the actual work.

        What this really has to do is set up a ValueListIterator which will
        then ask us back for the actual data when it's requested.

        http://www.informit.com/articles/article.aspx?p=26148&seqNum=4

        This will actually fetch one page of results so, for efficiency, the
        iterator will have to be clever enough not to re-fetch on the first
        access.
        """
        # Set flags for parameters we have to act on
        conditionalGet = (lastModified != BEGINNING_OF_TIME)
        pagedGet = (offset != 0 or limit != DEFAULT_PAGE_SIZE)

        uri = self._requestPrefix
        if detail:
            uri += "/detail"
        params = {"offset":offset, "limit":limit}
        retHeaders = list() # we may need "last-modified"
        ret_obj = self._cloudServersService.GET(uri, params, retHeaders=retHeaders)
        theList = ret_obj[self._responseKey]

        # Create the entity list
        entityList = self.createEntityListFromResponse(ret_obj, detail)

        cslogger.debug(ret_obj)
        cslogger.debug(retHeaders)

        if not conditionalGet:
            # For a non-conditional get, we store the one from the
            # returned headers for subsequent conditional gets
            lastModifiedAsString = find_in_list(retHeaders, "last-modified")

        # Now, make the entity list aware of enough state information to
        # perform future operations properly
        data = {'conditionalGet': conditionalGet,
                'pagedGet'      : pagedGet,
                'lastModified'  : lastModified,
                'lastModifiedAsString' : lastModifiedAsString,
                }

        return entityList

    def createList(self, detail):
        """
        Create a list of all items, optionally with details.
        """
        return self._createList(detail)

    def createDeltaList(self, detail, changes_since):
        """
        Create a list of all items modified since a specific time."""
        return self._createList(detail, changes_since=changes_since)

    #
    # Lists, Paged
    #
    def createListP(self, detail, offset, limit):
        """
        Create a paged list.
        """
        return self._createList(detail, offset=offset, limit=limit)

    def createDeltaListP(self, detail, changes_since, offset, limit):
        """
        Create a paged list of items changed since a particular time
        """
        return self._createDeltaList(detail, changes_since=changes_since, offset=offset, limit=limit,)
