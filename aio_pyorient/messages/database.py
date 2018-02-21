from aio_pyorient.constants import (DB_CLOSE_OP, DB_COUNT_RECORDS_OP, DB_CREATE_OP, DB_DROP_OP, DB_EXIST_OP, DB_LIST_OP,
                                    DB_OPEN_OP, DB_RELOAD_OP, DB_SIZE_OP, DB_TYPES, DB_TYPE_DOCUMENT, DB_TYPE_GRAPH,
                                    FIELD_BOOLEAN, FIELD_BYTE, FIELD_BYTES, FIELD_INT, FIELD_LONG, FIELD_SHORT,
                                    FIELD_STRING, FIELD_STRINGS, NAME, STORAGE_TYPES, STORAGE_TYPE_LOCAL,
                                    STORAGE_TYPE_PLOCAL, SUPPORTED_PROTOCOL, VERSION)
from aio_pyorient.exceptions import PyOrientBadMethodCallException
from aio_pyorient.messages.base import BaseMessage
from aio_pyorient.otypes import OrientCluster, OrientNode, OrientRecord, OrientVersion


class DbOpenMessage(BaseMessage):
    def __init__(self, _orient_socket):
        super().__init__(_orient_socket)

        self._user = ''
        self._pass = ''
        self._client_id = ''
        self._db_name = ''
        self._db_type = DB_TYPE_GRAPH
        self._append(( FIELD_BYTE, DB_OPEN_OP ))
        self._need_token = False

    def prepare(self, params=None):

        if isinstance(params, tuple) or isinstance(params, list):

            self._append((FIELD_STRINGS, [NAME, VERSION]))
            self._append((FIELD_SHORT, SUPPORTED_PROTOCOL))
            self._append((FIELD_STRING, self._client_id))

            if self.protocol > 21:
                self._append((FIELD_STRING, self._connection.serialization_type))
                if self.protocol > 26:
                    self._append((FIELD_BOOLEAN, self._request_token))
                    if self.protocol >= 36:
                        self._append((FIELD_BOOLEAN, True))  # support-push
                        self._append((FIELD_BOOLEAN, True))  # collect-stats

            self._append((FIELD_STRING, self._db_name))

            if self.protocol < 33:
                self._append((FIELD_STRING, self._db_type))

            self._append((FIELD_STRING, self._user))
            self._append((FIELD_STRING, self._pass))
            try:
                self._db_name = params[0]
                self._user = params[1]
                self._pass = params[2]
                self.set_db_type(params[3])
                self._client_id = params[4]

            except IndexError:
                # Use default for non existent indexes
                pass


        return super().prepare()

    async def fetch_response(self):
        self._append(FIELD_INT)  # session_id
        if self.protocol > 26:
            self._append(FIELD_STRING)  # token # if FALSE: Placeholder

        self._append(FIELD_SHORT)  # cluster_num

        result = await super().fetch_response()
        if self.protocol > 26:
            self._connection.session_id, self._connection.auth_token, cluster_num = result
            if self.auth_token == b'':
                self.set_session_token(False)
        else:
            self._connection.session_id, cluster_num = result

        clusters = []

        # Parsing cluster map TODO: this must be put in serialization interface
        for x in range(0, cluster_num):
            if self.protocol < 24:
                cluster = OrientCluster(
                    await self._decode_field(FIELD_STRING),
                    await self._decode_field(FIELD_SHORT),
                    await self._decode_field(FIELD_STRING),
                    await self._decode_field(FIELD_SHORT)
                )
            else:
                cluster = OrientCluster(
                    await self._decode_field(FIELD_STRING),
                    await self._decode_field(FIELD_SHORT)
                )
            clusters.append(cluster)

        self._append(FIELD_STRING)  # orient node list | string ""
        self._append(FIELD_STRING)  # Orient release

        nodes_config, release = await super().fetch_response(True)

        # parsing server release version
        info = OrientVersion(release)
        if len(nodes_config) > 0:
            _, decoded = self.get_serializer().decode(nodes_config)
            self._node_list = []
            print(f"{self._name} decoded: {decoded}")
            for node_dict in decoded.pop('members', {}):
                self._node_list.append(OrientNode(node_dict))

        # set database opened
        self._connection.db_opened = self._db_name

        return info, clusters, self._node_list
        # self._cluster_map = self._orientSocket.cluster_map = \
        #     Information([clusters, response, self._orientSocket])

        # return self._cluster_map

    def set_db_name(self, db_name):
        self._db_name = db_name
        return self

    def set_db_type(self, db_type):
        if db_type in DB_TYPES:
            # user choice storage if present
            self._db_type = db_type
        else:
            raise PyOrientBadMethodCallException(
                db_type + ' is not a valid database type', []
            )
        return self

    def set_client_id(self, _cid):
        self._client_id = _cid
        return self

    def set_user(self, _user):
        self._user = _user
        return self

    def set_pass(self, _pass):
        self._pass = _pass
        return self


