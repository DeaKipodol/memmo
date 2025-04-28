from ai_app.assist.common import client, model,makeup_response
import sys
from ai_app.assist.characters import instruction,system_role
import math
from ai_app.utils.function_calling import FunctionCalling,tools
from db.memory_manager import MemoryManager


class Chatbot:
    def __init__(self, model,system_role,instruction,**kwargs):
        """
        초기화:
          - context 리스트 생성 및 시스템 역할 설정
          - openai.api_key 설정
          - 사용할 모델명 저장
          - 사용자 이름
          - assistant 이름름
        """
        self.context = [{"role": "system","content": system_role}]
        self.model = model
        self.instruction=instruction

        self.max_token_size = 16 * 1024 #최대 토큰이상을 쓰면 오류가발생 따라서 토큰 용량관리가 필요.
        self.available_token_rate = 0.9#최대토큰의 90%만 쓰겠다.
    
        self.username=kwargs["user"]
        self.assistantname=kwargs["assistant"]
        self.memoryManager = MemoryManager()
        #self.context.extend(self.memoryManager.restore_chat())


    def add_user_message_in_context(self, message: str):
        """
        사용자 메시지 추가:
          - 사용자가 입력한 message를 context에 user 역할로 추가
        """
        self.context.append({
            "role": "user",
            "content": message,
            "saved" : False
            })

#completion출력
    def _send_request(self):
        try:
            response = client.chat.completions.create(
                model=self.model,
                messages=self.to_openai_contenxt(),
                temperature=0.5,
                top_p=1,
                max_tokens=256,
                frequency_penalty=0,
                presence_penalty=0
            ).model_dump()
        except Exception as e:
            print(f"Exception 오류({type(e)}) 발생:{e}")
            if 'maximum context length' in str(e):
                self.context.pop()
                return makeup_response("메시지 조금 짧게 보내줄래?")
            else: 
                return makeup_response("[챗봇에 문제가 발생했습니다. 잠시 뒤 이용해주세요]")
            
        return response
    def send_request(self):
        self.context[-1]['content'] += self.instruction
        return self._send_request()
    
#대화 문맥 추가*add response 수정-> 응답객체에서 content 추출출
    def add_response(self, response):
        response_message = {
                "role" : response['choices'][0]['message']["role"],
                "content" : response['choices'][0]['message']["content"],
                "saved" : False
        }
        self.context.append(response_message)

    def add_response_stream(self, response):
            self.context.append({
                    "role" : "assistant",
                    "content" : response,
                    "saved" : False,
                }
            )
    def get_response(self, response_text: str):
        """
        응답내용반환:
          - 메시지를 콘솔(또는 UI) 출력 후, 그대로 반환
        """
        print(response_text['choices'][0]['message']['content'])
        return response_text
    
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
    def to_openai_contenxt(self):
        return [{"role":v["role"], "content":v["content"]} for v in self.context]
    def save_chat(self):
        self.memoryManager.save_chat(self.context)   
if __name__ == "__main__":
    """
    <테스트 시나리오>대로 프로그램이 동작하도록 구성.
    1) 프로그램 구동: Chatbot 인스턴스 생성, 기본 context 포함
    2) 사용자 입력 -> context에 추가
    3) context를 API로 전송 -> 응답 수신
    4) 응답을 context에 추가, 콘솔에 출력
    5) 새 입력이 들어오면 (2)~(4) 반복
    """
    chatbot = Chatbot(
        model.basic,
        system_role=system_role,
        instruction=instruction,
        user= "대기",
        assistant= "memmo")
    func_calling=FunctionCalling(model.basic)
    print("===== Chatbot Started =====")
    print("초기 context:", chatbot.context)
    print("사용자가 'exit'라고 입력하면 종료합니다.\n")

    while True:
        # step-2: 사용자 입력 받기
        user_input = input("User > ")
        # 'exit' 입력 시 종료
        if user_input.strip().lower() == "exit":
            print("Chatbot 종료.")
            break
        chatbot.add_user_message_in_context(user_input)
        analyzed,analyzed_dict=func_calling.analyze(user_input,tools)
        '''"message": {
        "role": "assistant",
        "content": "안녕하세요! 어떻게 도와드릴까요?",
        "tool_calls": None,
        //
        호출 안했을 때
        
      }'''

        if analyzed_dict.get("tool_calls"): 
            """함수 실행결과를 포함해 응답한 응답객체 반환"""
            response = func_calling.run( analyzed,analyzed_dict, chatbot.context[:]) 
            chatbot.get_response(response)
        
        else:    
            response = chatbot.send_request()
        
            chatbot.get_response(response)
            chatbot.clean_context()
            chatbot.add_response(response)
            print(chatbot.context)


    # 종료 시점
    print("===== Chatbot Finished =====")