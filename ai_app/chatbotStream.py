import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
import json
from ai_app.assist.common import client, model,makeup_response
from ai_app.assist.characters import instruction,system_role
import math
from ai_app.utils.function_calling import FunctionCalling,tools
from db.memory_manager import MemoryManager 
from ai_app.assist.ConversationContextFactory import ConversationContextFactory
from ai_app.assist.ConversationContextFactory import ContextDict 
from ai_app.utils.writingRequirementsManager import WritingRequirementsManager
from ai_app.assist.characters import get_update_field_prompt
from typing import List, TypedDict, Literal
from ai_app.utils.auto_summary import AutoSummary

class MessageDict(TypedDict):
    role: Literal["user", "assistant"]
    content: str
    saved: bool
class ChatbotStream:
    def __init__(self, model,system_role,instruction,**kwargs):
        """
        초기화:
          - context 리스트 생성 및 시스템 역할 설정
          - sub_contexts 서브 대화방 문맥을 저장할 딕셔너리 {필드이름,문맥,요약,질문} 구성
          - current_field = 현재 대화방 추적 (기본값: 메인 대화방
          - openai.api_key 설정
          - 사용할 모델명 저장
          - 사용자 이름
          - assistant 이름름
        """
        self.context = [{"role": "system","content": system_role}]
        # 서브 대화방 문맥을 저장할 딕셔너리
        #현재 대화 맥락을 인지,(필드대화냐 메인대화냐=> 즉 챗봇클래스 재활용)
        self.sub_contexts :dict[str, ContextDict] = {}        
        self.current_field = "main"
        
        self.model = model
        self.instruction=instruction

        self.max_token_size = 16 * 1024 #최대 토큰이상을 쓰면 오류가발생 따라서 토큰 용량관리가 필요.
        self.available_token_rate = 0.9#최대토큰의 90%만 쓰겠다.
    
        self.username=kwargs["user"]
        self.assistantname=kwargs["assistant"]
        self.memoryManager = MemoryManager()
        self.writingRequirementsManager=WritingRequirementsManager()
              # ← AutoSummary 초기화: 메시지 10회마다 요약과 동시에 벡터화
        self.auto_summary = AutoSummary(
            summarize_threshold=10,
            summary_length=100
        )
        self.field_instructions = {
            "purpose_background": "당신의 역할은 글을 쓰는 이유와 배경을 명확히 정리하는 역할입니다. 사용자의 질문에 자연스럽게 답하면서 사회성높은 셜록답게 사용자에게 당신이 필요한 정보를 물어보거나 대답하세요.사용자의 오타에는 언급하지말고 답하세요",
            "context_topic": "글의 주제나 상황을 중심으로 정리하는 역할입니다.사용자의 질문에 사회성높은 셜록답게 사용자에게 당신이 필요한 정보를 물어보거나 자연스럽게 대화하세요 사용자의 오타에는 언급하지말고 답하세요",
            "audience_scope": "대상 독자의 특성과 목적에 맞게 정리하는 역할입니다.사용자의 질문에 사회성높은 셜록답게 사용자에게 당신이 필요한 정보를 물어보거나 자연스럽게 대화하세요 사용자의 오타에는 언급하지말고 답하세요",
            "format_structure": "글의 구조나 형식을 논리적 순서로 정리하는 역할입니다.사용자의 질문에 사회성높은 셜록답게 사용자에게 당신이 필요한 정보를 물어보거나 자연스럽게 대화하세요 사용자의 오타에는 언급하지말고 답하세요",
            "logic_evidence": "논리 전개나 근거, 자료가 잘 드러나도록 정리하는 역할입니다.사용자의 질문에 사회성높은 셜록답게 사용자에게 당신이 필요한 정보를 물어보거나 자연스럽게 대화하세요 사용자의 오타에는 언급하지말고 답하세요",
            "expression_method": "문체, 어조, 시점 등을 일관되게 정리하는 역할입니다.사용자의 질문에 사회성높은 셜록답게 사용자에게 당신이 필요한 정보를 물어보거나 자연스럽게 대화하세요 사용자의 오타에는 언급하지말고 답하세요",
            "additional_constraints": "키워드, 금지어, 조건 등의 제약사항을 명확히 정리하는 역할입니다.사용자의 질문에 사회성높은 셜록답게 사용자에게 당신이 필요한 정보를 물어보거나 자연스럽게 대화하세요 사용자의 오타에는 언급하지말고 답하세요",
            "output_expectations": "결과물 형태나 완성 기준을 구체적으로 정리하는 역할입니다.사용자의 질문에 사회성높은 셜록답게 사용자에게 당신이 필요한 정보를 물어보거나 자연스럽게 대화하세요 사용자의 오타에는 언급하지말고 답하세요"
        }
       
    def add_user_message_in_context(self, message: str):
        """
        사용자 메시지 추가:
          - 사용자가 입력한 message를 context에 user 역할로 추가
        """
        assistant_message = {
            "role": "user",
            "content": message,
            "saved": False
        }
        if self.current_field == "main":
            self.context.append(assistant_message)
        else:
            self.sub_contexts[self.current_field]["messages"].append(assistant_message)
    #전송부
    def _send_request_Stream(self,temp_context=None):
        
        completed_text = ""

        if temp_context is None:
           current_context = self.get_current_context()
           openai_context = self.to_openai_context(current_context)
           stream = client.responses.create(
            model=self.model,
            input=openai_context,  
            top_p=1,
            stream=True,
            
            text={
                "format": {
                    "type": "text"  # 또는 "json_object" 등 (Structured Output 사용 시)
                }
            }
                )
        else:  
           stream = client.responses.create(
            model=self.model,
            input=temp_context,  # user/assistant 역할 포함된 list 구조
            top_p=1,
            stream=True,
            text={
                "format": {
                    "type": "text"  # 또는 "json_object" 등 (Structured Output 사용 시)
                }
            }
                )
        
        loading = True  # delta가 나오기 전까지 로딩 중 상태 유지       
        for event in stream:
            #print(f"event: {event}")
            match event.type:
                case "response.created":
                    print("[🤖 응답 생성 시작]")
                    loading = True
                    # 로딩 애니메이션용 대기 시작
                    print("⏳ GPT가 응답을 준비 중입니다...")
                    
                case "response.output_text.delta":
                    if loading:
                        print("\n[💬 응답 시작됨 ↓]")
                        loading = False
                    # 글자 단위 출력
                    print(event.delta, end="", flush=True)
                 

                case "response.in_progress":
                    print("[🌀 응답 생성 중...]")

                case "response.output_item.added":
                    if getattr(event.item, "type", None) == "reasoning":
                        print("[🧠 GPT가 추론을 시작합니다...]")
                    elif getattr(event.item, "type", None) == "message":
                        print("[📩 메시지 아이템 추가됨]")
                #ResponseOutputItemDoneEvent는 우리가 case "response.output_item.done"에서 잡아야 해
                case "response.output_item.done":
                    item = event.item
                    if item.type == "message" and item.role == "assistant":
                        for part in item.content:
                            if getattr(part, "type", None) == "output_text":
                                completed_text= part.text
                case "response.completed":
                    print("\n")
                    #print(f"\n📦 최종 전체 출력: \n{completed_text}")
                case "response.failed":
                    print("❌ 응답 생성 실패")
                case "error":
                    print("⚠️ 스트리밍 중 에러 발생!")
                case _:
                    
                    print(f"[📬 기타 이벤트 감지: {event.type}]")
        return completed_text
  
    def send_request_Stream(self):
      self.context[-1]['content']+=self.instruction
      #context문 맨 마지막에 instruction을 추가해라.
      return self._send_request_Stream()#->실제 보내는 코드는 _send_request 이다,
