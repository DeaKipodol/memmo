from openai import OpenAI
import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 현재 스크립트의 디렉토리 부모 디렉토리(chatbot/)를 시스템 경로에 추가
import json
from pinecone import Pinecone
from ai_app.assist.common import embedding_model, today  # today 함수 가져오기
from db.db_manager import get_mongo_collection  # 새로 추가된 모듈


#벡터db 객체 생성성
pinecone_api_key = os.getenv("PINECONE_API_KEY")
pc = Pinecone(pinecone_api_key)
pinecone_index = pc.Index("memmo")
#ai api 객체 생성
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
#몽고디비 객체 생성
collection_chats = get_mongo_collection("memmo", "chats")

embedding_model=embedding_model.ada

# 현재 파일의 디렉토리를 기준으로 절대 경로 생성
current_dir = os.path.dirname(os.path.abspath(__file__))
file_path = os.path.join(current_dir, "..", "data", "요약된대화.json")

with open(file_path, "r", encoding="utf-8") as f:
    summaries_list = json.load(f)
collection_chats.delete_many({})
#벡터db에 저장할 각벡터의 식별자자
next_id = 1

for list_idx, summaries in enumerate(summaries_list):
    # today()를 호출하여 현재 날짜를 가져오고, list_idx를 추가하여 날짜를 생성
    base_date = today()  # 예: "20250325"
    date = f"{base_date[:6]}{int(base_date[6:]) + list_idx:02}"  # 연월일 + 인덱스(문자열 포맷팅에서 숫자를 2자리로 맞춰 주었다)
    #하루치 요약 부분은 임베딩함.
    for summary in summaries:
        vector = client.embeddings.create(
            input=summary["요약"],
            model=embedding_model
        ).data[0].embedding

        metadata = {"date": date, "keyword": summary["주제"]}
        #실제 벡터db(pinecone)에 저장
        upsert_response =pinecone_index.upsert(\
            vectors=[
                {
                    "id":str(next_id),
                    "values": vector,
                    "metadata": metadata
                    }
                ]
            )
        #원본요약은 몽고 db에 저장
        query = {"_id": next_id}
        newvalues = {"$set": {"date": date, "keyword": summary["주제"],  "summary" : summary["요약"]}} 
        collection_chats.update_one(query,newvalues,upsert=True)

        if (next_id) % 5 == 0:    
            print(f"id: {next_id}")
            
        next_id += 1