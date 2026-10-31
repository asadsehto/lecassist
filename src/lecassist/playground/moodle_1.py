from lecassist.Moodle import call_moodle, find_course, find_week
import pprint

print(find_course("ai101"))
print(find_course("PHY999") )
print(find_week(2, 3)) 
print(find_week(2, 20))