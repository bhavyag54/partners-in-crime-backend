import email
import json
import pymongo
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from bson import ObjectId
import auth


# from .db import read, read_one, create, update, delete 
from fastapi.middleware.cors import CORSMiddleware

from auth import verify
from utils import check_user_exists_using_email, create_notification
client = pymongo.MongoClient("mongodb+srv://partnersInCrime:partners123@cluster0.grt0lph.mongodb.net/?retryWrites=true&w=majority")
db = client["partnersInCrime"]
app = FastAPI()

origins = [
    "http://localhost",
    "http://localhost:3000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


"""
---------------------------------------------------------------------
Main Page 
---------------------------------------------------------------------
"""


@app.get('/firsttimelogin')
async def first_time_login(req: Request):
  user = verify(req.headers.get("Authorization"))
  
  if not user:
    raise HTTPException(status_code=401, detail="Unauthorized")
  user_email = user.get("email", None)
  if not user_email:
    raise HTTPException(status_code=400, detail="User Email Not Found")
  fetch_user = check_user_exists_using_email(user_email)
  if not fetch_user:
    raise HTTPException(status_code=400, detail="User Not Found")  
  result = {}
  fetch_skills =  fetch_user.get("skills", None)
  if not fetch_skills or not len(fetch_skills) > 0:
    result["data"] = True
  else:
    result["data"] = False
  return result




"""
------------------------------------------------------------------------
Search Section
------------------------------------------------------------------------
"""



@app.get("/suggestions")
def autocomp(q):
    pipeline = [
   {
     '$search': {
       'index': 'autodefault',
       "autocomplete": {
         "query": q,
         "path":'name',
        "tokenOrder": "sequential"
       }
      }
  },
   {
     '$limit': 10
   },
   {
     '$project': {
       "name": 1
     }
   }
    ]
    count=0

    collections=db["users"]
    aggregatedresult=collections.aggregate(pipeline)
    result={}
    data=[]
    for i in list(aggregatedresult):
        count+=1
        data.append({"name":i["name"]})
    skillCollection = db['skills']
    pipeline[-1] = {
     '$project': {
       "name": 1,
        "subskills": 1
     }
   }
   
    aggregatedresult=skillCollection.aggregate(pipeline)
    for i in list(aggregatedresult):
        count+=1
        data.append({"name":i["name"]})
        subskills = i.get("subskills", [])
        for j in subskills:
            if j:
                count+=1
                data.append({"name":j})
    result["meta"]={"total":count}
    result["data"]=data

    return result

"""
------------------------------------------------------------------------
Project Section
------------------------------------------------------------------------
"""



@app.post("/addproject")
async def add_project(req: Request):
  
  user = verify(req.headers.get("Authorization"))
  
  if not user:
    raise HTTPException(status_code=401, detail="Unauthorized")
  user_email = user.get("email", None)
  if not user_email:
    raise HTTPException(status_code=400, detail="User Email Not Found")
  fetch_user = check_user_exists_using_email(user_email)
  if not fetch_user:
    raise HTTPException(status_code=400, detail="User Not Found")
  result = {}
  print(fetch_user['_id'])
  result['user_id'] = ObjectId(fetch_user['_id'])
  result['name'] = fetch_user.get("name", None)
  result['email'] = fetch_user.get("email", None)
  result ['image'] = fetch_user.get("photo", None)  
  data = await req.body()
  if data:
    data = json.loads(data)
  result['hero_image'] = data.get("image_url", None)
  result['title'] = data.get("title", None)
  if not result['title']:
    raise HTTPException(status_code=400, detail="Please Enter Title")
  result['description'] = data.get("description", None)
  if not result['description']:
    raise HTTPException(status_code=400, detail="Please Enter Description")
  result['idea'] = data.get("idea", None)
  if not result['idea']:
    raise HTTPException(status_code=400, detail="Please Enter Idea")
  result['required_skills'] = data.get("skills", None)
  if not result['required_skills']:
    raise HTTPException(status_code=400, detail="Please Enter Skills")
  
  try:
    collection = db["projects"]
    fetch_inserted_project = collection.insert_one(result)
    fid = str(fetch_inserted_project.inserted_id)
    result.pop("_id")
    result.pop("user_id")
    return {"meta":{"inserted_id":fid},"data":result}
  except Exception as e:
    print(e)
    raise HTTPException(status_code=500, detail="Error Adding Project")

@app.get("/fetchprojects")
def fetch_projects(req: Request,q:str,page:int=1,per_page:int=10):
  user = verify(req.headers.get("Authorization"))
  if not user:
    raise HTTPException(status_code=401, detail="Unauthorized")
  user_email = user.get("email", None)
  if not user_email:
    raise HTTPException(status_code=400, detail="User Email Not Found")
  fetch_user = check_user_exists_using_email(user_email)
  if not fetch_user:
    raise HTTPException(status_code=400, detail="User Not Found")
  query = {"user_id":{"$ne":ObjectId(fetch_user['_id'])}}
  if q:
    query["title"] = {"$regex":q,"$options":"i"}
  fetch_projects = db["projects"].find(query).sort("created_at",-1).skip((page-1)*per_page).limit(per_page)
  fetch_count = db["projects"].count_documents(query)
  if not fetch_projects:
    raise HTTPException(status_code=404, detail="No Projects Found")
  result = []
  for i in list(fetch_projects):
    i['_id'] = str(i['_id'])
    fetch_user_id = i.get("user_id", None)
    if fetch_user_id:
      i['user_id'] = str(i['user_id'])
    count_interested = db['projects'].count_documents({"_id":ObjectId(i['_id']),"interested_users":ObjectId(fetch_user_id)})
    if count_interested:
      i['interested'] = True
    if i.get("interested_users"):
      i.pop("interested_users")
    result.append(i)

  return {'meta':{'total_records':fetch_count,'page':page,'per_page':per_page}, 'data':result}

@app.get("/fetchuserprojects")
def fetch_projects(req: Request,page:int=1,per_page:int=10):
  user = verify(req.headers.get("Authorization"))
  if not user:
    raise HTTPException(status_code=401, detail="Unauthorized")
  user_email = user.get("email", None)
  if not user_email:
    raise HTTPException(status_code=400, detail="User Email Not Found")
  fetch_user = check_user_exists_using_email(user_email)
  if not fetch_user:
    raise HTTPException(status_code=400, detail="User Not Found")
  fetch_user_id = fetch_user.get("_id", None)
  fetch_projects = db["projects"].find({"user_id":ObjectId(fetch_user_id)}).sort("created_at",-1).skip((page-1)*per_page).limit(per_page)
  fetch_count = db["projects"].count_documents({})
  if not fetch_projects:
    raise HTTPException(status_code=404, detail="No Projects Found")
  result = []
  for i in list(fetch_projects):
    i['_id'] = str(i['_id'])
    fetch_user_id = i.get("user_id", None)
    if fetch_user_id:
      i['user_id'] = str(i['user_id'])
    count_interested = db['projects'].count_documents({"_id":ObjectId(i['_id']),"interested_users":ObjectId(fetch_user_id)})
    if count_interested:
      i['interested'] = True
    if i.get("interested_users"):
      i.pop("interested_users")
    result.append(i)

  return {'meta':{'total_records':fetch_count,'page':page,'per_page':per_page}, 'data':result}


@app.get("/project/{id}")
def fetch_project(req: Request,id:str):
  if not ObjectId.is_valid(id):
    raise HTTPException(status_code=400, detail="Invalid Project Id")
  user = verify(req.headers.get("Authorization"))
  if not user:
    raise HTTPException(status_code=401, detail="Unauthorized")
  user_email = user.get("email", None)
  if not user_email:
    raise HTTPException(status_code=400, detail="User Email Not Found")
  fetch_user = check_user_exists_using_email(user_email)
  if not fetch_user:
    raise HTTPException(status_code=400, detail="User Not Found")
  fetch_project = db["projects"].find_one({"_id":ObjectId(id)})
  if not fetch_project:
    raise HTTPException(status_code=404, detail="No Project Found")
  fetch_project['_id'] = str(fetch_project['_id'])
  fetch_project['user_id'] = str(fetch_project['user_id'])
  fetch_interested_users = fetch_project['interested_users']
  if fetch_interested_users:
    fetch_interested_users = [str(i) for i in fetch_interested_users]
    fetch_project['interested_users'] = fetch_interested_users
  
  return fetch_project

"""
------------------------------------------------------------------------
Notification Section
------------------------------------------------------------------------
"""









@app.get('/notifications')
def get_notifications(req: Request,page:int=1,per_page:int=10):
  # print(req.headers.get("Authorization"))
  user = verify(req.headers.get("Authorization"))
  if not user:
    raise HTTPException(status_code=401, detail="Unauthorized")
  user_email = user.get("email", None)
  
  if not user_email:
    raise HTTPException(status_code=400, detail="User Email Not Found")
  fetch_user = check_user_exists_using_email(user_email)
  if not fetch_user:
    raise HTTPException(status_code=400, detail="User Not Found")
  user_id = fetch_user.get("_id", None)
  print(user_id)
  fetch_notifications = db["notifications"].find({"user_id":ObjectId(user_id)}).sort("created_at",-1).skip((page-1)*per_page).limit(per_page)
  fetch_count = db["notifications"].count_documents({"user_id":user_id})
  if not fetch_notifications:
    raise HTTPException(status_code=404, detail="No Notifications Found")
  result = {'new':[],'read':[]}
  for i in list(fetch_notifications):
    i['_id'] = str(i['_id'])
    i['user_id'] = str(i['user_id'])
    created_at = i.pop("created_at")
    i['date'] = created_at.strftime("%d %b %Y")
    i['time'] = created_at.strftime("%I:%M %p")
    if i['is_read'] == False:
      result['new'].append(i)
      db["notifications"].update_one({"_id":ObjectId(i['_id'])},{"$set":{"is_read":True}})
    else:
      result['read'].append(i)
  return {'meta':{'total_records':fetch_count,'page':page,'per_page':per_page}, 'data':result}

@app.get('/isNewnotification')
def is_new_notification(req: Request):
  user = verify(req.headers.get("Authorization"))
  if not user:
    raise HTTPException(status_code=401, detail="Unauthorized")
  user_email = user.get("email", None)
  
  if not user_email:
    raise HTTPException(status_code=400, detail="User Email Not Found")
  fetch_user = check_user_exists_using_email(user_email)
  if not fetch_user:
    raise HTTPException(status_code=400, detail="User Not Found")
  user_id = fetch_user.get("_id", None)
  fetch_notifications = db["notifications"].find_one({"user_id":ObjectId(user_id),"is_read":False})
  if not fetch_notifications:
    return {"data":False}
  return {"data":True}


"""
------------------------------------------------------------------------
Favourites Section
------------------------------------------------------------------------
"""


@app.post("/addfavourite")
async def add_favourite(req: Request):
  user = verify(req.headers.get("Authorization"))
  if not user:
    raise HTTPException(status_code=401, detail="Unauthorized")
  user_email = user.get("email", None)
  if not user_email:
    raise HTTPException(status_code=400, detail="User Email Not Found")
  fetch_user = check_user_exists_using_email(user_email)
  if not fetch_user:
    raise HTTPException(status_code=400, detail="User Not Found")
  result = {}
  data = await req.body()
  if data:
    data = json.loads(data)
  result['user_id'] = fetch_user.get("_id", None)
  result['hackathon_id'] = data.get("hackathon_id", None)
  result['project_id'] = data.get("project_id", None)
  if result['hackathon_id']:
    result['hackathon_details'] = {
      "name": data.get("name",None),
      "image": data.get("image",None),
      "heroImage": data.get("heroImage",None),
      "website": data.get("website",None),
      "url": data.get("url",None),
      "location": data.get("location",None),
      "start": data.get("start",None),
      "end": data.get("end",None),
      "mode": data.get("mode",None)
      }
  try:
    collection = db["favourites"]
    fetch_inserted_project = collection.insert_one(result)
    fid = str(fetch_inserted_project.inserted_id)
    result.pop("_id")
    result.pop("user_id")
    
  except Exception as e:
    print(e)
    raise HTTPException(status_code=500, detail="Error Adding Favourite")
  if result['project_id']:
    try:
      db['projects'].update_one({"_id":ObjectId(result['project_id'])},{"$inc":{"interested":1}})
      print("Adding Interested User")
      db['projects'].update_one({"_id":ObjectId(result['project_id'])},{"$push":{"interested_users":ObjectId(fetch_user.get("_id", None))}})
    except Exception as e:
      print("Error",e)
      raise HTTPException(status_code=500, detail="Error Updating Project")
    try:
      
      fetch_project = db["projects"].find_one({"_id":ObjectId(result['project_id'])})
      fetch_project_handler_id = fetch_project.get("user_id", None)
      if fetch_project_handler_id:
        
        person_interested = fetch_user.get("name", None)
        title = fetch_project.get("title", None)
        description = person_interested + " has interested in your project " + title
        create_notification(fetch_project_handler_id,'Your Project Got Some Interests',description,'Interest')
    except Exception as e:
      print(e)
      raise HTTPException(status_code=500, detail="Error Creating Notification")
  return {"meta":{"inserted_id":fid},"data":result}
@app.delete('/deleteFavourite/{id}')
async def delete_favourite(req: Request,id:str,is_project:bool=False):
  user = verify(req.headers.get("Authorization"))
  if not user:
    raise HTTPException(status_code=401, detail="Unauthorized")
  user_email = user.get("email", None)
  if not user_email:
    raise HTTPException(status_code=400, detail="User Email Not Found")
  fetch_user = check_user_exists_using_email(user_email)
  if not fetch_user:
    raise HTTPException(status_code=400, detail="User Not Found")
  query = {}
  query['user_id'] = fetch_user.get("_id", None)
  if is_project:
    query['project_id'] = id
  else:
    query['hackathon_id'] = id  
  try:
    collection = db["favourites"]
    collection.delete_one(query)
    if is_project:
      db["projects"].update_one({"_id":ObjectId(id)},{"$inc":{"interested":-1}})
      db["projects"].update_one({"_id":ObjectId(id)},{"$pull":{"interested_users":fetch_user.get("_id", None)}})
    return {"meta":{"status":"success"},"data":{}}
  except Exception as e:
    print(e)
    raise HTTPException(status_code=500, detail="Error Adding Favourite")


@app.get("/fetchuserhackathons")
def fetch_favourite_hackathons(req: Request,page:int=1,per_page:int=10):
  user = verify(req.headers.get("Authorization"))
  if not user:
    raise HTTPException(status_code=401, detail="Unauthorized")
  user_email = user.get("email", None)
  if not user_email:
    raise HTTPException(status_code=400, detail="User Email Not Found")
  fetch_user = check_user_exists_using_email(user_email)
  if not fetch_user:
    raise HTTPException(status_code=400, detail="User Not Found")
  fetch_user_id = fetch_user.get("_id", None)
  fetch_hackathons = db["favourites"].find({"user_id":ObjectId(fetch_user_id),"project_id":None,"hackathon_details":{"$exists":True}}).sort("created_at",-1).skip((page-1)*per_page).limit(per_page)
  fetch_count = db["favourites"].count_documents({"user_id":ObjectId(fetch_user_id),"project_id":None,"hackathon_details":{"$exists":True}})
  if not fetch_hackathons:
    raise HTTPException(status_code=404, detail="No Hackathons Found")
  result = []
  for i in list(fetch_hackathons):
    i['_id'] = str(i['_id'])
    i['hackathon_id'] = str(i['hackathon_id'])
    i['user_id'] = str(i['user_id'])
    result.append(i)
  return {'meta':{'total_records':fetch_count,'page':page,'per_page':per_page}, 'data':result}


#FETCH
# fetch 
@app.get('/search')
def findkey(req: Request,q):
  count=db.users.count_documents({"name": q})
  cursor = db.users.find({"name": q})
  res={}
  res["meta"]={}
  res["data"]=[]
  for i in list(cursor):
    i["_id"]=str(i["_id"])
    res["data"].append(i)
  res["meta"]={"count":count}
  cursor = db.skills.find_one({"name": q})
  if(cursor):
    main_skill=cursor["name"]
    sub_skills=cursor["subskills"]
    fetch_main_profile=db.users.find({"skills":{"$regex":main_skill,"$options":"i"}})
    for i in list(fetch_main_profile):
      i["_id"]=str(i["_id"])
      res["data"].append(i)
    for sub_skill in sub_skills:
      fetch_sub_profile=db.users.find({"skills":{"$regex":sub_skill,"$options":"i"}})
      for i in list(fetch_sub_profile):
        i["_id"]=str(i["_id"])
        res["data"].append(i) 
  else:
    fetch_query=db.users.find({"skills":{"$regex":q,"$options":"i"}})
    for i in list(fetch_query):
      i["_id"]=str(i["_id"])
      res["data"].append(i)
    res["meta"]={"count":count}
  return res
app.include_router(auth.router)


@app.get("/")
def home():
    return {"Let's": "Go"}
