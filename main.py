import json
from fastapi import FastAPI, HTTPException,Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from ai_app.chatbot import Chatbot  # 기존 코드의 Chatbot 클래스 임포트
from ai_app.chatbotStream import ChatbotStream
from ai_app.assist.common import client, model
from fastapi.responses import StreamingResponse
import asyncio
from ai_app.assist.characters import instruction,system_role
from ai_app.utils.function_calling import FunctionCalling, tools # 단일 함수 호출
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 시작 시에는 별다른 동작 없이 바로 yield
    yield
    # 종료 시 실행할 코드
    print("FastAPI shutting down...")
    chatbot.save_chat()
    print("Saved!")


app = FastAPI(lifespan=lifespan)
'''chatbot = Chatbot(
    model=model.basic,
    system_role = system_role,
    instruction=instruction,
    user= "대기",
    assistant= "memmo"
    )  # 모델 초기화'''

chatbot=ChatbotStream(
    model=model.basic,
    system_role = system_role,
    instruction=instruction,
    user= "대기",
    assistant= "memmo"
    )
# CORS 설정 (안드로이드 앱 접근 허용)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
''' FastAPI는 Pydantic을 기본적으로 지원

FastAPI에서는 요청 데이터를 받을 때, request.json을 직접 쓰지 않고 Pydantic 모델을 매개변수로 넣으면 자동으로 처리해 줘요.
-Flask에서는 직접 Pydantic을 호출해야 함
Flask는 기본적으로 Pydantic을 지원하지 않기 때문에, request.json을 가져와서 Pydantic 모델로 수동으로 검증해야 해요.'''
class UserRequest(BaseModel):
    message: str

func_calling = FunctionCalling(model=model.basic)


@app.post("/stream-chat")
async def stream_chat(user_input: UserRequest):
    # 1) 사용자 메시지를 우선 원본 문맥에 추가
    chatbot.add_user_message_in_context(user_input.message)
    
    chatbot.context[-1]['content'] += chatbot.instruction

    analyzed= func_calling.analyze(user_input.message, tools)

    temp_context = chatbot.to_openai_context().copy()
    

    for tool_call in analyzed:  # analyzed는 list of function_call dicts
            if tool_call.type != "function_call":
                continue
            func_name = tool_call.name
            func_args = json.loads(tool_call.arguments)
            call_id = tool_call.call_id

            func_to_call = func_calling.available_functions.get(func_name)
            if not func_to_call:
                print(f"[오류] 등록되지 않은 함수: {func_name}")
                continue

            try:
               
                function_call_msg = {
                    "type": "function_call",  # 고정
                    "call_id": call_id,  # 딕셔너리 내에 있거나 key가 다를 수 있으니 주의
                    "name": func_name,
                    "arguments": tool_call.arguments  # dict -> JSON string
                }
                print(f"함수 호출 메시지: {function_call_msg}")
                if func_name == "search_internet":
                    # context는 이미 run 메서드의 매개변수로 받고 있음
                   func_response = func_to_call(chat_context=chatbot.context[:], **func_args)
                else:
                   func_response = func_to_call(**func_args)

                temp_context.extend([
                    function_call_msg,
                {
                    "type": "function_call_output",
                    "call_id": call_id,
                    "output": str(func_response)
                }
            ])
                print(temp_context)

            except Exception as e:
                print(f"[함수 실행 오류] {func_name}: {e}")

    # 4) 함수 호출 결과가 반영된 temp_context으로 스트리밍 응답을 생성
    async def generate_with_tool():
        try:
            # stream=True로 스트리밍 응답
            stream = client.responses.create(
            model=chatbot.model,
            input=temp_context,  # user/assistant 역할 포함된 list 구조
            top_p=1,
            stream=True,
            text={
                "format": {
                    "type": "text"  # 또는 "json_object" 등 (Structured Output 사용 시)
                }
            }
                )
              
            loading = True
            for event in stream:
                        match event.type:
                            case "response.created":
                                print("[🤖 응답 생성 시작]")
                                loading = True
                                # 로딩 애니메이션용 대기 시작
                                yield "⏳ GPT가 응답을 준비 중입니다..."
                                await asyncio.sleep(0)
                            case "response.output_text.delta":
                                if loading:
                                    print("\n[💬 응답 시작됨 ↓]")

                                    loading = False
                                # 글자 단위 출력
                                yield f"{event.delta}"
                                await asyncio.sleep(0)
                            

                            case "response.in_progress":
                                print("[🌀 응답 생성 중...]")
                                yield "[🌀 응답 생성 중...]"
                                yield "\n"

                            case "response.output_item.added":
                                if getattr(event.item, "type", None) == "reasoning":
                                    yield "[🧠 GPT가 추론을 시작합니다...]"
                                    yield "\n"
                                elif getattr(event.item, "type", None) == "message":
                                    yield "[📩 메시지 아이템 추가됨]"
                                    yield "\n"
                            #ResponseOutputItemDoneEvent는 우리가 case "response.output_item.done"에서 잡아야 해
                            case "response.output_item.done":
                                item = event.item
                                if item.type == "message" and item.role == "assistant":
                                    for part in item.content:
                                        if getattr(part, "type", None) == "output_text":
                                            completed_text= part.text
                            case "response.completed":
                                yield "\n"
                                #print(f"\n📦 최종 전체 출력: \n{completed_text}")
                            case "response.failed":
                                print("❌ 응답 생성 실패")
                                yield "❌ 응답 생성 실패"
                            case "error":
                                print("⚠️ 스트리밍 중 에러 발생!")
                                yield "⚠️ 스트리밍 중 에러 발생!"
                            case _:
                                yield "\n"
                                yield f"[📬 기타 이벤트 감지: {event.type}]"
        except Exception as e:
            yield f"\nStream Error: {str(e)}"
        finally:
            # 스트리밍이 끝나면 최종 응답을 원본 문맥에만 반영하고 임시문맥은 사용하지 않음
                            # 기존 clean 방식 유지
            chatbot.add_response_stream( completed_text)
            
                        # 최종 응답을 원본 문맥에 저장
    # 5) 함수 호출이 있을 때는 위의 generate_with_tool()를 사용
    return StreamingResponse(generate_with_tool(), media_type="text/plain")






