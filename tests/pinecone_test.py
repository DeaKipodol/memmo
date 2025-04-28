from openai import OpenAI

import time
import os
from pinecone import Pinecone
pinecone_api_key = os.getenv("PINECONE_API_KEY")
pc = Pinecone(pinecone_api_key)
client=OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

index = pc.Index("memmo")
text1 = """
신데렐라는 어려서 부모를 잃고 불친절한 새어머니와 언니들과 삽니다. 요정 대모님이 나타나 해주신 마법으로 왕자님의 무도회에 참석합니다. 밤 12시가 되면 마법이 풀린다는 조건 하에 왕자님과 춤을 추고, 서둘러 도망치면서 유리구두 하나를 잃습니다. 왕자님은 유리구두를 가지고 신데렐라를 찾아 결혼하게 됩니다.
"""
text2 = """
컴퓨터 구조는 CPU, 메모리, 입출력 장치 등으로 구성되며, 이들은 버스로 연결됩니다. CPU는 명령어를 실행하고, 메모리는 데이터와 프로그램을 저장합니다. 입출력 장치는 사용자와 시스템 간의 상호작용을 담당합니다. 이 구성요소들은 소프트웨어와 하드웨어의 효율적인 동작을 위해 설계되었습니다.
"""

vector1 = client.embeddings.create(input=text1, model="text-embedding-ada-002").data[0].embedding
vector2 = client.embeddings.create(input=text2, model="text-embedding-ada-002").data[0].embedding
'''upsert는 "update"와 "insert"의 합성어로, 데이터베이스 작업에서 
  "존재하면 업데이트하고, 존재하지 않으면 삽입한다" 라는 의미
  upsert 작동 방식:

    벡터 ID 확인:
    upsert 작업은 제공된 벡터 데이터의 ID를 확인합니다.
    존재 여부 확인:
    해당 ID를 가진 벡터가 이미 데이터베이스에 존재하는지 확인합니다.
    업데이트 또는 삽입:
    존재하는 경우: 기존 벡터 데이터를 제공된 새 데이터로 업데이트합니다.
    존재하지 않는 경우: 새 벡터 데이터를 데이터베이스에 삽입합니다.

'''
index.upsert(
    vectors=[
        {
            "id": "vec1",
            "values": vector1,
            "metadata": {"input_date": "20230801"}
        },
        {
            "id": "vec2",
            "values": vector2,
            "metadata": {"input_date": "20230801"}
        },
    ],
    namespace="test1"
)


query = "동화책"
query_vector = client.embeddings.create(input=query, model="text-embedding-ada-002").data[0].embedding

search_response = index.query(
    filter={"input_date": "20230801"},
    top_k=10,  # top_k 값을 늘림
    vector=query_vector,
    namespace="test1"
)

print("search_response:", search_response)