#챗봇에 맞게 문맥 파싱
    def add_response(self, response):
        response_message = {
            "role" : response['choices'][0]['message']["role"],
            "content" : response['choices'][0]['message']["content"],
            "saved" : False
        }
        self.context.append(response_message)

    def add_response_stream(self, response):
            """
    챗봇 응답을 현재 대화방의 문맥에 추가합니다.
    
    Args:
        response (str): 챗봇이 생성한 응답 텍스트.
    """
            assistant_message = {
            "role": "assistant",
            "content": response,
            "saved": False
        }
            if self.current_field == "main":
                # 메인 대화방 문맥에 추가
                self.context.append(assistant_message)
            else:
                if self.current_field not in self.sub_contexts:
                    self.sub_contexts[self.current_field] = {"messages": []}
                self.sub_contexts[self.current_field]["messages"].append(assistant_message)
      
            # ← 메시지가 들어올 때마다 요약·벡터화 검사 추가
            self.auto_summary.maybe_summarize(self.context)                    

    def get_response(self, response_text: str):
        """
        응답내용반환:
          - 메시지를 콘솔(또는 UI) 출력 후, 그대로 반환
        """
        print(response_text['choices'][0]['message']['content'])
        return response_text
#마지막 지침제거거
    def clean_context(self):
        '''
        1.context리스트에 마지막 인덱스부터 처음까지 순회한다
        2."instruction:\n"을 기준으로 문자열을 나눈다..첫user을 찾으면 아래 과정을 진행한다,
        3.첫 번째 부분 [0]만 가져온다. (즉, "instruction:\n" 이전의 문자열만 남긴다.)
        4.strip()을 적용하여 앞뒤의 공백이나 개행 문자를 제거한다.
        '''
        for idx in reversed(range(len(self.context))):
            if self.context[idx]['role']=='user':
                self.context[idx]["content"]=self.context[idx]['content'].split('instruction:\n')[0].strip()
                break
