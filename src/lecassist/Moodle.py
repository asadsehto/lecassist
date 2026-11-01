import os
import httpx

url = os.environ["MOODLE_URL"] + "/webservice/rest/server.php"
token = os.environ["MOODLE_TOKEN"]

def call_moodle(function:str , **params)-> dict:
        all_params = {"wstoken":token , "moodlewsrestformat":"json", 
                  "wsfunction": function}
        all_params.update(params)
        r = httpx.get(url, params=all_params)
        data = r.json()
        if isinstance(data , dict) and "exception" in data:
           raise RuntimeError(function + ": " + data["message"])
        return data

def find_course(shortname:str):
      me = call_moodle("core_webservice_get_site_info")
      res = call_moodle("core_enrol_get_users_courses", userid=me["userid"])
      for r in res:
        if(r["shortname"].lower()==shortname.lower()):
             return {"id":r["id"], "shortname":r["shortname"],
                       "fullname": r["fullname"]}
      return None      

def find_week(course_id:int , week:int):
     section = call_moodle("core_course_get_contents", courseid = course_id)
     for s in section:
          if(s["section"]==week):
            return {"section":s["section"] ,"name":s["name"] }
     return None