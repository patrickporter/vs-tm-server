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
from mysql.connector import (connection)
import sqlite3
import time
import os

def create_sqlite_db(db_filename, sql_script_file):
    """Creates an sqlite db to store translation memory data"""
    script_file = open(sql_script_file, 'r')#, encoding='utf-8')
    script_data = script_file.read()
    script_file.close()

    commands = script_data.split(";\n\n")
        
        
    conn = sqlite3.connect(db_filename)
    c = conn.cursor()
    # Create
    for command in commands:
        c.execute(str.strip(command))
    c.close()
    conn.close()
    return {'result':'db created'}

def create_mysql_db_unless_exists(sql_script_file, user, password,
                                    host, db_name):
    """Creates a mysql db to store translation memory data or simply returns if the DB already exists"""
        
    conn = connection.MySQLConnection(user=user, password=password,
                                    host=host)
    #check to see if DB already exists, and if so..return
    cursor = conn.cursor()
    cursor.execute("show databases")
    databases=cursor.fetchall()
    #comes back as list of tuples
    for t in databases:
        if db_name in t:
            cursor.close()
            conn.close()
            return {'result':'db already exists; not created'}
        
    # Create db
    create="CREATE DATABASE " + db_name + " /*!40100 DEFAULT CHARACTER SET utf8 */;" #no need to escape here b/c not a user-passed value
    cursor.execute(create)
    conn.commit()
    conn.close()
        
    conn = connection.MySQLConnection(user=user, password=password,
                                    host=host, database=db_name)
    cursor = conn.cursor()

    script_file = open(sql_script_file, 'r')
    script_data = script_file.read()
    script_file.close()
    commands = script_data.split(";\n\n")
        
    # Create
    for command in commands:
        cursor.execute(str.strip(command))
    cursor.close()
    conn.close()
    return {'result':'db created'}




class TranslationMemory(dict):
    """A data object representing a translation memory document.
        subclass of dict to allow JSON serialization"""
    def __init__(self, tm_id, name, orig_filename, sourcelang, targetlang, 
                 created_datetime=time.time(), last_updated_datetime=time.time()):
        #add values as class properties, and as dict keys for serialization
        self.tm_id=self['tm_id']=tm_id
        self.name=self['name']=name
        self.orig_filename=self['orig_filename']=orig_filename
        self.sourcelang=self['sourcelang']=sourcelang
        self.targetlang=self['targetlang']=targetlang
        self.created_datetime=self['created_datetime']=created_datetime
        self.last_updated_datetime=self['last_updated_datetime']=last_updated_datetime
        

class TranslationUnit(dict):
    """A data object representing a translation unit belonging 
        subclass of dict to allow JSON serialization"""
    def __init__(self, tu_id, tm_id, sourcetext, targettext, 
                 created_by, created_date, 
                 changed_by, changed_date, last_used_date):
        #add values as class properties, and as dict keys for serialization
        self.tu_id=self['tu_id']=tu_id
        self.tm_id=self['tm_id']=tm_id
        self.sourcetext=self['sourcetext']=sourcetext
        self.targettext=self['targettext']=targettext
        self.created_by=self['created_by']=created_by
        self.created_date=self['created_date']=created_date
        self.changed_by=self['changed_by']=changed_by
        self.changed_date=self['changed_date']=changed_date
        self.last_used_date=self['last_used_date']=last_used_date
    
