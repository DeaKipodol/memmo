from pymongo import MongoClient
import os
from ai_app.assist.common import today
from .db_manager import get_mongo_collection  # 새로 추가된 모듈

mongo_cluster=MongoClient(os.getenv("MONGO_CLUSTER_URI"))
'''만약 환경변수 MONGO_CLUSTER_URI가 설정되어 있지 않으면, 기본값으로 mongodb://localhost:27017을 사용하게 됩니다.

오류 메시지에서 localhost:27017 연결 실패를 언급하는 것으로 보아, 환경변수가 제대로 설정되지 않았거나 Atlas URI가 아닌 로컬 MongoDB를 사용하려고 시도한 것입니다'''

collection_chats = get_mongo_collection("memmo", "chats")

class MemoryManager:

    def save_chat(self,context):
        messages=[]
        for message in context:
            if message.get("saved",True):
                continue
            #문맥속 저장되지 않은 값만 골라낸다.
            messages.append({"date":today(), "role": message["role"], "content": message["content"]})

        #messages에 한개라도 값이 있다면 콜랙션에 값을 넣어라=>몽고디비안에 넣어라라
        if len(messages)>0:
            collection_chats.insert_many(messages)
            '''insert_many()는 MongoDB 컬렉션에 여러 개의 데이터를 한 번에 저장할 때 사용하는 함수
            MongoDB에서는 데이터를 문서(document) 단위로 저장합니다.
            **insert_one()**은 하나의 문서(하나의 데이터)를 저장할 때 사용합니다.
            **insert_many()**는 한 번에 여러 개의 문서를 저장할 때 사용합니다.
            지금 코드에서는 저장할 '문서'가 message임.
            '''
   
    def restore_chat(self,date=None):
        '''특정 날짜에 저장한 값(들들)을 context자료구조 형태로 받아옴'''
        search_date= date if date is not None else today()#특정 날짜를 준다면 그날짜로 아니면 현재 날짜로
        search_results=collection_chats.find({"date": search_date})
        restored_chat=[{"role": v["role"], "content": v["content"], "saved": True} for v in search_results]
        return restored_chat