#질의응답 토큰 관리
    def handle_token_limit(self, response):
        # 누적 토큰 수가 임계점을 넘지 않도록 제어한다.
        try:
            current_usage_rate = response['usage']['total_tokens'] / self.max_token_size
            exceeded_token_rate = current_usage_rate - self.available_token_rate
            if exceeded_token_rate > 0:
                remove_size = math.ceil(len(self.context) / 10)
                self.context = [self.context[0]] + self.context[remove_size+1:]
        except Exception as e:
            print(f"handle_token_limit exception:{e}")
#api요소에만 해당하는부분만 반환해 문맥구성성
    def to_openai_context(self, context):
        return [{"role":v["role"], "content":v["content"]} for v in context]
    def get_current_context(self):
        if self.current_field == "main":
            return self.context
        else:
            return self.sub_contexts.get(self.current_field, {}).get("messages", [])
#db저장 메소드
    def save_chat(self):
        self.memoryManager.save_chat(self.context)   
 #@[필드 대화 관리]@

    def enter_sub_conversation(self, field_name: str) -> str:
        '''
        현재 들어간 필드 대화 진입 처리
        1.기존 필드방이 없다면 만든다
        2.현재 sub문맥에 진입한 필드방을 추가한다
        3.현재 진입한 필드의 이름을 바꾼다.
        4.진입메세지를 사용자에게 알린다.
        '''
        if field_name not in self.sub_contexts:
            self.sub_contexts[field_name] = ConversationContextFactory.create_context(field_name)
        self.current_field = field_name
        return f"{field_name} 에 대해 도와드릴게요.어떤 걸 도와 드릴까요?"
    
    def exit_sub_conversation(self) -> str:
        '''방나갈떄 처리로직
        1.현재 서브대화 내용을 요약 후 필드 내용 업데이트
        2.필드 대화를 나누었다는 것만 메인문맥에 추가
        3.반환값은 업데이트필드의 리턴으로로'''
        if self.current_field == "main":
            return "이미 메인 대화방에 있습니다."
        # 현재 서브 대화방 정보 가져오기
        field_name = self.current_field
        sub_context = self.sub_contexts[field_name]
        #문맥대화 가져옴
        conversation_text = " ".join([msg["content"] for msg in sub_context["messages"]])
        #현재 대화내용 요약
        try:
            response = client.responses.create(
                        model=model.advanced, 
                        input=[{
                        "role": "user", 
                        "content": f"{conversation_text}\n의 대화내용을 정리해라"
                    }],
                    )
            summarized_content = response.output_text # 요약된 내용 추출
        except Exception as e:
                summarized_content = "요약 실패: 원본 대화 내용 유지"
                print(f"에러 발생: {e}")
        # update_field 호출로 필드 업데이트 및 요약
        update_message = self.writingRequirementsManager.update_field(field_name, summarized_content)
        # 메인 문맥에 간단한 메시지 추가
        summary_message = f"필드 '{field_name}'에서 대화를 나눔"
        if summary_message:
            print(f"[대화 내용 요약]: {summary_message}")
        else:
            print("[대화 내용 요약이 없습니다.]")
        self.add_response_stream(summary_message)
        # 메인 대화방으로 전환
        self.current_field = "main"
        # update_field에서 반환된 메시지를 사용자에게 전달
        return update_message
    
    def add_user_message_in_context(self, message: str):
        user_message = {
            "role": "user",
            "content": message,
            "saved": False  # 추후 저장 여부 확인 시 사용
        }

        if self.current_field == "main":
            self.context.append(user_message)
        else:
            current_messages = self.get_current_context()
            current_messages.append(user_message)
    
    def get_current_context(self) -> List[MessageDict]:
        """
        현재 활성화된 대화방의 메시지 리스트를 반환합니다.
        - 메인 대화방이면 self.context
        - 서브 대화방이면 sub_contexts[field_name]["messages"]
        - 서브 방이 아직 없다면 즉시 생성
        """
        if self.current_field == "main":
            return self.context
        if self.current_field not in self.sub_contexts:
            self.sub_contexts[self.current_field] = ConversationContextFactory.create_context(self.current_field)
            '''만약 사용자가 방을 명시적으로 enter_sub_conversation() 하지 않고도, 바로 메시지를 보내는 경우:
            add_user_message_in_context()나 get_current_context() 호출 시 sub_contexts[field_name]이 없을 수 있음. 이때 자동으로 만들어주는 비상용 안전 로직'''
        return self.sub_contexts[self.current_field]["messages"]


