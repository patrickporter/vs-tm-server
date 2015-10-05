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

import xml.etree.ElementTree as ET
import logging
import json
import time
import Levenshtein
from functools import partial
from multiprocessing import Pool
import os
import glob
import subprocess
from operator import itemgetter
import datamodel

localDir = os.path.dirname(__file__)
absDir = os.path.join(os.getcwd(), localDir)




def get_lev_ratio(searchstring, minscore, casecost, comparestring):
        """Uses python-Levenshtein and performs a character-based Levenshtein distance calculation and returns a percentage score
           minscore should be a float between 0 and 1; casecost represents the cost of
           replacements that merely involve a change in case frome lower to upper or vice versa
           A casecost of less than 1 warps results in favor of strings differing only by case.
           The algorithm performs 2 lookups through the matrix..one with the actual strings,
           and one with both strings lowercased, calculating the case difference based on the
           difference between the two scores.
        """
        searchstring = str.strip(searchstring) #don't want to leave spaces and returns at ends
        comparestring = str.strip(comparestring) #don't want to leave spaces and returns at ends
        sumlen = len(searchstring) + len(comparestring)
        d1 = Levenshtein.distance(searchstring, comparestring)
        d2 = Levenshtein.distance(str.lower(searchstring), str.lower(comparestring))
        #d1 = editdistance.eval(searchstring, comparestring) 
        #d2 = editdistance.eval(str.lower(searchstring), str.lower(comparestring)) #editdistance library is slightly slower than python-Levenshtein
        diff = d1-d2
        dresult = d2 + (diff*casecost)
        ratio = (sumlen-dresult) / sumlen
        if ratio >= minscore:
            return tuple([comparestring, ratio])
        else:
            return

