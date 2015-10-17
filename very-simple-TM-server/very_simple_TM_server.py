#Copyright 2015 Patrick Porter
#
#Licensed under the Apache License, Version 2.0 (the "License");
#you may not use this file except in compliance with the License.
#You may obtain a copy of the License at
#
## http://www.apache.org/licenses/LICENSE-2.0
#
#Unless required by applicable law or agreed to in writing, software
#distributed under the License is distributed on an "AS IS" BASIS,
#WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#See the License for the specific language governing permissions and
#limitations under the License.

import logging
import cherrypy
import os
from TmProvider import TmProvider
from BackgroundTask import BackgroundTaskQueue
from auth import AuthController, require, owns_tm, is_admin, can_read_tm, can_write_to_tm, can_delete_tm, get_current_username


class VsTmServer(object):
    """Serves methods via HTTP for searching a set of string data for exact and fuzzy matches,
       as well as for loading, deleting, and otherwise maintaining the data"""
    
    auth=AuthController()
    
    def get_provider(): #tool to instantiate provider for session if null
        if not cherrypy.session.get('tm_provider'): #init new provider if new session
            cherrypy.session['tm_provider']=TmProvider(cherrypy.request.app.config['/'])
    cherrypy.tools.getprovider = cherrypy.Tool('before_handler', get_provider)

    def __init__(self):
        """In the app config, cores is the max number of processor cores that will be used for
           Levenshtein calculation during search.
           use_mysql defaults to False (in which case sqlite is used), 
           but if set to True will use MySql (DB must be already created/configured)"""
        self.bgtask = BackgroundTaskQueue(cherrypy.engine)
        self.bgtask.subscribe()
    
    def load_single_tm(self, tm_id):
        """Loads data for a given translation memory document from DB to memory for faster searching"""
        provider = cherrypy.session.get('tm_provider')
        result = provider.load_tm_to_memory(tm_id)
        return result

    @cherrypy.expose(['load_tm'])
    @cherrypy.tools.getprovider()
    @require(can_read_tm())
    def load_tus_to_memory(self, tm_id, **kwargs):
        """Loads data for a given translation memory document from DB to memory for faster searching.
        Returns an HTTP error if the tm_id in question does not exist."""
        provider = cherrypy.session.get('tm_provider')
        #first check if already loaded
        if provider.tms.get(int(tm_id)):
            return {'status' : 'tm already loaded...to update the in-memory TM, use a sync method'}
        result = self.load_single_tm(tm_id)
        if result['status']=='success':
            return result
        else:
            raise cherrypy.HTTPError(500, result['status']);
    
    @cherrypy.expose(['save_in_memory_tms'])
    @cherrypy.tools.getprovider()
    @require()
    def save_in_memory_tms_to_db(self, tm_name, sourcelang=None, targetlang=None):
        """Saves all the translation units currently in memory, from all TMs in memory,
            to one new translation memory in the DB."""
        provider = cherrypy.session.get('tm_provider')
        if len(provider.data)==0:
            return {'status' : 'no data currently in memory'}
        owner = get_current_username()
        return provider.create_tm_from_memory(tm_name, sourcelang, targetlang, owner, data)


    @cherrypy.expose
    @cherrypy.tools.getprovider()
    @require()
    def check_server_status(self, **kwargs):
        """Checks which, if any, TMs have been loaded to memory, which is necessary for searching."""
        status = {}
        provider = cherrypy.session.get('tm_provider')
        importing = self.bgtask.q.unfinished_tasks>0 #is an import task running in the background? TODO: sometimes unreliable for some reason..
        status['currently_importing_tmx'] = importing
        loadedtms = tuple(provider.tms.keys());
        status['loaded_tm_ids']  = loadedtms if provider.loaded and len(provider.data)>0 else None
        status['currently_loading_to_memory'] = provider.currently_loading
        return {'status': status}

    
    @cherrypy.expose(['list_tms'])
    @cherrypy.tools.getprovider()
    @require()
    def list_tms(self, **kwargs):
        """Lists the translation memory documents (TMX files) that have been imported into the database
           and are available for loading into memory and searching."""
        user = get_current_username()
        results = cherrypy.session.get('tm_provider').list_tms(user)
        return results

    
    @cherrypy.expose(['delete_tm'])
    @cherrypy.tools.getprovider()
    @require(can_delete_tm())
    def delete_tm_from_db(self, tm_id, **kwargs):
        """Permanently deletes all the data related to a previously-loaded
           translation memory document from the DB.  Careful..no going back unless
           the DB has been backed up. Clients should probably use a confirmation prompt"""
        return cherrypy.session.get('tm_provider').delete_tm_from_db(tm_id)
    
    @cherrypy.expose()
    @cherrypy.tools.getprovider()
    @require(can_delete_tm())
    def delete_tu(self, tm_id, source, target):
        """Permanently deletes a TU based on sourcetext/targettext pair from the specified TM."""
        return cherrypy.session.get('tm_provider').delete_tu(tm_id, source, target)
    
    @cherrypy.expose(['add_or_update_tu'])
    @cherrypy.tools.getprovider()
    @require(can_write_to_tm())
    def add_or_update_tu(self, tm_id, source, target, allow_multiple=False, overwrite_with_new=True):
        """Adds or updates a source text/target text pair to the specified translation memory."""
        #typeconvert for booleans passed as strings
        allow_multiple = True if str.lower(str(allow_multiple))=='true' else False
        overwrite_with_new = True if str.lower(str(overwrite_with_new))=='true' else False
        user = get_current_username()
        return cherrypy.session.get('tm_provider').add_or_update_tu(tm_id, source, target, user, allow_multiple, overwrite_with_new)

    @cherrypy.expose(['import_tmx'])
    @cherrypy.tools.getprovider()
    @require()
    def import_file(self, file, tm_name, **kwargs):
        """Starts an upload of a TMX file and then imports its info and translation units
           to the DB.  Runs DB import asynchronously in a background thread and returns immediately after 
           file upload is complete, indicating the status of 'currently loading'"""

        #TODO: validate for empty strings...here and elsewhere
        owner = get_current_username()
        self.bgtask.put(cherrypy.session.get('tm_provider').import_tmx_file, file, tm_name, owner)
        logging.info("importing TMX and loading to DB in subthread")
        status="parsing TMX and loading to DB"
        info = {'filename' : file.filename, 'content-type' : file.content_type.value, 'status' : status}
        return info
    
    @cherrypy.expose
    @cherrypy.tools.getprovider()
    @require(can_read_tm())
    def export_tmx_file(self, tm_id):
        """Retrieves the specified TM and exports it as a TMX file."""
        return {'not currently implemented'}
        #TODO: put in logic to export to TMX
    
    @cherrypy.expose
    @cherrypy.tools.getprovider()
    @require()
    def search(self, searchtext, threshold='.75', maxresults='0', casecost='.2', **kwargs):
        """The whole point...searches for exact and fuzzy matches;
           rates and ranks, returning in descending order of match %.
           threshold is the minimum match score to return.
           maxresults is the maximum number of results to return (0 means no max)
           casecost is the cost applied to replacements consisting of merely a case change
           in the Levenshtein distance calc.  A casecost of less than one warps results in favor
           of strings with merely case differences."""
        provider = cherrypy.session.get('tm_provider')
        if len(provider.data)==0:
            raise cherrypy.HTTPError(500, "No tm loaded");
        return provider.search(searchtext, threshold, maxresults, casecost) 
     
    @cherrypy.expose()
    @cherrypy.tools.getprovider()
    @require()
    def sync_memory_add_only(self):
        """Updates the in-memory data for the session from the DB, 
             adding new TUs only. No TUs will be deleted from the in-memory data,
             even if some of them have been deleted in the DB."""
        #simply reloading all the TMs in the current TM dictionary should work
        #first check if TM has been deleted before sync....return info if so
        provider = cherrypy.session.get('tm_provider')
        deleted_tms = []
        status = 'in-memory TMs successfully synced from DB'
        for tm_info in provider.tms.items():
            tm_id = tm_info[1].tm_id
            result  = self.load_single_tm(tm_id)
            if result['status']!='success':
                deleted_tms += str(tm_id);
        if len(deleted_tms)!=0:
            tmstring = ", ".join(str(e) for e in deleted_tms)
            message_string = "1 TM " if len(deleted_tms)==1 else "{0} TMs "
            message_string = message_string + "not loaded because they do not currently exist in the database, IDs: "
            status = message_string+tmstring
        return {'status' : status}

    @cherrypy.expose()
    @cherrypy.tools.getprovider()
    @require()
    def sync_memory_add_delete(self):
        """Updates the in-memory data for the session from the DB, 
            adding new TUs and removing deleted TUs,
            if the DB contains any changes."""
        #clear provider data
        #TODO: possibly offer a check_sync first to allow user to check before deleting in case they want to save as TM
        provider = cherrypy.session.get('tm_provider')
        provider.data = {}
        #now reload
        return self.sync_memory_add_only()


    #Don't expose this method without protection..it can be used to create DBs if they don't exist
    def create_db(self):
        config = cherrypy.request.app.config['/']
        if config.get('sql_scripts_path'):
            sqlite_scripts_path = "{0}/{1}.sql".format(config['sql_scripts_path'], 'sqlite')
            mysql_scripts_path = "{0}/{1}.sql".format(config['sql_scripts_path'], 'mysql_for_python')
        import datamodel
        if config.get('use_mysql')==True:
            return datamodel.create_mysql_db_unless_exists(mysql_scripts_path, user=config['db_user'], 
                                                    password=config['db_password'], host=config['db_host'], db_name=config['db_name'])
        else:
            sqlite_db_filepath = "{0}/{1}.db".format(config['sqlite_db_path'], config['db_name'])
            return datamodel.create_sqlite_db(db_filename=sqlite_db_filepath, sql_script_file=sqlite_scripts_path)
        
        
     


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    localDir = os.path.dirname(__file__)
    absDir = os.path.join(os.getcwd(), localDir)
    sqlite_db_path = "{0}/sqlitedb".format(absDir)
    sessions_path = "{0}/sessions".format(absDir)    
    sql_scripts_path = "{0}/sql_scripts".format(absDir)

    serverconfig = {
        'tools.sessions.on': True,
        'tools.sessions.storage_type' : "file",
        'tools.sessions.storage_path' : sessions_path,
        'tools.sessions.locking': 'early',
        'tools.auth.on': True,
        'server.socket_host': '0.0.0.0',
        'server.socket_port': 9090
        }
    appconfig = {
        '/' : {'db_user':'vstmserver',
                'db_password':'vstmserver1',
                'db_host':'127.0.0.1',
                'db_name':'vstmserver',
                'sqlite_db_path':sqlite_db_path,
                'numcores':4,
                'use_mysql':False,
                'sql_scripts_path' : sql_scripts_path,
                'tools.json_out.on': True},
        '/auth' : {'tools.json_out.on': False}
        
        }
    
    cherrypy.config.update(serverconfig)
    cherrypy.quickstart(VsTmServer(), '/', appconfig)
    
#TODO: allow config from file(s)
#TODO: a UI would be good to manage auth stuff..usernames, passwords, groups, etc. at least a basic one
#TODO: test running behind SSL