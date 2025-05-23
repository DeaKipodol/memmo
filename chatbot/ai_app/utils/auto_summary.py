import os
import uuid
from pinecone import Pinecone
from openai import OpenAI
from ai_app.assist.common import client, model, embedding_model, today
from db.db_manager import get_mongo_collection

class AutoSummary:
    """
    - 대화 메시지 수(summarize_threshold) 이상 모이면 요약 → MongoDB 저장
    - 요약문(vectorize_threshold) 이상 누적되면 벡터화 → Pinecone 저장 → MongoDB 상태 업데이트
    - 사용자가 지난 대화 검색 요청 시 벡터DB 조회 → MongoDB에서 원문 반환 (search_memory)
    """
    def __init__(
        self,
        summarize_threshold: int = 10,
        summary_length: int = 100,
        mongo_db: str = "memmo",
        mongo_col: str = "summaries",
        pinecone_index_name: str = "memmo-ai"
    ):
        self.summarize_threshold = summarize_threshold
        self.summary_length = summary_length
        self.summary_col = get_mongo_collection(mongo_db, mongo_col)
        pc = Pinecone(os.getenv("PINECONE_API_KEY"))
        self.pinecone_index = pc.Index(pinecone_index_name)
        self.embed_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    def classify_query_type(self, user_query: str) -> str:
        # ✅ 기존 2분류에서 3분류로 확장됨 (memory_search / internet_search / context)
        prompt = f'''
        다음 사용자 입력의 유형을 판단하시오. 아래 중 하나로만 답하시오:

        - "memory_search": 과거 대화 내용(예: 이전에 말한 논문 주제, 내가 전에 얘기한 목적 등)을 회상하려는 질문
        - "internet_search": 실시간 정보나 외부 세계의 사실(예: 오늘 날씨, 서울대 위치, 환율 등)을 묻는 질문
        - "context": 그 외 일반적인 문맥 기반 대화

        질문: "{user_query}"
        '''
        try:
            response = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": prompt}]
            )
            classification = response.choices[0].message.content.strip().lower()
            return classification
        except Exception as e:
            print(f"[AutoSummary] classify_query_type 오류: {e}")
            return "context"

    def maybe_summarize(self, context: list[dict]):
        unsaved = [m for m in context if not m.get("saved", False)]
        if len(unsaved) < self.summarize_threshold:
            return

        system_msg = {
            "role": "system",
            "content": (
                f"다음 대화를 요약하되, 아래 형식에 따라 항목별로 구조화하여 작성하십시오.\n\n"
                f"출력 형식:\n"
                f"- 사용자 이름: (예: 이상윤)\n"
                f"- 작성 목적: (이 사용자가 글을 쓰려는 이유 또는 동기)\n"
                f"- 조건 및 스타일: (형식, 분량, 말투 등 요청된 제약 사항)\n"
                f"- 주요 대화 요약:\n"
                f"  - 사용자: ...\n"
                f"  - assistant: ...\n\n"
                f"[주의 사항]\n"
                f"- 반드시 모든 항목을 포함하십시오. 단, 항목 내용이 없을 경우 '없음'이라고 명시하십시오.\n"
                f"- 대화 도중 사용자의 목적이나 스타일이 변경되면 '작성 목적' 또는 '조건 및 스타일' 항목에 반영하십시오.\n"
                f"- 항목별 길이는 간결하되 핵심은 빠뜨리지 마십시오.\n"
                f"- 전체 요약 길이는 {self.summary_length}자 내외로 하되, 중요한 정보가 많으면 조금 더 써도 좋다"
            )
        }
        messages = [system_msg] + [{"role": m["role"], "content": m["content"]} for m in unsaved]
        resp = client.responses.create(model=model.advanced, input=messages)
        summary_text = resp.output_text.strip()

        print(f"[AutoSummary] 요약 완료: {summary_text}")

        doc_id = str(uuid.uuid4())
        doc = {"_id": doc_id, "date": today(), "summary": summary_text, "vectorized": True}
        self.summary_col.insert_one(doc)

        for m in unsaved:
            m["saved"] = True
        for m in unsaved:
            if m in context:
                context.remove(m)

        context[:] = [msg for msg in context if not (msg["role"] == "system" and msg["content"].startswith("이전 대화 요약:"))]
        context.append({
            "role": "system",
            "content": f"이전 대화 요약: {summary_text}",
            "saved": True
        })

        self.vectorize_single(doc_id, summary_text, doc["date"])

    def vectorize_single(self, doc_id: str, summary_text: str, date: str):
        try:
            vec = self.embed_client.embeddings.create(
                input=summary_text,
                model=embedding_model.ada
            ).data[0].embedding

            self.pinecone_index.upsert(vectors=[{
                "id": doc_id,
                "values": vec,
                "metadata": {"date": date}
            }])

            print(f"[AutoSummary] 벡터DB 업로드 완료: 문서 ID = {doc_id}")

        except Exception as e:
            print(f"[AutoSummary] 벡터화 실패: {e}")

    def search_memory(self, query_text: str, top_k: int = 5) -> list[str]:
        try:
            embed_result = self.embed_client.embeddings.create(
                input=query_text,
                model=embedding_model.ada
            )
            query_vector = embed_result.data[0].embedding

            search_results = self.pinecone_index.query(
                vector=query_vector,
                top_k=top_k,
                include_metadata=True
            )

            summaries = []
            for match in search_results["matches"]:
                summary_doc = self.summary_col.find_one({"_id": match["id"]})
                if summary_doc:
                    summaries.append(summary_doc["summary"])

            print(f"[AutoSummary] 🔍 검색된 유사 요약 개수: {len(summaries)}")
            return summaries

        except Exception as e:
            print(f"[AutoSummary] search_memory 오류: {e}")
            return []

    def answer_with_memory_check(self, user_query: str, context: list[dict]) -> list[str]:
        query_type = self.classify_query_type(user_query)
        print(f"[AutoSummary] 질의 분류 결과: {query_type}")
        

        # ✅ 새로 추가된 분기: 인터넷 검색 요청이면 fallback 자체를 생략
        if query_type == "internet_search":
            print("[AutoSummary] ⛔ 인터넷 검색 질문으로 분류됨 → memory 응답 중단")
            return None

        # ✅ memory_search로 분류되더라도 최근 3개의 대화문(context)에 질문과 동일한 내용이 있으면
        # → 불필요한 벡터 fallback을 생략하고 context 응답을 그대로 사용함.
        # → 목적: 방금 한 질문에 대해 "기억 못함" 회피가 발생하지 않도록 보완.
        if query_type == "memory_search" and len(context) > 0:
            recent_texts = [m["content"] for m in context[-3:] if "content" in m]
            recent_combined = " ".join(recent_texts)

            # GPT 응답 확인
            if user_query.strip() in recent_combined:
                messages = context + [{"role": "user", "content": user_query}]
                base_response = client.chat.completions.create(
                    model=model.advanced,
                    messages=messages
                ).choices[0].message.content.strip()

                # 회피성 응답이면 fallback 실행
                if any(kw in base_response for kw in ["모름", "기억", "접근할 수 없", "정보 없음"]):
                    print("[AutoSummary] ⚠ 동일 문장 있지만 회피 응답 → fallback 계속 진행")
                else:
                    print("[AutoSummary] ✅ 동일 문장 있고 정상 응답 → fallback 생략")
                    return None
        
        messages = context + [{"role": "user", "content": user_query}]
        try:
            base_response = client.chat.completions.create(
                model=model.advanced,
                messages=messages
            ).choices[0].message.content.strip()
        except Exception as e:
            print(f"[AutoSummary] GPT 기본 응답 실패: {e}")
            return ["죄송합니다. 응답을 생성하지 못했습니다."]

        fallback_check_prompt = f'''
        아래 사용자 질문과 GPT 응답을 보고,
        GPT가 질문에 명확히 답하지 못했거나,
        '기억하지 못함', '모름', '정보 없음', '개인정보 불가' 등의 표현으로 회피한 경우에는 "FALLBACK",
        그 외 정상적인 정보 전달이 포함된 응답이면 "OK"라고만 답하시오.

        [질문]: {user_query}
        [응답]: {base_response}
        '''
        try:
            fallback_classification = client.chat.completions.create(
                model=model.advanced,
                messages=[{"role": "user", "content": fallback_check_prompt}]
            ).choices[0].message.content.strip().upper()
        except Exception as e:
            print(f"[AutoSummary] fallback 판단 오류: {e}")
            fallback_classification = "OK"

        memory_summaries = self.search_memory(user_query)

        # ✅ keyword_triggered 제거됨 (오탐 방지 목적)
        should_fallback = (
            query_type != "internet_search" and (
            query_type == "memory_search"
            or fallback_classification == "FALLBACK"
            )
        )
        
        print(f"[AutoSummary] 🧠 fallback 판단 근거 → 질의유형: '{query_type}', 응답판단: '{fallback_classification}'") #05-22 fallback이 어떤 조건에 의해 트리거되었는가? 추가 

        if should_fallback:
            print("[AutoSummary] ✅ fallback 조건 충족 → memory 응답 수행")
            memory_summaries = self.search_memory(user_query)

            if not memory_summaries:
                print("[AutoSummary] ⚠ memory summary 없음 → context 기반으로 응답 생성")
                return [base_response]
            
            print(f"[AutoSummary] ✅ memory summary {len(memory_summaries)}개 사용 → memory 기반 응답 생성")

            memory_context = [
                {
                    "role": "system",
                    "content": (
                        "다음 질문은 아래 요약 내용을 반드시 참고하여 응답하시오. \n\n"
                        f"이전 대화 요약: {s}"
                    )
                }
                for s in memory_summaries
            ]

            try:
                fallback_response = client.chat.completions.create(
                    model=model.advanced,
                    messages=memory_context + context + [{"role": "user", "content": user_query}]
                ).choices[0].message.content.strip()
                return [fallback_response]
            except Exception as e:
                print(f"[AutoSummary] GPT fallback 응답 실패: {e}")
                return ["죄송합니다. 회상 응답도 실패했습니다."]

        print("[AutoSummary] ⚠ fallback 조건 미충족 → context 응답 사용")
        return [base_response]

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()

class SearchRequest(BaseModel):
    query_text: str
    top_k: int = 5

_auto_summary_instance: AutoSummary | None = None

def get_auto_summary() -> AutoSummary:
    global _auto_summary_instance
    if _auto_summary_instance is None:
        _auto_summary_instance = AutoSummary()
    return _auto_summary_instance

@router.post("/memory/search")
async def search_memory_endpoint(req: SearchRequest):
    auto_summary = get_auto_summary()
    results = auto_summary.search_memory(req.query_text, req.top_k)
    return {"results": results}
