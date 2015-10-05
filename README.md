# Very Simple TM Server

A moderately scalable translation memory server written in Python.

It includes a CherryPy wrapper serving methods to interact with the translation memory provider. The TM provider performs fuzzy matching via character-based Levenshtein distance, modified to allow custom scoring for replacements that represent merely changes in case (i.e. uppercase to lowercase and vice versa).  By default, data is stored using an Sqlite db, but MySql is optionally supported.  Data is loaded into session-based memory for faster searching. Sessions are managed via cookie header and authentication with usernames and passwords. Translation memories are assigned an 'owner' who can read, write, and delete the TM. The TMs can also be assigned a 'read group' and 'readwrite group' for other users to interact with them. Admin users can read, write, and delete all TMs. 

<strong>NOTE</strong>: currently very experimental... In its current form it should only be used on a private LAN as it sends/receives all data unencrypted, including usernames and passwords. To run it on a public server, see <a href="http://cherrypy.readthedocs.org/en/latest/deploy.html#ssl-support">http://cherrypy.readthedocs.org/en/latest/deploy.html#ssl-support</a> regarding running CherryPy behind SSL. Some security risks have been addressed, for example protection against sql injection and against session fixation, but should probably be reviewed. Among other potential unaddressed security issues, it can currently serve a simple password form for login, but this form is not protected at all against potential XSS attacks.


<strong>Requirements</strong>:<br/>
Python 3.4<br/>
CherryPy<br/>
python_Levenshtein<br/>
MySql Server (optional)<br/>

<strong>Usage / API methods (GET or POST)</strong>:

<strong>name</strong>:<br/>
&nbsp;&nbsp;&nbsp;&nbsp;``` check_server_status ```<br/>
<strong>description</strong>:<br/>
&nbsp;&nbsp;&nbsp;&nbsp;Checks which, if any, TMs have been loaded to memory, which is necessary for searching.<br>
<strong>params</strong>:<br/>
&nbsp;&nbsp;&nbsp;&nbsp;[none]<br/>
<strong>returns</strong>:<br/>
&nbsp;&nbsp;&nbsp;&nbsp;JSON dict: ``` {'status': ...} ```<br/><br/>

<strong>name</strong>:<br/>
&nbsp;&nbsp;&nbsp;&nbsp;``` list_tms ```<br/>
<strong>description</strong>:<br/>
&nbsp;&nbsp;&nbsp;&nbsp;Lists the translation memory documents (TMX files) that have been imported into the database and are available for loading into memory and searching.<br/>
<strong>params</strong>:<br/>
&nbsp;&nbsp;&nbsp;&nbsp;[none]<br/>
<strong>returns</strong>:<br/>
&nbsp;&nbsp;&nbsp;&nbsp;JSON list of JSON dicts: ``` [{'created_datetime': ..., 'can_read': ..., 'tm_id': ..., 'name': ..., 'can_write': ..., 'sourcelang': ..., 'targetlang': ..., 'orig_filename': ..., 'last_updated_datetime': ...} ... ] ```<br/><br/>

<strong>name</strong>:<br/>
&nbsp;&nbsp;&nbsp;&nbsp;``` load_tm ```<br/>
<strong>description</strong>:<br/>
&nbsp;&nbsp;&nbsp;&nbsp;Loads data for a given translation memory document from DB to memory for faster searching. Returns an HTTP error if the tm_id in question does not exist.<br/>
<strong>params</strong>:<br/>
&nbsp;&nbsp;&nbsp;&nbsp;``` tm_id ```<br/>
<strong>returns</strong>:<br/>
&nbsp;&nbsp;&nbsp;&nbsp;JSON dict: ``` {'status': ...} ```<br/><br/>

<strong>name</strong>:<br/>
&nbsp;&nbsp;&nbsp;&nbsp;``` search ```<br/>
<strong>description</strong>:<br/>
&nbsp;&nbsp;&nbsp;&nbsp;Searches for exact and fuzzy matches, rates and ranks, returning in descending order of match %. ``` threshold ``` is the minimum match score to return. ``` maxresults ``` is the maximum number of results to return (0 means no max). ``` casecost ``` is the cost applied to replacements consisting of merely a case change in the Levenshtein distance calc:  A casecost of less than one warps results in favor of strings with merely case differences.<br/>
<strong>params</strong>:<br/>
&nbsp;&nbsp;&nbsp;&nbsp;``` searchtext ```<br/>
&nbsp;&nbsp;&nbsp;&nbsp;``` threshold ``` (default ``` 0.75 ```)<br/>
&nbsp;&nbsp;&nbsp;&nbsp;``` maxresults ``` (default ``` 0 ```, i.e. unlimited)<br/>
&nbsp;&nbsp;&nbsp;&nbsp;``` casecost ``` (default ``` 0.2 ```)<br/>
<strong>returns</strong>:<br/>
JSON dict: ``` {'data': {'matches': [{'sourcetext': ..., 'targettext': ..., 'matchscore': ..., 'created_by': ..., 'created_date': ..., 'changed_by': ..., 'changed_date': ..., 'last_used_date': ...}, ...]}} ```<br/><br/>

<strong>name</strong>:<br/>
&nbsp;&nbsp;&nbsp;&nbsp;``` sync_memory_add_only ```<br/>
<strong>description</strong>:<br/>
&nbsp;&nbsp;&nbsp;&nbsp;Updates the in-memory data for the session from the DB, adding new TUs only. No TUs will be deleted from the in-memory data, even if some of them have been deleted in the DB.<br/>
<strong>params</strong>:<br/>
&nbsp;&nbsp;&nbsp;&nbsp;[none]<br/>
<strong>returns</strong>:<br/>
&nbsp;&nbsp;&nbsp;&nbsp;JSON dict: ``` {'status': ...} ```<br/><br/>