class TmData(object):
    """Used to map data and objects related to translation memory documents.
       Uses either sqlite or mysql depending on the values passed in the config"""

    def __init__(self, config):
        self.DB_USER=config.get('db_user')
        self.DB_PASSWORD=config.get('db_password')
        self.DB_HOST=config.get('db_host')
        self.DB_NAME=config['db_name']
        self.use_mysql = config['use_mysql']
        self.placeholder = '%s' if self.use_mysql else '?' #the different DB engines use different placeholders for escaping statements
        if config.get('sqlite_db_path'):
            self.sqlite_db_filepath = "{0}/{1}.db".format(config['sqlite_db_path'], self.DB_NAME)
        if config.get('sql_scripts_path'):
            self.sqlite_scripts_path = "{0}/{1}.sql".format(config['sql_scripts_path'], 'sqlite')
            self.mysql_scripts_path = "{0}/{1}.sql".format(config['sql_scripts_path'], 'mysql')
        
    
    def get_connection(self):
        if self.use_mysql:
            cnx = connection.MySQLConnection(user=self.DB_USER, password=self.DB_PASSWORD,
                                     host=self.DB_HOST,
                                     database=self.DB_NAME)
        else:
            cnx = sqlite3.connect(self.sqlite_db_filepath)
        return cnx

    def get_user(self, username):
        conn = self.get_connection()
        cursor=conn.cursor()
        select_tm = ("SELECT username, password FROM users WHERE "
                        "`username` = "+self.placeholder)
        cursor.execute(select_tm, (username,))
        result = cursor.fetchall()
        if not result:
            cursor.close()
            conn.close()
            return None
        else:
            cursor.close()
            conn.close()
            return result[0] #gets the result from the index
        
        
    
    def set_password(self, username, password):
        conn = self.get_connection()
        cursor=conn.cursor()
        update_tm = ("UPDATE `users` "
                     "SET `password`=" + self.placeholder +
                     " WHERE `username`=" + self.placeholder) #query statement to update
        cursor.execute(update_tm, (password, username))
        
        conn.commit()
        cursor.close()
        conn.close()
        

    def get_owner(self, tm_id):
        conn = self.get_connection()
        cursor=conn.cursor()
        select_tm = ("SELECT owner FROM tms WHERE "
                        "`tm_id` = "+self.placeholder)
        cursor.execute(select_tm, (tm_id,))
        result = cursor.fetchall()
        if not result:
            cursor.close()
            conn.close()
            return result #returns empty if no results in list
        else:
            cursor.close()
            conn.close()
            return result[0][0] #gets the result from the index
        
        

    def get_tm_last_updated_datetime(self, tm_id):
        conn = self.get_connection()
        cursor=conn.cursor()
        select_tm = ("SELECT last_updated_datetime FROM tms WHERE "
                        "`tm_id` = "+self.placeholder)
        cursor.execute(select_tm, (tm_id,))
        result = cursor.fetchall()
        if not result:
            cursor.close()
            conn.close()
            return result #returns empty if no results in list
        else:
            cursor.close()
            conn.close()
            return result[0][0] #gets the result from the index
        
        
    def get_tm_read_group_users(self, tm_id):
        conn = self.get_connection()
        cursor=conn.cursor()
        select_users = ("SELECT user FROM `group_memberships` "
                        "INNER JOIN `tms` "
                        "ON `group_memberships`.`group` = `tms`.`readonly_group` OR `group_memberships`.`group` = `tms`.`readwrite_group` "
                        "WHERE `tm_id` = "+self.placeholder )
        cursor.execute(select_users, (tm_id,))
        result = cursor.fetchall()
        x = [x[0] for x in result]
        return x #gets the result from the index

    def get_tm_read_write_group_users(self, tm_id):
        conn = self.get_connection()
        cursor=conn.cursor()
        select_users = ("SELECT user FROM `group_memberships` "
                        "INNER JOIN `tms` "
                        "ON `group_memberships`.`group` = `tms`.`readwrite_group` "
                        "WHERE `tm_id` = "+self.placeholder )
        cursor.execute(select_users, (tm_id,))
        result = cursor.fetchall()
        x = [x[0] for x in result]
        cursor.close()
        conn.close()
        return x #gets the result from the index
    
    def get_admin_users(self):
        conn = self.get_connection()
        cursor=conn.cursor()
        select_users = ("SELECT username FROM users WHERE "
                        "`is_admin` = "+self.placeholder )
        cursor.execute(select_users, (1,))
        result = cursor.fetchall()
        if not result:
            cursor.close()
            conn.close()
            return result #returns empty if no results in list
        else:
            cursor.close()
            conn.close()
            return result[0] #gets the result from the index

    def get_tms(self):
        #TODO: if using sqlite and this gets called (or anything else...) while a tm is loading in a bg task. there may be db lock errors
        conn = self.get_connection()
        cursor=conn.cursor()
        select_tm = ("SELECT * FROM tms")
        cursor.execute(select_tm)
        result=cursor.fetchall()
        tms={x[0]:TranslationMemory(x[0], x[1], x[2], x[3], x[4], x[8], x[9]) for x in result}
        cursor.close()
        conn.close()
        return tms

    def get_tus(self, tm_id, tus=None):
        conn = self.get_connection()
        cursor=conn.cursor()
        select_tus = ("SELECT * FROM tus "
                          "WHERE tm_id="+self.placeholder)
        cursor.execute(select_tus, (tm_id,))
        result = cursor.fetchall()
        if tus==None:
            tus={}
        for x in result:
            tu = TranslationUnit(x[0], x[1], x[2], x[3], x[4], x[5], x[6], x[7], x[8])
            if x[2] not in tus.keys():
                tus[x[2]]=[tu,]
            else:
                tus[x[2]].append(tu)
        cursor.close()
        conn.close()
        return tus
    
    def get_tus_from_sourcetext(self, tm_id, sourcetext):
        conn = self.get_connection()
        cursor=conn.cursor()
        select_tus = ("SELECT * FROM tus "
                          "WHERE tm_id="+self.placeholder +
                          " AND sourcetext="+self.placeholder)
        cursor.execute(select_tus, (tm_id,sourcetext))
        result = cursor.fetchall()
        if len(result)==0:
            cursor.close()
            conn.close()
            return None
        else:
            tus={} #{sourcetext:list of tu objects with that sourcetext}
            for x in result:
                tu = TranslationUnit(x[0], x[1], x[2], x[3], x[4], x[5], x[6], x[7], x[8])
                if x[2] not in tus.keys():
                    tus[x[2]]=[tu]
                else:
                    tus[x[2]].append(tu)
            cursor.close()
            conn.close()
            return tus
    
    def add_tm(self, tm_name, orig_filename, sourcelang, targetlang, owner, 
               created_datetime=time.strftime("%Y-%m-%d %H:%M:%S"), last_updated_datetime=time.strftime("%Y-%m-%d %H:%M:%S")):
        conn = self.get_connection()
        cursor = conn.cursor()
        values_string = "VALUES(" + (self.placeholder + ", " ) * 6 + self.placeholder + ")"
        add_tm = ("INSERT INTO tms "
                       "(name, orig_filename, sourcelang, targetlang, owner, " 
                       "created_datetime, last_updated_datetime) "
                       + values_string)
        add_tm_data = (tm_name, orig_filename, sourcelang, targetlang, 
                       owner, created_datetime, last_updated_datetime)
        cursor.execute(add_tm, add_tm_data)
        #we've used a trigger to mimic the behavior of mysql
        #..i.e. preventing the autoincrement from resetting when a tm is deleted
        #...this will keep all tms with a unique ID even if one is deleted and then another is added
        #...because otherwise the newly added one will be given the id of the last deleted one
        if self.use_mysql:
            tm_id = cursor.lastrowid
        else:
            #the lastrowid doesn't work in sqlite, because it returns the actual row number not the id field...which may differ based on the trigger described above
            cursor.execute("SELECT count(*) from add_tm_events") #the cursor will already reflect the row added by the trigger..so don't add 1 here
            x = cursor.fetchall()
            tm_id= x[0][0]
        conn.commit()
        cursor.close()
        conn.close()
        return tm_id

    def add_tu(self, tm_id, sourcetext, targettext, created_by, changed_by, created_date=time.strftime("%Y-%m-%d %H:%M:%S"),
               changed_date=time.strftime("%Y-%m-%d %H:%M:%S"), last_used_date=time.strftime("%Y-%m-%d %H:%M:%S"), connection=None):
        
        commit_and_close=False
        if connection==None:
            commit_and_close=True
            conn=self.get_connection()
        else:
            conn=connection
        
        cursor=conn.cursor()
        values_string = "VALUES(" + (self.placeholder + ", " ) * 7 + self.placeholder + ")"
        add_tu = ("INSERT INTO tus "
                       "(tm_id, sourcetext, targettext, created_by, created_date, "
                       "changed_by, changed_date, last_used_date) "
                       + values_string)
        add_tu_data=(tm_id, sourcetext, targettext, created_by, created_date,
                     changed_by, changed_date, last_used_date)
        cursor.execute(add_tu, add_tu_data)
        tu_id = cursor.lastrowid
        if commit_and_close:
            conn.commit()
            cursor.close()
            conn.close()
        return tu_id
    
    def update_tu_by_id(self, tu_id, sourcetext, targettext, created_by, changed_by, 
                        created_date=time.time(), changed_date=time.time(), last_used_date=time.time()):
        conn = self.get_connection()
        cursor = conn.cursor()
        update_tm = ("UPDATE tms "
                     "SET sourcetext=" + self.placeholder +
                     ",targettext=" + self.placeholder +
                     ",created_by=" + self.placeholder +
                     ",created_date=" + self.placeholder +
                     ",changed_by=" + self.placeholder +
                     ",changed_date=" + self.placeholder +
                     ",last_used_date=" + self.placeholder +
                     " WHERE tu_id=" + self.placeholder) #query statement to update
        cursor.execute(update_tm, (tu_id, sourcetext, targettext, created_by, 
                                   created_date, changed_by, changed_date, last_used_date, tu_id))
        conn.commit
        cursor.close()
        conn.close()

    def delete_tm_by_id(self, tm_id):
        conn = self.get_connection()
        cursor = conn.cursor()
        delete_tm = ("DELETE FROM tms WHERE "
                        "`tm_id` = "+self.placeholder)
        cursor.execute(delete_tm, (tm_id,))
        conn.commit()
        cursor.close()
        conn.close()
    
    def delete_tu_by_tu_id(self, tu_id):
        conn = self.get_connection()
        cursor = conn.cursor()
        delete_tus = ("DELETE FROM tus WHERE "
                        "`tu_id` = "+self.placeholder)
        cursor.execute(delete_tus, (tu_id,))
        conn.commit()
        cursor.close()
        conn.close()

    def delete_tus_by_tm_id(self, tm_id):
        conn = self.get_connection()
        cursor = conn.cursor()
        delete_tus = ("DELETE FROM tus WHERE "
                        "`tm_id` = "+self.placeholder)
        cursor.execute(delete_tus, (tm_id,))
        conn.commit()
        cursor.close()
        conn.close()
