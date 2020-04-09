import sys
import json
import os
import tarfile
# import time
# import datetime

try:
    from database import Database
except: #jython fix #improve
    sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
    from database import Database

from utils import Utils

class Module:
    #module super in future
    def __init__(self, internal_path, external_path, report_path):
        print("[Tiktok] Module loaded")
        # self.report_name = report_name
        self.internal_path = internal_path
        self.external_path = external_path
        
        # self.report_path = os.path.join(report_path, "report", self.report_name)
        self.report_path = report_path
        Utils.check_and_generate_folder(self.report_path)

        self.internal_cache_path = os.path.join(self.report_path, "Contents", "internal")
        self.external_cache_path = os.path.join(self.report_path, "Contents", "external")
        Utils.check_and_generate_folder(self.internal_cache_path)
        Utils.check_and_generate_folder(self.external_cache_path)

        if self.internal_path:
            Utils.extract_tar(self.internal_path, self.internal_cache_path)

        if self.external_path:
            Utils.extract_tar(self.external_path, self.external_cache_path)

        self.databases = self.set_databases()
        self.shared_preferences = self.set_shared_preferences() #we can comment this
        #print(self.databases)
        #print(self.shared_preferences)
        
        self.used_databases = []

        print("[Tiktok] Module started")

    def set_databases(self):
        dbs = []
        dbs.extend(Utils.list_files(self.internal_cache_path, [".db"]))
        dbs.extend(Utils.list_files(self.external_cache_path, [".db"]))
        return dbs

    def set_shared_preferences(self):
        files = []
        for xmlfile in Utils.list_files(self.internal_cache_path, [".xml"]):
            if '/shared_prefs/' in xmlfile or '\\shared_prefs\\' in xmlfile:
                files.append(xmlfile)
        
        return files
    
    def generate_report(self):
        user_id = self.get_user_id()
        report_header = {
            "report_date": Utils.get_current_time(),
            "user": user_id
        }
        report = {}
        report["header"] = report_header
        report["profile"] = self.get_user_profile()
        report["messages"] = self.get_user_messages()
        report["users"] = self.get_user_profiles()
        report["searches"] = self.get_user_searches()
        report["videos"] = self.get_videos()
        report["freespace"] = self.get_undark_db() 
        print("[Tiktok] Generate Report")

        Utils.save_report(os.path.join(self.report_path, "Report.json"), report)
        return report

    #TIKTOK
    def get_user_messages(self):
        print("[Tiktok] Getting User Messages...")
        messages_list = []

        db1 = os.path.join(self.internal_cache_path, "databases", "db_im_xx")
        db2 = None

        for db in self.databases:
            if db.endswith("_im.db"):
                db2 = db
                break
        
        if not db2:
            print("[Tiktok] User Messages database not found!")
            return ""

        db2 = os.path.join(self.internal_path, db2)
        attach = "ATTACH '{}' AS 'db2'".format(db2)

        database = Database(db1)
        results = database.execute_query("select UID, UNIQUE_ID, NICK_NAME, datetime(created_time/1000, 'unixepoch', 'localtime') as created_time, content as message, case when read_status = 0 then 'Not read' when read_status = 1 then 'Read' else read_status end read_not_read, local_info from SIMPLE_USER, msg where UID = sender order by created_time;", attach = attach)
        for entry in results:
            message={}
            message["uid"] = entry[0]
            message["uniqueid"] = entry[1]
            message["nickname"] = entry[2]
            message["createdtime"] = entry[3]
            message["message"] = entry[4]
            message["readstatus"] = entry[5]
            message["localinfo"] = entry[6]
            messages_list.append(message)
        
        print("[Tiktok] {} messages found".format(len(messages_list)))

        if not db1 in self.used_databases:
            self.used_databases.append(db1)
        
        if not db2 in self.used_databases:
            self.used_databases.append(db2)

        return messages_list

    def get_user_profile(self):
        print("[Tiktok] Get User Profile...")
        xml_file = os.path.join(self.internal_cache_path, "shared_prefs", "aweme_user.xml")
        user_profile ={}
        values = Utils.xml_attribute_finder(xml_file)
        for key, value in values.items():
            if key.endswith("_aweme_user_info"):
                #try:
                dump=json.loads(value)
                atributes =["account_region", "follower_count","following_count", "gender", "google_account", "is_blocked", "is_minor", "nickname", "register_time", "sec_uid", "short_id", "uid", "unique_id"]

                for index in atributes:
                    user_profile[index] = dump[index]
                break
                #except ValueError:
                #    print("[Tiktok] JSON User Error")

        return user_profile

    def get_user_searches(self):
        print("[Tiktok] Getting User Search History...")
        xml_file = os.path.join(self.internal_cache_path, "shared_prefs", "search.xml")
        dump = json.loads(Utils.xml_attribute_finder(xml_file, "recent_history")["recent_history"])
        searches = []
        for i in dump: searches.append(i["keyword"])

        print("[Tiktok] {} search entrys found".format(len(searches)))
        return searches

    def get_user_profiles(self):
        print("[Tiktok] Getting User Profiles...")
        profiles = []

        db = os.path.join(self.internal_cache_path, "databases", "db_im_xx")

        database = Database(db)
        results = database.execute_query("select UID, UNIQUE_ID, NICK_NAME, AVATAR_THUMB, case when follow_status = 1 then 'Following' when follow_status = 2 then 'Followed and Following ' else follow_status end follow_following from SIMPLE_USER")
        for entry in results:
            message={}
            message["uid"] = entry[0]
            message["uniqueid"] = entry[1]
            message["nickname"] = entry[2]
            dump_avatar = json.loads(entry[3])
            message["avatar"] = dump_avatar["url_list"][0]
            message["follow_status"] = entry[4]
            profiles.append(message)
        
        print("[Tiktok] {} profiles found".format(len(profiles)))

        if not db in self.used_databases:
            self.used_databases.append(db)

        return profiles

    def get_user_id(self):
        print("[Tiktok] Getting User ID")
        xml_file = os.path.join(self.internal_cache_path, "shared_prefs", "iuserstate.xml")
        return Utils.xml_attribute_finder(xml_file, "userid")["userid"]

    def get_videos(self):
        print("[Tiktok] Getting Videos...")
        videos = []
        db = os.path.join(self.internal_cache_path, "databases", "video.db")

        database = Database(db)
        results = database.execute_query("select key, extra from video_http_header_t")

        for entry in results:
            video = {}
            video["key"] = entry[0]
            dump = json.loads(entry[1])
            
            for line in dump["responseHeaders"].splitlines():
                if 'Last-Modified:' in line:
                    video["last_modified"] = line.split(": ")[1]
                    break
            videos.append(video)
            #self.access_path_file(self.internal_path, "./cache/cache/{}".format(entry[0]))
        
        if not db in self.used_databases:
            self.used_databases.append(db)

        print("[Tiktok] {} videos found".format(len(videos)))
        return videos
    
    def get_undark_db(self):
        print("[Tiktok] Getting undark output...")
        output = {}

        for name in self.used_databases:
            listing = []
            undark_output = Utils.run_undark(name).decode()
            for line in undark_output.splitlines():
                listing.append(line)
            
            if listing:
                relative_name = os.path.normpath(name.replace(self.report_path, "")) #clean complete path
                output[relative_name] = listing

        return output
        
    ## PSY

    @staticmethod
    def get_attributes(self):
        return {
            'TIKTOK_MSG_UID': {
                "type": "string",
                "name": "Uid"
            },
            'TIKTOK_MSG_UNIQUE_ID': {
                "type": "string",
                "name": "Unique ID"
            }, 
            'TIKTOK_MSG_NICKNAME': {
                "type": "string",
                "name": "Nickname"
            },
            'TIKTOK_MSG_CREATED_TIME': {
                "type": "string",
                "name": "Created Time"
            }, 
            'TIKTOK_MSG_MESSAGE': {
                "type": "string",
                "name": "Message"
            },
            'TIKTOK_MSG_READ_STATUS': {
                "type": "string",
                "name": "Read Status"
            }, 
            'TIKTOK_MSG_LOCAL_INFO': {
                "type": "string",
                "name": "Local Info"
            },
            'TIKTOK_PROFILE_AVATAR': {
                "type": "string",
                "name": "Avatar"
            }, 
            'TIKTOK_PROFILE_REGION': {
                "type": "string",
                "name": "Region"
            },
            'TIKTOK_PROFILE_FOLLOWER': {
                "type": "long",
                "name": "Followers"
            }, 
            'TIKTOK_PROFILE_FOLLOWING': {
                "type": "long",
                "name": "Following"
            },
            'TIKTOK_PROFILE_GENDER': {
                "type": "long",
                "name": "Gender"
            }, 
            'TIKTOK_PROFILE_GOOGLE': {
                "type": "string",
                "name": "Google Account"
            },
            'TIKTOK_PROFILE_NICKNAME': {
                "type": "string",
                "name": "Nickname"
            }, 
            'TIKTOK_PROFILE_REGISTER_TIME': {
                "type": "long",
                "name": "Register Time"
            }, 
            'TIKTOK_PROFILE_SEC_UID': {
                "type": "string",
                "name": "Sec. UID"
            }, 
            'TIKTOK_PROFILE_SHORT_ID': {
                "type": "string",
                "name": "Short ID"
            }, 
            'TIKTOK_PROFILE_UID': {
                "type": "string",
                "name": "UID"
            }, 
            'TIKTOK_PROFILE_UNIQUE_ID': {
                "type": "string",
                "name": "Unique ID"
            }, 
            'TIKTOK_PROFILE_FOLLOW_STATUS': {
                "type": "long",
                "name": "Follow Status"
            }, 
            'TIKTOK_SEARCH': {
                "type": "string",
                "name": "Search"
            }, 
            'TIKTOK_UNDARK_KEY': {
                "type": "string",
                "name": "Database"
            }, 
            'TIKTOK_UNDARK_KEY': {
                "type": "string",
                "name": "Output"
            }, 
            'TIKTOK_UNDARK_OUTPUT': {
                "type": "string",
                "name": "Output"
            }
        }
        # self.att_prf_is_blocked = self.create_attribute_type('TIKTOK_PROFILE_IS_BLOCKED', BlackboardAttribute.TSK_BLACKBOARD_ATTRIBUTE_VALUE_TYPE.BYTE, "Is Blocked", skCase)
        # self.att_prf_is_minor = self.create_attribute_type('TIKTOK_PROFILE_IS_MINOR', BlackboardAttribute.TSK_BLACKBOARD_ATTRIBUTE_VALUE_TYPE.BYTE, "Is Minor", skCase)

    @staticmethod
    def get_artifacts(user_id):
        return {
            "TIKTOK_MESSAGE_" + user_id: {
                "name": "User " + user_id + " - MESSAGES"
            },
            "TIKTOK_PROFILE_" + user_id: {
                "name": "User " + user_id + " - PROFILE"
            },
            "TIKTOK_PROFILES_" + user_id: {
                "name": "User " + user_id + " - PROFILES"
            },
            "TIKTOK_SEARCHES_" + user_id: {
                "name": "User " + user_id + " - SEARCHES"
            },
            "TIKTOK_UNDARK_" + user_id: {
                "name": "User " + user_id + " - UNDARK"
            }
        }
        