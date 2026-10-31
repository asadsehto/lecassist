from lecassist.Moodle import call_moodle

res = call_moodle("core_enrol_get_users_courses" , userid = 3)
for r in res:
    print( r["shortname"] ,  r["fullname"])