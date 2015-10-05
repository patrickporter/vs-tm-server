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

#credit to: http://tools.cherrypy.org/wiki/AuthenticationAndAccessRestrictions
#adapted for specific purposes
# 
# Form based authentication for CherryPy. Requires the
# Session tool to be loaded.
#
import datamodel
import cherrypy
import hashlib

SESSION_KEY = '_cp_username'

def check_credentials(username, password):
    """Verifies credentials for username and password.
    Returns None on success or a string describing the error on failure"""
    dm = datamodel.TmData(cherrypy.request.app.config['/'])
    user = dm.get_user(username)
    if not user:
        return "Incorrect username or password"
    h = hashlib.md5()
    h.update(password.encode('utf-8'))
    pwd = h.hexdigest()
    if user[1] != pwd:
        return "Incorrect username or password"
    return None

    

def get_current_username():
    username = cherrypy.session.get(SESSION_KEY)
    if username:
        return cherrypy.session.get(SESSION_KEY)
    else:
        return None

def check_auth(*args, **kwargs):
    """A tool that looks in config for 'auth.require'. If found and it
    is not None, a login is required and the entry is evaluated as a list of
    conditions that the user must fulfill"""
    conditions = cherrypy.request.config.get('auth.require', None)
    if conditions is not None:
        username = cherrypy.session.get(SESSION_KEY)
        if username:
            cherrypy.request.login = username
            for condition in conditions:
                # A condition is just a callable that returns true or false
                result = condition() #PP. will return a reason message instead of boolean if check failed 
                if result != True:
                    raise cherrypy.HTTPError(403, result)
        else:
            raise cherrypy.HTTPRedirect("/auth/login?destination=" + cherrypy.url())
    
cherrypy.tools.auth = cherrypy.Tool('before_handler', check_auth)

def require(*conditions):
    """A decorator that appends conditions to the auth.require config
    variable."""
    def decorate(f):
        if not hasattr(f, '_cp_config'):
            f._cp_config = dict()
        if 'auth.require' not in f._cp_config:
            f._cp_config['auth.require'] = []
        f._cp_config['auth.require'].extend(conditions)
        return f
    return decorate


# Conditions are callables that return True
# if the user fulfills the conditions they define, False otherwise
#
# They can access the current username as cherrypy.request.login
#
# Define those at will however suits the application.

def can_read_tm():
    def check():
        dm = datamodel.TmData(cherrypy.request.app.config['/'])
        tm_id = cherrypy.request.params.get("tm_id")
        username = cherrypy.request.login
        return ((dm.get_owner(tm_id) == username) or
            (username in dm.get_tm_read_group_users(tm_id)) or
            (username in dm.get_admin_users()))
    return check

def can_write_to_tm():
    def check():
        dm = datamodel.TmData(cherrypy.request.app.config['/'])
        tm_id = cherrypy.request.params.get("tm_id")
        username = cherrypy.request.login
        return ((dm.get_owner(tm_id) == username) or
            (username in dm.get_tm_read_write_group_users(tm_id)) or
            (username in dm.get_admin_users()))
    return check

def can_delete_tm():
    def check():
        dm = datamodel.TmData(cherrypy.request.app.config['/'])
        tm_id = cherrypy.request.params.get("tm_id")
        username = cherrypy.request.login
        return ((dm.get_owner(tm_id) == username) or
            (username in dm.get_admin_users()))
    return check

def owns_tm():
    def check():
        result = datamodel.TmData(cherrypy.request.app.config['/']).get_owner(cherrypy.request.params.get("tm_id")) == cherrypy.request.login
        if result:
            return result
        else:
            return 'The current user does not own a TM with the id provided'
    return check

def is_admin():
    def check():
        result = datamodel.TmData(cherrypy.request.app.config['/']).get_admin_users()
        if cherrypy.request.login in result:
            return True
        else:
            return 'The current user does not have admin permissions'
    return check

# These might be handy

def any_of(*conditions):
    """Returns True if any of the conditions match"""
    def check():
        for c in conditions:
            if c():
                return True
        return False
    return check

# By default all conditions are required, but this might still be
# needed if you want to use it inside of an any_of(...) condition
def all_of(*conditions):
    """Returns True if all of the conditions match"""
    def check():
        for c in conditions:
            if not c():
                return False
        return True
    return check


# Controller to provide login and logout actions

class AuthController(object):
    
    def on_login(self, username):
        """Called on successful login"""
    
    def on_logout(self, username):
        """Called on logout"""
    
    #TODO: Don't use this form..or else escape to prevent xss
    def get_loginform(self, username, msg="Enter login information", destination="/"):
        return """<html><body>
            <form method="post" action="/auth/login">
            <input type="hidden" name="destination" value="%(destination)s" />
            %(msg)s<br />
            Username: <input type="text" name="username" value="%(username)s" /><br />
            Password: <input type="password" name="password" /><br />
            <input type="submit" value="Log in" /></form>
        </body></html>""" % locals()
    
    @cherrypy.expose
    def login(self, username=None, password=None, destination="/"):
        if username is None or password is None:
            return self.get_loginform("", destination=destination)
        
        error_msg = check_credentials(username, password)
        if error_msg:
            return self.get_loginform(username, error_msg, destination)
        else:
            cherrypy.session.regenerate() #thwart potential session fixation
            cherrypy.session[SESSION_KEY] = cherrypy.request.login = username
            self.on_login(username)
            raise cherrypy.HTTPRedirect(destination or "/")
    
    @cherrypy.expose
    def logout(self, from_page="/"):
        sess = cherrypy.session
        username = sess.get(SESSION_KEY, None)
        sess[SESSION_KEY] = None
        if username:
            cherrypy.request.login = None
            self.on_logout(username)
        raise cherrypy.HTTPRedirect(from_page or "/")

    #TODO: after testing, unexpose this method, delete it, or protect it
    #@cherrypy.expose
    def set_password(self, username, password):
        h = hashlib.md5()
        h.update(password.encode('utf-8'))
        pwd = h.hexdigest()
        dm = datamodel.TmData(cherrypy.request.app.config['/'])
        dm.set_password(username, pwd)
        