#
# DB CLOSE
#
# Closes the database and the network connection to the ODBClient Server
# instance. No return is expected. The socket is also closed.
#
# Request: empty
# Response: no response, the socket is just closed at server side
#
class DbCloseMessage(BaseMessage):
    def __init__(self, _orient_socket):
        super().__init__(_orient_socket)

        # order matters
        self._append(( FIELD_BYTE, DB_CLOSE_OP ))

    def prepare(self, params=None):
        return super().prepare()

    async def fetch_response(self):
        # set database closed
        self._connection.db_opened = None
        super().close()
        return 0


#
# DB EXISTS
#
# Asks if a database exists in the ODBClient Server instance. It returns true (non-zero) or false (zero).
#
# Request: (database-name:string) <-- before 1.0rc1 this was empty (server-storage-type:string - since 1.5-snapshot)
# Response: (result:byte)
#
# server-storage-type can be one of the supported types:
# plocal as a persistent database
# memory, as a volatile database
#
class DbExistsMessage(BaseMessage):
    def __init__(self, _orient_socket):
        super().__init__(_orient_socket)

        self._db_name = ''
        self._storage_type = ''

        if self.protocol > 16:  # 1.5-SNAPSHOT
            self._storage_type = STORAGE_TYPE_PLOCAL
        else:
            self._storage_type = STORAGE_TYPE_LOCAL

        # order matters
        self._append(( FIELD_BYTE, DB_EXIST_OP ))

    def prepare(self, params=None):

        if isinstance(params, tuple) or isinstance(params, list):
            try:
                self._db_name = params[0]
                # user choice storage if present
                self.set_storage_type(params[1])

            except IndexError:
                # Use default for non existent indexes
                pass

        if self.protocol >= 6:
            self._append(( FIELD_STRING, self._db_name ))  # db_name

        if self.protocol >= 16:
            # > 16 1.5-snapshot
            # custom choice server_storage_type
            self._append(( FIELD_STRING, self._storage_type ))

        return super().prepare()

    async def fetch_response(self):
        self._append(FIELD_BOOLEAN)
        return list(await super().fetch_response())[0]

    def set_db_name(self, db_name):
        self._db_name = db_name
        return self

    def set_storage_type(self, storage_type):
        if storage_type in STORAGE_TYPES:
            # user choice storage if present
            self._storage_type = storage_type
        else:
            raise PyOrientBadMethodCallException(
                storage_type + ' is not a valid storage type', []
            )
        return self


#
# DB CREATE
#
# Creates a database in the remote ODBClient server instance
#
# Request: (database-name:string)(database-type:string)(storage-type:string)
# Response: empty
#
# - database-name as string. Example: "demo"
# - database-type as string, can be 'document' or 'graph' (since version 8). Example: "document"
# - storage-type can be one of the supported types:
# - plocal, as a persistent database
# - memory, as a volatile database
#
class DbCreateMessage(BaseMessage):
    def __init__(self, _orient_socket):
        super().__init__(_orient_socket)

        self._db_name = ''
        self._db_type = DB_TYPE_DOCUMENT
        self._storage_type = ''
        self._backup_path = -1

        if self.protocol > 16:  # 1.5-SNAPSHOT
            self._storage_type = STORAGE_TYPE_PLOCAL
        else:
            self._storage_type = STORAGE_TYPE_LOCAL

        # order matters
        self._append(( FIELD_BYTE, DB_CREATE_OP ))

    def prepare(self, params=None):

        if isinstance(params, tuple) or isinstance(params, list):
            try:
                self._db_name = params[0]
                self.set_db_type(params[1])
                self.set_storage_type(params[2])
                self.set_backup_path(params[3])
            except IndexError:
                pass

        self._append(
            (FIELD_STRINGS, [self._db_name, self._db_type, self._storage_type ])
        )

        if self.protocol > 35:
            if isinstance( self._backup_path, int ):
                field_type = FIELD_INT
            else:
                field_type = FIELD_STRING
            self._append( ( field_type, self._backup_path ) )

        return super().prepare()

    async def fetch_response(self):
        await super().fetch_response()
        # set database opened
        self._connection.db_opened = self._db_name
        return

    def set_db_name(self, db_name):
        self._db_name = db_name
        return self

    def set_backup_path(self, backup_path):
        self._backup_path = backup_path
        return self

    def set_db_type(self, db_type):
        if db_type in DB_TYPES:
            # user choice storage if present
            self._db_type = db_type
        else:
            raise PyOrientBadMethodCallException(
                db_type + ' is not a valid database type', []
            )
        return self

    def set_storage_type(self, storage_type):
        if storage_type in STORAGE_TYPES:
            # user choice storage if present
            self._storage_type = storage_type
        else:
            raise PyOrientBadMethodCallException(
                storage_type + ' is not a valid storage type', []
            )
        return self