class TmProvider(object):
    """Provides methods for searching a set of string data for exact and fuzzy matches,
       as well as for loading, deleting, and otherwise maintaining the data"""
    
    def __init__(self, config):
        """cores is the max number of processor cores that will be used for
           Levenshtein calculation during search.
           use_mysql defaults to False (in which case sqlite is used), 
           but if set to True will use MySql (DB must be already created/configured)"""
        self.num_cores = config['numcores']
        self.use_mysql=config['use_mysql']
        self.data = {}
        self.tms = {}
        self.currently_loading = False
        self.loaded = False
        self.data_mgr = datamodel.TmData(config)
    
    def load_tm_to_memory(self, tm_id):
        """Loads data for a given translation memory document from DB to memory for faster searching"""
        tm_id=int(tm_id) #type conversion to int in case not done before passing
       
        #set status indicator variables
        self.loaded=False
        self.currently_loading=True
        
        #add the tm from the db to this instance's dict of loaded TMs
        tm = self.data_mgr.get_tms().get(tm_id)
        
        status = "success"

        if tm:
            self.tms[tm_id]=tm
            #load the TUs to this instance's dict of loaded TUs
            #by passing the current dict it adds the new items to the current dict
            #otherwise a new dict is created

            #test
            #size1 = len(self.data)
        
            self.data = self.data_mgr.get_tus(tm_id, self.data)
        
            #test
            #size2 = len(self.data)
        else:
            status = "no TM with ID of '{0}' exists".format(tm_id)
        
        #reset status indicators and return
        self.currently_loading=False
        self.loaded=True
        return {'status' : status}
        
    def list_tms(self, user):
        """Lists the translation memory documents (TMX files) that have been imported into the database
           and are available for loading into memory and searching"""
        all_tms = self.data_mgr.get_tms()
        results = []
        for tm in all_tms: #only return the TMs that the user can read and indicate whether read-only
            can_read = False
            can_write = False
            if ((self.data_mgr.get_owner(tm) == user) or
            (user in self.data_mgr.get_tm_read_write_group_users(tm)) or 
            (user in self.data_mgr.get_admin_users())):
                can_read = True
                can_write = True
            if user in self.data_mgr.get_tm_read_group_users(tm):
                can_read = True
            if can_read or can_write:
                result = all_tms[tm]
                result['can_read'] = can_read
                result['can_write'] = can_write
                results.append(result)
        return results
        
    def delete_tm_from_db(self, tm_id):
        """Permanently deletes all the data related to a previously-loaded
           translation memory document from the DB.  Careful..no going back unless
           the DB has been backed up."""
        deleted_sourcetexts={}
        for sourcetext in self.data.keys():
            delete_items=[]
            for item in self.data[sourcetext]:
                if str(item['tm_id'])==tm_id:
                    delete_items.append(item)
                    deleted_sourcetexts[sourcetext]=item['tu_id'] #to pop from the dict after iterating, if empty 
            #now after iterating we can remove the list items
            for item in delete_items:
                self.data[sourcetext].remove(item) #remove all items whose tm_id matches the one deleted from the DB
                    
        #now after iterating we can remove sourcetext keys that have no TU items left
        for item in deleted_sourcetexts.keys():
            if len(self.data[item])==0:
                self.data.pop(item)
        #now delete TM from in-memory TM list
        self.tms.pop(int(tm_id))
          
        #now delete from disk
        self.data_mgr.delete_tm_by_id(tm_id)
        self.data_mgr.delete_tus_by_tm_id(tm_id)
        return {'status' : 'success'}
    
    def delete_tu(self, tm_id, source, target):
        """Permanently deletes a TU based on sourcetext/targettext pair from the specified TM"""
        
        #delete from memory
        if source in self.data: #only do if actually in memory 
            sourcematches = self.data[source]
            for item in sourcematches:
                if str(item['tm_id']) == tm_id and item['targettext']==target:
                    self.data[source].remove(item) #remove all items whose tm_id matches the one deleted from the DB
            #now if the sourcetext key has no TU items left, remove the key
            if len(self.data[source])==0:
                self.data.pop(source)
        
        #now from DB
        existing_tus = self.data_mgr.get_tus_from_sourcetext(tm_id, source)
        tu_ids = []
        if existing_tus:
            for item in existing_tus[source]:
                if item['targettext']==target:
                    tu_ids.append(item['tu_id'])
            for tu_id in tu_ids:
                self.data_mgr.delete_tu_by_tu_id(tu_id)
        return {'status' : 'success'}
        
    def add_or_update_tu(self, tm_id, source, target, user, allow_multiple=False, overwrite_with_new=True):
        """Adds a source text/target text pair to the specified translation memory, 
        in the DB as well as the in-memory TM"""
        
        existing_tus = self.data_mgr.get_tus_from_sourcetext(tm_id, source)
        existing_targets = [x['targettext'] for x in existing_tus[source]] if existing_tus else []
        if target in existing_targets: #skip if there is a TU with the same source and target
            return {'status' : 'tu not added or updated because one with the same source text and target text already exists'}
        elif (not existing_tus) or (not allow_multiple):
            status = 'TU added'
            if existing_tus and overwrite_with_new: #if the source exists and overwrite = true, we are going to delete all existing TUs with that source and add this as new
                for i in range(len(existing_tus[source])):
                    self.data_mgr.delete_tu_by_tu_id(existing_tus[source][i]['tu_id'])
                status = 'TU(s) updated'
            #now add to DB and in-memory tm
            tu_id = self.data_mgr.add_tu(tm_id, source, target, user, user)
            self.data[source] = {'tm_id':tm_id, 'tu_id':tu_id, 'sourcetext':source, 'targettext':target,
                                      'created_by':user, 'changed_by':user, 'created_date':time.strftime("%Y-%m-%d %H:%M:%S"),
                                      'changed_date':time.strftime("%Y-%m-%d %H:%M:%S"), 'last_used_date':time.strftime("%Y-%m-%d %H:%M:%S")} #add new data to memory
            return {'status' : status}
        elif (allow_multiple and target not in existing_targets): #if tu with the same sourcetext doesn't exist...or if allow multiple and there isn't one already with same source and target...simply add it
            tu_id = self.data_mgr.add_tu(tm_id, source, target, user, user)
            self.data[source].append({'tm_id':tm_id, 'tu_id':tu_id, 'sourcetext':source, 'targettext':target,
                                      'created_by':user, 'changed_by':user, 'created_date':time.strftime("%Y-%m-%d %H:%M:%S"),
                                      'changed_date':time.strftime("%Y-%m-%d %H:%M:%S"), 'last_used_date':time.time()}) #add new data to memory
            return {'status' : 'tu added'}
        
        

    def create_tm_from_memory(self, tm_name, sourcelang, targetlang, owner, data):
        """Creates a new TM and adds all the TUs in memory to it in the DB, 
        the 'data' parameter should be a dict whose keys are source texts and values are dicts of TU data"""
        tm_id = self.data_mgr.add_tm(tm_name, "from_memory", sourcelang, targetlang, owner) 
        starttime=time.time()
        logging.info("started import from in-memory tm to DB, tm_id: {0}".format(tm_id))
        #open a data connection to keep open and send TUs one-by-one...to be committed and closed later when done
        cnx = self.data_mgr.get_connection()
        num_tus=0
        for key in data:
            value = data[key]
            for i in range(len(value)):
                tu = dict(value[i])
                self.data_mgr.add_tu(tm_id, tu['sourcetext'], tu['targettext'], user, user, 
                                     time.strftime("%Y-%m-%d %H:%M:%S"), time.strftime("%Y-%m-%d %H:%M:%S"), time.strftime("%Y-%m-%d %H:%M:%S"), cnx)
                num_tus+=1
        endtime = time.time() 
        logging.info("processed {0} TUs\ntime: {1}".format(num_tus, endtime - starttime))
        #commit and close
        cnx.commit()
        cnx.cursor().close()
        cnx.close()
        return {'status' : 'success. processed {0} TUs'.format(num_tus)}

    def normalize_time_tmx_to_iso(self, timestring):
        """deals with differences in handling of iso8601, time...
           i.e., the DBs seem to choke with the T and the Z"""
        #string e.g.: 20140204T184725Z has to become 2014-02-04 18:47:25 
        y = timestring[0:4]
        mon = timestring[4:6]
        d = timestring[6:8]
        h = timestring[9:11]
        min = timestring[11:13]
        s = timestring[13:15]
        result = "{0}-{1}-{2} {3}:{4}:{5}".format(y,mon,d,h,min,s)
        return result
        
    def load_tmx_to_db(self, tmxfile, tm_name, owner):
        """Takes a previously uploaded TMX file and parses it, adding the translation units 
           and info about the TM into the DB"""

        starttime=time.time()
        logging.info("started TMX import...")
        #TODO: check if TM already exists and error handling?????
        #TODO: check for empty string name and return...i.e. make required

        header = "";
        srclang=""
        num_tus = 0
        srclang = None
        tgtlang = None
        parser = ET.iterparse(tmxfile)
        for event, element in parser:
            if element.tag == 'header':
                srclang = element.attrib["srclang"]
            if element.tag == 'tu':
                tuvs = element.findall("tuv")
                #determine which is source and which is target...and put into tm insert
                lang0 = tuvs[0].attrib['{http://www.w3.org/XML/1998/namespace}lang']
                lang1 = tuvs[1].attrib['{http://www.w3.org/XML/1998/namespace}lang']
                if lang0 == srclang:
                    tgtlang = lang1
                else:
                    tgtlang = lang1
                break
        
        #insert a new TM into the DB and return the id of the newly inserted tm
        tm_id=self.data_mgr.add_tm(tm_name, tmxfile, srclang, tgtlang, owner)    
        
        #now insert TUs for the new TM
        #open a data connection to keep open and send TUs one-by-one...to be committed and closed later when done
        cnx = self.data_mgr.get_connection()
        
        #parse the rest of the doc
        parser = ET.iterparse(tmxfile)
        for event, element in parser:
            if element.tag == 'tu':
                tuvs = element.findall("tuv")
                lang0 = tuvs[0].attrib['{http://www.w3.org/XML/1998/namespace}lang']
                if lang0 == srclang:
                    segtext = tuvs[0].find("seg").text
                    trgtext = tuvs[1].find("seg").text
                else:
                    segtext = tuvs[1].find("seg").text
                    trgtext = tuvs[0].find("seg").text
                created_by = element.attrib['creationid'] if 'creationid' in element.attrib else owner
                #strip out the 'T' in tmx datetime stamp b/c mysql doesn't understand it
                created_date = self.normalize_time_tmx_to_iso(element.attrib['creationdate']) if 'creationdate' in element.attrib else time.strftime("%Y-%m-%d %H:%M:%S")
                changed_by = element.attrib['changeid'] if 'changeid' in element.attrib else owner
                changed_date = self.normalize_time_tmx_to_iso(element.attrib['changedate']) if 'changedate' in element.attrib else time.strftime("%Y-%m-%d %H:%M:%S")
                last_used_date = self.normalize_time_tmx_to_iso(element.attrib['lastusagedate']) if 'lastusagedate' in element.attrib else time.strftime("%Y-%m-%d %H:%M:%S")
                #insert the tu...By passing the current connection, the connection will stay open without the single insert being committed
                self.data_mgr.add_tu(tm_id=tm_id, sourcetext=str.strip(segtext), 
                           targettext=str.strip(trgtext),
                           created_by=created_by, created_date=created_date, 
                           changed_by=changed_by, changed_date=changed_date, last_used_date=last_used_date, connection=cnx)
                element.clear()
                num_tus+=1    
        endtime = time.time() 
        logging.info("processed {0} TUs\ntime: {1}".format(num_tus, endtime - starttime))
        #commit and close
        cnx.commit()
        cnx.cursor().close()
        cnx.close()
        
        
    
    def import_tmx_file(self, file, tm_name, owner):
        """Starts an upload of a TMX file and then calls the import to DB method"""
        #TODO: check for empty strings on args
        #TODO: deal with file locking issues here in case 2 people are trying to load the same filename...also prevent overwriting in this case
        starttime=time.time()
        logging.info("started TMX import...")
        size = 0
        localfilename="{0}/upload/{1}".format(absDir, file.filename)
        localfile = open(localfilename, 'wb')
        while True:
            data = file.file.read(8192)
            localfile.write(data)
            if not data:
                break
            size += len(data)
        
        localfile.close()
        endtime = time.time() - starttime
        logging.info("finished TMX upload...time elapsed: {0}".format(endtime))
        logging.info("started TMX parsing / DB insertion")
        self.load_tmx_to_db(localfilename, tm_name, owner)
        

    def export_tmx_file(self, tm_id):
        """Retrieves the specified TM and exports it as a TMX file"""
        logging.info("started TMX export...")
        #TODO: put in logic to export to TMX
            
    def search(self, searchtext, threshold=.75, maxresults=0, casecost=.2):
        """The whole point...searches for exact and fuzzy matches;
           rates and ranks, returning in descending order of match %.
           threshold is the minimum match score to return.
           maxresults is the maximum number of results to return (0 means no max)
           casecost is the cost applied to replacements consisting of merely a case change
           in the Levenshtein distance calc.  A casecost of less than one warps results in favor
           of strings with merely case differences."""

        #type convert in case necessary
        threshold=float(threshold)
        casecost=float(casecost)
        maxresults=int(maxresults)
         
        logging.info("searching with Levenshtein...")
        lev_start_time = time.time()
        sourcelist = list(self.data.keys())
        searchresults = {'data':{'matches':[]}}
        pre_endtime = time.time()
        logging.info("Pre-processing took {0} seconds\n".format(pre_endtime - lev_start_time))
        if self.num_cores==0:
            p = Pool() #uses max available
        else:
            p = Pool(self.num_cores)
        results = set(p.map(partial(get_lev_ratio, searchtext, threshold, casecost), sourcelist)) #this has to be a list of hashable objects i think??
        p.close()
        endtime = time.time()
        logging.info("Levenshtein lookup took {0} seconds\n".format(endtime - pre_endtime))

        results.remove(None) #there will be one 'None'' element...see get_lev_ratio ..r/t multiprocessing and speed...need to return small set...is it possible to do an intermediate processing step in the map???
        results = sorted(results, key=itemgetter(1), reverse=True) #sort results descending by score
        count=0
        for result in results:
            if maxresults !=0:
                if count >= maxresults: break
                count+=1
            sourcetext = result[0]
            tus = self.data[sourcetext] #for now this is only going to return one...but we should prob change it to allow miltiple source entries
            for tu in tus: #if there are multiple tus for a given shourcetext the tu select will return more than one record
                #TODO: make option to retrieve editops?
                #editops = Levenshtein.editops(str.strip(searchtext),str.strip(sourcetext))
                score = result[1]
                match = {'sourcetext':sourcetext, 'targettext':tu['targettext'], 'matchscore':score, 
                         'created_by':tu['created_by'], 'created_date':str(tu['created_date']), 
                         'changed_by':tu['changed_by'], 'changed_date':str(tu['changed_date']),
                         'last_used_date':str(tu['last_used_date'])}
                searchresults['data']['matches'].append(match)
        logging.info("post-processing took {0} seconds\n".format(time.time() - endtime))
        return searchresults
        
        
#TODO: can we make the lev method faster...i.e. is it something to do with processing the intermediate data???