if __name__ == "__main__":
    '''실행흐름
    단계	내용
1️⃣	사용자 입력 받음 (user_input)
2️⃣	→ add_user_message_in_context() 로 user 메시지를 문맥에 추가
3️⃣	→ analyze() 로 함수 호출이 필요한지 판단
4️⃣	→ 필요하면 함수 실행 + 결과를 temp_context에 추가
5️⃣	→ chatbot._send_request_Stream(temp_context) 로 응답 받음
6️⃣	✅ streamed_response 결과를 직접 add_response_stream()으로 수동 저장'''
    
    chatbot = ChatbotStream(
        model.advanced,
        system_role=system_role,
        instruction=instruction,
        user="대기",
        assistant="memmo")
    func_calling=FunctionCalling(model.advanced)
    print("===== Chatbot Started =====")
    print("초기 context:", chatbot.context)
    print("사용자가 'exit'라고 입력하면 종료합니다.\n")
    
    print(chatbot.sub_contexts)      # 출력: {}
    print(chatbot.current_field)

    while True:
        user_input = input("User > ")
        if user_input.strip().lower() == "exit":
            print("Chatbot 종료.")
            

        # 사용자 메시지를 문맥에 추가
        chatbot.add_user_message_in_context(user_input)

        # 사용자 입력 분석 (함수 호출 여부 확인)
        analyzed = func_calling.analyze(user_input, tools)

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
                    func_response=func_to_call(**func_args)
                

                temp_context.extend([
                    function_call_msg,
                {
                    "type": "function_call_output",
                    "call_id": call_id,
                    "output": str(func_response)
                }
            ])
              #  print("함수 실행후 임시문맥:{}".format(temp_context))

            except Exception as e:
                print(f"[함수 실행 오류] {func_name}: {e}")

        # 함수 결과 포함 응답 요청
        streamed_response = chatbot._send_request_Stream(temp_context=temp_context)
        temp_context = None
        chatbot.add_response_stream(streamed_response)
        print(chatbot.context)

    # === 분기 처리 끝 ===

    