#
# DB DROP
#
# Removes a database from the ODBClient Server instance.
# It returns nothing if the database has been deleted or throws
# a OStorageException if the database doesn't exists.
#
# Request: (database-name:string)(server-storage-type:string - since 1.5-snapshot)
# Response: empty
#
# - server-storage-type can be one of the supported types:
# - plocal as a persistent database
# - memory, as a volatile database
#
class DbDropMessage(BaseMessage):
    def __init__(self, _orient_socket):
        super().__init__(_orient_socket)

        self._db_name = ''
        self._storage_type = ''

        if self.protocol > 16:  # 1.5-SNAPSHOT
            self._storage_type = STORAGE_TYPE_PLOCAL
        else:
            self._storage_type = STORAGE_TYPE_LOCAL

        # order matters
        self._append(( FIELD_BYTE, DB_DROP_OP ))

    def prepare(self, params=None):

        if isinstance(params, tuple) or isinstance(params, list):
            try:
                self._db_name = params[0]
                self.set_storage_type(params[1])
            except IndexError:
                # Use default for non existent indexes
                pass

        self._append(( FIELD_STRING, self._db_name ))  # db_name

        if self.protocol >= 16:  # > 16 1.5-snapshot
            # custom choice server_storage_type
            self._append(( FIELD_STRING, self._storage_type ))

        return super().prepare()

    def set_db_name(self, db_name):
        self._db_name = db_name
        return self

    def set_storage_type(self, storage_type):
        if storage_type in STORAGE_TYPES:
            # user choice storage if present
            self._storage_type = storage_type
        else:
            raise PyOrientBadMethodCallException(
                storage_type + ' is not a valid storage type', []
            )
        return self


#
# DB COUNT RECORDS
#
# Asks for the number of records in a database in
# the ODBClient Server instance.
#
# Request: empty
# Response: (count:long)
#
class DbCountRecordsMessage(BaseMessage):
    def __init__(self, _orient_socket):
        super().__init__(_orient_socket)

        self._user = ''
        self._pass = ''

        # order matters
        self._append(( FIELD_BYTE, DB_COUNT_RECORDS_OP ))

    def prepare(self, params=None):
        return super().prepare()

    async def fetch_response(self):
        self._append(FIELD_LONG)
        return list(await super().fetch_response())[0]


#
# DB RELOAD
#
# Reloads database information. Available since 1.0rc4.
# 
# Request: empty
# Response:(num-of-clusters:short)[(cluster-name:string)(cluster-id:short)]
#
class DbReloadMessage(BaseMessage):
    def __init__(self, _orient_socket):
        super().__init__(_orient_socket)

        # order matters
        self._append(( FIELD_BYTE, DB_RELOAD_OP ))

    def prepare(self, params=None):
        return super().prepare()

    async def fetch_response(self):

        self._append(FIELD_SHORT)  # cluster_num

        cluster_num = list(await super().fetch_response())[0]

        clusters = []

        # Parsing cluster map
        for x in range(0, cluster_num):
            if self.protocol < 24:
                cluster = OrientCluster(
                    await self._decode_field(FIELD_STRING),
                    await self._decode_field(FIELD_SHORT),
                    await self._decode_field(FIELD_STRING),
                    await self._decode_field(FIELD_SHORT)
                )
            else:
                cluster = OrientCluster(
                    await self._decode_field(FIELD_STRING),
                    await self._decode_field(FIELD_SHORT)
                )
            clusters.append(cluster)

        return clusters


#
# DB SIZE
#
# Asks for the size of a database in the ODBClient Server instance.
#
# Request: empty
# Response: (size:long)
#
class DbSizeMessage(BaseMessage):
    def __init__(self, _orient_socket):
        super().__init__(_orient_socket)

        # order matters
        self._append(( FIELD_BYTE, DB_SIZE_OP ))

    def prepare(self, params=None):
        return super().prepare()

    async def fetch_response(self):
        self._append(FIELD_LONG)
        return list(await super().fetch_response())[0]


#
# DB List
#
# Asks for the size of a database in the ODBClient Server instance.
#
# Request: empty
# Response: (size:long)
#
class DbListMessage(BaseMessage):
    def __init__(self, _orient_socket):
        super().__init__(_orient_socket)

        # order matters
        self._append(( FIELD_BYTE, DB_LIST_OP ))

    def prepare(self, params=None):
        return super().prepare()

    async def fetch_response(self):
        self._append(FIELD_BYTES)
        __record = list(await super().fetch_response())[0]
        # bug in orientdb csv serialization in snapshot 2.0,
        # strip trailing spaces
        _, data = self.get_serializer().decode(__record.rstrip())

        return OrientRecord(dict(__o_storage=data))