<strong>name</strong>:<br/>
&nbsp;&nbsp;&nbsp;&nbsp;``` sync_memory_add_delete ```<br/>
<strong>description</strong>:<br/>
&nbsp;&nbsp;&nbsp;&nbsp;Updates the in-memory data for the session from the DB, adding new TUs and removing deleted TUs, if the DB contains any changes.<br/>
<strong>params</strong>:<br/>
&nbsp;&nbsp;&nbsp;&nbsp;[none]<br/>
<strong>returns</strong>:<br/>
&nbsp;&nbsp;&nbsp;&nbsp;JSON dict: ``` {'status': ...} ```<br/><br/>

<strong>name</strong>:<br/>
&nbsp;&nbsp;&nbsp;&nbsp;``` save_in_memory_tms ```<br/>
<strong>description</strong>:<br/>
&nbsp;&nbsp;&nbsp;&nbsp;Saves all the translation units currently in memory, from all TMs in memory, to one new translation memory in the DB.<br/>
<strong>params</strong>:<br/>
&nbsp;&nbsp;&nbsp;&nbsp;``` tm_name ```<br/>
&nbsp;&nbsp;&nbsp;&nbsp;``` sourcelang ``` (default ``` None ```)<br/>
&nbsp;&nbsp;&nbsp;&nbsp;``` targetlang ``` (default ``` None ```)<br/>
<strong>returns</strong>:<br/>
&nbsp;&nbsp;&nbsp;&nbsp;JSON dict: ``` {'status': ...} ```<br/><br/>

<strong>name</strong>:<br/>
&nbsp;&nbsp;&nbsp;&nbsp;``` delete_tm ```<br/>
<strong>description</strong>:<br/>
&nbsp;&nbsp;&nbsp;&nbsp;Permanently deletes all the data related to a previously-loaded translation memory document from the DB.<br/>
<strong>params</strong>:<br/>
&nbsp;&nbsp;&nbsp;&nbsp;``` tm_id ```<br/>
<strong>returns</strong>:<br/>
&nbsp;&nbsp;&nbsp;&nbsp;JSON dict: ``` {'status': ...} ```<br/><br/>

<strong>name</strong>:<br/>
&nbsp;&nbsp;&nbsp;&nbsp;``` delete_tu ```<br/>
<strong>description</strong>:<br/>
&nbsp;&nbsp;&nbsp;&nbsp;Permanently deletes a TU based on sourcetext/targettext pair from the specified TM.<br/>
<strong>params</strong>:<br/>
&nbsp;&nbsp;&nbsp;&nbsp;``` tm_id ```<br/>
&nbsp;&nbsp;&nbsp;&nbsp;``` source ```<br/>
&nbsp;&nbsp;&nbsp;&nbsp;``` target ```<br/>
<strong>returns</strong>:<br/>
&nbsp;&nbsp;&nbsp;&nbsp;JSON dict: ``` {'status': ...} ```<br/><br/>

<strong>name</strong>:<br/>
&nbsp;&nbsp;&nbsp;&nbsp;``` add_or_update_tu ```<br/>
<strong>description</strong>:<br/>
&nbsp;&nbsp;&nbsp;&nbsp;Adds or updates a source text/target text pair to the specified translation memory.<br/>
<strong>params</strong>:<br/>
&nbsp;&nbsp;&nbsp;&nbsp;``` tm_id ```<br/>
&nbsp;&nbsp;&nbsp;&nbsp;``` source ```<br/>
&nbsp;&nbsp;&nbsp;&nbsp;``` target ```<br/>
&nbsp;&nbsp;&nbsp;&nbsp;``` allow_multiple ``` (default ``` False ```)<br/>
&nbsp;&nbsp;&nbsp;&nbsp;``` overwrite_with_new ``` (default ``` True ```)<br/>
<strong>returns</strong>:<br/>
&nbsp;&nbsp;&nbsp;&nbsp;JSON dict: ``` {'status': ...} ```<br/><br/>

<strong>name</strong>:<br/>
&nbsp;&nbsp;&nbsp;&nbsp;``` import_tmx ```<br/>
<strong>description</strong>:<br/>
&nbsp;&nbsp;&nbsp;&nbsp;Starts an upload of a TMX file and then imports its info and translation units to the DB.  Runs DB import asynchronously in a background thread and returns immediately after file upload is complete, indicating the status of 'currently loading'<br/>
<strong>params</strong>:<br/>
&nbsp;&nbsp;&nbsp;&nbsp;``` file ```<br/>
&nbsp;&nbsp;&nbsp;&nbsp;``` tm_name ```<br/>
<strong>returns</strong>:<br/>
&nbsp;&nbsp;&nbsp;&nbsp;JSON dict: ``` {'filename' : ..., 'content-type' : ..., 'status' : ...} ```<br/><br/>

<strong>name</strong>:<br/>
&nbsp;&nbsp;&nbsp;&nbsp;``` export_tmx ```<br/>
<strong>description</strong>:<br/>
&nbsp;&nbsp;&nbsp;&nbsp;Retrieves the specified TM and exports it as a TMX file.<br/>
<strong>params</strong>:<br/>
&nbsp;&nbsp;&nbsp;&nbsp;``` tm_id ```<br/>
<strong>returns</strong>:<br/>
&nbsp;&nbsp;&nbsp;&nbsp;TMX file object<br/><br/>